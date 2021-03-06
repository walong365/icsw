# Copyright (C) 2015-2017 Bernhard Mallinger, Andreas Lang-Nevyjel, init.at
#
# this file is part of icsw-server
#
# Send feedback to: <mallinger@init.at>, <lang-nevyjel@init.at>
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
""" simple frontend to LiveStatus socket, also used by md-config-server (for KPI) """

import csv
import os.path
import socket
import time
from enum import Enum

from initat.tools import logging_tools, process_tools


class LiveQuery(object):
    def __init__(self, conn, resource):
        self._conn = conn
        self._resource = resource
        self._columns = []
        self._filters = []

    def call(self):
        if self._columns:
            _res = self._conn.call(str(self), self._columns)
        else:
            _res = self._conn.call(str(self))
        if LiveSocket.livestatus_enum:
            _res = LiveSocket.map_result(self._conn.log_com, self._resource, _res)
        return _res

    def __str__(self):
        r_field = [
            "GET {}".format(self._resource)
        ]
        if self._columns:
            r_field.append("Columns: {}".format(" ".join(self._columns)))
        r_field.extend(self._filters)
        # print "\nQuery:\n" + "\n".join(r_field + ["", ""])
        return "\n".join(r_field + ["", ""])

    def columns(self, *args):
        if LiveSocket.livestatus_enum:
            self._columns = LiveSocket.lookup_enum(self._resource, *args)
        else:
            self._columns = args
        self._columns = [str(_val) for _val in self._columns]
        return self

    def filter(self, key, op, value, method="or", count=None):
        if not isinstance(value, list):
            value = [value]
        for entry in value:
            self._filters.append("Filter: {} {} {}".format(key, op, entry))
        _nv = len(value)
        _val = count if count is not None else _nv
        if _val > 1:
            self._filters.append("{}: {:d}".format(method.title(), _val))
        return self


class LiveSocket(object):
    livestatus_enum = None

    def __init__(self, log_com, peer_name):
        self.log_com = log_com
        self.peer = peer_name

    def __getattr__(self, name):
        return LiveQuery(self, name)

    def call(self, request, columns=None):
        s = None
        try:
            if len(self.peer) == 2:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            else:
                s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.connect(self.peer)
            s.send(request.encode("utf-8"))
            s.shutdown(socket.SHUT_WR)
            csv_lines = csv.DictReader(s.makefile(), columns, delimiter=';')
            _result = list(csv_lines)
        except:
            self.log_com(
                "an error occured in call(): {}".format(
                    process_tools.get_except_info()
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
            _result = []
        finally:
            if s is not None:
                s.close()
        return _result

    @classmethod
    def lookup_enum(cls, t_type, *keys):
        _enum = getattr(cls.livestatus_enum, t_type).value
        try:
            _resolved = [
                getattr(_enum, _key).value["name"] for _key in keys
            ]
        except AttributeError:
            for _key in keys:
                if not hasattr(_enum, _key):
                    raise AttributeError(
                        "Attribute '{}' not known in enum, possible values: {}".format(
                            _key,
                            ", ".join(sorted([_v.name for _v in list(_enum)])),
                        )
                    )
        return _resolved

    @classmethod
    def map_result(cls, log_com, t_type, res_list):
        def _parse_icinga_dict(value):
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
                    if _lkey in {"check_command_pk", "device_pk", "uuid", "mc_uuid"}:
                        _loc_dict[_lkey] = _loc_dict[_lkey][0]
            # print value, _loc_dict
            return _loc_dict

        _enum = getattr(cls.livestatus_enum, t_type).value
        for entry in res_list:
            for _key, _value in entry.items():
                try:
                    _type = getattr(_enum, _key).value["type"]
                    if _type == "int":
                        # integer
                        entry[_key] = int(_value)
                    elif _type == "time":
                        # unix time in seconds
                        entry[_key] = int(_value)
                    elif _type == "float":
                        # float as double
                        entry[_key] = float(_value)
                    elif _type == "string":
                        pass
                    elif _type == "dict":
                        # special icinga dict
                        entry[_key] = _parse_icinga_dict(_value)
                    else:
                        log_com(
                            "unknown type '{}' for key {} (value={})".format(_type, _key, _value),
                            logging_tools.LOG_LEVEL_ERROR
                        )
                except KeyError:
                    raise
        return res_list

    @classmethod
    def init_enum(cls, log_com, sock_name):
        DEBUG = False
        # init enum for livestatus queries
        s_time = time.time()
        _result = LiveSocket(log_com, sock_name).columns.call()
        # print("*", _result)
        _enum_list = []
        _dict = {}
        for entry in _result:
            _dict.setdefault(entry["table"], []).append(entry)
        if DEBUG:
            log_com("tables found: {:d}".format(len(list(_dict.keys()))))
        for _table in sorted(_dict.keys()):
            _len = len(_dict[_table])
            if DEBUG:
                log_com("dump for table {} ({} entries):".format(_table, _len))
            _enum_name_list = []
            for _num, _entry in enumerate(_dict[_table], 1):
                _enum_name_list.append(
                    (
                        _entry["name"],
                        {"type": _entry["type"], "name": _entry["name"]}
                    )
                )
                if DEBUG:
                    log_com(
                        "    [{:3d}/{:3d} {:<6s}] {}: {}".format(
                            _num,
                            _len,
                            _entry["type"],
                            _entry["name"],
                            _entry["description"],
                        )
                    )
            table_enum = Enum(
                value="Livestatus{}TableEnum".format(_table.title()),
                names=_enum_name_list
            )
            _enum_list.append((_table, table_enum))
            # print table_enum, len(table_enum), _enum_name_list
        # print(_enum_list)
        if len(_enum_list):
            cls.livestatus_enum = Enum(
                value="LivestatusEnum",
                names=_enum_list,
            )
        else:
            log_com("num_list is empty, skipping init", logging_tools.LOG_LEVEL_WARN)
        e_time = time.time()
        log_com("init_enum took {}".format(logging_tools.get_diff_time_str(e_time - s_time)))

    @classmethod
    def get_mon_live_socket(cls, log_com, global_config):
        sock_name = os.path.join(global_config["MD_BASEDIR"], "var", "live")
        if os.path.exists(sock_name):
            if not cls.livestatus_enum:
                cls.init_enum(log_com, sock_name)
            return LiveSocket(log_com, sock_name)
        else:
            raise IOError("socket '{}' does not exist".format(sock_name))
