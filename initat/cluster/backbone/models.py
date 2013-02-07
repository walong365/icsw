#!/usr/bin/python-init

from django.db import models
from django.contrib.auth.models import User, Group, Permission
import datetime
from django.db.models import Q, signals
from django.dispatch import receiver
from django.core.exceptions import ValidationError
from lxml import etree
from lxml.builder import E
import uuid
import re
import time
import ipvx_tools
import logging_tools
import pprint
import pytz
import process_tools
import hashlib
import base64
import os
from django.conf import settings
from rest_framework import serializers
from django.utils.functional import memoize

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

def to_system_tz(in_dt):
    return in_dt.astimezone(system_timezone)

# cluster_log_source
cluster_log_source = None

def boot_uuid(cur_uuid):
    return "%s-boot" % (cur_uuid[:-5])

# helper functions
def _check_integer(inst, attr_name, **kwargs):
    cur_val = getattr(inst, attr_name)
    min_val, max_val = (kwargs.get("min_val", None),
                        kwargs.get("max_val", None))
    if cur_val is None and kwargs.get("none_to_zero", False):
        cur_val = 0
    try:
        cur_val = int(cur_val)
    except:
        raise ValidationError("%s is not an integer" % (attr_name))
    else:
        if min_val is not None and max_val is not None:
            if min_val is None:
                if cur_val > max_val:
                    raise ValidationError("%s too high (%d > %d)" % (
                        attr_name,
                        cur_val,
                        max_val))
            elif max_val is None:
                if cur_val < min_val:
                    raise ValidationError("%s too low (%d < %d)" % (
                        attr_name,
                        cur_val,
                        min_val))
            else:
                if cur_val < min_val or cur_val > max_val:
                    raise ValidationError("%s (%d) not in [%d, %d]" % (
                        attr_name,
                        cur_val,
                        min_val,
                        max_val))
        setattr(inst, attr_name, cur_val)
        return cur_val
    
def _check_empty_string(inst, attr_name):
    cur_val = getattr(inst, attr_name)
    if not cur_val.strip():
        raise ValidationError("%s can not be empty" % (attr_name))
    
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

##class app_config_con(models.Model):
##    idx = models.AutoField(db_column="app_config_con_idx", primary_key=True)
##    application = models.ForeignKey("application")
##    config = models.ForeignKey("config")
##    date = models.DateTimeField(auto_now_add=True)
##    class Meta:
##        db_table = u'app_config_con'
##
##class app_devgroup_con(models.Model):
##    idx = models.AutoField(db_column="app_devgroup_con_idx", primary_key=True)
##    application = models.ForeignKey("application")
##    device_group = models.ForeignKey("device_group")
##    date = models.DateTimeField(auto_now_add=True)
##    class Meta:
##        db_table = u'app_devgroup_con'
##
##class app_instpack_con(models.Model):
##    idx = models.AutoField(db_column="app_instpack_con_idx", primary_key=True)
##    application = models.ForeignKey("application")
##    inst_package = models.ForeignKey("inst_package")
##    date = models.DateTimeField(auto_now_add=True)
##    class Meta:
##        db_table = u'app_instpack_con'
##
##class application(models.Model):
##    idx = models.AutoField(db_column="application_idx", primary_key=True)
##    name = models.CharField(unique=True, max_length=255)
##    description = models.TextField()
##    date = models.DateTimeField(auto_now_add=True)
##    class Meta:
##        db_table = u'application'

class architecture(models.Model):
    idx = models.AutoField(db_column="architecture_idx", primary_key=True)
    architecture = models.CharField(default="", unique=True, max_length=128)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'architecture'
    def __unicode__(self):
        return self.architecture

class ccl_dgroup_con(models.Model):
    idx = models.AutoField(db_column="ccl_dgroup_con_idx", primary_key=True)
    ccl_event = models.ForeignKey("ccl_event")
    device_group = models.ForeignKey("device_group")
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'ccl_dgroup_con'

class ccl_dloc_con(models.Model):
    idx = models.AutoField(db_column="ccl_dloc_con_idx", primary_key=True)
    ccl_event = models.ForeignKey("ccl_event")
    device_location = models.ForeignKey("device_location")
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'ccl_dloc_con'

class ccl_event(models.Model):
    idx = models.AutoField(db_column="ccl_event_idx", primary_key=True)
    device = models.ForeignKey("device")
    rrd_data = models.ForeignKey("rrd_data")
    device_class = models.ForeignKey("device_class")
    threshold = models.FloatField(null=True, blank=True)
    threshold_class = models.IntegerField()
    cluster_event = models.ForeignKey("cluster_event")
    hysteresis = models.FloatField(null=True, blank=True)
    disabled = models.BooleanField()
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'ccl_event'

class ccl_event_log(models.Model):
    idx = models.AutoField(db_column="ccl_event_log_idx", primary_key=True)
    device = models.ForeignKey("device", null=True, blank=True)
    ccl_event = models.ForeignKey("ccl_event")
    cluster_event = models.ForeignKey("cluster_event")
    passive = models.BooleanField()
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'ccl_event_log'

class ccl_user_con(models.Model):
    idx = models.AutoField(db_column="ccl_user_con_idx", primary_key=True)
    ccl_event = models.ForeignKey("ccl_event")
    user = models.ForeignKey("user")
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'ccl_user_con'

class cluster_event(models.Model):
    idx = models.AutoField(db_column="cluster_event_idx", primary_key=True)
    name = models.CharField(unique=True, max_length=96)
    description = models.CharField(max_length=384, blank=True)
    color = models.CharField(max_length=18, blank=True)
    command = models.CharField(max_length=192, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'cluster_event'

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
        return "%d" % (self.value or 0)
    class Meta:
        db_table = u'config_int'

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

# no longer needed, AL 20120706
##class c.onfig_type(models.Model):
##    # deprecated, do not use
##    idx = models.AutoField(db_column="config_type_idx", primary_key=True)
##    name = models.CharField(unique=True, max_length=192)
##    identifier = models.CharField(unique=True, max_length=6)
##    description = models.CharField(max_length=384, blank=True)
##    date = models.DateTimeField(auto_now_add=True)
##    class Meta:
##        db_table = u'config_type'

class device(models.Model):
    idx = models.AutoField(db_column="device_idx", primary_key=True)
    name = models.CharField(unique=True, max_length=192)
    # FIXME
    device_group = models.ForeignKey("device_group", related_name="device_group")
    device_type = models.ForeignKey("device_type")
    # removed, ancient NDS stuff
    #axnumber = models.CharField(max_length=192, blank=True)
    alias = models.CharField(max_length=384, blank=True)
    comment = models.CharField(max_length=384, blank=True)
    # better suited in a n:m model, removed
    #switch = models.ForeignKey("device", null=True, related_name="switch_device")
    #switchport = models.IntegerField(null=True, blank=True)
    mon_device_templ = models.ForeignKey("mon_device_templ", null=True)
    mon_ext_host = models.ForeignKey("mon_ext_host", null=True, blank=True)
    device_location = models.ForeignKey("device_location", null=True)
    device_class = models.ForeignKey("device_class")
    rrd_class = models.ForeignKey("rrd_class", null=True)
    save_rrd_vectors = models.BooleanField()
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
##    dom0_memory = models.IntegerField(null=True, blank=True)
##    xen_guest = models.BooleanField()
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
    rsync = models.BooleanField()
    rsync_compressed = models.BooleanField()
    prod_link = models.ForeignKey("network", db_column="prod_link", null=True)
    # states (with timestamp)
    recvstate = models.TextField(blank=True, default="not set")
    recvstate_timestamp = models.DateTimeField(null=True)
    reqstate = models.TextField(blank=True, default="not set")
    reqstate_timestamp = models.DateTimeField(null=True)
    bootnetdevice = models.ForeignKey("netdevice", null=True, related_name="boot_net_device")
    bootserver = models.ForeignKey("device", null=True, related_name="boot_server")
    reachable_via_bootserver = models.BooleanField(default=False)
    dhcp_mac = models.NullBooleanField(null=True, blank=True)
    dhcp_write   = models.NullBooleanField(default=False)
    dhcp_written = models.NullBooleanField(default=False)
    dhcp_error = models.CharField(max_length=765, blank=True)
    propagation_level = models.IntegerField(default=0, blank=True)
    last_install = models.CharField(max_length=192, blank=True)
    last_boot = models.CharField(max_length=192, blank=True)
    last_kernel = models.CharField(max_length=192, blank=True)
    root_passwd = models.CharField(max_length=192, blank=True)
    # remove, no longer needed
    #device_mode = models.BooleanField()
    # link to monitor_server (or null for master)
    monitor_server = models.ForeignKey("device", null=True)
    monitor_checks = models.BooleanField(default=True, db_column="nagios_checks")
    # performance data tracking
    enable_perfdata = models.BooleanField(default=False)
    show_in_bootcontrol = models.BooleanField()
    # not so clever here, better in extra table, FIXME
    #cpu_info = models.TextField(blank=True, null=True)
    # machine uuid
    uuid = models.TextField(default="", max_length=64)
    # cluster url
    curl = models.CharField(default="ssh://", max_length=512)
    date = models.DateTimeField(auto_now_add=True)
    # slaves
    master_connections = models.ManyToManyField("self", through="cd_connection", symmetrical=False, related_name="slave_connections")
    # automap root for nagvis
    automap_root_nagvis = models.BooleanField(default=False)
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
            dhcp_write="1" if self.dhcp_write else "0",
            partition_table_id="%d" % (self.partition_table_id if self.partition_table_id else 0),
            act_partition_table_id="%d" % (self.act_partition_table_id if self.act_partition_table_id else 0),
            mon_device_templ="%d" % (self.mon_device_templ_id or 0),
            monitor_checks="1" if self.monitor_checks else "0",
            mon_ext_host="%d" % (self.mon_ext_host_id or 0),
            curl=unicode(self.curl),
            enable_perfdata="1" if self.enable_perfdata else "0",
            automap_root_nagvis="1" if self.automap_root_nagvis else "0",
        )
        if kwargs.get("with_monitoring", False):
            r_xml.attrib.update(
                {
                    "devs_mon_host_cluster" : "::".join(["%d" % (cur_mhc.pk) for cur_mhc in self.devs_mon_host_cluster.all()]),
                    "devs_mon_service_cluster" : "::".join(["%d" % (cur_mhc.pk) for cur_mhc in self.devs_mon_service_cluster.all()]),
                }
            )
        if kwargs.get("add_title", False):
            r_xml.attrib["title"] = "%s (%s%s)" % (
                self.name,
                self.device_type.identifier,
                ", %s" % (self.comment) if self.comment else "")
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
                now, recv_ts, req_ts = (
                    cluster_timezone.localize(datetime.datetime.now()).astimezone(pytz.UTC),
                    self.recvstate_timestamp,
                    self.reqstate_timestamp)
                # determine if the node is down / pingable / responding to hoststatus requests
                if not int(mother_xml.get("ok", "0")):
                    # not pingable, down
                    r_xml.attrib["net_state"] = "down"
                    r_xml.attrib["network"]   = "unknown"
                else:
                    r_xml.attrib["network"] = mother_xml.attrib["network"]
                    if recv_ts is not None:
                        recv_timeout = (now - recv_ts).seconds
                    else:
                        recv_timeout = 3600
                    if req_ts is not None:
                        req_timeout = (now - req_ts ).seconds
                    else:
                        req_timeout = 3600
                    if min(req_timeout, recv_timeout) > 20:
                        # too long ago, deem as outdated (not reachable by mother)
                        r_xml.attrib["net_state"] = "ping"
                    else:
                        r_xml.attrib["net_state"] = "up"
        if kwargs.get("with_variables", False):
            r_xml.append(
                E.device_variables(
                    *[cur_dv.get_xml() for cur_dv in self.device_variable_set.all()]
                )
            )
        return r_xml
    def __unicode__(self):
        return u"%s%s" % (self.name,
                          " (%s)" % (self.comment) if self.comment else "")
    class Meta:
        db_table = u'device'
        ordering = ("name",)

@receiver(signals.pre_save, sender=device)
def device_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        _check_empty_string(cur_inst, "name")
        if not cur_inst.uuid:
            cur_inst.uuid = str(uuid.uuid4())

class device_class(models.Model):
    idx = models.AutoField(db_column="device_class_idx", primary_key=True)
    classname = models.CharField(max_length=192, blank=False, unique=True)
    priority = models.IntegerField(null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    def get_xml(self):
        return E.device_class(
            unicode(self),
            pk="%d" % (self.pk),
            key="dc__%d" % (self.pk),
            classname=unicode(self.classname),
            priority="%d" % (self.priority)
        )
    def __unicode__(self):
        return u"%s (%d)" % (self.classname, self.priority)
    class Meta:
        db_table = u'device_class'

@receiver(signals.pre_save, sender=device_class)
def device_class_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        _check_integer(cur_inst, "priority")
        
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
            connection_info=self.connection_info
            )
    def __unicode__(self):
        return "%d (%s) %d" % (
            self.parent_id,
            self.connection_info,
            self.child_id)

@receiver(signals.pre_save, sender=cd_connection)
def cd_connection_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        try:
            cd_connection.objects.get(Q(parent=cur_inst.parent_id) & Q(child=cur_inst.child_id))
        except cd_connection.DoesNotExist:
            pass
        except cd_connection.MultipleObjectsReturned:
            raise ValidationError("connections already exist")
        else:
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
    #device = models.ForeignKey("device", null=True, blank=True, related_name="group_device")
    # must be an IntegerField, otherwise we have a cycle reference
    #device = models.IntegerField(null=True, blank=True)
    device = models.ForeignKey("device", db_column="device", null=True, blank=True, related_name="group_device")
    # flag
    cluster_device_group = models.BooleanField()
    date = models.DateTimeField(auto_now_add=True)
    def _add_meta_device(self):
        new_md = device(name=self.get_metadevice_name(),
                        device_group=self,
                        device_class=device_class.objects.get(Q(pk=1)),
                        device_type=device_type.objects.get(Q(identifier="MD")))
        new_md.save()
        self.device = new_md
        self.save()
        return new_md
    def get_metadevice_name(self):
        return "METADEV_%s" % (self.name)
    def get_xml(self, full=True, with_devices=True, with_variables=False, add_title=False, with_monitoring=False):
        cur_xml = E.device_group(
            unicode(self),
            pk="%d" % (self.pk),
            key="devg__%d" % (self.pk),
            name=self.name,
            description=self.description or "",
            is_cdg="1" if self.cluster_device_group else "0"
        )
        if with_devices:
            sub_list = self.device_group.all()
            cur_xml.append(
                E.devices(*[cur_dev.get_xml(
                    full=full,
                    with_variables=with_variables,
                    add_title=add_title,
                    with_monitoring=with_monitoring) for cur_dev in sub_list])
            )
        return cur_xml
    class Meta:
        db_table = u'device_group'
        ordering = ("-cluster_device_group", "name", )
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
        fields = ("idx", "name", "description")

@receiver(signals.pre_save, sender=device_group)
def device_group_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        if not cur_inst.name:
            raise ValidationError("name can not be zero")

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

class device_relationship(models.Model):
    idx = models.AutoField(db_column="device_relationship_idx", primary_key=True)
    host_device = models.ForeignKey("device", related_name="host_device")
    domain_device = models.ForeignKey("device", related_name="domain_device")
    relationship = models.CharField(max_length=9, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'device_relationship'

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

##class distribution(models.Model):
##    idx = models.AutoField(db_column="distribution_idx", primary_key=True)
##    distribution = models.TextField()
##    date = models.DateTimeField(auto_now_add=True)
##    class Meta:
##        db_table = u'distribution'

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

class extended_log(models.Model):
    idx = models.AutoField(db_column="extended_log_idx", primary_key=True)
    devicelog = models.ForeignKey("devicelog", null=True)
    log_source = models.ForeignKey("log_source", null=True)
    user = models.ForeignKey("user", null=True)
    users = models.CharField(max_length=765, blank=True)
    subject = models.CharField(max_length=765, blank=True)
    description = models.TextField(blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'extended_log'

class genstuff(models.Model):
    idx = models.AutoField(db_column="genstuff_idx", primary_key=True)
    name = models.CharField(unique=True, max_length=192)
    description = models.CharField(max_length=384, blank=True)
    value = models.CharField(max_length=192, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'genstuff'

class hopcount(models.Model):
    idx = models.AutoField(db_column="hopcount_idx", primary_key=True)
    s_netdevice = models.ForeignKey("netdevice", related_name="hopcount_s_netdevice")
    d_netdevice = models.ForeignKey("netdevice", related_name="hopcount_d_netdevice")
    value = models.IntegerField(null=True, blank=True)
    # device trace
    trace = models.CharField(max_length=765, blank=True)
    # number of trace entries
    trace_length = models.IntegerField(default=0)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'hopcount'
    def __unicode__(self):
        return "%d -- %d (%d, %s)" % (
            self.s_netdevice_id,
            self.d_netdevice_id,
            self.value,
            self.trace,
        )

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
    #device = models.ForeignKey("device", null=True)
    device = models.IntegerField(null=True)
    build_lock = models.BooleanField(default=False)
    # size in mbyte
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
        cur_img = E.image(
            unicode(self),
            pk="%d" % (self.pk),
            key="image__%d" % (self.pk),
            name="%s" % (self.name),
        )
        return cur_img
    def __unicode__(self):
        return "%s (arch %s)" % (self.name,
                                 unicode(self.architecture))
    class Meta:
        db_table = u'image'
        ordering = ("name", )

class image_excl(models.Model):
    idx = models.AutoField(db_column="image_excl_idx", primary_key=True)
    image = models.ForeignKey("image")
    exclude_path = models.TextField()
    valid_for_install = models.BooleanField()
    valid_for_upgrade = models.BooleanField()
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'image_excl'

# package related models
class package_repo(models.Model):
    idx = models.AutoField(primary_key=True)
    name = models.CharField(max_length=128, default="", unique=True)
    alias = models.CharField(max_length=128, default="")
    repo_type = models.CharField(max_length=128, default="")
    enabled = models.BooleanField(default=True)
    autorefresh = models.BooleanField(default=True)
    gpg_check = models.BooleanField(default=True)
    url = models.CharField(max_length=384, default="")
    created = models.DateTimeField(auto_now_add=True)
    def get_xml(self):
        return E.package_repo(
            unicode(self),
            pk="%d" % (self.pk),
            key="pr__%d" % (self.pk),
            name=self.name,
            alias=self.alias,
            repo_type=self.repo_type,
            enabled="1" if self.enabled else "0",
            autorefresh="1" if self.autorefresh else "0",
            gpg_check="1" if self.gpg_check else "0",
            url=self.url)
    def __unicode__(self):
        return self.name
    class Meta:
        ordering = ("name", )
        
class package_search(models.Model):
    idx = models.AutoField(primary_key=True)
    search_string = models.CharField(max_length=128, default="")
    # search string for latest search result
    last_search_string = models.CharField(max_length=128, default="")
    user = models.ForeignKey("user")
    num_searches = models.IntegerField(default=0)
    # state diagramm ini (new) -> run -> done -> wait (search again pressed) -> run -> done -> ...
    current_state = models.CharField(max_length=6, choices=(
        ("ini" , "initialised"),
        ("wait", "waiting"),
        ("run" , "search running"),
        ("done", "search done")), default="ini")
    deleted = models.BooleanField()
    # number of results for the last search
    results = models.IntegerField(default=0)
    last_search = models.DateTimeField(null=True)
    created = models.DateTimeField(auto_now_add=True)
    def get_xml(self):
        return E.package_search(
            unicode(self),
            pk="%d" % (self.pk),
            key="ps__%d" % (self.pk),
            search_string=self.search_string,
            current_state=self.current_state,
            num_searches="%d" % (self.num_searches),
            last_search_string="%s" % (self.last_search_string),
            last_search=unicode(to_system_tz(self.last_search)) if self.last_search else "never",
            results="%d" % (self.results))
    def __unicode__(self):
        return self.search_string

@receiver(signals.pre_save, sender=package_search)
def package_search_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        _check_empty_string(cur_inst, "search_string")
        if not cur_inst.deleted:
            num_ss = package_search.objects.exclude(Q(pk=cur_inst.pk)).filter(Q(search_string=cur_inst.search_string) & Q(deleted=False)).count()
            if num_ss:
                raise ValidationError("search_string already used")

class package_search_result(models.Model):
    idx = models.AutoField(primary_key=True)
    package_search = models.ForeignKey(package_search)
    name = models.CharField(max_length=128, default="")
    kind = models.CharField(max_length=16, default="package", choices=(
        ("package", "Package"),
        ("patch"  , "Patch"),
    ))
    arch = models.CharField(max_length=32, default="")
    # version w. release
    version = models.CharField(max_length=128, default="")
    copied = models.BooleanField(default=False)
    package_repo = models.ForeignKey(package_repo, null=True)
    created = models.DateTimeField(auto_now_add=True)
    def create_package(self):
        new_p = package(
            name=self.name,
            version=self.version,
            kind=self.kind,
            arch=self.arch,
            package_repo=self.package_repo)
        try:
            new_p.save()
        except:
            raise
        else:
            self.copied = True;
            self.save();
        return new_p
    def get_xml(self):
        return E.package_search_result(
            unicode(self),
            pk="%d" % (self.pk),
            key="psr__%d" % (self.pk),
            name=self.name,
            kind=self.kind,
            arch=self.arch,
            version=self.version,
            copied="1" if self.copied else "0",
            package_repo="%d" % (self.package_repo_id or 0)
        )
    class Meta:
        ordering = ("name", "arch", "version",)
        
class package(models.Model):
    idx = models.AutoField(db_column="package_idx", primary_key=True)
    name = models.CharField(max_length=128)
    version = models.CharField(max_length=128)
    kind = models.CharField(max_length=16, default="package", choices=(
        ("package", "Package"),
        ("patch"  , "Patch"),
    ))
    arch = models.CharField(max_length=32, default="")
    # hard to determine ...
    size = models.IntegerField(default=0)
    package_repo = models.ForeignKey(package_repo, null=True)
##    pgroup = models.TextField()
##    summary = models.TextField()
##    distribution = models.ForeignKey("distribution")
##    vendor = models.ForeignKey("vendor")
##    buildtime = models.IntegerField(null=True, blank=True)
##    buildhost = models.CharField(max_length=765, blank=True)
##    packager = models.CharField(max_length=765, blank=True)
##    date = models.DateTimeField(auto_now_add=True)
    created = models.DateTimeField(auto_now_add=True)
    def get_xml(self):
        return E.package(
            unicode(self),
            pk="%d" % (self.pk),
            key="pack__%d" % (self.pk),
            name=self.name,
            version=self.version,
            kind=self.kind,
            arch=self.arch,
            size="%d" % (self.size),
            package_repo="%d" % (self.package_repo_id)
        )
    def __unicode__(self):
        return "%s-%s" % (self.name, self.version)
    class Meta:
        db_table = u'package'
        unique_together = (("name", "version", "arch", "kind",),)

class package_device_connection(models.Model):
    idx = models.AutoField(primary_key=True)
    device = models.ForeignKey(device)
    package = models.ForeignKey(package)
    # target state
    target_state = models.CharField(max_length=8, choices=(
        ("keep"   , "keep"),
        ("install", "install"),
        ("upgrade", "upgrade"),
        ("erase"  , "erase")), default="keep")
    installed = models.CharField(max_length=8, choices=(
        ("u", "unknown"),
        ("y", "yes"),
        ("n", "no")), default="u")
    force_flag = models.BooleanField(default=False)
    nodeps_flag = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    response_type = models.CharField(max_length=16, choices=(
        ("zypper_xml", "zypper_xml"),
        ("unknown"   , "unknown"),
        ), default="zypper_xml")
    response_str = models.TextField(max_length=65535, default="")
    def get_xml(self, with_package=False):
        pdc_xml = E.package_device_connection(
            pk="%d" % (self.pk),
            key="pdc__%d" % (self.pk),
            device="%d" % (self.device_id),
            package="%d" % (self.package_id),
            target_state="%s" % (self.target_state),
            installed="%s" % (self.installed),
            force_flag="1" if self.force_flag else "0",
            nodeps_flag="1" if self.nodeps_flag else "0",
        )
        if with_package:
            pdc_xml.append(self.package.get_xml())
        return pdc_xml
    def interpret_response(self):
        if self.response_type == "zypper_xml":
            xml = etree.fromstring(self.response_str)
            if xml[0].tag == "info":
                # short when target_state ="keep"
                self.installed = "u"
            else:
                # full stream
                install_summary = xml.xpath(".//install-summary")[0]
                if not len(install_summary):
                    # nohting to do, set according to target state
                    self.installed = {"keep"    : "u",
                                      "install" : "y",
                                      "upgrade" : "y",
                                      "erase"   : "n"}[self.target_state]
                else:
                    if len(install_summary.xpath(".//to-install")):
                        self.installed = "y"
                    elif len(install_summary.xpath(".//to-remove")):
                        self.installed = "n"
                    else:
                        self.installed = "u"
        else:
            self.installed = "u"
    class Meta:
        pass

##class inst_package(models.Model):
##    idx = models.AutoField(db_column="inst_package_idx", primary_key=True)
##    package = models.ForeignKey("package")
##    location = models.TextField()
##    native = models.BooleanField()
##    last_build = models.IntegerField(null=True, blank=True)
##    present_on_disk = models.BooleanField()
##    #package_set = models.ForeignKey("package_set", null=True)
##    date = models.DateTimeField(auto_now_add=True)
##    class Meta:
##        db_table = u'inst_package'

##class instp_device(models.Model):
##    idx = models.AutoField(db_column="instp_device_idx", primary_key=True)
##    inst_package = models.ForeignKey("inst_package")
##    device = models.ForeignKey("device")
##    install = models.BooleanField()
##    upgrade = models.BooleanField()
##    del_field = models.BooleanField(db_column='del') # Field renamed because it was a Python reserved word. Field name made lowercase.
##    nodeps = models.BooleanField()
##    forceflag = models.BooleanField()
##    status = models.TextField()
##    install_time = models.DateTimeField(null=True, blank=True)
##    error_line_num = models.IntegerField(null=True, blank=True)
##    error_lines = models.TextField()
##    date = models.DateTimeField(auto_now_add=True)
##    class Meta:
##        db_table = u'instp_device'

class kernel(models.Model):
    idx = models.AutoField(db_column="kernel_idx", primary_key=True)
    name = models.CharField(max_length=384)
    kernel_version = models.CharField(max_length=384)
    major = models.CharField(max_length=192, blank=True)
    minor = models.CharField(max_length=192, blank=True)
    patchlevel = models.CharField(max_length=192, blank=True)
    version = models.IntegerField(null=True, blank=True)
    release = models.IntegerField(null=True, blank=True)
    builds = models.IntegerField(null=True, blank=True)
    build_machine = models.CharField(max_length=192, blank=True)
    # not a foreignkey to break cyclic dependencies
    #master_server = models.ForeignKey("device", null=True, related_name="master_server")
    master_server = models.IntegerField(null=True)
    master_role = models.CharField(max_length=192, blank=True)
    # not a foreignkey to break cyclic dependencies
    #device = models.ForeignKey("device", null=True)
    device = models.IntegerField(null=True)
    build_lock = models.BooleanField()
    config_name = models.CharField(max_length=192, blank=True)
    cpu_arch = models.CharField(max_length=192, blank=True)
    sub_cpu_arch = models.CharField(max_length=192, blank=True)
    target_dir = models.CharField(max_length=765, blank=True)
    comment = models.TextField(blank=True)
    enabled = models.BooleanField()
    initrd_version = models.IntegerField(null=True, blank=True)
    initrd_built = models.DateTimeField(null=True, blank=True)
    module_list = models.TextField(blank=True)
    target_module_list = models.TextField(blank=True)
    xen_host_kernel = models.BooleanField()
    xen_guest_kernel = models.BooleanField()
    bitcount = models.IntegerField(null=True, blank=True)
    stage1_lo_present = models.BooleanField()
    stage1_cpio_present = models.BooleanField()
    stage1_cramfs_present = models.BooleanField()
    stage2_present = models.BooleanField()
    date = models.DateTimeField(auto_now_add=True)
    def get_xml(self):
        return E.kernel(
            pk="%d" % (self.pk),
            key="kernel__%d" % (self.pk),
            name=self.name
        )
    def __unicode__(self):
        return self.name
    class Meta:
        db_table = u'kernel'

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
    warn_threshold = models.IntegerField(null=True, blank=True, default=0)
    crit_threshold = models.IntegerField(null=True, blank=True, default=0)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'lvm_lv'

class lvm_vg(models.Model):
    idx = models.AutoField(db_column="lvm_vg_idx", primary_key=True)
    partition_table = models.ForeignKey("partition_table")
    name = models.CharField(max_length=192)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'lvm_vg'

class mac_ignore(models.Model):
    idx = models.AutoField(db_column="mac_ignore_idx", primary_key=True)
    macaddr = models.CharField(max_length=192, db_column="macadr", default="")
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'mac_ignore'

class macbootlog(models.Model):
    idx = models.AutoField(db_column="macbootlog_idx", primary_key=True)
    device = models.ForeignKey("device", null=True)
    entry_type = models.CharField(max_length=96, db_column="type")
    ip_action = models.CharField(max_length=96, default="", db_column="ip")
    macaddr = models.CharField(max_length=192, db_column="macadr")
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

##class netbotz_picture(models.Model):
##    idx = models.AutoField(db_column="netbotz_picture_idx", primary_key=True)
##    device = models.ForeignKey("device")
##    year = models.IntegerField()
##    month = models.IntegerField()
##    day = models.IntegerField()
##    hour = models.IntegerField()
##    minute = models.IntegerField()
##    second = models.IntegerField()
##    path = models.CharField(max_length=765, blank=True)
##    date = models.DateTimeField(auto_now_add=True)
##    class Meta:
##        db_table = u'netbotz_picture'

class netdevice(models.Model):
    idx = models.AutoField(db_column="netdevice_idx", primary_key=True)
    device = models.ForeignKey("device")
    devname = models.CharField(max_length=36)
    macaddr = models.CharField(db_column="macadr", max_length=177, blank=True)
    driver_options = models.CharField(max_length=672, blank=True)
    speed = models.IntegerField(default=0, null=True, blank=True)
    netdevice_speed = models.ForeignKey("netdevice_speed")
    driver = models.CharField(max_length=384, blank=True)
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
    date = models.DateTimeField(auto_now_add=True)
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
            vlan_id=self.vlan_id)
    def find_matching_network_device_type(self):
        # remove digits
        name = self.devname.split(":")[0].strip("0123456789")
        ndt_list = network_device_type.objects.filter(Q(identifier__startswith=name))
        if len(ndt_list) == 0:
            return None
        elif len(ndt_list) == 1:
            return ndt_list[0]
        else:
            # FIXME, enhance to full match
            return ndt_list[0]
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
            E.peers(*[cur_peer.get_xml() for cur_peer in peer_information.objects.filter(Q(s_netdevice=self) | Q(d_netdevice=self)).distinct().select_related("s_netdevice", "s_netdevice__device", "d_netdevice", "d_netdevice__device")]),
            devname=self.devname,
            description=self.description or "",
            driver=self.driver or "",
            driver_options=self.driver_options or "",
            pk="%d" % (self.pk),
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
            key="nd__%d" % (self.pk),
            netdevice_speed="%d" % (self.netdevice_speed_id),
            network_device_type="%d" % (self.network_device_type_id),
            nd_type="%d" % (self.network_device_type_id))

@receiver(signals.pre_delete, sender=netdevice)
def netdevice_pre_delete(sender, **kwargs):
    # too late here, handled by delete_netdevice in network_views
    pass
    #if "instance" in kwargs:
        #cur_inst = kwargs["instance"]
        #for cur_dev in device.objects.filter(Q(bootnetdevice=cur_inst.pk)):
            #cur_dev.bootnetdevice = None
            #cur_dev.save(update_fields=["bootnetdevice"])
       
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
    def __unicode__(self):
        s_str, lut_idx = ("", 0)
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
    date = models.DateTimeField(auto_now_add=True)
    def copy(self):
        return net_ip(
            ip=self.ip,
            network=self.network,
            penalty=self.penalty,
            alias=self.alias,
            alias_excl=self.alias_excl)
    def get_hex_ip(self):
        return "".join(["%02X" % (int(part)) for part in self.ip.split(".")])
    def get_xml(self):
        return E.net_ip(
            unicode(self),
            pk="%d" % (self.pk),
            ip=self.ip,
            key="ni_%d" % (self.pk),
            network="%d" % (self.network_id),
            netdevice="%d" % (self.netdevice_id),
            penalty="%d" % (self.penalty or 1),
            alias=self.alias or "",
            alias_excl="1" if self.alias_excl else "0"
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
        if not ipv_addr.network_matches(cur_inst.network):
            match_list = ipv_addr.find_matching_network(network.objects.all())
            if match_list:
                cur_inst.network = match_list[0][1]
            else:
                raise ValidationError("no maching network found")
        all_ips = net_ip.objects.exclude(Q(pk=cur_inst.pk)).filter(Q(netdevice__device=cur_inst.netdevice.device)).values_list("ip", flat=True)
        if cur_inst.ip in all_ips:
            raise ValidationError("Adress already used")
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
    short_names = models.BooleanField()
    name = models.CharField(max_length=192, blank=False)
    penalty = models.PositiveIntegerField(default=1)
    postfix = models.CharField(max_length=12, blank=True)
    info = models.CharField(max_length=255, blank=True)
    network = models.IPAddressField()
    netmask = models.IPAddressField()
    broadcast = models.IPAddressField()
    gateway = models.IPAddressField()
    gw_pri = models.IntegerField(null=True, blank=True, default=1)
    write_bind_config = models.BooleanField()
    write_other_network_config = models.BooleanField()
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
            name=self.name,
            postfix=self.postfix or "",
            network=self.network,
            netmask=self.netmask,
            broadcast=self.broadcast,
            gateway=self.gateway,
            short_names="1" if self.short_names else "0",
            write_bind_config="1" if self.write_bind_config else "0",
            write_other_network_config="1" if self.write_other_network_config else "0",
            network_device_type="::".join(["%d" % (cur_pk) for cur_pk in self.network_device_type.all().values_list("pk", flat=True)]),
        )
        if add_ip_info:
            r_xml.attrib["ip_count"] = "%d" % (len(self.net_ip_set.all()))
        return r_xml
    class Meta:
        db_table = u'network'
    def get_full_postfix(self):
        return "%s.%s" % (self.postfix, self.name)
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
        return u"%s (%s, %s)" % (
            self.name,
            self.network,
            self.network_type.identifier
        )

@receiver(signals.pre_save, sender=network)
def network_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        # what was the changed attribute
        change_attr = getattr(cur_inst, "change_attribute", None)
        _check_integer(cur_inst, "penalty", min_val=-100, max_val=100)
        nw_type = cur_inst.network_type.identifier
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
            ip_dict["broadcast"] = ~ ip_dict["netmask"] | (ip_dict["network"] & ip_dict["netmask"])
        elif change_attr == "broadcast":
            ip_dict["netmask"] = ~ (ip_dict["broadcast"] & ~ ip_dict["network"])
        elif change_attr == "gateway":
            # do nothing
            pass
        ip_dict["network"] = ip_dict["network"] & ip_dict["netmask"]
        # always correct gateway
        ip_dict["gateway"] = (ip_dict["gateway"] & ~ ip_dict["netmask"]) | ip_dict["network"]
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
    
class network_network_device_type(models.Model):
    idx = models.AutoField(db_column="network_network_device_type_idx", primary_key=True)
    network = models.ForeignKey("network")
    network_device_type = models.ForeignKey("network_device_type")
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'network_network_device_type'

class network_type(models.Model):
    idx = models.AutoField(db_column="network_type_idx", primary_key=True)
    identifier = models.CharField(unique=True, max_length=3,
                                  choices=(("b", "boot"),
                                           ("p", "prod"),
                                           ("s", "slave"),
                                           ("o", "other"),
                                           ("l", "local")))
    description = models.CharField(max_length=192)
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

@receiver(signals.pre_save, sender=network_type)
def network_type_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        if not(cur_inst.identifier.strip()):
            raise ValidationError("identifer must not be empty")

class config(models.Model):
    idx = models.AutoField(db_column="new_config_idx", primary_key=True)
    name = models.CharField(unique=True, max_length=192, blank=False)
    description = models.CharField(max_length=765)
    priority = models.IntegerField(null=True, default=0)
    config_type = models.ForeignKey("config_type", db_column="new_config_type_id")
    parent_config = models.ForeignKey("config", null=True)
    date = models.DateTimeField(auto_now_add=True)
    def get_xml(self, full=True):
        r_xml = E.config(
            pk="%d" % (self.pk),
            key="conf__%d" % (self.pk),
            name=unicode(self.name),
            description=unicode(self.description or ""),
            priority="%d" % (self.priority or 0),
            config_type="%d" % (self.config_type_id),
            parent_config="%d" % (self.parent_config_id or 0),
        )
        if full:
            r_xml.extend([
                E.config_vars(*[cur_var.get_xml() for cur_var in list(self.config_str_set.all()) + \
                                list(self.config_int_set.all()) + list(self.config_bool_set.all()) + list(self.config_blob_set.all())]),
                E.mon_check_commands(*[cur_ngc.get_xml() for cur_ngc in list(self.mon_check_command_set.all())]),
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
        _check_integer(cur_inst, "priority")

@receiver(signals.post_save, sender=config)
def config_post_save(sender, **kwargs):
    if not kwargs["raw"] and "instance" in kwargs:
        cur_inst = kwargs["instance"]
        if kwargs["created"]:
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
            for cur_var in add_list:
                cur_var.config = cur_inst
                cur_var.save()
        if cur_inst.parent_config_id == cur_inst.pk and cur_inst.pk:
            raise ValidationError("cannot be my own parent")
                

class config_type(models.Model):
    idx = models.AutoField(db_column="new_config_type_idx", primary_key=True)
    name = models.CharField(unique=True, max_length=192)
    description = models.CharField(max_length=765, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    def get_xml(self):
        return E.config_type(
            unicode(self),
            pk="%d" % (self.pk),
            key="ctype__%d" % (self.pk),
            name=unicode(self.name),
            description=unicode(self.description or "")
        )
    def __unicode__(self):
        return self.name
    class Meta:
        db_table = u'new_config_type'

class new_rrd_data(models.Model):
    idx = models.AutoField(db_column="new_rrd_data_idx", primary_key=True)
    device = models.ForeignKey("device", null=True, blank=True)
    descr = models.CharField(max_length=765, blank=True)
    descr1 = models.CharField(max_length=192, blank=True)
    descr2 = models.CharField(max_length=192, blank=True)
    descr3 = models.CharField(max_length=192, blank=True)
    descr4 = models.CharField(max_length=192, blank=True)
    unit = models.CharField(max_length=96, blank=True)
    info = models.CharField(max_length=255, blank=True)
    from_snmp = models.IntegerField(null=True, blank=True)
    base = models.IntegerField(null=True, blank=True)
    factor = models.FloatField(null=True, blank=True)
    var_type = models.CharField(max_length=3, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'new_rrd_data'

class mon_host_cluster(models.Model):
    idx = models.AutoField(primary_key=True)
    name = models.CharField(max_length=32, blank=False, null=False, unique=True)
    description = models.CharField(max_length=64, default="")
    main_device = models.ForeignKey("device", related_name="main_mon_host_cluster")
    mon_service_templ = models.ForeignKey("mon_service_templ")
    devices = models.ManyToManyField(device, related_name="devs_mon_host_cluster")
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
            devices="::".join(["%d" %  (cur_pk) for cur_pk in self.devices.all().values_list("pk", flat=True)]),
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
    name = models.CharField(max_length=32, blank=False, null=False, unique=True)
    description = models.CharField(max_length=64, default="")
    main_device = models.ForeignKey("device", related_name="main_mon_service_cluster")
    mon_service_templ = models.ForeignKey("mon_service_templ")
    devices = models.ManyToManyField(device, related_name="devs_mon_service_cluster")
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
            devices="::".join(["%d" %  (cur_pk) for cur_pk in self.devices.all().values_list("pk", flat=True)]),
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

class mon_check_command(models.Model):
    idx = models.AutoField(db_column="ng_check_command_idx", primary_key=True)
    config_old = models.IntegerField(null=True, blank=True, db_column="config")
    config = models.ForeignKey("config", db_column="new_config_id")
    mon_check_command_type = models.ForeignKey("mon_check_command_type")
    mon_service_templ = models.ForeignKey("mon_service_templ")
    # only unique per config
    name = models.CharField(max_length=192)#, unique=True)
    command_line = models.CharField(max_length=765)
    description = models.CharField(max_length=192, blank=True)
    device = models.ForeignKey("device", null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    enable_perfdata = models.BooleanField(default=False)
    def get_xml(self):
        return E.mon_check_command(
            self.name,
            pk="%d" % (self.pk),
            key="moncc__%d" % (self.pk),
            config="%d" % (self.config_id),
            mon_check_command_type="%d" % (self.mon_check_command_type_id),
            mon_service_templ="%d" % (self.mon_service_templ_id),
            name=self.name or "",
            command_line=self.command_line or "",
            description=self.description or "",
            enable_perfdata="1" if self.enable_perfdata else "0",
        )
    class Meta:
        db_table = u'ng_check_command'

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
    snrecovery = models.BooleanField()
    sncritical = models.BooleanField()
    snwarning = models.BooleanField()
    snunknown = models.BooleanField()
    hnrecovery = models.BooleanField()
    hndown = models.BooleanField()
    hnunreachable = models.BooleanField()
    sncommand = models.CharField(max_length=192, blank=True, default="notify-by-email")
    hncommand = models.CharField(max_length=192, blank=True, default="host-notify-by-email")
    date = models.DateTimeField(auto_now_add=True)
    def get_xml(self):
        ret_xml = E.mon_contact(
            unicode(self),
            pk="%d" % (self.pk),
            key="moncon__%d" % (self.pk),
            user_id="%d" % (self.user_id or 0),
            snperiod_id="%d" % (self.snperiod_id or 0),
            hnperiod_id="%d" % (self.hnperiod_id or 0),
            sncommand = self.sncommand,
            hncommand = self.hncommand,
        )
        for bf in ["snrecovery", "sncritical", "snunknown",
                   "hnrecovery", "hndown", "hnunreachable"]:
            ret_xml.attrib[bf] = "1" if getattr(self, bf) else "0"
        return ret_xml
    def __unicode__(self):
        return unicode(self.user)
    class Meta:
        db_table = u'ng_contact'

class mon_contactgroup(models.Model):
    idx = models.AutoField(db_column="ng_contactgroup_idx", primary_key=True)
    name = models.CharField(max_length=192, unique=True)
    alias = models.CharField(max_length=255, blank=True, default="")
    date = models.DateTimeField(auto_now_add=True)
    device_groups = models.ManyToManyField("device_group")
    members = models.ManyToManyField("mon_contact")
    service_templates = models.ManyToManyField("mon_service_templ")
    def get_xml(self):
        return E.mon_contactgroup(
            unicode(self),
            members="::".join(["%d" % (cur_pk) for cur_pk in self.members.all().values_list("pk", flat=True)]),
            device_groups="::".join(["%d" % (cur_pk) for cur_pk in self.device_groups.all().values_list("pk", flat=True)]),
            service_templates="::".join(["%d" % (cur_pk) for cur_pk in self.service_templates.all().values_list("pk", flat=True)]),
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
    ccommand = models.CharField(max_length=192, blank=True, default="check-host-alive")
    max_attempts = models.IntegerField(null=True, blank=True, default=1)
    ninterval = models.IntegerField(null=True, blank=True, default=1)
    mon_period = models.ForeignKey("mon_period", null=True, blank=True)
    nrecovery = models.BooleanField()
    ndown = models.BooleanField()
    nunreachable = models.BooleanField()
    is_default = models.BooleanField()
    date = models.DateTimeField(auto_now_add=True)
    def get_xml(self):
        return E.mon_device_templ(
            unicode(self),
            pk="%d" % (self.pk),
            key="mondt__%d" % (self.pk),
            name=self.name,
            mon_service_templ="%d" % (self.mon_service_templ_id or 0),
            max_attempts="%d" % (self.max_attempts or 0),
            ninterval="%d" % (self.ninterval or 0),
            mon_period="%d" % (self.mon_period_id or 0),
            nrecovery="%d" % (1 if self.nrecovery else 0),
            ndown="%d" % (1 if self.ndown else 0),
            nunreachable="%d" % (1 if self.nunreachable else 0),
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
            ("max_attempts", 1, 10),
            ("ninterval"   , 0, 60)]:
            _check_integer(cur_inst, attr_name, min_val=min_val, max_val=max_val)
                    
class mon_ext_host(models.Model):
    idx = models.AutoField(db_column="ng_ext_host_idx", primary_key=True)
    name = models.CharField(unique=True, max_length=192)
    icon_image = models.CharField(max_length=192, blank=True)
    icon_image_alt = models.CharField(max_length=192, blank=True)
    vrml_image = models.CharField(max_length=192, blank=True)
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
        ordering = ("name", )
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
        range_re = re.compile("^[0-9]{1,2}:[0-9]{1,2}-[0-9]{1,2}:[0-9]{1,2}$")
        for day in ["sun", "mon", "tue", "wed", "thu", "fri", "sat"]:
            r_name = "%s_range" % (day)
            cur_val = getattr(cur_inst, r_name)
            if not range_re.match(cur_val):
                raise ValidationError("range for %s not correct" % (day))
            else:
                new_val = []
                for cur_time in cur_val.split("-"):
                    hours, minutes = [int(val) for val in cur_time.split(":")]
                    if (hours, minutes) in [(24, 0)]:
                        pass
                    elif hours < 0 or hours > 23 or minutes < 0 or minutes > 60:
                        raise ValidationError("illegal time %s (%s)" % (cur_time, day))
                    new_val.append("%02d:%02d" % (hours, minutes))
                setattr(cur_inst, r_name, "-".join(new_val))

class mon_service(models.Model):
    idx = models.AutoField(db_column="ng_service_idx", primary_key=True)
    name = models.CharField(max_length=192)
    alias = models.CharField(max_length=192, blank=True)
    command = models.CharField(max_length=192, blank=True)
    parameter1 = models.CharField(max_length=192, blank=True)
    parameter2 = models.CharField(max_length=192, blank=True)
    parameter3 = models.CharField(max_length=192, blank=True)
    parameter4 = models.CharField(max_length=192, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'ng_service'

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
            ("max_attempts", 1, 10),
            ("check_interval", 1, 60),
            ("retry_interval", 1, 60),
            ("ninterval", 0, 60)]:
            cur_val = _check_integer(cur_inst, attr_name, min_val=min_val, max_val=max_val)

##class package_set(models.Model):
##    idx = models.AutoField(db_column="package_set_idx", primary_key=True)
##    name = models.CharField(unique=True, max_length=255)
##    date = models.DateTimeField(auto_now_add=True)
##    class Meta:
##        db_table = u'package_set'

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
    lut_blob = models.TextField(blank=True, null=True)
    warn_threshold = models.IntegerField(null=True, blank=True)
    crit_threshold = models.IntegerField(null=True, blank=True)
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
        if not self.partition_fs:
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
            raise ValidationError("partition number not parseable")
        if p_num < 1 or p_num > 9:
            raise ValidationError("partition number out of bounds [1, 9]")
        all_part_nums = partition.objects.exclude(Q(pk=cur_inst.pk)).filter(Q(partition_disc=cur_inst.partition_disc)).values_list("pnum", flat=True)
        if p_num in all_part_nums:
            raise ValidationError("partition number already used")
        cur_inst.pnum = p_num
        # size
        _check_integer(cur_inst, "size", min_val=0)
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
        ext_parts = [cur_p for cur_p in my_parts if cur_p.partition_fs.name == "ext"]
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
        disc_re = re.compile("^/dev/[shv]d[a-d]$")
        cur_inst = kwargs["instance"]
        d_name = cur_inst.disc.strip().lower()
        if not d_name:
            raise ValidationError("name must not be zero")
        if not disc_re.match(d_name):
            raise ValidationError("illegal name")
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
        ordering = ("name", )

class partition_table(models.Model):
    idx = models.AutoField(db_column="partition_table_idx", primary_key=True)
    name = models.CharField(unique=True, max_length=192)
    description = models.CharField(max_length=255, blank=True, default="")
    enabled = models.BooleanField(default=True)
    valid = models.BooleanField(default=False)
    modify_bootloader = models.IntegerField(default=0)
    date = models.DateTimeField(auto_now_add=True)
    def get_xml(self, **kwargs):
        _validate = kwargs.get("validate", False)
        if _validate:
            prob_list = self._validate()
            new_valid = not any([log_level in [
                logging_tools.LOG_LEVEL_ERROR,
                logging_tools.LOG_LEVEL_CRITICAL] for log_level, what, is_global in prob_list])
            print new_valid
            pprint.pprint(prob_list)
            # validate 
            if new_valid != self.valid:
                self.valid = new_valid
                self.save()
        pt_xml = E.partition_table(
            unicode(self),
            E.partition_discs(
                *[sub_disc.get_xml() for sub_disc in self.partition_disc_set.all()]
                ),
            name=self.name,
            pk="%d" % (self.pk),
            key="ptable__%d" % (self.pk),
            description=unicode(self.description),
            valid="1" if self.valid else "0",
            enabled="1" if self.enabled else "0",
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
            from_devname=self.s_netdevice.devname,
            to_devname=self.d_netdevice.devname,
            from_device=self.s_netdevice.device.name,
            to_device=self.d_netdevice.device.name,
            s_netdevice="%d" % (self.s_netdevice_id),
            d_netdevice="%d" % (self.d_netdevice_id),
            from_penalty="%d" % (self.s_netdevice.penalty),
            to_penalty="%d" % (self.d_netdevice.penalty),
            penalty="%d" % (self.penalty or 1)
        )
    class Meta:
        db_table = u'peer_information'

class pi_connection(models.Model):
    idx = models.AutoField(db_column="pi_connection_idx", primary_key=True)
    package = models.ForeignKey("package")
    image = models.ForeignKey("image")
    install_time = models.IntegerField()
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'pi_connection'

class rrd_class(models.Model):
    idx = models.AutoField(db_column="rrd_class_idx", primary_key=True)
    name = models.CharField(unique=True, max_length=255)
    step = models.IntegerField()
    heartbeat = models.IntegerField()
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'rrd_class'

class rrd_data(models.Model):
    idx = models.AutoField(db_column="rrd_data_idx", primary_key=True)
    rrd_set = models.ForeignKey("rrd_set")
    descr = models.CharField(max_length=765)
    descr1 = models.CharField(max_length=189)
    descr2 = models.CharField(max_length=189, blank=True)
    descr3 = models.CharField(max_length=189, blank=True)
    descr4 = models.CharField(max_length=189, blank=True)
    unit = models.CharField(max_length=96, blank=True)
    info = models.CharField(max_length=255, blank=True)
    from_snmp = models.BooleanField()
    base = models.IntegerField(null=True, blank=True)
    factor = models.FloatField(null=True, blank=True)
    var_type = models.CharField(max_length=3, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'rrd_data'

class rrd_data_store(models.Model):
    idx = models.AutoField(db_column="rrd_data_store_idx", primary_key=True)
    device = models.ForeignKey("device")
    recv_time = models.IntegerField()
    data = models.TextField()
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'rrd_data_store'

class rrd_rra(models.Model):
    idx = models.AutoField(db_column="rrd_rra_idx", primary_key=True)
    rrd_class = models.ForeignKey("rrd_class")
    cf = models.CharField(max_length=192)
    steps = models.IntegerField()
    rows = models.IntegerField()
    xff = models.FloatField(null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'rrd_rra'

class rrd_set(models.Model):
    idx = models.AutoField(db_column="rrd_set_idx", primary_key=True)
    device = models.ForeignKey("device")
    filename = models.CharField(max_length=765, blank=True, null=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'rrd_set'

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
    device = models.ForeignKey("device")
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
        return u"%s (%s)%s" % (self.status,
                             ",".join([short for short, attr_name in [
                                 ("link" , "prod_link"),
                                 ("mem"  , "memory_test"),
                                 ("loc"  , "boot_local"),
                                 ("ins"  , "do_install"),
                                 ("clean", "is_clean")] if getattr(self, attr_name)]),
                             "(*)" if self.allow_boolean_modify else "")
    def get_xml(self, prod_net=None):
        return E.status(
            unicode(self) if prod_net is None else "%s into %s" % (unicode(self), unicode(prod_net)),
            pk="%d" % (self.pk),
            prod_net="%d" % (0 if prod_net is None else prod_net.pk),
            key="status__%d" % (self.pk))
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

class user(models.Model):
    idx = models.AutoField(db_column="user_idx", primary_key=True)
    active = models.BooleanField(default=True)
    login = models.CharField(unique=True, max_length=255)
    uid = models.IntegerField(unique=True)
    group = models.ForeignKey("group")
    aliases = models.TextField(blank=True, null=True)
    export = models.ForeignKey("device_config", null=True, related_name="export")
    export_scr = models.ForeignKey("device_config", null=True, related_name="export_scr")
    home = models.TextField(blank=True, null=True)
    scratch = models.TextField(blank=True, null=True)
    shell = models.CharField(max_length=765, blank=True, default="/bin/bash")
    # SHA encrypted
    password = models.CharField(max_length=48, blank=True)
    password_ssha = models.CharField(max_length=64, blank=True, default="")
    #cluster_contact = models.BooleanField()
    first_name = models.CharField(max_length=765, blank=True)
    last_name = models.CharField(max_length=765, blank=True)
    title = models.CharField(max_length=765, blank=True)
    email = models.CharField(max_length=765, blank=True)
    pager = models.CharField(max_length=765, blank=True)
    tel = models.CharField(max_length=765, blank=True)
    comment = models.CharField(max_length=765, blank=True)
    nt_password = models.CharField(max_length=255, blank=True)
    lm_password = models.CharField(max_length=255, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    allowed_device_groups = models.ManyToManyField(device_group)
    home_dir_created = models.BooleanField(default=False)
    def get_permissions(self):
        return ", ".join([cur_perm.name for cur_perm in Permission.objects.filter(Q(user__username=self.login))]) or "nothing"
    def set_permissions(self, new_perms):
        try:
            dj_user = User.objects.get(Q(username=self.login))
        except User.DoesNotExist:
            pass
        else:
            cur_perms = set([cur_entry.pk for cur_entry in dj_user.user_permissions.all()])
            new_perms = set([entry for entry in new_perms.split("::") if entry.strip()])
            for del_perm in cur_perms - new_perms:
                dj_user.user_permissions.remove(Permission.objects.get(Q(pk=del_perm)))
            for add_perm in new_perms - cur_perms:
                dj_user.user_permissions.add(Permission.objects.get(Q(pk=add_perm)))
    permissions = property(get_permissions, set_permissions)
    def get_xml(self, with_permissions=False, with_allowed_device_groups=True):
        user_xml = E.user(
            unicode(self),
            pk="%d" % (self.pk),
            key="user__%d" % (self.pk),
            login=self.login,
            uid="%d" % (self.uid),
            group="%d" % (self.group_id or 0),
            aliases=self.aliases or "",
            active="1" if self.active else "0",
            export="%d" % (self.export_id or 0),
            home_dir_created="1" if self.home_dir_created else "0",
        )
        if with_allowed_device_groups:
            user_xml.attrib["allowed_device_groups"] = "::".join(["%d" % (cur_pk) for cur_pk in self.allowed_device_groups.all().values_list("pk", flat=True)]),
        if with_permissions:
            user_xml.attrib["permissions"] = "::".join(["%d" % (cur_perm.pk) for cur_perm in Permission.objects.filter(Q(user__username=self.login))])
        else:
            # empty field
            user_xml.attrib["permissions"] = ""
        for attr_name in ["first_name", "last_name",
                          "title", "email", "pager", "tel", "comment"]:
            user_xml.attrib[attr_name] = getattr(self, attr_name)
        return user_xml
    class Meta:
        db_table = u'user'
        ordering = ("login", )
        permissions = {
            ("all_devices", "access all devices"),
            ("test_right", "Test right"),
            #("wf_apc" , "APC control"),
        }
    def __unicode__(self):
        return u"%s (%d; %s, %s)" % (
            self.login,
            self.pk,
            self.first_name or "first",
            self.last_name or "last")

class user_serializer_h(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(format='api', view_name="rest:user_detail_h")
    group = serializers.HyperlinkedRelatedField(view_name="rest:group_detail_h")
    class Meta:
        model = user
        fields = ("url", "login", "uid", "group")

class user_serializer(serializers.ModelSerializer):
    class Meta:
        model = user
        fields = ("idx", "login", "uid", "group")
        
@receiver(signals.pre_save, sender=user)
def user_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        _check_integer(cur_inst, "uid", min_val=100, max_val=65535)
        _check_empty_string(cur_inst, "login")

@receiver(signals.post_save, sender=user)
def user_post_save(sender, **kwargs):
    if not kwargs["raw"] and "instance" in kwargs:
        cur_inst = kwargs["instance"]
        try:
            django_user = User.objects.get(Q(username=cur_inst.login))
        except User.DoesNotExist:
            django_user = User(
                username=cur_inst.login
            )
            django_user.save()
        django_user.is_active = cur_inst.active
        django_user.first_name = cur_inst.first_name
        django_user.last_name = cur_inst.last_name
        django_user.email = cur_inst.email
        pw_gen_1 = "SHA1"
        if cur_inst.password.startswith(pw_gen_1):
            pass
        else:
            passwd = cur_inst.password
            new_sh = hashlib.new(pw_gen_1)
            new_sh.update(passwd)
            cur_pw = "%s:%s" % (pw_gen_1, base64.b64encode(new_sh.digest()))
            django_user.set_password(passwd)
            cur_inst.password = cur_pw
            # ssha1
            salt = os.urandom(4)
            new_sh.update(salt)
            #print base64.b64encode(new_sh.digest() +  salt)
            cur_inst.password_ssha = "%s:%s" % ("SSHA", base64.b64encode(new_sh.digest() +  salt))
            #cur_inst.password_ssha = "%s:%s" % ("SSHA", base64.b64encode(new_sh.digest() + salt))
            cur_inst.save()
        django_user.save()

@receiver(signals.post_delete, sender=user)
def user_post_delete(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        try:
            User.objects.get(Q(username=cur_inst.login)).delete()
        except User.DoesNotExist:
            pass

class group(models.Model):
    idx = models.AutoField(db_column="ggroup_idx", primary_key=True)
    active = models.BooleanField(default=True)
    groupname = models.CharField(db_column="ggroupname", unique=True, max_length=48, blank=False)
    gid = models.IntegerField(unique=True)
    homestart = models.TextField(blank=True)
    scratchstart = models.TextField(blank=True)
    group_comment = models.CharField(max_length=765, blank=True)
    first_name = models.CharField(max_length=765, blank=True)
    last_name = models.CharField(max_length=765, blank=True)
    title = models.CharField(max_length=765, blank=True)
    email = models.CharField(max_length=765, blank=True)
    pager = models.CharField(max_length=765, blank=True)
    tel = models.CharField(max_length=765, blank=True)
    comment = models.CharField(max_length=765, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    # not implemented right now in md-config-server
    allowed_device_groups = models.ManyToManyField(device_group)
    def get_xml(self):
        group_xml = E.group(
            unicode(self),
            pk="%d" % (self.pk),
            key="group__%d" % (self.pk),
            groupname=unicode(self.groupname),
            gid="%d" % (self.gid),
            homestart=self.homestart or "",
            active="1" if self.active else "0",
            allowed_device_groups="::".join(["%d" % (cur_pk) for cur_pk in self.allowed_device_groups.all().values_list("pk", flat=True)]),
        )
        for attr_name in ["first_name", "last_name", "group_comment",
                     "title", "email", "pager", "tel", "comment"]:
            group_xml.attrib[attr_name] = getattr(self, attr_name)
        return group_xml
    class Meta:
        db_table = u'ggroup'
        ordering = ("groupname", )
    def __unicode__(self):
        return "%s (gid=%d)" % (
            self.groupname,
            self.gid)

class group_serializer_h(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(format='api', view_name="rest:group_detail_h")
    class Meta:
        model = group
        fields = ("url", "groupname", "active", "gid")

class group_serializer(serializers.ModelSerializer):
    class Meta:
        model = group
        fields = ("groupname", "active", "gid")

@receiver(signals.pre_save, sender=group)
def group_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        _check_empty_string(cur_inst, "groupname")
        _check_integer(cur_inst, "gid", min_val=100, max_val=65535)

@receiver(signals.post_save, sender=group)
def group_post_save(sender, **kwargs):
    if not kwargs["raw"] and "instance" in kwargs:
        cur_inst = kwargs["instance"]
        try:
            django_group = Group.objects.get(Q(name=cur_inst.groupname))
        except Group.DoesNotExist:
            django_group = Group(name=cur_inst.groupname)
            django_group.save()
        
@receiver(signals.post_delete, sender=group)
def group_post_delete(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        try:
            Group.objects.get(Q(name=cur_inst.groupname)).delete()
        except:
            pass
        
class user_device_login(models.Model):
    idx = models.AutoField(db_column="user_device_login_idx", primary_key=True)
    user = models.ForeignKey("user")
    device = models.ForeignKey("device")
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'user_device_login'

# for secondary groups
class user_group(models.Model):
    idx = models.AutoField(db_column="user_ggroup_idx", primary_key=True)
    group = models.ForeignKey("group")
    user = models.ForeignKey("user")
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'user_ggroup'

class user_var(models.Model):
    idx = models.AutoField(db_column="user_var_idx", primary_key=True)
    user = models.ForeignKey("user")
    name = models.CharField(max_length=189)
    hidden = models.BooleanField()
    var_type = models.CharField(max_length=3, blank=True, db_column="type")
    editable = models.BooleanField()
    value = models.TextField(blank=True)
    description = models.TextField(blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'user_var'

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
    #config = models.CharField(max_length=255, blank=True)
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
            
@receiver(signals.pre_save, sender=peer_information)
def peer_information_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        _check_integer(cur_inst, "penalty", min_val=1)


def config_str_general_check(cur_inst):
    if not cur_inst.name:
        raise ValidationError("name must not be zero")
    
@receiver(signals.pre_save, sender=config_str)
def config_str_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        config_str_general_check(cur_inst)
        all_var_names = list(cur_inst.config.config_str_set.exclude(Q(pk=cur_inst.pk)).values_list("name", flat=True)) + \
            list(cur_inst.config.config_int_set.all().values_list("name", flat=True)) + \
            list(cur_inst.config.config_bool_set.all().values_list("name", flat=True)) + \
            list(cur_inst.config.config_blob_set.all().values_list("name", flat=True))
        if cur_inst.name in all_var_names:
            raise ValidationError("name already used")

@receiver(signals.pre_save, sender=config_int)
def config_int_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        config_str_general_check(cur_inst)
        all_var_names = list(cur_inst.config.config_str_set.all().values_list("name", flat=True)) + \
            list(cur_inst.config.config_int_set.exclude(Q(pk=cur_inst.pk)).values_list("name", flat=True)) + \
            list(cur_inst.config.config_bool_set.all().values_list("name", flat=True)) + \
            list(cur_inst.config.config_blob_set.all().values_list("name", flat=True))
        if cur_inst.name in all_var_names:
            raise ValidationError("name already used")
        _check_integer(cur_inst, "value")

@receiver(signals.pre_save, sender=config_bool)
def config_bool_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        config_str_general_check(cur_inst)
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
                cur_inst.value = True if (cur_inst.value or "").lower() in ["1", "true", "yes"] else False
        except ValueError:
            raise ValidationError("value cannot be interpret as bool")
        

@receiver(signals.pre_save, sender=config_blob)
def config_blob_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        config_str_general_check(cur_inst)
        all_var_names = list(cur_inst.config.config_str_set.all().values_list("name", flat=True)) + \
            list(cur_inst.config.config_int_set.all().values_list("name", flat=True)) + \
            list(cur_inst.config.config_bool_set.all().values_list("name", flat=True)) + \
            list(cur_inst.config.config_blob_set.exclude(Q(pk=cur_inst.pk)).values_list("name", flat=True))
        if cur_inst.name in all_var_names:
            raise ValidationError("name already used")

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
            
def get_related_models(in_obj):
    used_objs = 0
    for rel_obj in in_obj._meta.get_all_related_objects():
        rel_field_name = rel_obj.field.name
        used_objs += rel_obj.model.objects.filter(Q(**{rel_field_name : in_obj})).count()
    return used_objs
