# -*- coding: utf-8 -*-
#
# Copyright (C) 2015-2016 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FTNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
""" creates fixtures for cluster-server """

from initat.cluster.backbone import factories
from initat.cluster.backbone.models import config_catalog
from django.db.models import Q


def add_fixtures(**kwargs):
    try:
        sys_cc = config_catalog.objects.get(Q(system_catalog=True))
    except config_catalog.DoesNotExist:
        sys_cc = factories.ConfigCatalog(name="local", system_catalog=True)
