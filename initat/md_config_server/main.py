#
# Copyright (C) 2013-2017 Andreas Lang-Nevyjel, init.at
#
# this file is part of md-config-server
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
""" main process for md-config-server """

from __future__ import unicode_literals, print_function

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

import django
django.setup()

from django.conf import settings
from initat.tools import configfile
from initat.md_config_server.config import global_config


def run_code():
    from initat.md_config_server.server import ServerProcess
    ServerProcess().loop()


def main():
    global_config.add_config_entries(
        [
            ("DEBUG", configfile.bool_c_var(False, help_string="enable debug mode [%(default)s]", short_options="d", only_commandline=True)),
            ("VERBOSE", configfile.int_c_var(0, help_string="set verbose level [%(default)d]", short_options="v", only_commandline=True)),
            ("INITIAL_CONFIG_RUN", configfile.bool_c_var(False, help_string="make a config build run on startup [%(default)s]", only_commandline=True)),
            ("MEMCACHE_ADDRESS", configfile.str_c_var("127.0.0.1", help_string="memcache address")),
        ]
    )
    # enable connection debugging
    global_config["DEBUG"] = settings.DEBUG
    run_code()
    # exit
    os._exit(0)
