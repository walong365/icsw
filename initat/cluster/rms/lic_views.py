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
from django.http.response import HttpResponse
from initat.cluster.backbone.render import render_me
from initat.cluster.frontend.helper_functions import contact_server, xml_wrapper
from initat.cluster.rms.rms_addons import *  # @UnusedWildImport
from initat.cluster.backbone.models import ext_license_check_coarse
from lxml import etree  # @UnresolvedImport @UnusedImport
import json  # @UnusedImport
import pprint  # @UnusedImport
import server_command
import datetime


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
        result = contact_server(request, "rms", srv_com, timeout=10)
        _lic_dump = {}
        if result is not None:
            result = result.tree

            _start_node = result.xpath(".//*[local-name() = 'license_usage']")
            if len(_start_node):
                _lic_dump = _dump_xml(_start_node[0])
        request.xml_response["result"] = result


#    @method_decorator(login_required)
class get_license_overview_steps(View):
    def post(self, request):
        _post = request.POST
        steps = lic_utils.get_steps(_post['duration_type'], _post['date'])
        return HttpResponse(json.dumps(steps), content_type="application/json")

    def get(self, request):

        return HttpResponse(json.dumps(steps), content_type="application/json")

class lic_utils(object):

    @staticmethod
    def parse_date(date):
        return datetime.datetime.fromtimestamp(int(date))

    @staticmethod
    def parse_duration(in_duration_type, date):
        '''
        :param str in_duration_type:
        :param str date: timestamp from request
        :return: tuple (unit of data to display, start, end)
        '''
        date = lic_utils.parse_date(date)
        if in_duration_type == "day":
            duration_type = ext_license_check_coarse.Duration.Hour
            start = ext_license_check_coarse.Duration.Day.get_time_frame_start(date)
            end = ext_license_check_coarse.Duration.Day.get_end_time_for_start(start) - datetime.timedelta(seconds=1)
        elif in_duration_type == "week":
            duration_type = ext_license_check_coarse.Duration.Day
            date_as_date = date.date()  # forget time
            date_day = datetime.datetime(year=date_as_date.year, month=date_as_date.month, day=date_as_date.day)
            start = date_day - datetime.timedelta(days=date_day.weekday())
            end = start + datetime.timedelta(days=7) - datetime.timedelta(seconds=1)
        elif in_duration_type == "month":
            duration_type = ext_license_check_coarse.Duration.Day
            start = ext_license_check_coarse.Duration.Month.get_time_frame_start(date)
            end = ext_license_check_coarse.Duration.Month.get_end_time_for_start(start) - datetime.timedelta(seconds=1)
        elif in_duration_type == "year":
            duration_type = ext_license_check_coarse.Duration.Month
            start = datetime.datetime(year=date.year, month=1, day=1)
            end = datetime.datetime(year=date.year+1, month=1, day=1) - datetime.timedelta(seconds=1)
        return (duration_type, start, end)

    @staticmethod
    def get_steps(in_duration_type, date):
        (duration_type, start, end) = lic_utils.parse_duration(in_duration_type, date)

        steps = []
        cur = start

        while cur < end:
            steps.append({"date": duration_type.get_display_date(cur), "full_date": cur.isoformat()})
            cur = duration_type.get_end_time_for_start(cur) + datetime.timedelta(seconds=1)

        return steps
