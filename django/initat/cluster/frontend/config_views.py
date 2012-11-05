#!/usr/bin/python-init -Ot
# -*- coding: utf-8 -*-

""" config views """

import logging_tools
import process_tools
from initat.cluster.frontend.forms import config_type_form
from initat.cluster.backbone.models import config_type, config, device_group, device, netdevice, \
     net_ip, peer_information, config_str, config_int, config_bool, config_blob, \
     mon_check_command, mon_check_command_type, mon_service_templ, config_script, device_config, \
     tree_node, wc_files, partition_disc, partition, mon_period, mon_contact, mon_service_templ, \
     mon_contactgroup
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
import net_tools
import server_command

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
    _post = request.POST
    mode = _post.get("mode", "full")
    full_mode = mode == "full"
    request.log("get configs, mode is %s" % (mode))
    if full_mode:
        all_configs = config.objects.all().select_related("config_type").prefetch_related("config_int_set", "config_str_set", "config_bool_set", "config_blob_set", "mon_check_command_set", "config_script_set").order_by("name")
    else:
        all_configs = config.objects.all().select_related("config_type").order_by("name")
    xml_resp = E.response(
        E.config_list(
            *[cur_c.get_xml(full=full_mode) for cur_c in all_configs]
        )
    )
    if full_mode:
        xml_resp.append(E.config_types(
            *[cur_ct.get_xml() for cur_ct in config_type.objects.all().order_by("name")]
        ))
        xml_resp.append(E.mon_check_command_types(
            *[cur_ct.get_xml() for cur_ct in mon_check_command_type.objects.all().order_by("name")]
        ))
        xml_resp.append(E.mon_service_templates(
            *[cur_st.get_xml() for cur_st in mon_service_templ.objects.all().order_by("name")]
        ))
    #print etree.tostring(xml_resp, pretty_print=True)
    request.xml_response["response"] = xml_resp
    return request.xml_response.create_response()

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
                   "moncg"   : mon_contactgroup
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
                    if cur_obj._meta.get_field(attr_name).get_internal_type() == "ManyToManyField":
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
    del_cs = int(val_dict.keys()[0].split("__")[2])
    request.log("deleting config_script %d" % (del_cs))
    config_script.objects.get(Q(pk=del_cs)).delete()
    return request.xml_response.create_response()

@login_required
@init_logging
def get_device_configs(request):
    request.xml_response["response"] = _get_device_configs(request.POST.getlist("sel_list[]", []))
    #print etree.tostring(xml_resp, pretty_print=True)
    return request.xml_response.create_response()

def _get_device_configs(sel_list, **kwargs):
    dev_list  = [key.split("__")[1] for key in sel_list if key.startswith("dev__")]
    devg_list = [key.split("__")[1] for key in sel_list if key.startswith("devg__")]
    all_devs = device.objects.exclude(Q(device_type__identifier="MD")).filter(Q(pk__in=dev_list) | Q(device_group__in=devg_list))
    # all meta devices
    meta_devs = device.objects.filter(Q(device_type__identifier="MD") & Q(device_group__device_group__in=dev_list)).distinct()
    meta_confs = device_config.objects.filter(Q(device__in=meta_devs)).select_related("device")
    if "conf" in kwargs:
        all_confs = device_config.objects.filter(Q(config=kwargs["conf"]) & (Q(device__in=dev_list) | Q(device__device_group__in=devg_list)))
        meta_confs = meta_confs.filter(config=kwargs["conf"])
    else:
        all_confs = device_config.objects.filter(Q(device__in=dev_list) | Q(device__device_group__in=devg_list))
    xml_resp = E.device_configs()
    # build dict device_group -> conf_list
    dg_dict = {}
    for meta_conf in meta_confs:
        dg_dict.setdefault(meta_conf.device.device_group_id, []).append(meta_conf.config_id)
    for cur_conf in all_confs:
        xml_resp.append(cur_conf.get_xml())
    # add meta device configs
    for sbm_dev in all_devs:
        for conf_id in dg_dict.get(sbm_dev.device_group_id, []):
            xml_resp.append(E.device_config(
                device="%d" % (sbm_dev.pk),
                config="%d" % (conf_id),
                meta="1"))
    return xml_resp
    
@login_required
@init_logging
def alter_config_cb(request):
    _post = request.POST
    checked = bool(int(_post["value"]))
    dev_id, conf_id = (int(_post["id"].split("__")[1]),
                       int(_post["id"].split("__")[3]))
    cur_dev, cur_conf = (device.objects.select_related("device_type").get(Q(pk=dev_id)),
                         config.objects.get(Q(pk=conf_id)))
    # is metadevice ?
    is_meta = cur_dev.device_type.identifier == "MD"
    # all devices of device_group
    all_devs = cur_dev.device_group.device_group.all()
    request.log("device %s [%s]/ config %s: %s (%s in device_group)" % (
        unicode(cur_dev),
        "MD" if is_meta else "-",
        unicode(cur_conf),
        "set" if checked else "unset",
        logging_tools.get_plural("device", len(all_devs))))
    if is_meta:
        # handling of actions for meta devices
        if checked:
            # remove all configs from devices in group
            to_remove = device_config.objects.exclude(Q(device=cur_dev)).filter(Q(config=cur_conf) & Q(device__in=all_devs))
            if len(to_remove):
                to_remove.delete()
                request.log("removed %s from devices" % (logging_tools.get_plural("config", len(to_remove))))
            # unset all devices except meta_device
            try:
                device_config.objects.get(Q(device=cur_dev) & Q(config=cur_conf))
            except device_config.DoesNotExist:
                device_config(device=cur_dev,
                              config=cur_conf).save()
                request.log("set meta config")
            else:
                request.log("meta config already set")
        else:
            try:
                device_config.objects.get(Q(device=cur_dev) & Q(config=cur_conf)).delete()
            except device_config.DoesNotExist:
                request.log("meta config already unset")
            else:
                request.log("removed meta config")
    else:
        # get meta device
        try:
            meta_dev = cur_dev.device_group.device_group.get(Q(device_type__identifier="MD"))
        except device.DoesNotExist:
            meta_dev = None
        # handling of actions for non-meta devices
        if checked:
            try:
                device_config.objects.get(Q(device=cur_dev) & Q(config=cur_conf))
            except device_config.DoesNotExist:
                device_config(device=cur_dev,
                              config=cur_conf).save()
                request.log("set config")
            else:
                request.log("config already set")
        else:
            try:
                device_config.objects.get(Q(device=cur_dev) & Q(config=cur_conf)).delete()
            except device_config.DoesNotExist:
                if meta_dev:
                    # check if meta_device has config_set
                    try:
                        meta_conf = device_config.objects.get(Q(device=meta_dev) & Q(config=cur_conf))
                    except device_config.DoesNotExist:
                        request.log("config already unset and meta config also not set", logging_tools.LOG_LEVEL_ERROR)
                    else:
                        # set config for all devices exclude the meta device and this device
                        meta_conf.delete()
                        for set_dev in all_devs.exclude(Q(pk=meta_dev.pk)).exclude(Q(pk=cur_dev.pk)):
                            device_config(device=set_dev,
                                          config=cur_conf).save()
                else:
                    request.log("config already unset")
            else:
                request.log("removed config")
    xml_resp = _get_device_configs(["dev__%d" % (sel_dev.pk) for sel_dev in all_devs], conf=cur_conf)
    xml_resp.extend([
        E.config(pk="%d" % (cur_conf.pk)),
        E.devices(
            *[
                E.device(
                    pk="%d" % (sel_dev.pk),
                    key="dev__%d" % (sel_dev.pk)
                ) for sel_dev in all_devs])
    ])
    request.xml_response["response"] = xml_resp
    #print etree.tostring(xml_resp, pretty_print=True)
    return request.xml_response.create_response()

class tree_struct(object):
    def __init__(self, cur_dev, node_list, node=None, depth=0, wcf_dict={}):
        self.dev_pk = cur_dev.pk
        self.depth = depth
        if not node:
            if node_list:
                self.node = [entry for entry in node_list if not entry.parent_id][0]
                wcf_dict = dict([(cur_wc.tree_node_id, cur_wc) for cur_wc in wc_files.objects.filter(Q(device=self.node.device_id))])
            else:
                self.node = None
        else:
            self.node = node
        if self.node is not None:
            self.wc_file = wcf_dict.get(self.node.pk, None)
            self.childs = [tree_struct(
                cur_dev,
                node_list,
                node=cur_node,
                depth=self.depth + 1,
                wcf_dict=wcf_dict) for cur_node in node_list if cur_node.parent_id == self.node.pk]
        else:
            self.wc_file = None
            self.childs = []
    def get_name(self):
        if self.node:
            return "%s%s" % (self.wc_file.dest,
                             "/" if self.node.is_dir else "")
        else:
            return "empty"
    def __unicode__(self):
        return "\n".join([
            "%s%s (%d), %s" % ("  " * self.depth,
                               unicode(self.node),
                               self.depth,
                               self.get_name())
            ] + 
            ["%s" % (unicode(sub_entry)) for sub_entry in self.childs])
    def get_xml(self):
        return E.tree(
            self.wc_file.get_xml(),
            *[sub_node.get_xml() for sub_node in self.childs],
            name=self.get_name(),
            depth="%d" % (self.depth),
            is_dir="1" if self.node.is_dir else "0",
            is_link="1" if self.node.is_link else "0",
            node_id="%d_%d" % (self.dev_pk, self.node.pk)
        )
        
@login_required
@init_logging
def generate_config(request):
    _post = request.POST
    sel_list = [key.split("__")[1] for key in _post.getlist("sel_list[]", []) if key.startswith("dev__")]
    dev_list = device.objects.filter(Q(pk__in=sel_list)).order_by("name")
    dev_dict = dict([(cur_dev.pk, cur_dev) for cur_dev in dev_list])
    request.log("generating config for %s: %s" % (logging_tools.get_plural("device", len(dev_list)),
                                                  ", ".join([unicode(dev) for dev in dev_list])))
    srv_com = server_command.srv_command(command="build_config")
    srv_com["devices"] = srv_com.builder(
        "devices",
        *[srv_com.builder("device", pk="%d" % (cur_dev.pk)) for cur_dev in dev_list])
    result = net_tools.zmq_connection("config_webfrontend", timeout=5).add_connection("tcp://localhost:8005", srv_com)
    if not result:
        request.log("error contacting server", logging_tools.LOG_LEVEL_ERROR, xml=True)
    else:
        request.xml_response["result"] = E.devices()
        for dev_node in result.xpath(None, ".//ns:device"):
            res_node = E.device(dev_node.text, **dev_node.attrib)
            #if int(dev_node.attrib["state_level"]) == logging_tools.LOG_LEVEL_OK or True:
            cur_dev = dev_dict[int(dev_node.attrib["pk"])]
            # build tree
            cur_tree = tree_struct(cur_dev, tree_node.objects.filter(Q(device=cur_dev)))
            print unicode(cur_tree)
            print etree.tostring(cur_tree.get_xml(), pretty_print=True)
            res_node.append(cur_tree.get_xml())
            request.xml_response["result"].append(res_node)
        request.log("build done", xml=True)
    print etree.tostring(request.xml_response.build_response(), pretty_print=True)
    return request.xml_response.create_response()
