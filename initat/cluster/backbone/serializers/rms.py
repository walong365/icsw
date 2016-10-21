# Copyright (C) 2013-2016 Andreas Lang-Nevyjel, init.at
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
""" serializers for RMS """

# from django.db.models import Q, signals, get_model
# from django.dispatch import receiver
from initat.cluster.backbone.models import rms_project, rms_department, rms_queue, \
    rms_pe, rms_job, rms_job_run, rms_pe_info, ext_license, ext_license_check, \
    ext_license_client, ext_license_state, ext_license_usage, ext_license_user, \
    ext_license_version, ext_license_version_state, ext_license_vendor, ext_license_site, \
    ext_license_state_coarse, ext_license_version_state_coarse, RMSJobVariable, RMSJobVariableActionRun, \
    RMSJobVariableAction
from rest_framework import serializers

__all__ = [
    "rms_job_serializer",
    "rms_job_run_serializer",
    "rms_pe_info_serializer",
    "rms_project_serializer",
    "rms_department_serializer",
    "rms_queue_serializer",
    "rms_pe_serializer",
    "ext_license_site_serializer",
    "ext_license_serializer",
    "ext_license_version_serializer",
    "ext_license_vendor_serializer",
    "ext_license_user_serializer",
    "ext_license_client_serializer",
    "ext_license_check_serializer",
    "ext_license_state_serializer",
    "ext_license_version_state_serializer",
    "ext_license_usage_serializer",
    "ext_license_state_coarse_serializer",
    "ext_license_version_state_coarse_serializer",
    "RMSJobVariableSerializer",
    "RMSJobVariableActionSerializer",
    "RMSJobVariableActionRunSerializer",
]


class RMSJobVariableSerializer(serializers.ModelSerializer):
    value = serializers.CharField(source="get_value", read_only=True)
    value_int = serializers.CharField(source="get_int_value", read_only=True)

    class Meta:
        model = RMSJobVariable
        fields = (
            "rms_job", "rms_job_run", "name", "raw_value", "parsed_type", "unit", "value", "value_int",
        )


class RMSJobVariableActionSerializer(serializers.ModelSerializer):
    class Meta:
        fields = "__all__"
        model = RMSJobVariableAction


class RMSJobVariableActionRunSerializer(serializers.ModelSerializer):
    class Meta:
        fields = "__all__"
        model = RMSJobVariableActionRun


class rms_project_serializer(serializers.ModelSerializer):
    class Meta:
        model = rms_project
        fields = ("name",)


class rms_department_serializer(serializers.ModelSerializer):
    class Meta:
        model = rms_department
        fields = ("name",)


class rms_queue_serializer(serializers.ModelSerializer):
    class Meta:
        model = rms_queue
        fields = ("name",)


class rms_pe_serializer(serializers.ModelSerializer):
    class Meta:
        model = rms_pe
        fields = ("name",)


class rms_job_serializer(serializers.ModelSerializer):

    class Meta:
        model = rms_job
        fields = (
            "name", "jobid", "taskid", "owner", "user",
        )


class rms_pe_info_serializer(serializers.ModelSerializer):
    class Meta:
        fields = "__all__"
        model = rms_pe_info


class rms_job_run_serializer(serializers.ModelSerializer):
    rms_job = rms_job_serializer()
    rms_queue = rms_queue_serializer()
    rms_project = rms_project_serializer()
    rms_department = rms_department_serializer()
    rms_pe = rms_pe_serializer()
    rms_pe_info_set = rms_pe_info_serializer(many=True)
    start_time = serializers.CharField()
    end_time = serializers.CharField()
    queue_time = serializers.CharField()
    start_time_py = serializers.CharField()
    end_time_py = serializers.CharField()
    rmsjobvariable_set = RMSJobVariableSerializer(many=True)

    class Meta:
        model = rms_job_run
        fields = (
            "rms_job", "rms_queue", "rms_project", "rms_department", "rms_pe",
            "start_time", "end_time", "start_time_py", "end_time_py", "device", "hostname",
            "granted_pe", "slots", "priority", "account", "failed", "exit_status", "rms_queue",
            "queue_time", "rmsjobvariable_set", "rms_pe_info_set",
        )


class ext_license_site_serializer(serializers.ModelSerializer):
    class Meta:
        fields = "__all__"
        model = ext_license_site


class ext_license_serializer(serializers.ModelSerializer):
    class Meta:
        fields = "__all__"
        model = ext_license


class ext_license_version_serializer(serializers.ModelSerializer):
    class Meta:
        fields = "__all__"
        model = ext_license_version


class ext_license_vendor_serializer(serializers.ModelSerializer):
    class Meta:
        fields = "__all__"
        model = ext_license_vendor


class ext_license_user_serializer(serializers.ModelSerializer):
    class Meta:
        fields = "__all__"
        model = ext_license_user


class ext_license_client_serializer(serializers.ModelSerializer):
    class Meta:
        fields = "__all__"
        model = ext_license_client


class ext_license_check_serializer(serializers.ModelSerializer):
    class Meta:
        fields = "__all__"
        model = ext_license_check


class ext_license_state_serializer(serializers.ModelSerializer):
    class Meta:
        fields = "__all__"
        model = ext_license_state


class ext_license_version_state_serializer(serializers.ModelSerializer):
    class Meta:
        fields = "__all__"
        model = ext_license_version_state


class ext_license_usage_serializer(serializers.ModelSerializer):
    class Meta:
        fields = "__all__"
        model = ext_license_usage


class ext_license_state_coarse_serializer(serializers.ModelSerializer):
    display_date = serializers.Field(source="get_display_date")
    full_start_date = serializers.Field(source="ext_license_check_coarse.start_date")

    class Meta:
        fields = "__all__"
        model = ext_license_state_coarse


class ext_license_version_state_coarse_serializer(serializers.ModelSerializer):
    display_date = serializers.Field(source="get_display_date")
    full_start_date = serializers.Field(source="ext_license_check_coarse.start_date")
    ext_license_version_name = serializers.Field(source="ext_license_version.version")
    vendor_name = serializers.Field(source="vendor.name")

    class Meta:
        fields = "__all__"
        model = ext_license_version_state_coarse
