#!/usr/bin/python-init -Ot
# -*- coding: utf-8 -*-
#
# Copyright (C) 2013 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of host-monitoring
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

""" host-monitoring, main part """

# install reactor
import initat.host_monitoring.hm_twisted

import configfile
import process_tools
import sys

from initat.host_monitoring import hm_classes
from initat.host_monitoring.config import global_config
from initat.host_monitoring.client import client_code
from initat.host_monitoring.server import server_code
from initat.host_monitoring.relay import relay_code

try:
    from host_monitoring_version import VERSION_STRING
except ImportError:
    VERSION_STRING = "?.?"

def show_command_info():
    from initat.host_monitoring import modules
    if modules.IMPORT_ERRORS:
        print "Import errors:"
        for mod_name, com_name, error_str in modules.IMPORT_ERRORS:
            print "%-24s %-32s %s" % (mod_name.split(".")[-1], com_name, error_str)
    for com_name in sorted(modules.command_dict.keys()):
        cur_com = modules.command_dict[com_name]
        if isinstance(cur_com, hm_classes.hm_command):
            # print "\n".join(["", "command %s" % (com_name), ""])
            cur_com.parser.print_help()
    sys.exit(0)

def main():
    prog_name = global_config.name()
    global_config.add_config_entries([
        # ("MAILSERVER"          , configfile.str_c_var("localhost", info="Mail Server")),
        ("DEBUG"               , configfile.bool_c_var(False, help_string="enable debug mode [%(default)s]", short_options="d", only_commandline=True)),
        ("ZMQ_DEBUG"           , configfile.bool_c_var(False, help_string="enable 0MQ debugging [%(default)s]", only_commandline=True)),
        ("LOG_DESTINATION"     , configfile.str_c_var("uds:/var/lib/logging-server/py_log_zmq")),
        ("LOG_NAME"            , configfile.str_c_var(prog_name)),
        ("KILL_RUNNING"        , configfile.bool_c_var(True)),
        ("SHOW-COMMAND-INFO"   , configfile.bool_c_var(False, help_string="show command info", only_commandline=True)),
        ("BACKLOG_SIZE"        , configfile.int_c_var(5, help_string="backlog size for 0MQ sockets [%(default)d]")),
        ("VERBOSE"             , configfile.int_c_var(0, help_string="set verbose level [%(default)d]", short_options="v", only_commandline=True)),
        ("NICE_LEVEL"          , configfile.int_c_var(10, help_string="nice level [%(default)d]")),
        ("PID_NAME"            , configfile.str_c_var("%s/%s" % (prog_name,
                                                                 prog_name)))])
    if prog_name == "collserver":
        global_config.add_config_entries([
            ("COM_PORT"   , configfile.int_c_var(2001, info="listening Port", help_string="port to communicate [%(default)i]", short_options="p")),
            ("ENABLE_KSM" , configfile.bool_c_var(False, info="enable KSM", help_string="enable KSM [%(default)s]")),
            ("ENABLE_HUGE", configfile.bool_c_var(False, info="enable hugepages", help_string="enable hugepages [%(default)s]")),
            ("HUGEPAGES"  , configfile.int_c_var(50, info="percentage of memory to use for hugepages", help_string="hugepages percentage [%(default)d]"))
        ])
    elif prog_name == "collclient":
        global_config.add_config_entries([
            ("IDENTITY_STRING", configfile.str_c_var("collclient", help_string="identity string", short_options="i")),
            ("TIMEOUT"        , configfile.int_c_var(10, help_string="set timeout [%(default)d", only_commandline=True)),
            ("COM_PORT"       , configfile.int_c_var(2001, info="listening Port", help_string="port to communicate [%(default)i]", short_options="p")),
            ("HOST"           , configfile.str_c_var("localhost", help_string="host to connect to"))
        ])
    elif prog_name == "collrelay":
        global_config.add_config_entries([
            ("COM_PORT" , configfile.int_c_var(2004, info="listening Port", help_string="port to communicate [%(default)i]", short_options="p")),
            ("TIMEOUT"  , configfile.int_c_var(8, help_string="timeout for calls to distance machines [%(default)d]")),
            ("AUTOSENSE", configfile.bool_c_var(True, help_string="enable autosensing of 0MQ/TCP Clients [%(default)s]")),
            ])
    global_config.parse_file()
    options = global_config.handle_commandline(description="%s, version is %s" % (prog_name,
                                                                                  VERSION_STRING),
                                               add_writeback_option=prog_name in ["collserver", "collrelay"],
                                               positional_arguments=prog_name in ["collclient"],
                                               partial=prog_name in ["collclient"])
    global_config.write_file()
    if global_config["KILL_RUNNING"]:
        process_tools.kill_running_processes(exclude=configfile.get_manager_pid())
    if global_config["SHOW-COMMAND-INFO"]:
        show_command_info()
    if not options.DEBUG and prog_name in ["collserver", "collrelay"]:
        process_tools.become_daemon()
    elif prog_name in ["collserver", "collrelay"]:
        print "Debugging %s on %s" % (prog_name,
                                      process_tools.get_machine_name())
    if prog_name == "collserver":
        ret_state = server_code().loop()
    elif prog_name == "collrelay":
        ret_state = relay_code().loop()
    elif prog_name == "collclient":
        ret_state = client_code()
    else:
        print "Unknown operation mode %s" % (prog_name)
        ret_state = -1
    return ret_state
