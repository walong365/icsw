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

""" asset views """

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
from initat.cluster.frontend.helper_functions import contact_server, xml_wrapper

from initat.cluster.backbone.models import device, AssetPackage, AssetRun, \
    AssetPackageVersion, AssetType, StaticAssetTemplate, user, RunStatus, RunResult, PackageTypeEnum, \
    AssetBatch, StaticAssetTemplateField, StaticAsset, StaticAssetFieldValue
from initat.cluster.backbone.models.dispatch import ScheduleItem
from initat.cluster.backbone.serializers import AssetRunDetailSerializer, ScheduleItemSerializer, \
    AssetPackageSerializer, AssetRunOverviewSerializer, StaticAssetTemplateSerializer, \
    StaticAssetTemplateFieldSerializer, StaticAssetSerializer, StaticAssetTemplateRefsSerializer

try:
    from openpyxl import Workbook
    from openpyxl.writer.excel import save_virtual_workbook
except ImportError:
    Workbook = None


logger = logging.getLogger(__name__)


class run_assetrun_for_device_now(View):
    @method_decorator(login_required)
    def post(self, request):
        _dev = device.objects.get(pk=int(request.POST['pk']))
        ScheduleItem.objects.create(
            device=_dev,
            source=10,
            planned_date=datetime.datetime.now(tz=pytz.utc),
            run_now=True,
            dispatch_setting=None
        )
        return HttpResponse(
            json.dumps({"state": "started run"}),
            content_type="application/json"
        )


class get_devices_for_asset(View):
    @method_decorator(login_required)
    def post(self, request, *args, **kwargs):
        apv = AssetPackageVersion.objects.get(pk=int(request.POST['pk']))

        return HttpResponse(
            json.dumps(
                {
                    'devices': list(set([ar.asset_batch.device.pk for ar in apv.assetrun_set.all()]))
                }
            ),
            content_type="application/json"
        )


class get_assetrun_diffs(View):
    @method_decorator(login_required)
    def post(self, request):
        ar_pk1 = request.POST['pk1']
        ar_pk2 = request.POST['pk2']

        ar1 = AssetRun.objects.get(pk=int(ar_pk1))
        ar2 = AssetRun.objects.get(pk=int(ar_pk2))

        removed = ar1.get_asset_changeset(ar2)
        added = ar2.get_asset_changeset(ar1)

        return HttpResponse(
            json.dumps(
                {
                    'added': [str(obj) for obj in added],
                    'removed': [str(obj) for obj in removed]
                }
            ),
            content_type="application/json"
        )


class get_versions_for_package(View):
    @method_decorator(login_required)
    def post(self, request):
        pk = request.POST['pk']

        ap = AssetPackage.objects.get(pk=int(pk))

        return HttpResponse(
            json.dumps(
                {
                    'versions': [
                        (v.idx, v.version, v.release, v.size) for v in ap.assetpackageversion_set.all()
                    ]
                }
            ),
            content_type="application/json"
        )


class get_assets_for_asset_run(View):
    @method_decorator(login_required)
    def post(self, request, *args, **kwargs):
        ar = AssetRun.objects.get(pk=int(request.POST['pk']))

        if ar.run_type == AssetType.PACKAGE:
            return HttpResponse(
                json.dumps(
                    {
                        'assets': [
                            (
                                str(bap.name),
                                str(bap.version),
                                str(bap.release),
                                str(bap.size),
                                str(bap.install_date) if bap.install_date else "Unknown",
                                str(bap.package_type.name)
                            ) for bap in ar.generate_assets_no_save()
                        ]
                    }
                )
            )
        elif ar.run_type == AssetType.HARDWARE:
            return HttpResponse(
                json.dumps(
                    {
                        'assets': [
                            (
                                str(bah.type),
                                str(bah.info_dict)
                            ) for bah in ar.generate_assets_no_save()
                        ]
                    }
                )
            )
        elif ar.run_type == AssetType.LICENSE:
            return HttpResponse(
                json.dumps(
                    {
                        'assets': [
                            (
                                str(bal.name),
                                str(bal.license_key)
                            ) for bal in ar.generate_assets_no_save()
                        ]
                    }
                )
            )
        elif ar.run_type == AssetType.UPDATE:
            return HttpResponse(
                json.dumps(
                    {
                        'assets': [
                            (
                                str(bau.name),
                                str(bau.install_date),
                                str(bau.status)
                            ) for bau in ar.generate_assets_no_save()
                        ]
                    }
                )
            )
        elif ar.run_type == AssetType.PROCESS:
            return HttpResponse(
                json.dumps(
                    {
                        'assets': [
                            (
                                str(bap.name),
                                str(bap.pid)
                            ) for bap in ar.generate_assets_no_save()
                        ]
                    }
                )
            )
        elif ar.run_type == AssetType.PENDING_UPDATE:
            return HttpResponse(
                json.dumps(
                    {
                        'assets': [
                            (
                                str(bapu.name),
                                str(bapu.version),
                                str(bapu.optional)
                            ) for bapu in ar.generate_assets_no_save()
                        ]
                    }
                )
            )
        else:
            return HttpResponse(
                json.dumps(
                    {
                        'assets': [str(ba) for ba in ar.generate_assets_no_save]
                    }
                )
            )


class ScheduledRunViewSet(viewsets.ViewSet):
    def list(self, request):
        if "pks" in request.query_params:
            queryset = ScheduleItem.objects.filter(
                Q(device__in=json.loads(request.query_params.getlist("pks")[0]))
            )
        else:
            queryset = ScheduleItem.objects.all()
        serializer = ScheduleItemSerializer(queryset, many=True)
        return Response(serializer.data)


class AssetRunsViewSet(viewsets.ViewSet):
    def list_all(self, request):
        if "pks" in request.query_params:
           queryset = AssetRun.objects.filter(
               Q(asset_batch__device__in=json.loads(request.query_params.getlist("pks")[0]))
           )
        else:
            queryset = AssetRun.objects.all()

        queryset = queryset.filter(Q(created__gt=timezone.now() - datetime.timedelta(days=30)))

        queryset = queryset.order_by(
            # should be created, FIXME later
            "-idx",
            "-run_start_time")
        # ).annotate(
        #     num_packages=Count("asset_batch__packages"),
        #     num_hardware=Count("assethardwareentry"),
        #     num_processes=Count("assetprocessentry"),
        #     num_licenses=Count("assetlicenseentry"),
        #     num_updates=Sum(Case(When(assetupdateentry__installed=True, then=1), output_field=IntegerField(), default=0)),
        #     num_pending_updates=Sum(Case(When(assetupdateentry__installed=False, then=1), output_field=IntegerField(), default=0)),
        #     num_pci_entries=Count("assetpcientry"),
        #     num_asset_handles=Count("assetdmihead__assetdmihandle"),
        #     num_hw_entries=Sum("asset_batch__cpus")
        # )

        for ar in queryset:
            ar.num_packages = len(ar.asset_batch.packages.all())
            ar.num_hardware = len(ar.assethardwareentry_set.all())
            ar.num_processes = len(ar.assetprocessentry_set.all())
            ar.num_licenses = len(ar.assetlicenseentry_set.all())
            ar.num_updates = len(ar.assetupdateentry_set.all())
            ar.num_pending_updates = len(ar.assetupdateentry_set.all())
            ar.num_pci_entries = len(ar.assetpcientry_set.all())
            ar.num_asset_handles = 0
            for dmihead in ar.assetdmihead_set.all():
                ar.num_asset_handles += len(dmihead.assetdmihandle_set.all())
            ar.num_hw_entries = len(ar.asset_batch.cpus.all())

        serializer = AssetRunOverviewSerializer(queryset, many=True)

        return Response(serializer.data)

    def get_details(self, request):
        queryset = AssetRun.objects.prefetch_related(
            "asset_batch__packages",
            "assethardwareentry_set",
            "assetprocessentry_set",
            "assetupdateentry_set",
            "assetlicenseentry_set",
            "assetpcientry_set",
            "assetdmihead_set__assetdmihandle_set__assetdmivalue_set",
        ).filter(
            Q(pk=request.query_params["pk"])
        )
        serializer = AssetRunDetailSerializer(queryset, many=True)
        return Response(serializer.data)


class AssetPackageViewSet(viewsets.ViewSet):
    @method_decorator(login_required)
    def get_all(self, request):
        queryset = AssetPackage.objects.all().prefetch_related(
            "assetpackageversion_set"
        ).order_by(
            "name",
            "package_type",
        )
        serializer = AssetPackageSerializer(queryset, many=True)
        return Response(serializer.data)


class StaticAssetTemplateViewSet(viewsets.ViewSet):
    @method_decorator(login_required)
    def get_all(self, request):
        queryset = StaticAssetTemplate.objects.all().prefetch_related(
            "staticassettemplatefield_set"
        )
        [_template.check_ordering() for _template in queryset]
        serializer = StaticAssetTemplateSerializer(queryset, many=True)
        return Response(serializer.data)

    @method_decorator(login_required)
    def get_refs(self, request):
        queryset = StaticAsset.objects.all().prefetch_related(
            "device__domain_tree_node"
        )
        _data = []
        for _entry in queryset:
            _template_idx = _entry.static_asset_template_id
            _full_name = _entry.device.full_name
            _data.append({"static_asset_template": _template_idx, "device_name": _full_name})
        return Response(StaticAssetTemplateRefsSerializer(_data, many=True).data)

    @method_decorator(login_required)
    def reorder_fields(self, request):
        field_1 = StaticAssetTemplateField.objects.get(Q(pk=request.data["field1"]))
        field_2 = StaticAssetTemplateField.objects.get(Q(pk=request.data["field2"]))
        _swap = field_1.ordering
        field_1.ordering = field_2.ordering
        field_2.ordering = _swap
        field_1.save(update_fields=["ordering"])
        field_2.save(update_fields=["ordering"])
        return Response({"msg": "done"})

    @method_decorator(login_required)
    def create_template(self, request):
        new_obj = StaticAssetTemplateSerializer(data=request.data)
        if new_obj.is_valid():
            new_obj.save()
        else:
            raise ValidationError("New Template is not valid: {}".format(new_obj.errors))
        return Response(new_obj.data)

    @method_decorator(login_required)
    def delete_template(self, request, *args, **kwargs):
        cur_obj = StaticAssetTemplate.objects.get(Q(pk=kwargs["pk"]))
        can_delete_answer = can_delete_obj(cur_obj)
        if can_delete_answer:
            cur_obj.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        else:
            raise ValueError(can_delete_answer.msg)

    @method_decorator(login_required)
    def create_field(self, request):
        new_obj = StaticAssetTemplateFieldSerializer(data=request.data)
        if new_obj.is_valid():
            new_obj.save()
        else:
            raise ValidationError("New TemplateField is not valid: {}".format(new_obj.errors))
        return Response(new_obj.data)

    @method_decorator(login_required())
    def delete_field(self, request, **kwargs):
        cur_obj = StaticAssetTemplateField.objects.get(Q(pk=kwargs["pk"]))
        can_delete_answer = can_delete_obj(cur_obj)
        if can_delete_answer:
            cur_obj.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
            # it makes no sense to return something meaningful because the DestroyModelMixin returns
            # a 204 status on successful deletion
            # print "****", "del"
            # print unicode(cur_obj), resp.data
            # if not resp.data:
            #    resp.data = {}
            # resp.data["_messages"] = [u"deleted '%s'" % (unicode(cur_obj))]
            # return resp
        else:
            raise ValueError(can_delete_answer.msg)

    @method_decorator(login_required())
    def store_field(self, request, **kwargs):
        _prev_field = StaticAssetTemplateField.objects.get(Q(pk=kwargs["pk"]))
        # print _prev_var
        _cur_ser = StaticAssetTemplateFieldSerializer(
            StaticAssetTemplateField.objects.get(Q(pk=kwargs["pk"])),
            data=request.data
        )
        # print "*" * 20
        # print _cur_ser.device_variable_type
        if _cur_ser.is_valid():
            _new_field = _cur_ser.save()
        else:
            # todo, fixme
            raise ValidationError("Validation error: {}".format(str(_cur_ser.errors)))
        resp = _cur_ser.data
        c_list, r_list = get_change_reset_list(_prev_field, _new_field, request.data)
        resp = Response(resp)
        # print c_list, r_list
        resp.data["_change_list"] = c_list
        resp.data["_reset_list"] = r_list
        return resp


class copy_static_template(View):
    @method_decorator(login_required)
    def post(self, request):
        src_obj = StaticAssetTemplate.objects.get(Q(pk=request.POST["src_idx"]))
        create_user = user.objects.get(Q(pk=request.POST["user_idx"]))
        new_obj = json.loads(request.POST["new_obj"])
        new_template = src_obj.copy(new_obj, create_user)
        serializer = StaticAssetTemplateSerializer(new_template)
        return HttpResponse(
            json.dumps(serializer.data),
            content_type="application/json"
        )


class export_assetruns_to_csv(View):
    @method_decorator(login_required)
    def post(self, request):
        tmpfile = tempfile.SpooledTemporaryFile()

        writer = csv.writer(tmpfile)

        ar = AssetRun.objects.get(idx=int(request.POST["pk"]))

        _generate_csv_entry_for_assetrun(ar, writer.writerow)

        tmpfile.seek(0)
        s = tmpfile.read()

        return HttpResponse(
            json.dumps(
                {
                    'csv': s
                }
            )
        )


class export_packages_to_csv(View):
    @method_decorator(login_required)
    def post(self, request):
        tmpfile = tempfile.SpooledTemporaryFile()

        writer = csv.writer(tmpfile)

        apv = AssetPackageVersion.objects.select_related("asset_package").all()

        base_header = ['Name',
                       'Package Type',
                       'Version',
                       'Release',
                       'Size']

        writer.writerow(base_header)

        for version in apv:
            row = []

            row.append(version.asset_package.name)
            row.append(PackageTypeEnum(version.asset_package.package_type).name)
            row.append(version.version)
            row.append(version.release)
            row.append(version.size)

            writer.writerow(row)

        tmpfile.seek(0)
        s = tmpfile.read()

        return HttpResponse(
            json.dumps(
                {
                    'csv': s
                }
            )
        )


class export_scheduled_runs_to_csv(View):
    @method_decorator(login_required)
    def post(self, request):
        tmpfile = tempfile.SpooledTemporaryFile()

        writer = csv.writer(tmpfile)

        schedule_items = ScheduleItem.objects.select_related("dispatch_setting").all()

        base_header = [
            'Device Name',
            'Planned Time',
            'Dispatch Setting Name'
        ]

        writer.writerow(base_header)

        for schedule_item in schedule_items:
            row = []

            row.append(schedule_item.device.full_name)
            row.append(schedule_item.planned_date)
            row.append(schedule_item.dispatch_setting.name)

            writer.writerow(row)

        tmpfile.seek(0)
        s = tmpfile.read()

        return HttpResponse(
            json.dumps(
                {
                    'csv': s
                }
            )
        )


class export_assetbatch_to_xlsx(View):
    @method_decorator(login_required)
    def post(self, request):
        ab = AssetBatch.objects.get(idx=int(request.POST["pk"]))

        assetruns = ab.assetrun_set.all()

        workbook = Workbook()
        workbook.remove_sheet(workbook.active)

        for ar in assetruns:
            sheet = workbook.create_sheet()
            sheet.title = AssetType(ar.run_type).name

            _generate_csv_entry_for_assetrun(ar, sheet.append)

        s = save_virtual_workbook(workbook)

        new_s = base64.b64encode(s)

        return HttpResponse(
            json.dumps(
                {
                    'xlsx': new_s
                }
            )
        )


def addPageNumber(canvas, doc):
    from reportlab.lib.units import mm

    page_num = canvas.getPageNumber()
    text = "Page %s" % page_num
    canvas.drawRightString(285 * mm, 4 * mm, text)


class export_assetbatch_to_pdf(View):
    rows = []
    row_info = []
    _asset_type = None

    # def addHeader(self, _canvas, doc):
    #     from reportlab.lib.units import mm
    #     from reportlab.lib.pagesizes import A4
    #
    #     heigth, width = A4
    #
    #     text = "run_type:{}, batch_id:{}, scanned_device:{}".format(self.row_info[0], self.row_info[1],
    #                                                                 self.row_info[5])
    #     _canvas.drawString(10 * mm, heigth - 8 * mm, text)

    def _row_collector(self, _row):
        self.row_info = _row[0:8]

        if self._asset_type == AssetType.UPDATE:
            update_name = str(_row[8])
            install_date = str(_row[12])
            update_status = str(_row[13])
            self.rows.append([update_name, install_date, update_status])

        elif self._asset_type == AssetType.LICENSE:
            license_name = str(_row[8])
            license_key = str(_row[9])
            self.rows.append((license_name, license_key))

        elif self._asset_type == AssetType.PENDING_UPDATE:
            update_name = str(_row[8])
            update_version = str(_row[9])
            update_release = str(_row[10])
            update_kb_idx = str(_row[11])
            update_install_date = str(_row[12])
            update_status = str(_row[13])
            update_optional = str(_row[14])
            update_installed = str(_row[15])
            self.rows.append((update_name, update_version, update_release, update_kb_idx, update_install_date,
                              update_status, update_optional, update_installed))

        elif self._asset_type == AssetType.PROCESS:
            process_name = str(_row[8])
            process_id = str(_row[9])
            self.rows.append((process_name, process_id))

        elif self._asset_type == AssetType.HARDWARE:
            hardware_node_type = str(_row[8])
            hardware_depth = str(_row[9])
            hardware_attributes = str(_row[10])
            self.rows.append((hardware_node_type, hardware_depth, hardware_attributes))

        elif self._asset_type == AssetType.PACKAGE:
            package_name = str(_row[8])
            package_version = str(_row[9])
            package_release = str(_row[10])
            package_size = str(_row[11])
            package_install_date = str(_row[12])
            package_type = str(_row[13])
            self.rows.append((package_name, package_version, package_release, package_size,
                              package_install_date, package_type))

        elif self._asset_type == AssetType.PRETTYWINHW:
            _entry = str(_row[8])
            self.rows.append([_entry])

        elif self._asset_type == AssetType.DMI:
            handle = str(_row[8])
            dmi_type = str(_row[9])
            header = str(_row[10])
            key = str(_row[11])
            value = str(_row[12])
            self.rows.append((handle, dmi_type, header, key, value))

        else:
            self.rows.append([str(item) for item in _row])

    @method_decorator(login_required)
    def post(self, request):
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, PageBreak
        from reportlab.lib.styles import getSampleStyleSheet
        from io import BytesIO

        ab = AssetBatch.objects.get(idx=int(request.POST["pk"]))

        elements = []
        buffer = BytesIO()

        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30,
                                bottomMargin=18)
        doc.pagesize = landscape(A4)

        assetruns = ab.assetrun_set.all()
        for ar in assetruns:
            self.rows = []
            self._asset_type = AssetType(ar.run_type)

            _generate_csv_entry_for_assetrun(ar, self._row_collector)

            data = self.rows

            style = TableStyle([('ALIGN', (1, 1), (-2, -2), 'RIGHT'),
                                ('TEXTCOLOR', (1, 1), (-2, -2), colors.red),
                                ('VALIGN', (0, 0), (0, -1), 'TOP'),
                                ('TEXTCOLOR', (0, 0), (0, -1), colors.blue),
                                ('ALIGN', (0, -1), (-1, -1), 'CENTER'),
                                ('VALIGN', (0, -1), (-1, -1), 'MIDDLE'),
                                ('TEXTCOLOR', (0, -1), (-1, -1), colors.green),
                                ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.black),
                                ('BOX', (0, 0), (-1, -1), 0.25, colors.black),
                                ])

            # Configure style and word wrap
            s = getSampleStyleSheet()
            s = s["BodyText"]
            s.wordWrap = 'CJK'
            data2 = [[Paragraph(cell, s) for cell in row] for row in data]
            t = Table(data2)
            t.setStyle(style)

            # Send the data and build the file
            elements.append(Paragraph("Run Type: " + str(self.row_info[0]), s))
            elements.append(Paragraph("Batch ID: " + str(self.row_info[1]), s))
            elements.append(Paragraph("Run Start Time: " + str(self.row_info[2]), s))
            elements.append(Paragraph("Run End Time: " + str(self.row_info[3]), s))
            elements.append(Paragraph("Total Run Time: " + str(self.row_info[4]), s))
            elements.append(Paragraph("Scanned Device: " + str(self.row_info[5]), s))
            elements.append(Paragraph("Scan Status: " + str(self.row_info[6]), s))
            elements.append(Paragraph("Scan Status: " + str(self.row_info[7]), s))
            elements.append(PageBreak())

            elements.append(t)
            elements.append(PageBreak())

        doc.build(elements, onFirstPage=addPageNumber, onLaterPages=addPageNumber)

        pdf = buffer.getvalue()
        buffer.close()

        pdf_b64 = base64.b64encode(pdf)

        return HttpResponse(
            json.dumps(
                {
                    'pdf': pdf_b64
                }
            )
        )


def _generate_csv_entry_for_assetrun(ar, row_writer_func):
    base_header = [
        'Asset Type',
        'Batch Id',
        'Start Time',
        'End Time',
        'Total Run Time',
        'device',
        'status',
        'result'
    ]

    if ar.run_start_time and ar.run_end_time:
        ar_run_time = str((ar.run_end_time - ar.run_start_time).total_seconds())
    else:
        ar_run_time = "N/A"

    base_row = [AssetType(ar.run_type).name,
                str(ar.asset_batch.idx),
                str(ar.run_start_time),
                str(ar.run_end_time),
                ar_run_time,
                str(ar.device.full_name),
                RunStatus(ar.run_status).name,
                RunResult(ar.run_result).name]

    if ar.run_type == AssetType.PACKAGE:
        base_header.extend([
            'package_name',
            'package_version',
            'package_release',
            'package_size',
            'package_install_date',
            'package_type'])

        row_writer_func(base_header)

        for package_version in ar.packages.select_related("asset_package").all():
            row = base_row[:]

            row.append(package_version.asset_package.name)
            row.append(package_version.version)
            row.append(package_version.release)
            row.append(package_version.size)
            row.append(package_version.created)
            row.append(PackageTypeEnum(package_version.asset_package.package_type).name)

            row_writer_func(row)

    elif ar.run_type == AssetType.HARDWARE:
        base_header.extend([
            'hardware_node_type',
            'hardware_depth',
            'hardware_attributes', ])

        row_writer_func(base_header)

        for hardware_item in ar.assethardwareentry_set.all():
            row = base_row[:]

            row.append(hardware_item.type)
            row.append(hardware_item.depth)
            row.append(hardware_item.attributes)

            row_writer_func(row)

    elif ar.run_type == AssetType.LICENSE:
        base_header.extend(
            [
                'license_name',
                'license_key'
            ]
        )

        row_writer_func(base_header)

        for license in ar.assetlicenseentry_set.all():
            row = base_row[:]

            row.append(license.name)
            row.append(license.license_key)

            row_writer_func(row)

    elif ar.run_type == AssetType.UPDATE:
        base_header.extend([
            'update_name',
            'update_version',
            'update_release',
            'update_kb_idx',
            'update_install_date',
            'update_status',
            'update_optional',
            'update_installed'
        ])

        row_writer_func(base_header)

        for update in ar.assetupdateentry_set.all():
            row = base_row[:]

            row.append(update.name)
            row.append(update.version)
            row.append(update.release)
            row.append(update.kb_idx)
            row.append(update.install_date)
            row.append(update.status)
            row.append(update.optional)
            row.append(update.installed)

            row_writer_func(row)

    elif ar.run_type == AssetType.PROCESS:
        base_header.extend([
            'process_name',
            'process_id'
        ])

        row_writer_func(base_header)

        for process in ar.assetprocessentry_set.all():
            row = base_row[:]

            row.append(str(process.name))
            row.append(str(process.pid))

            row_writer_func(row)

    elif ar.run_type == AssetType.PENDING_UPDATE:
        base_header.extend([
            'update_name',
            'update_version',
            'update_release',
            'update_kb_idx',
            'update_install_date',
            'update_status',
            'update_optional',
            'update_installed'
        ])

        row_writer_func(base_header)

        for update in ar.assetupdateentry_set.all():
            row = base_row[:]

            row.append(update.name)
            row.append(update.version)
            row.append(update.release)
            row.append(update.kb_idx)
            row.append(update.install_date)
            row.append(update.status)
            row.append(update.optional)
            row.append(update.installed)

            row_writer_func(row)

    elif ar.run_type == AssetType.PCI:
        base_header.extend([
            'pci_info'
        ])

        row_writer_func(base_header)

        for pci_entry in ar.assetpcientry_set.all():
            row = base_row[:]

            row.append(str(pci_entry))

            row_writer_func(row)

    elif ar.run_type == AssetType.DMI:
        base_header.extend([
            'handle',
            'dmi_type',
            'header',
            'key',
            'value'
        ])

        row_writer_func(base_header)

        for dmi_head in ar.assetdmihead_set.all():
            for dmi_handle in dmi_head.assetdmihandle_set.all():
                handle = dmi_handle.handle
                dmi_type = dmi_handle.dmi_type
                header = dmi_handle.header

                for dmi_value in dmi_handle.assetdmivalue_set.all():
                    key = dmi_value.key
                    value = dmi_value.value

                    row = base_row[:]

                    row.append(handle)
                    row.append(dmi_type)
                    row.append(header)
                    row.append(key)
                    row.append(value)

                    row_writer_func(row)

    elif ar.run_type == AssetType.PRETTYWINHW:
        base_header.extend([
            'entry'
        ])

        row_writer_func(base_header)

        for cpu in ar.cpus.all():
            row = base_row[:]

            row.append(str(cpu))

            row_writer_func(row)

        for memorymodule in ar.memory_modules.all():
            row = base_row[:]

            row.append(str(memorymodule))

            row_writer_func(row)

        for gpu in ar.gpus.all():
            row = base_row[:]

            row.append(str(gpu))

            row_writer_func(row)

        for hdd in ar.hdds.all():
            row = base_row[:]

            row.append(str(hdd))

            row_writer_func(row)

        for partition in ar.partitions.all():
            row = base_row[:]

            row.append(str(partition))

            row_writer_func(row)

        for display in ar.displays.all():
            row = base_row[:]

            row.append(str(display))

            row_writer_func(row)


class DeviceStaticAssetViewSet(viewsets.ViewSet):
    @method_decorator(login_required)
    def create_asset(self, request):
        new_asset = StaticAssetSerializer(data=request.data)
        if new_asset.is_valid():
            asset = new_asset.save()
            asset.add_fields()
            return Response(StaticAssetSerializer(asset).data)
        else:
            raise ValidationError(
                "cannot create new StaticAsset"
            )

    @method_decorator(login_required)
    def delete_asset(self, request, **kwargs):
        StaticAsset.objects.get(Q(idx=kwargs["pk"])).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @method_decorator(login_required())
    def delete_field(self, request, **kwargs):
        cur_obj = StaticAssetFieldValue.objects.get(Q(pk=kwargs["pk"]))
        can_delete_answer = can_delete_obj(cur_obj)
        if can_delete_answer:
            cur_obj.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        else:
            raise ValueError(can_delete_answer.msg)

    @method_decorator(login_required)
    def add_unused(self, request, **kwargs):
        _asset = StaticAsset.objects.get(Q(pk=request.data["asset"]))
        for _field in StaticAssetTemplateField.objects.filter(Q(pk__in=request.data["fields"])):
            _field.create_field_value(_asset)
        return Response({"msg": "added"})


class device_asset_post(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request, *args, **kwargs):
        _lut = {_value["idx"]: _value for _value in json.loads(request.POST["asset_data"])}
        # import pprint
        # pprint.pprint(_lut)
        _field_list = StaticAssetFieldValue.objects.filter(
            Q(pk__in=_lut.keys())
        ).select_related(
            "static_asset_template_field"
        )
        _all_ok = all(
            [
                _field.check_new_value(_lut[_field.pk], request.xml_response) for _field in _field_list
            ]
        )
        if _all_ok:
            [
                _field.set_new_value(_lut[_field.pk], request.user) for _field in _field_list
            ]
        else:
            request.xml_response.error("validation problem")
