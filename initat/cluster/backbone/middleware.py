# Django settings for ICSW
#
# -*- coding: utf-8 -*-
#
# Copyright (C) 2010-2016 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
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

""" middleware for django """

# from backend.models import site_call_log, session_call_log
import fcntl
import time
import struct
import termios

from django.conf import settings
from reversion.revisions import revision_context_manager

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

    @property
    def request(self):
        return getattr(thread_local_obj, "request", None)

REVISION_MIDDLEWARE_FLAG = "reversion.revision_middleware_active"


# reversion 1.5
class revision_middleware(object):
    """Wraps the entire request in a revision."""
    def process_request(self, request):
        """Starts a new revision."""
        full_path = request.get_full_path()
        if not full_path.count(settings.MEDIA_URL):
            request.META[(REVISION_MIDDLEWARE_FLAG, self)] = True
            revision_context_manager.start()
            if hasattr(request, "user") and request.user.is_authenticated():
                revision_context_manager.set_user(request.user)

    def _close_revision(self, request):
        """Closes the revision."""
        if request.META.get((REVISION_MIDDLEWARE_FLAG, self), False):
            del request.META[(REVISION_MIDDLEWARE_FLAG, self)]
            revision_context_manager.end()

    def process_response(self, request, response):
        """Closes the revision."""
        self._close_revision(request)
        return response

    def process_exception(self, request, exception):
        """Closes the revision."""
        revision_context_manager.invalidate()
        self._close_revision(request)


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
    if DB_DEBUG:
        from django.db import connection  # @Reimport
        _path = kwargs.get("path", "/unknown")
        _runtime = kwargs.get("runtime", 0.0)
        full = kwargs.get("full", False)
        tot_time = sum([float(entry["time"]) for entry in connection.queries], 0.)
        try:
            cur_width = get_terminal_size()[0]
        except:
            # no regular TTY, ignore
            cur_width = None
        else:
            # only output if stdout is a regular TTY
            output(
                "queries: {:d} in {:.2f} seconds".format(
                    len(connection.queries),
                    tot_time,
                )
            )
        if len(connection.queries) > 1 and cur_width:
            for act_sql in connection.queries:
                sql_str = act_sql["sql"].replace("\n", "<NL>")
                if full:
                    out_str = sql_str
                else:
                    if sql_str.count("FROM") and sql_str.count("WHERE"):
                        oper_str = sql_str.split()[0]
                        if sql_str.count("FROM") > 1 or sql_str.count("WHERE") > 1:
                            output(
                                "FROM / COUNT: {:d} / {:d}".format(
                                    sql_str.count("FROM"),
                                    sql_str.count("WHERE")
                                )
                            )
                        # parse sql_str
                        sub_str = sql_str[sql_str.index("FROM"):sql_str.index("WHERE")]
                        for r_char in "(),=":
                            sub_str = sub_str.replace(r_char, "")
                        out_list = set()
                        for cur_str in sub_str.split():
                            if cur_str.startswith("[") and cur_str.endswith("]"):
                                out_list.add(cur_str.split(".")[0])
                        # print sql_str
                        sql_str = u"{} FROM {} :: {}".format(
                            oper_str,
                            ", ".join(sorted(list(out_list))),
                            sql_str
                        )
                    out_str = sql_str[0:cur_width - 8]
                output(
                    u"{:6.2f} {}".format(
                        float(act_sql["time"]),
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
