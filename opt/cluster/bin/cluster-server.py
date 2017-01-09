#!/usr/bin/python-init -Ot
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

from __future__ import print_function, unicode_literals

import sys

from initat.cluster_server import main

if not any(
    [
        _check in sys.argv for _check in [
            "-c",
            "-h",
            "--help",
            "--show-commands",
            "--show_commands",
            "--backup-database",
            "--backup_database"
        ]
    ]
):
    print("need command (specified via -c)")
    sys.exit(-1)
sys.exit(main.main())
