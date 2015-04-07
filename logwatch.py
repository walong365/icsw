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
import datetime
import time
import stat

import logging_tools
import process_tools

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
    parser.add_argument("--system-filter", type=str, default=".*", help="regexp filter for system [%(default)s]")
    parser.add_argument("--with-nodes", default=False, action="store_true", help="add node logs [%(default)s]")
    parser.add_argument("--node-filter", type=str, default=".*", help="regexp filter for nodes [%(default)s]")
    parser.add_argument("--verbose", default=False, action="store_true", help="enable verbose mode [%(default)s]")
    opts = parser.parse_args()
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
    try:
        opts.system_re = re.compile(opts.system_filter)
    except:
        print("cannot interpret '{}', using default".format(opts.system_filter))
        opts.system_re = re.compile("^$")
    try:
        opts.node_re = re.compile(opts.node_filter)
    except:
        print("cannot interpret '{}', using default".format(opts.node_filter))
        opts.node_re = re.compile("^$")
    opts.line_format = "{{datetime}} : {{device:<14s}}/{{system:<{:d}s}}/{{node:<14s}} {{level:<5s}} {{process:<20s}}{{msg}}".format(
        max_system_len
    )
    opts.used_systems = [_entry for _entry in opts.systems if opts.system_re.match(_entry)]
    _nodes = set()
    if opts.with_nodes:
        for _system in opts.used_systems:
            _subdir = os.path.join(opts.rootdir, "{}.d".format(_system))
            if os.path.isdir(_subdir):
                for _entry in os.listdir(_subdir):
                    _last = _entry.split(".")[-1]
                    if _last not in ["gz", "bz2", "xz", "zip"]:
                        _nodes.add(_entry)
    opts.nodes = sorted(list(_nodes))
    opts.used_nodes = [_entry for _entry in opts.nodes if opts.node_re.match(_entry)]


class LogLine(object):
    microsecond = 0

    def __init__(self, system, device, node, line):
        self.system = system
        self.device = device
        self.node = node or "---"
        # print "L:", line.strip()
        _parts = line.split(":", 3)
        # ensure unique datetimes
        LogLine.microsecond += 1
        self.dt = datetime.datetime.strptime(
            "{} {:06d}".format(":".join(_parts[:3]).strip(), LogLine.microsecond),
            "{} %f".format(opts.format)
        )
        self.datetime = datetime.datetime.strftime(self.dt, opts.format)
        _info, _line = _parts[3].split(")", 1)
        self.msg = _line.rstrip()
        self.level = _info.split("(")[0].strip()
        self.process = _info.split("(")[1].strip()

    def append_msg(self, msg):
        self.msg = "{}\n{}".format(self.msg, msg)

    def __unicode__(self):
        return opts.line_format.format(**self.__dict__)

    def __repr__(self):
        return unicode(self)


class LogWatcher(object):
    def __init__(self, sysname, device, logcache, node=None):
        self.name = sysname
        self.device = device
        self.node = node
        if self.node:
            self.path = os.path.join(opts.rootdir, "{}.d".format(sysname), self.node)
        else:
            self.path = os.path.join(opts.rootdir, sysname)
        self.valid = True
        self.__logcache = logcache
        self.open()
        if self.valid:
            self.rewind()

    def open(self):
        try:
            self.fd = open(self.path)
        except:
            if opts.verbose:
                print("Cannot open {}: {}".format(self.path, process_tools.get_except_info()))
            self.valid = False
            self.fd = None
        else:
            self.inode_num = os.stat(self.path)[stat.ST_INO]

    def close(self):
        if self.fd:
            self.fd.close()
            self.fd = None
            self.inode_num = 0

    def rewind(self):
        try:
            self.fd.seek(-100 * opts.n, 2)
        except:
            self.fd.seek(0, 0)
        _content = self.fd.read().split("\n", 1)[-1]
        self._interpret(_content)

    def read(self):
        try:
            cur_inode = os.stat(self.path)[stat.ST_INO]
        except:
            self.close()
        else:
            if cur_inode != self.inode_num:
                self.close()
        if self.fd is None:
            self.open()
        if self.fd is not None:
            self._interpret(self.fd.read())

    def _interpret(self, content):
        _prev_line = None
        LogLine.microsecond = 0
        for _line in content.split("\n"):
            _line = _line.strip()
            if _line:
                # print _line
                try:
                    _ll = LogLine(self.name, self.device, self.node, _line)
                except:
                    if _prev_line:
                        # some lines already present, append line to pure line content
                        _prev_line.append_msg(_line)
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
    if opts.verbose:
        print(
            "{:d} systems found: {}".format(
                len(opts.systems),
                ", ".join(sorted(opts.systems))
            )
        )
    print(
        "{:d} systems to use: {}".format(
            len(opts.used_systems),
            ", ".join(sorted(opts.used_systems))
        )
    )
    if opts.with_nodes:
        if opts.verbose:
            print(
                "{} found: {}".format(
                    logging_tools.get_plural("node", len(opts.nodes)),
                    ", ".join(sorted(opts.nodes))
                )
            )
        print(
            "{} to use: {}".format(
                logging_tools.get_plural("node", len(opts.used_nodes)),
                ", ".join(sorted(opts.used_nodes))
            )
        )
    _lc = LogCache()
    _lws = [_lw for _lw in [LogWatcher(_entry, opts.machine, _lc) for _entry in opts.used_systems] if _lw.valid]
    if opts.with_nodes:
        for _node in opts.used_nodes:
            _lws.extend([_lw for _lw in [LogWatcher(_entry, opts.machine, _lc, node=_node) for _entry in opts.used_systems] if _lw.valid])
    _lc.sort()
    _lc.prune()
    _lc.show()
    try:
        if opts.follow:
            while True:
                time.sleep(0.25)
                [_lw.read() for _lw in _lws]
                _lc.sort()
                _lc.show()
    except KeyboardInterrupt:
        print("exit...")
        pass


if __name__ == "__main__":
    main()
