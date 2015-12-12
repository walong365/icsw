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

from initat.server_version import VERSION_STRING
from initat.tools import cluster_location, configfile, process_tools
from initat.logcheck_server.config import global_config
from initat.logcheck_server.server import server_process


def main():
    long_host_name, mach_name = process_tools.get_fqdn()
    prog_name = global_config.name()
    global_config.add_config_entries(
        [
            ("DEBUG", configfile.bool_c_var(False, help_string="enable debug mode [%(default)s]", short_options="d", only_commandline=True)),
            ("VERBOSE", configfile.int_c_var(0, help_string="set verbose level [%(default)d]", short_options="v", only_commandline=True)),
        ]
    )
    options = global_config.handle_commandline(
        description="{}, version is {}".format(
            prog_name,
            VERSION_STRING
        ),
        positional_arguments=False
    )
    cluster_location.read_config_from_db(
        global_config,
        "syslog_server",
        [
            ("SERVER_SHORT_NAME", configfile.str_c_var(mach_name)),
            ("SYSLOG_DIR", configfile.str_c_var("/var/log/hosts")),
            ("KEEP_LOGS_UNCOMPRESSED", configfile.int_c_var(2)),
            ("KEEP_LOGS_TOTAL", configfile.int_c_var(30)),
            # maximum time in days to track logs
            ("LOGS_TRACKING_DAYS", configfile.int_c_var(4, info="time to track logs in days")),
            # cachesize for lineinfo (per file)
            ("LINECACHE_ENTRIES_PER_FILE", configfile.int_c_var(50, info="line cache per file")),
        ]
    )
    server_process(options).loop()
    configfile.terminate_manager()
    os._exit(0)
