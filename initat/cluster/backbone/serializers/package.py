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
""" serializer definitions for package elements """

from rest_framework import serializers

from initat.cluster.backbone.models import package_service, package_repo, package_search, package_search_result, \
    package_device_connection, package

__all__ = [
    "package_serializer",
    "package_repo_serializer",
    "package_search_serializer",
    "package_search_result_serializer",
    "package_service_serializer",
    "package_device_connection_serializer",
    "package_device_connection_wp_serializer",
]


class package_service_serializer(serializers.ModelSerializer):
    class Meta:
        model = package_service


class package_repo_serializer(serializers.ModelSerializer):
    service_name = serializers.CharField(source="get_service_name", read_only=True)

    class Meta:
        model = package_repo


class package_search_serializer(serializers.ModelSerializer):
    class Meta:
        model = package_search


class package_search_result_serializer(serializers.ModelSerializer):
    class Meta:
        model = package_search_result


class package_device_connection_serializer(serializers.ModelSerializer):
    class Meta:
        model = package_device_connection


class package_serializer(serializers.ModelSerializer):
    target_repo_name = serializers.CharField(read_only=True)

    class Meta:
        model = package


class package_device_connection_wp_serializer(serializers.ModelSerializer):
    package = package_serializer()

    class Meta:
        model = package_device_connection
