#!/usr/bin/python-init -Otu

from initat.host_monitoring import hm_classes
import imp
import os
import pkgutil
import pprint
import process_tools
import sys

__all__ = [
    cur_entry for cur_entry in [
        entry.split(".")[0] for entry in os.listdir(os.path.dirname(__file__)) if entry.endswith(".py")
    ] if cur_entry and not cur_entry.startswith("_")
]

module_list = []
command_dict = {}
IMPORT_ERRORS = []

_new_hm_list = []
for mod_name in __all__:
    try:
        new_mod = __import__(mod_name, globals(), locals())
        if hasattr(new_mod, "_general"):
            new_hm_mod = new_mod._general(mod_name, new_mod)
            _new_hm_list.append((new_hm_mod.Meta().priority, new_hm_mod))
    except:
        exc_info = process_tools.exception_info()
        for log_line in exc_info.log_lines:
            IMPORT_ERRORS.append((mod_name, "import", log_line))

_new_hm_list.sort(reverse=True)

for _pri, new_hm_mod in sorted(_new_hm_list, reverse=True):
    new_mod = new_hm_mod.obj
    module_list.append(new_hm_mod)
    #if hasattr(new_mod, "init_m_vect"):
    #    getattr(new_mod, "init_m_vect")()
    loc_coms = [entry for entry in dir(new_mod) if entry.endswith("_command")]
    for loc_com in loc_coms:
        try:
            new_hm_mod.add_command(loc_com, getattr(new_mod, loc_com))
        except:
            exc_info = process_tools.exception_info()
            for log_line in exc_info.log_lines:
                IMPORT_ERRORS.append((new_mod.__name__, loc_com, log_line))
        #print getattr(getattr(new_mod, loc_com), "info_string", "???")
    command_dict.update(new_hm_mod.commands)
