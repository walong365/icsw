#!/usr/bin/python-init -Ot
# -*- coding: utf-8 -*-
#
# Copyright (C) 2013 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of host-monitoring
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

""" host-monitoring, with 0MQ and twisted support, relay part """

import argparse
import base64
import configfile
import difflib
import icmp_twisted
import logging_tools
import net_tools
import netifaces
import os
import pprint
import process_tools
import resource
import server_command
import socket
import threading_tools
import time
import uuid_tools
import zmq

from lxml import etree # @UnresolvedImport
from lxml.builder import E # @UnresolvedImport

from initat.host_monitoring import limits, hm_classes
from initat.host_monitoring.config import global_config
from initat.host_monitoring.constants import MAPPING_FILE_IDS, MAPPING_FILE_TYPES, MASTER_FILE_NAME
from initat.host_monitoring.hm_twisted import twisted_process
from initat.host_monitoring.tools import my_cached_file

class id_discovery(object):
    # discover 0mq ids
    def __init__(self, srv_com, src_id, xml_input):
        self.port = int(srv_com["port"].text)
        self.host = srv_com["host"].text
        self.conn_str = "tcp://%s:%d" % (self.host,
                                         self.port)
        self.init_time = time.time()
        self.srv_com = srv_com
        self.src_id = src_id
        self.xml_input = xml_input
        cur_time = time.time()
        if self.conn_str in id_discovery.last_try and abs(id_discovery.last_try[self.conn_str] - cur_time) < 60:
            # need 60 seconds between tries
            self.socket = None
            self.send_return("last 0MQ discovery less than 60 seconds ago")
        else:
            id_discovery.pending[self.conn_str] = self
            new_sock = id_discovery.relayer_process.zmq_context.socket(zmq.DEALER)
            id_str = "relayer_dlr_%s_%s" % (process_tools.get_machine_name(),
                                            self.src_id)
            new_sock.setsockopt(zmq.IDENTITY, id_str)
            new_sock.setsockopt(zmq.LINGER, 0)
            new_sock.setsockopt(zmq.SNDHWM, id_discovery.backlog_size)
            new_sock.setsockopt(zmq.RCVHWM, id_discovery.backlog_size)
            new_sock.setsockopt(zmq.BACKLOG, id_discovery.backlog_size)
            new_sock.setsockopt(zmq.TCP_KEEPALIVE, 1)
            new_sock.setsockopt(zmq.TCP_KEEPALIVE_IDLE, 300)
            self.socket = new_sock
            id_discovery.relayer_process.register_poller(new_sock, zmq.POLLIN, self.get_result)
            # id_discovery.relayer_process.register_poller(new_sock, zmq.POLLIN, self.error)
            dealer_message = server_command.srv_command(command="get_0mq_id")
            dealer_message["target_ip"] = self.host
            self.socket.connect(self.conn_str)
            self.log("send discovery message")
            self.socket.send_unicode(unicode(dealer_message))
    def send_return(self, error_msg):
        self.log(error_msg, logging_tools.LOG_LEVEL_ERROR)
        dummy_mes = host_message(self.srv_com["command"].text, self.src_id, self.srv_com, self.xml_input)
        dummy_mes.set_result(limits.nag_STATE_CRITICAL, error_msg)
        self.send_result(dummy_mes)
    def send_result(self, host_mes, result=None):
        id_discovery.relayer_process.sender_socket.send_unicode(host_mes.src_id, zmq.SNDMORE)
        id_discovery.relayer_process.sender_socket.send_unicode(host_mes.get_result(result))
        self.close()
    def error(self, zmq_sock):
        self.log("got error for socket", logging_tools.LOG_LEVEL_ERROR)
        time.sleep(1)
    def get_result(self, zmq_sock):
        cur_reply = server_command.srv_command(source=zmq_sock.recv())
        if self.conn_str in id_discovery.last_try:
            del id_discovery.last_try[self.conn_str]
        try:
            zmq_id = cur_reply["zmq_id"].text
        except:
            self.send_return("error extracting 0MQ id: %s" % (process_tools.get_except_info()))
        else:
            if zmq_id in id_discovery.reverse_mapping and self.host not in id_discovery.reverse_mapping[zmq_id]:
                self.log("0MQ is %s but already used by %s: %s" % (
                    zmq_id,
                    logging_tools.get_plural("host", len(id_discovery.reverse_mapping[zmq_id])),
                    ", ".join(sorted(id_discovery.reverse_mapping[zmq_id]))),
                         logging_tools.LOG_LEVEL_ERROR)
                self.send_return("0MQ id not unique, virtual host setup found ?")
            else:
                self.log("0MQ id is %s" % (zmq_id))
                id_discovery.mapping[self.conn_str] = zmq_id
                # reinject
                if self.port == 2001:
                    id_discovery.relayer_process._send_to_client(self.src_id, self.srv_com, self.xml_input)
                else:
                    id_discovery.relayer_process._send_to_nhm_service(self.src_id, self.srv_com, self.xml_input)
                # save mapping
                file(MAPPING_FILE_IDS, "w").write("\n".join(["%s=%s" % (key, self.mapping[key]) for key in sorted(self.mapping.iterkeys())]))
                self.close()
    def close(self):
        del self.srv_com
        if self.socket:
            self.socket.close()
            id_discovery.relayer_process.unregister_poller(self.socket, zmq.POLLIN)
            del self.socket
        if self.conn_str in id_discovery.pending:
            # remove from pending dict
            del id_discovery.pending[self.conn_str]
        self.log("closing")
        del self
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        id_discovery.relayer_process.log("[idd, %s] %s" % (self.conn_str, what), log_level)
    @staticmethod
    def init(r_process, backlog_size, timeout, verbose):
        id_discovery.relayer_process = r_process
        id_discovery.backlog_size = backlog_size
        id_discovery.timeout = timeout
        id_discovery.verbose = verbose
        id_discovery.reverse_mapping = {}
        # mapping connection string -> 0MQ id
        if os.path.isfile(MAPPING_FILE_IDS):
            id_discovery.mapping = dict([line.strip().split("=", 1) for line in file(MAPPING_FILE_IDS, "r").read().split("\n") if line.strip() and line.count("=")])
            id_discovery.relayer_process.log(
                "read %s from %s" % (
                    logging_tools.get_plural("mapping", len(id_discovery.mapping)),
                    MAPPING_FILE_IDS))
            for key, value in id_discovery.mapping.iteritems():
                # only use ip-address / hostname from key
                id_discovery.reverse_mapping.setdefault(value, []).append(key[6:].split(":")[0])
            # pprint.pprint(id_discovery.reverse_mapping)
        else:
            id_discovery.mapping = {}
        id_discovery.pending = {}
        # last discovery try
        id_discovery.last_try = {}
    @staticmethod
    def destroy():
        for value in list(id_discovery.pending.values()):
            value.close()
    @staticmethod
    def set_mapping(conn_str, uuid):
        id_discovery.mapping[conn_str] = uuid
    @staticmethod
    def is_pending(conn_str):
        return conn_str in id_discovery.pending
    @staticmethod
    def has_mapping(conn_str):
        return conn_str in id_discovery.mapping
    @staticmethod
    def get_mapping(conn_str):
        return id_discovery.mapping[conn_str]
    @staticmethod
    def check_timeout(cur_time):
        del_list = []
        for conn_str, cur_ids in id_discovery.pending.iteritems():
            diff_time = abs(cur_ids.init_time - cur_time)
            if diff_time > id_discovery.timeout:
                del_list.append(cur_ids)
        for cur_ids in del_list:
            # set last try flag
            id_discovery.last_try[cur_ids.conn_str] = cur_time
            cur_ids.send_return("timeout triggered, closing")

class sr_probe(object):
    def __init__(self, host_con):
        self.host_con = host_con
        self.__val = {"send" : 0,
                      "recv" : 0}
        self.__time = time.time()
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.host_con.log("[probe for %s] %s" % (self.host_con.conn_str, what), log_level)
    @property
    def send(self):
        return self.__val["send"]
    @send.setter
    def send(self, val):
        cur_time = time.time()
        diff_time = abs(cur_time - self.__time)
        if  diff_time > 30 * 60:
            self.log("sent / received in %s: %s / %s" % (
                logging_tools.get_diff_time_str(diff_time),
                logging_tools.get_size_str(self.__val["send"]),
                logging_tools.get_size_str(self.__val["recv"]),
            ))
            self.__time = cur_time
            self.__val = {"send" : 0,
                          "recv" : 0}
        self.__val["send"] += val
    @property
    def recv(self):
        return self.__val["recv"]
    @recv.setter
    def recv(self, val):
        self.__val["recv"] += val

class host_connection(object):
    def __init__(self, conn_str, **kwargs):
        self.zmq_id = kwargs.get("zmq_id", "ms")
        self.tcp_con = kwargs.get("dummy_connection", False)
        host_connection.hc_dict[(not self.tcp_con, conn_str)] = self
        self.sr_probe = sr_probe(self)
        self.__open = False
        self.__conn_str = conn_str
    @property
    def conn_str(self):
        return self.__conn_str
    def close(self):
        pass
    def __del__(self):
        pass
    @staticmethod
    def init(r_process, backlog_size, timeout, verbose):
        host_connection.relayer_process = r_process
        host_connection.messages = {}
        # 2 queues for 0MQ and tcp, 0MQ is (True, conn_str), TCP is (False, conn_str)
        host_connection.hc_dict = {}
        host_connection.backlog_size = backlog_size
        host_connection.timeout = timeout
        host_connection.verbose = verbose
        # rotuer socket
        new_sock = host_connection.relayer_process.zmq_context.socket(zmq.ROUTER)
        id_str = "relayer_rtr_%s" % (process_tools.get_machine_name())
        new_sock.setsockopt(zmq.IDENTITY, id_str)
        new_sock.setsockopt(zmq.LINGER, 0)
        new_sock.setsockopt(zmq.SNDHWM, host_connection.backlog_size)
        new_sock.setsockopt(zmq.RCVHWM, host_connection.backlog_size)
        new_sock.setsockopt(zmq.RECONNECT_IVL_MAX, 500)
        new_sock.setsockopt(zmq.RECONNECT_IVL, 200)
        new_sock.setsockopt(zmq.BACKLOG, host_connection.backlog_size)
        new_sock.setsockopt(zmq.TCP_KEEPALIVE, 1)
        new_sock.setsockopt(zmq.TCP_KEEPALIVE_IDLE, 300)
        host_connection.zmq_socket = new_sock
        host_connection.relayer_process.register_poller(new_sock, zmq.POLLIN, host_connection.get_result)
        # host_connection.relayer_process.register_poller(new_sock, zmq.POLLERR, host_connection.error)
    @staticmethod
    def get_hc_0mq(conn_str, target_id="ms", **kwargs):
        if (True, conn_str) not in host_connection.hc_dict:
            if host_connection.verbose > 1:
                host_connection.relayer_process.log("new 0MQ host_connection for '%s'" % (conn_str))
            cur_hc = host_connection(conn_str, zmq_id=target_id, **kwargs)
        else:
            cur_hc = host_connection.hc_dict[(True, conn_str)]
        return cur_hc
    @staticmethod
    def get_hc_tcp(conn_str, **kwargs):
        if (False, conn_str) not in host_connection.hc_dict:
            if host_connection.verbose > 1:
                host_connection.relayer_process.log("new TCP host_connection for '%s'" % (conn_str))
            cur_hc = host_connection(conn_str, **kwargs)
        else:
            cur_hc = host_connection.hc_dict[(False, conn_str)]
        return cur_hc
    @staticmethod
    def check_timeout_g():
        cur_time = time.time()
        id_discovery.check_timeout(cur_time)
        [cur_hc.check_timeout(cur_time) for cur_hc in host_connection.hc_dict.itervalues()]
    @staticmethod
    def global_close():
        host_connection.zmq_socket.close()
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        host_connection.relayer_process.log("[hc] %s" % (what), log_level)
    def check_timeout(self, cur_time):
        to_messages = [cur_mes for cur_mes in self.messages.itervalues() if cur_mes.check_timeout(cur_time, host_connection.timeout)]
        if to_messages:
            # print "TO", len(to_messages), self.__conn_str
            for to_mes in to_messages:
                if not self.tcp_con:
                    pass
                    # self.__backlog_counter -= 1
                self.return_error(to_mes, "timeout (after %.2f seconds)" % (to_mes.get_runtime(cur_time)))
    def _open(self):
        if not self.__open:
            try:
                self.log("connecting to %s" % (self.__conn_str))
                host_connection.zmq_socket.connect(self.__conn_str)
            except:
                raise
            else:
                self.__open = True
                # make a short nap to let 0MQ settle things down
                time.sleep(0.2)
        return self.__open
    def _close(self):
        if self.__open:
            host_connection.zmq_socket.close()
            self.__open = False
    @staticmethod
    def add_message(new_mes):
        host_connection.messages[new_mes.src_id] = new_mes
        return new_mes
    def send(self, host_mes, com_struct):
        try:
            host_mes.set_com_struct(com_struct)
        except:
            self.return_error(
                host_mes,
                "error parsing arguments: %s" % (process_tools.get_except_info()))
        else:
            if not self.tcp_con:
                try:
                    self._open()
                except:
                    self.return_error(
                        host_mes,
                        "error connecting to %s: %s" % (self.__conn_str,
                                                        process_tools.get_except_info()))
                else:
                    if False and self.__backlog_counter == host_connection.backlog_size:
                        # no stupid backlog counting
                        self.return_error(
                            host_mes,
                            "connection error (backlog full [%d.%d]) for '%s'" % (
                                self.__backlog_counter,
                                host_connection.backlog_size,
                                self.__conn_str))
                        # self._close()
                    else:
                        try:
                            host_connection.zmq_socket.send_unicode(self.zmq_id, zmq.DONTWAIT | zmq.SNDMORE)
                            send_str = unicode(host_mes.srv_com)
                            host_connection.zmq_socket.send_unicode(send_str, zmq.DONTWAIT)
                        except:
                            self.return_error(
                                host_mes,
                                "connection error (%s)" % (process_tools.get_except_info()),
                            )
                        else:
                            # self.__backlog_counter += 1
                            self.sr_probe.send = len(send_str)
                            host_mes.sr_probe = self.sr_probe
                            host_mes.sent = True
            else:
                # send to twisted-thread for old clients
                host_connection.relayer_process.send_to_process(
                    "twisted",
                    "connection",
                    host_mes.src_id,
                    unicode(host_mes.srv_com))
    def send_result(self, host_mes, result=None):
        host_connection.relayer_process.sender_socket.send_unicode(host_mes.src_id, zmq.SNDMORE)
        host_connection.relayer_process.sender_socket.send_unicode(host_mes.get_result(result))
        del host_connection.messages[host_mes.src_id]
        del host_mes
    @staticmethod
    def _send_result(host_mes, result=None):
        host_connection.relayer_process.sender_socket.send_unicode(host_mes.src_id, zmq.SNDMORE)
        host_connection.relayer_process.sender_socket.send_unicode(host_mes.get_result(result))
        del host_connection.messages[host_mes.src_id]
        del host_mes
    def return_error(self, host_mes, error_str):
        host_mes.set_result(limits.nag_STATE_CRITICAL, error_str)
        self.send_result(host_mes)
    def _error(self, zmq_sock):
        # not needed right now
        print "**** _error", zmq_sock
        print dir(zmq_sock)
        print zmq_sock.getsockopt(zmq.EVENTS)
        # self._close()
        # raise zmq.ZMQError()
    @staticmethod
    def get_result(zmq_sock):
        src_id = zmq_sock.recv()
        cur_reply = server_command.srv_command(source=zmq_sock.recv())
        host_connection._handle_result(cur_reply)
    @staticmethod
    def _handle_result(result):
        # print unicode(result)
        mes_id = result["relayer_id"].text
        if mes_id in host_connection.messages:
            host_connection.relayer_process._new_client(result["host"].text, int(result["port"].text))
            if "host_unresolv" in result:
                host_connection.relayer_process._new_client(result["host_unresolved"].text, int(result["port"].text))
            cur_mes = host_connection.messages[mes_id]
            if cur_mes.sent:
                cur_mes.sent = False
                # self.__backlog_counter -= 1
            if len(result.xpath(None, ".//ns:raw")):
                # raw response, no interpret
                cur_mes.srv_com = result
                host_connection._send_result(cur_mes, None)
                # self.send_result(cur_mes, None)
            else:
                try:
                    res_tuple = cur_mes.interpret(result)
                except:
                    res_tuple = (
                        limits.nag_STATE_CRITICAL,
                        "error interpreting result: %s" % (
                            process_tools.get_except_info()))
                    exc_info = process_tools.exception_info()
                    for line in exc_info.log_lines:
                        host_connection.relayer_process.log(line, logging_tools.LOG_LEVEL_CRITICAL)
                host_connection._send_result(cur_mes, res_tuple)
                # self.send_result(cur_mes, res_tuple)
        else:
            # FIXME
            # print "ID", mes_id
            # print self.log("unknown id '%s' in _handle_result" % (mes_id), logging_tools.LOG_LEVEL_ERROR)
            pass
    def _handle_old_result(self, mes_id, result):
        if mes_id in host_connection.messages:
            cur_mes = host_connection.messages[mes_id]
            if result.startswith("no valid"):
                res_tuple = (limits.nag_STATE_CRITICAL, result)
            else:
                host_connection.relayer_process._old_client(cur_mes.srv_com["host"].text, int(cur_mes.srv_com["port"].text))
                try:
                    res_tuple = cur_mes.interpret_old(result)
                except:
                    res_tuple = (limits.nag_STATE_CRITICAL, "error interpreting result: %s" % (process_tools.get_except_info()))
            self.send_result(cur_mes, res_tuple)
        else:
            self.log("unknown id '%s' in _handle_old_result" % (mes_id), logging_tools.LOG_LEVEL_ERROR)

class host_message(object):
    def __init__(self, com_name, src_id, srv_com, xml_input):
        self.com_name = com_name
        self.src_id = src_id
        self.xml_input = xml_input
        self.srv_com = srv_com
        self.timeout = int(srv_com.get("timeout", "10"))
        self.srv_com["relayer_id"] = self.src_id
        self.s_time = time.time()
        self.sent = False
        self.sr_probe = None
    def set_result(self, state, res_str):
        self.srv_com["result"] = None
        self.srv_com["result"].attrib.update({"reply" : res_str,
                                              "state" : "%d" % (state)})
    def set_com_struct(self, com_struct):
        self.com_struct = com_struct
        if com_struct:
            cur_ns, rest = com_struct.handle_commandline((self.srv_com["arg_list"].text or "").split())
            # print "***", cur_ns, rest
            self.srv_com["arg_list"] = " ".join(rest)
            self.srv_com.delete_subtree("arguments")
            for arg_idx, arg in enumerate(rest):
                self.srv_com["arguments:arg%d" % (arg_idx)] = arg
            self.srv_com["arguments:rest"] = " ".join(rest)
            self.ns = cur_ns
        else:
            # connect to non-host-monitoring service
            self.srv_com["arguments:rest"] = self.srv_com["arg_list"].text
            self.ns = argparse.Namespace()
    def check_timeout(self, cur_time, to_value):
        return abs(cur_time - self.s_time) > max(to_value, self.timeout - 2)
    def get_runtime(self, cur_time):
        return abs(cur_time - self.s_time)
    def get_result(self, result):
        if result is None:
            result = self.srv_com
        if type(result) == type(()):
            # from interpret
            if not self.xml_input:
                ret_str = u"%d\0%s" % (result[0],
                                       result[1])
            else:
                # shortcut
                self.set_result(result[0], result[1])
                ret_str = unicode(self.srv_com)
        else:
            if not self.xml_input:
                ret_str = u"%s\0%s" % (result["result"].attrib["state"],
                                       result["result"].attrib["reply"])
            else:
                ret_str = unicode(result)
        return ret_str
    def interpret(self, result):
        if self.sr_probe:
            self.sr_probe.recv = len(result)
            self.sr_probe = None
        server_error = result.xpath(None, ".//ns:result[@state != '0']")
        if server_error:
            return (int(server_error[0].attrib["state"]),
                    server_error[0].attrib["reply"])
        else:
            return self.com_struct.interpret(result, self.ns)
    def interpret_old(self, result):
        if type(result) not in [str, unicode]:
            server_error = result.xpath(None, ".//ns:result[@state != '0']")
        else:
            server_error = None
        if server_error:
            return (int(server_error[0].attrib["state"]),
                    server_error[0].attrib["reply"])
        else:
            if result.startswith("error "):
                return (limits.nag_STATE_CRITICAL,
                        result)
            else:
                # copy host, hacky hack
                self.com_struct.NOGOOD_srv_com = self.srv_com
                ret_value = self.com_struct.interpret_old(result, self.ns)
                del self.com_struct.NOGOOD_srv_com
                return ret_value
    def __del__(self):
        del self.srv_com
        pass

class relay_code(threading_tools.process_pool):
    def __init__(self):
        # monkey path process tools to allow consistent access
        process_tools.ALLOW_MULTIPLE_INSTANCES = False
        # copy to access from modules
        from initat.host_monitoring import modules
        self.modules = modules
        self.global_config = global_config
        self.__verbose = global_config["VERBOSE"]
        self.__autosense = global_config["AUTOSENSE"]
        self.__log_cache, self.__log_template = ([], None)
        threading_tools.process_pool.__init__(self, "main", zmq=True, zmq_debug=global_config["ZMQ_DEBUG"])
        self.renice(global_config["NICE_LEVEL"])
        # pending_connection.init(self)
        self.__global_timeout = global_config["TIMEOUT"]
        host_connection.init(self, global_config["BACKLOG_SIZE"], self.__global_timeout, self.__verbose)
        # init lut
        self.__old_send_lut = {}
        if not global_config["DEBUG"]:
            c_flag, self.__io_dict = process_tools.set_handles(
                {"out" : (1, "collrelay.out"),
                 "err" : (0, "/var/lib/logging-server/py_err_zmq")},
                zmq_context=self.zmq_context,
                ext_return=True)
        else:
            self.__io_dict = None
        # we need no icmp capability in relaying
        self.add_process(twisted_process("twisted", icmp=False), twisted=True, start=True)
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context)
        self.install_signal_handlers()
        id_discovery.init(self, global_config["BACKLOG_SIZE"], global_config["TIMEOUT"], self.__verbose)
        self._init_filecache()
        self._init_master()
        self._init_msi_block()
        self._change_rlimits()
        self._init_network_sockets()
        self._init_ipc_sockets()
        self.register_exception("int_error" , self._sigint)
        self.register_exception("term_error", self._sigint)
        self.register_exception("hup_error", self._hup_error)
        self.__delayed = []
        self.register_timer(self._check_timeout, 2)
        self.register_func("twisted_result", self._twisted_result)
        self.version_dict = {}
        self._show_config()
        if not self._init_commands():
            self._sigint("error init")
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        if self.__log_template:
            while self.__log_cache:
                self.__log_template.log(*self.__log_cache.pop(0))
            self.__log_template.log(lev, what)
        else:
            self.__log_cache.append((lev, what))
    def _sigint(self, err_cause):
        if self["exit_requested"]:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            self["exit_requested"] = True
    def _hup_error(self, err_cause):
        self.log("got SIGHUP (%s), setting all clients with connmode TCP to unknown" % (err_cause), logging_tools.LOG_LEVEL_WARN)
        num_c = 0
        for t_host, c_state in self.__client_dict.iteritems():
            if c_state == "T":
                self.__client_dict[t_host] = None
                num_c += 1
        self.log("cleared %s" % (logging_tools.get_plural("state", num_c)))
    def _change_rlimits(self):
        for limit_name in ["OFILE"]:
            res = getattr(resource, "RLIMIT_%s" % (limit_name))
            soft, hard = resource.getrlimit(res)
            if soft < hard:
                self.log("changing ulimit of %s from %d to %d" % (
                    limit_name,
                    soft,
                    hard,
                    ))
                try:
                    resource.setrlimit(res, (hard, hard))
                except:
                    self.log("cannot alter ulimit: %s" % (process_tools.get_except_info()),
                        logging_tools.LOG_LEVEL_CRITICAL,
                        )
        # try:
        #    resource.setrlimit(resource.RLIMIT_OFILE, 4069)
    def _init_master(self):
        if os.path.isfile(MASTER_FILE_NAME):
            master_xml = etree.fromstring(file(MASTER_FILE_NAME, "r").read())
            self._register_master(master_xml.attrib["ip"], master_xml.attrib["uuid"], int(master_xml.attrib["port"]), write=False)
        else:
            self.log("no master_file found", logging_tools.LOG_LEVEL_WARN)
            self.master_ip = None
            self.master_port = None
            self.master_uuid = None
    def _register_master(self, master_ip, master_uuid, master_port, write=True):
        self.master_ip = master_ip
        self.master_uuid = master_uuid
        self.master_port = master_port
        if write:
            file(MASTER_FILE_NAME, "w").write(etree.tostring(
                E.master_data(
                    ip=self.master_ip,
                    uuid=self.master_uuid,
                    port="%d" % (self.master_port)
                )
                , pretty_print=True))
        conn_str = "tcp://%s:%d" % (self.master_ip, self.master_port)
        self.log("registered master at %s (%s)" % (conn_str, self.master_uuid))
        id_discovery.set_mapping(conn_str, self.master_uuid)
    def _init_filecache(self):
        self.__client_dict = {}
        self.__last_tried = {}
        if not self.__autosense:
            self.__new_clients, self.__old_clients = (
                my_cached_file("/tmp/.new_clients", log_handle=self.log),
                my_cached_file("/tmp/.old_clients", log_handle=self.log))
        else:
            if os.path.isfile(MAPPING_FILE_TYPES):
                self.__client_dict.update(dict([(key, "0") for key in file(MAPPING_FILE_TYPES, "r").read().split("\n") if key.strip()]))
        self.__default_0mq = False
    def _new_client(self, c_ip, c_port):
        self._set_client_state(c_ip, c_port, "0")
    def _old_client(self, c_ip, c_port):
        self._set_client_state(c_ip, c_port, "T")
    def _set_client_state(self, c_ip, c_port, c_type):
        write_file = False
        if self.__autosense:
            check_names = [c_ip]
            if c_ip in self.__ip_lut:
                real_name = self.__ip_lut[c_ip]
                if real_name != c_ip:
                    check_names.append(real_name)
            for c_name in check_names:
                if self.__client_dict.get(c_name, None) != c_type and c_port == 2001:
                    self.log("setting client '%s:%d' to '%s'" % (c_name, c_port, c_type))
                    self.__client_dict[c_name] = c_type
                    write_file = True
        if write_file:
            file(MAPPING_FILE_TYPES, "w").write("\n".join([key for key, value in self.__client_dict.iteritems() if value == "0"]))
    def _init_msi_block(self):
        # store pid name because global_config becomes unavailable after SIGTERM
        self.__pid_name = global_config["PID_NAME"]
        process_tools.save_pids(global_config["PID_NAME"], mult=3)
        process_tools.append_pids(global_config["PID_NAME"], pid=configfile.get_manager_pid(), mult=3)
        if True:
            self.log("Initialising meta-server-info block")
            msi_block = process_tools.meta_server_info("collrelay")
            msi_block.add_actual_pid(mult=3)
            msi_block.add_actual_pid(act_pid=configfile.get_manager_pid(), mult=3)
            msi_block.start_command = "/etc/init.d/host-relay start"
            msi_block.stop_command = "/etc/init.d/host-relay force-stop"
            msi_block.kill_pids = True
            # msi_block.heartbeat_timeout = 60
            msi_block.save_block()
        else:
            msi_block = None
        self.__msi_block = msi_block
    def process_start(self, src_process, src_pid):
        # twisted needs 4 threads if connecting to TCP clients, 3 if not (???)
        if src_process == "twisted":
            if src_pid in self.__msi_block.get_pids():
                # add one extra thread
                mult = 1
            else:
                mult = 3
        else:
            mult = 3
        process_tools.append_pids(self.__pid_name, src_pid, mult=mult)
        if self.__msi_block:
            self.__msi_block.add_actual_pid(src_pid, mult=mult)
            self.__msi_block.save_block()
    def _check_timeout(self):
        host_connection.check_timeout_g()
        # check nhm timeouts
        cur_time = time.time()
        del_list = []
        for key, value in self.__nhm_dict.iteritems():
            if abs(value[0] - cur_time) > self.__global_timeout:
                del_list.append(key)
                self._send_result(value[1]["identity"].text,
                                  "error timeout",
                                  server_command.SRV_REPLY_STATE_ERROR)
        if del_list:
            self.log("removing %s: %s" % (logging_tools.get_plural("nhm key", len(del_list)),
                                          ", ".join(sorted(del_list))),
                     logging_tools.LOG_LEVEL_ERROR)
            for key in del_list:
                del self.__nhm_dict[key]
        # check delayed
        cur_time = time.time()
        new_list = []
        if self.__delayed:
            self.log("%s in delayed queue" % (logging_tools.get_plural("object", len(self.__delayed))))
            for cur_del in self.__delayed:
                if cur_del.Meta.use_popen:
                    if cur_del.finished():
                        # print "finished delayed"
                        cur_del.send_return()
                    elif abs(cur_time - cur_del._init_time) > cur_del.Meta.max_runtime:
                        self.log("delay_object runtime exceeded, stopping")
                        cur_del.terminate()
                        cur_del.send_return()
                    else:
                        new_list.append(cur_del)
                else:
                    if not cur_del.terminated:
                        new_list.append(cur_del)
            self.__delayed = new_list
    def _twisted_result(self, src_proc, proc_id, src_id, srv_com, data_str):
        if src_id in self.__old_send_lut:
            self.__old_send_lut.pop(src_id)._handle_old_result(src_id, data_str)
        else:
            self.log("result for non-existing id '%s' received, discarding" % (src_id),
                     logging_tools.LOG_LEVEL_ERROR)
    def send_result(self, src_id, ret_str):
        self.sender_socket.send_unicode(src_id, zmq.SNDMORE)
        self.sender_socket.send_unicode(ret_str)
    def _init_ipc_sockets(self):
        # init IP lookup table
        self.__ip_lut = {}
        self.__forward_lut = {}
        self.__num_messages = 0
        # nhm (not host monitoring) dictionary for timeout
        self.__nhm_dict = {}
        self.__nhm_connections = set()
        sock_list = [("ipc", "receiver", zmq.PULL, 2),
                     ("ipc", "sender"  , zmq.PUB , 1024)]
        [setattr(self, "%s_socket" % (short_sock_name), None) for sock_proto, short_sock_name, a0, b0 in sock_list]
        for sock_proto, short_sock_name, sock_type, hwm_size in sock_list:
            sock_name = process_tools.get_zmq_ipc_name(short_sock_name)
            file_name = sock_name[5:]
            self.log("init %s ipc_socket '%s' (HWM: %d)" % (short_sock_name, sock_name,
                                                            hwm_size))
            if os.path.exists(file_name):
                self.log("removing previous file")
                try:
                    os.unlink(file_name)
                except:
                    self.log("... %s" % (process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
            wait_iter = 0
            while os.path.exists(file_name) and wait_iter < 100:
                self.log("socket %s still exists, waiting" % (sock_name))
                time.sleep(0.1)
                wait_iter += 1
            cur_socket = self.zmq_context.socket(sock_type)
            try:
                process_tools.bind_zmq_socket(cur_socket, sock_name)
                # client.bind("tcp://*:8888")
            except zmq.core.error.ZMQError:
                self.log("error binding %s: %s" % (
                    short_sock_name,
                    process_tools.get_except_info()),
                         logging_tools.LOG_LEVEL_CRITICAL)
                raise
            else:
                setattr(self, "%s_socket" % (short_sock_name), cur_socket)
                backlog_size = global_config["BACKLOG_SIZE"]
                os.chmod(file_name, 0777)
                cur_socket.setsockopt(zmq.LINGER, 0)
                cur_socket.setsockopt(zmq.SNDHWM, hwm_size)
                cur_socket.setsockopt(zmq.RCVHWM, hwm_size)
                if sock_type == zmq.PULL:
                    self.register_poller(cur_socket, zmq.POLLIN, self._recv_command)
        self.client_socket = self.zmq_context.socket(zmq.ROUTER)
        self.client_socket.setsockopt(zmq.IDENTITY, "ccollclient:%s" % (process_tools.get_machine_name()))
        self.client_socket.setsockopt(zmq.LINGER, 0)
        self.client_socket.setsockopt(zmq.SNDHWM, 2)
        self.client_socket.setsockopt(zmq.RCVHWM, 2)
        self.client_socket.setsockopt(zmq.TCP_KEEPALIVE, 1)
        self.client_socket.setsockopt(zmq.TCP_KEEPALIVE_IDLE, 300)
        self.register_poller(self.client_socket, zmq.POLLIN, self._recv_nhm_result)
    def _init_network_sockets(self):
        client = self.zmq_context.socket(zmq.ROUTER)
        uuid = "%s:relayer" % (uuid_tools.get_uuid().get_urn())
        client.setsockopt(zmq.IDENTITY, uuid)
        client.setsockopt(zmq.SNDHWM, 10)
        client.setsockopt(zmq.RCVHWM, 10)
        client.setsockopt(zmq.RECONNECT_IVL_MAX, 500)
        client.setsockopt(zmq.RECONNECT_IVL, 200)
        client.setsockopt(zmq.TCP_KEEPALIVE, 1)
        client.setsockopt(zmq.TCP_KEEPALIVE_IDLE, 300)
        conn_str = "tcp://*:%d" % (
            global_config["COM_PORT"])
        try:
            client.bind(conn_str)
        except zmq.core.error.ZMQError:
            self.log("error binding to *:%d: %s" % (
                global_config["COM_PORT"],
                process_tools.get_except_info()),
                     logging_tools.LOG_LEVEL_CRITICAL)
            client.close()
            self.network_socket = None
        else:
            self.log("bound to %s (ID %s)" % (conn_str, uuid))
            self.register_poller(client, zmq.POLLIN, self._recv_command)
            self.network_socket = client
    def _resolve_address(self, target):
        # to avoid loops in the 0MQ connection scheme (will result to nasty asserts)
        if target in self.__forward_lut:
            ip_addr = self.__forward_lut[target]
        else:
            orig_target = target
            if target.lower() in ["localhost", "127.0.0.1", "localhost.localdomain"]:
                # map localhost to something 0MQ can handle
                target = process_tools.get_machine_name()
            # step 1: resolve to ip
            try:
                ip_addr = socket.gethostbyname(target)
            except:
                self.log("cannot resolve target '%s': %s" % (
                    target,
                    process_tools.get_except_info()),
                         logging_tools.LOG_LEVEL_CRITICAL)
                raise
            try:
                # step 2: try to get full name
                full_name, aliases, ip_addrs = socket.gethostbyaddr(ip_addr)
            except:
                # forget it
                pass
            else:
                # resolve full name
                self.log("ip_addr %s resolved to '%s' (%s), %s" % (ip_addr, full_name, ", ".join(aliases) or "N/A", ", ".join(ip_addrs) or "N/A"))
                try:
                    new_ip_addr = socket.gethostbyname(full_name)
                except:
                    self.log("cannot resolve full_name '%s': %s" % (
                        full_name,
                        process_tools.get_except_info()),
                             logging_tools.LOG_LEVEL_CRITICAL)
                    raise
                else:
                    self.log("full_name %s resolves back to %s (was: %s)" % (
                        full_name,
                        new_ip_addr,
                        ip_addr),
                             logging_tools.LOG_LEVEL_OK if new_ip_addr == ip_addr else logging_tools.LOG_LEVEL_ERROR)
                    # should we use the new ip_addr ? dangerous, FIXME
                    # ip_addr = new_ip_addr
            if ip_addr not in self.__ip_lut:
                self.log("resolved %s to %s" % (target, ip_addr))
                self.__ip_lut[ip_addr] = target
            self.__forward_lut[target] = ip_addr
            self.log("ip resolving: %s -> %s" % (target, ip_addr))
            if orig_target != target:
                self.__forward_lut[orig_target] = ip_addr
                self.log("ip resolving: %s -> %s" % (orig_target, ip_addr))
        return ip_addr
    def _recv_command(self, zmq_sock):
        data = zmq_sock.recv()
        if zmq_sock.getsockopt(zmq.RCVMORE):
            src_id = data
            data = zmq_sock.recv()
        else:
            src_id = None
        xml_input = data.startswith("<")
        srv_com = None
        if xml_input:
            srv_com = server_command.srv_command(source=data)
            if src_id is None:
                src_id = srv_com["identity"].text
            else:
                srv_com["identity"] = src_id
        else:
            if data.count(";") > 1:
                if data.startswith(";"):
                    # new format
                    proto_version, data = data[1:].split(";", 1)
                else:
                    proto_version, data = ("0", data)
                proto_version = int(proto_version)
                if proto_version == 0:
                    parts = data.split(";", 3)
                    # insert default timeout of 10 seconds
                    parts.insert(3, "10")
                else:
                    parts = data.split(";", 4)
                src_id = parts.pop(0)
                # parse new format
                if parts[3].endswith(";"):
                    com_part = parts[3][:-1]
                else:
                    com_part = parts[3]
                # iterative parser
                try:
                    arg_list = []
                    while com_part.count(";"):
                        cur_size, cur_str = com_part.split(";", 1)
                        cur_size = int(cur_size)
                        com_part = cur_str[cur_size + 1:]
                        arg_list.append(cur_str[:cur_size].decode("utf-8"))
                    if com_part:
                        raise ValueError, "not fully parsed (%s)" % (com_part)
                    else:
                        cur_com = arg_list.pop(0) if arg_list else ""
                        srv_com = server_command.srv_command(command=cur_com, identity=src_id)
                        srv_com["host"] = parts[0]
                        srv_com["port"] = parts[1]
                        srv_com["timeout"] = parts[2]
                        for arg_index, arg in enumerate(arg_list):
                            srv_com["arguments:arg%d" % (arg_index)] = arg
                        srv_com["arg_list"] = " ".join(arg_list)
                except:
                    self.log("error parsing %s" % (data), logging_tools.LOG_LEVEL_ERROR)
                    srv_com = None
        if srv_com is not None:
            if self.__verbose:
                self.log("got command '%s' for '%s' (XML: %s)" % (
                    srv_com["command"].text,
                    srv_com["host"].text,
                    str(xml_input)))
            if "host" in srv_com and "port" in srv_com:
                # check target host, rewrite to ip
                t_host = srv_com["host"].text
                if t_host == "DIRECT":
                    self._handle_direct_command(src_id, srv_com)
                else:
                    try:
                        ip_addr = self._resolve_address(t_host)
                    except socket.gaierror:
                        self.log("resolve error for '%s'" % (t_host),
                                 logging_tools.LOG_LEVEL_ERROR)
                        self.sender_socket.send_unicode(src_id, zmq.SNDMORE)
                        self.sender_socket.send_unicode("%d\0resolve error" % (limits.nag_STATE_CRITICAL))
                    else:
                        srv_com["host_unresolved"] = t_host
                        srv_com["host"] = ip_addr
                        if self.__autosense:
                            # try to get the state of both addresses
                            c_state = self.__client_dict.get(t_host, self.__client_dict.get(ip_addr, None))
                            if c_state is None:
                                # not needed
                                # host_connection.delete_hc(srv_com)
                                if t_host not in self.__last_tried:
                                    self.__last_tried[t_host] = "T" if self.__default_0mq else "0"
                                self.__last_tried[t_host] = {
                                    "T" : "0",
                                    "0" : "T"}[self.__last_tried[t_host]]
                                c_state = self.__last_tried[t_host]
                            con_mode = c_state
                            # con_mode = "0"
                        else:
                            self.__old_clients.update()
                            self.__new_clients.update()
                            if t_host in self.__new_clients:
                                con_mode = "0"
                            elif t_host in self.__old_clients:
                                con_mode = "T"
                            elif self.__default_0mq:
                                con_mode = "0"
                            else:
                                con_mode = "T"
                        # decide which code to use
                        if self.__verbose:
                            self.log("connection to '%s:%d' via %s" % (t_host,
                                                                       int(srv_com["port"].text),
                                                                       con_mode))
                        if int(srv_com["port"].text) != 2001:
                            # connect to non-host-monitoring service
                            if con_mode == "0":
                                self._send_to_nhm_service(src_id, srv_com, xml_input)
                            else:
                                self._send_to_old_nhm_service(src_id, srv_com, xml_input)
                        elif con_mode == "0":
                            self._send_to_client(src_id, srv_com, xml_input)
                        elif con_mode == "T":
                            self._send_to_old_client(src_id, srv_com, xml_input)
                        else:
                            self.log("unknown con_mode '%s', error" % (con_mode),
                                     logging_tools.LOG_LEVEL_CRITICAL)
                        if self.__verbose:
                            self.log("send done")
            else:
                self.log("some keys missing (host and / or port)",
                         logging_tools.LOG_LEVEL_ERROR)
        else:
            self.log("cannot interpret input data '%s' as srv_command" % (data),
                     logging_tools.LOG_LEVEL_ERROR)
            # return a dummy message
            self._send_result(src_id, "cannot interpret", limits.nag_STATE_CRITICAL)
        self.__num_messages += 1
        if self.__num_messages % 1000 == 0:
            cur_mem = process_tools.get_mem_info()
            self.log("memory usage is %s after %s" % (
                logging_tools.get_size_str(cur_mem),
                logging_tools.get_plural("message", self.__num_messages)))
    def _check_version(self, key, new_vers):
        if new_vers == self.version_dict.get(key):
            self.log("no newer version for %s (%d)" % (key, new_vers))
            return False
        else:
            self.log("newer version for %s (%d -> %d)" % (key, self.version_dict.get(key, 0), new_vers))
            self.version_dict[key] = new_vers
            return True
    def _handle_direct_command(self, src_id, srv_com):
        # only DIRECT command from ccollclientzmq
        # print "*", src_id
        cur_com = srv_com["command"].text
        send_return = False
        if self.__verbose:
            self.log("got DIRECT command %s" % (cur_com))
        if cur_com == "file_content":
            t_file = srv_com["file_name"].text
            new_vers = int(srv_com["version"].text)
            ret_com = server_command.srv_command(
                command="file_content_result",
                version="%d" % (new_vers),
                slave_name=srv_com["slave_name"].text,
                file_name=t_file,
            )
            ret_com["result"] = None
            if self._check_version(t_file, new_vers):
                content = base64.b64decode(srv_com["content"].text)
                t_dir = os.path.dirname(t_file)
                if not os.path.exists(t_dir):
                    try:
                        os.makedirs(t_dir)
                    except:
                        self.log("error creating directory %s: %s" % (t_dir, process_tools.get_except_info()),
                                 logging_tools.LOG_LEVEL_ERROR)
                    else:
                        self.log("created directory %s" % (t_dir))
                try:
                    file(t_file, "w").write(content)
                    os.chown(t_file, int(srv_com["uid"].text), int(srv_com["gid"].text))
                except:
                    self.log("error creating file %s: %s" % (
                        t_file,
                        process_tools.get_except_info()),
                             logging_tools.LOG_LEVEL_ERROR)
                    ret_com["result"].attrib.update({
                        "reply" : "file not created: %s" % (process_tools.get_except_info()),
                        "state" : "%d" % (logging_tools.LOG_LEVEL_ERROR)})
                else:
                    self.log("created %s (%d bytes)" % (
                        t_file,
                        len(content)))
                    ret_com["result"].attrib.update({
                        "reply" : "file created",
                        "state" : "%d" % (logging_tools.LOG_LEVEL_OK)})
            else:
                ret_com["result"].attrib.update({
                    "reply" : "file not newer",
                    "state" : "%d" % (logging_tools.LOG_LEVEL_WARN)})
            ret_com["host"] = self.master_ip
            ret_com["port"] = "%d" % (self.master_port)
            self._send_to_nhm_service(None, ret_com, None, register=False)
        elif cur_com == "call_command":
            # also check for version ? compare with file versions ? deleted files ? FIXME
            cmdline = srv_com["cmdline"].text
            self.log("got command '%s'" % (cmdline))
            new_ss = hm_classes.subprocess_struct(
                server_command.srv_command(command=cmdline, result="0"),
                cmdline,
                cb_func=self._ext_com_result)
            new_ss.run()
            self.__delayed.append(new_ss)
        elif cur_com == "register_master":
            self._register_master(srv_com["master_ip"].text,
                                  srv_com["identity"].text,
                                  int(srv_com["master_port"].text))
        else:
            # add cache ?
            srv_com["host"] = self.master_ip
            srv_com["port"] = "%d" % (self.master_port)
            self._send_to_nhm_service(None, srv_com, None, register=False)
            # we nerver send dummy returns, usefull with -s flag in ccollclientzmq
            # send_return = True
        # if send_return:
            # self._send_result(src_id, "processed direct command", server_command.SRV_REPLY_STATE_OK)
    def _ext_com_result(self, sub_s):
        self.log("external command gave:")
        for line_num, line in enumerate(sub_s.read().split("\n")):
            self.log(" %2d %s" % (line_num + 1, line))
    def _send_to_client(self, src_id, srv_com, xml_input):
        # generate new xml from srv_com
        conn_str = "tcp://%s:%d" % (srv_com["host"].text,
                                    int(srv_com["port"].text))
        if id_discovery.has_mapping(conn_str):
            id_str = id_discovery.get_mapping(conn_str)
            cur_hc = host_connection.get_hc_0mq(conn_str, id_str)
            com_name = srv_com["command"].text
            cur_mes = host_connection.add_message(host_message(com_name, src_id, srv_com, xml_input))
            if com_name in self.modules.command_dict:
                com_struct = self.modules.command_dict[srv_com["command"].text]
                # handle commandline
                cur_hc.send(cur_mes, com_struct)
            else:
                cur_hc.return_error(cur_mes, "command '%s' not defined on relayer" % (com_name))
        elif id_discovery.is_pending(conn_str):
            cur_hc = host_connection.get_hc_0mq(conn_str)
            com_name = srv_com["command"].text
            cur_mes = host_connection.add_message(host_message(com_name, src_id, srv_com, xml_input))
            cur_hc.return_error(cur_mes, "0mq discovery in progress")
        else:
            id_discovery(srv_com, src_id, xml_input)
    def _send_to_nhm_service(self, src_id, srv_com, xml_input, **kwargs):
        conn_str = "tcp://%s:%d" % (
            srv_com["host"].text,
            int(srv_com["port"].text))
        if id_discovery.has_mapping(conn_str):
            connected = conn_str in self.__nhm_connections
            # trigger id discovery
            if not connected:
                try:
                    self.client_socket.connect(conn_str)
                except:
                    self._send_result(src_id, "error connecting: %s" % (process_tools.get_except_info()), server_command.SRV_REPLY_STATE_CRITICAL)
                else:
                    self.log("connected ROUTER client to %s" % (conn_str))
                    connected = True
                    self.__nhm_connections.add(conn_str)
            if connected:
                try:
                    self.client_socket.send_unicode(id_discovery.get_mapping(conn_str), zmq.SNDMORE | zmq.DONTWAIT)
                    self.client_socket.send_unicode(unicode(srv_com), zmq.DONTWAIT)
                except:
                    self._send_result(src_id, "error sending to %s: %s" % (
                        conn_str,
                        process_tools.get_except_info()), server_command.SRV_REPLY_STATE_CRITICAL)
                else:
                    if kwargs.get("register", True):
                        self.__nhm_dict[srv_com["identity"].text] = (time.time(), srv_com)
        elif id_discovery.is_pending(conn_str):
            self._send_result(src_id, "0mq discovery in progress", server_command.SRV_REPLY_STATE_CRITICAL)
        else:
            id_discovery(srv_com, src_id, xml_input)
    def _send_result(self, identity, reply_str, reply_state):
        self.sender_socket.send_unicode(identity, zmq.SNDMORE)
        self.sender_socket.send_unicode("%d\0%s" % (reply_state,
                                                    reply_str))
    def _recv_nhm_result(self, zmq_sock):
        data = []
        while True:
            data.append(zmq_sock.recv())
            if not zmq_sock.getsockopt(zmq.RCVMORE):
                break
        if len(data) == 2:
            srv_result = server_command.srv_command(source=data[1])
            cur_id = srv_result["identity"].text
            if cur_id in self.__nhm_dict:
                del self.__nhm_dict[cur_id]
                self._send_result(cur_id,
                                  srv_result["result"].attrib["reply"],
                                  int(srv_result["result"].attrib["state"]))
            else:
                self.log("received nhm-result for unknown id '%s', ignoring" % (cur_id),
                         logging_tools.LOG_LEVEL_ERROR)
    def _send_to_old_client(self, src_id, srv_com, xml_input):
        conn_str = "tcp://%s:%d" % (srv_com["host"].text,
                                    int(srv_com["port"].text))
        cur_hc = host_connection.get_hc_tcp(conn_str, dummy_connection=True)
        com_name = srv_com["command"].text
        cur_mes = host_connection.add_message(host_message(com_name, src_id, srv_com, xml_input))
        if com_name in self.modules.command_dict:
            com_struct = self.modules.command_dict[com_name]
            cur_hc.send(cur_mes, com_struct)
            self.__old_send_lut[cur_mes.src_id] = cur_hc
        else:
            cur_hc.return_error(cur_mes, "command '%s' not defined on relayer" % (com_name))
    def _send_to_old_nhm_service(self, src_id, srv_com, xml_input):
        conn_str = "tcp://%s:%d" % (srv_com["host"].text,
                                    int(srv_com["port"].text))
        cur_hc = host_connection.get_hc_tcp(conn_str, dummy_connection=True)
        com_name = srv_com["command"].text
        cur_mes = host_connection.add_message(host_message(com_name, src_id, srv_com, xml_input))
        cur_hc.send(cur_mes, None)
        self.__old_send_lut[cur_mes.src_id] = cur_hc
    def _handle_module_command(self, srv_com):
        try:
            self.commands[srv_com["command"].text](srv_com)
        except:
            exc_info = process_tools.exception_info()
            for log_line in process_tools.exception_info().log_lines:
                self.log(log_line, logging_tools.LOG_LEVEL_ERROR)
                srv_com["result"] = None
                srv_com["result"].attrib.update({
                    "reply" : "caught server exception '%s'" % (process_tools.get_except_info()),
                    "state" : "%d" % (server_command.SRV_REPLY_STATE_CRITICAL)})
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
    def _close_ipc_sockets(self):
        if self.receiver_socket is not None:
            self.unregister_poller(self.receiver_socket, zmq.POLLIN)
            self.receiver_socket.close()
        if self.sender_socket is not None:
            self.sender_socket.close()
        if self.client_socket is not None:
            self.unregister_poller(self.client_socket, zmq.POLLIN)
            self.client_socket.close()
        host_connection.global_close()
    def _close_io_sockets(self):
        if self.__io_dict:
            for key, value in self.__io_dict.iteritems():
                if value["type"] == "s":
                    self.log("closing stream for %s" % (key))
                    value["handle"].close()
        if self.network_socket:
            self.network_socket.close()
    def loop_end(self):
        self._close_ipc_sockets()
        self._close_io_sockets()
        id_discovery.destroy()
        from initat.host_monitoring import modules
        for cur_mod in modules.module_list:
            cur_mod.close_module()
        process_tools.delete_pid(self.__pid_name)
        if self.__msi_block:
            self.__msi_block.remove_meta_block()
    def loop_post(self):
        self.__log_template.close()
    def _init_commands(self):
        self.log("init commands")
        self.module_list = self.modules.module_list
        self.commands = self.modules.command_dict
        self.log("modules import errors:", logging_tools.LOG_LEVEL_ERROR)
        for mod_name, com_name, error_str in self.modules.IMPORT_ERRORS:
            self.log("%-24s %-32s %s" % (mod_name.split(".")[-1], com_name, error_str), logging_tools.LOG_LEVEL_ERROR)
        _init_ok = True
        for call_name, add_self in [("register_server", True),
                                    ("init_module"    , False)]:
            for cur_mod in self.modules.module_list:
                if self.__verbose:
                    self.log("calling %s for module '%s'" % (call_name,
                                                             cur_mod.name))
                try:
                    if add_self:
                        getattr(cur_mod, call_name)(self)
                    else:
                        getattr(cur_mod, call_name)()
                except:
                    exc_info = process_tools.exception_info()
                    for log_line in exc_info.log_lines:
                        self.log(log_line, logging_tools.LOG_LEVEL_CRITICAL)
                    _init_ok = False
                    break
            if not _init_ok:
                break
        return _init_ok
