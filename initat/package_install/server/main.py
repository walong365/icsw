# Copyright (C) 2001-2009,2012-2017 Andreas Lang-Nevyjel
#
# this file is part of package-server
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
""" package server """

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

import django

django.setup()

from .config import global_config
from initat.tools import configfile


def run_code():
    from initat.package_install.server.server import ServerProcess
    ServerProcess().loop()


def main():
    global_config.add_config_entries(
        [
            ("DELETE_MISSING_REPOS", configfile.bool_c_var(False, help_string="delete non-existing repos from DB", database=True)),
            ("SUPPORT_OLD_CLIENTS", configfile.bool_c_var(False, help_string="support old clients [%(default)s]", database=True)),
        ]
    )
    run_code()
    os._exit(0)
