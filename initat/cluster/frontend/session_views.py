# -*- coding: utf-8 -*-
#
# Copyright (C) 2012-2016 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw-server
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
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

from __future__ import print_function, unicode_literals

import base64
import datetime
import json
import logging
from importlib import import_module

import django
from django.conf import settings
from django.contrib.auth import login, logout, authenticate
from django.contrib.sessions.backends.cache import KEY_PREFIX
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http.response import HttpResponse
from django.middleware import csrf
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import View
from rest_framework import viewsets
from rest_framework.response import Response
from initat.cluster.backbone.server_enums import icswServiceEnum
from initat.cluster.backbone.middleware import thread_local_middleware, \
    thread_local_obj

from initat.cluster.backbone.models import user, login_history, background_job, RouteTrace
from initat.cluster.backbone.serializers import user_serializer, background_job_serializer
from initat.cluster.frontend.helper_functions import xml_wrapper
from initat.constants import GEN_CS_NAME
from initat.tools import config_store, server_mixins, logging_tools

logger = logging.getLogger("cluster.session")


class get_csrf_token(View):
    @method_decorator(never_cache)
    @csrf_exempt
    def get(self, request):
        return HttpResponse(
            json.dumps({"token": csrf.get_token(request)}),
            content_type="application/json"
        )


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


class SessionHelper(object):
    SESSION_IDLE_TIME = 10

    def __init__(self):
        self._sn_key = "{}_$icsw$_skeys".format(settings.SECRET_KEY_SHORT)
        self._read()
        # session store
        self._sstore = None
        # multiple sessions
        self._multiple_session_keys = []

    def add(self, session_key):
        self._sessions.append(session_key)
        self._write()

    def remove(self, session_key):
        if session_key in self._sessions:
            self._sessions.remove(session_key)
            self._write()

    def get_full_key(self, session):
        return "{}{}".format(KEY_PREFIX, session.session_key)

    def _read(self):
        _cur_vals = cache.get(self._sn_key)
        if _cur_vals is None:
            _cur_vals = []
        else:
            _cur_vals = json.loads(_cur_vals)
        self._sessions = _cur_vals

    def _write(self):
        cache.set(self._sn_key, json.dumps(self._sessions))

    def _ensure_session_store(self):
        if self._sstore is None:
            engine = import_module(settings.SESSION_ENGINE)
            self._sstore = engine.SessionStore()

    def delete_session(self, session_key):
        self._ensure_session_store()
        if session_key.startswith(KEY_PREFIX):
            self._sstore.delete(session_key[len(KEY_PREFIX):])
        else:
            self._sstore.delete(session_key)

    def check_for_multiple_session(self, current_session):
        _now = datetime.datetime.now()
        _dup_session_keys = []
        cur_user_id = current_session["_auth_user_id"]
        _c_key = self.get_full_key(current_session)
        for _key in self.session_keys:
            _content = cache.get(_key)
            if _content is not None and _key != _c_key:
                if _content["_auth_user_id"] == cur_user_id:
                    if "latest_contact" in _content:
                        # check for stale session
                        _diff = (_now - _content["latest_contact"]).total_seconds()
                        if _diff < self.SESSION_IDLE_TIME * 60:
                            _dup_session_keys.append(_key)
                        else:
                            # session is idle for more than SESSION_IDLE_TIME minutes, delete it
                            self.delete_session(_key)
                    else:
                        # old format, always add
                        _dup_session_keys.append(_key)
        self._multiple_session_keys = _dup_session_keys
        return self._multiple_session_keys

    @property
    def session_keys(self):
        return self._sessions


class session_logout(View):
    def post(self, request):
        my_sh = SessionHelper()
        my_sh.remove(my_sh.get_full_key(request.session))
        logout(request)
        return HttpResponse(
            json.dumps(
                {"logout": True}
            ),
            content_type="application/json"
        )


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
    # session names
    my_sh = SessionHelper()
    my_sh.add(my_sh.get_full_key(request.session))
    # check for multiple session
    _dup_keys = my_sh.check_for_multiple_session(request.session)
    # for alias logins login_name != login
    if login_credentials is not None:
        real_user_name, login_password, login_name = login_credentials
        request.session["login_name"] = login_name
        request.session["password"] = base64.b64encode(login_password.decode("utf-8"))
    else:
        request.session["login_name"] = _user_object.login

    # set user in thread_local middleware, otherwise the background job handling would not work
    thread_local_middleware.user = _user_object

    _user_object.login_count += 1
    _user_object.save(update_fields=["login_count"])
    _theme_shorts = [_short for _short, _long in settings.THEMES]
    if _user_object.ui_theme_selection not in _theme_shorts:
        _user_object.ui_theme_selection = _theme_shorts[0]
        _user_object.save()
    # log user

    _cs = config_store.ConfigStore(GEN_CS_NAME, quiet=True)
    _mult_ok = _cs.get("session.multiple.per.user.allowed", False)
    if _mult_ok:
        # multiple sessions ok, report NO multiple sessions
        return 0
    else:
        return len(_dup_keys)


class login_addons(View):
    @method_decorator(xml_wrapper)
    def post(self, request):
        # django version
        _vers = []
        for _v in django.VERSION:
            if isinstance(_v, int):
                _vers.append("{:d}".format(_v))
            else:
                break
        _ckey = "_NEXT_URL_{}".format(request.META["REMOTE_ADDR"])
        _next_url = cache.get(_ckey)
        cache.delete(_ckey)
        _cs = config_store.ConfigStore(GEN_CS_NAME, quiet=True)
        request.xml_response["login_hints"] = json.dumps(_get_login_hints())
        request.xml_response["django_version"] = ".".join(_vers)
        request.xml_response["next_url"] = _next_url or ""
        request.xml_response["theme_default"] = settings.THEME_DEFAULT
        request.xml_response["password_character_count"] = "{:d}".format(_cs["password.character.count"])
        request.xml_response["icsw_databases"] = json.dumps(
            [
                {
                    _key.replace(".", "_"): _value for _key, _value in _entry.iteritems()
                } for _entry in settings.ICSW_DATABASE_DICT.values()
            ]
        )
        request.xml_response["active_database_idx"] = settings.ICSW_ACTIVE_DATABASE_IDX


class change_database(View):
    @method_decorator(xml_wrapper)
    def post(self, request):
        _idx = request.POST["database_idx"]
        _cs = config_store.ConfigStore(GEN_CS_NAME, quiet=True, access_mode=config_store.AccessModeEnum.GLOBAL)
        _cs["default.database.idx"] = _idx
        _cs.write()


class ThemeViewSet(viewsets.ViewSet):
    @csrf_exempt
    def get_all_themes(self, request):
        _t_list = [
            {
                "short": "default",
                "name": "Default",
            },
        ]
        if settings.ICSW_OVERALL_STYLE != "condensed" or True:
            # shitty styles only for non-condensed mode
            _t_list.extend(
                [
                    {
                        "short": "cora",
                        "name": "Cora",
                    },
                    {
                        "short": "sirocco",
                        "name": "Sirocco",
                    },
                ]
            )
        # very stupid format
        return Response(_t_list)


class session_expel(View):
    def post(self, request):
        my_sh = SessionHelper()
        _dup_keys = my_sh.check_for_multiple_session(request.session)
        if _dup_keys:
            [my_sh.delete_session(_dup_key) for _dup_key in _dup_keys]
        return HttpResponse(
            json.dumps(
                {"deleted": len(_dup_keys)}
            ),
            content_type="application/json"
        )


class DummyLogger(object):
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        logger.log(log_level, u"[DL] {}".format(what))


class session_login(View):
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
            # check eggs for allegro
            _eco = server_mixins.EggConsumeObject(DummyLogger())
            _eco.init({"SERVICE_ENUM_NAME": icswServiceEnum.cluster_server.name})
            if _eco.consume("allegro", db_user):
                login_credentials = (real_user_name, login_password, login_name)
                _num_dup_sessions = _login(request, db_user, login_credentials)
                request.xml_response["duplicate_sessions"] = "{:d}".format(_num_dup_sessions)
                if _post.get("next_url", "").strip():
                    request.xml_response["redirect"] = _post["next_url"]
                else:
                    request.xml_response["redirect"] = "main.dashboard"
            else:
                request.xml_response.error("Ova resource problem")
                _failed_login(request, real_user_name)

    @classmethod
    def _check_login_data(cls, request, username, password):
        """Returns a valid user instance to be logged in or raises ValidationError"""
        if username and password:
            # print "*"
            db_user = authenticate(username=username, password=password)
            # print "+", db_user
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
            # ignore missing testcookie
            if not request.session.test_cookie_worked() and False:
                raise ValidationError(
                    "Your Web browser doesn't appear to have cookies enabled. " +
                    "Cookies are required for logging in."
                )

        assert db_user is not None
        return db_user

    @classmethod
    def get_real_user_name(cls, username):
        """Resolve aliases"""
        _all_users = user.objects.all()  # @UndefinedVariable
        all_aliases = [
            (
                login_name,
                [
                    _entry for _entry in al_list.strip().split() if _entry not in [None, "None"]
                ]
            ) for login_name, al_list in _all_users.values_list(
                "login", "aliases"
            ) if al_list is not None and al_list.strip()
        ]
        rev_dict = {}
        all_logins = [
            login_name for login_name, al_list in all_aliases
        ]
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


class UserView(viewsets.ViewSet):
    def get_user(self, request):
        context = {
            "request": request
        }
        if request.user and not request.user.is_anonymous:
            _user = request.user
            context["is_authenticated"] = True
        else:
            _user = user()
            context["is_authenticated"] = False
        context["is_anonymous"] = not context["is_authenticated"]
        serializer = user_serializer([_user], context=context, many=True)
        return Response(serializer.data)


class RouteViewSet(viewsets.ViewSet):
    def register(self, request):
        if request.user.is_authenticated():
            RouteTrace.objects.create(
                session_id=request.session.session_key,
                user_id=request.user.idx,
                from_name=request.data["from"],
                to_name=request.data["to"],
            )
        return Response([])


class BackgroundJobViewSet(viewsets.ViewSet):
    def get_bg_jobs(self, request):
        serializer = background_job_serializer(
            background_job.objects.all().select_related(
                "initiator__domain_tree_node",
                "user",
            ).prefetch_related(
                "background_job_run_set"
            ).order_by("-idx")[0:100],
            many=True
        )
        return Response(serializer.data)
