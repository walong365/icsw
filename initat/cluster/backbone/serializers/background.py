# -*- coding: utf-8 -*-
#
# Copyright (C) 2013-2014 Andreas Lang-Nevyjel
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

""" DB definitions for background jobs """

from rest_framework import serializers
from initat.cluster.backbone.models import background_job, background_job_run
import logging

logger = logging.getLogger(__name__)

__all__ = [
    "background_job_serializer",
    "background_job_run_serializer",
]


class background_job_serializer(serializers.ModelSerializer):
    initiator_name = serializers.Field(source="initiator_name")
    user_name = serializers.Field(source="user_name")

    class Meta:
        model = background_job


class background_job_run_serializer(serializers.ModelSerializer):
    class Meta:
        model = background_job_run
