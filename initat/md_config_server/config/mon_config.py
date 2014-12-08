# Copyright (C) 2008-2014 Andreas Lang-Nevyjel, init.at
#
# this file is part of md-config-server
#
# Send feedback to: <lang-nevyjel@init.at>
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
""" config part of md-config-server """


__all__ = [
    "mon_config", "build_safe_name", "SimpleCounter",
    "unique_list",
]


# also used in parse_anovis
def build_safe_name(in_str):
    in_str = in_str.replace("/", "_").replace(" ", "_").replace("(", "[").replace(")", "]")
    while in_str.count("__"):
        in_str = in_str.replace("__", "_")
    return in_str


class mon_config(dict):
    def __init__(self, obj_type, name, **kwargs):
        # dict-like object, uses {key, list} as storage
        self.obj_type = obj_type
        self.name = name
        super(mon_config, self).__init__()
        for _key, _value in kwargs.iteritems():
            self[_key] = _value

    def __setitem__(self, key, value):
        if type(value) == list:
            if key in self:
                super(mon_config, self).__getitem__(key).extend(value)
            else:
                # important: create a new list
                super(mon_config, self).__setitem__(key, [_val for _val in value])
        else:
            if key in self:
                super(mon_config, self).__getitem__(key).append(value)
            else:
                super(mon_config, self).__setitem__(key, [value])

    def __getitem__(self, key):
        if key == "name":
            return self.name
        else:
            return super(mon_config, self).__getitem__(key)


class unique_list(object):
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
