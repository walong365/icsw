#!/usr/bin/python-init -Ot
# -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008 Andreas Lang-Nevyjel, init.at
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
""" entities for generaring html pages """

import time
import types
import cgi
import sys
import array
import datetime
from basic_defs import DEBUG
global ALL_NAMES, ERR_NUM, SHOW_VAR_NAMES, VARS_SHOWN

def html_type(val):
    return cgi.escape(str(type(val)))

def info(val):
    return "value %s, type %s" % (str(val), html_type(val))
    
class message_log(object):
    def __init__(self):
        self.__lines = []
        self.__num_errors, self.__num_warnings, self.__num_lines = (0, 0, 0)
        self.set_table_class()
        self.set_layout("ilrlsc")
        self.set_pre_and_post_tags()
    def set_layout(self, lo_str):
        # lo_str ... layout_string, one or more of (i)info, (r)esult, (s)tat_str [error, ok, warn], (n)umber plus direction string (l,c,r)
        self.__layout_str = lo_str
        #def set_layout(
    def set_table_class(self, cl = "normalsmall"):
        self.tc = cl
    def add_errors(self, e_list):
        for info, result in e_list:
            self.add_error(info, result)
    def add_error(self, info, result):
        self.add(info, result, 0)
    def add_oks(self, ok_list):
        for info, result in ok_list:
            self.add_ok(info, result)
    def add_ok(self, info, result):
        self.add(info, result, 1)
    def log_ok(self, what, position=None):
        if type(what) != type([]):
            what = [what]
        for l_i, l_r in what:
            self.add(l_i, l_r, 1, position)
    def add_warns(self, w_list):
        for info, result in w_list:
            self.add_warn(info, result)
    def add_warn(self, info, result):
        self.add(info, result, 2)
    def add(self, info, result, state, position=None):
        # state is 0 for error, 1 for ok and 2 for warning
        if position is None:
            self.__lines.append((info, result, state))
        else:
            self.__lines.insert(position, (info, result, state))
        self.__num_lines += 1
        if not state:
            self.__num_errors += 1
        elif state == 2:
            self.__num_warnings += 1
    def set_rollback_mark(self):
        self.rollback_mark = self.__num_lines
    def rollback(self):
        del self.__lines[self.rollback_mark:]
    def get_num_errors(self):
        return self.__num_errors
    def get_num_lines(self):
        return self.__num_lines
    def get_num_warnings(self):
        return self.__num_warnings
    def set_pre_and_post_tags(self, pre_t="", post_t=""):
        self.__pre_tags = pre_t
        self.__post_tags = post_t
    def generate_stack(self, title="Messages", **args):
        show_only_errors   = args.get("show_only_errors"  , False)
        show_only_warnings = args.get("show_only_warnings", False)
        line_f, line_num = ([], 0)
        for info, result, status in self.__lines:
            show_line = False
            stat_str = {0 : "error",
                        1 : "ok",
                        2 : "warn"}[status]
            if show_only_errors:
                if stat_str in ["error"]:
                    show_line = True
            if show_only_warnings:
                if stat_str in ["warn"]:
                    show_line = True
            if not show_only_errors and not show_only_warnings:
                show_line = True
            if show_line:
                line_num += 1
                if self.tc == "normalsmall":
                    row_class_str = " class=\"%s\"" % (stat_str)
                else:
                    row_class_str = ""
                columns = []
                lo_idx = 0
                while lo_idx < len(self.__layout_str):
                    if result.lower() == stat_str and self.__layout_str[lo_idx:lo_idx+4] == "rlsc":
                        type_str, col_orientation = "sc"
                        td_cols = 2
                    else:
                        type_str, col_orientation = self.__layout_str[lo_idx:lo_idx+2]
                        td_cols = 1
                    lo_idx += 2 * td_cols
                    col_orientation = {"l" : "left",
                                       "c" : "center",
                                       "r" : "right"}[col_orientation]
                    if type_str == "i":
                        act_str = cgi.escape(info)
                    elif type_str == "r":
                        act_str = result
                    elif type_str == "s":
                        act_str = stat_str
                    elif type_str == "n":
                        act_str = "%d" % (line_num)
                    else:
                        act_str = "unknown type_str '%s'" % (type_str)
                    columns.append((col_orientation, td_cols, act_str))
                    # check for result == stat_str and (rlsc) in layout_str
                line_f.append("<tr%s>%s</tr>" % (row_class_str,
                                                 "".join(["<td%s%s>%s%s%s</td>" % (td_class and " class=\"%s\"" % (td_class) or "",
                                                                                   td_cols > 1 and " colspan=\"%d\"" % (td_cols) or "",
                                                                                   self.__pre_tags,
                                                                                   td_str,
                                                                                   self.__post_tags) for td_class, td_cols, td_str in columns])))
        if line_f:
            r_str = "%s<table class=\"%s\">\n%s\n</table>\n" % (title and gen_hline(title, 3) or "",
                                                                self.tc,
                                                                "\n".join(line_f))
        else:
            r_str = ""
        return r_str
            
class div_box(object):
    """ nested boxes, nice stuff """
    def __init__(self, **args):
        self.__childs = []
        self.__cls = args.get("cls", "")
        self.__next_right = args.get("next_right", True)
        self.__size = {"x" : args.get("width", 0),
                       "y" : args.get("height", 0)}
        if args.get("blind", False):
            self.__inner_space = args.get("inner_space", 0)
            self.__outer_space = 0
            self.__border_size = 0
        else:
            self.__inner_space = args.get("inner_space", 1)
            self.__border_size = args.get("border_size", 1)
            self.__outer_space = args.get("outer_space", 0)
        # space for content
        self.__top_space = args.get("top_space", 0)
        self.__content = args.get("content", "")
        self.__position = args.get("position", "absolute")
        if args.has_key("childs"):
            self.set_childs(args["childs"])
    def set_childs(self, childs):
        self.__childs = childs
    def next_is_right(self):
        return self.__next_right
    def set_pos(self, act_p):
        self.__pos = {"x" : act_p["x"] + self.__outer_space,
                      "y" : act_p["y"] + self.__outer_space}
    def layout(self):
        act_size = {"x" : 0,
                    "y" : 0}
        in_s = self.__inner_space
        corner_pos = {"x" : in_s,
                      "y" : in_s + self.__top_space}
        self.__pos = {"x" : 0,
                      "y" : 0}
        if self.__childs:
            nc_right = False
            for child in self.__childs:
                child.layout()
                sub_size = child._get_size()
                child.set_pos(corner_pos)
                if nc_right:
                    act_size["x"] += sub_size["x"] + 2 * in_s
                    act_size["y"] = max(act_size["y"], sub_size["y"] + 2 * in_s)
                else:
                    act_size["x"] = max(act_size["x"], sub_size["x"] + 2 * in_s)
                    act_size["y"] += sub_size["y"] + 2 * in_s
                nc_right = child.next_is_right()
                if nc_right:
                    corner_pos["x"] += sub_size["x"] + 2 * in_s
                else:
                    corner_pos["y"] += sub_size["y"] + 2 * in_s
            act_size["y"] += self.__top_space
        else:
            act_size = self.__size
        self.__act_size = act_size
    def _get_size(self):
        return {"x" : self.__act_size["x"] + 2 * self.__outer_space + 2 * self.__border_size,
                "y" : self.__act_size["y"] + 2 * self.__outer_space + 2 * self.__border_size}
    def get_style_string(self):
        s_dict = {"width"  : "%dpx" % (self.__act_size["x"]),
                  "height" : "%dpx" % (self.__act_size["y"]),
                  "left"   : "%dpx" % (self.__pos["x"]),
                  "top"    : "%dpx" % (self.__pos["y"]),
                  "border" : "%dpx solid" % (self.__border_size),
                  "text-align" : "center",
                  "valign" : "top"}
        return "; ".join(["%s:%s" % (key, value) for key, value in s_dict.iteritems()])
    def get_lines(self, level=0):
        ind_str = "  " * level
        act_lines = ["%s<div%s style=\"position:%s; %s;\">%s" % (ind_str,
                                                                 " class=\"%s\"" % (self.__cls) if self.__cls else "",
                                                                 self.__position,
                                                                 self.get_style_string(),
                                                                 self.__content)]
        for child in self.__childs:
            act_lines.extend(child.get_lines(level + 1))
        act_lines.append("%s</div>" % (ind_str))
        return act_lines

def box_test():
    cpu_core_width = 32
    cpu_core_height = 32
    sockets = 5
    dies_per_socket = 3
    cores_per_die = 1
    socket_divs = [div_box(cls="cpusocket",
                           inner_space=2,
                           top_space=12,
                           content="Socket%d" % (sock_num)) for sock_num in xrange(sockets)]
    for socket_div in socket_divs:
        die_divs = [div_box(cls="cpudie",
                            inner_space=1,
                            content="die%d" % (die_num),
                            top_space=12) for die_num in xrange(dies_per_socket)]
        socket_div.set_childs(die_divs)
        for die_div in die_divs:
            core_divs = [div_box(cls="cpucore", width=cpu_core_width,
                                 height=cpu_core_height,
                                 content="core%d" % (core_num)) for core_num in xrange(cores_per_die)]
            cache_div = div_box(cls="cpucache",
                                width=(cpu_core_width + 4) * cores_per_die - 2,
                                height=20,
                                content="cache")
            die_div.set_childs([div_box(blind=True,
                                        inner_space=1,
                                        childs=core_divs,
                                        next_right=False),
                                cache_div])
    cpu_b = div_box(position="relative",
                    childs=socket_divs,
                    top_space=14,
                    content="System")
    cpu_b.layout()
    print "\n".join(cpu_b.get_lines())

def init_html_vars():
    global ALL_NAMES, ERR_NUM, SHOW_VAR_NAMES, VARS_SHOWN
    ALL_NAMES = {}
    ERR_NUM = 0
    SHOW_VAR_NAMES = 0
    VARS_SHOWN = []
    
def timedelta_to_str(td):
    """ transforms a given timedelta-struct into a better
    readable string"""
    days, secs = (td.days, td.seconds)
    hours = int(secs / 3600)
    mins = int(secs - 3600 * hours) / 60
    secs = secs - 3600 * hours - 60 * mins
    return "%d:%02d:%02d" % (24 * days + hours, mins, secs)

class validate_struct(object):
    def __init__(self, req, name, simple_lut):
        self.__req = req
        self.set_info_name(name)
        # the internal simple lut is a dictionary with the form
        # name (of the db_entry): {'he'   : html_entity # html entitiy
        #                          'vf'   : <func>      # validate_func
        #                          'del'  : <>          # set for trigger-delete element
        #                          'new'  : <>          # set for trigger-new element
        #                          'ndb'  : <>          # has no db_entry
        #                          'pri'  : <pri>       # priority in list, defaults to 0
        #                          'def'  : default     # sets default_value for check_selection if not in db
        #                          'dbmr' : database map read function, if set is called instead of db-reference
        #                          'dbmw' : database map write function, if set is called instead of db-reference
        self.__simple_lut = {}
        # compounds (and db_info)
        self.__compounds = {}
        self.__compounds_db_info = {}
        # db_key to be set to trigger new object
        self.__new_db_key = None
        # name to trigger delete
        self.__del_name = None
        # list of non-db keys
        self.__non_db_keys = []
        # dict of db_keys with mapping function
        self.__db_keys_read_map, self.__db_keys_write_map = ({}, {})
        # database-fields to read for compound complexes
        self.__compound_db_keys = {}
        # parse simple_lut
        for key, value in simple_lut.iteritems():
            if type(value) == type({}):
                self.__simple_lut[key] = value
            elif type(value) == type(()):
                # compount lut, type: ((validate_func, {simple_lut_format}))
                val_func, sub_lut = value
                self.__compounds[key] = (val_func, [x for x in sub_lut.keys() if not x in ["database_info"]])
                self.__compounds_db_info[key] = sub_lut.get("database_info", None)
                for sk, sv in sub_lut.iteritems():
                    if sk == "database_info":
                        self.__compound_db_keys[key] = sv["field_name"]
                    else:
                        if type(sv) == type({}):
                            self.__simple_lut[sk] = sv
                        else:
                            self.__simple_lut[sk] = sv
            else:
                self.__simple_lut[key] = {"he" : value}
        pri_dict = {}
        for key, value in self.__simple_lut.iteritems():
            if self.__simple_lut[key].get("new", False):
                self.__new_db_key = key
            if self.__simple_lut[key].get("del", False):
                self.__del_name = key
            if self.__simple_lut[key].get("ndb", False):
                self.__non_db_keys.append(key)
            if self.__simple_lut[key].get("dbmr", None):
                self.__db_keys_read_map[key]  = self.__simple_lut[key]["dbmr"]
            if self.__simple_lut[key].get("dbmw", None):
                self.__db_keys_write_map[key] = self.__simple_lut[key]["dbmw"]
            pri_dict.setdefault(self.__simple_lut[key].get("pri", 0), []).append(key)
        self.__pris = sorted(pri_dict.keys())
        self.__pris.reverse()
        self.__lut_key_order = []
        for act_pri in self.__pris:
            self.__lut_key_order.extend(pri_dict[act_pri])
        self.__db_keys = [x for x in self.__simple_lut.keys() if x != self.__del_name and x not in self.__non_db_keys]
        self.__valid_db_keys = []
        self.init_delete_list()
        self.set_old_db_obj_idx()
        self.set_new_object_fields()
        self.set_submit_mode(0)
        self.set_map_function()
    def init_delete_list(self):
        # list of indices to delete
        self.__delete_list = []
    def set_map_function(self, map_func=None):
        self.__map_func = map_func
    def get_default_value(self, db_name):
        return self.__simple_lut[db_name]["def"]
    def set_default_value(self, db_name, val):
        self.__simple_lut[db_name]["def"] = val
    def get_default_dict(self):
        return dict([(k, v["def"]) for k, v in self.__simple_lut.iteritems() if v.has_key("def")] +
                    [(v.get("def_name", v["field_name"]), v["def"]) for k, v in self.__compounds_db_info.iteritems() if v and v.has_key("def")])
    def get_he_names(self):
        return [k for k, v in self.__simple_lut.iteritems() if v.has_key("he")]
    def set_submit_mode(self, sm):
        self.__submit_mode = sm
    def set_info_name(self, name):
        self.__name = name
    def set_old_db_obj_idx(self, idx=0):
        self.__old_db_obj_idx = idx
    def set_new_object_fields(self, nof={}):
        self.__new_object_fields = nof
    def link_object(self, db_idx, db_obj, ok_to_create=True):
        self.__db_idx = db_idx
        self.__db_obj = db_obj
        self.__old_db_obj = None
        self.__valid_db_keys = []
        self.__check_for_new_obj = (self.__db_obj.get_idx() <= 0)
        self.__ok_to_create = ok_to_create
        self.__suffix = self.__db_obj.get_suffix()
        # flag for delete
        self.__delete = False
        # flag for delte
        self.__create = False
        self.set_delete_ok()
        self.init_logs()
    def unlink_object(self):
        self.__db_idx, self.__db_obj = (None, None)
        self.__valid_db_keys = []
        self.__suffix = None
    def init_logs(self):
        self.add_logs = []
    def add_ok(self, ok_line, ok_state):
        self.add_logs.append(("o", ok_line, ok_state))
    def add_warn(self, warn_line, warn_state):
        self.add_logs.append(("w", warn_line, warn_state))
    def add_error(self, error_line, error_state):
        self.add_logs.append(("e", error_line, error_state))
    def get_suffix(self):
        return self.__suffix
    def is_new_object(self):
        return self.__check_for_new_obj
    def set_delete_ok(self, d_ok=True):
        self.__delete_ok = d_ok
    def check_delete(self):
        return self.__delete
    def check_create(self):
        return self.__create
    def get_delete_list(self):
        return self.__delete_list
    def get_he(self, db_name):
        return self.__simple_lut[db_name]["he"]
    def get_db_obj(self):
        return self.__db_obj
    def get_old_db_obj(self):
        return self.__old_db_obj
    def read_old_values(self):
        self.old_val_dict = {}
        # dict for beautified values
        self.old_b_val_dict = {}
        self.__valid_db_keys = []
        # read compound-database fields
        for compound_name, key in self.__compound_db_keys.iteritems():
            self.old_val_dict[key] = self.__db_obj[key]
        if self.__map_func:
            for key in self.__db_keys:
                ov = self.__db_obj[self.__map_func(key)]
                if type(ov) == type([]):
                    self.old_val_dict[key] = [x for x in ov]
                else:
                    self.old_val_dict[key] = ov
                self.__valid_db_keys.append(key)
        else:
            for key in self.__db_keys:
                ov = self.__db_obj[key]
                if type(ov) == type([]):
                    self.old_val_dict[key] = [x for x in ov]
                else:
                    self.old_val_dict[key] = ov
                self.__valid_db_keys.append(key)
        for key, func in self.__db_keys_read_map.iteritems():
            self.old_val_dict[key] = func(key)
    def check_for_changes(self):
        # at first read old values
        self.read_old_values()
        self.new_val_dict = {}
        # dict for beautified values
        self.new_b_val_dict = {}
        # clear additional arguments for copy_instance
        self.copy_instance_args = None
        # temporary error field
        self.__db_errors = []
        suffix = self.__suffix
        if self.__del_name and self.__simple_lut[self.__del_name]["he"].check_selection(suffix) and self.__delete_ok:
            self.__delete = True
            self.__delete_list.append(self.__db_idx)
        else:
            for db_name in self.__lut_key_order:
                lut_obj = self.__simple_lut[db_name]
                #for db_name, lut_obj in self.__simple_lut.iteritems():
                # None for non_db_keys
                old_val = self.old_val_dict.get(db_name, lut_obj.get("def", None))
                if type(old_val) == type(array.array("c")):
                    old_val_out = old_val.tostring()
                elif type(old_val) == datetime.datetime:
                    old_val_out = old_val.strftime("%Y-%m-%d %H:%M:%S")
                elif type(old_val) == datetime.timedelta:
                    old_val_out = timedelta_to_str(old_val)
                else:
                    old_val_out = old_val
                if lut_obj.has_key("he"):
                    if isinstance(lut_obj["he"], checkbox):
                        # checkboxes
                        new_val = lut_obj["he"].check_selection(suffix, old_val_out and not self.__submit_mode)
                    elif isinstance(lut_obj["he"], selection_list) and lut_obj["he"].get_option("multiple"):
                        # multiple selection lists
                        if self.__submit_mode:
                            new_val = lut_obj["he"].check_selection(suffix, [])
                        else:
                            new_val = lut_obj["he"].check_selection(suffix, old_val_out)
                    else:
                        new_val = lut_obj["he"].check_selection(suffix, old_val_out)
                    self.new_val_dict[db_name] = new_val
                else:
                    self.new_val_dict[db_name] = old_val
                if lut_obj.has_key("vf"):
                    try:
                        lut_obj["vf"]()
                    except ValueError, why:
                        self.new_val_dict[db_name] = old_val
                        self.__db_errors.append((lut_obj.get("new", 0), db_name, new_val, str(why)))
                        lut_obj["he"][suffix] = self.new_val_dict[db_name]
            # handle compounds
            for c_n, (c_f, c_keys) in self.__compounds.iteritems():
                try:
                    c_f()
                except ValueError, c_ret:
                    why, c_dict = c_ret
                    new_field = [1 for k in c_keys if self.__simple_lut[k].get("new", 0)]
                    for db_name, (db_new_val, db_err_val, he_list) in c_dict.iteritems():
                        new_val = self.new_val_dict[db_name]
                        self.new_val_dict[db_name] = db_new_val
                        self.__db_errors.append((new_field, db_name, new_val, str(why)))
                        for he_name, he_val in he_list:
                            self.get_he(he_name)[suffix] = he_val
    def set_new_values(self):
        if self.__map_func:
            for key in self.__db_keys:
                self.__db_obj[self.__map_func(key)] = self.new_val_dict[key]
        else:
            for key in self.__db_keys:
                self.__db_obj[key] = self.new_val_dict[key]
        for key, func in self.__db_keys_write_map.iteritems():
            self.__db_obj[key] = func(key, self.new_val_dict[key])
        # write compound-database fields
        for compound_name, key in self.__compound_db_keys.iteritems():
            self.__db_obj[key] = self.new_val_dict[key]
    def process_changes(self, change_log, i_dict):
        any_changes = False
        # set new values
        self.set_new_values()
        new_db_key = self.__new_db_key
        log_d, do_sql = ({}, False)
        if self.__check_for_new_obj:
            if new_db_key:
                # clear he for new_db_key
                new_he = self.__simple_lut[new_db_key]["he"]
                if isinstance(new_he, text_field):
                    new_he[self.__suffix] = ""
                else:
                    new_he[self.__suffix] = 0
                # step one: new_db_key he set ?
                self.__create = self.new_val_dict[new_db_key]
                # add all error fields
                for new_e, db_name, new_val, why_str in self.__db_errors:
                    if new_e and new_val:
                        # add error if the he has the flag new and the new_val was not the empty string
                        add_error = True
                    elif self.__create and not new_e:
                        # add error about non-new he's if we wanted to create a new instance 
                        add_error = True
                    else:
                        add_error = False
                    if add_error:
                        if self.__map_func:
                            self.__db_obj.change_error(self.__map_func(db_name), new_val, why_str)
                        else:
                            self.__db_obj.change_error(db_name, new_val, why_str)
                num_d = self.__db_obj.get_num_fields()
                # step two: only create if no errors reported
                self.__create = self.__create and not num_d["e"]
                if self.__create and self.__ok_to_create:
                    do_sql = True
                else:
                    self.__db_obj[new_db_key] = ""
                log_d = self.__db_obj.build_log_dict_n("set ", " for new %s" % (self.__name), self.old_b_val_dict, self.new_b_val_dict)
            else:
                # check for new obj but no new_db_key found -> ???
                pass
        else:
            # add all errors
            for new_e, db_name, new_val, why_str in self.__db_errors:
                if self.__map_func:
                    self.__db_obj.change_error(self.__map_func(db_name), new_val, why_str)
                else:
                    self.__db_obj.change_error(db_name, new_val, why_str)
            log_d = self.__db_obj.build_log_dict_c("altered ", " for %s" % (self.__name), self.old_b_val_dict, self.new_b_val_dict)
            do_sql = True
        change_log.add_errors(log_d.get("e", []))
        if do_sql:
            change_log.add_warns(log_d.get("w", []))
            change_log.add_oks(log_d["o"])
            for aw, al, add_str in self.add_logs:
                if aw == "e":
                    change_log.add_error(al, add_str)
                elif aw == "w":
                    change_log.add_warn(al, add_str)
                else:
                    change_log.add_ok(al, add_str)
            if self.__check_for_new_obj:
                # create new instance, phew...
                # copy instance
                if self.copy_instance_args:
                    self.__old_db_obj = self.__db_obj.copy_instance(self.copy_instance_args)
                else:
                    self.__old_db_obj = self.__db_obj.copy_instance()
                # set index of old instance to zero
                if self.__old_db_obj_idx:
                    self.__old_db_obj.set_suffix(self.__old_db_obj_idx)
                else:
                    self.__old_db_obj.set_idx(0)
                # set additional db_fields if required
                self.__db_obj.update(self.__new_object_fields)
##                 for k, v in self.__new_object_fields.iteritems():
##                     self.__db_obj[k] = v
                # create new instance
                self.__db_obj.commit_sql_changes(self.__req.dc, 1, 1, 0)
                # reread suffix
                self.__suffix = self.__db_obj.get_suffix()
                # set fields for __db_obj
                self.set_fields()
                # enqueue instances
                i_dict[self.__old_db_obj.get_idx()] = self.__old_db_obj
                i_dict[self.__db_obj.get_idx()]     = self.__db_obj
                # call special function (for instance to set new sub_idxs)
                if hasattr(self.__db_obj, "post_create_func"):
                    getattr(self.__db_obj, "post_create_func")()
                any_changes = True
            else:
                any_changes = self.__db_obj.commit_sql_changes(self.__req.dc, 1, 0, 0)
        return any_changes
    def set_fields(self, suff=None):
        # set fields from db-instance
        if suff is None:
            suffix = self.__suffix
        else:
            suffix = suff
        for key, value in self.__simple_lut.iteritems():
            if value.has_key("he"):
                if key not in self.__valid_db_keys:
                    if isinstance(value["he"], upload_field):
                        value["he"].check_selection(suffix, "")
                    else:
                        value["he"].check_selection(suffix, value.get("def", None))
                else:
                    if self.__map_func:
                        value["he"][suffix] = self.__db_obj[self.__map_func(key)]
                    else:
                        value["he"][suffix] = self.__db_obj[key]
    def init_fields(self, suffix, from_def = False):
        # clear fields from default values
        for key, value in self.__simple_lut.iteritems():
            if value.has_key("he"):
                if value.get("new", 0):
                    value["he"][suffix] = value.get("def", "")
                else:
                    if isinstance(value["he"], upload_field):
                        value["he"].check_selection(suffix, "")
                    else:
                        if from_def and value.has_key("def"):
                            value["he"].check_selection(suffix, value["def"])
                        else:
                            value["he"].check_selection(suffix)

class selection_class(object):
    """ selection class, new implementation
    Needs a name and a dictionary of the following form:
    key (used for http) => {'name':name,....}"""
    def __init__(self, req, name):
        self.req = req
        # if name starts with an asterisk (*) this is an auto-reset field
        self.name = name
        # class_dict stores a class-string for each suffix
        self.sel_dict, self.__class_dict = ({}, {})
##     def set_possible_values(self, pv=""):
##         # pv is one of (i)ntegers, (s)trings, (I) for List of integers, (S) for List of strings
##         self.__possible_values = pv
##     def get_possible_values(self):
##         return self.__possible_values
    def update(self, in_dict):
        for key, value in in_dict.iteritems():
            self[key] = value
    def set_class(self, suffix="", value=None):
        self.__class_dict[suffix] = value
    def get_class_str(self, suffix):
        if self.__class_dict.has_key(suffix):
            return " class=\"%s\"" % (self.__class_dict[suffix])
        else:
            return ""
    def del_sys_value(self, suffix=""):
        if self.req.sys_args.has_key(self.get_var_name(suffix)):
            del self.req.sys_args[self.get_var_name(suffix)]
    def set_sys_value(self, suffix="", value=None):
        self.req.sys_args[self.get_var_name(suffix)] = value
    def has_sys_value(self, suffix=""):
        return self.req.sys_args.has_key(self.get_var_name(suffix))
    def get_sys_value(self, suffix="", default=None):
        return self.req.sys_args.get(self.get_var_name(suffix), default)
    def get_name(self):
        return self.name
    def log_error(self, err_field):
        if type(err_field) == type(""):
            err_field = [err_field]
        for err_str in err_field:
            if self.req:
                self.req.info_stack.add_error(err_str, "html")
            else:
                print err_str
    def get_var_name(self, suffix="", create=False):
        global ALL_NAMES
        r_name = "%s%s" % (self.name, suffix)
        if r_name and create:
            if r_name in ALL_NAMES.keys():
                ALL_NAMES[r_name] += 1
                self.log_error("var_name '%s' used for the %d. time" % (r_name, ALL_NAMES[r_name]))
            else:
                ALL_NAMES[r_name] = 1
        return r_name
    def copy_selection(self, src_suffix, dst_suffix):
        # now done via self.set_sys_value(dst_suffix, get_sys_value(src_suffix))
        self.set_sys_value(dst_suffix, self.get_sys_value(src_suffix))
        #print "copy %s from %s to %s<br>" % (self.req.sys_args.get(self.get_var_name(src_suffix), None), self.get_var_name(src_suffix), self.get_var_name(dst_suffix))
    #    self.req.sys_args[self.get_var_name(dst_suffix)] = self.req.sys_args.get(self.get_var_name(src_suffix), None)
    def clear_var_name(self, suffix=""):
        global ALL_NAMES
        r_name = "%s%s" % (self.name, suffix)
        if r_name in ALL_NAMES.keys():
            del ALL_NAMES[r_name]
    def check_init(self, suffix, key=None):
        global ERR_NUM, SHOW_VAR_NAMES, VARS_SHOWN
        out_str, err_field = ("", [])
        if self.name:
            if SHOW_VAR_NAMES:
                if self.get_var_name(suffix) not in VARS_SHOWN:
                    VARS_SHOWN.append(self.get_var_name(suffix))
                    out_str += " [%s]" % (self.get_var_name(suffix))
            if key != None:
                if not self.sel_dict.has_key(suffix):
                    self.sel_dict[suffix] = {}
                    ERR_NUM += 1
                    out_str += "(%d)" % (ERR_NUM)
                    err_field.append("(%d) %s: suffix '%s' not initialised" % (ERR_NUM, self.get_name(), suffix))
##                 if not sel_dict.has_key(suffix]) != type({}):
##                     self.sel_dict[suffix] = {}
##                     ERR_NUM += 1
##                     out_str += "(%d)" % (ERR_NUM)
##                     err_field.append("(%d) %s: no dict for suffix '%s' (key '%s')" % (ERR_NUM, self.get_name(), suffix, key))
##                 if not self.sel_dict[suffix].has_key(key):
##                     ERR_NUM += 1
##                     out_str += "(%d)" % (ERR_NUM)
##                     err_field.append("(%d) %s: key '%s' added to suffix '%s'" % (ERR_NUM, self.get_name(), key, suffix))
##                     self.sel_dict[suffix][key] = {}
            if self.sel_dict.has_key(suffix):
                pass
            else:
                ERR_NUM += 1
                out_str += "(%d)" % (ERR_NUM)
                err_field.append("(%d) %s: suffix '%s' not initialised" % (ERR_NUM, self.get_name(), suffix))
                self.sel_dict[suffix] = ""
            if err_field:
                self.log_error(err_field)
        return out_str
        
class selection_list(selection_class):
    """ selection list class, new implementation
    Needs a name and a dictionary of the following form:
    key (used for http) => {'name':name,....}"""
    def __init__(self, req, name, sel_dict={}, **arg):
        selection_class.__init__(self, req, name)
        self.__options = dict([(k, arg.get(k, d)) for k, d in [("auto_reset"           , False),
                                                               ("sort_new_keys"        ,  True),
                                                               ("multiple"             , False),
                                                               ("size"                 ,     1),
                                                               ("initial_mode"         ,   "s"),
                                                               ("validate_set_value"   ,  True),
                                                               ("validate_get_value"   ,  True),
                                                               ("log_validation_errors",  True),
                                                               ("use_priority_key"     , False),
                                                               ("show_indices"         , False),
                                                               ("title"                ,    "")]])
        self.list_dict, self.__sort_list, self.idx_type = ({}, [], "")
        # keys only to be printed if suffix has a certain value (i.e suffix="")
        self.pe_keys = {}
        if sel_dict:
            self.mode_is_setup()
            self.update(sel_dict)
        self.restore_mode(self.__options["initial_mode"])
    def __nonzero__(self):
        return self.__sort_list and True or False
    def get_option(self, key):
        return self.__options[key]
    def __setitem__(self, key, value):
        if self.__mode == "s":
            self.__add_key(key, value)
        else:
            self.__set_selection(key, value)
    def __getitem__(self, key):
        if self.__mode == "s":
            return self.__get_key(key)
        else:
            return self.__get_selection(key)
    def __delitem__(self, key):
        if self.__mode == "s":
            self.__del_key(key)
        else:
            pass
    def mode_is_setup(self):
        self.__mode = "s"
    def mode_is_normal(self):
        self.__mode = "n"
    def get_mode(self):
        return self.__mode
    def restore_mode(self, mode):
        if mode == "s":
            self.mode_is_setup()
        else:
            self.mode_is_normal()
    def __set_index_type(self, it):
        if type(it) in [type(0), type(0L)]:
            its = "i"
        elif type(it) == type("s"):
            its = "s"
        else:
            print "Unknown type for %s: %s" % (self.get_name(), str(type(it)))
            its = None
        if not self.idx_type:
            self.idx_type = its
        elif self.idx_type != its:
            print "Error, index_type mismatch for %s (selection_list): %s (old) != %s (new)" % (self.get_name(),
                                                                                                self.idx_type,
                                                                                                its)
    def get_sort_list(self):
        return self.__sort_list
    def add_setup_key(self, key, stuff):
        self.__add_key(key, stuff)
    def __add_key(self, key, stuff):
        if type(stuff) == type(""):
            stuff = {"name" : stuff}
        # store index type
        self.__set_index_type(key)
        if self.list_dict.has_key(key):
            # overwrite (append) to existing key
            self.list_dict[key].update(stuff)
##             for k, v in stuff.iteritems():
##                 self.list_dict[key][k] = v
        else:
            self.list_dict[key] = stuff
            if self.__options["use_priority_key"]:
                self.__sort_list = [v for k, v in sorted([(v.get("pri", 0), k) for k, v in self.list_dict.iteritems()])]
            elif self.__options["sort_new_keys"]:
                self.__sort_list = sorted(self.list_dict.keys())
            else:
                self.__sort_list.append(key)
        # correct sel_dicts ?
        if stuff.get("update_sel_dict", 0):
            if self.__options["multiple"]:
                empty_value = []
            else:
                empty_value = None
            self.sel_dict[key] = empty_value
    def del_setup_key(self, key):
        self.__del_key(key)
    def __del_key(self, key):
        del self.list_dict[key]
        self.__sort_list.remove(key)
        for i_key in self.sel_dict.keys():
            if self.__options["multiple"]:
                if key in self.sel_dict[i_key]:
                    self.sel_dict[i_key].remove(key)
            else:
                if self.sel_dict[i_key] == key:
                    self.sel_dict[i_key] = 0
    def __get_key(self, key):
        return self.list_dict[key]
    def add_pe_key(self, sf, key, stuff):
        self.pe_keys.setdefault(key, []).append(sf)
        self.__add_key(key, stuff)
    def add_pe_key_ref(self, sf, key):
        self.pe_keys[key].append(sf)
    def create_hidden_var(self, suffix=""):
        if self.__options["multiple"]:
            sels = self.sel_dict[suffix]
        else:
            sels = [self.sel_dict[suffix]]
        return "\n".join(["<input type=hidden name=\"%s%s value=\"%s\" />" % (self.get_var_name(suffix),
                                                                              self.__options["multiple"] and "[]\"" or "\"",
                                                                              sel) for sel in sels])
    def __set_selection(self, suffix, in_key=None):
        if in_key is None:
            if self.__sort_list:
                in_key = self.__sort_list[0]
                if self.__options["multiple"]:
                    in_key = []
            else:
                # empty list
                if self.__options["multiple"]:
                    in_key = []
                else:
                    in_key = 0
        if self.__options["multiple"]:
            if type(in_key) != type([]):
                self.log_error("%s, suffix '%s': reset_key '%s' is not of type list (%s), trying to repair..." % (self.get_name(), suffix, str(in_key), str(type(in_key))))
                in_key = [in_key]
            if self.__options["validate_set_value"]:
                for in_key_part in in_key:
                    if in_key_part not in self.__sort_list:
                        self.log_error("multiple selection_list %s, suffix '%s': key '%s' not in key_list" % (self.get_name(), suffix, in_key_part))
        else:
            if self.__options["validate_set_value"]:
                if in_key not in self.__sort_list:
                    if self.__sort_list:
                        self.log_error("selection_list %s, suffix '%s': key '%s' not in key_list" % (self.get_name(), suffix, in_key))
                    else:
                        # empty list, no error
                        pass
        self.sel_dict[suffix] = in_key
    def __get_selection(self, suffix):
        return self.check_selection(suffix, None)
    def getitem(self, suffix, default):
        return self.check_selection(suffix, default)
    def check_selection(self, suffix = "", default=None):
        mult = self.__options["multiple"]
        if mult:
            empty_value = []
        else:
            empty_value = None
        # step one: value present ?
        if self.has_sys_value(suffix):
            value, had_value = (self.get_sys_value(suffix), True)
            if mult:
                # handle multi-dropboxes
                if not value:
                    value = empty_value
        else:
            had_value = False
            if default is not None:
                value = default
                if mult and type(value) != type([]):
                    self.log_error("%s suffix '%s': multiple selection_list but default is of type %s" % (self.get_name(), suffix, type(value)))
                    value = empty_value
            else:
                self.log_error("selection_list %s suffix '%s': not found in arguments and default not set" % (self.get_name(), suffix))
                value = empty_value
        if mult:
            if self.idx_type == "i":
                try:
                    value = [int(v) for v in value]
                except:
                    self.log_error("%s suffix '%s': exception raised %s (%s), value '%s'" % (self.get_name(), suffix, str(sys.exc_info()[0]), str(sys.exc_info()[1]), str(value)))
        else:
            if self.idx_type == "i":
                #print "****",value,html_type(value)
                try:
                    value = int(value)
                except:
                    self.log_error("%s suffix '%s': exception raised %s (%s), value '%s'" % (self.get_name(), suffix, str(sys.exc_info()[0]), str(sys.exc_info()[1]), str(value)))
        if had_value and self.__options["validate_get_value"]:
            if not mult:
                # right now we only handle non-multiple selection_lists
                if value not in self.__sort_list:
                    self.__set_selection(suffix)
                    new_value = self.sel_dict[suffix]
                    if self.__options["log_validation_errors"]:
                        if self.__options["multiple"]:
                            self.log_error("multiple selection_list %s suffix '%s': value '%s' not a valid value, correcting to '%s'" % (self.get_name(), suffix, str(value), str(new_value)))
                        else:
                            if self.__sort_list:
                                self.log_error("selection_list %s suffix '%s': value '%s' not a valid value, correcting to '%s'" % (self.get_name(), suffix, str(value), str(new_value)))
                            else:
                                # empty selection list, no error
                                pass
                    value = new_value
        self.sel_dict[suffix] = value
        if self.__options["auto_reset"]:
            self.__set_selection(suffix)
        return value
    def __call__(self, suffix = "", indent_level=0):
        keys_to_write = [x for x in self.__sort_list if not (x in self.pe_keys.keys() and not suffix in self.pe_keys.get(x, []))]
        if keys_to_write:
            out_str = ["".join([self.check_init(suffix, x) for x in keys_to_write])]
            out_str.append("<select name=\"%s%s%s%s%s>\n" % (self.get_var_name(suffix, True),
                                                             self.__options["multiple"] and "[]\" multiple" or "\"",
                                                             self.__options["size"] >  1 and " size=\"%d\"" % (self.__options["size"]) or "",
                                                             self.get_class_str(suffix),
                                                             self.__options["title"] and " title=\"%s\"" % (self.__options["title"]) or ""))
            if self.idx_type == "i":
                f_str = "<option value='%d'%s%s%s>%s</option>\n"
            else:
                f_str = "<option value='%s'%s%s%s>%s</option>\n"
            if self.__options["multiple"]:
                sel_keys = self.sel_dict[suffix]
            else:
                sel_keys = [self.sel_dict[suffix]]
            for key in keys_to_write:
                stuff = self.list_dict.get(key, {})
                name_str = cgi.escape(stuff.get("name", "not set"))
                if self.__options["show_indices"]:
                    name_str = "[%s] %s" % (str(key), name_str)
                out_str += f_str % (key,
                                    key in sel_keys and " selected " or "",
                                    (stuff.has_key("disabled") and not key in sel_keys) and " disabled" or "",
                                    stuff.has_key("class") and " class=\"%s\"" % (stuff["class"]) or "",
                                    name_str)
                comment, com_size = (stuff.get("comment", ""), stuff.get("comment_size", 20))
                if comment:
                    com_parts, pre_str, com_lines = ([x.strip() for x in comment.split()], "&nbsp;-&nbsp;", [])
                    while com_parts:
                        act_ol = ""
                        while len(act_ol) <= com_size and com_parts:
                            act_ol = "%s %s" % (act_ol, com_parts.pop(0))
                        if act_ol:
                            com_lines.append(pre_str + act_ol.strip())
                    out_str.append("\n".join(["<option disabled>%s</option>" % (x) for x in com_lines]))
            out_str.append("</select>")
        else:
            out_str = ["&lt;empty list&gt;"]
        return "".join(out_str)

class checkbox(selection_class):
    """ checkbox
    Needs a name and a default value"""
    def __init__(self, req, name, **arg):
        selection_class.__init__(self, req, name)
        self.__options = dict([(k, arg.get(k, d)) for k, d in [("auto_reset", False)]])
        #self.forced_set = {}
        self.sel_dict = {}
    def check_selection(self, suffix="", default=None):
        self.sel_dict[suffix] = False
        if self.has_sys_value(suffix) and self.get_sys_value(suffix):
            self.sel_dict[suffix] = True
        else:
            if default is not None:
                self.sel_dict[suffix] = default
        value = self.sel_dict[suffix]
        if self.__options["auto_reset"]:
            self[suffix] = False
        return value
    def create_hidden_var(self, suffix=""):
        return "%s%s" % (self.check_init(suffix),
                         self.sel_dict[suffix] and "<input type=hidden name=\"%s\" value=\"checked\" />" % (self.get_var_name(suffix)) or "")
    def __getitem__(self, suffix):
        return self.sel_dict[suffix]
    def __delitem__(self, suffix):
        del self.sel_dict[suffix]
    def __setitem__(self, suffix, value):
        self.sel_dict[suffix] = value
    def __call__(self, suffix="", indent_level=0):
        return "%s%s" % (self.check_init(suffix),
                         "<input type=checkbox name=\"%s\"%s%s/>" % (self.get_var_name(suffix, True),
                                                                     self.sel_dict.get(suffix, False) and " checked " or "",
                                                                     self.get_class_str(suffix)))
    
class radio_list(selection_class):
    """ button list class
    Needs a name and a dictionary of the following form:
    key (used for http) => {....}"""
    def __init__(self, req, name, sel_dict={}, **arg):
        selection_class.__init__(self, req, name)
        self.__options = dict([(k, arg.get(k, d)) for k, d in [("auto_reset"           , False),
                                                               ("sort_new_keys"        ,  True),
                                                               ("validate_get_value"   ,  True),
                                                               ("log_validation_errors",  True)]])
        self.list_dict, self.__sort_list, self.idx_type = ({}, [], "")
        self.update(sel_dict)
        #for k, s in sel_dict.iteritems():
        #    self[k] = s
        # dictionary about the keys already written
        self.__keys_written = {}
    def __set_index_type(self, it):
        if type(it) in [type(0), type(0L)]:
            its = "i"
        elif type(it) == type("s"):
            its = "s"
        else:
            print "Unknown type for %s: %s" % (self.get_name(), str(type(it)))
        if not self.idx_type:
            self.idx_type = its
        elif self.idx_type != its:
            print "Error, index_type mismatch for %s (radio_list): %s != %s" % (self.get_name(), self.idx_type, its)
    def __setitem__(self, key, stuff):
        # store index type
        if type(stuff) == type(""):
            stuff = {"name" : stuff}
        self.__set_index_type(key)
        if self.list_dict.has_key(key):
            # overwrite (append) to existing key
            self.list_dict[key].update(stuff)
            #for k, v in stuff.iteritems():
            #    self.list_dict[key][k] = v
        else:
            self.list_dict[key] = stuff
            if self.__options["sort_new_keys"]:
                self.__sort_list = sorted(self.list_dict.keys())
            else:
                self.__sort_list.append(key)
    def __set_selection(self, suffix="", in_key=None):
        if in_key is None:
            in_key = self.__sort_list[0]
        if in_key not in self.__sort_list:
            self.log_error("radio_list %s, suffix '%s': key '%s' not in key_list" % (self.get_name(), suffix, in_key))
        self.sel_dict[suffix] = in_key
    def __getitem__(self, suffix):
        return self.sel_dict[suffix]
    def check_selection(self, suffix = "", default=None):
        empty_value = None
        # step one: value present ?
        if self.has_sys_value(suffix):
            had_value = True
            value = self.get_sys_value(suffix)
        else:
            had_value = False
            if default is not None:
                value = default
            else:
                self.log_error("radio_list %s suffix '%s': not found in arguments and default not set" % (self.get_name(), suffix))
                value = empty_value
        if self.idx_type == "i":
            try:
                value = int(value)
            except:
                self.log_error("%s suffix '%s': exception raised %s (%s), value '%s'" % (self.get_name(), suffix, str(sys.exc_info()[0]), str(sys.exc_info()[1]), str(value)))
        if had_value and self.__options["validate_get_value"]:
            if value not in self.__sort_list:
                self.__set_selection(suffix)
                new_value = self.sel_dict[suffix]
                if self.__options["log_validation_errors"]:
                    self.log_error("radio_list %s suffix '%s': value '%s' not a valid value, correcting to '%s'" % (self.get_name(), suffix, str(value), str(new_value)))
                value = new_value
        self.sel_dict[suffix] = value
        if self.__options["auto_reset"]:
            self.__set_selection(suffix)
        return value
    def create_hidden_var(self, suffix=""):
        return "%s<input type=hidden name=\"%s\" value=\"%s\"/>" % (self.check_init(suffix),
                                                                    self.get_var_name(suffix),
                                                                    self[suffix])
    def __call__(self, suffix="", indent_level=0):
        key_to_write_idx = self.__keys_written.setdefault(suffix, 0)
        if not key_to_write_idx:
            register_write = True
            out_str = self.check_init(suffix)
            if self.sel_dict.has_key(suffix):
                # sel_dict has suffix in key_list, looks OK
                pass
            else:
                # check for default selection
                def_sel_idx = ([k for k, v in self.list_dict.iteritems() if v.get("default")] + [self.__sort_list[key_to_write_idx]])[0]
                self.log_error("%s, suffix '%s': setting '%s' as default radio selection" % (self.get_name(), suffix, str(def_sel_idx)))
                self.sel_dict[suffix] = def_sel_idx
        else:
            register_write = False
            out_str = ""
        if key_to_write_idx >= len(self.__sort_list):
            self.log_error("%s, suffix '%s': key_to_write_idx too big (%d >= %d)" % (self.get_name(), suffix, key_to_write_idx, len(self.__sort_list)))
        else:
            key_to_write = self.__sort_list[key_to_write_idx]
            stuff = self.list_dict[key_to_write]
            out_str += "%s<input type=radio name=\"%s\" value=\"%s\" %s%s/>%s" % (stuff.get("pre_str", ""),
                                                                                  self.get_var_name(suffix, register_write),
                                                                                  key_to_write,
                                                                                  self.sel_dict[suffix] == key_to_write and "checked " or "",
                                                                                  self.get_class_str(suffix),
                                                                                  stuff.get("post_str", ""))
            self.__keys_written[suffix] = key_to_write_idx + 1
        return out_str
    
class submit_button(selection_class):
    def __init__(self, req, name="submit", **args):
        selection_class.__init__(self, req, name)
        self.__options = dict([(k, args.get(k, d)) for k, d in [("ext_name", "")]])
    def __call__(self, suffix="", indent_level=0):
        return "<input type=submit value=\"%s\" %s%s/>\n" % (self.get_name(),
                                                             self.get_class_str(suffix),
                                                             self.__options.get("ext_name") and " name=\"%s\"" % (self.__options["ext_name"]) or "")
    def check_selection(self, suffix="", default=None):
        empty_value = ""
        if self.has_sys_value(suffix):
            value = self.get_sys_value(suffix)
        else:
            if default is None:
                value = empty_value
            else:
                value = default
        self.sel_dict[suffix] = value
        return value
    
class text_field(selection_class):
    """ textfield class
    Needs a name and a len/size"""
    def __init__(self, req, name, **args):
        selection_class.__init__(self, req, name)
        self.__options = dict([(k, args.get(k, d)) for k, d in [("auto_reset"             , False),
                                                                ("display_len"            ,    32),
                                                                ("size"                   ,    32),
                                                                ("is_password"            , False),
                                                                ("auto_convert_to_strings",  True),
                                                                ("title"                  ,    "")]])
        self.sel_dict = {}
    def check_selection(self, suffix="", default=None):
        empty_value = ""
        if self.has_sys_value(suffix):
            value = self.get_sys_value(suffix)
        else:
            if default is not None:
                if type(default) != type(""):
                    if not self.__options["auto_convert_to_strings"]:
                        self.log_error("%s suffix '%s': default '%s' is of type %s, repairing..." % (self.get_name(), suffix, default, type(default)))
                    value = str(default)
                else:
                    value = default
            else:
                self.log_error("text_field %s suffix '%s': not found in arguments and default not set" % (self.get_name(), suffix))
                value = empty_value
        self.sel_dict[suffix] = value
        if self.__options["auto_reset"]:
            self[suffix] = ""
        return value
    def __getitem__(self, suffix):
        return self.sel_dict[suffix]
    def __setitem__(self, suffix, value):
        if type(value) != type(""):
            if not self.__options["auto_convert_to_strings"]:
                self.log_error("%s suffix '%s': type of '%s' is %s (__setitem__)" % (self.get_name(), suffix, value, type(value)))
            self.sel_dict[suffix] = str(value)
        else:
            self.sel_dict[suffix] = value
    def __delitem__(self, suffix):
        self.sel_dict[suffix] = ""
    def create_hidden_var(self, suffix=""):
        return "%s<input type=hidden name=\"%s\" value=\"%s\"/>" % (self.check_init(suffix),
                                                                    self.get_var_name(suffix),
                                                                    self[suffix])
    def __call__(self, suffix="", indent_level=0):
        return "%s<input %sname=\"%s\" maxlength=\"%d\" size=\"%d\" value=\"%s\" %s%s/>" % (self.check_init(suffix),
                                                                                            self.__options["is_password"] and "type=password " or "",
                                                                                            self.get_var_name(suffix, True),
                                                                                            self.__options["size"],
                                                                                            self.__options["display_len"],
                                                                                            cgi.escape(self[suffix], 1),
                                                                                            self.__options["title"] and "title=\"%s\"" % (self.__options["title"]) or "",
                                                                                            self.get_class_str(suffix))

class toggle_field(selection_class):
    def __init__(self, req, name, **args):
        selection_class.__init__(self, req, name)
        self.__js_lines = []
        self.__req = req
        self.__name = name
        self.__text = args.get("text", "toggle field")
        # target, for instance 'a.' or 'tr#' (to select classes or ids)
        self.__target = args["target"]
    def __call__(self, suffix=""):
        c_name = self.get_var_name(suffix)
        self.__js_lines.extend(['$("a.%s").click(function(){$("%s%s").toggle(); return false;});' % (c_name, self.__target, c_name)])
         #self.__js_lines.extend(["$('a.%s').click(function(){$('a.%s').createAppend(" % (c_name, c_name),
        #                        "'tr', { className: 'exampleRow' }, [",
        #                        "'td', { align: 'center', style: 'color: white;' }, 'I was created by createAppend()!'",
        #                        "]",
        #                        ")});"])
        return "<a href=\"#\" class=\"%s\">%s</a>" % (c_name, self.__text)
    def get_span_element(self, suffix="", **args):
        shown = args.get("display", True)
        return "<span class=\"%s\"%s>" % (self.get_var_name(suffix),
                                          "" if shown else " style=\"display:none\"")
    def get_js_lines(self):
        if self.__js_lines:
            return "\n".join(["<script type=\"text/javascript\">"] + self.__js_lines + ["</script>", ""])
        else:
            return ""
        
class text_area(selection_class):
    """ textarea class
    Needs a name and a len/size"""
    def __init__(self, req, name, **arg):
        selection_class.__init__(self, req, name)
        self.__options = dict([(k, arg.get(k, d)) for k, d in [("auto_reset"  , False),
                                                               ("min_col_size",    30),
                                                               ("max_col_size",    80),
                                                               ("min_row_size",     3),
                                                               ("max_row_size",    10),
                                                               ("readonly"    , False)]])
    def __getitem__(self, suffix):
        return self.sel_dict[suffix]
    def __setitem__(self, suffix, value):
        self.sel_dict[suffix] = value
    def __delitem__(self, suffix):
        self.sel_dict[suffix] = ""
    def check_selection(self, suffix="", default=None):
        empty_value = ""
        if self.has_sys_value(suffix):
            value = self.get_sys_value(suffix)
        else:
            if default is None:
                self.log_error("text_area %s suffix '%s': not found in arguments and default not set" % (self.get_name(), suffix))
                value = empty_value
            else:
                value = default
        self.sel_dict[suffix] = value
        if self.__options["auto_reset"]:
            self[suffix] = ""
        return value
    def create_hidden_var(self, suffix=""):
        return "%s<input type=hidden name=\"%s\" value=\"%s\"/>" % (self.check_init(suffix),
                                                                    self.get_var_name(suffix),
                                                                    self[suffix])
    def __call__(self, suffix="", indent_level=0):
        act_cols = min([max([len(x) for x in self[suffix].split("\n")] + [self.__options["min_col_size"]]), self.__options["max_col_size"]])
        act_rows = min([max([len(self[suffix].split("\n"))] + [self.__options["min_row_size"]]), self.__options["max_row_size"]])
        return "%s<textarea name=\"%s\" cols=\"%d\" rows=\"%d\"%s%s>\n%s</textarea>" % (self.check_init(suffix),
                                                                                        self.get_var_name(suffix, True),
                                                                                        act_cols,
                                                                                        act_rows,
                                                                                        self.__options["readonly"] and " readonly" or "",
                                                                                        self.get_class_str(suffix),
                                                                                        cgi.escape(self[suffix], 1))

class upload_field(selection_class):
    """ upload_field class
    Needs a name and a len/size"""
    def __init__(self, req, name, **arg):
        selection_class.__init__(self, req, name)
        self.__options = dict([(k, arg.get(k, d)) for k, d in [("auto_reset" , False),
                                                               ("display_len",    32),
                                                               ("size"       ,    32),
                                                               ("is_password", False)]])
        self.sel_dict = {}
    def check_selection(self, suffix="", default=None):
        empty_value = ""
        if self.req.my_files.has_key(self.get_var_name(suffix)):
            sel_str, value = self.req.my_files[self.get_var_name(suffix)]
        else:
            if default is None:
                self.log_error("upload_field %s suffix '%s': not found in arguments and default not set" % (self.get_name(), suffix))
                value = empty_value
            else:
                value = default
        self.sel_dict[suffix] = value
        if self.__options["auto_reset"]:
            self[suffix] = ""
        return value
    def get_file_name(self, suffix=""):
        return self.req.my_files.get(self.get_var_name(suffix), ("", ""))[0]
    def __getitem__(self, suffix):
        return self.sel_dict[suffix]
    def __setitem__(self, suffix, value):
        self.sel_dict[suffix] = value
    def __delitem__(self, suffix):
        self.sel_dict[suffix] = ""
    def __call__(self, suffix="", indent_level=0):
        return "%s<input name=\"%s\" type=\"file\" maxlength=\"%d\" size=\"%d\" accept=\"text/*\" %s/>" % (self.check_init(suffix),
                                                                                                           self.get_var_name(suffix, True),
                                                                                                           self.__options["size"],
                                                                                                           self.__options["display_len"],
                                                                                                           self.get_class_str(suffix))

def gen_hline(what, h_class=1, escape=True, **args):
    if args.has_key("cls"):
        cls_str = " class=\"%s\"" % (args["cls"])
    else:
        cls_str = ""
    if escape:
        return "<h%d %s>%s</h%d>\n" % (h_class, cls_str, cgi.escape(what, 1), h_class)
    else:
        return "<h%d %s>%s</h%d>\n" % (h_class, cls_str, what, h_class)

class content(object):
    def __init__(self, what=None, suffix=None, **kwd):
        self.__content = what
        self.suffix = suffix
        self.set_content_type()
        # map from "cls" to "class"
        self.__add_tags = kwd.get("add_tags", "")
        if type(self.__add_tags) == type(""):
            self.__add_tags = [self.__add_tags]
        self.__attributes = dict([("class" if key == "cls" else key, value) for key, value in kwd.iteritems() if key not in ["add_tags"]])
        self.col_dict = {}
        self.set_width()
        self.set_height()
        #print "New content (type %s)" % (self.content_type)
    def set_attribute(self, key, value):
        self.__attributes[key] = value
    def set_content_type(self, ct="?"):
        self.content_type = ct
    def get_sub_content_type(self):
        return {"T" : "L",
                "L" : "C"}.get(self.content_type, "?")
    def set_width(self, width=1):
        self.width = width
    def get_width(self):
        return self.width
    def set_height(self, height=1):
        self.height = height
    def get_height(self):
        return self.height
    def set_table(self, table=None):
        self.__table = table
    def get_table(self):
        return self.__table
    def clear_table(self):
        self.__table = None
    def __del__(self):
        del self.__content
        del self.__attributes
        del self.col_dict
        #print "Del content (type %s)" % (self.content_type)
    def __setitem__(self, row, content):
        # for __getitem__/__setitem__:
        # start_idx == None: use actual row/line
        # start_idx == 0   : use next row/line
        if type(row) == type(""):
            if self.content_type == "L":
                act_table = self.get_table()
                start_line, end_line = act_table.get_act_lines()
                if start_line == end_line:
                    self.set_attribute(row, content)
                else:
                    for line in range(start_line, end_line + 1):
                        act_line = act_table[line]
                        act_line.set_attribute(row, content)
        else:
            act_table = self.get_table()
            if type(row) == types.SliceType:
                start_idx, stop_idx = (row.start, row.stop)
            else:
                start_idx, stop_idx = (row      , row     )
            if start_idx:
                pass
            else:
                if start_idx is None:
                    start_idx = act_table.row
                else:
                    start_idx = act_table.next_row
                stop_idx = start_idx + max(stop_idx, 1) - 1
            act_table.row      = start_idx
            act_table.next_row = stop_idx + 1
            height_start, height_stop = act_table.get_act_lines()
            set_errors = act_table.set_used_fields((height_start, height_stop), (start_idx, stop_idx))
            if not set_errors:
                self.col_dict[start_idx] = content
                self.col_dict[start_idx].set_content_type(self.get_sub_content_type())
                self.col_dict[start_idx].set_height(height_stop + 1 - height_start)
                self.col_dict[start_idx].set_width(stop_idx + 1 - start_idx)
        self.clear_table()
    def __getitem__(self, row):
        if type(row) == types.SliceType:
            start_idx, stop_idx = (row.start, row.stop)
        else:
            start_idx, stop_idx = (row      , row     )
        if start_idx:
            pass
        else:
            if start_idx is None:
                start_idx = self.line
            else:
                start_idx = self.next_line
                if self.auto_cr:
                    self.row, self.next_row = (0, 1)
            stop_idx = start_idx + max(stop_idx, 1) - 1
        self.line      = start_idx
        self.next_line = stop_idx + 1
        sub_cont = content()
        sub_cont.set_content_type(self.get_sub_content_type())
        self.col_dict.setdefault(start_idx, sub_cont)
        self.col_dict[start_idx].set_table(self)
        self.__act_lines = (start_idx, stop_idx)
        return self.col_dict[start_idx]
    def get_act_lines(self):
        return self.__act_lines
    def get_attributes(self):
        self.clear_table()
        a_field = ["%s=\"%s\"" % (name, value) for name, value in self.__attributes.iteritems() if name not in ["type", "beautify"]] + \
            self.__add_tags
        if a_field:
            return " ".join([""] + a_field)
        else:
            return ""
    def get_type(self):
        return self.__attributes.get("type", "td")
    def beautify_it(self):
        return self.__attributes.get("beautify", True)
    def __call__(self, suffix="", indent_level=0):
        if 0:
            what_list, out_list = (self.__content, ["size: h %d x w %d, " % (self.get_height(), self.get_width())])
        else:
            what_list, out_list = (self.__content, [])
        if type(what_list) == type(()):
            what_list = list(what_list)
        if type(what_list) != type([]):
            what_list = [what_list]
        for what in what_list:
            if type(what) == type(""):
                out_list.append(what)
            elif type(what) in [type(0), type(0L)]:
                out_list.append("%d" % (what))
            # hack for python 2.4 (SUSE 9.3)
            elif type(what) == types.InstanceType or str(type(what)).count("<class"):
                if self.suffix is None:
                    loc_suffix = suffix
                else:
                    loc_suffix = self.suffix
                out_list.append(what(loc_suffix))
            elif type(what) == type(False):
                out_list.append(str(what))
            elif type(what) == type(None):
                out_list.append("NONE")
            else:
                out_list.append(what)
        return "".join(out_list)
        
class html_table(content):
    def __init__(self, **args):
        content.__init__(self, None, **args)
        self.set_content_type("T")
        self.__check_for_thead = args.get("create_thead", False)
        # used field usage: 2 ... start of table element, 1 ... used by rowspan/colspan, 0 ... unused
        self.__used_field = {}
        self.__line_num, self.__row_num = (0, 0)
        self.set_cursor()
        self.set_auto_cr()
        self.__header_written, self.__footer_written = (False, False)
        self.__thead_written, self.__is_thead = (False, False)
    def get_cursor(self):
        return (self.line     , self.row     )
    def get_next_cursor(self):
        return (self.next_line, self.next_row)
    def get_line_num(self):
        return self.line
    def get_next_line_num(self):
        return self.next_line
    def set_auto_cr(self, acr=1):
        # if auto_carriage_return is set the row/next_row is set to 0/1 in case of a new_line ([0])
        self.auto_cr = acr
    def set_cursor(self, line=0, row=0):
        self.line     , self.row      = (line    , row    )
        self.next_line, self.next_row = (line + 1, row + 1)
    def set_used_fields(self, (start_line, end_line), (start_row, end_row)):
        # enlarge used_fields dictionary
        max_line_num = max([end_line] + self.__used_field.keys())
        max_row_num  = max([end_row ] + [len(x) for x in self.__used_field.values()])
        for line in range(1, max_line_num + 1):
            self.__used_field.setdefault(line, [])
            self.__used_field[line].extend([0] * (max_row_num - len(self.__used_field[line])))
        self.__line_num, self.__row_num = (max_line_num, max_row_num)
        if DEBUG:
            # slow path, check for already set fields
            num_errors, set_list = (0, [])
            for line in range(start_line, end_line + 1):
                for row in range(start_row, end_row + 1):
                    if self.__used_field[line][row - 1]:
                        num_errors += 1
                        print "ERROR! %d/%d already used with %d, refusing set" % (line, row, self.__used_field[line][row - 1])
                    else:
                        self.__used_field[line][row - 1] = 1
                        set_list.append((line, row - 1))
            if not start_row:
                print "ERROR! trying to set invalid row %d, refusing" % (start_row)
                num_errors += 1
            if num_errors:
                for line, row in set_list:
                    self.__used_field[line][row] = 0
            else:
                self.__used_field[start_line][start_row - 1] = 2
        else:
            # fast path, no check for already set fields
            num_errors = 0
            self.__used_field[start_line][start_row - 1] = 2
        return num_errors
        #print self.__used_field
    def get_size(self):
        return (self.__line_num, self.__row_num)
    def __del__(self):
        content.__del__(self)
        #print "Table delete"
    def __repr__(self):
        return "<html_table with size %d x %d>" % (self.get_size())
    def get_header(self):
        if self.__header_written:
            return ""
        else:
            self.__header_written = True
            return "<table%s>\n" % (self.get_attributes())
    def get_footer(self):
        if self.__footer_written:
            return ""
        else:
            self.__footer_written = True
            return "</table>\n"
    def flush_lines(self, suffix="", write_footer=False):
        ret_str = self(suffix, write_footer = write_footer)
        self.clear_data()
        self.set_cursor()
        return ret_str
    def clear_data(self):
        self.__used_field = {}
        self.__line_num, self.__row_num = (0, 0)
        self.col_dict = {}
    def __call__(self, suffix="", write_footer=True, indent_level=0):
        s_time = time.time()
        indent_level += 1
        num_lines, num_rows = self.get_size()
        ret_str = []
        ret_str.append(self.get_header())
        for line_num in range(1, self.__line_num + 1):
            line_started = False
            act_line = self.__used_field[line_num]
            line_types = []
            for row_num in range(1, self.__row_num + 1):
                act_usage = act_line[row_num - 1]
                #print line_num, row_num, act_usage
                if not act_usage:
                    if DEBUG:
                        loc_str = "<td>%d / %d not used</td>\n" % (line_num, row_num)
                    else:
                        loc_str = ""
                elif act_usage == 1:
                    loc_str = ""
                else:
                    act_ent = self.col_dict[line_num].col_dict[row_num]
                    act_width, act_height, act_type = (act_ent.get_width(),
                                                       act_ent.get_height(),
                                                       act_ent.get_type())
                    line_types.append(act_type)
                    act_head, act_foot = ("<%s%s%s%s>" % (act_type,
                                                          act_height > 1 and " rowspan=\"%d\"" % (act_height) or "",
                                                          act_width  > 1 and " colspan=\"%d\"" % (act_width)  or "",
                                                          act_ent.get_attributes()),
                                          "</%s>" % (act_type))
                    if act_ent.beautify_it():
                        indent_str = " " * 4 * indent_level
                        act_lines = [x.rstrip() for x in act_ent(suffix, indent_level).strip().split("\n")]
                        if len(act_lines) == 1:
                            loc_str = "%s%s%s\n" % (act_head, act_lines[0], act_foot)
                        else:
                            loc_str = "%s\n%s\n%s%s\n" % (act_head, "\n".join(["%s%s" % (indent_str + "  ", x) for x in act_lines]), indent_str, act_foot)
                    else:
                        loc_str = "%s%s%s\n" % (act_head, act_ent(suffix), act_foot)
                if loc_str:
                    if self.__check_for_thead and ("th" in line_types and not self.__thead_written):
                        self.__thead_written, self.__is_thead = (True, True)
                        ret_str.append("<thead>\n")
                    if not line_started:
                        ret_str.append("  <tr%s>\n" % (self[line_num].get_attributes()))
                        line_started = True
                    ret_str.append("    %s" % (loc_str))
            if line_started:
                ret_str.append("  </tr>\n")
                if self.__check_for_thead and ("th" in line_types):
                    if self.__is_thead:
                        self.__thead_written, self.__is_thead = (True, False)
                        ret_str.append("</thead>\n")
        if write_footer:
            ret_str.append(self.get_footer())
        e_time = time.time()
        #print "%.2f" % (e_time - s_time)
        return "".join(ret_str)

def test():
    #print "<html><body>"
    a = html_table()
    a["class"] = "normal"
    #a.set_auto_increase(1, 0)
    print a.get_cursor(), a.get_next_cursor()
    #a[3:5]["class"] = "asd"
        #a[1:5][6] = content(5)
    print a.get_cursor(), a.get_next_cursor()
    my_c = content(500)
    if 1:
        a[0:2]["class"] = "x"
        a[0][1] = my_c
        print "s5", a.get_cursor(), a.get_next_cursor()
        a[0][0:2] = content(4)
        print a.get_cursor(), a.get_next_cursor()
        #a[2:3][3:4] = content("set")
        #a[5][2]["class"] = "left"
        a[0][0:3] = content(["blla", checkbox(None, "test")])
        #print a.get_cursor(), a.get_next_cursor()
        #a[2][1] = content("txxxx")
        #print a.get_cursor(), a.get_next_cursor()
        a[0:3][2:2] = content("test")
        #print a.get_cursor(), a.get_next_cursor()
    print a("x")
    del my_c
    del a
    #print "</body></html>"
    
if __name__ == "__main__":
    import sys
    import pprint
    init_html_vars()
    test()
    print "Loadable module, exiting..."
    sys.exit(0)
