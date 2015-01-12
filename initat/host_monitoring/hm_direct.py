# -*- coding: utf-8 -*-
#
# Copyright (C) 2011-2014 Andreas Lang-Nevyjel
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

""" host-monitoring for 0MQ >=  4.x.y, direct socket part """

from initat.host_monitoring.config import global_config
import icmp_class
import logging_tools
import process_tools
import re
import select
import server_command
import socket
import threading_tools
import time
import zmq


class hm_icmp_protocol(icmp_class.icmp_protocol):
    def __init__(self, process, log_template):
        self.__log_template = log_template
        icmp_class.icmp_protocol.__init__(self)
        self.__process = process
        self.__work_dict, self.__seqno_dict = ({}, {})
        self.__pings_in_flight = 0
        self.__debug = global_config["DEBUG"]
        # keys already handled
        self.__handled = set()
        # group dict for ping to multiple hosts
        self.__group_dict = {}
        self.__group_idx = 0
        self.init_socket()
        self.__process.register_socket(self.socket, select.POLLIN, self.received)
        self.__process.register_timer(self._check_timeout, 30)
        # self.raw_socket.bind("0.0.0.0")

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, "[icmp] {}".format(what))

    def __setitem__(self, key, value):
        self.__work_dict[key] = value

    def __getitem__(self, key):
        return self.__work_dict[key]

    def __delitem__(self, key):
        for seq_key in self.__work_dict[key]["sent_list"].keys():
            if seq_key in self.__seqno_dict:
                del self.__seqno_dict[seq_key]
        del self.__work_dict[key]

    def _check_timeout(self):
        cur_time = time.time()
        _to_del = [key for key, value in self.__work_dict.iteritems() if abs(value["start"] - cur_time) > 60]
        if _to_del:
            _unhandled = [key for key in _to_del if key not in self.__handled]
            self.log("removing {} ({:d} unhandled)".format(
                logging_tools.get_plural("ping", len(_to_del)),
                len(_unhandled),
                ))
            for _del in _to_del:
                if _del in _unhandled:
                    pass
                else:
                    self.__handled.remove(_del)
                del self[_del]

    def __contains__(self, key):
        return key in self.__work_dict

    def ping(self, seq_str, target_list, num_pings, timeout):
        if self.__debug:
            self.log("ping to {} ({}; {:d}, {:.2f}) [{}]".format(
                logging_tools.get_plural("target", len(target_list)),
                ", ".join([_entry or "<resolve error>" for _entry in target_list]),
                num_pings, timeout,
                seq_str))
        cur_time = time.time()
        if len(target_list) > 1:
            seq_list = ["group_{:d}".format(idx) for idx in xrange(self.__group_idx, self.__group_idx + len(target_list))]
            self.__group_idx += len(target_list)
            self.__group_dict[seq_str] = dict([(cur_seq_str, None) for cur_seq_str in seq_list])
            for cur_seq_str in seq_list:
                self.__group_dict[cur_seq_str] = seq_str
        else:
            seq_list = [seq_str]
        for cur_seq_str, target in zip(seq_list, target_list):
            self[cur_seq_str] = {
                "host": target,
                "num": num_pings,
                "timeout": timeout,
                "start": cur_time,
                "end": cur_time + timeout,
                "next_send": cur_time,
                # time between pings
                "slide_time": 0.1,
                "sent": 0,
                "recv_ok": 0,
                "recv_fail": 0,
                "error_list": [],
                "sent_list": {},
                "recv_list": {}
            }
            if not target:
                self[cur_seq_str].update(
                    {
                        "host": "<resolve error>",
                        "num": 0,
                        "error_list": ["resolve error"],
                    }
                )
            self.__pings_in_flight += 1
        if self.__debug:
            _wft = [key for key, value in self.__work_dict.iteritems() if key in self.__handled]
            self.log(
                "{} in flight: {}, {} waiting for timeout: {}".format(
                    logging_tools.get_plural("ping", self.__pings_in_flight),
                    ", ".join(sorted([value["host"] for key, value in self.__work_dict.iteritems() if key not in self.__handled])),
                    logging_tools.get_plural("ping", len(_wft)),
                    ", ".join(sorted(_wft)),
                )
            )
        for key in seq_list:
            self._update(key)

    def _update(self, key, from_reply=False):
        cur_time = time.time()
        # print cur_time
        # pprint.pprint(self.__work_dict)
        if key in self and key not in self.__handled:
            value = self[key]
            if value["sent"] < value["num"]:
                # send if last send was at least slide_time ago
                if value["next_send"] <= cur_time:  # or value["recv_ok"] == value["sent"]:
                    # print key, value["recv_ok"], value["sent"], value["next_send"] <= cur_time
                    value["sent"] += 1
                    try:
                        self.send_echo(value["host"])
                    except:
                        value["error_list"].append(process_tools.get_except_info())
                        self.log(
                            "error sending to {}: {}".format(
                                value["host"],
                                ", ".join(value["error_list"])
                            ),
                            logging_tools.LOG_LEVEL_ERROR
                        )
                    else:
                        value["sent_list"][self.echo_seqno] = time.time()
                        value["next_send"] = cur_time + value["slide_time"]
                        self.__seqno_dict[self.echo_seqno] = key
                        if value["sent"] < value["num"]:
                            self.__process.register_timer(self._update, value["slide_time"] + 0.001, oneshot=True, data=key)
                        if value["sent"] == 1:
                            # register final timeout
                            # print "reg_to", key, value["timeout"]
                            self.__process.register_timer(self._update, value["timeout"], oneshot=True, data=key)
            # check for timeout
            # print value["sent_list"]
            if not from_reply:
                # only check timeouts when called from reactor via callLater
                for seq_to in [s_key for s_key, _s_value in value["sent_list"].iteritems() if cur_time >= value["end"] and s_key not in value["recv_list"]]:
                    value["recv_fail"] += 1
                    value["recv_list"][seq_to] = None
            # check for ping finish
            if value["error_list"] or (
                value["sent"] == value["num"] and value["recv_ok"] + value["recv_fail"] == value["num"] or abs(cur_time - value["start"]) > value["timeout"]
            ):
                all_times = [
                    value["recv_list"][s_key] - value["sent_list"][s_key] for s_key in
                    value["sent_list"].iterkeys() if value["recv_list"].get(s_key, None) is not None
                ]
                if key in self.__group_dict:
                    t_seq_str = self.__group_dict[key]
                    self.__group_dict[t_seq_str][key] = (value["host"], value["sent"], value["recv_ok"], all_times, ", ".join(value["error_list"]))
                    if len([t_key for t_key, value in self.__group_dict[t_seq_str].iteritems() if value is None]) == 0:
                        # group done
                        self.__process.send_ping_result(t_seq_str, list(self.__group_dict[t_seq_str].itervalues()))
                        del self.__group_dict[t_seq_str]
                    del self.__group_dict[key]
                else:
                    self.__process.send_ping_result(key, value["sent"], value["recv_ok"], all_times, ", ".join(value["error_list"]))
                self.__handled.add(key)  # del self[key]
                self.__pings_in_flight -= 1
        else:
            if from_reply:
                # should only happen for delayed pings or pings with error
                self.log("got delayed ping reply ({})".format(key), logging_tools.LOG_LEVEL_WARN)
        # pprint.pprint(self.__work_dict)

    def received(self, sock):
        recv_time = time.time()
        dgram = self.parse_datagram(sock.recv(1024))
        if dgram and dgram.packet_type == 0 and dgram.ident == self.__process.pid & 0x7fff:
            seqno = dgram.seqno
            if seqno not in self.__seqno_dict:
                self.log(
                    "got result with unknown seqno {:d}".format(
                        seqno
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
            else:
                _key = self.__seqno_dict[seqno]
                value = self[_key]
                if _key in self.__handled:
                    self.log(
                        "got delay ping result ({}) for host {} ({:.2f})".format(
                            seqno,
                            value["host"],
                            recv_time - value["start"],
                        ),
                        logging_tools.LOG_LEVEL_WARN,
                    )
                else:
                    if seqno not in value["recv_list"]:
                        value["recv_list"][seqno] = recv_time
                        # if seqno in value["sent_list"]:
                        #    print value["recv_list"][seqno] - value["sent_list"][seqno]
                        value["recv_ok"] += 1
                    self._update(self.__seqno_dict[seqno], from_reply=True)


class tcp_con(object):
    pending = []

    def __init__(self, proc, src_id, srv_com):
        self.__process = proc
        self.src_id = src_id
        self.srv_com = srv_com
        self.s_time = time.time()
        self._port = int(srv_com["port"].text)
        try:
            self._host = socket.gethostbyname(srv_com["host"].text)
        except:
            self._host = srv_com["host"].text
            self.log(
                "Failed to resolve host: {}: {}".format(
                    srv_com["host"].text,
                    process_tools.get_except_info()
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
            self.__process.send_result(self.src_id, unicode(self.srv_com), "error resolving host '{}'".format(self._host))
            self.__registered = False
        else:
            # BM Jan 2014:
            # there used to be a problem due to connections without successful connection being added to the pending list
            # then, for any further call, socket would not have been defined
            # therefore we only keep track of successful connections now
            tcp_con.pending.append(self)

            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # , socket.IPPROTO_TCP)
            self.socket.setblocking(0)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 262144)
            # self.socket.setsockopt(socket.SOCK_STREAM, socket.SO_KEEPALIVE, 1)
            self.__process.register_socket(self.socket, zmq.POLLOUT, self._send)  # @UndefinedVariable
            self.__registered = True
            try:
                self.socket.connect((self._host, self._port))
            except socket.error as _err:
                errno = _err.errno
                if errno != 115:
                    self.log("error while bind to ({}, {:d}): {}".format(self._host, self._port, errno))
            # if errno
            # print errno
            # time.sleep(0.1)
        # self._send()

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__process.log(
            "[{}:{:d}] {}".format(
                self._host,
                self._port,
                what
            ),
            log_level
        )

    def _send(self, sock):
        try:
            self.socket.send(self._send_str(self.srv_com))
        except:
            self.log("error sending: {}".format(process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
            self.close()
        else:
            self.__process.unregister_socket(self.socket)
            self.__process.register_socket(self.socket, select.POLLIN, self._recv)

    def _send_str(self, srv_com):
        com = srv_com["command"].text
        if srv_com["arg_list"].text:
            com = "{} {}".format(com, srv_com["arg_list"].text)
        return "{:08d}{}".format(len(com), com)

    def _recv(self, sock):
        try:
            _data = sock.recv(2048)
        except:
            self.log("recv problem: {}".format(process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
        else:
            if _data[0:8].isdigit():
                _len = int(_data[0:8])
                if _len + 8 == len(_data):
                    self.__process.send_result(self.src_id, unicode(self.srv_com), _data[8:])
                else:
                    self.log(
                        "wrong length: {:d} (header) != {:d} (body)".format(
                            _len,
                            len(_data) - 8
                        ),
                        logging_tools.LOG_LEVEL_ERROR
                    )
            else:
                self.log("wrong header: {}" .format(_data[0:8]), logging_tools.LOG_LEVEL_ERROR)
        self.close()

    def close(self):
        tcp_con.pending = [_entry for _entry in tcp_con.pending if _entry != self]
        if self.__registered:
            self.__registered = False
            self.__process.unregister_socket(self.socket)
        self.socket.close()
        del self.srv_com


class socket_process(threading_tools.process_obj):
    def process_init(self):
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context)
        # log.startLoggingWithObserver(my_observer, setStdout=False)
        self.register_func("connection", self._connection)
        # clear flag for extra twisted thread
        self.__extra_twisted_threads = 0
        # print self.start_kwargs
        if self.start_kwargs.get("icmp", True):
            self.icmp_protocol = hm_icmp_protocol(self, self.__log_template)
            # reactor.listenWith(icmp_twisted.icmp_port, self.icmp_protocol)
            # reactor.listen_ICMP(self.icmp_protocol)
            self.register_func("ping", self._ping)
        else:
            self.icmp_protocol = None
        self.register_func("resolved", self._resolved)
        self.register_timer(self._check_timeout, 5)
        self.__ip_re = re.compile("^\d+\.\d+\.\d+\.\d+$")
        self.__pending_id, self.__pending_dict = (0, {})

    def _check_timeout(self):
        cur_time = time.time()
        to_list = [entry for entry in tcp_con.pending if abs(entry.s_time - cur_time) > 20]
        if to_list:
            self.log("removing {} (timeout)".format(logging_tools.get_plural("TCP connection", len(to_list))))
            for _entry in to_list:
                _entry.log("timeout", logging_tools.LOG_LEVEL_WARN)
                _entry.close()

    def _connection(self, src_id, srv_com, *args, **kwargs):
        srv_com = server_command.srv_command(source=srv_com)
        tcp_con(self, src_id, srv_com)

    def _ping(self, *args, **kwargs):
        _addr_list = args[1]
        if all([self.__ip_re.match(_addr) for _addr in _addr_list]):
            self.icmp_protocol.ping(*args)
        else:
            self.__pending_id += 1
            self.__pending_dict[self.__pending_id] = args
            self.send_pool_message("resolve", self.__pending_id, args[1], target="resolve")
            # self.icmp_protocol.ping(*args)

    def _resolved(self, *args, **kwargs):
        _id, _addr_list = args[:2]
        # build new argument lis
        new_args = tuple([self.__pending_dict[_id][0]] + [_addr_list] + list(self.__pending_dict[_id][2:]))
        del self.__pending_dict[_id]
        self.icmp_protocol.ping(*new_args)

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)

    def send_result(self, src_id, srv_com, data):
        self.send_pool_message("socket_result", src_id, srv_com, data, target="main")

    def send_ping_result(self, *args):
        self.send_pool_message("socket_ping_result", *args, target="main")  # src_id, srv_com, data, target="main")

    def loop_post(self):
        # self.twisted_observer.close()
        if self.icmp_protocol:
            self.icmp_protocol.close()
        self.__log_template.close()
