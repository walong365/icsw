# Copyright (C) 2001-2016 Andreas Lang-Nevyjel, init.at
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
""" models for NOCTUA and CORVUS, device definition file """

import crypt
import logging
import random
import time
import uuid

from django.core.exceptions import ValidationError
from django.db.models import signals, CASCADE
from django.dispatch import receiver
from django.utils.crypto import get_random_string
from django.utils.lru_cache import lru_cache
from enum import Enum
from lxml.builder import E
from django.contrib.postgres.fields import JSONField
from initat.cluster.backbone.models.asset import *
from initat.cluster.backbone.models.variable import device_variable
from initat.cluster.backbone.models.capability import ComCapability
from initat.cluster.backbone.models.domain import *
from initat.cluster.backbone.models.functions import check_empty_string, \
    check_integer, to_system_tz, cluster_timezone
from initat.cluster.backbone.signals import BootsettingsChanged
from initat.constants import GEN_CS_NAME
from initat.tools import config_store, logging_tools

logger = logging.getLogger(__name__)

__all__ = [
    "device",
    "device_group",
    "device_selection",
    "cd_connection",
    "DeviceSNMPInfo",
    "DeviceClass",
    "DeviceScanLock",
    "DeviceLogEntry",
    "ActiveDeviceScanEnum",
    "LogLevel",
    "LogSource",
    "DeviceBootHistory",
    "log_source_lookup",
]


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


class ActiveDeviceScanEnum(Enum):
    # base scan (nmap)
    BASE = "base_scan"
    # SNMP based scan (161 udp)
    SNMP = "snmp"
    # host monitoring (2001 tcp)
    HM = "hostmon"


class device(models.Model):
    objects = models.Manager()
    all_enabled = DeviceEnabledManager()
    all_real_enabled = RealDeviceEnabledManager()
    all_meta_enabled = MetaDeviceEnabledManager()
    idx = models.AutoField(db_column="device_idx", primary_key=True)
    # no longer unique as of 20130531 (ALN)
    # no dots allowed (these parts are now in domain_tree_node)
    name = models.CharField(max_length=192, default="")
    # FIXME
    device_group = models.ForeignKey("backbone.device_group", related_name="device_group")
    alias = models.CharField(max_length=384, blank=True, default="")
    comment = models.CharField(max_length=384, blank=True, default="")
    mon_device_templ = models.ForeignKey("backbone.mon_device_templ", null=True, blank=True)
    mon_device_esc_templ = models.ForeignKey("backbone.mon_device_esc_templ", null=True, blank=True)
    mon_ext_host = models.ForeignKey("backbone.mon_ext_host", null=True, blank=True)
    etherboot_valid = models.BooleanField(default=False)
    kernel_append = models.CharField(max_length=384, blank=True)
    new_kernel = models.ForeignKey("kernel", null=True, related_name="new_kernel")
    # act_kernel = models.ForeignKey("kernel", null=True, related_name="act_kernel")
    # act_kernel_build = models.IntegerField(null=True, blank=True)
    stage1_flavour = models.CharField(max_length=48, blank=True, default="cpio")
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
    enable_perfdata = models.BooleanField(default=True, verbose_name="enable perfdata, check IPMI, SNMP and WMI")
    flap_detection_enabled = models.BooleanField(default=True)
    show_in_bootcontrol = models.BooleanField(default=True)
    # not so clever here, better in extra table, FIXME
    # cpu_info = models.TextField(blank=True, null=True)
    # machine uuid, cannot be unique due to MySQL problems with unique TextFields
    uuid = models.TextField(default="", max_length=64)
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
    md_cache_mode = models.IntegerField(
        choices=[
            (1, "automatic (server)"),
            (2, "never use cache"),
            (3, "once (until successfull)"),
        ],
        default=1,
    )
    # system name
    domain_tree_node = models.ForeignKey("backbone.domain_tree_node", null=True, default=None)
    # resolve name for monitoring (i.e. use IP for monitoring)
    mon_resolve_name = models.BooleanField(default=True, verbose_name="Resolve to IP for monitoring")
    # categories for this device
    categories = models.ManyToManyField("backbone.category", blank=True)
    # store rrd data to disk
    store_rrd_data = models.BooleanField(default=True)
    # has active RRDs
    has_active_rrds = models.BooleanField(default=False)
    # communication capability list, like IPMI, WMI, SNMP
    com_capability_list = models.ManyToManyField("backbone.ComCapability")
    # x = models.BigIntegerField(default=0)
    # has an IPMI interface
    # ipmi_capable = models.BooleanField(default=False, verbose_name="IPMI cabaple", blank=True)
    # flag: is meta device ?
    is_meta_device = models.BooleanField(default=False, blank=True)
    # active snmp scheme
    snmp_schemes = models.ManyToManyField("backbone.snmp_scheme")
    # device class
    device_class = models.ForeignKey("backbone.DeviceClass", null=True)

    @classmethod
    def get_com_caps_for_lock(cls, lock_type):
        # lock_type is an ActiveDeviceScanEnum
        # return all com_caps needed for the given lock_type
        return {
            ActiveDeviceScanEnum.BASE: [],
            ActiveDeviceScanEnum.HM: [ComCapability.MatchCode.hm],
            ActiveDeviceScanEnum.SNMP: [ComCapability.MatchCode.snmp],
        }[lock_type]

    def lock_possible(self, lock_type, device_obj, server_obj, config_obj):
        # check if the a given lock collides with the new lock_type
        # return the new lock or None and a list of (what, level) log entries
        # print device
        current = self.devicescanlock_set.filter(Q(active=True))
        # TODO, FIXME
        new_lock = DeviceScanLock(
            device=device_obj,
            server=server_obj,
            config=config_obj,
            active=True,
            uuid=uuid.uuid4().get_urn(),
            description="lock for '{}'".format(str(lock_type)),
        )
        new_lock.save()
        return new_lock, [("created {}".format(unicode(new_lock)), logging_tools.LOG_LEVEL_OK)]

    @property
    def com_uuid(self):
        _uuid = self.uuid
        if not _uuid.startswith("urn:"):
            _uuid = "urn:uuid:{}".format(_uuid)
        return _uuid

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
        if {"monitor_master", "monitor_server"} & sel_configs:
            return "master"
        elif sel_configs:
            return "slave"
        else:
            return "---"

    def get_boot_uuid(self):
        return "{}-boot".format(self.uuid[:-5])

    def add_log_entry(self, **kwargs):
        return DeviceLogEntry.new(device=self, **kwargs)  # source=log_src, levlog_stat, text, **kwargs)

    def get_simple_xml(self):
        return E.device(
            unicode(self),
            pk="{:d}".format(self.pk),
            key="dev__{:d}".format(self.pk),
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
            u" ({})".format(self.comment) if self.comment else ""
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
            ("discovery_server", "Access to discovery server", False),
            ("assets", "Access Asset Information", True),
            ("dispatch_settings", "Changed dispatch settings", True),
        )
        fk_ignore_list = [
            "mon_trace", "netdevice", "device_variable", "device_config", "quota_capable_blockdevice", "DeviceSNMPInfo", "DeviceLogEntry",
            "KernelDeviceHistory", "ImageDeviceHistory", "DeviceBootHistory",
            "mon_icinga_log_raw_host_alert_data", "mon_icinga_log_aggregated_host_data",
            "mon_icinga_log_raw_service_alert_data", "mon_icinga_log_aggregated_service_data",
            "mon_icinga_log_raw_service_flapping_data", "mon_icinga_log_raw_host_flapping_data",
            "mon_icinga_log_raw_service_notification_data", "mon_icinga_log_raw_host_notification_data",
            "mon_icinga_log_raw_service_downtime_data", "mon_icinga_log_raw_host_downtime_data",
            "LicenseUsageDeviceService", "LicenseLockListDeviceService", "MachineVector",
        ]

    class Meta:
        db_table = u'device'
        ordering = ("name",)
        unique_together = [("name", "domain_tree_node"), ]
        verbose_name = u'Device'


@receiver(signals.pre_save, sender=device)
def device_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        check_empty_string(cur_inst, "name")
        if cur_inst.name.count("."):
            short_name, dom_name = cur_inst.name.split(".", 1)
            try:
                cur_dnt = domain_tree_node.objects.get(Q(full_name=dom_name))
            except domain_tree_node.DoesNotExist:
                _cs = config_store.ConfigStore(GEN_CS_NAME, quiet=True)
                # create new domain
                if _cs["auto.create.new.domains"]:
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
        if not valid_domain_re.match(cur_inst.name):
            # check if we can simple fix it
            if not valid_domain_re.match(cur_inst.name.replace(" ", "_")):
                raise ValidationError("illegal characters in name '{}'".format(cur_inst.name))
            else:
                cur_inst.name = cur_inst.name.replace(" ", "_")
        if int(cur_inst.md_cache_mode) == 0:
            cur_inst.md_cache_mode = 1
        check_integer(cur_inst, "md_cache_mode", min_val=1, max_val=3)
        if not cur_inst.uuid:
            cur_inst.uuid = str(uuid.uuid4())
        if not cur_inst.device_class:
            cur_inst.device_class = DeviceClass.objects.get(Q(default_system_class=True))
        # check for already existing device
        try:
            _cur_dev = device.objects.exclude(
                Q(pk=cur_inst.idx)
            ).get(
                Q(name=cur_inst.name) & Q(domain_tree_node=cur_inst.domain_tree_node)
            )
        except device.DoesNotExist:
            pass
        else:
            raise ValidationError("device with name '{}' already exists".format(_cur_dev.full_name))

        # check for uniqueness of UUID
        try:
            present_dev = device.objects.get(Q(uuid=cur_inst.uuid))
        except device.DoesNotExist:
            pass
        else:
            if present_dev.pk != cur_inst.pk:
                raise ValidationError(
                    "UUID clash (same value '{}' for {} and {})".format(
                        cur_inst.uuid,
                        unicode(cur_inst),
                        unicode(present_dev),
                    )
                )
        # check for device group
        if cur_inst.device_group.cluster_device_group and not cur_inst.is_meta_device:
            raise ValidationError("no devices allowed in cluster_device_group")


@receiver(signals.post_save, sender=device)
def device_post_save(sender, **kwargs):
    def _strip_metadevice_name(name):
        if name.startswith("METADEV_"):
            return name[8:]
        else:
            return name

    if "instance" in kwargs:
        _cur_inst = kwargs["instance"]
        if _cur_inst.bootserver_id:
            BootsettingsChanged.send(sender=_cur_inst, device=_cur_inst, cause="device_changed")
        if _cur_inst.is_meta_device:
            _stripped = _strip_metadevice_name(_cur_inst.name)
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
        # check for change in meta_device class
        if not _cur_inst.is_meta_device:
            _dcs = device.objects.filter(
                Q(device_group=_cur_inst.device_group) &
                Q(is_meta_device=False)
            ).values("device_class", "pk")
            _count_dict = {}
            for _dc in _dcs:
                _count_dict.setdefault(_dc["device_class"], []).append(_dc["pk"])
            if _count_dict:
                # get device_classes with highest count
                _max_count = max([len(_value) for _value in _count_dict.itervalues()])
                _possible_classes = [_key for _key, _value in _count_dict.iteritems() if len(_value) == _max_count]
                # get metadevice
                _md = _cur_inst.device_group.device
                if _md.device_class_id not in _possible_classes:
                    if _possible_classes[0] is not None:
                        _md.device_class = DeviceClass.objects.get(Q(pk=_possible_classes[0]))
                    _md.save(update_fields=["device_class"])


class DeviceScanLock(models.Model):
    """
    Improved device locking
    """
    # add locks
    idx = models.AutoField(primary_key=True)
    # link to device
    device = models.ForeignKey("device")
    # uniqe id
    uuid = models.TextField(default="", max_length=64)
    # description
    description = models.CharField(default="", max_length=255)
    # calling server and config
    server = models.ForeignKey("backbone.device", on_delete=CASCADE, related_name="device_lock")
    config = models.ForeignKey("backbone.config", on_delete=CASCADE, related_name="config_lock")
    # active, will be set to False after lock removal
    active = models.BooleanField(default=True)
    # run_time in milliseconds
    run_time = models.IntegerField(default=0)
    # creation date
    date = models.DateTimeField(auto_now_add=True)

    def close(self):
        _run_time = cluster_timezone.localize(datetime.datetime.now()) - cluster_timezone.normalize(self.date)
        _run_time = _run_time.microseconds / 1000 + 1000 * _run_time.seconds
        self.active = False
        self.run_time = _run_time
        self.save()
        # close current lock and return a list of (what, level) lines
        return [("closed {}".format(unicode(self)), logging_tools.LOG_LEVEL_OK)]

    def __unicode__(self):
        return u"DSL {}".format(self.uuid)


class DeviceBootHistory(models.Model):
    # new kernel and / or image changes are connected to the device via this structure
    # might be empty if we only boot
    idx = models.AutoField(primary_key=True)
    device = models.ForeignKey("device")
    date = models.DateTimeField(auto_now_add=True)


class DeviceClass(models.Model):
    idx = models.AutoField(primary_key=True)
    # matchcode
    name = models.CharField(max_length=64, default="", unique=True)
    # description
    description = models.CharField(default="", max_length=128)
    # optional limitations, should be some kind of json-encoded dict
    limitations = models.TextField(default="", null=True)
    # system class (not deletable)
    system_class = models.BooleanField(default=False)
    # default system class, for devices without valid system_class
    default_system_class = models.BooleanField(default=False)
    # create user (None for system classes)
    create_user = models.ForeignKey("backbone.user", null=True)
    date = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        if self.system_class:
            if self.default_system_class:
                _ci = "*SYS"
            else:
                _ci = "SYS"
        else:
            _ci = unicode(self.create_user)
        return u"DeviceClass '{}' ({})".format(
            self.name,
            _ci,
        )


class device_selection(object):
    def __init__(self, sel_str):
        parts = sel_str.split("__")
        self.idx = int(parts[1])
        self.sel_type = {"dev": "d", "devg": "g"}[parts[0]]


def _get_top_level_dtn():
    try:
        top_level_dn = domain_tree_node.objects.get(Q(depth=0))
    except domain_tree_node.DoesNotExist:
        top_level_dn = None
    return top_level_dn


class cd_connection(models.Model):
    # controlling_device connection
    idx = models.AutoField(primary_key=True)
    parent = models.ForeignKey("backbone.device", related_name="parent_device")
    child = models.ForeignKey("backbone.device", related_name="child_device")
    created_by = models.ForeignKey("user", null=True)
    connection_info = models.CharField(max_length=256, default="not set")
    parameter_i1 = models.IntegerField(default=0)
    parameter_i2 = models.IntegerField(default=0)
    parameter_i3 = models.IntegerField(default=0)
    parameter_i4 = models.IntegerField(default=0)
    date = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return u"{} (via {}) {}".format(
            unicode(self.parent),
            self.connection_info,
            unicode(self.child)
        )

    class Meta:
        ordering = ("parent__name", "child__name",)
        verbose_name = "Controlling device connection"


@receiver(signals.pre_save, sender=cd_connection)
def cd_connection_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        for par_idx in xrange(1, 5):
            check_integer(cur_inst, "parameter_i{:d}".format(par_idx), min_val=0, max_val=256)
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
    # will be copied to comment of meta-device
    description = models.CharField(max_length=384, default="", blank=True)
    # device = models.ForeignKey("device", null=True, blank=True, related_name="group_device")
    # must be an IntegerField, otherwise we have a cycle reference
    # device = models.IntegerField(null=True, blank=True)
    device = models.ForeignKey("device", db_column="device", null=True, blank=True, related_name="group_device")
    # flag
    cluster_device_group = models.BooleanField(default=False)
    # enabled flag, ident to the enabled flag of the corresponding meta-device
    enabled = models.BooleanField(default=True)
    # domain tree node, used as default value for new devices
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

    # not really needed
    # @property
    # def full_name(self):
    #    if not self.domain_tree_node_id:
    #        self.domain_tree_node = domain_tree_node.objects.get(Q(depth=0))
    #        self.save()
    #    if self.domain_tree_node.full_name:
    #        return ".".join([self.name, self.domain_tree_node.full_name])
    #    else:
    #        return self.name

    class Meta:
        db_table = u'device_group'
        ordering = ("-cluster_device_group", "name",)
        verbose_name = u"Device group"

    class CSW_Meta:
        permissions = (
            # also referenced in migration 0983
            ("access_device_group", "Access to Device Group", True),
        )

    def __unicode__(self):
        return u"{}{}{}".format(
            self.name,
            " ({})".format(self.description) if self.description else "",
            "[*]" if self.cluster_device_group else ""
        )


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
                if cur_inst.device.comment != cur_inst.description:
                    cur_inst.device.comment = cur_inst.description
                    save_meta = True
            if save_meta:
                cur_inst.device.save()
        if cur_inst.cluster_device_group and not cur_inst.enabled:
            # always enable cluster device group
            cur_inst.enabled = True
            cur_inst.save()


class LogLevel(models.Model):
    idx = models.AutoField(primary_key=True)
    identifier = models.CharField(max_length=2, unique=True)
    level = models.IntegerField(default=logging_tools.LOG_LEVEL_OK)
    name = models.CharField(max_length=32, unique=True)
    date = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return "{} ({:d})".format(self.name, self.level)


@lru_cache()
def log_level_lookup(key):
    if isinstance(key, basestring):
        return LogLevel.objects.get(Q(identifier=key))
    else:
        return LogLevel.objects.get(Q(level=key))


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
            print(
                "Too many LogSources present for identifier '{}': {}, exiting".format(
                    identifier,
                    ", ".join([unicode(_src) for _src in sources])
                )
            )
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
def log_source_lookup(identifier, device=None):
    if type(identifier) in [int, long]:
        return LogSource.objects.get(Q(pk=identifier))
    elif device is not None:
        return LogSource.objects.get(Q(identifier=identifier) & Q(device=device))
    else:
        return LogSource.objects.get(Q(identifier=identifier))


class DeviceLogEntry(models.Model):
    idx = models.AutoField(primary_key=True)
    device = models.ForeignKey("device")
    # link to source, required
    source = models.ForeignKey("LogSource")
    # link to user or None
    user = models.ForeignKey("user", null=True)
    level = models.ForeignKey("LogLevel")
    text = models.CharField(max_length=765, default="")
    date = models.DateTimeField(auto_now_add=True) #

    @staticmethod
    def new(**kwargs):
        _dev = kwargs.get("device")
        if not _dev:
            _dev = device.objects.get(Q(device_group__cluster_device_group=True))

        # must be a valid user object
        _user = kwargs.get("user", None)
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
