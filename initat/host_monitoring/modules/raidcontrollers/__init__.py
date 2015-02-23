# Copyright (C) 2015 Andreas Lang-Nevyjel, init.at
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
""" load all defined raid controller commands """

import os
import inspect

from initat.host_monitoring.hm_classes import hm_command
from initat.host_monitoring.modules.raidcontrollers.base import ctrl_type


_mods = [
    cur_entry for cur_entry in [
        entry.split(".")[0] for entry in os.listdir(os.path.dirname(__file__)) if entry.endswith(".py")
    ] if cur_entry and not cur_entry.startswith("_")
]

COMMAND_DICT = {}
CTRL_DICT = {}

for mod_name in _mods:
    # no circular import
    if mod_name in ["base", "all"]:
        continue
    new_mod = __import__(mod_name, globals(), locals())
    for _name in dir(new_mod):
        _entry = getattr(new_mod, _name)
        if inspect.isclass(_entry):
            if _entry != ctrl_type and issubclass(_entry, ctrl_type):
                CTRL_DICT[_entry.Meta.name] = _entry
            elif _entry != hm_command and issubclass(_entry, hm_command):
                COMMAND_DICT[_name] = _entry
