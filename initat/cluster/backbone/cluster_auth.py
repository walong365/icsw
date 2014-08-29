#!/usr/bin/python-init

import base64
import crypt
import hashlib
import logging

from django.db.models import Q
from initat.cluster.backbone.models import user

logger = logging.getLogger("cluster.auth")


class db_backend(object):
    def authenticate(self, username=None, password=None):
        try:
            cur_user = user.objects.get(Q(login=username))
        except user.DoesNotExist:
            logger.error("user '{}' not found".format(username))
            return None
        else:
            if password is "AUTO_LOGIN" and cur_user.login_count == 0 and sum(user.objects.all().values_list("login_count", flat=True)) == 0:
                return cur_user
            # check password
            cur_pw = cur_user.password
            if cur_pw.count(":"):
                pw_hash, db_password = cur_pw.split(":", 1)
            else:
                pw_hash, db_password = ("", cur_pw)
            if pw_hash in ["SHA1"]:
                new_h = hashlib.new(pw_hash)
                new_h.update(password)
                if base64.b64encode(new_h.digest()) == db_password:
                    # match
                    return cur_user
                else:
                    logger.warn("password mismatch for %s" % (username))
            elif pw_hash in ["CRYPT"]:
                if crypt.crypt(password, db_password) == db_password:
                    return cur_user
                else:
                    logger.warn("password mismatch for %s" % (username))
            else:
                logger.error("unknown password hash '%s' for %s" % (
                    pw_hash,
                    username))
                return None

    def get_user(self, user_id):
        try:
            return user.objects.get(Q(pk=user_id))
        except user.DoesNotExist:
            return None
