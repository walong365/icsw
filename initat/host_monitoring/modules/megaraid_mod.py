#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008,2009,2010 Andreas Lang-Nevyjel, init.at
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
                                        "megaraid",
                                        "provides a interface to check the status of LSI MegaRAID RAID-cards",
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
            logger.info("Searching for Megaraid-controllers")
            result = self._exec_command("%s -AllAdpInfo" % (MEGARC_BIN), logger)
            adp_check = False
            for line in [line.strip() for line in result if line.strip()]:
                if line.lower().startswith("adapterno"):
                    adp_check = True
                elif adp_check:
                    line_p = line.split()
                    ctrl_num = int(line_p.pop(0))
                    self.__ctrl_dict[ctrl_num] = {"info"          : " ".join(line_p),
                                                  "logical_lines" : {}}
                    logger.info("Found Controller '%s' with ID %d" % (self.__ctrl_dict[ctrl_num]["info"],
                                                                      ctrl_num))
    def update_ctrl_dict(self, logger):
        for ctrl_num, ctrl_stuff in self.__ctrl_dict.iteritems():
            al_result = self._exec_command("%s -ldInfo -Lall -a%d" % (MEGARC_BIN, ctrl_num), logger)
            log_drive_num = None
            for line in [line.strip() for line in al_result if line.strip()]:
                if line.lower().count("information of logical drive"):
                    log_drive_num = int(line.strip("*").split()[4])
                    ctrl_stuff["logical_lines"][log_drive_num] = []
                if log_drive_num is not None:
                    ctrl_stuff["logical_lines"][log_drive_num].append(line)
    def get_ctrl_config(self, c_num = None):
        if c_num is None:
            return dict([(num, self.get_ctrl_config(num)) for num in self.__ctrl_dict.keys()])
        else:
            return self.__ctrl_dict[c_num]

class megaraid_status_OLD_command(hm_classes.hmb_command):
    def __init__(self, **args):
        hm_classes.hmb_command.__init__(self, "megaraid_status", **args)
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
            ret_state, ret_str = (limits.nag_STATE_OK, "OK")
            drive_stats = []
            for ctrl_num, ctrl_stuff in ret_dict.iteritems():
                for log_num, log_stuff in ctrl_stuff.get("logical_lines", {}).iteritems():
                    num_d += 1
                    for line in log_stuff:
                        if line.lower().startswith("logical drive") and line.lower().count("status"):
                            status = line.split()[-1]
                            if status.lower() != "optimal":
                                num_e += 1
                            drive_stats.append("ld %d (ctrl %d): %s" % (log_num,
                                                                        ctrl_num,
                                                                        status))
            if num_e:
                ret_state, ret_str = (limits.nag_STATE_CRITICAL, "Error")
            return ret_state, "%s: %s on %s, %s" % (ret_str,
                                                    logging_tools.get_plural("logical drive", num_d),
                                                    logging_tools.get_plural("controller", num_c),
                                                    ", ".join(drive_stats))
        else:
            return limits.nag_STATE_CRITICAL, "error %s" % (result)

if __name__ == "__main__":
    print "This is a loadable module."
    sys.exit(0)

