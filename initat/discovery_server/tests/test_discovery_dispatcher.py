import unittest
import dateutil
import django.core.management
from django.test import TestCase
import datetime
import pprint
import itertools
import pytz
import mock

from initat.cluster.backbone.models import DiscoverySource, DispatchSetting
from initat.discovery_server.dispatcher import DiscoveryDispatcher

from testutils.factories import DeviceTestFactory
from testutils.factories.discovery import DispatchSettingTestFactory, ScanHistoryTestFactory


# itertools recipe
def pairwise(iterable):
    "s -> (s0,s1), (s1,s2), (s2, s3), ..."
    a, b = itertools.tee(iterable)
    next(b, None)
    return itertools.izip(a, b)


def setUpModule():
    # TODO: possibly call this globally for all tests, it's needed whenever a device is being created
    django.core.management.call_command("create_cdg")


class DiscoveryDispatcherTest(TestCase):

    def setUp(self):
        self.jan_fst = datetime.datetime(2015, 1, 1, 1, 0, tzinfo=pytz.utc)
        self.jan_fst_three_am = datetime.datetime(2015, 1, 1, 3, 0, tzinfo=pytz.utc)
        self.jan_snd = datetime.datetime(2015, 1, 2, 1, 0, tzinfo=pytz.utc)
        self.jan_thrd = datetime.datetime(2015, 1, 3, 1, 0, tzinfo=pytz.utc)

    def test_empty(self):
        dispatcher = DiscoveryDispatcher()
        res = dispatcher.calculate(self.jan_fst, self.jan_snd)
        self.assertEqual(res, [])

    def create_simple_fixtures(self, device0, device1):
        source = DiscoverySource.SNMP
        # every 30 min this device
        DispatchSettingTestFactory(
            device=device0,
            source=source,
            duration_amount=30,
            duration_unit=DispatchSetting.DurationUnits.minutes,
        )
        # every hour this device with run_now
        DispatchSettingTestFactory(
            device=device1,
            source=source,
            duration_amount=1,
            duration_unit=DispatchSetting.DurationUnits.hours,
            run_now=1
        )

    def assert_no_overlaps(self, res):
        for item0, item1 in pairwise(res):
            # no overlap whatsoever due to source limit
            self.assertLessEqual(item0.expected_finish_date, item1.expected_run_date)

    def test_source_limit(self):
        device0 = DeviceTestFactory()
        device1 = DeviceTestFactory()

        self.create_simple_fixtures(device0, device1)

        with mock.patch.object(DiscoverySource, 'get_maximal_concurrent_runs') as get_maximal_concurrent_source_runs:
            get_maximal_concurrent_source_runs.return_value = 1
            dispatcher = DiscoveryDispatcher()
            res = dispatcher.calculate(self.jan_fst, self.jan_fst_three_am)
        # print 'final res'
        # pprint.pprint(res)

        # run_now must be considered
        self.assertEqual(res[0].device, device1)
        self.assertEqual(len([item for item in res if item.device == device0]), 4)
        self.assertEqual(len([item for item in res if item.device == device1]), 2)

        self.assert_no_overlaps(res)

    def test_device_limit(self):
        device0 = DeviceTestFactory()

        self.create_simple_fixtures(device0, device0)

        dispatcher = DiscoveryDispatcher()
        res = dispatcher.calculate(self.jan_fst, self.jan_fst_three_am)

        self.assert_no_overlaps(res)

    def test_scan_history(self):
        # check if scan history data is used
        device0 = DeviceTestFactory()
        source0 = DiscoverySource.IPMI

        # one long one with priority
        DispatchSettingTestFactory(
            device=device0,
            source=source0,
            duration_amount=1,
            duration_unit=DispatchSetting.DurationUnits.days,
        )
        ScanHistoryTestFactory(
            device=device0,
            source=source0,
            duration=60 * 60 * 12,  # 1/2 day
            date=self.jan_fst - dateutil.relativedelta.relativedelta(months=2)  # long ago
        )
        ScanHistoryTestFactory(
            device=device0,
            source=source0,
            duration=60 * 60 * 12 * 3,  # 3/2 days
            date=self.jan_fst - dateutil.relativedelta.relativedelta(months=1)  # long ago
        )

        dispatcher = DiscoveryDispatcher()
        res = dispatcher.calculate(self.jan_fst, self.jan_snd)

        self.assertEqual(res[0].expected_run_date, self.jan_fst)
        self.assertEqual(res[0].expected_finish_date, self.jan_snd)  # this tests the scan history

    def test_min_interval(self):
        device0 = DeviceTestFactory()
        source0 = DiscoverySource.IPMI
        source1 = DiscoverySource.SNMP

        # one long one with priority
        DispatchSettingTestFactory(
            device=device0,
            source=source0,
            duration_amount=1,
            duration_unit=DispatchSetting.DurationUnits.weeks,
            run_now=True
        )
        # this takes long
        ScanHistoryTestFactory(
            device=device0,
            source=source0,
            duration=60 * 60 * 24,
            date=self.jan_fst - dateutil.relativedelta.relativedelta(hours=1)  # recently, but run_now is set
        )

        # short ones without priority
        DispatchSettingTestFactory(
            device=device0,
            source=source1,
            duration_amount=1,
            duration_unit=DispatchSetting.DurationUnits.hours,
        )

        dispatcher = DiscoveryDispatcher()
        res = dispatcher.calculate(self.jan_fst, self.jan_thrd)

        print 'final res'
        pprint.pprint(res)
