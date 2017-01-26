# Copyright (C) 2013-2015,2017 Andreas Lang-Nevyjel
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
""" SNMP relayer """

import os

from initat.snmp_relay.config import global_config
from initat.tools import configfile, process_tools


def run_code():
    from initat.snmp_relay.server import server_process
    server_process().loop()


def main():
    # read global configfile
    prog_name = global_config.name()
    global_config.add_config_entries(
        [
            ("BASEDIR_NAME", configfile.str_c_var("/etc/sysconfig/snmp-relay.d")),
            ("SNMP_PROCESSES", configfile.int_c_var(4, help_string="number of SNMP processes [%(default)d]")),
            ("MAIN_TIMER", configfile.int_c_var(60, help_string="main timer [%(default)d]")),
            ("MAX_CALLS", configfile.int_c_var(100, help_string="number of calls per helper process [%(default)d]")),
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
    process_tools.ALLOW_MULTIPLE_INSTANCES = False
    run_code()
    # exit
    os._exit(0)
