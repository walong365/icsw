#!/usr/bin/python -Ot
#
# Copyright (C) 2007,2012-2014 Andreas Lang-Nevyjel
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

from django.db.models import Q
from initat.cluster.backbone.models import device
from initat.cluster_server.config import global_config
import check_scripts
import cluster_location
import cs_base_class
import logging_tools
import server_command
import process_tools

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
        cur_inst.srv_com.set_result(
            "%s running,%s clustername is %s, version is %s" % (
                logging_tools.get_plural("process", num_running),
                "%s stopped, " % (logging_tools.get_plural("process", num_stopped)) if num_stopped else "",
                cluster_name,
                global_config["VERSION"]),
            server_command.SRV_REPLY_STATE_OK if all_running else server_command.SRV_REPLY_STATE_ERROR,
        )

class server_status(cs_base_class.server_com):
    def _call(self, cur_inst):
        default_ns = check_scripts.get_default_ns()
        default_ns.instance = ["ALL"]
        stat_xml = check_scripts.check_system(default_ns)
        cur_inst.srv_com["status"] = stat_xml
        cur_inst.srv_com.set_result(
            "checked system",
            )

class server_control(cs_base_class.server_com):
    def _call(self, cur_inst):
        cmd = cur_inst.srv_com["*control"]
        instance = cur_inst.srv_com["*instance"]
        cur_inst.log("command {} for instance {}".format(cmd, instance))
        inst_xml = check_scripts.get_instance_xml().find("instance[@name='{}']".format(instance))
        if inst_xml is None:
            cur_inst.srv_com.set_result(
                "instance {} not found".format(instance),
                server_command.SRV_REPLY_STATE_ERROR,
                )
        else:
            if "init_script_name" in inst_xml.attrib:
                _at_cmd = "/etc/init.d/{} {}".format(inst_xml.get("init_script_name"), cmd)
                cur_inst.log("at command is '{}'".format(_at_cmd))
                process_tools.submit_at_command(_at_cmd)
                cur_inst.srv_com.set_result(
                    "sent {} to instance {}".format(cmd, instance)
                )
            else:
                cur_inst.srv_com.set_result(
                    "instance {} has not init script".format(instance),
                    server_command.SRV_REPLY_STATE_ERROR,
                )
