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
""" supermicro special """

from initat.cluster.backbone.models import monitoring_hint
from initat.host_monitoring.modules import supermicro_mod
from initat.md_config_server.special_commands.base import special_base
from lxml.builder import E  # @UnresolvedImport @UnusedImport


class special_supermicro(special_base):
    class Meta:
        server_contact = True
        info = "SuperMicro"
        command_line = "$USER2$ -m 127.0.0.1 smcipmi --ip=$HOSTADDRESS$ --user=${ARG1:SMC_USER:ADMIN} --passwd=${ARG2:SMC_PASSWD:ADMIN} $ARG3$"
        description = "queries IPMI Bladecenters via the collserver on the localhost"

    def to_hint(self, srv_reply):
        r_dict = supermicro_mod.generate_dict(srv_reply.xpath(".//ns:output/text()", smart_strings=False)[0].split("\n"))
        _hints = []
        for m_key in sorted(r_dict):
            _struct = r_dict[m_key]
            for e_key in sorted([_key for _key in _struct.iterkeys() if type(_key) in [int]]):
                _hints.append(
                    monitoring_hint(
                        key="{}.{:d}".format(m_key, e_key),
                        v_type="s",
                        value_string="present",
                        info="{} {:d}".format(_struct["info"], e_key),
                    )
                )
        return _hints

    def _call(self):
        user_name = self.host.dev_variables.get("SMC_USER", "ADMIN")
        cur_pwd = self.host.dev_variables.get("SMC_PASSWD", "ADMIN")
        hint_list = self.collrelay(
            "smcipmi",
            "--ip={}".format(self.host.valid_ip.ip),
            "--user={}".format(user_name),
            "--passwd={}".format(cur_pwd),
            "counter",
            connect_to_localhost=True
        )
        sc_array = []
        sc_array.append(
            self.get_arg_template(
                "Overview",
                arg1=user_name,
                arg2=cur_pwd,
                arg3="counter",
            )
        )
        for hint in hint_list:
            inst_name, inst_id = hint.key.split(".")
            sc_array.append(
                self.get_arg_template(
                    hint.info,
                    arg1=user_name,
                    arg2=cur_pwd,
                    arg3="{} {}".format(inst_name, inst_id),
                )
            )
        return sc_array
