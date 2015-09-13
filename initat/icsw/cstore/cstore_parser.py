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
parser for config store
"""


class Parser(object):
    def link(self, sub_parser, **kwargs):
        return self._add_cstore_parser(sub_parser)

    def _add_cstore_parser(self, sub_parser):
        parser = sub_parser.add_parser("cstore", help="configstore tool")
        parser.set_defaults(subcom="cstore", execute=self._execute)
        parser.add_argument(
            "--mode",
            default="liststores",
            choices=[
                "liststores", "showstore", "getkey", "storeexists", "keyexists", "createstore", "setkey",
            ],
            type=str,
            help="Operation mode [%(default)s]"
        )
        parser.add_argument("--store", default="client", type=str, help="ConfigStore name [%(default)s]")
        parser.add_argument("--quiet", default=False, action="store_true", help="Enable quiet mode [%(default)s]")
        parser.add_argument("--sort-by-value", default=False, action="store_true", help="Sort output by value [%(default)s]")
        parser.add_argument("--key", default="", type=str, help="Key to show [%(default)s]")
        parser.add_argument("--value", default="", type=str, help="value to set [%(default)s]")

    def _execute(self, opt_ns):
        from .main import main
        main(opt_ns)
