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
import sys
import process_tools
import os
import datetime
import time

global opts


def parse_args():
    global opts
    _mach_name = process_tools.get_machine_name(short=True)
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=str, default="/var/log/cluster/logging-server", help="root directory [%(default)s]")
    parser.add_argument("--machine", type=str, default=_mach_name, help="machine to use [%(default)s]")
    parser.add_argument("-n", type=int, default=400, help="show latest [%(default)d] lines")
    parser.add_argument("--format", type=str, default="%a %b %d %H:%M:%S %Y", help="argument for parsing loglines [%(default)s]")
    parser.add_argument("-f", dest="follow", default=False, action="store_true", help="enable follow mode [%(default)s]")
    opts = parser.parse_args()
    print opts
    rd = os.path.join(opts.root, opts.machine)
    if not os.path.isdir(rd):
        raise ValueError(
            "directory {} not found, possible machine names for root directory {}: {}".format(
                rd,
                opts.root,
                ", ".join(sorted([_entry for _entry in os.listdir(opts.root) if os.path.isdir(os.path.join(opts.root, _entry))])),
            )
        )
    opts.rootdir = rd
    opts.systems = [_entry for _entry in os.listdir(opts.rootdir) if not _entry.count(".") and not _entry.count("-server-direct")]
    max_system_len = max([len(_entry) for _entry in opts.systems])
    opts.line_format = "{{}} : {{:<{:d}s}} {{:<5s}} {{:<30s}} {{}}".format(max_system_len)


class LogLine(object):
    def __init__(self, system, line):
        self.system = system
        # print "L:", line.strip()
        _parts = line.split(":", 3)
        # print line
        # print "*", ":".join(_parts[:3])
        self.dt = datetime.datetime.strptime(":".join(_parts[:3]).strip(), opts.format)
        _info, _line = _parts[3].split(")", 1)
        self.line = _line.strip()
        self.level = _info.split("(")[0].strip()
        self.processinfo = _info.split("(")[1].strip()

    def append_line(self, line):
        self.line = "{}\n{}".format(self.line, line)

    def __unicode__(self):
        return opts.line_format.format(
            datetime.datetime.strftime(self.dt, opts.format),
            self.system,
            self.level,
            "({})".format(self.processinfo),
            self.line,
        )

    def __repr__(self):
        return unicode(self)


class LogWatcher(object):
    def __init__(self, sysname, logcache):
        self.name = sysname
        self.path = os.path.join(opts.rootdir, sysname)
        self.valid = True
        self.__logcache = logcache
        self.open()
        self.rewind()

    def open(self):
        try:
            self.fd = open(self.path)
        except:
            print("Cannot open {}: {}".format(self.path, process_tools.get_except_info()))
            self.valid = False
            self.fd = None

    def rewind(self):
        try:
            self.fd.seek(-100 * opts.n, 2)
        except:
            self.fd.seek(0, 0)
        _content = self.fd.read().split("\n", 1)[-1]
        self._interpret(_content)

    def read(self):
        self._interpret(self.fd.read())

    def _interpret(self, content):
        _prev_line = None
        for _line in content.split("\n"):
            _line = _line.strip()
            if _line:
                try:
                    _ll = LogLine(self.name, _line)
                except:
                    if _prev_line:
                        # some lines already present, append line to pure line content
                        _prev_line.append_line(_line)
                    else:
                        print(
                            "Error parsing line '{}' for system {}: {}".format(
                                _line,
                                self.name,
                                process_tools.get_except_info(),
                            )
                        )
                else:
                    self.__logcache.feed(_ll)
                    _prev_line = _ll

    def close(self):
        if self.fd:
            self.fd.close()

    def __unicode__(self):
        return u"LogWatcher for {}".format(self.name)

    def __repr__(self):
        return unicode(self)


class LogCache(object):
    def __init__(self):
        self.lines = []

    def feed(self, ll):
        self.lines.append(ll)

    def sort(self):
        self.lines = [_b for _a, _b in sorted([(_l.dt, _l) for _l in self.lines])]

    def prune(self):
        self.lines = self.lines[-opts.n:]

    def show(self):
        if self.lines:
            print("\n".join([unicode(_line) for _line in self.lines]))
            self.lines = []


def main():
    parse_args()
    print(
        "{:d} systems found: {}".format(
            len(opts.systems),
            ", ".join(sorted(opts.systems))
        )
    )
    _lc = LogCache()
    _lws = [_lw for _lw in [LogWatcher(_entry, _lc) for _entry in opts.systems] if _lw.valid]
    _lc.sort()
    _lc.prune()
    _lc.show()
    if opts.follow:
        while True:
            time.sleep(1)
            [_lw.read() for _lw in _lws]
            _lc.sort()
            _lc.show()


if __name__ == "__main__":
    main()
