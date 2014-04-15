#!/usr/bin/python-init -Otu
#
# -*- coding: utf-8 -*-
#
# Copyright (C) 2013-2014 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
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
""" shows and updates the current cluster routing table """

from django.core.management.base import BaseCommand
from django.db.models import Q
from initat.cluster.backbone.models import device_group
from initat.cluster.backbone import routing
from optparse import make_option
import pprint
import logging_tools

class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
    )
    help = ("Create and show the current cluster routing table.")
    args = ''

    def handle(self, **options):
        _csr = routing.srv_type_routing(force=True)
        _rsd = _csr.resolv_dict
        print "local device is {}".format(unicode(_csr.local_device))
        for _conf in sorted(_rsd):
            _c_list = _rsd[_conf]
            print "config '{}' ({})".format(_conf, logging_tools.get_plural("entry", len(_c_list)))
            for _name, _ip, _dev_pk, _penalty in _c_list:
                print "   {0:30s} {1:20s} pk={2:<4d} penalty={3:<4d}".format(_name, _ip, _dev_pk, _penalty)
