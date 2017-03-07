# -*- coding: utf-8 -*-
#
# Copyright (C) 2010-2017 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
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

"""
constants for websockets
"""

from enum import Enum


class WSStreamDefinition(object):
    def __init__(self, general: bool):
        self.general = general

    def to_json(self, name):
        return name


class WSStreamEnum(Enum):
    general = WSStreamDefinition(True)
    device_log_entries = WSStreamDefinition(False)
    rrd_graph = WSStreamDefinition(False)
    background_jobs = WSStreamDefinition(False)
    ova_counter = WSStreamDefinition(False)
    device_scan_lock = WSStreamDefinition(False)
    nmap_scans = WSStreamDefinition(False)
    hm_status = WSStreamDefinition(False)
    asset_batch = WSStreamDefinition(False)
