# Copyright (C) 2008-2017 Andreas Lang-Nevyjel init.at
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

import time

import zmq

from initat.tools import process_tools, server_command, logging_tools


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
