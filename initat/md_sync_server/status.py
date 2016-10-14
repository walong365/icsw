# Copyright (C) 2001-2016 Andreas Lang-Nevyjel, init.at
#
# this file is part of md-sync-server
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
""" status process, queries data from icinga via mk_livestatus """

import json
import time

from .common import LiveSocket
from .config import global_config
from initat.tools import logging_tools, process_tools, server_command, \
    threading_tools

__all__ = [
    "LiveSocket",
    "StatusProcess",
]


class StatusProcess(threading_tools.process_obj):
    def process_init(self):
        global_config.close()
        self.__log_template = logging_tools.get_logger(
            global_config["LOG_NAME"],
            global_config["LOG_DESTINATION"],
            zmq=True,
            context=self.zmq_context,
            init_logger=True,
        )
        self.register_func("get_node_status", self._get_node_status)
        self.__columns_fetched = False
        self.register_timer(self.get_all_columns, 60, first_timeout=3)
        self.__socket = None

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)

    def loop_post(self):
        self._close()
        self.__log_template.close()

    def get_all_columns(self):
        if not self.__columns_fetched:
            cur_sock = self._open()
            if cur_sock:
                col_query = cur_sock.columns
                _result = col_query.call()
                _type_dict = {}
                _dict = {}
                for entry in _result:
                    _dict.setdefault(entry["table"], []).append(entry)
                self.log("tables found: {:d}".format(len(_dict.keys())))
                for _table in sorted(_dict.keys()):
                    self.log("dump for table {} ({}):".format(_table, len(_dict[_table])))
                    _type_dict[_table] = {}
                    for _entry in _dict[_table]:
                        self.log("    [{:<6s}] {}: {})".format(_entry["type"], _entry["name"], _entry["description"]))
                        _type_dict[_table][_entry["name"]] = _entry["type"][0]
                self.__columns_fetched = True
                # store type dict
                self.__type_dict = _type_dict

    def _close(self):
        if self.__socket:
            del self.__socket
            self.__socket = None

    def _open(self):
        if self.__socket is None:
            try:
                self.__socket = LiveSocket.get_mon_live_socket()
            except Exception as e:
                self.log(unicode(e), logging_tools.LOG_LEVEL_ERROR)
        return self.__socket

    def _parse_icinga_dict(self, value):
        # start with empty dict
        _loc_dict = {}
        # dictonary
        if value.strip():
            for _kv in value.split(","):
                if _kv.count("|"):
                    _lkey, _kv = _kv.split("|")
                    _lkey = _lkey.lower()
                    _loc_dict[_lkey] = []
                if _kv.isdigit():
                    _kv = int(_kv)
                _loc_dict[_lkey].append(_kv)
                if _lkey in {"check_command_pk", "device_pk", "uuid"}:
                    _loc_dict[_lkey] = _loc_dict[_lkey][0]
        # print value, _loc_dict
        return _loc_dict

    def map_values(self, t_type, res_list):
        _type_dict = self.__type_dict[t_type]
        for entry in res_list:
            for _key, _value in entry.iteritems():
                try:
                    _type = _type_dict[_key]
                    if _type == "i":
                        # integer
                        entry[_key] = int(_value)
                    elif _type == "t":
                        # unix time in seconds
                        entry[_key] = int(_value)
                    elif _type == "s":
                        pass
                    elif _type == "d":
                        # special icinga dict
                        entry[_key] = self._parse_icinga_dict(_value)
                    else:
                        # print "*", _key, _type, _value
                        pass
                except KeyError:
                    self.log("unknown key {} for table {}".format(_key, t_type), logging_tools.LOG_LEVEL_ERROR)
        return res_list

    def _get_node_status(self, srv_com_str, **kwargs):
        srv_com = server_command.srv_command(source=srv_com_str)
        # overview mode if overview is a top-level element
        _host_overview = True if "host_overview" in srv_com else False
        _service_overview = True if "service_overview" in srv_com else False
        if not _host_overview:
            # ToDo, FIXME: receive full names in srv_command
            dev_names = srv_com.xpath(".//device_list/device/@full_name", smart_strings=False)
            # dev_names = sorted([cur_dev.full_name for cur_dev in device.objects.filter(Q(pk__in=pk_list))])
        s_time = time.time()
        try:
            cur_sock = self._open()
            if cur_sock:
                if not self.__columns_fetched:
                    self.get_all_columns()
                if _host_overview:
                    host_query = cur_sock.hosts.columns(
                        "name",
                        "address",
                        "state",
                        "plugin_output",
                        "custom_variables",
                    )
                    if _service_overview:
                        service_query = cur_sock.services.columns(
                            "host_name",
                            "description",
                            "state",
                            "plugin_output",
                            "custom_variables",
                        )
                    else:
                        service_query = None
                else:
                    if dev_names:
                        service_query = cur_sock.services.columns(
                            "host_name",
                            "description",
                            "state",
                            "plugin_output",
                            "last_check",
                            "check_type",
                            "state_type",
                            "last_state_change",
                            "max_check_attempts",
                            "display_name",
                            "current_attempt",
                            "custom_variables",
                            "acknowledged",
                            "acknowledgement_type",
                        ).filter("host_name", "=", dev_names)
                        host_query = cur_sock.hosts.columns(
                            "name",
                            "address",
                            "state",
                            "plugin_output",
                            "last_check",
                            "check_type",
                            "state_type",
                            "last_state_change",
                            "max_check_attempts",
                            "current_attempt",
                            "custom_variables",
                            "acknowledged",
                            "acknowledgement_type",
                        ).filter("name", "=", dev_names)
                        host_comment_query = cur_sock.comments.columns(
                            "host_name",
                            "author",
                            "comment",
                            "entry_type",
                            "entry_time",
                        ).filter(
                            "host_name", "=", dev_names
                        ).filter_raw(
                            [
                                "Filter: is_service = 0",
                                "And: 2"
                            ]
                        )
                        service_comment_query = cur_sock.comments.columns(
                            "host_name",
                            "author",
                            "comment",
                            "entry_type",
                            "entry_time",
                        ).filter(
                            "host_name", "=", dev_names
                        ).filter_raw(
                            [
                                "Filter: is_service = 1",
                                "And: 2"
                            ]
                        )
                    else:
                        service_query, host_query, host_comment_query, service_comment_query = (None, None, None, None)
                if host_query is not None:
                    host_result = self.map_values("hosts", host_query.call())
                else:
                    host_result = []
                if service_query is not None:
                    service_result = self.map_values("services", service_query.call())
                else:
                    service_result = []
                if host_comment_query is not None:
                    host_comment_result = self.map_values("comments", host_comment_query.call())
                else:
                    host_comment_result = []
                if service_comment_query is not None:
                    service_comment_result = self.map_values("comments", service_comment_query.call())
                else:
                    service_comment_result = []
                if _host_overview:
                    # get dev_names from result
                    dev_names = [_entry["name"] for _entry in host_result]
                srv_com["service_result"] = json.dumps(
                    [
                        _line for _line in service_result if _line.get("host_name", "")
                    ]
                )
                srv_com["host_result"] = json.dumps(
                    host_result
                )
                # todo: add host comments to host / service results
                # import pprint
                # pprint.pprint(host_comment_result)
                # pprint.pprint(service_comment_result)
                srv_com.set_result(
                    "query for {} gave {} and {}".format(
                        logging_tools.get_plural("device", len(dev_names)),
                        logging_tools.get_plural("host result", len(host_result)),
                        logging_tools.get_plural("service result", len(service_result)),
                    )
                )
            else:
                srv_com.set_result("cannot connect to socket", server_command.SRV_REPLY_STATE_CRITICAL)
        except:
            self.log(u"fetch exception: {}".format(process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
            exc_info = process_tools.exception_info()
            for line in exc_info.log_lines:
                self.log(u" - {}".format(line), logging_tools.LOG_LEVEL_ERROR)
            self._close()
            srv_com.set_result(
                "exception during fetch",
                server_command.SRV_REPLY_STATE_CRITICAL
            )
        else:
            self.log(
                "queried {} in {}".format(
                    logging_tools.get_plural("device", len(dev_names)),
                    logging_tools.get_diff_time_str(time.time() - s_time),
                    # u", ".join(sorted(dev_names))
                )
            )
        self.send_pool_message("remote_call_async_result", unicode(srv_com))
