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
import marshal

class my_modclass(hm_classes.hm_fileinfo):
    def __init__(self, **args):
        hm_classes.hm_fileinfo.__init__(self,
                                        "ibmraid_status",
                                        "provides a interface to check the status of IBM BC-S SAS Raid controller",
                                        **args)
class ibmraid_status_OLD_command(hm_classes.hmb_command):
    def __init__(self, **args):
        hm_classes.hmb_command.__init__(self, "ibmraid_status", **args)
        self.help_str = "returns the status of the given IBM SAS RAID controller"
    def server_call(self, cm):
        return "ok %s" % (file("/tmp/.ctrl_%s" % (cm[0]), "r").read())
    def client_call(self, result, parsed_coms):
        if result.startswith("ok "):
            ret_dict = marshal.loads(result[3:])
            ret_state = limits.nag_STATE_OK
            ret_f = []
            for ctrl_info in ret_dict["ctrl_list"]:
                ret_f.append("%s (%s)" % (ctrl_info["name"],
                                          ctrl_info["status"]))
                if ctrl_info["status"].lower() not in ["primary", "secondary"]:
                    ret_state = max(ret_state, limits.nag_STATE_CRITICAL)
            for ctrl_key in [key for key in ret_dict.keys() if key.split("_")[1].isdigit()]:
                cur_dict = ret_dict[ctrl_key]
                pprint.pprint(cur_dict)
                ctrl_f = []
                ctrl_f.append("C%d: %s" % (int(ctrl_key.split("_")[1]),
                                           cur_dict["Current Status"]))
                if cur_dict["BBU Charging"]:
                    ctrl_f.append("BBU Charging")
                    ret_state = max(ret_state, limits.nag_STATE_WARNING)
                if cur_dict["BBU State"].split()[0] != "1" or cur_dict["BBU Fault Code"].split()[0] != "0":
                    ctrl_f.append("BBU State/Fault Code: '%s/%s'" % (cur_dict["BBU State"],
                                                                     cur_dict["BBU Fault Code"]))
                    ret_state = max(ret_state, limits.nag_STATE_CRITICAL)
                if cur_dict["Current Status"].lower() not in ["primary", "secondary"]:
                    ret_state = max(ret_state, limits.nag_STATE_CRITICAL)
                vol_info = [logging_tools.get_plural("volume", len(cur_dict["volumes"]))]
                for cur_vol in cur_dict["volumes"]:
                    if cur_vol["status"] != "VBL INI":
                        vol_info.append("%s (%d, %s): %s" % (cur_vol["name"],
                                                             cur_vol["raidlevel"],
                                                             cur_vol["capacity"],
                                                             cur_vol["status"]))
                    pass
                ctrl_f.append(",".join(vol_info))
                ret_f.append(", ".join(ctrl_f))
            return ret_state, "; ".join(ret_f)

if __name__ == "__main__":
    print "This is a loadable module."
    sys.exit(0)

