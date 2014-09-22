# -*- coding: utf-8 -*-
#
# Copyright (C) 2014 Andreas Lang-Nevyjel
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
""" user definition serializers """

from django.contrib.contenttypes.models import ContentType
from rest_framework import serializers
from initat.cluster.backbone.models import group, user, csw_permission, group_permission, csw_object_permission, \
    group_object_permission, user_permission, user_object_permission, user_quota_setting, \
    group_quota_setting

__all__ = [
    "csw_permission_serializer",
    "csw_object_permission_serializer",
    "user_serializer",
    "group_serializer",
    "group_permission_serializer",
    "group_object_permission_serializer",
    "user_permission_serializer",
    "user_object_permission_serializer",
    "user_quota_setting_serializer",
    "group_quota_setting_serializer",
]


class content_type_serializer(serializers.ModelSerializer):
    class Meta:
        model = ContentType


class csw_permission_serializer(serializers.ModelSerializer):
    content_type = content_type_serializer()

    class Meta:
        model = csw_permission


class csw_object_permission_serializer(serializers.ModelSerializer):
    class Meta:
        model = csw_object_permission


class group_permission_serializer(serializers.ModelSerializer):
    class Meta:
        model = group_permission


class group_object_permission_serializer(serializers.ModelSerializer):
    # needed to resolve csw_permission
    csw_object_permission = csw_object_permission_serializer()

    class Meta:
        model = group_object_permission


class user_permission_serializer(serializers.ModelSerializer):
    class Meta:
        model = user_permission


class user_object_permission_serializer(serializers.ModelSerializer):
    # needed to resolve csw_permission
    csw_object_permission = csw_object_permission_serializer()

    class Meta:
        model = user_object_permission


class user_quota_setting_serializer(serializers.ModelSerializer):
    class Meta:
        model = user_quota_setting


class group_quota_setting_serializer(serializers.ModelSerializer):
    class Meta:
        model = group_quota_setting


class user_serializer(serializers.ModelSerializer):
    # object_perms = csw_object_permission_serializer(many=True, read_only=True)
    user_permission_set = user_permission_serializer(many=True, read_only=True)
    user_object_permission_set = user_object_permission_serializer(many=True, read_only=True)
    user_quota_setting_set = user_quota_setting_serializer(many=True, read_only=True)

    class Meta:
        model = user
        fields = (
            "idx", "login", "uid", "group", "first_name", "last_name", "shell",
            "title", "email", "pager", "comment", "tel", "password", "active", "export",
            "secondary_groups", "user_permission_set", "user_object_permission_set",
            "allowed_device_groups", "aliases", "db_is_auth_for_password", "is_superuser",
            "home_dir_created", "user_quota_setting_set",
        )


class user_flat_serializer(serializers.ModelSerializer):
    class Meta:
        model = user
        fields = (
            "idx", "login", "uid", "group", "first_name", "last_name", "shell",
            "title", "email", "pager", "comment", "tel", "password", "active", "export",
            "aliases", "db_is_auth_for_password", "is_superuser", "home_dir_created",
        )


class group_serializer(serializers.ModelSerializer):
    group_permission_set = group_permission_serializer(many=True, read_only=True)
    group_object_permission_set = group_object_permission_serializer(many=True, read_only=True)
    group_quota_setting_set = group_quota_setting_serializer(many=True, read_only=True)

    class Meta:
        model = group
        fields = (
            "groupname", "active", "gid", "idx", "parent_group",
            "homestart", "tel", "title", "email", "pager", "comment",
            "allowed_device_groups", "group_permission_set", "group_object_permission_set",
            "group_quota_setting_set",
        )
