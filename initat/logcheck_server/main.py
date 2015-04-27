# -*- coding: utf-8 -*-
#
# Copyright (C) 2001-2008,2011-2015 Andreas Lang-Nevyjel
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

import sys
from initat.server_version import VERSION_STRING
from initat.tools import cluster_location
from initat.tools import config_tools
from initat.tools import configfile
from initat.tools import process_tools
from initat.logcheck_server.config import global_config
from initat.logcheck_server.server import server_process


SERVER_PORT = 8014


def main():
    long_host_name, mach_name = process_tools.get_fqdn()
    prog_name = global_config.name()
    global_config.add_config_entries(
        [
            ("ZMQ_DEBUG", configfile.bool_c_var(False, help_string="enable 0MQ debugging [%(default)s]", only_commandline=True)),
            ("PID_NAME", configfile.str_c_var(os.path.join(prog_name, prog_name))),
            ("KILL_RUNNING", configfile.bool_c_var(True, help_string="kill running instances [%(default)s]")),
            ("LOG_DESTINATION", configfile.str_c_var("uds:/var/lib/logging-server/py_log_zmq")),
            ("LOG_NAME", configfile.str_c_var(prog_name)),
            ("VERBOSE", configfile.int_c_var(0, help_string="set verbose level [%(default)d]", short_options="v", only_commandline=True)),
        ]
    )
    global_config.parse_file()
    options = global_config.handle_commandline(
        description="{}, version is {}".format(
            prog_name,
            VERSION_STRING
        ),
        add_writeback_option=True,
        positional_arguments=False
    )
    global_config.write_file()
    sql_info = config_tools.server_check(server_type="syslog_server")
    if not sql_info.effective_device:
        sql_info = config_tools.server_check(server_type="logcheck_server")
        if not sql_info.effective_device:
            print "not a syslog_server"
            sys.exit(5)
    global_config.add_config_entries([("SERVER_IDX", configfile.int_c_var(sql_info.effective_device.pk, database=False))])
    cluster_location.read_config_from_db(
        global_config,
        "syslog_server", [
            ("SERVER_SHORT_NAME", configfile.str_c_var(mach_name)),
            ("SYSLOG_DIR", configfile.str_c_var("/var/log/hosts")),
            ("COMPORT", configfile.int_c_var(SERVER_PORT)),
            ("KEEP_LOGS_UNCOMPRESSED", configfile.int_c_var(2)),
            ("KEEP_LOGS_TOTAL", configfile.int_c_var(30)),
            ("COMPRESS_BINARY", configfile.str_c_var("bzip2")),
            ("INITIAL_LOGCHECK", configfile.bool_c_var(False)),
            ("LOGSCAN_TIME", configfile.int_c_var(60, info="time in minutes between two logscan iterations"))
        ]
    )
    server_process(options).loop()
    configfile.terminate_manager()
    os._exit(0)
