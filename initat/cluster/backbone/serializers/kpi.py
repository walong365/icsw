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

from rest_framework import serializers

from initat.cluster.backbone.models import Kpi, KpiDataSourceTuple


__all__ = [
    "KpiSerializer",
    "KpiDataSourceTupleSerializer",
]


class KpiDataSourceTupleSerializer(serializers.ModelSerializer):
    class Meta:
        model = KpiDataSourceTuple


class KpiSerializer(serializers.ModelSerializer):
    class Meta:
        model = Kpi



