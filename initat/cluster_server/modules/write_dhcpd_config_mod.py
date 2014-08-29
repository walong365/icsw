# Copyright (C) 2007-2008,2012-2014 Andreas Lang-Nevyjel
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
""" writes the dhcpd.conf in /etc """

from django.db.models import Q
from initat.cluster.backbone.models import network
from initat.cluster_server.config import global_config
import config_tools
import cs_base_class
import os
import process_tools
import server_command


class write_dhcpd_config(cs_base_class.server_com):
    class Meta:
        needed_configs = ["mother_server"]
        needed_option_keys = ["authoritative"]

    def _call(self, cur_inst):
        my_c = config_tools.server_check(server_type="mother_server")
        boot_ips = my_c.identifier_ip_lut.get("b", [])
        if len(boot_ips) > 1:
            cur_inst.srv_com.set_result(
                "error more than one boot-net found for '%s'" % (global_config["SERVER_SHORT_NAME"]),
                server_command.SRV_REPLY_STATE_ERROR)
        elif not boot_ips:
            cur_inst.srv_com.set_result(
                "error no boot-net found for '%s'" % (global_config["SERVER_SHORT_NAME"]),
                server_command.SRV_REPLY_STATE_ERROR)
        else:
            boot_ip = boot_ips[0]
            boot_net = boot_ip.network
            add_nets = list(
                [
                    (cur_net.network_type.identifier, cur_net) for cur_net in network.objects.exclude(
                        pk=boot_net.pk
                    ).filter(
                        Q(net_ip__netdevice__device=my_c.effective_device) &
                        Q(network_type__identifier__in=["s", "p", "o"])
                    ).distinct()
                ]
            )
            add_nets = sum([[_sub_net for _value, _sub_net in add_nets if _value == _t_val] for _t_val in ["p", "s", "o"]], [])
            dhcpd_c = [
                "ddns-update-style none;",
                "omapi-port 7911;",
                "ddns-domainname \"%s\";" % (global_config["SERVER_SHORT_NAME"]),
                "allow booting;\nallow bootp;",
                ""
            ]
            if cur_inst.srv_com["server_key:authoritative"].text.lower() in ["1", "true", "yes"]:
                dhcpd_c.extend([
                    "authoritative;",
                    "",
                ])
            # get gateway and domain-servers for the various nets
            gw_pri, gateway = (-10000, "0.0.0.0")
            cur_dc = config_tools.device_with_config("%server%")
            found_dict = {}
            for act_net in [boot_net] + add_nets:
                if act_net.gw_pri > gw_pri:
                    gw_pri, gateway = (act_net.gw_pri, act_net.gateway)
                for key, configs, _add_dict in [
                    ("domain-name-servers", ["name_server", "name_slave"], {}),
                    ("ntp-servers", ["xntp_server"], {}),
                    ("nis-servers", ["yp_server"], {"domainname" : "nis-domain"})
                ]:
                    found_confs = set(cur_dc.keys()) & set(configs)
                    if found_confs:
                        # some configs found
                        for found_conf in found_confs:
                            for cur_srv in cur_dc[found_conf]:
                                match_list = [cur_ip for cur_ip in cur_srv.ip_list if cur_ip.network.pk == act_net.pk]
                                if match_list:
                                    found_dict.setdefault(act_net.pk, {}).setdefault(key, []).append((cur_srv.device, match_list))
            dhcpd_c.extend([
                "shared-network %s {" % (global_config["SERVER_SHORT_NAME"]),
                "    option routers %s;" % (gateway)
                ])
            for act_net in [boot_net] + add_nets:
                comment_sign = "" if act_net.network_type.identifier == "b" else "#"
                dhcpd_c.extend([
                    "",
                    "    # network {} (identifier {})".format(unicode(act_net), act_net.network_type.identifier),
                    "",
                    "    {}subnet {} netmask {} {{".format(
                        comment_sign,
                        act_net.network,
                        act_net.netmask)
                ])
                if act_net.network_type.identifier == "b":
                    dhcpd_c.append("        {}authoritative;".format(comment_sign))
                dhcpd_c.append("    {}    next-server {};".format(
                    comment_sign,
                    my_c.identifier_ip_lut[act_net.network_type.identifier][0].ip))
                local_found_dict = found_dict.get(act_net.pk, {})
                for key in ["domain-name-servers", "ntp-servers", "nis-servers"]:
                    if key in local_found_dict:
                        dhcpd_c.append(
                            "    {}    option {} {};".format(
                                comment_sign,
                                key,
                                ", ".join(["{}".format(cur_dev.name) for cur_dev, _ip_list in local_found_dict[key]])
                            )
                        )
                dhcpd_c.extend([
                    "    {}    server-identifier {};".format(
                        comment_sign,
                        my_c.identifier_ip_lut[act_net.network_type.identifier][0].ip),
                    "    {}    option domain-name \"{}\";".format(
                        comment_sign,
                        act_net.name),
                    "    {}}}".format(
                        comment_sign
                        )
                    ])
            dhcpd_c.extend([
                "}",
                "",
            ])
            if os.path.isdir("/etc/dhp3"):
                file("/etc/dhcp3/dhcpd.conf", "w").write("\n".join(dhcpd_c))
            else:
                file("/etc/dhcpd.conf", "w").write("\n".join(dhcpd_c))
            ret_state = None
            for s_name in ["dhcp3-server", "dhcpd"]:
                if os.path.isfile("/etc/init.d/%s" % (s_name)):
                    cstat, log_f = process_tools.submit_at_command("/etc/init.d/%s restart" % (s_name), 1)
                    for log_line in log_f:
                        self.log(log_line)
                    if cstat:
                        ret_state, ret_str = (
                            server_command.SRV_REPLY_STATE_ERROR,
                            "error wrote dhcpd-config, unable to submit at-command (%d, please check logs)" % (cstat))
                    else:
                        ret_state, ret_str = (
                            server_command.SRV_REPLY_STATE_OK,
                            "ok wrote dhcpd-config and successfully submitted configuration")
            if ret_state is None:
                ret_state, ret_str = (
                    server_command.SRV_REPLY_STATE_ERROR,
                    "error no valid dhcp-server found (packages like dhcp-server missing ?)")
            cur_inst.srv_com.set_result(
                ret_str,
                ret_state,
            )
