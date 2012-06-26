#!/usr/bin/python-init -Ot
# -*- coding: utf-8 -*-

""" network views """

import json
import pprint
import logging_tools
import process_tools
from init.cluster.frontend.helper_functions import init_logging
from init.cluster.frontend.render_tools import render_me
from django.contrib.auth.decorators import login_required
from lxml import etree
from lxml.builder import E
from django.db.models import Q
from init.cluster.frontend.render_tools import render_me
from init.cluster.frontend.forms import network_form, network_type_form, network_device_type_form
from init.cluster.backbone.models import device, device_selection, device_device_selection, network, net_ip, \
     network_type, network_device_type
from django.db import IntegrityError
from django.http import HttpResponse, HttpResponseRedirect
from django.template.loader import render_to_string
from django.forms.models import modelformset_factory

@init_logging
@login_required
def show_netdevice_classes(request):
    network_type_formset = modelformset_factory(network_type, form=network_type_form, can_delete=True, extra=1)
    network_dt_formset   = modelformset_factory(network_device_type, form=network_device_type_form, can_delete=True, extra=1)
    if request.method == "POST" and "ds" not in request.POST:
        cur_type_fs = network_type_formset(request.POST, request.FILES, prefix="type")
        if cur_type_fs.is_valid():
            if cur_type_fs.save() or cur_type_fs.deleted_forms:
                cur_type_fs = network_type_formset(prefix="type")
        cur_dt_fs = network_dt_formset(request.POST, request.FILES, prefix="devtype")
        if cur_dt_fs.is_valid():
            if cur_dt_fs.save() or cur_dt_fs.deleted_forms:
                cur_dt_fs = network_dt_formset(prefix="devtype")
    else:
        cur_type_fs = network_type_formset(prefix="type")
        cur_dt_fs   = network_dt_formset(prefix="devtype")
    return render_me(request, "cluster_network_types.html", {
        "network_type_formset"    : cur_type_fs,
        "network_devtype_formset" : cur_dt_fs})()

@init_logging
@login_required
def show_cluster_networks(request):
    network_formset = modelformset_factory(network, form=network_form, can_delete=True, extra=1)
    if request.method == "POST" and "ds" not in request.POST:
        cur_fs = network_formset(request.POST, request.FILES)
        if cur_fs.is_valid():
            if cur_fs.save() or cur_fs.deleted_forms:
                # re-read formsets after successfull save or delete
                cur_fs = network_formset()
    else:
        cur_fs = network_formset()
    return render_me(request, "cluster_networks.html", {
        "network_formset" : cur_fs})()
