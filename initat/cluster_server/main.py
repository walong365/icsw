# Copyright (C) 2001-2008,2012-2015 Andreas Lang-Nevyjel
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
""" cluster-server """

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

import django
django.setup()

from django.conf import settings
from initat.tools import cluster_location
from initat.tools import configfile
from initat.tools import process_tools
from initat.cluster_server.config import global_config

from initat.server_version import VERSION_STRING


def run_code(options):
    from initat.cluster_server.server import server_process
    server_process(options).loop()


def main():
    long_host_name, mach_name = process_tools.get_fqdn()
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
        description="{}, version is {}".format(
            prog_name,
            VERSION_STRING
        ),
        positional_arguments=False
    )
    # enable connection debugging
    settings.DEBUG = global_config["DATABASE_DEBUG"]
    cluster_location.read_config_from_db(
        global_config,
        "server",
        [
            ("IMAGE_SOURCE_DIR", configfile.str_c_var("/opt/cluster/system/images")),
            ("MAILSERVER", configfile.str_c_var("localhost")),
            ("FROM_NAME", configfile.str_c_var("quotawarning")),
            ("FROM_ADDR", configfile.str_c_var(long_host_name)),
            ("VERSION", configfile.str_c_var(VERSION_STRING, database=False)),
            ("QUOTA_ADMINS", configfile.str_c_var("cluster@init.at")),
            ("MONITOR_QUOTA_USAGE", configfile.bool_c_var(False, info="enabled quota usage tracking")),
            ("TRACK_ALL_QUOTAS", configfile.bool_c_var(False, info="also track quotas without limit")),
            ("QUOTA_CHECK_TIME_SECS", configfile.int_c_var(3600)),
            ("USER_MAIL_SEND_TIME", configfile.int_c_var(3600, info="time in seconds between two mails")),
            ("SERVER_FULL_NAME", configfile.str_c_var(long_host_name, database=False)),
            ("SERVER_SHORT_NAME", configfile.str_c_var(mach_name, database=False)),
            ("DATABASE_DUMP_DIR", configfile.str_c_var("/opt/cluster/share/db_backup")),
            ("DATABASE_KEEP_DAYS", configfile.int_c_var(30)),
            ("USER_SCAN_TIMER", configfile.int_c_var(7200, info="time in seconds between two user_scan runs")),
            ("NEED_ALL_NETWORK_BINDS", configfile.bool_c_var(True, info="raise an error if not all bind() calls are successfull")),
        ]
    )
    settings.DATABASE_DEBUG = global_config["DATABASE_DEBUG"]
    run_code(options)
    configfile.terminate_manager()
    return 0
