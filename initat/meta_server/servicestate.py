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
from initat.tools import logging_tools, server_command
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


SERVICE_OK_DICT = {
    constants.TARGET_STATE_RUNNING: {
        constants.SERVICE_OK: (
            constants.LIC_STATE_VALID,
            constants.LIC_STATE_NOT_NEEDED,
            constants.LIC_STATE_GRACE,
        ),
        constants.SERVICE_DEAD: (
            constants.LIC_STATE_VIOLATED,
            constants.LIC_STATE_EXPIRED,
            constants.LIC_STATE_VALID_IN_FUTURE,
            constants.LIC_STATE_NONE,
        ),
        constants.SERVICE_INCOMPLETE: (),
        constants.SERVICE_NOT_INSTALLED: (),
        constants.SERVICE_NOT_CONFIGURED: None,
    },
    constants.TARGET_STATE_STOPPED: {
        constants.SERVICE_OK: (),
        constants.SERVICE_DEAD: None,
        constants.SERVICE_INCOMPLETE: (),
        constants.SERVICE_NOT_INSTALLED: None,
        constants.SERVICE_NOT_CONFIGURED: None,
    }
}


class ServiceStateTranstaction(object):
    def __init__(self, name, action, trans_id):
        self.name = name
        self.action = action
        self.trans_id = trans_id


class ServiceState(object):
    def __init__(self, log_com):
        self.__log_com = log_com
        self.log("init")
        self._path = global_config["STATE_DIR"]
        if not os.path.isdir(self._path):
            os.mkdir(self._path)
        os.chmod(self._path, 0700)
        self._db_path = os.path.join(self._path, "servicestate.sqlite")
        self._init_states()
        self.init_db()
        self.__shutdown = False

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_com("[SrvState] {}".format(what), log_level)

    def init_db(self):
        self.conn = sqlite3.connect(self._db_path)
        self.check_schema(self.conn)

    def enable_shutdown_mode(self):
        self.log("enable shutdown mode")
        self.__shutdown = True
        for _key in self.__target_dict.iterkeys():
            self.__target_dict[_key] = constants.TARGET_STATE_STOPPED

    def check_schema(self, conn):
        _table_dict = {
            "service": [
                "idx INTEGER PRIMARY KEY NOT NULL",
                "name TEXT NOT NULL UNIQUE",
                "target_state INTEGER DEFAULT {:d}".format(constants.TARGET_STATE_RUNNING),
                # active for services now in use (in instance_xml)
                "active INTEGER DEFAULT 1",
                "created INTEGER NOT NULL",
            ],
            "state": [
                "idx INTEGER PRIMARY KEY NOT NULL",
                "service INTEGER",
                # state, defaults to (==SERVICE_DEAD)
                "state INTEGER DEFAULT {:d}".format(constants.SERVICE_DEAD),
                # state, defaults to -1 (==NOT_NEEDED)
                "license_state INTEGER DEFAULT -1",
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
                # finished
                "finished INTEGER DEFAULT 0",
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
        with self.get_cursor(cached=False) as cursor:
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
                    (new_service, self._get_default_state(new_service), 1, int(time.time())),
                )
            self.__service_lut = {
                _entry[1]: _entry[0] for _entry in cursor.execute("SELECT idx, name FROM service")
            }
            # update states
            self.__target_dict = {
                _entry[0]: _entry[1] for _entry in cursor.execute("SELECT name, target_state FROM service")
            }

    def _get_default_state(self, srv_name):
        if srv_name == "package-client":
            if os.path.exists("/etc/packageserver") or os.path.exists("/etc/packageserver_id"):
                _ts = constants.TARGET_STATE_RUNNING
            else:
                _ts = constants.TARGET_STATE_STOPPED
        else:
            _ts = constants.TARGET_STATE_RUNNING
        return _ts

    def _init_states(self):
        # init state cache
        # instance name -> (running, ok) tuple
        # current state cache
        self.__state_dict = {}
        # target state
        self.__target_dict = {}
        # transition lock dict
        self.__transition_lock_dict = {}

    def _update_target_dict(self):
        _changed = False
        with self.get_cursor(cached=False) as crsr:
            for _name, _target_state in crsr.execute("SELECT name, target_state FROM service"):
                if _name in self.__target_dict:
                    if self.__target_dict[_name] != _target_state:
                        self.__target_dict[_name] = _target_state
                        _changed = True
        return _changed

    def _update_state(self, name, state, lic_state, proc_info_str):
        _save = False
        if (state, lic_state) != self.__state_dict.get(name, None):
            self.log(
                "state for {} is {} (license: {})".format(
                    name,
                    constants.STATE_DICT[state],
                    constants.LIC_STATE_DICT[lic_state],
                )
            )
            self.__state_dict[name] = (state, lic_state)
            with self.get_cursor() as crs:
                crs.execute(
                    "INSERT INTO state(service, license_state, state, proc_info_str, created) VALUES(?, ?, ?, ?, ?)",
                    (self.__service_lut[name], lic_state, state, proc_info_str, int(time.time())),
                )
        # check if the current state is in sync with the targetstate
        _ct = (self.__target_dict[name], self.__state_dict[name][0], self.__state_dict[name][1])
        return self._check_current_state(_ct)

    def _check_current_state(self, ct):
        _stuff = SERVICE_OK_DICT[ct[0]][ct[1]]
        if _stuff is None or ct[2] in _stuff:
            return True
        else:
            return False

    def _check_for_stable_state(self, service):
        name = service.name
        # interval for which the state has be stable
        STABLE_INTERVAL = 60 * 1
        # how old the latest state entry must be at least
        MIN_STATE_TIME = 20
        # check database for state records
        cur_time = int(time.time())
        with self.get_cursor() as crs:
            _records = crs.execute(
                "SELECT state, license_state, ?-created FROM state WHERE service=? ORDER BY -created LIMIT 10",
                (cur_time, self.__service_lut[name]),
            ).fetchall()
            _stable = True
            # correct times
            _records = [(_a, _b, abs(_c)) for _a, _b, _c in _records]
            # print _records
            _first = _records.pop(0)
            _stable_time = _first[2]
            for _rec in _records:
                if _rec[2] < STABLE_INTERVAL:
                    # only compare records which are not older than STABLE_INTERVAL
                    if _rec[0:2] != _first[0:2]:
                        _stable = False
                        break
                    else:
                        _stable_time = _rec[2]
        if not _stable:
            service.log(
                "state is not stable ({} < {})".format(
                    logging_tools.get_diff_time_str(_stable_time),
                    logging_tools.get_diff_time_str(STABLE_INTERVAL),
                ),
                logging_tools.LOG_LEVEL_WARN
            )
        else:
            # compare record for SERVICE_OK_LIST
            c_rec = (self.__target_dict[name], _first[0], _first[1])
            # print _first, c_rec
            if not self._check_current_state(c_rec) and _first[2] < MIN_STATE_TIME:
                service.log("state is not OK", logging_tools.LOG_LEVEL_WARN)
                _stable = False
            elif _first[2] < MIN_STATE_TIME:
                service.log("state not old enough ({:.2f} < {:.2f})".format(_first[2], MIN_STATE_TIME), logging_tools.LOG_LEVEL_WARN)
                _stable = False
        return _stable

    def _generate_transition(self, service):
        name = service.name
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
            _action = {0: "stop", 1: "start"}[self.__target_dict[name]]
            _res_node = service.entry.find(".//result")
            if _res_node is not None:
                _state = int(_res_node.find("state_info").attrib["state"])
                _lic_state = int(_res_node.find("license_info").attrib["state"])
                if _state in [constants.SERVICE_NOT_CONFIGURED, constants.SERVICE_NOT_INSTALLED]:
                    _action = "stop"
                elif _lic_state in [constants.LIC_STATE_VIOLATED, constants.LIC_STATE_EXPIRED, constants.LIC_STATE_VALID_IN_FUTURE, constants.LIC_STATE_NONE]:
                    _action = "stop"
            with self.get_cursor() as crs:
                crs.execute(
                    "INSERT INTO action(service, action, created) VALUES(?, ?, ?)",
                    (
                        self.__service_lut[name], _action, int(time.time())
                    ),
                )
                trans_id = crs.lastrowid
                self.__transition_lock_dict[name] = cur_time
            return [
                ServiceStateTranstaction(
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
                "UPDATE action SET runtime=?, finished=1 WHERE idx=?",
                (
                    abs(time.time() - trans.init_time), id
                ),
            )
            # get service
            name = crs.execute(
                "SELECT s.name FROM service s, action a WHERE a.service=s.idx AND a.idx=?",
                (id,),
            ).fetchone()[0]
            if name in self.__transition_lock_dict:
                del self.__transition_lock_dict[name]

    def update(self, res_list, **kwargs):
        # services to exclude from transition
        exclude = kwargs.get("exclude", [])
        # force mode (for first call or command-line induced)
        force = kwargs.get("force", False)
        # return a transition list
        t_list = []
        for _el in res_list:
            if int(_el.entry.attrib["startstop"]):
                # ignore entries without startstop == 1
                _res = _el.entry.find(".//result")
                if _res is not None:
                    # print etree.tostring(_el.entry, pretty_print=True)
                    _state = int(_res.find("state_info").attrib["state"])
                    _lic_state = int(_res.find("license_info").attrib["state"])
                    _proc_info_str = _res.find("state_info").get("proc_info_str", "")
                    _is_ok = self._update_state(_el.name, _state, _lic_state, _proc_info_str)
                    if not _is_ok:
                        if self.__shutdown:
                            if _el.name not in exclude:
                                t_list.extend(self._generate_transition(_el))
                        else:
                            _stable = self._check_for_stable_state(_el)
                            _el.log(
                                "not OK ({}, state {} / {} [{}], {}, {})".format(
                                    "should run" if self.__target_dict[_el.name] else "should not run",
                                    constants.STATE_DICT[_state],
                                    constants.LIC_STATE_DICT[_lic_state],
                                    "stable" if _stable else "not stable",
                                    logging_tools.get_plural("pid", len(_res.findall(".//pid"))),
                                    _proc_info_str or '---',
                                ),
                                logging_tools.LOG_LEVEL_WARN
                            )
                            if _stable or force:
                                if _el.name not in exclude:
                                    t_list.extend(self._generate_transition(_el))
                    # if _state or True:
                    #    print "*", _el.name, _state, len(_pids)
                else:
                    _el.log("no result entry found", logging_tools.LOG_LEVEL_WARN)
        self.conn.commit()
        return t_list
        # print _res, etree.tostring(_el.entry, pretty_print=True)

    def get_mail_text(self, trans_list):
        subject = "ICSW Transaction info for {}: {}".format(
            logging_tools.get_plural("transaction", len(trans_list)),
            ", ".join(sorted([_trans.name for _trans in trans_list])),
        )
        cur_time = time.time()
        REPORT_TIME = 3600
        # return a mail text body for the given transaction list
        mail_text = [
            "Local time: {}".format(time.ctime(cur_time)),
            "{} initiated:".format(logging_tools.get_plural("transaction", len(trans_list))),
            "",
        ] + [
            "   - {} -> {}".format(_trans.name, _trans.action) for _trans in trans_list
        ] + [
            ""
        ]
        with self.get_cursor() as crsr:
            for _trans in trans_list:
                _srv_id = crsr.execute(
                    "SELECT idx FROM service WHERE name=?",
                    (_trans.name,),
                ).fetchone()[0]
                _states = crsr.execute(
                    "SELECT state, license_state, created, proc_info_str FROM state WHERE service=? AND created > ? ORDER BY -created",
                    (_srv_id, cur_time - REPORT_TIME)
                ).fetchall()
                _actions = crsr.execute(
                    "SELECT action, success, runtime, finished, created FROM action WHERE service=? AND created > ? ORDER BY -created",
                    (_srv_id, cur_time - REPORT_TIME)
                ).fetchall()
                mail_text.extend(
                    [
                        "{} and {} for service {} in the last {}:".format(
                            logging_tools.get_plural("state", len(_states)),
                            logging_tools.get_plural("action", len(_states)),
                            _trans.name,
                            logging_tools.get_diff_time_str(REPORT_TIME),
                        ),
                        "",
                    ] + [
                        "{} state={}, license_state={} [{}]".format(
                            time.ctime(int(_state[2])),
                            _state[0],
                            _state[1],
                            _state[3],
                        ) for _state in _states
                    ] + [
                        ""
                    ] + [
                        "{} action={}, runtime={:.2f} [{} / {}]".format(
                            time.ctime(int(_action[4])),
                            _action[0],
                            _action[2],
                            _action[1],
                            _action[3],
                        ) for _action in _actions
                    ]
                )
        return subject, mail_text

    def handle_command(self, srv_com):
        # returns True if the state machine should be triggered
        trigger = False
        _com = srv_com["command"].text[5:]
        _bldr = srv_com.builder()
        cur_time = time.time()
        if self.__shutdown:
            # ignore commands when in shutdown mode
            srv_com.set_result(
                "server is shutting down",
                server_command.SRV_REPLY_STATE_ERROR,
            )
        elif _com == "overview":
            instances = _bldr.instances()
            if "services" in srv_com:
                services = [_name for _name in srv_com["*services"].strip().split(",") if _name.strip()]
            else:
                services = []
            with self.get_cursor() as crsr:
                with self.get_cursor() as state_crsr:
                    for _srv_id, name, target_state, active in crsr.execute("SELECT idx, name, target_state, active FROM service ORDER BY name"):
                        if services and name not in services:
                            continue
                        instances.append(
                            _bldr.instance(
                                _bldr.states(
                                    *[
                                        _bldr.state(
                                            state="{:d}".format(state),
                                            license_state="{:d}".format(license_state),
                                            created="{:d}".format(int(created)),
                                            proc_info_str=proc_info_str,
                                        ) for state, license_state, created, proc_info_str in state_crsr.execute(
                                            "SELECT state, license_state, created, proc_info_str FROM state WHERE service=? AND created > ? ORDER BY -created",
                                            (_srv_id, cur_time - 24 * 3600),
                                        )
                                    ]
                                ),
                                _bldr.actions(
                                    *[
                                        _bldr.action(
                                            action="{:s}".format(action),
                                            success="{:d}".format(success),
                                            runtime="{:.2f}".format(runtime),
                                            finished="{:d}".format(finished),
                                            created="{:d}".format(int(created)),
                                        ) for action, success, runtime, finished, created in state_crsr.execute(
                                            "SELECT action, success, runtime, finished, created FROM action WHERE service=? AND created > ? ORDER BY -created",
                                            (_srv_id, cur_time - 24 * 3600),
                                        )
                                    ]
                                ),
                                name=name,
                                target_state="{:d}".format(target_state),
                                active="{:d}".format(active),
                            )
                        )
            srv_com["overview"] = instances
        elif _com == "enable":
            services = [_name for _name in srv_com["*services"].strip().split(",") if _name.strip()]
            with self.get_cursor(cached=False) as crsr:
                enable_list = [
                    (_entry[0], _entry[1]) for _entry in crsr.execute(
                        "SELECT idx, name FROM service WHERE target_state={:d}".format(
                            constants.TARGET_STATE_STOPPED
                        )
                    ).fetchall() if _entry[1] in services
                ]
                for _idx, _name in enable_list:
                    crsr.execute(
                        "UPDATE service SET target_state=? WHERE idx=?",
                        (constants.TARGET_STATE_RUNNING, _idx)
                    )
                    crsr.execute(
                        "INSERT INTO action(service, action, created, success, finished) VALUES(?, ?, ?, ?, ?)",
                        (
                            _idx, "enable", int(time.time()), 1, 1,
                        )
                    )
            srv_com.set_result(
                "enabled {}: {}".format(
                    logging_tools.get_plural("service", len(enable_list)),
                    ", ".join([_name for _id, _name in enable_list]) or "none",
                )
            )
            trigger = self._update_target_dict()
        elif _com == "disable":
            services = [_name for _name in srv_com["*services"].strip().split(",") if _name.strip()]
            with self.get_cursor(cached=False) as crsr:
                disable_list = [
                    (_entry[0], _entry[1]) for _entry in crsr.execute(
                        "SELECT idx, name FROM service WHERE target_state={:d}".format(
                            constants.TARGET_STATE_RUNNING
                        )
                    ).fetchall() if _entry[1] in services
                ]
                for _idx, _name in disable_list:
                    crsr.execute(
                        "UPDATE service SET target_state=? WHERE idx=?",
                        (constants.TARGET_STATE_STOPPED, _idx)
                    )
                    crsr.execute(
                        "INSERT INTO action(service, action, created, success, finished) VALUES(?, ?, ?, ?, ?)",
                        (
                            _idx, "disable", int(time.time()), 1, 1,
                        )
                    )
            srv_com.set_result(
                "disabled {}: {}".format(
                    logging_tools.get_plural("service", len(disable_list)),
                    ", ".join([_name for _id, _name in disable_list]) or "none",
                )
            )
            trigger = self._update_target_dict()
        else:
            srv_com.set_result(
                "command {} not defined".format(srv_com["command"].text),
                server_command.SRV_REPLY_STATE_ERROR,
            )
        return trigger
