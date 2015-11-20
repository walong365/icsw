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

from django.contrib.auth import login, logout, authenticate
from django.core.exceptions import ValidationError
from django.http.response import HttpResponse
from django.core.urlresolvers import reverse
from django.core.cache import cache
from django.db.models import Q, Sum
from django.http import HttpResponseRedirect
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.generic import View
import django

from initat.tools import config_store
from initat.constants import GEN_CS_NAME
from initat.cluster.backbone.models import user, login_history
from initat.cluster.backbone.render import render_me
from initat.cluster.frontend.helper_functions import xml_wrapper

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
    return _hints


def login_page(request, **kwargs):
    # this is checked in sess_login
    request.session.set_test_cookie()
    # store next url
    _ckey = "_NEXT_URL_{}".format(request.META["REMOTE_ADDR"])
    cache.set(_ckey, kwargs.get("next", ""), 15)
    return render_me(
        request,
        "login.html",
        {
            "from_logout": kwargs.get("from_logout", False),
            # "app_path": reverse("session:login"),
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
        _user.login_fail_count += 1
        _user.save(update_fields=["login_count", "login_fail_count"])


def _login(request, _user_object, login_credentials=None):
    login(request, _user_object)
    login_history.login_attempt(_user_object, request, True)
    request.session["user_vars"] =\
        dict([(user_var.name, user_var) for user_var in _user_object.user_variable_set.all()])
    # for alias logins login_name != login
    if login_credentials is not None:
        real_user_name, login_password, login_name = login_credentials
        request.session["login_name"] = login_name
        request.session["password"] = base64.b64encode(login_password.decode("utf-8"))
    else:
        request.session["login_name"] = _user_object.login
    _user_object.login_count += 1
    _user_object.save(update_fields=["login_count"])


class login_addons(View):
    @method_decorator(xml_wrapper)
    def post(self, request):
        # django version
        _vers = []
        for _v in django.VERSION:
            if type(_v) == int:
                _vers.append("{:d}".format(_v))
            else:
                break
        _ckey = "_NEXT_URL_{}".format(request.META["REMOTE_ADDR"])
        _next_url = cache.get(_ckey)
        cache.delete(_ckey)
        _cs = config_store.ConfigStore(GEN_CS_NAME, quiet=True)
        request.xml_response["login_hints"] = json.dumps(_get_login_hints())
        request.xml_response["login_screen_type"] = _cs["login.screen.type"]
        request.xml_response["django_version"] = ".".join(_vers)
        request.xml_response["next_url"] = _next_url or ""
        request.xml_response["password_character_count"] = "{:d}".format(_cs["password.character.count"])


class sess_login(View):
    def get(self, request):
        if request.user.is_authenticated():
            # return HttpResponseRedirect(reverse("user:account_info"))
            return HttpResponseRedirect(reverse("main:index"))
        else:
            if user.objects.all().count():  # @UndefinedVariable
                if user.objects.all().aggregate(total_logins=Sum("login_count"))["total_logins"] == 0:
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
        login_name = _post.get('username')
        login_password = _post.get('password')

        real_user_name = self.__class__.get_real_user_name(login_name)

        try:
            db_user = self.__class__._check_login_data(request, real_user_name, login_password)
        except ValidationError as e:
            for err_msg in e:
                request.xml_response.error(unicode(err_msg))
            _failed_login(request, real_user_name)
        else:
            login_credentials = (real_user_name, login_password, login_name)
            _login(request, db_user, login_credentials)
            if _post.get("next_url", "").strip():
                request.xml_response["redirect"] = _post["next_url"]
            else:
                request.xml_response["redirect"] = reverse("main:index")

    @classmethod
    def _check_login_data(cls, request, username, password):
        """Returns a valid user instance to be logged in or raises ValidationError"""
        if username and password:
            db_user = authenticate(username=username, password=password)
            if db_user is None:
                raise ValidationError(
                    "Please enter a correct username and password. " +
                    "Note that both fields are case-sensitive."
                )
            if db_user is not None and not db_user.is_active:
                raise ValidationError("This account is inactive.")
        else:
            raise ValidationError("Need username and password")
        # TODO: determine whether this should be moved to its own method.
        if request:
            if not request.session.test_cookie_worked():
                raise ValidationError("Your Web browser doesn't appear to have cookies enabled. " +
                                      "Cookies are required for logging in.")

        assert db_user is not None
        return db_user

    @classmethod
    def get_real_user_name(cls, username):
        """Resolve aliases"""
        _all_users = user.objects.all()  # @UndefinedVariable
        all_aliases = [
            (
                login_name,
                [_entry for _entry in al_list.strip().split() if _entry not in [None, "None"]]
            ) for login_name, al_list in _all_users.values_list(
                "login", "aliases"
            ) if al_list is not None and al_list.strip()
        ]
        rev_dict = {}
        all_logins = [login_name for login_name, al_list in all_aliases]
        for pk, al_list in all_aliases:
            for cur_al in al_list:
                if cur_al in rev_dict:
                    raise ValidationError("Alias '{}' is not unique".format(cur_al))
                elif cur_al in all_logins:
                    # ignore aliases which are also logins
                    pass
                else:
                    rev_dict[cur_al] = pk
        if username in rev_dict:
            real_user_name = rev_dict[username]
        else:
            real_user_name = username
        return real_user_name


class get_user(View):
    def post(self, request):
        if request.user and not request.user.is_anonymous:
            _user = {
                "idx": request.user.pk,
                "pk": request.user.pk,
                "is_superuser": request.user.is_superuser,
                "authenticated": True,
                "login": request.user.login,
                "login_name": request.session["login_name"],
                "full_name": unicode(request.user),
            }
        else:
            _user = {
                "is_superuser": False,
                "authenticated": False,
            }
        return HttpResponse(json.dumps(_user), content_type="application/json")
