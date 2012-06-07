#!/usr/bin/python -Ot
# -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2001,2002,2003,2004,2005,2007,2009 Andreas Lang-Nevyjel, init.at
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
""" object definitions for user / group handling """

import cdef_basics
import cPickle
import os
import os.path
import html_tools
import array
import copy

class user_var(object):
    def __init__(self, in_dict, source_is_db=False):
        self.name   = in_dict["name"]
        self.v_type = in_dict["type"]
        value = in_dict["value"]
        if type(value) == type(array.array("c")):
            value = value.tostring()
        self.hidden = in_dict.get("hidden", True)
        self.editable = in_dict.get("editable", False)
        self.description = in_dict.get("description", "") or "not set"
        if source_is_db:
            # parse string from db
            if self.v_type == "s":
                pass
            elif self.v_type == "i":
                value = int(value)
            elif self.v_type == "b":
                value = value == "1" and True or False
            elif self.v_type in ["l", "d"]:
                try:
                    value = cPickle.loads(value)
                except:
                    print "error decoding user_value %s (type %s)" % (self.name, self.v_type)
                    if self.v_type == "l":
                        value = []
                    else:
                        value = {}
            else:
                print "Unknown user_var_type '%s' for user_var" % (self.v_type)
                value = None
        self.__value = value
        self.changed, self.type_changed = (False, False)
    def set_new_type(self, new_type, new_value):
        # change type
        self.type_changed = True
        self.v_type = new_type
        self.set_value(new_value)
    def get_type_str(self):
        return {"s" : "String",
                "i" : "Integer",
                "b" : "Boolean",
                "l" : "List",
                "d" : "Dictionary"}.get(self.v_type, "Unknown [%s]" % (self.v_type))
    def get_new_sql_string(self):
        val_str, val_tuple = self.get_value_sql_string()
        return ("name=%%s, type=%%s, %s" % (val_str), tuple([self.name,
                                                             self.v_type] +
                                                            list(val_tuple)))
    def get_value_sql_string(self):
        if self.v_type == "s":
            val_str = self.__value
        elif self.v_type == "i":
            val_str = "%d" % (self.__value)
        elif self.v_type == "b":
            val_str = self.__value and "1" or "0"
        elif self.v_type in ["l", "d"]:
            val_str = cPickle.dumps(self.__value)
        else:
            print "Unknown user_var_type '%s'" % (self.v_type)
            val_str = ""
        return ("value=%s, hidden=%s, description=%s", (val_str,
                                                        self.hidden and 1 or 0,
                                                        self.description))
    def get_value_str(self):
        return str(self.__value)
    def get_value(self):
        # important to check if dictionaries change
        return copy.deepcopy(self.__value)
    def set_value(self, new_val):
        if new_val != self.__value:
            self.__value = new_val
            self.changed = True
    
class capability(object):
    def __init__(self, db_rec):
        self.name, self.idx = (db_rec["name"],
                               db_rec["capability_idx"])
        self.mother_capability, self.mother_capability_name = (db_rec["mother_capability"],
                                                               db_rec["mother_capability_name"])
        self.priority = db_rec["priority"]
        self.default, self.db_enabled = (db_rec["defvalue"],
                                         db_rec["enabled"])
        self.description = db_rec["description"]
        self.modulename = db_rec["modulename"]
        self.left_string, self.right_string = (db_rec["left_string"],
                                               db_rec["right_string"])
        if self.mother_capability:
            self.top_element = False
        else:
            self.top_element = True
        self._init_authorization()
    def _init_authorization(self):
        # usage authoried by
        self.authorized_by = "None"
        self.enabled = False
    def authorize(self, source):
        if self.db_enabled:
            self.authorized_by = source
            self.enabled = True

class capability_stack(object):
    def __init__(self, req):
        # dict of all capabilities in this stack
        self.__cap_dict = {}
        # lookuptable from idxs and names (short and long) to idx
        self.__cap_lut = {}
        # long and short module names
        self.__long_names, self.__short_names = ([], [])
        # fetch from database
        req.dc.execute("SELECT DISTINCT c.* FROM capability c")# LEFT JOIN ggroupcap gc ON (gc.capability=c.capability_idx AND gc.ggroup=%d)" % (req.session_data.group_idx))
        for db_rec in req.dc.fetchall():
            self._add_capability(capability(db_rec))
            #print req.dc.fetchall()
        self.__cg_tree = {}
        for cap_idx, cap in self.__cap_dict.iteritems():
            # build mother_list
            mother_list = [cap.idx]
            idx = 0
            mother_idx = cap.mother_capability
            while mother_idx:
                mother_list.append(mother_idx)
                mother_idx = self.__cap_dict[mother_list[-1]].mother_capability
                idx += 1
                if idx > 10:
                    # for safety reasons
                    break
            # mother_list after reverse: top -> next -> next -> cap
            mother_list.reverse()
            cap.mother_list = mother_list
            act_tree = self.__cg_tree
            for c_idx in mother_list:
                act_tree = act_tree.setdefault(c_idx, {})
        #pprint.pprint(self.__cg_tree)
    def add_user_rights(self, req, group_idx, user_idx, user_info):
        # group caps
        sql_str = "SELECT gc.capability AS gcap FROM ggroupcap gc WHERE gc.ggroup=%d" % (group_idx)
        req.dc.execute(sql_str)
        group_caps = [db_rec["gcap"] for db_rec in req.dc.fetchall() if db_rec["gcap"]]
        # user caps
        sql_str = "SELECT uc.capability AS ucap FROM usercap uc WHERE uc.user=%d" % (user_idx)
        req.dc.execute(sql_str)
        user_caps  = [db_rec["ucap"] for db_rec in req.dc.fetchall() if db_rec["ucap"] and db_rec["ucap"] not in group_caps]
        dead_caps = {"group" : [],
                     "user"  : []}
        for group_cap in group_caps:
            if self.__cap_lut.has_key(group_cap):
                self[group_cap].authorize("group")
                if user_info:
                    user_info.add_capability(self[group_cap], "group")
            else:
                dead_caps["group"].append(group_cap)
        for user_cap in user_caps:
            if self.__cap_lut.has_key(user_cap):
                self[user_cap].authorize("user")
                if user_info:
                    user_info.add_capability(self[user_cap], "user")
            else:
                dead_caps["user"].append(user_cap)
        # remove dead group and user caps
        for cap_type, cap_list in dead_caps.iteritems():
            if cap_list:
                if cap_type == "group":
                    sql_str = "DELETE FROM ggroupcap WHERE %s AND (ggroup=%d)" % (" OR ".join(["capability=%d" % (idx) for idx in cap_list]),
                                                                                  group_idx)
                else:
                    sql_str = "DELETE FROM usercap WHERE %s AND (user=%d)" % (" OR ".join(["capability=%d" % (idx) for idx in cap_list]),
                                                                              group_idx)
                req.dc.execute(sql_str)
    def _add_capability(self, cap):
        self.__cap_dict[cap.idx] = cap
        self.__cap_lut[cap.idx] = cap.idx
        self.__cap_lut[cap.name] = cap.idx
        if self.__cap_lut.has_key(cap.modulename):
            if cap.left_string:
                self.__cap_lut[cap.modulename] = cap.idx
        else:
            self.__cap_lut[cap.modulename] = cap.idx
        self.__short_names.append(cap.name)
        self.__short_names.sort()
        self.__long_names.append(cap.modulename)
        self.__long_names.sort()
    def get_long_modules_names(self):
        return self.__long_names
    def has_key(self, key):
        return self.__cap_lut.has_key(key)
    def __getitem__(self, key):
        return self.__cap_dict[self.__cap_lut[key]]
    def get_all_cap_idxs(self, with_top_level=False):
        if with_top_level:
            return self.__cap_dict.keys()
        else:
            return [idx for idx in self.__cap_dict.keys() if not self.__cap_dict[idx].top_element]
    def get_sorted_idxs(self, top_idx=0, **args):
        only_authorized = args.get("only_authorized", False)
        check_level = args.get("check_level", 0)
        # return indices sorted by priority, starting at top_idx
        pri_dict = {}
        for cap_idx, cap_stuff in self.__cap_dict.iteritems():
            if cap_stuff.db_enabled:
                if check_level:
                    check_list = cap_stuff.mother_list[0 : check_level]
                else:
                    check_list = cap_stuff.mother_list
                if only_authorized:
                    add_it = (cap_stuff.top_element and not top_idx) or (top_idx in check_list and cap_idx in check_list and cap_stuff.enabled)
                else:
                    add_it = (cap_stuff.top_element and not top_idx) or (top_idx in check_list and cap_idx in check_list)
                #print cap_idx, top_idx, cap_stuff.mother_list, check_list, add_it
                if add_it:
                    pri_dict.setdefault(cap_stuff.priority, []).append((cap_stuff.description, cap_idx))
                    pri_dict[cap_stuff.priority].sort()
        return sum([[idx for name, idx in pri_dict[pri]] for pri in sorted(pri_dict.keys())], [])
    
class group(cdef_basics.db_obj):
    def __init__(self, name, group_idx, init_dict={}):
        cdef_basics.db_obj.__init__(self, name, group_idx, "g")
        self.init_sql_changes({"table" : "ggroup",
                               "idx"   : self.idx})
        self.set_valid_keys({"gid"          : "i",
                             "active"       : "b",
                             "ggroupname"   : "s",
                             "homestart"    : "s",
                             "scratchstart" : "s",
                             "respvname"    : "s",
                             "respnname"    : "s",
                             "resptitan"    : "s",
                             "respemail"    : "s",
                             "resptel"      : "s",
                             "respcom"      : "s",
                             "groupcom"     : "s"},
                            ["ggroup_idx"])
        self.users, self.caps = ({}, {})
        self.user_name_lut = {}
        self.new_ggroup_var_idx = -1
        if init_dict:
            self.set_parameters(init_dict)
    def get_user(self, user_name):
        if type(user_name) in (type(0), type(0L)):
            return self.users.get(self.user_name_lut.get(user_name, ""), None)
        else:
            return self.users.get(user_name, None)
    def get_num_users(self):
        return len(self.users.keys())
    def get_num_capabilities(self):
        return len(self.caps.keys())
    def has_user(self, user_name):
        return user_name in self.users.keys()
    def add_user(self, user_struct):
        self.users[user_struct["login"]] = user_struct
        self.user_name_lut[user_struct.get_idx()] = user_struct["login"]
    def del_user(self, del_idx):
        del self.users[self.user_name_lut[del_idx]]
        del self.user_name_lut[del_idx]
    def add_capability(self, cap_stuff):
        cap_name, cap_idx = (cap_stuff.name, cap_stuff.idx)
        if cap_name not in self.caps.keys():
            self.caps[cap_stuff.name] = cap_idx
            #print "adding %s to %s" % (cap_stuff["name"], self["ggroupname"])
    def has_capability(self, cap):
        return cap in self.caps.keys()
        
class user(cdef_basics.db_obj):
    def __init__(self, name, user_idx, init_dict={}):
        cdef_basics.db_obj.__init__(self, name, user_idx, "u")
        self.set_valid_keys({"uid"             : "i",
                             "active"          : "b",
                             "ggroup"          : "i",
                             "password"        : "s",
                             "login"           : "s",
                             "export"          : "i",
                             "export_scr"      : "i",
                             "home"            : "s",
                             "scratch"         : "s",
                             "shell"           : "s",
                             "password"        : "s",
                             "cluster_contact" : "b",
                             "uservname"       : "s",
                             "usernname"       : "s",
                             "usertitan"       : "s",
                             "useremail"       : "s",
                             "userpager"       : "s",
                             "usertel"         : "s",
                             "usercom"         : "s",
                             "lm_password"     : "s",
                             "nt_password"     : "s",
                             "aliases"         : "s",
                             "sge_servers"     : ("f", "sge_user_con", "sge_config"),
                             "login_servers"   : ("f", "user_device_login", "device"),
                             },
                            ["user_idx"])
        self.init_sql_changes({"table" : "user",
                               "idx"   : self.idx})
        self.user_vars, self.var_lut, self.sec_groups = ({}, {}, [])
        self.new_user_var_idx = -1
        if init_dict:
            self.set_parameters(init_dict)
        self.set_act_short_module_name()
        self.__capabilities_dict = {"group" : [],
                                    "user"  : []}
        self["sge_servers"]   = []
        self["login_servers"] = []
    def add_capability(self, cap_stuff, src):
        cap = cap_stuff.name
        # used for actually logged-in user
        if cap not in self.__capabilities_dict[src]:
            self.__capabilities_dict[src].append(cap)
    def capability_ok(self, cap, src=None):
        if src:
            return cap in self.__capabilities_dict[src]
        else:
            return cap in self.__capabilities_dict["group"] or cap in self.__capabilities_dict["user"]
    def get_num_of_caps(self, src):
        return len(self.__capabilities_dict[src])
    def add_sge_server(self, sc_idx):
        if sc_idx not in self["sge_servers"]:
            self["sge_servers"].append(sc_idx)
    def add_login_server(self, sc_idx):
        if sc_idx not in self["login_servers"]:
            self["login_servers"].append(sc_idx)
    def delete_sge_server(self, sc_idx):
        if sc_idx in self["sge_servers"]:
            self["sge_servers"].remove(sc_idx)
    def delete_login_server(self, sc_idx):
        if sc_idx in self["login_servers"]:
            self["login_servers"].remove(sc_idx)
    def get_sge_servers(self):
        return self["sge_servers"]
    def get_login_servers(self):
        return self["login_servers"]
    def add_secondary_group_idx(self, group_idx):
        self.sec_groups.append(group_idx)
    def get_secondary_group_idxs(self):
        return self.sec_groups
    def set_act_short_module_name(self, smn="nn"):
        self.__act_smn = smn
    def set_parameters(self, stuff):
        cdef_basics.db_obj.set_parameters(self, stuff)
    def add_user_var(self, db_rec):
        # transform _rrd_ settings from string to dict
        if [True for x in ["_rrd_", "_sdc_"] if db_rec["name"].count(x)] and db_rec["type"] == "s":
            try:
                if type(db_rec["value"]) == type(array.array("c")):
                    value = cPickle.loads(db_rec["value"].tostring())
                else:
                    value = cPickle.loads(db_rec["value"])
            except:
                pass
            else:
                db_rec["type"] = "d"
        #print "adding %svar %s (%s, %s)" % (new_var and "new " or "", db_rec["name"], db_rec["type"], db_rec["value"])
        uv = user_var(db_rec, source_is_db=True)#["name"], db_rec["type"], db_rec["value"], 0)
        self.user_vars[db_rec["user_var_idx"]] = uv
        self.var_lut = dict([(v.name, k) for k, v in self.user_vars.iteritems()])
    def get_user_var_names(self, include_hidden=False):
        if include_hidden:
            v_names = self.var_lut.keys()
        else:
            v_names = [key for key, value in self.var_lut.iteritems() if not self.user_vars[value].hidden]
        return sorted(v_names)
    def get_real_name(self, v_name):
        if v_name.startswith("_"):
            r_name = "%s%s" % (self.__act_smn, v_name)
        else:
            r_name = v_name
        return r_name
    def has_user_var(self, v_name):
        return self.var_lut.has_key(self.get_real_name(v_name))
    def get_user_var(self, v_key):
        if type(v_key) == type(""):
            return self.user_vars[self.var_lut[v_key]]
        else:
            return self.user_vars[v_key]
    def get_user_var_value(self, v_name, def_value, **args):
        r_name = self.get_real_name(v_name)
        if type(def_value) == type(""):
            def_type = "s"
        elif type(def_value) == type(0):
            def_type = "i"
        elif type(def_value) == type([]):
            def_type = "l"
        elif type(def_value) == type({}):
            def_type = "d"
        elif type(def_value) == type(True):
            def_type = "b"
        if not self.var_lut.has_key(r_name):
            uv = user_var({"name"        : r_name,
                           "type"        : def_type,
                           "value"       : def_value,
                           "description" : args.get("description", "no description"),
                           "hidden"      : args.get("hidden", True),
                           "editable"    : args.get("editable", False)})
            self.user_vars[self.new_user_var_idx] = uv
            self.new_user_var_idx -= 1
            self.var_lut = dict([(v.name, k) for k, v in self.user_vars.iteritems()])
        else:
            # check type
            uv = self.user_vars[self.var_lut[r_name]]
            if uv.v_type != def_type:
                # type mismatch, override with default_value
                uv.set_new_type(def_type, def_value)
        return uv.get_value()
    def modify_user_var(self, v_name, new_val):
        self.user_vars[self.var_lut[self.get_real_name(v_name)]].set_value(new_val)
    def save_modified_user_vars(self, dc):
        for var_idx, var_stuff in self.user_vars.iteritems():
            if var_idx < 0:
                uv_str, uv_tuple = var_stuff.get_new_sql_string()
                dc.execute("INSERT INTO user_var SET %s, user=%d" % (uv_str, self.get_idx()), uv_tuple)
            else:
                if var_stuff.type_changed:
                    dc.execute("UPDATE user_var SET type=%%s WHERE user_var_idx=%d" % (var_idx), var_stuff.v_type)
                if var_stuff.changed:
                    uv_str, uv_tuple = var_stuff.get_value_sql_string()
                    dc.execute("UPDATE user_var SET %s WHERE user_var_idx=%d" % (uv_str, var_idx), uv_tuple)

class user_group_tree(object):
    def __init__(self, req):
        self.dc = req.dc
        self.cap_stack = req.cap_stack
        self._init_dicts()
    def _init_dicts(self):
        self.__group_dict, self.__user_dict = ({}, {})
        # fetch group capability trees
        self.dc.execute("SELECT g.*, gc.capability FROM ggroup g LEFT JOIN ggroupcap gc ON gc.ggroup=g.ggroup_idx")
        for db_rec in self.dc.fetchall():
            group_name = db_rec["ggroupname"]
            if group_name and not self.__group_dict.has_key(group_name):
                self.__group_dict[group_name] = group(group_name, db_rec["ggroup_idx"], db_rec)
            if db_rec["capability"] and self.cap_stack.has_key(db_rec["capability"]):
                self.__group_dict[group_name].add_capability(self.cap_stack[db_rec["capability"]])
        # fetch user capability trees
        self.dc.execute("SELECT g.ggroupname, u.*, uc.capability FROM ggroup g, user u LEFT JOIN usercap uc ON uc.user=u.user_idx WHERE u.ggroup=g.ggroup_idx")
        for db_rec in self.dc.fetchall():
            group_name, login_name = (db_rec["ggroupname"], db_rec["login"])
            if login_name and not self.__group_dict[group_name].has_user(login_name):
                new_user = user(login_name, db_rec["user_idx"], db_rec)
                self.__group_dict[group_name].add_user(new_user)
                self.__user_dict[login_name] = new_user
            if db_rec["capability"] and self.cap_stack.has_key(db_rec["capability"]):
                self.__user_dict[login_name].add_capability(self.cap_stack[db_rec["capability"]], "user")
        # generate lookuptable idx->name (and reverse) for group
        self.__group_name_lut = dict([(self.__group_dict[x].get_idx(), x) for x in self.__group_dict.keys()] +
                                     [(x, self.__group_dict[x].get_idx()) for x in self.__group_dict.keys()])
        # generate lookuptable idx->name (and reverse) for user
        self.__user_name_lut = dict([(self.__user_dict[x].get_idx(), x) for x in self.__user_dict.keys()] +
                                    [(x, self.__user_dict[x].get_idx()) for x in self.__user_dict.keys()])
        # fetch user variable tree
        self.dc.execute("SELECT * FROM user_var")
        # list of variables to delete
        del_vars = []
        for db_rec in self.dc.fetchall():
            user_idx = db_rec["user"]
            if self.__user_name_lut.has_key(user_idx):
                self.__user_dict[self.__user_name_lut[user_idx]].add_user_var(db_rec)
            else:
                del_vars.append(db_rec["user_var_idx"])
        if del_vars:
            self.dc.execute("DELETE FROM user_var WHERE %s" % (" OR ".join(["user_var_idx=%d" % (x) for x in del_vars])))
        # user - sge-server connection
        self.dc.execute("SELECT DISTINCT d.name, dc.device_config_idx, su.user FROM sge_user_con su, device d, device_config dc, new_config c WHERE c.name LIKE('sge_server%') AND c.new_config_idx=dc.new_config AND dc.device=d.device_idx AND su.sge_config=dc.device_config_idx ORDER BY d.name")
        for db_rec in self.dc.fetchall():
            if self.__user_name_lut.has_key(db_rec["user"]):
                self.__user_dict[self.__user_name_lut[db_rec["user"]]].add_sge_server(db_rec["device_config_idx"])
        # user - login-server connection
        self.dc.execute("SELECT DISTINCT d.name, d.device_idx, udl.user FROM user_device_login udl, device d WHERE udl.device=d.device_idx ORDER BY d.name")
        for db_rec in self.dc.fetchall():
            if self.__user_name_lut.has_key(db_rec["user"]):
                self.__user_dict[self.__user_name_lut[db_rec["user"]]].add_login_server(db_rec["device_idx"])
        # add secondary groups
        self.dc.execute("SELECT * FROM user_ggroup")
        for db_rec in self.dc.fetchall():
            group_idx, user_idx = (db_rec["ggroup"], db_rec["user"])
            if self.__user_name_lut.has_key(user_idx):
                self.__user_dict[self.__user_name_lut[user_idx]].add_secondary_group_idx(group_idx)
        # export and scratch dirs
        self.dc.execute("SELECT d.name, d.device_idx, dc.device_config_idx, c.name AS cname, cs.name AS csname, cs.value, c.new_config_idx FROM " + \
                        "device d, device_config dc, new_config c, config_str cs, device_type dt WHERE dt.device_type_idx=d.device_type AND " + \
                        "dt.identifier='H' AND dc.device=d.device_idx AND dc.new_config=c.new_config_idx AND cs.new_config=c.new_config_idx AND (cs.name LIKE('%export%') OR c.name LIKE('%quota%'))")
        self.__exp_dict, self.__quota_dict = ({}, {})
        for db_rec in self.dc.fetchall():
            if db_rec["csname"] in ["homeexport", "scratchexport"]:
                self.__exp_dict.setdefault(db_rec["csname"], {}).setdefault(db_rec["name"], []).append((db_rec["device_config_idx"],
                                                                                                        db_rec["value"].replace("%h", db_rec["name"]), ""))
            elif db_rec["cname"] in ["quota"]:
                self.__quota_dict[db_rec["name"]] = db_rec["csname"]
        # store quota_info in exp_dict
        for exp_name, exp_stuff in self.__exp_dict.iteritems():
            for d_name, e_list in exp_stuff.iteritems():
                if d_name in self.__quota_dict.keys():
                    exp_stuff[d_name] = [(x, y, self.__quota_dict[d_name]) for x, y, z in e_list]
        # set default values
        for g_name, g_stuff in self.__group_dict.iteritems():
            g_stuff.act_values_are_default()
        for u_name, u_stuff in self.__user_dict.iteritems():
            u_stuff.act_values_are_default()
    def get_num_users(self):
        return sum([value.get_num_users() for value in self.__group_dict.itervalues()])
    def get_num_groups(self):
        return len([key for key in self.__group_dict.keys()])
    def get_group(self, g_id):
        if type(g_id) in [type(0), type(0L)]:
            return self.__group_dict[self.__group_name_lut[g_id]]
        else:
            return self.__group_dict[g_id]
    def group_exists(self, g_id):
        if type(g_id) in [type(0), type(0L)]:
            return g_id in self.__group_name_lut
        else:
            return g_id in self.__group_dict
    def del_group(self, g_id):
        if type(g_id) in [type(0), type(0L)]:
            new_g_id = self.__group_name_lut[g_id]
            del self.__group_dict[g_id]
            g_id = new_g_id
        del self.__group_dict[g_id]
    def get_user(self, u_id):
        if type(u_id) in [type(0), type(0L)]:
            return self.__user_dict[self.__user_name_lut[u_id]]
        else:
            return self.__user_dict[u_id]
    def get_group_names(self, idx_list):
        return [self.__group_name_lut[x] for x in idx_list]
    def get_all_group_names(self):
        return sorted([x for x in self.__group_name_lut.keys() if type(x) == type("")])
    def get_all_user_names(self):
        return sorted([x for x in self.__user_name_lut.keys() if type(x) == type("")])
    def get_all_users(self):
        return self.__user_dict.values()
    def get_all_groups(self):
        return self.__group_dict.values()
    def build_export_str(self, act_group, act_user, export_type, default="---"):
        # export_type must be home or scratch
        if export_type == "home":
            exp_entry = act_user["export"]
        else:
            exp_entry = act_user["export_scr"]
        if exp_entry and len(act_group["%sstart" % (export_type)].strip()) > 1:
            ed_key = "%sexport" % (export_type)
            if self.__exp_dict.has_key(ed_key):
                exp_dev = None
                for ed_name, ed_stuff in self.__exp_dict[ed_key].iteritems():
                    for ed_idx, ed_start, quota_capable in ed_stuff:
                        if ed_idx == exp_entry:
                            exp_dev = (ed_name, ed_start)
                            break
                if exp_dev:
                    full_path = (os.path.normpath("%s/%s" % (ed_start, act_user[export_type]))).replace("%h", ed_name)
                    exp_path = (os.path.normpath("%s/%s" % (act_group["%sstart" % (export_type)], act_user[export_type]))).replace("%h", ed_name)
                    return "%s on %s (exported as %s)" % (full_path, ed_name, exp_path)
                else:
                    return "Error no %s-export with idx %d found" % (export_type, exp_entry)
            else:
                return "Error no exports of type '%s' found" % (export_type)
        else:
            return default
##     def get_cg_dict(self):
##         return self.__cg_dict
    def get_export_dict(self):
        return self.__exp_dict
    
def read_possible_shells():
    if os.path.isfile("/etc/shells"):
        p_shells = [y for y in [x.strip() for x in file("/etc/shells", "r").read().split("\n")] if os.path.isfile(y)]
    else:
        p_shells = ["/bin/bash", "/bin/false"]
    return sorted(p_shells)

def validate_start_path(s_path, pt, log):
    ok = True
    if s_path != "":
        if not s_path.startswith("/"):
            log.add_error("invalid %sstart-path %s" %(pt, s_path), "must start with a '/'")
            ok = False
        if len(s_path) < 3 and s_path != "/":
            log.add_error("invalid %sstart-path %s" %(pt, s_path), "too short")
            ok = False
    return ok

def show_capability_info(req, act_ug_tree, act_group, act_user, cb_field):
    cap_stack = act_ug_tree.cap_stack
    # which display mode
    if act_user:
        cap_headline = "Capabilities for user %s (actual primary group: %s):" % (act_user["login"],
                                                                                 act_group["ggroupname"])
    else:
        cap_headline = "Capabilities for group %s:" % (act_group["ggroupname"])
    info_table = html_tools.html_table(cls="user")
    act_idx_str = "0"
    for cg_idx in cap_stack.get_sorted_idxs(0, only_authorized=False):
        line_idx = 0
        act_idx_parts = [int(x) for x in act_idx_str.split(".")]
        act_idx_parts[0] += 1
        act_idx_str = "%d" % (act_idx_parts[0])
        top_cg = cap_stack[cg_idx]
        header_element = html_tools.content("%s: %s" % (act_idx_str,
                                                        top_cg.description), cls="center")
        level_list = []
        sub1_idxs = cap_stack.get_sorted_idxs(cg_idx, only_authorized=False, check_level=2)
        for sub1_idx in [x for x in sub1_idxs if x != cg_idx]:
            level_list.append((1, cap_stack[sub1_idx]))
            sub2_idxs = cap_stack.get_sorted_idxs(sub1_idx, only_authorized=False, check_level=3)
            for sub2_idx in [x for x in sub2_idxs if x not in sub1_idxs]:
                level_list.append((2, cap_stack[sub2_idx]))
                sub3_idxs = cap_stack.get_sorted_idxs(sub2_idx, only_authorized=False, check_level=4)
                for sub3_idx in [x for x in sub3_idxs if x not in sub2_idxs]:
                    level_list.append((3, cap_stack[sub3_idx]))
        for level, act_cg in level_list:
            act_idx_parts = [int(x) for x in act_idx_str.split(".")] + [0, 0, 0]
            act_idx_parts[level] += 1
            act_idx_str = ".".join(["%d" % (x) for x in act_idx_parts[:level + 1]])
            group_auth, user_auth = (False, False)
            if act_group:
                group_auth = act_group.has_capability(act_cg.name)
            if act_user:
                user_auth = act_user.capability_ok(act_cg.name)
            pre_1_str = act_idx_str
            pre_2_str = act_cg.description
            post_element = None
            if cb_field:
                if act_user and act_group and act_group.has_capability(act_cg.name):
                    post_element = html_tools.content("authorized by group", cls="left")
                else:
                    post_element = html_tools.content(cb_field, act_cg.name, cls="left")
            else:
                if group_auth or user_auth:
                    post_element = html_tools.content("authorized by %s" % ((group_auth and "group" or (user_auth and "user" or "error"))),
                                                      cls="left")
            if post_element:
                if header_element:
                    info_table[0]["class"] = "title"
                    info_table[None][1:3] = header_element
                    header_element = None
                line_idx = 1 - line_idx
                info_table[0]["class"] = "line1%d" % (line_idx)
                info_table[None][0] = html_tools.content(pre_1_str, cls="right")
                info_table[None][0] = html_tools.content(pre_2_str, cls="left")
                info_table[None][0] = post_element
    return cap_headline, info_table
##     for cg_pri in cg_pris:
##         act_cg_names = cg_pri_dict[cg_pri]
##         act_cg_names.sort()
##         for cg_name in act_cg_names:
##             group_written = False
##             act_cg = cg_dict[cg_name]
##             all_cs = act_cg.get_capabilities(True)
##             if not cb_field:
##                 if act_user:
##                     if act_group:
##                         all_cs = [x for x in all_cs if act_group.has_capability(x) or act_user.capability_ok(x)]
##                         user_cs = [x for x in all_cs if act_user.capability_ok(x, "user")]
##                     else:
##                         all_cs = [x for x in all_cs if act_user.capability_ok(x, "user")]
##                         user_cs = all_cs
##                 else:
##                     all_cs = [x for x in all_cs if act_group.has_capability(x)]
##                     user_cs = []
##             else:
##                 user_cs = []
##             act_row = 0
##             for c_name in all_cs:
##                 act_c = act_cg.get_capability(c_name)
##                 cap_written = True
##                 if not group_written:
##                     group_written = True
##                     info_table[0]["class"] = "line10"
##                     info_table[None][0:3]  = html_tools.content(act_cg["description"], cls="center", type="th")
##                 cap_idx += 1
##                 # additional fields to write
##                 add_fields = ["%d" % (act_c.get_idx())]
##                 if act_c["mother_capability"]:
##                     add_fields.append("* %s" % (act_c["mother_capability"]))
##                 if act_user and c_name in user_cs:
##                     add_fields.append("+")
##                 add_fields_str = add_fields and "(%s) " % (", ".join(add_fields)) or ""
##                 if cb_field:
##                     c_content = html_tools.content(["%s. " % (("%3d" % (cap_idx)).replace(" ", "&nbsp;")), cb_field, " %s%s" %(add_fields_str, act_c["description"])], c_name, cls="left")
##                 else:
##                     c_content = html_tools.content("%s. %s%s" % (("%3d" % (cap_idx)).replace(" ", "&nbsp;"), add_fields_str, act_c["description"]), cls="left")
##                 if act_row == 0:
##                     info_table[0][0] = c_content
##                 else:
##                     info_table[None][0] = c_content
##                 act_row += 1
##                 if act_row == 3:
##                     act_row = 0
##             if act_row:
##                 info_table[None][0:3 - act_row] = html_tools.content("&nbsp;")
##     if not cap_written:
##         info_table = None
##     return cap_headline, info_table
