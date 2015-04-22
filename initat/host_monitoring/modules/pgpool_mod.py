# -*- coding: utf-8 -*-

# Copyright (C) 2008-2014 Andreas Lang-Nevyjel, init.at
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

from ConfigParser import SafeConfigParser
from initat.host_monitoring import limits
from initat.host_monitoring.hm_classes import hm_command, hm_module
from initat.tools import server_command
import cPickle
from initat.tools import logging_tools
import os
try:
    import psycopg2  # @UnresolvedImport
except:
    psycopg2 = None

CONFIG_DIR = "/etc/sysconfig/host-monitoring.d/"
CONFIG_FILE = "database.config"
SECTION = "pgpool"

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


class _general(hm_module):
    def init_module(self):
        if psycopg2:
            self.enabled = True
        else:
            self.log("no psycopg2 module, disabling module", logging_tools.LOG_LEVEL_ERROR)
            self.enabled = False


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
