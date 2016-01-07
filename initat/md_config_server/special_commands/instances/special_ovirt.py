# Copyright (C) 2008-2016 Andreas Lang-Nevyjel, init.at
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
""" special ovirt call """

from lxml import etree

from initat.cluster.backbone.models import monitoring_hint, SpecialGroupsEnum
from initat.md_config_server.icinga_log_reader.log_reader import host_service_id_util
from initat.md_config_server.special_commands.base import SpecialBase
from initat.tools import process_tools

OVIRT_USER_NAME = "OVIRT_USER_NAME"
OVIRT_PASSWORD = "OVRT_PASSWORD"


class special_ovirt(SpecialBase):
    class Meta:
        server_contact = True
        info = "ovirt (Virtualisation)"
        group = SpecialGroupsEnum.system
        command_line = "$USER2$ -m 127.0.0.1 ovirt_overview --address $ARG1$ " \
            "--username ${{ARG2:{}:notset}} --password ${{ARG3:{}:notset}}".format(
                OVIRT_USER_NAME,
                OVIRT_PASSWORD,
            ) + \
            " --passive-check-prefix $ARG4$ --reference $ARG5$"
        description = "checks running virtual machines via API-calls to the engine"

    def to_hint(self, srv_reply):
        _hints = []
        if srv_reply is not None:
            # print srv_reply.pretty_print()
            num_states = {key: 0 for key in ["up", "down"]}
            if "vms" in srv_reply:
                for vm in srv_reply.xpath(".//ns:vms")[0]:
                    _xml = etree.fromstring(process_tools.decompress_struct(vm.text))
                    _state = _xml.xpath(".//status/state/text()")[0]
                    if _state in num_states:
                        num_states[_state] += 1
                    if _state == "up":
                        _dom_name = _xml.findtext("name")
                        _hints.append(
                            monitoring_hint(
                                key="domain_{}".format(_xml.get("id")),
                                v_type="s",
                                info="domain {}".format(_dom_name),
                                value_string=_dom_name,
                                persistent=True,
                                is_active=False,
                            )
                        )
            _hints.append(
                monitoring_hint(
                    key="overview",
                    v_type="B",
                    info="Domain overview",
                    persistent=True,
                    value_blob=process_tools.compress_struct(num_states),
                    is_active=True,
                )
            )
        return _hints

    def _call(self):
        _passive_check_prefix = host_service_id_util.create_host_service_description(self.host.pk, self.parent_check, "")
        _user_name = self.host.dev_variables.get(OVIRT_USER_NAME, "notset")
        _password = self.host.dev_variables.get(OVIRT_PASSWORD, "notset")
        sc_array = []
        for hint in self.collrelay(
            "ovirt_overview",
            "--address={}".format(self.host.valid_ip.ip),
            "--username={}".format(_user_name),
            "--password={}".format(_password),
            connect_to_localhost=True,
        ):
            _trigger_passive = hint.key.startswith("overview")
            print "****", hint
            sc_array.append(
                self.get_arg_template(
                    hint.info,
                    arg1=self.host.valid_ip.ip,
                    arg2=_user_name,
                    arg3=_password,
                    arg4=_passive_check_prefix if _trigger_passive else "-",
                    arg5=hint.value_string if hint.is_active else "",
                    check_active=hint.is_active,
                )
            )
        return sc_array
