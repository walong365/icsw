# Copyright (C) 2001-2015 Andreas Lang-Nevyjel, init.at
#
# this file is part of icsw-server
#
# Send feedback to: <lang-nevyjel@init.at>
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
""" database definitions for monitoring """

import datetime
import json
import operator
import re
from collections import defaultdict

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, signals, Max, Min
from django.dispatch import receiver
from initat.tools import logging_tools

__all__ = [
    "mon_host_cluster",
    "mon_service_cluster",
    "host_check_command",
    "mon_check_command",
    "mon_check_command_type",
    "mon_contact",
    "mon_notification",
    "mon_contactgroup",
    "mon_device_templ",
    "mon_device_esc_templ",
    "mon_host_dependency_templ",
    "mon_host_dependency",
    "mon_service_dependency_templ",
    "mon_service_dependency",
    "mon_ext_host",
    "mon_period",
    "mon_service_templ",
    "mon_service_esc_templ",
    # distribution models
    "mon_dist_master",  # "mon_dist_master_serializer",
    "mon_dist_slave",  # "mon_dist_slave_serializer",
    "monitoring_hint",
    "mon_check_command_special",
    # trace
    "mon_trace",  # monitoring trace for speedup
    # unreachable info
    "mon_build_unreachable",  # track unreachable devices
    "snmp_scheme_vendor",
    "snmp_scheme",
    "snmp_scheme_tl_oid",
    "mon_icinga_log_raw_host_alert_data",
    "mon_icinga_log_raw_service_alert_data",
    "mon_icinga_log_file",
    "mon_icinga_log_last_read",
]


def db_limit_1():
    # return True if databases do not support some unique_together combinations
    return True if settings.DATABASES["default"]["ENGINE"].lower().count("oracle") else False


class snmp_scheme_vendor(models.Model):
    idx = models.AutoField(primary_key=True)
    # name
    name = models.CharField(max_length=128, unique=True)
    # info (full name of company)
    company_info = models.CharField(max_length=256, default="")
    date = models.DateTimeField(auto_now_add=True)

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
    # priority for handling, schemes with higher priority will be handled first
    priority = models.IntegerField(default=0)
    date = models.DateTimeField(auto_now_add=True)

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


class mon_trace(models.Model):
    idx = models.AutoField(primary_key=True)
    device = models.ForeignKey("backbone.device")
    # fingerprint of device netdevices
    dev_netdevice_fp = models.CharField(max_length=128, default="", db_index=True)
    # fingerprint of server netdevices
    srv_netdevice_fp = models.CharField(max_length=128, default="", db_index=True)
    traces = models.TextField(default="")
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "backbone"


class mon_dist_base(models.Model):
    # start of build
    config_build_start = models.DateTimeField(default=None, null=True)
    # end of build
    config_build_end = models.DateTimeField(default=None, null=True)
    # version of of relayer / icinga
    relayer_version = models.CharField(max_length=128, default="")
    mon_version = models.CharField(max_length=128, default="")
    # total build start
    build_start = models.DateTimeField(default=None, null=True)
    # total build end
    build_end = models.DateTimeField(default=None, null=True)
    # number of devices
    num_devices = models.IntegerField(default=0)
    # unroutable devices, always zero for slaves
    unreachable_devices = models.IntegerField(default=0)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True


# distribution models, one per run
class mon_dist_slave(mon_dist_base):
    idx = models.AutoField(primary_key=True)
    mon_dist_master = models.ForeignKey("backbone.mon_dist_master")
    device = models.ForeignKey("backbone.device")
    # start of first sync
    sync_start = models.DateTimeField(default=None, null=True)
    # end of last sync
    sync_end = models.DateTimeField(default=None, null=True)
    # number of distribute runs (==sync)
    num_runs = models.IntegerField(default=0)
    # files transfered / number of transfered commands
    num_files = models.IntegerField(default=0)
    num_transfers = models.IntegerField(default=0)
    # pure data
    size_data = models.IntegerField(default=0)
    # with overhead
    size_raw = models.IntegerField(default=0)

    class Meta:
        app_label = "backbone"
        verbose_name = "Config builds as slave"


class mon_dist_master(mon_dist_base):
    idx = models.AutoField(primary_key=True)
    device = models.ForeignKey("backbone.device")
    version = models.IntegerField(default=0)
    # version of of md-config-server
    md_version = models.CharField(max_length=128, default="")

    class Meta:
        app_label = "backbone"
        ordering = ("-idx",)
        verbose_name = "Config builds as master"


class mon_build_unreachable(models.Model):
    idx = models.AutoField(primary_key=True)
    mon_dist_master = models.ForeignKey("backbone.mon_dist_master")
    device_pk = models.IntegerField(default=0)
    device_name = models.CharField(max_length=256, default="")
    devicegroup_name = models.CharField(max_length=256, default="")
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "backbone"


class mon_host_cluster(models.Model):
    idx = models.AutoField(primary_key=True)
    name = models.CharField(max_length=128, blank=False, null=False, unique=True)
    description = models.CharField(max_length=255, default="")
    main_device = models.ForeignKey("backbone.device", related_name="main_mon_host_cluster")
    mon_service_templ = models.ForeignKey("backbone.mon_service_templ")
    devices = models.ManyToManyField("backbone.device", related_name="devs_mon_host_cluster")
    warn_value = models.IntegerField(default=0)
    error_value = models.IntegerField(default=1)
    # True for user editable (user created) clusters
    user_editable = models.BooleanField(default=True)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "backbone"
        verbose_name = "Host Cluster"


class mon_service_cluster(models.Model):
    idx = models.AutoField(primary_key=True)
    name = models.CharField(max_length=128, blank=False, null=False, unique=True)
    description = models.CharField(max_length=255, default="")
    main_device = models.ForeignKey("backbone.device", related_name="main_mon_service_cluster")
    mon_service_templ = models.ForeignKey("backbone.mon_service_templ")
    devices = models.ManyToManyField("backbone.device", related_name="devs_mon_service_cluster")
    mon_check_command = models.ForeignKey("backbone.mon_check_command")
    warn_value = models.IntegerField(default=0)
    error_value = models.IntegerField(default=1)
    # True for user editable (user created) clusters
    user_editable = models.BooleanField(default=True)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "backbone"
        verbose_name = "Service Cluster"


class host_check_command(models.Model):
    idx = models.AutoField(db_column="ng_check_command_idx", primary_key=True)
    name = models.CharField(max_length=64, unique=True, blank=False, null=False)
    command_line = models.CharField(max_length=128, unique=True, blank=False, null=False)
    date = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return "hcc_{}".format(self.name)

    class Meta:
        app_label = "backbone"


class mon_check_command_special(models.Model):
    idx = models.AutoField(primary_key=True)
    name = models.CharField(max_length=64, unique=True)
    info = models.CharField(max_length=64, default="")
    command_line = models.CharField(max_length=512, default="")
    description = models.CharField(max_length=512, default="")
    is_active = models.BooleanField(default=True)
    date = models.DateTimeField(auto_now_add=True)
    # triggers other commands
    meta = models.BooleanField(default=False)
    # for commands from a meta-command
    parent = models.ForeignKey("self", null=True)
    # identifier, to find certain checks, for internal use only
    identifier = models.CharField(max_length=64, default="")

    class Meta:
        app_label = "backbone"


class mon_check_command(models.Model):
    idx = models.AutoField(db_column="ng_check_command_idx", primary_key=True)
    config_old = models.IntegerField(null=True, blank=True, db_column="config")
    config = models.ForeignKey("backbone.config", db_column="new_config_id")
    # deprecated, now references category tree
    mon_check_command_type = models.ForeignKey("backbone.mon_check_command_type", null=True, default=None, blank=True)
    mon_service_templ = models.ForeignKey("backbone.mon_service_templ", null=True, blank=True)
    # only unique per config
    name = models.CharField(max_length=192)  # , unique=True)
    # flag for special commands (@<SREF>@command)
    mon_check_command_special = models.ForeignKey("backbone.mon_check_command_special", null=True, blank=True)
    # for mon_check_special_command this is empty
    command_line = models.CharField(max_length=765, default="")
    description = models.CharField(max_length=192, blank=True)
    # device = models.ForeignKey("backbone.device", null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    enable_perfdata = models.BooleanField(default=False)
    volatile = models.BooleanField(default=False)
    # categories for this check
    categories = models.ManyToManyField("backbone.category", blank=True)
    # device to exclude
    exclude_devices = models.ManyToManyField("backbone.device", related_name="mcc_exclude_devices", blank=True)
    # event handler settings
    is_event_handler = models.BooleanField(default=False)
    event_handler = models.ForeignKey("self", null=True, default=None, blank=True)
    event_handler_enabled = models.BooleanField(default=True)
    # is an active check
    is_active = models.BooleanField(default=True)
    # which tcp port(s) cover this check
    tcp_coverage = models.CharField(default="", max_length=256, blank=True)

    class Meta:
        db_table = 'ng_check_command'
        unique_together = (("name", "config"))
        app_label = "backbone"


class mon_check_command_type(models.Model):
    idx = models.AutoField(db_column="ng_check_command_type_idx", primary_key=True)
    name = models.CharField(unique=True, max_length=192)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ng_check_command_type'
        app_label = "backbone"


class mon_contact(models.Model):
    idx = models.AutoField(db_column="ng_contact_idx", primary_key=True)
    user = models.ForeignKey("backbone.user")
    snperiod = models.ForeignKey("backbone.mon_period", related_name="service_n_period", verbose_name="service period")
    hnperiod = models.ForeignKey("backbone.mon_period", related_name="host_n_period", verbose_name="host period")
    snrecovery = models.BooleanField(default=False, verbose_name="Notify on service recovery")
    sncritical = models.BooleanField(default=False, verbose_name="Notify on service critical")
    snwarning = models.BooleanField(default=False, verbose_name="Notify on service warning")
    snunknown = models.BooleanField(default=False, verbose_name="Notify on service unknown")
    sflapping = models.BooleanField(default=False, verbose_name="Notify on service flapping")
    splanned_downtime = models.BooleanField(default=False, verbose_name="Notify on service planned downtime")
    hnrecovery = models.BooleanField(default=False, verbose_name="Notify on host recovery")
    hndown = models.BooleanField(default=False, verbose_name="Notify on host down")
    hnunreachable = models.BooleanField(default=False, verbose_name="Notify on host unreachable")
    hflapping = models.BooleanField(default=False, verbose_name="Notify on host flapping")
    hplanned_downtime = models.BooleanField(default=False, verbose_name="Notify on host planned downtime")
    date = models.DateTimeField(auto_now_add=True)
    notifications = models.ManyToManyField("backbone.mon_notification", blank=True)
    mon_alias = models.CharField(max_length=64, default="", verbose_name="alias", blank=True)

    class Meta:
        db_table = 'ng_contact'
        app_label = "backbone"


class mon_notification(models.Model):
    idx = models.AutoField(primary_key=True)
    name = models.CharField(max_length=128, blank=False, unique=True)
    channel = models.CharField(max_length=8, choices=[
        ("mail", "E-Mail"),
        ("sms", "SMS")], blank=False)
    not_type = models.CharField(
        max_length=8,
        choices=[
            ("host", "Host"),
            ("service", "Service")
        ],
        blank=False,
        verbose_name="Notification type"
    )
    subject = models.CharField(max_length=140, blank=True)
    # changed to 255 for MySQL / Oracle initial setup
    content = models.CharField(max_length=512, blank=False)
    enabled = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "backbone"


class mon_contactgroup(models.Model):
    idx = models.AutoField(db_column="ng_contactgroup_idx", primary_key=True)
    name = models.CharField(max_length=192, unique=True)
    alias = models.CharField(max_length=255, blank=True, default="")
    date = models.DateTimeField(auto_now_add=True)
    device_groups = models.ManyToManyField("device_group", blank=True)
    members = models.ManyToManyField("backbone.mon_contact", blank=True)
    service_templates = models.ManyToManyField("backbone.mon_service_templ", blank=True)
    service_esc_templates = models.ManyToManyField("backbone.mon_service_esc_templ", blank=True)

    class Meta:
        db_table = 'ng_contactgroup'
        app_label = "backbone"


class mon_device_templ(models.Model):
    idx = models.AutoField(db_column="ng_device_templ_idx", primary_key=True)
    name = models.CharField(unique=True, max_length=192)
    mon_service_templ = models.ForeignKey("backbone.mon_service_templ")
    host_check_command = models.ForeignKey("backbone.host_check_command", null=True)
    # check interval
    check_interval = models.IntegerField(default=1)
    # retry interval
    retry_interval = models.IntegerField(default=1)
    # max_check_attempts
    max_attempts = models.IntegerField(null=True, blank=True, default=1)
    # notification interval
    ninterval = models.IntegerField(null=True, blank=True, default=1)
    not_period = models.ForeignKey("backbone.mon_period", related_name="dev_notify_period")
    # monitoring period
    mon_period = models.ForeignKey("backbone.mon_period", related_name="dev_check_period")
    # Notificiation Flags
    nrecovery = models.BooleanField(default=False, verbose_name="Notify on recovery")
    ndown = models.BooleanField(default=False, verbose_name="Notify when down")
    nunreachable = models.BooleanField(default=False, verbose_name="Notify when unreachable")
    nflapping = models.BooleanField(default=False, verbose_name="Notify when flapping")
    nplanned_downtime = models.BooleanField(default=False, verbose_name="Notify for planned downtime")
    is_default = models.BooleanField(default=False)
    low_flap_threshold = models.IntegerField(default=0)
    high_flap_threshold = models.IntegerField(default=0)
    flap_detection_enabled = models.BooleanField(default=False)
    flap_detect_up = models.BooleanField(default=True)
    flap_detect_down = models.BooleanField(default=False)
    flap_detect_unreachable = models.BooleanField(default=False)
    # freshness checks
    check_freshness = models.BooleanField(default=False)
    freshness_threshold = models.IntegerField(default=60)
    date = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return self.name

    class Meta:
        db_table = 'ng_device_templ'
        app_label = "backbone"


class mon_device_esc_templ(models.Model):
    idx = models.AutoField(primary_key=True)
    name = models.CharField(unique=True, max_length=192)
    first_notification = models.IntegerField(default=1)
    last_notification = models.IntegerField(default=1)
    mon_service_esc_templ = models.ForeignKey("backbone.mon_service_esc_templ")
    ninterval = models.IntegerField(default=1)
    esc_period = models.ForeignKey("backbone.mon_period")
    nrecovery = models.BooleanField(default=False, verbose_name="Notify on recovery")
    ndown = models.BooleanField(default=False, verbose_name="Notify when down")
    nunreachable = models.BooleanField(default=False, verbose_name="Notify when unreachable")
    nflapping = models.BooleanField(default=False, verbose_name="Notify when flapping")
    nplanned_downtime = models.BooleanField(default=False, verbose_name="Notify on planned downtime")
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "backbone"


class mon_host_dependency_templ(models.Model):
    idx = models.AutoField(primary_key=True)
    name = models.CharField(unique=True, max_length=192)
    inherits_parent = models.BooleanField(default=False)
    priority = models.IntegerField(default=0)
    efc_up = models.BooleanField(default=False)
    efc_down = models.BooleanField(default=True)
    efc_unreachable = models.BooleanField(default=True)
    efc_pending = models.BooleanField(default=False)
    nfc_up = models.BooleanField(default=False)
    nfc_down = models.BooleanField(default=True)
    nfc_unreachable = models.BooleanField(default=True)
    nfc_pending = models.BooleanField(default=False)
    dependency_period = models.ForeignKey("backbone.mon_period")
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("name",)
        app_label = "backbone"


class mon_host_dependency(models.Model):
    idx = models.AutoField(primary_key=True)
    devices = models.ManyToManyField("device", related_name="mhd_devices", blank=True)
    dependent_devices = models.ManyToManyField("device", related_name="mhd_dependent_devices")
    mon_host_dependency_templ = models.ForeignKey("backbone.mon_host_dependency_templ")
    mon_host_cluster = models.ForeignKey("backbone.mon_host_cluster", null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "backbone"


class mon_service_dependency_templ(models.Model):
    idx = models.AutoField(primary_key=True)
    name = models.CharField(unique=True, max_length=192)
    inherits_parent = models.BooleanField(default=False)
    priority = models.IntegerField(default=0)
    efc_ok = models.BooleanField(default=False)
    efc_warn = models.BooleanField(default=True)
    efc_unknown = models.BooleanField(default=True)
    efc_critical = models.BooleanField(default=False)
    efc_pending = models.BooleanField(default=False)
    nfc_ok = models.BooleanField(default=False)
    nfc_warn = models.BooleanField(default=True)
    nfc_unknown = models.BooleanField(default=True)
    nfc_critical = models.BooleanField(default=False)
    nfc_pending = models.BooleanField(default=False)
    dependency_period = models.ForeignKey("backbone.mon_period")
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("name",)
        app_label = "backbone"


class mon_service_dependency(models.Model):
    idx = models.AutoField(primary_key=True)
    devices = models.ManyToManyField("backbone.device", related_name="msd_devices", blank=True)
    mon_check_command = models.ForeignKey("backbone.mon_check_command", related_name="msd_mcc")
    dependent_devices = models.ManyToManyField("backbone.device", related_name="msd_dependent_devices")
    dependent_mon_check_command = models.ForeignKey("backbone.mon_check_command", related_name="msd_dependent_mcc")
    mon_service_dependency_templ = models.ForeignKey("backbone.mon_service_dependency_templ")
    # overrides device and mon_check_command
    mon_service_cluster = models.ForeignKey("backbone.mon_service_cluster", null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "backbone"


class mon_ext_host(models.Model):
    idx = models.AutoField(db_column="ng_ext_host_idx", primary_key=True)
    name = models.CharField(unique=True, max_length=192)
    # png
    icon_image = models.CharField(max_length=192, blank=True)
    icon_image_alt = models.CharField(max_length=192, blank=True)
    vrml_image = models.CharField(max_length=192, blank=True)
    # gd2
    statusmap_image = models.CharField(max_length=192, blank=True)
    date = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return self.name

    def data_image_field(self):
        _url = settings.STATIC_URL + "icinga/{}".format(self.icon_image)
        return _url

    class Meta:
        ordering = ("name",)
        db_table = 'ng_ext_host'
        app_label = "backbone"


class mon_period(models.Model):
    idx = models.AutoField(db_column="ng_period_idx", primary_key=True)
    name = models.CharField(unique=True, max_length=192, default="")
    alias = models.CharField(max_length=255, blank=True, unique=True, default="")
    sun_range = models.CharField(max_length=48, blank=True, db_column="sunrange")
    mon_range = models.CharField(max_length=48, blank=True, db_column="monrange")
    tue_range = models.CharField(max_length=48, blank=True, db_column="tuerange")
    wed_range = models.CharField(max_length=48, blank=True, db_column="wedrange")
    thu_range = models.CharField(max_length=48, blank=True, db_column="thurange")
    fri_range = models.CharField(max_length=48, blank=True, db_column="frirange")
    sat_range = models.CharField(max_length=48, blank=True, db_column="satrange")
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ng_period'
        app_label = "backbone"


class mon_service_templ(models.Model):
    idx = models.AutoField(db_column="ng_service_templ_idx", primary_key=True)
    name = models.CharField(max_length=192, unique=True)
    volatile = models.BooleanField(default=False)
    nsc_period = models.ForeignKey("backbone.mon_period", related_name="service_check_period")
    max_attempts = models.IntegerField(default=1)
    check_interval = models.IntegerField(default=5)
    retry_interval = models.IntegerField(default=10)
    ninterval = models.IntegerField(default=5)
    nsn_period = models.ForeignKey("backbone.mon_period", related_name="service_notify_period")
    nrecovery = models.BooleanField(default=False, verbose_name="Notify on recovery")
    ncritical = models.BooleanField(default=False, verbose_name="Notify when critical")
    nwarning = models.BooleanField(default=False, verbose_name="Notify when warning")
    nunknown = models.BooleanField(default=False, verbose_name="Notify when unknown")
    nflapping = models.BooleanField(default=False, verbose_name="Notify when flapping")
    nplanned_downtime = models.BooleanField(default=False, verbose_name="Notify when planned downtime")
    low_flap_threshold = models.IntegerField(default=0)
    high_flap_threshold = models.IntegerField(default=0)
    flap_detection_enabled = models.BooleanField(default=False)
    flap_detect_ok = models.BooleanField(default=True)
    flap_detect_warn = models.BooleanField(default=False)
    flap_detect_critical = models.BooleanField(default=False)
    flap_detect_unknown = models.BooleanField(default=False)
    # freshness checks
    check_freshness = models.BooleanField(default=False)
    freshness_threshold = models.IntegerField(default=60)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ng_service_templ'
        app_label = "backbone"


class mon_service_esc_templ(models.Model):
    idx = models.AutoField(primary_key=True)
    name = models.CharField(unique=True, max_length=192)
    first_notification = models.IntegerField(default=1)
    last_notification = models.IntegerField(default=1)
    ninterval = models.IntegerField(default=1)
    esc_period = models.ForeignKey("backbone.mon_period")
    nrecovery = models.BooleanField(default=False)
    ncritical = models.BooleanField(default=False)
    nwarning = models.BooleanField(default=False)
    nunknown = models.BooleanField(default=False)
    nflapping = models.BooleanField(default=False)
    nplanned_downtime = models.BooleanField(default=False)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "backbone"


class MonitoringHintEnabledManager(models.Manager):
    def get_queryset(self):
        return super(MonitoringHintEnabledManager, self).get_queryset().filter(enabled=True)


class monitoring_hint(models.Model):
    objects = models.Manager()
    all_enabled = MonitoringHintEnabledManager()
    idx = models.AutoField(primary_key=True)
    device = models.ForeignKey("backbone.device")
    # call idx, for multi-server-call specials
    call_idx = models.IntegerField(default=0)
    # choices not needed, can be any value from special_*
    m_type = models.CharField(max_length=32)  # , choices=[("ipmi", "IPMI"), ("snmp", "SNMP"), ])
    # key of vector or OID
    key = models.CharField(default="", max_length=255)
    # type of value
    v_type = models.CharField(
        default="f",
        choices=[
            ("f", "float"),
            ("i", "integer"),
            ("b", "boolean"),
            ("s", "string"),
        ],
        max_length=6
    )
    # current value
    value_float = models.FloatField(default=0.0)
    value_int = models.IntegerField(default=0)
    value_string = models.CharField(default="", max_length=256, blank=True)
    # limits
    lower_crit_float = models.FloatField(default=0.0)
    lower_warn_float = models.FloatField(default=0.0)
    upper_warn_float = models.FloatField(default=0.0)
    upper_crit_float = models.FloatField(default=0.0)
    lower_crit_int = models.IntegerField(default=0)
    lower_warn_int = models.IntegerField(default=0)
    upper_warn_int = models.IntegerField(default=0)
    upper_crit_int = models.IntegerField(default=0)
    lower_crit_float_source = models.CharField(default="n", choices=[("n", "not set"), ("s", "system"), ("u", "user")], max_length=4)
    lower_warn_float_source = models.CharField(default="n", choices=[("n", "not set"), ("s", "system"), ("u", "user")], max_length=4)
    upper_warn_float_source = models.CharField(default="n", choices=[("n", "not set"), ("s", "system"), ("u", "user")], max_length=4)
    upper_crit_float_source = models.CharField(default="n", choices=[("n", "not set"), ("s", "system"), ("u", "user")], max_length=4)
    lower_crit_int_source = models.CharField(default="n", choices=[("n", "not set"), ("s", "system"), ("u", "user")], max_length=4)
    lower_warn_int_source = models.CharField(default="n", choices=[("n", "not set"), ("s", "system"), ("u", "user")], max_length=4)
    upper_warn_int_source = models.CharField(default="n", choices=[("n", "not set"), ("s", "system"), ("u", "user")], max_length=4)
    upper_crit_int_source = models.CharField(default="n", choices=[("n", "not set"), ("s", "system"), ("u", "user")], max_length=4)
    # info string
    info = models.CharField(default="", max_length=255)
    # enabled
    enabled = models.BooleanField(default=True)
    # used in monitoring
    check_created = models.BooleanField(default=False)
    changed = models.DateTimeField(auto_now=True)  # , default=datetime.datetime.now())
    # persistent: do not remove even when missing from server (for instance openvpn)
    persistent = models.BooleanField(default=False)
    # is check active ?
    is_active = models.BooleanField(default=True)
    # datasource : (c)ache, (s)erver, (p)ersistent
    datasource = models.CharField(max_length=6, default="s", choices=[("c", "cache"), ("s", "server"), ("p", "persistent")])
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "backbone"
        ordering = ("m_type", "key",)
        verbose_name = "Monitoring hint"


########################################
# models for direct data from icinga logs
class mon_icinga_log_raw_base(models.Model):
    idx = models.AutoField(primary_key=True)
    date = models.DateTimeField(db_index=True)
    device = models.ForeignKey("backbone.device", db_index=True, null=True)  # only null for device_independent
    device_independent = models.BooleanField(default=False, db_index=True)  # events which apply to all devices such as icinga shutdown
    # text from log entry
    msg = models.TextField()
    # entry originates from this logfile
    logfile = models.ForeignKey("backbone.mon_icinga_log_file", blank=True, null=True)

    STATE_TYPE_HARD = "H"
    STATE_TYPE_SOFT = "S"
    STATE_UNDETERMINED = "UD"  # state as well as state type
    STATE_UNDETERMINED_LONG = "UNDETERMINED"
    STATE_TYPES = [(STATE_TYPE_HARD, "HARD"), (STATE_TYPE_SOFT, "SOFT"), (STATE_UNDETERMINED, STATE_UNDETERMINED)]

    FLAPPING_START = "START"
    FLAPPING_STOP = "STOP"

    class Meta:
        app_label = "backbone"
        abstract = True


class raw_host_alert_manager(models.Manager):
    def calc_alerts(self, start_time, end_time, device_ids=None):
        host_alerts = defaultdict(lambda: [])

        additional_device_filter = {}
        if device_ids is not None:
            additional_device_filter = {'device__in': device_ids}
        for entry in self.filter(device_independent=False, date__range=(start_time, end_time),
                                 **additional_device_filter):
            host_alerts[entry.device_id].append(entry)
        # calc dev independent afterwards and add to all keys
        for entry in mon_icinga_log_raw_host_alert_data.objects\
                .filter(device_independent=True, date__range=(start_time, end_time)):
            for key in host_alerts:
                host_alerts[key].append(entry)
        for l in host_alerts.values():
            # not in order due to dev independents
            l.sort(key=operator.attrgetter('date'))
        return host_alerts

    def calc_limit_alerts(self, time, mode='last before', device_ids=None):
        """
        Find last alert before or first alert after some point in time for some devices
        :param mode: 'last before' or 'first after'
        """
        return raw_service_alert_manager.do_calc_limit_alerts(self, is_host=True, time=time, mode=mode,
                                                              device_ids=device_ids)


class mon_icinga_log_raw_host_alert_data(mon_icinga_log_raw_base):
    STATE_UP = "UP"
    STATE_DOWN = "D"
    STATE_UNREACHABLE = "UR"
    STATE_CHOICES = [(STATE_UP, "UP"), (STATE_DOWN, "DOWN"), (STATE_UNREACHABLE, "UNREACHABLE"),
                     (mon_icinga_log_raw_base.STATE_UNDETERMINED, mon_icinga_log_raw_base.STATE_UNDETERMINED_LONG)]
    STATE_CHOICES_REVERSE_MAP = {val: key for (key, val) in STATE_CHOICES}

    objects = raw_host_alert_manager()

    state_type = models.CharField(max_length=2, choices=mon_icinga_log_raw_base.STATE_TYPES)
    state = models.CharField(max_length=2, choices=STATE_CHOICES)
    log_rotation_state = models.BooleanField(default=False)  # whether this is an entry at the beginning of a fresh archive file.
    initial_state = models.BooleanField(default=False)  # whether this is an entry after icinga restart


class raw_service_alert_manager(models.Manager):
    def calc_alerts(self, start_time, end_time, device_ids=None):
        service_alerts = defaultdict(lambda: [])

        additional_device_filter = {}
        if device_ids is not None:
            additional_device_filter = {'device__in': device_ids}
        queryset = self.filter(device_independent=False, date__range=(start_time, end_time), **additional_device_filter)
        for entry in queryset:
            key = entry.device_id, entry.service_id, entry.service_info
            service_alerts[key].append(entry)
        # calc dev independent afterwards and add to all keys
        for entry in self.filter(device_independent=True, date__range=(start_time, end_time)):
            for key in service_alerts:
                service_alerts[key].append(entry)
        for l in service_alerts.values():
            # not in order due to dev independents
            l.sort(key=operator.attrgetter('date'))
        return service_alerts

    def calc_limit_alerts(self, time, mode='last before', device_ids=None):
        """
        Find last alert before or first alert after some point in time for some devices
        :param mode: 'last before' or 'first after'
        """
        return raw_service_alert_manager.do_calc_limit_alerts(self, is_host=False, time=time, mode=mode,
                                                              device_ids=device_ids)

    @staticmethod
    def do_calc_limit_alerts(obj_man, is_host, time, mode='last before', device_ids=None):
        assert mode in ('last before', 'first after')

        group_by_fields = ['device_id', 'state', 'state_type']
        additional_fields = ['date', 'msg']
        if not is_host:
            group_by_fields.extend(['service_id', 'service_info'])

        # NOTE: code was written for 'last_before' mode and then generalised, hence some vars are called 'latest...'
        try:
            if mode == 'last before':
                latest_dev_independent_service_alert =\
                    obj_man.filter(date__lte=time, device_independent=True).latest('date')
            else:
                latest_dev_independent_service_alert =\
                    obj_man.filter(date__gte=time, device_independent=True).earliest('date')

            # can't use values() on single entry
            latest_dev_independent_service_alert = {key: getattr(latest_dev_independent_service_alert, key)
                                                    for key in (group_by_fields + additional_fields)}
        except obj_man.model.DoesNotExist:
            latest_dev_independent_service_alert = None

        # get last service alert of each service before the start time
        additional_device_filter = {}
        if device_ids is not None:
            additional_device_filter = {'device__in': device_ids}
        last_service_alert_cache = {}
        if mode == 'last before':
            queryset = obj_man.filter(date__lte=time, device_independent=False, **additional_device_filter)
        else:
            queryset = obj_man.filter(date__gte=time, device_independent=False, **additional_device_filter)

        queryset = queryset.values(*group_by_fields)

        # only get these values and annotate with extreme date, then we get the each field-tuple with their extreme date

        if mode == 'last before':
            queryset = queryset.annotate(extreme_date=Max('date'))
        else:
            queryset = queryset.annotate(extreme_date=Min('date'))

        for entry in queryset:
            # prefer latest info if there is dev independent one

            if mode == 'last before':
                comp = lambda x, y: x > y
            else:
                comp = lambda x, y: x < y
            if latest_dev_independent_service_alert is not None and \
                    comp(latest_dev_independent_service_alert['date'], entry['extreme_date']):
                relevant_entry = latest_dev_independent_service_alert
            else:
                relevant_entry = entry

            if is_host:
                key = entry['device_id']
            else:
                key = entry['device_id'], entry['service_id'], entry['service_info']

            # the query above is not perfect, it should group only by device and service
            # this seems to be hard in django:
            # http://stackoverflow.com/questions/19923877/django-orm-get-latest-for-each-group
            # so we do the last grouping by this key here manually
            if key not in last_service_alert_cache or comp(entry['extreme_date'], last_service_alert_cache[key][1]):
                last_service_alert_cache[key] = relevant_entry, entry['extreme_date']

        # NOTE: apparently, in django, if you use group_by, you can only select the elements you group_by and
        #       the annotated elements therefore we retrieve the extra parameters manually
        for k, v in last_service_alert_cache.items():
            if any(key not in v[0] for key in additional_fields):
                if is_host:
                    additional_fields_query = obj_man.filter(device_id=k, date=v[1])
                else:
                    additional_fields_query = obj_man.filter(device_id=k[0], service_id=k[1], service_info=k[2], date=v[1])

                if len(additional_fields_query) == 0:  # must be dev independent
                    additional_fields_query = obj_man.filter(device_independent=True, date=v[1])

                v[0].update(additional_fields_query.values(*additional_fields)[0])

        # drop extreme date
        return {k: v[0] for (k, v) in last_service_alert_cache.items()}

    @staticmethod
    def calculate_service_name_for_client(entry):
        """
        :param entry: aggregated or raw log model entry. service should be prefetched for reasonable performance.
        """
        return raw_service_alert_manager._do_calculate_service_name_for_client(entry.service, entry.service_info)

    @staticmethod
    def calculate_service_name_for_client_tuple(service_id, service_info):
        try:
            service = mon_check_command.objects.get(pk=service_id)
        except mon_check_command.DoesNotExist:
            service = None
        return raw_service_alert_manager._do_calculate_service_name_for_client(service, service_info)

    @staticmethod
    def _do_calculate_service_name_for_client(service, service_info):
        service_name = service.name if service else ""
        return "{},{}".format(service_name, service_info if service_info else "")


class mon_icinga_log_raw_service_alert_data(mon_icinga_log_raw_base):
    STATE_UNDETERMINED = "UD"
    STATE_CHOICES = [("O", "OK"), ("W", "WARNING"), ("U", "UNKNOWN"), ("C", "CRITICAL"),
                     (mon_icinga_log_raw_base.STATE_UNDETERMINED, mon_icinga_log_raw_base.STATE_UNDETERMINED_LONG)]
    STATE_CHOICES_REVERSE_MAP = {val: key for (key, val) in STATE_CHOICES}

    objects = raw_service_alert_manager()

    # NOTE: there are different setup, at this time only regular check_commands are supported
    # they are identified by the mon_check_command.pk and their name, hence the fields here
    # the layout of this table probably has to change in order to accommodate for further services
    # I however can't do that now as I don't know how what to change it to
    service = models.ForeignKey(mon_check_command, null=True, db_index=True)  # null for device_independent events

    if db_limit_1():
        service_info = models.TextField(blank=True, null=True)
    else:
        service_info = models.TextField(blank=True, null=True, db_index=True)

    state_type = models.CharField(max_length=2, choices=mon_icinga_log_raw_base.STATE_TYPES)
    state = models.CharField(max_length=2, choices=STATE_CHOICES)

    # whether this is an entry at the beginning of a fresh archive file.
    log_rotation_state = models.BooleanField(default=False)
    # whether this is an entry after icinga restart
    initial_state = models.BooleanField(default=False)


class mon_icinga_log_full_system_dump(models.Model):
    # save dates of all full system dumps,
    # i.e. with log_rotation_state = True or inital_state = True in (host|service)-alerts table
    # this is needed for faster access, the alerts-tables are too huge
    idx = models.AutoField(primary_key=True)
    date = models.DateTimeField(db_index=True)


class mon_icinga_log_raw_service_flapping_data(mon_icinga_log_raw_base):
    # see comment in mon_icinga_log_raw_service_alert_data
    service = models.ForeignKey(mon_check_command, null=True)  # null for device_independent events
    service_info = models.TextField(blank=True, null=True)

    flapping_state = models.CharField(max_length=5, choices=[(mon_icinga_log_raw_base.FLAPPING_START, mon_icinga_log_raw_base.FLAPPING_START),
                                                             (mon_icinga_log_raw_base.FLAPPING_STOP, mon_icinga_log_raw_base.FLAPPING_STOP)])


class mon_icinga_log_raw_host_flapping_data(mon_icinga_log_raw_base):
    flapping_state = models.CharField(max_length=5, choices=[(mon_icinga_log_raw_base.FLAPPING_START, mon_icinga_log_raw_base.FLAPPING_START),
                                                             (mon_icinga_log_raw_base.FLAPPING_STOP, mon_icinga_log_raw_base.FLAPPING_STOP)])


class mon_icinga_log_raw_service_notification_data(mon_icinga_log_raw_base):
    # see comment in mon_icinga_log_raw_service_alert_data
    service = models.ForeignKey(mon_check_command, null=True)
    service_info = models.TextField(blank=True, null=True)

    state = models.CharField(max_length=2, choices=mon_icinga_log_raw_service_alert_data.STATE_CHOICES)
    user = models.TextField()
    notification_type = models.TextField()


class mon_icinga_log_raw_host_notification_data(mon_icinga_log_raw_base):
    state = models.CharField(max_length=2, choices=mon_icinga_log_raw_host_alert_data.STATE_CHOICES)
    user = models.TextField()
    notification_type = models.TextField()


class mon_icinga_log_file(models.Model):
    idx = models.AutoField(primary_key=True)
    filepath = models.TextField()

    class Meta:
        app_label = "backbone"


class _last_read_manager(models.Manager):
    def get_last_read(self):
        """
        @return int timestamp
        """
        if self.all():
            return self.all()[0]
        else:
            return None


class mon_icinga_log_last_read(models.Model):
    # this table contains only one row
    idx = models.AutoField(primary_key=True)
    position = models.BigIntegerField()  # position of start of last line read
    timestamp = models.IntegerField()  # time of last line read

    objects = _last_read_manager()

    class Meta:
        app_label = "backbone"


########################################
# models for aggregated data from icinga


class mon_icinga_log_aggregated_timespan(models.Model):
    idx = models.AutoField(primary_key=True)
    end_date = models.DateTimeField()
    start_date = models.DateTimeField(db_index=True)
    duration = models.IntegerField()  # seconds
    duration_type = models.IntegerField(db_index=True)  # durations pseudo enum from functions

    class Meta:
        app_label = "backbone"


class mon_icinga_log_aggregated_host_data(models.Model):
    STATE_FLAPPING = "FL"  # this is also a state type
    STATE_CHOICES = mon_icinga_log_raw_host_alert_data.STATE_CHOICES + [(STATE_FLAPPING, "FLAPPING")]
    STATE_CHOICES_REVERSE_MAP = {val: key for (key, val) in STATE_CHOICES}

    STATE_TYPES = mon_icinga_log_raw_base.STATE_TYPES + [(STATE_FLAPPING, STATE_FLAPPING)]

    idx = models.AutoField(primary_key=True)
    device = models.ForeignKey("backbone.device")
    timespan = models.ForeignKey(mon_icinga_log_aggregated_timespan)

    state_type = models.CharField(max_length=2, choices=STATE_TYPES)
    state = models.CharField(max_length=2, choices=STATE_CHOICES)

    # ratio of time span spent in this (state_type, state)
    value = models.FloatField()

    class Meta:
        app_label = "backbone"


class mon_icinga_log_aggregated_service_data(models.Model):
    STATE_FLAPPING = "FL"
    STATE_CHOICES = mon_icinga_log_raw_service_alert_data.STATE_CHOICES + [(STATE_FLAPPING, "FLAPPING")]
    STATE_CHOICES_REVERSE_MAP = {val: key for (key, val) in STATE_CHOICES}

    idx = models.AutoField(primary_key=True)
    timespan = models.ForeignKey(mon_icinga_log_aggregated_timespan)

    STATE_TYPES = mon_icinga_log_raw_base.STATE_TYPES + [(STATE_FLAPPING, STATE_FLAPPING)]

    device = models.ForeignKey("backbone.device")
    state_type = models.CharField(max_length=2, choices=STATE_TYPES)
    state = models.CharField(max_length=2, choices=STATE_CHOICES)

    # see comment in mon_icinga_log_raw_service_alert_data
    service = models.ForeignKey(mon_check_command, null=True)  # null for old entries for special check commands
    service_info = models.TextField(blank=True, null=True)

    # ratio of time span spent in this (state_type, state)
    value = models.FloatField()

    class Meta:
        app_label = "backbone"
