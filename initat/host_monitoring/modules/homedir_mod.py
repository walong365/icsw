#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007 Andreas Lang-Nevyjel, init.at
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
import logging_tools

class my_modclass(hm_classes.hm_fileinfo):
    def __init__(self, **args):
        hm_classes.hm_fileinfo.__init__(self,
                                        "homedir",
                                        "checks if the homedirectory of a given user is reachable",
                                        **args)

class homedir_command(hm_classes.hmb_command):
    def __init__(self, **args):
        hm_classes.hmb_command.__init__(self, "homedir", **args)
        self.help_str = "returns the status of a given user-homedir"
        self.short_client_info = "USER_NAME"
        self.long_client_info = "name of the user to check"
    def server_call(self, cm):
        if len(cm) >= 1:
            stat, out = commands.getstatusoutput("ls -1 ~%s" % (cm[0]))
            if stat:
                return "error ls ~%s returned %d: %s" % (cm[0], stat, out)
            else:
                return "ok homedir of user %s is reachable (%s)" % (cm[0],
                                                                    logging_tools.get_plural("entry", len(out.split("\n"))))
        else:
            return "warning no username given"
    def client_call(self, result, parsed_coms):
        if result.startswith("ok "):
            return limits.nag_STATE_OK, result
        else:
            return limits.nag_STATE_CRITICAL, "error %s" % (result)

if __name__ == "__main__":
    print "This is a loadable module."
    sys.exit(0)

