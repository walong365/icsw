# Copyright (C) 2001-2014 Andreas Lang-Nevyjel, init.at
#
# this file is part of icsw-server
#
# Send feedback to: <lang-nevyjel@init.at>
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
""" database definitions for monitoring """

from initat.cluster.backbone.models import mon_host_cluster, mon_service_cluster, mon_ext_host, \
    mon_check_command, mon_host_dependency, mon_service_dependency, host_check_command, \
    mon_notification, mon_contact, mon_contactgroup, mon_check_command_special, mon_device_templ, \
    mon_service_templ, mon_period, mon_host_dependency_templ, mon_service_dependency_templ, \
    mon_device_esc_templ, monitoring_hint, mon_service_esc_templ
from rest_framework import serializers

__all__ = [
    "mon_host_cluster_serializer",
    "mon_service_cluster_serializer",
    "host_check_command_serializer",
    "mon_check_command_serializer",
    "mon_check_command_nat_serializer",
    "mon_contact_serializer",
    "mon_notification_serializer",
    "mon_contactgroup_serializer",
    "mon_device_templ_serializer",
    "mon_device_esc_templ_serializer",
    "mon_host_dependency_templ_serializer",
    "mon_host_dependency_serializer",
    "mon_service_dependency_templ_serializer",
    "mon_service_dependency_serializer",
    "mon_ext_host_serializer",
    "mon_period_serializer",
    "mon_service_templ_serializer",
    "mon_service_esc_templ_serializer",
    # distribution models
    "monitoring_hint_serializer",
    "mon_check_command_special_serializer",
]


class mon_host_cluster_serializer(serializers.ModelSerializer):
    class Meta:
        fields = "__all__"
        model = mon_host_cluster


class mon_service_cluster_serializer(serializers.ModelSerializer):
    class Meta:
        fields = "__all__"
        model = mon_service_cluster


class host_check_command_serializer(serializers.ModelSerializer):
    class Meta:
        fields = "__all__"
        model = host_check_command


class mon_check_command_special_serializer(serializers.ModelSerializer):
    class Meta:
        fields = "__all__"
        model = mon_check_command_special


class mon_check_command_serializer(serializers.ModelSerializer):
    object_type = serializers.CharField(source="get_object_type", read_only=True)

    class Meta:
        fields = "__all__"
        model = mon_check_command


class mon_check_command_nat_serializer(serializers.ModelSerializer):
    config = serializers.SlugRelatedField(slug_field="name", read_only=True)

    class Meta:
        fields = "__all__"
        model = mon_check_command


class mon_notification_serializer(serializers.ModelSerializer):
    class Meta:
        fields = "__all__"
        model = mon_notification


class mon_contact_serializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="get_user_name", read_only=True)

    class Meta:
        fields = "__all__"
        model = mon_contact


class mon_contactgroup_serializer(serializers.ModelSerializer):
    class Meta:
        model = mon_contactgroup
        fields = ("idx", "name", "alias", "device_groups", "members", "service_templates", "service_esc_templates",)


class mon_device_templ_serializer(serializers.ModelSerializer):
    class Meta:
        fields = "__all__"
        model = mon_device_templ


class mon_device_esc_templ_serializer(serializers.ModelSerializer):
    class Meta:
        fields = "__all__"
        model = mon_device_esc_templ


class mon_host_dependency_templ_serializer(serializers.ModelSerializer):
    class Meta:
        fields = "__all__"
        model = mon_host_dependency_templ


class mon_host_dependency_serializer(serializers.ModelSerializer):
    class Meta:
        fields = "__all__"
        model = mon_host_dependency


class mon_service_dependency_templ_serializer(serializers.ModelSerializer):
    class Meta:
        fields = "__all__"
        model = mon_service_dependency_templ


class mon_service_dependency_serializer(serializers.ModelSerializer):
    class Meta:
        fields = "__all__"
        model = mon_service_dependency


class mon_ext_host_serializer(serializers.ModelSerializer):
    data_image = serializers.URLField(source="data_image_field", read_only=True)

    class Meta:
        fields = "__all__"
        model = mon_ext_host


class mon_period_serializer(serializers.ModelSerializer):
    class Meta:
        model = mon_period
        fields = (
            "idx", "name", "alias", "sun_range", "mon_range", "tue_range",
            "wed_range", "thu_range", "fri_range", "sat_range", "service_check_period",
            # "mon_device_templ_set",
        )
        read_only_fields = ("service_check_period",)  # "mon_device_templ_set")


class mon_service_templ_serializer(serializers.ModelSerializer):
    class Meta:
        fields = "__all__"
        model = mon_service_templ


class mon_service_esc_templ_serializer(serializers.ModelSerializer):
    class Meta:
        fields = "__all__"
        model = mon_service_esc_templ


class monitoring_hint_serializer(serializers.ModelSerializer):
    class Meta:
        model = monitoring_hint
        fields = "__all__"
        read_only_fields = [
            "idx", "device", "call_idx", "m_type", "key", "v_type",
            "value_float", "value_int", "value_string", "info",
            "check_created", "changed", "persistent", "datasource", "date",
        ]
