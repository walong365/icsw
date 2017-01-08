# Copyright (C) 2008-2017 Andreas Lang-Nevyjel, init.at
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
""" IPMI check for collserver special """

from __future__ import unicode_literals, print_function

from django.db.models import Q

from initat.cluster.backbone.models import monitoring_hint, SpecialGroupsEnum
from initat.md_config_server.special_commands.base import SpecialBase


class SpecialIpmiExt(SpecialBase):
    class Meta:
        command_line = "/bin/true"
        is_active = False
        info = "IPMI as passive checks via collectd"
        group = SpecialGroupsEnum.hardware
        description = "queries the IPMI sensors of the IPMI interface directly (not via the target host)"
        identifier = "ipmi_passive_checks"

    def call(self):
        sc_array = []
        for ipmi_ext in monitoring_hint.all_enabled.filter(
            Q(device=self.host) & Q(m_type="ipmi")
        ):
            new_at = self.get_arg_template(
                ipmi_ext.info,
                _monitoring_hint=ipmi_ext.pk,
            )
            sc_array.append(new_at)
            if not ipmi_ext.check_created:
                ipmi_ext.check_created = True
                ipmi_ext.save(update_fields=["check_created"])
        return sc_array
