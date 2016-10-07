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
""" host_type_config, part of md-config-server """

import os

from lxml.builder import E

from initat.tools import logging_tools

__all__ = [
    "MonBaseContainer",
]


class MonBaseContainer(dict):
    def __init__(self, name, build_process):
        dict.__init__(self)
        # holds a list (and sometimes a dict) of config elements of the same type of {Flat, Structured}MonBaseConfig
        self.name = name
        self.__build_proc = build_process
        # clear list and dict
        self.clear()
        self.act_content, self.prev_content = ([], [])

    def ignore_content(self, obj):
        return False

    @property
    def object_list(self):
        return self._obj_list

    def add_object(self, value):
        self._obj_list.append(value)

    def clear(self):
        self._obj_list = []
        super(MonBaseContainer, self).clear()

    @property
    def is_valid(self):
        return True

    def get_file_name(self, etc_dir):
        if self.name in ["uwsgi"]:
            return "/opt/cluster/etc/uwsgi/icinga.wsgi.ini"
        else:
            return os.path.normpath(os.path.join(etc_dir, "{}.cfg".format(self.name)))

    def create_content(self):
        # if self.act_content:
        self.old_content = self.act_content
        self.act_content = self.get_content()

    def set_previous_config(self, prev_conf):
        self.act_content = prev_conf.act_content

    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        self.__build_proc.log(what, level)

    def get_content(self):
        act_list = self.object_list
        content = []
        _types = {}
        if act_list:
            for act_le in act_list:
                if self.ignore_content(act_le):
                    continue
                _types.setdefault(act_le.obj_type, []).append(True)
                content.extend(act_le.emit_content())
            self.log(
                "created {} for {}: {}".format(
                    logging_tools.get_plural("entry", len(act_list)),
                    logging_tools.get_plural("object_type", len(_types)),
                    ", ".join(sorted(_types.keys())),
                )
            )
        return content

    def get_xml(self):
        res_xml = getattr(E, "{}_list".format(self.name))()
        for act_le in self.object_list:
            if self.ignore_content(act_le):
                continue
            res_xml.append(act_le.emit_xml())
        return [res_xml]
