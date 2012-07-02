#!/usr/bin/python-init -Ot
# -*- coding: utf-8 -*-

""" device views """

import json
import pprint
import logging_tools
import process_tools
from init.cluster.frontend.helper_functions import init_logging
from init.cluster.frontend.render_tools import render_me
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from init.cluster.backbone.models import device_type, device_group, device, device_class, netdevice, \
     netdevice_speed, network_device_type, network, net_ip, network
from django.core.exceptions import ValidationError
from lxml import etree
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
def device_network(request):
    return render_me(
        request, "device_network.html",
    )()

@login_required
@init_logging
def get_json_tree(request):
    _post = request.POST
    # build list for device_selection -> group lookup
    sel_list = request.session.get("sel_list", [])
    dg_list = device_group.objects.filter(Q(device_group__in=[cur_sel.split("_")[-1] for cur_sel in sel_list if cur_sel.startswith("dev_")])).values_list("pk", flat=True)
    full_tree = device_group.objects.order_by("-cluster_device_group", "name")
    json_struct = []
    for cur_dg in full_tree:
        key = "dg__%d" % (cur_dg.pk)
        cur_jr = {
            "title"    : unicode(cur_dg),
            "isFolder" : True,
            "isLazy"   : True,
            "select"   : key in sel_list,
            "expand"   : cur_dg.pk in dg_list,
            "key"      : key,
            "url"      : reverse("device:get_json_devlist"),
            "data"     : {"dg_idx" : cur_dg.pk},
            "children" : _get_device_list(request, cur_dg.pk) if cur_dg.pk in dg_list else []
        }
        json_struct.append(cur_jr)
    return HttpResponse(json.dumps(json_struct),
                        mimetype="application/json")

def _get_device_list(request, dg_idx):
    cur_devs = device.objects.filter(Q(device_group=dg_idx)).select_related("device_type").order_by("name")
    sel_list = request.session.get("sel_list", [])
    json_struct = []
    for sub_dev in cur_devs:
        if sub_dev.device_type.identifier not in ["MD"]:
            key = "dev__%d" % (sub_dev.pk)
            json_struct.append({
                "title"  : unicode(sub_dev),
                "select" : True if key in sel_list else False,
                "key"    : key
            })
    return json_struct
    
@login_required
@init_logging
def get_json_devlist(request):
    _post = request.POST
    return HttpResponse(json.dumps(_get_device_list(request, _post["dg_idx"])),
                        mimetype="application/json")

def _get_netdevice_list(cur_dev):
    cur_list = E.netdevices()
    for ndev in cur_dev.netdevice_set.all().order_by("devname"):
        cur_list.append(ndev.get_xml())
    return cur_list

@login_required
@init_logging
def get_network_tree(request):
    _post = request.POST
    sel_list = _post.getlist("sel_list[]", [])
    dev_pk_list = [int(entry.split("__")[1]) for entry in sel_list if entry.startswith("dev__")]
    xml_resp = E.response()
    dev_list = E.devices()
    for cur_dev in device.objects.filter(Q(pk__in=dev_pk_list)).select_related(
        "device_group",
        "device_type").prefetch_related("netdevice_set").order_by("device_group__name", "name"):
        dev_list.append(
            E.device(
                _get_netdevice_list(cur_dev),
                name=cur_dev.name,
                pk="%d" % (cur_dev.pk),
                key="dev__%d" % (cur_dev.pk),
            )
        )
    xml_resp.append(dev_list)
    xml_resp.append(E.netspeed_list(
        *[E.netspeed(unicode(cur_ns), pk="%d" % (cur_ns.pk)) for cur_ns in netdevice_speed.objects.all()]))
    xml_resp.append(E.network_device_type_list(
        *[E.network_device_type(unicode(cur_ndt), pk="%d" % (cur_ndt.pk)) for cur_ndt in network_device_type.objects.all()]))
    # networks
    xml_resp.append(E.network_list(
        *[cur_nw.get_xml() for cur_nw in network.objects.all().order_by("name")]
    ))
    # ethtool options
    xml_resp.append(E.ethtool_autoneg_list(
        *[E.ethtool_autoneg(cur_value, pk="%d" % (cur_idx)) for cur_idx, cur_value in enumerate(["default", "on", "off"])]))
    xml_resp.append(E.ethtool_duplex_list(
        *[E.ethtool_duplex(cur_value, pk="%d" % (cur_idx)) for cur_idx, cur_value in enumerate(["default", "on", "off"])]))
    xml_resp.append(E.ethtool_speed_list(
        *[E.ethtool_speed(cur_value, pk="%d" % (cur_idx)) for cur_idx, cur_value in enumerate(["default", "10 Mbit", "100 MBit", "1 GBit", "10 GBit"])]))
    # peers
    xml_resp.append(_get_valid_peers())
    print etree.tostring(xml_resp, pretty_print=True)
    request.xml_response["response"] = xml_resp
    return request.xml_response.create_response()

def _get_valid_peers():
    return E.valid_peers(
        *[E.valid_peer("%s on %s (%s)" % (cur_p.devname, cur_p.device.name, ", ".join([cur_ip.ip for cur_ip in cur_p.net_ip_set.all()])), pk="%d" % (cur_p.pk)) for cur_p in netdevice.objects.filter(Q(routing=True)).order_by("device__name", "devname").prefetch_related("net_ip_set").select_related("device")]
    )

@login_required
@init_logging
def get_xml_tree(request):
    _post = request.POST
    full_tree = device_group.objects.all().prefetch_related("device", "device_group").distinct().order_by("-cluster_device_group", "name")
    xml_resp = E.response()
    for cur_dg in full_tree:
        dev_list = E.devices()
        for cur_d in cur_dg.device_group.all():
            d_el = E.device(
                unicode(cur_d),
                name=cur_d.name,
                comment=cur_d.comment,
                device_type="%d" % (cur_d.device_type_id),
                device_group="%d" % (cur_d.device_group_id),
                idx="%d" % (cur_d.pk),
                key="dev__%d" % (cur_d.pk)
            )
            dev_list.append(d_el)
        dg_el = E.device_group(
            dev_list,
            unicode(cur_dg),
            name=cur_dg.name,
            description=cur_dg.description,
            key="dg__%d" % (cur_dg.pk),
            idx="%d" % (cur_dg.pk),
            is_cdg="1" if cur_dg.cluster_device_group else "0")
        xml_resp.append(dg_el)
    # add device type
    xml_resp.append(
        E.device_types(
            *[E.device_type(name=cur_dt.description,
                            identifier=cur_dt.identifier, idx="%d" % (cur_dt.pk))
              for cur_dt in device_type.objects.all()]
        )
    )
    request.xml_response["response"] = xml_resp
    #request.log("catastrophic error", logging_tools.LOG_LEVEL_ERROR, xml=True)
    return request.xml_response.create_response()

@login_required
@init_logging
def change_xml_entry(request):
    _post = request.POST
    try:
        if _post["id"].count("__") == 2:
            # format object_type, attr_name, object_id, used in device_tree
            object_type, attr_name, object_id = _post["id"].split("__", 2)
        elif _post["id"].count("__") == 3:
            # format object_type, mother_id, object_id, attr_name, used in device_network
            object_type, mother_id, object_id, attr_name = _post["id"].split("__", 3)
        elif _post["id"].count("__") == 5:
            # format mother object_type, dev_id, mother_id, object_type, object_id, attr_name, used in device_network for IPs
            m_object_type, dev_id, mother_id, object_type, object_id, attr_name = _post["id"].split("__", 5)
    except:
        request.log("cannot parse", logging_tools.LOG_LEVEL_ERROR, xml=True)
    else:
        if object_type == "dg":
            mod_obj = device_group
        elif object_type == "dev":
            mod_obj = device
        elif object_type == "nd":
            mod_obj = netdevice
        elif object_type == "ip":
            mod_obj = net_ip
        else:
            request.log("unknown object_type '%s'" % (object_type), logging_tools.LOG_LEVEL_ERROR, xml=True)
            mod_obj = None
        if mod_obj:
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
def create_device_group(request):
    _post = request.POST
    name = _post["name"]
    try:
        new_dg = device_group(name=name,
                              description=_post["description"])
        new_dg.save()
    except:
        request.log("cannot create device_group %s" % (name),
                    logging_tools.LOG_LEVEL_ERROR,
                    xml=True)
        request.log(" - %s" % (process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
    else:
        pass
    return request.xml_response.create_response()

@login_required
@init_logging
def delete_device_group(request):
    pk = request.POST["idx"]
    try:
        device_group.objects.get(Q(pk=pk)).delete()
    except:
        request.log("cannot delete device_group",
                    logging_tools.LOG_LEVEL_ERROR,
                    xml=True)
        request.log(" - %s" % (process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
    return request.xml_response.create_response()

@login_required
@init_logging
def create_device(request):
    _post = request.POST
    range_re = re.compile("^(?P<name>.+)\[(?P<start>\d+)-(?P<end>\d+)\](?P<post>.*)$")
    name = request.POST["name"]
    range_m = range_re.match(name)
    if range_m is None:
        create_list = [name]
    else:
        num_dig = max(len(range_m.group("start")),
                      len(range_m.group("end")))
        start_idx, end_idx = (int(range_m.group("start")),
                              int(range_m.group("end")))
        start_idx, end_idx = (min(start_idx, end_idx),
                              max(start_idx, end_idx))
        start_idx, end_idx = (min(max(start_idx, 1), 1000),
                              min(max(end_idx, 1), 1000))
        request.log("range has %s (%d -> %d)" % (logging_tools.get_plural("digit", num_dig),
                                                 start_idx,
                                                 end_idx))
        form_str = "%s%%0%dd%s" % (range_m.group("name"),
                                   num_dig,
                                   range_m.group("post"))
        create_list = [form_str % (cur_idx) for cur_idx in xrange(start_idx, end_idx + 1)]
    for create_dev in sorted(create_list):
        try:
            new_dev = device(name=create_dev,
                             device_group=device_group.objects.get(Q(pk=_post["group"])),
                             comment=_post["comment"],
                             device_type=device_type.objects.get(Q(pk=_post["type"])),
                             device_class=device_class.objects.get(Q(pk=1)))
            new_dev.save()
        except ValidationError, what:
            request.log("error creating: %s" % (unicode(what.messages[0])), logging_tools.LOG_LEVEL_ERROR, xml=True)
            break
        else:
            pass
    return request.xml_response.create_response()

@login_required
@init_logging
def delete_device(request):
    pk = request.POST["idx"]
    try:
        device.objects.get(Q(pk=pk)).delete()
    except:
        request.log("cannot delete device",
                    logging_tools.LOG_LEVEL_ERROR,
                    xml=True)
        request.log(" - %s" % (process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
    else:
        request.log("deleted device", xml=True)
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
    cur_list = request.session.get("sel_list", [])
    _post = request.POST
    add_flag, add_sel = (int(_post["add"]), _post["key"])
    if add_flag and add_sel not in cur_list:
        cur_list.append(add_sel)
    elif not add_flag and add_sel in cur_list:
        cur_list.remove(add_sel)
    if add_sel.startswith("dg_"):
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
def delete_netdevice(request):
    _post = request.POST
    keys = _post.keys()
    
    dev_pk_key = [key for key in keys if key.startswith("nd_")][0]
    dev_pk, nd_pk = (int(dev_pk_key.split("__")[1]),
                     int(dev_pk_key.split("__")[2]))
    netdevice.objects.get(Q(pk=nd_pk) & Q(device=dev_pk)).delete()
    return request.xml_response.create_response()

@login_required
@init_logging
def create_netdevice(request):
    _post = request.POST
    keys = _post.keys()
    dev_pk = int([key for key in keys if key.startswith("nd__")][0].split("__")[1])
    cur_dev = device.objects.get(Q(pk=dev_pk))
    value_dict = dict([(key.split("__", 2)[2], value) for key, value in _post.iteritems()])
    pprint.pprint(value_dict)
    if "new" in value_dict:
        # new is here used as a prefix, so new__devname is correct and not new_devname (AL, 20120826)
        request.log("create new netdevice for '%s'" % (unicode(cur_dev)))
        copy_dict = dict([(key, value_dict["new__%s" % (key)]) for key in [
            "devname", "driver", "driver_options", "ethtool_autoneg", "macaddr", "fake_macaddr",
            "ethtool_duplex", "ethtool_speed", "vlan_id", "description"] if "new__%s" % (key) in value_dict])
        new_nd = netdevice(device=cur_dev,
                           netdevice_speed=netdevice_speed.objects.get(Q(pk=value_dict["new__netdevice_speed"])),
                           **copy_dict)
        try:
            new_nd.save()
        except ValidationError, what:
            request.log("error creating: %s" % (unicode(what.messages[0])), logging_tools.LOG_LEVEL_ERROR, xml=True)
        except:
            raise
        else:
            request.xml_response["new_netdevice"] = new_nd.get_xml()
    return request.xml_response.create_response()
    
@login_required
@init_logging
def delete_net_ip(request):
    _post = request.POST
    keys = _post.keys()
    main_key = [key for key in keys if key.endswith("__ip")][0]
    net_ip.objects.get(Q(pk=main_key.split("__")[4])).delete()
    return request.xml_response.create_response()

@login_required
@init_logging
def create_net_ip(request):
    _post = request.POST
    keys = _post.keys()
    main_key = [key for key in keys if key.endswith("__new")][0]
    cur_nd = netdevice.objects.get(Q(pk=main_key.split("__")[2]))
    print cur_nd
    value_dict = dict([(key.split("__", 4)[4], value) for key, value in _post.iteritems()])
    pprint.pprint(value_dict)
    if "new" in value_dict:
        request.log("create new net_ip for '%s'" % (unicode(cur_nd)))
        copy_dict = dict([(key, value_dict["new__%s" % (key)]) for key in [
            "ip"] if "new__%s" % (key) in value_dict])
        new_ip = net_ip(netdevice=cur_nd,
                        network=network.objects.get(Q(pk=value_dict["new__network"])),
                        **copy_dict)
        try:
            new_ip.save()
        except ValidationError, what:
            request.log("error creating: %s" % (unicode(what.messages[0])), logging_tools.LOG_LEVEL_ERROR, xml=True)
        except:
            raise
        else:
            request.xml_response["new_net_ip"] = new_ip.get_xml()
    return request.xml_response.create_response()
