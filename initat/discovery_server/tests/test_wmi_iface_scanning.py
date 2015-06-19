import django.core.management
from django.test import TestCase
from lxml.builder import E
import mock

from initat.discovery_server.discovery_struct import ExtCom
from initat.cluster.backbone.models import netdevice, net_ip
from initat.cluster.backbone.models.functions import clear_memoize_cache
from initat.discovery_server.ext_com_scan import WmiScanBatch, ScanBatch
from testutils.factories import DeviceTestFactory


def setUpModule():
    # TODO: possibly call this globally for all tests, it's needed whenever a device is being created
    django.core.management.call_command("create_cdg")
    django.core.management.call_command("create_fixtures")


class WmiScanning(TestCase):

    SCAN_OUTPUT_DISCARD_DISABLED_NETWORK_ADAPTER = 'CLASS: Win32_NetworkAdapter\nDeviceID\x01Index\x01MACAddress\x01Name\x01Speed\n7\x017\x0152:54:00:11:34:52\x01Intel(R) PRO/1000 MT Network Connection\x011000000000\n'
    SCAN_OUTPUT_DISCARD_DISABLED_NETWORK_ADAPTER_CONFIGURATION =  'CLASS: Win32_NetworkAdapterConfiguration\nDefaultIPGateway\x01Index\x01IPAddress\x01IPSubnet\x01MTU\nNULL\x010\x01NULL\x01NULL\x010\nNULL\x011\x01NULL\x01NULL\x010\nNULL\x012\x01NULL\x01NULL\x010\nNULL\x013\x01NULL\x01NULL\x010\nNULL\x014\x01NULL\x01NULL\x010\nNULL\x015\x01NULL\x01NULL\x010\nNULL\x016\x01NULL\x01NULL\x010\n(192.168.1.1)\x017\x01(192.168.1.43,fe80::7593:665a:a164:a07b)\x01(255.255.255.0,64)\x010\nNULL\x018\x01NULL\x01NULL\x010\nNULL\x019\x01NULL\x01NULL\x010\nNULL\x0110\x01NULL\x01NULL\x010\nNULL\x0111\x01NULL\x01NULL\x010\n'

    SCAN_OUTPUT_ALL_NETWORK_ADAPTER = 'CLASS: Win32_NetworkAdapter\nDeviceID\x01Index\x01MACAddress\x01Name\x01Speed\n0\x010\x01(null)\x01WAN Miniport (SSTP)\x010\n1\x011\x01(null)\x01WAN Miniport (IKEv2)\x010\n2\x012\x01(null)\x01WAN Miniport (L2TP)\x010\n3\x013\x01(null)\x01WAN Miniport (PPTP)\x010\n4\x014\x01(null)\x01WAN Miniport (PPPOE)\x010\n5\x015\x01(null)\x01WAN Miniport (IPv6)\x010\n6\x016\x01(null)\x01WAN Miniport (Network Monitor)\x010\n7\x017\x0152:54:00:11:34:52\x01Intel(R) PRO/1000 MT Network Connection\x011000000000\n8\x018\x01(null)\x01Microsoft ISATAP Adapter\x01100000\n9\x019\x01(null)\x01WAN Miniport (IP)\x010\n10\x0110\x01(null)\x01Teredo Tunneling Pseudo-Interface\x01100000\n11\x0111\x0120:41:53:59:4E:FF\x01RAS Async Adapter\x010\n'
    SCAN_OUTPUT_ALL_NETWORK_ADAPTER_CONFIGURATION =  'CLASS: Win32_NetworkAdapterConfiguration\nDefaultIPGateway\x01Index\x01IPAddress\x01IPSubnet\x01MTU\nNULL\x010\x01NULL\x01NULL\x010\nNULL\x011\x01NULL\x01NULL\x010\nNULL\x012\x01NULL\x01NULL\x010\nNULL\x013\x01NULL\x01NULL\x010\nNULL\x014\x01NULL\x01NULL\x010\nNULL\x015\x01NULL\x01NULL\x010\nNULL\x016\x01NULL\x01NULL\x010\n(192.168.1.1)\x017\x01(192.168.1.43,fe80::7593:665a:a164:a07b)\x01(255.255.255.0,64)\x010\nNULL\x018\x01NULL\x01NULL\x010\nNULL\x019\x01NULL\x01NULL\x010\nNULL\x0110\x01NULL\x01NULL\x010\nNULL\x0111\x01NULL\x01NULL\x010\n'

    def setUp(self):
        clear_memoize_cache()

    def _do_run(self, scan_dev, output_network_adapter, output_network_adapter_configuration):
        dev_com = E.device(
            scan_address="203.0.113.1",  # reserved ip
            username="user",
            password="pw",
            discard_disabled_interfaces="1",
        )
        ScanBatch.setup(proc=mock.Mock())

        with mock.patch.object(ExtCom, 'run') as run_mocked:  # don't actually call
            scan_batch = WmiScanBatch(dev_com, scan_dev)

        self.assertEqual(run_mocked.call_count, 2)

        # do what run() would do
        finished_method = lambda: 0
        for ext_com in scan_batch._ext_coms.itervalues():
            ext_com.finished = finished_method
            ext_com.result = 0
        scan_batch._ext_coms[WmiScanBatch.NETWORK_ADAPTER_MODEL].communicate =\
            lambda: (output_network_adapter, "")
        scan_batch._ext_coms[WmiScanBatch.NETWORK_ADAPTER_CONFIGURATION_MODEL].communicate =\
            lambda: (output_network_adapter_configuration, "")

        # actual parse
        scan_batch.check_ext_com()

    def test_scan_single_device(self, scan_dev=None):
        scan_dev = scan_dev or DeviceTestFactory()
        self._do_run(
            scan_dev,
            self.SCAN_OUTPUT_DISCARD_DISABLED_NETWORK_ADAPTER,
            self.SCAN_OUTPUT_DISCARD_DISABLED_NETWORK_ADAPTER_CONFIGURATION
        )

        nds = netdevice.objects.filter(device=scan_dev)
        self.assertEqual(len(nds), 1)
        self.assertEqual(nds[0].devname, "Intel(R) PRO/1000 MT Network Connection")
        self.assertEqual(nds[0].macaddr, "52:54:00:11:34:52")

        nips = net_ip.objects.filter(netdevice=nds[0])
        self.assertEqual(len(nips), 1)
        self.assertEqual(nips[0].ip, "192.168.1.43")

    def test_scan_all(self, scan_dev=None):
        scan_dev = scan_dev or DeviceTestFactory()
        self._do_run(
            scan_dev,
            self.SCAN_OUTPUT_ALL_NETWORK_ADAPTER,
            self.SCAN_OUTPUT_ALL_NETWORK_ADAPTER_CONFIGURATION
        )

        nds = netdevice.objects.filter(device=scan_dev)
        self.assertEqual(len(nds), 12)

        nips = net_ip.objects.filter(netdevice=nds[0])
        self.assertEqual(len(nips), 1)

    def test_multiple_scans(self):
        scan_dev = DeviceTestFactory()
        self.test_scan_single_device(scan_dev)
        # first run worked

        # running again should yield same number of net devices and ips
        self.test_scan_single_device(scan_dev)

        # single dev is contained in run for all, so this should work again
        self.test_scan_all(scan_dev)

        # same scan again, no changes
        self.test_scan_all(scan_dev)

