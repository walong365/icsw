# -*- coding: utf-8 -*-
#
# Copyright (C) 2015-2017 Bernhard Mallinger, Andreas Lang-Nevyjel
#
# Send feedback to: <mallinger@init.at>
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

""" license views """

import logging

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.utils.decorators import method_decorator
from django.views.generic import View
from rest_framework import viewsets
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.response import Response

from initat.cluster.backbone.available_licenses import LicenseEnum, get_available_licenses
from initat.cluster.backbone.license_file_reader import LicenseFileReader
from initat.cluster.backbone.models import License, device_variable, icswEggCradle
from initat.cluster.backbone.serializers import icswEggCradleSerializer
from initat.cluster.frontend.helper_functions import xml_wrapper
from initat.cluster.frontend.rest_views import rest_logging

logger = logging.getLogger("cluster.license")


def login_required_rest(default_value_generator=lambda: []):
    # function to return which captures default value generator
    def dec(fun):
        # actual decorator
        def wrapped(request, *args, **kwargs):
            if request.user.is_authenticated():
                return fun(request, *args, **kwargs)
            else:
                return Response(default_value_generator())
        return wrapped
    return dec


class LicenseViewSet(viewsets.ViewSet):
    # @method_decorator(login_required_rest(lambda: []))
    @rest_logging
    def get_all_licenses(self, request, *args, **kwargs):
        # pseudo-serialize named dict
        _resp = Response(
            [
                {
                    'id': lic.id,
                    'name': lic.name,
                    'description': lic.description,
                    'parameter_usage': {},
                    "fp_state": License.objects.fingerprint_ok(lic.enum_value)
                } for lic in get_available_licenses()
            ]
        )
        for line, level in License.objects.cached_logs:
            logger.log(level, line)
        return _resp

    @rest_logging
    def get_ova_counter(self, request):
        _sys_cradle = icswEggCradle.objects.get(Q(system_cradle=True))
        return Response(
            [
                icswEggCradleSerializer(_sys_cradle).data
            ]
        )


class get_license_packages(ListAPIView):
    # no login required for this since we want to show it in the login page
    @rest_logging
    def list(self, request, *args, **kwargs):
        # this triggers a lot of DB-calls
        License.objects.check_ova_baskets()
        resp = Response(License.objects.get_license_packages())
        for line, level in License.objects.cached_logs:
            logger.log(level, line)
        return resp


class GetLicenseViolations(ListAPIView):
    @method_decorator(login_required_rest(lambda: []))
    @rest_logging
    def list(self, request, *args, **kwargs):
        return Response([])


class GetValidLicenses(RetrieveAPIView):
    @method_decorator(
        login_required_rest(
            lambda: {
                'valid_licenses': [],
                'all_licenses': [l.name for l in LicenseEnum]
            }
        )
    )
    @rest_logging
    def get(self, request, *args, **kwargs):
        resp = Response(
            {
                'valid_licenses': [l.name for l in License.objects.get_valid_licenses()],
                'all_licenses': [l.name for l in LicenseEnum],
            }
        )
        for line, level in License.objects.cached_logs:
            logger.log(level, line)
        return resp


class upload_license_file(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        lic_file = request.FILES['license_file']
        lic_file_content = lic_file.read()

        try:
            dummy_lic = License(
                license_file=lic_file_content,
                file_name="uploaded via webfrontend",
            )
            reader = LicenseFileReader(dummy_lic, log_com=request.xml_response.log)
        except LicenseFileReader.InvalidLicenseFile as e:
            request.xml_response.error(str(e), logger=logger)
        else:
            if License.objects.license_exists(lic_file_content):
                request.xml_response.warn("This license file has already been uploaded")
            else:
                local_cluster_id = device_variable.objects.get_cluster_id()
                file_cluster_ids = reader.get_referenced_cluster_ids()
                if local_cluster_id not in file_cluster_ids:
                    msg = "\n".join(
                        [
                            "This license file contains licenses for the following clusters: {}".format(
                                ", ".join(file_cluster_ids)
                            ),
                            "This cluster has the id {}.".format(
                                local_cluster_id
                            ),
                        ]
                    )
                    request.xml_response.error(msg)
                else:
                    dummy_lic.save()
                    request.xml_response.info(
                        "Successfully uploaded license file: {}".format(
                            str(dummy_lic)
                        )
                    )
                    # srv_com = server_command.srv_command(command="check_license_violations")
                    # contact_server(request, icswServiceEnum.cluster_server,
                    #  srv_com, timeout=60, log_error=True, log_result=False)
