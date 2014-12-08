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
""" IPMI special """

from django.db.models import Q
from initat.cluster.backbone.models import monitoring_hint
from initat.md_config_server.special_commands.base import special_base


class special_ipmi(special_base):
    class Meta:
        server_contact = True
        info = "IPMI checks via collserver"
        command_line = "$USER2$ -m $HOSTADDRESS$ ipmi_sensor --lowern=${ARG1:na} --lowerc=${ARG2:na} " \
            "--lowerw=${ARG3:na} --upperw=${ARG4:na} --upperc=${ARG5:na} --uppern=${ARG6:na} $ARG7$"
        description = "queries the IPMI sensors of the underlying IPMI interface of the target device"

    def to_hint(self, srv_reply):
        _hints = []
        if srv_reply is not None:
            if "list:sensor_list" in srv_reply:
                for sensor in srv_reply["list:sensor_list"]:
                    lim_dict = {l_key: sensor.attrib[key] for l_key, key in [
                        ("lower_warn", "limit_lw"),
                        ("lower_crit", "limit_lc"),
                        ("upper_warn", "limit_uw"),
                        ("upper_crit", "limit_uc")] if key in sensor.attrib}
                    new_hint = monitoring_hint(
                        key=sensor.attrib["key"],
                        v_type="f",
                        info=sensor.attrib["info"],
                    )
                    new_hint.update_limits(0.0, lim_dict)
                    _hints.append(new_hint)
        return _hints

    def _call(self):
        sc_array = []
        for hint in self.collrelay("ipmi_sensor"):
            sc_array.append(
                self.get_arg_template(
                    hint.info,
                    arg1="na",
                    arg2=hint.get_limit("lower_crit", "na", ignore_zero=True),
                    arg3=hint.get_limit("lower_warn", "na", ignore_zero=True),
                    arg4=hint.get_limit("upper_warn", "na", ignore_zero=True),
                    arg5=hint.get_limit("upper_crit", "na", ignore_zero=True),
                    arg6="na",
                    arg7=hint.key,
                )
            )
        return sc_array
