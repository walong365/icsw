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
""" rsync install frontend """

import re
import logging_tools
import functions
import tools
import html_tools
import cdef_device

DEFAULT_STATUS_STRING = "w not set"

def module_info():
    return {"ri" : {"description"           : "Rsync install",
                    "enabled"               : 1,
                    "default"               : 0,
                    "left_string"           : "RSync install",
                    "right_string"          : "RSyncs given directory trees",
                    "capability_group_name" : "conf",
                    "priority"              : 40}}

class rsync_info(object):
    def __init__(self):
        self.__rsync_objects = {}
        # device_config lut
        self.__dc_lut = {}
    def get_num_rsync_objects(self, only_processed=True):
        if only_processed:
            return len([True for v in self.__rsync_objects.values() if v.get_process_flag()])
        else:
            return len([True for v in self.__rsync_objects.values()])
    def get_rsync_object(self, rso_idx):
        return self.__rsync_objects[rso_idx]
    def get_sorted_rsync_object_idxs(self):
        lu_dict = dict([(v.get_name(), k) for k, v in self.__rsync_objects.iteritems() if v.get_process_flag()])
        return [lu_dict[x] for x in sorted(lu_dict.keys())]
    def fetch_config(self, dc):
        # first step: get possible rsync-configs
        dc.execute("SELECT c.new_config_idx, c.name FROM new_config c WHERE c.name LIKE('%rsync%')")
        for db_rec in dc.fetchall():
            self.__rsync_objects[db_rec["new_config_idx"]] = rsync_object(db_rec["new_config_idx"], db_rec["name"])
        if self.__rsync_objects:
            # add variables
            dc.execute("SELECT cs.name, cs.value, cs.new_config FROM config_str cs WHERE (%s)" % (" OR ".join(["cs.new_config=%d" % (x) for x in self.__rsync_objects.keys()])))
            for db_rec in dc.fetchall():
                self.__rsync_objects[db_rec["new_config"]].add_var(db_rec["name"], db_rec["value"])
            # add servers
            dc.execute("SELECT dc.device_config_idx, dc.new_config, d.device_idx, d.name FROM device_config dc, device d WHERE dc.device=d.device_idx AND (%s)" % (" OR ".join(["dc.new_config=%d" % (x) for x in self.__rsync_objects.keys()])))
            for db_rec in dc.fetchall():
                self.__dc_lut[db_rec["device_config_idx"]] = db_rec["new_config"]
                self.__rsync_objects[db_rec["new_config"]].add_server(db_rec["device_idx"], db_rec["name"], db_rec["device_config_idx"])
        # add devices
        dc.execute("SELECT dr.*, d.device_idx, d.name FROM device_rsync_config dr, device d WHERE dr.device=d.device_idx")
        for db_rec in dc.fetchall():
            self.__rsync_objects[db_rec["new_config"]].add_device(db_rec["device_idx"], db_rec)#["device_idx"], x["name"], x["last_rsync"])
    def get_new_config_idx(self, drs_config):
        return self.__dc_lut[drs_config]
    def check_for_name_match(self, name_re):
        for rs_o in self.__rsync_objects.values():
            rs_o.set_process_flag(name_re.match(rs_o.get_name()))
        
class rsync_object(object):
    def __init__(self, idx, name):
        self.__idx = idx
        self.__name = name
        self.__servers = {}
        self.__vars = {}
        # device count
        self.__devcount = 0
        # associated devices
        self.__devices = {}
        # keys needed to be valid
        self.__needed_keys = ["export_rsync", "import_rsync"]
        # is valid
        self.__is_valid = False
        # process_flag (to disable object not matching a given name)
        self.set_process_flag()
    def set_process_flag(self, pf=True):
        self.__process_flag = pf
    def get_process_flag(self):
        return self.__process_flag
    def get_name(self):
        return self.__name
    def get_config_idx(self):
        return self.__idx
    def get_suffix(self):
        return "ro%d" % (self.__idx)
    def get_device_suffix(self, dev):
        return "%sx%s" % (self.get_suffix(), dev.get_suffix())
    def has_devices(self):
        return self.__devices and True or False
    def get_servers(self):
        return [x for x, y in self.__servers.values()]
    def get_device_names(self):
        return [x["name"] for x in self.__devices.values()]
    def get_device_dict(self, dev_idx):
        return self.__devices[dev_idx]
    def get_server_conf_idxs(self):
        return [y for x, y in self.__servers.values()]
    def add_server(self, srv_idx, srv_name, conf_idx):
        if srv_idx and srv_idx not in self.__servers.keys():
            self.__servers[srv_idx] = (srv_name, conf_idx)
        self._check_validity()
    def add_var(self, var_idx, var_value):
        if var_idx and var_idx not in self.__vars.keys():
            self.__vars[var_idx] = var_value
        self._check_validity()
    def add_device(self, dev_idx, in_dict):
        if in_dict["status"] == None:
            in_dict["status"] = DEFAULT_STATUS_STRING
        self.__devices[dev_idx] = in_dict
        self.__devcount += 1
    def remove_device(self, dev_idx):
        del self.__devices[dev_idx]
        self.__devcount -= 1
    def device_present(self, dev_idx):
        return self.__devices.has_key(dev_idx)
    def is_valid(self):
        return self.__is_valid
    def _check_validity(self):
        # return True if certain keys are present
        self.__is_valid = (len([True for x in self.__needed_keys if self.__vars.has_key(x)]) == 2) and self.__servers
    def get_info(self):
        if self.__is_valid:
            return "rsyncing from '%s' to '%s'" % (self.__vars["export_rsync"],
                                                   self.__vars["import_rsync"])
        else:
            return "not valid"
            
def get_last_contact_state_and_str(l_c):
    def get_str_from_sec(sec):
        r_strs = []
        if sec > 3600:
            r_strs.append("%d" % (int(sec/3600)))
            sec -= 3600 * int(sec/3600)
        if sec > 60:
            r_strs.append("%02d" % (int(sec/60)))
            sec -= 60 * int(sec/60)
        r_strs.append("%02d" % (sec))
        if len(r_strs) == 1:
            return "%s secs" % (r_strs[0])
        else:
            return ":".join(r_strs)
    if l_c is None:
        state, ret_str = (3, "Never")
    else:
        diff_time = l_c.today() - l_c
        if diff_time.days:
            state, ret_str = (2, "more than one day (%s %s) ago" % (logging_tools.get_plural("day", diff_time.days),
                                                                    get_str_from_sec(diff_time.seconds)))
        elif diff_time.seconds > 3600:
            state, ret_str = (1, "more than one hour (%s) ago" % (get_str_from_sec(diff_time.seconds)))
        else:
            state, ret_str = (0, "%s ago" % (get_str_from_sec(diff_time.seconds)))
    return state, ret_str

def collapse_names(name_list):
    return logging_tools.compress_list(name_list)

def collapse_versions(vers_list):
    unique_dict = dict([(k, len([1 for x in vers_list if x == k])) for k in vers_list])
    unique_vers = unique_dict.keys()
    return ", ".join(["%s%s" % (x, unique_dict[x] > 1 and "(%d)" % (unique_dict[x]) or "") for x in unique_vers])

def collapse_last_contact(lc_list):
    if [1 for x in lc_list if x is None]:
        max_str = "Never"
    else:
        max_str = get_last_contact_state_and_str(max([x for x in lc_list if x is not None]))[1]
    if [1 for x in lc_list if x is not None]:
        min_str = get_last_contact_state_and_str(min([x for x in lc_list if x is not None]))[1]
    else:
        min_str = "Never"
    if min_str == max_str:
        return min_str
    else:
        return "%s - %s" % (min_str, max_str)

def show_info(req, rsync_dict, add_command, overview):
    num_rso     = rsync_dict.get_num_rsync_objects()
    num_rso_tot = rsync_dict.get_num_rsync_objects(False)
    if num_rso == num_rso_tot:
        req.write(html_tools.gen_hline("Rsync overview, %s" % (logging_tools.get_plural("rsync object", num_rso)), 2))
    else:
        req.write(html_tools.gen_hline("Rsync overview, %s (of %s total)" % (logging_tools.get_plural("rsync object", num_rso),
                                                                             logging_tools.get_plural("rsync object", num_rso_tot)), 2))
    info_table = html_tools.html_table(cls="normalsmall")
    info_table[0]["class"] = "line01"
    if overview:
        h_names = ["Name", "valid", "server info", "device info", "info"]
    else:
        h_names = ["Name", "valid", "server info", "device info", "command", "info"]
    for h_name in h_names:
        info_table[None][0] = html_tools.content(h_name, cls="center", type="th")
    line_idx = 0
    for ro_idx in rsync_dict.get_sorted_rsync_object_idxs():
        line_idx = 1 - line_idx
        info_table[0]["class"] = "line1%d" % (line_idx)
        act_rso = rsync_dict.get_rsync_object(ro_idx)
        srv_list = act_rso.get_servers()
        dev_list = act_rso.get_device_names()
        info_table[None][0] = html_tools.content(act_rso.get_name(), cls="left")
        info_table[None][0] = html_tools.content(act_rso.is_valid() and "yes" or "no", cls=act_rso.is_valid() and "okmin" or "errormin")
        info_table[None][0] = html_tools.content(srv_list and "%s: %s" % (logging_tools.get_plural("source server", len(srv_list)),
                                                                          logging_tools.compress_list(sorted(srv_list))) or "no source servers")
        info_table[None][0] = html_tools.content(dev_list and "%s: %s" % (logging_tools.get_plural("device", len(dev_list)),
                                                                          logging_tools.compress_list(sorted(dev_list))) or "none")
        if not overview:
            info_table[None][0] = html_tools.content(add_command, act_rso.get_suffix(), cls="center")
        info_table[None][0] = html_tools.content(act_rso.get_info(), cls="left")
    req.write(info_table())
    submit_button = html_tools.submit_button(req, "submit")
    req.write("<div class=\"center\">%s</div>\n" % (submit_button()))
    
def get_size_str(sz):
    if 0:
        pf_list, out_list = (["B", "k", "M", "G", "T"], [])
        while 1:
            next_sz = int(sz / 1024)
            act_v = sz - 1024 * next_sz
            out_list.insert(0, "%d %s" % (act_v, pf_list.pop(0)))
            sz = next_sz
            if not sz:
                break
        return " ".join(out_list)
    else:
        ms = 1
        for pf in ["", "k", "M", "G"]:
            if sz < ms * 1024:
                if ms == 1:
                    return "%d %sB" % (sz, pf)
                else:
                    return "%.2f %sB" % (float(sz) / ms, pf)
            ms = ms * 1024
        
def process_page(req):
    if req.conf["genstuff"].has_key("AUTO_RELOAD"):
        del req.conf["genstuff"]["AUTO_RELOAD"]
    functions.write_header(req)
    functions.write_body(req)
    dev_tree = tools.display_list(req)
    dev_tree.add_regexp_field()
    dev_tree.add_devsel_fields(tools.get_device_selection_lists(req.dc, req.user_info.get_idx()))
    dev_tree.query(["H"],
                   ["comment", "bootserver", "dv.val_date", "dv.val_str", "dv.name AS dv_name"],
                   [("device_config", "dc"), ("new_config", "c")],
                   ["dc.new_config=c.new_config_idx", "(dc.device=d.device_idx OR dc.device=d2.device_idx)", "c.name='package_client'"],
                   ["device d2 ON d2.device_idx=dg.device", "device_variable dv ON (dv.device=d.device_idx AND dv.name LIKE('package%'))"],
                   {"dv_name" : ["val_str", "val_date"]})
    # what to display
    op_list = html_tools.selection_list(req, "dt", {"i0" : "Install (overview)",
                                                    "i1" : "Install (detail)",
                                                    "r"  : "RSync sources"})
    # association field
    add_command = html_tools.selection_list(req, "ass", {"a0" : "---",
                                                         "a1" : "add",
                                                         "a2" : "remove"}, auto_reset=True)
    name_re = html_tools.text_field(req, "ipre", size=32, display_len=16)
    an_re = re.compile(".*%s" % (name_re.check_selection("", "") or ""))
    op_mode = op_list.check_selection("", "i0")
    # remove dangling bonds
    req.dc.execute("SELECT 1 FROM device_rsync_config i LEFT JOIN device d ON d.device_idx=i.device WHERE d.name IS NULL")
    if req.dc.rowcount:
        req.dc.execute("SELECT i.device_rsync_config_idx FROM device_rsync_config i LEFT JOIN device d ON d.device_idx=i.device WHERE d.name IS NULL")
        all_dels = [x["device_rsync_config_idx"] for x in req.dc.fetchall()]
        if all_dels:
            req.dc.execute("DELETE FROM device_rsync_config WHERE %s" % (" OR ".join(["device_rsync_config_idx=%d" % (x) for x in all_dels])))
    rsync_dict = rsync_info()
    # fetch rsync config
    rsync_dict.fetch_config(req.dc)
    # check for name_match
    rsync_dict.check_for_name_match(an_re)
    # action log
    action_log = html_tools.message_log()
    # verbose button
    verbose_button = html_tools.checkbox(req, "verb")
    is_verbose = verbose_button.check_selection()
    scon_logs = html_tools.message_log()
    act_logs = html_tools.message_log()
    # deassociate button
    deass_button = html_tools.checkbox(req, "da", auto_reset=1)
    # show only installed packages
    show_installed_button = html_tools.checkbox(req, "soi")
    show_installed = show_installed_button.check_selection()
    # ignore different client-version
    ignore_client_version_button = html_tools.checkbox(req, "icv")
    ignore_client_version = ignore_client_version_button.check_selection()
    if not dev_tree.devices_found() or not rsync_dict.get_num_rsync_objects():
        if not dev_tree.devices_found():
            req.write(html_tools.gen_hline("No devices found", 2))
        if not rsync_dict.get_num_rsync_objects():
            req.write(html_tools.gen_hline("No matching rsync objects defined", 2))
    else:
        dg_sel, d_sel, dg_sel_eff = dev_tree.get_selection()
        ds_dict = dev_tree.get_device_selection_lists()
        sel_table = html_tools.html_table(cls="blindsmall")
        sel_table[0][0] = html_tools.content(dev_tree, "devg", cls="center")
        sel_table[None][0] = html_tools.content(dev_tree, "dev", cls="center")
        if ds_dict:
            sel_table[None][0] = html_tools.content(dev_tree, "sel", cls="center")
            col_span = 3
        else:
            col_span = 2
        # report for problem devices
        sel_table[0][1:col_span] = html_tools.content(["Regexp for Groups ", dev_tree.get_devg_re_field(), " and devices ", dev_tree.get_dev_re_field(),
                                                       "\n, ", dev_tree.get_devsel_action_field(), " selection", dev_tree.get_devsel_field()], cls="center")
        select_button = html_tools.submit_button(req, "select")
        sel_table[0][1:col_span] = html_tools.content(["Verbose: "                   , verbose_button,
                                                       ",\n ignore client versions: ", ignore_client_version_button,
                                                       ",\n show only installed: "   , show_installed_button,
                                                       ",\n display type: "          , op_list,
                                                       ",\n RegExp for name: "       , name_re,
                                                       ", "                          , select_button],  cls="center")
        req.write("<form action=\"%s.py?%s\" method = post>%s</form>\n" % (req.module_name,
                                                                           functions.get_sid(req),
                                                                           sel_table()))
        # refresh-button for devices
        refresh_d_button = html_tools.checkbox(req, "rfrd", auto_reset=1)
        # refresh-button for device_groups
        refresh_dg_button = html_tools.checkbox(req, "rfrdg", auto_reset=1)
        refresh_all = refresh_d_button.check_selection("")
        dev_dict = {}
        if op_mode != "r":
            refresh_list = []
            if d_sel:
                # fetch detailed install - info
                sql_str = "SELECT d.name, d.device_idx, d.device_group, d.device_type, dr.* FROM device d LEFT JOIN device_rsync_config dr ON dr.device=d.device_idx WHERE (%s)" % (" OR ".join(["d.device_idx=%d" % (x) for x in d_sel]))
                req.dc.execute(sql_str)
                for db_rec in req.dc.fetchall():
                    dev_idx = db_rec["device_idx"]
                    if not dev_dict.has_key(dev_idx):
                        new_dev = cdef_device.device(db_rec["name"], dev_idx, db_rec["device_group"], db_rec["device_type"])
                        dev_var_dict = dev_tree.get_dev_struct(db_rec["device_idx"])["dv_name"]
                        new_dev.last_contact = dev_var_dict.get("package_server_last_contact", {"val_date" : None})["val_date"]
                        new_dev.client_version = dev_var_dict.get("package_client_version", {"val_str" : "not set"})["val_str"]
                        dev_dict[dev_idx] = new_dev
                        if refresh_d_button.check_selection(new_dev.get_suffix()) or refresh_all or refresh_dg_button.check_selection("%d" % (db_rec["device_group"])):
                            refresh_list.append(db_rec["name"])
                    else:
                        new_dev = dev_dict[dev_idx]
                    if db_rec["device_rsync_config_idx"]:
                        # use packages field
                        config_idx = db_rec["new_config"]
                        act_rso = rsync_dict.get_rsync_object(config_idx)
                        if not new_dev.packages.has_key(config_idx) and act_rso.get_process_flag():
                            # in the device-structure we store a reference to the resync_object
                            new_dev.packages[config_idx] = rsync_dict.get_rsync_object(config_idx)
            gt_add = add_command.check_selection("", "a0")
            for rsync_idx in rsync_dict.get_sorted_rsync_object_idxs():
                act_rso = rsync_dict.get_rsync_object(rsync_idx)
                glob_add = add_command.check_selection(act_rso.get_suffix(), "a0")
                for dev_idx, act_dev in dev_dict.iteritems():
                    dev_refresh = False
                    loc_add = glob_add == "a0" and gt_add or glob_add
                    if op_mode == "i1":
                        if deass_button.check_selection(act_rso.get_device_suffix(act_dev)):
                            loc_add = "a2"
                    if not act_rso.device_present(dev_idx) and loc_add == "a1":
                        act_rso.add_device(dev_idx, {"name"   : act_dev.get_name(),
                                                     "status" : DEFAULT_STATUS_STRING})
                        # iterate over servers
                        req.dc.execute("INSERT INTO device_rsync_config SET new_config=%d, device=%d" % (act_rso.get_config_idx(), dev_idx))
                        act_dev.packages[act_rso.get_config_idx()] = act_rso
                        dev_refresh = True
                    elif act_rso.device_present(dev_idx) and loc_add == "a2":
                        # iterate over servers
                        req.dc.execute("DELETE FROM device_rsync_config WHERE device=%d AND new_config=%d" % (dev_idx, act_rso.get_config_idx()))
                        act_rso.remove_device(dev_idx)
                        del act_dev.packages[act_rso.get_config_idx()]
                        dev_refresh = True
                    if dev_refresh and act_dev.get_name() not in refresh_list:
                        refresh_list.append(act_dev.get_name())
            if refresh_list:
                tools.iterate_s_commands([tools.s_command(req, "package_server", 8007, "new_rsync_config", sorted(refresh_list), 15)], scon_logs)
                    
        if act_logs:
            req.write(act_logs.generate_stack("Action log"))
        if scon_logs:
            req.write(scon_logs.generate_stack("Connection log"))
        req.write("<form action=\"%s.py?%s\" method = post>%s%s%s%s%s%s" % (req.module_name,
                                                                            functions.get_sid(req),
                                                                            verbose_button.create_hidden_var(),
                                                                            op_list.create_hidden_var(),
                                                                            name_re.create_hidden_var(),
                                                                            show_installed_button.create_hidden_var(),
                                                                            ignore_client_version_button.create_hidden_var(),
                                                                            dev_tree.get_hidden_sel()))
        if op_mode == "r":
            show_info(req, rsync_dict, add_command, True)
        else:
            if d_sel:
                dev_table = html_tools.html_table(cls="normal")
                req.write("%s%s" % (html_tools.gen_hline("Selected %s in %s" % (logging_tools.get_plural("device", len(d_sel)),
                                                                                logging_tools.get_plural("devicegroup", len(dg_sel_eff))),
                                                         2),
                                    dev_table.get_header()))
##                 dict_keys = ["total", "upgrade", "install", "del", "---"]
                oline_idx = 1
                for dg in dg_sel_eff:
                    dev_table[1][1:op_mode == "i0" and 7 or 4] = html_tools.content(dev_tree.get_sel_dev_str(dg), cls="devgroup")
                    dev_table[0][0] = html_tools.content("Name", type="th", cls="center")
                    dev_table[None]["class"] = "line0%d" % (oline_idx)
                    oline_idx = 1 - oline_idx                    
                    if op_mode == "i0":
                        dev_table[None][0] = html_tools.content(["Refresh: ", refresh_dg_button], "%d" % (dg), type="th", cls="center")
                        for what in ["contact", "version", "#", "Status", "Errors"]:
                            dev_table[None][0] = html_tools.content(what, type="th", cls="center")
                    else:
                        for what in ["Name", "Remove", "Status"]:
                            dev_table[None][0] = html_tools.content(what, type="th", cls="center")
                    req.write(dev_table.flush_lines())
                    line_idx = 1
                    if op_mode == "i0":
                        # overview cache table
                        ov_c_table = []
                    for dev in [x for x in d_sel if x in dev_tree.get_sorted_dev_idx_list(dg)]:
                        act_dev = dev_dict[dev]
                        num_dict = {"total" : len(act_dev.packages.keys()),
                                    "wait"  : len([True for act_rso in act_dev.packages.values() if act_rso.get_device_dict(dev)["status"].startswith("w ")]),
                                    "error" : len([True for act_rso in act_dev.packages.values() if act_rso.get_device_dict(dev)["status"].startswith("error ")])}

                        if num_dict["error"]:
                            line_pf = "line2"
                        elif num_dict["wait"]:
                            line_pf = "line3"
                        else:
                            line_pf = "line1"
                        if op_mode == "i0":
                            # actual line
                            act_ov_c_line = [{"content"           : act_dev.get_name(),
                                              "format"            : "left",
                                              "ignore"            : 1,
                                              "collapse_data"     : act_dev.get_name(),
                                              "collapse_function" : collapse_names,
                                              "key"               : "name"}]
                        else:
                            dev_table[0:1 + num_dict["total"]][0] = html_tools.content("%s" % (act_dev.get_name()), cls="left")
                            dev_table[None]["class"] = "%s%d" % (line_pf, line_idx)
                        lc_state, lc_str = get_last_contact_state_and_str(act_dev.last_contact)
                        line_idx = 1 - line_idx
                        info_str = logging_tools.get_plural("rsync object", num_dict["total"])
                        if op_mode == "i0":
                            act_ov_c_line.extend([{"content" : refresh_d_button,
                                                   "format"  : "center",
                                                   "ignore"  : 1},
                                                  {"content"           : lc_str,
                                                   "format"            : "center",
                                                   "key"               : "contact",
                                                   "collapse_data"     : act_dev.last_contact,
                                                   "collapse_function" : collapse_last_contact,
                                                   "ignore"            : 1},
                                                  {"content"           : act_dev.client_version,
                                                   "format"            : "center",
                                                   "key"               : "version",
                                                   "collapse_data"     : act_dev.client_version,
                                                   "collapse_function" : collapse_versions,
                                                   "ignore"            : ignore_client_version},
                                                  {"content" : "%d" % (num_dict["total"]),
                                                   "format"  : "center"},
                                                  {"content" : info_str.replace(" ", "&nbsp;"),
                                                   "format"  : "center"}])
                            if num_dict["error"]:
                                act_ov_c_line.append({"content" : "%s : %s" % (logging_tools.get_plural("Error", num_dict["error"]),
                                                                               ", ".join([x.get_name() for x in act_dev.packages.values() if x.get_device_dict(dev)["status"].startswith("error")])),
                                                      "format"  : "left"})
                            else:
                                act_ov_c_line.append({"content" : "-",
                                                      "format"  : "center"})
                            ov_c_table.append((act_dev.get_suffix(), "%s%d" % (line_pf, line_idx), act_ov_c_line))
                        else:
                            dev_table[None][0:3] = html_tools.content(["Refresh: ", refresh_d_button, "; ",
                                                                        info_str,
                                                                        ", last contact: %s" % (lc_str),
                                                                        ", package_client_version is %s" % (act_dev.client_version)], cls="left")
                        if op_mode == "i1":
                            dev_table.set_cursor(1, 2)
                            act_line_idx = 1
                            for act_rso in act_dev.packages.values():
                                rso_dd = act_rso.get_device_dict(dev)
                                if rso_dd["status"].startswith("error"):
                                    act_line_pf = "line2"
                                elif rso_dd["status"].startswith("w "):
                                    act_line_pf = "line3"
                                else:
                                    act_line_pf = "line1"
                                act_line_idx = 1 - act_line_idx
                                dev_table.set_auto_cr(0)
                                dev_table[0][2] = html_tools.content(act_rso.get_name(), cls="left")
                                dev_table[None]["class"] = "%s%d" % (act_line_pf, act_line_idx)
                                dev_table.set_auto_cr()
                                dev_table[None][0] = html_tools.content(deass_button, act_rso.get_device_suffix(act_dev), cls="center")
                                dev_table[None][0] = html_tools.content(rso_dd["status"] or "not set")
                            req.write(dev_table.flush_lines(act_dev.get_suffix()))
                    if op_mode == "i0":
                        # check for same results for all device_group devices
                        first_line, all_the_same = (None, True)
                        for dev_suffix, line_class, ov_c_line in ov_c_table:
                            if first_line is None:
                                collapse_dict = dict([(x["key"], [x["collapse_data"]]) for x in ov_c_line if x.has_key("key")])
                                first_line = ";".join([x["content"] for x in ov_c_line if not x.get("ignore", False)])
                            else:
                                if ";".join([x["content"] for x in ov_c_line if not x.get("ignore", False)]) != first_line:
                                    all_the_same = False
                                    break
                                else:
                                    for key, value in [(x["key"], x["collapse_data"]) for x in ov_c_line if x.has_key("key")]:
                                        collapse_dict[key].append(value)
                        if all_the_same:
                            dummy_suffix, line_class, ov_c_line = ov_c_table[0]
                            act_row = 0
                            for stuff in ov_c_line:
                                if not act_row:
                                    act_row_f = 0
                                else:
                                    act_row_f = None
                                if stuff.get("ignore", 0):
                                    if stuff.has_key("key"):
                                        content = stuff["collapse_function"](collapse_dict[stuff["key"]])
                                    else:
                                        content = "&nbsp;"
                                else:
                                    content = stuff["content"]
                                dev_table[act_row_f][0] = html_tools.content(content, cls = stuff["format"])
                                if act_row_f == 0:
                                    dev_table[None]["class"] = line_class
                                act_row += 1
                            req.write(dev_table.flush_lines(""))
                        else:
                            for dev_suffix, line_class, ov_c_line in ov_c_table:
                                act_row = 0
                                for stuff in ov_c_line:
                                    if not act_row:
                                        act_row_f = 0
                                    else:
                                        act_row_f = None
                                    dev_table[act_row_f][0] = html_tools.content(stuff["content"], cls = stuff["format"])
                                    if act_row_f == 0:
                                        dev_table[None]["class"] = line_class
                                    act_row += 1
                                req.write(dev_table.flush_lines(dev_suffix))
                req.write(dev_table.get_footer())
                if len(d_sel) > 1:
                    req.write("<div class=\"center\">Refresh all: %s</div>\n" % (refresh_d_button("")))
            else:
                req.write(html_tools.gen_hline("No devices selected", 2))
            show_info(req, rsync_dict, add_command, False)
        req.write("</form>\n")
