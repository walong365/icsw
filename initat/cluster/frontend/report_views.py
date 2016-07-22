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
import json
import logging
import datetime

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views.generic import View
from threading import Thread


from initat.cluster.backbone.models import device, device_variable

from initat.cluster.frontend.asset_views import PDFReportGenerator

from initat.cluster.frontend.helper_functions import xml_wrapper


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

REPORT_GENERATORS = {}
REPORT_TIMEOUT_SECONDS = 1800

class get_progress(View):
    @method_decorator(login_required)
    def post(self, request):
        report_generator_id = int(request.POST["id"])

        progress = 0
        if report_generator_id in REPORT_GENERATORS:
            progress = REPORT_GENERATORS[report_generator_id].progress

        return HttpResponse(
            json.dumps(
                {
                    'progress': progress
                }
            )
        )


class get_report_pdf(View):
    @method_decorator(login_required)
    def post(self, request):
        report_generator_id = int(request.POST["id"])

        data = ""

        if report_generator_id in REPORT_GENERATORS:
            data = REPORT_GENERATORS[report_generator_id].buffer.getvalue()
            del REPORT_GENERATORS[report_generator_id]

        pdf_b64 = base64.b64encode(data)

        return HttpResponse(
            json.dumps(
                {
                    'pdf': pdf_b64
                }
            )
        )

class generate_report_pdf(View):
    @method_decorator(login_required)
    def post(self, request):
        current_time = datetime.datetime.now()
        ## remove references of old report generators
        for report_generator_id in REPORT_GENERATORS.keys():
            if (current_time - REPORT_GENERATORS[report_generator_id].timestamp).seconds > REPORT_TIMEOUT_SECONDS:
                del REPORT_GENERATORS[report_generator_id]

        settings_dict = {}

        for key in request.POST.iterkeys():
            valuelist = request.POST.getlist(key)
            # look for pk in key

            index = key.split("[")[1][:-1]
            if index not in settings_dict:
                settings_dict[index] = {}

            if key[::-1][:4] == ']kp[':
                settings_dict[index]["pk"] = int(valuelist[0])
            else:
                value = True if valuelist[0] == "true" else False

                settings_dict[index][key.split("[")[-1][:-1]] = value

        pk_settings = {}

        for setting_index in settings_dict:
            pk = settings_dict[setting_index]['pk']
            pk_settings[pk] = {}

            for key in settings_dict[setting_index]:
                if key != 'pk':
                    pk_settings[pk][key] = settings_dict[setting_index][key]

        _devices = []
        for _device in device.objects.filter(idx__in = [int(pk) for pk in pk_settings.keys()]):
            if not _device.is_meta_device:
                _devices.append(_device)

        pdf_report_generator = PDFReportGenerator()
        pdf_report_generator.timestamp = current_time
        REPORT_GENERATORS[id(pdf_report_generator)] = pdf_report_generator

        Thread(target=generate_pdf, args=(_devices, pk_settings, pdf_report_generator)).start()

        return HttpResponse(
            json.dumps(
                {
                    'id': id(pdf_report_generator)
                }
            )
        )

def generate_pdf(_devices, pk_settings, pdf_report_generator):
    for _device in _devices:
        pdf_report_generator.generate_report(_device, pk_settings[_device.idx])

    buffer = pdf_report_generator.get_pdf_as_buffer()
    pdf_report_generator.buffer = buffer
