# -*- coding: utf-8 -*-
#
# Copyright (C) 2009-2014 Andreas Lang-Nevyjel (lang-nevyjel@init.at)
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of logging-server
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
""" logging server, central logging facility, main part """

from initat.logging_server import version
from initat.logging_server.config import global_config
from initat.logging_server.server import main_process
import configfile
import daemon
import os
import process_tools
import socket
import stat
import sys

def main():
    long_host_name, _mach_name = process_tools.get_fqdn()
    global_config.add_config_entries([
        ("MAILSERVER"          , configfile.str_c_var("localhost", help_string="mailserver for sending [%(default)s]", short_options="M")),
        ("DEBUG"               , configfile.bool_c_var(False, help_string="enable debug mode [%(default)s]", short_options="d", only_commandline=True)),
        ("ZMQ_DEBUG"           , configfile.bool_c_var(False, help_string="enable 0MQ debugging [%(default)s]", only_commandline=True)),
        ("FROM_NAME"           , configfile.str_c_var("pyerror")),
        ("FROM_ADDR"           , configfile.str_c_var(socket.getfqdn(), autoconf_exclude=True)),
        ("LOG_FORMAT"          , configfile.str_c_var("%(asctime)s : %(levelname)-5s (%(threadName)s.%(process)d) %(message)s")),
        ("DATE_FORMAT"         , configfile.str_c_var("%a %b %d %H:%M:%S %Y")),
        ("OUT_HANDLE"          , configfile.str_c_var("/var/lib/logging-server/py_out", autoconf_exclude=True)),
        ("ERR_HANDLE"          , configfile.str_c_var("/var/lib/logging-server/py_err", autoconf_exclude=True)),
        ("LOG_HANDLE"          , configfile.str_c_var("/var/lib/logging-server/py_log", autoconf_exclude=True)),
        ("LOG_DESTINATION"     , configfile.str_c_var("/var/log/cluster/logging-server", autoconf_exclude=True)),
        ("LISTEN_PORT"         , configfile.int_c_var(8011, autoconf_exclude=True)),
        ("STATISTICS_TIMER"    , configfile.int_c_var(600, help_string="how often we should log statistical information [%(default)i]")),
        ("SEND_ERROR_MAILS"    , configfile.bool_c_var(True, help_string="send error mails")),
        ("LOG_COMMANDS"        , configfile.bool_c_var(True, autoconf_exclude=True)),
        ("KILL_RUNNING"        , configfile.bool_c_var(True, autoconf_exclude=True)),
        ("EXCESS_LIMIT"        , configfile.int_c_var(1000, help_string="log lines per second to trigger excess_log [%(default)s]")),
        ("FORWARDER"           , configfile.str_c_var("", help_string="Address to forwared all logs to")),
        ("ONLY_FORWARD"        , configfile.bool_c_var(False, help_string="only forward (no local logging)")),
        ("MAX_AGE_FILES"       , configfile.int_c_var(365, help_string="max age for logfiles in days [%(default)i]", short_options="age")),
        ("USER"                , configfile.str_c_var("idlog", help_string="run as user [%(default)s]", short_options="u", autoconf_exclude=True)),
        ("GROUP"               , configfile.str_c_var("idg", help_string="run as group [%(default)s]", short_options="g", autoconf_exclude=True)),
        ("TO_ADDR"             , configfile.str_c_var("lang-nevyjel@init.at", help_string="mail address to send error-mails [%(default)s]")),
        ("LONG_HOST_NAME"      , configfile.str_c_var(long_host_name)),
        ("MAX_LINE_LENGTH"     , configfile.int_c_var(0, help_string="max line number size, 0 for unlimited [%(default)i]"))])
    global_config.parse_file()
    options = global_config.handle_commandline(
        description="logging server, version is {}".format(version.VERSION_STRING),
        add_auto_config_option=True
    )
    if not global_config.show_autoconfig():
        if global_config["KILL_RUNNING"]:
            process_tools.kill_running_processes()
        try:
            os.chmod("/var/lib/logging-server", stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)
            os.chmod("/var/log/cluster/sockets", stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)
        except:
            pass
        global_config.write_file()
        process_tools.renice()
        process_tools.change_user_group(global_config["USER"], global_config["GROUP"])
        if not options.DEBUG:
            with daemon.DaemonContext():
                sys.stdout = file(os.path.join(global_config["LOG_DESTINATION"], "log.stdout"), "a")
                sys.stderr = file(os.path.join(global_config["LOG_DESTINATION"], "log.stderr"), "a")
                main_process(options).loop()
            os.kill(os.getpid(), 9)
            # os._exit(0)
        else:
            print("Debugging logging-server")
            main_process(options).loop()
    return 0
