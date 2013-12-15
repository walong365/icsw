#!/usr/bin/python-init

from django.core.exceptions import ValidationError, ImproperlyConfigured
from django.db import models
from django.db.models import Q, signals, get_model
from django.dispatch import receiver
from django.forms import Textarea
from django.utils.functional import memoize
from initat.cluster.backbone.model_functions import _check_empty_string, _check_float, _check_integer, _check_non_empty_string, to_system_tz
from initat.cluster.backbone.mon_models import *
from initat.cluster.backbone.user_models import *
from initat.cluster.backbone.package_models import *
from lxml import etree # @UnresolvedImport
from lxml.builder import E # @UnresolvedImport
from rest_framework import serializers
import base64
import datetime
import hashlib
import inspect
import ipvx_tools
import logging
import logging_tools
import os
import pytz
import re
import time
import uuid

ALLOWED_CFS = ["MAX", "MIN", "AVERAGE"]

# top monitoring category
TOP_MONITORING_CATEGORY = "/mon"
TOP_LOCATION_CATEGORY = "/location"
TOP_CONFIG_CATEGORY = "/config"
TOP_DEVICE_CATEGORY = "/device"

TOP_LOCATIONS = set([
    TOP_MONITORING_CATEGORY,
    TOP_LOCATION_CATEGORY,
    TOP_CONFIG_CATEGORY,
    TOP_DEVICE_CATEGORY,
    ])

# validation REs
valid_domain_re = re.compile("^[a-zA-Z0-9-_]+$")
valid_category_re = re.compile("^[a-zA-Z0-9-_\.]+$")

logger = logging.getLogger(__name__)

class cs_timer(object):
    def __init__(self):
        self.start_time = time.time()
    def __call__(self, what):
        cur_time = time.time()
        log_str = "%s in %s" % (what, logging_tools.get_diff_time_str(cur_time - self.start_time))
        self.start_time = cur_time
        return log_str

def only_wf_perms(in_list):
    return [entry.split("_", 1)[1] for entry in in_list if entry.startswith("backbone.wf_")]

cluster_timezone = pytz.timezone(settings.TIME_ZONE)
system_timezone = pytz.timezone(time.tzname[0])

# cluster_log_source
cluster_log_source = None

def boot_uuid(cur_uuid):
    return "%s-boot" % (cur_uuid[:-5])

class home_export_list(object):
    """ build home_export_list (dict) from DB, used in forms.py and ldap_modules.py """
    def __init__(self):
        exp_entries = device_config.objects.filter(
            Q(config__name__icontains="homedir") &
            Q(config__name__icontains="export") &
            Q(device__device_type__identifier="H")).prefetch_related("config__config_str_set").select_related("device")
        home_exp_dict = {}
        for entry in exp_entries:
            dev_name, act_pk = (entry.device.name,
                                entry.pk)
            home_exp_dict[act_pk] = {
                    "key"          : act_pk,
                    "entry"        : entry,
                    "name"         : dev_name,
                    "homeexport"   : "",
                    "node_postfix" : "",
                    "options"      : "-soft"}
            for c_str in entry.config.config_str_set.all():
                if c_str.name in home_exp_dict[act_pk]:
                    home_exp_dict[act_pk][c_str.name] = c_str.value
        # remove invalid exports (with no homeexport-entry)
        invalid_home_keys = [key for key, value in home_exp_dict.iteritems() if not value["homeexport"]]
        for ihk in invalid_home_keys:
            del home_exp_dict[ihk]
        for key, value in home_exp_dict.iteritems():
            value["info"] = "%s on %s" % (value["homeexport"], value["name"])
        self.exp_dict = home_exp_dict
    def get(self, *args, **kwargs):
        # hacky
        return self.exp_dict[int(kwargs["pk"])][ "entry"]
    def all(self):
        for pk in [s_pk for _s_info, s_pk in sorted([(value["info"], key) for key, value in self.exp_dict.iteritems()])]:
            yield self.exp_dict[pk]["entry"]

class apc_device(models.Model):
    idx = models.AutoField(db_column="idx", primary_key=True)
    device = models.ForeignKey("device")
    power_on_delay = models.IntegerField(null=True, blank=True)
    reboot_delay = models.IntegerField(null=True, blank=True)
    apc_type = models.CharField(max_length=765, blank=True)
    version_info = models.TextField(blank=True)
    num_outlets = models.IntegerField(null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'apc_device'

class architecture(models.Model):
    idx = models.AutoField(db_column="architecture_idx", primary_key=True)
    architecture = models.CharField(default="", unique=True, max_length=128)
    date = models.DateTimeField(auto_now_add=True)
    def get_xml(self):
        return E.architecture(
            self.architecture,
            pk="%d" % (self.idx),
            key="arch__%d" % (self.idx),
            architecture=self.architecture,
        )
    class Meta:
        db_table = u'architecture'
    def __unicode__(self):
        return self.architecture

class architecture_serializer(serializers.ModelSerializer):
    class Meta:
        model = architecture
        fields = ("idx", "architecture",)

# class ccl_event(models.Model):
    # idx = models.AutoField(db_column="ccl_event_idx", primary_key=True)
    # device = models.ForeignKey("device")
    # rrd_data = models.ForeignKey("rrd_data")
    # device_class = models.ForeignKey("device_class")
    # threshold = models.FloatField(null=True, blank=True)
    # threshold_class = models.IntegerField()
    # cluster_event = models.ForeignKey("cluster_event")
    # hysteresis = models.FloatField(null=True, blank=True)
    # disabled = models.BooleanField()
    # date = models.DateTimeField(auto_now_add=True)
    # class Meta:
        # db_table = u'ccl_event'

# class ccl_event_log(models.Model):
    # idx = models.AutoField(db_column="ccl_event_log_idx", primary_key=True)
    # device = models.ForeignKey("device", null=True, blank=True)
    # ccl_event = models.ForeignKey("ccl_event")
    # cluster_event = models.ForeignKey("cluster_event")
    # passive = models.BooleanField()
    # date = models.DateTimeField(auto_now_add=True)
    # class Meta:
        # db_table = u'ccl_event_log'

# class ccl_user_con(models.Model):
    # idx = models.AutoField(db_column="ccl_user_con_idx", primary_key=True)
    # ccl_event = models.ForeignKey("ccl_event")
    # user = models.ForeignKey("user")
    # date = models.DateTimeField(auto_now_add=True)
    # class Meta:
        # db_table = u'ccl_user_con'

# class cluster_event(models.Model):
    # idx = models.AutoField(db_column="cluster_event_idx", primary_key=True)
    # name = models.CharField(unique=True, max_length=96)
    # description = models.CharField(max_length=384, blank=True)
    # color = models.CharField(max_length=18, blank=True)
    # command = models.CharField(max_length=192, blank=True)
    # date = models.DateTimeField(auto_now_add=True)
    # class Meta:
        # db_table = u'cluster_event'

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
    def get_xml(self):
        return E.config_str(
            pk="%d" % (self.pk),
            key="varblob__%d" % (self.pk),
            type="blob",
            name=self.name,
            description=self.description,
            config="%d" % (self.config_id),
            value=self.value or ""
        )
    class Meta:
        db_table = u'config_blob'

@receiver(signals.pre_save, sender=config_blob)
def config_blob_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        _check_empty_string(cur_inst, "name")
        all_var_names = list(cur_inst.config.config_str_set.all().values_list("name", flat=True)) + \
            list(cur_inst.config.config_int_set.all().values_list("name", flat=True)) + \
            list(cur_inst.config.config_bool_set.all().values_list("name", flat=True)) + \
            list(cur_inst.config.config_blob_set.exclude(Q(pk=cur_inst.pk)).values_list("name", flat=True))
        if cur_inst.name in all_var_names:
            raise ValidationError("name already used")

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
    def get_xml(self):
        return E.config_str(
            pk="%d" % (self.pk),
            key="varbool__%d" % (self.pk),
            type="bool",
            name=self.name,
            description=self.description,
            config="%d" % (self.config_id),
            value="1" if self.value else "0"
        )
    def __unicode__(self):
        return "True" if self.value else "False"
    class Meta:
        db_table = u'config_bool'

@receiver(signals.pre_save, sender=config_bool)
def config_bool_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        _check_empty_string(cur_inst, "name")
        all_var_names = list(cur_inst.config.config_str_set.all().values_list("name", flat=True)) + \
            list(cur_inst.config.config_int_set.all().values_list("name", flat=True)) + \
            list(cur_inst.config.config_bool_set.exclude(Q(pk=cur_inst.pk)).values_list("name", flat=True)) + \
            list(cur_inst.config.config_blob_set.all().values_list("name", flat=True))
        if cur_inst.name in all_var_names:
            raise ValidationError("name already used")
        try:
            if type(cur_inst.value) == bool:
                pass
            else:
                if type(cur_inst.value) in [int, long]:
                    cur_inst.value = True if cur_inst.value else False
                else:
                    cur_inst.value = True if (cur_inst.value or "").lower() in ["1", "true", "yes"] else False
        except ValueError:
            raise ValidationError("value cannot be interpret as bool")

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
    def get_xml(self):
        return E.config_str(
            pk="%d" % (self.pk),
            key="varint__%d" % (self.pk),
            type="int",
            name=self.name,
            description=self.description,
            config="%d" % (self.config_id),
            value="%d" % (self.value or 0)
        )
    def __unicode__(self):
        if type(self.value) in [str, unicode]:
            self.value = int(self.value)
        return "%d" % (self.value or 0)
    class Meta:
        db_table = u'config_int'

@receiver(signals.pre_save, sender=config_int)
def config_int_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        _check_empty_string(cur_inst, "name")
        all_var_names = list(cur_inst.config.config_str_set.all().values_list("name", flat=True)) + \
            list(cur_inst.config.config_int_set.exclude(Q(pk=cur_inst.pk)).values_list("name", flat=True)) + \
            list(cur_inst.config.config_bool_set.all().values_list("name", flat=True)) + \
            list(cur_inst.config.config_blob_set.all().values_list("name", flat=True))
        if cur_inst.name in all_var_names:
            raise ValidationError("name '%s' already used" % (cur_inst.name))
        _check_integer(cur_inst, "value")

class config_script(models.Model):
    idx = models.AutoField(db_column="config_script_idx", primary_key=True)
    name = models.CharField(max_length=192)
    description = models.CharField(max_length=765, db_column="descr")
    enabled = models.BooleanField(default=True)
    priority = models.IntegerField(null=True, blank=True)
    config = models.ForeignKey("config", db_column="new_config_id")
    value = models.TextField(blank=True)
    # to be removed
    error_text = models.TextField(blank=True)
    device = models.ForeignKey("device", null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    def get_xml(self):
        self.enabled = self.enabled or False
        return E.config_script(
            pk="%d" % (self.pk),
            key="cscript__%d" % (self.pk),
            name=self.name,
            enabled="1" if self.enabled else "0",
            priority="%d" % (self.priority or 0),
            config="%d" % (self.config_id),
            value=self.value or ""
        )
    class Meta:
        db_table = u'config_script'
        ordering = ("priority", "name",)

@receiver(signals.pre_save, sender=config_script)
def config_script_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        if not cur_inst.name:
            raise ValidationError("name is empty")
        if not cur_inst.value:
            raise ValidationError("value is empty")
        if cur_inst.name in cur_inst.config.config_script_set.exclude(Q(pk=cur_inst.pk)).values_list("name", flat=True):
            raise ValidationError("name already used")
        _check_integer(cur_inst, "priority")

class config_str(models.Model):
    idx = models.AutoField(db_column="config_str_idx", primary_key=True)
    name = models.CharField(max_length=192)
    description = models.CharField(db_column="descr", max_length=765)
    config_old = models.IntegerField(null=True, blank=True, db_column="config")
    config = models.ForeignKey("config", db_column="new_config_id")
    value = models.TextField(blank=True)
    device = models.ForeignKey("device", null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    def get_xml(self):
        return E.config_str(
            pk="%d" % (self.pk),
            key="varstr__%d" % (self.pk),
            type="str",
            name=self.name,
            description=self.description,
            config="%d" % (self.config_id),
            value=self.value or ""
        )
    def __unicode__(self):
        return self.value or u""
    class Meta:
        db_table = u'config_str'
        ordering = ("name",)

@receiver(signals.pre_save, sender=config_str)
def config_str_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        _check_empty_string(cur_inst, "name")
        all_var_names = list(cur_inst.config.config_str_set.exclude(Q(pk=cur_inst.pk)).values_list("name", flat=True)) + \
            list(cur_inst.config.config_int_set.all().values_list("name", flat=True)) + \
            list(cur_inst.config.config_bool_set.all().values_list("name", flat=True)) + \
            list(cur_inst.config.config_blob_set.all().values_list("name", flat=True))
        if cur_inst.name in all_var_names:
            raise ValidationError("name already used")

class device(models.Model):
    idx = models.AutoField(db_column="device_idx", primary_key=True)
    # no longer unique as of 20130531 (ALN)
    # no dots allowed (these parts are now in domain_tree_node)
    name = models.CharField(max_length=192)
    # FIXME
    device_group = models.ForeignKey("device_group", related_name="device_group")
    device_type = models.ForeignKey("device_type")
    alias = models.CharField(max_length=384, blank=True)
    comment = models.CharField(max_length=384, blank=True)
    mon_device_templ = models.ForeignKey("mon_device_templ", null=True)
    mon_device_esc_templ = models.ForeignKey("mon_device_esc_templ", null=True)
    mon_ext_host = models.ForeignKey("mon_ext_host", null=True, blank=True)
    # deprecated
    device_location = models.ForeignKey("device_location", null=True)
    # device_class = models.ForeignKey("device_class")
    # rrd_class = models.ForeignKey("rrd_class", null=True)
    # save_rrd_vectors = models.BooleanField()
    etherboot_valid = models.BooleanField(default=False)
    kernel_append = models.CharField(max_length=384, blank=True)
    newkernel = models.CharField(max_length=192, blank=True)
    new_kernel = models.ForeignKey("kernel", null=True, related_name="new_kernel")
    actkernel = models.CharField(max_length=192, blank=True)
    act_kernel = models.ForeignKey("kernel", null=True, related_name="act_kernel")
    act_kernel_build = models.IntegerField(null=True, blank=True)
    kernelversion = models.CharField(max_length=192, blank=True)
    stage1_flavour = models.CharField(max_length=48, blank=True)
    # removed 20121030 by AL
# #    dom0_memory = models.IntegerField(null=True, blank=True)
# #    xen_guest = models.BooleanField()
    newimage = models.CharField(max_length=765, blank=True)
    new_image = models.ForeignKey("image", null=True, related_name="new_image")
    actimage = models.CharField(max_length=765, blank=True)
    act_image = models.ForeignKey("image", null=True, related_name="act_image")
    imageversion = models.CharField(max_length=192, blank=True)
    partition_table = models.ForeignKey("partition_table", null=True, related_name="new_partition_table")
    act_partition_table = models.ForeignKey("partition_table", null=True, related_name="act_partition_table")
    partdev = models.CharField(max_length=192, blank=True)
    fixed_partdev = models.IntegerField(null=True, blank=True)
    bz2_capable = models.IntegerField(null=True, blank=True)
    new_state = models.ForeignKey("status", null=True, db_column="newstate_id")
    rsync = models.BooleanField(default=False)
    rsync_compressed = models.BooleanField(default=False)
    prod_link = models.ForeignKey("network", db_column="prod_link", null=True)
    # states (with timestamp)
    recvstate = models.TextField(blank=True, default="not set")
    recvstate_timestamp = models.DateTimeField(null=True)
    reqstate = models.TextField(blank=True, default="not set")
    reqstate_timestamp = models.DateTimeField(null=True)
    # uptime (with timestamp)
    uptime = models.IntegerField(default=0)
    uptime_timestamp = models.DateTimeField(null=True, default=None)
    bootnetdevice = models.ForeignKey("netdevice", null=True, related_name="boot_net_device")
    bootserver = models.ForeignKey("device", null=True, related_name="boot_server")
    reachable_via_bootserver = models.BooleanField(default=False)
    dhcp_mac = models.NullBooleanField(null=True, blank=True)
    dhcp_write = models.NullBooleanField(default=False)
    dhcp_written = models.NullBooleanField(default=False)
    dhcp_error = models.CharField(max_length=765, blank=True)
    propagation_level = models.IntegerField(default=0, blank=True)
    last_install = models.CharField(max_length=192, blank=True)
    last_boot = models.CharField(max_length=192, blank=True)
    last_kernel = models.CharField(max_length=192, blank=True)
    root_passwd = models.CharField(max_length=192, blank=True)
    # remove, no longer needed
    # device_mode = models.BooleanField()
    # link to monitor_server (or null for master)
    monitor_server = models.ForeignKey("device", null=True)
    monitor_checks = models.BooleanField(default=True, db_column="nagios_checks")
    # performance data tracking
    enable_perfdata = models.BooleanField(default=False)
    flap_detection_enabled = models.BooleanField(default=False)
    show_in_bootcontrol = models.BooleanField(default=True)
    # not so clever here, better in extra table, FIXME
    # cpu_info = models.TextField(blank=True, null=True)
    # machine uuid, cannot be unique due to MySQL problems with unique TextFields
    uuid = models.TextField(default="", max_length=64) # , unique=True)
    # cluster url
    curl = models.CharField(default="ssh://", max_length=512)
    date = models.DateTimeField(auto_now_add=True)
    # slaves
    master_connections = models.ManyToManyField("self", through="cd_connection", symmetrical=False, related_name="slave_connections")
    # automap root for nagvis
    automap_root_nagvis = models.BooleanField(default=False)
    # parent nagvis
    nagvis_parent = models.ForeignKey("device", null=True, related_name="nagvis_childs")
    # enabled ?
    enabled = models.BooleanField(default=True)
    # try to read relevant data from device via md-config-server
    md_cache_mode = models.IntegerField(choices=[
        (1, "automatic (server)"),
        (2, "never use cache"),
        (3, "once (until successfull)"),
        ], default=1)
    # system name
    domain_tree_node = models.ForeignKey("domain_tree_node", null=True, default=None)
    # categories for this device
    categories = models.ManyToManyField("category")
    @property
    def full_name(self):
        if not self.domain_tree_node_id:
            self.domain_tree_node = domain_tree_node.objects.get(Q(depth=0))
            self.save()
        if self.domain_tree_node.full_name:
            return ".".join([self.name, self.domain_tree_node.full_name])
        else:
            return self.name
    def get_boot_uuid(self):
        return boot_uuid(self.uuid)
    def add_log(self, log_src, log_stat, text, **kwargs):
        return devicelog.new_log(self, log_src, log_stat, text, **kwargs)
    def get_simple_xml(self):
        return E.device(
            unicode(self),
            pk="%d" % (self.pk),
            key="dev__%d" % (self.pk),
            name=self.name
        )
    def get_xml(self, full=True, **kwargs):
        r_xml = E.device(
            unicode(self),
            E.devicelogs(),
            # all master connections
            E.connections(),
            name=self.name,
            comment=self.comment,
            pk="%d" % (self.pk),
            key="dev__%d" % (self.pk),
            # states
            recvstate=self.recvstate,
            reqstate=self.reqstate,
            device_type="%d" % (self.device_type_id),
            device_group="%d" % (self.device_group_id),
            new_kernel="%d" % (self.new_kernel_id or 0),
            act_kernel="%d" % (self.act_kernel_id or 0),
            new_image="%d" % (self.new_image_id or 0),
            act_image="%d" % (self.act_image_id or 0),
            stage1_flavour=unicode(self.stage1_flavour),
            kernel_append=unicode(self.kernel_append),
            monitor_server="%d" % (self.monitor_server_id or 0),
            # target state
            new_state="%d" % (self.new_state_id or 0),
            full_new_state="%d__%d" % (self.new_state_id or 0,
                                       self.prod_link_id or 0),
            boot_dev_name="%s" % (self.bootnetdevice.devname if self.bootnetdevice else "---"),
            boot_dev_macaddr="%s" % (self.bootnetdevice.macaddr if self.bootnetdevice else ""),
            boot_dev_driver="%s" % (self.bootnetdevice.driver if self.bootnetdevice else ""),
            greedy_mode="0" if not self.dhcp_mac else "1",
            bootserver="%d" % (self.bootserver_id or 0),
            nagvis_parent="%d" % (self.nagvis_parent_id or 0),
            dhcp_write="1" if self.dhcp_write else "0",
            partition_table="%d" % (self.partition_table_id if self.partition_table_id else 0),
            act_partition_table="%d" % (self.act_partition_table_id if self.act_partition_table_id else 0),
            mon_device_templ="%d" % (self.mon_device_templ_id or 0),
            mon_device_esc_templ="%d" % (self.mon_device_esc_templ_id or 0),
            monitor_checks="1" if self.monitor_checks else "0",
            mon_ext_host="%d" % (self.mon_ext_host_id or 0),
            curl=unicode(self.curl),
            enable_perfdata="1" if self.enable_perfdata else "0",
            automap_root_nagvis="1" if self.automap_root_nagvis else "0",
            uuid=self.uuid or "",
            enabled="1" if self.enabled else "0",
            # to correct string entries
            md_cache_mode="%d" % (int(self.md_cache_mode)),
            domain_tree_node="%d" % (self.domain_tree_node_id or 0),
            uptime="%d" % (self.uptime or 0),
            categories="::".join(["%d" % (cur_cat.pk) for cur_cat in self.categories.all()]),
            flap_detection_enabled="1" if self.flap_detection_enabled else "0",
        )
        if kwargs.get("full_name", False):
            r_xml.attrib["full_name"] = self.full_name
            r_xml.text = u"%s%s" % (
                self.full_name,
                " (%s)" % (self.comment) if self.comment else "")
        if kwargs.get("with_monitoring", False):
            r_xml.attrib.update(
                {
                    "devs_mon_host_cluster" : "::".join(["%d" % (cur_mhc.pk) for cur_mhc in self.devs_mon_host_cluster.all()]),
                    "devs_mon_service_cluster" : "::".join(["%d" % (cur_mhc.pk) for cur_mhc in self.devs_mon_service_cluster.all()]),
                }
            )
        if full:
            r_xml.extend([
                E.netdevices(*[ndev.get_xml() for ndev in self.netdevice_set.all()])
            ])
        if kwargs.get("add_state", False):
            mother_xml = kwargs["mother_xml"]
            if mother_xml is None:
                # no info from mother, set defaults
                r_xml.attrib.update({
                    "net_state" : "unknown",
                    "network"   : "unknown"})
            else:
                now, recv_ts, req_ts, uptime_ts = (
                    cluster_timezone.localize(datetime.datetime.now()).astimezone(pytz.UTC),
                    self.recvstate_timestamp,
                    self.reqstate_timestamp,
                    self.uptime_timestamp,
                )
                # determine if the node is down / pingable / responding to hoststatus requests
                if not int(mother_xml.get("ok", "0")):
                    # not pingable, down
                    r_xml.attrib["net_state"] = "down"
                    r_xml.attrib["network"] = "unknown"
                else:
                    r_xml.attrib["network"] = mother_xml.attrib["network"]
                    if recv_ts is not None:
                        recv_timeout = (now - recv_ts).seconds
                    else:
                        recv_timeout = 3600
                    if req_ts is not None:
                        req_timeout = (now - req_ts).seconds
                    else:
                        req_timeout = 3600
                    if req_timeout > recv_timeout:
                        # recv_state is newer
                        r_xml.attrib["valid_state"] = "recv"
                    else:
                        # req_state is newer
                        r_xml.attrib["valid_state"] = "req"
                    if min(req_timeout, recv_timeout) > 20:
                        # too long ago, deem as outdated (not reachable by mother)
                        r_xml.attrib["net_state"] = "ping"
                    else:
                        r_xml.attrib["net_state"] = "up"
                    # uptime setting
                    if uptime_ts is not None:
                        uptime_timeout = (now - uptime_ts).seconds
                    else:
                        uptime_timeout = 3600
                    if uptime_timeout > 30:
                        # too long ago, outdated
                        r_xml.attrib["uptime_valid"] = "0"
                    else:
                        r_xml.attrib["uptime_valid"] = "1"
                        r_xml.attrib["uptime"] = "%d" % (self.uptime)
        if kwargs.get("with_variables", False):
            r_xml.append(
                E.device_variables(
                    *[cur_dv.get_xml() for cur_dv in self.device_variable_set.all()]
                )
            )
        if kwargs.get("with_partition", False):
            if self.act_partition_table_id:
                r_xml.append(
                    self.act_partition_table.get_xml()
                )
        if kwargs.get("with_md_cache", False):
            r_xml.append(
                E.md_check_data_stores(
                    *[cur_md.get_xml() for cur_md in self.md_check_data_store_set.all()]
                )
            )
        return r_xml
    def latest_contact(self):
        lc_obj = [obj for obj in self.device_variable_set.all() if obj.name == "package_server_last_contact"]
        if lc_obj:
            return int(time.mktime(to_system_tz(lc_obj[0].val_date).timetuple()))
        else:
            return 0
    def __unicode__(self):
        return u"%s%s" % (
            self.name,
            " (%s)" % (self.comment) if self.comment else "")
    class CSW_Meta:
        permissions = (
            ("all_devices", "access all devices", False),
            ("show_graphs", "Access to device graphs", True),
            ("change_network", "Change network", True),
            # (""),
            # ("wf_apc" , "APC control"),
        )
    class Meta:
        db_table = u'device'
        ordering = ("name",)
        unique_together = [("name", "domain_tree_node"), ]

class device_serializer(serializers.ModelSerializer):
    full_name = serializers.Field(source="full_name")
    class Meta:
        model = device
        fields = ("idx", "name", "device_group", "device_type",
            "comment", "full_name", "domain_tree_node", "enabled",
            )

class device_serializer_package_state(device_serializer):
    package_device_connection_set = package_device_connection_serializer(many=True)
    # package_
    latest_contact = serializers.Field(source="latest_contact")
    class Meta:
        model = device
        fields = ("idx", "name", "device_group", "device_type",
            "comment", "full_name", "domain_tree_node", "enabled",
            "package_device_connection_set", "latest_contact",
            )

@receiver(signals.pre_save, sender=device)
def device_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        _check_empty_string(cur_inst, "name")
        if cur_inst.name.count("."):
            short_name, dom_name = cur_inst.name.split(".", 1)
            try:
                cur_dnt = domain_tree_node.objects.get(Q(full_name=dom_name))
            except domain_tree_node.DoesNotExist:
                # create new domain
                if settings.AUTO_CREATE_NEW_DOMAINS:
                    cur_inst.domain_tree_node = domain_name_tree().add_domain(dom_name)
                    cur_inst.name = short_name
                else:
                    raise ValidationError("domain '%s' not defined" % (dom_name))
            else:
                cur_inst.domain_tree_node = cur_dnt
                cur_inst.name = short_name
        else:
            top_level_dn = domain_tree_node.objects.get(Q(depth=0))
            if not cur_inst.domain_tree_node_id:
                cur_inst.domain_tree_node = top_level_dn
            if not cur_inst.pk:
                if cur_inst.domain_tree_node_id == top_level_dn.pk:
                    if cur_inst.device_group.device_id:
                        # set domain_node to domain_node of meta_device
                        cur_inst.domain_tree_node = cur_inst.device_group.device.domain_tree_node
                    else:
                        # no meta device (i am the new meta device, ignore)
                        pass
            # raise ValidationError("no dots allowed in device name '%s'" % (cur_inst.name))
        if not valid_domain_re.match(cur_inst.name):
            # check if we can simple fix it
            if not valid_domain_re.match(cur_inst.name.replace(" ", "_")):
                raise ValidationError("illegal characters in name '%s'" % (cur_inst.name))
            else:
                cur_inst.name = cur_inst.name.replace(" ", "_")
        if int(cur_inst.md_cache_mode) == 0:
            cur_inst.md_cache_mode = 1
        _check_integer(cur_inst, "md_cache_mode", min_val=1, max_val=3)
        if not cur_inst.uuid:
            cur_inst.uuid = str(uuid.uuid4())
        # check for uniqueness of UUID
        try:
            present_dev = device.objects.get(Q(uuid=cur_inst.uuid))
        except device.DoesNotExist:
            pass
        else:
            if present_dev.pk != cur_inst.pk:
                raise ValidationError("UUID clash (=%s for %s and %s)" % (
                    cur_inst.uuid,
                    unicode(cur_inst),
                    unicode(present_dev),
                    ))
        # Check if the device limit is reached, disabled as of 2013-10-14 (AL)
        if False:
            dev_count = settings.CLUSTER_LICENSE["device_count"]

            # Exclude special meta devices
            md_type = device_type.objects.get(identifier="MD")
            current_count = device.objects.exclude(device_type=md_type).count()

            if dev_count > 0 and current_count >= dev_count:
                logger.warning("Device limit %d reached", dev_count)
                raise ValidationError("Device limit reached!")

class device_config(models.Model):
    idx = models.AutoField(db_column="device_config_idx", primary_key=True)
    device = models.ForeignKey("device")
    config = models.ForeignKey("config", db_column="new_config_id")
    date = models.DateTimeField(auto_now_add=True)
    def get_xml(self):
        return E.device_config(
            pk="%d" % (self.pk),
            key="dc__%d" % (self.pk),
            device="%d" % (self.device_id),
            config="%d" % (self.config_id)
        )
    class Meta:
        db_table = u'device_config'

class cd_connection(models.Model):
    # controlling_device connection
    idx = models.AutoField(primary_key=True)
    parent = models.ForeignKey("device", related_name="parent_device")
    child = models.ForeignKey("device", related_name="child_device")
    created_by = models.ForeignKey("user", null=True)
    connection_info = models.CharField(max_length=256, default="not set")
    parameter_i1 = models.IntegerField(default=0)
    parameter_i2 = models.IntegerField(default=0)
    parameter_i3 = models.IntegerField(default=0)
    parameter_i4 = models.IntegerField(default=0)
    date = models.DateTimeField(auto_now_add=True)
    def get_xml(self):
        return E.cd_connection(
            unicode(self),
            pk="%d" % (self.pk),
            key="cd_connection__%d" % (self.pk),
            parent="%d" % (self.parent_id),
            parent_name=unicode(self.parent),
            child="%d" % (self.child_id),
            child_name=unicode(self.child),
            created_by="%d" % (self.created_by_id or 0),
            connection_info=self.connection_info,
            parameter_i1="%d" % (self.parameter_i1),
            parameter_i2="%d" % (self.parameter_i2),
            parameter_i3="%d" % (self.parameter_i3),
            parameter_i4="%d" % (self.parameter_i4),
            )
    def __unicode__(self):
        return "%s (via %s) %s" % (
            unicode(self.parent),
            self.connection_info,
            unicode(self.child))
    class Meta:
        ordering = ("parent__name", "child__name",)

@receiver(signals.pre_save, sender=cd_connection)
def cd_connection_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        for par_idx in xrange(1, 5):
            _check_integer(cur_inst, "parameter_i%d" % (par_idx), min_val=0, max_val=100)
        try:
            cd_connection.objects.get(Q(parent=cur_inst.parent_id) & Q(child=cur_inst.child_id))
        except cd_connection.DoesNotExist:
            pass
        except cd_connection.MultipleObjectsReturned:
            raise ValidationError("connections already exist")
        else:
            if cur_inst.pk is None:
                raise ValidationError("connection already exists")

class device_selection(models.Model):
    idx = models.AutoField(db_column="device_selection_idx", primary_key=True)
    name = models.CharField(unique=True, max_length=192)
    user = models.ForeignKey("user", null=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'device_selection'

class device_device_selection(models.Model):
    idx = models.AutoField(db_column="device_device_selection_idx", primary_key=True)
    device_selection = models.ForeignKey("device_selection")
    device = models.ForeignKey("device")
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'device_device_selection'

class device_group(models.Model):
    idx = models.AutoField(db_column="device_group_idx", primary_key=True)
    name = models.CharField(unique=True, max_length=192, blank=False)
    description = models.CharField(max_length=384, default="")
    # device = models.ForeignKey("device", null=True, blank=True, related_name="group_device")
    # must be an IntegerField, otherwise we have a cycle reference
    # device = models.IntegerField(null=True, blank=True)
    device = models.ForeignKey("device", db_column="device", null=True, blank=True, related_name="group_device")
    # flag
    cluster_device_group = models.BooleanField(default=False)
    enabled = models.BooleanField(default=True)
    date = models.DateTimeField(auto_now_add=True)
    def _add_meta_device(self):
        new_md = device(name=self.get_metadevice_name(),
                        device_group=self,
                        # device_class=device_class.objects.get(Q(pk=1)),
                        device_type=device_type.objects.get(Q(identifier="MD")))
        new_md.save()
        self.device = new_md
        self.save()
        return new_md
    def get_metadevice_name(self):
        return "METADEV_%s" % (self.name)
    def get_xml(self,
                full=True,
                with_devices=True,
                with_variables=False,
                with_monitoring=False,
                ignore_enabled=False,
                full_name=False):
        cur_xml = E.device_group(
            unicode(self),
            pk="%d" % (self.pk),
            key="devg__%d" % (self.pk),
            name=self.name,
            description=self.description or "",
            is_cdg="1" if self.cluster_device_group else "0",
            enabled="1" if self.enabled else "0",
        )
        if with_devices:
            if ignore_enabled:
                sub_list = self.device_group.all()
            else:
                # manual filtering, otherwise we would trigger a new DB-query
                sub_list = [cur_dev for cur_dev in self.device_group.all() if cur_dev.enabled]
            cur_xml.append(
                E.devices(*[cur_dev.get_xml(
                    full=full,
                    with_variables=with_variables,
                    with_monitoring=with_monitoring,
                    full_name=full_name) for cur_dev in sub_list])
            )
        return cur_xml
    class Meta:
        db_table = u'device_group'
        ordering = ("-cluster_device_group", "name",)
    def __unicode__(self):
        return u"%s%s%s" % (
            self.name,
            " (%s)" % (self.description) if self.description else "",
            "[*]" if self.cluster_device_group else ""
        )

class device_group_serializer(serializers.ModelSerializer):
    def validate(self, in_dict):
        if "description" not in in_dict:
            in_dict["description"] = ""
        return in_dict
    class Meta:
        model = device_group
        fields = ("idx", "name", "description", "cluster_device_group", "enabled", "device",)

@receiver(signals.pre_save, sender=device_group)
def device_group_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        if not cur_inst.name:
            raise ValidationError("name can not be zero")
        if not valid_domain_re.match(cur_inst.name):
            raise ValidationError("invalid characters in '%s'" % (cur_inst.name))

@receiver(signals.post_save, sender=device_group)
def device_group_post_save(sender, **kwargs):
    cur_inst = kwargs["instance"]

    if kwargs["created"] and not kwargs["raw"]:
        # first is always cdg
        if device_group.objects.count() == 1 and not cur_inst.cluster_device_group:
            cur_inst.cluster_device_group = True
            cur_inst.save()
    if not kwargs["raw"]:
        # meta_device is always created
        if not cur_inst.device_id:
            cur_inst._add_meta_device()
        if cur_inst.device_id and cur_inst.device.name != cur_inst.get_metadevice_name():
            cur_inst.device.name = cur_inst.get_metadevice_name()
            cur_inst.device.save()
        if cur_inst.cluster_device_group and not cur_inst.enabled:
            # always enable cluster device group
            cur_inst.enabled = True
            cur_inst.save()

class device_location(models.Model):
    idx = models.AutoField(db_column="device_location_idx", primary_key=True)
    location = models.CharField(max_length=192, blank=False, unique=True)
    date = models.DateTimeField(auto_now_add=True)
    def get_xml(self):
        return E.device_location(
            unicode(self),
            pk="%d" % (self.pk),
            key="dl__%d" % (self.pk),
            location=unicode(self.location)
        )
    def __unicode__(self):
        return self.location
    class Meta:
        db_table = u'device_location'

# #class device_relationship(models.Model):
# #    idx = models.AutoField(db_column="device_relationship_idx", primary_key=True)
# #    host_device = models.ForeignKey("device", related_name="host_device")
# #    domain_device = models.ForeignKey("device", related_name="domain_device")
# #    relationship = models.CharField(max_length=9, blank=True)
# #    date = models.DateTimeField(auto_now_add=True)
# #    class Meta:
# #        db_table = u'device_relationship'

class device_rsync_config(models.Model):
    idx = models.AutoField(db_column="device_rsync_config_idx", primary_key=True)
    config = models.ForeignKey("config", db_column="new_config_id")
    device = models.ForeignKey("device")
    last_rsync_time = models.DateTimeField(null=True, blank=True)
    status = models.TextField()
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'device_rsync_config'

class device_type(models.Model):
    idx = models.AutoField(db_column="device_type_idx", primary_key=True)
    identifier = models.CharField(unique=True, max_length=24)
    description = models.CharField(unique=True, max_length=192)
    date = models.DateTimeField(auto_now_add=True)
    def get_xml(self):
        return E.device_type(
            unicode(self),
            name=self.description,
            identifier=self.identifier,
            pk="%d" % (self.pk),
            key="devt__%d" % (self.pk)
        )
    def __unicode__(self):
        return self.description
    class Meta:
        db_table = u'device_type'

class device_variable(models.Model):
    idx = models.AutoField(db_column="device_variable_idx", primary_key=True)
    device = models.ForeignKey("device")
    is_public = models.BooleanField(default=True)
    name = models.CharField(max_length=765)
    description = models.CharField(max_length=765, default="", blank=True)
    var_type = models.CharField(max_length=3, choices=[
        ("i", "integer"),
        ("s", "string"),
        ("d", "datetime"),
        ("t", "time"),
        ("b", "blob")])
    val_str = models.TextField(blank=True, null=True, default="")
    val_int = models.IntegerField(null=True, blank=True, default=0)
    # base64 encoded
    val_blob = models.TextField(blank=True, null=True, default="")
    val_date = models.DateTimeField(null=True, blank=True)
    val_time = models.TextField(blank=True, null=True) # This field type is a guess.
    date = models.DateTimeField(auto_now_add=True)
    def set_value(self, value):
        if type(value) == datetime.datetime:
            self.var_type = "d"
            self.val_date = cluster_timezone.localize(value)
        elif type(value) in [int, long] or (type(value) in [str, unicode] and value.isdigit()):
            self.var_type = "i"
            self.val_int = int(value)
        else:
            self.var_type = "s"
            self.val_str = value
    def get_value(self):
        if self.var_type == "i":
            return self.val_int
        elif self.var_type == "s":
            return self.val_str
        else:
            return "get_value for %s" % (self.var_type)
    value = property(get_value, set_value)
    def get_xml(self):
        dev_xml = E.device_variable(
            pk="%d" % (self.pk),
            key="dv__%d" % (self.pk),
            device="%d" % (self.device_id),
            is_public="1" if self.is_public else "0",
            name=self.name,
            description=self.description or "",
            var_type=self.var_type)
        if self.var_type == "i":
            dev_xml.attrib["value"] = "%d" % (self.val_int)
        elif self.var_type == "s":
            dev_xml.attrib["value"] = self.val_str
        return dev_xml
    def __unicode__(self):
        return "%s[%s] = %s" % (
            self.name,
            self.var_type,
            str(self.get_value()))
    def init_as_gauge(self, max_value, start=0):
        self.__max, self.__cur = (max_value, start)
        self._update_gauge()
    def count(self, num=1):
        self.__cur += num
        self._update_gauge()
    def _update_gauge(self):
        self.val_int = min(100, int(float(100 * self.__cur) / float(max(1, self.__max))))
        self.save()
    class Meta:
        db_table = u'device_variable'
        ordering = ("name",)

@receiver(signals.pre_save, sender=device_variable)
def device_variable_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        if cur_inst.device_id:
            _check_empty_string(cur_inst, "name")
            if cur_inst.var_type == "s":
                _check_empty_string(cur_inst, "val_str")
            if cur_inst.var_type == "i":
                _check_integer(cur_inst, "val_int")
            _check_empty_string(cur_inst, "var_type")
            all_var_names = device_variable.objects.exclude(Q(pk=cur_inst.pk)).filter(Q(device=cur_inst.device)).values_list("name", flat=True)
            if cur_inst.name in all_var_names:
                raise ValidationError("name '%s' already used for device" % (cur_inst.name))

class devicelog(models.Model):
    idx = models.AutoField(db_column="devicelog_idx", primary_key=True)
    device = models.ForeignKey("device", null=True, blank=True)
    log_source = models.ForeignKey("log_source", null=True)
    user = models.ForeignKey("user", null=True)
    log_status = models.ForeignKey("log_status", null=True)
    text = models.CharField(max_length=765, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    @staticmethod
    def new_log(cur_dev, log_src, log_stat, text, **kwargs):
        if log_src and type(log_src) in [int, long]:
            log_src = cached_short_log_source(log_src)
        if log_stat and type(log_stat) in [int, long]:
            log_stat = cached_log_status(log_stat)
        cur_log = devicelog(
            device=cur_dev,
            log_source=log_src or cluster_log_source,
            user=kwargs.get("user", None),
            log_status=log_stat,
            text=text)
        cur_log.save()
        return cur_log
    def get_xml(self):
        return E.devicelog(
            pk="%d" % (self.pk),
            key="devlog__%d" % (self.pk),
            log_source_name=unicode(self.log_source.name),
            log_status_name=unicode(self.log_status.name),
            text=unicode(self.text),
            date=unicode(self.date)
        )
    def __unicode__(self):
        return u"%s (%s, %s:%d)" % (
            self.text,
            self.log_source.name,
            self.log_status.identifier,
            self.log_status.log_level)
    class Meta:
        db_table = u'devicelog'
        ordering = ("date",)

class dmi_entry(models.Model):
    idx = models.AutoField(db_column="dmi_entry_idx", primary_key=True)
    device = models.ForeignKey("device")
    dmi_type = models.IntegerField()
    handle = models.IntegerField()
    dmi_length = models.IntegerField()
    info = models.CharField(max_length=765)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'dmi_entry'

class dmi_ext_key(models.Model):
    idx = models.AutoField(db_column="dmi_ext_key_idx", primary_key=True)
    dmi_key = models.ForeignKey("dmi_key")
    ext_value_string = models.CharField(max_length=765)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'dmi_ext_key'

class dmi_key(models.Model):
    idx = models.AutoField(db_column="dmi_key_idx", primary_key=True)
    dmi_entry = models.ForeignKey("dmi_entry")
    key_string = models.CharField(max_length=765)
    value_string = models.CharField(max_length=765, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'dmi_key'

class genstuff(models.Model):
    idx = models.AutoField(db_column="genstuff_idx", primary_key=True)
    name = models.CharField(unique=True, max_length=192)
    description = models.CharField(max_length=384, blank=True)
    value = models.CharField(max_length=192, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'genstuff'

class route_generation(models.Model):
    idx = models.AutoField(primary_key=True)
    # generation, is increased whenever one of the routing entries changes
    generation = models.IntegerField(default=1)
    date = models.DateTimeField(auto_now_add=True)
    def __unicode__(self):
        return u"route generation %d" % (
            self.generation,
        )

def mark_routing_dirty():
    cur_gen = route_generation.objects.all().order_by("-generation")
    if len(cur_gen):
        new_gen = list(cur_gen)[0]
        cur_gen.delete()
        new_gen.generation += 1
    else:
        new_gen = route_generation(generation=1)
    new_gen.save()

class hw_entry(models.Model):
    idx = models.AutoField(db_column="hw_entry_idx", primary_key=True)
    device = models.ForeignKey("device")
    hw_entry_type = models.ForeignKey("hw_entry_type")
    iarg0 = models.IntegerField(null=True, blank=True)
    iarg1 = models.IntegerField(null=True, blank=True)
    sarg0 = models.CharField(max_length=765, blank=True)
    sarg1 = models.CharField(max_length=765, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'hw_entry'

class hw_entry_type(models.Model):
    idx = models.AutoField(db_column="hw_entry_type_idx", primary_key=True)
    identifier = models.CharField(max_length=24)
    description = models.CharField(max_length=765)
    iarg0_descr = models.CharField(max_length=765, blank=True)
    iarg1_descr = models.CharField(max_length=765, blank=True)
    sarg0_descr = models.CharField(max_length=765, blank=True)
    sarg1_descr = models.CharField(max_length=765, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'hw_entry_type'

class ibc_connection(models.Model):
    idx = models.AutoField(db_column="ibc_connection_idx", primary_key=True)
    device = models.ForeignKey("device")
    slave_device = models.ForeignKey("device", null=True, related_name="slave_device")
    slave_info = models.CharField(max_length=192, blank=True)
    blade = models.IntegerField()
    state = models.CharField(max_length=96, blank=True)
    blade_exists = models.IntegerField(null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'ibc_connection'

class ibc_device(models.Model):
    idx = models.AutoField(db_column="ibc_device_idx", primary_key=True)
    device = models.ForeignKey("device")
    blade_type = models.CharField(max_length=192, blank=True)
    num_blades = models.IntegerField(null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'ibc_device'

class image(models.Model):
    idx = models.AutoField(db_column="image_idx", primary_key=True)
    name = models.CharField(max_length=192, blank=True, unique=True)
    source = models.CharField(max_length=384, blank=True)
    version = models.IntegerField(null=True, blank=True, default=1)
    release = models.IntegerField(null=True, blank=True, default=0)
    builds = models.IntegerField(null=True, blank=True, default=0)
    build_machine = models.CharField(max_length=192, blank=True, default="")
    # not a foreign key to break cyclic dependencies
    # device = models.ForeignKey("device", null=True)
    device = models.IntegerField(null=True)
    build_lock = models.BooleanField(default=False)
    # size in Byte
    size = models.IntegerField(default=0)
    size_string = models.TextField(blank=True, default="")
    sys_vendor = models.CharField(max_length=192, blank=True)
    sys_version = models.CharField(max_length=192, blank=True)
    sys_release = models.CharField(max_length=192, blank=True)
    bitcount = models.IntegerField(null=True, blank=True)
    architecture = models.ForeignKey("architecture")
    full_build = models.BooleanField(default=False)
    date = models.DateTimeField(auto_now_add=True)
    enabled = models.BooleanField(default=True)
    def get_xml(self):
        if self.size_string and self.size_string.count(";"):
            self.size_string = logging_tools.get_size_str(self.size or 0)
            self.save()
        cur_img = E.image(
            unicode(self),
            pk="%d" % (self.pk),
            key="image__%d" % (self.pk),
            name="%s" % (self.name),
            enabled="1" if self.enabled else "0",
            version="%d" % (self.version),
            release="%d" % (self.release),
            sys_vendor="%s" % (self.sys_vendor),
            sys_version="%s" % (self.sys_version),
            sys_release="%s" % (self.sys_release),
            size_string="%s" % (self.size_string),
            size="%d" % (self.size or 0),
            architecture="%d" % (self.architecture_id or 0),
        )
        return cur_img
    def __unicode__(self):
        return "%s (arch %s)" % (
            self.name,
            unicode(self.architecture))
    class Meta:
        db_table = u'image'
        ordering = ("name",)

@receiver(signals.pre_save, sender=image)
def image_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        cur_inst.size_string = logging_tools.get_size_str(cur_inst.size)

class image_serializer(serializers.ModelSerializer):
    class Meta:
        model = image
        fields = ("idx", "name", "enabled", "version", "release",
            "sys_vendor", "sys_version", "sys_release", "size_string", "size", "architecture",
            "new_image", "act_image"
            )

class kernel(models.Model):
    idx = models.AutoField(db_column="kernel_idx", primary_key=True)
    name = models.CharField(max_length=384)
    kernel_version = models.CharField(max_length=384)
    major = models.CharField(max_length=192, blank=True)
    minor = models.CharField(max_length=192, blank=True)
    patchlevel = models.CharField(max_length=192, blank=True)
    version = models.IntegerField(null=True, blank=True, default=1)
    release = models.IntegerField(null=True, blank=True, default=1)
    builds = models.IntegerField(null=True, blank=True, default=0)
    build_machine = models.CharField(max_length=192, blank=True)
    # not a foreignkey to break cyclic dependencies
    # master_server = models.ForeignKey("device", null=True, related_name="master_server")
    master_server = models.IntegerField(null=True)
    master_role = models.CharField(max_length=192, blank=True)
    # not a foreignkey to break cyclic dependencies
    # device = models.ForeignKey("device", null=True)
    device = models.IntegerField(null=True)
    build_lock = models.BooleanField(default=False)
    config_name = models.CharField(max_length=192, blank=True)
    cpu_arch = models.CharField(max_length=192, blank=True)
    sub_cpu_arch = models.CharField(max_length=192, blank=True)
    target_dir = models.CharField(max_length=765, blank=True)
    comment = models.TextField(blank=True, default="")
    enabled = models.BooleanField(default=False)
    initrd_version = models.IntegerField(null=True, blank=True)
    initrd_built = models.DateTimeField(null=True, blank=True)
    # which modules are actually built into initrd
    module_list = models.TextField(blank=True)
    # which modules are requested
    target_module_list = models.TextField(blank=True, default="")
    xen_host_kernel = models.NullBooleanField(default=False)
    xen_guest_kernel = models.NullBooleanField(default=False)
    bitcount = models.IntegerField(null=True, blank=True)
    stage1_lo_present = models.BooleanField(default=False)
    stage1_cpio_present = models.BooleanField(default=False)
    stage1_cramfs_present = models.BooleanField(default=False)
    stage2_present = models.BooleanField(default=False)
    date = models.DateTimeField(auto_now_add=True)
    def get_usecount(self):
        return 5
    def get_xml(self):
        return E.kernel(
            pk="%d" % (self.pk),
            key="kernel__%d" % (self.pk),
            name=self.name,
            major=self.major,
            minor=self.minor,
            version="%d" % (self.version),
            release="%d" % (self.release),
            enabled="1" if self.enabled else "0",
            bitcount="%d" % (self.bitcount or 0),
        )
    def __unicode__(self):
        return self.name
    class Meta:
        db_table = u'kernel'
    class CSW_Meta:
        fk_ignore_list = ["initrd_build", "kernel_build"]

class kernel_serializer(serializers.ModelSerializer):
    class Meta:
        model = kernel
        fields = ("idx", "name", "enabled", "kernel_version", "version",
            "release", "bitcount", "initrd_build_set", "kernel_build_set",
            "new_kernel", "act_kernel", "comment", "target_module_list", "module_list")

class initrd_build(models.Model):
    idx = models.AutoField(primary_key=True)
    kernel = models.ForeignKey("kernel")
    user_name = models.CharField(max_length=128, default="root")
    # run_time in seconds
    run_time = models.IntegerField(default=0)
    success = models.BooleanField(default=False)
    date = models.DateTimeField(auto_now_add=True)

class kernel_build(models.Model):
    idx = models.AutoField(db_column="kernel_build_idx", primary_key=True)
    kernel = models.ForeignKey("kernel")
    build_machine = models.CharField(max_length=192, blank=True)
    device = models.ForeignKey("device", null=True)
    version = models.IntegerField(null=True, blank=True)
    release = models.IntegerField(null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'kernel_build'

class kernel_local_info(models.Model):
    idx = models.AutoField(db_column="kernel_local_info_idx", primary_key=True)
    kernel = models.ForeignKey("kernel")
    device = models.ForeignKey("device")
    syncer_role = models.CharField(max_length=192, blank=True)
    info_blob = models.TextField(blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'kernel_local_info'

class kernel_log(models.Model):
    idx = models.AutoField(db_column="kernel_log_idx", primary_key=True)
    kernel = models.ForeignKey("kernel")
    device = models.ForeignKey("device")
    syncer_role = models.CharField(max_length=192, blank=True)
    log_level = models.IntegerField(null=True, blank=True)
    log_str = models.TextField(blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'kernel_log'

class log_source(models.Model):
    idx = models.AutoField(db_column="log_source_idx", primary_key=True)
    # server_type or user
    identifier = models.CharField(max_length=192)
    # name (Cluster Server, webfrontend, ...)
    name = models.CharField(max_length=192)
    # link to device or None
    device = models.ForeignKey("device", null=True)
    # long description
    description = models.CharField(max_length=765, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    @staticmethod
    def create_log_source_entry(identifier, name, **kwargs):
        ls_dev = kwargs.get("device", None)
        sources = log_source.objects.filter(Q(identifier=identifier) & Q(device=ls_dev))
        if len(sources) > 1:
            print "Too many log_source_entries present (%s), exiting" % (", ".join([identifier, name]))
            cur_source = None
        elif not len(sources):
            if ls_dev is not None:
                new_source = log_source(
                    identifier=identifier,
                    name=name,
                    description=u"%s on %s" % (name, unicode(ls_dev)),
                    device=kwargs["device"]
                )
                new_source.save()
            else:
                new_source = log_source(
                    identifier=identifier,
                    name=name,
                    description=kwargs.get("description", "%s (id %s)" % (name, identifier))
                )
                new_source.save()
            cur_source = new_source
        else:
            cur_source = sources[0]
        return cur_source
    def __unicode__(self):
        return "ls %s (%s), %s" % (self.name,
                                   self.identifier,
                                   self.description)
    class Meta:
        db_table = u'log_source'

def log_source_lookup(identifier, log_dev):
    return log_source.objects.get(Q(identifier=identifier) & Q(device=log_dev))

def short_log_source_lookup(idx):
    return log_source.objects.get(Q(pk=idx))

cached_log_source = memoize(log_source_lookup, {}, 2)
cached_short_log_source = memoize(short_log_source_lookup, {}, 2)

class log_status(models.Model):
    idx = models.AutoField(db_column="log_status_idx", primary_key=True)
    identifier = models.CharField(max_length=12, blank=True)
    log_level = models.IntegerField(null=True, blank=True)
    name = models.CharField(max_length=192, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'log_status'

def log_status_lookup(key):
    if type(key) in [str, unicode]:
        return log_status.objects.get(Q(identifier=key))
    else:
        return log_status.objects.get(Q(log_level={
            logging_tools.LOG_LEVEL_OK       : 0,
            logging_tools.LOG_LEVEL_WARN     : 50,
            logging_tools.LOG_LEVEL_ERROR    : 100,
            logging_tools.LOG_LEVEL_CRITICAL : 200}[key]))

cached_log_status = memoize(log_status_lookup, {}, 1)

class lvm_lv(models.Model):
    idx = models.AutoField(db_column="lvm_lv_idx", primary_key=True)
    partition_table = models.ForeignKey("partition_table")
    lvm_vg = models.ForeignKey("lvm_vg")
    size = models.BigIntegerField(null=True, blank=True)
    mountpoint = models.CharField(max_length=192, default="/")
    mount_options = models.CharField(max_length=384, blank=True)
    fs_freq = models.IntegerField(null=True, blank=True)
    fs_passno = models.IntegerField(null=True, blank=True)
    name = models.CharField(max_length=192)
    partition_fs = models.ForeignKey("partition_fs")
    warn_threshold = models.IntegerField(null=True, blank=True, default=85)
    crit_threshold = models.IntegerField(null=True, blank=True, default=95)
    date = models.DateTimeField(auto_now_add=True)
    def get_xml(self):
        return E.lvm_lv(
            pk="%d" % (self.pk),
            key="lvm_lv__%d" % (self.pk),
            lvm_vg="%d" % (self.lvm_vg_id or 0),
            mountpoint="%s" % (self.mountpoint),
            name="%s" % (self.name),
            warn_threshold="%d" % (self.warn_threshold or 0),
            crit_threshold="%d" % (self.crit_threshold or 0),
       )
    class Meta:
        db_table = u'lvm_lv'
        ordering = ("name",)

@receiver(signals.pre_save, sender=lvm_lv)
def lvm_lv_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        _check_integer(cur_inst, "warn_threshold", none_to_zero=True, min_val=0, max_val=100)
        _check_integer(cur_inst, "crit_threshold", none_to_zero=True, min_val=0, max_val=100)
        # fs_freq
        _check_integer(cur_inst, "fs_freq", min_val=0, max_val=1)
        # fs_passno
        _check_integer(cur_inst, "fs_passno", min_val=0, max_val=2)

class lvm_vg(models.Model):
    idx = models.AutoField(db_column="lvm_vg_idx", primary_key=True)
    partition_table = models.ForeignKey("partition_table")
    name = models.CharField(max_length=192)
    date = models.DateTimeField(auto_now_add=True)
    def get_xml(self):
        return E.lvm_vg(
            E.lvm_lvs(
                *[cur_lv.get_xml() for cur_lv in self.lvm_lv_set.all()]
            ),
            pk="%d" % (self.pk),
            key="lvm_vg__%d" % (self.pk),
            partition_table="%d" % (self.partition_table_id or 0),
            name=self.name,
        )
    class Meta:
        db_table = u'lvm_vg'
        ordering = ("name",)

class mac_ignore(models.Model):
    idx = models.AutoField(db_column="mac_ignore_idx", primary_key=True)
    macaddr = models.CharField(max_length=192, db_column="macadr", default="00:00:00:00:00:00")
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'mac_ignore'

class macbootlog(models.Model):
    idx = models.AutoField(db_column="macbootlog_idx", primary_key=True)
    device = models.ForeignKey("device", null=True)
    entry_type = models.CharField(max_length=96, db_column="type", default="???")
    ip_action = models.CharField(max_length=96, db_column="ip", default="0.0.0.0")
    macaddr = models.CharField(max_length=192, db_column="macadr", default="00:00:00:00:00:00")
    log_source = models.ForeignKey("log_source", null=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'macbootlog'

class ms_outlet(models.Model):
    idx = models.AutoField(db_column="msoutlet_idx", primary_key=True)
    device = models.ForeignKey("device")
    slave_device = models.ForeignKey("device", null=True, related_name="ms_slave_device")
    slave_info = models.CharField(max_length=192, blank=True)
    outlet = models.IntegerField()
    state = models.CharField(max_length=96, blank=True)
    t_power_on_delay = models.IntegerField(null=True, blank=True)
    t_power_off_delay = models.IntegerField(null=True, blank=True)
    t_reboot_delay = models.IntegerField(null=True, blank=True)
    power_on_delay = models.IntegerField(null=True, blank=True)
    power_off_delay = models.IntegerField(null=True, blank=True)
    reboot_delay = models.IntegerField(null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'msoutlet'

class netdevice(models.Model):
    idx = models.AutoField(db_column="netdevice_idx", primary_key=True)
    device = models.ForeignKey("device")
    devname = models.CharField(max_length=36)
    macaddr = models.CharField(db_column="macadr", max_length=177, blank=True)
    driver_options = models.CharField(max_length=672, blank=True)
    speed = models.IntegerField(default=0, null=True, blank=True)
    netdevice_speed = models.ForeignKey("netdevice_speed")
    driver = models.CharField(max_length=384, blank=True, default="e1000e")
    routing = models.BooleanField(default=False)
    penalty = models.IntegerField(null=True, blank=True, default=1)
    dhcp_device = models.NullBooleanField(null=True, blank=True, default=False)
    ethtool_options = models.IntegerField(null=True, blank=True, default=0)
    fake_macaddr = models.CharField(db_column="fake_macadr", max_length=177, blank=True)
    network_device_type = models.ForeignKey("network_device_type")
    description = models.CharField(max_length=765, blank=True)
    is_bridge = models.BooleanField(default=False)
    bridge_name = models.CharField(max_length=765, blank=True)
    vlan_id = models.IntegerField(null=True, blank=True)
    # for VLAN devices
    master_device = models.ForeignKey("self", null=True, related_name="vlan_slaves")
    date = models.DateTimeField(auto_now_add=True)
    def __init__(self, *args, **kwargs):
        models.Model.__init__(self, *args, **kwargs)
        self.saved_values = {
            "penalty" : self.penalty,
            "routing" : self.routing,
        }
    def copy(self):
        return netdevice(
            devname=self.devname,
            macaddr=self.get_dummy_macaddr(),
            driver_options=self.driver_options,
            speed=self.speed,
            netdevice_speed=self.netdevice_speed,
            driver=self.driver,
            routing=self.routing,
            penalty=self.penalty,
            dhcp_device=self.dhcp_device,
            ethtool_options=self.ethtool_options,
            fake_macaddr=self.get_dummy_macaddr(),
            network_device_type=self.network_device_type,
            description=self.description,
            is_bridge=self.is_bridge,
            bridge_name=self.bridge_name,
            vlan_id=self.vlan_id,
            )
    def find_matching_network_device_type(self):
        # remove digits
        name = self.devname.split(":")[0].strip("0123456789")
        ndt_dict = dict([(cur_ndt.identifier, cur_ndt) for cur_ndt in network_device_type.objects.all()])
        match_list = [ndt for nw_id, ndt in ndt_dict.iteritems() if nw_id.startswith(name) or name.endswith(nw_id)]
        if len(match_list) == 0:
            return None
        elif len(match_list) == 1:
            return match_list[0]
        else:
            # FIXME, enhance to full match
            return match_list[0]
    def get_dummy_macaddr(self):
        return ":".join(["00"] * self.network_device_type.mac_bytes)
    class Meta:
        db_table = u'netdevice'
        ordering = ("devname",)
    @property
    def ethtool_autoneg(self):
        return (self.ethtool_options or 0) & 3
    @property
    def ethtool_duplex(self):
        return ((self.ethtool_options or 0) >> 2) & 3
    @property
    def ethtool_speed(self):
        return ((self.ethtool_options or 0) >> 4) & 7
    @ethtool_autoneg.setter
    def ethtool_autoneg(self, in_val):
        self.ethtool_options = ((self.ethtool_options or 0) & ~3) | int(in_val)
    @ethtool_duplex.setter
    def ethtool_duplex(self, in_val):
        self.ethtool_options = ((self.ethtool_options or 0) & ~12) | (int(in_val) << 2)
    @ethtool_speed.setter
    def ethtool_speed(self, in_val):
        self.ethtool_options = ((self.ethtool_options or 0) & 15) | (int(in_val) << 4)
    def ethtool_string(self):
        return ",".join(["FIXME"])
    def __unicode__(self):
        return self.devname
    def get_xml(self):
        self.vlan_id = self.vlan_id or 0
        return E.netdevice(
            self.devname,
            E.net_ips(*[cur_ip.get_xml() for cur_ip in self.net_ip_set.all()]),
            E.peers(*[cur_peer.get_xml() for cur_peer in peer_information.objects.filter(
                Q(s_netdevice=self) | Q(d_netdevice=self)
                ).distinct().select_related(
                    "s_netdevice",
                    "s_netdevice__device",
                    "d_netdevice",
                    "d_netdevice__device",
                    "s_netdevice__device__domain_tree_node",
                    "d_netdevice__device__domain_tree_node")]),
            devname=self.devname,
            description=self.description or "",
            driver=self.driver or "",
            driver_options=self.driver_options or "",
            pk="%d" % (self.pk),
            key="nd__%d" % (self.pk),
            ethtool_autoneg="%d" % (self.ethtool_autoneg),
            ethtool_duplex="%d" % (self.ethtool_duplex),
            ethtool_speed="%d" % (self.ethtool_speed),
            macaddr=self.macaddr or ":".join(["00"] * 6),
            fake_macaddr=self.fake_macaddr or ":".join(["00"] * 6),
            penalty="%d" % (self.penalty or 1),
            dhcp_device="1" if self.dhcp_device else "0",
            routing="1" if self.routing else "0",
            device="%d" % (self.device_id),
            vlan_id="%d" % (self.vlan_id),
            netdevice_speed="%d" % (self.netdevice_speed_id),
            network_device_type="%d" % (self.network_device_type_id),
            nd_type="%d" % (self.network_device_type_id),
            master_device="%d" % (self.master_device_id or 0),
            )
@receiver(signals.pre_delete, sender=netdevice)
def netdevice_pre_delete(sender, **kwargs):
    # too late here, handled by delete_netdevice in network_views
    pass
    # if "instance" in kwargs:
        # cur_inst = kwargs["instance"]
        # for cur_dev in device.objects.filter(Q(bootnetdevice=cur_inst.pk)):
            # cur_dev.bootnetdevice = None
            # cur_dev.save(update_fields=["bootnetdevice"])

@receiver(signals.pre_save, sender=netdevice)
def netdevice_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        _check_empty_string(cur_inst, "devname")
        all_nd_names = netdevice.objects.exclude(Q(pk=cur_inst.pk)).filter(Q(device=cur_inst.device_id)).values_list("devname", flat=True)
        if cur_inst.devname in all_nd_names:
            raise ValidationError("devname '%s' already used" % (cur_inst.devname))
        # change network_device_type
        nd_type = cur_inst.find_matching_network_device_type()
        if not nd_type:
            raise ValidationError("no matching device_type found")
        cur_inst.network_device_type = nd_type
        # fix None as vlan_id
        _check_integer(cur_inst, "vlan_id", none_to_zero=True, min_val=0)
        # penalty
        _check_integer(cur_inst, "penalty", min_val=1)
        # check mac address
        dummy_mac, mac_re = (":".join(["00"] * cur_inst.network_device_type.mac_bytes),
                             re.compile("^%s$" % (":".join(["[0-9a-f]{2}"] * cur_inst.network_device_type.mac_bytes))))
        # set empty if not set
        try:
            if not cur_inst.macaddr.strip() or int(cur_inst.macaddr.replace(":", ""), 16) == 0:
                cur_inst.macaddr = dummy_mac
        except:
            raise ValidationError("MACaddress has illegal format")
        # set empty if not set
        try:
            if not cur_inst.fake_macaddr.strip() or int(cur_inst.fake_macaddr.replace(":", ""), 16) == 0:
                cur_inst.fake_macaddr = dummy_mac
        except:
            raise ValidationError("fake MACaddress has illegal format")
        if not mac_re.match(cur_inst.macaddr):
            raise ValidationError("MACaddress has illegal format")
        if not mac_re.match(cur_inst.fake_macaddr):
            raise ValidationError("fake MACaddress has illegal format")

@receiver(signals.post_save, sender=netdevice)
def netdevice_post_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        mark_dirty = False
        for comp_val in ["penalty", "routing"]:
            if getattr(cur_inst, comp_val) != cur_inst.saved_values[comp_val]:
                mark_dirty = True
                break
        if mark_dirty:
            mark_routing_dirty()

@receiver(signals.post_delete, sender=netdevice)
def netdevice_post_delete(sender, **kwargs):
    if "instance" in kwargs:
        mark_routing_dirty()

class netdevice_speed(models.Model):
    idx = models.AutoField(db_column="netdevice_speed_idx", primary_key=True)
    speed_bps = models.BigIntegerField(null=True, blank=True)
    check_via_ethtool = models.BooleanField(default=True)
    full_duplex = models.BooleanField(default=True)
    date = models.DateTimeField(auto_now_add=True)
    def get_xml(self):
        return E.netdevice_speed(
            unicode(self),
            pk="%d" % (self.pk),
            key="nds__%d" % (self.pk),
            speed_bps="%d" % (self.speed_bps),
            check_via_ethtool="1" if self.check_via_ethtool else "0",
            full_duplex="1" if self.full_duplex else "0",
        )
    class Meta:
        db_table = u'netdevice_speed'
        ordering = ("speed_bps", "full_duplex")
    def __unicode__(self):
        _s_str, lut_idx = ("", 0)
        cur_s = self.speed_bps
        while cur_s > 999:
            cur_s = cur_s / 1000
            lut_idx += 1
        return u"%d%sBps, %s duplex, %s" % (
            cur_s,
            " kMGT"[lut_idx].strip(),
            "full" if self.full_duplex else "half",
            "check via ethtool" if self.check_via_ethtool else "no check")

class net_ip(models.Model):
    idx = models.AutoField(db_column="netip_idx", primary_key=True)
    ip = models.CharField(max_length=48)
    network = models.ForeignKey("network")
    netdevice = models.ForeignKey("netdevice")
    penalty = models.IntegerField(default=0)
    alias = models.CharField(max_length=765, blank=True, default="")
    alias_excl = models.NullBooleanField(null=True, blank=True, default=False)
    domain_tree_node = models.ForeignKey("domain_tree_node", null=True, default=None)
    date = models.DateTimeField(auto_now_add=True)
    def copy(self):
        return net_ip(
            ip=self.ip,
            network=self.network,
            penalty=self.penalty,
            alias=self.alias,
            alias_excl=self.alias_excl,
            domain_tree_node=self.domain_tree_node,
            )
    def get_hex_ip(self):
        return "".join(["%02X" % (int(part)) for part in self.ip.split(".")])
    def get_xml(self):
        return E.net_ip(
            unicode(self),
            pk="%d" % (self.pk),
            ip=self.ip,
            key="ip__%d" % (self.pk),
            network="%d" % (self.network_id),
            netdevice="%d" % (self.netdevice_id),
            penalty="%d" % (self.penalty or 1),
            alias=self.alias or "",
            alias_excl="1" if self.alias_excl else "0",
            domain_tree_node="%d" % (self.domain_tree_node_id or 0),
        )
    def __unicode__(self):
        return self.ip
    class Meta:
        db_table = u'netip'

@receiver(signals.pre_save, sender=net_ip)
def net_ip_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        try:
            ipv_addr = ipvx_tools.ipv4(cur_inst.ip)
        except:
            raise ValidationError("not a valid IPv4 address")
        if not cur_inst.network_id:
            match_list = ipv_addr.find_matching_network(network.objects.all())
            if len(match_list):
                cur_inst.network = match_list[0][1]
        if not cur_inst.network_id:
            raise ValidationError("no matching network found")
        if not ipv_addr.network_matches(cur_inst.network):
            match_list = ipv_addr.find_matching_network(network.objects.all())
            if match_list:
                cur_inst.network = match_list[0][1]
            else:
                raise ValidationError("no maching network found")
        dev_ips = net_ip.objects.exclude(Q(pk=cur_inst.pk)).filter(Q(netdevice__device=cur_inst.netdevice.device)).values_list("ip", flat=True)
        if cur_inst.ip in dev_ips:
            raise ValidationError("Address already %s used, device %s" % (cur_inst.ip, unicode(cur_inst.netdevice.device)))
        if cur_inst.network.network_type.identifier == "b":
            # set boot netdevice
            cur_inst.netdevice.device.bootnetdevice = cur_inst.netdevice
            cur_inst.netdevice.device.save()

@receiver(signals.post_save, sender=net_ip)
def net_ip_post_save(sender, **kwargs):
    cur_inst = kwargs["instance"]
    if kwargs["created"] and not kwargs["raw"] and "instance" in kwargs:
        cur_inst = kwargs["instance"]
        if cur_inst.ip == "127.0.0.1" and kwargs["created"] and not cur_inst.alias.strip():
            cur_inst.alias = "localhost"
            cur_inst.alias_excl = True
            cur_inst.save()

class network(models.Model):
    idx = models.AutoField(db_column="network_idx", primary_key=True)
    identifier = models.CharField(unique=True, max_length=255, blank=False)
    network_type = models.ForeignKey("network_type")
    master_network = models.ForeignKey("network", null=True, related_name="rel_master_network", blank=True)
    # should no longer be used, now in domain_tree_node
    short_names = models.BooleanField(default=True)
    # should no longer be used, now in domain_tree_node
    name = models.CharField(max_length=192, blank=True, default="")
    penalty = models.PositiveIntegerField(default=1)
    # should no longer be used, now in domain_tree_node
    postfix = models.CharField(max_length=12, blank=True)
    info = models.CharField(max_length=255, blank=True)
    network = models.IPAddressField(blank=False)
    netmask = models.IPAddressField(blank=False)
    broadcast = models.IPAddressField(blank=False)
    gateway = models.IPAddressField(blank=False)
    gw_pri = models.IntegerField(null=True, blank=True, default=1)
    # should no longer be used, now in domain_tree_node
    write_bind_config = models.BooleanField(default=False)
    # should no longer be used, now in domain_tree_node
    write_other_network_config = models.BooleanField(default=False)
    start_range = models.IPAddressField(default="0.0.0.0")
    end_range = models.IPAddressField(default="0.0.0.0")
    date = models.DateTimeField(auto_now_add=True)
    network_device_type = models.ManyToManyField("network_device_type")
    def get_xml(self, add_ip_info=False):
        r_xml = E.network(
            unicode(self),
            pk="%d" % (self.pk),
            key="nw_%d" % (self.pk),
            penalty="%d" % (self.penalty),
            identifier=self.identifier,
            network_type="%d" % (self.network_type_id),
            master_network="%d" % (self.master_network_id or 0),
            network=self.network,
            netmask=self.netmask,
            broadcast=self.broadcast,
            gateway=self.gateway,
            network_device_type="::".join(["%d" % (ndev_type.pk) for ndev_type in self.network_device_type.all()]),
        )
        if add_ip_info:
            r_xml.attrib["ip_count"] = "%d" % (len(self.net_ip_set.all()))
        return r_xml
    class Meta:
        db_table = u'network'
    def get_info(self):
        all_slaves = self.rel_master_network.all()
        # return extended info
        log_str = "%s network '%s' has %s%s" % (
            self.network_type.get_identifier_display(),
            self.identifier,
            logging_tools.get_plural("slave network", len(all_slaves)),
            ": %s" % ([cur_slave.identifier for cur_slave in all_slaves]) if all_slaves else "",
        )
        return log_str
    def __unicode__(self):
        return u"%s (%s/%s, %s)" % (
            self.name,
            self.network,
            self.netmask,
            self.network_type.identifier
        )

class network_serializer(serializers.ModelSerializer):
    class Meta:
        model = network

@receiver(signals.pre_save, sender=network)
def network_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        # what was the changed attribute
        change_attr = getattr(cur_inst, "change_attribute", None)
        _check_integer(cur_inst, "penalty", min_val= -100, max_val=100)
        nw_type = cur_inst.network_type.identifier
        if cur_inst.rel_master_network.all().count() and nw_type != "p":
            raise ValidationError("slave networks exists, cannot change type")
        if nw_type != "s" and cur_inst.master_network_id:
            raise ValidationError("only slave networks can have a master")
        if nw_type == "s" and cur_inst.master_network_id:
            if cur_inst.master_network.network_type.identifier != "p":
                raise ValidationError("master network must be a production network")
        # validate IP
        ip_dict = dict([(key, None) for key in ["network", "netmask", "broadcast", "gateway"]])
        for key in ip_dict.keys():
            try:
                ip_dict[key] = ipvx_tools.ipv4(getattr(cur_inst, key))
            except:
                raise ValidationError("%s is not an IPv4 address" % (key))
        if not change_attr:
            change_attr = "network"
        if change_attr in ["network", "netmask"]:
            ip_dict["broadcast"] = ~ip_dict["netmask"] | (ip_dict["network"] & ip_dict["netmask"])
        elif change_attr == "broadcast":
            ip_dict["netmask"] = ~(ip_dict["broadcast"] & ~ip_dict["network"])
        elif change_attr == "gateway":
            # do nothing
            pass
        ip_dict["network"] = ip_dict["network"] & ip_dict["netmask"]
        # always correct gateway
        ip_dict["gateway"] = (ip_dict["gateway"] & ~ip_dict["netmask"]) | ip_dict["network"]
        # set values
        for key, value in ip_dict.iteritems():
            setattr(cur_inst, key, unicode(value))

class network_device_type(models.Model):
    idx = models.AutoField(db_column="network_device_type_idx", primary_key=True)
    identifier = models.CharField(unique=True, max_length=48, blank=False)
    description = models.CharField(max_length=192)
    mac_bytes = models.PositiveIntegerField(default=6)
    date = models.DateTimeField(auto_now_add=True)
    def get_xml(self):
        return E.network_device_type(
            unicode(self),
            pk="%d" % (self.pk),
            key="nwdt__%d" % (self.pk),
            identifier=self.identifier,
            description=self.description,
            mac_bytes="%d" % (self.mac_bytes)
        )
    class Meta:
        db_table = u'network_device_type'
    def __unicode__(self):
        return u"%s (%s [%d])" % (
            self.identifier,
            self.description,
            self.mac_bytes)

@receiver(signals.pre_save, sender=network_device_type)
def network_device_type_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        if not(cur_inst.identifier.strip()):
            raise ValidationError("identifer must not be empty")
        _check_integer(cur_inst, "mac_bytes", min_val=6, max_val=24)

class network_device_type_serializer(serializers.ModelSerializer):
    class Meta:
        model = network_device_type
        fields = ("idx", "identifier", "description", "mac_bytes", "date")

class network_network_device_type(models.Model):
    idx = models.AutoField(db_column="network_network_device_type_idx", primary_key=True)
    network = models.ForeignKey("network")
    network_device_type = models.ForeignKey("network_device_type")
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'network_network_device_type'

class network_type(models.Model):
    idx = models.AutoField(db_column="network_type_idx", primary_key=True)
    identifier = models.CharField(
        unique=True, max_length=3,
        choices=(
            ("b", "boot"),
            ("p", "prod"),
            ("s", "slave"),
            ("o", "other"),
            ("l", "local")))
    description = models.CharField(max_length=192, blank=False)
    date = models.DateTimeField(auto_now_add=True)
    def get_xml(self):
        return E.network_type(
            unicode(self),
            pk="%d" % (self.pk),
            key="nwt__%d" % (self.pk),
            identifier=self.identifier,
            description=self.description)
    class Meta:
        db_table = u'network_type'
    def __unicode__(self):
        return u"%s (%s)" % (self.description,
                             self.identifier)

class network_type_serializer(serializers.ModelSerializer):
    class Meta:
        model = network_type
        fields = ("idx", "identifier", "description", "date")

@receiver(signals.pre_save, sender=network_type)
def network_type_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        # raise ValidationError("test validation error")
        if not(cur_inst.identifier.strip()):
            raise ValidationError("identifer must not be empty")

class config(models.Model):
    idx = models.AutoField(db_column="new_config_idx", primary_key=True)
    name = models.CharField(unique=True, max_length=192, blank=False)
    description = models.CharField(max_length=765)
    priority = models.IntegerField(null=True, default=0)
    # config_type = models.ForeignKey("config_type", db_column="new_config_type_id")
    parent_config = models.ForeignKey("config", null=True)
    date = models.DateTimeField(auto_now_add=True)
    # categories for this config
    categories = models.ManyToManyField("category")
    def get_xml(self, full=True):
        r_xml = E.config(
            pk="%d" % (self.pk),
            key="conf__%d" % (self.pk),
            name=unicode(self.name),
            description=unicode(self.description or ""),
            priority="%d" % (self.priority or 0),
            # config_type="%d" % (self.config_type_id),
            parent_config="%d" % (self.parent_config_id or 0),
            categories="::".join(["%d" % (cur_cat.pk) for cur_cat in self.categories.all()]),
        )
        if full:
            # explicit but exposes chached queries
            dev_names = [dev_conf.device.name for dev_conf in self.device_config_set.all()]
            r_xml.attrib["num_device_configs"] = "%d" % (len(dev_names))
            r_xml.attrib["device_list"] = logging_tools.compress_list(sorted(dev_names))
            r_xml.extend([
                E.config_vars(*[cur_var.get_xml() for cur_var in
                                list(self.config_str_set.all()) + \
                                list(self.config_int_set.all()) + \
                                list(self.config_bool_set.all()) + \
                                list(self.config_blob_set.all())]),
                E.mon_check_commands(*[cur_ngc.get_xml(with_exclude_devices=full) for cur_ngc in list(self.mon_check_command_set.all())]),
                E.config_scripts(*[cur_cs.get_xml() for cur_cs in list(self.config_script_set.all())])
            ])
        return r_xml
    def __unicode__(self):
        return self.name
    def show_variables(self, log_com, detail=False):
        log_com(" - config %s (pri %d)" % (self.name,
                                           self.priority))
        if detail:
            for var_type in ["str", "int", "bool"]:
                for cur_var in getattr(self, "config_%s_set" % (var_type)).all():
                    log_com("    %-20s : %s" % (cur_var.name, unicode(cur_var)))
    class Meta:
        db_table = u'new_config'

@receiver(signals.pre_save, sender=config)
def config_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        _check_empty_string(cur_inst, "name")
        # priority
        _check_integer(cur_inst, "priority", min_val= -9999, max_val=9999)

@receiver(signals.post_save, sender=config)
def config_post_save(sender, **kwargs):
    if not kwargs["raw"] and "instance" in kwargs:
        cur_inst = kwargs["instance"]
        if kwargs["created"] and getattr(cur_inst, "create_default_entries", True):
            add_list = []
            if cur_inst.name.count("export"):
                if cur_inst.name.count("home"):
                    # create a homedir export
                    # add export / options config_vars
                    add_list = [
                        config_str(
                            name="homeexport",
                            description="export path for automounter maps",
                            value="/export_change_me"),
                        config_str(
                            name="createdir",
                            description="create path for directory creation",
                            value="/create_change_me"),
                        config_str(
                            name="options",
                            description="Options",
                            value="-soft,tcp,lock,rsize=8192,wsize=8192,noac,lookupcache=none"
                        ),
                        config_str(
                            name="node_postfix",
                            description="postfix (to change network interface)",
                            value=""
                        )
                    ]
                else:
                    # create a normal export
                    # add import / export / options config_vars
                    add_list = [
                        config_str(
                            name="export",
                            description="export path",
                            value="/export_change_me"),
                        config_str(
                            name="import",
                            description="import path (for automounter)",
                            value="/import_change_me"),
                        config_str(
                            name="options",
                            description="Options",
                            value="-soft,tcp,lock,rsize=8192,wsize=8192,noac,lookupcache=none"
                            )
                    ]
            elif cur_inst.name == "ldap_server":
                add_list = [
                    config_str(
                        name="base_dn",
                        description="Base DN",
                        value="dc=test,dc=ac,dc=at"),
                    config_str(
                        name="admin_cn",
                        description="Admin CN (relative to base_dn",
                        value="admin"),
                    config_str(
                        name="root_passwd",
                        description="LDAP Admin passwd",
                        value="changeme"),
                ]
            elif cur_inst.name == "name_server":
                add_list = [
                    config_str(
                        name="FORWARDER_1",
                        description="first forward",
                        value="192.168.1.1"),
                    config_str(
                        name="USER",
                        description="named user",
                        value="named"),
                    config_str(
                        name="GROUP",
                        description="named group",
                        value="named"),
                    config_str(
                        name="SECRET",
                        description="ndc secret",
                        value="h8DM8opPS3ThdswucAoUqQ=="),
                ]
            for cur_var in add_list:
                cur_var.config = cur_inst
                cur_var.save()
        if cur_inst.parent_config_id == cur_inst.pk and cur_inst.pk:
            raise ValidationError("cannot be my own parent")

# class config_type(models.Model):
    # idx = models.AutoField(db_column="new_config_type_idx", primary_key=True)
    # name = models.CharField(unique=True, max_length=192)
    # description = models.CharField(max_length=765, blank=True)
    # date = models.DateTimeField(auto_now_add=True)
    # def get_xml(self):
        # return E.config_type(
            # unicode(self),
            # pk="%d" % (self.pk),
            # key="ctype__%d" % (self.pk),
            # name=unicode(self.name),
            # description=unicode(self.description or "")
        # )
    # def __unicode__(self):
        # return self.name
    # class Meta:
        # db_table = u'new_config_type'

# #class new_rrd_data(models.Model):
# #    idx = models.AutoField(db_column="new_rrd_data_idx", primary_key=True)
# #    device = models.ForeignKey("device", null=True, blank=True)
# #    descr = models.CharField(max_length=765, blank=True)
# #    descr1 = models.CharField(max_length=192, blank=True)
# #    descr2 = models.CharField(max_length=192, blank=True)
# #    descr3 = models.CharField(max_length=192, blank=True)
# #    descr4 = models.CharField(max_length=192, blank=True)
# #    unit = models.CharField(max_length=96, blank=True)
# #    info = models.CharField(max_length=255, blank=True)
# #    from_snmp = models.IntegerField(null=True, blank=True)
# #    base = models.IntegerField(null=True, blank=True)
# #    factor = models.FloatField(null=True, blank=True)
# #    var_type = models.CharField(max_length=3, blank=True)
# #    date = models.DateTimeField(auto_now_add=True)
# #    class Meta:
# #        db_table = u'new_rrd_data'

class partition(models.Model):
    idx = models.AutoField(db_column="partition_idx", primary_key=True)
    partition_disc = models.ForeignKey("partition_disc")
    mountpoint = models.CharField(max_length=192, default="/")
    partition_hex = models.CharField(max_length=6, blank=True)
    size = models.IntegerField(null=True, blank=True, default=100)
    mount_options = models.CharField(max_length=255, blank=True, default="defaults")
    pnum = models.IntegerField()
    bootable = models.BooleanField(default=False)
    fs_freq = models.IntegerField(null=True, blank=True, default=0)
    fs_passno = models.IntegerField(null=True, blank=True, default=0)
    partition_fs = models.ForeignKey("partition_fs")
    # lut_blob = models.TextField(blank=True, null=True)
    # comma-delimited list of /dev/disk/by-* entries
    disk_by_info = models.TextField(default="")
    warn_threshold = models.IntegerField(null=True, blank=True, default=85)
    crit_threshold = models.IntegerField(null=True, blank=True, default=95)
    date = models.DateTimeField(auto_now_add=True)
    def get_xml(self):
        p_xml = E.partition(
            pk="%d" % (self.pk),
            key="part__%d" % (self.pk),
            mountpoint=self.mountpoint or "",
            mount_options=self.mount_options or "",
            pnum="%d" % (self.pnum or 0),
            partition_fs="%d" % (self.partition_fs_id),
            size="%d" % (self.size if type(self.size) in [long, int] else 0),
            bootable="%d" % (1 if self.bootable else 0),
            fs_freq="%d" % (self.fs_freq),
            fs_passno="%d" % (self.fs_passno),
            warn_threshold="%d" % (self.warn_threshold or 0),
            crit_threshold="%d" % (self.crit_threshold or 0),
        )
        if hasattr(self, "problems"):
            p_xml.append(
                E.problems(
                    *[E.problem(what, level="%d" % (log_level)) for log_level, what, is_global in self.problems if is_global is False]
                )
            )
        return p_xml
    def _validate(self, p_disc):
        p_list = []
        p_name = "%s%d" % (p_disc, self.pnum)
        if not self.partition_fs_id:
            p_list.append((logging_tools.LOG_LEVEL_ERROR, "no partition_fs set (%s)" % (p_name), False))
        else:
            if self.partition_fs.hexid == "0" and self.partition_fs.name == "empty":
                p_list.append((logging_tools.LOG_LEVEL_ERROR, "empty partitionf_fs (%s)" % (p_name), False))
            if self.partition_fs.need_mountpoint():
                if not self.mountpoint.startswith("/"):
                    p_list.append((logging_tools.LOG_LEVEL_ERROR, "no mountpoint defined for %s" % (p_name), False))
                if not self.mount_options.strip():
                    p_list.append((logging_tools.LOG_LEVEL_ERROR, "no mount_options given for %s" % (p_name), False))
        self.problems = p_list
    def _get_problems(self):
        return self.problems
    class Meta:
        db_table = u'partition'
        ordering = ("pnum",)

@receiver(signals.pre_save, sender=partition)
def partition_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        p_num = cur_inst.pnum
        try:
            p_num = int(p_num)
        except:
            raise ValidationError("partition number '%s' not parseable" % (p_num))
        if p_num == 0:
            if partition.objects.filter(Q(partition_disc=cur_inst.partition_disc)).count() > 1:
                raise ValidationError("for pnum==0 only one partition is allowed")
        elif p_num < 1 or p_num > 32:
            raise ValidationError("partition number %d out of bounds [1, 32]" % (p_num))
        all_part_nums = partition.objects.exclude(Q(pk=cur_inst.pk)).filter(Q(partition_disc=cur_inst.partition_disc)).values_list("pnum", flat=True)
        if p_num in all_part_nums:
            raise ValidationError("partition number already used")
        cur_inst.pnum = p_num
        # size
        _check_integer(cur_inst, "size", min_val=0)
        _check_integer(cur_inst, "warn_threshold", none_to_zero=True, min_val=0, max_val=100)
        _check_integer(cur_inst, "crit_threshold", none_to_zero=True, min_val=0, max_val=100)
        # mountpoint
        if cur_inst.mountpoint.strip() and not cur_inst.mountpoint.startswith("/"):
            raise ValidationError("mountpoint must start with '/'")
        # fs_freq
        _check_integer(cur_inst, "fs_freq", min_val=0, max_val=1)
        # fs_passno
        _check_integer(cur_inst, "fs_passno", min_val=0, max_val=2)

class partition_disc(models.Model):
    idx = models.AutoField(db_column="partition_disc_idx", primary_key=True)
    partition_table = models.ForeignKey("partition_table")
    disc = models.CharField(max_length=192)
    priority = models.IntegerField(null=True, default=0)
    date = models.DateTimeField(auto_now_add=True)
    def get_xml(self):
        pd_xml = E.partition_disc(
            self.disc,
            E.partitions(
                *[sub_part.get_xml() for sub_part in self.partition_set.all()]
                ),
            pk="%d" % (self.pk),
            key="pdisc__%d" % (self.pk),
            priority="%d" % (self.priority),
            disc=self.disc,
        )
        if hasattr(self, "problems"):
            pd_xml.append(
                E.problems(
                    *[E.problem(what, level="%d" % (log_level)) for log_level, what, is_global in self.problems if not is_global]
                )
            )
        return pd_xml
    def _validate(self):
        p_list = []
        for part in self.partition_set.all():
            part._validate(self)
        my_parts = self.partition_set.all()
        all_mps = [cur_mp.mountpoint for cur_mp in my_parts if cur_mp.mountpoint.strip()]
        if len(all_mps) != len(set(all_mps)):
            p_list.append((logging_tools.LOG_LEVEL_ERROR, "mountpoints not unque", False))
        if all_mps:
            if "/" not in all_mps:
                p_list.append((logging_tools.LOG_LEVEL_ERROR, "/ missing from mountpoints", False))
            if "/usr" in all_mps:
                p_list.append((logging_tools.LOG_LEVEL_ERROR, "cannot boot when /usr is on a separate partition", False))
        ext_parts = [cur_p for cur_p in my_parts if cur_p.partition_fs_id and cur_p.partition_fs.name == "ext"]
        if my_parts:
            max_pnum = max([cur_p.pnum for cur_p in my_parts])
            if len(ext_parts) == 0:
                if  max_pnum > 4:
                    p_list.append((logging_tools.LOG_LEVEL_ERROR, "too many partitions (%d), only 4 without ext allowed" % (max_pnum), False))
            elif len(ext_parts) > 1:
                p_list.append((logging_tools.LOG_LEVEL_ERROR, "too many ext partitions (%d) defined" % (len(ext_parts)), False))
            else:
                ext_part = ext_parts[0]
                if ext_part.pnum != 4:
                    p_list.append((logging_tools.LOG_LEVEL_ERROR, "extended partition must have pnum 4", False))
        self.problems = p_list
    def _get_problems(self):
        return self.problems + sum([cur_part._get_problems() for cur_part in self.partition_set.all()], [])
    class Meta:
        db_table = u'partition_disc'
        ordering = ("priority", "disc",)
    def __unicode__(self):
        return self.disc

@receiver(signals.pre_save, sender=partition_disc)
def partition_disc_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        disc_re = re.compile("^/dev/([shv]d[a-z]|dm-(\d+)|mapper/.*|ida/(.*)|cciss/(.*))$")
        cur_inst = kwargs["instance"]
        d_name = cur_inst.disc.strip().lower()
        if not d_name:
            raise ValidationError("name must not be zero")
        if not disc_re.match(d_name):
            raise ValidationError("illegal name '%s'" % (d_name))
        all_discs = partition_disc.objects.exclude(Q(pk=cur_inst.pk)).filter(Q(partition_table=cur_inst.partition_table)).values_list("disc", flat=True)
        if d_name in all_discs:
            raise ValidationError("name already used")
        cur_inst.disc = d_name

class partition_fs(models.Model):
    # mix of partition and fs info, not perfect ...
    idx = models.AutoField(db_column="partition_fs_idx", primary_key=True)
    name = models.CharField(unique=True, max_length=48)
    identifier = models.CharField(max_length=3)
    descr = models.CharField(max_length=765, blank=True)
    hexid = models.CharField(max_length=6)
    date = models.DateTimeField(auto_now_add=True)
    def get_xml(self):
        return E.partition_fs(
            self.name,
            pk="%d" % (self.pk),
            key="partfs__%d" % (self.pk),
            identifier=self.identifier,
            descr=self.descr,
            hexid=self.hexid,
        )
    def need_mountpoint(self):
        return True if self.hexid in ["83"] else False
    def __unicode__(self):
        return self.descr
    class Meta:
        db_table = u'partition_fs'
        ordering = ("name",)

class partition_table(models.Model):
    idx = models.AutoField(db_column="partition_table_idx", primary_key=True)
    name = models.CharField(unique=True, max_length=192)
    description = models.CharField(max_length=255, blank=True, default="")
    enabled = models.BooleanField(default=True)
    valid = models.BooleanField(default=False)
    modify_bootloader = models.IntegerField(default=0)
    nodeboot = models.BooleanField(default=False)
    # non users-created partition tables can be deleted automatically
    user_created = models.BooleanField(default=True)
    date = models.DateTimeField(auto_now_add=True)
    def get_xml(self, **kwargs):
        _validate = kwargs.get("validate", False)
        if _validate:
            prob_list = self._validate()
            new_valid = not any([log_level in [
                logging_tools.LOG_LEVEL_ERROR,
                logging_tools.LOG_LEVEL_CRITICAL] for log_level, what, is_global in prob_list])
            # validate
            if new_valid != self.valid:
                self.valid = new_valid
                self.save()
        pt_xml = E.partition_table(
            unicode(self),
            E.partition_discs(
                *[sub_disc.get_xml() for sub_disc in self.partition_disc_set.all()]
                ),
            E.lvm_info(
                *[cur_vg.get_xml() for cur_vg in self.lvm_vg_set.all().prefetch_related("lvm_lv_set")]
            ),
            name=self.name,
            pk="%d" % (self.pk),
            key="ptable__%d" % (self.pk),
            description=unicode(self.description),
            valid="1" if self.valid else "0",
            enabled="1" if self.enabled else "0",
            nodeboot="1" if self.nodeboot else "0",
        )
        if _validate:
            pt_xml.append(
                E.problems(
                    *[E.problem(what, level="%d" % (log_level)) for log_level, what, is_global in prob_list if is_global]
                )
            )
        return pt_xml
    def _validate(self):
        # problem list, format is level, problem, global (always True for partition_table)
        p_list = []
        if not self.partition_disc_set.all():
            p_list.append((logging_tools.LOG_LEVEL_ERROR, "no discs defined", True))
        for p_disc in self.partition_disc_set.all():
            p_disc._validate()
        self.problems = p_list
        return self.problems + sum([cur_disc._get_problems() for cur_disc in self.partition_disc_set.all()], [])
    def __unicode__(self):
        return self.name
    class Meta:
        db_table = u'partition_table'
    class CSW_Meta:
        fk_ignore_list = ["partition_disc", "sys_partition", "lvm_lv", "lvm_vg"]

class partition_table_serializer(serializers.ModelSerializer):
    class Meta:
        model = partition_table
        fields = ("partition_disc_set", "lvm_lv_set", "lvm_vg_set", "name", "idx", "description", "valid",
            "enabled", "nodeboot", "act_partition_table", "new_partition_table")
        # otherwise the REST framework would try to store lvm_lv and lvm_vg
        read_only_fields = ("lvm_lv_set", "lvm_vg_set")

@receiver(signals.pre_save, sender=partition_table)
def partition_table_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        if not cur_inst.name.strip():
            raise ValidationError("name must not be zero")

class pci_entry(models.Model):
    idx = models.AutoField(db_column="pci_entry_idx", primary_key=True)
    device_idx = models.ForeignKey("device")
    domain = models.IntegerField(null=True, blank=True)
    bus = models.IntegerField(null=True, blank=True)
    slot = models.IntegerField(null=True, blank=True)
    func = models.IntegerField(null=True, blank=True)
    vendor = models.CharField(max_length=18)
    vendorname = models.CharField(max_length=192)
    device = models.CharField(max_length=18)
    devicename = models.CharField(max_length=192)
    class_field = models.CharField(max_length=18, db_column='class') # Field renamed because it was a Python reserved word. Field name made lowercase.
    classname = models.CharField(max_length=192)
    subclass = models.CharField(max_length=18)
    subclassname = models.CharField(max_length=192)
    revision = models.CharField(max_length=96)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'pci_entry'

class peer_information(models.Model):
    idx = models.AutoField(db_column="peer_information_idx", primary_key=True)
    s_netdevice = models.ForeignKey("netdevice", related_name="peer_s_netdevice")
    d_netdevice = models.ForeignKey("netdevice", related_name="peer_d_netdevice")
    penalty = models.IntegerField(default=0)
    date = models.DateTimeField(auto_now_add=True)
    def get_xml(self):
        return E.peer_information(
            pk="%d" % (self.pk),
            # why routing and not pi ?
            key="routing__%d" % (self.pk),
            from_devname=self.s_netdevice.devname,
            to_devname=self.d_netdevice.devname,
            from_device=self.s_netdevice.device.name,
            to_device=self.d_netdevice.device.name,
            from_device_full=self.s_netdevice.device.full_name,
            to_device_full=self.d_netdevice.device.full_name,
            s_netdevice="%d" % (self.s_netdevice_id),
            d_netdevice="%d" % (self.d_netdevice_id),
            from_penalty="%d" % (self.s_netdevice.penalty),
            to_penalty="%d" % (self.d_netdevice.penalty),
            penalty="%d" % (self.penalty or 1)
        )
    def __unicode__(self):
        return u"%s [%d] %s" % (self.s_netdevice.devname, self.penalty, self.d_netdevice.devname)
    class Meta:
        db_table = u'peer_information'

@receiver(signals.pre_save, sender=peer_information)
def peer_information_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        _check_integer(cur_inst, "penalty", min_val=1)

@receiver(signals.post_save, sender=peer_information)
def peer_information_post_save(sender, **kwargs):
    if not kwargs["raw"] and "instance" in kwargs:
        mark_routing_dirty()

@receiver(signals.post_delete, sender=peer_information)
def peer_information_post_delete(sender, **kwargs):
    if "instance" in kwargs:
        mark_routing_dirty()

# #class pi_connection(models.Model):
# #    idx = models.AutoField(db_column="pi_connection_idx", primary_key=True)
# #    package = models.ForeignKey("package")
# #    image = models.ForeignKey("image")
# #    install_time = models.IntegerField()
# #    date = models.DateTimeField(auto_now_add=True)
# #    class Meta:
# #        db_table = u'pi_connection'

# #class rrd_class(models.Model):
# #    idx = models.AutoField(db_column="rrd_class_idx", primary_key=True)
# #    name = models.CharField(unique=True, max_length=255)
# #    step = models.IntegerField(default=30)
# #    heartbeat = models.IntegerField(default=60)
# #    date = models.DateTimeField(auto_now_add=True)
# #    class Meta:
# #        db_table = u'rrd_class'
# #    def get_xml(self):
# #        return E.rrd_class(
# #            unicode(self),
# #            pk="%d" % (self.pk),
# #            key="rrdc__%d" % (self.pk),
# #            name=self.name,
# #            step="%d" % (self.step),
# #            heartbeat="%d" % (self.heartbeat),
# #        )
# #    def __unicode__(self):
# #        return self.name
# #
# #@receiver(signals.pre_save, sender=rrd_class)
# #def rrd_class_pre_save(sender, **kwargs):
# #    if "instance" in kwargs:
# #        cur_inst = kwargs["instance"]
# #        _check_empty_string(cur_inst, "name")
# #        _check_integer(cur_inst, "step")
# #        _check_integer(cur_inst, "heartbeat")
# #
# #class rrd_data(models.Model):
# #    idx = models.AutoField(db_column="rrd_data_idx", primary_key=True)
# #    rrd_set = models.ForeignKey("rrd_set")
# #    descr = models.CharField(max_length=765)
# #    descr1 = models.CharField(max_length=189)
# #    descr2 = models.CharField(max_length=189, blank=True)
# #    descr3 = models.CharField(max_length=189, blank=True)
# #    descr4 = models.CharField(max_length=189, blank=True)
# #    unit = models.CharField(max_length=96, blank=True)
# #    info = models.CharField(max_length=255, blank=True)
# #    from_snmp = models.BooleanField()
# #    base = models.IntegerField(null=True, blank=True)
# #    factor = models.FloatField(null=True, blank=True)
# #    var_type = models.CharField(max_length=3, blank=True)
# #    date = models.DateTimeField(auto_now_add=True)
# #    class Meta:
# #        db_table = u'rrd_data'
# #
# #class rrd_data_store(models.Model):
# #    idx = models.AutoField(db_column="rrd_data_store_idx", primary_key=True)
# #    device = models.ForeignKey("device")
# #    recv_time = models.IntegerField()
# #    data = models.TextField()
# #    date = models.DateTimeField(auto_now_add=True)
# #    class Meta:
# #        db_table = u'rrd_data_store'
# #
# #class rrd_rra(models.Model):
# #    idx = models.AutoField(db_column="rrd_rra_idx", primary_key=True)
# #    rrd_class = models.ForeignKey("rrd_class")
# #    cf = models.CharField(max_length=192, choices=[(val, val) for val in ALLOWED_CFS])
# #    steps = models.IntegerField(default=30)
# #    rows = models.IntegerField(default=2000)
# #    xff = models.FloatField(default=0.1)
# #    date = models.DateTimeField(auto_now_add=True)
# #    class Meta:
# #        db_table = u'rrd_rra'
# #    def get_xml(self):
# #        return E.rrd_rra(
# #            unicode(self),
# #            pk="%d" % (self.idx),
# #            key="rrdrra_%d" % (self.idx),
# #            rrd_class="%d" % (self.rrd_class_id),
# #            cf=self.cf,
# #            steps="%d" % (self.steps),
# #            rows="%d" % (self.rows),
# #            xff="%.2f" % (self.xff),
# #        )
# #    def __unicode__(self):
# #        return "%s:%d:%d:%.2f" % (self.cf, self.steps, self.rows, self.xff)
# #
# #@receiver(signals.pre_save, sender=rrd_rra)
# #def rrd_rra_pre_save(sender, **kwargs):
# #    if "instance" in kwargs:
# #        cur_inst = kwargs["instance"]
# #        _check_empty_string(cur_inst, "cf")
# #        _check_integer(cur_inst, "steps", min_val=1, max_val=3600)
# #        _check_integer(cur_inst, "rows", min_val=30, max_val=12000)
# #
# #class rrd_set(models.Model):
# #    idx = models.AutoField(db_column="rrd_set_idx", primary_key=True)
# #    device = models.ForeignKey("device")
# #    filename = models.CharField(max_length=765, blank=True, null=True)
# #    date = models.DateTimeField(auto_now_add=True)
# #    class Meta:
# #        db_table = u'rrd_set'

class session_data(models.Model):
    idx = models.AutoField(db_column="session_data_idx", primary_key=True)
    session_id = models.CharField(unique=True, max_length=96)
    value = models.TextField()
    user = models.ForeignKey("user")
    remote_addr = models.TextField(blank=True)
    alias = models.CharField(max_length=255, blank=True)
    login_time = models.DateTimeField(null=True, blank=True)
    logout_time = models.DateTimeField(null=True, blank=True)
    forced_logout = models.BooleanField()
    rebuild_server_routes = models.BooleanField(default=False)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'session_data'

class sge_complex(models.Model):
    idx = models.AutoField(db_column="sge_complex_idx", primary_key=True)
    name = models.CharField(unique=True, max_length=255)
    total_time = models.CharField(max_length=192, blank=True)
    slot_time = models.CharField(max_length=192, blank=True)
    pe_slots_min = models.IntegerField(null=True, blank=True)
    pe_slots_max = models.IntegerField(null=True, blank=True)
    default_queue = models.CharField(max_length=192, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'sge_complex'

class sge_host(models.Model):
    idx = models.AutoField(db_column="sge_host_idx", primary_key=True)
    host_name = models.CharField(max_length=255)
    device = models.ForeignKey("device")
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'sge_host'

class sge_job(models.Model):
    idx = models.AutoField(db_column="sge_job_idx", primary_key=True)
    job_uid = models.CharField(unique=True, max_length=255)
    jobname = models.CharField(max_length=255)
    jobnum = models.IntegerField()
    taskid = models.IntegerField(null=True, blank=True)
    jobowner = models.CharField(max_length=255)
    jobgroup = models.CharField(max_length=255)
    log_path = models.TextField()
    sge_user = models.ForeignKey("sge_user")
    queue_time = models.DateTimeField(null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'sge_job'

class sge_job_run(models.Model):
    idx = models.AutoField(db_column="sge_job_run_idx", primary_key=True)
    sge_job = models.ForeignKey("sge_job")
    account = models.CharField(max_length=384)
    sge_userlist = models.ForeignKey("sge_userlist")
    sge_project = models.ForeignKey("sge_project")
    priority = models.IntegerField(null=True, blank=True)
    granted_pe = models.CharField(max_length=192)
    slots = models.IntegerField(null=True, blank=True)
    failed = models.IntegerField(null=True, blank=True)
    failed_str = models.CharField(max_length=765, blank=True)
    exit_status = models.IntegerField(null=True, blank=True)
    masterq = models.CharField(max_length=255)
    start_time = models.DateTimeField(null=True, blank=True)
    start_time_sge = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    end_time_sge = models.DateTimeField(null=True, blank=True)
    sge_ru_wallclock = models.IntegerField(null=True, blank=True)
    sge_cpu = models.IntegerField(null=True, blank=True)
    sge_mem = models.FloatField(null=True, blank=True)
    sge_io = models.IntegerField(null=True, blank=True)
    sge_iow = models.IntegerField(null=True, blank=True)
    sge_maxvmem = models.IntegerField(null=True, blank=True)
    sge_parsed = models.IntegerField(null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'sge_job_run'

class sge_log(models.Model):
    idx = models.AutoField(db_column="sge_log_idx", primary_key=True)
    sge_job = models.ForeignKey("sge_job")
    sge_queue = models.ForeignKey("sge_queue")
    sge_host = models.ForeignKey("sge_host")
    log_level = models.IntegerField(null=True, blank=True)
    log_str = models.CharField(max_length=765)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'sge_log'

class sge_pe_host(models.Model):
    idx = models.AutoField(db_column="sge_pe_host_idx", primary_key=True)
    sge_job_run = models.ForeignKey("sge_job_run")
    device = models.ForeignKey("device")
    hostname = models.CharField(max_length=255)
    num_slots = models.IntegerField(null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'sge_pe_host'

class sge_project(models.Model):
    idx = models.AutoField(db_column="sge_project_idx", primary_key=True)
    name = models.CharField(unique=True, max_length=255)
    oticket = models.FloatField(null=True, blank=True)
    fshare = models.FloatField(null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'sge_project'

class sge_queue(models.Model):
    idx = models.AutoField(db_column="sge_queue_idx", primary_key=True)
    queue_name = models.CharField(max_length=255)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'sge_queue'

class sge_ul_ult(models.Model):
    idx = models.AutoField(db_column="sge_ul_ult_idx", primary_key=True)
    sge_userlist = models.ForeignKey("sge_userlist")
    sge_userlist_type = models.ForeignKey("sge_userlist_type")
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'sge_ul_ult'

class sge_user(models.Model):
    idx = models.AutoField(db_column="sge_user_idx", primary_key=True)
    name = models.CharField(unique=True, max_length=255)
    oticket = models.FloatField(null=True, blank=True)
    fshare = models.FloatField(null=True, blank=True)
    default_project = models.ForeignKey("sge_project", null=True)
    cluster_user = models.ForeignKey("user")
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'sge_user'

class sge_user_con(models.Model):
    idx = models.AutoField(db_column="sge_user_con_idx", primary_key=True)
    user = models.ForeignKey("user")
    sge_config = models.IntegerField()
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'sge_user_con'

class sge_userlist(models.Model):
    idx = models.AutoField(db_column="sge_userlist_idx", primary_key=True)
    name = models.CharField(unique=True, max_length=255)
    oticket = models.FloatField(null=True, blank=True)
    fshare = models.FloatField(null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'sge_userlist'

class sge_userlist_type(models.Model):
    idx = models.AutoField(db_column="sge_userlist_type_idx", primary_key=True)
    name = models.CharField(unique=True, max_length=192)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'sge_userlist_type'

class snmp_config(models.Model):
    idx = models.AutoField(db_column="snmp_config_idx", primary_key=True)
    config_old = models.IntegerField(null=True, blank=True, db_column="config")
    config = models.ForeignKey("config", db_column="new_config_id")
    snmp_mib = models.ForeignKey("snmp_mib")
    device = models.ForeignKey("device", null=True, default=None)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'snmp_config'

class snmp_mib(models.Model):
    idx = models.AutoField(db_column="snmp_mib_idx", primary_key=True)
    name = models.CharField(unique=True, max_length=192)
    descr = models.CharField(max_length=765, blank=True)
    mib = models.CharField(max_length=255)
    rrd_key = models.CharField(max_length=192)
    unit = models.CharField(max_length=96, blank=True)
    base = models.IntegerField(null=True, blank=True)
    factor = models.FloatField(null=True, blank=True)
    var_type = models.CharField(max_length=3, blank=True)
    special_command = models.CharField(max_length=765, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'snmp_mib'

class status(models.Model):
    idx = models.AutoField(db_column="status_idx", primary_key=True)
    status = models.CharField(unique=True, max_length=255)
    prod_link = models.BooleanField(default=True)
    memory_test = models.BooleanField(default=False)
    boot_local = models.BooleanField(default=False)
    do_install = models.BooleanField(default=False)
    is_clean = models.BooleanField(default=False)
    # allow mother to set bools according to status
    allow_boolean_modify = models.BooleanField(default=True)
    date = models.DateTimeField(auto_now_add=True)
    def __unicode__(self):
        # print ".", self.status
        return u"%s (%s)%s" % (
            self.status,
            ",".join([short for short, attr_name in [
                ("link"  , "prod_link"),
                ("mem"   , "memory_test"),
                ("loc"   , "boot_local"),
                ("ins"   , "do_install"),
                ("retain", "is_clean")] if getattr(self, attr_name)]),
            "(*)" if self.allow_boolean_modify else "")
    def get_xml(self, prod_net=None):
        return E.status(
            unicode(self) if prod_net is None else "%s into %s" % (unicode(self), unicode(prod_net)),
            pk="%d" % (self.pk),
            prod_net="%d" % (0 if prod_net is None else prod_net.pk),
            key="status__%d" % (self.pk),
        )
    class Meta:
        db_table = u'status'

class sys_partition(models.Model):
    idx = models.AutoField(db_column="sys_partition_idx", primary_key=True)
    partition_table = models.ForeignKey("partition_table")
    name = models.CharField(max_length=192)
    mountpoint = models.CharField(max_length=192, default="/")
    mount_options = models.CharField(max_length=255, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'sys_partition'

class tree_node(models.Model):
    idx = models.AutoField(primary_key=True)
    device = models.ForeignKey("device", default=None)
    is_dir = models.BooleanField(default=False)
    is_link = models.BooleanField(default=False)
    parent = models.ForeignKey("tree_node", null=True, default=None)
    # is an intermediate node is has not to be created
    intermediate = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    def __cmp__(self, other):
        if self.is_dir == other.is_dir:
            if self.wc_files.dest < other.wc_files.dest:
                return -1
            elif self.wc_files.dest > other.wc_files.dest:
                return 1
            else:
                return 0
        elif self.is_dir:
            return -1
        else:
            return +1
    def get_type_str(self):
        return "dir" if self.is_dir else ("link" if self.is_link else "file")
    def __unicode__(self):
        return "tree_node, %s" % (self.get_type_str())

class wc_files(models.Model):
    idx = models.AutoField(db_column="wc_files_idx", primary_key=True)
    device = models.ForeignKey("device")
    tree_node = models.OneToOneField("tree_node", null=True, default=None)
    run_number = models.IntegerField(default=0)
    config = models.ManyToManyField("config")
    # config = models.CharField(max_length=255, blank=True)
    uid = models.IntegerField(default=0, blank=True)
    gid = models.IntegerField(default=0, blank=True)
    mode = models.IntegerField(default=0755, blank=True)
    dest_type = models.CharField(max_length=8, choices=(
        ("f", "file"),
        ("l", "link"),
        ("d", "directory"),
        ("e", "erase"),
        ("c", "copy"),
        ("i", "internal"),
    ))
    # source path
    source = models.CharField(max_length=1024)
    # destination path, relative to tree_node
    dest = models.CharField(max_length=1024)
    # error
    error_flag = models.BooleanField(default=False)
    # content, defaults to the empty string
    content = models.TextField(blank=True, default="")
    date = models.DateTimeField(auto_now_add=True)
    def get_xml(self):
        try:
            # stupid hack, FIXME
            E.content(
                self.content
            )
        except:
            c_str = "<BINARY>"
        else:
            c_str = self.content
        return E.content(
            c_str,
            run_number="%d" % (self.run_number),
            uid="%d" % (self.uid),
            gid="%d" % (self.gid),
            mode="%d" % (self.mode),
            error_flag="1" if self.error_flag else "0"
        )
    class Meta:
        db_table = u'wc_files'

def get_related_models(in_obj, m2m=False, detail=False, check_all=False):
    used_objs = [] if detail else 0
    if hasattr(in_obj, "CSW_Meta"):
        # copy list because we remove entries as we iterate over foreign models
        fk_ignore_list = [entry for entry in getattr(in_obj.CSW_Meta, "fk_ignore_list", [])]
    else:
        fk_ignore_list = []
    if check_all:
        ignore_list = []
    else:
        ignore_list = fk_ignore_list
    for rel_obj in in_obj._meta.get_all_related_objects():
        rel_field_name = rel_obj.field.name
        # print rel_obj.model._meta.object_name, rel_obj.model._meta.object_name in ignore_list, ignore_list
        if rel_obj.model._meta.object_name not in ignore_list:
            if detail:
                used_objs.extend(list(rel_obj.model.objects.filter(Q(**{rel_field_name : in_obj}))))
            else:
                used_objs += rel_obj.model.objects.filter(Q(**{rel_field_name : in_obj})).count()
        else:
            ignore_list.remove(rel_obj.model._meta.object_name)
    if m2m:
        for m2m_obj in in_obj._meta.get_all_related_many_to_many_objects():
            m2m_field_name = m2m_obj.field.name
            if detail:
                used_objs.extend(list(m2m_obj.model.objects.filter(Q(**{m2m_field_name : in_obj}))))
            else:
                used_objs += m2m_obj.model.objects.filter(Q(**{m2m_field_name : in_obj})).count()
    if ignore_list:
        raise ImproperlyConfigured("ignore_list not empty, typos (model %s, %s) ?" % (
            in_obj._meta.model_name,
            ", ".join(ignore_list)
            ))
    return used_objs

def get_change_reset_list(s_obj, d_obj, required_changes=None):
    if not required_changes:
        required_changes = {}
    c_list, r_list = ([], [])
    for _f in s_obj._meta.fields:
        s_val, d_val = (getattr(s_obj, _f.name), getattr(d_obj, _f.name))
        cur_t = _f.get_internal_type()
        # ignore Date(Time)Fields
        if _f.name in required_changes and cur_t not in ["DateTimeField", "DateField"]:
            if cur_t == "ForeignKey":
                # print _f.name, cur_t, d_val, required_changes[_f.name]
                if d_val is not None:
                    d_val = d_val.pk
            if d_val != required_changes[_f.name]:
                print _f.name, d_val
                r_list.append((_f.name, d_val))
        if cur_t in ["CharField", "IntegerField", "PositiveIntegerField", "BooleanField"]:
            if s_val != d_val:
                c_list.append((_f.verbose_name, "changed from '%s' to '%s'" % (s_val, d_val)))
        elif cur_t in ["ForeignKeyField"]:
            print "**", _f.name
        else:
            print cur_t
    return c_list, r_list

class md_check_data_store(models.Model):
    idx = models.AutoField(primary_key=True)
    device = models.ForeignKey(device)
    name = models.CharField(max_length=64, default="")
    mon_check_command = models.ForeignKey(mon_check_command)
    data = models.TextField(default="")
    created = models.DateTimeField(auto_now_add=True, auto_now=True)
    def get_xml(self):
        return E.md_check_data_store(
            unicode(self),
            pk="%d" % (self.pk),
            key="mdcds__%d" % (self.pk),
            device="%d" % (self.device_id),
            name="%s" % (self.name),
            mon_check_command="%d" % (self.mon_check_command_id),
            data="%s" % (etree.tostring(etree.fromstring(self.data), pretty_print=True)),
        )
    def __unicode__(self):
        return self.name

class domain_name_tree(object):
    # helper structure
    def __init__(self):
        self.__node_dict = {}
        self.__domain_lut = {}
        for cur_node in domain_tree_node.objects.all().order_by("depth"):
            self.__node_dict[cur_node.pk] = cur_node
            self.__domain_lut.setdefault(cur_node.full_name, []).append(cur_node)
            cur_node._sub_tree = {}
            if cur_node.parent_id is None:
                self._root_node = cur_node
            else:
                if cur_node.depth - 1 != self.__node_dict[cur_node.parent_id].depth:
                    # fix depth
                    cur_node.depth = self.__node_dict[cur_node.parent_id].depth + 1
                    cur_node.save()
                self.__node_dict[cur_node.parent_id]._sub_tree.setdefault(cur_node.name, []).append(cur_node)
    def check_intermediate(self):
        used_pks = set(device.objects.all().values_list("domain_tree_node", flat=True)) | set(net_ip.objects.all().values_list("domain_tree_node", flat=True))
        for cur_tn in self.__node_dict.itervalues():
            is_im = cur_tn.pk not in used_pks
            if cur_tn.intermediate != is_im:
                cur_tn.intermediate = is_im
                cur_tn.save()
    def add_device_references(self):
        used_dtn_pks = list(device.objects.filter(Q(enabled=True) & Q(device_group__enabled=True)).values_list("domain_tree_node_id", flat=True))
        used_dict = dict([(key, used_dtn_pks.count(key)) for key in set(used_dtn_pks)])
        for value in self.__node_dict.itervalues():
            value.local_refcount = used_dict.get(value.pk, 0)
        for value in self.__node_dict.itervalues():
            value.total_refcount = self._get_sub_refcounts(value)
    def _get_sub_refcounts(self, s_node):
        return self.__node_dict[s_node.pk].local_refcount + sum([self._get_sub_refcounts(sub_node) for sub_node in sum(s_node._sub_tree.itervalues(), [])])
    def add_domain(self, new_domain_name):
        dom_parts = list(reversed(new_domain_name.split(".")))
        cur_node = self._root_node
        for _part_num, dom_part in enumerate(dom_parts):
            # part_num == len(dom_parts) - 1
            if dom_part not in cur_node._sub_tree:
                new_node = domain_tree_node(
                    name=dom_part,
                    parent=cur_node,
                    node_postfix="",
                    full_name="%s.%s" % (dom_part, cur_node.full_name),
                    intermediate=False,
                    depth=cur_node.depth + 1)
                new_node.save()
                self.__node_dict[new_node.pk] = new_node
                cur_node._sub_tree.setdefault(dom_part, []).append(new_node)
                new_node._sub_tree = {}
            # add to the first entry in sub_tree
            cur_node = cur_node._sub_tree[dom_part][0]
        return cur_node
    def get_domain_tree_node(self, dom_name):
        return self.__domain_lut[dom_name]
    def get_sorted_pks(self):
        return self._root_node.get_sorted_pks()
    def __getitem__(self, key):
        if type(key) in [int, long]:
            return self.__node_dict[key]
    def keys(self):
        return self.__node_dict.keys()
    def get_xml(self, no_intermediate=False):
        pk_list = self.get_sorted_pks()
        if no_intermediate:
            return E.domain_tree_nodes(
                *[self.__node_dict[pk].get_xml() for pk in pk_list if self.__node_dict[pk].intermediate == False]
            )
        else:
            return E.domain_tree_nodes(
                *[self.__node_dict[pk].get_xml() for pk in pk_list]
            )
    def all(self):
        # emulate queryset
        for pk in self.get_sorted_pks():
            yield self[pk]

# domain name models
class domain_tree_node(models.Model):
    idx = models.AutoField(primary_key=True)
    # the top node has no name
    name = models.CharField(max_length=64, default="")
    # full_name, gets computed on structure change
    full_name = models.CharField(max_length=256, default="")
    # the top node has no parent
    parent = models.ForeignKey("self", null=True)
    # postfix to add to device name
    node_postfix = models.CharField(max_length=16, default="", blank=True)
    # depth information, top_node has idx=0
    depth = models.IntegerField(default=0)
    # intermediate node (no IPs allowed)
    intermediate = models.BooleanField(default=False)
    # creation timestamp
    created = models.DateTimeField(auto_now_add=True, auto_now=True)
    # create short_names entry for /etc/hosts
    create_short_names = models.BooleanField(default=True)
    # create entry for clusternodes even when network not in list
    always_create_ip = models.BooleanField(default=False)
    # use for nameserver config
    write_nameserver_config = models.BooleanField(default=False)
    # comment
    comment = models.CharField(max_length=256, default="", blank=True)
    def get_sorted_pks(self):
        return [self.pk] + sum([pk_list for _sub_name, pk_list in sorted([(key, sum([sub_value.get_sorted_pks() for sub_value in value], [])) for key, value in self._sub_tree.iteritems()])], [])
    def __unicode__(self):
        if self.depth:
            if self.depth > 2:
                return u"%s%s%s (%s)" % (r"| " * (self.depth - 1), r"+-", self.name, self.full_name)
            else:
                return u"%s%s (%s)" % (r"+-" * (self.depth), self.name, self.full_name)
        else:
            return u"[TLN]"
    def get_xml(self):
        r_xml = E.domain_tree_node(
            unicode(self),
            pk="%d" % (self.pk),
            key="dtn__%d" % (self.pk),
            name=self.name,
            full_name=self.full_name,
            parent="%d" % (self.parent_id or 0),
            node_postfix="%s" % (self.node_postfix),
            depth="%d" % (self.depth),
            intermediate="%d" % (1 if self.intermediate else 0),
            create_short_names="1" if self.create_short_names else "0",
            write_nameserver_config="1" if self.write_nameserver_config else "0",
            always_create_ip="1" if self.always_create_ip else "0",
            comment="%s" % (self.comment or ""),
        )
        if hasattr(self, "local_refcount"):
            r_xml.attrib["local_refcount"] = "%d" % (self.local_refcount)
            r_xml.attrib["total_refcount"] = "%d" % (self.total_refcount)
        return r_xml

@receiver(signals.pre_save, sender=domain_tree_node)
def domain_tree_node_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        cur_inst.name = cur_inst.name.strip()
        if cur_inst.name and cur_inst.name.count("."):
            raise ValidationError("dot '.' not allowed in domain_name part")
        if cur_inst.depth and not valid_domain_re.match(cur_inst.name):
            raise ValidationError("illegal characters in name '%s'" % (cur_inst.name))
        if cur_inst.intermediate:
            if net_ip.objects.filter(Q(domain_tree_node=cur_inst)).count() + device.objects.filter(Q(domain_tree_node=cur_inst)).count():
                # print "***", unicode(cur_inst)
                raise ValidationError("cannot set used domain_tree_node as intermediate")
        cur_inst.node_postfix = cur_inst.node_postfix.strip()
        if not cur_inst.node_postfix and valid_domain_re.match(cur_inst.node_postfix):
            raise ValidationError("illegal characters in node postfix '%s'" % (cur_inst.node_postfix))
        if cur_inst.depth:
            _check_empty_string(cur_inst, "name")
            parent_node = cur_inst.parent
            new_full_name = "%s%s" % (
                cur_inst.name,
                ".%s" % (parent_node.full_name) if parent_node.full_name else "",
            )
            cur_inst.depth = parent_node.depth + 1
            if new_full_name != cur_inst.full_name:
                cur_inst.full_name = new_full_name
                cur_inst.full_name_changed = True
            used_names = domain_tree_node.objects.exclude(Q(pk=cur_inst.pk)).filter(Q(depth=cur_inst.depth) & Q(parent=cur_inst.parent)).values_list("name", flat=True)
            if cur_inst.name in used_names:
                raise ValidationError("name '%s' already used here" % (cur_inst.name))
        else:
            _check_non_empty_string(cur_inst, "name")
            _check_non_empty_string(cur_inst, "node_postfix")


@receiver(signals.post_save, sender=domain_tree_node)
def domain_tree_node_post_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        if getattr(cur_inst, "full_name_changed", False):
            for sub_node in domain_tree_node.objects.filter(Q(parent=cur_inst)):
                sub_node.save()

def _migrate_mon_type(cat_tree):
    # read all monitoring_config_types
    cur_cats = set(mon_check_command.objects.all().values_list("categories", flat=True))
    if cur_cats == set([None]):
        all_mon_ct = dict([(pk, "%s/%s" % (
            TOP_MONITORING_CATEGORY,
            cur_name)) for pk, cur_name in mon_check_command_type.objects.all().values_list("pk", "name")])
        mig_dict = dict([(key, cat_tree.add_category(value)) for key, value in all_mon_ct.iteritems()])
        for cur_mon_cc in mon_check_command.objects.all().prefetch_related("categories"):
            if cur_mon_cc.mon_check_command_type_id:
                cur_mon_cc.categories.add(mig_dict[cur_mon_cc.mon_check_command_type_id])
                cur_mon_cc.mon_check_command_type = None
                cur_mon_cc.save()

def _migrate_location_type(cat_tree):
    # read all monitoring_config_types
    all_loc_ct = dict([(pk, "%s/%s" % (
        TOP_LOCATION_CATEGORY,
        cur_name)) for pk, cur_name in device_location.objects.all().values_list("pk", "location")])
    mig_dict = dict([(key, cat_tree.add_category(value)) for key, value in all_loc_ct.iteritems()])
    for cur_dev in device.objects.all():
        if cur_dev.device_location_id:
            cur_dev.categories.add(mig_dict[cur_dev.device_location_id])
            cur_dev.device_location = None
            cur_dev.save()

class category_tree(object):
    # helper structure
    def __init__(self, **kwargs):
        self.with_device_count = kwargs.get("with_device_count", False)
        self.with_devices = kwargs.get("with_devices", False)
        self.__node_dict = {}
        self.__category_lut = {}
        if not category.objects.all().count():
            category(name="", full_name="", comment="top node").save()
        if self.with_device_count or self.with_devices:
            _sql = category.objects.all().prefetch_related("device_set", "config_set", "mon_check_command_set")
        else:
            _sql = category.objects.all()
        for cur_node in _sql.order_by("depth"):
            if self.with_device_count or self.with_devices:
                cur_node.device_count = cur_node.device_set.count() + cur_node.config_set.count() + cur_node.mon_check_command_set.count()
            self.__node_dict[cur_node.pk] = cur_node
            self.__category_lut.setdefault(cur_node.full_name, []).append(cur_node)
            cur_node._sub_tree = {}
            if cur_node.parent_id is None:
                self._root_node = cur_node
            else:
                if cur_node.depth - 1 != self.__node_dict[cur_node.parent_id].depth:
                    # fix depth
                    cur_node.depth = self.__node_dict[cur_node.parent_id].depth + 1
                    cur_node.save()
                self.__node_dict[cur_node.parent_id]._sub_tree.setdefault(cur_node.name, []).append(cur_node)
        if not TOP_MONITORING_CATEGORY in self.__category_lut:
            _migrate_mon_type(self)
        if not TOP_LOCATION_CATEGORY in self.__category_lut:
            _migrate_location_type(self)
        for check_name in [TOP_CONFIG_CATEGORY, TOP_DEVICE_CATEGORY]:
            if not check_name in self.__category_lut:
                self.add_category(check_name)
        for cur_node in self.__node_dict.itervalues():
            is_immutable = cur_node.full_name in ["", TOP_CONFIG_CATEGORY, TOP_MONITORING_CATEGORY, TOP_DEVICE_CATEGORY, TOP_LOCATION_CATEGORY]
            if cur_node.immutable != is_immutable:
                cur_node.immutable = is_immutable
                cur_node.save()
    def add_category(self, new_category_name):
        while new_category_name.startswith("/"):
            new_category_name = new_category_name[1:]
        while new_category_name.endswith("/"):
            new_category_name = new_category_name[:-1]
        while new_category_name.count("//"):
            new_category_name = new_category_name.replace("//", "/")
        cat_parts = list(new_category_name.split("/"))
        cur_node = self._root_node
        for _part_num, cat_part in enumerate(cat_parts):
            # part_num == len(cat_parts) - 1
            if cat_part not in cur_node._sub_tree:
                new_node = category(
                    name=cat_part,
                    parent=cur_node,
                    full_name="%s/%s" % (cur_node.full_name, cat_part),
                    depth=cur_node.depth + 1)
                new_node.save()
                self.__node_dict[new_node.pk] = new_node
                cur_node._sub_tree.setdefault(cat_part, []).append(new_node)
                new_node._sub_tree = {}
            # add to the first entry in sub_tree
            cur_node = cur_node._sub_tree[cat_part][0]
        return cur_node
    def get_category(self, cat_name):
        return self.__category_lut[cat_name]
    def get_sorted_pks(self):
        return self._root_node.get_sorted_pks()
    def __contains__(self, key):
        if type(key) in [int, long]:
            return key in self.__node_dict
        else:
            return key in self.__category_lut
    def __getitem__(self, key):
        if type(key) in [int, long]:
            return self.__node_dict[key]
    def keys(self):
        return self.__node_dict.keys()
    def prune(self):
        # removes all unreferenced nodes
        removed = True
        while removed:
            removed = False
            del_nodes = []
            for cur_leaf in self.__node_dict.itervalues():
                if not cur_leaf._sub_tree and not cur_leaf.immutable:
                    # count related models (with m2m)
                    if not get_related_models(cur_leaf, m2m=True):
                        del_nodes.append(cur_leaf)
            for del_node in del_nodes:
                del self[del_node.parent_id]._sub_tree[del_node.name]
                del self.__node_dict[del_node.pk]
                del_node.delete()
            removed = len(del_nodes) > 0
    def get_xml(self):
        pk_list = self.get_sorted_pks()
        return E.categories(
            *[self.__node_dict[pk].get_xml(with_devices=self.with_devices) for pk in pk_list]
        )

# category
class category(models.Model):
    idx = models.AutoField(primary_key=True)
    # the top node has no name
    name = models.CharField(max_length=64, default="")
    # full_name, gets computed on structure change
    full_name = models.CharField(max_length=1024, default="")
    # the top node has no parent
    parent = models.ForeignKey("self", null=True)
    # depth information, top_node has idx=0
    depth = models.IntegerField(default=0)
    # creation timestamp
    created = models.DateTimeField(auto_now_add=True, auto_now=True)
    # immutable
    immutable = models.BooleanField(default=False)
    # location field for location nodes, defaults to Vienna
    latitude = models.FloatField(default=48.1)
    longitude = models.FloatField(default=16.3)
    # comment
    comment = models.CharField(max_length=256, default="", blank=True)
    def get_sorted_pks(self):
        return [self.pk] + sum([pk_list for _sub_name, pk_list in sorted([(key, sum([sub_value.get_sorted_pks() for sub_value in value], [])) for key, value in self._sub_tree.iteritems()])], [])
    def __unicode__(self):
        return u"%s" % (self.full_name if self.depth else "[TLN]")
    def get_xml(self, **kwargs):
        with_devices = kwargs.get("with_devices", False)
        r_xml = E.category(
            unicode(self),
            pk="%d" % (self.pk),
            key="dtn__%d" % (self.pk),
            name=self.name,
            full_name=self.full_name,
            parent="%d" % (self.parent_id or 0),
            depth="%d" % (self.depth),
            comment="%s" % (self.comment or ""),
            immutable="1" if self.immutable else "0",
            latitude="%.6f" % (self.latitude),
            longitude="%.6f" % (self.longitude),
            device_count="%d" % (getattr(self, "device_count", 0)),
        )
        if with_devices:
            r_xml.attrib["devices"] = "::".join(["%d" % (cur_dev.pk) for cur_dev in self.device_set.all()])
        return r_xml

@receiver(signals.pre_save, sender=category)
def category_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        cur_inst.name = cur_inst.name.strip()
        _check_float(cur_inst, "latitude")
        _check_float(cur_inst, "longitude")
        if cur_inst.name:
            if  cur_inst.name.count("/"):
                raise ValidationError("slash '/' not allowed in name part")
        if cur_inst.depth and not valid_category_re.match(cur_inst.name):
            raise ValidationError("illegal characters in name '%s'" % (cur_inst.name))
        if cur_inst.depth:
            _check_empty_string(cur_inst, "name")
            parent_node = cur_inst.parent
            new_full_name = "%s/%s" % (
                parent_node.full_name,
                cur_inst.name,
            )
            cur_inst.depth = parent_node.depth + 1
            if new_full_name != cur_inst.full_name:
                cur_inst.full_name = new_full_name
                cur_inst.full_name_changed = True
            # check for used named
            used_names = category.objects.exclude(Q(pk=cur_inst.pk)).filter(Q(depth=cur_inst.depth) & Q(parent=cur_inst.parent)).values_list("name", flat=True)
            if cur_inst.name in used_names:
                raise ValidationError("name '%s' already used here" % (cur_inst.name))
        else:
            _check_non_empty_string(cur_inst, "name")

@receiver(signals.post_save, sender=category)
def category_post_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        if getattr(cur_inst, "full_name_changed", False):
            for sub_node in category.objects.filter(Q(parent=cur_inst)):
                sub_node.save()

KPMC_MAP = {
    "devg"          : device_group,
    "dev"           : device,
    "nd"            : netdevice,
    "ip"            : net_ip,
    "routing"       : peer_information,
    "conf"          : config,
    "varstr"        : config_str,
    "varint"        : config_int,
    "varbool"       : config_bool,
    "varblob"       : config_blob,
    "cscript"       : config_script,
    "image"         : image,
    "kernel"        : kernel,
    "pdisc"         : partition_disc,
    "part"          : partition,
    "monper"        : mon_period,
    "mondt"         : mon_device_templ,
    "monst"         : mon_service_templ,
    "mondet"        : mon_device_esc_templ,
    "monset"        : mon_service_esc_templ,
    "moncg"         : mon_contactgroup,
    "monhc"         : mon_host_cluster,
    "monn"          : mon_notification,
    "monsc"         : mon_service_cluster,
    "moncc"         : mon_check_command,
    "moncon"        : mon_contact,
    "nwdt"          : network_device_type,
    "nwt"           : network_type,
    # "dc"            : device_class,
    # "dl"            : device_location,
    "nw"            : network,
    "user"          : user,
    "ps"            : package_search,
    "group"         : group,
    "dv"            : device_variable,
    "ptable"        : partition_table,
    # "rrdc"          : rrd_class,
    # "rrdrra"        : rrd_rra,
    "lvm_vg"        : lvm_vg,
    "lvm_lv"        : lvm_lv,
    "package_repo"  : package_repo,
    "mdcds"         : md_check_data_store,
    "dtn"           : domain_tree_node,
    "cat"           : category,
    "hcc"           : host_check_command,
    "cd_connection" : cd_connection,
    "monhd"         : mon_host_dependency_templ,
}
