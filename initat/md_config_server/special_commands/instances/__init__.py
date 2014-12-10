# Copyright (C) 2001-2014 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 2 as
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


import os
import process_tools

__all__ = [
    cur_entry for cur_entry in [
        entry.split(".")[0] for entry in os.listdir(
            os.path.join(
                os.path.dirname(__file__),
            )
        ) if entry.endswith(".py")
    ] if cur_entry and not cur_entry.startswith("_")
]

IMPORT_ERRORS = []

for mod_name in __all__:
    try:
        full_name = "initat.md_config_server.special_commands.instances.{}".format(mod_name)
        new_mod = __import__(full_name, globals(), locals(), [mod_name], -1)
        globals()[mod_name] = getattr(new_mod, mod_name)
    except:
        exc_info = process_tools.exception_info()
        for log_line in exc_info.log_lines:
            IMPORT_ERRORS.append((mod_name, "import", log_line))
