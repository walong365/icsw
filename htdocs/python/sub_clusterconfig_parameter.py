#!/usr/bin/python -Ot
# -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2001,2002,2003,2004,2005,2007,2008 Andreas Lang-Nevyjel, init.at
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
""" device parameters and stuff """

import logging_tools
import html_tools
import tools
import crypt
import random
import cdef_device
import time
import datetime

def get_time_str(sec):
    return "%s" % (logging_tools.get_plural("second", sec))

class device_variable_vs(html_tools.validate_struct):
    def __init__(self, req):
        html_tools.validate_struct.__init__(self, req, "device_variable",
                                            {"name"                : {"he"  : html_tools.text_field(req, "dvn",  size=64, display_len=30),
                                                                      "new" : 1,
                                                                      "vf"  : self.validate_name,
                                                                      "def" : ""},
                                             "description"         : {"he"  : html_tools.text_field(req, "dvc",  size=64, display_len=30),
                                                                      "def" : ""},
                                             "value"               : {"he"  : html_tools.text_field(req, "dvv",  size=255,  display_len=30),
                                                                      "vf"  : self.validate_value,
                                                                      "def" : ""},
                                             "del"                 : {"he"  : html_tools.checkbox(req, "dvd", auto_reset=1),
                                                                      "del" : 1},
                                             "device"              : {"ndb" : 1,
                                                                      "def" : 0},
                                             "is_public"           : {"def" : 1},
                                             "device_variable_idx" : {"ndb" : 1,
                                                                      "def" : 0},
                                             "var_type"            : {"def" : ""}})
        self.set_map_function(self.map_func)
    def set_act_type(self, in_type):
        self.__act_type = in_type
        self.__long_act_type = {"s" : "str",
                                "i" : "int",
                                "b" : "blob",
                                "t" : "time",
                                "d" : "date"}[self.__act_type]
    def map_func(self, key):
        if key == "value":
            return "val_%s" % (self.__long_act_type)
        else:
            return key
    def validate_name(self):
        if self.is_new_object():
            # some dirty stuff because of the different device_variabel_types
            self.copy_instance_args = self.__act_type
            self.get_db_obj().set_type(self.__act_type)
        if self.new_val_dict["name"] in self.names and self.new_val_dict["name"] != self.old_val_dict["name"]:
            self.new_val_dict["name"] = self.old_val_dict["name"]
            raise ValueError, "already used"
        elif not self.new_val_dict["name"]:
            self.new_val_dict["name"] = self.old_val_dict["name"]
            raise ValueError, "must not be empty"
    def validate_value(self):
        if self.__act_type == "s":
            pass
        elif self.__act_type == "i":
            if tools.is_number(self.new_val_dict["value"].strip()):
                self.new_val_dict["value"] = int(self.new_val_dict["value"].strip())
            else:
                raise ValueError, "not an integer"
        elif self.__act_type == "d":
            try:
                act_date = time.strptime(self.new_val_dict["value"], "%Y-%m-%d %H:%M:%S")
            except ValueError:
                act_date = time.localtime()
            else:
                pass
            self.new_val_dict["value"] = datetime.datetime(*act_date[0:6])
        elif self.__act_type == "t":
            num_p = ([0, 0] + [int(y) for y in [x.strip() for x in self.new_val_dict["value"].split(":")]])[-3:]
            if len(num_p) != 3:
                raise ValueError, "Cannot parse value"
            for count, max_val in zip(num_p, [0, 60, 60]):
                if max_val and count >= max_val:
                    raise ValueError, "Cannot parse value (%d >= %d)" % (count, max_val)
            seconds = 3600 * num_p[0] + 60 * num_p[1] + num_p[2]
            days = seconds / (3600 * 24)
            seconds -= days * (3600 * 24)
            self.new_val_dict["value"] = datetime.timedelta(days, seconds)
        return

def show_device_parameters(req, dev_tree, sub_sel):
    low_submit = html_tools.checkbox(req, "sub")
    sub = low_submit.check_selection("")
    dg_sel, d_sel, dg_sel_eff = dev_tree.get_selection()
    change_log = html_tools.message_log()
    dev_dict = {}
    req.dc.execute("SELECT val_str FROM device_variable WHERE name='md_type'")
    if req.dc.rowcount:
        md_type = req.dc.fetchone()["val_str"]
    else:
        md_type = "icinga"
    if sub_sel == "a":
        snmp_dict = tools.get_snmp_class_dict(req.dc)
        loc_dict  = tools.get_device_location_dict(req.dc)
        class_dict = tools.get_device_class_dict(req.dc)
        snmp_dict[0]  = {"name"      : "not set"}
        loc_dict[0]   = {"location"  : "not set"}
        class_dict[0] = {"classname" : "not set"}
        snmp_list = html_tools.selection_list(req, "sn", {})
        for snmp_idx, stuff in snmp_dict.iteritems():
            snmp_list[snmp_idx] = "%s (r/o: %s, r/w: %s, version: %d)" % (stuff["name"],
                                                                          stuff.get("read_community", "not set"),
                                                                          "*" * len(stuff.get("write_community", "not set")),
                                                                          stuff.get("snmp_version", 0))
        snmp_list.add_pe_key("g", -1, "keep")
        loc_list = html_tools.selection_list(req, "loc", {}, sort_new_keys=0)
        for loc_idx, stuff in loc_dict.iteritems():
            loc_list[loc_idx] = stuff["location"]
        loc_list.add_pe_key("g", 0, "keep")
        class_list = html_tools.selection_list(req, "cl", {})
        for class_idx, stuff in class_dict.iteritems():
            class_list[class_idx] = stuff["classname"]
        class_list.add_pe_key("g", 0, "keep")
        snmp_list.mode_is_normal()
        loc_list.mode_is_normal()
        class_list.mode_is_normal()
        req.dc.execute("SELECT d.device_idx, d.device_location, d.name, d.snmp_class, d.device_class, d.device_group, d.device_type FROM device d WHERE (%s)" % (" OR ".join(["d.device_idx=%d" % (x) for x in d_sel])))
        for db_rec in req.dc.fetchall():
            new_dev = cdef_device.device(db_rec["name"], db_rec["device_idx"], db_rec["device_group"], db_rec["device_type"])
            for what in ["snmp_class", "device_class", "device_location"]:
                new_dev[what] = db_rec[what]
            dev_dict[db_rec["device_idx"]] = new_dev
        # check for global changes
        glob_snmp = snmp_list.check_selection("g", -1)
        snmp_list["g"] = -1

        glob_loc  = loc_list.check_selection("g", 0)
        loc_list["g"] = 0

        glob_class = class_list.check_selection("g", 0)
        class_list["g"] = 0

    elif sub_sel == "d":
        dv_type_list = html_tools.selection_list(req, "dvt", {"s" : "String",
                                                              "i" : "Integer",
                                                              "b" : "Blob",
                                                              "d" : "Date",
                                                              "t" : "Time"})
        dv_vs = device_variable_vs(req)
        req.dc.execute("SELECT d.device_idx, d.name, d.device_group, d.device_type, dv.* FROM device d LEFT JOIN device_variable dv ON dv.device=d.device_idx WHERE (%s)" % (" OR ".join(["d.device_idx=%d" % (x) for x in d_sel])))
        for db_rec in req.dc.fetchall():
            if not dev_dict.has_key(db_rec["device_idx"]):
                new_dev = cdef_device.device(db_rec["name"], db_rec["device_idx"], db_rec["device_group"], db_rec["device_type"])
                dev_dict[db_rec["device_idx"]] = new_dev
            if db_rec["device_variable_idx"]:
                db_rec["name"] = db_rec["dv.name"]
                new_dev.add_device_variable(db_rec)
        dv_del_list = []
    elif sub_sel == "r":
        # device relationship
        rel_ship_list = html_tools.selection_list(req, "drs", {"n"   : "---",
                                                               "xen" : "xen guest"})
        req.dc.execute("SELECT d.device_idx, d.ng_ext_host, d.device_group, d.device_type, d.name, r.host_device, r.relationship FROM device d LEFT JOIN device_relationship r ON d.device_idx=r.domain_device WHERE (%s)" % (" OR ".join(["d.device_idx=%d" % (x) for x in d_sel])))
        for db_rec in req.dc.fetchall():
            new_dev = cdef_device.device(db_rec["name"], db_rec["device_idx"], db_rec["device_group"], db_rec["device_type"])
            dev_dict[db_rec["device_idx"]] = new_dev
            new_dev.relationship = (db_rec["host_device"], db_rec["relationship"])
        # get all devices
        req.dc.execute("SELECT d.name, d.device_idx, dg.name AS dg_name FROM device d, device_group dg, device_type dt WHERE d.device_group=dg.device_group_idx AND d.device_type=dt.device_type_idx AND dt.identifier='H' ORDER BY d.name")
        host_list = html_tools.selection_list(req, "hl", {0 : "---"}, sort_new_keys=False)
        for db_rec in req.dc.fetchall():
            host_list[db_rec["device_idx"]] = "%s (%s)" % (db_rec["name"],
                                                           db_rec["dg_name"])
        rel_ship_list.mode_is_normal()
        host_list.mode_is_normal()
    elif sub_sel == "p":
        # fetch apc and ibc info
        apc_dict, ibc_dict = (tools.ordered_dict(),
                              tools.ordered_dict())
        # apc part
        req.dc.execute("SELECT d.name, d.device_idx, d.device_group, d.device_type, m.* FROM device_type dt, device d LEFT JOIN msoutlet m ON m.device=d.device_idx WHERE d.device_type=dt.device_type_idx AND dt.identifier='AM' ORDER BY d.name, m.outlet")
        apc_ibc_sel_list = html_tools.selection_list(req, "na", {0 : "-- None ---"}, sort_new_keys=0)
        for db_rec in req.dc.fetchall():
            apc_idx = db_rec["device_idx"]
            if not apc_dict.has_key(apc_idx):
                new_apc = cdef_device.apc(db_rec["name"], apc_idx, db_rec["device_group"], db_rec["device_type"])
                apc_dict[apc_idx] = new_apc
                apc_ibc_sel_list[apc_idx] = "APC %s" % (db_rec["name"])
            if db_rec["outlet"]:
                apc_dict[apc_idx].add_outlet(db_rec["outlet"], db_rec)
        # ibc part
        req.dc.execute("SELECT d.name, d.device_idx, d.device_group, d.device_type, i.* FROM device_type dt, device d LEFT JOIN ibc_connection i ON i.device=d.device_idx WHERE d.device_type=dt.device_type_idx AND dt.identifier='IBC' ORDER BY d.name, i.blade")
        for db_rec in req.dc.fetchall():
            ibc_idx = db_rec["device_idx"]
            if not ibc_dict.has_key(ibc_idx):
                new_ibc = cdef_device.ibc(db_rec["name"], ibc_idx, db_rec["device_group"], db_rec["device_type"])
                ibc_dict[ibc_idx] = new_ibc
                apc_ibc_sel_list[ibc_idx] = "IBC %s" % (db_rec["name"])
            if db_rec["blade"]:
                ibc_dict[ibc_idx].add_blade(db_rec["blade"], db_rec)
        # get max num of outlets
        max_num_outlets = 8
        for act_apc in apc_dict.itervalues():
            if act_apc.get_outlet_nums():
                # max([]) raises an error
                max_num_outlets = max(max_num_outlets, max(act_apc.get_outlet_nums()))
        for act_ibc in ibc_dict.itervalues():
            if act_ibc.get_blade_nums():
                max_num_outlets = max(max_num_outlets, max(act_ibc.get_blade_nums()))
        outlet_sel_list = html_tools.selection_list(req, "no", {}, sort_new_keys=0)
        for i in range(1, max_num_outlets + 1):
            outlet_sel_list[i] = "%d" % (i)
        # fetch device info (with apc-connectivity)
        req.dc.execute("SELECT d.device_idx, d.device_location, d.name, d.name AS slave_name, d.snmp_class, d.device_class, d.device_group, d.device_type, ms.slave_device, ms.device, ms.outlet, ms.state, ms.slave_info FROM device d LEFT JOIN msoutlet ms ON ms.slave_device=d.device_idx")
        for db_rec in req.dc.fetchall():
            dev_idx = db_rec["device_idx"]
            if not dev_dict.has_key(dev_idx) and dev_idx in d_sel:
                new_dev = cdef_device.device(db_rec["name"], dev_idx, db_rec["device_group"], db_rec["device_type"])
                dev_dict[dev_idx] = new_dev
            if db_rec["slave_device"]:
                if dev_idx in d_sel:
                    dev_dict[dev_idx].add_apc_connection(db_rec["device"], db_rec["outlet"], db_rec["state"], db_rec["slave_info"])
                apc_dict[db_rec["device"]].set_device(db_rec["outlet"], db_rec["slave_device"], db_rec["slave_name"], db_rec["slave_info"])
        # fetch device info (with ibc-connectivity)
        req.dc.execute("SELECT d.device_idx, d.device_location, d.name, d.name AS slave_name, d.snmp_class, d.device_class, d.device_group, d.device_type, i.slave_device, i.device, i.blade, i.state, i.slave_info FROM device d LEFT JOIN ibc_connection i ON i.slave_device=d.device_idx")
        for db_rec in req.dc.fetchall():
            dev_idx = db_rec["device_idx"]
            if not dev_dict.has_key(dev_idx) and dev_idx in d_sel:
                new_dev = cdef_device.device(db_rec["name"], dev_idx, db_rec["device_group"], db_rec["device_type"])
                dev_dict[dev_idx] = new_dev
            if db_rec["slave_device"]:
                if dev_idx in d_sel:
                    dev_dict[dev_idx].add_ibc_connection(db_rec["device"], db_rec["blade"], db_rec["state"], db_rec["slave_info"])
                ibc_dict[db_rec["device"]].set_device(db_rec["blade"], db_rec["slave_device"], db_rec["slave_name"], db_rec["slave_info"])
        apc_ibc_info_field = html_tools.text_field(req, "ai", size=64, display_len=16)
        apc_ibc_ignore_connected = html_tools.checkbox(req, "apic", auto_reset=True)
        apc_ibc_clear_connections = html_tools.checkbox(req, "apccon", auto_reset=True)
        outlet_sel_list.mode_is_normal()
        apc_ibc_sel_list.mode_is_normal()
        apc_change_dict, ibc_change_dict = ({}, {})
        glob_apc, glob_outlet, apc_ibc_ignore, clear_connected = (int(apc_ibc_sel_list.check_selection("g", 0)),
                                                                  int(outlet_sel_list.check_selection("g", 0)),
                                                                  apc_ibc_ignore_connected.check_selection("g", 0),
                                                                  apc_ibc_clear_connections.check_selection("g", 0))
    elif sub_sel == "n":
        ng_monitor_check = html_tools.selection_list(req, "nmc", {0 : "keep",
                                                                  1 : "enable",
                                                                  2 : "disable"}, auto_reset=1, sort_new_keys=True)
        ng_ext_host_rb = html_tools.radio_list(req, "ehr", {0 : "keep"}, auto_reset=True, sort_new_keys=False)
        ng_ext_host = html_tools.selection_list(req, "eh", {0 : "none"}, sort_new_keys=False)
        ng_ext_host.add_pe_key("g", -1, "keep")
        # get ng_ext_host_usage
        req.dc.execute("SELECT ng_ext_host, COUNT(1) AS count FROM device GROUP BY ng_ext_host")
        ng_ext_host_usage_dict = dict([(db_rec["ng_ext_host"], db_rec["count"]) for db_rec in req.dc.fetchall()])
        ng_ext_hosts = tools.get_nagios_ext_hosts(req.dc)
        # at first add these with usage_count != 0
        for used in [True, False]:
            for ng_idx, ng_stuff in ng_ext_hosts.iteritems():
                is_used = ng_idx in ng_ext_host_usage_dict.keys()
                if is_used == used:
                    ng_ext_host[ng_idx] = "%s%s" % (ng_stuff["name"],
                                                    "" if not used else " (%d)" % (ng_ext_host_usage_dict[ng_idx]))
                if used:
                    # radiobuttons
                    ng_ext_host_rb[ng_idx] = ng_stuff["name"]
        ng_dev_templs = tools.get_nagios_device_templates(req.dc)
        ng_dev_templ = html_tools.selection_list(req, "dt", {}, sort_new_keys=0)
        ng_dev_templ.add_pe_key("g", -1, "keep")
        ng_dev_templ[0] = "--- not set ---"
        for ng_idx, ng_stuff in ng_dev_templs.iteritems():
            ng_dev_templ[ng_idx] = ng_stuff["name"]
        ng_fetch_partinfo = html_tools.checkbox(req, "fpi", auto_reset=True)
        ng_dev_check = html_tools.checkbox(req, "dc")
        req.dc.execute("SELECT d.device_idx, d.ng_ext_host, d.nagios_checks, d.ng_device_templ, d.device_group, d.device_type, d.name FROM device d WHERE (%s)" % (" OR ".join(["d.device_idx=%d" % (x) for x in d_sel])))
        for db_rec in req.dc.fetchall():
            new_dev = cdef_device.device(db_rec["name"], db_rec["device_idx"], db_rec["device_group"], db_rec["device_type"])
            for what in ["ng_ext_host", "ng_device_templ", "nagios_checks"]:
                new_dev[what] = db_rec[what]
            dev_dict[db_rec["device_idx"]] = new_dev
        ng_dev_templ.mode_is_normal()
        ng_ext_host.mode_is_normal()
        ng_monitor_check.mode_is_normal()
        glob_ng_ext_host = ng_ext_host_rb.check_selection("g", 0)
        glob_ng_dev_templ = ng_dev_templ.check_selection("g", -1)
        glob_mon_check = ng_monitor_check.check_selection("g", 0)
    elif sub_sel == "s":
        root_password = html_tools.text_field(req, "rp", is_password=1)
        req.dc.execute("SELECT d.device_idx, d.root_passwd, d.device_group, d.device_type, d.name FROM device d WHERE (%s)" % (" OR ".join(["d.device_idx=%d" % (x) for x in d_sel])))
        for db_rec in req.dc.fetchall():
            new_dev = cdef_device.device(db_rec["name"], db_rec["device_idx"], db_rec["device_group"], db_rec["device_type"])
            dev_dict[db_rec["device_idx"]] = new_dev
            new_dev["root_passwd"] = db_rec["root_passwd"]
        glob_root_passwd = root_password.check_selection("g", "")
        root_password["g"] = ""
        real_glob_root_passwd = glob_root_passwd.strip()
    else:
        change_log.add_error("Unknown subtype '%s'" % (sub_sel), "config")
    nagios_change = False
    fetch_partitioninfo_list = []
    idx_list = []
    for dg in dg_sel_eff:
        idx_list.extend(dev_tree.get_sorted_effective_dev_idx_list(dg))
    for d_idx in [x for x in idx_list if dev_dict.has_key(x)]:
        d_stuff = dev_dict[d_idx]
        sf = d_stuff.get_suffix()
        if sub_sel == "a":
            act_snmp = d_stuff["snmp_class"]
            new_snmp = snmp_list.check_selection(sf, act_snmp)
            if new_snmp == act_snmp and glob_snmp != -1:
                new_snmp = glob_snmp
            if act_snmp != new_snmp:
                d_stuff.add_sql_changes({"snmp_class" : new_snmp})
                change_log.add_ok("Changed snmp_class of device '%s' to '%s'" % (d_stuff.get_name(), snmp_dict[new_snmp]["name"]), "ok")
                snmp_list[sf] = new_snmp
            act_loc = d_stuff["device_location"]
            new_loc = loc_list.check_selection(sf, act_loc)
            if new_loc == act_loc and glob_loc:
                new_loc = glob_loc
            if act_loc != new_loc:
                d_stuff.add_sql_changes({"device_location" : new_loc})
                change_log.add_ok("Changed location of device '%s' to '%s'" % (d_stuff.get_name(), loc_dict[new_loc]["location"]), "ok")
                loc_list[sf] = new_loc
            act_class = d_stuff["device_class"]
            new_class = class_list.check_selection(sf, act_class)
            if new_class == act_class and glob_class:
                new_class = glob_class
            if act_class != new_class:
                d_stuff.add_sql_changes({"device_class" : new_class})
                change_log.add_ok("Changed class of device '%s' to '%s'" % (d_stuff.get_name(), class_dict[new_class]["classname"]), "ok")
                class_list[sf] = new_class
            d_stuff.commit_sql_changes(req.dc)
        elif sub_sel == "d":
            dv_vs.set_default_value("var_type", dv_type_list.check_selection(d_stuff.get_new_device_variable_suffix(), "s"))
            d_stuff.add_device_variable(dv_vs.get_default_dict())
            for var_idx in d_stuff.variables.keys():
                v_stuff = d_stuff.variables[var_idx]
                if not var_idx:
                    # FIXME, revert to setup mode
                    v_stuff.is_init_mode(True)
                    v_stuff["val_%s" % (v_stuff.get_long_type())] = ""
                    v_stuff.act_values_are_default()
                dv_vs.set_old_db_obj_idx(d_stuff.get_new_device_variable_suffix())
                dv_vs.set_act_type(v_stuff.get_type())
                dv_vs.link_object(var_idx, v_stuff, d_stuff.get_idx())
                dv_vs.set_new_object_fields({"device" : d_stuff.get_idx()})
                dv_vs.names = [v["name"] for v in d_stuff.variables.values() if v["name"] and v["name"] != v_stuff["name"]]
                dv_vs.check_for_changes()
                if dv_vs.check_delete():
                    dv_del_list.append((d_idx, var_idx))
                else:
                    dv_vs.process_changes(change_log, d_stuff.variables)
                dv_vs.unlink_object()
        elif sub_sel == "r":
            # previous sets
            prev_host, prev_rel = d_stuff.relationship
            act_rel = rel_ship_list.check_selection(sf, prev_rel or "n")
            act_host = host_list.check_selection(sf, prev_host or 0)
            # target sets
            t_rel, t_host = (act_rel, act_host)
            if act_rel != "n" and act_host == d_idx:
                change_log.add_warn("%s cannot be guest on itself" % (d_stuff.get_name()), "internal")
                t_rel, t_host = ("n", 0)
            else:
                if act_rel == "n":
                    t_host = 0
                elif t_host == 0:
                    t_rel = "n"
            if t_host:
                if t_rel == prev_rel and t_host == prev_host:
                    # same
                    pass
                else:
                    if prev_rel:
                        # remove previous relationship
                        change_log.add_ok("removing %s as %s" % (d_stuff.get_name(),
                                                                 rel_ship_list.list_dict[prev_rel]["name"]),
                                          "SQL")
                        req.dc.execute("DELETE FROM device_relationship WHERE domain_device=%s", (d_idx))
                    change_log.add_ok("%s is now a %s on host %s" % (d_stuff.get_name(),
                                                                     rel_ship_list.list_dict[t_rel]["name"],
                                                                     host_list.list_dict[t_host]["name"]),
                                      "SQL")
                    req.dc.execute("INSERT INTO device_relationship SET host_device=%s, domain_device=%s, relationship=%s", (t_host,
                                                                                                                             d_idx,
                                                                                                                             t_rel))
                    nagios_change = True
            else:
                if prev_host:
                    change_log.add_ok("removing %s as %s" % (d_stuff.get_name(),
                                                             rel_ship_list.list_dict[prev_rel]["name"]),
                                      "SQL")
                    req.dc.execute("DELETE FROM device_relationship WHERE domain_device=%s", (d_idx))
                    nagios_change = True
            rel_ship_list[sf] = t_rel
            host_list[sf] = t_host
        elif sub_sel == "n":
            act_ng_ext_host = d_stuff["ng_ext_host"]
            # check if image is still valid
            if act_ng_ext_host not in ng_ext_hosts.keys():
                act_ng_ext_host = 0
            new_ng_ext_host = ng_ext_host.check_selection(sf, act_ng_ext_host)
            ng_ext_host_change = False
            # use default value
            if new_ng_ext_host == act_ng_ext_host and glob_ng_ext_host:
                new_ng_ext_host = glob_ng_ext_host
                ng_ext_host[sf] = new_ng_ext_host
                ng_ext_host_change = True
            elif new_ng_ext_host != act_ng_ext_host:
                ng_ext_host_change = True
            if ng_ext_host_change:
                nagios_change = True
                d_stuff.add_sql_changes({"ng_ext_host" : new_ng_ext_host})
                d_stuff["ng_ext_host"] = new_ng_ext_host
                change_log.add_ok("Change Nagios picture of device '%s' to '%s'" % (d_stuff.get_name(), ng_ext_hosts[new_ng_ext_host]["name"]), "ok")
            act_ng_dev_templ = d_stuff["ng_device_templ"]
            new_ng_dev_templ = ng_dev_templ.check_selection(sf, act_ng_dev_templ)
            
            if new_ng_dev_templ == act_ng_dev_templ and glob_ng_dev_templ >= 0:
                new_ng_dev_templ = glob_ng_dev_templ
                ng_dev_templ[sf] = new_ng_dev_templ
            if act_ng_dev_templ != new_ng_dev_templ:
                nagios_change = True
                d_stuff.add_sql_changes({"ng_device_templ" : new_ng_dev_templ})
                if new_ng_dev_templ:
                    change_log.add_ok("Change Nagios device_template for device '%s' to '%s'" % (d_stuff.get_name(), ng_dev_templs[new_ng_dev_templ]["name"]), "ok")
                else:
                    change_log.add_ok("Clearing Nagios device_template for device '%s'" % (d_stuff.get_name()), "ok")
            new_ng_check = ng_dev_check.check_selection(sf, default=not sub and d_stuff["nagios_checks"])
            if glob_mon_check:
                if glob_mon_check == 1:
                    new_ng_check = True
                else:
                    new_ng_check = False
            ng_dev_check[sf] = new_ng_check
            if new_ng_check != d_stuff["nagios_checks"]:
                nagios_change = True
                d_stuff.add_sql_changes({"nagios_checks" : new_ng_check and 1 or 0})
            d_stuff.commit_sql_changes(req.dc)
            fetch_pi = ng_fetch_partinfo.check_selection(sf)
            if fetch_pi:
                fetch_partitioninfo_list.append(d_stuff.get_name())
            ng_ext_host["g"] = 0
            ng_dev_templ["g"] = -1
        elif sub_sel == "p":
            new_ai_con, new_ai_port, new_info = (apc_ibc_sel_list.check_selection(sf, 0),
                                                 outlet_sel_list.check_selection(sf, 0),
                                                 apc_ibc_info_field.check_selection(sf, ""))
            if clear_connected:
                old_apc_cons = [x for x in d_stuff.apc_cons]
                for apc_idx, outlet, state, info in old_apc_cons:
                    change_log.add_ok("Removing device %s from outlet %d on APC %s (info '%s')" % (d_stuff.get_name(), outlet, apc_dict[apc_idx].get_name(), info), "OK")
                    d_stuff.remove_apc_connection(apc_idx, outlet)
                    apc_dict[apc_idx].remove_device(outlet)
                    apc_change_dict.setdefault(apc_idx, {})[outlet] = (0, "")
                old_ibc_cons = [x for x in d_stuff.apc_cons]
                for ibc_idx, blade, state, info in old_ibc_cons:
                    change_log.add_ok("Removing device %s from blade %d on IBC %s (info '%s')" % (d_stuff.get_name(), blade, ibc_dict[ibc_idx].get_name(), info), "OK")
                    d_stuff.remove_ibc_connection(ibc_idx, outlet)
                    ibc_dict[ibc_idx].remove_blade(blade)
                    ibc_change_dict.setdefault(ibc_idx, {})[blade] = (0, "")
            else:
                if new_ai_con and new_ai_port:
                    if apc_dict.has_key(new_ai_con):
                        ai_stuff = apc_dict[new_ai_con]
                        if ai_stuff.valid_apc():
                            apc_ibc_sel_list[sf] = 0
                            # check if we remove the outlet from another device
                            outlet_info = ai_stuff.outlets[new_ai_port]
                            old_dev = outlet_info["device"]
                            add_it = True
                            if old_dev == d_idx:
                                # same device
                                change_log.add_warn("Outlet %d on APC %s already occupied by %s" % (new_ai_port, ai_stuff.get_name(), d_stuff.get_name()), "used")
                                add_it = False
                            elif old_dev:
                                change_log.add_warn("Removing device %s from outlet %d on APC %s" % (outlet_info["name"], new_ai_port, ai_stuff.get_name()), "used")
                                if old_dev in d_sel:
                                    dev_dict[old_dev].remove_apc_connection(new_ai_con, new_ai_port)
                                ai_stuff.remove_device(new_ai_port)
                                apc_change_dict.setdefault(new_ai_con, {})[new_ai_port] = (0, "")
                            if add_it:
                                change_log.add_ok("Added outlet %d on APC %s to device %s (info '%s')" % (new_ai_port, ai_stuff.get_name(), d_stuff.get_name(), new_info), "OK")
                                d_stuff.add_apc_connection(new_ai_con, new_ai_port, "unknown", new_info)
                                ai_stuff.set_device(new_ai_port, d_idx, d_stuff.get_name(), new_info)
                                apc_change_dict.setdefault(new_ai_con, {})[new_ai_port] = (d_idx, new_info)
                        else:
                            change_log.add_warn("Cannot add outlet %d on APC %s to device %s (info '%s')" % (new_ai_port, ai_stuff.get_name(), d_stuff.get_name(), new_info), "not valid")
                    else:
                        ibc_stuff = ibc_dict[new_ai_con]
                        if ibc_stuff.valid_ibc():
                            apc_ibc_sel_list[sf] = 0
                            # check if we remove the outlet from another device
                            blade_info = ibc_stuff.blades[new_ai_port]
                            old_dev = blade_info["device"]
                            add_it = True
                            if old_dev == d_idx:
                                # same device
                                change_log.add_warn("Blade %d on IBC %s already occupied by %s" % (new_ai_port, ibc_stuff.get_name(), d_stuff.get_name()), "used")
                                add_it = False
                            elif old_dev:
                                change_log.add_warn("Removing device %s from outlet %d on IBC %s" % (blade_info["name"], new_ai_port, ibc_stuff.get_name()), "used")
                                if old_dev in d_sel:
                                    dev_dict[old_dev].remove_ibc_connection(new_ai_con, new_ai_port)
                                ibc_stuff.remove_device(new_ai_port)
                                ibc_change_dict.setdefault(new_ai_con, {})[new_ai_port] = (0, "")
                            if add_it:
                                change_log.add_ok("Added outlet %d on IBC %s to device %s (info '%s')" % (new_ai_port, ibc_stuff.get_name(), d_stuff.get_name(), new_info), "OK")
                                d_stuff.add_ibc_connection(new_ai_con, new_ai_port, "unknown", new_info)
                                ibc_stuff.set_device(new_ai_port, d_idx, d_stuff.get_name(), new_info)
                                ibc_change_dict.setdefault(new_ai_con, {})[new_ai_port] = (d_idx, new_info)
                        else:
                            change_log.add_warn("Cannot add blade %d on IBC %s to device %s (info '%s')" % (new_ai_port, ibc_stuff.get_name(), d_stuff.get_name(), new_info), "not valid")
                for old_ai_idx, old_port_num, state, info in [x for x in d_stuff.apc_cons] + [x for x in d_stuff.ibc_cons]:
                    if apc_dict.has_key(old_ai_idx):
                        old_ph_type = "apc"
                    else:
                        old_ph_type = "ibc"
                    act_suffix = d_stuff.get_outlet_suffix(old_ai_idx, old_port_num)
                    new_ai_con, new_ai_port, new_info = (int(apc_ibc_sel_list.check_selection(act_suffix, old_ai_idx)),
                                                         int(outlet_sel_list.check_selection(act_suffix, old_port_num)),
                                                         apc_ibc_info_field.check_selection(act_suffix, info))
                    if new_ai_con != old_ai_idx or new_ai_port != old_port_num or new_info != info:
                        if new_ai_con == 0:
                            if apc_dict.has_key(old_ai_idx):
                                # delete apc connection
                                change_log.add_ok("Removing device %s from outlet %d on APC %s (info '%s')" % (d_stuff.get_name(), old_port_num, apc_dict[old_ai_idx].get_name(), info), "OK")
                                d_stuff.remove_apc_connection(old_ai_idx, old_port_num)
                                apc_dict[old_ai_idx].remove_device(old_port_num)
                                apc_change_dict.setdefault(old_ai_idx, {})[old_port_num] = (0, "")
                            else:
                                change_log.add_ok("Removing device %s from blade %d on IBC %s (info '%s')" % (d_stuff.get_name(), old_port_num, ibc_dict[old_ai_idx].get_name(), info), "OK")
                                d_stuff.remove_ibc_connection(old_ai_idx, old_port_num)
                                ibc_dict[old_ai_idx].remove_device(old_port_num)
                                ibc_change_dict.setdefault(old_ai_idx, {})[old_port_num] = (0, "")
                        else:
                            change_it = True
                            if apc_dict.has_key(new_ai_con):
                                apc_stuff = apc_dict[new_ai_con]
                                outlet_struct = apc_stuff.outlets[new_ai_port]
                                old_dev = outlet_struct["device"]
                                new_ph_type = "apc"
                            else:
                                ibc_stuff = ibc_dict[new_ai_con]
                                blade_struct = ibc_stuff.blades[new_ai_port]
                                old_dev = blade_struct["device"]
                                new_ph_type = "ibc"
                            if new_ai_con != old_ai_idx or new_ai_port != old_port_num:
                                if old_dev == d_idx:
                                    if new_ph_type == "apc":
                                        change_log.add_warn("Outlet %d on APC %s already occupied by %s" % (new_ai_port, apc_stuff.get_name(), d_stuff.get_name()), "used")
                                    else:
                                        change_log.add_warn("Blade %d on IBC %s already occupied by %s" % (new_ai_port, apc_stuff.get_name(), d_stuff.get_name()), "used")
                                    change_it = False
                                    new_ai_con, new_ai_port = (old_ai_idx, old_port_num)
                                elif old_dev:
                                    if new_ph_type == "apc":
                                        change_log.add_warn("Removing device %s from outlet %d on APC %s" % (outlet_struct["name"], new_ai_port, apc_stuff.get_name()), "used")
                                        if old_dev in d_sel:
                                            dev_dict[old_dev].remove_apc_connection(new_ai_con, new_ai_port)
                                        apc_stuff.remove_device(new_ai_port)
                                        apc_change_dict.setdefault(new_ai_con, {})[new_ai_port] = (0, "")
                                    else:
                                        change_log.add_warn("Removing device %s from blade %d on IBC %s" % (outlet_struct["name"], new_ai_port, apc_stuff.get_name()), "used")
                                        if old_dev in d_sel:
                                            dev_dict[old_dev].remove_ibc_connection(new_ai_con, new_ai_port)
                                        ibc_stuff.remove_device(new_ai_port)
                                        ibc_change_dict.setdefault(new_ai_con, {})[new_ai_port] = (0, "")
                            if change_it:
                                if new_ai_con != old_ai_idx or new_ai_port != old_port_num:
                                    if new_ph_type == "apc":
                                        apc_stuff.remove_device(old_port_num)
                                        apc_change_dict.setdefault(old_ai_idx, {})[old_port_num] = (0, "")
                                        d_stuff.remove_apc_connection(old_ai_idx, old_port_num)
                                        change_log.add_ok("Moved device %s from outlet %d on APC %s to outlet %d on APC %s, setting info to '%s'" % (d_stuff.get_name(), old_port_num, apc_dict[old_ai_idx].get_name(), new_ai_port, apc_stuff.get_name(), new_info), "OK")
                                        d_stuff.add_apc_connection(new_ai_con, new_ai_port, "unknown", new_info)
                                        apc_stuff.set_device(new_ai_port, d_idx, d_stuff.get_name(), new_info)
                                        apc_change_dict.setdefault(new_ai_con, {})[new_ai_port] = (d_idx, new_info)
                                        new_suffix = d_stuff.get_outlet_suffix(new_ai_con, new_ai_port)
                                        apc_ibc_sel_list[new_suffix] = new_ai_con
                                        outlet_sel_list[new_suffix] = new_ai_port
                                        apc_ibc_info_field[new_suffix] = new_info
                                    else:
                                        ibc_stuff.remove_device(old_port_num)
                                        ibc_change_dict.setdefault(old_ai_idx, {})[old_port_num] = (0, "")
                                        d_stuff.remove_ibc_connection(old_ai_idx, old_port_num)
                                        change_log.add_ok("Moved device %s from blade %d on IBC %s to outlet %d on IBC %s, setting info to '%s'" % (d_stuff.get_name(), old_port_num, ibc_dict[old_ai_idx].get_name(), new_ai_port, ibc_stuff.get_name(), new_info), "OK")
                                        d_stuff.add_ibc_connection(new_ai_con, new_ai_port, "unknown", new_info)
                                        ibc_stuff.set_device(new_ai_port, d_idx, d_stuff.get_name(), new_info)
                                        ibc_change_dict.setdefault(new_ai_con, {})[new_ai_port] = (d_idx, new_info)
                                        new_suffix = d_stuff.get_outlet_suffix(new_ai_con, new_ai_port)
                                        apc_ibc_sel_list[new_suffix] = new_ai_con
                                        outlet_sel_list[new_suffix] = new_ai_port
                                        apc_ibc_info_field[new_suffix] = new_info
                                else:
                                    new_suffix = d_stuff.get_outlet_suffix(new_ai_con, new_ai_port)
                                    apc_ibc_info_field[new_suffix] = new_info
                                    if new_ph_type == "apc":
                                        change_log.add_ok("Changed info of device %s (APC %s, outlet %d) from '%s' to '%s'" % (d_stuff.get_name(), apc_stuff.get_name(), new_ai_port, info, new_info), "OK")
                                        apc_change_dict.setdefault(new_ai_con, {})[new_ai_port] = (d_idx, new_info)
                                    else:
                                        change_log.add_ok("Changed info of device %s (IBC %s, outlet %d) from '%s' to '%s'" % (d_stuff.get_name(), ibc_stuff.get_name(), new_ai_port, info, new_info), "OK")
                                        ibc_change_dict.setdefault(new_ai_con, {})[new_ai_port] = (d_idx, new_info)
        elif sub_sel == "s":
            new_passwd = root_password.check_selection(sf, "") or glob_root_passwd
            root_password[sf] = ""
            if new_passwd:
                real_new_passwd = new_passwd.strip() or real_glob_root_passwd
                if real_new_passwd:
                    crypted = crypt.crypt(real_new_passwd, "".join([chr(random.randint(97, 122)) for x in range(16)]))
                    change_log.add_ok("Changed root_password of device '%s'" % (d_stuff.get_name()), "ok")
                else:
                    crypted = ""
                    d_stuff.add_sql_changes({"root_passwd" : ""})
                    change_log.add_ok("Cleared root_password of device '%s'" % (d_stuff.get_name()), "ok")
                d_stuff.add_sql_changes({"root_passwd" : crypted})
                d_stuff["root_passwd"] = crypted
            d_stuff.commit_sql_changes(req.dc)
    if sub_sel == "d":
        if dv_del_list:
            change_log.add_ok("Deleted %s" % (logging_tools.get_plural("device_variable", len(dv_del_list))), "SQL")
            req.dc.execute("DELETE FROM device_variable WHERE (%s)" % (" OR ".join(["device_variable_idx=%d" % (y) for (x, y) in dv_del_list])))
            for mach_idx, var_idx in dv_del_list:
                del dev_dict[mach_idx].variables[var_idx]
    if sub_sel == "p" and glob_apc:
        all_apc_idxs = apc_dict.keys()
        all_apc_idxs = all_apc_idxs[all_apc_idxs.index(glob_apc):]
        glob_apc = all_apc_idxs.pop(0)
        idx_list = []
        for dg in dg_sel_eff:
            idx_list.extend(dev_tree.get_sorted_effective_dev_idx_list(dg))
        for d_idx in [x for x in idx_list if dev_dict.has_key(x)]:
            d_stuff = dev_dict[d_idx]
            sf = d_stuff.get_suffix()
            if glob_apc:
                apc_stuff = apc_dict[glob_apc]
                while not apc_stuff.outlets.has_key(glob_outlet):
                    change_log.add_warn("APC %s has no outlet %d" % (apc_stuff.get_name(), glob_outlet), "not found")
                    glob_outlet = 1
                    if all_apc_idxs:
                        glob_apc = all_apc_idxs.pop(0)
                    else:
                        glob_apc = 0
                    if glob_apc:
                        apc_stuff = apc_dict[glob_apc]
                    else:
                        break
                if apc_stuff.outlets.has_key(glob_outlet):
                    outlet_stuff = apc_stuff.outlets[glob_outlet]
                    already_set = False
                    if outlet_stuff["device"] and apc_ibc_ignore:
                        if outlet_stuff["device"] == d_idx:
                            already_set = True
                        else:
                            change_log.add_warn("Removing device %s from outlet %d on APC %s" % (outlet_stuff["name"], glob_outlet, apc_stuff.get_name()), "used")
                            if outlet_stuff["device"] in d_sel:
                                dev_dict[outlet_stuff["device"]].remove_apc_connection(glob_apc, glob_outlet)
                            apc_stuff.remove_device(glob_outlet)
                            apc_change_dict.setdefault(glob_apc, {})[glob_outlet] = (0, "")
                    else:
                        while outlet_stuff["device"] and glob_apc:
                            if outlet_stuff["device"] == d_idx:
                                already_set = True
                                break
                            else:
                                glob_outlet += 1
                                if glob_outlet == 9:
                                    glob_outlet = 1
                                    if all_apc_idxs:
                                        glob_apc = all_apc_idxs.pop(0)
                                    else:
                                        glob_apc = 0
                                if glob_apc:
                                    apc_stuff = apc_dict[glob_apc]
                                    outlet_stuff = apc_stuff.outlets[glob_outlet]
                        if not glob_apc:
                            change_log.add_error("No free APC/outlet for device %s" % (d_stuff.get_name()), "all used")
                    if already_set:
                        change_log.add_warn("Device %s already attached to outlet %d on APC %s" % (outlet_stuff["name"], glob_outlet, apc_stuff.get_name()), "used")
                    elif glob_apc:
                        new_info = "autogenerated"
                        change_log.add_ok("Attaching device %s to APC %s, outlet %d, info '%s'" % (d_stuff.get_name(), apc_stuff.get_name(), glob_outlet, new_info), "ok")
                        d_stuff.add_apc_connection(glob_apc, glob_outlet, "unknown", new_info)
                        apc_stuff.set_device(glob_outlet, d_idx, d_stuff.get_name(), new_info)
                        apc_change_dict.setdefault(glob_apc, {})[glob_outlet] = (d_idx, new_info)
                        new_suffix = d_stuff.get_outlet_suffix(glob_apc, glob_outlet)
                        apc_ibc_sel_list[new_suffix] = glob_apc
                        outlet_sel_list[new_suffix] = glob_outlet
                        apc_ibc_info_field[new_suffix] = new_info
            else:
                change_log.add_error("No free APC/outlet for device %s" % (d_stuff.get_name()), "all used")
            if glob_apc:
                # increase apc by one
                glob_outlet += 1
                if glob_outlet == 9:
                    glob_outlet = 1
                    if all_apc_idxs:
                        glob_apc = all_apc_idxs.pop(0)
                    else:
                        glob_apc = 0
    if sub_sel == "p":
        for apc_idx, out_list in apc_change_dict.iteritems():
            for outlet, (dev_idx, dev_info) in out_list.iteritems():
                sql_str, sql_tuple = ("UPDATE msoutlet SET slave_device=%s, slave_info=%s WHERE device=%s AND outlet=%s", (dev_idx,
                                                                                                                           dev_info,
                                                                                                                           apc_idx,
                                                                                                                           outlet))
                req.dc.execute(sql_str, sql_tuple)
        for ibc_idx, out_list in ibc_change_dict.iteritems():
            for blade, (dev_idx, dev_info) in out_list.iteritems():
                sql_str, sql_tuple = ("UPDATE ibc_connection SET slave_device=%s, slave_info=%s WHERE device=%s AND blade=%s", (dev_idx,
                                                                                                                                dev_info,
                                                                                                                                ibc_idx,
                                                                                                                                blade))
                req.dc.execute(sql_str, sql_tuple)
    if fetch_partitioninfo_list:
        ds_command = tools.s_command(req, "server", 8004, "fetch_partition_info", [], 30, None, {"devname" : ",".join(fetch_partitioninfo_list)})
        tools.iterate_s_commands([ds_command], change_log)
        nagios_change = True
    out_table = html_tools.html_table(cls = "normal")
    if nagios_change:
        tools.signal_nagios_config_server(req, change_log)
    req.write("%s%s%s" % (change_log.generate_stack("Action log"),
                          html_tools.gen_hline(dev_tree.get_sel_dev_str(), 2),
                          out_table.get_header()))
    if sub_sel == "a":
        header_fields = ["Name", "SNMP Class", "Location", "Device Class"]
    elif sub_sel == "p":
        header_fields = ["Name", "APC", "Outlet", "Info", "State"]
        apc_ibc_sel_list.mode_is_setup()
        for apc_idx, apc_stuff in apc_dict.iteritems():
            free_os = apc_stuff.get_free_list()
            if apc_stuff.valid_apc():
                apc_ibc_sel_list[apc_idx] = "%s (%s used, %s free)" % (apc_stuff.get_name(),
                                                                       logging_tools.get_plural("outlet", apc_stuff.get_num_devices_set()),
                                                                       free_os and logging_tools.compress_num_list(free_os) or "none")
            else:
                apc_ibc_sel_list[apc_idx] = "%s [invalid]" % (apc_stuff.get_name())
        apc_ibc_sel_list.mode_is_normal()
    elif sub_sel == "n":
        header_fields = ["name", "Device Template", "Check", "Fetch Partitioninfo", "Nagios picture", "pic"]
    elif sub_sel == "r":
        header_fields = ["name", "relationship"]
    elif sub_sel == "d":
        header_fields = ["name", "# vars", "del", "Name", "type", "value", "Description"]
    else:
        header_fields = ["name", "passwd", "new password"]
    row0_idx = 0
    if header_fields:
        for dg in dg_sel_eff:
            out_table[0][1:len(header_fields)] = html_tools.content(dev_tree.get_sel_dev_str(dg), cls="devgroup")
            out_table[0]["class"] = "lineh"
            for head in header_fields:
                out_table[None][0] = html_tools.content(head, type="th", cls="center")
            for dev in [x for x in d_sel if x in dev_tree.get_sorted_dev_idx_list(dg)]:
                d_stuff = dev_dict[dev]
                out_table[0]["class"] = "line1%d" % (row0_idx)
                if sub_sel == "a":
                    out_table[None][0] = html_tools.content(d_stuff.get_name(), cls="left")
                    for field in [snmp_list, loc_list, class_list]:
                        out_table[None][0] = html_tools.content(field, d_stuff.get_suffix(), cls="center")
                elif sub_sel == "p":
                    num_apc_cons = len(d_stuff.apc_cons)
                    num_ibc_cons = len(d_stuff.ibc_cons)
                    out_table[None:num_apc_cons + num_ibc_cons + 2][0] = html_tools.content(d_stuff.get_name(), cls="left")
                    out_table[None][0:len(header_fields) - 1] = html_tools.content(d_stuff.get_connection_info(apc_dict, ibc_dict))
                    row1_idx = 0
                    for apc_idx, outlet, state, info in d_stuff.apc_cons:
                        out_table[0]["class"] = "line3%d" % (row1_idx)
                        act_o = apc_dict[apc_idx].outlets[outlet]
                        out_table[None][2] = html_tools.content([apc_ibc_sel_list], d_stuff.get_outlet_suffix(apc_idx, outlet), cls="right")
                        out_table[None][0] = html_tools.content(["Outlet ", outlet_sel_list], d_stuff.get_outlet_suffix(apc_idx, outlet), cls="left")
                        out_table[None][0] = html_tools.content(["Info:"  , apc_ibc_info_field], d_stuff.get_outlet_suffix(apc_idx, outlet), cls="left")
                        out_table[None][0] = html_tools.content("state is %s, power_on_delay is %s, power_off_delay is %s, reboot_delay is %s" % (act_o["state"],
                                                                                                                                                  get_time_str(act_o["pond"]),
                                                                                                                                                  get_time_str(act_o["poffd"]),
                                                                                                                                                  get_time_str(act_o["rebd"])),
                                                                cls="left")
                        row1_idx = 1-row1_idx
                    for ibc_idx, blade, state, info in d_stuff.ibc_cons:
                        out_table[0]["class"] = "line3%d" % (row1_idx)
                        act_b = ibc_dict[ibc_idx].blades[blade]
                        out_table[None][2] = html_tools.content([apc_ibc_sel_list], d_stuff.get_outlet_suffix(ibc_idx, blade), cls="right")
                        out_table[None][0] = html_tools.content(["Blade ", outlet_sel_list], d_stuff.get_outlet_suffix(ibc_idx, blade), cls="left")
                        out_table[None][0] = html_tools.content(["Info:"  , apc_ibc_info_field], d_stuff.get_outlet_suffix(ibc_idx, blade), cls="left")
                        out_table[None][0] = html_tools.content("state is %s" % (act_b["state"]), cls="left")
                        row1_idx = 1-row1_idx
                    out_table[0]["class"] = "line1%d" % (row0_idx)
                    out_table[None][2] = html_tools.content(["New "   , apc_ibc_sel_list], d_stuff.get_suffix(), cls="right")
                    out_table[None][0] = html_tools.content(["Outlet ", outlet_sel_list], d_stuff.get_suffix(), cls="left")
                    out_table[None][0] = html_tools.content(["Info:"  , apc_ibc_info_field], d_stuff.get_suffix(), cls="left")
                    out_table[None][0] = html_tools.content("&nbsp;", cls="left")
                elif sub_sel == "n":
                    out_table[None][0] = html_tools.content(d_stuff.get_name(), cls="left")
                    out_table[None][0] = html_tools.content(ng_dev_templ, d_stuff.get_suffix(), cls="center")
                    out_table[None][0] = html_tools.content(ng_dev_check, d_stuff.get_suffix(), cls="center")
                    out_table[None][0] = html_tools.content(ng_fetch_partinfo, d_stuff.get_suffix(), cls="center")
                    if len(d_sel) > 1:
                        out_table[None][0] = html_tools.content(ng_ext_host, d_stuff.get_suffix(), cls="center")
                        if ng_ext_hosts.has_key(d_stuff["ng_ext_host"]):
                            out_table[None][0] = html_tools.content("<img src=\"/%s/images/logos/%s\" border=1>" % (md_type,
                                                                                                                    ng_ext_hosts[d_stuff["ng_ext_host"]]["icon_image"]), d_stuff.get_suffix(), cls="center")
                        else:
                            out_table[None][0] = html_tools.content("N / A", cls="center")
                    else:
                        if ng_ext_hosts:
                            out_table[None][0] = html_tools.content(["keep (", ng_ext_host_rb, ") or choose from below"], "g", cls="center")
                            if ng_ext_hosts.has_key(d_stuff["ng_ext_host"]):
                                out_table[None][0] = html_tools.content("<img src=\"/%s/images/logos/%s\" border=1>" % (md_type,
                                                                                                                        ng_ext_hosts[d_stuff["ng_ext_host"]]["icon_image"]), d_stuff.get_suffix(), cls="center")
                            else:
                                out_table[None][0] = html_tools.content("N / A", cls="center")
                        else:
                            out_table[None][0:2] = html_tools.content("No nagios-pictures found", "g", cls="center")
                elif sub_sel == "r":
                    out_table[None][0] = html_tools.content(d_stuff.get_name(), d_stuff.get_suffix(), cls="left")
                    out_table[None][0] = html_tools.content([rel_ship_list, " on ", host_list], d_stuff.get_suffix(), cls="center")
                elif sub_sel == "s":
                    out_table[None][0] = html_tools.content(d_stuff.get_name(), cls="left")
                    out_table[None][0] = html_tools.content(d_stuff["root_passwd"] and "set" or "not set", cls="center")
                    for field in [root_password]:
                        out_table[None][0] = html_tools.content(field, d_stuff.get_suffix(), cls="center")
                elif sub_sel == "d":
                    v_lut = dict([(v["name"], k) for k, v in d_stuff.variables.iteritems() if k])
                    v_lut[""] = 0
                    v_names = sorted([x for x in v_lut.keys() if x])
                    num_v = len(v_names) + 1
                    out_table[None : num_v][0] = html_tools.content(d_stuff.get_name(), cls="left")
                    out_table[None : num_v][0] = html_tools.content(num_v == 1 and "-" or "%d" % (num_v - 1), cls="center")
                    v_names.append("")
                    v_idx = 0
                    for v_name in v_names:
                        v_idx += 1
                        v_stuff = d_stuff.variables[v_lut[v_name]]
                        act_y, act_x = out_table.get_cursor()
                        if v_name:
                            out_table[None][0] = html_tools.content(dv_vs.get_he("del")  , v_stuff.get_suffix(), cls="errormin")
                            out_table[None][0] = html_tools.content(dv_vs.get_he("name") , v_stuff.get_suffix(), cls="left")
                            out_table[None][0] = html_tools.content(v_stuff.get_beautify_type(), cls="center")
                        else:
                            out_table[None][0:2] = html_tools.content(["New:", dv_vs.get_he("name")] , v_stuff.get_suffix(), cls="left")
                            out_table[None][0] = html_tools.content(dv_type_list, v_stuff.get_suffix(), cls="center")
                        if v_stuff["is_public"]:
                            out_table[None][0] = html_tools.content(dv_vs.get_he("value"), v_stuff.get_suffix(), cls="left")
                            out_table[None][0] = html_tools.content(dv_vs.get_he("description"), v_stuff.get_suffix(), cls="left")
                        else:
                            if v_stuff.get_long_type() == "blob":
                                out_table[None][0] = html_tools.content(logging_tools.get_plural("Byte", len(v_stuff[v_stuff.get_var_val_name()])), v_stuff.get_suffix(), cls="left")
                            else:
                                out_table[None][0] = html_tools.content(str(v_stuff[v_stuff.get_var_val_name()]), v_stuff.get_suffix(), cls="left")
                            out_table[None][0] = html_tools.content(str(v_stuff["description"]), v_stuff.get_suffix(), cls="left")
                        if v_idx != num_v:
                            out_table.set_cursor(act_y + 1, act_x)
                            out_table[None]["class"] = "line1%d" % (row0_idx)
                row0_idx = 1 - row0_idx
            req.write(out_table.flush_lines())
    if len(d_sel) > 1:
        if sub_sel == "a":
            for head, field in [("&nbsp;", "&nbsp;"), ("SNMP Class", snmp_list), ("Location", loc_list), ("Device Class", class_list)]:
                out_table[2][0]      = html_tools.content(head , type="th", cls="center")
                out_table[3][None]   = html_tools.content(field           , cls="center")
            out_table[1][1:4] = html_tools.content("Global settings", cls="devgroup")
            out_table[2:3]["class"] = "lineh"
            req.write(out_table.flush_lines("g"))
        elif sub_sel == "p":
            out_table[0]["class"] = "lineh"
            out_table[None][0:len(header_fields)] = html_tools.content("Global settings", type = "th", cls="center")
            out_table[0]["class"] = "line10"
            out_table[None][0:len(header_fields)] = html_tools.content(["Attach all devices; starting at ", apc_ibc_sel_list, ", outlet ", outlet_sel_list, "; overwrite connected devices: ",
                                                                        apc_ibc_ignore_connected,
                                                                        ", clear already set connections:",
                                                                        apc_ibc_clear_connections], cls="left")
            req.write(out_table.flush_lines("g"))
        elif sub_sel == "n":
            for head, field, pre_str, post_str in [("&nbsp;", "&nbsp;", "", ""),
                                                   ("NG Device Template", ng_dev_templ, "", ""),
                                                   ("Check", ng_monitor_check, "", ""),
                                                   ("Fetch Partitioninfo", "&nbsp;", "", ""),
                                                   ("Nagios picture", ng_ext_host_rb, "keep (", ") or choose from below"),
                                                   ("pic", "&nbsp;", "", "")]:
                out_table[2][0]      = html_tools.content(head , type="th"          , cls="center")
                out_table[3][None]   = html_tools.content([pre_str, field, post_str], cls="center")
            out_table[1][1:6] = html_tools.content("Global settings", cls="devgroup")
            out_table[2:3]["class"] = "lineh"
            req.write(out_table.flush_lines("g"))
        elif sub_sel == "s":
            for head, field in [("&nbsp;", "&nbsp;"), ("&nbsp;", "&nbsp;"), ("new password", root_password)]:
                out_table[2][0]      = html_tools.content(head , type="th", cls="center")
                out_table[3][None]   = html_tools.content(field           , cls="center")
            out_table[1][1:3] = html_tools.content("Global settings", cls="devgroup")
            out_table[2:3]["class"] = "lineh"
            req.write(out_table.flush_lines("g"))
    submit_button = html_tools.submit_button(req, "submit")
    submit_button.set_class("", "button")
    req.write(out_table.get_footer())
    if sub_sel == "n":
        if ng_ext_hosts:
            max_nag_rows = 10
            req.write(html_tools.gen_hline("Found %s:" % (logging_tools.get_plural("icon", len(ng_ext_hosts.keys()))), 3))
            # show nagios pictures
            np_table = html_tools.html_table(cls="normal")
            row_idx, line_idx = (1, 1)
            for ng_eh_stuff in ng_ext_hosts.values():
                np_table[line_idx]["class"] = "line10"
                np_table[line_idx][row_idx] = html_tools.content("<img src=\"/%s/images/logos/%s\" border=1>" % (md_type,
                                                                                                                 ng_eh_stuff["icon_image"]), cls="center")
                np_table[line_idx + 1]["class"] = "line11"
                np_table[line_idx + 1][row_idx] = html_tools.content([ng_eh_stuff["name"], ng_ext_host_rb], cls="center")
                row_idx += 1
                if row_idx == max_nag_rows + 1:
                    line_idx += 2
                    row_idx = 1
            if row_idx != 1:
                np_table[line_idx : line_idx + 1][row_idx : max_nag_rows] = html_tools.content("&nbsp;")
            req.write(np_table("g"))
    low_submit[""] = 1
    req.write("%s<div class=\"center\">%s</div>\n" % (low_submit.create_hidden_var(),
                                                      submit_button("")))
