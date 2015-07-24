# -*- coding: utf-8 -*-
#
# Copyright (C) 2001-2008,2010-2015 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of meta-server
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
""" meta-server, main part """

import os

from initat.meta_server.config import global_config
from initat.meta_server.server import main_process
from initat.tools import configfile
from initat.client_version import VERSION_STRING


def main():
    global_config.add_config_entries(
        [
            ("DEBUG", configfile.bool_c_var(False, help_string="enable debug mode [%(default)s]", short_options="d", only_commandline=True)),
        ]
    )
    options = global_config.handle_commandline(
        description="meta-server, version is {}".format(VERSION_STRING),
    )
    main_process().loop()
    os._exit(0)
