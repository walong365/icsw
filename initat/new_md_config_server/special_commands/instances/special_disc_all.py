# Copyright (C) 2008-2015 Andreas Lang-Nevyjel, init.at
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
""" special check for all disks """

from initat.cluster.backbone.models import SpecialGroupsEnum
from initat.md_config_server.special_commands.base import SpecialBase


class special_disc_all(SpecialBase):
    class Meta:
        info = "report fullest disc"
        group = SpecialGroupsEnum.system_disc
        command_line = "$USER2$ -m $HOSTADDRESS$ df -w ${ARG1:85} -c ${ARG2:95} $ARG3$"
        description = "queries the collserver on the target system for the partition with the lowest space"

    def _call(self):
        sc_array = [self.get_arg_template("All partitions", arg3="ALL")]
        return sc_array
