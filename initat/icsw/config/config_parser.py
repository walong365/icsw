# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 Andreas Lang-Nevyjel (lang-nevyjel@init.at)
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of logging-server
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
""" config information and modify """





class Parser(object):
    def link(self, sub_parser, **kwargs):
        self.__server_mode = kwargs["server_mode"]
        self._add_config_parser(sub_parser)

    def _add_config_parser(self, sub_parser):
        parser = sub_parser.add_parser("config", help="config handling (update, create, compare)")
        parser.set_defaults(subcom="config", execute=self._execute)
        child_parser = parser.add_subparsers(help="config subcommands")
        self._add_enum_parser(child_parser)
        self._add_show_parser(child_parser)
        self._add_role_parser(child_parser)
        return parser

    def _add_enum_parser(self, child_parser):
        if self.__server_mode:
            parser = child_parser.add_parser("enum", help="show enumerated server configs")
            parser.set_defaults(childcom="enum_show")
            parser.add_argument(
                "--sync",
                default=False,
                action="store_true",
                help="sync found Enum with database [%(default)s] and create dummy configs"
            )

    def _add_show_parser(self, child_parser):
        parser = child_parser.add_parser("show", help="show config open(s) for NOCTUA / CORVUS")
        parser.set_defaults(childcom="show")
        parser.add_argument(
            "-s", dest="full_strip", default=False, action="store_true", help="strip all empty lines from file [%(default)s]"
        )
        parser.add_argument(
            "-c", dest="remove_hashes", default=False, action="store_true",
            help="remove all lines starting with hashes from file [%(default)s]"
        )
        parser.add_argument("-b", dest="binary", default=False, action="store_true", help="treat files as binaries [%(default)s]")
        parser.add_argument(
            "--short-path", dest="short_path", default=False, action="store_true",
            help="use short path for file objects [%(default)s]"
        )
        parser.add_argument("files", nargs="+", help="files to operate on")

    def _add_role_parser(self, child_parser):
        parser = child_parser.add_parser(
                "role",
                help="do an automatic configuration based on the intended "
                     "usage of the server"
                )
        parser.set_defaults(childcom="role")
        parser.add_argument('role', choices=['noctua'])

    def _execute(self, opt_ns):
        from .main import main
        main(opt_ns)
