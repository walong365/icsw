#!/usr/bin/python-init -Ot
# -*- coding: utf-8 -*-

""" config views """

import logging_tools
import process_tools
from initat.cluster.frontend.forms import config_type_form
from initat.cluster.backbone.models import config_type, config, device_group, device, netdevice, \
     net_ip, peer_information, config_str, config_int, config_bool, config_blob, \
     mon_check_command, mon_check_command_type, mon_service_templ, mon_period, mon_contact, user, \
     mon_contactgroup, get_related_models, network_type, network_device_type
from django.db.models import Q
from initat.cluster.frontend.helper_functions import init_logging
from initat.core.render import render_me
from django.contrib.auth.decorators import login_required
from django.forms.models import modelformset_factory
from lxml import etree
from lxml.builder import E
from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError
import pprint

@init_logging
@login_required
def create_command(request):
    _post = request.POST
    pprint.pprint(_post)
    keys = _post.keys()
    conf_pk = int(keys[0].split("__")[1])
    value_dict = dict([(key.split("__", 3)[3], value) for key, value in _post.iteritems() if key.count("__") > 2])
    copy_dict = dict([(key, value) for key, value in value_dict.iteritems() if key in ["name", "command_line", "description"]])
    request.log("create new monitoring_command %s for config %d" % (value_dict["name"], conf_pk))
    new_nc = mon_check_command(
        config=config.objects.get(Q(pk=conf_pk)),
        mon_check_command_type=mon_check_command_type.objects.get(Q(pk=value_dict["mon_check_command_type"])),
        mon_service_templ=mon_service_templ.objects.get(Q(pk=value_dict["mon_service_templ"])),
        **copy_dict)
    #pprint.pprint(copy_dict)
    try:
        new_nc.save()
    except ValidationError, what:
        request.log("error creating new monitoring_config: %s" % (unicode(what.messages[0])), logging_tools.LOG_LEVEL_ERROR, xml=True)
    else:
        request.xml_response["new_monitoring_command"] = new_nc.get_xml()
    return request.xml_response.create_response()
    
@init_logging
@login_required
def delete_command(request):
    _post = request.POST
    main_key = [key for key in _post.keys() if key.endswith("__name")][0]
    try:
        mon_check_command.objects.get(Q(pk=main_key.split("__")[3])).delete()
    except mon_check_command.DoesNotExist:
        request.log("mon_check_command does not exist", logging_tools.LOG_LEVEL_ERROR, xml=True)
    return request.xml_response.create_response()

@init_logging
@login_required
def setup(request):
    return render_me(
        request, "monitoring_setup.html",
    )()

@init_logging
@login_required
def get_config(request):
    xml_resp = E.response()
    request.xml_response["response"] = xml_resp
    xml_resp.append(E.device_groups(*[cur_dg.get_xml(full=False, with_devices=False) for cur_dg in device_group.objects.exclude(Q(cluster_device_group=True))]))
    xml_resp.append(E.users(*[cur_u.get_xml() for cur_u in user.objects.all()]))
    xml_resp.append(E.mon_periods(*[cur_p.get_xml() for cur_p in mon_period.objects.all()]))
    xml_resp.append(E.mon_contacts(*[cur_c.get_xml() for cur_c in mon_contact.objects.all()]))
    xml_resp.append(E.mon_service_templs(*[cur_st.get_xml() for cur_st in mon_service_templ.objects.all()]))
    xml_resp.append(E.mon_contactgroups(*[cur_cg.get_xml() for cur_cg in mon_contactgroup.objects.all()]))
    return request.xml_response.create_response()
    
@init_logging
@login_required
def create_object(request, *args, **kwargs):
    _post = request.POST
    obj_name = kwargs["obj_name"]
    request.log("obj_name for create_object is '%s'" % (obj_name))
    new_obj_class = globals()[obj_name]
    key_pf = min([(len(key), key) for key in _post.iterkeys() if key.count("__new")])[1]
    set_dict = {}
    m2m_dict = {}
    for key, value in _post.iteritems():
        if key.startswith(key_pf) and key != key_pf:
            s_key = key[len(key_pf) + 2:]
            int_type = new_obj_class._meta.get_field(s_key).get_internal_type()
            skip = False
            if int_type.lower() in ["booleanfield", "nullbooleanfield"]:
                d_value = True if int(value) else False
            elif int_type.lower() in ["foreignkey"]:
                d_value = new_obj_class._meta.get_field(s_key).rel.to.objects.get(pk=value)
            elif int_type.lower() in ["integerfield"]:
                d_value = int(value)
            elif int_type.lower() in ["manytomanyfield"]:
                skip = True
                m2m_dict[s_key] = [int(val) for val in value.split("::") if val.strip()]
            else:
                d_value = value
            request.log("key '%s' is '%s' -> '%s' (%s)" % (s_key, value, unicode(d_value), type(d_value)))
            if not skip:
                set_dict[s_key] = d_value
    new_obj = new_obj_class(**set_dict)
    try:
        new_obj.save()
    except ValidationError, what:
        request.log("error creating: %s" % (unicode(what.messages[0])), logging_tools.LOG_LEVEL_ERROR, xml=True)
    except:
        request.log("error creating: %s" % (process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR, xml=True)
    else:
        # add m2m entries
        for key, value in m2m_dict.iteritems():
            request.log("added %s for %s" % (logging_tools.get_plural("m2m entry", len(value)), key))
            for sub_value in value:
                getattr(new_obj, key).add(new_obj_class._meta.get_field(key).rel.to.objects.get(Q(pk=sub_value)))
        request.log("created new entry", xml=True)
        request.xml_response["new_entry"] = new_obj.get_xml()
    return request.xml_response.create_response()

@init_logging
@login_required
def delete_object(request, *args, **kwargs):
    _post = request.POST
    obj_name = kwargs["obj_name"]
    request.log("obj_name for delete_object is '%s'" % (obj_name))
    del_obj_class = globals()[obj_name]
    key_pf = min([(len(key), key) for key in _post.iterkeys() if key.count("__")])[1]
    del_pk = int(key_pf.split("__")[1])
    request.log("removing item with pk %d" % (del_pk))
    try:
        del_obj = del_obj_class.objects.get(Q(pk=del_pk))
    except:
        request.log("object not found for deletion: %s" % (process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR, xml=True)
    else:
        num_ref = get_related_models(del_obj)
        if num_ref:
            request.log("cannot delete %s '%s': %s" % (
                del_obj._meta.object_name,
                unicode(del_obj),
                logging_tools.get_plural("reference", num_ref)), logging_tools.LOG_LEVEL_ERROR, xml=True)
        else:
            del_obj.delete()
            request.log("deleted %s" % (del_obj._meta.object_name), xml=True)
    return request.xml_response.create_response()
    