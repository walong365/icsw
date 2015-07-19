# Copyright (C) 2007-2009,2013-2015 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file belongs to the rrd-server package
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
""" rrd-grapher for graphing rrd-data """

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

import django
django.setup()

from django.conf import settings
from initat.cluster.backbone.models import LogSource
from initat.rrd_grapher.config import global_config, SERVER_COM_PORT
from initat.server_version import VERSION_STRING
from initat.tools import config_tools
from initat.tools import configfile
from initat.tools import process_tools
import sys


def run_code():
    from initat.rrd_grapher.server import server_process
    server_process().loop()


def main():
    long_host_name, _mach_name = process_tools.get_fqdn()
    prog_name = global_config.name()
    global_config.add_config_entries(
        [
            ("DEBUG", configfile.bool_c_var(False, help_string="enable debug mode [%(default)s]", short_options="d", only_commandline=True)),
            ("VERBOSE", configfile.int_c_var(0, help_string="verbose lewel [%(default)s]", only_commandline=True)),
            ("CHECK", configfile.bool_c_var(False, short_options="C", help_string="only check for server status", action="store_true", only_commandline=True)),
            ("USER", configfile.str_c_var("idrrd", help_string="user to run as [%(default)s")),
            ("GROUP", configfile.str_c_var("idg", help_string="group to run as [%(default)s]")),
            ("GROUPS", configfile.array_c_var([])),
            ("LOG_DESTINATION", configfile.str_c_var("uds:/var/lib/logging-server/py_log_zmq")),
            ("LOG_NAME", configfile.str_c_var(prog_name)),
            ("PID_NAME", configfile.str_c_var(
                os.path.join(
                    prog_name,
                    prog_name
                )
            )),
            ("COM_PORT", configfile.int_c_var(SERVER_COM_PORT, database=True)),
            ("SERVER_PATH", configfile.bool_c_var(False, help_string="set server_path to store RRDs [%(default)s]", only_commandline=True)),
            ("VERBOSE", configfile.int_c_var(0, help_string="set verbose level [%(default)d]", short_options="v", only_commandline=True)),
            ("RRD_DIR", configfile.str_c_var("/var/cache/rrd", help_string="directory of rrd-files on local disc", database=True)),
            ("RRD_CACHED_DIR", configfile.str_c_var("/var/run/rrdcached", database=True)),
            ("RRD_CACHED_SOCKET", configfile.str_c_var("/var/run/rrdcached/rrdcached.sock", database=True)),
            ("GRAPHCONFIG_BASE", configfile.str_c_var("/opt/cluster/share/rrd_grapher/", help_string="name of colortable file")),
            ("COMPOUND_DIR", configfile.str_c_var("/opt/cluster/share/rrd_grapher/", help_string="include dir for compound XMLs")),
        ]
    )
    global_config.parse_file()
    _options = global_config.handle_commandline(
        description="{}, version is {}".format(
            prog_name,
            VERSION_STRING),
        add_writeback_option=True,
        positional_arguments=False)
    global_config.write_file()
    sql_info = config_tools.server_check(server_type="rrd_server")
    if not sql_info.effective_device:
        print "not an rrd_server"
        sys.exit(5)
    else:
        global_config.add_config_entries([("SERVER_IDX", configfile.int_c_var(sql_info.effective_device.pk, database=False))])
    if global_config["CHECK"]:
        sys.exit(0)
    global_config.add_config_entries(
        [
            (
                "LOG_SOURCE_IDX",
                configfile.int_c_var(
                    LogSource.new(
                        "rrd-grapher", device=sql_info.effective_device
                    ).pk
                )
            ),
            (
                "GRAPH_ROOT_DEBUG",
                configfile.str_c_var(
                    os.path.abspath(
                        os.path.join(
                            settings.STATIC_ROOT_DEBUG,
                            "graphs"
                        )
                    ),
                    database=True
                )
            ),
            (
                "GRAPH_ROOT",
                configfile.str_c_var(
                    os.path.abspath(
                        os.path.join(
                            settings.STATIC_ROOT_DEBUG if global_config["DEBUG"] else settings.STATIC_ROOT,
                            "graphs"
                        )
                    ),
                    database=True
                )
            ),
        ]
    )
    if global_config["RRD_CACHED_SOCKET"] == "/var/run/rrdcached.sock":
        global_config["RRD_CACHED_SOCKET"] = os.path.join(global_config["RRD_CACHED_DIR"], "rrdcached.sock")
    run_code()
    configfile.terminate_manager()
    sys.exit(0)
