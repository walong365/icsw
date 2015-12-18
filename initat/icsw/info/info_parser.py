# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 Andreas Lang-Nevyjel (lang-nevyjel@init.at)
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of logging-server
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
""" show command helps """

import argparse
import os
import re

from initat.tools import process_tools


class Parser(object):
    def link(self, sub_parser, **kwargs):
        return self._add_info_parser(sub_parser, server_mode=kwargs["server_mode"])

    def _add_info_parser(self, sub_parser, server_mode):
        _mach_name = process_tools.get_machine_name(short=True)
        parser = sub_parser.add_parser("info", help="show command help")
        parser.set_defaults(subcom="info", execute=self._execute)
        _choices = ["host-monitoring"]
        if server_mode:
            _choices.extend(
                [
                    "cluster-server"
                ]
            )
        parser.add_argument("--subsys", type=str, default=_choices[0], choices=_choices, help="show command info for given subsystem [%(default)s]")
        parser.add_argument("args", nargs="*")

        return parser

    def _execute(self, opt_ns):
        from .main import main
        main(opt_ns)
