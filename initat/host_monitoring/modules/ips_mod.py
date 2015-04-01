#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008 lang-nevyjel@init.at
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

IPS_BIN = "/usr/sbin/ipssend"

class my_modclass(hm_classes.hm_fileinfo):
    def __init__(self, **args):
        hm_classes.hm_fileinfo.__init__(self,
                                        "ips",
                                        "provides a interface to check the status of ips-driven controllers (ServerRAID)",
                                        **args)
    def init(self, mode, logger, basedir_name, **args):
        if mode == "i":
            self.__ctrl_dict = {}
    def _exec_command(self, com, logger):
        stat, out = commands.getstatusoutput(com)
        if stat:
            logger.warning("cannot execute %s (%d): %s" % (com, stat, out))
            out = ""
        return out.split("\n")
    def init_ctrl_dict(self, logger):
        if not self.__ctrl_dict:
            logger.info("Searching for ips-controllers")
            result = self._exec_command("%s getversion" % (IPS_BIN), logger)
            num_ctrl = len([True for line in result if line.lower().count("controller number")])
            if num_ctrl:
                for ctrl_num in range(1, num_ctrl + 1):
                    ctrl_stuff = {"last_al_lines" : []}
                    # get config for every controller
                    c_result = self._exec_command("%s getconfig %d AD" % (IPS_BIN, ctrl_num), logger)
                    ctrl_stuff["config"] = {}
                    for key, val in [self._split_config_line(line) for line in c_result if line.count(":")]:
                        ctrl_stuff["config"][key] = val
                    self.__ctrl_dict[ctrl_num] = ctrl_stuff
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
    def update_ctrl_dict(self, logger):
        for ctrl_num, ctrl_stuff in self.__ctrl_dict.iteritems():
            al_result = self._exec_command("%s getconfig %d AL" % (IPS_BIN, ctrl_num), logger)
            if al_result != ctrl_stuff["last_al_lines"]:
                ctrl_config = {"logical"  : {},
                               "array"    : {},
                               "channel"  : {},
                               "physical" : []}
                ctrl_stuff["last_al_lines"] = al_result
                act_part, prev_line = ("", "")
                for line in al_result:
                    ls = line.strip()
                    lsl = ls.lower()
                    if prev_line.startswith("-" * 10) and line.endswith("information"):
                        act_part = " ".join(line.split()[0:2]).lower().replace(" ", "_")
                    elif line.lower().startswith("command complet") or line.startswith("-" * 10):
                        pass
                    else:
                        if act_part == "logical_drive":
                            if line.lower().count("drive number"):
                                act_log_drv_num = int(line.split()[-1])
                                ctrl_config["logical"][act_log_drv_num] = {}
                            elif line.lower().strip().startswith("array"):
                                array_name = ls.split()[1]
                                ctrl_config["array"][array_name] = " ".join(line.lower().strip().split()[2:])
                            elif line.count(":"):
                                key, val = self._split_config_line(line)
                                ctrl_config["logical"][act_log_drv_num][key] = val
                        elif act_part == "physical_device":
                            if lsl.startswith("channel #"):
                                act_channel_num = int(lsl[-2])
                                ctrl_config["channel"][act_channel_num] = {}
                            elif lsl.startswith("initiator"):
                                ctrl_config["channel"][act_channel_num][int(lsl.split()[-1])] = " ".join(lsl.split()[:-4])
                            elif lsl.startswith("target"):
                                act_scsi_id = int(lsl.split()[-1])
                                act_scsi_stuff = {}
                                act_scsi_stuff["channel"] = act_channel_num
                                ctrl_config["channel"][act_channel_num][act_scsi_id] = act_scsi_stuff
                                ctrl_config["physical"].append(act_scsi_stuff)
                            elif line.count(":"):
                                key, val = self._split_config_line(line)
                                act_scsi_stuff[key] = val
                        #print act_part, line
                    prev_line = line
                ctrl_stuff["config"] = ctrl_config
    def get_ctrl_config(self, c_num = None):
        if c_num is None:
            return dict([(num, self.get_ctrl_config(num)) for num in self.__ctrl_dict.keys()])
        else:
            return self.__ctrl_dict[c_num]["config"]

def get_short_state(in_state):
    return in_state.split("(")[1].split(")")[0].lower()
                    
class ips_status_command(hm_classes.hmb_command):
    def __init__(self, **args):
        hm_classes.hmb_command.__init__(self, "ips_status", **args)
        self.help_str = "returns the status of the connected IPS-devices"
        self.cache_timeout = 600
        self.is_immediate = False
    def server_call(self, cm):
        if not os.path.isfile(IPS_BIN):
            return "error no ipssend-binary found in %s" % (os.path.dirname(IPS_BIN))
        self.module_info.init_ctrl_dict(self.logger)
        self.module_info.update_ctrl_dict(self.logger)
        return "ok %s" % (hm_classes.sys_to_net(self.module_info.get_ctrl_config()))
    def client_call(self, result, parsed_coms):
        if result.startswith("ok "):
            ret_dict = hm_classes.net_to_sys(result[3:])
            num_warn, num_error = (0, 0)
            ret_f = []
            for c_num, c_stuff in ret_dict.iteritems():
                act_field = []
                if c_stuff["logical"]:
                    log_field = ["ld%d: %d (%s)" % (l_num, l_stuff["size_(in_mb)"], get_short_state(l_stuff["status_of_logical_drive"])) for l_num, l_stuff in c_stuff["logical"].iteritems()]
                    act_field.append(",".join(log_field))
                if c_stuff["physical"]:
                    phys_field = []
                    for phys in c_stuff["physical"]:
                        s_state = get_short_state(phys["state"])
                        if s_state == "sby":
                            # ignore empty standby bays
                            pass
                        else:
                            if s_state not in ["onl", "hsp"]:
                                num_error += 1
                            phys_field.append("c%d/id%d: %s" % (phys["channel"], phys["scsi_id"], s_state))
                    act_field.append(",".join(phys_field))
                if act_field:
                    ret_f.append("c%d: %s" % (c_num, ", ".join(act_field)))
                else:
                    num_error += 1
                    ret_f.append("c%d: no information found" % (c_num))
                if num_error:
                    ret_state, ret_str = (limits.nag_STATE_CRITICAL, "ERROR")
                elif num_warn:
                    ret_state, ret_str = (limits.nag_STATE_WARNING, "WARNING")
                else:
                    ret_state, ret_str = (limits.nag_STATE_OK, "OK")
            if not ret_f:
                return limits.nag_STATE_WARNING, "no controller information found"
            else:
                return ret_state, "%s: %s" % (ret_str, "; ".join(ret_f))
        else:
            return limits.nag_STATE_CRITICAL, "error %s" % (result)

if __name__ == "__main__":
    print "This is a loadable module."
    sys.exit(0)

