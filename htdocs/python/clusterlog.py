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

import functions
import logging_tools
import html_tools
import tools
import datetime

def module_info():
    return {"clo" : {"description"           : "Clusterlog",
                     "default"               : 0,
                     "enabled"               : 1,
                     "left_string"           : "Cluster Log",
                     "right_string"          : "Show and add entries to the Clusterlog",
                     "priority"              : -100,
                     "capability_group_name" : "info"}}

class cluster(object):
    def __init__(self, req):
        self.__dg_names, self.__d_names = ([], [])
        # device_group dict idx/name -> dg
        self.__device_groups = {}
        # device dict idx/name -> d
        self.__devices = {}
        # lut idx/name -> name/idx
        self.__dg_lut = {}
        # lut idx/name -> dg
        self.__device_lut = {}
        # device selection list
        self.__sel_list = html_tools.selection_list(req, "dev", {0 : "all"}, size=5, multiple=True, sort_new_keys=False)
        # new log_entry list
        self.__nle_list = html_tools.selection_list(req, "nld", {}, sort_new_keys=False)
    def add_device_stuff(self, sql_stuff):
        dg_name, dg_idx = (sql_stuff["dg_name"],
                           sql_stuff["device_group_idx"])
        if dg_name not in self.__dg_names:
            self.__dg_names.append(dg_name)
            self.__dg_names.sort()
            new_dg = device_group(dg_name, sql_stuff)
            self.__device_groups[dg_idx]  = new_dg
            self.__device_groups[dg_name] = new_dg
            self.__dg_lut[dg_idx]  = dg_name
            self.__dg_lut[dg_name] = dg_idx
        else:
            new_dg = self.__device_groups[dg_idx]
        d_name, d_idx = (sql_stuff["name"], sql_stuff["device_idx"])
        self.__devices[d_name] = new_dg
        self.__devices[d_idx]  = new_dg
        self.__device_lut[d_name] = d_idx
        self.__device_lut[d_idx]  = d_name
        new_dg.add_device_stuff(sql_stuff)
    def get_device(self, ds):
        return self.__devices[ds].get_device(ds)
    def get_device_group(self, ds):
        return self.__device_groups[ds]
    def populate_sel_list(self):
        nle_sel = None
        for is_cdg in [True, False]:
            for dg_name in self.__dg_names:
                dg = self.__device_groups[dg_name]
                if dg.is_cdg() == is_cdg:
                    dg_idx = self.__dg_lut[dg_name]
                    sel_name = "--- %s (%s%s) ---" % (dg_name,
                                                      dg.is_cdg() and "CDG, " or "",
                                                      dg.get_device_info_str())
                    self.__sel_list[-dg_idx] = {"name"  : sel_name,
                                                "class" : "group"}
                    self.__nle_list[-dg_idx] = {"name"     : sel_name,
                                                "class"    : "group",
                                                "disabled" : True}
                    d_names = dg.get_device_names()
                    # always md-device first
                    for md_c in [True, False]:
                        for d_name in d_names:
                            dev_struct = dg.get_device(d_name)
                            if dev_struct.is_meta_device() == md_c:
                                if is_cdg:
                                    nle_sel = self.__device_lut[d_name]
                                self.__sel_list[self.__device_lut[d_name]] = "%s%s" % (d_name,
                                                                                       dev_struct.get_comment() and " (%s)" % (dev_struct.get_comment()) or "")
                                self.__nle_list[self.__device_lut[d_name]] = "%s%s" % (d_name,
                                                                                       dev_struct.get_comment() and " (%s)" % (dev_struct.get_comment()) or "")
        self.__sel_list.mode_is_normal()
        self.__nle_list.mode_is_normal()
        self.__selected_devices = self.__sel_list.check_selection("", [])
        if nle_sel:
            self.__nle_sel = self.__nle_list.check_selection("", nle_sel)
        else:
            self.__nle_sel = self.__nle_list.check_selection("", 0)
    def get_sel_list(self):
        return self.__sel_list
    def get_nle_list(self):
        return self.__nle_list
    def get_selected_devices(self):
        return self.__selected_devices
    def get_nle_device(self):
        return self.__nle_sel
        
class device_group(object):
    def __init__(self, name, sql_stuff):
        #print "new device_group %s (%d)" % (name, idx)
        self.__name = name
        self.__idx  = sql_stuff["device_group_idx"]
        self.__cdg  = sql_stuff["cluster_device_group"]
        self.__d_names, self.__d_idxs = ([], [])
        self.__devices = {}
        # lut, name/idx -> idx/name
        self.__d_lut = {}
        self.__has_meta_device = False
        self.__comment = ""
    def is_cdg(self):
        return self.__cdg
    def add_device_stuff(self, sql_stuff):
        d_name, d_idx, d_id = (sql_stuff["name"], sql_stuff["device_idx"], sql_stuff["identifier"])
        self.__d_names.append(d_name)
        self.__d_idxs.append(d_idx)
        self.__d_names.sort()
        new_d = device(d_name, d_idx, d_id, sql_stuff["comment"])
        self.__devices[d_idx] = new_d
        self.__devices[d_name] = new_d
        self.__d_lut[d_name] = d_idx
        self.__d_lut[d_idx] = d_name
        if new_d.is_meta_device():
            self.__has_meta_device = True
    def get_device_info_str(self):
        return "%s%s" % (logging_tools.get_plural("device", len(self.__d_names)),
                         self.__has_meta_device and ", with MD" or "")
    def has_meta_device(self):
        return self.__has_meta_device
    def get_device(self, ds):
        return self.__devices[ds]
    def get_device_names(self):
        return self.__d_names
    def get_device_idxs(self):
        return self.__d_idxs
    def get_comment(self):
        return self.__comment

class device(object):
    def __init__(self, name, idx, d_id, comment):
        #print "new device %s (%d, %s)" % (name, idx, d_id)
        self.__name = name
        self.__idx = idx
        self.__comment = comment
        self.__id = d_id
        self.__is_meta_device = self.__id == "MD"
    def get_name(self):
        return self.__name
    def is_meta_device(self):
        return self.__is_meta_device
    def get_comment(self):
        return self.__comment
        
def get_log_level_field(req):
    log_lev_lut = dict([(v["log_level"], k) for k, v in req.log_status_lut.iteritems()])
    log_levs = sorted(log_lev_lut.keys())
    log_lev_field = html_tools.selection_list(req, "llev", {}, sort_new_keys=False)
    for log_lev in log_levs:
        log_idx = log_lev_lut[log_lev]
        log_lev_field[log_idx] = "%s (%d)" % (req.log_status_lut[log_idx]["name"],
                                              log_lev)
    log_lev_field.mode_is_normal()
    def_value = log_lev_lut[log_levs[0]]
    return log_lev_field, log_lev_field.check_selection("", def_value), def_value

def get_log_source_field(req):
    log_descr_lut = dict([(v["description"].lower(), k) for k, v in req.log_source_lut.iteritems()])
    log_descrs = sorted(log_descr_lut.keys())
    log_src_field = html_tools.selection_list(req, "lsrc", {0 : "all"}, sort_new_keys=False, size=5, multiple=True)
    for log_descr in log_descrs:
        log_idx = log_descr_lut[log_descr]
        log_stuff = req.log_source_lut[log_idx]
        log_src_field[log_idx] = "%s (%s)" % (log_stuff["description"] or "<no description>",
                                              log_stuff["name"])
    log_src_field.mode_is_normal()
    return log_src_field, log_src_field.check_selection("", [])

def get_num_lines_field(req):
    nlf = html_tools.selection_list(req, "numl", {}, sort_new_keys=False)
    for nl in [15, 25, 50, 75, 100, 150, 200]:
        nlf[nl] = "%d lines" % (nl)
    nlf.mode_is_normal()
    return nlf, nlf.check_selection("", 15)

def get_search_field(req):
    sf = html_tools.text_field(req, "stf", size=255, display_len=16)
    return sf, sf.check_selection("", "").strip()

class log_lines(object):
    def __init__(self, req, cluster_struct, log_sources, log_levels, user_dict):
        self.__num_lines = 0
        self.__lines = []
        self.__out_table = html_tools.html_table(cls="normal")
        self.__cluster_struct = cluster_struct
        self.__del_button = html_tools.checkbox(req, "dl", auto_reset=True)
        self.__ls_lut, self.__ll_lut = (log_sources, log_levels)
        self.__line_dict = {}
        self.__user_dict = user_dict
        # default value
        self.__range_field = "&nbsp;"
        self.__req = req
        self.enable_extended_logs(False)
        # indices written
        self.__idxs_written, self.__idxs_dict = ([], {})
        self.__starting_idx = None
    def enumerate_lists(self):
        r_idx = self.__starting_idx or 0
        for line in self.__lines:
            r_idx += 1
            line.set_running_idx(r_idx)
    def enable_extended_logs(self, eel):
        self.__extended_logs = eel
    def get_range_field(self):
        return self.__range_field
    def feed_sql_line(self, dc, num_lines):
        self.__lines_to_show = num_lines
        try:
            tg_range_idx = int(self.__req.sys_args.get("range", "0"))
        except:
            tg_range_idx = 0
        self.__range_field = html_tools.selection_list(self.__req, "range", {}, sort_new_keys=False)
        r_start, act_num, act_idx, range_idx = (None, 0, 0, 0)
        last_dl_idx = 0
        for sql_line in dc:
            act_dl_idx = sql_line["devicelog_idx"]
            if act_dl_idx == last_dl_idx:
                act_line = self.__line_dict.get(act_dl_idx, None)
            else:
                if tg_range_idx in [range_idx, range_idx - 1]:
                    if self.__starting_idx is None:
                        self.__starting_idx = act_idx
                    act_line = log_line(sql_line)
                    self.__line_dict[act_line.get_idx()] = act_line
                    self.__lines.append(act_line)
                else:
                    act_line = None
                act_num += 1
                act_idx += 1
                if not r_start:
                    r_start = sql_line["date"]
                    start_idx = act_idx
                if act_num == num_lines:
                    self.__range_field[range_idx] = "%d - %d, %s - %s" % (start_idx,
                                                                          start_idx - 1 + act_num,
                                                                          r_start.strftime("%d. %B %Y %H:%M:%S"),
                                                                          sql_line["date"].strftime("%d. %B %Y %H:%M:%S"))
                    range_idx += 1
                    r_start, act_num = (None, 0)
            if act_line:
                act_line.feed_sql_line(sql_line)
                act_line = None
            last_dl_idx = act_dl_idx
        if act_num:
            self.__range_field[range_idx] = "%d - %d, %s - %s" % (start_idx,
                                                                  start_idx - 1 + act_num,
                                                                  r_start.strftime("%d. %B %Y %H:%M:%S"),
                                                                  sql_line["date"].strftime("%d. %B %Y %H:%M:%S"))
        self.__act_range = self.__range_field.check_selection("", 0)
        self.__num_lines = act_idx
    def get_num_lines(self):
        return self.__num_lines
    def set_dev_sel(self, ds):
        self.__dev_sel = ds
    def get_dev_sel(self):
        return self.__dev_sel
    def set_min_log_level(self, ml):
        self.__min_log_level = ml
    def get_min_log_level(self):
        return self.__min_log_level
    def check_for_changes(self):
        l_del_list, el_del_list = ([], [])
        glob_del = self.__del_button.check_selection("g")
        for line in self.__lines[0 : self.__lines_to_show]:
            ll, ell = line.check_for_changes(self.__del_button, glob_del)
            l_del_list.extend(ll)
            el_del_list.extend(ell)
        if l_del_list:
            num_del = len(l_del_list)
            self.__lines = [x for x in self.__lines if x.get_idx() not in l_del_list]
            for dl in l_del_list:
                del self.__line_dict[dl]
            # init widgets for the next N lines
            for line in self.__lines[self.__lines_to_show - num_del : ]:
                line.check_for_changes(self.__del_button, False)
        if l_del_list:
            self.__req.dc.execute("DELETE FROM devicelog WHERE %s" % (" OR ".join(["devicelog_idx=%d" % (x) for x in l_del_list])))
            self.__req.dc.execute("DELETE FROM extended_log WHERE %s" % (" OR ".join(["devicelog=%d" % (x) for x in l_del_list])))
        if el_del_list:
            self.__req.dc.execute("DELETE FROM extended_log WHERE %s" % (" OR ".join(["extended_log_idx=%d" % (x) for x in el_del_list])))
    def fill_table(self):
        last_date = None
        for line in self.__lines[0 : self.__lines_to_show]:
            self.__idxs_written.append(line.get_running_idx())
            self.__idxs_dict[line.get_running_idx()] = line.get_idx()
            last_date = line.add_to_table(last_date, self.__out_table, self.__del_button, self.__ls_lut, self.__ll_lut, self.__cluster_struct, self.__extended_logs, self.__user_dict)
        self.__out_table[0]["class"] = "line01"
        self.__out_table[None][0] = html_tools.content("---", cls="center")
        self.__out_table[None][0] = html_tools.content(self.__del_button, "g", cls="errormin")
        self.__out_table[None][0:6] = html_tools.content("&nbsp;", cls="center")
    def get_table(self):
        return self.__out_table
    def get_idxs_written(self):
        return self.__idxs_written
    def get_idxs_mapping(self):
        return self.__idxs_dict
    def __nonzero__(self):
        return len(self.__lines)

class log_line(object):
    def __init__(self, sql_stuff):
        self.__date   = datetime.date(sql_stuff["date"].year, sql_stuff["date"].month , sql_stuff["date"].day   )
        self.__time   = datetime.time(sql_stuff["date"].hour, sql_stuff["date"].minute, sql_stuff["date"].second)
        self.__text   = sql_stuff["text"]
        self.__idx    = sql_stuff["devicelog_idx"]
        self.__suffix = "l%d" % (self.__idx)
        self.__device = sql_stuff["device"]
        self.__user   = sql_stuff["user"]
        self.__log_source = sql_stuff["log_source"]
        self.__log_status = sql_stuff["log_status"]
        self.__extended_lines = []
        self.__extended_lines_dict = {}
        self.__el_r_idx = 0
    def get_idx(self):
        return self.__idx
    def set_running_idx(self, idx):
        self.__running_idx = idx
    def get_running_idx(self):
        return self.__running_idx
    def check_for_changes(self, del_button, glob_del):
        l_del_list, el_del_list = ([], [])
        for el in self.__extended_lines:
            el_del_list.extend(el.check_for_changes(del_button, glob_del))
        if el_del_list:
            self.__exteneded_lines = [x for x in self.__extended_lines if x.get_idx() not in el_del_list]
        if del_button.check_selection(self.__suffix) or glob_del:
            l_del_list.append(self.get_idx())
        return l_del_list, el_del_list
    def get_num_extended_lines(self):
        return self.__el_r_idx
    def feed_sql_line(self, sql_line):
        if sql_line["extended_log_idx"]:
            self.__el_r_idx += 1
            new_el = extended_log_line(self.__el_r_idx, sql_line)
            self.__extended_lines_dict[new_el.get_idx()] = new_el
            self.__extended_lines.append(new_el)
    def get_date_time(self):
        return self.__date, self.__time
    def get_suffix(self):
        return self.__suffix
    def add_to_table(self, last_date, ht, del_button, ls_lut, ll_lut, c_struct, with_el, user_dict):
        if self.__date != last_date:
            last_date = self.__date
            headers = ["Idx", "del", "device", "EL", "time", "source", "text", "status"]
            ht[0]["class"] = "line01"
            ht[None][0:len(headers)] = html_tools.content(last_date.strftime("%A, %d. %B %Y"), type="th", cls="center")
            ht[0]["class"] = "line00"
            for what in headers:
                ht[None][0] = html_tools.content(what, cls="center")
        if with_el:
            tot_height = 2 * self.__el_r_idx + 1
        else:
            tot_height = 1
        ht[0]["class"] = "line1%d" % (self.__running_idx % 2)
        ht[None:tot_height][0] = html_tools.content("%d" % (self.__running_idx), cls="left")
        ht[None:tot_height][0] = html_tools.content(del_button, self.__suffix, cls="errormin")
        try:
            ht[None][0] = html_tools.content(c_struct.get_device(self.__device).get_name(), cls="center")
        except:
            ht[None][0] = html_tools.content(" --- ", cls="center")
        ht[None][0] = html_tools.content(self.__el_r_idx and "%d" % (self.__el_r_idx) or "-", cls="center")
        ht[None][0] = html_tools.content(self.__time.strftime("%H:%M:%S"), cls="center")
        if ls_lut[self.__log_source]["identifier"] == "user":
            log_src_str = "user: %s" % (user_dict.get(self.__user, "unknown user"))
        else:
            log_src_str = ls_lut[self.__log_source]["description"] or ls_lut[self.__log_source]["name"]
        ht[None][0] = html_tools.content(log_src_str, cls="left")
        ht[None][0] = html_tools.content(self.__text, cls="left")
        if self.__log_status:
            ht[None][0] = html_tools.content("%s (%d)" % (ll_lut[self.__log_status]["name"],
                                                          ll_lut[self.__log_status]["log_level"]), cls="center")
        else:
            ht[None][0] = html_tools.content("not set", cls="center")
        if with_el:
            for e_log in self.__extended_lines:
                e_log.add_to_table(ht, del_button, ls_lut, ll_lut, c_struct, user_dict)
        return last_date

class extended_log_line(object):
    def __init__(self, r_idx, sql_stuff):
        self.__running_idx = r_idx
        self.__date        = datetime.date(sql_stuff["el_date"].year, sql_stuff["el_date"].month , sql_stuff["el_date"].day   )
        self.__time        = datetime.time(sql_stuff["el_date"].hour, sql_stuff["el_date"].minute, sql_stuff["el_date"].second)
        self.__idx         = sql_stuff["extended_log_idx"]
        self.__user        = sql_stuff["user"]
        self.__users       = sql_stuff["users"]
        self.__subject     = sql_stuff["subject"]
        self.__description = sql_stuff["description"]
        self.__log_source  = sql_stuff["log_source"]
        self.__suffix = "el%d" % (self.__idx)
    def check_for_changes(self, del_button, glob_del):
        delete_me = del_button.check_selection(self.__suffix)
        if delete_me or glob_del:
            return [self.__idx]
        else:
            return []
    def get_idx(self):
        return self.__idx
    def get_suffix(self):
        return self.__suffix
    def add_to_table(self, ht, del_button, ls_lut, ll_lut, c_struct, user_dict):
        ht[0]["class"] = "white"
        ht[None][3] = html_tools.content(self.__users, cls="left")
        ht[None][0] = html_tools.content(del_button, self.get_suffix(), cls="errormin")
        ht[None][0] = html_tools.content("&nbsp;", cls="center")
        if ls_lut[self.__log_source]["identifier"] == "user":
            log_src_str = "user: %s" % (user_dict.get(self.__user, "unknown user"))
        else:
            log_src_str = ls_lut[self.__log_source]["description"] or ls_lut[self.__log_source]["name"]
        ht[None][0] = html_tools.content(log_src_str, cls="left")
        ht[None][0:2] = html_tools.content(self.__subject, cls="left")
        ht[0]["class"] = "white"
        ht[None][3:8] = html_tools.content("<textarea style=\"width=10%%; font-family:monospace; font-style:normal; font-size:9pt; \" cols=\"100\" rows=\"%d\" readonly>%s</textarea>\n" % (max(4, min(len(self.__description.split("\n")), 10)),
                                                                                                                                                                                            self.__description), cls="left")

def fetch_log_lines(req, my_cluster, num_lines, all, als, with_el, search_text):
    sql_str = "SELECT user_idx, login FROM user"
    req.dc.execute(sql_str)
    user_dict = dict([(x["user_idx"], x["login"]) for x in req.dc])
    act_logs = log_lines(req, my_cluster, req.log_source_lut, req.log_status_lut, user_dict)
    act_logs.enable_extended_logs(with_el)
    dev_sel = my_cluster.get_selected_devices()
    act_logs.set_dev_sel(dev_sel)
    if not dev_sel or not als:
        pass
    else:
        # resolve device-groups
        if min(dev_sel) < 0:
            dev_sel = [x for x in dev_sel if x > 0] + sum([my_cluster.get_device_group(-x).get_device_idxs() for x in dev_sel if x < 0], [])
        min_log_lev = req.log_status_lut[all]["log_level"]
        log_lev_idxs = [k for k, v in req.log_status_lut.iteritems() if v["log_level"] >= min_log_lev]
        sql_str = "SELECT dl.devicelog_idx, dl.device, dl.log_source, dl.user, dl.log_status, dl.text, dl.date, el.extended_log_idx, el.log_source AS el_log_source, el.user AS el_user, el.users, el.subject, el.description, el.date AS el_date " \
                  "FROM devicelog dl LEFT JOIN extended_log el ON el.devicelog=dl.devicelog_idx " \
                  "WHERE (%s) AND (%s) AND (%s) AND (%s) ORDER BY dl.date DESC" % (0 in dev_sel and "1" or " OR ".join(["dl.device=%d" % (x) for x in dev_sel]),
                                                                                   0 in als and "1" or " OR ".join(["dl.log_source=%d" % (x) for x in als]),
                                                                                   " OR ".join(["dl.log_status=%d" % (x) for x in log_lev_idxs + [0]]),
                                                                                   search_text and "dl.text LIKE(%s) OR el.description LIKE(%s)" or "1")
        if search_text:
            req.dc.execute(sql_str, ("%%%s%%" % (search_text), "%%%s%%" % (search_text)))
        else:
            req.dc.execute(sql_str)
        lines_found = req.dc.rowcount
        act_logs.set_min_log_level(min_log_lev)
        act_logs.feed_sql_line(req.dc, num_lines)
        act_logs.check_for_changes()
        act_logs.enumerate_lists()
    return act_logs

def show_log(req, act_logs, als):
    dev_sel = act_logs.get_dev_sel()
    if not dev_sel or not als:
        req.write(html_tools.gen_hline(", ".join((not dev_sel and ["no devices selected"] or []) +
                                                 (not als and ["no log_sources selected"] or [])), 3))
    else:
        req.write(html_tools.gen_hline("Showing logs for %s, %s, log_level >= %d, found %s:" % (0 in dev_sel and "all devices" or logging_tools.get_plural("device", len(dev_sel)),
                                                                                                0 in als and "all log_sources" or logging_tools.get_plural("log_source", len(als)),
                                                                                                act_logs.get_min_log_level(),
                                                                                                logging_tools.get_plural("line", act_logs.get_num_lines())), 3))
        act_logs.fill_table()
        req.write(act_logs.get_table()(""))

def check_for_new_log_entry(req, my_cluster, log_lev_field, default_log_level):
    log_text_field = html_tools.text_field(req, "lt", size=255, display_len=32, auto_reset=True)
    users_field = html_tools.text_field(req, "elu", size=255, display_len=24, auto_reset=True)
    subject_field = html_tools.text_field(req, "els", size=255, display_len=32)
    extended_text = html_tools.text_area(req, "elt", min_col_size=100, min_row_size=10)
    try:
        new_ext_idx = int(req.sys_args.get("atln", "0"))
    except:
        new_ext_idx = 0
    new_dev = my_cluster.get_nle_device()
    new_log_lev = log_lev_field.check_selection("n", default_log_level)
    new_log_text = log_text_field.check_selection("n", "").strip()
    new_ext_users = users_field.check_selection("e", "").strip()
    new_ext_subject = subject_field.check_selection("e", "").strip()
    new_ext_text = extended_text.check_selection("e", "").strip()
    user_log_source_idx = req.log_source.get("user", {"log_source_idx" : 0})["log_source_idx"]
    if new_log_text:
        req.dc.execute("INSERT INTO devicelog VALUES(0, %s, %s, %s, %s, %s, null)", (new_dev,
                                                                                           user_log_source_idx,
                                                                                           req.user_info.get_idx(),
                                                                                           new_log_lev,
                                                                                           new_log_text))
        if new_ext_idx == 0:
            new_ext_idx = req.dc.insert_id()
    if new_ext_idx and new_ext_users and new_ext_text and new_ext_subject:
        req.dc.execute("INSERT INTO extended_log VALUES(0, %s, %s, %s, %s, %s, %s, null)", (new_ext_idx,
                                                                                                  user_log_source_idx,
                                                                                                  req.user_info.get_idx(),
                                                                                                  new_ext_users,
                                                                                                  new_ext_subject,
                                                                                                  new_ext_text))
    return log_text_field, users_field, subject_field, extended_text
    
def show_new_log_entry(req, my_cluster, log_lines, log_lev_field, (log_text_field, users_field, subject_field, extended_text)):
    new_idx_f = html_tools.selection_list(req, "atl", {0 : "new entry"}, sort_new_keys=False)
    idx_map = log_lines.get_idxs_mapping()
    for idx in log_lines.get_idxs_written():
        new_idx_f[idx_map[idx]] = "%d" % (idx)
    new_idx_f.mode_is_normal()
    new_idx_f.check_selection("n", 0)
    new_table = html_tools.html_table(cls="normalsmall")
    new_table[0]["class"] = "line01"
    new_table[None][0] = html_tools.content(["Device: ", my_cluster.get_nle_list()], "", cls="left")
    new_table[None][0] = html_tools.content(["Log level: ", log_lev_field], "n", cls="left")
    new_table[None][0] = html_tools.content(["Text: ", log_text_field], "n", cls="left")
    new_table[0]["class"] = "line00"
    new_table[None][0] = html_tools.content(["Add extened log to: ", new_idx_f], "n", cls="left")
    new_table[None][0] = html_tools.content(["Users: ", users_field], "e", cls="left")
    new_table[None][0] = html_tools.content(["Subject: ", subject_field], "e", cls="left")
    new_table[0]["class"] = "line00"
    new_table[None][0:3] = html_tools.content(extended_text, "e", cls="left")
    req.write("%s%s" % (html_tools.gen_hline("New logentry", 3),
                        new_table("")))
    
def process_page(req):
    if req.conf["genstuff"].has_key("AUTO_RELOAD"):
        del req.conf["genstuff"]["AUTO_RELOAD"]
    functions.write_header(req)
    functions.write_body(req)
    # init log and status
    tools.init_log_and_status_fields(req)
    # user log_source idx
    user_log_source_idx = req.log_source.get("user", {"log_source_idx" : 0})["log_source_idx"]
    # fetch device tree
    my_cluster = cluster(req)
    req.dc.execute("SELECT d.name, d.device_idx, dg.name AS dg_name, dg.cluster_device_group, d.comment, dg.device_group_idx, dt.identifier FROM device d INNER JOIN device_type dt INNER JOIN device_group dg WHERE dt.device_type_idx=d.device_type AND d.device_group=dg.device_group_idx ORDER BY dg.name, d.name")
    for db_rec in req.dc.fetchall():
        my_cluster.add_device_stuff(db_rec)
    my_cluster.populate_sel_list()
    log_lev_field  , act_log_level, default_log_level = get_log_level_field(req)
    log_src_field  , act_log_src   = get_log_source_field(req)
    num_lines_field, act_num_lines = get_num_lines_field(req)
    search_field, search_sel       = get_search_field(req)
    with_extended_field = html_tools.checkbox(req, "wel")
    with_extended = with_extended_field.check_selection("")
    # select button
    select_button = html_tools.submit_button(req, "select")
    # submit_button
    submit_button = html_tools.submit_button(req, "submit")
    sel_table = html_tools.html_table(cls="blindsmall")
    sel_table[0][0] = html_tools.content(my_cluster.get_sel_list(), "", cls="center")
    sel_table[None][0] = html_tools.content(log_src_field, "", cls="center")
    new_log_stuff = check_for_new_log_entry(req, my_cluster, log_lev_field, default_log_level)
    log_lines = fetch_log_lines(req, my_cluster, act_num_lines, act_log_level, act_log_src, with_extended, search_sel)
    sel_table[0][0:2] = html_tools.content(["Show ", num_lines_field, " with log level ", log_lev_field, " or higher", ", extended logs: ", with_extended_field], "", cls="center")
    sel_table[0][0:2] = html_tools.content(["Search for text ", search_field, ", ", log_lines.get_range_field(), ", ", select_button], "", cls="center")
    req.write("<form action=\"%s.py?%s\" method=post>%s</form>" % (req.module_name,
                                                                   functions.get_sid(req),
                                                                   sel_table("")))
    req.write("<form action=\"%s.py?%s\" method=post>" % (req.module_name,
                                                          functions.get_sid(req)))
    show_log(req, log_lines, act_log_src)
    show_new_log_entry(req, my_cluster, log_lines, log_lev_field, new_log_stuff)
    req.write("<div class=\"center\">%s</div>%s</form>" % (submit_button(""),
                                                           "".join([type(x) != type("") and x.create_hidden_var("") or "" for x in [num_lines_field, log_lev_field, log_lines.get_range_field(), with_extended_field, my_cluster.get_sel_list(), log_src_field]])))
        
