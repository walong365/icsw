# Copyright (C) 2001-2016 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of rms-tools
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

""" rms-server, monitoring process """

from __future__ import print_function, unicode_literals

import os
import re
import time
import uuid

import zmq
from django.core.cache import cache
from django.db.models import Q
from lxml import etree
from lxml.builder import E

from initat.cluster.backbone import db_tools
from initat.cluster.backbone.models import device, rms_user, rms_accounting_record, \
    rms_accounting_run, RMSAggregationLevelEnum
from initat.host_monitoring import hm_classes
from initat.tools import logging_tools, process_tools, server_command, \
    sge_tools, threading_tools
from .config import global_config
from .functions import call_command


class QueueInfo(object):
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
                setattr(self, _attr, getattr(self, _attr) + self.total)

    @property
    def free(self):
        return self.total - self.used

    def __repr__(self):
        return unicode(self)

    def __unicode__(self):
        return "{:d} used, {:d} total, {:d} reserved".format(
            self.used,
            self.total,
            self.reserved,
        )


class RMSMonProcess(threading_tools.process_obj):
    def process_init(self):
        global_config.close()
        self.__log_template = logging_tools.get_logger(
            global_config["LOG_NAME"],
            global_config["LOG_DESTINATION"],
            zmq=True,
            context=self.zmq_context,
            init_logger=True
        )
        db_tools.close_connection()
        self._init_cache()
        self.__node_options = sge_tools.get_empty_node_options()
        self.__run_options = sge_tools.get_empty_job_options(
            suppress_times=True,
            suppress_nodelist=True,
            show_stdoutstderr=False,
        )
        self._init_network()
        self._init_sge_info()
        # job content dict
        self.__job_content_dict = {}
        # pinning dict
        self.__job_pinning_dict = {}
        self.register_func("get_config", self._get_config)
        self.register_func("job_control", self._job_control)
        self.register_func("queue_control", self._queue_control)
        self.register_func("file_watch_content", self._file_watch_content)
        self.register_func("affinity_info", self._affinity_info)
        self.register_func("job_ended", self._job_ended)
        self.register_func("full_reload", self._full_reload)
        # job stop/start info
        self.register_timer(self._update_nodes, 30)
        if global_config["TRACE_FAIRSHARE"]:
            self.log("register fairshare tracer")
            self.register_timer(self._update_fairshare, 60, instant=True)

    def _init_cache(self):
        self.__cache = {
            "device": {}
        }

    def _init_sge_info(self):
        self.log("init sge_info")
        self.__sge_info = sge_tools.SGEInfo(
            log_command=self.log,
            run_initial_update=False,
            verbose=True if global_config["DEBUG"] else False,
            is_active=True,
            source="local",
            sge_dict=dict([(key, global_config[key]) for key in ["SGE_ARCH", "SGE_ROOT", "SGE_CELL"]])
        )
        self._update()
        # set environment
        os.environ["SGE_ROOT"] = global_config["SGE_ROOT"]
        os.environ["SGE_CELL"] = global_config["SGE_CELL"]

    def _init_network(self):
        _v_conn_str = process_tools.get_zmq_ipc_name("vector", s_name="collserver", connect_to_root_instance=True)
        vector_socket = self.zmq_context.socket(zmq.PUSH)
        vector_socket.setsockopt(zmq.LINGER, 0)
        vector_socket.connect(_v_conn_str)
        self.vector_socket = vector_socket
        _c_conn_str = "tcp://localhost:8002"
        collectd_socket = self.zmq_context.socket(zmq.PUSH)
        collectd_socket.setsockopt(zmq.LINGER, 0)
        collectd_socket.setsockopt(zmq.IMMEDIATE, 1)
        collectd_socket.connect(_c_conn_str)
        self.collectd_socket = collectd_socket

    def _update(self):
        self.__sge_info.update(no_file_cache=True, force_update=True)
        self.__sge_info.build_luts()

    def _update_nodes(self):
        s_time = time.time()
        self._update()
        _node_res = sge_tools.build_node_list(self.__sge_info, self.__node_options)
        _run_res = sge_tools.build_running_list(self.__sge_info, self.__run_options)
        self.generate_slotinfo(_node_res, _run_res)
        # rms_accounting_run.objects.exclude(Q(aggregation_level=RMSAggregationLevelEnum.none.value.short)).delete()
        self.aggregate_accounting()
        e_time = time.time()
        self.log("update() call took {}".format(logging_tools.get_diff_time_str(e_time - s_time)))

    def aggregate_accounting(self):
        # aggregate from (none) to (hour) to (day) to (week) to (month) to (year)
        for entry in RMSAggregationLevelEnum:
            entry.value.aggregate(self.log)

    def _get_device(self, dev_str):
        if dev_str in self.__cache["device"]:
            _dev = self.__cache["device"][dev_str]
        else:
            if not dev_str.count("."):
                # short name
                try:
                    _dev = device.objects.get(Q(name=dev_str))
                except device.DoesNotExist:
                    self.log("no device with short name '{}' found".format(dev_str), logging_tools.LOG_LEVEL_ERROR)
                    _dev = None
                except device.MultipleObjectsReturned:
                    self.log(
                        "got more than one result for short name '{}': {}".format(
                            dev_str,
                            process_tools.get_except_info()
                        ),
                        logging_tools.LOG_LEVEL_ERROR
                    )
                    _dev = None
            else:
                _short, _domain = dev_str.split(".", 1)
                try:
                    _dev = device.objects.get(Q(name=_short) & Q(domain_tree_node__full_name=_domain))
                except device.DoesNotExist:
                    self.log("no device with FQDN '{}' found".format(dev_str), logging_tools.LOG_LEVEL_ERROR)
                    _dev = None
                except device.MultipleObjectsReturned:
                    self.log(
                        "got more than one result for FQDN '{}': {}".format(
                            dev_str,
                            process_tools.get_except_info()
                        ),
                        logging_tools.LOG_LEVEL_ERROR
                    )
                    _dev = None
            self.__cache["device"][dev_str] = _dev
        return _dev

    def generate_slotinfo(self, node_res, run_res):
        act_time = int(time.time())
        # vector socket
        drop_com = server_command.srv_command(command="set_vector")
        _bldr = drop_com.builder()
        _rms_vector = _bldr("values")
        # 10 minutes valid
        valid_until = act_time + 10 * 60

        _queue_names = set()
        _host_names = set()
        _s_time = time.time()
        _host_stats = {}

        # print("*", _owner_dict)
        # print("*", _pe_text, _owner_text, _slots)
        # queue dict
        _queues = {"total": QueueInfo()}
        for _node in node_res.findall(".//node"):
            # print(etree.tostring(_node, pretty_print=True))
            _host = _node.findtext("host")
            _queue = _node.findtext("queue")
            _queue_names.add(_queue)
            _host_names.add(_host)
            _si = _node.findtext("slot_info")
            _su, _sr, _st = (int(_val) for _val in _si.split("/"))
            _state = _node.findtext("state")
            _queues["total"].feed(_st, _sr, _su, _state)
            if _queue not in _queues:
                _queues[_queue] = QueueInfo()
            _queues[_queue].feed(_st, _sr, _su, _state)
            if _host not in _host_stats:
                _host_stats[_host] = QueueInfo()
            _host_stats[_host].feed(_st, _sr, _su, _state)
        # print node_res
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
        report_list = [
            ("total", "slots defined"),
            ("reserved", "slots reserved"),
            ("used", "slots used"),
            ("free", "slots free"),
            ("error", "instances in error state"),
            ("disabled", "instances in disabled state"),
            ("alarm", "instances in alarm state"),
            ("unknown", "instances in error state"),
            ("count", "instances"),
        ]
        for q_name, q_value in _queues.iteritems():
            # sanitize queue name
            q_name = q_name.replace(".", "_")
            for _key, _info in report_list:
                _rms_vector.append(
                    hm_classes.mvect_entry(
                        "rms.queues.{}.{}".format(q_name, _key),
                        info="{} in queue {}".format(_info, q_name),
                        default=0,
                        value=getattr(q_value, _key),
                        factor=1,
                        valid_until=valid_until,
                        base=1000,
                    ).build_xml(_bldr)
                )

        # accounting records
        total_slots = _queues["total"].total
        # print(etree.tostring(run_res, pretty_print=True))
        _owner_dict = {
            _rms_user.name: {
                "obj": _rms_user,
                "slots": []
            } for _rms_user in rms_user.objects.all()
        }
        account_run = rms_accounting_run.objects.create(slots_defined=total_slots)

        # print(_owner_dict)
        # running slots info
        for _node in run_res.findall(".//job"):
            _pe_text = _node.findtext("granted_pe")
            _owner_text = _node.findtext("owner")
            if _pe_text == "-":
                _slots = 1
            else:
                _slots = int(_pe_text.split("(")[1].split(")")[0])
            if _owner_text not in _owner_dict:
                new_user = rms_user(
                    name=_owner_text,
                )
                new_user.save()
                _owner_dict[new_user.name] = {
                    "obj": new_user,
                    "slots": [],
                }
            _owner_dict[_owner_text]["slots"].append(_slots)
        _total = 0
        _records = []
        for _name, _struct in _owner_dict.iteritems():
            _slots = sum(_struct["slots"])
            _records.append(
                rms_accounting_record(
                    rms_accounting_run=account_run,
                    rms_user=_struct["obj"],
                    slots_used=_slots,
                )
            )
            _total += _slots
            _rms_vector.append(
                hm_classes.mvect_entry(
                    "rms.user.{}.slots".format(_name),
                    info="Slots used by user '{}'".format(_name),
                    default=0,
                    value=_slots,
                    factor=1,
                    valid_until=valid_until,
                    base=1,
                ).build_xml(_bldr)
            )
        # total vector
        _rms_vector.append(
            hm_classes.mvect_entry(
                "rms.user.slots".format(_name),
                info="Slots used by all users",
                default=0,
                value=_total,
                factor=1,
                valid_until=valid_until,
                base=1,
            ).build_xml(_bldr)
        )
        # create accounting records
        rms_accounting_record.objects.bulk_create(_records)
        drop_com["vector_rms"] = _rms_vector
        drop_com["vector_rms"].attrib["type"] = "vector"
        # for cap_name in self.__cap_list:
        #    self.__server_cap_dict[cap_name](cur_time, drop_com)
        self.vector_socket.send_unicode(unicode(drop_com))
        # collectd commands
        valid_hosts = {
            _host: _dev for _host, _dev in [
                (_host, self._get_device(_host)) for _host in _host_names
            ] if _dev is not None and _host in _host_stats
        }
        for _host_name, _dev in valid_hosts.iteritems():
            mach_vect = E.machine_vector(
                time="{:d}".format(act_time),
                simple="0",
                name=_dev.full_name,
                uuid=_dev.uuid,
            )
            q_value = _host_stats[_host_name]
            mach_vect.extend(
                [
                    hm_classes.mvect_entry(
                        "rms.slots.{}".format(_key),
                        info="{}".format(_info),
                        default=0,
                        value=getattr(q_value, _key),
                        factor=1,
                        valid_until=valid_until,
                        base=1000,
                    ).build_xml(E) for _key, _info in report_list
                ]
            )
            try:
                self.collectd_socket.send_unicode(etree.tostring(mach_vect), zmq.DONTWAIT)
            except:
                self.log(
                    "error sending rms-slot info regarding {} to collectd: {}".format(
                        _dev.full_name,
                        process_tools.get_except_info(),
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
        _e_time = time.time()
        self.log("info handling took {}".format(logging_tools.get_diff_time_str(_e_time - _s_time)))

    def _full_reload(self, *args, **kwargs):
        self.log("doing a full_reload")
        self._update()

    def _get_config(self, *args, **kwargs):
        srv_com = server_command.srv_command(source=args[0])
        if "needed_dicts" in srv_com:
            needed_dicts = srv_com["*needed_dicts"]
        else:
            needed_dicts = None
        self.log("get_config, needed_dicts is {}".format(", ".join(needed_dicts) if needed_dicts else "all"))
        # needed_dicts = opt_dict.get("needed_dicts", ["hostgroup", "queueconf", "qhost", "complexes"])
        # update_list = opt_dict.get("update_list", [])
        self.__sge_info.update(update_list=needed_dicts)
        srv_com["sge"] = self.__sge_info.get_tree(
            file_dict=self.__job_content_dict,
            pinning_dict=self.__job_pinning_dict,
        )
        self.send_pool_message("remote_call_async_result", unicode(srv_com))
        del srv_com

    def _get_sge_bin(self, name):
        return os.path.join(global_config["SGE_ROOT"], "bin", global_config["SGE_ARCH"], name)

    def _job_control(self, *args, **kwargs):
        srv_com = server_command.srv_command(source=args[0])
        job_action = srv_com["action"].text
        job_id = srv_com.xpath(".//ns:job_list/ns:job/@job_id", smart_strings=False)[0]
        self.log("job action '{}' for job '{}'".format(job_action, job_id))
        if job_action in ["force_delete", "delete"]:
            cur_stat, cur_out = call_command(
                "{} {} {}".format(
                    self._get_sge_bin("qdel"),
                    "-f" if job_action == "force_delete" else "",
                    job_id,
                ),
                log_com=self.log
            )
            srv_com.set_result(
                "{} gave: {}".format(job_action, cur_out),
                server_command.SRV_REPLY_STATE_ERROR if cur_stat else server_command.SRV_REPLY_STATE_OK
            )
        elif job_action in ["modify_priority"]:
            targ_pri = int(srv_com.xpath(".//ns:job_list/ns:job/@priority", smart_strings=False)[0])
            cur_stat, cur_out = call_command(
                "{} -p {:d} {}".format(
                    self._get_sge_bin("qalter"),
                    targ_pri,
                    job_id,
                ),
                log_com=self.log
            )
            srv_com.set_result(
                "{} gave: {}".format(job_action, cur_out),
                server_command.SRV_REPLY_STATE_ERROR if cur_stat else server_command.SRV_REPLY_STATE_OK
            )
        else:
            srv_com.set_result(
                "unknown job_action {}".format(job_action),
                server_command.SRV_REPLY_STATE_ERROR,
            )
        self.send_pool_message("remote_call_async_result", unicode(srv_com))

    def _queue_control(self, *args, **kwargs):
        srv_com = server_command.srv_command(source=args[0])
        queue_action = srv_com["action"].text
        queue_spec = srv_com.xpath(".//ns:queue_list/ns:queue/@queue_spec", smart_strings=False)[0]
        self.log("queue action '{}' for job '{}'".format(queue_action, queue_spec))
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
                "unknown job_action {}".format(queue_action),
                server_command.SRV_REPLY_STATE_ERROR,
            )
        self.send_pool_message("remote_call_async_result", unicode(srv_com))

    def _affinity_info(self, *args, **kwargs):
        srv_com = server_command.srv_command(source=args[0])
        job_id = srv_com["*job_id"]
        task_id = srv_com["*task_id"]
        action = srv_com["*action"]
        if task_id and task_id.lower().isdigit():
            task_id = int(task_id)
            full_job_id = "{}.{:d}".format(job_id, task_id)
        else:
            task_id = None
            full_job_id = job_id
        process_id = int(srv_com["*process_id"])
        _source_host = srv_com["source"].attrib["host"]
        _source_dev = self._get_device(_source_host)
        if action == "add":
            target_cpu = int(srv_com["*target_cpu"])
            self.log(
                "pinning process {:d} of job {} to CPU {:d} (host: {})".format(
                    process_id,
                    full_job_id,
                    target_cpu,
                    unicode(_source_dev),
                )
            )
        else:
            self.log(
                "removing process {:d} of job {} (host: {})".format(
                    process_id,
                    full_job_id,
                    unicode(_source_dev),
                )
            )
        if _source_dev is not None:
            if action == "add":
                self.__job_pinning_dict.setdefault(
                    full_job_id, {}
                ).setdefault(
                    _source_dev.idx, {}
                )[process_id] = target_cpu
            else:
                if full_job_id in self.__job_pinning_dict:
                    if _source_dev.idx in self.__job_pinning_dict[full_job_id]:
                        if process_id in self.__job_pinning_dict[full_job_id][_source_dev.idx]:
                            del self.__job_pinning_dict[full_job_id][_source_dev.idx][process_id]
        # import pprint
        # pprint.pprint(self.__job_pinning_dict)

    def _job_ended(self, *args, **kwargs):
        job_id, task_id = (args[0], args[1])
        if task_id:
            full_job_id = "{}.{}".format(job_id, task_id)
        else:
            full_job_id = "{}".format(job_id)
        if full_job_id in self.__job_pinning_dict:
            self.log("removed job {} from pinning dict".format(full_job_id))
            del self.__job_pinning_dict[full_job_id]
        if full_job_id in self.__job_content_dict:
            self.log("removed job {} from job_content_dict".format(full_job_id))
            del self.__job_content_dict[full_job_id]

    def _file_watch_content(self, *args, **kwargs):
        srv_com = server_command.srv_command(source=args[0])
        job_id = srv_com["*send_id"].split(":")[0]
        file_name = srv_com["*name"]
        # in case of empty file
        content = srv_com["content"].text or ""
        last_update = int(float(srv_com["*update"]))
        self.log(
            u"got content for '{}' (job {}), len {:d} bytes, update_ts {:d}".format(
                file_name,
                job_id,
                len(content),
                last_update,
            )
        )
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
        self.collectd_socket.close()
        self.__log_template.close()

    # fairshare handling
    def _update_fairshare(self):
        self._update()
        # get user list
        cur_stat, cur_out = call_command(
            "{} -suserl".format(
                self._get_sge_bin("qconf"),
            ),
            log_com=self.log
        )
        if cur_stat:
            # problem calling, return immediately
            return
        _users = [line.strip() for line in cur_out.split("\n")]
        _fs_tree = self.__sge_info.get_tree().find("fstree")
        if _fs_tree is not None:
            # fairshare tree found
            # check if all users are present
            for _user in _users:
                _user_el = _fs_tree.find(".//node[@name='{}']".format(_user))
                if _user_el is None:
                    _path = global_config["FAIRSHARE_TREE_NODE_TEMPLATE"].format(
                        project="defaultproject",
                        user=_user,
                    )
                    _shares = global_config["FAIRSHARE_TREE_DEFAULT_SHARES"]
                    self.log(
                        "No user element for user '{}' found, adding node at {} with {:d} shares".format(
                            _user,
                            _path,
                            _shares,
                        ),
                        logging_tools.LOG_LEVEL_WARN
                    )
                    _cur_stat, _cur_out = call_command(
                        "{} -astnode {}={:d}".format(
                            self._get_sge_bin("qconf"),
                            _path,
                            _shares,
                        ),
                        log_com=self.log
                    )
        else:
            self.log("no fairshare tree element found", logging_tools.LOG_LEVEL_WARN)
        # todo: match user list with sharetree config
        cur_stat, cur_out = call_command(
            "{} -n -c 1 ".format(
                self._get_sge_bin("sge_share_mon"),
            ),
            log_com=self.log
        )
        _float_re = re.compile("^\d+\.\d+")
        # headers
        drop_com = server_command.srv_command(command="set_vector")
        _bldr = drop_com.builder()
        _rms_vector = _bldr("values")
        # 10 minutes valid
        act_time = int(time.time())
        valid_until = act_time + 10 * 60
        if not cur_stat:
            for _line in cur_out.split("\n"):
                _dict = {}
                for _part in _line.strip().split():
                    _header, _value = _part.split("=", 1)
                    _header = _header.replace("%", "")
                    if _float_re.match(_value):
                        _dict[_header] = float(_value)
                    elif _value.isdigit():
                        _dict[_header] = int(_value)
                    else:
                        _dict[_header] = _value
                # filter
                if _dict["project_name"] == "defaultproject" and _dict.get("user_name", None):
                    _user = _dict["user_name"]
                    for _t_key, _key, _info in [
                        ("cpu", "cpu", "CPU usage"),
                        ("io", "io", "IO usage"),
                        ("mem", "mem", "Memory usage"),
                        ("ltcpu", "ltcpu", "long target CPU usage"),
                        ("ltio", "ltio", "long target IO usage"),
                        ("ltmem", "ltmem", "long target Memory usage"),
                        ("job_count", "job_count", "Job count"),
                        ("share.short_target", "short_target_share", "short target share"),
                        ("share.long_target", "long_target_share", "long target share"),
                        ("share.actual", "actual_share", "actual share"),
                        ("shares", "shares", "configured shares"),
                        ("level", "level", "level"),
                        ("total", "total", "total"),
                    ]:
                        _rms_vector.append(
                            hm_classes.mvect_entry(
                                "rms.fairshare.{}.{}".format(_user, _t_key),
                                info="{} for user {}".format(_info, _user),
                                default=0.,
                                value=_dict[_key],
                                factor=1,
                                valid_until=valid_until,
                                base=1000,
                            ).build_xml(_bldr)
                        )

        drop_com["vector_rms"] = _rms_vector
        drop_com["vector_rms"].attrib["type"] = "vector"
        self.vector_socket.send_unicode(unicode(drop_com))
