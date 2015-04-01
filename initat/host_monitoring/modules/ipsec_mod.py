#!/usr/bin/python-init -Ot
#
# Copyright (C) 2008,2009,2012 Andreas Lang-Nevyjel init.at
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

import sys
import commands
from initat.host_monitoring import limits, hm_classes
import os
import os.path
import logging_tools
import process_tools
import pprint
import time
import socket
import server_command

class _general(hm_classes.hm_module):
    def init_module(self):
        self._find_ipsec_command()
    def _find_ipsec_command(self):
        self.__ipsec_command = ""
        for s_dir in ["/bin", "/usr/bin", "/sbin", "/usr/sbin"]:
            if os.path.isfile("%s/ipsec" % (s_dir)):
                self.__ipsec_command = "%s/ipsec" % (s_dir)
                break
    def _exec_command(self, com):
        if com.startswith("."):
            if self.__ipsec_command:
                com = "%s %s" % (self.__ipsec_command, com[1:])
            else:
                self.log("no ipsec command found",
                         logging_tools.LOG_LEVEL_ERROR)
                com, out = ""
        if com:
            stat, out = commands.getstatusoutput(com)
            if stat:
                self.log("cannot execute %s (%d): %s" % (com, stat, out),
                         logging_tools.LOG_LEVEL_WARN)
                out = ""
        return out.split("\n")
    def _update_ipsec_status(self):
        # for strongswan
        act_out = self._exec_command(". statusall")
        con_dict = {}
        for line in act_out:
            parts = line.strip().split()
            if len(parts) > 1:
                parts.pop(0)
                first_key = parts.pop(0)
                if first_key.startswith('"'):
                    # connection related
                    con_key = first_key[1:-2]
                    con_dict.setdefault(con_key, {"flags" : [],
                                                  "keys" : {},
                                                  "sa_dict" : {}})
                    parts = [part.strip() for part in (" ".join(parts)).split(";") if part.strip()]
                    for part in parts:
                        if part.count(": "):
                            key, value = part.split(": ", 1)
                            if key.endswith(" proposal") and value.replace("N/A", "N_A").count("/") == 2:
                                value = [sub_value.replace("N_A", "N/A") for sub_value in value.replace("N/A", "N_A").split("/")]
                            elif key == "prio" and value.count(",") == 1:
                                value = value.split(",")
                            con_dict[con_key]["keys"][key] = value
                        else:
                            con_dict[con_key]["flags"].append(part)
                elif first_key.startswith("#"):
                    sa_key = int(first_key[1:-1])
                    con_key = parts.pop(0)
                    if con_key not in ["pending"]:
                        if con_key.count(":"):
                            con_key, port_num = con_key.split(":")
                        else:
                            port_num = "0"
                        con_key, port_num = (con_key[1:-1], int(port_num))
                        parts = [part.strip() for part in (" ".join(parts)).split(";") if part.strip()]
                        con_dict[con_key]["sa_dict"].setdefault(("con_%d.%d" % (sa_key, port_num)), []).extend(parts)
        return con_dict

class ipsec_status_command(hm_classes.hm_command):
    def __init__(self, name):
        hm_classes.hm_command.__init__(self, name, positional_arguments=True)
    def __call__(self, srv_com, cur_ns):
        srv_com["ipsec_status"] = self.module._update_ipsec_status()
    def interpret(self, srv_com, cur_ns):
        con_dict = srv_com["ipsec_status"]
        return self._interpret(con_dict, cur_ns)
    def interpret_old(self, result, parsed_coms):
        con_dict = hm_classes.net_to_sys(result[3:])
        return self._interpret(con_dict, parsed_coms)
    def _interpret(self, con_dict, cur_ns):
        if cur_ns.arguments:
            first_arg = cur_ns.arguments[0]
        else:
            first_arg = None
        if not first_arg:
            # overview
            if con_dict:
                ret_state, ret_list = (limits.nag_STATE_OK, [])
                for con_name in sorted(con_dict):
                    if "erouted" in con_dict[con_name]["flags"]:
                        ret_list.append("%s ok" % (con_name))
                    else:
                        ret_list.append("%s is not erouted" % (con_name))
                        ret_state = max(ret_state, limits.nag_STATE_CRITICAL)
                return ret_state, ", ".join(ret_list)
            else:
                return limits.nag_STATE_WARNING, "no connections defined"
        elif con_dict.has_key(first_arg):
            con_stuff = con_dict[first_arg]
            ret_state, ret_list = (limits.nag_STATE_OK, [])
            if "erouted" in con_stuff["flags"]:
                ret_list.append("is erouted")
                for key in con_stuff["keys"]:
                    if key.endswith("proposal"):
                        ret_list.append("%s: %s" % (key, "/".join(con_stuff["keys"][key])))
            else:
                ret_list.append("is not erouted")
                ret_state = max(ret_state, limits.nag_STATE_CRITICAL)
            return ret_state, "connection %s: %s" % (first_arg,
                                                     ", ".join(ret_list))
        else:
            return limits.nag_STATE_CRITICAL, "error connection '%s' not found (defined: %s)" % (first_arg,
                                                                                                 ", ".join(sorted(con_dict)) or "none")

if __name__ == "__main__":
    print "This is a loadable module."
    sys.exit(0)

