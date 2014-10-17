#
# this file is part of collectd-init
#
# Copyright (C) 2014 Andreas Lang-Nevyjel init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 2 as
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

from initat.collectd.struct import ext_com
from initat.collectd.collectd_types import *  # @UnusedWildImport
from initat.snmp_relay.snmp_process import simple_snmp_oid
from lxml import etree  # @UnresolvedImports
from lxml.builder import E  # @UnresolvedImports
import logging_tools
import server_command
import time

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


class snmp_scheme(object):
    def __init__(self):
        pass

    def get_oid_list(self):
        _list = []
        if hasattr(self, "var_list"):
            _list.append(("V", self.var_list))
        if hasattr(self, "table_list"):
            _list.append(("T", self.table_list))
        return _list

    def simplify_dict(self, in_dict):
        # simplify dict (reduce keys)
        while True:
            if len(set([list(_key)[0] for _key in in_dict.iterkeys()])) == 1:
                in_dict = {tuple(list(_key)[1:]): _value for _key, _value in in_dict.iteritems()}
            else:
                break
        if len(set([len(_key) for _key in in_dict.iterkeys()])) == 1:
            # all keys have the same length, remove from behind
            while True:
                if len(set([list(_key)[-1] for _key in in_dict.iterkeys()])) == 1:
                    in_dict = {tuple(list(_key)[:-1]): _value for _key, _value in in_dict.iteritems()}
                else:
                    break
        return in_dict

    def build(self, job, res_dict):
        headers = {
            "name": job.device_name,
            "uuid": job.uuid,
            "time": "{:d}".format(int(job.last_start))
        }
        _tree = E.machine_vector(
            simple="0",
            **headers
        )
        _mon_info = E.monitor_info(
            **headers
        )
        self.feed_trees(_tree, _mon_info, res_dict)
        return _tree, _mon_info


class apcv1_scheme(snmp_scheme):
    var_list = [simple_snmp_oid("1.3.6.1.4.1.318.1.1.12.2.3.1.1.2.1")]

    def feed_trees(self, mv_tree, mon_tree, res_dict):
        mv_tree.append(
            E.mve(
                info="Ampere",
                unit="A",
                base="1",
                v_type="f",
                value="{:.1f}".format(float(res_dict.values()[0]) / 10.),
                name="apc.ampere.used",
            )
        )


class apc_upc_v1_scheme(snmp_scheme):
    var_list = [
        simple_snmp_oid("1.3.6.1.4.1.318.1.1.1.3.2.1.0"),
        simple_snmp_oid("1.3.6.1.4.1.318.1.1.1.3.2.2.0"),
        simple_snmp_oid("1.3.6.1.4.1.318.1.1.1.3.2.3.0"),
        simple_snmp_oid("1.3.6.1.4.1.318.1.1.1.3.2.4.0"),
        simple_snmp_oid("1.3.6.1.4.1.318.1.1.1.4.2.1.0"),
        simple_snmp_oid("1.3.6.1.4.1.318.1.1.1.4.2.2.0"),
        simple_snmp_oid("1.3.6.1.4.1.318.1.1.1.4.2.3.0"),
        simple_snmp_oid("1.3.6.1.4.1.318.1.1.1.4.2.4.0"),
    ]

    def feed_trees(self, mv_tree, mon_tree, res_dict):
        res_dict = self.simplify_dict(res_dict)
        mv_tree.extend([
            E.mve(
                info="Input frequency",
                unit="1/s",
                base="1",
                v_type="i",
                value="{:d}".format(res_dict[(3, 2, 4)]),
                name="upc.frequency.in",
            ),
            E.mve(
                info="Output frequency",
                unit="1/s",
                base="1",
                v_type="i",
                value="{:d}".format(res_dict[(4, 2, 2)]),
                name="upc.frequency.out",
            ),
            E.mve(
                info="Input line voltage",
                unit="V",
                base="1",
                v_type="i",
                value="{:d}".format(res_dict[(3, 2, 1)]),
                name="upc.voltage.in.line",
            ),
            E.mve(
                info="Input line voltage max",
                unit="V",
                base="1",
                v_type="i",
                value="{:d}".format(res_dict[(3, 2, 2)]),
                name="upc.voltage.in.line_max",
            ),
            E.mve(
                info="Input line voltage min",
                unit="V",
                base="1",
                v_type="i",
                value="{:d}".format(res_dict[(3, 2, 3)]),
                name="upc.voltage.in.line_min",
            ),
            E.mve(
                info="Output voltage",
                unit="V",
                base="1",
                v_type="i",
                value="{:d}".format(res_dict[(4, 2, 1)]),
                name="upc.voltage.out",
            ),
            E.mve(
                info="Output load",
                unit="%",
                base="1",
                v_type="i",
                value="{:d}".format(res_dict[(4, 2, 3)]),
                name="upc.load.out",
            ),
            E.mve(
                info="Output current",
                unit="A",
                base="1",
                v_type="i",
                value="{:d}".format(res_dict[(4, 2, 4)]),
                name="upc.ampere.out",
            ),
        ])


class snmp_job(object):
    def __init__(self, id_str, ip, snmp_scheme, snmp_version, snmp_read_community, **kwargs):
        self.id_str = id_str
        snmp_job.add_job(self)
        self.ip = ip
        self.snmp_version = snmp_version
        self.snmp_scheme = snmp_scheme
        self.snmp_read_community = snmp_read_community
        self.device_name = kwargs.get("device_name", "")
        self.uuid = kwargs.get("uuid", "")
        self.max_runtime = kwargs.get("max_runtime", 45)
        self.run_every = kwargs.get("run_every", 30)
        self.counter = 0
        self.last_start = None
        # batch id we are currently waiting for
        self.waiting_for = None
        self.running = False
        # to remove from list
        self.to_remove = False
        self._init_scheme_object()
        self.check()

    def _init_scheme_object(self):
        # get snmp scheme object
        scheme_name = "{}_scheme".format(self.snmp_scheme)
        if scheme_name in globals():
            self.snmp_scheme_object = globals()[scheme_name]()
            self.log(
                "new SNMP {}, ip is {} (V{:d}, {}), valid scheme {}".format(
                    self.id_str,
                    self.ip,
                    self.snmp_version,
                    self.snmp_read_community,
                    self.snmp_scheme
                )
            )
        else:
            self.snmp_scheme_object = None
            self.log(
                "new SNMP {}, ip is {} (V{:d}, {}), invalid scheme {}".format(
                    self.id_str,
                    self.ip,
                    self.snmp_version,
                    self.snmp_read_community,
                    self.snmp_scheme
                ),
                logging_tools.LOG_LEVEL_CRITICAL
            )

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
            if attr_name == "snmp_scheme":
                self._init_scheme_object()

    def _start_snmp_batch(self):
        if self.snmp_scheme_object:
            self.counter += 1
            self.last_start = time.time()
            self.running = True
            self.waiting_for = "{}_{:d}".format(self.uuid, self.counter)
            # see proc_data in snmp_relay_schemes
            self.bg_proc.spc.start_batch(
                self.snmp_version,
                self.ip,
                self.snmp_read_community,
                self.waiting_for,
                True,
                10,
                *self.snmp_scheme_object.get_oid_list()
            )
            # self.bg_proc.spc.start_batch(
            #    self.waiting_for,
            #    self.ip,
            #    self.snmp_version,
            #    self.snmp_read_community,
            #    self.snmp_scheme_object.get_oid_list()
            # )

    def feed(self, *res_list):
        self.waiting_for = None
        self.running = False
        error_list, _ok_list, res_dict = res_list[0:3]
        if error_list:
            self.log("error fetching SNMP data from {}".format(self.device_name), logging_tools.LOG_LEVEL_ERROR)
        else:
            _tree, _mon_info = self.snmp_scheme_object.build(self, res_dict)
            # graphing
            self.bg_proc.feed_data(etree.tostring(_tree))  # @UndefinedVariable

    def check_for_timeout(self):
        diff_time = int(abs(time.time() - self.last_start))
        if diff_time > self.max_runtime:
            self.log("timeout ({:d} > {:d})".format(diff_time, self.max_runtime), logging_tools.LOG_LEVEL_WARN)
            return True
        else:
            return False

    def check(self):
        # return True if process is still running
        if self.running:
            if self.waiting_for:
                if self.check_for_timeout():
                    self.waiting_for = None
                    self.running = False
        else:
            if self.last_start is None or abs(int(time.time() - self.last_start)) >= self.run_every and not self.to_remove:
                self._start_snmp_batch()
        return self.running

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.bg_proc.log(u"[snmp {:d}] {}".format(self.idx, what), log_level)

    @staticmethod
    def feed_result(recv_data):
        job_id = recv_data[0]
        _found = False
        for _job in snmp_job.ref_dict.itervalues():
            if _job.waiting_for == job_id:
                _job.feed(*recv_data[1:])
                _found = True
        if not _found:
            snmp_job.g_log("job_id {} unknown".format(job_id), logging_tools.LOG_LEVEL_ERROR)

    @staticmethod
    def setup(bg_proc):
        snmp_job.run_idx = 0
        snmp_job.bg_proc = bg_proc
        snmp_job.ref_dict = {}

    @staticmethod
    def add_job(new_job):
        snmp_job.run_idx += 1
        new_job.idx = snmp_job.run_idx
        snmp_job.ref_dict[new_job.id_str] = new_job

    @staticmethod
    def g_log(what, log_level=logging_tools.LOG_LEVEL_OK):
        snmp_job.bg_proc.log(u"[SNMP] {}".format(what), log_level)

    @staticmethod
    def get_job(job_id):
        return snmp_job.ref_dict[job_id]

    @staticmethod
    def sync_jobs_with_id_list(id_list):
        # sync the currently configures jobs with the new id_list
        _cur = set(snmp_job.ref_dict.keys())
        _new = set(id_list)
        _to_remove = _cur - _new
        _same = _cur & _new
        _to_create = _new - _cur
        if _to_remove:
            snmp_job.g_log("{} to remove: {}".format(logging_tools.get_plural("SNMP job", len(_to_remove)), ", ".join(sorted(list(_to_remove)))))
            for _rem in _to_remove:
                snmp_job.ref_dict[_rem].to_remove = True
        return _to_create, _to_remove, _same

    @staticmethod
    def check_jobs():
        _to_delete = []
        for id_str, job in snmp_job.ref_dict.iteritems():
            job.check()
            if job.to_remove and not job.running:
                _to_delete.append(id_str)
        if _to_delete:
            snmp_job.g_log(
                "removing {}: {}".format(
                    logging_tools.get_plural("SNMP job", len(_to_delete)),
                    ", ".join(sorted(_to_delete))
                ),
                logging_tools.LOG_LEVEL_WARN
            )
            for _del in _to_delete:
                del bg_job.ref_dict[_del]


class ipmi_builder(object):
    def __init__(self):
        pass

    def build(self, in_lines, **kwargs):
        ipmi_dict = parse_ipmi(in_lines.split("\n"))
        _tree = E.machine_vector(
            simple="0",
            **kwargs
        )
        _mon_info = E.monitor_info(
            **kwargs
        )
        for key, value in ipmi_dict.iteritems():
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
                **{_wn: _wv for _wn, _wv in value[4].iteritems() if _wv.strip()}
            )
            _mon_info.append(_mon)
        return _tree, _mon_info

    def get_comline(self, _dev_xml):
        if _dev_xml.get("ipmi_interface", ""):
            _iface_str = " -I {}".format(_dev_xml.get("ipmi_interface"))
        else:
            _iface_str = ""
        return "/usr/bin/ipmitool -H {} -U {} -P {} {} sensor list".format(
            _dev_xml.get("ip"),
            _dev_xml.get("ipmi_username"),
            _dev_xml.get("ipmi_password"),
            _iface_str,
        )


class bg_job(object):
    def __init__(self, id_str, comline, builder, **kwargs):
        self.id_str = id_str
        bg_job.add_job(self)
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
        bg_job.bg_proc.log(u"[bgj {:d}] {}".format(self.idx, what), log_level)

    def update_attribute(self, attr_name, attr_value):
        if getattr(self, attr_name) != attr_value:
            self.log("changed attribute {} from '{}' to '{}'".format(
                attr_name,
                getattr(self, attr_name),
                attr_value,
                ))
            setattr(self, attr_name, attr_value)

    def _start_ext_com(self):
        self.counter += 1
        self.last_start = time.time()
        self.running = True
        self.__ec = ext_com(
            self.log,
            self.comline,
        )
        self.result = None
        self.__ec.run()
        return self.__ec

    def check_for_timeout(self):
        diff_time = int(abs(time.time() - self.last_start))
        if diff_time > self.max_runtime:
            self.log("timeout ({:d} > {:d})".format(diff_time, self.max_runtime), logging_tools.LOG_LEVEL_WARN)
            return True
        else:
            return False

    def terminate(self):
        self.log("terminating job", logging_tools.LOG_LEVEL_ERROR)
        self.__ec.terminate()

    def check(self):
        # return True if process is still running
        if self.running:
            self.result = self.__ec.finished()
            if self.result is None:
                if self.check_for_timeout():
                    self.log("terminating")
                    self.terminate()
                    self.running = False
            else:
                self.running = False
                stdout, stderr = self.__ec.communicate()
                self.log(
                    "done (RC={:d}) in {} (stdout: {}{})".format(
                        self.result,
                        logging_tools.get_diff_time_str(self.__ec.end_time - self.__ec.start_time),
                        logging_tools.get_plural("byte", len(stdout)),
                        ", stderr: {}".format(logging_tools.get_plural("byte", len(stderr))) if stderr else "",
                    )
                )
                if stdout and self.result == 0:
                    if self.builder is not None:
                        _tree, _mon_info = self.builder.build(stdout, name=self.device_name, uuid=self.uuid, time="{:d}".format(int(self.last_start)))
                        # graphing
                        bg_job.bg_proc.feed_data(etree.tostring(_tree))  # @UndefinedVariable
                        # monitoring
                        bg_job.bg_proc.send_to_md(unicode(server_command.srv_command(command="monitoring_info", mon_info=_mon_info)))
                    else:
                        bg_job.log("no builder set", logging_tools.LOG_LEVEL_ERROR)
                if stderr:
                    for line_num, line in enumerate(stderr.strip().split("\n")):
                        self.log("  {:3d} {}".format(line_num + 1, line), logging_tools.LOG_LEVEL_ERROR)
        else:
            if self.last_start is None or abs(int(time.time() - self.last_start)) >= self.run_every and not self.to_remove:
                self._start_ext_com()
        return self.running
    # static methods

    @staticmethod
    def setup(bg_proc):
        bg_job.run_idx = 0
        bg_job.bg_proc = bg_proc
        bg_job.ref_dict = {}

    @staticmethod
    def g_log(what, log_level=logging_tools.LOG_LEVEL_OK):
        bg_job.bg_proc.log(u"[bgj] {}".format(what), log_level)

    @staticmethod
    def add_job(new_job):
        bg_job.run_idx += 1
        new_job.idx = bg_job.run_idx
        bg_job.ref_dict[new_job.id_str] = new_job

    @staticmethod
    def get_job(job_id):
        return bg_job.ref_dict[job_id]

    @staticmethod
    def sync_jobs_with_id_list(id_list):
        # sync the currently configures jobs with the new id_list
        _cur = set(bg_job.ref_dict.keys())
        _new = set(id_list)
        _to_remove = _cur - _new
        _same = _cur & _new
        _to_create = _new - _cur
        if _to_remove:
            bg_job.g_log("{} to remove: {}".format(logging_tools.get_plural("background job", len(_to_remove)), ", ".join(sorted(list(_to_remove)))))
            for _rem in _to_remove:
                bg_job.ref_dict[_rem].to_remove = True
        return _to_create, _to_remove, _same

    @staticmethod
    def check_jobs():
        _to_delete = []
        for id_str, job in bg_job.ref_dict.iteritems():
            job.check()
            if job.to_remove and not job.running:
                _to_delete.append(id_str)
        if _to_delete:
            bg_job.g_log(
                "removing {}: {}".format(
                    logging_tools.get_plural(
                        "background job", len(_to_delete)
                    ),
                    ", ".join(sorted(_to_delete))
                ),
                logging_tools.LOG_LEVEL_WARN
            )
            for _del in _to_delete:
                del bg_job.ref_dict[_del]
