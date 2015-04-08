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

import os


__all__ = [
    "base_config",
]


class base_config(object):
    def __init__(self, name, **kwargs):
        self.__name = name
        self.__dict, self.__key_list = ({}, [])
        self.is_host_file = kwargs.get("is_host_file", False)
        self.belongs_to_ndo = kwargs.get("belongs_to_ndo", False)
        self.headers = kwargs.get("headers", [])
        for key, value in kwargs.get("values", []):
            self[key] = value
        self.act_content = []

    def get_name(self):
        return self.__name

    def get_file_name(self, etc_dir):
        if self.__name in ["uwsgi"]:
            return "/opt/cluster/etc/uwsgi/icinga.wsgi.ini"
        else:
            return os.path.normpath(os.path.join(etc_dir, "{}.cfg".format(self.__name)))

    def __setitem__(self, key, value):
        if key.startswith("*"):
            key, multiple = (key[1:], True)
        else:
            multiple = False
        if key not in self.__key_list:
            self.__key_list.append(key)
        if multiple:
            self.__dict.setdefault(key, []).append(value)
        else:
            self.__dict[key] = value

    def __getitem__(self, key):
        return self.__dict[key]

    def create_content(self):
        self.old_content = self.act_content
        c_lines = []
        last_key = None
        for key in self.__key_list:
            if last_key:
                if last_key[0] != key[0]:
                    c_lines.append("")
            last_key = key
            value = self.__dict[key]
            if type(value) == list:
                pass
            elif type(value) in [int, long]:
                value = [str(value)]
            else:
                value = [value]
            for act_v in value:
                c_lines.append("%s=%s" % (key, act_v))
        self.act_content = self.headers + c_lines
