#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007 lang-nevyjel@init.at
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

SCCLI_BIN = "/sbin/sccli"
CHECK_COMMAND_FILE = "/tmp/.sfxbox_commands"

class my_modclass(hm_classes.hm_fileinfo):
    def __init__(self, **args):
        hm_classes.hm_fileinfo.__init__(self,
                                        "sun fc",
                                        "provides a interface to check the status of Sun FibreChannel Boxes",
                                        **args)
    def init(self, mode, logger, basedir_name, **args):
        if mode == "i":
            self.__ctrl_dict = {}
            if not os.path.isfile(CHECK_COMMAND_FILE):
                logger.info("creating file %s" % (CHECK_COMMAND_FILE))
                file(CHECK_COMMAND_FILE, "w").write("\n".join(["show logical-drives",
                                                               "show disks",
                                                               ""]))
    def _exec_command(self, com, logger):
        stat, out = commands.getstatusoutput(com)
        if stat:
            logger.warning("cannot execute %s (%d): %s" % (com, stat, out))
            out = ""
        return out.split("\n")
    def init_ctrl_dict(self, logger):
        if not self.__ctrl_dict:
            logger.info("Searching for FibreChannel-boxes")
            result = self._exec_command("%s -l" % (SCCLI_BIN), logger)
            dev_list = sorted([x.split()[0] for x in result])
            num_devs = len(dev_list)
            if num_devs:
                logger.info("found %s: %s" % (logging_tools.get_plural("device", len(dev_list)),
                                              ", ".join(dev_list)))
                for dev_device in dev_list:
                    ctrl_stuff = {}
                    # get config for every controller
                    c_result = self._exec_command("cat %s | %s %s" % (CHECK_COMMAND_FILE,
                                                                      SCCLI_BIN,
                                                                      dev_device),
                                                  logger)
                    ctrl_stuff["output"] = c_result
                    self.__ctrl_dict[dev_device] = ctrl_stuff
    def update_ctrl_dict(self, logger):
        for dev_device, ctrl_stuff in self.__ctrl_dict.iteritems():
            al_result = self._exec_command("cat %s | %s %s" % (CHECK_COMMAND_FILE,
                                                               SCCLI_BIN,
                                                               dev_device),
                                           logger)
            ctrl_stuff["output"] = al_result
    def get_ctrl_config(self):
        return self.__ctrl_dict
                    
class sfcbox_status_command(hm_classes.hmb_command):
    def __init__(self, **args):
        hm_classes.hmb_command.__init__(self, "sfcbox_status", **args)
        self.is_immediate = False
        self.cache_timeout = 600
        self.help_str = "returns the status of the FibreChannel Box"
    def server_call(self, cm):
        if not os.path.isfile(SCCLI_BIN):
            return "error no sccli-binary found in %s" % (os.path.dirname(SCCLI_BIN))
        self.module_info.init_ctrl_dict(self.logger)
        self.module_info.update_ctrl_dict(self.logger)
        return "ok %s" % (hm_classes.sys_to_net(self.module_info.get_ctrl_config()))
    def client_call(self, result, parsed_coms):
        if result.startswith("ok "):
            ret_dict = hm_classes.net_to_sys(result[3:])
            num_warn, num_error = (0, 0)
            ret_f = []
            for dev_name, dev_stuff in ret_dict.iteritems():
                out_lines = [x.strip() for x in dev_stuff["output"] if x.strip()]
                head_line = out_lines.pop(0)
                real_dev_name = (head_line[head_line.index(dev_name) + 1 + len(dev_name):]).strip()
                dev_struct = {"real_name" : real_dev_name,
                              "lds"       : {}}
                act_mode = "-"
                for line in out_lines:
                    if line.startswith("--" * 10):
                        act_mode = {"-" : "l",
                                    "l" : "p"}[act_mode]
                    else:
                        if act_mode == "l" and line.startswith("ld"):
                            dev_struct["lds"][line.split()[0]] = logical_drive(real_dev_name, line)
                        elif act_mode == "p":
                            try:
                                new_pd = physical_drive(line)
                            except ValueError:
                                pass
                            else:
                                if dev_struct["lds"].has_key(new_pd.ld):
                                    dev_struct["lds"][new_pd.ld].add_physical_drive(new_pd)
                ret_f.extend([act_ld.get_info_str() for act_ld in dev_struct["lds"].values()])
                num_error += sum([act_ld.num_failed for act_ld in dev_struct["lds"].values()])
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

def get_short_state(in_state):
    return in_state.split("(")[1].split(")")[0].lower()

def parse_size(s_str):
    mult = {"k" : 1000,
            "m" : 1000 * 1000,
            "g" : 1000 * 1000 * 1000,
            "t" : 1000 * 1000 * 1000 * 1000}[s_str[-2].lower()]
    return float(s_str[:-2]) * mult

def get_size(i_size):
    return logging_tools.get_size_str(i_size, False, 1000)

class logical_drive(object):
    def __init__(self, r_name, line):
        l_parts = line.split()
        self.real_name = r_name
        self.name = l_parts.pop(0)
        self.ld_id = l_parts.pop(0)
        self.size = parse_size(l_parts.pop(0))
        self.assigned = l_parts.pop(0)
        self.raid_type = l_parts.pop(0)
        self.num_disks = int(l_parts.pop(0))
        self.num_spare = int(l_parts.pop(0))
        self.num_failed = int(l_parts.pop(0))
        self.status = l_parts.pop(0).lower()
        self.drives = []
    def add_physical_drive(self, pd):
        self.drives.append(pd)
    def get_info_str(self):
        return "%s on %s: %s with %s %s%s%s" % (self.name,
                                                self.real_name,
                                                logging_tools.get_plural("disk", self.num_disks),
                                                get_size(self.size).strip(),
                                                self.raid_type,
                                                self.num_spare and ", %s" % (logging_tools.get_plural("spare disk", self.num_spare)) or "",
                                                self.num_failed and ", %s" % (logging_tools.get_plural("failed disk", self.num_spare)) or "")
    def __repr__(self):
        return "%s, %s, %s, %s" % (self.name,
                                   self.ld_id,
                                   get_size(self.size),
                                   ", ".join([str(x) for x in self.drives]))

class physical_drive(object):
    def __init__(self, line):
        l_parts = line.split()
        if len(l_parts) < 3:
            raise ValueError, "not enough parts"
        self.channel = int(l_parts.pop(0))
        self.pd_id = int(l_parts.pop(0))
        self.size = parse_size(l_parts.pop(0))
        self.speed = parse_size(l_parts.pop(0))
        self.ld = l_parts.pop(0)
        self.status = l_parts.pop(0)
        self.descr = " ".join(l_parts)
    def __repr__(self):
        return "%d, %d, %s" % (self.channel,
                               self.pd_id,
                               get_size(self.size))

if __name__ == "__main__":
    print "This is a loadable module."
    sys.exit(0)

