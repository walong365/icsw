#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001-2009,2012-2014 Andreas Lang-Nevyjel
#
# this file is part of package-client
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
""" daemon to automatically install packages (.rpm, .deb) """

import os
import configfile
import process_tools
import sys

from initat.package_install.client.config import global_config, VERSION_STRING, P_SERVER_COM_PORT, PACKAGE_CLIENT_PORT, LF_NAME
from initat.package_install.client.server import server_process

def main():
    process_tools.delete_lockfile(LF_NAME, None, 0)
    prog_name = global_config.name()
    global_config.add_config_entries([
        ("PID_NAME"               , configfile.str_c_var("%s/%s" % (prog_name, prog_name))),
        ("DEBUG"                  , configfile.bool_c_var(False, help_string="enable debug mode [%(default)s]", short_options="d", only_commandline=True)),
        ("ZMQ_DEBUG"              , configfile.bool_c_var(False, help_string="enable 0MQ debugging [%(default)s]", only_commandline=True)),
        ("VERBOSE"                , configfile.int_c_var(0, help_string="set verbose level [%(default)d]", short_options="v", only_commandline=True)),
        ("KILL_RUNNING"           , configfile.bool_c_var(True)),
        ("POLL_INTERVALL"         , configfile.int_c_var(5, help_string="poll intervall")),
        ("EXIT_ON_FAIL"           , configfile.bool_c_var(False, help_string="exit on fail [%(default)s]")),
        ("COM_PORT"               , configfile.int_c_var(PACKAGE_CLIENT_PORT, help_string="node to bind to [%(default)d]")),
        ("SERVER_COM_PORT"        , configfile.int_c_var(P_SERVER_COM_PORT, help_string="server com port [%(default)d]")),
        ("LOG_DESTINATION"        , configfile.str_c_var("uds:/var/lib/logging-server/py_log_zmq")),
        ("LOG_NAME"               , configfile.str_c_var(prog_name)),
        ("VAR_DIR"                , configfile.str_c_var("/var/lib/cluster/package-client", help_string="location of var-directory [%(default)s]")),
        ("MODIFY_REPOS"           , configfile.bool_c_var(False, help_string="modify repository files")),
        ("PACKAGE_SERVER_FILE"    , configfile.str_c_var("/etc/packageserver", help_string="filename where packageserver location is stored [%(default)s]"))
    ])
    global_config.parse_file()
    _options = global_config.handle_commandline(
        description="%s, version is %s" % (
            prog_name,
            VERSION_STRING),
        add_writeback_option=True,
        add_exit_after_writeback_option=True,
        positional_arguments=False,
        partial=False)
    global_config.write_file()
    if _options.exit_after_writeback and _options.writeback:
        sys.exit(0)
    ps_file_name = global_config["PACKAGE_SERVER_FILE"]
    if not os.path.isfile(ps_file_name):
        try:
            file(ps_file_name, "w").write("localhost\n")
        except:
            print "error writing to %s: %s" % (ps_file_name, process_tools.get_except_info())
            sys.exit(5)
        else:
            pass
    try:
        global_config.add_config_entries([
            ("PACKAGE_SERVER", configfile.str_c_var(file(ps_file_name, "r").read().strip().split("\n")[0].strip())),
            ("VERSION", configfile.str_c_var(VERSION_STRING)),
        ])
    except:
        print "error reading from %s: %s" % (ps_file_name, process_tools.get_except_info())
        sys.exit(5)
    global_config.add_config_entries([("DEBIAN", configfile.bool_c_var(os.path.isfile("/etc/debian_version")))])
    if global_config["KILL_RUNNING"]:
        process_tools.kill_running_processes(exclude=configfile.get_manager_pid())
    process_tools.fix_directories(0, 0, [global_config["VAR_DIR"]])
    process_tools.renice()
    if not global_config["DEBUG"]:
        process_tools.become_daemon(mother_hook=process_tools.wait_for_lockfile, mother_hook_args=(LF_NAME, 5, 200))
    else:
        print "Debugging %s on %s" % (prog_name, process_tools.get_machine_name())
        # no longer needed
        # global_config["LOG_DESTINATION"] = "stdout"
    ret_code = server_process().loop()
    process_tools.delete_lockfile(LF_NAME, None, 0)
    sys.exit(ret_code)

if __name__ == "__main__":
    main()

