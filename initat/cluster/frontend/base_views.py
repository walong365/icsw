#!/usr/bin/python-init -Ot
# -*- coding: utf-8 -*-

""" base views """

from PIL import Image
import datetime
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.db import transaction
from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views.generic import View
import initat.cluster.backbone.models
from initat.cluster.backbone.models import device_variable, category, \
    category_tree, location_gfx
from initat.cluster.backbone.models.functions import can_delete_obj, get_related_models
from initat.cluster.backbone.render import permission_required_mixin, render_me
from initat.cluster.frontend.forms import category_form, location_gfx_form
from initat.cluster.frontend.helper_functions import xml_wrapper
from lxml.builder import E  # @UnresolvedImport
import initat.cluster.backbone.models
import json
import PIL
import logging
import logging_tools
import process_tools
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


class delete_object(View):
    """
    This is an advanced delete which handles further actions which might
    be necessary in order to delete an object
    """
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        # returns {obj_ok : [related_obj_info] } for objects which have related objects
        _post = request.POST
        obj_pks = json.loads(_post.get("obj_pks"))
        model = getattr(initat.cluster.backbone.models, _post.get("model"))

        response = {}
        successfully_deleted = []
        import time
        for obj_pk in obj_pks:
            # a = time.time()

            try:
                obj = model.objects.get(pk=obj_pk)
            except model.DoesNotExist:
                # problem solved itself..
                request.xml_response.error("Object {} does not exist any more.".format(obj_pk))
            else:

                can_delete_answer = can_delete_obj(obj, logger)
                # print 'can del took ', time.time() - a, bool(can_delete_answer), len(can_delete_answer.related_objects)
                if can_delete_answer:
                    obj.delete()
                    # print 'actual del', time.time() - a
                    successfully_deleted.append(obj)
                else:
                    answer_list = []
                    for rel_obj in can_delete_answer.related_objects:
                        objects_list = []
                        refs_of_refs = set()
                        for obj in rel_obj.ref_list:
                            objects_list.append(
                                {k: v for (k, v) in obj.__dict__.iteritems() if k != '_state'}
                            )
                            refs_of_refs.update(get_related_models(obj, detail=True))

                        answer_list.append({
                            'model': rel_obj.model._meta.object_name,
                            'field_name': rel_obj.field.name,
                            'null': rel_obj.field.null,
                            'objects': {
                                'num_refs_of_refs': len(refs_of_refs),
                                'list': objects_list,
                            },
                        })
                    response[obj_pk] = answer_list
                    # print 'build 2nd level rel list', time.time() - a
                # print 'obj', obj_pk, ' took ', time.time() - a

        # json can't deal with datetime
        def formatter(x):
            if isinstance(x, datetime.datetime):
                return x.strftime("%Y-%m-%d %H:%M")
            elif isinstance(x, datetime.date):
                # NOTE: datetime is instance of date, so check datetime first
                return x.isoformat()
            else:
                return x
        request.xml_response['related_objects'] = json.dumps(response, default=formatter)

        if successfully_deleted:
            request.xml_response.info("Successfully deleted {} object{}".format(
                len(successfully_deleted), "s" if len(successfully_deleted) > 1 else ""))


class force_delete_object(View):
    """
    Delete objects with references with delete strategies for each reference
    """
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        obj_pk = json.loads(_post.get("obj_pk"))
        model = getattr(initat.cluster.backbone.models, _post.get("model"))
        delete_strategy_list = json.loads(_post.get("delete_strategies", "{}"))
        delete_strategies = {}
        for entry in delete_strategy_list:
            delete_strategies[(entry['model'], entry['field_name'])] = entry['selected_action']

        obj_to_delete = model.objects.get(pk=obj_pk)

        logger.info("deleting obj with pk {} from {}".format(obj_pk, model))
        logger.info("deleting strategies: {}".format(delete_strategies))

        can_delete_answer = can_delete_obj(obj_to_delete, logger)
        for rel_obj in can_delete_answer.related_objects:
            dict_key = (rel_obj.model._meta.object_name, rel_obj.field.name)
            strat = delete_strategies.get(dict_key, None)
            if strat == "set null":
                logger.info("set null on {} ".format(rel_obj))
                for db_obj in rel_obj.ref_list:
                    setattr(db_obj, rel_obj.field.name, None)
                    db_obj.save()
            elif strat == "delete cascade":
                for db_obj in rel_obj.ref_list:
                    logger.info("delete cascade for {} ({})".format(db_obj, rel_obj))
                    db_obj.delete()
            elif strat == "delete object":
                logger.info("delete object on {}".format(rel_obj))
                for db_obj in rel_obj.ref_list:
                    db_obj.delete()
            else:
                raise ValueError("Invalid strategy for {}: {}; available strategies: {}".format(
                    dict_key, strat, delete_strategies
                ))

        logger.info("finished with refs")
        can_delete_answer_after = can_delete_obj(obj_to_delete, logger)
        if can_delete_answer_after:
            # all references cleared
            obj_to_delete.delete()
        else:
            request.xml_response.error(can_delete_answer_after.msg)

