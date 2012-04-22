#!/usr/bin/python -Ot
# -*- coding: utf-8 -*-
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008,2009,2011,2012 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
# 
# This file is part of webfrontend
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
""" basic tools for DB abstraction """

import net_tools
import re
import copy
import logging_tools
import html_tools
import pprint
import server_command
import process_tools
import time
import sys
import os
import ipvx_tools

class ordered_iteritems_iterator(object):
    def __init__(self, od):
        self.__od = od
        self.__kl = self.__od.get_keys()
    def __iter__(self):
        self.__index = 0
        return self
    def next(self):
        if self.__index == len(self.__kl):
            raise StopIteration
        act_key = self.__kl[self.__index]
        self.__index += 1
        return act_key, self.__od[act_key]
    def __repr__(self):
        return "{%s}" % (", ".join(["'%s' : %s" % (k, v) for k, v in self.__iter__()]))
        
class ordered_itervalues_iterator(object):
    def __init__(self, od):
        self.__od = od
        self.__kl = self.__od.get_keys()
    def __iter__(self):
        self.__index = 0
        return self
    def next(self):
        if self.__index == len(self.__kl):
            raise StopIteration
        act_key = self.__kl[self.__index]
        self.__index += 1
        return self.__od[act_key]
    def __repr__(self):
        return "[%s]" % (", ".join(["'%s'" % (k) for k in self.__iter__()]))
        
class ordered_iterkeys_iterator(object):
    def __init__(self, od):
        self.__od = od
        self.__kl = self.__od.get_keys()
    def __iter__(self):
        self.__index = 0
        return self
    def next(self):
        if self.__index == len(self.__kl):
            raise StopIteration
        act_key = self.__kl[self.__index]
        self.__index += 1
        return act_key
    def index(self, k):
        return self.__kl.index(k)
    def __getitem__(self, k):
        return self.__kl[k]
    def __len__(self):
        return len(self.__kl)
    def __repr__(self):
        return "[%s]" % (", ".join(["'%s'" % (k) for k in self.__iter__()]))
        
class ordered_dict(dict):
    def __init__(self):
        dict.__init__(self)
        self.__key_list = []
        self.__index = 0
    def __setitem__(self, key, value):
        dict.__setitem__(self, key, value)
        if key not in self.__key_list:
            self.__key_list.append(key)
    def iteritems(self):
        return ordered_iteritems_iterator(self)
    def itervalues(self):
        return ordered_itervalues_iterator(self)
    def iterkeys(self):
        return ordered_iterkeys_iterator(self)
    def values(self):
        return ordered_itervalues_iterator(self)
    def key(self):
        return ordered_iterkeys_iterator(self)
    def keys(self):
        return ordered_iterkeys_iterator(self)
    def get_keys(self):
        return self.__key_list
    def has_key(self, value):
        return value in self.__key_list
    def setdefault(self, key, what):
        if key not in self.__key_list:
            dict.__setitem__(self, key, what)
            self.__key_list.append(key)
        return dict.__getitem__(self, key)
    def __delitem__(self, key):
        if key in self.__key_list:
            self.__key_list.remove(key)
        dict.__delitem__(self, key)
    def __nonzero__(self):
        return len(self.__key_list)
    def __len__(self):
        return len(self.__key_list)
    def __repr__(self):
        return "{%s}" % (", ".join(["'%s' : %s" % (k, v) for k, v in self.iteritems()]))
    
def get_ordered_idx_list(in_dict, sort_key):
    sort_dict = dict([(v[sort_key], k) for k, v in in_dict.iteritems() if v[sort_key]])
    return [sort_dict[k] for k in sorted(sort_dict.keys())]

def is_mac_address(mac, mac_bytes=6):
    return re.match("^%s$" % (":".join(["([a-f0-9]{2})"] * mac_bytes)), mac.lower())
    
def is_number(num):
    if type(num) in [type(0), type(0L)]:
        return True
    elif type(num) == type(None):
        return False
    else:
        if len(num) > 1 and num.startswith("-"):
            num = num[1:]
        return num.isdigit()

class display_list(object):
    def __init__(self, req, **args):
        self.req = req
        self.__grp_regexp, self.__dev_regexp = ("", "")
        self.__devsel_field, self.__devsel_action_field = (None, None)
        self.__new_dev_selection, self.__devsel_action = ("", "a")
        self.__ds_dict = ordered_dict()
        self.__device_preselection = []
        self.__device_deselection = []
        self.__include_mdg = args.get("include_cluster_meta_device_group", False)
        self.__query_meta_devices = args.get("with_meta_devices", False)
        self.size = 5
    def add_device_preselection(self, psd):
        self.__device_preselection += psd
    def remove_device_deselection(self, dvd):
        self.__device_deselection += dvd
    def add_regexp_field(self, name="re", size = 255, view = 16):
        self.__devg_re_field = html_tools.text_field(self.req, "dldgr%s" % (name), size=size, display_len=view)
        self.__dev_re_field = html_tools.text_field(self.req, "dldr%s" % (name), size=size, display_len=view)
        self.__grp_regexp = self.__devg_re_field.check_selection("", "")
        self.__dev_regexp = self.__dev_re_field.check_selection("", "")
        self.__devg_re_field[""] = ""
        self.__dev_re_field[""] = ""
    def get_dev_re_field(self):
        return self.__dev_re_field
    def get_devg_re_field(self):
        return self.__devg_re_field
    def get_devsel_field(self):
        return self.__devsel_field
    def get_devsel_action_field(self):
        return self.__devsel_action_field
    def add_devsel_fields(self, ds_dict, name="ds", size=255, view=16):
        self.__ds_dict = ds_dict
        self.__devsel_field = html_tools.text_field(self.req, name, size=size, display_len=view)
        self.__devsel_action_field = html_tools.selection_list(self.req, "%sa" % (name), {"a" : "save as public",
                                                                                          "b" : "save as private",
                                                                                          "c" : "delete"})
        self.__new_dev_selection = self.__devsel_field.check_selection("", "")
        self.__devsel_field[""] = ""
        self.__devsel_action = self.__devsel_action_field.check_selection("", "a")
        #self.__devsel_action_field[""] = "a"
    def query(self, device_types=[], device_fields=[], add_tables=[], add_queries=[], left_joins=[], var_dict={}):
        if device_types:
            pos_str = " OR ".join(["dt.identifier='%s'" % (x) for x in device_types if not x.startswith("!")]) or None
            neg_str = " AND ".join(["dt.identifier!='%s'" % (x[1:]) for x in device_types if x.startswith("!")]) or None
            if pos_str and neg_str:
                dt_string = "((%s) AND (%s))" % (pos_str, neg_str)
            elif pos_str:
                dt_string = "(%s)" % (pos_str)
            elif neg_str:
                dt_string = "(%s)" % (neg_str)
            else:
                dt_string = None
            #dt_string=" OR ".join(["dt.identifier='%s'" % (x) for x in self.__device_types])
        else:
            dt_string = None
        self.__dev_fields     = device_fields + ["name", "device_group", "bootserver", "device_idx", "show_in_bootcontrol", "xen_guest", "dg.device_group_idx",
                                                 "dg.cluster_device_group", "dg.name AS dgname", "dt.identifier"]
        self.__from_tables    = add_tables    + [("device_group", "dg")]
        self.__left_joins     = ["device d ON d.device_group=dg.device_group_idx"] + left_joins
        self.__sql_restraints = add_queries   + (dt_string and [dt_string] or [])
        sql_str = "SELECT DISTINCT %s " % (", ".join(["d.%s" % (x) for x in self.__dev_fields if not x.count(".")] + [x for x in self.__dev_fields if x.count(".")])) + \
            "FROM %s " % (" INNER JOIN ".join(["%s %s" % (x, y) for x, y in self.__from_tables])) + \
            "LEFT JOIN %s " % (" LEFT JOIN ".join(self.__left_joins)) + \
            "LEFT JOIN device_type dt ON dt.device_type_idx=d.device_type %s ORDER BY dgname, d.name" % ("WHERE %s" % (" AND ".join(self.__sql_restraints)) if self.__sql_restraints else "")
        self.__sql_str = sql_str
        #print "***", self.__sql_str
        # fields to copy for device_groups
        dg_fields  = [x.split()[-1].split(".")[-1] for x in self.__dev_fields if x.startswith("dg")]
        # fields to copy for devices
        d_fields   = [x.split()[-1].split(".")[-1] for x in self.__dev_fields if x not in dg_fields]
        # fields to copy for meta-devices
        mdg_fields = ["device_idx", "name", "device_group"]
        self.req.dc.execute(self.__sql_str)
        dev_tree, md_info, dg_info, d_info = ({}, {}, {}, {})
        dg_lut, d_lut = ({}, {})
        # list of (sorted) device/group names
        dgn_list, dn_list = ([], [])
        # for adding of cluster_meta_device_group
        cdg_idx, cdmd_idx, cdmd_found = (0, 0, False)
        vd_keys = var_dict.keys()
        for sql_rec in self.req.dc.fetchall():
            if sql_rec["device_group_idx"] not in dev_tree.keys():
                dgn_list.append(sql_rec["dgname"])
                dev_tree[sql_rec["device_group_idx"]] = []
                dg_lut[sql_rec["device_group_idx"]] = sql_rec["dgname"]
                dg_info[sql_rec["device_group_idx"]] = dict([(a, sql_rec[a]) for a in dg_fields])
                if sql_rec["cluster_device_group"]:
                    cdg_idx = sql_rec["device_group_idx"]
            if sql_rec["identifier"] == "MD":
                if not md_info.has_key(sql_rec["device_group_idx"]):
                    md_info[sql_rec["device_group_idx"]] = dict([(a, sql_rec[a]) for a in mdg_fields])
                    if sql_rec["device_group"] == cdg_idx:
                        cdmd_idx = sql_rec["device_idx"]
                        if self.__include_mdg:
                            cdmd_found = True
            if (sql_rec["device_idx"] and (sql_rec["identifier"] != "MD" or self.__query_meta_devices)) or cdmd_found:
                if sql_rec["name"] not in dn_list:
                    cdmd_found = False
                    dn_list.append(sql_rec["name"])
                    dev_tree[sql_rec["device_group_idx"]].append(sql_rec["device_idx"])
                    d_lut[sql_rec["device_idx"]] = sql_rec["name"]
                    d_info[sql_rec["device_idx"]] = dict([(a, sql_rec[a]) for a in d_fields] + [(a, {}) for a in vd_keys])
                d_struct = d_info[sql_rec["device_idx"]]
                for v_key in vd_keys:
                    if v_key in sql_rec.keys() and sql_rec[v_key] not in d_struct[v_key].keys():
                        d_struct[v_key][sql_rec[v_key]] = dict([(k, sql_rec[k]) for k in var_dict[v_key]])
        # save it
        self.__dgn_list = dgn_list
        self.dn_list = dn_list
        self.__md_info = md_info
        self.__dev_tree = dev_tree
        self.__dg_lut , self.__d_lut = (dg_lut , d_lut)
        self.__dg_info , self.__d_info = (dg_info, d_info)
        self.build_inverse_luts()
        act_dev_sel = [int(x) for x in self.req.sys_args.get("devs", []) if x.isdigit()]
        if act_dev_sel:
            dg_sel, d_sel = ([], [])
            for act_devs in act_dev_sel:
                if self.__ds_dict.has_key(act_devs):
                    d_sel.extend([x for x in self.__ds_dict[act_devs]["devices"] if x not in d_sel])
        else:
            # check for selected devicegroups/devices
            dg_sel = [y for y in [int(x) for x in self.req.sys_args.get("devg", []) if x.isdigit()] if y in dg_lut.keys()]
            d1_sel = [y for y in [int(x) for x in self.req.sys_args.get("dev" , []) + self.__device_preselection if x.isdigit()] if
                      (y not in self.__device_deselection) and (y in d_lut.keys())]
            d_sel = []
            for d1_sub_sel in d1_sel:
                if d1_sub_sel not in d_sel:
                    d_sel.append(d1_sub_sel)
        if self.__grp_regexp:
            if self.__grp_regexp.startswith("!"):
                try:
                    dg_re = re.compile("%s" % (self.__grp_regexp[1:]) or ".*")
                except:
                    pass
                else:
                    new_dg_sel, dg_del = ([], [])
                    for dg in [x for x in dg_lut.keys() if x in dg_sel]:
                        if dg_re.search(dg_lut[dg].lower()):
                            dg_del.append(dg)
                        else:
                            new_dg_sel.append(dg)
                    dg_sel = new_dg_sel
                    # deselect devices
                    new_d_sel = []
                    for d_sub_sel in d_sel:
                        if self.__d_info[d_sub_sel]["device_group"] not in dg_del:
                            new_d_sel.append(d_sub_sel)
                    d_sel = new_d_sel
            else:
                try:
                    dg_re = re.compile("%s" % (self.__grp_regexp) or ".*")
                except:
                    pass
                else:
                    for dg in [x for x in dg_lut.keys() if x not in dg_sel]:
                        if dg_re.search(dg_lut[dg].lower()):
                            dg_sel.append(dg)
        if self.__dev_regexp:
            if self.__dev_regexp.startswith("!"):
                try:
                    d_re = re.compile("%s" % (self.__dev_regexp[1:]) or ".*")
                except:
                    pass
                else:
                    new_d_sel = []
                    for sub_sel in [x for x in d_lut.keys() if x in d_sel]:
                        if not d_re.search(d_lut[sub_sel].lower()):
                            new_d_sel.append(sub_sel)
                        else:
                            # deselect devicegroup
                            if self.__d_info[sub_sel]["device_group"] in dg_sel:
                                dg_sel.remove(self.__d_info[sub_sel]["device_group"])
                    d_sel = new_d_sel
            else:
                try:
                    d_re = re.compile("%s" % (self.__dev_regexp) or ".*")
                except:
                    pass
                else:
                    for sub_sel in [x for x in d_lut.keys() if x not in d_sel]:
                        if d_re.search(d_lut[sub_sel].lower()):
                            d_sel.append(sub_sel)
        # effective dg_selection
        dg_sel_eff = copy.deepcopy(dg_sel)
        # selected all devices of a selected dg
        for sdg in dg_sel:
            d_sel.extend([x for x in dev_tree[sdg] if x not in d_sel])
        # select all devicegroups where all devices are selected
        for sdg in [x for x in dev_tree.keys() if x not in dg_sel]:
            if dev_tree[sdg]:
                if len(dev_tree[sdg]) == len([y for y in d_sel if y in dev_tree[sdg]]):
                    dg_sel.append(sdg)
                    dg_sel_eff.append(sdg)
                elif len([y for y in dev_tree[sdg] if y in d_sel]):
                    dg_sel_eff.append(sdg)
        dg_sel = [self.get_devg_idx(x) for x in sorted([self.get_devg_name(x) for x in dg_sel])]
        d_sel = [self.get_dev_idx(x) for x in sorted([self.get_dev_name(x) for x in d_sel])]
        dg_sel_eff = [self.get_devg_idx(x) for x in sorted([self.get_devg_name(x) for x in dg_sel_eff])]
        #print "*", dg_sel, "*", d_sel, "*", dg_sel_eff, "*<br>"
        self.__dg_sel, self.__d_sel, self.__dg_sel_eff = (dg_sel, d_sel, dg_sel_eff)
        if self.__new_dev_selection and (d_sel or self.__devsel_action == "c"):
            old_found = [x for x in self.__ds_dict.values() if x["name"] == self.__new_dev_selection]
            if old_found:
                old_idx = old_found[0]["device_selection_idx"]
                self.req.dc.execute("DELETE FROM device_device_selection WHERE device_selection=%d" % (old_idx))
                self.req.dc.execute("DELETE FROM device_selection WHERE device_selection_idx=%d" % (old_idx))
                del self.__ds_dict[old_idx]
            if self.__devsel_action in ["a", "b"]:
                ins_user = self.__devsel_action == "b" and self.req.user_info.get_idx() or 0
                self.req.dc.execute("INSERT INTO device_selection SET name=%s, user=%s", (self.__new_dev_selection,
                                                                                                ins_user))
                ins_idx = self.req.dc.insert_id()
                self.req.dc.execute("INSERT INTO device_device_selection VALUES%s" % (",".join(["(0, %d, %d, null)" % (ins_idx, x) for x in d_sel])))
                self.__ds_dict[ins_idx] = {"name"                 : self.__new_dev_selection,
                                           "devices"              : copy.deepcopy(d_sel),
                                           "device_selection_idx" : ins_idx,
                                           "user"                 : ins_user}
                generate_device_selection_info_strings(self.__ds_dict) 
            # check for 
        #print "*", self.__new_dev_selection
    def get_device_selection_lists(self):
        return self.__ds_dict
    def __call__(self, suffix=""):
        if suffix == "devg":
            return self.get_devicegroup_str()
        elif suffix == "dev":
            return self.get_device_str()
        elif suffix == "sel":
            return self.get_device_selection_str()
        else:
            return "unknown suffix \"%s\"" % (suffix)
    def get_devicegroup_str(self):
        out_f = ["<select name=\"devg[]\" size=\"%d\" multiple>" % (self.size)]
        for dg in self.get_sorted_devg_idx_list():
            if self.get_num_of_devs(dg):
                out_f.append("<option value=\"%d\" %s>%s (%s)</option>" % (dg,
                                                                           (dg in self.__dg_sel and "selected") or "",
                                                                           self.get_devg_name(dg),
                                                                           logging_tools.get_plural("device", self.get_num_of_devs(dg))))
        out_f.append("</select>")
        return "\n".join(out_f)
    def get_device_str(self):
        out_f = ["<select name=\"dev[]\" size=\"%d\" multiple>" % (self.size)]
        for dg in self.get_sorted_devg_idx_list():
            if self.get_num_of_devs(dg):
                out_f.append("<option value=\"%d\" disabled class=\"inverse\">%s (%s)</option>" % (dg,
                                                                                                   self.get_devg_name(dg),
                                                                                                   logging_tools.get_plural("device", self.get_num_of_devs(dg))))
                # two loops: first for Metadevices, than the normal ones
                for meta_show in [True, False]:
                    for dev in self.get_sorted_dev_idx_list(dg):
                        dev_struct = self.get_dev_struct(dev)
                        show_it = False
                        if meta_show and dev_struct["identifier"] == "MD":
                            show_it = True
                            dev_show_name = dev_struct["name"]
                            if dev_show_name.startswith("METADEV_"):
                                dev_show_name = dev_show_name[8:]
                            dev_show_name += " (md)"
                        elif not meta_show and dev_struct["identifier"] != "MD":
                            show_it = True
                            dev_show_name = dev_struct["name"]
                        if show_it:
                            out_f.append("<option value=\"%d\"%s%s>%s%s%s%s</option>" % (dev,
                                                                                         "selected" if (dev in self.__d_sel) else "",
                                                                                         dev_struct.has_key("class") and " class=\"%s\"" % (dev_struct["class"]) or "",
                                                                                         dev_struct.get("pre_str", ""),
                                                                                         dev_show_name,
                                                                                         (dev_struct["comment"] and " (%s)" % (dev_struct["comment"])) or "",
                                                                                         dev_struct.get("post_str", "")
                                                                                         ))
        out_f.append("</select>")
        return "\n".join(out_f)
    def get_device_selection_str(self):
        out_f = []
        if self.__ds_dict:
            out_f.append("<select name=\"devs[]\" size=\"%d\" multiple>" % (self.size))
            for ds_idx, ds_stuff in self.__ds_dict.iteritems():
                out_f.append("<option value=\"%d\">%s</option>" % (ds_idx, ds_stuff["info"]))
            out_f.append("</select>")
        return "\n".join(out_f)
    def get_devg_regexp_str(self):
        return self.__devg_re_field("")
    def get_dev_regexp_str(self):
        return self.__dev_re_field("")
    def get_devsel_str(self):
        return self.__devsel_field("")
    def get_devsel_action_str(self):
        return self.__devsel_action_field("")
    def build_inverse_luts(self):
        self.__dg_lut_inv = dict(zip(self.__dg_lut.values(), self.__dg_lut.keys()))
        self.__d_lut_inv = dict(zip( self.__d_lut.values(), self.__d_lut.keys()))
    def devices_selected(self):
        return self.__d_sel and 1 or 0
    def rename_device_group(self, dg, new_name):
        self.__dgn_list.remove(self.__dg_lut[dg])
        # enqueue
        ins_idx = 0
        for dgn in self.__dgn_list:
            if new_name.lower() < dgn.lower():
                break
            ins_idx += 1
        self.__dgn_list.insert(ins_idx, new_name)
        self.__dg_info[dg]["dgname"] = new_name
        self.__dg_lut[dg] = new_name
        self.build_inverse_luts()
    def rename_device(self, dg, d_idx, new_name):
        self.dn_list.remove(self.__d_lut[d_idx])
        # enqueue
        ins_idx = 0
        for dn in self.dn_list:
            if new_name.lower() < dn.lower():
                break
            ins_idx += 1
        self.dn_list.insert(ins_idx, new_name)
        self.__d_info[d_idx]["name"] = new_name
        self.__d_lut[d_idx] = new_name
        self.build_inverse_luts()
    def add_device(self, dg_idx, d_struct):
        # enqueue
        ins_idx = 0
        for dn in self.dn_list:
            if d_struct["name"].lower() < dn.lower():
                break
            ins_idx += 1
        self.dn_list.insert(ins_idx, d_struct["name"])
        self.__d_lut[d_struct["device_idx"]] = d_struct["name"]
        self.__d_info[d_struct["device_idx"]] = dict([(a, d_struct[a]) for a in d_struct.keys()])
        # enqueue into dev_tree
        ins_idx = 0
        for di in self.__dev_tree[dg_idx]:
            if d_struct["name"].lower() < self.__d_info[di]["name"].lower():
                break
            ins_idx += 1
        self.__dev_tree[dg_idx].insert(ins_idx, d_struct["device_idx"])
        self.build_inverse_luts()
    def add_device_group(self, dg_struct, md_struct=None):
        # enqueue
        ins_idx = 0
        for dgn in self.__dgn_list:
            if dg_struct["dgname"].lower() < dgn.lower():
                break
            ins_idx += 1
        self.__dgn_list.insert(ins_idx, dg_struct["dgname"])
        self.__dev_tree[dg_struct["device_group_idx"]] = []
        self.__dg_lut[dg_struct["device_group_idx"]] = dg_struct["dgname"]
        self.__dg_info[dg_struct["device_group_idx"]] = dict([(a, dg_struct[a]) for a in dg_struct.keys()])
        if md_struct:
            self.add_meta_device(dg_struct["device_group_idx"], md_struct)
        self.build_inverse_luts()
    def add_meta_device(self, dg, md_struct):
        if md_struct:
            self.__md_info[dg] = dict([(a, md_struct[a]) for a in md_struct.keys()])
    def delete_meta_device(self, dg):
        if self.__md_info.has_key(dg):
            del self.__md_info[dg]
    def delete_device_group(self, dg_idx):
        dgn_name = self.__dg_lut[dg_idx]
        self.__dgn_list.remove(dgn_name)
        del self.__dev_tree[dg_idx]
        del self.__dg_lut[dg_idx]
        del self.__dg_info[dg_idx]
        if self.__md_info.has_key(dg_idx):
            del self.__md_info[dg_idx]
        self.build_inverse_luts()
    def delete_device(self, d_idx, dg_idx):
        dn_name = self.__d_lut[d_idx]
        self.dn_list.remove(dn_name)
        self.__dev_tree[dg_idx].remove(d_idx)
        del self.__d_lut[d_idx]
        del self.__d_info[d_idx]
        self.build_inverse_luts()
    def devices_found(self):
        return (self.__dev_tree and 1) or 0
    def get_devg_name(self, dg_idx):
        return self.__dg_info[dg_idx]["dgname"]
    def get_dev_name(self, d_idx):
        return self.get_dev_struct(d_idx)["name"]
    def get_devg_idx(self, dg_name):
        return self.__dg_lut_inv[dg_name]
    def get_dev_idx(self, d_name):
        return self.__d_lut_inv[d_name]
    def get_num_of_devs(self, dg_idx=None):
        if dg_idx:
            return len(self.__dev_tree[dg_idx])
        else:
            return sum([len(x) for x in self.__dev_tree.values()])
    def get_num_of_devgs(self):
        return len(self.__dev_tree.keys())
    def get_sorted_devg_idx_list(self):
        return [self.__dg_lut_inv[x] for x in self.__dgn_list]
    def get_sorted_dev_idx_list(self, dg_idx):
        return self.__dev_tree[dg_idx]
    def get_sorted_effective_dev_idx_list(self, dg_idx):
        return [x for x in self.__dev_tree[dg_idx] if x in self.__d_sel]
    def get_dev_struct(self, d_idx):
        return self.__d_info[d_idx]
    def get_devg_struct(self, dg_idx):
        return self.__dg_info[dg_idx]
    def devg_has_md(self, dg_idx):
        return self.__md_info.has_key(dg_idx)
    def get_md_struct(self, dg_idx):
        return self.__md_info.get(dg_idx, None)
    def get_selection(self):
        return self.__dg_sel, self.__d_sel, self.__dg_sel_eff
    def get_all_devg_names(self):
        return self.__dgn_list
    def get_all_dev_names(self):
        return self.dn_list
    def write_hidden_sel(self):
        self.req.write(self.get_hidden_sel())
    def get_hidden_sel(self):
        return "".join(["<input type=hidden name=\"dev[]\" value=\"%d\"/>\n" % (x) for x in self.__d_sel])
    def move_device(self, d_idx, old_dg, new_dg):
        self.__dev_tree[old_dg].remove(d_idx)
        # enqueue
        ins_idx = 0
        for di in self.__dev_tree[new_dg]:
            if self.__d_info[d_idx]["name"].lower() < self.__d_info[di]["name"].lower():
                break
            ins_idx += 1
        self.__dev_tree[new_dg].insert(ins_idx, d_idx)
    def get_sel_dev_str(self, dg=None):
        if dg is None:
            ret_str = "Selected %s in %s" % (logging_tools.get_plural("device", len(self.__d_sel)),
                                             logging_tools.get_plural("devicegroup", len(self.__dg_sel_eff)))
        else:
            ret_str = "devicegroup %s, " % (self.get_devg_name(dg))
            idx_list = self.get_sorted_dev_idx_list(dg)
            sel_list = [x for x in idx_list if x in self.__d_sel]
            if sel_list == idx_list:
                if len(sel_list) == 1:
                    ret_str += "device is selected"
                else:
                    ret_str += "all %s selected" % (logging_tools.get_plural("device", len(idx_list)))
            else:
                ret_str += "%d of %s selected" % (len(sel_list), logging_tools.get_plural("device", len(idx_list)))
        return ret_str
    
# server command struct
class s_command(object):
    def __init__(self, req, config, port, command, devs, timeout=5, hostname=None, add_dict={}, **kwargs):
        self.config, self.hostname, self.port = (config, hostname, port)
        self.start_time = time.time()
        self.req = req
        if type(devs) == type({}):
            self.devs = devs
        else:
            self.devs = dict(zip(devs, [""] * len(devs)))
        self.set_state("w", "initialising")
        if type(command) == type(""):
            self.command = command
            self.server_com = server_command.server_command(command=command)
            self.server_com.set_option_dict(add_dict)
        else:
            self.server_com = command
            self.command = command.get_command()
        self.server_reply = None
        self.set_possible_hosts()
        self.hostip = None
        targ_ip = None
        if self.req.conf["server"].has_key(config):
            hosts = self.req.conf["server"][config]
            if hostname:
                if hosts.has_key(hostname):
                    targ_ip = hosts[hostname]
                    self.set_possible_hosts([hostname])
                else:
                    self.req.info_stack.add_error("unknown host %s for config %s" % (hostname, config), "config")
                    self.set_state("e", "error unknown host %s for config %s" % (hostname, config))
            else:
                # when no host is specified prefer the localhost
                if "127.0.0.1" in hosts.values():
                    self.hostname = [key for key, value in hosts.iteritems() if value == "127.0.0.1"][0]
                else:
                    self.hostname = hosts.keys()[0]
                targ_ip = hosts[self.hostname]
                self.set_possible_hosts(hosts.keys())
            # target type, TCP or 0MQ
            web_srv_name = "/etc/sysconfig/cluster/srv_targets"
            st_dict = {}
            if os.path.isfile(web_srv_name):
                for srv_ip, srv_port, srv_type in [line.strip().split(":") for line in file(web_srv_name, "r").read().split("\n") if line.strip() and line.count(":") == 2]:
                    st_dict["%s:%s" % (srv_ip, srv_port)] = srv_type
            self.srv_type = st_dict.get("%s:%d" % (targ_ip, port), "T")
            if targ_ip:
                self.hostip = targ_ip
                if self.srv_type == "0":
                    # rewrite server_command to srv_command
                    srv_com = server_command.srv_command(command=self.command)
                    opt_dict = self.server_com.get_option_dict()
                    if opt_dict:
                        for key, value in opt_dict.iteritems():
                            srv_com["server_key:%s" % (key)] = value
##                    print srv_com, unicode(srv_com)
##                    print self.server_com.get_option_dict()
                    self.server_com = srv_com
                else:
                    print self.command
                    self.server_com.set_nodes(self.devs.keys())
                    self.server_com.set_node_commands({})
                    for dev, com in self.devs.iteritems():
                        if com:
                            self.server_com.set_node_command(dev, com)
        else:
            self.set_state("e", "error unknown config %s" % (config))
            self.req.info_stack.add_error("unknown config %s" % (config), "config")
    def __getitem__(self, key):
        if key == "host":
            return self.hostip if self.hostip != None else self.hostname
        elif key == "port":
            return self.port
        elif key == "command":
            if self.srv_type == "0":
                return unicode(self.server_com)
            else:
                return self.server_com.create_string()
        else:
            print "Unknown key %s for __getitem__ in s_command (tools.py)" % (key)
    def get(self, key, default_value):
        if key in ["host", "port", "command"]:
            return self[key]
        else:
            return default_value
    def get_conn_str(self):
        return "tcp://%s:%d" % (self.hostip,
                                self.port)
    def get_hostname(self):
        return self.hostname
    def set_possible_hosts(self, h_list=[]):
        self.possible_hosts = h_list
    def get_possible_hosts(self):
        return self.possible_hosts
    def set_state(self, act_stat, ret=None):
        self.act_state = act_stat
        if ret:
            self.set_return(ret)
    def get_state(self):
        return self.act_state
    def set_return(self, what="not set"):
        self.act_return = what
    def get_return(self):
        return self.act_return
    def get_info(self):
        return "%s [%s:%d, %s], command %s%s" % (
            self.config,
            self.hostip or "notset",
            self.port,
            "TCP" if self.srv_type == "T" else "0MQ",
            self.command,
            self.hostname and ", host %s" % (self.hostname) or "")
    def add_to_log(self, log, info, res, stat=None):
        if log:
            if stat is None:
                if type(res) == type(()):
                    stat, res = res
                    if stat == server_command.SRV_REPLY_STATE_OK:
                        log.add(info, res.strip(), 1)
                    elif stat == server_command.SRV_REPLY_STATE_WARN:
                        log.add(info, res.strip(), 2)
                    else:
                        log.add(info, res.strip(), 0)
                else:
                    if res.startswith("error"):
                        log.add(info, res[5:].strip(), 0)
                    elif res.startswith("warn"):
                        log.add(info, res[4:].strip(), 2)
                    else:
                        log.add(info, res.strip(), 1)
            else:
                log.add(info, res.strip(), stat)
    def set_0mq_result(self, srv_reply):
        self.end_time = time.time()
        time_info = logging_tools.get_diff_time_str(self.end_time - self.start_time)
        com_str = "command '%s' to %s (%s%s) in %s" % (self.command,
                                                       self.hostname,
                                                       "[%s] " % (self.hostip) if self.hostip else "",
                                                       self.config,
                                                       time_info)
        error = int(srv_reply["result"].attrib["state"])
        reply_str = srv_reply["result"].attrib["reply"]
        if error:
            self.set_state("e", "error %s" % (reply_str))
            self.req.info_stack.add_error("info (%s, %s, %d): %s" % (self.get_info(),
                                                                     time_info,
                                                                     error,
                                                                     reply_str), "result")
        else:
            self.set_state("o", reply_str)
        self.server_reply = srv_reply
    def set_result(self, what, log=None):
        self.end_time = time.time()
        time_info = logging_tools.get_diff_time_str(self.end_time - self.start_time)
        com_str = "command '%s'%s to %s (%s%s) in %s" % (self.command,
                                                         self.server_com.get_option_dict() and \
                                                             " with %s" % (logging_tools.get_plural("option", len(self.server_com.get_option_dict().keys()))) or "",
                                                         self.hostname,
                                                         "[%s] " % (self.hostip) if self.hostip else "",
                                                         self.config,
                                                         time_info)
        error, res_str = what
        if error:
            self.req.info_stack.add_error("info (%s, %s, %d): %s" % (self.get_info(),
                                                                     time_info,
                                                                     error,
                                                                     res_str[:32]), "result")
            self.set_state("e", "error %s" % (res_str))
            server_repl = server_command.server_reply(result="error %s" % (res_str), node_results={})
            for node in self.server_com.get_nodes():
                server_repl.set_node_result(node, res_str)
            self.server_reply = server_repl
        else:
            try:
                server_repl = server_command.server_reply(res_str)
            except ValueError:
                self.req.info_stack.add_error("info (%s, %s, %s): %s" % (self.get_info(),
                                                                         time_info,
                                                                         process_tools.get_except_info(),
                                                                         res_str[:32]), "result")
                self.set_state("e", "error interpreting result")
                self.add_to_log(log, com_str, res_str)
            else:                
                self.server_reply = server_repl
                if server_repl.get_state() > server_command.SRV_REPLY_STATE_WARN:
                    self.req.info_stack.add_error("info (%s, %s): %s" % (self.get_info(), time_info, server_repl.get_result()), "result")
                    self.set_state("e", "error %s" % (server_repl.get_result()))
                    self.add_to_log(log, com_str, server_repl.get_state_and_result())
                else:
                    self.set_state("o", server_repl.get_result())
                    self.add_to_log(log, com_str, server_repl.get_state_and_result())
                    result_dict, res_dict = (server_repl.get_node_results(), {})
                    for dev in self.devs:
                        res_dict.setdefault(result_dict.get(dev, "error array empty (internal error)"), []).append(dev)
                    if log:
                        for key, value in res_dict.iteritems():
                            if key is None:
                                key = "error key is None"
                            try:
                                compr_list = logging_tools.compress_list(sorted(value))
                            except:
                                compr_list = ", ".join(sorted(value))
                            self.add_to_log(log, " - %s" % (value), key)
    def __repr__(self):
        return "%s to %s on %s (port %d, %s), %s (%s)" % (
            self.command,
            self.config,
            self.hostname,
            self.port,
            "TCP" if self.srv_type == "T" else "0MQ",
            self.get_state(),
            self.get_return())

def iterate_s_commands(s_list, log=None, **kwargs):
    if s_list:
        target_list = [target for target in s_list if target.get_state() != "e"]
        tcp_list = [target for target in target_list if target.srv_type == "T"]
        if tcp_list:
            # build dict
            res_dict = net_tools.multiple_connections(save_logs=True, target_list=target_list, timeout=kwargs.get("timeout", 30)).iterate()
            for idx, act_command in enumerate(target_list):
                res_stuff = res_dict[idx]
                act_command.set_result((res_stuff["errnum"], res_stuff["ret_str"]), log)
        zmq_list = [target for target in target_list if target.srv_type == "0"]
        if zmq_list:
            # iterate
            for zmq_command in zmq_list:
                result = net_tools.zmq_connection("%s:wfe" % (process_tools.get_machine_name()),
                                                  timeout=kwargs.get("timeout", 30)).add_connection(zmq_command.get_conn_str(), zmq_command.server_com)
                #print len(unicode(result))
                zmq_command.set_0mq_result(result)
        
def get_user_list(dc, idxs, all_flag=False):
    if idxs == []:
        if all_flag:
            dc.execute("SELECT * FROM user")
            user_dict = dict([(x["user_idx"], x) for x in dc.fetchall()])
        else:
            user_dict = {}
    else:
        dc.execute("SELECT * FROM user WHERE %s" % (" OR ".join(["user_idx=%d" % (x) for x in idxs])))
        user_dict = dict([(x["user_idx"], x) for x in dc.fetchall()])
    return user_dict

def get_partition_dict(dc):
    pt_parts = ["partition_table_idx", "name", "description", "valid", "modify_bootloader"]
    pd_parts = ["partition_disc_idx", "disc"]
    p_parts  = ["partition_idx", "mountpoint", "partition_fs", "partition_hex", "size", "mount_options", "pnum", "bootable", "fs_freq", "fs_passno"]
    sys_parts = ["name", "mountpoint", "mount_options"]
    dc.execute("SELECT %s, %s, %s FROM partition_table pt LEFT JOIN partition_disc pd ON pd.partition_table=pt.partition_table_idx " % (",".join(["pt.%s" % (x) for x in pt_parts]),
                                                                                                                                        ",".join(["pd.%s" % (x) for x in pd_parts]),
                                                                                                                                        ",".join(["p.%s" % (x) for x in p_parts])) +
               "LEFT JOIN partition p ON p.partition_disc=pd.partition_disc_idx ORDER BY pt.name, pd.disc, p.pnum")
    pt = ordered_dict()
    act_idx = 0
    for db_rec in dc.fetchall():
        pt_idx, pd_idx, p_idx = (db_rec["partition_table_idx"], db_rec["partition_disc_idx"], db_rec["pnum"])
        if not pt.has_key(pt_idx):
            pt[pt_idx] = dict([(y, db_rec[y]) for y in pt_parts] + [("discs", {}), ("num_partitions", 0), ("sys_partitions", {}), ("tot_size", 0)])
        if db_rec["disc"]:
            if not pt[pt_idx]["discs"].has_key(pd_idx):
                pt[pt_idx]["discs"][pd_idx] = dict([(y, db_rec[y]) for y in pd_parts] + [("partitions", {}), ("tot_size", 0)])
            if db_rec["pnum"]:
                if not pt[pt_idx]["discs"][pd_idx].has_key(p_idx):
                    pt[pt_idx]["num_partitions"] += 1
                    pt[pt_idx]["tot_size"] += db_rec["size"]
                    pt[pt_idx]["discs"][pd_idx]["tot_size"] += db_rec["size"]
                    pt[pt_idx]["discs"][pd_idx]["partitions"][p_idx] = dict([(y, db_rec[y]) for y in p_parts])
    dc.execute("SELECT sp.* FROM sys_partition sp")
    for db_rec in dc.fetchall():
        pt_idx, sys_idx = (db_rec["partition_table"], db_rec["sys_partition_idx"])
        if pt.has_key(pt_idx):
            pt[pt_idx]["sys_partitions"][sys_idx] = dict([(y, db_rec[y]) for y in sys_parts])
    return pt

def get_network_dict(dc):
    dc.execute("SELECT n.*, nt.identifier AS ntident, ndt.network_device_type FROM " + \
               "network n INNER JOIN network_type nt LEFT JOIN network_network_device_type ndt ON ndt.network=n.network_idx WHERE " + \
               "nt.network_type_idx=n.network_type ORDER BY n.identifier ASC")
    act_dict = get_ordered_dict(dc, "network_idx", "network_device_types", "network_device_type")
    generate_network_info_strings(act_dict)
    return act_dict

def get_network_device_type_dict(dc):
    dc.execute("SELECT nt.* FROM network_device_type nt ORDER BY nt.description")
    return get_ordered_dict(dc, "network_device_type_idx")

def get_network_type_dict(dc):
    dc.execute("SELECT nt.* FROM network_type nt ORDER BY nt.description")
    return get_ordered_dict(dc, "network_type_idx")
    
def get_image_dict(dc):
    dc.execute("SELECT i.*, DATE_FORMAT(i.date,'%e. %b %Y %H:%i:%s') AS odate FROM image i ORDER BY i.name")
    return get_ordered_dict(dc, "image_idx")

def get_all_device_types(dc):
    dc.execute("SELECT * FROM device_type ORDER BY identifier")
    return get_ordered_dict(dc, "device_type_idx")

def get_snmp_class_dict(dc):
    dc.execute("SELECT s.* FROM snmp_class s ORDER BY s.name")
    return get_ordered_dict(dc, "snmp_class_idx")

def generate_network_info_strings(act_dict):
    for idx, stuff in act_dict.iteritems():
        nw_mask = {"255.255.255.0" : "C",
                   "255.255.0.0"   : "B",
                   "255.0.0.0"     : "A"}.get(stuff["netmask"], None)
        if not nw_mask:
            nw_mask = "%d" % (ipvx_tools.ipv4(stuff["netmask"]).netmask_bits())
        stuff["nw_info"] = "%s (%s) %s / %s" % (stuff["identifier"],
                                                stuff["ntident"],
                                                stuff["network"],
                                                nw_mask)
        # use counter
        stuff["usecount"] = 0
        
def get_device_location_dict(dc):
    dc.execute("SELECT l.* FROM device_location l ORDER BY l.location")
    return get_ordered_dict(dc, "device_location_idx")
    
def get_device_class_dict(dc):
    dc.execute("SELECT c.* FROM device_class c ORDER BY c.classname")
    return get_ordered_dict(dc, "device_class_idx")
    
def get_ordered_dict(dc, idx_str, sub_list=None, sub_add=None):
    act_dict = ordered_dict()
    for db_rec in dc.fetchall():
        idx = db_rec[idx_str]
        if not act_dict.has_key(idx):
            if sub_list:
                db_rec[sub_list] = []
            act_dict[idx] = dict([(y, db_rec[y]) for y in db_rec.keys()])
        if sub_add and db_rec[sub_add]:
            act_dict[idx][sub_list].append(db_rec[sub_add])
    return act_dict

def get_ng_service_templates(dc):
    dc.execute("SELECT nst.* FROM ng_service_templ nst ORDER BY nst.name")
    return get_ordered_dict(dc, "ng_service_templ_idx")

class ng_check_command_types(object):
    def __init__(self, dc, change_log=None):
        needed_types = ["services", "hw/temp", "hw/fan", "network", "memory", "disk/df", "disk/hw", "other", "cpu/mb", "load", "uptime"]
        dc.execute("SELECT nct.* FROM ng_check_command_type nct")
        self.__dict, self.__name_list = ({}, [])
        self._add_from_db(dc)
        # check for missing
        mis_names = [name for name in needed_types if not name in self.__name_list]
        found_names = [name for name in needed_types if name in self.__name_list]
        if mis_names:
            if change_log:
                # add log if present
                change_log.add_ok("Adding %d nagios_check_command_types" % (len(mis_names)), "ok")
            # add missing entries
            sql_str = "INSERT INTO ng_check_command_type VALUES%s" % (",".join(["(0,'%s',null)" % (name) for name in mis_names]))
            dc.execute(sql_str)
            if found_names:
                # fetch missing from db
                dc.execute("SELECT * FROM ng_check_command_type nct WHERE %s" % (" OR ".join(["nct.name='%s'" % (name) for name in mis_names])))
            else:
                # fetch all
                dc.execute("SELECT * FROM ng_check_command_type nct")
            self._add_from_db(dc)
            if not found_names:
                # check all references
                self._check_references(dc)
        else:
            self._check_references(dc)
    def _add_from_db(self, dc):
        for db_rec in dc.fetchall():
            self.__dict[db_rec["ng_check_command_type_idx"]] = db_rec
            self.__dict[db_rec["name"]] = db_rec
            self.__name_list.append(db_rec["name"])
        self.__name_list.sort()
    def _check_references(self, dc):
        dc.execute("SELECT nc.ng_check_command_idx, nc.command_line, nc.name, nc.description, nc.ng_check_command_type FROM ng_check_command nc")
        ng_cc_dict = dict([(db_rec["ng_check_command_idx"], db_rec) for db_rec in dc.fetchall()])
        for ng_idx, ng_stuff in ng_cc_dict.iteritems():
            com_line = ng_stuff["command_line"].lower()
            name = ng_stuff["name"].lower()
            if [True for c_name in ["disc", "disk", "hda"] if name.count(c_name)]:
                t_type = "disk/df"
            elif [True for c_name in ["gdth", "3ware", "icp", "threeware", "smart"] if name.count(c_name)]:
                t_type = "disk/hw"
            elif [True for c_name in ["net"] if name.count(c_name)]:
                t_type = "network"
            elif com_line.count("sensor"):
                if [True for c_name in ["fan"] if com_line.count(c_name)]:
                    t_type = "hw/fan"
                elif [True for c_name in ["temp"] if com_line.count(c_name)]:
                    t_type = "hw/temp"
            elif [True for c_name in ["load"] if name.count(c_name) and not name.lower().count("usv")]:
                t_type = "load"
            elif [True for c_name in ["mem", "swap"] if name.count(c_name)]:
                t_type = "memory"
            elif [True for c_name in ["uptime"] if name.count(c_name)]:
                t_type = "uptime"
            else:
                t_type = "services"
            if not ng_stuff["ng_check_command_type"]:
                if ng_stuff["ng_check_command_type"] != self[t_type]["ng_check_command_type_idx"]:
                    dc.execute("UPDATE ng_check_command SET ng_check_command_type=%d WHERE ng_check_command_idx=%d" % (self[t_type]["ng_check_command_type_idx"],
                                                                                                                       ng_idx))
    def __getitem__(self, key):
        return self.__dict[key]
    def keys(self):
        return self.__dict.keys()
    def iteritems(self):
        for name in self.__name_list:
            yield self[name]["ng_check_command_type_idx"], self[name]
    def get(self, key, default):
        return self.__dict.get(key, default)

def get_new_config_types(dc):
    dc.execute("SELECT nct.* FROM new_config_type nct ORDER BY nct.name")
    return get_ordered_dict(dc, "new_config_type_idx")

def get_snmp_mibs(dc):
    dc.execute("SELECT s.* FROM snmp_mib s ORDER BY s.name")
    return get_ordered_dict(dc, "snmp_mib_idx")

def get_new_configs(dc):
    dc.execute("SELECT nc.* FROM new_config nc ORDER BY nc.name")
    return get_ordered_dict(dc, "new_config_idx")

def get_device_selection_lists(dc, user_idx):
    dc.execute("SELECT ds.device_selection_idx, ds.name, ds.user, dds.device FROM " + \
               "device_selection ds LEFT JOIN device_device_selection dds ON dds.device_selection=ds.device_selection_idx AND " + \
               "(ds.user=%d OR ds.user=0) ORDER BY ds.name" % (user_idx))
    act_dict = get_ordered_dict(dc, "device_selection_idx", "devices", "device")
    generate_device_selection_info_strings(act_dict) 
    return act_dict

def get_nagios_periods(dc):
    dc.execute("SELECT np.* FROM ng_period np ORDER BY np.name")
    return get_ordered_dict(dc, "ng_period_idx")

def get_nagios_contact_groups(dc):
    dc.execute("SELECT ng.* FROM ng_contactgroup ng ORDER BY ng.name")
    return get_ordered_dict(dc, "ng_contactgroup_idx")

def get_nagios_contacts(dc):
    dc.execute("SELECT c.*, u.login, u.useremail FROM ng_contact c, user u WHERE c.user=u.user_idx ORDER BY u.login")
    act_dict = get_ordered_dict(dc, "ng_contact_idx")
    return act_dict

def get_nagios_ext_hosts(dc):
    dc.execute("SELECT n.* FROM ng_ext_host n ORDER BY n.name")
    return get_ordered_dict(dc, "ng_ext_host_idx")

def get_nagios_service_templates(dc):
    dc.execute("SELECT nt.* FROM ng_service_templ nt ORDER BY nt.name")
    return get_ordered_dict(dc, "ng_service_templ_idx")

def get_nagios_device_templates(dc):
    dc.execute("SELECT nd.* FROM ng_device_templ nd ORDER BY nd.name")
    return get_ordered_dict(dc, "ng_device_templ_idx")

def generate_device_selection_info_strings(act_dict):
    for idx, stuff in act_dict.iteritems():
        stuff["info"] = "%s (%s, %s)" % (stuff["name"],
                                         stuff["user"] and "private" or "public",
                                         logging_tools.get_plural("device", len(stuff["devices"])))

def get_netdevice_speed(dc):
    dc.execute("SELECT ns.* FROM netdevice_speed ns ORDER BY ns.speed_bps")
    # speed, check, duplex
    missing_speeds = [(10000000    , 0, 1),
                      (100000000   , 1, 1),
                      (100000000   , 0, 1),
                      (1000000000  , 1, 1),
                      (1000000000  , 0, 1),
                      (10000000000 , 1, 1),
                      (10000000000 , 0, 1)]
    for db_rec in dc.fetchall():
        act_tuple = (db_rec["speed_bps"],
                     db_rec["check_via_ethtool"],
                     db_rec["full_duplex"])
        if act_tuple in missing_speeds:
            missing_speeds.remove(act_tuple)
    if missing_speeds:
        dc.execute("INSERT INTO netdevice_speed VALUES%s" % (",".join(["(0, %d, %d, %d, null)" % (speed, cva, dplx) for speed, cva, dplx in missing_speeds])))
    dc.execute("SELECT ns.* FROM netdevice_speed ns ORDER BY ns.speed_bps")
    return get_ordered_dict(dc, "netdevice_speed_idx")
    
def get_all_log_sources(dc):
    dc.execute("SELECT l.* FROM log_source l ORDER BY l.identifier")
    return get_ordered_dict(dc, "log_source_idx")

def init_log_and_status_fields(req):
    req.log_source, req.log_status = (process_tools.get_all_log_sources(req.dc),
                                      process_tools.get_all_log_status(req.dc))
    if req.log_source:
        req.log_source_lut = dict([(x["log_source_idx"], x) for x in req.log_source.itervalues() if type(x) != type([])] +
                                  [(x["log_source_idx"], x) for x in reduce(lambda a, b : a + b, [y for y in req.log_source.itervalues() if type(y) == type([])], [])])
    else:
        req.log_source_lut = {}
    if req.log_status:
        req.log_status_lut = dict([(x["log_status_idx"], x) for x in req.log_status.itervalues()])
    else:
        req.log_status_lut = { }

def signal_yp_ldap_server(req, action_log):
    if req.conf["server"].has_key("yp_server") or req.conf["server"].has_key("ldap_server"):
        if req.conf["server"].has_key("yp_server"):
            iterate_s_commands([s_command(req, "yp_server", 8004, "write_yp_config", [], 20)], action_log)
        if req.conf["server"].has_key("ldap_server"):
            iterate_s_commands([s_command(req, "ldap_server", 8004, "sync_ldap_config", [], 20)], action_log)
    else:
        action_log.add_warn("No YP or LDAP Server defined", "missing")
        
def signal_nagios_config_server(req, action_log):
    if req.conf["server"].has_key("nagios_master"):
        iterate_s_commands([s_command(req, "nagios_master", 8010, "rebuild_host_config", [], 20)], action_log)
    else:
        action_log.add_warn("No Nagios-Server defined", "missing")
        
def signal_package_servers(req, action_log):
    if req.conf["server"].has_key("package_server"):
        iterate_s_commands([s_command(req, "package_server", 8007, "new_rsync_server_config", [], 20, x) for x in req.conf["server"]["package_server"].keys()], action_log)
        
def rebuild_hopcount(req, change_log, rebuild_hc_causes):
    ss_list = []
    server_list = req.conf["server"]
    server_list = server_list.get("server", [])
    if server_list:
        req.dc.execute("SELECT d.name FROM device d INNER JOIN device_config dc INNER JOIN new_config c INNER JOIN device_group dg " + \
                       "LEFT JOIN device d2 ON (d2.device_group=dg.device_group_idx AND d2.device_idx=dg.device) WHERE " + \
                       "dc.new_config AND d.device_group=dg.device_group_idx AND (dc.device=d.device_idx OR dc.device=d2.device_idx) " + \
                       "AND dc.new_config=c.new_config_idx AND c.name='rebuild_hopcount' AND (%s)" % (" OR ".join(["d.name='%s'" % (x) for x in server_list.keys()])))
        reb_servers = req.dc.fetchall()
        if reb_servers:
            reb_server = reb_servers[0]["name"]
            ss_list.append(s_command(req, "server", 8004, "rebuild_hopcount", [], 60, reb_server))
            change_log.add_warn("Rebuilding hopcount table (server %s, cause: %s)" % (reb_server, ",".join(rebuild_hc_causes.keys())), "SQL")
        else:
            change_log.add_error("unable to rebuild hopcount table (no server with rebuild_hopcount found)", "no servers found")
    else:
        change_log.add_error("unable to rebuild hopcount table", "no servers found")
    return ss_list

def rebuild_etc_hosts(req, change_log, rebuild_eh_causes):
    ss_list = []
    server_list = req.conf["server"]
    server_list = server_list.get("server", [])
    if server_list:
        req.dc.execute("SELECT d.name FROM device d INNER JOIN device_config dc INNER JOIN new_config c INNER JOIN " + \
                       "device_group dg LEFT JOIN device d2 ON (d2.device_group=dg.device_group_idx AND d2.device_idx=dg.device) " + \
                       "WHERE dc.new_config AND d.device_group=dg.device_group_idx AND (dc.device=d.device_idx OR dc.device=d2.device_idx) " + \
                       "AND dc.new_config=c.new_config_idx AND c.name='auto_etc_hosts' AND (%s)" % (" OR ".join(["d.name='%s'" % (x) for x in server_list.keys()])))
        reb_servers = req.dc.fetchall()
        if reb_servers:
            ss_list.extend([s_command(req, "server", 8004, "write_etc_hosts", [], 60, x["name"]) for x in reb_servers])
            change_log.add_warn("Writing etc_hosts (%s %s, cause: %s)" % (logging_tools.get_plural("server", len(reb_servers)),
                                                                          ", ".join([x["name"] for x in reb_servers]),
                                                                          ", ".join(rebuild_eh_causes.keys())), "SQL")
        else:
            change_log.add_error("unable to write /etc/hosts files (no server with auto_etc_hosts found)", "no servers found")
    else:
        change_log.add_error("unable to write /etc/hosts file", "no servers found")
    return ss_list

class boot_server_struct(object):
    def __init__(self, dc, c_log, **args):
        self.__bs_dict = {}
        if args.get("add_zero_entry", False):
            self._add_bs(0, "no bootserver")
        dc.execute("SELECT d.name, d.device_idx, nt.identifier FROM device d INNER JOIN new_config c INNER JOIN device_config dc INNER JOIN netip i INNER JOIN network nw INNER JOIN network_type nt INNER JOIN netdevice n INNER JOIN device_group dg LEFT JOIN device d2 ON d2.device_idx=dg.device LEFT JOIN device_type dt ON (d2.device_type=dt.device_type_idx AND dt.identifier='MD') WHERE d.device_group=dg.device_group_idx AND (dc.device=d.device_idx OR dc.device=d2.device_idx) AND dc.new_config=c.new_config_idx AND c.name='server' AND n.device=d.device_idx AND i.netdevice=n.netdevice_idx AND i.network=nw.network_idx AND nw.network_type=nt.network_type_idx AND (nt.identifier='b' OR nt.identifier='p') ORDER BY d.name")
        all_servers = dc.fetchall()
        for nt_id in ["b", "p"]:
            bs_found = 0
            for db_rec in all_servers:
                if db_rec["identifier"] == nt_id:
                    bs_found += 1
                    self._add_bs(db_rec["device_idx"], db_rec["name"])
            if nt_id == "p" and bs_found:
                c_log.add_warn("No bootservers found in boot-network, found %s in production network" % (bs_found),
                               "config warn")
            if bs_found:
                break
    def _add_bs(self, idx, name):
        self.__bs_dict[idx] = name
        self.__bs_dict[name] = idx
    def __getitem__(self, key):
        return self.__bs_dict[key]
    def keys(self):
        return self.__bs_dict.keys()
    def has_key(self, key):
        return self.__bs_dict.has_key(key)
    def get_names(self):
        return [self[key] for key in self.get_idxs() if not key] + sorted([self[key] for key in self.get_idxs() if key])
    def get_idxs(self):
        return sorted([key for key in self.__bs_dict.keys() if type(key) in [type(0), type(0L)]])

if __name__ == "__main__":
    print "Loadable module, exiting ..."
    sys.exit(0)
