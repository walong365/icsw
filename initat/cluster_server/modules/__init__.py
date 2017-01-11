# Copyright (C) 2012-2017 Andreas Lang-Nevyjel
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



import os

from initat.cluster_server.modules import cs_base_class
from initat.tools import process_tools

imp_dir = os.path.dirname(__file__)

__all__ = [
    str(cur_entry) for cur_entry in [
        entry.split(".")[0] for entry in os.listdir(imp_dir) if entry.endswith("_mod.py")
    ] if cur_entry and not cur_entry.startswith("_")
]

_new_hm_list = []
for mod_name in __all__:
    new_mod = __import__(mod_name, globals(), locals())
    _new_hm_list.extend(
        [
            cur_obj for cur_obj in [
                getattr(new_mod, key) for key in dir(new_mod)
            ] if type(cur_obj) == type and issubclass(cur_obj, cs_base_class.icswCSServerCom)
        ]
    )

error_log = []
command_dict = {}

for hm in _new_hm_list:
    try:
        command_dict[hm.__name__] = hm()
    except:
        error_log.append(
            "{} : {}".format(
                hm.__name__,
                process_tools.get_except_info()
            )
        )
    else:
        if not hm.Meta.disabled:
            command_dict[hm.__name__].name = hm.__name__
        else:
            del command_dict[hm.__name__]

command_names = sorted(command_dict.keys())
