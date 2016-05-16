# -*- coding: utf-8 -*-
# Copyright (C) 2012-2016 init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of host-monitoring
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

""" base views """

import datetime
import json
import logging

import PIL
from PIL import Image
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views.generic import View
from lxml.builder import E
from rest_framework.generics import ListAPIView
from rest_framework.response import Response

import initat.cluster.backbone.models
from initat.cluster.backbone.models import device_variable, category, \
    category_tree, location_gfx, DeleteRequest, device, config, mon_check_command, \
    device_mon_location
from initat.cluster.backbone.models.functions import can_delete_obj, get_related_models
from initat.cluster.backbone.render import permission_required_mixin
from initat.cluster.frontend.helper_functions import xml_wrapper, contact_server
from initat.cluster.frontend.rest_views import rest_logging
from initat.tools import logging_tools, process_tools, server_command

logger = logging.getLogger("cluster.base")

HIDDEN_FIELDS = set(["password", ])


class get_gauge_info(View):
    @method_decorator(xml_wrapper)
    def post(self, request):
        gauge_info = E.gauge_info()
        for gauge_dv in device_variable.objects.filter(Q(name="_SYS_GAUGE_") & Q(is_public=False)).order_by("description"):
            gauge_info.append(
                E.gauge_element(
                    gauge_dv.description,
                    value="{:d}".format(gauge_dv.val_int),
                    idx="{:d}".format(gauge_dv.pk),
                )
            )
        # for testing
        # gauge_info.append(E.gauge_element("test", value="40", idx="50"))
        request.xml_response["response"] = gauge_info


# class DeviceLocation(permission_required_mixin, View):
#    all_required_permissions = ["backbone.user.modify_category_tree"]
#    @method_decorator(login_required)
#    def get(self, request):
#        return render_me(
#            request,
#            "device_location.html",
#            {}
#        )()


class prune_category_tree(permission_required_mixin, View):
    all_required_permissions = ["backbone.user.modify_category_tree"]

    @method_decorator(xml_wrapper)
    def post(self, request):
        doit = True if int(request.POST.get("doit", "0")) else False
        to_delete = category_tree().prune(mode=request.POST['mode'], doit=doit)
        if doit:
            request.xml_response.info(
                "tree pruned ({})".format(
                    logging_tools.get_plural("element", len(to_delete))
                )
            )
            request.xml_response["deleted"] = E.categories(
                *[
                    E.category(pk="{:d}".format(_del.saved_pk)) for _del in to_delete
                ]
            )
        else:
            request.xml_response["nodes"] = len(to_delete)
            if to_delete:
                request.xml_response["info"] = "OK to delete {} ?".format(
                    logging_tools.get_plural("element", len(to_delete))
                )
            else:
                request.xml_response["info"] = "Nothing to prune"


TARGET_WIDTH, TARGET_HEIGTH = (1920, 1920)


class upload_location_gfx(View):
    @method_decorator(xml_wrapper)
    def post(self, request):
        _location = location_gfx.objects.get(Q(pk=request.POST["location_gfx_id"]))
        if _location.locked:
            request.xml_response.warn("location_gfx is locked")
        else:
            if len(request.FILES) == 1:
                _file = request.FILES[request.FILES.keys()[0]]
                if _file.content_type in ["image/png", "image/jpeg"]:
                    _img = Image.open(_file)
                    _w, _h = _img.size
                    _x_fact = float(TARGET_WIDTH) / float(_w)
                    _y_fact = float(TARGET_HEIGTH) / float(_h)
                    _fact = min(_x_fact, _y_fact)
                    _w = int(_w * _fact)
                    _h = int(_h * _fact)
                    _img = _img.resize((_w, _h), resample=PIL.Image.BICUBIC)
                    try:
                        _location.store_graphic(_img, _file.content_type, _file.name)
                    except:
                        request.xml_response.critical(
                            "error storing image: {}".format(
                                process_tools.get_except_info()
                            ),
                            logger=logger
                        )
                    else:
                        request.xml_response.info(
                            "uploaded {} (type {}, size {:d} x {:d})".format(
                                _file.name,
                                _file.content_type,
                                _w,
                                _h,
                            )
                        )
                else:
                    request.xml_response.error(
                        "wrong content_type '{}'".format(
                            _file.content_type
                        )
                    )
            else:
                request.xml_response.error("need exactly one file")


class location_gfx_icon(View):
    def get(self, request, **kwargs):
        try:
            _loc = location_gfx.objects.get(Q(pk=kwargs["id"]))
        except location_gfx.DoesNotExist:
            _content = location_gfx.default_icon()
        else:
            _content = _loc.get_icon()
        return HttpResponse(_content, content_type="image/jpeg")


class location_gfx_image(View):
    def get(self, request, **kwargs):
        try:
            _loc = location_gfx.objects.get(Q(pk=kwargs["id"]))
        except location_gfx.DoesNotExist:
            _content = location_gfx.default_image()
        else:
            _content = _loc.get_image()
        return HttpResponse(_content, content_type="image/jpeg")


class modify_location_gfx(View):
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        try:
            _loc = location_gfx.objects.get(Q(pk=_post["id"]))
        except location_gfx.DoesNotExist:
            request.xml_response.error("location_gfx does not exist")
        else:
            _changed = True
            if _post["mode"] == "rotate":
                _loc.rotate(int(_post["degrees"]))
            elif _post["mode"] == "resize":
                _loc.resize(float(_post["factor"]))
            elif _post["mode"] == "brightness":
                _loc.brightness(float(_post["factor"]))
            elif _post["mode"] == "sharpen":
                _loc.sharpen(float(_post["factor"]))
            elif _post["mode"] == "restore":
                _loc.restore_original_image()
            elif _post["mode"] == "undo":
                _loc.undo_last_step()
            elif _post["mode"].startswith("af_"):
                _loc.apply_filter(_post["mode"][3:].upper())
            else:
                _changed = False
                request.xml_response.error("unknown mode '{}'".format(_post["mode"]))
            if _changed:
                request.xml_response["image_url"] = _loc.get_image_url()
                request.xml_response["icon_url"] = _loc.get_icon_url()
                request.xml_response["width"] = "{:d}".format(_loc.width)
                request.xml_response["height"] = "{:d}".format(_loc.height)


class change_category(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        def remove_mon_loc(_dev, _loc):
            # get all dmls which are not from the current location and DMLs
            # which are not on structural entries
            dml_set = device_mon_location.objects.exclude(
                Q(location__physical=False)
            ).filter(
                Q(location=_loc) & Q(device=_dev)
            )
            if dml_set.count():
                mon_loc_removed.extend(list(dml_set))
                dml_set.delete()

        _post = request.POST
        # import pprint
        # pprint.pprint(_post)
        add_cat = True if int(_post.get("set", "0").lower()) else False
        # format: [(device_idx, cat_idx), ...]
        _added, _removed = ([], [])
        devs_added, devs_removed, dev_ss_removed, mon_loc_removed = ([], [], [], [])
        for sc_cat in category.objects.filter(Q(pk__in=json.loads(_post["cat_pks"]))):
            for _dev in device.objects.filter(
                Q(pk__in=json.loads(_post["dev_pks"]))
            ).prefetch_related(
                "categories"
            ):
                if add_cat and sc_cat not in _dev.categories.all():
                    devs_added.append(_dev)
                    _dev.categories.add(sc_cat)
                    _added.append((_dev.idx, sc_cat.idx))
                    if sc_cat.single_select:
                        _single_del_list = [
                            _del_cat for _del_cat in _dev.categories.all() if _del_cat != sc_cat and _del_cat.single_select
                        ]
                        if len(_single_del_list):
                            dev_ss_removed.append(_dev)
                            for _to_del in _single_del_list:
                                _dev.categories.remove(_to_del)
                                remove_mon_loc(_dev, _to_del)
                                _removed.append((_dev.idx, _to_del.idx))
                elif not add_cat and sc_cat in _dev.categories.all():
                    devs_removed.append(_dev)
                    _dev.categories.remove(sc_cat)
                    remove_mon_loc(_dev, sc_cat)
                    _removed.append((_dev.idx, sc_cat.idx))
        _info_f = []
        if devs_added:
            _info_f.append(
                "added to {}".format(
                    logging_tools.get_plural("device", len(devs_added))
                )
            )
        if devs_removed:
            _info_f.append(
                "removed from {}".format(
                    logging_tools.get_plural("device", len(devs_removed))
                )
            )
        if dev_ss_removed:
            request.xml_response.warn(
                "removed location from {} due to single-select policy".format(
                    logging_tools.get_plural("device", len(dev_ss_removed)),
                ),
                logger
            )
        if mon_loc_removed:
            request.xml_response.warn(
                u"removed {}".format(
                    logging_tools.get_plural("Location reference", len(mon_loc_removed))
                ),
                logger
            )

        request.xml_response.info(
            u"{}: {}".format(
                unicode(sc_cat),
                ", ".join(_info_f) or "nothing done",
            )
        )
        request.xml_response["changes"] = json.dumps(
            {
                "added": _added,
                "removed": _removed,
                "dml_removed": [
                    (entry.device_id, entry.location_id, entry.location_gfx_id, entry.idx) for entry in mon_loc_removed
                ]
            }
        )


class GetKpiSourceData(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    @rest_logging
    def post(self, request):
        srv_com = server_command.srv_command(command="get_kpi_source_data")
        srv_com['dev_mon_cat_tuples'] = request.POST['dev_mon_cat_tuples']
        srv_com['time_range'] = request.POST['time_range']
        srv_com['time_range_parameter'] = request.POST['time_range_parameter']
        result = contact_server(request, "md-config", srv_com, log_error=True, log_result=False)
        if result:
            print result.pretty_print()
            request.xml_response['response'] = result['kpi_set']


class CalculateKpiPreview(ListAPIView):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    @rest_logging
    def post(self, request):
        srv_com = server_command.srv_command(command="calculate_kpi_preview")
        srv_com["kpi_serialized"] = request.POST['kpi_serialized']
        srv_com['dev_mon_cat_tuples'] = request.POST['dev_mon_cat_tuples']
        result = contact_server(request, "md-config", srv_com, log_error=True, log_result=False, timeout=120)
        if result:
            request.xml_response['kpi_set'] = result.get('kpi_set', json.dumps(None))
            request.xml_response['kpi_error_report'] = result.get('kpi_error_report', json.dumps(None))


class CheckDeleteObject(View):
    """
    This is an advanced delete which handles further actions which might
    be necessary in order to delete an object

    Does not actually delete yet as this can take very long (>30 seconds) but returns
    data about which objects can be deleted for the client to delete and data about object references.
    """
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        # returns:
        # - related_objs: {obj_ok : [related_obj_info] } for objects which have related objects
        # - deletable_objects: [obj_pk]
        _post = request.POST
        obj_pks = json.loads(_post.get("obj_pks"))
        model = getattr(initat.cluster.backbone.models, _post.get("model"))

        objs_to_delete = model.objects.filter(pk__in=obj_pks)

        if len(objs_to_delete) < len(obj_pks):
            request.xml_response.error("Could not find all objects to delete.")
            logger.warn("To delete: {}; found only: {}".format(obj_pks, [o.pk for o in objs_to_delete]))

        related_objects_info = {}
        deletable_objects = []
        # import time
        for obj_to_delete in objs_to_delete:
            # a = time.time()

            can_delete_answer = can_delete_obj(obj_to_delete, logger)
            # print 'can del took ', time.time() - a, bool(can_delete_answer), len(can_delete_answer.related_objects)
            if can_delete_answer:
                deletable_objects.append(obj_to_delete.pk)
            else:
                info = []
                # there are django related objects, which describe the fields that are related
                # and there are referenced objects, which are the actual db objects having these fields
                for related_object in can_delete_answer.related_objects:
                    referenced_objects_list = []
                    refs_of_refs = set()
                    for referenced_object in related_object.ref_list:
                        referenced_objects_list.append(
                            {k: v for (k, v) in referenced_object.__dict__.iteritems() if k != '_state'}
                        )
                        refs_of_refs.update(get_related_models(referenced_object, detail=True))

                    info.append(
                        {
                            'model': related_object.model._meta.object_name,
                            'model_verbose_name': related_object.model._meta.verbose_name.capitalize(),
                            'field_name': related_object.field.name,
                            'field_verbose_name': related_object.field.verbose_name.capitalize(),
                            'null': related_object.field.null,
                            'objects': {
                                'num_refs_of_refs': len(refs_of_refs),
                                'list': referenced_objects_list,
                            },
                        }
                    )
                related_objects_info[obj_to_delete.pk] = info
                # print 'build 2nd level rel list', time.time() - a
            # print 'obj', obj_pk, ' took ', time.time() - a

        # json can't deal with datetime, django formatter doesn't have nice dates
        def formatter(x):
            if isinstance(x, datetime.datetime):
                return x.strftime("%Y-%m-%d %H:%M")
            elif isinstance(x, datetime.date):
                # NOTE: datetime is instance of date, so check datetime first
                return x.isoformat()
            else:
                return x
        request.xml_response['related_objects'] = json.dumps(related_objects_info, default=formatter)
        request.xml_response['deletable_objects'] = json.dumps(deletable_objects)


class AddDeleteRequest(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        obj_pks = json.loads(request.POST.get("obj_pks"))
        model_name = request.POST.get("model")
        model = getattr(initat.cluster.backbone.models, model_name)

        for obj_pk in obj_pks:
            obj = model.objects.get(pk=obj_pk)

            if hasattr(obj, "enabled"):
                obj.enabled = False
                obj.save()

            if DeleteRequest.objects.filter(obj_pk=obj_pk, model=model_name).exists():
                request.xml_response.error("This object is already in the deletion queue.")
            else:
                del_req = DeleteRequest(
                    obj_pk=obj_pk,
                    model=model_name,
                    delete_strategies=request.POST.get("delete_strategies", None)
                )
                with transaction.atomic():
                    # save right away, not after request finishes, since cluster server is notified now
                    del_req.save()

        srv_com = server_command.srv_command(command="handle_delete_requests")
        contact_server(request, "server", srv_com, log_result=False)


class CheckDeletionStatus(View):
    # Returns how many of certain objects are already deleted
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        del_requests = json.loads(request.POST.get("del_requests"))

        for k, del_request in del_requests.iteritems():

            model_name, obj_pks = del_request
            model = getattr(initat.cluster.backbone.models, model_name)

            num_remaining_objs = len(model.objects.filter(pk__in=obj_pks))

            request.xml_response['num_remaining_{}'.format(k)] = num_remaining_objs

            if num_remaining_objs == 0:
                msg = "Finished deleting {}".format(logging_tools.get_plural("object", len(obj_pks)))
            else:
                additional = " ({} remaining)".format(num_remaining_objs) if len(obj_pks) > 1 else ""
                msg = "Deleting {}{}".format(logging_tools.get_plural("object", len(obj_pks)), additional)

            request.xml_response['msg_{}'.format(k)] = msg


class CategoryReferences(ListAPIView):
    @method_decorator(login_required)
    @rest_logging
    def list(self, request, *args, **kwargs):
        all_m2ms = [
            _f for _f in category._meta.get_fields(include_hidden=True) if _f.many_to_many and _f.auto_created
        ]
        _names = [_f.name for _f in all_m2ms]
        _required = {"config", "mon_check_command", "deviceselection", "device"}
        if set(_names) != _required:
            raise ValidationError("Related fields for category_tree changed")
        # not optimal, improve format
        contents = []
        for rel in all_m2ms:
            for cat_id, remote_id in getattr(
                category,
                rel.get_accessor_name()
            ).through.objects.all().values_list(
                "category_id",
                "{}_id".format(rel.name)
            ):
                contents.append((rel.name, cat_id, remote_id))
        return Response(contents)
