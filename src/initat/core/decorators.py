import logging_tools
import sys
import process_tools
import time

from django.http import HttpResponseForbidden, HttpResponse
from django.conf import settings

from initat.core.utils import (logging_pool, send_emergency_mail, xml_response,
                               build_simple_xml)


def require_POST_params(params):
    """
    Decorator that requires a POST request and certain *params* to be present.
    Supports either a single paramter or and iterable of paramters.

    @require_POST_params("id")
    def foo(request):
        pass

    @required_POST_params(["id", "id2"])
    def bar(request):
        pass

    """
    def _decorator(func):
        def _wrapper(request, *args, **kwargs):
            if request.method != "POST":
                return HttpResponseForbidden("Only POST allowed")
            if isinstance(params, (tuple, list, set)):
                for i in params:
                    if i not in request.POST:
                        return HttpResponseForbidden("Missing parameter %s" % i)
            else:
                if params not in request.POST:
                    return HttpResponseForbidden("Missing parameter %s" % params)
            return func(request, *args, **kwargs)
        return _wrapper
    return _decorator


class init_logging(object):
    """
    Decorator for django views that catches exceptions and logs them.
    This has to be the first decorator in the decorator queue
    (above @login_required) to catch redirects.
    """
    def __init__(self, func):
        self.__name__ = func.__name__
        self.__logger = logging_pool.get_logger("http")
        self._func = func
        self.xml_response = None
        self.__prev_xml_response = None
        self.__stdout_buffer = None
        self.orig_stdout = None
        self.__prev_logger = None

    def log(self, what="", log_level=logging_tools.LOG_LEVEL_OK, **kwargs):
        if kwargs.get("request_vars", False):
            self.log_request_vars(kwargs["request"])
        else:
            for_xml = kwargs.get("xml", False)
            if for_xml:
                self.xml_response.feed_log_line(log_level, what)
            self.__logger.log(log_level, "[%s] %s" % (self.__name__, what))

    def write(self, what):
        self.__stdout_buffer = "%s%s" % (self.__stdout_buffer, what)
        if self.__stdout_buffer.endswith("\n"):
            self.__logger.log(logging_tools.LOG_LEVEL_OK, "[%s stdout] %s" % (self.__name__, self.__stdout_buffer.rstrip()))
            self.__stdout_buffer = ""
        # verbose
        if (not settings.IS_WINDOWS) and settings.DEBUG:
            if not isinstance(self.orig_stdout, logging_tools.log_adapter):
                self.orig_stdout.write(what.encode("utf-8", "replace"))

    def log_request_vars(self, request, log_lines=None):
        if not log_lines:
            log_lines = []
        log_lines.extend(["",
                          "method is %s" % (request.method),
                          ""])
        if request.method == "POST":
            log_lines.append("%s defined" % (logging_tools.get_plural("key", len(request.POST))))
            for key in sorted(request.POST):
                log_lines.append(u"%-20s: %s" % (key, unicode(request.POST[key])))
        for line in log_lines:
            self.log(line, logging_tools.LOG_LEVEL_ERROR)
        if not settings.DEBUG:
            send_emergency_mail(log_lines=log_lines)

    def __call__(self, *args, **kwargs):
        s_time = time.time()
        request = args[0]
        if request.user:
            self.log("calling user is '%s'" % (request.user))
        else:
            self.log("no user defined in request", logging_tools.LOG_LEVEL_WARN)
        if hasattr(request, "init_log_counter"):
            # store previous logger
            request.init_log_counter += 1
            self.__prev_logger = request.log
            self.xml_response = request.xml_response
            request.log("nesting init_logging", logging_tools.LOG_LEVEL_WARN)
        else:
            request.init_log_counter = 1
            self.__prev_logger = None
            self.__prev_xml_response = None
            # modify stdout
            self.orig_stdout = sys.stdout
            # stdout buffer
            sys.stdout = self
            # xml response object
            request.xml_response = xml_response()
            self.xml_response = request.xml_response
        self.__stdout_buffer = ""
        request.log = self.log
        try:
            ret_value = self._func(*args, **kwargs)
        except Exception:  # pylint: disable-msg=W0703
            exc_info = process_tools.exception_info()
            log_lines = exc_info.log_lines
            self.log_request_vars(request, log_lines)
            if request.is_ajax():
                error_str = process_tools.get_except_info()
                ret_value = HttpResponse(build_simple_xml("xml_result", {"err_str": error_str}),
                                         mimetype="application/xml")
            else:
                raise
        finally:
            if not self.__prev_logger:
                # flush buffer
                if self.__stdout_buffer:
                    self.write("\n")
                # restore stdout
                if request.init_log_counter == 1:
                    sys.stdout = self.orig_stdout
        if request.is_ajax() and ret_value["Content-Type"].lower() not in ["application/xml",
                                                                           "application/json"]:
            #print ret_value["Content-Type"]
            ret_value = HttpResponse(build_simple_xml("xml_result", {"err_str": "session has expired, please login again"}),
                                     mimetype="application/xml")
        if request.is_ajax() and ret_value["Content-Type"] == "application/json" and "callback" in request.GET:
            # modify content with callback-function for dynatree calls
            ret_value.content = "%s(%s)" % (request.GET["callback"], ret_value.content)
        if logging_pool:
            logging_pool.free_logger(self.__logger)
        if self.__prev_logger:
            # copy previous logger back to struct
            request.log = self.__prev_logger
            self.__prev_logger = None
        request.init_log_counter -= 1
        e_time = time.time()
        self.log("processed in %s" % (logging_tools.get_diff_time_str(e_time - s_time)))
        return ret_value
