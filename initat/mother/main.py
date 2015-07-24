# -*- coding: utf-8 -*-
#
# Copyright (C) 2001-2009,2012-2015 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of mother
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FTNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
""" mother daemon, main part """

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

import django
django.setup()

from django.conf import settings
from initat.cluster.backbone.models import LogSource
from initat.server_version import VERSION_STRING
from initat.tools import cluster_location
from initat.tools import configfile
import initat.mother.server
from initat.mother.config import global_config
from initat.tools import process_tools
import sys


def main():
    _long_host_name, mach_name = process_tools.get_fqdn()
    prog_name = global_config.name()
    global_config.add_config_entries(
        [
            ("DEBUG", configfile.bool_c_var(False, help_string="enable debug mode [%(default)s]", short_options="d", only_commandline=True)),
            ("DATABASE_DEBUG", configfile.bool_c_var(False, help_string="enable database debug mode [%(default)s]", only_commandline=True)),
            ("MODIFY_NFS_CONFIG", configfile.bool_c_var(True, help_string="modify /etc/exports [%(default)s]", action="store_true")),
            ("VERBOSE", configfile.int_c_var(0, help_string="set verbose level [%(default)d]", short_options="v", only_commandline=True)),
        ]
    )
    _options = global_config.handle_commandline(
        description="{}, version is {}".format(
            prog_name,
            VERSION_STRING
        ),
        positional_arguments=False,
    )
    cluster_location.read_config_from_db(
        global_config,
        "mother_server",
        [
            ("TFTP_LINK", configfile.str_c_var("/tftpboot")),
            ("TFTP_DIR", configfile.str_c_var("/opt/cluster/system/tftpboot")),
            ("CLUSTER_DIR", configfile.str_c_var("/opt/cluster")),
            ("NODE_PORT", configfile.int_c_var(2001)),
            # in 10th of seconds
            ("NODE_BOOT_DELAY", configfile.int_c_var(50)),
            ("FANCY_PXE_INFO", configfile.bool_c_var(False)),
            ("SERVER_SHORT_NAME", configfile.str_c_var(mach_name)),
        ]
    )
    global_config.add_config_entries(
        [
            ("CONFIG_DIR", configfile.str_c_var(os.path.join(global_config["TFTP_DIR"], "config"))),
            ("ETHERBOOT_DIR", configfile.str_c_var(os.path.join(global_config["TFTP_DIR"], "etherboot"))),
            ("KERNEL_DIR", configfile.str_c_var(os.path.join(global_config["TFTP_DIR"], "kernels"))),
            ("SHARE_DIR", configfile.str_c_var(os.path.join(global_config["CLUSTER_DIR"], "share", "mother"))),
            ("NODE_SOURCE_IDX", configfile.int_c_var(LogSource.new("node").pk)),
        ]
    )
    settings.DEBUG = global_config["DATABASE_DEBUG"]
    settings.DATABASE_DEBUG = global_config["DATABASE_DEBUG"]
    initat.mother.server.server_process().loop()
    configfile.terminate_manager()
    sys.exit(0)
