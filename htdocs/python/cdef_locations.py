#!/usr/bin/python -Ot
# -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2007 Andreas Lang-Nevyjel, init.at
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
""" object definitions for locations """

import cdef_basics

class device_location(cdef_basics.db_obj):
    def __init__(self, name, idx, init_dict):
        cdef_basics.db_obj.__init__(self, name, idx, "dl")
        self.set_valid_keys({"location" : "s"},
                            [])
        self.init_sql_changes({"table" : "device_location",
                               "idx"   : self.idx})
        self.set_parameters(init_dict)
        self.device_list = []
    def copy_instance(self):
        new_nw = device_location(self.get_name(), self.get_idx(), {})
        new_nw.copy_keys(self)
        return new_nw
    def add_device(self, dev_name):
        if dev_name not in self.device_list:
            self.device_list.append(dev_name)

class device_class(cdef_basics.db_obj):
    def __init__(self, name, idx, init_dict):
        cdef_basics.db_obj.__init__(self, name, idx, "dc")
        self.set_valid_keys({"classname" : "s",
                             "priority"  : "i"},
                            [])
        self.init_sql_changes({"table" : "device_class",
                               "idx"   : self.idx})
        self.set_parameters(init_dict)
        self.device_list = []
    def copy_instance(self):
        new_nw = device_class(self.get_name(), self.get_idx(), {})
        new_nw.copy_keys(self)
        return new_nw
    def add_device(self, dev_name):
        if dev_name not in self.device_list:
            self.device_list.append(dev_name)
