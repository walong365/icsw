# Copyright (C) 2001-2015 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw-server
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
""" models for NOCTUA and CORVUS, master file """
""" only used for migration to stable 0800 state """

from django.apps import apps
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError, ImproperlyConfigured
from django.db import models
from django.db.models import Q, signals
from django.dispatch import receiver
from django.utils.lru_cache import lru_cache
from django.utils.crypto import get_random_string
from initat.cluster.backbone.middleware import thread_local_middleware, thread_local_obj
from lxml import etree  # @UnresolvedImport
from lxml.builder import E  # @UnresolvedImport
import crypt
import datetime
from initat.tools import ipvx_tools
import json
import logging
from initat.tools import logging_tools
import marshal
from initat.tools import net_tools
from initat.tools import process_tools
import pytz
import random
import re
from initat.tools import server_command
import time
import uuid

from initat.cluster.backbone.models.domain import *  # @UnusedWildImport
from initat.cluster.backbone.models.config import *  # @UnusedWildImport
from initat.cluster.backbone.models.monitoring import *  # @UnusedWildImport
from initat.cluster.backbone.models.network import *  # @UnusedWildImport
from initat.cluster.backbone.models.package import *  # @UnusedWildImport
from initat.cluster.backbone.models.user import *  # @UnusedWildImport
from initat.cluster.backbone.models.background import *  # @UnusedWildImport
from initat.cluster.backbone.models.hints import *  # @UnusedWildImport
from initat.cluster.backbone.models.rms import *  # @UnusedWildImport
from initat.cluster.backbone.models.partition import *  # @UnusedWildImport
from initat.cluster.backbone.models.setup import *  # @UnusedWildImport
from initat.cluster.backbone.models.graph import *  # @UnusedWildImport
from initat.cluster.backbone.models.kpi import *  # @UnusedWildImport
from initat.cluster.backbone.models.license import *  # @UnusedWildImport


logger = logging.getLogger(__name__)


def db_limit_1():
    # return True if databases do not support some unique_together combinations
    return True if settings.DATABASES["default"]["ENGINE"].lower().count("oracle") else False


class DeviceVariableManager(models.Manager):

    def get_cluster_id(self):
        try:
            return self.get(name="CLUSTER_ID").val_str
        except device_variable.DoesNotExist:
            return None


class device_variable(models.Model):
    objects = DeviceVariableManager()

    idx = models.AutoField(db_column="device_variable_idx", primary_key=True)
    device = models.ForeignKey("device")
    is_public = models.BooleanField(default=True)
    name = models.CharField(max_length=765)
    description = models.CharField(max_length=765, default="", blank=True)
    # can be copied to a group or device ? There is no sense in making the cluster_name a local instance
    local_copy_ok = models.BooleanField(default=True)
    # will the variable be inerited by lower levels (CDG -> DG -> D) ?
    inherit = models.BooleanField(default=True)
    # protected, not deletable by frontend
    protected = models.BooleanField(default=False)
    var_type = models.CharField(
        max_length=3,
        choices=[
            ("i", "integer"),
            ("s", "string"),
            ("d", "datetime"),
            ("t", "time"),
            ("b", "blob"),
            # only for posting a new dv
            ("?", "guess")
        ]
    )
    val_str = models.TextField(blank=True, null=True, default="")
    val_int = models.IntegerField(null=True, blank=True, default=0)
    # base64 encoded
    val_blob = models.TextField(blank=True, null=True, default="")
    val_date = models.DateTimeField(null=True, blank=True)
    val_time = models.TextField(blank=True, null=True)  # This field type is a guess.
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = u'device_variable'
        unique_together = ("name", "device",)
        ordering = ("name",)


class device_config(models.Model):
    idx = models.AutoField(db_column="device_config_idx", primary_key=True)
    device = models.ForeignKey("device")
    config = models.ForeignKey("backbone.config", db_column="new_config_id")
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = u'device_config'


class DeviceSNMPInfo(models.Model):
    idx = models.AutoField(db_column="device_idx", primary_key=True)
    device = models.OneToOneField("backbone.device", related_name="DeviceSNMPInfo", null=True)
    description = models.CharField(default="", max_length=512)
    contact = models.CharField(default="", max_length=512)
    name = models.CharField(default="", max_length=512)
    location = models.CharField(default="", max_length=512)
    services = models.IntegerField(default=0)
    date = models.DateTimeField(auto_now_add=True)


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
    mon_device_templ = models.ForeignKey("backbone.mon_device_templ", null=True, blank=True)
    mon_device_esc_templ = models.ForeignKey("backbone.mon_device_esc_templ", null=True, blank=True)
    mon_ext_host = models.ForeignKey("backbone.mon_ext_host", null=True, blank=True)
    etherboot_valid = models.BooleanField(default=False)
    kernel_append = models.CharField(max_length=384, blank=True)
    newkernel = models.CharField(max_length=192, blank=True)
    new_kernel = models.ForeignKey("kernel", null=True, related_name="new_kernel")
    actkernel = models.CharField(max_length=192, blank=True)
    act_kernel = models.ForeignKey("kernel", null=True, related_name="act_kernel")
    act_kernel_build = models.IntegerField(null=True, blank=True)
    kernelversion = models.CharField(max_length=192, blank=True)
    stage1_flavour = models.CharField(max_length=48, blank=True, default="CPIO")
    newimage = models.CharField(max_length=765, blank=True)
    new_image = models.ForeignKey("image", null=True, related_name="new_image")
    actimage = models.CharField(max_length=765, blank=True)
    act_image = models.ForeignKey("image", null=True, related_name="act_image")
    imageversion = models.CharField(max_length=192, blank=True)
    # new partition table
    partition_table = models.ForeignKey("backbone.partition_table", null=True, related_name="new_partition_table")
    # current partition table
    act_partition_table = models.ForeignKey("backbone.partition_table", null=True, related_name="act_partition_table", blank=True)
    partdev = models.CharField(max_length=192, blank=True)
    fixed_partdev = models.IntegerField(null=True, blank=True)
    bz2_capable = models.IntegerField(null=True, blank=True)
    new_state = models.ForeignKey("backbone.status", null=True, db_column="newstate_id", blank=True)
    rsync = models.BooleanField(default=False)
    rsync_compressed = models.BooleanField(default=False)
    prod_link = models.ForeignKey("backbone.network", db_column="prod_link", null=True, blank=True)
    # states (with timestamp)
    recvstate = models.TextField(blank=True, default="not set")
    recvstate_timestamp = models.DateTimeField(null=True)
    reqstate = models.TextField(blank=True, default="not set")
    reqstate_timestamp = models.DateTimeField(null=True)
    # uptime (with timestamp)
    uptime = models.IntegerField(default=0)
    uptime_timestamp = models.DateTimeField(null=True, default=None)
    bootnetdevice = models.ForeignKey("backbone.netdevice", null=True, related_name="boot_net_device", on_delete=models.SET_NULL)
    bootserver = models.ForeignKey("device", null=True, related_name="boot_server", blank=True)
    reachable_via_bootserver = models.BooleanField(default=False)
    dhcp_mac = models.NullBooleanField(null=True, blank=True, default=False)
    dhcp_write = models.NullBooleanField(default=False)
    dhcp_written = models.NullBooleanField(default=False)
    dhcp_error = models.CharField(max_length=765, blank=True)
    propagation_level = models.IntegerField(default=0, blank=True)
    last_install = models.CharField(max_length=192, blank=True)
    last_boot = models.CharField(max_length=192, blank=True)
    last_kernel = models.CharField(max_length=192, blank=True)
    root_passwd = models.CharField(max_length=192, blank=True)
    # link to monitor_server (or null for master)
    monitor_server = models.ForeignKey("device", null=True, blank=True)
    monitor_checks = models.BooleanField(default=True, db_column="nagios_checks", verbose_name="Checks enabled")
    # performance data tracking, also needed for IPMI and SNMP active monitoring
    enable_perfdata = models.BooleanField(default=True, verbose_name="enable perfdata, check IPMI and SNMP")
    flap_detection_enabled = models.BooleanField(default=True)
    show_in_bootcontrol = models.BooleanField(default=True)
    # not so clever here, better in extra table, FIXME
    # cpu_info = models.TextField(blank=True, null=True)
    # machine uuid, cannot be unique due to MySQL problems with unique TextFields
    uuid = models.TextField(default="", max_length=64)  # , unique=True)
    # cluster url
    curl = models.CharField(default="ssh://", max_length=512, verbose_name="cURL")
    # , choices=[
    #    ("ssh://", "ssh://"),
    #    ("snmp://", "snmp://"),
    #    ("ipmi://", "ipmi://"),
    #    ("ilo4://", "ilo4://"), # no longer used ?
    #    ]
    # )
    date = models.DateTimeField(auto_now_add=True)
    # slaves
    master_connections = models.ManyToManyField("self", through="cd_connection", symmetrical=False, related_name="slave_connections")
    # automap root for nagvis
    automap_root_nagvis = models.BooleanField(default=False)
    # parent nagvis
    nagvis_parent = models.ForeignKey("device", null=True, related_name="nagvis_childs", blank=True)
    # enabled ?
    enabled = models.BooleanField(default=True)
    # try to read relevant data from device via md-config-server
    md_cache_mode = models.IntegerField(choices=[
        (1, "automatic (server)"),
        (2, "never use cache"),
        (3, "once (until successfull)"),
        ], default=1)
    # system name
    domain_tree_node = models.ForeignKey("backbone.domain_tree_node", null=True, default=None)
    # resolve name for monitoring (i.e. use IP for monitoring)
    mon_resolve_name = models.BooleanField(default=True, verbose_name="Resolve to IP for monitoring")
    # categories for this device
    categories = models.ManyToManyField("backbone.category")
    # store rrd data to disk
    store_rrd_data = models.BooleanField(default=True)
    # has active RRDs
    has_active_rrds = models.BooleanField(default=False)
    # active snmp scheme
    snmp_schemes = models.ManyToManyField("backbone.snmp_scheme")
    # scan active ?
    active_scan = models.CharField(
        max_length=16,
        default="",
        choices=[
            ("snmp", "SNMP"),
            ("ipmi", "IPMI"),
            # also used for partition fetch
            ("hm", "Host monitor"),
        ],
        blank=True
    )

    class CSW_Meta:
        permissions = (
            ("all_devices", "Access all devices", False),
            ("show_graphs", "Access to device graphs", True),
            ("change_basic", "Change basic settings", True),
            ("change_network", "Change network", True),
            ("change_config", "Change configuration", True),
            ("change_boot", "Change boot settings", True),
            ("change_disk", "Change Disk setup", True),
            ("change_variables", "Change variables", True),
            ("change_connection", "Change device connection", True),
            ("change_monitoring", "Change device monitoring config", True),
            ("change_location", "Change device location", True),
            ("change_category", "Change device category", True),
            ("show_status_history", "Access to status history", True),
        )
        fk_ignore_list = [
            "mon_trace", "netdevice", "device_variable", "device_config", "quota_capable_blockdevice", "DeviceSNMPInfo", "devicelog", "DeviceLogEntry",
            "mon_icinga_log_raw_host_alert_data", "mon_icinga_log_aggregated_host_data",
            "mon_icinga_log_raw_service_alert_data", "mon_icinga_log_aggregated_service_data",
            "mon_icinga_log_raw_service_flapping_data", "mon_icinga_log_raw_host_flapping_data",
            "mon_icinga_log_raw_service_notification_data", "mon_icinga_log_raw_host_notification_data",
        ]

    class Meta:
        db_table = u'device'
        ordering = ("name",)
        unique_together = [("name", "domain_tree_node"), ]


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

    class Meta:
        ordering = ("parent__name", "child__name",)
        verbose_name = "Controlling device connection"


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
    # enabled flag, ident to the enabled flag of the corresponding meta-device
    enabled = models.BooleanField(default=True)
    # domain tree node, see enabled flag
    domain_tree_node = models.ForeignKey("domain_tree_node", null=True, default=None)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = u'device_group'
        ordering = ("-cluster_device_group", "name",)


# license related
class cluster_license(models.Model):
    idx = models.AutoField(db_column="device_rsync_config_idx", primary_key=True)
    name = models.CharField(max_length=64, default="", unique=True)
    enabled = models.BooleanField(default=False)
    description = models.CharField(max_length=256, default="")
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("name",)


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
    # for ordering
    priority = models.IntegerField(default=0)
    description = models.CharField(unique=True, max_length=192)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = u'device_type'


class DeviceLogEntry(models.Model):
    idx = models.AutoField(primary_key=True)
    device = models.ForeignKey("device")
    # link to source, required
    source = models.ForeignKey("LogSource")
    # link to user or None
    user = models.ForeignKey("user", null=True)
    level = models.ForeignKey("LogLevel")
    text = models.CharField(max_length=765, default="")
    date = models.DateTimeField(auto_now_add=True)


class LogSource(models.Model):
    idx = models.AutoField(primary_key=True)
    # server_type or user
    identifier = models.CharField(max_length=192)
    # link to device or None
    device = models.ForeignKey("device", null=True)
    # long description
    description = models.CharField(max_length=765, default="")
    date = models.DateTimeField(auto_now_add=True)


class LogLevel(models.Model):
    idx = models.AutoField(primary_key=True)
    identifier = models.CharField(max_length=2, unique=True)
    level = models.IntegerField(default=logging_tools.LOG_LEVEL_OK)
    name = models.CharField(max_length=32, unique=True)
    date = models.DateTimeField(auto_now_add=True)


class devicelog(models.Model):
    idx = models.AutoField(db_column="devicelog_idx", primary_key=True)
    device = models.ForeignKey("device", null=True, blank=True)
    log_source = models.ForeignKey("log_source", null=True)
    user = models.ForeignKey("user", null=True)
    log_status = models.ForeignKey("log_status", null=True)
    text = models.CharField(max_length=765, blank=True)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = u'devicelog'


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

    class Meta:
        db_table = u'log_source'
        verbose_name = u"Log source (old)"


class log_status(models.Model):
    idx = models.AutoField(db_column="log_status_idx", primary_key=True)
    identifier = models.CharField(max_length=12, blank=True)
    log_level = models.IntegerField(null=True, blank=True)
    name = models.CharField(max_length=192, blank=True)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = u'log_status'


class mac_ignore(models.Model):
    idx = models.AutoField(db_column="mac_ignore_idx", primary_key=True)
    macaddr = models.CharField(max_length=192, db_column="macadr", default="00:00:00:00:00:00")
    user = models.ForeignKey("backbone.user", null=True)
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


class status(models.Model):
    idx = models.AutoField(db_column="status_idx", primary_key=True)
    status = models.CharField(unique=True, max_length=255)
    prod_link = models.BooleanField(default=True)
    memory_test = models.BooleanField(default=False)
    boot_iso = models.BooleanField(default=False)
    boot_local = models.BooleanField(default=False)
    do_install = models.BooleanField(default=False)
    is_clean = models.BooleanField(default=False)
    # allow mother to set bools according to status
    allow_boolean_modify = models.BooleanField(default=True)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = u'status'


class tree_node(models.Model):
    idx = models.AutoField(primary_key=True)
    device = models.ForeignKey("device", default=None)
    is_dir = models.BooleanField(default=False)
    is_link = models.BooleanField(default=False)
    parent = models.ForeignKey("tree_node", null=True, default=None)
    # is an intermediate node is has not to be created
    intermediate = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)


class wc_files(models.Model):
    idx = models.AutoField(db_column="wc_files_idx", primary_key=True)
    device = models.ForeignKey("device")
    tree_node = models.OneToOneField("tree_node", null=True, default=None)
    run_number = models.IntegerField(default=0)
    config = models.ManyToManyField("backbone.config")
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
    # content, defaults to the empty string, base64-encoded for binary data
    content = models.TextField(blank=True, default="")
    binary = models.BooleanField(default=False)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = u'wc_files'
        app_label = "backbone"


class quota_capable_blockdevice(models.Model):
    idx = models.AutoField(primary_key=True)
    device = models.ForeignKey("device")
    block_device_path = models.CharField(max_length=256, default="")
    # mount path, empty for not mounted
    mount_path = models.CharField(max_length=512, default="")
    # filesystemtype, link to partition_fs
    fs_type = models.ForeignKey("backbone.partition_fs")
    # size in Bytes
    size = models.BigIntegerField(default=0)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "backbone"


class DeleteRequest(models.Model):
    idx = models.AutoField(primary_key=True)
    obj_pk = models.IntegerField()
    model = models.TextField()
    delete_strategies = models.TextField(null=True, blank=True)

    class Meta:
        app_label = "backbone"
        if not db_limit_1():
            unique_together = ("obj_pk", "model")
