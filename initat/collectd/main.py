# Copyright (C) 2014-2015 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file belongs to the collectd-init package
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
""" main part of collectd-init """

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

import django
django.setup()

from initat.cluster.backbone.models import LogSource
from initat.collectd.config_static import COMMAND_PORT
from initat.server_version import VERSION_STRING
from io_stream_helper import io_stream
from initat.tools import cluster_location
from initat.tools import config_tools
from initat.tools import configfile
import daemon
from initat.tools import process_tools
import sys
import time


def run_code():
    from initat.collectd.server import server_process
    server_process().loop()


def kill_previous():
    # check for already running rrdcached processes and kill them
    proc_dict = process_tools.get_proc_list_new(proc_name_list=["rrdcached", "collectd"])
    if proc_dict:
        for _key in proc_dict.iterkeys():
            try:
                os.kill(_key, 15)
            except:
                pass
        time.sleep(2)
        for _key in proc_dict.iterkeys():
            try:
                os.kill(_key, 9)
            except:
                pass


def _create_dirs(global_config):
    graph_root = global_config["RRD_DIR"]
    if not os.path.isdir(graph_root):
        try:
            os.makedirs(graph_root)
        except:
            print("*** cannot create graph_root '{}': {}".format(graph_root, process_tools.get_except_info()))
        else:
            print("created graph_root '{}'".format(graph_root))


def main():
    global_config = configfile.configuration(process_tools.get_programm_name(), single_process_mode=True)
    long_host_name, _mach_name = process_tools.get_fqdn()
    prog_name = global_config.name()
    global_config.add_config_entries([
        ("DEBUG", configfile.bool_c_var(False, help_string="enable debug mode [%(default)s]", short_options="d", only_commandline=True)),
        ("ZMQ_DEBUG", configfile.bool_c_var(False, help_string="enable 0MQ debugging [%(default)s]", only_commandline=True)),
        ("KILL_RUNNING", configfile.bool_c_var(True, help_string="kill running instances [%(default)s]")),
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
        # ("COM_PORT", configfile.int_c_var(SERVER_COM_PORT, database=True)),
        ("VERBOSE", configfile.int_c_var(0, help_string="set verbose level [%(default)d]", short_options="v", only_commandline=True)),
        ("RRD_DIR", configfile.str_c_var("/var/cache/rrd", help_string="directory of rrd-files on local disc", database=True)),
        ("RRD_CACHED_DIR", configfile.str_c_var("/var/run/rrdcached", database=True)),
        ("RRD_CACHED_SOCKET", configfile.str_c_var("/var/run/rrdcached/rrdcached.sock", database=True)),
        ("RRD_STEP", configfile.int_c_var(60, help_string="RRD step value", database=True)),
    ])
    global_config.parse_file()
    _options = global_config.handle_commandline(
        description="{}, version is {}".format(
            prog_name,
            VERSION_STRING),
        add_writeback_option=True,
        positional_arguments=False)
    global_config.write_file()
    sql_info = config_tools.server_check(server_type="rrd_collector")
    if not sql_info.effective_device:
        print "not an rrd_collector"
        sys.exit(5)
    else:
        global_config.add_config_entries([("SERVER_IDX", configfile.int_c_var(sql_info.effective_device.pk, database=False))])
    if global_config["CHECK"]:
        sys.exit(0)
    if global_config["KILL_RUNNING"]:
        _log_lines = process_tools.kill_running_processes(
            "{}.py".format(prog_name),
            ignore_names=[],
        )

    global_config.add_config_entries(
        [
            (
                "LOG_SOURCE_IDX",
                configfile.int_c_var(
                    LogSource.new(
                        "rrd-collector", device=sql_info.effective_device
                    ).pk
                )
            ),
        ]
    )
    cluster_location.read_config_from_db(global_config, "rrd_collector", [
        ("RRD_COVERAGE_1", configfile.str_c_var("1min for 2days", database=True)),
        ("RRD_COVERAGE_2", configfile.str_c_var("5min for 2 week", database=True)),
        ("RRD_COVERAGE_3", configfile.str_c_var("15mins for 1month", database=True)),
        ("RRD_COVERAGE_4", configfile.str_c_var("4 hours for 1 year", database=True)),
        ("RRD_COVERAGE_5", configfile.str_c_var("1day for 5 years", database=True)),
        ("MODIFY_RRD_COVERAGE", configfile.bool_c_var(False, help_string="alter RRD files on disk when coverage differs from configured one", database=True)),
        ("MEMCACHE_ADDRESS", configfile.str_c_var("127.0.0.1:11211", help_string="memcache address")),
        ("SNMP_PROCS", configfile.int_c_var(4, help_string="number of SNMP processes to use [%(default)s]")),
        ("MAX_SNMP_JOBS", configfile.int_c_var(40, help_string="maximum number of jobs a SNMP process shall handle [%(default)s]")),
        ("RECV_PORT", configfile.int_c_var(8002, help_string="receive port, do not change [%(default)s]")),
        ("COMMAND_PORT", configfile.int_c_var(COMMAND_PORT, help_string="command port, do not change [%(default)s]")),
        ("GRAPHER_PORT", configfile.int_c_var(8003, help_string="grapher port, do not change [%(default)s]")),
        ("MD_SERVER_HOST", configfile.str_c_var("127.0.0.1", help_string="md-config-server host [%(default)s]")),
        ("MD_SERVER_PORT", configfile.int_c_var(8010, help_string="md-config-server port, do not change [%(default)s]")),
        ("MEMCACHE_HOST", configfile.str_c_var("127.0.0.1", help_string="host where memcache resides [%(default)s]")),
        ("MEMCACHE_PORT", configfile.int_c_var(11211, help_string="port on which memcache is reachable [%(default)s]")),
        ("MEMCACHE_TIMEOUT", configfile.int_c_var(2 * 60, help_string="timeout in seconds for values stored in memcache [%(default)s]")),
        ("RRD_CACHED_WRITETHREADS", configfile.int_c_var(4, help_string="number of write threads for RRD-cached")),
        ("AGGREGATE_STRUCT_UPDATE", configfile.int_c_var(600, help_string="timer for aggregate struct updates")),
    ])
    if global_config["RRD_CACHED_SOCKET"] == "/var/run/rrdcached.sock":
        global_config["RRD_CACHED_SOCKET"] = os.path.join(global_config["RRD_CACHED_DIR"], "rrdcached.sock")
    _create_dirs(global_config)

    process_tools.renice()
    process_tools.fix_directories(
        global_config["USER"],
        global_config["GROUP"],
        [
            "/var/run/collectd-init", global_config["RRD_DIR"], global_config["RRD_CACHED_DIR"],
        ]
    )
    kill_previous()
    process_tools.change_user_group(global_config["USER"], global_config["GROUP"], global_config["GROUPS"], global_config=global_config)
    if not global_config["DEBUG"]:
        with daemon.DaemonContext(
            uid=process_tools.get_uid_from_name(global_config["USER"])[0],
            gid=process_tools.get_gid_from_name(global_config["GROUP"])[0],
        ):
            global_config = configfile.get_global_config(prog_name, parent_object=global_config)
            sys.stdout = io_stream("/var/lib/logging-server/py_log_zmq")
            sys.stderr = io_stream("/var/lib/logging-server/py_err_zmq")
            run_code()
            configfile.terminate_manager()
    else:
        global_config = configfile.get_global_config(prog_name, parent_object=global_config)
        print("Debugging collectd-init on {}".format(long_host_name))
        run_code()
    sys.exit(0)
