# -*- coding: utf-8 -*-
#
# Copyright (C) 2012-2017 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw-server
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

""" helper functions for the init.at clustersoftware """



import memcache
import time
from django.conf import settings
from django.http import HttpResponse
from lxml import etree
from lxml.builder import E

from initat.cluster.backbone import routing
from initat.tools import logging_tools, net_tools


class XMLWrapper(object):
    """
    provides a wrapper for XML-based response objects
    """
    def __init__(self):
        self.reset()

    def reset(self):
        """
        sets the xml response to the start state
        """
        self.log_buffer = []
        self.max_log_level = logging_tools.LOG_LEVEL_OK
        self.val_dict = {}

    def log(self, log_level, log_str, logger=None):
        self.max_log_level = max(self.max_log_level, log_level)
        self.log_buffer.append((log_level, log_str))
        if logger:
            logger.log(log_level, log_str)

    def clear_log_buffer(self):
        self.log_buffer = []

    def info(self, log_str, logger=None):
        self.log(logging_tools.LOG_LEVEL_OK, log_str, logger)

    def warn(self, log_str, logger=None):
        self.log(logging_tools.LOG_LEVEL_WARN, log_str, logger)

    def error(self, log_str, logger=None):
        self.log(logging_tools.LOG_LEVEL_ERROR, log_str, logger)

    def critical(self, log_str, logger=None):
        self.log(logging_tools.LOG_LEVEL_CRITICAL, log_str, logger)

    def feed_log_lines(self, lines):
        [self.feed_log_line(_lev, _str) for _lev, _str in lines]

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
        for key, value in in_dict.items():
            self[key] = value

    def is_ok(self):
        """
        checks the logging status, if OK
        """
        if self.log_buffer:
            return self.max_log_level == logging_tools.LOG_LEVEL_OK
        else:
            return True

    def _get_value_xml(self, key, value):
        if type(value) == list:
            ret_val = E.value_list(
                **{
                    "name": key,
                    "num": "{:d}".format(len(value)),
                    "type": "list",
                }
            )
            for _val_num, sub_val in enumerate(value):
                ret_val.append(self._get_value_xml(key, sub_val))
        else:
            ret_val = E.value(
                value if isinstance(value, etree._Element) else str(value),  # @UndefinedVariable
                ** {
                    "name": key,
                    "type": {
                        int: "integer",
                        int: "integer",
                        str: "string",
                        str: "string",
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
            len([True for log_lev, _log_str in self.log_buffer if log_lev == logging_tools.LOG_LEVEL_WARN])
        )
        return E.response(
            E.header(
                E.messages(
                    *[
                        E.message(
                            log_str,
                            **{
                                "log_level": "{:d}".format(log_lev),
                                "log_level_str": logging_tools.get_log_level_str(log_lev)
                            }
                        ) for log_lev, log_str in self.log_buffer
                    ]
                ),
                **{
                    "code": "{:d}".format(
                        max(
                            [
                                log_lev for log_lev, log_str in self.log_buffer
                            ] + [
                                logging_tools.LOG_LEVEL_OK
                            ]
                        )
                    ),
                    "errors": "{:d}".format(num_errors),
                    "warnings": "{:d}".format(num_warnings),
                    "messages": "{:d}".format(len(self.log_buffer))
                }
            ),
            E.values(
                *[self._get_value_xml(key, value) for key, value in self.val_dict.items()]
            )
        )

    def __unicode__(self):
        """
        :returns: the unicode representation of xml response
        """
        return etree.tostring(self.build_response(), encoding=str)  # @UndefinedVariable

    def show(self, logger=None):
        def _log(what, log_level=logging_tools.LOG_LEVEL_OK):
            if logger is None:
                print("[{}] {}".format(logging_tools.get_log_level_str(log_level), what))
        # log status to logger or stdout
        _log(
            "overal state is {}, {} defined:".format(
                logging_tools.get_log_level_str(self.max_log_level),
                logging_tools.get_plural("log message", len(self.log_buffer)),
            )
        )
        for _log_level, _log_str in self.log_buffer:
            _log(_log_str, _log_level)

    def create_response(self):
        """
        creates a new xml response
        """
        return HttpResponse(
            str(self),
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
        request.xml_response = XMLWrapper()
        ret_value = self._func(*args, **kwargs)
        if ret_value is None:
            return request.xml_response.create_response()
        else:
            return ret_value


class CachedMemcacheClient(object):
    def __init__(self):
        self.__read = False
        self.__client = None

    @property
    def address(self):
        if not self.__read:
            from initat.icsw.service.instance import InstanceXML
            _xml = InstanceXML(quiet=True)
            _port = _xml.get_port_dict("memcached", command=True)
            self.__address = ["127.0.0.1:{:d}".format(_port)]
            self.__read = True
        return self.__address

    @property
    def client(self):
        if self.__client is None:
            self.__client = memcache.Client(self.address, cache_cas=True)
        return self.__client


_C_MCC = CachedMemcacheClient()


def contact_server(request, srv_type_enum, send_com, **kwargs):
    # log lines
    _log_lines = []
    # xml request
    _xml_req = kwargs.get("xml_request", hasattr(request, "xml_response"))
    # simple mapping
    cur_router = routing.SrvTypeRouting()
    if srv_type_enum.name not in cur_router:
        # try again harder (rebuild routing table)
        cur_router = routing.SrvTypeRouting(force=True)

    if srv_type_enum.name in cur_router:
        # com = send_com["*command"]
        # connection id
        _conn_id = kwargs.get("connection_id", "webfrontend")
        # memcache key to catch multi-calls to server with this is
        # mc_key = "$$MCTS_KD_{}".format(_conn_id)
        # memcache key for connection dict
        mc_key = "{}_WebConDict".format(settings.ICSW_CACHE_KEY)
        mc_client = _C_MCC.client
        # print(dir(mc_client))
        # print("c=", _conn_id)
        # try to set default value (will most likely fail but never mind)
        _default_c = {"open": {}}
        # the open dict has the format
        # conn_id -> (last_time_used, request_pending)
        mc_client.add(mc_key, _default_c)
        _cur_time = time.time()
        _default_time = _cur_time - 3600
        _run_idx = 0
        while True:
            _c = mc_client.gets(mc_key)
            # print("gets={}".format(str(_c)))
            if _c is None:
                # should never happen, set default value again
                mc_client.add(mc_key, _default_c)
                continue
            if isinstance(_c["open"], list):
                _c["open"] = {}
            while True:
                _run_idx += 1
                cur_conn_id = "{}_{:d}".format(_conn_id, _run_idx)
                _open_entry = _c["open"].get(cur_conn_id, (_default_time, False))
                # connection has to be closed for at least 10 seconds
                if not _open_entry[1] and _open_entry[0] < _cur_time - 10:
                    # print("reuse")
                    break
            _c["open"][cur_conn_id] = (_cur_time, True)
            # import pprint
            # pprint.pprint(_c["open"])
            _ret = mc_client.cas(mc_key, _c)
            # print("_ret={}".format(_ret))
            if _ret:
                break
            else:
                # print("ERRLoop")
                pass
        # print("CurConnId={}".format(cur_conn_id))
        # print("list='{}' ({})".format(_c["open"], com))
        # print send_com.pretty_print()
        if request.user:
            send_com["user_id"] = request.user.pk
        _conn = net_tools.ZMQConnection(
            cur_conn_id,
            timeout=kwargs.get("timeout", 10)
        )
        # split to node-local servers ?
        if kwargs.get("split_send", True):
            send_list = cur_router.check_for_split_send(srv_type_enum.name, send_com)
            if cur_router.no_bootserver_devices:
                # for _miss_pk, _miss_name in cur_router.no_bootserver_devices:
                cur_router._log(
                    request,
                    _log_lines,
                    "no bootserver for {}: {}".format(
                        logging_tools.get_plural("device", len(cur_router.no_bootserver_devices)),
                        ", ".join(
                            sorted([_v[1] for _v in cur_router.no_bootserver_devices])
                        ),
                    ),
                    logging_tools.LOG_LEVEL_WARN
                )
        else:
            send_list = [(None, send_com)]
        if send_list:
            _conn_strs = []
            for _send_id, _send_com in send_list:
                if _send_id is None:
                    # get send_id from target_server_id
                    _send_id = kwargs.get("target_server_id", None)
                    # no split send, decide based on target_server_id
                #    _conn_str = cur_router.get_connection_string(srv_type, server_id=)
                # else:
                # print "*", _send_id
                _connect_port_enum = kwargs.get("connect_port_enum", None)
                _conn_str = cur_router.get_connection_string(
                    srv_type_enum,
                    server_id=_send_id,
                    connect_port_enum=_connect_port_enum
                )
                _conn_strs.append(_conn_str)
                _conn.add_connection(_conn_str, _send_com, multi=True, immediate=True)
            log_result = kwargs.get("log_result", True)
            log_error = kwargs.get("log_error", True)
            cur_router.start_result_feed()
            # merge results
            [
                cur_router.feed_srv_result(
                    send_com,
                    _res,
                    request if _xml_req else None,
                    _conn_str,
                    _log_lines,
                    log_result,
                    log_error,
                    srv_type_enum,
                ) for _res, _conn_str in zip(_conn.loop(), _conn_strs)
            ]
            result = cur_router.result
        else:
            result = None
        # remove cur_conn_id from cache
        while True:
            _c = mc_client.gets(mc_key)
            if _c is None:
                # should never happen, set default value again
                mc_client.add(mc_key, _default_c)
                continue
            # if cur_conn_id in _c["open"]:
            #    _c["open"].remove(cur_conn_id)
            _c["open"][cur_conn_id] = (time.time(), False)
            _ret = mc_client.cas(mc_key, _c)
            # print("_ret={}".format(_ret))
            if _ret:
                break
            else:
                # try again
                continue
        # print("done", cur_conn_id)
    else:
        result = None
        _err_str = "ServiceType '{}' not defined in routing".format(srv_type_enum.name)
        cur_router._log(request, _log_lines, _err_str, logging_tools.LOG_LEVEL_ERROR)
    if _xml_req:
        return result
    else:
        return result, _log_lines
