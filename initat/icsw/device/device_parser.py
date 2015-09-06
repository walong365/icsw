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
""" device information and modify """

import os

try:
    from . import devicelog
except:
    devicelog = None


class Parser(object):
    def link(self, sub_parser):
        return self._add_dev_parser(sub_parser)

    def _add_dev_parser(self, sub_parser):
        parser = sub_parser.add_parser("device", help="device information")
        parser.set_defaults(subcom="device", execute=self._execute)
        child_parser = parser.add_subparsers(help="device subcommands")
        self._add_info_parser(child_parser)
        self._add_overview_parser(child_parser)
        # self._add_reboot_parser(child_parser)
        self._add_graphdump_parser(child_parser)
        self._add_removegraph_parser(child_parser)
        if devicelog:
            devicelog.populate_parser(child_parser)
        self._add_modify_parser(child_parser)
        self._add_change_uuid_parser(child_parser)
        return parser

    def _add_info_parser(self, sub_parser):
        _act = sub_parser.add_parser("info", help="show device info")
        _act.set_defaults(childcom="info")
        _act.add_argument("--ip", default=False, action="store_true", help="enable display of IP-info [%(default)s]")
        _act.add_argument("--boot", default=False, action="store_true", help="enable display of bootrecords [%(default)s]")
        _act.add_argument("--join-logs", default=False, action="store_true", help="join logs [%(default)s]")
        self._add_many_device_option(_act)

    def _add_overview_parser(self, sub_parser):
        _act = sub_parser.add_parser("overview", help="show device structur (groups)")
        _act.add_argument("--devices", default=False, action="store_true", help="show devices [%(default)s]")
        _act.set_defaults(childcom="overview")

    def _add_graphdump_parser(self, sub_parser):
        _act = sub_parser.add_parser("graphdump", help="show graph structure")
        _act.set_defaults(childcom="graphdump")
        self._add_many_device_option(_act)

    def _add_removegraph_parser(self, sub_parser):
        _act = sub_parser.add_parser("removegraph", help="remove keys from graph structure")
        _act.set_defaults(childcom="removegraph")
        _act.add_argument("--key-re", type=str, default="use.a.re", help="regular expression for key removal [%(default)s]")
        _act.add_argument("--doit", default=False, action="store_true", help="enable deletiong [%(default)s]")
        self._add_many_device_option(_act)

    def _add_modify_parser(self, sub_parser):
        _act = sub_parser.add_parser("csvmodify", help="modify device(s) via CSV files")
        _act.set_defaults(childcom="csvmodify")
        _act.add_argument("--file", type=str, default="", help="CSV input file [%(default)s]")

    def _add_many_device_option(self, _parser):
        _parser.add_argument("-g", type=str, dest="groupname", default="", help="name of group [%(default)s]")
        _parser.add_argument("dev", type=str, nargs="*", help="device to query [%(default)s]", default="")

    def _add_change_uuid_parser(self, sub_parser):
        _act = sub_parser.add_parser("changeuuid", help="change the uuid of the local device")
        _act.set_defaults(childcom="changeuuid")
        _act.add_argument("--uuid", type=str, default="", help="new UUID [%(default)s], empty the generate a new one")

    def _execute(self, opt_ns):
        if opt_ns.childcom in ["changeuuid"]:
            from .changeuuid import main
            main(opt_ns)
        elif opt_ns.childcom in ["info", "graphdump", "removegraph"]:
            from .main import dev_main
            dev_main(opt_ns)
        elif opt_ns.childcom in ["csvmodify"]:
            from .csvmodify import main
            if not opt_ns.file:
                raise ValueError("no CSV-file given")
            elif not os.path.exists(opt_ns.file):
                raise SystemError("CSV-File '{}' does not exist".format(opt_ns.file))
            main(opt_ns)
        else:
            from .main import overview_main
            overview_main(opt_ns)
