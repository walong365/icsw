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

import time

from initat.tools import logging_tools

from .objects import LogCache, LogWatcher


def main(opt_ns):
    if opt_ns.verbose:
        print(
            "{:d} systems found: {}".format(
                len(opt_ns.systems),
                ", ".join(sorted(opt_ns.systems))
            )
        )
    print(
        "{:d} systems to use: {}".format(
            len(opt_ns.used_systems),
            ", ".join(sorted(opt_ns.used_systems))
        )
    )
    if opt_ns.with_nodes:
        if opt_ns.verbose:
            print(
                "{} found: {}".format(
                    logging_tools.get_plural("node", len(opt_ns.nodes)),
                    ", ".join(sorted(opt_ns.nodes))
                )
            )
        print(
            "{} to use: {}".format(
                logging_tools.get_plural("node", len(opt_ns.used_nodes)),
                ", ".join(sorted(opt_ns.used_nodes))
            )
        )
    _lc = LogCache(opt_ns)
    _lws = [_lw for _lw in [LogWatcher(opt_ns, _entry, _lc) for _entry in opt_ns.used_systems] if _lw.valid]
    if opt_ns.with_nodes:
        for _node in opt_ns.used_nodes:
            _lws.extend([_lw for _lw in [LogWatcher(opt_ns, _entry, _lc, node=_node) for _entry in opt_ns.used_systems] if _lw.valid])
    _lc.sort()
    _lc.prune()
    _lc.show()
    try:
        if opt_ns.follow:
            while True:
                time.sleep(0.25)
                [_lw.read() for _lw in _lws]
                _lc.sort()
                _lc.show()
    except KeyboardInterrupt:
        print("exit...")
        pass
