# Copyright (C) 2008-2015 Andreas Lang-Nevyjel, init.at
#
# this file is part of md-config-server
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
""" openvpn special """

from initat.cluster.backbone.models import monitoring_hint, SpecialGroupsEnum
from initat.md_config_server.special_commands.base import SpecialBase


class special_openvpn(SpecialBase):
    class Meta:
        server_contact = True
        info = "OpenVPN check"
        group = SpecialGroupsEnum.system
        command_line = "$USER2$ -m $HOSTADDRESS$ openvpn_status -i $ARG1$ -p $ARG2$"
        description = "checks for running OpenVPN instances"

    def to_hint(self, srv_reply):
        _hints = []
        if "openvpn_instances" in srv_reply:
            ovpn_dict = srv_reply["openvpn_instances"]
            for inst_name in ovpn_dict:
                if ovpn_dict[inst_name]["type"] == "server":
                    for c_name in ovpn_dict[inst_name]["dict"]:
                        _hints.append(
                            monitoring_hint(
                                key="{}|{}".format(inst_name, c_name),
                                v_type="s",
                                value_string="used",
                                info="Client {} on instance {}".format(c_name, inst_name),
                                persistent=True,
                            )
                        )
        return _hints

    def _call(self):
        sc_array = []
        # no expected_dict found, try to get the actual config from the server
        hint_list = self.collrelay("openvpn_status")
        ip_dict = {}
        for hint in hint_list:
            if hint.enabled:
                inst_name, peer_name = hint.key.split("|")
                ip_dict.setdefault(inst_name, []).append(peer_name)
                sc_array.append(
                    self.get_arg_template(
                        hint.info,
                        arg1=inst_name,
                        arg2=peer_name
                    )
                )
        for inst_name in sorted(ip_dict.keys()):
            _clients = ip_dict[inst_name]
            if len(_clients) > 1:
                sc_array.append(
                    self.get_arg_template(
                        "OpenVPN clients for {} ({:d})".format(inst_name, len(_clients)),
                        arg1=inst_name,
                        arg2=",".join(_clients),
                    )
                )
        if not sc_array:
            sc_array.append(self.get_arg_template("OpenVPN", arg1="ALL", arg2="ALL"))
        return sc_array
