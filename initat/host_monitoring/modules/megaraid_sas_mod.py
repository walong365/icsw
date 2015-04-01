#!/usr/bin/python-init -Ot
#
# Copyright (C) 2010 Andreas Lang-Nevyjel, init.at
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
from initat.host_monitoring import limits
from initat.host_monitoring import hm_classes
import logging_tools
import os
import os.path
import commands
import pprint

MEGARC_BIN = "/sbin/megarc"

class my_modclass(hm_classes.hm_fileinfo):
    def __init__(self, **args):
        hm_classes.hm_fileinfo.__init__(self,
                                        "megaraid_sas",
                                        "provides a interface to check the status of LSI SAS MegaRAID RAID-cards",
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
            logger.info("Searching for Megaraid SAS-controllers")
            result = self._exec_command("%s -AdpAllInfo -aAll" % (MEGARC_BIN), logger)
            adp_check = False
            for line in [line.strip() for line in result if line.strip()]:
                if line.lower().startswith("adapter #"):
                    line_p = line.split()
                    ctrl_num = int(line_p[-1][1:])
                    self.__ctrl_dict[ctrl_num] = {"info"          : " ".join(line_p),
                                                  "logical_lines" : {}}
                    logger.info("Found Controller '%s' with ID %d" % (self.__ctrl_dict[ctrl_num]["info"],
                                                                      ctrl_num))
    def update_ctrl_dict(self, logger):
        for ctrl_num, ctrl_stuff in self.__ctrl_dict.iteritems():
            al_result = self._exec_command("%s -ldInfo -Lall -a%d" % (MEGARC_BIN, ctrl_num), logger)
            log_drive_num = None
            for line in [line.strip() for line in al_result if line.strip()]:
                if line.lower().count("virtual disk:"):
                    log_drive_num = int(line.strip().split()[2])
                    ctrl_stuff["logical_lines"][log_drive_num] = []
                if log_drive_num is not None:
                    if line.count(":"):
                        ctrl_stuff["logical_lines"][log_drive_num].append([part.strip() for part in line.split(":", 1)])
            al_result = self._exec_command("%s -AdpBbuCmd -GetBbuStatus -a%d" % (MEGARC_BIN, ctrl_num), logger)
            ctrl_stuff["bbu_keys"] = {}
            main_key = "main"
            for line in [line.rstrip() for line in al_result if line.strip()]:
                if not line.startswith(" "):
                    main_key = "main"
                if line.count(":"):
                    if line.endswith(":"):
                        main_key = line.strip()[:-1].lower()
                    else:
                        if main_key in ["bbu firmware status"]:
                            pass
                        else:
                            key, value = line.split(":", 1)
                            act_key = key.strip().lower()
                            value = value.strip()
                            value = {"no" : False,
                                     "yes" : True}.get(value.lower(), value)
                            ctrl_stuff["bbu_keys"].setdefault(main_key, {})[act_key] = value
    def get_ctrl_config(self, c_num = None):
        if c_num is None:
            return dict([(num, self.get_ctrl_config(num)) for num in self.__ctrl_dict.keys()])
        else:
            return self.__ctrl_dict[c_num]

class megaraid_sas_status_OLD_command(hm_classes.hmb_command):
    def __init__(self, **args):
        hm_classes.hmb_command.__init__(self, "megaraid_sas_status", **args)
        self.help_str = "returns the status of the given controller"
        #self.net_only = True
        self.is_immediate = False
        self.cache_timeout = 600
    def server_call(self, cm):
        self.module_info.init_ctrl_dict(self.logger)
        self.module_info.update_ctrl_dict(self.logger)
        return "ok %s" % (hm_classes.sys_to_net(self.module_info.get_ctrl_config()))
    def client_call(self, result, parsed_coms):
        if result.startswith("ok "):
            ret_dict = hm_classes.net_to_sys(result[3:])
            num_c, num_d, num_e = (len(ret_dict.keys()), 0, 0)
            ret_state = limits.nag_STATE_OK
            drive_stats = []
            for ctrl_num, ctrl_stuff in ret_dict.iteritems():
                for log_num, log_stuff in ctrl_stuff.get("logical_lines", {}).iteritems():
                    log_dict = dict([(key.lower(), value) for key, value in log_stuff])
                    num_d += 1
                    if "state" in log_dict:
                        status = log_dict["state"]
                        if status.lower() != "optimal":
                            num_e += 1
                        drive_stats.append("ld %d (ctrl %d, %s): %s" % (log_num,
                                                                        ctrl_num,
                                                                        log_dict.get("size", "???"),
                                                                        status))
            if num_e:
                ret_state = limits.nag_STATE_CRITICAL
            return ret_state, "%s: %s on %s, %s" % (limits.get_state_str(ret_state),
                                                    logging_tools.get_plural("logical drive", num_d),
                                                    logging_tools.get_plural("controller", num_c),
                                                    ", ".join(drive_stats))
        else:
            return limits.nag_STATE_CRITICAL, "error %s" % (result)

class megaraid_sas_bbu_status_command(hm_classes.hmb_command):
    def __init__(self, **args):
        hm_classes.hmb_command.__init__(self, "megaraid_sas_bbu_status", **args)
        self.help_str = "returns the BBU status of the given controller"
        #self.net_only = True
        self.is_immediate = False
        self.cache_timeout = 600
    def server_call(self, cm):
        self.module_info.init_ctrl_dict(self.logger)
        self.module_info.update_ctrl_dict(self.logger)
        return "ok %s" % (hm_classes.sys_to_net(self.module_info.get_ctrl_config()))
    def client_call(self, result, parsed_coms):
        if result.startswith("ok "):
            ret_dict = hm_classes.net_to_sys(result[3:])
            num_c, num_d, num_e = (len(ret_dict.keys()), 0, 0)
            ret_state = limits.nag_STATE_OK
            drive_stats = []
            for ctrl_num, ctrl_stuff in ret_dict.iteritems():
                ret_fields = []
                if "bbu_keys" in ctrl_stuff:
                    bbu_dict = ctrl_stuff["bbu_keys"]
                    ret_fields.append("temperature %s" % (bbu_dict["main"].get("temperature", "???")))
                    #pprint.pprint(bbu_dict)
                    charge_fields = ["%s charge: %s" % (key.split()[0], bbu_dict["main"][key]) for key in bbu_dict["main"] if key.count("state of charge")]
                    ret_fields.extend(charge_fields)
                    alarm_keys = [key for key in bbu_dict["gasguagestatus"] if key.count("alarm") or key.count("over")]
                    alarm_fields = [key for key in alarm_keys if bbu_dict["gasguagestatus"][key]]
                    if alarm_fields:
                        ret_fields.append("alarms: %s" % ("-".join(alarm_fields)))
                        ret_state = max(ret_state, limits.nag_STATE_CRITICAL)
                else:
                    ret_fields.append("no bbu-related information found")
                    ret_state = max(ret_state, limits.nag_STATE_CRITICAL)
            if num_e:
                ret_state = limits.nag_STATE_CRITICAL
            return ret_state, "%s: %s, %s" % (limits.get_state_str(ret_state),
                                              logging_tools.get_plural("controller", num_c),
                                              ", ".join(ret_fields))
        else:
            return limits.nag_STATE_CRITICAL, "error %s" % (result)

if __name__ == "__main__":
    print "This is a loadable module."
    sys.exit(0)

