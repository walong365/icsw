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

from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import View
from initat.cluster.backbone.render import render_me
from initat.cluster.frontend.helper_functions import contact_server, xml_wrapper
from initat.cluster.rms.rms_addons import *  # @UnusedWildImport
from lxml import etree  # @UnresolvedImport @UnusedImport
import json  # @UnusedImport
import pprint  # @UnusedImport
import server_command


class overview(View):
    @method_decorator(login_required)
    def get(self, request):
        return render_me(request, "lic_overview.html")()


def _dump_xml(s_node):
    return (
        s_node.tag.split("}")[-1],
        {
            _key: int(_value) if _value.isdigit() else _value for _key, _value in s_node.attrib.iteritems()
        },
        [
            _dump_xml(_child) for _child in s_node
        ]
    )


class license_liveview(View):
    @method_decorator(login_required)
    def get(self, request):
        return render_me(request, "rms_license_liveview.html")

    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        srv_com = server_command.srv_command(command="get_license_usage")
        result = contact_server(request, "rms", srv_com, timeout=10).tree

        _start_node = result.xpath(".//*[local-name() = 'license_usage']")
        if len(_start_node):
            _lic_dump = _dump_xml(_start_node[0])
        else:
            _lic_dump = {}
        request.xml_response["result"] = result
