#
# this file is part of collectd-init
#
# Copyright (C) 2013-2014 Andreas Lang-Nevyjel init.at
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

from initat.collectd.collectd_types import value
from initat.collectd.config import global_config
from lxml.builder import E  # @UnresolvedImports
import memcache
import json
import logging_tools
import process_tools
import subprocess
import time

mc = memcache.Client(["{}:{:d}".format(global_config["MEMCACHE_HOST"], global_config["MEMCACHE_PORT"])])


class ext_com(object):
    run_idx = 0

    def __init__(self, log_com, command):
        ext_com.run_idx += 1
        self.idx = ext_com.run_idx
        self.command = command
        self.popen = None
        self.__log_com = log_com

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_com(u"[ec {:d}] {}".format(self.idx, what), log_level)

    def run(self):
        self.start_time = time.time()
        self.popen = subprocess.Popen(self.command, shell=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
        self.log("start with pid %d" % (self.popen.pid))

    def communicate(self):
        if self.popen:
            try:
                return self.popen.communicate()
            except:
                self.log(u"error in communicate: {}".format(process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
                return ("", "")
        else:
            return ("", "")

    def finished(self):
        self.result = self.popen.poll()
        if self.result is not None:
            self.end_time = time.time()
        return self.result

    def terminate(self):
        self.popen.kill()


class host_info(object):
    def __init__(self, log_template, uuid, name):
        self.__log_template = log_template
        self.name = name
        self.uuid = uuid
        self.__dict = {}
        self.last_update = None
        self.updates = 0
        self.stores = 0
        self.store_to_disk = True
        self.log("init host_info for {} ({})".format(name, uuid))
        self.__mc_timeout = global_config["MEMCACHE_TIMEOUT"]

    @staticmethod
    def setup():
        host_info.entries = {}

    @staticmethod
    def host_update(hi):
        cur_time = time.time()
        # delete old entries
        del_keys = [key for key, value in host_info.entries.iteritems() if abs(value[0] - cur_time) > 15 * 60]
        if del_keys:
            for del_key in del_keys:
                del host_info.entries[del_key]
        # set new entry
        host_info.entries[hi.uuid] = (cur_time, hi.name)
        mc.set("cc_hc_list", json.dumps(host_info.entries))

    def mc_key(self):
        return "cc_hc_{}".format(self.uuid)

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(u"[h {}] {}".format(self.name, what), log_level)

    def get_host_info(self):
        return E.host_info(
            name=self.name,
            uuid=self.uuid,
            last_update="{:d}".format(int(self.last_update or 0) or 0),
            keys="{:d}".format(len(self.__dict)),
            # update calls (full info)
            updates="{:d}".format(self.updates),
            # store calls (short info)
            stores="{:d}".format(self.stores),
            store_to_disk="1" if self.store_to_disk else "0",
        )

    def get_key_list(self, key_filter):
        h_info = self.get_host_info()
        for key in sorted(self.__dict.keys()):
            if key_filter.match(key):
                h_info.append(self.__dict[key].get_key_info())
        return h_info

    def update(self, _xml):
        cur_time = time.time()
        old_keys = set(self.__dict.keys())
        for entry in _xml.findall("mve"):
            cur_name = entry.attrib["name"]
            if cur_name not in self.__dict:
                # set new value
                self.__dict[cur_name] = value(cur_name)
            # update value
            self.__dict[cur_name].update(entry, cur_time)
        self._store_json_to_memcached()
        new_keys = set(self.__dict.keys())
        c_keys = old_keys ^ new_keys
        if c_keys:
            self.updates += 1
            del_keys = old_keys - new_keys
            for del_key in del_keys:
                del self.__dict[del_key]
            self.log("{} changed".format(logging_tools.get_plural("key", len(c_keys))), logging_tools.LOG_LEVEL_WARN)
            return True
        else:
            return False

    def update_ov(self, _xml):
        cur_time = time.time()
        for entry in _xml.findall("m"):
            cur_name = entry.attrib["n"]
            if cur_name in self.__dict:
                self.__dict[cur_name].update_ov(entry, cur_time)
        self._store_json_to_memcached()

    def _store_json_to_memcached(self):
        json_vector = [_value.get_json() for _value in self.__dict.itervalues()]
        host_info.host_update(self)
        # set and ignore errors, default timeout is 2 minutes
        mc.set(self.mc_key(), json.dumps(json_vector), self.__mc_timeout)

    def transform(self, key, value, cur_time):
        self.last_update = cur_time
        if key in self.__dict:
            try:
                return (
                    self.__dict[key].sane_name,
                    self.__dict[key].transform(value, cur_time),
                )
            except:
                self.log("error transforming {}: {}".format(key, process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
                return (None, None)
        else:
            # key not known, skip
            return (None, None)

    def get_values(self, _xml, simple):
        self.stores += 1
        if simple:
            tag_name, name_name, value_name = ("m", "n", "v")
        else:
            tag_name, name_name, value_name = ("mve", "name", "value")
        cur_time = time.time()
        values = [self.transform(entry.attrib[name_name], entry.attrib[value_name], cur_time) for entry in _xml.findall(tag_name)]
        return values

    def __unicode__(self):
        return "{} ({})".format(self.name, self.uuid)
