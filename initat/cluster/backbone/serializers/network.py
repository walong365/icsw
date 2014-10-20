#!/usr/bin/python-init

from initat.cluster.backbone.models import network_type, network_device_type, network, net_ip, \
    netdevice, netdevice_speed, peer_information, snmp_network_type
# from lxml.builder import E  # @UnresolvedImport
from rest_framework import serializers
import logging

__all__ = [
    "network_serializer", "network_with_ip_serializer",
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
