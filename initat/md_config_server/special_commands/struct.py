# Copyright (C) 2008-2016 Andreas Lang-Nevyjel, init.at
#
# this file is part of md-config-server
#
# Send feedback to: <lang-nevyjel@init.at>
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
""" structs fopr special (dynamic) tasks for md-config-server """

from __future__ import unicode_literals, print_function

from enum import Enum

__all__ = [
    b"DynamicCheckServer",
    b"DynamicCheckAction",
]


class DynamicCheckServer(Enum):
    snmp_relay = "snmp_relay"
    collrelay = "collrelay"


class DynamicCheckAction(object):
    def __init__(self, srv_enum, command, *args, **kwargs):
        self.srv_enum = srv_enum
        self.command = command
        self.args = args
        self.kwargs = kwargs

    def salt(self, hbc, special_instance):
        self.hbc = hbc
        self.special_instance = special_instance
        return self

    def __unicode__(self):
        return "DynamicCheckAction {} for {}".format(self.command, self.srv_enum.name)

    def __repr__(self):
        return unicode(self)
