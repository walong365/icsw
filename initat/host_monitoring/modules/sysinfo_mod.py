# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
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
""" system related information """

import commands

from initat.host_monitoring import hm_classes, limits
from initat.tools import process_tools
from initat.tools import logging_tools
from initat.tools import server_command


class _general(hm_classes.hm_module):
    def init_module(self):
        self.lsmod_command = process_tools.find_file("lsmod")


class lsmodinfo_command(hm_classes.hm_command):
    def __init__(self, name):
        hm_classes.hm_command.__init__(self, name)
        self.parser.add_argument("--required", dest="required", type=str, default="")

    def __call__(self, srv_com, cur_ns):
        _stat, _out = commands.getstatusoutput(self.module.lsmod_command)
        if _stat:
            srv_com.set_result("error getting module list", server_command.SRV_REPLY_STATE_ERROR)
        else:
            _lines = _out.split("\n")[1:]
            srv_com["modules"] = process_tools.compress_struct(
                [
                    (
                        _part[0],
                        int(_part[1]),
                        int(_part[2]),
                        [] if len(_part) == 3 else _part[3].split(",")
                    ) for _part in [_line.strip().split() for _line in _lines]
                ]
            )

    def interpret(self, srv_com, cur_ns):
        modules = process_tools.decompress_struct(srv_com["*modules"])
        if cur_ns.required:
            _required = set(cur_ns.required.split(","))
            _found = set([_part[0] for _part in modules])
            if _required & _found == _required:
                return limits.nag_STATE_OK, "{} found: {}".format(
                    logging_tools.get_plural("required module", len(_required)),
                    ", ".join(sorted(list(_required)))
                )
            else:
                _missing = _required - _found
                return limits.nag_STATE_CRITICAL, "{} required, {} missing: {}".format(
                    logging_tools.get_plural("module", len(_required)),
                    logging_tools.get_plural("module", len(_missing)),
                    ", ".join(sorted(list(_missing)))
                )
        else:
            return limits.nag_STATE_OK, "loaded {}".format(logging_tools.get_plural("module", len(modules)))


class mountinfo_command(hm_classes.hm_command):
    def __init__(self, name):
        hm_classes.hm_command.__init__(self, name)
        self.parser.add_argument("--mountpoint", type=str, default="/")
        self.parser.add_argument("--filesys", type=str, default="ext4")

    def __call__(self, srv_com, cur_ns):
        _mounts = [_line.strip().split() for _line in file("/proc/mounts", "r").read().split("\n") if _line.strip()]
        srv_com["mounts"] = process_tools.compress_struct(_mounts)

    def interpret(self, srv_com, cur_ns):
        _mounts = process_tools.decompress_struct(srv_com["*mounts"])
        _mount = [_entry for _entry in _mounts if _entry[1] == cur_ns.mountpoint]
        if len(_mount):
            _mount = _mount[0]
            if _mount[2] == cur_ns.filesys:
                return limits.nag_STATE_OK, "mountpoint {} has filesystem {}".format(cur_ns.mountpoint, cur_ns.filesys)
            else:
                return limits.nag_STATE_CRITICAL, "mountpoint {} has wrong filesystem: {} != {}".format(cur_ns.mountpoint, _mount[2], cur_ns.filesys)
        else:
            return limits.nag_STATE_CRITICAL, "mountpoint {} not found".format(cur_ns.mountpoint)
