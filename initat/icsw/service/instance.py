#
# Copyright (C) 2001-2009,2011-2017 Andreas Lang-Nevyjel, init.at
#
# this file is part of icsw-client
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

""" instance definition for services """

import hashlib
import os

from lxml import etree
from lxml.builder import E

from initat.tools import logging_tools, process_tools
from .constants import SERVERS_DIR, CLUSTER_DIR

from initat.constants import PLATFORM_SYSTEM_TYPE, PlatformSystemTypeEnum, IS_PYINSTALLER_BINARY


def _dummy_log_com(what, log_level=logging_tools.LOG_LEVEL_OK):
    print("{} {}".format(logging_tools.get_log_level_str(log_level), what))


IGNORE_MD5S = {
    "39939c77aa728b14cd26ee10b7070401",
    "f06717b8d1334fe1e6ced9ee1f7cb9df",
}


class RelaxNG(object):
    cache = {}

    def __init__(self, start_dir, name):
        if PLATFORM_SYSTEM_TYPE == PlatformSystemTypeEnum.WINDOWS or IS_PYINSTALLER_BINARY:
            path_comps = []
            while True:
                start_dir, ext = os.path.split(start_dir)
                if ext == "cluster":
                    break
                path_comps.append(ext)

            start_dir = CLUSTER_DIR
            for path_comp in reversed(path_comps):
                start_dir = os.path.join(start_dir, path_comp)

        self.name = name
        if self.name not in RelaxNG.cache:
            RelaxNG.cache[self.name] = etree.RelaxNG(
                etree.fromstring(
                    open(
                        os.path.join(
                            start_dir,
                            "relax.d",
                            "{}.xml".format(self.name)
                        ),
                        "r"
                    ).read()
                )
            )
        self.ng = RelaxNG.cache[self.name]

    def validate(self, content, in_xml):
        md5 = hashlib.new("md5")
        md5.update(content.encode("ascii"))
        md5 = md5.hexdigest()
        if md5 in IGNORE_MD5S:
            # ignore certain files
            return True
        else:
            return self.ng.validate(in_xml)

    @property
    def error_log(self):
        return self.ng.error_log


def ResolveInstance(func):
    def wrapper(*args, **kwargs):
        _inst = args[0]
        _id = args[1]
        if isinstance(_id, str):
            _id = _inst[_id]
        elif _id.__class__.__name__ in ["icswClientEnum", "icswServerEnum"]:
            _id = _inst.resolve_enum(_id)
        return func(_inst, _id, *args[2:], **kwargs)
    return wrapper


class InstanceXML(object):
    def __init__(self, log_com=None, quiet=False):
        self.__quiet = quiet
        if log_com:
            self.__log_com = log_com
        else:
            self.__log_com = _dummy_log_com
        self.log("init")
        self.read()
        self.normalize()

    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        if not self.__quiet:
            self.__log_com("[iXML] {}".format(what), level)

    @property
    def source_dir(self):
        return SERVERS_DIR

    def reread(self):
        self.read()
        self.normalize()

    def read(self):
        relax_dir = os.path.dirname(__file__)
        if __file__.startswith("/opt") or "ICSW_CLUSTER_DIR" in os.environ:
            _dir = SERVERS_DIR
        else:
            # not beautiful but working
            _dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", SERVERS_DIR[1:])

        if PLATFORM_SYSTEM_TYPE == PlatformSystemTypeEnum.WINDOWS or IS_PYINSTALLER_BINARY:
            _dir = os.path.join(CLUSTER_DIR, "etc", "servers.d")

        _inst_ng = RelaxNG(_dir, "instance")
        _overlay_ng = RelaxNG(_dir, "overlay")
        self.tree = E.instances()
        # lookup table for name / alias search
        self.__lut = {}
        # enum lookup table
        self.__enum_lut = {}
        # alias lut
        self.__alias_lut = {}
        # check for additional instances
        _content_dict = {}
        _tree_dict = {}
        if os.path.isdir(_dir):
            for entry in [_file for _file in os.listdir(_dir) if _file.endswith(".xml")]:
                try:
                    _content = open(os.path.join(_dir, entry), "r").read()
                    _content_dict[entry] = _content
                    _tree_dict[entry] = etree.fromstring(_content)
                except:
                    self.log(
                        "cannot read entry '{}' from {}: {}".format(
                            entry,
                            _dir,
                            process_tools.get_except_info(),
                        ),
                        logging_tools.LOG_LEVEL_ERROR
                    )
        _inst_keys, _overlay_keys = (
            [
                _key for _key, _value in _tree_dict.items() if not int(_value.get("overlay", "0"))
            ],
            [
                _key for _key, _value in _tree_dict.items() if int(_value.get("overlay", "0"))
            ],
        )
        _to_remove = []
        for _keys, _relax, _catastrophic in [(_inst_keys, _inst_ng, True), (_overlay_keys, _overlay_ng, False)]:
            for _key in _keys:
                _valid = _relax.validate(_content_dict[_key], _tree_dict[_key])
                if not _valid:
                    if _catastrophic:
                        raise ValueError(
                            "cannot validate {} in {}: {}".format(
                                _key,
                                _dir,
                                str(_relax.error_log)
                            )
                        )
                    else:
                        self.log(
                            "error validating {} in {}: {}".format(
                                _key,
                                _dir,
                                str(_relax.error_log),
                            ),
                            logging_tools.LOG_LEVEL_ERROR
                        )
                        _to_remove.append(_key)
        for _key in _to_remove:
            del _tree_dict[_key]
        _inst_keys = list(set(_inst_keys) - set(_to_remove))
        _overlay_keys = list(set(_overlay_keys) - set(_to_remove))
        _first_instance = "client.xml"
        _inst_keys = [
            _entry for _entry in _inst_keys if _entry == _first_instance
        ] + [
            _entry for _entry in _inst_keys if _entry != _first_instance
        ]
        _IGNORE_DUPS = ["memcached"]
        for _inst_key in _inst_keys:
            for sub_inst in _tree_dict[_inst_key].findall("instance"):
                _add_list = [sub_inst.attrib["name"]]
                if "alias" in sub_inst.attrib:
                    for _an in sub_inst.attrib["alias"].split(","):
                        _add_list.append(_an)
                        self.__alias_lut[_an] = sub_inst.attrib["name"]
                for _name in _add_list:
                    if _name in self.__lut:
                        if _name in _IGNORE_DUPS:
                            # ignore
                            print("duplicate entry '{}' found, ignoring".format(_name))
                        else:
                            raise KeyError(
                                "name {} already present in instance lut".format(
                                    _name
                                )
                            )
                    else:
                        self.__lut[_name] = sub_inst
                for _enum_name in _tree_dict[_inst_key].xpath(".//config-enum/text()"):
                    self.__enum_lut[_enum_name] = sub_inst
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
        self._build_dependency_dict()

    def _build_dependency_dict(self):
        self.__needed_for_start = {}
        self.__needed_for_stop = {}
        # build dependencies
        for _iwd in self.tree.xpath("instance[.//dependencies]"):
            _inst_name = _iwd.attrib["name"]
            _needed = _iwd.xpath(".//dependencies/needed-for-start")
            for _need_el in _needed:
                _need = _need_el.text
                _sym = True if int(_need_el.get("symmetrical", "0")) else False
                if self.tree.find(".//instance[@name='{}']".format(_need)) is None:
                    if _need in {"memcached"}:
                        # transient error, ignore
                        _need = None
                    else:
                        raise KeyError("dependency '{}' for instance '{}' not found".format(_need, _inst_name))
                if _need == _inst_name:
                    raise KeyError("cannot depend on myself ({})".format(_inst_name))
                if _need is not None:
                    self.__needed_for_start.setdefault(_inst_name, []).append(_need)
                    if _sym:
                        self.__needed_for_stop.setdefault(_need, []).append(_inst_name)

    def get_start_dependencies(self, inst_name):
        # return list of required started instances for given instance name
        return self.__needed_for_start.get(inst_name, [])

    def get_stop_dependencies(self, inst_name):
        # return list of required stopped instances for given instance name
        return self.__needed_for_stop.get(inst_name, [])

    def __contains__(self, name):
        return name in self.__lut

    def __getitem__(self, name):
        return self.__lut[name]

    def get_alias_dict(self):
        return self.__alias_lut

    def resolve_enum(self, enum):
        if enum.name not in self.__enum_lut:
            print("**", enum.name, self.__enum_lut.keys())
        return self.__enum_lut[enum.name]

    # utility functions
    def get_all_instances(self):
        return self.tree.findall(".//instance")

    @ResolveInstance
    def get_config_enums(self, inst):
        # if only_contact is set to True only config_names where @contact=1 (or contact is not set) will be returned
        return inst.xpath(".//config-enums/config-enum/text()")

    @ResolveInstance
    def get_pid_file_name(self, inst):
        return inst.attrib["pid_file_name"]

    @ResolveInstance
    def get_attrib(self, inst):
        return dict(inst.attrib)

    @ResolveInstance
    def do_node_split(self, inst):
        return True if inst.find(".//node-split") is not None else False

    @ResolveInstance
    def get_uuid_postfix(self, inst):
        return inst.attrib["uuid-postfix"]

    @ResolveInstance
    def get_port_dict(self, inst, ptype=None, command=False):
        _pd = {}
        for _port in inst.xpath(".//network/ports/port"):
            _pd[_port.get("type", "command")] = int(_port.text)
        if command:
            # return command port
            if len(_pd) == 1:
                return list(_pd.values())[0]
            else:
                if "command" in _pd:
                    return _pd["command"]
                else:
                    raise KeyError("no 'command' port found in dict: {}".format(str(_pd)))
        elif ptype:
            # return given port type
            return _pd[ptype]
        else:
            return _pd

    def normalize(self):
        for cur_el in self.tree.findall("instance"):
            name = cur_el.attrib["name"]
            for key, def_value in [
                ("runs_on", "server"),
                ("any-processes-ok", "0"),
                ("sum-subprocesses", "0"),
                ("pid_file_name", "{}.pid".format(name)),
                ("init_script_name", name),
                ("startstop", "1"),
                ("status_from_pid", "0"),
                ("process_name", name),
                # default wait time before killing processes
                ("wait_time", "10"),
                ("ignore-for-service", "0"),
                # inherit start-type from check_type
                ("start-type", "inherit"),
            ]:
                if key not in cur_el.attrib:
                    cur_el.attrib[key] = def_value
