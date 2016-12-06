import os
import pickle

from django.test import TestCase

from initat.cluster.backbone.models import AssetRun, AssetBatch, AssetType, ScanType, RunStatus, RunResult

class DummyDevice(object):
    def __init__(self):
        self.name = "DummyDevice"

    def save(self):
        pass

class TestAssetManagement(TestCase):
    BASE_PATH = os.path.join(os.path.dirname(__file__), 'data')
    TEST_DATA = pickle.load(open(os.path.join(BASE_PATH, "asset_management_test_data"), "rb"))

    assetbatch_dict = {}
    assetrun_dict = {}

    def test_00_asset_type_package(self):
        for asset_run, asset_batch in self.__assetrun_assetbatch_setup_iterator(AssetType.PACKAGE):
            self.assertTrue(len(asset_batch.installed_packages.all()) > 0)

    def test_01_asset_type_hardware(self):
        for asset_run, asset_batch in self.__assetrun_assetbatch_setup_iterator(AssetType.HARDWARE):
            self.assertTrue(asset_run.assethardwareentry_set.all() > 0)

    def test_02_asset_type_process(self):
        for asset_run, asset_batch in self.__assetrun_assetbatch_setup_iterator(AssetType.PROCESS):
            self.assertTrue(asset_run.assetprocessentry_set.all() > 0)

    def test_03_asset_type_pending_update(self):
        for asset_run, asset_batch in self.__assetrun_assetbatch_setup_iterator(AssetType.PENDING_UPDATE):
            self.assertTrue(asset_batch.pending_updates_status > 0)

    def test_04_asset_type_dmi(self):
        for asset_run, asset_batch in self.__assetrun_assetbatch_setup_iterator(AssetType.DMI):
            self.assertTrue(asset_run.assetdmihead_set.all() > 0)

    def test_05_asset_type_pci(self):
        for asset_run, asset_batch in self.__assetrun_assetbatch_setup_iterator(AssetType.PCI):
            self.assertTrue(asset_run.assetpcientry_set.all() > 0)

    def test_06_asset_type_lshw(self):
        for asset_run, asset_batch in self.__assetrun_assetbatch_setup_iterator(AssetType.LSHW):
            self.assertTrue(asset_run.run_type == AssetType.LSHW)

    def test_07_asset_type_partition(self):
        for asset_run, asset_batch in self.__assetrun_assetbatch_setup_iterator(AssetType.PARTITION):
            self.assertTrue(asset_run.run_type == AssetType.PARTITION)

    def test_08_asset_type_lsblk(self):
        for asset_run, asset_batch in self.__assetrun_assetbatch_setup_iterator(AssetType.LSBLK):
            self.assertTrue(asset_run.run_type == AssetType.LSBLK)

    def test_09_asset_type_xrandr(self):
        for asset_run, asset_batch in self.__assetrun_assetbatch_setup_iterator(AssetType.XRANDR):
            self.assertTrue(asset_run.run_type == AssetType.XRANDR)

    def test_10_asset_batch(self):
        print(AssetBatch.objects.all())

    def __assetrun_assetbatch_setup_iterator(self, asset_type):
        for identifier, result_dict in self.TEST_DATA:
            if identifier in self.assetbatch_dict:
                asset_batch = self.assetbatch_dict[identifier]
            else:
                asset_batch = AssetBatch()
                asset_batch.save()
                print(asset_batch.idx)
                self.assetbatch_dict[identifier] = asset_batch

            raw_result_str = result_dict[asset_type]
            run_index = len(asset_batch.assetrun_set.all())
            asset_run = AssetRun(
                run_index=run_index,
                run_type=asset_type,
                run_status=RunStatus.PLANNED,
                scan_type=ScanType.HM,
                batch_index=0,
                asset_batch=asset_batch,
                raw_result_str=raw_result_str
            )
            asset_run.save()
            asset_run.generate_assets()
            asset_run.state_finished(RunResult.SUCCESS, "")

            yield (asset_run, asset_batch)
