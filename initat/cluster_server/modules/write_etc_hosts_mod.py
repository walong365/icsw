# Copyright (C) 2007-2008,2011-2015 Andreas Lang-Nevyjel
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

from config_tools import router_object
from django.db.models import Q
from initat.cluster.backbone.models import netdevice, device, device_variable, domain_tree_node
import cluster_location
import codecs
import cs_base_class
import ipvx_tools
import logging_tools
import networkx
import os
import process_tools

SSH_KNOWN_HOSTS_FILENAME = "/etc/ssh/ssh_known_hosts"
ETC_HOSTS_FILENAME = "/etc/hosts"
GROUP_DIR = "/opt/cluster/etc/pdsh"


class write_etc_hosts(cs_base_class.server_com):
    class Meta:
        needed_configs = ["auto_etc_hosts"]

    def _call(self, cur_inst):
        file_list = []
        server_idxs = [self.server_idx]
        # get additional idx if host is virtual server

        is_server, serv_idx, _server_type, _server_str, _config_idx, _real_server_name = cluster_location.is_server("server", True, False)
        if is_server and serv_idx != self.server_idx:
            server_idxs.append(serv_idx)
        # recognize for which devices i am responsible
        dev_r = cluster_location.device_recognition()
        server_idxs = list(set(server_idxs) | set(dev_r.device_dict.keys()))
        # get all peers to local machine and local netdevices
        my_idxs = netdevice.objects.exclude(
            Q(enabled=False)
        ).filter(
            Q(device__in=server_idxs) &
            Q(device__enabled=True) &
            Q(device__device_group__enabled=True)
        ).values_list("pk", flat=True)
        # ref_table
        route_obj = router_object(cur_inst.log)
        all_paths = []
        for s_ndev in my_idxs:
            all_paths.extend(networkx.shortest_path(route_obj.nx, s_ndev, weight="weight").values())
        # pprint.pprint(all_paths)
        nd_lut = {
            cur_nd.pk: cur_nd for cur_nd in netdevice.objects.all().select_related(
                "device"
            ).prefetch_related(
                "net_ip_set", "net_ip_set__network", "net_ip_set__domain_tree_node"
            )
        }
        # fetch key-information
        ssh_vars = device_variable.objects.filter(Q(name="ssh_host_rsa_key_pub")).select_related("device")
        rsa_key_dict = {}
        for _db_rec in ssh_vars:
            pass
        # read pre/post lines from /etc/hosts
        pre_host_lines, post_host_lines = ([], [])
        # parse pre/post host_lines
        try:
            host_lines = [line.strip() for line in codecs.open(ETC_HOSTS_FILENAME, "r", "utf-8").read().split("\n")]
        except:
            self.log(
                "error reading / parsing {}: {}".format(
                    ETC_HOSTS_FILENAME,
                    process_tools.get_except_info()),
                logging_tools.LOG_LEVEL_ERROR)
        else:
            mode, any_modes_found = (0, False)
            for line in host_lines:
                if line.lower().startswith("### aeh-start-pre"):
                    mode, any_modes_found = (1, True)
                elif line.lower().startswith("### aeh-start-post"):
                    mode, any_modes_found = (2, True)
                elif line.lower().startswith("### aeh-end"):
                    mode, any_modes_found = (0, True)
                else:
                    if mode == 1:
                        pre_host_lines.append(line)
                    elif mode == 2:
                        post_host_lines.append(line)
            if not any_modes_found:
                self.log("no ### aeh-.* stuff found in {}, copying to {}.orig".format(
                    ETC_HOSTS_FILENAME, ETC_HOSTS_FILENAME))
                try:
                    pass
                except:
                    self.log("error writing {}.orig: {}".format(
                        ETC_HOSTS_FILENAME,
                        process_tools.get_except_info()))
        # mapping from device_name to all names for ssh_host_keys
        name_dict = {}
        # ip dictionary
        ip_dict = {}
        # min_target_dict
        min_target_dict = {}
        for cur_path in all_paths:
            min_value = route_obj.get_penalty(cur_path)
            target_nd = nd_lut[cur_path[-1]]
            min_target_dict[target_nd] = min(min_target_dict.get(target_nd, 999999999), min_value)
        tl_dtn = domain_tree_node.objects.get(Q(depth=0))
        for cur_path in all_paths:
            target_nd = nd_lut[cur_path[-1]]
            min_value = min_target_dict[target_nd]
            for cur_ip in nd_lut[cur_path[-1]].net_ip_set.all():
                # get names
                host_names = []
                cur_dtn = cur_ip.domain_tree_node or tl_dtn
                if not (cur_ip.alias.strip() and cur_ip.alias_excl):
                    host_names.append("{}{}".format(target_nd.device.name, cur_dtn.node_postfix))
                host_names.extend(["{}".format(cur_entry) for cur_entry in cur_ip.alias.strip().split()])
                if "localhost" in [x.split(".")[0] for x in host_names]:
                    host_names = [host_name for host_name in host_names if host_name.split(".")[0] == "localhost"]
                if cur_dtn.full_name:
                    if cur_dtn.create_short_names:
                        # also create short_names
                        out_names = (
                            " ".join(
                                [
                                    "{}.{} {}".format(host_name, cur_dtn.full_name, host_name) for host_name in host_names if not host_name.count(".")
                                ]
                            )
                        ).split()
                    else:
                        # only print the long names
                        out_names = ["{}.{}".format(host_name, cur_dtn.full_name) for host_name in host_names if not host_name.count(".")]
                else:
                    if cur_dtn.create_short_names:
                        # also create short_names
                        out_names = (" ".join(["{}".format(host_name) for host_name in host_names if not host_name.count(".")])).split()
                    else:
                        # only print the long names
                        out_names = ["{}".format(host_name) for host_name in host_names if not host_name.count(".")]
                # add names with dot
                out_names.extend([host_name for host_name in host_names if host_name.count(".")])
                # name_dict without localhost
                name_dict.setdefault(
                    target_nd.device.name, []
                ).extend(
                    [
                        out_name for out_name in out_names if out_name not in name_dict[target_nd.device.name] and not out_name.startswith("localhost")
                    ]
                )
                ip_dict.setdefault(cur_ip.ip, [])
                if out_names not in [entry[1] for entry in ip_dict[cur_ip.ip]]:
                    if cur_ip.ip != "0.0.0.0":
                        ip_dict[cur_ip.ip].append((min_value, out_names))
        # out_list
        loc_dict = {}
        for ip, h_list in ip_dict.iteritems():
            all_values = sorted([entry[0] for entry in h_list])
            if all_values:
                min_value = all_values[0]
                out_names = []
                for val in all_values:
                    for _act_val, act_list in [(x_value, x_list) for x_value, x_list in h_list if x_value == val]:
                        out_names.extend([value for value in act_list if value not in out_names])
                # print min_value, ip, out_names
                loc_dict.setdefault(min_value, []).append([ipvx_tools.ipv4(ip)] + out_names)
        pen_list = sorted(loc_dict.keys())
        out_file = []
        for pen_value in pen_list:
            act_out_list = logging_tools.new_form_list()
            for entry in sorted(loc_dict[pen_value]):
                act_out_list.append([logging_tools.form_entry(entry[0])] + [logging_tools.form_entry(cur_e) for cur_e in entry[1:]])
            host_lines = str(act_out_list).split("\n")
            out_file.extend(["# penalty {:d}, {}".format(
                pen_value,
                logging_tools.get_plural("host entry", len(host_lines))), ""] + host_lines + [""])
        if not os.path.isdir(GROUP_DIR):
            try:
                os.makedirs(GROUP_DIR)
            except:
                pass
        if os.path.isdir(GROUP_DIR):
            # remove old files
            for file_name in os.listdir(GROUP_DIR):
                try:
                    os.unlink(os.path.join(GROUP_DIR, file_name))
                except:
                    pass
            # get all devices with netips
            all_devs = device.objects.filter(
                Q(enabled=True) &
                Q(device_group__enabled=True) &
                Q(netdevice__net_ip__ip__contains=".")
            ).values_list("name", "device_group__name").order_by("device_group__name", "name")
            dg_dict = {}
            for dev_name, dg_name in all_devs:
                dg_dict.setdefault(dg_name, []).append(dev_name)
            for file_name, content in dg_dict.iteritems():
                codecs.open(os.path.join(GROUP_DIR, file_name), "w", "utf-8").write("\n".join(sorted(set(content)) + [""]))
        file_list.append(ETC_HOSTS_FILENAME)
        codecs.open(ETC_HOSTS_FILENAME, "w+", "utf-8").write(
            "\n".join(
                [
                    "### AEH-START-PRE insert pre-host lines below"
                ] +
                pre_host_lines +
                [
                    "### AEH-END-PRE insert pre-host lines above",
                    ""
                ] +
                out_file +
                [
                    "",
                    "### AEH-START-POST insert post-host lines below"
                ] +
                post_host_lines +
                [
                    "### AEH-END-POST insert post-host lines above",
                    ""
                ]
            )
        )
        # write known_hosts_file
        if os.path.isdir(os.path.dirname(SSH_KNOWN_HOSTS_FILENAME)):
            skh_f = file(SSH_KNOWN_HOSTS_FILENAME, "w")
            for ssh_key_node in sorted(rsa_key_dict.keys()):
                skh_f.write(
                    "{} {}\n".format(
                        ",".join(name_dict.get(ssh_key_node, [ssh_key_node])), rsa_key_dict[ssh_key_node]
                    )
                )
            skh_f.close()
            file_list.append(SSH_KNOWN_HOSTS_FILENAME)
        cur_inst.srv_com.set_result(
            "wrote {}".format(", ".join(sorted(file_list)))
        )
