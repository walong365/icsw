#!/usr/bin/python -Ot
# -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2001,2002,2003,2004,2005,2007 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
# 
# This file belongs to webfrontend
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

import cdef_basics

class inst_package(cdef_basics.db_obj):
    def __init__(self, name, idx):
        cdef_basics.db_obj.__init__(self, name, idx, "p")
        self.set_valid_keys({"arch"             : "s",
                             "packager"         : "s",
                             "pgroup"           : "s",
                             "summary"          : "s",
                             "group_idx"        : "i",
                             "version"          : "s",
                             "release"          : "s",
                             "buildtime"        : "i",
                             "buildhost"        : "s",
                             "native"           : "i",
                             "size"             : "i",
                             "inst_package_idx" : "i",
                             "present_on_disk"  : "i"},
                            [])
        self.init_sql_changes({"table" : "package",
                               "idx"   : self.idx})
        self.devices, self.devcount = ([], 0)
        self.show_it = 0
    def add_device(self, d_idx):
        self.devices.append(d_idx)
    def device_already_used(self, d_idx):
        return d_idx in self.devices

class instp_device(cdef_basics.db_obj):
    def __init__(self, name, idx):
        cdef_basics.db_obj.__init__(self, name, idx, "ip")
        self.set_valid_keys({"install"        : "i",
                             "upgrade"        : "i",
                             "del"            : "i",
                             "nodeps"         : "i",
                             "forceflag"      : "i",
                             "install_time"   : "i",
                             "inst_package"   : "i",
                             "device"         : "i",
                             "status"         : "s",
                             "error_line_num" : "i",
                             "error_lines"    : "s"},
                            [])
        self.init_sql_changes({"table" : "instp_device",
                               "idx"   : self.idx})
