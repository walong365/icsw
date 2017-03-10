# Copyright (C) 2016-2017 Gregor Kaufmann, Andreas Lang-Nevyjel
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
""" asset views """

from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import View
from rest_framework import viewsets

from initat.cluster.frontend.helper_functions import xml_wrapper


########################################################################################################################
# Static Asset Views
########################################################################################################################

class SimpleAssetBatchLoader(View):
    @method_decorator(login_required)
    def post(self, request):
        import json
        from django.http import HttpResponse
        from initat.cluster.backbone.models import AssetBatch
        from initat.cluster.backbone.serializers import SimpleAssetBatchSerializer

        device_pks = [int(obj) for obj in request.POST.getlist("device_pks[]")]
        excluded_assetbatch_pks = [int(obj) for obj in request.POST.getlist("excluded_assetbatch_pks[]")]

        queryset = AssetBatch.objects.filter(device__in=device_pks).exclude(idx__in=excluded_assetbatch_pks)

        serializer = SimpleAssetBatchSerializer(queryset, many=True)

        return HttpResponse(json.dumps(serializer.data))


class AssetBatchDeleter(View):
    @method_decorator(login_required)
    def post(self, request):
        import json
        from django.http import HttpResponse
        from initat.cluster.backbone.models import AssetBatch

        assetbatch_pks = [int(obj) for obj in request.POST.getlist("assetbatch_pks[]")]

        queryset = AssetBatch.objects.filter(idx__in=assetbatch_pks)

        deletion_info = queryset.delete()

        return HttpResponse(json.dumps(deletion_info))


class AssetBatchViewSet(viewsets.ViewSet):
    @method_decorator(login_required)
    def list(self, request):
        import json
        from initat.cluster.backbone.models import AssetBatch

        if "simple" in request.query_params:
            prefetch_list = [
                "device"
            ]
        else:
            prefetch_list = [
                "installed_packages",
                "installed_packages__package_version",
                "installed_packages__package_version__asset_package",
                "installed_updates",
                "pending_updates",
                "memory_modules",
                "cpus",
                "gpus",
                "network_devices",
                "device",
                "device__act_partition_table"
            ]

        if "assetbatch_pks" in request.query_params:
            queryset = AssetBatch.objects.prefetch_related(*prefetch_list).filter(
                idx__in=json.loads(request.query_params.getlist("assetbatch_pks")[0]))
        else:
            if "device_pks" in request.query_params:
                queryset = AssetBatch.objects.prefetch_related(*prefetch_list).filter(
                    device__in=json.loads(request.query_params.getlist("device_pks")[0]))
            else:
                queryset = AssetBatch.objects.prefetch_related(*prefetch_list).all()

        if "simple" in request.query_params:
            from initat.cluster.backbone.serializers import SimpleAssetBatchSerializer
            if "truncate_result" in request.query_params:
                from collections import defaultdict
                asset_batches_per_device = defaultdict(list)

                for ab in queryset.order_by("-created"):
                    if len(asset_batches_per_device[ab.device]) < 10:
                        asset_batches_per_device[ab.device].append(ab)

                new_queryset = []
                for _device in asset_batches_per_device.keys():
                    new_queryset.extend(asset_batches_per_device[_device])

                serializer = SimpleAssetBatchSerializer(new_queryset, many=True)
            else:
                serializer = SimpleAssetBatchSerializer(queryset.order_by("-created"), many=True)
        else:
            from initat.cluster.backbone.serializers import AssetBatchSerializer
            serializer = AssetBatchSerializer(queryset, many=True)

        from rest_framework.response import Response
        return Response(serializer.data)


class ScheduledRunViewSet(viewsets.ViewSet):
    @method_decorator(login_required)
    def list(self, request):
        import json
        from initat.cluster.backbone.models.dispatch import ScheduleItem
        from initat.cluster.backbone.serializers import ScheduleItemSerializer

        if "pks" in request.query_params:
            queryset = ScheduleItem.objects.filter(
                model_name="device",
                object_id__in=json.loads(request.query_params.getlist("pks")[0])
            )
        else:
            queryset = ScheduleItem.objects.all()
        serializer = ScheduleItemSerializer(queryset, many=True)

        for entry in serializer.data:
            entry['device'] = entry['object_id']

        from rest_framework.response import Response
        return Response(serializer.data)


class AssetPackageLoader(View):
        @method_decorator(login_required)
        def post(self, request):
            import json
            from django.http import HttpResponse
            from initat.cluster.backbone.models import AssetPackage

            if request.POST['type'] == "AssetPackage":
                from initat.cluster.backbone.serializers import ReverseSimpleAssetPackageSerializer
                queryset = AssetPackage.objects.prefetch_related("assetpackageversion_set").all()
                serializer = ReverseSimpleAssetPackageSerializer(queryset, many=True)
                return HttpResponse(json.dumps(serializer.data))
            elif request.POST['type'] == "AssetPackageVersion":
                from initat.cluster.backbone.serializers import AssetPackageVersionSerializer
                asset_package_id = int(request.POST["asset_package_id"])
                ap = AssetPackage.objects.prefetch_related("assetpackageversion_set").get(idx=asset_package_id)
                serializer = AssetPackageVersionSerializer(ap.assetpackageversion_set.all(), many=True)
                return HttpResponse(json.dumps(serializer.data))


########################################################################################################################
# Dynamic Asset Views
########################################################################################################################


class StaticAssetTemplateViewSet(viewsets.ViewSet):
    @method_decorator(login_required)
    def get_all(self, request):
        _ = request
        from initat.cluster.backbone.models import StaticAssetTemplate
        from initat.cluster.backbone.serializers import StaticAssetTemplateSerializer
        queryset = StaticAssetTemplate.objects.all().prefetch_related(
            "staticassettemplatefield_set"
        )
        [_template.check_ordering() for _template in queryset]
        serializer = StaticAssetTemplateSerializer(queryset, many=True)
        from rest_framework.response import Response
        return Response(serializer.data)

    @method_decorator(login_required)
    def get_refs(self, request):
        _ = request
        from initat.cluster.backbone.models import StaticAsset
        from initat.cluster.backbone.serializers import StaticAssetTemplateRefsSerializer

        queryset = StaticAsset.objects.all().prefetch_related(
            "device__domain_tree_node"
        )
        _data = []
        for _entry in queryset:
            _template_idx = _entry.static_asset_template_id
            _full_name = _entry.device.full_name
            _data.append({"static_asset_template": _template_idx, "device_name": _full_name})

        from rest_framework.response import Response
        return Response(StaticAssetTemplateRefsSerializer(_data, many=True).data)

    @method_decorator(login_required)
    def reorder_fields(self, request):
        from initat.cluster.backbone.models import StaticAssetTemplateField

        field_1 = StaticAssetTemplateField.objects.get(pk=request.data["field1"])
        field_2 = StaticAssetTemplateField.objects.get(pk=request.data["field2"])
        _swap = field_1.ordering
        field_1.ordering = field_2.ordering
        field_2.ordering = _swap
        field_1.save(update_fields=["ordering"])
        field_2.save(update_fields=["ordering"])

        from rest_framework.response import Response
        return Response({"msg": "done"})

    @method_decorator(login_required)
    def create_template(self, request):
        from initat.cluster.backbone.serializers import StaticAssetTemplateSerializer
        new_obj = StaticAssetTemplateSerializer(data=request.data)
        if new_obj.is_valid():
            new_obj.save()
        else:
            from django.core.exceptions import ValidationError
            raise ValidationError("New Template is not valid: {}".format(new_obj.errors))

        from rest_framework.response import Response
        return Response(new_obj.data)

    @method_decorator(login_required)
    def delete_template(self, request, *args, **kwargs):
        _, _ = request, args
        from initat.cluster.backbone.models import StaticAssetTemplate
        from initat.cluster.backbone.models.functions import can_delete_obj

        cur_obj = StaticAssetTemplate.objects.get(pk=kwargs["pk"])
        can_delete_answer = can_delete_obj(cur_obj)
        if can_delete_answer:
            from rest_framework import status
            from rest_framework.response import Response
            cur_obj.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        else:
            raise ValueError(can_delete_answer.msg)

    @method_decorator(login_required)
    def create_field(self, request):
        from initat.cluster.backbone.serializers import StaticAssetTemplateFieldSerializer
        new_obj = StaticAssetTemplateFieldSerializer(data=request.data)
        if new_obj.is_valid():
            new_obj.save()
        else:
            from django.core.exceptions import ValidationError
            raise ValidationError("New TemplateField is not valid: {}".format(new_obj.errors))

        from rest_framework.response import Response
        return Response(new_obj.data)

    @method_decorator(login_required())
    def delete_field(self, request, **kwargs):
        _ = request
        from initat.cluster.backbone.models import StaticAssetTemplateField
        from initat.cluster.backbone.models.functions import can_delete_obj

        cur_obj = StaticAssetTemplateField.objects.get(pk=kwargs["pk"])
        can_delete_answer = can_delete_obj(cur_obj)
        if can_delete_answer:
            from rest_framework import status
            from rest_framework.response import Response
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
        from initat.cluster.backbone.models import StaticAssetTemplateField
        from initat.cluster.backbone.models.functions import get_change_reset_list
        from initat.cluster.backbone.serializers import StaticAssetTemplateFieldSerializer

        _prev_field = StaticAssetTemplateField.objects.get(pk=kwargs["pk"])
        # print _prev_var
        _cur_ser = StaticAssetTemplateFieldSerializer(
            StaticAssetTemplateField.objects.get(pk=kwargs["pk"]),
            data=request.data
        )
        # print "*" * 20
        # print _cur_ser.device_variable_type
        if _cur_ser.is_valid():
            _new_field = _cur_ser.save()
        else:
            # todo, fixme
            from django.core.exceptions import ValidationError
            raise ValidationError("Validation error: {}".format(str(_cur_ser.errors)))
        resp = _cur_ser.data
        c_list, r_list = get_change_reset_list(_prev_field, _new_field, request.data)

        from rest_framework.response import Response
        resp = Response(resp)
        # print c_list, r_list
        resp.data["_change_list"] = c_list
        resp.data["_reset_list"] = r_list
        return resp


class CopyStaticTemplate(View):
    @method_decorator(login_required)
    def post(self, request):
        import json
        from django.http import HttpResponse
        from initat.cluster.backbone.models import StaticAssetTemplate, user
        from initat.cluster.backbone.serializers import StaticAssetTemplateSerializer

        src_obj = StaticAssetTemplate.objects.get(pk=request.POST["src_idx"])
        create_user = user.objects.get(pk=request.POST["user_idx"])
        new_obj = json.loads(request.POST["new_obj"])
        new_template = src_obj.copy(new_obj, create_user)
        serializer = StaticAssetTemplateSerializer(new_template)
        return HttpResponse(
            json.dumps(serializer.data),
            content_type="application/json"
        )


class DeviceStaticAssetViewSet(viewsets.ViewSet):
    @method_decorator(login_required)
    def create_asset(self, request):
        from initat.cluster.backbone.serializers import StaticAssetSerializer
        _count = request.data.get("count", 1)
        asset = None
        for _iter in range(_count):
            new_asset = StaticAssetSerializer(data=request.data)
            if new_asset.is_valid():
                asset = new_asset.save()
                asset.add_fields()
            else:
                from django.core.exceptions import ValidationError
                raise ValidationError(
                    "cannot create new StaticAsset"
                )
        # return only latest asset
        from rest_framework.response import Response
        return Response(StaticAssetSerializer(asset).data)

    @method_decorator(login_required)
    def delete_asset(self, request, **kwargs):
        _ = request
        from rest_framework import status
        from initat.cluster.backbone.models import StaticAsset
        StaticAsset.objects.get(idx=kwargs["pk"]).delete()

        from rest_framework.response import Response
        return Response(status=status.HTTP_204_NO_CONTENT)

    @method_decorator(login_required())
    def delete_field(self, request, **kwargs):
        _ = request
        from initat.cluster.backbone.models import StaticAssetFieldValue
        from initat.cluster.backbone.models.functions import can_delete_obj

        cur_obj = StaticAssetFieldValue.objects.get(pk=kwargs["pk"])
        can_delete_answer = can_delete_obj(cur_obj)
        if can_delete_answer:
            from rest_framework import status
            from rest_framework.response import Response
            cur_obj.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        else:
            raise ValueError(can_delete_answer.msg)

    @method_decorator(login_required)
    def add_unused(self, request, **kwargs):
        _ = kwargs
        from initat.cluster.backbone.models import StaticAssetTemplateField, StaticAsset

        _asset = StaticAsset.objects.get(pk=request.data["asset"])
        for _field in StaticAssetTemplateField.objects.filter(pk__in=request.data["fields"]):
            _field.create_field_value(_asset)

        from rest_framework.response import Response
        return Response({"msg": "added"})


class DeviceAssetPost(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request, *args, **kwargs):
        _, _ = args, kwargs
        import json
        from initat.cluster.backbone.models import StaticAssetFieldValue

        _lut = {_value["idx"]: _value for _value in json.loads(request.POST["asset_data"])}
        # import pprint
        # pprint.pprint(_lut)
        _field_list = StaticAssetFieldValue.objects.filter(
            pk__in=list(_lut.keys())
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


class GetFieldvaluesForTemplate(View):
    @method_decorator(login_required)
    def post(self, request):
        import json
        from django.http import HttpResponse
        from initat.cluster.backbone.models import StaticAssetTemplate, StaticAssetTemplateFieldType

        idx_list = [int(value) for value in request.POST.getlist("idx_list[]")]

        static_asset_templates = StaticAssetTemplate.objects.filter(
            idx__in=idx_list
        ).prefetch_related(
            "staticassettemplatefield_set__staticassetfieldvalue_set__static_asset__device",
            # "staticassettemplatefield_set__device"
        )

        data = {}

        def set_aggregate_value(aggregate_obj, _field_object, fixed):
            if fixed:
                aggregate_obj['aggregate'] = _field_object['value']
                return

            field_type = _field_object['field_type']
            if field_type == StaticAssetTemplateFieldType.INTEGER:
                if not aggregate_obj['aggregate']:
                    aggregate_obj['aggregate'] = 0
                aggregate_obj['aggregate'] += _field_object['value_int']
            else:
                aggregate_obj['aggregate'] = "N/A"

        def set_value(_field_object):
            value = None
            if _field_object['field_type'] == StaticAssetTemplateFieldType.STRING:
                value = _field_object['value_str']
            elif _field_object['field_type'] == StaticAssetTemplateFieldType.INTEGER:
                value = _field_object['value_int']
            elif _field_object['field_type'] == StaticAssetTemplateFieldType.DATE:
                value = _field_object['value_date']
            elif _field_object['field_type'] == StaticAssetTemplateFieldType.TEXT:
                value = _field_object['value_text']

            _field_object['value'] = value

        for static_asset_template in static_asset_templates:
            data[static_asset_template.idx] = {}

            for template_field in static_asset_template.staticassettemplatefield_set.all():
                data[static_asset_template.idx][template_field.ordering] = {}

                data[static_asset_template.idx][template_field.ordering]['name'] = template_field.name
                data[static_asset_template.idx][template_field.ordering]['list'] = []
                data[static_asset_template.idx][template_field.ordering]['aggregate'] = None
                data[static_asset_template.idx][template_field.ordering]['fixed'] = template_field.fixed
                data[static_asset_template.idx][template_field.ordering]['status'] = 0

                for template_field_value in template_field.staticassetfieldvalue_set.all():
                    date_obj = template_field_value.value_date.isoformat() if template_field_value.value_date else None
                    field_object = {
                        'device_idx': template_field_value.static_asset.device.idx,
                        'field_name': template_field.name,
                        'value_str': template_field_value.value_str,
                        'value_int': template_field_value.value_int,
                        'value_date': date_obj,
                        'value_text': template_field_value.value_text,
                        'field_type': template_field.field_type,
                        'status': 0
                    }
                    set_value(field_object)
                    set_aggregate_value(
                        data[static_asset_template.idx][template_field.ordering],
                        field_object,
                        template_field.fixed
                    )
                    data[static_asset_template.idx][template_field.ordering]['list'].append(field_object)

                    if template_field.field_type == StaticAssetTemplateFieldType.DATE and template_field.date_check:
                        import datetime
                        warn_delta = datetime.timedelta(days=template_field.date_warn_value)
                        critical_delta = datetime.timedelta(days=template_field.date_critical_value)

                        if (datetime.date.today() + warn_delta) > template_field_value.value_date:
                            data[static_asset_template.idx][template_field.ordering]['status'] = 1
                            field_object['status'] = 1
                        if (datetime.date.today() + critical_delta) > template_field_value.value_date:
                            data[static_asset_template.idx][template_field.ordering]['status'] = 2
                            field_object['status'] = 2

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


class HiddenStaticAssetTemplateTypesManager(View):
    @method_decorator(login_required)
    def post(self, request):
        import json
        from django.http import HttpResponse
        from initat.cluster.backbone.models import HiddenStaticAssetTemplateTypes

        if request.POST['action'] == "read":
            from initat.cluster.backbone.serializers import HiddenStaticAssetTemplateTypesSerializer
            queryset = HiddenStaticAssetTemplateTypes.objects.all()
            serializer = HiddenStaticAssetTemplateTypesSerializer(queryset, many=True)
            return HttpResponse(json.dumps(serializer.data))
        elif request.POST['action'] == "write":
            new_obj = HiddenStaticAssetTemplateTypes(type=request.POST["type"])
            new_obj.save()
        elif request.POST['action'] == "delete":
            obj = HiddenStaticAssetTemplateTypes.objects.get(type=request.POST["type"])
            obj.delete()

        return HttpResponse(json.dumps(0))
