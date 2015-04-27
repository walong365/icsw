# -*- coding: utf-8 -*-
#
# Copyright (C) 2001-2008,2010-2015 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of meta-server
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
""" meta-server, main part """

import os
import socket
import sys

from initat.meta_server.config import global_config
from initat.meta_server.server import main_process
from initat.tools import configfile
from initat.tools import process_tools
from initat.client_version import VERSION_STRING
from initat.tools.io_stream_helper import io_stream


def main():
    long_host_name, _mach_name = process_tools.get_fqdn()
    global_config.add_config_entries(
        [
            ("MAILSERVER", configfile.str_c_var("localhost", help_string="Mailserver to use [%(default)s]")),
            ("DEBUG", configfile.bool_c_var(False, help_string="enable debug mode [%(default)s]", short_options="d", only_commandline=True)),
            ("ZMQ_DEBUG", configfile.bool_c_var(False, help_string="enable 0MQ debugging [%(default)s]", only_commandline=True)),
            (
                "COM_PORT",
                configfile.int_c_var(
                    8012,
                    info="listening Port",
                    help_string="port to communicate [%(default)i]", short_options="p", autoconf_exclude=True
                )
            ),
            ("LOG_DESTINATION", configfile.str_c_var("uds:/var/lib/logging-server/py_log", autoconf_exclude=True)),
            ("LOG_NAME", configfile.str_c_var("meta-server", autoconf_exclude=True)),
            ("MAIN_DIR", configfile.str_c_var("/var/lib/meta-server", autoconf_exclude=True)),
            ("FROM_NAME", configfile.str_c_var("meta-server", help_string="from address for info mails [%(default)s]")),
            ("FROM_ADDR", configfile.str_c_var(socket.getfqdn(), autoconf_exclude=True)),
            ("TO_ADDR", configfile.str_c_var("lang-nevyjel@init.at", help_string="mail address to send error-emails to [%(default)s]", short_options="t")),
            ("FAILED_CHECK_TIME", configfile.int_c_var(120, help_string="time in seconds to wait befor we do something [%(default)d]")),
            ("TRACK_CSW_MEMORY", configfile.bool_c_var(False, help_string="enable tracking of the memory usage of the CSW [%(default)s]", action="store_true")),
            ("MIN_CHECK_TIME", configfile.int_c_var(20, info="minimum time between two checks [%(default)s]", autoconf_exclude=True)),
            ("MIN_MEMCHECK_TIME", configfile.int_c_var(300, info="minimum time between two memory checks [%(default)s]", autoconf_exclude=True)),
            ("SERVER_FULL_NAME", configfile.str_c_var(long_host_name, autoconf_exclude=True)),
            ("PID_NAME", configfile.str_c_var("meta-server", autoconf_exclude=True)),
        ]
    )
    global_config.parse_file()
    options = global_config.handle_commandline(
        description="meta-server, version is {}".format(VERSION_STRING),
        add_auto_config_option=True,
    )
    if not global_config.show_autoconfig():
        global_config.write_file()
        main_process().loop()
        os._exit(0)
    return 0
