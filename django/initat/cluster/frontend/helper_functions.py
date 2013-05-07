#!/usr/bin/python-init -Otu
# -*- coding: utf-8 -*-

""" helper functions for the init.at clustersoftware """

import sys
import os
import time
import datetime
from django.conf import settings
from django.db.models import Q
from django.http import HttpResponse
import logging_tools
import process_tools
import smtplib
import pprint
import email
import email.mime
import email.header
import copy
from lxml import etree
from lxml.builder import E
import django.core.urlresolvers
import zmq
from django.utils.translation import ugettext as _

class logging_pool(object):
    """
    pool for logging management
    """
    #: variable not used
    idle_pool = []
    #: amount of created loggers
    created = 0
    #: dictionary of loggers
    logger_dict = {}
    if zmq:
        zmq_context = zmq.Context()
    else:
        zmq_context = None
    @staticmethod
    def get_logger(name="http", **kwargs):
        """
        getting the actual (current) logger
        
        :param name: the name of name space
        :type name: str
        :param kwargs: arbitrary optional arguments in a dictionary
        :type kwargs: dict
        :returns: cur_logger (logger) -- the actual logger
        """
        log_name = "%s.%s" % (settings.REL_SITE_ROOT, name)
        if "init.at.%s" % (log_name) in logging_pool.logger_dict:
            cur_logger = logging_pool.logger_dict["init.at.%s" % (log_name)]
            cur_logger.usecount += 1
        else:
            logging_pool.created += 1
            cur_logger = logging_tools.get_logger("%s" % (log_name),
                                                  ["uds:/var/lib/logging-server/py_log"],
                                                  init_logger=True,
                                                  zmq=True if zmq else False,
                                                  context=logging_pool.zmq_context)
            cur_logger.log_command("ignore_process_id")
            if "max_file_size" in kwargs:
                cur_logger.log_command("set_file_size %d" % (kwargs["max_file_size"]))
            cur_logger.usecount = 1
            logging_pool.logger_dict[cur_logger.logger.name] = cur_logger
        return cur_logger
    @staticmethod
    def free_logger(cur_logger):
        """
        one logger will be free
        """
        f_logger_name = cur_logger.logger.name
        logging_pool.logger_dict[f_logger_name].usecount -= 1

class xml_response(object):
    """
    provides the xml response
    """
    def __init__(self):
        self.reset()
    def reset(self):
        """
        sets the xml response to the start state
        """
        self.log_buffer = []
        self.val_dict = {}
    def feed_log_line(self, log_level, log_str):
        """
        appends new log line with log data
        
        :param log_level: the logging level
        :param log_str: the log content
        :type log_str: str
        """
        self.log_buffer.append((log_level, log_str))
    def __setitem__(self, key, value):
        """
        sets a new item (key-value pair)
        
        :param key: the key of the new item
        :param value: the value of the new item
        """
        if key in self.val_dict:
            if type(self.val_dict[key]) != list:
                self.val_dict[key] = [self.val_dict[key]]
            self.val_dict[key].append(value)
        else:
            self.val_dict[key] = value
    def __getitem__(self, key):
        """
        :param key: delivered key, his value will be returned
        :returns: the corresponding value to the delivered key
        """
        return self.val_dict[key]
    def update(self, in_dict):
        """
        makes an update of key-value dictionary
        
        :param in_dict: dictionary with the actual key-value pairs
        :type in_dict: dict
        """
        for key, value in in_dict.iteritems():
            self[key] = value
    def is_ok(self):
        """
        checks the logging status, if OK
        """
        if self.log_buffer:
            return True if max([log_lev for log_lev, log_str in self.log_buffer]) == logging_tools.LOG_LEVEL_OK else False
        else:
            return True
    def _get_value_xml(self, key, value):
        if type(value) == list:
            ret_val = E.value_list(**{
                "name" : key,
                "num"  : "%d" % (len(value)),
                "type"  :"list",
            })
            for val_num, sub_val in enumerate(value):
                ret_val.append(self._get_value_xml(key, sub_val))
        else:
            ret_val = E.value(value if type(value) == etree._Element else unicode(value), **{
               "name" : key,
               "type" : {
                   int            : "integer",
                   long           : "integer",
                   str            : "string",
                   unicode        : "string",
                   float          : "float",
                   etree._Element : "xml"}.get(type(value), "unknown")})
        return ret_val
    def build_response(self):
        """
        builds the xml response
        """
        num_errors, num_warnings = (
            len([True for log_lev, log_str in self.log_buffer if log_lev == logging_tools.LOG_LEVEL_ERROR]),
            len([True for log_lev, log_str in self.log_buffer if log_lev == logging_tools.LOG_LEVEL_WARN]))
        return E.response(
            E.header(
                E.messages(
                    *[E.message(log_str, **{"log_level"     : "%d" % (log_lev),
                                            "log_level_str" : logging_tools.get_log_level_str(log_lev)}) for log_lev, log_str in self.log_buffer]),
                **{"code"     : "%d" % (max([log_lev for log_lev, log_str in self.log_buffer] + [logging_tools.LOG_LEVEL_OK])),
                   "errors"   : "%d" % (num_errors),
                   "warnings" : "%d" % (num_warnings),
                   "messages" : "%d" % (len(self.log_buffer))}),
            E.values(
                *[self._get_value_xml(key, value) for key, value in self.val_dict.iteritems()]
            )
        )
    def __unicode__(self):
        """
        :returns: the unicode representation of xml response
        """
        return etree.tostring(self.build_response(), encoding=unicode)
    def create_response(self):
        """
        creates a new xml response
        """
        return HttpResponse(unicode(self),
                            mimetype="application/xml")
     
def keyword_check(*kwarg_list):
    def decorator(func):
        def _wrapped_view(*args, **kwargs):
            diff_set = set(kwargs.keys()) - set(kwarg_list)
            if diff_set:
                raise KeyError, "Invalid keyword arguments: %s" % (str(diff_set))
            return func(*args, **kwargs)
        return _wrapped_view
    return decorator

##class rest_logging(object):
##    def __init__(self, func):
##        self.__name__ = func.__name__
##        self.__logger = logging_pool.get_logger("rest")
##        self._func = func
##    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
##        self.__logger.log(log_level, "[%s] %s" % (self.__name__, what))
##    def as_view(self, *args, **kwargs):
##        print args, kwargs
##        return self._func.as_view(*args, **kwargs)
    
class init_logging(object):
    def __init__(self, func):
        """ decorator for catching exceptions and logging, has to be the first decorator in the decorator queue (above login_required) to catch redirects """
        self.__name__ = func.__name__
        self.__doc__ = func.__doc__
        #self.__repr__ = func.__repr__
        self.__logger = logging_pool.get_logger("http")
        self._func = func
        self.__write_iter_count = 0
        #self._backup_stdout = sys.stdout
    def log(self, what="", log_level=logging_tools.LOG_LEVEL_OK, **kwargs):
        if kwargs.get("request_vars", False):
            self.log_request_vars(kwargs["request"])
        else:
            for_xml = kwargs.get("xml", False)
            if for_xml:
                self.xml_response.feed_log_line(log_level, what)
            self.__logger.log(log_level, "[%s] %s" % (self.__name__, what))
    def write(self, what):
        self.__write_iter_count += 1
        self.__stdout_buffer = "%s%s" % (self.__stdout_buffer, what)
        if self.__stdout_buffer.endswith("\n"):
            self.__logger.log(logging_tools.LOG_LEVEL_OK, "[%s stdout] %s" % (self.__name__, self.__stdout_buffer.rstrip()))
            self.__stdout_buffer = ""
        # verbose
        # self.__logger.log(logging_tools.LOG_LEVEL_WARN, "%s %s" % (self.orig_stdout, type(self.orig_stdout)))
        if settings.DEBUG:
            if not isinstance(self.orig_stdout, logging_tools.log_adapter) and not isinstance(self.orig_stdout, init_logging):
                if self.__write_iter_count > 10:
                    logging_tools.my_syslog("iteration detected, type of self.orig_stdout is %s (%s)" % (str(type(self.orig_stdout)),
                                                                                                         str(self.orig_stdout)))
                    sys.exit(-1)
                else:
                    self.orig_stdout.write(what.encode("utf-8", "replace"))
        self.__write_iter_count -= 1
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
            send_emergency_mail(log_lines=log_lines, request=request)
    def __call__(self, *args, **kwargs):
        s_time = time.time()
        request = args[0]
        if request.user.is_authenticated():
            self.log("calling user is '%s'" % (unicode(request.user)))
        else:
            self.log("no user defined in session", logging_tools.LOG_LEVEL_WARN)
        # FIXME! sys.stdout is init_logging - looks like only django runserver problem, not on nginx
        #self.log("# %s %s" % (str(type(sys.stdout)), str(type(self._backup_stdout))))
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
        except:
            exc_info = process_tools.exception_info()
            log_lines = exc_info.log_lines
            self.log_request_vars(request, log_lines)
            if request.is_ajax():
                # parse_xml_response(xml) don't understand the build_simple_xml response
                # need request.META["HTTP_X_REQUESTED_WITH"] = "XMLHttpRequest"
                #error_str = process_tools.get_except_info()
                #ret_value = HttpResponse(build_simple_xml("xml_result", {"err_str" : error_str}),
                #                         mimetype="application/xml")
                request.xml_response.log_buffer = [(logging_tools.LOG_LEVEL_ERROR, _("An internal error occured. Please report issue"))]
                ret_value = request.xml_response.create_response()
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
                    #if type(sys.stdout) != type(self._backup_stdout):
                    #    sys.stdout = self._backup_stdout
        if request.is_ajax() and ret_value["Content-Type"].lower() not in ["application/xml",
                                                                           "application/json"]:
            #print ret_value["Content-Type"]
            ret_value = HttpResponse(etree.tostring(E.xml_result(err_str="session has expired, please login again")),
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

def send_emergency_mail(**kwargs):
    """
    sends an emergency email to init-company
    
    :param kwargs: arbitrary optional arguments
    :type kwargs: dict 
    """
    # mainly used for windows
    exc_info = process_tools.exception_info()
    msg_lines = kwargs.get("log_lines", exc_info.log_lines)
    request = kwargs.get("request", None)
    if request:
        msg_lines.extend(["",
                          "djangouser: %s" % (unicode(request.user)),
                          "PATH_INFO: %s" % (request.META.get("PATH_INFO", "nor found")),
                          "USER_AGENT: %s" % (request.META.get("HTTP_USER_AGENT", "not found"))])
    header_cs = "utf-8"
    mesg = email.mime.text.MIMEText("\n".join(msg_lines), _charset=header_cs)
    mesg["Subject"] = "Python error"
    mesg["From"] = "python-error@init.at"
    mesg["To"] = "oekotex@init.at"
    srv = smtplib.SMTP()
    srv.connect(settings.MAIL_SERVER, 25)
    srv.sendmail(mesg["From"], mesg["To"].split(","), mesg.as_string())
    srv.close()

if __name__ == "__main__":
    print "Loadable module, exiting..."
    sys.exit(-1)
