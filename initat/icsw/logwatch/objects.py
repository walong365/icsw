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

import os
import datetime
import stat

from initat.tools import process_tools


class LogLine(object):
    microsecond = 0

    def __init__(self, format, line_format, system, device, node, line):
        self.system = system
        self.device = device
        self.node = node or "---"
        self.__line_format = line_format
        # print "L:", line.strip()
        _parts = line.split(":", 3)
        # ensure unique datetimes
        LogLine.microsecond += 1
        self.dt = datetime.datetime.strptime(
            "{} {:06d}".format(":".join(_parts[:3]).strip(), LogLine.microsecond),
            "{} %f".format(format)
        )
        self.datetime = datetime.datetime.strftime(self.dt, format)
        _info, _line = _parts[3].split(")", 1)
        self.msg = _line.rstrip()
        self.level = _info.split("(")[0].strip()
        self.process = _info.split("(")[1].strip()

    def append_msg(self, msg):
        self.msg = "{}\n{}".format(self.msg, msg)

    def __unicode__(self):
        return self.__line_format.format(**self.__dict__)

    def __repr__(self):
        return unicode(self)


class LogWatcher(object):
    def __init__(self, opt_ns, sysname, logcache, node=None):
        self.opt_ns = opt_ns
        print self.opt_ns
        self.device = opt_ns.machine
        self.name = sysname
        self.node = node
        if self.node:
            self.path = os.path.join(self.opt_ns.rootdir, "{}.d".format(sysname), self.node)
        else:
            self.path = os.path.join(self.opt_ns.rootdir, sysname)
        self.valid = True
        self.__logcache = logcache
        self.open()
        if self.valid:
            self.rewind()

    def open(self):
        try:
            self.fd = open(self.path)
        except:
            if self.opt_ns.verbose:
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
            self.fd.seek(-100 * self.opt_ns.n, 2)
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
                    _ll = LogLine(self.opt_ns.format, self.opt_ns.line_format, self.name, self.device, self.node, _line)
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
    def __init__(self, opt_ns):
        self.lines = []
        self.opt_ns = opt_ns

    def feed(self, ll):
        self.lines.append(ll)

    def sort(self):
        self.lines = [_b for _a, _b in sorted([(_l.dt, _l) for _l in self.lines])]

    def prune(self):
        self.lines = self.lines[-self.opt_ns.n:]

    def show(self):
        if self.lines:
            print("\n".join([unicode(_line) for _line in self.lines]))
            self.lines = []

