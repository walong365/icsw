# Copyright (C) 2013-2014 Andreas Lang-Nevyjel, init.at
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
""" database definitions for RMS """

# from django.db.models import Q, signals, get_model
# from django.dispatch import receiver
from django.db import models
import datetime
import time

__all__ = [
    "rms_job",
    "rms_job_run",
    "rms_pe_info",
    "rms_project",
    "rms_department",
    "rms_queue",
    "rms_pe",
    "ext_license_site",
    "ext_license",
    "ext_license_version",
    "ext_license_vendor",
    "ext_license_user",
    "ext_license_client",
    "ext_license_client_version",
    "ext_license_check",
    "ext_license_state",
    "ext_license_version_state",
    "ext_license_usage",
    "ext_license_check_coarse",
    "ext_license_version_state_coarse",
    "ext_license_state_coarse",
    "ext_license_usage_coarse",
]


class rms_project(models.Model):
    idx = models.AutoField(primary_key=True)
    name = models.CharField(unique=True, max_length=255)
    # oticket = models.FloatField(null=True, blank=True)
    # fshare = models.FloatField(null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "backbone"


class rms_department(models.Model):
    idx = models.AutoField(primary_key=True)
    name = models.CharField(unique=True, max_length=255)
    # oticket = models.FloatField(null=True, blank=True)
    # fshare = models.FloatField(null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "backbone"


class rms_queue(models.Model):
    idx = models.AutoField(primary_key=True)
    name = models.CharField(unique=True, max_length=255)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "backbone"


class rms_pe(models.Model):
    idx = models.AutoField(primary_key=True)
    name = models.CharField(unique=True, max_length=255)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "backbone"


class rms_job(models.Model):
    idx = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    # id of job
    jobid = models.IntegerField()
    taskid = models.IntegerField(null=True)
    owner = models.CharField(max_length=255, default="")
    user = models.ForeignKey("backbone.user", null=True)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "backbone"


class rms_job_run(models.Model):
    idx = models.AutoField(primary_key=True)
    rms_job = models.ForeignKey(rms_job)
    # device, from hostname via qacct
    device = models.ForeignKey("backbone.device", null=True)
    rms_pe = models.ForeignKey("backbone.rms_pe", null=True)
    hostname = models.CharField(max_length=255)
    # from qacct
    rms_project = models.ForeignKey("backbone.rms_project", null=True)
    rms_department = models.ForeignKey("backbone.rms_department", null=True)
    granted_pe = models.CharField(max_length=192, default="")
    slots = models.IntegerField(null=True)
    priority = models.IntegerField(default=0)
    account = models.CharField(max_length=384, default="")
    failed = models.IntegerField(default=0)
    failed_str = models.CharField(max_length=255, default="")
    exit_status = models.IntegerField(default=0)
    exit_status_str = models.CharField(max_length=255, default="")
    queue_time = models.DateTimeField(null=True)
    # via qname
    rms_queue = models.ForeignKey("backbone.rms_queue")
    start_time = models.DateTimeField(null=True)
    end_time = models.DateTimeField(null=True)
    # end data from qacct
    start_time_py = models.DateTimeField(null=True)
    end_time_py = models.DateTimeField(null=True)
    # data set via qacct ?
    qacct_called = models.BooleanField(default=False)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "backbone"


class rms_pe_info(models.Model):
    idx = models.AutoField(primary_key=True)
    rms_job_run = models.ForeignKey(rms_job_run)
    device = models.ForeignKey("backbone.device", null=True)
    hostname = models.CharField(max_length=255)
    slots = models.IntegerField(default=0)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "backbone"


# license models
# TODO: track cluster / external license usage
class ext_license_base(models.Model):
    idx = models.AutoField(primary_key=True)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
        app_label = "backbone"


class ext_license_site(ext_license_base):
    name = models.CharField(max_length=128, unique=True)


class ext_license(ext_license_base):
    name = models.CharField(max_length=128, unique=True)
    ext_license_site = models.ForeignKey("backbone.ext_license_site")


class ext_license_version(ext_license_base):
    '''
    License version as reported by server (different from what is used and reported by client.)
    This is probably the import one.
    '''
    ext_license = models.ForeignKey("backbone.ext_license")
    version = models.CharField(max_length=64, default="")


class ext_license_vendor(ext_license_base):
    name = models.CharField(max_length=64, default="", unique=True)


class ext_license_client(ext_license_base):
    long_name = models.CharField(max_length=256, default="")
    short_name = models.CharField(max_length=128, default="")
    device = models.ForeignKey("backbone.device", null=True, on_delete=models.SET_NULL)


class ext_license_user(ext_license_base):
    name = models.CharField(max_length=256, default="")
    user = models.ForeignKey("backbone.user", null=True, on_delete=models.SET_NULL)


class ext_license_check(ext_license_base):
    ext_license_site = models.ForeignKey("backbone.ext_license_site", null=True)
    run_time = models.FloatField(default=0.0)

    class CSW_Meta:
        backup = False


class ext_license_state(models.Model):
    idx = models.AutoField(primary_key=True)
    ext_license_check = models.ForeignKey("backbone.ext_license_check")
    ext_license = models.ForeignKey("backbone.ext_license")
    used = models.IntegerField(default=0)
    reserved = models.IntegerField(default=0)
    free = models.IntegerField(default=0)
    issued = models.IntegerField(default=0)

    class Meta:
        app_label = "backbone"


class ext_license_version_state(models.Model):
    idx = models.AutoField(primary_key=True)
    ext_license_check = models.ForeignKey("backbone.ext_license_check")
    ext_license_version = models.ForeignKey("backbone.ext_license_version")
    ext_license_state = models.ForeignKey("backbone.ext_license_state")
    is_floating = models.BooleanField(default=False)
    vendor = models.ForeignKey("backbone.ext_license_vendor")

    class Meta:
        app_label = "backbone"


class ext_license_client_version(ext_license_base):
    '''
    License version as reported by client (different from what is used and reported by server.)
    '''
    ext_license = models.ForeignKey("backbone.ext_license")
    client_version = models.CharField(default="", max_length=64)


class ext_license_usage(models.Model):
    idx = models.AutoField(primary_key=True)
    ext_license_version_state = models.ForeignKey("backbone.ext_license_version_state")
    ext_license_client = models.ForeignKey("backbone.ext_license_client")
    ext_license_user = models.ForeignKey("backbone.ext_license_user")
    ext_license_client_version = models.ForeignKey("backbone.ext_license_client_version", null=True)
    checkout_time = models.IntegerField(default=0)
    num = models.IntegerField(default=0)  # number of licenses of a single instance of a program

    class Meta:
        app_label = "backbone"


'''
The models above are too fine-grained for fast access, so we use the ones
below for displaying them. Here, the data is aggregated using dynamic durations.
'''


class ext_license_check_coarse(models.Model):
    idx = models.AutoField(primary_key=True)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    duration = models.IntegerField()  # seconds
    duration_type = models.IntegerField()  # duration pseudo enum from functions
    ext_license_site = models.ForeignKey("backbone.ext_license_site", null=True)

    class Meta:
        app_label = "backbone"


class ext_license_state_coarse(models.Model):
    idx = models.AutoField(primary_key=True)
    ext_license_check_coarse = models.ForeignKey("backbone.ext_license_check_coarse")  # "pk"

    ext_license = models.ForeignKey("backbone.ext_license")  # grouped by this

    # free is issued - used; reserved field might be added later
    used = models.FloatField(default=0.0)  # smartly aggregated value
    used_min = models.IntegerField(default=0)
    used_max = models.IntegerField(default=0)
    issued = models.FloatField(default=0.0)  # smartly aggregated value
    issued_min = models.IntegerField(default=0)
    issued_max = models.IntegerField(default=0)
    data_points = models.IntegerField()  # number of measurements used for calculating this

    class Meta:
        app_label = "backbone"


class ext_license_version_state_coarse(models.Model):
    idx = models.AutoField(primary_key=True)
    ext_license_check_coarse = models.ForeignKey("backbone.ext_license_check_coarse")  # "pk"
    ext_license_state_coarse = models.ForeignKey("backbone.ext_license_state_coarse")  # "pk"

    ext_license_version = models.ForeignKey("backbone.ext_license_version")  # grouped by this
    vendor = models.ForeignKey("backbone.ext_license_vendor")  # grouped by this

    frequency = models.IntegerField()  # number of actual usages of this combination of license_version and vendor occurred, grouped by check and state

    class Meta:
        app_label = "backbone"


class ext_license_usage_coarse(models.Model):
    idx = models.AutoField(primary_key=True)
    ext_license_version_state_coarse = models.ForeignKey("backbone.ext_license_version_state_coarse")  # "pk"

    ext_license_client = models.ForeignKey("backbone.ext_license_client")  # grouped by this
    ext_license_user = models.ForeignKey("backbone.ext_license_user")  # grouped by this
    # client version currently deemed not necessary, possibly add later
    # ext_license_client_version = models.ForeignKey("backbone.ext_license_client_version", null=True)
    num = models.IntegerField(default=0)  # number of licenses of a single instance of a program

    frequency = models.IntegerField()  # number of times this client/user/num combination occurred for this version_state

    class Meta:
        app_label = "backbone"

