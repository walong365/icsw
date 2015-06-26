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
import tempfile
import django.utils.timezone
from initat.tools import logging_tools
from initat.cluster.backbone.models import device_variable
from initat.discovery_server.discovery_struct import ExtCom
from initat.discovery_server.wmi_struct import WmiUtils

from .event_log_poller import EventLogPollerJobBase


__all__ = [
    'IpmiLogJob',
    ]


class IpmiLogJob(EventLogPollerJobBase):

    def periodic_check(self):
        pass
