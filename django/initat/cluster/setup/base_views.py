#!/usr/bin/python-init -Ot
# -*- coding: utf-8 -*-

""" base views """

import pprint
import re
import logging_tools
import process_tools
import logging
from lxml.builder import E

from django.db.models import Q
from django.db.utils import IntegrityError
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.views.generic import View
from django.utils.decorators import method_decorator

import initat.cluster.backbone.models
from initat.cluster.frontend.helper_functions import xml_wrapper
from initat.cluster.backbone.models import device_group, device, \
     get_related_models, device_class, KPMC_MAP, device_variable

logger = logging.getLogger("cluster.setup")

HIDDEN_FIELDS = set(["password",])

class change_xml_entry(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        #pprint.pprint(_post)
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
                        request.xml_response.error("object %s with id %s does not exit" % (
                            object_type,
                            object_id), logger)
                    else:
                        compound_fields = {
                            "device_variable" : [
                                "value"],
                            "user"            : [
                                "permissions"],
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
                                for rem_value in rem_values:
                                    m2m_rel.remove(cur_obj._meta.get_field(attr_name).rel.to.objects.get(pk=rem_value))
                                for add_value in add_values:
                                    m2m_rel.add(cur_obj._meta.get_field(attr_name).rel.to.objects.get(pk=add_value))
                                if (add_values or rem_values) or not (ignore_nop):
                                    request.xml_response.info("added %d, removed %d" % (len(add_values), len(rem_values)), logger)
                            else:
                                # others may be present but are not used right now
                                old_value = getattr(cur_obj, attr_name)
                                if _post["checkbox"] == "true":
                                    # cast to bool
                                    new_value = bool(int(new_value))
                                try:
                                    if cur_obj._meta.get_field(attr_name).get_internal_type() == "ForeignKey":
                                        # follow foreign key the django way
                                        if int(new_value) == 0:
                                            new_value = None
                                        else:
                                            new_value = cur_obj._meta.get_field(attr_name).rel.to.objects.get(pk=new_value)
                                except:
                                    # in case of meta-fields like ethtool_autoneg,speed,duplex
                                    pass
                                cur_obj.change_attribute = attr_name
                                setattr(cur_obj, attr_name, new_value)
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
                                    other_change = E.changes(
                                        E.change(unicode(getattr(cur_obj, attr_name)), id=_post["id"], name=attr_name))
                                    for other in other_list:
                                        name = other.split("__")[-1]
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
        no_check_fields = {"device_variable" : ["value"],
                           "user"            : ["permissions"]}.get(obj_name, [])
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
                    int_type = new_obj_class._meta.get_field(s_key).get_internal_type()
                    if int_type.lower() in ["booleanfield", "nullbooleanfield"]:
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
                start_idx, end_idx = (int(range_m.group("start")),
                                      int(range_m.group("end")))
                start_idx, end_idx = (min(start_idx, end_idx),
                                      max(start_idx, end_idx))
                start_idx, end_idx = (min(max(start_idx, 1), 1000),
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
            for add_field, value in {"device" : [("device_class", device_class.objects.get(Q(pk=1)))]}.get(obj_name, []):
                setattr(new_obj, add_field, value)
            if obj_name == "device_variable":
                new_obj.device = device.objects.get(Q(pk=key_pf.split("__")[1]))
            try:
                new_obj.save()
            except ValidationError, what:
                request.xml_response.error("error creating: %s" % (unicode(what.messages[0])), logger)
            except:
                request.xml_repsonse.error("error creating: %s" % (process_tools.get_except_info()), logger)
            else:
                created_ok.append(new_obj)
                # add m2m entries
                for key, value in m2m_dict.iteritems():
                    logger.info("added %s for %s" % (logging_tools.get_plural("m2m entry", len(value)), key))
                    for sub_value in value:
                        getattr(new_obj, key).add(new_obj_class._meta.get_field(key).rel.to.objects.get(Q(pk=sub_value)))
                request.xml_response["new_entry"] = new_obj.get_xml()
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
        #gauge_info.append(E.gauge_element("test", value="40"))
        request.xml_response["response"] = gauge_info
    
class delete_object(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request, *args, **kwargs):
        _post = request.POST
        obj_name = kwargs["obj_name"]
        force_delete = _post.get("force_delete", "false").lower() == "true"
        del_obj_class = getattr(initat.cluster.backbone.models, obj_name)
        key_pf = min([(len(key), key) for key in _post.iterkeys() if key.count("__")])[1]
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
                request.xml_response.error(
                    "cannot delete %s '%s': %s" % (
                        del_obj._meta.object_name,
                        unicode(del_obj),
                        logging_tools.get_plural("reference", num_ref)), logger)
            else:
                del_info = unicode(del_obj)
                del_obj.delete()
                request.xml_response.info("deleted %s '%s'" % (del_obj._meta.object_name, del_info), logger)

class get_object(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request, *args, **kwargs):
        _post = request.POST
        key_type, key_pk = _post["key"].split("__")
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
    