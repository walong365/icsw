# Copyright (C) 2016 Gregor Kaufmann, Andreas Lang-Nevyjel
#
# Send feedback to: <g.kaufmann@init.at>, <lang-nevyjel@init.at>
#
# This file is part of icsw-server
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

""" report views """

import base64
import csv
import datetime
import json
import logging
import tempfile

import pytz
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from initat.cluster.backbone.models.functions import can_delete_obj, get_change_reset_list
from django.db.models import Q, Count, Case, When, IntegerField, Sum
from django.http import HttpResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.generic import View
from rest_framework import viewsets, status
from rest_framework.response import Response
from io import BytesIO

from initat.cluster.backbone.models import device, AssetPackage, AssetRun, \
    AssetPackageVersion, AssetType, StaticAssetTemplate, user, RunStatus, RunResult, PackageTypeEnum, \
    AssetBatch, StaticAssetTemplateField, device_variable
from initat.cluster.backbone.models.dispatch import ScheduleItem
from initat.cluster.backbone.serializers import AssetRunDetailSerializer, ScheduleItemSerializer, \
    AssetPackageSerializer, AssetRunOverviewSerializer, StaticAssetTemplateSerializer, \
    StaticAssetTemplateFieldSerializer

from initat.cluster.frontend.helper_functions import xml_wrapper, contact_server

try:
    from openpyxl import Workbook
    from openpyxl.writer.excel import save_virtual_workbook
except ImportError:
    Workbook = None


logger = logging.getLogger(__name__)


class upload_report_gfx(View):
    @method_decorator(xml_wrapper)
    def post(self, request):
        _file = request.FILES[request.FILES.keys()[0]]
        if _file.content_type in ["image/png", "image/jpeg"]:
            system_device = device.objects.filter(name="METADEV_system")[0]
            report_logo_tmp = system_device.device_variable_set.filter(name="__REPORT_LOGO__")
            if report_logo_tmp:
                report_logo_tmp = report_logo_tmp[0]

            else:
                report_logo_tmp = device_variable.objects.create(device=system_device, is_public=False,
                                                                 name="__REPORT_LOGO__",
                                                                 inherit=False,
                                                                 protected=True,
                                                                 var_type="b")
            report_logo_tmp.val_blob = base64.b64encode(_file.read())
            report_logo_tmp.save()

class get_report_gfx(View):
    @method_decorator(xml_wrapper)
    def post(self, request):
        print request
        system_device = device.objects.filter(name="METADEV_system")[0]
        report_logo_tmp = system_device.device_variable_set.filter(name="__REPORT_LOGO__")

        val_blob = ""
        if report_logo_tmp:
            val_blob = report_logo_tmp[0].val_blob

        return HttpResponse(
            json.dumps(
                {
                    'gfx': val_blob
                }
            )
        )