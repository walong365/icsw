#
# Copyright (C) 2015-2016 Bernhard Mallinger, Andreas Lang-Nevyjel, init.at
#
# this file is part of icsw-server
#
# Send feedback to: <mallinger@init.at>, <lang-nevyjel@init.at>
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
from collections import defaultdict

import dateutil.relativedelta
import dateutil.rrule
import django.utils.timezone
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Avg
from django.db.models import signals
from django.dispatch import receiver
from enum import IntEnum

from initat.cluster.backbone.models.functions import memoize_with_expiry
from .functions import check_integer


__all__ = [
    "DispatcherSettingSchedule",
    "DispatcherSettingScheduleEnum",
    "DispatcherSetting",
    "DispatchSetting",
    "DiscoverySource",
    "ScanHistory",
]


class DiscoverySource(IntEnum):
    SNMP = 1
    ASU = 2
    IPMI = 3

    def get_maximal_concurrent_runs(self):
        # TODO: move to database?
        if self == DiscoverySource.ASU:
            return 1
        else:
            return 5


class DispatcherSettingScheduleEnum(IntEnum):
    year = dateutil.rrule.YEARLY
    month = dateutil.rrule.MONTHLY
    week = dateutil.rrule.WEEKLY
    day = dateutil.rrule.DAILY
    hour = dateutil.rrule.HOURLY
    minute = dateutil.rrule.MINUTELY
    second = dateutil.rrule.SECONDLY


class DispatcherSettingSchedule(models.Model):
    idx = models.AutoField(primary_key=True)
    # name
    name = models.CharField(unique=True, default="", max_length=64)
    # baseline
    baseline = models.IntegerField(choices=[(rr.value, rr.name) for rr in DispatcherSettingScheduleEnum])
    # creation date
    date = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return "Schedule {}".format(self.name)


class DispatcherSetting(models.Model):
    idx = models.AutoField(primary_key=True)
    # name
    name = models.CharField(unique=True, default="", max_length=64)
    # description
    description = models.CharField(default="", blank=True, max_length=256)
    # is system (== undeleteable) setting
    is_system = models.BooleanField(default=False)
    # create user or null
    user = models.ForeignKey("backbone.user", null=True)
    # which ComCaps to use, use all when not set and is_system
    com_capabilities = models.ManyToManyField("backbone.ComCapability", blank=True)
    # schedule settings
    run_schedule = models.ForeignKey("backbone.DispatcherSettingSchedule")
    # multiplicator for run_schedule, must be greater than 0
    mult = models.IntegerField(default=1)
    # with second to run minutely, hourly, daily, weekly and so on schedules
    sched_start_second = models.IntegerField(default=None, null=True)
    # with minute to run hourly, daily, weekly and so on schedules
    sched_start_minute = models.IntegerField(default=None, null=True)
    sched_start_hour = models.IntegerField(default=None, null=True)
    # 0 is sunday, 1 is monday, 6 is saturday
    sched_start_day = models.IntegerField(default=None, null=True)
    # which week to run yearly and monthly schedules
    # 1 is the first week of the year
    sched_start_week = models.IntegerField(default=None, null=True)
    # which month to run yearly schedules
    # 1 is january
    sched_start_month = models.IntegerField(default=None, null=True)
    # creation date
    date = models.DateTimeField(auto_now_add=True)


@receiver(signals.pre_save, sender=DispatcherSetting)
def DispatcherSettingPreSave(sender, **kwargs):
    if "instance" in kwargs:
        _cur_inst = kwargs["instance"]
        check_integer(_cur_inst, "mult", min_val=1, max_val=365)
        if not _cur_inst.is_system:
            if not _cur_inst.user:
                raise ValidationError("Need user for non-system schedule")
        _sched = _cur_inst.run_schedule.name
        _check = _sched == "year"
        for _name, _min, _max in [
            # ordering is important
            ("month", 1, 12),
            ("week", 1, 53),
            ("day", 0, 6),
            ("hour", 0, 23),
            ("minute", 0, 59),
            ("second", 0, 59),
        ]:
            _attr_name = "sched_start_{}".format(_name)
            _val = getattr(_cur_inst, _attr_name)
            if _check:
                if _val is None:
                    _val = _min
                    setattr(_cur_inst, _attr_name, _val)
                check_integer(_cur_inst, _attr_name, min_val=_min, max_val=_max)
            # print _check, _name, _val, _sched
            if _name == _sched:
                _check = True
            # if _val is not None:
        print _cur_inst.sched_start_second


class DispatchSetting(models.Model):
    # device relative setting, will be replaced
    class DurationUnits(IntEnum):
        # as understood by dateutil.relativedelta
        months = 1
        weeks = 2
        days = 3
        hours = 4
        minutes = 5

    idx = models.AutoField(primary_key=True)
    date = models.DateTimeField(auto_now_add=True)

    device = models.ForeignKey("backbone.device")
    source = models.IntegerField(choices=[(src.value, src.name) for src in DiscoverySource])

    # interval for executions. a run is scheduled exactly this duration after the last start (but it may be delayed)
    duration_amount = models.IntegerField(default=1)
    duration_unit = models.IntegerField(choices=[(u.value, u.name) for u in DurationUnits])

    run_now = models.BooleanField(default=False)

    # TODO: probably needs enabled flag

    def get_source_enum_instance(self):
        return DiscoverySource(self.source)

    def get_interval_as_delta(self):
        return dateutil.relativedelta.relativedelta(**{self.DurationUnits(self.duration_unit).name: self.duration_amount})


class _ScanHistoryManager(models.Manager):
    def get_average_run_duration(self, source, device):
        default = dateutil.relativedelta.relativedelta(minutes=1)  # TODO: source-dependent default?
        return self.__get_run_duration_cache().get(source, {}).get(device.pk, default)

    @memoize_with_expiry(10)
    def __get_run_duration_cache(self):
        cache = defaultdict(lambda: {})
        for entry in self.values("source", "device_id").annotate(avg_duration=Avg("duration")):
            cache[entry['source']][entry['device_id']] = dateutil.relativedelta.relativedelta(
                seconds=entry['avg_duration']
            )
        return cache


class ScanHistory(models.Model):
    objects = _ScanHistoryManager()
    idx = models.AutoField(primary_key=True)
    date = models.DateTimeField(default=django.utils.timezone.now)  # auto_add_now breaks factory boy

    device = models.ForeignKey("backbone.device")
    source = models.IntegerField(choices=[(src.value, src.name) for src in DiscoverySource])

    duration = models.IntegerField()  # seconds

    success = models.BooleanField(default=True)
