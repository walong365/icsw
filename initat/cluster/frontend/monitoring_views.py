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

""" monitoring views """

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.utils.decorators import method_decorator
from django.views.generic import View
from initat.cluster.backbone.models import device
from initat.cluster.frontend.forms import mon_period_form, mon_notification_form, mon_contact_form, \
    mon_service_templ_form, host_check_command_form, mon_contactgroup_form, mon_device_templ_form, \
    mon_host_cluster_form, mon_service_cluster_form, mon_host_dependency_templ_form, \
    mon_service_esc_templ_form, mon_device_esc_templ_form, mon_service_dependency_templ_form, \
    mon_host_dependency_form, mon_service_dependency_form, device_monitoring_form
from initat.cluster.frontend.helper_functions import contact_server, xml_wrapper
from initat.core.render import render_me
from initat.cluster.backbone.render import permission_required_mixin
from lxml.builder import E # @UnresolvedImports
import base64
import json
import logging
import server_command

logger = logging.getLogger("cluster.monitoring")

class setup(permission_required_mixin, View):
    all_required_permissions = ["backbone.setup_monitoring"]
    def get(self, request):
        # print mon_contact_form()
        return render_me(
            request, "monitoring_setup.html", {
                "mon_period_form" : mon_period_form(),
                "mon_notification_form" : mon_notification_form(),
                "mon_contact_form" : mon_contact_form(),
                "mon_service_templ_form" : mon_service_templ_form(),
                "host_check_command_form" : host_check_command_form(),
                "mon_contactgroup_form" : mon_contactgroup_form(),
                "mon_device_templ_form" : mon_device_templ_form(),
                }
        )()

class setup_cluster(permission_required_mixin, View):
    all_required_permissions = ["backbone.setup_monitoring"]
    def get(self, request):
        return render_me(
            request, "monitoring_setup_cluster.html", {
                "mon_host_cluster_form" : mon_host_cluster_form(),
                "mon_service_cluster_form" : mon_service_cluster_form(),
                "mon_host_dependency_templ_form" : mon_host_dependency_templ_form(),
                "mon_service_dependency_templ_form" : mon_service_dependency_templ_form(),
                "mon_host_dependency_form" : mon_host_dependency_form(),
                "mon_service_dependency_form" : mon_service_dependency_form(),
                }
        )()

class setup_escalation(View):
    @method_decorator(login_required)
    def get(self, request):
        return render_me(
            request, "monitoring_setup_escalation.html", {
                "mon_service_esc_templ_form" : mon_service_esc_templ_form(),
                "mon_device_esc_templ_form" : mon_device_esc_templ_form(),
                }
        )()

class device_config(permission_required_mixin, View):
    all_required_permissions = ["backbone.change_monitoring"]
    def get(self, request):
        return render_me(
            request, "monitoring_device.html", {
                "device_monitoring_form" : device_monitoring_form(),
                "device_object_level_permission" : "backbone.change_monitoring",
            }
        )()

class create_config(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        srv_com = server_command.srv_command(command="rebuild_host_config", cache_mode="ALWAYS")
        result = contact_server(request, "tcp://localhost:8010", srv_com)
        if result:
            request.xml_response["result"] = E.devices()

# class rebuild_config(View):
#    @method_decorator(login_required)
#    @method_decorator(xml_wrapper)
#    def post(self, request):
#        srv_com = server_command.srv_command(command="rebuild_config")
#        _result = contact_server(request, "tcp://localhost:8010", srv_com, timeout=30)

class call_icinga(View):
    @method_decorator(login_required)
    def get(self, request):
        resp = HttpResponseRedirect(
            "http://%s:%s@%s/icinga/" % (
                request.user.login,
                base64.b64decode(request.session["password"]),
                request.META["HTTP_HOST"]
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
        srv_com["server_key:device_pk"] = "%d" % (part_dev.pk)
        srv_com["server_key:device_pk"] = "%d" % (part_dev.pk)
        _result = contact_server(request, "tcp://localhost:8004", srv_com, timeout=30)


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
            *[E.device(pk="%d" % (int(cur_pk))) for cur_pk in pk_list]
        )
        result = contact_server(request, "tcp://localhost:8010", srv_com, timeout=30)
        if result:
            node_results = result.xpath(".//config")
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
        if "pk_list" in _post:
            pk_list = json.loads(_post["pk_list"])
        else:
            pk_list = request.POST.getlist("pks[]")
        srv_com = server_command.srv_command(command="get_node_status")
        srv_com["device_list"] = E.device_list(
            *[E.device(pk="%d" % (int(cur_pk))) for cur_pk in pk_list]
        )
        result = contact_server(request, "tcp://localhost:8010", srv_com, timeout=30)
        if result:
            node_results = result.xpath(".//node_results")
            if len(node_results):
                node_results = node_results[0]
                if len(node_results):
                    # first device
                    request.xml_response["result"] = E.node_results(
                        *[E.node_result(
                            *[E.result(cur_res.attrib.pop("plugin_output"), **cur_res.attrib) for cur_res in node_result],
                            **node_result.attrib
                        ) for node_result in node_results]
                    )
                else:
                    request.xml_response.error("no node_results", logger=logger)
            else:
                request.xml_response.error("no node_results", logger=logger)
