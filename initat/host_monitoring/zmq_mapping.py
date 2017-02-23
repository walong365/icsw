# -*- coding: utf-8 -*-
#
# Copyright (C) 2013-2017 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw-server-client
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

""" host-monitoring, with 0MQ and direct socket support, relay part """

import pprint
import sqlite3
import time

from initat.tools import logging_tools

CS_NAME = "hr.0mq-mapping"


SQL_SCHEMA_VERSION = 1
INIT_SQL_SCHEMA_VERSION = 1


class DBCursor(object):
    def __init__(self, conn, cached):
        self.__cached = cached
        self.conn = conn

    def __enter__(self):
        self.cursor = self.conn.cursor()
        return self.cursor

    def __exit__(self, *args):
        self.cursor.close()
        if not self.__cached:
            self.conn.commit()


class MappingDB(object):
    def __init__(self, db_path, log_com):
        self._db_path = db_path
        self._log_com = log_com
        self.log("init SQLite for 0MQ mapping at {}".format(self._db_path))
        self.init_sqlite()

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self._log_com("[MDB] {}".format(what), log_level)

    def init_sqlite(self):
        self.conn = sqlite3.connect(self._db_path)
        self.conn.row_factory = sqlite3.Row
        self.check_schema(self.conn)

    def get_cursor(self, cached=True):
        return DBCursor(self.conn, cached)

    def check_schema(self, conn):
        _descr = conn.execute("PRAGMA table_info(state)").fetchall()
        # schema:
        # device: one entry per device (== unique machine uuid)
        # connection: one or more per device
        # print(_descr)
        _table_dict = {
            "schema_version": [
                "version INTEGER NOT NULL",
            ],
            "device": [
                "idx INTEGER PRIMARY KEY NOT NULL",
                # machine uuid
                "machine_uuid TEXT NOT NULL UNIQUE",
                "created INTEGER NOT NULL",
                "last_update INTEGER default 0",
            ],
            "connection": [
                "idx INTEGER PRIMARY KEY NOT NULL",
                # connection uuid with server part
                "connection_uuid TEXT NOT NULL",
                # updated when the target HM restarts
                "dynamic_uuid TEXT default ''",
                # ip or name
                "address TEXT NOT NULL",
                "port INTEGER NOT NULL default 0",
                # server specifier (empty in most cases)
                "server TEXT NOT NULL default ''",
                # link to device
                "device INTEGER",
                "changed INTEGER default 0",
                "created INTEGER NOT NULL",
                "FOREIGN KEY(device) REFERENCES device(idx)",
            ],
        }
        _index_list = [
            "connection(connection_uuid)",
        ]
        all_tables = {
            _entry[0]: _entry[1] for _entry in conn.execute(
                "SELECT name, sql FROM sqlite_master WHERE type='table';"
            ).fetchall()
        }
        # step one: create missing tables
        for _t_name, _t_struct in _table_dict.items():
            _sql_str = "CREATE TABLE {}({})".format(
                _t_name,
                ", ".join(_t_struct),
            )
            if _t_name not in all_tables:
                self.log("creating table {}: {}".format(_t_name, _sql_str))
                conn.execute("{};".format(_sql_str))

        # step two: check version
        _cur_vers = conn.execute("SELECT * FROM schema_version").fetchall()
        if not len(_cur_vers):
            if not len(all_tables):
                # initial install, schema is up-to date
                conn.execute(
                    "INSERT INTO schema_version(version) VALUES(?)",
                    (SQL_SCHEMA_VERSION,)
                )
            else:
                # some tables were present, must be old version
                conn.execute(
                    "INSERT INTO schema_version(version) VALUES(?)",
                    (INIT_SQL_SCHEMA_VERSION,)
                )

        _cur_vers = conn.execute("SELECT version FROM schema_version").fetchone()[0]
        if _cur_vers != SQL_SCHEMA_VERSION:
            self.log(
                "SQL schema version found ({:d}) differs from current version ({:d})".format(
                    _cur_vers,
                    SQL_SCHEMA_VERSION
                ),
                logging_tools.LOG_LEVEL_WARN
            )
        else:
            self.log(
                "SQL schema version found ({:d}) matches current version".format(
                    SQL_SCHEMA_VERSION
                )
            )
        # indices
        for _index_num, _index in enumerate(_index_list, 1):
            _idx_str = "CREATE INDEX IF NOT EXISTS i{:d} ON {}".format(
                _index_num,
                _index,
            )
            self.log("creating index with '{}'".format(_idx_str))
            conn.execute(_idx_str)

    def clear(self):
        self.log("clearing database")
        return
        with self.get_cursor(cached=False) as cursor:
            cursor.execute("DELETE FROM device")

    def add_mapping(self, address: str, port: int, uuid: str):
        if not uuid.startswith("urn:uuid:"):
            # normalize
            uuid = "urn:uuid:{}".format(uuid)
        _parts = uuid.split(":")
        if len(_parts) == 3:
            server = ""
        else:
            _parts = [_entry for _entry in _parts if _entry.strip()]
            server = _parts.pop(-1)
        with self.get_cursor(cached=False) as cursor:
            _current = list(
                cursor.execute(
                    "SELECT idx FROM uuid WHERE connection_uuid=? AND server=?",
                    (uuid, server)
                )
            )
            if not _current:
                cursor.execute(
                    "INSERT INTO uuid(connection_uuid, server, created) VALUES(?, ?, ?)",
                    (uuid, server, int(time.time())),
                )
                _uuid_idx = cursor.lastrowid
            else:
                _uuid_idx = _current[0][0]
            _found = list(
                cursor.execute(
                    "SELECT idx FROM device WHERE uuid=? AND address=? AND port=?",
                    (_uuid_idx, address, port),
                )
            )
            if not _found:
                cursor.execute(
                    "INSERT INTO device(uuid, address, port, created) VALUES(?, ?, ?, ?)",
                    (_uuid_idx, address, port, int(time.time())),
                )
            # print("add")

    def dump(self):
        with self.get_cursor(cached=False) as cursor:
            for entry in cursor.execute(
                "SELECT *, c.idx AS c_idx, d.idx AS d_idx FROM device d, connection c WHERE d.idx=c.device"
            ):
                _dict = dict(zip(entry.keys(), tuple(entry)))
                # print("*", _dict)

    def update_mapping(self, mapping_obj):
        if mapping_obj.machine_uuid:
            # get old connection id(s), base is the connection string
            print(mapping_obj._conn_str)
            # get device
            with self.get_cursor(cached=False) as cursor:
                _result = cursor.execute(
                    "SELECT idx FROM device WHERE machine_uuid=?",
                    (mapping_obj.machine_uuid,),
                ).fetchone()
                print("-" * 30)
                if _result:
                    dev_idx = _result[0]
                    # found 1 matching entry
                    print("FOUND", dev_idx)
                    print(mapping_obj.connection_uuid)
                else:
                    # nothing found with this machine id, create new one
                    cursor.execute(
                        "INSERT INTO device(machine_uuid, created) VALUES(?, ?)",
                        (mapping_obj.machine_uuid, int(time.time())),
                    )
                    dev_idx = cursor.lastrowid
                    self.log(
                        "creating new device entry with machine_uuid='{}' ({:d})".format(
                            mapping_obj.machine_uuid,
                            dev_idx,
                        )
                    )
                # we now have a valid device idx
                # check for new connection
                conn_results = [
                    dict(_entry) for _entry in cursor.execute(
                        "SELECT * FROM connection WHERE device=?",
                        (dev_idx,),
                    )
                ]
                if not len(conn_results):
                    # create new connection entry
                    cursor.execute(
                        "INSERT INTO connection(device, connection_uuid, dynamic_uuid, address, port, created) VALUES(?, ?, ?, ?, ?, ?)",
                        (
                            dev_idx,
                            mapping_obj.connection_uuid,
                            mapping_obj.dynamic_uuid,
                            mapping_obj.address,
                            mapping_obj.port,
                            int(time.time()),
                        ),
                    )
                    conn_idx = cursor.lastrowid
                    self.log(
                        "created new connection object (uuid='{}', tcp://{}:{:d}, [{:d}])".format(
                            mapping_obj.connection_uuid,
                            mapping_obj.address,
                            mapping_obj.port,
                            conn_idx,
                        )
                    )
                else:
                    # step 1: find match connections
                    mc_list = [
                        entry for entry in conn_results if entry["connection_uuid"] == mapping_obj.connection_uuid
                    ]
                    if mc_list and mapping_obj.dynamic_uuid:
                        if len(mc_list) > 1:
                            self.log(
                                "found more than one matching connection for {}".format(
                                    mc_list[0]["connection_uuid"],
                                ),
                                logging_tools.LOG_LEVEL_ERROR
                            )
                        else:
                            match_con = mc_list[0]
                            if mapping_obj.dynamic_uuid != match_con["dynamic_uuid"]:
                                if not match_con["dynamic_uuid"]:
                                    # update
                                    cursor.execute(
                                        "UPDATE connection SET dynamic_uuid=? WHERE idx=?",
                                        (mapping_obj.dynamic_uuid, match_con["idx"]),
                                    )
                                    self.log(
                                        "set dynamic_uuid to {}".format(
                                            mapping_obj.dynamic_uuid,
                                        )
                                    )
                                else:
                                    # at this point we have connection object with a
                                    # dynamic_uuid different from the one reported by
                                    # the system
                                    # two possibilities:
                                    # - the HM on the target system was restarted
                                    # - we have two HMs running with at least the same
                                    #   connection_uuid
                                    # the only way to distinguish is when the recorded
                                    # stream of dynamic_uuids contains duplicates (reoccuring values)
                                    # update dynamic uuid
                                    self.log(
                                        "updated dynamic_uuid to {}".format(
                                            mapping_obj.dynamic_uuid,
                                        )
                                    )
                                    cursor.execute(
                                        "UPDATE connection SET dynamic_uuid=? WHERE idx=?",
                                        (mapping_obj.dynamic_uuid, match_con["idx"]),
                                    )
                            if mapping_obj.reuse_detected:
                                self.log("reuse detected", logging_tools.LOG_LEVEL_ERROR)
                                # gather reuse statistics
                                info_list = [
                                    "tcp://{}:{:d}".format(
                                        mapping_obj.address,
                                        mapping_obj.port,
                                    )
                                ]
                                print(mapping_obj.address, mapping_obj.port)
                                for entry in cursor.execute(
                                    "SELECT * FROM connection WHERE connection_uuid=?",
                                    (mapping_obj.connection_uuid,)
                                ):
                                    info_list.append("tcp://{}:{:d}".format(entry["address"], entry["port"]))
                                info_list = list(set(info_list))
                                mapping_obj.reuse_info = "{}: {}".format(
                                    logging_tools.get_plural("address", len(info_list)),
                                    ", ".join(sorted(info_list)),
                                )
                                print("g", mapping_obj.reuse_info, id(mapping_obj))
                                # print("RED_CHECK")
                                # print("**", mapping_obj.dynamic_uuid)
                                # pprint.pprint(match_con)

    def get_0mq_addrs(self, port):
        # return all address stored in database
        with self.get_cursor(cached=False) as cursor:
            _result = [
                _result[0] for _result in cursor.execute(
                    "SELECT DISTINCT address FROM connection WHERE port=?",
                    (port,),
                )
            ]
        return _result
