#!/usr/bin/python -Ot
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
""" basic object for db abstraction """

import sys
import array

class db_obj(object):
    def __init__(self, name, idx, pfpf=""):
        # clear field_lookup table
        self.act_f_lut = None
        self.set_name(name)
        self.idx = idx
        self.set_forced_object()
        self.pfpf = pfpf
        self.set_suffix("%d%s" % (idx, pfpf))
        self.set_valid_keys({})
        self.is_init_mode(True)
        self.set_beautify_get()
        self.__verbose = False
    def set_verbose(self, vb=True):
        self.__verbose = vb
    def is_init_mode(self, sm):
        self.__init_mode = sm
    def get_is_init_mode(self):
        return self.__init_mode
    def set_beautify_get(self, bg=0):
        self.__beautify_get = bg
    def set_parameters(self, stuff):
        for key in [x for x in self.__valid_keys if x in stuff.keys()]:
            self[key] = stuff[key]
    def set_valid_keys(self, in_dict = {}, nolog_keys=[]):
        if in_dict == {}:
            self.__valid_keys = []
            self.__nolog_keys = nolog_keys
            self.__type_dict = in_dict
            self.__set_dict = {}
            self.__change_dict = {}
            self.__change_list = []
            self.__field_dict = {}
            self.__sql_changes = {}
            self.change_warn_dict, self.change_error_dict = ({}, {})
        else:
            for key, value in in_dict.iteritems():
                if key not in self.__valid_keys:
                    self.__valid_keys.append(key)
                if type(value) == type(""):
                    self.__type_dict[key] = value
                else:
                    rt, stuff, field_name = value
                    self.__type_dict[key] = rt
                    if rt == "f":
                        self.__field_dict[key] = stuff
                        if stuff not in self.__sql_changes.keys():
                            self.modify_sql_changes({stuff : {"table"       : stuff,
                                                              "type"        : "slave",
                                                              "multi_field" : field_name,
                                                              "multi"       : key}})
            self.__nolog_keys.extend([x for x in nolog_keys if x not in self.__nolog_keys])
    def copy_keys(self, other):
        for key in [x for x in self.__valid_keys if other.has_key(x)]:
            self[key] = other[key]
            if key not in self.__change_dict["d"]:
                self.__change_dict["d"].append(key)
                self.__change_list.append(key)
    def set_suffix(self, pf):
        if pf.startswith("-"):
            self.pf = "min%s" % (pf[1:])
        else:
            self.pf = pf
    def get_suffix(self):
        return self.pf
    def set_forced_object(self, forced = False):
        self.forced_object = forced
    def is_forced_object(self):
        return self.forced_object
    def set_idx(self, idx):
        self.idx = idx
        self.set_suffix("%d%s" % (idx, self.pfpf))
        return self.idx
    def get_idx(self):
        return self.idx
    def set_name(self, name):
        self.name = name
    def get_name(self):
        return self.name
    def init_sql_changes(self, init_dict={}):
        if init_dict:
            self.modify_sql_changes({"d" : init_dict})
    def modify_sql_changes(self, mod_dict):
        for what, n_dict in mod_dict.iteritems():
            self.__sql_changes[what] = n_dict
            self.__sql_changes[what].setdefault("changes", {})
            self.__sql_changes[what].setdefault("type", "master")
            self.__change_dict[what] = []
    def create_sql_strings(self, (master_table, master_idx, slave_table), sql_stuff):
        sql_str = []
        if sql_stuff["changes"]:
            if sql_stuff["type"] == "slave":
                new_set, old_set = (sql_stuff["changes"][sql_stuff["multi"]], self.__old_values_dict[sql_stuff["multi"]])
                #print "nsos", new_set, old_set
                for del_s in [x for x in old_set if x not in new_set]:
                    sql_str.append(("DELETE FROM %s WHERE %s" % (slave_table,
                                                                 " AND ".join(["%s=%d" % (master_table, master_idx)] +
                                                                              [x in ["upgrade", "relase"] and "`%s`=%s" % (x, y) or "%s=%s" % (x, y) for x, y in sql_stuff["changes"].iteritems() if x != sql_stuff["multi"]] +
                                                                              ["%s=%s" % (sql_stuff["multi_field"], del_s)])),
                                    ()))
                for new_s in [x for x in new_set if x not in old_set]:
                    change_keys = [x for x in sql_stuff["changes"].keys() if x != sql_stuff["multi"]]
                    sql_str.append(("INSERT INTO %s SET %s" % (slave_table,
                                                               ", ".join(["%s=%d" % (master_table, master_idx)] +
                                                                         [x in ["upgrade", "release"] and "`%s`=%%s" % (x) or "%s=%%s" % (x) for x in change_keys] +
                                                                         ["%s=%s" % (sql_stuff["multi_field"], new_s)])),
                                    tuple([sql_stuff["changes"][x] for x in change_keys])))
            else:
                # master table; slave_table is the flag for INSERT or UPDATE
                if slave_table:
                    change_keys = [x for x in sql_stuff["changes"].keys() if x != "%s_idx" % (master_table)]
                    sql_str = [("INSERT INTO %s SET %s" % (master_table,
                                                           ", ".join([x in ["upgrade", "release"] and "`%s`=%%s" % (x) or "%s=%%s" % (x) for x in change_keys])),
                                tuple([sql_stuff["changes"][x] for x in change_keys]))]
                else:
                    change_keys = sql_stuff["changes"].keys()
                    sql_str = [("UPDATE %s SET %s WHERE %s_idx=%d" % (master_table,
                                                                      ", ".join([x in ["upgrade", "release"] and "`%s`=%%s" % (x) or "%s=%%s" % (x) for x in change_keys]),
                                                                      master_table,
                                                                      master_idx),
                                tuple([sql_stuff["changes"][x] for x in change_keys]))]
        return sql_str
    def add_sql_changes(self, val_dict, where="d"):
        # not needed any more ?
        for key, value in val_dict.iteritems():
            self.__sql_changes[where]["changes"][key] = value
    def commit_sql_changes(self, dc, do_it=True, create_it=False, show_it=False):
        any_changes = False
        w_list = ["d"] + [x for x in self.__sql_changes.keys() if x != "d"]
        master_idx = None
        for where in w_list:
            stuff = self.__sql_changes[where]
            if where == "d":
                if create_it:
                    self.add_sql_changes(dict([(k, self.__set_dict[k]) for k in self.__valid_keys if k not in self.__field_dict.keys()]), where)
                else:
                    self.add_sql_changes(dict([(k, self.__set_dict[k]) for k in self.__change_dict[where]]), where)
            else:
                self.add_sql_changes(dict([(k, self.__set_dict[k]) for k in self.__change_dict[where]]), where)
            if stuff["changes"] or create_it:
                # create sql strings
                if stuff["type"] == "master":
                    if create_it:
                        sql_strs = self.create_sql_strings((stuff["table"], master_idx  , 1), stuff)
                    else:
                        sql_strs = self.create_sql_strings((stuff["table"], stuff["idx"], 0), stuff)
                else:
                    sql_strs = self.create_sql_strings((self.__sql_changes["d"]["table"], master_idx, stuff["table"]), stuff)
                if sql_strs:
                    any_changes = True
                if do_it:
                    for sql_str, sql_tuple in sql_strs:
                        dc.execute(sql_str, sql_tuple)
                    if create_it and stuff["type"] == "master":
                        stuff["idx"] = self.set_idx(dc.insert_id())
                if show_it or not do_it:
                    print "\n*** %s *** %s *** \n" % (sql_str, sql_tuple)
            if where == "d":
                master_idx = stuff["idx"]
        return any_changes
    def change_warn(self, key, new_val, err_str):
        if key in self.__valid_keys:
            self.change_warn_dict[key] = (new_val, err_str)
        else:
            raise IndexError, "key '%s' not defined in change_warn()" % (key)
    def change_error(self, key, new_val, err_str):
        if key in self.__valid_keys:
            self.change_error_dict[key] = (new_val, err_str)
        else:
            raise IndexError, "key '%s' not defined in change_error()" % (key)
    def has_key(self, key):
        return key in self.__set_dict.keys()
    def act_values_are_default(self):
        self.__old_values_dict = {}
        for key, value in self.__set_dict.iteritems():
            if type(value) == type([]):
                self.__old_values_dict[key] = [x for x in value]
            else:
                self.__old_values_dict[key] = value
        self.is_init_mode(False)
    def update(self, in_dict):
        for key, value in in_dict.iteritems():
            self[key] = value
    def __setitem__(self, key, value):
        if type(value) == array.array("c"):
            value = value.tostring()
##         if self.__verbose:
##             print key, key in self.__valid_keys, self.__init_mode, value
        if key in self.__valid_keys:
            if not self.__init_mode:
                # migrate array to char
                ov = self.__old_values_dict[key]
                if type(ov) == type(array.array("c")):
                    ov = ov.tostring()
                if value != ov:
                    self.__change_list.append(key)
                    self.__change_dict.setdefault(self.__field_dict.get(key, "d"), []).append(key)
            if type(value) == type([]):
                self.__set_dict[key] = [x for x in value]
            else:
                self.__set_dict[key] = value
        else:
            raise IndexError, "key '%s' not defined in __setitem__() (name '%s'), %s" % (key,
                                                                                         self.name,
                                                                                         self.__set_dict.keys() and "defined keys: %s" % (", ".join(sorted(self.__set_dict.keys()))) or "no keys defined")
    def __getitem__(self, key):
##         if self.__verbose:
##             print key, self.__set_dict.has_key(key), self.__set_dict[key]
        if self.__set_dict.has_key(key):
            if self.__beautify_get:
                return self.beautify_key(key, self.__set_dict[key])
            else:
                return self.__set_dict[key]
        else:
            raise IndexError, "key '%s' (%d) not defined in __getitem__() (name '%s'), %s" % (key,
                                                                                              self.__beautify_get,
                                                                                              self.name,
                                                                                              self.__set_dict.keys() and "defined keys: %s" % (", ".join(sorted(self.__set_dict.keys()))) or "no keys defined")
    def beautify_key(self, key, val):
        if self.act_f_lut and hasattr(self, "html_out_filter_%s" % (key)):
            try:
                return getattr(self, "html_out_filter_%s" % (key))(val, self.act_f_lut[key])
            except:
                return "html_out_filter raised an exception: %s (%s)" % (str(sys.exc_info()[0]), str(sys.exc_info()[1]))
        else:
            return val
    def get_num_field(self):
        return len(self.change_error_dict.keys()), len(self.change_warn_dict.keys()), len(self.__change_list)
    def get_num_fields(self):
        return {"e" : len(self.change_error_dict.keys()),
                "w" : len(self.change_warn_dict.keys()),
                "o" : len(self.__change_list)}
    def build_change_lists(self, pre_str = "", post_str="", change=1, show_all=0, compress_ok=0):
        e_list, w_list, ok_list = ([], [], [])
        all_keys = [x for x in self.__valid_keys]
        self.set_beautify_get(1)
        if change:
            for key, (new_val, info_str) in [x for x in self.change_error_dict.iteritems() if x not in self.__nolog_keys]:
                e_list.append(("%s%s from %s to %s%s" % (pre_str, key, self.get_string(key, self[key]), self.get_string(key, self.beautify_key(key, new_val)), post_str), info_str))
                if key in all_keys:
                    all_keys.remove(key)
            for key, (new_val, info_str) in [x for x in self.change_warn_dict.iteritems() if x not in self.__nolog_keys]:
                w_list.append(("%s%s from %s to %s%s" % (pre_str, key, self.get_string(key, self[key]), self.get_string(key, self.beautify_key(key, new_val)), post_str), info_str))
                if key in all_keys:
                    all_keys.remove(key)
            for key in [x for x in self.__change_list if x not in self.__nolog_keys]:
                ok_list.append("%s from %s to %s" % (key, self.get_string(key, self.beautify_key(key, self.__old_values_dict[key])), self.get_string(key, self[key])))
                if key in all_keys:
                    all_keys.remove(key)
            if show_all:
                for key in [x for x in all_keys if x not in self.__nolog_keys]:
                    ok_list.append(("%s%s from %s to %s%s" % (pre_str, key, self.get_string(key, self.beautify_key(key, self.__old_values_dict[key])), self.get_string(key, self[key]), post_str), "ok"))
        else:
            for key, (new_val, info_str) in [x for x in self.change_error_dict.iteritems() if x not in self.__nolog_keys]:
                e_list.append(("%s%s to %s%s" % (pre_str, key, self.get_string(key, self.beautify_key(key, new_val)), post_str), info_str))
                if key in all_keys:
                    all_keys.remove(key)
            for key, (new_val, info_str) in [x for x in self.change_warn_dict.iteritems() if x not in self.__nolog_keys]:
                w_list.append(("%s%s to %s%s" % (pre_str, key, self.get_string(key, self.beautify_key(key, new_val)), post_str), info_str))
                if key in all_keys:
                    all_keys.remove(key)
            for key in [x for x in self.__change_list if x not in self.__nolog_keys]:
                ok_list.append("%s to %s" % (key, self.get_string(key, self[key])))
                if key in all_keys:
                    all_keys.remove(key)
            if show_all:
                for key in [x for x in all_keys if x not in self.__nolog_keys]:
                    ok_list.append("%s to %s" % (key, self.get_string(key, self[key])))
        self.set_beautify_get(0)
        if compress_ok and ok_list:
            ok_list = [("%s%s%s" % (pre_str, ", ".join(ok_list), post_str), "ok")]
        else:
            ok_list = [("%s%s%s" % (pre_str, x, post_str), "ok") for x in ok_list]
        return e_list, w_list, ok_list
    def build_log_dict_n(self, pre_str, post_str, ob_dict, nb_dict):
        # buld log dict, new instance
        e_list, w_list, ok_list = ([], [], [])
        all_keys = [x for x in self.__valid_keys]
        for key, (new_val, info_str) in [x for x in self.change_error_dict.iteritems() if x not in self.__nolog_keys]:
            e_list.append(("%s%s to %s%s" % (pre_str, key, self.get_string(key, nb_dict.get(key, new_val)), post_str), info_str))
            if key in all_keys:
                all_keys.remove(key)
        for key, (new_val, info_str) in [x for x in self.change_warn_dict.iteritems() if x not in self.__nolog_keys]:
            w_list.append(("%s%s to %s%s" % (pre_str, key, self.get_string(key, nb_dict.get(key, new_val)), post_str), info_str))
            if key in all_keys:
                all_keys.remove(key)
        for key in [x for x in self.__change_list if x not in self.__nolog_keys]:
            ok_list.append("%s to %s" % (key, self.get_string(key, nb_dict.get(key, self[key]))))
            if key in all_keys:
                all_keys.remove(key)
        for key in [x for x in all_keys if x not in self.__nolog_keys]:
            ok_list.append("%s to %s" % (key, self.get_string(key, nb_dict.get(key, self[key]))))
        if ok_list:
            ok_list = [("%s%s%s" % (pre_str, ", ".join(ok_list), post_str), "ok")]
        else:
            ok_list = []
        return {"e" : e_list,
                "w" : w_list,
                "o" : ok_list}
    def build_log_dict_c(self, pre_str, post_str, ob_dict, nb_dict):
        # buld log dict, change
        e_list, w_list, ok_list = ([], [], [])
        all_keys = [x for x in self.__valid_keys]
        for key, (new_val, info_str) in [x for x in self.change_error_dict.iteritems() if x not in self.__nolog_keys]:
            e_list.append(("%s%s from %s to %s%s" % (pre_str, key, self.get_string(key, ob_dict.get(key, self[key])), self.get_string(key, nb_dict.get(key, new_val)), post_str), info_str))
            if key in all_keys:
                all_keys.remove(key)
        for key, (new_val, info_str) in [x for x in self.change_warn_dict.iteritems() if x not in self.__nolog_keys]:
            w_list.append(("%s%s from %s to %s%s" % (pre_str, key, self.get_string(key, ob_dict.get(key, self[key])), self.get_string(key, nb_dict.get(key, new_val)), post_str), info_str))
            if key in all_keys:
                all_keys.remove(key)
        for key in [x for x in self.__change_list if x not in self.__nolog_keys]:
            ok_list.append("%s from %s to %s" % (key, self.get_string(key, ob_dict.get(key, self.__old_values_dict[key])), self.get_string(key, nb_dict.get(key, self[key]))))
            if key in all_keys:
                all_keys.remove(key)
        if ok_list:
            ok_list = [("%s%s%s" % (pre_str, ", ".join(ok_list), post_str), "ok")]
        return {"e" : e_list,
                "w" : w_list,
                "o" : ok_list}
    def get_string(self, key, value):
        if self.__type_dict[key] == "s": 
            return "'%s'" % (value)
        elif self.__type_dict[key] == "i":
            return "%s" % (value)
        elif self.__type_dict[key] == "b":
            return "%s" % ({0 : "off",
                            1 : "on"}[value])
        elif self.__type_dict[key] == "f":
            return "'%s'" % (str(value))
        else:
            return "type %s: '%s'" % (str(self.__type_dict[key]), str(value))
    def set_fields(self, f_lut):
        for key, stuff in f_lut.iteritems():
            for field, getset_func in [(k, v) for k, v in stuff.iteritems() if type(k) != type("")]:
                if getset_func:
                    old_val = getattr(self, getset_func)(None, stuff)
                else:
                    old_val = self[key]
                #print field.get_name(), self.get_suffix(), old_val, type(old_val)
                field[self.get_suffix()] = old_val
    def check_for_changes(self, f_lut, sub, redirect_dict={}):
        # own suffix
        own_pf = self.get_suffix()
        # save field_lookup table
        self.act_f_lut = f_lut
        # old_value dict
        old_val_dict = {}
        # generate validate dict
        validate_dict = {}
        for key, stuff in f_lut.iteritems():
            validate_func_name = "validate_%s" % (stuff.get("compound", key))
            validate_dict.setdefault(validate_func_name, {"key_dict" : {}, "button_list" : []})
            validate_dict[validate_func_name]["key_dict"].setdefault(key, {})
            validate_dict[validate_func_name]["func"] = getattr(self, validate_func_name, None)
            for k_in, v_val in stuff.iteritems():
                if type(k_in) == type(""):
                    validate_dict[validate_func_name][k_in] = stuff[k_in]
                else:
                    validate_dict[validate_func_name]["key_dict"][key][k_in] = v_val
        for vf_name, stuff in validate_dict.iteritems():
            new_val_dict, old_val_dict = ({}, {})
            for key, fields in stuff["key_dict"].iteritems():
                new_val_dict[key] = []
                old_val_dict[key] = []
                # take source_suffix, defaults to own suffix
                src_pf = redirect_dict.get(key, own_pf)
                for field, getset_func in fields.iteritems():
                    if getset_func:
                        old_val = getattr(self, getset_func)(None, stuff)
                    else:
                        old_val = self[key]
                    if field.get_name() in stuff["button_list"]:
                        new_val = field.check_selection(src_pf, old_val and not sub)
                    else:
                        new_val = field.check_selection(src_pf, old_val)
                    if src_pf != own_pf:
                        field[own_pf] = new_val
                    if len(fields) == 1:
                        old_val_dict[key] = old_val
                        new_val_dict[key] = new_val
                    else:
                        old_val_dict[key].append(old_val)
                        new_val_dict[key].append(new_val)
            val_func = stuff["func"]
            if val_func:
                #print "Calling validate_func '%s', keys %s<br>" % (vf_name, ", ".join(stuff["key_dict"].keys()))
                if len(stuff["key_dict"].keys()) == 1:
                    check_lev, err_str, add_flags = val_func(new_val_dict[key], old_val_dict[key], stuff)
                else:
                    check_lev, err_str, add_flags = val_func(new_val_dict, old_val_dict, stuff)
                #print " -- result: %d, %s, %s <br>" % (check_lev, err_str, str(add_flags))
            else:
                check_lev, err_str, add_flags = (0, "OK", {})
                # if always_check is set we check the values even if old and new value are the same
            if new_val_dict != old_val_dict or check_lev:
                no_log = add_flags.get("no_log", [])
                for key, fields in stuff["key_dict"].iteritems():
                    for field, getset_func in fields.iteritems():
                        if len(fields) == 1:
                            old_val, new_val = (old_val_dict[key], new_val_dict[key])
                        else:
                            old_val, new_val = (old_val_dict[key].pop(0), new_val_dict[key].pop(0))
                        # do we have to change old_val/new_val ?
                        
                        if add_flags.get("change_dict", {}).has_key(key):
                            old_val, new_val = (add_flags["change_dict"][key],
                                                add_flags["change_dict"][key])
                        if hasattr(self, "html_in_filter_%s" % (key)):
                            new_val_str = getattr(self, "html_in_filter_%s" % (key))(new_val, stuff)
                        else:
                            new_val_str = new_val
                        set_value = False
                        if check_lev:
                            if key not in no_log:
                                if check_lev == 1:
                                    if add_flags.get("change_dict", {}).has_key(key):
                                        set_value = True
                                    else:
                                        self.change_warn(key, new_val_str, err_str)
                                else:
                                    self.change_error(key, new_val_str, err_str)
                            #print "Reseting. %s to %s<br>" % (own_pf, old_val)
                            field[own_pf] = old_val
                        else:
                            set_value = True
                        if set_value and not add_flags.has_key("skip_set"):
                            if add_flags.get("integer", 0):
                                new_val = int(new_val)
                            #print "Calling getset_func '%s' for vf_name %s, key %s<br>" % (getset_func, vf_name, key)
                            if getset_func:
                                getattr(self, getset_func)(new_val, stuff)
                            else:
                                self[key] = new_val
                            if add_flags.get("reset", 0):
                                #print "Reseting %s<br>" % (own_pf)
                                field[own_pf] = new_val
                #print key, old_val, new_val, "<br>"
