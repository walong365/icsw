#!/usr/bin/python-init -Ot
# -*- coding: utf-8 -*-
#
# Copyright (C) 2011,2012,2013 Andreas Lang-Nevyjel
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

""" host-monitoring, with 0MQ and twisted support, twisted part """

from icmp_twisted import install

reactor = install()

import icmp_twisted
import logging_tools
import process_tools
import server_command
import socket
import threading_tools
import time

from twisted.internet.protocol import ClientFactory, Protocol
from twisted.python import log

from initat.host_monitoring.config import global_config

class tcp_send(Protocol):
    # def __init__(self, log_recv):
        # Protocol.__init__(self)
        # self.__log_recv = log_recv
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
        # print data
        # self.log_recv.datagramReceived(data, None)
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
        # print "del tcp_send"
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
            self.log(
                "%s: %s" % (
                    str(connector).strip(),
                    str(reason).strip()),
                logging_tools.LOG_LEVEL_ERROR)
    def clientConnectionFailed(self, connector, reason):
        self.log(
            "%s: %s" % (
                str(connector).strip(),
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
        self.__pings_in_flight = 0
        self.__twisted_process = tw_process
        self.__debug = global_config["DEBUG"]
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
        if self.__debug:
            self.log("ping to %s (%d, %.2f) [%s]" % (target, num_pings, timeout, seq_str))
        cur_time = time.time()
        self[seq_str] = {
            "host"       : target,
            "num"        : num_pings,
            "timeout"    : timeout,
            "start"      : cur_time,
            "end"        : cur_time + timeout,
            "next_send"  : cur_time,
            # time between pings
            "slide_time" : 0.1,
            "sent"       : 0,
            "recv_ok"    : 0,
            "recv_fail"  : 0,
            "error_list" : [],
            "sent_list"  : {},
            "recv_list"  : {}}
        self.__pings_in_flight += 1
        if self.__debug:
            self.log(
                "%s in flight: %s" % (
                    logging_tools.get_plural("ping", self.__pings_in_flight),
                    ", ".join(sorted([value["host"] for value in self.__work_dict.itervalues()]))
                    )
                )
        self._update(seq_str)
    def _update(self, key, from_reply=False):
        cur_time = time.time()
        # print cur_time
        # pprint.pprint(self.__work_dict)
        if key in self.__work_dict:
            value = self.__work_dict[key]
            if value["sent"] < value["num"]:
                # if value["sent_list"]:
                # send if last send was at least slide_time ago
                if value["next_send"] <= cur_time: # or value["recv_ok"] == value["sent"]:
                    # print key, value["recv_ok"], value["sent"], value["next_send"] <= cur_time
                    value["sent"] += 1
                    try:
                        self.send_echo(value["host"])
                    except:
                        value["error_list"].append(process_tools.get_except_info())
                        self.log(
                            "error sending to %s: %s" % (
                                value["host"],
                                ", ".join(value["error_list"])),
                            logging_tools.LOG_LEVEL_ERROR)
                    else:
                        value["sent_list"][self.echo_seqno] = time.time()
                        value["next_send"] = cur_time + value["slide_time"]
                        self.__seqno_dict[self.echo_seqno] = key
                        if value["sent"] < value["num"]:
                            reactor.callLater(value["slide_time"] + 0.001, self._update, key)
                        if value["sent"] == 1:
                            # register final timeout
                            reactor.callLater(value["timeout"], self._update, key)
            # check for timeout
            # print value["sent_list"]
            if not from_reply:
                # only check timeouts when called from reactor via callLater
                for seq_to in [s_key for s_key, _s_value in value["sent_list"].iteritems() if cur_time >= value["end"] and s_key not in value["recv_list"]]:
                    value["recv_fail"] += 1
                    value["recv_list"][seq_to] = None
            # check for ping finish
            if value["error_list"] or (value["sent"] == value["num"] and value["recv_ok"] + value["recv_fail"] == value["num"]):
                all_times = [value["recv_list"][s_key] - value["sent_list"][s_key] for s_key in value["sent_list"].iterkeys() if value["recv_list"].get(s_key, None) != None]
                self.__twisted_process.send_ping_result(key, value["sent"], value["recv_ok"], all_times, ", ".join(value["error_list"]))
                del self[key]
                self.__pings_in_flight -= 1
        else:
            # should only happen for delayed pings or pings with error
            self.log("got delayed ping reply (%s)" % (key), logging_tools.LOG_LEVEL_WARN)
        # pprint.pprint(self.__work_dict)
    def received(self, dgram, recv_time=None):
        if dgram.packet_type == 0 and dgram.ident == self.__twisted_process.pid & 0x7fff:
            seqno = dgram.seqno
            # if seqno % 3 == 10:
            #    return
            if seqno not in self.__seqno_dict:
                self.log("got result with unknown seqno %d" % (seqno),
                         logging_tools.LOG_LEVEL_ERROR)
            else:
                value = self[self.__seqno_dict[seqno]]
                if not seqno in value["recv_list"]:
                    value["recv_list"][seqno] = recv_time
                    # if seqno in value["sent_list"]:
                    #    print value["recv_list"][seqno] - value["sent_list"][seqno]
                    value["recv_ok"] += 1
                self._update(self.__seqno_dict[seqno], from_reply=True)

class twisted_process(threading_tools.process_obj):
    def process_init(self):
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context)
        self.__relayer_socket = self.connect_to_socket("internal")
        my_observer = logging_tools.twisted_log_observer(
            global_config["LOG_NAME"],
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
            # reactor.listenWith(icmp_twisted.icmp_port, self.icmp_protocol)
            reactor.listen_ICMP(self.icmp_protocol)
            self.register_func("ping", self._ping)
    def _connection(self, src_id, srv_com, *args, **kwargs):
        srv_com = server_command.srv_command(source=srv_com)
        try:
            self.tcp_factory.add_to_send(src_id, srv_com)
        except:
            self.send_result(src_id, unicode(srv_com), "error in lookup: %s" % (process_tools.get_except_info()))
        else:
            try:
                _cur_con = reactor.connectTCP(srv_com["host"].text, int(srv_com["port"].text), self.tcp_factory)
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
        # self.send_pool_message("pong", cur_idx)
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
        self.__relayer_socket.close()

