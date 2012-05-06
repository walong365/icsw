#!/usr/bin/python-init -Ot
# -*- coding: utf-8 -*-
#
# Copyright (C) 2011,2012 Andreas Lang-Nevyjel
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
""" host-monitoring, with 0MQ and twisted support """

from twisted.internet import reactor
from twisted.internet.protocol import ClientFactory, Protocol, DatagramProtocol
from twisted.python import log
import zmq
import sys
import os
import os.path
import socket
import time
import logging_tools
import process_tools
import mail_tools
import threading_tools
import configfile
import server_command
import stat
import net_tools
from host_monitoring import limits, hm_classes
import argparse
import icmp_twisted
import pprint
import uuid
import uuid_tools
import difflib
from lxml import etree
from lxml.builder import E
import netifaces

try:
    from host_monitoring_version import VERSION_STRING
except ImportError:
    VERSION_STRING = "?.?"

MAX_USED_MEM = 150
TIME_FORMAT = "%.3f"

CONFIG_DIR = "/etc/sysconfig/host-monitoring.d"
MAPPING_FILE_IDS = os.path.join(CONFIG_DIR, "collrelay_0mq_mapping")
MAPPING_FILE_TYPES = os.path.join(CONFIG_DIR, "0mq_clients")

def client_code():
    from host_monitoring import modules
    #log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=)
    conn_str = "tcp://%s:%d" % (global_config["HOST"],
                                global_config["COM_PORT"])
    arg_stuff = global_config.get_argument_stuff()
    arg_list = arg_stuff["arg_list"]
    com_name = arg_list.pop(0)
    if com_name in modules.command_dict:
        srv_com = server_command.srv_command(command=com_name)#" ".join(arg_list))
        for src_key, dst_key in [("HOST", "host"),
                                 ("COM_PORT", "port")]:
            srv_com[dst_key] = global_config[src_key]
        com_struct = modules.command_dict[com_name]
        try:
            cur_ns, rest = com_struct.handle_commandline(arg_list)
        except ValueError, what:
            ret_state, ret_str = (limits.nag_STATE_CRITICAL, "error parsing: %s" % (what[1]))
        else:
            if hasattr(cur_ns, "arguments"):
                for arg_index, arg in enumerate(cur_ns.arguments):
                    srv_com["arguments:arg%d" % (arg_index)] = arg
            srv_com["arguments:rest"] = " ".join(rest)
            result = net_tools.zmq_connection("%s:%d" % (global_config["IDENTITY_STRING"],
                                                         os.getpid()),
                                              timeout=global_config["TIMEOUT"]).add_connection(conn_str, srv_com)
            if result:
                error_result = result.xpath(None, ".//ns:result[@state != '0']")
                if error_result:
                    error_result = error_result[0]
                    ret_state, ret_str = (int(error_result.attrib["state"]),
                                          error_result.attrib["reply"])
                else:
                    ret_state, ret_str = com_struct.interpret(result, cur_ns)
            else:
                ret_state, ret_str = (limits.nag_STATE_CRITICAL, "timeout")
    else:
        c_matches = difflib.get_close_matches(com_name, modules.command_dict.keys())
        if c_matches:
            cm_str = "close matches: %s" % (", ".join(c_matches))
        else:
            cm_str = "no matches found"
        ret_str = "unknown command %s, %s" % (com_name, cm_str)
        ret_state = limits.nag_STATE_CRITICAL
    print ret_str
    return ret_state

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
            new_sock.setsockopt(zmq.HWM, id_discovery.backlog_size)
            new_sock.setsockopt(zmq.BACKLOG, id_discovery.backlog_size)
            self.socket = new_sock
            id_discovery.relayer_process.register_poller(new_sock, zmq.POLLIN, self.get_result)
            #id_discovery.relayer_process.register_poller(new_sock, zmq.POLLIN, self.error)
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
                "read %s from %s" % (logging_tools.get_plural("mapping", len(id_discovery.mapping)),
                                     MAPPING_FILE_IDS))
            for key, value in id_discovery.mapping.iteritems():
                # only use ip-address / hostname from key
                id_discovery.reverse_mapping.setdefault(value, []).append(key[6:].split(":")[0])
            pprint.pprint(id_discovery.reverse_mapping)
        else:
            id_discovery.mapping = {}
        id_discovery.pending = {}
        # last discovery try
        id_discovery.last_try = {}
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
        
class host_connection(object):
    def __init__(self, conn_str, **kwargs):
        self.zmq_id = kwargs.get("zmq_id", "ms")
        self.tcp_con = kwargs.get("dummy_connection", False)
        host_connection.hc_dict[(not self.tcp_con, conn_str)] = self
        self.__open = False
        self.__conn_str = conn_str
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
        new_sock.setsockopt(zmq.HWM, host_connection.backlog_size)
        new_sock.setsockopt(zmq.BACKLOG, host_connection.backlog_size)
        host_connection.zmq_socket = new_sock
        host_connection.relayer_process.register_poller(new_sock, zmq.POLLIN, host_connection.get_result)
        #host_connection.relayer_process.register_poller(new_sock, zmq.POLLERR, host_connection.error)
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
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        host_connection.relayer_process.log("[hc] %s" % (what), log_level)
    def check_timeout(self, cur_time):
        to_messages = [cur_mes for cur_mes in self.messages.itervalues() if cur_mes.check_timeout(cur_time, host_connection.timeout)]
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
            self.return_error(host_mes,
                              "error parsing arguments: %s" % (process_tools.get_except_info()))
        else:
            if not self.tcp_con:
                try:
                    self._open()
                except:
                    self.return_error(host_mes,
                                      "error connecting to %s: %s" % (self.__conn_str,
                                                                      process_tools.get_except_info()))
                else:
                    if False and self.__backlog_counter == host_connection.backlog_size:
                        # no stupid backlog counting
                        self.return_error(host_mes,
                                          "connection error (backlog full [%d.%d]) for '%s'" % (
                                              self.__backlog_counter,
                                              host_connection.backlog_size,
                                              self.__conn_str))
                        #self._close()
                    else:
                        try:
                            host_connection.zmq_socket.send_unicode(self.zmq_id, zmq.NOBLOCK|zmq.SNDMORE)
                            host_connection.zmq_socket.send_unicode(unicode(host_mes.srv_com), zmq.NOBLOCK)
                        except:
                            self.return_error(host_mes,
                                              "connection error (%s)" % (process_tools.get_except_info()),
                                              )
                        else:
                            #self.__backlog_counter += 1
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
        #self._close()
        #raise zmq.ZMQError()
    @staticmethod
    def get_result(zmq_sock):
        src_id = zmq_sock.recv()
        cur_reply = server_command.srv_command(source=zmq_sock.recv())
        host_connection._handle_result(cur_reply)
    @staticmethod
    def _handle_result(result):
        #print unicode(result)
        mes_id = result["relayer_id"].text
        if mes_id in host_connection.messages:
            host_connection.relayer_process._new_client(result["host"].text, int(result["port"].text))
            cur_mes = host_connection.messages[mes_id]
            if cur_mes.sent:
                cur_mes.sent = False
                #self.__backlog_counter -= 1
            if len(result.xpath(None, ".//ns:raw")):
                # raw response, no interpret
                cur_mes.srv_com = result
                host_connection._send_result(cur_mes, None)
                #self.send_result(cur_mes, None)
            else:
                try:
                    res_tuple = cur_mes.interpret(result)
                except:
                    res_tuple = (limits.nag_STATE_CRITICAL, "error interpreting result: %s" % (process_tools.get_except_info()))
                host_connection._send_result(cur_mes, res_tuple)
                #self.send_result(cur_mes, res_tuple)
        else:
            # FIXME
            #print self.log("unknown id '%s' in _handle_result" % (mes_id), logging_tools.LOG_LEVEL_ERROR)
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
        self.srv_com["relayer_id"] = self.src_id
        self.s_time = time.time()
        self.sent = False
    def set_result(self, state, res_str):
        self.srv_com["result"] = None
        self.srv_com["result"].attrib.update({"reply" : res_str,
                                              "state" : "%d" % (state)})
    def set_com_struct(self, com_struct):
        self.com_struct = com_struct
        if com_struct:
            cur_ns, rest = com_struct.handle_commandline((self.srv_com["arg_list"].text or "").split())
            #print "***", cur_ns, rest
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
        return abs(cur_time - self.s_time) > to_value
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
        
class tcp_send(Protocol):
    #def __init__(self, log_recv):
        #Protocol.__init__(self)
        #self.__log_recv = log_recv
    def __init__(self, factory, src_id, srv_com):
        self.factory = factory
        self.src_id = src_id
        self.srv_com = srv_com
        self.__header_size = None
        self.__chunks = 0
    def connectionMade(self):
        com = self.srv_com["command"].text
        if self.srv_com["arg_list"].text:
            com = "%s %s" % (com, self.srv_com["arg_list"].text)
        self.transport.write("%08d%s" % (len(com), com))
    def dataReceived(self, data):
        #print data
        #self.log_recv.datagramReceived(data, None)
        if self.__header_size is None:
            if data[0:8].isdigit():
                d_len = int(data[0:8])
                self.__header_size = d_len
                self.__data = ""
                self._received(data)
            else:
                self.factory.log("protocol error", logging_tools.LOG_LEVEL_ERROR)
                self.transport.loseConnection()
        else:
            self._received(data)
    def _received(self, data):
        self.__data = "%s%s" % (self.__data, data)
        if len(self.__data) == self.__header_size + 8:
            if self.__chunks:
                self.factory.log("got %d bytes in %d chunks" % (len(self.__data), self.__chunks + 1))
            self.factory.received(self, self.__data[8:])
            self.transport.loseConnection()
        else:
            self.__chunks += 1
    def __del__(self):
        #print "del tcp_send"
        pass

class tcp_factory(ClientFactory):
    def __init__(self, t_process):
        self.twisted_process = t_process
        self.__to_send = {}
        self.noisy = False
    def add_to_send(self, src_id, srv_com):
        cur_id = "%s:%d" % (socket.gethostbyname(srv_com["host"].text), int(srv_com["port"].text))
        self.__to_send.setdefault(cur_id, []).append((src_id, srv_com))
    def connectionLost(self, reason):
        print "gone", reason
    def buildProtocol(self, addr):
        return tcp_send(self, *self._remove_tuple(addr))
    def clientConnectionLost(self, connector, reason):
        if str(reason).lower().count("closed cleanly"):
            pass
        else:
            self.log("%s: %s" % (str(connector).strip(),
                                 str(reason).strip()),
                     logging_tools.LOG_LEVEL_ERROR)
    def clientConnectionFailed(self, connector, reason):
        self.log("%s: %s" % (str(connector).strip(),
                             str(reason).strip()),
                 logging_tools.LOG_LEVEL_ERROR)
        self._remove_tuple(connector)
    def _remove_tuple(self, connector):
        cur_id = "%s:%d" % (connector.host, connector.port)
        if cur_id in self.__to_send:
            send_tuple = self.__to_send[cur_id].pop()
            if not self.__to_send[cur_id]:
                del self.__to_send[cur_id]
            return send_tuple
        else:
            raise SyntaxError, "nothing found to send for '%s'" % (cur_id)
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.twisted_process.log("[tcp] %s" % (", ".join([line.strip() for line in what.split("\n")])), log_level)
    def received(self, cur_proto, data):
        self.twisted_process.send_result(cur_proto.src_id, unicode(cur_proto.srv_com), data)

class hm_icmp_protocol(icmp_twisted.icmp_protocol):
    def __init__(self, tw_process, log_template):
        self.__log_template = log_template
        icmp_twisted.icmp_protocol.__init__(self)
        self.__work_dict, self.__seqno_dict = ({}, {})
        self.__twisted_process = tw_process
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, "[icmp] %s" % (what))
    def __setitem__(self, key, value):
        self.__work_dict[key] = value
    def __getitem__(self, key):
        return self.__work_dict[key]
    def __delitem__(self, key):
        for seq_key in self.__work_dict[key]["sent_list"].keys():
            if seq_key in self.__seqno_dict:
                del self.__seqno_dict[seq_key]
        del self.__work_dict[key]
    def ping(self, seq_str, target, num_pings, timeout):
        self.log("ping to %s (%d, %.2f) [%s]" % (target, num_pings, timeout, seq_str))
        cur_time = time.time()
        self[seq_str] = {"host"       : target,
                         "num"        : num_pings,
                         "timeout"    : timeout,
                         "start"      : cur_time,
                         # time between pings
                         "slide_time" : 0.1,
                         "sent"       : 0,
                         "recv_ok"    : 0,
                         "recv_fail"  : 0,
                         "error_list" : [],
                         "sent_list"  : {},
                         "recv_list"  : {}}
        self._update()
    def _update(self):
        cur_time = time.time()
        del_keys = []
        #pprint.pprint(self.__work_dict)
        for key, value in self.__work_dict.iteritems():
            if value["sent"] < value["num"]:
                if value["sent_list"]:
                    # send if last send was at least slide_time ago
                    to_send = max(value["sent_list"].values()) + value["slide_time"] < cur_time or value["recv_ok"] == value["sent"]
                else:
                    # always send
                    to_send = True
                if to_send:
                    value["sent"] += 1
                    try:
                        self.send_echo(value["host"])
                    except:
                        value["error_list"].append(process_tools.get_except_info())
                        self.log("error sending to %s: %s" % (value["host"],
                                                              ", ".join(value["error_list"])),
                                 logging_tools.LOG_LEVEL_ERROR)
                    else:
                        value["sent_list"][self.echo_seqno] = cur_time
                        self.__seqno_dict[self.echo_seqno] = key
                        reactor.callLater(value["slide_time"] + 0.001, self._update)
                        reactor.callLater(value["timeout"] + value["slide_time"] * value["num"] + 0.001, self._update)
            # check for timeout
            for seq_to in [s_key for s_key, s_value in value["sent_list"].iteritems() if abs(s_value - cur_time) > value["timeout"] and s_key not in value["recv_list"]]:
                value["recv_fail"] += 1
                value["recv_list"][seq_to] = None
            # check for ping finish
            if value["error_list"] or (value["sent"] == value["num"] and value["recv_ok"] + value["recv_fail"] == value["num"]):
                all_times = [value["recv_list"][s_key] - value["sent_list"][s_key] for s_key in value["sent_list"].iterkeys() if value["recv_list"].get(s_key, None) != None]
                self.__twisted_process.send_ping_result(key, value["sent"], value["recv_ok"], all_times, ", ".join(value["error_list"]))
                del_keys.append(key)
        for del_key in del_keys:
            del self[del_key]
        #pprint.pprint(self.__work_dict)
    def received(self, dgram):
        if dgram.packet_type == 0 and dgram.ident == self.__twisted_process.pid & 0x7fff:
            seqno = dgram.seqno
            if seqno not in self.__seqno_dict:
                self.log("got result with unknown seqno %d" % (seqno),
                         logging_tools.LOG_LEVEL_ERROR)
            else:
                value = self[self.__seqno_dict[seqno]]
                if not seqno in value["recv_list"]:
                    value["recv_list"][seqno] = time.time()
                    value["recv_ok"] += 1
            self._update()
        
class twisted_process(threading_tools.process_obj):
    def process_init(self):
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context)
        self.__relayer_socket = self.connect_to_socket("internal")
        my_observer = logging_tools.twisted_log_observer(global_config["LOG_NAME"],
                                                         global_config["LOG_DESTINATION"],
                                                         zmq=True,
                                                         context=self.zmq_context)
        log.startLoggingWithObserver(my_observer, setStdout=False)
        self.twisted_observer = my_observer
        self.tcp_factory = tcp_factory(self)
        self.register_func("connection", self._connection)
        # clear flag for extra twisted thread
        self.__extra_twisted_threads = 0
        if self.start_kwargs.get("icmp", True):
            self.icmp_protocol = hm_icmp_protocol(self, self.__log_template)
            reactor.listenWith(icmp_twisted.icmp_port, self.icmp_protocol)
            self.register_func("ping", self._ping)
    def _connection(self, src_id, srv_com, *args, **kwargs):
        srv_com = server_command.srv_command(source=srv_com)
        try:
            self.tcp_factory.add_to_send(src_id, srv_com)
        except:
            self.send_result(src_id, unicode(srv_com), "error in lookup: %s" % (process_tools.get_except_info()))
        else:
            try:
                cur_con = reactor.connectTCP(srv_com["host"].text, int(srv_com["port"].text), self.tcp_factory)
            except:
                self.log("exception in _connection (twisted_process): %s" % (process_tools.get_except_info()),
                         logging_tools.LOG_LEVEL_ERROR)
            else:
                if reactor.threadpool:
                    cur_threads = len(reactor.threadpool.threads)
                    if cur_threads != self.__extra_twisted_threads:
                        self.log("number of twisted threads changed from %d to %d" % (self.__extra_twisted_threads, cur_threads))
                        self.__extra_twisted_threads = cur_threads
                        self.send_pool_message("process_start")
        #self.send_pool_message("pong", cur_idx)
    def _ping(self, *args, **kwargs):
        self.icmp_protocol.ping(*args)
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)
    def send_result(self, src_id, srv_com, data):
        self.send_to_socket(self.__relayer_socket, ["twisted_result", src_id, srv_com, data])
    def send_ping_result(self, *args):
        self.send_to_socket(self.__relayer_socket, ["twisted_ping_result"] + list(args))
    def loop_post(self):
        self.twisted_observer.close()
        self.__log_template.close()

class my_cached_file(process_tools.cached_file):
    def __init__(self, name, **kwargs):
        self.hosts = set()
        process_tools.cached_file.__init__(self, name, **kwargs)
    def changed(self):
        if self.content:
            self.log("reread file %s" % (self.name))
            self.hosts = set([cur_line.strip() for cur_line in self.content.strip().split("\n") if cur_line.strip() and not cur_line.strip().startswith("#")])
        else:
            self.hosts = set()
    def __contains__(self, h_name):
        return h_name in self.hosts
        
class relay_process(threading_tools.process_pool):
    def __init__(self):
        # copy to access from modules
        from host_monitoring import modules
        self.modules = modules
        self.global_config = global_config
        self.__verbose = global_config["VERBOSE"]
        self.__autosense = global_config["AUTOSENSE"]
        self.__log_cache, self.__log_template = ([], None)
        threading_tools.process_pool.__init__(self, "main", zmq=True, zmq_debug=global_config["ZMQ_DEBUG"])
        self.renice(global_config["NICE_LEVEL"])
        #pending_connection.init(self)
        self.__global_timeout = global_config["TIMEOUT"]
        host_connection.init(self, global_config["BACKLOG_SIZE"], self.__global_timeout, self.__verbose)
        # init lut
        self.__old_send_lut = {}
        if not global_config["DEBUG"]:
            process_tools.set_handles({"out" : (1, "collrelay.out"),
                                       "err" : (0, "/var/lib/logging-server/py_err_zmq")},
                                      zmq_context=self.zmq_context)
        # we need no icmp capability in relaying
        self.add_process(twisted_process("twisted", icmp=False), twisted=True, start=True)
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context)
        self.install_signal_handlers()
        id_discovery.init(self, global_config["BACKLOG_SIZE"], global_config["TIMEOUT"], self.__verbose)
        self._init_filecache()
        self._init_msi_block()
        self._init_ipc_sockets()
        self.register_exception("int_error" , self._sigint)
        self.register_exception("term_error", self._sigint)
        self.register_exception("hup_error", self._hup_error)
        self.register_timer(self._check_timeout, 2)
        self.register_func("twisted_result", self._twisted_result)
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
            msi_block.stop_command  = "/etc/init.d/host-relay force-stop"
            msi_block.kill_pids = True
            #msi_block.heartbeat_timeout = 60
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
        sock_list = [("ipc", "receiver", zmq.PULL  , 2   ),
                     ("ipc", "sender"  , zmq.PUB   , 1024)]
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
                #client.bind("tcp://*:8888")
            except zmq.core.error.ZMQError:
                self.log("error binding %s: %s" % (short_sock_name,
                                                   process_tools.get_except_info()),
                         logging_tools.LOG_LEVEL_CRITICAL)
                raise
            else:
                setattr(self, "%s_socket" % (short_sock_name), cur_socket)
                backlog_size = global_config["BACKLOG_SIZE"]
                os.chmod(file_name, 0777)
                cur_socket.setsockopt(zmq.LINGER, 0)
                cur_socket.setsockopt(zmq.HWM, hwm_size)
                if sock_type == zmq.PULL:
                    self.register_poller(cur_socket, zmq.POLLIN, self._recv_command)
        self.client_socket = self.zmq_context.socket(zmq.ROUTER)
        self.client_socket.setsockopt(zmq.IDENTITY, "ccollclient:%s" % (process_tools.get_machine_name()))
        self.client_socket.setsockopt(zmq.LINGER, 0)
        self.client_socket.setsockopt(zmq.HWM, 10)
        self.register_poller(self.client_socket, zmq.POLLIN, self._recv_nhm_result)
    def _resolve_address(self, target):
        # to avoid loops in the 0MQ connection scheme (will result to nasty asserts)
        if target in self.__forward_lut:
            ip_addr = self.__forward_lut[target]
        else:
            orig_target = target
            if target.lower() in ["localhost", "127.0.0.1", "localhost.localdomain"]:
                target = process_tools.get_machine_name()
            # step 1: resolve to ip
            ip_addr = socket.gethostbyname(target)
            try:
                # step 2: try to get full name
                full_name, aliases, ip_addrs = socket.gethostbyaddr(ip_addr)
            except:
                # forget it
                pass
            else:
                # resolve full name
                ip_addr = socket.gethostbyname(full_name)
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
        xml_input = data.startswith("<")
        srv_com = None
        if xml_input:
            srv_com = server_command.srv_command(source=data)
            src_id = srv_com["identity"].text
        else:
            if data.count(";") > 1:
                parts = data.split(";", 3)
                src_id = parts.pop(0)
                com_part = parts[2].split(None, 1)
                srv_com = server_command.srv_command(command=com_part.pop(0) if com_part else "", identity=src_id)
                srv_com["host"] = parts[0]
                srv_com["port"] = parts[1]
                if com_part:
                    arg_list = com_part[0].split()
                    for arg_index, arg in enumerate(arg_list):
                        srv_com["arguments:arg%d" % (arg_index)] = arg
                else:
                    arg_list = []
                srv_com["arg_list"] = " ".join(arg_list)
        if srv_com is not None:
            if self.__verbose:
                self.log("got command '%s' for '%s' (XML: %s)" % (srv_com["command"].text,
                                                                  srv_com["host"].text,
                                                                  str(xml_input)))
            if "host" in srv_com and "port" in srv_com:
                # check target host, rewrite to ip
                t_host = srv_com["host"].text
                ip_addr = self._resolve_address(t_host)
                srv_com["host"] = ip_addr
                if self.__autosense:
                    c_state = self.__client_dict.get(t_host, None)
                    if c_state is None:
                        # not needed
                        #host_connection.delete_hc(srv_com)
                        if t_host not in self.__last_tried:
                            self.__last_tried[t_host] = "T" if self.__default_0mq else "0"
                        self.__last_tried[t_host] = {"T" : "0",
                                                     "0" : "T"}[self.__last_tried[t_host]]
                        c_state = self.__last_tried[t_host]
                    con_mode = c_state
                    #con_mode = "0"
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
            zmq_sock.send_unicode(src_id, zmq.SNDMORE)
            zmq_sock.send_unicode("cannot interpret")
        self.__num_messages += 1
        if self.__num_messages % 1000 == 0:
            cur_mem = process_tools.get_mem_info()
            self.log("memory usage is %s after %s" % (logging_tools.get_size_str(cur_mem),
                                                      logging_tools.get_plural("message", self.__num_messages)))
    def _send_to_client(self, src_id, srv_com, xml_input):
        # generate new xml from srv_com
        conn_str = "tcp://%s:%d" % (srv_com["host"].text,
                                    int(srv_com["port"].text))
        if id_discovery.has_mapping(conn_str):
            cur_hc = host_connection.get_hc_0mq(conn_str, id_discovery.get_mapping(conn_str))
            com_name = srv_com["command"].text
            cur_mes = host_connection.add_message(host_message(com_name, src_id, srv_com, xml_input))
            if com_name in self.modules.command_dict:
                com_struct = self.modules.command_dict[srv_com["command"].text]
                # handle commandline
                cur_hc.send(cur_mes, com_struct)
            else:
                cur_hc.return_error(cur_mes, "command '%s' not defined" % (com_name))
        elif id_discovery.is_pending(conn_str):
            cur_hc = host_connection.get_hc_0mq(conn_str)
            com_name = srv_com["command"].text
            cur_mes = host_connection.add_message(host_message(com_name, src_id, srv_com, xml_input))
            cur_hc.return_error(cur_mes, "0mq discovery in progress")
        else:
            id_discovery(srv_com, src_id, xml_input)
    def _send_to_nhm_service(self, src_id, srv_com, xml_input):
        conn_str = "tcp://%s:%d" % (srv_com["host"].text,
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
                    self.client_socket.send_unicode(id_discovery.get_mapping(conn_str), zmq.SNDMORE|zmq.NOBLOCK)
                    self.client_socket.send_unicode(unicode(srv_com), zmq.NOBLOCK)
                except:
                    self._send_result(src_id, "error sending to %s: %s" % (
                        conn_str,
                        process_tools.get_except_info()), server_command.SRV_REPLY_STATE_CRITICAL)
                else:
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
            cur_hc.return_error(cur_mes, "command '%s' not defined" % (com_name))
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
    def loop_end(self):
        self._close_ipc_sockets()
        process_tools.delete_pid(self.__pid_name)
        if self.__msi_block:
            self.__msi_block.remove_meta_block()
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
                if global_config["VERBOSE"]:
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

class server_process(threading_tools.process_pool):
    def __init__(self):
        # copy to access from modules
        self.global_config = global_config
        self.__log_cache, self.__log_template = ([], None)
        threading_tools.process_pool.__init__(self,
                                              "main",
                                              zmq=True,
                                              zmq_contexts=1,
                                              zmq_debug=global_config["ZMQ_DEBUG"])
        self.renice(global_config["NICE_LEVEL"])
        if not global_config["DEBUG"]:
            process_tools.set_handles({"out" : (1, "host-monitoring.out"),
                                       "err" : (0, "/var/lib/logging-server/py_err")},
                                      zmq_context=self.zmq_context)
        self.add_process(twisted_process("twisted"), twisted=True, start=True)
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context)
        self.install_signal_handlers()
        self._init_msi_block()
        self._change_socket_settings()
        self._init_network_sockets()
        self.register_exception("int_error", self._sigint)
        self.register_exception("term_error", self._sigint)
        self.register_func("twisted_ping_result", self._twisted_ping_result)
        self._show_config()
        if not self._init_commands():
            self._sigint("error init")
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        if self.__log_template:
            while self.__log_cache:
                cur_lev, cur_what = self.__log_cache.pop(0)
                self.__log_template.log(cur_lev, cur_what)
            self.__log_template.log(lev, what)
        else:
            self.__log_cache.append((lev, what))
    def _sigint(self, err_cause):
        if self["exit_requested"]:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            self["exit_requested"] = True
    def _change_socket_settings(self):
        # hm, really needed ?
        for sys_name, sys_value in [
            ("net.core.rmem_default", 524288),
            ("net.core.rmem_max", 5242880),
            ("net.core.wmem_default", 524288),
            ("net.core.wmem_max", 5242880)]:
            f_path = "/proc/sys/%s" % (sys_name.replace(".", "/"))
            if os.path.isfile(f_path):
                cur_value = int(open(f_path, "r").read().strip())
                if cur_value < sys_value:
                    try:
                        file(f_path, "w").write("%d" % (sys_value))
                    except:
                        self.log("cannot change of %s from %d to %d: %s" % (
                            f_path,
                            cur_value,
                            sys_value,
                            process_tools.get_except_info()),
                                 logging_tools.LOG_LEVEL_ERROR)
                    else:
                        self.log("changed %s from %d to %d" % (
                            f_path,
                            cur_value,
                            sys_value))
                else:
                    self.log("%s is now %d (needed: %d), OK" % (
                        f_path,
                        cur_value,
                        sys_value))
    def _init_msi_block(self):
        # store pid name because global_config becomes unavailable after SIGTERM
        self.__pid_name = global_config["PID_NAME"]
        process_tools.save_pids(global_config["PID_NAME"], mult=3)
        process_tools.append_pids(global_config["PID_NAME"], pid=configfile.get_manager_pid(), mult=3)
        if True:#not self.__options.DEBUG:
            self.log("Initialising meta-server-info block")
            msi_block = process_tools.meta_server_info("collserver")
            msi_block.add_actual_pid(mult=3)
            msi_block.add_actual_pid(act_pid=configfile.get_manager_pid(), mult=3)
            msi_block.start_command = "/etc/init.d/host-monitoring start"
            msi_block.stop_command = "/etc/init.d/host-monitoring force-stop"
            msi_block.kill_pids = True
            #msi_block.heartbeat_timeout = 60
            msi_block.save_block()
        else:
            msi_block = None
        self.__msi_block = msi_block
    def process_start(self, src_process, src_pid):
        process_tools.append_pids(self.__pid_name, src_pid, mult=3)
        if self.__msi_block:
            self.__msi_block.add_actual_pid(src_pid, mult=3)
            self.__msi_block.save_block()
    def _init_network_sockets(self):
        self.socket_list = []
        zmq_id_name = "/etc/sysconfig/host-monitoring.d/0mq_id"
        if not os.path.isfile(zmq_id_name):
            my_0mq_id = uuid_tools.get_uuid().get_urn()
            zmq_id_xml = E.bind_info(
                E.zmq_id(my_0mq_id, bind_address="*"))
            file(zmq_id_name, "w").write(etree.tostring(zmq_id_xml, pretty_print=True, xml_declaration=True, encoding="utf-8"))
        my_0mq_id = file(zmq_id_name, "r").read().strip()
        rewrite = False
        if my_0mq_id.startswith("<?xml"):
            zmq_id_xml = etree.fromstring(my_0mq_id)
            for cur_el in zmq_id_xml.xpath(".//zmq_id[@bind_address]"):
                if cur_el.text is None:
                    rewrite = True
                    cur_el.text = uuid.uuid1().get_urn()
        else:
            zmq_id_xml = E.bind_info(
                E.zmq_id(my_0mq_id, bind_address="*"))
            rewrite = True
        if rewrite:
            file(zmq_id_name, "w").write(etree.tostring(zmq_id_xml, pretty_print=True, xml_declaration=True, encoding="utf-8"))
        my_0mq_id = zmq_id_xml.xpath(".//zmq_id[@bind_address='*']/text()")
        my_0mq_id = my_0mq_id[0]
        # get all ipv4 interfaces with their ip addresses, dict: interfacename -> IPv4
        ipv4_dict = dict([(cur_if_name, [ip_tuple["addr"] for ip_tuple in value[2]][0]) for cur_if_name, value in [(if_name, netifaces.ifaddresses(if_name)) for if_name in netifaces.interfaces()] if 2 in value])
        ipv4_lut = dict([(value, key) for key, value in ipv4_dict.iteritems()])
        ipv4_addresses = ipv4_dict.values()
        zmq_id_dict = dict([(cur_el.attrib["bind_address"], (cur_el.text, True if "virtual" in cur_el.attrib else False)) for cur_el in zmq_id_xml.xpath(".//zmq_id[@bind_address]")])
        if zmq_id_dict.keys() == ["*"]:
            # wildcard bind
            pass
        else:
            if "*" in zmq_id_dict:
                wc_urn, wc_virtual = zmq_id_dict.pop("*")
                for target_ip in ipv4_addresses:
                    if target_ip not in zmq_id_dict:
                        zmq_id_dict[target_ip] = (wc_urn, wc_virtual)
        self.log("0MQ bind info")
        for key in sorted(zmq_id_dict.iterkeys()):
            self.log("bind address %-15s: %s%s" % (key,
                                                   zmq_id_dict[key][0],
                                                   " is virtual" if zmq_id_dict[key][1] else ""))
        for bind_ip, (bind_0mq_id, is_virtual) in zmq_id_dict.iteritems():
            client = self.zmq_context.socket(zmq.ROUTER)
            client.setsockopt(zmq.IDENTITY, bind_0mq_id)
            client.setsockopt(zmq.HWM, 256)
            try:
                client.bind("tcp://%s:%d" % (
                    bind_ip,
                    global_config["COM_PORT"]))
            except zmq.core.error.ZMQError:
                self.log("error binding to %s:%d: %s" % (
                    "virtual %s" % (bind_ip) if is_virtual else bind_ip,
                    global_config["COM_PORT"],
                    process_tools.get_except_info()),
                         logging_tools.LOG_LEVEL_CRITICAL)
                if not is_virtual:
                    raise
                client.close()
            else:
                self.register_poller(client, zmq.POLLIN, self._recv_command)
                self.socket_list.append(client)
        sock_list = [("ipc", "vector" , zmq.PULL, 512, None),
                     ("ipc", "command", zmq.REP , 512, self._recv_ext_command)]
        for sock_proto, short_sock_name, sock_type, hwm_size, dst_func in sock_list:
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
                #client.bind("tcp://*:8888")
            except zmq.core.error.ZMQError:
                self.log("error binding %s: %s" % (short_sock_name,
                                                   process_tools.get_except_info()),
                         logging_tools.LOG_LEVEL_CRITICAL)
                raise
            else:
                setattr(self, "%s_socket" % (short_sock_name), cur_socket)
                backlog_size = global_config["BACKLOG_SIZE"]
                os.chmod(file_name, 0777)
                cur_socket.setsockopt(zmq.LINGER, 0)
                cur_socket.setsockopt(zmq.HWM, hwm_size)
                if dst_func:
                    self.register_poller(cur_socket, zmq.POLLIN, dst_func)
    def register_vector_receiver(self, t_func):
        self.register_poller(self.vector_socket, zmq.POLLIN, t_func)
    def _recv_ext_command(self, zmq_sock):
        data = [zmq_sock.recv()]
        while zmq_sock.getsockopt(zmq.RCVMORE):
            data.append(zmq_sock.recv())
        print "ext_command", data
        zmq_sock.send_unicode("test")
    def _recv_command(self, zmq_sock):
        data = [zmq_sock.recv()]
        while zmq_sock.getsockopt(zmq.RCVMORE):
            data.append(zmq_sock.recv())
        if len(data) == 2:
            src_id = data.pop(0)
            data = data[0]
            srv_com = server_command.srv_command(source=data)
            rest_el = srv_com.xpath(None, ".//ns:arguments/ns:rest")
            if rest_el:
                rest_str = rest_el[0].text or u""
            else:
                rest_str = u""
            # is a delayed command
            delayed = False
            cur_com = srv_com["command"].text
            srv_com["result"] = None
            srv_com["result"].attrib.update({
                "state"      : "%d" % (server_command.SRV_REPLY_STATE_OK),
                "reply"      : "ok",
                "start_time" : TIME_FORMAT % (time.time())})
            if cur_com in self.commands:
                delayed = self._handle_module_command(srv_com, rest_str)
            else:
                c_matches = difflib.get_close_matches(cur_com, self.commands.keys())
                if c_matches:
                    cm_str = "close matches: %s" % (", ".join(c_matches))
                else:
                    cm_str = "no matches found"
                srv_com["result"].attrib.update(
                    {"reply" : "unknown command '%s', %s" % (cur_com, cm_str),
                     "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR)})
            if delayed:
                # delayed is a subprocess_struct
                delayed.set_send_stuff(self, src_id, zmq_sock)
                com_usage = len([True for cur_del in self.__delayed if cur_del.command == cur_com])
                #print "CU", com_usage, [cur_del.target_host for cur_del in self.__delayed]
                if com_usage > delayed.Meta.max_usage:
                    srv_com["result"].attrib.update(
                        {"reply" : "delay limit %d reached for '%s'" % (
                            delayed.Meta.max_usage,
                            cur_com),
                         "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR)})
                    delayed = None
                else:
                    if not self.__delayed:
                        self.register_timer(self._check_delayed, 0.1)
                        self.loop_granularity = 10.0
                    if delayed.Meta.twisted:
                        self.send_to_process("twisted",
                                             *delayed.run())
                    else:
                        delayed.run()
                    self.__delayed.append(delayed)
            if not delayed:
                self._send_return(zmq_sock, src_id, srv_com)
        else:
            self.log("cannot receive more data, already got '%s'" % (", ".join(data)),
                     logging_tools.LOG_LEVEL_ERROR)
    def _send_return(self, zmq_sock, src_id, srv_com):
        c_time = time.time()
        srv_com["result"].attrib["end_time"] = TIME_FORMAT % c_time
        info_str = "got command '%s' from '%s', took %s" % (
            srv_com["command"].text,
            srv_com["source"].attrib["host"],
            logging_tools.get_diff_time_str(abs(c_time - float(srv_com["result"].attrib["start_time"]))))
        if int(srv_com["result"].attrib["state"]) != server_command.SRV_REPLY_STATE_OK:
            info_str = "%s, result is %s (%s)" % (info_str,
                                                  srv_com["result"].attrib["reply"],
                                                  srv_com["result"].attrib["state"])
            log_level = logging_tools.LOG_LEVEL_WARN
        else:
            log_level = logging_tools.LOG_LEVEL_OK
        self.log(info_str, log_level)
        srv_com.update_source()
        zmq_sock.send_unicode(src_id, zmq.SNDMORE)
        zmq_sock.send_unicode(unicode(srv_com))
        del srv_com
    def _check_delayed(self):
        cur_time = time.time()
        new_list = []
        for cur_del in self.__delayed:
            if cur_del.Meta.use_popen:
                if cur_del.finished():
                    #print "finished delayed"
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
        if not len(self.__delayed):
            self.loop_granularity = 1000.0
            self.unregister_timer(self._check_delayed)
    def _handle_module_command(self, srv_com, rest_str):
        cur_com = self.commands[srv_com["command"].text]
        sp_struct = None
        try:
            cur_ns = cur_com.handle_server_commandline(rest_str.split())
            sp_struct = cur_com(srv_com, cur_ns)
        except:
            exc_info = process_tools.exception_info()
            for log_line in process_tools.exception_info().log_lines:
                self.log(log_line, logging_tools.LOG_LEVEL_ERROR)
            srv_com["result"].attrib.update({
                "reply" : "caught server exception '%s'" % (process_tools.get_except_info()),
                "state" : "%d" % (server_command.SRV_REPLY_STATE_CRITICAL)})
        return sp_struct
    def _twisted_ping_result(self, src_proc, src_id, *args):
        ping_id = args[0]
        for cur_del in self.__delayed:
            if cur_del.seq_str == ping_id:
                cur_del.process(*args)
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
    def loop_end(self):
        process_tools.delete_pid(self.__pid_name)
        if self.__msi_block:
            self.__msi_block.remove_meta_block()
    def _init_commands(self):
        self.log("init commands")
        self.__delayed = []
        from host_monitoring import modules
        self.log("modules import errors:", logging_tools.LOG_LEVEL_ERROR)
        for mod_name, com_name, error_str in modules.IMPORT_ERRORS:
            self.log("%-24s %-32s %s" % (mod_name.split(".")[-1], com_name, error_str), logging_tools.LOG_LEVEL_ERROR)
        self.module_list = modules.module_list
        self.commands = modules.command_dict
        _init_ok = True
        for call_name, add_self in [("register_server", True),
                                    ("init_module", False)]:
            for cur_mod in modules.module_list:
                if global_config["VERBOSE"]:
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
    def loop_post(self):
        for cur_sock in self.socket_list:
            cur_sock.close()
        self.vector_socket.close()
        self.command_socket.close()
        self.__log_template.close()

def show_command_info():
    from host_monitoring import modules
    if modules.IMPORT_ERRORS:
        print "Import errors:"
        for mod_name, com_name, error_str in modules.IMPORT_ERRORS:
            print "%-24s %-32s %s" % (mod_name.split(".")[-1], com_name, error_str)
    for com_name in sorted(modules.command_dict.keys()):
        cur_com = modules.command_dict[com_name]
        if isinstance(cur_com, hm_classes.hm_command):
            #print "\n".join(["", "command %s" % (com_name), ""])
            cur_com.parser.print_help()
    sys.exit(0)
    
global_config = configfile.get_global_config(process_tools.get_programm_name())

def main():
    prog_name = global_config.name()
    global_config.add_config_entries([
        #("MAILSERVER"          , configfile.str_c_var("localhost", info="Mail Server")),
        ("DEBUG"               , configfile.bool_c_var(False, help_string="enable debug mode [%(default)s]", short_options="d", only_commandline=True)),
        ("ZMQ_DEBUG"           , configfile.bool_c_var(False, help_string="enable 0MQ debugging [%(default)s]", only_commandline=True)),
        ("LOG_DESTINATION"     , configfile.str_c_var("uds:/var/lib/logging-server/py_log_zmq")),
        ("LOG_NAME"            , configfile.str_c_var(prog_name)),
        ("KILL_RUNNING"        , configfile.bool_c_var(True)),
        ("SHOW-COMMAND-INFO"   , configfile.bool_c_var(False, help_string="show command info", only_commandline=True)),
        ("BACKLOG_SIZE"        , configfile.int_c_var(5, help_string="backlog size for 0MQ sockets [%(default)d]")),
        ("VERBOSE"             , configfile.int_c_var(0, help_string="set verbose level [%(default)d]", short_options="v", only_commandline=True)),
        ("NICE_LEVEL"          , configfile.int_c_var(10, help_string="nice level [%(default)d]")),
        ("PID_NAME"            , configfile.str_c_var("%s/%s" % (prog_name,
                                                                 prog_name)))])
    if prog_name == "collserver":
        global_config.add_config_entries([
            ("COM_PORT", configfile.int_c_var(2001, info="listening Port", help_string="port to communicate [%(default)i]", short_options="p")),
        ])
    elif prog_name == "collclient":
        global_config.add_config_entries([
            ("IDENTITY_STRING", configfile.str_c_var("collclient", help_string="identity string", short_options="i")),
            ("TIMEOUT"        , configfile.int_c_var(10, help_string="set timeout [%(default)d", only_commandline=True)),
            ("COM_PORT"       , configfile.int_c_var(2001, info="listening Port", help_string="port to communicate [%(default)i]", short_options="p")),
            ("HOST"           , configfile.str_c_var("localhost", help_string="host to connect to"))
        ])
    elif prog_name == "collrelay":
        global_config.add_config_entries([
            ("TIMEOUT"  , configfile.int_c_var(8, help_string="timeout for calls to distance machines [%(default)d]")),
            ("AUTOSENSE", configfile.bool_c_var(False, help_string="enable autosensing of 0MQ/TCP Clients [%(default)s]")),
            ])
    global_config.parse_file()
    options = global_config.handle_commandline(description="%s, version is %s" % (prog_name,
                                                                                  VERSION_STRING),
                                               add_writeback_option=prog_name in ["collserver", "collrelay"],
                                               positional_arguments=prog_name in ["collclient"],
                                               partial=prog_name in ["collclient"])
    global_config.write_file()
    if global_config["KILL_RUNNING"]:
        process_tools.kill_running_processes(exclude=configfile.get_manager_pid())
    if global_config["SHOW-COMMAND-INFO"]:
        show_command_info()
    if not options.DEBUG and prog_name in ["collserver", "collrelay"]:
        process_tools.become_daemon()
    elif prog_name in ["collserver", "collrelay"]:
        print "Debugging %s on %s" % (prog_name,
                                      process_tools.get_machine_name())
    if prog_name == "collserver":
        ret_state = server_process().loop()
    elif prog_name == "collrelay":
        ret_state = relay_process().loop()
    elif prog_name == "collclient":
        ret_state = client_code()
    else:
        print "Unknown operation mode %s" % (prog_name)
        ret_state = -1
    sys.exit(ret_state)

if __name__ == "__main__":
    main()
