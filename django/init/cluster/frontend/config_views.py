#!/usr/bin/python-init -Ot
# -*- coding: utf-8 -*-

""" config views """

import logging_tools
import process_tools
from init.cluster.frontend.forms import config_type_form
from init.cluster.backbone.models import config_type, config, device_group, device, netdevice, \
     net_ip, peer_information, config_str, config_int, config_bool, config_blob, \
     ng_check_command, ng_check_command_type, ng_service_templ, config_script
from django.db.models import Q
from init.cluster.frontend.helper_functions import init_logging
from init.cluster.frontend.render_tools import render_me
from django.contrib.auth.decorators import login_required
from django.forms.models import modelformset_factory
from lxml import etree
from lxml.builder import E
from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError
import pprint

@init_logging
@login_required
def show_config_type_options(request):
    config_type_formset = modelformset_factory(config_type, form=config_type_form, can_delete=True, extra=1)
    if request.method == "POST" and "ds" not in request.POST:
        cur_ct_fs = config_type_formset(request.POST, request.FILES)
        if cur_ct_fs.is_valid():
            if cur_ct_fs.save() or cur_ct_fs.deleted_forms:
                # re-read formsets after successfull save or delete
                cur_ct_fs = config_type_formset()
    else:
        cur_ct_fs = config_type_formset()
    return render_me(request, "cluster_config_type.html", {
        "config_type_formset" : cur_ct_fs})()

@login_required
@init_logging
def show_configs(request):
    return render_me(
        request, "config_overview.html",
    )()

@login_required
@init_logging
def get_configs(request):
    all_configs = config.objects.all().select_related("config_type").prefetch_related("config_int_set", "config_str_set", "config_bool_set", "config_blob_set", "ng_check_command_set", "config_script_set").order_by("name")
    xml_resp = E.response(
        E.config_list(
            *[cur_c.get_xml() for cur_c in all_configs]
        )
    )
    xml_resp.append(E.config_types(
        *[cur_ct.get_xml() for cur_ct in config_type.objects.all().order_by("name")]
    ))
    xml_resp.append(E.ng_check_command_types(
        *[cur_ct.get_xml() for cur_ct in ng_check_command_type.objects.all().order_by("name")]
    ))
    xml_resp.append(E.ng_service_templates(
        *[cur_st.get_xml() for cur_st in ng_service_templ.objects.all().order_by("name")]
    ))
    print etree.tostring(xml_resp, pretty_print=True)
    request.xml_response["response"] = xml_resp
    return request.xml_response.create_response()

@login_required
@init_logging
def change_xml_entry(request):
    _post = request.POST
    try:
        if _post["id"].count("__") == 2:
            # old version:
            # format object_type, attr_name, object_id, used in device_tree
            # new version:
            # format object_type, object_id, attr_name used in device_configs
            object_type, object_id, attr_name = _post["id"].split("__", 2)
        elif _post["id"].count("__") == 3:
            # format object_type, mother_id, object_id, attr_name, used in device_network
            object_type, mother_id, object_id, attr_name = _post["id"].split("__", 3)
        elif _post["id"].count("__") == 4:
            # format mother_type, mother_id, object_type, object_id, attr_name, used in config_overview
            mother_type, mother_id, object_type, object_id, attr_name = _post["id"].split("__", 4)
        elif _post["id"].count("__") == 5:
            # format mother object_type, dev_id, mother_id, object_type, object_id, attr_name, used in device_network for IPs
            m_object_type, dev_id, mother_id, object_type, object_id, attr_name = _post["id"].split("__", 5)
        else:
            request.log("cannot parse", logging_tools.LOG_LEVEL_ERROR, xml=True)
    except:
        request.log("cannot parse", logging_tools.LOG_LEVEL_ERROR, xml=True)
    else:
        mod_obj = {"dg"      : device_group,
                   "dev"     : device,
                   "nd"      : netdevice,
                   "ip"      : net_ip,
                   "routing" : peer_information,
                   "conf"    : config,
                   "varstr"  : config_str,
                   "varint"  : config_int,
                   "varbool" : config_bool,
                   "varblob" : config_blob,
                   "ngcc"    : ng_check_command,
                   }.get(object_type, None)
        if not mod_obj:
            request.log("unknown object_type '%s'" % (object_type), logging_tools.LOG_LEVEL_ERROR, xml=True)
        else:
            try:
                cur_obj = mod_obj.objects.get(pk=object_id)
            except mod_obj.DoesNotExist:
                request.log("object %s with id %s does not exit" % (object_type,
                                                                    object_id), logging_tools.LOG_LEVEL_ERROR, xml=True)
            else:
                if (object_type, attr_name) == ("dg", "meta_device"):
                    # special call: create new metadevice
                    cur_obj.add_meta_device()
                    request.log("created metadevice for %s" % (cur_obj.name), xml=True)
                elif (object_type, attr_name) == ("dev", "device_group"):
                    # special call: create new metadevice
                    target_dg = device_group.objects.get(Q(pk=_post["value"]))
                    cur_obj.device_group = target_dg
                    cur_obj.save()
                    request.log("moved device %s to %s" % (cur_obj.name,
                                                           target_dg.name), xml=True)
                else:
                    new_value = _post["value"]
                    if _post["checkbox"] == "true":
                        new_value = bool(int(new_value))
                    old_value = getattr(cur_obj, attr_name)
                    try:
                        if cur_obj._meta.get_field(attr_name).get_internal_type() == "ForeignKey":
                            # follow foreign key the django way
                            new_value = cur_obj._meta.get_field(attr_name).rel.to.objects.get(pk=new_value)
                    except:
                        # in case of meta-fields like ethtool_autoneg,speed,duplex
                        pass
                    setattr(cur_obj, attr_name, new_value)
                    try:
                        cur_obj.save()
                    except ValidationError, what:
                        request.log("error modifying: %s" % (unicode(what.messages[0])), logging_tools.LOG_LEVEL_ERROR, xml=True)
                        request.xml_response["original_value"] = old_value
                    except IntegrityError, what:
                        request.log("error modifying (%d): %s" % (what[0], unicode(what[1])), logging_tools.LOG_LEVEL_ERROR, xml=True)
                        request.xml_response["original_value"] = old_value
                    except:
                        raise
                    else:
                        # reread new_value (in case of pre/post-save corrections)
                        new_value = getattr(cur_obj, attr_name)
                        request.xml_response["object"] = cur_obj.get_xml()
                        request.log("changed %s from %s to %s" % (attr_name, unicode(old_value), unicode(new_value)), xml=True)
    return request.xml_response.create_response()

@login_required
@init_logging
def create_config(request):
    _post = request.POST
    val_dict = dict([(key.split("__", 2)[2], value) for key, value in _post.iteritems() if key.count("__") > 1])
    copy_dict = dict([(key, value) for key, value in val_dict.iteritems() if key in ["name", "description", "priority"]])
    new_conf = config(config_type=config_type.objects.get(Q(pk=val_dict["config_type"])),
                      **copy_dict)
    try:
        new_conf.save()
    except ValidationError, what:
        request.log("error creating: %s" % (unicode(what.messages[0])), logging_tools.LOG_LEVEL_ERROR, xml=True)
    except IntegrityError, what:
        request.log("error modifying (%d): %s" % (what[0], unicode(what[1])), logging_tools.LOG_LEVEL_ERROR, xml=True)
    except:
        raise
    else:
        request.xml_response["new_config"] = new_conf.get_xml()
    return request.xml_response.create_response()

@login_required
@init_logging
def delete_config(request):
    _post = request.POST
    val_dict = dict([(key.split("__", 1)[1], value) for key, value in _post.iteritems() if key.count("__") > 0])
    del_pk = int(val_dict.keys()[0].split("__")[0])
    request.log("deleting config %d" % (del_pk))
    config.objects.get(Q(pk=del_pk)).delete()
    return request.xml_response.create_response()

@login_required
@init_logging
def create_var(request):
    _post = request.POST
    keys = _post.keys()
    conf_pk = int(keys[0].split("__")[1])
    value_dict = dict([(key.split("__", 3)[3], value) for key, value in _post.iteritems() if key.count("__") > 2])
    request.log("create new config_var %s for config %d (%s)" % (
        value_dict["name"],
        conf_pk,
        value_dict["type"]))
    new_obj = {"str"  : config_str,
               "int"  : config_int,
               "bool" : config_bool,
               "blob" : config_blob}[value_dict["type"]]
    new_var = new_obj(name=value_dict["name"],
                      description=value_dict["description"],
                      config=config.objects.get(Q(pk=conf_pk)),
                      value=value_dict["value"])
    try:
        new_var.save()
    except ValidationError, what:
        request.log("error creating new variable: %s" % (unicode(what.messages[0])), logging_tools.LOG_LEVEL_ERROR, xml=True)
    else:
        request.xml_response["new_var"] = new_var.get_xml()
    return request.xml_response.create_response()

@login_required
@init_logging
def delete_var(request):
    _post = request.POST
    main_key = [key for key in _post.keys() if key.endswith("__name")][0]
    mother_name, conf_pk, var_type, var_pk, stuff = main_key.split("__", 4)
    del_obj = {"str"  : config_str,
               "int"  : config_int,
               "bool" : config_bool,
               "blob" : config_blob}[var_type[3:]]
    request.log("remove config_%s with pk %s" % (var_type[3:], var_pk))
    del_obj.objects.get(Q(pk=var_pk)).delete()
    return request.xml_response.create_response()

@login_required
@init_logging
def create_script(request):
    _post = request.POST
    keys = _post.keys()
    conf_pk = int(keys[0].split("__")[1])
    val_dict = dict([(key.split("__", 3)[3], value) for key, value in _post.iteritems() if key.count("__") > 2])
    copy_dict = dict([(key, value) for key, value in val_dict.iteritems() if key in ["name", "description", "priority", "value"]])
    print val_dict
    print copy_dict
    new_script = config_script(config=config.objects.get(Q(pk=conf_pk)),
                               **copy_dict)
    try:
        new_script.save()
    except ValidationError, what:
        request.log("error creating new config_script: %s" % (unicode(what.messages[0])), logging_tools.LOG_LEVEL_ERROR, xml=True)
    else:
        request.xml_response["new_config_script"] = new_script.get_xml()
    return request.xml_response.create_response()

@login_required
@init_logging
def delete_script(request):
    _post = request.POST
    val_dict = dict([(key.split("__", 1)[1], value) for key, value in _post.iteritems() if key.count("__") > 0])
    del_cs = int(val_dict.keys()[0].split("__")[0])
    request.log("deleting config_scrript %d" % (del_cs))
    config_script.objects.get(Q(pk=del_cs)).delete()
    return request.xml_response.create_response()
    