#!/usr/bin/python-init -Ot
#
# Copyright (C) 2006,2007,2008 Andreas Lang-Nevyjel, init.at
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
import process_tools

class my_modclass(hm_classes.hm_fileinfo):
    def __init__(self, **args):
        hm_classes.hm_fileinfo.__init__(self,
                                        "autofs",
                                        "provides a interface to check the status of the automounter daemon",
                                        **args)
    def init(self, mode, logger, basedir_name, **args):
        if mode == "i":
            self.am_checker = process_tools.automount_checker()

class autofs_status_command(hm_classes.hmb_command):
    def __init__(self, **args):
        hm_classes.hmb_command.__init__(self, "autofs_status", **args)
        self.help_str = "returns the status of the automounter"
    def server_call(self, cm):
        if self.module_info.am_checker.valid():
            a_dicts = self.module_info.am_checker.check()
            return "ok %s" % (hm_classes.sys_to_net(a_dicts))
        else:
            return "warning automount_checker is not valid"
    def client_call(self, result, parsed_coms):
        if result.startswith("ok "):
            my_am = process_tools.automount_checker(check_paths=False)
            my_am.set_dict(hm_classes.net_to_sys(result[3:]))
            if my_am.dict_is_valid():
                conf_str    = my_am.get_config_string()
                running_str = my_am.get_running_string()
                if running_str == conf_str:
                    return limits.nag_STATE_OK, "OK: %s" % (running_str)
                else:
                    return limits.nag_STATE_CRITICAL, "ERROR: conf != run: %s != %s" % (conf_str, running_str)
            else:
                return limits.nag_STATE_CRITICAL, "ERROR: wrong dictionaries returned"
        elif result.startswith("warning"):
            return limits.nag_STATE_WARNING, result
        else:
            return limits.nag_STATE_CRITICAL, "ERROR: %s" % (result)

if __name__ == "__main__":
    print "This is a loadable module."
    sys.exit(0)

