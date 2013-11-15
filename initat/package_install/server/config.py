#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008,2009,2012,2013 Andreas Lang-Nevyjel
#
# this file is part of package-server
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
""" package server, configuration """

import configfile
import process_tools

global_config = configfile.get_global_config(process_tools.get_programm_name())

P_SERVER_PUB_PORT = 8007
PACKAGE_CLIENT_PORT = 2003

ADD_PACK_PATH = "additional_packages"
DEL_PACK_PATH = "deleted_packages"

LAST_CONTACT_VAR_NAME = "package_server_last_contact"
PACKAGE_VERSION_VAR_NAME = "package_client_version"
DIRECT_MODE_VAR_NAME = "package_client_direct_mode"

CONFIG_NAME = "/etc/sysconfig/cluster/package_server_clients.xml"
