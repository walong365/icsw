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
""" load all notify background tasks """

import os
import inspect
from .base import BGInotifyTask


__all__ = ["BG_TASKS"]


_dir = os.path.dirname(os.path.abspath(__file__))

_files = [_entry.split(".")[0] for _entry in os.listdir(_dir) if _entry.endswith("_task.py")]

tasks = []
for mod_name in _files:
    new_mod = __import__(mod_name, globals(), locals())
    for _key in dir(new_mod):
        _value = getattr(new_mod, _key)
        if _value != BGInotifyTask and inspect.isclass(_value) and issubclass(_value, BGInotifyTask):
            tasks.append(_value)

BG_TASKS = tasks
