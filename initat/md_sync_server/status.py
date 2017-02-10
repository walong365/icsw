# Copyright (C) 2001-2017 Andreas Lang-Nevyjel, init.at
#
# this file is part of icsw-server-server
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

from initat.tools import logging_tools, process_tools, server_command, \
    threading_tools
from .common import LiveSocket
from .config import global_config

__all__ = [
    b"LiveSocket",
    b"StatusProcess",
]


class LivstatusFetch(dict):
    def __init__(self, log_com, live_socket):
        dict.__init__(self)
        self.__log_com = log_com
        self._socket = live_socket
        self.__start_time = time.time()

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_com("[LF] {}".format(what), log_level)

    def fetch(self):
        _src_keys = list(self.keys())
        _res_len = 0
        for _src_key in _src_keys:
            _dst_key = "{}_result".format(_src_key)
            self[_dst_key] = self[_src_key].call()
            _res_len += len(self[_dst_key])
        self._num_results = _res_len

    @property
    def info_str(self):
        self.__end_time = time.time()
        _query_keys = [key for key in self.keys() if not key.endswith("_result")]
        log_str = "{} gave {} in {}".format(
            logging_tools.get_plural("query", len(_query_keys)),
            logging_tools.get_plural("result", self._num_results),
            logging_tools.get_diff_time_str(self.__end_time - self.__start_time),
        )
        self.log(log_str)
        return log_str


class StatusProcess(threading_tools.icswProcessObj):
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
        self.__socket = None

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)

    def loop_post(self):
        self._close()
        self.__log_template.close()

    def _close(self):
        if self.__socket:
            del self.__socket
            self.__socket = None

    def _open(self):
        if self.__socket is None:
            try:
                self.__socket = LiveSocket.get_mon_live_socket(self.log)
            except Exception as e:
                self.log(str(e), logging_tools.LOG_LEVEL_ERROR)
        return self.__socket

    def _get_node_status(self, srv_com_str, **kwargs):
        def _salt_line(line, key, in_dict):
            line["_comments"] = in_dict.get(line[key], [])
            return line

        srv_com = server_command.srv_command(source=srv_com_str)
        # overview mode if overview is a top-level element
        _host_overview = True if "host_overview" in srv_com else False
        _service_overview = True if "service_overview" in srv_com else False
        if not _host_overview:
            # ToDo, FIXME: receive full names in srv_command
            dev_names = srv_com.xpath(".//device_list/device/@full_name", smart_strings=False)
            # dev_names = sorted([cur_dev.full_name for cur_dev in device.objects.filter(Q(pk__in=pk_list))])
        try:
            cur_sock = self._open()
            if cur_sock:
                fetch_dict = LivstatusFetch(self.log, cur_sock)
                if _host_overview:
                    fetch_dict["host"] = cur_sock.hosts.columns(
                        "name",
                        "address",
                        "state",
                        "plugin_output",
                        "custom_variables",
                    )
                    if _service_overview:
                        fetch_dict["service"] = cur_sock.services.columns(
                            "description",
                            "state",
                            "plugin_output",
                            "custom_variables",
                        )
                else:
                    if dev_names:
                        fetch_dict["service"] = cur_sock.services.columns(
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
                            "active_checks_enabled",
                        ).filter("host_name", "=", dev_names)
                        fetch_dict["host"] = cur_sock.hosts.columns(
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
                            "active_checks_enabled",
                        ).filter("name", "=", dev_names)
                        fetch_dict["host_comment"] = cur_sock.comments.columns(
                            "host_name",
                            "author",
                            "comment",
                            "entry_type",
                            "entry_time",
                        ).filter(
                            "host_name", "=", dev_names
                        ).filter(
                            "is_service", "=", "0",
                            method="and",
                            count=2,
                        )
                        fetch_dict["service_comment"] = cur_sock.comments.columns(
                            "host_name",
                            "service_description",
                            "author",
                            "comment",
                            "entry_type",
                            "entry_time",
                        ).filter(
                            "host_name", "=", dev_names
                        ).filter(
                            "is_service", "=", "1",
                            method="and",
                            count=2,
                        )
                        # print str(fetch_dict["service_comment"])
                fetch_dict.fetch()
                _host_comments = {}
                for entry in fetch_dict["host_comment_result"]:
                    _host_comments.setdefault(entry["host_name"], []).append(entry)
                _service_comments = {}
                for entry in fetch_dict["service_comment_result"]:
                    _service_comments.setdefault(entry["service_description"], []).append(entry)
                # import pprint
                # pprint.pprint(_host_comments)
                # pprint.pprint(_service_comments)
                srv_com["service_result"] = json.dumps(
                    [
                        _salt_line(_line, "description", _service_comments) for _line in fetch_dict["service_result"] if _line.get("host_name", "")
                    ]
                )
                # import pprint
                # pprint.pprint(fetch_dict["host_result"])
                srv_com["host_result"] = json.dumps(
                    [
                        _salt_line(_line, "name", _host_comments) for _line in fetch_dict["host_result"]
                    ]
                )
                srv_com.set_result(
                    fetch_dict.info_str
                )
                # print(srv_com.pretty_print())
            else:
                srv_com.set_result("cannot connect to socket", server_command.SRV_REPLY_STATE_CRITICAL)
        except:
            self.log("fetch exception: {}".format(process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
            exc_info = process_tools.icswExceptionInfo()
            for line in exc_info.log_lines:
                self.log(" - {}".format(line), logging_tools.LOG_LEVEL_ERROR)
            self._close()
            srv_com.set_result(
                "exception during fetch: {}".format(
                    process_tools.get_except_info()
                ),
                server_command.SRV_REPLY_STATE_CRITICAL
            )
        self.send_pool_message("remote_call_async_result", str(srv_com))
