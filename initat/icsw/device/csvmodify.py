#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001-2006,2013-2015 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file belongs to cluster-backbone-tools
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

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

import django
django.setup()

from django.db.models import Q
from initat.cluster.backbone.models import device, device_group
from initat.cluster.backbone.models.functions import to_system_tz
from initat.tools import logging_tools
import re
import datetime
import csv

"""
CSV example:

name,netdevice[devname=enp0s25]__macaddr
lemmy,00:11:22:33:44:55
ipmi-mc01,00:25:90:d7:8b:4b
ipmi-mc02,00:25:90:d7:8a:ff
ipmi-mc03,00:25:90:d9:5a:66
ipmi-mc04,00:25:90:d7:8b:59

"""


class SmartKey(object):
    def __init__(self, dev, key):
        self.device = dev
        self.key = key
        self.parts = self.key.split("__")
        self._resolve()

    def _resolve(self):
        self.resolved = False
        # start object
        _obj = self.device
        # copy
        _prts = [_key for _key in self.parts]
        while len(_prts) > 1 and _obj:
            _prt = _prts.pop(0)
            if _prt.count("["):
                _prt, _filter = _prt.split("[", 1)
                _filter = dict(tuple(_entry.split("=", 1)) for _entry in _filter[:-1].split(","))
            else:
                _filter = {}
            try:
                _next = getattr(_obj, _prt)
            except:
                try:
                    _next = getattr(_obj, "{}_set".format(_prt))
                except:
                    print(
                        "unresolvable '{}' for object '{}'".format(
                            _prt,
                            unicode(_obj),
                        )
                    )
                    _obj = None
                    break
                else:
                    _next = _next.filter(**_filter)
                    if len(_next) > 1:
                        print(
                            "found more than one in list {} ({:d})".format(
                                _prt,
                                len(_next),
                            )
                        )
                        _obj = None
                    else:
                        _obj = _next[0]
            else:
                _obj = _next
        if _obj:
            self.object = _obj
            self.resolved = True
            self.attr_name = _prts[0]

    def set(self, value):
        if self.resolved:
            _prev = getattr(self.object, self.attr_name)
            print(
                "changing attribute '{}' of '{}' form '{}' to '{}'".format(
                    unicode(self.attr_name),
                    unicode(self.object),
                    _prev,
                    unicode(value)
                )
            )
            setattr(self.object, self.attr_name, value)
            self.object.save(update_fields=[self.attr_name])
        else:
            print("SmartKey had resolve error(s)")


def main(opt_ns):
    with open(opt_ns.file) as csv_file:
        reader = csv.DictReader(csv_file)
        for _ld in reader:
            if "name" not in _ld:
                print("Need name in line_dict (found: {})".format(", ".join(_ld.keys())))
            else:
                _name = _ld.pop("name")
                try:
                    _dev = device.objects.get(Q(name=_name))
                except device.DoesNotExist:
                    print("no device with name '{}' found".format(_name))
                else:
                    for _key, _value in _ld.iteritems():
                        _sm = SmartKey(_dev, _key)
                        if _sm.resolved:
                            _sm.set(_value)
