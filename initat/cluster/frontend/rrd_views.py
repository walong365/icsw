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

""" RRD views """

from django.conf import settings
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from django.http.response import HttpResponse
from django.utils.decorators import method_decorator
from django.views.generic import View
from initat.cluster.frontend.helper_functions import xml_wrapper, contact_server
from initat.cluster.backbone.models import device
from lxml.builder import E  # @UnresolvedImports
import datetime
import dateutil.parser
import dateutil.tz
import json
import logging
import server_command

logger = logging.getLogger("cluster.rrd")


class device_rrds(View):
    @method_decorator(login_required)
    def post(self, request):
        dev_pks = request.POST.getlist("pks[]")
        return _get_node_rrd(request, dev_pks)


class merge_cds(View):
    @method_decorator(login_required)
    def post(self, request):
        dev_pks = [_pk for _pk in request.POST.getlist("pks[]")]
        devs = device.objects.filter(Q(pk__in=dev_pks))
        cd_pks = list(device.objects.filter(Q(device_type__identifier="CD") & Q(master_connections__in=devs)).values_list("pk", flat=True))
        return _get_node_rrd(request, dev_pks + cd_pks)


def _get_node_rrd(request, dev_pks):
    srv_com = server_command.srv_command(command="get_node_rrd")
    srv_com["device_list"] = E.device_list(
        *[E.device(pk="{:d}".format(int(dev_pk))) for dev_pk in dev_pks],
        merge_results="1"
    )
    result, _log_lines = contact_server(request, "grapher", srv_com, timeout=30)
    if result:
        node_results = result.xpath(".//ns:result", smart_strings=False)
        if len(node_results):
            return HttpResponse(node_results[0].text, content_type="application/json")
        return HttpResponse(json.dumps({"error": "no node results"}), content_type="application/json")
    else:
        return HttpResponse(json.dumps({"error": ", ".join([_line for _level, _line in _log_lines])}), content_type="application/json")


class graph_rrds(View):
    def _parse_post_boolean(self, _post, name, default):
        return "1" if _post.get(name, default).lower() in ["1", "true"] else "0"

    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        srv_com = server_command.srv_command(command="graph_rrd")
        pk_list, graph_keys = (
            json.loads(_post["pks"]),
            json.loads(_post["keys"])
        )
        if int(self._parse_post_boolean(_post, "cds_already_merged", "0")):
            cd_pks = list(device.objects.filter(Q(device_type__identifier="CD") & Q(master_connections__in=pk_list)).values_list("pk", flat=True))
        else:
            cd_pks = []
        srv_com["device_list"] = E.device_list(
            *[E.device(pk="{:d}".format(int(dev_pk))) for dev_pk in pk_list + cd_pks]
        )
        srv_com["graph_key_list"] = E.graph_key_list(
            *[E.graph_key(graph_key) for graph_key in graph_keys if not graph_key.startswith("_")]
        )
        if "start_time" in _post:
            start_time = dateutil.parser.parse(_post["start_time"])
            end_time = dateutil.parser.parse(_post["end_time"])
        else:
            start_time = datetime.datetime.now(dateutil.tz.tzutc()) - datetime.timedelta(4 * 3600)
            end_time = datetime.datetime.now(dateutil.tz.tzutc())
        srv_com["parameters"] = E.parameters(
            E.debug_mode("1" if settings.DEBUG else "0"),
            E.start_time(unicode(start_time)),
            E.end_time(unicode(end_time)),
            E.size(_post.get("size", "400x200")),
            E.hide_empty(self._parse_post_boolean(_post, "hide_empty", "0")),
            E.include_zero(self._parse_post_boolean(_post, "include_zero", "0")),
            E.scale_y(self._parse_post_boolean(_post, "scale_y", "0")),
            E.merge_cd(self._parse_post_boolean(_post, "merge_cd", "0")),
            E.job_mode(_post.get("job_mode", "none")),
            E.selected_job(_post.get("selected_job", "0")),
            E.merge_devices(self._parse_post_boolean(_post, "merge_devices", "1")),
            E.timeshift(_post.get("timeshift", "0")),
        )
        result = contact_server(request, "grapher", srv_com, timeout=30)
        if result:
            graph_list = result.xpath(".//graph_list", smart_strings=False)
            if len(graph_list):
                graph_list = graph_list[0]
                if len(graph_list):
                    # first device
                    request.xml_response["result"] = graph_list
                else:
                    request.xml_response.error("no node_results", logger=logger)
            else:
                request.xml_response.error("no node_results", logger=logger)
