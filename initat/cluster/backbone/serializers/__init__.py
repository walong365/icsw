# Copyright (C) 2001-2016 Andreas Lang-Nevyjel, init.at
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

from rest_framework import serializers

from initat.cluster.backbone.models import device, device_selection, device_config, device_variable, \
    LogSource, LogLevel, device_group, mac_ignore, \
    macbootlog, status, WrittenConfigFile, mon_dist_slave, mon_dist_master, cd_connection, \
    quota_capable_blockdevice, DeviceSNMPInfo
from initat.cluster.backbone.serializers.asset import *  # @UnusedWildImport
from initat.cluster.backbone.serializers.background import *  # @UnusedWildImport
from initat.cluster.backbone.serializers.capability import *  # @UnusedWildImport
from initat.cluster.backbone.serializers.config import *  # @UnusedWildImport
from initat.cluster.backbone.serializers.dispatch import *  # @UnusedWildImport
from initat.cluster.backbone.serializers.domain import *  # @UnusedWildImport
from initat.cluster.backbone.serializers.graph import *  # @UnusedWildImport
from initat.cluster.backbone.serializers.hints import *  # @UnusedWildImport
from initat.cluster.backbone.serializers.kpi import *  # @UnusedWildImport
from initat.cluster.backbone.serializers.monitoring import *  # @UnusedWildImport
from initat.cluster.backbone.serializers.network import *  # @UnusedWildImport
from initat.cluster.backbone.serializers.package import *  # @UnusedWildImport
from initat.cluster.backbone.serializers.partition import *  # @UnusedWildImport
from initat.cluster.backbone.serializers.rms import *  # @UnusedWildImport
from initat.cluster.backbone.serializers.selection import *  # @UnusedWildImport
from initat.cluster.backbone.serializers.setup import *  # @UnusedWildImport
from initat.cluster.backbone.serializers.user import *  # @UnusedWildImport


class device_variable_serializer(serializers.ModelSerializer):
    class Meta:
        model = device_variable


class device_config_help_serializer(serializers.ModelSerializer):
    info_string = serializers.CharField(source="home_info")
    homeexport = serializers.SerializerMethodField()
    createdir = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField()

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
    # not really needed
    # full_name = serializers.CharField(read_only=True)

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
    created = serializers.DateTimeField(read_only=True)
    device_name = serializers.CharField(read_only=True)

    class Meta:
        model = macbootlog


class status_serializer(serializers.ModelSerializer):
    info_string = serializers.CharField(read_only=True)

    class Meta:
        model = status


class WrittenConfigFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = WrittenConfigFile


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
    full_name = serializers.CharField(read_only=True)
    is_meta_device = serializers.BooleanField(read_only=True, required=False)
    is_cluster_device_group = serializers.BooleanField(read_only=True)
    device_group_name = serializers.CharField(read_only=True)
    access_levels = serializers.SerializerMethodField()
    root_passwd_set = serializers.BooleanField(read_only=True)
    # monitor_type = serializers.CharField(source="get_monitor_type")
    # is_cd_device = serializers.SerializerMethodField()

    def get_access_levels(self, obj):
        return self.context["request"].user.get_object_access_levels(obj)

    class Meta:
        model = device
        fields = (
            "idx", "name", "device_group", "is_meta_device",
            "alias", "comment", "full_name", "domain_tree_node", "enabled",
            "monitor_checks", "mon_device_templ", "mon_device_esc_templ", "md_cache_mode",
            "enable_perfdata", "flap_detection_enabled",
            "automap_root_nagvis", "nagvis_parent", "monitor_server", "mon_ext_host",
            "is_meta_device", "device_group_name", "bootserver",
            "is_cluster_device_group", "root_passwd_set", "has_active_rrds",
            "mon_resolve_name", "access_levels", "store_rrd_data",
            # dhcp error
            "dhcp_error",
            # for network view
            "new_state", "prod_link", "dhcp_mac", "dhcp_write",
            # for categories
            "categories",
            # monitor type
            # "monitor_type",
            # uuid
            "uuid",
            # active_scan
            "active_scan",
        )
        read_only_fields = ("uuid",)


class cd_connection_serializer(serializers.ModelSerializer):
    class Meta:
        model = cd_connection


class cd_connection_serializer_boot(serializers.ModelSerializer):
    parent = device_serializer()
    child = device_serializer()

    class Meta:
        model = cd_connection


class device_serializer_boot(device_serializer):
    partition_table = serializers.SerializerMethodField()
    # current partition table
    act_partition_table = serializers.SerializerMethodField()
    # bootnetdevice = netdevice_serializer()
    hoststatus_source = serializers.SerializerMethodField()
    # uptime = serializers.Field(source="get_uptime")
    # uptime_valid = serializers.Field(source="uptime_valid")
    network = serializers.SerializerMethodField()
    net_state = serializers.SerializerMethodField()
    hoststatus_str = serializers.SerializerMethodField()
    act_image = serializers.ReadOnlyField(source="get_act_image")
    act_kernel = serializers.ReadOnlyField(source="get_act_kernel")
    master_connections = serializers.SerializerMethodField()
    slave_connections = serializers.SerializerMethodField()

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
        # returns unknown / down / ping / up
        # unknown is also used when the device is not a valid device for mother
        _state = "unknown"
        _node = self._get_dev_node(obj)
        if _node is not None:
            _state = _node.attrib.get("ip_state", "unknown")
            if _state == "up":
                _state = "ping"
                if _node.attrib.get("hoststatus_source", ""):
                    # hoststatus set, state is up
                    _state = "up"
        return _state

    def get_hoststatus_str(self, obj):
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
            "idx", "name", "full_name", "device_group_name", "access_levels",
            # meta-fields
            "hoststatus_source", "network", "net_state", "hoststatus_str",
            # target state
            "new_state", "prod_link",
            # partition
            "act_partition_table", "partition_table",
            # image
            "new_image", "act_image",
            # kernel
            "new_kernel", "act_kernel", "stage1_flavour", "kernel_append",
            # boot device
            "dhcp_mac", "dhcp_write", "dhcp_written", "dhcp_error", "bootnetdevice",
            # connections
            "master_connections", "slave_connections",
        )


class quota_capable_blockdevice_serializer(serializers.ModelSerializer):
    device = device_serializer(read_only=True)

    class Meta:
        model = quota_capable_blockdevice
