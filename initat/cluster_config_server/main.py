#!/usr/bin/python-init -Ot default
#
# Copyright (C) 2001-2008,2012-2015 Andreas Lang-Nevyjel, init.at
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

import django
django.setup()

from initat.server_version import VERSION_STRING
from initat.cluster_config_server.config import global_config, SERVER_PORT, NCS_PORT
from initat.cluster.backbone.models import LogSource
from initat.tools import cluster_location
from initat.tools import config_tools
from initat.tools import configfile
from initat.tools import process_tools


def run_code():
    from initat.cluster_config_server.server import server_process
    server_process().loop()


def main():
    long_host_name, _mach_name = process_tools.get_fqdn()
    prog_name = global_config.name()
    global_config.add_config_entries([
        ("DEBUG", configfile.bool_c_var(False, help_string="enable debug mode [%(default)s]", short_options="d", only_commandline=True)),
        ("ZMQ_DEBUG", configfile.bool_c_var(False, help_string="enable 0MQ debugging [%(default)s]", only_commandline=True)),
        ("PID_NAME", configfile.str_c_var(os.path.join(prog_name, prog_name))),
        ("LOG_DESTINATION", configfile.str_c_var("uds:/var/lib/logging-server/py_log_zmq")),
        ("LOG_NAME", configfile.str_c_var(prog_name)),
        ("USER", configfile.str_c_var("idccs", help_string="user to run as [%(default)s]")),
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
        positional_arguments=False
    )
    global_config.write_file()
    sql_info = config_tools.server_check(server_type="config_server")
    if not sql_info.effective_device:
        print "not a config_server"
        sys.exit(5)
    cluster_location.read_config_from_db(global_config, "config_server", [
        ("TFTP_DIR", configfile.str_c_var("/tftpboot")),
        ("MONITORING_PORT", configfile.int_c_var(NCS_PORT)),
        ("LOCALHOST_IS_EXCLUSIVE", configfile.bool_c_var(True)),
        ("HOST_CACHE_TIME", configfile.int_c_var(10 * 60)),
        ("WRITE_REDHAT_HWADDR_ENTRY", configfile.bool_c_var(True)),
        ("ADD_NETDEVICE_LINKS", configfile.bool_c_var(False)),
    ])
    global_config.add_config_entries(
        [
            ("CONFIG_DIR", configfile.str_c_var(os.path.join(global_config["TFTP_DIR"], "config"))),
            ("IMAGE_DIR", configfile.str_c_var(os.path.join(global_config["TFTP_DIR"], "images"))),
            ("KERNEL_DIR", configfile.str_c_var(os.path.join(global_config["TFTP_DIR"], "kernels"))),
            (
                "LOG_SOURCE_IDX",
                configfile.int_c_var(LogSource.new("config-server", device=sql_info.effective_device).pk)
            )
        ]
    )
    run_code()
    configfile.terminate_manager()
    # exit
    os._exit(0)
