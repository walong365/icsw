# Copyright (C) 2008-2014,2016 Andreas Lang-Nevyjel, init.at
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
""" special libvirt call """

from __future__ import unicode_literals, print_function

from initat.cluster.backbone.models import monitoring_hint, SpecialGroupsEnum
from initat.md_config_server.special_commands.base import SpecialBase
from ..struct import DynamicCheckServer, DynamicCheckAction


class SpecialLibvirt(SpecialBase):
    class Meta:
        info = "libvirt (Virtualisation)"
        group = SpecialGroupsEnum.system
        command_line = "$USER2$ -m $HOSTADDRESS$ domain_status $ARG1$"
        description = "checks running virtual machines on the target host via libvirt"

    def dynamic_update_calls(self):
        yield DynamicCheckAction(DynamicCheckServer.collrelay, "domain_overview")

    def feed_result(self, dc_action, srv_reply):
        _hints = []
        # print(srv_reply.pretty_print())
        if srv_reply is not None:
            # print("domain_overview" in srv_reply)
            if "domain_overview" in srv_reply:
                domain_info = srv_reply["domain_overview"]
                # print("***", domain_info)
                if "running" in domain_info and "defined" in domain_info:
                    domain_info = domain_info["running"]
                for _d_idx, d_dict in domain_info.iteritems():
                    new_hint = monitoring_hint(
                        key=d_dict["name"],
                        v_type="s",
                        info="Domain {}".format(d_dict["name"]),
                        value_string="running",
                    )
                    _hints.append(new_hint)
        self.store_hints(_hints)
        yield None

    def call(self):
        sc_array = []
        for hint in self.hint_list:
            sc_array.append(
                self.get_arg_template(
                    hint.info,
                    arg1=hint.key,
                )
            )
        return sc_array
