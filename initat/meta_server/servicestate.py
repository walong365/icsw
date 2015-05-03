#!/usr/bin/python-init -Otu
# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw-client
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

""" meta-server, config """

import os
import sqlite3
import time

from initat.meta_server.config import global_config
from initat.tools import logging_tools
from initat.icsw.service import constants


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


STATE_DICT = {
    (constants.SERVICE_OK, 0): "pids missing",
    (constants.SERVICE_OK, 1): "OK",
    (constants.SERVICE_DEAD, 0): "not running",
    (constants.SERVICE_DEAD, 1): "nearly running",
    (constants.SERVICE_NOT_INSTALLED, 0): "not installed",
    (constants.SERVICE_NOT_INSTALLED, 1): "strange",
    (constants.SERVICE_NOT_CONFIGURED, 0): "not configured",
    # ??? FIXME
    (constants.SERVICE_NOT_CONFIGURED, 1): "unlicensend",
}


class ServiceState(object):
    def __init__(self, log_com):
        self.__log_com = log_com
        self.log("init")
        self._path = global_config["STATE_DIR"]
        if not os.path.isdir(self._path):
            os.mkdir(self._path)
        os.chmod(self._path, 0700)
        self._db_path = os.path.join(self._path, "servicestate.sqlite")
        self.init_db()
        self.init_states()

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_com("[SrvState] {}".format(what), log_level)

    def init_db(self):
        self.conn = sqlite3.connect(self._db_path)
        self.check_schema(self.conn)

    def check_schema(self, conn):
        _table_dict = {
            "service": [
                "idx INTEGER PRIMARY KEY NOT NULL",
                "name TEXT NOT NULL UNIQUE",
                "target_state INTEGER DEFAULT 1",
                # active for services now in use (in instance_xml)
                "active INTEGER DEFAULT 1",
                "created INTEGER NOT NULL",
            ],
            "state": [
                "idx INTEGER PRIMARY KEY NOT NULL",
                "service INTEGER",
                # running (any pids found)
                "running INTEGER DEFAULT 0",
                # state, defaults to 1 (==SERVICE_DEAD)
                "state INTEGER DEFAULT 1",
                # process info str
                "proc_info_str TEXT DEFAULT ''",
                # creation time
                "created INTEGER NOT NULL",
                "FOREIGN KEY(service) REFERENCES service(idx)",
            ],
            "action": [
                "idx INTEGER PRIMARY KEY NOT NULL",
                "service INTEGER",
                # action (stop, start, restart)
                "action TEXT NOT NULL",
                # success of operation (0 ... no success, 1 ... success)
                "success INTEGER DEFAULT 0",
                # runtime in seconds
                "runtime REAL DEFAULT 0.0",
                # creation time
                "created INTEGER NOT NULL",
                "FOREIGN KEY(service) REFERENCES service(idx)",
            ]
        }
        all_tables = {_entry[0]: _entry[1] for _entry in conn.execute("SELECT name, sql FROM sqlite_master WHERE type='table';").fetchall()}
        for _t_name, _t_struct in _table_dict.iteritems():
            _sql_str = "CREATE TABLE {}({})".format(
                _t_name,
                ", ".join(_t_struct),
            )
            if _t_name in all_tables:
                if _sql_str != all_tables[_t_name]:
                    self.log("SQL creation statements differ, recreating table '{}'".format(_t_name), logging_tools.LOG_LEVEL_WARN)
                    self.log("  before: {}".format(all_tables[_t_name]))
                    self.log("   after: {}".format(_sql_str))
                    conn.execute("DROP TABLE {};".format(_t_name))
                    del all_tables[_t_name]
            if _t_name not in all_tables:
                self.log("creating table {}: {}".format(_t_name, _sql_str))
                conn.execute("{};".format(_sql_str))
        conn.commit()

    def get_cursor(self, cached=True):
        return DBCursor(self.conn, cached)

    def sync_with_instance(self, inst_xml):
        with self.get_cursor() as cursor:
            _current_names = [_entry[0] for _entry in cursor.execute("SELECT name FROM service").fetchall()]
            _new_names = inst_xml.tree.xpath(".//instance[@startstop='1']/@name", smart_strings=False)
            new_services = set(_new_names) - set(_current_names)
            old_services = set(_current_names) - set(_new_names)
            found_services = set(_new_names) & set(_current_names)
            self.log("{} already in database".format(logging_tools.get_plural("service", len(found_services))))
            for found_service in found_services:
                cursor.execute("UPDATE service SET active=? WHERE name=?", (1, found_service,))
            for old_service in old_services:
                self.log("disabling service {}".format(old_service))
                cursor.execute("UPDATE service SET active=? WHERE name=?", (0, old_service, ))
            for new_service in new_services:
                self.log("adding new service {}".format(new_service))
                cursor.execute(
                    "INSERT INTO service(name, target_state, active, created) VALUES(?, ?, ?, ?)",
                    (new_service, 1, 1, int(time.time())),
                )
            self.__service_lut = {_entry[1]: _entry[0] for _entry in cursor.execute("SELECT idx, name FROM service")}

    def init_states(self):
        # init state cache
        # instance name -> (running, ok) tuple
        with self.get_cursor() as cursor:
            # current state cache
            self.__state_dict = {}
            # target state
            self.__target_dict = {_entry[0]: _entry[1] for _entry in cursor.execute("SELECT name, target_state FROM service")}
            # transition lock dict
            self.__transition_lock_dict = {}

    def _update_state(self, name, state, running, proc_info_str):
        _save = False
        if (state, running) != self.__state_dict.get(name, None):
            self.log(
                "state for {} is {}".format(
                    name,
                    STATE_DICT[(state, running)],
                )
            )
            self.__state_dict[name] = (state, running)
            with self.get_cursor() as crs:
                crs.execute(
                    "INSERT INTO state(service, running, state, proc_info_str, created) VALUES(?, ?, ?, ?, ?)",
                    (self.__service_lut[name], running, state, proc_info_str, int(time.time())),
                )
        # check if the current state is in sync with the targetstate
        is_ok = (self.__target_dict[name], self.__state_dict[name]) in [
            (0, (constants.SERVICE_DEAD, 0)), (1, (constants.SERVICE_OK, 1)),
        ]
        return is_ok

    def _check_for_stable_state(self, name):
        C_TIME = 60 * 1
        # check database for state records
        cur_time = int(time.time())
        with self.get_cursor() as crs:
            _records = crs.execute(
                "SELECT running, state, ?-created FROM state WHERE service=? ORDER BY -created LIMIT 10",
                (cur_time, self.__service_lut[name]),
            ).fetchall()
            _stable = True
            # print _records
            _first = _records.pop(0)
            _stable_time = _first[2]
            for _rec in _records:
                if _rec[2] < C_TIME:
                    # only compare records which are not older than C_TIME
                    if _rec[0:2] != _first[0:2]:
                        _stable = False
                        break
                    else:
                        _stable_time = _rec[2]
        if not _stable:
            self.log(
                "state for service {} is not stable ({} < {})".format(
                    name,
                    logging_tools.get_diff_time_str(_stable_time),
                    logging_tools.get_diff_time_str(C_TIME),
                ),
                logging_tools.LOG_LEVEL_WARN
            )
        return _stable

    def _generate_transition(self, name):
        cur_time = time.time()
        LOCK_TIMEOUT = 30
        if name in self.__transition_lock_dict and self.__transition_lock_dict[name] + LOCK_TIMEOUT > cur_time:
            lock_to = abs(cur_time - self.__transition_lock_dict[name])
            self.log(
                "transition lock still valid for {} ({:.2f} > {:.2f})".format(
                    name,
                    lock_to,
                    LOCK_TIMEOUT,
                ),
                logging_tools.LOG_LEVEL_WARN
            )
            return []
        else:
            self.__transition_lock_dict[name] = cur_time
            _action = {0: "stop", 1: "restart"}[self.__target_dict[name]]
            with self.get_cursor() as crs:
                crs.execute(
                    "INSERT INTO action(service, action, created) VALUES(?, ?, ?)",
                    (self.__service_lut[name], _action, int(time.time())),
                )
                trans_id = crs.lastrowid
            return [
                (
                    name,
                    _action,
                    trans_id,
                )
            ]

    def transition_finished(self, trans):
        id = trans.id
        self.log("transition {:d} finished".format(id))
        with self.get_cursor(cached=False) as crs:
            crs.execute(
                "UPDATE action SET runtime=? WHERE idx=?",
                (abs(time.time() - trans.init_time), id),
            )

    def update(self, res_list):
        # return a transition list
        t_list = []
        for _el in res_list:
            if int(_el.entry.attrib["startstop"]):
                # ignore entries without startstop == 1
                _res = _el.entry.find(".//result")
                if _res is not None:
                    # print etree.tostring(_el.entry, pretty_print=True)
                    _state = int(_res.find("state_info").attrib["state"])
                    _pids = _res.findall(".//pid")
                    _proc_info_str = _res.find("state_info").get("proc_info_str", "")
                    _running = 1 if len(_pids) else 0
                    _is_ok = self._update_state(_el.name, _state, _running, _proc_info_str)
                    if not _is_ok:
                        _stable = self._check_for_stable_state(_el.name)
                        _el.log(
                            "not OK ({}, state {} [{}], {}, {})".format(
                                "should run" if self.__target_dict[_el.name] else "should not run",
                                STATE_DICT[(_state, _running)],
                                "stable" if _stable else "not stable",
                                logging_tools.get_plural("pid", len(_pids)),
                                _proc_info_str or '---',
                            ),
                            logging_tools.LOG_LEVEL_WARN
                        )
                        if _stable:
                            t_list.extend(self._generate_transition(_el.name))
                    # if _state or True:
                    #    print "*", _el.name, _state, len(_pids)
                else:
                    _el.log("no result entry found", logging_tools.LOG_LEVEL_WARN)
        self.conn.commit()
        return t_list
        # print _res, etree.tostring(_el.entry, pretty_print=True)
