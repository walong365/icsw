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
""" returns status of the cluster and updates the cluster_name if necessary """

import sys
import cs_base_class
import configfile
import os
import pprint
import server_command
import logging_tools
from initat.cluster_server.config import global_config
from initat.cluster.backbone.models import device, device_group
from django.db.models import Q
import cluster_location

CLUSTER_NAME_FILE = "/etc/sysconfig/cluster/cluster_name"

class status(cs_base_class.server_com):
    class Meta:
        show_execution_time = False
    def _call(self, cur_inst):
        p_dict = self.process_pool.get_info_dict()
        cur_cdg = device.objects.get(Q(device_group__cluster_device_group=True))
        cluster_name = cluster_location.db_device_variable(cur_cdg, "CLUSTER_NAME").get_value() or "CN_not_set"
        cur_inst.srv_com["clustername"] = cluster_name
        cur_inst.srv_com["version"] = global_config["VERSION"]
        num_running = len([True for value in p_dict.itervalues() if value["alive"]])
        num_stopped = len([True for value in p_dict.itervalues() if not value["alive"]])
        all_running = num_stopped == 0
        cur_inst.srv_com["result"].attrib.update({
            "reply" : "%s running,%s clustername is %s, version is %s" % (
                logging_tools.get_plural("process", num_running),
                "%s stopped, " % (logging_tools.get_plural("process", num_stopped)) if num_stopped else "",
                cluster_name,
                global_config["VERSION"]),
            "state" : "%d" % (server_command.SRV_REPLY_STATE_OK if all_running else server_command.SRV_REPLY_STATE_ERROR)})
    
if __name__ == "__main__":
    print "Loadable module, exiting ..."
    sys.exit(0)
    
