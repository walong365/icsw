#!/usr/bin/python -Ot
# -*- coding: utf-8 -*-
#
# Copyright (C) 2012-2014 Andreas Lang-Nevyjel
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

""" basic session views """

from django.contrib.auth import login, logout
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.generic import View
from initat.cluster.frontend.forms import authentication_form
from initat.cluster.frontend.helper_functions import update_session_object
from initat.core.render import render_me
import base64
import logging

logger = logging.getLogger("cluster.setup")

class redirect_to_main(View):
    @method_decorator(never_cache)
    def get(self, request):
        return HttpResponseRedirect(reverse("session:login"))

class sess_logout(View):
    def get(self, request):
        from_logout = request.user.is_authenticated()
        logout(request)
        login_form = authentication_form()
        return render_me(request, "login.html", {
            "login_form"  : login_form,
            "from_logout" : from_logout,
            "app_path"    : reverse("session:login")})()

class sess_login(View):
    def get(self, request):
        return render_me(request, "login.html", {
            "login_form" : authentication_form(),
            "app_path"   : reverse("session:login")})()
    def post(self, request):
        _post = request.POST
        login_form = authentication_form(data=_post)
        if login_form.is_valid():
            db_user = login_form.get_user()
            login(request, db_user)
            request.session["password"] = base64.b64encode(login_form.cleaned_data.get("password").decode("utf-8"))
            request.session["user_vars"] = dict([(user_var.name, user_var) for user_var in db_user.user_variable_set.all()])
            # for alias logins login_name != login
            request.session["login_name"] = login_form.get_login_name()
            update_session_object(request)
            return HttpResponseRedirect(reverse("main:index"))
        return render_me(request, "login.html", {
            "login_form" : login_form,
            "app_path"   : reverse("session:login")})()
