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
from init.cluster.frontend.forms import new_config_type_form
from init.cluster.backbone.models import new_config_type
from django.db.models import Q
from django.template.loader import render_to_string
from django.forms.models import modelformset_factory

def show_config_type_options(req):
    request = req.request
    config_type_formset = modelformset_factory(new_config_type, form=new_config_type_form, can_delete=True, extra=1)
    if request.method == "POST" and "ds" not in request.POST:
        cur_ct_fs = config_type_formset(request.POST, request.FILES)
        if cur_ct_fs.is_valid():
            if cur_ct_fs.save() or cur_ct_fs.deleted_forms:
                # re-read formsets after successfull save or delete
                cur_ct_fs = config_type_formset()
    else:
        cur_ct_fs = config_type_formset()
    req.write(render_to_string("cluster_config_type.html", {
        "config_type_formset" : cur_ct_fs}))
