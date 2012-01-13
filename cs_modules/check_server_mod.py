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
import server_command
import check_scripts
import uuid_tools

class check_server(cs_base_class.server_com):
    def __init__(self):
        cs_base_class.server_com.__init__(self)
    def call_it(self, opt_dict, call_params):
        res_struct = server_command.server_reply()
        res_struct.set_state_and_result(0, "ok")
        opt_dict = check_scripts.get_default_opt_dict()
        opt_dict["full_status"] = 1
        opt_dict["mem_info"] = 1
        ret_dict = check_scripts.check_system(opt_dict, {}, call_params.dc)
        pub_coms  = sorted([com_name for com_name, com_struct in [(com_name, call_params.get_l_config()["COM_DICT"][com_name]) for com_name in call_params.get_l_config()["COM_LIST"]] if     com_struct.get_public_via_net()])
        priv_coms = sorted([com_name for com_name, com_struct in [(com_name, call_params.get_l_config()["COM_DICT"][com_name]) for com_name in call_params.get_l_config()["COM_LIST"]] if not com_struct.get_public_via_net()])
        res_struct.set_option_dict({"version"          : call_params.get_l_config()["VERSION_STRING"],
                                    "uuid"             : uuid_tools.get_uuid().get_urn(),
                                    "server_status"    : ret_dict,
                                    "public_commands"  : pub_coms,
                                    "private_commands" : priv_coms})
        return res_struct
    
if __name__ == "__main__":
    print "Loadable module, exiting ..."
    sys.exit(0)
    
