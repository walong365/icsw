# -*- coding: utf-8 -*-

import django.template
import logging

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import render_to_response, redirect
from django.template.loader import render_to_string
from django.utils.decorators import method_decorator

logger = logging.getLogger("cluster.render")

class render_me(object):
    """
    A simple wrapper class around render_to_response with a RequestContext.
    """
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

    def render(self, *args):
        in_dict = {}
        for add_dict in args:
            in_dict.update(add_dict)
        self.my_dict.update(in_dict)
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
        if self.all_required_permissions:
            if not request.user.has_perms(self.all_required_permissions):
                logger.error("user %s has not the required permissions %s" % (
                    unicode(request.user),
                    str(self.all_required_permissions),
                    ))
                return redirect(settings.LOGIN_URL)
        if self.any_required_permissions:
            if not request.user.has_any_perms(self.any_required_permissions):
                logger.error("user %s has not any of the required permissions %s" % (
                    unicode(request.user),
                    str(self.any_required_permissions),
                    ))
                return redirect(settings.LOGIN_URL)
        return super(permission_required_mixin, self).dispatch(
            request,
            *args,
            **kwargs
            )
