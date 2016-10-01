# -*- coding: utf-8 -*-
#
# Copyright (C) 2015-2016 Bernhard Mallinger, Andreas Lang-Nevyjel
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
from django.utils.decorators import method_decorator
from django.views.generic import View
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.response import Response

from initat.cluster.backbone.available_licenses import LicenseEnum, get_available_licenses
from initat.cluster.backbone.license_file_reader import LicenseFileReader
from initat.cluster.backbone.models import License, device_variable
from initat.cluster.backbone.models.license import LicenseViolation, LicenseUsage
from initat.cluster.backbone.server_enums import icswServiceEnum
from initat.cluster.frontend.helper_functions import contact_server, xml_wrapper
from initat.cluster.frontend.rest_views import rest_logging
from initat.tools import server_command


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


class get_all_licenses(ListAPIView):
    # @method_decorator(login_required_rest(lambda: []))
    @rest_logging
    def list(self, request, *args, **kwargs):
        # pseudo-serialize named dict
        return Response(
            [
                {
                    'id': lic.id,
                    'name': lic.name,
                    'description': lic.description,
                    'parameter_usage': {
                        k.to_user_name(): v for k, v in LicenseUsage.get_license_usage(lic.enum_value).iteritems()
                    },
                    "fp_state": License.objects.fingerprint_ok(lic.enum_value)
                } for lic in get_available_licenses()
            ]
        )


class get_license_packages(ListAPIView):
    # no login required for this since we want to show it in the login page
    @rest_logging
    def list(self, request, *args, **kwargs):
        return Response(License.objects.get_license_packages())


class GetLicenseViolations(ListAPIView):
    @method_decorator(login_required_rest(lambda: []))
    @rest_logging
    def list(self, request, *args, **kwargs):
        _res = [
            {
                viol.license: {
                    'type': 'hard' if viol.hard else 'soft',
                    'name': LicenseEnum.id_string_to_user_name(viol.license),
                    'revocation_date': viol.date + LicenseUsage.GRACE_PERIOD,
                }
            } for viol in LicenseViolation.objects.all()
        ]
        return Response(_res)


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
        return Response(
            {
                'valid_licenses': [l.name for l in License.objects.get_valid_licenses()],
                'all_licenses': [l.name for l in LicenseEnum],
            }
        )


class upload_license_file(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        lic_file = request.FILES['license_file']
        lic_file_content = lic_file.read()

        try:
            reader = LicenseFileReader(lic_file_content)
        except LicenseFileReader.InvalidLicenseFile as e:
            request.xml_response.error(unicode(e), logger=logger)
        else:
            if License.objects.license_exists(lic_file_content):
                request.xml_response.warn("This license file has already been uploaded")
            else:
                local_cluster_id = device_variable.objects.get_cluster_id()
                file_cluster_ids = reader.get_referenced_cluster_ids()
                if local_cluster_id not in file_cluster_ids:
                    msg = "\n".join(
                        [
                            u"This license file contains licenses for the following clusters: {}".format(
                                ", ".join(file_cluster_ids)
                            ),
                            u"This cluster has the id {}.".format(
                                local_cluster_id
                            ),
                        ]
                    )
                    request.xml_response.error(msg)
                else:
                    new_lic = License(file_name=lic_file.name, license_file=lic_file_content)
                    new_lic.save()
                    request.xml_response.info("Successfully uploaded license file: {}".format(unicode(new_lic)))

                    srv_com = server_command.srv_command(command="check_license_violations")
                    contact_server(request, icswServiceEnum.cluster_server, srv_com, timeout=60, log_error=True, log_result=False)
