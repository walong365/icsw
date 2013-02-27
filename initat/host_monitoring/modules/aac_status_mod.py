#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008,2012 lang-nevyjel@init.at
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
import pprint

ARCCONF_BIN = "/usr/sbin/arcconf"

class _general(hm_classes.hm_module):
    def init_module(self):
        self.__ctrl_dict = {}
    def _exec_command(self, com, logger):
        stat, out = commands.getstatusoutput(com)
        if stat:
            logger.warning("cannot execute %s (%d): %s" % (com, stat, out))
            out = ""
        return out.split("\n")
    def init_ctrl_dict(self, logger):
        if not self.__ctrl_dict:
            logger.log("Searching for ips-controllers")
            result = self._exec_command("%s getversion" % (ARCCONF_BIN), logger)
            num_ctrl = len([True for line in result if line.lower().count("controller #")])
            if num_ctrl:
                for ctrl_num in range(1, num_ctrl + 1):
                    ctrl_stuff = {"last_al_lines" : []}
                    # get config for every controller
                    c_result = self._exec_command("%s getconfig %d AD" % (ARCCONF_BIN, ctrl_num), logger)
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
            al_result = self._exec_command("%s getconfig %d AL" % (ARCCONF_BIN, ctrl_num), logger)
            if al_result != ctrl_stuff["last_al_lines"]:
                ctrl_config = {"logical"    : {},
                               "array"      : {},
                               "channel"    : {},
                               "physical"   : [],
                               "controller" : {}}
                ctrl_stuff["last_al_lines"] = al_result
                act_part, prev_line = ("", "")
                for line in al_result:
                    ls = line.strip()
                    lsl = ls.lower()
                    if prev_line.startswith("-" * 10) and line.endswith("information"):
                        act_part = " ".join(line.split()[0:2]).lower().replace(" ", "_").replace("drive", "device")
                    elif line.lower().startswith("command complet") or line.startswith("-" * 10):
                        pass
                    else:
                        if act_part == "logical_device":
                            if line.lower().count("logical device number") or line.lower().count("logical drive number"):
                                act_log_drv_num = int(line.split()[-1])
                                ctrl_config["logical"][act_log_drv_num] = {}
                            elif line.lower().strip().startswith("logical device name"):
                                array_name = ls.split()[1]
                                ctrl_config["array"][array_name] = " ".join(line.lower().strip().split()[2:])
                            elif line.count(":"):
                                key, val = self._split_config_line(line)
                                ctrl_config["logical"][act_log_drv_num][key] = val
                        elif act_part == "physical_device":
                            if lsl.startswith("channel #"):
                                act_channel_num = int(lsl[-2])
                                ctrl_config["channel"][act_channel_num] = {}
                                act_scsi_stuff = None
                            elif lsl.startswith("device #"):
                                act_scsi_id = int(lsl[-1])
                                act_channel_num = -1
                                act_scsi_stuff = {}
                            elif lsl.startswith("reported channel,device"):
                                act_scsi_id = int(lsl.split(",")[-1])
                                if act_channel_num == -1:
                                    act_channel_num = int(lsl.split(",")[-2].split()[-1])
                                    ctrl_config["channel"][act_channel_num] = {}
                                ctrl_config["channel"][act_channel_num][act_scsi_id] = " ".join(lsl.split()[:-4])
                                act_scsi_stuff["channel"] = act_channel_num
                                act_scsi_stuff["scsi_id"] = act_scsi_id
                                ctrl_config["channel"][act_channel_num][act_scsi_id] = act_scsi_stuff
                                ctrl_config["physical"].append(act_scsi_stuff)
                            elif line.count(":"):
                                if act_scsi_stuff is not None:
                                    key, val = self._split_config_line(line)
                                    act_scsi_stuff[key] = val
                        elif act_part == "controller_information":
                            if lsl.count(":"):
                                key, value = [entry.strip() for entry in lsl.split(":", 1)]
                                ctrl_config["controller"][key] = value
                        #print act_part, linea
                    prev_line = line
                ctrl_stuff["config"] = ctrl_config
            gs_result = self._exec_command("%s getstatus %d" % (ARCCONF_BIN, ctrl_num), logger)
            task_list = []
            act_task = None
            for line in gs_result:
                lline = line.lower()
                if lline.startswith("logical device task"):
                    act_task = {"header" : lline}
                elif act_task:
                    if lline.count(":"):
                        key, value = [part.strip().lower() for part in lline.split(":", 1)]
                        act_task[key] = value
                if not lline.strip():
                    if act_task:
                        task_list.append(act_task)
                        act_task = None
            ctrl_stuff["config"]["task_list"] = task_list
    def get_ctrl_config(self, c_num = None):
        if c_num is None:
            return dict([(num, self.get_ctrl_config(num)) for num in self.__ctrl_dict.keys()])
        else:
            return self.__ctrl_dict[c_num]["config"]
                    
def get_short_state(in_state):
    return in_state.lower()

class aacold_status_command(hm_classes.hm_command):
    def __init__(self, name):
        hm_classes.hm_command.__init__(self, name, positional_arguments=False)
    def server_call(self, cm):
        if not os.path.isfile(ARCCONF_BIN):
            return "error no arcconf-binary found in %s" % (os.path.dirname(ARCCONF_BIN))
        self.module_info.init_ctrl_dict(self.logger)
        self.module_info.update_ctrl_dict(self.logger)
        return "ok %s" % (hm_classes.sys_to_net(self.module_info.get_ctrl_config()))
    def client_call(self, result, parsed_coms):
        if result.startswith("ok "):
            ret_dict = hm_classes.net_to_sys(result[3:])

if __name__ == "__main__":
    print "This is a loadable module."
    sys.exit(0)

