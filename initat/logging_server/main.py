# -*- coding: utf-8 -*-
#
# Copyright (C) 2009-2015 Andreas Lang-Nevyjel (lang-nevyjel@init.at)
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of logging-server
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
""" logging server, central logging facility, main part """

from initat.client_version import VERSION_STRING
from initat.logging_server.config import global_config
from initat.logging_server.server import main_process
from initat.tools import configfile


def main():
    global_config.add_config_entries(
        [
            ("DEBUG", configfile.bool_c_var(False, help_string="enable ebugging [%(default)s]", only_commandline=True, short_options="d")),
        ]
    )
    options = global_config.handle_commandline(
        description="logging server, version is {}".format(VERSION_STRING),
    )
    main_process(options).loop()
    return 0
