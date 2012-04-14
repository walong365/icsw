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

import logging_tools
import html_tools
import tools
import cdef_config

class new_config_type_vs(html_tools.validate_struct):
    def __init__(self, req):
        html_tools.validate_struct.__init__(self, req, "config_type",
                                            {"name"        : {"he"  : html_tools.text_field(req, "ctn",  size=64, display_len=40),
                                                              "new" : 1,
                                                              "vf"  : self.validate_name,
                                                              "def" : ""},
                                             "description" : {"he"  : html_tools.text_field(req, "ctd", size=128, display_len=40),
                                                              "vf"  : self.validate_descr,
                                                              "def" : "New config type"},
                                             "del"         : {"he"  : html_tools.checkbox(req, "ctr", auto_reset=1),
                                                              "del" : 1}})
        self.names = []
    def validate_name(self):
        if self.new_val_dict["name"] in self.names:
            self.new_val_dict["name"] = self.old_val_dict["name"]
            raise ValueError, "already used"
        elif not self.new_val_dict["name"]:
            self.new_val_dict["name"] = self.old_val_dict["name"]
            raise ValueError, "must not be empty"
    def validate_descr(self):
        if not self.new_val_dict["description"]:
            raise ValueError, "must not be empty"
        
def show_config_type_options(req):
    low_submit = html_tools.checkbox(req, "sub")
    sub = low_submit.check_selection("")
    change_log = html_tools.message_log()
    new_config_types = tools.get_new_config_types(req.dc)
    if not new_config_types:
        change_log.add_ok("Adding default config_types", "ok")
        req.dc.execute("INSERT INTO new_config_type VALUES%s" % (",".join(["(0,'%s','%s',null)" % (x, y) for x, y in [("soft", "Software settings"),
                                                                                                                      ("hard", "Hardware setting")]]
                                                                          )))
        new_config_types = tools.get_new_config_types(req.dc)
    ct_dict = tools.ordered_dict()
    for idx, stuff in new_config_types.iteritems():
        ct_dict[idx] = cdef_config.new_config_type(stuff["name"], idx, stuff)
    c_dict = tools.ordered_dict()
    req.dc.execute("SELECT nc.* FROM new_config nc ORDER BY nc.name")
    for db_rec in req.dc.fetchall():
        idx = db_rec["new_config_idx"]
        c_dict[idx] = cdef_config.new_config(db_rec["name"], idx, db_rec)
    ct_vs = new_config_type_vs(req)
    ct_dict[0] = cdef_config.new_config_type(ct_vs.get_default_value("name"), 0, ct_vs.get_default_dict())
    for ct_idx in ct_dict.keys():
        ct_stuff = ct_dict[ct_idx]
        ct_stuff.count = len([1 for k, v in c_dict.iteritems() if k and v["new_config_type"] == ct_idx])
        ct_vs.names = [ct_dict[x]["name"] for x in ct_dict.keys() if x != ct_idx and x]
        ct_vs.link_object(ct_idx, ct_stuff)
        ct_vs.set_delete_ok(ct_stuff.count == 0)
        ct_vs.check_for_changes()
        if not ct_vs.check_delete():
            ct_vs.process_changes(change_log, ct_dict)
    if ct_vs.get_delete_list():
        for del_idx in ct_vs.get_delete_list():
            change_log.add_ok("Deleted config_type '%s'" % (ct_dict[del_idx]["name"]), "SQL")
            del ct_dict[del_idx]
        sql_str = "DELETE FROM new_config_type WHERE %s" % (" OR ".join(["new_config_type_idx=%d" % (x) for x in ct_vs.get_delete_list()]))
        req.dc.execute(sql_str)

    req.write(change_log.generate_stack("Action log"))
    req.write(html_tools.gen_hline("%s defined" % (logging_tools.get_plural("config type", len(ct_dict.keys())-1)), 2))
    ct_table = html_tools.html_table(cls="normalsmall")
    req.write(ct_table.get_header())
    ct_table[0]["class"] = "lineh"
    for what in ["Name", "description", "refs/del"]:
        ct_table[None][0] = html_tools.content(what, type="th")
    ct_sf_dict = dict([(v["name"].lower(), k) for k, v in ct_dict.iteritems() if v["name"]])
    line_idx = 1
    for ct_stuff in [ct_dict[n] for n in [ct_sf_dict[n] for n in sorted(ct_sf_dict.keys())] + [0]]:
        line_idx = 1 - line_idx
        if not ct_stuff.get_idx():
            ct_table[0]["class"] = "lineh"
            ct_table[None][0 : 3] = html_tools.content("New config_type", type="th")
        ct_table[0]["class"] = "line0%d" % (line_idx)
        ct_table[None][0] = html_tools.content(ct_vs.get_he("name"))
        if ct_stuff.get_idx():
            ct_table[None][0] = html_tools.content(ct_vs.get_he("description"))
            if ct_stuff.count:
                ct_table[None][0] = html_tools.content("%d" % (ct_stuff.count), cls="center")
            else:
                ct_table[None][0] = html_tools.content(ct_vs.get_he("del")    , cls="errormin")
        else:
            ct_table[None][0 : 2] = html_tools.content(ct_vs.get_he("description"))
        req.write(ct_table.flush_lines(ct_stuff.get_suffix()))
    req.write(ct_table.get_footer())

    low_submit[""] = 1
    submit_button = html_tools.submit_button(req, "submit")
    submit_button.set_class("", "button")
    req.write("%s<div class=\"center\">%s</div>\n" % (low_submit.create_hidden_var(""),
                                                      submit_button("")))
