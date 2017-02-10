# -*- coding: utf-8 -*-
#
# Copyright (C) 2014-2017 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw-server-server
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
""" permission decorated for views """



import logging

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ImproperlyConfigured
from django.core.urlresolvers import reverse
from django.shortcuts import redirect
from django.utils.decorators import method_decorator

logger = logging.getLogger("cluster.render")


class permission_required_mixin(object):
    all_required_permissions = ()
    any_required_permissions = ()

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        perm_ok = True
        if self.all_required_permissions:
            if any(
                [
                    _perm.count(".") != 2 for _perm in self.all_required_permissions
                ]
            ):
                raise ImproperlyConfigured(
                    "permission format error: {}".format(
                        ", ".join(self.all_required_permissions)
                    )
                )
            if not request.user.has_object_perms(self.all_required_permissions):
                logger.error(
                    "user {} has not the required permissions {}".format(
                        str(request.user),
                        str(self.all_required_permissions),
                    )
                )
                perm_ok = False
        if self.any_required_permissions:
            if any(
                [
                    _perm.count(".") != 2 for _perm in self.any_required_permissions
                ]
            ):
                raise ImproperlyConfigured("permission format error: {}".format(", ".join(self.any_required_permissions)))
            if not request.user.has_any_object_perms(self.any_required_permissions):
                logger.error(
                    "user {} has not any of the required permissions {}".format(
                        str(request.user),
                        str(self.any_required_permissions),
                    )
                )
                perm_ok = False
        if not perm_ok:
            try:
                perm_url = reverse("main:permission_denied")
            except:
                return redirect(settings.LOGIN_URL)
            else:
                print(reverse)
                return redirect(perm_url)
        return super(permission_required_mixin, self).dispatch(
            request,
            *args,
            **kwargs
        )
