#!/usr/bin/python-init

import base64
import logging
import hashlib

from django.db.models import Q

from initat.cluster.backbone.models import user

logger = logging.getLogger("cluster.auth")

class db_backend(object):
    def authenticate(self, username=None, password=None):
        try:
            cur_user = user.objects.get(Q(login=username))
        except user.DoesNotExist:
            logger.error("user '%s' not found" % (username))
            return None
        else:
            # check password
            cur_pw = cur_user.password
            if cur_pw.startswith("SHA1:"):
                new_h = hashlib.new(cur_pw.split(":")[0])
                new_h.update(password)
                if base64.b64encode(new_h.digest()) == cur_pw.split(":")[1]:
                    # match
                    return cur_user
                else:
                    logger.warn("password mismatch for %s" % (username))
            else:
                logger.error("unknown password hash '%s' for %s" % (
                    cur_pw,
                    username))
                return None
    def get_user(self, user_id):
        try:
            return user.objects.get(Q(pk=user_id))
        except user.DoesNotExist:
            return None
        
