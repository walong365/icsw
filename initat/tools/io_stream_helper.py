# -*- coding: utf-8 -*-
#
# Copyright (c) 2009-2017 Andreas Lang-Nevyjel, init.at
#
# this file is part of icsw-client
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; Version 3 of the License
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

import atexit
import os
import pickle

import zmq

from initat.logging_server.constants import icswLogHandleTypes, get_log_path


class icswIOStream(object):
    def __init__(self, sock_name="/var/lib/logging-server/py_err_py_zmq", **kwargs):
        self.__buffered = kwargs.get("buffered", False)
        # late init of context and socket to reduce threads
        self.__zmq_context = kwargs.get("zmq_context", None)
        self.__zmq_sock = None
        self.__buffer = ""
        if isinstance(sock_name, icswLogHandleTypes):
            sock_name = get_log_path(sock_name)
        self.__sock_name = self.zmq_socket_name(sock_name, check_ipc_prefix=True)
        if kwargs.get("register_atexit", True):
            atexit.register(self.close)

    @staticmethod
    def zmq_socket_name(sock_name, **kwargs):
        if not sock_name.endswith("_zmq"):
            sock_name = "{}_zmq".format(sock_name)
        if kwargs.get("check_ipc_prefix", False):
            if not sock_name.startswith("ipc://"):
                sock_name = "ipc://{}".format(sock_name)
        return sock_name

    def open(self):
        if self.__zmq_sock is None:
            if self.__zmq_context is None:
                self.__zmq_context = zmq.Context()
            self.__zmq_sock = self.__zmq_context.socket(zmq.PUSH)
            self.__zmq_sock.connect(self.__sock_name)
            self.__zmq_sock.setsockopt(zmq.LINGER, 60)

    @property
    def stream_target(self):
        return self.__sock_name

    def write(self, err_str):
        if not isinstance(err_str, str):
            err_str = str(err_str, errors="replace")
        self.__buffer = "{}{}".format(self.__buffer, err_str)
        if len(self.__buffer) > 1024 or not self.__buffered:
            # syslog.syslog(syslog.LOG_INFO, "****")
            self.flush()
        return len(err_str)

    def flush(self):
        if not self.__buffer:
            return
        pid, t_dict = (
            os.getpid(),
            {
                "IOS_type": "error",
                "error_str": self.__buffer,
                "pid": os.getpid(),
            }
        )
        if os.path.isdir("/proc/{:d}".format(pid)):
            try:
                stat_lines = [
                    (
                        entry.split() + ["", ""]
                    )[0:2] for entry in open(
                        "/proc/{:d}/status".format(pid),
                        "r"
                    ).read().split("\n")
                ]
            except:
                pass
            else:
                for what, rest in stat_lines:
                    r_what = what.lower()[:-1]
                    if rest.isdigit() and len(rest) < 10:
                        t_dict[r_what] = int(rest)
                    else:
                        t_dict[r_what] = rest
        self.open()
        self.__zmq_sock.send(pickle.dumps(t_dict))
        self.__buffer = ""

    def fileno(self):
        # dangerous, do not use
        self.open()
        return self.__zmq_sock.getsockopt(zmq.FD)

    def close(self):
        if self.__zmq_sock:
            self.flush()
            self.__zmq_sock.close()
            # important: set socket attribute to None
            self.__zmq_sock = None

    def __del__(self):
        self.close()
