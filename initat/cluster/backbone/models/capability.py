# Copyright (C) 2015 Andreas Lang-Nevyjel, init.at
#
# this file is part of cluster-backbone-sql
#
# Send feedback to: <lang-nevyjel@init.at>
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
""" database definitions for monitoring """

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, signals, Max, Min
from django.dispatch import receiver
from initat.cluster.backbone.available_licenses import LicenseEnum, LicenseParameterTypeEnum
from initat.cluster.backbone.models.functions import _check_empty_string, _check_integer
from collections import defaultdict
import json
from initat.cluster.backbone.models.license import LicenseUsage
from initat.tools import logging_tools
import re
import operator

__all__ = [
    "snmp_scheme_vendor",
    "snmp_scheme",
    "snmp_scheme_tl_oid",
]


class snmp_scheme_vendor(models.Model):
    idx = models.AutoField(primary_key=True)
    # name
    name = models.CharField(max_length=128, unique=True)
    # info (full name of company)
    company_info = models.CharField(max_length=256, default="")
    date = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return "snmp_scheme_vendor {}".format(self.name)

    class Meta:
        app_label = "backbone"


class snmp_scheme(models.Model):
    idx = models.AutoField(primary_key=True)
    # vendor
    snmp_scheme_vendor = models.ForeignKey("backbone.snmp_scheme_vendor")
    # name
    name = models.CharField(max_length=128, unique=True)
    # description
    description = models.CharField(max_length=128, default="")
    # version
    version = models.IntegerField(default=1)
    # used for collectd calls
    collect = models.BooleanField(default=False)
    # when found make an initial lookup call
    initial = models.BooleanField(default=False)
    # moncheck
    mon_check = models.BooleanField(default=False)
    # power_control
    power_control = models.BooleanField(default=False)
    # priority for handling, schemes with higher priority will be handled first
    priority = models.IntegerField(default=0)
    date = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return "snmp_scheme {}".format(self.name)

    @property
    def full_name(self):
        return "{}.{}".format(
            self.snmp_scheme_vendor.name,
            self.name,
        )

    @property
    def full_name_version(self):
        return "{}_v{:d}".format(
            self.full_name,
            self.version,
        )

    class Meta:
        app_label = "backbone"


class snmp_scheme_tl_oid(models.Model):
    idx = models.AutoField(primary_key=True)
    snmp_scheme = models.ForeignKey("backbone.snmp_scheme")
    oid = models.CharField(default="", max_length=255)
    # is this oid optional ?
    optional = models.BooleanField(default=False)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "backbone"


class capability(models.Model):
    idx = models.AutoField(primary_key=True)
    # short name
    name = models.CharField(max_length=16, unique=True)
    # info
    info = models.CharField(max_length=64, unique=True)
    # port spec
    port_spec = models.CharField(max_length=256, default="")
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "backbone"
