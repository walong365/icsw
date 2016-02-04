# -*- coding: utf-8 -*-
#
# Copyright (C) 2006-2016 Andreas Lang-Nevyjel init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# this file is part of python-modules-base
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
""" network middleware """

import argparse
import operator
import os
import time

import zmq

from initat.tools import process_tools, server_command, logging_tools


class zmq_connection(object):
    def __init__(self, identity_str, **kwargs):
        self.__ext_context = "context" in kwargs
        if self.__ext_context:
            self.context = kwargs["context"]
        else:
            self.context = zmq.Context()
        # linger time in msecs
        self.__linger_time = kwargs.get("linger", 500)
        self.__timeout = kwargs.get("timeout", 5)
        self.identity = identity_str
        self.poller = zmq.Poller()
        self.poller_handler = {}
        self.__results = {}
        self.__pending = set()
        self.__add_list = []
        self.__socket_dict = {}
        self.__registered = set()
        self.__dummy_fd = -1

    def register_poller(self, zmq_socket, sock_fd, poll_type, callback):
        self.poller_handler.setdefault(zmq_socket, {})[poll_type] = callback
        if sock_fd in self.__registered:
            self.poller.modify(zmq_socket, operator.ior(*self.poller_handler[zmq_socket].keys()))
        else:
            self.poller.register(zmq_socket, poll_type)
            self.__registered.add(sock_fd)

    def unregister_poller(self, zmq_socket):
        if isinstance(zmq_socket, int):
            zmq_socket = self.__socket_dict[zmq_socket]
        del self.poller_handler[zmq_socket]
        self.poller.unregister(zmq_socket)

    def add_connection(self, conn_str, command, **kwargs):
        new_sock = process_tools.get_socket(
            self.context,
            "DEALER",
            linger=self.__linger_time,
            identity=self.identity,
            immediate=kwargs.get("immediate", False),
        )
        if isinstance(command, server_command.srv_command):
            c_type = "sc"
        else:
            c_type = None
        try:
            new_sock.connect(conn_str)
        except:
            self.__dummy_fd -= 1
            cur_fd = self.__dummy_fd
            self.__add_list.append((cur_fd, c_type))
            _result = server_command.srv_command(source=unicode(command))
            _result.set_result(
                "error connecting: {}".format(
                    process_tools.get_except_info()
                ),
                server_command.SRV_REPLY_STATE_CRITICAL
            )
            self.__results[cur_fd] = unicode(_result)
        else:
            # self.register_poller(new_sock, zmq.POLLOUT, self.__show)
            sock_fd = new_sock.getsockopt(zmq.FD)  # @UndefinedVariable
            self.register_poller(new_sock, sock_fd, zmq.POLLIN, self.__receive)  # @UndefinedVariable
            # self.register_poller(new_sock, sock_fd, zmq.POLLERR, self.__show)
            self.__socket_dict[sock_fd] = new_sock
            self.__add_list.append((sock_fd, c_type))
            try:
                new_sock.send_unicode(unicode(command))
            except:
                _result = server_command.srv_command(source=unicode(command))
                _result.set_result(
                    "error sending to {}: {}".format(
                        conn_str,
                        process_tools.get_except_info(),
                    ),
                    server_command.SRV_REPLY_STATE_CRITICAL
                )
                self.__results[sock_fd] = unicode(_result)
                new_sock.close()
            else:
                self.__results[sock_fd] = None
                self.__pending.add(sock_fd)
        if not kwargs.get("multi", False):
            return self.loop()[0]

    def loop(self):
        start_time = time.time()
        while self.__pending:
            socks = self.poller.poll(timeout=max(self.__timeout, 1) * 1000)
            for sock, c_type in socks:
                try:
                    cur_cb = self.poller_handler[sock][c_type]
                except KeyError:
                    print(
                        "unknown key for loop(): ({}, {:d})".format(
                            str(sock),
                            c_type
                        )
                    )
                else:
                    cur_cb(sock)
            cur_time = time.time()
            if abs(cur_time - start_time) >= self.__timeout:
                # need list to avoid 'object has changed ...' error
                for sock_fd in list(self.__pending):
                    self._close_socket(sock_fd)
            if not self.__pending:
                break
        self.close()
        # self.context.term()
        return [self._interpret_result(com_type, self.__results[cur_fd]) for cur_fd, com_type in self.__add_list]

    def __show(self, sock_fd):
        print sock_fd

    def _close_socket(self, sock_fd):
        self.unregister_poller(sock_fd)
        self.__socket_dict[sock_fd].close()
        del self.__socket_dict[sock_fd]
        self.__pending.remove(sock_fd)

    def _interpret_result(self, in_type, in_bytes):
        if in_bytes is not None:
            if in_type == "sc":
                in_bytes = server_command.srv_command(source=in_bytes)
        return in_bytes

    def __receive(self, sock):
        sock_fd = sock.getsockopt(zmq.FD)  # @UndefinedVariable
        self.__results[sock_fd] = sock.recv()
        self._close_socket(sock_fd)

    def close(self):
        for sock_fd in list(self.__pending):
            self._close_socket(sock_fd)
        if not self.__ext_context and self.context is not None:
            self.context.term()
            self.context = None


def SendCommandDefaults():
    from initat.icsw.service.instance import InstanceXML
    _def = argparse.Namespace(
        arguments=[],
        timeout=10,
        port=InstanceXML(quiet=True).get_port_dict("host-monitoring", command=True),
        protocoll="tcp",
        host="localhost",
        verbose=False,
        identity_string="sc_default_{}_{:d}".format(
            os.uname()[1],
            os.getpid()
        ),
        iterations=1,
        raw=False,
        kv=[],
        kva=[],
        kv_path="",
        split=False,
        only_send=False,
        quiet=True,
    )
    return _def


class SendCommand(object):
    def __init__(self, args):
        self.ret_state = 0
        self.args = args
        self.command = None
        self.other_args = self.args.arguments
        self.zmq_context = zmq.Context(1)

    def init_connection(self):
        if self.args.identity_string:
            self.identity_str = self.args.identity_string
        else:
            self.identity_str = process_tools.zmq_identity_str(self.args.identity_substring)
        s_type = "DEALER" if not self.args.split else "PUSH"
        client = self.zmq_context.socket(getattr(zmq, s_type))
        client.setsockopt(zmq.IDENTITY, self.identity_str)  # @UndefinedVariable
        client.setsockopt(zmq.LINGER, self.args.timeout)  # @UndefinedVariable
        if self.args.protocoll == "ipc":
            if self.args.root:
                process_tools.ALLOW_MULTIPLE_INSTANCES = False
            conn_str = "{}".format(
                process_tools.get_zmq_ipc_name(
                    self.args.host,
                    s_name=self.args.server_name,
                    connect_to_root_instance=self.args.root
                )
            )
        else:
            conn_str = "{}://{}:{:d}".format(self.args.protocoll, self.args.host, self.args.port)
        if self.args.split:
            recv_conn_str = "{}".format(
                process_tools.get_zmq_ipc_name(
                    self.args.split,
                    s_name=self.args.server_name,
                    connect_to_root_instance=self.args.root
                )
            )
            recv_sock = self.zmq_context.socket(zmq.ROUTER)  # @UndefinedVariable
            recv_sock.setsockopt(zmq.IDENTITY, self.identity_str)  # @UndefinedVariable
            recv_sock.setsockopt(zmq.LINGER, self.args.timeout)  # @UndefinedVariable
        else:
            recv_conn_str = None
            recv_sock = None
        self.send_sock = client
        self.recv_sock = recv_sock
        self.conn_str = conn_str
        self.recv_conn_str = recv_conn_str
        self.verbose(
            "socket_type is {}\nIdentity_string is '{}'\nconnection_string is '{}'".format(
                s_type,
                self.identity_str,
                conn_str,
            )
        )
        if self.args.split:
            self.verbose("receive connection string is '{}'".format(recv_conn_str))

    def connect(self):
        try:
            self.send_sock.connect(self.conn_str)
        except:
            print(
                "error connecting to {}: {}".format(
                    self.conn_str,
                    process_tools.get_except_info()
                )
            )
            self.ret_state = -1
            success = False
        else:
            if self.recv_sock:
                self.recv_sock.connect(self.recv_conn_str)
            success = True
        return success

    def verbose(self, what):
        if self.args.verbose:
            print(what)

    def close(self):
        if self.send_sock:
            self.send_sock.close()
            self.send_sock = None
        if self.recv_sock:
            self.recv_sock.close()
            self.recv_sock = None
        self.zmq_context.term()

    def send_and_receive(self, srv_com=None):
        _reply = None
        for cur_iter in xrange(self.args.iterations):
            self.verbose("iteration {:d}".format(cur_iter))
            if srv_com is None:
                srv_com = self._build_com()
            self.send(srv_com)
            if not self.args.only_send:
                _timeout, _recv_id, _recv_str = self.receive()
                if not _timeout:
                    _reply = self._handle_return(_recv_id, _recv_str)
                    break
            else:
                break
        return _reply

    def _build_com(self):
        if not self.command:
            self.command = self.args.arguments.pop(0)
        if self.args.raw:
            srv_com = self.command
        else:
            srv_com = server_command.srv_command(command=self.command)
            srv_com["identity"] = self.identity_str
            self._add_args(srv_com)
        return srv_com

    def _add_args(self, srv_com):
        if self.args.kv:
            for kv_pair in self.args.kv:
                if kv_pair.count(":"):
                    key, value = kv_pair.split(":", 1)
                    if self.args.kv_path:
                        srv_com["{}:{}".format(self.args.kv_path, key)] = value
                    else:
                        srv_com[key] = value
                else:
                    print("cannot parse key '{}'".format(kv_pair))
        if self.args.kva:
            for kva_pair in self.args.kva:
                key, attr, value = kva_pair.split(":")
                if self.args.kv_path:
                    srv_com["{}:{}".format(self.args.kv_path, key)].attrib[attr] = value
                else:
                    srv_com[key].attrib[attr] = value
        # not in raw mode, arg_list must always be set (even if empty)
        if not self.args.raw:
            srv_com["arg_list"] = " ".join(self.other_args)
        for arg_index, arg in enumerate(self.other_args):
            self.verbose(" arg {:2d}: {}".format(arg_index, arg))
            srv_com["arguments:arg{:d}".format(arg_index)] = arg

    def send(self, srv_com):
        self.s_time = time.time()
        self.send_sock.send_unicode(unicode(srv_com))
        if self.args.raw:
            self.verbose(srv_com)
        else:
            self.verbose(srv_com.pretty_print())

    def receive(self):
        r_client = self.send_sock if not self.recv_sock else self.recv_sock
        if r_client.poll(self.args.timeout * 1000):
            recv_str = r_client.recv()
            if r_client.getsockopt(zmq.RCVMORE):  # @UndefinedVariable
                recv_id = recv_str
                recv_str = r_client.recv()
            else:
                recv_id = None
            timeout = False
        else:
            print(
                "error timeout in receive() from {} after {}".format(
                    self.recv_conn_str or self.conn_str,
                    logging_tools.get_plural("second", self.args.timeout)
                )
            )
            timeout = True
            recv_id, recv_str = (None, None)
        self.e_time = time.time()
        if timeout:
            self.verbose(
                "communication took {}".format(
                    logging_tools.get_diff_time_str(self.e_time - self.s_time),
                )
            )
        else:
            self.verbose(
                "communication took {}, received {:d} bytes".format(
                    logging_tools.get_diff_time_str(self.e_time - self.s_time),
                    len(recv_str),
                )
            )
        return timeout, recv_id, recv_str

    def _handle_return(self, recv_id, recv_str):
        try:
            srv_reply = server_command.srv_command(source=recv_str)
        except:
            print("cannot interpret reply: {}".format(process_tools.get_except_info()))
            print("reply was: {}".format(recv_str))
            srv_reply = None
            self.ret_state = 1
        else:
            self.verbose("\nXML response (id: '{}'):\n{}\n".format(recv_id, srv_reply.pretty_print()))
            if "result" in srv_reply:
                _result = srv_reply["result"]
                if not self.args.quiet:
                    print(srv_reply["result"].attrib.get("reply", "no reply attribute in result node"))
                self.ret_state = int(srv_reply["result"].attrib.get("state", server_command.SRV_REPLY_STATE_UNSET))
            elif len(srv_reply.xpath(".//nodestatus", smart_strings=False)):
                print(srv_reply.xpath(".//nodestatus", smart_strings=False)[0].text)
                self.ret_state = 0
            else:
                print("no result node found in reply")
                self.ret_state = 2
        return srv_reply
