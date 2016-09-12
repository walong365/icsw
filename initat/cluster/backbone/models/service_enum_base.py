# Copyright (C) 2016 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw-server
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
# -*- coding: utf-8 -*-
#
""" serviceEnum Base for 'global' configenum object, for servers """

from initat.host_monitoring.service_enum_base import icswServiceEnumBaseClient

__all__ = [
    "icswServiceEnumBase"
]


class icswServiceEnumBase(icswServiceEnumBaseClient):
    def __init__(self, name, info="N/A", root_service=True):
        icswServiceEnumBaseClient.__init__(self, name, info, root_service)
        self.client_service = False
        self.server_service = True
