# -*- coding: utf-8 -*-
#
# Copyright (C) 2013-2014 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of webfrontend
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

""" License views """

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db.models import Q
from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views.generic import View
from initat.cluster.backbone.models import device, user_variable, rms_job_run
from initat.cluster.backbone.render import render_me
from initat.cluster.backbone.serializers import rms_job_run_serializer
from initat.cluster.frontend.helper_functions import contact_server, xml_wrapper, \
    update_session_object
from initat.cluster.backbone.models.rms import ext_license_state_coarse,\
    ext_license_check_coarse
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from initat.cluster.rms.rms_addons import *  # @UnusedWildImport
from lxml import etree  # @UnresolvedImport @UnusedImport
from lxml.builder import E  # @UnresolvedImport
import json
import logging
import logging_tools
import pprint  # @UnusedImport
import server_command
import sys
import threading
import time
import datetime
from collections import namedtuple


class overview(View):
    @method_decorator(login_required)
    def get(self, request):
        return render_me(request, "lic_overview.html")()

