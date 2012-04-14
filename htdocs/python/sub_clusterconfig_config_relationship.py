#!/usr/bin/python -Ot
# -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2008 Andreas Lang-Nevyjel, init.at
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
""" modify device relationship """
# DEAD CODE, FIXME, AJAX 

import functions
import html_tools
import tools
import cdef_basics
import logging_tools
import pprint
import re

class table_iterator(object):
    def __init__(self, **args):
        self.__num_iterators = args.get("num_iterators", 1)
        self.__iterators = [1 for idx in xrange(self.__num_iterators)]
    def get_iterator(self, idx):
        self.__iterators[idx] = 1 - self.__iterators[idx]
        return self.__iterators[idx]

class db_object(object):
    def __init__(self, req, **args):
        self.__req = req
        self.db_rec = args["db_rec"]
        self.__primary_db = args["primary_db"]
        self.__index_field = args["index_field"]
        self.db_change_list = set()
    def __getitem__(self, key):
        return self.db_rec[key]
    def __setitem__(self, key, value):
        # when called via the __setitem__ the db will get changed
        self.db_change_list.add(key)
        self.db_rec[key] = value
    def commit_db_changes(self, primary_idx):
        if self.db_change_list:
            sql_str, sql_tuple = (", ".join(["%s=%%s" % (key) for key in self.db_change_list]),
                                  tuple([self[key] for key in self.db_change_list]))
            self.__req.dc.execute("UPDATE %s SET %s WHERE %s=%d" % (self.__primary_db,
                                                                    sql_str,
                                                                    self.__index_field,
                                                                    primary_idx),
                                  sql_tuple)
    def expand(self, ret_f):
        attr_re = re.compile("(?P<pre_str>.*){(?P<attr_spec>.*)}(?P<post_str>.*)")
        new_f = []
        for act_p in ret_f:
            if act_p.startswith("*"):
                # no expansion
                pass
            else:
                while act_p.count("{") and act_p.count("}"):
                    attr_m = attr_re.match(act_p)
                    src, src_name = attr_m.group("attr_spec").split(".", 1)
                    if src == "db":
                        var_val = self[src_name]
                    elif src == "attr":
                        var_val = getattr(self, src_name)
                    else:
                        var_val = "unknown src %s (src_name %s)" % (src, src_name)
                    act_p = "%s%s%s" % (attr_m.group("pre_str"),
                                        var_val,
                                        attr_m.group("post_str"))
            new_f.append(act_p)
        return new_f

class device(db_object):
    def __init__(self, req, **args):
        self.__req = req
        self.__root = args["root"]
        db_object.__init__(self, self.__req, db_rec=args.get("db_rec", {}),
                           primary_db="device",
                           index_field="device_idx")
        self.idx = self["device_idx"]

class relationship(db_object):
    def __init__(self, req, **args):
        self.__req = req
        self.__root = args["root"]
        self.__template = args.get("template", False)
        db_object.__init__(self, self.__req, db_rec=args.get("db_rec", {}),
                           primary_db="device_relationship",
                           index_field="device_relationship_idx")
        if args.get("create", False):
            # reate new entitiy
            self.__req.dc.execute("INSERT INTO device_relationship SET name=%s", (self["name"]))
            # get dictionary from db to get the correct default-values
            self.__req.dc.execute("SELECT * FROM device_relationship WHERE genstuff_idx=%d" % (self.__req.dc.insert_id()))
            self.db_rec = self.__req.dc.fetchone()
        if not self.__template:
            self.unique_id = "gs%d" % (self["device_relationship_idx"])
            self.idx = self["device_relationship_idx"]
    def create_content(self, act_ti):
        req = self.__req
        if self.__template:
            ret_f = ["New: %s" % (self.__root.get_dev_list())]
        else:
            ret_f = ["<input name=\"{attr.unique_id}n\" value=\"{db.value}\"/>",
                     "<input name=\"{attr.unique_id}v\" value=\"{db.name}\">",
                     "<input type=checkbox name=\"{attr.unique_id}del\" />"]
        return "<tr class=\"line1%d\"><td>%s</td></tr>" % (act_ti.get_iterator(0),
                                                           "".join(self.expand(ret_f)))
#     def __getitem__(self, key):
#         return super(genstuff, self).__getitem__(key)
    def feed_args(self, args):
        if self.__template:
            new_name = args.get(self.__root.get_new_idx("genstuff"), "")
            if new_name:
                # validate new_args
                pass
                # generate new genstuff
                self.__root.add_leaf("genstuff", genstuff(self.__req, root=self.__root, create=True, db_rec={"name" : new_name}))
        else:
            if args.has_key("%sn" % (self.unique_id)):
                if args.has_key("%sdel" % (self.unique_id)):
                    # delete entry
                    self.__root.delete("genstuff", self)
                    self.__req.dc.execute("DELETE FROM genstuff WHERE genstuff_idx=%d" % (self.idx))
                else:
                    new_name = args["%sn" % (self.unique_id)]
                    new_value = args["%sv" % (self.unique_id)]
                    if self["name"] != new_name:
                        self["name"] = new_name
                    if self["value"] != new_value:
                        self["value"] = new_value
    def commit_changes(self):
        self.commit_db_changes(self.idx)

class relationship_tree(object):
    def __init__(self, req):
        self.req = req
        self.__dict = {"genstuff" : {},
                       "device"   : {}}
    def read_from_db(self):
        self.req.dc.execute("SELECT * FROM device_relationship")
        for db_rec in self.req.dc.fetchall():
            new_rel = relationship(self.req, db_rec=db_rec, root=self)
            self.add_leaf("relationship", new_rel)
        self.__new_gs = relationship(self.req, template=True, root=self)
        # fetch all devices
        self.req.dc.execute("SELECT d.name, d.device_idx FROM device d")
        self.__dev_lut = {}
        for db_rec in self.req.dc.fetchall():
            new_d = device(self.req, db_rec=db_rec, root=self)
            self.add_leaf("device", new_d)
            self.__dev_lut[new_d["name"]] = new_d["device_idx"]
    def add_leaf(self, tree_name, new_ent):
        self.__dict[tree_name][new_ent.idx] = new_ent
    def validate_tree(self):
        pass
    def get_new_idx(self, tree_name):
        return "new%s" % (tree_name)
    def get_dev_list(self):
        # return a selection-list with all hosts
        ret_f = ["<select name=\"a\">"]
        for dev_name in sorted(self.__dev_lut.keys()):
            ret_f.append("<option value=\"%d\">%s</option>" % (self.__dev_lut[dev_name],
                                                               dev_name))
        ret_f.append("</select")
        return "\n".join(ret_f)
    def delete(self, tree_name, obj):
        del self.__dict[tree_name][obj.idx]
    def parse_values(self):
        args = self.req.sys_args
        for gs_stuff in self.__dict["genstuff"].values() + [self.__new_gs]:
            gs_stuff.feed_args(args)
    def commit_changes(self):
        args = self.req.sys_args
        for gs_stuff in self.__dict["genstuff"].values():
            gs_stuff.commit_changes()
    def create_content(self):
        req = self.req
        act_ti = table_iterator()
        table_content = []
        for gs_idx, gs_stuff in self.__dict["genstuff"].iteritems():
            table_content.append(gs_stuff.create_content(act_ti))
        table_content.append(self.__new_gs.create_content(act_ti))
        req.write("<table class=\"normalsmall\">%s</table>" % ("\n".join(table_content)))

def process_page(req):
    if req.conf["genstuff"].has_key("AUTO_RELOAD"):
        del req.conf["genstuff"]["AUTO_RELOAD"]
    functions.write_header(req)
    functions.write_body(req)
    req.write("<form action=\"%s.py?%s\" method = post>" % (req.module_name,
                                                            functions.get_sid(req)))
    tt = relationship_tree(req)
    tt.read_from_db()
    tt.validate_tree()
    tt.parse_values()
    tt.commit_changes()
    tt.create_content()
    req.write(html_tools.submit_button(req, "select")(""))
    req.write("</form>")
