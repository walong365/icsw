# -*- coding: utf-8 -*-
#
# Copyright (C) 2012-2015 Andreas Lang-Nevyjel
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

import base64
import json
import logging

from django.conf import settings
from django.contrib.auth import login, logout, authenticate
from django.core.urlresolvers import reverse
from django.db.models import Q, Sum
from django.http import HttpResponseRedirect
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.generic import View
from initat.cluster.backbone.models import user, login_history
from initat.cluster.backbone.render import render_me
from initat.cluster.frontend.forms import authentication_form
from initat.cluster.frontend.helper_functions import update_session_object, xml_wrapper
import django

logger = logging.getLogger("cluster.setup")


class redirect_to_main(View):
    @method_decorator(never_cache)
    def get(self, request):
        return HttpResponseRedirect(reverse("session:login"))


def _get_login_hints():
    # show login hints ?
    _hints, _valid = ([], True)
    if user.objects.all().count() < 3:  # @UndefinedVariable
        for _user in user.objects.all().order_by("login"):  # @UndefinedVariable
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


def login_page(request, **kwargs):
    # django version
    _vers = []
    for _v in django.VERSION:
        if type(_v) == int:
            _vers.append("{:d}".format(_v))
        else:
            break
    return render_me(
        request,
        "login.html",
        {
            "from_logout": kwargs.get("from_logout", False),
            # "login_hints": _get_login_hints(),
            # "app_path": reverse("session:login"),
            "LOGIN_SCREEN_TYPE": {"big": "big", "medium": "medium"}.get(settings.LOGIN_SCREEN_TYPE, "big"),
            "LOGIN_HINTS": _get_login_hints(),
            "DJANGO_VERSION": ".".join(_vers),
            "NEXT_URL": kwargs.get("next", ""),
        }
    )()


class sess_logout(View):
    def get(self, request):
        from_logout = request.user.is_authenticated()
        logout(request)
        return login_page(request, from_logout=from_logout)


def _failed_login(request, user_name):
    try:
        _user = user.objects.get(Q(login=user_name))  # @UndefinedVariable
    except user.DoesNotExist:  # @UndefinedVariable
        pass
    else:
        login_history.login_attempt(_user, request, False)


def _login(request, _user_object, login_form=None):
    login(request, _user_object)
    login_history.login_attempt(_user_object, request, True)
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
        if request.user.is_authenticated():
            return HttpResponseRedirect(reverse("main:index"))
        else:
            if user.objects.all().count():  # @UndefinedVariable
                if user.objects.all().aggregate(total_logins=Sum("login_count"))["total_logins"] == 0:  # @UndefinedVariable
                    first_user = authenticate(
                        username=user.objects.all().values_list("login", flat=True)[0],  # @UndefinedVariable
                        password="AUTO_LOGIN"
                    )
                    if first_user is not None:
                        _login(request, first_user)
                        return HttpResponseRedirect(reverse("user:account_info"))
            return login_page(request, next=request.GET.get("next", ""))

    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = json.loads(request.POST["blob"])
        login_form = authentication_form(data=_post)
        if login_form.is_valid():
            db_user = login_form.get_user()
            _login(request, db_user, login_form)
            if _post.get("next_url", "").strip():
                request.xml_response["redirect"] = _post["next_url"]
            else:
                request.xml_response["redirect"] = reverse("main:index")
        else:
            for _key, _value in login_form.errors.iteritems():
                for _str in _value:
                    request.xml_response.error(_str)
            _failed_login(request, login_form.real_user_name)
