#!/usr/bin/python-init -Ot
#
# Copyright (C) 2015 Bernhard Mallinger, init.at
#
# this file is part of icsw-server
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
import operator
from collections import defaultdict

from initat.cluster.backbone.models.discovery import DispatchSetting, ScanHistory


class DiscoveryDispatcher(object):
    def __init__(self):
        pass

    def calculate(self, start, end):
        """
        Main method. Returns list of scheduled DispatchSettings where scheduled start is in [start, end)
        :rtype: list of _ScheduleItem
        """

        # generate list which would work in an ideal world with infinite resources and no conflicts
        naive_run_list = self._get_next_planned_run_times(start, end)

        # print 'naive'
        # pprint.pprint(naive_run_list)

        # sort according to priority (run_now) and planned date
        presorted_list = self._presort_list(naive_run_list)

        # print 'presort'
        # pprint.pprint(presorted_list)

        # delay according to constraints
        run_list = self._handle_constraints(presorted_list, end=end)

        # print 'run list'
        # pprint.pprint(run_list)

        return run_list

    def _get_next_planned_run_times(self, start, end):
        """Returns planned run times without considering any constraints
        :rtype: list of _ScheduleItem
        """
        if end < start:
            raise ValueError()
        run_list = []
        for dispatch_setting in DispatchSetting.objects.all():
            _qs = ScanHistory.objects.filter(device=dispatch_setting.device, source=dispatch_setting.source)
            try:
                last_run = _qs.latest('date')
            except ScanHistory.DoesNotExist:
                planned_date = start
            else:
                if dispatch_setting.run_now:
                    # priority, run soon
                    planned_date = start
                else:
                    # last run worked, this is the regular case
                    interval = dispatch_setting.get_interval_as_delta()
                    if not last_run.success:
                        # last run failed, rerun earlier (cut interval):
                        interval /= 10

                    planned_date = max(last_run.date + interval, start)

            while planned_date < end:
                run_list.append(
                    _ScheduleItem(
                        device=dispatch_setting.device,
                        source=dispatch_setting.get_source_enum_instance(),
                        planned_date=planned_date,
                        dispatch_setting=dispatch_setting,
                    )
                )

                planned_date += dispatch_setting.get_interval_as_delta()

        return run_list

    def _presort_list(self, naive_run_list):
        """sort according to run_now and planned_date
        :rtype: list of _ScheduleItem
        """
        # for each dispatch setting with run_now flag, add first entry here
        run_now_list = []
        regular_list = []
        dispatch_settings_in_run_now_list = set()
        for item in naive_run_list:
            if item.dispatch_setting.run_now and item.dispatch_setting not in dispatch_settings_in_run_now_list:
                dispatch_settings_in_run_now_list.add(item.dispatch_setting)
                run_now_list.append(item)
            else:
                regular_list.append(item)

        # sort prio: run_now, date, device_pk (to make sort somewhat stable)
        run_now_list.sort(key=lambda entry: (entry.planned_date, entry.device.pk))
        regular_list.sort(key=lambda entry: (entry.planned_date, entry.device.pk))
        return run_now_list + regular_list

    def _handle_constraints(self, presorted_list, end):
        """
        :rtype: list of _ScheduleItem
        """
        sched_info = _ScheduleInfo()
        for item in presorted_list:
            expected_run_date = item.planned_date

            # we can run as soon as source limit is fulfilled
            max_concurrent_runs = item.source.get_maximal_concurrent_runs()
            if len(sched_info.items_by_source[item.source]) >= max_concurrent_runs:
                # queue is full
                n_th_last_by_src = sched_info.items_by_source[item.source][-item.source.get_maximal_concurrent_runs()]
                expected_run_date = max(expected_run_date, n_th_last_by_src.expected_finish_date)

            # device constraint (only one by device)
            if sched_info.items_by_device[item.device]:
                last_by_device = sched_info.items_by_device[item.device][-1]
                expected_run_date = max(expected_run_date, last_by_device.expected_finish_date)

            # make sure that we are not running faster than the interval for this dispatch setting
            if sched_info.items_by_dispatch_setting[item.dispatch_setting]:
                last_by_dispatch_setting = sched_info.items_by_dispatch_setting[item.dispatch_setting][-1]
                expected_run_date = max(
                    expected_run_date,
                    last_by_dispatch_setting.expected_run_date + item.dispatch_setting.get_interval_as_delta()
                )

            item.set_expected_dates(
                expected_run_date,
                expected_run_date + ScanHistory.objects.get_average_run_duration(item.source, item.device),
            )

            sched_info.add_item(item)

        list_cut_off = (item for item in presorted_list if item.expected_run_date < end)

        return sorted(list_cut_off, key=operator.attrgetter('expected_run_date'))


class _ScheduleItem(object):
    def __init__(self, device, source, planned_date, dispatch_setting):
        """
        :type dispatch_setting: DispatchSetting
        """
        # date always means datetime
        self.device = device
        self.source = source
        self.planned_date = planned_date  # naive date according to interval
        self.dispatch_setting = dispatch_setting

        self.expected_run_date = None  # date considering other jobs
        self.expected_finish_date = None

    def set_expected_dates(self, expected_run_date, expected_finish_date):
        self.expected_run_date = expected_run_date
        self.expected_finish_date = expected_finish_date

    def __repr__(self):
        return "ScheduleItem(dev={}, src={}, planned={}, expected_run={}, expected_finish={})".format(
            self.device, self.source, self.planned_date, self.expected_run_date, self.expected_finish_date
        )


class _ScheduleInfo(object):
    """
    keeps items lists sorted by expected finish date
    """
    def __init__(self):
        self.items_by_device = defaultdict(lambda: [])
        self.items_by_source = defaultdict(lambda: [])
        self.items_by_dispatch_setting = defaultdict(lambda: [])

    def add_item(self, item):
        # TODO: insertion sort?
        self.items_by_device[item.device].append(item)
        self.items_by_device[item.device].sort(key=operator.attrgetter("expected_finish_date"))

        self.items_by_source[item.source].append(item)
        self.items_by_source[item.source].sort(key=operator.attrgetter("expected_finish_date"))

        self.items_by_dispatch_setting[item.dispatch_setting].append(item)
        self.items_by_dispatch_setting[item.dispatch_setting].sort(key=operator.attrgetter("expected_finish_date"))
