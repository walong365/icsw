# Copyright (C) 2015 Bernhard Mallinger, init.at
#
# this file is part of md-config-server
#
# Send feedback to: <mallinger@init.at>
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
import collections
import django.utils.timezone
from django.db.models import Q
import operator
from initat.cluster.backbone.models import mon_icinga_log_raw_service_alert_data, mon_icinga_log_raw_base


class TimeLine(list):
    @staticmethod
    def calculate_time_lines(device_service_identifiers, start, end):
        """
        :param device_service_identifiers: [(dev_id, serv_pk, serv_info)]
        :return: {(dev_id, serv_pk, serv_info) : TimeLine}
        """
        # TODO: hosts
        additional_filter = reduce(operator.or_, (Q(device_id=dev_id, service_id=serv_id, service_info=service_info)
                                                  for (dev_id, serv_id, service_info) in device_service_identifiers))
        initial_values =\
            mon_icinga_log_raw_service_alert_data.objects.calc_limit_alerts(start, mode='last before',
                                                                            additional_filter=additional_filter)
        alerts =\
            mon_icinga_log_raw_service_alert_data.objects.calc_alerts(start, end, additional_filter=additional_filter)

        time_lines = collections.defaultdict(lambda: TimeLine())

        for (dev_id, serv_id, service_info), entry in initial_values.iteritems():
            time_lines[(dev_id, serv_id, service_info)].append(
                TimeLineEntry(date=start, state=(entry['state'], entry['state_type']))
            )

        for (dev_id, serv_id, service_info), alert_list in alerts.iteritems():
            tl = time_lines[(dev_id, serv_id, service_info)]
            last_alert = None
            for alert in alert_list:
                if last_alert is None or alert.state != last_alert.state or alert.state_type != last_alert.state_type:
                    tl.append(
                        TimeLineEntry(date=alert.date, state=(alert.state, alert.state_type))
                    )

        return time_lines

    @staticmethod
    def calculate_compound_time_line(method, time_lines):
        """
        Merges all time_lines according to method
        :param method: "or" or "and"
        """
        # work on copies
        time_lines = [collections.deque(tl) for tl in time_lines]
        compound_time_line = TimeLine()
        state_ordering = {
            mon_icinga_log_raw_service_alert_data.STATE_OK: 0,
            mon_icinga_log_raw_service_alert_data.STATE_WARNING: 1,
            mon_icinga_log_raw_service_alert_data.STATE_CRITICAL: 2,
            mon_icinga_log_raw_service_alert_data.STATE_UNKNOWN: 3,
            mon_icinga_log_raw_service_alert_data.STATE_UNDETERMINED: 4,
        }
        state_type_ordering = {
            mon_icinga_log_raw_base.STATE_TYPE_SOFT: 0,
            mon_icinga_log_raw_base.STATE_TYPE_HARD: 1,
            mon_icinga_log_raw_service_alert_data.STATE_UNDETERMINED: 2,
        }

        def add_to_compound_tl(date, current_tl_states):
            if method == 'or':
                next_state = min(current_tl_states,
                                 key=lambda state: (state_ordering[state[0]], state_type_ordering[state[1]]))
            elif method == 'and':
                next_state = max(current_tl_states,
                                 key=lambda state: (state_ordering[state[0]], state_type_ordering[state[1]]))
            else:
                raise RuntimeError("Invalid aggregate_historic method: {}".format(method) +
                                   "(must be either 'or' or 'and')")

            if not compound_time_line or compound_time_line[-1].state != next_state:  # only update on state change
                compound_time_line.append(TimeLineEntry(date, next_state))

        current_tl_states = [tl[0].state for tl in time_lines]
        add_to_compound_tl(time_lines[0][0].date, current_tl_states)
        future_date = django.utils.timezone.now()
        while any(time_lines):
            # find index of queue with chronological next event
            next_queue = min(xrange(len(time_lines)),
                             key=lambda x: time_lines[x][0].date if time_lines[x] else future_date)

            next_entry = time_lines[next_queue].popleft()
            current_tl_states[next_queue] = next_entry.state

            add_to_compound_tl(next_entry.date, current_tl_states)

        # no final event, this is the convention
        return compound_time_line


class TimeLineEntry(object):
    def __init__(self, date, state):
        """
        :type date: datetime.datetime
        :param state: (state, state_type)
        """
        self.date = date
        self.state = state

    def __repr__(self):
        return u"TimeLineEntry({}, {})".format(self.date, self.state)
