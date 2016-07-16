#
# Copyright (C) 2016 Andreas Lang-Nevyjel, init.at
#
# this file is part of icsw-server
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
""" main process for md-interface-server """

import os

from initat.md_interface_server.config import global_config
from initat.server_version import VERSION_STRING
from initat.tools import configfile


def run_code():
    from initat.md_interface_server.server import server_process
    server_process().loop()


def main():
    prog_name = global_config.name()
    global_config.add_config_entries(
        [
            ("DEBUG", configfile.bool_c_var(False, help_string="enable debug mode [%(default)s]", short_options="d", only_commandline=True)),
            ("VERBOSE", configfile.int_c_var(0, help_string="set verbose level [%(default)d]", short_options="v", only_commandline=True)),
            ("MEMCACHE_ADDRESS", configfile.str_c_var("127.0.0.1", help_string="memcache address")),
        ]
    )
    _options = global_config.handle_commandline(
        description="{}, version is {}".format(
            prog_name,
            VERSION_STRING
        ),
        positional_arguments=False
    )
    # enable connection debugging
    run_code()
    # exit
    os._exit(0)
