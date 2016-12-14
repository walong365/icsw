import os
import pickle
import sys
from io import StringIO

from unittest import TestCase

from initat.cluster.backbone.models import AssetRun, AssetBatch, AssetType, RunStatus, RunResult, device, \
    device_group, partition_disc
from initat.cluster.backbone.management.commands.create_icsw_fixtures import Command as CreateFixturesCommand


class TestAssetManagement(TestCase):
    BASE_PATH = os.path.join(os.path.dirname(__file__), 'data')
    TEST_DATA = pickle.load(open(os.path.join(BASE_PATH, "asset_management_test_data"), "rb"))
    CHECKABLE_ASSET_BATCH_PROPERTIES = ["cpus", "memory_modules", "gpus", "displays", "network_devices"]

    assetbatch_dict = {}

    @classmethod
    def setUpClass(cls):
        standard_stdout = sys.stdout
        sys.stdout = StringIO()
        CreateFixturesCommand().handle()
        sys.stdout = standard_stdout

        cdg_group = device_group(name="cdg", cluster_device_group=True)
        cdg_group.save()

        dummy_device_group = device_group(name="dummy_device_group", cluster_device_group=False)
        dummy_device_group.save()

    def test_00_asset_type_package(self):
        for asset_run, asset_batch, identifier in self.__assetrun_assetbatch_setup_iterator(AssetType.PACKAGE):
            self.assertGreater(asset_batch.installed_packages.all().count(), 0, "Failed for {}".format(identifier))

    def test_01_asset_type_hardware(self):
        for asset_run, asset_batch, identifier in self.__assetrun_assetbatch_setup_iterator(AssetType.HARDWARE):
            self.assertGreater(asset_run.assethardwareentry_set.all().count(), 0, "Failed for {}".format(identifier))

    def test_02_asset_type_process(self):
        for asset_run, asset_batch, identifier in self.__assetrun_assetbatch_setup_iterator(AssetType.PROCESS):
            self.assertGreater(asset_run.assetprocessentry_set.all().count(), 0, "Failed for {}".format(identifier))

    def test_03_asset_type_pending_update(self):
        for asset_run, asset_batch, identifier in self.__assetrun_assetbatch_setup_iterator(AssetType.PENDING_UPDATE):
            self.assertGreater(asset_batch.pending_updates_status, 0, "Failed for {}".format(identifier))

    def test_04_asset_type_dmi(self):
        for asset_run, asset_batch, identifier in self.__assetrun_assetbatch_setup_iterator(AssetType.DMI):
            self.assertGreater(asset_run.assetdmihead_set.all().count(), 0, "Failed for {}".format(identifier))

    def test_05_asset_type_pci(self):
        for asset_run, asset_batch, identifier in self.__assetrun_assetbatch_setup_iterator(AssetType.PCI):
            self.assertGreater(asset_run.assetpcientry_set.all().count(), 0, "Failed for {}".format(identifier))

    def test_06_asset_type_lshw(self):
        for asset_run, asset_batch, identifier in self.__assetrun_assetbatch_setup_iterator(AssetType.LSHW):
            self.assertTrue(asset_run.run_type == AssetType.LSHW, "Failed for {}".format(identifier))

    def test_07_asset_type_partition(self):
        for asset_run, asset_batch, identifier in self.__assetrun_assetbatch_setup_iterator(AssetType.PARTITION):
            self.assertTrue(asset_run.run_type == AssetType.PARTITION, "Failed for {}".format(identifier))

    def test_08_asset_type_lsblk(self):
        for asset_run, asset_batch, identifier in self.__assetrun_assetbatch_setup_iterator(AssetType.LSBLK):
            self.assertTrue(asset_run.run_type == AssetType.LSBLK, "Failed for {}".format(identifier))

    def test_09_asset_type_xrandr(self):
        for asset_run, asset_batch, identifier in self.__assetrun_assetbatch_setup_iterator(AssetType.XRANDR):
            self.assertTrue(asset_run.run_type == AssetType.XRANDR, "Failed for {}".format(identifier))

    def test_10_asset_type_update(self):
        for asset_run, asset_batch, identifier in self.__assetrun_assetbatch_setup_iterator(AssetType.UPDATE):
            self.assertGreater(asset_batch.installed_updates.all().count(), 0, "Failed for {}".format(identifier))

    def test_11_asset_type_prettywinhw(self):
        for asset_run, asset_batch, identifier in self.__assetrun_assetbatch_setup_iterator(AssetType.PRETTYWINHW):
            self.assertTrue(asset_run.run_type == AssetType.PRETTYWINHW, "Failed for {}".format(identifier))

    def test_12_asset_batch(self):
        for result_obj, asset_batch in self.assetbatch_dict.items():
            identifier = result_obj.identifier

            print("")
            print("------")
            print(identifier)

            asset_batch.generate_assets()

            check_properties = [_property for _property in self.CHECKABLE_ASSET_BATCH_PROPERTIES if
                                _property not in result_obj.ignore_tests]
            for _property in check_properties:
                self.assertGreater(getattr(asset_batch, _property).all().count(), 0,
                                   "Failed for {} with property {}".format(identifier, _property))
            for _property in result_obj.ignore_tests:
                self.assertTrue(getattr(asset_batch, _property).all().count() == 0,
                                "Failed for {} with property {}".format(identifier, _property))

            self.assertTrue(asset_batch.partition_table is not None, "Failed for {}".format(identifier))
            self.assertGreater(asset_batch.partition_table.partition_disc_set.all().count(), 0,
                               "Failed for {}".format(identifier))
            for disk in asset_batch.partition_table.partition_disc_set.all():
                print("HDD: {}".format(disk.disc))
                print("SERIAL: {}".format(disk.serial))
                print("SIZE: {}".format(disk.size))

                self.assertTrue(disk.size is not None, "Failed for {}".format(identifier))
                self.assertGreater(disk.size, 0, "Failed for {}".format(identifier))
                for partition in disk.partition_set.all():
                    print("\_MOUNTPOINT: {}".format(partition.mountpoint))
                    print("\_SIZE: {}".format(partition.size))
                    print("\_FS: {}".format(partition.partition_fs.name))
                    print("")

                    self.assertTrue(partition.size is not None, "Failed for {}".format(identifier))
                    self.assertGreater(partition.size, 0, "Failed for {}".format(identifier))

            self.assertGreater(asset_batch.partition_table.logicaldisc_set.all().count(), 0,
                "Failed for {}".format(identifier))
            for logical_disk in asset_batch.partition_table.logicaldisc_set.all():
                print("")
                print("NAME: {}".format(logical_disk.device_name))
                print("FS: {}".format(logical_disk.partition_fs.name))
                print("SIZE: {}".format(logical_disk.size))
                print("FREE: {}".format(logical_disk.free_space))
                print("")


            for expected_hdd in result_obj.expected_hdds:
                try:
                    asset_batch.partition_table.partition_disc_set.get(
                        disc=expected_hdd.device_name,
                        serial=expected_hdd.serial,
                        size=expected_hdd.size
                        )
                except partition_disc.DoesNotExist:
                    self.fail("Expected HDD [{}, {}, {}] for {} not found".format(expected_hdd.device_name,
                                                                                  expected_hdd.serial,
                                                                                  expected_hdd.size,
                                                                                  identifier))

            for expected_partition in result_obj.expected_partitions:
                try:
                    disk = asset_batch.partition_table.partition_disc_set.get(disc=expected_partition.device_name)
                except partition_disc.DoesNotExist:
                    self.fail("Expected device [{}] for {} not found".format(expected_partition.device_name,
                                                                             identifier))
                else:
                    found = False
                    for partition in disk.partition_set.all():
                        if partition.mountpoint == expected_partition.mountpoint:
                            if partition.size == expected_partition.size:
                                if partition.partition_fs.name == expected_partition.filesystem:
                                    found = True

                    if not found:
                        self.fail("Expected Partition [{}, {}, {}, {}] for {} not found".format(
                            expected_partition.device_name,
                            expected_partition.mountpoint,
                            expected_partition.size,
                            expected_partition.filesystem,
                            identifier))

    def __assetrun_assetbatch_setup_iterator(self, asset_type):
        idx = 0
        for result_obj in self.TEST_DATA:
            identifier = result_obj.identifier
            result_dict = result_obj.result_dict
            idx += 1
            if result_obj in self.assetbatch_dict:
                asset_batch = self.assetbatch_dict[result_obj]
            else:
                dummy_device_group = device_group.objects.get(name="dummy_device_group")
                dummy_device = device(name="dummy_device_{}".format(idx), device_group=dummy_device_group)
                dummy_device.save()

                asset_batch = AssetBatch(device=dummy_device)
                asset_batch.save()
                self.assetbatch_dict[result_obj] = asset_batch

            if asset_type not in result_dict:
                continue

            scan_type = result_obj.scan_type
            raw_result_str = result_dict[asset_type]
            run_index = len(asset_batch.assetrun_set.all())
            asset_run = AssetRun(
                run_index=run_index,
                run_type=asset_type,
                run_status=RunStatus.PLANNED,
                scan_type=scan_type,
                batch_index=0,
                asset_batch=asset_batch,
                raw_result_str=raw_result_str
            )
            asset_run.save()
            asset_run.generate_assets()
            asset_run.state_finished(RunResult.SUCCESS, "")

            yield (asset_run, asset_batch, identifier)
