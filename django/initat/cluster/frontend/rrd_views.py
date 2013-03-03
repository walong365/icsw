#!/usr/bin/python-init -Ot
# -*- coding: utf-8 -*-

""" RRD views """

import json
import pprint
import logging_tools
import process_tools
from initat.cluster.frontend.helper_functions import init_logging
from initat.core.render import render_me
from django.contrib.auth.decorators import login_required
from lxml import etree
from lxml.builder import E
from django.db.models import Q
from django.core.exceptions import ValidationError
from initat.cluster.backbone.models import rrd_rra, rrd_class, ALLOWED_CFS
import server_command
import net_tools
import time

@login_required
@init_logging
def class_overview(request):
    if request.method == "GET":
        return render_me(
            request, "rrd_class_overview.html",
        )()
    else:
        xml_resp = E.response(
            E.rrd_classes(*[
                cur_rc.get_xml() for cur_rc in rrd_class.objects.all()
            ]),
            E.rrd_rras(*[
                cur_rra.get_xml() for cur_rra in rrd_rra.objects.all()
            ]),
            E.rra_cfs(*[
                E.rra_cf(cur_cf, pk=cur_cf) for cur_cf in ALLOWED_CFS
            ])
        )
        request.xml_response["response"] = xml_resp
        return request.xml_response.create_response()
