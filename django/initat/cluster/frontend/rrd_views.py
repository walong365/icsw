#!/usr/bin/python-init -Ot
# -*- coding: utf-8 -*-

""" RRD views """

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
    #@method_decorator(login_required)
    #def get(self, request):
    #    return render_me(
    #        request, "rrd_class_overview.html",
    #    )()
    @method_decorator(xml_wrapper)
    def post(self, request):
        srv_com = server_command.srv_command(command="get_node_rrd")
        dev_pk = request.POST["pk"]
        srv_com["device_list"] = E.device_list(
            E.device(pk="%d" % (int(dev_pk)))
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
        dev_pk, graph_key = (_post["pk"], _post["key"])
        srv_com["device_list"] = E.device_list(
            E.device(pk="%d" % (int(dev_pk)))
        )
        srv_com["graph_key_list"] = E.graph_key_list(
            E.graph_key(graph_key)
        )
        result = contact_server(request, "tcp://localhost:8003", srv_com, timeout=30)
        if result:
            graph_list = result.xpath(None, ".//graph_list")
            if len(graph_list):
                graph_list = graph_list[0]
                if len(graph_list):
                    # first device
                    res_graph = graph_list[0]
                    request.xml_response["result"] = res_graph
                else:
                    request.xml_response.error("no node_results", logger=logger)
            else:
                request.xml_response.error("no node_results", logger=logger)
