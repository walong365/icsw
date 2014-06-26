# -*- coding: utf-8 -*-
#
# Copyright (c) 2009-2014 Andreas Lang-Nevyjel, init.at
#
# this file is part of python-modules-base
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License
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
""" sends everything to the local logging-server """

import os
import pickle
import zmq

def zmq_socket_name(sock_name, **kwargs):
    if not sock_name.endswith("_zmq"):
        sock_name = "{}_zmq".format(sock_name)
    if kwargs.get("check_ipc_prefix", False):
        if not sock_name.startswith("ipc://"):
            sock_name = "ipc://{}".format(sock_name)
    return sock_name

class io_stream(object):
    def __init__(self, sock_name="/tmp/py_log", **kwargs):
        # ignore protocoll
        self.__sock_name = sock_name
        zmq_context = kwargs["zmq_context"]
        if zmq_context is None:
            zmq_context = zmq.Context()
        self.__zmq_sock = zmq_context.socket(zmq.PUSH)
        self.__zmq_sock.connect(zmq_socket_name(sock_name, check_ipc_prefix=True))
        self.__protocol = None
    def write(self, err_str):
        pid, t_dict = (os.getpid(), {
            "IOS_type"  : "error",
            "error_str" : err_str,
            "pid"       : os.getpid()})
        if os.path.isdir("/proc/{:d}".format(pid)):
            try:
                stat_lines = [(entry.split() + ["", ""])[0 : 2] for entry in file("/proc/{:d}/status".format(pid), "r").read().split("\n")]
            except:
                pass
            else:
                for what, rest in stat_lines:
                    r_what = what.lower()[:-1]
                    if rest.isdigit() and len(rest) < 10:
                        t_dict[r_what] = int(rest)
                    else:
                        t_dict[r_what] = rest
        self.__zmq_sock.send(pickle.dumps(t_dict))
    def close(self):
        if self.__zmq_sock:
            self.__zmq_sock.close()
        del self.__protocol
    def flush(self):
        pass
    def __del__(self):
        pass

