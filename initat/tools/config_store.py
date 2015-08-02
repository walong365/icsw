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
import sys
from lxml import etree
import argparse

from initat.tools import process_tools
from initat.tools.logging_tools import logbase
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
                            <value>password</value>
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
        self.read()

    def log(self, what, log_level=logbase.LOG_LEVEL_OK):
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
                print "{} {}".format(logbase.get_log_level_str(log_level), what)

    @staticmethod
    def exists(name):
        return os.path.exists(ConfigStore.build_path(name))

    @staticmethod
    def build_path(name):
        return os.path.join("/opt", "cluster", "etc", "cstores.d", "{}_config.xml".format(name))

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
                    logbase.LOG_LEVEL_ERROR,
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
                                logbase.LOG_LEVEL_ERROR,
                            )
                        else:
                            _parsed += 1
                            self.vars[_new_var.name] = _new_var
                    self.log(
                        "added {} from {} (found {})".format(
                            logbase.get_plural("variable", _parsed),
                            _read_name,
                            logbase.get_plural("key", _found),
                        )
                    )
                else:
                    self.log(
                        "XML-tree from '{}' is invalid: {}".format(
                            _read_name,
                            str(_ng.error_log),
                        ),
                        logbase.LOG_LEVEL_ERROR
                    )
        else:
            self.log(
                "ConfigStore '{}' not found".format(
                    _read_name
                ),
                logbase.LOG_LEVEL_ERROR
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
                    logbase.LOG_LEVEL_ERROR
                )
            else:
                self.log("wrote to {}".format(self.file_name))
        else:
            self.log("tree is not valid", logbase.LOG_LEVEL_ERROR)

    def __getitem__(self, key):
        if self.tree_valid:
            return self.vars[key].get_value()
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


if __name__ == "__main__":
    def quiet_log(_a, _b):
        pass

    _ap = argparse.ArgumentParser()
    _ap.add_argument("--mode", default="getkey", choices=["getkey", "storeexists", "keyexists"], type=str, help="Operation mode [%(default)s]")
    _ap.add_argument("--store", default="client", type=str, help="ConfigStore name [%(default)s]")
    _ap.add_argument("--key", default="", type=str, help="Key to show [%(default)s]")
    opts = _ap.parse_args()
    if opts.mode == "storeexists":
        if ConfigStore.exists(opts.store):
            sys.exit(0)
        else:
            sys.exit(1)
    elif opts.mode == "getkey":
        _store = ConfigStore(opts.store, log_com=quiet_log)
        if opts.key in _store:
            print(_store[opts.key])
            sys.exit(0)
        else:
            raise KeyError("unknown key '{}'".format(opts.key))
