# -*- coding: utf-8 -*-
#
# Copyright (C) 2013,2015-2016 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of host-monitoring
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

""" meta-server, config """

from __future__ import unicode_literals, print_function

from initat.tools import configfile, process_tools

__all__ = [
    b"global_config",
    # original sql schema version
    b"INIT_SQL_SCHEMA_VERSION",
    b"SQL_SCHEMA_VERSION",
]


global_config = configfile.get_global_config(process_tools.get_programm_name(), single_process_mode=True)

INIT_SQL_SCHEMA_VERSION = 1
SQL_SCHEMA_VERSION = 2
