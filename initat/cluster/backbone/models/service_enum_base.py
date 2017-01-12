# Copyright (C) 2016-2017 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw-server
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
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
# -*- coding: utf-8 -*-
#
""" serviceEnum Base for 'global' configenum object, for servers """



from django.db.models import Q
from initat.host_monitoring.service_enum_base import icswServiceEnumBaseClient
from django.contrib.contenttypes.models import ContentType

__all__ = [
    b"icswServiceEnumBase",
    b"EggAction",
]


class EggAction(object):
    def __init__(self, action, content_type, weight=1, timeframe=0, ghost=False):
        # timeframe is in days
        self.action = action
        if isinstance(content_type, str):
            try:
                content_type = ContentType.objects.get(Q(model=content_type))
            except ContentType.DoesNotExist:
                # this can happen during install
                content_type = None
            except ContentType.MultipleObjectsReturned:
                print("Multiple objects defined in service_enum_base.py for content_type {}".format(content_type))
                content_type = ContentType.objects.filter(Q(model=content_type))[0]
            except:
                # this can happen on UCS installs
                content_type = None
        self.content_type = content_type
        self.weight = weight
        self.timeframe_secs = 24 * 3600 * timeframe
        self.ghost = ghost

    def __str__(self):
        return "{} {}".format(self.action, str(self.content_type))


class icswServiceEnumBase(icswServiceEnumBaseClient):
    def __init__(self, name, info="N/A", root_service=True, msi_block_name=None, egg_actions=[]):
        icswServiceEnumBaseClient.__init__(self, name, info, root_service, msi_block_name)
        self.client_service = False
        self.server_service = True
        # for egg consumers
        self.egg_actions = egg_actions
