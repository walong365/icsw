#!/usr/bin/python-init -OtW default
#
# Copyright (C) 2013-2015 Andreas Lang-Nevyjel, init.at
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

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

import django
django.setup()

from django.conf import settings
from initat.md_config_server.constants import SERVER_COM_PORT, IDOMOD_PROCESS_TIMED_EVENT_DATA, \
    IDOMOD_PROCESS_SERVICE_CHECK_DATA, IDOMOD_PROCESS_HOST_CHECK_DATA, BROKER_TIMED_EVENTS, \
    BROKER_SERVICE_CHECKS, BROKER_HOST_CHECKS, CACHE_MODES
from initat.server_version import VERSION_STRING
from initat.tools import cluster_location, configfile, process_tools
from initat.md_config_server.config import global_config


def run_code():
    from initat.md_config_server.server import server_process
    server_process().loop()


def main():
    long_host_name, mach_name = process_tools.get_fqdn()
    prog_name = global_config.name()
    global_config.add_config_entries(
        [
            ("DEBUG", configfile.bool_c_var(False, help_string="enable debug mode [%(default)s]", short_options="d", only_commandline=True)),
            ("VERBOSE", configfile.int_c_var(0, help_string="set verbose level [%(default)d]", short_options="v", only_commandline=True)),
            ("INITIAL_CONFIG_RUN", configfile.bool_c_var(False, help_string="make a config build run on startup [%(default)s]", only_commandline=True)),
            (
                "INITIAL_CONFIG_CACHE_MODE", configfile.str_c_var(
                    "DYNAMIC",
                    help_string="cache mode for initial config run [%(default)s]",
                    only_commandline=True,
                    choices=CACHE_MODES
                )
            ),
            ("MEMCACHE_ADDRESS", configfile.str_c_var("127.0.0.1", help_string="memcache address")),
        ]
    )
    _options = global_config.handle_commandline(
        description="{}, version is {}".format(
            prog_name,
            VERSION_STRING
        ),
        positional_arguments=False
    )
    # enable connection debugging
    settings.DEBUG = global_config["DEBUG"]
    cluster_location.read_config_from_db(
        global_config,
        "monitor_server",
        [
            ("COM_PORT", configfile.int_c_var(SERVER_COM_PORT)),
            ("NETSPEED_WARN_MULT", configfile.float_c_var(0.85)),
            ("NETSPEED_CRITICAL_MULT", configfile.float_c_var(0.95)),
            ("NETSPEED_DEFAULT_VALUE", configfile.int_c_var(10000000)),
            ("CHECK_HOST_ALIVE_PINGS", configfile.int_c_var(5)),
            ("CHECK_HOST_ALIVE_TIMEOUT", configfile.float_c_var(5.0)),
            ("ENABLE_COLLECTD", configfile.bool_c_var(False)),
            ("ENABLE_LIVESTATUS", configfile.bool_c_var(True)),
            ("ENABLE_NDO", configfile.bool_c_var(False)),
            ("ENABLE_NAGVIS", configfile.bool_c_var(False)),
            ("ENABLE_FLAP_DETECTION", configfile.bool_c_var(False)),
            ("NAGVIS_DIR", configfile.str_c_var("/opt/nagvis4icinga")),
            ("NAGVIS_URL", configfile.str_c_var("/nagvis")),
            ("NONE_CONTACT_GROUP", configfile.str_c_var("none_group")),
            ("FROM_ADDR", configfile.str_c_var(long_host_name)),
            ("LOG_EXTERNAL_COMMANDS", configfile.bool_c_var(False)),
            ("LOG_PASSIVE_CHECKS", configfile.bool_c_var(False)),
            ("BUILD_CONFIG_ON_STARTUP", configfile.bool_c_var(True)),
            ("RELOAD_ON_STARTUP", configfile.bool_c_var(True)),
            ("RETAIN_HOST_STATUS", configfile.bool_c_var(True)),
            ("RETAIN_SERVICE_STATUS", configfile.bool_c_var(True)),
            ("PASSIVE_HOST_CHECKS_ARE_SOFT", configfile.bool_c_var(True)),
            ("RETAIN_PROGRAM_STATE", configfile.bool_c_var(False)),
            ("USE_HOST_DEPENDENCIES", configfile.bool_c_var(False)),
            ("USE_SERVICE_DEPENDENCIES", configfile.bool_c_var(False)),
            ("TRANSLATE_PASSIVE_HOST_CHECKS", configfile.bool_c_var(True)),
            ("USE_ONLY_ALIAS_FOR_ALIAS", configfile.bool_c_var(False)),
            ("HOST_DEPENDENCIES_FROM_TOPOLOGY", configfile.bool_c_var(False)),
            (
                "NDO_DATA_PROCESSING_OPTIONS", configfile.int_c_var(
                    (2 ** 26 - 1) - (IDOMOD_PROCESS_TIMED_EVENT_DATA - IDOMOD_PROCESS_SERVICE_CHECK_DATA + IDOMOD_PROCESS_HOST_CHECK_DATA)
                )
            ),
            ("EVENT_BROKER_OPTIONS", configfile.int_c_var((2 ** 20 - 1) - (BROKER_TIMED_EVENTS + BROKER_SERVICE_CHECKS + BROKER_HOST_CHECKS))),
            ("CCOLLCLIENT_TIMEOUT", configfile.int_c_var(10)),
            ("CSNMPCLIENT_TIMEOUT", configfile.int_c_var(20)),
            ("MAX_SERVICE_CHECK_SPREAD", configfile.int_c_var(5)),
            ("MAX_HOST_CHECK_SPREAD", configfile.int_c_var(5)),
            ("MAX_CONCURRENT_CHECKS", configfile.int_c_var(500)),
            ("CHECK_SERVICE_FRESHNESS", configfile.bool_c_var(True, help_string="enable service freshness checking")),
            ("CHECK_HOST_FRESHNESS", configfile.bool_c_var(True, help_string="enable host freshness checking")),
            ("SAFE_CC_NAME", configfile.bool_c_var(False)),
            ("SERVICE_FRESHNESS_CHECK_INTERVAL", configfile.int_c_var(60)),
            ("HOST_FRESHNESS_CHECK_INTERVAL", configfile.int_c_var(60)),
            ("SAFE_NAMES", configfile.bool_c_var(False, help_string="convert all command descriptions to safe names (without spaces), [%(default)s]")),
            (
                "ENABLE_ICINGA_LOG_PARSING",
                configfile.bool_c_var(True, help_string="collect icinga logs in the database (required for status history and kpis)")
            ),
        ]
    )
    run_code()
    configfile.terminate_manager()
    # exit
    os._exit(0)
