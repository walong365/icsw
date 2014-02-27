#!/usr/bin/python-init -Otu

import factory
from initat.cluster.backbone.models import netdevice_speed, log_source, \
    device_type, partition_fs, log_status, hw_entry_type, status, network_device_type, \
    network_type, host_check_command

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
