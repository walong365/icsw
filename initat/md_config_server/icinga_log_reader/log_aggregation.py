# Copyright (C) 2015-2017 Bernhard Mallinger, Andreas Lang-Nevyjel, init.at
#
# this file is part of md-config-server
#
# Send feedback to: <mallinger@init.at>, <lang-nevyjel@init.at>
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

import datetime
import itertools
from collections import defaultdict

from django.conf import settings
from django.db.models.query_utils import Q

from initat.cluster.backbone.models.functions import cluster_timezone, duration
from initat.cluster.backbone.models.status_history import mon_icinga_log_raw_host_alert_data, mon_icinga_log_raw_service_alert_data, \
    mon_icinga_log_last_read, mon_icinga_log_raw_service_flapping_data, \
    mon_icinga_log_raw_host_flapping_data, mon_icinga_log_aggregated_host_data, mon_icinga_log_aggregated_timespan, mon_icinga_log_raw_base,\
    mon_icinga_log_aggregated_service_data, mon_icinga_log_full_system_dump, StatusHistoryUtils, AlertList, mon_icinga_log_raw_host_downtime_data, \
    mon_icinga_log_raw_service_downtime_data
from initat.tools import logging_tools

__all__ = [
    "icinga_log_aggregator"
]


# itertools recipe
def pairwise(iterable):
    "s -> (s0,s1), (s1,s2), (s2, s3), ..."
    a, b = itertools.tee(iterable)
    next(b, None)
    return zip(a, b)


class icinga_log_aggregator(object):
    def __init__(self, log_reader):
        '''
        :param IcingaLogReader log_reader:
        '''
        self.log_reader = log_reader

    def log(self, *args, **kwargs):
        self.log_reader.log(*args, **kwargs)

    def update(self):
        from initat.md_config_server.config import global_config
        if global_config["ENABLE_ICINGA_LOG_PARSING"]:  # this is actually also checked in IcingaLogReader.update()
            if 'sqlite' in settings.DATABASES['default']['ENGINE']:
                self.log(
                    "log aggregation is not supported with the sqlite database backend",
                    logging_tools.LOG_LEVEL_ERROR
                )
            else:
                self._host_flapping_cache = mon_icinga_log_raw_host_flapping_data.objects.all().order_by('date')
                self._service_flapping_cache = mon_icinga_log_raw_service_flapping_data.objects.all().order_by('date')

                self._host_downtime_cache = mon_icinga_log_raw_host_downtime_data.objects.all().order_by('date')
                self._service_downtime_cache = mon_icinga_log_raw_service_downtime_data.objects.all().order_by('date')

                # aggregate in order of duration for incremental aggregation (would break if not in order)
                for duration_type in (duration.Hour, duration.Day, duration.Week, duration.Month, duration.Year):
                    # self.log("updating icinga log aggregates for {}".format(duration_type.__name__))

                    do_loop = True
                    try:
                        last_entry = mon_icinga_log_aggregated_timespan.objects.filter(
                            duration_type=duration_type.ID
                        ).latest("start_date")
                        next_start_time = last_entry.end_date
                        self.log(
                            "last icinga aggregated entry for {} from {} to {}".format(
                                duration_type.__name__,
                                last_entry.start_date,
                                last_entry.end_date
                            )
                        )
                    except mon_icinga_log_aggregated_timespan.DoesNotExist:
                        try:
                            earliest_date1 = mon_icinga_log_raw_host_alert_data.objects.earliest("date").date
                            earliest_date2 = mon_icinga_log_raw_service_alert_data.objects.earliest("date").date
                            earliest_date = min(earliest_date1, earliest_date2)
                            next_start_time = duration_type.get_time_frame_start(earliest_date)
                            self.log(
                                "no archive data for duration type {}, starting new data at {}".format(
                                    duration_type.__name__,
                                    next_start_time
                                )
                            )
                        except (mon_icinga_log_raw_host_alert_data.DoesNotExist,
                                mon_icinga_log_raw_service_alert_data.DoesNotExist):
                            self.log("no log data, hence nothing to aggregate")
                            do_loop = False

                    # i = 0
                    next_last_service_alert_cache = None
                    while do_loop:
                        next_end_time = duration_type.get_end_time_for_start(next_start_time)
                        last_read_obj = mon_icinga_log_last_read.objects.get_last_read()
                        if last_read_obj and next_end_time < datetime.datetime.fromtimestamp(
                            last_read_obj.timestamp,
                            cluster_timezone
                        ):
                            # have sufficient data
                            self.log(
                                "creating entry for {} starting at {}".format(
                                    duration_type.__name__,
                                    next_start_time
                                )
                            )
                            next_last_service_alert_cache = self._create_timespan_entry(
                                next_start_time,
                                next_end_time,
                                duration_type,
                                next_last_service_alert_cache
                            )
                        else:
                            # self.log("not sufficient data for entry from {} to {}".format(next_start_time,
                            # next_end_time))
                            do_loop = False

                        # check if we are supposed to die
                        self.log_reader.step()
                        if self.log_reader["exit_requested"]:
                            self.log("exit requested")
                            do_loop = False

                        # i += 1

                        # def printfun(s):
                        #    import time
                        #    prof_file_name = "/tmp/db_calls.out.{}".format(time.time())

                        #    with open(prof_file_name, "a") as f:
                        #        f.write(s)
                        #        f.write("\n")
                        # show_database_calls(printfun=printfun, full=True)

                        # if i == 2:
                        #    break

                        next_start_time = next_end_time

                    if self.log_reader["exit_requested"]:
                        break

    def _create_timespan_entry(self, start_time, end_time, duration_type, next_last_service_alert_cache=None):
        timespan_seconds = (end_time - start_time).total_seconds()

        timespan_db = mon_icinga_log_aggregated_timespan.objects.create(
            start_date=start_time,
            end_date=end_time,
            duration=timespan_seconds,
            duration_type=duration_type.ID,
        )

        try:
            # create from scratch for smallest unit and incrementally for all higher ones
            if duration_type == duration.Hour:
                next_last_service_alert_cache = self._create_timespan_entry_from_raw_data(
                    timespan_db,
                    start_time,
                    end_time,
                    duration_type,
                    next_last_service_alert_cache
                )
            else:
                self._create_timespan_entry_incrementally(
                    timespan_db,
                    start_time,
                    end_time,
                    duration_type,
                    next_last_service_alert_cache
                )
                next_last_service_alert_cache = None  # we don't get this here, but also don't need it
        except Exception as e:
            self.log("Exception while creating timespan entry: {}".format(e))
            timespan_db.delete()
            raise
        return next_last_service_alert_cache

    @staticmethod
    def get_active_hosts_and_services_in_timespan_queryset(start_time, end_time):

        # get latest full system dump plus all in the timespan. these entries define the relevant hosts and services
        # of this time span
        dump_times = []
        try:
            dump_times.append(
                mon_icinga_log_full_system_dump.objects.filter(date__lte=(start_time)).latest('date').date
            )
        except mon_icinga_log_full_system_dump.DoesNotExist:
            # no earlier date
            pass
        dump_times.extend(
            mon_icinga_log_full_system_dump.objects.filter(
                date__range=(start_time, end_time)
            ).values_list(
                'date',
                flat=True
            )
        )

        if not dump_times:
            # this happens if there are log entries, but no proper icinga start message
            # this is not really a valid state, but take the next dump to have something reasonable
            try:
                latest_obj = mon_icinga_log_full_system_dump.objects.filter(date__gte=(start_time)).earliest('date')
            except mon_icinga_log_full_system_dump.DoesNotExist:
                pass
            else:
                dump_times.append(
                    latest_obj.date
                )

        if not dump_times:
            return [], []

        def build_dump_times_filters(dump_times):
            cur = dump_times.pop()
            cur_filter = Q(date__range=(cur - datetime.timedelta(seconds=5), cur + datetime.timedelta(seconds=5)))
            if dump_times:
                return Q(cur_filter | build_dump_times_filters(dump_times))
            else:
                return cur_filter

        dump_times_filters = build_dump_times_filters(dump_times)

        timespan_hosts = mon_icinga_log_raw_host_alert_data.objects.filter(
            dump_times_filters, device_independent=False
        ).distinct(
            "device_id"
        ).values_list(
            "device_id", flat=True
        )
        timespan_services = mon_icinga_log_raw_service_alert_data.objects.filter(
            dump_times_filters, device_independent=False
        ).distinct(
            "device_id",
            "service_id",
            "service_info"
        ).values_list(
            "device_id",
            "service_id",
            "service_info"
        )

        return timespan_hosts, timespan_services

    def _create_timespan_entry_from_raw_data(self, timespan_db, start_time, end_time, duration_type,
                                             next_last_service_alert_cache=None):
        timespan_seconds = timespan_db.duration

        timespan_hosts, timespan_services =\
            self.get_active_hosts_and_services_in_timespan_queryset(start_time, end_time)

        # get flappings of timespan (can't use db in inner loop)
        # TODO: possibly extract keys in cache
        preprocess_start_stop_data = StatusHistoryUtils.preprocess_start_stop_data
        service_flapping_cache = preprocess_start_stop_data(
            self._service_flapping_cache,
            lambda flap_data: (
                flap_data.device_id,
                flap_data.service_id,
                flap_data.service_info
            ),
            'flapping_state',
            start_time,
            end_time
        )
        host_flapping_cache = preprocess_start_stop_data(
            self._host_flapping_cache,
            lambda flap_data: flap_data.device_id,
            'flapping_state',
            start_time,
            end_time
        )

        if next_last_service_alert_cache:
            last_service_alert_cache = next_last_service_alert_cache
        else:
            last_service_alert_cache = mon_icinga_log_raw_service_alert_data.objects.calc_limit_alerts(start_time)
            # only need cache format here:
            last_service_alert_cache = {
                k: (v['state'], v['state_type']) for k, v in last_service_alert_cache.items()
            }

        last_host_alert_cache = mon_icinga_log_raw_host_alert_data.objects.calc_limit_alerts(start_time)
        # only need cache format again
        last_host_alert_cache = {
            k: (v['state'], v['state_type']) for k, v in last_host_alert_cache.items()
        }

        # regular changes in time span
        def calc_weighted_states(relevant_entries, state_description_before, start_in_planned_downtime, debug=False):
            # state_description_before is always the entry according to regular alerts
            # if start_in_planned_downtime, then we count it as planned downtime, but also return the state before
            weighted_states = defaultdict(lambda: 0.0)
            for raw_entry1, raw_entry2 in pairwise(relevant_entries):
                entry_timespan_seconds = (raw_entry2.date - raw_entry1.date).total_seconds()
                entry_weight = entry_timespan_seconds / timespan_seconds

                weighted_states[(raw_entry1.state, raw_entry1.state_type)] += entry_weight
                if debug:
                    self.log(
                        "from {} to {} in state {} {}; weight: {}".format(
                            raw_entry1.date,
                            raw_entry2.date,
                            raw_entry1.state,
                            raw_entry1.state_type,
                            entry_weight
                        )
                    )

            actual_state_description_before = state_description_before if not start_in_planned_downtime else (
                mon_icinga_log_raw_base.STATE_PLANNED_DOWN,
                mon_icinga_log_raw_base.STATE_PLANNED_DOWN
            )

            # first/last
            if not relevant_entries:
                # always state before
                weighted_states[actual_state_description_before] += 1.0
                last_state_description = state_description_before
                if debug:
                    self.log("always in state {}".format(state_description_before))
            else:
                # at least one entry
                # first
                first_entry_timespan_seconds = (relevant_entries[0].date - start_time).total_seconds()
                first_entry_weight = first_entry_timespan_seconds / timespan_seconds

                weighted_states[actual_state_description_before] += first_entry_weight

                if debug:
                    self.log("fst;in state {}; weight: {}".format(state_description_before, first_entry_weight))

                # last
                last_entry = relevant_entries[len(relevant_entries) - 1]
                last_entry_timespan_seconds = (end_time - last_entry.date).total_seconds()
                last_entry_weight = last_entry_timespan_seconds / timespan_seconds

                last_state_description = (last_entry.state, last_entry.state_type)
                weighted_states[last_state_description] += last_entry_weight
                if debug:
                    self.log("last;in state {}; weight: {}".format(last_state_description, last_entry_weight))

            return weighted_states, last_state_description

        # flapping
        # check if we start in flapping state
        def calc_flapping_ratio(cache, key):
            flapping_seconds = 0.0
            for flapping in cache.get(key, []):
                flap_start = max(flapping.start, start_time)
                flap_end = min(flapping.end, end_time)
                flapping_seconds += (flap_end - flap_start).total_seconds()
            return flapping_seconds / timespan_seconds

        service_alerts = mon_icinga_log_raw_service_alert_data.objects.calc_alerts(start_time, end_time)
        host_alerts = mon_icinga_log_raw_host_alert_data.objects.calc_alerts(start_time, end_time)

        service_downtimes = StatusHistoryUtils.preprocess_start_stop_data(
            self._service_downtime_cache,
            StatusHistoryUtils.get_key_func(is_host=False),
            'downtime_state',
            start_time,
            end_time
        )
        host_downtimes = StatusHistoryUtils.preprocess_start_stop_data(
            self._host_downtime_cache,
            StatusHistoryUtils.get_key_func(is_host=True),
            'downtime_state',
            start_time,
            end_time
        )

        def process_service_alerts():
            next_last_service_alert_cache = {}

            service_db_rows = []
            # don't consider alerts for any machine, they are added below

            for device_id, service_id, service_info in timespan_services:
                # need to find last state
                state_description_before = last_service_alert_cache.get((device_id, service_id, service_info), None)
                if not state_description_before:
                    state_description_before = mon_icinga_log_raw_base.STATE_UNDETERMINED, mon_icinga_log_raw_base.STATE_UNDETERMINED

                serv_key = (device_id, service_id, service_info)

                downtime_list = service_downtimes.get(serv_key, [])
                service_alerts[serv_key] = AlertList.add_downtimes_to_alerts(
                    service_alerts[serv_key],
                    state_description_before,
                    downtime_list=downtime_list
                )
                start_in_planned_downtime = bool(AlertList.get_downtime_entry(downtime_list, start_time))
                # state_description_before is always state without considering downtimes
                # (this is necessary to keep track of state before downtime)

                weighted_states, last_state_description = calc_weighted_states(
                    service_alerts[serv_key],
                    state_description_before,
                    start_in_planned_downtime=start_in_planned_downtime
                )
                next_last_service_alert_cache[(device_id, service_id, service_info)] = last_state_description

                flapping_ratio = calc_flapping_ratio(service_flapping_cache, (device_id, service_id, service_info))
                if flapping_ratio != 0.0:
                    weighted_states[
                        (
                            mon_icinga_log_aggregated_service_data.STATE_FLAPPING,
                            mon_icinga_log_aggregated_service_data.STATE_FLAPPING
                        )
                    ] = flapping_ratio

                for ((state, state_type), value) in weighted_states.items():
                    service_db_rows.append(
                        mon_icinga_log_aggregated_service_data(
                            state=state,
                            state_type=state_type,
                            value=value,
                            timespan=timespan_db,
                            device_id=device_id,
                            service_id=service_id,
                            service_info=service_info,
                        )
                    )

                essential_weighted_states = sum(
                    val for (state, state_type), val in weighted_states.items() if state != mon_icinga_log_aggregated_service_data.STATE_FLAPPING
                )
                if abs(essential_weighted_states - 1.0) > 0.01:
                    self.log(
                        "missing icinga log entries for device {} between {} and {} ({}), amounts sum to {}".format(
                            device_id,
                            start_time,
                            end_time,
                            duration_type.__name__,
                            essential_weighted_states
                        )
                    )
            mon_icinga_log_aggregated_service_data.objects.bulk_create(service_db_rows)
            return next_last_service_alert_cache

        def process_host_alerts():
            host_db_rows = []

            # for device_id in self._host_alert_keys_cache:
            for device_id in timespan_hosts:
                state_description_before = last_host_alert_cache.get(device_id, None)
                if not state_description_before:
                    state_description_before = mon_icinga_log_raw_base.STATE_UNDETERMINED, mon_icinga_log_raw_base.STATE_UNDETERMINED

                downtime_list = host_downtimes.get(device_id, [])
                host_alerts[device_id] = AlertList.add_downtimes_to_alerts(
                    host_alerts[device_id],
                    state_description_before,
                    downtime_list=downtime_list
                )
                start_in_planned_downtime = bool(AlertList.get_downtime_entry(downtime_list, start_time))

                weighted_states, last_state_description = calc_weighted_states(
                    host_alerts[device_id],
                    state_description_before,
                    start_in_planned_downtime=start_in_planned_downtime
                )
                flapping_ratio = calc_flapping_ratio(host_flapping_cache, device_id)
                if flapping_ratio != 0.0:
                    weighted_states[
                        (
                            mon_icinga_log_aggregated_host_data.STATE_FLAPPING,
                            mon_icinga_log_aggregated_host_data.STATE_FLAPPING
                        )
                    ] = flapping_ratio

                for ((state, state_type), value) in weighted_states.items():
                    host_db_rows.append(
                        mon_icinga_log_aggregated_host_data(
                            state=state,
                            state_type=state_type,
                            value=value,
                            timespan=timespan_db,
                            device_id=device_id,
                        )
                    )

                essential_weighted_states_sum = sum(
                    val for (state, state_type), val in weighted_states.items() if state != mon_icinga_log_aggregated_host_data.STATE_FLAPPING
                )
                if abs(essential_weighted_states_sum - 1.0) > 0.01:
                    self.log(
                        "missing icinga log entries for device {} between {} and {} ({}), amounts sum to {}".format(
                            device_id,
                            start_time,
                            end_time,
                            duration_type.__name__,
                            essential_weighted_states_sum
                        )
                    )

            mon_icinga_log_aggregated_host_data.objects.bulk_create(host_db_rows)

        next_last_service_alert_cache = process_service_alerts()
        process_host_alerts()

        return next_last_service_alert_cache

    def _create_timespan_entry_incrementally(self, timespan_db, start_time, end_time, duration_type,
                                             next_last_service_alert_cache):

        shorter_duration = duration.get_shorter_duration(duration_type)

        end_time_minus_epsilon = end_time - datetime.timedelta(seconds=1)

        def create_host_entries_incrementally():
            host_entries = []
            db_entries = mon_icinga_log_aggregated_host_data.objects.filter(
                timespan__duration_type=shorter_duration.ID,
                timespan__start_date__range=(start_time, end_time_minus_epsilon)
            )
            # check no of time spans:
            number_of_source_timespans = db_entries.distinct('timespan').count()
            # self.log("got {} values for host ".format(number_of_source_timespans))

            # dict for summing up
            data_sum = defaultdict(lambda: 0.0)
            # check how many timespan entries we have for each service (to detect added/removed services)
            data_timespans = defaultdict(lambda: set())
            for (timespan_id, device_id, state, state_type, value) in db_entries.values_list(
                "timespan_id", "device_id", "state", "state_type", "value"
            ):
                data_sum[device_id, state, state_type] += value
                data_timespans[device_id].add(timespan_id)

            for device_id, timespan_entries in data_timespans.items():
                for i in range(len(timespan_entries), number_of_source_timespans):
                    # add undetermined entry for each iteration here
                    data_sum[
                        device_id,
                        mon_icinga_log_raw_service_alert_data.STATE_UNDETERMINED,
                        mon_icinga_log_raw_service_alert_data.STATE_UNDETERMINED
                    ] += 1.0

            for ((device_id, state, state_type), value_sum) in data_sum.items():
                host_entries.append(
                    mon_icinga_log_aggregated_host_data(
                        state=state,
                        state_type=state_type,
                        value=value_sum / number_of_source_timespans,
                        timespan=timespan_db,
                        device_id=device_id,
                    )
                )
            mon_icinga_log_aggregated_host_data.objects.bulk_create(host_entries)

        def create_service_entries_incrementally():
            serv_entries = []
            db_entries = mon_icinga_log_aggregated_service_data.objects.filter(
                timespan__duration_type=shorter_duration.ID,
                timespan__start_date__range=(start_time, end_time_minus_epsilon)
            )
            number_of_source_timespans = db_entries.distinct('timespan').count()

            # dict for summing up
            data_sum = defaultdict(lambda: 0.0)
            # check how many timespan entries we have for each service (to detect added/removed services)
            data_timespans = defaultdict(lambda: set())
            for (
                timespan_id, device_id, service_id, service_info, state, state_type, value
            ) in db_entries.values_list(
                "timespan_id", "device_id", "service_id", "service_info",
                "state", "state_type", "value"
            ):
                data_sum[device_id, service_id, service_info, state, state_type] += value
                data_timespans[device_id, service_id, service_info].add(timespan_id)

            for (device_id, service_id, service_info), timespan_entries in data_timespans.items():
                for i in range(len(timespan_entries), number_of_source_timespans):
                    # add undetermined entry for each iteration here
                    data_sum[device_id, service_id, service_info,
                             mon_icinga_log_raw_service_alert_data.STATE_UNDETERMINED,
                             mon_icinga_log_raw_service_alert_data.STATE_UNDETERMINED] += 1.0

            for ((device_id, service_id, service_info, state, state_type), value_sum) in data_sum.items():
                serv_entries.append(
                    mon_icinga_log_aggregated_service_data(
                        state=state,
                        state_type=state_type,
                        value=value_sum / number_of_source_timespans,
                        timespan=timespan_db,
                        device_id=device_id,
                        service_id=service_id,
                        service_info=service_info,
                    )
                )
            mon_icinga_log_aggregated_service_data.objects.bulk_create(serv_entries)

        create_host_entries_incrementally()
        create_service_entries_incrementally()
