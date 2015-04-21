# from lxml.builder import E  # @UnresolvedImport
from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, signals
from django.dispatch import receiver
from initat.tools import ipvx_tools
import logging
from initat.tools import logging_tools
from initat.tools import process_tools
import re

__all__ = [
    "network",
    "network_type",
    "net_ip",
    "network_device_type",
    "netdevice",
    "netdevice_speed",
    "peer_information",
    "snmp_network_type",
]

logger = logging.getLogger(__name__)


class network_device_type(models.Model):
    idx = models.AutoField(db_column="network_device_type_idx", primary_key=True)
    identifier = models.CharField(unique=True, max_length=48, blank=False)
    name_re = models.CharField(max_length=128, default="^.*$")
    description = models.CharField(max_length=192)
    mac_bytes = models.PositiveIntegerField(default=6)
    allow_virtual_interfaces = models.BooleanField(default=True)
    # used for matching ?
    for_matching = models.BooleanField(default=True)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = u'network_device_type'
        app_label = "backbone"


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

    class Meta:
        db_table = u'network_type'
        app_label = "backbone"


class network(models.Model):
    idx = models.AutoField(db_column="network_idx", primary_key=True)
    identifier = models.CharField(unique=True, max_length=255, blank=False)
    network_type = models.ForeignKey("network_type")
    master_network = models.ForeignKey("backbone.network", null=True, related_name="rel_master_network", blank=True)
    # should no longer be used, now in domain_tree_node
    short_names = models.BooleanField(default=True)
    # should no longer be used, now in domain_tree_node
    name = models.CharField(max_length=192, blank=True, default="")
    penalty = models.PositiveIntegerField(default=1, verbose_name="cost")
    # should no longer be used, now in domain_tree_node
    postfix = models.CharField(max_length=12, blank=True, default="")
    info = models.CharField(max_length=255, blank=True)
    network = models.GenericIPAddressField(blank=False)
    netmask = models.GenericIPAddressField(blank=False)
    broadcast = models.GenericIPAddressField(blank=False)
    gateway = models.GenericIPAddressField(blank=False)
    gw_pri = models.IntegerField(null=True, blank=True, default=1)
    # should no longer be used, now in domain_tree_node
    write_bind_config = models.BooleanField(default=False)
    # should no longer be used, now in domain_tree_node
    write_other_network_config = models.BooleanField(default=False)
    start_range = models.GenericIPAddressField(default="0.0.0.0")
    end_range = models.GenericIPAddressField(default="0.0.0.0")
    date = models.DateTimeField(auto_now_add=True)
    network_device_type = models.ManyToManyField("backbone.network_device_type")
    enforce_unique_ips = models.BooleanField(default=False)

    class Meta:
        db_table = u'network'
        app_label = "backbone"


class net_ip(models.Model):
    idx = models.AutoField(db_column="netip_idx", primary_key=True)
    ip = models.CharField(max_length=48)
    network = models.ForeignKey("backbone.network")
    netdevice = models.ForeignKey("backbone.netdevice")
    penalty = models.IntegerField(default=0, verbose_name="cost")
    alias = models.CharField(max_length=765, blank=True, default="")
    alias_excl = models.NullBooleanField(null=True, blank=True, default=False)
    domain_tree_node = models.ForeignKey("backbone.domain_tree_node", null=True, default=None)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = u"netip"
        app_label = "backbone"


class netdevice(models.Model):
    idx = models.AutoField(db_column="netdevice_idx", primary_key=True)
    device = models.ForeignKey("backbone.device")
    devname = models.CharField(max_length=64)
    macaddr = models.CharField(db_column="macadr", max_length=177, blank=True, default="")
    driver_options = models.CharField(max_length=672, blank=True)
    speed = models.IntegerField(default=0, null=True, blank=True)
    netdevice_speed = models.ForeignKey("backbone.netdevice_speed")
    driver = models.CharField(max_length=384, blank=True, default="e1000e")
    # is a valid routing target
    routing = models.BooleanField(default=False)
    # inter-device routing enabled
    inter_device_routing = models.BooleanField(default=True)
    penalty = models.IntegerField(null=True, blank=True, default=1, verbose_name="cost")
    dhcp_device = models.NullBooleanField(null=True, blank=True, default=False)
    ethtool_options = models.IntegerField(null=True, blank=True, default=0)
    fake_macaddr = models.CharField(db_column="fake_macadr", max_length=177, blank=True, default="")
    network_device_type = models.ForeignKey("backbone.network_device_type")
    description = models.CharField(max_length=765, blank=True)
    is_bridge = models.BooleanField(default=False)
    bridge_device = models.ForeignKey("self", null=True, related_name="bridge_slaves", blank=True)
    bridge_name = models.CharField(max_length=765, blank=True)
    vlan_id = models.IntegerField(null=True, blank=True, default=0)
    # for VLAN devices
    master_device = models.ForeignKey("self", null=True, related_name="vlan_slaves", blank=True)
    # enabled for monitoring
    enabled = models.BooleanField(default=True)
    date = models.DateTimeField(auto_now_add=True)
    # maximum transfer unit
    mtu = models.IntegerField(default=1500)
    # snmp related fields, zero for non-SNMP fetched network devices
    snmp_idx = models.IntegerField(default=0)
    # force matching th network device types, defaults to True
    # also affects MAC-address matching
    force_network_device_type_match = models.BooleanField(default=True)
    # snmp network type
    snmp_network_type = models.ForeignKey("backbone.snmp_network_type", null=True, blank=True)
    # admin / oper stats
    snmp_admin_status = models.IntegerField(default=0)
    snmp_oper_status = models.IntegerField(default=0)

    class Meta:
        db_table = u'netdevice'
        ordering = ("snmp_idx", "devname",)
        app_label = "backbone"

    def delete(self, *args, **kwargs):
        super(netdevice, self).delete(*args, **kwargs)


class netdevice_speed(models.Model):
    idx = models.AutoField(db_column="netdevice_speed_idx", primary_key=True)
    speed_bps = models.BigIntegerField(null=True, blank=True)
    check_via_ethtool = models.BooleanField(default=True)
    full_duplex = models.BooleanField(default=True)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = u'netdevice_speed'
        ordering = ("speed_bps", "full_duplex")
        app_label = "backbone"


class peer_information(models.Model):
    idx = models.AutoField(db_column="peer_information_idx", primary_key=True)
    s_netdevice = models.ForeignKey("backbone.netdevice", related_name="peer_s_netdevice")
    s_spec = models.CharField(default="", max_length=128, verbose_name="source spec", blank=True)
    d_netdevice = models.ForeignKey("backbone.netdevice", related_name="peer_d_netdevice")
    d_spec = models.CharField(default="", max_length=128, verbose_name="dest spec", blank=True)
    penalty = models.IntegerField(default=0, verbose_name="cost")
    # true for peers created via SNMP
    autocreated = models.BooleanField(default=False)
    info = models.CharField(default="", max_length=256, blank=True)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = u'peer_information'
        app_label = "backbone"


class snmp_network_type(models.Model):
    idx = models.AutoField(primary_key=True)
    if_type = models.IntegerField(default=0)
    if_label = models.CharField(max_length=128, default="")
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "backbone"
