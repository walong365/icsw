#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001-2014 Andreas Lang-Nevyjel
#
# this file is part of package-server
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
""" package server """

from django.db import connection
from initat.cluster.backbone.routing import get_server_uuid
from initat.package_install.server.config import global_config
from initat.package_install.server.repository_process import repo_process
from initat.package_install.server.structs import client
import cluster_location
import configfile
import logging_tools
import os
import process_tools
import server_command
import threading_tools
import zmq


class server_process(threading_tools.process_pool):
    def __init__(self):
        self.__log_cache, self.__log_template = ([], None)
        self.__pid_name = global_config["PID_NAME"]
        threading_tools.process_pool.__init__(
            self, "main", zmq=True,
            zmq_debug=global_config["ZMQ_DEBUG"])
        self.register_exception("int_error", self._int_error)
        self.register_exception("term_error", self._int_error)
        self.register_exception("hup_error", self._hup_error)
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context)
        self._log_config()
        # idx for delayed commands
        self.__delayed_id, self.__delayed_struct = (0, {})
        self._re_insert_config()
        self.__msi_block = self._init_msi_block()
        self._init_clients()
        self._init_network_sockets()
        self.add_process(repo_process("repo"), start=True)
        # close DB connection
        connection.close()
        self.register_timer(self._send_update, 3600, instant=True)
        self.register_func("delayed_result", self._delayed_result)
        self.send_to_process("repo", "rescan_repos")

    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        if self.__log_template:
            while self.__log_cache:
                self.__log_template.log(*self.__log_cache.pop(0))
            self.__log_template.log(lev, what)
        else:
            self.__log_cache.append((lev, what))

    def _init_clients(self):
        client.init(self)

    def _register_client(self, c_uid, srv_com):
        client.register(c_uid, srv_com["source"].attrib["host"])

    def _re_insert_config(self):
        self.log("re-insert config")
        cluster_location.write_config("package_server", global_config)

    def _init_msi_block(self):
        process_tools.save_pid(self.__pid_name, mult=3)
        process_tools.append_pids(self.__pid_name, pid=configfile.get_manager_pid(), mult=3)
        if not global_config["DEBUG"] or True:
            self.log("Initialising meta-server-info block")
            msi_block = process_tools.meta_server_info("package-server")
            msi_block.add_actual_pid(mult=3, fuzzy_ceiling=4, process_name="main")
            msi_block.add_actual_pid(act_pid=configfile.get_manager_pid(), mult=3, process_name="manager")
            msi_block.start_command = "/etc/init.d/package-server start"
            msi_block.stop_command = "/etc/init.d/package-server force-stop"
            msi_block.kill_pids = True
            msi_block.save_block()
        else:
            msi_block = None
        return msi_block

    def _log_config(self):
        self.log("Config info:")
        for line, log_level in global_config.get_log(clear=True):
            self.log(" - clf: [%d] %s" % (log_level, line))
        conf_info = global_config.get_config_info()
        self.log("Found %d valid config-lines:" % (len(conf_info)))
        for conf in conf_info:
            self.log("Config : %s" % (conf))

    def _int_error(self, err_cause):
        if self["exit_requested"]:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            self["exit_requested"] = True

    def _hup_error(self, err_cause):
        self.log("got SIGHUP, rescanning repositories")
        self.send_to_process("repo", "rescan_all")

    def process_start(self, src_process, src_pid):
        mult = 3
        process_tools.append_pids(self.__pid_name, src_pid, mult=mult)
        if self.__msi_block:
            self.__msi_block.add_actual_pid(src_pid, mult=mult, process_name=src_process)
            self.__msi_block.save_block()

    def loop_end(self):
        for c_name in client.name_set:
            cur_c = client.get(c_name)
            if cur_c is None:
                self.log("no client found for '%s'" % (c_name), logging_tools.LOG_LEVEL_ERROR)
            else:
                cur_c.close()
        process_tools.delete_pid(self.__pid_name)
        if self.__msi_block:
            self.__msi_block.remove_meta_block()

    def loop_post(self):
        for open_sock in self.socket_dict.itervalues():
            open_sock.close()
        self.__log_template.close()

    def _new_com(self, zmq_sock):
        data = [zmq_sock.recv_unicode()]
        while zmq_sock.getsockopt(zmq.RCVMORE):
            data.append(zmq_sock.recv_unicode())
        if len(data) == 2:
            c_uid, srv_com = (data[0], server_command.srv_command(source=data[1]))
            cur_com = srv_com["command"].text
            if cur_com == "register":
                self._register_client(c_uid, srv_com)
            else:
                if c_uid.endswith("webfrontend"):
                    self._handle_wfe_command(zmq_sock, c_uid, srv_com)
                else:
                    try:
                        cur_client = client.get(c_uid)
                    except KeyError:
                        srv_com.update_source()
                        # srv_com["result"] = None
                        self.log("got command '%s' from %s" % (cur_com, c_uid))
                        # check for normal command
                        if cur_com == "get_0mq_id":
                            srv_com["zmq_id"] = self.bind_id
                            srv_com.set_result("0MQ_ID is %s" % (self.bind_id))
                        elif cur_com == "status":
                            srv_com.set_result("up and running")
                        else:
                            self.log(
                                "unknown uid %s (command %s), not known" % (
                                    c_uid,
                                    cur_com,
                                ),
                                logging_tools.LOG_LEVEL_CRITICAL
                            )
                            srv_com.set_result("unknown command '%s'" % (cur_com), server_command.SRV_REPLY_STATE_ERROR)
                        zmq_sock.send_unicode(c_uid, zmq.SNDMORE)
                        zmq_sock.send_unicode(unicode(srv_com))
                    else:
                        cur_client.new_command(srv_com)
        else:
            self.log("wrong number of data chunks (%d != 2)" % (len(data)),
                     logging_tools.LOG_LEVEL_ERROR)

    def _delayed_result(self, src_name, src_pid, ext_id, ret_str, ret_state, **kwargs):
        in_uid, srv_com = self.__delayed_struct[ext_id]
        del self.__delayed_struct[ext_id]
        self.log("sending delayed return for %s" % (unicode(srv_com)))
        srv_com.set_result(ret_str, ret_state)
        zmq_sock = self.socket_dict["router"]
        zmq_sock.send_unicode(unicode(in_uid), zmq.SNDMORE)
        zmq_sock.send_unicode(unicode(srv_com))

    def _handle_wfe_command(self, zmq_sock, in_uid, srv_com):
        in_com = srv_com["command"].text
        self.log("got server_command %s from %s" % (
            in_com,
            in_uid))
        srv_com.update_source()
        immediate_return = True
        srv_com.set_result("result not set", server_command.SRV_REPLY_STATE_UNSET)
        if in_com == "new_config":
            all_devs = srv_com.xpath(".//ns:device_command/@name", smart_strings=False)
            if not all_devs:
                valid_devs = list(client.name_set)
            else:
                valid_devs = [name for name in all_devs if name in client.name_set]
            self.log("{} requested, {} found".format(
                logging_tools.get_plural("device", len(all_devs)),
                logging_tools.get_plural("device", len(valid_devs))))
            for cur_dev in all_devs:
                srv_com.xpath(
                    ".//ns:device_command[@name='%s']" % (cur_dev), smart_strings=False
                )[0].attrib["config_sent"] = "1" if cur_dev in valid_devs else "0"
            if valid_devs:
                self._send_update(command="new_config", dev_list=valid_devs)
            srv_com.set_result(
                "send update to {:d} of {}".format(
                    len(valid_devs),
                    logging_tools.get_plural("device", len(all_devs))
                ),
                server_command.SRV_REPLY_STATE_OK if len(valid_devs) == len(all_devs) else server_command.SRV_REPLY_STATE_WARN
            )
        elif in_com == "reload_searches":
            self.send_to_process("repo", "reload_searches")
            srv_com.set_result("ok reloading")
        elif in_com == "rescan_repos":
            self.__delayed_id += 1
            self.__delayed_struct[self.__delayed_id] = (in_uid, srv_com)
            srv_com["return_id"] = self.__delayed_id
            self.send_to_process("repo", "rescan_repos", unicode(srv_com))
            immediate_return = False
        elif in_com == "sync_repos":
            all_devs = list(client.name_set)
            self.log("sending sync_repos to {}".format(logging_tools.get_plural("device", len(all_devs))))
            if all_devs:
                self._send_update(command="sync_repos", dev_list=all_devs)
            srv_com.set_result(
                "send sync_repos to {}".format(
                    logging_tools.get_plural("device", len(all_devs))
                )
            )
        elif in_com == "clear_caches":
            all_devs = list(client.name_set)
            if os.getuid():
                self.log("root privileges required to clear cache", logging_tools.LOG_LEVEL_ERROR)
            else:
                self.send_to_process("repo", "clear_cache", unicode(srv_com))
            self.log("sending clear_cache to %s" % (logging_tools.get_plural("device", len(all_devs))))
            if all_devs:
                self._send_update(command="clear_cache", dev_list=all_devs)
            srv_com.set_result(
                "send clear_cache to {}".format(
                    logging_tools.get_plural("device", len(all_devs))
                )
            )
        else:
            srv_com.set_result("command %s not known" % (in_com), server_command.SRV_REPLY_STATE_ERROR)
        # print srv_com.pretty_print()
        if immediate_return:
            zmq_sock.send_unicode(unicode(in_uid), zmq.SNDMORE)
            zmq_sock.send_unicode(unicode(srv_com))

    def _init_network_sockets(self):
        my_0mq_id = get_server_uuid("package")
        self.bind_id = my_0mq_id
        self.socket_dict = {}
        # get all ipv4 interfaces with their ip addresses, dict: interfacename -> IPv4
        for key, sock_type, bind_port, target_func in [
            ("router", zmq.ROUTER, global_config["SERVER_PUB_PORT"], self._new_com),
        ]:
            client = self.zmq_context.socket(sock_type)
            client.setsockopt(zmq.IDENTITY, self.bind_id)
            client.setsockopt(zmq.LINGER, 100)
            client.setsockopt(zmq.RCVHWM, 256)
            client.setsockopt(zmq.SNDHWM, 256)
            client.setsockopt(zmq.BACKLOG, 1)
            client.setsockopt(zmq.TCP_KEEPALIVE, 1)
            client.setsockopt(zmq.TCP_KEEPALIVE_IDLE, 300)
            # hm, this can be dangerous
            # client.setsockopt(zmq.ROUTER_MANDATORY, 1)
            conn_str = "tcp://*:%d" % (bind_port)
            try:
                client.bind(conn_str)
            except zmq.ZMQError:
                self.log(
                    "error binding to %s{%d}: %s" % (
                        conn_str,
                        sock_type,
                        process_tools.get_except_info()
                    ),
                    logging_tools.LOG_LEVEL_CRITICAL)
                client.close()
            else:
                self.log("bind to port %s{%d}, ID is %s" % (
                    conn_str,
                    sock_type,
                    self.bind_id,
                    ))
                self.register_poller(client, zmq.POLLIN, target_func)
                self.socket_dict[key] = client

    def send_reply(self, t_uid, srv_com):
        send_sock = self.socket_dict["router"]
        send_sock.send_unicode(t_uid, zmq.SNDMORE | zmq.NOBLOCK)
        send_sock.send_unicode(unicode(srv_com), zmq.NOBLOCK)

    def _send_update(self, command="send_info", dev_list=[], **kwargs):
        send_list = dev_list or client.name_set
        self.log(
            "send command {} to {} ({})".format(
                command,
                logging_tools.get_plural("client", len(send_list)),
                ", ".join(["{}={}".format(key, value) for key, value in kwargs.iteritems()]) if kwargs else "no kwargs",
            )
        )
        send_com = server_command.srv_command(command=command, **kwargs)
        for target_name in send_list:
            cur_c = client.get(target_name)
            if cur_c is not None:
                self.send_reply(cur_c.uid, send_com)
            else:
                self.log("no client with name '%s' found" % (target_name), logging_tools.LOG_LEVEL_WARN)
