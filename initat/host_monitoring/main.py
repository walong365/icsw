# -*- coding: utf-8 -*-
#
# Copyright (C) 2013-2015 Andreas Lang-Nevyjel
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

import os
import sys

from initat.host_monitoring import hm_classes
from initat.host_monitoring.config import global_config
from initat.client_version import VERSION_STRING
from initat.tools import configfile
from initat.tools import logging_tools


def show_command_info():
    from initat.host_monitoring import modules
    if modules.IMPORT_ERRORS:
        print("Import errors:")
        for mod_name, com_name, error_str in modules.IMPORT_ERRORS:
            print("%-24s %-32s %s" % (mod_name.split(".")[-1], com_name, error_str))
    valid_names = sorted(modules.command_dict.keys())
    for mod in modules.module_list:
        c_names = [name for name in valid_names if modules.command_dict[name].module == mod]
        local_valid_names = []
        for com_name in c_names:
            cur_com = modules.command_dict[com_name]
            if isinstance(cur_com, hm_classes.hm_command):
                local_valid_names.append(com_name)
        local_valid_names = sorted(local_valid_names)
        print(
            "\n{}\n{}\n{}\n{}".format(
                "-" * 50,
                unicode(mod),
                "{} defined: {}".format(
                    logging_tools.get_plural("command", len(local_valid_names)),
                    ", ".join(local_valid_names),
                ) if local_valid_names else "no commands defined",
                "-" * 50,
            )
        )
        for com_name in local_valid_names:
            cur_com = modules.command_dict[com_name]
            print("\ncommand {}:\n".format(com_name))
            cur_com.parser.print_help()
            print("-" * 10)
    sys.exit(0)


def run_code(prog_name, global_config):
    if prog_name in ["collserver"]:
        from initat.host_monitoring.server import server_code
        ret_state = server_code().loop()
    elif prog_name in ["collrelay"]:
        from initat.host_monitoring.relay import relay_code
        ret_state = relay_code().loop()
    elif prog_name == "collclient":
        from initat.host_monitoring.client import client_code
        ret_state = client_code(global_config)
    else:
        print("Unknown mode {}".format(prog_name))
        ret_state = -1
    return ret_state


def main():
    prog_name = global_config.name()
    global_config.add_config_entries(
        [
            ("DEBUG", configfile.bool_c_var(False, help_string="enable debug mode [%(default)s]", short_options="d", only_commandline=True)),
            ("ZMQ_DEBUG", configfile.bool_c_var(False, help_string="enable 0MQ debugging [%(default)s]", only_commandline=True)),
            ("LOG_DESTINATION", configfile.str_c_var("uds:/var/lib/logging-server/py_log_zmq", autoconf_exclude=True)),
            ("LOG_NAME", configfile.str_c_var(prog_name, autoconf_exclude=True)),
            ("KILL_RUNNING", configfile.bool_c_var(True, autoconf_exclude=True)),
            ("SHOW_COMMAND_INFO", configfile.bool_c_var(False, help_string="show command info", only_commandline=True)),
            ("BACKLOG_SIZE", configfile.int_c_var(5, help_string="backlog size for 0MQ sockets [%(default)d]")),
            ("VERBOSE", configfile.int_c_var(0, help_string="set verbose level [%(default)d]", short_options="v", only_commandline=True)),
            ("OBJGRAPH", configfile.bool_c_var(False, help_string="enable objgraph [%(default)c]", only_commandline=True)),
            ("NICE_LEVEL", configfile.int_c_var(10, help_string="nice level [%(default)d]")),
            (
                "PID_NAME",
                configfile.str_c_var(
                    os.path.join(
                        prog_name,
                        prog_name
                    ),
                    autoconf_exclude=True
                )
            )
        ]
    )
    if prog_name in ["collserver"]:
        global_config.add_config_entries(
            [
                (
                    "COM_PORT",
                    configfile.int_c_var(
                        2001, info="listening Port", help_string="port to communicate [%(default)d]", short_options="p", autoconf_exclude=True
                    )
                ),
                ("ENABLE_KSM", configfile.bool_c_var(False, info="enable KSM", help_string="enable KSM [%(default)s]")),
                ("ENABLE_HUGE", configfile.bool_c_var(False, info="enable hugepages", help_string="enable hugepages [%(default)s]")),
                ("HUGEPAGES", configfile.int_c_var(50, info="percentage of memory to use for hugepages", help_string="hugepages percentage [%(default)d]")),
                (
                    "NO_INOTIFY",
                    configfile.bool_c_var(
                        False,
                        info="disable inotify process",
                        help_string="disable inotify proces [%(default)s]", action="store_true"
                    )
                ),
                (
                    "AFFINITY",
                    configfile.bool_c_var(
                        False, info="enable process_affinity tools",
                        help_string="enables pinning of processes to certain cores", action="store_true"
                    )
                ),
                (
                    "TRACK_IPMI",
                    configfile.bool_c_var(
                        False, info="enable tracking of IPMI sensors",
                        help_string="enable tracking of IPMI sensor data", action="store_true"
                    )
                ),
                (
                    "INOTIFY_IDLE_TIMEOUT",
                    configfile.int_c_var(
                        5,
                        info="seconds to wait between two inotify() checks", help_string="loop timer for inotify_check [%(default)d]"
                    )
                ),
                ("RUN_ARGUS", configfile.bool_c_var(False, help_string="enable argus [%(default)s]")),
                ("MACHVECTOR_POLL_COUNTER", configfile.int_c_var(30, help_string="machvector poll counter")),
            ]
        )
    elif prog_name == "collclient":
        global_config.add_config_entries(
            [
                ("IDENTITY_STRING", configfile.str_c_var("collclient", help_string="identity string", short_options="i")),
                ("TIMEOUT", configfile.int_c_var(10, help_string="set timeout [%(default)d", only_commandline=True)),
                ("COM_PORT", configfile.int_c_var(2001, info="listening Port", help_string="port to communicate [%(default)d]", short_options="p")),
                ("HOST", configfile.str_c_var("localhost", help_string="host to connect to")),
            ]
        )
    elif prog_name in ["collrelay"]:
        global_config.add_config_entries(
            [
                ("COM_PORT", configfile.int_c_var(2004, info="listening Port", help_string="port to communicate [%(default)d]", short_options="p")),
                ("TIMEOUT", configfile.int_c_var(8, help_string="timeout for calls to distance machines [%(default)d]")),
                ("AUTOSENSE", configfile.bool_c_var(True, help_string="enable autosensing of 0MQ/TCP Clients [%(default)s]")),
                ("FORCERESOLVE", configfile.bool_c_var(False, action="store_true", info="enable automatic resolving (dangerous) [%(default)s]")),
            ]
        )
    if prog_name in ["collrelay", "collserver"]:
        pass
    global_config.parse_file()
    options = global_config.handle_commandline(
        description="{}, version is {}".format(
            prog_name,
            VERSION_STRING
        ),
        add_writeback_option=prog_name in ["collserver", "collrelay"],
        positional_arguments=prog_name in ["collclient"],
        partial=prog_name in ["collclient"],
        add_auto_config_option=prog_name in ["collserver"],
    )
    if global_config["SHOW_COMMAND_INFO"]:
        show_command_info()
    if global_config.show_autoconfig():
        ret_state = 0
    else:
        global_config.write_file()
        ret_state = run_code(prog_name, global_config)
    return ret_state
