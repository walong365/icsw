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
""" show and follow cluster logs """

import argparse
import os
import re

from initat.tools import process_tools

LOGSERVER_ROOT = "/var/log/cluster/logging-server"


class Parser(object):
    def link(self, sub_parser):
        return self._add_lw_parser(sub_parser)

    def _add_lw_parser(self, sub_parser):
        _mach_name = process_tools.get_machine_name(short=True)
        parser = sub_parser.add_parser("logwatch", help="watch icsw logs")
        parser.set_defaults(subcom="status", execute=self._execute)
        parser.add_argument("--root", type=str, default=LOGSERVER_ROOT, help="root directory [%(default)s]")
        parser.add_argument("--machine", type=str, default=_mach_name, help="machine to use [%(default)s]")
        parser.add_argument("-n", type=int, default=400, help="show latest [%(default)d] lines")
        parser.add_argument("--format", type=str, default="%a %b %d %H:%M:%S %Y", help="argument for parsing loglines [%(default)s]")
        parser.add_argument("-f", dest="follow", default=True, action="store_true", help="enable follow mode, always enabled [%(default)s]")
        parser.add_argument("-F", dest="follow", default=True, action="store_false", help="disable follow mode")
        parser.add_argument("--system-filter", type=str, default=".*", help="regexp filter for system [%(default)s]")
        parser.add_argument("--with-nodes", default=False, action="store_true", help="add node logs [%(default)s]")
        parser.add_argument("--node-filter", type=str, default=".*", help="regexp filter for nodes [%(default)s]")
        parser.add_argument("--verbose", default=False, action="store_true", help="enable verbose mode [%(default)s]")
        parser.add_argument("--show-unparseable", default=False, action="store_true", help="show unparseable lines [%(default)s]")
        return parser

    @staticmethod
    def get_default_ns():
        sub_parser = argparse.ArgumentParser().add_subparsers()
        def_ns = Parser().link(sub_parser).parse_args([])
        return def_ns

    def _execute(self, opt_ns):
        from .main import main
        rd = os.path.join(opt_ns.root, opt_ns.machine)
        if not os.path.isdir(rd):
            raise ValueError(
                "directory {} not found, possible machine names for root directory {}: {}".format(
                    rd,
                    opt_ns.root,
                    ", ".join(sorted([_entry for _entry in os.listdir(opt_ns.root) if os.path.isdir(os.path.join(opt_ns.root, _entry))])),
                )
            )
        opt_ns.rootdir = rd
        opt_ns.systems = [_entry for _entry in os.listdir(opt_ns.rootdir) if not _entry.count(".") and not _entry.count("-server-direct")]
        max_system_len = max([len(_entry) for _entry in opt_ns.systems])
        try:
            opt_ns.system_re = re.compile(opt_ns.system_filter)
        except:
            print("cannot interpret '{}', using default".format(opt_ns.system_filter))
            opt_ns.system_re = re.compile("^$")
        try:
            opt_ns.node_re = re.compile(opt_ns.node_filter)
        except:
            print("cannot interpret '{}', using default".format(opt_ns.node_filter))
            opt_ns.node_re = re.compile("^$")
        opt_ns.line_format = "{{datetime}} : {{device:<14s}}/{{system:<{:d}s}}/{{node:<14s}} {{level:<5s}} {{process:<20s}}{{msg}}".format(
            max_system_len
        )
        opt_ns.used_systems = [_entry for _entry in opt_ns.systems if opt_ns.system_re.match(_entry)]
        _nodes = set()
        if opt_ns.with_nodes:
            for _system in opt_ns.used_systems:
                _subdir = os.path.join(opt_ns.rootdir, "{}.d".format(_system))
                if os.path.isdir(_subdir):
                    for _entry in os.listdir(_subdir):
                        _last = _entry.split(".")[-1]
                        if _last not in ["gz", "bz2", "xz", "zip"]:
                            _nodes.add(_entry)
        opt_ns.nodes = sorted(list(_nodes))
        opt_ns.used_nodes = [_entry for _entry in opt_ns.nodes if opt_ns.node_re.match(_entry)]
        main(opt_ns)
