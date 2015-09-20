# Copyright (C) 2013-2015 Andreas Lang-Nevyjel, init.at
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

import datetime
import time

from django.db import models
from django.db.models import signals
from django.dispatch import receiver
from initat.cluster.backbone.models.functions import cluster_timezone, duration as duration_types


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
    "RMSJobVariable",
    "RMSJobVariableAction",
    "RMSJobVariableActionRun"
]


class rms_project(models.Model):
    idx = models.AutoField(primary_key=True)
    name = models.CharField(unique=True, max_length=255)
    # oticket = models.FloatField(null=True, blank=True)
    # fshare = models.FloatField(null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return self.name

    class Meta:
        app_label = "backbone"


class rms_department(models.Model):
    idx = models.AutoField(primary_key=True)
    name = models.CharField(unique=True, max_length=255)
    # oticket = models.FloatField(null=True, blank=True)
    # fshare = models.FloatField(null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return self.name

    class Meta:
        app_label = "backbone"


class rms_queue(models.Model):
    idx = models.AutoField(primary_key=True)
    name = models.CharField(unique=True, max_length=255)
    date = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return "queue {}".format(self.name)

    class Meta:
        app_label = "backbone"


class rms_pe(models.Model):
    idx = models.AutoField(primary_key=True)
    name = models.CharField(unique=True, max_length=255)
    date = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return "pe {}".format(self.name)

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

    @property
    def full_id(self):
        return "{:d}{}".format(
            self.jobid,
            ".{:d}".format(self.taskid) if self.taskid else "",
        )

    def add_job_run(self, _dev_name, _dev):
        new_run = rms_job_run(
            rms_job=self,
            device=_dev,
            hostname=_dev_name,
            start_time_py=cluster_timezone.localize(datetime.datetime.now()),
        )
        return new_run

    def get_latest_job_run(self):
        _runs = self.rms_job_run_set.all().order_by("-pk")
        if _runs.count():
            _latest_run = _runs[0]
        else:
            _latest_run = None
        return _latest_run

    def close_job_run(self):
        _latest_run = self.get_latest_job_run()
        if _latest_run:
            _latest_run.end_time_py = cluster_timezone.localize(datetime.datetime.now())
            _latest_run.save(update_fields=["end_time_py"])
        return _latest_run

    def __unicode__(self):
        return "job {}".format(self.full_id)

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

    def rms_pe_info(self):
        # used by serializer and rrd-grapher.initat.graph"
        return [
            {
                "device": _pe_info.device_id,
                "hostname": _pe_info.hostname,
                "slots": _pe_info.slots,
            } for _pe_info in self.rms_pe_info_set.all()
        ]

    def get_queue_time(self):
        return time.mktime(cluster_timezone.normalize(self.queue_time).timetuple()) if self.queue_time else ""

    def get_start_time(self):
        return time.mktime(cluster_timezone.normalize(self.start_time).timetuple()) if self.start_time else ""

    def get_end_time(self):
        return time.mktime(cluster_timezone.normalize(self.end_time).timetuple()) if self.end_time else ""

    def get_start_time_py(self):
        return time.mktime(cluster_timezone.normalize(self.start_time_py).timetuple()) if self.start_time_py else ""

    def get_end_time_py(self):
        return time.mktime(cluster_timezone.normalize(self.end_time_py).timetuple()) if self.end_time_py else ""

    def __unicode__(self):
        return "run for {} in {}".format(
            unicode(self.rms_job),
            unicode(self.rms_queue),
        )

    def _set_is_value(self, attr_name, value):
        if type(value) in [int, long]:
            setattr(self, attr_name, value)
            setattr(self, "{}_str".format(attr_name), "")
        else:
            _int, _str = value.strip().split(None, 1)
            setattr(self, attr_name, int(_int))
            setattr(self, "{}_str".format(attr_name), _str.strip())

    def feed_qacct_data(self, in_dict):
        self.priority = in_dict["priority"]
        self.rms_project = in_dict["project"]
        self.rms_department = in_dict["department"]
        self.account = in_dict["account"]
        self._set_is_value("failed", in_dict["failed"])
        self._set_is_value("exit_status", in_dict["exit_status"])
        if in_dict["start_time"]:
            self.start_time = in_dict["start_time"]
        if in_dict["end_time"]:
            self.end_time = in_dict["end_time"]
        if in_dict["qsub_time"]:
            self.queue_time = in_dict["qsub_time"]
        self.qacct_called = True
        self.save()

    class Meta:
        app_label = "backbone"


@receiver(signals.post_save, sender=rms_job_run)
def _rms_job_run_post_save(sender, instance, raw, **kwargs):
    from initat.cluster.backbone.available_licenses import LicenseEnum, LicenseParameterTypeEnum
    from initat.cluster.backbone.models import LicenseUsage
    if not raw:
        if instance.device is not None:
            LicenseUsage.log_usage(LicenseEnum.rms, LicenseParameterTypeEnum.device, instance.device)


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

    def __unicode__(self):
        return "ExternalLicense(name={})".format(self.name)

    __repr__ = __unicode__

    class CSW_Meta:
        fk_ignore_list = [
            "LicenseUsageExtLicense", "LicenseLockListExtLicense",
        ]


class ext_license_version(ext_license_base):
    """
    License version as reported by server (different from what is used and reported by client.)
    This is probably the import one.
    """
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

    class CSW_Meta:
        backup = False


class ext_license_version_state(models.Model):
    idx = models.AutoField(primary_key=True)
    ext_license_check = models.ForeignKey("backbone.ext_license_check")
    ext_license_version = models.ForeignKey("backbone.ext_license_version")
    ext_license_state = models.ForeignKey("backbone.ext_license_state")
    is_floating = models.BooleanField(default=False)
    vendor = models.ForeignKey("backbone.ext_license_vendor")

    class Meta:
        app_label = "backbone"

    class CSW_Meta:
        backup = False


class ext_license_client_version(ext_license_base):
    """
    License version as reported by client (different from what is used and reported by server.)
    """
    ext_license = models.ForeignKey("backbone.ext_license")
    client_version = models.CharField(default="", max_length=64)

    class CSW_Meta:
        backup = False


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

    class CSW_Meta:
        backup = False


"""
The models above are too fine-grained for fast access, so we use the ones
below for displaying them. Here, the data is aggregated using dynamic durations.
"""


class ext_license_check_coarse(models.Model):
    idx = models.AutoField(primary_key=True)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    duration = models.IntegerField()  # seconds
    duration_type = models.IntegerField()  # duration pseudo enum from functions
    ext_license_site = models.ForeignKey("backbone.ext_license_site", null=True)

    def get_display_date(self):
        klass = duration_types.get_class(self.duration_type)
        # border values easily create problems with timezones etc, hence use central values
        return klass.get_display_date(self.start_date + ((self.end_date - self.start_date) / 2))  # @IgnorePep8

    class Meta:
        app_label = "backbone"

    class CSW_Meta:
        backup = False


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

    class CSW_Meta:
        backup = False

    def get_display_date(self):
        return self.ext_license_check_coarse.get_display_date()


class ext_license_version_state_coarse(models.Model):
    idx = models.AutoField(primary_key=True)
    ext_license_check_coarse = models.ForeignKey("backbone.ext_license_check_coarse")  # "pk"
    ext_license_state_coarse = models.ForeignKey("backbone.ext_license_state_coarse")  # "pk"

    ext_license_version = models.ForeignKey("backbone.ext_license_version")  # grouped by this
    vendor = models.ForeignKey("backbone.ext_license_vendor")  # grouped by this

    frequency = models.IntegerField()  # number of actual usages of this combination of license_version and vendor occurred, grouped by check and state

    class Meta:
        app_label = "backbone"

    class CSW_Meta:
        backup = False

    def get_display_date(self):
        return self.ext_license_check_coarse.get_display_date()


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

    class CSW_Meta:
        backup = False


class RMSJobVariable(models.Model):
    idx = models.AutoField(primary_key=True)
    # link to job
    rms_job = models.ForeignKey("backbone.rms_job")
    name = models.CharField(max_length=255, default="")
    raw_value = models.TextField(default="")
    parsed_type = models.CharField(
        max_length=2,
        choices=[
            ("i", "Integer"),
            ("f", "Float"),
            ("s", "String"),
        ],
        default="s",
    )
    parsed_integer = models.IntegerField(default=None, null=True)
    parsed_float = models.FloatField(default=None, null=True)
    date = models.DateTimeField(auto_now_add=True)

    @property
    def value(self):
        if self.parsed_type == "i":
            return self.parsed_integer
        elif self.parsed_type == "f":
            return self.parsed_float
        else:
            return self.raw_value

    def __unicode__(self):
        return "RMSJobVariable '{}'".format(self.name)

    class Meta:
        unique_together = (
            ("name", "rms_job"),
        )


@receiver(signals.pre_save, sender=RMSJobVariable)
def rms_job_variable_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_var = kwargs["instance"]
        cur_var.parsed_float, cur_var.parsed_int = (None, None)
        try:
            _float = float(cur_var.raw_value.replace(",", ".").strip())
        except:
            try:
                _int = int(cur_var.strip())
            except:
                cur_var.parsed_type = "s"
            else:
                cur_var.parsed_type = "i"
                cur_var.parsed_int = _int
        else:
            cur_var.parsed_type = "f"
            cur_var.parsed_float = _float


class RMSJobVariableAction(models.Model):
    # code to call when a variable changes
    idx = models.AutoField(primary_key=True)
    name = models.CharField(default="", max_length=255, unique=True)
    # this code gets called
    code = models.TextField(default="")
    date = models.DateTimeField(auto_now_add=True)


class RMSJobVariableActionRun(models.Model):
    idx = models.AutoField(primary_key=True)
    rms_job = models.ForeignKey("backbone.rms_job")
    rms_job_variable_action_run = models.ForeignKey("backbone.RMSJobVariableAction")
    run_time = models.FloatField(default=0.0)
    success = models.BooleanField(default=False)
    vars_created = models.IntegerField(default=0)
    triggered_run = models.BooleanField(default=False)
    date = models.DateTimeField(auto_now_add=True)
