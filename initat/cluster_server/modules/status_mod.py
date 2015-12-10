# Copyright (C) 2007,2012-2015 Andreas Lang-Nevyjel
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

import os

from django.conf import settings

import cs_base_class
import initat.cluster_server
from initat.cluster.backbone import routing
from initat.cluster_server.config import global_config
from initat.icsw.service import instance, container, service_parser, main
from initat.tools import process_tools, server_command, uuid_tools, net_tools


class status(cs_base_class.server_com):
    class Meta:
        show_execution_time = False

    def _call(self, cur_inst):
        p_dict = self.main_proc.get_info_dict()
        self.main_proc.server_status(cur_inst.srv_com, self.main_proc.msi_block, global_config)


class server_status(cs_base_class.server_com):
    def _call(self, cur_inst):
        inst_xml = instance.InstanceXML(cur_inst.log).tree
        cur_c = container.ServiceContainer(cur_inst.log)
        _def_ns = service_parser.Parser.get_default_ns()
        cur_c.check_system(_def_ns, inst_xml)
        cur_inst.srv_com["status"] = inst_xml
        _local_state = main.query_local_meta_server()
        if _local_state is not None:
            _bldr = cur_inst.srv_com.builder()
            cur_inst.srv_com["metastatus"] = _local_state["overview:instances"]
            cur_inst.srv_com["version_info"] = _bldr(
                "sys",
                **settings.ICSW_VERSION_DICT
            )
            cur_inst.srv_com.set_result(
                "checked system {}".format(global_config["SERVER_FULL_NAME"]),
            )
        else:
            cur_inst.srv_com.set_result(
                "error querying local meta-server (timeout?)",
                server_command.SRV_REPLY_STATE_ERROR,
            )


class server_control(cs_base_class.server_com):
    def _call(self, cur_inst):
        cur_inst.srv_com["command"] = "state{}".format(cur_inst.srv_com["*control"])
        _result = net_tools.zmq_connection(
            "icsw_cssc_{:d}".format(os.getpid())
        ).add_connection(
            "tcp://localhost:8012",
            cur_inst.srv_com,
        )
        cur_inst.srv_com.set_result(*_result.get_log_tuple(map_to_log_level=False))


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
        def_ns = check_scripts.ICSWParser.get_default_ns()
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
        zmq_id = routing.get_server_uuid("server")
        cur_inst.srv_com["zmq_id"] = zmq_id
        cur_inst.srv_com.set_result(
            "0MQ_ID is {}".format(zmq_id),
        )
