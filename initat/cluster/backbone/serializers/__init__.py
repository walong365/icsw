# Copyright (C) 2001-2017 Andreas Lang-Nevyjel, init.at
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

""" model serializers """

from rest_framework import serializers
from initat.cluster.backbone.models import LogSource, LogLevel, mac_ignore, \
    macbootlog, status, WrittenConfigFile, mon_dist_slave, mon_dist_master, quota_capable_blockdevice
from initat.cluster.backbone.serializers.asset import *
from initat.cluster.backbone.serializers.variable import *
from initat.cluster.backbone.serializers.background import *
from initat.cluster.backbone.serializers.license import *
from initat.cluster.backbone.serializers.capability import *
from initat.cluster.backbone.serializers.config import *
from initat.cluster.backbone.serializers.device import *
from initat.cluster.backbone.serializers.dispatch import *
from initat.cluster.backbone.serializers.domain import *
from initat.cluster.backbone.serializers.graph import *
from initat.cluster.backbone.serializers.hints import *
from initat.cluster.backbone.serializers.kpi import *
from initat.cluster.backbone.serializers.monitoring import *
from initat.cluster.backbone.serializers.network import *
from initat.cluster.backbone.serializers.package import *
from initat.cluster.backbone.serializers.partition import *
from initat.cluster.backbone.serializers.rms import *
from initat.cluster.backbone.serializers.selection import *
from initat.cluster.backbone.serializers.setup import *
from initat.cluster.backbone.serializers.user import *


class LogSourceSerializer(serializers.ModelSerializer):
    class Meta:
        fields = "__all__"
        model = LogSource


class LogLevelSerializer(serializers.ModelSerializer):
    class Meta:
        fields = "__all__"
        model = LogLevel


class mac_ignore_serializer(serializers.ModelSerializer):
    class Meta:
        fields = "__all__"
        model = mac_ignore


class macbootlog_serializer(serializers.ModelSerializer):
    created = serializers.DateTimeField(read_only=True)
    device_name = serializers.CharField(read_only=True)

    class Meta:
        fields = "__all__"
        model = macbootlog


class status_serializer(serializers.ModelSerializer):
    info_string = serializers.CharField(read_only=True)

    class Meta:
        fields = "__all__"
        model = status


class WrittenConfigFileSerializer(serializers.ModelSerializer):
    class Meta:
        fields = "__all__"
        model = WrittenConfigFile


class mon_dist_slave_serializer(serializers.ModelSerializer):
    class Meta:
        fields = "__all__"
        model = mon_dist_slave


class mon_dist_master_serializer(serializers.ModelSerializer):
    mon_dist_slave_set = mon_dist_slave_serializer(many=True)

    class Meta:
        fields = "__all__"
        model = mon_dist_master


class quota_capable_blockdevice_serializer(serializers.ModelSerializer):
    device = device_serializer(read_only=True)

    class Meta:
        fields = "__all__"
        model = quota_capable_blockdevice
