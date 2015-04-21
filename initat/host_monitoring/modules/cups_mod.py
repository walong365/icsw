#!/usr/bin/python-init -Ot
#
# Copyright (C) 2007,2012 Andreas Lang-Nevyjel, init.at
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
from initat.tools import server_command

class _general(hm_classes.hm_module):
    pass

class cups_status_command(hm_classes.hm_command):
    def __call__(self, srv_com, cur_ns):
        lp_stat, lp_out = commands.getstatusoutput("lpstat -p")
        if lp_stat:
            srv_com["result"].attrib.update({"reply" : "error getting lpstat info (%d): %s" % (lp_stat, lp_out),
                                              "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR)})
        else:
            printer_dict = dict([(line_p[1], line_p[2]) for line_p in [line.strip().split(None, 2) for line in lp_out.split("\n") if line.startswith("printer")]])
            srv_com["printers"] = printer_dict
##            if "arguments:arg0" in srv_com:
##                printer = srv_com["arguments:arg0"].text.strip()
##                if printer in printer_dict:
##                    srv_com["result"].attrib.update({"reply"  : "error getting lpstat info (%d): %s" % (lp_stat, lp_out),
##                                                      "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR)})
##                    return "ok %s" % (hm_classes.sys_to_net((cm[0], printer_dict[cm[0]])))
##                else:
##                    return "error printer %s not known to cups" % (cm[0])
##            else:
##                return "ok %s" % (hm_classes.sys_to_net(printer_dict))
    def interpret(self, srv_com, cur_ns): 
        return self._interpret(srv_com["printers"], cur_ns)
    def interpret_old(self, result, parsed_coms):
        return self._interpret(hm_classes.net_to_sys(result[3:]), parsed_coms)
    def _interpret(self, print_dict, parsed_coms):
        if type(print_dict) == type({}):
            multi_printer = True
        else:
            multi_printer = False
            print_dict = {print_dict[0] : print_dict[1]}
        print_res_dict = {}
        ret_state = limits.nag_STATE_OK
        for p_name, p_stuff in print_dict.iteritems():
            since_idx = p_stuff.index("since")
            pre_time, post_time = (p_stuff[0 : since_idx], p_stuff[since_idx + 6:])
            if pre_time.startswith("is "):
                pre_time = pre_time[3:]
            pre_time  = pre_time.strip().replace("  ", " ").replace("  ", " ").replace(".", ",")
            post_time = post_time.strip().replace("  ", " ").replace("  ", " ")
            if not [True for pf in ["idle, enabled", "now printing"] if pre_time.lower().startswith(pf)]:
                ret_state = max(ret_state, limits.nag_STATE_CRITICAL)
            print_res_dict[p_name] = "%s (since %s)" % (pre_time, post_time)
        return ret_state, ", ".join(["%s%s" % (multi_printer and "%s: " % (p_name) or "", print_res_dict[p_name]) for p_name in sorted(print_res_dict.keys())])

if __name__ == "__main__":
    print "This is a loadable module."
    sys.exit(0)

