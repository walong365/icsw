# Copyright (C) 2001-2008,2012-2014 Andreas Lang-Nevyjel
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
from initat.cluster.backbone.models import LogSource
from io_stream_helper import io_stream
from initat.tools import cluster_location
from initat.tools import config_tools
from initat.tools import configfile
import daemon
from initat.tools import process_tools
import sys

from initat.server_version import VERSION_STRING

SERVER_PORT = 8004


def run_code(options):
    from initat.cluster_server.server import server_process
    server_process(options).loop()


def show_commands():
    import initat.cluster_server.modules
    _coms = initat.cluster_server.modules.command_names
    print("possible commands ({:d}):".format(len(_coms)))
    for _com in sorted(_coms):
        print("  {}".format(_com))


def main():
    global_config = configfile.configuration(process_tools.get_programm_name(), single_process_mode=True)
    long_host_name, mach_name = process_tools.get_fqdn()
    prog_name = global_config.name()
    global_config.add_config_entries([
        ("DEBUG", configfile.bool_c_var(False, help_string="enable debug mode [%(default)s]", short_options="d", only_commandline=True)),
        ("DATABASE_DEBUG", configfile.bool_c_var(False, help_string="enable database debug mode [%(default)s]", only_commandline=True)),
        ("ZMQ_DEBUG", configfile.bool_c_var(False, help_string="enable 0MQ debugging [%(default)s]", only_commandline=True)),
        ("PID_NAME", configfile.str_c_var("%s" % (prog_name))),
        ("LOG_DESTINATION", configfile.str_c_var("uds:/var/lib/logging-server/py_log_zmq")),
        ("LOG_NAME", configfile.str_c_var(prog_name)),
        ("VERBOSE", configfile.int_c_var(0, help_string="set verbose level [%(default)d]", short_options="v", only_commandline=True)),
        ("CONTACT", configfile.bool_c_var(False, only_commandline=True, help_string="directly connect cluster-server on localhost [%(default)s]")),
        (
            "COMMAND", configfile.str_c_var(
                "", short_options="c",  # choices=[""] + initat.cluster_server.modules.command_names, only_commandline=True,
                help_string="command to execute, for list of all commands use --show-commands"
            )
        ),
        (
            "SHOW_COMMANDS",
            configfile.bool_c_var(
                False, only_commandline=True, help_string="show all possible commands",
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
                [], short_options="D", only_commandline=True, nargs="*", help_string="optional key-value pairs (command dependent)"
            )
        ),
        (
            "SHOW_RESULT", configfile.bool_c_var(
                False, only_commandline=True, help_string="show full XML result [%(default)s]"
            )
        ),
    ])
    global_config.parse_file()
    options = global_config.handle_commandline(
        description="{}, version is {}".format(
            prog_name,
            VERSION_STRING
        ),
        add_writeback_option=True,
        positional_arguments=False
    )
    # enable connection debugging
    settings.DEBUG = global_config["DATABASE_DEBUG"]
    global_config.write_file()
    if global_config["SHOW_COMMANDS"]:
        show_commands()
        sys.exit(0)
    sql_info = config_tools.server_check(server_type="server")
    if not sql_info.effective_device:
        print "not a server"
        sys.exit(5)
    if sql_info.device:
        global_config.add_config_entries(
            [
                ("SERVER_IDX", configfile.int_c_var(sql_info.device.pk, database=False)),
                ("EFFECTIVE_DEVICE_IDX", configfile.int_c_var(sql_info.effective_device.pk, database=False)),
            ]
        )
    else:
        global_config.add_config_entries(
            [
                ("SERVER_IDX", configfile.int_c_var(0, database=False)),
                ("EFFECTIVE_DEVICE_IDX", configfile.int_c_var(0, database=False)),
            ]
        )
    if not global_config["SERVER_IDX"]:
        sys.stderr.write(" {} is no cluster-server, exiting...".format(long_host_name))
        sys.exit(5)
    global_config.add_config_entries(
        [
            (
                "LOG_SOURCE_IDX", configfile.int_c_var(
                    LogSource.new("cluster-server", device=sql_info.effective_device).pk
                )
            )
        ]
    )
    if not global_config["LOG_SOURCE_IDX"]:
        print "Too many LogSources with my id present, exiting..."
        sys.exit(5)
    # if global_config["KILL_RUNNING"] and not global_config["COMMAND"]:
    #    _log_lines = process_tools.kill_running_processes(prog_name + ".py")
    cluster_location.read_config_from_db(
        global_config,
        "server",
        [
            ("COM_PORT", configfile.int_c_var(SERVER_PORT)),
            ("IMAGE_SOURCE_DIR", configfile.str_c_var("/opt/cluster/system/images")),
            # ("UPDATE_SITE"          , configfile.str_c_var("http://www.initat.org/cluster/RPMs/")),
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
    # if not global_config["DEBUG"] and not global_config["COMMAND"]:
    #    with daemon.DaemonContext():
    global_config = configfile.get_global_config(prog_name, parent_object=global_config)
    run_code(options)
    configfile.terminate_manager()
    # exit
    os._exit(0)
