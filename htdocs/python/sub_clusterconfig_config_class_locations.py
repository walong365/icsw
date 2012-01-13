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
import cdef_locations

class new_device_location_vs(html_tools.validate_struct):
    def __init__(self, req):
        new_dict = {"location"  : {"he"  : html_tools.text_field(req, "ndl",  size=127, display_len=16),
                                   "new" : 1,
                                   "vf"  : self.validate_location,
                                   "def" : ""},
                    "del"         : {"he"  : html_tools.checkbox(req, "dld", auto_reset=True),
                                     "del" : 1}}
        html_tools.validate_struct.__init__(self, req, "Device location", new_dict)
    def validate_location(self):
        if self.new_val_dict["location"] in self.locations:
            self.new_val_dict["location"] = self.old_val_dict["location"]
            raise ValueError, "already used"
        elif not self.new_val_dict["location"].strip():
            raise ValueError, "must not be empty"

class location_tree(object):
    def __init__(self, req, change_log):
        self.__req = req
        self.__change_log = change_log
        self.__locations = {}
        self.vs = new_device_location_vs(self.__req)
        self._read_locations()
    def _read_locations(self):
        self.__req.dc.execute("SELECT l.* FROM device_location l ORDER BY l.location")
        for db_rec in self.__req.dc.fetchall():
            self[db_rec["device_location_idx"]] = cdef_locations.device_location("device_location", db_rec["device_location_idx"], db_rec)
            self[db_rec["device_location_idx"]].act_values_are_default()
        self.__req.dc.execute("SELECT d.name, d.device_location FROM device d")
        found_keys = self.keys()
        for db_rec in self.__req.dc.fetchall():
            if db_rec["device_location"] in found_keys:
                self[db_rec["device_location"]].add_device(db_rec["name"])
        self[0] = cdef_locations.device_location(self.vs.get_default_value("location"), 0, self.vs.get_default_dict())
        self[0].act_values_are_default()
    def __getitem__(self, key):
        return self.__locations[key]
    def __setitem__(self, key, value):
        self.__locations[key] = value
    def __delitem__(self, key):
        del self.__locations[key]
    def keys(self):
        return self.__locations.keys()
    def values(self):
        return self.__locations.values()
    def get_ordered_idxs(self):
        name_lut = dict([(self[key]["location"], key) for key in self.keys() if key])
        return [name_lut[key] for key in sorted(name_lut.keys())]
    def check_locations(self):
        for loc_idx in self.keys():
            loc_stuff = self[loc_idx]
            self.vs.locations = [x["location"] for x in self.values() if x["location"] and x["location"] != loc_stuff["location"]]
            self.vs.link_object(loc_idx, loc_stuff)
            self.vs.check_for_changes()
            if not self.vs.check_delete() or loc_stuff.device_list:
                self.vs.process_changes(self.__change_log, self)
            self.vs.unlink_object()
        if self.vs.get_delete_list():
            for del_idx in self.vs.get_delete_list():
                self.__change_log.add_ok("Deleted device location '%s'" % (self[del_idx]["location"]), "SQL")
                del self[del_idx]
            self.__req.dc.execute("DELETE FROM device_location WHERE %s" % (" OR ".join(["device_location_idx=%d" % (x) for x in self.vs.get_delete_list()])))
    def show_location_table(self):
        loc_table = html_tools.html_table(cls="normalsmall")
        loc_table[0]["class"] = "line00"
        for what in ["Location", "delete", "Device list"]:
            loc_table[None][0] = html_tools.content(what, type="th")
        line_idx = 1
        for loc_idx in self.get_ordered_idxs() + [0]:
            loc_stuff = self[loc_idx]
            line_idx = 1 - line_idx
            loc_table[0]["class"] = "line1%d" % (line_idx)
            if loc_idx:
                dev_list = loc_stuff.device_list
                loc_table[None][0] = html_tools.content(self.vs.get_he("location"), loc_stuff.get_suffix(), cls="left")
                if dev_list:
                    loc_table[None][0] = html_tools.content("%d" % (len(dev_list)), cls="center")
                    loc_table[None][0] = html_tools.content(logging_tools.compress_list(dev_list), cls="left")
                else:
                    loc_table[None][0] = html_tools.content(self.vs.get_he("del"), loc_stuff.get_suffix(), cls="errormin")
                    loc_table[None][0] = html_tools.content("---", cls="center")
            else:
                loc_table[None][0:3] = html_tools.content(["New: ",
                                                           self.vs.get_he("location")], loc_stuff.get_suffix(), cls="left")
        self.__req.write("%s%s" % (html_tools.gen_hline("%s defined:" % (logging_tools.get_plural("Device location", len([key for key in self.keys() if key]))), 2),
                                   loc_table("")))
        
class new_device_class_vs(html_tools.validate_struct):
    def __init__(self, req):
        new_dict = {"classname" : {"he"  : html_tools.text_field(req, "ndcn",  size=127, display_len=16),
                                   "new" : 1,
                                   "vf"  : self.validate_classname,
                                   "def" : ""},
                    "priority"  : {"he"  : html_tools.text_field(req, "ndcp",  size=8, display_len=6),
                                   "vf"  : self.validate_priority,
                                   "def" : 0},
                    "del"       : {"he"  : html_tools.checkbox(req, "dcd", auto_reset=True),
                                   "del" : 1}}
        html_tools.validate_struct.__init__(self, req, "Deviceclass", new_dict)
    def validate_classname(self):
        if self.new_val_dict["classname"] in self.classnames:
            self.new_val_dict["classname"] = self.old_val_dict["classname"]
            raise ValueError, "already used"
        elif not self.new_val_dict["classname"].strip():
            raise ValueError, "must not be empty"
    def validate_priority(self):
        if tools.is_number(self.new_val_dict["priority"].strip()):
            self.new_val_dict["priority"] = int(self.new_val_dict["priority"].strip())
        else:
            raise ValueError, "not an integer"

class class_tree(object):
    def __init__(self, req, change_log):
        self.__req = req
        self.__change_log = change_log
        self.__classes = {}
        self.vs = new_device_class_vs(self.__req)
        self._read_classes()
    def _read_classes(self):
        self.__req.dc.execute("SELECT c.* FROM device_class c ORDER BY c.priority")
        for db_rec in self.__req.dc.fetchall():
            self[db_rec["device_class_idx"]] = cdef_locations.device_class("device_class", db_rec["device_class_idx"], db_rec)
            self[db_rec["device_class_idx"]].act_values_are_default()
        self.__req.dc.execute("SELECT d.name, d.device_class FROM device d")
        found_keys = self.keys()
        for db_rec in self.__req.dc.fetchall():
            if db_rec["device_class"] in found_keys:
                self[db_rec["device_class"]].add_device(db_rec["name"])
        self[0] = cdef_locations.device_class(self.vs.get_default_value("classname"), 0, self.vs.get_default_dict())
        self[0].act_values_are_default()
    def __getitem__(self, key):
        return self.__classes[key]
    def __setitem__(self, key, value):
        self.__classes[key] = value
    def __delitem__(self, key):
        del self.__classes[key]
    def keys(self):
        return self.__classes.keys()
    def values(self):
        return self.__classes.values()
    def get_ordered_idxs(self):
        name_lut = dict([(self[key]["priority"], key) for key in self.keys() if key])
        return [name_lut[key] for key in sorted(name_lut.keys())]
    def check_classes(self):
        for class_idx in self.keys():
            class_stuff = self[class_idx]
            self.vs.classnames = [x["classname"] for x in self.values() if x["classname"] and x["classname"] != class_stuff["classname"]]
            self.vs.link_object(class_idx, class_stuff)
            self.vs.check_for_changes()
            if not self.vs.check_delete() or class_stuff.device_list:
                self.vs.process_changes(self.__change_log, self)
            self.vs.unlink_object()
        if self.vs.get_delete_list():
            for del_idx in self.vs.get_delete_list():
                self.__change_log.add_ok("Deleted deviceclass '%s'" % (self[del_idx]["classname"]), "SQL")
                del self[del_idx]
            self.__req.dc.execute("DELETE FROM device_class WHERE %s" % (" OR ".join(["device_class_idx=%d" % (x) for x in self.vs.get_delete_list()])))
    def show_class_table(self):
        class_table = html_tools.html_table(cls="normalsmall")
        class_table[0]["class"] = "line00"
        for what in ["Location", "delete", "Device list", "Priority"]:
            class_table[None][0] = html_tools.content(what, type="th")
        line_idx = 1
        for class_idx in self.get_ordered_idxs() + [0]:
            class_stuff = self[class_idx]
            line_idx = 1 - line_idx
            class_table[0]["class"] = "line1%d" % (line_idx)
            if class_idx:
                dev_list = class_stuff.device_list
                class_table[None][0] = html_tools.content(self.vs.get_he("classname"), class_stuff.get_suffix(), cls="left")
                if dev_list:
                    class_table[None][0] = html_tools.content("%d" % (len(dev_list)), cls="center")
                    class_table[None][0] = html_tools.content(logging_tools.compress_list(dev_list), cls="left")
                else:
                    class_table[None][0] = html_tools.content(self.vs.get_he("del"), class_stuff.get_suffix(), cls="errormin")
                    class_table[None][0] = html_tools.content("---", cls="center")
            else:
                class_table[None][0:3] = html_tools.content(["New: ",
                                                             self.vs.get_he("classname")], class_stuff.get_suffix(), cls="left")
            class_table[None][0] = html_tools.content(self.vs.get_he("priority"), class_stuff.get_suffix(), cls="center")
        self.__req.write("%s%s" % (html_tools.gen_hline("%s defined:" % (logging_tools.get_plural("Device class", len([key for key in self.keys() if key]))), 2),
                                   class_table("")))
        
def show_options(req):
    change_log = html_tools.message_log()
    act_location_tree = location_tree(req, change_log)
    act_location_tree.check_locations()
    act_class_tree = class_tree(req, change_log)
    act_class_tree.check_classes()
    req.write(change_log.generate_stack("Action log"))
    act_location_tree.show_location_table()
    act_class_tree.show_class_table()
    low_submit = html_tools.checkbox(req, "sub")
    sub = low_submit.check_selection("")
    low_submit[""] = 1
    submit_button = html_tools.submit_button(req, "submit")
    submit_button.set_class("", "button")
    req.write("%s<div class=\"center\">%s</div>\n" % (low_submit.create_hidden_var(),
                                                      submit_button("")))
    
