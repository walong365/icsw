#!/usr/bin/python-init -Ot
#
# Copyright (C) 2008,2009,2010,2012 Andreas Lang-Nevyjel, init.at
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
""" special task for configuring openvpn """

import sys
import pprint
import re
import logging_tools
import pyipc
import struct
import os
import process_tools
import server_command
from host_monitoring import ipc_comtools

EXPECTED_FILE = "/etc/sysconfig/host-monitoring.d/openvpn_expected"

def parse_expected():
    ret_dict = {}
    if os.path.isfile(EXPECTED_FILE):
        in_field = open(EXPECTED_FILE, "r").read().split("\n")
        lines = [line.strip() for line in in_field if line.strip() and not line.strip().startswith("#")]
        for line in lines:
            if line.count("=") == 1:
                dev_name, dev_stuff = line.split("=", 1)
                dev_dict = {}
                ret_dict[dev_name.strip()] = dev_dict
                instances = dev_stuff.split()
                for instance in instances:
                    inst_parts = instance.split(":")
                    inst_dict = {}
                    dev_dict[inst_parts.pop(0)] = inst_dict
                    for inst_part in inst_parts:
                        c_parts = inst_part.split(",")
                        client_name = c_parts.pop(0)
                        inst_dict[client_name] = True
                        #inst_dict[client_name] = limits.nag_STATE_CRITICAL
                        #if c_parts and c_parts[0].lower() in ["w"]:
                        #    inst_dict[client_name] = limits.nag_STATE_WARNING
    return ret_dict

def handle(s_check, host, dc, build_proc, valid_ip, **kwargs):
    build_proc.mach_log("Starting special openvpn")
    exp_dict = parse_expected()
    if exp_dict.has_key(host["name"]):
        exp_dict = exp_dict[host["name"]]
    else:
        exp_dict = {}
    if not exp_dict:
        # no expected_dict found, try to get the actual config from the server
        srv_result = ipc_comtools.send_and_receive_zmq(valid_ip, "openvpn_status", server="collrelay", zmq_context=build_proc.zmq_context, port=2001)
        print unicode(srv_result)
        print "*" * 20
        try:
            res_ok, res_dict = ipc_comtools.send_and_receive(valid_ip, "openvpn_status", target_port=2001, decode=True)
        except:
            print "nogo"
            build_proc.mach_log("error getting open_status from %s: %s" % (valid_ip,
                                                                           process_tools.get_except_info()),
                                logging_tools.LOG_LEVEL_CRITICAL)
        else:
            print "go"
            if res_ok:
                build_proc.mach_log("error calling openvpn_status: %s" % (str(res_dict)),
                                    logging_tools.LOG_LEVEL_ERROR)
            else:
                # build exp_dict
                for inst_name in res_dict:
                    if res_dict[inst_name]["type"] == "server":
                        for c_name in res_dict[inst_name]["dict"]:
                            exp_dict.setdefault(inst_name, {})[c_name] = True
    sc_array = []
    for inst_name in sorted(exp_dict):
        for peer_name in sorted(exp_dict[inst_name]):
            sc_array.append(("OpenVPN peer %s on %s" % (peer_name, inst_name), [inst_name, peer_name]))
    if not sc_array:
        sc_array.append(("OpenVPN", ["ALL", "ALL"]))
    return sc_array

if __name__ == "__main__":
    print "Loadable module, exiting"
    sys.exit(0)
    