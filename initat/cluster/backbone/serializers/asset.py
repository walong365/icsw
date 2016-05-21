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

from initat.cluster.backbone.models import AssetRun, Asset, AssetPackage, \
    AssetPackageVersion, AssetBatch

__all__ = [
    "AssetRunSerializer",
    "AssetBatchSerializer",
    "AssetSerializer",
    "AssetPackageSerializer",
    "AssetPackageVersionSerializer",
    "ShallowPastAssetRunSerializer",
    "ShallowPastAssetBatchSerializer",
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


class AssetBatchSerializer(serializers.ModelSerializer):

    class Meta:
        model = AssetBatch


class AssetSerializer(serializers.ModelSerializer):
    assetstr = serializers.SerializerMethodField()

    def get_assetstr(self, obj):
        return str(obj.getAssetInstance())

    class Meta:
        model = Asset


class AssetPackageVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetPackageVersion
        fields = ("idx", "size", "version", "release")


class AssetPackageSerializer(serializers.ModelSerializer):
    versions = AssetPackageVersionSerializer(many=True)

    class Meta:
        model = AssetPackage
        fields = ("idx", "name")


class AssetRunSerializer(serializers.ModelSerializer):
    device = serializers.SerializerMethodField()
    # asset_set = AssetSerializer(many=True)
    assets = serializers.SerializerMethodField()
    # packages = AssetPackageVersionSerializer(many=True)

    def get_assets(self, obj):
        return [str(pkg) for pkg in obj.generate_assets_no_save()]

    def get_device(self, obj):
        if self.context and "device" in self.context:
            return self.context["device"]
        else:
            return 0

    class Meta:
        model = AssetRun
        fields = ("idx", "device", "run_index", "run_type", "assets",
                  "run_start_time", "run_end_time", "packages")
