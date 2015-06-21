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
""" serializer definitions for Graphs elements """

from initat.cluster.backbone.models import SensorAction, SensorThreshold

__all__ = [
    "SensorActionSerializer",
    "SensorThresholdSerializer",
]


class SensorActionSerializer(serializers.ModelSerializer):
    class Meta:
        model = SensorAction


class SensorThresholdSerializer(serializers.ModelSerializer):
    class Meta:
        model = SensorThreshold
