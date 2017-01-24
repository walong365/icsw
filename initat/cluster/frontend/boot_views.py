#!/usr/bin/python -Ot
# -*- coding: utf-8 -*-
#
# Copyright (C) 2012-2017 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw-server
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
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

""" boot views """

import json
import logging

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views.generic import View
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from initat.cluster.backbone.models import device, cd_connection, kernel, image, partition_table, status, network, mac_ignore
from initat.cluster.frontend.helper_functions import contact_server, xml_wrapper
from initat.tools import logging_tools, server_command

logger = logging.getLogger("cluster.boot")


class get_boot_info_json(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        from initat.cluster.backbone.server_enums import icswServiceEnum
        from initat.cluster.backbone.serializers import device_serializer_boot
        _post = request.POST
        # print _post
        sel_list = _post.getlist("sel_list[]")
        dev_result = device.objects.filter(
            Q(pk__in=sel_list)
        ).prefetch_related(
            # "bootnetdevice__net_ip_set__network__network_device_type",
            "categories",
            "domain_tree_node",
            "kerneldevicehistory_set",
            "imagedevicehistory_set",
            "snmp_schemes__snmp_scheme_vendor",
            "com_capability_list",
            "DeviceSNMPInfo",
            "snmp_schemes__snmp_scheme_tl_oid_set",
        ).select_related(
            "device_group",
        )
        cd_cons = cd_connection.objects.filter(
            Q(child__in=sel_list) | Q(parent__in=sel_list)
        ).select_related(
            "child__device_group",
            "child__domain_tree_node",
            "parent__device_group",
            "parent__domain_tree_node",
        ).prefetch_related(
            "child__categories",
            "parent__categories",
        )
        call_mother = True if int(_post["call_mother"]) else False
        # to speed up things while testing
        if call_mother:
            srv_com = server_command.srv_command(command="nodestatus")
            srv_com["devices"] = srv_com.builder(
                "devices",
                *[
                    srv_com.builder("device", pk="{:d}".format(cur_dev.pk)) for cur_dev in dev_result
                ]
            )
            result = contact_server(
                request, icswServiceEnum.mother_server, srv_com, timeout=10, log_result=False, connection_id="webfrontend_status"
            )
        else:
            result = None
        # print result.pretty_print()
        # import pprint
        if result is not None and result.xpath(".//ns:cd_ping_list/ns:cd_ping"):
            cd_result = {}
            for cd_ping in result.xpath(".//ns:cd_ping_list/ns:cd_ping"):
                # print cd_ping.attrib
                # todo: support unknown state (ip_state == unknown)
                cd_result[int(cd_ping.attrib["pk"])] = True if cd_ping.attrib["ip_state"] == "up" else False
            request.xml_response["cd_response"] = json.dumps(cd_result)
        ctx = {
            "request": request,
            "fields": ["partition_table", "act_partition_table"],
            "mother_result": result,
            "cd_connections": cd_cons,
        }
        _json = device_serializer_boot(
            dev_result,
            many=True,
            context=ctx,
        ).data
        # import pprint
        # pprint.pprint(_json)
        request.xml_response["response"] = json.dumps(_json)


class update_device_bootsettings(APIView):
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsAuthenticated,)

    def post(self, request, pk):
        _data = request.data
        cur_dev = device.objects.get(Q(pk=pk))
        cur_dev.dhcp_mac = _data["dhcp_mac"]
        cur_dev.dhcp_write = _data["dhcp_write"]
        cur_dev.save(update_fields=["dhcp_mac", "dhcp_write"])
        response = Response(["updated"])
        return response


class update_device(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        from initat.cluster.backbone.server_enums import icswServiceEnum
        _post = request.POST
        dev_data = json.loads(_post["boot"])
        _change_lut = {
            "b": "change_dhcp_mac",
            "t": "change_target_state",
            "p": "change_partition_table",
            "i": "change_new_image",
            "k": "change_new_kernel",
        }
        # import pprint
        # pprint.pprint(dev_data)
        _changed = False
        _mother_commands = set()
        _all_update_list = set()
        pk_list = dev_data["pk_list"]
        # many = True
        # update enabled list
        _en = {key: False for key in _change_lut.keys()}
        for short_key in _en.keys():
            _en[short_key] = dev_data["bo_enabled"].get(short_key, False) and dev_data["change"].get(short_key, False)
        # print _en
        # print pk_list
        with transaction.atomic():
            all_devs = list(
                device.objects.filter(
                    Q(pk__in=pk_list)
                ).select_related(
                    "domain_tree_node", "device_group"
                ).prefetch_related(
                    "categories"
                ).order_by(
                    "device_group__name",
                    "name"
                )
            )
            # print all_devs
            for cur_dev in all_devs:
                # print "**", cur_dev
                update_list = set()
                if _en["t"]:
                    _bs = dev_data["target_state"]
                    _ts_mode = dev_data["ts_mode"]
                    new_new_state = status.objects.get(Q(pk=_bs[str(_ts_mode)]))
                    if _ts_mode == "s":
                        new_prod_link = None
                    else:
                        new_prod_link = network.objects.get(Q(pk=_ts_mode))
                    if new_new_state != cur_dev.new_state or new_prod_link != cur_dev.prod_link:
                        cur_dev.new_state = new_new_state
                        cur_dev.prod_link = new_prod_link
                        update_list.add("target state")
                        _mother_commands.add("refresh")
                if _en["i"]:
                    new_image = image.objects.get(Q(pk=dev_data["new_image"])) if dev_data.get("new_image", None) else None
                    if new_image != cur_dev.new_image:
                        cur_dev.new_image = new_image
                        update_list.add("image")
                if _en["k"]:
                    new_kernel = kernel.objects.get(Q(pk=dev_data["new_kernel"])) if dev_data.get("new_kernel", None) else None
                    new_stage1_flavour = dev_data.get("stage1_flavour", "")
                    new_kernel_append = dev_data.get("kernel_append", "")
                    if new_kernel != cur_dev.new_kernel or new_stage1_flavour != cur_dev.stage1_flavour or new_kernel_append != cur_dev.kernel_append:
                        cur_dev.new_kernel = new_kernel
                        cur_dev.stage1_flavour = new_stage1_flavour
                        cur_dev.kernel_append = new_kernel_append
                        update_list.add("kernel")
                        _mother_commands.add("refresh")
                if _en["p"]:
                    new_part = partition_table.objects.get(Q(pk=dev_data["partition_table"])) if dev_data["partition_table"] else None
                    if new_part != cur_dev.partition_table:
                        cur_dev.partition_table = new_part
                        update_list.add("partition")
                if _en["b"]:
                    new_dhcp_mac, new_dhcp_write = (dev_data["dhcp_mac"], dev_data["dhcp_write"])
                    _bc = False
                    if new_dhcp_mac != cur_dev.dhcp_mac or new_dhcp_write != cur_dev.dhcp_write:
                        cur_dev.dhcp_mac = new_dhcp_mac
                        cur_dev.dhcp_write = new_dhcp_write
                        _bc = True
                    if cur_dev.bootnetdevice:
                        new_driver, new_macaddr = (dev_data["driver"], dev_data["macaddr"])
                        if new_driver != cur_dev.bootnetdevice.driver or new_macaddr != cur_dev.bootnetdevice.macaddr:
                            cur_dev.bootnetdevice.driver = new_driver
                            # ignore empty macaddr (for many changes)
                            if dev_data["change_macaddr"]:
                                cur_dev.bootnetdevice.macaddr = new_macaddr
                            _bc = True
                    if _bc:
                        update_list.add("bootdevice")
                        _mother_commands.add("refresh")
                if update_list:
                    _changed = True
                    _all_update_list |= update_list
                if _changed:
                    # temporarily disable background jobs because we send one command to mother
                    cur_dev._no_bg_job = True
                    cur_dev.save()
                    if cur_dev.bootnetdevice:
                        # promote no_bg_job flag
                        cur_dev.bootnetdevice.device = cur_dev
                        cur_dev.bootnetdevice.save()
                    cur_dev._no_bg_job = False
                    # print cur_dev.new_kernel, cur_dev.new_image
        if _mother_commands:
            for _mother_com in _mother_commands:
                srv_com = server_command.srv_command(command=_mother_com)
                srv_com["devices"] = srv_com.builder(
                    "devices",
                    *[
                        srv_com.builder("device", name=cur_dev.name, pk="{:d}".format(cur_dev.pk)) for cur_dev in all_devs
                    ]
                )
                _res = contact_server(request, icswServiceEnum.mother_server, srv_com, timeout=10, connection_id="webfrontend_refresh")
        if _all_update_list:
            if len(all_devs) > 1:
                dev_info_str = "{}: {}".format(
                    logging_tools.get_plural("device", len(all_devs)),
                    ", ".join(
                        [
                            str(cur_dev) for cur_dev in all_devs
                        ]
                    )
                )
            else:
                dev_info_str = str(all_devs[0])
            request.xml_response.info(
                "updated {} for '{}'".format(
                    ", ".join(_all_update_list),
                    dev_info_str
                )
            )


class soft_control(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        from initat.cluster.backbone.server_enums import icswServiceEnum
        _post = request.POST
        dev_pk_list = json.loads(_post["dev_pk_list"])
        cur_devs = {
            _dev.pk: _dev for _dev in device.objects.filter(Q(pk__in=dev_pk_list))
        }
        soft_state = _post["command"]
        logger.info(
            "sending soft_control '{}' to {}: {}".format(
                soft_state,
                logging_tools.get_plural("device", len(dev_pk_list)),
                logging_tools.reduce_list(sorted([str(cur_dev) for cur_dev in cur_devs.values()])),
            )
        )
        srv_com = server_command.srv_command(command="soft_control")
        srv_com["devices"] = srv_com.builder(
            "devices",
            *[
                srv_com.builder("device", soft_command=soft_state, pk="{:d}".format(cur_dev.pk)) for cur_dev in cur_devs.values()
            ]
        )
        result = contact_server(request, icswServiceEnum.mother_server, srv_com, timeout=10, log_result=False)
        _ok_list, _error_list = (
            result.xpath(".//ns:device[@command_sent='1']/@pk"),
            result.xpath(".//ns:device[@command_sent='0']/@pk"),
        )
        if result:
            if _ok_list:
                request.xml_response.info(
                    "sent {} to {}".format(
                        soft_state,
                        logging_tools.reduce_list(sorted([cur_devs[int(_pk)].full_name for _pk in _ok_list])),
                    ),
                    logger
                )
            if _error_list:
                request.xml_response.warn(
                    "unable to send {} to {}".format(
                        soft_state,
                        logging_tools.reduce_list(sorted([cur_devs[int(_pk)].full_name for _pk in _error_list])),
                    ),
                    logger
                )
            if not _ok_list and not _error_list:
                request.xml_response.warn("nothing to do")


class hard_control(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        from initat.cluster.backbone.server_enums import icswServiceEnum
        _post = request.POST
        cd_con_pks = json.loads(_post["cd_pk_list"])
        cur_cd_cons = cd_connection.objects.select_related("child", "parent").filter(Q(pk__in=cd_con_pks))
        command = _post["command"]
        logger.info(
            "got hc command '{}' for {}:".format(
                command,
                logging_tools.get_plural("device", len(cd_con_pks))
            )
        )
        for cur_cd_con in cur_cd_cons:
            logger.info(
                "  device {} (controlling device: {})".format(
                    str(cur_cd_con.child),
                    str(cur_cd_con.parent)
                )
            )
        srv_com = server_command.srv_command(command="hard_control")
        srv_com["devices"] = srv_com.builder(
            "devices",
            *[
                srv_com.builder(
                    "device",
                    command=command,
                    pk="{:d}".format(cur_cd_con.parent_id),
                    cd_con="{:d}".format(cur_cd_con.pk),
                    bootserver_hint="{:d}".format(cur_cd_con.child.bootserver_id),
                )
                for cur_cd_con in cur_cd_cons
            ]
        )
        contact_server(request, icswServiceEnum.mother_server, srv_com, timeout=10)


class modify_mbl(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        _mbl = json.loads(_post["mbl"])
        if _post["action"] == "ignore":
            try:
                mac_ignore.objects.get(Q(macaddr=_mbl["macaddr"]))
            except mac_ignore.DoesNotExist:
                new_mi = mac_ignore(
                    macaddr=_mbl["macaddr"]
                )
                new_mi.save()
        else:
            mac_ignore.objects.filter(Q(macaddr=_mbl["macaddr"])).delete()
        return HttpResponse(json.dumps({}), content_type="application/json")
