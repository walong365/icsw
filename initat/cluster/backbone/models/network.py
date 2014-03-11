#!/usr/bin/python-init

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, signals, get_model
from django.dispatch import receiver
from initat.cluster.backbone.models.functions import _check_empty_string, \
    _check_integer
from lxml.builder import E # @UnresolvedImport
from rest_framework import serializers
import ipvx_tools
import logging
import logging_tools
import process_tools
import re

__all__ = [
    "network", "network_serializer",
    "network_type", "network_type_serializer",
    "net_ip", "net_ip_serializer",
    "network_device_type", "network_device_type_serializer",
    "netdevice", "netdevice_serializer",
    "netdevice_speed", "netdevice_speed_serializer",
    "peer_information", "peer_information_serializer",
    ]

logger = logging.getLogger(__name__)

class network_device_type(models.Model):
    idx = models.AutoField(db_column="network_device_type_idx", primary_key=True)
    identifier = models.CharField(unique=True, max_length=48, blank=False)
    name_re = models.CharField(max_length=128, default="^.*$")
    description = models.CharField(max_length=192)
    mac_bytes = models.PositiveIntegerField(default=6)
    allow_virtual_interfaces = models.BooleanField(default=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'network_device_type'
        app_label = "backbone"
    def match(self, devname):
        if self.allow_virtual_interfaces and devname.count(":") == 1:
            _m_name = devname.split(":")[0]
        else:
            _m_name = devname
        return re.match(self.name_re, _m_name)
    def info_string(self):
        return unicode(self)
    def __unicode__(self):
        return u"%s (%s [%d])" % (
            self.identifier,
            self.description,
            self.mac_bytes)

@receiver(signals.post_init, sender=network_device_type)
def network_device_type_post_init(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        # print "*" * 20, cur_inst.identifier, cur_inst.pk, "+" * 20
        if cur_inst.name_re == "^.*$" and cur_inst.pk:
            if cur_inst.identifier in ["lo"]:
                cur_inst.name_re = "^%s$" % (cur_inst.identifier)
            else:
                cur_inst.name_re = "^%s\d+$" % (cur_inst.identifier)
            cur_inst.save()

@receiver(signals.pre_save, sender=network_device_type)
def network_device_type_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        if not(cur_inst.identifier.strip()):
            raise ValidationError("identifer must not be empty")
        if not re.match("^[a-zA-Z0-9]+$", cur_inst.identifier):
            raise ValidationError("identifier '%s' contains illegal characters" % (cur_inst.identifier))
        if not cur_inst.name_re.startswith("^"):
            cur_inst.name_re = "^%s" % (cur_inst.name_re)
        if not cur_inst.name_re.endswith("$"):
            cur_inst.name_re = "%s$" % (cur_inst.name_re)
        try:
            _cur_re = re.compile(cur_inst.name_re)
        except:
            raise ValidationError("invalid re '%s': %s" % (cur_inst.name_re, process_tools.get_except_info()))
        _check_integer(cur_inst, "mac_bytes", min_val=6, max_val=24)

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
    def __unicode__(self):
        return u"%s (%s)" % (self.description,
                             self.identifier)

class network(models.Model):
    idx = models.AutoField(db_column="network_idx", primary_key=True)
    identifier = models.CharField(unique=True, max_length=255, blank=False)
    network_type = models.ForeignKey("network_type")
    master_network = models.ForeignKey("backbone.network", null=True, related_name="rel_master_network", blank=True)
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
    network_device_type = models.ManyToManyField("backbone.network_device_type")
    enforce_unique_ips = models.BooleanField(default=False)
    class CSW_Meta:
        permissions = (
            ("modify_network", "modify global network settings", False),
        )
    def get_identifier(self):
        return self.network_type.identifier
    class Meta:
        db_table = u'network'
        app_label = "backbone"
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
    def info_string(self):
        return unicode(self)
    def __unicode__(self):
        return u"%s (%s/%s, %s)" % (
            self.identifier,
            self.network,
            self.netmask,
            self.network_type.identifier
        )

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
            print cur_inst.pk, cur_inst.master_network_id
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

class net_ip(models.Model):
    idx = models.AutoField(db_column="netip_idx", primary_key=True)
    ip = models.CharField(max_length=48)
    network = models.ForeignKey("backbone.network")
    netdevice = models.ForeignKey("backbone.netdevice")
    penalty = models.IntegerField(default=0)
    alias = models.CharField(max_length=765, blank=True, default="")
    alias_excl = models.NullBooleanField(null=True, blank=True, default=False)
    domain_tree_node = models.ForeignKey("backbone.domain_tree_node", null=True, default=None)
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
    def __unicode__(self):
        return self.ip
    @property
    def full_name(self):
        if not self.domain_tree_node_id:
            self.domain_tree_node = get_model("backbone", "domain_tree_node").objects.get(Q(depth=0))
            self.save()
        if self.domain_tree_node.full_name:
            return ".".join([self.netdevice.device.name, self.domain_tree_node.full_name])
        else:
            return self.netdevice.device.name
        return
    class Meta:
        db_table = u"netip"
        app_label = "backbone"

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
            raise ValidationError("no matching network found for '%s'" % (cur_inst.ip))
        if not ipv_addr.network_matches(cur_inst.network):
            match_list = ipv_addr.find_matching_network(network.objects.all())
            if match_list:
                cur_inst.network = match_list[0][1]
            else:
                raise ValidationError("no maching network found for '%s'" % (cur_inst.ip))
        dev_ips = net_ip.objects.exclude(Q(pk=cur_inst.pk)).filter(Q(netdevice__device=cur_inst.netdevice.device)).values_list("ip", flat=True)
        if cur_inst.ip in dev_ips:
            raise ValidationError("Address already %s used, device %s" % (cur_inst.ip, unicode(cur_inst.netdevice.device)))
        if cur_inst.network.enforce_unique_ips:
            try:
                present_ip = net_ip.objects.exclude(Q(pk=cur_inst.pk)).get(Q(network=cur_inst.network) & Q(ip=cur_inst.ip))
            except net_ip.DoesNotExist:
                pass
            except net_ip.MultipleObjectsReturned:
                raise ValidationError("IP already used more than once in network (force_unique_ips == True)")
            else:
                raise ValidationError("IP already used for %s (enforce_unique_ips == True)" % (unicode(present_ip.netdevice.device)))

@receiver(signals.pre_delete, sender=net_ip)
def net_ip_pre_delete(sender, **kwargs):
    cur_inst = kwargs["instance"]
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        if cur_inst.network.network_type.identifier == "b":
            cur_dev = cur_inst.netdevice.device
            if cur_inst.netdevice == cur_dev.bootnetdevice:
                # remove bootnetdevice
                cur_dev.bootnetdevice = None
                cur_dev.save()

@receiver(signals.post_save, sender=net_ip)
def net_ip_post_save(sender, **kwargs):
    cur_inst = kwargs["instance"]
    if kwargs["created"] and not kwargs["raw"] and "instance" in kwargs:
        cur_inst = kwargs["instance"]
        if cur_inst.ip == "127.0.0.1" and kwargs["created"] and not cur_inst.alias.strip():
            cur_inst.alias = "localhost"
            cur_inst.alias_excl = True
            cur_inst.save()
    if not kwargs["raw"]:
        if cur_inst.network.network_type.identifier == "b":
            # check for single boot IP
            num_boot_ips = net_ip.objects.filter(Q(network__network_type__identifier="b") & Q(netdevice__device=cur_inst.netdevice.device)).count()
            # set boot netdevice
            cur_inst.netdevice.device.bootnetdevice = cur_inst.netdevice
            cur_inst.netdevice.device.save()
            if num_boot_ips > 1:
                raise ValidationError("too many IP-adresses in a boot network defined")

class network_device_type_serializer(serializers.ModelSerializer):
    info_string = serializers.Field(source="info_string")
    class Meta:
        model = network_device_type

class network_type_serializer(serializers.ModelSerializer):
    class Meta:
        model = network_type

class network_serializer(serializers.ModelSerializer):
    info_string = serializers.Field(source="info_string")
    network_type_identifier = serializers.Field(source="get_identifier")
    class Meta:
        model = network

class net_ip_serializer(serializers.ModelSerializer):
    # network = network_serializer()
    class Meta:
        model = net_ip

class netdevice(models.Model):
    idx = models.AutoField(db_column="netdevice_idx", primary_key=True)
    device = models.ForeignKey("backbone.device")
    devname = models.CharField(max_length=36)
    macaddr = models.CharField(db_column="macadr", max_length=177, blank=True)
    driver_options = models.CharField(max_length=672, blank=True)
    speed = models.IntegerField(default=0, null=True, blank=True)
    netdevice_speed = models.ForeignKey("backbone.netdevice_speed")
    driver = models.CharField(max_length=384, blank=True, default="e1000e")
    routing = models.BooleanField(default=False)
    penalty = models.IntegerField(null=True, blank=True, default=1)
    dhcp_device = models.NullBooleanField(null=True, blank=True, default=False)
    ethtool_options = models.IntegerField(null=True, blank=True, default=0)
    fake_macaddr = models.CharField(db_column="fake_macadr", max_length=177, blank=True)
    network_device_type = models.ForeignKey("backbone.network_device_type")
    description = models.CharField(max_length=765, blank=True)
    is_bridge = models.BooleanField(default=False)
    bridge_name = models.CharField(max_length=765, blank=True)
    vlan_id = models.IntegerField(null=True, blank=True, default=0)
    # for VLAN devices
    master_device = models.ForeignKey("self", null=True, related_name="vlan_slaves", blank=True)
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
        match_list = [ndt for ndt in network_device_type.objects.all() if ndt.match(self.devname)]
        if len(match_list) == 0:
            return None
        elif len(match_list) == 1:
            return match_list[0]
        else:
            # take ndt with shortest name_re
            return sorted([(len(ndt.name_re), ndt) for ndt in match_list])[0][1]
    def get_dummy_macaddr(self):
        return ":".join(["00"] * self.network_device_type.mac_bytes)
    class Meta:
        db_table = u'netdevice'
        ordering = ("devname",)
        app_label = "backbone"
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

@receiver(signals.pre_delete, sender=netdevice)
def netdevice_pre_delete(sender, **kwargs):
    # too late here, handled by delete_netdevice in network_views
    pass
    # if "instance" in kwargs:
        # cur_inst = kwargs["instance"]
        # for cur_dev in device.objects.filter(Q(bootnetdevice=cur_inst.pk)):
            # cur_dev.bootnetdevice = None
            # cur_dev.save(update_fields=["bootnetdevice"])

class netdevice_serializer(serializers.ModelSerializer):
    net_ip_set = net_ip_serializer(many=True)
    ethtool_autoneg = serializers.Field(source="ethtool_autoneg")
    ethtool_duplex = serializers.Field(source="ethtool_duplex")
    ethtool_speed = serializers.Field(source="ethtool_speed")
    class Meta:
        model = netdevice

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
            raise ValidationError("no matching device_type found for '%s' (%s)" % (unicode(cur_inst), cur_inst.pk))
        cur_inst.network_device_type = nd_type
        # fix None as vlan_id
        _check_integer(cur_inst, "vlan_id", none_to_zero=True, min_val=0)
        # penalty
        _check_integer(cur_inst, "penalty", min_val=1)
        # check mac address
        if cur_inst.macaddr:
            cur_inst.macaddr = cur_inst.macaddr.replace("-", ":").lower()
        if cur_inst.fake_macaddr:
            cur_inst.fake_macaddr = cur_inst.fake_macaddr.replace("-", ":").lower()
        dummy_mac, mac_re = (":".join(["00"] * cur_inst.network_device_type.mac_bytes),
                             re.compile("^%s$" % (":".join(["[0-9a-f]{2}"] * cur_inst.network_device_type.mac_bytes))))
        # set empty if not set
        try:
            if not cur_inst.macaddr.strip() or int(cur_inst.macaddr.replace(":", ""), 16) == 0:
                cur_inst.macaddr = dummy_mac
        except:
            raise ValidationError("MACaddress '%s' has illegal format" % (cur_inst.macaddr))
        # set empty if not set
        try:
            if not cur_inst.fake_macaddr.strip() or int(cur_inst.fake_macaddr.replace(":", ""), 16) == 0:
                cur_inst.fake_macaddr = dummy_mac
        except:
            raise ValidationError("fake MACaddress '%s' has illegal format" % (cur_inst.fake_macaddr))
        if not mac_re.match(cur_inst.macaddr):
            raise ValidationError("MACaddress '%s' has illegal format" % (cur_inst.macaddr))
        if not mac_re.match(cur_inst.fake_macaddr):
            raise ValidationError("fake MACaddress has illegal format" % (cur_inst.fake_macaddr))
        if cur_inst.master_device_id:
            if not cur_inst.vlan_id:
                raise ValidationError("VLAN id cannot be zero")
            if cur_inst.master_device_id == cur_inst.pk:
                raise ValidationError("cannot be my own VLAN master")
            if cur_inst.master_device.master_device_id:
                raise ValidationError("cannot chain VLAN devices")
        if cur_inst.vlan_id and not cur_inst.master_device_id:
            raise ValidationError("need a VLAN master")

@receiver(signals.post_save, sender=netdevice)
def netdevice_post_save(sender, **kwargs):
    if "instance" in kwargs:
        _cur_inst = kwargs["instance"]

@receiver(signals.post_delete, sender=netdevice)
def netdevice_post_delete(sender, **kwargs):
    if "instance" in kwargs:
        _cur_inst = kwargs["instance"]

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
    def info_string(self):
        return unicode(self)
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

class netdevice_speed_serializer(serializers.ModelSerializer):
    info_string = serializers.Field(source="info_string")
    class Meta:
        model = netdevice_speed

@receiver(signals.pre_save, sender=network_type)
def network_type_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        # raise ValidationError("test validation error")
        if not(cur_inst.identifier.strip()):
            raise ValidationError("identifer must not be empty")

class peer_information(models.Model):
    idx = models.AutoField(db_column="peer_information_idx", primary_key=True)
    s_netdevice = models.ForeignKey("backbone.netdevice", related_name="peer_s_netdevice")
    d_netdevice = models.ForeignKey("backbone.netdevice", related_name="peer_d_netdevice")
    penalty = models.IntegerField(default=0)
    date = models.DateTimeField(auto_now_add=True)
    def __unicode__(self):
        return u"%s [%d] %s" % (self.s_netdevice.devname, self.penalty, self.d_netdevice.devname)
    class Meta:
        db_table = u'peer_information'
        app_label = "backbone"

class peer_information_serializer(serializers.ModelSerializer):
    class Meta:
        model = peer_information

@receiver(signals.pre_save, sender=peer_information)
def peer_information_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        try:
            _cur_peer = peer_information.objects.get(
                (Q(s_netdevice=cur_inst.s_netdevice_id) & Q(d_netdevice=cur_inst.d_netdevice_id)) |
                (Q(s_netdevice=cur_inst.d_netdevice_id) & Q(d_netdevice=cur_inst.s_netdevice_id)))
        except peer_information.DoesNotExist:
            pass
        else:
            raise ValidationError("peer already exists")
        _check_integer(cur_inst, "penalty", min_val=1)

@receiver(signals.post_save, sender=peer_information)
def peer_information_post_save(sender, **kwargs):
    if not kwargs["raw"] and "instance" in kwargs:
        _cur_inst = kwargs["instance"]

@receiver(signals.post_delete, sender=peer_information)
def peer_information_post_delete(sender, **kwargs):
    if "instance" in kwargs:
        _cur_inst = kwargs["instance"]

