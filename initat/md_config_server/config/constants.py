# Copyright (C) 2008-2017 Andreas Lang-Nevyjel, init.at
#
# this file is part of icsw-server
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
""" constants for md-config-server """

from enum import Enum

__all__ = [
    "MON_VAR_IP_NAME",
    "SpecialTypesEnum",
]

MON_VAR_IP_NAME = "__$$ICSW$$__MON_VAR_IP"


class SpecialTypesEnum(Enum):
    mon_host_cluster = "hc"
    mon_service_cluster = "sc"
    mon_host_dependency = "hd"
    mon_service_dependency = "sd"
