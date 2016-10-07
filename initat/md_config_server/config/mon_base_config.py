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

import os
from .content_emitter import StructuredContentEmitter, FlatContentEmitter


__all__ = [
    "MonBaseConfig",
    "build_safe_name",
    "SimpleCounter",
    "MonUniqueList",
    "StructuredMonBaseConfig",
    "FlatMonBaseConfig",
]


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
        super(MonBaseConfig, self).__init__()
        for _key, _value in args:
            self[_key] = _value
        for _key, _value in kwargs.iteritems():
            self[_key] = _value
        self.act_content, self.prev_content = ([], [])

    def get_file_name(self, etc_dir):
        if self.name in ["uwsgi"]:
            return "/opt/cluster/etc/uwsgi/icinga.wsgi.ini"
        else:
            return os.path.normpath(os.path.join(etc_dir, "{}.cfg".format(self.name)))

    def __setitem__(self, key, value):
        _cur_v = self.setdefault(key, [])
        if type(value) != list:
            value = [value]
        if self.obj_type == "flat":
            _cur_v.extend([_v for _v in value if _v not in _cur_v])
        else:
            _cur_v.extend([_v for _v in value])

    def __getitem__(self, key):
        if key == "name":
            return self.name
        else:
            return super(MonBaseConfig, self).__getitem__(key)


class StructuredMonBaseConfig(MonBaseConfig, StructuredContentEmitter):
    pass


class FlatMonBaseConfig(MonBaseConfig, FlatContentEmitter):
    pass


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
