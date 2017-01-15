# Copyright (C) 2001-2009,2012-2015,2017 Andreas Lang-Nevyjel
#
# this file is part of package-client
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
""" daemon to automatically install packages (.rpm, .deb) """

import os

from initat.package_install.client.config import global_config
from initat.client_version import VERSION_STRING
from initat.tools import configfile, process_tools


def run_code():
    from initat.package_install.client.server import server_process
    server_process().loop()


def main():
    prog_name = global_config.name()
    global_config.add_config_entries(
        [
            ("DEBUG", configfile.bool_c_var(False, help_string="enable debug mode [%(default)s]", short_options="d", only_commandline=True)),
            ("VERBOSE", configfile.int_c_var(0, help_string="set verbose level [%(default)d]", short_options="v", only_commandline=True)),
        ]
    )
    _options = global_config.handle_commandline(
        description="{}, version is {}".format(
            prog_name,
            VERSION_STRING
        ),
        positional_arguments=False,
        partial=False
    )
    ret_code = 0
    ps_file_name = "/etc/packageserver"
    if not os.path.isfile(ps_file_name):
        try:
            open(ps_file_name, "w").write("localhost\n")
        except:
            print(("error writing to {}: {}".format(ps_file_name, process_tools.get_except_info())))
            ret_code = 5
        else:
            pass
    try:
        global_config.add_config_entries(
            [
                ("PACKAGE_SERVER", configfile.str_c_var(open(ps_file_name, "r").read().strip().split("\n")[0].strip())),
                ("VERSION", configfile.str_c_var(VERSION_STRING)),
            ]
        )
    except:
        print(("error reading from {}: {}".format(ps_file_name, process_tools.get_except_info())))
        ret_code = 5
    if not ret_code:
        global_config.add_config_entries([("DEBIAN", configfile.bool_c_var(os.path.isfile("/etc/debian_version")))])
        run_code()
        # exit
        os._exit(0)
    return 0
