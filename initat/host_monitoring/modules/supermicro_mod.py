#!/usr/bin/python-init -Ot
#
# Copyright (C) 2013 Andreas Lang-Nevyjel, init.at
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
""" checks for Supermicro Hardware (using SMCIPMITool and others) """

import sys
import re
import commands
from initat.host_monitoring import limits, hm_classes
import os
import os.path
import time
import datetime
import logging_tools
import server_command
import pprint
import base64
import marshal
import bz2

SMCIPMI_BIN = "/sbin/SMCIPMITool"

class _general(hm_classes.hm_module):
    pass

def generate_dict(in_list):
    r_dict = {}
    cur_mode, sense_flag, handle_lines = (None, True, False)
    for line in in_list:
        parts = line.lower().strip().split()
        if sense_flag:
            if parts:
                cur_mode = parts[0]
                handle_lines = line.endswith(")")
                if handle_lines:
                    cur_mode = parts[0]
                    num_present, num_possible = [int(entry) for entry in line.split("(")[1].split(")")[0].split("/")]
                    cur_dict = {"possible" : num_possible,
                                "present"  : num_present}
                    r_dict[cur_mode] = cur_dict
                offset = 0
                sense_flag = False
        else:
            if not parts:
                sense_flag = True
            else:
                if handle_lines:
                    offset += 1
                    if offset == 2:
                        cur_map = [entry.strip() for entry in line.lower().split("|")]
                    elif offset > 3:
                        parts = [entry.strip() for entry in line.lower().split("|")]
                        num = int(parts[0].split()[-1])
                        loc_dict = dict(zip(cur_map, parts))
                        cur_dict[num] = loc_dict
    return r_dict

class smcipmi_struct(hm_classes.subprocess_struct):
    class Meta:
        max_usage = 128
        id_str = "supermicro"
        verbose = True
    def __init__(self, log_com, srv_com, target_host, login, passwd, command):
        self.__log_com = log_com
        hm_classes.subprocess_struct.__init__(
            self,
            srv_com,
            "%s %s %s %s %s" % (
                SMCIPMI_BIN,
                target_host,
                login,
                passwd,
                command),
        )
    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        self.__log_com("[smcipmi] %s" % (what), level)
    def process(self):
        if self.run_info["result"]:
            self.srv_com["result"].attrib.update({
                "reply" : "error (%d): %s" % (self.run_info["result"], self.read().strip()),
                "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR)})
        else:
            output = self.read()
            self.srv_com["output"] = output
 
class smcipmi_command(hm_classes.hm_command):
    info_str = "SMCIPMITool frontend"
    def __init__(self, name):
        hm_classes.hm_command.__init__(self, name, server_arguments=True, positional_arguments=True)
        self.server_parser.add_argument("--user", dest="user", type=str, default="ADMIN")
        self.server_parser.add_argument("--passwd", dest="passwd", type=str, default="ADMIN")
        self.server_parser.add_argument("--ip", dest="ip", type=str)
    def __call__(self, srv_com, cur_ns):
        args = cur_ns.arguments
        if not len(args):
            srv_com["result"].attrib.update({
                "reply" : "no arguments specified",
                "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR)})
            cur_smcc = None
        else:
            com = args[0]
            real_com = {
                "counter" : "system",
                "power"   : "power status",
                "gigabit" : "gigabit status",
                "blade"   : "blade status",
                "ib"      : "ib status",
                "cmm"     : "cmm status",
            }.get(com, com)
            srv_com["orig_command"] = com
            srv_com["mapped_command"] = real_com
            self.log("mapping command '%s' to '%s'" % (com, real_com))
            cur_smcc = smcipmi_struct(
                self.log,
                srv_com,
                cur_ns.ip,
                cur_ns.user,
                cur_ns.passwd,
                real_com,
            )
        return cur_smcc
    def _handle_power(self, in_dict):
        if in_dict["power"] == "on":
            ret_state = limits.nag_STATE_OK
        else:
            ret_state = limits.nag_STATE_CRITICAL
        cur_temp = float(in_dict["temp."].split("/")[0][:-1])
        cur_ac = float(in_dict["ac"][:-1])
        return ret_state, "PS '%s' is %s, temp: %.2f C, fan1/2: %d/%d, %.2f A | temp=%.2f amps=%.2f" % (
            in_dict["ps"],
            in_dict["power"],
            cur_temp,
            int(in_dict["fan 1"]),
            int(in_dict["fan 2"]),
            cur_ac,
            cur_temp, 
            cur_ac,
        )
    def _handle_blade(self, in_dict):
        if in_dict["power"] == "on" or in_dict["error"]:
            ret_state = limits.nag_STATE_OK
        else:
            ret_state = limits.nag_STATE_CRITICAL
        return ret_state, "blade '%s' is %s (%s)" % (
            in_dict["blade"],
            in_dict["power"],
            in_dict["error"] if in_dict["error"] else "no error",
        )
    def interpret(self, srv_com, cur_ns):
        orig_com, mapped_com = (
            srv_com.xpath(None, ".//ns:orig_command/text()")[0],
            srv_com.xpath(None, ".//ns:mapped_command/text()")[0],
        )
        r_dict = generate_dict(srv_com.xpath(None, ".//ns:output/text()")[0].split("\n"))
        if orig_com == "counter":
            return limits.nag_STATE_OK, ", ".join(["%s : %d of %d" % (
                key,
                value["present"],
                value["possible"]) for key, value in r_dict.iteritems()])
        else:
            # get number
            obj_type = orig_com
            obj_num = int(srv_com.xpath(None, ".//ns:arguments/ns:rest/text()")[0].strip().split()[-1])
            obj_key = {"ib" : "ibqdr"}.get(obj_type, obj_type)
            if obj_key in r_dict:
                if obj_num in r_dict[obj_key]:
                    return getattr(self, "_handle_%s" % (obj_type))(r_dict[obj_key][obj_num])
                else:
                    return limits.nag_STATE_CRITICAL, "no %s#%d found" % (
                        obj_key,
                        obj_num,
                    )
            else:
                return limits.nag_STATE_CRITICAL, "key %s not found in %s" % (
                    obj_key,
                    ", ".join(sorted(r_dict.keys())) or "EMPTY")
        return limits.nag_STATE_OK, "ok"
        
if __name__ == "__main__":
    print "This is a loadable module."
    sys.exit(0)
