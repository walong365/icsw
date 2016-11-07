# Django settings for ICSW
#
# -*- coding: utf-8 -*-
#
# Copyright (C) 2010-2016 Andreas Lang-Nevyjel
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

from __future__ import unicode_literals, print_function

import fcntl
import time
import struct
import termios

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


def get_terminal_size():
    height, width, _hp, _wp = struct.unpack(
        'HHHH',
        fcntl.ioctl(0, termios.TIOCGWINSZ, struct.pack('HHHH', 0, 0, 0, 0)))
    return width, height


def show_database_calls(*args, **kwargs):
    DB_DEBUG = False

    def output(s):
        if 'printfun' in kwargs:
            kwargs['printfun'](s)
        else:
            print (s)

    if hasattr(settings, "DATABASE_DEBUG"):
        DB_DEBUG = settings.DATABASE_DEBUG
    else:
        DB_DEBUG = settings.DEBUG
    DB_CALL_LIMIT = 10
    if DB_DEBUG:
        from django.db import connection  # @Reimport
        _path = kwargs.get("path", "/unknown")
        _runtime = kwargs.get("runtime", 0.0)
        tot_time = sum([float(entry["time"]) for entry in connection.queries], 0.)
        try:
            cur_width = get_terminal_size()[0]
        except:
            # no regular TTY, ignore
            cur_width = None
        else:
            if len(connection.queries) > DB_CALL_LIMIT:
                # only output if stdout is a regular TTY
                output(
                    "queries: {:d} in {:.2f} seconds".format(
                        len(connection.queries),
                        tot_time,
                    )
                )
        if len(connection.queries) > DB_CALL_LIMIT and cur_width:
            for act_sql in connection.queries:
                if act_sql["sql"]:
                    out_str = act_sql["sql"].replace("\n", "<NL>")
                    _len_pre = len(out_str)
                    out_str = out_str[0:cur_width - 21]
                    _len_post = len(out_str)
                    output(
                        u"{:6.2f} [{:4d}/{:5d}] {}".format(
                            float(act_sql["time"]),
                            _len_post,
                            _len_pre,
                            out_str
                        )
                    )
        _line = "{} {:4d} {:8.4f} {:<50s}\n".format(
            time.ctime(),
            len(connection.queries),
            _runtime,
            _path
        )
        file("database_calls", "a").write(_line)
    else:
        output("django.db.connection not loaded in backbone.middleware.py")


class database_debug(object):
    def process_request(self, request):
        request.__start_time = time.time()

    def process_response(self, request, response):
        if settings.DEBUG and not request.path.count(settings.MEDIA_URL) and connection.queries:
            show_database_calls(path=request.path, runtime=time.time() - request.__start_time)
        return response
