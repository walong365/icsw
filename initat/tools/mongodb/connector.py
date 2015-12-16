# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of logcheck-server
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
""" mongodb connector object """

import pymongo
from pymongo.errors import PyMongoError
import time

from initat.cluster.backbone.models import config_str, config_int
from initat.cluster.backbone.models.functions import memoize_with_expiry


class MongoDbConnector(object):
    def __init__(self):
        self._reconnect()

    def _reconnect(self):
        self.client, self.event_log_db = self.__class__._get_config()
        self._con_time = time.time()
        if self.client is not None:
            self._connected = True
        else:
            self._connected = False

    @property
    def connected(self):
        return self._connected

    def reconnect(self):
        cur_time = time.time()
        if abs(cur_time - self._con_time) > 1:
            self._reconnect()

    @classmethod
    @memoize_with_expiry(10)
    def _get_config(cls):
        return cls._get_config_uncached()

    @classmethod
    def _get_config_uncached(cls):

        mongo_config = {
            'MONGODB_HOST': "localhost",
            'MONGODB_PORT': 27017,
        }

        configs_db = list(
            config_str.objects.filter(
                name="MONGODB_HOST",
                config__name="discovery_server",
            )
        )

        configs_db += list(
            config_int.objects.filter(
                name="MONGODB_PORT",
                config__name="discovery_server",
            )
        )

        for mongo_config_entry in configs_db:
            mongo_config[mongo_config_entry.name] = mongo_config_entry.value

        client = pymongo.MongoClient(
            host=mongo_config['MONGODB_HOST'],
            port=mongo_config['MONGODB_PORT'],
            tz_aware=True,
            serverSelectionTimeoutMS=1000,
            connectTimeoutMS=1000,
        )
        try:
            cls.srv_info = client.server_info()
        except PyMongoError as error:
            cls.srv_info = None
            cls.error = error
            client, event_log_db = (None, None)
        else:
            cls.error = None
            event_log_db = client.icsw_event_log
        return client, event_log_db

    @classmethod
    def json_error_dict(cls):
        if cls.error is not None:
            return {
                "error": "Failed to connect to mongo-db: {}".format(cls.error)
            }
        else:
            return {}
