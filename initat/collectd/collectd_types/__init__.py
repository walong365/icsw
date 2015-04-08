#
# this file is part of collectd-init
#
# Copyright (C) 2013-2015 Andreas Lang-Nevyjel init.at
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
""" load all defined collectd types to handle icinga / nagios performance data """

import inspect
import os

import process_tools

from .base import PerfdataObject


_mods = [
    cur_entry for cur_entry in [
        entry.split(".")[0] for entry in os.listdir(os.path.dirname(__file__)) if entry.endswith(".py")
    ] if cur_entry and not cur_entry.startswith("_")
]

ALL_PERFDATA = {}
IMPORT_ERRORS = []

for mod_name in _mods:
    # no circular import
    if mod_name in ["base"]:
        continue
    try:
        new_mod = __import__(mod_name, globals(), locals())
    except:
        exc_info = process_tools.exception_info()
        IMPORT_ERRORS.extend(exc_info.log_lines)
    else:
        for _name in dir(new_mod):
            _entry = getattr(new_mod, _name)
            if inspect.isclass(_entry):
                if _entry != PerfdataObject and issubclass(_entry, PerfdataObject):
                    _inst = _entry()
                    ALL_PERFDATA["{}_{}".format(mod_name, _name)] = (_inst.PD_RE, _inst)
