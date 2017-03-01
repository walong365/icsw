#
# Copyright (C) 2016-2017 Andreas Lang-Nevyjel, init.at
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
import time


__all__ = [
    "ICSW_DEBUG_MODE",
    "ICSW_DEBUG_LEVEL",
    "ICSW_DEBUG_MIN_DB_CALLS",
    "ICSW_DEBUG_MIN_RUN_TIME",
    "ICSW_DEBUG_SHOW_DB_CALLS",
    "ICSW_DEBUG_LOG_DB_CALLS",
    "ICSW_DEBUG_VARS",
]


# dummy defs
ICSW_DEBUG_MODE = None
ICSW_DEBUG_LEVEL = None
ICSW_DEBUG_SHOW_DB_CALLS = None
ICSW_DEBUG_MIN_DB_CALLS = None
ICSW_DEBUG_MIN_RUN_TIME = None
ICSW_DEBUG_DB_CALL_LOG = None


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

    def set_environ_value(self, value):
        os.environ[self.name] = str(value)


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
    icswDebugVar(
        "ICSW_DEBUG_DB_CALL_LOG",
        "",
        "file to log database-call statistic",
    )
]


# set debug vars
for _var in ICSW_DEBUG_VARS:
    _var.set_local_var()


def get_debug_var(name):
    return [_entry for _entry in ICSW_DEBUG_VARS if _entry.name == name][0]


def get_terminal_size():
    import shutil
    width, height = shutil.get_terminal_size()
    return width, height


def show_db_call_counter():
    if ICSW_DEBUG_SHOW_DB_CALLS:
        try:
            from django.db import connection
            print("DB-calls: {:d}".format(len(connection.queries)))
        except:
            print("error showing DB-calls")


def show_database_calls(*args, **kwargs):
    def to_stdout(_what):
        print(_what)

    output = kwargs.get("log_com", to_stdout)
    if ICSW_DEBUG_MODE and ICSW_DEBUG_SHOW_DB_CALLS:
        from django.db import connection
        _path = kwargs.get("path", "unknown")
        _runtime = kwargs.get("runtime", 0.0)
        tot_time = sum(
            [
                float(entry["time"]) for entry in connection.queries
            ],
            0.
        )
        if "log_com" in kwargs:
            # hm ...
            max_width = kwargs.get("max_width", 99999)
        else:
            try:
                max_width = get_terminal_size()[0]
            except:
                # no regular TTY, ignore
                max_width = None
        if max_width:
            if len(connection.queries) > ICSW_DEBUG_MIN_DB_CALLS:
                # only output if stdout is a regular TTY
                output(
                    "queries: {:d} in {:.2f} seconds".format(
                        len(connection.queries),
                        tot_time,
                    )
                )
                for act_sql in connection.queries:
                    if act_sql["sql"]:
                        out_str = act_sql["sql"].replace("\n", "<NL>")
                        _len_pre = len(out_str)
                        out_str = out_str[0:max_width - 21]
                        _len_post = len(out_str)
                        if _len_pre == _len_post:
                            _size_str = "     {:5d}".format(_len_pre)
                        else:
                            _size_str = "{:4d}/{:5d}".format(_len_post, _len_pre)
                        output(
                            "{:6.2f} [{}] {}".format(
                                float(act_sql["time"]),
                                _size_str,
                                out_str
                            )
                        )
        if ICSW_DEBUG_DB_CALL_LOG:
            _line = "t={} q={:4d} t={:8.4f} p={:<50s}\n".format(
                time.ctime(),
                len(connection.queries),
                _runtime,
                _path,
            )
            open(ICSW_DEBUG_DB_CALL_LOG, "a").write(_line)
