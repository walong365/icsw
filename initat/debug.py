#
# Copyright (C) 2016-2017 Andreas Lang-Nevyjel, init.at
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
debug settings for icsw

to enable base debugging set the environment variable ICSW_DEBUG_MODE

to limit the debug calls of the server processes one can set
the environment vars

ICSW_DEBUG_MIN_RUN_TIME (in millisceonds)
ICSW_DEUBG_MIN_DB_CALLS (minimum database calls)


to log database calls set ICSW_DEUBG_SHOW_DB_CALLS

"""

import os

__all__ = [
    "ICSW_DEBUG_MODE",
    "ICSW_DEBUG_LEVEL",
    "ICSW_DEBUG_MIN_DB_CALLS",
    "ICSW_DEBUG_MIN_RUN_TIME",
    "ICSW_DEBUG_SHOW_DB_CALLS",
    "ICSW_DEBUG_VARS",
]


class icswDebugVar(object):
    def __init__(self, name, default, descr):
        self.name = name
        self.default = default
        self.type = type(self.default)
        self.description = descr

    def cast(self, str_val):
        if isinstance(self.default, bool):
            return bool(str_val)
        elif isinstance(self.default, int):
            return int(str_val)
        elif isinstance(self.default, float):
            return float(str_val)
        else:
            return str_val

    @property
    def argparse_name(self):
        return self.name[11:].lower().replace("_", "-")

    @property
    def option_name(self):
        return self.name[11:].lower()

    def set_local_var(self):
        if self.name in os.environ:
            self.current = self.cast(os.environ[self.name])
        else:
            self.current = self.default
        globals()[self.name] = self.current

    def create_export_line(self, cur_value):
        return "export {}={}".format(
            self.name,
            str(cur_value),
        )

    def create_clear_line(self):
        return "unset {}".format(
            self.name
        )


ICSW_DEBUG_VARS = [
    icswDebugVar(
        "ICSW_DEBUG_MODE",
        False,
        "debug mode",
    ),
    icswDebugVar(
        "ICSW_DEBUG_LEVEL",
        0,
        "set icsw debug level",
    ),
    icswDebugVar(
        "ICSW_DEBUG_MIN_RUN_TIME",
        10000.0,
        "minimum runtime of service step in milliseconds",
    ),
    icswDebugVar(
        "ICSW_DEBUG_MIN_DB_CALLS",
        100,
        "mininum number of database-calls for service step",
    ),
    icswDebugVar(
        "ICSW_DEBUG_SHOW_DB_CALLS",
        False,
        "display of database calls",
    ),
]

for _var in ICSW_DEBUG_VARS:
    _var.set_local_var()
