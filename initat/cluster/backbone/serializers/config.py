# Copyright (C) 2001-2014,2016-2017 Andreas Lang-Nevyjel, init.at
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
#
# -*- coding: utf-8 -*-
#
""" model serializers for config and upload"""

from rest_framework import serializers

from initat.cluster.backbone.models import config, config_str, \
    config_int, config_bool, config_blob, config_script, device_config, \
    ConfigServiceEnum
from initat.cluster.backbone.serializers.monitoring import mon_check_command_serializer

__all__ = [
    "config_str_serializer",
    "config_int_serializer",
    "config_bool_serializer",
    "config_blob_serializer",
    "config_script_serializer",
    "config_serializer",
    "config_dump_serializer",
    "device_config_serializer",
    "ConfigServiceEnumSerializer",
]


class config_str_serializer(serializers.ModelSerializer):
    object_type = serializers.CharField(source="get_object_type", read_only=True)

    class Meta:
        fields = "__all__"
        model = config_str


class config_int_serializer(serializers.ModelSerializer):
    object_type = serializers.CharField(source="get_object_type", read_only=True)

    class Meta:
        fields = "__all__"
        model = config_int


class config_blob_serializer(serializers.ModelSerializer):
    object_type = serializers.CharField(source="get_object_type", read_only=True)

    class Meta:
        fields = "__all__"
        model = config_blob


class config_bool_serializer(serializers.ModelSerializer):
    object_type = serializers.CharField(source="get_object_type", read_only=True)

    class Meta:
        fields = "__all__"
        model = config_bool


class config_script_serializer(serializers.ModelSerializer):
    object_type = serializers.CharField(source="get_object_type", read_only=True)

    class Meta:
        fields = "__all__"
        model = config_script


# should reside in __init__.py (device related)
class device_config_serializer(serializers.ModelSerializer):
    class Meta:
        fields = "__all__"
        model = device_config


class ConfigServiceEnumSerializer(serializers.ModelSerializer):
    class Meta:
        fields = "__all__"
        model = ConfigServiceEnum


class config_serializer(serializers.ModelSerializer):
    config_str_set = config_str_serializer(many=True, read_only=True)
    config_int_set = config_int_serializer(many=True, read_only=True)
    config_blob_set = config_blob_serializer(many=True, read_only=True)
    config_bool_set = config_bool_serializer(many=True, read_only=True)
    config_script_set = config_script_serializer(many=True, read_only=True)
    mcc_rel = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    device_config_set = device_config_serializer(many=True, read_only=True)
    # categories only as flat list, no nesting

    class Meta:
        fields = "__all__"
        model = config


class config_dump_serializer(serializers.ModelSerializer):
    config_str_set = config_str_serializer(many=True, allow_null=True)
    config_int_set = config_int_serializer(many=True, allow_null=True)
    config_blob_set = config_blob_serializer(many=True, allow_null=True)
    config_bool_set = config_bool_serializer(many=True, allow_null=True)
    config_script_set = config_script_serializer(many=True, allow_null=True)
    # mon_check_command_set = mon_check_command_serializer(many=True, allow_null=True)
    # categories only as flat list, no nesting

    def create(self, validated_data):
        _sets = {}
        for key in validated_data.keys():
            # remove all subsets, needed because of limitations in DRF
            if key.endswith("_set"):
                _sets[key] = validated_data[key]
                del validated_data[key]
        print("V=", validated_data)
        print("C")
        return config(**validated_data)

    class Meta:
        model = config
        fields = (
            "idx", "name", "description", "priority", "enabled", "categories",
            "config_str_set", "config_int_set", "config_blob_set", "config_bool_set",
            "config_script_set", "mon_check_command_set", "server_config",
        )
