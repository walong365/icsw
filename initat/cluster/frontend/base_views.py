#!/usr/bin/python-init -Ot
# -*- coding: utf-8 -*-

""" base views """

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from django.db.models import Q
from django.db.utils import IntegrityError, DataError
from django.utils.decorators import method_decorator
from django.views.generic import View
from initat.cluster.backbone.models import device, \
     get_related_models, KPMC_MAP, device_variable, category, \
     category_tree
from initat.cluster.frontend.forms import category_form
from initat.cluster.frontend.helper_functions import xml_wrapper
from initat.core.render import render_me, render_string
from lxml.builder import E # @UnresolvedImport
import initat.cluster.backbone.models
import logging
import logging_tools
import pprint
import process_tools
import re

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

class create_object(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request, *args, **kwargs):
        _post = request.POST
        obj_name = kwargs["obj_name"]
        logger.info("obj_name for create_object is '%s'" % (obj_name))
        new_obj_class = getattr(initat.cluster.backbone.models, obj_name)
        key_pf = min([(len(key), key) for key in _post.iterkeys() if key.count("__new")])[1]
        set_dict, extra_dict = ({}, {})
        m2m_dict = {}
        logger.info("key_prefix is '%s'" % (key_pf))
        no_check_fields = {
            "device_variable" : ["value"]}.get(obj_name, [])
        # was used for permissions, not needed right now
        proxy_fields = {}
        xml_create_args = {
            "user"  : {"with_permissions" : True},
            "group" : {"with_permissions" : True},
        }
        if no_check_fields:
            logger.info("%s: %s" % (
                logging_tools.get_plural("no_check_field", len(no_check_fields)),
                ", ".join(no_check_fields)))
        for key, value in _post.iteritems():
            if key.startswith(key_pf) and key != key_pf:
                s_key = key[len(key_pf) + 2:]
                if s_key in no_check_fields:
                    extra_dict[s_key] = value
                else:
                    skip = False
                    if s_key not in proxy_fields:
                        int_type = new_obj_class._meta.get_field(s_key).get_internal_type()
                    else:
                        int_type = "???"
                    if s_key in proxy_fields:
                        # proxy field, for instance permissions (related to django group/user not csw group/user)
                        # see above, not in use right now
                        if s_key == "permissions":
                            d_value = value
                        else:
                            # FIXME
                            pass
                    elif int_type.lower() in ["booleanfield", "nullbooleanfield"]:
                        d_value = True if int(value) else False
                    elif int_type.lower() in ["foreignkey"]:
                        if int(value) == 0:
                            d_value = None
                        else:
                            d_value = new_obj_class._meta.get_field(s_key).rel.to.objects.get(pk=value)
                    elif int_type.lower() in ["integerfield"]:
                        d_value = int(value)
                    elif int_type.lower() in ["manytomanyfield"]:
                        skip = True
                        m2m_dict[s_key] = [int(val) for val in value.split("::") if val.strip()]
                    else:
                        d_value = value
                    logger.info("key '%s' is '%s' -> '%s' (%s)" % (s_key, value, unicode(d_value), type(d_value)))
                    if not skip:
                        set_dict[s_key] = d_value
        create_list = [(None, None)]
        for range_attr, range_re in {"device" : [
            ("name", re.compile("^(?P<name>.+)\[(?P<start>\d+)-(?P<end>\d+)\](?P<post>.*)$"))]}.get(obj_name, []):
            range_m = range_re.match(set_dict[range_attr])
            if range_m:
                num_dig = max(len(range_m.group("start")),
                              len(range_m.group("end")))
                start_idx, end_idx = (
                    int(range_m.group("start")),
                    int(range_m.group("end")))
                start_idx, end_idx = (
                    min(start_idx, end_idx),
                    max(start_idx, end_idx))
                start_idx, end_idx = (
                    min(max(start_idx, 1), 1000),
                    min(max(end_idx, 1), 1000))
                logger.info(
                    "range has %s (%d -> %d)" % (
                        logging_tools.get_plural("digit", num_dig),
                        start_idx,
                        end_idx))
                form_str = "%s%%0%dd%s" % (
                    range_m.group("name"),
                    num_dig,
                    range_m.group("post"))
                create_list = [(range_attr, form_str % (cur_idx)) for cur_idx in xrange(start_idx, end_idx + 1)]
        created_ok = []
        for change_key, change_value in create_list:
            new_obj = new_obj_class(**set_dict)
            for key, value in extra_dict.iteritems():
                setattr(new_obj, key, value)
            if change_key:
                setattr(new_obj, change_key, change_value)
            # add defaults
            if obj_name == "device_variable":
                new_obj.device = device.objects.get(Q(pk=key_pf.split("__")[1]))
            try:
                new_obj.save()
            except ValidationError, what:
                request.xml_response.error("error creating: %s" % (unicode(what.messages[0])), logger)
            except:
                request.xml_response.error("error creating: %s" % (process_tools.get_except_info()), logger)
            else:
                created_ok.append(new_obj)
                # add m2m entries
                for key, value in m2m_dict.iteritems():
                    logger.info("added %s for %s" % (logging_tools.get_plural("m2m entry", len(value)), key))
                    for sub_value in value:
                        getattr(new_obj, key).add(new_obj_class._meta.get_field(key).rel.to.objects.get(Q(pk=sub_value)))
                request.xml_response["new_entry"] = new_obj.get_xml(**xml_create_args.get(new_obj._meta.object_name, {}))
        if created_ok:
            request.xml_response.info("created %s new %s" % (
                " %d" % (len(create_list)) if len(create_list) > 1 else "",
                new_obj._meta.object_name), logger)

class get_gauge_info(View):
    @method_decorator(xml_wrapper)
    def post(self, request):
        gauge_info = E.gauge_info()
        for gauge_dv in device_variable.objects.filter(Q(name="_SYS_GAUGE_") & Q(is_public=False)).order_by("description"):
            gauge_info.append(
                E.gauge_element(
                    gauge_dv.description,
                    value="%d" % (gauge_dv.val_int),
                )
            )
        # gauge_info.append(E.gauge_element("test", value="40"))
        request.xml_response["response"] = gauge_info

class delete_object(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request, *args, **kwargs):
        _post = request.POST
        obj_name = kwargs["obj_name"]
        force_delete = _post.get("force_delete", "false").lower() == "true"
        del_obj_class = getattr(initat.cluster.backbone.models, obj_name)
        valid_keys = [key for key in _post.iterkeys() if key.count("__")]
        if valid_keys:
            key_pf = min([(len(key), key) for key in valid_keys])[1]
            del_index = int(_post.get("delete_index", "1"))
            logger.info("obj_name for delete_object is '%s' (delete_index is %d), force_delete flag is %s" % (
                obj_name,
                del_index,
                str(force_delete),
            ))
            del_pk = int(key_pf.split("__")[del_index])
            logger.info("removing item with pk %d" % (del_pk))
            try:
                del_obj = del_obj_class.objects.get(Q(pk=del_pk))
            except:
                request.xml_response.error("object not found for deletion: %s" % (process_tools.get_except_info()), logger)
            else:
                min_ref = 0
                if obj_name == "device_group":
                    # remove associated meta_device
                    if del_obj.device_id:
                        min_ref = 1
                num_ref = get_related_models(del_obj)
                if num_ref > min_ref and not force_delete:
                    # pprint.pprint(get_related_models(del_obj, detail=True))
                    request.xml_response.error(
                        "cannot delete %s '%s': %s" % (
                            del_obj._meta.object_name,
                            unicode(del_obj),
                            logging_tools.get_plural("reference", num_ref)), logger)
                else:
                    del_info = unicode(del_obj)
                    del_obj.delete()
                    request.xml_response.info("deleted %s '%s'" % (del_obj._meta.object_name, del_info), logger)
        else:
            request.xml_response.error("no valid keys found (present: %s)" % (", ".join(sorted(_post.keys()))), logger)

class get_object(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request, *args, **kwargs):
        _post = request.POST
        key_type, key_pk = _post["key"].split("__")
        if not key_pk.isdigit():
            request.xml_response.error("PK is not an integer", logger)
        else:
            arg_dict = {}
            for key, value in _post.iteritems():
                if key.startswith("true_flag"):
                    arg_dict[value] = True
                elif key.startswith("false_flag"):
                    arg_dict[value] = False
            mod_obj = KPMC_MAP.get(key_type, None)
            if not mod_obj:
                request.xml_response.error("object with type '%s' not found" % (key_type), logger)
            else:
                request.xml_response["result"] = mod_obj.objects.get(Q(pk=key_pk)).get_xml(**arg_dict)

class get_category_tree(View):
    @method_decorator(login_required)
    def get(self, request):
        return render_me(request, "category_tree.html",
            {
                "category_form" : category_form(),
            }
            )()
#     @method_decorator(xml_wrapper)
#     def post(self, request):
#         _post = request.POST
#         with_devices = True if int(_post.get("with_devices", "0")) else False
#         with_device_count = True if int(_post.get("with_device_count", "0")) else False
#         request.xml_response["response"] = category_tree(
#             with_device_count=with_device_count,
#             with_devices=with_devices,
#             ).get_xml()

class prune_category_tree(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        category_tree().prune()
        request.xml_response.info("tree pruned")

# class category_detail(View):
#     @method_decorator(login_required)
#     @method_decorator(xml_wrapper)
#     def post(self, request):
#         cur_cat = category.objects.get(Q(pk=request.POST["key"]))
#         if cur_cat.full_name.startswith("/location"):
#             cur_form = location_detail_form
#         else:
#             cur_form = category_detail_form
#         request.xml_response["form"] = render_string(
#             request,
#             "crispy_form.html",
#             {
#                 "form" : cur_form(
#                     auto_id="cat__%d__%%s" % (cur_cat.pk),
#                     instance=cur_cat,
#                 )
#             }
#         )

class get_cat_references(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        cur_cat = category.objects.prefetch_related("device_set", "config_set", "mon_check_command_set", "device_set__domain_tree_node").get(Q(pk=request.POST["key"]))
        res_list = E.references()
        for entry in ["device", "config", "mon_check_command"]:
            _getter = getattr(cur_cat, "%s_set" % (entry))
            if _getter.count():
                sub_list = getattr(E, entry)(count="%d" % (_getter.count()))
                for sub_entry in _getter.all():
                    info_str = sub_entry.full_name if entry == "device" else unicode(sub_entry)
                    sub_list.append(E.entry(info_str, pk="%d" % (sub_entry.pk)))
                res_list.append(sub_list)
        request.xml_response["result"] = res_list

# class delete_category(View):
#     @method_decorator(login_required)
#     @method_decorator(xml_wrapper)
#     def post(self, request):
#         _post = request.POST
#         cur_cat = category.objects.get(Q(pk=_post["key"]))
#         num_ref = get_related_models(cur_cat, m2m=True)
#         if num_ref:
#             request.xml_response.error(
#                 "category '%s' still referenced by %s" % (
#                     unicode(cur_cat),
#                     logging_tools.get_plural("object", num_ref)),
#                 logger)
#         elif not cur_cat.depth:
#             request.xml_response.error(
#                 "cannot delete root category",
#                 logger)
#         else:
#             request.xml_response.info("removed category '%s'" % (unicode(cur_cat)), logger)
#             cur_cat.delete()

# class create_category(View):
#     @method_decorator(login_required)
#     @method_decorator(xml_wrapper)
#     def get(self, request):
#         new_form = category_new_form(
#             auto_id="cat__new__%s",
#         )
#         new_form.helper.form_action = reverse("base:create_category")
#         request.xml_response["form"] = render_string(
#             request,
#             "crispy_form.html",
#             {
#                 "form" : new_form,
#             }
#         )
#         return request.xml_response.create_response()
#     @method_decorator(login_required)
#     @method_decorator(xml_wrapper)
#     def post(self, request):
#         logger.info("creating new category")
#         _post = request.POST
#         cur_form = category_new_form(_post)
#         if cur_form.is_valid():
#             full_tree = category_tree()
#             if cur_form.cleaned_data["full_name"] in full_tree:
#                 request.xml_response.warn("category already exists", logger)
#             else:
#                 try:
#                     new_cat = full_tree.add_category(cur_form.cleaned_data["full_name"])
#                     # print "**", cur_form.cleaned_data
#                     # copy from cleaned_data
#                     for key in ["comment", ]:
#                         setattr(new_cat, key, cur_form.cleaned_data[key])
#                     new_cat.save()
#                 except:
#                     request.xml_response.error("error creating new category: %s" % (process_tools.get_except_info()), logger)
#                 else:
#                     request.xml_response.info("created new category '%s'" % (unicode(new_cat)), logger)
#                     node_list = [new_cat.get_xml()]
#                     while new_cat.parent_id:
#                         new_cat = new_cat.parent
#                         node_list.append(new_cat.get_xml())
#                     request.xml_response["new_nodes"] = list(reversed(node_list))
#         else:
#             line = ", ".join(cur_form.errors.as_text().split("\n"))
#             request.xml_response.error(line, logger)

# class move_category(View):
#     @method_decorator(login_required)
#     @method_decorator(xml_wrapper)
#     def post(self, request):
#         _post = request.POST
#         src_node = category.objects.get(Q(pk=_post["src_id"]))
#         dst_node = category.objects.get(Q(pk=_post["dst_id"]))
#         mode = _post["mode"]
#         if mode in ["over", "child"]:
#             src_node.parent = dst_node
#         else:
#             src_node.parent = dst_node.parent
#         try:
#             src_node.save()
#         except:
#             request.xml_response.error("error moving node: %s" % (process_tools.get_except_info()), logger)
#         else:
#             request.xml_response.info("moved category '%s' to '%s' (%s)" % (
#                 unicode(src_node),
#                 unicode(dst_node),
#                 mode), logger)
#         # cleanup category tree
#         _cur_ct = category_tree()

class change_category(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        obj_type, obj_pk = _post["obj_key"].split("__")
        mod_obj = KPMC_MAP.get(obj_type, None)
        cur_obj = mod_obj.objects.get(Q(pk=obj_pk))
        add = True if int(_post["flag"]) else False
        new_cat = category.objects.get(Q(pk=_post["cat_pk"]))
        if add:
            cur_obj.categories.add(new_cat)
            request.xml_response.info("add category '%s' to %s" % (unicode(new_cat), unicode(cur_obj)), logger)
        else:
            cur_obj.categories.remove(new_cat)
            request.xml_response.info("removed category '%s' from %s" % (unicode(new_cat), unicode(cur_obj)), logger)
        request.xml_response["object"] = cur_obj.get_xml()
