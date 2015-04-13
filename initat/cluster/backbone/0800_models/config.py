# Copyright (C) 2001-2014 Andreas Lang-Nevyjel, init.at
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
""" model definitions, partitions """

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, signals
from django.apps import apps
from django.dispatch import receiver

__all__ = [
    "config_catalog",
    "config",
    "config_str",
    "config_int",
    "config_blob",
    "config_bool",
    "config_script",
]


class config_catalog(models.Model):
    idx = models.AutoField(primary_key=True)
    # MySQL restriction
    name = models.CharField(max_length=254, unique=True, blank=False, null=False)
    url = models.URLField(max_length=256, default="", blank=True)
    author = models.CharField(max_length=256, default="", blank=True)
    # gets increased by one on every download
    version = models.IntegerField(default=1)
    # extraction time
    extraction_time = models.DateTimeField(null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return self.name


class config(models.Model):
    idx = models.AutoField(db_column="new_config_idx", primary_key=True)
    name = models.CharField(max_length=192, blank=False)
    config_catalog = models.ForeignKey(config_catalog, null=True)
    description = models.CharField(max_length=765, default="", blank=True)
    priority = models.IntegerField(null=True, default=0)
    # valid for servers (activate special functionalities)
    server_config = models.BooleanField(default=False)
    # system config, not user generated
    system_config = models.BooleanField(default=False)
    # config_type = models.ForeignKey("config_type", db_column="new_config_type_id")
    # can not be used for server configs
    parent_config = models.ForeignKey("config", null=True, blank=True)
    enabled = models.BooleanField(default=True)
    date = models.DateTimeField(auto_now_add=True)
    # categories for this config
    categories = models.ManyToManyField("backbone.category")

    class Meta:
        db_table = u'new_config'
        ordering = ["name", "config_catalog__name"]
        unique_together = (("name", "config_catalog"),)


class config_str(models.Model):
    idx = models.AutoField(db_column="config_str_idx", primary_key=True)
    name = models.CharField(max_length=192)
    description = models.CharField(db_column="descr", max_length=765)
    config_old = models.IntegerField(null=True, blank=True, db_column="config")
    config = models.ForeignKey("config", db_column="new_config_id")
    value = models.TextField(blank=True)
    device = models.ForeignKey("device", null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = u'config_str'
        ordering = ("name",)


class config_blob(models.Model):
    idx = models.AutoField(db_column="config_blob_idx", primary_key=True)
    name = models.CharField(max_length=192)
    description = models.CharField(max_length=765, db_column="descr")
    # deprecated
    config_old = models.IntegerField(null=True, blank=True, db_column="config")
    config = models.ForeignKey("config", db_column="new_config_id")
    value = models.TextField(blank=True)
    device = models.ForeignKey("device", null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = u'config_blob'


class config_bool(models.Model):
    idx = models.AutoField(db_column="config_bool_idx", primary_key=True)
    name = models.CharField(max_length=192)
    description = models.CharField(max_length=765, db_column="descr")
    # deprecated
    config_old = models.IntegerField(null=True, blank=True, db_column="config")
    config = models.ForeignKey("config", db_column="new_config_id")
    value = models.IntegerField(null=True, blank=True)
    device = models.ForeignKey("device", null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = u'config_bool'


class config_int(models.Model):
    idx = models.AutoField(db_column="config_int_idx", primary_key=True)
    name = models.CharField(max_length=192)
    description = models.CharField(max_length=765, db_column="descr")
    # deprecated
    config_old = models.IntegerField(null=True, blank=True, db_column="config")
    config = models.ForeignKey("config", db_column="new_config_id")
    value = models.IntegerField(null=True, blank=True)
    device = models.ForeignKey("device", null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = u'config_int'


class config_script(models.Model):
    idx = models.AutoField(db_column="config_script_idx", primary_key=True)
    name = models.CharField(max_length=192)
    description = models.CharField(max_length=765, db_column="descr")
    enabled = models.BooleanField(default=True)
    priority = models.IntegerField(null=True, blank=True, default=0)
    config = models.ForeignKey("config", db_column="new_config_id")
    value = models.TextField(blank=True)
    # to be removed
    error_text = models.TextField(blank=True, default="")
    device = models.ForeignKey("device", null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = u'config_script'
        ordering = ("priority", "name",)

