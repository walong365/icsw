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

from initat.cluster.backbone.models.discovery import DispatchSetting, ScanHistory


class ScheduleItem(object):
    def __init__(self, device, source, planned_date, dispatch_setting):
        self.device = device
        self.source = source
        self.planned_date = planned_date  # date according to interval
        self.dispatch_setting = dispatch_setting
        self.expected_date = None  # date considering other jobs
        self.dependent_on_items = []


class DiscoveryDispatcher(object):
    def __init__(self):
        pass

    def calculate(self, start, end):
        # consider constraints

        # - at most one concurrent scan by device

        # - at most n concurrent scans by source

        # - run_now

        run_list = self.get_next_planned_run_times(start, end)
        # sort prio: run_now, date, device_pk (to make sort somewhat stable)
        run_list.sort(key=lambda item: (not item.dispatch_setting.run_now, item.planned_date, item.device.pk))

        items_by_device = defaultdict(lambda: [])
        items_by_source = defaultdict(lambda: [])

        for item in run_list:

            dependent_on = set(
                self.get_up_to_nth_last(items_by_source[item.source], item.source.get_maximal_concurrent_runs())
            )
            last_item_on_device = items_by_device.get(item.device)
            if last_item_on_device:
                dependent_on.add(items_by_device)

            item.dependent_on_items = list(dependent_on)

            items_by_device[item.device].append(item)
            items_by_source[item.source].append(item)

    def get_next_planned_run_times(self, start, end):
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

    @staticmethod
    def get_up_to_nth_last(l, n):
        return l[:len(l) - n - 1]
