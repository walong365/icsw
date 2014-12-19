# -*- coding: utf-8 -*-
#
# Copyright (C) 2012-2014 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of webfrontend
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

""" helper functions for the init.at clustersoftware """

from django.conf import settings
from django.http import HttpResponse
from initat.cluster.backbone import routing
from lxml import etree  # @UnresolvedImports
from lxml.builder import E  # @UnresolvedImports
import email.mime
import logging_tools
import net_tools
import process_tools
import smtplib


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

    def log(self, log_level, log_str, logger=None):
        self.log_buffer.append((log_level, log_str))
        if logger:
            logger.log(log_level, log_str)

    def info(self, log_str, logger=None):
        self.log(logging_tools.LOG_LEVEL_OK, log_str, logger)

    def warn(self, log_str, logger=None):
        self.log(logging_tools.LOG_LEVEL_WARN, log_str, logger)

    def error(self, log_str, logger=None):
        self.log(logging_tools.LOG_LEVEL_ERROR, log_str, logger)

    def critical(self, log_str, logger=None):
        self.log(logging_tools.LOG_LEVEL_CRITICAL, log_str, logger)

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
            return True if max([log_lev for log_lev, _log_str in self.log_buffer]) == logging_tools.LOG_LEVEL_OK else False
        else:
            return True

    def _get_value_xml(self, key, value):
        if type(value) == list:
            ret_val = E.value_list(**{
                "name": key,
                "num": "{:d}".format(len(value)),
                "type": "list",
            })
            for _val_num, sub_val in enumerate(value):
                ret_val.append(self._get_value_xml(key, sub_val))
        else:
            ret_val = E.value(
                value if isinstance(value, etree._Element) else unicode(value),  # @UndefinedVariable
                ** {
                    "name": key,
                    "type": {
                        int: "integer",
                        long: "integer",
                        str: "string",
                        unicode: "string",
                        float: "float",
                        etree._Element: "xml",  # @UndefinedVariable
                    }.get(type(value), "unknown")
                }
            )
        return ret_val

    def build_response(self):
        """
        builds the xml response
        """
        num_errors, num_warnings = (
            len([True for log_lev, _log_str in self.log_buffer if log_lev == logging_tools.LOG_LEVEL_ERROR]),
            len([True for log_lev, _log_str in self.log_buffer if log_lev == logging_tools.LOG_LEVEL_WARN]))
        return E.response(
            E.header(
                E.messages(
                    *[E.message(log_str, **{
                        "log_level": "{:d}".format(log_lev),
                        "log_level_str": logging_tools.get_log_level_str(log_lev)}) for log_lev, log_str in self.log_buffer]),
                **{"code": "{:d}".format(max([log_lev for log_lev, log_str in self.log_buffer] + [logging_tools.LOG_LEVEL_OK])),
                   "errors": "{:d}".format(num_errors),
                   "warnings": "{:d}".format(num_warnings),
                   "messages": "{:d}".format(len(self.log_buffer))}),
            E.values(
                *[self._get_value_xml(key, value) for key, value in self.val_dict.iteritems()]
            )
        )

    def __unicode__(self):
        """
        :returns: the unicode representation of xml response
        """
        return etree.tostring(self.build_response(), encoding=unicode)  # @UndefinedVariable

    def create_response(self):
        """
        creates a new xml response
        """
        return HttpResponse(
            unicode(self),
            content_type="application/xml",
        )


class xml_wrapper(object):
    def __init__(self, func):
        self.__name__ = func.__name__
        self.__doc__ = func.__doc__
        self._func = func

    def __repr__(self):
        return self._func

    def __call__(self, *args, **kwargs):
        request = args[0]
        request.xml_response = xml_response()
        ret_value = self._func(*args, **kwargs)
        if ret_value is None:
            return request.xml_response.create_response()
        else:
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
        msg_lines.extend([
            "",
            "djangouser : {}".format(unicode(request.user)),
            "PATH_INFO  : {}".format(request.META.get("PATH_INFO", "nor found")),
            "USER_AGENT : {}".format(request.META.get("HTTP_USER_AGENT", "not found"))])
    header_cs = "utf-8"
    mesg = email.mime.text.MIMEText("\n".join(msg_lines), _charset=header_cs)  # @UndefinedVariable
    mesg["Subject"] = "Python error"
    mesg["From"] = "python-error@init.at"
    mesg["To"] = "oekotex@init.at"
    srv = smtplib.SMTP()
    srv.connect(settings.MAIL_SERVER, 25)
    srv.sendmail(mesg["From"], mesg["To"].split(","), mesg.as_string())
    srv.close()


def update_session_object(request):
    # update request.session_object with user_vars
    if request.session and request.user is not None:
        # request.session["user_vars"] = dict([(user_var.name, user_var) for user_var in request.user.user_variable_set.all()])
        # copy layout vars from user_vars
        for var_name, attr_name, default in [
            ("east[isClosed]", "east_closed", True),
            ("west[isClosed]", "west_closed", False),
            ("sidebar_mode", "sidebar_mode", "group"),
        ]:
            if var_name in request.session.get("user_vars", {}):
                request.session[attr_name] = request.session["user_vars"][var_name].value
            else:
                request.session[attr_name] = default


def contact_server(request, srv_type, send_com, **kwargs):
    # log lines
    _log_lines = []
    # xml request
    _xml_req = kwargs.get("xml_request", hasattr(request, "xml_response"))
    # simple mapping
    cur_router = routing.srv_type_routing()
    if cur_router.has_type(srv_type):
        # print send_com.pretty_print()
        if request.user:
            send_com["user_id"] = request.user.pk
        _conn = net_tools.zmq_connection(
            kwargs.get("connection_id", "webfrontend"),
            timeout=kwargs.get("timeout", 10))
        # split to node-local servers ?
        if kwargs.get("split_send", True):
            send_list = cur_router.check_for_split_send(srv_type, send_com)
            if cur_router.no_bootserver_devices:
                # for _miss_pk, _miss_name in cur_router.no_bootserver_devices:
                cur_router._log(
                    request,
                    _log_lines,
                    "no bootserver for {}: {}".format(
                        logging_tools.get_plural("device", len(cur_router.no_bootserver_devices)),
                        ", ".join(sorted([_v[1] for _v in cur_router.no_bootserver_devices])),
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
        else:
            send_list = [(None, send_com)]
        if send_list:
            _conn_strs = []
            for _send_id, _send_com in send_list:
                if _send_id is None:
                    # no split send, decide based on target_server_id
                    _conn_str = cur_router.get_connection_string(srv_type, server_id=kwargs.get("target_server_id", None))
                else:
                    _conn_str = cur_router.get_connection_string(srv_type, server_id=_send_id)
                _conn_strs.append(_conn_str)
                _conn.add_connection(_conn_str, _send_com, multi=True, immediate=True)
            log_result = kwargs.get("log_result", True)
            log_error = kwargs.get("log_error", True)
            cur_router.start_result_feed()
            [
                cur_router.feed_result(
                    send_com,
                    _res,
                    request if _xml_req else None,
                    _conn_str,
                    _log_lines,
                    log_result,
                    log_error
                ) for _res, _conn_str in zip(_conn.loop(), _conn_strs)
            ]
            result = cur_router.result
        else:
            result = None
    else:
        result = None
        _err_str = u"srv_type '{}' not defined in routing".format(srv_type)
        cur_router._log(request, _log_lines, _err_str, logging_tools.LOG_LEVEL_ERROR)
    if _xml_req:
        return result
    else:
        return result, _log_lines
