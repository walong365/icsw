#!/usr/bin/python -Otu

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.core.urlresolvers import reverse
import logging

logger = logging.getLogger("cluster.render")

class permission_required_mixin(object):
    all_required_permissions = ()
    any_required_permissions = ()
    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        perm_ok = True
        if self.all_required_permissions:
            if not request.user.has_object_perms(self.all_required_permissions):
                logger.error("user %s has not the required permissions %s" % (
                    unicode(request.user),
                    str(self.all_required_permissions),
                    ))
                perm_ok = False
        if self.any_required_permissions:
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
