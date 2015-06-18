#!/usr/bin/python-init -OtB
# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 Andreas Lang-Nevyjel (lang-nevyjel@init.at)
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of collectd-init
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
""" dumps graphic structure """

import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

import django
django.setup()

from django.db.models import Q
from initat.cluster.backbone.models import MachineVector, device
import argparse
import re
import datetime
import time
import stat

from initat.tools import logging_tools, process_tools

global opts


def parse_args():
    global opts
    _mvs = MachineVector.objects.all().select_related("device", "device__domain_tree_node")
    _dev_dict = {_mv.device.full_name: (_mv, _mv.device) for _mv in _mvs}
    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", default=False, action="store_true", help="enable verbose mode [%(default)s]")
    parser.add_argument("device", nargs="*", default="ALL", choices=["ALL"] + sorted(_dev_dict.keys()), help="show only specified device [%(default)s]")
    opts = parser.parse_args()
    if opts.device == "ALL":
        opts.dev_list = [_dev_dict[_key][1] for _key in sorted(_dev_dict.iterkeys())]
    else:
        opts.dev_list = [_dev_dict[_key][1] for _key in opts.device]


def show_vector(_dev):
    _mv = _dev.machinevector_set.all().prefetch_related(
        "mvstructentry_set",
        "mvstructentry_set__mvvalueentry_set",
    )[0]
    print
    print("showing {} ({:d} structural entries)".format(unicode(_mv), len(_mv.mvstructentry_set.all())))
    for _struct in _mv.mvstructentry_set.all():
        _key = _struct.key
        print(" {:<40s}  + {}".format(_key, unicode(_struct)))
        for _value in _struct.mvvalueentry_set.all():
            if _value.key:
                _fkey = "{}.{}".format(_key, _value.key)
            else:
                _fkey = _key
            print("   {:<40s}   - {}".format(_fkey, unicode(_value)))


def main():
    parse_args()
    _dev_list = opts.dev_list
    print(
        "showing {}: {}".format(
            logging_tools.get_plural("device", len(_dev_list)),
            ", ".join(sorted([unicode(_dev) for _dev in _dev_list])),
        )
    )
    for _dev in _dev_list:
        show_vector(_dev)


if __name__ == "__main__":
    main()
