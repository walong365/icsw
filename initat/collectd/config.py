#
# this file is part of collectd-init
#
# Copyright (C) 2013-2015 Andreas Lang-Nevyjel init.at
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

""" base constants and config """

from initat.tools import process_tools, configfile, uuid_tools

global_config = configfile.get_global_config(process_tools.get_programm_name())

IPC_SOCK_SNMP = process_tools.get_zmq_ipc_name("snmp", connect_to_root_instance=True, s_name="collectd-init")
MD_SERVER_UUID = uuid_tools.get_uuid().get_urn()
