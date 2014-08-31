# Copyright (C) 2014 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# this file is part of discovery-server
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
""" discovery-server, main part """

import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

from initat.discovery_server.version import VERSION_STRING
from initat.discovery_server.config import global_config, SERVER_PORT
from initat.discovery_server.server import server_process
from initat.cluster.backbone.models import log_source
import cluster_location
import config_tools
import configfile
import process_tools


def main():
    long_host_name, _mach_name = process_tools.get_fqdn()
    prog_name = global_config.name()
    global_config.add_config_entries([
        ("DEBUG", configfile.bool_c_var(False, help_string="enable debug mode [%(default)s]", short_options="d", only_commandline=True)),
        ("ZMQ_DEBUG", configfile.bool_c_var(False, help_string="enable 0MQ debugging [%(default)s]", only_commandline=True)),
        ("PID_NAME", configfile.str_c_var(os.path.join(prog_name, prog_name))),
        ("KILL_RUNNING", configfile.bool_c_var(True, help_string="kill running instances [%(default)s]")),
        ("FORCE", configfile.bool_c_var(False, help_string="force running [%(default)s]", action="store_true", only_commandline=True)),
        ("CHECK", configfile.bool_c_var(False, help_string="only check for server status", action="store_true", only_commandline=True, short_options="C")),
        ("LOG_DESTINATION", configfile.str_c_var("uds:/var/lib/logging-server/py_log_zmq")),
        ("LOG_NAME", configfile.str_c_var(prog_name)),
        ("USER", configfile.str_c_var("iddis", help_string="user to run as [%(default)s]")),
        ("GROUP", configfile.str_c_var("idg", help_string="group to run as [%(default)s]")),
        ("GROUPS", configfile.array_c_var(["idg"])),
        ("LOG_DESTINATION", configfile.str_c_var("uds:/var/lib/logging-server/py_log_zmq")),
        ("LOG_NAME", configfile.str_c_var(prog_name)),
        ("VERBOSE", configfile.int_c_var(0, help_string="set verbose level [%(default)d]", short_options="v", only_commandline=True)),
        ("SERVER_PORT", configfile.int_c_var(SERVER_PORT, help_string="server port [%(default)d]")),
    ])
    global_config.parse_file()
    _options = global_config.handle_commandline(
        description="%s, version is %s" % (
            prog_name,
            VERSION_STRING),
        add_writeback_option=True,
        positional_arguments=False)
    global_config.write_file()
    sql_info = config_tools.server_check(server_type="discovery_server")
    if not sql_info.effective_device:
        print "not a discovery_server"
        sys.exit(5)
    else:
        global_config.add_config_entries([("SERVER_IDX", configfile.int_c_var(sql_info.device.pk, database=False))])
    if global_config["CHECK"]:
        sys.exit(0)
    if global_config["KILL_RUNNING"]:
        _log_lines = process_tools.kill_running_processes(prog_name + ".py", exclude=configfile.get_manager_pid())
    cluster_location.read_config_from_db(global_config, "discovery_server", [
    ])
    process_tools.renice()
    process_tools.fix_directories(global_config["USER"], global_config["GROUP"], ["/var/run/discovery-server"])
    global_config.set_uid_gid(global_config["USER"], global_config["GROUP"])
    process_tools.change_user_group(global_config["USER"], global_config["GROUP"])
    if not global_config["DEBUG"]:
        process_tools.become_daemon()
        process_tools.set_handles(
            {
                "out": (1, "discovery-server.out"),
                "err": (0, "/var/lib/logging-server/py_err")
            }
        )
    else:
        print "Debugging discovery-server on %s" % (long_host_name)
    ret_code = server_process().loop()
    sys.exit(ret_code)
