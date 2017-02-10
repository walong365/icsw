# Copyright (C) 2015-2017 Andreas Lang-Nevyjel, init.at
#
# this file is part of icsw-server-client
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
"""
simple interface to a file-base config store, file format is XML

for password-types we need to add some encryption / message digest code via {algorithm}hash

"""
try:
    import grp
except ImportError:
    grp = None
import os
import stat

from enum import Enum
from lxml import etree
from lxml.builder import E

from initat.constants import CONFIG_STORE_ROOT
from initat.tools import process_tools, logging_tools

__all__ = [
    "ConfigVar",
    "ConfigStore",
    "AccessModeEnum",
    "ConfigStoreError",
]


class ConfigStoreError(ValueError):
    pass


CS_NG = """
<element name="config-store" xmlns="http://relaxng.org/ns/structure/1.0">
    <attribute name="name">
    </attribute>
    <optional>
        <!-- now optional, no longer used -->
        <attribute name="dictstyle">
        </attribute>
    </optional>
    <optional>
        <attribute name="prefix">
        </attribute>
    </optional>
    <optional>
        <attribute name="access-mode">
            <choice>
                <!-- world readable -->
                <value>global</value>
                <!-- idg readable -->
                <value>local</value>
            </choice>
        </attribute>
    </optional>
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


class AccessModeEnum(Enum):
    GLOBAL = "global"
    LOCAL = "local"


ACCESS_MODE_DICT = {
    AccessModeEnum.GLOBAL: {
        "mode": 0o664,
    },
    AccessModeEnum.LOCAL: {
        "mode": 0o640,
    }
}


class ConfigVar(object):
    def __init__(self, name, val, descr=""):
        self.name = name
        self.value = val
        if isinstance(self.value, bool):
            self._type = "bool"
        elif isinstance(self.value, int):
            self._type = "int"
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
            raise ConfigStoreError(
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
    IDG_GID = None

    def __init__(
        self,
        name,
        log_com=None,
        read=True,
        quiet=False,
        prefix=None,
        access_mode=None,
        fix_access_mode=False,
        fix_prefix_on_read=True,
        raise_exception_on_read=True,
    ):
        # do not move this to a property, otherwise the Makefile will no longer work
        self.file_name = ConfigStore.build_path(name)
        self.tree_valid = True
        # if prefix is set all keys starting with prefix will act as dictionary lookup keys
        self.prefix = prefix
        self.name = name
        self.__quiet = quiet
        self.__log_com = log_com
        self.__raise_exception_on_read = raise_exception_on_read
        self.__uid, self.__gid, self.__mode = (None, None, None)
        self.vars = {}
        self.__required_access_mode = access_mode
        # checks prefix when reading and fix if necessary
        # if True the prefix from file is set to the argument value
        # if False we take the value from the file
        self.__fix_prefix_on_read = fix_prefix_on_read
        self.__access_mode = None
        if read:
            self.read()
            if fix_access_mode and self.__required_access_mode is not None and not self.access_mode_is_ok:
                self.write()

    def set_prefix(self, prefix, index):
        if self.prefix:
            raise ConfigStoreError("prefix already set ({})".format(self.prefix))
        vars = {_key: _value.get_value() for _key, _value in self.vars.items()}
        self.vars = {}
        self.prefix = prefix
        self[index] = vars

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
                print("{} {}".format(logging_tools.get_log_level_str(log_level), what))

    @staticmethod
    def remove_store(name):
        if os.path.exists(ConfigStore.build_path(name)):
            os.unlink(ConfigStore.build_path(name))

    @staticmethod
    def exists(name):
        # checks for existance and readability
        _exists = False
        if os.path.exists(ConfigStore.build_path(name)):
            try:
                _stat = os.stat(ConfigStore.build_path(name))
                if _stat[stat.ST_SIZE] == 0:
                    raise ConfigStoreError("empty size")
                open(ConfigStore.build_path(name), "r").read(1)
            except:
                pass
            else:
                _exists = True
        return _exists

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

    @property
    def idg_gid(self):
        if ConfigStore.IDG_GID is None:
            try:
                ConfigStore.IDG_GID = grp.getgrnam("idg").gr_gid
            except:
                ConfigStore.IDG_GID = None
        return ConfigStore.IDG_GID

    @property
    def access_mode_is_ok(self):
        return self.__access_mode is not None and self.__access_mode_is_ok

    def read(self, name=None):
        if name is not None:
            _read_name = ConfigStore.build_path(name)
        else:
            _read_name = self.file_name
        if os.path.isfile(_read_name):
            self.tree_valid = False
            try:
                _stat = os.stat(_read_name)
                _tree = etree.fromstring(open(_read_name, "r").read().encode("ascii"))
                self.__uid, self.__gid, self.__mode = (
                    _stat[stat.ST_UID],
                    _stat[stat.ST_GID],
                    _stat[stat.ST_MODE],
                )
            except:
                self.log(
                    "cannot read or interpret ConfigStore at '{}': {}".format(
                        _read_name,
                        process_tools.get_except_info(),
                    ),
                    logging_tools.LOG_LEVEL_ERROR,
                )
            else:
                if _stat[stat.ST_SIZE] == 0:
                    self.log("ConfigStore at '{}' is empty, deleting...".format(_read_name))
                    try:
                        os.unlink(_read_name)
                    except:
                        self.log("cannot delete, ignoring...", logging_tools.LOG_LEVEL_CRITICAL)
                else:
                    _ng = etree.RelaxNG(etree.fromstring(CS_NG))
                    _valid = _ng.validate(_tree)
                    if _valid:
                        self.tree_valid = True
                        self.name = _tree.get("name", "")
                        self.__access_mode_is_valid = False
                        try:
                            self.__access_mode = getattr(AccessModeEnum, _tree.get("access-mode", "global").upper())
                        except:
                            self.__access_mode = AccessModeEnum.GLOBAL
                        if self.__required_access_mode is not None and self.__required_access_mode != self.__access_mode:
                            self.__access_mode = self.__required_access_mode
                        # try to guess access mode
                        _t_mode = ACCESS_MODE_DICT[self.__access_mode]["mode"]
                        if (self.__mode & ~(_t_mode | stat.S_IFREG)) | _t_mode == _t_mode and self.__gid == self.idg_gid:
                            self.__access_mode_is_ok = True
                        else:
                            self.__access_mode_is_ok = False
                        _xml_prefix = _tree.get("prefix", "")
                        _rewrite = False
                        if (_xml_prefix or None) != self.prefix:
                            if self.__fix_prefix_on_read:
                                self.log(
                                    "prefix differs (self='{}', XML='{}'), rewriting file".format(
                                        self.prefix,
                                        _xml_prefix or None,
                                    ),
                                    logging_tools.LOG_LEVEL_ERROR,
                                )
                                _rewrite = True
                            else:
                                self.prefix = _xml_prefix
                        else:
                            self.prefix = _xml_prefix
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
                        if _rewrite:
                            self.log("rewriting file", logging_tools.LOG_LEVEL_WARN)
                            self.write()
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
        if not self.tree_valid and self.__raise_exception_on_read:
            raise ConfigStoreError(
                "Store '{}' is not valid, please check logs".format(
                    _read_name
                )
            )

    def _generate(self):
        _root = E("config-store", name=self.name)
        if self.prefix:
            _root.attrib.update(
                {
                    "prefix": self.prefix,
                }
            )
        if self.__access_mode is not None:
            _root.attrib.update(
                {
                    "access-mode": self.__access_mode.value,
                }
            )
        _kl = E("key-list")
        for _key in sorted(self.vars.keys()):
            _kl.append(self.vars[_key].get_element())
        _root.append(_kl)
        return _root

    def show(self):
        if self.tree_valid:
            return etree.tostring(
                self._generate(),
                pretty_print=True,
                encoding="utf-8"
            ).decode("utf-8")

    @property
    def info(self):
        return "{} and {} defined, {}, access mode is {} {}".format(
            logging_tools.get_plural("key", len(list(self.keys()))),
            logging_tools.get_plural("value", len(self.vars)),
            "prefix is '{}'".format(self.prefix) if self.prefix else "no prefix defined",
            "valid" if self.access_mode_is_ok else "invalid",
            self.__access_mode,
        )

    def write(self, access_mode=None):
        # dangerous, use with care
        if self.tree_valid:
            if access_mode is not None:
                self.__access_mode = access_mode
            try:
                open(self.file_name, "w").write(
                    etree.tostring(
                        self._generate(),
                        pretty_print=True,
                        xml_declaration=True,
                        encoding="ascii",
                    ).decode("utf-8")
                )
            except:
                self.log(
                    "cannot write tree to {}: {}".format(
                        self.file_name,
                        process_tools.get_except_info(),
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
            else:
                _mode_set_ok = True
                try:
                    _stat = os.stat(self.file_name)
                    os.chown(self.file_name, _stat[stat.ST_UID], self.idg_gid)
                except:
                    _mode_set_ok = False
                if self.__access_mode == AccessModeEnum.GLOBAL:
                    _tmod = 0o664
                else:
                    _tmod = 0o640
                try:
                    os.chmod(self.file_name, _tmod)
                except:
                    _mode_set_ok = False
                    self.log(
                        "cannot change mod of {} to {:o}: {}".format(
                            self.file_name,
                            _tmod,
                            process_tools.get_except_info(),
                        ),
                        logging_tools.LOG_LEVEL_ERROR
                    )
                self.log(
                    "wrote to {}, setting of mode {} was {}".format(
                        self.file_name,
                        self.__access_mode,
                        "successfull" if _mode_set_ok else "unsuccessfull",
                    ),
                    logging_tools.LOG_LEVEL_OK if _mode_set_ok else logging_tools.LOG_LEVEL_WARN,
                )
        else:
            self.log("tree is not valid", logging_tools.LOG_LEVEL_ERROR)

    def keys(self, **kwargs):
        only_dict = kwargs.get("only_dict", False)
        if self.tree_valid:
            if self.prefix:
                _keys = set()
                for _key in list(self.vars.keys()):
                    if _key.startswith("{}_".format(self.prefix)) and _key.count("_") > 1:
                        _keys.add(_key.split("_")[1])
                    else:
                        if not only_dict:
                            _keys.add(_key)
                return list(_keys)
            else:
                return list(self.vars.keys())
        else:
            return []

    def __getitem__(self, key):
        if self.tree_valid:
            if self.prefix and key not in self.vars:
                _r_dict = {}
                _pf = "{}_{}_".format(self.prefix, key)
                for _key in self.vars.keys():
                    if _key.startswith(_pf):
                        _r_dict[_key[len(_pf):]] = self.vars[_key].get_value()
                if _r_dict:
                    return _r_dict
                else:
                    raise ConfigStoreError("no dict-type structure with key {} found".format(key))
            else:
                return self.vars[key].get_value()
        else:
            raise ConfigStoreError("ConfigStore {} not valid".format(self.name))

    def get(self, key, default):
        if self.tree_valid:
            if key in self.vars:
                return self.vars[key].get_value()
            else:
                return default
        else:
            raise ConfigStoreError("ConfigStore {} not valid".format(self.name))

    def __delitem__(self, key):
        if self.tree_valid:
            del self.vars[key]
        else:
            raise ConfigStoreError("ConfigStore {} not valid".format(self.name))

    def __setitem__(self, key, value):
        if isinstance(value, dict):
            if self.prefix:
                for _skey, _svalue in value.items():
                    _full_key = "{}_{}_{}".format(
                        self.prefix,
                        key,
                        _skey,
                    )
                    self.vars[_full_key] = ConfigVar(_full_key, _svalue)
            else:
                raise ConfigStoreError("prefix needed to set dict-type values ({} -> {})".format(key, str(value)))
        else:
            if key in self:
                _descr = self.vars[key].description
            else:
                _descr = ""
            if isinstance(value, tuple):
                value, _descr = value
            self.vars[key] = ConfigVar(key, value, descr=_descr)

    def __contains__(self, key):
        if self.prefix:
            return key in list(self.keys())
        else:
            return key in self.vars

    def get_dict(self, uppercase_keys=False):
        _dict = {}
        for _key, _value in self.vars.items():
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
            if isinstance(_val, int):
                _obj = configfile.int_c_var
            elif isinstance(_val, bool):
                _obj = configfile.bool_c_var
            else:
                _obj = configfile.str_c_var
            _adds.append(
                (_dst, _obj(_val, database=False, source="ConfigStore"))
            )
        global_config.add_config_entries(_adds)


if __name__ == "__main__":
    # some test code
    cs = ConfigStore("test", prefix="a", read=False)
    cs["awqe"] = {
        "ab": 4,
        "c": True,
    }
    cs["xqe"] = {
        "ab": 4,
        "c": True,
    }
    cs["x"] = "la"
    print(cs.show())
    print(cs["awqe"])
    print(cs["xqe"])
    print(list(cs.keys()))
