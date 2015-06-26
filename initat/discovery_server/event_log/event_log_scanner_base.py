# Copyright (C) 2015 Bernhard Mallinger, init.at
#
# Send feedback to: <mallinger@init.at>
#
# this file is part of discovery-server
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


class EventLogPollerJobBase(object):
    def __init__(self, log, db, target_device, target_ip):
        self.log = log
        self.db = db
        self.target_device = target_device
        self.target_ip = target_ip

    def start(self):
        pass

    def periodic_check(self):
        raise NotImplementedError

    def __eq__(self, other):
        if not isinstance(other, EventLogPollerJobBase):
            return False
        return self.target_device == other.target_device and self.target_ip == other.target_ip
