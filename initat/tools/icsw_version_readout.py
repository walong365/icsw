#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001-2007,2010-2015 Andreas Lang-Nevyjel, init.at
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
""" read version from cstore """

import datetime
import os

from initat.constants import VERSION_CS_NAME
from initat.tools import config_store

__all__ = [
    "VERSION_STRING",
    "VERSION_MAJOR",
    "VERSION_MINOR",
    "BUILD_TIME",
    "BUILD_MACHINE",
]


if config_store.ConfigStore.exists(VERSION_CS_NAME):
    _vers = config_store.ConfigStore(VERSION_CS_NAME, quiet=True)
    VERSION_STRING = _vers["software"]
    if "build.time" in _vers:
        BUILD_TIME = _vers["build.time"]
        BUILD_MACHINE = _vers["build.machine"]
    else:
        BUILD_TIME = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        BUILD_MACHINE = os.uname()[1]
else:
    VERSION_STRING = "0.0-0"
    BUILD_TIME = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    BUILD_MACHINE = os.uname()[1]

VERSION_MAJOR = VERSION_STRING.split("-")[0]
VERSION_MINOR = VERSION_STRING.split("-")[0]
