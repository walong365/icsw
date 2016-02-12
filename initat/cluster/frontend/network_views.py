#!/usr/bin/python-init -Ot
# -*- coding: utf-8 -*-
#
# Copyright (C) 2013-2016 Andreas Lang-Nevyjel
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

import json
import logging
import netifaces

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.db.utils import IntegrityError
from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views.generic import View
from networkx.readwrite import json_graph

from initat.cluster.backbone.models import device, peer_information, network, network_type
from initat.cluster.backbone.render import permission_required_mixin
from initat.cluster.frontend.helper_functions import xml_wrapper
from initat.tools import config_tools, ipvx_tools, logging_tools

logger = logging.getLogger("cluster.network")


class json_network(View):
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        logger.log(log_level, "[jsn] %s" % (what))

    @method_decorator(login_required)
    def post(self, request):
        _post = request.POST
        graph_mode = _post["graph_sel"]
        dev_list = [int(value.split("__")[1]) for value in request.session.get("sel_list", [])]
        logger.info(
            "drawing network, mode is {}, {}".format(
                graph_mode,
                logging_tools.get_plural("device", len(dev_list)),
            )
        )
        r_obj = config_tools.topology_object(
            self.log,
            graph_mode,
            dev_list=dev_list,
            only_allowed_device_groups=True,
            user=request.user
        )
        r_obj.add_full_names()
        json_obj = json.dumps(json_graph.node_link_data(r_obj.nx))
        # import time
        # time.sleep(10)
        # pprint.pprint(json_obj)
        return HttpResponse(json_obj, content_type="application/json")


class copy_network(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        import pprint
        pprint.pprint(_post)
        source_dev = device.objects.get(Q(pk=_post["source_dev"]))
        copy_coms = True if _post["copy_coms"].lower()[0] in ["1", "t", "y"] else False
        target_devs = device.objects.exclude(
            Q(pk=source_dev.pk)
        ).filter(
            Q(pk__in=json.loads(_post["all_devs"]))
        ).prefetch_related(
            "netdevice_set",
            "netdevice_set__netdevice_speed",
            "netdevice_set__network_device_type",
            "netdevice_set__net_ip_set",
            "netdevice_set__net_ip_set__network",
            "netdevice_set__net_ip_set__network__network_type"
        ).order_by("name")
        if len(target_devs):
            diff_ip = ipvx_tools.ipv4("0.0.0.1")
            logger.info("source device is %s" % (unicode(source_dev)))
            logger.info(
                "{}: {}".format(
                    logging_tools.get_plural("target device", len(target_devs)),
                    ", ".join([unicode(cur_dev) for cur_dev in target_devs])
                )
            )
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
                logger.info(
                    "operating on {}, offset is {:d}".format(
                        unicode(target_dev),
                        offset
                    )
                )
                if target_dev.bootnetdevice_id:
                    logger.info("removing bootnetdevice {}".format(unicode(target_dev.bootnetdevice)))
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
                bridge_master_dict = {}
                src_dict, dst_dict = ({}, {})
                # copy from source
                for cur_nd in source_dev.netdevice_set.all().prefetch_related(
                    "netdevice_speed",
                    "network_device_type",
                    "net_ip_set",
                    "net_ip_set__network",
                    "net_ip_set__domain_tree_node",
                    "net_ip_set__network__network_type"
                ):
                    src_dict[cur_nd.devname] = cur_nd
                    if cur_nd.master_device_id:
                        vlan_master_dict[cur_nd.devname] = cur_nd.master_device.devname
                    if cur_nd.bridge_device_id:
                        bridge_master_dict[cur_nd.devname] = cur_nd.bridge_device.devname
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
                        "network__network_type"
                    ):
                        new_ip = cur_ip.copy()
                        new_ip.netdevice = new_nd
                        if cur_ip.network.network_type.identifier != "l":
                            # increase IP for non-loopback addresses
                            ip_val = ipvx_tools.ipv4(cur_ip.ip)
                            for _seq in xrange(offset):
                                ip_val += diff_ip
                            new_ip.ip = str(ip_val)
                            while not new_ip.is_unique:
                                ip_val += diff_ip
                                new_ip.ip = str(ip_val)
                        new_ip.save()
                    # peering
                    if cur_nd.pk in peer_dict:
                        for target_nd, penalty in peer_dict[cur_nd.pk]:
                            if target_nd is None:
                                # local peer
                                peer_information(
                                    s_netdevice=new_nd,
                                    d_netdevice=new_nd,
                                    penalty=penalty,
                                ).save()
                            else:
                                try:
                                    # remote peer
                                    peer_information(
                                        s_netdevice=new_nd,
                                        d_netdevice=target_nd,
                                        penalty=penalty,
                                    ).save()
                                except IntegrityError:
                                    request.xml_response.warn(
                                        "cannot create peer",
                                        logger
                                    )
                # vlan masters
                for dst_name, src_name in vlan_master_dict.items():
                    dst_dict[dst_name].master_device = dst_dict[src_name]
                    dst_dict[dst_name].save()
                # bridge masters
                for dst_name, src_name in bridge_master_dict.items():
                    dst_dict[dst_name].bridge_device = dst_dict[src_name]
                    dst_dict[dst_name].save()
                if copy_coms:
                    target_dev.com_capability_list.clear()
                    for src_com in source_dev.com_capability_list.all():
                        target_dev.com_capability_list.add(src_com)
                    target_dev.snmp_schemes.clear()
                    for src_scheme in source_dev.snmp_schemes.all():
                        target_dev.snmp_schemes.add(src_scheme)
            request.xml_response.info(
                "copied network settings for {}".format(
                    logging_tools.get_plural("device", len(target_devs)),
                ),
                logger
            )
        else:
            request.xml_response.error("no target_devices", logger)


class get_network_clusters(permission_required_mixin, View):
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        logger.log(log_level, "[jsn] %s" % (what))
    all_required_permissions = []

    def post(self, request):
        r_obj = config_tools.router_object(self.log)
        return HttpResponse(json.dumps(r_obj.get_clusters()), content_type="application/json")


class get_active_scans(permission_required_mixin, View):
    all_required_permissions = []

    def get(self, request):
        _pks = json.loads(request.GET["pks"])
        _dev = list(device.objects.filter(Q(pk__in=_pks)).values("pk", "active_scan"))
        return HttpResponse(
            json.dumps(_dev),
            content_type="application/json"
        )


class get_free_ip(View):
    @method_decorator(login_required)
    def post(self, request):
        _post = request.POST
        net_ip = json.loads(_post["netip"])
        cur_nw = network.objects.get(Q(idx=net_ip["network"]))
        free_ip = cur_nw.get_free_ip()
        if free_ip:
            _res = {
                "ip": str(free_ip)
            }
        else:
            _res = {}
        return HttpResponse(
            json.dumps(_res),
            content_type="application/json"
        )


class rescan_networks(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        if network.objects.all().count() and False:
            request.xml_response.warn("Networks already defined")
        else:
            import pprint
            _post = request.POST
            pprint.pprint(_post)
            _ifs = netifaces.interfaces()
            # todo: add gateways
            _gws = netifaces.gateways().get(netifaces.AF_INET, [])
            # dict: network -> network objects
            new_nets = {}
            for _if in _ifs:
                _addr = netifaces.ifaddresses(_if)
                if netifaces.AF_INET in _addr:
                    for _net in _addr[netifaces.AF_INET]:
                        _required_keys = {"addr", "netmask"}
                        if _net["netmask"] != "255.255.255.255" and _required_keys == _required_keys & set(_net.keys()):
                            netmask = ipvx_tools.ipv4(_net["netmask"])
                            address = ipvx_tools.ipv4(_net["addr"])
                            networkaddr = netmask & address
                            if str(networkaddr) not in new_nets:
                                # get type
                                if ipvx_tools.is_loopback_network(networkaddr):
                                    _type = network_type.objects.get(identifier="l")
                                else:
                                    _type = network_type.objects.get(identifier="o")
                                net_id = "scanned_{:d}".format(len(new_nets.keys()) + 1)
                                new_nw = network(
                                    identifier=net_id,
                                    info="autogenerated",
                                    network=str(networkaddr),
                                    netmask=str(netmask),
                                    gateway="0.0.0.0",
                                    broadcast=str(~netmask | (networkaddr & netmask)),
                                    network_type=_type,
                                )
                                new_nw.save()
                                new_nets[str(networkaddr)] = new_nw
            request.xml_response.info(
                "added {}".format(
                    logging_tools.get_plural("network", len(new_nets))
                )
            )
