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
from dateutil.relativedelta import relativedelta
from collections import defaultdict
import operator

from initat.cluster.backbone.models.discovery import DispatchSetting, ScanHistory


class ScheduleItem(object):
    def __init__(self, device, source, planned_date, dispatch_setting):
        # date always means datetime
        self.device = device
        self.source = source
        self.planned_date = planned_date  # date according to interval
        self.dispatch_setting = dispatch_setting

        self.expected_run_date = None  # date considering other jobs
        self.expected_finish_date = None

    def set_expected_dates(self, expected_run_date, expected_finish_date):
        self.expected_run_date = expected_run_date
        self.expected_finish_date = expected_finish_date


class DiscoveryDispatcher(object):
    def __init__(self):
        pass

    def calculate(self, start, end):
        # consider constraints

        # - at most one concurrent scan by device

        # - at most n concurrent scans by source

        # - run_now

        naive_run_list = self.get_next_planned_run_times(start, end)
        # sort prio: run_now, date, device_pk (to make sort somewhat stable)
        naive_run_list.sort(key=lambda entry: (not entry.dispatch_setting.run_now, entry.planned_date, entry.device.pk))

        sched_info = _ScheduleInfo()

        for item in naive_run_list:
            expected_run_date = item.planned_date

            # we can run as soon as source limit is fulfilled
            n_th_last_by_src = sched_info.items_by_source[item.source][- item.source.get_maximal_concurrent_runs()]
            expected_run_date = max(expected_run_date, n_th_last_by_src.expected_finish_date)

            # device constraint (only one by device
            last_by_device = sched_info.items_by_device[item.device][-1]
            expected_run_date = max(expected_run_date, last_by_device.expected_finish_date)

            item.expected_run_date = expected_run_date
            item.expected_finish_date =\
                expected_run_date + ScanHistory.objects.get_average_run_duration(item.source, item.device)

            sched_info.add_item(item)

    def get_next_planned_run_times(self, start, end):
        """Returns planned run times without considering any constraints"""
        if end < start:
            raise ValueError()
        run_list = []
        for dispatch_setting in DispatchSetting.objects.all():
            try:
                last_run = ScanHistory.objects.get(device=dispatch_setting.device, source=dispatch_setting.source)
            except ScanHistory.DoesNotExist:
                planned_date = start
            else:
                if last_run.successful:
                    interval = dispatch_setting.interval
                    planned_date = last_run.date + relativedelta(**{interval.unit: interval.amount})
                else:
                    # last run failed, rerun earlier:
                    planned_date = max(last_run.date + relativedelta(hours=4), start)

            while planned_date < end:
                run_list.append(
                    ScheduleItem(
                        device=dispatch_setting.device,
                        source=dispatch_setting.source,
                        planned_date=planned_date,
                        dispatch_setting=dispatch_setting,
                    )
                )
                planned_date += relativedelta(**{interval.unit: interval.amount})

        return run_list


class _ScheduleInfo(object):
    """
    keeps items lists sorted by expected finish date
    """
    def __init__(self):
        self.items_by_device = defaultdict(lambda: [])
        self.items_by_source = defaultdict(lambda: [])

    def add_item(self, item):
        # TODO: insertion sort?
        self.items_by_device[item.device].append(item)
        self.items_by_device[item.device].sort(key=operator.attrgetter("expected_finish_date"))

        self.items_by_source[item.source].append(item)
        self.items_by_source[item.source].sort(key=operator.attrgetter("expected_finish_date"))
