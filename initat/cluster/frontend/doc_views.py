# -*- coding: utf-8 -*-
#
# Copyright (C) 2014-2016 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw-server
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

import logging
import os

from django.conf import settings
from django.http.response import HttpResponse
from django.views.generic import View

logger = logging.getLogger("cluster.doc")


class doc_page(View):
    def get(self, request, page):
        if page.startswith("images/") or page.endswith(".png"):
            # dirty hack
            return HttpResponse(file(os.path.join(settings.HANDBOOK_DIR, page), "rb").read())
        elif page.endswith(".css"):
            return HttpResponse(file(os.path.join(settings.HANDBOOK_DIR, "chunks", page), "rb").read())
        else:
            # TODO: proper system for displaying html documentation
            # return render_me(request, "docu_root.html", {"chunk_name": page})
            return HttpResponse(file(os.path.join(settings.HANDBOOK_DIR, "corvus_handbook.html"), "rb").read())
            # if not page.endswith(".xhtml"):
            #     page = "{}.xhtml".format(page)
            # return render_me(request, "docu_root.html", {"chunk_name": page})
            # if page.endswith(".xhtml"):
            #    page = page.split(".")[0]
            # this won't work anymore // BM 11052015
            # return HttpResponse(file(settings.HANDBOOK_CHUNKS[page], "r").read())


# class test_page(View):
#    def get(self, request):
#        return render_me(request, "docu_root.html", {"chunk_name": "index.xhtml"})
