# Copyright (C) 2011-2017 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw-server
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
# -*- coding: utf-8 -*-
#

"""
system-wide constants for the ICSW
"""

import os
import platform
import sys
from enum import Enum

__all__ = [

    # config stores

    "GEN_CS_NAME",
    "DB_ACCESS_CS_NAME",
    "VERSION_CS_NAME",

    # directories

    "ICSW_ROOT",
    "CLUSTER_DIR",
    "CONFIG_STORE_ROOT",
    "USER_EXTENSION_ROOT",
    "LOG_ROOT",
    "MON_DAEMON_INFO_FILE",
    "PY_LIBDIR_SHORT",
    "SITE_PACKAGES_BASE",

    "INITAT_BASE",
    "INITAT_BASE_DEBUG",
    #
    "META_SERVER_DIR",
]

if hasattr(sys, "_MEIPASS"):
    IS_PYINSTALLER_BINARY = True
else:
    IS_PYINSTALLER_BINARY = False

class PlatformSystemTypeEnum(Enum):
    # none, never matches, for HM
    NONE = -1
    # for any, needed for HM
    ANY = 0
    LINUX = 1
    WINDOWS = 2
    UNKNOWN = 3


GEN_CS_NAME = "icsw.general"
DB_ACCESS_CS_NAME = "icsw.db.access"
VERSION_CS_NAME = "icsw.sysversion"

# python version
_PY_VERSION = "{:d}.{:d}".format(
    sys.version_info.major,
    sys.version_info.minor,
)
PY_LIBDIR_SHORT = "python{}".format(_PY_VERSION)

# cluster dir
_cluster_dir = os.path.join("/", "opt", "cluster")
_icsw_root = os.path.join("/", "opt", "cluster", "lib", PY_LIBDIR_SHORT, "site-packages")

_os_vars = {"ICSW_CLUSTER_DIR", "ICSW_ROOT"}

if any([_var in os.environ for _var in _os_vars]) and not all([_var in os.environ for _var in _os_vars]):
    print(
        "not all environment vars for debugging are set: {}".format(
            ", ".join(
                [
                    "{} ({})".format(
                        _var,
                        "present" if _var in os.environ else "not present",
                    ) for _var in sorted(_os_vars)
                ]
            )
        )
    )
    raise SystemExit
if platform.system() == "Linux":
    PLATFORM_SYSTEM_TYPE = PlatformSystemTypeEnum.LINUX
elif platform.system() == "Windows":
    PLATFORM_SYSTEM_TYPE = PlatformSystemTypeEnum.WINDOWS
else:
    PLATFORM_SYSTEM_TYPE = PlatformSystemTypeEnum.UNKNOWN

if PLATFORM_SYSTEM_TYPE == PlatformSystemTypeEnum.WINDOWS:
    import site

    CLUSTER_DIR = None
    for _path in site.getsitepackages():
        opt_path = os.path.join(_path, "opt")
        if os.path.exists(opt_path):
            CLUSTER_DIR = os.path.join(opt_path, "cluster")
            break
elif IS_PYINSTALLER_BINARY:
    CLUSTER_DIR = os.path.join(sys._MEIPASS, "opt", "cluster")
else:
    CLUSTER_DIR = os.environ.get("ICSW_CLUSTER_DIR", _cluster_dir)

ICSW_ROOT = os.environ.get("ICSW_ROOT", _icsw_root)

# user extension dir
USER_EXTENSION_ROOT = os.path.join(CLUSTER_DIR, "share", "user_extensions.d")
# changed from cluster to icsw due to clash with corosync packages
LOG_ROOT = "/var/log/icsw"
# monitoring daemon info
MON_DAEMON_INFO_FILE = os.path.join(CLUSTER_DIR, "etc", "mon_info")

SITE_PACKAGES_BASE = ICSW_ROOT
CONFIG_STORE_ROOT = os.path.join(CLUSTER_DIR, "etc", "cstores.d")

BACKBONE_DIR = os.path.join(ICSW_ROOT, "initat", "cluster", "backbone")

# system base
INITAT_BASE = os.path.join(SITE_PACKAGES_BASE, "initat")
# local debug base (== same as INITAT_BASE for production)
INITAT_BASE_DEBUG = os.path.dirname(__file__)

# meta server directory
META_SERVER_DIR = "/var/lib/meta-server"

WINDOWS_HM_VERSION = "3.0-11"
