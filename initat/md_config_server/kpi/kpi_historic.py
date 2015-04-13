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
from django.db.models import Q
import operator
from initat.cluster.backbone.models import mon_icinga_log_raw_service_alert_data


class TimeLine(list):
    pass

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


class TimeLineEntry(object):
    def __init__(self, date, state):
        """
        :type date: datetime.datetime
        :param state: (state, state_type)
        """
        self.date = date
        self.state = state
