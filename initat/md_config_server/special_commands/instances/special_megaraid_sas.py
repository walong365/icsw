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

from django.db.models import Q
from initat.cluster.backbone.models import monitoring_hint
from initat.md_config_server.special_commands.base import SpecialBase
from initat.md_config_server.icinga_log_reader.log_reader import host_service_id_util
from initat.host_monitoring.modules import raidcontroller_mod
from argparse import Namespace
from lxml.builder import E  # @UnresolvedImport @UnusedImport
import logging_tools


class special_megaraid_sas(SpecialBase):
    class Meta:
        retries = 2
        server_contact = True
        info = "MegaRaid SAS"
        command_line = "$USER2$ -m $HOSTADDRESS$ megaraid_sas_status --key $ARG1$ --check $ARG2$ --passive-check-postfix $ARG3$"
        description = "detailed checks for MegaRaid SAS controllers"

    def RCClass(self):
        return raidcontroller_mod.ctrl_type.ctrl_class("megaraid_sas")

    def to_hint(self, srv_reply):
        cur_ns = Namespace(get_hints=True)
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
            hints = [self._transform_to_hint(entry) for entry in self.RCClass()._dummy_hint()]
        sc_array = []
        for hint in hints:
            _trigger_passive = hint.key == "all" and hint.value_string == "all"
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
