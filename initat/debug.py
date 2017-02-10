#
# Copyright (C) 2016-2017 Andreas Lang-Nevyjel, init.at
#
# this file is part of icsw-server-client
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

to enable base debugging set the environment variable ICSW_DEBUG_SOFTWARE

to limit the debug calls of the server processes one can set
the environment vars

ICSW_DEBUG_MIN_RUN_TIME (in millisceonds)
ICSW_DEUBG_MIN_DB_CALLS (minimum database calls)


to log database calls set ICSW_DEUBG_SHOW_DB_CALLS

"""

import os

__all__ = [
    "ICSW_DEBUG_MODE",
    "ICSW_DEBUG_LEVEL",
    "ICSW_DEBUG_MIN_DB_CALLS",
    "ICSW_DEBUG_MIN_RUN_TIME",
    "ICSW_DEBUG_SHOW_DB_CALLS",
]

ICSW_DEBUG_MODE = True if os.environ.get("ICSW_DEBUG_SOFTWARE") else False
if ICSW_DEBUG_MODE:
    ICSW_DEBUG_LEVEL = int(os.environ.get("ICSW_DEBUG_LEVEL", "0"))
else:
    ICSW_DEBUG_LEVEL = 0
ICSW_DEBUG_MIN_RUN_TIME = float(os.environ.get("ICSW_DEBUG_MIN_RUN_TIME", "10000.0"))
ICSW_DEBUG_MIN_DB_CALLS = int(os.environ.get("ICSW_DEBUG_MIN_DB_CALLS", "100"))
ICSW_DEBUG_SHOW_DB_CALLS = True if os.environ.get("ICSW_DEBUG_SHOW_DB_CALLS") else False
