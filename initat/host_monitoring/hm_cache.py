# Copyright (C) 2001-2017 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
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
""" cache definitions for host-monitorint commands """

import time


class CacheObject(object):
    def __init__(self, key):
        self.key = key
        self.valid_until = None
        # retrieval pending
        self.retrieval_pending = False
        self.clients = []

    def register_retrieval_client(self, client):
        self.clients.append(client)

    def store_object(self, obj, valid_until):
        self.obj = obj
        self.valid_until = valid_until
        self.retrieval_pending = False
        self._resolve_clients()

    def _resolve_clients(self):
        for _c in self.clients:
            _c.resolve_cache(self.obj)
        self.clients = []

    def is_valid(self):
        if self.valid_until:
            return time.time() < self.valid_until
        else:
            return False


class HMCCache(object):
    def __init__(self, timeout):
        self._timeout = timeout
        self._cache = {}

    def store_object(self, key, obj):
        cur_time = time.time()
        self._cache[key].store_object(obj, cur_time + self._timeout)

    def start_retrieval(self, key):
        self._cache[key].retrieval_pending = True

    def load_object(self, key):
        return self._cache[key].obj

    def cache_valid(self, key):
        if key not in self._cache:
            self._cache[key] = CacheObject(key)
        return self._cache[key].is_valid()

    def retrieval_pending(self, key):
        return self._cache[key].retrieval_pending

    def register_retrieval_client(self, key, client):
        return self._cache[key].register_retrieval_client(client)


class HMCCacheMixin(object):
    class Meta:
        cache_timeout = 10

    def _cache_init(self):
        if not hasattr(self, "_HMC"):
            self._HMC = HMCCache(self.Meta.cache_timeout)

    def start_retrieval(self, key):
        # to flag start of external object generation
        self._cache_init()
        self._HMC.start_retrieval(key)

    def store_object(self, key, obj):
        self._cache_init()
        self._HMC.store_object(key, obj)

    def load_object(self, key):
        return self._HMC.load_object(key)

    def cache_valid(self, key):
        self._cache_init()
        # return True if the given key is in the cache and valid
        return self._HMC.cache_valid(key)

    def retrieval_pending(self, key):
        return self._HMC.retrieval_pending(key)

    def register_retrieval_client(self, key, client):
        return self._HMC.register_retrieval_client(key, client)
