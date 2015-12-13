#!/usr/bin/python-init -Otu
#
# -*- coding: utf-8 -*-
#
# Copyright (C) 2013-2015 Andreas Lang-Nevyjel
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
""" create version entries after DB migration run """

from django.core.management.base import BaseCommand

from initat.cluster.backbone.models import ICSWVersion, VERSION_NAME_LIST
from initat.constants import VERSION_CS_NAME
from initat.tools import config_store


class Command(BaseCommand):
    option_list = BaseCommand.option_list
    help = ("Create Database version entries after an migration run.")
    args = ''

    def handle(self, **options):
        main()


def main():
    if not ICSWVersion.objects.all().count():
        insert_idx = 0
    else:
        insert_idx = max(ICSWVersion.objects.all().values_list("insert_idx", flat=True))
    insert_idx += 1
    _vers = config_store.ConfigStore(VERSION_CS_NAME, quiet=True)
    print(
        "Creating {:d} version entries with idx {:d} ...".format(
            len(VERSION_NAME_LIST),
            insert_idx
        )
    )
    for _name in VERSION_NAME_LIST:
        _v = _vers[_name]
        print("    {} is {}".format(_name, _v))
        ICSWVersion.objects.create(
            name=_name,
            version=_v,
            insert_idx=insert_idx,
        )
    # stale entries
    stale = ICSWVersion.objects.filter(Q(insert_idx__lt=insert_idx)).count()
    print("Stale entries in database: {:d}".format(stale))
