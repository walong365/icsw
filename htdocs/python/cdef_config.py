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
import array

class new_config(cdef_basics.db_obj):
    def __init__(self, name, idx, init_dict={}):
        cdef_basics.db_obj.__init__(self, name, idx)
        self.set_valid_keys({"name"            : "s",
                             "description"     : "s",
                             "priority"        : "i",
                             "new_config_type" : "i",
                             "snmp_mibs"       : ("f", "snmp_config", "snmp_mib")},
                            [])
        self.init_sql_changes({"table" : "new_config",
                               "idx"   : self.idx})
        if init_dict:
            self.set_parameters(init_dict)
        self.vars, self.nagios, self.scripts = ({"int"  : {},
                                                 "str"  : {},
                                                 "blob" : {},
                                                 "bool" : {}},
                                                {},
                                                {})
        self["snmp_mibs"] = []
        self.set_new_config_var_suffix()
        self.set_new_ng_check_command_suffix()
        self.set_new_config_script_suffix()
        self.show = 1
        self.device_count = 0
    def add_snmp_mib(self, mi):
        if mi not in self["snmp_mibs"]:
            self["snmp_mibs"].append(mi)
            self["snmp_mibs"].sort()
    def delete_snmp_mib(self, mi):
        if mi in self["snmp_mibs"]:
            self["snmp_mibs"].remove(mi)
    def set_new_config_var_suffix(self):
        self.ncvs = "%snv" % (self.get_suffix())
    def get_new_config_var_suffix(self):
        return self.ncvs
    def set_new_ng_check_command_suffix(self):
        self.nccs = "%snc" % (self.get_suffix())
    def get_new_ng_check_command_suffix(self):
        return self.nccs
    def set_new_config_script_suffix(self):
        self.ncss = "%sns" % (self.get_suffix())
    def get_new_config_script_suffix(self):
        return self.ncss
    def add_var_stuff(self, what, in_dict):
        if what == "bool":
            v_type = "B"
        else:
            v_type = what[0]
        new_var = config_var(in_dict["name"], in_dict["config_%s_idx" % (what)], v_type)
        if in_dict["config_%s_idx" % (what)]  ==  0:
            new_var.set_suffix(self.get_new_config_var_suffix())
        new_var.set_valid_keys({"value" : {"int"  : "i",
                                           "str"  : "s",
                                           "blob" : "s",
                                           "bool" : "i"}[what]},
                               [])
        new_var.init_sql_changes({"table" : "config_%s" % (what),
                                  "idx"   : new_var.get_idx()})
        if type(in_dict["value"]) == type(array.array("c")):
            in_dict["value"] = in_dict["value"].tostring()
        new_var.set_parameters(in_dict)
##         if self.vars[what].has_key(new_var.get_idx()):
##             print "***"
##         else:
##             print "+++"
        self.vars[what][new_var.get_idx()] = new_var
        new_var.act_values_are_default()
    def add_nagios_stuff(self, in_dict):
        new_nag = config_nagios(in_dict["name"], in_dict["ng_check_command_idx"], in_dict)
        if in_dict["ng_check_command_idx"]  ==  0:
            new_nag.set_suffix(self.get_new_ng_check_command_suffix())
        self.nagios[new_nag.get_idx()] = new_nag
        new_nag.act_values_are_default()
    def add_script_stuff(self, in_dict):
        new_script = config_script(in_dict["name"], in_dict["config_script_idx"], in_dict)
        if in_dict["config_script_idx"]  ==  0:
            new_script.set_suffix(self.get_new_config_script_suffix())
        self.scripts[new_script.get_idx()] = new_script
        new_script.act_values_are_default()
    def copy_instance(self):
        new_ct = new_config(self.get_name(), self.get_idx())
        new_ct.copy_keys(self)
        return new_ct
    def post_create_func(self):
        self.set_new_config_var_suffix()
        self.set_new_ng_check_command_suffix()
        self.set_new_config_script_suffix()

class config_var(cdef_basics.db_obj):
    def __init__(self, name, idx, v_type):
        cdef_basics.db_obj.__init__(self, name, idx, v_type)
        self.set_valid_keys({"name"       : "s",
                             "descr"      : "s",
                             "new_config" : "i"},
                            ["new_config"])
        self.set_type(v_type)
    def get_type(self):
        return {"s" : "str",
                "i" : "int",
                "b" : "blob",
                "B" : "bool"}[self.pfpf]
    def set_type(self, tpe):
        #print self["name"], tpe
        self.pfpf = tpe[0]
        self.suffix = "%d%s" % (self.idx, self.pfpf)
        self.init_sql_changes({"table" : "config_%s" % (tpe),
                               "idx"   : self.get_idx()})
    def copy_instance(self, new_type):
        new_cv = config_var(self.get_name(), self.get_idx(), new_type[0])
        new_cv.copy_keys(self)
        return new_cv

class config_nagios(cdef_basics.db_obj):
    def __init__(self, name, idx, init_dict={}):
        cdef_basics.db_obj.__init__(self, name, idx, "n")
        self.set_valid_keys({"ng_service_templ"      : "i",
                             "name"                  : "s",
                             "command_line"          : "s",
                             "new_config"            : "i",
                             "description"           : "s",
                             "ng_check_command_type" : "i"},
                            ["new_config"])
        self.init_sql_changes({"table" : "ng_check_command",
                               "idx"   : self.get_idx()})
        if init_dict:
            self.set_parameters(init_dict)
    def copy_instance(self):
        new_cn = config_nagios(self.get_name(), self.get_idx())
        new_cn.copy_keys(self)
        return new_cn
    def html_out_filter_ng_service_templ(self, val, stuff):
        int_val = int(val)
        if int_val:
            return stuff["ng_service_templates"][int_val]["name"]
        else:
            return "default"

class config_script(cdef_basics.db_obj):
    def __init__(self, name, idx, init_dict={}):
        cdef_basics.db_obj.__init__(self, name, idx, "c")
        self.set_valid_keys({"name"       : "s",
                             "descr"      : "s",
                             "new_config" : "i",
                             "enabled"    : "b",
                             "new_config" : "i",
                             "priority"   : "i",
                             "value"      : "s",
                             "error_text" : "s"},
                            ["new_config", "value"])
        self.init_sql_changes({"table" : "config_script",
                               "idx"  :self.get_idx()})
        if init_dict:
            self.set_parameters(init_dict)
    def copy_instance(self):
        new_cs = config_script(self.get_name(), self.get_idx())
        new_cs.copy_keys(self)
        return new_cs

class new_config_type(cdef_basics.db_obj):
    def __init__(self, name, idx, init_dict={}):
        cdef_basics.db_obj.__init__(self, name, idx)
        self.set_valid_keys({"name"        : "s",
                             "description" : "s"},
                            [])
        self.init_sql_changes({"table" : "new_config_type",
                               "idx"   : self.idx})
        if init_dict:
            self.set_parameters(init_dict)
        self.show = 0
    def copy_instance(self):
        new_ct = new_config_type(self.get_name(), self.get_idx())
        new_ct.copy_keys(self)
        return new_ct

class snmp_mib(cdef_basics.db_obj):
    def __init__(self, name, idx, init_dict={}):
        cdef_basics.db_obj.__init__(self, name, idx)
        self.set_valid_keys({"name"            : "s",
                             "descr"           : "s",
                             "mib"             : "s",
                             "rrd_key"         : "s",
                             "unit"            : "s",
                             "base"            : "i",
                             "factor"          : "f",
                             "var_type"        : "s",
                             "special_command" : "s",
                             "new_configs"     : ("f", "snmp_config", "new_config")},
                            [])
        self.init_sql_changes({"table" : "snmp_mib",
                               "idx"   : self.idx})
        if init_dict:
            self.set_parameters(init_dict)
        self.count = 0
        self["new_configs"] = []
    def add_config(self, ci):
        if ci not in self["new_configs"]:
            self["new_configs"].append(ci)
            self.count += 1
    def delete_config(self, ci):
        if ci in self["new_configs"]:
            self["new_configs"].remove(ci)
            self.count -= 1
    def copy_instance(self):
        new_ct = snmp_mib(self.get_name(), self.get_idx())
        new_ct.copy_keys(self)
        return new_ct
