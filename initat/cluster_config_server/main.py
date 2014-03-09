#!/usr/bin/python-init -OtW default
#
# Copyright (C) 2001-2008,2012-2014 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# this file is part of cluster-config-server
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
""" cluster-config-server, main part """

import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

from initat.cluster_config_server.cluster_config_server_version import VERSION_STRING
from initat.cluster_config_server.config import global_config, SERVER_PUB_PORT, SERVER_PULL_PORT, NCS_PORT
from initat.cluster_config_server.server import server_process
from initat.cluster.backbone.models import log_source
import cluster_location
import config_tools
import configfile
import process_tools

def main():
    long_host_name, _mach_name = process_tools.get_fqdn()
    prog_name = global_config.name()
    global_config.add_config_entries([
        ("DEBUG"               , configfile.bool_c_var(False, help_string="enable debug mode [%(default)s]", short_options="d", only_commandline=True)),
        ("ZMQ_DEBUG"           , configfile.bool_c_var(False, help_string="enable 0MQ debugging [%(default)s]", only_commandline=True)),
        ("PID_NAME"            , configfile.str_c_var(os.path.join(prog_name, prog_name))),
        ("KILL_RUNNING"        , configfile.bool_c_var(True, help_string="kill running instances [%(default)s]")),
        ("FORCE"               , configfile.bool_c_var(False, help_string="force running [%(default)s]", action="store_true", only_commandline=True)),
        ("CHECK"               , configfile.bool_c_var(False, help_string="only check for server status", action="store_true", only_commandline=True, short_options="C")),
        ("LOG_DESTINATION"     , configfile.str_c_var("uds:/var/lib/logging-server/py_log_zmq")),
        ("LOG_NAME"            , configfile.str_c_var(prog_name)),
        ("USER"                , configfile.str_c_var("idccs", help_string="user to run as [%(default)s]")),
        ("GROUP"               , configfile.str_c_var("idg", help_string="group to run as [%(default)s]")),
        ("GROUPS"              , configfile.array_c_var(["idg"])),
        ("LOG_DESTINATION"     , configfile.str_c_var("uds:/var/lib/logging-server/py_log_zmq")),
        ("LOG_NAME"            , configfile.str_c_var(prog_name)),
        ("VERBOSE"             , configfile.int_c_var(0, help_string="set verbose level [%(default)d]", short_options="v", only_commandline=True)),
        ("SERVER_PUB_PORT"     , configfile.int_c_var(SERVER_PUB_PORT, help_string="server publish port [%(default)d]")),
        ("SERVER_PULL_PORT"    , configfile.int_c_var(SERVER_PULL_PORT, help_string="server pull port [%(default)d]")),
    ])
    global_config.parse_file()
    _options = global_config.handle_commandline(
        description="%s, version is %s" % (
            prog_name,
            VERSION_STRING),
        add_writeback_option=True,
        positional_arguments=False)
    global_config.write_file()
    sql_info = config_tools.server_check(server_type="config_server")
    if not sql_info.effective_device:
        print "not a config_server"
        sys.exit(5)
    if global_config["CHECK"]:
        sys.exit(0)
    if global_config["KILL_RUNNING"]:
        _log_lines = process_tools.kill_running_processes(prog_name + ".py", exclude=configfile.get_manager_pid())
    cluster_location.read_config_from_db(global_config, "config_server", [
        ("TFTP_DIR"                  , configfile.str_c_var("/tftpboot")),
        ("MONITORING_PORT"           , configfile.int_c_var(NCS_PORT)),
        ("LOCALHOST_IS_EXCLUSIVE"    , configfile.bool_c_var(True)),
        ("HOST_CACHE_TIME"           , configfile.int_c_var(10 * 60)),
        ("WRITE_REDHAT_HWADDR_ENTRY" , configfile.bool_c_var(True)),
        ("ADD_NETDEVICE_LINKS"       , configfile.bool_c_var(False)),
    ])
    global_config.add_config_entries([
        ("CONFIG_DIR" , configfile.str_c_var("%s/%s" % (global_config["TFTP_DIR"], "config"))),
        ("IMAGE_DIR"  , configfile.str_c_var("%s/%s" % (global_config["TFTP_DIR"], "images"))),
        ("KERNEL_DIR" , configfile.str_c_var("%s/%s" % (global_config["TFTP_DIR"], "kernels")))])
    global_config.add_config_entries([("LOG_SOURCE_IDX", configfile.int_c_var(log_source.create_log_source_entry("config-server", "Cluster ConfigServer", device=sql_info.effective_device).pk))])
    process_tools.renice()
    process_tools.fix_directories(global_config["USER"], global_config["GROUP"], ["/var/run/cluster-config-server"])
    global_config.set_uid_gid(global_config["USER"], global_config["GROUP"])
    process_tools.change_user_group(global_config["USER"], global_config["GROUP"])
    if not global_config["DEBUG"]:
        process_tools.become_daemon()
        process_tools.set_handles({"out" : (1, "cluster-config-server.out"),
                                   "err" : (0, "/var/lib/logging-server/py_err")})
    else:
        print "Debugging cluster-config-server on %s" % (long_host_name)
    ret_code = server_process().loop()
    sys.exit(ret_code)

if __name__ == "__main__":
    main()

