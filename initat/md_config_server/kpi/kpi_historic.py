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
import pprint
import django.utils.timezone
from django.db.models import Q
import operator
import itertools
from initat.cluster.backbone.models import mon_icinga_log_raw_service_alert_data, mon_icinga_log_raw_base, AlertList


# itertools recipe
def pairwise(iterable):
    "s -> (s0,s1), (s1,s2), (s2, s3), ..."
    a, b = itertools.tee(iterable)
    next(b, None)
    return itertools.izip(a, b)


class TimeLineUtils(list):
    @staticmethod
    def calculate_time_lines(identifiers, is_host, start, end):
        """
        Calculate time line, i.e. list of states with a date ordered chronologically.
        First entry has date start, last one has end
        (last date does not actually mean anything since this state is valid for 0 seconds, but
        it implicitly includes info about when the time span ends)
        :param is_host: whether identifiers are all hosts or if not, they must be all services
        :param identifiers: [dev_id] | [(dev_id, serv_pk, serv_info)]
        :return: {(dev_id, serv_pk, serv_info) : TimeLine}
        """
        from initat.md_config_server.kpi import KpiResult

        if is_host:
            alert_filter = reduce(operator.or_, (Q(device_id=dev_id) for dev_id in identifiers))
        else:
            alert_filter = reduce(operator.or_, (Q(device_id=dev_id, service_id=serv_id, service_info=service_info)
                                                 for (dev_id, serv_id, service_info) in identifiers))

        alert_list = AlertList(is_host=is_host, alert_filter=alert_filter, start_time=start, end_time=end)

        if is_host:
            convert_state = KpiResult.from_icinga_host_status
        else:
            convert_state = KpiResult.from_icinga_service_status

        time_lines = {}

        for key, entry in alert_list.last_before.iteritems():
            # sadly, last before has different format than regular alerts
            time_lines[key] = [
                TimeLineEntry(date=start, state=(convert_state(entry['state']), entry['state_type']))
            ]

        for key, service_alert_list in alert_list.alerts.iteritems():
            if key not in time_lines:
                # couldn't find initial state, it has not existed at the time of start
                tl = time_lines[key] = [
                    TimeLineEntry(date=start,
                                  state=(convert_state(mon_icinga_log_raw_service_alert_data.STATE_UNDETERMINED),
                                         mon_icinga_log_raw_service_alert_data.STATE_UNDETERMINED))
                ]
            else:
                tl = time_lines[key]

            last_alert = None
            for alert in service_alert_list:
                if last_alert is None or alert.state != last_alert.state or alert.state_type != last_alert.state_type:
                    tl.append(
                        TimeLineEntry(date=alert.date, state=(convert_state(alert.state), alert.state_type))
                    )
                last_alert = alert

        # add final entry
        for tl in time_lines.itervalues():
            last_state = tl[-1].state
            tl.append(TimeLineEntry(date=end, state=last_state))

        return time_lines

    @staticmethod
    def calculate_compound_time_line(method, time_lines):
        """
        Merges all time_lines according to method
        :param method: "or" or "and"
        """
        # work on copies
        time_lines = [collections.deque(tl) for tl in time_lines]
        compound_time_line = []
        # currently handled via KpiResult:
#        state_ordering = {
#            mon_icinga_log_raw_base.STATE_PLANNED_DOWN: -10,
#            mon_icinga_log_raw_base.STATE_UNDETERMINED: 10,
#
#            mon_icinga_log_raw_service_alert_data.STATE_OK: 0,
#            mon_icinga_log_raw_service_alert_data.STATE_WARNING: 1,
#            mon_icinga_log_raw_service_alert_data.STATE_CRITICAL: 2,
#            mon_icinga_log_raw_service_alert_data.STATE_UNKNOWN: 3,  # same value as for hosts
#
#            mon_icinga_log_raw_host_alert_data.STATE_UP: 0,
#            mon_icinga_log_raw_host_alert_data.STATE_UNREACHABLE: 1,
#            mon_icinga_log_raw_host_alert_data.STATE_DOWN: 2,
#            mon_icinga_log_raw_host_alert_data.STATE_UNKNOWN: 3,  # same value as for services
#        }
        state_type_ordering = {
            # prefer soft:
            # soft critical is better than hard critical
            # note that hard ok would be better than soft ok, but soft ok usually doesn't ok because
            # if a check runs through, it's hard ok anyways
            mon_icinga_log_raw_base.STATE_PLANNED_DOWN: -1,
            mon_icinga_log_raw_base.STATE_TYPE_SOFT: 0,
            mon_icinga_log_raw_base.STATE_TYPE_HARD: 1,
            mon_icinga_log_raw_base.STATE_UNDETERMINED: 2,
        }

        def add_to_compound_tl(date, current_tl_states, force_add=False):
            # key_fun = lambda state: (state_ordering[state[0]], state_type_ordering[state[1]])
            key_fun = lambda state: (state[0], state_type_ordering[state[1]])
            if method == 'or':
                next_state = min(current_tl_states, key=key_fun)
            elif method == 'and':
                next_state = max(current_tl_states, key=key_fun)
            else:
                raise RuntimeError("Invalid aggregate_historic method: {}".format(method) +
                                   "(must be either 'or' or 'and')")

            if not compound_time_line or compound_time_line[-1].state != next_state or force_add:
                # only add entries on state change or if otherwise necessary
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

            is_last = not any(time_lines)
            # we need to make sure that the last entry is added as every time line ends with the final date

            add_to_compound_tl(next_entry.date, current_tl_states, force_add=is_last)

        return compound_time_line

    @staticmethod
    def aggregate_time_line(time_line):
        states_accumulator = collections.defaultdict(lambda: 0)
        for entry1, entry2 in pairwise(time_line):
            time_span = entry2.date - entry1.date
            states_accumulator[entry1.state] += time_span.total_seconds()

        total_time_span = sum(states_accumulator.itervalues())
        return {k: v / total_time_span for k, v in states_accumulator.iteritems()}

    @staticmethod
    def merge_state_types(time_line, soft_states_as_hard_states):
        """
        Remove state type intelligently
        """
        from initat.md_config_server.kpi.kpi_language import KpiResult
        accumulator = collections.defaultdict(lambda: 0)
        if soft_states_as_hard_states:
            for k, v in time_line.iteritems():
                accumulator[k[0]] += v
        else:
            for k, v in time_line.iteritems():
                # treat some soft states as different states (soft down isn't necessarily actually down)
                if k[0] == KpiResult.critical and k[1] == mon_icinga_log_raw_base.STATE_TYPE_SOFT:
                    actual_state = KpiResult.warning
                else:
                    # states like soft ok and soft warn are just treated as ok and warn respectively
                    actual_state = k[0]
                accumulator[actual_state] += v
        return accumulator


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
