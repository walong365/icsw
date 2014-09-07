# -*- coding: utf-8 -*-
#
# Copyright (C) 2001-2008,2011-2014 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of logcheck-server
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
""" logcheck-server (to be run on a syslog_server) """

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

import django
django.setup()

from initat.logcheck_server.version import VERSION_STRING
from io_stream_helper import io_stream
import cluster_location
import config_tools
import configfile
import daemon
import process_tools
import sys

SERVER_PORT = 8014


def run_code(options):
    from initat.logcheck_server.server import server_process
    server_process(options).loop()


def main():
    global_config = configfile.configuration(process_tools.get_programm_name(), single_process_mode=True)
    long_host_name, mach_name = process_tools.get_fqdn()
    prog_name = global_config.name()
    global_config.add_config_entries([
        ("DEBUG", configfile.bool_c_var(False, help_string="enable debug mode [%(default)s]", short_options="d", only_commandline=True)),
        ("ZMQ_DEBUG", configfile.bool_c_var(False, help_string="enable 0MQ debugging [%(default)s]", only_commandline=True)),
        ("PID_NAME", configfile.str_c_var(os.path.join(prog_name, prog_name))),
        ("KILL_RUNNING", configfile.bool_c_var(True, help_string="kill running instances [%(default)s]")),
        ("FORCE", configfile.bool_c_var(False, help_string="force running [%(default)s]", action="store_true", only_commandline=True)),
        ("CHECK", configfile.bool_c_var(False, help_string="only check for server status", action="store_true", only_commandline=True, short_options="C")),
        ("LOG_DESTINATION", configfile.str_c_var("uds:/var/lib/logging-server/py_log_zmq")),
        ("USER", configfile.str_c_var("idlog", help_string="user to run as [%(default)s]")),
        ("GROUP", configfile.str_c_var("idg", help_string="group to run as [%(default)s]")),
        ("LOG_NAME", configfile.str_c_var(prog_name)),
        ("VERBOSE", configfile.int_c_var(0, help_string="set verbose level [%(default)d]", short_options="v", only_commandline=True)),
    ])
    global_config.parse_file()
    options = global_config.handle_commandline(
        description="%s, version is %s" % (
            prog_name,
            VERSION_STRING
        ),
        add_writeback_option=True,
        positional_arguments=False
    )
    global_config.write_file()
    sql_info = config_tools.server_check(server_type="syslog_server")
    if not sql_info.effective_device:
        print "not a syslog_server"
        sys.exit(5)
    if global_config["CHECK"]:
        sys.exit(0)
    if sql_info.device:
        global_config.add_config_entries([("SERVER_IDX", configfile.int_c_var(sql_info.effective_device.pk, database=False))])
    else:
        global_config.add_config_entries([("SERVER_IDX", configfile.int_c_var(0, database=False))])
    if not global_config["SERVER_IDX"] and not global_config["FORCE"]:
        sys.stderr.write(" %s is no syslog-server, exiting..." % (long_host_name))
        sys.exit(5)
    cluster_location.read_config_from_db(global_config, "syslog_server", [
        ("SERVER_SHORT_NAME", configfile.str_c_var(mach_name)),
        ("SYSLOG_DIR", configfile.str_c_var("/var/log/hosts")),
        ("COMPORT", configfile.int_c_var(SERVER_PORT)),
        ("KEEP_LOGS_UNCOMPRESSED", configfile.int_c_var(2)),
        ("KEEP_LOGS_TOTAL", configfile.int_c_var(30)),
        ("INITIAL_LOGCHECK", configfile.bool_c_var(False)),
        ("LOGSCAN_TIME", configfile.int_c_var(60, info="time in minutes between two logscan iterations"))
    ])
    if global_config["KILL_RUNNING"]:
        _log_lines = process_tools.kill_running_processes(prog_name + ".py")
    process_tools.renice()
    # need root rights to change syslog and log rotation
    # global_config.set_uid_gid(global_config["USER"], global_config["GROUP"])
    # process_tools.change_user_group(global_config["USER"], global_config["GROUP"])
    if not global_config["DEBUG"]:
        with daemon.DaemonContext():
            global_config = configfile.get_global_config(prog_name, parent_object=global_config)
            sys.stdout = io_stream("/var/lib/logging-server/py_log_zmq")
            sys.stderr = io_stream("/var/lib/logging-server/py_err_zmq")
            run_code(options)
            configfile.terminate_manager()
    else:
        print("Debugging logcheck_server")
        global_config = configfile.get_global_config(prog_name, parent_object=global_config)
        run_code(options)
    sys.exit(0)
