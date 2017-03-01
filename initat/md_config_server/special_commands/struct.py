# Copyright (C) 2008-2017 Andreas Lang-Nevyjel, init.at
#
# this file is part of icsw-server
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
""" structs fopr special (dynamic) tasks for md-config-server """

import inflection
from enum import Enum

from initat.tools import logging_tools, process_tools
from initat.host_monitoring.constants import DynamicCheckServer


__all__ = [
    "DynamicCheckServer",
    "DynamicCheckAction",
    "DynamicCheckActionCopyIp",
    "DynamicCheckDict",
    "DynamicCheckMode",
    "DynamicCheckResult",
]


class DynamicCheckResultType(Enum):
    # do nothing, error
    none = "none"
    # fetch result
    fetch = "fetch"
    # iterate: valid for meta checks (reiterate)
    iterate = "iterate"
    # check, we got some check result
    check = "check"


class DynamicCheckAction(object):
    def __init__(self, srv_enum, command, *args, **kwargs):
        self.srv_enum = srv_enum
        self.command = command
        self.args = args
        self.kwargs = kwargs

    def salt(self, hbc, special_instance):
        self.hbc = hbc
        self.special_instance = special_instance
        return self

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.special_instance.log(what, log_level)

    def __unicode__(self):
        return "DynamicCheckAction {} for {}".format(self.command, self.srv_enum.name)

    def __repr__(self):
        return str(self)


class DynamicCheckActionCopyIp(DynamicCheckAction):
    def salt(self, hbc, special_instance):
        DynamicCheckAction.salt(self, hbc, special_instance)
        self.kwargs["address"] = hbc.ip
        return self


class DynamicCheckMode(Enum):
    # create config
    create = "create"
    # fetch dynamic updates
    fetch = "fetch"


class DynamicCheckResult(object):
    def __init__(self):
        # none, config, check or fetch
        self.r_type = DynamicCheckResultType.none
        self.errors = []
        self.check_list = []
        self.config_list = []
        self.rewrite_lut = {}
        self.special_instance = None

    def feed_error(self, line):
        self.errors.append(line)

    def set_configs(self, lines):
        self.config_list.extend(lines)
        self.r_type = DynamicCheckResultType.iterate

    def set_checks(self, lines):
        self.check_list.extend(lines)
        self.r_type = DynamicCheckResultType.check

    def dump_errors(self, log_com):
        if self.errors:
            for _line in self.errors:
                log_com(_line, logging_tools.LOG_LEVEL_CRITICAL)

    def set_server_contact(self, s_instance):
        self.r_type = DynamicCheckResultType.fetch
        self.special_instance = s_instance

    def __unicode__(self):
        return "DynamicCheckResult {}".format(self.r_type)


class DynamicCheckDict(object):
    def __init__(self):
        # list of classes
        self._class_list = []
        self._class_dict = {}
        self.import_errors = []
        self.__log_cache = []
        self.__process = None

    def link(self, process):
        self.__process = process
        for what, level in self.__log_cache:
            self.log(what, level)
        self.__log_cache = []

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        if self.__process:
            self.__process.log("[DCD] {}".format(what), log_level)
        else:
            self.__log_cache.append((what, log_level))

    def feed(self, key, obj):
        self._class_list.append(obj)
        self._class_dict[key] = obj

    def valid_class_dict(self, log_com):
        # filter _class_dict and return only valid commands
        _res = {}
        for _name, _entry in self._class_dict.items():
            _inst = _entry(log_com)
            if self.meta_to_class_name(_inst.Meta.name) != _name:
                log_com(
                    "special {} has illegal name {}".format(
                        _name,
                        _inst.Meta.name
                    ),
                    logging_tools.LOG_LEVEL_CRITICAL
                )
            else:
                log_com("found special {}".format(_name))
                _res[_name] = _inst
        return _res

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
        # import reverse lut for meta subcommands
        # init Dynamic Check Result
        rv = DynamicCheckResult()
        # mccs .... mon_check_command_special
        # mccs = gbc.mccs_dict[s_check.mccs_id]
        mccs = s_check.mon_check_command_special
        # mccs to be called
        call_mccs = mccs
        # store name of mccs (for parenting)
        mccs_name = mccs.name
        if mccs.parent_id:
            # to get the correct command_line
            # link to parent
            mccs = mccs.parent
            check_has_parent = True
        else:
            check_has_parent = False
        # create lut entry to rewrite command name to mccs
        rv.rewrite_lut["check_command"] = mccs.dummy_mcc.unique_name
        # print("***", _rewrite_lut)
        try:
            # create special check instance
            cur_special = self[mccs.name](
                hbc.log,
                self,
                # get mon_check_command (we need arg_ll)
                s_check=cur_gc["command"][call_mccs.dummy_mcc.unique_name],
                # monitoring check command
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
                    if check_has_parent:
                        # for meta specials
                        sc_array = cur_special(mode, instance=mccs_name)
                    else:
                        # sc array is the list of instances to be called
                        sc_array = cur_special(mode)
                else:
                    # fetch mode, currently not supported for meta checks
                    if cur_special.Meta.meta:
                        self.log("mode {} not supported for meta checks".format(mode), logging_tools.LOG_LEVEL_CRITICAL)
                    else:
                        if cur_special.Meta.server_contact:
                            if hasattr(cur_special, "dynamic_update_calls") and hasattr(cur_special, "feed_result"):
                                rv.set_server_contact(cur_special)
                            else:
                                self.log(
                                    "specialcheck {} has no dynamic_update_calls() or feed_result() function".format(
                                        mccs_name,
                                    ),
                                    logging_tools.LOG_LEVEL_ERROR
                                )
            except:
                exc_info = process_tools.icswExceptionInfo()
                rv.feed_error(
                    "error calling special {}:".format(mccs.name),
                )
                for line in exc_info.log_lines:
                    rv.feed_error(" - {}".format(line))
                sc_array = []
            finally:
                cur_special.cleanup()
            if mode == DynamicCheckMode.create:
                if cur_special.Meta.meta and sc_array and not check_has_parent:
                    # dive in subcommands, for instance 'all SNMP checks'
                    # check for configs not really configured
                    # print("-" * 50)
                    # print("*", sc_array)
                    # this has to be fixed, check lines 329 ff. from build_cache.py
                    _dead_coms = [
                        # _entry for _entry in sc_array if not hasattr(gbc.mccs_dict[_entry], "check_command_name")
                    ]
                    if _dead_coms:
                        rv.feed_error(
                            "unconfigured checks: {}".format(
                                ", ".join(sorted(_dead_coms))
                            ),
                        )
                    # we return a list of config names (to be iterated over)

                    rv.set_configs(
                        [
                            META_SUB_REVERSE_LUT[_entry] for _entry in sc_array if _entry not in _dead_coms
                        ]
                    )
                else:
                    # we return a list of checks
                    rv.set_checks(sc_array)
        return rv
