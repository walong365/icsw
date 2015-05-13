#!/usr/bin/python-init -Ot
#
# Copyright (C) 2015 Andreas Lang-Nevyjel, init.at
#
# this file is part of icsw-client
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

""" constants for service handling """

__all__ = [
    "SERVICE_OK",
    "SERVICE_DEAD",
    "SERVICE_NOT_INSTALLED",
    "SERVICE_INCOMPLETE",
    "SERVICE_NOT_LICENSED",
    "SERVICE_NOT_CONFIGURED",
    "INIT_BASE",
    "SERVERS_DIR",
]

# service states
SERVICE_OK = 0
SERVICE_DEAD = 1
SERVICE_INCOMPLETE = 2
SERVICE_NOT_LICENSED = 4
SERVICE_NOT_INSTALLED = 5
SERVICE_NOT_CONFIGURED = 6

# path definitions
INIT_BASE = "/opt/python-init/lib/python/site-packages/initat"
SERVERS_DIR = "/opt/cluster/etc/servers.d"
