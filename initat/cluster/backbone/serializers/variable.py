# Copyright (C) 2001-2016 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw-server
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

""" model serializers for device variables """

from rest_framework import serializers

from initat.cluster.backbone.models import device_variable, device_variable_scope, \
    dvs_allowed_names


__all__ = [
    "device_variable_serializer",
    "device_variable_scope_serializer",
    "dvs_allowed_names",
]


class device_variable_serializer(serializers.ModelSerializer):
    class Meta:
        model = device_variable


class dvs_allowed_names_serializer(serializers.ModelSerializer):
    class Meta:
        model = dvs_allowed_names


class device_variable_scope_serializer(serializers.ModelSerializer):
    dvs_allowed_names_set = dvs_allowed_names_serializer(many=True)

    class Meta:
        model = device_variable_scope
