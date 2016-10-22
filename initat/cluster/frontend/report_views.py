# Copyright (C) 2016 Gregor Kaufmann, Andreas Lang-Nevyjel
#
# Send feedback to: <g.kaufmann@init.at>, <lang-nevyjel@init.at>
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
""" report views """

from __future__ import print_function, unicode_literals

import base64
import json
import os

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views.generic import View
from reportlab.lib.pagesizes import landscape, letter, A4, A3

from initat.cluster.backbone.models import device, device_variable
from initat.cluster.backbone.models.report import ReportHistory
from initat.cluster.backbone.server_enums import icswServiceEnum
from initat.cluster.frontend.helper_functions import xml_wrapper, contact_server
from initat.report_server.report import sizeof_fmt, _select_assetruns_for_device
from initat.tools import server_command

_ = {landscape, letter, A4, A3}

if settings.DEBUG:
    _file_root = os.path.join(settings.FILE_ROOT, "frontend", "static")
    NOCTUA_LOGO_PATH = os.path.join(_file_root, "images", "product", "noctua-flat-trans.png")
else:
    _file_root = settings.ICSW_PROD_WEB_DIR
    NOCTUA_LOGO_PATH = os.path.join(settings.STATIC_ROOT, "noctua-flat-trans.png")


########################################################################################################################
# Views
########################################################################################################################


class GetProgress(View):
    @method_decorator(login_required)
    def post(self, request):
        report_id = int(request.POST["id"])

        report_history_object = ReportHistory.objects.filter(idx=report_id)

        progress = 0

        if report_history_object:
            report_history_object = report_history_object[0]

            progress = report_history_object.progress

        return HttpResponse(
            json.dumps(
                {
                    'progress': progress
                }
            )
        )


class GetReportData(View):
    @method_decorator(login_required)
    def post(self, request):
        data_b64 = ""
        report_type = "unknown"
        report_id = None

        if "report_id" in request.POST:
            report_id = int(request.POST["report_id"])

            report_history = ReportHistory.objects.get(idx=report_id)
            report_type = report_history.type
            data = report_history.get_data()
            data_b64 = base64.b64encode(data)
        else:
            report_id = 0

        return HttpResponse(
            json.dumps(
                {
                    report_type: data_b64,
                    "report_id": report_id
                }
            )
        )

    @method_decorator(login_required)
    def get(self, request):
        report_id = int(request.GET["report_id"])

        report_history = ReportHistory.objects.get(idx=report_id)
        report_type = report_history.type
        data = report_history.get_data()
        data_b64 = base64.b64encode(data)

        return HttpResponse(
            json.dumps(
                {
                    report_type: data_b64,
                }
            )
        )


class GenerateReportPdf(View):
    @method_decorator(login_required)
    def post(self, request):
        pk_settings, _devices = _init_report_settings(request)

        if 'HOSTNAME' in request.META:
            pk_settings[-1]['hostname'] = request.META['HOSTNAME']
        else:
            pk_settings[-1]['hostname'] = "unknown"

        srv_com = server_command.srv_command(command="generate_report")
        srv_com['format'] = 'pdf'
        srv_com['pk_settings'] = str(pk_settings)
        srv_com['devices'] = str([d.idx for d in _devices])

        (result, _) = contact_server(
            request,
            icswServiceEnum.report_server,
            srv_com,
        )
        if result is not None:
            report_id = result.get("report_id")
        else:
            report_id = 0

        return HttpResponse(
            json.dumps(
                {
                    'report_id': report_id
                }
            )
        )


class UploadReportGfx(View):
    @method_decorator(xml_wrapper)
    def post(self, request):
        _file = request.FILES[request.FILES.keys()[0]]
        if _file.content_type in ["image/png", "image/jpeg"]:
            system_device = None
            for _device in device.objects.all():
                if _device.is_cluster_device_group():
                    system_device = _device
                    break

            if system_device:
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


class GetReportGfx(View):
    @method_decorator(xml_wrapper)
    def post(self, request):
        id(request)
        val_blob = ""
        system_device = None
        for _device in device.objects.all():
            if _device.is_cluster_device_group():
                system_device = _device
                break

        if system_device:
            report_logo_tmp = system_device.device_variable_set.filter(name="__REPORT_LOGO__")

            if report_logo_tmp:
                val_blob = report_logo_tmp[0].val_blob

        return HttpResponse(
            json.dumps(
                {
                    'gfx': val_blob
                }
            )
        )


class GenerateReportXlsx(View):
    @method_decorator(login_required)
    def post(self, request):
        pk_settings, _devices = _init_report_settings(request)

        srv_com = server_command.srv_command(command="generate_report")
        srv_com['format'] = 'xlsx'
        srv_com['pk_settings'] = str(pk_settings)
        srv_com['devices'] = str([d.idx for d in _devices])

        (result, _) = contact_server(
            request,
            icswServiceEnum.report_server,
            srv_com,
        )
        if result is not None:
            report_id = result.get("report_id")
        else:
            report_id = 0

        return HttpResponse(
            json.dumps(
                {
                    'report_id': report_id
                }
            )
        )


class ReportDataAvailable(View):
    @method_decorator(login_required)
    def post(self, request):
        idx_list = []
        for item in request.POST.iterlists():
            key, _list = item
            if key == "idx_list[]":
                idx_list = _list
                break

        assetbatch_id = request.POST.get("assetbatch_id", None)
        if assetbatch_id:
            assetbatch_id = int(assetbatch_id)

        pk_setting_dict = {}

        meta_devices = []

        group_selected_runs = {}

        for idx in idx_list:
            idx = int(idx)
            _device = device.objects.get(idx=idx)

            if _device.is_meta_device:
                meta_devices.append(_device)
                continue

            selected_runs = _select_assetruns_for_device(_device, assetbatch_id=assetbatch_id)
            selected_run_info_array = \
                [(ar.run_type, str(ar.run_start_time), ar.asset_batch.idx) for ar in selected_runs]

            if _device.device_group_name() not in group_selected_runs:
                group_selected_runs[_device.device_group_name()] = []

            for run_type in [ar.run_type for ar in selected_runs]:
                if run_type not in group_selected_runs[_device.device_group_name()]:
                    group_selected_runs[_device.device_group_name()].append(run_type)

            pk_setting_dict[idx] = selected_run_info_array

        for _device in meta_devices:
            if _device.device_group_name() in group_selected_runs:
                pk_setting_dict[_device.idx] = group_selected_runs[_device.device_group_name()]

        return HttpResponse(
            json.dumps(
                {
                    'pk_setting_dict': pk_setting_dict,
                }
            )
        )


class ReportHistoryAvailable(View):
    @method_decorator(login_required)
    def post(self, request):
        id(request)
        data = {}
        report_ids = []

        for report_history in ReportHistory.objects.all():
            if not report_history.created_by_user:
                continue
            if not report_history.created_at_time:
                continue

            o = {
                'report_id': str(report_history.idx),
                'created_by_user': str(report_history.created_by_user),
                'created_at_time': str(report_history.created_at_time),
                'number_of_pages': str(report_history.number_of_pages),
                'size': sizeof_fmt(report_history.size),
                'raw_size': report_history.b64_size,
                'type': str(report_history.type),
                'number_of_downloads': str(report_history.number_of_downloads)
            }

            report_ids.append(report_history.idx)
            data[report_history.idx] = o

        return HttpResponse(
            json.dumps(
                {
                    'report_ids': list(reversed(sorted(report_ids))),
                    'report_history': data
                }
            )
        )


class UpdateDownloadCount(View):
    @method_decorator(login_required)
    def post(self, request):
        idx = int(request.POST["idx"])

        report_history = ReportHistory.objects.get(idx=idx)

        report_history.number_of_downloads += 1
        report_history.save()

        return HttpResponse(
            json.dumps(
                {
                    'download_count': report_history.number_of_downloads
                }
            )
        )


########################################################################################################################
# Helper Functions
########################################################################################################################

def _init_report_settings(request):
    settings_dict = {}

    _settings = json.loads(request.POST["json"])
    for index, stuff in enumerate(_settings):
        settings_dict[index] = stuff

    pk_settings = {}

    for setting_index in settings_dict:
        pk = settings_dict[setting_index]['pk']
        pk_settings[pk] = {}

        for key in settings_dict[setting_index]:
            if key != 'pk':
                pk_settings[pk][key] = settings_dict[setting_index][key]

    _devices = []
    for _device in device.objects.filter(idx__in=[int(pk) for pk in pk_settings.keys()]):
        if not _device.is_meta_device:
            _devices.append(_device)

    return pk_settings, _devices
