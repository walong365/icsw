# -*- coding: utf-8 -*-
#
# Copyright (C) 2015-2017 Bernhard Mallinger, Andreas Lang-Nevyjel
#
# Send feedback to: <mallinger@init.at>, <lang-nevyjel@init.at>
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



from rest_framework import serializers

from initat.cluster.backbone.models import DispatchSetting, DispatcherSetting, DispatcherSettingSchedule, \
    DispatcherLink, ScheduleItem

__all__ = [
    "DispatchSettingSerializer",
    "DispatcherSettingSerializer",
    "DispatcherSettingScheduleSerializer",
    "DispatcherLinkSerializer",
    "ScheduleItemSerializer",
]


class DispatchSettingSerializer(serializers.ModelSerializer):

    class Meta:
        fields = "__all__"
        model = DispatchSetting


class DispatcherSettingSerializer(serializers.ModelSerializer):

    class Meta:
        fields = "__all__"
        model = DispatcherSetting


class DispatcherSettingScheduleSerializer(serializers.ModelSerializer):

    class Meta:
        fields = "__all__"
        model = DispatcherSettingSchedule


class DispatcherLinkSerializer(serializers.ModelSerializer):

    class Meta:
        fields = "__all__"
        model = DispatcherLink


class ScheduleItemSerializer(serializers.ModelSerializer):

    class Meta:
        fields = "__all__"
        model = ScheduleItem
