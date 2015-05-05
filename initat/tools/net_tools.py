# -*- coding: utf-8 -*-
#
# Copyright (C) 2006-2015 Andreas Lang-Nevyjel init.at
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

import operator
import sys
import time

from initat.tools import process_tools
from initat.tools import server_command
import zmq


# copy from process_tools

def get_except_info(exc_info=None):
    if not exc_info:
        exc_info = sys.exc_info()
    return "{} ({})".format(
        str(exc_info[0]),
        str(exc_info[1]))


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
            _result.set_result("error connecting: {}".format(get_except_info()), server_command.SRV_REPLY_STATE_CRITICAL)
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
                        get_except_info(),
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
