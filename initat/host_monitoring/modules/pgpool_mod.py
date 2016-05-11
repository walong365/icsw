# -*- coding: utf-8 -*-

# Copyright (C) 2008-2016 Andreas Lang-Nevyjel, init.at
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

"""
Checks related to pgpool-II >= 3.0 via SQL interface.
"""

import cPickle
import os
from ConfigParser import SafeConfigParser
import subprocess

from initat.host_monitoring import limits
from initat.host_monitoring.hm_classes import hm_command, hm_module
from initat.tools import server_command, logging_tools, process_tools, config_store

try:
    import psycopg2  # @UnresolvedImport
except:
    psycopg2 = None

CONFIG_DIR = "/etc/sysconfig/host-monitoring.d/"
CONFIG_FILE = "database.config"
SECTION = "pgpool"

CSTORE_NAME = "icsw.hm.pgpool_access"

DEFAULTS = {
    "HOST": "",
    "PORT": "5432",
    "USER": "postgres",
    "PASSWORD": "",
    "DATABASE": "template1"
}

# Key used in srv_com dictionary like objects
KEY = "pgpool"

NODE_UP_NO_CONN = 1  # Node is up. No connections yet.
NODE_UP = 2  # Node is up. Connections are pooled.
NODE_DOWN = 3  # Node is down.

NS_DICT = {
    NODE_UP_NO_CONN: "node up, no connection",
    NODE_UP: "node up, connections are pooled",
    NODE_DOWN: "node down",
}


class PGPoolUsage(object):
    def __init__(self):
        self.events = []

    def feed(self, entry):
        if entry:
            self.events.append(entry)

    def get_usage(self, key):
        _s_keys = key.split("/")
        _header_dict = {
            "Backend ID": "Backend"
        }
        _res = {}
        for event in self.events:
            _ke = ".".join(
                [
                    "{} {}".format(
                        _header_dict.get(_key, _key),
                        event[_key]
                    ).strip().replace(" ", "_") for _key in _s_keys
                ]
            )
            _res.setdefault(_ke, []).append((event["Connected"], event["Counter"]))
        _res_2 = {}
        _mv_list = []
        for _key, _value in _res.iteritems():
            _key = "pgpool.worker.{}".format(_key)
            _len = len(_value)
            _connected = len([True for _ev in _value if _ev[0]])
            _counter = sum([_ev[1] for _ev in _value])
            _mv_list.extend(
                [
                    (
                        "{}.num".format(_key),
                        _len,
                        "Number of workers for $3",
                    ),
                    (
                        "{}.connected".format(_key),
                        _connected,
                        "active connections for $3",
                    ),
                    (
                        "{}.free".format(_key),
                        _len - _connected,
                        "idle connections for $3",
                    ),
                    (
                        "{}.counter".format(_key),
                        _counter,
                        "Number of calls for $3",
                    ),
                ]
            )
        return _mv_list


class PGPoolOverview(object):
    def __init__(self, mv, log_com):
        self.__log_com = log_com
        self.mv = mv
        self.mv_keys = set()
        self._pcp_proc_info = process_tools.find_file("pcp_proc_info")
        self.enabled = False
        if self._pcp_proc_info:
            self.log("found pcp_proc_info at {}".format(self._pcp_proc_info))
            if config_store.ConfigStore.exists(CSTORE_NAME):
                self.enabled = True
                self._pgpool_config = config_store.ConfigStore(CSTORE_NAME, log_com=self.log)
            else:
                self.log("no config_store named {} found".format(CSTORE_NAME), logging_tools.LOG_LEVEL_WARN)
        else:
            self.log("foudn no pcp_proc_info, disabled monitoring", logging_tools.LOG_LEVEL_WARN)

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_com("[PGO] {}".format(what), log_level)

    def _build_command(self):
        return "{} {:d} {} {:d} {} {} -a -v".format(
            self._pcp_proc_info,
            self._pgpool_config["pgpool.timeout"],
            self._pgpool_config["pgpool.address"],
            self._pgpool_config["pgpool.port"],
            self._pgpool_config["pgpool.user"],
            self._pgpool_config["pgpool.password"],
        )

    def update_machine_vector(self, mv):
        if not self.enabled:
            return
        try:
            _out = subprocess.check_output(
                self._build_command(),
                shell=True,
            )
        except subprocess.CalledProcessError:
            self.log(
                "error calling pcp_info: {}".format(
                    process_tools.get_except_info(),
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
        else:
            _results = PGPoolUsage()
            _entry = {}
            for _line in _out.split("\n"):
                if _line.count(":"):
                    _key, _value = _line.split(":", 1)
                    _key = _key.strip()
                    _value = _value.strip()
                    if _value.isdigit():
                        _value = int(_value)
                    if _key == "Database":
                        _results.feed(_entry)
                        _entry = {}
                    _entry[_key] = _value
            _results.feed(_entry)
            _mv_list = []
            for _key in ["Database/Backend ID"]:
                _mv_list.extend(_results.get_usage(_key))
            _new_keys = set()
            for _key, _num, _info in _mv_list:
                _new_keys.add(_key)
                if _key not in self.mv_keys:
                    mv.register_entry(_key, 0, _info)
                mv[_key] = _num
            _old_keys = self.mv_keys - _new_keys
            for _ok in _old_keys:
                mv.unregister_entry(_ok)
            self.mv_keys = _new_keys


class _general(hm_module):
    def init_module(self):
        if psycopg2:
            self.enabled = True
        else:
            self.log("no psycopg2 module, disabling module", logging_tools.LOG_LEVEL_ERROR)
            self.enabled = False

    def init_machine_vector(self, mv):
        self.databases = {}
        self.overview = PGPoolOverview(mv, self.log)

    def update_machine_vector(self, mv):
        self.overview.update_machine_vector(mv)


class ArgumentError(Exception):
    pass


class PgPoolCommand(hm_command):
    sql = NotImplemented
    key = NotImplemented

    def read_config(self):
        self.config = {}
        parser = SafeConfigParser()
        if os.path.isfile(os.path.join(CONFIG_DIR, CONFIG_FILE)):
            parser.read(os.path.join(CONFIG_DIR, CONFIG_FILE))
        if parser.has_section(SECTION):
            self.config["host"] = parser.get(SECTION, "HOST")
            self.config["port"] = parser.get(SECTION, "PORT")
            self.config["user"] = parser.get(SECTION, "USER")
            self.config["password"] = parser.get(SECTION, "PASSWORD")
            self.config["database"] = parser.get(SECTION, "DATABASE")
        else:
            for key, value in DEFAULTS.iteritems():
                self.config[key.lower()] = value
        # Access via UNIX socket
        if not self.config["host"]:
            del self.config["host"]

    def query(self, sql=None):
        """ Passing in sql overrrides self.sql """
        cursor = psycopg2.connect(**self.config).cursor()
        if sql:
            cursor.execute(sql)
        else:
            cursor.execute(self.sql)
        return cursor.fetchall()

    def pack(self, value):
        """ Since dicts are passed through use pack and unpack to pass arbitrary objects """
        d = {}
        d["result"] = cPickle.dumps(value)
        return d

    def unpack(self, packed_dict):
        value = packed_dict["result"]
        return cPickle.loads(value)

    def __call__(self, srv_com, cur_ns):
        try:
            result = self.query()
        except (psycopg2.DatabaseError, psycopg2.InterfaceError):
            error_info = {
                "reply": "Error executing '%s'" % self.sql,
                "state": str(server_command.SRV_REPLY_STATE_ERROR)
            }
            srv_com["result"].attrib.update(error_info)
        else:
            srv_com[self.key] = self.pack(result)

"""
# Not really that useful as a check - just dumps the config info
class pgpool_status_command(PgPoolCommand):
    info_str = "Display pgpool status info"
    sql = "SHOW pool_status;"
    key = KEY
"""


class pgpool_nodes_command(PgPoolCommand):
    info_str = (
        "Check if the correct node count is returned and all nodes are not "
        "in status NODE_DOWN"
    )
    sql = "SHOW pool_nodes;"
    key = KEY

    def __init__(self, name):
        super(PgPoolCommand, self).__init__(name, positional_arguments=True)
        self.read_config()

    def interpret(self, srv_com, cur_ns):
        result = self.unpack(srv_com[self.key])
        node_count = len(result)
        state_dict = {
            _key: [_entry for _entry in result if int(_entry[3]) == _key] for _key in [NODE_DOWN, NODE_UP, NODE_UP_NO_CONN]
        }
        # filter empty states
        state_dict = {_key: _value for _key, _value in state_dict.iteritems() if _value}
        # state string
        state_str = ", ".join(
            [
                "{:d} {} : {}".format(
                    len(state_dict[_key]),
                    NS_DICT[_key],
                    ",".join([_line[1] for _line in state_dict[_key]])
                ) for _key in sorted(state_dict.keys())
            ]
        )
        nodes_up = len(state_dict.get(NODE_UP, []))
        if cur_ns.arguments:
            t_nc = int(cur_ns.arguments[0])
            if node_count != t_nc:
                state = limits.nag_STATE_CRITICAL
                text = "pgpool node count out of range: {:d}, expected: {:d}".format(node_count, t_nc)
            elif node_count != nodes_up:
                state = limits.nag_STATE_CRITICAL
                text = "pgpool: {} found but only {}".format(
                    logging_tools.get_plural("node", node_count),
                    logging_tools.get_plural("node up", node_count - nodes_up)
                )
            else:
                state = limits.nag_STATE_OK
                text = "pgpool node count: {:d}".format(node_count)
        else:
            state, text = (limits.nag_STATE_CRITICAL, "number of nodes not specified")
        text = "{}, status: {}".format(text, state_str)
        return state, text


class pgpool_processes_command(PgPoolCommand):
    info_str = "Check for the correct count of pgpool processes"
    sql = "SHOW pool_processes;"
    key = KEY

    def __init__(self, name):
        super(PgPoolCommand, self).__init__(name, positional_arguments=True)
        self.parser.add_argument("--min", dest="min", type=int, default=0)
        self.parser.add_argument("--max", dest="max", type=int, default=0)
        self.read_config()

    def interpret(self, srv_com, cur_ns):
        result = self.unpack(srv_com[self.key])
        process_count = len(result)
        if not cur_ns.min <= process_count <= cur_ns.max:
            state = limits.nag_STATE_CRITICAL
            text = "pgpool process count out of range: {:d} not in [{:d}, {:d}]".format(
                process_count,
                cur_ns.min,
                cur_ns.max,
            )
        else:
            state = limits.nag_STATE_OK
            text = "pgpool process count: {:d} in [{:d}, {:d}]".format(
                process_count,
                cur_ns.min,
                cur_ns.max,
            )
        return state, text


class pgpool_pools_command(PgPoolCommand):
    info_str = "Check for the correct count of pgpool pools"
    sql = "SHOW pool_pools;"
    key = KEY
    # Minimum and maximum count of pgpool pools - most likely to be used with min == max

    def __init__(self, name):
        super(PgPoolCommand, self).__init__(name, positional_arguments=True)
        self.parser.add_argument("--min", dest="min", type=int, default=0)
        self.parser.add_argument("--max", dest="max", type=int, default=0)
        self.read_config()

    def interpret(self, srv_com, cur_ns):
        def _val(val):
            return int(val) if val.isdigit() else val
        result = self.unpack(srv_com[self.key])
        # import pprint
        headers = [
            "pool_pid", "start_time", "pool_id", "backend_id", "database", "username",
            "create_time", "majorversion", "minorversion", "pool_counter", "pool_backendpid", "pool_connected"
        ]
        result = [{key: _val(value) for key, value in zip(headers, line)} for line in result]
        pool_count = len(result)
        if not cur_ns.min <= pool_count <= cur_ns.max:
            state = limits.nag_STATE_CRITICAL
            text = "pgpool pool count out of range: {:d} not in [{:d}, {:d}]".format(
                pool_count,
                cur_ns.min,
                cur_ns.max,
            )
        else:
            state = limits.nag_STATE_OK
            text = "pgpool pool count: {:d} in [{:d}, {:d}]".format(
                pool_count,
                cur_ns.min,
                cur_ns.max,
            )
        return state, text


class pgpool_version_command(PgPoolCommand):
    info_str = "Check for a specific version of pgpool"
    sql = "SHOW pool_version;"
    key = KEY

    def __init__(self, name):
        super(PgPoolCommand, self).__init__(name, positional_arguments=True)
        self.read_config()

    def interpret(self, srv_com, cur_ns):
        result = self.unpack(srv_com[self.key])[0][0]
        if cur_ns.arguments:
            t_vers = " ".join(cur_ns.arguments)
            result = result.replace("(", "").replace(")", "").replace("  ", " ")
            if t_vers != result:
                if result.startswith(t_vers) and t_vers:
                    state = limits.nag_STATE_WARNING
                    text = "Version not exact : {} != {}".format(t_vers, result)
                else:
                    state = limits.nag_STATE_CRITICAL
                    text = "Version mismatch: {} != {}".format(t_vers, result)
            else:
                state, text = (limits.nag_STATE_OK, "versions match ({})".format(t_vers))
        else:
            state, text = (limits.nag_STATE_CRITICAL, "no target version specified")
        return state, text
