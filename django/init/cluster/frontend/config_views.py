#!/usr/bin/python-init -Ot
# -*- coding: utf-8 -*-

""" config views """

import logging_tools
from init.cluster.frontend.forms import config_type_form
from init.cluster.backbone.models import config_type, config
from django.db.models import Q
from init.cluster.frontend.helper_functions import init_logging
from init.cluster.frontend.render_tools import render_me
from django.contrib.auth.decorators import login_required
from django.template.loader import render_to_string
from django.forms.models import modelformset_factory
from lxml import etree
from lxml.builder import E

@init_logging
@login_required
def show_config_type_options(request):
    config_type_formset = modelformset_factory(config_type, form=config_type_form, can_delete=True, extra=1)
    if request.method == "POST" and "ds" not in request.POST:
        cur_ct_fs = config_type_formset(request.POST, request.FILES)
        if cur_ct_fs.is_valid():
            if cur_ct_fs.save() or cur_ct_fs.deleted_forms:
                # re-read formsets after successfull save or delete
                cur_ct_fs = config_type_formset()
    else:
        cur_ct_fs = config_type_formset()
    return render_me(request, "cluster_config_type.html", {
        "config_type_formset" : cur_ct_fs})()

@login_required
@init_logging
def show_configs(request):
    return render_me(
        request, "config_overview.html",
    )()

@login_required
@init_logging
def get_configs(request):
    all_configs = config.objects.all().select_related("config_type").order_by("name")
    xml_resp = E.config_list(
        *[cur_c.get_xml() for cur_c in all_configs]
    )
    request.xml_response["response"] = xml_resp
    return request.xml_response.create_response()
    