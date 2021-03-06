# Copyright (C) 2016-2017 Andreas Lang-Nevyjel, init.at
#
# this file is part of icsw-server
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
""" config part of md-config-server """

from initat.tools import configfile, process_tools


__all__ = [
    "global_config",
    "CS_NAME",
    "CS_MON_NAME",
]

global_config = configfile.get_global_config(process_tools.get_programm_name())
# general settings for main proces
CS_NAME = "icsw.md-sync"
# monitoring info (used icinga version)
CS_MON_NAME = "icsw.md-sync.mon"
