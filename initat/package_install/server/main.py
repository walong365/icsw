# Copyright (C) 2001-2009,2012-2015 Andreas Lang-Nevyjel
#
# this file is part of package-server
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
""" package server """

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

import django
django.setup()

from django.db import connection
from initat.cluster.backbone.models import LogSource
from .constants import P_SERVER_PUB_PORT, PACKAGE_CLIENT_PORT
from .config import global_config
from initat.tools import config_tools, configfile, process_tools

from initat.server_version import VERSION_STRING


def run_code():
    from initat.package_install.server.server import server_process
    server_process().loop()


def main():
    long_host_name, _mach_name = process_tools.get_fqdn()
    prog_name = global_config.name()
    global_config.add_config_entries(
        [
            ("DEBUG", configfile.bool_c_var(False, help_string="enable debug mode [%(default)s]", short_options="d", only_commandline=True)),
            ("PID_NAME", configfile.str_c_var(os.path.join(prog_name, prog_name))),
            ("USER", configfile.str_c_var("idpacks", help_string="user to run as [%(default)s]")),
            ("GROUP", configfile.str_c_var("idg", help_string="group to run as [%(default)s]")),
            ("GROUPS", configfile.array_c_var(["idg"])),
            ("LOG_DESTINATION", configfile.str_c_var("uds:/var/lib/logging-server/py_log_zmq")),
            ("LOG_NAME", configfile.str_c_var(prog_name)),
            ("VERBOSE", configfile.int_c_var(0, help_string="set verbose level [%(default)d]", short_options="v", only_commandline=True)),
            ("SERVER_PUB_PORT", configfile.int_c_var(P_SERVER_PUB_PORT, help_string="server publish port [%(default)d]")),
            ("NODE_PORT", configfile.int_c_var(PACKAGE_CLIENT_PORT, help_string="port where the package-clients are listening [%(default)d]")),
            ("DELETE_MISSING_REPOS", configfile.bool_c_var(False, help_string="delete non-existing repos from DB")),
            ("SUPPORT_OLD_CLIENTS", configfile.bool_c_var(False, help_string="support old clients [%(default)s]", database=True)),
        ]
    )
    global_config.parse_file()
    _options = global_config.handle_commandline(
        description="{}, version is {}".format(
            prog_name,
            VERSION_STRING
        ),
        add_writeback_option=True,
        positional_arguments=False,
    )
    global_config.write_file()
    sql_info = config_tools.server_check(server_type="package_server")
    if not sql_info.effective_device:
        print "not a package_server"
        return 5
    global_config.add_config_entries(
        [
            (
                "SERVER_IDX",
                configfile.int_c_var(sql_info.effective_device.pk, database=False)
            ),
            (
                "LOG_SOURCE_IDX",
                configfile.int_c_var(LogSource.new("package-server", device=sql_info.effective_device).pk)
            )
        ]
    )
    # close DB connection
    connection.close()
    run_code()
    configfile.terminate_manager()
    os._exit(0)
