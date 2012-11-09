#!/usr/bin/python-init -Ot
# -*- coding: utf-8 -*-

""" network views """

import json
import pprint
import logging_tools
import process_tools
from initat.cluster.frontend.helper_functions import init_logging
from initat.core.render import render_me
from django.contrib.auth.decorators import login_required
from lxml import etree
from lxml.builder import E
from django.db.models import Q
from django.core.exceptions import ValidationError
from initat.cluster.backbone.models import device, network, net_ip, \
     network_type, network_device_type, netdevice, peer_information, \
     netdevice_speed, device_variable, device_group
import server_command
import net_tools

@login_required
@init_logging
def device_network(request):
    return render_me(
        request, "device_network.html",
    )()

@init_logging
@login_required
def show_network_d_types(request):
    if request.method == "GET":
        return render_me(request, "cluster_network_types.html")()
    else:
        xml_resp = E.response()
        request.xml_response["response"] = xml_resp
        xml_resp.append(E.network_types(
            *[cur_nwt.get_xml() for cur_nwt in network_type.objects.all()]))
        xml_resp.append(E.network_device_types(
            *[cur_nwdt.get_xml() for cur_nwdt in network_device_type.objects.all()]))
        xml_resp.append(E.network_type_choices(
            *[E.network_type_choice(long_info, pk="%s" % (short_info)) for short_info, long_info in network_type._meta.get_field_by_name("identifier")[0].choices]))
        return request.xml_response.create_response()

@init_logging
@login_required
def show_cluster_networks(request):
    if request.method == "GET":
        return render_me(request, "cluster_networks.html")()
    else:
        xml_resp = E.response(
            E.networks(
                *[cur_nw.get_xml() for cur_nw in network.objects.all()]
                ),
            E.network_types(
                *[cur_nwt.get_xml() for cur_nwt in network_type.objects.all()]
                ),
            E.network_device_types(
                *[cur_nwdt.get_xml() for cur_nwdt in network_device_type.objects.all()]
            )
        )
        request.xml_response["response"] = xml_resp
        return request.xml_response.create_response()

@login_required
@init_logging
def delete_netdevice(request):
    _post = request.POST
    keys = _post.keys()
    dev_pk_key = [key for key in keys if key.startswith("nd_")][0]
    dev_pk, nd_pk = (int(dev_pk_key.split("__")[1]),
                     int(dev_pk_key.split("__")[2]))
    removed_peers = peer_information.objects.filter(Q(s_netdevice=nd_pk) | Q(d_netdevice=nd_pk))
    request.xml_response["removed_peers"] = E.peers(*[rem_peer.get_xml() for rem_peer in removed_peers])
    nd_dev = device.objects.get(Q(pk=dev_pk))
    if nd_dev.bootnetdevice_id == nd_pk:
        nd_dev.bootnetdevice = None
        nd_dev.save()
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
    value_dict = dict([(key.split("__", 4)[4], value) for key, value in _post.iteritems()])
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

@login_required
@init_logging
def create_new_peer(request):
    _post = request.POST
    s_netdevice=netdevice.objects.get(Q(pk=_post["id"].split("__")[2]))
    d_netdevice=netdevice.objects.get(Q(pk=_post["new_peer"]))
    try:
        cur_peer = peer_information.objects.get(
            (Q(s_netdevice=s_netdevice.pk) & Q(d_netdevice=d_netdevice.pk)) |
            (Q(s_netdevice=d_netdevice.pk) & Q(d_netdevice=s_netdevice.pk)))
    except peer_information.DoesNotExist:
        new_peer = peer_information(
            s_netdevice=s_netdevice,
            d_netdevice=d_netdevice,
            penalty=_post["penalty"])
        try:
            new_peer.save()
        except ValidationError, what:
            request.log("error creating new peer: %s" % (unicode(what.messages[0])), logging_tools.LOG_LEVEL_ERROR, xml=True)
        else:
            request.log("created new peer", xml=True)
            request.xml_response["new_peer_information"] = new_peer.get_xml()
    except peer_information.MultipleObjectsReturned:
        request.log("peer already exists", logging_tools.LOG_LEVEL_ERROR, xml=True)
    else:
        request.log("peer already exists", logging_tools.LOG_LEVEL_ERROR, xml=True)
    return request.xml_response.create_response()

@login_required
@init_logging
def delete_peer(request):
    _post = request.POST
    peer_information.objects.get(Q(pk=_post["id"].split("__")[-1])).delete()
    return request.xml_response.create_response()

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
        "device_type").prefetch_related("netdevice_set", "netdevice_set__net_ip_set").order_by("device_group__name", "name"):
        dev_list.append(cur_dev.get_xml())
    xml_resp.append(dev_list)
    ns_list = E.netspeed_list(
        *[E.netspeed(unicode(cur_ns), pk="%d" % (cur_ns.pk)) for cur_ns in netdevice_speed.objects.all()])
    if not len(ns_list):
        # create some dummy entries
        netdevice_speed(
            speed_bps=1000000000,
            check_via_ethtool=True,
            full_duplex=True).save()
        ns_list = E.netspeed_list(
            *[E.netspeed(unicode(cur_ns), pk="%d" % (cur_ns.pk)) for cur_ns in netdevice_speed.objects.all()])
    xml_resp.append(ns_list)
    xml_resp.append(E.network_device_type_list(
        *[E.network_device_type(unicode(cur_ndt), pk="%d" % (cur_ndt.pk)) for cur_ndt in network_device_type.objects.all()]))
    # networks
    xml_resp.append(E.network_list(
        *[cur_nw.get_xml() for cur_nw in network.objects.all().select_related("network_type").order_by("name")]
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

def _get_hopcount_state(request):
    rebuild_possible = False
    xml_resp = E.hopcount_state()
    # hopcount info
    try:
        reb_var = device_variable.objects.get(Q(name="hopcount_table_build_time") & Q(device__device_group__cluster_device_group=True))
    except device_variable.DoesNotExist:
        try:
            state_var = device_variable.objects.get(Q(name="hopcount_state_var") & Q(device__device_group__cluster_device_group=True))
        except:
            xml_resp.attrib["rebuild_info"] = "never built"
            rebuild_possible = True
        else:
            xml_resp.attrib["rebuild_info"] = "rebuilding, %d %% done" % (state_var.val_int)
    else:
        xml_resp.attrib["rebuild_info"] = "built %s" % (logging_tools.get_relative_dt(reb_var.val_date))
        rebuild_possible = True
    request.xml_response["response"] = xml_resp
    return rebuild_possible
    
@login_required
@init_logging
def get_hopcount_state(request):
    _get_hopcount_state(request)
    return request.xml_response.create_response()
    
@login_required
@init_logging
def rebuild_hopcount(request):
    if _get_hopcount_state(request):
        srv_com = server_command.srv_command(command="rebuild_hopcount")
        result = net_tools.zmq_connection("blabla", timeout=2).add_connection("tcp://localhost:8004", srv_com)
        if not result:
            request.log("error contacting server", logging_tools.LOG_LEVEL_ERROR, xml=True)
        else:
            request.log("started hopcount rebuild", xml=True)
    return request.xml_response.create_response()

def _get_valid_peers():
    return E.valid_peers(
        *[E.valid_peer("%s [%d] on %s (%s)" % (
            cur_p.devname,
            cur_p.penalty or 1,
            cur_p.device.name,
            ", ".join([cur_ip.ip for cur_ip in cur_p.net_ip_set.all()]) or "no IPs"), pk="%d" % (cur_p.pk))
          for cur_p in netdevice.objects.filter(Q(routing=True)).order_by("device__name", "devname").prefetch_related("net_ip_set").select_related("device")]
    )

@login_required
@init_logging
def get_valid_peers(request):
    request.xml_response["valid_peers"] = _get_valid_peers()
    return request.xml_response.create_response()

