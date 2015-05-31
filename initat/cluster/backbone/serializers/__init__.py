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
from initat.tools import ipvx_tools
import json
import logging
from initat.tools import logging_tools
from initat.tools import net_tools
from initat.tools import process_tools
import pytz
import random
import re
from initat.tools import server_command
import time
import uuid

from initat.cluster.backbone.models import device, device_selection, device_config, device_variable, \
    LogSource, LogLevel, device_group, mac_ignore, \
    macbootlog, status, wc_files, mon_dist_slave, mon_dist_master, cd_connection, \
    quota_capable_blockdevice, window_manager, virtual_desktop_protocol, virtual_desktop_user_setting, \
    DeviceSNMPInfo, DeleteRequest

from initat.cluster.backbone.serializers.capability import *  # @UnusedWildImport
from initat.cluster.backbone.serializers.domain import *  # @UnusedWildImport
from initat.cluster.backbone.serializers.config import *  # @UnusedWildImport
from initat.cluster.backbone.serializers.monitoring import *  # @UnusedWildImport
from initat.cluster.backbone.serializers.network import *  # @UnusedWildImport
from initat.cluster.backbone.serializers.package import *  # @UnusedWildImport
from initat.cluster.backbone.serializers.user import *  # @UnusedWildImport
from initat.cluster.backbone.serializers.background import *  # @UnusedWildImport
from initat.cluster.backbone.serializers.hints import *  # @UnusedWildImport
from initat.cluster.backbone.serializers.rms import *  # @UnusedWildImport
from initat.cluster.backbone.serializers.setup import *  # @UnusedWildImport
from initat.cluster.backbone.serializers.partition import *  # @UnusedWildImport
from initat.cluster.backbone.serializers.kpi import *  # @UnusedWildImport


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


class LogSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = LogSource


class LogLevelSerializer(serializers.ModelSerializer):
    class Meta:
        model = LogLevel


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


class mon_dist_slave_serializer(serializers.ModelSerializer):
    class Meta:
        model = mon_dist_slave


class mon_dist_master_serializer(serializers.ModelSerializer):
    mon_dist_slave_set = mon_dist_slave_serializer(many=True)

    class Meta:
        model = mon_dist_master


class DeviceSNMPInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceSNMPInfo


class device_serializer(serializers.ModelSerializer):
    full_name = serializers.Field(source="full_name")
    is_meta_device = serializers.Field(source="is_meta_device")
    is_cluster_device_group = serializers.Field(source="is_cluster_device_group")
    device_group_name = serializers.Field(source="device_group_name")
    access_level = serializers.SerializerMethodField("get_access_level")
    access_levels = serializers.SerializerMethodField("get_access_levels")
    root_passwd_set = serializers.Field(source="root_passwd_set")
    act_partition_table = partition_table_serializer(read_only=True)
    partition_table = partition_table_serializer()
    netdevice_set = netdevice_serializer(many=True)
    monitoring_hint_set = monitoring_hint_serializer(many=True)
    device_variable_set = device_variable_serializer(many=True)
    device_mon_location_set = device_mon_location_serializer(many=True)
    device_config_set = device_config_serializer(many=True)
    package_device_connection_set = package_device_connection_serializer(many=True)
    latest_contact = serializers.Field(source="latest_contact")
    client_version = serializers.Field(source="client_version")
    monitor_type = serializers.Field(source="get_monitor_type")
    snmp_schemes = snmp_scheme_serializer(many=True, read_only=True)
    DeviceSNMPInfo = DeviceSNMPInfoSerializer(read_only=True)
    is_cd_device = serializers.SerializerMethodField("get_is_cd_device")

    def __init__(self, *args, **kwargs):
        fields = kwargs.get("context", {}).pop("fields", [])
        super(device_serializer, self).__init__(*args, **kwargs)
        _optional_fields = {
            "act_partition_table", "partition_table", "netdevice_set", "categories", "device_variable_set", "device_config_set",
            "package_device_connection_set", "latest_contact", "client_version", "monitor_type", "monitoring_hint_set", "device_mon_location_set",
        }
        for _to_remove in _optional_fields - set(fields):
            # in case we have been subclassed
            if _to_remove in self.fields:
                self.fields.pop(_to_remove)

    def get_access_level(self, obj):
        if "olp" in self.context:
            return self.context["request"].user.get_object_perm_level(self.context["olp"], obj)
        return -1

    def get_access_levels(self, obj):
        return {key: value for key, value in self.context["request"].user.get_object_access_levels(obj).iteritems()}

    def get_is_cd_device(self, obj):
        return True if (obj.ipmi_capable or len([_scheme.power_control for _scheme in obj.snmp_schemes.all() if _scheme.power_control])) else False

    class Meta:
        model = device
        fields = (
            "idx", "name", "device_group", "is_meta_device",
            "comment", "full_name", "domain_tree_node", "enabled",
            "monitor_checks", "mon_device_templ", "mon_device_esc_templ", "md_cache_mode",
            "enable_perfdata", "flap_detection_enabled",
            "automap_root_nagvis", "nagvis_parent", "monitor_server", "mon_ext_host",
            "is_meta_device", "device_group_name", "bootserver",
            "is_cluster_device_group", "root_passwd_set", "has_active_rrds",
            "mon_resolve_name", "access_level", "access_levels", "store_rrd_data", "ipmi_capable",
            "access_level", "access_levels", "store_rrd_data",
            # dhcp error
            "dhcp_error",
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
            # device monitoring location
            "device_mon_location_set",
            # snmp schemes
            "snmp_schemes",
            # snmp info
            "DeviceSNMPInfo",
            # uuid
            "uuid",
            # active_scan
            "active_scan",
            # cd_device mark
            "is_cd_device",
        )
        read_only_fields = ("uuid",)


class cd_connection_serializer(serializers.ModelSerializer):
    class Meta:
        model = cd_connection


class device_serializer_package_state(device_serializer):
    class Meta:
        model = device
        fields = (
            "idx", "name", "device_group", "is_meta_device",
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
    hoststatus_source = serializers.SerializerMethodField("get_hoststatus_source")
    # uptime = serializers.Field(source="get_uptime")
    # uptime_valid = serializers.Field(source="uptime_valid")
    network = serializers.SerializerMethodField("get_network")
    net_state = serializers.SerializerMethodField("get_net_state")
    net_state_str = serializers.SerializerMethodField("get_net_state_str")
    act_image = serializers.Field(source="get_act_image")
    act_kernel = serializers.Field(source="get_act_kernel")
    master_connections = serializers.SerializerMethodField("get_master_connections")
    slave_connections = serializers.SerializerMethodField("get_slave_connections")

    def _get_dev_node(self, dev):
        _res = self.context["mother_result"]
        if _res is not None:
            _res = _res.xpath(".//ns:device[@pk='{:d}']".format(dev.pk))
            if len(_res):
                _res = _res[0]
            else:
                _res = None
        return _res

    def get_master_connections(self, obj):
        _cd_con = self.context["cd_connections"]
        return cd_connection_serializer_boot(
            [
                entry for entry in _cd_con if entry.parent_id == obj.pk
            ],
            many=True,
            context=self.context
        ).data

    def get_slave_connections(self, obj):
        _cd_con = self.context["cd_connections"]
        return cd_connection_serializer_boot(
            [
                entry for entry in _cd_con if entry.child_id == obj.pk
            ],
            many=True,
            context=self.context
        ).data

    def get_network(self, obj):
        _network = "unknown"
        _node = self._get_dev_node(obj)
        if _node is not None:
            _network = _node.attrib.get("network", "unknown") or "unknown"
        return _network

    def get_hoststatus_source(self, obj):
        _source = ""
        _node = self._get_dev_node(obj)
        if _node is not None:
            _source = _node.attrib.get("hoststatus_source", "") or ""
        return _source

    def get_net_state(self, obj):
        _state = "down"
        _node = self._get_dev_node(obj)
        if _node is not None:
            _ip_state = _node.attrib.get("ip_state", "down")
            if _ip_state == "up":
                _state = "ping"
                if _node.attrib.get("hoststatus_source", ""):
                    # hoststatus set, state is up
                    _state = "up"
        return _state

    def get_net_state_str(self, obj):
        _state_str = ""
        _node = self._get_dev_node(obj)
        if _node is not None:
            _state_str = _node.attrib.get("hoststatus", "")
        return _state_str

    def get_partition_table(self, obj):
        return obj.partition_table_id or None

    def get_act_partition_table(self, obj):
        return obj.act_partition_table_id or None

    class Meta:
        model = device
        fields = (
            "idx", "name", "full_name", "device_group_name", "access_level", "access_levels",
            # meta-fields
            "hoststatus_source", "network", "net_state", "net_state_str",
            # target state
            "new_state", "prod_link",
            # partition
            "act_partition_table", "partition_table",
            # image
            "new_image", "act_image",
            # kernel
            "new_kernel", "act_kernel", "stage1_flavour", "kernel_append",
            # boot device
            "dhcp_mac", "dhcp_write", "dhcp_written", "dhcp_error", "bootnetdevice", "bootnetdevice",
            # connections
            "master_connections", "slave_connections",
        )


class quota_capable_blockdevice_serializer(serializers.ModelSerializer):
    device = device_serializer(read_only=True)

    class Meta:
        model = quota_capable_blockdevice
