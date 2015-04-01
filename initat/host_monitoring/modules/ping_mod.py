#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008 Andreas Lang-Nevyjel, init.at
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

class my_modclass(hm_classes.hm_fileinfo):
    def __init__(self, **args):
        hm_classes.hm_fileinfo.__init__(self,
                                        "ping",
                                        "tools for pinging other machines (local or remote)",
                                        **args)
    def process_client_args(self, opts, hmb):
        ok, why = (1, "")
        my_lim = limits.limits()
        for opt, arg in opts:
            if hmb.name in ["ping_remote", "ping_remote_flood"]:
                pass
        return ok, why, [my_lim]

class ping_remote_command(hm_classes.hmb_command):
    def __init__(self, **args):
        hm_classes.hmb_command.__init__(self, "ping_remote", **args)
        self.help_str = "pings a given ip-address from a remote host"
        self.short_client_info = "OPTIONS addrs num timeout"
        self.long_client_info = "addrs is a comma-separated list of ip addresses to check, OPTIONS has the form key=True/False where key is one of flood_ping, fast_mode; if num and/or timeout is omitted the defaults (3 and 10.0) are used"
    def client_call(self, result, parsed_coms):
        if result == "N":
            return limits.nag_STATE_WARNING, "Not available"
        else:
            if result.startswith("ok "):
                r_dict = hm_classes.net_to_sys(result[3:])
                addrs = sorted(r_dict.keys())
                if addrs:
                    ret_state, ret_str_a = (limits.nag_STATE_OK, [])
                    for addr in addrs:
                        stuff = r_dict[addr]
                        if type(stuff) == type(""):
                            act_state, state = limits.nag_STATE_CRITICAL, stuff
                            ret_str_a.append("%s: %s" % (addr, state))
                        else:
                            if not stuff["received"]:
                                act_state, state = limits.nag_STATE_CRITICAL, "Critical"
                            elif stuff["timeout"]:
                                act_state, state = limits.nag_STATE_WARNING, "Warning"
                            else:
                                act_state, state = limits.nag_STATE_OK, "OK"
                            if act_state == limits.nag_STATE_CRITICAL:
                                act_str = "%s: no reply (%s sent) from %s" % (state,
                                                                              stuff["send"],
                                                                              addr)
                            else:
                                act_str = "%s: %d%% loss of %s, (%s avg) from %s" % (state,
                                                                                     int(100 * stuff["timeout"] / stuff["send"]),
                                                                                     logging_tools.get_plural("packet", stuff["send"]),
                                                                                     logging_tools.get_diff_time_str(stuff["mean_time"]),
                                                                                     addr)
                            ret_str_a.append(act_str)
                        ret_state = max(ret_state, act_state)
                    ret_str = "\n".join(ret_str_a)
                else:
                    ret_state, ret_str = limits.nag_STATE_CRITICAL, "No hosts found"
            else:
                print "error %s" % (result)
            return ret_state, ret_str
        
class ping_command(hm_classes.hmb_command):
    def __init__(self, **args):
        hm_classes.hmb_command.__init__(self, "ping", **args)
        self.help_str = "pings a given ip-address from the local host"
        self.relay_call = True
        self.special_hook = "ping"

if __name__ == "__main__":
    print "This is a loadable module."
    sys.exit(0)
