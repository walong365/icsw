#!/usr/bin/python-init -Ot
#
# Copyright (c) 2012,2013 Andreas Lang-Nevyjel, lang-nevyjel@init.at
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
import logging_tools
import os
import process_tools
import server_command
import sys
import time
import zmq
from lxml import etree

def main():
    parser = argparse.ArgumentParser("send command to servers of the init.at Clustersoftware")
    parser.add_argument("arguments", nargs="+", help="additional arguments, first one is command")
    parser.add_argument("-t", help="set timeout [%(default)d]", default=10, type=int, dest="timeout")
    parser.add_argument("-p", help="port [%(default)d]", default=2001, dest="port", type=int)
    parser.add_argument("-P", help="protocoll [%(default)s]", type=str, default="tcp", choices=["tcp", "ipc"], dest="protocoll")
    parser.add_argument("-S", help="servername [%(default)s]", type=str, default="collrelay", dest="server_name")
    parser.add_argument("-H", help="host [%(default)s] or server", default="localhost", dest="host")
    parser.add_argument("-v", help="verbose mode [%(default)s]", default=False, dest="verbose", action="store_true")
    parser.add_argument("-i", help="set identity substring [%(default)s]", type=str, default="sc", dest="identity_string")
    parser.add_argument("-n", help="set number of iterations [%(default)d]", type=int, default=1, dest="iterations")
    parser.add_argument("--raw", help="do not convert to server_command", default=False, action="store_true")
    parser.add_argument("--root", help="connect to root-socket [%(default)s]", default=False, action="store_true")
    parser.add_argument("--kv", help="key-value pair, colon-separated", action="append")
    #parser.add_argument("arguments", nargs="+", help="additional arguments")
    ret_state = 1
    args, other_args = parser.parse_known_args()
    #print args.arguments, other_args
    command = args.arguments.pop(0)
    other_args = args.arguments + other_args
    identity_str = process_tools.zmq_identity_str(args.identity_string)
    zmq_context = zmq.Context(1)
    client = zmq_context.socket(zmq.DEALER)#ROUTER)#DEALER)
    client.setsockopt(zmq.IDENTITY, identity_str)
    client.setsockopt(zmq.LINGER, args.timeout)
    if args.protocoll == "ipc":
        if args.root:
            process_tools.ALLOW_MULTIPLE_INSTANCES = False
        conn_str = "%s" % (process_tools.get_zmq_ipc_name(args.host, s_name=args.server_name, connect_to_root_instance=args.root))
    else:
        conn_str = "%s://%s:%d" % (args.protocoll, args.host, args.port)
    if args.verbose:
        print "Identity_string is '%s', connection_string is '%s'" % (identity_str, conn_str)
    client.connect(conn_str)
    for cur_iter in xrange(args.iterations):
        if args.verbose:
            print "iteration %d" % (cur_iter)
        if args.raw:
            srv_com = command
        else:
            srv_com = server_command.srv_command(command=command)
            if args.kv:
                for kv_pair in args.kv:
                    key, value = kv_pair.split(":")
                    srv_com[key] = value
        for arg_index, arg in enumerate(other_args):
            if args.verbose:
                print " arg %2d: %s" % (arg_index, arg)
                srv_com["arguments:arg%d" % (arg_index)] = arg
        if not args.raw:
            srv_com["arg_list"] = " ".join(other_args)
        s_time = time.time()
        client.send_unicode(unicode(srv_com))
        if client.poll(args.timeout * 1000):
            recv_str = client.recv()
            timeout  = False
        else:
            print "error timeout"
            timeout = True
        e_time = time.time()
        if args.verbose:
            if timeout:
                print "communication took %s" % (
                    logging_tools.get_diff_time_str(e_time - s_time),
                )
            else:
                print "communication took %s, received %d bytes" % (
                    logging_tools.get_diff_time_str(e_time - s_time),
                    len(recv_str),
                )
        if not timeout:
            try:
                srv_reply = server_command.srv_command(source=recv_str)
            except:
                print "cannot interpret reply: %s" % (process_tools.get_except_info())
                print "reply was: %s" % (recv_str)
                eet_state = 1
            else:
                if args.verbose:
                    print
                    print "XML response:"
                    print
                    print srv_reply.pretty_print()
                    print
                if "result" in srv_reply:
                    print srv_reply["result"].attrib["reply"]
                    ret_state = int(srv_reply["result"].attrib["state"])
                elif len(srv_reply.xpath(None, ".//nodestatus")):
                    print srv_reply.xpath(None, ".//nodestatus")[0].text
                    ret_state = 0
                else:
                    print "no result tag found in reply"
                    ret_state = 2
    client.close()
    sys.exit(ret_state)

if __name__ == "__main__":
    main()
