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

""" host-monitoring, main part """

import sys

from initat.tools import configfile, process_tools


def run_code(prog_name, global_config):
    if prog_name in ["collserver"]:
        from initat.host_monitoring.server import ServerCode
        ret_state = ServerCode(global_config).loop()
    elif prog_name in ["collrelay"]:
        from initat.host_monitoring.relay import RelayCode
        ret_state = RelayCode(global_config).loop()
    elif prog_name == "collclient":
        from initat.host_monitoring.client import ClientCode
        ret_state = ClientCode(global_config)
    else:
        print("Unknown mode {}".format(prog_name))
        ret_state = -1
    return ret_state


def main(options=None):
    global_config = configfile.get_global_config(
        process_tools.get_programm_name(),
        single_process_mode=True
    )
    prog_name = global_config.name()
    if prog_name == "collclient":
        global_config.add_config_entries(
            [
                ("IDENTITY_STRING", configfile.str_c_var(options.IDENTITY_STRING)),
                ("TIMEOUT", configfile.int_c_var(options.TIMEOUT)),
                ("COMMAND_PORT", configfile.int_c_var(options.COMMAND_PORT)),
                ("HOST", configfile.str_c_var(options.HOST)),
                ("ARGUMENTS", configfile.array_c_var(options.ARGUMENTS)),
            ]
        )
    ret_state = run_code(prog_name, global_config)
    return ret_state


if __name__ == "__main__":
    sys.exit(main())
