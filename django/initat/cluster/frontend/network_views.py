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
     netdevice_speed, device_variable, device_group, route_generation, to_system_tz
import server_command
import net_tools
import ipvx_tools
import time

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
                *[cur_nw.get_xml(add_ip_info=True) for cur_nw in network.objects.all()]
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
        "device_type").prefetch_related(
            "netdevice_set",
            "netdevice_set__net_ip_set").order_by("device_group__name", "name"):
        dev_list.append(cur_dev.get_xml())
    # now handled via fixtures
    xml_resp.extend(
        [
            dev_list,
            E.netdevice_speeds(
                *[cur_ns.get_xml() for cur_ns in netdevice_speed.objects.all()]),
            E.network_device_type_list(
                *[E.network_device_type(unicode(cur_ndt), pk="%d" % (cur_ndt.pk)) for cur_ndt in network_device_type.objects.all()]),
            # networks
            E.network_list(
                *[cur_nw.get_xml() for cur_nw in network.objects.all().select_related("network_type").prefetch_related("network_device_type").order_by("name")]
            ),
            # ethtool options
            E.ethtool_autoneg_list(
                *[E.ethtool_autoneg(cur_value, pk="%d" % (cur_idx)) for cur_idx, cur_value in enumerate(["default", "on", "off"])]),
            E.ethtool_duplex_list(
                *[E.ethtool_duplex(cur_value, pk="%d" % (cur_idx)) for cur_idx, cur_value in enumerate(["default", "on", "off"])]),
            E.ethtool_speed_list(
                *[E.ethtool_speed(cur_value, pk="%d" % (cur_idx)) for cur_idx, cur_value in enumerate(["default", "10 Mbit", "100 MBit", "1 GBit", "10 GBit"])]),
            # peers,
            _get_valid_peers()
        ]
    )
    #print etree.tostring(xml_resp, pretty_print=True)
    request.xml_response["response"] = xml_resp
    return request.xml_response.create_response()

def _get_hopcount_state(request):
    rebuild_possible = False
    xml_resp = E.hopcount_state()
    valid_routes = []#route_generation.objects.filter(Q(valid=True))
    if len(valid_routes) == 1:
        valid_route = valid_routes[0]
        route_info = "gen #%d, built %s, %d/%d" % (
            valid_route.generation,
            logging_tools.get_relative_dt(to_system_tz(valid_route.date)),
            valid_route.num_hops,
            valid_route.num_dups,
        )
        if valid_route.dirty:
            xml_resp.attrib["routing_info"] = "dirty route found (%s)" % (
                route_info,
            )
            enable_rebuild = True
        else:
            xml_resp.attrib["routing_info"] = "valid route found (%s)" % (
                route_info,
            )
            enable_rebuild = False
    elif not len(valid_routes):
        xml_resp.attrib["routing_info"] = "no valid routes found"
        enable_rebuild = True
    else:
        xml_resp.attrib["routing_info"] = "more then one (%d) valid routes found" % (len(valid_routes))
        enable_rebuild = True
    xml_resp.attrib["enable_rebuild"] = "1" if enable_rebuild else "0"
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
    routing_nds = netdevice.objects.filter(Q(routing=True)).order_by(
        "device__name",
        "devname").prefetch_related("net_ip_set").select_related("device")
    peer_dict = dict([(cur_nd.pk, 0) for cur_nd in routing_nds])
    for s_nd, d_nd in peer_information.objects.all().values_list("s_netdevice", "d_netdevice"):
        if s_nd in peer_dict:
            peer_dict[s_nd] += 1
        if d_nd in peer_dict:
            peer_dict[d_nd] += 1
    return E.valid_peers(
        *[E.valid_peer("%s [%s, pen %d] on %s (%s)" % (
            cur_p.devname,
            logging_tools.get_plural("peer", peer_dict.get(cur_p.pk, 0)),
            cur_p.penalty or 1,
            cur_p.device.name,
            ", ".join([cur_ip.ip for cur_ip in cur_p.net_ip_set.all()]) or "no IPs"), pk="%d" % (cur_p.pk))
          for cur_p in routing_nds]
    )

@login_required
@init_logging
def get_valid_peers(request):
    request.xml_response["valid_peers"] = _get_valid_peers()
    return request.xml_response.create_response()

@login_required
@init_logging
def copy_network(request):
    _post = request.POST
    source_dev = device.objects.get(Q(pk=_post["source_dev"]))
    target_devs = device.objects.exclude(Q(pk=source_dev.pk)).filter(Q(pk__in=[value.split("__")[1] for value in _post.getlist("all_devs[]") if value.startswith("dev__")])).prefetch_related(
        "netdevice_set",
        "netdevice_set__netdevice_speed",
        "netdevice_set__network_device_type",
        "netdevice_set__net_ip_set",
        "netdevice_set__net_ip_set__network",
        "netdevice_set__net_ip_set__network__network_type").order_by("name")
    if len(target_devs):
        diff_ip = ipvx_tools.ipv4("0.0.0.1")
        request.log("source device is %s" % (unicode(source_dev)))
        request.log("%s: %s" % (logging_tools.get_plural("target device", len(target_devs)),
                                ", ".join([unicode(cur_dev) for cur_dev in target_devs])))
        # read peer_informations
        src_nds = source_dev.netdevice_set.all().values_list("pk", flat=True)
        peer_dict = {}
        for peer_info in peer_information.objects.filter(Q(s_netdevice__in=src_nds) | Q(d_netdevice__in=src_nds)):
            s_local, d_local = (peer_info.s_netdevice_id in src_nds,
                                peer_info.d_netdevice_id in src_nds)
            print "*", s_local, d_local
            if s_local and d_local:
                if peer_info.s_netdevice_id != peer_info.d_netdevice_id:
                    request.log("host peering detection, not handled", logging_tools.LOG_LEVEL_CRITICAL)
                else:
                    peer_dict.setdefault(peer_info.s_netdevice_id, []).append((None, peer_info.penalty))
            elif s_local:
                peer_dict.setdefault(peer_info.s_netdevice_id, []).append((peer_info.d_netdevice, peer_info.penalty))
            else:
                peer_dict.setdefault(peer_info.d_netdevice_id, []).append((peer_info.s_netdevice, peer_info.penalty))
        for target_num, target_dev in enumerate(target_devs):
            offset = target_num + 1
            request.log("operating on %s, offset is %d" % (unicode(target_dev), offset))
            if target_dev.bootnetdevice_id:
                request.log("removing bootnetdevice %s" % (unicode(target_dev.bootnetdevice)))
                target_dev.bootnetdevice = None
                target_dev.save()
            # preserve mac/fakemac addresses
            mac_dict, fmac_dict = ({}, {})
            for cur_nd in target_dev.netdevice_set.all():
                if int(cur_nd.macaddr.replace(":", ""), 16):
                    mac_dict[cur_nd.devname] = cur_nd.macaddr
                if int(cur_nd.fake_macaddr.replace(":", ""), 16):
                    fmac_dict[cur_nd.devname] = cur_nd.fake_macaddr
                # remove all netdevices
                cur_nd.delete()
            # copy from source
            for cur_nd in source_dev.netdevice_set.all().prefetch_related(
                "netdevice_speed",
                "network_device_type",
                "net_ip_set",
                "net_ip_set__network",
                "net_ip_set__network__network_type"):
                new_nd = cur_nd.copy()
                if new_nd.devname in mac_dict:
                    new_nd.macaddr = mac_dict[new_nd.devname]
                if new_nd.devname in fmac_dict:
                    new_nd.fake_macaddr = fmac_dict[new_nd.devname]
                new_nd.device = target_dev
                new_nd.save()
                for cur_ip in cur_nd.net_ip_set.all().prefetch_related(
                    "network",
                    "network__network_type"):
                    new_ip = cur_ip.copy()
                    new_ip.netdevice = new_nd
                    if cur_ip.network.network_type.identifier != "l":
                        # increase IP for non-loopback addresses
                        ip_val = ipvx_tools.ipv4(cur_ip.ip)
                        for seq in xrange(offset):
                            ip_val += diff_ip
                        new_ip.ip = str(ip_val)
                    new_ip.save()
                # peering
                if cur_nd.pk in peer_dict:
                    for target_nd, penalty in peer_dict[cur_nd.pk]:
                        if target_nd == None:
                            # local peer
                            peer_information(
                                s_netdevice=new_nd,
                                d_netdevice=new_nd,
                                penalty=penalty).save()
                        else:
                            # remote peer
                            peer_information(
                                s_netdevice=new_nd,
                                d_netdevice=target_nd,
                                penalty=penalty).save()
        request.log("copied network settings", xml=True)
    else:
        request.log("no target_devices", logging_tools.LOG_LEVEL_WARN, xml=True)
    return request.xml_response.create_response()
    