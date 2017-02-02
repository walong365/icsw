# Copyright (C) 2013-2017 Andreas Lang-Nevyjel, init.at
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
""" load all defined commands """

import hashlib
import importlib
import inspect
import os

from initat.host_monitoring.hm_classes import MonitoringCommand
from initat.tools import process_tools

__all__ = [
    cur_entry for cur_entry in [
        entry.split(".")[0] for entry in os.listdir(
            os.path.dirname(__file__)
        ) if entry.endswith(".py")
    ] if cur_entry and not cur_entry.startswith("_")
]
__all__.sort()

sha3_512_digester = hashlib.new("sha3_512")

module_list = []
command_dict = {}
IMPORT_ERRORS = []

_new_hm_list = []
for mod_name in __all__:
    mod_path = os.path.join(os.path.dirname(__file__), "{}.py".format(mod_name))
    try:
        with open(mod_path, "rb") as f:
            sha3_512_digester.update(f.read())
    except:
        pass

    try:
        new_mod = importlib.import_module("initat.host_monitoring.modules.{}".format(mod_name))
        if hasattr(new_mod, "_general"):
            new_hm_mod = new_mod._general(mod_name, new_mod)
            if new_hm_mod.enabled:
                _new_hm_list.append((new_hm_mod.Meta().priority, new_hm_mod))
    except:
        exc_info = process_tools.icswExceptionInfo()
        for log_line in exc_info.log_lines:
            IMPORT_ERRORS.append((mod_name, "import", log_line))

HOST_MONITOR_MODULES_HEX_CHECKSUM = sha3_512_digester.hexdigest()

del sha3_512_digester

_new_hm_list.sort(reverse=True, key=lambda x: x[0])

for _pri, new_hm_mod in sorted(_new_hm_list, key=lambda x: x[0], reverse=True):
    new_mod = new_hm_mod.obj
    module_list.append(new_hm_mod)
    loc_coms = [
        entry for entry in dir(new_mod) if entry.endswith("_command") and inspect.isclass(
            getattr(new_mod, entry)
        ) and issubclass(
            getattr(new_mod, entry), MonitoringCommand
        )
    ]
    for loc_com in loc_coms:
        try:
            new_hm_mod.add_command(loc_com, getattr(new_mod, loc_com))
        except:
            exc_info = process_tools.icswExceptionInfo()
            for log_line in exc_info.log_lines:
                IMPORT_ERRORS.append((new_mod.__name__, loc_com, log_line))
        # print getattr(getattr(new_mod, loc_com), "info_string", "???")
    command_dict.update(new_hm_mod.commands)
