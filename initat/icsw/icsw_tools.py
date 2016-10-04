#
# Copyright (C) 2016 Andreas Lang-Nevyjel, init.at
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

""" tools for icsw commands """

import os

from initat.tools import process_tools

__all__ = [
    "ICSW_DEBUG_MODE",
]

ICSW_DEBUG_MODE = process_tools.get_machine_name() in ["eddie", "lemmy"] and (
    os.environ.get("DEBUG_ICSW_SOFTWARE") or os.environ.get("ICSW_DEBUG_SOFTWARE")
)
