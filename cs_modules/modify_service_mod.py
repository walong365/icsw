#!/usr/bin/python -Ot
#
# Copyright (C) 2007 Andreas Lang-Nevyjel
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
import cs_base_class
import os
import server_command
import process_tools

class modify_service(cs_base_class.server_com):
    def __init__(self):
        cs_base_class.server_com.__init__(self)
        self.set_needed_option_keys(["service", "mode"])
    def call_it(self, opt_dict, call_params):
        res_struct = server_command.server_reply()
        full_service_name = "/etc/init.d/%s" % (opt_dict["service"])
        if opt_dict["mode"] in ["start", "stop", "restart"]:
            if os.path.isfile(full_service_name):
                at_com = "%s %s" % (full_service_name, opt_dict["mode"])
                cstat, c_logs = process_tools.submit_at_command(at_com, opt_dict.get("timediff", 0))
                if cstat:
                    res_struct.set_state_and_result(0, "error unable to submit '%s' to at-daemon" % (at_com))
                else:
                    res_struct.set_state_and_result(0, "ok submitted at-command '%s'" % (at_com))
            else:
                res_struct.set_state_and_result(0, "error unknown serivce '%s'" % (opt_dict["service"]))
        else:
            res_struct.set_state_and_result(0, "error unknown mode '%s'" % (opt_dict["mode"]))
        return res_struct

if __name__ == "__main__":
    print "Loadable module, exiting ..."
    sys.exit(0)
    
