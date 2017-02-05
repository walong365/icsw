# Copyright (C) 2015-2017 Andreas Lang-Nevyjel, init.at
#
# this file is part of md-config-server
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
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
""" special config for MegaRaid SAS modules """

from argparse import Namespace

from initat.cluster.backbone.models import monitoring_hint, SpecialGroupsEnum
from initat.host_monitoring.modules.raidcontrollers.all import AllRAIDCtrl
from initat.md_config_server.icinga_log_reader.log_reader import HostServiceIDUtil
from initat.md_config_server.special_commands.base import SpecialBase
from ..struct import DynamicCheckServer, DynamicCheckAction

SHORT_OUTPUT_NAME = "MEGARAID_SAS_SHORT_OUTPUT"
IGNORE_BBU_NAME = "MEGARAID_SAS_IGNORE_MISSING_BBU"
IGNORE_KEYS_NAME = "MEGARAID_SAS_IGNORE_KEYS"


class SpecialMegaraidSas(SpecialBase):
    class Meta:
        retries = 2
        server_contact = True
        group = SpecialGroupsEnum.hardware_disc
        info = "MegaRaid SAS"
        command_line = "$USER2$ -m $HOSTADDRESS$ megaraid_sas_status --key $ARG1$ --check $ARG2$ " \
            "--passive-check-prefix $ARG3$ --short-output ${{ARG4:{}:0}} --ignore-missing-bbu ${{ARG5:{}:0}} " \
            "--ignore-keys ${{ARG6:{}:N}}".format(
                SHORT_OUTPUT_NAME,
                IGNORE_BBU_NAME,
                IGNORE_KEYS_NAME,
            )
        description = "detailed checks for MegaRaid SAS controllers"
        uuid = "df821c8e-aba9-4def-bc32-5a5b01720f56"

    def dynamic_update_calls(self):
        yield DynamicCheckAction(DynamicCheckServer.collrelay, "megaraid_sas_status")

    def feed_result(self, dc_action, srv_reply):
        _short_output = self.host.dev_variables.get(SHORT_OUTPUT_NAME, 0)
        _ignore_missing_bbu = self.host.dev_variables.get(IGNORE_BBU_NAME, 0)
        _ignore_keys = self.host.dev_variables.get(IGNORE_KEYS_NAME, "N")
        cur_ns = Namespace(
            get_hints=True,
            short_output=_short_output,
            ignore_missing_bbu=_ignore_missing_bbu,
            ignore_keys=_ignore_keys
        )
        # transform from srv_reply to dict, see code in raidcontroller_mod (megaraid_sas_status_command.interpret)
        ctrl_dict = {}
        for res in srv_reply["result"]:
            ctrl_dict[int(res.tag.split("}")[1].split("_")[-1])] = srv_reply._interpret_el(res)
        # import pprint
        # pprint.pprint(ctrl_dict)
        _res = self.RCClass()._interpret(ctrl_dict, cur_ns)
        self.store_hints([self._transform_to_hint(entry) for entry in _res])
        yield None

    def _transform_to_hint(self, entry):
        key, check, info, _active = entry
        return monitoring_hint(
            key=key,
            v_type="s",
            value_string=check,
            info=info,
            persistent=True,
            is_active=_active,
        )

    def RCClass(self):
        return AllRAIDCtrl.ctrl_class("megaraid_sas")

    def call(self):
        # print self.host, self.s_check
        _passive_check_prefix = HostServiceIDUtil.create_host_service_description(self.host.pk, self.parent_check, "")
        hints = self.hint_list
        if not hints:
            hints = [self._transform_to_hint(entry) for entry in self.RCClass()._dummy_hints()]
        sc_array = []
        for hint in hints:
            _trigger_passive = hint.value_string == "all"
            sc_array.append(
                self.get_arg_template(
                    hint.info,
                    arg1=hint.key,
                    arg2=hint.value_string,
                    arg3=_passive_check_prefix if _trigger_passive else "-",
                    check_active=hint.is_active,
                )
            )
        return sc_array
