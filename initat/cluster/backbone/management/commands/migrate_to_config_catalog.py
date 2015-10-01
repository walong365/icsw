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
""" migrate to configuration catalogs """

from django.core.management.base import BaseCommand

from initat.cluster.backbone.models import config, config_catalog
from initat.tools import logging_tools


class Command(BaseCommand):
    help = ("Migrate to config catalogs.")
    args = ''

    def handle(self, **options):
        num_cc = config_catalog.objects.all().count()
        if not num_cc:
            def_cc = config_catalog.create_local_catalog()
            print("created config_catalog '{}'".format(unicode(def_cc)))
            for conf in config.objects.all():
                conf.config_catalog = def_cc
                conf.save()
            print("migrated {:d} configs".format(config.objects.all().count()))
        else:
            print("{} already present".format(logging_tools.get_plural("config catalog", num_cc)))
