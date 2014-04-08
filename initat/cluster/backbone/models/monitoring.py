#!/usr/bin/python-init

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, signals
from django.dispatch import receiver
from initat.cluster.backbone.models.functions import _check_empty_string, _check_integer
from rest_framework import serializers
from django.conf import settings
import logging_tools
import re

__all__ = [
    "mon_host_cluster", "mon_host_cluster_serializer",
    "mon_service_cluster", "mon_service_cluster_serializer",
    "host_check_command", "host_check_command_serializer",
    "mon_check_command", "mon_check_command_serializer", "mon_check_command_nat_serializer",
    "mon_check_command_type",
    "mon_contact", "mon_contact_serializer",
    "mon_notification", "mon_notification_serializer",
    "mon_contactgroup", "mon_contactgroup_serializer",
    "mon_device_templ", "mon_device_templ_serializer",
    "mon_device_esc_templ", "mon_device_esc_templ_serializer",
    "mon_host_dependency_templ", "mon_host_dependency_templ_serializer",
    "mon_host_dependency", "mon_host_dependency_serializer",
    "mon_service_dependency_templ", "mon_service_dependency_templ_serializer",
    "mon_service_dependency", "mon_service_dependency_serializer",
    "mon_ext_host", "mon_ext_host_serializer",
    "mon_period", "mon_period_serializer",
    "mon_service_templ", "mon_service_templ_serializer",
    "mon_service_esc_templ", "mon_service_esc_templ_serializer",
    # distribution models
    "mon_dist_master", # "mon_dist_master_serializer",
    "mon_dist_slave", # "mon_dist_slave_serializer",
    ]

# distribution models, one per run
class mon_dist_slave(models.Model):
    idx = models.AutoField(primary_key=True)
    mon_dist_master = models.ForeignKey("backbone.mon_dist_master")
    device = models.ForeignKey("backbone.device")
    # start of build
    config_build_start = models.DateTimeField(default=None, null=True)
    # end of build
    config_build_end = models.DateTimeField(default=None, null=True)
    # start of first sync
    sync_start = models.DateTimeField(default=None, null=True)
    # end of last sync
    sync_end = models.DateTimeField(default=None, null=True)
    # number of distribute runs (==sync)
    num_runs = models.IntegerField(default=0)
    # version of of master relayer / md-config-server / icinga
    relayer_version = models.CharField(max_length=128, default="")
    mon_version = models.CharField(max_length=128, default="")
    # files transfered / number of transfered commands
    num_files = models.IntegerField(default=0)
    num_transfers = models.IntegerField(default=0)
    # pure data
    size_data = models.IntegerField(default=0)
    # with overhead
    size_raw = models.IntegerField(default=0)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        app_label = "backbone"

class mon_dist_master(models.Model):
    idx = models.AutoField(primary_key=True)
    device = models.ForeignKey("backbone.device")
    version = models.IntegerField(default=0)
    # start of build
    config_build_start = models.DateTimeField(default=None, null=True)
    # end of build
    config_build_end = models.DateTimeField(default=None, null=True)
    # total build start
    build_start = models.DateTimeField(default=None, null=True)
    # total build end
    build_end = models.DateTimeField(default=None, null=True)
    # version of of master relayer / md-config-server / icinga
    relayer_version = models.CharField(max_length=128, default="")
    md_version = models.CharField(max_length=128, default="")
    mon_version = models.CharField(max_length=128, default="")
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        app_label = "backbone"
        ordering = ("-idx",)

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
    def __unicode__(self):
        return self.name
    class Meta:
        app_label = "backbone"

class mon_host_cluster_serializer(serializers.ModelSerializer):
    class Meta:
        model = mon_host_cluster

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
    main_device = models.ForeignKey("backbone.device", related_name="main_mon_service_cluster")
    mon_service_templ = models.ForeignKey("backbone.mon_service_templ")
    devices = models.ManyToManyField("backbone.device", related_name="devs_mon_service_cluster")
    mon_check_command = models.ForeignKey("backbone.mon_check_command")
    warn_value = models.IntegerField(default=0)
    error_value = models.IntegerField(default=1)
    # True for user editable (user created) clusters
    user_editable = models.BooleanField(default=True)
    date = models.DateTimeField(auto_now_add=True)
    def __unicode__(self):
        return self.name
    class Meta:
        app_label = "backbone"

class mon_service_cluster_serializer(serializers.ModelSerializer):
    class Meta:
        model = mon_service_cluster

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
    def __unicode__(self):
        return "mcc_%s" % (self.name)
    class Meta:
        app_label = "backbone"

class host_check_command_serializer(serializers.ModelSerializer):
    class Meta:
        model = host_check_command

class mon_check_command(models.Model):
    idx = models.AutoField(db_column="ng_check_command_idx", primary_key=True)
    config_old = models.IntegerField(null=True, blank=True, db_column="config")
    config = models.ForeignKey("backbone.config", db_column="new_config_id")
    # deprecated, now references category tree
    mon_check_command_type = models.ForeignKey("backbone.mon_check_command_type", null=True, default=None, blank=True)
    mon_service_templ = models.ForeignKey("backbone.mon_service_templ", null=True, blank=True)
    # only unique per config
    name = models.CharField(max_length=192) # , unique=True)
    # flag for special commands (@<SREF>@command)
    is_special_command = models.BooleanField(default=False)
    command_line = models.CharField(max_length=765)
    description = models.CharField(max_length=192, blank=True)
    # device = models.ForeignKey("backbone.device", null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    enable_perfdata = models.BooleanField(default=False)
    volatile = models.BooleanField(default=False)
    # categories for this device
    categories = models.ManyToManyField("backbone.category", blank=True)
    # device to exclude
    exclude_devices = models.ManyToManyField("backbone.device", related_name="mcc_exclude_devices", blank=True)
    # event handler settings
    is_event_handler = models.BooleanField(default=False)
    event_handler = models.ForeignKey("self", null=True, default=None, blank=True)
    event_handler_enabled = models.BooleanField(default=True)
    class Meta:
        db_table = u'ng_check_command'
        unique_together = (("name", "config"))
        app_label = "backbone"
    class CSW_Meta:
        permissions = (
            ("setup_monitoring", "Change monitoring settings", False),
        )
    def __unicode__(self):
        return "mcc_%s" % (self.name)

class mon_check_command_serializer(serializers.ModelSerializer):
    class Meta:
        model = mon_check_command

class mon_check_command_nat_serializer(serializers.ModelSerializer):
    config = serializers.SlugRelatedField(slug_field="name")
    class Meta:
        model = mon_check_command

@receiver(signals.pre_save, sender=mon_check_command)
def mon_check_command_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        special_re = re.compile("^@.+@.+$")
        cur_inst.is_special_command = True if special_re.match(cur_inst.name) else False
        if not cur_inst.name:
            raise ValidationError("name is empty")
        if not cur_inst.command_line:
            raise ValidationError("command_line is empty")
        if cur_inst.name in cur_inst.config.mon_check_command_set.exclude(Q(pk=cur_inst.pk)).values_list("name", flat=True):
            raise ValidationError("name already used")
        if not cur_inst.is_event_handler:
            mc_refs = cur_inst.mon_check_command_set.all()
            if len(mc_refs):
                raise ValidationError("still referenced by %s" % (logging_tools.get_plural("check_command", len(mc_refs))))
        if cur_inst.is_special_command and cur_inst.is_event_handler:
            cur_inst.is_event_handler = False
            cur_inst.save()
            raise ValidationError("special command not allowed as event handler")
        if cur_inst.is_event_handler and cur_inst.event_handler_id:
            cur_inst.event_handler = None
            cur_inst.save()
            raise ValidationError("cannot be an event handler and reference to another event handler")

class mon_check_command_type(models.Model):
    idx = models.AutoField(db_column="ng_check_command_type_idx", primary_key=True)
    name = models.CharField(unique=True, max_length=192)
    date = models.DateTimeField(auto_now_add=True)
    def __unicode__(self):
        return self.name
    class Meta:
        db_table = u'ng_check_command_type'
        app_label = "backbone"

class mon_contact(models.Model):
    idx = models.AutoField(db_column="ng_contact_idx", primary_key=True)
    user = models.ForeignKey("backbone.user")
    snperiod = models.ForeignKey("backbone.mon_period", related_name="service_n_period", verbose_name="service period")
    hnperiod = models.ForeignKey("backbone.mon_period", related_name="host_n_period", verbose_name="host period")
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
    notifications = models.ManyToManyField("backbone.mon_notification", blank=True)
    mon_alias = models.CharField(max_length=64, default="", verbose_name="alias", blank=True)
    def get_user_name(self):
        return u"%s (%s %s)" % (
            self.user.login,
            self.user.first_name,
            self.user.last_name,
            )
    def __unicode__(self):
        return unicode(self.user)
    class Meta:
        db_table = u'ng_contact'
        app_label = "backbone"

class mon_contact_serializer(serializers.ModelSerializer):
    user_name = serializers.Field(source="get_user_name")
    class Meta:
        model = mon_contact

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
        ("sms" , "SMS")], blank=False)
    not_type = models.CharField(max_length=8, choices=[
        ("host"   , "Host"),
        ("service", "Service")], blank=False)
    subject = models.CharField(max_length=140, blank=True)
    content = models.CharField(max_length=4096, blank=False)
    enabled = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    def __unicode__(self):
        return "%s (%s via %s)" % (
            self.name,
            self.not_type,
            self.channel,
        )
    class Meta:
        app_label = "backbone"

class mon_notification_serializer(serializers.ModelSerializer):
    class Meta:
        model = mon_notification

@receiver(signals.pre_save, sender=mon_notification)
def mon_notification_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        _cur_inst = kwargs["instance"]


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
    device_groups = models.ManyToManyField("device_group", blank=True)
    members = models.ManyToManyField("backbone.mon_contact", blank=True)
    service_templates = models.ManyToManyField("backbone.mon_service_templ", blank=True)
    service_esc_templates = models.ManyToManyField("backbone.mon_service_esc_templ", blank=True)
    def __unicode__(self):
        return self.name
    class Meta:
        db_table = u'ng_contactgroup'
        app_label = "backbone"

class mon_contactgroup_serializer(serializers.ModelSerializer):
    class Meta:
        model = mon_contactgroup
        fields = ("idx", "name", "alias", "device_groups", "members", "service_templates", "service_esc_templates",)

@receiver(signals.pre_save, sender=mon_contactgroup)
def mon_contactgroup_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        _check_empty_string(cur_inst, "name")

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
    nrecovery = models.BooleanField(default=False)
    ndown = models.BooleanField(default=False)
    nunreachable = models.BooleanField(default=False)
    nflapping = models.BooleanField(default=False)
    nplanned_downtime = models.BooleanField(default=False)
    is_default = models.BooleanField(default=False)
    low_flap_threshold = models.IntegerField(default=0)
    high_flap_threshold = models.IntegerField(default=0)
    flap_detection_enabled = models.BooleanField(default=False)
    flap_detect_up = models.BooleanField(default=True)
    flap_detect_down = models.BooleanField(default=False)
    flap_detect_unreachable = models.BooleanField(default=False)
    date = models.DateTimeField(auto_now_add=True)
    def __unicode__(self):
        return self.name
    class Meta:
        db_table = u'ng_device_templ'
        app_label = "backbone"

class mon_device_templ_serializer(serializers.ModelSerializer):
    class Meta:
        model = mon_device_templ

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
    mon_service_esc_templ = models.ForeignKey("backbone.mon_service_esc_templ")
    ninterval = models.IntegerField(default=1)
    esc_period = models.ForeignKey("backbone.mon_period")
    nrecovery = models.BooleanField(default=False)
    ndown = models.BooleanField(default=False)
    nunreachable = models.BooleanField(default=False)
    nflapping = models.BooleanField(default=False)
    nplanned_downtime = models.BooleanField(default=False)
    date = models.DateTimeField(auto_now_add=True)
    def __unicode__(self):
        return self.name
    class Meta:
        app_label = "backbone"

class mon_device_esc_templ_serializer(serializers.ModelSerializer):
    class Meta:
        model = mon_device_esc_templ

@receiver(signals.pre_save, sender=mon_device_esc_templ)
def mon_device_esc_templ_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        if not cur_inst.name.strip():
            raise ValidationError("name must not be empty")
        for attr_name, min_val, max_val in [
            ("first_notification", 1, 10),
            ("last_notification" , 1, 10),
            ("ninterval"         , 0, 60 * 24)]:
            _check_integer(cur_inst, attr_name, min_val=min_val, max_val=max_val)

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
    @property
    def execution_failure_criteria(self):
        return ",".join([short for short, _long in [("o", "up"), ("d", "down"), ("u", "unreachable"), ("p", "pending")] if getattr(self, "efc_%s" % (_long))]) or "n"
    @property
    def notification_failure_criteria(self):
        return ",".join([short for short, _long in [("o", "up"), ("d", "down"), ("u", "unreachable"), ("p", "pending")] if getattr(self, "nfc_%s" % (_long))]) or "n"
    def __unicode__(self):
        return self.name
    class Meta:
        ordering = ("name",)
        app_label = "backbone"

class mon_host_dependency_templ_serializer(serializers.ModelSerializer):
    class Meta:
        model = mon_host_dependency_templ

@receiver(signals.pre_save, sender=mon_host_dependency_templ)
def mon_host_dependency_templ_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        _check_integer(cur_inst, "priority", min_val= -128, max_val=128)
        if not cur_inst.name.strip():
            raise ValidationError("name must not be empty")

class mon_host_dependency(models.Model):
    idx = models.AutoField(primary_key=True)
    devices = models.ManyToManyField("device", related_name="mhd_devices", null=True, blank=True)
    dependent_devices = models.ManyToManyField("device", related_name="mhd_dependent_devices")
    mon_host_dependency_templ = models.ForeignKey("backbone.mon_host_dependency_templ")
    mon_host_cluster = models.ForeignKey("backbone.mon_host_cluster", null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    def is_valid(self):
        return True if (self.mon_host_dependency_templ_id) else False
    def get_id(self, devices=None, dependent_devices=None):
        # returns an unique ID
        return "{%d:%d:[%s]:[%s]}" % (
            self.mon_host_dependency_templ_id or 0,
            self.mon_host_cluster_id or 0,
            ",".join(["%d" % (val) for val in sorted([sub_dev.pk for sub_dev in (devices if devices is not None else self.devices.all())])]),
            ",".join(["%d" % (val) for val in sorted([sub_dev.pk for sub_dev in (dependent_devices if dependent_devices is not None else self.dependent_devices.all())])]),
            )
    def feed_config(self, conf):
        conf["inherits_parent"] = "1" if self.mon_host_dependency_templ.inherits_parent else "0"
        conf["execution_failure_criteria"] = self.mon_host_dependency_templ.execution_failure_criteria
        conf["notification_failure_criteria"] = self.mon_host_dependency_templ.notification_failure_criteria
        conf["dependency_period"] = self.mon_host_dependency_templ.dependency_period.name
    class Meta:
        app_label = "backbone"

class mon_host_dependency_serializer(serializers.ModelSerializer):
    class Meta:
        model = mon_host_dependency

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
    @property
    def execution_failure_criteria(self):
        return ",".join([short for short, _long in [("o", "ok"), ("w", "warn"), ("u", "unknown"), ("c", "critical"), ("p", "pending")] if getattr(self, "efc_%s" % (_long))]) or "n"
    @property
    def notification_failure_criteria(self):
        return ",".join([short for short, _long in [("o", "ok"), ("w", "warn"), ("u", "unknown"), ("c", "critical"), ("p", "pending")] if getattr(self, "nfc_%s" % (_long))]) or "n"
    def __unicode__(self):
        return self.name
    class Meta:
        ordering = ("name",)
        app_label = "backbone"

class mon_service_dependency_templ_serializer(serializers.ModelSerializer):
    class Meta:
        model = mon_service_dependency_templ

@receiver(signals.pre_save, sender=mon_service_dependency_templ)
def mon_service_dependency_templ_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        _check_integer(cur_inst, "priority", min_val= -128, max_val=128)
        if not cur_inst.name.strip():
            raise ValidationError("name must not be empty")

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
    def is_valid(self):
        return True if (self.mon_service_dependency_templ_id and self.mon_check_command_id and self.dependent_mon_check_command_id) else False
    def get_id(self, devices=None, dependent_devices=None):
        # returns an unique ID
        return "{%d:%d:%d:%d:[%s]:[%s]}" % (
            self.mon_check_command_id or 0,
            self.dependent_mon_check_command_id or 0,
            self.mon_service_dependency_templ_id or 0,
            self.mon_service_cluster_id or 0,
            ",".join(["%d" % (val) for val in sorted([sub_dev.pk for sub_dev in (devices if devices is not None else self.devices.all())])]),
            ",".join(["%d" % (val) for val in sorted([sub_dev.pk for sub_dev in (dependent_devices if dependent_devices is not None else self.dependent_devices.all())])]),
            )
    def feed_config(self, conf):
        conf["inherits_parent"] = "1" if self.mon_service_dependency_templ.inherits_parent else "0"
        conf["execution_failure_criteria"] = self.mon_service_dependency_templ.execution_failure_criteria
        conf["notification_failure_criteria"] = self.mon_service_dependency_templ.notification_failure_criteria
        conf["dependency_period"] = self.mon_service_dependency_templ.dependency_period.name
    class Meta:
        app_label = "backbone"

class mon_service_dependency_serializer(serializers.ModelSerializer):
    class Meta:
        model = mon_service_dependency

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
        _url = settings.STATIC_URL + "icinga/%s" % (self.icon_image)
        return _url
    class Meta:
        ordering = ("name",)
        db_table = u'ng_ext_host'
        app_label = "backbone"

class mon_ext_host_serializer(serializers.ModelSerializer):
    data_image = serializers.Field(source="data_image_field")
    class Meta:
        model = mon_ext_host

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
    def __unicode__(self):
        return self.name
    class Meta:
        db_table = u'ng_period'
        app_label = "backbone"

class mon_period_serializer(serializers.ModelSerializer):
    class Meta:
        model = mon_period
        fields = ("idx", "name", "alias", "sun_range", "mon_range", "tue_range",
            "wed_range", "thu_range", "fri_range", "sat_range", "service_check_period",
            # "mon_device_templ_set",
            )
        read_only_fields = ("service_check_period",) # "mon_device_templ_set")

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
    def __unicode__(self):
        return self.name
    class Meta:
        db_table = u'ng_service_templ'
        app_label = "backbone"

class mon_service_templ_serializer(serializers.ModelSerializer):
    class Meta:
        model = mon_service_templ

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
    esc_period = models.ForeignKey("backbone.mon_period")
    nrecovery = models.BooleanField(default=False)
    ncritical = models.BooleanField(default=False)
    nwarning = models.BooleanField(default=False)
    nunknown = models.BooleanField(default=False)
    nflapping = models.BooleanField(default=False)
    nplanned_downtime = models.BooleanField(default=False)
    date = models.DateTimeField(auto_now_add=True)
    def __unicode__(self):
        return self.name
    class Meta:
        app_label = "backbone"

class mon_service_esc_templ_serializer(serializers.ModelSerializer):
    class Meta:
        model = mon_service_esc_templ

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
