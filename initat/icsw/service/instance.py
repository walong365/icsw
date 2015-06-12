#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001-2009,2011-2015 Andreas Lang-Nevyjel, init.at
#
# this file is part of python-modules-base
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

""" instance definition for services """

import os
from lxml import etree  # @UnresolvedImport

from lxml.builder import E  # @UnresolvedImport
from initat.tools import logging_tools
from initat.tools import process_tools
from .constants import SERVERS_DIR


class InstanceXML(object):
    def __init__(self, log_com):
        self.__log_com = log_com
        self.read()
        self.normalize()

    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        self.__log_com("[iXML] {}".format(what), level)

    @property
    def source_dir(self):
        return SERVERS_DIR

    def reread(self):
        self.read()
        self.normalize()

    def read(self):
        self.tree = E.instances()
        # check for additional instances
        _tree_dict = {}
        if os.path.isdir(SERVERS_DIR):
            for entry in [_file for _file in os.listdir(SERVERS_DIR) if _file.endswith(".xml")]:
                try:
                    _tree_dict[entry] = etree.fromstring(open(os.path.join(SERVERS_DIR, entry), "r").read())  # @UndefinedVariable
                except:
                    self.log(
                        "cannot read entry '{}' from {}: {}".format(
                            entry,
                            SERVERS_DIR,
                            process_tools.get_except_info(),
                        ),
                        logging_tools.LOG_LEVEL_ERROR
                    )
        _inst_keys, _overlay_keys = (
            [
                _key for _key, _value in _tree_dict.iteritems() if not int(_value.get("overlay", "0"))
            ],
            [
                _key for _key, _value in _tree_dict.iteritems() if int(_value.get("overlay", "0"))
            ],
        )
        for _inst_key in _inst_keys:
            for sub_inst in _tree_dict[_inst_key].findall("instance"):
                self.tree.append(sub_inst)
        for _overlay_key in _overlay_keys:
            for sub_inst in _tree_dict[_overlay_key].findall("instance"):
                _main_inst = self.tree.find("instance[@name='{}']".format(sub_inst.get("name")))
                if _main_inst is None:
                    self.log(
                        "cannot find instance with name '{}' for overlay".format(
                            sub_inst.get("name"),
                        ),
                        logging_tools.LOG_LEVEL_ERROR
                    )
                else:
                    # simply append, fixme todo: intelligent merge
                    for _el in sub_inst:
                        _main_inst.append(_el)

    def normalize(self):
        for cur_el in self.tree.findall("instance"):
            name = cur_el.attrib["name"]
            for key, def_value in [
                ("runs_on", "server"),
                ("any_threads_ok", "0"),
                ("pid_file_name", "{}.pid".format(name)),
                ("init_script_name", name),
                ("startstop", "1"),
                ("process_name", name),
                ("meta_server_name", name),
                # default wait time before killing processes
                ("wait_time", "10"),
            ]:
                if key not in cur_el.attrib:
                    cur_el.attrib[key] = def_value
