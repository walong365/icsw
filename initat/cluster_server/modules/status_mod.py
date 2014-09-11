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
import initat.cluster_server
import logging_tools
import os
import process_tools
import server_command
import uuid_tools


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
                "{} stopped, ".format(logging_tools.get_plural("process", num_stopped)) if num_stopped else "",
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
                cur_com = "/etc/init.d/{} {}".format(inst_xml.get("init_script_name"), cmd)
                ret_stat, _stdout, _stderr = process_tools.call_command(cur_com, cur_inst.log)
                if ret_stat:
                    cur_inst.srv_com.set_result(
                        "error calling '{}': {}".format(cur_com, "{} {}".format(_stdout, _stderr)),
                        server_command.SRV_REPLY_STATE_ERROR,
                    )
                else:
                    cur_inst.srv_com.set_result(
                        "ok called '{}': {}".format(cur_com, "{} {}".format(_stdout, _stderr).strip()),
                    )
            else:
                cur_inst.srv_com.set_result(
                    "instance {} has not init script".format(instance),
                    server_command.SRV_REPLY_STATE_ERROR,
                )


# merged from modify_service_mod
class modify_service(cs_base_class.server_com):
    class Meta:
        needed_option_keys = ["service", "mode"]

    def _call(self, cur_inst):
        full_service_name = "/etc/init.d/{}".format(self.option_dict["service"])
        if self.option_dict["mode"] in ["start", "stop", "restart"]:
            if os.path.isfile(full_service_name):
                cur_com = "{} {}".format(full_service_name, self.option_dict["mode"])
                ret_stat, _stdout, _stderr = process_tools.call_command(cur_com, cur_inst.log)
                # cstat, _c_logs = process_tools.submit_at_command(at_com, self.option_dict.get("timediff", 0))
                if ret_stat:
                    cur_inst.srv_com.set_result(
                        "error calling '{}': {}".format(cur_com, "{} {}".format(_stdout, _stderr).strip()),
                        server_command.SRV_REPLY_STATE_ERROR
                    )
                else:
                    cur_inst.srv_com.set_result(
                        "ok called '{}': {}".format(cur_com, "{} {}".format(_stdout, _stderr).strip()),
                    )
            else:
                cur_inst.srv_com.set_result(
                    "error unknown service '{}'".format(full_service_name),
                    server_command.SRV_REPLY_STATE_ERROR
                )
        else:
            cur_inst.srv_com.set_result(
                "error unknown mode '{}'".format(self.option_dict["mode"]),
                server_command.SRV_REPLY_STATE_ERROR
            )


# merged from check_server_mod, still needed ?
class check_server(cs_base_class.server_com):
    def _call(self, cur_inst):
        def_ns = check_scripts.get_default_ns()
        # def_ns["full_status"] = True
        # def_ns["mem_info"] = True
        ret_dict = check_scripts.check_system(def_ns)
        pub_coms = sorted(
            [
                com_name for com_name, com_struct in initat.cluster_server.modules.command_dict.iteritems() if com_struct.Meta.public_via_net
            ]
        )
        priv_coms = sorted(
            [
                com_name for com_name, com_struct in initat.cluster_server.modules.command_dict.iteritems() if not com_struct.Meta.public_via_net
            ]
        )
        # FIXME, sql info not transfered
        for _key, value in ret_dict.iteritems():
            if type(value) == dict and "sql" in value:
                value["sql"] = str(value["sql"])
        cur_inst.srv_com.set_result(
            "returned server info",
        )
        cur_inst.srv_com["result:server_info"] = {
            "version": global_config["VERSION"],
            "uuid": uuid_tools.get_uuid().get_urn(),
            "server_status": ret_dict,
            "public_commands": pub_coms,
            "private_commands": priv_coms
        }


# merged from version_mod
class version(cs_base_class.server_com):
    class Meta:
        show_execution_time = False

    def _call(self, cur_inst):
        cur_inst.srv_com["version"] = global_config["VERSION"]
        cur_inst.srv_com.set_result(
            "version is {}".format(global_config["VERSION"])
        )


# merged from get_uuid_mod
class get_uuid(cs_base_class.server_com):
    class Meta:
        show_execution_time = False

    def _call(self, cur_inst):
        cur_inst.srv_com["uuid"] = uuid_tools.get_uuid().get_urn()
        cur_inst.srv_com.set_result(
            "uuid is {}".format(uuid_tools.get_uuid().get_urn()),
        )


class get_0mq_id(cs_base_class.server_com):
    class Meta:
        show_execution_time = False

    def _call(self, cur_inst):
        zmq_id = "{}:clusterserver:".format(uuid_tools.get_uuid().get_urn())
        cur_inst.srv_com["zmq_id"] = zmq_id
        cur_inst.srv_com.set_result(
            "0MQ_ID is {}".format(zmq_id),
        )
