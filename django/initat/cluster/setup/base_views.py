#!/usr/bin/python-init -Ot
# -*- coding: utf-8 -*-

""" base views """

import logging_tools
import process_tools
from initat.cluster.backbone.models import config_type, config, device_group, device, netdevice, \
     net_ip, peer_information, config_str, config_int, config_bool, config_blob, \
     mon_check_command, mon_check_command_type, mon_service_templ, config_script, device_config, \
     tree_node, wc_files, partition_disc, partition, mon_period, mon_contact, mon_service_templ, \
     mon_contactgroup, get_related_models, network_device_type, network_type, device_class, \
     device_location, network
from django.db.models import Q
from initat.cluster.frontend.helper_functions import init_logging
from initat.core.render import render_me
from django.contrib.auth.decorators import login_required
from lxml import etree
from lxml.builder import E
from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError
import pprint
import net_tools
import server_command

@login_required
@init_logging
def change_xml_entry(request):
    _post = request.POST
    #pprint.pprint(_post)
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
            # format mother_type, mother_id, object_type, object_id, attr_name, used in config_overview and part_overview
            mother_type, mother_id, object_type, object_id, attr_name = _post["id"].split("__", 4)
        elif _post["id"].count("__") == 5:
            # format mother object_type, dev_id, mother_id, object_type, object_id, attr_name, used in device_network for IPs
            m_object_type, dev_id, mother_id, object_type, object_id, attr_name = _post["id"].split("__", 5)
        elif _post["id"].count("__") == 6:
            # format mother object_type, dev_id, mother_id, object_type, object_id, attr_name, used in partition setup
            gm_object_type, m_object_type, dev_id, mother_id, object_type, object_id, attr_name = _post["id"].split("__", 6)
        else:
            request.log("cannot parse '%s'" % (_post["id"]), logging_tools.LOG_LEVEL_ERROR, xml=True)
    except:
        request.log("cannot parse", logging_tools.LOG_LEVEL_ERROR, xml=True)
    else:
        mod_obj = {"devg"    : device_group,
                   "dev"     : device,
                   "nd"      : netdevice,
                   "ip"      : net_ip,
                   "routing" : peer_information,
                   "conf"    : config,
                   "varstr"  : config_str,
                   "varint"  : config_int,
                   "varbool" : config_bool,
                   "varblob" : config_blob,
                   "cscript" : config_script,
                   "moncc"   : mon_check_command,
                   "moncon"  : mon_contact,
                   "pdisc"   : partition_disc,
                   "part"    : partition,
                   "monper"  : mon_period,
                   "monst"   : mon_service_templ,
                   "moncg"   : mon_contactgroup,
                   "nwdt"    : network_device_type,
                   "nwt"     : network_type,
                   "dc"      : device_class,
                   "dl"      : device_location,
                   "nw"      : network
                   }.get(object_type, None)
        if not mod_obj:
            request.log("unknown object_type '%s'" % (object_type), logging_tools.LOG_LEVEL_ERROR, xml=True)
        else:
            try:
                cur_obj = mod_obj.objects.get(pk=object_id)
            except mod_obj.DoesNotExist:
                request.log("object %s with id %s does not exit" % (
                    object_type,
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
                    if "other_list" in _post:
                        other_list = _post["other_list"].split("::")
                        request.log("%s found in request: %s" % (
                            logging_tools.get_plural("other", len(other_list)),
                            ", ".join(other_list)))
                    new_value = _post["value"]
                    if cur_obj._meta.get_field(attr_name).get_internal_type() == "ManyToManyField":
                        if other_list:
                            request.log("ignoring others", logging_tools.LOG_LEVEL_CRITICAL)
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
                        request.log("added %d, removed %d" % (len(add_values), len(rem_values)), xml=True)
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
                        cur_obj.master_change = attr_name
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
        request.log("created new %s" % (new_obj._meta.object_name), xml=True)
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

