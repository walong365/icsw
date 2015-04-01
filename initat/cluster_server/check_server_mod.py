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
import server_command
import check_scripts
import uuid_tools
import pprint
import initat.cluster_server
from initat.cluster_server.config import global_config

class check_server(cs_base_class.server_com):
    def _call(self, cur_inst):
        def_ns = check_scripts.get_default_ns()
        #def_ns["full_status"] = True
        #def_ns["mem_info"] = True
        ret_dict = check_scripts.check_system(def_ns)
        pub_coms   = sorted([com_name for com_name, com_struct in initat.cluster_server.command_dict.iteritems() if com_struct.Meta.public_via_net])
        priv_coms  = sorted([com_name for com_name, com_struct in initat.cluster_server.command_dict.iteritems() if not com_struct.Meta.public_via_net])
        # FIXME, sql info not transfered
        for key, value in ret_dict.iteritems():
            if type(value) == dict and "sql" in value:
                value["sql"] = str(value["sql"])
        cur_inst.srv_com["result"].attrib.update({
            "reply" : "returned server info",
            "state" : "%d" % (server_command.SRV_REPLY_STATE_OK)})
        cur_inst.srv_com["result:server_info"] = {
            "version"          : global_config["VERSION"],
            "uuid"             : uuid_tools.get_uuid().get_urn(),
            "server_status"    : ret_dict,
            "public_commands"  : pub_coms,
            "private_commands" : priv_coms}
    
if __name__ == "__main__":
    print "Loadable module, exiting ..."
    sys.exit(0)

