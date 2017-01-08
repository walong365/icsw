# -*- coding: utf-8 -*-
#
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
""" monitors postgres performance values """

import os
import time
import pprint

from initat.host_monitoring import limits, hm_classes

from initat.tools import logging_tools, process_tools, config_store

try:
    import psycopg2
except:
    psycopg2 = None

DEFAULTS = {
    "host": "localhost",
    "port": 5432,
    "user": "postgres",
    "password": "",
    "database": "template1"
}

CS_NAME = "icsw.hm.postgresql"
# Key used in srv_com dictionary like objects
KEY = "postgres"


class PGOverview(object):
    def __init__(self, mv):
        self.top_key = "db.{}.{}".format(KEY, "overview")
        self._keys = set()
        self._init_keys(mv)

    def _key(self, key):
        _key = "{}.{}".format(self.top_key, key)
        if _key not in self._keys:
            self._keys.add(_key)
        return _key

    def _init_keys(self, mv):
        mv.register_entry(self._key("connections.total"), 0, "number of configured connections")
        mv.register_entry(self._key("connections.used"), 0, "number of used connections")

    def feed(self, pg_settings, activity, mv):
        mv[self._key("connections.used")] = sum([len(_val) for _val in activity.itervalues()])
        mv[self._key("connections.total")] = int(pg_settings["max_connections"]["setting"])
        # pprint.pprint({_key: _value["setting"] for _key, _value in pg_settings.iteritems()})


class PGStat(object):
    def __init__(self, name, mv):
        self.name = name
        self.connections = 0
        self.top_key = "db.{}.{}".format(KEY, self.name)
        self._keys = set()
        self._init_keys(mv)
        self.last_ts = None

    def _key(self, key):
        _key = "{}.{}".format(self.top_key, key)
        if _key not in self._keys:
            self._keys.add(_key)
        return _key

    def _init_keys(self, mv):
        mv.register_entry(self._key("backends"), 0, "number of backends for $3")
        mv.register_entry(self._key("connections"), 0, "number of connections for $3")
        mv.register_entry(self._key("xact_commit"), 0., "number of transactions committed in $3", "1/s"),
        mv.register_entry(self._key("xact_rollback"), 0., "number of transactions rolled back in $3", "1/s"),
        mv.register_entry(self._key("blks_read"), 0., "number of blocks read in $3", "1/s"),
        mv.register_entry(self._key("blks_hit"), 0., "number of blocks found in buffer in $3", "1/s"),
        mv.register_entry(self._key("tup_returned"), 0., "number of rows returned by queries in $3", "1/s"),
        mv.register_entry(self._key("tup_fetched"), 0., "number of rows fetched by queries in $3", "1/s"),
        mv.register_entry(self._key("tup_inserted"), 0., "number of rows inserted by queries in $3", "1/s"),
        mv.register_entry(self._key("tup_updated"), 0., "number of rows updated by queries in $3", "1/s"),
        mv.register_entry(self._key("tup_deleted"), 0., "number of rows deleted by queries in $3", "1/s"),
        mv.register_entry(self._key("blk_read_time"), 0., "time spent reading data in $3", "s"),
        mv.register_entry(self._key("blk_write_time"), 0., "time spent writing data in $3", "s"),

    def feed(self, line, mv):
        cur_time = time.time()
        if self.last_ts:
            diff_time = max(1, abs(cur_time - self.last_ts))
            mv[self._key("backends")] = line["numbackends"]
            for key in [
                "xact_commit", "xact_rollback", "blks_read", "blks_hit",
                "tup_returned", "tup_fetched", "tup_inserted", "tup_updated", "tup_deleted"
            ]:
                if key in line and key in self.last_line:
                    mv[self._key(key)] = (line[key] - self.last_line[key]) / diff_time
            for key in ["blk_read_time", "blk_write_time"]:
                if key in line and key in self.last_line:
                    mv[self._key(key)] = (line[key] - self.last_line[key]) / (1000. * diff_time)
            mv[self._key("connections")] = self.connections
        self.last_ts = cur_time
        self.last_line = line

    def remove(self, mv):
        for key in self._keys:
            mv.unregister_entry(key)


class _general(hm_classes.hm_module):
    def init_module(self):
        self.activity = None
        self.pg_settings = None
        self.enabled = True
        if psycopg2:
            self.read_config()
        else:
            self.log("disabled postgres monitoring because no psycopg2 module available", logging_tools.LOG_LEVEL_ERROR)
            self.enabled = False
        # pprint.pprint(self.query("SELECT * FROM pg_stat_activity;"))

    def read_config(self):
        sample_name = "{}_sample".format(CS_NAME)
        if not config_store.ConfigStore.exists(
            sample_name,
        ):
            self.log("Creating sample config store")
            sample_cs = config_store.ConfigStore(sample_name, log_com=self.log, read=False, access_mode=config_store.AccessModeEnum.LOCAL, fix_access_mode=True)
            for _key, _value in DEFAULTS.iteritems():
                sample_cs[_key] = _value
            sample_cs.write()
        if config_store.ConfigStore.exists(CS_NAME):
            try:
                self.config = config_store.ConfigStore(CS_NAME, log_com=self.log, access_mode=config_store.AccessModeEnum.LOCAL, fix_access_mode=True)
            except:
                self.log(
                    "disabled postgres machvector-feed because error parsing config store {}: {}".format(
                        CS_NAME,
                        process_tools.get_except_info(),
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
                self.config = None
        else:
            self.log(
                "disabled postgres machvector-feed because no config-store {} found".format(
                    CS_NAME,
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
            self.config = None

    def _get_config(self):
        _config = self.config.get_dict()
        if not _config["host"]:
            del _config["host"]
        return _config

    def query(self, sql):
        try:
            cursor = psycopg2.connect(**self._get_config()).cursor()
        except:
            self.log(
                "cannot connect to database: {}".format(
                    process_tools.get_except_info()
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
            _res = None
        else:
            try:
                cursor.execute(sql)
            except:
                self.log(
                    "cannot execute query '{}': {}".format(
                        sql,
                        process_tools.get_except_info()
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
                _res = None
            else:
                headers = [_entry.name for _entry in cursor.description]
                _res = [
                    {key: value for key, value in zip(headers, row)} for row in cursor.fetchall()
                ]
            cursor.close()
        return _res

    def init_machine_vector(self, mv):
        self.databases = {}
        self.overview = PGOverview(mv)

    def update_machine_vector(self, mv):
        if not self.enabled or not self.config:
            return
        activity = {}
        _activity_res = self.query("SELECT * FROM pg_stat_activity;")
        if _activity_res is not None:
            for _entry in _activity_res:
                activity.setdefault(_entry["datname"], []).append(_entry)
        # for monitoring command
        self.activity = activity
        res = self.query("SELECT * FROM pg_stat_database;")
        if res is not None:
            touched = set()
            for line in res:
                db_name = line["datname"]
                if db_name not in self.databases:
                    self.log("adding mv for database {}".format(db_name))
                    self.databases[db_name] = PGStat(db_name, mv)
                self.databases[db_name].connections = len(activity.get(db_name, []))
                self.databases[db_name].feed(line, mv)
                touched.add(db_name)
            to_remove = set(self.databases.keys()) - touched
            for rem_db in to_remove:
                self.log("remove mv for database {}".format(rem_db))
                self.databases[rem_db].remove(mv)
                del self.databases[rem_db]
        _settings = self.query("SELECT * FROM pg_settings;")
        if _settings is not None:
            self.pg_settings = {_entry["name"]: _entry for _entry in _settings}
            self.overview.feed(
                self.pg_settings,
                activity,
                mv
            )
        else:
            self.pg_settings = {}


class postgresql_connection_info_command(hm_classes.hm_command):
    def __call__(self, srv_com, cur_ns):
        if self.module.pg_settings:
            srv_com["max_connections"] = int(self.module.pg_settings["max_connections"]["setting"])
            srv_com["used_connections"] = sum([len(_val) for _val in self.module.activity.itervalues()])

    def interpret(self, srv_com, cur_ns):
        if "max_connections" in srv_com:
            _max, _used = (
                int(srv_com["*max_connections"]),
                int(srv_com["*used_connections"]),
            )
            _perc = _used * 100. / max(1, _max)
            if _perc > 85:
                _state = limits.mon_STATE_CRITICAL
            elif _perc > 75:
                _state = limits.mon_STATE_WARNING
            else:
                _state = limits.mon_STATE_OK
            return _state, "connection info: {:d} of {:d} used ({:.2f} %)".format(
                _used,
                _max,
                _perc,
            )
        else:
            return limits.mon_STATE_CRITICAL, "no connection info found"
