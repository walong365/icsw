#!/usr/bin/python-init -Ot
#
# Copyright (c) 2012-2014 Andreas Lang-Nevyjel, lang-nevyjel@init.at
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

from lxml import etree # @UnresolvedImports
import argparse
import logging_tools
import process_tools
import server_command
import sys
import time
import zmq

def main():
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
    # parser.add_argument("arguments", nargs="+", help="additional arguments")
    ret_state = 1
    args, other_args = parser.parse_known_args()
    if args.quiet:
        args.verbose = False
    # print args.arguments, other_args
    command = args.arguments.pop(0)
    other_args = args.arguments + other_args
    if args.identity_string:
        identity_str = args.identity_string
    else:
        identity_str = process_tools.zmq_identity_str(args.identity_substring)
    zmq_context = zmq.Context(1)
    s_type = "DEALER" if not args.split else "PUSH"
    client = zmq_context.socket(getattr(zmq, s_type))
    client.setsockopt(zmq.IDENTITY, identity_str)
    client.setsockopt(zmq.LINGER, args.timeout)
    if args.protocoll == "ipc":
        if args.root:
            process_tools.ALLOW_MULTIPLE_INSTANCES = False
        conn_str = "{}".format(process_tools.get_zmq_ipc_name(args.host, s_name=args.server_name, connect_to_root_instance=args.root))
    else:
        conn_str = "{}://{}:{:d}".format(args.protocoll, args.host, args.port)
    if args.split:
        recv_conn_str = "{}".format(process_tools.get_zmq_ipc_name(args.split, s_name=args.server_name, connect_to_root_instance=args.root))
        recv_sock = zmq_context.socket(zmq.ROUTER)
        recv_sock.setsockopt(zmq.IDENTITY, identity_str)
        recv_sock.setsockopt(zmq.LINGER, args.timeout)
    else:
        recv_sock = None
    if args.verbose:
        print("socket_type is {}\nIdentity_string is '{}'\nconnection_string is '{}'".format(
            s_type,
            identity_str,
            conn_str)
        )
        if args.split:
            print("receive connection string is '{}'".format(recv_conn_str))
    try:
        client.connect(conn_str)
    except:
        print(
            "error connecting to {}: {}".format(
                conn_str,
                process_tools.get_except_info()
            )
        )
        sys.exit(-1)
    if recv_sock:
        recv_sock.connect(recv_conn_str)
    for cur_iter in xrange(args.iterations):
        if args.verbose:
            print("iteration {:d}".format(cur_iter))
        if args.raw:
            srv_com = command
        else:
            srv_com = server_command.srv_command(command=command)
            srv_com["identity"] = identity_str
            if args.kv:
                for kv_pair in args.kv:
                    if kv_pair.count(":"):
                        key, value = kv_pair.split(":", 1)
                        if args.kv_path:
                            srv_com["{}:{}".format(args.kv_path, key)] = value
                        else:
                            srv_com[key] = value
                    else:
                        print("cannot parse key '{}'".format(kv_pair))
            if args.kva:
                for kva_pair in args.kva:
                    key, attr, value = kva_pair.split(":")
                    if args.kv_path:
                        srv_com["{}:{}".format(args.kv_path, key)].attrib[attr] = value
                    else:
                        srv_com[key].attrib[attr] = value
        for arg_index, arg in enumerate(other_args):
            if args.verbose:
                print(" arg {:2d}: {}".format(arg_index, arg))
            srv_com["arguments:arg{:d}".format(arg_index)] = arg
        # not in raw mode, arg_list must always be set (even if empty)
        if not args.raw:
            srv_com["arg_list"] = " ".join(other_args)
        s_time = time.time()
        client.send_unicode(unicode(srv_com))
        if args.verbose:
            if args.raw:
                print(srv_com)
            else:
                print(srv_com.pretty_print())
        if not args.only_send:
            r_client = client if not recv_sock else recv_sock
            if r_client.poll(args.timeout * 1000):
                recv_str = r_client.recv()
                if r_client.getsockopt(zmq.RCVMORE):
                    recv_id = recv_str
                    recv_str = r_client.recv()
                else:
                    recv_id = ""
                timeout = False
            else:
                print("error timeout")
                timeout = True
            e_time = time.time()
            if args.verbose:
                if timeout:
                    print("communication took {}".format(
                        logging_tools.get_diff_time_str(e_time - s_time),
                    ))
                else:
                    print("communication took {}, received {:d} bytes".format(
                        logging_tools.get_diff_time_str(e_time - s_time),
                        len(recv_str),
                    ))
            if not timeout:
                try:
                    srv_reply = server_command.srv_command(source=recv_str)
                except:
                    print("cannot interpret reply: {}".format(process_tools.get_except_info()))
                    print("reply was: {}".format(recv_str))
                    ret_state = 1
                else:
                    if args.verbose:
                        print
                        print "XML response (id: '{}'):".format(recv_id)
                        print
                        print srv_reply.pretty_print()
                        print
                    if "result" in srv_reply:
                        if not args.quiet:
                            print srv_reply["result"].attrib["reply"]
                        ret_state = int(srv_reply["result"].attrib["state"])
                    elif len(srv_reply.xpath(".//nodestatus", smart_strings=False)):
                        print srv_reply.xpath(".//nodestatus", smart_strings=False)[0].text
                        ret_state = 0
                    else:
                        print "no result tag found in reply"
                        ret_state = 2
    client.close()
    if recv_sock:
        recv_sock.close()
    zmq_context.term()
    sys.exit(ret_state)

if __name__ == "__main__":
    main()
