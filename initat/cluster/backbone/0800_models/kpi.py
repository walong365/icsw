# Copyright (C) 2015 init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of cluster-backbone-sql
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


from django.db import models
from django.db.models import Q, signals
import logging_tools


__all__ = [
    "kpi",
    "kpi_selected_device_monitoring_category_tuple",
]


class kpi(models.Model):
    idx = models.AutoField(primary_key=True)
    name = models.TextField(blank=False)
    available_device_categories = models.ManyToManyField('category', related_name="available_device_category")
    available_monitoring_categories = models.ManyToManyField('category', related_name="available_monitoring_category")

    class Meta:
        app_label = "backbone"


class kpi_selected_device_monitoring_category_tuple(models.Model):
    # Relevant (dev_cat x mon_cat) for a kpi.
    # Specifies the data actually relevant for kpi calculation.
    idx = models.AutoField(primary_key=True)
    kpi = models.ForeignKey(kpi)
    device_category = models.ForeignKey('category', related_name="device_cateogory")
    monitoring_category = models.ForeignKey('category', related_name="monitoring_category")

    class Meta:
        app_label = "backbone"
