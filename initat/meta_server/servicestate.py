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

""" meta-server, ServiceState code """

import os
import sqlite3
import time
import commands

from initat.meta_server.config import global_config
from initat.tools import logging_tools, server_command, process_tools
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


# format: configured state (stop / run) -> current state -> license state ->
# if the evaluation of SERVICE_OK_DICT yields to None
# or if the license_state is in the resulting tuple
# the current state is deemed ok
class ServiceActionState(object):
    @staticmethod
    def setup(parent):
        ServiceActionState.parent = parent
        ServiceActionState.num_states = 0
        ServiceActionState.mapping = {
            "target": constants.TARGET_STATE_DICT,
            "process": constants.STATE_DICT,
            "configured": constants.CONF_STATE_DICT,
            "license": constants.LIC_STATE_DICT,
        }
        ServiceActionState.keys = ["target", "process", "configured", "license"]
        # decision dict
        ServiceActionState.d_dict = {}

    @staticmethod
    def g_log(what, log_level=logging_tools.LOG_LEVEL_OK):
        ServiceActionState.parent.log("[sas] {}".format(what), log_level)

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        ServiceActionState.parent.log("[sas] {}".format(what), log_level)

    def __init__(self, **kwargs):
        # target state(s) or NONE if does not matter
        self._vals = {_key: None for _key in ServiceActionState.keys}
        for _key in ServiceActionState.keys:
            if _key in kwargs:
                _val = kwargs[_key]
                self._vals[_key] = _val if type(_val) is list else [_val]
        self._action = kwargs["action"]
        ServiceActionState.add_state(self)

    @staticmethod
    def add_state(sas):
        _als = []
        ServiceActionState.num_states += 1
        for _key in ServiceActionState.keys:
            _vals = sas._vals[_key]
            if _vals is None:
                _vals = ServiceActionState.mapping[_key]
            if not _als:
                _als = [[_val] for _val in _vals]
            else:
                _als = sum([[_pl + [_val] for _val in _vals] for _pl in _als], [])
        for _tuple in _als:
            ServiceActionState.d_dict[tuple(_tuple)] = sas._action
        ServiceActionState.g_log(
            "added action {}, {:d} states defined, {:d} keys".format(
                sas._action,
                ServiceActionState.num_states,
                len(ServiceActionState.d_dict),
            )
        )

    @staticmethod
    def get_action(_tuple):
        return ServiceActionState.d_dict.get(_tuple, "keep")


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
        self.init_sas()
        self._init_states()
        self.init_db()
        self.__shutdown = False
        # for throtteling
        self.__throttle_dict = {}

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_com("[SrvState] {}".format(what), log_level)

    def init_sas(self):
        ServiceActionState.setup(self)
        ServiceActionState(
            target=constants.TARGET_STATE_RUNNING,
            process=constants.SERVICE_OK,
            configured=constants.CONF_STATE_RUN,
            license=[
                constants.LIC_STATE_VALID,
                constants.LIC_STATE_NOT_NEEDED,
                constants.LIC_STATE_GRACE,
            ],
            action="keep",
        )
        ServiceActionState(
            target=constants.TARGET_STATE_RUNNING,
            process=constants.SERVICE_DEAD,
            configured=[
                constants.CONF_STATE_STOP,
                constants.CONF_STATE_IP_MISMATCH,
            ],
            license=[
                constants.LIC_STATE_VIOLATED,
                constants.LIC_STATE_EXPIRED,
                constants.LIC_STATE_VALID_IN_FUTURE,
                constants.LIC_STATE_NONE,
            ],
            action="keep",
        )
        ServiceActionState(
            target=constants.TARGET_STATE_RUNNING,
            configured=constants.CONF_STATE_RUN,
            process=[constants.SERVICE_INCOMPLETE, constants.SERVICE_NOT_INSTALLED, constants.SERVICE_DEAD],
            license=[
                constants.LIC_STATE_VALID,
                constants.LIC_STATE_NOT_NEEDED,
                constants.LIC_STATE_GRACE,
            ],
            action="start",
        )
        ServiceActionState(
            target=constants.TARGET_STATE_RUNNING,
            configured=[constants.CONF_STATE_STOP, constants.CONF_STATE_IP_MISMATCH, constants.CONF_STATE_MODELS_CHANGED],
            process=[constants.SERVICE_OK, constants.SERVICE_INCOMPLETE],
            action="stop",
        )
        ServiceActionState(
            target=constants.TARGET_STATE_STOPPED,
            process=[constants.SERVICE_DEAD, constants.SERVICE_NOT_INSTALLED, constants.SERVICE_NOT_CONFIGURED],
            action="keep",
        )
        ServiceActionState(
            target=constants.TARGET_STATE_STOPPED,
            process=[constants.SERVICE_INCOMPLETE, constants.SERVICE_OK],
            action="stop",
        )

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
                # process state, defaults to (==SERVICE_DEAD)
                "pstate INTEGER DEFAULT {:d}".format(constants.SERVICE_DEAD),
                # configured state, defaults to (==CONF_STATE_STOP)
                "cstate INTEGER DEFAULT {:d}".format(constants.CONF_STATE_STOP),
                # license state, defaults to -1 (==NOT_NEEDED)
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
        all_tables = {
            _entry[0]: _entry[1] for _entry in conn.execute("SELECT name, sql FROM sqlite_master WHERE type='table';").fetchall()
        }
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
        # create indices
        for _t_name, _f_name in [
            ("state", "service"),
            ("state", "created"),
            ("action", "service"),
            ("action", "created"),
        ]:
            _idx_name = "{}_{}".format(_t_name, _f_name)
            conn.execute("CREATE INDEX IF NOT EXISTS {} ON {}({})".format(_idx_name, _t_name, _f_name))
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
            # services
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
        elif srv_name == "mongodb-init":
            if os.path.exists("/etc/init.d/mongodb-init"):
                _ts = constants.TARGET_STATE_RUNNING
            else:
                _ts = constants.TARGET_STATE_STOPPED
        else:
            _ts = constants.TARGET_STATE_RUNNING
        return _ts

    def _sync_system_states(self):
        # ignore when in shutdown mode
        if not self.__shutdown:
            # sync system states with internal target states for meta-server and logging-server
            _sys_states = self._parse_system_states()
            if None not in _sys_states:
                _log_s, _meta_s = (
                    True if self.__target_dict["logging-server"] == 1 else False,
                    True if self.__target_dict["meta-server"] == 1 else False,
                )
                if _log_s == _meta_s:
                    # we only support same stats for meta- and logging-serer
                    if (_log_s, _meta_s) != _sys_states:
                        if _log_s:
                            # enable logging and meta server
                            self.log("enabling logging- and meta-server for system startup")
                            self._handle_ls_for_system(True)
                        else:
                            # disable logging and meta server
                            self.log("disabling logging- and meta-server for system startup")
                            self._handle_ls_for_system(False)

    def _handle_ls_for_system(self, enable):
        _insserv_bin = process_tools.find_file("insserv")
        _update_rc_bin = process_tools.find_file("update-rc.d")
        _chkconfig_bin = process_tools.find_file("chkconfig")
        if enable:
            _srvs = ["logging-server", "meta-server"]
        else:
            _srvs = ["meta-server", "logging-server"]
        for _srv in _srvs:
            if _insserv_bin:
                _cmdline = "{} {} {}".format(
                    _insserv_bin,
                    "" if enable else "-r",
                    _srv
                )
            elif _update_rc_bin:
                _cmdline = "{} {} {}".format(
                    _update_rc_bin,
                    _srv,
                    "enable" if enable else "disable",
                )
            elif _chkconfig_bin:
                _cmdline = "{} {} {}".format(
                    _chkconfig_bin,
                    _srv,
                    "on" if enable else "off",
                )
            _stat, _out = commands.getstatusoutput(_cmdline)
            _lines = _out.split("\n")
            self.log(
                "{} gave [{:d}] {}".format(
                    _cmdline,
                    _stat,
                    logging_tools.get_plural("line", len(_lines)),
                )
            )
            for _l_num, _line in enumerate(_lines, 1):
                self.log("  {:3d} {}".format(_l_num, _line))

    def _parse_system_states(self):
        # parse runlevel, for transition from meta-server / logging-server / host-monitoring to icsw-client
        t_dirs = [_dir for _dir in ["/etc/rc3.d/", "/etc/init.d/rc3.d", "/etc/rc.d/rc3.d"] if os.path.isdir(_dir)]
        _start_l, _start_m = (None, None)
        if t_dirs:
            _start_l, _start_m = (False, False)
            t_dir = t_dirs[0]
            for entry in os.listdir(t_dir):
                _path = os.path.join(t_dir, entry)
                if os.path.islink(_path) and entry.startswith("S"):
                    if entry.endswith("logging-server"):
                        _start_l = True
                    elif entry.endswith("meta-server"):
                        _start_m = True
        return (_start_l, _start_m)

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

    def _update_state(self, name, p_state, c_state, lic_state, proc_info_str):
        if (p_state, c_state, lic_state) != self.__state_dict.get(name, None):
            self.log(
                "state for {} is {} (configured: {}, license: {}, target_dict_state TODO)".format(
                    name,
                    constants.STATE_DICT[p_state],
                    constants.CONF_STATE_DICT[c_state],
                    constants.LIC_STATE_DICT[lic_state],
                )
            )
            self.__state_dict[name] = (p_state, c_state, lic_state)
            with self.get_cursor() as crs:
                crs.execute(
                    "INSERT INTO state(service, license_state, pstate, cstate, proc_info_str, created) VALUES(?, ?, ?, ?, ?, ?)",
                    (self.__service_lut[name], lic_state, p_state, c_state, proc_info_str, int(time.time())),
                )
        # check if the current state is in sync with the targetstate
        _ct = (self.__target_dict[name], p_state, c_state, lic_state)
        return self._check_current_state(_ct)

    def _check_current_state(self, ct):
        _target, _process, _config, _license = ct
        _action = ServiceActionState.get_action(ct)
        return (_action == "keep", _action)

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
                "SELECT pstate, cstate, license_state, ?-created FROM state WHERE service=? ORDER BY -created LIMIT 10",
                (cur_time, self.__service_lut[name]),
            ).fetchall()
            _stable = True
            # correct times
            _records = [(_a, _b, _c, abs(_d)) for _a, _b, _c, _d in _records]
            # print _records
            _first = _records.pop(0)
            _stable_time = _first[3]
            for _rec in _records:
                if _rec[3] < STABLE_INTERVAL:
                    # only compare records which are not older than STABLE_INTERVAL
                    if _rec[0:3] != _first[0:3]:
                        _stable = False
                        break
                    else:
                        _stable_time = _rec[3]
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
            c_rec = (self.__target_dict[name], _first[0], _first[1], _first[2])
            # print _first, c_rec
            if not self._check_current_state(c_rec)[0] and _first[3] < MIN_STATE_TIME:
                service.log("state is not OK", logging_tools.LOG_LEVEL_WARN)
                _stable = False
            elif _first[3] < MIN_STATE_TIME:
                service.log(
                    "state not old enough ({:.2f} < {:.2f})".format(
                        _first[3],
                        MIN_STATE_TIME
                    ),
                    logging_tools.LOG_LEVEL_WARN
                )
                _stable = False
        return _stable

    def _generate_transition(self, service, action):
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
            with self.get_cursor() as crs:
                crs.execute(
                    "INSERT INTO action(service, action, created) VALUES(?, ?, ?)",
                    (
                        self.__service_lut[name], action, int(time.time())
                    ),
                )
                trans_id = crs.lastrowid
                self.__transition_lock_dict[name] = cur_time
            return [
                ServiceStateTranstaction(
                    name,
                    action,
                    trans_id,
                )
            ]

    def transition_finished(self, trans):
        t_id = trans.id
        self.log("transition {:d} finished".format(t_id))
        with self.get_cursor(cached=False) as crs:
            crs.execute(
                "UPDATE action SET runtime=?, finished=1 WHERE idx=?",
                (
                    abs(time.time() - trans.init_time), t_id
                ),
            )
            # get service
            name = crs.execute(
                "SELECT s.name FROM service s, action a WHERE a.service=s.idx AND a.idx=?",
                (t_id,),
            ).fetchone()[0]
            if name in self.__transition_lock_dict:
                del self.__transition_lock_dict[name]

    def _check_for_throttle(self, el, cur_time, t_dict):
        if el.name in t_dict and el.name in self.__throttle_dict and abs(cur_time - self.__throttle_dict[el.name]) < t_dict[el.name]:
            self.log("throtteling transition generation for {}".format(el.name), logging_tools.LOG_LEVEL_WARN)
            return True
        else:
            self.__throttle_dict[el.name] = cur_time
            return False

    def update(self, res_list, **kwargs):
        # services to exclude from transition
        exclude = kwargs.get("exclude", [])
        # force mode (for first call or command-line induced)
        force = kwargs.get("force", False)
        # list of instances which should be throttled
        throttle_dict = {key: delay for key, delay in kwargs.get("throttle", [])}
        # return a transition list
        t_list = []
        # time
        cur_time = time.time()
        for _el in res_list:
            if int(_el.entry.attrib["startstop"]):
                # ignore entries without startstop == 1
                _res = _el.entry.find(".//result")
                if _res is not None:
                    # print etree.tostring(_el.entry, pretty_print=True)
                    _p_state = int(_res.find("process_state_info").attrib["state"])
                    _c_state = int(_res.find("configured_state_info").attrib["state"])
                    _lic_state = int(_res.find("license_info").attrib["state"])
                    _proc_info_str = _res.find("process_state_info").get("proc_info_str", "")
                    _is_ok, _action = self._update_state(_el.name, _p_state, _c_state, _lic_state, _proc_info_str)
                    if not _is_ok:
                        if self.__shutdown:
                            if _el.name not in exclude:
                                if not self._check_for_throttle(_el, cur_time, throttle_dict):
                                    t_list.extend(self._generate_transition(_el, _action))
                        else:
                            _stable = self._check_for_stable_state(_el)
                            _el.log(
                                "not OK ({}, PState={}, CState={}, LState={} [{}], {}, {})".format(
                                    "should run" if self.__target_dict[_el.name] else "should not run",
                                    constants.STATE_DICT[_p_state],
                                    constants.CONF_STATE_DICT[_c_state],
                                    constants.LIC_STATE_DICT[_lic_state],
                                    "stable" if _stable else "not stable",
                                    logging_tools.get_plural("pid", len(_res.findall(".//pid"))),
                                    _proc_info_str or '---',
                                ),
                                logging_tools.LOG_LEVEL_WARN
                            )
                            if _stable or force:
                                if _el.name not in exclude:
                                    if not self._check_for_throttle(_el, cur_time, throttle_dict):
                                        t_list.extend(self._generate_transition(_el, _action))
                else:
                    _el.log("no result entry found", logging_tools.LOG_LEVEL_WARN)
        self.conn.commit()
        # sync system states with target states (for meta-server and logging-server)
        self._sync_system_states()
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
                    "SELECT pstate, cstate, license_state, created, proc_info_str FROM state WHERE service=? AND created > ? ORDER BY -created",
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
                        "{} pstate={}, cstate={}, license_state={} [{}]".format(
                            time.ctime(int(_state[3])),
                            _state[0],
                            _state[1],
                            _state[2],
                            _state[4],
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
                    for _srv_id, name, target_state, active in crsr.execute(
                        "SELECT idx, name, target_state, active FROM service ORDER BY name"
                    ):
                        if services and name not in services:
                            continue
                        instances.append(
                            _bldr.instance(
                                _bldr.states(
                                    *[
                                        _bldr.state(
                                            pstate="{:d}".format(p_state),
                                            cstate="{:d}".format(c_state),
                                            license_state="{:d}".format(license_state),
                                            created="{:d}".format(int(created)),
                                            proc_info_str=proc_info_str,
                                        ) for p_state, c_state, license_state, created, proc_info_str in state_crsr.execute(
                                            "SELECT pstate, cstate, license_state, created, proc_info_str FROM state "
                                            "WHERE service=? AND created > ? ORDER BY -created LIMIT 100",
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
                                            "SELECT action, success, runtime, finished, created FROM action "
                                            "WHERE service=? AND created > ? ORDER BY -created LIMIT 100",
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
            self._sync_system_states()
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
            self._sync_system_states()
        else:
            srv_com.set_result(
                "command {} not defined".format(srv_com["command"].text),
                server_command.SRV_REPLY_STATE_ERROR,
            )
        self.log("handled command {} in {}".format(_com, logging_tools.get_diff_time_str(time.time() - cur_time)))
        return trigger
