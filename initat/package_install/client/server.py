#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008,2009,2012,2013 Andreas Lang-Nevyjel
#
# this file is part of package-client
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
""" daemon to automatically install packages (.rpm, .deb) """

import os
import configfile
import zmq
import uuid_tools
import server_command
import logging_tools
import process_tools
import threading_tools

from initat.package_install.client.config import global_config, LF_NAME
from initat.package_install.client.install_process import yum_install_process, zypper_install_process, \
    get_srv_command

class server_process(threading_tools.process_pool):
    def __init__(self):
        self.global_config = global_config
        self.__log_cache, self.__log_template = ([], None)
        threading_tools.process_pool.__init__(self, "main", zmq=True,
            zmq_debug=global_config["ZMQ_DEBUG"]
            )
        if not global_config["DEBUG"]:
            process_tools.set_handles({
                "out" : (1, "package_client.out"),
                "err" : (0, "/var/lib/logging-server/py_err")},
                                      zmq_context=self.zmq_context)
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context)
        self.install_signal_handlers()
        # init environment
        self._init_environment()
        self._init_msi_block()
        self.register_exception("int_error"  , self._int_error)
        self.register_exception("term_error" , self._int_error)
        self.register_exception("alarm_error", self._alarm_error)
        # set lockfile
        process_tools.set_lockfile_msg(LF_NAME, "connect...")
        # log buffer
        self._show_config()
        # log limits
        self._log_limits()
        self._init_network_sockets()
        self.register_func("send_to_server", self._send_to_server)
        if os.path.isfile("/etc/centos-release"):
            self.add_process(yum_install_process("install"), start=True)
        else:
            self.add_process(zypper_install_process("install"), start=True)
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        if self.__log_template:
            while self.__log_cache:
                cur_lev, cur_what = self.__log_cache.pop(0)
                self.__log_template.log(cur_lev, cur_what)
            self.__log_template.log(lev, what)
        else:
            self.__log_cache.append((lev, what))
    def _init_environment(self):
        # Debian fix to get full package names, sigh ...
        os.environ["COLUMNS"] = "2000"
    def _init_msi_block(self):
        # store pid name because global_config becomes unavailable after SIGTERM
        self.__pid_name = global_config["PID_NAME"]
        process_tools.save_pids(global_config["PID_NAME"], mult=3)
        process_tools.append_pids(global_config["PID_NAME"], pid=configfile.get_manager_pid(), mult=3)
        if True: # not self.__options.DEBUG:
            self.log("Initialising meta-server-info block")
            msi_block = process_tools.meta_server_info("package-client")
            msi_block.add_actual_pid(mult=3, fuzzy_ceiling=3)
            msi_block.add_actual_pid(act_pid=configfile.get_manager_pid(), mult=3)
            msi_block.start_command = "/etc/init.d/package-client start"
            msi_block.stop_command = "/etc/init.d/package-client force-stop"
            msi_block.kill_pids = True
            # msi_block.heartbeat_timeout = 60
            msi_block.save_block()
        else:
            msi_block = None
        self.__msi_block = msi_block
    def _show_config(self):
        try:
            for log_line, log_level in global_config.get_log():
                self.log("Config info : [%d] %s" % (log_level, log_line))
        except:
            self.log("error showing configfile log, old configfile ? (%s)" % (process_tools.get_except_info()),
                     logging_tools.LOG_LEVEL_ERROR)
        conf_info = global_config.get_config_info()
        self.log("Found %s:" % (logging_tools.get_plural("valid configline", len(conf_info))))
        for conf in conf_info:
            self.log("Config : %s" % (conf))
    def _log_limits(self):
        # read limits
        r_dict = {}
        try:
            import resource
        except ImportError:
            self.log("cannot import resource", logging_tools.LOG_LEVEL_CRITICAL)
        else:
            available_resources = [key for key in dir(resource) if key.startswith("RLIMIT")]
            for av_r in available_resources:
                try:
                    r_dict[av_r] = resource.getrlimit(getattr(resource, av_r))
                except ValueError:
                    r_dict[av_r] = "invalid resource"
                except:
                    r_dict[av_r] = None
            if r_dict:
                res_keys = sorted(r_dict.keys())
                self.log("%s defined" % (logging_tools.get_plural("limit", len(res_keys))))
                res_list = logging_tools.new_form_list()
                for key in res_keys:
                    val = r_dict[key]
                    if type(val) == type(""):
                        info_str = val
                    elif type(val) == type(()):
                        info_str = "%8d (hard), %8d (soft)" % val
                    else:
                        info_str = "None (error?)"
                    res_list.append([logging_tools.form_entry(key, header="key"),
                                     logging_tools.form_entry(info_str, header="value")])
                for line in str(res_list).split("\n"):
                    self.log(line)
            else:
                self.log("no limits found, strange ...", logging_tools.LOG_LEVEL_WARN)
    def _init_network_sockets(self):
        # connect to server
        srv_port = self.zmq_context.socket(zmq.DEALER)
        srv_port.setsockopt(zmq.LINGER, 1000)
        srv_port.setsockopt(zmq.IDENTITY, uuid_tools.get_uuid().get_urn())
        srv_port.setsockopt(zmq.TCP_KEEPALIVE, 1)
        srv_port.setsockopt(zmq.TCP_KEEPALIVE_IDLE, 300)
        # srv_port.setsockopt(zmq.SUBSCRIBE, "")
        self.conn_str = "tcp://%s:%d" % (
            global_config["PACKAGE_SERVER"],
            global_config["SERVER_COM_PORT"])
        srv_port.connect(self.conn_str)
        # pull_port = self.zmq_context.socket(zmq.PUSH)
        # pull_port.setsockopt(zmq.IDENTITY, uuid_tools.get_uuid().get_urn())
        self.register_poller(srv_port, zmq.POLLIN, self._recv)
        self.log("connected to %s" % (self.conn_str))
        self.srv_port = srv_port
        # client socket
        self.bind_id = "%s:pclient:" % (uuid_tools.get_uuid().get_urn())
        client_sock = self.zmq_context.socket(zmq.ROUTER)
        client_sock.setsockopt(zmq.LINGER, 1000)
        client_sock.setsockopt(zmq.IDENTITY, self.bind_id)
        client_sock.setsockopt(zmq.TCP_KEEPALIVE, 1)
        client_sock.setsockopt(zmq.TCP_KEEPALIVE_IDLE, 300)
        client_sock.setsockopt(zmq.SNDHWM, 16)
        client_sock.setsockopt(zmq.RCVHWM, 16)
        client_sock.setsockopt(zmq.RECONNECT_IVL_MAX, 500)
        client_sock.setsockopt(zmq.RECONNECT_IVL, 200)
        bind_str = "tcp://0.0.0.0:%d" % (
                    global_config["COM_PORT"])
        client_sock.bind(bind_str)
        self.log("bound to %s (ID %s)" % (bind_str, self.bind_id))
        self.client_socket = client_sock
        self.register_poller(client_sock, zmq.POLLIN, self._recv_client)
        # send commands
        self._send_to_server_int(get_srv_command(command="register"))
        self._get_repos()
        self._get_new_config()
    def _send_to_server_int(self, xml_com):
        self._send_to_server("self", os.getpid(), xml_com["command"].text, unicode(xml_com), "server command")
    def _send_to_server(self, src_proc, *args, **kwargs):
        src_pid, com_name, send_com, send_info = args
        self.log("sending %s (%s) to server %s" % (com_name, send_info, self.conn_str))
        self.srv_port.send_unicode(send_com)
    def _get_new_config(self):
        self._send_to_server_int(get_srv_command(command="get_package_list"))
        # self._send_to_server_int(get_srv_command(command="get_rsync_list"))
    def _get_repos(self):
        self._send_to_server_int(get_srv_command(command="get_repo_list"))
    def _recv_client(self, zmq_sock):
        data = [zmq_sock.recv()]
        while zmq_sock.getsockopt(zmq.RCVMORE):
            data.append(zmq_sock.recv())
        if len(data) == 2:
            src_id = data.pop(0)
            data = data[0]
            srv_com = server_command.srv_command(source=data)
            srv_com.update_source()
            cur_com = srv_com["command"].text
            self.log("got %s (length: %d) from %s" % (cur_com, len(data), src_id))
            srv_com["result"] = None
            if cur_com == "get_0mq_id":
                srv_com["zmq_id"] = self.bind_id
                srv_com["result"].attrib.update({
                    "reply" : "0MQ_ID is %s" % (self.bind_id),
                    "state" : "%d" % (server_command.SRV_REPLY_STATE_OK)})
            elif cur_com == "status":
                # FIXME, Todo
                srv_com["result"].attrib.update({
                    "reply" : "everything OK :-)",
                    "state" : "%d" % (server_command.SRV_REPLY_STATE_OK)})
            else:
                srv_com["result"].attrib.update(
                    {"reply" : "unknown command '%s'" % (cur_com),
                        "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR)})
            zmq_sock.send_unicode(src_id, zmq.SNDMORE)
            zmq_sock.send_unicode(unicode(srv_com))
            del srv_com
        else:
            self.log("cannot receive more data, already got '%s'" % (", ".join(data)),
                     logging_tools.LOG_LEVEL_ERROR)
    def _recv(self, zmq_sock):
        batch_list = []
        while True:
            data = []
            while True:
                try:
                    in_com = server_command.srv_command(source=zmq_sock.recv_unicode())
                except:
                    self.log("error decoding command: %s" % (process_tools.get_except_info()),
                             logging_tools.LOG_LEVEL_ERROR)
                else:
                    rcv_com = in_com["command"].text
                    self.log("got command %s" % (rcv_com))
                    if rcv_com == "new_config":
                        self._get_new_config()
                    elif rcv_com == "sync_repos":
                        self._get_repos()
                    else:
                        data.append(in_com)
                if not zmq_sock.getsockopt(zmq.RCVMORE):
                    break
            batch_list.extend(data)
            if not zmq_sock.poll(zmq.POLLIN):
                break
        # batch_list = self._optimize_list(batch_list)
        self.send_to_process("install",
                             "command_batch",
                             [unicode(cur_com) for cur_com in batch_list])
    # def _optimize_list(self, in_list):
    #    return in_list
    def _int_error(self, err_cause):
        self.__exit_cause = err_cause
        if self["exit_requested"]:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            self.log("got int_error, err_cause is '%s'" % (err_cause), logging_tools.LOG_LEVEL_WARN)
            self["exit_requested"] = True
    def _alarm_error(self, err_cause):
        self.__comsend_queue.put("reload")
    def loop_end(self):
        process_tools.delete_pid(self.__pid_name)
        if self.__msi_block:
            self.__msi_block.remove_meta_block()
    def loop_post(self):
        self.srv_port.close()
        self.client_socket.close()
        self.__log_template.close()
