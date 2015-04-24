# Copyright (C) 2007-2009,2013-2015 Andreas Lang-Nevyjel
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

from django.db.models import Q
from initat.cluster.backbone.models import net_ip, device, \
    domain_tree_node, config, network
from initat.cluster_server.config import global_config
import commands
import codecs
from initat.tools import config_tools
import cs_base_class
import grp
from initat.tools import ipvx_tools
from initat.tools import logging_tools
import os
from initat.tools import process_tools
import pwd
from initat.tools import server_command
import time


class write_nameserver_config(cs_base_class.server_com):
    class Meta:
        needed_configs = ["name_server"]

    def _call(self, cur_inst):
        _log_lines, sys_dict = process_tools.fetch_sysinfo("/")
        sys_version = sys_dict["version"]
        if sys_version.startswith("8") or sys_version == "sles8":
            named_dir = "/var/named"
        else:
            named_dir = "/var/lib/named"
        if not os.path.isdir(named_dir):
            cur_inst.srv_com.set_result(
                "error no named_dir {}".format(named_dir),
                server_command.SRV_REPLY_STATE_ERROR
            )
            return
        cur_config = config.objects.get(Q(name="name_server"))
        act_conf_dict = config_tools.get_config_var_list(
            cur_config,
            device.objects.get(Q(pk=self.server_idx))
            )
        # get domain of server (to be used in SOA records of reverse maps)
        top_level_name = device.objects.get(Q(pk=self.server_idx)).domain_tree_node.full_name
        # get user/group id
        # print act_conf_dict.get("USER", "root")
        if "USER" in act_conf_dict:
            named_user = act_conf_dict["USER"].value
        else:
            named_user = "root"
        if "GROUP" in act_conf_dict:
            named_group = act_conf_dict["GROUP"].value
        else:
            named_group = "root"
        try:
            named_uid = pwd.getpwnam(named_user)[2]
        except KeyError:
            named_uid = 0
        try:
            named_gid = grp.getgrnam(named_group)[2]
        except KeyError:
            named_gid = 0
        cf_lines = [
            "options {",
            "  default-server localhost;",
            "};",
            "server localhost {",
            "  key key1;",
            "};",
            "key key1 {",
            "  algorithm hmac-md5;"
        ]
        if act_conf_dict.has_key("SECRET"):
            cf_lines.append("  secret \"%s\" ;" % (act_conf_dict["SECRET"].value))
        cf_lines.append("};")
        ncf_lines = ["options {",
                     "  directory \"%s\";\n" % (named_dir),
                     "  datasize default;",
                     "  stacksize default;",
                     "  coresize default;",
                     "  empty-zones-enable no;",
                     # "  files unlimited;",
                     "  auth-nxdomain no;"]
        forwarders = [act_conf_dict[key].value for key in act_conf_dict.iterkeys() if key.startswith("FORWARDER")]
        if len(forwarders):
            ncf_lines.append("  forwarders {\n%s\n  };" % ("\n".join(["    %s;" % (x) for x in forwarders if x])))
        ncf_lines.append("  listen-on {")
        server_idxs = [self.server_idx]
        my_ips = net_ip.objects.filter(Q(netdevice__device__in=server_idxs)).values_list("ip", flat=True)
        for my_ip in my_ips:
            ncf_lines.append("    %s;" % (my_ip))
        ncf_lines.extend(
            [
                "  };",
                "  allow-query { any; };",
                "  allow-recursion { any; };",
                "};",
                "",
                "controls {",
                "  inet * allow { any ; } keys { \"key1\"; };",
                "};",
                "",
                # "include \"/etc/rndc.key\";",
                # "",
                # ])
                "key key1 {",
                "  algorithm hmac-md5;",
            ]
        )
        if act_conf_dict.has_key("SECRET"):
            ncf_lines.append("  secret \"%s\" ;" % (act_conf_dict["SECRET"].value))
        ncf_lines.extend(["};"])
        # ncf_lines.extend(["logging{",
        # "  channel simple_log {",
        # "    file \"/var/log/named/bind.log\" versions 3 size 5m;",
        # "    severity warning;",
        # "    print-time yes;",
        # "    print-severity yes;",
        # "    print-category yes;",
        # "  };",
        # "  category default{",
        # "    simple_log;",
        # "  };",
        # "};"])
        ncf_lines.extend(["\nzone \".\" IN {",
                          "  type hint;",
                          "  file \"root.hint\";",
                          "};"])
        ncf_lines.extend(["\ninclude \"/etc/named.conf.include\";"])
        # print ncf_lines
        real_config_name = "name_server" # self.act_config_name.replace("%", "")
        # other_conf = {"name_server" : "name_slave",
        #              "name_slave"  : "name_server"}[real_config_name]
        # get peers
        # sql_str = "SELECT i.ip, d.name FROM netip i INNER JOIN netdevice n INNER JOIN device_config dc INNER JOIN new_config c INNER JOIN network nw INNER JOIN network_type nt INNER JOIN hopcount h INNER JOIN device d INNER JOIN device_group dg " + \
        #          "LEFT JOIN device d2 ON d2.device_idx=dg.device WHERE d.device_group=dg.device_group_idx AND n.device=d.device_idx AND i.network=nw.network_idx AND nw.network_type=nt.network_type_idx AND nt.identifier='p' AND " + \
        #          "n.netdevice_idx=h.s_netdevice AND (%s) AND (d.device_idx=dc.device OR d2.device_idx=dc.device) AND dc.new_config=c.new_config_idx AND c.name='%s' AND i.netdevice=n.netdevice_idx ORDER BY h.value" % (" OR ".join(["h.d_netdevice=%d" % (x) for x in my_netdev_idxs]), other_conf)
        # call_params.dc.execute(sql_str)
        master_ips, slave_ips = ([], [])
        if False:
            if real_config_name == "name_server":
                # get slaves
                # slave_ips = [x["ip"] for x in call_params.dc.fetchall()]
                sub_dir = "master"
            elif real_config_name == "name_slave":
                # get masters
                # master_ips = [x["ip"] for x in call_params.dc.fetchall()]
                sub_dir = "slave"
        else:
            sub_dir = "master"
        # top level dtn
        tl_dtn = domain_tree_node.objects.get(Q(depth=0))
        # print master_ips, slave_ips

        # loop 1: forward maps
        all_dtns = domain_tree_node.objects.filter(Q(write_nameserver_config=True))
        cur_serial = int(time.strftime("%Y%m%d%H", time.localtime(time.time())))
        CS_FILENAME = "/tmp/.cs_serial"
        if os.path.isfile(CS_FILENAME):
            try:
                last_serial = int(file(CS_FILENAME, "r").read().strip())
            except:
                pass
            else:
                while cur_serial <= last_serial:
                    cur_serial += 1
        try:
            file(CS_FILENAME, "w").write("%d" % (cur_serial))
        except:
            pass
        for cur_dtn in all_dtns:
            nwname = cur_dtn.full_name
            if not nwname:
                continue
            write_zone_file = True
            name, name2 = (nwname, nwname)
            ncf_lines.append("\nzone \"%s\" IN {" % (name))
            zonefile_name = "%s.zone" % (name2)
            if nwname == "localdomain":
                # special handling
                ncf_lines.extend(["  type master;",
                                  "  notify no;",
                                  "  allow-transfer { none; };"])
            else:
                if real_config_name == "name_server":
                    ncf_lines.append("  type master;")
                    if len(slave_ips):
                        ncf_lines.extend(["  notify yes;",
                                          "  allow-transfer { %s; };" % ("; ".join(slave_ips)),
                                          "  also-notify { %s; };\n" % ("; ".join(slave_ips))])
                    else:
                        ncf_lines.extend(["  notify no;",
                                          "  allow-transfer { none; };",
                                          "  allow-update { none; };"])
                elif real_config_name == "name_slave":
                    zonefile_name = "slave/%s.zone" % (name2)
                    write_zone_file = False
                    ncf_lines.extend(["  type slave;",
                                      "  allow-transfer { none; };",
                                      "  notify no;",
                                      "  masters { %s; };" % ("; ".join(master_ips))])
            ncf_lines.extend(["  file \"%s/%s\";" % (sub_dir, zonefile_name),
                              "};"])
            if write_zone_file:
                _lines = []
                zname = "%s." % (nwname)
                _lines.extend(["$ORIGIN %s" % (zname),
                              "$TTL 30M",
                              "%s  IN SOA %s lang-nevyjel.%s. (" % (zname, nwname, nwname)])
                for what in [str(cur_serial), "1H", "15M", "1W", "30M"]:
                    _lines.append("%s%s" % (" " * 10, what))
                _lines.extend(["%s)" % (" " * 5),
                              "; NS and MX-records"])
                _form = logging_tools.form_list()
                _form.set_format_string(3, "s", "-", "; ")
                _form.add_line([" ", "IN NS", "%s." % (global_config["SERVER_SHORT_NAME"]), ""])
                for dev_type in [0]:
                    addstr = "real"
                    # if net.identifier == "l":
                    #    sel_str = " AND d.name='%s'" % (global_config["SERVER_SHORT_NAME"])
                    # else:
                    #    sel_str = ""
                    print_ips = net_ip.objects.filter(
                        Q(domain_tree_node=cur_dtn) &
                        Q(netdevice__device__enabled=True) & Q(netdevice__device__device_group__enabled=True) &
                        Q(domain_tree_node__write_nameserver_config=True) &
                        Q(netdevice__device__is_meta_device=False)
                    ).select_related("netdevice__device", "domain_tree_node").order_by("ip")
                    num_ips = print_ips.count()
                    if num_ips:
                        _form.add_line(
                            "; {} {}".format(
                                addstr,
                                logging_tools.get_plural("record", num_ips)
                            )
                        )
                        for ret in print_ips:
                            out_names = []
                            if not (ret.alias.strip() and ret.alias_excl):
                                out_names.append("%s%s" % (ret.netdevice.device.name, cur_dtn.node_postfix))
                            out_names.extend(ret.alias.strip().split())
                            first = True
                            for s_name in out_names:
                                if first:
                                    first = False
                                    f_name = s_name
                                    _form.add_line([s_name, "IN A", ret.ip, ret.netdevice.device.comment])
                                else:
                                    _form.add_line([s_name, "CNAME", f_name, ret.netdevice.device.comment])
                _lines.extend(unicode(_form).split(u"\n"))
                _file_name = "%s/%s/%s.zone" % (named_dir, sub_dir, nwname)
                codecs.open(_file_name, "w", "utf-8").write("\n".join(_lines + [""]))
                os.chmod(_file_name, 0600)
                os.chown(_file_name, named_uid, named_gid)


        # loop 2: reverse maps

        nets = network.objects.all() # filter(Q(write_bind_config=True))
        # call_params.dc.execute("SELECT n.network_idx, n.netmask, n.name, n.postfix, n.network, nt.identifier FROM network n, network_type nt WHERE n.network_type=nt.network_type_idx AND n.write_bind_config")
        # nets = call_params.dc.fetchall()
        for net in nets:
            nw_ip = ipvx_tools.ipv4(net.network)
            nw_mask = ipvx_tools.ipv4(net.netmask)
            nw_ip_parts, nw_mask_parts = (
                nw_ip.parts,
                nw_mask.parts)
            network_parts = 4
            while True:
                if not nw_mask_parts or nw_mask_parts[-1]:
                    break
                network_parts -= 1
                nw_mask_parts.pop(-1)
                nw_ip_parts.pop(-1)
            nw_flipped_parts = [value for value in nw_ip_parts]
            nw_flipped_parts.reverse()
            nw_flipped_ip = ".".join(["%d" % (value) for value in nw_flipped_parts])
            nw_ip = ".".join(["%d" % (value) for value in nw_ip_parts])
            write_zone_file = True
            if not nw_flipped_ip:
                continue
            for name, name2 in [("%s.in-addr.arpa" % (nw_flipped_ip), nw_ip)]:
                ncf_lines.append("\nzone \"%s\" IN {" % (name))
                zonefile_name = "%s.zone" % (name2)
                if net.identifier == "l":
                    ncf_lines.extend(["  type master;",
                                      "  notify no;",
                                      "  allow-transfer { none; };"])
                else:
                    if real_config_name == "name_server":
                        ncf_lines.append("  type master;")
                        if len(slave_ips):
                            ncf_lines.extend(["  notify yes;",
                                              "  allow-transfer { %s; };" % ("; ".join(slave_ips)),
                                              "  also-notify { %s; };\n" % ("; ".join(slave_ips))])
                        else:
                            ncf_lines.extend(["  notify no;",
                                              "  allow-transfer { none; };",
                                              "  allow-update { none; };"])
                    elif real_config_name == "name_slave":
                        zonefile_name = "slave/%s.zone" % (name2)
                        write_zone_file = False
                        ncf_lines.extend(["  type slave;",
                                          "  allow-transfer { none; };",
                                          "  notify no;",
                                          "  masters { %s; };" % ("; ".join(master_ips))])
                ncf_lines.extend(["  file \"%s/%s\";" % (sub_dir, zonefile_name),
                                  "};"])

            if write_zone_file:
                _lines = []
                zname = "%s.in-addr.arpa." % (nw_flipped_ip)
                _lines.extend(["$ORIGIN %s" % (zname),
                              "$TTL 30M",
                              "%s  IN SOA %s lang-nevyjel. (" % (zname, top_level_name)])
                for what in [str(cur_serial), "1H", "15M", "1W", "30M"]:
                    _lines.append("%s%s" % (" " * 10, what))
                _lines.extend(["%s)" % (" " * 5),
                              "; NS and MX-records"])
                _form = logging_tools.form_list()
                _form.set_format_string(3, "s", "-", "; ")
                _form.add_line([" ", "IN NS", "%s%s.%s." % (global_config["SERVER_SHORT_NAME"], "init", "at"), ""])
                for dev_type in [0]:
                    addstr = "real"
                    # if net.identifier == "l":
                    #    sel_str = " AND d.name='%s'" % (global_config["SERVER_SHORT_NAME"])
                    # else:
                    #    sel_str = ""
                    print_ips = net_ip.objects.filter(
                        Q(netdevice__device__enabled=True) & Q(netdevice__device__device_group__enabled=True) &
                        Q(domain_tree_node__write_nameserver_config=True) &
                        Q(netdevice__device__is_meta_device=False) &
                        Q(network=net)).select_related("netdevice__device", "domain_tree_node").order_by("ip")
                    num_ips = print_ips.count()
                    if num_ips:
                        _form.add_line(
                            "; {} {}".format(
                                addstr,
                                logging_tools.get_plural("record", num_ips)
                            )
                        )
                        for ret in print_ips:
                            host_part = str(ipvx_tools.ipv4(ret.ip) & (~ipvx_tools.ipv4(net.network))).split(".")
                            host_part.reverse()
                            for _idx in range(network_parts):
                                host_part.pop(-1)
                            fiand = ".".join(reversed(host_part))
                            out_names = []
                            if ret.domain_tree_node_id:
                                cur_dtn = ret.domain_tree_node
                            else:
                                cur_dtn = tl_dtn
                            if not (ret.alias.strip() and ret.alias_excl):
                                out_names.append("%s%s" % (ret.netdevice.device.name, cur_dtn.node_postfix))
                            out_names.extend(ret.alias.strip().split())
                            for s_name in out_names:
                                _form.add_line([fiand, "IN PTR", "%s.%s." % (s_name, cur_dtn.full_name), ret.netdevice.device.comment])
                _lines.extend(unicode(_form).split("\n"))
                file_name = "%s/%s/%s.zone" % (named_dir, sub_dir, nw_ip)
                codecs.open(file_name, "w", "utf-8").write("\n".join(_lines + [""]))
                os.chmod(file_name, 0600)
                os.chown(file_name, named_uid, named_gid)
        cfile = "/etc/rndc.conf"
        ncname = "/etc/named.conf"
        file(ncname, "w").write("\n".join(ncf_lines + [""]))
        file(cfile, "w").write("\n".join(cf_lines + [""]))
        os.chmod(cfile, 0600)
        os.chmod(ncname, 0600)
        os.chown(ncname, named_uid, named_gid)
        cstat, cout = commands.getstatusoutput("/usr/sbin/rndc reload")
        if cstat:
            cur_inst.srv_com.set_result(
                "wrote nameserver-config ({}), reloading gave: '{}".format(
                    logging_tools.get_plural("network", len(nets)),
                    cout
                ),
                server_command.SRV_REPLY_STATE_ERROR
            )
        else:
            cur_inst.srv_com.set_result(
                "wrote nameserver-config ({}) and successfully reloaded configuration".format(
                    logging_tools.get_plural("network", len(nets)),
                )
            )
