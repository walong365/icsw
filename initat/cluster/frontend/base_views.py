#!/usr/bin/python-init -Ot
# -*- coding: utf-8 -*-

""" base views """
import traceback

from PIL import Image
import datetime
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.db import transaction
from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views.generic import View
from rest_framework.generics import ListAPIView
from initat.cluster.frontend.rest_views import rest_logging
from initat.tools import server_command
import initat.cluster.backbone.models
from initat.cluster.backbone.models import device_variable, category, \
    category_tree, location_gfx, DeleteRequest
from initat.cluster.backbone.models.functions import can_delete_obj, get_related_models
from initat.cluster.backbone.render import permission_required_mixin, render_me
from initat.cluster.frontend.helper_functions import xml_wrapper, contact_server
from lxml.builder import E  # @UnresolvedImport
import initat.cluster.backbone.models
import json
import PIL
import logging
from initat.tools import logging_tools
from initat.tools import process_tools
import pprint

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
                    value="%d" % (gauge_dv.val_int),
                    idx="%d" % (gauge_dv.pk),
                )
            )
        # gauge_info.append(E.gauge_element("test", value="40"))
        request.xml_response["response"] = gauge_info


class get_category_tree(permission_required_mixin, View):
    all_required_permissions = ["backbone.user.modify_category_tree"]

    @method_decorator(login_required)
    def get(self, request):
        return render_me(
            request,
            "category_tree.html",
            {}
        )()


class prune_category_tree(permission_required_mixin, View):
    all_required_permissions = ["backbone.user.modify_category_tree"]

    @method_decorator(xml_wrapper)
    def post(self, request):
        category_tree().prune()
        request.xml_response.info("tree pruned")


TARGET_WIDTH, TARGET_HEIGTH = (1920, 1920)


class upload_location_gfx(View):
    @method_decorator(xml_wrapper)
    def post(self, request):
        _location = location_gfx.objects.get(Q(pk=request.POST["location_id"]))
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
                        request.xml_response.critical("error storing image: {}".format(process_tools.get_except_info()), logger=logger)
                    else:
                        request.xml_response.info("uploaded {} (type {}, size {:d} x {:d})".format(
                            _file.name,
                            _file.content_type,
                            _w,
                            _h,
                        ))
                else:
                    request.xml_response.error("wrong content_type '{}'".format(_file.content_type))
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
        _post = request.POST
        multi_mode = True if _post.get("multi", "False").lower()[0] in ["1", "t", "y"] else False
        # format: [(device_idx, cat_idx), ...]
        _added, _removed = ([], [])
        if multi_mode:
            set_mode = True if int(_post["set"]) else False
            sc_cat = category.objects.get(Q(pk=_post["cat_pk"]))
            devs_added, devs_removed = ([], [])
            for _obj in getattr(
                initat.cluster.backbone.models, _post["obj_type"]
            ).objects.filter(
                Q(pk__in=json.loads(_post["obj_pks"]))
            ).prefetch_related("categories"):
                if set_mode and sc_cat not in _obj.categories.all():
                    devs_added.append(_obj)
                    _obj.categories.add(sc_cat)
                    _remcats = [_cat for _cat in _obj.categories.all() if _cat != sc_cat and _cat.single_select()]
                    _obj.categories.remove(*_remcats)
                    _added.append((_obj.idx, sc_cat.idx))
                    _removed.extend([(_obj.idx, _remcat.idx) for _remcat in _remcats])
                elif not set_mode and sc_cat in _obj.categories.all():
                    devs_removed.append(_obj)
                    _removed.append((_obj.idx, sc_cat.idx))
                    _obj.categories.remove(sc_cat)
            request.xml_response.info(
                u"{}: added to {}, removed from {}".format(
                    unicode(sc_cat),
                    logging_tools.get_plural("device", len(devs_added)),
                    logging_tools.get_plural("device", len(devs_removed)),
                )
            )
        else:
            cur_obj = getattr(initat.cluster.backbone.models, _post["obj_type"]).objects.get(Q(pk=_post["obj_pk"]))
            cur_sel = set(cur_obj.categories.filter(Q(full_name__startswith=_post["subtree"])).values_list("pk", flat=True))
            new_sel = set(json.loads(_post["cur_sel"]))
            # remove
            to_del = [_entry for _entry in cur_sel - new_sel]
            to_add = [_entry for _entry in new_sel - cur_sel]
            if to_del:
                cur_obj.categories.remove(*category.objects.filter(Q(pk__in=to_del)))
                _removed.extend([(cur_obj.idx, _to_del) for _to_del in to_del])
            if to_add:
                cur_obj.categories.add(*category.objects.filter(Q(pk__in=to_add)))
                _added.extend([(cur_obj.idx, _to_add) for _to_add in to_add])
            request.xml_response.info(
                "added {:d}, removed {:d}".format(
                    len(to_add),
                    len(to_del)
                )
            )
        request.xml_response["changes"] = json.dumps({"added": _added, "removed": _removed})


class KpiView(View):
    @method_decorator(login_required)
    def get(self, request):
        return render_me(
            request,
            "kpi.html",
            {}
        )()


class GetKpiSourceData(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    @rest_logging
    def post(self, request):
        srv_com = server_command.srv_command(command="get_kpi_source_data")
        srv_com['tuples'] = request.POST['tuples']
        srv_com['time_range'] = request.POST['time_range']
        srv_com['time_range_parameter'] = request.POST['time_range_parameter']
        result = contact_server(request, "md-config", srv_com, log_error=True, log_result=False)
        if result:
            request.xml_response['response'] = result['kpi_set']


class CalculateKpi(ListAPIView):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    @rest_logging
    def post(self, request):
        srv_com = server_command.srv_command(command="calculate_kpi")
        srv_com["kpi_pk"] = request.POST['kpi_pk']
        srv_com["formula"] = request.POST['formula']
        result = contact_server(request, "md-config", srv_com, log_error=True, log_result=False)
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

                    info.append({
                        'model': related_object.model._meta.object_name,
                        'model_verbose_name': related_object.model._meta.verbose_name.capitalize(),
                        'field_name': related_object.field.name,
                        'field_verbose_name': related_object.field.verbose_name.capitalize(),
                        'null': related_object.field.null,
                        'objects': {
                            'num_refs_of_refs': len(refs_of_refs),
                            'list': referenced_objects_list,
                        },
                    })
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
