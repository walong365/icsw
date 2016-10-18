# Copyright (C) 2001-2008,2012-2016 Andreas Lang-Nevyjel
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
""" cluster-server """

from __future__ import unicode_literals, print_function

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

import django
django.setup()

from django.conf import settings
from initat.tools import configfile
from initat.cluster_server.config import global_config

from initat.server_version import VERSION_STRING


def run_code(options):
    from initat.cluster_server.server import ServerProcess
    ServerProcess(options).loop()


def main(opt_args=None):
    prog_name = global_config.name()
    global_config.add_config_entries(
        [
            ("DEBUG", configfile.bool_c_var(False, help_string="enable debug mode [%(default)s]", short_options="d", only_commandline=True)),
            ("DATABASE_DEBUG", configfile.bool_c_var(False, help_string="enable database debug mode [%(default)s]", only_commandline=True)),
            ("VERBOSE", configfile.int_c_var(0, help_string="set verbose level [%(default)d]", short_options="v", only_commandline=True)),
            ("CONTACT", configfile.bool_c_var(False, only_commandline=True, help_string="directly connect cluster-server on localhost [%(default)s]")),
            (
                "COMMAND", configfile.str_c_var(
                    "", short_options="c",  # choices=[""] + initat.cluster_server.modules.command_names, only_commandline=True,
                    help_string="command to execute",
                )
            ),
            (
                "BACKUP_DATABASE", configfile.bool_c_var(
                    False, only_commandline=True,
                    help_string="start backup of database immediately [%(default)s], only works in DEBUG mode"
                )
            ),
            (
                "OPTION_KEYS", configfile.array_c_var(
                    [],
                    short_options="D",
                    action="append",
                    only_commandline=True,
                    nargs="*",
                    help_string="optional key:value pairs (command dependent)"
                )
            ),
            (
                "SHOW_RESULT", configfile.bool_c_var(
                    False, only_commandline=True, help_string="show full XML result [%(default)s]"
                )
            ),
        ]
    )
    options = global_config.handle_commandline(
        *opt_args or [],
        description="{}, version is {}".format(
            prog_name,
            VERSION_STRING
        ),
        positional_arguments=False
    )
    # enable connection debugging
    settings.DEBUG = global_config["DATABASE_DEBUG"]
    settings.DATABASE_DEBUG = global_config["DATABASE_DEBUG"]
    run_code(options)
    return 0
