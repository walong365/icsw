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
from initat.cluster.backbone.models.license import License
from initat.cluster.backbone.models import cluster_license_cache, background_job, device_variable
import django.template

import routing


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
            "NUM_BACKGROUND_JOBS": 0,
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

    def _unfold(self, in_dict):
        _keys = in_dict.keys()
        # unfold dictionary
        for _key in _keys:
            _parts = _key.split(".")
            in_dict.setdefault(_parts[0], {}).setdefault(_parts[1], {})[_parts[2]] = in_dict[_key]

    def render(self, *args):
        in_dict = {}
        for add_dict in args:
            in_dict.update(add_dict)
        self.my_dict.update(in_dict)
        if self.request.user and not self.request.user.is_anonymous:
            gp_dict = self.request.user.get_global_permissions()
            op_dict = self.request.user.get_all_object_perms(None)
            self._unfold(gp_dict)
            self._unfold(op_dict)
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
            _num_bg_jobs = background_job.objects.exclude(Q(state__in=["done", "timeout", "ended", "merged"])).count()
            # routing info
            _service_types = {key: True for key in routing.srv_type_routing().service_types}
        else:
            gp_dict = {}
            op_dict = {}
            _user = {
                "is_superuser": False,
                "authenticated": False,
            }
            _num_bg_jobs = 0
            _service_types = {}
            _vars = {"sidebar_open": True}
        # license cache
        cur_clc = cluster_license_cache()
        # pprint.pprint(gp_dict)
        # pprint.pprint(op_dict)
        _cid = _get_cluster_info_dict()
        self.my_dict["CLUSTER_NAME"] = _cid.get("CLUSTER_NAME", "")
        self.my_dict["CLUSTER_ID"] = _cid.get("CLUSTER_ID", "")
        self.my_dict["GLOBAL_PERMISSIONS"] = json.dumps(gp_dict)
        self.my_dict["OBJECT_PERMISSIONS"] = json.dumps(op_dict)
        # self.my_dict["ACTIVATED_FEATURES"] = json.dumps([feat.name for feat in License.objects.get_activated_features()])
        self.my_dict["GOOGLE_MAPS_KEY"] = settings.GOOGLE_MAPS_KEY
        self.my_dict["PASSWORD_CHARACTER_COUNT"] = settings.PASSWORD_CHARACTER_COUNT
        self.my_dict["USER_VARS"] = json.dumps(_vars)
        # store routing types as json
        self.my_dict["SERVICE_TYPES"] = json.dumps(_service_types)
        # add transformed dict ( md-config -> md_config )
        _service_types.update({key.replace("-", "_"): value for key, value in _service_types.iteritems()})
        self.my_dict["DJANGO_SERVICE_TYPES"] = _service_types
        # store as json for angular
        self.my_dict["CLUSTER_LICENSE"] = json.dumps(cur_clc.licenses)
        # store as dict for django templates
        self.my_dict["DJANGO_CLUSTER_LICENSE"] = cur_clc.licenses
        self.my_dict["CURRENT_USER"] = json.dumps(_user)
        self.my_dict["NUM_BACKGROUND_JOBS"] = _num_bg_jobs
        self.my_dict["ADDITIONAL_MENU_FILES"] = json.dumps(settings.ADDITIONAL_MENU_FILES)
        self.my_dict["ADDITIONAL_ANGULAR_APPS"] = settings.ADDITIONAL_ANGULAR_APPS
        self.my_dict["ADDITIONAL_URLS"] = [
            (_name, reverse(_url, args=_args)) for _name, _url, _args in settings.ADDITIONAL_URLS
        ]
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