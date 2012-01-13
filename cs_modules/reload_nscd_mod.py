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
import process_tools

class reload_nscd(cs_base_class.server_com):
    def __init__(self):
        cs_base_class.server_com.__init__(self)
    def call_it(self, opt_dict, call_params):
        cstat, log_f = process_tools.submit_at_command("/etc/init.d/nscd restart", 1)
        for log_line in log_f:
            call_params.log(log_f)
        if cstat:
            return "error unable to submit at-command (%d, please check logs) to restart nscd" % (cstat)
        else:
            return "ok successfully restarted nscd"
    
if __name__ == "__main__":
    print "Loadable module, exiting ..."
    sys.exit(0)
    
