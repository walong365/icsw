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
from initat.cluster.backbone.models import device_type, device_group, device, device_class
from django.core.exceptions import ValidationError
from lxml import etree
from lxml.builder import E
from django.db.models import Q
import re
import time
from django.core.urlresolvers import reverse

@login_required
@init_logging
def show_boot(request):
    return render_me(
        request, "boot_overview.html",
    )()
