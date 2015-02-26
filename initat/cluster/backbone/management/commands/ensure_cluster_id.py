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
""" ensures the cluster has a valid cluster ID """

from django.core.management.base import BaseCommand
from initat.cluster.backbone.models import device


class Command(BaseCommand):
    help = ("Ensure that the cluster has a valid CLUSTER_ID")
    args = ''

    def handle(self, **options):
        try:
            _cdd = device.objects.get(Q(device_group__cluster_device_group=True))
        except device.DoesNotExist:
            pass
        else:
            _cdd.save()
