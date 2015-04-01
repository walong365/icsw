#!/usr/bin/python -Ot
#
# Copyright (C) 2007,2012,2013 Andreas Lang-Nevyjel
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
    class Meta:
        needed_option_keys = ["service", "mode"]
    def _call(self, cur_inst):
        full_service_name = "/etc/init.d/%s" % (self.option_dict["service"])
        if self.option_dict["mode"] in ["start", "stop", "restart"]:
            if os.path.isfile(full_service_name):
                at_com = "%s %s" % (full_service_name, self.option_dict["mode"])
                cstat, c_logs = process_tools.submit_at_command(at_com, self.option_dict.get("timediff", 0))
                if cstat:
                    cur_inst.srv_com["result"].attrib.update({
                        "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR),
                        "reply" : "error unable to submit '%s' to at-daemon" % (at_com)
                        })
                else:
                    cur_inst.srv_com["result"].attrib.update({
                        "state" : "%d" % (server_command.SRV_REPLY_STATE_OK),
                        "reply" : "ok submitted '%s' to at-daemon" % (at_com)
                        })
            else:
                cur_inst.srv_com["result"].attrib.update({
                    "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR),
                    "reply" : "error unknown service '%s'" % (full_service_name)
                })
        else:
            cur_inst.srv_com["result"].attrib.update({
                "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR),
                "reply" : "error unknown mode '%s'" % (self.option_dict["mode"])
            })

if __name__ == "__main__":
    print "Loadable module, exiting ..."
    sys.exit(0)
    
