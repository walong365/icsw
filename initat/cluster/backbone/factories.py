#!/usr/bin/python-init -Otu

import factory
from initat.cluster.backbone.models import netdevice_speed, LogLevel, \
    device_type, partition_fs, status, network_device_type, \
    network_type, host_check_command, config, mon_check_command, device_group, \
    device, mon_period, mon_service_templ, mon_device_templ, user, group, mon_contact, \
    network, netdevice, net_ip, device_config, cluster_license, LogSource, \
    config_hint, config_var_hint, config_script_hint, device_variable, virtual_desktop_protocol, \
    window_manager, snmp_network_type, snmp_scheme, snmp_scheme_vendor, snmp_scheme_tl_oid


class Device(factory.django.DjangoModelFactory):
    class Meta:
        model = device
        django_get_or_create = ("name",)


class DeviceGroup(factory.django.DjangoModelFactory):
    class Meta:
        model = device_group
        django_get_or_create = ("name",)


class NetDeviceSpeed(factory.django.DjangoModelFactory):
    class Meta:
        model = netdevice_speed
        django_get_or_create = ("speed_bps", "check_via_ethtool", "full_duplex",)


class LogSourceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = LogSource
        django_get_or_create = ("identifier", "device")


class LogLevelFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = LogLevel
        django_get_or_create = ("identifier",)


class DeviceType(factory.django.DjangoModelFactory):
    class Meta:
        model = device_type
        django_get_or_create = ("identifier",)
    priority = 0

    @factory.post_generation
    def priority(self, create, extracted, **kwargs):
        if self.priority != extracted:
            self.priority = extracted
            self.save()


class PartitionFS(factory.django.DjangoModelFactory):
    class Meta:
        model = partition_fs
        django_get_or_create = ("name", "identifier",)
    kernel_module = ""

    @factory.post_generation
    def kernel_module(self, create, extracted, **kwargs):
        if extracted is None:
            extracted = ""
        if self.kernel_module != extracted:
            self.kernel_module = extracted
            self.save()

    @factory.post_generation
    def hexid(self, create, extracted, **kwargs):
        if self.hexid != extracted:
            self.hexid = extracted
            self.save()


class Status(factory.django.DjangoModelFactory):
    class Meta:
        model = status
        django_get_or_create = ("status",)
    memory_test = False
    prod_link = False
    boot_local = False
    do_install = False
    is_clean = False
    allow_boolean_modify = False


class NetworkDeviceType(factory.django.DjangoModelFactory):
    class Meta:
        model = network_device_type
        django_get_or_create = ("identifier",)


class NetworkType(factory.django.DjangoModelFactory):
    class Meta:
        model = network_type
        django_get_or_create = ("identifier",)


class HostCheckCommand(factory.django.DjangoModelFactory):
    class Meta:
        model = host_check_command
        django_get_or_create = ("name",)


class Config(factory.django.DjangoModelFactory):
    class Meta:
        model = config
        django_get_or_create = ("name",)

    @factory.post_generation
    def description(self, create, extracted, **kwargs):
        extracted = extracted or ""
        if not self.description:
            self.description = extracted
            self.save()

    @factory.post_generation
    def server_config(self, create, extracted, **kwargs):
        extracted = extracted or False
        if self.server_config != extracted:
            self.server_config = extracted
            self.save()

    @factory.post_generation
    def system_config(self, create, extracted, **kwargs):
        extracted = extracted or False
        if self.system_config != extracted:
            self.system_config = extracted
            self.save()


class MonCheckCommand(factory.django.DjangoModelFactory):
    class Meta:
        model = mon_check_command
        django_get_or_create = ("name",)


class MonPeriod(factory.django.DjangoModelFactory):
    class Meta:
        model = mon_period
        django_get_or_create = ("name",)


class MonServiceTempl(factory.django.DjangoModelFactory):
    class Meta:
        model = mon_service_templ
        django_get_or_create = ("name",)


class MonDeviceTempl(factory.django.DjangoModelFactory):
    class Meta:
        model = mon_device_templ
        django_get_or_create = ("name",)


class User(factory.django.DjangoModelFactory):
    class Meta:
        model = user
        django_get_or_create = ("login",)


class Group(factory.django.DjangoModelFactory):
    class Meta:
        model = group
        django_get_or_create = ("groupname",)


class MonContact(factory.django.DjangoModelFactory):
    class Meta:
        model = mon_contact
        django_get_or_create = ("user",)


class Network(factory.django.DjangoModelFactory):
    class Meta:
        model = network
        django_get_or_create = ("identifier",)


class NetDevice(factory.django.DjangoModelFactory):
    class Meta:
        model = netdevice
        django_get_or_create = ("device", "devname",)


class NetIp(factory.django.DjangoModelFactory):
    class Meta:
        model = net_ip
        django_get_or_create = ("ip", "network",)


class DeviceConfig(factory.django.DjangoModelFactory):
    class Meta:
        model = device_config
        django_get_or_create = ("device", "config",)


class ClusterLicense(factory.django.DjangoModelFactory):
    class Meta:
        model = cluster_license
        django_get_or_create = ("name",)


class ConfigHint(factory.django.DjangoModelFactory):
    class Meta:
        model = config_hint
        django_get_or_create = ("config_name",)
    help_text_short = ""
    help_text_html = ""
    config_description = ""
    valid_for_meta = False
    exact_match = True

    @factory.post_generation
    def help_text_short(self, create, extracted, **kwargs):
        if self.help_text_short != extracted:
            self.help_text_short = extracted
            self.save()

    @factory.post_generation
    def help_text_html(self, create, extracted, **kwargs):
        if self.help_text_html != extracted:
            self.help_text_html = extracted
            self.save()

    @factory.post_generation
    def config_description(self, create, extracted, **kwargs):
        extracted = extracted or ""
        if self.config_description != extracted:
            self.config_description = extracted
            self.save()

    @factory.post_generation
    def exact_match(self, create, extracted, **kwargs):
        extracted = True if extracted is None else extracted
        if self.exact_match != extracted:
            self.exact_match = extracted
            self.save()


class ConfigVarHint(factory.django.DjangoModelFactory):
    class Meta:
        model = config_var_hint
        django_get_or_create = ("var_name", "config_hint")
    help_text_short = ""
    help_text_html = ""
    ac_flag = False
    ac_description = ""
    ac_value = ""

    @factory.post_generation
    def help_text_short(self, create, extracted, **kwargs):
        extracted = extracted or ""
        if self.help_text_short != extracted:
            self.help_text_short = extracted
            self.save()

    @factory.post_generation
    def help_text_html(self, create, extracted, **kwargs):
        extracted = extracted or ""
        if self.help_text_html != extracted:
            self.help_text_html = extracted
            self.save()

    @factory.post_generation
    def ac_flag(self, create, extracted, **kwargs):
        extracted = extracted or False
        if self.ac_flag != extracted:
            self.ac_flag = extracted
            self.save()

    @factory.post_generation
    def ac_description(self, create, extracted, **kwargs):
        extracted = extracted or ""
        if self.ac_description != extracted:
            self.ac_description = extracted
            self.save()

    @factory.post_generation
    def ac_value(self, create, extracted, **kwargs):
        extracted = extracted or ""
        if self.ac_value != extracted:
            self.ac_value = extracted
            self.save()


class ConfigScriptHint(factory.django.DjangoModelFactory):
    class Meta:
        model = config_script_hint
        django_get_or_create = ("script_name", "config_hint")
    help_text_short = ""
    help_text_html = ""
    ac_flag = False
    ac_description = ""
    ac_value = ""

    @factory.post_generation
    def help_text_short(self, create, extracted, **kwargs):
        extracted = extracted or ""
        if self.help_text_short != extracted:
            self.help_text_short = extracted
            self.save()

    @factory.post_generation
    def help_text_html(self, create, extracted, **kwargs):
        extracted = extracted or ""
        if self.help_text_html != extracted:
            self.help_text_html = extracted
            self.save()

    @factory.post_generation
    def ac_flag(self, create, extracted, **kwargs):
        extracted = extracted or False
        if self.ac_flag != extracted:
            self.ac_flag = extracted
            self.save()

    @factory.post_generation
    def ac_description(self, create, extracted, **kwargs):
        extracted = extracted or ""
        if self.ac_description != extracted:
            self.ac_description = extracted
            self.save()

    @factory.post_generation
    def ac_value(self, create, extracted, **kwargs):
        extracted = extracted or ""
        if self.ac_value != extracted:
            self.ac_value = extracted
            self.save()


class DeviceVariable(factory.django.DjangoModelFactory):
    class Meta:
        model = device_variable
        django_get_or_create = ("name", "device")

    @factory.post_generation
    def local_copy_ok(self, create, extracted, **kwargs):
        extracted = extracted or False
        if self.local_copy_ok != extracted:
            self.local_copy_ok = extracted
            self.save()


class VirtualDesktopProtocol(factory.django.DjangoModelFactory):
    class Meta:
        model = virtual_desktop_protocol
        django_get_or_create = ("name",)


class WindowManager(factory.django.DjangoModelFactory):
    class Meta:
        model = window_manager
        django_get_or_create = ("name",)


class SNMPNetworkType(factory.django.DjangoModelFactory):
    class Meta:
        model = snmp_network_type
        django_get_or_create = ("if_type",)


def _check_boolean(obj, new_val, attr_name):
    if getattr(obj, attr_name) != new_val:
        setattr(obj, attr_name, new_val)
        obj.save()


class SNMPScheme(factory.django.DjangoModelFactory):
    class Meta:
        model = snmp_scheme
        django_get_or_create = ("name", "snmp_scheme_vendor", "version")

    @factory.post_generation
    def collect(self, create, extracted, **kwargs):
        _check_boolean(self, extracted or False, "collect")

    @factory.post_generation
    def initial(self, create, extracted, **kwargs):
        _check_boolean(self, extracted or False, "initial")

    @factory.post_generation
    def mon_check(self, create, extracted, **kwargs):
        _check_boolean(self, extracted or False, "mon_check")

    @factory.post_generation
    def description(self, create, extracted, **kwargs):
        extracted = extracted or ""
        if self.description != extracted:
            self.description = extracted
            self.save()

    @factory.post_generation
    def priority(self, create, extracted, **kwargs):
        extracted = extracted or 0
        if self.priority != extracted:
            self.priority = extracted
            self.save()


class SNMPSchemeTLOID(factory.django.DjangoModelFactory):
    class Meta:
        model = snmp_scheme_tl_oid
        django_get_or_create = ("oid", "snmp_scheme")

    @factory.post_generation
    def optional(self, create, extracted, **kwargs):
        extracted = extracted or False
        if self.optional != extracted:
            self.optional = extracted
            self.save()


class SNMPSchemeVendor(factory.django.DjangoModelFactory):
    class Meta:
        model = snmp_scheme_vendor
        django_get_or_create = ("name",)

    @factory.post_generation
    def company_info(self, create, extracted, **kwargs):
        extracted = extracted or ""
        if self.company_info != extracted:
            self.company_info = extracted
            self.save()
