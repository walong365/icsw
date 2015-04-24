# Copyright (C) 2001-2008,2012-2015 Andreas Lang-Nevyjel, init.at
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
""" cluster-config-server, build process """

from django.db import connection
from django.db.models import Q
from initat.cluster.backbone.models import device, network, config, log_level_lookup, LogSource, \
    net_ip
from initat.cluster.backbone.routing import get_server_uuid, get_type_from_config
from initat.cluster_config_server.build_client import build_client
from initat.cluster_config_server.build_container import generated_tree, build_container
from initat.cluster_config_server.config import global_config
from initat.tools import config_tools
from initat.tools import logging_tools
from initat.tools import threading_tools
import time


def pretty_print(name, obj, offset):
    lines = []
    off_str = " " * offset
    if type(obj) == dict:
        if name:
            head_str = "%s%s(D):" % (off_str, name)
            lines.append(head_str)
        else:
            head_str = ""
        keys = sorted(obj.keys())
        max_len = max([len(key) for key in keys])
        for key in keys:
            lines.extend(pretty_print(
                ("%s%s" % (key, " " * max_len))[0:max_len],
                obj[key],
                len(head_str)))
    elif type(obj) in [list, tuple]:
        head_str = "%s%s(L %d):" % (off_str, name, len(obj))
        lines.append(head_str)
        idx = 0
        for value in obj:
            lines.extend(pretty_print("%d" % (idx), value, len(head_str)))
            idx += 1
    elif isinstance(obj, basestring):
        if obj:
            lines.append("%s%s(S): %s" % (off_str, name, obj))
        else:
            lines.append("%s%s(S): (empty string)" % (off_str, name))
    elif type(obj) in [type(2), type(2L)]:
        lines.append("%s%s(I): %d" % (off_str, name, obj))
    else:
        lines.append("%s%s(?): %s" % (off_str, name, str(obj)))
    return lines


class network_tree(dict):
    def __init__(self):
        all_nets = network.objects.all().select_related("network_type", "master_network")  # @UndefinedVariable
        for cur_net in all_nets:
            self[cur_net.pk] = cur_net
            self.setdefault(cur_net.network_type.identifier, {})[cur_net.pk] = cur_net
            # idx_list, self and slaves
            cur_net.idx_list = [cur_net.pk]
        for net_pk, cur_net in self.iteritems():
            if type(net_pk) in [int, long]:
                if cur_net.network_type.identifier == "s":
                    if cur_net.master_network_id in self and self[cur_net.master_network_id].network_type.identifier == "p":
                        self[cur_net.master_network_id].idx_list.append(net_pk)


class build_process(threading_tools.process_obj):
    def process_init(self):
        self.__log_template = logging_tools.get_logger(
            global_config["LOG_NAME"],
            global_config["LOG_DESTINATION"],
            zmq=True,
            context=self.zmq_context,
            init_logger=True)
        # close database connection
        connection.close()
        self.router_obj = config_tools.router_object(self.log)
        self.config_src = LogSource.objects.get(Q(pk=global_config["LOG_SOURCE_IDX"]))
        self.register_func("generate_config", self._generate_config)
        # for requests from config_control
        self.register_func("complex_request", self._complex_request)
        build_client.init(self)

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)

    def loop_post(self):
        build_client.close_clients()
        self.__log_template.close()

    def _complex_request(self, queue_id, dev_name, req_name, *args, **kwargs):
        self.log("got request '%s' for '%s' (%d)" % (req_name, dev_name, queue_id))
        cur_c = build_client.get_client(name=dev_name)
        success = getattr(cur_c, req_name)(*args)
        self.send_pool_message("complex_result", queue_id, success)

    def _generate_config(self, attr_dict, **kwargs):
        if global_config["DEBUG"]:
            cur_query_count = len(connection.queries)
        # get client
        cur_c = build_client.get_client(**attr_dict)
        cur_c.log("starting config build")
        s_time = time.time()
        dev_sc = None
        # get device by name
        try:
            if cur_c.name.count("."):
                b_dev = device.objects.select_related("device_group").prefetch_related("netdevice_set", "netdevice_set__net_ip_set").get(
                    Q(name=cur_c.name.split(".")[0]) &
                    Q(domain_tree_node__full_name=cur_c.name.split(".", 1)[1])
                    )
            else:
                b_dev = device.objects.select_related("device_group").prefetch_related("netdevice_set", "netdevice_set__net_ip_set").get(
                    Q(name=cur_c.name))
        except device.DoesNotExist:
            cur_c.log("device not found by name", logging_tools.LOG_LEVEL_ERROR, state="done")
        except device.MultipleObjectsReturned:
            cur_c.log("more than one device with name '%s' found" % (cur_c.name), logging_tools.LOG_LEVEL_ERROR, state="done")
        else:
            dev_sc = config_tools.server_check(
                host_name=cur_c.name,
                server_type="node",
                fetch_network_info=True
            )
            cur_c.log("server_check report(): %s" % (dev_sc.report()))
            cur_net_tree = network_tree()
            # sanity checks
            if not cur_c.create_config_dir():
                cur_c.log("creating config_dir", logging_tools.LOG_LEVEL_ERROR, state="done")
            elif (b_dev.prod_link_id == 0 or not b_dev.prod_link):
                cur_c.log("no valid production_link set", logging_tools.LOG_LEVEL_ERROR, state="done")
            elif len(cur_net_tree.get("b", {})) > 1:
                cur_c.log("more than one boot network found", logging_tools.LOG_LEVEL_ERROR, state="done")
            elif not len(cur_net_tree.get("b", {})):
                cur_c.log("no boot network found", logging_tools.LOG_LEVEL_ERROR, state="done")
            elif not len(cur_net_tree.get("p", {})):
                cur_c.log("no production networks found", logging_tools.LOG_LEVEL_ERROR, state="done")
            else:
                cur_c.log("found %s: %s" % (
                    logging_tools.get_plural("production network", len(cur_net_tree["p"])),
                    ", ".join([unicode(cur_net) for cur_net in cur_net_tree["p"].itervalues()])))
                act_prod_net = None
                for prod_net in cur_net_tree["p"].itervalues():
                    cur_c.clean_directory(prod_net.identifier)
                    cur_c.log("%s %s" % (
                        "active" if prod_net.pk == b_dev.prod_link_id else "inactive",
                        prod_net.get_info()))
                    if prod_net.pk == b_dev.prod_link.pk:
                        act_prod_net = prod_net
                if not act_prod_net:
                    cur_c.log("invalid production link", logging_tools.LOG_LEVEL_ERROR, state="done")
                else:
                    ips_in_prod = [cur_ip.ip for cur_ip in dev_sc.identifier_ip_lut.get("p", [])]
                    if ips_in_prod:
                        netdevices_in_net = [dev_sc.ip_netdevice_lut[ip] for ip in ips_in_prod]
                        if b_dev.bootnetdevice_id and b_dev.bootnetdevice:
                            net_devs_ok = [net_dev for net_dev in netdevices_in_net if net_dev.pk == b_dev.bootnetdevice.pk]
                            net_devs_warn = [net_dev for net_dev in netdevices_in_net if net_dev.pk != b_dev.bootnetdevice.pk]
                        else:
                            net_devs_ok, net_devs_warn = ([], netdevices_in_net)
                        if len(net_devs_ok) == 1:
                            boot_netdev = net_devs_ok[0]
                            # finaly, we have the device, the boot netdevice, actual production net
                            self._generate_config_step2(cur_c, b_dev, act_prod_net, boot_netdev, dev_sc)
                        elif len(net_devs_ok) > 1:
                            cur_c.log(
                                "too many netdevices (%d) with IP in production network found" % (len(net_devs_ok)),
                                logging_tools.LOG_LEVEL_ERROR,
                                state="done"
                            )
                        elif len(net_devs_warn) == 1:
                            cur_c.log(
                                " one netdevice with IP in production network found but not on bootnetdevice",
                                logging_tools.LOG_LEVEL_ERROR,
                                state="done"
                            )
                        else:
                            cur_c.log(
                                "too many netdevices (%d) with IP in production network found (not on bootnetdevice!)" % (len(net_devs_warn)),
                                logging_tools.LOG_LEVEL_ERROR,
                                state="done"
                            )
                    else:
                        cur_c.log("no IP-address in production network", logging_tools.LOG_LEVEL_ERROR, state="done")
        cur_c.log_kwargs("after build", only_new=False)
        # done (yeah ?)
        # send result
        e_time = time.time()
        if dev_sc:
            dev_sc.device.add_log_entry(
                source=self.config_src,
                level=log_level_lookup(int(cur_c.state_level)),
                text="built config in %s" % (logging_tools.get_diff_time_str(e_time - s_time))
            )
        cur_c.log("built took %s" % (logging_tools.get_diff_time_str(e_time - s_time)))
        if global_config["DEBUG"]:
            tot_query_count = len(connection.queries) - cur_query_count
            cur_c.log("queries issued: %d" % (tot_query_count))
            for q_idx, act_sql in enumerate(connection.queries[cur_query_count:], 1):
                cur_c.log(" %4d %s" % (q_idx, act_sql["sql"][:120]))
        # pprint.pprint(cur_c.get_send_dict())
        self.send_pool_message("client_update", cur_c.get_send_dict())

    def _generate_vtl(self, conf_dict):
        vtl = []
        for key in sorted(conf_dict.keys()):
            value = self._to_unicode(conf_dict[key])
            vtl.append((key, value))
        return vtl

    def _to_unicode(self, value):
        if isinstance(value, basestring):
            value = u"'%s'" % (unicode(value))
        elif type(value) in [long, int]:
            value = "%d" % (value)
        elif type(value) in [list]:
            value = u"{LIST} [%s]" % (", ".join([self._to_unicode(s_value) for s_value in value]))
        elif type(value) in [dict]:
            value = u"{DICT} %s" % (unicode(value))
        else:
            value = u"{CLASS %s} '%s'" % (
                value.__class__.__name__,
                unicode(value),
                )
        return value

    def _generate_config_step2(self, cur_c, b_dev, act_prod_net, boot_netdev, dev_sc):
        self.router_obj.check_for_update()
        running_ip = [ip.ip for ip in dev_sc.identifier_ip_lut["p"] if dev_sc.ip_netdevice_lut[ip.ip].pk == boot_netdev.pk][0]
        cur_c.log("IP in production network '%s' is %s, network_postfix is '%s'" % (
            act_prod_net.identifier,
            running_ip,
            act_prod_net.postfix))
        # multiple configs
        multiple_configs = ["server"]
        all_servers = config_tools.device_with_config("%server%")
        def_servers = all_servers.get("server", [])
        # def_servers = []
        if not def_servers:
            cur_c.log("no Servers found", logging_tools.LOG_LEVEL_ERROR, state="done")
        else:
            srv_names = sorted(
                [
                    "{}{}".format(cur_srv.short_host_name, act_prod_net.postfix) for cur_srv in def_servers
                ]
            )
            cur_c.log(
                "{} found: {}".format(
                    logging_tools.get_plural("server", len(def_servers)),
                    ", ".join(srv_names)
                )
            )
            # store in act_prod_net
            conf_dict = {}
            conf_dict["servers"] = srv_names
            for server_type in sorted(all_servers.keys()):
                if server_type not in multiple_configs:
                    routing_info, act_server, routes_found = ([66666666], None, 0)
                    for actual_server in all_servers[server_type]:
                        act_routing_info = actual_server.get_route_to_other_device(
                            self.router_obj,
                            dev_sc,
                            filter_ip=running_ip,
                            allow_route_to_other_networks=True
                        )
                        if act_routing_info:
                            routes_found += 1
                            # store in some dict-like structure
                            # print "***", actual_server.short_host_name, dir(actual_server)
                            # FIXME, postfix not handled
                            conf_dict["%s:%s" % (actual_server.short_host_name, server_type)] = actual_server.device.full_name
                            conf_dict["%s:%s_ip" % (actual_server.short_host_name, server_type)] = act_routing_info[0][2][1][0]
                            if server_type in ["config_server", "mother_server"] and actual_server.device.pk == b_dev.bootserver_id:
                                routing_info, act_server = (act_routing_info[0], actual_server)
                            else:
                                if act_routing_info[0][0] < routing_info[0]:
                                    routing_info, act_server = (act_routing_info[0], actual_server)
                        else:
                            cur_c.log("empty routing info for %s to %s" % (
                                server_type,
                                actual_server.device.name), logging_tools.LOG_LEVEL_WARN)
                    if act_server:
                        server_ip = routing_info[2][1][0]
                        # map from server_ip to localized name
                        conf_dict[server_type] = net_ip.objects.get(Q(ip=server_ip)).full_name
                        conf_dict["{}_ip".format(server_type)] = server_ip
                        r_type = get_type_from_config(server_type)
                        if r_type:
                            conf_dict["{}_uuid".format(server_type)] = get_server_uuid(r_type, act_server.device.uuid)
                        cur_c.log("  %20s: %-25s (IP %15s)%s" % (
                            server_type,
                            conf_dict[server_type],
                            server_ip,
                            " (best of %d)" % (routes_found) if routes_found > 1 else ""))
                    else:
                        cur_c.log("  %20s: not found" % (server_type))
            new_img = b_dev.new_image
            if new_img:
                conf_dict["system"] = {
                    "vendor": new_img.sys_vendor,
                    "version": new_img.sys_version,
                    "release": new_img.sys_release,
                }
            else:
                self.log("no image defined, using defaults")
                conf_dict["system"] = {
                    "vendor": "suse",
                    "version": 13,
                    "release": 1,
                }
            conf_dict["device"] = b_dev
            conf_dict["net"] = act_prod_net
            conf_dict["host"] = b_dev.name
            conf_dict["hostfq"] = b_dev.full_name
            conf_dict["device_idx"] = b_dev.pk
            # image is missing, FIXME
# #                    dc.execute("SELECT * FROM image WHERE image_idx=%s", (self["new_image"]))
# #                    if dc.rowcount:
# #                        act_prod_net["image"] = dc.fetchone()
# #                    else:
# #                        act_prod_net["image"] = {}
            config_pks = list(config.objects.filter(
                Q(device_config__device=b_dev) | (
                    Q(device_config__device__device_group=b_dev.device_group_id) &
                    Q(device_config__device__is_meta_device=True)
                )
            ). order_by("-priority", "name").distinct().values_list("pk", flat=True))
            parent_pks = []
            while True:
                new_pks = set(
                    config.objects.exclude(parent_config=None).filter(
                        Q(pk__in=config_pks + parent_pks)
                    ).values_list("parent_config", flat=True)) - set(config_pks + parent_pks)
                if new_pks:
                    parent_pks.extend(list(new_pks))
                else:
                    break
            pseudo_config_list = config.objects.all().prefetch_related(
                "config_str_set", "config_int_set", "config_bool_set", "config_blob_set", "config_script_set"
            ).order_by("-priority", "name")
            config_dict = dict([(cur_pc.pk, cur_pc) for cur_pc in pseudo_config_list])
            # copy variables
            for p_config in pseudo_config_list:
                for var_type in ["str", "int", "bool", "blob"]:
                    for cur_var in getattr(p_config, "config_%s_set" % (var_type)).all():
                        conf_dict["%s.%s" % (p_config.name, cur_var.name)] = cur_var.value
            for _cur_conf in pseudo_config_list:
                # cur_conf.show_variables(cur_c.log, detail=global_config["DEBUG"])
                pass
            cur_c.log("%s found: %s, %s found: %s" % (
                logging_tools.get_plural("config", len(config_pks)),
                ", ".join([config_dict[pk].name for pk in config_pks]) if config_pks else "no configs",
                logging_tools.get_plural("parent config", len(parent_pks)),
                ", ".join([config_dict[pk].name for pk in parent_pks]) if parent_pks else "no parent configs"))
            # extend with parent pks
            config_pks.extend(list(parent_pks))
            # node interfaces
            conf_dict["node_if"] = []
            taken_list, not_taken_list = ([], [])
            for cur_net in b_dev.netdevice_set.exclude(
                    Q(enabled=False)
            ).prefetch_related(
                "net_ip_set",
                "net_ip_set__network",
                "net_ip_set__network__network_type",
                "net_ip_set__domain_tree_node"
            ):
                for cur_ip in cur_net.net_ip_set.all():
                    # if cur_ip.network_id
                    if cur_ip.network_id in act_prod_net.idx_list:
                        take_it, cause = (True, "network_index in list")
                    elif cur_ip.network.network_type.identifier == "l":
                        take_it, cause = (True, "network_type is loopback")
                    else:
                        if cur_ip.domain_tree_node and cur_ip.domain_tree_node.always_create_ip:
                            take_it, cause = (True, "network_index not in list but always_create_ip set")
                        else:
                            take_it, cause = (False, "network_index not in list and always_create_ip not set")
                    if take_it:
                        conf_dict["node_if"].append(cur_ip)
                        taken_list.append((cur_ip, cause))
                    else:
                        not_taken_list.append((cur_ip, cause))
            cur_c.log("%s in taken_list" % (logging_tools.get_plural("Netdevice", len(taken_list))))
            for entry, cause in taken_list:
                cur_c.log("  - %-6s (IP %-15s, network %-20s) : %s" % (
                    entry.netdevice.devname,
                    entry.ip,
                    unicode(entry.network),
                    cause))
            cur_c.log("%s in not_taken_list" % (logging_tools.get_plural("Netdevice", len(not_taken_list))))
            for entry, cause in not_taken_list:
                cur_c.log("  - %-6s (IP %-15s, network %-20s) : %s" % (
                    entry.netdevice.devname,
                    entry.ip,
                    unicode(entry.network),
                    cause))
            if cur_c.command == "get_config_vars":
                cur_c.var_tuple_list = self._generate_vtl(conf_dict)
                cur_c.add_set_keys("var_tuple_list")
                cur_c.log("vars created", state="done")
            elif cur_c.command == "build_config":
                # create config
                # dict: which config was called (sucessfully)
                conf_dict["called"] = {}
                cur_c.conf_dict, cur_c.link_dict, cur_c.erase_dict = ({}, {}, {})
                # cur_c.conf_dict[config_obj.dest] = config_obj
                new_tree = generated_tree()
                cur_bc = build_container(cur_c, config_dict, conf_dict, new_tree, self.router_obj)
                for pk in config_pks:
                    cur_bc.process_scripts(pk)
                new_tree.write_config(cur_c, cur_bc)
                if False in conf_dict["called"]:
                    cur_c.log(
                        "error in scripts for {}: {}".format(
                            logging_tools.get_plural("config", len(conf_dict["called"][False])),
                            ", ".join(sorted([unicode(config_dict[pk]) for pk, err_lines in conf_dict["called"][False]]))
                        ),
                        logging_tools.LOG_LEVEL_ERROR,
                        state="done"
                    )
                    cur_c.add_set_keys("error_dict")
                    cur_c.error_dict = dict([(unicode(config_dict[pk]), err_lines) for pk, err_lines in conf_dict["called"][False]])
                else:
                    cur_c.log("config built", state="done")
                cur_bc.close()
            else:
                cur_c.log("unknown action '%s'" % (cur_c.command), logging_tools.LOG_LEVEL_ERROR, state="done")
