# -*- coding: utf-8 -*-
#
# Copyright (C) 2001-2017 Andreas Lang-Nevyjel, init.at
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
""" native modules, dummy file to create json """

from initat.constants import PlatformSystemTypeEnum
from .. import hm_classes
from ..constants import HMAccessClassEnum, DynamicCheckServer, HMIPProtocolEnum


class ModuleDefinition(hm_classes.MonitoringModule):
    class Meta:
        required_platform = PlatformSystemTypeEnum.LINUX
        required_access = HMAccessClassEnum.level0
        uuid = "a3f0e9e6-432e-4dd1-9ff7-ed655755fa94"


class check_http_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        check_instance = DynamicCheckServer.native
        required_access = HMAccessClassEnum.level0
        uuid = "fafb5e5d-961c-4aef-ac3c-2f8a87261016"
        description = "check http server on target host"
        parameters = hm_classes.MCParameters(
            hm_classes.MCParameter(
                "-I",
                "ip_address",
                "",
                "IP Address or name",
                macro_name="$HOSTADDRESS$"
            ),
            hm_classes.MCParameter(
                "-p",
                "port",
                80,
                "Port to connect to",
                devvar_name="HTTP_CHECK_PORT",
            ),
        )
        ports = hm_classes.MCPortList(
            hm_classes.MCPort(HMIPProtocolEnum.tcp, 80),
            hm_classes.MCPort(HMIPProtocolEnum.tcp, 443),
        )
