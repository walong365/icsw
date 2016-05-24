#!/usr/bin/python -Ot
#
# -*- coding: utf-8 -*-
#
# Copyright (C) 2016 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
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

""" auth views for nginx """

import logging
import pprint

from django.views.generic import View
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
import base64
import time
import bz2
import pickle
from django.template import Template
from initat.tools import process_tools
from django.template.loader import render_to_string
from django.template import RequestContext

logger = logging.getLogger("cluster.auth")

# hack for next


class MyCookie(dict):
    def __init__(self, src=None):
        if src:
            _dict = pickle.loads(bz2.decompress(base64.b64decode(src)))
            self.update(_dict)

    def __str__(self):
        return base64.b64encode(bz2.compress(pickle.dumps(self)))


class auth_user(View):
    def get(self, request):
        _ok = False
        if "AUTH_COOKIE" in request.COOKIES:
            try:
                _cookie = MyCookie(request.COOKIES["AUTH_COOKIE"])
                _init_time = _cookie["init"]
            except:
                print process_tools.get_except_info()
                return HttpResponse("Unauthorized", status=401)
            else:
                if abs(_init_time - time.time()) < 3:
                    _ok = True
        if _ok:
            return HttpResponse("Ok", status=200)
        else:
            # pprint.pprint([(k, v) for k, v in request.META.iteritems() if k.count("HTTP")])
            _resp = HttpResponse("Unauthorized", status=401)
            return _resp


class do_login(View):

    def get(self, request):
        # print csrf.get_token()
        _req = RequestContext(request)
        # pprint.pprint([(k, v) for k, v in request.META.iteritems() if k.count("HTTP")])
        # pprint.pprint(request.META)
        _temp = Template(
            '<!DOCTYPE html><html lang="en"><head></head>' +
            '<body><form action="/auth/auth/do_login" method="post">' +
            '{% csrf_token %}' +
            'Name: <input type="text" name="user" value="test"/><br/>' +
            'Password <input type="password" name="password" value="pwd"/><br/>' +
            '<input type="hidden" name="next" value="{}" />'.format(request.META["HTTP_X_ORIGINAL_URI"]) +
            '<input type="submit" value="Submit"/>' +
            '</form></body></html>'
        )
        _html = _temp.render(_req)
        _resp = HttpResponse(_html)
        return _resp

    def post(self, request):
        # print request.GET, request.POST["name"]
        _user, _passwd = (request.POST["user"], request.POST["password"])

        response = HttpResponseRedirect("/atest")
        _cookie = MyCookie()
        _cookie["user"] = "abc"
        _cookie["init"] = int(time.time())
        response.set_cookie("AUTH_COOKIE", str(_cookie))
        return response
