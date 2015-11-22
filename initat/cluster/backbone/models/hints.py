# Copyright (C) 2014-2015 Andreas Lang-Nevyjel, init.at
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
""" database definitions for hints """

from django.db import models

__all__ = [
    "config_hint",
    "config_var_hint",
    "config_script_hint",
]


class config_hint(models.Model):
    idx = models.AutoField(primary_key=True)
    # config
    config_name = models.CharField(max_length=192, blank=False, unique=True)
    config_description = models.CharField(max_length=192, default="")
    valid_for_meta = models.BooleanField(default=True)
    exact_match = models.BooleanField(default=True)
    # short and long help text
    help_text_short = models.TextField(default="")
    help_text_html = models.TextField(default="")
    date = models.DateTimeField(auto_now_add=True)


class config_var_hint(models.Model):
    idx = models.AutoField(primary_key=True)
    # config hint
    config_hint = models.ForeignKey("backbone.config_hint")
    var_name = models.CharField(max_length=192, default="")
    # short and long help text
    help_text_short = models.TextField(default="")
    help_text_html = models.TextField(default="")
    # should the var be created automatically ?
    ac_flag = models.BooleanField(default=False)
    ac_type = models.CharField(
        default="str",
        max_length=64,
        choices=[
            ("str", "string var"),
            ("int", "int var"),
            ("bool", "bool var")
        ]
    )
    ac_description = models.CharField(default="description", max_length=128)
    # will be casted to int, bool
    ac_value = models.TextField(default="")
    date = models.DateTimeField(auto_now_add=True)


class config_script_hint(models.Model):
    idx = models.AutoField(primary_key=True)
    # config hint
    config_hint = models.ForeignKey("backbone.config_hint")
    script_name = models.CharField(max_length=192, default="")
    # short and long help text
    help_text_short = models.TextField(default="")
    help_text_html = models.TextField(default="")
    # should the var be created automatically ?
    ac_flag = models.BooleanField(default=False)
    ac_description = models.CharField(default="description", max_length=128)
    # will be casted to int, bool
    ac_value = models.TextField(default="")
    date = models.DateTimeField(auto_now_add=True)
