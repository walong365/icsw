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

from initat.cluster.backbone.routing import get_server_uuid
from initat.rms.accounting import accounting_process
from initat.rms.config import global_config
from initat.rms.license import license_process
from initat.rms.rmsmon import rms_mon_process
from django.db import connection
from initat.tools import cluster_location
from initat.tools import configfile
from initat.tools import logging_tools
from initat.tools import process_tools
from initat.tools import server_command
from initat.tools import threading_tools
import zmq


class server_process(threading_tools.process_pool):
    def __init__(self):
        self.__log_cache, self.__log_template = ([], None)
        self.__pid_name = global_config["PID_NAME"]
        threading_tools.process_pool.__init__(
            self,
            "main",
            zmq=True,
            zmq_debug=global_config["ZMQ_DEBUG"]
        )
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context)
        self.__msi_block = self._init_msi_block()
        connection.close()
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
        self.add_process(accounting_process("accounting"), start=True)
        self.add_process(license_process("license"), start=True)
        self.register_func("command_result", self._com_result)

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
            self.log(" - clf: [{:d}] {}".format(log_level, line))
        conf_info = global_config.get_config_info()
        self.log("Found {:d} valid global config-lines:".format(len(conf_info)))
        for conf in conf_info:
            self.log("Config : {}".format(conf))

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
        process_tools.append_pids(self.__pid_name, pid=configfile.get_manager_pid(), mult=5)
        if not global_config["DEBUG"] or True:
            self.log("Initialising meta-server-info block")
            msi_block = process_tools.meta_server_info("rms-server")
            msi_block.add_actual_pid(mult=3, fuzzy_ceiling=4, process_name="main")
            msi_block.add_actual_pid(act_pid=configfile.get_manager_pid(), mult=5, process_name="manager")
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
            client.bind("tcp://*:{:d}".format(global_config["COM_PORT"]))
        except zmq.ZMQError:
            self.log(
                "error binding to {:d}: {}".format(
                    global_config["COM_PORT"],
                    process_tools.get_except_info()
                ),
                logging_tools.LOG_LEVEL_CRITICAL
            )
            raise
        else:
            self.log("connected to tcp://*:{:d} (via ID {})".format(global_config["COM_PORT"], self.bind_id))
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
                self.log("got command '{}' from {}".format(srv_com["command"].text, src_id))
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
                srv_com.set_result("0MQ_ID is {}".format(self.bind_id))
                self._send_result(src_id, srv_com)
            elif cur_com == "status":
                srv_com.set_result(
                    "up and running",
                    server_command.SRV_REPLY_STATE_OK)
                self._send_result(src_id, srv_com)
            elif cur_com == "get_license_usage":
                self.send_to_process("license", "get_license_usage", src_id, unicode(srv_com))
            elif cur_com == "file_watch_content":
                self.send_to_process("rms_mon", "file_watch_content", src_id, unicode(srv_com))
            elif cur_com in ["pe_start", "pe_end", "job_start", "job_end"]:
                self.send_to_process("accounting", "job_ss_info", cur_com, src_id, unicode(srv_com))
                srv_com.set_result("got it")
                self._send_result(src_id, srv_com)
            else:
                # print srv_com.pretty_print()
                srv_com.set_result(
                    "unknown command {}".format(cur_com),
                    server_command.SRV_REPLY_STATE_ERROR,
                )
                self._send_result(src_id, srv_com)
        else:
            self.log(
                "received wrong data (len() = {:d} != 2)".format(len(data)),
                logging_tools.LOG_LEVEL_ERROR,
            )

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
