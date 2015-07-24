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

import os
from lxml import etree

from initat.tools import configfile, logging_tools, process_tools
from lxml.builder import E


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


class ConfigVar(object):
    def __init__(self, name, val, descr=""):
        self.name = name
        self.value = val
        self.description = descr

    def get_element(self):
        if type(self.value) in [int, long]:
            _val = "{:d}".format(self.value)
            _type = "int"
        elif type(self.value) is bool:
            _val = "True" if self.value else "False"
            _type = "bool"
        else:
            _val = self.value
            _type = "str"
        _el = E.key(
            _val,
            name=self.name,
            type=_type,
        )
        if self.description:
            _el.attrib["description"] = self.description
        return _el


class ConfigStore(object):
    def __init__(self, name, log_com=None):
        self.file_name = name
        self.tree_valid = False
        self.name = None
        self.__log_com = log_com
        self.vars = {}
        self.read()

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        if self.__log_com:
            self.__log_com(
                "[CS {}] {}".format(
                    self.name if self.tree_valid else "N/V",
                    what,
                ),
                log_level
            )
        else:
            print "{} {}".format(logging_tools.get_log_level_str(log_level), what)

    def read(self):
        self.tree_valid = False
        if os.path.isfile(self.file_name):
            try:
                _tree = etree.fromstring(file(self.file_name, "r").read())
            except:
                self.log(
                    "cannot read or interpret ConfigStore at '{}': {}".format(
                        self.file_name,
                        process_tools.get_except_info(),
                    ),
                    logging_tools.LOG_LEVEL_ERROR,
                )
            else:
                _ng = etree.RelaxNG(etree.fromstring(CS_NG))
                _valid = _ng.validate(_tree)
                if _valid:
                    self.tree_valid = True
                    self.name = _tree.get("name", "")
                    _found, _parsed = (0, 0)
                    for _key in _tree.xpath(".//key", smart_strings=False):
                        _found += 1
                        _name = _key.attrib["name"]
                        _type = _key.attrib["type"]
                        _val = _key.text
                        try:
                            if _type == "int":
                                _val = int(_val)
                            elif _type == "bool":
                                _val = True if _val.lower() in ["y", "yes", "1", "true"] else False
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
                            self.vars[_name] = ConfigVar(_name, _val, descr=_key.get("description", ""))
                    self.log(
                        "added {} from {} (found {})".format(
                            logging_tools.get_plural("variable", _parsed),
                            self.file_name,
                            logging_tools.get_plural("key", _found),
                        )
                    )
                else:
                    self.log(
                        "XML-tree from '{}' is invalid: {}".format(
                            self.file_name,
                            str(_ng.error_log),
                        ),
                        logging_tools.LOG_LEVEL_ERROR
                    )
        else:
            self.log(
                "ConfigStore '{}' not found".format(
                    self.file_name
                ),
                logging_tools.LOG_LEVEL_ERROR
            )

    def write(self):
        # dangerous, use with care
        if self.tree_valid:
            _root = E("config-store", name=self.name)
            _kl = E("key-list")
            for _key, _var in self.vars.iteritems():
                _kl.append(_var.get_element())
            _root.append(_kl)
            try:
                file(self.file_name, "w").write(etree.tostring(_root, pretty_print=True, xml_declaration=True))
            except:
                self.log(
                    "cannot write tree to {}: {}".format(
                        self.file_name,
                        process_tools.get_except_info(),
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
            else:
                self.log("wrote to {}".format(self.file_name))
        else:
            self.log("tree is not valid", logging_tools.LOG_LEVEL_ERROR)

    def __getitem__(self, key):
        return self.vars[key].value

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
