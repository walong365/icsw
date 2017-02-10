# -*- coding: utf-8 -*-
#
# Copyright (C) 2015-2017 Andreas Lang-Nevyjel (lang-nevyjel@init.at)
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw-server-client
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
""" show cluster error logs """

import os
import sys

from initat.constants import LOG_ROOT

LOGSERVER_ROOT = os.path.join(LOG_ROOT, "logging-server")


class Parser(object):
    def link(self, sub_parser, **kwargs):
        return self._add_lw_parser(sub_parser)

    def _add_lw_parser(self, sub_parser):
        parser = sub_parser.add_parser("error", help="show cluster error log")
        parser.set_defaults(subcom="error", execute=self._execute)
        parser.add_argument("--stat", default=False, action="store_true", help="show statistis (error per UID, [%(default)s]")
        parser.add_argument("--clear", default=False, action="store_true", help="compress actual error file [%(default)s]")
        parser.add_argument("--noempty", default=False, action="store_true", help="suppress empty error lines [%(default)s]")
        parser.add_argument("-s", dest="index", action="append", help="show index at position [%(default)s]", default=[])
        parser.add_argument("-l", type=int, dest="num", help="show last [%(default)s] error", default=0)

        return parser

    def _old_execute(self, opt_ns):
        print("lse is now deprectated, please use error")
        sys.exit(2)

    def _execute(self, opt_ns):
        from .main import main
        main(opt_ns)
