#!/usr/bin/python -Ot
# -*- coding: utf-8 -*-
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2012 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
# 
# This file belongs to webfrontend
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

import logging_tools
from init.cluster.frontend.forms import network_form, device_location_form, device_class_form
from init.cluster.backbone.models import device_location, device_class
from django.db.models import Q
from django.template.loader import render_to_string
from django.forms.models import modelformset_factory

def show_options(req):
    request = req.request
    dev_location_formset = modelformset_factory(device_location, form=device_location_form, can_delete=True, extra=1)
    dev_class_formset = modelformset_factory(device_class, form=device_class_form, can_delete=True, extra=1)
    if request.method == "POST" and "ds" not in request.POST:
        cur_location_fs = dev_location_formset(request.POST, request.FILES, prefix="location")
        if cur_location_fs.is_valid():
            if cur_location_fs.save() or cur_location_fs.deleted_forms:
                cur_location_fs = dev_location_formset(prefix="location")
        cur_class_fs = dev_class_formset(request.POST, request.FILES, prefix="class")
        if cur_class_fs.is_valid():
            if cur_class_fs.save() or cur_class_fs.deleted_forms:
                cur_class_fs = dev_class_formset(prefix="class")
    else:
        cur_location_fs = dev_location_formset(prefix="location")
        cur_class_fs = dev_class_formset(prefix="class")
    req.write(render_to_string("device_class_location.html", {
        "device_class_formset"    : cur_class_fs,
        "device_location_formset" : cur_location_fs}))
