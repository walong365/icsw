# Copyright (C) 2008-2016 Andreas Lang-Nevyjel init.at
#
# Send feedback to: <lang-nevyjel@init.at>
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

""" ipc communication tools, now using 0MQ as communication layer """

from __future__ import unicode_literals, print_function

import os
import time

import zmq
from initat.icsw.service.instance import InstanceXML

from initat.tools import process_tools, server_command, logging_tools, threading_tools


class IPCCommandHandler(object):
    def __init__(self, parent):
        self.__parent = parent

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__parent.log(u"[ICH] {}".format(what), log_level)

    def handle(self, data):
        # for format see ccollclientzmq.c and csendsyncerzmq.c
        # ;<VERSION>;<ID_STR>;<HOST>;<PORT>;<TIMEOUT>;<RAW>;<ARG>;<ARG>;
        # for csendsyncerzmq:
        # ;2;<ID_STR>;;0;10;0;{ARGS...}
        # parse ipc command
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
                parts.insert(4, "0")
            elif proto_version == 1:
                parts = data.split(";", 4)
                parts.insert(4, "0")
            else:
                parts = data.split(";", 5)
            src_id = parts.pop(0)
            # parse new format
            if parts[4].endswith(";"):
                com_part = parts[4][:-1]
            else:
                com_part = parts[4]
            # iterative parser
            try:
                arg_list = []
                while com_part.count(";"):
                    cur_size, cur_str = com_part.split(";", 1)
                    cur_size = int(cur_size)
                    com_part = cur_str[cur_size + 1:]
                    arg_list.append(cur_str[:cur_size].decode("utf-8"))
                if com_part:
                    raise ValueError("not fully parsed ({})".format(com_part))
                else:
                    cur_com = arg_list.pop(0) if arg_list else ""
                    srv_com = server_command.srv_command(command=cur_com, identity=src_id)
                    _e = srv_com.builder()
                    srv_com[""].extend(
                        [
                            _e.host(parts[0]),
                            _e.port(parts[1]),
                            _e.timeout(parts[2]),
                            _e.raw_connect(parts[3]),
                            _e.arguments(
                                *[getattr(_e, "arg{:d}".format(arg_idx))(arg) for arg_idx, arg in enumerate(arg_list)]
                            ),
                            _e.arg_list(" ".join(arg_list)),
                        ]
                    )
            except:
                self.log("error parsing {}: {}".format(data, process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
                srv_com = None
        else:
            src_id, srv_com = (None, None)
        return src_id, srv_com


class IPCClientHandler(threading_tools.PollerBase):
    def __init__(self, process):
        self.__process = process
        threading_tools.PollerBase.__init__(self)
        # set flag
        self.debug_zmq = False
        # list of all sockets
        self.__sock_list = []
        # dict of send / recv sockets via server name
        self.__sock_lut = {}
        # dict id -> dc_action
        self.__pending_messages = {}
        self.__msg_id = 0
        self.__msg_prefix = "ipc_com_{:d}".format(os.getpid())
        self.__hm_port = InstanceXML(quiet=True).get_port_dict("host-monitoring", command=True)
        self.__hbc_dict = {}
        self.log("init")

    def register_hbc(self, hbc):
        self.__hbc_dict[hbc.device.idx] = hbc
        for si in hbc.pending_fetch_calls:
            for _action in si.dynamic_update_calls():
                self.call(_action.salt(hbc, si))

    def add_server(self, server_enum, timeout=30):
        # add new server (collrelay or snmp_relay)
        identity_str = process_tools.zmq_identity_str(self.__msg_prefix, short=True)
        zmq_context = self.__process.zmq_context
        cur_timeout = timeout
        client_send = zmq_context.socket(zmq.PUSH)
        client_recv = zmq_context.socket(zmq.SUB)
        client_send.setsockopt(zmq.LINGER, cur_timeout * 2)
        client_recv.setsockopt_string(zmq.SUBSCRIBE, identity_str)
        send_conn_str = "{}".format(
            process_tools.get_zmq_ipc_name(
                "receiver",
                s_name=server_enum.value,
                connect_to_root_instance=True,
            )
        )
        recv_conn_str = "{}".format(
            process_tools.get_zmq_ipc_name(
                "sender",
                s_name=server_enum.value,
                connect_to_root_instance=True,
            )
        )
        self.log(
            "adding server ({} -> {} -> {})".format(
                send_conn_str,
                server_enum.value,
                recv_conn_str,
            )
        )
        self.__sock_list.append(client_send)
        self.__sock_list.append(client_recv)
        self.__sock_lut[server_enum] = (client_send, client_recv)
        client_send.connect(send_conn_str)
        client_recv.connect(recv_conn_str)
        self.register_poller(client_recv, zmq.POLLIN, self._handle_message)

    def close(self):
        for _srv, _sockets in self.__sock_lut.iteritems():
            self.unregister_poller(_sockets[1], zmq.POLLIN)
        for _sock in self.__sock_list:
            _sock.close()
        self.log("close")

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__process.log("[IPCH] {}".format(what), log_level)

    def call(self, dc_action):
        self.__msg_id += 1
        _msg_id = process_tools.zmq_identity_str("{}_{:04d}".format(self.__msg_prefix, self.__msg_id), short=True)
        dc_action.start_time = time.time()
        self.__pending_messages[_msg_id] = dc_action
        srv_com = server_command.srv_command(command=dc_action.command, identity=_msg_id)
        _to_localhost = dc_action.kwargs.pop("connect_to_localhost", False)
        # print("+++", _msg_id, id(dc_action), dc_action.special_instance.Meta.name)
        # destination
        _target_ip = "127.0.0.1" if _to_localhost else dc_action.hbc.ip
        srv_com["host"] = _target_ip
        srv_com["port"] = self.__hm_port
        # special raw mode
        srv_com["raw"] = "True"
        # add arguments and keys
        srv_com["arg_list"] = " ".join(
            list(dc_action.args) + [
                "--{}={}".format(_key, _value) for _key, _value in dc_action.kwargs.iteritems()
            ]
        )
        # add additional keys
        # for key, value in dc_action.kwargs.iteritems():
        #    srv_com[key] = "{:d}".format(value) if type(value) in [int, long] else value
        dc_action.log(
            "calling server '{}' for {}, command is '{}', {}, {}".format(
                dc_action.srv_enum.name,
                _target_ip,
                dc_action.command,
                "args is '{}'".format(
                    ", ".join(
                        [
                            str(value) for value in dc_action.args
                        ]
                    )
                ) if dc_action.args else "no arguments",
                ", ".join(
                    [
                        "{}='{}'".format(
                            key,
                            str(value)
                        ) for key, value in dc_action.kwargs.iteritems()
                    ]
                ) if dc_action.kwargs else "no kwargs",
            )
        )
        try:
            self.__sock_lut[dc_action.srv_enum][0].send_unicode(unicode(srv_com))
        except:
            dc_action.log(
                "unable to send: {}".format(
                    process_tools.get_except_info()
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
            self.feed_result(_msg_id, None)

    def loop(self):
        while self.__pending_messages:
            self.log(
                "{}".format(
                    logging_tools.get_plural("pending message", len(self.__pending_messages))
                )
            )
            self._do_select(1000)

    def _handle_message(self, zmq_socket):
        id_str = zmq_socket.recv()
        if id_str and zmq_socket.getsockopt(zmq.RCVMORE):
            data = zmq_socket.recv()
        else:
            id_str = None
        if id_str:
            try:
                srv_reply = server_command.srv_command(source=data)
            except:
                self.log("error decoding data {}".format(data), logging_tools.LOG_LEVEL_ERROR)
                id_str = None
        if id_str:
            self.feed_result(id_str, srv_reply)

    def feed_result(self, id_str, srv_reply):
        if id_str in self.__pending_messages:
            dc_action = self.__pending_messages[id_str]
            # print("----", id_str, id(dc_action), dc_action.special_instance.Meta.name)
            for _action in dc_action.special_instance.feed_result(dc_action, srv_reply):
                if _action:
                    self.call(_action.salt(dc_action.hbc, dc_action.special_instance))
            del self.__pending_messages[id_str]
        else:
            self.log("Got unknown id_str {}".format(id_str))


def send_and_receive_zmq(target_host, command, *args, **kwargs):
    identity_str = process_tools.zmq_identity_str(kwargs.pop("identity_string", "srv_com"))
    zmq_context = kwargs.pop("zmq_context")
    cur_timeout = kwargs.pop("timeout", 20)
    client_send = zmq_context.socket(zmq.PUSH)
    client_recv = zmq_context.socket(zmq.SUB)
    client_send.setsockopt(zmq.LINGER, cur_timeout * 2)
    client_recv.setsockopt(zmq.SUBSCRIBE, identity_str)
    # kwargs["server"] : collrelay or snmprelay
    server_name = kwargs.pop("server")
    send_conn_str = "{}".format(
        process_tools.get_zmq_ipc_name(
            kwargs.pop("process", "receiver"),
            s_name=server_name,
            connect_to_root_instance=True,
        )
    )
    recv_conn_str = "{}".format(
        process_tools.get_zmq_ipc_name(
            kwargs.pop("process", "sender"),
            s_name=server_name,
            connect_to_root_instance=True,
        )
    )
    client_send.connect(send_conn_str)
    client_recv.connect(recv_conn_str)
    srv_com = server_command.srv_command(command=command, identity=identity_str)
    srv_com["host"] = target_host
    srv_com["raw"] = "True"
    srv_com["arg_list"] = " ".join(args)
    # add additional keys
    for key, value in kwargs.iteritems():
        srv_com[key] = "{:d}".format(value) if type(value) in [int, long] else value
    s_time = time.time()
    client_send.send_unicode(unicode(srv_com))
    client_send.close()
    if client_recv.poll(cur_timeout * 1000):
        id_str = client_recv.recv()
    else:
        id_str = None
    if id_str and client_recv.getsockopt(zmq.RCVMORE):
        e_time = time.time()
        if client_recv.poll((cur_timeout - (e_time - s_time)) * 1000):
            recv_str = client_recv.recv()
        else:
            recv_str = None
    else:
        recv_str = None
    client_recv.close()
    if recv_str and id_str:
        try:
            srv_reply = server_command.srv_command(source=recv_str)
        except:
            # srv_reply = None
            raise
    else:
        # srv_reply = None
        raise SystemError("timeout ({:d} seconds) exceeded".format(int(cur_timeout)))
    return srv_reply
