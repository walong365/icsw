# -*- coding: utf-8 -*-

import os
from unittest import TestCase as NoDBTestCase

from pynag import Model
from pynag.Model import (
    Timeperiod, Hostgroup, Host, Command, Contact, Contactgroup, Service
)

from factory import DjangoModelFactory

from django.test import TestCase

from initat.cluster.backbone.models import (
    device_type, device_group, network_type, network_device_type, netdevice_speed,
    config, device_config, mon_period, mon_contact, mon_contactgroup,
    mon_check_command, netdevice, peer_information
)
from initat.md_config_server.icinga_migration.utils import flags_to_dict
from initat.md_config_server.icinga_migration.transformations import (
    transform_timeperiod, transform_hostgroup, transform_host,
    transform_command, transform_contact, transform_contactgroup,
    transform_service, DEFAULT_TIME_RANGE, DEFAULT_CONTACT_GROUP_NAME,
    SINGLE_USER_GROUP_SUFFIX, CACHES,
)

from initat.md_config_server.icinga_migration.operations import (
    create_devices, create_peering_information, unify_templates,
)

TEST_CONFIG_DIR = os.path.join(
    os.path.dirname(__file__), "icinga_migration_test_configs"
)
TEST_CONFIG = os.path.join(TEST_CONFIG_DIR, "icinga.cfg")
Model.cfg_file = TEST_CONFIG


class DeviceTypeFactory(DjangoModelFactory):
    class Meta(object):
        model = device_type
        abstract = True
        django_get_or_create = ("identifier", )


class DeviceTypeMetaDeviceFactory(DeviceTypeFactory):
    description = "Meta Device"
    identifier = "MD"


class DeviceTypeHostFactory(DeviceTypeFactory):
    description = "Host"
    identifier = "H"


class DeviceGroupFactory(DjangoModelFactory):
    name = "some_device_group"

    class Meta(object):
        model = device_group


class NetworkTypeFactory(DjangoModelFactory):
    class Meta(object):
        model = network_type
        abstract = True
        django_get_or_create = ("identifier", )


class NetworkTypeOtherNetworkFactory(NetworkTypeFactory):
    description = "other network"
    identifier = "o"


class NetworkDeviceTypeFactory(DjangoModelFactory):
    class Meta(object):
        model = network_device_type
        abstract = True
        django_get_or_create = ("identifier", )


class NetworkDeviceTypeEthernetFactory(NetworkDeviceTypeFactory):
    description = "ethernet devices"
    identifier = "eth"


class NetdeviceSpeedFactory(DjangoModelFactory):
    speed_bps = 1000000000
    full_duplex = True
    check_via_ethtool = False

    class Meta(object):
        model = netdevice_speed


def create_base_fixtures():
    DeviceTypeMetaDeviceFactory.create()
    DeviceTypeHostFactory.create()
    DeviceGroupFactory.create(name="cdg", cluster_device_group=True)
    NetworkTypeOtherNetworkFactory.create()
    NetworkDeviceTypeEthernetFactory.create()
    NetdeviceSpeedFactory.create()


class FlagsToDictTest(NoDBTestCase):
    def setUp(self):
        self.mapping = {
            "a": "a_flag",
            "b": "b_flag",
            "c": "c_flag",
        }

    def test(self):
        result = flags_to_dict(" a   , b ", "", self.mapping)
        expected = {"a_flag": True, "b_flag": True, "c_flag": False}
        self.assertEquals(result, expected)

    def test_defaults(self):
        result = flags_to_dict("", "c", self.mapping)
        expected = {"a_flag": False, "b_flag": False, "c_flag": True}
        self.assertEquals(result, expected)

        result = flags_to_dict(None, "b", self.mapping)
        expected = {"a_flag": False, "b_flag": True, "c_flag": False}
        self.assertEquals(result, expected)

    def test_special_n(self):
        self.mapping.update({"n": None})

        result = flags_to_dict("n", "a,b,c", self.mapping)
        expected = {"a_flag": False, "b_flag": False, "c_flag": False}
        self.assertEqual(result, expected)


class DestroyCacheMixin(object):
    def tearDown(self):
        for values in CACHES.values():
            values.clear()


class CacheSafeTestCase(DestroyCacheMixin, TestCase):
    pass


class TransformTimeperiodTest(CacheSafeTestCase):
    def setUp(self):
        self.simple = Timeperiod.objects.filter(
            timeperiod_name="simple_timeperiod"
        )[0]
        self.complex = Timeperiod.objects.filter(
            timeperiod_name="complex_timeperiod"
        )[0]

    def test_singleton(self):
        self.assertEqual(
            transform_timeperiod(self.simple).pk,
            transform_timeperiod(self.simple).pk,
        )

    def test_simple(self):
        result = transform_timeperiod(self.simple)
        self.assertEqual(result.thu_range, "12:00-24:00")
        self.assertEqual(result.fri_range, "06:00-07:00")
        for attribute in (
            "sun_range", "mon_range", "tue_range", "wed_range", "sat_range"
        ):
            self.assertEqual(getattr(result, attribute), "00:00-24:00")
        self.assertEqual(result.name, "simple_timeperiod")
        self.assertEqual(result.alias, "alias_simple_timeperiod")

    def test_complex(self):
        # Note: None of the "complex" attributes are supported yet.
        result = transform_timeperiod(self.complex)
        for attribute in (
            "sun_range", "mon_range", "tue_range", "wed_range", "thu_range",
            "fri_range", "sat_range"
        ):
            self.assertEqual(getattr(result, attribute), DEFAULT_TIME_RANGE)


class TransformHostgroupTest(CacheSafeTestCase):
    def setUp(self):
        DeviceTypeMetaDeviceFactory.create()
        self.hostgroup = Hostgroup.objects.filter(
            hostgroup_name="simple_hostgroup"
        )[0]

    def test_singleton(self):
        self.assertEqual(
            transform_hostgroup(self.hostgroup).pk,
            transform_hostgroup(self.hostgroup).pk,
        )

    def test(self):
        result = transform_hostgroup(self.hostgroup)
        self.assertEqual(result.name, "simple_hostgroup")
        self.assertEqual(result.description, "alias_simple_hostgroup")


class TransformCommandTest(CacheSafeTestCase):
    def setUp(self):
        self.command = Command.objects.filter(command_name="command_no_argument")[0]

    def test_no_singleton(self):
        self.assertNotEqual(
            transform_command(self.command).pk,
            transform_command(self.command).pk
        )

    def test(self):
        result = transform_command(self.command)
        self.assertEqual(result.name, self.command["command_name"])
        self.assertEqual(result.command_line, self.command["command_line"])
        self.assertEqual(result.config.name, self.command["command_name"])


class TransformContactTest(CacheSafeTestCase):
    def setUp(self):
        self.contact = Contact.objects.filter(contact_name="john_smith")[0]

    def test_singleton(self):
        self.assertEqual(
            transform_contact(self.contact).pk,
            transform_contact(self.contact).pk,
        )

    def test_user_and_group(self):
        result = transform_contact(self.contact)
        self.assertEqual(result.user.login, "john_smith")
        self.assertEqual(result.user.email, "john_smith@example.com")
        self.assertFalse(result.user.active)
        self.assertEqual(result.user.uid, 100)
        self.assertEqual(result.user.group.gid, 100)
        self.assertEqual(result.user.group.groupname, DEFAULT_CONTACT_GROUP_NAME)

    def test_single_user_group(self):
        result, unused_created_group = transform_contact(
            self.contact, user_specific_group=True
        )
        single_user_group = mon_contactgroup.objects.get()
        self.assertEqual(
            single_user_group.name, result.user.login + SINGLE_USER_GROUP_SUFFIX
        )

        self.assertItemsEqual(
            list(result.mon_contactgroup_set.all()),
            [single_user_group]
        )

    def test(self):
        result = transform_contact(self.contact)

        timeperiod = mon_period.objects.get()

        self.assertEqual(result.snperiod, timeperiod)
        self.assertEqual(result.hnperiod, timeperiod)
        self.assertEqual(result.mon_alias, "John Smith")

        true = (
            "snwarning", "snunknown", "sncritical", "snrecovery",
            "hndown", "hnunreachable", "hnrecovery",
        )
        false = (
            "splanned_downtime", "sflapping", "hflapping", "hplanned_downtime"
        )
        for i in true:
            self.assertTrue(getattr(result, i))
        for i in false:
            self.assertFalse(getattr(result, i))


class TransformContactgroupTest(CacheSafeTestCase):
    def setUp(self):
        self.contactgroup = Contactgroup.objects.filter(
            contactgroup_name="simple_contactgroup"
        )[0]

    def test_singleton(self):
        self.assertEqual(
            transform_contactgroup(self.contactgroup).pk,
            transform_contactgroup(self.contactgroup).pk,
        )

    def test(self):
        result = transform_contactgroup(self.contactgroup)
        self.assertEqual(result.alias, "alias_simple_contactgroup")
        self.assertEqual(result.name, "simple_contactgroup")

        john_smith = mon_contact.objects.get()
        self.assertItemsEqual(list(result.members.all()), [john_smith])


class TransformServiceTest(CacheSafeTestCase):
    def setUp(self):
        self.service = Service.objects.filter(
            service_description="service_a"
        )[0]

    def test_singleton(self):
        self.assertEqual(
            transform_service(self.service).pk,
            transform_service(self.service).pk,
        )

    def test(self):
        result = transform_service(self.service)

        timeperiod = mon_period.objects.get()

        self.assertEqual(result.nsc_period, timeperiod)
        self.assertEqual(result.nsn_period, timeperiod)
        self.assertEqual(result.name, "service_a")

        # notification_options    w,c,r
        # flap_detection_options  o,c

        true = (
            "nwarning", "ncritical", "nrecovery", "flap_detect_ok",
            "flap_detect_critical"
        )
        false = (
            "nunknown", "nflapping", "nplanned_downtime", "flap_detect_warn",
            "flap_detect_unknown"
        )
        for i in true:
            self.assertTrue(getattr(result, i))
        for i in false:
            self.assertFalse(getattr(result, i))

        self.assertTrue(result.volatile)
        self.assertTrue(result.check_freshness)
        self.assertTrue(result.flap_detection_enabled)

        self.assertEqual(result.ninterval, 2)
        self.assertEqual(result.retry_interval, 3)
        self.assertEqual(result.check_interval, 4)
        self.assertEqual(result.max_attempts, 5)
        # Note: The value in the config is lower than what we support and
        # defaults to our minimum.
        self.assertEqual(result.freshness_threshold, 10)
        self.assertEqual(result.low_flap_threshold, 7)
        self.assertEqual(result.high_flap_threshold, 8)

    def test_contacts_via_single_user_group(self):
        result = transform_service(self.service)

        single_user_group = mon_contactgroup.objects.get()
        self.assertEqual(single_user_group.members.get().user.login, "john_smith")

        self.assertEqual(single_user_group, result.mon_contactgroup_set.get())


class TransformHostTest(CacheSafeTestCase):
    def setUp(self):
        create_base_fixtures()

        self.host = Host.objects.filter(
            host_name="simple_host"
        )[0]

    def test_singleton(self):
        result_1 = transform_host(self.host)
        self.assertEqual(netdevice.objects.filter(device=result_1).count(), 1)

        result_2 = transform_host(self.host)
        self.assertEqual(result_1.pk, result_2.pk)
        self.assertEqual(netdevice.objects.filter(device=result_2).count(), 1)

    def test(self):
        result = transform_host(self.host)
        self.assertEqual(result.device_group.name, "simple_hostgroup")
        self.assertEqual(result.alias, "alias_simple_host")

        self.assertItemsEqual(result.all_ips(), ["10.10.10.11"])

        # Check if the check_command from the service is correctly associated
        all_device_configs = result.device_config_set.all()
        all_configs = config.objects.filter(device_config=all_device_configs)
        all_commands = mon_check_command.objects.filter(config=all_configs)
        self.assertEqual(all_commands.count(), 3)
        self.assertItemsEqual(
            [i.name for i in all_commands],
            # command_one_argument should be created twice
            ["command_one_argument", "command_no_argument", "command_one_argument"],
        )

        # Check if the check_command from the host is associated as the
        # host_check_command.
        self.assertEqual(
            result.mon_device_templ.host_check_command.name,
            "host_check_command"
        )


class CreateDevicesTest(CacheSafeTestCase):
    def setUp(self):
        create_base_fixtures()

    def test(self):
        devices = create_devices()
        self.assertEqual(len(devices), 2)
        self.assertItemsEqual(
            [i.name for i in devices],
            ["simple_host", "parent_host"]
        )


class CreatePeeringInformationTest(CacheSafeTestCase):
    def setUp(self):
        create_base_fixtures()
        self.devices = create_devices()
        self.child = self.parent = None
        for d in self.devices:
            if d.name == "simple_host":
                self.child = d
                self.child_netdevice = d.netdevice_set.get()
            elif d.name == "parent_host":
                self.parent = d
                self.parent_netdevice = d.netdevice_set.get()
            else:
                raise Exception(
                    "Problem setting up test: Found host other than "
                    "child or parent"
                )

    def test(self):
        create_peering_information(self.devices)
        connection = peer_information.objects.get()

        # Since the connection is assumed to be bidirectional source and
        # destination can be swapped without changes.
        self.assertItemsEqual(
            [connection.s_netdevice, connection.d_netdevice],
            [self.parent_netdevice, self.child_netdevice],
        )


class UnifyTemplatesTest(CacheSafeTestCase):
    def setUp(self):
        create_base_fixtures()
        self.devices = create_devices()

    def test(self):
        unify_templates(self.devices)
