#!/usr/bin/python-init -Ot
# -*- coding: utf-8 -*-
#
# Copyright (C) 2013,2014 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of webfrontend
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#

""" network views """

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from django.db.models import Q
from django.http import HttpResponse, HttpResponseRedirect
from django.utils.decorators import method_decorator
from django.views.generic import View
from initat.cluster.backbone.models import device, network, net_ip, \
    network_type, network_device_type, netdevice, peer_information, \
    netdevice_speed, domain_tree_node, domain_name_tree, get_related_models
from initat.cluster.frontend.forms import domain_tree_node_form, network_form, \
    network_type_form, network_device_type_form
from initat.cluster.frontend.helper_functions import xml_wrapper
from initat.core.render import render_me, render_string
from lxml.builder import E # @UnresolvedImports
from networkx.readwrite import json_graph
import config_tools
import ipvx_tools
import logging
import logging_tools
import process_tools

logger = logging.getLogger("cluster.network")

def cleanup_tree(in_xml, attr_dict):
    # experimental stuff, not needed right now
    # add standard keys
    for key, value in attr_dict.iteritems():
        value |= set(["key", "pk", "name"])
    for cur_node in in_xml.xpath(".//*"):
        if cur_node.tag in attr_dict:
            for del_key in [key for key in cur_node.attrib.iterkeys() if key not in attr_dict[cur_node.tag]]:
                del cur_node.attrib[del_key]

class device_network(View):
    @method_decorator(login_required)
    def get(self, request):
        return render_me(
            request, "device_network.html",
        )()
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        sel_list = _post.getlist("sel_list[]", [])
        dev_pk_list = [int(entry.split("__")[1]) for entry in sel_list if entry.startswith("dev__")]
        xml_resp = E.response()
        dev_list = E.devices()
        for cur_dev in device.objects.filter(Q(pk__in=dev_pk_list)).select_related(
            "device_group",
            "domain_tree_node",
            "device_type").prefetch_related(
                "netdevice_set",
                "categories",
                "netdevice_set__net_ip_set").order_by("device_group__name", "name"):
            dev_list.append(cur_dev.get_xml(full_name=True))
        dnt_struct = domain_name_tree()
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
                _get_valid_peers(),
                dnt_struct.get_xml(),
            ]
        )
        # print etree.tostring(xml_resp, pretty_print=True)
        request.xml_response["response"] = xml_resp

class show_cluster_networks(View):
    @method_decorator(login_required)
    def get(self, request):
        return render_me(request, "cluster_networks.html", {
            "network_form" : network_form(),
            "network_device_type_form" : network_device_type_form(),
            "network_type_form" : network_type_form(),
            })()

class delete_netdevice(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        keys = _post.keys()
        dev_pk_key = [key for key in keys if key.startswith("nd_")][0]
        dev_pk, nd_pk = (int(dev_pk_key.split("__")[1]),
                         int(dev_pk_key.split("__")[2]))
        removed_peers = peer_information.objects.filter(Q(s_netdevice=nd_pk) | Q(d_netdevice=nd_pk))
        request.xml_response["removed_peers"] = E.peers(*[rem_peer.get_xml() for rem_peer in removed_peers])
        nd_dev = device.objects.get(Q(pk=dev_pk))
        to_del = netdevice.objects.get(Q(pk=nd_pk) & Q(device=dev_pk))
        for vlan_slave in to_del.vlan_slaves.all():
            # unseet master for vlan_slaves
            vlan_slave.master_device = None
            vlan_slave.save()
        if nd_dev.bootnetdevice_id == nd_pk:
            nd_dev.bootnetdevice = None
            nd_dev.save()
        to_del.delete()

class create_netdevice(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        keys = _post.keys()
        dev_pk = int([key for key in keys if key.startswith("nd__")][0].split("__")[1])
        cur_dev = device.objects.get(Q(pk=dev_pk))
        value_dict = dict([(key.split("__", 2)[2], value) for key, value in _post.iteritems()])
        if "new" in value_dict:
            # new is here used as a prefix, so new__devname is correct and not new_devname (AL, 20120826)
            logger.info("create new netdevice for '%s'" % (unicode(cur_dev)))
            copy_dict = dict([(key, value_dict["new__%s" % (key)]) for key in [
                "devname", "driver", "driver_options", "ethtool_autoneg", "macaddr", "fake_macaddr",
                "ethtool_duplex", "ethtool_speed", "vlan_id", "description"] if "new__%s" % (key) in value_dict])
            new_nd = netdevice(device=cur_dev,
                               netdevice_speed=netdevice_speed.objects.get(Q(pk=value_dict["new__netdevice_speed"])),
                               **copy_dict)
            try:
                new_nd.save()
            except ValidationError, what:
                request.xml_response.error("error creating: %s" % (unicode(what.messages[0])), logger)
            except:
                raise
            else:
                request.xml_response["new_netdevice"] = new_nd.get_xml()

class delete_net_ip(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        keys = _post.keys()
        main_key = [key for key in keys if key.endswith("__ip")][0]
        net_ip.objects.get(Q(pk=main_key.split("__")[4])).delete()

class create_net_ip(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        keys = _post.keys()
        # print keys
        main_key = [key for key in keys if key.endswith("__new")][0]
        # print main_key
        # key_length, is 5 for device network settings and 3 for deviceinfo.js
        key_length = len(main_key.split("__"))
        # print key_length
        cur_nd = netdevice.objects.get(Q(pk=main_key.split("__")[{5 : 2, 4 : 1, 3 : 1}[key_length]]))
        # transform constants, FIXME
        split_idx = {5 : 4, 4 : 3, 3 : 2}[key_length]
        value_dict = dict([(key.split("__", split_idx)[split_idx], value) for key, value in _post.iteritems()])
        if "new" in value_dict:
            logger.info("create new net_ip for '%s'" % (unicode(cur_nd)))
            copy_dict = dict([(key, value_dict["new__%s" % (key)]) for key in ["ip"] if "new__%s" % (key) in value_dict])
            new_ip = net_ip(netdevice=cur_nd,
                            network=network.objects.get(Q(pk=value_dict["new__network"])),
                            domain_tree_node=domain_tree_node.objects.get(Q(pk=value_dict["new__domain_tree_node"])),
                            **copy_dict)
            try:
                new_ip.save()
            except ValidationError, what:
                request.xml_response.error("error creating: %s" % (unicode(what.messages[0])), logger)
            except:
                raise
            else:
                request.xml_response["new_net_ip"] = new_ip.get_xml()

class create_new_peer(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        s_netdevice = netdevice.objects.get(Q(pk=_post["id"].split("__")[2]))
        d_netdevice = netdevice.objects.get(Q(pk=_post["new_peer"]))
        try:
            _cur_peer = peer_information.objects.get(
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
                request.xml_response.error("error creating new peer: %s" % (unicode(what.messages[0])), logger)
            else:
                request.xml_response.info("created new peer", logger)
                request.xml_response["new_peer_information"] = new_peer.get_xml()
        except peer_information.MultipleObjectsReturned:
            request.xml_response.error("peer already exists", logger)
        else:
            request.xml_response.error("peer already exists", logger)

class delete_peer(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        peer_information.objects.get(Q(pk=_post["id"].split("__")[-1])).delete()

def _get_valid_peers():
    routing_nds = netdevice.objects.filter(Q(device__enabled=True) & Q(device__device_group__enabled=True) & Q(routing=True)).order_by(
        "device__name",
        "devname").prefetch_related("net_ip_set", "device__categories").select_related("device", "device__domain_tree_node")
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
            cur_p.device.full_name,
            ", ".join([cur_ip.ip for cur_ip in cur_p.net_ip_set.all()]) or "no IPs"), pk="%d" % (cur_p.pk))
          for cur_p in routing_nds]
    )

class get_valid_peers(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        request.xml_response["valid_peers"] = _get_valid_peers()

class json_network(View):
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        logger.log(log_level, "[jsn] %s" % (what))
    @method_decorator(login_required)
    def post(self, request):
        _post = request.POST
        graph_mode = _post["graph_mode"]
        logger.info("drawing network, mode is %s" % (graph_mode))
        dev_list = [int(value.split("__")[1]) for value in request.session.get("sel_list", [])]
        r_obj = config_tools.topology_object(self.log, graph_mode, dev_list=dev_list)
        r_obj.add_full_names()
        json_obj = json_graph.dumps(r_obj.nx)
        # import time
        # time.sleep(10)
        # pprint.pprint(json_obj)
        return HttpResponse(json_obj, mimetype="application/json")

class copy_network(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
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
            logger.info("source device is %s" % (unicode(source_dev)))
            logger.info("%s: %s" % (logging_tools.get_plural("target device", len(target_devs)),
                                    ", ".join([unicode(cur_dev) for cur_dev in target_devs])))
            # read peer_informations
            src_nds = source_dev.netdevice_set.all().values_list("pk", flat=True)
            peer_dict = {}
            for peer_info in peer_information.objects.filter(Q(s_netdevice__in=src_nds) | Q(d_netdevice__in=src_nds)):
                s_local, d_local = (peer_info.s_netdevice_id in src_nds,
                                    peer_info.d_netdevice_id in src_nds)
                # print "*", s_local, d_local
                if s_local and d_local:
                    if peer_info.s_netdevice_id != peer_info.d_netdevice_id:
                        logger.critical("host peering detection, not handled")
                    else:
                        peer_dict.setdefault(peer_info.s_netdevice_id, []).append((None, peer_info.penalty))
                elif s_local:
                    peer_dict.setdefault(peer_info.s_netdevice_id, []).append((peer_info.d_netdevice, peer_info.penalty))
                else:
                    peer_dict.setdefault(peer_info.d_netdevice_id, []).append((peer_info.s_netdevice, peer_info.penalty))
            for target_num, target_dev in enumerate(target_devs):
                offset = target_num + 1
                logger.info("operating on %s, offset is %d" % (unicode(target_dev), offset))
                if target_dev.bootnetdevice_id:
                    logger.info("removing bootnetdevice %s" % (unicode(target_dev.bootnetdevice)))
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
                vlan_master_dict = {}
                src_dict, dst_dict = ({}, {})
                # copy from source
                for cur_nd in source_dev.netdevice_set.all().prefetch_related(
                    "netdevice_speed",
                    "network_device_type",
                    "net_ip_set",
                    "net_ip_set__network",
                    "net_ip_set__domain_tree_node",
                    "net_ip_set__network__network_type"):
                    src_dict[cur_nd.devname] = cur_nd
                    if cur_nd.master_device_id:
                        vlan_master_dict[cur_nd.devname] = cur_nd.master_device.devname
                    new_nd = cur_nd.copy()
                    dst_dict[new_nd.devname] = new_nd
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
                            for _seq in xrange(offset):
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
                # vlan masters
                for dst_name, src_name in vlan_master_dict.items():
                    dst_dict[dst_name].master_device = dst_dict[src_name]
                    dst_dict[dst_name].save()
            request.xml_response.info("copied network settings", logger)
        else:
            request.xml_response.error("no target_devices", logger)

class get_domain_name_tree(View):
    @method_decorator(login_required)
    def get(self, request):
        return render_me(request, "domain_name_tree.html", {
            "domain_name_tree_form" : domain_tree_node_form(),
            })()
