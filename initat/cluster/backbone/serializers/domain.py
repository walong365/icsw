# Copyright (C) 2014 Andreas Lang-Nevyjel, init.at
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
""" serializer definitions for domain elements """

from rest_framework import serializers
from initat.cluster.backbone.models import domain_tree_node, category, location_gfx, device_mon_location

__all__ = [
    "domain_tree_node_serializer",
    "category_serializer",
    "location_gfx_serializer",
    "device_mon_location_serializer",
]


class domain_tree_node_serializer(serializers.ModelSerializer):
    tree_info = serializers.CharField(source="__unicode__", read_only=True)

    class Meta:
        model = domain_tree_node


class category_serializer(serializers.ModelSerializer):

    class Meta:
        model = category


class location_gfx_serializer(serializers.ModelSerializer):
    icon_url = serializers.URLField(source="get_icon_url", read_only=True)
    image_url = serializers.URLField(source="get_image_url", read_only=True)

    class Meta:
        model = location_gfx


class device_mon_location_serializer(serializers.ModelSerializer):
    # device_name = serializers.CharField(source="get_device_name")

    class Meta:
        model = device_mon_location
