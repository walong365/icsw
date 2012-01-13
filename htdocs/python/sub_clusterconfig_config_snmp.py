#!/usr/bin/python -Ot
# -*- coding: utf8 -*-
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2009 Andreas Lang-Nevyjel, init.at
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

import logging_tools
import html_tools
import tools
import cdef_config

class snmp_mib_vs(html_tools.validate_struct):
    def __init__(self, req, var_type_list, new_config_list):
        html_tools.validate_struct.__init__(self, req, "SNMP MIB",
                                            {"name"        : {"he"  : html_tools.text_field(req, "smn",  size=64, display_len=12),
                                                              "new" : 1,
                                                              "vf"  : self.validate_name,
                                                              "def" : ""},
                                             "descr"       : {"he"  : html_tools.text_field(req, "smd", size=128, display_len=30),
                                                              "vf"  : self.validate_descr,
                                                              "def" : "New SNMP Mib"},
                                             "mib"         : {"he"  : html_tools.text_field(req, "smm", size=128, display_len=40),
                                                              "def" : "1.2.3.4.5",
                                                              "vf"  : self.validate_mib},
                                             "rrd_key"     : {"he"  : html_tools.text_field(req, "smk", size=128, display_len=40),
                                                              "def" : "new.rrd.key"},
                                             "var_type"    : {"he"  : var_type_list,
                                                              "def" : "i"},
                                             "special_command" : {"he"  : html_tools.text_field(req, "smbspec", size=255, display_len=32),
                                                                  "def" : ""},
                                             "base"        : {"he"  : html_tools.text_field(req, "smbase", size=16, display_len=6),
                                                              "vf"  : self.validate_base,
                                                              "def" : 1},
                                             "factor"      : {"he"  : html_tools.text_field(req, "smfac", size=16, display_len=6),
                                                              "vf"  : self.validate_factor,
                                                              "def" : 1.0},
                                             "unit"        : {"he"  : html_tools.text_field(req, "smunit", size=16, display_len=6),
                                                              "def" : ""},
                                             "new_configs" : {"he"  : new_config_list,
                                                              "def" : [],
                                                              "vf"  : self.validate_new_configs},
                                             "del"         : {"he"  : html_tools.checkbox(req, "smr", auto_reset=1),
                                                              "del" : 1}})
        self.names = []
        self.__new_configs = new_config_list
    def validate_name(self):
        if self.new_val_dict["name"] in self.names:
            self.new_val_dict["name"] = self.old_val_dict["name"]
            raise ValueError, "already used"
        elif not self.new_val_dict["name"]:
            self.new_val_dict["name"] = self.old_val_dict["name"]
            raise ValueError, "must not be empty"
    def validate_descr(self):
        if not self.new_val_dict["descr"]:
            raise ValueError, "must not be empty"
    def validate_base(self):
        if not self.new_val_dict["base"]:
            raise ValueError, "must not be empty"
        if tools.is_number(self.new_val_dict["base"].strip()):
            ifac = int(self.new_val_dict["base"])
            if ifac > 0:
                self.new_val_dict["base"] = ifac
            else:
                raise ValueError, "must be > 0"
        else:
            raise ValueError, "not an integer"
    def validate_factor(self):
        if not self.new_val_dict["factor"]:
            raise ValueError, "must not be empty"
        try:
            ffac = float(self.new_val_dict["factor"].strip())
        except:
            raise ValueError, "not a float"
        else:
            if ffac > 0.:
                self.new_val_dict["factor"] = ffac
            else:
                raise ValueError, "must be > 0."
    def validate_mib(self):
        pass
    def validate_new_configs(self):
        def get_list(idx_f):
            if not idx_f:
                return "empty"
            else:
                return ", ".join([self.__new_configs.list_dict.get(x, {"name" : "key %d not found" % (x)})["name"] for x in idx_f])
        self.new_val_dict["new_configs"] = [x for x in self.new_val_dict["new_configs"] if self.__new_configs.list_dict.has_key(x)]
        self.old_b_val_dict["new_configs"] = get_list(self.old_val_dict["new_configs"])
        self.new_b_val_dict["new_configs"] = get_list(self.new_val_dict["new_configs"])
        
def show_snmp_options(req):
    low_submit = html_tools.checkbox(req, "sub")
    sub = low_submit.check_selection("")
    change_log = html_tools.message_log()
    snmp_mibs = tools.get_snmp_mibs(req.dc)
    sm_dict = tools.ordered_dict()
    for idx, stuff in snmp_mibs.iteritems():
        sm_dict[idx] = cdef_config.snmp_mib(stuff["name"], idx, stuff)
    nc_dict = tools.get_new_configs(req.dc)
    nc_sel_list = html_tools.selection_list(req, "snnc", multiple=1, size=4, sort_new_keys=0)
    for key, value in nc_dict.iteritems():
        nc_sel_list[key] = "%s [%s]" % (value["name"], value["description"])
    nc_sel_list.mode_is_normal()
    req.dc.execute("SELECT sc.snmp_mib,sc.new_config FROM snmp_config sc")
    for db_rec in req.dc.fetchall():
        if sm_dict.has_key(db_rec["snmp_mib"]) and nc_dict.has_key(db_rec["new_config"]):
            sm_dict[db_rec["snmp_mib"]].add_config(db_rec["new_config"])
    for idx, stuff in sm_dict.iteritems():
        sm_dict[idx].act_values_are_default()
    vt_list = html_tools.selection_list(req, "smvt", {}, sort_new_keys=0)
    for vt in ["float", "int"]:
        vt_list[vt[0]] = vt
    sm_vs = snmp_mib_vs(req, vt_list, nc_sel_list)
    sm_dict[0] = cdef_config.snmp_mib(sm_vs.get_default_value("name"), 0, sm_vs.get_default_dict())
    sm_vs.set_submit_mode(sub)
    for sm_idx in sm_dict.keys():
        sm_stuff = sm_dict[sm_idx]
        sm_vs.names = [sm_dict[x]["name"] for x in sm_dict.keys() if x != sm_idx and x]
        sm_vs.link_object(sm_idx, sm_stuff)
        sm_vs.set_delete_ok(sm_stuff.count == 0)
        sm_vs.check_for_changes()
        if not sm_vs.check_delete():
            sm_vs.process_changes(change_log, sm_dict)
    if sm_vs.get_delete_list():
        for del_idx in sm_vs.get_delete_list():
            change_log.add_ok("Deleted SNMP MIB '%s'" % (sm_dict[del_idx]["name"]), "SQL")
            del sm_dict[del_idx]
        sql_str = "DELETE FROM snmp_mib WHERE %s" % (" OR ".join(["snmp_mib_idx=%d" % (x) for x in sm_vs.get_delete_list()]))
        req.dc.execute(sql_str)
        sql_str = "DELETE FROM snmp_config WHERE %s" % (" OR ".join(["snmp_mib=%d" % (x) for x in sm_vs.get_delete_list()]))
        req.dc.execute(sql_str)

    req.write(change_log.generate_stack("Action log"))
    req.write(html_tools.gen_hline("%s defined" % (logging_tools.get_plural("SNMP MIB", len(sm_dict.keys()) - 1)), 2))
    sm_table = html_tools.html_table(cls="normalsmall")
    req.write(sm_table.get_header())
    sm_table[0]["class"] = "lineh"
    for what in ["Name", "refs/del", "Settings", "Config(s)"]:
        sm_table[None][0] = html_tools.content(what, type="th")
    sm_sf_dict = dict([(v["name"].lower(), k) for k, v in sm_dict.iteritems() if v["name"]])
    line_idx = 1
    for sm_stuff in [sm_dict[n] for n in [sm_sf_dict[n] for n in sorted(sm_sf_dict.keys())] + [0]]:
        line_idx = 1 - line_idx
        if not sm_stuff.get_idx():
            sm_table[0]["class"] = "lineh"
            sm_table[None][0 : 5] = html_tools.content("New SNMP MIB", type="th")
        req.write(sm_table.flush_lines(""))
        sm_table[0]["class"] = "line0%d" % (line_idx)
        sm_table[None:5][0] = html_tools.content(sm_vs.get_he("name"))
        if sm_stuff.get_idx():
            if sm_stuff.count:
                sm_table[None:5][0] = html_tools.content("%d" % (sm_stuff.count), cls="center")
            else:
                sm_table[None:5][0] = html_tools.content(sm_vs.get_he("del")    , cls="errormin")
            sm_table[None][0] = html_tools.content(["Descr: ", sm_vs.get_he("descr")], cls="left")
        else:
            sm_table[None][0 : 2] = html_tools.content(["Descr: ", sm_vs.get_he("descr")], cls="left")
        sm_table[None:5][0] = html_tools.content(sm_vs.get_he("new_configs"))
        sm_table[2]["class"] = "line0%d" % (line_idx)
        sm_table[None][sm_stuff.get_idx() and 3 or 2:3] = html_tools.content(["key: ", sm_vs.get_he("rrd_key")], cls="left")
        sm_table[0]["class"] = "line0%d" % (line_idx)
        sm_table[None][sm_stuff.get_idx() and 3 or 2:3] = html_tools.content(["MIB:", sm_vs.get_he("mib")], cls="left")
        sm_table[0]["class"] = "line0%d" % (line_idx)
        sm_table[None][sm_stuff.get_idx() and 3 or 2:3] = html_tools.content(["type: ", sm_vs.get_he("var_type"),
                                                                              ", unit:", sm_vs.get_he("unit"),
                                                                              ", base=", sm_vs.get_he("base"),
                                                                              ", factor=", sm_vs.get_he("factor")], cls="left")
        sm_table[0]["class"] = "line0%d" % (line_idx)
        sm_table[None][sm_stuff.get_idx() and 3 or 2:3] = html_tools.content(["special: ", sm_vs.get_he("special_command")], cls="left")
        req.write(sm_table.flush_lines(sm_stuff.get_suffix()))
    req.write(sm_table.get_footer())

    low_submit[""] = 1
    submit_button = html_tools.submit_button(req, "submit")
    submit_button.set_class("", "button")
    req.write("%s<div class=\"center\">%s</div>\n" % (low_submit.create_hidden_var(""),
                                                      submit_button("")))
