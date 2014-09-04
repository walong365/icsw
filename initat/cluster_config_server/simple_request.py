# Copyright (C) 2001-2008,2012-2014 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# this file is part of cluster-config-server
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
""" cluster-config-server, simple request structure """

from django.db.models import Q
from initat.cluster.backbone.models import config, config_str, device_variable
import config_tools
import logging_tools
import server_command


# copy from md-config-server
class var_cache(dict):
    def __init__(self, cdg):
        super(var_cache, self).__init__(self)
        self.__cdg = cdg

    def get_vars(self, cur_dev):
        global_key, dg_key, dev_key = (
            "GLOBAL",
            "dg__{:d}".format(cur_dev.device_group_id),
            "dev__{:d}".format(cur_dev.pk))
        if global_key not in self:
            def_dict = {
                "SNMP_VERSION": 2,
                "SNMP_READ_COMMUNITY": "public",
                "SNMP_WRITE_COMMUNITY": "private"
            }
            # read global configs
            self[global_key] = dict([(cur_var.name, cur_var.get_value()) for cur_var in device_variable.objects.filter(Q(device=self.__cdg))])
            # update with def_dict
            for key, value in def_dict.iteritems():
                if key not in self[global_key]:
                    self[global_key][key] = value
        if dg_key not in self:
            # read device_group configs
            self[dg_key] = dict([(cur_var.name, cur_var.get_value()) for cur_var in device_variable.objects.filter(Q(device=cur_dev.device_group.device))])
        if dev_key not in self:
            # read device configs
            self[dev_key] = dict([(cur_var.name, cur_var.get_value()) for cur_var in device_variable.objects.filter(Q(device=cur_dev))])
        ret_dict, info_dict = ({}, {})
        # for s_key in ret_dict.iterkeys():
        for key, key_n in [(dev_key, "d"), (dg_key, "g"), (global_key, "c")]:
            info_dict[key_n] = 0
            for s_key, s_value in self.get(key, {}).iteritems():
                if s_key not in ret_dict:
                    ret_dict[s_key] = s_value
                    info_dict[key_n] += 1
        return ret_dict, info_dict


class simple_request(object):
    def __init__(self, cc, zmq_id, node_text):
        self.cc = cc
        self.zmq_id = zmq_id
        if zmq_id.count(":") == 2:
            src_ip = zmq_id.split(":")[-1]
            if not src_ip:
                src_ip = None
        else:
            src_ip = None
        self.src_ip = src_ip
        self.node_text = node_text
        self.command = node_text.strip().split()[0]
        self.data = " ".join(node_text.strip().split()[1:])
        self.server_ip = None

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.cc.log(what, log_level)

    def _find_best_server(self, conf_list):
        dev_sc = config_tools.server_check(
            short_host_name=self.cc.device.name,
            server_type="node",
            fetch_network_info=True)
        bs_list = []
        for cur_conf in conf_list:
            srv_routing = cur_conf.get_route_to_other_device(
                self.cc.router_obj,
                dev_sc,
                filter_ip=self.src_ip,
                allow_route_to_other_networks=False)
            if srv_routing:
                bs_list.append((srv_routing[0][0], cur_conf))
        if bs_list:
            return sorted(bs_list)[0][1]
        else:
            self.log("no result in find_best_server ({})".format(logging_tools.get_plural("entry", len(conf_list))))
            return None

    def _get_config_str_vars(self, cs_name):
        config_pks = config.objects.filter(
            Q(device_config__device=self.cc.device) |
            (Q(device_config__device__device_group=self.cc.device.device_group_id) &
             Q(device_config__device__device_type__identifier="MD"))). \
            order_by("-priority", "name").distinct().values_list("pk", flat=True)
        c_vars = config_str.objects.filter(Q(config__in=config_pks) & Q(name=cs_name))
        ent_list = []
        for c_var in c_vars:
            for act_val in [part.strip() for part in c_var.value.strip().split() if part.strip()]:
                if act_val not in ent_list:
                    ent_list.append(act_val)  #
        return ent_list

    def _get_valid_server_struct(self, s_list):
        # list of boot-related config names
        bsl_servers = set(["kernel_server", "image_server", "mother_server"])
        # list of server_types which has to be mapped to the mother-server
        map_to_mother = set(["kernel_server", "image_server"])
        for type_name in s_list:
            conf_list = config_tools.device_with_config(type_name).get(type_name, [])
            if conf_list:
                if type_name in bsl_servers:
                    # config name (from s_list) is in bsl_servers
                    valid_server_struct = None
                    for srv_found in conf_list:
                        # iterate over servers
                        if srv_found.device and srv_found.device.pk == self.cc.device.bootserver_id:
                            # found bootserver, match
                            valid_server_struct = srv_found
                            break
                else:
                    valid_server_struct = self._find_best_server(conf_list)
            else:
                # no config found
                valid_server_struct = None
            if valid_server_struct:
                # exit if srv_struct found
                break
        if valid_server_struct and type_name in map_to_mother:
            # remap to mother_server
            valid_server_struct = config_tools.server_check(
                server_type="mother_server",
                short_host_name=valid_server_struct.short_host_name,
                fetch_network_info=True)
        if valid_server_struct:
            dev_sc = config_tools.server_check(
                short_host_name=self.cc.device.name,
                server_type="node",
                fetch_network_info=True)
            # check if there is a route between us and server
            srv_routing = valid_server_struct.get_route_to_other_device(
                self.cc.router_obj,
                dev_sc,
                filter_ip=self.src_ip,
                allow_route_to_other_networks=False,
                # prefer production routes
                prefer_production_net=True,
            )
            # srv_routing = valid_server_struct.prefer_production_net(srv_routing)
            if not srv_routing:
                # check for updated network ?
                self.log(
                    "found valid_server_struct {} but no route".format(
                        valid_server_struct.server_info_str
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
                valid_server_struct = None
            else:
                # print "r", srv_routing
                self.server_ip = srv_routing[0][2][1][0]
                self.log("found valid_server_struct {} (device {}) with ip {}".format(
                    valid_server_struct.server_info_str,
                    unicode(valid_server_struct.device),
                    self.server_ip))
        else:
            self.log("no valid server_struct found (search list: {})".format(", ".join(s_list)),
                     logging_tools.LOG_LEVEL_ERROR)
        return valid_server_struct

    def create_config_dir(self):
        # link to build client
        self.cc.complex_config_request(self, "create_config_dir")

    def get_partition(self):
        # link to build client
        self.cc.complex_config_request(self, "get_partition")

    def create_config_dir_result(self, result):
        if result:
            return "ok created config dir"
        else:
            return "error cannot create config dir"

    def get_partition_result(self, result):
        if result:
            return "ok created partition info"
        else:
            return "error cannot create partition info"

    def build_config_result(self, result):
        xml_result = server_command.srv_command(source=result)
        res_node = xml_result.xpath(".//ns:device[@pk='{:d}']".format(self.cc.device.pk), smart_strings=False)[0]
        self.log("result node has {}:".format(logging_tools.get_plural("attribute", len(res_node.attrib))))
        for key, value in res_node.attrib.iteritems():
            self.log("   {:<10s}: {}".format(key, value))
        del self.cc.pending_config_requests[self.cc.device.name]
        self.cc.done_config_requests[
            self.cc.device.name
        ] = "ok config built" if int(res_node.attrib["state_level"]) in [logging_tools.LOG_LEVEL_OK, logging_tools.LOG_LEVEL_WARN] else "error building config"
