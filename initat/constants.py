# Copyright (C) 2011-2015 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of cluster-backbone-sql
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
# -*- coding: utf-8 -*-
#

"""
system-wide constants for the ICSW
"""

import os
import sys


GEN_CS_NAME = "icsw.general"
DB_ACCESS_CS_NAME = "icsw.db.access"
VERSION_CS_NAME = "icsw.sysversion"

# cluster dir
CLUSTER_DIR = "/opt/cluster"
# user extension dir
USER_EXTENSION_ROOT = os.path.join(CLUSTER_DIR, "share", "user_extensions.d")
LOG_ROOT = "/var/log/cluster"
_PY_VERSION = "{:d}.{:d}".format(
    sys.version_info.major,
    sys.version_info.minor
)
PY_LIBDIR_SHORT = "python{}".format(_PY_VERSION)
SITE_PACKAGES_BASE = os.path.join("/opt/python-init", "lib", PY_LIBDIR_SHORT, "site-packages")
INITAT_BASE = os.path.join(SITE_PACKAGES_BASE, "initat")
