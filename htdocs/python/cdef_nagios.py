#!/usr/bin/python -Ot
# -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007 Andreas Lang-Nevyjel, init.at
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

class ng_period(cdef_basics.db_obj):
    def __init__(self, name, idx, init_dict={}):
        time_ranges = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        cdef_basics.db_obj.__init__(self, name, idx)
        self.set_valid_keys(dict([(x, "s") for x in ["name", "alias"] + ["%srange" % (y) for y in time_ranges]]),
                            [])
        self.init_sql_changes({"table" : "ng_period",
                               "idx"   : self.idx})
        if init_dict:
            self.set_parameters(init_dict)
        self.used = 0
    def copy_instance(self):
        new_ng_p = ng_period(self.get_name(), self.get_idx())
        new_ng_p.copy_keys(self)
        return new_ng_p
            
class ng_contactgroup(cdef_basics.db_obj):
    def __init__(self, name, idx, init_dict={}):
        cdef_basics.db_obj.__init__(self, name, idx)
        self.set_valid_keys({"name"              : "s",
                             "alias"             : "s",
                             "device_groups"     : ("f", "ng_device_contact", "device_group"    ),
                             "members"           : ("f", "ng_ccgroup"       , "ng_contact"      ),
                             "service_templates" : ("f", "ng_cgservicet"    , "ng_service_templ")},
                            [])
        self.init_sql_changes({"table" : "ng_contactgroup",
                               "idx"   : self.idx})
        if init_dict:
            self.set_parameters(init_dict)
        self["device_groups"]     = []
        self["members"]           = []
        self["service_templates"] = []
    def add_member(self, member):
        if member not in self["members"]:
            self["members"].append(member)
    def delete_member(self, member):
        if member in self["members"]:
            self["members"].remove(member)
    def add_device_group(self, device_group):
        if device_group not in self["device_groups"]:
            self["device_groups"].append(device_group)
    def delete_device_group(self, device_group):
        if device_group in self["device_groups"]:
            self["device_groups"].remove(device_group)
    def add_service_template(self, service_template):
        if service_template not in self["service_templates"]:
            self["service_templates"].append(service_template)
    def delete_service_template(self, service_template):
        if service_template in self["service_templates"]:
            self["service_templates"].remove(service_template)
    def copy_instance(self):
        new_ng_g = ng_contactgroup(self.get_name(), self.get_idx())
        new_ng_g.copy_keys(self)
        return new_ng_g

class ng_contact(cdef_basics.db_obj):
    def __init__(self, name, idx, init_dict={}):
        cdef_basics.db_obj.__init__(self, name, idx)
        self.set_valid_keys({"user"          : "i",
                             "snperiod"      : "i",
                             "hnperiod"      : "i",
                             "snrecovery"    : "b",
                             "sncritical"    : "b",
                             "snwarning"     : "b",
                             "snunknown"     : "b",
                             "hnrecovery"    : "b",
                             "hndown"        : "b",
                             "hnunreachable" : "b"
                             },
                            [])
        self.init_sql_changes({"table" : "ng_contact",
                               "idx"   : self.idx})
        if init_dict:
            self.set_parameters(init_dict)
    def copy_instance(self):
        new_ng_g = ng_contact(self.get_name(), self.get_idx())
        new_ng_g.copy_keys(self)
        return new_ng_g
    def html_out_filter_snperiod(self, val, stuff):
        val = int(val)
        if val:
            return stuff["tp_tree"][val]["name"]
        else:
            return "<key %s not found>" % (str(val))
    def html_out_filter_hnperiod(self, val, stuff):
        val = int(val)
        if val:
            return stuff["tp_tree"][val]["name"]
        else:
            return "<key %s not found>" % (str(val))
    def html_out_filter_user(self, val, stuff):
        if val:
            return stuff["user_tree"][val]["login"]
        else:
            return "<key %s not found>" % (str(val))

class ng_service_template(cdef_basics.db_obj):
    def __init__(self, name, idx, init_dict={}):
        cdef_basics.db_obj.__init__(self, name, idx)
        self.set_valid_keys({"name"           : "s",
                             "volatile"       : "b",
                             "nsc_period"     : "i",
                             "nsn_period"     : "i",
                             "max_attempts"   : "i",
                             "check_interval" : "i",
                             "retry_interval" : "i",
                             "ninterval"      : "i",
                             "nrecovery"      : "b",
                             "ncritical"      : "b",
                             "nwarning"       : "b",
                             "nunknown"       : "b"
                             },
                            [])
        self.init_sql_changes({"table" : "ng_service_templ",
                               "idx"   : self.idx})
        if init_dict:
            self.set_parameters(init_dict)
    def copy_instance(self):
        new_ng_s = ng_service_template(self.get_name(), self.get_idx())
        new_ng_s.copy_keys(self)
        return new_ng_s
    def html_out_filter_nsc_period(self, val, stuff):
        val = int(val)
        if val:
            return stuff["tp_tree"][val]["name"]
        else:
            return "<key %s not found>" % (str(val))
    def html_out_filter_nsn_period(self, val, stuff):
        val = int(val)
        if val:
            return stuff["tp_tree"][val]["name"]
        else:
            return "<key %s not found>" % (str(val))

class ng_device_template(cdef_basics.db_obj):
    def __init__(self, name, idx, init_dict={}):
        cdef_basics.db_obj.__init__(self, name, idx)
        self.set_valid_keys({"name"             : "s",
                             "ng_service_templ" : "i",
                             "max_attempts"     : "i",
                             "ninterval"        : "i",
                             "ng_period"        : "i",
                             "nrecovery"        : "b",
                             "ndown"            : "b",
                             "nunreachable"     : "b"
                             },
                            [])
        self.init_sql_changes({"table" : "ng_device_templ",
                               "idx"   : self.idx})
        if init_dict:
            self.set_parameters(init_dict)
    def copy_instance(self):
        new_ng_d = ng_device_template(self.get_name(), self.get_idx())
        new_ng_d.copy_keys(self)
        return new_ng_d
    def html_out_filter_ng_period(self, val, stuff):
        val = int(val)
        if stuff["tp_tree"].has_key(val):
            return stuff["tp_tree"][val]["name"]
        else:
            return "<key %s not found>" % (str(val))
    def html_out_filter_ng_service_templ(self, val, stuff):
        val = int(val)
        if stuff["dt_tree"].has_key(val):
            return stuff["dt_tree"][val]["name"]
        else:
            return "<key %s not found>" % (str(val))
