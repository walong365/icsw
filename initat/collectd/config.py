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

""" base constants and logging base """

import logging_tools
import process_tools
import uuid_tools
import configfile

global_config = configfile.get_global_config("collectd-init", single_process=True, ignore_lock=True)
global_config.add_config_entries([
    ("SNMP_PROCS", configfile.int_c_var(4, help_string="number of SNMP processes to use [%(default)s]")),
    ("MAX_SNMP_JOBS", configfile.int_c_var(40, help_string="maximum number of jobs a SNMP process shall handle [%(default)s]")),
    ("LOG_NAME", configfile.str_c_var("collectd", help_string="log instance name to use [%(default)s]")),
    ("RECV_PORT", configfile.int_c_var(8002, help_string="receive port, do not change [%(default)s]")),
    ("COMMAND_PORT", configfile.int_c_var(8008, help_string="command port, do not change [%(default)s]")),
    ("GRAPHER_PORT", configfile.int_c_var(8003, help_string="grapher port, do not change [%(default)s]")),
    ("MD_SERVER_HOST", configfile.str_c_var("127.0.0.1", help_string="md-config-server host [%(default)s]")),
    ("MD_SERVER_PORT", configfile.int_c_var(8010, help_string="md-config-server port, do not change [%(default)s]")),
    ("MEMCACHE_HOST", configfile.str_c_var("127.0.0.1", help_string="host where memcache resides [%(default)s]")),
    ("MEMCACHE_PORT", configfile.int_c_var(11211, help_string="port on which memcache is reachable [%(default)s]")),
    ("MEMCACHE_TIMEOUT", configfile.int_c_var(2 * 60, help_string="timeout in seconds for values stored in memcache [%(default)s]"))
])
global_config.parse_file()
global_config.write_file()

IPC_SOCK = process_tools.get_zmq_ipc_name("com", connect_to_root_instance=True, s_name="collectd")
IPC_SOCK_SNMP = process_tools.get_zmq_ipc_name("snmp", connect_to_root_instance=True, s_name="collectd")

LOG_DESTINATION = "ipc:///var/lib/logging-server/py_log_zmq"

MD_SERVER_UUID = uuid_tools.get_uuid().get_urn()


class log_base(object):
    def __init__(self):
        self.__log_template = logging_tools.get_logger(
            global_config["LOG_NAME"],
            LOG_DESTINATION,
            zmq=True,
            context=self.zmq_context,
        )
        # ignore alternating process ids
        self.__log_template.log_command("ignore_process_id")

    @property
    def log_template(self):
        return self.__log_template

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)

    def close_log(self):
        self.__log_template.close()
