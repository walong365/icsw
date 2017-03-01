# -*- coding: utf-8 -*-
#
# Copyright (C) 2015-2017 Andreas Lang-Nevyjel (lang-nevyjel@init.at)
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw-client
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
""" controll cluster debug mode """

import os
import sys

from initat.constants import LOG_ROOT

LOGSERVER_ROOT = os.path.join(LOG_ROOT, "logging-server")


class Parser(object):
    def link(self, sub_parser, **kwargs):
        return self._add_debug_parser(sub_parser)

    def _add_debug_parser(self, sub_parser):
        from initat.debug import ICSW_DEBUG_VARS
        parser = sub_parser.add_parser("debug", help="control icsw debug modes")
        parser.set_defaults(subcom="debug", execute=self._execute)
        parser.add_argument(
            "--show",
            default=False,
            action="store_true",
            help="show current debug settings [%(default)s]",
        )
        parser.add_argument(
            "--clear",
            default=False,
            action="store_true",
            help="clear all debug variables [%(default)s]",
        )
        for _var in ICSW_DEBUG_VARS:
            if _var.type is bool:
                parser.add_argument(
                    "--enable-{}".format(_var.argparse_name),
                    dest=_var.option_name,
                    default=_var.default,
                    action="store_true",
                    help="enable {} [%(default)s]".format(
                        _var.description,
                    ),
                )
                parser.add_argument(
                    "--disable-{}".format(_var.argparse_name),
                    dest=_var.option_name,
                    default=_var.default,
                    action="store_false",
                    help="disable {} [%(default)s]".format(
                        _var.description,
                    ),
                )
            else:
                parser.add_argument(
                    "--{}".format(_var.argparse_name),
                    default=_var.default,
                    type=_var.type,
                    help="{} [%(default)s]".format(
                        _var.description,
                    ),
                )
        return parser

    def _execute(self, opt_ns):
        from .main import main
        main(opt_ns)
