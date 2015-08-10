# -*- coding: utf-8 -*-
#
# Copyright (C) 2012-2015 Andreas Lang-Nevyjel
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

""" monitoring views """
import collections
import datetime
from lxml import etree
import base64
import itertools
import json
import logging
import socket
import StringIO
import uuid
from collections import defaultdict

from django.contrib.auth.decorators import login_required
from django.db.models.query import Prefetch
from django.db.models import Q
from django.http import HttpResponseRedirect, HttpResponse
from django.utils.decorators import method_decorator
from django.views.generic import View
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.response import Response
from django.core.cache import cache
from initat.cluster.backbone.available_licenses import LicenseEnum, LicenseParameterTypeEnum
from initat.cluster.backbone.models import device, domain_name_tree, netdevice, \
    net_ip, peer_information, mon_ext_host, get_related_models, monitoring_hint, mon_check_command, \
    parse_commandline, mon_check_command_special, device_group
from initat.cluster.backbone.models.license import LicenseUsage, LicenseLockListDeviceService
from initat.cluster.frontend.common import duration_utils
from initat.cluster.frontend.rest_views import rest_logging
from initat.cluster.backbone.models.status_history import mon_icinga_log_aggregated_host_data, \
    mon_icinga_log_aggregated_timespan, mon_icinga_log_aggregated_service_data, \
    mon_icinga_log_raw_base, mon_icinga_log_raw_service_alert_data, mon_icinga_log_raw_host_alert_data, AlertList
from initat.cluster.backbone.models.functions import duration
from initat.cluster.backbone.render import permission_required_mixin, render_me
from initat.cluster.frontend.helper_functions import contact_server, xml_wrapper
from lxml.builder import E  # @UnresolvedImports
from initat.md_config_server.icinga_log_reader.log_reader_utils import host_service_id_util
from initat.tools import logging_tools
from initat.tools import process_tools
from initat.tools import server_command
import cairosvg

logger = logging.getLogger("cluster.monitoring")


class setup(permission_required_mixin, View):
    all_required_permissions = ["backbone.mon_check_command.setup_monitoring"]

    def get(self, request):
        return render_me(
            request, "monitoring_setup.html", {
                }
        )()


class setup_cluster(permission_required_mixin, View):
    all_required_permissions = ["backbone.mon_check_command.setup_monitoring"]

    def get(self, request):
        return render_me(
            request, "monitoring_setup_cluster.html", {
                }
        )()


class build_info(permission_required_mixin, View):
    all_required_permissions = ["backbone.mon_check_command.setup_monitoring"]

    def get(self, request):
        return render_me(
            request, "monitoring_build_info.html", {
                }
        )()


class setup_escalation(permission_required_mixin, View):
    all_required_permissions = ["backbone.mon_check_command.setup_monitoring"]

    def get(self, request):
        return render_me(
            request, "monitoring_setup_escalation.html", {
                }
        )()


class device_config(permission_required_mixin, View):
    all_required_permissions = ["backbone.mon_check_command.change_monitoring"]

    def get(self, request):
        return render_me(
            request, "monitoring_device.html", {
                "device_object_level_permission": "backbone.device.change_monitoring",
            }
        )()


class MonitoringHints(permission_required_mixin, View):
    all_required_permissions = ["backbone.mon_check_command.change_monitoring"]

    def get(self, request):
        return render_me(
            request, "monitoring_hints.html", {
            }
        )()


class MonitoringDisk(permission_required_mixin, View):
    all_required_permissions = ["backbone.device.change_disk"]

    def get(self, request):
        return render_me(
            request, "monitoring_disk.html", {
            }
        )()


class create_config(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        srv_com = server_command.srv_command(command="rebuild_host_config", cache_mode=request.POST.get("cache_mode", "DYNAMIC"))
        result = contact_server(request, "md-config", srv_com, connection_id="wf_mdrc")
        if result:
            request.xml_response["result"] = E.devices()


class call_icinga(View):
    @method_decorator(login_required)
    def get(self, request):
        pw = request.session.get("password")
        pw = base64.b64decode(pw) if pw else "no_passwd"
        resp = HttpResponseRedirect(
            u"http{}://{}:{}@{}/icinga/".format(
                "s" if request.is_secure() else "",
                request.user.login,
                # fixme, if no password is set (due to automatic login) use no_passwd
                pw,
                request.get_host()
            )
        )
        return resp


class fetch_partition(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        part_dev = device.objects.get(Q(pk=_post["pk"]))
        logger.info("reading partition info from %s" % (unicode(part_dev)))
        srv_com = server_command.srv_command(command="fetch_partition_info")
        _dev_node = srv_com.builder("device")
        _dev_node.attrib.update(
            {
                "pk": "{:d}".format(part_dev.pk),
            }
        )
        srv_com["devices"] = _dev_node
        _result = contact_server(request, "discovery", srv_com, timeout=30)


class clear_partition(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        part_dev = device.objects.get(Q(pk=_post["pk"]))
        logger.info("clearing partition info from {}".format(unicode(part_dev)))
        _part = part_dev.act_partition_table
        if _part is None:
            request.xml_response.error(u"no partition table defined for {}".format(unicode(part_dev)))
        else:
            part_dev.act_partition_table = None
            part_dev.save(update_fields=["act_partition_table"])
            if not _part.user_created and not get_related_models(_part):
                request.xml_response.warn(u"partition table {} removed".format(_part))
                _part.delete()


class use_partition(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        part_dev = device.objects.get(Q(pk=_post["pk"]))
        logger.info("using partition info from {} as act_partition".format(unicode(part_dev)))
        part_dev.act_partition_table = part_dev.partition_table
        part_dev.save(update_fields=["act_partition_table"])
        request.xml_response.info("set {} as act_partition_table".format(unicode(part_dev.partition_table)))


class get_node_config(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        if "pk_list" in _post:
            pk_list = json.loads(_post["pk_list"])
        else:
            pk_list = request.POST.getlist("pks[]")
        srv_com = server_command.srv_command(command="get_host_config")
        srv_com["device_list"] = E.device_list(
            *[E.device(pk="{:d}".format(int(cur_pk)), mode=request.POST["mode"]) for cur_pk in pk_list]
        )
        result = contact_server(request, "md-config", srv_com, timeout=30)
        if result:
            node_results = result.xpath(".//config", smart_strings=False)
            if len(node_results):
                request.xml_response["result"] = node_results[0]
            else:
                request.xml_response.error("no config", logger=logger)
        else:
            request.xml_response.error("no config", logger=logger)


class get_node_status(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        pk_list = json.loads(_post["pk_list"])
        srv_com = server_command.srv_command(command="get_node_status")
        # noinspection PyUnresolvedReferences
        srv_com["device_list"] = E.device_list(
            *[E.device(pk="{:d}".format(int(cur_pk))) for cur_pk in pk_list if cur_pk]
        )
        result = contact_server(request, "md-config", srv_com, timeout=30)
        if result:
            host_results = result.xpath(".//ns:host_result/text()", smart_strings=False)
            service_results = result.xpath(".//ns:service_result/text()", smart_strings=False)
            if len(host_results) + len(service_results):

                # log and lock access
                any_locked = False
                host_results_filtered = []
                devices_used = set()
                for dev_res in json.loads(host_results[0]):
                    locked = False
                    for entry in dev_res['custom_variables'].split(","):
                        split = entry.split("|")
                        if len(split) == 2 and split[0].lower() == "device_pk":
                            try:
                                dev_pk = int(split[1])
                                locked = LicenseLockListDeviceService.objects.is_device_locked(
                                    LicenseEnum.monitoring_dashboard, dev_pk)
                                if not locked:
                                    devices_used.add(dev_pk)
                            except ValueError:
                                logger.warn("Invalid device pk in get_node_result access logging: {}".format(entry))

                    if not locked:
                        host_results_filtered.append(dev_res)

                    any_locked |= locked

                LicenseUsage.log_usage(LicenseEnum.monitoring_dashboard, LicenseParameterTypeEnum.device, devices_used)

                service_results_filtered = []
                services_used = collections.defaultdict(lambda: [])
                for serv_res in json.loads(service_results[0]):
                    host_pk, service_pk, _ = host_service_id_util.parse_host_service_description(
                        serv_res['description'],
                        log=logger.error
                    )
                    locked = False
                    if host_pk is not None and service_pk is not None:

                        locked = LicenseLockListDeviceService.objects.is_device_service_locked(
                            LicenseEnum.monitoring_dashboard, host_pk, service_pk
                        )

                        if not locked:
                            services_used[host_pk].append(service_pk)

                    if not locked:
                        service_results_filtered.append(serv_res)

                    any_locked |= locked

                LicenseUsage.log_usage(LicenseEnum.monitoring_dashboard, LicenseParameterTypeEnum.service,
                                       services_used)

                if any_locked:
                    request.xml_response.info("Some entries are on the license lock list and therefore not displayed.")

                # simply copy json dump
                request.xml_response["host_result"] = json.dumps(host_results_filtered)
                request.xml_response["service_result"] = json.dumps(service_results_filtered)

            else:
                request.xml_response.error("no service or node_results", logger=logger)


class livestatus(View):
    @method_decorator(login_required)
    def get(self, request):
        return render_me(
            request, "monitoring_livestatus.html", {
                }
        )()


class StatusHistory(permission_required_mixin, View):
    def get(self, request):
        return render_me(
            request, "monitoring_status_history.html", {
            }
        )()


class Graph(permission_required_mixin, View):
    def get(self, request):
        return render_me(
            request, "monitoring_graph.html", {
            }
        )()


class overview(View):
    @method_decorator(login_required)
    def get(self, request):
        return render_me(
            request, "monitoring_overview.html", {
                }
        )()


class delete_hint(View):
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        monitoring_hint.objects.get(Q(pk=_post["hint_pk"])).delete()


class get_mon_vars(View):
    def post(self, request):
        _post = request.POST
        _dev_pks = [int(_post["device_pk"])]
        _dev = device.objects.select_related("device_group").get(Q(pk=_dev_pks[0]))
        if not _dev.is_meta_device:
            # add meta device
            _dev_pks.append(_dev.device_group.device_group.filter(Q(is_meta_device=True))[0].pk)
        res_list = []
        mon_check_commands = mon_check_command.objects.filter(
            Q(config__device_config__device__in=_dev_pks)
        ).select_related("config")
        for _mc in mon_check_commands:
            _mon_info, _log_lines = parse_commandline(_mc.command_line)
            for _key, _value in _mon_info["default_values"].iteritems():
                if type(_value) == tuple:
                    res_list.append(
                        (
                            _mc.name,
                            _value[0],
                            _value[1],
                            "i" if _value[1].isdigit() else "s",
                            _mc.config.name,
                        )
                    )
        mon_special_check_commands = mon_check_command_special.objects.filter(
            Q(mon_check_command__config__device_config__device__in=_dev_pks)
        )
        for _mc in mon_special_check_commands:
            _mon_info, _log_lines = parse_commandline(_mc.command_line)
            for _key, _value in _mon_info["default_values"].iteritems():
                if type(_value) == tuple:
                    _checks = _mc.mon_check_command_set.all()
                    if len(_checks) == 1:
                        res_list.append(
                            (
                                _mc.name,
                                _value[0],
                                _value[1],
                                "i" if _value[1].isdigit() else "s",
                                _checks[0].config.name,
                            )
                        )
        return HttpResponse(json.dumps(
            # [
            #    {"idx": 0, "name": "please choose..."}
            # ] +
            [
                {
                    "idx": _idx,
                    "info": "{} (default {}) from check_command {} (config {})".format(
                        _value[1],
                        _value[2],
                        _value[0],
                        _value[4],
                    ),
                    "type": _value[3],
                    "name": _value[1],
                    "value": _value[2],
                } for _idx, _value in enumerate(res_list, 1)
            ]), content_type="application/json")


class resolve_name(View):
    @method_decorator(xml_wrapper)
    def post(self, request):
        fqdn = request.POST["fqdn"]
        if fqdn.strip():
            try:
                _ip = socket.gethostbyname(fqdn)
            except:
                pass
            else:
                logger.info(u"resolved {} to {}".format(fqdn, _ip))
                request.xml_response["ip"] = _ip


class create_device(permission_required_mixin, View):
    all_required_permissions = ["backbone.user.modify_tree"]

    @method_decorator(login_required)
    def get(self, request):
        return render_me(
            request, "create_new_device.html", {
            }
        )()

    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        # domain name tree
        dnt = domain_name_tree()
        device_data = json.loads(_post["device_data"])
        try:
            cur_dg = device_group.objects.get(Q(name=device_data["device_group"]))
        except device_group.DoesNotExist:
            try:
                cur_dg = device_group.objects.create(
                    name=device_data["device_group"],
                    domain_tree_node=dnt.get_domain_tree_node(""),
                    description="auto created device group {}".format(device_data["device_group"]),
                    )
            except:
                request.xml_response.error(
                    u"cannot create new device group: {}".format(
                        process_tools.get_except_info()
                    ),
                    logger=logger
                )
                cur_dg = None
            else:
                request.xml_response.info(u"created new device group '{}'".format(unicode(cur_dg)), logger=logger)
        else:
            if cur_dg.cluster_device_group:
                request.xml_response.error(
                    u"no devices allowed in system (cluster) group",
                    logger=logger
                )
                cur_dg = None
        if cur_dg is not None:
            if device_data["full_name"].count("."):
                short_name, domain_name = device_data["full_name"].split(".", 1)
                dnt_node = dnt.add_domain(domain_name)
            else:
                short_name = device_data["full_name"]
                # top level node
                dnt_node = dnt.get_domain_tree_node("")
            try:
                cur_dev = device.objects.get(Q(name=short_name) & Q(domain_tree_node=dnt_node))
            except device.DoesNotExist:
                # check image
                if device_data["icon_name"].strip():
                    try:
                        cur_img = mon_ext_host.objects.get(Q(name=device_data["icon_name"]))
                    except mon_ext_host.DoesNotExist:
                        cur_img = None
                    else:
                        pass
                try:
                    cur_dev = device.objects.create(
                        device_group=cur_dg,
                        is_meta_device=False,
                        domain_tree_node=dnt_node,
                        name=short_name,
                        mon_resolve_name=device_data["resolve_via_ip"],
                        comment=device_data["comment"],
                        mon_ext_host=cur_img,
                    )
                except:
                    request.xml_response.error(
                        u"cannot create new device: {}".format(
                            process_tools.get_except_info()
                        ),
                        logger=logger
                    )
                    cur_dev = None
                else:
                    request.xml_response.info(u"created new device '{}'".format(unicode(cur_dev)), logger=logger)
            else:
                request.xml_response.warn(u"device {} already exists".format(unicode(cur_dev)), logger=logger)
                cur_dev = None

            if cur_dev is not None:
                try:
                    cur_nd = netdevice.objects.get(Q(device=cur_dev) & Q(devname='eth0'))
                except netdevice.DoesNotExist:
                    cur_nd = netdevice.objects.create(
                        devname="eth0",
                        device=cur_dev,
                        routing=device_data["routing_capable"],
                        )
                    if device_data["peer"]:
                        peer_information.objects.create(
                            s_netdevice=cur_nd,
                            d_netdevice=netdevice.objects.get(Q(pk=device_data["peer"])),
                            penalty=1,
                        )
                try:
                    cur_ip = net_ip.objects.get(Q(netdevice=cur_nd) & Q(ip=device_data["ip"]))
                except net_ip.DoesNotExist:
                    cur_ip = net_ip(
                        netdevice=cur_nd,
                        ip=device_data["ip"],
                        domain_tree_node=dnt_node,
                    )
                    cur_ip.create_default_network = True
                    try:
                        cur_ip.save()
                    except:
                        request.xml_response.error(u"cannot create IP: {}".format(process_tools.get_except_info()), logger=logger)
                        cur_ip = None


class svg_to_png(View):
    @method_decorator(xml_wrapper)
    def post(self, request):
        parser = etree.XMLParser(remove_comments=True)
        _post = request.POST
        _bytes = _post["svg"]
        _out = StringIO.StringIO()
        # _xml = etree.fromstring(_post["svg"], parser)
        # for _el in _xml.iter():
        #    for _key, _value in _el.attrib.iteritems():
        #        if _key.startswith("ng-"):
        #            del _el.attrib[_key]
        try:
            cairosvg.svg2png(bytestring=_bytes.strip(), write_to=_out)
        except:
            request.xml_response.error("error converting svg to png")
        else:
            _png_content = _out.getvalue()
            _cache_key = "SVG2PNG_{}".format(uuid.uuid4().get_urn().split("-")[-1])
            cache.set(_cache_key, _png_content, 60)
            logger.info(
                "converting svg with {} to png with {} (cache_key is {})".format(
                    logging_tools.get_size_str(len(_post["svg"])),
                    logging_tools.get_size_str(len(_png_content)),
                    _cache_key,
                )
            )
            request.xml_response["cache_key"] = _cache_key


class fetch_png_from_cache(View):
    def get(self, request, cache_key=None):
        _val = cache.get(cache_key)
        if _val:
            return HttpResponse(_val, content_type="image/png")
        else:
            return HttpResponse("", content_type="image/png")
