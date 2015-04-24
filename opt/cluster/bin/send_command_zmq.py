#!/usr/bin/python-init -Ot
#
# Copyright (c) 2012-2015 Andreas Lang-Nevyjel, lang-nevyjel@init.at
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
""" sends a command to one of the python-servers, 0MQ version"""

import argparse
from initat.tools import logging_tools
from initat.tools import process_tools
from initat.tools import server_command
import sys
import time
import zmq


def _get_parser():
    parser = argparse.ArgumentParser("send command to servers of the init.at Clustersoftware")
    parser.add_argument("arguments", nargs="+", help="additional arguments, first one is command")
    parser.add_argument("-t", help="set timeout [%(default)d]", default=10, type=int, dest="timeout")
    parser.add_argument("-p", help="port [%(default)d]", default=2001, dest="port", type=int)
    parser.add_argument("-P", help="protocoll [%(default)s]", type=str, default="tcp", choices=["tcp", "ipc"], dest="protocoll")
    parser.add_argument("-S", help="servername [%(default)s]", type=str, default="collrelay", dest="server_name")
    parser.add_argument("-H", help="host [%(default)s] or server", default="localhost", dest="host")
    parser.add_argument("-v", help="verbose mode [%(default)s]", default=False, dest="verbose", action="store_true")
    parser.add_argument("-i", help="set identity substring [%(default)s]", type=str, default="sc", dest="identity_substring")
    parser.add_argument("-I", help="set identity string [%(default)s], has precedence over -i", type=str, default="", dest="identity_string")
    parser.add_argument("-n", help="set number of iterations [%(default)d]", type=int, default=1, dest="iterations")
    parser.add_argument("-q", help="be quiet [%(default)s], overrides verbose", default=False, action="store_true", dest="quiet")
    parser.add_argument("--raw", help="do not convert to server_command", default=False, action="store_true")
    parser.add_argument("--root", help="connect to root-socket [%(default)s]", default=False, action="store_true")
    parser.add_argument("--kv", help="key-value pair, colon-separated [key:value]", action="append")
    parser.add_argument("--kva", help="key-attribute pair, colon-separated [key:attribute:value]", action="append")
    parser.add_argument("--kv-path", help="path to store key-value pairs under", type=str, default="")
    parser.add_argument("--split", help="set read socket (for split-socket command), [%(default)s]", type=str, default="")
    parser.add_argument("--only-send", help="only send command, [%(default)s]", default=False, action="store_true")
    return parser


class send_com(object):
    def __init__(self):
        self.ret_state = 0
        self.parser = _get_parser()
        self.zmq_context = zmq.Context(1)

    def parse(self):
        self.args, self.other_args = self.parser.parse_known_args()
        if self.args.quiet:
            self.args.verbose = False
        self.command = self.args.arguments.pop(0)
        self.other_args = self.args.arguments + self.other_args

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
            conn_str = "{}".format(process_tools.get_zmq_ipc_name(self.args.host, s_name=self.args.server_name, connect_to_root_instance=self.args.root))
        else:
            conn_str = "{}://{}:{:d}".format(self.args.protocoll, self.args.host, self.args.port)
        if self.args.split:
            recv_conn_str = "{}".format(process_tools.get_zmq_ipc_name(self.args.split, s_name=self.args.server_name, connect_to_root_instance=self.args.root))
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

    def send_and_receive(self):
        for cur_iter in xrange(self.args.iterations):
            self.verbose("iteration {:d}".format(cur_iter))
            srv_com = self._build_com()
            self.send(srv_com)
            if not self.args.only_send:
                _timeout, _recv_id, _recv_str = self.receive()
                if not _timeout:
                    self._handle_return(_recv_id, _recv_str)
            else:
                break

    def _build_com(self):
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


def main():
    my_com = send_com()
    my_com.parse()
    my_com.init_connection()
    if my_com.connect():
        my_com.send_and_receive()
    my_com.close()
    sys.exit(my_com.ret_state)

if __name__ == "__main__":
    main()
