# -*- coding: utf-8 -*-
#
# Copyright (C) 2014 Andreas Lang-Nevyjel
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
""" user definition serializers """

from django.contrib.contenttypes.models import ContentType
from rest_framework import serializers

from initat.cluster.backbone.models import group, user, csw_permission, csw_object_permission, \
    user_quota_setting, \
    group_quota_setting, user_scan_result, user_scan_run, virtual_desktop_protocol, virtual_desktop_user_setting, \
    window_manager, UserLogEntry, user_variable, Role, RolePermission, RoleObjectPermission

__all__ = [
    "csw_permission_serializer",
    "csw_object_permission_serializer",
    "RoleSerializer",
    "RolePermissionSerializer",
    "RoleObjectPermissionSerializer",
    "user_serializer",
    "user_flat_serializer",
    "group_serializer",
    "group_flat_serializer",
    # "group_permission_serializer",
    # "group_object_permission_serializer",
    # "user_permission_serializer",
    # "user_object_permission_serializer",
    "user_quota_setting_serializer",
    "group_quota_setting_serializer",
    "user_scan_run_serializer",
    "user_scan_result_serializer",
    "virtual_desktop_user_setting_serializer",
    "virtual_desktop_protocol_serializer",
    "window_manager_serializer",
    "UserLogEntrySerializer",
    "user_variable_serializer",
]


class content_type_serializer(serializers.ModelSerializer):
    class Meta:
        fields = "__all__"
        model = ContentType


class csw_permission_serializer(serializers.ModelSerializer):
    content_type = content_type_serializer()

    class Meta:
        fields = "__all__"
        model = csw_permission


class csw_object_permission_serializer(serializers.ModelSerializer):
    class Meta:
        fields = "__all__"
        model = csw_object_permission


class RolePermissionSerializer(serializers.ModelSerializer):
    class Meta:
        fields = "__all__"
        model = RolePermission


class RoleObjectPermissionSerializer(serializers.ModelSerializer):
    csw_object_permission = csw_object_permission_serializer()

    def create(self, validated_data):
        _obj_perm = validated_data.pop("csw_object_permission")
        _new_csw_obj = csw_object_permission.objects.create(**_obj_perm)
        _new_role = RoleObjectPermission.objects.create(csw_object_permission=_new_csw_obj, **validated_data)
        return _new_role

    class Meta:
        fields = "__all__"
        model = RoleObjectPermission


class user_quota_setting_serializer(serializers.ModelSerializer):
    class Meta:
        fields = "__all__"
        model = user_quota_setting


class group_quota_setting_serializer(serializers.ModelSerializer):
    class Meta:
        fields = "__all__"
        model = group_quota_setting


class user_scan_result_serializer(serializers.ModelSerializer):
    class Meta:
        fields = "__all__"
        model = user_scan_result


class user_scan_run_serializer(serializers.ModelSerializer):
    user_scan_result_set = user_scan_result_serializer(many=True, read_only=True)

    class Meta:
        fields = "__all__"
        model = user_scan_run


class user_variable_serializer(serializers.ModelSerializer):

    class Meta:
        fields = "__all__"
        model = user_variable


class user_serializer(serializers.ModelSerializer):
    # object_perms = csw_object_permission_serializer(many=True, read_only=True)
    user_quota_setting_set = user_quota_setting_serializer(many=True, read_only=True)
    user_scan_run_set = user_scan_run_serializer(many=True, read_only=True)
    info = serializers.CharField(source="get_info", read_only=True)
    login_name = serializers.SerializerMethodField()
    user_variable_set = user_variable_serializer(many=True, read_only=True)
    session_id = serializers.SerializerMethodField()
    is_anonymous = serializers.SerializerMethodField()
    is_authenticated = serializers.SerializerMethodField()

    def get_session_id(self, obj):
        _req = self.context["request"]
        if hasattr(_req, "session"):
            _key = _req.session.session_key
        else:
            _key = ""
        return _key

    def get_login_name(self, obj):
        _req = self.context["request"]
        _login_name = obj.login
        if hasattr(_req, "session"):
            _login_name = _req.session.get("login_name", _login_name)
        return _login_name

    def get_is_anonymous(self, obj):
        return self.context.get("is_anonymous", False)

    def get_is_authenticated(self, obj):
        return self.context.get("is_authenticated", True)

    class Meta:
        model = user
        fields = (
            "idx", "login", "uid", "group", "first_name", "last_name", "shell",
            "title", "email", "pager", "comment", "tel", "password", "active", "export",
            "secondary_groups",
            "aliases", "db_is_auth_for_password", "is_superuser",
            "home_dir_created", "user_quota_setting_set", "info", "scan_user_home", "scan_depth",
            "only_webfrontend", "home", "user_scan_run_set", "login_name", "create_rms_user",
            "user_variable_set", "session_id", "ui_theme_selection",
            "is_anonymous", "is_authenticated", "roles",
        )


class user_flat_serializer(serializers.ModelSerializer):

    class Meta:
        fields = "__all__"
        model = user


class group_flat_serializer(serializers.ModelSerializer):
    class Meta:
        fields = "__all__"
        model = group


class group_serializer(serializers.ModelSerializer):
    group_quota_setting_set = group_quota_setting_serializer(many=True, read_only=True)

    class Meta:
        model = group
        fields = (
            "groupname", "active", "gid", "idx", "parent_group",
            "homestart", "tel", "title", "email", "pager", "comment",
            "roles", "group_quota_setting_set",
        )


class RoleSerializer(serializers.ModelSerializer):
    rolepermission_set = RolePermissionSerializer(many=True, read_only=True)
    roleobjectpermission_set = RoleObjectPermissionSerializer(many=True, read_only=True)

    class Meta:
        model = Role
        fields = (
            "idx", "name", "description", "active", "create_user",
            "rolepermission_set", "roleobjectpermission_set",
        )


class virtual_desktop_user_setting_serializer(serializers.ModelSerializer):
    # rest should not change these
    pid = serializers.IntegerField(read_only=True)
    effective_port = serializers.IntegerField(read_only=True)
    process_name = serializers.CharField(read_only=True)
    last_start_attempt = serializers.DateTimeField(read_only=True)

    websockify_pid = serializers.IntegerField(read_only=True)
    websockify_process_name = serializers.CharField(read_only=True)
    websockify_effective_port = serializers.IntegerField(read_only=True)
    password = serializers.CharField(read_only=True)

    state = serializers.IntegerField(read_only=True)

    vnc_obfuscated_password = serializers.ReadOnlyField(source="get_vnc_obfuscated_password")
    state_description = serializers.ReadOnlyField(source="get_state_description")

    class Meta:
        fields = "__all__"
        model = virtual_desktop_user_setting


class virtual_desktop_protocol_serializer(serializers.ModelSerializer):
    class Meta:
        fields = "__all__"
        model = virtual_desktop_protocol


class window_manager_serializer(serializers.ModelSerializer):
    class Meta:
        fields = "__all__"
        model = window_manager


class UserLogEntrySerializer(serializers.ModelSerializer):
    class Meta:
        fields = "__all__"
        model = UserLogEntry
