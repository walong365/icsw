# Copyright (C) 2001-2016 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that i will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
""" importer for special modules """

from __future__ import unicode_literals, print_function

import inspect
import inflection
import os
from enum import Enum

from initat.md_config_server.special_commands.base import SpecialBase
from initat.tools import process_tools, logging_tools

__all__ = [
    b"dynamic_checks",
    b"DynamicCheckMode",
]


class DynamicCheckMode(Enum):
    # create config
    create = "create"
    # fetch dynamic updates
    fetch = "fetch"


class DynamicCheckResult(object):
    def __init__(self):
        # none, config, check or fetch
        self.r_type = "none"
        self.errors = []
        self.check_list = []
        self.config_list = []
        self.rewrite_lut = {}
        self.special_instance = None

    def feed_error(self, line):
        self.errors.append(line)

    def set_configs(self, lines):
        self.config_list.extend(lines)
        self.r_type = "config"

    def set_checks(self, lines):
        self.check_list.extend(lines)
        self.r_type = "check"

    def dump_errors(self, log_com):
        if self.errors:
            for _line in self.errors:
                log_com(_line, logging_tools.LOG_LEVEL_CRITICAL)

    def set_server_contact(self, s_instance):
        self.r_type = "fetch"
        self.special_instance = s_instance

    def __unicode__(self):
        return "DynamicCheckResult {}".format(self.r_type)


class DynamicCheckDict(object):
    def __init__(self):
        # list of classes
        self._class_list = []
        self._class_dict = {}
        self.import_errors = []

    def feed(self, key, obj):
        self._class_list.append(obj)
        self._class_dict[key] = obj

    @staticmethod
    def meta_to_class_name(name):
        return "Special{}".format(name)

    @property
    def class_dict(self):
        return self._class_dict

    def __getitem__(self, key):
        _key = DynamicCheckDict.meta_to_class_name(inflection.camelize(key))
        return self._class_dict[_key]

    def handle(self, gbc, hbc, cur_gc, s_check, mode):
        #
        rv = DynamicCheckResult()
        # mccs .... mon_check_command_special
        mccs = gbc.mccs_dict[s_check.mccs_id]
        # store name of mccs (for parenting)
        mccs_name = mccs.name
        if mccs.parent_id:
            # to get the correct command_line
            com_mccs = mccs
            # link to parent
            mccs = gbc.mccs_dict[mccs.parent_id]
        else:
            com_mccs = mccs
        # create lut entry to rewrite command name to mccs
        rv.rewrite_lut["check_command"] = mccs.md_name
        # print("***", _rewrite_lut)
        try:
            cur_special = self[mccs.name](
                hbc.log,
                self,
                # get mon_check_command (we need arg_ll)
                s_check=cur_gc["command"][com_mccs.md_name],
                parent_check=s_check,
                host=hbc.device,
                build_cache=gbc,
            )
        except:
            rv.feed_error(
                "unable to initialize special '{}': {}".format(
                    mccs.name,
                    process_tools.get_except_info()
                )
            )
        else:
            # calling handle to return a list of checks with format
            # [(description, [ARG1, ARG2, ARG3, ...]), (...)]
            try:
                if mode == DynamicCheckMode.create:
                    if mccs_name != mccs.name:
                        # for meta specials
                        sc_array = cur_special(mode, instance=mccs_name)
                    else:
                        sc_array = cur_special(mode)
                else:
                    # fetch mode, currently not supported for meta checks
                    if cur_special.Meta.meta:
                        self.log("mode {} not supported for meta checks".format(mode), logging_tools.LOG_LEVEL_CRITICAL)
                    else:
                        if cur_special.Meta.server_contact:
                            rv.set_server_contact(cur_special)
                        else:
                            pass
            except:
                exc_info = process_tools.exception_info()
                rv.feed_error(
                    "error calling special {}:".format(mccs.name),
                )
                for line in exc_info.log_lines:
                    rv.feed_error(" - {}".format(line))
                sc_array = []
            finally:
                cur_special.cleanup()
            if mode == DynamicCheckMode.create:
                if cur_special.Meta.meta and sc_array and mccs_name == mccs.name:
                    # dive in subcommands, for instance 'all SNMP checks'
                    # check for configs not really configured
                    _dead_coms = [_entry for _entry in sc_array if not hasattr(gbc.mccs_dict[_entry], "check_command_name")]
                    if _dead_coms:
                        rv.feed_error(
                            "unconfigured checks: {}".format(
                                ", ".join(sorted(_dead_coms))
                            ),
                        )
                    # we return a list of config (to be iterated again)
                    rv.set_configs(
                        [
                            gbc.mccs_dict[_entry].check_command_name for _entry in sc_array if _entry not in _dead_coms
                        ]
                    )
                else:
                    # we return a list of checks
                    rv.set_checks(sc_array)
        return rv


dynamic_checks = DynamicCheckDict()


_inst_list = [
    cur_entry for cur_entry in [
        entry.split(".")[0] for entry in os.listdir(
            os.path.join(
                os.path.dirname(__file__),
            )
        ) if entry.endswith(".py")
    ] if cur_entry and not cur_entry.startswith("_")
]

for mod_name in _inst_list:
    __all__.append(str(mod_name))
    try:
        full_name = "initat.md_config_server.special_commands.instances.{}".format(mod_name)
        new_mod = __import__(full_name, globals(), locals(), [str(mod_name)], -1)
        for _key in dir(new_mod):
            _obj = getattr(new_mod, _key)
            if inspect.isclass(_obj) and not _obj == SpecialBase and issubclass(_obj, SpecialBase):
                # print(_obj.Meta)
                dynamic_checks.feed(_key, _obj)
    except:
        exc_info = process_tools.exception_info()
        for log_line in exc_info.log_lines:
            dynamic_checks.import_errors.append((mod_name, "import", log_line))
