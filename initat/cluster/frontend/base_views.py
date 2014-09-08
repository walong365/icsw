#!/usr/bin/python-init -Ot
# -*- coding: utf-8 -*-

""" base views """

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views.generic import View
from initat.cluster.backbone.models import device_variable, category, \
    category_tree
from initat.cluster.backbone.render import permission_required_mixin, render_me
from initat.cluster.frontend.forms import category_form, location_gfx_form
from initat.cluster.frontend.helper_functions import xml_wrapper
from lxml.builder import E  # @UnresolvedImport
import initat.cluster.backbone.models
import json
import logging
import logging_tools
from PIL import Image

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
            {
                "category_form": category_form(),
                "location_gfx_form": location_gfx_form(),
            }
        )()


class prune_category_tree(permission_required_mixin, View):
    all_required_permissions = ["backbone.user.modify_category_tree"]

    @method_decorator(xml_wrapper)
    def post(self, request):
        category_tree().prune()
        request.xml_response.info("tree pruned")


MIN_WIDTH, MAX_WIDTH, MIN_HEIGHT, MAX_HEIGHT = (
    400, 1920, 200, 1600,
)


class upload_location_gfx(View):
    @method_decorator(xml_wrapper)
    def post(self, request):
        if len(request.FILES) == 1:
            _file = request.FILES[request.FILES.keys()[0]]
            if _file.content_type in ["image/png", "image/jpeg"]:
                _img = Image.open(_file)
                _w, _h = _img.size
                if _w < MIN_WIDTH or _w > MAX_WIDTH or _h < MIN_HEIGHT or _h > MAX_HEIGHT:
                    request.xml_response.error("wrong size ({:d}, {:d}) not in [({:d}, {:d}), ({:d}, {:d})]".format(
                        _w, _h,
                        MIN_WIDTH, MIN_HEIGHT,
                        MAX_WIDTH, MAX_HEIGHT,
                    ))
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


class change_category(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        multi_mode = True if _post.get("multi", "False").lower()[0] in ["1", "t", "y"] else False
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
                    _obj.categories.remove(*[_cat for _cat in _obj.categories.all() if _cat != sc_cat and _cat.single_select()])
                elif not set_mode and sc_cat in _obj.categories.all():
                    devs_removed.append(_obj)
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
            if to_add:
                cur_obj.categories.add(*category.objects.filter(Q(pk__in=to_add)))
            request.xml_response.info(
                "added {:d}, removed {:d}".format(
                    len(to_add),
                    len(to_del)
                )
            )
