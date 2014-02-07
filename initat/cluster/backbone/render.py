#!/usr/bin/python -Otu


from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ImproperlyConfigured
from django.core.urlresolvers import reverse
from django.shortcuts import render_to_response, redirect
from django.template.loader import render_to_string
from django.utils.decorators import method_decorator
from rest_framework import serializers
import django.template
import logging
from rest_framework.renderers import JSONRenderer

logger = logging.getLogger("cluster.render")

class simple_global_perm(object):
    def __init__(self, key, value):
        self.key = key
        self.value = value

class simple_global_perm_serializer(serializers.Serializer):
    key = serializers.CharField()
    value = serializers.IntegerField()

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
    def render(self, *args):
        in_dict = {}
        for add_dict in args:
            in_dict.update(add_dict)
        self.my_dict.update(in_dict)
        if self.request.user:
            ser = simple_global_perm_serializer([simple_global_perm(key, value) for key, value in self.request.user.get_global_permissions().iteritems()], many=True)
            self.my_dict["GLOBAL_PERMISSIONS"] = JSONRenderer().render(ser.data)
        else:
            self.my_dict["GLOBAL_PERMISSIONS"] = JSONRenderer().render([])
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
                raise ImproperlyConfigured("permission format error: %s" % (", ".join(self.all_required_permissions)))
            if not request.user.has_object_perms(self.all_required_permissions):
                logger.error("user %s has not the required permissions %s" % (
                    unicode(request.user),
                    str(self.all_required_permissions),
                    ))
                perm_ok = False
        if self.any_required_permissions:
            if any([_perm.count(".") != 2 for _perm in self.any_required_permissions]):
                raise ImproperlyConfigured("permission format error: %s" % (", ".join(self.any_required_permissions)))
            if not request.user.has_any_object_perms(self.any_required_permissions):
                logger.error("user %s has not any of the required permissions %s" % (
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
