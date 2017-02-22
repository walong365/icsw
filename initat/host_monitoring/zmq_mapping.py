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
        # print(_descr)
        _table_dict = {
            "schema_version": [
                "version INTEGER NOT NULL",
            ],
            "uuid": [
                "idx INTEGER PRIMARY KEY NOT NULL",
                # connection uuid with server part
                "connection_uuid TEXT NOT NULL UNIQUE",
                "machine_uuid TEXT default ''",
                "dynamic_uuid TEXT default ''",
                "server TEXT NOT NULL default ''",
                "changed INTEGER default 0",
                "created INTEGER NOT NULL",
            ],
            "device": [
                "idx INTEGER PRIMARY KEY NOT NULL",
                "uuid INTEGER",
                "ip TEXT NOT NULL",
                "port INTEGER NOT NULL default 0",
                "created INTEGER NOT NULL",
                "last_update INTEGER default 0",
                "FOREIGN KEY(uuid) REFERENCES uuid(idx)",
            ],
        }
        _index_list = [
            "uuid(connection_uuid)",
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
        with self.get_cursor(cached=False) as cursor:
            cursor.execute("DELETE FROM uuid")

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
                    "SELECT idx FROM device WHERE uuid=? AND ip=? AND port=?",
                    (_uuid_idx, address, port),
                )
            )
            if not _found:
                cursor.execute(
                    "INSERT INTO device(uuid, ip, port, created) VALUES(?, ?, ?, ?)",
                    (_uuid_idx, address, port, int(time.time())),
                )
            # print("add")

    def dump(self):
        with self.get_cursor(cached=False) as cursor:
            for entry in cursor.execute(
                "SELECT *, u.idx AS u_idx, d.idx AS d_idx FROM device d, uuid u WHERE d.uuid=u.idx"
            ):
                _dict = dict(zip(entry.keys(), tuple(entry)))
                print("*", _dict)

    def update_mapping(self, mapping_obj):
        if mapping_obj._changes:
            # get old connection id(s), base is the connection string
            print(mapping_obj._conn_str)
            # get device
            with self.get_cursor(cached=False) as cursor:
                _result = []
                for entry in cursor.execute(
                        "SELECT *, u.idx AS u_idx, d.idx AS d_idx FROM device d, uuid u WHERE d.uuid=u.idx AND d.ip=? AND d.port=?",
                        (mapping_obj.address, mapping_obj.port),
                ):
                    _dict = dict(zip(entry.keys(), tuple(entry)))
                    _result.append(_dict)
                if len(_result) == 1:
                    # found 1 matching entry
                    _dict = _result[0]
                    pprint.pprint(_dict)
                    print(mapping_obj.connection_uuid)
                else:
                    self.log(
                        "found more than one matching entry, refusing update",
                        logging_tools.LOG_LEVEL_ERROR
                    )
                    for _entry in _result:
                        self.log(
                            "    {}".format(str(_entry))
                        )

    def get_0mq_addrs(self, port):
        # return all address stored in database
        with self.get_cursor(cached=False) as cursor:
            _result = [
                _result[0] for _result in cursor.execute(
                    "SELECT DISTINCT ip FROM device WHERE port=?",
                    (port,),
                )
            ]
        return _result
