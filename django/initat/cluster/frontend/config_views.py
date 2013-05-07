#!/usr/bin/python-init -Ot
# -*- coding: utf-8 -*-

""" config views """

import logging_tools
import process_tools
from initat.cluster.backbone.models import config_type, config, device_group, device, netdevice, \
     net_ip, peer_information, config_str, config_int, config_bool, config_blob, \
     mon_check_command, mon_check_command_type, mon_service_templ, config_script, device_config, \
     tree_node, wc_files, partition_disc, partition, mon_period, mon_contact, mon_service_templ, \
     mon_contactgroup, get_related_models, network_device_type, network_type, get_related_models, \
     mon_check_command_type, mon_service_templ
from django.http import HttpResponse, HttpResponseRedirect
from django.db.models import Q
from django.core.urlresolvers import reverse
from initat.cluster.frontend.helper_functions import init_logging
from initat.core.render import render_me
from django.contrib.auth.decorators import login_required
from lxml import etree
from lxml.builder import E
from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError
import datetime
import tempfile
import pprint
import net_tools
import server_command

@init_logging
@login_required
def show_config_types(request):
    """
    * short test
    """
    if request.method == "GET":
        return render_me(
            request, "cluster_config_type.html",
        )()
    else:
        xml_resp = E.response()
        request.xml_response["response"] = xml_resp
        xml_resp.extend(
            [
                E.config_types(
                    *[cur_ct.get_xml() for cur_ct in config_type.objects.all()]
                    ),
                E.mon_check_command_types(
                    *[cur_mt.get_xml() for cur_mt in mon_check_command_type.objects.all()]
                )
            ]
        )
        return request.xml_response.create_response()

@login_required
@init_logging
def show_configs(request):
    if request.method == "GET":
        return render_me(
            request, "config_overview.html",
        )()
    else:
        _post = request.POST
        mode = _post.get("mode", "full")
        full_mode = mode == "full"
        request.log("get configs, mode is %s" % (mode))
        if full_mode:
            all_configs = config.objects.all().select_related("config_type").prefetch_related(
                "config_int_set",
                "config_str_set",
                "config_bool_set",
                "config_blob_set",
                "config_script_set",
                "mon_check_command_set",
                "device_config_set",
                "device_config_set__device",
                ).order_by("name")
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
        request.log("error modifying: %s" % (unicode(what)), logging_tools.LOG_LEVEL_ERROR, xml=True)
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
    del_obj = config.objects.get(Q(pk=int(val_dict.keys()[0].split("__")[0])))
    delete_object(request, del_obj)
    return request.xml_response.create_response()

def delete_object(request, del_obj):
    num_ref = get_related_models(del_obj)
    if num_ref:
        request.log("cannot delete %s '%s': %s" % (
            del_obj._meta.object_name,
            unicode(del_obj),
            logging_tools.get_plural("reference", num_ref)), logging_tools.LOG_LEVEL_ERROR, xml=True)
    else:
        del_obj.delete()
        request.log("deleted %s" % (del_obj._meta.object_name), xml=True)
    
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
    del_obj = del_obj.objects.get(Q(pk=var_pk))
    delete_object(request, del_obj)
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
    del_cs = config_script.objects.get(Q(pk=del_cs))
    delete_object(request, del_cs)
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
            # check if we can safely set the meta device_config
            set_meta = True
            if len(to_remove):
                if any([True for del_obj in to_remove if get_related_models(del_obj)]):
                    request.log("device configs are in use (hence protected)", logging_tools.LOG_LEVEL_ERROR, xml=True)
                    set_meta = False
                else:
                    to_remove.delete()
                    request.log("removed %s from devices" % (logging_tools.get_plural("config", len(to_remove))))
            # unset all devices except meta_device
            if set_meta:
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
                del_obj = device_config.objects.get(Q(device=cur_dev) & Q(config=cur_conf))
            except device_config.DoesNotExist:
                request.log("meta config already unset")
            else:
                delete_object(request, del_obj)
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
                del_obj = device_config.objects.get(Q(device=cur_dev) & Q(config=cur_conf))
            except device_config.DoesNotExist:
                if meta_dev:
                    # check if meta_device has config_set
                    try:
                        meta_conf = device_config.objects.get(Q(device=meta_dev) & Q(config=cur_conf))
                    except device_config.DoesNotExist:
                        request.log("config already unset and meta config also not set", logging_tools.LOG_LEVEL_ERROR)
                    else:
                        # set config for all devices exclude the meta device and this device
                        if get_related_models(meta_conf):
                            request.log("meta config is in use", logging_tools.LOG_LEVEL_ERROR, xml=True)
                        else:
                            meta_conf.delete()
                            for set_dev in all_devs.exclude(Q(pk=meta_dev.pk)).exclude(Q(pk=cur_dev.pk)):
                                device_config(device=set_dev,
                                              config=cur_conf).save()
                else:
                    request.log("config already unset")
            else:
                delete_object(request, del_obj)
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
    return request.xml_response.create_response()

class tree_struct(object):
    def __init__(self, cur_dev, node_list, node=None, depth=0):
        self.dev_pk = cur_dev.pk
        self.depth = depth
        if not node:
            if node_list:
                self.node = [entry for entry in node_list if not entry.parent_id][0]
            else:
                self.node = None
        else:
            self.node = node
        if self.node is not None:
            self.wc_file = self.node.wc_files
            self.childs = [tree_struct(
                cur_dev,
                node_list,
                node=cur_node,
                depth=self.depth + 1,
                ) for cur_node in sorted(node_list) if cur_node.parent_id == self.node.pk]
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
    result = net_tools.zmq_connection("config_webfrontend", timeout=30).add_connection("tcp://localhost:8005", srv_com)
    if not result:
        request.log("error contacting server", logging_tools.LOG_LEVEL_ERROR, xml=True)
    else:
        request.xml_response["result"] = E.devices()
        for dev_node in result.xpath(None, ".//ns:device"):
            res_node = E.device(dev_node.text, **dev_node.attrib)
            if int(dev_node.attrib["state_level"]) < logging_tools.LOG_LEVEL_ERROR:
                #if int(dev_node.attrib["state_level"]) == logging_tools.LOG_LEVEL_OK or True:
                cur_dev = dev_dict[int(dev_node.attrib["pk"])]
                # build tree
                cur_tree = tree_struct(cur_dev, tree_node.objects.filter(Q(device=cur_dev)).select_related("wc_files"))
                res_node.append(cur_tree.get_xml())
            request.xml_response["result"].append(res_node)
        request.log("build done", xml=True)
    #print etree.tostring(request.xml_response.build_response(), pretty_print=True)
    return request.xml_response.create_response()

@login_required
@init_logging
def download_hash(request):
    _post = request.POST
    conf_ids = [int(value) for value in _post.getlist("config_ids[]")]
    request.log("got download request for %s: %s" % (
        logging_tools.get_plural("config", len(conf_ids)),
        ", ".join(["%d" % (val) for val in sorted(conf_ids)])))
    hash_value = "QQ".join(["%d" % (conf_id) for conf_id in conf_ids])
    request.xml_response["download_link"] = reverse("config:download_configs", args=[hash_value])
    return request.xml_response.create_response()

@login_required
@init_logging
def download_configs(request, **kwargs):
    conf_ids = [int(value) for value in kwargs["hash"].split("QQ")]
    request.log("got download request for %s: %s" % (
        logging_tools.get_plural("config", len(conf_ids)),
        ", ".join(["%d" % (val) for val in sorted(conf_ids)])))
    res_xml = E.configuration()
    configs = E.configs()
    res_xml.append(configs)
    conf_list = config.objects.filter(Q(pk__in=conf_ids)).prefetch_related(
        "config_type",
        "config_str_set",
        "config_int_set",
        "config_bool_set",
        "config_blob_set",
        "mon_check_command_set",
        "config_script_set")
    for cur_conf in conf_list:
        cur_xml = cur_conf.get_xml()
        cur_xml.append(cur_conf.config_type.get_xml())
        configs.append(cur_xml)
    # remove all pks and keys
    for pk_el in res_xml.xpath(".//*[@pk]"):
        del pk_el.attrib["pk"]
        del pk_el.attrib["key"]
    # remove attributes from config
    for pk_el in res_xml.xpath(".//config"):
        for del_attr in ["parent_config", "num_device_configs", "device_list", "config_type"]:
            if del_attr in pk_el.attrib:
                del pk_el.attrib[del_attr]
    act_resp = HttpResponse(etree.tostring(res_xml, pretty_print=True),
                            mimetype="application/xml")
    act_resp["Content-disposition"] = "attachment; filename=config_%s.xml" % (datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
    return act_resp

@login_required
@init_logging
def upload_config(request):
    try:
        default_mct = mon_check_command_type.objects.all()[0]
    except:
        default_mct = None
    try:
        default_mst = mon_service_templ.objects.all()[0]
    except:
        default_mst = None
    try:
        conf_xml = etree.fromstring(request.FILES["config"].read())
    except:
        request.log("cannot interpret upload file: %s" % (process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
    else:
        for cur_conf in conf_xml.xpath(".//config"):
            # check config_type
            conf_type = cur_conf.find("config_type")
            try:
                cur_ct = config_type.objects.get(Q(name=conf_type.attrib["name"]))
            except config_type.DoesNotExist:
                cur_ct = config_type(**conf_type.attrib)
                request.log("creating new config_type '%s'" % (unicode(cur_ct)))
                cur_ct.save()
            try:
                new_conf = config.objects.get(Q(name=cur_conf.attrib["name"]))
            except config.DoesNotExist:
                new_conf = config(config_type=cur_ct, **cur_conf.attrib)
                new_conf.create_default_entries = False
                new_conf.save()
                request.log("creating new config '%s'" % (unicode(new_conf)))
                for new_obj in cur_conf.xpath(".//config_str|.//config_int|.//config_bool|.//config_blob|.//mon_check_command|.//config_script"):
                    if "type" in new_obj.attrib:
                        new_sub_obj = globals()["config_%s" % (new_obj.attrib["type"])]
                    else:
                        new_sub_obj = globals()[new_obj.tag]
                    for del_attr in ["config", "type", "mon_check_command_type", "mon_service_templ"]:
                        if del_attr in new_obj.attrib:
                            del new_obj.attrib[del_attr]
                    new_sub_obj = new_sub_obj(config=new_conf, **new_obj.attrib)
                    request.log(
                        "creating new %s (value '%s') named %s" % (
                            new_sub_obj._meta.object_name,
                            unicode(new_sub_obj),
                            new_sub_obj.name,
                        )
                    )
                    if new_obj.tag == "mon_check_command":
                        new_sub_obj.mon_check_command_type = default_mct
                        new_sub_obj.mon_service_templ = default_mst
                    new_sub_obj.save()
    return HttpResponseRedirect(reverse("config:show_configs"))
    