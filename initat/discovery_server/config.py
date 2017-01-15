# Copyright (C) 2014-2015,2017 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# this file is part of discovery-server
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
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
""" discovery-server, configuration and constants """

from initat.tools import configfile, process_tools

from initat.server_version import VERSION_STRING

global_config = configfile.get_global_config(process_tools.get_programm_name())
IPC_SOCK_SNMP = process_tools.get_zmq_ipc_name("snmp", connect_to_root_instance=True, s_name="discovery-server")
