# Copyright (C) 2001-2015 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of cluster-backbone-sql
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
#
# -*- coding: utf-8 -*-
#
""" model serializers for setup tasks (kernel, image, architecture) """

from initat.cluster.backbone.models import kernel, image, architecture
from rest_framework import serializers

__all__ = [
    "architecture_serializer",
    "image_serializer",
    "kernel_serializer",
]


class architecture_serializer(serializers.ModelSerializer):
    class Meta:
        model = architecture


class image_serializer(serializers.ModelSerializer):
    class Meta:
        model = image
        # set fields explicitly to get references to history
        fields = (
            "idx", "name", "enabled", "version", "release", "builds",
            "sys_vendor", "sys_version", "sys_release", "size_string", "size", "architecture",
            "new_image", "imagedevicehistory_set",
        )
        read_only_fields = ("imagedevicehistory_set", "new_image",)


class kernel_serializer(serializers.ModelSerializer):
    class Meta:
        model = kernel
        # set fields explicitly to get references to history
        fields = (
            "idx", "name", "enabled", "kernel_version", "version", "display_name",
            "release", "bitcount", "initrd_build_set", "kernel_build_set", "initrd_built",
            "new_kernel", "comment", "target_module_list", "module_list",
            "stage1_lo_present", "stage1_cpio_present", "stage1_cramfs_present", "stage2_present",
            "kerneldevicehistory_set",
        )
