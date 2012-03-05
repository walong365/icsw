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
from host_monitoring import limits
from host_monitoring import hm_classes
import os
import os.path
import logging_tools
import pprint

ARCCONF_BIN = "/usr/sbin/arcconf"

class my_modclass(hm_classes.hm_fileinfo):
    def __init__(self, **args):
        hm_classes.hm_fileinfo.__init__(self,
                                        "aac_status",
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

class aac_status_command(hm_classes.hmb_command):
    def __init__(self, **args):
        hm_classes.hmb_command.__init__(self, "aac_status", **args)
        self.help_str = "returns the status of the connected IPS-devices"
        self.cache_timeout = 600
        self.is_immediate = False
    def server_call(self, cm):
        if not os.path.isfile(ARCCONF_BIN):
            return "error no arcconf-binary found in %s" % (os.path.dirname(ARCCONF_BIN))
        self.module_info.init_ctrl_dict(self.logger)
        self.module_info.update_ctrl_dict(self.logger)
        return "ok %s" % (hm_classes.sys_to_net(self.module_info.get_ctrl_config()))
    def client_call(self, result, parsed_coms):
        if result.startswith("ok "):
            ret_dict = hm_classes.net_to_sys(result[3:])
            num_warn, num_error = (0, 0)
            ret_f = []
            for c_num, c_stuff in ret_dict.iteritems():
                #pprint.pprint(c_stuff)
                act_field = []
                if c_stuff["logical"]:
                    log_field = []
                    for l_num, l_stuff in c_stuff["logical"].iteritems():
                        sold_name = "status_of_logical_device" if l_stuff.has_key("status_of_logical_device") else "status_of_logical_drive"
                        log_field.append("ld%d: %s (%s, %s)" % (l_num,
                                                                logging_tools.get_size_str(int(l_stuff["size"].split()[0]) * 1000000, divider=1000).strip(),
                                                                "RAID%s" % (l_stuff["raid_level"]) if l_stuff.has_key("raid_level") else "RAID?",
                                                                get_short_state(l_stuff[sold_name])))
                        if l_stuff[sold_name].lower() in ["degraded"]:
                            num_error += 1
                        elif l_stuff[sold_name].lower() not in ["optimal", "okay"]:
                            num_warn += 1
                    act_field.extend(log_field)
                if c_stuff["physical"]:
                    phys_dict = {}
                    for phys in c_stuff["physical"]:
                        if phys.has_key("size"):
                            s_state = get_short_state(phys["state"])
                            if s_state == "sby":
                                # ignore empty standby bays
                                pass
                            else:
                                if s_state not in ["onl", "hsp", "optimal", "online"]:
                                    num_error += 1
                                con_info = ""
                                if phys.has_key("reported_location"):
                                    cd_info = phys["reported_location"].split(",")
                                    if len(cd_info) == 2:
                                        try:
                                            con_info = "c%d.%d" % (int(cd_info[0].split()[-1]),
                                                                   int(cd_info[1].split()[-1]))
                                        except:
                                            con_info = "error parsing con_info %s" % (phys["reported_location"])
                                phys_dict.setdefault(s_state, []).append("c%d/id%d%s" % (phys["channel"],
                                                                                         phys["scsi_id"],
                                                                                         " (%s)" % (con_info) if con_info else ""))
                    act_field.extend(["%s: %s" % (key, ",".join(phys_dict[key])) for key in sorted(phys_dict.keys())])
                if "task_list" in c_stuff:
                    for act_task in c_stuff["task_list"]:
                        act_field.append("%s on logical device %s: %s, %d %%" % (act_task.get("header", "unknown task"),
                                                                                 act_task.get("logical device", "?"),
                                                                                 act_task.get("current operation", "unknown op"),
                                                                                 int(act_task.get("percentage complete", "0"))))
                # check controller warnings
                ctrl_field = []
                if c_stuff["controller"]:
                    ctrl_dict = c_stuff["controller"]
                    c_stat = ctrl_dict.get("controller status", "")
                    if c_stat:
                        ctrl_field.append("status %s" % (c_stat))
                        if c_stat.lower() not in ["optimal", "okay"]:
                            num_error += 1
                    ov_temp = ctrl_dict.get("over temperature", "")
                    if ov_temp:
                        if ov_temp == "yes":
                            num_error += 1
                            ctrl_field.append("over temperature")
                ret_f.append("c%d (%s): %s" % (c_num,
                                               ", ".join(ctrl_field) or "---",
                                               ", ".join(act_field)))
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

