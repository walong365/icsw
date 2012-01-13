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
""" to modify configs """

import functions
import logging_tools
import html_tools
import tools
import time
import re
import sys
import traceback
import cdef_config
import difflib
import cPickle
import sub_clusterconfig_show_device_config
import server_command
import cgi
import pprint

# dummy traceback container
class tb_container(object):
    def __init__(self):
        self.content = ""
    def write(self, what):
        self.content += what
    def get_content(self):
        return self.content

def show_device_config(req, dev_tree, devg_dict, dev_dict, sub_sel_1, sub_sel_2):
    dg_sel, d_sel, dg_sel_eff = dev_tree.get_selection()
    low_submit = html_tools.checkbox(req, "sub")
    sub = low_submit.check_selection("")
    cts = tools.get_new_config_types(req.dc)
    cs  = tools.get_new_configs(req.dc)
    change_log = html_tools.message_log()
    # show list
    ct_show_list = html_tools.selection_list(req, "ctd", {0: "all types"}, multiple=1, size=2)
    for ct_idx, ct_stuff in cts.iteritems():
        ct_show_list[ct_idx] = ct_stuff["name"]
    saved_re        = req.user_info.get_user_var_value("_sdc_re", "")
    saved_show_list = req.user_info.get_user_var_value("_sdc_sl", [0])
    ct_shows = ct_show_list.check_selection("", saved_show_list)
    req.user_info.modify_user_var("_sdc_sl", ct_shows)
    if ct_shows == [0] or ct_shows == []:
        ct_shows = [x for x in cts.keys()]
    # show info?
    show_info_button = html_tools.checkbox(req, "si")
    show_info = show_info_button.check_selection()
    #req.user_info
    # regexp
    c_regexp = html_tools.text_field(req, "cre", size=64, display_len=8)
    sel_button = html_tools.checkbox(req, "sos")
    saved_only_selected = req.user_info.get_user_var_value("_sdc_os", 0)
    only_selected = sel_button.check_selection("", not sub and saved_only_selected)
    act_c_regexps = c_regexp.check_selection("", saved_re).split(",")
    req.user_info.modify_user_var("_sdc_re", ",".join(act_c_regexps))
    req.user_info.modify_user_var("_sdc_os", only_selected)
    regexp_list = []
    for act_c_regexp in act_c_regexps:
        if act_c_regexp.startswith("!"):
            c_re_exclude = 1
            act_c_regexp = act_c_regexp[1:]
        else:
            c_re_exclude = 0
        try:
            c_re = re.compile(".*%s" % (act_c_regexp))
        except:
            c_re = re.compile(".*")
        else:
            pass
        regexp_list.append((c_re_exclude, c_re))
    # build all config buttons
    cb_dict, cr_dict, cr_com, cr_sel = (tools.ordered_dict(),
                                        tools.ordered_dict(),
                                        {},
                                        {})
    for idx, stuff in cs.iteritems():
        if stuff["new_config_type"] in ct_shows or only_selected:
            re_show, tot_count, show_count, rem_count, pos_count = (1, 0, 0, 0, 0)
            if only_selected:
                re_show = 1
            else:
                for c_re_exclude, c_re in regexp_list:
                    tot_count += 1
                    if not c_re_exclude:
                        pos_count += 1
                        if c_re.match(stuff["name"]):
                            show_count += 1
                    if c_re_exclude and c_re.match(stuff["name"]):
                        rem_count += 1
                if show_count and not rem_count:
                    re_show = 1
                elif not pos_count and not rem_count:
                    re_show = 1
                else:
                    re_show = 0
            if re_show:
                cb_dict[idx] = html_tools.checkbox(req, "c%dc" % (idx))
                cr_dict[idx] = html_tools.radio_list(req, "c%dr" % (idx), {"0n" : {},
                                                                           "1s" : {},
                                                                           "2d" : {}}, auto_reset=1)
                cr_com[idx] = cr_dict[idx].check_selection("g", "0n")
                cr_sel[idx] = html_tools.checkbox(req, "cs%dc" % (idx))
    # fetch device_configs for device_group meta_devices
    meta_dict = dict([(devg_dict[x].get_meta_device_idx(), x) for x in dg_sel_eff if devg_dict[x].has_meta_device()])
    meta_lut  = dict([(x, devg_dict[x].get_meta_device_idx()) for x in dg_sel_eff if devg_dict[x].has_meta_device()])
    if meta_dict:
        req.dc.execute("SELECT dc.* FROM device_config dc WHERE (%s)" % (" OR ".join(["dc.device=%d" % (x) for x in meta_dict.keys()])))
        for db_rec in req.dc.fetchall():
            if db_rec["new_config"] in cs.keys():
                devg_dict[meta_dict[db_rec["device"]]].add_config(db_rec["new_config"])
    # fetch device_configs
    req.dc.execute("SELECT dc.* FROM device_config dc WHERE (%s)" % (" OR ".join(["dc.device=%d" % (x) for x in d_sel])))
    for db_rec in req.dc.fetchall():
        if db_rec["new_config"] in cs.keys():
            dev_dict[db_rec["device"]].add_config(db_rec["new_config"])
    # delete configs not used if flag is set
    if only_selected:
        confs_act_used = []
        for dg_idx in [x for x in dev_tree.get_sorted_devg_idx_list() if x in dg_sel_eff]:
            if sub_sel_1 in ["o0", "o1"]:
                act_dg = devg_dict[dg_idx]
                for conf in act_dg.configs:
                    if conf not in confs_act_used:
                        confs_act_used.append(conf)
            if sub_sel_1 in ["o0", "o2"]:
                for d_idx in [y for y in dev_tree.get_sorted_dev_idx_list(dg_idx) if y in d_sel]:
                    act_d = dev_dict[d_idx]
                    for conf in act_d.configs:
                        if conf not in confs_act_used:
                            confs_act_used.append(conf)
        del_conf_idxs = [x for x in cs.keys() if x not in confs_act_used]
        for del_conf in del_conf_idxs:
            del cb_dict[del_conf]
            del cr_dict[del_conf]
            del cr_com[del_conf]
            del cr_sel[del_conf]
    # list of config_names changed
    change_list = []
    dev_conf_changed = False
    del_list, set_list = ([], [])
    for dg_idx in [x for x in dev_tree.get_sorted_devg_idx_list() if x in dg_sel_eff]:
        act_dg = devg_dict[dg_idx]
        meta_dev_idx = meta_lut.get(dg_idx, None)
        # possible state changes (gs...group set, gn...group not set, ds...device set, dn...device not set):
        # cn ... casenumber
        # cn old state new state action
        #  1 gn/dn     gn/dn     -
        #  2 gn/dn     gn/ds     set device
        #  3 gn/dn     gs/dn     set group; delete all devices
        #  4 gn/dn     gs/ds     set group; delete all devices
        #  5 gn/ds     gn/dn     delete device
        #  6 gn/ds     gn/ds     -
        #  7 gn/ds     gs/dn     set group, delete all devices
        #  8 gn/ds     gs/ds     set group, delete all devices
        #  9 gs/dn     gn/dn     delete group
        # 10 gs/dn     gn/ds     delete group and all devices; set local device
        # 11 gs/dn     gs/dn     -
        # 12 gs/dn     gs/ds     -
        # 13 gs/ds     gn/dn     invalid old_state, delete group
        # 14 gs/ds     gn/ds     invalid old_state, delete group, set local device
        # 15 gs/ds     gs/dn     invalid old_state, delete local device
        # 16 gs/ds     gs/ds     invalid old_state, delete local device
        super_s_dict, super_add, super_del = ({}, [], [])
        for idx, item in cb_dict.iteritems():
            if sub_sel_1 in ["o0", "o1"]:
                was_set = act_dg.has_config(idx)
                is_set = item.check_selection(act_dg.get_suffix(), was_set and (not (sub and cr_sel[idx].check_selection("g"))))
                if sub_sel_1 == "o1":
                    if cr_com[idx] == "1s" and not is_set:
                        is_set = 1
                        item[act_dg.get_suffix()] = is_set
                    elif cr_com[idx] == "2d" and is_set:
                        is_set = 0
                        item[act_dg.get_suffix()] = is_set
                # the following lines are commented out in order to disable the setting the devicegroup properties from the global settings
                #if cr_com[idx] == "s" and not is_set:
                #    is_set=1
                #    item.reset_selection(act_dg.get_suffix(), is_set)
                #elif cr_com[idx] == "d" and is_set:
                #    is_set=0
                #    item.reset_selection(act_dg.get_suffix(), is_set)
                if is_set and not was_set:
                    # handles cn 3, 4, 7, 8
                    if meta_dev_idx is not None:
                        set_list.append((meta_dev_idx, idx))
                    act_dg.add_config(idx)
                    super_add.append(idx)
                elif was_set and not is_set:
                    # handles cn 9, 10, 13, 14
                    if meta_dev_idx is not None:
                        del_list.append((meta_dev_idx, idx))
                    act_dg.del_config(idx)
                    super_del.append(idx)
            super_s_dict[idx] = act_dg.has_config(idx)
        if super_add:
            dev_list = dev_tree.get_sorted_dev_idx_list(dg_idx)
            if dev_list:
                dev_conf_changed = True
                sql_str = "DELETE FROM device_config WHERE (%s) AND (%s)" % (" OR ".join(["new_config=%d" % (x) for x in super_add]),
                                                                             " OR ".join(["device=%d" % (x) for x in dev_list]))
                change_list.extend([cs[x]["name"] for x in super_add])
                req.dc.execute(sql_str)
        for d_idx in [y for y in dev_tree.get_sorted_dev_idx_list(dg_idx) if y in d_sel]:
            act_d = dev_dict[d_idx]
            if sub_sel_1 in ["o0", "o2"]:
                for idx, item in cb_dict.iteritems():
                    was_set = act_d.has_config(idx)
                    is_set = item.check_selection(act_d.get_suffix(), was_set and (not (sub and cr_sel[idx].check_selection("g"))))
                    if cr_com[idx] == "1s" and not is_set:
                        is_set = 1
                        item[act_d.get_suffix()] = is_set
                    elif cr_com[idx] == "2d" and is_set:
                        is_set = 0
                        item[act_d.get_suffix()] = is_set
                    if super_s_dict[idx]:
                        # handles cn 3, 4, 7, 8, 11, 12, 15, 16
                        if was_set:
                            if not idx in super_add:
                                print "Error", idx
                            act_d.del_config(idx)
                        item[act_d.get_suffix()] = 1
                    else:
                        if is_set and not was_set:
                            if idx not in super_del:
                                # handles cn 2, 10
                                set_list.append((d_idx, idx))
                                act_d.add_config(idx)
                        elif was_set and not is_set:
                            # handles cn 5, 13
                            del_list.append((d_idx, idx))
                            act_d.del_config(idx)
                        item[act_d.get_suffix()] = act_d.has_config(idx) or super_s_dict[idx]
    #if set_list or del_list:
    #    print "set : ", set_list
    #    print "del : ", del_list
    if set_list:
        dev_conf_changed = True
        sql_str = "INSERT INTO device_config VALUES%s" % (",".join(["(0,%d,%d, null)" % (x, y) for x, y in set_list]))
        change_list.extend([cs[y]["name"] for x, y in set_list])
        req.dc.execute(sql_str)
    if del_list:
        dev_conf_changed = True
        sql_str = "DELETE FROM device_config WHERE %s" % (" OR ".join(["(device=%d AND new_config=%d)" % (x, y) for x, y in del_list]))
        change_list.extend([cs[y]["name"] for x, y in del_list])
        req.dc.execute(sql_str)
    change_list = dict([(x, True) for x in change_list]).keys()
    # check for rsync changes
    if [True for x in change_list if x.count("rsync")]:
        tools.signal_package_servers(req, change_log)
    low_submit[""] = 1
    if dev_conf_changed:
        req.write(html_tools.gen_hline("config changed, forcing to rebuild server_connection_dict", 2))
        if req.session_data.has_property("server_routes"):
            req.session_data.del_property("server_routes")
        req.session_data.set_property("signal_other_sessions", 1)
        tools.signal_nagios_config_server(req, change_log)
    for idx, item in cr_sel.iteritems():
        item["g"] = 1
        req.write("%s\n" % (item.create_hidden_var("g")))
    out_table = html_tools.html_table(cls="normal")
    srv_dict = sub_clusterconfig_show_device_config.create_config(req, dev_tree, dev_dict, change_log, sub_sel_2)
    req.write(change_log.generate_stack("Action log"))
    sub_clusterconfig_show_device_config.show_config(req, dev_tree, dev_dict, srv_dict, sub_sel_2, [cs[x]["name"] for x in cb_dict.keys()])
    
    req.write("%s%s" % (html_tools.gen_hline("Device config", 2),
                        out_table.get_header()))
    row_count = show_info and 3 or 4
    if cb_dict:
        num_lines = int((len(cb_dict.keys()) + row_count - 1) / row_count)
    else:
        num_lines = 0
    # recalculate row_count
    if num_lines:
        row_count = int((len(cb_dict.keys()) + num_lines - 1) / num_lines)
    num_out = 0
    for dg_idx in [x for x in dev_tree.get_sorted_devg_idx_list() if x in dg_sel_eff]:
        act_dg = devg_dict[dg_idx]
        out_table[0]["class"] = "lineh"
        out_table[None][0 : 2 * row_count] = html_tools.content(dev_tree.get_sel_dev_str(dg_idx), cls="devgroup")
        req.write(out_table.flush_lines(act_dg.get_suffix()))
        super_s_dict = {}
        if act_dg.has_meta_device():
            for idx, item in cb_dict.iteritems():
                super_s_dict[idx] = act_dg.has_config(idx)
        else:
            for idx, item in cb_dict.iteritems():
                super_s_dict[idx] = 0
        if sub_sel_1 in ["o0", "o1"]:
            if act_dg.has_meta_device():
                if num_lines:
                    num_out += 1
                    #super_s_dict = {}
                    out_table[1]["class"] = "line01"
                    s_num_global = act_dg.get_num_configs(cb_dict.keys())
                    t_num_global = act_dg.get_num_configs(cs.keys())
                    out_table[None][0 : 2 * row_count] = html_tools.content("Group selection: %d of %d shown, %s selected, not shown: %s selected [total : %s]" % (len(cb_dict.keys()),
                                                                                                                                                                   len(cs.keys()),
                                                                                                                                                                   s_num_global and "%d" % (s_num_global) or "none",
                                                                                                                                                                   t_num_global - s_num_global and "%d" % (t_num_global - s_num_global) or "none",
                                                                                                                                                                   t_num_global and "%d" % (t_num_global) or "none"),
                                                                            cls="left")
                    line_idx, row_idx = (2, 1)
                    for idx, item in cb_dict.iteritems():
                        #super_s_dict[idx] = act_dg.has_config(idx)
                        if row_idx == 1:
                            out_table[line_idx]["class"] = "line1%d" % (line_idx % 2)
                        if show_info and cs[idx]["description"]:
                            info_str = " (%s)" % (cs[idx]["description"])
                        else:
                            info_str = ""
                        out_table[line_idx][row_idx] = html_tools.content("%s%s:" % (cs[idx]["name"], info_str), cls="right")
                        out_table[None][0] = html_tools.content(item, cls="left")
                        line_idx += 1
                        if line_idx > num_lines + 1:
                            line_idx = 2
                            row_idx += 2
                    if line_idx <= num_lines + 1 and row_idx < 2 * row_count + 1:
                        out_table[line_idx : num_lines + 1][row_idx : 2 * row_count] = html_tools.content("&nbsp;")
            else:
                #super_s_dict = {}
                #for idx, item in cb_dict.iteritems():
                #    super_s_dict[idx] = 0
                out_table[0][0 : 2 * row_count] = html_tools.content("DeviceGroup has no MetaDevice associated", cls="line30")
            req.write(out_table.flush_lines(act_dg.get_suffix()))
        for d_idx in [y for y in dev_tree.get_sorted_dev_idx_list(dg_idx) if y in d_sel]:
            act_d = dev_dict[d_idx]
            if sub_sel_1 in ["o0", "o2"]:
                if num_lines:
                    sub_set = cb_dict.keys()
                    s_num_local  = act_d.get_num_configs(sub_set)
                    s_num_global = act_dg.get_num_configs(sub_set)
                    t_num_local  = act_d.get_num_configs(cs.keys())
                    t_num_global = act_dg.get_num_configs(cs.keys())
                    config_info = "; %d of %s shown, %s local selected (%s from group), not shown: %s local selected (%s from group) [total : %s / %s]" % (len(cb_dict.keys()),
                                                                                                                                                           logging_tools.get_plural("config", len(cs.keys())),
                                                                                                                                                           s_num_local  and "%d" % (s_num_local)  or "none",
                                                                                                                                                           s_num_global and "%d" % (s_num_global) or "none",
                                                                                                                                                           t_num_local - s_num_local  and "%d" % (t_num_local - s_num_local)  or "none",
                                                                                                                                                           t_num_global - s_num_global and "%d" % (t_num_global - s_num_global) or "none",
                                                                                                                                                           t_num_local  and "%d" % (t_num_local)  or "none",
                                                                                                                                                           t_num_global and "%d" % (t_num_global) or "none")
                else:
                    config_info = ""
                out_table[0]["class"] = "line00"
                out_table[None][0 : 2 * row_count] = html_tools.content([act_d.get_name(), config_info])
                req.write(out_table.flush_lines(act_d.get_suffix()))
                if num_lines:
                    num_out += 1
                    line_idx, row_idx = (1, 1)
                    for idx, item in cb_dict.iteritems():
                        if row_idx == 1:
                            out_table[line_idx]["class"] = "line1%d" % (line_idx % 2)
                        if show_info and cs[idx]["description"]:
                            info_str = " (%s)" % (cs[idx]["description"])
                        else:
                            info_str = ""
                        super_str = super_s_dict[idx] and " (*)" or ""
                        out_table[line_idx][row_idx] = html_tools.content("%s%s%s:" % (cs[idx]["name"],
                                                                                       info_str,
                                                                                       super_str), cls="right")
                        out_table[None][0] = html_tools.content(item, cls="left")
                        line_idx += 1
                        if line_idx > num_lines:
                            line_idx = 1
                            row_idx += 2
                    if line_idx <= num_lines and row_idx < 2 * row_count + 1:
                        out_table[line_idx : num_lines][row_idx : 2 * row_count] = html_tools.content("&nbsp;")
                    req.write(out_table.flush_lines(act_d.get_suffix()))
    req.write(out_table.get_footer())
    if num_out > 1:
        out_table = html_tools.html_table(cls="normalsmall")
        req.write("%s%s" % (html_tools.gen_hline("Global settings (%s)" % {"o0" : "for devices",
                                                                           "o1" : "for devicegroups",
                                                                           "o2" : "for devices"}[sub_sel_1], 3),
                            out_table.get_header()))
        out_table[0]["class"] = "lineh"
        for i in range(row_count):
            for what in ["Config", "keep", "set", "del"]:
                out_table[None][0] = html_tools.content(what, cls="center", type="th")
        req.write(out_table.flush_lines())
        line_idx, row_idx = (1, 1)
        for idx, item in cr_dict.iteritems():
            if row_idx == 1:
                out_table[line_idx]["class"] = "line1%d" % (line_idx % 2)
            if show_info and cs[idx]["description"]:
                info_str = " (%s)" % (cs[idx]["description"])
            else:
                info_str = ""
            out_table[line_idx][row_idx] = html_tools.content("%s%s:" % (cs[idx]["name"],
                                                                         info_str), cls="right")
            out_table[None][0] = html_tools.content(item, cls="center")
            out_table[None][0] = html_tools.content(item, cls="center")
            out_table[None][0] = html_tools.content(item, cls="center")
            line_idx += 1
            if line_idx > num_lines:
                line_idx = 1
                row_idx += 4
        if line_idx <= num_lines and row_idx < 4 * row_count + 1:
            out_table[line_idx : num_lines][row_idx : 4 * row_count] = html_tools.content("&nbsp;")
        req.write(out_table.flush_lines("g"))
        req.write(out_table.get_footer())
    submit_button = html_tools.submit_button(req, "submit")
    submit_button.set_class("", "button")
    opt_table = html_tools.html_table(cls="blindsmall")
    opt_table[0][0] = html_tools.content(["Options: show " , ct_show_list,
                                          ", name regexp: ", c_regexp,
                                          ", only selected: ", sel_button,
                                          ",\n show info:" , show_info_button])
    req.write(opt_table(""))
    req.write("%s<div class=\"center\">%s</div>\n" % (low_submit.create_hidden_var(""),
                                                      submit_button("")))
    
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
        
class new_config_vs(html_tools.validate_struct):
    def __init__(self, req, ct_list, mib_list):
        html_tools.validate_struct.__init__(self, req, "config",
                                            {"name"            : {"he"  : html_tools.text_field(req, "cn",  size=64, display_len=20),
                                                                  "new" : 1,
                                                                  "vf"  : self.validate_name,
                                                                  "def" : ""},
                                             "description"     : {"he"  : html_tools.text_field(req, "cd", size=128, display_len=40),
                                                                  "vf"  : self.validate_descr,
                                                                  "def" : "New config"},
                                             "priority"        : {"he"  : html_tools.text_field(req, "cp",   size=6,  display_len=6),
                                                                  "vf"  : self.validate_priority,
                                                                  "def" : 0},
                                             "new_config_type" : {"he"  : ct_list,
                                                                  "vf"  : self.validate_nct,
                                                                  "def" : 0},
                                             "del"             : {"he"  : html_tools.checkbox(req, "cdel", auto_reset=1),
                                                                  "del" : 1},
                                             "snmp_mibs"       : {"he"  : mib_list,
                                                                  "def" : [],
                                                                  "vf"  : self.validate_snmp_mibs}
                                             })
        self.__mib_list = mib_list
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
    def validate_priority(self):
        if not tools.is_number(self.new_val_dict["priority"]):
            raise ValueError, "must be an integer"
        else:
            self.new_val_dict["priority"] = int(self.new_val_dict["priority"])
    def validate_nct(self):
        oi, ni = (int(self.old_val_dict["new_config_type"]),
                  int(self.new_val_dict["new_config_type"]))
        self.old_b_val_dict["new_config_type"] = self.ct_tree.get(oi, {"name" : "key %d not found" % (oi)})["name"]
        self.new_b_val_dict["new_config_type"] = self.ct_tree.get(ni, {"name" : "key %d not found" % (ni)})["name"]
    def validate_snmp_mibs(self):
        def get_list(idx_f):
            if not idx_f:
                return "empty"
            else:
                return ", ".join([self.__mib_list.list_dict.get(x, {"name" : "key %d not found" % (x)})["name"] for x in idx_f])
        self.new_val_dict["snmp_mibs"] = [x for x in self.new_val_dict["snmp_mibs"] if self.__mib_list.list_dict.has_key(x)]
        self.new_val_dict["snmp_mibs"].sort()
        self.old_b_val_dict["snmp_mibs"] = get_list(self.old_val_dict["snmp_mibs"])
        self.new_b_val_dict["snmp_mibs"] = get_list(self.new_val_dict["snmp_mibs"])

class new_config_var_vs(html_tools.validate_struct):
    def __init__(self, req):
        html_tools.validate_struct.__init__(self, req, "config_var",
                                            {"name"            : {"he"  : html_tools.text_field(req, "cvn",  size=64, display_len=30),
                                                                  "new" : 1,
                                                                  "vf"  : self.validate_name,
                                                                  "def" : ""},
                                             "descr"           : {"he"  : html_tools.text_field(req, "cvd", size=255, display_len=30),
                                                                  "def" : "New config var"},
                                             "value"           : {"he"  : html_tools.text_field(req, "cvv",  size=255,  display_len=30),
                                                                  "vf"  : self.validate_value,
                                                                  "def" : ""},
                                             "del"             : {"he"  : html_tools.checkbox(req, "cvl", auto_reset=1),
                                                                  "del" : 1},
                                             "config_str_idx"  : {"ndb" : 1,
                                                                  "def" : 0},
                                             "new_config"      : {"ndb" : 1,
                                                                  "def" : 0}})
    def validate_name(self):
        if self.is_new_object():
            # some dirty stuff because of the three different var_types
            self.copy_instance_args = self.act_type
            self.get_db_obj().set_type(self.act_type)
        if self.new_val_dict["name"] in self.names and self.new_val_dict["name"] != self.old_val_dict["name"]:
            self.new_val_dict["name"] = self.old_val_dict["name"]
            raise ValueError, "already used"
        elif not self.new_val_dict["name"]:
            self.new_val_dict["name"] = self.old_val_dict["name"]
            raise ValueError, "must not be empty"
    def validate_value(self):
        if not self.new_val_dict["value"]:
            raise ValueError, "must not be empty"
        if self.act_type == "bool":
            if tools.is_number(self.new_val_dict["value"].strip()):
                nv = int(self.new_val_dict["value"].strip())
                if nv in [0, 1]:
                    self.new_val_dict["value"] = nv
                else:
                    raise ValueError, "must be in range [0, 1]"
            else:
                raise ValueError, "not an integer"
        elif self.act_type == "int":
            if tools.is_number(self.new_val_dict["value"].strip()):
                self.new_val_dict["value"] = int(self.new_val_dict["value"].strip())
            else:
                raise ValueError, "not an integer"

class new_nagios_vs(html_tools.validate_struct):
    def __init__(self, req, nag_class, ncct_list):
        html_tools.validate_struct.__init__(self, req, "nagios_command",
                                            {"name"                  : {"he"  : html_tools.text_field(req, "cnn",  size=64, display_len=30),
                                                                        "new" : 1,
                                                                        "vf"  : self.validate_name,
                                                                        "def" : ""},
                                             "command_line"          : {"he"  : html_tools.text_field(req, "cnc", size=255, display_len=30),
                                                                        "vf"  : self.validate_command,
                                                                        "def" : ""},
                                             "description"           : {"he"  : html_tools.text_field(req, "cne", size=255, display_len=30),
                                                                        "def" : "New nagios config"},
                                             "ng_service_templ"      : {"he"  : nag_class,
                                                                        "vf"  : self.validate_ngt,
                                                                        "def" : 0},
                                             "ng_check_command_type" : {"he"  : ncct_list,
                                                                        "vf"  : self.validate_nct,
                                                                        "def" : 0},
                                             "del"                   : {"he"  : html_tools.checkbox(req, "cnd", auto_reset=1),
                                                                        "del" : 1},
                                             "ng_check_command_idx"  : {"ndb" : 1,
                                                                        "def" : 0},
                                             "new_config"            : {"ndb" : 1,
                                                                        "def" : 0}})
    def validate_name(self):
        if not self.new_val_dict["name"]:
            self.new_val_dict["name"] = self.old_val_dict["name"]
            raise ValueError, "must not be empty"
    def validate_command(self):
        if not self.new_val_dict["command_line"]:
            raise ValueError, "must not be empty"
    def validate_ngt(self):
        oi, ni = (int(self.old_val_dict["ng_service_templ"]),
                  int(self.new_val_dict["ng_service_templ"]))
        self.old_b_val_dict["ng_service_templ"] = self.ng_service_templates.get(oi, {"name" : "not set"})["name"]
        self.new_b_val_dict["ng_service_templ"] = self.ng_service_templates.get(ni, {"name" : "not set"})["name"]
    def validate_nct(self):
        oi, ni = (int(self.old_val_dict["ng_check_command_type"]),
                  int(self.new_val_dict["ng_check_command_type"]))
        self.old_b_val_dict["ng_check_command_type"] = self.act_ng_check_command_types.get(oi, {"name" : "not set"})["name"]
        self.new_b_val_dict["ng_check_command_type"] = self.act_ng_check_command_types.get(ni, {"name" : "not set"})["name"]

class new_config_script_vs(html_tools.validate_struct):
    def __init__(self, req):
        html_tools.validate_struct.__init__(self, req, "config_script",
                                            {"name"              : {"he"  : html_tools.text_field(req, "csn",  size=64, display_len=30),
                                                                    "new" : 1,
                                                                    "vf"  : self.validate_name,
                                                                    "def" : ""},
                                             "priority"          : {"he"  : html_tools.text_field(req, "csp", size=6, display_len=6),
                                                                    "vf"  : self.validate_priority,
                                                                    "def" : 0},
                                             "descr"             : {"he"  : html_tools.text_field(req, "csd", size=255, display_len=30),
                                                                    "def" : "New config script"},
                                             "c0"                : (self.validate_value, {"value"  : {"he"  : html_tools.text_area(req, "csv", min_col_size=50, max_col_size=120, min_row_size=3, max_row_size=10),
                                                                                                      "def" : ""},
                                                                                          "upload" : {"he"  : html_tools.upload_field(req, "cvu", size=10000, display_len=30),
                                                                                                      "ndb" : 1,
                                                                                                      "def" : ""}}),
                                             "enabled"           : {"he"  : html_tools.checkbox(req, "cse"),
                                                                    "def" : 1},
                                             "del"               : {"he"  : html_tools.checkbox(req, "csl", auto_reset=1),
                                                                    "del" : 1},
                                             "config_script_idx" : {"ndb" : 1,
                                                                    "def" : 0},
                                             "error_text"        : {"ndb" : 1,
                                                                    "def" : ""},
                                             "new_config"        : {"ndb" : 1,
                                                                    "def" : 0}})
    def validate_name(self):
        if self.new_val_dict["name"] in self.names and self.new_val_dict["name"] != self.old_val_dict["name"]:
            self.new_val_dict["name"] = self.old_val_dict["name"]
            raise ValueError, "already used"
        elif not self.new_val_dict["name"]:
            self.new_val_dict["name"] = self.old_val_dict["name"]
            raise ValueError, "must not be empty"
    def validate_priority(self):
        if not tools.is_number(self.new_val_dict["priority"]):
            raise ValueError, "must be an integer"
        else:
            self.new_val_dict["priority"] = int(self.new_val_dict["priority"])
    def validate_value(self):
        if self.new_val_dict["upload"]:
            self.new_val_dict["value"] = self.new_val_dict["upload"]
            self.get_he("value")[self.get_suffix()] = self.new_val_dict["value"]
        # correct \r\n line endings from web
        pre_lines, post_lines = ("\n".join([x.strip() for x in self.old_val_dict["value"].strip().split("\n")]),
                                 "\n".join([x.strip() for x in self.new_val_dict["value"].strip().split("\n")]))
        if pre_lines != post_lines:
            pre_lines  = [x.strip() for x in pre_lines.split("\n")]
            post_lines = [x.strip() for x in post_lines.split("\n")]
            dif = difflib.Differ()
            diff_list = list(dif.compare(pre_lines, post_lines))
            self.add_ok("Changelog for script", "log")
            for line in diff_list:
                if line.startswith(" "):
                    self.add_ok("    %s" % (line), "same")
                else:
                    self.add_warn("%s" % (line), "diff %s" % (line[0]))
        if not self.new_val_dict["value"].strip():
            raise ValueError, ("must not be empty", {"value" : (self.old_val_dict["value"], self.new_val_dict["value"], [("value" , self.old_val_dict["value"]),
                                                                                                                         ("upload", "")])})
    
def show_config_options(req, dev_tree, dev_dict, sub_opts_1):
    dg_sel, d_sel, dg_sel_eff = dev_tree.get_selection()
    low_submit = html_tools.checkbox(req, "sub")
    sub = low_submit.check_selection("")
    change_log = html_tools.message_log()
    new_config_types = tools.get_new_config_types(req.dc)
    if not new_config_types:
        change_log.add_ok("Adding default config_types", "ok")
        req.dc.execute("INSERT INTO new_config_type VALUES%s" % (", ".join(["(0, '%s', '%s', null)" % (x, y) for x, y in [("soft", "Software settings"),
                                                                                                                          ("hard", "Hardware setting")]]
                                                                           )))
        new_config_types = tools.get_new_config_types(req.dc)
    order_opt_list = html_tools.selection_list(req, "oo", {"o0" : {"name" : "name"},
                                                           "o1" : {"name" : "pri/name"},
                                                           "o2" : {"name" : "type/name"},
                                                           "o3" : {"name" : "type/pri/name"}
                                                           })
    order_opt = order_opt_list.check_selection("", "o0")
    ct_dict = tools.ordered_dict()
    ct_list = html_tools.selection_list(req, "cct", {})
    for idx, stuff in new_config_types.iteritems():
        ct_dict[idx] = cdef_config.new_config_type(stuff["name"], idx, stuff)
        ct_list[idx] = {"name" : "%s" % (stuff["name"])}
        ct_dict[idx].act_values_are_default()
    c_ext      = html_tools.checkbox(req, "ce")
    c_pre_ext  = html_tools.checkbox(req, "cpe")
    # nagios
    nag_class  = html_tools.selection_list(req, "cns", {}, sort_new_keys=0)
    ng_service_templates = tools.get_ng_service_templates(req.dc)
    ng_service_templates[0] = {"name" : "default"}
    for key, value in ng_service_templates.iteritems():
        nag_class[key] = value["name"]
    nag_class.mode_is_normal()
    # config types
    act_ng_check_command_types = tools.ng_check_command_types(req.dc, change_log)
    ncct_list = html_tools.selection_list(req, "ncct", {0 : "none"}, sort_new_keys=0)
    for key, value in act_ng_check_command_types.iteritems():
        ncct_list[key] = value["name"]
    ncct_list.mode_is_normal()
    # snmp mibs
    snmp_mibs = tools.get_snmp_mibs(req.dc)
    snmp_dict = tools.ordered_dict()
    mib_list = html_tools.selection_list(req, "cnmib", {}, sort_new_keys=0, multiple=1, size=3)
    for idx, stuff in snmp_mibs.iteritems():
        snmp_dict[idx] = cdef_config.snmp_mib(stuff["name"], idx, stuff)
        mib_list[idx] = "%(name)s [%(descr)s, MIB is %(mib)s, rrd_key is %(rrd_key)s]" % stuff
        snmp_dict[idx].act_values_are_default()
    mib_list.mode_is_normal()
    # config_upload
    config_upload = html_tools.upload_field(req, "tcu", size=10000, display_len=30)
    # errors
    et_del      = html_tools.checkbox(req, "etd", auto_reset=1)

    ct_vs  = new_config_type_vs(req)
    c_vs   = new_config_vs(req, ct_list, mib_list)
    cv_vs  = new_config_var_vs(req)
    nag_vs = new_nagios_vs(req, nag_class, ncct_list)
    cs_vs  = new_config_script_vs(req)
    var_types = ["str", "int", "blob", "bool"]
    vt_list = html_tools.selection_list(req, "vtl", {}, sort_new_keys=0)
    for vt in var_types:
        vt_list[vt] = vt
    c_dict = tools.ordered_dict()
    req.dc.execute("SELECT nc.* FROM new_config nc ORDER BY nc.name")
    for db_rec in req.dc.fetchall():
        idx = db_rec["new_config_idx"]
        c_dict[idx] = cdef_config.new_config(db_rec["name"], idx, db_rec)
    # fetch vars
    for long_v in ["int", "str", "blob", "bool"]:
        req.dc.execute("SELECT v.* FROM config_%s v WHERE v.new_config ORDER BY v.name" % (long_v))
        for db_rec in req.dc.fetchall():
            if c_dict.has_key(db_rec["new_config"]):
                c_dict[db_rec["new_config"]].add_var_stuff(long_v, db_rec)
    # fetch nagios
    req.dc.execute("SELECT c.* FROM ng_check_command c WHERE c.new_config ORDER BY c.name")
    for db_rec in req.dc.fetchall():
        if c_dict.has_key(db_rec["new_config"]):
            c_dict[db_rec["new_config"]].add_nagios_stuff(db_rec)
    # fetch scripts
    req.dc.execute("SELECT s.* FROM config_script s WHERE s.new_config ORDER BY s.name")
    for db_rec in req.dc.fetchall():
        if c_dict.has_key(db_rec["new_config"]):
            c_dict[db_rec["new_config"]].add_script_stuff(db_rec)
    # fetch mibs
    req.dc.execute("SELECT s.* FROM snmp_config s WHERE s.new_config ORDER BY s.snmp_mib")
    for db_rec in req.dc.fetchall():
        if c_dict.has_key(db_rec["new_config"]):
            c_dict[db_rec["new_config"]].add_snmp_mib(db_rec["snmp_mib"])
    # list of changed configs
    changed_configs = []
    # check for config upload
    c_upload = config_upload.check_selection("", "")
    if c_upload:
        try:
            c_unp = cPickle.loads(c_upload)
        except:
            change_log.add_error("Error unpickling config", str(sys.exc_info()[1]))
        else:
            if len(c_unp) == 2:
                new_ct_d, new_c_d = c_unp
                new_s_d = {}
            else:
                new_ct_d, new_c_d, new_s_d = c_unp
            # nagios check-command types
            act_ng_check_command_types = tools.ng_check_command_types(req.dc)
            ng_cct_lut = dict([(v["name"], k) for k, v in act_ng_check_command_types.iteritems()])
            # lookup table ul_idx -> act_idx (for new_config_type)
            # dict, format is config_name -> [mpi_names]
            mibs_to_add, ul_mibs_lut = ({}, {})
            for new_mib_idx, new_mib_stuff in new_s_d.iteritems():
                if new_mib_stuff["name"] in [x["name"] for x in snmp_mibs.values()]:
                    change_log.add_warn("Error adding snmp_mib '%s'" % (new_mib_stuff["name"]), "already present")
                    ul_mibs_lut[new_mib_stuff["name"]] = [k for k, v in snmp_mibs.iteritems() if v["name"] == new_mib_stuff["name"]][0]
                else:
                    req.dc.execute("INSERT INTO snmp_mib VALUES(0, %s, %s, %s, %s, %s, %s, %s, %s, %s, null)", (new_mib_stuff["name"],
                                                                                                                new_mib_stuff["descr"],
                                                                                                                new_mib_stuff["mib"],
                                                                                                                new_mib_stuff["rrd_key"],
                                                                                                                new_mib_stuff["unit"],
                                                                                                                new_mib_stuff["base"],
                                                                                                                new_mib_stuff["factor"],
                                                                                                                new_mib_stuff["var_type"],
                                                                                                                new_mib_stuff.get("special_command", "")))
                    add_idx = req.dc.insert_id()
                    snmp_dict[add_idx] = cdef_config.snmp_mib(new_mib_stuff["name"], add_idx, dict([(k, new_mib_stuff[k]) for k in ["name", "descr", "mib", "rrd_key", "unit", "base", "factor", "var_type"]]))
                    change_log.add_ok("Adding SNMP MIB '%s' (%s)" % (new_mib_stuff["name"], new_mib_stuff["descr"]), "SQL")
                    ul_mibs_lut[new_mib_stuff["name"]] = add_idx
                for new_c in new_mib_stuff["new_configs"]:
                    mibs_to_add.setdefault(new_c, []).append(new_mib_stuff["name"])
            ul_ct_lut = {}
            for new_ct_idx, new_ct_stuff in new_ct_d.iteritems():
                if new_ct_stuff["name"] in [x["name"] for x in new_config_types.values()]:
                    change_log.add_warn("Error adding config_type '%s'" % (new_ct_stuff["name"]), "already present")
                    ul_ct_lut[new_ct_idx] = [k for k, v in new_config_types.iteritems() if v["name"] == new_ct_stuff["name"]][0]
                else:
                    req.dc.execute("INSERT INTO new_config_type VALUES(0,'%s','%s',null)" % (new_ct_stuff["name"],
                                                                                             new_ct_stuff["description"]))
                    add_idx = req.dc.insert_id()
                    ct_dict[add_idx] = cdef_config.new_config_type(new_ct_stuff["name"], add_idx, {"name": new_ct_stuff["name"], "description": new_ct_stuff["description"]})
                    ct_list[add_idx] = {"name" : "%s" % (new_ct_stuff["name"])}
                    change_log.add_ok("Adding config_type '%s' (%s)" % (new_ct_stuff["name"], new_ct_stuff["description"]), "SQL")
                    ul_ct_lut[new_ct_idx] = add_idx
            for new_c_idx, new_c_stuff in new_c_d.iteritems():
                if new_c_stuff["name"] in [x["name"] for x in c_dict.itervalues()]:
                    change_log.add_warn("Error adding config '%s'" % (new_c_stuff["name"]), "already present")
                    add_idx = [k for k, v in c_dict.iteritems() if v["name"] == new_c_stuff["name"]][0]
                else:
                    req.dc.execute("INSERT INTO new_config VALUES(0,'%s','%s',%d,%d,null)" % (new_c_stuff["name"], new_c_stuff["description"], new_c_stuff["priority"], ul_ct_lut[new_c_stuff["new_config_type"]]))
                    add_idx = req.dc.insert_id()
                    # add to changed configs
                    changed_configs.append(add_idx)
                    change_log.add_ok("Adding config '%s' (%s)" % (new_c_stuff["name"], new_c_stuff["description"]), "SQL")
                    c_dict[add_idx] = cdef_config.new_config(new_c_stuff["name"], add_idx, {"name" : new_c_stuff["name"], "description" : new_c_stuff["description"], "priority" : new_c_stuff["priority"], "new_config_type" : ul_ct_lut[new_c_stuff["new_config_type"]]})
                    for long_v in ["int", "str", "blob", "bool"]:
                        if new_c_stuff.has_key(long_v):
                            for var_idx, var_stuff in new_c_stuff[long_v].iteritems():
                                req.dc.execute("INSERT INTO config_%s VALUES(0, %%s, %%s, 0, %%s, %%s, 0, null)" % (long_v), (var_stuff["name"],
                                                                                                                              var_stuff["descr"],
                                                                                                                              add_idx,
                                                                                                                              var_stuff["value"]))
                                var_stuff["config_%s_idx" % (long_v)] = req.dc.insert_id()
                                c_dict[add_idx].add_var_stuff(long_v, var_stuff)
                    if new_c_stuff.has_key("script"):
                        for script_idx, script_stuff in new_c_stuff["script"].iteritems():
                            req.dc.execute("INSERT INTO config_script VALUES(0, %s, %s, %s, %s, %s, %s, '', 0, null)", (script_stuff["name"],
                                                                                                                        script_stuff["descr"],
                                                                                                                        script_stuff["enabled"],
                                                                                                                        script_stuff["priority"],
                                                                                                                        add_idx,
                                                                                                                        script_stuff["value"]))
                            script_stuff["config_script_idx"] = req.dc.insert_id()
                            c_dict[add_idx].add_script_stuff(script_stuff)
                    if new_c_stuff.has_key("ng_check_command"):
                        for nag_idx, nag_stuff in new_c_stuff["ng_check_command"].iteritems():
                            nag_stuff["ng_service_templ"] = 0
                            # find check_command_type in lut
                            if ng_cct_lut.has_key(nag_stuff["ct_name"]):
                                cct_idx = ng_cct_lut[nag_stuff["ct_name"]]
                            elif nag_stuff["ct_name"]:
                                # insert cct_idx
                                change_log.add_ok("Adding nagios_check_command_type '%s'" % (nag_stuff["ct_name"]), "SQL")
                                req.dc.execute("INSERT INTO ng_check_command_type SET name='%s'" % (nag_stuff["ct_name"]))
                                cct_idx = req.dc.insert_id()
                                ng_cct_lut[nag_stuff["ct_name"]] = cct_idx
                            else:
                                cct_idx = 0
                            nag_stuff["ng_check_command_type"] = cct_idx
                            req.dc.execute("INSERT INTO ng_check_command VALUES(0, 0, %s, %s, 0, %s, %s, %s, 0, null)", (add_idx,
                                                                                                                         cct_idx,
                                                                                                                         nag_stuff["name"],
                                                                                                                         nag_stuff["command_line"],
                                                                                                                         nag_stuff["description"]))
                            nag_stuff["ng_check_command_idx"] = req.dc.insert_id()
                            c_dict[add_idx].add_nagios_stuff(nag_stuff)
                for nm in mibs_to_add.get(new_c_stuff["name"], []):
                    c_dict[add_idx].add_snmp_mib(ul_mibs_lut[nm])
            #print ul_ct_lut
            #print new_ct_d, new_c_d
            
    req.dc.execute("SELECT nc.name, dc.new_config, COUNT(dc.new_config) AS devcount FROM device_config dc, device d, new_config nc WHERE d.device_idx=dc.device AND nc.new_config_idx=dc.new_config GROUP BY dc.new_config")
    for db_rec in req.dc.fetchall():
        if c_dict.has_key(db_rec["new_config"]):
            c_dict[db_rec["new_config"]].device_count += db_rec["devcount"]
    ct_dict[0] = cdef_config.new_config_type(ct_vs.get_default_value("name"), 0, ct_vs.get_default_dict())
    c_dict[0]  = cdef_config.new_config(c_vs.get_default_value("name"), 0, c_vs.get_default_dict())
    # fix default values
    for idx, stuff in c_dict.iteritems():
        stuff.act_values_are_default()
    ct_list.mode_is_normal()
    
    glob_expand = html_tools.selection_list(req, "ge", {"g0" : "keep",
                                                        "g1" : "expand all",
                                                        "g2" : "collapse all"}, auto_reset=1)
    glob_expand_com = glob_expand.check_selection("", "g0")
    saved_re        = req.user_info.get_user_var_value("_sdc_re", "")
    saved_show_list = req.user_info.get_user_var_value("_sdc_sl", [0])
    saved_conf_expands = req.session_data.get_property("expanded_confs", [])
    c_regexp = html_tools.text_field(req, "cre", size=64, display_len=8)
    act_c_regexps = c_regexp.check_selection("", saved_re).split(",")
    req.user_info.modify_user_var("_sdc_re", ",".join(act_c_regexps))
    regexp_list = []
    for act_c_regexp in act_c_regexps:
        if act_c_regexp.startswith("!"):
            c_re_exclude = 1
            act_c_regexp = act_c_regexp[1:]
        else:
            c_re_exclude = 0
        try:
            c_re = re.compile(".*%s" % (act_c_regexp))
        except:
            c_re = re.compile(".*")
        else:
            pass
        regexp_list.append((c_re_exclude, c_re))
    ct_show_list = html_tools.selection_list(req, "ctd", {}, multiple=1, size=2)
    for ct_idx in ct_dict.keys():
        ct_show_list[ct_idx] = ct_dict[ct_idx]["name"] or "all types"
    ct_shows = ct_show_list.check_selection("", saved_show_list)
    req.user_info.modify_user_var("_sdc_sl", ct_shows)
    if ct_shows == [0]:
        ct_shows = [x for x in ct_dict.keys()]
    for ct_idx in ct_shows:
        ct_dict[ct_idx].show = 1
    v_del_dict, s_del_list, n_del_list = (dict([(vt, []) for vt in var_types]),
                                          [],
                                          [])
    # link new_config_type to c_vs
    c_vs.ct_tree = new_config_types
    # selected configs
    sel_configs = []
    # list to delete error_texts
    et_del_list = []
    c_dict_keys = [x for x in c_dict.keys()]
    for c_idx in c_dict_keys:
        c_stuff = c_dict[c_idx]
        re_show = None
        tot_count, show_count, rem_count, pos_count = (0, 0, 0, 0)
        for c_re_exclude, c_re in regexp_list:
            tot_count += 1
            if not c_re_exclude:
                pos_count += 1
                if c_re.match(c_stuff["name"]):
                    show_count += 1
            if c_re_exclude and c_re.match(c_stuff["name"]):
                rem_count += 1
        if show_count and not rem_count:
            re_show = 1
        elif not pos_count and not rem_count:
            re_show = 1
        else:
            re_show = 0
        if (not ct_dict[c_stuff["new_config_type"]].show or (not re_show)) and c_stuff["name"]:
            c_stuff.show = 0
            continue
        sel_configs.append(c_idx)
        expand = c_ext.check_selection(c_stuff.get_suffix(), not sub and c_stuff.get_suffix() in saved_conf_expands)
        if glob_expand_com == "g1":
            expand = 1
        elif glob_expand_com == "g2":
            expand = 0
        c_ext[c_stuff.get_suffix()] = expand
        if expand and c_stuff.get_suffix() not in saved_conf_expands:
            saved_conf_expands.append(c_stuff.get_suffix())
        elif not expand and c_stuff.get_suffix() in saved_conf_expands:
            saved_conf_expands.remove(c_stuff.get_suffix())
        pre_expand = c_pre_ext.check_selection(c_stuff.get_suffix())
        c_pre_ext[c_stuff.get_suffix()] = expand
        c_stuff.expand = expand
        c_vs.set_submit_mode(sub and pre_expand)
        c_vs.names = [c_dict[x]["name"] for x in c_dict.keys() if x != c_idx and x]
        c_vs.link_object(c_idx, c_stuff)
        c_vs.check_for_changes()
        if not c_vs.check_delete() or c_stuff.device_count:
            c_vs.process_changes(change_log, c_dict)
            if c_vs.check_create():
                new_db_obj, old_db_obj = (c_vs.get_db_obj(), c_vs.get_old_db_obj())
                old_db_obj.add_var_stuff("str", cv_vs.get_default_dict())
                old_db_obj.add_nagios_stuff(nag_vs.get_default_dict())
                old_db_obj.add_script_stuff(cs_vs.get_default_dict())
                if new_db_obj["name"].count("export"):
                    add_var_dict = {"export"  : "/export_dir",
                                    "import"  : "/import_dir",
                                    "options" : "-tcp,hard,intr,rsize=8192,wsize=8192,timeo=14,retrans=10"}
                elif new_db_obj["name"].endswith("rsync"):
                    add_var_dict = {"rsync_name"     : ("rsyncname", "Name of rsync-export in /etc/rsyncd.conf"),
                                    "export_rsync"   : ("/export_dir", "Directory to export"),
                                    "import_rsync"   : ("/import_dir", "Directory to import"),
                                    "excluded_dirs"  : (".cvs", "entries to exclude")}
                else:
                    add_var_dict = {}
                if add_var_dict:
                    for var_name, var_content in add_var_dict.iteritems():
                        if type(var_content) == type(()):
                            var_content, var_descr = var_content
                        else:
                            var_descr = "auto-added var"
                        if type(var_content) == type(""):
                            var_type = "str"
                            req.dc.execute("INSERT INTO config_str SET name='%s', descr='%s',new_config=%d, value='%s'" % (var_name, var_descr, new_db_obj.get_idx(), var_content))
                        else:
                            var_type = "int"
                            req.dc.execute("INSERT INTO config_int SET name='%s', descr='%s',new_config=%d, value=%d" % (var_name, var_descr, new_db_obj.get_idx(), var_content))
                        add_idx = req.dc.insert_id()
                        new_db_obj.add_var_stuff(var_type, {"name"                       : var_name,
                                                            "config_%s_idx" % (var_type) : add_idx,
                                                            "descr"                      : var_descr,
                                                            "new_config"                 : new_db_obj.get_idx(),
                                                            "value"                      : var_content})
                if not pre_expand:
                    # init fields with default-values
                    new_db_obj.add_var_stuff("str", cv_vs.get_default_dict())
                    new_db_obj.add_nagios_stuff(nag_vs.get_default_dict())
                    new_db_obj.add_script_stuff(cs_vs.get_default_dict())
                else:
                    # copy fields of new_config to new_config instance :-)
                    for field in cv_vs.get_he_names():
                        cv_vs.get_he(field).copy_selection(old_db_obj.get_new_config_var_suffix(), new_db_obj.get_new_config_var_suffix())
                    for field in nag_vs.get_he_names():
                        nag_vs.get_he(field).copy_selection(old_db_obj.get_new_ng_check_command_suffix(), new_db_obj.get_new_ng_check_command_suffix())
                    for field in cs_vs.get_he_names():
                        cs_vs.get_he(field).copy_selection(old_db_obj.get_new_config_script_suffix(), new_db_obj.get_new_config_script_suffix())
                cv_vs.init_fields(old_db_obj.get_new_config_var_suffix(), not pre_expand)
                nag_vs.init_fields(old_db_obj.get_new_ng_check_command_suffix(), not pre_expand)
                cs_vs.init_fields(old_db_obj.get_new_config_script_suffix(), not pre_expand)
                # init fields for new instance (zero-idx)
                # copy special fields
                # a little bit fishy ...
                old_db_obj.expand = new_db_obj.expand
                new_db_obj.expand = expand
                c_ext[new_db_obj.get_suffix()] = new_db_obj.expand
                c_pre_ext[new_db_obj.get_suffix()] = new_db_obj.expand
                if new_db_obj["name"] not in act_c_regexps:
                    act_c_regexps.append(new_db_obj["name"])
                    c_regexp[""] = ",".join(act_c_regexps)
                sel_configs.append(new_db_obj.get_idx())
                if pre_expand:
                    vt_list.check_selection(old_db_obj.get_new_config_var_suffix())
                else:
                    vt_list.check_selection(old_db_obj.get_new_config_var_suffix(), var_types[0])
                # add to changed configs
                changed_configs.append(new_db_obj.get_idx())
            c_stuff.add_var_stuff("str", cv_vs.get_default_dict())
            c_stuff.add_nagios_stuff(nag_vs.get_default_dict())
            c_stuff.add_script_stuff(cs_vs.get_default_dict())
            # list of changes
            local_changes = []
            # var stuff
            for act_var_type in c_stuff.vars.keys():
                for var_idx in c_stuff.vars[act_var_type].keys():
                    v_stuff = c_stuff.vars[act_var_type][var_idx]
                    cv_vs.set_old_db_obj_idx(c_stuff.get_new_config_var_suffix())
                    cv_vs.set_new_object_fields({"new_config" : c_stuff.get_idx()})
                    # FIXME !!!
                    cv_vs.names = [x["name"] for x in c_stuff.vars[act_var_type].values() if x["name"]]
                    cv_vs.act_type = vt_list.check_selection(v_stuff.get_suffix(), "") or v_stuff.get_type()

                    cv_vs.link_object(var_idx, v_stuff, c_stuff.get_idx())
                    cv_vs.check_for_changes()
                    if cv_vs.check_delete():
                        v_del_dict[cv_vs.act_type].append((c_stuff.get_idx(), var_idx))
                        local_changes.append(True)
                    else:
                        local_changes.append(cv_vs.process_changes(change_log, c_stuff.vars[act_var_type]))
                    cv_vs.unlink_object()
            # nagios stuff
            for nag_idx in c_stuff.nagios.keys():
                n_stuff = c_stuff.nagios[nag_idx]
                nag_vs.set_old_db_obj_idx(c_stuff.get_new_ng_check_command_suffix())
                nag_vs.set_new_object_fields({"new_config" : c_stuff.get_idx()})
                nag_vs.names = [x["name"] for x in c_stuff.nagios.values() if x["name"]]
                nag_vs.ng_service_templates = ng_service_templates
                nag_vs.act_ng_check_command_types = act_ng_check_command_types
                nag_vs.link_object(nag_idx, n_stuff, c_stuff.get_idx())
                nag_vs.check_for_changes()
                if nag_vs.check_delete():
                    n_del_list.append((c_stuff.get_idx(), nag_idx))
                else:
                    nag_vs.process_changes(change_log, c_stuff.nagios)
                nag_vs.unlink_object()
            # script stuff
            for script_idx in c_stuff.scripts.keys():
                s_stuff = c_stuff.scripts[script_idx]
                # to distinguish select / submit
                cs_vs.set_submit_mode(sub and pre_expand)
                cs_vs.set_old_db_obj_idx(c_stuff.get_new_config_script_suffix())
                cs_vs.set_new_object_fields({"new_config" : c_stuff.get_idx()})
                cs_vs.names = [x["name"] for x in c_stuff.scripts.values() if x["name"]]
                cs_vs.link_object(script_idx, s_stuff, c_stuff.get_idx())
                cs_vs.check_for_changes()
                if cs_vs.check_delete():
                    s_del_list.append((c_stuff.get_idx(), script_idx))
                    local_changes.append(True)
                else:
                    local_changes.append(cs_vs.process_changes(change_log, c_stuff.scripts))
                cs_vs.unlink_object()
                if et_del.check_selection(s_stuff.get_suffix(), False):
                    et_del_list.append((c_idx, script_idx))
                    local_changes.append(True)
            if [True for x in local_changes if x]:
                changed_configs.append(c_idx)
        c_vs.unlink_object()
    req.session_data.set_property("expanded_confs", saved_conf_expands)
    for vt, vt_l in v_del_dict.iteritems():
        if vt_l:
            change_log.add_ok("Deleted %s: %s" % (logging_tools.get_plural("%s variable" % (vt), len(vt_l)),
                                                  ", ".join(["%s on config %s" % (c_dict[x].vars[vt][y].get_name(), c_dict[x].get_name()) for x, y in vt_l])), "SQL")
            for c_idx, var_idx in vt_l:
                del c_dict[c_idx].vars[vt][var_idx]
                sql_str = "DELETE FROM config_%s WHERE %s" % (vt, " OR ".join(["config_%s_idx=%d" % (vt, y) for x, y in vt_l]))
                req.dc.execute(sql_str)
    if et_del_list:
        change_log.add_ok("Deleted %s: %s" % (logging_tools.get_plural("error_text", len(et_del_list)),
                                              ", ".join(["%s on config %s" % (c_dict[x].scripts[y].get_name(), c_dict[x].get_name()) for x, y in et_del_list])), "SQL")
        sql_str = "UPDATE config_script SET error_text='' WHERE %s" % (" OR ".join(["config_script_idx=%d" % (y) for x, y in et_del_list]))
        req.dc.execute(sql_str)
    if s_del_list:
        change_log.add_ok("Deleted %s: %s" % (logging_tools.get_plural("script", len(s_del_list)),
                                              ", ".join(["%s on config %s" % (c_dict[x].scripts[y].get_name(), c_dict[x].get_name()) for x, y in s_del_list])), "SQL")
        for c_idx, script_idx in s_del_list:
            del c_dict[c_idx].scripts[script_idx]
        sql_str = "DELETE FROM config_script WHERE %s" % (" OR ".join(["config_script_idx=%d" % (y) for x, y in s_del_list]))
        req.dc.execute(sql_str)
    if n_del_list:
        change_log.add_ok("Deleted %s: %s" % (logging_tools.get_plural("Nagios command", len(n_del_list)),
                                              ", ".join(["%s on config %s" % (c_dict[x].nagios[y].get_name(), c_dict[x].get_name()) for x, y in n_del_list])), "SQL")
        for c_idx, nag_idx in n_del_list:
            del c_dict[c_idx].nagios[nag_idx]
        sql_str = "DELETE FROM ng_check_command WHERE %s" % (" OR ".join(["ng_check_command_idx=%d" % (y) for x, y in n_del_list]))
        req.dc.execute(sql_str)
    if c_vs.get_delete_list():
        for del_idx in c_vs.get_delete_list():
            change_log.add_ok("Deleted config '%s'" % (c_dict[del_idx]["name"]), "SQL")
            del c_dict[del_idx]
        sql_str = "DELETE FROM new_config WHERE %s" % (" OR ".join(["new_config_idx=%d" % (x) for x in c_vs.get_delete_list()]))
        req.dc.execute(sql_str)
        for var_type in var_types:
            sql_str = "DELETE FROM config_%s WHERE %s" % (var_type, " OR ".join(["new_config=%d" % (x) for x in c_vs.get_delete_list()]))
            req.dc.execute(sql_str)
        sql_str = "DELETE FROM snmp_config WHERE %s" % (" OR ".join(["new_config=%d" % (x) for x in c_vs.get_delete_list()]))
        req.dc.execute(sql_str)
        sql_str = "DELETE FROM config_script WHERE %s" % (" OR ".join(["new_config=%d" % (x) for x in c_vs.get_delete_list()]))
        req.dc.execute(sql_str)

    # config_types
    c_sf_dict = dict([(v["name"], k) for k, v in c_dict.iteritems() if v["name"] and v.show])
    if order_opt == "o0":
        # order by name
        c_sf_names = sorted(c_sf_dict.keys())
    elif order_opt == "o1":
        # order by pri/name
        pri_dict = {}
        for c_idx, c_stuff in c_dict.iteritems():
            if c_stuff["name"] and c_stuff.show:
                pri_dict.setdefault(c_stuff["priority"], []).append(c_stuff["name"])
        c_sf_names = []
        for pri in sorted(pri_dict.keys(), reverse=True):
            c_sf_names.extend(sorted(pri_dict[pri]))
    elif order_opt == "o2":
        # order by type/name
        type_dict = {}
        for c_idx, c_stuff in c_dict.iteritems():
            if c_stuff["name"] and c_stuff.show:
                type_dict.setdefault(c_stuff["new_config_type"], []).append(c_stuff["name"])
        c_sf_names = []
        for s_type in sorted(type_dict.keys()):
            c_sf_names.extend(sorted(type_dict[s_type]))
    elif order_opt == "o3":
        # order by type/pri/name
        gen_dict = {}
        for c_idx, c_stuff in c_dict.iteritems():
            if c_stuff["name"] and c_stuff.show:
                gen_dict.setdefault(c_stuff["new_config_type"], {}).setdefault(c_stuff["priority"], []).append(c_stuff["name"])
        c_sf_names = []
        for g_s0 in sorted(gen_dict.keys()):
            for g_s1 in sorted(gen_dict[g_s0].keys()):
                c_sf_names.extend(sorted(gen_dict[g_s0][g_s1]))
    # signal servers
    changed_configs = dict([(k, 1) for k in changed_configs]).keys()
    changed_config_names = dict([(c_dict[k]["name"], k) for k in changed_configs])
    changed_config_servers = dict([(k, req.conf["server"].get(k)) for k in changed_config_names.keys()])
    com_list = []
    for changed_config_name, changed_servers in changed_config_servers.iteritems():
        changed_conf = c_dict[changed_config_names[changed_config_name]]
        # find integer variables with name 'COMPORT' or similar
        int_vars = dict([(x["name"], x["value"]) for x in changed_conf.vars["int"].itervalues() if x["name"].lower().count("port")])
        if len(int_vars.keys()) > 1:
            int_vars = dict([(k, v) for k, v in int_vars.iteritems() if k.lower().count("com")])
        if len(int_vars.keys()) == 1:
            if changed_servers:
                for h_name, h_ip in changed_servers.iteritems():
                    com_list.append(tools.s_command(req, changed_config_name, int_vars.values()[0], server_command.server_command(command="reload_config"), [], 10, h_name))
    if com_list:
        tools.iterate_s_commands(com_list, change_log)
    dg_sel, d_sel, dg_sel_eff = dev_tree.get_selection()
    srv_dict = sub_clusterconfig_show_device_config.create_config(req, dev_tree, dev_dict, change_log, sub_opts_1)
    req.write(change_log.generate_stack("Action log"))
    sub_clusterconfig_show_device_config.show_config(req, dev_tree, dev_dict, srv_dict, sub_opts_1, c_sf_names)
    req.write(html_tools.gen_hline("%s defined, showing %s" % (logging_tools.get_plural("config", len(c_dict.keys())-1),
                                                               logging_tools.get_plural("config", len(c_sf_names))), 2))
    out_table = html_tools.html_table(cls="normal")
    req.write(out_table.get_header())
    out_table[0]["class"] = "lineh"
    for what in ["exp", "Name", "priority", "config_type", "info", "description", "del"]:
        out_table[None][0] = html_tools.content(what, type="th")
    line_idx = 1
    for c_stuff in [c_dict[n] for n in [c_sf_dict[n] for n in c_sf_names] + [0]]:
        line_idx = 1 - line_idx
        if not c_stuff.get_idx():
            out_table[0]["class"] = "lineh"
            out_table[None][0 : 7] = html_tools.content("New config", type="th")
        var_dict = dict([(k, len([1 for x in c_stuff.vars[k].values() if x.get_idx()])) for k in var_types])
        out_table[0]["class"] = "line0%d" % (line_idx)
        if c_stuff.expand:
            out_table[None : 4][0] = html_tools.content([c_ext, c_pre_ext.create_hidden_var(c_stuff.get_suffix())], cls="centersmall")
        else:
            out_table[None][0] = html_tools.content([c_ext, c_pre_ext.create_hidden_var(c_stuff.get_suffix())], cls="centersmall")
        out_table[None][0] = html_tools.content(c_vs.get_he("name"))
        out_table[None][0] = html_tools.content(c_vs.get_he("priority"), cls="center")
        out_table[None][0] = html_tools.content(ct_list   , cls="center")
        if c_stuff.get_idx():
            num_scripts, num_nag, num_snmps = (len([1 for x in c_stuff.scripts.itervalues() if x.get_idx()]),
                                               len([1 for x in c_stuff.nagios.itervalues() if x.get_idx()]),
                                               len([True for x in c_stuff["snmp_mibs"]]))
            out_table[None][0] = html_tools.content(", ".join([logging_tools.get_plural("%s var" % (k), var_dict[k]) for k in var_types if var_dict[k]] + 
                                                              (num_scripts and [logging_tools.get_plural("script", num_scripts)] or []) + 
                                                              (num_nag and [logging_tools.get_plural("nagios checkcommand", num_nag)] or []) +
                                                              (num_snmps and [logging_tools.get_plural("SNMP MIB", num_snmps)] or [])) or "---", cls="left")
            out_table[None][0] = html_tools.content(c_vs.get_he("description"))
            if c_stuff.device_count:
                out_table[None][0] = html_tools.content("%d" % (c_stuff.device_count), cls="center")
            else:
                out_table[None][0] = html_tools.content(c_vs.get_he("del"), cls="errormin")
        else:
            out_table[None][0 : 3] = html_tools.content(c_vs.get_he("description"))
        if c_stuff.expand:
            # var part
            var_table = html_tools.html_table(cls="blind")
            line1_idx = 1
            var_name_lut_dict = {}
            empty_list = []
            for vt in var_types:
                for key, value in c_stuff.vars[vt].iteritems():
                    if value.get_idx():
                        var_name_lut_dict[value["name"]] = (vt, key)
                    else:
                        empty_list = [(vt, 0)]
            var_table[0]["class"] = "line31"
            for what in ["Varname", "Class", "Type", "del", "Value", "Description"]:
                var_table[None][0] = html_tools.content(what, type="th")
            for var_type, var_idx in [var_name_lut_dict[n] for n in sorted(var_name_lut_dict.keys())] + empty_list:
                var = c_stuff.vars[var_type][var_idx]
                line1_idx = 1 - line1_idx
                if not var_idx:
                    var_table[0]["class"] = "line30"
                    var_table[None][0 : 2] = html_tools.content(["New: ", cv_vs.get_he("name")], var.get_suffix(), cls="left")
                    var_table[None][0 : 2] = html_tools.content(vt_list     , var.get_suffix(), cls="center")
                else:
                    var_table[0]["class"] = "line1%d" % (line1_idx)
                    var_table[None][0] = html_tools.content(cv_vs.get_he("name") , var.get_suffix(), cls="left")
                    var_val = cv_vs.get_he("name")[var.get_suffix()]
                    if var_val.startswith(":"):
                        var_class = "template"
                    elif var_val.count(":"):
                        var_class = "local"
                    else:
                        var_class = "global"
                    var_table[None][0] = html_tools.content(var_class , var.get_suffix(), cls="center")
                    var_table[None][0] = html_tools.content(var.get_type(), var.get_suffix(), cls="center")
                    var_table[None][0] = html_tools.content(cv_vs.get_he("del")       , var.get_suffix(), cls="errormin")
                var_table[None][0] = html_tools.content(cv_vs.get_he("value"), var.get_suffix())
                var_table[None][0] = html_tools.content(cv_vs.get_he("descr"), var.get_suffix())
            #out_table[0][2 : 7] = var_table
            # nagios part
            nag_table = html_tools.html_table(cls="blind")
            line1_idx = 1
            nag_dict = {}
            for key, value in c_stuff.nagios.iteritems():
                if key:
                    nag_dict.setdefault(value["name"], []).append(key)
            if len([1 for n in c_stuff.nagios.itervalues() if not n.get_idx()]):
                empty_list = [0]
            else:
                empty_list = []
            nag_table[0]["class"] = "line31"
            for what in ["NagiosCommandName", "Class", "del", "NagiosCommand", ("DisplayStr / Type", "left")]:
                if type(what) == type(""):
                    nag_table[None][0] = html_tools.content(what, type="th")
                else:
                    what, or_str = what
                    nag_table[None][0] = html_tools.content(what, cls=or_str, type="th")
            nag_idx_list = []
            for n_name in sorted(nag_dict.keys()):
                nag_idx_list.extend(nag_dict[n_name])
            nag_idx_list.extend(empty_list)
            for nag_idx in nag_idx_list:
                nag = c_stuff.nagios[nag_idx]
                line1_idx = 1 - line1_idx
                if not nag_idx:
                    nag_table[0]["class"] = "line30"
                    nag_table[None][0] = html_tools.content(["New:", nag_vs.get_he("name")], nag.get_suffix())
                    nag_table[None][0 : 2] = html_tools.content(nag_class, nag.get_suffix(), cls="center")
                else:
                    nag_table[0]["class"] = "line1%d" % (line1_idx)
                    nag_table[None][0] = html_tools.content(nag_vs.get_he("name")            , nag.get_suffix())
                    nag_table[None][0] = html_tools.content(nag_vs.get_he("ng_service_templ"), nag.get_suffix(), cls="center")
                    nag_table[None][0] = html_tools.content(nag_vs.get_he("del")             , nag.get_suffix(), cls="errormin")
                nag_table[None][0] = html_tools.content(nag_vs.get_he("command_line"), nag.get_suffix())
                nag_table[None][0] = html_tools.content([nag_vs.get_he("description"),
                                                         " / ",
                                                         nag_vs.get_he("ng_check_command_type")], nag.get_suffix())
                
            nag_table[0]["class"] = "line31"
            nag_table[None][0 : 5] = html_tools.content(["SNMP MIBs: ", c_vs.get_he("snmp_mibs")], cls="top")
            out_table[0][2 : 7] = html_tools.content(var_table, cls="blind", beautify=0)
            out_table[0][2 : 7] = html_tools.content(nag_table, cls="blind", beautify=0)
            # script part
            script_table = html_tools.html_table(cls="blind")
            line1_idx = 1
            script_dict = dict([(s["name"], k) for k, s in c_stuff.scripts.iteritems() if s.get_idx()])
            if len([1 for s in c_stuff.scripts.itervalues() if not s.get_idx()]):
                empty_list = [0]
            else:
                empty_list = []
            if script_dict:
                script_table[0]["class"] = "line30"
                for what in ["Scriptname", "enabled", "pri", "del", "Description", "info"]:
                    script_table[None][0] = html_tools.content(what, type="th")
            for script_idx in [script_dict[n] for n in sorted(script_dict.keys())] + empty_list:
                script = c_stuff.scripts[script_idx]
                line1_idx = 1 - line1_idx
                loc_errors = ""
                if not script_idx:
                    script_table[0]["class"] = "line30"
                    script_table[None][0 : 6] = html_tools.content("New script", type="th")
                if script_idx:
                    lines = script["value"].split("\n")
                    line_type = "line1%d" % (line1_idx)
                    script_type = "unknown script"
                    if lines:
                        first_line = lines[0]
                        if first_line.startswith("#!"):
                            script_type = first_line[2:]
                        else:
                            script_type = "internal python-script"
                            # check syntax
                            start_time = time.time()
                            try:
                                compile(script["value"].replace("\r\n", "\n")+"\n", "<script>", "exec")
                            except:
                                line_type = "error"
                                script_type += ", one or more errors in script"
                                tbc = tb_container()
                                tb_type, tb_value, tb_traceback = sys.exc_info()
                                traceback.print_exception(tb_type, tb_value, tb_traceback, None, tbc)
                                loc_errors = tbc.get_content()
                            else:
                                script_type += ", syntax seems to be ok"
                            end_time = time.time()
                            diff_time = end_time-start_time
                            script_type += " (%ssecs)" % (diff_time < 0.001 and "%.2f m" % (diff_time * 1000) or "%.4f " % (diff_time))
                    script_table[0]["class"] = line_type
                    script_table[None][0] = html_tools.content(["Name:", cs_vs.get_he("name")]   , script.get_suffix())
                    script_table[None][0] = html_tools.content(cs_vs.get_he("enabled")           , script.get_suffix(), cls="center")
                    script_table[None][0] = html_tools.content(["pri:", cs_vs.get_he("priority")], script.get_suffix(), cls="center")
                    script_table[None][0] = html_tools.content(cs_vs.get_he("del")               , script.get_suffix(), cls="errormin")
                    script_table[None][0] = html_tools.content(["descr:", cs_vs.get_he("descr")] , script.get_suffix())
                    script_table[None][0] = html_tools.content("%s in %s" % (logging_tools.get_plural("byte", len(script["value"])),
                                                                             logging_tools.get_plural("line", len(script["value"].split("\n")))))
                    script_table[0]["class"] = line_type
                    target = "fetchscript.py?%s&script=%d" % (functions.get_sid(req), script_idx)
                    script_table[None][0 : 2] = html_tools.content(["Upload:", cs_vs.get_he("upload")], script.get_suffix())
                    script_table[None][0] = html_tools.content("<a href=\"%s\" type=\"text/plain\">fetch scripttext</a>" % (target), cls="center")
                    script_table[None][0 : 3] = html_tools.content("Guessed scripttype: %s" % (script_type))
                else:
                    script_table[0]["class"] = "line1%d" % (line1_idx)
                    script_table[None][0] = html_tools.content(["Name:", cs_vs.get_he("name")]      , script.get_suffix())
                    script_table[None][0] = html_tools.content(cs_vs.get_he("enabled")              , script.get_suffix(), cls="center")
                    script_table[None][0 : 2] = html_tools.content(["pri:", cs_vs.get_he("priority")] , script.get_suffix(), cls="center")
                    script_table[None][0 : 2] = html_tools.content(["descr:", cs_vs.get_he("descr")]  , script.get_suffix())
                    script_table[0]["class"] = "line1%d" % (line1_idx)
                    script_table[None][0 : 6] = html_tools.content(["Upload:", cs_vs.get_he("upload")], script.get_suffix())
                script_table[0]["class"] = "line1%d" % (line1_idx)
                if script["error_text"] or loc_errors:
                    script_table[None][0 : 3] = html_tools.content(cs_vs.get_he("value"), script.get_suffix(), beautify = 0)
                    if script["error_text"]:
                        script_table[None][0] = html_tools.content(et_del, script.get_suffix(), cls="errormin", beautify = 0)
                    else:
                        script_table[None][0] = html_tools.content("&nbsp;", beautify=0)
                    err_str = loc_errors and cgi.escape(loc_errors) or cgi.escape(script["error_text"])
                    script_table[None][0 : 2] = html_tools.content("ERROR:<br>%s" % (err_str.replace("\n", "<br>").replace(" ", "&nbsp;")),
                                                                   cls="left",
                                                                   beautify=0)
                else:
                    script_table[None][0 : 6] = html_tools.content(cs_vs.get_he("value"), script.get_suffix(), beautify=0)
            out_table[0][2 : 7] = html_tools.content(script_table, cls="blind", beautify=0)
        req.write(out_table.flush_lines(c_stuff.get_suffix()))
    req.write(out_table.get_footer())
    # config_types
    opt_table = html_tools.html_table(cls="blindsmall")
    opt_table[0][0] = html_tools.content(["Options: order by ", order_opt_list,
                                          ", show ", ct_show_list,
                                          ", name regexp: ", c_regexp,
                                          ", expand:", glob_expand])
    d_target = "fetchconfig.py?%s&%s" % (functions.get_sid(req), "&".join(["config[]=%d" % (x) for x in sel_configs if x]))
    opt_table[0][0] = html_tools.content(["<a href=\"%s\" type=\"text/plain\">Save selected configs</a>, " % (d_target),
                                          "upload from ",
                                          config_upload])
    req.write(opt_table(""))

    low_submit[""] = 1
    submit_button = html_tools.submit_button(req, "submit")
    submit_button.set_class("", "button")
    req.write("%s<div class=\"center\">%s</div>\n" % (low_submit.create_hidden_var(""),
                                                      submit_button("")))
