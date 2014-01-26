#!/usr/bin/python-init -Ot
# -*- coding: utf-8 -*-

""" base views """

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.db.utils import IntegrityError, DataError
from django.utils.decorators import method_decorator
from django.views.generic import View
from initat.cluster.backbone.models import get_related_models, KPMC_MAP, device_variable, category, \
     category_tree
from initat.cluster.frontend.forms import category_form
from initat.cluster.frontend.helper_functions import xml_wrapper
from initat.core.render import render_me
from lxml.builder import E # @UnresolvedImport
import initat.cluster.backbone.models
import logging
import logging_tools
import json
import process_tools

logger = logging.getLogger("cluster.base")

HIDDEN_FIELDS = set(["password", ])

class change_xml_entry(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        # pprint.pprint(_post)
        # ignore no-operation runs
        ignore_nop = True if int(_post.get("ignore_nop", "0")) else False
        try:
            first_id = _post["id"]
            if first_id.count("__") == 2:
                # old version:
                # format object_type, attr_name, object_id, used in device_tree
                # new version:
                # format object_type, object_id, attr_name used in device_configs
                object_type, object_id, attr_name = first_id.split("__", 2)
            elif first_id.count("__") == 3:
                # format object_type, mother_id, object_id, attr_name, used in device_network
                object_type, mother_id, object_id, attr_name = first_id.split("__", 3)
            elif first_id.count("__") == 4:
                # format mother_type, mother_id, object_type, object_id, attr_name, used in config_overview and part_overview
                mother_type, mother_id, object_type, object_id, attr_name = first_id.split("__", 4)
            elif first_id.count("__") == 5:
                # format mother object_type, dev_id, mother_id, object_type, object_id, attr_name, used in device_network for IPs
                m_object_type, dev_id, mother_id, object_type, object_id, attr_name = first_id.split("__", 5)
            elif first_id.count("__") == 6:
                # format mother object_type, dev_id, mother_id, object_type, object_id, attr_name, used in partition setup
                gm_object_type, m_object_type, dev_id, mother_id, object_type, object_id, attr_name = first_id.split("__", 6)
            else:
                request.xml_response.error("cannot parse '%s'" % (first_id))
                object_type = None
        except:
            request.xml_response.error("cannot parse")
        else:
            mod_obj = KPMC_MAP.get(object_type, None)
            if not mod_obj:
                request.xml_response.error("unknown object_type '%s'" % (object_type))
            else:
                if "other_list" in _post:
                    other_list = _post["other_list"].split("::")
                    logger.info("%s found in request: %s" % (
                        logging_tools.get_plural("other", len(other_list)),
                        ", ".join(other_list)))
                else:
                    other_list = None
                if "pks[]" in _post:
                    object_ids = _post.getlist("pks[]")
                else:
                    object_ids = [object_id]
                new_value = _post["value"]
                for object_id in object_ids:
                    try:
                        cur_obj = mod_obj.objects.get(pk=object_id)
                    except mod_obj.DoesNotExist:
                        request.xml_response.error("%s with id %s does not exit" % (
                            mod_obj._meta.object_name,
                            object_id), logger)
                    else:
                        compound_fields = {
                            "device_variable" : [
                                "value"
                                ],
                            "netdevice"       : [
                                "ethtool_autoneg",
                                "ethtool_duplex",
                                "ethtool_speed"
                                ]
                            }.get(cur_obj._meta.object_name, [])
                        backward_m2m_relations = {
                            "device" : {
                                "devs_mon_host_cluster"    : "mon_host_cluster",
                                "devs_mon_service_cluster" : "mon_service_cluster"},
                            }.get(cur_obj._meta.object_name, [])
                        if attr_name in backward_m2m_relations:
                            # handle backward relations
                            if other_list:
                                logger.critical("ignoring others")
                            new_value = set([int(val) for val in new_value.split("::") if val.strip()])
                            m2m_rel = getattr(cur_obj, attr_name)
                            old_value = set(m2m_rel.all().values_list("pk", flat=True))
                            rem_values = old_value - new_value
                            add_values = new_value - old_value
                            glob_obj = getattr(initat.cluster.backbone.models, backward_m2m_relations[attr_name])
                            if rem_values:
                                m2m_rel.remove(*list(glob_obj.objects.filter(Q(pk__in=rem_values))))
                            if add_values:
                                m2m_rel.add(*list(glob_obj.objects.filter(Q(pk__in=add_values))))
                            if (add_values or rem_values) or not (ignore_nop):
                                request.xml_response.info("added %d, removed %d" % (len(add_values), len(rem_values)), logger)
                        else:
                            # check field ? hack for compound fields
                            check_field = attr_name not in compound_fields
                            if check_field and cur_obj._meta.get_field(attr_name).get_internal_type() == "ManyToManyField":
                                if other_list:
                                    logger.critical("ignoring others")
                                # handle many to many
                                new_value = set([int(val) for val in new_value.split("::") if val.strip()])
                                m2m_rel = getattr(cur_obj, attr_name)
                                old_value = set(m2m_rel.all().values_list("pk", flat=True))
                                rem_values = old_value - new_value
                                add_values = new_value - old_value
                                num_added, num_removed = (0, 0)
                                for rem_value in rem_values:
                                    try:
                                        m2m_rel.remove(cur_obj._meta.get_field(attr_name).rel.to.objects.get(pk=rem_value))
                                    except ValidationError, what:
                                        request.xml_response.error("error modifying: %s" % (unicode(what.messages[0])), logger)
                                    else:
                                        num_removed += 1
                                for add_value in add_values:
                                    try:
                                        m2m_rel.add(cur_obj._meta.get_field(attr_name).rel.to.objects.get(pk=add_value))
                                    except ValidationError, what:
                                        request.xml_response.error("error modifying: %s" % (unicode(what.messages[0])), logger)
                                    else:
                                        num_added += 1
                                if (num_removed or num_added) or not (ignore_nop):
                                    request.xml_response.info("added %d, removed %d" % (num_added, num_removed), logger)
                            else:
                                # others may be present but are not used right now
                                old_value = getattr(cur_obj, attr_name)
                                if _post["checkbox"] == "true":
                                    # cast to bool
                                    new_value = bool(int(new_value))
                                try:
                                    if cur_obj._meta.get_field(attr_name).get_internal_type() == "ForeignKey":
                                        # follow foreign key the django way
                                        if int(new_value) in [0, ""]:
                                            new_value = None
                                        else:
                                            new_value = cur_obj._meta.get_field(attr_name).rel.to.objects.get(pk=new_value)
                                except:
                                    # in case of meta-fields like ethtool_autoneg,speed,duplex
                                    pass
                                cur_obj.change_attribute = attr_name
                                try:
                                    setattr(cur_obj, attr_name, new_value)
                                except:
                                    request.xml_response.error("cannot set %s to %s: %s" % (
                                        attr_name,
                                        unicode(new_value),
                                        process_tools.get_except_info(),
                                        ))
                                try:
                                    cur_obj.save()
                                except ValidationError, what:
                                    request.xml_response.error("error modifying: %s" % (unicode(what.messages[0])), logger)
                                    # not safe to use in case of multi-object modification, FIXME
                                    request.xml_response["original_value"] = old_value
                                except IntegrityError, what:
                                    request.xml_response.error("error modifying: %s" % (unicode(what)), logger)
                                    # not safe to use in case of multi-object modification, FIXME
                                    request.xml_response["original_value"] = old_value
                                except DataError, what:
                                    request.xml_response.error("data error: %s" % (unicode(what)), logger)
                                    request.xml_response["original_value"] = old_value
                                except:
                                    raise
                                else:
                                    # reread new_value (in case of pre/post-save corrections)
                                    new_value = getattr(cur_obj, attr_name)
                                    # not safe to use in case of multi-object modification, FIXME
                                    request.xml_response["object"] = cur_obj.get_xml()
                                    if attr_name in HIDDEN_FIELDS:
                                        request.xml_response.info("changed %s" % (attr_name), logger)
                                    else:
                                        request.xml_response.info("changed %s from %s to %s" % (attr_name, unicode(old_value), unicode(new_value)), logger)
                                # handle others
                                if other_list:
                                    if cur_obj._meta.get_field(attr_name).get_internal_type() == "ForeignKey":
                                        other_change = E.changes(
                                            E.change("%d" % (getattr(cur_obj, "%s_id" % (attr_name))), id=_post["id"], name=attr_name)
                                        )
                                    else:
                                        other_change = E.changes(
                                            E.change(unicode(getattr(cur_obj, attr_name)), id=_post["id"], name=attr_name)
                                        )
                                    for other in other_list:
                                        name = other.split("__")[-1]
                                        if cur_obj._meta.get_field(name).get_internal_type() == "ForeignKey":
                                            other_change.append(E.change("%d" % (getattr(cur_obj, "%s_id" % (name))), id=other, name=name))
                                        else:
                                            other_change.append(E.change(unicode(getattr(cur_obj, name)), id=other, name=name))
                                    # not safe to use in case of multi-object modification, FIXME
                                    request.xml_response["changes"] = other_change

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

class get_category_tree(View):
    @method_decorator(login_required)
    def get(self, request):
        return render_me(request, "category_tree.html",
            {
                "category_form" : category_form(),
            }
            )()

class prune_category_tree(View):
    @method_decorator(login_required)
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
        # new style
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
        request.xml_response.info("added %d, removed %d" % (len(to_add), len(to_del)))

