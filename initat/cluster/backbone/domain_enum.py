# Copyright (C) 2016 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw-server
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
# -*- coding: utf-8 -*-
#
""" enums for domains """

from __future__ import unicode_literals, print_function

from enum import Enum

from initat.cluster.backbone.server_enums import icswServiceEnum


class icswDomainEnumType(object):
    def __init__(self, name, info, default_enum, domain_enum):
        self.name = name
        self.info = info
        self.default_enum = default_enum
        self.domain_enum = domain_enum


class icswDomainEnum(Enum):
    boot = icswDomainEnumType(
        "mother",
        "Node boot service",
        icswServiceEnum.monitor_server,
        icswServiceEnum.monitor_slave,
    )
    monitor = icswDomainEnumType(
        "monitor",
        "Monitor devices",
        None,
        icswServiceEnum.mother_server,
    )
