# Copyright (C) 2015 init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw-server
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
# -*- coding: utf-8 -*-
#

""" model definitions for key performance indicators """

import datetime

import django.utils.timezone
from django.db import models

from initat.cluster.backbone.models.functions import duration
from initat.cluster.backbone.models.domain import category


__all__ = [
    "Kpi",
    "DataSourceTuple",
    "KpiDataSourceTuple",
    "KpiStoredResult",
]


class _KpiManager(models.Manager):
    @staticmethod
    def parse_kpi_time_range(time_range, time_range_parameter):
        def get_duration_class_start_end(duration_class, time_point):
            start = duration_class.get_time_frame_start(
                time_point
            )
            end = duration_class.get_end_time_for_start(start)
            return start, end

        start, end = None, None

        if time_range == 'none':
            pass
        elif time_range == 'yesterday':
            start, end = get_duration_class_start_end(
                duration.Day,
                django.utils.timezone.now() - datetime.timedelta(days=1),
            )
        elif time_range == 'last week':
            start, end = get_duration_class_start_end(
                duration.Week,
                django.utils.timezone.now() - datetime.timedelta(days=7),
            )
        elif time_range == 'last month':
            start, end = get_duration_class_start_end(
                duration.Month,
                django.utils.timezone.now().replace(day=1) - datetime.timedelta(days=1)
            )
        elif time_range == 'last year':
            start, end = get_duration_class_start_end(
                duration.Year,
                django.utils.timezone.now().replace(day=1, month=1) - datetime.timedelta(days=1)
            )
        elif time_range == 'last n days':
            start = duration.Day.get_time_frame_start(
                django.utils.timezone.now() - datetime.timedelta(days=time_range_parameter)
            )
            end = start + datetime.timedelta(days=time_range_parameter)

        return (start, end)


class Kpi(models.Model):
    objects = _KpiManager()
    idx = models.AutoField(primary_key=True)
    name = models.TextField(blank=False)

    date = models.DateTimeField(auto_now_add=True)

    formula = models.TextField(blank=True)

    enabled = models.BooleanField(default=True)

    # pretend as if all device/monitoring tuples were checked
    # TODO: implement in gui
    # uses_all_data = models.BooleanField(default=False)

    # 'last_week', 'yesterday', etc.
    time_range = models.TextField(blank=True, default='none')
    # parameter for 'last n days'
    time_range_parameter = models.IntegerField(default=0)

    gui_selected_categories = models.TextField(blank=True)  # json

    # if this is false, states like 'soft critical' is not interpreted as actually critical
    soft_states_as_hard_states = models.BooleanField(default=True)

    def set_result(self, result_str, date):
        try:
            self.kpistoredresult.result = result_str
            self.kpistoredresult.date = date
            self.kpistoredresult.save()
        except KpiStoredResult.DoesNotExist:
            KpiStoredResult(kpi=self, result=result_str, date=date).save()

    def has_historic_data(self):
        return self.time_range != 'none'

    def get_time_range(self):
        start, end = _KpiManager.parse_kpi_time_range(self.time_range, self.time_range_parameter)
        if start is None:
            raise RuntimeError("get_historic_data() called for kpi with no defined time range.")
        return start, end

    def __unicode__(self):
        return u"KPI {}".format(self.name)

    class Meta:
        ordering = ('idx', )  # rest view in order of creation
        verbose_name = "KPI"

    class CSW_Meta:
        fk_ignore_list = ["KpiDataSourceTuple", "KpiStoredResult"]
        permissions = (
            ("kpi", "define and access key performance indicators (kpis)", False),
        )


class DataSourceTuple(models.Model):
    idx = models.AutoField(primary_key=True)
    # we have to use the category class definition due to a strange Django-bug (ALN, 2016-05-16)
    device_category = models.ForeignKey(category, related_name="device_category")
    monitoring_category = models.ForeignKey(category, related_name="monitoring_category")

    def __repr__(self):
        return u"DataSourceTuple(dev_cat={}, mon_cat={})".format(
            self.device_category,
            self.monitoring_category,
        )

    __unicode__ = __repr__  # useful for force_text

    class Meta:
        abstract = True


class KpiDataSourceTuple(DataSourceTuple):
    # Relevant (dev_cat x mon_cat) for a kpi.
    # Specifies the data actually relevant for kpi calculation.
    kpi = models.ForeignKey(Kpi, null=True)

    def __repr__(self):
        return u"KpiDataSourceTuple(kpi={}, dev_cat={}, mon_cat={})".format(
            self.kpi,
            self.device_category,
            self.monitoring_category,
        )

    __unicode__ = __repr__  # useful for force_text

    class Meta:
        verbose_name = "KPI data sources"


class KpiStoredResult(models.Model):
    idx = models.AutoField(primary_key=True)
    kpi = models.OneToOneField(Kpi)
    date = models.DateTimeField()
    result = models.TextField(null=True)  # json
