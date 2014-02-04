#!/usr/bin/python -Ot
# -*- coding: utf-8 -*-
#
# Copyright (C) 2012-2014 Andreas Lang-Nevyjel
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

""" boot views """

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils.decorators import method_decorator
from django.views.generic import View
from initat.cluster.backbone.models import device, cd_connection, \
     kernel, image, partition_table, status, network, devicelog
from initat.cluster.frontend.helper_functions import contact_server, xml_wrapper
from initat.core.render import render_me
from lxml.builder import E # @UnresolvedImports
import logging
import logging_tools
import server_command

logger = logging.getLogger("cluster.boot")

# ordering is important
OPTION_LIST = [
    ("t", "target state", None),
    ("s", "soft control", None),
    ("h", "hard control", None),
    ("b", "bootdevice"  , None),
    ("k", "kernel"      , kernel),
    ("i", "image"       , image),
    ("p", "partition"   , None),
    ("l", "devicelog"   , None),
]

class show_boot(View):
    @method_decorator(login_required)
    def get(self, request):
        return render_me(
            request, "boot_overview.html",
        )()

class get_html_options(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        xml_resp = E.options()
        for short, long_opt, _t_obj in OPTION_LIST:
            xml_resp.append(E.option(long_opt, short=short))
        request.xml_response["response"] = xml_resp

class get_addon_info(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        addon_type = _post["type"]
        addon_long, addon_class = [(long_opt, t_class) for short, long_opt, t_class in OPTION_LIST if short == addon_type][0]
        logger.info("requested addon dictionary '%s'" % (addon_long))
        addon_list = E.list()
        if addon_class:
            for obj in addon_class.objects.all(): # filter(Q(enabled=True)):
                addon_list.append(obj.get_xml())
        if addon_type == "t":
            prod_nets = network.objects.filter(Q(network_type__identifier="p"))
            # add all states without production net
            for t_state in status.objects.filter(Q(prod_link=False)):
                addon_list.append(t_state.get_xml())
            # add all states with production net
            for prod_net in prod_nets:
                for t_state in status.objects.filter(Q(prod_link=True)):
                    addon_list.append(t_state.get_xml(prod_net))
        if addon_type == "p":
            for cur_part in partition_table.objects.filter(Q(enabled=True) & Q(nodeboot=True)).prefetch_related(
                "partition_disc_set",
                "partition_disc_set__partition_set",
                "partition_disc_set__partition_set__partition_fs",
                ).order_by("name"):
                addon_list.append(cur_part.get_xml(validate=True))
        logger.info("returning %s" % (logging_tools.get_plural("object", len(addon_list))))
        request.xml_response["response"] = addon_list

def strip_dict(in_dict):
    return in_dict.keys()[0].split("__")[1], dict([("__".join(key.split("__")[2:]), value) for key, value in in_dict.iteritems()])

class set_boot(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        dev_id, _post = strip_dict(_post)
        with transaction.atomic():
            cur_dev = device.objects.get(Q(pk=dev_id))
            boot_mac = _post["boot_dev_macaddr"]
            boot_driver = _post["boot_dev_driver"]
            dhcp_write = True if int(_post["write_dhcp"])  else False
            dhcp_mac = True if int(_post["greedy_mode"]) else False
            any_error = False
            cur_dev.dhcp_mac = dhcp_mac
            cur_dev.dhcp_write = dhcp_write
            if cur_dev.bootnetdevice:
                bnd = cur_dev.bootnetdevice
                bnd.driver = boot_driver
                bnd.macaddr = boot_mac
                try:
                    bnd.save()
                except ValidationError:
                    any_error = True
                    request.xml_response.error("cannot save boot settings", logger)
            cur_dev.save()
        if not any_error:
            request.xml_response.info("updated bootdevice settings of %s" % (unicode(cur_dev)), logger)
        srv_com = server_command.srv_command(command="alter_macaddr")
        srv_com["devices"] = srv_com.builder(
            "devices",
            srv_com.builder("device", name=cur_dev.name, pk="%d" % (cur_dev.pk)))
        contact_server(request, "tcp://localhost:8000", srv_com, timeout=10, log_result=False, log_error=False)

class set_partition(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        cur_dev = device.objects.get(Q(pk=_post["dev_id"].split("__")[1]))
        if not int(_post["new_part"]):
            cur_dev.partition_table = None
        else:
            cur_dev.partition_table = partition_table.objects.get(Q(pk=_post["new_part"]))
        cur_dev.save()

class set_image(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        cur_dev = device.objects.get(Q(pk=_post["dev_id"].split("__")[1]))
        if not int(_post["new_image"]):
            cur_dev.new_image = None
        else:
            cur_dev.new_image = image.objects.get(Q(pk=_post["new_image"]))
        cur_dev.save()

class set_kernel(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        dev_id, _post = strip_dict(_post)
        with transaction.atomic():
            cur_dev = device.objects.get(Q(pk=dev_id))
            if int(_post["new_kernel"]) == 0:
                cur_dev.new_kernel = None
            else:
                cur_dev.new_kernel = kernel.objects.get(Q(pk=_post["new_kernel"]))
            cur_dev.stage1_flavour = _post["kernel_flavour"]
            cur_dev.kernel_append = _post["kernel_append"]
            cur_dev.save()
        # very important
        srv_com = server_command.srv_command(command="refresh")
        srv_com["devices"] = srv_com.builder(
            "devices",
            srv_com.builder("device", pk="%d" % (cur_dev.pk)))
        contact_server(request, "tcp://localhost:8000", srv_com, timeout=10, connection_id="webfrontend_refresh")
        request.xml_response.info("updated kernel settings of %s" % (unicode(cur_dev)), logger)

class set_target_state(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        with transaction.atomic():
            cur_dev = device.objects.get(Q(pk=_post["dev_id"].split("__")[1]))
            t_state, t_prod_net = [int(value) for value in _post["new_state"].split("__")]
            if t_state == 0:
                cur_dev.new_state = None
                cur_dev.prod_link = None
            else:
                cur_dev.new_state = status.objects.get(Q(pk=t_state))
                if t_prod_net:
                    cur_dev.prod_link = network.objects.get(Q(pk=t_prod_net))
                else:
                    cur_dev.prod_link = None
            cur_dev.save()
        srv_com = server_command.srv_command(command="refresh")
        srv_com["devices"] = srv_com.builder(
            "devices",
            srv_com.builder("device", pk="%d" % (cur_dev.pk)))
        contact_server(request, "tcp://localhost:8000", srv_com, timeout=10, log_result=False)
        request.xml_response.info("updated target state of %s" % (unicode(cur_dev)), logger)

class get_boot_info(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        option_dict = dict([(short, True if _post.get("opt_%s" % (short)) in ["true"] else False) for short, _long_opt, _t_class in OPTION_LIST])
        sel_list = _post.getlist("sel_list[]")
        dev_result = device.objects.filter(Q(pk__in=sel_list))
        call_mother = True if int(_post["call_mother"]) else False
        # to speed up things while testing
        result = None
        if call_mother:
            srv_com = server_command.srv_command(command="status")
            srv_com["devices"] = srv_com.builder(
                "devices",
                *[srv_com.builder("device", pk="%d" % (cur_dev.pk)) for cur_dev in dev_result])
            result = contact_server(request, "tcp://localhost:8000", srv_com, timeout=10, log_result=False, connection_id="webfrontend_status")
            # result = net_tools.zmq_connection("boot_full_webfrontend", timeout=10).add_connection("tcp://localhost:8000", srv_com)
        xml_resp = E.boot_info()
        # lut for connections
        dev_lut = {}
        for cur_dev in dev_result:
            # recv/reqstate are written by mother, here we 'salt' this information with the device XML (pingstate)
            if call_mother:
                if result is not None:
                    # copy from mother
                    dev_node = result.xpath(".//ns:device[@pk='%d']" % (cur_dev.pk), smart_strings=False)
                    if len(dev_node):
                        dev_node = dev_node[0]
                    else:
                        dev_node = None
                else:
                    dev_node = None
                dev_info = cur_dev.get_xml(full=False, add_state=True, mother_xml=dev_node)
            else:
                dev_info = cur_dev.get_xml(full=False)
            dev_lut[cur_dev.pk] = dev_info
            xml_resp.append(dev_info)
        # add option-dict related stuff
        # print etree.tostring(xml_resp, pretty_print=True)
        if option_dict.get("h", False):
            # device connections
            for cur_cd in cd_connection.objects.filter(Q(child__in=dev_result)).select_related("child", "parent"):
                dev_lut[cur_cd.child_id].find("connections").append(cur_cd.get_xml())
        request.xml_response["response"] = xml_resp

class get_devlog_info(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        lp_dict = dict([(int(key.split("__")[1]), int(_post[key])) for key in _post.keys() if key.startswith("dev__")])
        dev_result = device.objects.filter(Q(pk__in=lp_dict.keys()))
        oldest_pk = min(lp_dict.values() + [0])
        logger.info("request devlogs for %s, oldest devlog_pk is %d" % (
            logging_tools.get_plural("device", len(lp_dict)),
            oldest_pk))
        xml_resp = E.devlog_info()
        # lut for device_logs
        dev_lut, dev_dict = ({}, {})
        for cur_dev in dev_result:
            # recv/reqstate are written by mother, here we 'salt' this information with the device XML (pingstate)
            dev_info = cur_dev.get_xml(full=False)
            dev_lut[cur_dev.pk] = dev_info
            dev_dict[cur_dev.pk] = cur_dev
            xml_resp.append(dev_info)
        dev_logs = devicelog.objects.filter(Q(pk__gt=oldest_pk) & Q(device__in=dev_result)).select_related("log_source", "log_status", "user")
        logs_transfered = dict([(key, 0) for key in lp_dict.iterkeys()])
        for dev_log in dev_logs:
            if dev_log.pk > lp_dict[dev_log.device_id]:
                logs_transfered[dev_log.device_id] += 1
                dev_lut[dev_log.device_id].find("devicelogs").append(dev_log.get_xml())
        logs_transfered = dict([(key, value) for key, value in logs_transfered.iteritems() if value])
        logger.info("transfered logs: %s" % (", ".join(["%s: %d" % (unicode(dev_dict[pk]), logs_transfered[pk]) for pk in logs_transfered.iterkeys()]) or "none"))
        request.xml_response["response"] = xml_resp

class soft_control(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        cur_dev = device.objects.get(Q(pk=_post["key"].split("__")[1]))
        soft_state = _post["key"].split("__")[-1]
        logger.info("sending soft_control '%s' to device %s" % (soft_state, unicode(cur_dev)))
        srv_com = server_command.srv_command(command="soft_control")
        srv_com["devices"] = srv_com.builder(
            "devices",
            srv_com.builder("device", soft_command=soft_state, pk="%d" % (cur_dev.pk)))
        result = contact_server(request, "tcp://localhost:8000", srv_com, timeout=10, log_result=False)
        # result = net_tools.zmq_connection("boot_webfrontend", timeout=10).add_connection("tcp://localhost:8000", srv_com)
        if result:
            request.xml_response.info("sent %s to %s" % (soft_state, unicode(cur_dev)), logger)

class hard_control(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        cd_id, command = (_post["cd_id"],
                          _post["value"])
        cur_cd_con = cd_connection.objects.get(Q(pk=cd_id.split("__")[-1]))
        target_dev = device.objects.select_related("child", "parent").get(Q(pk=cd_id.split("__")[1]))
        logger.info("got hc command '%s' for device '%s' (controling device: %s)" % (
            command,
            unicode(target_dev),
            unicode(cur_cd_con.parent)))
        srv_com = server_command.srv_command(command="hard_control")
        srv_com["devices"] = srv_com.builder(
            "devices",
            srv_com.builder("device", command=command, cd_con="%d" % (cur_cd_con.pk)))
        contact_server(request, "tcp://localhost:8000", srv_com, timeout=10)
