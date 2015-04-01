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

""" rms-server, process definitions """

from initat.rms.config import global_config
from initat.cluster.backbone.routing import get_server_uuid
from lxml.builder import E # @UnresolvedImports
import cluster_location
import commands
import configfile
import logging_tools
import os
import process_tools
import server_command
import sge_tools
import threading_tools
import time
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
        self._init_sge_info()
        self.__job_content_dict = {}
        self.register_func("get_config", self._get_config)
        self.register_func("job_control", self._job_control)
        self.register_func("queue_control", self._queue_control)
        self.register_func("file_watch_content", self._file_watch_content)
        self.register_func("full_reload", self._full_reload)
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
    def _update(self):
        self.__sge_info.update(no_file_cache=True, force_update=True)
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
                "%s gave: %s" % (queue_action, cur_out),
                server_command.SRV_REPLY_STATE_ERROR if cur_stat else server_command.SRV_REPLY_STATE_OK
            )
        else:
            srv_com.set_result(
                "unknown job_action %s" % (queue_action),
                server_command.SRV_REPLY_STATE_ERROR,
            )
        self.send_pool_message("command_result", src_id, unicode(srv_com))
    def _file_watch_content(self, *args , **kwargs):
        src_id, srv_src = args
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
                self.__job_content_dict.setdefault(job_id, {})[file_name] = E.file_content(
                    content,
                    name=file_name,
                    last_update="%d" % (last_update),
                    size="%d" % (len(content)),
                    )
            except:
                self.log("error settings content of file {}: {}".format(
                    file_name,
                    process_tools.get_except_info()
                    ),
                    logging_tools.LOG_LEVEL_ERROR)
            else:
                tot_files = sum([len(value) for value in self.__job_content_dict.itervalues()], 0)
                tot_length = sum([sum([len(cur_el.text) for _name, cur_el in _dict.iteritems()], 0) for job_id, _dict in self.__job_content_dict.iteritems()])
                self.log("cached: {:d} files, {} ({:d} bytes)".format(tot_files, logging_tools.get_size_str(tot_length), tot_length))
        else:
            self.log("job_id {} is suspicious, ignoring".format(job_id), logging_tools.LOG_LEVEL_WARN)
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)
    def loop_post(self):
        self.__log_template.close()

class server_process(threading_tools.process_pool):
    def __init__(self):
        self.__log_cache, self.__log_template = ([], None)
        self.__pid_name = global_config["PID_NAME"]
        threading_tools.process_pool.__init__(self, "main", zmq=True,
                                              zmq_debug=global_config["ZMQ_DEBUG"])
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context)
        self.__msi_block = self._init_msi_block()
        # re-insert config
        self._re_insert_config()
        self.register_exception("int_error", self._int_error)
        self.register_exception("term_error", self._int_error)
        self.register_exception("hup_error", self._hup_error)
        self._log_config()
        # dc.release()
        self._init_network_sockets()
        # self.add_process(db_verify_process("db_verify"), start=True)
        self.add_process(rms_mon_process("rms_mon"), start=True)
        self.register_func("command_result", self._com_result)
        # self._init_em()
        # self.register_timer(self._check_db, 3600, instant=True)
        # self.register_timer(self._update, 30, instant=True)
        # self.__last_update = time.time() - self.__glob_config["MAIN_LOOP_TIMEOUT"]
        # self.send_to_process("build", "rebuild_config", global_config["ALL_HOSTS_NAME"])
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        if self.__log_template:
            while self.__log_cache:
                self.__log_template.log(*self.__log_cache.pop(0))
            self.__log_template.log(lev, what)
        else:
            self.__log_cache.append((lev, what))
    def _log_config(self):
        self.log("Config info:")
        for line, log_level in global_config.get_log(clear=True):
            self.log(" - clf: [%d] %s" % (log_level, line))
        conf_info = global_config.get_config_info()
        self.log("Found %d valid global config-lines:" % (len(conf_info)))
        for conf in conf_info:
            self.log("Config : %s" % (conf))
    def _int_error(self, err_cause):
        if self["exit_requested"]:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            self["exit_requested"] = True
    def _hup_error(self, err_cause):
        self.log("got sighup", logging_tools.LOG_LEVEL_WARN)
        self.send_to_process("rms_mon", "full_reload")
    def _re_insert_config(self):
        self.log("re-insert config")
        cluster_location.write_config("rms_server", global_config)
    def process_start(self, src_process, src_pid):
        mult = 3
        process_tools.append_pids(self.__pid_name, src_pid, mult=mult)
        if self.__msi_block:
            self.__msi_block.add_actual_pid(src_pid, mult=mult, process_name=src_process)
            self.__msi_block.save_block()
    def _init_msi_block(self):
        process_tools.save_pid(self.__pid_name, mult=3)
        process_tools.append_pids(self.__pid_name, pid=configfile.get_manager_pid(), mult=3)
        if not global_config["DEBUG"] or True:
            self.log("Initialising meta-server-info block")
            msi_block = process_tools.meta_server_info("rms_server")
            msi_block.add_actual_pid(mult=3, fuzzy_ceiling=3, process_name="main")
            msi_block.add_actual_pid(act_pid=configfile.get_manager_pid(), mult=3, process_name="manager")
            msi_block.start_command = "/etc/init.d/rms-server start"
            msi_block.stop_command = "/etc/init.d/rms-server force-stop"
            msi_block.kill_pids = True
            msi_block.save_block()
        else:
            msi_block = None
        return msi_block
    def _init_network_sockets(self):
        my_0mq_id = get_server_uuid("rms")
        self.bind_id = my_0mq_id
        client = self.zmq_context.socket(zmq.ROUTER)
        client.setsockopt(zmq.IDENTITY, self.bind_id)
        client.setsockopt(zmq.RCVHWM, 256)
        client.setsockopt(zmq.SNDHWM, 256)
        client.setsockopt(zmq.RECONNECT_IVL_MAX, 500)
        client.setsockopt(zmq.RECONNECT_IVL, 200)
        client.setsockopt(zmq.TCP_KEEPALIVE, 1)
        client.setsockopt(zmq.TCP_KEEPALIVE_IDLE, 300)
        try:
            client.bind("tcp://*:%d" % (global_config["COM_PORT"]))
        except zmq.ZMQError:
            self.log("error binding to %d: %s" % (global_config["COM_PORT"],
                                                  process_tools.get_except_info()),
                     logging_tools.LOG_LEVEL_CRITICAL)
            raise
        else:
            self.log("connected to tcp://*:%d (via ID %s)" % (global_config["COM_PORT"], self.bind_id))
            self.register_poller(client, zmq.POLLIN, self._recv_command)
            self.com_socket = client
    def _recv_command(self, zmq_sock):
        data = []
        while True:
            data.append(zmq_sock.recv_unicode())
            more = zmq_sock.getsockopt(zmq.RCVMORE)
            if not more:
                break
        if len(data) == 2:
            # print data
            src_id, xml_input = data
            srv_com = server_command.srv_command(source=xml_input)
            in_com_text = srv_com["command"].text
            if in_com_text not in ["get_config"]:
                self.log("got command '%s' from %s" % (srv_com["command"].text, src_id))
            srv_com.update_source()
            # set dummy result
            srv_com["result"] = None
            cur_com = srv_com["command"].text
            if cur_com == "get_config":
                self.send_to_process("rms_mon", "get_config", src_id, unicode(srv_com))
            elif cur_com == "job_control":
                self.send_to_process("rms_mon", "job_control", src_id, unicode(srv_com))
            elif cur_com == "queue_control":
                self.send_to_process("rms_mon", "queue_control", src_id, unicode(srv_com))
            elif cur_com == "get_0mq_id":
                srv_com["zmq_id"] = self.bind_id
                srv_com["result"].attrib.update({
                    "reply" : "0MQ_ID is %s" % (self.bind_id),
                    "state" : "%d" % (server_command.SRV_REPLY_STATE_OK)})
                self._send_result(src_id, srv_com)
            elif cur_com == "status":
                srv_com.set_result(
                    "up and running",
                    server_command.SRV_REPLY_STATE_OK)
                self._send_result(src_id, srv_com)
            elif cur_com == "file_watch_content":
                self.send_to_process("rms_mon", "file_watch_content", src_id, unicode(srv_com))
            else:
                srv_com["result"].attrib.update(
                    {
                        "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR),
                        "reply" : "unknown command %s" % (cur_com)
                    }
                )
                self._send_result(src_id, srv_com)
        else:
            self.log("received wrong data (len() = %d != 2)" % (len(data)),
                     logging_tools.LOG_LEVEL_ERROR)
    def _send_result(self, src_id, srv_com):
        self.com_socket.send_unicode(src_id, zmq.SNDMORE)
        self.com_socket.send_unicode(unicode(srv_com))
    def _com_result(self, src_proc, proc_id, src_id, srv_com):
        self._send_result(src_id, srv_com)
    def loop_post(self):
        if self.com_socket:
            self.log("closing socket")
            self.com_socket.close()
        process_tools.delete_pid(self.__pid_name)
        if self.__msi_block:
            self.__msi_block.remove_meta_block()
        self.__log_template.close()

