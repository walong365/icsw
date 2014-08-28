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

from django.contrib.auth import login, logout, authenticate
from django.core.urlresolvers import reverse
from django.db.models import Q, Sum
from django.http import HttpResponseRedirect
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.generic import View
from initat.cluster.backbone.models import cluster_setting, user, device_variable
from initat.cluster.backbone.render import render_me
from initat.cluster.frontend.forms import authentication_form
from initat.cluster.frontend.helper_functions import update_session_object
import base64
import json
import logging

logger = logging.getLogger("cluster.setup")


class redirect_to_main(View):
    @method_decorator(never_cache)
    def get(self, request):
        return HttpResponseRedirect(reverse("session:login"))


def _get_login_screen_type():
    try:
        cur_cs = cluster_setting.objects.get(Q(name='GLOBAL'))
    except cluster_setting.DoesNotExist:
        _lst = "big"
    else:
        _lst = cur_cs.login_screen_type
    return _lst


def _get_login_hints():
    # show login hints ?
    _hints, _valid = ([], True)
    if user.objects.all().count() < 3:
        for _user in user.objects.all().order_by("login"):
            user_name = _user.login
            _user_valid = False
            for ck_pwd in [user_name, "{}{}".format(user_name, user_name)]:
                if authenticate(username=user_name, password=ck_pwd) is not None:
                    _hints.append((user_name, ck_pwd, _user.is_superuser))
                    _user_valid = True
            if not _user_valid:
                _valid = False
    if not _valid:
        _hints = []
    return json.dumps(_hints)


def _get_cluster_name():
    try:
        c_name = device_variable.objects.values_list("val_str", flat=True).get(
            Q(name="CLUSTER_NAME") &
            Q(device__device_group__cluster_device_group=True))
    except device_variable.DoesNotExist:
        return ""
    else:
        return c_name


def login_page(request, **kwargs):
        return render_me(request, "login.html", {
            "CLUSTER_NAME": _get_cluster_name(),
            "LOGIN_SCREEN_TYPE": _get_login_screen_type(),
            "login_form": kwargs.get("login_form", authentication_form()),
            "from_logout": kwargs.get("from_logout", False),
            "login_hints": _get_login_hints(),
            "app_path": reverse("session:login")
            }
        )()


class sess_logout(View):
    def get(self, request):
        from_logout = request.user.is_authenticated()
        logout(request)
        return login_page(request, from_logout=from_logout)


def _login(request, _user_object, login_form=None):
    login(request, _user_object)
    request.session["user_vars"] = dict([(user_var.name, user_var) for user_var in _user_object.user_variable_set.all()])
    # for alias logins login_name != login
    if login_form is not None:
        request.session["login_name"] = login_form.get_login_name()
        request.session["password"] = base64.b64encode(login_form.cleaned_data.get("password").decode("utf-8"))
    else:
        request.session["login_name"] = _user_object.login
    _user_object.login_count += 1
    _user_object.save(update_fields=["login_count"])
    update_session_object(request)


class sess_login(View):
    def get(self, request):
        if user.objects.all().count():
            if user.objects.all().aggregate(total_logins=Sum("login_count"))["total_logins"] == 0:
                first_user = authenticate(username=user.objects.all().values_list("login", flat=True)[0], password="AUTO_LOGIN")
                if first_user is not None:
                    _login(request, first_user)
                    return HttpResponseRedirect(reverse("user:account_info"))
        return login_page(request)

    def post(self, request):
        _post = request.POST
        login_form = authentication_form(data=_post)
        if login_form.is_valid():
            db_user = login_form.get_user()
            _login(request, db_user, login_form)
            return HttpResponseRedirect(reverse("main:index"))
        return login_page(request, login_form=login_form)
