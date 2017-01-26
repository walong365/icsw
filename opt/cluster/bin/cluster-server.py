#!/usr/bin/python3-init -Ot
#
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

import os
import sys
import argparse

if not __file__.startswith("/opt/cluster"):
    _add_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    if _add_path not in sys.path:
        sys.path.insert(0, _add_path)

from initat.cluster_server import main

my_parser = argparse.ArgumentParser()
my_parser.add_argument(
    "-c",
    dest="COMMAND",
    default="version",
    type=str,
    help="Command to execute [%(default)s]",
)
my_parser.add_argument(
    "--backup-database",
    default=False,
    action="store_true",
    dest="BACKUP_DATABASE",
    help="backup database [%(default)s]",
)
my_parser.add_argument(
    "-D",
    action="append",
    default=[],
    nargs="*",
    help="optional key:value paris (command dependent)",
    dest="OPTION_KEYS",
)
my_parser.add_argument(
    "--show-result",
    dest="SHOW_RESULT",
    default=False,
    action="store_true",
    help="show full XML result [%(default)s]",
)

sys.exit(main.main(options=my_parser.parse_args()))
