# -*- coding: utf-8 -*-
#
# Copyright (C) 2013-2017 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of host-monitoring
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


def main():
    global_config = configfile.get_global_config(
        process_tools.get_programm_name(),
        single_process_mode=True
    )
    global_config.add_config_entries(
        [
            (
                "DEBUG",
                configfile.bool_c_var(
                    False,
                )
            ),
            (
                "VERBOSE",
                configfile.int_c_var(
                    0,
                )
            ),
        ]
    )
    from initat.host_monitoring.server import ServerCode
    ret_state = ServerCode(global_config).loop()

    return ret_state


if __name__ == "__main__":
    sys.exit(main())
