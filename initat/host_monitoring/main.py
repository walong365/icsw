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

import sys

from initat.host_monitoring import hm_classes
from initat.host_monitoring.config import global_config
from initat.client_version import VERSION_STRING
from initat.tools import configfile, logging_tools


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
            ("SHOW_COMMAND_INFO", configfile.bool_c_var(False, help_string="show command info", only_commandline=True)),
            ("VERBOSE", configfile.int_c_var(0, help_string="set verbose level [%(default)d]", short_options="v", only_commandline=True)),
        ]
    )
    if prog_name == "collclient":
        global_config.add_config_entries(
            [
                ("IDENTITY_STRING", configfile.str_c_var("collclient", help_string="identity string", short_options="i")),
                ("TIMEOUT", configfile.int_c_var(10, help_string="set timeout [%(default)d", only_commandline=True)),
                ("COM_PORT", configfile.int_c_var(2001, info="listening Port", help_string="port to communicate [%(default)d]", short_options="p")),
                ("HOST", configfile.str_c_var("localhost", help_string="host to connect to")),
            ]
        )
    options = global_config.handle_commandline(
        description="{}, version is {}".format(
            prog_name,
            VERSION_STRING
        ),
        positional_arguments=prog_name in ["collclient"],
        partial=prog_name in ["collclient"],
    )
    if global_config["SHOW_COMMAND_INFO"]:
        show_command_info()
    ret_state = run_code(prog_name, global_config)
    return ret_state
