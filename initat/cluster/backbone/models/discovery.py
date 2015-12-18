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
from collections import defaultdict
import dateutil.relativedelta
import django.utils.timezone

from django.db import models
from django.db.models import Avg
from enum import IntEnum
from initat.cluster.backbone.models.functions import memoize_with_expiry


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


class DispatchSetting(models.Model):
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
            cache[entry['source']][entry['device_id']] =\
                dateutil.relativedelta.relativedelta(seconds=entry['avg_duration'])
        return cache


class ScanHistory(models.Model):
    objects = _ScanHistoryManager()
    idx = models.AutoField(primary_key=True)
    date = models.DateTimeField(default=django.utils.timezone.now)  # auto_add_now breaks factory boy

    device = models.ForeignKey("backbone.device")
    source = models.IntegerField(choices=[(src.value, src.name) for src in DiscoverySource])

    duration = models.IntegerField()  # seconds

    success = models.BooleanField(default=True)
