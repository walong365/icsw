#!/usr/bin/python-init -OtW default
#
# Copyright (C) 2013,2013 Andreas Lang-Nevyjel, init.at
#
# this file is part of md-config-server
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
""" main process for md-config-server """

import sys
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

import cluster_location
import config_tools
import configfile
import process_tools

from initat.md_config_server.config import global_config
from initat.md_config_server.constants import SERVER_COM_PORT, IDOMOD_PROCESS_TIMED_EVENT_DATA, \
    IDOMOD_PROCESS_SERVICE_CHECK_DATA, IDOMOD_PROCESS_HOST_CHECK_DATA, BROKER_TIMED_EVENTS, \
    BROKER_SERVICE_CHECKS, BROKER_HOST_CHECKS
from initat.md_config_server.server import server_process

try:
    from md_config_server.version import VERSION_STRING
except ImportError:
    VERSION_STRING = "?.?"

from django.conf import settings
from django.db.models import Q
from django.db import connection, connections
from initat.cluster.backbone.models import device, device_group, device_variable, mon_device_templ, \
     mon_ext_host, mon_check_command, mon_period, mon_contact, \
     mon_contactgroup, mon_service_templ, netdevice, network, network_type, net_ip, \
     user, mon_host_cluster, mon_service_cluster, config, md_check_data_store, category, \
     category_tree, TOP_MONITORING_CATEGORY, mon_notification, config_str, config_int, host_check_command

def main():
    long_host_name, mach_name = process_tools.get_fqdn()
    prog_name = global_config.name()
    global_config.add_config_entries([
        ("DEBUG"               , configfile.bool_c_var(False, help_string="enable debug mode [%(default)s]", short_options="d", only_commandline=True)),
        ("ZMQ_DEBUG"           , configfile.bool_c_var(False, help_string="enable 0MQ debugging [%(default)s]", only_commandline=True)),
        ("KILL_RUNNING"        , configfile.bool_c_var(True, help_string="kill running instances [%(default)s]")),
        ("CHECK"               , configfile.bool_c_var(False, short_options="C", help_string="only check for server status", action="store_true", only_commandline=True)),
        ("USER"                , configfile.str_c_var("idnagios", help_string="user to run as [%(default)s")),
        ("GROUP"               , configfile.str_c_var("idg", help_string="group to run as [%(default)s]")),
        ("GROUPS"              , configfile.array_c_var([])),
        ("LOG_DESTINATION"     , configfile.str_c_var("uds:/var/lib/logging-server/py_log_zmq")),
        ("LOG_NAME"            , configfile.str_c_var(prog_name)),
        ("PID_NAME"            , configfile.str_c_var(os.path.join(prog_name,
                                                                   prog_name))),
        ("COM_PORT"            , configfile.int_c_var(SERVER_COM_PORT)),
        ("VERBOSE"             , configfile.int_c_var(0, help_string="set verbose level [%(default)d]", short_options="v", only_commandline=True)),
    ])
    global_config.parse_file()
    options = global_config.handle_commandline(
        description="%s, version is %s" % (prog_name,
                                           VERSION_STRING),
        add_writeback_option=True,
        positional_arguments=False)
    global_config.write_file()
    sql_info = config_tools.server_check(server_type="monitor_server")
    if not sql_info.effective_device:
        print "not a monitor_server"
        sys.exit(5)
    else:
        global_config.add_config_entries([("SERVER_IDX", configfile.int_c_var(sql_info.effective_device.pk, database=False))])
    if global_config["CHECK"]:
        sys.exit(0)
    if global_config["KILL_RUNNING"]:
        log_lines = process_tools.kill_running_processes(
            "%s.py" % (prog_name),
            ignore_names=["nagios", "icinga"],
            exclude=configfile.get_manager_pid())

    global_config.add_config_entries([("LOG_SOURCE_IDX", configfile.int_c_var(cluster_location.log_source.create_log_source_entry("mon-server", "Cluster MonitoringServer", device=sql_info.effective_device).pk))])

    cluster_location.read_config_from_db(global_config, "monitor_server", [
        ("COM_PORT"                    , configfile.int_c_var(SERVER_COM_PORT)),
        ("NETSPEED_WARN_MULT"          , configfile.float_c_var(0.85)),
        ("NETSPEED_CRITICAL_MULT"      , configfile.float_c_var(0.95)),
        ("NETSPEED_DEFAULT_VALUE"      , configfile.int_c_var(10000000)),
        ("CHECK_HOST_ALIVE_PINGS"      , configfile.int_c_var(5)),
        ("CHECK_HOST_ALIVE_TIMEOUT"    , configfile.float_c_var(5.0)),
        ("ENABLE_PNP"                  , configfile.bool_c_var(False)),
        ("ENABLE_COLLECTD"             , configfile.bool_c_var(False)),
        ("ENABLE_LIVESTATUS"           , configfile.bool_c_var(True)),
        ("ENABLE_NDO"                  , configfile.bool_c_var(False)),
        ("ENABLE_NAGVIS"               , configfile.bool_c_var(False)),
        ("ENABLE_FLAP_DETECTION"       , configfile.bool_c_var(False)),
        ("PNP_DIR"                     , configfile.str_c_var("/opt/pnp4nagios")),
        ("PNP_URL"                     , configfile.str_c_var("/pnp4nagios")),
        ("NAGVIS_DIR"                  , configfile.str_c_var("/opt/nagvis4icinga")),
        ("NAGVIS_URL"                  , configfile.str_c_var("/nagvis")),
        ("NONE_CONTACT_GROUP"          , configfile.str_c_var("none_group")),
        ("FROM_ADDR"                   , configfile.str_c_var(long_host_name)),
        ("BUILD_CONFIG_ON_STARTUP"     , configfile.bool_c_var(True)),
        ("RETAIN_HOST_STATUS"          , configfile.int_c_var(1)),
        ("RETAIN_SERVICE_STATUS"       , configfile.int_c_var(1)),
        ("NDO_DATA_PROCESSING_OPTIONS" , configfile.int_c_var((2 ** 26 - 1) - (IDOMOD_PROCESS_TIMED_EVENT_DATA - IDOMOD_PROCESS_SERVICE_CHECK_DATA + IDOMOD_PROCESS_HOST_CHECK_DATA))),
        ("EVENT_BROKER_OPTIONS"        , configfile.int_c_var((2 ** 20 - 1) - (BROKER_TIMED_EVENTS + BROKER_SERVICE_CHECKS + BROKER_HOST_CHECKS))),
        ("CCOLLCLIENT_TIMEOUT"         , configfile.int_c_var(6)),
        ("CSNMPCLIENT_TIMEOUT"         , configfile.int_c_var(20)),
        ("MAX_SERVICE_CHECK_SPREAD"    , configfile.int_c_var(5)),
        ("MAX_HOST_CHECK_SPREAD"       , configfile.int_c_var(5)),
        ("MAX_CONCURRENT_CHECKS"       , configfile.int_c_var(500)),
        ("SERVER_SHORT_NAME"           , configfile.str_c_var(mach_name)),
    ])
    process_tools.renice()
    process_tools.fix_directories(global_config["USER"], global_config["GROUP"], ["/var/run/md-config-server"])
    global_config.set_uid_gid(global_config["USER"], global_config["GROUP"])
    if global_config["ENABLE_NAGVIS"]:
        process_tools.fix_directories(global_config["USER"], global_config["GROUP"], [
            {"name"     : os.path.join(global_config["NAGVIS_DIR"], "etc"),
             "walk_dir" : False},
            {"name"     : os.path.join(global_config["NAGVIS_DIR"], "etc", "maps"),
             "walk_dir" : False}
        ])
        process_tools.fix_files(global_config["USER"], global_config["GROUP"], [
            os.path.join(global_config["NAGVIS_DIR"], "etc", "auth.db"),
            os.path.join(global_config["NAGVIS_DIR"], "etc", "nagvis.ini.php"),
            os.path.join(global_config["NAGVIS_DIR"], "share", "server", "core", "defines", "global.php"),
        ])
    process_tools.change_user_group(global_config["USER"], global_config["GROUP"], global_config["GROUPS"], global_config=global_config)
    if not global_config["DEBUG"]:
        process_tools.become_daemon()
    else:
        print "Debugging md-config-server on %s" % (long_host_name)
    ret_state = server_process().loop()
    sys.exit(ret_state)
