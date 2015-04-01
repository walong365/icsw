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
""" create the cluster device supergroup """

from optparse import make_option

from django.core.management.base import BaseCommand
from django.db.models import Q
from initat.cluster.backbone import factories
from initat.cluster.backbone.models import device_group


class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option('--name', action='store', dest='name',
                    default="system", help='Name of the cluster device group [defaults to \"system\"]'),
        make_option('--description', action='store', dest='description',
                    default="system group", help='Description of the cluster device group [defaults to \"system group\"]'),
    )
    help = ("Create the cluster device group.")
    args = ''

    def handle(self, **options):
        try:
            cur_cdg = device_group.objects.get(Q(cluster_device_group=True))
        except device_group.DoesNotExist:
            cur_cdg = device_group(name=options["name"], description=options["description"], cluster_device_group=True)
            cur_cdg.save()
            print "Created cluster device group '{}'".format(unicode(cur_cdg))
        else:
            print "Cluster device group '{}' already exists".format(unicode(cur_cdg))
        factories.DeviceVariable(name="CLUSTER_NAME", device=cur_cdg.device_group.all()[0], local_copy_ok=False, value="new cluster")
