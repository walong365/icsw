# Copyright (C) 2015 init.at
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
""" model serializers """
import json

from rest_framework import serializers

from initat.cluster.backbone.models import Kpi, KpiDataSourceTuple, KpiStoredResult
from initat.md_config_server.kpi import KpiSet, KpiResult


__all__ = [
    "KpiSerializer",
    "KpiDataSourceTupleSerializer",
]


class KpiDataSourceTupleSerializer(serializers.ModelSerializer):
    class Meta:
        model = KpiDataSourceTuple


class KpiSerializer(serializers.ModelSerializer):
    result = serializers.SerializerMethodField("_get_result")

    def _get_result(self, obj):
        try:
            stored_result = obj.kpistoredresult
        except KpiStoredResult.DoesNotExist:
            return None
        else:
            if stored_result.result is None:
                # result is here, but calculation resulted in None
                return None
            else:
                parsed = json.loads(stored_result.result)
                # kpi_set = KpiSet.deserialize(parsed)
                return {
                    # 'values': [obj.result.get_numeric_icinga_service_status() for obj in kpi_set.objects if obj.result is not None],
                    'date': stored_result.date,
                    'json': parsed,
                }

    class Meta:
        model = Kpi



