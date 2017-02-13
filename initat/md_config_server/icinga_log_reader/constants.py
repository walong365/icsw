# Copyright (C) 2014-2015,2017 Andreas Lang-Nevyjel, init.at
#
# this file is part of icsw-server-server
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

""" constants for icinga log reader (and aggregation) """

from enum import Enum
from collections import namedtuple


IcingaLogLine = namedtuple('icinga_log_line', ('timestamp', 'kind', 'info', 'line_no'))


class ILRParserEnum(Enum):
    icinga_service_alert = 'SERVICE ALERT'
    icinga_current_service_state = 'CURRENT SERVICE STATE'
    icinga_initial_service_state = 'INITIAL SERVICE STATE'
    icinga_service_flapping_alert = 'SERVICE FLAPPING ALERT'
    icinga_service_notification = 'SERVICE NOTIFICATION'
    icinga_service_downtime_alert = 'SERVICE DOWNTIME ALERT'

    icinga_host_alert = 'HOST ALERT'
    icinga_current_host_state = 'CURRENT HOST STATE'
    icinga_initial_host_state = 'INITIAL HOST STATE'
    icinga_host_notification = 'HOST NOTIFICATION'
    icinga_host_flapping_alert = 'HOST FLAPPING ALERT'
    icinga_host_downtime_alert = 'HOST DOWNTIME ALERT'

    icinga_service_event_handler = "SERVICE EVENT HANDLER"

    # timeperiod
    icinga_timeperiod_transition = "TIMEPERIOD TRANSITION"

    icinga_log_version = "LOG VERSION"
    icinga_log_rotation = "LOG ROTATION"
