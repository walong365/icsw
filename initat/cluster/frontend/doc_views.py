# -*- coding: utf-8 -*-
#
# Copyright (C) 2014 Andreas Lang-Nevyjel
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

""" views for dynamic docu"""

from django.conf import settings
from django.http.response import HttpResponse
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import View
import logging
import os

logger = logging.getLogger("cluster.main")

class doc_page(View):
    @method_decorator(login_required)
    def get(self, request, page):
        if page.startswith("images/"):
            # dirty hack
            return HttpResponse(file(os.path.join(settings.HANDBOOK_DIR, page), "rb").read())
        elif page.endswith(".css"):
            return HttpResponse(file(os.path.join(settings.HANDBOOK_DIR, "chunks", page), "rb").read())
        else:
            if page.endswith(".xhtml"):
                page = page.split(".")[0]
            return HttpResponse(file(settings.HANDBOOK_CHUNKS[page], "r").read())
