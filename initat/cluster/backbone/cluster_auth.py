# Copyright (C) 2015-2017 Andreas Lang-Nevyjel, init.at
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
authentication backend
"""

import base64
import crypt
import hashlib
import logging

from django.db.models import Q

from initat.cluster.backbone.models import user

logger = logging.getLogger("cluster.auth")


class db_backend(object):
    def authenticate(self, username: str=None, password: str=None):
        try:
            cur_user = user.objects.get(Q(login=username))
        except user.DoesNotExist:
            logger.error("user '{}' not found".format(username))
            return None
        else:
            if password is "AUTO_LOGIN" and cur_user.login_count == 0 and sum(
                user.objects.all().values_list("login_count", flat=True)
            ) == 0:
                return cur_user
            # check password
            cur_pw = cur_user.password
            if cur_pw.count(":"):
                pw_hash, db_password = cur_pw.split(":", 1)
            else:
                pw_hash, db_password = ("", cur_pw)
            if db_password.startswith("b'"):
                # fix for temporary str / byte problems
                db_password = db_password[2:-1]
            if pw_hash in ["SHA1"]:
                new_h = hashlib.new(pw_hash)
                new_h.update(password.encode("ascii"))
                if base64.b64encode(new_h.digest()) == db_password.encode("ascii"):
                    # match
                    return cur_user
                else:
                    logger.warning("password mismatch for '{}'".format(username))
            elif pw_hash in ["CRYPT"]:
                if crypt.crypt(password, db_password) == db_password:
                    return cur_user
                else:
                    logger.warning("password mismatch for '{}'".format(username))
            else:
                logger.error(
                    "unknown password hash '{}' for user '{}'".format(
                        pw_hash,
                        username,
                    )
                )
                return None

    def get_user(self, user_id):
        try:
            return user.objects.get(Q(pk=user_id))
        except user.DoesNotExist:
            return None
