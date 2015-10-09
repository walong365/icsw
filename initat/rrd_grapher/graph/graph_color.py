# Copyright (C) 2007-2009,2013-2015 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file belongs to the rrd-server package
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
""" color structures for the grapher part of rrd-grapher service """

import os
import re
from lxml import etree

from initat.tools import logging_tools
from ..config import global_config
from .base_functions import full_graph_key


class SimpleColorTable(object):
    def __init__(self, entries):
        self.__entries = entries
        self.__idx = 0

    @property
    def color(self):
        _col = self.__entries[self.__idx]
        self.__idx += 1
        if self.__idx == len(self.__entries):
            self.__idx = 0
        return _col


class Colorizer(object):
    def __init__(self, log_com):
        self.log_com = log_com
        self.def_color_table = "dark28"
        self._gc_base = global_config["GRAPHCONFIG_BASE"]
        if not os.path.isdir(self._gc_base):
            # not defined, set old value
            self._gc_base = "/opt/cluster/share"
        self._read_files()

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.log_com("[col] {}".format(what), log_level)

    def _read_files(self):
        _ct_file = os.path.join(self._gc_base, "color_tables.xml")
        _cr_file = os.path.join(self._gc_base, "color_rules.xml")
        self.colortables = etree.fromstring(file(_ct_file, "r").read())
        self.color_tables = {}
        for c_table in self.colortables.findall(".//colortable[@name]"):
            self.color_tables[c_table.get("name")] = [
                "#{:s}".format(color.get("rgb")) for color in c_table if self._check_color(color)
            ]
        self.log("read colortables from {}".format(_ct_file))
        self.color_rules = etree.fromstring(file(_cr_file, "r").read())  # @UndefinedVariable
        self.log("read colorrules from {}".format(_cr_file))
        self.match_re_keys = [
            (
                re.compile(
                    "^{}".format(
                        entry.attrib["key"].replace(".", r"\.")
                    )
                ),
                entry
            ) for entry in self.color_rules.xpath(".//entry[@key]", smart_strings=False)
        ]
        # fast lookup table, store computed lookups
        self.fast_lut = {}

    def _check_color(self, color):
        cur_c = "#{}".format(color.get("rgb"))
        return (int(cur_c[1:3], 16) + int(cur_c[3:5], 16) + int(cur_c[5:7], 16)) < 3 * 224

    def reset(self):
        # reset values for next graph
        self.table_offset = {}

    def simple_color_table(self, name):
        if name in self.color_tables:
            return SimpleColorTable(self.color_tables[name])
        else:
            return SimpleColorTable(self.color_tables[self.color_tables.keys()[0]])

    def get_color_and_style(self, mvs_entry, mvv_entry):
        if hasattr(mvv_entry, "color"):
            # specified in entry
            _clr = getattr(mvv_entry, "color")
            s_dict = {}
            for _attr in["draw_type", "invert"]:
                if hasattr(mvv_entry, _attr):
                    s_dict[_attr] = getattr(mvv_entry, _attr)
        else:
            t_name, s_dict = self.get_table_name(mvs_entry, mvv_entry)
            if t_name not in self.table_offset:
                self.table_offset[t_name] = 0
            self.table_offset[t_name] += 1
            if self.table_offset[t_name] == len(self.color_tables[t_name]):
                self.table_offset[t_name] = 0
            _clr = self.color_tables[t_name][self.table_offset[t_name]]
            if "transparency" in s_dict:
                _clr = "{}{:02x}".format(_clr, int(s_dict["transparency"]))
        return _clr, s_dict

    def get_table_name(self, mvs_entry, mvv_entry):
        s_dict = {}
        key_name = full_graph_key(mvs_entry.key, mvv_entry.key)
        # print "* key for get_table_name(): ", key_name
        # already cached in fast_lut ?
        if key_name not in self.fast_lut:
            # no, iterate over files
            for c_re, c_entry in self.match_re_keys:
                if c_re.match(key_name):
                    self.fast_lut[key_name] = c_entry
        t_name = self.def_color_table
        if key_name in self.fast_lut:
            c_xml = self.fast_lut[key_name]
            if c_xml.find(".//range[@colortable]") is not None:
                t_name = c_xml.find(".//range[@colortable]").get("colortable")
            for modify_xml in c_xml.findall("modify"):
                if re.match(modify_xml.get("key_match"), key_name):
                    s_dict[modify_xml.attrib["attribute"]] = modify_xml.attrib["value"]
        return t_name, s_dict
