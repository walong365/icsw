# Copyright (C) 2015 Andreas Lang-Nevyjel, init.at
#
# this file is part of icsw-client
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
"""
simple interface to a file-base config store, file format is XML
"""

import array
import netifaces
import sys
import time
import os

from django.db.models import Q
import networkx
from initat.tools import configfile, logging_tools, process_tools
from lxml import etree


CS_NG = """
<element name="config-store" xmlns="http://relaxng.org/ns/structure/1.0">
    <attribute name="name">
    </attribute>
    <zeroOrMore>
        <element name="key-list">
            <oneOrMore>
                <element name="key">
                    <attribute name="name">
                    </attribute>
                    <attribute name="type">
                        <choice>
                            <value>int</value>
                            <value>str</value>
                            <value>bool</value>
                        </choice>
                    </attribute>
                    <optional>
                        <attribute name="description">
                        </attribute>
                    </optional>
                    <text/>
                </element>
            </oneOrMore>
        </element>
    </zeroOrMore>
</element>
"""


class ConfigStore(object):
    def __init__(self, name, log_com=None):
        self.store_name = name
        self.__log_com = log_com
        self.vars = {}
        self.read()

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        if self.__log_com:
            self.__log_com("[CS] {}".format(what), log_level)
        else:
            print "{} {}".format(logging_tools.get_log_level_str(log_level), what)

    def read(self):
        if os.path.isfile(self.store_name):
            try:
                _tree = etree.fromstring(file(self.store_name, "r").read())
            except:
                self.log(
                    "cannot read or interpret ConfigStore at '{}': {}".format(
                        self.store_name,
                        process_tools.get_except_info(),
                    ),
                    logging_tools.LOG_LEVEL_ERROR,
                )
            else:
                _ng = etree.RelaxNG(etree.fromstring(CS_NG))
                _valid = _ng.validate(_tree)
                if _valid:
                    _found, _parsed = (0, 0)
                    for _key in _tree.xpath(".//key", smart_strings=False):
                        _found += 1
                        _type = _key.attrib["type"]
                        _name = _key.attrib["name"]
                        _val = _key.text
                        try:
                            if _type == "int":
                                _val = int(_val)
                            elif _type == "bool":
                                _val = bool(_val)
                        except:
                            self.log(
                                "error casting key '{}' to {} (text was '{}'): {}".format(
                                    _name,
                                    _type,
                                    _key.text,
                                    process_tools.get_except_info(),
                                ),
                                logging_tools.LOG_LEVEL_ERROR,
                            )
                        else:
                            _parsed += 1
                            self.vars[_name] = _val
                    self.log(
                        "added {} from {} (found {})".format(
                            logging_tools.get_plural("variable", _parsed),
                            self.store_name,
                            logging_tools.get_plural("key", _found),
                        )
                    )
                else:
                    self.log(
                        "XML-tree from '{}' is invalid: {}".format(
                            self.store_name,
                            str(_ng.error_log),
                        ),
                        logging_tools.LOG_LEVEL_ERROR
                    )
        else:
            self.log("ConfigStore '{}' not found".format(self.store_name), logging_tools.LOG_LEVEL_ERROR)

    def __getitem__(self, key):
        return self.vars[key]

    def copy_to_global_config(self, global_config, mapping):
        _adds = []
        for _src, _dst in mapping:
            _val = self[_src]
            if type(_val) in [int, long]:
                _obj = configfile.int_c_var
            elif type(_val) == bool:
                _obj = configfile.bool_c_var
            else:
                _obj = configfile.str_c_var
            _adds.append(
                (_dst, _obj(_val, database=False, source="ConfigStore"))
            )
        global_config.add_config_entries(_adds)
