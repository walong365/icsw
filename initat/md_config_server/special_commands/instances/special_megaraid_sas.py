# Copyright (C) 2015 Andreas Lang-Nevyjel, init.at
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
""" special config for MegaRaid SAS modules """

from argparse import Namespace

from initat.cluster.backbone.models import monitoring_hint, device_variable
from initat.md_config_server.special_commands.base import SpecialBase
from initat.md_config_server.icinga_log_reader.log_reader import host_service_id_util
from initat.host_monitoring.modules.raidcontrollers.all import AllRAIDCtrl


# private var to store setting
PV_NAME = "__megaraid_sas_output_flag"
SHORT_OUTPUT_NAME = "MEGARAID_SAS_SHORT_OUTPUT"
IGNORE_BBU_NAME = "MEGARAID_SAS_IGNORE_MISSING_BBU"


class special_megaraid_sas(SpecialBase):
    class Meta:
        retries = 2
        server_contact = True
        info = "MegaRaid SAS"
        command_line = "$USER2$ -m $HOSTADDRESS$ megaraid_sas_status --key $ARG1$ --check $ARG2$ " \
            "--passive-check-postfix $ARG3$ --short-output ${{ARG4:{}:0}} --ignore-missing-bbu ${{ARG5:{}:0}".format(
                SHORT_OUTPUT_NAME,
                IGNORE_BBU_NAME,
            )
        description = "detailed checks for MegaRaid SAS controllers"

    def RCClass(self):
        return AllRAIDCtrl.ctrl_class("megaraid_sas")

    def to_hint(self, srv_reply):
        _prev_output = self.host.dev_variables.get(PV_NAME, -1)
        _short_output = self.host.dev_variables.get(SHORT_OUTPUT_NAME, 0)
        _ignore_missing_bbu = self.host.dev_variables.get(IGNORE_BBU_NAME, 0)
        if _prev_output != _short_output:
            self.remove_cache_entries()
        if PV_NAME not in self.host.dev_variables:
            new_var = device_variable(
                is_public=False,
                name=PV_NAME,
                local_copy_ok=False,
                var_type="i",
                # init value
                val_int=-1,
            )
            self.add_variable(new_var)
        self.set_variable(PV_NAME, _short_output)
        cur_ns = Namespace(get_hints=True, short_output=_short_output, ignore_missing_bbu=_ignore_missing_bbu)
        # transform from srv_reply to dict, see code in raidcontroller_mod (megaraid_sas_status_command.interpret)
        ctrl_dict = {}
        for res in srv_reply["result"]:
            ctrl_dict[int(res.tag.split("}")[1].split("_")[-1])] = srv_reply._interpret_el(res)
        _res = self.RCClass()._interpret(ctrl_dict, cur_ns)
        return [self._transform_to_hint(entry) for entry in _res]

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

    def _call(self):
        # print self.host, self.s_check
        _passive_check_postfix = host_service_id_util.create_host_service_description(self.host.pk, self.parent_check, "")
        hints = self.collrelay(
            "megaraid_sas_status",
        )
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
                    arg3=_passive_check_postfix if _trigger_passive else "-",
                    check_active=hint.is_active,
                )
            )
        return sc_array
