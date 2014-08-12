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
from initat.host_monitoring import hm_classes
from initat.rms.config import global_config
from lxml import etree # @UnresolvedImport
from lxml.builder import E # @UnresolvedImport
import commands
import logging_tools
import os
import process_tools
import server_command
import sge_tools
import threading_tools
import time
import uuid
import zmq

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

class rms_mon_process(threading_tools.process_obj):
    def process_init(self):
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context, init_logger=True)
        self.__node_options = sge_tools.get_empty_node_options()
        self._init_network()
        self._init_sge_info()
        self.__job_content_dict = {}
        self.register_func("get_config", self._get_config)
        self.register_func("job_control", self._job_control)
        self.register_func("queue_control", self._queue_control)
        self.register_func("file_watch_content", self._file_watch_content)
        self.register_func("full_reload", self._full_reload)
        self.register_timer(self._update, 30)
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
        _num_queues = 0
        act_time = time.time()
        _su_t = 0
        _sr_t = 0
        _st_t = 0
        _qs_error = 0
        _qs_disabled = 0
        for _node in _res.findall(".//node"):
            _num_queues += 1
            _host = _node.findtext("host")
            _queue = _node.findtext("queue")
            _queue_names.add(_queue)
            _host_names.add(_queue)
            _su, _sr, _st = (
                int(_node.findtext("slots_used")),
                int(_node.findtext("slots_reserved")),
                int(_node.findtext("slots_total")),
            )
            _su_t += _su
            _sr_t += _sr
            _st_t += _st
            # count states
            _state = _node.findtext("state")
            if "E" in _state:
                _qs_error += 1
            if "d" in _state:
                _qs_disabled += 1
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
        for _key, _value, _info in [
            ("total", _num_queues, "queues defined"),
            ("error", _qs_error, "queues in error state"),
            ("disabled", _qs_disabled, "queues disabled"),
            ]:
            _rms_vector.append(
                hm_classes.mvect_entry(
                    "rms.queues.{}".format(_key),
                    info=_info,
                    default=0,
                    value=_value,
                    factor=1,
                    valid_until=valid_until,
                    base=1000,
                ).build_xml(_bldr)
            )
        for _key, _value, _info in [
            ("total", _st_t, "slots defined"),
            ("reserved", _sr_t, "slots reserved"),
            ("used", _su_t, "slots used"),
            ("free", _st_t - _su_t, "slots free"),
            ]:
            _rms_vector.append(
                hm_classes.mvect_entry(
                    "rms.slots.{}".format(_key),
                    info=_info,
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
    def _job_control(self, *args , **kwargs):
        src_id, srv_com_str = args
        srv_com = server_command.srv_command(source=srv_com_str)
        job_action = srv_com["action"].text
        job_id = srv_com.xpath(".//ns:job_list/ns:job/@job_id", smart_strings=False)[0]
        self.log("job action '{}' for job '{}'".format(job_action, job_id))
        if job_action in ["force_delete", "delete"]:
            cur_stat, cur_out, log_lines = call_command(
                "{} {} {}".format(
                    self._get_sge_bin("qdel"),
                    "-f" if job_action == "force_delete" else "",
                    job_id
                )
            )
            for log_line in log_lines:
                self.log(log_line, logging_tools.LOG_LEVEL_OK if not cur_stat else logging_tools.LOG_LEVEL_ERROR)
            srv_com.set_result(
                "%s gave: %s" % (job_action, cur_out),
                server_command.SRV_REPLY_STATE_ERROR if cur_stat else server_command.SRV_REPLY_STATE_OK
            )
        else:
            srv_com.set_result(
                "unknown job_action %s" % (job_action),
                server_command.SRV_REPLY_STATE_ERROR,
            )
        self.send_pool_message("command_result", src_id, unicode(srv_com))
    def _queue_control(self, *args , **kwargs):
        src_id, srv_com_str = args
        srv_com = server_command.srv_command(source=srv_com_str)
        queue_action = srv_com["action"].text
        queue_spec = srv_com.xpath(".//ns:queue_list/ns:queue/@queue_spec", smart_strings=False)[0]
        self.log("queue action '%s' for job '%s'" % (queue_action, queue_spec))
        if queue_action in ["enable", "disable", "clear_error"]:
            cur_stat, cur_out, log_lines = call_command(
                "{} {} {}".format(
                    self._get_sge_bin("qmod"),
                    {
                        "enable" : "-e",
                        "disable" : "-d",
                        "clear_error" : "-c",
                    }[queue_action],
                    queue_spec,
                )
            )
            for log_line in log_lines:
                self.log(log_line, logging_tools.LOG_LEVEL_OK if not cur_stat else logging_tools.LOG_LEVEL_ERROR)
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
    def _file_watch_content(self, *args , **kwargs):
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
                if not file_name in self.__job_content_dict.get(job_id, {}):
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
                tot_length = sum([sum([int(cur_el.attrib["size"]) for _name, cur_el in _dict.iteritems()], 0) for job_id, _dict in self.__job_content_dict.iteritems()])
                self.log("cached: {:d} files, {} ({:d} bytes)".format(tot_files, logging_tools.get_size_str(tot_length), tot_length))
        else:
            self.log("job_id {} is suspicious, ignoring".format(job_id), logging_tools.LOG_LEVEL_WARN)
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)
    def loop_post(self):
        self.vector_socket.close()
        self.__log_template.close()

