# Copyright (C) 2016 Andreas Lang-Nevyjel, init.at
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
""" syncer definition basics for md-config and md-sync-server """

from enum import Enum


__all__ = [
    "RemoteServer",
    "SlaveState",
]


class RemoteServer(object):
    def __init__(self, uuid, ip, port):
        self.ip = ip
        self.port = port
        self.conn_str = "tcp://{}:{:d}".format(self.ip, self.port)
        self.uuid = uuid

    def __unicode__(self):
        return "RemoteServer at {} [{}]".format(self.conn_str, self.uuid)


class SlaveState(Enum):
    init = "init"
