# Copyright (C) 2015 Bernhard Mallinger, init.at
#
# this file is part of cluster-backbone-sql
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
""" database definitions for recording icinga events and aggregating them """

import collections
import itertools
import operator
from collections import defaultdict

import django
from django.db import models
from django.db.models import Max, Min, Prefetch, Q

from initat.cluster.backbone.available_licenses import LicenseParameterTypeEnum
from initat.cluster.backbone.models import mon_check_command
from initat.cluster.backbone.models.functions import db_limit_1
from initat.cluster.backbone.models.license import LicenseLockListDeviceService, LicenseUsage


########################################
# models for direct data from icinga logs


class mon_icinga_log_raw_base(models.Model):
    idx = models.AutoField(primary_key=True)
    date = models.DateTimeField(db_index=True)
    device = models.ForeignKey("backbone.device", db_index=True, null=True)  # only null for device_independent
    # events which apply to all devices such as icinga shutdown
    device_independent = models.BooleanField(default=False, db_index=True)
    # text from log entry
    msg = models.TextField()
    # entry originates from this logfile
    logfile = models.ForeignKey("backbone.mon_icinga_log_file", blank=True, null=True)

    STATE_UNKNOWN = "U"
    STATE_UNKNOWN_LONG = "UNKNOWN"

    STATE_TYPE_HARD = "H"
    STATE_TYPE_SOFT = "S"
    # undetermined is the icsw view point of not knowing about a state.
    # icinga sometimes says "unknown" (see services below)
    STATE_UNDETERMINED = "UD"  # state as well as state type
    STATE_UNDETERMINED_LONG = "UNDETERMINED"
    STATE_PLANNED_DOWN = "PD"  # state as well as state type
    STATE_PLANNED_DOWN_LONG = "PLANNED DOWN"
    STATE_TYPES = [(STATE_TYPE_HARD, "HARD"),
                   (STATE_TYPE_SOFT, "SOFT"),
                   (STATE_UNDETERMINED, STATE_UNDETERMINED),
                   (STATE_PLANNED_DOWN, STATE_PLANNED_DOWN_LONG)]

    START = "START"
    STOP = "STOP"

    # use for CharFields
    _start_stop_field_args = {
        "max_length": 5,
        "choices": [(START, START), (STOP, STOP)]
    }

    class Meta:
        abstract = True


class raw_host_alert_manager(models.Manager):
    def calc_alerts(self, start_time, end_time, additional_filter=None):
        host_alerts = defaultdict(lambda: [])

        queryset = self
        if additional_filter is not None:
            queryset = queryset.filter(additional_filter)
        for entry in queryset.filter(Q(device_independent=False) & Q(date__range=(start_time, end_time))):
            host_alerts[entry.device_id].append(entry)
        # calc dev independent afterwards and add to all keys
        for entry in mon_icinga_log_raw_host_alert_data.objects.filter(
            device_independent=True, date__range=(start_time, end_time)
        ):
            for key in host_alerts:
                host_alerts[key].append(entry)

        for l in host_alerts.itervalues():
            # not in order due to dev independents and downtimes
            l.sort(key=operator.attrgetter('date'))
        return host_alerts

    def calc_limit_alerts(self, time, mode='last before', **kwargs):
        """
        Find last alert before or first alert after some point in time for some devices
        :param mode: 'last before' or 'first after'
        """
        return StatusHistoryUtils.do_calc_limit_alerts(self, is_host=True, time=time, mode=mode, **kwargs)


class mon_icinga_log_raw_host_alert_data(mon_icinga_log_raw_base):
    STATE_UP = "UP"
    STATE_DOWN = "D"
    STATE_UNREACHABLE = "UR"
    STATE_CHOICES = [
        (STATE_UP, "UP"),
        (STATE_DOWN, "DOWN"),
        (STATE_UNREACHABLE, "UNREACHABLE"),
        (mon_icinga_log_raw_base.STATE_UNKNOWN, mon_icinga_log_raw_base.STATE_UNKNOWN_LONG),
        (mon_icinga_log_raw_base.STATE_PLANNED_DOWN, mon_icinga_log_raw_base.STATE_PLANNED_DOWN_LONG),
        (mon_icinga_log_raw_base.STATE_UNDETERMINED, mon_icinga_log_raw_base.STATE_UNDETERMINED_LONG)
    ]
    STATE_CHOICES_REVERSE_MAP = {val: key for (key, val) in STATE_CHOICES}

    objects = raw_host_alert_manager()

    state_type = models.CharField(max_length=2, choices=mon_icinga_log_raw_base.STATE_TYPES)
    state = models.CharField(max_length=2, choices=STATE_CHOICES)
    # whether this is an entry at the beginning of a fresh archive file.
    log_rotation_state = models.BooleanField(default=False)
    # whether this is an entry after icinga restart
    initial_state = models.BooleanField(default=False)

    class CSW_Meta:
        backup = False


class raw_service_alert_manager(models.Manager):
    def calc_alerts(self, start_time, end_time, additional_filter=None):
        # result is ordered by date
        service_alerts = defaultdict(lambda: [])

        queryset = self.filter(device_independent=False, date__range=(start_time, end_time))
        if additional_filter is not None:
            queryset = queryset.filter(additional_filter)

        for entry in queryset:
            key = entry.device_id, entry.service_id, entry.service_info
            service_alerts[key].append(entry)
        # calc dev independent afterwards and add to all keys
        for entry in self.filter(device_independent=True, date__range=(start_time, end_time)):
            for key in service_alerts:
                service_alerts[key].append(entry)

        for l in service_alerts.itervalues():
            # not in order due to dev independents and downtimes
            l.sort(key=operator.attrgetter('date'))
        return service_alerts

    def calc_limit_alerts(self, time, mode='last before', **kwargs):
        """
        Find last alert before or first alert after some point in time for some devices
        :param mode: 'last before' or 'first after'
        """
        return StatusHistoryUtils.do_calc_limit_alerts(self, is_host=False, time=time, mode=mode, **kwargs)

    @staticmethod
    def calculate_service_name_for_client(entry):
        """
        :param entry: aggregated or raw log model entry. service should be prefetched for reasonable performance.
        """
        return raw_service_alert_manager._do_calculate_service_name_for_client(entry.service, entry.service_info)

    @staticmethod
    def calculate_service_name_for_client_tuple(service_id, service_info):
        try:
            service = mon_check_command.objects.get(pk=service_id)
        except mon_check_command.DoesNotExist:
            service = None
        return raw_service_alert_manager._do_calculate_service_name_for_client(service, service_info)

    @staticmethod
    def _do_calculate_service_name_for_client(service, service_info):
        service_name = service.name if service else u""
        return u"{},{}".format(service_name, service_info if service_info else u"")


class mon_icinga_log_raw_service_alert_data(mon_icinga_log_raw_base):
    STATE_OK = "O"
    STATE_WARNING = "W"
    STATE_CRITICAL = "C"
    STATE_CHOICES = [
        (STATE_OK, "OK"),
        (STATE_WARNING, "WARNING"),
        (mon_icinga_log_raw_base.STATE_UNKNOWN, mon_icinga_log_raw_base.STATE_UNKNOWN_LONG),
        (STATE_CRITICAL, "CRITICAL"),
        (mon_icinga_log_raw_base.STATE_UNDETERMINED, mon_icinga_log_raw_base.STATE_UNDETERMINED_LONG),
        (mon_icinga_log_raw_base.STATE_PLANNED_DOWN, mon_icinga_log_raw_base.STATE_PLANNED_DOWN_LONG),
    ]
    STATE_CHOICES_REVERSE_MAP = {val: key for (key, val) in STATE_CHOICES}

    objects = raw_service_alert_manager()

    # NOTE: there are different setup, at this time only regular check_commands are supported
    # they are identified by the mon_check_command.pk and their name, hence the fields here
    # the layout of this table probably has to change in order to accommodate for further services
    # I however can't do that now as I don't know how what to change it to
    service = models.ForeignKey(mon_check_command, null=True, db_index=True)  # null for device_independent events
    if db_limit_1():
        service_info = models.TextField(blank=True, null=True)
    else:
        service_info = models.TextField(blank=True, null=True, db_index=True)

    state_type = models.CharField(max_length=2, choices=mon_icinga_log_raw_base.STATE_TYPES)
    state = models.CharField(max_length=2, choices=STATE_CHOICES)

    # whether this is an entry at the beginning of a fresh archive file.
    log_rotation_state = models.BooleanField(default=False)
    # whether this is an entry after icinga restart
    initial_state = models.BooleanField(default=False)

    class CSW_Meta:
        backup = False


class mon_icinga_log_full_system_dump(models.Model):
    # save dates of all full system dumps,
    # i.e. with log_rotation_state = True or inital_state = True in (host|service)-alerts table
    # this is needed for faster access, the alerts-tables are too huge
    idx = models.AutoField(primary_key=True)
    date = models.DateTimeField(db_index=True, unique=True)

    class CSW_Meta:
        backup = False


class mon_icinga_log_raw_service_flapping_data(mon_icinga_log_raw_base):
    service = models.ForeignKey(mon_check_command, null=True)  # null for device_independent events
    service_info = models.TextField(blank=True, null=True)

    flapping_state = models.CharField(**mon_icinga_log_raw_base._start_stop_field_args)

    class CSW_Meta:
        backup = False


class mon_icinga_log_raw_host_flapping_data(mon_icinga_log_raw_base):
    flapping_state = models.CharField(**mon_icinga_log_raw_base._start_stop_field_args)

    class CSW_Meta:
        backup = False


class mon_icinga_log_raw_service_notification_data(mon_icinga_log_raw_base):
    service = models.ForeignKey(mon_check_command, null=True)  # null for unidentifiable services and dev independent
    service_info = models.TextField(blank=True, null=True)

    state = models.CharField(max_length=2, choices=mon_icinga_log_raw_service_alert_data.STATE_CHOICES)
    user = models.TextField()
    notification_type = models.TextField()

    class CSW_Meta:
        backup = False


class mon_icinga_log_raw_host_notification_data(mon_icinga_log_raw_base):
    state = models.CharField(max_length=2, choices=mon_icinga_log_raw_host_alert_data.STATE_CHOICES)
    user = models.TextField()
    notification_type = models.TextField()

    class CSW_Meta:
        backup = False


class mon_icinga_log_raw_service_downtime_data(mon_icinga_log_raw_base):
    service = models.ForeignKey(mon_check_command, null=True)
    service_info = models.TextField(blank=True, null=True)

    downtime_state = models.CharField(**mon_icinga_log_raw_base._start_stop_field_args)

    def __init__(self, *args, **kwargs):
        super(mon_icinga_log_raw_service_downtime_data, self).__init__(*args, **kwargs)
        # interface compatibility with regular alerts
        self.state = mon_icinga_log_raw_base.STATE_PLANNED_DOWN
        self.state_type = mon_icinga_log_raw_base.STATE_PLANNED_DOWN

    class CSW_Meta:
        backup = False


class mon_icinga_log_raw_host_downtime_data(mon_icinga_log_raw_base):
    downtime_state = models.CharField(**mon_icinga_log_raw_base._start_stop_field_args)

    def __init__(self, *args, **kwargs):
        super(mon_icinga_log_raw_host_downtime_data, self).__init__(*args, **kwargs)
        # interface compatibility with regular alerts
        self.state = mon_icinga_log_raw_base.STATE_PLANNED_DOWN
        self.state_type = mon_icinga_log_raw_base.STATE_PLANNED_DOWN

    class CSW_Meta:
        backup = False


class mon_icinga_log_file(models.Model):
    idx = models.AutoField(primary_key=True)
    filepath = models.TextField()

    class CSW_Meta:
        backup = False


class _last_read_manager(models.Manager):
    def get_last_read(self):
        """
        @return int timestamp
        """
        if self.all():
            return self.all()[0]
        else:
            return None


class mon_icinga_log_last_read(models.Model):
    # this table contains only one row
    idx = models.AutoField(primary_key=True)
    position = models.BigIntegerField()  # position of start of last line read
    timestamp = models.IntegerField()  # time of last line read

    objects = _last_read_manager()

    class CSW_Meta:
        backup = False


########################################
# models for aggregated data from icinga


class mon_icinga_log_aggregated_timespan(models.Model):
    idx = models.AutoField(primary_key=True)
    end_date = models.DateTimeField()
    start_date = models.DateTimeField(db_index=True)
    duration = models.IntegerField()  # seconds
    duration_type = models.IntegerField(db_index=True)  # durations pseudo enum from functions


class mon_icinga_log_aggregated_host_data(models.Model):
    STATE_FLAPPING = "FL"  # this is also a state type
    STATE_CHOICES = mon_icinga_log_raw_host_alert_data.STATE_CHOICES + [(STATE_FLAPPING, "FLAPPING")]
    STATE_CHOICES_REVERSE_MAP = {val: key for (key, val) in STATE_CHOICES}

    STATE_CHOICES_READABLE = {k: v.capitalize() for (k, v) in STATE_CHOICES}

    STATE_TYPES = mon_icinga_log_raw_base.STATE_TYPES + [(STATE_FLAPPING, STATE_FLAPPING)]

    idx = models.AutoField(primary_key=True)
    device = models.ForeignKey("backbone.device")
    timespan = models.ForeignKey(mon_icinga_log_aggregated_timespan)

    state_type = models.CharField(max_length=2, choices=STATE_TYPES)
    state = models.CharField(max_length=2, choices=STATE_CHOICES)

    # ratio of time span spent in this (state_type, state)
    value = models.FloatField()

    class CSW_Meta:
        backup = False


class mon_icinga_log_aggregated_service_data_manager(models.Manager):

    @staticmethod
    def merge_state_types(data, undetermined_state, normalize=False):
        # data is list of dicts {'state': state, 'value': value, 'state_type': state_type}
        # this merges soft and hard states, but also supports multiple entries per state
        data_merged_state_types = []
        # merge state_types (soft/hard)

        for state in set(d['state'] for d in data):
            data_merged_state_types.append(
                {
                    'state': state,
                    'value': sum(d['value'] for d in data if d['state'] == state)
                }
            )

        if normalize:
            # normalize to 1.0 (useful if the data is from multiple aggregated timespans)
            total_value = sum(d['value'] for d in data_merged_state_types)
            for d in data_merged_state_types:
                d['value'] /= total_value

        if not data_merged_state_types:
            data_merged_state_types.append({'state': undetermined_state, 'value': 1})
        return data_merged_state_types

    def get_data(self, devices, timespans, license, merge_services=False, use_client_name=True):
        """
        :param devices: either [device_pk] (meaning all services of these) or {device_pk: (service_pk, service_info)}
        :param license: which license to use for this query
        :param use_client_name: whether to refer to services the way the cs code does or as (serv_pk, serv_info)
        """
        if use_client_name:
            trans = mon_icinga_log_aggregated_service_data.STATE_CHOICES_READABLE
        else:
            class dummy_dict(dict):
                def __getitem__(self, item):
                    return item
            trans = dummy_dict()

        def get_data_per_device(devices, timespans):

            if isinstance(devices, dict):
                _queries = []
                for dev_id, service_list in devices.iteritems():
                    # query: device_pk matches as well as one service_pk/service_info combination
                    service_qs = (
                        (
                            Q(service_id=serv_pk) & Q(service_info=service_info)
                        ) for serv_pk, service_info in service_list
                    )
                    _queries.append(Q(device_id=dev_id) & reduce(lambda x, y: x | y, service_qs))
                # or around all queries
                query_filter = reduce(lambda x, y: x | y, _queries)
                device_ids = devices.keys()
            else:
                query_filter = Q(device_id__in=devices)
                device_ids = devices

            queryset = mon_icinga_log_aggregated_service_data.objects.filter(query_filter & Q(timespan__in=timespans))

            data_per_device = {device_id: defaultdict(lambda: []) for device_id in device_ids}
            used_device_services = {device_id: set() for device_id in device_ids}
            # can't do regular prefetch_related for queryset, this seems to work
            device_service_timespans = collections.defaultdict(lambda: collections.defaultdict(lambda: set()))
            for entry in queryset.prefetch_related(Prefetch("service")):

                if entry.service is not None:
                    locked = LicenseLockListDeviceService.objects.is_device_service_locked(
                        license,
                        entry.device_id,
                        entry.service.pk
                    )
                else:
                    locked = LicenseLockListDeviceService.objects.is_device_locked(
                        license,
                        entry.device_id
                    )

                if not locked:

                    if entry.service is not None:
                        used_device_services[entry.device_id].add(entry.service.pk)

                    relevant_data_from_entry = {
                        'state': trans[entry.state],
                        'state_type': entry.state_type,
                        'value': entry.value
                    }

                    if use_client_name:
                        service_key = mon_icinga_log_raw_service_alert_data.objects.calculate_service_name_for_client(entry)
                    else:
                        service_key = (entry.service_id, entry.service_info)

                    device_service_timespans[entry.device_id][service_key].add(entry.timespan)

                    # there can be more than one entry for each state and state type per service
                    # if there are multiple timespans
                    data_per_device[entry.device_id][service_key].append(relevant_data_from_entry)

            if len(timespans) > 1:
                # now for each service, we should have len(timespans) entries.
                # if not, we don't have data for that, so fill it up
                for device_id, service_name_timespans in device_service_timespans.iteritems():
                    for service_key, timespans_present in service_name_timespans.iteritems():
                        num_missing = len(timespans) - len(timespans_present)
                        if num_missing > 0:
                            data_per_device[device_id][service_key].append(
                                {
                                    'state': trans[mon_icinga_log_raw_service_alert_data.STATE_UNDETERMINED],
                                    'state_type': mon_icinga_log_raw_service_alert_data.STATE_UNDETERMINED,
                                    'value': 1 * num_missing,  # this works since we normalize afterwards
                                }
                            )

            return data_per_device, used_device_services

        def merge_all_services_of_devices(data_per_device):
            return_data = {}
            for device_id, device_data in data_per_device.iteritems():
                # it's not obvious how to aggregate service states
                # we now just add the values,but we could e.g. also use the most common state of a service as it's state
                # then we could say "4 services were ok, 3 were critical".
                data_concat = list(itertools.chain.from_iterable(s_data for s_data in device_data.itervalues()))
                return_data[device_id] = self.merge_state_types(
                    data_concat,
                    trans[mon_icinga_log_raw_base.STATE_UNDETERMINED],
                    normalize=True
                )
            return return_data

        def merge_service_state_types_per_device(data_per_device):
            return_data = {}
            # merge state types for each service in each device
            for device_id, device_service_data in data_per_device.iteritems():
                return_data[device_id] = {
                    service_key: self.merge_state_types(
                        service_data,
                        trans[mon_icinga_log_raw_base.STATE_UNDETERMINED],
                        normalize=len(timespans) > 1  # don't need to normalize if only 1
                    ) for service_key, service_data in device_service_data.iteritems()
                }

            return return_data

        data_per_device, used_device_services = get_data_per_device(devices, timespans)

        # this mode is for an overview of the services of a device without saying anything about a particular service
        if merge_services:
            LicenseUsage.log_usage(license, LicenseParameterTypeEnum.device, data_per_device.iterkeys())
            return merge_all_services_of_devices(data_per_device)
        else:
            LicenseUsage.log_usage(license, LicenseParameterTypeEnum.service, used_device_services)
            return merge_service_state_types_per_device(data_per_device)


class mon_icinga_log_aggregated_service_data(models.Model):
    objects = mon_icinga_log_aggregated_service_data_manager()

    STATE_FLAPPING = "FL"
    STATE_CHOICES = mon_icinga_log_raw_service_alert_data.STATE_CHOICES + [(STATE_FLAPPING, "FLAPPING")]
    STATE_CHOICES_REVERSE_MAP = {val: key for (key, val) in STATE_CHOICES}

    STATE_CHOICES_READABLE = {k: v.capitalize() for (k, v) in STATE_CHOICES}

    idx = models.AutoField(primary_key=True)
    timespan = models.ForeignKey(mon_icinga_log_aggregated_timespan)

    STATE_TYPES = mon_icinga_log_raw_service_alert_data.STATE_TYPES + [(STATE_FLAPPING, STATE_FLAPPING)]

    device = models.ForeignKey("backbone.device")
    state_type = models.CharField(max_length=2, choices=STATE_TYPES)
    state = models.CharField(max_length=2, choices=STATE_CHOICES)

    service = models.ForeignKey(mon_check_command, null=True)  # null for unidentifiable services
    service_info = models.TextField(blank=True, null=True)

    # ratio of time span spent in this (state_type, state)
    value = models.FloatField()

    class CSW_Meta:
        backup = False


########################################
# outsourced calculation functions


class StatusHistoryUtils(object):
    """Misc functions used in this file mostly"""
    @staticmethod
    def get_key_fun(is_host):
        if is_host:
            key_fun = lambda entry: entry.device_id
        else:
            key_fun = lambda entry: (entry.device_id, entry.service_id, entry.service_info)
        return key_fun

    @staticmethod
    def preprocess_start_stop_data(queryset, key_fun, field_name, start_time, end_time):
        """
        for models which have entries for start and stop events,
        create a dict which contains (start, stop) tuples
        extract entries for this timespan (the rest would be the same for every timespan)
        @param start_time: discard events which have finished before start_time
        @param end_time: discard events which start after end_time
        """
        StartStopDuration = collections.namedtuple(
            "StartStopDuration",
            ['start', 'end', 'start_entry', 'end_entry']
        )
        cache = defaultdict(lambda: [])  # this is sorted by time
        aux_start_times = {}
        for entry in queryset:
            key = key_fun(entry)
            if key not in aux_start_times and getattr(entry, field_name) == mon_icinga_log_raw_base.START:
                # proper start
                if entry.date <= end_time:  # discard events which start after we have ended
                    aux_start_times[key] = entry
            if key in aux_start_times and getattr(entry, field_name) == mon_icinga_log_raw_base.STOP:
                # a proper stop
                start_entry = aux_start_times.pop(key)
                if entry.date >= start_time:  # discard elements which have already finished when we haven't started yet
                    cache[key].append(StartStopDuration(start_entry.date, entry.date, start_entry, entry))
        # handles events which haven't stopped yet
        for key, start_entry in aux_start_times.iteritems():
            cache[key].append(StartStopDuration(start_entry.date, django.utils.timezone.now(), start_entry, None))
        return dict(cache)  # make into regular dict

    @staticmethod
    def do_calc_limit_alerts(obj_man, is_host, time, mode='last before', additional_filter=None):
        """
        For historic and database query reasons returns a dict with relevant values (see group_by_fields and
        additional_fields).
        """

        # TODO: replace mode by some enum34 instance
        assert mode in ('last before', 'first after')

        # keep available fields in sync with special downtime state fields which we construct below
        group_by_fields = ['device_id', 'state', 'state_type']
        additional_fields = ['date', 'msg']
        if not is_host:
            group_by_fields.extend(['service_id', 'service_info'])

        # NOTE: code was written for 'last_before' mode and then generalised, hence some vars are called 'latest...'
        try:
            if mode == 'last before':
                latest_dev_independent_service_alert = obj_man.filter(date__lte=time, device_independent=True).latest('date')
            else:
                latest_dev_independent_service_alert = obj_man.filter(date__gte=time, device_independent=True).earliest('date')

            # can't use values() on single entry
            latest_dev_independent_service_alert = {
                key: getattr(latest_dev_independent_service_alert, key) for key in (group_by_fields + additional_fields)
            }
        except obj_man.model.DoesNotExist:
            latest_dev_independent_service_alert = None

        # get last service alert of each service before the start time
        last_service_alert_cache = {}
        if mode == 'last before':
            queryset = obj_man.filter(Q(date__lte=time) & Q(device_independent=False))
        else:
            queryset = obj_man.filter(Q(date__gte=time) & Q(device_independent=False))

        apply_additional_filter = lambda x: x if additional_filter is None else x.filter(additional_filter)

        queryset = apply_additional_filter(queryset)
        queryset = queryset.values(*group_by_fields)

        # only get these values and annotate with extreme date, then we get the each field-tuple with their extreme date

        if mode == 'last before':
            queryset = queryset.annotate(extreme_date=Max('date'))
        else:
            queryset = queryset.annotate(extreme_date=Min('date'))

        for entry in queryset:
            # prefer latest info if there is dev independent one

            if mode == 'last before':
                comp = lambda x, y: x > y
            else:
                comp = lambda x, y: x < y
            if latest_dev_independent_service_alert is not None and \
                    comp(latest_dev_independent_service_alert['date'], entry['extreme_date']):
                relevant_entry = latest_dev_independent_service_alert
            else:
                relevant_entry = entry

            if is_host:
                key = entry['device_id']
            else:
                key = entry['device_id'], entry['service_id'], entry['service_info']

            # the query above is not perfect, it should group only by device and service
            # this seems to be hard in django:
            # http://stackoverflow.com/questions/19923877/django-orm-get-latest-for-each-group
            # so we do the last grouping by this key here manually
            if key not in last_service_alert_cache or comp(entry['extreme_date'], last_service_alert_cache[key][1]):
                last_service_alert_cache[key] = relevant_entry, entry['extreme_date']

        # NOTE: apparently, in django, if you use group_by, you can only select the elements you group_by and
        #       the annotated elements therefore we retrieve the extra parameters manually
        for k, v in last_service_alert_cache.iteritems():
            if any(key not in v[0] for key in additional_fields):
                if is_host:
                    additional_fields_query = obj_man.filter(
                        device_id=k,
                        date=v[1]
                    )
                else:
                    additional_fields_query = obj_man.filter(
                        device_id=k[0],
                        service_id=k[1],
                        service_info=k[2],
                        date=v[1]
                    )

                if len(additional_fields_query) == 0:  # must be dev independent
                    additional_fields_query = obj_man.filter(device_independent=True, date=v[1])
                v[0].update(additional_fields_query.values(*additional_fields)[0])

        # drop extreme date
        return {k: v[0] for (k, v) in last_service_alert_cache.iteritems()}


class AlertList(object):
    """Nice interface to a list of either host or service alerts.
    Includes handling of last before and first after state as well as downtimes.
    Log aggregation accesses this stuff directly as this here would be too slow (especially calc_limit_alerts).
    """
    def __init__(self, is_host, alert_filter, start_time, end_time, calc_first_after=False):
        # self.is_host = is_host
        # self.alert_filter = alert_filter

        model = mon_icinga_log_raw_host_alert_data if is_host else mon_icinga_log_raw_service_alert_data

        self.alerts = model.objects.calc_alerts(
            start_time=start_time,
            end_time=end_time,
            additional_filter=alert_filter
        )
        self.last_before = model.objects.calc_limit_alerts(
            time=start_time,
            mode='last before',
            additional_filter=alert_filter
        )
        if calc_first_after:
            self.first_after = model.objects.calc_limit_alerts(
                time=end_time,
                mode='first after',
                additional_filter=alert_filter
            )

        # handle downtimes
        downtime_model = mon_icinga_log_raw_host_downtime_data if is_host else mon_icinga_log_raw_service_downtime_data
        print downtime_model
        downtimes_qs = downtime_model.objects.all().order_by('date')
        if alert_filter is not None:
            downtimes_qs = downtimes_qs.filter(alert_filter)
        downtimes = StatusHistoryUtils.preprocess_start_stop_data(
            downtimes_qs,
            StatusHistoryUtils.get_key_fun(is_host),
            'downtime_state',
            start_time,
            end_time
        )

        for k, downtime_list in downtimes.iteritems():
            self.alerts[k] = self.add_downtimes_to_alerts(self.alerts[k], self.last_before.get(k, None), downtime_list)
            downtime_at_start_alert = self.get_downtime_entry(downtime_list, start_time)
            if downtime_at_start_alert:
                downtime_entry = {}
                # create entry in "last before" format
                for key in [
                    'device_id', 'service_id',
                    'service_info', 'date', 'msg',
                    'state', 'state_type'
                ]:
                    if hasattr(downtime_at_start_alert, key):
                        downtime_entry[key] = getattr(downtime_entry, key)

                self.last_before[k] = downtime_at_start_alert

    @staticmethod
    def add_downtimes_to_alerts(alerts, last_state_description_before_time_span, downtime_list):
        """

        :param alerts:
        :param last_state_description_before_time_span:
        :param downtime_list: downtime list which overlaps this time span
        :return:
        """
        if not downtime_list:
            return alerts
        else:
            # filter alerts
            all_alerts = alerts
            alerts = [alert for alert in alerts
                      if not any(downtime.start <= alert.date < downtime.end
                                 for downtime in downtime_list)]
            # add downtime state changing alerts
            for downtime in downtime_list:
                # search last before entry
                last_alert_before_downtime = None
                for alert in all_alerts:
                    if alert.date > downtime.start:
                        break
                    last_alert_before_downtime = alert

                alerts.append(downtime.start_entry)

                # add end time if downtime has ended
                if downtime.end_entry is not None:
                    downtime_end_msg = None
                    if last_alert_before_downtime is not None:
                        state = last_alert_before_downtime.state
                        state_type = last_alert_before_downtime.state_type
                        downtime_end_msg = last_alert_before_downtime.msg
                    else:
                        # use default
                        if last_state_description_before_time_span is not None:
                            state, state_type = last_state_description_before_time_span
                        else:
                            # if there was no earlier alert, we have started with a planned downtime
                            state = state_type = mon_icinga_log_raw_base.STATE_UNDETERMINED
                    downtime.end_entry.state = state
                    downtime.end_entry.state_type = state_type
                    if downtime_end_msg is not None:
                        downtime.end_entry.msg = downtime_end_msg
                    alerts.append(downtime.end_entry)

            # if this is too slow, we could also insert the entries in order
            alerts.sort(key=operator.attrgetter('date'))
            return alerts

    @staticmethod
    def get_downtime_entry(downtime_list, time):
        for downtime in downtime_list:
            if downtime.start <= time < downtime.end:
                return downtime.start_entry
        return None
