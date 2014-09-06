#!/usr/bin/python-init -Ot
#
# Copyright (C) 2014 Andreas Lang-Nevyjel
#
# this file is part of cluster-backbone-sql
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

""" reads and modifies local_settings.py """

import os
import sys
from django.utils.crypto import get_random_string

LS_FILE = "/etc/sysconfig/cluster/local_settings.py"


# a similar routine exists in setup_cluster.py
def check_local_settings():
    LS_DIR = os.path.dirname(LS_FILE)
    sys.path.append(LS_DIR)
    changed = False
    try:
        from local_settings import SECRET_KEY  # @UnresolvedImports
    except:
        SECRET_KEY = None
    try:
        from local_settings import PASSWORD_HASH_FUNCTION  # @UnresolvedImports
    except:
        PASSWORD_HASH_FUNCTION = "SHA1"
        changed = True
    try:
        from local_settings import GOOGLE_MAPS_KEY  # @UnresolvedImports
    except:
        changed = True
        GOOGLE_MAPS_KEY = ""
    if SECRET_KEY in [None, "None"]:
        chars = 'abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)'
        SECRET_KEY = get_random_string(50, chars)
        changed = True
    if changed:
        file(LS_FILE, "w").write("\n".join(
            [
                "SECRET_KEY = \"{}\"".format(SECRET_KEY),
                "PASSWORD_HASH_FUNCTION = \"{}\"".format(PASSWORD_HASH_FUNCTION),
                "GOOGLE_MAPS_KEY = \"{}\"".format(GOOGLE_MAPS_KEY),
                "",
            ]
        ))
    sys.path.remove(LS_DIR)

if __name__ == "__main__":
    check_local_settings()
