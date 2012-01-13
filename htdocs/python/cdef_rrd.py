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
""" object definitions for cluster-history """

import cdef_basics
import logging_tools
import colorsys

class rrd_rra(cdef_basics.db_obj):
    def __init__(self, rrd_class, idx, db_rec):
        cdef_basics.db_obj.__init__(self, "rrd_rra_%d" % (idx), idx)
        #cdef_rrd.rrd_rra.__init__(self, "rrd_rra_%d" % (db_rec["rrd_rra_idx"]), db_rec["rrd_rra_idx"], db_rec)
        self.set_valid_keys({"rrd_class" : "i",
                             "cf"        : "i",
                             "steps"     : "i",
                             "rows"      : "i",
                             "xff"       : "f"},
                            ["rrd_class"])
        self.init_sql_changes({"table" : "rrd_rra",
                               "idx"   : self.idx})
        if not self.idx:
            self.set_suffix(rrd_class.get_new_rra_suffix())
        self.set_parameters(db_rec)
        self.__rrd_class = rrd_class
    def get_pdp_length(self):
        if self.idx:
            return logging_tools.get_time_str(self["steps"] * self.__rrd_class["step"])
        else:
            return ""
    def get_total_length(self):
        if self.idx:
            return logging_tools.get_time_str(self["rows"] * self["steps"] * self.__rrd_class["step"])
        else:
            return ""
    def copy_instance(self):
        new_rra_c = rrd_rra(self.__rrd_class, self.idx, {})
        new_rra_c.copy_keys(self)
        return new_rra_c
    def get_size(self, mult=1):
        tot_rows = self["rows"]
        return 8 * tot_rows * mult
        
class rrd_class(cdef_basics.db_obj):
    def __init__(self, idx, db_rec):
        cdef_basics.db_obj.__init__(self, "rrd_class_%d" % (idx), idx)
        self.set_valid_keys({"name"      : "s",
                             "step"      : "i",
                             "heartbeat" : "i"},
                            [])
        self.init_sql_changes({"table" : "rrd_class",
                               "idx"   : self.idx})
        self.set_parameters(db_rec)
        self.rra_tree = {}
        self.count = 0
        self.set_new_rra_suffix()
    def _add_rrd_rra(self, db_rec):
        if type(db_rec["rrd_rra_idx"]) in [type(0), type(0L)]:
            new_rrd_rra = rrd_rra(self, db_rec["rrd_rra_idx"], db_rec)
            self.rra_tree[db_rec["rrd_rra_idx"]] = new_rrd_rra
            new_rrd_rra.act_values_are_default()
    def _add_new_rrd_rra(self, def_dict):
        def_dict["rrd_rra_idx"] = 0
        if not def_dict.has_key("rrd_class"):
            def_dict["rrd_class"] = self.idx
        self._add_rrd_rra(def_dict)
    def del_rrd_rra(self, idx):
        del self.rra_tree[idx]
    def get_rra_idxs(self):
        # place 0 at last
        zero_present = 0 in self.rra_tree.keys()
        sort_dict = dict([((rra["steps"], rra["rows"], rra["cf"]), idx) for idx, rra in self.rra_tree.iteritems() if idx])
        idxs = sort_dict.keys()
        idxs.sort()
        idxs = [sort_dict[x] for x in idxs]
        if zero_present:
            idxs.append(0)
        return idxs
    def get_rra(self, key):
        return self.rra_tree[key]
    def copy_instance(self):
        new_rrd_c = rrd_class(self.idx, {})
        new_rrd_c.copy_keys(self)
        return new_rrd_c
    def get_new_rra_suffix(self):
        return self.nrs
    def set_new_rra_suffix(self):
        self.nrs = "%snv" % (self.get_suffix())
    def post_create_func(self):
        self.set_new_rra_suffix()
    def copy_rrd_rras(self, req, other_class):
        for idx, rra_stuff in other_class.rra_tree.iteritems():
            if idx:
                new_dict = {"rrd_class" : self.idx,
                            "cf"        : rra_stuff["cf"],
                            "steps"     : rra_stuff["steps"],
                            "rows"      : rra_stuff["rows"],
                            "xff"       : rra_stuff["xff"]}
                req.dc.execute("INSERT INTO rrd_rra SET rrd_class=%s, cf=%s, steps=%s, rows=%s, xff=%s", (self.idx, rra_stuff["cf"], rra_stuff["steps"], rra_stuff["rows"], rra_stuff["xff"]))
                new_dict["rrd_rra_idx"] = req.dc.insert_id()
                self._add_rrd_rra(new_dict)
    def get_size(self, mult=1):
        tot_rows = 0
        for idx, rra_stuff in self.rra_tree.iteritems():
            if idx:
                tot_rows += rra_stuff["rows"]
        return 8 * tot_rows * mult

class ccl_event(cdef_basics.db_obj):
    def __init__(self, idx, db_rec):
        cdef_basics.db_obj.__init__(self, "ccl_event_%d" % (idx), idx)
        self.set_valid_keys({"device"          : "i",
                             "rrd_data"        : "i",
                             "threshold"       : "f",
                             "threshold_class" : "i",
                             "cluster_event"   : "i",
                             "hysteresis"      : "f",
                             "disabled"        : "b",
                             "device_class"    : "i",
                             "locations"       : ("f", "ccl_dloc_con", "device_location"),
                             "groups"          : ("f", "ccl_dgroup_con", "device_group"),
                             "users"           : ("f", "ccl_user_con", "user")},
                            [])
        self.init_sql_changes({"table" : "ccl_event",
                               "idx"   : self.idx})
        self.set_parameters(db_rec)
    def get_hbar_info(self, ev_dict, key_dict):
        thresh, hyst = (self["threshold"],
                        self["hysteresis"])
        bar_color = key_dict["color"]
        # modify bar color
        hue, light, sat = colorsys.rgb_to_hls(*[float(int(x, 16)) / 256. for x in [bar_color[0:2], bar_color[2:4], bar_color[4:]]])
        new_bar_color = "".join(["%02x" % (x * 255) for x in list(colorsys.hls_to_rgb(hue, light < 0.8 and light + 0.2 or light - 0.2, sat))])
        return [{"lower"   : thresh - hyst / 2.,
                 "upper"   : thresh + hyst / 2.,
                 "pri"     : 0,
                 "color"   : new_bar_color,
                 "outline" : False},
                {"lower" : thresh,
                 "pri"   : 5,
                 "color" : bar_color}]
    def copy_instance(self):
        new_ccl_ev = ccl_event(self.idx, {})
        new_ccl_ev.copy_keys(self)
        return new_ccl_ev
