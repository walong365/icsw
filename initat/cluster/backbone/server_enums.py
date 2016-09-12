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

__all__ = [
    "icswAppEnum"
]


# this gets initialised as soon as this module is imported so import this onyl
# whne you need this object

icswAppEnum = None


def init_app_enum():
    global icswAppEnum
    if icswAppEnum is None:
        from django.conf import settings
        _all = []
        for _enum in settings.ICSW_CONFIG_ENUM_LIST:
            for entry in _enum:
                _all.append((entry.name, entry.value))
        icswAppEnum = Enum(value="icswServerEnum", names=_all)

init_app_enum()
