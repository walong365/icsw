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

        return HttpResponse(json.dumps({'devices': list(set([ar.device.pk for ar in apv.assetrun_set.all()]))}), content_type="application/json")


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

        # base_header = [
        #     'Asset Type',
        #     'Batch Id',
        #     'Start Time',
        #     'End Time',
        #     'Total Run Time',
        #     'device',
        #     'status',
        #     'result'
        # ]
        #
        # if ar.run_start_time and ar.run_end_time:
        #     ar_run_time = str((ar.run_end_time - ar.run_start_time).total_seconds())
        # else:
        #     ar_run_time = "N/A"
        #
        # base_row = [AssetType(ar.run_type).name,
        #             str(ar.asset_batch.idx),
        #             str(ar.run_start_time),
        #             str(ar.run_end_time),
        #             ar_run_time,
        #             str(ar.device.full_name),
        #             RunStatus(ar.run_status).name,
        #             RunResult(ar.run_result).name]
        #
        # if ar.run_type == AssetType.PACKAGE:
        #     base_header.extend([
        #         'package_name',
        #         'package_version',
        #         'package_release',
        #         'package_size',
        #         'package_install_date',
        #         'package_type'])
        #
        #     writer.writerow(base_header)
        #
        #     for package_version in ar.packages.select_related("asset_package").all():
        #         row = base_row[:]
        #
        #         row.append(package_version.asset_package.name)
        #         row.append(package_version.version)
        #         row.append(package_version.release)
        #         row.append(package_version.size)
        #         row.append(package_version.created)
        #         row.append(PackageTypeEnum(package_version.asset_package.package_type).name)
        #
        #         writer.writerow(row)
        #
        # elif ar.run_type == AssetType.HARDWARE:
        #     base_header.extend([
        #         'hardware_node_type',
        #         'hardware_depth',
        #         'hardware_attributes', ])
        #
        #     writer.writerow(base_header)
        #
        #     for hardware_item in ar.assethardwareentry_set.all():
        #         row = base_row[:]
        #
        #         row.append(hardware_item.type)
        #         row.append(hardware_item.depth)
        #         row.append(hardware_item.attributes)
        #
        #         writer.writerow(row)
        #
        # elif ar.run_type == AssetType.LICENSE:
        #     base_header.extend([
        #         'license_name',
        #         'license_key'])
        #
        #     writer.writerow(base_header)
        #
        #     for license in ar.assetlicenseentry_set.all():
        #         row = base_row[:]
        #
        #         row.append(license.name)
        #         row.append(license.license_key)
        #
        #         writer.writerow(row)
        #
        # elif ar.run_type == AssetType.UPDATE:
        #     base_header.extend([
        #         'update_name',
        #         'update_version',
        #         'update_release',
        #         'update_kb_idx',
        #         'update_install_date',
        #         'update_status',
        #         'update_optional',
        #         'update_installed'
        #     ])
        #
        #     writer.writerow(base_header)
        #
        #     for update in ar.assetupdateentry_set.all():
        #         row = base_row[:]
        #
        #         row.append(update.name)
        #         row.append(update.version)
        #         row.append(update.release)
        #         row.append(update.kb_idx)
        #         row.append(update.install_date)
        #         row.append(update.status)
        #         row.append(update.optional)
        #         row.append(update.installed)
        #
        #         writer.writerow(row)
        #
        # elif ar.run_type == AssetType.PROCESS:
        #     base_header.extend([
        #         'process_name',
        #         'process_id',
        #     ])
        #
        #     writer.writerow(base_header)
        #
        #     for process in ar.assetprocessentry_set.all():
        #         row = base_row[:]
        #
        #         row.append(str(process.name))
        #         row.append(str(process.pid))
        #
        #         writer.writerow(row)
        #
        # elif ar.run_type == AssetType.PENDING_UPDATE:
        #     base_header.extend([
        #         'update_name',
        #         'update_version',
        #         'update_release',
        #         'update_kb_idx',
        #         'update_install_date'
        #         'update_status',
        #         'update_optional',
        #         'update_installed'
        #     ])
        #
        #     writer.writerow(base_header)
        #
        #     for update in ar.assetupdateentry_set.all():
        #         row = base_row[:]
        #
        #         row.append(update.name)
        #         row.append(update.version)
        #         row.append(update.release)
        #         row.append(update.kb_idx)
        #         row.append(update.install_date)
        #         row.append(update.status)
        #         row.append(update.optional)
        #         row.append(update.installed)
        #
        #         writer.writerow(row)
        #
        # elif ar.run_type == AssetType.PCI:
        #     base_header.extend([
        #         'pci_info'
        #     ])
        #
        #     writer.writerow(base_header)
        #
        #     for pci_entry in ar.assetpcientry_set.all():
        #         row = base_row[:]
        #
        #         row.append(str(pci_entry))
        #
        #         writer.writerow(row)
        #
        # elif ar.run_type == AssetType.DMI:
        #     base_header.extend([
        #         'handle',
        #         'dmi_type',
        #         'header',
        #         'key',
        #         'value'
        #     ])
        #
        #     writer.writerow(base_header)
        #
        #     for dmi_head in ar.assetdmihead_set.all():
        #         for dmi_handle in dmi_head.assetdmihandle_set.all():
        #             handle = dmi_handle.handle
        #             dmi_type = dmi_handle.dmi_type
        #             header = dmi_handle.header
        #
        #             for dmi_value in dmi_handle.assetdmivalue_set.all():
        #                 key = dmi_value.key
        #                 value = dmi_value.value
        #
        #                 row = base_row[:]
        #
        #                 row.append(handle)
        #                 row.append(dmi_type)
        #                 row.append(header)
        #                 row.append(key)
        #                 row.append(value)
        #
        #                 writer.writerow(row)
        #
        #
        # elif ar.run_type == AssetType.PRETTYWINHW:
        #     writer.writerow(base_header)
        #
        #     for cpu in ar.cpus.all():
        #         row = base_row[:]
        #
        #         row.append(str(cpu))
        #
        #         writer.writerow(row)
        #
        #     for memorymodule in ar.memory_modules.all():
        #         row = base_row[:]
        #
        #         row.append(str(memorymodule))
        #
        #         writer.writerow(row)
        #
        #     for gpu in ar.gpus.all():
        #         row = base_row[:]
        #
        #         row.append(str(gpu))
        #
        #         writer.writerow(row)
        #
        #     for hdd in ar.hdds.all():
        #         row = base_row[:]
        #
        #         row.append(str(hdd))
        #
        #         writer.writerow(row)
        #
        #     for partition in ar.partitions.all():
        #         row = base_row[:]
        #
        #         row.append(str(partition))
        #
        #         writer.writerow(row)
        #
        #     for display in ar.displays.all():
        #         row = base_row[:]
        #
        #         row.append(str(display))
        #
        #         writer.writerow(row)

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


# class export_assetbatch_to_xlsx(View):
#     @method_decorator(login_required)
#     def post(self, request):
#         ab = AssetBatch.objects.get(idx=int(request.POST["pk"]))
#
#         assetruns = ab.assetrun_set.all()
#
#         workbook = Workbook()
#         workbook.remove_sheet(workbook.active)
#
#         for ar in assetruns:
#             base_header = ['Asset Type',
#                            'Batch Id',
#                            'Start Time',
#                            'End Time',
#                            'Total Run Time',
#                            'device',
#                            'status',
#                            'result']
#
#             if ar.run_start_time and ar.run_end_time:
#                 ar_run_time = str((ar.run_end_time - ar.run_start_time).total_seconds())
#             else:
#                 ar_run_time = "N/A"
#
#             base_row = [AssetType(ar.run_type).name,
#                         str(ar.asset_batch.idx),
#                         str(ar.run_start_time),
#                         str(ar.run_end_time),
#                         ar_run_time,
#                         str(ar.device.full_name),
#                         RunStatus(ar.run_status).name,
#                         RunResult(ar.run_result).name]
#
#             sheet = workbook.create_sheet()
#             sheet.title = AssetType(ar.run_type).name
#
#             if ar.run_type == AssetType.PACKAGE:
#                 base_header.extend([
#                     'package_name',
#                     'package_version',
#                     'package_release',
#                     'package_size',
#                     'package_install_date',
#                     'package_type'])
#
#                 sheet.append(base_header)
#
#                 for package_version in ar.packages.select_related("asset_package").all():
#                     row = base_row[:]
#
#                     row.append(package_version.asset_package.name)
#                     row.append(package_version.version)
#                     row.append(package_version.release)
#                     row.append(package_version.size)
#                     row.append(package_version.created)
#                     row.append(PackageTypeEnum(package_version.asset_package.package_type).name)
#
#                     sheet.append(row)
#
#             elif ar.run_type == AssetType.HARDWARE:
#                 base_header.extend([
#                     'hardware_node_type',
#                     'hardware_depth',
#                     'hardware_attributes',])
#
#                 sheet.append(base_header)
#
#                 for hardware_item in ar.assethardwareentry_set.all():
#                     row = base_row[:]
#
#                     row.append(hardware_item.type)
#                     row.append(hardware_item.depth)
#                     row.append(hardware_item.attributes)
#
#                     sheet.append(row)
#
#
#             elif ar.run_type == AssetType.LICENSE:
#                 base_header.extend([
#                     'license_name',
#                     'license_key'])
#
#                 sheet.append(base_header)
#
#                 for license in ar.assetlicenseentry_set.all():
#                     row = base_row[:]
#
#                     row.append(license.name)
#                     row.append(license.license_key)
#
#                     sheet.append(row)
#
#             elif ar.run_type == AssetType.UPDATE:
#                 base_header.extend([
#                     'update_name',
#                     'update_version',
#                     'update_release',
#                     'update_kb_idx',
#                     'update_install_date',
#                     'update_status',
#                     'update_optional',
#                     'update_installed'
#                 ])
#
#                 sheet.append(base_header)
#
#                 for update in ar.assetupdateentry_set.all():
#                     row = base_row[:]
#
#                     row.append(update.name)
#                     row.append(update.version)
#                     row.append(update.release)
#                     row.append(update.kb_idx)
#                     row.append(update.install_date)
#                     row.append(update.status)
#                     row.append(update.optional)
#                     row.append(update.installed)
#
#                     sheet.append(row)
#
#             elif ar.run_type == AssetType.PROCESS:
#                 base_header.extend([
#                     'process_name',
#                     'process_id'
#                 ])
#
#                 sheet.append(base_header)
#
#                 for process in ar.assetprocessentry_set.all():
#                     row = base_row[:]
#
#                     row.append(str(process.name))
#                     row.append(str(process.pid))
#
#                     sheet.append(row)
#
#             elif ar.run_type == AssetType.PENDING_UPDATE:
#                 base_header.extend([
#                     'update_name',
#                     'update_version',
#                     'update_release',
#                     'update_kb_idx',
#                     'update_install_date',
#                     'update_status',
#                     'update_optional',
#                     'update_installed'
#                 ])
#
#                 sheet.append(base_header)
#
#                 for update in ar.assetupdateentry_set.all():
#                     row = base_row[:]
#
#                     row.append(update.name)
#                     row.append(update.version)
#                     row.append(update.release)
#                     row.append(update.kb_idx)
#                     row.append(update.install_date)
#                     row.append(update.status)
#                     row.append(update.optional)
#                     row.append(update.installed)
#
#                     sheet.append(row)
#
#             elif ar.run_type == AssetType.PCI:
#                 base_header.extend([
#                     'pci_info'
#                 ])
#
#                 sheet.append(base_header)
#
#                 for pci_entry in ar.assetpcientry_set.all():
#                     row = base_row[:]
#
#                     row.append(str(pci_entry))
#
#                     sheet.append(row)
#
#             elif ar.run_type == AssetType.DMI:
#                 base_header.extend([
#                     'handle',
#                     'dmi_type',
#                     'header',
#                     'key',
#                     'value'
#                 ])
#
#                 sheet.append(base_header)
#
#                 for dmi_head in ar.assetdmihead_set.all():
#                     for dmi_handle in dmi_head.assetdmihandle_set.all():
#                         handle = dmi_handle.handle
#                         dmi_type = dmi_handle.dmi_type
#                         header = dmi_handle.header
#
#                         for dmi_value in dmi_handle.assetdmivalue_set.all():
#                             key = dmi_value.key
#                             value = dmi_value.value
#
#                             row = base_row[:]
#
#                             row.append(handle)
#                             row.append(dmi_type)
#                             row.append(header)
#                             row.append(key)
#                             row.append(value)
#
#                             sheet.append(row)
#
#
#             elif ar.run_type == AssetType.PRETTYWINHW:
#                 sheet.append(base_header)
#
#                 for cpu in ar.cpus.all():
#                     row = base_row[:]
#
#                     row.append(str(cpu))
#
#                     sheet.append(row)
#
#                 for memorymodule in ar.memory_modules.all():
#                     row = base_row[:]
#
#                     row.append(str(memorymodule))
#
#                     sheet.append(row)
#
#                 for gpu in ar.gpus.all():
#                     row = base_row[:]
#
#                     row.append(str(gpu))
#
#                     sheet.append(row)
#
#                 for hdd in ar.hdds.all():
#                     row = base_row[:]
#
#                     row.append(str(hdd))
#
#                     sheet.append(row)
#
#                 for partition in ar.partitions.all():
#                     row = base_row[:]
#
#                     row.append(str(partition))
#
#                     sheet.append(row)
#
#                 for display in ar.displays.all():
#                     row = base_row[:]
#
#                     row.append(str(display))
#
#                     sheet.append(row)
#
#         s = save_virtual_workbook(workbook)
#
#         new_s = base64.b64encode(s)
#
#         return HttpResponse(
#             json.dumps(
#                 {
#                     'xlsx': new_s
#                 }
#             )
#         )



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


def _generate_csv_entry_for_assetrun(ar, row_writer_func):
    base_header = ['Asset Type',
                   'Batch Id',
                   'Start Time',
                   'End Time',
                   'Total Run Time',
                   'device',
                   'status',
                   'result']


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

    #sheet = workbook.create_sheet()
    #sheet.title = AssetType(ar.run_type).name

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
        base_header.extend([
            'license_name',
            'license_key'])

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
