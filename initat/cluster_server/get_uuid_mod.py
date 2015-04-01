#!/usr/bin/python -Ot
#
# Copyright (C) 2007,2012 Andreas Lang-Nevyjel
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
import uuid_tools
import server_command

class get_uuid(cs_base_class.server_com):
    class Meta:
        show_execution_time = False
    def _call(self, cur_inst):
        cur_inst.srv_com["uuid"] = uuid_tools.get_uuid().get_urn()
        cur_inst.srv_com["result"].attrib.update({
            "reply" : "uuid is %s" % (uuid_tools.get_uuid().get_urn()),
            "state" : "%d" % (server_command.SRV_REPLY_STATE_OK)})
    
class get_0mq_id(cs_base_class.server_com):
    class Meta:
        show_execution_time = False
    def _call(self, cur_inst):
        cur_inst.srv_com["zmq_id"] = uuid_tools.get_uuid().get_urn()
        cur_inst.srv_com["result"].attrib.update({
            "reply" : "0MQ_ID is %s" % (uuid_tools.get_uuid().get_urn()),
            "state" : "%d" % (server_command.SRV_REPLY_STATE_OK)})
        
if __name__ == "__main__":
    print "Loadable module, exiting ..."
    sys.exit(0)
    