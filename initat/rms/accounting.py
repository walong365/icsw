# Copyright (C) 2001-2014 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of rms-tools
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

""" rms-server, accounting process """

from django.db import connection
from django.db.models import Q
from initat.cluster.backbone.models import rms_job, rms_job_run, rms_pe_info, \
    rms_project, rms_department, rms_pe, rms_queue, user, device, cluster_timezone
from initat.rms.config import global_config
from initat.rms.functions import call_command
from lxml import etree  # @UnresolvedImport @UnusedImport
import commands
import datetime
import logging_tools
import os
import pprint  # @UnusedImport
import server_command
import threading_tools
import time

_OBJ_DICT = {
    "rms_queue": rms_queue,
    "rms_project": rms_project,
    "rms_department": rms_department,
    "rms_pe": rms_pe,
}


def call_command(command, log_com=None):
    start_time = time.time()
    stat, out = commands.getstatusoutput(command)
    end_time = time.time()
    log_lines = ["calling '{}' took {}, result (stat {:d}) is {} ({})".format(
        command,
        logging_tools.get_diff_time_str(end_time - start_time),
        stat,
        logging_tools.get_plural("byte", len(out)),
        logging_tools.get_plural("line", len(out.split("\n"))))]
    if log_com:
        for log_line in log_lines:
            log_com(" - {}".format(log_line))
        if stat:
            for log_line in out.split("\n"):
                log_com(" - {}".format(log_line))
        return stat, out
    else:
        if stat:
            # append output to log_lines if error
            log_lines.extend([" - {}".format(line) for line in out.split("\n")])
        return stat, out, log_lines


class accounting_process(threading_tools.process_obj):
    def process_init(self):
        self.__log_template = logging_tools.get_logger(
            global_config["LOG_NAME"],
            global_config["LOG_DESTINATION"],
            zmq=True,
            context=self.zmq_context,
            init_logger=True
        )
        connection.close()
        self._init_environ()
        # job stop/start info
        self.register_func("job_ss_info", self._job_ss_info)
        self.register_timer(self._check_accounting, 600)
        # full scan done ?
        self.__full_scan_done = False
        # caching
        self._disable_cache()
        # self.register_func("get_job_xml", self._get_job_xml)

    def process_running(self):
        # initial accounting run
        self._check_accounting()
        # check the last week
        _stime = datetime.datetime.now() - datetime.timedelta(days=7)
        self._check_accounting({"start_time": _stime.strftime("%Y%m%d%H%M")})

    def _init_environ(self):
        os.environ["SGE_ROOT"] = global_config["SGE_ROOT"]
        os.environ["SGE_CELL"] = global_config["SGE_CELL"]

    def _get_sge_bin(self, name):
        return os.path.join(global_config["SGE_ROOT"], "bin", global_config["SGE_ARCH"], name)

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)

    def loop_post(self):
        self.__log_template.close()

    def _disable_cache(self, log=False):
        self.log("disabling cache")
        self.__use_cache, self.__cache = (False, {})
        if log:
            self.__ac_e_time = time.time()
            self.log(
                "scanned {} in {} ({:.2f} / second)".format(
                    logging_tools.get_plural("entry", self.__entries_scanned),
                    logging_tools.get_diff_time_str(self.__ac_e_time - self.__ac_s_time),
                    self.__entries_scanned / max(self.__ac_e_time - self.__ac_s_time, 0.0001),
                )
            )
            self._log_missing(self._get_missing_dict())

    def _enable_cache(self):
        self.log("enabling cache")
        self.__ac_s_time = time.time()
        self.__use_cache, self.__cache = (
            True,
            {
                "device": {},
            }
        )
        self.__cache.update({key: {} for key in _OBJ_DICT.iterkeys()})

    def _get_missing_dict(self):
        _missing_ids = rms_job_run.objects.filter(Q(qacct_called=False)).values_list("rms_job__jobid", "rms_job__jobid", "rms_job__taskid")
        _mis_dict = {}
        for _entry in _missing_ids:
            _id = "{:d}".format(_entry[1])
            if _entry[2]:
                _id = "{}.{:d}".format(
                    _id,
                    _entry[2],
                )
            _mis_dict.setdefault(_id, []).append(_entry[0])
        return _mis_dict

    def _log_missing(self, _mis_dict):
        if _mis_dict:
            self.log(
                "entries missing in accounting database: {:d} ({})".format(
                    sum(len(_val) for _val in _mis_dict.itervalues()),
                    logging_tools.get_plural("job", len(_mis_dict)),
                ),
                logging_tools.LOG_LEVEL_WARN
            )
            self.log(
                ", ".join(
                    [
                        "{}{}".format(_key, " ({:d})".format(len(_mis_dict[_key])) if len(_mis_dict[_key]) > 1 else "") for _key in sorted(_mis_dict.keys())
                    ]
                )
            )
        else:
            self.log("all jobs accounted")

    def _check_accounting(self, *args, **kwargs):
        # init stats
        self.__jobs_added, self.__entries_scanned, self.__highest_id = (
            0,
            0,
            0,
        )
        self.__jobs_scanned = set()
        if args:
            _data = args[0]
            if "job_id" in _data:
                self._call_qacct("-j", "{:d}".format(_data["job_id"]))
            elif "start_time" in _data:
                self._call_qacct("-b", _data["start_time"], "-j")
            else:
                self.log(
                    "cannot parse args / kwargs: {}, {}".format(str(args), str(kwargs)),
                    logging_tools.LOG_LEVEL_ERROR,
                )
        else:
            # get jobs without valid accounting info
            _jobs = rms_job_run.objects.all().count()
            _mis_dict = self._get_missing_dict()
            # _missing_ids = rms_job_run.objects.filter(Q(qacct_called=False)).values_list("rms_job__jobid", flat=True)
            if not _jobs:
                self.__full_scan_done = True
                self.log("no jobs in database, checking accounting info", logging_tools.LOG_LEVEL_WARN)
                self._enable_cache()
                self._call_qacct("-j")
                self._disable_cache(log=True)
            elif global_config["FORCE_SCAN"] and not self.__full_scan_done:
                self.__full_scan_done = True
                self.log("full scan forced, checking accounting info", logging_tools.LOG_LEVEL_WARN)
                self._enable_cache()
                self._call_qacct("-j")
                self._disable_cache(log=True)
            elif len(_mis_dict) > 1000:
                self._log_missing(_mis_dict)
                self._enable_cache()
                self._call_qacct("-j")
                self._disable_cache(log=True)
            else:
                self._log_missing(_mis_dict)
                for _id in sorted(_mis_dict.iterkeys()):
                    self._call_qacct("-j", "{}".format(_id))
                self._log_stats()
        if self.__jobs_added:
            self.log("added {}".format(logging_tools.get_plural("job", self.__jobs_added)))

    def _call_qacct(self, *args):
        cur_stat, cur_out = call_command(
            "{} {}".format(
                self._get_sge_bin("qacct"),
                " ".join(args) if args else "",
            ),
            log_com=self.log,
        )
        if not cur_stat:
            self._interpret_qacct(cur_out)

    def _log_stats(self):
        self.log(
            "scanned {:d} entries ({:d} jobs, up to jobnumber {:d})".format(
                self.__entries_scanned,
                len(self.__jobs_scanned),
                self.__highest_id,
            )
        )

    def _interpret_qacct(self, cur_out):
        _dict = {}
        for _line in cur_out.split("\n"):
            if _line.startswith("==="):
                if "jobnumber" in _dict:
                    self._feed_qacct(_dict)
                _dict = {}
            else:
                if _line.strip():
                    _parts = _line.strip().split(None, 1)
                    if len(_parts) > 1:
                        # simple cleanup
                        _key, _value = _parts
                        if _value.isdigit():
                            _value = int(_value)
                        elif _value in ["NONE", "undefined", "-/-"]:
                            _value = None
                        elif _key.endswith("time") and len(_value.split()) > 4:
                            _value = cluster_timezone.localize(datetime.datetime.strptime(_value, "%a %b %d %H:%M:%S %Y"))
                        _dict[_key] = _value
        if "jobnumber" in _dict:
            self._feed_qacct(_dict)

    def _feed_qacct(self, in_dict):
        if not in_dict["start_time"] or not in_dict["end_time"]:
            # start or end time not set, forget it (crippled entry)
            return
        _job_id = "{:d}{}".format(
            in_dict["jobnumber"],
            ".{:d}".format(in_dict["taskid"]) if in_dict["taskid"] else "",
        )
        self.__entries_scanned += 1
        self.__jobs_scanned.add(_job_id)
        self.__highest_id = max(self.__highest_id, in_dict["jobnumber"])
        if not self.__entries_scanned % 100:
            self._log_stats()

        try:
            _cur_job_run = rms_job_run.objects.get(Q(rms_job__jobid=in_dict["jobnumber"]) & Q(rms_job__taskid=in_dict["taskid"]))
        except rms_job_run.DoesNotExist:
            _cur_job_run = self._add_job_from_qacct(_job_id, in_dict)
        except rms_job_run.MultipleObjectsReturned:
            _job_runs = rms_job_run.objects.filter(Q(rms_job__jobid=in_dict["jobnumber"]) & Q(rms_job__taskid=in_dict["taskid"]))
            # find matching objects
            _match = [
                _cur_job_run for _cur_job_run in _job_runs if _cur_job_run.start_time == in_dict["start_time"] and _cur_job_run.end_time == in_dict["end_time"]
            ]
            if len(_match):
                # entry found with same start / end time, no need to update
                if len(_match) > 1:
                    self.log(
                        "found more than one matching job_run ({:d}) for job {}, please check code".format(
                            len(_match),
                            _job_id,
                        ),
                        logging_tools.LOG_LEVEL_OK
                    )
                _cur_job_run = _match[0]
                # print "*", len(_match), _cur_job_run.qacct_called, _job_id, len(_job_runs)
                # if _job_id == "8129":
                #    for _e in _job_runs:
                #        print _e.start_time, _e.end_time
            else:
                # create new run
                _cur_job_run = self._add_job_from_qacct(_job_id, in_dict)

        if _cur_job_run is not None:
            if _cur_job_run.qacct_called:
                if _cur_job_run.start_time and _cur_job_run.end_time:
                    if _cur_job_run.start_time == in_dict["start_time"] and \
                            _cur_job_run.end_time == in_dict["end_time"]:
                        # pure duplicate
                        _cur_job_run = None
                    else:
                        self.log("duplicate with different start/end time found for job {}, creating new run".format(_job_id), logging_tools.LOG_LEVEL_WARN)
                        _cur_job_run = self._add_job_from_qacct(_job_id, in_dict)
            if _cur_job_run is not None:
                # resolve dict
                for key, obj_name in [
                    ("department", "rms_department"),
                    ("project", "rms_project"),
                    ("qname", "rms_queue"),
                ]:
                    if in_dict[key]:
                        in_dict[key] = self._get_object(obj_name, in_dict[key])
                _cur_job_run.feed_qacct_data(in_dict)

    def _add_job_from_qacct(self, _job_id, in_dict):
        self.__jobs_added += 1
        if not self.__jobs_added % 100:
            self.log("added {:d} jobs".format(self.__jobs_added))
        _job = self._get_job(
            in_dict["jobnumber"],
            in_dict["taskid"],
            owner=in_dict["owner"],
            name=in_dict["jobname"],
        )
        _source_host = in_dict["hostname"]
        _source_dev = self._get_device(_source_host)
        _cur_job_run = _job.add_job_run(_source_host, _source_dev)
        _cur_job_run.rms_queue = self._get_object("rms_queue", in_dict["qname"])
        if in_dict["granted_pe"]:
            _cur_job_run.granted_pe = in_dict["granted_pe"]
            _cur_job_run.rms_pe = self._get_object("rms_pe", in_dict["granted_pe"])
        # set slots to the default value
        _cur_job_run.slots = in_dict["slots"]
        _cur_job_run.save()
        if not self.__use_cache:
            self.log("added new {}".format(unicode(_cur_job_run)))
        return _cur_job_run

    def _get_object(self, obj_name, name):
        if self.__use_cache and name in self.__cache[obj_name]:
            cur_obj = self.__cache[obj_name][name]
        else:
            _obj = _OBJ_DICT[obj_name]
            # FIXME, add caching
            try:
                cur_obj = _obj.objects.get(Q(name=name))
            except _obj.DoesNotExist:
                self.log("creating new {} with name {}".format(obj_name, name))
                cur_obj = _obj.objects.create(
                    name=name
                )
            if self.__use_cache:
                self.__cache[obj_name][name] = cur_obj
        return cur_obj

    def _get_job(self, job_id, task_id, **kwargs):
        task_id = task_id or None
        try:
            cur_job = rms_job.objects.get(Q(jobid=job_id) & Q(taskid=task_id))
        except rms_job.DoesNotExist:
            self.log(
                "creating new job with id {}{}".format(
                    job_id,
                    " (task id {})".format(str(task_id)) if task_id else "",
                )
            )
            cur_job = rms_job.objects.create(
                jobid=job_id,
                taskid=task_id,
                name=kwargs["name"],
                owner=kwargs["owner"],
            )
        if not cur_job.user_id and "owner" in kwargs:
            try:
                _user = user.objects.get(Q(login=kwargs["owner"]))  # @UndefinedVariable
            except user.DoesNotExist:  # @UndefinedVariable
                self.log(
                    "no user with name {} found, check aliases ?".format(kwargs["owner"]),
                    logging_tools.LOG_LEVEL_ERROR,
                )
            else:
                if not self.__use_cache:
                    self.log("set user of job {} to {}".format(unicode(cur_job), unicode(_user)))
                cur_job.user = _user
                cur_job.save()
        return cur_job

    def _get_device(self, dev_str):
        if self.__use_cache and dev_str in self.__cache["device"]:
            _dev = self.__cache["device"][dev_str]
        else:
            if not dev_str.count("."):
                # short name
                try:
                    _dev = device.objects.get(Q(name=dev_str))
                except device.DoesNotExist:
                    self.log("no device with short name '{}' found".format(dev_str), logging_tools.LOG_LEVEL_ERROR)
                    _dev = None
            else:
                _short, _domain = dev_str.split(".", 1)
                try:
                    _dev = device.objects.get(Q(name=_short) & Q(domain_tree_node__full_name=_domain))
                except device.DoesNotExist:
                    self.log("no device with FQDN '{}' found".format(dev_str), logging_tools.LOG_LEVEL_ERROR)
                    _dev = None
            if self.__use_cache:
                self.__cache["device"][dev_str] = _dev
        return _dev

    def _job_ss_info(self, *args, **kwargs):
        _com, _id, _sc_text = args
        srv_com = server_command.srv_command(source=_sc_text)
        _config = srv_com["config"]
        self.log(
            "got {} (job_id {}, {} in config)".format(
                _com,
                _id,
                logging_tools.get_plural("key", len(_config))
            )
        )
        # print srv_com.pretty_print()
        # print srv_com["config"]
        _source_host = srv_com["source"].attrib["host"]
        _source_dev = self._get_device(_source_host)
        self.log(
            "source device {} resolves to {}".format(
                _source_host,
                unicode(_source_dev) if _source_dev else "---",
            )
        )
        if _com in ["job_start", "job_end"]:
            _queue = self._get_object("rms_queue", _config["job_queue"])
            _job = self._get_job(
                int(_config["job_id"]),
                _config.get("task_id", 0),
                owner=_config["job_owner"],
                name=_config["job_name"],
            )
            if _com == "job_start":
                _new_run = _job.add_job_run(_source_host, _source_dev)
                _new_run.rms_queue = _queue
                # set slots to the default value
                _new_run.slots = 1
                _new_run.save()
                self.log("added new {}".format(unicode(_new_run)))
            else:
                # after 1 minute check the accounting log
                self.register_timer(self._check_accounting, 60, oneshot=True, data={"job_id": _job.jobid, "task_id": _job.taskid})
                _latest_run = _job.close_job_run()
                if _latest_run:
                    self.log("closed job_run {}".format(unicode(_latest_run)))
        else:
            _pe = self._get_object("rms_pe", _config["pe"])
            _job = self._get_job(
                int(_config["job_id"]),
                _config.get("task_id", 0),
                owner=_config["job_owner"],
                name=_config["job_name"],
            )
            _latest_run = _job.get_latest_job_run()
            if _com == "pe_start" and _latest_run:
                _latest_run.slots = int(_config["pe_slots"])
                _latest_run.rms_pe = _pe
                _latest_run.granted_pe = _config["pe"]
                _latest_run.save(update_fields=["rms_pe", "granted_pe", "slots"])
                if "pe_hostfile_content" in _config:
                    _lines = [_entry.strip() for _entry in _config["pe_hostfile_content"].split("\n") if _entry.strip()]
                    for _line in _lines:
                        _parts = _line.split()
                        _pe_dev = self._get_device(_parts[0])
                        _slots = int(_parts[1])
                        self.log(
                            "pe info parsed for {}: device '{}' (from {}), {}".format(
                                unicode(_latest_run),
                                unicode(_pe_dev) if _pe_dev else "---",
                                _parts[0],
                                logging_tools.get_plural("slot", _slots),
                            )
                        )
                        rms_pe_info.objects.create(
                            rms_job_run=_latest_run,
                            device=_pe_dev,
                            hostname=_parts[0],
                            slots=_slots,
                        )
