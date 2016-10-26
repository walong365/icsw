# -*- coding: utf-8 -*-
#
# Copyright (C) 2016 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FTNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
""" creates fixtures for device classes """

from __future__ import unicode_literals, print_function

from django.conf import settings
from django.db.models import Q

from initat.cluster.backbone import factories
from initat.cluster.backbone.models import DeviceClass, device
from initat.tools import logging_tools


def add_fixtures(**kwargs):
    _class_dict = {}
    for _name, _descr, _default in [
        ("normal", "Normal devices", True),
        ("periphery", "Pheriphery devices", False),
    ]:
        _class_dict[_name] = factories.DeviceClassFactory(
            name=_name,
            description=_descr,
            system_class=True,
            default_system_class=_default,
        )
    if settings.ICSW_DEBUG:
        # debug output
        for _c in DeviceClass.objects.all():
            print(unicode(_c))

    _no_class = device.objects.filter(Q(device_class=None))
    if _no_class.count():
        _def_class = DeviceClass.objects.get(Q(system_class=True) & Q(default_system_class=True))
        print(
            "Settings DeviceClass for {} to {}".format(
                logging_tools.get_plural("device", _no_class.count()),
                unicode(_def_class),
            )
        )
        for _dev in _no_class:
            _dev.device_class = _def_class
            _dev.save(update_fields=["device_class"])
