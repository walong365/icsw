# Copyright (C) 2008-2014,2016 Andreas Lang-Nevyjel, init.at
#
# this file is part of md-config-server
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
""" config part of md-config-server """

import time

from lxml.builder import E

from initat.tools import logging_tools

__all__ = [
    "MonBaseConfig",
    "build_safe_name",
    "SimpleCounter",
    "MonUniqueList",
    "StructuredMonBaseConfig",
    "FlatMonBaseConfig",
    "CfgEmitStats",
    "LogBufferMixin",
]


class SimpleCounter(object):
    def __init__(self):
        self.num_ok = 0
        self.num_warning = 0
        self.num_error = 0

    def error(self, num=1):
        self.num_error += num

    def warning(self, num=1):
        self.num_warning += num

    def ok(self, num=1):
        self.num_ok += num


# also used in parse_anovis
def build_safe_name(in_str):
    in_str = in_str.replace("/", "_").replace(" ", "_").replace("(", "[").replace(")", "]")
    while in_str.count("__"):
        in_str = in_str.replace("__", "_")
    return in_str


class MonBaseConfig(dict):
    def __init__(self, obj_type, name, *args, **kwargs):
        # dict-like object, uses {key, list} as storage
        # every key references to a (unique) list of items
        self.obj_type = obj_type
        self.name = name
        # if set to True change handling of setitem
        # (allow only unique values, see below)
        self._flat_values = self.obj_type == "flat"
        super(MonBaseConfig, self).__init__()
        for _key, _value in args:
            self[_key] = _value
        for _key, _value in kwargs.iteritems():
            self[_key] = _value
        self.act_content, self.prev_content = ([], [])

    def __setitem__(self, key, value):
        _cur_v = self.setdefault(key, [])
        if type(value) != list:
            value = [value]
        if self._flat_values:
            _cur_v.extend([_v for _v in value if _v not in _cur_v])
        else:
            _cur_v.extend([_v for _v in value])

    def __getitem__(self, key):
        if key == "name":
            return self.name
        else:
            return super(MonBaseConfig, self).__getitem__(key)


class MonUniqueList(object):
    def __init__(self):
        self._list = set()

    def add(self, name):
        if name not in self._list:
            self._list.add(name)
            return name
        else:
            add_idx = 1
            while True:
                _name = "{}_{:d}".format(name, add_idx)
                if _name not in self._list:
                    break
                else:
                    add_idx += 1
            self._list.add(_name)
            return _name


class CfgEmitStats(object):
    def __init__(self):
        self.__start_time = time.time()
        self._written = set()
        self._written_empty = set()

    def add(self, key, empty=False):
        if empty:
            self._written_empty.add(key)
        else:
            self._written.add(key)

    def merge(self, other_stat):
        self._written |= other_stat.written
        self._written_empty |= other_stat.written_empty

    @property
    def info(self):
        return "{}, {}".format(
            logging_tools.get_plural("file", len(self._written)),
            logging_tools.get_plural("empty file", len(self._written_empty)),
        )

    @property
    def total_count(self):
        return self.count + len(self._written_empty)

    @property
    def count(self):
        return len(self._written)

    @property
    def runtime(self):
        return logging_tools.get_diff_time_str(time.time() - self.__start_time)

    @property
    def written(self):
        return self._written

    @property
    def written_empty(self):
        return self._written_empty

    @property
    def total_written(self):
        return self._written | self._written_empty


class LogBufferMixin(object):
    def __init__(self):
        self.__log_buffer = []

    def log(self, what, log_level=logging_tools.LOG_LEVEL_ERROR):
        self.__log_buffer.append((what, log_level))

    @property
    def buffered_logs(self):
        _logs = self.__log_buffer
        self.__log_buffer = []
        return _logs


class StructuredContentEmitter(object):
    """
    emitter for structured content
    define <OBJECT> {
        <KEY1> <VALUE1>
        ...
        <KEYn> <VALUEn>
    }
    """
    def emit_content(self):
        _content = [
            u"define {} {{".format(self.obj_type)
        ] + [
            u"  {} {}".format(
                act_key,
                self._build_value_string(act_key)
            ) for act_key in sorted(self.iterkeys())
        ] + [
            u"}",
            ""
        ]
        return _content

    def emit_xml(self):
        new_node = getattr(
            E, self.obj_type
        )(
            **dict(
                [
                    (
                        key,
                        self._build_value_string(key)
                    ) for key in sorted(self.iterkeys())
                ]
            )
        )
        return new_node

    def _build_value_string(self, _key):
        in_list = self[_key]
        # print self.obj_type, _key, in_list
        if in_list:
            # check for unique types
            if len(set([type(_val) for _val in in_list])) != 1:
                raise ValueError(
                    "values in list {} for key {} have different types".format(
                        str(in_list),
                        _key
                    )
                )
            else:
                _first_val = in_list[0]
                if type(_first_val) in [int, long]:
                    return ",".join(["{:d}".format(_val) for _val in in_list])
                else:
                    if "" in in_list:
                        raise ValueError(
                            "empty string found in list {} for key {}".format(
                                str(in_list),
                                _key
                            )
                        )
                    return u",".join([unicode(_val) for _val in in_list])
        else:
            return "-"


class FlatContentEmitter(object):
    """
    emitter for flat content
    <KEY1>=<VALUE1>
    ...
    <KEYn>=<VALUEn>
    """
    def emit_content(self):
        c_lines = []
        last_key = None
        for key in sorted(self.keys()):
            if last_key:
                if last_key[0] != key[0]:
                    c_lines.append("")
            last_key = key
            value = self[key]
            if key.count("[") and value == [None]:
                # for headers
                c_lines.append(key)
            else:
                if type(value) == list:
                    pass
                elif type(value) in [int, long]:
                    value = ["{:d}".format(value)]
                else:
                    value = [value]
                for act_v in value:
                    c_lines.append(u"{}={}".format(key, act_v))
        return c_lines


class StructuredMonBaseConfig(MonBaseConfig, StructuredContentEmitter):
    pass


class FlatMonBaseConfig(MonBaseConfig, FlatContentEmitter):
    pass
