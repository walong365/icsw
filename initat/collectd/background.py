#
# this file is part of icsw-server
#
# Copyright (C) 2014-2017 Andreas Lang-Nevyjel init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#

""" background job definitions for collectd-init """

import time

from lxml import etree
from lxml.builder import E

from initat.collectd.collectd_struct import ext_com
from initat.collectd.config import global_config
from initat.snmp.sink import SNMPSink
from initat.snmp.snmp_struct import value_cache
from initat.cluster.backbone.models import DeviceLogEntry
from initat.cluster.backbone.server_enums import icswServiceEnum
from initat.tools import logging_tools, server_command, process_tools

IPMI_LIMITS = ["ln", "lc", "lw", "uw", "uc", "un"]

# just info
IPMI_LONG_LIMITS = [
    "{} {}".format(
        {
            "l": "lower",
            "u": "upper",
        }[key[0]],
        {
            "n": "non-critical",
            "w": "warning",
            "c": "critical",
        }.get(key[1:], key[1:]),
    ) for key in IPMI_LIMITS]


def parse_ipmi_type(name, sensor_type):
    key, info, unit, base = ("", "", "", 1)
    parts = name.strip().split()
    lparts = name.strip().lower().split()
    key_str = "_".join([_p.replace(".", ",") for _p in lparts])
    # print "parse", name, sensor_type, parts
    if sensor_type == "rpm":
        if lparts[-1] == "tach":
            lparts.pop(-1)
        key = "fan.{}".format(key_str)
        if parts and parts[0].lower() in ["fan"]:
            parts.pop(0)
        info = "rotation of fan {}".format(" ".join(parts))
        unit = "RPM"
        base = 1000
    elif sensor_type == "degrees c":
        key = "temp.{}".format(key_str)
        info = "Temperature of {}".format(" ".join(parts))
        unit = "C"
    elif sensor_type == "volts":
        key = "volts.{}".format(key_str)
        info = "Voltage of {}".format(" ".join(parts))
        unit = "V"
    elif sensor_type == "watts":
        key = "watts.{}".format(key_str)
        info = "Power usage of {}".format(" ".join(parts))
        unit = "W"
    return key, info, unit, base


def parse_ipmi(in_lines):
    result = {}
    for line in in_lines:
        parts = [_part.strip() for _part in line.split("|")]
        if len(parts) == 10:
            s_type = parts[2].lower()
            if s_type not in ["discrete"] and parts[1].lower() not in ["na"]:
                key, info, unit, base = parse_ipmi_type(parts[0], s_type)
                if key:
                    # limit dict,
                    limits = {key: l_val for key, l_val in zip(IPMI_LIMITS, [{"na": ""}.get(value, value) for value in parts[4:10]])}
                    result[key] = (float(parts[1]), info, unit, base, limits)
    return result


class SNMPJob(object):
    def __init__(self, id_str, device_obj, ip, snmp_schemes, snmp_version, snmp_read_community, **kwargs):
        self.id_str = id_str
        self.device_obj = device_obj
        SNMPJob.add_job(self)
        self.ip = ip
        self.snmp_version = snmp_version
        self.snmp_schemes = snmp_schemes
        self.snmp_read_community = snmp_read_community
        self.device_name = kwargs.get("device_name", "")
        self.uuid = kwargs.get("uuid", "")
        self.max_runtime = kwargs.get("max_runtime", 45)
        self.run_every = kwargs.get("run_every", 30)
        self.snmp_read_timeout = kwargs.get("snmp_read_timeout", 10)
        self.counter = 0
        self.last_start = None
        # batch id we are currently waiting for
        self.waiting_for = None
        self.running = False
        # to remove from list
        self.to_remove = False
        self._init_snmp_handlers()
        # for storing values :-)
        self.__vcache = value_cache()
        self.check()

    def _init_snmp_handlers(self):
        # get snmp scheme object
        self.snmp_handlers = SNMPJob.snmp_sink.get_handlers(self.snmp_schemes)
        self.log(
            "new SNMP {}, ip is {} (V{:d}, {}), {}".format(
                self.id_str,
                self.ip,
                self.snmp_version,
                self.snmp_read_community,
                logging_tools.get_plural("valid scheme", len(self.snmp_handlers)),
            )
        )
        return
        # self.log(
        #    "new SNMP {}, ip is {} (V{:d}, {}), invalid scheme {}".format(
        #        self.id_str,
        #        self.ip,
        #        self.snmp_version,
        #        self.snmp_read_community,
        #        self.snmp_scheme
        #    ),
        #    logging_tools.LOG_LEVEL_CRITICAL
        # )

    def update_attribute(self, attr_name, attr_value):
        if attr_name == "snmp_schemes":
            _new_pks = set([_val.pk for _val in attr_value])
            _old_pks = set([_val.pk for _val in self.snmp_schemes])
            if _new_pks != _old_pks:
                self.snmp_schemes = attr_value
                self._init_snmp_handlers()
        else:
            if getattr(self, attr_name) != attr_value:
                self.log(
                    "changed attribute {} from '{}' to '{}'".format(
                        attr_name,
                        getattr(self, attr_name),
                        attr_value,
                    )
                )
                setattr(self, attr_name, attr_value)

    def _start_snmp_batch(self):
        if len(self.snmp_handlers):
            self.counter += 1
            self.last_start = time.time()
            self.running = True
            self.waiting_for = "{}:{:d}".format(self.id_str, self.counter)
            # see proc_data in snmp_relay_schemes
            fetch_list = sum([_handler.collect_fetch() for _handler in self.snmp_handlers], [])
            self.bg_proc.spc.start_batch(
                self.snmp_version,
                self.ip,
                self.snmp_read_community,
                self.waiting_for,
                True,
                self.snmp_read_timeout,
                *fetch_list
            )

    def feed(self, *res_list):
        self.waiting_for = None
        self.running = False
        error_list, _ok_list, res_dict = res_list[0:3]
        if error_list:
            self.log("error fetching SNMP data from {}".format(self.device_name), logging_tools.LOG_LEVEL_ERROR)
        else:
            headers = {
                "name": self.device_name,
                "uuid": self.uuid,
                "time": "{:d}".format(int(self.last_start))
            }
            mv_tree = E.machine_vector(
                simple="0",
                **headers
            )
            mon_info = E.monitor_info(
                **headers
            )
            for _handler in self.snmp_handlers:
                try:
                    _handler.collect_feed(res_dict, mv_tree=mv_tree, mon_info=mon_info, vc=self.__vcache)
                except:
                    self.log(
                        "error feeding for handler {} (IP {}): {}".format(
                            str(_handler),
                            self.ip,
                            process_tools.get_except_info(),
                        ),
                        logging_tools.LOG_LEVEL_CRITICAL
                    )
                    for _log_line in process_tools.icswExceptionInfo().log_lines:
                        self.log(_log_line, logging_tools.LOG_LEVEL_CRITICAL)
            # graphing
            self.bg_proc.process_data_xml(mv_tree, len(etree.tostring(mv_tree)))

    def check_for_timeout(self):
        diff_time = abs(time.time() - self.last_start)
        if diff_time > self.max_runtime:
            self.log(
                "timeout ({} > {})".format(
                    logging_tools.get_diff_time_str(diff_time),
                    logging_tools.get_diff_time_str(self.max_runtime)
                ),
                logging_tools.LOG_LEVEL_WARN
            )
            self.bg_proc.spc.trigger_timeout(self.waiting_for)
            return True
        else:
            return False

    def check(self, start=True):
        # return True if process is still running
        if self.running:
            if self.waiting_for:
                if self.check_for_timeout():
                    self.waiting_for = None
                    self.running = False
        else:
            if self.last_start is None or abs(int(time.time() - self.last_start)) >= self.run_every and not self.to_remove:
                if start:
                    self._start_snmp_batch()
        return self.running

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.bg_proc.log("[snmp {:d}] {}".format(self.idx, what), log_level)

    @staticmethod
    def feed_result(recv_data):
        job_id = recv_data[0]
        _found = False
        _w_ignore = set()
        for _job in SNMPJob.ref_dict.values():
            if _job.waiting_for == job_id:
                _job.feed(*recv_data[1:])
                _found = True
            else:
                _w_ignore.add(_job.waiting_for or "-")
        if not _found:
            SNMPJob.g_log(
                "job_id {} unknown, present {:d}: {}".format(
                    job_id,
                    len(_w_ignore),
                    ", ".join(list(_w_ignore)),
                ),
                logging_tools.LOG_LEVEL_ERROR
            )

    @staticmethod
    def setup(bg_proc):
        SNMPJob.run_idx = 0
        SNMPJob.bg_proc = bg_proc
        SNMPJob.ref_dict = {}
        SNMPJob.snmp_sink = SNMPSink(bg_proc.log)

    @staticmethod
    def add_job(new_job):
        SNMPJob.run_idx += 1
        new_job.idx = SNMPJob.run_idx
        SNMPJob.ref_dict[new_job.id_str] = new_job

    @staticmethod
    def g_log(what, log_level=logging_tools.LOG_LEVEL_OK):
        SNMPJob.bg_proc.log("[SNMP] {}".format(what), log_level)

    @staticmethod
    def get_job(job_id):
        return SNMPJob.ref_dict[job_id]

    @staticmethod
    def sync_jobs_with_id_list(id_list):
        # sync the currently configured jobs with the new id_list
        _cur = set(SNMPJob.ref_dict.keys())
        _new = set(id_list)
        _to_remove = _cur - _new
        _same = _cur & _new
        _to_create = _new - _cur
        if _to_remove:
            SNMPJob.g_log(
                "{} to remove: {}".format(
                    logging_tools.get_plural("SNMP job", len(_to_remove)),
                    ", ".join(sorted(list(_to_remove)))
                )
            )
            for _rem in _to_remove:
                SNMPJob.ref_dict[_rem].to_remove = True
        return _to_create, _to_remove, _same

    @staticmethod
    def check_jobs(start=True):
        _to_delete = []
        # print "-"
        for id_str, job in SNMPJob.ref_dict.items():
            # print "*", id_str, job.ip, job.running
            job.check(start=start)
            if job.to_remove and not job.running:
                _to_delete.append(id_str)
        if _to_delete:
            SNMPJob.g_log(
                "removing {}: {}".format(
                    logging_tools.get_plural("SNMP job", len(_to_delete)),
                    ", ".join(sorted(_to_delete))
                ),
                logging_tools.LOG_LEVEL_WARN
            )
            for _del in _to_delete:
                try:
                    del SNMPJob.ref_dict[_del]
                except KeyError:
                    SNMPJob.g_log(
                        "key {} not in ref_dict, strange...".format(_del),
                        logging_tools.LOG_LEVEL_CRITICAL
                    )


class IPMIBuilder(object):
    def __init__(self):
        pass

    def build(self, in_lines, **kwargs):
        ipmi_dict = parse_ipmi(in_lines.decode("utf-8").split("\n"))
        _tree = E.machine_vector(
            simple="0",
            **kwargs
        )
        _mon_info = E.monitor_info(
            **kwargs
        )
        for key, value in ipmi_dict.items():
            _val = E.mve(
                info=value[1],
                unit=value[2],
                base="{:d}".format(value[3]),
                v_type="f",
                value="{:.6f}".format(value[0]),
                name="ipmi.{}".format(key),
            )
            _tree.append(_val)
            _mon = E.value(
                info=value[1],
                unit=value[2],
                m_type="ipmi",
                base="{:d}".format(value[3]),
                v_type="f",
                value="{:.6f}".format(value[0]),
                name="ipmi.{}".format(key),
                **{_wn: _wv for _wn, _wv in value[4].items() if _wv.strip()}
            )
            _mon_info.append(_mon)
        return _tree, _mon_info

    def get_comline(self, _dev_xml):
        if _dev_xml.get("ipmi_interface", ""):
            _iface_str = " -I {}".format(_dev_xml.get("ipmi_interface"))
        else:
            _iface_str = ""
        return "/opt/cluster/bin/ipmitool -H {} -U {} -P {} {} sensor list".format(
            _dev_xml.get("ip"),
            _dev_xml.get("ipmi_username"),
            _dev_xml.get("ipmi_password"),
            _iface_str,
        )


class BackgroundJob(object):
    def __init__(self, id_str, device_obj, comline, builder, **kwargs):
        self.device_obj = device_obj
        self.id_str = id_str
        BackgroundJob.add_job(self)
        self.device_name = kwargs.get("device_name", "")
        self.uuid = kwargs.get("uuid", "")
        self.comline = comline
        self.builder = builder
        self.max_runtime = kwargs.get("max_runtime", 45)
        self.run_every = kwargs.get("run_every", 60)
        self.counter = 0
        self.last_start = None
        self.running = False
        # to remove from list
        self.to_remove = False
        self.log("new job {}, commandline is '{}'".format(self.id_str, self.comline))
        self.check()

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        BackgroundJob.bg_proc.log("[bgj {:d}] {}".format(self.idx, what), log_level)

    def update_attribute(self, attr_name, attr_value):
        if getattr(self, attr_name) != attr_value:
            self.log(
                "changed attribute {} from '{}' to '{}'".format(
                    attr_name,
                    getattr(self, attr_name),
                    attr_value,
                )
            )
            setattr(self, attr_name, attr_value)

    def _start_ext_com(self):
        self.counter += 1
        self.last_start = time.time()
        self.running = True
        self.__ec = ext_com(
            self.log,
            self.comline,
            debug=BackgroundJob.debug,
        )
        self.result = None
        if self.__ec.run():
            return self.__ec
        else:
            self.running = False
            return None

    def check_for_timeout(self):
        diff_time = int(abs(time.time() - self.last_start))
        if diff_time > self.max_runtime:
            self.log(
                "timeout ({:d} > {:d})".format(
                    diff_time,
                    self.max_runtime
                ),
                logging_tools.LOG_LEVEL_WARN
            )
            return True
        else:
            return False

    def terminate(self):
        self.log("terminating job", logging_tools.LOG_LEVEL_ERROR)
        self.__ec.terminate()

    def check(self, start=True):
        # return True if process is still running
        if self.running:
            self.result = self.__ec.finished()
            if self.result is None:
                if self.check_for_timeout():
                    DeviceLogEntry.new(
                        device=self.device_obj,
                        source=global_config["LOG_SOURCE_IDX"],
                        level=logging_tools.LOG_LEVEL_CRITICAL,
                        text="timeout for background job",
                    )
                    self.log("terminating")
                    self.terminate()
                    self.running = False
            else:
                self.running = False
                stdout, stderr = self.__ec.communicate()
                if BackgroundJob.debug or self.result:
                    self.log(
                        "done (RC={:d}) in {} (stdout: {}{})".format(
                            self.result,
                            logging_tools.get_diff_time_str(self.__ec.end_time - self.__ec.start_time),
                            logging_tools.get_plural("byte", len(stdout)),
                            ", stderr: {}".format(
                                logging_tools.get_plural("byte", len(stderr))
                            ) if stderr else "",
                        )
                    )
                if stdout and self.result == 0:
                    if self.builder is not None:
                        _tree, _mon_info = self.builder.build(stdout, name=self.device_name, uuid=self.uuid, time="{:d}".format(int(self.last_start)))
                        _num_mves = len(_tree.findall(".//mve"))
                        if not _num_mves:
                            DeviceLogEntry.new(
                                device=self.device_obj,
                                source=global_config["LOG_SOURCE_IDX"],
                                level=logging_tools.LOG_LEVEL_WARN,
                                text="reading from IPMI got no sensor results",
                            )
                        # graphing
                        BackgroundJob.bg_proc.process_data_xml(_tree, len(etree.tostring(_tree)))
                        # monitoring
                        BackgroundJob.bg_proc.send_to_remote_server(
                            icswServiceEnum.monitor_server,
                            str(server_command.srv_command(command="monitoring_info", mon_info=_mon_info))
                        )
                    else:
                        BackgroundJob.log("no builder set", logging_tools.LOG_LEVEL_ERROR)
                if stderr:
                    DeviceLogEntry.new(
                        device=self.device_obj,
                        source=global_config["LOG_SOURCE_IDX"],
                        level=logging_tools.LOG_LEVEL_ERROR,
                        text="error running background job ({})".format(
                            logging_tools.get_plural(
                                "line", len(stderr.decode("utf-8").strip().split("\n")),
                            )
                        )
                    )
                    self.log("error output follows, cmdline was '{}'".format(self.comline))
                    for line_num, line in enumerate(stderr.decode("utf-8").strip().split("\n")):
                        self.log("  {:3d} {}".format(line_num + 1, line), logging_tools.LOG_LEVEL_ERROR)
        else:
            if self.last_start is None or abs(int(time.time() - self.last_start)) >= self.run_every and not self.to_remove:
                if start:
                    self._start_ext_com()
        return self.running
    # static methods

    @staticmethod
    def setup(bg_proc):
        BackgroundJob.run_idx = 0
        BackgroundJob.bg_proc = bg_proc
        BackgroundJob.debug = global_config["DEBUG"]
        BackgroundJob.ref_dict = {}

    @staticmethod
    def g_log(what, log_level=logging_tools.LOG_LEVEL_OK):
        BackgroundJob.bg_proc.log("[bgj] {}".format(what), log_level)

    @staticmethod
    def add_job(new_job):
        BackgroundJob.run_idx += 1
        new_job.idx = BackgroundJob.run_idx
        BackgroundJob.ref_dict[new_job.id_str] = new_job

    @staticmethod
    def get_job(job_id):
        return BackgroundJob.ref_dict[job_id]

    @staticmethod
    def sync_jobs_with_id_list(id_list):
        # sync the currently configures jobs with the new id_list
        _cur = set(BackgroundJob.ref_dict.keys())
        _new = set(id_list)
        _to_remove = _cur - _new
        _same = _cur & _new
        _to_create = _new - _cur
        if _to_remove:
            BackgroundJob.g_log(
                "{} to remove: {}".format(
                    logging_tools.get_plural("background job", len(_to_remove)),
                    ", ".join(sorted(list(_to_remove)))
                )
            )
            for _rem in _to_remove:
                BackgroundJob.ref_dict[_rem].to_remove = True
        return _to_create, _to_remove, _same

    @staticmethod
    def check_jobs(start=True):
        _to_delete = []
        for id_str, job in BackgroundJob.ref_dict.items():
            job.check(start=start)
            if job.to_remove and not job.running:
                _to_delete.append(id_str)
        if _to_delete:
            BackgroundJob.g_log(
                "removing {}: {}".format(
                    logging_tools.get_plural(
                        "background job", len(_to_delete)
                    ),
                    ", ".join(sorted(_to_delete))
                ),
                logging_tools.LOG_LEVEL_WARN
            )
            for _del in _to_delete:
                del BackgroundJob.ref_dict[_del]
