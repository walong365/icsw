# -*- coding: utf-8 -*-
#
# Copyright (C) 2016 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FTNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
""" creates fixtures for dispatcher """


from initat.cluster.backbone import factories
from initat.cluster.backbone.models import DispatcherSettingScheduleEnum
import dateutil.rrule


def add_fixtures(**kwargs):
    disp_dict = {}
    for disp in DispatcherSettingScheduleEnum:
        disp_dict[disp.value] = factories.DispatcherSettingScheduleFactory(
            name=disp.name,
            baseline=disp.value,
        )
    # create system settings
    _once_per_hour = factories.DispatcherSettingFactory(
        name="once_per_hour",
        description="run once per hour",
        is_system=True,
        run_schedule=disp_dict[DispatcherSettingScheduleEnum.hour],
        sched_start_second=0,
        sched_start_minute=15,
    )
    _once_per_day = factories.DispatcherSettingFactory(
        name="once_per_day",
        description="run once per day",
        is_system=True,
        run_schedule=disp_dict[DispatcherSettingScheduleEnum.day],
        sched_start_second=0,
        sched_start_minute=15,
        sched_start_hour=6,
    )
    _once_per_week = factories.DispatcherSettingFactory(
        name="once_per_week",
        description="run once per week",
        is_system=True,
        run_schedule=disp_dict[DispatcherSettingScheduleEnum.week],
        sched_start_second=0,
        sched_start_minute=15,
        sched_start_hour=6,
        sched_start_day=1,
    )
