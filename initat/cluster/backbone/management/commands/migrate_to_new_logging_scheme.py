#!/usr/bin/python-init -Otu
#
# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 Andreas Lang-Nevyjel
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
from initat.cluster.backbone.models import log_status, devicelog, log_source, \
    LogLevel, LogSource, DeviceLogEntry, user
import logging_tools
from django.db.models import Q


class Command(BaseCommand):
    help = ("Migrate to new logging_scheme")
    args = ''

    def handle(self, **options):
        cur_c = DeviceLogEntry.objects.all().count()
        if not cur_c:
            LogSource.objects.all().exclude(Q(identifier="cluster")).delete()
            # LogLevel.objects.all().delete()
            print("migrating to new logging scheme, logs to handle: {:d}".format(devicelog.objects.all().count()))
            # old to new log_source dict
            _ls_dict = {}
            for _ls in log_source.objects.all():
                if _ls.identifier == "user":
                    _ls_dict[_ls.pk] = None
                else:
                    _ls_dict[_ls.pk] = LogSource.new(
                        identifier=_ls.identifier,
                        name=_ls.name,
                        description=_ls.description,
                        device=_ls.device,
                    )
            # old to new log_status (Level) dict
            _ll_dict = {}
            for _ls in log_status.objects.all():
                _ll_dict[_ls.pk] = LogLevel.objects.get(Q(identifier={"c": "c", "w": "w", "e": "e"}.get(_ls.identifier, "o")))
            print _ls_dict
            print _ll_dict

        else:
            print("new logging_scheme already in use")
