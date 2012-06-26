#!/usr/bin/python-init -Ot
# -*- coding: utf-8 -*-

""" config views """

import logging_tools
from init.cluster.frontend.forms import new_config_type_form
from init.cluster.backbone.models import new_config_type
from django.db.models import Q
from init.cluster.frontend.helper_functions import init_logging
from init.cluster.frontend.render_tools import render_me
from django.contrib.auth.decorators import login_required
from django.template.loader import render_to_string
from django.forms.models import modelformset_factory

@init_logging
@login_required
def show_config_type_options(request):
    config_type_formset = modelformset_factory(new_config_type, form=new_config_type_form, can_delete=True, extra=1)
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
