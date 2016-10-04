# -*- coding: utf-8 -*-
#
# Copyright (C) 2016 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw-server
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

""" Serializers for AssetManagement """

from rest_framework import serializers

from initat.cluster.backbone.models import AssetRun, AssetPackage, \
    AssetPackageVersion, AssetBatch, AssetHardwareEntry, AssetProcessEntry, \
    StaticAssetTemplate, StaticAssetTemplateField, AssetLicenseEntry, AssetUpdateEntry, \
    AssetPCIEntry, AssetDMIHead, AssetDMIHandle, AssetDMIValue, AssetHWMemoryEntry, AssetHWCPUEntry, AssetHWGPUEntry, \
    AssetHWLogicalEntry, AssetHWDisplayEntry, StaticAsset, StaticAssetFieldValue, \
    AssetPackageVersionInstallTime, AssetHWNetworkDevice, partition_table, partition_disc, partition

from initat.cluster.backbone.models.partition import partition_disc

__all__ = [
    "AssetRunSimpleSerializer",
    "AssetRunOverviewSerializer",
    "AssetRunDetailSerializer",
    "AssetBatchSerializer",
    "AssetPackageSerializer",
    "AssetPackageVersionInstallTime",
    "AssetPackageVersionSerializer",
    "ShallowPastAssetRunSerializer",
    "ShallowPastAssetBatchSerializer",
    "AssetHardwareEntrySerializer",
    "AssetProcessEntrySerializer",
    "StaticAssetTemplateSerializer",
    "StaticAssetTemplateFieldSerializer",
    "AssetLicenseEntrySerializer",
    "AssetUpdateEntrySerializer",
    "AssetPCIEntrySerializer",
    "AssetDMIHeadSerializer",
    "AssetDMIHandleSerializer",
    "AssetDMIValueSerializer",
    "StaticAssetSerializer",
    "StaticAssetFieldValueSerializer",
    "StaticAssetTemplateRefsSerializer",
    "SimpleAssetBatchSerializer"
]


# for simple overview on frontend
class ShallowPastAssetRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetRun
        fields = (
            "idx", "device", "run_start_time", "run_duration",
            "scan_type", "run_type", "run_status",
        )


class ShallowPastAssetBatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetBatch
        fields = (
            "idx", "device", "run_start_time", "run_time"
        )

class AssetHardwareEntrySerializer(serializers.ModelSerializer):

    class Meta:
        model = AssetHardwareEntry


class AssetPackageVersionInstallTimeSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetPackageVersionInstallTime
        fields = ("idx", "package_version", "install_time")

class AssetPackageVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetPackageVersion
        fields = ("idx", "size", "version", "release", "info", "created", "install_info")


class AssetPackageSerializer(serializers.ModelSerializer):
    assetpackageversion_set = AssetPackageVersionSerializer(many=True)

    class Meta:
        model = AssetPackage
        fields = ("idx", "name", "package_type", "assetpackageversion_set")


class AssetRunSimpleSerializer(serializers.ModelSerializer):

    class Meta:
        model = AssetRun
        fields = (
            "idx", "device", "run_index", "run_type", "run_result",
            "run_start_time", "run_end_time", "run_duration",
            "asset_batch", "run_status",
        )


class AssetRunOverviewSerializer(serializers.ModelSerializer):
    num_packages = serializers.IntegerField()
    num_hardware = serializers.IntegerField()
    num_processes = serializers.IntegerField()
    num_licenses = serializers.IntegerField()
    num_updates = serializers.IntegerField()
    num_pending_updates = serializers.IntegerField()
    num_pci_entries = serializers.IntegerField()
    num_asset_handles = serializers.IntegerField()
    num_hw_entries = serializers.IntegerField()

    class Meta:
        model = AssetRun
        fields = (
            "idx", "device", "run_index", "run_type", "run_result",
            "run_start_time", "run_end_time", "run_duration",
            "asset_batch", "run_status",
            "error_string", "interpret_error_string",
            # many to many count fields
            "num_packages", "num_hardware", "num_processes",
            "num_updates", "num_pending_updates", "num_licenses",
            "num_pci_entries", "num_asset_handles", "num_hw_entries"
        )


class AssetProcessEntrySerializer(serializers.ModelSerializer):

    class Meta:
        model = AssetProcessEntry


class AssetLicenseEntrySerializer(serializers.ModelSerializer):

    class Meta:
        model = AssetLicenseEntry


class AssetUpdateEntrySerializer(serializers.ModelSerializer):

    class Meta:
        model = AssetUpdateEntry


class AssetPCIEntrySerializer(serializers.ModelSerializer):

    class Meta:
        model = AssetPCIEntry


class AssetDMIValueSerializer(serializers.ModelSerializer):

    class Meta:
        model = AssetDMIValue


class AssetDMIHandleSerializer(serializers.ModelSerializer):
    assetdmivalue_set = AssetDMIValueSerializer(many=True)

    class Meta:
        model = AssetDMIHandle


class AssetDMIHeadSerializer(serializers.ModelSerializer):
    assetdmihandle_set = AssetDMIHandleSerializer(many=True)

    class Meta:
        model = AssetDMIHead


class AssetHWMemoryEntrySerializer(serializers.ModelSerializer):
    formfactorname = serializers.SerializerMethodField()
    memorytypename = serializers.SerializerMethodField()

    def get_formfactorname(self, obj):
        return obj.get_name_of_form_factor()

    def get_memorytypename(self, obj):
        return obj.get_name_of_memory_type()

    class Meta:
        model = AssetHWMemoryEntry
        fields = (
            "idx", "banklabel", "formfactor", "memorytype",
            "manufacturer", "capacity", "formfactorname", "memorytypename"
        )


class AssetHWNetworkDeviceSerializer(serializers.ModelSerializer):

    class Meta:
        model = AssetHWNetworkDevice
        fields = (
            "idx", "manufacturer", "product_name", "device_name", "speed", "mac_address"
        )


class AssetHWCPUEntrySerializer(serializers.ModelSerializer):

    class Meta:
        model = AssetHWCPUEntry
        fields = (
            "idx", "numberofcores", "name"
        )


class AssetHWGPUEntrySerializer(serializers.ModelSerializer):

    class Meta:
        model = AssetHWGPUEntry
        fields = (
            "idx", "name"
        )


class AssetHWHDDEntrySerializer(serializers.ModelSerializer):

    class Meta:
        model = partition_disc
        fields = (
            "idx", "disc"
        )


class AssetHWLogicalEntrySerializer(serializers.ModelSerializer):

    class Meta:
        model = AssetHWLogicalEntry
        fields = (
            "idx", "name", "size", "free"
        )


class AssetHWDisplayEntrySerializer(serializers.ModelSerializer):

    class Meta:
        model = AssetHWDisplayEntry
        fields = (
            "idx", "name", "type", "manufacturer"
        )


class AssetRunDetailSerializer(serializers.ModelSerializer):
    assethardwareentry_set = AssetHardwareEntrySerializer(many=True)
    assetprocessentry_set = AssetProcessEntrySerializer(many=True)
    assetlicenseentry_set = AssetLicenseEntrySerializer(many=True)
    assetupdateentry_set = AssetUpdateEntrySerializer(many=True)
    assetpcientry_set = AssetPCIEntrySerializer(many=True)
    assetdmihead_set = AssetDMIHeadSerializer(many=True)
    cpus = AssetHWCPUEntrySerializer(many=True)
    memory_modules = AssetHWMemoryEntrySerializer(many=True)
    gpus = AssetHWGPUEntrySerializer(many=True)
    hdds = AssetHWHDDEntrySerializer(many=True)
    displays = AssetHWDisplayEntrySerializer(many=True)
    packages_install_times = AssetPackageVersionInstallTimeSerializer(many=True)

    class Meta:
        model = AssetRun
        fields = (
            "idx",
            "packages", "packages_install_times", "assethardwareentry_set",
            "assetprocessentry_set", "assetlicenseentry_set",
            "assetupdateentry_set", "assetpcientry_set", "assetdmihead_set",
            "memory_modules", "memory_count", "cpus", "cpu_count", "gpus", "hdds",
            "displays"
        )


class StaticAssetTemplateFieldSerializer(serializers.ModelSerializer):
    default_value_date = serializers.DateField(input_formats=["%d.%m.%Y"])

    class Meta:
        model = StaticAssetTemplateField


class StaticAssetTemplateSerializer(serializers.ModelSerializer):
    staticassettemplatefield_set = StaticAssetTemplateFieldSerializer(many=True, read_only=True)

    class Meta:
        model = StaticAssetTemplate


class StaticAssetFieldValueSerializer(serializers.ModelSerializer):
    class Meta:
        model = StaticAssetFieldValue


class StaticAssetSerializer(serializers.ModelSerializer):
    staticassetfieldvalue_set = StaticAssetFieldValueSerializer(many=True, read_only=True)

    class Meta:
        model = StaticAsset


class StaticAssetTemplateRefsSerializer(serializers.Serializer):
    static_asset_template = serializers.IntegerField()
    device_name = serializers.CharField()

class AssetPartitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = partition
        fields = ("idx", "mountpoint", "size")

class AssetPartitionDiscSerializer(serializers.ModelSerializer):
    partition_set = AssetPartitionSerializer(many=True)

    class Meta:
        model = partition_disc
        fields = ("idx", "disc", "serial", "size", "partition_set")

class AssetPartitionTableSerializer(serializers.ModelSerializer):
    partition_disc_set = AssetPartitionDiscSerializer(many=True)

    class Meta:
        model = partition_table
        fields = ("idx", "name", "partition_disc_set")

class AssetBatchSerializer(serializers.ModelSerializer):
    packages_install_times = AssetPackageVersionInstallTimeSerializer(many=True)
    installed_updates = AssetUpdateEntrySerializer(many=True)
    pending_updates = AssetUpdateEntrySerializer(many=True)
    memory_modules = AssetHWMemoryEntrySerializer(many=True)
    cpus = AssetHWCPUEntrySerializer(many=True)
    gpus = AssetHWGPUEntrySerializer(many=True)
    network_devices = AssetHWNetworkDeviceSerializer(many=True)
    partition_table = AssetPartitionTableSerializer()

    class Meta:
        model = AssetBatch
        fields = ("idx", "run_start_time", "run_end_time", "run_time", "run_status", "device", "packages",
                  "packages_install_times", "pending_updates", "installed_updates", "cpus", "memory_modules", "gpus",
                  "is_finished_processing", "network_devices", "partition_table")

class SimpleAssetBatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetBatch
        fields = ("idx", "run_start_time", "run_end_time", "run_time", "run_status", "device", "packages_length",
                  "packages_install_times_length", "pending_updates_length", "installed_updates_length", "cpus_length",
                  "memory_modules_length", "gpus_length", "network_devices_length", "is_finished_processing",
                  "partition_table_length")
