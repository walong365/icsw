# Copyright (C) 2015-2016 Bernhard Mallinger, Andreas Lang-Nevyjel, init.at
#
# this file is part of md-sync-server
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

from enum import Enum

from .config import global_config


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
            _res = LiveSocket.map_result(self._resource, _res)
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
        return self

    def filter_raw(self, filter_list):
        self._filters.extend(filter_list)
        return self

    def filter(self, key, op, value):
        if type(value) == list:
            for entry in value:
                self._filters.append("Filter: {} {} {}".format(key, op, entry))
            if len(value) > 1:
                self._filters.append("Or: {:d}".format(len(value)))
        else:
            self._filters.append("Filter: {} {} {}".format(key, op, value))
        return self


class LiveSocket(object):
    livestatus_enum = None

    def __init__(self, peer_name):
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
            s.send(request)
            s.shutdown(socket.SHUT_WR)
            csv_lines = csv.DictReader(s.makefile(), columns, delimiter=';')
            _result = list(csv_lines)
        except:
            _result = []
        finally:
            if s is not None:
                s.close()
        return _result

    @classmethod
    def lookup_enum(cls, t_type, *keys):
        _enum = getattr(cls.livestatus_enum, t_type).value
        return [getattr(_enum, _key).value["name"] for _key in keys]

    @classmethod
    def map_result(cls, t_type, res_list):
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
                    if _lkey in {"check_command_pk", "device_pk", "uuid"}:
                        _loc_dict[_lkey] = _loc_dict[_lkey][0]
            # print value, _loc_dict
            return _loc_dict

        _enum = getattr(cls.livestatus_enum, t_type).value
        for entry in res_list:
            for _key, _value in entry.iteritems():
                try:
                    _type = getattr(_enum, _key).value["type"]
                    if _type == "integer":
                        # integer
                        entry[_key] = int(_value)
                    elif _type == "time":
                        # unix time in seconds
                        entry[_key] = int(_value)
                    elif _type == "string":
                        pass
                    elif _type == "dict":
                        # special icinga dict
                        entry[_key] = _parse_icinga_dict(_value)
                    else:
                        # print "*", _key, _type, _value
                        pass
                except KeyError:
                    raise
        return res_list

    @classmethod
    def init_enum(cls, sock_name):
        # init enum for livestatus queries
        _result = LiveSocket(sock_name).columns.call()
        _enum_list = []
        _dict = {}
        for entry in _result:
            _dict.setdefault(entry["table"], []).append(entry)
        # self.log("tables found: {:d}".format(len(_dict.keys())))
        for _table in sorted(_dict.keys()):
            # self.log("dump for table {} ({}):".format(_table, len(_dict[_table])))
            _enum_name_list = []
            for _entry in _dict[_table]:
                _enum_name_list.append(
                    (
                        _entry["name"],
                        {"type": _entry["type"], "name": _entry["name"]}
                    )
                )
                # self.log("    [{:<6s}] {}: {})".format(_entry["type"], _entry["name"], _entry["description"]))
            table_enum = Enum(
                value="Livestatus{}TableEnum".format(_table.title()),
                names=_enum_name_list
            )
            _enum_list.append((_table, table_enum))
            # print table_enum, len(table_enum), _enum_name_list
        cls.livestatus_enum = Enum(
            value="LivestatusEnum",
            names=_enum_list,
        )

    @classmethod
    def get_mon_live_socket(cls):
        sock_name = os.path.join(global_config["MD_BASEDIR"], "var", "live")
        if os.path.exists(sock_name):
            if not cls.livestatus_enum:
                cls.init_enum(sock_name)
            return LiveSocket(sock_name)
        else:
            raise IOError("socket '{}' does not exist".format(sock_name))
