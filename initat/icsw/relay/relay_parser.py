#!/usr/bin/python-init -Otu
# Copyright (C) 2015 Andreas Lang-Nevyjel, init.at
#
# this file is part of icsw-client
#
# Send feedback to: <lang-nevyjel@init.at>
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
"""
parser for relay info / modifying
"""


from initat.host_monitoring.discovery import CS_NAME
from initat.tools.config_store import ConfigStore


class Parser(object):
    def link(self, sub_parser):
        # only add parser if relay-cstore exists
        if ConfigStore.exists(CS_NAME):
            return self._add_relay_parser(sub_parser)

    def _add_relay_parser(self, sub_parser):
        parser = sub_parser.add_parser("relay", help="host-relay tool")
        parser.set_defaults(subcom="relay", execute=self._execute)
        parser.add_argument(
            "--mode",
            default="dump",
            choices=[
                "dump",
            ],
            type=str,
            help="Operation mode [%(default)s]"
        )
        parser.add_argument(
            "--port",
            default=0,
            type=int,
            help="Filter for port [%(default)s]",
        )
        parser.add_argument(
            "--remove-unique",
            default=False,
            action="store_true",
            help="remove unique UUID entries [%(default)s]",
        )

    def _execute(self, opt_ns):
        from .main import main
        main(opt_ns)
