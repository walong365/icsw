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

for password-types we need to add some encryption / message digest code via {algorithm}hash

"""

import os
from lxml import etree

from initat.tools import process_tools, logging_tools
from lxml.builder import E

CS_NG = """
<element name="config-store" xmlns="http://relaxng.org/ns/structure/1.0">
    <attribute name="name">
    </attribute>
    <zeroOrMore>
        <element name="key-list">
            <zeroOrMore>
                <element name="key">
                    <attribute name="name">
                    </attribute>
                    <attribute name="type">
                        <choice>
                            <value>int</value>
                            <value>str</value>
                            <value>bool</value>
                            <value>password</value>
                        </choice>
                    </attribute>
                    <optional>
                        <attribute name="description">
                        </attribute>
                    </optional>
                    <text/>
                </element>
            </zeroOrMore>
        </element>
    </zeroOrMore>
</element>
"""

CONFIG_STORE_ROOT = os.path.join("/opt", "cluster", "etc", "cstores.d")


class ConfigVar(object):
    def __init__(self, name, val, descr=""):
        self.name = name
        self.value = val
        if type(self.value) in [int, long]:
            self._type = "int"
        elif type(self.value) is bool:
            self._type = "bool"
        else:
            self._type = "str"
        self.description = descr

    def set_type(self, _type):
        self._type = _type

    @staticmethod
    def interpret(el):
        _name = el.attrib["name"]
        _type = el.attrib["type"]
        _val = el.text
        try:
            if _type == "int":
                _val = int(_val)
            elif _type == "bool":
                _val = True if _val.lower() in ["y", "yes", "1", "true"] else False
            elif _type == "password":
                _val = _val
        except:
            raise ValueError(
                "error casting key '{}' to {} (text was '{}'): {}".format(
                    _name,
                    _type,
                    el.text,
                    process_tools.get_except_info(),
                )
            )
        else:
            return ConfigVar(_name, _val, descr=el.get("description", ""))

    def get_element(self):
        if self._type == "int":
            _val = "{:d}".format(self.value)
            _type = "int"
        elif self._type == "bool":
            _val = "True" if self.value else "False"
        else:
            _val = self.get_value()
        _el = E.key(
            _val,
            name=self.name,
            type=self._type,
        )
        if self.description:
            _el.attrib["description"] = self.description
        return _el

    def get_value(self):
        if self._type in ["str", "password"] and self.value is None:
            return ""
        else:
            return self.value


class ConfigStore(object):
    def __init__(self, name, log_com=None, read=True, quiet=False):
        self.file_name = ConfigStore.build_path(name)
        self.tree_valid = True
        self.name = name
        self.__quiet = quiet
        self.__log_com = log_com
        self.vars = {}
        if read:
            self.read()

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        if not self.__quiet:
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

    @staticmethod
    def exists(name):
        return os.path.exists(ConfigStore.build_path(name))

    @staticmethod
    def build_path(name):
        return os.path.join(CONFIG_STORE_ROOT, "{}_config.xml".format(name))

    @staticmethod
    def get_store_names():
        # return all valid store names
        return sorted(
            [
                entry[:-11] for entry in os.listdir(CONFIG_STORE_ROOT) if entry.endswith("_config.xml")
            ]
        )

    def read(self, name=None):
        if name is not None:
            _read_name = ConfigStore.build_path(name)
        else:
            _read_name = self.file_name
        if os.path.isfile(_read_name):
            self.tree_valid = False
            try:
                _tree = etree.fromstring(file(_read_name, "r").read())
            except:
                self.log(
                    "cannot read or interpret ConfigStore at '{}': {}".format(
                        _read_name,
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
                        try:
                            _new_var = ConfigVar.interpret(_key)
                        except:
                            self.log(
                                "error creating new var: {}".format(
                                    process_tools.get_except_info(),
                                ),
                                logging_tools.LOG_LEVEL_ERROR,
                            )
                        else:
                            _parsed += 1
                            self.vars[_new_var.name] = _new_var
                    self.log(
                        "added {} from {} (found {})".format(
                            logging_tools.get_plural("variable", _parsed),
                            _read_name,
                            logging_tools.get_plural("key", _found),
                        )
                    )
                else:
                    self.log(
                        "XML-tree from '{}' is invalid: {}".format(
                            _read_name,
                            str(_ng.error_log),
                        ),
                        logging_tools.LOG_LEVEL_ERROR
                    )
        else:
            self.log(
                "ConfigStore '{}' not found".format(
                    _read_name
                ),
                logging_tools.LOG_LEVEL_ERROR
            )

    def _generate(self):
        _root = E("config-store", name=self.name)
        _kl = E("key-list")
        for _key in sorted(self.vars.iterkeys()):
            _kl.append(self.vars[_key].get_element())
        _root.append(_kl)
        return _root

    def show(self):
        if self.tree_valid:
            return etree.tostring(self._generate(), pretty_print=True)

    @property
    def info(self):
        return "{} defined".format(logging_tools.get_plural("key", len(self.vars)))

    def write(self):
        # dangerous, use with care
        if self.tree_valid:
            try:
                file(self.file_name, "w").write(etree.tostring(self._generate(), pretty_print=True, xml_declaration=True))
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
                try:
                    os.chmod(self.file_name, 0664)
                except:
                    self.log(
                        "cannot change mod of {} to 0664: {}".format(
                            self.file_name,
                            process_tools.get_except_info(),
                        ),
                        logging_tools.LOG_LEVEL_ERROR
                    )
        else:
            self.log("tree is not valid", logging_tools.LOG_LEVEL_ERROR)

    def keys(self):
        if self.tree_valid:
            return self.vars.keys()
        else:
            return []

    def __getitem__(self, key):
        if self.tree_valid:
            return self.vars[key].get_value()
        else:
            raise ValueError("ConfigStore {} not valid".format(self.name))

    def __delitem__(self, key):
        if self.tree_valid:
            del self.vars[key]
        else:
            raise ValueError("ConfigStore {} not valid".format(self.name))

    def __setitem__(self, key, value):
        if key in self:
            _descr = self.vars[key].description
        else:
            _descr = ""
        self.vars[key] = ConfigVar(key, value, descr=_descr)

    def __contains__(self, key):
        return key in self.vars

    def get_dict(self, uppercase_keys=False):
        _dict = {}
        for _key, _value in self.vars.iteritems():
            if uppercase_keys:
                _key = _key.upper()
            _dict[_key] = _value.get_value()
        return _dict

    def set_type(self, key, _type):
        self.vars[key].set_type(_type)

    def copy_to_global_config(self, global_config, mapping):
        from initat.tools import configfile
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
