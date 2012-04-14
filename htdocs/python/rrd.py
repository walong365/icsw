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
""" webfrontend interface for cluster-history """

import time
import os.path
import re
import logging_tools
import functions
import tools
import pprint
import html_tools
import cdef_rrd
import random

def module_info():
    return {"ch" : {"description"           : "Cluster history",
                    "enabled"               : 1,
                    "default"               : 0,
                    "left_string"           : "Cluster history",
                    "right_string"          : "Time-tracked device parameters",
                    "capability_group_name" : "info",
                    "priority"              : -50}}

class new_cluster_event_vs(html_tools.validate_struct):
    def __init__(self, req):
        # cluster_event dict
        self.__cluster_events = html_tools.selection_list(req, "cevev", {}, sort_new_keys=False)
        self.__raw_cluster_events = {}
        req.dc.execute("SELECT * FROM cluster_event ORDER BY name")
        for db_rec in req.dc.fetchall():
            self.__raw_cluster_events[db_rec["cluster_event_idx"]] = db_rec
            self.__cluster_events[db_rec["cluster_event_idx"]] = "%s (%s)" % (db_rec["name"],
                                                                              db_rec["description"])
        # device classes
        self.__device_classes = html_tools.selection_list(req, "cevdc", {}, sort_new_keys=False)
        self.__raw_device_classes = {}
        req.dc.execute("SELECT * FROM device_class ORDER BY priority")
        for db_rec in req.dc.fetchall():
            self.__raw_device_classes[db_rec["device_class_idx"]] = db_rec
            self.__device_classes[db_rec["device_class_idx"]] = "%s (%d)" % (db_rec["classname"],
                                                                             db_rec["priority"])
        # locations
        self.__locations = html_tools.selection_list(req, "cedl", {}, multiple=True, sort_new_keys=False, size=3)
        req.dc.execute("SELECT * FROM device_location ORDER BY location")
        for db_rec in req.dc.fetchall():
            self.__locations[db_rec["device_location_idx"]] = db_rec["location"]
        # device_groups
        self.__device_groups = html_tools.selection_list(req, "cedg", {}, multiple=True, sort_new_keys=False, size=3)
        req.dc.execute("SELECT * FROM device_group ORDER BY name")
        for db_rec in req.dc.fetchall():
            self.__device_groups[db_rec["device_group_idx"]] = db_rec["name"]
        # users
        self.__users = html_tools.selection_list(req, "cedu", {}, multiple=True, sort_new_keys=False, size=3)
        req.dc.execute("SELECT * FROM user ORDER BY login")
        for db_rec in req.dc.fetchall():
            self.__users[db_rec["user_idx"]] = db_rec["login"]
        self.__device_classes.mode_is_normal()
        self.__cluster_events.mode_is_normal()
        self.__locations.mode_is_normal()
        self.__device_groups.mode_is_normal()
        self.__users.mode_is_normal()
        new_dict = {"threshold_class" : {"he"  : html_tools.selection_list(req, "cevclass", {1  : "ascending",
                                                                                             0  : "crossing",
                                                                                             -1 : "descending"}, initial_mode="n"),
                                         "def" : 1},
                    "threshold"       : {"he"  : html_tools.text_field(req, "cevth", size=8, display_len=8),
                                         "new" : True,
                                         "vf"  : self.validate_threshold,
                                         "def" : ""},
                    "hysteresis"      : {"he"  : html_tools.text_field(req, "cevhys", size=8, display_len=8),
                                         "vf"  : self.validate_hysteresis,
                                         "def" : 2.},
                    "cluster_event"   : {"he"  : self.__cluster_events,
                                         "def" : self.__cluster_events.list_dict.keys()[0]},
                    "device_class"    : {"he"  : self.__device_classes,
                                         "def" : self.__device_classes.list_dict.keys()[0]},
                    "disabled"        : {"he"  : html_tools.checkbox(req, "cevdis"),
                                         "def" : False},
                    "del"             : {"he"  : html_tools.checkbox(req, "cevdel", auto_reset=1),
                                         "del" : 1},
                    "locations"       : {"he"  : self.__locations,
                                         "vf"  : self._validate_locations,
                                         "def" : []},
                    "groups"          : {"he"  : self.__device_groups,
                                         "vf"  : self._validate_device_groups,
                                         "def" : []},
                    "users"           : {"he"  : self.__users,
                                         "vf"  : self._validate_users,
                                         "def" : []}}
        self.hidden_flag = html_tools.checkbox(req, "cevany")
        html_tools.validate_struct.__init__(self, req, "Cluster Event", new_dict)
    def get_cluster_event_dict(self):
        return self.__raw_cluster_events
    def get_classes(self, dc_idx):
        # returns all dev_class_idxs with a priority below the given one
        return [class_idx for class_idx, class_stuff in self.__raw_device_classes.iteritems() if class_stuff["priority"] <= self.__raw_device_classes[dc_idx]["priority"]]
    def validate_threshold(self):
        try:
            f_val = float(self.new_val_dict["threshold"])
        except ValueError:
            raise ValueError, "must be a float"
        else:
            self.new_val_dict["threshold"] = f_val
    def validate_hysteresis(self):
        try:
            f_val = float(self.new_val_dict["hysteresis"])
        except ValueError:
            raise ValueError, "must be a float"
        else:
            self.new_val_dict["hysteresis"] = f_val
    def _get_list(self, idx_f, in_dict):
        if not idx_f:
            return "empty"
        else:
            return ", ".join([in_dict.get(x, {"name" : "key %d not found" % (x)})["name"] for x in idx_f])
    def _validate_device_groups(self):
        self.new_val_dict["groups"] = [x for x in self.new_val_dict["groups"] if self.__device_groups.list_dict.has_key(x)]
        self.old_val_dict["groups"].sort()
        self.new_val_dict["groups"].sort()
        self.old_b_val_dict["groups"] = self._get_list(self.old_val_dict["groups"], self.__device_groups.list_dict)
        self.new_b_val_dict["groups"] = self._get_list(self.new_val_dict["groups"], self.__device_groups.list_dict)
    def _validate_locations(self):
        self.new_val_dict["locations"] = [x for x in self.new_val_dict["locations"] if self.__locations.list_dict.has_key(x)]
        self.old_val_dict["locations"].sort()
        self.new_val_dict["locations"].sort()
        self.old_b_val_dict["locations"] = self._get_list(self.old_val_dict["locations"], self.__locations.list_dict)
        self.new_b_val_dict["locations"] = self._get_list(self.new_val_dict["locations"], self.__locations.list_dict)
    def _validate_users(self):
        self.new_val_dict["users"] = [x for x in self.new_val_dict["users"] if self.__users.list_dict.has_key(x)]
        self.old_val_dict["users"].sort()
        self.new_val_dict["users"].sort()
        self.old_b_val_dict["users"] = self._get_list(self.old_val_dict["users"], self.__users.list_dict)
        self.new_b_val_dict["users"] = self._get_list(self.new_val_dict["users"], self.__users.list_dict)

class rrd_data(object):
    def __init__(self, req, db_rec):
        self.__req = req
        self.idx = db_rec["rrd_data_idx"]
        self.info = db_rec["info"]
        self.device_idx = db_rec["device_idx"]
        self.description = db_rec["description"]
        self.descrs = (db_rec["descr1"],
                       db_rec["descr2"],
                       db_rec["descr3"],
                       db_rec["descr4"])
        self.base, self.unit, self.factor = (db_rec["base"],
                                             db_rec["unit"],
                                             db_rec["factor"])
        self.from_snmp = db_rec["from_snmp"]
        # cluster event dictionary
        self.event_dict = {}
    def get_header_str(self):
        return {"csi"   : "Cluster software",
                "df"    : "Disk",
                "io"    : "Input / Output",
                "load"  : "Load",
                "mail"  : "Mail subsystem",
                "mem"   : "Memory",
                "net"   : "Network",
                "num"   : "Num",
                "proc"  : "Process table",
                "sql"   : "SQL",
                "swap"  : "Swap tables",
                "vms"   : "CPU load",
                "snmp"  : "SNMP",
                "apc"   : "APC",
                "temp"  : "Temperature",
                "hum"   : "Humidity",
                "flow"  : "Airflow",
                "rms"   : "Resource Managment System",
                "nag"   : "Nagios",
                "usv"   : "Battery information",
                "lic"   : "License information",
                "quota" : "Quota information",
                "ovpn"  : "OpenVPN",
                "power" : "Power information",
                "fan"   : "Fan / Blower information",
                "ping"  : "Ping remote",
                "ns"    : "Nameserver"}.get(self.descrs[0], "* %s (ud) *" % (self.descrs[0]))
    def get_info_str(self):
        return self.info
    def set_lmma_result(self, v_stuff):
        self.__lmma_result = v_stuff
    def get_lmma_result(self, lmma_type):
        if self.__lmma_result.has_key(lmma_type):
            act_val = self.__lmma_result[lmma_type]
            if act_val == None:
                return "NaN", "errorcenter"
            elif type(act_val) == type(""):
                if act_val.lower() == "nan":
                    return "NaN", "errorcenter"
                else:
                    return act_val, "warncenter"
            else:
                return self._beautify_val(act_val), "center"
        else:
            return "Err", "errorcenter"
    def _beautify_val(self, act_v):
        pfix_list = ["", "k", "M", "G", "T", "E"]
        while True:
            if act_v <= self.base or self.base < 10:
                break
            pfix_list.pop(0)
            act_v /= self.base
        if self.unit == "1":
            d_unit = ""
        else:
            d_unit = self.unit
        return "%5.2f %s%s" % (act_v, pfix_list[0], d_unit)
    def _add_active_cluster_event(self, db_rec):
        ce_idx = db_rec["ccl_event_idx"]
        if ce_idx not in self.event_dict.keys():
            db_rec["users"] = []
            db_rec["locations"] = []
            db_rec["groups"] = []
            self.event_dict[ce_idx] = cdef_rrd.ccl_event(ce_idx, db_rec)
        act_ev = self.event_dict[ce_idx]
        if db_rec["ccl_dgroup_con_idx"] and db_rec["device_group"] not in act_ev["groups"]:
            act_ev["groups"].append(db_rec["device_group"])
            act_ev["groups"].sort()
        if db_rec["ccl_dloc_con_idx"] and db_rec["device_location"] not in act_ev["locations"]:
            act_ev["locations"].append(db_rec["device_location"])
            act_ev["locations"].sort()
        if db_rec["ccl_user_con_idx"] and db_rec["user"] not in act_ev["users"]:
            act_ev["users"].append(db_rec["user"])
            act_ev["users"].sort()
    def fix_events(self):
        for event in self.event_dict.itervalues():
            event.act_values_are_default()
    def _get_hbar_info(self, key_dict):
        return sum([ev_stuff.get_hbar_info(self.__ce_vs.get_cluster_event_dict(), key_dict) for ev_idx, ev_stuff in self.event_dict.iteritems() if ev_idx], [])
    def link_ce_vs(self, ce_vs):
        self.__ce_vs = ce_vs
    def _check_for_changes(self, change_log):
        # changes to report
        ce_vs = self.__ce_vs
        low_submit = ce_vs.hidden_flag.check_selection("n%d" % (self.idx))
        ce_vs.set_submit_mode(low_submit)
        ce_vs.init_delete_list()
        ce_vs.set_old_db_obj_idx("n%d" % (self.idx))
        num_changes = 0
        def_dict = ce_vs.get_default_dict()
        def_dict["ccl_event_idx"] = 0
        def_event = cdef_rrd.ccl_event(def_dict["ccl_event_idx"], def_dict)
        def_event.set_suffix("n%d" % (self.idx))
        ce_vs.hidden_flag[def_event.get_suffix()] = True
        def_event["rrd_data"] = self.idx
        def_event["device"] = self.device_idx
        def_event.act_values_are_default()
        self.event_dict[def_event.idx] = def_event
        for ev_idx in self.get_event_idxs():
            ev_stuff = self.event_dict[ev_idx]
            ce_vs.hidden_flag[ev_stuff.get_suffix()] = True
            ce_vs.link_object(ev_idx, ev_stuff)
            ce_vs.check_for_changes()
            if not ce_vs.check_delete():
                if ce_vs.process_changes(change_log, self.event_dict):
                    num_changes += 1
                if ce_vs.check_create():
                    ce_vs.hidden_flag[ev_stuff.get_suffix()] = True
            ce_vs.unlink_object()
        if ce_vs.get_delete_list():
            num_changes += 1
            for ev_idx in ce_vs.get_delete_list():
                change_log.add_ok("Delete Clusterevent", "SQL")
                del self.event_dict[ev_idx]
            for del_table in ["ccl_dloc_con", "ccl_dgroup_con", "ccl_event_log", "ccl_user_con"]:
                self.__req.dc.execute("DELETE FROM %s WHERE %s" % (del_table,
                                                                   " OR ".join(["ccl_event=%d" % (x) for x in ce_vs.get_delete_list()])))
            self.__req.dc.execute("DELETE FROM ccl_event WHERE %s" % (" OR ".join(["ccl_event_idx=%d" % (x) for x in ce_vs.get_delete_list()])))
        return num_changes
    def get_event_idxs(self):
        idx_list = self.event_dict.keys()
        zero_in_list = 0 in idx_list
        if zero_in_list:
            idx_list.remove(0)
        idx_list.sort()
        if zero_in_list:
            idx_list.append(0)
        return idx_list
    def _get_affected_list(self, event):
        if event["device_class"] and event["locations"] and event["groups"]:
            self.__req.dc.execute("SELECT d.name FROM device d, device_type dt WHERE dt.device_type_idx=d.device_type AND dt.identifier != 'MD' AND " + \
                                  "(%s) AND (%s) AND (%s)" % (" OR ".join(["d.device_class=%d" % (x) for x in self.__ce_vs.get_classes(event["device_class"]) + [0]]),
                                                              " OR ".join(["d.device_location=%d" % (x) for x in event["locations"] + [0]]),
                                                              " OR ".join(["d.device_group=%d" % (x) for x in event["groups"]])))
            dev_list = [x["name"] for x in self.__req.dc.fetchall()]
        else:
            dev_list = []
        return dev_list
    def get_event_info_table(self, ar_tree, dev_names):
        dev_structs = [ar_tree[dev_name] for dev_name in dev_names]
        return html_tools.content(self.get_event_info(dev_structs), cls="left")
    def get_event_info(self, dev_structs, event_idx=0):
        ret_list = []
        if event_idx:
            idx_list = [event_idx]
        else:
            idx_list = [x for x in self.get_event_idxs() if x]
            if idx_list:
                ret_list.append("%s defined" % (logging_tools.get_plural("active event", len(idx_list))))
            else:
                ret_list.append("no active events defined")
        pce_dict = dict([(dev_struct.name, dev_struct.get_num_passive_cluster_events(event_idx)) for dev_struct in dev_structs])
        # remove empty pce
        pce_dict = dict([(k, v) for k, v in pce_dict.iteritems() if v])
        num_pce = sum(pce_dict.values(), 0)
        if num_pce:
            ret_list.append("%s triggered on %s in timeframe" % (logging_tools.get_plural("passive event", num_pce),
                                                                 logging_tools.get_plural("device", len(pce_dict.keys()))))
        else:
            ret_list.append("no passive events")
        return ", ".join(ret_list)
    def get_event_table(self, ar_tree, dev_names):
        dev_struct = ar_tree[dev_names[0]]
        idx_list = self.get_event_idxs()
        event_table = html_tools.html_table(cls="blind")
        event_table[0]["class"] = "line01"
        for h_line in ["Threshold", "del", "class", "hysteresis", "event", "device_class", "disabled", "locations", "device_groups", "users"]:
            event_table[None][0] = html_tools.content(h_line, cls="center", type="th")
        line_idx, line_num = (0, 2)
        for idx in idx_list:
            line_idx = 1 - line_idx
            event = self.event_dict[idx]
            is_new = (idx == 0) and True or False
            if is_new:
                event_table[0]["class"] = "line31"
                event_table[None][0:2] = html_tools.content(["New: ", self.__ce_vs.get_he("threshold"), self.unit], event.get_suffix(), cls="left")
            else:
                event_table[0]["class"] = "line1%d" % (line_idx)
                event_table[None][0] = html_tools.content([self.__ce_vs.get_he("threshold"), " ", self.unit], event.get_suffix(), cls="left")
                event_table[None][0] = html_tools.content(self.__ce_vs.get_he("del")      , event.get_suffix(), cls="errormin")
            event_table[None][0] = html_tools.content([self.__ce_vs.get_he("threshold_class"),
                                                       self.__ce_vs.hidden_flag.create_hidden_var(event.get_suffix())],
                                                      event.get_suffix(), cls="center")
            event_table[None][0] = html_tools.content(self.__ce_vs.get_he("hysteresis")     , event.get_suffix(), cls="center")
            event_table[None][0] = html_tools.content(self.__ce_vs.get_he("cluster_event")  , event.get_suffix(), cls="center")
            event_table[None][0] = html_tools.content(self.__ce_vs.get_he("device_class")   , event.get_suffix(), cls="center")
            event_table[None][0] = html_tools.content(self.__ce_vs.get_he("disabled")       , event.get_suffix(), cls="center")
            if is_new:
                event_table[None][0:3] = html_tools.content("&nbsp;", cls="center")
            else:
                event_table[None:is_new and 1 or 3][0] = html_tools.content(self.__ce_vs.get_he("locations")    , event.get_suffix(), cls="center")
                event_table[None:is_new and 1 or 3][0] = html_tools.content(self.__ce_vs.get_he("groups")       , event.get_suffix(), cls="center")
                event_table[None:is_new and 1 or 3][0] = html_tools.content(self.__ce_vs.get_he("users")        , event.get_suffix(), cls="center")
            if not is_new:
                event_table[line_num + 1]["class"] = "line1%d" % (line_idx)
                event_table[None][1:7] = html_tools.content(self.get_event_info([dev_struct], idx), cls="left")
                event_table[line_num + 2]["class"] = "line1%d" % (line_idx)
                dev_list = self._get_affected_list(event)
                event_table[None][1:7] = html_tools.content(dev_list and "%s affected: %s" % (logging_tools.get_plural("Device", len(dev_list)),
                                                                                              logging_tools.compress_list(dev_list)) or "No devices affected", cls="left")
                line_num += 2
            line_num += 1
        return event_table

class rrd_device(object):
    # boot event color lut
    be_color_lut = {1 : {"color" : "00fff0",
                         "text"  : "boot maintenance"},
                    2 : {"color" : "0f0ff0",
                         "text"  : "boot other"},
                    3 : {"color" : "ff00f0",
                         "text"  : "reset"},
                    4 : {"color" : "0ff080",
                         "text"  : "halt"},
                    5 : {"color" : "ff8080",
                         "text"  : "got IP address"}}
    def __init__(self, req, db_rec):
        self.__req = req
        self.name = db_rec["name"]
        self.dg_name = db_rec["dg_name"]
        self.description = db_rec["description"]
        self.rrd_class_idx = db_rec["rrd_class"]
        self.identifier = db_rec["identifier"]
        self.idx = db_rec["device_idx"]
        self.save_vectors = db_rec["save_rrd_vectors"]
        self.suffix = "d%d" % (self.idx)
        self.cluster_device_group = db_rec["cluster_device_group"]
        # boot events
        self.__boot_events = {}
        # cluster events
        self.__passive_cluster_events = {}
        self.rrd_tree = {}
        self.num_rrd_data = 0
        self.set_rrd_server_status("error not set", {})
        self.__dummy_device = False
    def is_dummy_device(self, set=None):
        if set is not None:
            self.__dummy_device = set
        return self.__dummy_device
    def get_name(self):
        my_name = self.name
        if self.identifier == "MD":
            if my_name.startswith("METADEV_"):
                my_name = "%s (metadevice)" % (my_name[8:])
        return my_name
    def add_boot_event(self, db_rec, node_log_idx, user_log_idx):
        if db_rec["log_source"] == node_log_idx:
            # node log
            self.__boot_events[db_rec["ts"]] = self.be_color_lut[db_rec["user"]]
        else:
            # user log, check for apc-command
            if db_rec["text"].lower().count("apc"):
                self.__boot_events[db_rec["ts"]] = {"color" : "000000",
                                                    "text"  : db_rec["text"]}
    def add_passive_cluster_event(self, db_rec):
        sd_name = db_rec["src_dev_name"]
        if sd_name.startswith("METADEV_"):
            sd_name = "%s [md]" % (sd_name[8:])
        self.__passive_cluster_events[db_rec["ts"]] = {"db_rec" : db_rec,
                                                       "color"  : db_rec["color"],
                                                       "text"   : "psvCE %s (from source %s, key %s)" % (db_rec["name"],
                                                                                                         sd_name,
                                                                                                         db_rec["descr"])}
    def get_num_passive_cluster_events(self, ccl_idx=0):
        return len([True for value in self.__passive_cluster_events.itervalues() if ccl_idx == 0 or ccl_idx == value["db_rec"]["ccl_event"]])
    def get_passive_cluster_events(self):
        return self.__passive_cluster_events
    def get_device_options(self, rrd_compounds, act_rrd_data_tree, sel_data):
        c_list = rrd_compounds["compound_list"]
        dev_opts = {}
        if self.__boot_events or self.__passive_cluster_events:
            # add boot events as VRULES
            dev_opts["vrules"] = self.__boot_events
            for b_idx, b_stuff in self.__passive_cluster_events.iteritems():
                dev_opts["vrules"][b_idx] = b_stuff
        dev_opts["hbars"] = dict([(key, self.rrd_tree[key]._get_hbar_info(act_rrd_data_tree.get_rrd_options(key))) for key in sel_data if self.rrd_tree.has_key(key)])
        return dev_opts
    def _add_rrd_data(self, db_rec):
        if db_rec["descr"]:
            self.num_rrd_data += 1
            self.rrd_tree[db_rec["descr"]] = rrd_data(self.__req, db_rec)
    def get_rrd_info_str(self):
        if self.num_rrd_data:
            return "%s found" % (logging_tools.get_plural("RRD-record", self.num_rrd_data))
        else:
            return "no RRD-data found"
    def set_rrd_server_status(self, srv_stat, node_dict):
        self.__rrd_server_status = srv_stat
        if srv_stat.startswith("ok"):
            if len(node_dict[self.name]) == 2:
                self.__update_time, self.__update_type = node_dict[self.name]
                self.__update_step = 0
            else:
                self.__update_time, self.__update_type, self.__update_step = node_dict[self.name]
    def _get_step_info_str(self):
        return self.__update_step and "%d seconds" % (self.__update_step) or "unknown"
    def get_rrd_server_status(self):
        if self.__rrd_server_status.startswith("ok"):
            if self.__update_time:
                act_time = time.time()
                diff_time = abs(act_time - self.__update_time)
                if diff_time < 300:
                    return "ok", "ok %s ago (%s), step is %s" % (logging_tools.get_plural("second", diff_time),
                                                                 self.__update_type,
                                                                 self._get_step_info_str())
                else:
                    return "warn", "warning %s (%s), step is %s" % (time.strftime("%a, %d. %b %Y %H:%M:%S", time.localtime(self.__update_time)),
                                                                    self.__update_type,
                                                                    self._get_step_info_str())
            else:
                return "warn", "warning time and type not set"
        else:
            return "error", self.__rrd_server_status
    def link_html_items(self, class_list, (save_button, global_save_setting), low_submit, change_log):
        self.new_rrd_class_idx = class_list.check_selection(self.suffix, self.rrd_class_idx)
        change_dict = {}
        if self.new_rrd_class_idx != self.rrd_class_idx:
            change_dict["rrd_class"] = self.new_rrd_class_idx
            change_log.add_ok("Changing RRD_class for device %s" % (self.name), "SQL")
        save_vectors = {0 : save_button.check_selection(self.suffix, self.save_vectors and not low_submit),
                        1 : 1,
                        2 : 0}[global_save_setting]
        if self.save_vectors != save_vectors:
            change_dict["save_rrd_vectors"] = save_vectors and 1 or 0
            self.save_vectors = save_vectors
            change_log.add_ok("Setting save_vector to %s device %s" % (self.save_vectors and "enabled" or "disabled", self.name), "SQL")
        save_button[self.suffix] = self.save_vectors
        if change_dict:
            self.__req.dc.execute("UPDATE device SET %s WHERE name=%%s" % (", ".join(["%s=%%s" % (key) for key in change_dict.keys()])),
                                  tuple([change_dict[key] for key in change_dict.keys()] + [self.name]))
            return [self.name]
        else:
            return []
        
class rrd_tree(object):
    def __init__(self, req, dev_sel):
        self.__req = req
        # name -> index
        self.__dev_tree = {}
        self.__dev_names, self.__devg_names = ([], [])
        # dg_name -> dev_names
        self.__devg_tree = {}
        # fetch log status
        self.__log_status = tools.get_all_log_sources(req.dc)
        # device selection
        self.__dev_sel = dev_sel
        # cluster_device_group_info
        self.__cdg_info = None
        # fetch device tree
        sql_str = "SELECT d.name, d.rrd_class, d.device_idx, d.save_rrd_vectors, dg.name AS dg_name, dt.identifier, dt.description, rs.rrd_set_idx, COUNT(ra.rrd_set) AS rra_count, dg.cluster_device_group FROM " + \
            "device_group dg, device_type dt, device d LEFT JOIN rrd_set rs ON rs.device=d.device_idx LEFT JOIN rrd_data ra ON ra.rrd_set=rs.rrd_set_idx WHERE " + \
            "dt.device_type_idx=d.device_type AND dg.device_group_idx=d.device_group%s GROUP BY d.name, rs.rrd_set_idx" % (dev_sel and " AND (%s)" % (" OR ".join(["d.device_idx=%d" % (x) for x in dev_sel])) or "")
        req.dc.execute(sql_str)
        self.__dev_name_lut = {}
        for db_rec in req.dc.fetchall():
            if not self.__dev_tree.has_key(db_rec["name"]):
                self.__dev_name_lut[db_rec["device_idx"]] = db_rec["name"]
                self._add_device(db_rec)
    def add_detailed_rra_info(self):
        self.__req.dc.execute("SELECT d.name, d.rrd_class, d.device_idx, d.save_rrd_vectors, dg.name AS dg_name, dt.identifier, dt.description, rs.rrd_set_idx, ra.*, dg.cluster_device_group FROM " + \
                              "device d, device_group dg, device_type dt, rrd_set rs LEFT JOIN rrd_data ra ON ra.rrd_set=rs.rrd_set_idx WHERE " + \
                              "dt.device_type_idx=d.device_type AND rs.device=d.device_idx AND dg.device_group_idx=d.device_group%s" % (self.__dev_sel and " AND (%s)" % (" OR ".join(["d.device_idx=%d" % (x) for x in self.__dev_sel])) or ""))
        for db_rec in self.__req.dc.fetchall():
            self.__dev_tree[db_rec["name"]]._add_rrd_data(db_rec)
    def get_cdg_info(self):
        return self.__cdg_info
    def fetch_cluster_events(self, ard_tree):
        if type(ard_tree) == type(0):
            # use ard_tree as number of days to check in the past
            stime_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time() - ard_tree * 24 * 3600))
            etime_str = time.strftime("%Y-%m-%d 23:59:59", time.localtime(time.time()))
        else:
            stime_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time() - ard_tree.time_frame["start"] * 60))
            etime_str = time.strftime("%Y-%m-%d 23:59:59", time.localtime(time.time() - ard_tree.time_frame["end"] * 60))
        if self.__dev_sel:
            dev_sel_str = " AND (%s)" % (" OR ".join(["cl.device=%d" % (x) for x in self.__dev_sel]))
        else:
            dev_sel_str = ""
        sql_str = "SELECT ev.name, ev.color, cl.device, d.name AS src_dev_name, cl.ccl_event, rd.descr, UNIX_TIMESTAMP(cl.date) AS ts FROM ccl_event_log cl, cluster_event ev, ccl_event ccl, device d, rrd_data rd WHERE " + \
                  " ccl.ccl_event_idx=cl.ccl_event AND cl.cluster_event=ev.cluster_event_idx AND ccl.device=d.device_idx AND ccl.rrd_data=rd.rrd_data_idx AND cl.date > '%s' AND cl.date < '%s'%s" % (stime_str,
                                                                                                                                                                                                      etime_str,
                                                                                                                                                                                                      dev_sel_str)
        self.__req.dc.execute(sql_str)
        # dict for unknown events
        unk_dev_dict = {}
        for db_rec in self.__req.dc.fetchall():
            if self.__dev_name_lut.has_key(db_rec["device"]):
                self.__dev_tree[self.__dev_name_lut[db_rec["device"]]].add_passive_cluster_event(db_rec)
            else:
                unk_dev_dict.setdefault(db_rec["device"], []).append(db_rec)
                #self.__dev_name_lut[db_rec["device_idx"]] = db_rec["name"]
                #self._add_device(db_rec)
        if unk_dev_dict:
            sql_str = "SELECT d.name, d.rrd_class, d.device_idx, d.save_rrd_vectors, dg.name AS dg_name, dg.cluster_device_group, dt.identifier, dt.description, d2.name AS src_dev_name, rd.descr FROM " + \
                      "device d, device_group dg, device_type dt, device d2, ccl_event ccl, rrd_data rd WHERE " + \
                      "dt.device_type_idx=d.device_type AND dg.device_group_idx=d.device_group AND ccl.device=d2.device_idx AND ccl.rrd_data=rd.rrd_data_idx AND " + \
                      "(%s)" % (" OR ".join(["d.device_idx=%d" % (x) for x in unk_dev_dict.keys()]))
            self.__req.dc.execute(sql_str)
            for db_rec in self.__req.dc.fetchall():
                self.__dev_name_lut[db_rec["device_idx"]] = db_rec["name"]
                new_dev = self._add_device(db_rec, True)
                for ccl_ev in unk_dev_dict[db_rec["device_idx"]]:
                    self.__dev_tree[self.__dev_name_lut[db_rec["device_idx"]]].add_passive_cluster_event(ccl_ev)
    def fetch_boot_events(self, ard_tree):
        # fetch bootevents
        node_log_idx = ([key for key, value in self.__log_status.iteritems() if value["identifier"] == "node"] + [0])[0]
        user_log_idx = ([key for key, value in self.__log_status.iteritems() if value["identifier"] == "user"] + [0])[0]
        stime_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time() - ard_tree.time_frame["start"] * 60))
        etime_str = time.strftime("%Y-%m-%d 23:59:59", time.localtime(time.time() - ard_tree.time_frame["end"] * 60))
        if self.__dev_sel:
            sql_str = "SELECT dl.user, dl.log_source, UNIX_TIMESTAMP(dl.date) AS ts, dl.device, dl.text FROM devicelog dl " + \
                      " WHERE dl.user AND (dl.log_source=%d OR dl.log_source=%d) AND (dl.date > '%s' AND dl.date < '%s') AND (%s)" % (node_log_idx,
                                                                                                                                      user_log_idx,
                                                                                                                                      stime_str,
                                                                                                                                      etime_str,
                                                                                                                                      " OR ".join(["dl.device=%d" % (x) for x in self.__dev_sel]))
            
            self.__req.dc.execute(sql_str)
            for db_rec in self.__req.dc.fetchall():
                self.__dev_tree[self.__dev_name_lut[db_rec["device"]]].add_boot_event(db_rec, node_log_idx, user_log_idx)
    def _add_device(self, db_rec, is_dummy_device=False):
        if not is_dummy_device:
            if db_rec["cluster_device_group"]:
                self.__cdg_info = (db_rec["dg_name"], db_rec["name"])
            self.__dev_names.append(db_rec["name"])
            self.__dev_names.sort()
            if db_rec["dg_name"] not in self.__devg_names:
                self.__devg_names.append(db_rec["dg_name"])
                self.__devg_names.sort()
                self.__devg_tree[db_rec["dg_name"]] = []
            self.__devg_tree[db_rec["dg_name"]].append(db_rec["name"])
            self.__devg_tree[db_rec["dg_name"]].sort()
        self.__dev_tree[db_rec["name"]] = rrd_device(self.__req, db_rec)
        if is_dummy_device:
            self.__dev_tree[db_rec["name"]].is_dummy_device(True)
        if db_rec.has_key("rra_count"):
            self.__dev_tree[db_rec["name"]].num_rrd_data = db_rec["rra_count"]
        return self.__dev_tree[db_rec["name"]]
    def get_dev_names(self, dg_name=""):
        if dg_name:
            return self.__devg_tree[dg_name]
        else:
            return self.__dev_names
    def get_devg_names(self):
        return self.__devg_names
    def __getitem__(self, key):
        return self.__dev_tree[key]

class rrd_data_tree(object):
    def __init__(self, req, dev_tree):
        # request object
        self.__req = req
        self.low_submit = html_tools.checkbox(self.__req, "sub")
        self.__active_submit = self.low_submit.check_selection("")
        self.low_submit[""] = 1
        self._init_html_stuff()
        self.change_log = html_tools.message_log()
        # cluster event changes
        self.cluster_event_changes = 0
        # rrd_info re
        self.rrd_list = html_tools.selection_list(req, "rrds", {}, sort_new_keys=False, size=8, multiple=True)
        dev_names = dev_tree.get_dev_names()
        self.rrd_data_tree = {}
        # data tree to store settings like color and drawing flags
        self.settings_tree = {}
        # build data_tree
        self.descr_lut, self.descr_idx_lut, self.info_lut, self.re_ok = ({}, {}, {}, {})
        idx = 0
        for dev_name in dev_names:
            for descr, rrd_data in dev_tree[dev_name].rrd_tree.iteritems():
                if not self.rrd_data_tree.has_key(descr):
                    #if descr.startswith("load"):
                    #    print "New", descr
                    idx += 1
                    self.rrd_data_tree[descr] = {}
                    self.re_ok[descr] = True
                    self.descr_lut[descr] = idx
                    self.descr_idx_lut[idx] = descr
                    self.info_lut[descr] = rrd_data.get_info_str()
                self.rrd_data_tree[descr][dev_name] = rrd_data
        # sort keys, honor integer parts and meta-device parts
        all_descr_lut = dict([(tuple([y.isdigit() and int(y) or y for y in sum([x.split("_") for x in descr.split(".")], [])]), descr) for descr in self.rrd_data_tree.keys()])
        all_descrs = [all_descr_lut[x] for x in sorted(all_descr_lut.keys())]
        last_header = ""
        header_idx = 0
        for descr in all_descrs:
            act_rrd_data = self.rrd_data_tree[descr].values()[0]
            act_header = act_rrd_data.get_header_str()
            if act_header != last_header:
                last_header = act_header
                header_drawn = False
                header_idx -= 1
            act_info_str = self.info_lut[descr]
            if self.__act_re_string:
                # check for regular expression matching
                show = False
                for re_str in self.__act_re_regexps:
                    if re_str.match(act_info_str.lower()) or re_str.match(descr.lower()):
                        show = True
                self.re_ok[descr] = show
            if self.re_ok[descr]:
                if not header_drawn:
                    header_drawn = True
                    self.rrd_list["h%d" % (header_idx)] = {"name"     : "--- %s ---" % (last_header),
                                                           "disabled" : True,
                                                           "class"    : "inverse"}
                count = len(self.rrd_data_tree[descr].keys())
                self.rrd_list[descr] = {"name" : "%s%s%s" % (act_info_str,
                                                             count > 1 and " (%d devs)" % (count) or "",
                                                             act_rrd_data.from_snmp and " (SNMP)" or "")}
        self.act_sel = self.rrd_list.check_selection("", [])
        self.corrected_act_sel = [x for x in self.act_sel if self.rrd_data_tree.has_key(x)]
        # time frame
        self.time_frame_field = {"start" : html_tools.text_field(self.__req, "rrdtfs", size=12, display_len=8),
                                 "end"   : html_tools.text_field(self.__req, "rrdtfe", size=12, display_len=8)}
        self.time_frame = {"start" : self._check_time_frame(self.time_frame_field["start"].check_selection("", "06:00")),
                           "end"   : self._check_time_frame(self.time_frame_field["end"].check_selection("", "now"))}
        if self.time_frame["start"] == self.time_frame["end"]:
            self.time_frame["start"] = self.time_frame["end"] + 120
        if self.time_frame["start"] < self.time_frame["end"]:
            sw = self.time_frame["end"]
            self.time_frame["end"] = self.time_frame["start"]
            self.time_frame["start"] = sw
        self.time_frame_field["start"][""] = self._set_time_frame(self.time_frame["start"])
        self.time_frame_field["end"][""] = self._set_time_frame(self.time_frame["end"])
        # graph size
        self.graph_size_field = {"width"  : html_tools.text_field(self.__req, "rrdw", size=6, display_len=4),
                                 "height" : html_tools.text_field(self.__req, "rrdh", size=6, display_len=4)}
        self.graph_size = {"width"  : self._check_graph_size(self.graph_size_field["width"] , 600, 1920),
                           "height" : self._check_graph_size(self.graph_size_field["height"], 200, 1200)}
        self.graph_size_field["width"][""]  = "%d" % (self.graph_size["width"])
        self.graph_size_field["height"][""] = "%d" % (self.graph_size["height"])
        # show selection
        self.show_field = html_tools.selection_list(self.__req, "rrdevs", {0 : "---",
                                                                           1 : "graph config",
                                                                           2 : "graph config, event info",
                                                                           3 : "graph and event config"})
        self.act_show_setting = self.show_field.check_selection("", 0)
        self.configure_graph = self.act_show_setting > 0
        self.show_events = self.act_show_setting > 1
        self.configure_events = self.act_show_setting == 3
        self.cluster_event_vs = new_cluster_event_vs(self.__req)
        # various settings
        color_dict = {"xxxxxx" : "choose",
                      "000000" : "black",
                      "808080" : "grey",
                      "800000" : "maroon",
                      "ff0000" : "red",
                      "008000" : "green",
                      "00ff00" : "lime",
                      "808000" : "olive",
                      "ffff00" : "yellow",
                      "000080" : "navy",
                      "0000ff" : "blue",
                      "800080" : "purple",
                      "ff00ff" : "fuchsia",
                      "008080" : "tealk",
                      "00ffff" : "aqua",
                      "c0c0c0" : "silver",
                      "ffffff" : "white"}
        self.graph_settings = {"min"      : html_tools.checkbox(self.__req, "rrdmin"),
                               "average"  : html_tools.checkbox(self.__req, "rrdave"),
                               "max"      : html_tools.checkbox(self.__req, "rrdmax"),
                               "any"      : html_tools.checkbox(self.__req, "rrdany"),
                               "color"    : html_tools.text_field(self.__req, "rrdcol", size=6, display_len=6),
                               "colorsel" : html_tools.selection_list(self.__req, "rrdcsel", color_dict, initial_mode="n"),
                               "mode"     : html_tools.selection_list(self.__req, "rrdmode", {"LINE1"       : "LINE1",
                                                                                              "LINE2"       : "LINE2",
                                                                                              "LINE3"       : "LINE3",
                                                                                              "AREA"        : "AREA",
                                                                                              "AREAOUTLINE" : "AREAOUTLINE"}),
                               "pri"      : html_tools.text_field(self.__req, "rrdpri", size=6, display_len=4),
                               "shift"    : html_tools.text_field(self.__req, "rrdsh", size=32, display_len=16),
                               "invert"   : html_tools.checkbox(self.__req, "rrdinv"),
                               "smooth"   : html_tools.text_field(self.__req, "rrdsmo", size=8, display_len=6)}
        # true if key was also present in last pagecall
        self.was_on_list_dict = {}
        # check graph settings
        for act_sel in self.act_sel:
            # iterate until we got something different from sel and white
            def_color = "xxxxxx"
            while def_color in ["xxxxxx", "ffffff"]:
                def_color = color_dict.keys()[random.randint(1, len(color_dict.keys()) - 2)]
            if act_sel.split(".")[-1].count("_"):
                sel_splits = act_sel.split(".")
                sel_splits.append(sel_splits.pop(-1).split("_")[0])
                real_sel = ".".join(sel_splits)
                if self.__req.user_info.has_user_var("_rrd_%s" % (real_sel)) and not self.__req.user_info.has_user_var("_rrd_%s" % (act_sel)):
                    saved_setting = self.__req.user_info.get_user_var_value("_rrd_%s" % (real_sel), {})
                    # initialize value
                    self.__req.user_info.get_user_var_value("_rrd_%s" % (act_sel), {})
                else:
                    saved_setting = self.__req.user_info.get_user_var_value("_rrd_%s" % (act_sel), {})
            else:
                saved_setting = self.__req.user_info.get_user_var_value("_rrd_%s" % (act_sel), {})
            # correct wrong db_settings
            if saved_setting == "":
                saved_setting = {}
            self.was_on_list_dict[act_sel] = self.graph_settings["any"].check_selection(act_sel)
            self.graph_settings["any"][act_sel] = True
            # check min/average/max
            for d_mode in ["min", "average", "max"]:
                if self.was_on_list_dict[act_sel]:
                    saved_setting[d_mode] = self.graph_settings[d_mode].check_selection(act_sel)
                else:
                    saved_setting[d_mode] = self.graph_settings[d_mode].check_selection(act_sel, saved_setting.get(d_mode, False) and 1 or 0)
            if not saved_setting["max"] and not saved_setting["min"] and not saved_setting["average"]:
                saved_setting["average"] = True
                self.graph_settings["average"][act_sel] = True
            if self.was_on_list_dict[act_sel]:
                saved_setting["color"]  = self.graph_settings["color"].check_selection(act_sel)
                saved_setting["mode"]   = self.graph_settings["mode"].check_selection(act_sel, "LINE1")
                saved_setting["pri"]    = self.graph_settings["pri"].check_selection(act_sel, "0")
                saved_setting["shift"]  = self.graph_settings["shift"].check_selection(act_sel, "now")
                saved_setting["invert"] = self.graph_settings["invert"].check_selection(act_sel)
                saved_setting["smooth"] = self.graph_settings["smooth"].check_selection(act_sel, "0")
            else:
                saved_setting["color"]  = self.graph_settings["color"].check_selection(act_sel, saved_setting.get("color", def_color))
                saved_setting["mode"]   = self.graph_settings["mode"].check_selection(act_sel, saved_setting.get("mode", "LINE1"))
                saved_setting["pri"]    = self.graph_settings["pri"].check_selection(act_sel, str(saved_setting.get("pri", 1)))
                saved_setting["shift"]  = self.graph_settings["shift"].check_selection(act_sel, ",".join([self._set_time_frame(tf) for tf in saved_setting.get("shift", [0])]))
                saved_setting["invert"] = self.graph_settings["invert"].check_selection(act_sel, saved_setting.get("invert", False))
                saved_setting["smooth"] = self.graph_settings["smooth"].check_selection(act_sel, self._set_time_frame(saved_setting.get("smooth", 0), zero_string="none"))
            # check color
            spec_color_sel = self.graph_settings["colorsel"].check_selection(act_sel, "xxxxxx")
            self.graph_settings["colorsel"][act_sel] = "xxxxxx"
            if spec_color_sel != "xxxxxx":
                saved_setting["color"] = spec_color_sel
            if not re.match("^[0-9a-fA-F]{6}$", saved_setting["color"]):
                saved_setting["color"] = def_color
            self.graph_settings["color"][act_sel] = saved_setting["color"]
            # check pri
            if not saved_setting["pri"].isdigit():
                saved_setting["pri"] = "1"
            saved_setting["pri"] = int(saved_setting["pri"])
            self.graph_settings["pri"][act_sel] = str(saved_setting["pri"])
            # check shifting
            pure_shifts = [self._check_time_frame(act_shift) for act_shift in saved_setting["shift"].split(",")]
            pure_shifts.sort()
            new_shifts = [self._set_time_frame(pure_shift) for pure_shift in pure_shifts]
            saved_setting["shift"] = pure_shifts
            self.graph_settings["shift"][act_sel] = ",".join(new_shifts)
            # check smoothing
            pure_smooth = self._check_time_frame(saved_setting["smooth"], zero_string="none")
            saved_setting["smooth"] = pure_smooth
            self.graph_settings["smooth"][act_sel] = self._set_time_frame(pure_smooth, zero_string="none")
            self.__req.user_info.modify_user_var("_rrd_%s" % (act_sel), saved_setting)
            self.settings_tree[act_sel] = saved_setting
        # check event settings
        self._check_event_changes()
    def _check_event_changes(self):
        if self.show_events:
            # check for keys with only one device
            event_keys = [key for key in self.corrected_act_sel if self.get_num_devices(key) == 1]
            # rrd data idxs wht ccl_events
            rrd_data_dict = dict([(rd.idx, rd) for rd in [self.rrd_data_tree[ev_key].values()[0] for ev_key in event_keys]])
            if rrd_data_dict:
                sql_str = "SELECT * FROM ccl_event ce " + \
                        "LEFT JOIN ccl_dloc_con dl ON dl.ccl_event=ce.ccl_event_idx " + \
                        "LEFT JOIN ccl_dgroup_con dg ON dg.ccl_event=ce.ccl_event_idx " + \
                        "LEFT JOIN ccl_user_con du ON du.ccl_event=ce.ccl_event_idx WHERE (%s)" % (" OR ".join(["ce.rrd_data=%d" % (x) for x in rrd_data_dict.keys()]))
                self.__req.dc.execute(sql_str)
                for db_rec in self.__req.dc.fetchall():
                    rrd_data = rrd_data_dict[db_rec["rrd_data"]]
                    rrd_data._add_active_cluster_event(db_rec)
                for rrd_data in rrd_data_dict.values():
                    # call act_values_are default for events
                    rrd_data.fix_events()
            num_changes = 0
            for event_key in event_keys:
                dev_name = self.rrd_data_tree[event_key].keys()[0]
                rrd_data = self.rrd_data_tree[event_key][dev_name]
                rrd_data.link_ce_vs(self.cluster_event_vs)
                if self.configure_events:
                    num_changes += rrd_data._check_for_changes(self.change_log)
            self.cluster_event_changes = num_changes
            #print event_key, dev_name
    def get_rrd_options(self, sel_data):
        if type(sel_data) == type([]):
            # return dict for sel_data list
            return dict([(sel, dict([(k, v) for k, v in self.settings_tree[sel].iteritems()] + [("descr", self.get_info_str(sel))])) for sel in sel_data])
        else:
            # return only one dict
            return dict([(k, v) for k, v in self.settings_tree[sel_data].iteritems()] + [("descr", self.get_info_str(sel_data))])
    def get_rrd_compounds(self, sel_data):
        rrd_compounds = {"compound_list" : []}
        last_header = ""
        for descr in sel_data:
            act_header = self.rrd_data_tree[descr].values()[0].get_header_str()
            if act_header != last_header:
                rrd_compounds[act_header] = []
                rrd_compounds["compound_list"].append(act_header)
                last_header = act_header
            rrd_compounds[act_header].append(descr)
        return rrd_compounds
    def _check_graph_size(self, in_field, def_value, max_val):
        act_in_val = in_field.check_selection("", "%d" % (def_value))
        if act_in_val.isdigit():
            act_val = max(min(int(act_in_val), max_val), 100)
        else:
            act_val = def_value
        return act_val
    def get_time_frame_length(self):
        diff_time = abs(self.time_frame["start"] - self.time_frame["end"])
        return logging_tools.get_time_str(diff_time * 60)
    def _check_time_frame(self, time_frame_str, zero_string="now"):
        re_hour_min = re.compile("^(?P<hours>\d{1,3}):(?P<mins>\d{1,2})$")
        re_day_hour_min = re.compile("^(?P<days>\d{1,4}):(?P<hours>\d{1,2}):(?P<mins>\d{1,2})$")
        if time_frame_str == zero_string:
            time_frame = 0
        elif time_frame_str.isdigit():
            time_frame = int(time_frame_str)
        elif re_hour_min.match(time_frame_str):
            re_m = re_hour_min.match(time_frame_str)
            time_frame = 60 * int(re_m.group("hours")) + int(re_m.group("mins"))
        elif re_day_hour_min.match(time_frame_str):
            re_m = re_day_hour_min.match(time_frame_str)
            time_frame = 60 * (24 * int(re_m.group("days")) + int(re_m.group("hours"))) + int(re_m.group("mins"))
        else:
            time_frame = 0
        return time_frame
    def _set_time_frame(self, val, zero_string="now"):
        if val == 0:
            val_str = zero_string
        else:
            hours = int(val / 60)
            mins = val - 60 * hours
            days = int(hours / 24)
            hours -= 24 * days
            if days:
                val_str = "%d:%02d:%02d" % (days, hours, mins)
            else:
                val_str = "%d:%02d" % (hours, mins)
        return val_str
    def _init_html_stuff(self):
        self.rrd_info_re = html_tools.text_field(self.__req, "rrdire", size=128, display_len=10)
        self.layout_list = html_tools.selection_list(self.__req, "rrlayout", {0 : "dev (h) x rrd (w)",
                                                                              1 : "rrd (h) x dev (w)"})
        self.actual_layout = self.layout_list.check_selection("", 0)
        # regular expression string
        self.__act_re_string = self.rrd_info_re.check_selection("", "")
        self.__act_re_regexps = [re.compile(".*%s.*" % (re_str.strip())) for re_str in self.__act_re_string.lower().split(",")]
    def feed_lmma_result(self, r_dict):
        for dev_name, dev_stuff in r_dict.iteritems():
            for key, val_stuff in dev_stuff.iteritems():
                if self.rrd_data_tree.has_key(key):
                    if self.rrd_data_tree[key].has_key(dev_name):
                        self.rrd_data_tree[key][dev_name].set_lmma_result(val_stuff)
    def get_num_devices(self, key):
        return len(self.rrd_data_tree[key].keys())
    def get_device_name(self, key):
        return self.rrd_data_tree[key].keys()[0]
    def get_device_names(self, key):
        return self.rrd_data_tree[key].keys()
    def get_first_rrd_data(self, key):
        return self.rrd_data_tree[key].values()[0]
    def get_info_str(self, key):
        return self.info_lut[key]
    def get_lmma_stuff(self, dev_name, key, lmma_type):
        if self.rrd_data_tree[key].has_key(dev_name):
            return self.rrd_data_tree[key][dev_name].get_lmma_result(lmma_type)
        else:
            return "not set", "warncenter"

class new_rrd_class_vs(html_tools.validate_struct):
    def __init__(self, req):
        new_dict = {"name"      : {"he"  : html_tools.text_field(req, "rrdcname", size=63, display_len=22),
                                   "new" : True,
                                   "vf"  : self.validate_name,
                                   "def" : ""},
                    "step"      : {"he"  : html_tools.text_field(req, "rrdcstep", size=8, display_len=8),
                                   "vf"  : self.validate_step,
                                   "def" : "30"},
                    "heartbeat" : {"he"  : html_tools.text_field(req, "rrdchb", size=8, display_len=8),
                                   "vf"  : self.validate_heartbeat,
                                   "def" : "30"},
                    "del"       : {"he"  : html_tools.checkbox(req, "rrddel", auto_reset=1),
                                   "del" : 1}}
        html_tools.validate_struct.__init__(self, req, "RRD Class", new_dict)
    def validate_name(self):
        if self.new_val_dict["name"] in self.names:
            self.new_val_dict["name"] = self.old_val_dict["name"]
            raise ValueError, "already used"
    def validate_step(self):
        if not tools.is_number(self.new_val_dict["step"]):
            raise ValueError, "must be an integer"
        else:
            self.new_val_dict["step"] = int(self.new_val_dict["step"])
    def validate_heartbeat(self):
        if not tools.is_number(self.new_val_dict["heartbeat"]):
            raise ValueError, "must be an integer"
        else:
            self.new_val_dict["heartbeat"] = int(self.new_val_dict["heartbeat"])

class new_rrd_rra_vs(html_tools.validate_struct):
    def __init__(self, req, cf_list):
        new_dict = {"cf"    : {"he"  : cf_list,
                               "vf"  : self.validate_steps,
                               "def" : "AVERAGE"},
                    "steps" : {"he"  : html_tools.text_field(req, "rrasteps", size=8, display_len=8),
                               "vf"  : self.validate_steps,
                               "def" : "",
                               "new" : True},
                    "rows"  : {"he"  : html_tools.text_field(req, "rrarows", size=8, display_len=8),
                               "vf"  : self.validate_rows,
                               "def" : "2880"},
                    "xff"   : {"he"  : html_tools.text_field(req, "rrarxff", size=8, display_len=8),
                               "vf"  : self.validate_xff,
                               "def" : "0.5"},
                    "del"   : {"he"  : html_tools.checkbox(req, "rradel", auto_reset=1),
                               "del" : 1}}
        html_tools.validate_struct.__init__(self, req, "RRD rra", new_dict)
    def validate_steps(self):
        if not tools.is_number(self.new_val_dict["steps"]):
            raise ValueError, "must be an integer"
        else:
            self.new_val_dict["steps"] = int(self.new_val_dict["steps"])
    def validate_rows(self):
        if not tools.is_number(self.new_val_dict["rows"]):
            raise ValueError, "must be an integer"
        else:
            self.new_val_dict["rows"] = int(self.new_val_dict["rows"])
    def validate_xff(self):
        try:
            act_f = float(self.new_val_dict["xff"])
        except ValueError:
            raise ValueError, "must be a float"
        else:
            self.new_val_dict["xff"] = act_f

class rrd_class_tree(object):
    def __init__(self, req):
        self.__req = req
        self.__rrd_class_tree = {}
        self.html_class_list = html_tools.selection_list(req, "rrdc")
        self.html_save_button = html_tools.checkbox(req, "rrsb")
        self.html_global_save_list = html_tools.selection_list(req, "rrsbg", {0 : "--- keep ---",
                                                                              1 : "enable saving",
                                                                              2 : "disable saving"}, auto_reset=True)
        self.copy_from_list = html_tools.selection_list(req, "rrdccf", auto_reset=True, sort_new_keys=False)
        self.copy_from_list[0] = "<nowhere>"
        self.__cf_list = html_tools.selection_list(req, "rrdcf", {"AVERAGE" : "AVERAGE",
                                                                  "MAX"     : "MAX",
                                                                  "MIN"     : "MIN"})
        self.__cf_list.mode_is_normal()
        # validate structs
        self.__rrd_c_vs = new_rrd_class_vs(req)
        self.__rrd_r_vs = new_rrd_rra_vs(req, self.__cf_list)
        # fetch rrd_class tree
        req.dc.execute("SELECT c.*, r.* FROM rrd_class c LEFT JOIN rrd_rra r ON r.rrd_class=c.rrd_class_idx ORDER BY c.name")
        for db_rec in req.dc.fetchall():
            if not self.__rrd_class_tree.has_key(db_rec["rrd_class_idx"]):
                self._add_rrd_class(db_rec)
            self.__rrd_class_tree[db_rec["rrd_class_idx"]]._add_rrd_rra(db_rec)
        #ng_g_dict[0] = cdef_nagios.ng_contactgroup(ng_g_vs.get_default_value("name"), 0, ng_g_vs.get_default_dict())
        self._add_new_rrd_class()
        self.html_class_list.add_pe_key("glob", 0, "--- keep ---")
        self.html_class_list.mode_is_normal()
        #for field in [self.get_he("name")]:
        #    field.mode_is_normal()
    def fetch_use_count(self):
        self.__req.dc.execute("SELECT d.rrd_class, COUNT(d.rrd_class) AS count FROM device d, rrd_class r WHERE r.rrd_class_idx=d.rrd_class GROUP by d.rrd_class")
        for db_rec in self.__req.dc.fetchall():
            self.__rrd_class_tree[db_rec["rrd_class"]].count = db_rec["count"]
    def process_changes(self, change_log, sub_flag):
        rcv, rrv = (self.__rrd_c_vs,
                    self.__rrd_r_vs)
        rcv.set_submit_mode(sub_flag)
        # copy idx
        copy_from_idx = self.copy_from_list.check_selection("", 0)
        # rra_delete list
        rra_del_list = []
        for rrd_class_idx in self.__rrd_class_tree.keys():
            act_rrd_class = self.__rrd_class_tree[rrd_class_idx]
            rcv.names = [x["name"] for x in self.__rrd_class_tree.values() if x["name"] != act_rrd_class["name"]]
            rcv.link_object(rrd_class_idx, act_rrd_class)
            rcv.check_for_changes()
            if not rcv.check_delete():
                rcv.process_changes(change_log, self.__rrd_class_tree)
                if rcv.check_create():
                    if copy_from_idx:
                        act_rrd_class.copy_rrd_rras(self.__req, self.__rrd_class_tree[copy_from_idx])
                # add new_rra
                if act_rrd_class.idx:
                    act_rrd_class._add_new_rrd_rra(rrv.get_default_dict())
                #print self.__rrd_class_tree.keys()
                #    new_db_obj, old_db_obj = (rcv.get_db_obj(), rcv.get_old_db_obj())
                rrv.set_old_db_obj_idx(act_rrd_class.get_new_rra_suffix())
                for rra_idx in act_rrd_class.get_rra_idxs():
                    act_rra = act_rrd_class.get_rra(rra_idx)
                    rrv.link_object(rra_idx, act_rra)
                    rrv.check_for_changes()
                    if not rrv.check_delete():
                        rrv.process_changes(change_log, act_rrd_class.rra_tree)
                    else:
                        rra_del_list.append((act_rrd_class.idx, rra_idx))
                    rrv.unlink_object()
            rcv.unlink_object()
        if rra_del_list:
            for class_idx, rra_idx in rra_del_list:
                change_log.add_ok("Deleted rrd_rra from rrd_class '%s'" % (self[class_idx]["name"]), "SQL")
                self[class_idx].del_rrd_rra(rra_idx)
            self.__req.dc.execute("DELETE FROM rrd_rra WHERE %s" % (" OR ".join(["rrd_rra_idx=%d" % (idx) for rra_idx, idx in rra_del_list])))
        if rcv.get_delete_list():
            for del_class in rcv.get_delete_list():
                change_log.add_ok("Deleted rrd_class '%s'" % (self[del_class].name), "SQL")
                self._del_rrd_class(del_class)
    def _add_new_rrd_class(self):
        def_dict = self.__rrd_c_vs.get_default_dict()
        def_dict["rrd_class_idx"] = 0
        self._add_rrd_class(def_dict)
    def _del_rrd_class(self, idx, with_db = True):
        del self.__rrd_class_tree[idx]
        self.copy_from_list.del_setup_key(idx)
        if with_db:
            self.__req.dc.execute("DELETE FROM rrd_rra WHERE rrd_class=%d" % (idx))
            self.__req.dc.execute("DELETE FROM rrd_class WHERE rrd_class_idx=%d" % (idx))
    def _add_rrd_class(self, db_rec):
        if db_rec["rrd_class_idx"]:
            self.html_class_list[db_rec["rrd_class_idx"]] = db_rec["name"]
        if db_rec["name"]:
            self.copy_from_list[db_rec["rrd_class_idx"]] = db_rec["name"]
        new_rrd_class = cdef_rrd.rrd_class(db_rec["rrd_class_idx"], db_rec)
        new_rrd_class.act_values_are_default()
        self.__rrd_class_tree[new_rrd_class.idx] = new_rrd_class
    def get_display_names(self):
        valid_dict = dict([(x["name"], x.idx) for x in self.__rrd_class_tree.values() if x.idx])
        valid_dict[""] = 0
        self.__lookup_dict = valid_dict
        valid_names = valid_dict.keys()
        valid_names.remove("")
        valid_names.sort()
        valid_names.append("")
        return valid_names
    def __getitem__(self, key):
        if type(key) == type(""):
            return self.__rrd_class_tree[self.__lookup_dict[key]]
        else:
            return self.__rrd_class_tree[key]
    def get_class_he(self, key):
        return self.__rrd_c_vs.get_he(key)
    def get_rra_he(self, key):
        return self.__rrd_r_vs.get_he(key)

def overview_mode(req, act_rrd_tree, act_rrd_class_tree, option):
    class_list = act_rrd_class_tree.html_class_list
    save_button = act_rrd_class_tree.html_save_button
    global_save_setting = act_rrd_class_tree.html_global_save_list.check_selection("glob", 0)
    global_class = act_rrd_class_tree.html_class_list.check_selection("glob", 0)
    act_rrd_class_tree.html_class_list["glob"] = 0
    low_submit = html_tools.checkbox(req, "subg")
    sub = low_submit.check_selection("")
    submit_button = html_tools.submit_button(req, "submit")
    act_rrd_tree.fetch_cluster_events(7)
    scon_logs = html_tools.message_log()
    # dev names
    if option == "o0":
        dev_names = [d_name for d_name in act_rrd_tree.get_dev_names() if act_rrd_tree[d_name].save_vectors]
    else:
        dev_names = [d_name for d_name in act_rrd_tree.get_dev_names()]
    # check for new device_idxs
    dev_changes = []
    for dev_name in dev_names:
        act_dev = act_rrd_tree[dev_name]
        dev_changes.extend(act_dev.link_html_items(class_list, (save_button, global_save_setting), sub, scon_logs))
    ds_command = tools.s_command(req, "rrd_server_collector", 8003, "device_status", dev_names, 10)
    all_commands = [ds_command]
    if dev_changes:
        all_commands.append(tools.s_command(req, "rrd_server_collector", 8003, "check_device_settings", dev_changes, 10))
    tools.iterate_s_commands(all_commands, scon_logs)
    if ds_command.server_reply:
        node_dicts = ds_command.server_reply.get_node_dicts()
        for node_name, node_res in ds_command.server_reply.get_node_results().iteritems():
            act_rrd_tree[node_name].set_rrd_server_status(node_res, node_dicts)
    req.write(html_tools.gen_hline("Overview about %s in %s (%s)" % (logging_tools.get_plural("device", len(act_rrd_tree.get_dev_names())),
                                                                     logging_tools.get_plural("device group", len(dev_names)),
                                                                     logging_tools.get_plural("rrd class", len(act_rrd_class_tree.get_display_names()))),
                                   2))
    sel_table = html_tools.html_table(cls="normal")
    line1_idx = 0
    tot_size = 0
    devs_shown = 0
    cdg_info = act_rrd_tree.get_cdg_info() or ("", "")
    first_dev_group = False
    for show_cdg_group in [True, False]:
        for dg_name in act_rrd_tree.get_devg_names():
            if (show_cdg_group and dg_name == cdg_info[0]) or (not show_cdg_group and dg_name != cdg_info[0]):
                line1_idx = 1 - line1_idx
                dg_dev_names = [name for name in act_rrd_tree.get_dev_names(dg_name) if name in dev_names]
                if dg_dev_names:
                    if len(dg_dev_names) > 1 or first_dev_group:
                        dev_group_shown = True
                        sel_table[0]["class"] = "line01"#%d" % (line1_idx)
                        sel_table[None][0:7] = html_tools.content("devicegroup %s, %s: %s" % (dg_name,
                                                                                              logging_tools.get_plural("device", len(dg_dev_names)),
                                                                                              logging_tools.compress_list(dg_dev_names)), type="th", cls="center")
                        sel_table[0]["class"] = "line00"#%d" % (line1_idx)
                        for hn in ["Name", "Type", "RRD info", "last update", "write", "rrd class", "size"]:
                            sel_table[None][0] = html_tools.content(hn, cls="center")
                    else:
                        dev_group_shown = False
                    first_dev_group = False
                    line2_idx = 0
                    group_size = 0
                    for dev_name in dg_dev_names:
                        devs_shown += 1
                        line2_idx = 1 - line2_idx
                        act_dev = act_rrd_tree[dev_name]
                        dev_stat, stat_str = act_dev.get_rrd_server_status()
                        if dev_stat == "ok":
                            dev_stat = "line1%d" % (line2_idx)
                        sel_table[0]["class"] = dev_stat
                        sel_table[None][0] = html_tools.content("<a href=\"%s.py?%s&dm=d3&dev[]=%d\">%s</a>" % (req.module_name,
                                                                                                                functions.get_sid(req),
                                                                                                                act_dev.idx,
                                                                                                                act_dev.get_name()), cls="left")
                        sel_table[None][0] = html_tools.content(act_dev.description, cls="center")
                        sel_table[None][0] = html_tools.content(act_dev.get_rrd_info_str(), cls="left")
                        sel_table[None][0] = html_tools.content(stat_str, cls="left")
                        sel_table[None][0] = html_tools.content(save_button, act_dev.suffix, cls="center")
                        sel_table[None][0] = html_tools.content(class_list, act_dev.suffix, cls="center")
                        try:
                            act_class = act_rrd_class_tree[act_dev.rrd_class_idx]
                        except KeyError:
                            sel_table[None][0] = html_tools.content("<invalid class>", cls="errorcenter")
                        else:
                            loc_size = act_class.get_size(act_dev.num_rrd_data)
                            tot_size += loc_size
                            group_size += loc_size
                            sel_table[None][0] = html_tools.content(logging_tools.get_size_str(loc_size, True), cls="right")
                    if group_size and len(dg_dev_names) > 1:
                        sel_table[0]["class"] = "line00"
                        sel_table[None][0:7] = html_tools.content("Size needed for rrd-data for devicegroup %s: %s" % (dg_name,
                                                                                                                       logging_tools.get_size_str(group_size, True)), cls="right")
    if tot_size:
        sel_table[0]["class"] = "line00"
        sel_table[None][0:7] = html_tools.content("Total size needed for rrd-data on system: %s" % (logging_tools.get_size_str(tot_size, True)), cls="right")
    if devs_shown > 1:
        sel_table[0]["class"] = "line00"
        sel_table[None][0:4] = html_tools.content("Global settings:", cls="right")
        sel_table[None][0] = html_tools.content(act_rrd_class_tree.html_global_save_list, "glob", cls="center")
        sel_table[None][0] = html_tools.content(class_list, "glob", cls="center")
        sel_table[None][0] = html_tools.content("&nbsp;", cls="center")
    low_submit[""] = 1
    req.write(sel_table())
    req.write("%s<div class=\"center\">%s</div>\n" % (low_submit.create_hidden_var(),
                                                      submit_button()))

def rrd_class_mode(req, act_rrd_tree, act_rrd_class_tree):
    act_rrd_class_tree.fetch_use_count()
    submit_button = html_tools.submit_button(req, "submit")
    low_submit = html_tools.checkbox(req, "sub")
    sub = low_submit.check_selection("")
    change_log = html_tools.message_log()
    act_rrd_class_tree.process_changes(change_log, sub)
    req.write(change_log.generate_stack("Action log"))
    req.write(html_tools.gen_hline("Overview about %s" % (logging_tools.get_plural("rrd class", len(act_rrd_class_tree.get_display_names()))),
                                   2))
    sel_table = html_tools.html_table(cls="normal")
    sel_table[0]["class"] = "line10"
    sel_table[None][0] = html_tools.content("&nbsp;", type="th", cls="min")
    for what in ["Name", "#RRAs", "del/#", "step", "heartbeat"]:
        sel_table[None][0] = html_tools.content(what, type="th")
    line1_idx = 0
    for class_name in act_rrd_class_tree.get_display_names():
        line1_idx = 1 - line1_idx
        sel_table[0]["class"] = "line0%d" % (line1_idx)
        act_class = act_rrd_class_tree[class_name]
        if class_name:
            sel_table[None][0:2] = html_tools.content(act_rrd_class_tree.get_class_he("name"), cls="left")
            sel_table[None][0] = html_tools.content("%d" % (len(act_class.rra_tree.keys()) - 1), cls="center")
            if act_class.count:
                sel_table[None][0] = html_tools.content("%d" % (act_class.count), cls="center")
            else:
                sel_table[None][0] = html_tools.content(act_rrd_class_tree.get_class_he("del"), cls="errormin")
        else:
            sel_table[None][0:4] = html_tools.content(["New: ",
                                                       act_rrd_class_tree.get_class_he("name"),
                                                       ", copy rrd_rras from ",
                                                       act_rrd_class_tree.copy_from_list()], cls="left")
        sel_table[None][0] = html_tools.content(act_rrd_class_tree.get_class_he("step"), cls="center")
        sel_table[None][0] = html_tools.content(act_rrd_class_tree.get_class_he("heartbeat"), cls="center")
        sub_table = html_tools.html_table(cls="blind")
        rra_idxs = act_class.get_rra_idxs()
        if rra_idxs:
            sub_table[0]["class"] = "line10"
            for what in ["del", "CF function", "pdp length", "steps", "total length", "rows", "xff", "size needed"]:
                sub_table[None][0] = html_tools.content(what, type="th")
            line2_idx = 0
            for rra_idx in rra_idxs:
                act_rra = act_class.get_rra(rra_idx)
                rra_suf = act_rra.get_suffix()
                line2_idx = 1 - line2_idx
                sub_table[0]["class"] = "line1%d" % (line2_idx)
                if act_rra.idx:
                    sub_table[None][0] = html_tools.content(act_rrd_class_tree.get_rra_he("del"), rra_suf, cls="errormin")
                    sub_table[None][0] = html_tools.content(act_rrd_class_tree.get_rra_he("cf"), rra_suf, cls="center")
                else:
                    sub_table[None][0:2] = html_tools.content(["New:",
                                                               act_rrd_class_tree.get_rra_he("cf")], rra_suf, cls="center")
                sub_table[None][0] = html_tools.content(act_rra.get_pdp_length(), rra_suf, cls="right")
                sub_table[None][0] = html_tools.content(act_rrd_class_tree.get_rra_he("steps"), rra_suf, cls="left")
                sub_table[None][0] = html_tools.content(act_rra.get_total_length(), rra_suf, cls="right")
                sub_table[None][0] = html_tools.content(act_rrd_class_tree.get_rra_he("rows"), rra_suf, cls="left")
                sub_table[None][0] = html_tools.content(act_rrd_class_tree.get_rra_he("xff"), rra_suf, cls="center")
                if act_rra.idx:
                    sub_table[None][0] = html_tools.content(logging_tools.get_size_str(act_rra.get_size(), True), cls="center")
                else:
                    sub_table[None][0] = html_tools.content("&nbsp;", cls="center")
            sel_table[0]["class"] = "line0%d" % (line1_idx)
            sel_table[None][0] = html_tools.content("&nbsp;", cls="min")
            sel_table[None][2:6] = sub_table
            sel_table[0]["class"] = "line0%d" % (line1_idx)
            sel_table[None][0:6] = html_tools.content("Size needed per dataset (approximately): %s" % (logging_tools.get_size_str(act_class.get_size(), True)), cls="let")
        req.write(sel_table.flush_lines(act_class.get_suffix()))
    req.write(sel_table())
    low_submit[""] = 1
    req.write("<div class=\"center\">%s%s</div>\n" % (low_submit.create_hidden_var(),
                                                      submit_button()))

def pre_init_data_tree(req, act_rrd_tree, act_rrd_class_tree):
    act_rrd_data_tree = rrd_data_tree(req, act_rrd_tree)
    return act_rrd_data_tree
    
def matrix_mode(req, act_rrd_tree, act_rrd_class_tree, act_rrd_data_tree):
    submit_button = html_tools.submit_button(req, "submit")
    #act_rrd_data_tree = rrd_data_tree(req, act_rrd_tree, rrd_info_re.check_selection("", ""))
    change_log = html_tools.message_log()
    sel_data = act_rrd_data_tree.corrected_act_sel
    if sel_data:
        ds_command = tools.s_command(req, "rrd_server_grapher", 8017, "report_lmma", act_rrd_tree.get_dev_names(), 30, add_dict={"rrds"       : sel_data,
                                                                                                                                 "start_time" : act_rrd_data_tree.time_frame["start"],
                                                                                                                                 "end_time"   : act_rrd_data_tree.time_frame["end"]})
        tools.iterate_s_commands([ds_command], change_log)
        if ds_command.server_reply:
            if ds_command.get_state() == "o":
                act_rrd_data_tree.feed_lmma_result(ds_command.server_reply.get_node_dicts())
        req.write(change_log.generate_stack("Action log", show_only_errors=True, show_only_warnings=True))
        lmma_types = ["last", "min", "average", "max"]
        lmma_table = html_tools.html_table(cls="normal")
        req.write(html_tools.gen_hline("Last / Max / Min / Average Matrix (time frame: %s)" % (act_rrd_data_tree.get_time_frame_length()), 2))
        if act_rrd_data_tree.actual_layout:
            lmma_table[0]["class"] = "line00"
            lmma_table[None][0] = html_tools.content("Info", type="th", cls="center")
            lmma_table[None][0] = html_tools.content("type", type="th", cls="center")
            for dev_name in act_rrd_tree.get_dev_names():
                act_dev = act_rrd_tree[dev_name]
                lmma_table[None][0] = html_tools.content(act_dev.get_name(), type="th", cls="center")
            line1_idx = 0
            for key in act_rrd_data_tree.corrected_act_sel:
                line1_idx = 1 - line1_idx
                lmma_table[0]["class"] = "line1%d" % (line1_idx)
                lmma_table[None:4][0] = html_tools.content(act_rrd_data_tree.get_info_str(key))
                for lmma_type in lmma_types:
                    if lmma_type != "last":
                        lmma_table[0]["class"] = "line1%d" % (line1_idx)
                    lmma_table[None][2] = html_tools.content(lmma_type, cls="center")
                    for dev_name in act_rrd_tree.get_dev_names():
                        td_str, td_type = act_rrd_data_tree.get_lmma_stuff(dev_name, key, lmma_type)
                        lmma_table[None][0] = html_tools.content(td_str, cls=td_type)
        else:
            lmma_table[0]["class"] = "line00"
            lmma_table[None:2][0] = html_tools.content("device", type="th", cls="center")
            for key in act_rrd_data_tree.corrected_act_sel:
                lmma_table[None][0:4] = html_tools.content(act_rrd_data_tree.get_info_str(key), type="th", cls="center")
            lmma_table[0]["class"] = "line00"
            lmma_table.set_cursor(2, 1)
            for key in act_rrd_data_tree.corrected_act_sel:
                for lmma_type in lmma_types:
                    lmma_table[None][0] = html_tools.content(lmma_type, cls="center")
            line1_idx = 0
            for dev_name in act_rrd_tree.get_dev_names():
                act_dev = act_rrd_tree[dev_name]
                line1_idx = 1 - line1_idx
                lmma_table[0]["class"] = "line1%d" % (line1_idx)
                lmma_table[None][0] = html_tools.content(act_dev.get_name(), cls="left")
                for key in act_rrd_data_tree.corrected_act_sel:
                    for lmma_type in lmma_types:
                        td_str, td_type = act_rrd_data_tree.get_lmma_stuff(dev_name, key, lmma_type)
                        lmma_table[None][0] = html_tools.content(td_str, cls=td_type)
        req.write(lmma_table())
    else:
        req.write(html_tools.gen_hline("No rrd_data selected", 2))
    #req.write("".join([act_rrd_data_tree.rrd_list()]))
    req.write("%s<div class=\"center\">%s</div>\n" % (act_rrd_data_tree.low_submit.create_hidden_var(),
                                                      submit_button()))

def graphing_mode(req, act_rrd_tree, act_rrd_class_tree, act_rrd_data_tree):
    act_rrd_tree.fetch_boot_events(act_rrd_data_tree)
    if act_rrd_data_tree.show_events:
        act_rrd_tree.fetch_cluster_events(act_rrd_data_tree)
    submit_button = html_tools.submit_button(req, "submit")
    change_log = act_rrd_data_tree.change_log
    sel_data = act_rrd_data_tree.corrected_act_sel
    if sel_data:
        rrd_compounds = act_rrd_data_tree.get_rrd_compounds(sel_data)
        ds_command = tools.s_command(req, "rrd_server_grapher", 8017, "draw_graphs", act_rrd_tree.get_dev_names(), 60, add_dict={"rrds"           : sel_data,
                                                                                                                                 "rrd_options"    : act_rrd_data_tree.get_rrd_options(sel_data),
                                                                                                                                 "rrd_compounds"  : rrd_compounds,
                                                                                                                                 "start_time"     : act_rrd_data_tree.time_frame["start"],
                                                                                                                                 "end_time"       : act_rrd_data_tree.time_frame["end"],
                                                                                                                                 "width"          : act_rrd_data_tree.graph_size["width"],
                                                                                                                                 "height"         : act_rrd_data_tree.graph_size["height"],
                                                                                                                                 "device_options" : dict([(dev_name, act_rrd_tree[dev_name].get_device_options(rrd_compounds, act_rrd_data_tree, sel_data)) for dev_name in act_rrd_tree.get_dev_names()])})
        rrd_com_list = [ds_command]
        if act_rrd_data_tree.cluster_event_changes:
            rrd_com_list.append(tools.s_command(req, "rrd_server_collector", 8003, "reload_cluster_events", []))
        tools.iterate_s_commands(rrd_com_list, change_log)
        if ds_command.server_reply:
            graph_matrix = ds_command.server_reply.get_option_dict()
        else:
            graph_matrix = {}
            #print opt_dict.keys(), [x.keys() for x in opt_dict.values()]
        if act_rrd_data_tree.cluster_event_changes:
            req.write(change_log.generate_stack("Action log"))#, show_only_errors=True, show_only_warnings=True))
        else:
            req.write(change_log.generate_stack("Action log", show_only_errors=True, show_only_warnings=True))
        if act_rrd_data_tree.configure_graph:
            info_table = html_tools.html_table(cls="normal")
            last_header = ""
            line1_idx = 0
            for key in act_rrd_data_tree.corrected_act_sel:
                act_header = act_rrd_data_tree.rrd_data_tree[key].values()[0].get_header_str()
                if act_header != last_header:
                    last_header = act_header 
                    info_table[0]["class"] = "line00"
                    info_table[None][0:10] = html_tools.content(act_header, type="th", cls="center")
                line1_idx = 1 - line1_idx
                info_table[0]["class"] = "line1%d" % (line1_idx)
                num_devs = act_rrd_data_tree.get_num_devices(key)
                info_table[None][0] = html_tools.content([act_rrd_data_tree.get_info_str(key),
                                                          act_rrd_data_tree.graph_settings["any"].create_hidden_var(key),
                                                          num_devs > 1 and " (%s)" % (logging_tools.get_plural("device", num_devs)) or ""])
                for d_mode in ["min", "average", "max"]:
                    info_table[None][0] = html_tools.content(["%s: " % (d_mode),
                                                              act_rrd_data_tree.graph_settings[d_mode]], key, cls="center")
                info_table[None][0] = html_tools.content(["color ", act_rrd_data_tree.graph_settings["color"],
                                                          " or ", act_rrd_data_tree.graph_settings["colorsel"]], key, cls="center")
                info_table[None][0] = html_tools.content(["mode "     , act_rrd_data_tree.graph_settings["mode"]], key, cls="center")
                info_table[None][0] = html_tools.content(["priority " , act_rrd_data_tree.graph_settings["pri"]], key, cls="center")
                info_table[None][0] = html_tools.content(["invert "   , act_rrd_data_tree.graph_settings["invert"]], key, cls="center")
                info_table[None][0] = html_tools.content(["smoothing ", act_rrd_data_tree.graph_settings["smooth"]], key, cls="center")
                info_table[None][0] = html_tools.content(["shifting " , act_rrd_data_tree.graph_settings["shift"]], key, cls="center")
                if act_rrd_data_tree.show_events:
                    act_rrd_data = act_rrd_data_tree.get_first_rrd_data(key)
                    if num_devs > 1 or not act_rrd_data_tree.configure_events:
                        event_table = act_rrd_data.get_event_info_table(act_rrd_tree, act_rrd_data_tree.get_device_names(key))
                    else:
                        event_table = act_rrd_data.get_event_table(act_rrd_tree, act_rrd_data_tree.get_device_names(key))
                    info_table[0]["class"] = "line10"
                    info_table[None][0:10] = event_table
            req.write(info_table())
        if graph_matrix:
            act_g_idx = 0
            graph_file_base = "/".join(os.path.dirname(req.environ["SCRIPT_FILENAME"]).split("/")[:-1] + ["graphs"])
            graph_table = html_tools.html_table(cls="normalsmall")
            if act_rrd_data_tree.actual_layout:
                graph_table[0]["class"] = "white"
                graph_table[None][0] = html_tools.content("&nbsp;", cls="left")
                for dev_name in act_rrd_tree.get_dev_names():
                    act_dev = act_rrd_tree[dev_name]
                    graph_table[None][0] = html_tools.content(act_dev.get_name(), type="th", cls="center")
                for c_name in rrd_compounds["compound_list"]:
                    graph_table[0]["class"] = "white"
                    graph_table[None][0] = html_tools.content(c_name, cls="left")
                    for dev_name in act_rrd_tree.get_dev_names():
                        act_g_idx += 1
                        act_g_name = "%s_%d.png" % (functions.get_sid(req), act_g_idx)
                        if graph_matrix.has_key(c_name) and graph_matrix[c_name].has_key(dev_name):
                            if graph_matrix[c_name][dev_name].startswith("error"):
                                graph_table[None][0] = html_tools.content(graph_matrix[c_name][dev_name], cls="center")
                            else:
                                file("%s/%s" % (graph_file_base, act_g_name), "w").write(graph_matrix[c_name][dev_name])
                                graph_table[None][0] = html_tools.content("<img src=\"../graphs/%s\"/>" % (act_g_name), cls="topcenter")
                        else:
                            graph_table[None][0] = html_tools.content("no graph", cls="center")
            else:
                graph_table[0]["class"] = "white"
                graph_table[None][0] = html_tools.content("&nbsp;", cls="left")
                for c_name in rrd_compounds["compound_list"]:
                    graph_table[None][0] = html_tools.content(c_name, type="th", cls="center")
                for dev_name in act_rrd_tree.get_dev_names():
                    act_dev = act_rrd_tree[dev_name]
                    graph_table[0]["class"] = "white"
                    graph_table[None][0] = html_tools.content(act_dev.get_name(), cls="left")
                    for c_name in rrd_compounds["compound_list"]:
                        act_g_idx += 1
                        act_g_name = "%s_%d.png" % (functions.get_sid(req), act_g_idx)
                        if graph_matrix.has_key(c_name) and graph_matrix[c_name].has_key(dev_name):
                            if graph_matrix[c_name][dev_name].startswith("error"):
                                graph_table[None][0] = html_tools.content(graph_matrix[c_name][dev_name], cls="center")
                            else:
                                file("%s/%s" % (graph_file_base, act_g_name), "w").write(graph_matrix[c_name][dev_name])
                                graph_table[None][0] = html_tools.content("<img src=\"../graphs/%s\"/>" % (act_g_name), cls="topcenter")
                        else:
                            graph_table[None][0] = html_tools.content("no graph", cls="center")
            req.write("%s%s" % (html_tools.gen_hline("Graph matrix", 2),
                                graph_table("")))
        else:
            req.write(html_tools.gen_hline("Empty graph-matrix", 2))
    else:
        req.write(html_tools.gen_hline("No rrd_data selected", 2))
    #req.write("".join([act_rrd_data_tree.rrd_list()]))
    req.write("%s<div class=\"center\">%s</div>\n" % (act_rrd_data_tree.low_submit.create_hidden_var(),
                                                      submit_button()))

def process_page(req):
    if req.conf["genstuff"].has_key("AUTO_RELOAD"):
        del req.conf["genstuff"]["AUTO_RELOAD"]
    functions.write_header(req)
    functions.write_body(req)
    if req.conf["server"].has_key("rrd_server_collector"):
        dev_tree = tools.display_list(req, with_meta_devices=True)
        dev_tree.add_regexp_field()
        dev_tree.add_devsel_fields(tools.get_device_selection_lists(req.dc, req.user_info.get_idx()))
        # FIXME
        dev_tree.query([],
                       ["comment"],
                       [],
                       [],
                       ["device d2 ON d2.device_idx=dg.device"])
        # display mode
        disp_mode_list = html_tools.selection_list(req, "dm", {"d0" : "Overview",
                                                               "d1" : "RRD classes",
                                                               "d2" : "Data Matrix",
                                                               "d3" : "Graphing"})
        # options for overview
        ov_options_list = html_tools.selection_list(req, "ool", {"o0" : "only with write-flag",
                                                                 "o1" : "everything"})
        act_rrd_class_tree = rrd_class_tree(req)
        # sort mode
        disp_mode = disp_mode_list.check_selection("", "d0")
        # draw_mode, unifies upper and lower part
        rrd_draw_mode = disp_mode in ["d2", "d3"]
        if not dev_tree.devices_found():
            req.write(html_tools.gen_hline("No devices with rrd-data found", 2))
        else:
            dg_sel, d_sel, dg_sel_eff = dev_tree.get_selection()
            ds_dict = dev_tree.get_device_selection_lists()
            act_rrd_tree = rrd_tree(req, d_sel)
            if rrd_draw_mode:
                act_rrd_tree.add_detailed_rra_info()
                act_rrd_data_tree = pre_init_data_tree(req, act_rrd_tree, act_rrd_class_tree)
            sel_table = html_tools.html_table(cls="blindsmall")
            sel_table[0][0] = html_tools.content(dev_tree, "devg", cls="center")
            sel_table[None][0] = html_tools.content(dev_tree, "dev", cls="center")
            col_span = 2
            if ds_dict:
                sel_table[None][0] = html_tools.content(dev_tree, "sel", cls="center")
                col_span += 1
            if rrd_draw_mode:
                sel_table[None][0] = html_tools.content(act_rrd_data_tree.rrd_list(), "sel", cls="center")
                col_span += 1
                dev_tree.size = act_rrd_data_tree.rrd_list.get_option("size")
            select_button = html_tools.submit_button(req, "select")
            submit_button = html_tools.submit_button(req, "submit")
            sel_table[0][0:col_span] = html_tools.content(["Regexp for Groups ", dev_tree.get_devg_re_field(),
                                                           " and devices ", dev_tree.get_dev_re_field(),
                                                           "\n, ", dev_tree.get_devsel_action_field(), " selection",
                                                           dev_tree.get_devsel_field()], cls="center")
            bottom_line = ["Mode: ", disp_mode_list]
            if rrd_draw_mode:
                bottom_line.extend([", RRD data regexp: ",
                                    act_rrd_data_tree.rrd_info_re,
                                    ", layout: ",
                                    act_rrd_data_tree.layout_list,
                                    ", from ",
                                    act_rrd_data_tree.time_frame_field["start"],
                                    " to ",
                                    act_rrd_data_tree.time_frame_field["end"]])
                if disp_mode == "d3":
                    bottom_line.extend([", ",
                                        act_rrd_data_tree.graph_size_field["width"],
                                        " x ",
                                        act_rrd_data_tree.graph_size_field["height"],
                                        ", show ",
                                        act_rrd_data_tree.show_field])
            elif disp_mode in ["d0"]:
                ov_option = ov_options_list.check_selection("", "o0")
                bottom_line.extend([", ",
                                    ov_options_list])
            bottom_line.extend([", ", rrd_draw_mode and submit_button or select_button])
            sel_table[0][0:col_span] = html_tools.content(bottom_line, cls="center")
            req.write("<form action=\"%s.py?%s\" method = post>%s" % (req.module_name,
                                                                      functions.get_sid(req),
                                                                      sel_table()))
            if not rrd_draw_mode:
                req.write("</form><form action=\"%s.py?%s\" method = post>%s%s" % (req.module_name,
                                                                                   functions.get_sid(req),
                                                                                   disp_mode_list.create_hidden_var(),
                                                                                   dev_tree.get_hidden_sel()))
            if disp_mode == "d0":
                overview_mode(req, act_rrd_tree, act_rrd_class_tree, ov_option)
                req.write(ov_options_list.create_hidden_var(""))
            elif disp_mode == "d1":
                rrd_class_mode(req, act_rrd_tree, act_rrd_class_tree)
            elif disp_mode == "d2":
                matrix_mode(req, act_rrd_tree, act_rrd_class_tree, act_rrd_data_tree)
            elif disp_mode == "d3":
                graphing_mode(req, act_rrd_tree, act_rrd_class_tree, act_rrd_data_tree)
            req.write("</form>")
    else:
        req.write(html_tools.gen_hline("No rrd-server collector defined", 2))
        
