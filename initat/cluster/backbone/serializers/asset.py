# -*- coding: utf-8 -*-
#
# Copyright (C) 2016 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw-server
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 2 as
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
    AssetPCIEntry, AssetDMIHead, AssetDMIHandle, AssetDMIValue

__all__ = [
    "AssetRunSimpleSerializer",
    "AssetRunOverviewSerializer",
    "AssetRunDetailSerializer",
    "AssetBatchSerializer",
    "AssetPackageSerializer",
    "AssetPackageVersionSerializer",
    "ShallowPastAssetRunSerializer",
    "ShallowPastAssetBatchSerializer",
    "AssetHardwareEntrySerializer",
    "AssetProcessEntrySerializer",
    "StaticAssetTemplateSerializer",
    "AssetLicenseEntrySerializer",
    "AssetUpdateEntrySerializer",
    "AssetPCIEntrySerializer",
    "AssetDMIHeadSerializer",
    "AssetDMIHandleSerializer",
    "AssetDMIValueSerializer",
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
            "idx", "device", "run_start_time", "run_time",
            "num_runs_ok", "num_runs_error", "num_completed",
        )


class AssetHardwareEntrySerializer(serializers.ModelSerializer):

    class Meta:
        model = AssetHardwareEntry


class AssetBatchSerializer(serializers.ModelSerializer):

    class Meta:
        model = AssetBatch


class AssetPackageVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetPackageVersion
        fields = ("idx", "size", "version", "release", "info", "created")


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
            "num_pci_entries", "num_asset_handles",
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


class AssetRunDetailSerializer(serializers.ModelSerializer):
    assethardwareentry_set = AssetHardwareEntrySerializer(many=True)
    assetprocessentry_set = AssetProcessEntrySerializer(many=True)
    assetlicenseentry_set = AssetLicenseEntrySerializer(many=True)
    assetupdateentry_set = AssetUpdateEntrySerializer(many=True)
    assetpcientry_set = AssetPCIEntrySerializer(many=True)
    assetdmihead_set = AssetDMIHeadSerializer(many=True)

    class Meta:
        model = AssetRun
        fields = (
            "idx",
            "packages", "assethardwareentry_set",
            "assetprocessentry_set", "assetlicenseentry_set",
            "assetupdateentry_set", "assetpcientry_set", "assetdmihead_set",
        )


class StaticAssetTemplateFieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = StaticAssetTemplateField


class StaticAssetTemplateSerializer(serializers.ModelSerializer):
    staticassettemplatefield_set = StaticAssetTemplateFieldSerializer(many=True, read_only=True)

    class Meta:
        model = StaticAssetTemplate
