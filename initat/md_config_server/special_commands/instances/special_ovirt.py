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
from initat.host_monitoring.modules import ovirt_mod
from initat.tools import process_tools

OVIRT_USER_NAME = "OVIRT_USER_NAME"
OVIRT_PASSWORD = "OVRT_PASSWORD"


class special_ovirt_domains(SpecialBase):
    class Meta:
        server_contact = True
        info = "ovirt Virtual Machines (Virtualisation)"
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
        VALID_STATES = {"up", "down"}
        if srv_reply is not None:
            # print srv_reply.pretty_print()
            info_dict = {key: 0 for key in VALID_STATES}
            info_dict["run_ids"] = []
            info_dict["run_names"] = []
            if "vms" in srv_reply:
                for vm in srv_reply.xpath(".//ns:vms")[0]:
                    _xml = etree.fromstring(process_tools.decompress_struct(vm.text))
                    _state = _xml.xpath(".//status/state/text()")[0]
                    if _state in VALID_STATES:
                        info_dict[_state] += 1
                    if _state == "up":
                        _dom_id = _xml.get("id")
                        _dom_name = _xml.findtext("name")
                        info_dict["run_ids"].append(_dom_id)
                        info_dict["run_names"].append(_dom_name)
                        _hints.append(
                            monitoring_hint(
                                key="domain_{}".format(_dom_id),
                                v_type="s",
                                info="ovirt Domain {}".format(_dom_name),
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
                    value_blob=process_tools.compress_struct(info_dict),
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
            sc_array.append(
                self.get_arg_template(
                    hint.info,
                    arg1=self.host.valid_ip.ip,
                    arg2=_user_name,
                    arg3=_password,
                    arg4=_passive_check_prefix if _trigger_passive else "-",
                    arg5=hint.value_blob if hint.is_active else "",
                    check_active=hint.is_active,
                )
            )
        return sc_array


class special_ovirt_storage_domains(SpecialBase):
    class Meta:
        server_contact = True
        info = "ovirt Storage domains (Virtualisation)"
        group = SpecialGroupsEnum.system
        command_line = "$USER2$ -m 127.0.0.1 ovirt_storagedomains --address $ARG1$ " \
            "--username ${{ARG2:{}:notset}} --password ${{ARG3:{}:notset}}".format(
                OVIRT_USER_NAME,
                OVIRT_PASSWORD,
            ) + \
            " --passive-check-prefix $ARG4$ --reference $ARG5$"
        description = "checks storage domains via API-calls to the engine"

    def to_hint(self, srv_reply):
        _hints = []
        VALID_STATES = {"up", "down"}
        if srv_reply is not None:
            # print srv_reply.pretty_print()
            info_dict = {
                "run_ids": [],
                "run_names": [],
            }
            doms = ovirt_mod.StorageDomain.deserialize(srv_reply)
            for sd in doms:
                _dom_id = sd.get("id")
                _dom_name = sd.findtext("name")
                info_dict["run_ids"].append(_dom_id)
                info_dict["run_names"].append(_dom_name)
                _hints.append(
                    monitoring_hint(
                        key="storage_domain_{}".format(_dom_id),
                        v_type="s",
                        info="ovirt StorageDomain {}".format(_dom_name),
                        value_string=_dom_name,
                        persistent=True,
                        is_active=False,
                    )
                )
            _hints.append(
                monitoring_hint(
                    key="overview",
                    v_type="B",
                    info="StorageDomain overview",
                    persistent=True,
                    value_blob=process_tools.compress_struct(info_dict),
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
            "ovirt_storagedomains",
            "--address={}".format(self.host.valid_ip.ip),
            "--username={}".format(_user_name),
            "--password={}".format(_password),
            connect_to_localhost=True,
        ):
            _trigger_passive = hint.key.startswith("overview")
            sc_array.append(
                self.get_arg_template(
                    hint.info,
                    arg1=self.host.valid_ip.ip,
                    arg2=_user_name,
                    arg3=_password,
                    arg4=_passive_check_prefix if _trigger_passive else "-",
                    arg5=hint.value_blob if hint.is_active else "",
                    check_active=hint.is_active,
                )
            )
        return sc_array
