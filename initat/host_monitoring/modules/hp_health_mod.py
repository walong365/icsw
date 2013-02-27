#!/usr/bin/python-init -Ot
#
# Copyright (C) 2011 lang-nevyjel@init.at
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
from initat.host_monitoring import limits
from initat.host_monitoring import hm_classes
import os
import os.path
import logging_tools
import pprint
import time

HPASM_BIN = "/sbin/hpasmcli"

class my_modclass(hm_classes.hm_fileinfo):
    def __init__(self, **args):
        hm_classes.hm_fileinfo.__init__(self,
                                        "hp_health",
                                        "provides a interface to check the status of HP-devices with hpasmcli installed",
                                        **args)
    def _exec_command(self, com, logger):
        stat, out = commands.getstatusoutput(com)
        if stat:
            logger.warning("cannot execute %s (%d): %s" % (com, stat, out))
            out = ""
        return out.split("\n")
    def call_hpasm_cli(self, command, logger):
        if os.path.exists(HPASM_BIN):
            s_time = time.time()
            ret_lines = self._exec_command("%s -s \"%s\"" % (HPASM_BIN,
                                                             command),
                                           logger)
            e_time = time.time()
            return ["ok %s" % (command),
                    "took %s" % (logging_tools.get_diff_time_str(e_time - s_time))] + ret_lines
        else:
            return ["error %s not found" % (HPASM_BIN)]
    def _split_config_line(self, line):
        key, val = line.split(":", 1)
        key = key.lower().strip().replace(" ", "_")
        val = val.strip()
        if val.isdigit():
            val = int(val)
        elif val.lower() == "enabled":
            val = True
        elif val.lower() == "disabled":
            val = False
        return key, val
                    
def get_short_state(in_state):
    return in_state.lower()

class hp_dimm_command(hm_classes.hmb_command):
    def __init__(self, **args):
        hm_classes.hmb_command.__init__(self, "hp_dimm", **args)
        self.help_str = "returns the status of the DIMMs"
    def server_call(self, cm):
        return "ok %s" % (hm_classes.sys_to_net(self.module_info.call_hpasm_cli("show dimm", self.logger)))
    def _interpret_result(self, in_list):
        dimm_dict = {"list"   : [],
                     "status" : "ok"}
        cur_dimm = None
        for line in in_list:
            if line.count(":"):
                key, value = [part.strip() for part in line.lower().split(":", 1)]
                if key.endswith("#"):
                    key = (key[:-1]).strip()
                if key.startswith("processor"):
                    if cur_dimm:
                        dimm_dict["list"].append(cur_dimm)
                    cur_dimm = {}
                cur_dimm[key] = value
                if key == "status" and value != "ok":
                    dimm_dict["status"] = value
        if cur_dimm:
            dimm_dict["list"].append(cur_dimm)
        return dimm_dict
    def client_call(self, result, parsed_coms):
        if result.startswith("ok "):
            ret_list = hm_classes.net_to_sys(result[3:])
            if ret_list[0].startswith("error"):
                return limits.nag_STATE_CRITICAL, ret_list[0]
            else:
                command = ret_list.pop(0)
                exec_time = ret_list.pop(0)
                dimm_dict = self._interpret_result(ret_list)
                ret_list = ["found %s" % (logging_tools.get_plural("DIMM", len(dimm_dict["list"])))]
                if dimm_dict["status"] == "ok":
                    ret_state = limits.nag_STATE_OK
                else:
                    ret_state = limits.nag_STATE_CRITICAL
                    for dimm in dimm_dict["list"]:
                        if dimm["status"] != "ok":
                            ret_list.append("DIMM module %s (processor %s, %s): %s" % (dimm["module"],
                                                                                       dimm["processor"],
                                                                                       dimm["size"],
                                                                                       dimm["status"]))
                return ret_state, "; ".join(ret_list)
        else:
            return limits.nag_STATE_CRITICAL, "error %s" % (result)

class hp_powersupply_command(hm_classes.hmb_command):
    def __init__(self, **args):
        hm_classes.hmb_command.__init__(self, "hp_powersupply", **args)
        self.help_str = "returns the status of the powersupplies"
    def server_call(self, cm):
        return "ok %s" % (hm_classes.sys_to_net(self.module_info.call_hpasm_cli("show powersupply", self.logger)))
    def _interpret_result(self, in_list):
        ps_dict = {"list"      : [],
                   "condition" : "ok"}
        cur_ps = None
        for line in in_list:
            if line.lower().startswith("power supply"):
                if cur_ps:
                    ps_dict["list"].append(cur_ps)
                cur_ps = {"num" : line.strip().split("#")[1]}
            if line.count(":"):
                key, value = [part.strip() for part in line.lower().split(":", 1)]
                cur_ps[key] = value
                if key == "condition" and value != "ok":
                    ps_dict["condition"] = value
        if cur_ps:
            ps_dict["list"].append(cur_ps)
        return ps_dict
    def client_call(self, result, parsed_coms):
        if result.startswith("ok "):
            ret_list = hm_classes.net_to_sys(result[3:])
            if ret_list[0].startswith("error"):
                return limits.nag_STATE_CRITICAL, ret_list[0]
            else:
                command = ret_list.pop(0)
                exec_time = ret_list.pop(0)
                ps_dict = self._interpret_result(ret_list)
                ret_list = ["found %s" % (logging_tools.get_plural("powersupply", len(ps_dict["list"])))]
                if ps_dict["condition"] == "ok":
                    ret_state = limits.nag_STATE_OK
                else:
                    ret_state = limits.nag_STATE_CRITICAL
                for ps in ps_dict["list"]:
                    if ps["condition"] == "ok":
                        ret_list.append("PS %s, %s" % (ps["num"],
                                                       ps["power"]))
                    else:
                        ret_list.append("PS %s, present: %s, condition: %s" % (ps["num"],
                                                                               ps["present"],
                                                                               ps["condition"]))
                return ret_state, "; ".join(ret_list)
        else:
            return limits.nag_STATE_CRITICAL, "error %s" % (result)

if __name__ == "__main__":
    print "This is a loadable module."
    sys.exit(0)

