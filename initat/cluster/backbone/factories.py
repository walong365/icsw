#!/usr/bin/python-init -Otu

import factory
from initat.cluster.backbone.models import netdevice_speed, log_source, \
    device_type, partition_fs, log_status, hw_entry_type, status, network_device_type, \
    network_type, host_check_command, config, mon_check_command, device_group, \
    device, mon_period, mon_service_templ, mon_device_templ, user, group, mon_contact, \
    network, netdevice, net_ip, device_config, cluster_license, cluster_setting, \
    config_hint, config_var_hint

class Device(factory.django.DjangoModelFactory):
    FACTORY_FOR = device
    FACTORY_DJANGO_GET_OR_CREATE = ("name",)

class DeviceGroup(factory.django.DjangoModelFactory):
    FACTORY_FOR = device_group
    FACTORY_DJANGO_GET_OR_CREATE = ("name",)

class NetDeviceSpeed(factory.django.DjangoModelFactory):
    FACTORY_FOR = netdevice_speed
    FACTORY_DJANGO_GET_OR_CREATE = ("speed_bps", "check_via_ethtool", "full_duplex",)

class LogSource(factory.django.DjangoModelFactory):
    FACTORY_FOR = log_source
    FACTORY_DJANOG_GET_OR_CREATE = ("identifier",)

class DeviceType(factory.django.DjangoModelFactory):
    FACTORY_FOR = device_type
    FACTORY_DJANGO_GET_OR_CREATE = ("identifier",)
    priority = 0
    @factory.post_generation
    def priority(self, create, extracted, **kwargs):
        if self.priority != extracted:
            self.priority = extracted
            self.save()

class PartitionFS(factory.django.DjangoModelFactory):
    FACTORY_FOR = partition_fs
    FACTORY_DJANGO_GET_OR_CREATE = ("name", "identifier",)
    kernel_module = ""
    @factory.post_generation
    def kernel_module(self, create, extracted, **kwargs):
        if self.kernel_module != extracted:
            self.kernel_module = extracted
            self.save()

class LogStatus(factory.django.DjangoModelFactory):
    FACTORY_FOR = log_status
    FACTORY_DJANGO_GET_OR_CREATE = ("identifier", "log_level",)
    @factory.post_generation
    def name(self, create, extracted, **kwargs):
        if self.name != extracted:
            self.name = extracted
            self.save()

class HWEntryType(factory.django.DjangoModelFactory):
    FACTORY_FOR = hw_entry_type
    FACTORY_DJANGO_GET_OR_CREATE = ("identifier",)
    iarg0_descr = ""
    iarg1_descr = ""
    sarg0_descr = ""
    sarg1_descr = ""

class Status(factory.django.DjangoModelFactory):
    FACTORY_FOR = status
    FACTORY_DJANGO_GET_OR_CREATE = ("status",)
    memory_test = False
    prod_link = False
    boot_local = False
    do_install = False
    is_clean = False
    allow_boolean_modify = False

class NetworkDeviceType(factory.django.DjangoModelFactory):
    FACTORY_FOR = network_device_type
    FACTORY_DJANGO_GET_OR_CREATE = ("identifier",)

class NetworkType(factory.django.DjangoModelFactory):
    FACTORY_FOR = network_type
    FACTORY_DJANGO_GET_OR_CREATE = ("identifier",)

class HostCheckCommand(factory.django.DjangoModelFactory):
    FACTORY_FOR = host_check_command
    FACTORY_DJANGO_GET_OR_CREATE = ("name",)

class Config(factory.django.DjangoModelFactory):
    FACTORY_FOR = config
    FACTORY_DJANGO_GET_OR_CREATE = ("name",)

class MonCheckCommand(factory.django.DjangoModelFactory):
    FACTORY_FOR = mon_check_command
    FACTORY_DJANGO_GET_OR_CREATE = ("name",)

class MonPeriod(factory.django.DjangoModelFactory):
    FACTORY_FOR = mon_period
    FACTORY_DJANGO_GET_OR_CREATE = ("name",)

class MonServiceTempl(factory.django.DjangoModelFactory):
    FACTORY_FOR = mon_service_templ
    FACTORY_DJANGO_GET_OR_CREATE = ("name",)

class MonDeviceTempl(factory.django.DjangoModelFactory):
    FACTORY_FOR = mon_device_templ
    FACTORY_DJANGO_GET_OR_CREATE = ("name",)

class User(factory.django.DjangoModelFactory):
    FACTORY_FOR = user
    FACTORY_DJANGO_GET_OR_CREATE = ("login",)

class Group(factory.django.DjangoModelFactory):
    FACTORY_FOR = group
    FACTORY_DJANGO_GET_OR_CREATE = ("groupname",)

class MonContact(factory.django.DjangoModelFactory):
    FACTORY_FOR = mon_contact
    FACTORY_DJANGO_GET_OR_CREATE = ("user",)

class Network(factory.django.DjangoModelFactory):
    FACTORY_FOR = network
    FACTORY_DJANGO_GET_OR_CREATE = ("identifier",)

class NetDevice(factory.django.DjangoModelFactory):
    FACTORY_FOR = netdevice
    FACTORY_DJANGO_GET_OR_CREATE = ("device", "devname",)

class NetIp(factory.django.DjangoModelFactory):
    FACTORY_FOR = net_ip
    FACTORY_DJANGO_GET_OR_CREATE = ("ip", "network",)

class DeviceConfig(factory.django.DjangoModelFactory):
    FACTORY_FOR = device_config
    FACTORY_DJANGO_GET_OR_CREATE = ("device", "config",)

class ClusterSetting(factory.django.DjangoModelFactory):
    FACTORY_FOR = cluster_setting
    FACTORY_DJANGO_GET_OR_CREATE = ("name",)

class ClusterLicense(factory.django.DjangoModelFactory):
    FACTORY_FOR = cluster_license
    FACTORY_DJANGO_GET_OR_CREATE = ("cluster_setting", "name",)

class ConfigHint(factory.django.DjangoModelFactory):
    FACTORY_FOR = config_hint
    FACTORY_DJANGO_GET_OR_CREATE = ("config_name",)
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

class ConfigVarHint(factory.django.DjangoModelFactory):
    FACTORY_FOR = config_var_hint
    FACTORY_DJANGO_GET_OR_CREATE = ("var_name",)
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

