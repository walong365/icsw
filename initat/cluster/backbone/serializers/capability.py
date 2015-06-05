# Copyright (C) 2001-2014 Andreas Lang-Nevyjel, init.at
#
# this file is part of cluster-backbone-sql
#
# Send feedback to: <lang-nevyjel@init.at>
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
""" database definitions for monitoring """

from initat.cluster.backbone.models import snmp_scheme, snmp_scheme_vendor, \
    snmp_scheme_tl_oid, ComCapability
from rest_framework import serializers

__all__ = [
    "snmp_scheme_serializer",
    "snmp_scheme_vendor_serializer",
    "snmp_scheme_tl_oid_serializer",
    "ComCapabilitySerializer",
]


class snmp_scheme_tl_oid_serializer(serializers.ModelSerializer):
    class Meta:
        model = snmp_scheme_tl_oid


class snmp_scheme_vendor_serializer(serializers.ModelSerializer):
    class Meta:
        model = snmp_scheme_vendor


class snmp_scheme_serializer(serializers.ModelSerializer):
    snmp_scheme_vendor = snmp_scheme_vendor_serializer()
    snmp_scheme_tl_oid_set = snmp_scheme_tl_oid_serializer(many=True)
    full_name = serializers.Field(source="full_name")

    class Meta:
        model = snmp_scheme


class ComCapabilitySerializer(serializers.ModelSerializer):

    class Meta:
        model = ComCapability
