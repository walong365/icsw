# Copyright (C) 2015 Andreas Lang-Nevyjel, init.at
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
""" model definitions, internal stuff (database version, patch levels, ....) """

from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, signals
from django.dispatch import receiver
from enum import enum

from initat.cluster.backbone.models.functions import check_integer, check_empty_string

__all__ = [
    "ICSWVersion",
]


class ICSWVersion(models.Model):
    idx = models.AutoField(primary_key=True)
    name = models.CharField(
        max_length=63,
        choices=[
            ("database", "Database scheme"),
            ("software", "Software package version"),
            ("models", "Models version"),
        ]
    )
    version = models.CharField(max_length=128)
    date = models.DateTimeField(auto_now_add=True)
