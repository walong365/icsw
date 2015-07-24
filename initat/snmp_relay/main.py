# Copyright (C) 2013-2015 Andreas Lang-Nevyjel
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
""" SNMP relayer """

import os

from initat.tools import configfile
from initat.tools import process_tools
from initat.snmp_relay.config import global_config


def run_code():
    from initat.snmp_relay.server import server_process
    server_process().loop()


def main():
    # read global configfile
    prog_name = global_config.name()
    global_config.add_config_entries(
        [
            ("BASEDIR_NAME", configfile.str_c_var("/etc/sysconfig/snmp-relay.d")),
            ("DEBUG", configfile.bool_c_var(False, help_string="enable debug mode [%(default)s]", short_options="d", only_commandline=True)),
            ("SNMP_PROCESSES", configfile.int_c_var(4, help_string="number of SNMP processes [%(default)d]", short_options="n")),
            ("MAIN_TIMER", configfile.int_c_var(60, help_string="main timer [%(default)d]")),
            ("LOG_NAME", configfile.str_c_var("snmp-relay")),
            ("LOG_DESTINATION", configfile.str_c_var("uds:/var/lib/logging-server/py_log_zmq")),
            ("MAX_CALLS", configfile.int_c_var(100, help_string="number of calls per helper process [%(default)d]")),
            ("VERBOSE", configfile.int_c_var(0, help_string="set verbose level [%(default)d]", short_options="v", only_commandline=True)),
            (
                "PID_NAME",
                configfile.str_c_var(
                    os.path.join(
                        prog_name,
                        prog_name
                    )
                )
            ),
        ]
    )
    _options = global_config.handle_commandline(
        positional_arguments=False,
        partial=False,
    )
    process_tools.ALLOW_MULTIPLE_INSTANCES = False
    run_code()
    configfile.terminate_manager()
    # exit
    os._exit(0)
