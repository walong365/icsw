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
""" init all enums and create the IcswAppEnum object """

from enum import Enum
from .models.service_enum_base import icswServiceEnumBase
from initat.host_monitoring.service_enum_base import icswServiceEnumBaseClient


__all__ = [
    "icswServiceEnum"
]


class icswAppBaseServiceEnumClass(object):
    def __init__(self, *args):
        if not isinstance(args[0], icswServiceEnumBase) and not isinstance(args[0], icswServiceEnumBaseClient):
            raise ValueError("value of serviceEnum has to be an instance of icswServiceEnumBase")


# this gets initialised as soon as this module is imported so import this onyl
# whne you need this object

icswServiceEnum = None


def init_app_enum():
    global icswServiceEnum
    from initat.cluster.backbone.models.functions import register_service_enum
    from initat.host_monitoring.client_enums import icswServiceEnum as icswServiceEnumClient
    from initat.icsw.service import instance
    register_service_enum(icswServiceEnumClient, "client")
    if icswServiceEnum is None:
        from django.conf import settings
        _all = []
        for _enum in settings.ICSW_SERVICE_ENUM_LIST:
            for entry in _enum:
                entry.value.clear_instance_names()
                _all.append((entry.name, entry.value))
        icswServiceEnum = Enum(value="icswServerEnum", names=_all, type=icswAppBaseServiceEnumClass)
    _xml = instance.InstanceXML(quiet=True)
    for _inst in _xml.get_all_instances():
        _attr = _xml.get_attrib(_inst)
        _enums = _xml.get_config_enums(_inst)
        for _enum_str in _enums:
            if _enum_str.count("-"):
                _err_str = "config-enum names in *.xml are not allowed to have dashes in there name: {}".format(
                    _enum_str,
                )
                raise SyntaxError(_err_str)
            try:
                _enum = getattr(icswServiceEnum, _enum_str)
            except AttributeError:
                print("Unknown ServerEnum '{}'".format(_enum_str))
            else:
                _enum.value.add_instance_name(_attr["name"])

init_app_enum()
