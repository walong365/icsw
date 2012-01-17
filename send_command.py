#!/usr/bin/python-init -Ot
#
# Copyright (c) 2001,2002,2003,2004,2005,2006,2007,2008,2011 Andreas Lang-Nevyjel, lang-nevyjel@init.at
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
""" sends a command to one of the python-servers """

import sys
import net_tools
import time
import os
import os.path
import server_command
import logging_tools
import configfile
from lxml import etree
import zmq

def main():
    ret_state = 1
    my_config = configfile.configuration("send_command",
                                         [("PORT"           , configfile.int_c_var(8012, help_string="port [%(default)d]", short_options="p")),
                                          ("HOST"           , configfile.str_c_var("localhost", help_string="target host [%(default)s]")),
                                          ("PROTOCOLL"      , configfile.str_c_var("tcp", help_string="protocoll [%(default)s]", short_options="P")),
                                          ("RETRY"          , configfile.int_c_var(1, help_string="number of retries [%(default)d]", short_options="n")),
                                          ("MEASURE"        , configfile.bool_c_var(False, help_string="measuer execution time [%(default)s]")),
                                          ("TIMEOUT"        , configfile.int_c_var(10, help_string="timeout in seconds [%(default)d]", short_options="t")),
                                          ("IDENTITY_STRING", configfile.str_c_var("sc", help_string="set identity substring [%(default)s]")),
                                          ("ZMQ"            , configfile.bool_c_var(False, help_string="enable 0MQ mode [%(default)s]")),
                                          ("SRV_COM_MODE"   , configfile.bool_c_var(True, help_string="disbale server command mode [%(default)s], always True for 0MQ", short_options="S"))])
    options = my_config.handle_commandline(add_writeback_option=False, positional_arguments=True)
##    print options.PROTO
##    print my_config["PROTO"]
##    print my_config
##    try:
##        opts, args = getopt.getopt(sys.argv[1:], "T:t:hmMdDn:cH:ep:", ["help"])
##    except:
##        print "error"
##        sys.exit(1)
##    else:
##        if not args and not opts:
##            opts = [("-h", "")]
##        timeout, de_pickle, pre_pickle, num, srv_com_mode, host_dict, meassure_time, protocoll = (10., False, False, 1, True, {}, 0, 1)
##        s_t = "tcp"
##        for opt, arg in opts:
##            if opt in ["-h", "--help"]:
##                print "Usage: %s [ -H Hosts ] [ -T type ] [ -t timeout ] [ -n NUM ] [ -p PROTO ] [ -h | --help ] [ -m ] [ -M ] host port command [KEY:VALUE] [KEY:VALUE] ..." % (os.path.basename(sys.argv[0]))
##                print "  default timeout is %d seconds" % (timeout)
##                print "  -M, -D enables pickeling for sending (only valid for non-server_command mode)"
##                print "  -m, -d enables depickeling for receiving (only valid for non-server_command mode)"
##                print "  -n sets number of retries"
##                print "  -t sets timeout"
##                print "  -T sets send_type (t)cp or (u)dp, default is (%s)%s" % (s_t[0], s_t[1:])
##                print "  -c enables non-server_command mode"
##                print "  -H HOSTS comma-separated list of hosts, each host can have a colon separated option (i.e. rom00:off,rom01)"
##                print "  -e meassure execution time"
##                print "  -p PROTO sets protocoll, default is %d" % (protocoll)
##                sys.exit(-1)
##            if opt == "-p":
##                protocoll = int(arg)
##            if opt == "-e":
##                meassure_time = 1
##            if opt == "-H":
##                host_dict = dict([(x.split(":", 1) + [""])[0:2] for x in arg.split(",")])
##            if opt == "-T":
##                if arg == "t":
##                    s_t = "tcp"
##                elif arg == "u":
##                    s_t = "udp"
##                else:
##                    print "Cannot parse type '%s'" % (arg)
##                    sys.exit(-1)
##            if opt == "-t":
##                try:
##                    timeout = float(arg)
##                except:
##                    print "cannot parse timeout %s" % (arg)
##                    sys.exit(-1)
##            if opt == "-c":
##                srv_com_mode = False
##            if opt in ["-m", "-d"]:
##                de_pickle = True
##            if opt in ["-M", "-D"]:
##                pre_pickle = True
##            if opt == "-n":
##                num = int(arg)
##        if len(args) < 3:
##            print "Need more arguments (%d given)" % (len(args))
##            sys.exit(-1)
    start_time = time.time()
    if my_config["ZMQ"]:
        conn_str = "%s://%s:%d" % (my_config["PROTOCOLL"],
                                   my_config["HOST"],
                                   my_config["PORT"])
        srv_com = server_command.srv_command(command=" ".join(options.arguments))
        cur_context = zmq.Context()
        result = net_tools.zmq_connection(my_config["IDENTITY_STRING"], timeout=my_config["TIMEOUT"], context=cur_context).add_connection(conn_str, srv_com)
        if result is not None:
            print etree.tostring(result.tree, pretty_print=True)
        else:
            print "cannot connect"
        cur_context.term()
    else:
        de_pickle, pre_pickle = True, True
        protocoll = 1
        args = options.arguments
        if not my_config["SRV_COM_MODE"]:
            if pre_pickle:
                command = server_command.sys_to_net({"command" : args[0], "args" : args[1:]})
            else:
                command = " ".join(args)
        else:
            command = server_command.server_command(command=args[0])
##            command.set_nodes(host_dict.keys())
##            for t_host, host_com in host_dict.iteritems():
##                if host_com:
##                    command.set_node_command(t_host, host_com)
            opt_dict = {}
            if len(args) > 1:
                command.set_option_dict(dict([x.split(":", 1) for x in args[1:] if len(x.split(":")) > 1]))
        for idx in range(my_config["RETRY"]):
            if my_config["PROTOCOLL"] == "tcp":
                errnum, data = net_tools.single_connection(mode="tcp", host=my_config["HOST"], port=my_config["PORT"], command=command, timeout=my_config["TIMEOUT"], protocoll=protocoll).iterate()
            else:
                errnum, data = net_tools.single_connection(mode="udp", host=my_config["HOST"], port=my_config["PORT"], command=command, timeout=my_config["TIMEOUT"], protocoll=protocoll).iterate()
            if errnum:
                print "error: %d %s" % (errnum, data)
            else:
                if not my_config["SRV_COM_MODE"]:
                    if de_pickle:
                        if data.startswith("ok"):
                            print server_command.net_to_sys(data[3:])
                        else:
                            print data
                    else:
                        print "Got: %s" % (data)
                else:
                    try:
                        server_reply = server_command.server_reply(data)
                    except ValueError:
                        print "Error: got no valid server_reply (got: '%s')" % (data)
                    else:
                        ret_state, result = server_reply.get_state_and_result()
                        node_res, opt_dict = (server_reply.get_node_results(),
                                              server_reply.get_option_dict())
                        print "res: %s%s" % (result, node_res and ", %s" % (", ".join(["%s: %s" % (key, value) for key, value in node_res.iteritems()])) or "")
                        if opt_dict:
                            print "%s found:" % (logging_tools.get_plural("key", len(opt_dict.keys())))
                            for key, value in opt_dict.iteritems():
                                print " - ", key, value
                break
    end_time = time.time()
    if my_config["MEASURE"]:
        print "took %s" % (logging_tools.get_diff_time_str(end_time - start_time))
    sys.exit(ret_state)

if __name__ == "__main__":
    main()
