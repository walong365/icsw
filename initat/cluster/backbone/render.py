# -*- coding: utf-8 -*-
#
# Copyright (C) 2014-2015 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of cluster-backbone-sql
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

import json
import logging

import django
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ImproperlyConfigured
from django.core.urlresolvers import reverse
from django.db.models import Q
from django.shortcuts import render_to_response, redirect
from django.template.loader import render_to_string
from django.utils.decorators import method_decorator
from initat.cluster.backbone.models import device_variable
import django.template

logger = logging.getLogger("cluster.render")


def _get_cluster_info_dict():
    _list = device_variable.objects.values_list("name", "val_str").filter(
        Q(name__in=["CLUSTER_NAME", "CLUSTER_ID"]) &
        Q(device__device_group__cluster_device_group=True)
    )
    return {_v[0]: _v[1] for _v in _list}


class render_me(object):
    def __init__(self, request, template, *args, **kwargs):
        self.request = request
        self.template = template
        self.my_dict = {
            # default values
            "NUM_QUOTA_SERVERS": 0,
        }
        for add_dict in args:
            self.my_dict.update(add_dict)
        for key, value in kwargs.iteritems():
            self.my_dict[key] = value
        # just for debug purposes

    def update(self, in_dict):
        self.my_dict.update(in_dict)

    def __call__(self, *args):
        return self.render(*args)

    def render(self, *args):
        in_dict = {}
        for add_dict in args:
            in_dict.update(add_dict)
        self.my_dict.update(in_dict)
        if self.request.user and not self.request.user.is_anonymous:
            _user = {
                "idx": self.request.user.pk,
                "pk": self.request.user.pk,
                "is_superuser": self.request.user.is_superuser,
                "authenticated": True,
                "login": self.request.user.login,
                "login_name": self.request.session["login_name"],
                "full_name": unicode(self.request.user),
            }
            _vars = {_name: _var.value for _name, _var in self.request.session["user_vars"].iteritems()}
            # routing info

        else:
            _user = {
                "is_superuser": False,
                "authenticated": False,
            }
            _vars = {"sidebar_open": True}
        _cid = _get_cluster_info_dict()
        self.my_dict["CLUSTER_NAME"] = _cid.get("CLUSTER_NAME", "")
        self.my_dict["CLUSTER_ID"] = _cid.get("CLUSTER_ID", "")
        self.my_dict["GOOGLE_MAPS_KEY"] = settings.GOOGLE_MAPS_KEY
        self.my_dict["PASSWORD_CHARACTER_COUNT"] = settings.PASSWORD_CHARACTER_COUNT
        self.my_dict["USER_VARS"] = json.dumps(_vars)
        # store as json for angular
        # store as dict for django templates
        self.my_dict["CURRENT_USER"] = json.dumps(_user)
        self.my_dict["ADDITIONAL_MENU_FILES"] = json.dumps(settings.ADDITIONAL_MENU_FILES)
        self.my_dict["ADDITIONAL_ANGULAR_APPS"] = settings.ADDITIONAL_ANGULAR_APPS
        # self.my_dict["ADDITIONAL_URLS"] = [
        #     (_name, reverse(_url, args=_args)) for _name, _url, _args in settings.ADDITIONAL_URLS
        # ]
        return render_to_response(
            self.template,
            self.my_dict,
            context_instance=django.template.RequestContext(self.request)
        )


def render_string(request, template_name, in_dict=None):
    return unicode(render_to_string(
        template_name,
        in_dict if in_dict is not None else {},
        django.template.RequestContext(request))
    )


class permission_required_mixin(object):
    all_required_permissions = ()
    any_required_permissions = ()

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        perm_ok = True
        if self.all_required_permissions:
            if any([_perm.count(".") != 2 for _perm in self.all_required_permissions]):
                raise ImproperlyConfigured("permission format error: {}".format(", ".join(self.all_required_permissions)))
            if not request.user.has_object_perms(self.all_required_permissions):
                logger.error("user {} has not the required permissions {}".format(
                    unicode(request.user),
                    str(self.all_required_permissions),
                    ))
                perm_ok = False
        if self.any_required_permissions:
            if any([_perm.count(".") != 2 for _perm in self.any_required_permissions]):
                raise ImproperlyConfigured("permission format error: {}".format(", ".join(self.any_required_permissions)))
            if not request.user.has_any_object_perms(self.any_required_permissions):
                logger.error("user {} has not any of the required permissions {}".format(
                    unicode(request.user),
                    str(self.any_required_permissions),
                    ))
                perm_ok = False
        if not perm_ok:
            try:
                perm_url = reverse("main:permission_denied")
            except:
                return redirect(settings.LOGIN_URL)
            else:
                print reverse
                return redirect(perm_url)
        return super(permission_required_mixin, self).dispatch(
            request,
            *args,
            **kwargs
        )
