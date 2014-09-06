# -*- coding: utf-8 -*-
#
# Copyright (C) 2014 Andreas Lang-Nevyjel
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

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ImproperlyConfigured
from django.core.urlresolvers import reverse
from django.db.models import Q
from django.shortcuts import render_to_response, redirect
from django.template.loader import render_to_string
from django.utils.decorators import method_decorator
from initat.cluster.backbone.models import cluster_license_cache, background_job
import django.template
import json
import logging
import routing

logger = logging.getLogger("cluster.render")


class render_me(object):
    def __init__(self, request, template, *args, **kwargs):
        self.request = request
        self.template = template
        self.my_dict = {}
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
            _user = {"idx": self.request.user.pk, "pk": self.request.user.pk}
            _num_bg_jobs = background_job.objects.exclude(Q(state__in=["done", "timeout", "ended", "merged"])).count()
            # routing info
            _service_types = {key: True for key in routing.srv_type_routing().service_types}
        else:
            gp_dict = {}
            op_dict = {}
            _user = {}
            _num_bg_jobs = 0
            _service_types = {}
        # license cache
        cur_clc = cluster_license_cache()
        # import pprint
        # pprint.pprint(gp_dict)
        self.my_dict["GLOBAL_PERMISSIONS"] = json.dumps(gp_dict)
        self.my_dict["OBJECT_PERMISSIONS"] = json.dumps(op_dict)
        self.my_dict["GOOGLE_MAPS_KEY"] = settings.GOOGLE_MAPS_KEY
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
        return render_to_response(
            self.template,
            self.my_dict,
            context_instance=django.template.RequestContext(self.request))


def render_string(request, template_name, in_dict=None):
    return unicode(render_to_string(
        template_name,
        in_dict if in_dict is not None else {},
        django.template.RequestContext(request)))


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
