#
# Copyright (C) 2016-2017 Andreas Lang-Nevyjel, init.at
#
# this file is part of icsw-server-server
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
""" main process for md-sync-server """

import os

from initat.md_sync_server.config import global_config
from initat.tools import configfile


def run_code():
    from initat.md_sync_server.server import server_process
    server_process().loop()


def main():
    global_config.add_config_entries(
        [
            ("MEMCACHE_ADDRESS", configfile.str_c_var("127.0.0.1", help_string="memcache address")),
        ]
    )
    # enable connection debugging
    run_code()
    # exit
    os._exit(0)
