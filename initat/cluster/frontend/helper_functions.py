#!/usr/bin/python-init -Otu
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

from config_tools import server_check, device_with_config, router_object
from django.conf import settings
from django.core.cache import cache
from django.db.models import Q
from django.http import HttpResponse
from initat.cluster.backbone.models import device
from lxml import etree # @UnresolvedImports
from lxml.builder import E # @UnresolvedImports
import email.mime
import json
import logging
import logging_tools
import net_tools
import process_tools
import server_command
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
                "name" : key,
                "num"  : "%d" % (len(value)),
                "type"  :"list",
            })
            for _val_num, sub_val in enumerate(value):
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
            len([True for log_lev, _log_str in self.log_buffer if log_lev == logging_tools.LOG_LEVEL_ERROR]),
            len([True for log_lev, _log_str in self.log_buffer if log_lev == logging_tools.LOG_LEVEL_WARN]))
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
        return HttpResponse(
            unicode(self),
            mimetype="application/xml",
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

def update_session_object(request):
    # update request.session_object with user_vars
    if request.session and request.user is not None:
        # request.session["user_vars"] = dict([(user_var.name, user_var) for user_var in request.user.user_variable_set.all()])
        # copy layout vars from user_vars
        for var_name, attr_name, default in [
            ("east[isClosed]", "east_closed" , True),
            ("west[isClosed]", "west_closed" , False),
            ("sidebar_mode"  , "sidebar_mode", "group"),
        ]:
            if var_name in request.session.get("user_vars", {}):
                request.session[attr_name] = request.session["user_vars"][var_name].value
            else:
                request.session[attr_name] = default

_SRV_TYPE_PORT_MAPPING = {
    "mother"    : 8000,
    "grapher"   : 8003,
    "server"    : 8004,
    "config"    : 8005,
    "package"   : 8007,
    "rms"       : 8009,
    "md-config" : 8010,
    "cransys"   : 8013,
}

_SRV_NAME_TYPE_MAPPING = {
    "mother"    : ["mother_server"],
    "grapher"   : ["rrd_server"],
    "server"    : ["server"],
    "config"    : ["config_server"],
    "package"   : ["package_server"],
    # sge_server is deprecated, still in use
    "rms"       : ["rms_server", "sge_server"],
    "md-config" : ["monitor_server"],
    "cransys"   : ["cransys_server"],
}

_NODE_SPLIT = ["mother", "config"]

class srv_type_routing(object):
    def __init__(self):
        self.logger = logging.getLogger("cluster.srv_routing")
        self._routing_key = "_WF_ROUTING"
        _resolv_dict = cache.get(self._routing_key)
        if _resolv_dict is None:
            _resolv_dict = self._build_resolv_dict()
        else:
            _resolv_dict = json.loads(_resolv_dict)
        self._resolv_dict = _resolv_dict
    def has_type(self, srv_type):
        return srv_type in self._resolv_dict
    def get_connection_string(self, srv_type, server_id=None):
        # server list
        _srv_list = self._resolv_dict[srv_type]
        if server_id:
            # filter
            _found_srv = [entry for entry in _srv_list if entry[2] == server_id]
            if not _found_srv:
                self.logger.critical("no server_id %d found for srv_type %s, taking first one" % (server_id, srv_type))
                _found_srv = _srv_list
        else:
            _found_srv = _srv_list
        # no server id, take first one
        return "tcp://%s:%d" % (
            _found_srv[0][1],
            _SRV_TYPE_PORT_MAPPING[srv_type],
        )
    def _build_resolv_dict(self):
        # local device
        _myself = server_check(server_type="", fetch_network_info=True)
        _router = router_object(self.logger)
        conf_names = sum(_SRV_NAME_TYPE_MAPPING.values(), [])
        # build reverse lut
        _rv_lut = {}
        for key, value in _SRV_NAME_TYPE_MAPPING.iteritems():
            _rv_lut.update({_name : key for _name in value})
        # resolve dict
        _resolv_dict = {}
        # get all config
        for _conf_name in conf_names:
            _srv_type = _rv_lut[_conf_name]
            _sc = device_with_config(config_name=_conf_name)
            if _conf_name in _sc:
                for _dev in _sc[_conf_name]:
                    # routing info
                    if _dev.effective_device.pk == _myself.device.pk:
                        _first_ip = "127.0.0.1"
                    else:
                        _ri = _dev.get_route_to_other_device(_router, _myself, allow_route_to_other_networks=True)
                        _first_ri = _ri[0]
                        _first_ip = _first_ri[2][1][0]
                    _resolv_dict.setdefault(_srv_type, []).append(
                        (
                            _dev.effective_device.full_name,
                            _first_ip,
                            _dev.effective_device.pk
                        )
                    )
                    self.logger.debug("adding device '%s' (IP %s, %d) to srv_type %s" % (
                        _dev.effective_device.full_name,
                        _first_ip,
                        _dev.effective_device.pk,
                        _srv_type,
                        )
                    )
        # missing routes
        _missing_srv = set(_SRV_NAME_TYPE_MAPPING.keys()) - set(_resolv_dict.keys())
        if _missing_srv:
            for _srv_type in sorted(_missing_srv):
                self.logger.warning("no device for srv_type '%s' found" % (_srv_type))
        # valid for 15 minutes
        cache.set(self._routing_key, json.dumps(_resolv_dict), 60 * 15)
        return _resolv_dict
    def check_for_split_send(self, srv_type, in_com):
        if srv_type in _NODE_SPLIT:
            return self._split_send(srv_type, in_com)
        else:
            return [(None, in_com)]
    def _split_send(self, srv_type, in_com):
        cur_devs = in_com.xpath(".//ns:devices/ns:devices/ns:device")
        _dev_dict = {}
        for _dev in cur_devs:
            _pk = int(_dev.attrib["pk"])
            _dev_dict[_pk] = etree.tostring(_dev)
        _pk_list = _dev_dict.keys()
        _cl_dict = {}
        for _value in device.objects.filter(Q(pk__in=_pk_list)).values_list("pk", "bootserver", "name"):
            if _value[1]:
                _cl_dict.setdefault(_value[1], []).append(_value[0])
            else:
                self.logger.error("device %d (%s) has no bootserver associated" % (
                    _value[0],
                    _value[2],
                ))
        # do we need more than one server connection ?
        if len(_cl_dict) > 1:
            _srv_keys = _cl_dict.keys()
            _srv_dict = {key : server_command.srv_command(source=etree.tostring(in_com.tree)) for key in _srv_keys}
            # clear devices
            [_value.delete_subtree("devices") for _value in _srv_dict.itervalues()]
            # add devices where needed
            for _key, _pk_list in _cl_dict.iteritems():
                _tree = _srv_dict[_key]
                _devlist = _tree.builder("devices")
                _tree["devices"] = _devlist
                _devlist.extend([etree.fromstring(_dev_dict[_pk]) for _pk in _pk_list])
                # print "T", _key, _tree.pretty_print()
            return [(key, value) for key, value in _srv_dict.iteritems()]
        else:
            return [(_cl_dict.keys()[0], in_com)]
    def start_result_feed(self):
        self.result = None
    def feed_result(self, orig_com, result, request, conn_str, log_lines, log_result, log_error):
        if result is None:
            if log_error:
                _err_str = "error contacting server %s, %s" % (
                    conn_str,
                    orig_com["command"].text
                )
                if request:
                    request.xml_response.error(_err_str)
                else:
                    log_lines.append((logging_tools.LOG_LEVEL_ERROR, _err_str))
        else:
            # TODO: check if result is et
            if log_result:
                log_str, log_level = result.get_log_tuple()
                if request:
                    request.xml_response.log(log_level, log_str)
                else:
                    log_lines.append((log_level, log_str))
            if self.result is None:
                self.result = result
            else:
                # merge result, TODO
                pass

def contact_server(request, srv_type, send_com, **kwargs):
    # log lines
    _log_lines = []
    # xml request
    _xml_req = kwargs.get("xml_request", hasattr(request, "xml_response"))
    # simple mapping
    cur_router = srv_type_routing()
    if cur_router.has_type(srv_type):
        conn_str = cur_router.get_connection_string(srv_type)
        # print send_com.pretty_print()
        if request.user:
            send_com["user_id"] = request.user.pk
        _conn = net_tools.zmq_connection(
            kwargs.get("connection_id", "webfrontend"),
            timeout=kwargs.get("timeout", 10))
        send_list = cur_router.check_for_split_send(srv_type, send_com)
        _conn_strs = []
        for _send_id, _send_com in send_list:
            _conn_str = cur_router.get_connection_string(srv_type, server_id=_send_id)
            _conn_strs.append(conn_str)
            _conn.add_connection(_conn_str, _send_com, multi=True)
        log_result = kwargs.get("log_result", True)
        log_error = kwargs.get("log_error", True)
        cur_router.start_result_feed()
        [cur_router.feed_result(send_com, _res, request if _xml_req else None, _conn_str, _log_lines, log_result, log_error) for _res, _conn_str in zip(_conn.loop(), _conn_strs)]
        result = cur_router.result
    else:
        result = None
        _err_str = "srv_type '%s' not defined in routing" % (srv_type)
        if _xml_req:
            request.xml_response.error(_err_str)
        else:
            _log_lines.append((logging_tools.LOG_LEVEL_ERROR, _err_str))
    if _xml_req:
        return result
    else:
        return result, _log_lines
