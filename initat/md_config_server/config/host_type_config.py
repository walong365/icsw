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
""" host_type_config, part of md-config-server """

from initat.md_config_server.config.content_emitter import content_emitter
from lxml.builder import E  # @UnresolvedImport
import logging_tools


__all__ = [
    "host_type_config",
]


class host_type_config(content_emitter):
    def __init__(self, build_process):
        self.__build_proc = build_process
        self.act_content, self.prev_content = ([], [])

    def clear(self):
        self.__obj_list, self.__dict = ([], {})

    def is_valid(self):
        return True

    def create_content(self):
        # if self.act_content:
        self.old_content = self.act_content
        self.act_content = self.get_content()

    def set_previous_config(self, prev_conf):
        self.act_content = prev_conf.act_content

    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        self.__build_proc.log(what, level)

    def get_content(self):
        act_list = self.get_object_list()
        dest_type = self.get_name()
        content = []
        if act_list:
            for act_le in act_list:
                content.extend(self._emit_content(dest_type, act_le))
            self.log("created {} for {}".format(
                logging_tools.get_plural("entry", len(act_list)),
                dest_type))
        return content

    def get_xml(self):
        res_xml = getattr(E, "{}_list".format(self.get_name()))()
        for act_le in self.get_object_list():
            if self.ignore_content(act_le):
                continue
            new_node = getattr(
                E, self.get_name()
            )(
                **dict(
                    [
                        (
                            key,
                            self._build_value_string(key, act_le[key])
                        ) for key in sorted(act_le.iterkeys())
                    ]
                )
            )
            res_xml.append(new_node)
        return [res_xml]
