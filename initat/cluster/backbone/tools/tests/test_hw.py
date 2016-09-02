import os
import unittest
from lxml import etree
import json
from initat.cluster.backbone.tools.hw import Hardware


class TestHardware(unittest.TestCase):
    BASE_PATH = os.path.join(os.path.dirname(__file__), 'data')

    def test_lshw(self):
        lshw_tree = etree.parse(open(os.path.join(self.BASE_PATH, 'lshw.xml')))
        hw = Hardware(lshw_tree=lshw_tree)
        self._common_test(hw)
        self.assertEqual(hw.cpus[0].number_of_cores, 4)

    def test_win32(self):
        win32_tree = json.load(
            open(os.path.join(self.BASE_PATH, 'win32.json')))
        hw = Hardware(win32_tree=win32_tree)
        self.assertEqual(hw.cpus[0].number_of_cores, 1)
        self._common_test(hw)

    def _common_test(self, hw):
        self.assertNotEqual(hw.cpus, [])
        self.assertIsNotNone(hw.memory)
        self.assertNotEqual(hw.gpus, [])
        self.assertNotEqual(hw.hdds, [])
        self.assertNotEqual(hw.network_devices, [])


if __name__ == '__main__':
    unittest.main()
