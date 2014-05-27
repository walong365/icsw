#!/usr/bin/python-init -Ot
# -*- coding: utf-8 -*-

""" base views """

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.utils.decorators import method_decorator
from django.views.generic import View
from initat.cluster.backbone.models import device_variable, category, \
     category_tree
from initat.cluster.backbone.render import permission_required_mixin, render_me
from initat.cluster.frontend.forms import category_form
from initat.cluster.frontend.helper_functions import xml_wrapper
from lxml.builder import E # @UnresolvedImport
import initat.cluster.backbone.models
import json
import logging
import logging_tools

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
        return render_me(request, "category_tree.html",
            {
                "category_form" : category_form(),
            }
            )()

class prune_category_tree(permission_required_mixin, View):
    all_required_permissions = ["backbone.user.modify_category_tree"]
    @method_decorator(xml_wrapper)
    def post(self, request):
        category_tree().prune()
        request.xml_response.info("tree pruned")

# class get_cat_references(View):
#     @method_decorator(login_required)
#     @method_decorator(xml_wrapper)
#     def post(self, request):
#         cur_cat = category.objects.prefetch_related("device_set", "config_set", "mon_check_command_set", "device_set__domain_tree_node").get(Q(pk=request.POST["key"]))
#         res_list = E.references()
#         for entry in ["device", "config", "mon_check_command"]:
#             _getter = getattr(cur_cat, "%s_set" % (entry))
#             if _getter.count():
#                 sub_list = getattr(E, entry)(count="%d" % (_getter.count()))
#                 for sub_entry in _getter.all():
#                     info_str = sub_entry.full_name if entry == "device" else unicode(sub_entry)
#                     sub_list.append(E.entry(info_str, pk="%d" % (sub_entry.pk)))
#                 res_list.append(sub_list)
#         request.xml_response["result"] = res_list

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
            for _obj in getattr(initat.cluster.backbone.models, _post["obj_type"]).objects.filter(Q(pk__in=json.loads(_post["obj_pks"]))).prefetch_related("categories"):
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

