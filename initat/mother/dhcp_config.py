# Copyright (C) 2007-2008,2012-2015 Andreas Lang-Nevyjel
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

import os
import time

from django.db.models import Q
from initat.cluster.backbone.models import network
from initat.tools import config_tools, logging_tools

from .config import global_config


class DHCPNetwork(object):
    def __init__(self, act_net):
        self.content = []
        self._generate(act_net)

    @staticmethod
    def setup(server_check, addon_dict):
        DHCPNetwork.server_check = server_check
        DHCPConfigMixin.addon_dict = addon_dict

    def _feed(self, lines):
        if type(lines) != list:
            lines = [lines]
        self.content.extend(lines)

    def comment_content(self):
        # add comment sign to content
        _new_c = []
        for _line in self.content:
            if _line.strip().startswith("#"):
                pass
            else:
                _line = "    # {}".format(_line[4:])
            _new_c.append(_line)
        self.content = _new_c

    def _generate(self, act_net):
        self._feed(
            [
                "",
                "    # network {} (identifier {})".format(unicode(act_net), act_net.network_type.identifier),
                "",
                "    subnet {} netmask {} {{".format(
                    act_net.network,
                    act_net.netmask,
                )
            ]
        )
        if act_net.network_type.identifier == "b":
            self._feed("        authoritative;")
        # check for ip in actual net
        _srv_ip = [
            _entry for _entry in DHCPNetwork.server_check.identifier_ip_lut[act_net.network_type.identifier] if _entry.network_id == act_net.pk
        ][0]
        self._feed(
            "        next-server {};".format(
                _srv_ip.ip,
            )
        )
        local_found_dict = DHCPConfigMixin.addon_dict.get(act_net.pk, {})
        for key in ["domain-name-servers", "ntp-servers", "nis-servers"]:
            if key in local_found_dict:
                self._feed(
                    "        option {} {};".format(
                        key,
                        ", ".join(
                            [
                                "{}".format(cur_dev.name) for cur_dev, _ip_list in local_found_dict[key]
                            ]
                        )
                    )
                )
        self._feed(
            [
                "        server-identifier {};".format(
                    _srv_ip.ip
                ),
                "        option domain-name \"{}\";".format(
                    act_net.name
                ),
                "    }",
            ]
        )


class DHCPConfigMixin(object):
    def write_dhcp_config(self):
        if not global_config["WRITE_DHCP_CONFIG"]:
            self.log("altering the DHCP-config disabled", logging_tools.LOG_LEVEL_WARN)
            return

        is_authoritative = global_config["DHCP_AUTHORITATIVE"]
        self.log("writing dhcp-config, {}".format("auth" if is_authoritative else "not auth"))

        my_c = config_tools.server_check(server_type="mother_server")
        boot_ips = my_c.identifier_ip_lut.get("b", [])
        if not boot_ips:
            self.log(
                "error no boot-net found",
                logging_tools.LOG_LEVEL_ERROR,
            )
        else:
            add_nets = list(
                [
                    (
                        cur_net.network_type.identifier, cur_net
                    ) for cur_net in network.objects.exclude(
                        pk__in=[boot_ip.network.pk for boot_ip in boot_ips]
                    ).filter(
                        Q(net_ip__netdevice__device=my_c.effective_device) &
                        Q(network_type__identifier__in=["s", "p", "o"])
                    ).distinct()
                ]
            )
            add_nets = sum(
                [
                    [
                        _sub_net for _value, _sub_net in add_nets if _value == _t_val
                    ] for _t_val in ["p", "s", "o"]
                ],
                []
            )
            dhcpd_c = [
                "",
                "# created from mother on {}".format(time.ctime(time.time())),
                "",
                "ddns-update-style none;",
                "omapi-port 7911;",
                "ddns-domainname \"{}\";".format(global_config["SERVER_SHORT_NAME"]),
                "allow booting;\nallow bootp;",
                "",
                "option space PXE;",
                "option PXE.mtftp-ip    code 1 = ip-address;",
                "option PXE.mtftp-cport code 2 = unsigned integer 16;",
                "option PXE.mtftp-tmout code 4 = unsigned integer 8;",
                "option PXE.mtftp-delay code 5 = unsigned integer 8;",
                "option arch code 93 = unsigned integer 16;",
                "",
            ]
            if is_authoritative:
                dhcpd_c.extend(
                    [
                        "authoritative;",
                        "",
                    ]
                )
            # get gateway and domain-servers for the various nets
            gw_pri, gateway = (-10000, "0.0.0.0")
            cur_dc = config_tools.device_with_config("%server%")
            found_dict = {}
            for act_net in [boot_ip.network for boot_ip in boot_ips] + add_nets:
                if act_net.gw_pri > gw_pri:
                    gw_pri, gateway = (act_net.gw_pri, act_net.gateway)
                for key, configs, _add_dict in [
                    ("domain-name-servers", ["name_server", "name_slave"], {}),
                    ("ntp-servers", ["xntp_server"], {}),
                    ("nis-servers", ["yp_server"], {"domainname": "nis-domain"})
                ]:
                    found_confs = set(cur_dc.keys()) & set(configs)
                    if found_confs:
                        # some configs found
                        for found_conf in found_confs:
                            for cur_srv in cur_dc[found_conf]:
                                match_list = [cur_ip for cur_ip in cur_srv.ip_list if cur_ip.network.pk == act_net.pk]
                                if match_list:
                                    found_dict.setdefault(act_net.pk, {}).setdefault(key, []).append((cur_srv.device, match_list))
            dhcpd_c.extend(
                [
                    "shared-network {} {{".format(global_config["SERVER_SHORT_NAME"]),
                    # do not write routers (gateway may be invalid)
                    # "    option routers {};".format(gateway)
                ]
            )
            DHCPNetwork.setup(my_c, found_dict)
            for act_net in [boot_ip.network for boot_ip in boot_ips] + add_nets:
                if act_net.netmask == "0.0.0.0":
                    self.log(
                        "refuse network {} with netmask '{}'".format(
                            unicode(act_net),
                            act_net.netmask,
                        ),
                        logging_tools.LOG_LEVEL_ERROR
                    )
                else:
                    _net = DHCPNetwork(act_net)
                    if global_config["DHCP_ONLY_BOOT_NETWORKS"] and act_net.network_type.identifier != "b":
                        _net.comment_content()
                    dhcpd_c.extend(_net.content)
            dhcpd_c.extend(
                [
                    "}",
                    "",
                ]
            )
            _target_file = None
            for _tf in ["/etc/dhcp/dhcpd.conf", "/etc/dhcp3/dhcpd.conf", "/etc/dhcpd.conf"]:
                if os.path.isfile(_tf):
                    self.log("found dhcp-config in {}".format(_tf))
                    _target_file = _tf
                    break
            if not _target_file:
                self.log("no DHCP config file found", logging_tools.LOG_LEVEL_ERROR)
            else:
                file(_target_file, "w").write("\n".join(dhcpd_c))
                self.log("wrote DHCP config to {}".format(_target_file))
                for _srv_name in self.srv_helper.find_services(".*dhcpd.*"):
                    self.srv_helper.service_command(_srv_name, "restart")
