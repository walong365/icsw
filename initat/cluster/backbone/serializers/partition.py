# Copyright (C) 2001-2016 Andreas Lang-Nevyjel, init.at
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
""" model serializers for partition setup """

from rest_framework import serializers

from initat.cluster.backbone.models import partition, partition_fs, lvm_lv, lvm_vg, \
    partition_disc, partition_table, sys_partition


__all__ = [
    "partition_serializer",
    "partition_fs_serializer",
    "sys_partition_serializer",
    "lvm_lv_serializer",
    "lvm_vg_serializer",
    "partition_disc_serializer",
    "partition_disc_serializer_save",
    "partition_disc_serializer_create",
    "partition_table_serializer",
    "partition_table_serializer_save",
]


class partition_serializer(serializers.ModelSerializer):
    class Meta:
        fields = "__all__"
        model = partition


class partition_fs_serializer(serializers.ModelSerializer):
    need_mountpoint = serializers.ReadOnlyField()

    class Meta:
        fields = "__all__"
        model = partition_fs


class sys_partition_serializer(serializers.ModelSerializer):
    class Meta:
        fields = "__all__"
        model = sys_partition


class lvm_lv_serializer(serializers.ModelSerializer):
    class Meta:
        fields = "__all__"
        model = lvm_lv


class lvm_vg_serializer(serializers.ModelSerializer):
    class Meta:
        fields = "__all__"
        model = lvm_vg


class partition_disc_serializer_save(serializers.ModelSerializer):
    class Meta:
        model = partition_disc
        fields = ("disc", "label_type",)


class partition_disc_serializer_create(serializers.ModelSerializer):
    # partition_set = partition_serializer(many=True)
    class Meta:
        fields = "__all__"
        model = partition_disc


class partition_disc_serializer(serializers.ModelSerializer):
    partition_set = partition_serializer(many=True)

    class Meta:
        fields = "__all__"
        model = partition_disc


class partition_table_serializer(serializers.ModelSerializer):

    partition_disc_set = partition_disc_serializer(many=True)
    sys_partition_set = sys_partition_serializer(many=True)
    lvm_lv_set = lvm_lv_serializer(many=True)
    lvm_vg_set = lvm_vg_serializer(many=True)
    device = serializers.SerializerMethodField()

    def create(self, obj):
        name = obj['name']
        enabled = obj['enabled']
        nodeboot = obj['nodeboot']
        description = obj['description'] if 'description' in obj else ""
        return partition_table.objects.create(
            name=name,
            enabled=enabled,
            nodeboot=nodeboot,
            description=description,
        )

    def get_device(self, obj):
        if self.context and "device" in self.context:
            return self.context["device"]
        else:
            return 0

    class Meta:
        model = partition_table
        fields = (
            "partition_disc_set", "lvm_lv_set", "lvm_vg_set", "name", "idx", "description", "valid",
            "enabled", "nodeboot", "sys_partition_set",
            "device",
        )
        # otherwise the REST framework would try to store lvm_lv and lvm_vg
        # read_only_fields = ("lvm_lv_set", "lvm_vg_set",) # "partition_disc_set",)


class partition_table_serializer_save(serializers.ModelSerializer):
    class Meta:
        model = partition_table
        fields = (
            "name", "idx", "description", "valid",
            "enabled", "nodeboot",
        )
