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
""" serializer definitions for network elements """

import logging

from rest_framework import serializers

from initat.cluster.backbone.models import network_type, network_device_type, network, net_ip, \
    netdevice, netdevice_speed, peer_information, snmp_network_type

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
]

logger = logging.getLogger(__name__)


class network_device_type_serializer(serializers.ModelSerializer):
    info_string = serializers.Field(source="info_string")

    class Meta:
        model = network_device_type


class network_type_serializer(serializers.ModelSerializer):
    class Meta:
        model = network_type


class network_serializer(serializers.ModelSerializer):
    info_string = serializers.Field(source="info_string")
    network_type_identifier = serializers.Field(source="get_identifier")
    network_type_name = serializers.Field(source="get_type_name")
    num_ip = serializers.Field(0)

    class Meta:
        model = network


class network_with_ip_serializer(serializers.ModelSerializer):
    info_string = serializers.Field(source="info_string")
    network_type_identifier = serializers.Field(source="get_identifier")
    num_ip = serializers.Field(source="num_ip")

    class Meta:
        model = network


class net_ip_serializer(serializers.ModelSerializer):
    # network = network_serializer()
    _changed_by_user_ = serializers.SerializerMethodField("get_changed_by_user")

    def get_changed_by_user(self, obj):
        return True

    class Meta:
        model = net_ip


class netdevice_serializer(serializers.ModelSerializer):
    net_ip_set = net_ip_serializer(many=True, read_only=True)
    ethtool_autoneg = serializers.Field(source="ethtool_autoneg")
    ethtool_duplex = serializers.Field(source="ethtool_duplex")
    ethtool_speed = serializers.Field(source="ethtool_speed")

    class Meta:
        model = netdevice


class netdevice_speed_serializer(serializers.ModelSerializer):
    info_string = serializers.Field(source="info_string")

    class Meta:
        model = netdevice_speed


class peer_information_serializer(serializers.ModelSerializer):
    class Meta:
        model = peer_information


class snmp_network_type_serializer(serializers.ModelSerializer):
    class Meta:
        model = snmp_network_type
