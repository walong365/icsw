# Copyright (C) 2014-2017 Andreas Lang-Nevyjel, init.at
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
""" serializer definitions for network elements """

import logging

from rest_framework import serializers

from initat.cluster.backbone.models import network_type, network_device_type, network, net_ip, \
    netdevice, netdevice_speed, peer_information, snmp_network_type, NmapScan

__all__ = [
    "network_serializer",
    "network_with_ip_serializer",
    "network_type_serializer",
    "net_ip_serializer",
    "network_device_type_serializer",
    "netdevice_serializer",
    "netdevice_speed_serializer",
    "peer_information_serializer",
    "snmp_network_type_serializer",
    "NmapScanSerializerSimple",
    "NmapScanSerializerDetailed"
]

logger = logging.getLogger(__name__)


class network_device_type_serializer(serializers.ModelSerializer):
    info_string = serializers.CharField(read_only=True)

    class Meta:
        fields = "__all__"
        model = network_device_type


class network_type_serializer(serializers.ModelSerializer):
    class Meta:
        fields = "__all__"
        model = network_type


class network_serializer(serializers.ModelSerializer):
    info_string = serializers.CharField(read_only=True)
    network_type_identifier = serializers.CharField(source="get_identifier", read_only=True)
    network_type_name = serializers.CharField(source="get_type_name", read_only=True)
    num_ip = serializers.IntegerField(read_only=True)

    class Meta:
        fields = "__all__"
        model = network


class network_with_ip_serializer(serializers.ModelSerializer):
    info_string = serializers.CharField(read_only=True)
    network_type_identifier = serializers.CharField(source="get_identifier", read_only=True)
    num_ip = serializers.IntegerField(read_only=True)

    class Meta:
        fields = "__all__"
        model = network


class net_ip_serializer(serializers.ModelSerializer):
    # network = network_serializer()
    _changed_by_user_ = serializers.SerializerMethodField("get_changed_by_user")

    def get_changed_by_user(self, obj):
        return True

    class Meta:
        fields = "__all__"
        model = net_ip


class netdevice_serializer(serializers.ModelSerializer):
    net_ip_set = net_ip_serializer(many=True, read_only=True)
    ethtool_autoneg = serializers.IntegerField()
    ethtool_duplex = serializers.IntegerField()
    ethtool_speed = serializers.IntegerField()

    class Meta:
        fields = "__all__"
        model = netdevice


class netdevice_speed_serializer(serializers.ModelSerializer):
    info_string = serializers.CharField()

    class Meta:
        fields = "__all__"
        model = netdevice_speed


class peer_information_serializer(serializers.ModelSerializer):
    s_device = serializers.IntegerField(source="get_s_device", read_only=True)
    d_device = serializers.IntegerField(source="get_d_device", read_only=True)
    
    class Meta:
        fields = "__all__"
        model = peer_information


class snmp_network_type_serializer(serializers.ModelSerializer):
    class Meta:
        fields = "__all__"
        model = snmp_network_type


class NmapScanSerializerSimple(serializers.ModelSerializer):
    class Meta:
        model = NmapScan
        fields = (
            "idx", "network", "date", "devices_found", "devices_scanned", "devices_ignored", "runtime", "in_progress",
            "error_string"
        )


class NmapScanSerializerDetailed(serializers.ModelSerializer):
    devices = serializers.SerializerMethodField()

    def get_devices(self, obj):
        nmap_scans = NmapScan.objects.filter(network=obj.network).order_by("idx")

        nmap_scan_cached_devices = {}

        nmap_devices = obj.get_nmap_devices()

        for device in nmap_devices:
            if device.mac:
                first_nmap_scan_found = False

                for nmap_scan in nmap_scans:
                    if nmap_scan.idx in nmap_scan_cached_devices:
                        old_devices = nmap_scan_cached_devices[nmap_scan.idx]
                    else:
                        old_devices = nmap_scan.get_nmap_devices()
                        nmap_scan_cached_devices[nmap_scan.idx] = old_devices

                    for old_device in old_devices:
                        if old_device.mac and old_device.mac == device.mac:
                            device.first_seen_nmap_scan_idx = nmap_scan.idx
                            device.first_seen_nmap_scan_date = str(nmap_scan.date)
                            first_nmap_scan_found = True
                            break

                    if first_nmap_scan_found:
                        break

        return [host.get_dict() for host in nmap_devices]

    class Meta:
        model = NmapScan
        fields = (
            "idx", "network", "date", "devices", "devices_found", "devices_ignored", "devices_scanned", "runtime",
            "matrix"
        )
