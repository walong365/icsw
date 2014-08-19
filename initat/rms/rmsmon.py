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

""" rms-server, monitoring process """

from django.core.cache import cache
from django.db.models import Q
from initat.cluster.backbone.models import rms_job, rms_job_run, rms_pe_info, \
    rms_project, rms_department, rms_pe, rms_queue, user, device, cluster_timezone
from initat.host_monitoring import hm_classes
from initat.rms.config import global_config
from lxml import etree  # @UnresolvedImport @UnusedImport
from lxml.builder import E  # @UnresolvedImport
import commands
import datetime
import logging_tools
import os
import pprint
import process_tools
import server_command
import sge_tools
import threading_tools
import time
import uuid
import zmq

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


class queue_info(object):
    def __init__(self):
        self.used = 0
        self.total = 0
        self.reserved = 0
        self.alarm = 0
        self.unknown = 0
        self.error = 0
        self.disabled = 0
        self.count = 0

    def feed(self, _t, _r, _u, _state):
        self.total += _t
        self.reserved += _r
        self.used += _u
        self.count += 1
        # count states
        for _short, _attr in [("E", "error"), ("d", "disabled"), ("u", "unknown"), ("a", "alarm")]:
            if _short in _state:
                setattr(self, _attr, getattr(self, _attr) + 1)


class rms_mon_process(threading_tools.process_obj):
    def process_init(self):
        self.__log_template = logging_tools.get_logger(
            global_config["LOG_NAME"],
            global_config["LOG_DESTINATION"],
            zmq=True,
            context=self.zmq_context,
            init_logger=True
        )
        self.__node_options = sge_tools.get_empty_node_options()
        self._init_network()
        self._init_sge_info()
        self.__job_content_dict = {}
        self.register_func("get_config", self._get_config)
        self.register_func("job_control", self._job_control)
        self.register_func("queue_control", self._queue_control)
        self.register_func("file_watch_content", self._file_watch_content)
        self.register_func("full_reload", self._full_reload)
        # job stop/start info
        self.register_func("job_ss_info", self._job_ss_info)
        self.register_timer(self._update, 30)
        self.register_timer(self._check_accounting, 3600)
        # full scan done ?
        self.__full_scan_done = False
        # caching
        self._disable_cache()
        self._check_accounting()
        # self.register_func("get_job_xml", self._get_job_xml)

    def _init_sge_info(self):
        self.log("init sge_info")
        self.__sge_info = sge_tools.sge_info(
            log_command=self.log,
            run_initial_update=False,
            verbose=True if global_config["DEBUG"] else False,
            is_active=True,
            always_direct=True,
            sge_dict=dict([(key, global_config[key]) for key in ["SGE_ARCH", "SGE_ROOT", "SGE_CELL"]]))
        self._update()
        # set environment
        os.environ["SGE_ROOT"] = global_config["SGE_ROOT"]
        os.environ["SGE_CELL"] = global_config["SGE_CELL"]

    def _init_network(self):
        conn_str = process_tools.get_zmq_ipc_name("vector", s_name="collserver", connect_to_root_instance=True)
        vector_socket = self.zmq_context.socket(zmq.PUSH)
        vector_socket.setsockopt(zmq.LINGER, 0)
        vector_socket.connect(conn_str)
        self.vector_socket = vector_socket

    def _update(self):
        self.__sge_info.update(no_file_cache=True, force_update=True)
        self.__sge_info.build_luts()
        _res = sge_tools.build_node_list(self.__sge_info, self.__node_options)
        self._generate_slotinfo(_res)

    def _generate_slotinfo(self, _res):
        _queue_names = set()
        _host_names = set()
        act_time = time.time()
        # queue dict
        _queues = {"total": queue_info()}
        for _node in _res.findall(".//node"):
            _host = _node.findtext("host")
            _queue = _node.findtext("queue")
            _queue_names.add(_queue)
            _host_names.add(_queue)
            _su, _sr, _st = (
                int(_node.findtext("slots_used")),
                int(_node.findtext("slots_reserved")),
                int(_node.findtext("slots_total")),
            )
            _state = _node.findtext("state")
            _queues["total"].feed(_st, _sr, _su, _state)
            if _queue not in _queues:
                _queues[_queue] = queue_info()
            _queues[_queue].feed(_st, _sr, _su, _state)
        # print _res
        drop_com = server_command.srv_command(command="set_vector")
        _bldr = drop_com.builder()
        _rms_vector = _bldr("values")
        # 10 minutes valid
        valid_until = act_time + 10 * 60
        _rms_vector.append(
            hm_classes.mvect_entry(
                "rms.clusterqueues.total",
                info="ClusterQueues defined",
                default=0,
                value=len(_queue_names),
                factor=1,
                valid_until=valid_until,
                base=1000,
            ).build_xml(_bldr)
        )
        _rms_vector.append(
            hm_classes.mvect_entry(
                "rms.hosts.total",
                info="Hosts defined",
                default=0,
                value=len(_host_names),
                factor=1,
                valid_until=valid_until,
                base=1000,
            ).build_xml(_bldr)
        )
        for q_name, q_value in _queues.iteritems():
            # sanitize queue name
            q_name = q_name.replace(".", "_")
            for _key, _value, _info in [
                ("total", q_value.total, "slots defined"),
                ("reserved", q_value.reserved, "slots reserved"),
                ("used", q_value.used, "slots used"),
                ("free", q_value.total - q_value.used, "slots free"),
                ("error", q_value.error, "instances in error state"),
                ("disabled", q_value.disabled, "instances in disabled state"),
                ("alarm", q_value.alarm, "instances in alarm state"),
                ("unknown", q_value.unknown, "instances in error state"),
                ("count", q_value.count, "instances"),
            ]:
                _rms_vector.append(
                    hm_classes.mvect_entry(
                        "rms.queues.{}.{}".format(q_name, _key),
                        info="{} in queue {}".format(_info, q_name),
                        default=0,
                        value=_value,
                        factor=1,
                        valid_until=valid_until,
                        base=1000,
                    ).build_xml(_bldr)
                )
        drop_com["vector_rms"] = _rms_vector
        drop_com["vector_rms"].attrib["type"] = "vector"
        # for cap_name in self.__cap_list:
        #    self.__server_cap_dict[cap_name](cur_time, drop_com)
        self.vector_socket.send_unicode(unicode(drop_com))

    def _full_reload(self, *args, **kwargs):
        self.log("doing a full_reload")
        self._update()

    def _get_config(self, *args, **kwargs):
        src_id, srv_com_str = args
        srv_com = server_command.srv_command(source=srv_com_str)
        if "needed_dicts" in srv_com:
            needed_dicts = srv_com["*needed_dicts"]
        else:
            needed_dicts = None
        self.log("get_config, needed_dicts is {}".format(", ".join(needed_dicts) if needed_dicts else "all"))
        # needed_dicts = opt_dict.get("needed_dicts", ["hostgroup", "queueconf", "qhost", "complexes"])
        # update_list = opt_dict.get("update_list", [])
        self.__sge_info.update(update_list=needed_dicts)
        srv_com["sge"] = self.__sge_info.get_tree(file_dict=self.__job_content_dict)
        self.send_pool_message("command_result", src_id, unicode(srv_com))
        del srv_com

    def _get_sge_bin(self, name):
        return os.path.join(global_config["SGE_ROOT"], "bin", global_config["SGE_ARCH"], name)

    def _job_control(self, *args, **kwargs):
        src_id, srv_com_str = args
        srv_com = server_command.srv_command(source=srv_com_str)
        job_action = srv_com["action"].text
        job_id = srv_com.xpath(".//ns:job_list/ns:job/@job_id", smart_strings=False)[0]
        self.log("job action '{}' for job '{}'".format(job_action, job_id))
        if job_action in ["force_delete", "delete"]:
            cur_stat, cur_out = call_command(
                "{} {} {}".format(
                    self._get_sge_bin("qdel"),
                    "-f" if job_action == "force_delete" else "",
                    job_id
                ),
                log_com=self.log
            )
            srv_com.set_result(
                "{} gave: {}".format(job_action, cur_out),
                server_command.SRV_REPLY_STATE_ERROR if cur_stat else server_command.SRV_REPLY_STATE_OK
            )
        else:
            srv_com.set_result(
                "unknown job_action %s" % (job_action),
                server_command.SRV_REPLY_STATE_ERROR,
            )
        self.send_pool_message("command_result", src_id, unicode(srv_com))

    def _queue_control(self, *args, **kwargs):
        src_id, srv_com_str = args
        srv_com = server_command.srv_command(source=srv_com_str)
        queue_action = srv_com["action"].text
        queue_spec = srv_com.xpath(".//ns:queue_list/ns:queue/@queue_spec", smart_strings=False)[0]
        self.log("queue action '%s' for job '%s'" % (queue_action, queue_spec))
        if queue_action in ["enable", "disable", "clear_error"]:
            cur_stat, cur_out = call_command(
                "{} {} {}".format(
                    self._get_sge_bin("qmod"),
                    {
                        "enable": "-e",
                        "disable": "-d",
                        "clear_error": "-c",
                    }[queue_action],
                    queue_spec,
                ),
                log_com=self.log,
            )
            srv_com.set_result(
                "{} gave: {}".format(queue_action, cur_out),
                server_command.SRV_REPLY_STATE_ERROR if cur_stat else server_command.SRV_REPLY_STATE_OK
            )
        else:
            srv_com.set_result(
                "unknown job_action %s" % (queue_action),
                server_command.SRV_REPLY_STATE_ERROR,
            )
        self.send_pool_message("command_result", src_id, unicode(srv_com))

    def _file_watch_content(self, *args, **kwargs):
        _src_id, srv_src = args
        srv_com = server_command.srv_command(source=srv_src)
        job_id = srv_com["send_id"].text.split(":")[0]
        file_name = srv_com["name"].text
        content = srv_com["content"].text
        last_update = int(float(srv_com["update"].text))
        self.log("got content for '{}' (job {}), len {:d} bytes, update_ts {:d}".format(
            file_name,
            job_id,
            len(content),
            last_update,
            ))
        if len(job_id) and job_id[0].isdigit():
            # job_id is ok
            try:
                if file_name not in self.__job_content_dict.get(job_id, {}):
                    self.__job_content_dict.setdefault(job_id, {})[file_name] = E.file_content(
                        name=file_name,
                        last_update="{:d}".format(int(last_update)),
                        cache_uuid="rms_fc_{}".format(uuid.uuid4()),
                        size="{:d}".format(len(content)),
                    )
                    # already present, replace file
                _cur_struct = self.__job_content_dict[job_id][file_name]
                # timeout: 5 hours
                cache.set(_cur_struct.attrib["cache_uuid"], content, 5 * 3600)
            except:
                self.log(
                    "error settings content of file {}: {}".format(
                        file_name,
                        process_tools.get_except_info()
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
            else:
                tot_files = sum([len(value) for value in self.__job_content_dict.itervalues()], 0)
                tot_length = sum(
                    [
                        sum([int(cur_el.attrib["size"]) for _name, cur_el in _dict.iteritems()], 0)
                        for job_id, _dict in self.__job_content_dict.iteritems()
                    ]
                )
                self.log("cached: {:d} files, {} ({:d} bytes)".format(tot_files, logging_tools.get_size_str(tot_length), tot_length))
        else:
            self.log("job_id {} is suspicious, ignoring".format(job_id), logging_tools.LOG_LEVEL_WARN)

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)

    def loop_post(self):
        self.vector_socket.close()
        self.__log_template.close()

    def _disable_cache(self):
        self.log("disabling cache")
        self.__use_cache, self.__cache = (False, {})

    def _enable_cache(self):
        self.log("enabling cache")
        self.__use_cache, self.__cache = (
            True,
            {
                "device": {},
            }
        )
        self.__cache.update({key: {} for key in _OBJ_DICT.iterkeys()})

    def _check_accounting(self, *args, **kwargs):
        self.__jobs_added = 0
        self.__jobs_scanned = 0
        if args:
            _data = args[0]
            self._call_qacct("-j", "{:d}".format(_data["job_id"]))
        else:
            # get jobs without valid accounting info
            _jobs = rms_job_run.objects.all().count()
            _missing_ids = rms_job_run.objects.filter(Q(qacct_called=False)).values_list("rms_job__jobid", flat=True)
            if not _jobs:
                self.__full_scan_done = True
                self.log("no jobs in database, checking accounting info", logging_tools.LOG_LEVEL_WARN)
                self._enable_cache()
                self._call_qacct("-j")
                self._disable_cache()
            elif global_config["FORCE_SCAN"] and not self.__full_scan_done:
                self.__full_scan_done = True
                self.log("full scan forced, checking accounting info", logging_tools.LOG_LEVEL_WARN)
                self._enable_cache()
                self._call_qacct("-j")
                self._disable_cache()
            elif len(_missing_ids) > 10:
                self.log("accounting info for {:d} jobs missing, doing a full call".format(len(_missing_ids)), logging_tools.LOG_LEVEL_WARN)
                self._call_qacct("-j")
            else:
                self.log(
                    "accounting info missing for {}: {}".format(
                        logging_tools.get_plural("job", len(_missing_ids)),
                        ", ".join(["{:d}".format(_id) for _id in _missing_ids])
                    ),
                    logging_tools.LOG_LEVEL_WARN
                )
                for _id in _missing_ids:
                    self._call_qacct("-j", "{:d}".format(_id))
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
        _job_id = "{:d}{}".format(
            in_dict["jobnumber"],
            ".{:d}".format(in_dict["taskid"]) if in_dict["taskid"] else "",
        )
        try:
            _cur_job_run = rms_job_run.objects.get(Q(rms_job__jobid=in_dict["jobnumber"]) & Q(rms_job__taskid=in_dict["taskid"]))
        except rms_job_run.DoesNotExist:
            _cur_job_run = self._add_job_from_qacct(_job_id, in_dict)
        except rms_job_run.MultipleObjectsReturned:
            _job_runs = rms_job_run.objects.filter(Q(rms_job__jobid=in_dict["jobnumber"]) & Q(rms_job__taskid=in_dict["taskid"]))
            if in_dict["start_time"] and in_dict["end_time"]:
                # find matching objects
                if any([_cur_job_run.start_time == in_dict["start_time"] and _cur_job_run.end_time == in_dict["end_time"] for _cur_job_run in _job_runs]):
                    # entry found with same start / end time, no need to update
                    _cur_job_run = None
                else:
                    # create new run
                    _cur_job_run = self._add_job_from_qacct(_job_id, in_dict)
            else:
                # start or end time not set, forget it
                _cur_job_run = None
        else:
            self.__jobs_scanned += 1
            if not self.__jobs_scanned % 100:
                self.log("scanned {:d} jobs".format(self.__jobs_scanned))

        if _cur_job_run is not None:
            if _cur_job_run.qacct_called:
                if _cur_job_run.start_time and _cur_job_run.end_time:
                    if _cur_job_run.start_time == in_dict["start_time"] and \
                            _cur_job_run.end_time == in_dict["end_time"]:
                        # pure duplicate
                        self.log("duplicate with identical start/end time found for job {}".format(_job_id), logging_tools.LOG_LEVEL_WARN)
                    else:
                        self.log("duplicate with different start/end time found for job {}, creating new run".format(_job_id), logging_tools.LOG_LEVEL_WARN)
                        _cur_job_run = self._add_job_from_qacct(_job_id, in_dict)
            else:
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
                "creating new job with id {} ({})".format(
                    job_id,
                    "task id {}".format(str(task_id)) if task_id else "no task id",
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
                _user = user.objects.get(Q(login=kwargs["owner"]))
            except user.DoesNotExist:
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
                self.register_timer(self._check_accounting, 10, oneshot=True, data={"job_id": _job.jobid, "task_id": _job.taskid})
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
