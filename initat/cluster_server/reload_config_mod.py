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
import configfile
import server_command
from initat.cluster_server.config import global_config

class reload_config(cs_base_class.server_com):
    def _call(self, cur_inst):
        configfile.read_config_from_db(global_config, self.dc, "server")
        # log config
        for conf_line in global_config.get_config_info():
            self.log("Config : %s" % (conf_line))
        cur_inst.srv_com["result"].attrib.update({
            "reply" : "ok reloaded config",
            "state" : "%d" % (server_command.SRV_REPLY_STATE_OK)})

if __name__ == "__main__":
    print "Loadable module, exiting ..."
    sys.exit(0)
