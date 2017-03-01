# -*- coding: utf-8 -*-
#
# Copyright (C) 2013-2017 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw-client
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
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

""" host-monitoring, with 0MQ and direct socket support, relay part """

import argparse
import subprocess
import time
from enum import Enum
import pprint

import zmq

from initat.tools import logging_tools, process_tools, server_command
from initat.debug import ICSW_DEBUG_MODE
from . import limits
from .constants import MAX_0MQ_CONNECTION_ERRORS, HostConnectionReTriggerEnum

if ICSW_DEBUG_MODE:
    MAX_0MQ_CONNECTION_ERRORS = 3


DUMMY_0MQ_ID = "ms"


class ExtReturn(object):
    # extended return, for results where more than nag_state / nag_str
    # has to be returned (passive results for instance)
    # __slots__ = []
    def __init__(self, ret_state=None, ret_str=None, passive_results=None, ascii_chunk=""):
        self.ret_state = ret_state if ret_state is not None else limits.mon_STATE_OK
        self.ret_str = ret_str
        self._ret_field = []
        self.passive_results = passive_results or []
        self.ascii_chunk = ascii_chunk

    def ret_str_setter(self, value):
        self._ret_str = value

    def ret_str_getter(self):
        if self._ret_field:
            if self._ret_str is not None:
                raise ValueError(
                    "ret_str '{}' and ret_field '{}' both set".format(
                        self._ret_str,
                        str(self._ret_field),
                    )
                )
            return ", ".join(self._ret_field)
        else:
            return self._ret_str or "return not set in ExtReturn(...)"
    ret_str = property(ret_str_getter, ret_str_setter)

    def feed_state(self, state):
        self.ret_state = max(self.ret_state, state)

    def feed_str(self, value):
        self._ret_field.append(value)

    def feed_str_state(self, str_value, state_value):
        self.feed_str(str_value)
        self.feed_state(state_value)

    @staticmethod
    def get_state_str(in_val):
        # always return state / str
        if isinstance(in_val, ExtReturn):
            return in_val.ret_state, in_val.ret_str
        else:
            return in_val

    @staticmethod
    def get_ext_return(in_val):
        # always return ExtReturn
        if isinstance(in_val, ExtReturn):
            return in_val
        else:
            return ExtReturn(in_val[0], in_val[1])

    def str(self):
        return "{} ({:d})".format(self.ret_str, self.ret_state)


class SimpleCounter(object):
    def __init__(self, in_list, ok=[], warn=[], prefix=None, unknown_is_warn=False):
        self._list = in_list
        # all not in ok or warn are deemed error
        self._ok = ok
        self._warn = warn
        self._prefix = prefix
        self._unknown_is_warn = unknown_is_warn
        self._error = _error = list(set(self._list) - set(self._warn) - set(self._ok))
        self._lut = {}
        self._lut.update(
            {
                _key: "[E]" for _key in self._error
            }
        )
        self._lut.update(
            {
                _key: "[W]" for _key in self._warn
            }
        )

    @property
    def result(self):
        if self._error:
            _state = limits.mon_STATE_WARNING if self._unknown_is_warn else limits.mon_STATE_CRITICAL
        elif self._warn and set(self._list) & set(self._warn):
            _state = limits.mon_STATE_WARNING
        else:
            _state = limits.mon_STATE_OK
        _str = ", ".join(
            [
                "{:d} {}{}".format(
                    self._list.count(_value),
                    _value,
                    self._lut.get(_value, ""),
                ) for _value in sorted(self._ok + self._warn + self._error) if self._list.count(_value)
            ]
        ) or "empty list in SCounter"
        if self._prefix:
            _str = "{}: {}".format(self._prefix, _str)
        return _str, _state


class SRProbe(object):
    __slots__ = ["host_con", "__val", "__time"]

    def __init__(self, host_con):
        self.host_con = host_con
        self.__val = {
            "send": 0,
            "recv": 0,
        }
        self.__time = time.time()

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.host_con.log("[probe for {}] {}".format(self.host_con.conn_str, what), log_level)

    @property
    def send(self):
        return self.__val["send"]

    @send.setter
    def send(self, val):
        cur_time = time.time()
        diff_time = abs(cur_time - self.__time)
        if diff_time > 30 * 60:
            self.log(
                "sent / received in {}: {} / {}".format(
                    logging_tools.get_diff_time_str(diff_time),
                    logging_tools.get_size_str(self.__val["send"]),
                    logging_tools.get_size_str(self.__val["recv"]),
                )
            )
            self.__time = cur_time
            self.__val = {
                "send": 0,
                "recv": 0
            }
        self.__val["send"] += val

    @property
    def recv(self):
        return self.__val["recv"]

    @recv.setter
    def recv(self, val):
        self.__val["recv"] += val


class HostConnection(object):
    __slots__ = [
        "zmq_id", "tcp_con", "sr_probe", "__open", "__conn_str", "messages",
        "zmq_conn_errors", "retrigger_state", "zmq_conn_count", "resend_queue",
    ]

    def __init__(self, conn_str: str, **kwargs):
        """
        connection to a host
        :param conn_str:
        :param kwargs:
        """
        self.zmq_id = kwargs.get("zmq_id", DUMMY_0MQ_ID)
        self.__conn_str = conn_str
        self.tcp_con = kwargs.get("dummy_connection", False)
        HostConnection.hc_dict[self.hc_dict_key] = self
        self.sr_probe = SRProbe(self)
        # number of consecutive 0MQ errors
        self.zmq_conn_errors = 0
        self.zmq_conn_count = 0
        self.retrigger_state = HostConnectionReTriggerEnum.no
        self.messages = {}
        # for messags to be resent if first send after open was not
        # sucessful
        self.resend_queue = []
        self.__open = False

    @property
    def hc_dict_key(self):
        return (not self.tcp_con, self.__conn_str)

    @property
    def conn_str(self):
        return self.__conn_str

    def close(self):
        pass

    def __del__(self):
        pass

    @classmethod
    def init(cls, r_process, backlog_size, timeout, zmq_discovery):
        cls.relayer_process = r_process
        # 2 queues for 0MQ and tcp, 0MQ is (True, conn_str), TCP is (False, conn_str)
        cls.hc_dict = {}
        # lut to map message_ids to host_connections
        cls.message_lut = {}
        cls.backlog_size = backlog_size
        cls.timeout = timeout
        cls.g_log(
            "backlog size is {:d}, timeout is {:d}".format(
                cls.backlog_size,
                cls.timeout,
            )
        )
        # router socket
        id_str = "relayer_rtr_{}".format(process_tools.get_machine_name())
        new_sock = process_tools.get_socket(
            cls.relayer_process.zmq_context,
            "ROUTER",
            identity=id_str,
            linger=0,
            sndhwm=cls.backlog_size,
            rcvhwm=cls.backlog_size,
            backlog=cls.backlog_size,
            immediate=True,
        )
        cls.zmq_socket = new_sock
        cls.relayer_process.register_poller(new_sock, zmq.POLLIN, cls.get_result)
        # ZMQDiscovery instance
        cls.zmq_discovery = zmq_discovery

    @classmethod
    def has_hc_0mq(cls, conn_str, target_id=DUMMY_0MQ_ID, **kwargs):
        return (True, conn_str) in cls.hc_dict

    @classmethod
    def get_hc_0mq(cls, conn_str, target_id=DUMMY_0MQ_ID, **kwargs):
        if (True, conn_str) not in cls.hc_dict:
            if ICSW_DEBUG_MODE:
                cls.relayer_process.log(
                    "new 0MQ HostConnection for '{}'".format(
                        conn_str
                    )
                )
            cur_hc = cls(conn_str, zmq_id=target_id, **kwargs)
        else:
            cur_hc = cls.hc_dict[(True, conn_str)]
            if cur_hc.zmq_id != target_id:
                cur_hc.zmq_id = target_id
        return cur_hc

    @classmethod
    def get_hc_tcp(cls, conn_str, **kwargs):
        if (False, conn_str) not in cls.hc_dict:
            if ICSW_DEBUG_MODE:
                cls.relayer_process.log("new TCP HostConnection for '{}'".format(conn_str))
            cur_hc = cls(conn_str, **kwargs)
        else:
            cur_hc = cls.hc_dict[(False, conn_str)]
        return cur_hc

    @classmethod
    def check_timeout_global(cls, id_discovery):
        # global check_timeout function
        cur_time = time.time()
        id_discovery.check_timeout(cur_time)
        # check timeouts for all host connections
        [cur_hc.check_timeout(cur_time) for cur_hc in cls.hc_dict.values()]

    @classmethod
    def global_close(cls):
        cls.zmq_socket.close()

    @classmethod
    def g_log(cls, what, log_level=logging_tools.LOG_LEVEL_OK):
        cls.relayer_process.log("[hc] {}".format(what), log_level)

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        HostConnection.relayer_process.log("[hc {}] {}".format(self.__conn_str, what), log_level)

    def check_timeout(self, cur_time):
        # check all messages for current cls
        to_messages = [
            cur_mes for cur_mes in self.messages.values() if cur_mes.check_timeout(
                cur_time, HostConnection.timeout
            )
        ]
        if to_messages:
            for to_mes in to_messages:
                self.return_error(
                    to_mes,
                    "timeout (after {:.2f} seconds [con={:.2f}, mes={:.2f}])".format(
                        to_mes.get_runtime(cur_time),
                        HostConnection.timeout,
                        to_mes.timeout,
                    )
                )
        if self.resend_queue:
            for host_mes in self.resend_queue:
                self.send(host_mes, None)
            self.resend_queue = []

    def _open(self):
        _opened = False
        if not self.__open:
            try:
                self.log("connecting 0MQ")
                HostConnection.zmq_socket.connect(self.__conn_str)
            except:
                raise
            else:
                self.__open = True
                _opened = True
                # make a short nap to let 0MQ settle things down
                # time.sleep(0.2)
        return _opened

    def _close(self):
        if self.__open:
            HostConnection.zmq_socket.disconnect(self.__conn_str)
            self.log("disconnecting")
            self.__open = False

    def add_message(self, new_mes):
        HostConnection.message_lut[new_mes.src_id] = self.hc_dict_key
        self.messages[new_mes.src_id] = new_mes
        return new_mes

    def send(self, host_mes: object, com_struct: object):
        try:
            if com_struct is not None:
                # for resending
                host_mes.set_com_struct(com_struct)
        except:
            self.return_error(
                host_mes,
                "error parsing arguments: {}".format(process_tools.get_except_info())
            )
        else:
            if not self.tcp_con:
                try:
                    _was_opened = self._open()
                except:
                    self.return_error(
                        host_mes,
                        "error connecting to {}: {}".format(
                            self.__conn_str,
                            process_tools.get_except_info()
                        )
                    )
                else:
                    map = HostConnection.zmq_discovery.get_mapping(self.__conn_str)
                    # how often to refetch the 0MQ settings
                    fetch_every = 4 if map.reuse_detected else 20
                    if (
                        _was_opened or self.zmq_conn_count % fetch_every == 0
                    ) and (not map.is_new_client or map.reuse_detected):
                        # if client has no machine_uuid set and
                        # - first call after open
                        # - every 20th call
                        # we trigger a refetch
                        if self.retrigger_state == HostConnectionReTriggerEnum.no:
                            self.log("no machine uuid set, triggering 0MQ fetch")
                            self.retrigger_state = HostConnectionReTriggerEnum.init
                    self.zmq_conn_count += 1
                    send_str = str(host_mes.srv_com)

                    try:
                        HostConnection.zmq_socket.send_unicode(self.zmq_id, zmq.DONTWAIT | zmq.SNDMORE)
                        HostConnection.zmq_socket.send_unicode(send_str, zmq.DONTWAIT)
                    except:
                        self.zmq_conn_errors += 1
                        if self.zmq_conn_errors >= MAX_0MQ_CONNECTION_ERRORS:
                            if self.retrigger_state == HostConnectionReTriggerEnum.no:
                                self.retrigger_state = HostConnectionReTriggerEnum.init
                                _info = ", trigger 0MQ-ID fetch "
                            else:
                                _info = ", waiting for 0MQ fetch"
                        else:
                            _info = ", {:d} of {:d} ".format(
                                self.zmq_conn_errors,
                                MAX_0MQ_CONNECTION_ERRORS,
                            )
                        if _was_opened and len(self.resend_queue) < 5:
                            # error after first open, move to resend queue
                            self.log(
                                "error after open, moving message to resend queue",
                                logging_tools.LOG_LEVEL_WARN
                            )
                            self.resend_queue.append((host_mes))
                        else:
                            self.return_error(
                                host_mes,
                                "connection error via ZMQ-ID '{}'{}({})".format(
                                    self.zmq_id,
                                    _info,
                                    process_tools.get_except_info(),
                                ),
                            )
                    else:
                        self.zmq_conn_errors = 0
                        self.sr_probe.send = len(send_str)
                        host_mes.sr_probe = self.sr_probe
                        host_mes.sent = True
                    if self.retrigger_state == HostConnectionReTriggerEnum.init:
                        # check current state
                        self.retrigger_state = HostConnectionReTriggerEnum.sent
                        if HostConnection.zmq_discovery.has_mapping(self.conn_str) and not HostConnection.zmq_discovery.is_pending(self.conn_str):
                            self.log("triggering discovery run, clear resue flag")
                            HostConnection.zmq_discovery(
                                server_command.srv_command(
                                    conn_str=self.conn_str,
                                ),
                                src_id=None,
                                xml_input=True,
                            )
                            # self._close()
                    elif self.retrigger_state == HostConnectionReTriggerEnum.sent:
                        self.retrigger_state = HostConnectionReTriggerEnum.no
                        self.zmq_conn_errors = 0
            else:
                # send to socket-thread for old clients
                HostConnection.relayer_process.send_to_process(
                    "socket",
                    "connection",
                    host_mes.src_id,
                    str(host_mes.srv_com),
                )

    def send_result(self, host_mes, result=None):
        _result, _src_socket = host_mes.get_result(result, HostConnection.relayer_process)
        if host_mes.xml_input:
            # determine returning socket
            if _src_socket == "ipc":
                _send_sock = HostConnection.relayer_process.sender_socket
            else:
                _send_sock = HostConnection.relayer_process.network_socket
        else:
            _send_sock = HostConnection.relayer_process.sender_socket
        _send_sock.send_unicode(host_mes.src_id, zmq.SNDMORE)
        _send_sock.send_unicode(_result)
        del self.messages[host_mes.src_id]
        del HostConnection.message_lut[host_mes.src_id]
        del host_mes

    def return_error(self, host_mes, error_str):
        host_mes.set_result(limits.mon_STATE_CRITICAL, error_str)
        self.send_result(host_mes)

    def _error(self, zmq_sock):
        # not needed right now
        # print "**** _error", zmq_sock
        # print dir(zmq_sock)
        # print zmq_sock.getsockopt(zmq.EVENTS)
        pass
        # self._close()
        # raise zmq.ZMQError()

    @classmethod
    def get_result(cls, zmq_sock):
        _src_id = zmq_sock.recv().decode("utf-8")
        cur_reply = server_command.srv_command(source=zmq_sock.recv())
        # print("*", _src_id)
        # print(cur_reply.pretty_print())
        HostConnection._handle_result(cur_reply)

    @classmethod
    def _handle_result(cls, result):
        # print unicode(result)
        mes_id = result["relayer_id"].text
        # if mes_id in HostConnection.messages:
        if mes_id in cls.message_lut:
            cls.relayer_process._new_client(
                result["*host"],
                int(result["*port"]),
            )
            if "host_unresolved" in result:
                cls.relayer_process._new_client(
                    result["*host_unresolved"],
                    int(result["*port"]),
                )
            cls.hc_dict[cls.message_lut[mes_id]].handle_result(mes_id, result)
        else:
            cls.g_log(
                "got result for delayed id '{}'".format(
                    mes_id
                ),
                logging_tools.LOG_LEVEL_WARN
            )
        del result

    def handle_result(self, mes_id, result):
        cur_mes = self.messages[mes_id]
        # default: nor reuse (detection not possible or not important)
        _reuse = False
        if self.zmq_id != DUMMY_0MQ_ID:
            if "machine_uuid" in result:
                mach_uuid, dyn_uuid = (
                    result["*machine_uuid"],
                    result["*dynamic_uuid"],
                )
            else:
                mach_uuid, dyn_uuid = (
                    self.zmq_id,
                    ""
                )
            # reuse detected ?
            _reuse = HostConnection.zmq_discovery.update_mapping(
                self.__conn_str,
                self.zmq_id,
                mach_uuid,
                dyn_uuid
            )
        if cur_mes.sent:
            # ???
            cur_mes.sent = False
        if len(result.xpath(".//ns:raw", smart_strings=False)):
            # raw response, no interpret
            cur_mes.srv_com = result
            self.send_result(cur_mes, None)
            # self.send_result(cur_mes, None)
        else:
            try:
                if _reuse:
                    _map = HostConnection.zmq_discovery.get_mapping(self.__conn_str)
                    print(id(_map))
                    ret = ExtReturn(
                        limits.mon_STATE_CRITICAL,
                        "0MQ-ID reuse detected ({})".format(
                            _map.reuse_info,
                        )
                    )
                    # _map.clear_reuse()
                else:
                    ret = ExtReturn.get_ext_return(cur_mes.interpret(result))
            except:
                ret = ExtReturn(
                    limits.mon_STATE_CRITICAL,
                    "error interpreting result: {}".format(
                        process_tools.get_except_info()
                    )
                )
                exc_info = process_tools.icswExceptionInfo()
                for line in exc_info.log_lines:
                    HostConnection.relayer_process.log(line, logging_tools.LOG_LEVEL_CRITICAL)
            self.send_result(cur_mes, ret)

    def _handle_old_result(self, mes_id, result, is_error):
        if mes_id in self.messages:
            cur_mes = self.messages[mes_id]
            if result.startswith("no valid") or is_error:
                res_tuple = (limits.mon_STATE_CRITICAL, result)
            else:
                HostConnection.relayer_process._old_client(
                    cur_mes.srv_com["host"].text,
                    int(cur_mes.srv_com["port"].text)
                )
                try:
                    res_tuple = cur_mes.interpret_old(result)
                except:
                    res_tuple = (limits.mon_STATE_CRITICAL, "error interpreting result: {}".format(process_tools.get_except_info()))
            self.send_result(cur_mes, res_tuple)
        else:
            self.log("unknown id '{}' in _handle_old_result".format(mes_id), logging_tools.LOG_LEVEL_ERROR)


class HostMessage(object):
    hm_idx = 0
    hm_open = set()
    __slots__ = [
        "src_id", "xml_input", "timeout", "s_time", "sent",
        "sr_probe", "ns", "com_name", "srv_com", "com_struct"
    ]

    def __init__(self, com_name, src_id, srv_com, xml_input):
        self.com_name = com_name
        # self.hm_idx = HostMessage.hm_idx
        # HostMessage.hm_idx += 1
        # HostMessage.hm_open.add(self.hm_idx)
        self.src_id = src_id
        self.xml_input = xml_input
        self.srv_com = srv_com
        # print srv_com.pretty_print()
        self.timeout = int(srv_com.get("timeout", "10"))
        self.srv_com[""].append(srv_com.builder("relayer_id", self.src_id))
        self.s_time = time.time()
        self.sent = False
        self.sr_probe = None

    def set_result(self, state, res_str=None):
        if isinstance(state, ExtReturn):
            self.srv_com.set_result(state.ret_str, state.ret_state)
        else:
            self.srv_com.set_result(res_str, state)

    def set_com_struct(self, com_struct):
        self.com_struct = com_struct
        if com_struct:
            cur_ns, rest = com_struct.handle_commandline((self.srv_com["arg_list"].text or "").split())
            _e = self.srv_com.builder()
            _arg_list = self.srv_com.xpath(".//ns:arg_list", smart_strings=False)
            if len(_arg_list):
                _arg_list[0].text = " ".join(rest)
            else:
                self.srv_com[""].append(_e.arg_list(" ".join(rest)))
            self.srv_com.delete_subtree("arguments")
            self.srv_com[""].append(
                _e.arguments(
                    *([getattr(_e, "arg{:d}".format(arg_idx))(arg) for arg_idx, arg in enumerate(rest)] + [_e.rest(" ".join(rest))])
                )
            )
            self.srv_com.delete_subtree("namespace")
            for key, value in vars(cur_ns).items():
                self.srv_com["namespace:{}".format(key)] = value
            self.ns = cur_ns
        else:
            # connect to non-host-monitoring service
            self.srv_com["arguments:rest"] = self.srv_com["arg_list"].text
            self.ns = argparse.Namespace()

    def check_timeout(self, cur_time, to_value):
        # check for timeout, to_value is a global timeout from the HostConnection object
        _timeout = self.get_runtime(cur_time) > min(to_value, self.timeout)
        return _timeout

    def get_runtime(self, cur_time):
        return abs(cur_time - self.s_time)

    def get_result(self, result, relayer_process=None):
        if result is None:
            result = self.srv_com
        if self.xml_input:
            _src_socket = self.srv_com["*source_socket"]
        else:
            _src_socket = None
        if isinstance(result, tuple):
            # tuple result from interpret
            if not self.xml_input:
                ret_str = "%d\0%s" % (
                    result[0],
                    result[1]
                )
            else:
                # shortcut
                self.set_result(result[0], result[1])
                ret_str = str(self.srv_com)
        elif isinstance(result, ExtReturn):
            # extended return from interpret
            if not self.xml_input:
                ret_str = "%d\0%s" % (
                    result.ret_state,
                    result.ret_str,
                )
            else:
                self.set_result(result)
                ret_str = str(self.srv_com)
            if relayer_process:
                if result.passive_results:
                    relayer_process.send_passive_results_to_master(result.passive_results)
                if result.ascii_chunk:
                    relayer_process.send_passive_results_as_chunk_to_master(result.ascii_chunk)
        else:
            if not self.xml_input:
                ret_str = "%s\0%s" % (
                    result["result"].attrib["state"],
                    result["result"].attrib["reply"],
                )
            else:
                ret_str = str(result)
        return ret_str, _src_socket

    def interpret(self, result):
        if self.sr_probe:
            self.sr_probe.recv = len(result)
            self.sr_probe = None
        server_error = result.xpath(".//ns:result[@state != '0']", smart_strings=False)
        if server_error:
            return (
                int(server_error[0].attrib["state"]),
                server_error[0].attrib["reply"]
            )
        else:
            return self.com_struct.interpret(result, self.ns)

    def interpret_old(self, result):
        if not isinstance(result, str):
            server_error = result.xpath(".//ns:result[@state != '0']", smart_strings=False)
        else:
            server_error = None
        if server_error:
            return (int(server_error[0].attrib["state"]),
                    server_error[0].attrib["reply"])
        else:
            if result.startswith("error "):
                return (limits.mon_STATE_CRITICAL,
                        result)
            else:
                # copy host, hacky hack
                self.com_struct.NOGOOD_srv_com = self.srv_com
                ret_value = self.com_struct.interpret_old(result, self.ns)
                del self.com_struct.NOGOOD_srv_com
                return ret_value

    def __del__(self):
        # HostMessage.hm_open.remove(self.hm_idx)
        del self.srv_com
        pass


class HMSubprocessStruct(object):
    __slots__ = [
        "srv_com", "command", "command_line", "com_num", "popen", "srv_process",
        "cb_func", "_init_time", "terminated", "__nfts", "__return_sent", "__finished",
        "multi_command", "run_info", "src_id"
    ]

    class Meta:
        max_usage = 2
        direct = False
        max_runtime = 300
        use_popen = True
        verbose = False
        id_str = "not_set"

    def __init__(self, srv_com, com_line, cb_func=None):
        # copy Meta keys
        for key in dir(HMSubprocessStruct.Meta):
            if not key.startswith("__") and not hasattr(self.Meta, key):
                setattr(self.Meta, key, getattr(HMSubprocessStruct.Meta, key))
        self.srv_com = srv_com
        self.command = srv_com["command"].text
        self.command_line = com_line
        self.multi_command = isinstance(self.command_line, list)
        self.com_num = 0
        self.popen = None
        self.srv_process = None
        self.cb_func = cb_func
        self._init_time = time.time()
        # if not a popen call
        self.terminated = False
        # flag for not_finished info
        self.__nfts = None
        # return already sent
        self.__return_sent = False
        # finished
        self.__finished = False

    def run(self):
        run_info = {}
        if self.multi_command:
            if self.command_line:
                cur_cl = self.command_line[self.com_num]
                if isinstance(cur_cl, tuple):
                    # in case of tuple
                    run_info["comline"] = cur_cl[0]
                else:
                    run_info["comline"] = cur_cl
                run_info["command"] = cur_cl
                run_info["run"] = self.com_num
                self.com_num += 1
            else:
                run_info["comline"] = None
        else:
            run_info["comline"] = self.command_line
        self.run_info = run_info
        if run_info["comline"]:
            # if comline is None we do nothing, no server_reply is set
            if self.Meta.verbose:
                self.log("popen '{}'".format(run_info["comline"]))
            self.popen = subprocess.Popen(
                run_info["comline"],
                shell=True,
                stderr=subprocess.STDOUT,
                stdout=subprocess.PIPE
            )
            self.started()

    def set_send_stuff(self, srv_proc, src_id, zmq_sock):
        self.srv_process = srv_proc
        self.src_id = src_id
        self.zmq_sock = zmq_sock

    def started(self):
        pass

    def read(self):
        if self.popen:
            return self.popen.stdout.read()
        else:
            return None

    def finished(self):
        if self.run_info["comline"] is None:
            self.run_info["result"] = 0
            # empty list of commands
            fin = True
        elif not hasattr(self, "popen"):
            # calling finished () after popen has been delete, strange bug
            self.run_info["result"] = 0
            # empty list of commands
            fin = True
        else:
            self.run_info["result"] = self.popen.poll()
            if self.Meta.verbose:
                if self.run_info["result"] is None:
                    cur_time = time.time()
                    if not self.__nfts or abs(self.__nfts - cur_time) > 1:
                        self.__nfts = cur_time
                        self.log("not finished")
                else:
                    self.log("finished with {}".format(str(self.run_info["result"])))
            fin = False
            if self.run_info["result"] is not None:
                self.process()
                if self.multi_command:
                    if self.com_num == len(self.command_line):
                        # last command
                        fin = True
                    else:
                        # next command
                        self.run()
                else:
                    fin = True
        self.__finished = fin
        return fin

    def process(self):
        if self.cb_func:
            self.cb_func(self)
        else:
            self.srv_com.set_result("default process() call", server_command.SRV_REPLY_STATE_ERROR)

    def terminate(self):
        # popen may not be set or None
        if getattr(self, "popen", None):
            self.popen.kill()
        if getattr(self, "srv_com", None):
            self.srv_com.set_result(
                "runtime ({}) exceeded".format(logging_tools.get_plural("second", self.Meta.max_runtime)),
                server_command.SRV_REPLY_STATE_ERROR
            )

    def send_return(self):
        if not self.__return_sent:
            self.__return_sent = True
            if self.srv_process:
                self.srv_process._send_return(self.zmq_sock, self.src_id, self.srv_com)
                del self.srv_com
                del self.zmq_sock
                del self.srv_process
        if self.__finished:
            if hasattr(self, "popen") and self.popen:
                del self.popen
