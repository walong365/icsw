# Copyright (C) 2001-2015 Andreas Lang-Nevyjel, init.at
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
""" models for NOCTUA and CORVUS, master file """

from django.apps import apps
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError, ImproperlyConfigured
from django.core.signals import request_finished, request_started
from django.db import models
from django.db.models import Q, signals
from django.dispatch import receiver
from django.utils.lru_cache import lru_cache
from django.utils.crypto import get_random_string
from initat.cluster.backbone.middleware import thread_local_middleware, \
    _thread_local
from initat.cluster.backbone.models.functions import _check_empty_string, \
    _check_float, _check_integer, _check_non_empty_string, to_system_tz, \
    get_change_reset_list, get_related_models, cluster_timezone, duration
from lxml import etree  # @UnresolvedImport
from lxml.builder import E  # @UnresolvedImport
import crypt
import collections
import datetime
import json
import logging
import marshal
import pytz
import random
import re
import time
import uuid

from initat.tools import ipvx_tools
from initat.tools import logging_tools
from initat.tools import net_tools
from initat.tools import process_tools
from initat.tools import server_command

from initat.cluster.backbone.models.capability import *  # @UnusedWildImport
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
from initat.cluster.backbone.models.status_history import *  # @UnusedWildImport
from initat.cluster.backbone.signals import user_changed, group_changed, \
    bootsettings_changed, virtual_desktop_user_setting_changed
import initat.cluster.backbone.models.model_history


# attention: this list is used in create_fixtures.py
LICENSE_CAPS = [
    ("monitor", "Monitoring services", ["md-config"]),
    ("monext", "Extended monitoring services", ["md-config"]),
    ("boot", "boot/config facility for nodes", ["mother"]),
    ("package", "Package installation", ["package"]),
    ("rms", "Resource Management system", ["rms"]),
    ("docu", "show documentation", []),
]

ALL_LICENSES = [name for name, _descr, _srv in LICENSE_CAPS]


def get_license_descr(name):
    return [_descr for _name, _descr, _srv in LICENSE_CAPS if name == _name][0]

ALLOWED_CFS = ["MAX", "MIN", "AVERAGE"]

logger = logging.getLogger(__name__)


class cs_timer(object):
    def __init__(self):
        self.start_time = time.time()

    def __call__(self, what):
        cur_time = time.time()
        log_str = "{} in {}".format(
            what,
            logging_tools.get_diff_time_str(cur_time - self.start_time)
        )
        self.start_time = cur_time
        return log_str


@receiver(request_started)
def bg_req_started(*args, **kwargs):
    # init number of background jobs created
    _thread_local.num_bg_jobs = 0


@receiver(request_finished)
def bg_req_finished(*args, **kwargs):
    # check number of background jobs and signal localhost
    if getattr(_thread_local, "num_bg_jobs", 0):
        _thread_local.num_bg_jobs = 0
        _signal_localhost()


@receiver(user_changed)
def user_changed(*args, **kwargs):
    _insert_bg_job("sync_users", kwargs["cause"], kwargs["user"])


@receiver(group_changed)
def group_changed(*args, **kwargs):
    _insert_bg_job("sync_users", kwargs["cause"], kwargs["group"])


@receiver(virtual_desktop_user_setting_changed)
def vdus_changed(*args, **kwargs):
    _insert_bg_job("reload_virtual_desktop_dispatcher", kwargs["cause"], kwargs["vdus"])


@receiver(bootsettings_changed)
def rcv_bootsettings_changed(*args, **kwargs):
    # not signal when bootserver is not set
    if kwargs["device"].bootserver_id:
        _insert_bg_job("change_bootsetting", kwargs["cause"], kwargs["device"])


def _insert_bg_job(cmd, cause, obj):
    if getattr(obj, "_no_bg_job", False):
        return
    # create entry to be handled by the cluster-server
    # get local device, key is defined in routing.py
    _routing_key = "_WF_ROUTING"
    _resolv_dict = cache.get(_routing_key)
    if _resolv_dict:
        _r_dict = json.loads(_resolv_dict)
        if "_local_device" in _r_dict:
            _local_pk = _r_dict["_local_device"][0]
        else:
            _local_pk = 0
    else:
        try:
            _local_pk = device.objects.get(Q(name=process_tools.get_machine_name())).pk
        except device.DoesNotExist:
            _local_pk = 0
    # we need local_pk and a valid user (so we have to be called via webfrontend)
    if _local_pk and thread_local_middleware().user and isinstance(thread_local_middleware().user, user):
        srv_com = server_command.srv_command(
            command=cmd,
        )
        _bld = srv_com.builder()
        srv_com["object"] = _bld.object(
            unicode(obj),
            model=obj._meta.model_name,
            app=obj._meta.app_label,
            pk="{:d}".format(obj.pk)
        )
        background_job.objects.create(
            command=cmd,
            cause=u"{} of '{}'".format(cause, unicode(obj)),
            state="pre-init",
            initiator=device.objects.get(Q(pk=_local_pk)),
            user=thread_local_middleware().user,
            command_xml=unicode(srv_com),
            # valid for 4 hours
            valid_until=cluster_timezone.localize(datetime.datetime.now() + datetime.timedelta(seconds=60 * 5)),  # 3600 * 4)),
        )
        # init if not already done
        if not hasattr(_thread_local, "num_bg_jobs"):
            _thread_local.num_bg_jobs = 1
        else:
            _thread_local.num_bg_jobs += 1
    else:
        if not _local_pk:
            logger.error("cannot identify local device")


def _signal_localhost():
    # signal clusterserver running on localhost
    _sender = net_tools.zmq_connection("wf_server_notify")
    # only send no receive
    _sender.add_connection("tcp://localhost:8004", server_command.srv_command(command="wf_notify"), multi=True)
    # close connection / terminate context
    _sender.close()


def boot_uuid(cur_uuid):
    return "{}-boot".format(cur_uuid[:-5])


class home_export_list(object):
    """ build home_export_list (dict) from DB, used in forms.py and ldap_modules.py """
    def __init__(self):
        exp_entries = device_config.objects.filter(
            Q(config__name__icontains="homedir") &
            Q(config__name__icontains="export") &
            Q(device__is_meta_device=False)
        ).prefetch_related(
            "config__config_str_set"
        ).select_related(
            "device",
            "device__domain_tree_node"
        )
        home_exp_dict = {}
        for entry in exp_entries:
            dev_name, dev_name_full, act_pk = (
                entry.device.name,
                entry.device.full_name,
                entry.pk,
            )
            home_exp_dict[act_pk] = {
                "key": act_pk,
                "entry": entry,
                "name": dev_name,
                "full_name": dev_name_full,
                "homeexport": "",
                "node_postfix": "",
                "createdir": "",
                "options": "-soft",
            }
            for c_str in entry.config.config_str_set.all():
                if c_str.name in home_exp_dict[act_pk]:
                    home_exp_dict[act_pk][c_str.name] = c_str.value
        # remove invalid exports (with no homeexport-entry)
        invalid_home_keys = [key for key, value in home_exp_dict.iteritems() if not value["homeexport"]]
        for ihk in invalid_home_keys:
            del home_exp_dict[ihk]
        for key, value in home_exp_dict.iteritems():
            value["info"] = u"{} on {}".format(value["homeexport"], value["name"])
            value["entry"].info_str = value["info"]
            value["entry"].info_dict = value
        self.exp_dict = home_exp_dict

    def get(self, *args, **kwargs):
        # hacky
        return self.exp_dict[int(kwargs["pk"])]["entry"]

    def all(self):
        for pk in [s_pk for _s_info, s_pk in sorted([(value["info"], key) for key, value in self.exp_dict.iteritems()])]:
            yield self.exp_dict[pk]["entry"]


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

    def set_value(self, value):
        if type(value) == datetime.datetime:
            self.var_type = "d"
            self.val_date = cluster_timezone.localize(value)
        elif type(value) in [int, long] or (isinstance(value, basestring) and value.isdigit()):
            self.var_type = "i"
            self.val_int = int(value)
        else:
            self.var_type = "s"
            self.val_str = value
        self._clear()

    def get_value(self):
        if self.var_type == "i":
            return self.val_int
        elif self.var_type == "s":
            return self.val_str
        else:
            return "get_value for {}".format(self.var_type)

    def _clear(self):
        # clear all values which are not used
        for _short, _long in [
            ("i", "int"),
            ("s", "str"),
            ("b", "blob"),
            ("d", "date"),
            ("t", "time")
        ]:
            if self.var_type != _short:
                setattr(self, "val_{}".format(_long), None)
    value = property(get_value, set_value)

    def __unicode__(self):
        return "{}[{}] = {}".format(
            self.name,
            self.var_type,
            str(self.get_value())
        )

    def init_as_gauge(self, max_value, start=0):
        self.__max, self.__cur = (max_value, start)
        self._update_gauge()

    def count(self, num=1):
        self.__cur += num
        self._update_gauge()

    def _update_gauge(self):
        new_val = min(100, int(float(100 * self.__cur) / float(max(1, self.__max))))
        if self.pk:
            if self.val_int != new_val:
                self.val_int = new_val
                device_variable.objects.filter(Q(pk=self.pk)).update(val_int=new_val)
        else:
            self.val_int = new_val
            self.save()

    class Meta:
        db_table = u'device_variable'
        unique_together = ("name", "device",)
        ordering = ("name",)
        verbose_name = "Device variable"


@receiver(signals.pre_save, sender=device_variable)
def device_variable_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        if cur_inst.device_id:
            _check_empty_string(cur_inst, "name")
            if cur_inst.var_type == "?":
                # guess type
                _val = cur_inst.val_str
                cur_inst.val_str = ""
                if len(_val.strip()) and _val.strip().isdigit():
                    cur_inst.var_type = "i"
                    cur_inst.val_int = int(_val.strip())
                else:
                    cur_inst.var_type = "s"
                    cur_inst.val_str = _val
            if cur_inst.var_type == "s":
                _check_empty_string(cur_inst, "val_str")
            if cur_inst.var_type == "i":
                _check_integer(cur_inst, "val_int")
            _check_empty_string(cur_inst, "var_type")
            all_var_names = device_variable.objects.exclude(Q(pk=cur_inst.pk)).filter(Q(device=cur_inst.device)).values_list("name", flat=True)
            if cur_inst.name in all_var_names:
                raise ValidationError(
                    "name '{}' already used for device '{}'".format(
                        cur_inst.name,
                        unicode(cur_inst.device)
                    )
                )
            cur_inst._clear()


class device_config(models.Model):
    idx = models.AutoField(db_column="device_config_idx", primary_key=True)
    device = models.ForeignKey("device")
    config = models.ForeignKey("backbone.config", db_column="new_config_id")
    date = models.DateTimeField(auto_now_add=True)

    def home_info(self):
        return self.info_str

    class Meta:
        db_table = u'device_config'
        verbose_name = "Device configuration"


@receiver(signals.post_save, sender=device_config)
def _device_config_post_save(sender, instance, raw, **kwargs):
    if not raw:
        log_usage_data = collections.defaultdict(lambda: [])

        for mcc in instance.config.mon_check_command_set.all().select_related("mon_service_templ"):
            if mcc.mon_service_templ is not None and mcc.mon_service_templ.any_notification_enabled():
                log_usage_data[instance.device_id].append(mcc)

        LicenseUsage.log_usage(LicenseEnum.notification, LicenseParameterTypeEnum.service, log_usage_data)


class DeviceSNMPInfo(models.Model):
    idx = models.AutoField(db_column="device_idx", primary_key=True)
    device = models.OneToOneField("backbone.device", related_name="DeviceSNMPInfo", null=True)
    description = models.CharField(default="", max_length=512)
    contact = models.CharField(default="", max_length=512)
    name = models.CharField(default="", max_length=512)
    location = models.CharField(default="", max_length=512)
    services = models.IntegerField(default=0)
    date = models.DateTimeField(auto_now_add=True)


class DeviceEnabledManager(models.Manager):
    def get_queryset(self):
        return super(DeviceEnabledManager, self).get_queryset().filter(Q(enabled=True) & Q(device_group__enabled=True))


class RealDeviceEnabledManager(models.Manager):
    def get_queryset(self):
        return super(RealDeviceEnabledManager, self).get_queryset().filter(Q(enabled=True) & Q(device_group__enabled=True) & Q(is_meta_device=False))


class MetaDeviceEnabledManager(models.Manager):
    def get_queryset(self):
        return super(MetaDeviceEnabledManager, self).get_queryset().filter(Q(enabled=True) & Q(device_group__enabled=True) & Q(is_meta_device=True))


class device(models.Model):
    objects = models.Manager()
    all_enabled = DeviceEnabledManager()
    all_real_enabled = RealDeviceEnabledManager()
    all_meta_enabled = MetaDeviceEnabledManager()
    idx = models.AutoField(db_column="device_idx", primary_key=True)
    # no longer unique as of 20130531 (ALN)
    # no dots allowed (these parts are now in domain_tree_node)
    name = models.CharField(max_length=192)
    # FIXME
    device_group = models.ForeignKey("device_group", related_name="device_group")
    alias = models.CharField(max_length=384, blank=True)
    comment = models.CharField(max_length=384, blank=True)
    mon_device_templ = models.ForeignKey("backbone.mon_device_templ", null=True, blank=True)
    mon_device_esc_templ = models.ForeignKey("backbone.mon_device_esc_templ", null=True, blank=True)
    mon_ext_host = models.ForeignKey("backbone.mon_ext_host", null=True, blank=True)
    etherboot_valid = models.BooleanField(default=False)
    kernel_append = models.CharField(max_length=384, blank=True)
    new_kernel = models.ForeignKey("kernel", null=True, related_name="new_kernel")
    # act_kernel = models.ForeignKey("kernel", null=True, related_name="act_kernel")
    # act_kernel_build = models.IntegerField(null=True, blank=True)
    stage1_flavour = models.CharField(max_length=48, blank=True, default="CPIO")
    new_image = models.ForeignKey("image", null=True, related_name="new_image")
    # act_image = models.ForeignKey("image", null=True, related_name="act_image")
    # kernel version running
    # kernelversion = models.CharField(max_length=192, blank=True, default="")
    # image version running
    # imageversion = models.CharField(max_length=192, blank=True, default="")
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
    # recvstate = models.TextField(blank=True, default="not set")
    # recvstate_timestamp = models.DateTimeField(null=True)
    # reqstate = models.TextField(blank=True, default="not set")
    # reqstate_timestamp = models.DateTimeField(null=True)
    # uptime (with timestamp)
    # uptime = models.IntegerField(default=0)
    # uptime_timestamp = models.DateTimeField(null=True, default=None)
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
    # communication capability list, like IPMI, WMI, SNMP
    com_capability_list = models.ManyToManyField("backbone.ComCapability")
    # has an IPMI interface
    ipmi_capable = models.BooleanField(default=False, verbose_name="IPMI cabaple", blank=True)
    # flag: is meta device ?
    is_meta_device = models.BooleanField(default=False, blank=True)
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

    @property
    def full_name(self):
        if not self.domain_tree_node_id:
            self.domain_tree_node = domain_tree_node.objects.get(Q(depth=0))
            self.save()
        if self.domain_tree_node.full_name:
            return ".".join([self.name, self.domain_tree_node.full_name])
        else:
            return self.name

    @staticmethod
    def get_device(fqdn):
        if fqdn.count("."):
            _sn, _domain = fqdn.split(".", 1)
        else:
            _sn, _domain = (fqdn, "")
        try:
            _dev = device.objects.get(Q(name=_sn) & Q(domain_tree_node__full_name=_domain))
        except:
            _dev = None
        return _dev

    @property
    def display_name(self):
        # like full_name but replaces METADEV_ with group
        _name = self.full_name
        if self.is_meta_device and _name.startswith("METADEV_"):
            _name = "group {}".format(_name[8:])
        return _name

    def crypt(self, in_pwd):
        if in_pwd:
            salt = "".join([chr(random.randint(65, 90)) for _idx in xrange(4)])
            _crypted = crypt.crypt(in_pwd, salt)
            if _crypted == "*0":
                _crypted = ""
        else:
            _crypted = ""
        return _crypted

    def root_passwd_set(self):
        return True if self.root_passwd else False

    def device_group_name(self):
        return self.device_group.name

    def is_cluster_device_group(self):
        return self.device_group.cluster_device_group

    def get_monitor_type(self):
        sel_configs = set(self.device_config_set.filter(
            Q(config__name__in=["monitor_server", "monitor_master", "monitor_slave"])).values_list("config__name", flat=True)
        )
        if set(["monitor_master", "monitor_server"]) & sel_configs:
            return "master"
        elif sel_configs:
            return "slave"
        else:
            return "---"

    def get_boot_uuid(self):
        return boot_uuid(self.uuid)

    def add_log_entry(self, **kwargs):
        return DeviceLogEntry.new(device=self, **kwargs)  # source=log_src, levlog_stat, text, **kwargs)

    def get_simple_xml(self):
        return E.device(
            unicode(self),
            pk="%d" % (self.pk),
            key="dev__%d" % (self.pk),
            name=self.name
        )

    def all_ips(self):
        # return all IPs
        return list(set(self.netdevice_set.all().values_list("net_ip__ip", flat=True)))

    def all_dns(self):
        # return all names, including short ones
        _list = [self.name, self.full_name]
        for _domain, _alias, _excl in self.netdevice_set.all().values_list("net_ip__domain_tree_node__full_name", "net_ip__alias", "net_ip__alias_excl"):
            if _alias:
                _add_names = _alias.strip().split()
                if not _excl:
                    _add_names.append(self.name)
            else:
                _add_names = [self.name]
            _list.extend(["{}.{}".format(_name, _domain) for _name in _add_names])
        return list(set(_list))

    def get_act_image(self):
        if self.imagedevicehistory_set.all().count():
            _ho = self.imagedevicehistory_set.all()[0]
            return (_ho.image_id, _ho.version, _ho.release)
        else:
            return None

    def get_act_kernel(self):
        if self.kerneldevicehistory_set.all().count():
            _ho = self.kerneldevicehistory_set.all()[0]
            return (_ho.kernel_id, _ho.version, _ho.release)
        else:
            return None

    # def get_uptime(self):
    #    _rs = 0
    #    if self.mother_xml is not None:
    #        if int(self.mother_xml.get("ok", "0")):
    #            now, uptime_ts = (
    #                cluster_timezone.localize(datetime.datetime.now()).astimezone(pytz.UTC),
    #                self.uptime_timestamp,
    #            )
    #            if uptime_ts is not None:
    #                uptime_timeout = (now - uptime_ts).seconds
    #            else:
    #                uptime_timeout = 3600
    #            if uptime_timeout > 30:
    #                # too long ago, outdated
    #                _rs = 0
    #            else:
    #                _rs = self.uptime
    #    return _rs

    # def uptime_valid(self):
    #    _rs = False
    #    if self.mother_xml is not None:
    #        if int(self.mother_xml.get("ok", "0")):
    #            now, uptime_ts = (
    #                cluster_timezone.localize(datetime.datetime.now()).astimezone(pytz.UTC),
    #                self.uptime_timestamp,
    #            )
    #            if uptime_ts is not None:
    #                uptime_timeout = (now - uptime_ts).seconds
    #            else:
    #                uptime_timeout = 3600
    #            if uptime_timeout > 30:
    #                # too long ago, outdated
    #                _rs = False
    #            else:
    #                _rs = True
    #    return _rs

    def latest_contact(self):
        lc_obj = [obj for obj in self.device_variable_set.all() if obj.name == "package_server_last_contact"]
        if lc_obj:
            return int(time.mktime(to_system_tz(lc_obj[0].val_date).timetuple()))
        else:
            return 0

    def client_version(self):
        vers_obj = [obj for obj in self.device_variable_set.all() if obj.name == "package_client_version"]
        if vers_obj:
            return vers_obj[0].val_str
        else:
            return "?.?"

    def create_boot_history(self):
        return DeviceBootHistory.objects.create(
            device=self,
        )

    def __unicode__(self):
        return u"{}{}".format(
            self.name,
            u" ({})".format(self.comment) if self.comment else "")

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
            "KernelDeviceHistory", "ImageDeviceHistory", "DeviceBootHistory",
            "mon_icinga_log_raw_host_alert_data", "mon_icinga_log_aggregated_host_data",
            "mon_icinga_log_raw_service_alert_data", "mon_icinga_log_aggregated_service_data",
            "mon_icinga_log_raw_service_flapping_data", "mon_icinga_log_raw_host_flapping_data",
            "mon_icinga_log_raw_service_notification_data", "mon_icinga_log_raw_host_notification_data",
            "mon_icinga_log_raw_service_downtime_data", "mon_icinga_log_raw_host_downtime_data",
            "LicenseUsageDeviceService", "LicenseLockListDeviceService",
        ]

    class Meta:
        db_table = u'device'
        ordering = ("name",)
        unique_together = [("name", "domain_tree_node"), ]
        verbose_name = u'Device'


class DeviceBootHistory(models.Model):
    # new kernel and / or image changes are connected to the device via this structure
    # might be empty if we only boot
    idx = models.AutoField(primary_key=True)
    device = models.ForeignKey("device")
    date = models.DateTimeField(auto_now_add=True)


class device_selection(object):
    def __init__(self, sel_str):
        parts = sel_str.split("__")
        self.idx = int(parts[1])
        self.sel_type = {"dev": "d", "devg": "g"}[parts[0]]


@receiver(signals.post_save, sender=device)
def device_post_save(sender, **kwargs):
    if "instance" in kwargs:
        _cur_inst = kwargs["instance"]
        if _cur_inst.bootserver_id:
            bootsettings_changed.send(sender=_cur_inst, device=_cur_inst, cause="device_changed")
        if _cur_inst.is_meta_device:
            _stripped = strip_metadevice_name(_cur_inst.name)
            if _stripped != _cur_inst.device_group.name:
                _cur_inst.device_group.name = _stripped
                _cur_inst.device_group.save()
            if _cur_inst.device_group.cluster_device_group:
                # check for device ID
                _var_dict = {_v.name: _v for _v in _cur_inst.device_variable_set.all()}
                # if "CLUSTER_NAME" not in _var_dict:
                #    device_variable.objects.create(
                #        device=_cur_inst,
                #        name="CLUSTER_NAME",
                #        val_str="new Cluster",
                #        var_type="s",
                #        inherit=False,
                #    )
                if "CLUSTER_ID" not in _var_dict:
                    device_variable.objects.create(
                        device=_cur_inst,
                        name="CLUSTER_ID",
                        is_public=False,
                        val_str="{}-{}".format(  # NOTE: license admin gui checks for this pattern
                            get_random_string(6, "ABCDEFGHKLPRSTUWXYZ123456789"),
                            get_random_string(4, "ABCDEFGHKLPRSTUWXYZ123456789"),
                        ),
                        var_type="s",
                        inherit=False,
                        protected=True,
                    )


def _get_top_level_dtn():
    try:
        top_level_dn = domain_tree_node.objects.get(Q(depth=0))
    except domain_tree_node.DoesNotExist:
        top_level_dn = None
    return top_level_dn


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
                    raise ValidationError("domain '{}' not defined".format(dom_name))
            else:
                cur_inst.domain_tree_node = cur_dnt
                cur_inst.name = short_name
        else:
            if not cur_inst.domain_tree_node_id:
                cur_inst.domain_tree_node = _get_top_level_dtn()
            if not cur_inst.pk:
                top_level_dn = _get_top_level_dtn()
                if top_level_dn is not None:
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
                raise ValidationError("illegal characters in name '{}'".format(cur_inst.name))
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
                raise ValidationError(
                    "UUID clash (={} for {} and {})".format(
                        cur_inst.uuid,
                        unicode(cur_inst),
                        unicode(present_dev),
                    )
                )
        # check for device group
        if cur_inst.device_group.cluster_device_group and not cur_inst.is_meta_device:
            raise ValidationError("no devices allowed in cluster_device_group")


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

    def __unicode__(self):
        return "{} (via {}) {}".format(
            unicode(self.parent),
            self.connection_info,
            unicode(self.child))

    class Meta:
        ordering = ("parent__name", "child__name",)
        verbose_name = "Controlling device connection"


@receiver(signals.pre_save, sender=cd_connection)
def cd_connection_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        for par_idx in xrange(1, 5):
            _check_integer(cur_inst, "parameter_i{:d}".format(par_idx), min_val=0, max_val=256)
        try:
            cd_connection.objects.get(Q(parent=cur_inst.parent_id) & Q(child=cur_inst.child_id))
        except cd_connection.DoesNotExist:
            pass
        except cd_connection.MultipleObjectsReturned:
            raise ValidationError("connections already exist")
        else:
            if cur_inst.pk is None:
                raise ValidationError("connection already exists")


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

    def _add_meta_device(self):
        new_md = device(
            name=self.get_metadevice_name(),
            device_group=self,
            domain_tree_node=self.domain_tree_node,
            enabled=self.enabled,
            is_meta_device=True,
        )
        new_md.save()
        self.device = new_md
        self.save()
        return new_md

    def get_metadevice_name(self, name=None):
        return "METADEV_{}".format(name if name else self.name)

    class Meta:
        db_table = u'device_group'
        ordering = ("-cluster_device_group", "name",)
        verbose_name = u"Device group"

    def __unicode__(self):
        return u"{}{}{}".format(
            self.name,
            " ({})".format(self.description) if self.description else "",
            "[*]" if self.cluster_device_group else ""
        )


def strip_metadevice_name(name):
    if name.startswith("METADEV_"):
        return name[8:]
    else:
        return name


@receiver(signals.pre_save, sender=device_group)
def device_group_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        if not cur_inst.name:
            raise ValidationError("name can not be zero")
        if not valid_domain_re.match(cur_inst.name):
            raise ValidationError("invalid characters in '{}'".format(cur_inst.name))


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
        if cur_inst.device_id:
            save_meta = False
            if cur_inst.device.name != cur_inst.get_metadevice_name():
                cur_inst.device.name = cur_inst.get_metadevice_name()
                save_meta = True
            for c_field in ["enabled", "domain_tree_node"]:
                if getattr(cur_inst.device, c_field) != getattr(cur_inst, c_field):
                    setattr(cur_inst.device, c_field, getattr(cur_inst, c_field))
                    save_meta = True
            if save_meta:
                cur_inst.device.save()
        if cur_inst.cluster_device_group and not cur_inst.enabled:
            # always enable cluster device group
            cur_inst.enabled = True
            cur_inst.save()


class device_rsync_config(models.Model):
    idx = models.AutoField(db_column="device_rsync_config_idx", primary_key=True)
    config = models.ForeignKey("config", db_column="new_config_id")
    device = models.ForeignKey("device")
    last_rsync_time = models.DateTimeField(null=True, blank=True)
    status = models.TextField()
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = u'device_rsync_config'


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

    @staticmethod
    def new(**kwargs):
        _dev = kwargs.get("device")
        if not _dev:
            _dev = device.objects.get(Q(device_group__cluster_device_group=True))

        # must be a valid user object
        _user = kwargs.get("user")
        source = kwargs.get("source")
        if source is None:
            source = log_source_lookup("webfrontend")
        elif isinstance(source, basestring) or type(source) in [int, long]:
            source = log_source_lookup(source)

        level = kwargs.get("level")
        if level is None:
            level = log_level_lookup("o")
        elif isinstance(level, basestring) or type(level) in [int, long]:
            level = log_level_lookup(level)

        cur_log = DeviceLogEntry.objects.create(
            device=_dev,
            source=source,
            level=level,
            user=_user,
            text=kwargs.get("text", "no text given"),
        )
        return cur_log

    def __unicode__(self):
        return u"{} ({}, {}:{:d})".format(
            self.text,
            self.source.identifier,
            self.level.identifier,
            self.level.level,
        )


@lru_cache()
def log_source_lookup(identifier, device=None):
    if type(identifier) in [int, long]:
        return LogSource.objects.get(Q(pk=identifier))
    elif device is not None:
        return LogSource.objects.get(Q(identifier=identifier) & Q(device=device))
    else:
        return LogSource.objects.get(Q(identifier=identifier))


class LogSource(models.Model):
    idx = models.AutoField(primary_key=True)
    # server_type or user
    identifier = models.CharField(max_length=192)
    # link to device or None
    device = models.ForeignKey("device", null=True)
    # long description
    description = models.CharField(max_length=765, default="")
    date = models.DateTimeField(auto_now_add=True)

    @staticmethod
    def new(identifier, **kwargs):
        ls_dev = kwargs.get("device", None)
        sources = LogSource.objects.filter(Q(identifier=identifier) & Q(device=ls_dev))
        if len(sources) > 1:
            print("Too many LogSources present ({}), exiting".format(", ".join([identifier])))
            cur_source = None
        elif not len(sources):
            if ls_dev is not None:
                new_source = LogSource(
                    identifier=identifier,
                    description=u"{} on {}".format(identifier, unicode(ls_dev)),
                    device=ls_dev,
                )
                new_source.save()
            else:
                new_source = LogSource(
                    identifier=identifier,
                    description=kwargs.get("description", "no description for {}".format(identifier))
                )
                new_source.save()
            cur_source = new_source
        else:
            cur_source = sources[0]
        return cur_source

    def __unicode__(self):
        return "{} ({})".format(
            self.identifier,
            self.description)


@lru_cache()
def log_level_lookup(key):
    if isinstance(key, basestring):
        return LogLevel.objects.get(Q(identifier=key))
    else:
        return LogLevel.objects.get(Q(level=key))


class LogLevel(models.Model):
    idx = models.AutoField(primary_key=True)
    identifier = models.CharField(max_length=2, unique=True)
    level = models.IntegerField(default=logging_tools.LOG_LEVEL_OK)
    name = models.CharField(max_length=32, unique=True)
    date = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return "{} ({:d})".format(self.name, self.level)


class devicelog(models.Model):
    idx = models.AutoField(db_column="devicelog_idx", primary_key=True)
    device = models.ForeignKey("device", null=True, blank=True)
    log_source = models.ForeignKey("log_source", null=True)
    user = models.ForeignKey("user", null=True)
    log_status = models.ForeignKey("log_status", null=True)
    text = models.CharField(max_length=765, blank=True)
    date = models.DateTimeField(auto_now_add=True)

    # @staticmethod
    # def new_log(cur_dev, log_src, log_stat, text, **kwargs):
    # if log_src and type(log_src) in [int, long]:
    #    log_src = log_source_lookup(log_src)
    # if log_stat and type(log_stat) in [int, long]:
    #    log_stat = log_status_lookup(log_stat)
    # cur_log = devicelog.objects.create(
    #    device=cur_dev,
    #    log_source=log_src or cluster_log_source,
    #    user=kwargs.get("user", None),
    #    log_status=log_stat,
    #    text=text,
    # )
    # return cur_log

    def __unicode__(self):
        return u"DEPRECATED, {} ({}, {}:{:d})".format(
            self.text,
            self.log_source.name,
            self.log_status.identifier,
            self.log_status.log_level
        )

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

    @staticmethod
    def create_log_source_entry(identifier, name, **kwargs):
        ls_dev = kwargs.get("device", None)
        sources = log_source.objects.filter(Q(identifier=identifier) & Q(device=ls_dev))
        if len(sources) > 1:
            print("Too many log_source_entries present ({}), exiting".format(", ".join([identifier, name])))
            cur_source = None
        elif not len(sources):
            if ls_dev is not None:
                new_source = log_source(
                    identifier=identifier,
                    name=name,
                    description=u"{} on {}".format(name, unicode(ls_dev)),
                    device=kwargs["device"]
                )
                new_source.save()
            else:
                new_source = log_source(
                    identifier=identifier,
                    name=name,
                    description=kwargs.get("description", "{} (id {})".format(name, identifier))
                )
                new_source.save()
            cur_source = new_source
        else:
            cur_source = sources[0]
        return cur_source

    def __unicode__(self):
        return "{} ({}), {}".format(
            self.name,
            self.identifier,
            self.description)

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

    def get_created(self):
        return time.mktime(cluster_timezone.normalize(self.date).timetuple())

    def get_device_name(self):
        if self.device_id:
            return self.device.full_name
        else:
            return ""

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

    def info_string(self):
        return unicode(self)

    def __unicode__(self):
        # print ".", self.status
        return u"{} ({}){}".format(
            self.status,
            ",".join([short for short, attr_name in [
                ("link", "prod_link"),
                ("mem", "memory_test"),
                ("loc", "boot_local"),
                ("ins", "do_install"),
                ("iso", "boot_iso"),
                ("retain", "is_clean")] if getattr(self, attr_name)]),
            "(*)" if self.allow_boolean_modify else "")

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
        return "tree_node, {}".format(self.get_type_str())


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

    def __unicode__(self):
        return "qcb {} ({})".format(self.block_device_path, self.mount_path)

    class Meta:
        app_label = "backbone"


class DeleteRequest(models.Model):
    idx = models.AutoField(primary_key=True)
    obj_pk = models.IntegerField()
    model = models.TextField()
    delete_strategies = models.TextField(null=True, blank=True)

    class Meta:
        app_label = "backbone"
        unique_together = ("obj_pk", "model")


# register models in history
def _register_models():
    models = (
        # user
        group, csw_permission, csw_object_permission, user, user_permission, user_object_permission,
        # net
        netdevice, net_ip, peer_information,
        # device
        device, device_group, device_config, device_variable,
        # config
        config, config_catalog, config_script, config_int, config_bool, config_str, config_blob,
        # category
        category,
        # mon
        mon_check_command, mon_check_command_special,
        # kpi
        Kpi, KpiDataSourceTuple,
        # lic
        License,
    )
    for model in models:
        model_history.icsw_register(model)

_register_models()
