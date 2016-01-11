# -*- coding: utf-8 -*-
#
# Copyright (C) 2012-2016 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of mother
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FTNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
""" helper functions for db access / close """

import socket

from django.conf import settings
from django.db import OperationalError

from initat.constants import DB_ACCESS_CS_NAME
from initat.tools import config_store

# connection test timeout
DB_TIMEOUT = 2.0


def is_oracle():
    # return True if database is oracle """
    return True if settings.DATABASES["default"]["ENGINE"].lower().count("oracle") else False


def is_reachable():
    if not config_store.ConfigStore.exists(DB_ACCESS_CS_NAME):
        return False
    from django.db import connections
    _settings = settings.DATABASES["default"]
    if _settings.get("HOST", "").strip() and _settings["HOST"] not in ["localhost", "127.0.0.1"]:
        if _settings["ENGINE"].lower().count("psyco"):
            _port = int(_settings.get("PORT", "5432") or "5432")
            try:
                _c = socket.create_connection((_settings["HOST"], _port), DB_TIMEOUT)
            except:
                return False
            else:
                _c.close()
    conn = connections["default"]
    try:
        c = conn.cursor()
    except:
        return False
    else:
        c.close()
        return True


def close_connection():
    from django.db import connection
    if is_oracle():
        try:
            connection.close()
        except OperationalError:
            pass
    else:
        connection.close()
