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
import tempfile

import pytz
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Q, Count, Case, When, IntegerField, Sum
from django.http import HttpResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.generic import View
from rest_framework import viewsets
from rest_framework.response import Response
from io import BytesIO

from initat.cluster.backbone.models import device, AssetPackage, AssetRun, \
    AssetPackageVersion, AssetType, StaticAssetTemplate, user, RunStatus, RunResult, PackageTypeEnum, AssetBatch
from initat.cluster.backbone.models.dispatch import ScheduleItem
from initat.cluster.backbone.serializers import AssetRunDetailSerializer, ScheduleItemSerializer, \
    AssetPackageSerializer, AssetRunOverviewSerializer, StaticAssetTemplateSerializer


try:
    from openpyxl import Workbook
    from openpyxl.writer.excel import save_virtual_workbook
except ImportError:
    Workbook = None


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
                    'devices': list(set([ar.device.pk for ar in apv.assetrun_set.all()]))
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
        elif ar.run_type == AssetType.SOFTWARE_VERSION:
            return HttpResponse(
                json.dumps(
                    {
                        'assets': [str(basv) for basv in ar.generate_assets_no_save()]
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
                Q(device__in=json.loads(request.query_params.getlist("pks")[0]))
            )
        else:
            queryset = AssetRun.objects.all()
        queryset = queryset.filter(Q(created__gt=timezone.now() - datetime.timedelta(days=2)))
        queryset = queryset.order_by(
            # should be created, FIXME later
            "-idx",
            "-run_start_time",
        ).annotate(
            num_packages=Count("packages"),
            num_hardware=Count("assethardwareentry"),
            num_processes=Count("assetprocessentry"),
            num_licenses=Count("assetlicenseentry"),
            num_updates=Sum(Case(When(assetupdateentry__installed=True, then=1), output_field=IntegerField(), default=0)),
            num_pending_updates=Sum(Case(When(assetupdateentry__installed=False, then=1), output_field=IntegerField(), default=0)),
            num_pci_entries=Count("assetpcientry"),
            num_asset_handles=Count("assetdmihead__assetdmihandle"),
            num_hw_entries=Sum("cpu_count") + Sum("memory_count")
        )
        serializer = AssetRunOverviewSerializer(queryset, many=True)
        return Response(serializer.data)

    def get_details(self, request):
        queryset = AssetRun.objects.prefetch_related(
            "packages",
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
    def get_all(self, request):
        queryset = StaticAssetTemplate.objects.all().prefetch_related(
            "staticassettemplatefield_set"
        )
        serializer = StaticAssetTemplateSerializer(queryset, many=True)
        return Response(serializer.data)

    @method_decorator(login_required)
    def create_template(self, request):
        new_obj = StaticAssetTemplateSerializer(data=request.data)
        if new_obj.is_valid():
            new_obj.save()
        else:
            raise ValidationError("New Template is not valid")
        return Response(new_obj.data)


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

        schedule_items = ScheduleItem.objects.select_related("device", "dispatch_setting").all()

        base_header = ['Device Name',
                       'Planned Time',
                       'Dispatch Setting Name']

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

class PDFReportGenerator(object):
    class Bookmark(object):
        def __init__(self, name, pagenum, parent = None):
            self.name = name
            self.pagenum = pagenum
            self.parent = parent


    class Report(object):
        def __init__(self):
            self.number_of_pages = 0

    def __init__(self):
        from PyPDF2 import PdfFileWriter, PdfFileReader

        self.bookmarks = []
        self.root_bookmark_cache = {}

        self.number_of_pages = 0
        self.final_output_pdf = PdfFileWriter()

    def __append_to_output_pdf(self, input):
        from PyPDF2 import PdfFileWriter, PdfFileReader

        input_pdf = PdfFileReader(input)

        [self.final_output_pdf.addPage(input_pdf.getPage(page_num)) for page_num in range(input_pdf.numPages)]

    def generate_bookmark(self, name, parent = None):
        bookmark = PDFReportGenerator.Bookmark(name, self.number_of_pages, parent = parent)
        self.bookmarks.append(bookmark)
        return bookmark

    def generate_report_for_asset_batch(self, asset_batch):
        from reportlab.pdfgen.canvas import Canvas
        from PollyReports import *

        if not asset_batch.device in self.root_bookmark_cache:
            self.root_bookmark_cache[asset_batch.device] = self.generate_bookmark(asset_batch.device.name)

        buffer = BytesIO()
        canvas = Canvas(buffer, (72 * 11, 72 * 8.5))

        assetruns = asset_batch.assetrun_set.all()
        row_collector = RowCollector()

        # Hardware report is generated last
        hardware_report_ar = None

        for ar in assetruns:
            row_collector.reset()
            row_collector.current_asset_type = AssetType(ar.run_type)
            _generate_csv_entry_for_assetrun(ar, row_collector.collect)

            _pagefooter = Band([Element((0, 0), ("Helvetica-Bold", 10), sysvar="pagenumber",
                                               format=lambda x: "Page %d" % x),
                                       Element((500, 0), ("Helvetica-Bold", 10),
                                               text="Timestamp: {}".format(row_collector.row_info[2].split(".")[0]))])

            if AssetType(ar.run_type) == AssetType.UPDATE:
                data = row_collector.rows_dict[1:]
                data = sorted(data, key=lambda k: k['update_status'])
                if not data:
                    continue

                self.generate_bookmark("Installed Updates", self.root_bookmark_cache[asset_batch.device])

                rpt = Report(data)

                rpt.detailband = Band([Element((0, 0), ("Helvetica", 6), key='update_name'),
                                       Element((400, 0), ("Helvetica", 6), key='install_date'),
                                       Element((600, 0), ("Helvetica", 6), key='update_status'),
                                       Rule((0, 0), 7.5 * 90, thickness=0.1)])

                rpt.pageheader = Band([Image(pos=(570, -25), width=103, height=42, text="/home/kaufmann/logo.png"),
                                       Element((0, 0), ("Times-Bold", 20), text="Installed Updates for {}".format(row_collector.row_info[5])),
                                       Element((0, 24), ("Helvetica", 12), text="Update Name"),
                                       Element((400, 24), ("Helvetica", 12), text="Install Date"),
                                       Element((600, 24), ("Helvetica", 12), text="Install Status"),
                                       Rule((0, 42), 7.5 * 90, thickness=2), ])


                rpt.groupheaders = [Band([Element((0, 4), ("Helvetica-Bold", 10),
                                          getvalue=lambda x: x['update_status'],
                                          format=lambda x: "Updates with status: {}".format(x)), ],
                                          getvalue=lambda x: x["update_status"]), ]

                rpt.pagefooter = _pagefooter


                rpt.generate(canvas)
                self.number_of_pages += rpt.pagenumber

            elif AssetType(ar.run_type) == AssetType.LICENSE:
                data = row_collector.rows[1:]
                if not data:
                    continue

                self.generate_bookmark("Available Licenses", self.root_bookmark_cache[asset_batch.device])

                rpt = Report(data)

                rpt.detailband = Band([Element((0, 0), ("Helvetica", 6), key=0),
                                       Element((500, 0), ("Helvetica", 6), key=1),
                                       Rule((0, 0), 7.5 * 90, thickness=0.1)])

                rpt.pageheader = Band(
                    [Image(pos=(570, -25), width=103, height=42, text="/home/kaufmann/logo.png"),
                     Element((0, 0), ("Times-Bold", 20), text="Available Licenses for {}".format(row_collector.row_info[5])),
                     Element((0, 24), ("Helvetica", 12), text="License Name"),
                     Element((500, 24), ("Helvetica", 12), text="License Key"),
                     Rule((0, 42), 7.5 * 90, thickness=2), ])

                rpt.pagefooter = _pagefooter

                rpt.generate(canvas)
                self.number_of_pages += rpt.pagenumber

            elif AssetType(ar.run_type) == AssetType.PACKAGE:
                from initat.cluster.backbone.models import asset

                packages = asset.get_packages_for_ar(ar)

                #data = row_collector.rows_dict[1:]
                #data = sorted(data, key=lambda k: k['package_name'])
                if not packages:
                    continue

                self.generate_bookmark("Installed Packages", self.root_bookmark_cache[asset_batch.device])

                data = [package.get_as_row() for package in packages]
                data = sorted(data, key=lambda k: k['package_name'])

                rpt = Report(data)

                rpt.detailband = Band([Element((0, 0), ("Helvetica", 6), key='package_name'),
                                       Element((400, 0), ("Helvetica", 6), key='package_version'),
                                       Element((500, 0), ("Helvetica", 6), key='package_release'),
                                       Element((550, 0), ("Helvetica", 6), key='package_size'),
                                       Element((600, 0), ("Helvetica", 6), key='package_install_date'),
                                       Rule((0, 0), 7.5 * 90, thickness=0.1)])

                rpt.pageheader = Band(
                    [Image(pos=(570, -25), width=103, height=42, text="/home/kaufmann/logo.png"),
                    Element((0, 0), ("Times-Bold", 20), text="Installed Packages for {}".format(row_collector.row_info[5])),
                    Element((0, 24), ("Helvetica", 12), text="Name"),
                    Element((400, 24), ("Helvetica", 12), text="Version"),
                    Element((500, 24), ("Helvetica", 12), text="Release"),
                    Element((550, 24), ("Helvetica", 12), text="Size"),
                    Element((600, 24), ("Helvetica", 12), text="Install Date"),
                    Rule((0, 42), 7.5 * 90, thickness=2), ])

                rpt.groupheaders = [Band([Element((0, 4), ("Helvetica-Bold", 10),
                                                  getvalue=lambda x: x['package_name'][0],
                                                  format=lambda x: "Packages starting with: {}".format(x)), ],
                                         getvalue=lambda x: x["package_name"][0]), ]

                rpt.pagefooter = _pagefooter

                rpt.generate(canvas)
                self.number_of_pages += rpt.pagenumber

            elif AssetType(ar.run_type) == AssetType.PENDING_UPDATE:
                data = row_collector.rows_dict[1:]
                data = sorted(data, key=lambda k: k['update_name'])
                if not data:
                    continue

                self.generate_bookmark("Available Updates", self.root_bookmark_cache[asset_batch.device])

                rpt = Report(data)

                rpt.detailband = Band([Element((0, 0), ("Helvetica", 6), key='update_name'),
                                       Rule((0, 0), 7.5 * 90, thickness=0.1),
                                       Element((400, 0), ("Helvetica", 6), key='update_version'),
                                       Rule((0, 0), 7.5 * 90, thickness=0.1),
                                       Element((600, 0), ("Helvetica", 6), key='update_optional'),
                                       Rule((0, 0), 7.5 * 90, thickness=0.1)])

                rpt.pageheader = Band(
                    [Image(pos=(570, -25), width=103, height=42, text="/home/kaufmann/logo.png"),
                    Element((0, 0), ("Times-Bold", 20), text="Available Updates for {}".format(row_collector.row_info[5])),
                    Element((0, 24), ("Helvetica", 12), text="Update Name"),
                    Element((400, 24), ("Helvetica", 12), text="Version"),
                    Element((600, 24), ("Helvetica", 12), text="Optional"),
                    Rule((0, 42), 7.5 * 90, thickness=2), ])

                rpt.groupheaders = [Band([Element((0, 4), ("Helvetica-Bold", 10),
                                                  getvalue=lambda x: x['update_name'][0].upper(),
                                                  format=lambda x: "Updates starting with: {}".format(x)), ],
                                         getvalue=lambda x: x["update_name"][0].upper()), ]

                rpt.pagefooter = _pagefooter

                rpt.generate(canvas)
                self.number_of_pages += rpt.pagenumber

            elif ar.run_type == AssetType.PRETTYWINHW:
                hardware_report_ar = ar
                continue


        canvas.save()
        self.__append_to_output_pdf(buffer)
        #append_pdf(PdfFileReader(buffer), self.final_output_pdf)


        # generate hardware report, append to output pdf
        if hardware_report_ar:
            self.__append_to_output_pdf(self.generate_hardware_report(hardware_report_ar))

    def __increase_page_count(self, canvas, doc):
        self.number_of_pages += 1

    def generate_hardware_report(self, hardware_report_ar):
        from reportlab.lib import colors
        from reportlab.lib.units import inch, mm
        from reportlab.lib.pagesizes import A4, landscape, letter
        from reportlab.platypus import SimpleDocTemplate, Spacer, Table, TableStyle, Paragraph
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.graphics.shapes import Drawing, Rect

        self.generate_bookmark("Hardware Report", self.root_bookmark_cache[hardware_report_ar.asset_batch.device])

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=landscape(letter), rightMargin=25, leftMargin=25, topMargin=25,
                                bottomMargin=25)
        doc.pagesize = landscape(letter)
        elements = []

        styleSheet = getSampleStyleSheet()

        data = [["Name", "Cores"]]
        for cpu in hardware_report_ar.cpus.all():
            data.append([Paragraph(str(cpu.cpuname), styleSheet["BodyText"]),
                         Paragraph(str(cpu.numberofcores), styleSheet["BodyText"])])

        P0_1 = Paragraph('<b>CPUs:</b>', styleSheet["BodyText"])

        t_1 = Table(data,
                    colWidths=(100 * mm, 100 * mm),
                    style=[('GRID', (0, 0), (-1, -1), 1, colors.black),
                           ('BOX', (0, 0), (-1, -1), 2, colors.black)])


        data = [["Name", "Driver Version"]]
        for gpu in hardware_report_ar.gpus.all():
            data.append([Paragraph(str(gpu.gpuname), styleSheet["BodyText"]),
                         Paragraph(str(gpu.driverversion), styleSheet["BodyText"])])

        P0_2 = Paragraph('<b>GPUs:</b>', styleSheet["BodyText"])
        t_2 = Table(data,
                    colWidths=(100 * mm, 100 * mm),
                    style=[('GRID', (0, 0), (-1, -1), 1, colors.black),
                           ('BOX', (0, 0), (-1, -1), 2, colors.black),
                           ])


        data = [["Name", "Serialnumber", "Size"]]
        for hdd in hardware_report_ar.hdds.all():
            data.append([Paragraph(str(hdd.name), styleSheet["BodyText"]),
                         Paragraph(str(hdd.serialnumber), styleSheet["BodyText"]),
                         Paragraph(sizeof_fmt(hdd.size), styleSheet["BodyText"])])

        P0_3 = Paragraph('<b>HDDs:</b>', styleSheet["BodyText"])
        t_3 = Table(data,
                    colWidths=(66 * mm, 67 * mm, 67 * mm),
                    style=[('GRID', (0, 0), (-1, -1), 1, colors.black),
                           ('BOX', (0, 0), (-1, -1), 2, colors.black),
                           ])

        data = [["Name", "Size", "Free", "Graph"]]
        for partition in hardware_report_ar.partitions.all():
            d = Drawing(10, 10)
            r = Rect(0, 0, 130, 12)
            r.fillColor = colors.red
            d.add(r)

            if partition.size != None and partition.free != None:
                free_length = int((float(partition.free) / float(partition.size)) * 130)
                free_start = 130 - free_length

                r = Rect(free_start, 0, free_length, 12)
                r.fillColor = colors.green
                d.add(r)
            else:
                d = Paragraph("N/A", styleSheet["BodyText"])

            data.append([Paragraph(str(partition.name), styleSheet["BodyText"]),
                         Paragraph(sizeof_fmt(partition.size), styleSheet["BodyText"]),
                         Paragraph(sizeof_fmt(partition.free), styleSheet["BodyText"]),
                         d])

        P0_4 = Paragraph('<b>Partitions:</b>', styleSheet["BodyText"])
        t_4 = Table(data,
                    colWidths=(50 * mm, 50 * mm, 50 * mm, 50 * mm),
                    style=[('GRID', (0, 0), (-1, -1), 1, colors.black),
                           ('BOX', (0, 0), (-1, -1), 2, colors.black),
                           ])

        data = [["Banklabel", "Formfactor", "Memorytype", "Manufacturer", "Capacity"]]
        for memory_module in hardware_report_ar.memory_modules.all():


            data.append([Paragraph(str(memory_module.banklabel), styleSheet["BodyText"]),
                         Paragraph(str(memory_module.get_name_of_form_factor()), styleSheet["BodyText"]),
                         Paragraph(str(memory_module.get_name_of_memory_type()), styleSheet["BodyText"]),
                         Paragraph(str(memory_module.manufacturer), styleSheet["BodyText"]),
                         Paragraph(sizeof_fmt(memory_module.capacity), styleSheet["BodyText"])])

        P0_5 = Paragraph('<b>Memory Modules:</b>', styleSheet["BodyText"])
        t_5 = Table(data,
                    colWidths=(40 * mm, 40 * mm, 40 * mm, 40 * mm, 40 * mm),
                    style=[('GRID', (0, 0), (-1, -1), 1, colors.black),
                           ('BOX', (0, 0), (-1, -1), 2, colors.black),
                           ])

        PH = Paragraph('<font face="times-bold" size="22">Hardware Report for {}</font>'.format(
            hardware_report_ar.device.name), styleSheet["BodyText"])

        data = [[P0_1, t_1],
                [P0_2, t_2],
                [P0_3, t_3],
                [P0_4, t_4],
                [P0_5, t_5]]



        t = Table(data, colWidths=(100, None), style=
        [('VALIGN', (0, 0), (0, -1), 'MIDDLE')])

        elements.append(PH)
        elements.append(Spacer(1, 30))
        elements.append(t)

        doc.build(elements, onFirstPage=self.__increase_page_count, onLaterPages=self.__increase_page_count)

        return buffer

    def get_pdf_as_buffer(self):
        buffer = BytesIO()

        for bookmark in sorted(self.bookmarks, key=lambda k: k.pagenum):
            if not bookmark.parent:
                bookmark.pdf_parent = self.final_output_pdf.addBookmark(bookmark.name, bookmark.pagenum)

        #parent = final_output_pdf.addBookmark("Device: {}".format(asset_batch.device.name), 0)
        for bookmark in sorted(self.bookmarks, key=lambda k: k.pagenum):
            if bookmark.parent:
                self.final_output_pdf.addBookmark(bookmark.name, bookmark.pagenum,
                                                  parent=bookmark.parent.pdf_parent)

        self.final_output_pdf.write(buffer)

        return buffer

class export_assetbatch_to_pdf(View):
    @method_decorator(login_required)
    def post(self, request):
        #ab = AssetBatch.objects.get(idx=int(request.POST["pk"]))



        asset_batches = AssetBatch.objects.all()
        pdf_report_generator = PDFReportGenerator()

        asset_batch_per_device = {}

        for asset_batch in asset_batches:
            if asset_batch.device in asset_batch_per_device:
                if asset_batch_per_device[asset_batch.device].idx < asset_batch.idx:
                    asset_batch_per_device[asset_batch.device] = asset_batch
            else:
                asset_batch_per_device[asset_batch.device] = asset_batch


        for device in asset_batch_per_device:
            pdf_report_generator.generate_report_for_asset_batch(asset_batch_per_device[device])

        buffer = pdf_report_generator.get_pdf_as_buffer()

        pdf_b64 = base64.b64encode(buffer.getvalue())

        return HttpResponse(
            json.dumps(
                {
                    'pdf': pdf_b64
                }
            )
        )

class RowCollector(object):
    def __init__(self):
        self.rows = []
        self.rows_dict = []
        self.row_info = []
        self.current_asset_type = None

    def reset(self):
        self.rows = []
        self.rows_dict = []
        self.row_info = []
        self.current_asset_type = None

    def collect(self, _row):
        self.row_info = _row[0:8]

        if self.current_asset_type == AssetType.UPDATE:
            update_name = str(_row[8])
            install_date = str(_row[12])
            update_status = str(_row[13])

            o = {}
            o['update_name'] = update_name
            o['install_date'] = install_date
            o['update_status'] = update_status

            self.rows_dict.append(o)
            self.rows.append([update_name, install_date, update_status])

        elif self.current_asset_type == AssetType.LICENSE:
            license_name = str(_row[8])
            license_key = str(_row[9])

            o = {}
            o['license_name'] = license_name
            o['license_key'] = license_key

            self.rows_dict.append(o)
            self.rows.append((license_name, license_key))

        elif self.current_asset_type == AssetType.PENDING_UPDATE:
            update_name = str(_row[8])
            update_version = str(_row[9])
            update_release = str(_row[10])
            update_kb_idx = str(_row[11])
            update_install_date = str(_row[12])
            update_status = str(_row[13])
            update_optional = str(_row[14])
            update_installed = str(_row[15])
            update_new_version = str(_row[16])

            o = {}
            o['update_name'] = update_name
            o['update_version'] = update_new_version if update_new_version else "N/A"
            o['update_optional'] = update_optional

            self.rows_dict.append(o)
            self.rows.append((update_name, update_version, update_release, update_kb_idx, update_install_date,
                              update_status, update_optional, update_installed))

        elif self.current_asset_type == AssetType.PROCESS:
            process_name = str(_row[8])
            process_id = str(_row[9])
            self.rows.append((process_name, process_id))

        elif self.current_asset_type == AssetType.HARDWARE:
            hardware_node_type = str(_row[8])
            hardware_depth = str(_row[9])
            hardware_attributes = str(_row[10])
            self.rows.append((hardware_node_type, hardware_depth, hardware_attributes))

        elif self.current_asset_type == AssetType.PACKAGE:
            package_name = _row[8]
            package_version = _row[9]
            package_release = _row[10]
            package_size = _row[11]
            package_install_date = _row[12]
            package_type = _row[13]

            if package_size and type(package_size) == type(1):
                if package_type == PackageTypeEnum.WINDOWS.name:
                    package_size_str = sizeof_fmt(package_size * (1024))
                else:
                    package_size_str = sizeof_fmt(package_size)

            else:
                package_size_str = "N/A"

            o = {}
            o['package_name'] = package_name
            o['package_version'] = package_version if package_version else "N/A"
            o['package_release'] = package_release if package_release else "N/A"
            o['package_size'] = package_size_str
            o['package_install_date'] = str(package_install_date)
            o['package_type'] = package_type

            self.rows_dict.append(o)
            self.rows.append((package_name, package_version, package_release, package_size,
                              package_install_date, package_type))

        elif self.current_asset_type == AssetType.PRETTYWINHW:
            _entry = str(_row[8])
            self.rows.append([_entry])

        elif self.current_asset_type == AssetType.DMI:
            handle = str(_row[8])
            dmi_type = str(_row[9])
            header = str(_row[10])
            key = str(_row[11])
            value = str(_row[12])
            self.rows.append((handle, dmi_type, header, key, value))

        else:
            self.rows.append([str(item) for item in _row])

def sizeof_fmt(num, suffix='B'):
    if num == None:
        return "N/A"
    for unit in ['','Ki','Mi','Gi','Ti','Pi','Ei','Zi']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)

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
            'update_installed',
            'update_new_version'
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
            row.append(update.new_version)

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
