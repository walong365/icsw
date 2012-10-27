#!/usr/bin/python-init -Ot
# -*- coding: utf-8 -*-

""" boot views """

import json
import pprint
import logging_tools
import process_tools
from initat.cluster.frontend.helper_functions import init_logging
from initat.cluster.frontend.render_tools import render_me
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from initat.cluster.backbone.models import device_type, device_group, device, device_class, kernel
from django.core.exceptions import ValidationError
from lxml import etree
from lxml.builder import E
from django.db.models import Q
import server_command
import re
import time
import net_tools
from django.core.urlresolvers import reverse

@login_required
@init_logging
def show_boot(request):
    return render_me(
        request, "boot_overview.html",
    )()

OPTION_LIST = [("k", "kernel"),
               ("i", "image")]
@login_required
@init_logging
def get_html_options(request):
    xml_resp = E.options()
    for short, long_opt in OPTION_LIST:
        xml_resp.append(E.option(long_opt, short=short))
    request.xml_response["response"] = xml_resp
    return request.xml_response.create_response()

@login_required
@init_logging
def get_boot_info(request):
    _post = request.POST
    pprint.pprint(_post)
    option_dict = dict([(short, True if _post.get("opt_%s" % (short)) in ["true"] else False) for short, long_opt in OPTION_LIST])
    pprint.pprint(option_dict)
    sel_list = _post.getlist("sel_list[]")
    dev_result = device.objects.filter(Q(name__in=sel_list))
    srv_com = server_command.srv_command(command="status")
    srv_com["devices"] = srv_com.builder(
        "devices",
        *[srv_com.builder("device", pk="%d" % (cur_dev.pk)) for cur_dev in dev_result])
    result = net_tools.zmq_connection("boot_webfrontend", timeout=10).add_connection("tcp://localhost:8000", srv_com)
    if not result:
        request.log("error contacting server", logging_tools.LOG_LEVEL_ERROR, xml=True)
    else:
        pass
    xml_resp = E.boot_info()
    def_dict = {"network"       : "unknown",
                "network_state" : "error"}
    for cur_dev in dev_result:
        dev_info = cur_dev.get_xml(full=False)
        for cur_info in ["recvstate", "reqstate"]:
            dev_info.attrib[cur_info] = getattr(cur_dev, cur_info)
        if result is not None:
            # copy from mother
            dev_node = result.xpath(None, ".//ns:device[@pk='%d']" % (cur_dev.pk))
            if len(dev_node):
                dev_node = dev_node[0]
            else:
                dev_node = None
        else:
            dev_node = None
        if dev_node is not None:
            dev_info.attrib.update(dict([(key, dev_node.attrib.get(key, value)) for key, value in def_dict.iteritems()]))
        else:
            dev_info.attrib.update(def_dict)
        xml_resp.append(dev_info)
    # add option-dict related stuff
    if option_dict["k"]:
        kernels = E.kernels()
        for cur_k in kernel.objects.filter(Q(enabled=True)).order_by("bitcount", "name"):
            kernels.append(cur_g.get_xml())
        xml_resp.append(kernels)
    request.xml_response["response"] = xml_resp
    return request.xml_response.create_response()
