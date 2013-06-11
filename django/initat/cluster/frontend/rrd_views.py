#!/usr/bin/python-init -Ot
# -*- coding: utf-8 -*-

""" RRD views """

import logging
from lxml.builder import E

from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import View

from initat.core.render import render_me
from initat.cluster.frontend.helper_functions import xml_wrapper
from initat.cluster.backbone.models import rrd_rra, rrd_class, ALLOWED_CFS

logger = logging.getLogger("cluster.rrd")

class class_overview(View):
    @method_decorator(login_required)
    def get(self, request):
        return render_me(
            request, "rrd_class_overview.html",
        )()
    @method_decorator(xml_wrapper)
    def post(self, request):
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
