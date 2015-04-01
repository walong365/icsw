#!/usr/bin/python -Otu

import django.template
import logging

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator

logger = logging.getLogger("cluster.render")

class permission_required_mixin(object):
    all_required_permissions = ()
    any_required_permissions = ()
    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        if self.all_required_permissions:
            if not request.user.has_object_perms(self.all_required_permissions):
                logger.error("user %s has not the required permissions %s" % (
                    unicode(request.user),
                    str(self.all_required_permissions),
                    ))
                return redirect(settings.LOGIN_URL)
        if self.any_required_permissions:
            if not request.user.has_any_object_perms(self.any_required_permissions):
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

