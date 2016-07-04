# Copyright (C) 2016 Gregor Kaufmann, init.at
#
# this file is part of laser-server
#
# Send feedback to: <kaufmann@init.at>
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
""" laser-server, main part """


import os

from initat.laser_server.constants import SERVER_COM_PORT

from initat.tools import configfile
from initat.laser_server.config import global_config

def run_code():
    from initat.laser_server.server import server_process
    s = server_process()
    s.loop()

def main():
    global_config.add_config_entries(
        [
            ("DEBUG", configfile.bool_c_var(False, help_string="enable debug mode [%(default)s]", short_options="d", only_commandline=True)),
            ("VERBOSE", configfile.int_c_var(0, help_string="set verbose level [%(default)d]", short_options="v", only_commandline=True)),
            ("COM_PORT", configfile.int_c_var(SERVER_COM_PORT)),
        ]
    )

    run_code()
    configfile.terminate_manager()
    # exit
    os._exit(0)