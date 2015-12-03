# -*- coding: utf-8 -*-
#
# Copyright (C) 2012-2015 Andreas Lang-Nevyjel, init.at
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

from django.conf import settings
from django.db import OperationalError


def is_oracle():
    # return True if database is oracle """
    return True if settings.DATABASES["default"]["ENGINE"].lower().count("oracle") else False


class close_connection():
    from django.db import connection
    if is_oracle():
        try:
            connection.close()
        except OperationalError:
            pass
    else:
        connection.close()
