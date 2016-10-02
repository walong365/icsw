# Copyright (C) 2016 Andreas Lang-Nevyjel, init.at
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
    "icswServiceEnumBase",
    "EggAction",
]


class EggAction(object):
    def __init__(self, action, content_type, weight=1):
        self.action = action
        if isinstance(content_type, basestring):
            content_type = ContentType.objects.get(Q(model=content_type))
        self.content_type = content_type
        self.weight = weight

    def __unicode__(self):
        return u"{} {}".format(self.action, unicode(self.content_type))


class icswServiceEnumBase(icswServiceEnumBaseClient):
    def __init__(self, name, info="N/A", root_service=True, msi_block_name=None, egg_actions=[]):
        icswServiceEnumBaseClient.__init__(self, name, info, root_service, msi_block_name)
        self.client_service = False
        self.server_service = True
        # for egg consumers
        self.egg_actions = egg_actions
