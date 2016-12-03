# Copyright (C) 2013-2016 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw-server
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
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

from __future__ import unicode_literals, print_function

import datetime
import time
from enum import Enum

from django.db import models
from django.db.models import signals, Q
from django.dispatch import receiver

from initat.cluster.backbone.models.functions import cluster_timezone, duration as duration_types

from initat.tools import logging_tools

__all__ = [
    b"rms_job",
    b"rms_job_run",
    b"rms_pe_info",
    b"rms_project",
    b"rms_department",
    b"rms_user",
    b"rms_queue",
    b"rms_pe",
    b"rms_accounting_run",
    b"rms_accounting_record",
    b"ext_license_site",
    b"ext_license",
    b"ext_license_version",
    b"ext_license_vendor",
    b"ext_license_user",
    b"ext_license_client",
    b"ext_license_client_version",
    b"ext_license_check",
    b"ext_license_state",
    b"ext_license_version_state",
    b"ext_license_usage",
    b"ext_license_check_coarse",
    b"ext_license_version_state_coarse",
    b"ext_license_state_coarse",
    b"ext_license_usage_coarse",
    b"RMSJobVariable",
    b"RMSJobVariableAction",
    b"RMSJobVariableActionRun",
    b"RMSAggregationLevelEnum",
]


class rms_project(models.Model):
    idx = models.AutoField(primary_key=True)
    name = models.CharField(unique=True, max_length=255)
    # oticket = models.FloatField(null=True, blank=True)
    # fshare = models.FloatField(null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return self.name


class rms_department(models.Model):
    idx = models.AutoField(primary_key=True)
    name = models.CharField(unique=True, max_length=255)
    # oticket = models.FloatField(null=True, blank=True)
    # fshare = models.FloatField(null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return self.name


class rms_queue(models.Model):
    idx = models.AutoField(primary_key=True)
    name = models.CharField(unique=True, max_length=255)
    date = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return "queue {}".format(self.name)


class rms_pe(models.Model):
    idx = models.AutoField(primary_key=True)
    name = models.CharField(unique=True, max_length=255)
    date = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return "pe {}".format(self.name)


class rms_user(models.Model):
    idx = models.AutoField(primary_key=True)
    name = models.CharField(unique=True, max_length=255)
    # makes sense because this can change during time
    fshare = models.IntegerField(default=0)
    # link to user
    user = models.ForeignKey("backbone.user", null=True)
    # default project
    default_project = models.ForeignKey("backbone.rms_project", null=True)
    date = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return "rms_user {}".format(self.name)


class RMSAggregationLevel(object):
    run_idx = 0

    def __init__(self, short, what):
        self.short = short
        self.what = what
        self.idx = RMSAggregationLevel.run_idx
        self.prev_idx = self.idx - 1
        RMSAggregationLevel.run_idx += 1
        # print(self.idx, self.short)

    def aggregate(self, log_com):
        # get base aggregation level
        base = {
            "h": "n",
            "d": "h",
            "m": "d",
            "y": "m"
        }.get(self.short, None)
        if base:
            # base is now the base level for aggregation
            # get latest aggregated run
            _latest = rms_accounting_run.objects.filter(Q(aggregation_level=self.short)).order_by("-pk")
            # print("** {} {:d}".format(self.short, _latest.count()))
            if _latest.count():
                _latest = _latest[0]
                _start_time = _latest.aggregation_end
                # print("{}: {}".format(self.short, _start_time))
            else:
                # none defined
                log_com(
                    "No records found for {}".format(self.what),
                    logging_tools.LOG_LEVEL_WARN
                )
                # aggregate all
                _start_time = None
            # get base records
            src_records = rms_accounting_run.objects.filter(
                Q(aggregation_level=base)
            )
            if _start_time is not None:
                if base == "n":
                    src_records = src_records.filter(
                        Q(
                            date__gte=_start_time
                        )
                    )
                else:
                    src_records = src_records.filter(
                        Q(
                            aggregation_start=_start_time
                        )
                    )
            src_records = src_records.prefetch_related("rms_accounting_record_set__rms_user")
            if src_records.count():
                # print("found {:d} for {}".format(src_records.count(), self.short))

                # quantify
                # get min / max
                if base == "n":
                    min_date = min([entry.date for entry in src_records])
                    max_date = max([entry.date for entry in src_records])
                else:
                    min_date = min([entry.aggregation_start for entry in src_records])
                    max_date = max([entry.aggregation_end for entry in src_records])
                # print(min_date, max_date)
                min_date = cluster_timezone.normalize(min_date)
                max_date = cluster_timezone.normalize(max_date)
                # print(min_date, max_date)
                # build quantify list based on min and max date
                quant_list = self.build_quantify_list(min_date, max_date)
                quant_list = self.fill_quant_list(quant_list, src_records)
                # create new records
                for entry in quant_list:
                    self.evaluate_q_entry(entry, log_com)
                # import pprint
                # pprint.pprint(quant_list)

    def build_quantify_list(self, min_date, max_date):
        _list = []
        abs_end_time = self.ts_to_base(cluster_timezone.localize(datetime.datetime.now()))
        # print(min_date, abs_end_time, abs_end_time - min_date)
        # hour
        start_time = self.ts_to_base(min_date)
        while True:
            end_time = self.next_step(start_time)
            if end_time > abs_end_time:
                break
            _list.append(
                {
                    "start": start_time,
                    "end": end_time,
                    "records": [],
                }
            )
            start_time = end_time
            if start_time >= max_date:
                break
        return _list

    def fill_quant_list(self, q_list, src_records):
        for entry in q_list:
            n_list = []
            for rec in src_records:
                if rec.aggregation_level == "n":
                    c_d = rec.date
                else:
                    c_d = rec.aggregation_start + datetime.timedelta(seconds=(rec.aggregation_end - rec.aggregation_start).total_seconds() / 2)
                if c_d > entry["start"] and c_d < entry["end"]:
                    entry["records"].append(rec)
                else:
                    n_list.append(rec)
            src_records = n_list
        return q_list

    def evaluate_q_entry(self, entry, log_com):
        # evaluate quantify entry
        if entry["records"]:
            timespan = (entry["end"] - entry["start"]).total_seconds()
            # simple weight
            #  - True: simple count entries
            #  - False: weigth according to entry width
            simple_weight = entry["records"][0].aggregation_level == "n"
            if simple_weight:
                _count = len(entry["records"])
            _total_slots = 0
            for run in entry["records"]:
                if simple_weight:
                    _fact = 1
                    _div = _count
                else:
                    _fact = run.weight
                    _div = timespan
                _total_slots += run.slots_defined * _fact
            new_run = rms_accounting_run(
                aggregation_level=self.short,
                aggregation_start=entry["start"],
                aggregation_end=entry["end"],
                weight=timespan,
                num_source_records=len(entry["records"]),
                slots_defined=int(_total_slots / float(_div))
            )
            new_run.save()
            # print("create for {}".format(self.short))
            _user_dict = {}
            for run in entry["records"]:
                if simple_weight:
                    _fact = 1
                    _div = _count
                else:
                    _fact = run.weight
                    _div = timespan
                _total_slots += run.slots_defined * _fact
                for rec in run.rms_accounting_record_set.all():
                    if rec.rms_user_id not in _user_dict:
                        _user_dict[rec.rms_user_id] = {
                            "rms_user": rec.rms_user,
                            "slots": 0,
                        }
                    _user_dict[rec.rms_user_id]["slots"] += _fact * rec.slots_used
            db_recs = []
            for _key, _struct in _user_dict.iteritems():
                _struct["slots"] /= float(_div)
                db_recs.append(
                    rms_accounting_record(
                        rms_accounting_run=new_run,
                        rms_user=_struct["rms_user"],
                        slots_used=_struct["slots"],
                    )
                )
                # print("*", _struct)
            if db_recs:
                rms_accounting_record.objects.bulk_create(db_recs)
            log_com(
                "creating new run for {} (from {}, {} created)".format(
                    self.short,
                    logging_tools.get_plural("source run", len(entry["records"])),
                    logging_tools.get_plural("user record", len(db_recs)),
                )
            )
            # import pprint
            # print(self.short)
            # pprint.pprint(_user_dict)

    def ts_to_base(self, s_time):
        if self.short == "h":
            return s_time.replace(second=0, minute=0)
        elif self.short == "d":
            return s_time.replace(second=0, minute=0, hour=0)
        elif self.short == "m":
            return s_time.replace(second=0, minute=0, hour=0, day=1)
        elif self.short == "y":
            return s_time.replace(second=0, minute=0, hour=0, day=1, month=1)

    def next_step(self, s_time):
        # return next timestep for quantification
        if self.short == "h":
            return s_time + datetime.timedelta(hours=1)
        elif self.short == "d":
            return s_time + datetime.timedelta(days=1)
        elif self.short == "m":
            return (s_time + datetime.timedelta(days=32)).replace(day=1)
        elif self.short == "y":
            return (s_time + datetime.timedelta(days=366)).replace(day=1, month=1)
        else:
            return None


class RMSAggregationLevelEnum(Enum):
    none = RMSAggregationLevel("n", "base")
    hour = RMSAggregationLevel("h", "hourly")
    day = RMSAggregationLevel("d", "daily")
    month = RMSAggregationLevel("m", "monthly")
    year = RMSAggregationLevel("y", "yearly")


class rms_accounting_run(models.Model):
    idx = models.AutoField(primary_key=True)
    # run is aggregated (hour / day / month)
    aggregation_level = models.CharField(
        max_length=1,
        default=RMSAggregationLevelEnum.none.value.short,
        choices=[(_al.value.short, _al.name) for _al in RMSAggregationLevelEnum],
    )
    # number of slots defined
    slots_defined = models.IntegerField(default=1)
    # start and end of aggregation interval (end_of_n == start_of_n+1)
    aggregation_start = models.DateTimeField(default=None, null=True)
    aggregation_end = models.DateTimeField(default=None, null=True)
    # weight in seconds
    weight = models.IntegerField(default=0)
    # number of source records
    num_source_records = models.IntegerField(default=0)
    date = models.DateTimeField(auto_now_add=True)


class rms_accounting_record(models.Model):
    idx = models.AutoField(primary_key=True)
    rms_user = models.ForeignKey("backbone.rms_user")
    rms_accounting_run = models.ForeignKey("backbone.rms_accounting_run")
    slots_used = models.IntegerField(default=0)
    date = models.DateTimeField(auto_now_add=True)


class rms_job(models.Model):
    idx = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    # id of job
    jobid = models.IntegerField()
    taskid = models.IntegerField(null=True)
    owner = models.CharField(max_length=255, default="")
    # prefered
    rms_user = models.ForeignKey("backbone.rms_user", null=True, on_delete=models.SET_NULL)
    # fallback
    user = models.ForeignKey("backbone.user", null=True, on_delete=models.SET_NULL)
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

    def get_rms_job_variables(self):
        return self.rmsjobvariable_set.all()

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


@receiver(signals.post_save, sender=rms_job_run)
def _rms_job_run_post_save(sender, instance, raw, **kwargs):
    pass


class rms_pe_info(models.Model):
    idx = models.AutoField(primary_key=True)
    rms_job_run = models.ForeignKey(rms_job_run)
    device = models.ForeignKey("backbone.device", null=True)
    hostname = models.CharField(max_length=255)
    slots = models.IntegerField(default=0)
    date = models.DateTimeField(auto_now_add=True)


# license models
# TODO: track cluster / external license usage
class ext_license_base(models.Model):
    idx = models.AutoField(primary_key=True)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True


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

    class CSW_Meta:
        backup = False


class ext_license_version_state(models.Model):
    idx = models.AutoField(primary_key=True)
    ext_license_check = models.ForeignKey("backbone.ext_license_check")
    ext_license_version = models.ForeignKey("backbone.ext_license_version")
    ext_license_state = models.ForeignKey("backbone.ext_license_state")
    is_floating = models.BooleanField(default=False)
    vendor = models.ForeignKey("backbone.ext_license_vendor")

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

    class CSW_Meta:
        backup = False


class RMSJobVariable(models.Model):
    idx = models.AutoField(primary_key=True)
    # link to job
    rms_job = models.ForeignKey("backbone.rms_job")
    rms_job_run = models.ForeignKey("backbone.rms_job_run", null=True)
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
    unit = models.CharField(max_length=16, default="")
    date = models.DateTimeField(auto_now_add=True)

    def get_value(self):
        return self.value

    def get_int_value(self):
        _v = self.value
        if self.parsed_type == "f":
            _v = int(_v)
        return _v

    @property
    def value(self):
        if self.parsed_type == "i":
            return self.parsed_integer
        elif self.parsed_type == "f":
            return self.parsed_float
        else:
            return self.raw_value

    @property
    def var_type(self):
        return self.get_parsed_type_display()

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
        cur_var.unit = cur_var.unit or ""
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
