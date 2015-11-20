# -*- coding: utf-8 -*-
#
# Copyright (C) 2013-2015 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of host-monitoring
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

""" host-monitoring, main part """

import sys


if __name__ == "__main__":
    # modify path if testing
    sys.path.insert(0, ".")

from initat.host_monitoring.config import global_config
from initat.client_version import VERSION_STRING
from initat.tools import configfile
from initat.icsw.service.instance import InstanceXML


def run_code(prog_name, global_config):
    if prog_name in ["collserver"]:
        from initat.host_monitoring.server import server_code
        ret_state = server_code().loop()
    elif prog_name in ["collrelay"]:
        from initat.host_monitoring.relay import relay_code
        ret_state = relay_code().loop()
    elif prog_name == "collclient":
        from initat.host_monitoring.client import client_code
        ret_state = client_code(global_config)
    else:
        print("Unknown mode {}".format(prog_name))
        ret_state = -1
    return ret_state


def main():
    prog_name = global_config.name()
    global_config.add_config_entries(
        [
            ("DEBUG", configfile.bool_c_var(False, help_string="enable debug mode [%(default)s]", short_options="d", only_commandline=True)),
            ("VERBOSE", configfile.int_c_var(0, help_string="set verbose level [%(default)d]", short_options="v", only_commandline=True)),
        ]
    )
    if prog_name == "collclient":
        global_config.add_config_entries(
            [
                ("IDENTITY_STRING", configfile.str_c_var("collclient", help_string="identity string", short_options="i")),
                ("TIMEOUT", configfile.int_c_var(10, help_string="set timeout [%(default)d", only_commandline=True)),
                (
                    "COM_PORT",
                    configfile.int_c_var(
                        InstanceXML(quiet=True).get_port_dict("host-monitoring", command=True),
                        info="listening Port",
                        help_string="port to communicate [%(default)d]",
                        short_options="p"
                    )
                ),
                ("HOST", configfile.str_c_var("localhost", help_string="host to connect to")),
            ]
        )
    options = global_config.handle_commandline(
        description="{}, version is {}".format(
            prog_name,
            VERSION_STRING
        ),
        positional_arguments=prog_name in ["collclient"],
        partial=prog_name in ["collclient"],
    )
    ret_state = run_code(prog_name, global_config)
    return ret_state


if __name__ == "__main__":
    main()
