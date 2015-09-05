# -*- coding: utf-8 -*-
#
# Copyright (C) 2013-2015 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of host-monitoring
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

""" host-monitoring / relay mixin """

from initat.tools import logging_tools, process_tools

from .config import global_config


class HMHRMixin(object):
    def _init_commands(self):
        self.log("init commands")
        self.__delayed = []
        self.module_list = self.modules.module_list
        self.commands = self.modules.command_dict
        if self.modules.IMPORT_ERRORS:
            self.log("modules import errors:", logging_tools.LOG_LEVEL_ERROR)
            for mod_name, com_name, error_str in self.modules.IMPORT_ERRORS:
                self.log("{:<24s} {:<32s} {}".format(mod_name.split(".")[-1], com_name, error_str), logging_tools.LOG_LEVEL_ERROR)
        _init_ok = True
        for call_name, add_self in [
            ("register_server", True),
            ("init_module", False)
        ]:
            for cur_mod in self.modules.module_list:
                if global_config["VERBOSE"]:
                    self.log(
                        "calling {} for module '{}'".format(
                            call_name,
                            cur_mod.name
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
            if not _init_ok:
                break
        return _init_ok
