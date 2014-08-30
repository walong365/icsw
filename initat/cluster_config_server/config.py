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
""" cluster-config-server, configuration and constants """

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

import configfile
import process_tools

try:
    from initat.cluster_config_server.cluster_config_server_version import VERSION_STRING
except ImportError:
    VERSION_STRING = "?.?"

SERVER_PORT = 8005
NCS_PORT = 8010
GATEWAY_THRESHOLD = 1000

global_config = configfile.get_global_config(process_tools.get_programm_name())
