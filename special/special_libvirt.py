#!/usr/bin/python-init -Ot
#
# Copyright (C) 2010,2012 Andreas Lang-Nevyjel, init.at
#
# this file is part of nagios-config-server
#
# Send feedback to: <lang-nevyjel@init.at>
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
""" special task for configuring libvirt """

import sys
import pprint
import re
import logging_tools
import pyipc
import struct
import os
import process_tools
from host_monitoring import ipc_comtools

def handle(s_check, host, dc, build_proc, valid_ip, global_config=None, **kwargs):
    act_com = "domain_overview"
    build_proc.mach_log("Starting special libvirt (%s), host_name %s" % (act_com,
                                                                         host["name"]))
    sc_array = []
    try:
        res_ok, res_dict = ipc_comtools.send_and_receive_zmq(valid_ip, act_com, port=2001, zmq_context=build_proc.zmq_context, server="collrelay")
    except:
        build_proc.mach_log("error getting %s from %s: %s" % (
            act_com,
            valid_ip,
            process_tools.get_except_info()),
                            logging_tools.LOG_LEVEL_CRITICAL)
    else:
        if res_ok:
            build_proc.mach_log("error calling %s: %s" % (
                act_com,
                str(res_dict)),
                                logging_tools.LOG_LEVEL_ERROR)
        else:
            if "running" in res_dict and "defined" in res_dict:
                res_dict = res_dict["running"]
            # build sc_array
            for inst_id in res_dict:
                d_dict = res_dict[inst_id]
                sc_array.append(("Domain %s" % (d_dict["name"]),
                                 [d_dict["name"]]))
    return sc_array

if __name__ == "__main__":
    print "Loadable module, exiting"
    sys.exit(0)
    