#!/usr/bin/python-init

import datetime
import uuid
import re
import time
import inspect
import ipvx_tools
import logging_tools
import pytz
import hashlib
import base64
import logging
import os
from lxml import etree # @UnresolvedImport
from lxml.builder import E # @UnresolvedImport
from rest_framework import serializers

from django.conf import settings
from django.core.exceptions import ValidationError, ImproperlyConfigured
from django.db import models
from django.db.models import Q, signals, get_model
from django.dispatch import receiver
from django.utils.functional import memoize
from django.contrib.contenttypes.models import ContentType

from initat.cluster.backbone.model_functions import _check_empty_string, _check_float, _check_integer, _check_non_empty_string

class mon_host_cluster(models.Model):
    idx = models.AutoField(primary_key=True)
    name = models.CharField(max_length=128, blank=False, null=False, unique=True)
    description = models.CharField(max_length=255, default="")
    main_device = models.ForeignKey("device", related_name="main_mon_host_cluster")
    mon_service_templ = models.ForeignKey("mon_service_templ")
    devices = models.ManyToManyField("device", related_name="devs_mon_host_cluster")
    warn_value = models.IntegerField(default=0)
    error_value = models.IntegerField(default=1)
    date = models.DateTimeField(auto_now_add=True)
    def get_xml(self):
        return E.mon_host_cluster(
            unicode(self),
            pk="%d" % (self.pk),
            key="monhc__%d" % (self.pk),
            name=self.name,
            main_device="%d" % (self.main_device_id),
            mon_service_templ="%d" % (self.mon_service_templ_id),
            devices="::".join(["%d" % (cur_pk) for cur_pk in self.devices.all().values_list("pk", flat=True)]),
            warn_value="%d" % (self.warn_value),
            error_value="%d" % (self.error_value),
            description=self.description,
        )
    def __unicode__(self):
        return self.name

@receiver(signals.pre_save, sender=mon_host_cluster)
def mon_host_cluster_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        _check_empty_string(cur_inst, "name")
        for attr_name, min_val, max_val in [
            ("warn_value" , 0, 128),
            ("error_value", 0, 128)]:
            _check_integer(cur_inst, attr_name, min_val=min_val, max_val=max_val)

class mon_service_cluster(models.Model):
    idx = models.AutoField(primary_key=True)
    name = models.CharField(max_length=128, blank=False, null=False, unique=True)
    description = models.CharField(max_length=255, default="")
    main_device = models.ForeignKey("device", related_name="main_mon_service_cluster")
    mon_service_templ = models.ForeignKey("mon_service_templ")
    devices = models.ManyToManyField("device", related_name="devs_mon_service_cluster")
    mon_check_command = models.ForeignKey("mon_check_command")
    warn_value = models.IntegerField(default=0)
    error_value = models.IntegerField(default=1)
    date = models.DateTimeField(auto_now_add=True)
    def get_xml(self):
        return E.mon_service_cluster(
            unicode(self),
            pk="%d" % (self.pk),
            key="monsc__%d" % (self.pk),
            name=self.name,
            main_device="%d" % (self.main_device_id),
            mon_service_templ="%d" % (self.mon_service_templ_id),
            mon_check_command="%d" % (self.mon_check_command_id),
            devices="::".join(["%d" % (cur_pk) for cur_pk in self.devices.all().values_list("pk", flat=True)]),
            warn_value="%d" % (self.warn_value),
            error_value="%d" % (self.error_value),
            description=self.description,
        )
    def __unicode__(self):
        return self.name

@receiver(signals.pre_save, sender=mon_service_cluster)
def mon_service_cluster_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        _check_empty_string(cur_inst, "name")
        for attr_name, min_val, max_val in [
            ("warn_value" , 0, 128),
            ("error_value", 0, 128)]:
            _check_integer(cur_inst, attr_name, min_val=min_val, max_val=max_val)

class host_check_command(models.Model):
    idx = models.AutoField(db_column="ng_check_command_idx", primary_key=True)
    name = models.CharField(max_length=64, unique=True, blank=False, null=False)
    command_line = models.CharField(max_length=128, unique=True, blank=False, null=False)
    date = models.DateTimeField(auto_now_add=True)
    def get_xml(self):
        return E.host_check_command(
            self.name,
            pk="%d" % (self.pk),
            key="hcc__%d" % (self.pk),
            name=self.name,
            command_line=self.command_line,
        )
    def __unicode__(self):
        return "mcc_%s" % (self.name)

class mon_check_command(models.Model):
    idx = models.AutoField(db_column="ng_check_command_idx", primary_key=True)
    config_old = models.IntegerField(null=True, blank=True, db_column="config")
    config = models.ForeignKey("config", db_column="new_config_id")
    # deprecated, now references category tree
    mon_check_command_type = models.ForeignKey("mon_check_command_type", null=True, default=None)
    mon_service_templ = models.ForeignKey("mon_service_templ", null=True)
    # only unique per config
    name = models.CharField(max_length=192) # , unique=True)
    command_line = models.CharField(max_length=765)
    description = models.CharField(max_length=192, blank=True)
    # device = models.ForeignKey("device", null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    enable_perfdata = models.BooleanField(default=False)
    volatile = models.BooleanField(default=False)
    # categories for this device
    categories = models.ManyToManyField("category")
    # device to exclude
    exclude_devices = models.ManyToManyField("device", related_name="mcc_exclude_devices")
    def get_xml(self, with_exclude_devices=False):
        r_xml = E.mon_check_command(
            self.name,
            pk="%d" % (self.pk),
            key="moncc__%d" % (self.pk),
            config="%d" % (self.config_id),
            mon_service_templ="%d" % (self.mon_service_templ_id or 0),
            name=self.name or "",
            command_line=self.command_line or "",
            description=self.description or "",
            enable_perfdata="1" if self.enable_perfdata else "0",
            volatile="1" if self.volatile else "0",
            categories="::".join(["%d" % (cur_cat.pk) for cur_cat in self.categories.all()]),
        )
        if with_exclude_devices:
            r_xml.attrib["exclude_devices"] = "::".join(["%d" % (cur_dev.pk) for cur_dev in self.exclude_devices.all()])
        return r_xml
    class Meta:
        db_table = u'ng_check_command'
    def __unicode__(self):
        return "mcc_%s" % (self.name)

@receiver(signals.pre_save, sender=mon_check_command)
def mon_check_command_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        if not cur_inst.name:
            raise ValidationError("name is empty")
        if not cur_inst.command_line:
            raise ValidationError("command_line is empty")
        if cur_inst.name in cur_inst.config.mon_check_command_set.exclude(Q(pk=cur_inst.pk)).values_list("name", flat=True):
            raise ValidationError("name already used")

class mon_check_command_type(models.Model):
    idx = models.AutoField(db_column="ng_check_command_type_idx", primary_key=True)
    name = models.CharField(unique=True, max_length=192)
    date = models.DateTimeField(auto_now_add=True)
    def get_xml(self):
        return E.mon_check_command_type(
            unicode(self),
            pk="%d" % (self.pk),
            key="ngcct__%d" % (self.pk),
            name=self.name or ""
        )
    def __unicode__(self):
        return self.name
    class Meta:
        db_table = u'ng_check_command_type'

class mon_contact(models.Model):
    idx = models.AutoField(db_column="ng_contact_idx", primary_key=True)
    user = models.ForeignKey("user")
    snperiod = models.ForeignKey("mon_period", related_name="service_n_period")
    hnperiod = models.ForeignKey("mon_period", related_name="host_n_period")
    snrecovery = models.BooleanField(default=False)
    sncritical = models.BooleanField(default=False)
    snwarning = models.BooleanField(default=False)
    snunknown = models.BooleanField(default=False)
    sflapping = models.BooleanField(default=False)
    splanned_downtime = models.BooleanField(default=False)
    hnrecovery = models.BooleanField(default=False)
    hndown = models.BooleanField(default=False)
    hnunreachable = models.BooleanField(default=False)
    hflapping = models.BooleanField(default=False)
    hplanned_downtime = models.BooleanField(default=False)
    date = models.DateTimeField(auto_now_add=True)
    notifications = models.ManyToManyField("mon_notification")
    mon_alias = models.CharField(max_length=64, default="")
    def get_xml(self):
        ret_xml = E.mon_contact(
            unicode(self),
            pk="%d" % (self.pk),
            key="moncon__%d" % (self.pk),
            user="%d" % (self.user_id or 0),
            snperiod="%d" % (self.snperiod_id or 0),
            hnperiod="%d" % (self.hnperiod_id or 0),
            notifications="::".join(["%d" % (cur_not.pk) for cur_not in self.notifications.all()]),
            mon_alias="%s" % (unicode(self.mon_alias or "")),
        )
        for bf in ["snrecovery", "sncritical", "snunknown", "snwarning", "sflapping", "splanned_downtime",
                   "hnrecovery", "hndown", "hnunreachable", "hflapping", "hplanned_downtime"]:
            ret_xml.attrib[bf] = "1" if getattr(self, bf) else "0"
        return ret_xml
    def __unicode__(self):
        return unicode(self.user)
    class Meta:
        db_table = u'ng_contact'

@receiver(signals.pre_save, sender=mon_contact)
def mon_contact_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        used_user_ids = mon_contact.objects.exclude(Q(pk=cur_inst.pk)).values_list("user", flat=True)
        if cur_inst.user_id in used_user_ids:
            raise ValidationError("user already in used by mon_contact")

class mon_notification(models.Model):
    idx = models.AutoField(primary_key=True)
    name = models.CharField(max_length=128, blank=False, unique=True)
    channel = models.CharField(max_length=8, choices=[
        ("mail", "E-Mail"),
        ("sms" , "SMS")])
    not_type = models.CharField(max_length=8, choices=[
        ("host"   , "Host"),
        ("service", "Service")])
    subject = models.CharField(max_length=140, blank=False)
    content = models.CharField(max_length=512, blank=False)
    enabled = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    def get_xml(self):
        return E.mon_notification(
            unicode(self),
            pk="%d" % (self.pk),
            key="monn__%d" % (self.pk),
            name=self.name,
            channel=self.channel,
            not_type=self.not_type,
            subject=self.subject,
            content=self.content,
            enabled="1" if self.enabled else "0",
        )
    def __unicode__(self):
        return "%s (%s via %s)" % (
            self.name,
            self.not_type,
            self.channel,
        )


"""
connection between the various nagios / icinage notification objects:

device -> mon_device_templ -> mon_service_templ
       -> mon_device_esc_templ -> mon_service_esc_templ

contactgroup -> mon_service_templ
             -> mon_service_esc_templ
             -> members
"""

class mon_contactgroup(models.Model):
    idx = models.AutoField(db_column="ng_contactgroup_idx", primary_key=True)
    name = models.CharField(max_length=192, unique=True)
    alias = models.CharField(max_length=255, blank=True, default="")
    date = models.DateTimeField(auto_now_add=True)
    device_groups = models.ManyToManyField("device_group")
    members = models.ManyToManyField("mon_contact")
    service_templates = models.ManyToManyField("mon_service_templ")
    service_esc_templates = models.ManyToManyField("mon_service_esc_templ")
    def get_xml(self):
        return E.mon_contactgroup(
            unicode(self),
            members="::".join(["%d" % (cur_pk) for cur_pk in self.members.all().values_list("pk", flat=True)]),
            device_groups="::".join(["%d" % (cur_pk) for cur_pk in self.device_groups.all().values_list("pk", flat=True)]),
            service_templates="::".join(["%d" % (cur_pk) for cur_pk in self.service_templates.all().values_list("pk", flat=True)]),
            service_esc_templates="::".join(["%d" % (cur_pk) for cur_pk in self.service_esc_templates.all().values_list("pk", flat=True)]),
            pk="%d" % (self.pk),
            key="moncg__%d" % (self.pk),
            name=self.name,
            alias=self.alias,
        )
    def __unicode__(self):
        return self.name
    class Meta:
        db_table = u'ng_contactgroup'

@receiver(signals.pre_save, sender=mon_contactgroup)
def mon_contactgroup_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        _check_empty_string(cur_inst, "name")

class mon_device_templ(models.Model):
    idx = models.AutoField(db_column="ng_device_templ_idx", primary_key=True)
    name = models.CharField(unique=True, max_length=192)
    mon_service_templ = models.ForeignKey("mon_service_templ")
    host_check_command = models.ForeignKey(host_check_command, null=True)
    # check interval
    check_interval = models.IntegerField(default=1)
    # retry interval
    retry_interval = models.IntegerField(default=1)
    # max_check_attempts
    max_attempts = models.IntegerField(null=True, blank=True, default=1)
    # notification interval
    ninterval = models.IntegerField(null=True, blank=True, default=1)
    # monitoring period
    mon_period = models.ForeignKey("mon_period", null=True, blank=True)
    # Notificiation Flags
    nrecovery = models.BooleanField(default=False)
    ndown = models.BooleanField(default=False)
    nunreachable = models.BooleanField(default=False)
    nflapping = models.BooleanField(default=False)
    nplanned_downtime = models.BooleanField(default=False)
    is_default = models.BooleanField()
    low_flap_threshold = models.IntegerField(default=0)
    high_flap_threshold = models.IntegerField(default=0)
    flap_detection_enabled = models.BooleanField(default=False)
    flap_detect_up = models.BooleanField(default=True)
    flap_detect_down = models.BooleanField(default=False)
    flap_detect_unreachable = models.BooleanField(default=False)
    date = models.DateTimeField(auto_now_add=True)
    def get_xml(self):
        return E.mon_device_templ(
            unicode(self),
            pk="%d" % (self.pk),
            key="mondt__%d" % (self.pk),
            name=self.name,
            host_check_command="%d" % (self.host_check_command_id or 0),
            mon_service_templ="%d" % (self.mon_service_templ_id or 0),
            check_interval="%d" % (self.check_interval),
            retry_interval="%d" % (self.retry_interval),
            max_attempts="%d" % (self.max_attempts or 0),
            ninterval="%d" % (self.ninterval or 0),
            mon_period="%d" % (self.mon_period_id or 0),
            nrecovery="%d" % (1 if self.nrecovery else 0),
            ndown="%d" % (1 if self.ndown else 0),
            nunreachable="%d" % (1 if self.nunreachable else 0),
            nflapping="%d" % (1 if self.nflapping else 0),
            nplanned_downtime="%d" % (1 if self.nplanned_downtime else 0),
            low_flap_threshold="%d" % (self.low_flap_threshold),
            high_flap_threshold="%d" % (self.high_flap_threshold),
            flap_detection_enabled="%d" % (1 if self.flap_detection_enabled else 0),
            flap_detect_up="%d" % (1 if self.flap_detect_up else 0),
            flap_detect_down="%d" % (1 if self.flap_detect_down else 0),
            flap_detect_unreachable="%d" % (1 if self.flap_detect_unreachable else 0),
        )
    def __unicode__(self):
        return self.name
    class Meta:
        db_table = u'ng_device_templ'

@receiver(signals.pre_save, sender=mon_device_templ)
def mon_device_templ_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        if not cur_inst.name.strip():
            raise ValidationError("name must not be zero")
        for attr_name, min_val, max_val in [
            ("max_attempts"       , 1, 10),
            ("ninterval"          , 0, 60 * 24),
            ("low_flap_threshold" , 0, 100),
            ("high_flap_threshold", 0, 100),
            ("check_interval"     , 1, 60),
            ("retry_interval"     , 1, 60),
            ]:
            _check_integer(cur_inst, attr_name, min_val=min_val, max_val=max_val)

class mon_device_esc_templ(models.Model):
    idx = models.AutoField(primary_key=True)
    name = models.CharField(unique=True, max_length=192)
    first_notification = models.IntegerField(default=1)
    last_notification = models.IntegerField(default=1)
    mon_service_esc_templ = models.ForeignKey("mon_service_esc_templ")
    ninterval = models.IntegerField(default=1)
    esc_period = models.ForeignKey("mon_period")
    nrecovery = models.BooleanField()
    ndown = models.BooleanField()
    nunreachable = models.BooleanField()
    nflapping = models.BooleanField(default=False)
    nplanned_downtime = models.BooleanField(default=False)
    date = models.DateTimeField(auto_now_add=True)
    def get_xml(self):
        return E.mon_device_esc_templ(
            unicode(self),
            pk="%d" % (self.pk),
            key="mondet__%d" % (self.pk),
            name=self.name,
            first_notification="%d" % (self.first_notification),
            last_notification="%d" % (self.last_notification),
            mon_service_esc_templ="%d" % (self.mon_service_esc_templ_id or 0),
            ninterval="%d" % (self.ninterval or 0),
            esc_period="%d" % (self.esc_period_id or 0),
            nrecovery="%d" % (1 if self.nrecovery else 0),
            nflapping="%d" % (1 if self.nflapping else 0),
            nplanned_downtime="%d" % (1 if self.nplanned_downtime else 0),
            ndown="%d" % (1 if self.ndown else 0),
            nunreachable="%d" % (1 if self.nunreachable else 0),
        )
    def __unicode__(self):
        return self.name

@receiver(signals.pre_save, sender=mon_device_esc_templ)
def mon_device_esc_templ_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        if not cur_inst.name.strip():
            raise ValidationError("name must not be empty")
        for attr_name, min_val, max_val in [
            ("first_notification", 1, 10),
            ("last_notification" , 1, 10),
            ("ninterval"         , 0, 60)]:
            _check_integer(cur_inst, attr_name, min_val=min_val, max_val=max_val)

class mon_host_dependency(models.Model):
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
    dependency_period = models.ForeignKey("mon_period")
    @property
    def execution_failure_criteria(self):
        return ",".join([short for short, long in [("o", "up"), ("d", "down"), ("u", "unreachable"), ("p", "pending")] if getattr(self, "efc_%s" % (long))]) or "n"
    @property
    def notification_failure_criteria(self):
        return ",".join([short for short, long in [("o", "up"), ("d", "down"), ("u", "unreachable"), ("p", "pending")] if getattr(self, "nfc_%s" % (long))]) or "n"
    def get_xml(self):
        r_xml = E.mon_host_dependency(
            unicode(self),
            pk="%d" % (self.pk),
            priority="%d" % (self.priority),
            key="monhd__%d" % (self.pk),
            name=self.name,
            dependency_period="%d" % (self.dependency_period_id),
        )
        for b_type in ["e", "n"]:
            for c_type in ["up", "down", "unreachable", "pending"]:
                attr_name = "%sfc_%s" % (b_type, c_type)
                r_xml.attrib[attr_name] = "1" if getattr(self, attr_name) else "0"
        return r_xml
    def __unicode__(self):
        return self.name
    class Meta:
        ordering = ("name",)

@receiver(signals.pre_save, sender=mon_host_dependency)
def mon_host_dependency_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        _check_integer(cur_inst, "priority", min_val= -128, max_val=128)
        if not cur_inst.name.strip():
            raise ValidationError("name must not be empty")

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
    def get_xml(self, with_images=False):
        cur_xml = E.mon_ext_host(
            unicode(self),
            name=self.name,
            pk="%d" % (self.pk),
            key="mext__%d" % (self.pk),
            icon_image="%s" % (self.icon_image)
        )
        if with_images:
            cur_xml.attrib["data-image"] = "/icinga/images/logos/%s" % (
                self.icon_image)
        return cur_xml
    def __unicode__(self):
        return self.name
    class Meta:
        ordering = ("name",)
        db_table = u'ng_ext_host'

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
    def get_xml(self):
        ret_xml = E.mon_period(
            unicode(self),
            pk="%d" % (self.pk),
            key="monper__%d" % (self.pk),
            name=unicode(self.name),
            alias=unicode(self.alias),
        )
        for day in ["sun", "mon", "tue", "wed", "thu", "fri", "sat"]:
            ret_xml.attrib["%s_range" % (day)] = getattr(self, "%s_range" % (day))
        return ret_xml
    def __unicode__(self):
        return self.name
    class Meta:
        db_table = u'ng_period'

@receiver(signals.pre_save, sender=mon_period)
def mon_period_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        if not cur_inst.name.strip():
            raise ValidationError("name is empty")
        range_re1 = re.compile("^[0-9]{1,2}:[0-9]{1,2}-[0-9]{1,2}:[0-9]{1,2}$")
        range_re2 = re.compile("^[0-9]{1,2}-[0-9]{1,2}$")
        for day in ["sun", "mon", "tue", "wed", "thu", "fri", "sat"]:
            r_name = "%s_range" % (day)
            cur_val = getattr(cur_inst, r_name)
            re_t1 = range_re1.match(cur_val)
            re_t2 = range_re2.match(cur_val)
            if not (re_t1 or re_t2):
                raise ValidationError("range for %s not correct" % (day))
            else:
                new_val = []
                for cur_time in cur_val.split("-"):
                    if re_t1:
                        hours, minutes = [int(val) for val in cur_time.split(":")]
                    else:
                        hours, minutes = (int(cur_time), 0)
                    if (hours, minutes) in [(24, 0)]:
                        pass
                    elif hours < 0 or hours > 23 or minutes < 0 or minutes > 60:
                        raise ValidationError("illegal time %s (%s)" % (cur_time, day))
                    new_val.append("%02d:%02d" % (hours, minutes))
                setattr(cur_inst, r_name, "-".join(new_val))

# class mon_service(models.Model):
    # idx = models.AutoField(db_column="ng_service_idx", primary_key=True)
    # name = models.CharField(max_length=192)
    # alias = models.CharField(max_length=192, blank=True)
    # command = models.CharField(max_length=192, blank=True)
    # parameter1 = models.CharField(max_length=192, blank=True)
    # parameter2 = models.CharField(max_length=192, blank=True)
    # parameter3 = models.CharField(max_length=192, blank=True)
    # parameter4 = models.CharField(max_length=192, blank=True)
    # date = models.DateTimeField(auto_now_add=True)
    # class Meta:
        # db_table = u'ng_service'

class mon_service_templ(models.Model):
    idx = models.AutoField(db_column="ng_service_templ_idx", primary_key=True)
    name = models.CharField(max_length=192, unique=True)
    volatile = models.BooleanField(default=False)
    nsc_period = models.ForeignKey("mon_period", related_name="service_check_period")
    max_attempts = models.IntegerField(default=1)
    check_interval = models.IntegerField(default=5)
    retry_interval = models.IntegerField(default=10)
    ninterval = models.IntegerField(default=5)
    nsn_period = models.ForeignKey("mon_period", related_name="service_notify_period")
    nrecovery = models.BooleanField(default=False)
    ncritical = models.BooleanField(default=False)
    nwarning = models.BooleanField(default=False)
    nunknown = models.BooleanField(default=False)
    nflapping = models.BooleanField(default=False)
    nplanned_downtime = models.BooleanField(default=False)
    low_flap_threshold = models.IntegerField(default=0)
    high_flap_threshold = models.IntegerField(default=0)
    flap_detection_enabled = models.BooleanField(default=False)
    flap_detect_ok = models.BooleanField(default=True)
    flap_detect_warn = models.BooleanField(default=False)
    flap_detect_critical = models.BooleanField(default=False)
    flap_detect_unknown = models.BooleanField(default=False)
    date = models.DateTimeField(auto_now_add=True)
    def get_xml(self):
        return E.mon_service_templ(
            unicode(self),
            pk="%d" % (self.pk),
            key="monst__%d" % (self.pk),
            name=self.name,
            volatile="1" if self.volatile else "0",
            max_attempts="%d" % (self.max_attempts),
            nsc_period="%d" % (self.nsc_period_id or 0),
            check_interval="%d" % (self.check_interval),
            retry_interval="%d" % (self.retry_interval),
            nsn_period="%d" % (self.nsn_period_id or 0),
            ninterval="%d" % (self.ninterval),
            nrecovery="%d" % (1 if self.nrecovery else 0),
            ncritical="%d" % (1 if self.ncritical else 0),
            nwarning="%d" % (1 if self.nwarning else 0),
            nunknown="%d" % (1 if self.nunknown else 0),
            nflapping="%d" % (1 if self.nflapping else 0),
            nplanned_downtime="%d" % (1 if self.nplanned_downtime else 0),
            low_flap_threshold="%d" % (self.low_flap_threshold),
            high_flap_threshold="%d" % (self.high_flap_threshold),
            flap_detection_enabled="%d" % (1 if self.flap_detection_enabled else 0),
            flap_detect_ok="%d" % (1 if self.flap_detect_ok else 0),
            flap_detect_warn="%d" % (1 if self.flap_detect_warn else 0),
            flap_detect_critical="%d" % (1 if self.flap_detect_critical else 0),
            flap_detect_unknown="%d" % (1 if self.flap_detect_unknown else 0),
        )
    def __unicode__(self):
        return self.name
    class Meta:
        db_table = u'ng_service_templ'

@receiver(signals.pre_save, sender=mon_service_templ)
def mon_service_templ_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        if not cur_inst.name.strip():
            raise ValidationError("name must not be zero")
        for attr_name, min_val, max_val in [
            ("max_attempts"  , 1, 10),
            ("check_interval", 1, 60),
            ("retry_interval", 1, 60),
            ("ninterval"     , 0, 60),
            ("low_flap_threshold" , 0, 100),
            ("high_flap_threshold", 0, 100),
            ]:
            _cur_val = _check_integer(cur_inst, attr_name, min_val=min_val, max_val=max_val)

class mon_service_esc_templ(models.Model):
    idx = models.AutoField(primary_key=True)
    name = models.CharField(unique=True, max_length=192)
    first_notification = models.IntegerField(default=1)
    last_notification = models.IntegerField(default=1)
    ninterval = models.IntegerField(default=1)
    esc_period = models.ForeignKey("mon_period")
    nrecovery = models.BooleanField(default=False)
    ncritical = models.BooleanField(default=False)
    nwarning = models.BooleanField(default=False)
    nunknown = models.BooleanField(default=False)
    nflapping = models.BooleanField(default=False)
    nplanned_downtime = models.BooleanField(default=False)
    date = models.DateTimeField(auto_now_add=True)
    def get_xml(self):
        return E.mon_service_esc_templ(
            unicode(self),
            pk="%d" % (self.pk),
            key="monset__%d" % (self.pk),
            name=self.name,
            first_notification="%d" % (self.first_notification),
            last_notification="%d" % (self.last_notification),
            ninterval="%d" % (self.ninterval or 0),
            esc_period="%d" % (self.esc_period_id or 0),
            nflapping="%d" % (1 if self.nflapping else 0),
            nplanned_downtime="%d" % (1 if self.nplanned_downtime else 0),
            nrecovery="%d" % (1 if self.nrecovery else 0),
            ncritical="%d" % (1 if self.ncritical else 0),
            nwarning="%d" % (1 if self.nwarning else 0),
            nunknown="%d" % (1 if self.nunknown else 0),
        )
    def __unicode__(self):
        return self.name

@receiver(signals.pre_save, sender=mon_service_esc_templ)
def mon_service_esc_templ_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        if not cur_inst.name.strip():
            raise ValidationError("name must not be zero")
        for attr_name, min_val, max_val in [
            ("first_notification", 1, 10),
            ("last_notification" , 1, 10),
            ("ninterval"         , 0, 60)]:
            _check_integer(cur_inst, attr_name, min_val=min_val, max_val=max_val)

