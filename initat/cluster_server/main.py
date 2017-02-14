# Copyright (C) 2001-2008,2012-2017 Andreas Lang-Nevyjel
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
""" cluster-server """

from __future__ import unicode_literals, print_function

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

import django
django.setup()

from initat.tools import configfile
from initat.cluster_server.config import global_config


def run_code():
    from initat.cluster_server.server import ServerProcess
    ServerProcess().loop()


def main(options=None):
    global_config.add_config_entries(
        [
            (
                "COMMAND", configfile.StringConfigVar(
                    options.COMMAND if options else "",
                )
            ),
            (
                "BACKUP_DATABASE", configfile.BoolConfigVar(
                    options.BACKUP_DATABASE if options else False,
                )
            ),
            (
                "OPTION_KEYS", configfile.ArrayConfigVar(
                    options.OPTION_KEYS if options else [],
                )
            ),
            (
                "SHOW_RESULT", configfile.BoolConfigVar(
                    options.SHOW_RESULT if options else False,
                )
            ),
        ]
    )
    run_code()
    return 0
