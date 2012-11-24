#!/usr/bin/python-init -Ot
# -*- coding: utf-8 -*-

""" device views """

import json
import pprint
import logging_tools
import process_tools
from initat.cluster.frontend.helper_functions import init_logging
from initat.core.render import render_me
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from initat.cluster.backbone.models import device_type, device_group, device, device_class, \
     mon_device_templ, mon_ext_host, cd_connection, package_device_connection
from django.core.exceptions import ValidationError
from lxml import etree
import config_tools
from lxml.builder import E
from django.db.models import Q
import re
import time
from django.core.urlresolvers import reverse

@login_required
@init_logging
def device_tree(request):
    return render_me(request ,"device_tree.html", hide_sidebar=True)()

@login_required
@init_logging
def get_json_tree(request):
    _post = request.POST
    # build list for device_selection -> group lookup
    sel_list = request.session.get("sel_list", [])
    dg_list = device_group.objects.filter(Q(device_group__in=[cur_sel.split("_")[-1] for cur_sel in sel_list if cur_sel.startswith("dev_")])).values_list("pk", flat=True)
    full_tree = device_group.objects.prefetch_related("device_group", "device_group__device_type").order_by("-cluster_device_group", "name")
    json_struct = []
    for cur_dg in full_tree:
        key = "devg__%d" % (cur_dg.pk)
        cur_jr = {
            "title"    : unicode(cur_dg),
            "isFolder" : True,
            "isLazy"   : False,
            "select"   : key in sel_list,
            "expand"   : cur_dg.pk in dg_list,
            "key"      : key,
            "data"     : {"devg_pk" : cur_dg.pk},
            "children" : _get_device_list(request, cur_dg)
        }
        json_struct.append(cur_jr)
    return HttpResponse(json.dumps(json_struct),
                        mimetype="application/json")

def _get_device_list(request, cur_dg):
    cur_devs = cur_dg.device_group.all()
    sel_list = request.session.get("sel_list", [])
    json_struct = []
    for sub_dev in cur_devs:
        if sub_dev.device_type.identifier not in ["MD"]:
            key = "dev__%d" % (sub_dev.pk)
            json_struct.append({
                "title"  : "%s (%s%s)" % (unicode(sub_dev.name),
                                          sub_dev.device_type.identifier,
                                          ", %s" % (sub_dev.comment) if sub_dev.comment else ""),
                "select" : True if key in sel_list else False,
                "key"    : key
            })
    return json_struct

@login_required
@init_logging
def get_xml_tree(request):
    _post = request.POST
    full_tree = device_group.objects.all().prefetch_related("device", "device_group").distinct().order_by("-cluster_device_group", "name")
    xml_resp = E.response()
    for cur_dg in full_tree:
        xml_resp.append(cur_dg.get_xml(with_devices=True))
    # add device type
    xml_resp.append(
        E.device_types(
            *[E.device_type(name=cur_dt.description,
                            identifier=cur_dt.identifier, pk="%d" % (cur_dt.pk))
              for cur_dt in device_type.objects.all()]
        )
    )
    # add mother server(s)
    all_mothers = config_tools.device_with_config("mother_server").get("mother_server", [])
    xml_resp.append(
        E.mother_servers(
            *[E.mother_server(unicode(mother_server.effective_device), pk="%d" % (mother_server.effective_device.pk)) for mother_server in all_mothers])
    )
    request.xml_response["response"] = xml_resp
    #request.log("catastrophic error", logging_tools.LOG_LEVEL_ERROR, xml=True)
    return request.xml_response.create_response()

@login_required
@init_logging
def clear_selection(request):
    request.session["sel_list"] = []
    request.session.save()
    return request.xml_response.create_response()
    
@login_required
@init_logging
def add_selection(request):
    _post = request.POST
    if "key" in _post:
        # single set / delete
        add_flag, add_sel_list, cur_list = (
            int(_post["add"]),
            [_post["key"]],
            request.session.get("sel_list", []))
    else:
        # total set / delete
        add_flag, add_sel_list, cur_list = (
            1,
            _post.getlist("key[]"),
            []
        )
    for add_sel in add_sel_list:
        if add_flag and add_sel not in cur_list:
            cur_list.append(add_sel)
        elif not add_flag and add_sel in cur_list:
            cur_list.remove(add_sel)
        if add_sel.startswith("devg_"):
            # emulate toggle of device_group
            request.log("toggle selection of device_group %d" % (int(add_sel.split("__")[1])))
            toggle_devs = ["dev__%d" % (cur_pk) for cur_pk in device.objects.filter(Q(device_group=add_sel.split("__")[1])).values_list("pk", flat=True)]
            for toggle_dev in toggle_devs:
                if toggle_dev in cur_list:
                    cur_list.remove(toggle_dev)
                else:
                    cur_list.append(toggle_dev)
    request.session["sel_list"] = cur_list
    request.session.save()
    request.log("%s in list" % (logging_tools.get_plural("selection", len(cur_list))))
    return request.xml_response.create_response()

@login_required
@init_logging
def show_configs(request):
    return render_me(
        request, "device_configs.html",
    )()

@login_required
@init_logging
def get_group_tree(request):
    _post = request.POST
    ignore_md = True if int(_post.get("ignore_meta_devices", 0)) else False
    # also possible via _post.getlist("sel_list", []) ?
    sel_list = _post.getlist("sel_list[]", [])#request.session.get("sel_list", [])
    sel_pks = [int(value.split("__")[1]) for value in sel_list]
    xml_resp = E.device_groups()
    all_dgs = device_group.objects.exclude(Q(cluster_device_group=True)).prefetch_related("device_group").order_by("name")
    meta_dev_type_id = device_type.objects.get(Q(identifier="MD")).pk
    # only devices are transfered with the selected attribute
    for cur_dg in all_dgs:
        cur_xml = cur_dg.get_xml(full=False)
        any_sel = False
##        if cur_xml.attrib["key"] in sel_list:
##            cur_xml.attrib["selected"] = "selected"
##            any_sel = True
        for cur_dev in cur_xml.find("devices"):
            if ignore_md and int(cur_dev.attrib["device_type"]) == meta_dev_type_id:
                cur_dev.getparent().remove(cur_dev)
            else:
                cur_dev.attrib["meta_device"] = "1" if int(cur_dev.attrib["device_type"]) == meta_dev_type_id else "0"
                if cur_dev.attrib["key"] in sel_list or cur_xml.attrib["key"] in sel_list:
                    cur_dev.attrib["selected"] = "selected"
                    any_sel = True
        if any_sel:
            xml_resp.append(cur_xml)
    extra_re = re.compile("^extra_t(\d+)$")
    for extra_key in [key for key in _post.keys() if extra_re.match(key)]:
        extra_name = _post[extra_key]
        device_filter = True if "%s_device" % (extra_key) in _post else False
        kwargs = {"mon_ext_host" : {"with_images" : True}}.get(extra_name, {})
        select_rel_dict = {"cd_connection" : ["parent", "child"]}
        request.log("adding extra data %s (device filter : %s)" % (extra_name,
                                                                   str(device_filter)))
        extra_obj = globals()[extra_name]
        if device_filter:
            obj_list = extra_obj.objects.filter(Q(device__in=sel_pks))
        else:
            obj_list = extra_obj.objects.all()
        extra_list = getattr(E, "%ss" % (extra_name))(
            *[cur_obj.get_xml(**kwargs) for cur_obj in obj_list.select_related(*select_rel_dict.get(extra_name, []))]
        )
        xml_resp.append(extra_list)
    request.xml_response["response"] = xml_resp
    #print etree.tostring(xml_resp, pretty_print=True)
    return request.xml_response.create_response()

@init_logging
@login_required
def connections(request):
    if request.method == "GET":
        return render_me(request, "device_connections.html")()
    else:
        return request.xml_response.create_response()

@init_logging
@login_required
def create_connection(request):
    _post = request.POST
    drag_dev, target_dev = (
        device.objects.get(Q(pk=_post["drag_id"].split("__")[1])),
        device.objects.get(Q(pk=_post["target"].split("__")[1])))
    t_type = _post["target_type"]
    request.log("dragged '%s' over '%s' (field %s)" % (
        unicode(drag_dev),
        unicode(target_dev),
        t_type))
    new_cd = cd_connection(
        parent=target_dev if t_type == "master" else drag_dev,
        child=drag_dev if t_type=="master" else target_dev,
        created_by=request.session["db_user"],
        connection_info="webfrontend")
    try:
        new_cd.save()
    except ValidationError, what:
        request.log("error creating: %s" % (unicode(what.messages[0])), logging_tools.LOG_LEVEL_ERROR, xml=True)
    else:
        request.log("added connection", xml=True)
        request.xml_response["new_connection"] = new_cd.get_xml()
    return request.xml_response.create_response()

@init_logging
@login_required
def delete_connection(request):
    _post = request.POST
    del_pk = _post["pk"]
    del_con = cd_connection.objects.get(Q(pk=del_pk))
    request.log("removing %s" % (unicode(del_con)), xml=True)
    del_con.delete()
    return request.xml_response.create_response()

@init_logging
@login_required
def manual_connection(request):
    _post = request.POST
    re_dict = {"drag"   : _post["source"],
               "target" : _post["target"]}
    t_type = _post["mode"]
    request.log("mode is '%s', drag_str is '%s', target_str is '%s'" % (
        t_type,
        re_dict["drag"],
        re_dict["target"]))
    # # (hash) is our magic sign for \d
    for key in re_dict.keys():
        val = re_dict[key]
        if val.count("#"):
            parts = val.split("#")
            val = "(%s)(%s)(%s)" % (parts[0], "#" * (len(parts) - 1), parts[-1])
            val = val.replace("#", "\d")
        re_dict[key] = re.compile("^%s$" % (val))
    # all cd / non-cd devices
    cd_devices = device.objects.filter(Q(device_type__identifier='CD'))
    non_cd_devices = device.objects.exclude(Q(device_type__identifier='CD'))
    # iterate over non-cd-device
    #pprint.pprint(re_dict)
    match_dict = {}
    for key, dev_list in [("drag", non_cd_devices),
                          ("target", cd_devices)]:
        match_dict[key] = {}
        for cur_dev in dev_list:
            cur_m = re_dict[key].match(cur_dev.name)
            if cur_m and cur_m.groups():
                d_key = cur_m.groups()[1]
                if d_key.isdigit():
                    d_key = int(d_key)
                match_dict[key][d_key] = (cur_m.groups(), cur_dev)
    # matching keys
    m_keys = set(match_dict["drag"].keys()) & set(match_dict["target"].keys())
    request.log("%s: %s" % (logging_tools.get_plural("matching key", len(m_keys)),
                            ", ".join(sorted([str(key) for key in m_keys]))))
    created_cons = []
    for m_key in m_keys:
        new_cd = cd_connection(
            parent=match_dict["target" if t_type == "slave" else "drag"][m_key][1],
            child=match_dict["drag" if t_type == "slave" else "target"][m_key][1],
            created_by=request.session["db_user"],
            connection_info="manual")
        try:
            new_cd.save()
        except ValidationError, what:
            request.log("error creating: %s" % (unicode(what.messages[0])), logging_tools.LOG_LEVEL_ERROR, xml=True)
            for del_cd in created_cons:
                del_cd.delete()
        else:
            created_cons.append(new_cd)
    if m_keys:
        if created_cons:
            request.log("created %s" % (logging_tools.get_plural("connection", len(m_keys))), xml=True)
    else:
        request.log("found no matching devices", logging_tools.LOG_LEVEL_WARN, xml=True)
    #print drag_str.replace("#", "\d")
    #drag_re = re.compile(re_fstr % (drag_str.replace("#", "\d")))
    #target_re = re.compile(re_fstr % (target_str.replace("#", "\d")))
    #pprint.pprint(_post)
    return request.xml_response.create_response()
