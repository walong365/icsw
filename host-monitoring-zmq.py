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

from twisted.internet import reactor, task
from twisted.internet.protocol import ClientFactory, Protocol, Factory
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
from lxml import etree
from host_monitoring import limits
import argparse

try:
    from host_monitoring_version import VERSION_STRING
except ImportError:
    VERSION_STRING = "?.?"

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
        com_struct = modules.command_dict[com_name]
        try:
            cur_ns, rest = com_struct.handle_commandline(arg_list)
        except ValueError, what:
            ret_state, ret_str = (limits.nag_STATE_CRITICAL, "error parsing: %s" % (what[1]))
        else:
            print "***", cur_ns, rest
            if hasattr(cur_ns, "arguments"):
                for arg_index, arg in enumerate(cur_ns.arguments):
                    srv_com["arguments:arg%d" % (arg_index)] = arg
            srv_com["arguments:rest"] = " ".join(rest)
            result = net_tools.zmq_connection(global_config["IDENTITY_STRING"]).add_connection(conn_str, srv_com)
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
        ret_str = "unknown command %s" % (com_name)
        ret_state = limits.nag_STATE_CRITICAL
    print ret_str
    return ret_state

BACKLOG_SIZE = 5

class host_connection(object):
    def __init__(self, conn_str, **kwargs):
        host_connection.hc_dict[conn_str] = self
        self.__open = False
        self.__conn_str = conn_str
        self.messages = {}
        dummy_con = kwargs.get("dummy_connection", False)
        if dummy_con:
            self.socket = None
        else:
            new_sock = host_connection.relayer_thread.zmq_context.socket(zmq.XREQ)
            new_sock.setsockopt(zmq.IDENTITY, "relayer_%s" % (process_tools.get_machine_name()))
            new_sock.setsockopt(zmq.LINGER, 0)
            new_sock.setsockopt(zmq.HWM, BACKLOG_SIZE)
            new_sock.setsockopt(zmq.BACKLOG, BACKLOG_SIZE)
            self.socket = new_sock
            host_connection.relayer_thread.register_poller(self.socket, zmq.POLLIN, self._get_result)
            host_connection.relayer_thread.register_poller(self.socket, zmq.POLLERR, self._error)
            self.__backlog_counter = 0
    @staticmethod
    def init(r_thread):
        host_connection.relayer_thread = r_thread
        host_connection.hc_dict = {}
    @staticmethod
    def get_hc(conn_str, **kwargs):
        if conn_str not in host_connection.hc_dict:
            new_hc = host_connection(conn_str, **kwargs)
        return host_connection.hc_dict[conn_str]
    @staticmethod
    def check_timeout_g():
        cur_time = time.time()
        [cur_hc.check_timeout(cur_time) for cur_hc in host_connection.hc_dict.itervalues()]
    def check_timeout(self, cur_time):
        to_messages = [cur_mes for cur_mes in self.messages.itervalues() if cur_mes.check_timeout(cur_time)]
        for to_mes in to_messages:
            self.return_error(to_mes, "timeout")
    def _open(self):
        if not self.__open:
            try:
                self.socket.connect(self.__conn_str)
            except:
                raise
            else:
                self.__open = True
        return self.__open
    def _close(self):
        if self.__open:
            self.socket.close()
            self.__open = False
    def add_message(self, new_mes):
        self.messages[new_mes.src_id] = new_mes
        return new_mes
    def send(self, host_mes, com_struct):
        host_mes.set_com_struct(com_struct)
        if self.socket:
            try:
                self._open()
            except:
                self.return_error(host_mes,
                                  "error connecting to %s: %s" % (self.__conn_str,
                                                                  process_tools.get_except_info()))
            else:
                if self.__backlog_counter == BACKLOG_SIZE:
                    self.return_error(host_mes,
                                      "connection error (backlog full) for '%s'" % (self.__conn_str))
                    #self._close()
                else:
                    self.__backlog_counter += 1
                    print "tts0", self.__backlog_counter, BACKLOG_SIZE
                    host_mes.sent = True
                    self.socket.send_unicode(unicode(host_mes.srv_com))
                    print "tts1"
            print self.messages.keys()
        else:
            # send to twisted-thread for old clients
            host_connection.relayer_thread.send_to_process(
                "twisted",
                "connection",
                host_mes.src_id,
                unicode(host_mes.srv_com))
    def send_result(self, host_mes, result=None):
        host_connection.relayer_thread.relayer_socket.send_unicode(host_mes.src_id, zmq.SNDMORE)
        host_connection.relayer_thread.relayer_socket.send_unicode(host_mes.get_result(result))
        del self.messages[host_mes.src_id]
        print self.messages.keys()
    def return_error(self, host_mes, error_str):
        host_mes.set_result(limits.nag_STATE_CRITICAL, error_str)
        self.send_result(host_mes)
    def _error(self, zmq_sock):
        # not needed right now
        print "****", zmq_sock
        print dir(zmq_sock)
        print zmq_sock.getsockopt(zmq.EVENTS)
        #self._close()
        #raise zmq.ZMQError()
#    print zmq_sock.recv()
    def _get_result(self, zmq_sock):
        self._handle_result(server_command.srv_command(source=zmq_sock.recv()))
    def _handle_result(self, result):
        #print unicode(result)
        mes_id = result["relayer_id"].text
        cur_mes = self.messages[mes_id]
        if cur_mes.sent:
            cur_mes.sent = False
            self.__backlog_counter -= 1
        try:
            res_tuple = cur_mes.interpret(result)
        except:
            res_tuple = (limits.nag_STATE_CRITICAL, "error interpreting result: %s" % (process_tools.get_except_info()))
        self.send_result(cur_mes, res_tuple)
    def _handle_old_result(self, mes_id, result):
        #print unicode(result)
        cur_mes = self.messages[mes_id]
        try:
            res_tuple = cur_mes.interpret_old(result)
        except:
            res_tuple = (limits.nag_STATE_CRITICAL, "error interpreting result: %s" % (process_tools.get_except_info()))
        self.send_result(cur_mes, res_tuple)

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
        self.srv_com["result"] = {"reply" : res_str,
                                  "state" : "%d" % (state)}
    def set_com_struct(self, com_struct):
        self.com_struct = com_struct
        cur_ns, rest = com_struct.handle_commandline((self.srv_com["arg_list"].text or "").split())
        self.ns = cur_ns
    def check_timeout(self, cur_time):
        return abs(cur_time - self.s_time) > 1
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
        server_error = result.xpath(None, ".//ns:result[@state != '0']")
        if server_error:
            return (int(server_error[0].attrib["state"]),
                     server_error[0].attrib["reply"])
        else:
            return self.com_struct.interpret_old(result, self.ns)
        
##class pending_connection(object):
##    def __init__(self, src_id, srv_com, com_struct, conn_str, xml_input=False):
##        self.__xml_input = xml_input
##        self.s_time = time.time()
##        self.srv_com = srv_com
##        #self.identity_str = "relay"#"relay_%d" % (pending_connection.counter)
##        self.com_struct = com_struct
##        srv_com["relayer_id"] = src_id
##        if com_struct:
##            cur_ns, rest = com_struct.handle_commandline([])
##            self.ns = cur_ns
##            cur_sock = pending_connection.get_socket(conn_str)
##            try:
##                cur_sock.send_unicode(unicode(srv_com))
##            except:
##                print "***"
##                self.sock = None
##                raise
##            else:
##                print "s"
##                pending_connection.pending[cur_sock] = self
##                self.sock = cur_sock
##            print "c"
##        else:
##            self.sock = None
##        self.src_id = src_id
##        #print "pending: %d" % (len(pending_connection.pending))
##    @staticmethod
##    def init(r_thread):
##        pending_connection.pending = {}
##        pending_connection.counter = 0
##        pending_connection.sockets = {}
##        pending_connection.relayer_thread = r_thread
##    @staticmethod
##    def get_socket(conn_str):
##        print conn_str
##        if conn_str not in pending_connection.sockets:
##            new_sock = pending_connection.relayer_thread.zmq_context.socket(zmq.XREQ)
##            pending_connection.counter += 1
##            new_sock.setsockopt(zmq.IDENTITY, "relayer_%s" % (process_tools.get_machine_name()))
##            new_sock.setsockopt(zmq.LINGER, 100)
##            new_sock.connect(conn_str)
##            pending_connection.sockets[conn_str] = new_sock
##        return pending_connection.sockets[conn_str]
##    def close(self):
##        if self.sock:
##            del pending_connection.pending[self.sock]
##            #pending_connection.relayer_thread.unregister_poller(self.sock, zmq.POLLIN)
##            #print "cpc"
##            del self.sock
##        del self
##    def __del__(self):
##        #print "dpc #%s" % (self.identity_str)
##        pass
##    def send_result(self, result=None):
##        pending_connection.relayer_thread.relayer_socket.send_unicode(self.src_id, zmq.SNDMORE)
##        if result is None:
##            result = self.srv_com
##        if type(result) == type(()):
##            # from interpret
##            if not self.__xml_input:
##                pending_connection.relayer_thread.relayer_socket.send_unicode(u"%d\0%s" % (result[0],
##                                                                                           result[1]))
##            else:
##                # shortcut
##                self.set_result(result[0], result[1])
##                pending_connection.relayer_thread.relayer_socket.send_unicode(unicode(self.srv_com))
##        else:
##            if not self.__xml_input:
##                pending_connection.relayer_thread.relayer_socket.send_unicode(u"%s\0%s" % (result["result"].attrib["state"],
##                                                                                           result["result"].attrib["reply"]))
##            else:
##                pending_connection.relayer_thread.relayer_socket.send_unicode(unicode(result))

class tcp_send(Protocol):
    #def __init__(self, log_recv):
        #Protocol.__init__(self)
        #self.__log_recv = log_recv
    def __init__(self, factory):
        self.factory = factory
    def connectionMade(self):
        print "***"
        com = self.factory.srv_com["command"].text
        self.transport.write("%08d%s" % (len(com), com))
    def dataReceived(self, data):
        #print data
        #self.log_recv.datagramReceived(data, None)
        if data[0:8].isdigit():
            d_len = int(data[0:8])
            if len(data) == d_len + 8:
                self.factory.received(data[8:])
            else:
                self.factory.log("wrong message length", logging_tools.LOG_LEVEL_ERROR)
        else:
            self.factory.log("protocol error ", logging_tools.LOG_LEVEL_ERROR)
        self.transport.loseConnection()
    def __del__(self):
        print "del tcp_send"

class tcp_factory(ClientFactory):
    # handling of tcp_factor freeing not implemented right now, FIXME
    def __init__(self, t_process, src_id, srv_com):
        self.twisted_process = t_process
        self.src_id = src_id
        self.srv_com = srv_com
    def connectionLost(self, reason):
        print "gone", reason
    def buildProtocol(self, addr):
        return tcp_send(self)
    def clientConnectionLost(self, connector, reason):
        if str(reason).lower().count("closed cleanly"):
            pass
        else:
            self.twisted_process.log("[tcp] %s: %s" % (str(connector).strip(),
                                                       str(reason).strip()),
                                     logging_tools.LOG_LEVEL_ERROR)
    def clientConnectionFailed(self, connector, reason):
        self.twisted_process.log("[tcp] %s: %s" % (str(connector).strip(),
                                                   str(reason).strip()),
                                 logging_tools.LOG_LEVEL_ERROR)
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.twisted_process.log("[tcp] %s" % (what), log_level)
    def received(self, data):
        self.twisted_process.send_result(self.src_id, unicode(self.srv_com), data)
    def __del__(self):
        return "del tcp_factory"

class twisted_process(threading_tools.process_obj):
    def process_init(self):
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context)
        self.__relayer_socket = self.connect_to_socket("internal")
        # init twisted reactor
        #self._got_udp = udp_log_receiver()
        #tcp_factory = Factory()
        #tcp_factory.protocol = tcp_log_receiver
        #reactor.listenUDP(8004, self._got_udp)
        #reactor.listenTCP(8004, tcp_factory)
        #log_recv = twisted_log_receiver(self)
        self.register_func("connection", self._connection)
    def _connection(self, src_id, srv_com, *args, **kwargs):
        srv_com = server_command.srv_command(source=srv_com)
        print srv_com
        try:
            cur_con = reactor.connectTCP(srv_com["host"].text, int(srv_com["port"].text), tcp_factory(self, src_id, srv_com))
        except:
            print process_tools.get_except_info()
        #self.send_pool_message("pong", cur_idx)
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)
    def send_result(self, src_id, srv_com, data):
        self.send_to_socket(self.__relayer_socket, ["twisted_result", src_id, srv_com, data])

class relay_thread(threading_tools.process_pool):
    def __init__(self):
        # copy to access from modules
        from host_monitoring import modules
        self.modules = modules
        self.global_config = global_config
        self.__log_cache, self.__log_template = ([], None)
        threading_tools.process_pool.__init__(self, "main", zmq=True)
        self.renice()
        #pending_connection.init(self)
        host_connection.init(self)
        # init lut
        self.__old_send_lut = {}
        if not global_config["DEBUG"]:
            process_tools.set_handles({"out" : (1, "collrelay.out"),
                                       "err" : (0, "/var/lib/logging-server/py_err_zmq")},
                                      zmq_context=self.zmq_context)
        self.add_process(twisted_process("twisted"), twisted=True, start=True)
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context)
        self.install_signal_handlers()
        self._init_msi_block()
        self._init_ipc_sockets()
        self.register_exception("int_error", self._sigint)
        self.register_exception("term_error", self._sigint)
        self.register_timer(self._check_timeout, 1)
        self.register_func("twisted_result", self._twisted_result)
        self._show_config()
        if not self._init_commands():
            self._sigint("error init")
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        if self.__log_template:
            self.__log_template.log(lev, what)
        else:
            self.__log_cache.append((lev, what))
    def _sigint(self, err_cause):
        if self["exit_requested"]:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            self["exit_requested"] = True
    def _init_msi_block(self):
        # store pid name because global_config becomes unavailable after SIGTERM
        self.__pid_name = global_config["PID_NAME"]
        process_tools.save_pids(global_config["PID_NAME"], mult=3)
        process_tools.append_pids(global_config["PID_NAME"], pid=configfile.get_manager_pid(), mult=2)
        if True:#not self.__options.DEBUG:
            self.log("Initialising meta-server-info block")
            msi_block = process_tools.meta_server_info("collrelay")
            msi_block.add_actual_pid(mult=3)
            msi_block.add_actual_pid(act_pid=configfile.get_manager_pid(), mult=2)
            msi_block.start_command = "/etc/init.d/host-relay start"
            msi_block.stop_command = "/etc/init.d/host-relay force-stop"
            msi_block.kill_pids = True
            #msi_block.heartbeat_timeout = 60
            msi_block.save_block()
        else:
            msi_block = None
        self.__msi_block = msi_block
    def _check_timeout(self):
        host_connection.check_timeout_g()
    def _twisted_result(self, src_proc, proc_id, src_id, srv_com, data_str):
        if src_id in self.__old_send_lut:
            self.__old_send_lut.pop(src_id)._handle_old_result(src_id, data_str)
        else:
            self.log("result for non-existing id '%s' received, discarding" % (src_id),
                     logging_tools.LOG_LEVEL_ERROR)
        return
        print src_id, self.__old_send_lut
        srv_com = server_command.srv_command(source=srv_com)
        print "tr", src_id, unicode(srv_com), data_str
        com_name = srv_com["command"].text
        if com_name in self.modules.command_dict:
            # build dummy host_message
            dummy_hm = host_message(com_name, src_id, srv_com, True)
            dummy_hm.set_com_struct(self.modules.command_dict[com_name])
            res_tuple = dummy_hm.interpret_old(data_str)
        else:
            res_tuple = (limits.nag_STATE_CRITICAL, "error unknown command '%s'" % (com_name))
        self.send_result(src_id, u"%d\0%s" % (res_tuple[0], res_tuple[1]))
    def send_result(self, src_id, ret_str):
        self.relayer_socket.send_unicode(src_id, zmq.SNDMORE)
        self.relayer_socket.send_unicode(ret_str)
    def _init_ipc_sockets(self):
        client = self.zmq_context.socket(zmq.XREP)
        try:
            process_tools.bind_zmq_socket(client, process_tools.get_zmq_ipc_name("receiver"))
        except zmq.core.error.ZMQError:
            self.log("error binding %s: %s" % (process_tools.get_zmq_ipc_name("receiver"),
                                               process_tools.get_except_info()),
                     logging_tools.LOG_LEVEL_CRITICAL)
            raise
        else:
            self.relayer_socket = client
            os.chmod(process_tools.get_zmq_ipc_name("receiver")[5:], 0777)
            self.register_poller(client, zmq.POLLIN, self._recv_command)
    def _recv_command(self, zmq_sock):
        src_id = zmq_sock.recv()
        more = zmq_sock.getsockopt(zmq.RCVMORE)
        if more:
            data = zmq_sock.recv()
            more = zmq_sock.getsockopt(zmq.RCVMORE)
            xml_input = data.startswith("<")
            srv_com = None
            if xml_input:
                srv_com = server_command.srv_command(source=data)
            else:
                if data.count(";") > 1:
                    parts = data.split(";", 2)
                    com_part = parts[2].split(None, 1)
                    srv_com = server_command.srv_command(command=com_part.pop(0))
                    srv_com["host"] = parts[0]
                    srv_com["port"] = parts[1]
                    for arg_index, arg in enumerate(com_part):
                        srv_com["arguments:arg%d" % (arg_index)] = arg
                    srv_com["arg_list"] = " ".join(com_part)
            if srv_com is not None:
                self.log("got command '%s' for '%s' (XML: %s)" % (srv_com["command"].text,
                                                                  srv_com["host"].text,
                                                                  str(xml_input)))
                #self._send_to_old_client(src_id, srv_com, xml_input)
                self._send_to_client(src_id, srv_com, xml_input)
            else:
                self.log("cannot interpret input data '%s' is srv_command" % (data),
                         logging_tools.LOG_LEVEL_ERROR)
            #zmq_sock.send_unicode(src_id, zmq.SNDMORE)
            #zmq_sock.send_unicode(unicode(result))
        else:
            self.log("cannot receive more data, already got '%s'" % (src_id),
                     logging_tools.LOG_LEVEL_ERROR)
    def _send_to_old_client(self, src_id, srv_com, xml_input):
        conn_str = "tcp://%s:%d" % (srv_com["host"].text,
                                    int(srv_com["port"].text))
        cur_hc = host_connection.get_hc(conn_str, dummy_connection=True)
        com_name = srv_com["command"].text
        cur_mes = cur_hc.add_message(host_message(com_name, src_id, srv_com, xml_input))
        if com_name in self.modules.command_dict:
            com_struct = self.modules.command_dict[srv_com["command"].text]
            
            cur_hc.send(cur_mes, com_struct)
            self.__old_send_lut[cur_mes.src_id] = cur_hc
        else:
            cur_hc.return_error(cur_mes, "command '%s' not defined" % (com_name))
            
    def _send_to_client(self, src_id, srv_com, xml_input):
        # generate new xml from srv_com
        conn_str = "tcp://%s:%d" % (srv_com["host"].text,
                                    int(srv_com["port"].text))
        cur_hc = host_connection.get_hc(conn_str)
        com_name = srv_com["command"].text
        cur_mes = cur_hc.add_message(host_message(com_name, src_id, srv_com, xml_input))
        if com_name in self.modules.command_dict:
            com_struct = self.modules.command_dict[srv_com["command"].text]
            # handle commandline
            cur_hc.send(cur_mes, com_struct)
            if False:
                if True:
                    try:
                        cur_pc = pending_connection(src_id, srv_com, com_struct, conn_str, xml_input)
                    except:
                        err_str = "unable to initiate pending_connection: %s" % (process_tools.get_except_info())
                        self.log(err_str,
                                 logging_tools.LOG_LEVEL_ERROR)
                        self.relayer_socket.send_unicode(src_id, zmq.SNDMORE)
                        self.relayer_socket.send_unicode(u"%d\0%s" % (limits.nag_STATE_CRITICAL,
                                                                      err_str))
                        raise
                    else:
                        self.register_poller(cur_pc.sock, zmq.POLLIN, self._get_result)
                else:
                    result = com_struct.interpret(net_tools.zmq_connection("relayer").add_connection(conn_str, srv_com), None)
                    self.relayer_socket.send_unicode(src_id, zmq.SNDMORE)
                    self.relayer_socket.send_unicode(u"%d\0%s" % (result[0], result[1]))
        else:
            cur_hc.return_error(cur_mes, "command '%s' not defined" % (com_name))
        #result = net_tools.zmq_connection(identity_string).add_connection(conn_str, send_xml)
        #return result
    def _close_socket(self, zmq_sock):
        del self.__send_dict[zmq_sock]
        self.unregister_poller(zmq_sock, zmq.POLLIN)
    def _handle_module_command(self, srv_com):
        try:
            self.commands[srv_com["command"].text](srv_com)
        except:
            exc_info = process_tools.exception_info()
            for log_line in process_tools.exception_info().log_lines:
                self.log(log_line, logging_tools.LOG_LEVEL_ERROR)
                srv_com["result"] = {
                    "reply" : "caught server exception '%s'" % (process_tools.get_except_info()),
                    "state" : "%d" % (server_command.SRV_REPLY_STATE_CRITICAL)}
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
        self.module_list = self.modules.module_list
        self.commands = self.modules.command_dict
        _init_ok = True
        for call_name, add_self in [("register_server", True),
                                    ("init_module", False)]:
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

class server_thread(threading_tools.process_pool):
    def __init__(self):
        # copy to access from modules
        self.global_config = global_config
        self.__log_cache, self.__log_template = ([], None)
        threading_tools.process_pool.__init__(self, "main", zmq=True)
        self.renice()
        if not global_config["DEBUG"]:
            process_tools.set_handles({"out" : (1, "host-monitoring.out"),
                                       "err" : (0, "/var/lib/logging-server/py_err")},
                                      zmq_context=self.zmq_context)
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context)
        self.install_signal_handlers()
        self._init_msi_block()
        self._init_network_sockets()
        self.register_exception("int_error", self._sigint)
        self.register_exception("term_error", self._sigint)
        self._show_config()
        if not self._init_commands():
            self._sigint("error init")
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        if self.__log_template:
            self.__log_template.log(lev, what)
        else:
            self.__log_cache.append((lev, what))
    def _sigint(self, err_cause):
        if self["exit_requested"]:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            self["exit_requested"] = True
    def _init_msi_block(self):
        # store pid name because global_config becomes unavailable after SIGTERM
        self.__pid_name = global_config["PID_NAME"]
        process_tools.save_pids(global_config["PID_NAME"], mult=3)
        process_tools.append_pids(global_config["PID_NAME"], pid=configfile.get_manager_pid(), mult=2)
        if True:#not self.__options.DEBUG:
            self.log("Initialising meta-server-info block")
            msi_block = process_tools.meta_server_info("collserver")
            msi_block.add_actual_pid(mult=3)
            msi_block.add_actual_pid(act_pid=configfile.get_manager_pid(), mult=2)
            msi_block.start_command = "/etc/init.d/host-monitoring start"
            msi_block.stop_command = "/etc/init.d/host-monitoring force-stop"
            msi_block.kill_pids = True
            #msi_block.heartbeat_timeout = 60
            msi_block.save_block()
        else:
            msi_block = None
        self.__msi_block = msi_block
    def _init_network_sockets(self):
        client = self.zmq_context.socket(zmq.XREP)
        client.setsockopt(zmq.IDENTITY, "ms")
        client.setsockopt(zmq.HWM, 256)
        try:
            client.bind("tcp://*:%d" % (global_config["COM_PORT"]))
        except zmq.core.error.ZMQError:
            self.log("error binding to %d: %s" % (global_config["COM_PORT"],
                                                  process_tools.get_except_info()),
                     logging_tools.LOG_LEVEL_CRITICAL)
            raise
        else:
            self.register_poller(client, zmq.POLLIN, self._recv_command)
    def _recv_command(self, zmq_sock):
        src_id = zmq_sock.recv()
        more = zmq_sock.getsockopt(zmq.RCVMORE)
        if more:
            data = zmq_sock.recv()
            more = zmq_sock.getsockopt(zmq.RCVMORE)
            srv_com = server_command.srv_command(source=data)
            rest_el = srv_com.xpath(None, ".//ns:arguments/ns:rest")
            if rest_el:
                rest_str = rest_el[0].text or u""
            else:
                rest_str = u""
            self.log("got command '%s' from '%s'" % (srv_com["command"].text,
                                                     srv_com["source"].attrib["host"]))
            
            srv_com.update_source()
            srv_com["result"] = {"state" : server_command.SRV_REPLY_STATE_OK,
                                 "reply" : "ok"}
            if srv_com["command"].text == "status":
                srv_com["result"].attrib["reply"] = "ok process is running"
            elif srv_com["command"].text == "version":
                srv_com["result"].attrib["reply"] = "version is %s" % (VERSION_STRING)
            elif srv_com["command"].text in self.commands:
                self._handle_module_command(srv_com, rest_str)
            else:
                srv_com["result"].attrib.update(
                    {"reply" : "unknown command '%s'" % (srv_com["command"].text),
                     "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR)})
            zmq_sock.send_unicode(src_id, zmq.SNDMORE)
            zmq_sock.send_unicode(unicode(srv_com))
            del srv_com
        else:
            self.log("cannot receive more data, already got '%s'" % (src_id),
                     logging_tools.LOG_LEVEL_ERROR)
    def _handle_module_command(self, srv_com, rest_str):
        cur_com = self.commands[srv_com["command"].text]
        try:
            cur_ns = cur_com.handle_server_commandline(rest_str.split())
            cur_com(srv_com, cur_ns)
        except:
            exc_info = process_tools.exception_info()
            for log_line in process_tools.exception_info().log_lines:
                self.log(log_line, logging_tools.LOG_LEVEL_ERROR)
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
    def loop_end(self):
        process_tools.delete_pid(self.__pid_name)
        if self.__msi_block:
            self.__msi_block.remove_meta_block()
    def _init_commands(self):
        self.log("init commands")
        from host_monitoring import modules
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

global_config = configfile.get_global_config(process_tools.get_programm_name())

def main():
    long_host_name, mach_name = process_tools.get_fqdn()
    prog_name = global_config.name()
    global_config.add_config_entries([
        #("MAILSERVER"          , configfile.str_c_var("localhost", info="Mail Server")),
        ("DEBUG"               , configfile.bool_c_var(False, help_string="enable debug mode [%(default)s]", short_options="d", only_commandline=True)),
        ("LOG_DESTINATION"     , configfile.str_c_var("uds:/var/lib/logging-server/py_log_zmq")),
        ("LOG_NAME"            , configfile.str_c_var(prog_name)),
        ("KILL_RUNNING"        , configfile.bool_c_var(True)),
        ("SERVER_FULL_NAME"    , configfile.str_c_var(long_host_name)),
        ("VERBOSE"             , configfile.int_c_var(0, help_string="set verbose level [%(default)d]", short_options="v", only_commandline=True)),
        ("PID_NAME"            , configfile.str_c_var("%s/%s" % (prog_name,
                                                                 prog_name)))])
    if prog_name == "collserver":
        global_config.add_config_entries([
            ("COM_PORT", configfile.int_c_var(2001, info="listening Port", help_string="port to communicate [%(default)i]", short_options="p")),
        ])
    elif prog_name == "collclient":
        global_config.add_config_entries([
            ("IDENTITY_STRING", configfile.str_c_var("collclient", help_string="identity string", short_options="i")),
            ("COM_PORT", configfile.int_c_var(2001, info="listening Port", help_string="port to communicate [%(default)i]", short_options="p")),
            ("HOST"    , configfile.str_c_var("localhost", help_string="host to connect to"))
        ])
    global_config.parse_file()
    # import modules
    # modules = addon_modules("modules")
    options = global_config.handle_commandline(description="%s, version is %s" % (prog_name,
                                                                                  VERSION_STRING),
                                               add_writeback_option=prog_name in ["collserver"],
                                               positional_arguments=prog_name in ["collclient"],
                                               partial=prog_name in ["collclient"])
    # always set FROM_ADDR
    #global_config["FROM_ADDR"] = long_host_name
    global_config.write_file()
    #process_tools.fix_directories("root", "root", [(glob_config["MAIN_DIR"], 0777)])
    if not options.DEBUG and prog_name in ["collserver", "collrelay"]:
        process_tools.become_daemon()
    elif prog_name in ["collserver"]:
        print "Debugging %s on %s" % (prog_name,
                                      global_config["SERVER_FULL_NAME"])
    if prog_name == "collserver":
        ret_state = server_thread().loop()
    elif prog_name == "collrelay":
        ret_state = relay_thread().loop()
    elif prog_name == "collclient":
        ret_state = client_code()
    else:
        print "Unknown opmode %s" % (prog_name)
        ret_state = -1
    sys.exit(ret_state)

if __name__ == "__main__":
    main()
