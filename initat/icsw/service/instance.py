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
import hashlib

from lxml import etree
from lxml.builder import E

from initat.tools import logging_tools, process_tools
from .constants import SERVERS_DIR


def _dummy_log_com(what, log_level=logging_tools.LOG_LEVEL_OK):
    print("{} {}".format(logging_tools.get_log_level_str(log_level), what))


IGNORE_MD5S = {
    "39939c77aa728b14cd26ee10b7070401",
    "f06717b8d1334fe1e6ced9ee1f7cb9df",
}


class RelaxNG(object):
    cache = {}

    def __init__(self, start_dir, name):
        self.name = name
        if self.name not in RelaxNG.cache:
            RelaxNG.cache[self.name] = etree.RelaxNG(
                etree.fromstring(
                    file(
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
        md5.update(content)
        md5 = md5.hexdigest()
        if md5 in IGNORE_MD5S:
            # ignore certain files
            return True
        else:
            return self.ng.validate(in_xml)

    @property
    def error_log(self):
        return self.ng.error_log


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
        if __file__.startswith("/opt"):
            _dir = SERVERS_DIR
        else:
            # not beautiful but working
            _dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", SERVERS_DIR[1:])
        _inst_ng = RelaxNG(_dir, "instance")
        _overlay_ng = RelaxNG(_dir, "overlay")
        self.tree = E.instances()
        # lookup table for name / alias search
        self.__lut = {}
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
                    _tree_dict[entry] = etree.fromstring(_content)  # @UndefinedVariable
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
                _key for _key, _value in _tree_dict.iteritems() if not int(_value.get("overlay", "0"))
            ],
            [
                _key for _key, _value in _tree_dict.iteritems() if int(_value.get("overlay", "0"))
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
        for _inst_key in _inst_keys:
            for sub_inst in _tree_dict[_inst_key].findall("instance"):
                _add_list = [sub_inst.attrib["name"]]
                if "alias" in sub_inst.attrib:
                    for _an in sub_inst.attrib["alias"].split(","):
                        _add_list.append(_an)
                        self.__alias_lut[_an] = sub_inst.attrib["name"]
                for _name in _add_list:
                    if _name in self.__lut:
                        raise KeyError("name {} already present in instance lut".format(_name))
                    else:
                        self.__lut[_name] = sub_inst
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

    def __contains__(self, name):
        return name in self.__lut

    def __getitem__(self, name):
        return self.__lut[name]

    def get_alias_dict(self):
        return self.__alias_lut

    # utility functions
    def get_all_instances(self):
        return self.tree.findall(".//instance")

    # access functions
    def get_config_names(self, inst, only_contact=True):
        if isinstance(inst, basestring):
            inst = self[inst]
        # if only_contact is set to True only config_names where @contact=1 (or contact is not set) will be returned
        if only_contact:
            return inst.xpath(".//config_names/config_name[@contact='1' or not(@contact)]/text()")
        else:
            return inst.xpath(".//config_names/config_name/text()")

    def get_pid_file_name(self, inst):
        if isinstance(inst, basestring):
            inst = self[inst]
        return inst.attrib["pid_file_name"]

    def do_node_split(self, inst):
        if isinstance(inst, basestring):
            inst = self[inst]
        return True if inst.find(".//node-split") is not None else False

    def get_uuid_postfix(self, inst):
        if isinstance(inst, basestring):
            inst = self[inst]
        return inst.attrib["uuid-postfix"]

    def get_port_dict(self, inst, ptype=None, command=False):
        if isinstance(inst, basestring):
            inst = self[inst]
        _pd = {}
        for _port in inst.xpath(".//network/ports/port"):
            _pd[_port.get("type", "command")] = int(_port.text)
        if command:
            # return command port
            if len(_pd) == 1:
                return _pd.values()[0]
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
