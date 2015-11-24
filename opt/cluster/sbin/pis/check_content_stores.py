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

""" transform local_settings, uuid and db.cf to config_store(s) """

import os
import sys
import stat

from initat.tools import config_store, logging_tools
from initat.constants import GEN_CS_NAME, DB_ACCESS_CS_NAME
from django.utils.crypto import get_random_string

LS_OLD_FILE = "/etc/sysconfig/cluster/local_settings.py"
AUTO_FLAG = "/etc/sysconfig/cluster/db_auto_update"
SATELLITE_FLAG = "/etc/sysconfig/cluster/is_satellite"
SLAVE_FLAG = "/etc/sysconfig/cluster/is_slave"
DB_FILE = "/etc/sysconfig/cluster/db.cf"


def remove_file(f_name):
    if os.path.exists(f_name):
        try:
            os.unlink(f_name)
        except:
            pass


def log(what, log_level=logging_tools.LOG_LEVEL_OK):
    print(
        "[{}] {}".format(
            logging_tools.get_log_level_str(log_level),
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
        chars = "abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)"
        SECRET_KEY = get_random_string(50, chars)
    sys.path.remove(LS_DIR)
    return {
        "django.secret.key": SECRET_KEY,
        "password.hash.function": PASSWORD_HASH_FUNCTION,
        "google.maps.key": GOOGLE_MAPS_KEY,
        "password.character.count": int(PASSWORD_CHARACTER_COUNT),
        "auto.create.new.domains": AUTO_CREATE_NEW_DOMAINS,
        "login.screen.type": LOGIN_SCREEN_TYPE,
    }


def migrate_uuid():
    from initat.tools import uuid_tools
    uuid_tools.get_uuid()


def migrate_db_cf():
    if not config_store.ConfigStore.exists(DB_ACCESS_CS_NAME) and os.path.exists(DB_FILE):
        _src_stat = os.stat(DB_FILE)
        _cs = config_store.ConfigStore(DB_ACCESS_CS_NAME)
        sql_dict = {
            key.split("_")[1]: value for key, value in [
                line.strip().split("=", 1) for line in file(DB_FILE, "r").read().split(
                    "\n"
                ) if line.count("=") and line.count("_") and not line.count("NAGIOS")
            ]
        }
        for src_key in [
            "DATABASE", "USER", "PASSWD", "HOST", "ENGINE", "PORT",
        ]:
            if src_key in sql_dict:
                _val = sql_dict[src_key]
                if _val.isdigit():
                    _val = int(_val)
                _cs["db.{}".format(src_key.lower())] = _val
        _cs.set_type("db.passwd", "password")
        _cs.write()
        # copy modes
        os.chown(_cs.file_name, _src_stat[stat.ST_UID], _src_stat[stat.ST_GID])
        os.chmod(_cs.file_name, _src_stat[stat.ST_MODE])
        # delete old file
        remove_file(DB_FILE)


def main():
    if not config_store.ConfigStore.exists(GEN_CS_NAME):
        # migrate
        new_store = config_store.ConfigStore(GEN_CS_NAME)
        for _key, _value in get_old_local_settings().iteritems():
            new_store[_key] = _value
        new_store.write()
    new_store = config_store.ConfigStore(GEN_CS_NAME)
    if "db.auto.update" not in new_store:
        if os.path.exists(AUTO_FLAG):
            new_store["db.auto.update"] = True
            remove_file(AUTO_FLAG)
        else:
            new_store["db.auto.update"] = False
    if "mode.is.satellite" not in new_store:
        if os.path.exists(SATELLITE_FLAG):
            new_store["mode.is.satellite"] = True
            remove_file(SATELLITE_FLAG)
        else:
            new_store["mode.is.satellite"] = False
    if "mode.is.slave" not in new_store:
        if os.path.exists(SLAVE_FLAG):
            new_store["mode.is.slave"] = True
            remove_file(SLAVE_FLAG)
        else:
            new_store["mode.is.slave"] = False
    if "create.default.network" not in new_store:
        new_store["create.default.network"] = True
    if "create.network.device.types" not in new_store:
        new_store["create.network.device.types"] = True
    new_store.write()
    remove_file(LS_OLD_FILE)
    migrate_uuid()
    migrate_db_cf()


if __name__ == "__main__":
    main()
