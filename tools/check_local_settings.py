#!/usr/bin/python-init -Ot
#
# Copyright (C) 2014-2015 Andreas Lang-Nevyjel
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

""" reads and modifies local_settings.py, now stored in a config_store"""

import os
import sys

from initat.tools import config_store
from initat.tools.logging_tools import logbase
from django.utils.crypto import get_random_string

LS_OLD_FILE = "/etc/sysconfig/cluster/local_settings.py"
CS_NAME = "icsw.general"


def log(what, log_level=logbase.LOG_LEVEL_OK):
    print(
        "[{}] {}".format(
            logbase.get_log_level_str(log_level),
            what,
        )
    )


# a similar routine exists in setup_cluster.py
def get_old_local_settings():
    LS_DIR = os.path.dirname(LS_OLD_FILE)
    sys.path.append(LS_DIR)
    try:
        from local_settings import SECRET_KEY  # @UnresolvedImports
    except:
        SECRET_KEY = None
    try:
        from local_settings import PASSWORD_HASH_FUNCTION  # @UnresolvedImports
    except:
        PASSWORD_HASH_FUNCTION = "SHA1"
    try:
        from local_settings import GOOGLE_MAPS_KEY  # @UnresolvedImports
    except:
        GOOGLE_MAPS_KEY = ""
    try:
        from local_settings import AUTO_CREATE_NEW_DOMAINS  # @UnresolvedImports
    except:
        AUTO_CREATE_NEW_DOMAINS = True
    try:
        from local_settings import LOGIN_SCREEN_TYPE  # @UnresolvedImports
    except:
        LOGIN_SCREEN_TYPE = "big"
    try:
        from local_settings import PASSWORD_CHARACTER_COUNT
    except:
        PASSWORD_CHARACTER_COUNT = 8
    if SECRET_KEY in [None, "None"]:
        chars = 'abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)'
        SECRET_KEY = get_random_string(50, chars)
    sys.path.remove(LS_DIR)
    return {
        "django.secret.key": SECRET_KEY,
        "password.hash.function": PASSWORD_CHARACTER_COUNT,
        "google.maps.key": GOOGLE_MAPS_KEY,
        "password.character.count": PASSWORD_CHARACTER_COUNT,
        "auto.create.new.domains": AUTO_CREATE_NEW_DOMAINS,
        "login.screen.type": LOGIN_SCREEN_TYPE,
    }


def main():
    if not config_store.ConfigStore.exists(CS_NAME):
        new_store = config_store.ConfigStore(CS_NAME)
        for _key, _value in get_old_local_settings().iteritems():
            new_store[_key] = _value
        new_store.write()

if __name__ == "__main__":
    main()
