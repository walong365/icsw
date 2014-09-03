# Copyright (C) 2001-2014 Andreas Lang-Nevyjel, init.at
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
""" model serializers """

from django.core.cache import cache
from django.core.exceptions import ValidationError, ImproperlyConfigured
from django.core.signals import request_finished, request_started
from django.db import models
from django.db.models import Q, signals
from django.dispatch import receiver
from initat.cluster.backbone.middleware import thread_local_middleware, \
    _thread_local
from initat.cluster.backbone.models.functions import _check_empty_string, \
    _check_float, _check_integer, _check_non_empty_string, to_system_tz, \
    get_change_reset_list, get_related_models, cluster_timezone
from lxml import etree  # @UnresolvedImport
from lxml.builder import E  # @UnresolvedImport
from rest_framework import serializers
import crypt
import datetime
import ipvx_tools
import json
import logging
import logging_tools
import net_tools
import process_tools
import pytz
import random
import re
import server_command
import time
import uuid

from initat.cluster.backbone.models import device, config, config_int, config_str, config_blob, \
    architecture, config_catalog, device_selection, device_config, device_variable, partition, \
    partition_fs, lvm_lv, lvm_vg, partition_disc, partition_table, sys_partition, log_source, \
    log_status, device_group, cluster_license, image, device_type, cluster_setting, mac_ignore, \
    macbootlog, status, wc_files, package, package_repo, package_device_connection, mon_dist_slave, \
    mon_dist_master, config_bool, config_script, config_script_hint, cd_connection

from initat.cluster.backbone.serializers.domain import *  # @UnusedWildImport
from initat.cluster.backbone.serializers.monitoring import *  # @UnusedWildImport
from initat.cluster.backbone.serializers.network import *  # @UnusedWildImport
from initat.cluster.backbone.serializers.package import *  # @UnusedWildImport
from initat.cluster.backbone.serializers.user import *  # @UnusedWildImport
from initat.cluster.backbone.serializers.background import *  # @UnusedWildImport
from initat.cluster.backbone.serializers.hints import *  # @UnusedWildImport
from initat.cluster.backbone.serializers.rms import *  # @UnusedWildImport


class architecture_serializer(serializers.ModelSerializer):
    class Meta:
        model = architecture


class config_catalog_serializer(serializers.ModelSerializer):
    class Meta:
        model = config_catalog


class device_variable_serializer(serializers.ModelSerializer):
    class Meta:
        model = device_variable


class device_config_serializer(serializers.ModelSerializer):
    class Meta:
        model = device_config


class device_config_help_serializer(serializers.ModelSerializer):
    info_string = serializers.Field(source="home_info")
    homeexport = serializers.SerializerMethodField("get_homeexport")
    createdir = serializers.SerializerMethodField("get_createdir")
    name = serializers.SerializerMethodField("get_name")
    full_name = serializers.SerializerMethodField("get_full_name")

    def get_name(self, obj):
        return obj.info_dict["name"]

    def get_full_name(self, obj):
        return obj.info_dict["full_name"]

    def get_createdir(self, obj):
        return obj.info_dict["createdir"]

    def get_homeexport(self, obj):
        return obj.info_dict["homeexport"]

    class Meta:
        model = device_config
        fields = ("idx", "info_string", "homeexport", "createdir", "name", "full_name")


class partition_serializer(serializers.ModelSerializer):
    class Meta:
        model = partition


class partition_fs_serializer(serializers.ModelSerializer):
    need_mountpoint = serializers.Field(source="need_mountpoint")

    class Meta:
        model = partition_fs


class sys_partition_serializer(serializers.ModelSerializer):
    class Meta:
        model = sys_partition


class lvm_lv_serializer(serializers.ModelSerializer):
    class Meta:
        model = lvm_lv


class lvm_vg_serializer(serializers.ModelSerializer):
    class Meta:
        model = lvm_vg


class partition_disc_serializer_save(serializers.ModelSerializer):
    class Meta:
        model = partition_disc
        fields = ("disc", "label_type",)


class partition_disc_serializer_create(serializers.ModelSerializer):
    # partition_set = partition_serializer(many=True)
    class Meta:
        model = partition_disc
        # fields = ("disc", "partition_table")


class partition_disc_serializer(serializers.ModelSerializer):
    partition_set = partition_serializer(many=True)

    class Meta:
        model = partition_disc


class partition_table_serializer(serializers.ModelSerializer):
    partition_disc_set = partition_disc_serializer(many=True)
    sys_partition_set = sys_partition_serializer(many=True)
    lvm_lv_set = lvm_lv_serializer(many=True)
    lvm_vg_set = lvm_vg_serializer(many=True)

    class Meta:
        model = partition_table
        fields = (
            "partition_disc_set", "lvm_lv_set", "lvm_vg_set", "name", "idx", "description", "valid",
            "enabled", "nodeboot", "act_partition_table", "new_partition_table", "sys_partition_set",
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


class device_selection_serializer(serializers.Serializer):
    idx = serializers.IntegerField()
    sel_type = serializers.CharField(max_length=2)

    class Meta:
        model = device_selection


class device_group_serializer(serializers.ModelSerializer):
    def validate(self, in_dict):
        if "description" not in in_dict:
            in_dict["description"] = ""
        return in_dict

    class Meta:
        model = device_group


class cluster_license_serializer(serializers.ModelSerializer):
    class Meta:
        model = cluster_license


class cluster_setting_serializer(serializers.ModelSerializer):
    cluster_license_set = cluster_license_serializer(many=True)

    class Meta:
        model = cluster_setting


class device_type_serializer(serializers.ModelSerializer):
    class Meta:
        model = device_type


class image_serializer(serializers.ModelSerializer):
    class Meta:
        model = image
        fields = (
            "idx", "name", "enabled", "version", "release",
            "sys_vendor", "sys_version", "sys_release", "size_string", "size", "architecture",
            "new_image", "act_image",
        )


class log_source_serializer(serializers.ModelSerializer):
    class Meta:
        model = log_source


class log_status_serializer(serializers.ModelSerializer):
    class Meta:
        model = log_status


class mac_ignore_serializer(serializers.ModelSerializer):
    class Meta:
        model = mac_ignore


class macbootlog_serializer(serializers.ModelSerializer):
    created = serializers.Field(source="get_created")
    device_name = serializers.Field(source="get_device_name")

    class Meta:
        model = macbootlog


class status_serializer(serializers.ModelSerializer):
    info_string = serializers.Field(source="info_string")

    class Meta:
        model = status


class wc_files_serializer(serializers.ModelSerializer):
    class Meta:
        model = wc_files


class config_str_serializer(serializers.ModelSerializer):
    object_type = serializers.Field(source="get_object_type")

    class Meta:
        model = config_str


class config_int_serializer(serializers.ModelSerializer):
    object_type = serializers.Field(source="get_object_type")

    class Meta:
        model = config_int


class config_blob_serializer(serializers.ModelSerializer):
    object_type = serializers.Field(source="get_object_type")

    class Meta:
        model = config_blob


class config_bool_serializer(serializers.ModelSerializer):
    object_type = serializers.Field(source="get_object_type")

    class Meta:
        model = config_bool


class config_script_serializer(serializers.ModelSerializer):
    object_type = serializers.Field(source="get_object_type")

    class Meta:
        model = config_script


class config_serializer(serializers.ModelSerializer):
    config_str_set = config_str_serializer(many=True, read_only=True)
    config_int_set = config_int_serializer(many=True, read_only=True)
    config_blob_set = config_blob_serializer(many=True, read_only=True)
    config_bool_set = config_bool_serializer(many=True, read_only=True)
    config_script_set = config_script_serializer(many=True, read_only=True)
    mon_check_command_set = mon_check_command_serializer(many=True, read_only=True)
    usecount = serializers.Field(source="get_use_count")
    # categories only as flat list, no nesting

    class Meta:
        model = config


class config_str_nat_serializer(serializers.ModelSerializer):
    config = serializers.SlugRelatedField(slug_field="name")

    class Meta:
        model = config_str


class config_int_nat_serializer(serializers.ModelSerializer):
    config = serializers.SlugRelatedField(slug_field="name")

    class Meta:
        model = config_int


class config_bool_nat_serializer(serializers.ModelSerializer):
    config = serializers.SlugRelatedField(slug_field="name")

    class Meta:
        model = config_bool


class config_blob_nat_serializer(serializers.ModelSerializer):
    config = serializers.SlugRelatedField(slug_field="name")

    class Meta:
        model = config_blob


class config_script_nat_serializer(serializers.ModelSerializer):
    config = serializers.SlugRelatedField(slug_field="name")

    class Meta:
        model = config_script


class config_dump_serializer(serializers.ModelSerializer):
    config_str_set = config_str_nat_serializer(many=True)
    config_int_set = config_int_nat_serializer(many=True)
    config_blob_set = config_blob_nat_serializer(many=True)
    config_bool_set = config_bool_nat_serializer(many=True)
    config_script_set = config_script_nat_serializer(many=True)
    mon_check_command_set = mon_check_command_nat_serializer(many=True)
    # categories only as flat list, no nesting

    class Meta:
        model = config
        fields = (
            "idx", "name", "description", "priority", "enabled", "categories",
            "config_str_set", "config_int_set", "config_blob_set", "config_bool_set",
            "config_script_set", "mon_check_command_set",
        )


class mon_dist_slave_serializer(serializers.ModelSerializer):
    class Meta:
        model = mon_dist_slave


class mon_dist_master_serializer(serializers.ModelSerializer):
    mon_dist_slave_set = mon_dist_slave_serializer(many=True)

    class Meta:
        model = mon_dist_master


class device_serializer(serializers.ModelSerializer):
    full_name = serializers.Field(source="full_name")
    is_meta_device = serializers.Field(source="is_meta_device")
    is_cluster_device_group = serializers.Field(source="is_cluster_device_group")
    device_type_identifier = serializers.Field(source="device_type_identifier")
    device_group_name = serializers.Field(source="device_group_name")
    access_level = serializers.SerializerMethodField("get_access_level")
    access_levels = serializers.SerializerMethodField("get_access_levels")
    root_passwd_set = serializers.Field(source="root_passwd_set")
    act_partition_table = partition_table_serializer(read_only=True)
    partition_table = partition_table_serializer()
    netdevice_set = netdevice_serializer(many=True)
    monitoring_hint_set = monitoring_hint_serializer(many=True)
    device_variable_set = device_variable_serializer(many=True)
    device_config_set = device_config_serializer(many=True)
    package_device_connection_set = package_device_connection_serializer(many=True)
    latest_contact = serializers.Field(source="latest_contact")
    client_version = serializers.Field(source="client_version")
    monitor_type = serializers.Field(source="get_monitor_type")

    def __init__(self, *args, **kwargs):
        fields = kwargs.get("context", {}).pop("fields", [])
        serializers.ModelSerializer.__init__(self, *args, **kwargs)
        _optional_fields = set(
            [
                "act_partition_table", "partition_table", "netdevice_set", "categories", "device_variable_set", "device_config_set",
                "package_device_connection_set", "latest_contact", "client_version", "monitor_type", "monitoring_hint_set"
            ]
        )
        for _to_remove in _optional_fields - set(fields):
            # in case we have been subclassed
            if _to_remove in self.fields:
                self.fields.pop(_to_remove)

    def get_access_level(self, obj):
        if "olp" in self.context:
            return self.context["request"].user.get_object_perm_level(self.context["olp"], obj)
        return -1

    def get_access_levels(self, obj):
        return ",".join(["{}={:d}".format(key, value) for key, value in self.context["request"].user.get_object_access_levels(obj).iteritems()])

    class Meta:
        model = device
        fields = (
            "idx", "name", "device_group", "device_type",
            "comment", "full_name", "domain_tree_node", "enabled",
            "monitor_checks", "mon_device_templ", "mon_device_esc_templ", "md_cache_mode",
            "enable_perfdata", "flap_detection_enabled",
            "automap_root_nagvis", "nagvis_parent", "monitor_server", "mon_ext_host",
            "is_meta_device", "device_type_identifier", "device_group_name", "bootserver",
            "is_cluster_device_group", "root_passwd_set", "has_active_rrds",
            "curl", "mon_resolve_name", "access_level", "access_levels", "store_rrd_data",
            "access_level", "access_levels", "store_rrd_data",
            # disk info
            "partition_table", "act_partition_table",
            # for network view
            "new_state", "prod_link", "dhcp_mac", "dhcp_write", "netdevice_set",
            # for categories
            "categories",
            # variables
            "device_variable_set",
            # config
            "device_config_set",
            # package info
            "package_device_connection_set", "latest_contact", "client_version",
            # monitor type
            "monitor_type",
            # monitoring hint
            "monitoring_hint_set",
            "uuid",
        )
        read_only_fields = ("uuid",)


class cd_connection_serializer(serializers.ModelSerializer):
    class Meta:
        model = cd_connection


class device_serializer_package_state(device_serializer):
    class Meta:
        model = device
        fields = (
            "idx", "name", "device_group", "device_type",
            "comment", "full_name", "domain_tree_node", "enabled",
            "package_device_connection_set", "latest_contact", "is_meta_device",
            "access_level", "access_levels", "client_version",
        )


class device_serializer_only_boot(serializers.ModelSerializer):
    class Meta:
        model = device
        fields = ("idx", "dhcp_mac", "dhcp_write",)


class device_serializer_monitoring(device_serializer):
    # only used for updating (no read)
    class Meta:
        model = device
        fields = (
            "monitor_checks", "mon_device_templ", "mon_device_esc_templ", "md_cache_mode",
            "act_partition_table", "enable_perfdata", "flap_detection_enabled",
            "automap_root_nagvis", "nagvis_parent", "monitor_server", "mon_ext_host",
            "mon_resolve_name", "access_level", "access_levels", "store_rrd_data",
        )
        read_only_fields = ("act_partition_table",)


class cd_connection_serializer_boot(serializers.ModelSerializer):
    parent = device_serializer()
    child = device_serializer()

    class Meta:
        model = cd_connection


class device_serializer_boot(device_serializer):
    partition_table = serializers.SerializerMethodField("get_partition_table")
    # current partition table
    act_partition_table = serializers.SerializerMethodField("get_act_partition_table")
    bootnetdevice = netdevice_serializer()
    valid_state = serializers.Field(source="valid_state")
    uptime = serializers.Field(source="get_uptime")
    uptime_valid = serializers.Field(source="uptime_valid")
    network = serializers.Field(source="network")
    net_state = serializers.Field(source="net_state")
    master_connections = cd_connection_serializer_boot(source="get_master_cons", many=True)
    slave_connections = cd_connection_serializer_boot(source="get_slave_cons", many=True)

    def get_partition_table(self, obj):
        return obj.partition_table_id or None

    def get_act_partition_table(self, obj):
        return obj.act_partition_table_id or None

    class Meta:
        model = device
        fields = (
            "idx", "name", "full_name", "device_group_name", "access_level", "access_levels",
            # meta-fields
            "valid_state", "network", "net_state", "uptime", "uptime_valid",
            "recvstate", "reqstate",
            # target state
            "new_state", "prod_link",
            # partition
            "act_partition_table", "partition_table",
            # image
            "act_image", "new_image", "imageversion",
            # kernel
            "act_kernel", "new_kernel", "stage1_flavour", "kernel_append",
            # boot device
            "dhcp_mac", "dhcp_write", "dhcp_written", "dhcp_error", "bootnetdevice", "bootnetdevice",
            # connections
            "master_connections", "slave_connections",
        )
