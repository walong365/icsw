# Copyright (C) 2014 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw-server-server
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
""" serializer definitions for Graphs elements """

from initat.cluster.backbone.models import SensorAction, SensorThreshold, SensorThresholdAction, \
    GraphSetting, GraphSettingSize, GraphSettingTimeshift, GraphSettingForecast, GraphTimeFrame
from rest_framework import serializers

__all__ = [
    "SensorActionSerializer",
    "SensorThresholdSerializer",
    "SensorThresholdActionSerializer",
    "GraphSettingSerializer",
    "GraphSettingSerializerCustom",
    "GraphSettingSizeSerializer",
    "GraphSettingTimeshiftSerializer",
    "GraphSettingForecastSerializer",
    "GraphTimeFrameSerializer",
]


class SensorActionSerializer(serializers.ModelSerializer):
    class Meta:
        fields = "__all__"
        model = SensorAction


class SensorThresholdSerializer(serializers.ModelSerializer):
    device = serializers.SerializerMethodField()

    def get_device(self, obj):
        if self.context and "device" in self.context:
            return self.context["device"]
        else:
            return 0

    class Meta:
        fields = "__all__"
        model = SensorThreshold


class SensorThresholdActionSerializer(serializers.ModelSerializer):
    class Meta:
        fields = "__all__"
        model = SensorThresholdAction


class GraphSettingSizeSerializer(serializers.ModelSerializer):
    class Meta:
        fields = "__all__"
        model = GraphSettingSize


class GraphSettingTimeshiftSerializer(serializers.ModelSerializer):
    class Meta:
        fields = "__all__"
        model = GraphSettingTimeshift


class GraphSettingForecastSerializer(serializers.ModelSerializer):
    class Meta:
        fields = "__all__"
        model = GraphSettingForecast


class GraphSettingForecastSerializerCustom(serializers.Serializer):
    seconds = serializers.IntegerField()
    mode = serializers.CharField()


class GraphSettingTimeshiftSerializerCustom(serializers.Serializer):
    seconds = serializers.IntegerField()


class GraphSettingSizeSerializerCustom(serializers.Serializer):
    width = serializers.IntegerField()
    height = serializers.IntegerField()


class GraphSettingSerializerCustom(serializers.ModelSerializer):
    # name = serializers.CharField(read_only=True)
    graph_setting_size = GraphSettingSizeSerializerCustom()
    graph_setting_timeshift = GraphSettingTimeshiftSerializerCustom(required=False)
    graph_setting_forecast = GraphSettingForecastSerializerCustom(required=False)

    def create(self, validated_data):
        validated_data["graph_setting_size"] = GraphSettingSize(**validated_data.pop("graph_setting_size"))
        if "graph_setting_timeshift" in validated_data:
            validated_data["graph_setting_timeshift"] = GraphSettingTimeshift(**validated_data.pop("graph_setting_timeshift"))
        if "graph_setting_forecast" in validated_data:
            validated_data["graph_setting_forecast"] = GraphSettingForecast(**validated_data.pop("graph_setting_forecast"))
        _gs = GraphSetting(**validated_data)
        _gs.to_enum()
        return _gs

    class Meta:
        fields = "__all__"
        model = GraphSetting


class GraphSettingSerializer(serializers.ModelSerializer):
    class Meta:
        fields = "__all__"
        model = GraphSetting


class GraphTimeFrameSerializer(serializers.ModelSerializer):
    class Meta:
        fields = "__all__"
        model = GraphTimeFrame
