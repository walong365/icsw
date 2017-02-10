# -*- coding: utf-8 -*-
#
# Copyright (C) 2013-2017 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw-server-server
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

""" License views """

import collections
import json
import logging

from django.contrib.auth.decorators import login_required
from django.http.response import HttpResponse
from django.utils.decorators import method_decorator
from django.views.generic import View
from rest_framework.generics import ListAPIView
from rest_framework.response import Response

from initat.cluster.backbone.models import ext_license_version_state_coarse, ext_license_usage_coarse, \
    ext_license_state_coarse
from initat.cluster.backbone.serializers import ext_license_state_coarse_serializer, \
    ext_license_version_state_coarse_serializer
from initat.cluster.backbone.server_enums import icswServiceEnum
from initat.cluster.frontend.common import duration_utils
from initat.cluster.frontend.helper_functions import contact_server, xml_wrapper
from initat.tools import server_command

logger = logging.getLogger("cluster.license")


def _dump_xml(s_node):
    return (
        s_node.tag.split("}")[-1],
        {
            _key: int(_value) if _value.isdigit() else _value for _key, _value in s_node.attrib.items()
        },
        [
            _dump_xml(_child) for _child in s_node
        ]
    )


class license_liveview(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        srv_com = server_command.srv_command(command="get_license_usage")
        result = contact_server(request, icswServiceEnum.rms_server, srv_com, timeout=10)
        _lic_dump = {}
        if result is not None:
            result = result.tree
            # not needed
            # _start_node = result.xpath(".//*[local-name() = 'license_usage']")
            # if len(_start_node):
            #     _lic_dump = _dump_xml(_start_node[0])
        request.xml_response["result"] = result


class get_license_overview_steps(View):
    @method_decorator(login_required)
    def post(self, request):
        _post = request.POST
        steps = duration_utils.get_steps(_post['duration_type'], _post['date'])
        return HttpResponse(json.dumps(steps), content_type="application/json")


class license_state_coarse_list(ListAPIView):

    serializer_class = ext_license_state_coarse_serializer

    def list(self, request, *args, **kwargs):
        lic_id = int(request.GET["lic_id"])
        (duration_type, start, end) = duration_utils.parse_duration_from_request(request)

        # todo, fixme: replace with egg consumer call
        if False:   # LicenseLockListExtLicense.objects.is_ext_license_locked(LicenseEnum.license_optimisation_management, lic_id):
            return Response([])
        else:
            # LicenseUsage.log_usage(
            #     LicenseEnum.license_optimisation_management,
            #     LicenseParameterTypeEnum.ext_lic,
            #     lic_id
            # )

            logger.debug(
                "retrieving data for license {} from {} to {}, type {}".format(
                    lic_id,
                    start,
                    end,
                    duration_type
                )
            )
            self.object_list = ext_license_state_coarse.objects.filter(
                ext_license_id=lic_id,
                ext_license_check_coarse__duration_type=duration_type.ID,
                ext_license_check_coarse__start_date__range=(start, end)
            )

            serializer = self.get_serializer(self.object_list, many=True)
            return Response(serializer.data)


class license_version_state_coarse_list(ListAPIView):

    serializer_class = ext_license_version_state_coarse_serializer

    def list(self, request, *args, **kwargs):
        lic_id = request.GET["lic_id"]
        (duration_type, start, end) = duration_utils.parse_duration_from_request(request)

        self.object_list = ext_license_version_state_coarse.objects.filter(
            ext_license_version__ext_license=lic_id,
            ext_license_check_coarse__duration_type=duration_type.ID,
            ext_license_check_coarse__start_date__range=(start, end)
        )

        serializer = self.get_serializer(self.object_list, many=True)
        return Response(serializer.data)


class _license_usage_view(ListAPIView):
    '''
    generic view base class for user and device
    '''
    def list(self, request, *args, **kwargs):
        lic_id = request.GET["lic_id"]
        (duration_type, start, end) = duration_utils.parse_duration_from_request(request)

        data = ext_license_usage_coarse.objects.filter(
            ext_license_version_state_coarse__ext_license_version__ext_license=lic_id,
            ext_license_version_state_coarse__ext_license_check_coarse__duration_type=duration_type.ID,
            ext_license_version_state_coarse__ext_license_check_coarse__start_date__range=(start, end)
        ).extra(
            select={"val": "num * backbone_ext_license_usage_coarse.frequency"}
        ).values_list(self.get_name_column_name(), "ext_license_version_state_coarse__ext_license_check_coarse__start_date", "val")
        # for device, we possibly will also want the long name, in which case we could have two columns here and combine them in the loop below or so

        summing = collections.defaultdict(lambda: 0)

        # sum up (would be nicer in db query, but it doesn't seem to be combinable with val calculation)
        for d in data:
            name = d[0]
            full_start_date = d[1]
            val = d[2]
            summing[(name, full_start_date)] += val

        result = []
        for entry in summing.items():
            name = entry[0][0]
            full_start_date = entry[0][1]
            val_sum = entry[1]
            result.append(
                {
                    'type': name,
                    'val': val_sum,
                    'full_start_date': full_start_date,
                    'display_date': duration_type.get_display_date(full_start_date)
                }
            )

        return Response(result)


class license_user_coarse_list(_license_usage_view):
    def get_name_column_name(self):
        return "ext_license_user__name"


class license_device_coarse_list(_license_usage_view):
    def get_name_column_name(self):
        return "ext_license_client__short_name"
