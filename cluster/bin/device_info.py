#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001-2006,2013-2014 Andreas Lang-Nevyjel, init.at
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
import argparse


def main():
    my_parser = argparse.ArgumentParser()
    my_parser.add_argument("dev", type=str, help="device to query [%(default)s]", default="")
    opts = my_parser.parse_args()
    try:
        cur_dev = device.objects.get(Q(name=opts.dev))
    except device.DoesNotExist:
        print("No device named '{}' found".format(opts.dev))
        sys.exit(1)
    for cur_dev in [cur_dev]:
        print(u"Information about device '{}' (devicegroup {})".format(
            unicode(cur_dev),
            unicode(cur_dev.device_group))
        )
        print("UUID is '{}'".format(cur_dev.uuid))
        net_devs = cur_dev.netdevice_set.all().order_by("devname")
        for cur_nd in net_devs:
            print("   {} ({})".format(
                cur_nd.devname,
                ", ".join([cur_ip.ip for cur_ip in cur_nd.net_ip_set.all().order_by("ip")]) or "no IPs")
            )

if __name__ == "__main__":
    main()
