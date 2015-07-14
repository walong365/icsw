# -*- coding: utf-8 -*-
#
# Copyright (C) 2014 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of logcheck-server
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
""" creates fixtures for logcheck-server """

from initat.cluster.backbone import factories
from .config_catalog_fixtures import SysConfig


def add_fixtures(**kwargs):
    SysConfig(
        name="logcheck_server",
        description="store and check node logs",
        server_config=True,
        system_config=True,
    )
    SysConfig(
        name="syslog_server",
        description="store and check node logs (for stage2)",
        server_config=True,
        system_config=True,
    )
