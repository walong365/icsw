#!/usr/bin/python-init -OtB
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
""" device information """


class Parser(object):
    def link(self, sub_parser):
        return self._add_dev_parser(sub_parser)

    def _add_dev_parser(self, sub_parser):
        parser = sub_parser.add_parser("device", help="device information")
        parser.set_defaults(subcom="device", execute=self._execute)
        parser.add_argument("dev", type=str, nargs="+", help="device to query [%(default)s]", default="")
        return parser

    def _execute(self, opt_ns):
        from .main import main
        main(opt_ns)
