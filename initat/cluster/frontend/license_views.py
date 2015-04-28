# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 Bernhard Mallinger
#
# Send feedback to: <mallinger@init.at>
#
# This file is part of webfrontend
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

""" license views """

import logging

from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from initat.cluster.frontend.rest_views import rest_logging

from initat.cluster.backbone.models import License


logger = logging.getLogger("cluster.monitoring")


class get_all_licenses(ListAPIView):
    @method_decorator(login_required)
    @rest_logging
    def list(self, request, *args, **kwargs):
        # pseudo-serialize named dict
        return Response(
            [
                {
                    'id': lic.id,
                    'name': lic.name,
                    'description': lic.description,
                } for lic in License.objects.get_all_licenses()
            ]
        )


class get_license_packages(ListAPIView):
    @method_decorator(login_required)
    @rest_logging
    def list(self, request, *args, **kwargs):
        return Response(License.objects.get_license_packages())


