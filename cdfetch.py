#!/usr/bin/python-init -Ot
#
# Copyright (c) 2013 Andreas Lang-Nevyjel, lang-nevyjel@init.at
#
# this file is part of collectd-init
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
""" connect to a given collectd-server and fetch some data """

import argparse
import logging_tools
import os
import process_tools
import server_command
import sys
import time
import zmq
from lxml import etree # @UnresolvedImports
from initat.host_monitoring.hm_classes import mvect_entry

class base_com(object):
    def __init__(self, options, *args):
        self.options = options
        srv_com = server_command.srv_command(command=self.Meta.command)
        srv_com["identity"] = process_tools.zmq_identity_str(self.options.identity_string)
        for arg_index, arg in enumerate(args):
            if self.options.verbose:
                print " arg %2d: %s" % (arg_index, arg)
                srv_com["arguments:arg%d" % (arg_index)] = arg
        srv_com["arg_list"] = " ".join(args)
        srv_com["host_filter"] = self.options.host_filter
        srv_com["key_filter"] = self.options.key_filter
        self.srv_com = srv_com #
        self.ret_state = 1
    def __getitem__(self, key):
        return self.srv_com[key]
    def __unicode__(self):
        return unicode(self.srv_com)
    def send_and_receive(self, client):
        conn_str = "tcp://%s:%d" % (self.options.host, self.options.port)
        if self.options.verbose:
            print "Identity_string is '%s', connection_string is '%s'" % (self.srv_com["identity"].text, conn_str)
        client.connect(conn_str)
        s_time = time.time()

        client.send_unicode(unicode(self.srv_com))
        if self.options.verbose:
            print self.srv_com.pretty_print()
        r_client = client
        if r_client.poll(self.options.timeout * 1000):
            recv_str = r_client.recv()
            if r_client.getsockopt(zmq.RCVMORE):
                recv_id = recv_str
                recv_str = r_client.recv()
            else:
                recv_id = ""
            self.receive_tuple = (recv_id, recv_str)
            timeout = False
        else:
            print "error timeout (%.2f > %d)" % (time.time() - s_time, self.options.timeout)
            timeout = True
        e_time = time.time()
        if self.options.verbose:
            if timeout:
                print "communication took %s" % (
                    logging_tools.get_diff_time_str(e_time - s_time),
                )
            else:
                print "communication took %s, received %d bytes" % (
                    logging_tools.get_diff_time_str(e_time - s_time),
                    len(recv_str),
                )
        return True if not timeout else False
    def interpret(self):
        recv_id, recv_str = self.receive_tuple
        try:
            srv_reply = server_command.srv_command(source=recv_str)
        except:
            print "cannot interpret reply: %s" % (process_tools.get_except_info())
            print "reply was: %s" % (recv_str)
            self.ret_state = 1
        else:
            if self.options.verbose:
                print
                print "XML response (id: '%s'):" % (recv_id)
                print
                print srv_reply.pretty_print()
                print
            if "result" in srv_reply:
                if hasattr(self, "_interpret"):
                    # default value: everything OK
                    self.ret_state = 0
                    self._interpret(srv_reply)
                else:
                    print srv_reply["result"].attrib["reply"]
                    self.ret_state = int(srv_reply["result"].attrib["state"])
            else:
                print "no result tag found in reply"
                self.ret_state = 2

class host_list_com(base_com):
    class Meta:
        command = "host_list"
    def _interpret(self, srv_com):
        h_list = srv_com.xpath(None, ".//host_list")
        if len(h_list):
            h_list = h_list[0]
            print "got result for %s:" % (logging_tools.get_plural("host", int(h_list.attrib["entries"])))
            for host in h_list:
                print "%-30s (%-40s) : %4d keys, last update %s" % (
                    host.attrib["name"],
                    host.attrib["uuid"],
                    int(host.attrib["keys"]),
                    time.ctime(int(host.attrib["last_update"]))
                    )
            pass
        else:
            print "No host_list found in result"
            self.ret_state = 1

class key_list_com(base_com):
    class Meta:
        command = "key_list"
    def _interpret(self, srv_com):
        h_list = srv_com.xpath(None, ".//host_list")
        if len(h_list):
            h_list = h_list[0]
            print "got result for %s:" % (logging_tools.get_plural("host", int(h_list.attrib["entries"])))
            for host in h_list:
                print "%-30s (%-40s) : %4d keys, last update %s" % (
                    host.attrib["name"],
                    host.attrib["uuid"],
                    int(host.attrib["keys"]),
                    time.ctime(int(host.attrib["last_update"]))
                    )
                out_f = logging_tools.new_form_list()
                for num_key, key_el in enumerate(host):
                    cur_mv = mvect_entry(key_el.attrib.pop("name"), info="", **key_el.attrib)
                    out_f.append(cur_mv.get_form_entry(num_key + 1))
                print unicode(out_f)
        else:
            print "No host_list found in result"
            self.ret_state = 1

def main():
    parser = argparse.ArgumentParser("query the datastore of collectd servers")
    parser.add_argument("arguments", nargs="+", help="additional arguments, first one is command")
    parser.add_argument("-t", help="set timeout [%(default)d]", default=10, type=int, dest="timeout")
    parser.add_argument("-p", help="port [%(default)d]", default=8008, dest="port", type=int)
    parser.add_argument("-H", help="host [%(default)s] or server", default="localhost", dest="host")
    parser.add_argument("-v", help="verbose mode [%(default)s]", default=False, dest="verbose", action="store_true")
    parser.add_argument("-i", help="set identity substring [%(default)s]", type=str, default="cdf", dest="identity_string")
    parser.add_argument("--host-filter", help="set filter for host name [%(default)s]", type=str, default=".*", dest="host_filter")
    parser.add_argument("--key-filter", help="set filter for key name [%(default)s]", type=str, default=".*", dest="key_filter")
    # parser.add_argument("arguments", nargs="+", help="additional arguments")
    ret_state = 1
    args, other_args = parser.parse_known_args()
    # print args.arguments, other_args
    command = args.arguments.pop(0)
    other_args = args.arguments + other_args
    if "%s_com" % (command) in globals():
        try:
            cur_com = globals()["%s_com" % (command)](args, *other_args)
        except:
            print "error init '%s': %s" % (command, process_tools.get_except_info())
            sys.exit(ret_state)
    else:
        print "Unknown command '%s'" % (command)
        sys.exit(ret_state)
    zmq_context = zmq.Context(1)
    client = zmq_context.socket(zmq.DEALER) # if not args.split else zmq.PUB) # ROUTER)#DEALER)
    client.setsockopt(zmq.IDENTITY, cur_com["identity"].text)
    client.setsockopt(zmq.LINGER, args.timeout)
    was_ok = cur_com.send_and_receive(client)
    if was_ok:
        cur_com.interpret()
    client.close()
    zmq_context.term()
    sys.exit(cur_com.ret_state)

if __name__ == "__main__":
    main()
