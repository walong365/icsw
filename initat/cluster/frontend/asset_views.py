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

import csv
import datetime
import json
import logging
import tempfile
import base64

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

from initat.report_server.report import PDFReportGenerator, generate_csv_entry_for_assetrun
from initat.cluster.backbone.models import device, AssetPackage, AssetRun, \
    AssetPackageVersion, AssetType, StaticAssetTemplate, user, RunStatus, RunResult, PackageTypeEnum, \
    AssetBatch, StaticAssetTemplateField, StaticAsset, StaticAssetFieldValue, StaticAssetTemplateFieldType
from initat.cluster.backbone.models.dispatch import ScheduleItem
from initat.cluster.backbone.serializers import AssetRunDetailSerializer, ScheduleItemSerializer, \
    AssetPackageSerializer, AssetRunOverviewSerializer, StaticAssetTemplateSerializer, \
    StaticAssetTemplateFieldSerializer, StaticAssetSerializer, StaticAssetTemplateRefsSerializer, AssetBatchSerializer

try:
    from openpyxl import Workbook
    from openpyxl.writer.excel import save_virtual_workbook
except ImportError:
    Workbook = None


logger = logging.getLogger(__name__)

class AssetBatchViewSet(viewsets.ViewSet):
    def list(self, request):
        if "pks" in request.query_params:
            queryset = AssetBatch.objects.prefetch_related("packages_install_times", "installed_updates",
                "pending_updates", "memory_modules", "cpus", "gpus").filter(
                Q(device__in=json.loads(request.query_params.getlist("pks")[0]))
            )
        else:
            queryset = AssetBatch.objects.all()
        serializer = AssetBatchSerializer(queryset, many=True)
        return Response(serializer.data)


class run_assetrun_for_device_now(View):
    @method_decorator(login_required)
    def post(self, request):
        _dev = device.objects.get(pk=int(request.POST['pk']))
        ScheduleItem.objects.create(
            device=_dev,
            source=10,
            planned_date=timezone.now(),
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

        generate_csv_entry_for_assetrun(ar, writer.writerow)

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

            generate_csv_entry_for_assetrun(ar, sheet.append)

        s = save_virtual_workbook(workbook)

        new_s = base64.b64encode(s)

        return HttpResponse(
            json.dumps(
                {
                    'xlsx': new_s
                }
            )
        )

class export_assetbatch_to_pdf(View):
    @method_decorator(login_required)
    def post(self, request):
        ab = AssetBatch.objects.get(idx=int(request.POST["pk"]))

        settings_dict = {
            "packages_selected": True,
            "licenses_selected": True,
            "installed_updates_selected": True,
            "avail_updates_selected": True,
            "hardware_report_selected": True
        }

        pdf_report_generator = PDFReportGenerator()
        pdf_report_generator.generate_device_report(ab.device, settings_dict)
        pdf_report_generator.finalize_pdf()
        pdf_b64 = base64.b64encode(pdf_report_generator.buffer.getvalue())

        return HttpResponse(
            json.dumps(
                {
                    'pdf': pdf_b64
                }
            )
        )


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


class get_fieldvalues_for_template(View):
    @method_decorator(login_required)
    def post(self, request):
        idx_list = [int(value) for value in request.POST.getlist("idx_list[]")]

        static_asset_templates = StaticAssetTemplate.objects.filter(idx__in=idx_list)

        data = {}

        def set_aggregate_value(aggregate_obj, field_object):
            if field_object['value_int']:
                if not aggregate_obj['aggregate']:
                    aggregate_obj['aggregate'] = 0
                aggregate_obj['aggregate'] += field_object['value_int']
            else:
                str_value = ''
                if field_object['value_str']:
                    str_value = field_object['value_str']
                elif field_object['value_date']:
                    str_value = field_object['value_date']
                elif field_object['value_text']:
                    str_value = field_object['value_text']

                if not aggregate_obj['aggregate']:
                    aggregate_obj['aggregate'] = str_value
                else:
                    aggregate_obj['aggregate'] += ", {}".format(str_value)

        def set_value(field_object):
            value = None
            if field_object['field_type'] == StaticAssetTemplateFieldType.STRING:
                value = field_object['value_str']
            elif field_object['field_type'] == StaticAssetTemplateFieldType.INTEGER:
                value = field_object['value_int']
            elif field_object['field_type'] == StaticAssetTemplateFieldType.DATE:
                value = field_object['value_date']
            elif field_object['field_type'] == StaticAssetTemplateFieldType.TEXT:
                value = field_object['value_text']

            field_object['value'] = value


        for static_asset_template in static_asset_templates:
            data[static_asset_template.idx] = {}

            for template_field in static_asset_template.staticassettemplatefield_set.all():
                data[static_asset_template.idx][template_field.ordering] = {}

                data[static_asset_template.idx][template_field.ordering]['name'] = template_field.name
                data[static_asset_template.idx][template_field.ordering]['list'] = []
                data[static_asset_template.idx][template_field.ordering]['aggregate'] = None
                data[static_asset_template.idx][template_field.ordering]['fixed'] = template_field.fixed
                data[static_asset_template.idx][template_field.ordering]['status'] = 0

                if template_field.fixed:
                    field_object = {
                        'device_idx': 0,
                        'field_name': template_field.name,
                        'value_str': template_field.default_value_str,
                        'value_int': template_field.default_value_int,
                        'value_date': template_field.default_value_date.isoformat() if template_field.default_value_date else None,
                        'value_text': template_field.default_value_text,
                        'field_type': template_field.field_type,
                        'status': 0
                    }

                    if template_field.field_type == StaticAssetTemplateFieldType.DATE and (template_field.default_value_date < datetime.date.today()):
                        data[static_asset_template.idx][template_field.ordering]['status'] = 2
                        field_object['status'] = 2

                    set_value(field_object)
                    set_aggregate_value(data[static_asset_template.idx][template_field.ordering], field_object)
                    data[static_asset_template.idx][template_field.ordering]['list'].append(field_object)

                else:
                    for template_field_value in template_field.staticassetfieldvalue_set.all():
                        field_object = {
                            'device_idx': template_field_value.static_asset.device.idx,
                            'field_name': template_field.name,
                            'value_str': template_field_value.value_str,
                            'value_int': template_field_value.value_int,
                            'value_date': template_field_value.value_date.isoformat() if template_field_value.value_date else None,
                            'value_text': template_field_value.value_text,
                            'field_type': template_field.field_type,
                            'status': 0
                        }
                        set_value(field_object)
                        set_aggregate_value(data[static_asset_template.idx][template_field.ordering], field_object)
                        data[static_asset_template.idx][template_field.ordering]['list'].append(field_object)

                        if template_field.field_type == StaticAssetTemplateFieldType.DATE and (template_field_value.value_date < datetime.date.today()):
                            data[static_asset_template.idx][template_field.ordering]['status'] = 2
                            field_object["status"] = 2

                        if template_field.consumable:
                            items_left = template_field.consumable_start_value - field_object["value_int"]
                            if items_left <= template_field.consumable_warn_value:
                                field_object["status"] = 1
                            if items_left <= template_field.consumable_critical_value:
                                field_object["status"] = 2

                if not data[static_asset_template.idx][template_field.ordering]['aggregate']:
                    data[static_asset_template.idx][template_field.ordering]['aggregate'] = "N/A"

                if template_field.consumable:
                    aggregate_value = data[static_asset_template.idx][template_field.ordering]['aggregate']
                    if not aggregate_value == "N/A":
                        items_left = template_field.consumable_start_value - aggregate_value

                        if items_left <= template_field.consumable_warn_value:
                            data[static_asset_template.idx][template_field.ordering]['status'] = 1
                        if items_left <= template_field.consumable_critical_value:
                            data[static_asset_template.idx][template_field.ordering]['status'] = 2

        return HttpResponse(
            json.dumps(
                {
                    'data': data
                }
            )
        )