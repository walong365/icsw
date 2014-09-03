# Copyright (C) 2001-2009,2011-2014 Andreas Lang-Nevyjel, init.at
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
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

import django
django.setup()

from initat.rms.config import global_config, COM_PORT
from initat.rms.rms_server_version import VERSION_STRING
from initat.rms.rmsmon import call_command
from initat.rms.server import server_process
import cluster_location
import config_tools
import configfile
import process_tools
import sge_license_tools


def main():
    long_host_name, _mach_name = process_tools.get_fqdn()
    prog_name = global_config.name()
    global_config.add_config_entries([
        ("DEBUG", configfile.bool_c_var(False, help_string="enable debug mode [%(default)s]", short_options="d", only_commandline=True)),
        ("ZMQ_DEBUG", configfile.bool_c_var(False, help_string="enable 0MQ debugging [%(default)s]", only_commandline=True)),
        ("PID_NAME", configfile.str_c_var(os.path.join(prog_name, prog_name))),
        ("KILL_RUNNING", configfile.bool_c_var(True, help_string="kill running instances [%(default)s]")),
        ("CHECK", configfile.bool_c_var(False, short_options="C", help_string="only check for server status", action="store_true", writeback=False)),
        ("USER", configfile.str_c_var("sge", help_string="user to run as [%(default)s")),
        ("GROUP", configfile.str_c_var("sge", help_string="group to run as [%(default)s]")),
        ("GROUPS", configfile.array_c_var(["idg"])),
        ("FORCE", configfile.bool_c_var(False, help_string="force running ", action="store_true", only_commandline=True)),
        ("LOG_DESTINATION", configfile.str_c_var("uds:/var/lib/logging-server/py_log_zmq")),
        ("LOG_NAME", configfile.str_c_var(prog_name)),
        ("VERBOSE", configfile.int_c_var(0, help_string="set verbose level [%(default)d]", short_options="v", only_commandline=True)),
        ("FORCE_SCAN", configfile.bool_c_var(
            False, help_string="force initial scan of accounting file [%(default)s]", action="store_true",
            only_commandline=True)),
    ])
    global_config.parse_file()
    _options = global_config.handle_commandline(
        description="%s, version is %s" % (
            prog_name,
            VERSION_STRING),
        add_writeback_option=True,
        positional_arguments=False)
    global_config.write_file()
    # check for newer rms-server
    sql_s_info = config_tools.server_check(server_type="rms_server")
    if not sql_s_info.effective_device:
        sql_s_info = config_tools.server_check(server_type="sge_server")
        if not sql_s_info.effective_device:
            if global_config["FORCE"]:
                global_config.add_config_entries([("DUMMY_RUN", configfile.bool_c_var(True))])
            else:
                sys.stderr.write(" %s is no sge-server, exiting..." % (long_host_name))
                sys.exit(5)
        else:
            # config is sge_server
            global_config.add_config_entries([("DUMMY_RUN", configfile.bool_c_var(False))])
    else:
        # config is rms_server
        global_config.add_config_entries([("DUMMY_RUN", configfile.bool_c_var(False))])
    if global_config["CHECK"]:
        sys.exit(0)
    if not global_config["DUMMY_RUN"]:
        global_config.add_config_entries([("SERVER_IDX", configfile.int_c_var(sql_s_info.effective_device.pk, database=False))])
        # FIXME
    if global_config["KILL_RUNNING"]:
        _log_lines = process_tools.kill_running_processes(prog_name + ".py", exclude=configfile.get_manager_pid())
    sge_dict = {}
    for v_name, v_src, v_default in [
        ("SGE_ROOT", "/etc/sge_root", "/opt/sge"),
        ("SGE_CELL", "/etc/sge_cell", "default")
    ]:
        if os.path.isfile(v_src):
            sge_dict[v_name] = file(v_src, "r").read().strip()
        else:
            if global_config["FORCE"]:
                sge_dict[v_name] = v_default
            else:
                print "error: Cannot read %s from file %s, exiting..." % (v_name, v_src)
                sys.exit(2)
    stat, sge_dict["SGE_ARCH"], _log_lines = call_command("/{}/util/arch".format(sge_dict["SGE_ROOT"]))
    if stat:
        if global_config["FORCE"]:
            sge_dict["SGE_ARCH"] = "lx26_amd64"
        else:
            print "error Cannot evaluate SGE_ARCH"
            sys.exit(1)
    cluster_location.read_config_from_db(
        global_config,
        "rms_server",
        [
            ("CHECK_ITERATIONS", configfile.int_c_var(3)),
            ("COM_PORT", configfile.int_c_var(COM_PORT)),
            ("RETRY_AFTER_CONNECTION_PROBLEMS", configfile.int_c_var(0)),
            ("FROM_ADDR", configfile.str_c_var("sge_server")),
            ("TO_ADDR", configfile.str_c_var("lang-nevyjel@init.at")),
            ("SGE_ARCH", configfile.str_c_var(sge_dict["SGE_ARCH"])),  # , fixed=True)),
            ("SGE_ROOT", configfile.str_c_var(sge_dict["SGE_ROOT"])),  # , fixed=True)),
            ("SGE_CELL", configfile.str_c_var(sge_dict["SGE_CELL"])),  # , fixed=True)),
            ("MONITOR_JOBS", configfile.bool_c_var(True)),
            ("TRACE_FAIRSHARE", configfile.bool_c_var(False)),
            ("STRICT_MODE", configfile.bool_c_var(False)),
            ("APPEND_SERIAL_COMPLEX", configfile.bool_c_var(True)),
            ("CLEAR_ITERATIONS", configfile.int_c_var(1)),
            ("CHECK_ACCOUNTING_TIMEOUT", configfile.int_c_var(300)),
            ("LICENSE_BASE", configfile.str_c_var("/etc/sysconfig/licenses")),
            ("TRACK_LICENSES", configfile.bool_c_var(False)),
            ("MODIFY_SGE_GLOBAL", configfile.bool_c_var(False)),
        ],
        dummy_run=global_config["DUMMY_RUN"]
    )
    # check modify_sge_global flag and set filesystem flag accordingly
    sge_license_tools.handle_license_policy(global_config["LICENSE_BASE"], global_config["MODIFY_SGE_GLOBAL"])
    pid_dir = "/var/run/{}".format(os.path.dirname(global_config["PID_NAME"]))
    if pid_dir not in ["/var/run", "/var/run/"]:
        process_tools.fix_directories(global_config["USER"], global_config["GROUP"], [pid_dir])
    process_tools.change_user_group(global_config["USER"], global_config["GROUP"], global_config["GROUPS"], global_config=global_config)
    if not global_config["DEBUG"]:
        process_tools.become_daemon()
        process_tools.set_handles(
            {
                "out": (1, "sge-server.out"),
                "err": (0, "/var/lib/logging-server/py_err")
            }
        )
    else:
        print "Debugging RMS-server"
    ret_state = server_process().loop()
    return ret_state
