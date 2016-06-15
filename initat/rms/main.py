# Copyright (C) 2001-2009,2011-2016 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of rms-tools
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

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

import django
django.setup()

from initat.rms.functions import call_command
from initat.rms.config import global_config
from initat.rms.server import ServerProcess
from initat.server_version import VERSION_STRING
from initat.tools import cluster_location, configfile, process_tools, sge_license_tools


def main():
    long_host_name, _mach_name = process_tools.get_fqdn()
    prog_name = global_config.name()
    global_config.add_config_entries(
        [
            ("DEBUG", configfile.bool_c_var(False, help_string="enable debug mode [%(default)s]", short_options="d", only_commandline=True)),
            ("VERBOSE", configfile.int_c_var(0, help_string="set verbose level [%(default)d]", short_options="v", only_commandline=True)),
            (
                "FORCE_SCAN", configfile.bool_c_var(
                    False,
                    help_string="force initial scan of accounting file [%(default)s]",
                    action="store_true",
                    only_commandline=True
                )
            ),
        ]
    )
    _options = global_config.handle_commandline(
        description="{}, version is {}".format(
            prog_name,
            VERSION_STRING
        ),
        positional_arguments=False
    )
    sge_dict = {}
    _all_ok = True
    for v_name, v_src, v_default in [
        ("SGE_ROOT", "/etc/sge_root", "/opt/sge"),
        ("SGE_CELL", "/etc/sge_cell", "default")
    ]:
        if os.path.isfile(v_src):
            sge_dict[v_name] = file(v_src, "r").read().strip()
        else:
            _all_ok = False
            sge_dict[v_name] = ""
    if _all_ok:
        stat, sge_dict["SGE_ARCH"], _log_lines = call_command(
            "/{}/util/arch".format(sge_dict["SGE_ROOT"])
        )
        if stat:
            sge_dict["SGE_ARCH"] = ""
    else:
        sge_dict["SGE_ARCH"] = ""
    cluster_location.read_config_from_db(
        global_config,
        "rms_server",
        [
            ("CHECK_ITERATIONS", configfile.int_c_var(3)),
            ("RETRY_AFTER_CONNECTION_PROBLEMS", configfile.int_c_var(0)),
            ("FROM_ADDR", configfile.str_c_var("rms_server")),
            ("TO_ADDR", configfile.str_c_var("cluster@init.at")),
            ("SGE_ARCH", configfile.str_c_var(sge_dict["SGE_ARCH"])),
            ("SGE_ROOT", configfile.str_c_var(sge_dict["SGE_ROOT"])),
            ("SGE_CELL", configfile.str_c_var(sge_dict["SGE_CELL"])),
            ("FAIRSHARE_TREE_NODE_TEMPLATE", configfile.str_c_var("/{project}/{user}")),
            ("FAIRSHARE_TREE_DEFAULT_SHARES", configfile.int_c_var(1000)),
            ("TRACE_FAIRSHARE", configfile.bool_c_var(False)),
            ("CLEAR_ITERATIONS", configfile.int_c_var(1)),
            ("CHECK_ACCOUNTING_TIMEOUT", configfile.int_c_var(300)),
            ("LICENSE_BASE", configfile.str_c_var("/etc/sysconfig/licenses")),
            ("TRACK_LICENSES", configfile.bool_c_var(False)),
            ("TRACK_LICENSES_IN_DB", configfile.bool_c_var(False)),
            ("MODIFY_SGE_GLOBAL", configfile.bool_c_var(False)),
        ],
    )
    # check modify_sge_global flag and set filesystem flag accordingly
    sge_license_tools.handle_license_policy(global_config["LICENSE_BASE"], global_config["MODIFY_SGE_GLOBAL"])
    ServerProcess().loop()
    configfile.terminate_manager()
    # exit
    os._exit(0)
