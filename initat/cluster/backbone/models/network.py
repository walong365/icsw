# from lxml.builder import E  # @UnresolvedImport
from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, signals
from django.dispatch import receiver
from initat.cluster.backbone.models.functions import _check_empty_string, \
    _check_integer
from initat.cluster.backbone.signals import bootsettings_changed
import ipvx_tools
import logging
import logging_tools
import process_tools
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

    def match(self, devname):
        if self.allow_virtual_interfaces and devname.count(":") == 1:
            _m_name = devname.split(":")[0]
        else:
            _m_name = devname
        return re.match(self.name_re, _m_name)

    def info_string(self):
        return unicode(self)

    def __unicode__(self):
        return u"{} ({} [{:d}])".format(
            self.identifier,
            self.description,
            self.mac_bytes)


@receiver(signals.post_init, sender=network_device_type)
def network_device_type_post_init(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        # print "*" * 20, cur_inst.identifier, cur_inst.pk, "+" * 20
        if cur_inst.name_re == "^.*$" and cur_inst.pk and not cur_inst.for_matching:
            if cur_inst.identifier in ["lo"]:
                cur_inst.name_re = "^{}$".format(cur_inst.identifier)
            else:
                cur_inst.name_re = "^{}\d+$".format(cur_inst.identifier)
            cur_inst.save()


@receiver(signals.pre_save, sender=network_device_type)
def network_device_type_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        if not(cur_inst.identifier.strip()):
            raise ValidationError("identifer must not be empty")
        if not re.match("^[a-zA-Z0-9]+$", cur_inst.identifier):
            raise ValidationError("identifier '{}' contains illegal characters".format(cur_inst.identifier))
        if not cur_inst.name_re.startswith("^"):
            cur_inst.name_re = "^{}".format(cur_inst.name_re)
        if not cur_inst.name_re.endswith("$"):
            cur_inst.name_re = "{}$".format(cur_inst.name_re)
        try:
            _cur_re = re.compile(cur_inst.name_re)
        except:
            raise ValidationError(
                "invalid re '{}': {}".format(
                    cur_inst.name_re,
                    process_tools.get_except_info()
                )
            )
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
        return u"{} ({})".format(
            self.description,
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

    class CSW_Meta:
        permissions = (
            ("modify_network", "modify global network settings", False),
            ("show_clusters", "show network clustering", False),
        )

    @staticmethod
    def get_unique_identifier():
        _all_ids = network.objects.all().values_list("identifier", flat=True)
        gen_idx = 1
        while True:
            if "autogen{:d}".format(gen_idx) not in _all_ids:
                break
            gen_idx += 1
        return "autogen{:d}".format(gen_idx)

    def get_identifier(self):
        return self.network_type.identifier

    def num_ip(self):
        return self.net_ip_set.all().count()

    class Meta:
        db_table = u'network'
        app_label = "backbone"

    def get_info(self):
        all_slaves = self.rel_master_network.all()
        # return extended info
        log_str = "{} network '{}' has {}{}".format(
            self.network_type.get_identifier_display(),
            self.identifier,
            logging_tools.get_plural("slave network", len(all_slaves)),
            ": {}".format([cur_slave.identifier for cur_slave in all_slaves]) if all_slaves else "",
        )
        return log_str

    def info_string(self):
        return unicode(self)

    def __unicode__(self):
        return u"{} ({}/{}, {})".format(
            self.identifier,
            self.network,
            ipvx_tools.get_network_name_from_mask(self.netmask),
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
        if cur_inst.rel_master_network.all().count() and nw_type != "p":
            raise ValidationError("slave networks exists, cannot change type")
        if nw_type != "s" and cur_inst.master_network_id:
            raise ValidationError("only slave networks can have a master")
        if nw_type == "s" and cur_inst.master_network_id:
            # print cur_inst.pk, cur_inst.master_network_id
            if cur_inst.master_network.network_type.identifier != "p":
                raise ValidationError("master network must be a production network")
        # validate IP
        ip_dict = dict([(key, None) for key in ["network", "netmask", "broadcast", "gateway"]])
        for key in ip_dict.keys():
            try:
                ip_dict[key] = ipvx_tools.ipv4(getattr(cur_inst, key))
            except:
                raise ValidationError("{} is not an IPv4 address".format(key))
        if not change_attr:
            change_attr = "network"
        if change_attr in ["network", "netmask"]:
            ip_dict["broadcast"] = ~ip_dict["netmask"] | (ip_dict["network"] & ip_dict["netmask"])
        elif change_attr == "broadcast":
            ip_dict["netmask"] = ~(ip_dict["broadcast"] & ~ip_dict["network"])
        elif change_attr == "gateway":
            # do nothing
            pass
        # check netmask
        _mask = 0
        any_match = False
        for _idx in xrange(32, -1, -1):
            if _mask == ip_dict["netmask"].value():
                any_match = True
                break
            _mask = _mask + 2 ** (_idx - 1)
        if not any_match:
            raise ValidationError("netmask is not valid")
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
    penalty = models.IntegerField(default=0, verbose_name="cost")
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
            self.domain_tree_node = apps.get_model("backbone", "domain_tree_node").objects.get(Q(depth=0))
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
            if getattr(cur_inst, "create_default_network", False):
                try:
                    default_nw = network.objects.get(Q(network="0.0.0.0"))
                except network.DoesNotExist:
                    default_nw = network.objects.create(
                        network="0.0.0.0",
                        netmask="0.0.0.0",
                        broadcast="255.255.255.255",
                        gateway="0.0.0.0",
                        identifier="all",
                        network_type=network_type.objects.get(Q(identifier="o"))
                    )
                cur_inst.network = default_nw
            else:
                raise ValidationError("no matching network found for '{}'".format(cur_inst.ip))
        if not ipv_addr.network_matches(cur_inst.network):
            match_list = ipv_addr.find_matching_network(network.objects.all())
            if match_list:
                cur_inst.network = match_list[0][1]
            else:
                raise ValidationError("no maching network found for '{}'".format(cur_inst.ip))
        dev_ips = net_ip.objects.exclude(Q(pk=cur_inst.pk)).filter(Q(netdevice__device=cur_inst.netdevice.device)).values_list("ip", flat=True)
        if cur_inst.ip in dev_ips:
            raise ValidationError("Address {} already used, device {}".format(cur_inst.ip, unicode(cur_inst.netdevice.device)))
        if cur_inst.network.enforce_unique_ips:
            try:
                present_ip = net_ip.objects.exclude(Q(pk=cur_inst.pk)).get(Q(network=cur_inst.network) & Q(ip=cur_inst.ip))
            except net_ip.DoesNotExist:
                pass
            except net_ip.MultipleObjectsReturned:
                raise ValidationError("IP already used more than once in network (force_unique_ips == True)")
            else:
                raise ValidationError("IP already used for {} (enforce_unique_ips == True)".format(unicode(present_ip.netdevice.device)))


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
                cur_dev.save(update_fields=["bootnetdevice"])


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
            if cur_inst.netdevice.device.bootserver_id:
                bootsettings_changed.send(sender=cur_inst, device=cur_inst.netdevice.device, cause="net_ip_changed")


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
    # enabled, in fact admin enabled
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

    def __init__(self, *args, **kwargs):
        models.Model.__init__(self, *args, **kwargs)
        self.saved_values = {
            "penalty": self.penalty,
            "routing": self.routing,
        }

    def copy(self):
        return netdevice(
            devname=self.devname,
            macaddr=self.get_dummy_macaddr(),
            driver_options=self.driver_options,
            inter_device_routing=self.inter_device_routing,
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
            enabled=self.enabled,
            mtu=self.mtu,
            force_network_device_type_match=self.force_network_device_type_match,
            snmp_network_type=self.snmp_network_type,
            snmp_admin_status=self.snmp_admin_status,
            snmp_oper_status=self.snmp_oper_status,
            # hm ...
            # bridge_device=self.bridge_device,
        )

    def find_matching_network_device_type(self):
        match_list = [ndt for ndt in network_device_type.objects.filter(Q(for_matching=True)) if ndt.match(self.devname)]
        if len(match_list) == 0:
            return None
        elif len(match_list) == 1:
            return match_list[0]
        else:
            # take ndt with shortest name_re
            return sorted([(len(ndt.name_re), ndt) for ndt in match_list])[0][1]

    def get_dummy_macaddr(self):
        return ":".join(["00"] * self.network_device_type.mac_bytes)

    class CSW_Meta:
        fk_ignore_list = ["net_ip", "peer_information"]

    class Meta:
        db_table = u'netdevice'
        ordering = ("devname",)
        app_label = "backbone"

    def delete(self, *args, **kwargs):
        super(netdevice, self).delete(*args, **kwargs)

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
    pass
    # if "instance" in kwargs:
    #    cur_inst = kwargs["instance"]
    #    for cur_dev in get_model("backbone", "device").objects.filter(Q(bootnetdevice=cur_inst.pk)):
    #        cur_dev.bootnetdevice = None
    #        cur_dev.save(update_fields=["bootnetdevice"])


@receiver(signals.pre_save, sender=netdevice)
def netdevice_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        if cur_inst.devname:
            cur_inst.devname = cur_inst.devname[:63]
        _check_empty_string(cur_inst, "devname")
        _check_integer(cur_inst, "mtu", min_val=0, max_val=65536)
        all_nd_names = netdevice.objects.exclude(Q(pk=cur_inst.pk)).filter(Q(device=cur_inst.device_id)).values_list("devname", flat=True)
        if cur_inst.devname in all_nd_names:
            raise ValidationError("devname '{}' already used".format(cur_inst.devname))
        # change network_device_type
        if cur_inst.force_network_device_type_match:
            nd_type = cur_inst.find_matching_network_device_type()
            if not nd_type:
                raise ValidationError("no matching device_type found for '{}' ({})".format(unicode(cur_inst), cur_inst.pk or "new nd"))
            cur_inst.network_device_type = nd_type
        else:
            if not cur_inst.network_device_type_id:
                # take the first one which is not used for matching
                cur_inst.network_device_type = network_device_type.objects.filter(Q(for_matching=False))[0]
        # fix None as vlan_id
        _check_integer(cur_inst, "vlan_id", none_to_zero=True, min_val=0)
        # penalty
        _check_integer(cur_inst, "penalty", min_val=1)
        # mac address matching (if needed)
        if cur_inst.force_network_device_type_match:
            # check mac address
            if cur_inst.macaddr:
                cur_inst.macaddr = cur_inst.macaddr.replace("-", ":").lower()
            if cur_inst.fake_macaddr:
                cur_inst.fake_macaddr = cur_inst.fake_macaddr.replace("-", ":").lower()
            dummy_mac, mac_re = (":".join(["00"] * cur_inst.network_device_type.mac_bytes),
                                 re.compile("^{}$".format(":".join(["[0-9a-f]{2}"] * cur_inst.network_device_type.mac_bytes))))
            # set empty if not set
            try:
                if not cur_inst.macaddr.strip() or int(cur_inst.macaddr.replace(":", ""), 16) == 0:
                    cur_inst.macaddr = dummy_mac
            except:
                raise ValidationError("MACaddress '{}' has illegal format".format(cur_inst.macaddr))
            # set empty if not set
            try:
                if not cur_inst.fake_macaddr.strip() or int(cur_inst.fake_macaddr.replace(":", ""), 16) == 0:
                    cur_inst.fake_macaddr = dummy_mac
            except:
                raise ValidationError("fake MACaddress '{}' has illegal format".format(cur_inst.fake_macaddr))
            if not mac_re.match(cur_inst.macaddr):
                raise ValidationError("MACaddress '{}' has illegal format".format(cur_inst.macaddr))
            if not mac_re.match(cur_inst.fake_macaddr):
                raise ValidationError("fake MACaddress '{}' has illegal format".format(cur_inst.fake_macaddr))
        if cur_inst.master_device_id:
            if not cur_inst.vlan_id:
                raise ValidationError("VLAN id cannot be zero")
            if cur_inst.master_device_id == cur_inst.pk:
                raise ValidationError("cannot be my own VLAN master")
            if cur_inst.master_device.master_device_id:
                raise ValidationError("cannot chain VLAN devices")

        if cur_inst.netdevice_speed_id is None:
            # set a default
            cur_inst.netdevice_speed = netdevice_speed.objects.get(Q(speed_bps=1000000000) & Q(full_duplex=True) & Q(check_via_ethtool=False))
        # if cur_inst.vlan_id and not cur_inst.master_device_id:
        #    raise ValidationError("need a VLAN master")


@receiver(signals.post_save, sender=netdevice)
def netdevice_post_save(sender, **kwargs):
    if "instance" in kwargs:
        _cur_inst = kwargs["instance"]
        if _cur_inst.device.bootserver_id:
            bootsettings_changed.send(sender=_cur_inst, device=_cur_inst.device, cause="netdevice_changed")


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
        if self.speed_bps:
            _s_str, lut_idx = ("", 0)
            cur_s = self.speed_bps
            while cur_s > 999:
                cur_s = cur_s / 1000
                lut_idx += 1
            _speed_str = "{}{}Bps".format(
                cur_s,
                " kMGT"[lut_idx].strip()
            )
        else:
            _speed_str = "unspec."
        return u"{}, {} duplex, {}".format(
            _speed_str,
            "full" if self.full_duplex else "half",
            "check via ethtool" if self.check_via_ethtool else "no check")


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
    s_spec = models.CharField(default="", max_length=128, verbose_name="source spec", blank=True)
    d_netdevice = models.ForeignKey("backbone.netdevice", related_name="peer_d_netdevice")
    d_spec = models.CharField(default="", max_length=128, verbose_name="dest spec", blank=True)
    penalty = models.IntegerField(default=0, verbose_name="cost")
    date = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return u"{} [{:d}] {}".format(
            self.s_netdevice.devname,
            self.penalty,
            self.d_netdevice.devname
        )

    class Meta:
        db_table = u'peer_information'
        app_label = "backbone"


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
            if _cur_peer.pk != cur_inst.pk:
                raise ValidationError("peer already exists ({:d}, {:d})".format(cur_inst.s_netdevice_d, cur_inst.d_netdevice_id))
        _check_integer(cur_inst, "penalty", min_val=1)


@receiver(signals.post_save, sender=peer_information)
def peer_information_post_save(sender, **kwargs):
    if not kwargs["raw"] and "instance" in kwargs:
        _cur_inst = kwargs["instance"]


@receiver(signals.post_delete, sender=peer_information)
def peer_information_post_delete(sender, **kwargs):
    if "instance" in kwargs:
        _cur_inst = kwargs["instance"]


class snmp_network_type(models.Model):
    idx = models.AutoField(primary_key=True)
    if_type = models.IntegerField(default=0)
    if_label = models.CharField(max_length=128, default="")
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "backbone"
