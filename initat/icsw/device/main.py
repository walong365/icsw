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
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

import django
django.setup()

from django.db.models import Q
from initat.cluster.backbone.models import device
from initat.cluster.backbone.models.functions import to_system_tz
from initat.tools import logging_tools
import argparse


def main(opt_ns):
    # resolve devices
    dev_dict = {
        _dev.name: _dev for _dev in device.objects.filter(Q(name__in=opt_ns.dev))
    }
    _unres = set(opt_ns.dev) - set(dev_dict.keys())
    print(
        "{}: {}{}".format(
            logging_tools.get_plural("device", len(opt_ns.dev)),
            ", ".join(sorted(opt_ns.dev)),
            ", unresolvable: {}".format(
                ", ".join(sorted(list(_unres)))
            ) if _unres else ""
        )
    )
    for dev_name in sorted(dev_dict.keys()):
        device_info(dev_dict[dev_name])


def device_info(cur_dev):
    print(u"Information about device '{}' (full name {}, devicegroup {})".format(
        unicode(cur_dev),
        unicode(cur_dev.full_name),
        unicode(cur_dev.device_group))
    )
    print("UUID is '{}', database-ID is {:d}".format(cur_dev.uuid, cur_dev.pk))
    net_devs = cur_dev.netdevice_set.all().order_by("devname")
    if len(net_devs):
        for cur_nd in net_devs:
            print(
                "    {}".format(
                    cur_nd.devname,
                )
            )
            for cur_ip in cur_nd.net_ip_set.all().order_by("ip"):
                print(
                    "        IP {} in network {}".format(
                        cur_ip.ip,
                        unicode(cur_ip.network),
                    )
                )
    print("")
    if cur_dev.deviceboothistory_set.count():
        _brs = cur_dev.deviceboothistory_set.all()
        print("found {}".format(logging_tools.get_plural("boot record", len(_brs))))
        for _entry in _brs:
            print "  {}, kernel: {}, image: {}".format(
                to_system_tz(_entry.date),
                ", ".join(
                    [
                        "{} ({}, {})".format(
                            unicode(_kernel.kernel.name),
                            _kernel.full_version,
                            _kernel.timespan,
                        ) for _kernel in _entry.kerneldevicehistory_set.all()
                    ]
                ) or "---",
                ", ".join(
                    [
                        "{} ({}, {})".format(
                            unicode(_image.image.name),
                            _image.full_version,
                            _image.timespan,
                        ) for _image in _entry.imagedevicehistory_set.all()
                    ]
                ) or "---",
            )
    else:
        print("device has not boot history records")
