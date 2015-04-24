# Copyright (C) 2008-2014 Andreas Lang-Nevyjel, init.at
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
""" special tasks for md-config-server, should be split into submodules, FIXME """

from django.db.models import Q
from initat.cluster.backbone.models import monitoring_hint
from initat.md_config_server.special_commands.base import SpecialBase
from lxml.builder import E  # @UnresolvedImport @UnusedImport
from initat.tools import logging_tools


class special_eonstor(SpecialBase):
    class Meta:
        retries = 2
        server_contact = True
        info = "Eonstor checks"
        command_line = "$USER3$ -m $HOSTADDRESS$ -C ${ARG1:SNMP_COMMUNITY:public} -V ${ARG2:SNMP_VERSION:2} $ARG3$ $ARG4$"
        description = "checks the eonstore disc chassis via SNMP"

    def to_hint(self, srv_reply):
        _hints = []
        if srv_reply is not None:
            if self.call_idx == 0:
                if "eonstor_info" in srv_reply:
                    info_dict = srv_reply["eonstor_info"]
                    self.info_dict = info_dict
                    # disks
                    for disk_id in sorted(info_dict.get("disc_ids", [])):
                        _hints.append(self._get_env_check("Disc {:2d}".format(disk_id), "eonstor_disc_info", disk_id))
                    # lds
                    for ld_id in sorted(info_dict.get("ld_ids", [])):
                        _hints.append(self._get_env_check("Logical Drive {:2d}".format(ld_id), "eonstor_ld_info", ld_id))
                    # env_dicts
                    for env_dict_name in sorted(info_dict.get("ent_dict", {}).keys()):
                        if env_dict_name not in ["ups", "bbu"]:
                            env_dict = info_dict["ent_dict"][env_dict_name]
                            for idx in sorted(env_dict.keys()):
                                _hints.append(self._get_env_check(env_dict[idx], "eonstor_{}_info".format(env_dict_name), idx))
            else:
                if "eonstor_info:state" in srv_reply:
                    _com = srv_reply["*command"]
                    act_state = int(srv_reply["eonstor_info:state"].text)
                    self.log(
                        "state for {} ({}) is {:d}".format(
                            _com,
                            srv_reply["*arg_list"],
                            act_state
                        )
                    )
                    idx = int(srv_reply["*arg_list"])
                    env_dict_name = _com.split("_")[1]
                    if env_dict_name == "ups" and act_state & 128:
                        self.log(
                            "disabling psu because not present",
                            logging_tools.LOG_LEVEL_ERROR
                        )
                    elif env_dict_name == " bbu" and act_state & 128:
                        self.log(
                            "disabling bbu because not present",
                            logging_tools.LOG_LEVEL_ERROR
                        )
                    else:
                        _hints.append(
                            self._get_env_check(
                                self.info_dict["ent_dict"][env_dict_name][idx],
                                "eonstor_{}_info".format(env_dict_name),
                                idx
                            )
                        )
        return _hints

    def _get_env_check(self, info, key, idx):
        return monitoring_hint(
            key=key,
            v_type="i",
            value_int=idx,
            info=info,
        )

    def _call(self):
        self.info_dict = {}
        hints = self.snmprelay(
            "eonstor_get_counter",
        )
        if self.info_dict:
            info_dict = self.info_dict
            for env_dict_name in sorted([_entry for _entry in info_dict.get("ent_dict", {}) if _entry in ["ups", "bbu"]]):
                env_dict = info_dict["ent_dict"][env_dict_name]
                for idx in sorted(env_dict.keys()):
                    hints.extend(
                        self.snmprelay(
                            "eonstor_{}_info".format(env_dict_name),
                            "{:d}".format(idx)
                        )
                    )
        sc_array = []
        for hint in hints:
            sc_array.append(
                self.get_arg_template(
                    hint.info,
                    arg1=self.host.dev_variables["SNMP_READ_COMMUNITY"],
                    arg2=self.host.dev_variables["SNMP_VERSION"],
                    arg3=hint.key,
                    arg4="{:d}".format(hint.value_int),
                )
            )
        self.log("sc_array has {}".format(logging_tools.get_plural("entry", len(sc_array))))
        return sc_array
