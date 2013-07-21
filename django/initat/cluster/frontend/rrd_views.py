#!/usr/bin/python-init -Ot
# -*- coding: utf-8 -*-

""" RRD views """

import datetime
import logging
import pprint
import server_command
from lxml import etree
from lxml.builder import E

from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import View
from initat.core.render import render_me
from initat.cluster.frontend.helper_functions import xml_wrapper, contact_server

logger = logging.getLogger("cluster.rrd")

class device_rrds(View):
    # @method_decorator(login_required)
    # def get(self, request):
    #    return render_me(
    #        request, "rrd_class_overview.html",
    #    )()
    @method_decorator(xml_wrapper)
    def post(self, request):
        srv_com = server_command.srv_command(command="get_node_rrd")
        dev_pks = request.POST.getlist("pks[]")
        srv_com["device_list"] = E.device_list(
            *[E.device(pk="%d" % (int(dev_pk))) for dev_pk in dev_pks],
            merge_results="1"
        )
        result = contact_server(request, "tcp://localhost:8003", srv_com, timeout=30)
        if result:
            node_results = result.xpath(None, ".//node_results")
            if len(node_results):
                node_results = node_results[0]
                if len(node_results):
                    # first device
                    node_result = node_results[0]
                    request.xml_response["result"] = node_result
                else:
                    request.xml_response.error("no node_results", logger=logger)
            else:
                request.xml_response.error("no node_results", logger=logger)

class graph_rrds(View):
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        srv_com = server_command.srv_command(command="graph_rrd")
        pk_list, graph_keys = (_post.getlist("pks[]"), set(_post.getlist("keys[]")))
        srv_com["device_list"] = E.device_list(
            *[E.device(pk="%d" % (int(dev_pk))) for dev_pk in pk_list]
        )
        srv_com["graph_key_list"] = E.graph_key_list(
            *[E.graph_key(graph_key) for graph_key in graph_keys if not graph_key.startswith("_")]
        )
        dt_1970 = datetime.datetime(1970, 1, 1)
        if "start_time" in _post:
            start_time = datetime.datetime.strptime(_post["start_time"], "%Y-%m-%d %H:%M")
            end_time = datetime.datetime.strptime(_post["end_time"], "%Y-%m-%d %H:%M")
        else:
            start_time = datetime.datetime.now() - datetime.timedelta(4 * 3600)
            end_time = datetime.datetime.now()
        srv_com["parameters"] = E.parameters(
            E.start_time(_post.get("start_time",
                                   start_time.strftime("%Y-%m-%d %H:%M"))),
            E.end_time(_post.get("end_time",
                                end_time.strftime("%Y-%m-%d %H:%M"))),
            E.size(_post.get("size", "400x200"))
        )
        result = contact_server(request, "tcp://localhost:8003", srv_com, timeout=30)
        if result:
            graph_list = result.xpath(None, ".//graph_list")
            if len(graph_list):
                graph_list = graph_list[0]
                if len(graph_list):
                    # first device
                    request.xml_response["result"] = graph_list
                else:
                    request.xml_response.error("no node_results", logger=logger)
            else:
                request.xml_response.error("no node_results", logger=logger)
