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

    def read(self):
        self.tree = E.instances()
        # check for additional instances
        if os.path.isdir(SERVERS_DIR):
            for entry in os.listdir(SERVERS_DIR):
                if entry.endswith(".xml"):
                    try:
                        add_inst_list = etree.fromstring(open(os.path.join(SERVERS_DIR, entry), "r").read())  # @UndefinedVariable
                    except:
                        self.log(
                            "cannot read entry '{}' from {}: {}".format(
                                entry,
                                SERVERS_DIR,
                                process_tools.get_except_info(),
                            ),
                            logging_tools.LOG_LEVEL_ERROR
                        )
                    else:
                        for sub_inst in add_inst_list.findall("instance"):
                            self.tree.append(sub_inst)

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
            ]:
                if key not in cur_el.attrib:
                    cur_el.attrib[key] = def_value
