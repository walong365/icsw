# -*- coding: utf-8 -*-

import copy
import lsm
from unittest import TestCase as NoDBTestCase

from initat.host_monitoring import limits
from initat.host_monitoring.long_running_checks import LONG_RUNNING_CHECK_RESULT_KEY
from initat.host_monitoring.modules.libstoragemgmt_mod import (
    libstoragemgmt_command
)

TESTDATA = {
    'pools': [('pool01', 2), ('pool02', 2)],
    'disks': [
        ('disk01', 2), ('disk02', 2), ('disk03', 2),
        ('disk04', 2), ('disk05', 2), ('disk06', 2),
    ],
    'systems': [('StaticCluster MSA01 (HP MSA 2040 SAS)', 2)]
}


class LibstoragemgmtCommandTest(NoDBTestCase):
    def setUp(self):
        test_data_good = copy.deepcopy(TESTDATA)

        test_data_bad = copy.deepcopy(TESTDATA)
        test_data_bad["pools"][0] = ("bad_pool", lsm.Pool.STATUS_ERROR)
        test_data_bad["disks"][0] = ("bad_disk", lsm.Disk.STATUS_ERROR)
        test_data_bad["systems"][0] = ("bad_system", lsm.System.STATUS_ERROR)

        self.command = libstoragemgmt_command("foo")
        self.srv_com_good = {
            LONG_RUNNING_CHECK_RESULT_KEY: test_data_good
        }
        self.srv_com_bad = {
            LONG_RUNNING_CHECK_RESULT_KEY: test_data_bad
        }

    def test_good(self):
        result = self.command.interpret(self.srv_com_good)
        expected = (
            limits.nag_STATE_OK,
            "systems: (good=1 bad=0), pools: (good=2 bad=0), disks: "
            "(good=6 bad=0)"
        )
        self.assertTupleEqual(result, expected)

    def test_bad(self):
        result = self.command.interpret(self.srv_com_bad)
        expected = (
            limits.nag_STATE_CRITICAL,
            "systems: (good=0 bad=1), pools: (good=1 bad=1), disks: "
            "(good=5 bad=1)"
        )
        self.assertTupleEqual(result, expected)
