#!/usr/bin/python-init -Ot
# -*- coding: utf-8 -*-
#
# Copyright (c) 2009,2010,2011,2012,2013 Andreas Lang-Nevyjel, init.at
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

import cPickle
import os
import sys
try:
    import zmq
except:
    zmq = None
from twisted.internet.protocol import ConnectedDatagramProtocol
from twisted.internet import reactor

def zmq_socket_name(sock_name, **kwargs):
    if not sock_name.endswith("_zmq"):
        sock_name = "%s_zmq" % (sock_name)
    if kwargs.get("check_ipc_prefix", False):
        if not sock_name.startswith("ipc://"):
            sock_name = "ipc://%s" % (sock_name)
    return sock_name

class error_protocol(ConnectedDatagramProtocol):
    def __init__(self):
        self.out_buffer = []
    def doStart(self):
        self.sendDatagram()
    def sendDatagram(self):
        while self.out_buffer:
            self.transport.write(self.out_buffer.pop(0))
    def connectionFailed(self, why):
        print "conn refused", why
    
class io_stream(object):
    def __init__(self, sock_name="/tmp/py_log", **kwargs):
        # ignore protocoll
        self.__sock_name = sock_name
        zmq_context = kwargs.get("zmq_context", None)
        if zmq_context or kwargs.get("zmq", False):
            if zmq_context is None:
                zmq_context = zmq.Context()
            self.__zmq_sock = zmq_context.socket(zmq.PUSH)
            self.__zmq_sock.connect(zmq_socket_name(sock_name, check_ipc_prefix=True))
            self.__protocol = None
        else:
            self.__protocol = error_protocol()
            self.__zmq_sock = None
    def write(self, err_str):
        pid, t_dict = (os.getpid(), {
            "IOS_type"  : "error",
            "error_str" : err_str,
            "pid"       : os.getpid()})
        if os.path.isdir("/proc/%d" % (pid)):
            try:
                stat_lines = [(entry.split() + ["", ""])[0 : 2] for entry in file("/proc/%d/status" % (pid), "r").read().split("\n")]
            except:
                pass
            else:
                for what, rest in stat_lines:
                    r_what = what.lower()[:-1]
                    if rest.isdigit() and len(rest) < 10:
                        t_dict[r_what] = int(rest)
                    else:
                        t_dict[r_what] = rest
        if self.__protocol:
            self.__protocol.out_buffer.append(cPickle.dumps(t_dict))
            reactor.connectUNIXDatagram(self.__sock_name, self.__protocol)
        else:
            self.__zmq_sock.send(cPickle.dumps(t_dict))
    def close(self):
        if self.__zmq_sock:
            self.__zmq_sock.close()
        del self.__protocol
    def flush(self):
        pass
    def __del__(self):
        pass

if __name__ == "__main__":
    print "Loadable module, exiting ..."
    sys.exit(0)
