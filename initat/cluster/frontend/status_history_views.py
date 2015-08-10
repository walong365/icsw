# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 Bernhard Mallinger
#
# Send feedback to: <mallinger@init.at>
#
# This file is part of webfrontend
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


import datetime
import logging
from collections import defaultdict
import django.utils.timezone
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.utils.decorators import method_decorator
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.response import Response

from initat.cluster.backbone.available_licenses import LicenseEnum, LicenseParameterTypeEnum
from initat.cluster.backbone.models.license import LicenseUsage, LicenseLockListDeviceService
from initat.cluster.frontend.common import duration_utils
from initat.cluster.frontend.rest_views import rest_logging
from initat.cluster.backbone.models.status_history import mon_icinga_log_aggregated_host_data, \
    mon_icinga_log_aggregated_timespan, mon_icinga_log_aggregated_service_data, \
    mon_icinga_log_raw_base, mon_icinga_log_raw_service_alert_data, AlertList
from initat.cluster.backbone.models.functions import duration


logger = logging.getLogger("cluster.monitoring")


########################################
# device status history views
class _device_status_history_util(object):
    @staticmethod
    def get_timespan_tuple_from_request(request):
        date = duration_utils.parse_date(request.GET["date"])
        duration_type = {'day': duration.Day,
                         'week': duration.Week,
                         'month': duration.Month,
                         'year': duration.Year}[request.GET['duration_type']]
        start = duration_type.get_time_frame_start(date)
        end = duration_type.get_end_time_for_start(start)
        return start, end, duration_type

    @staticmethod
    def get_timespan_db_from_request(request):
        start, end, duration_type = _device_status_history_util.get_timespan_tuple_from_request(request)

        if duration_type == 'day' and (django.utils.timezone.now() - start) < datetime.timedelta(days=1):
            # produce view for today
            pass

        try:
            # time spans end one second before next start
            return mon_icinga_log_aggregated_timespan.objects.get(
                duration_type=duration_type.ID,
                start_date__range=(start, end - datetime.timedelta(seconds=1))
            )
        except mon_icinga_log_aggregated_timespan.DoesNotExist:
            return None

    @staticmethod
    def get_line_graph_data(request, for_host):
        """
        Get line graph data for hosts and services
        :param request: Request with usual parameters
        :param for_host: boolean, whether to get data for services or hosts
        :return: dict of either {(dev_id, service_id): values} or {dev_id: values}
        """
        if for_host:
            trans = dict((k, v.capitalize()) for (k, v) in mon_icinga_log_aggregated_host_data.STATE_CHOICES)
        else:
            trans = dict((k, v.capitalize()) for (k, v) in mon_icinga_log_aggregated_service_data.STATE_CHOICES)

        device_ids = [int(i) for i in request.GET["device_ids"].split(",")]

        # calculate detailed view based on all events
        start, end, _ = _device_status_history_util.get_timespan_tuple_from_request(request)
        alert_filter = Q(device__in=device_ids)

        alert_list = AlertList(is_host=for_host, alert_filter=alert_filter, start_time=start, end_time=end,
                               calc_first_after=True)

        return_data = {}

        for key, amended_list in alert_list.alerts.iteritems():
            # only use dev/serv keys which have entries in the time frame (i.e. those from entries)
            # they might be active before and after, but not during the time frame, in which case
            # they are not relevant to us

            # add first and last in case they are not contained in range already
            entry_before = alert_list.last_before.get(key, None)
            if entry_before is not None and amended_list[0].date != entry_before['date']:
                amended_list = [entry_before] + amended_list
            entry_after = alert_list.first_after.get(key, None)
            if entry_after is not None and amended_list[-1].date != entry_after['date']:
                amended_list = amended_list + [entry_after]

            l = []
            for entry in amended_list:
                if isinstance(entry, dict):
                    l.append({'date': entry['date'], 'state': trans[entry['state']], 'msg': entry['msg']})
                else:
                    l.append({'date': entry.date, 'state': trans[entry.state], 'msg': entry.msg})

            if not for_host:
                # use nice service id for services
                objs = mon_icinga_log_raw_service_alert_data.objects  # pep 8
                key = key[0], objs.calculate_service_name_for_client_tuple(key[1], key[2])

            return_data[key] = l
        return return_data


class get_hist_timespan(RetrieveAPIView):
    @method_decorator(login_required)
    @rest_logging
    def retrieve(self, request, *args, **kwargs):
        timespan = _device_status_history_util.get_timespan_db_from_request(request)
        if timespan:
            data = {'status': 'found', 'start': timespan.start_date, 'end': timespan.end_date}
        else:
            data = {'status': 'not found'}
            start, end, duration_type = _device_status_history_util.get_timespan_tuple_from_request(request)
            # return most recent data type if this type is not yet finished
            try:
                latest_timespan_db = mon_icinga_log_aggregated_timespan.objects.filter(
                    duration_type=duration_type.ID
                ).latest('start_date')
            except mon_icinga_log_aggregated_timespan.DoesNotExist:
                pass  # no data at all, can't do anything useful
            else:
                date = duration_utils.parse_date(request.GET["date"])
                if latest_timespan_db.end_date < date:
                    data = {
                        'status': 'found earlier',
                        'start': latest_timespan_db.start_date,
                        'end': latest_timespan_db.end_date
                    }

        return Response(data)


class get_hist_device_data(ListAPIView):
    @method_decorator(login_required)
    @rest_logging
    def list(self, request, *args, **kwargs):
        device_ids = [int(i) for i in request.GET["device_ids"].split(",")]

        timespan_db = _device_status_history_util.get_timespan_db_from_request(request)

        data = []
        if timespan_db:
            data = mon_icinga_log_aggregated_host_data.objects.filter(
                device_id__in=device_ids,
                timespan=timespan_db
            ).values('device_id', 'state', 'state_type', 'value')

        data_per_device = {device_id: [] for device_id in device_ids}
        for d in data:
            d['state'] = mon_icinga_log_aggregated_host_data.STATE_CHOICES_READABLE[d['state']].capitalize()
            data_per_device[d['device_id']].append(d)

        data_merged_state_types = {}
        for device_id, device_data in data_per_device.iteritems():
            if not LicenseLockListDeviceService.objects.is_device_locked(LicenseEnum.reporting, device_id):
                data_merged_state_types[device_id] = mon_icinga_log_aggregated_service_data.objects.merge_state_types(
                    device_data,
                    mon_icinga_log_aggregated_host_data.STATE_CHOICES_READABLE[
                        mon_icinga_log_raw_base.STATE_UNDETERMINED
                    ]
                )

        LicenseUsage.log_usage(LicenseEnum.reporting,
                               LicenseParameterTypeEnum.device,
                               data_merged_state_types.iterkeys())

        return Response([data_merged_state_types])  # fake a list, see coffeescript


class get_hist_service_data(ListAPIView):
    @method_decorator(login_required)
    @rest_logging
    def list(self, request, *args, **kwargs):
        device_ids = [int(i) for i in request.GET["device_ids"].split(",")]

        timespan_db = _device_status_history_util.get_timespan_db_from_request(request)

        merge_services = bool(int(request.GET.get("merge_services", 0)))
        return_data = mon_icinga_log_aggregated_service_data.objects.get_data(devices=device_ids,
                                                                              timespans=[timespan_db],
                                                                              license=LicenseEnum.reporting,
                                                                              merge_services=merge_services)

        return Response([return_data])  # fake a list, see coffeescript


class get_hist_device_line_graph_data(ListAPIView):
    """
    Returns device data for line graph
    """
    @method_decorator(login_required)
    @rest_logging
    def list(self, request, *args, **kwargs):

        return_data = _device_status_history_util.get_line_graph_data(request, for_host=True)
        return Response([return_data])  # fake a list, see coffeescript


class get_hist_service_line_graph_data(ListAPIView):
    """
    Returns service data for line graph
    """
    @method_decorator(login_required)
    @rest_logging
    def list(self, request, *args, **kwargs):
        prelim_return_data = _device_status_history_util.get_line_graph_data(request, for_host=False)

        return_data = defaultdict(lambda: {})

        for ((dev_id, service_identifier), values) in prelim_return_data.iteritems():
            return_data[dev_id][service_identifier] = values

        """
        def f():
            prelim_return_data = _device_status_history_util.get_line_graph_data(request, for_host=False)

            return_data = defaultdict(lambda: {})

            for ((dev_id, service_identifier), values) in prelim_return_data.iteritems():
                return_data[dev_id][service_identifier] = values

        import cProfile
        import time
        a = "/tmp/profl-{}".format(time.time())
        print 'prof to ', a
        cProfile.runctx("f()", globals(), locals(), a)

        from django.db import connection
        from pprint import pprint
        pprint(sorted(connection.queries, key=lambda a: a['time']), open("/tmp/prof1", "w"))

        return Response([return_data])  # fake a list, see coffeescript
        """
        return Response([return_data])  # fake a list, see coffeescript
