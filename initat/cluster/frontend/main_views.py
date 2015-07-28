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

""" main views """

import json
import logging

from django.http.response import HttpResponse
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.utils.decorators import method_decorator
from django.views.generic import View
from initat.cluster.backbone import routing
from initat.cluster.backbone.models import background_job, device_variable
from initat.cluster.backbone.render import render_me
from initat.cluster.frontend.helper_functions import contact_server, xml_wrapper
from initat.tools import server_command

logger = logging.getLogger("cluster.main")


class index(View):
    @method_decorator(login_required)
    def get(self, request):
        return render_me(
            request,
            "index.html",
            {
                "doc_page": "index",
            }
        )()


class permissions_denied(View):
    @method_decorator(login_required)
    def get(self, request):
        return render_me(request, "permission_denied.html")()


class get_number_of_background_jobs(View):
    def post(self, request):
        _return = {"background_jobs": background_job.objects.exclude(Q(state__in=["done", "timeout", "ended", "merged"])).count()}
        return HttpResponse(json.dumps(_return), content_type="application/json")


class get_cluster_info(View):
    def post(self, request):
        _info_dict = {
            "CLUSTER_NAME": "",
            "CLUSTER_ID": "",
        }
        for _key, _value in device_variable.objects.values_list("name", "val_str").filter(
            Q(name__in=["CLUSTER_NAME", "CLUSTER_ID"]) &
            Q(device__device_group__cluster_device_group=True)
        ):
            _info_dict[_key] = _value
        return HttpResponse(json.dumps(_info_dict), content_type="application/json")


class get_routing_info(View):
    def post(self, request):
        cur_routing = routing.srv_type_routing(force="force" in request.POST)
        _return = {
            "service_types": {key: True for key in routing.srv_type_routing().service_types},
            "routing": cur_routing.resolv_dict,
            "local_device": unicode(cur_routing.local_device.full_name if cur_routing.local_device is not None else "UNKNOWN"),
        }
        return HttpResponse(json.dumps(_return), content_type="application/json")


class info_page(View):
    @method_decorator(login_required)
    def get(self, request):
        return render_me(request, "info_page.html")()


class get_server_info(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        cur_routing = routing.srv_type_routing()
        _server_list = []
        for _server in cur_routing.resolv_dict.get("cluster-server", []):
            srv_com = server_command.srv_command(command="server_status")
            _res = contact_server(request, "cluster-server", srv_com, timeout=10, connection_id="server_status", target_server_id=_server[2])
            if _res is not None and _res.tree is not None:
                # dirty stuff
                _res["command"].attrib["server_name"] = _server[0]
                _res["command"].attrib["server_id"] = "{:d}".format(_server[2])
                _tree = _res.tree
            else:
                srv_com["command"].attrib["server_name"] = _server[0]
                srv_com["command"].attrib["server_id"] = "{:d}".format(_server[2])
                _tree = srv_com.tree
            for _node in _tree.iter():
                if str(_node.tag).startswith("{"):
                    _node.tag = _node.tag.split("}", 1)[1]
            _server_list.append(_tree)
        request.xml_response["result"] = _server_list


class server_control(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _cmd = json.loads(request.POST["cmd"])
        # import pprint
        # pprint.pprint(_cmd)
        logger.info(
            "got server_control '{0}' for instance {1} (server_id {2:d})".format(
                _cmd["type"],
                _cmd["instance"],
                int(_cmd["server_id"]),
            )
        )
        srv_com = server_command.srv_command(
            command="server_control",
            control=_cmd["type"],
            services=_cmd["instance"]
        )
        # cur_routing = routing.srv_type_routing()
        request.xml_response["result"] = contact_server(
            request,
            "server",
            srv_com,
            timeout=10,
            connection_id="server_control",
            target_server_id=_cmd["server_id"]
        )


class virtual_desktop_viewer(View):
    @method_decorator(login_required)
    def get(self, request):
        return render_me(
            request,
            "virtual_desktop_viewer.html",
            {
                # "hide_sidebar": True,
                "vdus_index": request.GET.get("vdus_index", 0),
            }
        )()
