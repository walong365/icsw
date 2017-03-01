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

""" main views """

import datetime
import glob
import json
import logging
import os

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http.response import HttpResponse
from django.utils.decorators import method_decorator
from django.views.generic import View

from initat.cluster.backbone import routing
from initat.cluster.backbone.models import background_job, device_variable, device
from initat.cluster.backbone.server_enums import icswServiceEnum
from initat.cluster.frontend.helper_functions import contact_server, xml_wrapper
from initat.tools import server_command

logger = logging.getLogger("cluster.main")


class get_number_of_background_jobs(View):
    @method_decorator(login_required)
    def post(self, request):
        request.session["latest_contact"] = datetime.datetime.now()
        _return = {
            "background_jobs": background_job.objects.get_number_of_pending_jobs()
        }
        return HttpResponse(json.dumps(_return), content_type="application/json")


class get_cluster_info(View):
    def post(self, request):
        _info_dict = {
            "CLUSTER_NAME": "",
            "CLUSTER_ID": "",
            "DATABASE_VERSION": settings.ICSW_DATABASE_VERSION,
            "SOFTWARE_VERSION": settings.ICSW_SOFTWARE_VERSION,
            "MODELS_VERSION": settings.ICSW_MODELS_VERSION,
            "GOOGLE_MAPS_KEY": settings.ICSW_GOOGLE_MAPS_KEY,
        }
        for _key, _value in device_variable.objects.values_list("name", "val_str").filter(
            Q(name__in=["CLUSTER_NAME", "CLUSTER_ID"]) &
            Q(device__device_group__cluster_device_group=True)
        ):
            _info_dict[_key] = _value
        return HttpResponse(json.dumps(_info_dict), content_type="application/json")


class get_docu_info(View):
    def post(self, request):
        HANDBOOK_DIR = "/opt/cluster/share/doc/handbook"
        _info_dict = {
            "HANDBOOK_PDF_PRESENT": bool(glob.glob(os.path.join(HANDBOOK_DIR, "*.pdf"))),
            "HANDBOOK_CHUNKS_PRESENT": bool(glob.glob(os.path.join(HANDBOOK_DIR, "*chunk"))),
        }
        return HttpResponse(json.dumps(_info_dict), content_type="application/json")


class get_overall_style(View):
    def post(self, request):
        return HttpResponse(
            json.dumps(
                {
                    "overall_style": settings.ICSW_OVERALL_STYLE
                }
            ),
            content_type="application/json"
        )


class get_routing_info(View):
    # @method_decorator(login_required)
    def get(self, request):
        cur_routing = routing.SrvTypeRouting(force="force" in request.POST)
        _return = {
            "service_types": {key: True for key in routing.SrvTypeRouting().service_types},
            "routing": cur_routing.resolv_dict,
            "local_device": str(cur_routing.local_device.full_name) if cur_routing.local_device is not None else None,
            "internal_dict": cur_routing.internal_dict,
            "unroutable_configs": cur_routing.unroutable_configs,
        }
        return HttpResponse(json.dumps(_return), content_type="application/json")


class get_server_info(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        cur_routing = routing.SrvTypeRouting(force=True)
        _server_list = []
        for _server in cur_routing.resolv_dict.get(icswServiceEnum.cluster_server.name, []):
            srv_com = server_command.srv_command(command="server_status")
            _res = contact_server(
                request,
                icswServiceEnum.cluster_server,
                srv_com,
                timeout=10,
                connection_id="server_status",
                target_server_id=_server[2],
            )
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
        # cur_routing = routing.SrvTypeRouting()
        request.xml_response["result"] = contact_server(
            request,
            icswServiceEnum.cluster_server,
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


class RemoteViewerConfigLoader(View):
    @method_decorator(login_required)
    def post(self, request):
        import base64

        device_idx = int(request.POST["device_idx"])

        _device = device.objects.get(idx=device_idx)
        device_group = _device.device_group.device

        ssh_password = None
        ssh_username = None
        for obj in [device_group, _device]:
            try:
                ssh_password = obj.device_variable_set.get(name="SSH_PASSWORD").get_value()
            except device_variable.DoesNotExist:
                pass

            try:
                ssh_username = obj.device_variable_set.get(name="SSH_USERNAME").get_value()
            except device_variable.DoesNotExist:
                pass

        host = None
        ips = _device.all_ips()
        if ips:
            host = ips[0]

        config_str = None
        if host and ssh_password and ssh_username:
            config = {
                "host": host,
                "ssh_username": ssh_username,
                "ssh_password": ssh_password
            }
            config_str = json.dumps(config)

        return HttpResponse(json.dumps({"config_str": config_str}))
