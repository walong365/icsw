# Copyright (C) 2001-2017 Andreas Lang-Nevyjel, init.at
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
import os

from initat.md_config_server.special_commands.base import SpecialBase
from initat.tools import process_tools
from ..struct import DynamicCheckDict

__all__ = [
    b"dynamic_checks",
]


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
                # print("***", _key, _obj, _obj.Meta)
                dynamic_checks.feed(_key, _obj)
    except:
        exc_info = process_tools.exception_info()
        for log_line in exc_info.log_lines:
            dynamic_checks.import_errors.append((mod_name, "import", log_line))
