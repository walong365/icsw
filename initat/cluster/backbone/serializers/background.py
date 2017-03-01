# -*- coding: utf-8 -*-
#
# Copyright (C) 2013-2014,2016-2017 Andreas Lang-Nevyjel
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

""" Serializers for background jobs DB objects """

import logging

from rest_framework import serializers

from initat.cluster.backbone.models import background_job, background_job_run

logger = logging.getLogger(__name__)

__all__ = [
    "background_job_serializer",
    "background_job_run_serializer",
]


class background_job_run_serializer(serializers.ModelSerializer):
    class Meta:
        fields = "__all__"
        model = background_job_run


class background_job_serializer(serializers.ModelSerializer):
    initiator_name = serializers.CharField(read_only=True)
    user_name = serializers.CharField(read_only=True)
    background_job_run_set = background_job_run_serializer(many=True, read_only=True)

    class Meta:
        fields = "__all__"
        model = background_job
