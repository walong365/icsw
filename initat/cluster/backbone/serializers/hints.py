# Copyright (C) 2014-2017 Andreas Lang-Nevyjel, init.at
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
""" serializer definitions for hints """

from initat.cluster.backbone.models import config_hint, config_var_hint, config_script_hint
from rest_framework import serializers

__all__ = [
    "config_hint_serializer",
    "config_var_hint_serializer",
    "config_script_hint_serializer",
]


class config_var_hint_serializer(serializers.ModelSerializer):
    class Meta:
        fields = "__all__"
        model = config_var_hint


class config_script_hint_serializer(serializers.ModelSerializer):
    class Meta:
        fields = "__all__"
        model = config_script_hint


class config_hint_serializer(serializers.ModelSerializer):
    config_var_hint_set = config_var_hint_serializer(many=True)
    config_script_hint_set = config_script_hint_serializer(many=True)

    class Meta:
        fields = "__all__"
        model = config_hint
