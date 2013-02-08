""" middleware for django """

#from backend.models import site_call_log, session_call_log
from django.conf import settings

DB_DEBUG = False

if hasattr(settings, "DATABASE_DEBUG"):
    DB_DEBUG = settings.DATABASE_DEBUG
else:
    DB_DEBUG = settings.DEBUG

if DB_DEBUG:
    from django.db import connection
else:
    connection = None
from django.http import HttpResponseRedirect
import django.contrib.auth
import process_tools
import time
import datetime
import pprint
import reversion
import struct
import fcntl
import termios
from reversion.revisions import revision_context_manager

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

class log_call(object):
    def __init__(self):
        self.__start_time = 0
    def process_request(self, request):
        self.__start_time = time.time()
        return None
    def process_response(self, request, response):
        if isinstance(response, HttpResponseRedirect):
            if response.has_header("Location"):
                act_uri = request.build_absolute_uri()
                # rebuild response for access to https://fallback.oeko-tex.com/newoekotex
                if act_uri.count("document") or act_uri.count("fallback"):
                    response["Location"] = "https://%s%s" % (request.get_host(),
                                                             response["Location"])
        full_path = request.get_full_path()
        if not full_path.count(settings.MEDIA_URL):
            if hasattr(request, "session") and request.session.has_key("session_history_object"):
                # add full session_call_log
                new_scl = session_call_log(session_history=request.session["session_history_object"],
                                           full_path=full_path,
                                           remote_addr=request.META.get("REMOTE_ADDR", "0.0.0.0"),
                                           run_time=abs(time.time() - self.__start_time))
            else:
                # no session_history_object, add simple site_call_log
                if hasattr(request, "user"):
                    new_scl = site_call_log(user_name=unicode(request.user),
                                            path=full_path)
                else:
                    new_scl = None
            if new_scl:
                try:
                    new_scl.save()
                except:
                    if len(full_path) > 250:
                        # ignore, too long for db
                        pass
                    else:
                        print "error saving site_call_log: %s" % (process_tools.get_except_info())
                        # changed to another server with (IntegrityError triggered), close session
                        if "session_history_object" in request.session:
                            cur_sho = request.session["session_history_object"]
                            cur_sho.logout_time = datetime.datetime.now()
                            try:
                                cur_sho.save()
                            except:
                                pass
                        django.contrib.auth.logout(request)
        return response

def get_terminal_size():
    height, width, hp, wp = struct.unpack('HHHH',
                                 fcntl.ioctl(0, termios.TIOCGWINSZ,
                                             struct.pack('HHHH', 0, 0, 0, 0)))
    return width, height

def show_database_calls(**kwargs):
    if connection:
        full = kwargs.get("full", False)
        tot_time = sum([float(entry["time"]) for entry in connection.queries], 0.)
        try:
            cur_width = get_terminal_size()[0]
        except:
            # no regular TTY, ignore
            cur_width = None
        else:
            # only output if stdout is a regular TTY
            print "queries: %d in %.2f seconds" % (len(connection.queries),
                                                   tot_time)
        if len(connection.queries) > 1 and cur_width:
            for act_sql in connection.queries:
                sql_str = act_sql["sql"].replace("\n", "<NL>")
                if full:
                    out_str = sql_str
                else:
                    if sql_str.count("FROM") and sql_str.count("WHERE"):
                        oper_str = sql_str.split()[0]
                        if sql_str.count("FROM") > 1 or sql_str.count("WHERE") > 1:
                            print "FROM / COUNT: %d / %d" % (sql_str.count("FROM"), sql_str.count("WHERE"))
                        # parse sql_str
                        sub_str = sql_str[sql_str.index("FROM"):sql_str.index("WHERE")]
                        for r_char in "(),=":
                            sub_str = sub_str.replace(r_char, "")
                        out_list = set()
                        for cur_str in sub_str.split():
                            if cur_str.startswith("[") and cur_str.endswith("]"):
                                out_list.add(cur_str.split(".")[0])
                        #print sql_str
                        sql_str = "%s FROM %s :: %s" % (
                            oper_str,
                            ", ".join(sorted(list(out_list))),
                            sql_str)
                    out_str = sql_str[0:cur_width - 8]
                print "%6.2f %s" % (float(act_sql["time"]), out_str)
    else:
        print "django.db.connection not loaded in backbone.middleware.py"
    
class database_debug(object):
    def process_response(self, request, response):
        if settings.DEBUG and not request.path.count(settings.MEDIA_URL) and connection.queries:
            show_database_calls()
        return response
