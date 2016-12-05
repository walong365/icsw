# -*- coding: utf-8 -*-
#
# Copyright (C) 2013-2016 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of host-monitoring
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

""" host-monitoring / relay mixin """

from __future__ import unicode_literals, print_function

from initat.tools import logging_tools, process_tools
from .config import global_config

INIT_LIST = [
    ("register_server", True),
    ("init_module", False)
]


class HMHRMixin(object):
    def _init_commands(self):
        self.log("init commands")
        self.__delayed = []
        self.module_list = self.modules.module_list
        self.commands = self.modules.command_dict
        if self.modules.IMPORT_ERRORS:
            self.log("modules import errors:", logging_tools.LOG_LEVEL_ERROR)
            for mod_name, com_name, error_str in self.modules.IMPORT_ERRORS:
                self.log(
                    "{:<24s} {:<32s} {}".format(mod_name.split(".")[-1], com_name, error_str),
                    logging_tools.LOG_LEVEL_ERROR
                )
        _init_ok = True
        for cur_mod in self.modules.module_list:
            # init state flags for correct handling of shutdown (do not call close_module when
            # init_module was not called)
            cur_mod.INIT_STATE = {_name: False for _name, _flag in INIT_LIST}
        for call_name, add_self in INIT_LIST:
            for cur_mod in self.modules.module_list:
                if global_config["VERBOSE"]:
                    self.log(
                        "calling {} for module '{}'".format(
                            call_name,
                            cur_mod.name,
                        )
                    )
                try:
                    if add_self:
                        getattr(cur_mod, call_name)(self)
                    else:
                        getattr(cur_mod, call_name)()
                except:
                    exc_info = process_tools.exception_info()
                    for log_line in exc_info.log_lines:
                        self.log(log_line, logging_tools.LOG_LEVEL_CRITICAL)
                    _init_ok = False
                    break
                else:
                    cur_mod.INIT_STATE[call_name] = True
            if not _init_ok:
                break
        return _init_ok
