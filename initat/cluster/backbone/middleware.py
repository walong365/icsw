# Django settings for ICSW
#
# -*- coding: utf-8 -*-
#
# Copyright (C) 2010-2017 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
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

""" middleware for django """

# from backend.models import site_call_log, session_call_log


import time

from django.conf import settings

DB_DEBUG = False

if hasattr(settings, "DATABASE_DEBUG"):
    DB_DEBUG = settings.DATABASE_DEBUG
else:
    DB_DEBUG = settings.DEBUG
if DB_DEBUG:
    from django.db import connection

from threading import local

thread_local_obj = local()


class thread_local_middleware(object):
    def process_request(self, request):
        thread_local_obj.request = request
        thread_local_obj.test = "test"
        thread_local_obj.user = getattr(request, "user", None)

    @property
    def user(self):
        return getattr(thread_local_obj, "user", None)

    @user.setter
    def user(self, user):
        setattr(thread_local_obj, "user", user)
        
    @property
    def request(self):
        return getattr(thread_local_obj, "request", None)

REVISION_MIDDLEWARE_FLAG = "reversion.revision_middleware_active"


class database_debug(object):
    def process_request(self, request):
        request.__start_time = time.time()

    def process_response(self, request, response):
        if settings.DEBUG and not request.path.count(settings.MEDIA_URL) and connection.queries:
            from initat.debug import show_database_calls
            show_database_calls(path=request.path, runtime=time.time() - request.__start_time)
        return response
