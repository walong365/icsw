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
""" package install frontend """

import time
import re
import logging_tools
import functions
import tools
import html_tools
import cdef_device
import cdef_packages

CONN_TIMEOUT = 5

def module_info():
    return {"pi" : {"description"           : "Package install",
                    "enabled"               : 1,
                    "default"               : 0,
                    "left_string"           : "Package install",
                    "right_string"          : "Install packages without rebooting",
                    "capability_group_name" : "conf",
                    "priority"              : 40}}

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

def show_sets(req):
    
    print "***"

def show_maintenance(req, ip_dict, grp_dict, all_groups, groups_list, html_stuff, assoc_command, tstate_command, nodep_flag, force_flag, sort_mode, overview=0, dev_dict={}, show_associated=0, add_device_list=0):
    def write_ip_header():
        ov_table[0][0] = html_tools.content("Name", type="th")
        ov_table[None]["class"] = "line00"
        out_list = []
        #if not overview or sort_mode in ["a1", "a2", "a3"]:
        out_list  = ["Group"]
        out_list += ["Arch", "Version", "Release", "disk"]
        if not overview or overview.endswith("b"):
            out_list += ["Size", "mode", "Builddate"]
        if not overview:
            out_list += ["Packager", "Buildhost"]
        if dev_dict:
            out_list += ["assigned&nbsp;to", "assign", "action", "nodeps", "force", "k&nbsp;/&nbsp;u&nbsp;/&nbsp;i&nbsp;/&nbsp;e", "wait", "error"]
        else:
            out_list += ["Associations"]
        for what in out_list:
            ov_table[None][0] = html_tools.content(what, type="th", cls="center")
    def show_ip(ip):
        if ip:
            ov_table[0][0] = html_tools.content(ip.get_name(), cls="left")
        else:
            ov_table[0][0] = html_tools.content("general", cls="left")
        line_pf = "line1"
        if ip:
            if overview and sort_mode in ["a1", "a2", "a3"]:
                ov_table[None][0] = html_tools.content(ip["pgroup"], cls="center")
            else:
                ov_table[None][0] = html_tools.content(groups_list, cls="center")
            ov_table[None][0] = html_tools.content(ip["arch"], cls="center")
            ov_table[None][0] = html_tools.content(ip["version"], cls="center")
            ov_table[None][0] = html_tools.content(ip["release"], cls="center")
            ov_table[None][0] = html_tools.content("yes" if ip["present_on_disk"] else "no", cls="center")
            if not ip["present_on_disk"]:
                line_pf = "error"
        else:
            if overview and sort_mode in ["a1", "a2", "a3"]:
                ov_table[None][0] = html_tools.content("---", cls="center")
            else:
                ov_table[None][0] = html_tools.content("---", cls="center")
            ov_table[None][0:4] = html_tools.content("---", cls="center")
        if ip:
            if not overview or overview.endswith("b"):
                ov_table[None][0] = html_tools.content(get_size_str(ip["size"]), cls="right")
                ov_table[None][0] = html_tools.content(method_list, ip.get_suffix(), cls="center")
                if ip["buildtime"]:
                    ov_table[None][0] = html_tools.content(time.strftime("%a, %d. %b %Y, %H:%M:%S", time.localtime(ip["buildtime"])), cls="right")
                else:
                    ov_table[None][0] = html_tools.content("unknown", cls="center")
            if not overview:
                if ip["packager"].endswith(ip["buildhost"]):
                    ov_table[None][0] = html_tools.content(ip["packager"][0:len(ip["packager"]) - len(ip["buildhost"])], cls="right")
                else:
                    ov_table[None][0] = html_tools.content(ip["packager"], cls="right")
                ov_table[None][0] = html_tools.content(ip["buildhost"], cls="left")
        else:
            if not overview or overview.endswith("b"):
                ov_table[None][0:3] = html_tools.content("---", cls="center")
            if not overview:
                ov_table[None][0:2] = html_tools.content("---", cls="center")
        if dev_dict:
            if ip:
                dev_len = len(dev_dict.keys())
                instp_list = [[y for y in dev_dict[dev_idx].packages.values() if y["inst_package"] == ip["inst_package_idx"]][0] for dev_idx in ip.devices]
                if add_device_list:
                    dev_instp_list = sorted([[dev_dict[dev_idx].get_name() for y in dev_dict[dev_idx].packages.values() if y["inst_package"] == ip["inst_package_idx"]][0] for dev_idx in ip.devices])
                if dev_len == len(instp_list):
                    if add_device_list:
                        ov_table[None][0] = html_tools.content("all (%s)" % (logging_tools.compress_list(dev_instp_list)), cls="center")
                    else:
                        ov_table[None][0] = html_tools.content("all", cls="center")
                elif not len(instp_list):
                    ov_table[None][0] = html_tools.content("none", cls="center")
                else:
                    if add_device_list:
                        ov_table[None][0] = html_tools.content("%d of %d (%s)" % (len(instp_list), dev_len, logging_tools.compress_list(dev_instp_list)), cls="center")
                    else:
                        ov_table[None][0] = html_tools.content("%d of %d" % (len(instp_list), dev_len), cls="center")
            else:
                ov_table[None][0] = html_tools.content("---", cls="center")
                instp_list = []
            ov_table[None][0] = html_tools.content(assoc_command, cls="center")
            ov_table[None][0] = html_tools.content(tstate_command, cls="center")
            ov_table[None][0] = html_tools.content(nodep_flag, cls="center")
            ov_table[None][0] = html_tools.content(force_flag, cls="center")
            if instp_list:
                num_dict = {"upgrade" : len([x for x in instp_list if x["upgrade"]]),
                            "install" : len([x for x in instp_list if x["install"]]),
                            "erase"   : len([x for x in instp_list if x["del"]])}
                num_dict["---"] = len(instp_list) - (num_dict["upgrade"] + num_dict["install"] + num_dict["erase"])
                num_dict["error"] = len([x for x in instp_list if x["status"].startswith("error ")])
                num_dict["wait"] = len([x for x in instp_list if x["status"].startswith("w ") or not x["status"]])
                if num_dict["error"]:
                    line_pf = "line2"
                elif num_dict["wait"]:
                    line_pf = "line3"
                ov_table[None][0] = html_tools.content("%(---)d / %(upgrade)d / %(install)d / %(erase)d" % num_dict, cls="center")
                for nk in ["wait", "error"]:
                    ov_table[None][0] = html_tools.content(num_dict[nk], cls="center")
            else:
                for i in range(3):
                    ov_table[None][0] = html_tools.content("-", cls="center")
        else:
            if ip:
                if ip.devcount:
                    if overview:
                        ov_table[None][0] = html_tools.content("%s" % (logging_tools.get_plural("device", ip.devcount)),
                                                               cls="left")
                    else:
                        ov_table[None][0] = html_tools.content("%s: %s" % (logging_tools.get_plural("device", ip.devcount),
                                                                           logging_tools.compress_list(ip.dev_list)), cls="left")
                else:
                    if overview:
                        ov_table[None][0] = html_tools.content("-", cls="center")
                    else:
                        ov_table[None][0] = html_tools.content(["del:", del_button], cls="errorcenter")
            else:
                ov_table[None][0] = html_tools.content("-", cls="center")
        if line_pf.startswith("line"):
            line_pf = "%s%d" % (line_pf, line_idx)
        ov_table[None]["class"] = line_pf
    del_button, method_list = html_stuff
    ov_table = html_tools.html_table(cls="normalsmall")
    all_groups = sorted(grp_dict.keys())
    req.write("%s%s" % (html_tools.gen_hline("Package %s (%s in %s)" % (overview and "overview" or "maintenance",
                                                                        logging_tools.get_plural("package", len([1 for x in ip_dict.values() if x.show_it])),
                                                                        logging_tools.get_plural("group", len(all_groups))), 2),
                      ov_table.get_header()))
    if sort_mode in ["a1", "a2", "a3"]:
        if sort_mode == "a1":
            sort_ks = [(k, v.get_name()) for k, v in ip_dict.iteritems()]
        elif sort_mode == "a2":
            sort_ks = [(k, v["size"]) for k, v in ip_dict.iteritems()]
        else:
            sort_ks = [(k, v["buildtime"]) for k, v in ip_dict.iteritems()]
        all_sort_dict = {}
        for idx, k in sort_ks:
            all_sort_dict.setdefault(k, []).append(idx)
        write_ip_header()
        any_written = 0
        line_idx = 1
        for ip_idxs in [all_sort_dict[x] for x in sorted(all_sort_dict.keys())]:
            for ip in [ip_dict[ip_idx] for ip_idx in ip_idxs]:
                #ip["group_idx"] = all_groups.index(ip["pgroup"]) + 1
                if ip.show_it:
                    any_written = 1
                    show_ip(ip)
                    line_idx = 1 - line_idx
                    req.write(ov_table.flush_lines(ip.get_suffix()))
        if any_written:
            ov_table[0][0:13] = html_tools.content("Global setting", cls="center", type="th")
            ov_table[None]["class"] = "line01"
            show_ip(None)
            req.write(ov_table.flush_lines(""))
        
    else:
        if overview:
            if dev_dict:
                header_len = overview.endswith("b") and 17 or 14
            else:
                header_len = overview.endswith("b") and 10 or 7
        else:
            header_len = 12
        any_written = 0
        for group, act_groups in [(x, grp_dict[x]) for x in all_groups]:
            if sort_mode == "p%d" % (all_groups.index(group)) or sort_mode == "a0":
                loc_archs_dict = {}
                for ip in act_groups.itervalues():
                    loc_archs_dict.setdefault(ip["arch"], 0)
                    loc_archs_dict[ip["arch"]] += 1
                loc_archs = sorted(loc_archs_dict.keys())
                ip_header_written = 0
                line_idx = 1
                for ip_idx, ip in act_groups.iteritems():
                    #ip["group_idx"] = all_groups.index(group)+1
                    if ip.show_it:
                        if not ip_header_written:
                            ov_table[0][0:header_len] = html_tools.content("%s (%s), %s: %s" % (group,
                                                                                                logging_tools.get_plural("package", len(act_groups)),
                                                                                                logging_tools.get_plural("architecture", len(loc_archs)),
                                                                                                ", ".join(["%s (%d)" % (x, loc_archs_dict[x]) for x in loc_archs])), cls="center", type="th")
                            ov_table[None]["class"] = "line01"
                            write_ip_header()
                            ip_header_written = 1
                        any_written = 1
                        show_ip(ip)
                        line_idx = 1 - line_idx
                        req.write(ov_table.flush_lines(ip.get_suffix()))
        if any_written:
            ov_table[0][0:header_len] = html_tools.content("Global setting", cls="center", type="th")
            ov_table[None]["class"] = "line01"
            show_ip(None)
            req.write(ov_table.flush_lines(""))
    req.write(ov_table.get_footer())
    submit_button = html_tools.submit_button(req, "submit")
    req.write("<div class=\"center\">%s</div>\n" % (submit_button()))

def check_for_group_changes(req, scon_logs, ip_dict, list_field, html_stuff, all_groups, log, verbose):
    del_button, method_list = html_stuff
    grp_dict = {}
    # check for changes
    del_dict = {}
    for ip_idx, ip in ip_dict.iteritems():
        if not ip.devices and del_button.check_selection(ip.get_suffix()):
            del_dict[ip_idx] = ip["inst_package_idx"]
            if log:
                log.add_ok("Deleting package '%s-%s-%s'" % (ip.get_name(), ip["version"], ip["release"]), "SQL")
        else:
            act_grp = all_groups.index(ip["pgroup"]) + 1
            new_grp = list_field.check_selection(ip.get_suffix(), act_grp)
            if new_grp != act_grp:
                ip["pgroup"] = all_groups[new_grp - 1]
                if verbose:
                    log.add_ok("Changing group of '%s' from '%s' to '%s'" % (ip.get_name(), all_groups[act_grp - 1], all_groups[new_grp - 1]), "SQL")
            ip.commit_sql_changes(req.dc, 1, 0)
            grp_dict.setdefault(ip["pgroup"], tools.ordered_dict())
            grp_dict[ip["pgroup"]][ip_idx] = ip
            # method
            act_m = method_list.check_selection(ip.get_suffix(), ip["native"])
            if ip["native"] != act_m:
                log.add_ok("Changing install method of '%s' from %d to %d" % (ip.get_name(), ip["native"], act_m), "SQL")
                ip["native"] = act_m
                req.dc.execute("UPDATE inst_package SET native=%d WHERE inst_package_idx=%d" % (act_m, ip["inst_package_idx"]))
    if del_dict:
        for d_idx in del_dict.keys():
            del ip_dict[d_idx]
        #req.dc.execute("DELETE FROM inst_package WHERE (%s)" % (" OR ".join(["inst_package_idx=%d" % (x) for x in del_dict.values()])))
        tools.iterate_s_commands([tools.s_command(req, "package_server", 8007, "delete_packages", [], timeout=CONN_TIMEOUT, add_dict={"package_idxs" : del_dict.values()})], scon_logs)
    return grp_dict

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

#----------------------------------------------------------------------------------------------------
# here starts the beta-code, see also partitionutility.py
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

class package_set(db_object):
    def __init__(self, req, **args):
        self.__req = req
        self.__root = args["root"]
        self.__template = args.get("template", False)
        db_object.__init__(self, self.__req, db_rec=args.get("db_rec", {}),
                           primary_db="package_set",
                           index_field="package_set_idx")
        if args.get("create", False):
            # reate new entitiy
            if self.__req.dc.execute("INSERT INTO package_set SET name=%s", (self["name"])):
            # get dictionary from db to get the correct default-values
                self.__req.dc.execute("SELECT * FROM package_set WHERE package_set_idx=%d" % (self.__req.dc.insert_id()))
                self.db_rec = self.__req.dc.fetchone()
            else:
                # unable to add new package_set
                raise ValueError, "unable to create database record"
        if not self.__template:
            self.unique_id = "gs%d" % (self["package_set_idx"])
            self.idx = self["package_set_idx"]
    def create_content(self, act_ti):
        req = self.__req
        if self.__template:
            ret_f = ["<td class=\"left\" colspan=\"2\">New: <input name=\"%s\" value=\"\"/></td>" % (self.__root.get_new_idx("package_set"))]
        else:
            ret_f = ["<td class=\"left\"><input name=\"{attr.unique_id}n\" value=\"{db.name}\"></td>"]
            if self["count"]:
                ret_f.append("<td class=\"center\">%d</td>" % (self["count"]))
            else:
                ret_f.append("<td class=\"errormin\"><input type=checkbox name=\"{attr.unique_id}del\" /></td>")
        return "<tr class=\"line1%d\">%s</tr>" % (act_ti.get_iterator(0),
                                                  "".join(self.expand(ret_f)))
#     def __getitem__(self, key):
#         return super(genstuff, self).__getitem__(key)
    def feed_args(self, args):
        if self.__template:
            new_name = args.get(self.__root.get_new_idx("package_set"), "")
            if new_name:
                # validate new_args
                if new_name in self.__root.get_tree_content("package_set", "name"):
                    # name already used, pass
                    pass
                else:
                    # generate new genstuff
                    try:
                        self.__root.add_leaf("package_set", package_set(self.__req, root=self.__root, create=True, db_rec={"name" : new_name}))
                    except:
                        # error creating
                        pass
        else:
            if args.has_key("%sn" % (self.unique_id)) and self.idx:
                if args.has_key("%sdel" % (self.unique_id)):
                    # delete entry
                    self.__root.delete("package_set", self)
                    self.__req.dc.execute("DELETE FROM package_set WHERE package_set_idx=%d" % (self.idx))
                else:
                    new_name = args["%sn" % (self.unique_id)]
                    if self["name"] != new_name:
                        self["name"] = new_name
    def commit_changes(self):
        self.commit_db_changes(self.idx)

class package_set_tree(object):
    def __init__(self, req, action_log):
        self.req = req
        self.__action_log = action_log
        self.__dict = {"package_set" : {}}
    def read_from_db(self):
        self.req.dc.execute("SELECT p.package_set_idx, p.name, COUNT(ip.location) AS count FROM package_set p LEFT JOIN inst_package ip ON p.package_set_idx=ip.package_set GROUP BY p.package_set_idx")
        for db_rec in self.req.dc.fetchall():
            new_ps = package_set(self.req, db_rec=db_rec, root=self)
            self.add_leaf("package_set", new_ps)
        # count main-packages
        self.req.dc.execute("SELECT COUNT(ip.location) AS count FROM inst_package ip WHERE ip.package_set=0")
        self.add_leaf("package_set", package_set(self.req, db_rec={"name"            : "MAIN",
                                                                   "package_set_idx" : 0,
                                                                   "count"           : self.req.dc.fetchone()["count"]}, root=self))
        self.__new_ps = package_set(self.req, template=True, root=self)
    def add_leaf(self, tree_name, new_ps):
        self.__dict[tree_name][new_ps.idx] = new_ps
    def get_tree_content(self, tree_name, df_name):
        return [value[df_name] for value in self.__dict[tree_name].itervalues()]
    def validate_tree(self):
        pass
    def get_new_idx(self, tree_name):
        return "new%s" % (tree_name)
    def delete(self, tree_name, obj):
        del self.__dict[tree_name][obj.idx]
    def parse_values(self):
        args = self.req.sys_args
        for gs_stuff in self.__dict["package_set"].values() + [self.__new_ps]:
            gs_stuff.feed_args(args)
    def commit_changes(self):
        args = self.req.sys_args
        for gs_stuff in self.__dict["package_set"].values():
            gs_stuff.commit_changes()
    def create_content(self):
        req = self.req
        act_ti = table_iterator()
        table_content = []
        for gs_idx, gs_stuff in self.__dict["package_set"].iteritems():
            table_content.append(gs_stuff.create_content(act_ti))
        table_content.append(self.__new_ps.create_content(act_ti))
        req.write("<table class=\"normalsmall\">%s</table>" % ("\n".join(table_content)))
        submit_button = html_tools.submit_button(req, "submit")
        req.write("<div class=\"center\">%s</div>\n" % (submit_button()))

# here ends the beta-code, see also partitionutility.py
#----------------------------------------------------------------------------------------------------

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
                   [("device_config", "dc"),
                    ("new_config", "c")],
                   ["dc.new_config=c.new_config_idx",
                    "(dc.device=d.device_idx OR dc.device=d2.device_idx)",
                    "c.name='package_client'"],
                   ["device d2 ON d2.device_idx=dg.device",
                    "device_variable dv ON (dv.device=d.device_idx AND dv.name LIKE('package%'))"],
                   {"dv_name" : ["val_str", "val_date"]})
    # sort-by list
    sort_list = html_tools.selection_list(req, "sb", {"a0" : "Show all, order by Group and Name",
                                                      "a1" : "Show all, order By Name",
                                                      "a2" : "Show all, order By Size",
                                                      "a3" : "Show all, order By Builddate"}, size=5)
    # what to display
    op_list = html_tools.selection_list(req, "dt", {"i0a" : "Install (overview, small)",
                                                    "i0b" : "Install (overview, big)",
                                                    "i1a" : "Install (detail, small)",
                                                    "i1b" : "Install (detail, big)",
                                                    "m"   : "Maintenance",
                                                    "s"   : "Sets"})
    # association field
    assoc_command = html_tools.selection_list(req, "ass", {"a0" : "---",
                                                           "a1" : "remove",
                                                           "a2" : "attach"}, auto_reset=1)
    # target state
    tstate_command = html_tools.selection_list(req, "ts", {"a0" : "---",
                                                           "a1" : "install",
                                                           "a2" : "upgrade",
                                                           "a3" : "erase"}, auto_reset=1)
    # nodep flag
    nodep_flag = html_tools.selection_list(req, "ndf", {"a0" : "---",
                                                        "a1" : "--nodeps",
                                                        "a2" :"normal"}, auto_reset=1)
    # force flag
    force_flag = html_tools.selection_list(req, "frf", {"a0" : "---",
                                                        "a1" : "--force",
                                                        "a2" : "normal"}, auto_reset=1)
    name_re = html_tools.text_field(req, "ipre", size=32, display_len=16)
    an_re = re.compile("%s" % (name_re.check_selection("", "") or ".*"))
    op_mode = op_list.check_selection("", "i0a")
    # remove dangling bonds
    req.dc.execute("SELECT 1 FROM instp_device i LEFT JOIN device d ON d.device_idx=i.device WHERE d.name IS NULL")
    if req.dc.rowcount:
        req.dc.execute("SELECT i.instp_device_idx FROM instp_device i LEFT JOIN device d ON d.device_idx=i.device WHERE d.name IS NULL")
        all_dels = [x["instp_device_idx"] for x in req.dc.fetchall()]
        if all_dels:
            req.dc.execute("DELETE FROM instp_device WHERE %s" % (" OR ".join(["instp_device_idx=%d" % (x) for x in all_dels])))
    # fetch packages with inst_package struct
    req.dc.execute("SELECT p.*, ip.*, a.architecture as arch, a.architecture_idx FROM package p, inst_package ip, architecture a WHERE a.architecture_idx=p.architecture AND ip.package=p.package_idx GROUP BY p.pgroup, p.name, p.version, p.release, a.architecture")
    ip_dict, all_groups, arch_dict = (tools.ordered_dict(), [], {})
    pack_ipp_dict = {}
    for db_rec in req.dc.fetchall():
        act_idx = db_rec["package_idx"]
        act_ip = cdef_packages.inst_package(db_rec["name"], act_idx)
        ip_dict[act_idx] = act_ip
        if db_rec["pgroup"] not in all_groups:
            all_groups.append(db_rec["pgroup"])
        arch_dict.setdefault(db_rec["arch"], {})[db_rec["package_idx"]] = act_ip
        pack_ipp_dict[db_rec["inst_package_idx"]] = db_rec["package_idx"]
        for db_key in ["arch", "packager", "pgroup", "summary", "version", "release", "buildtime", "buildhost", "size", "inst_package_idx", "native", "present_on_disk"]:
            act_ip[db_key] = db_rec[db_key]
        act_ip.devcount = 0
        act_ip.dev_list = []
        act_ip.act_values_are_default()
    # add devcount
    if op_mode == "m":
        del_list = []
        req.dc.execute("SELECT ip.package, id.device, ip.inst_package_idx FROM inst_package ip LEFT JOIN instp_device id ON id.inst_package=ip.inst_package_idx ORDER BY ip.package")
        for db_rec in req.dc.fetchall():
            act_idx = db_rec["package"]
            if ip_dict.has_key(act_idx):
                if db_rec["device"]:
                    try:
                        ip_dict[act_idx].dev_list.append(dev_tree.get_dev_name(db_rec["device"]))
                    except:
                        del_list.append(db_rec["inst_package_idx"])
                    else:
                        ip_dict[act_idx].devcount += 1
        if del_list:
            req.dc.execute("DELETE FROM inst_package WHERE %s" % (" OR ".join(["inst_package_idx=%d" % (x) for x in del_list])))
    else:
        req.dc.execute("SELECT ip.package, COUNT(id.device) AS devcount FROM inst_package ip LEFT JOIN instp_device id ON id.inst_package=ip.inst_package_idx GROUP BY ip.package")
        for db_rec in req.dc.fetchall():
            act_idx = db_rec["package"]
            if ip_dict.has_key(act_idx):
                ip_dict[act_idx].devcount = db_rec["devcount"]
    arch_list = html_tools.selection_list(req, "arch", sort_new_keys=0)
    arch_list["all"] = " - ALL - (%s)" % (logging_tools.get_plural("package", len(ip_dict.keys())))
    for arch, num_p in [(x, len(arch_dict[x])) for x in sorted(arch_dict.keys())]:
        arch_list[arch] = "%s (%s)" % (arch, logging_tools.get_plural("package", num_p))
    show_arch = arch_list.check_selection("", "all")
    all_groups.sort()
    groups_list = html_tools.selection_list(req, "pg", {})
    for group in all_groups:
        groups_list[all_groups.index(group) + 1] = group
        sort_list["p%d" % (all_groups.index(group))] = "Show group %s" % (group)
    del_button = html_tools.checkbox(req, "pd", auto_reset=1)
    method_list = html_tools.selection_list(req, "ml", {0 : "shell",
                                                        1 : "native"})
    # sort mode
    sort_mode = sort_list.check_selection("", "a0")
    # action log
    action_log = html_tools.message_log()
    # verbose button
    verbose_button = html_tools.checkbox(req, "verb")
    is_verbose = verbose_button.check_selection()
    scon_logs = html_tools.message_log()
    act_logs = html_tools.message_log()
    # deassociate button
    deass_button = html_tools.checkbox(req, "da", auto_reset=1)
    # show only associated packages
    show_associated_button = html_tools.checkbox(req, "soi")
    show_associated = show_associated_button.check_selection()
    # device list button
    add_device_list_button = html_tools.checkbox(req, "adl")
    add_device_list = add_device_list_button.check_selection()
    # ignore different client-version
    ignore_client_version_button = html_tools.checkbox(req, "icv")
    ignore_client_version = ignore_client_version_button.check_selection()
    # package sets
    ps_tree = package_set_tree(req, action_log)
    ps_tree.read_from_db()
    ps_tree.validate_tree()
    if not dev_tree.devices_found():
        req.write(html_tools.gen_hline("No devices found", 2))
    else:
        dg_sel, d_sel, dg_sel_eff = dev_tree.get_selection()
        ds_dict = dev_tree.get_device_selection_lists()
        sel_table = html_tools.html_table(cls="blindsmall")
        sel_table[0][0] = html_tools.content(dev_tree, "devg", cls="center")
        sel_table[None][0] = html_tools.content(dev_tree, "dev", cls="center")
        if ds_dict:
            sel_table[None][0] = html_tools.content(dev_tree, "sel", cls="center")
            col_span = 4
        else:
            col_span = 3
        sel_table[None][0] = html_tools.content(sort_list, cls="center")
        # report for problem devices
        sel_table[0][1:col_span] = html_tools.content(["Regexp for Groups ", dev_tree.get_devg_re_field(), " and devices ", dev_tree.get_dev_re_field(),
                                                       "\n, ", dev_tree.get_devsel_action_field(), " selection", dev_tree.get_devsel_field()], cls="center")
        select_button = html_tools.submit_button(req, "select")
        sel_table[0][1:col_span] = html_tools.content(["display type: "       , op_list,
                                                       ",\n show architecture: "         , arch_list], cls="center")
        sel_table[0][1:col_span] = html_tools.content(["Verbose: "                       , verbose_button,
                                                       ",\n ignore client versions: "    , ignore_client_version_button,
                                                       ",\n show only associated: "      , show_associated_button,
                                                       ",\n show detailed device list: " , add_device_list_button,
                                                       ",\n RegExp for name: "           , name_re,
                                                       "\n, ", select_button], cls="center")
        req.write("<form action=\"%s.py?%s\" method = post>%s</form>\n" % (req.module_name,
                                                                           functions.get_sid(req),
                                                                           sel_table()))
        # refresh-button for devices
        refresh_d_button = html_tools.checkbox(req, "rfrd", auto_reset=1)
        # refresh-button for device_groups
        refresh_dg_button = html_tools.checkbox(req, "rfrdg", auto_reset=1)
        refresh_all = refresh_d_button.check_selection("")
        grp_dict = check_for_group_changes(req, scon_logs, ip_dict, groups_list, (del_button, method_list), all_groups, act_logs, is_verbose)
        if op_mode == "m":
            for ip in ip_dict.values():
                if (ip["arch"] == show_arch or show_arch == "all")  and an_re.search(ip.get_name()):
                    ip.show_it = 1
        else:
            dev_dict = {}
            refresh_list = []
            if d_sel:
                # only fetch info for packages with associations
                instp_idxs = [x["inst_package_idx"] for x in ip_dict.values() if x.devcount]
                # fetch detailed install - info
                req.dc.execute("SELECT d.name, d.device_idx, d.device_group, d.device_type, id.*, UNIX_TIMESTAMP(id.install_time) AS inst_time FROM device d LEFT JOIN instp_device id ON id.device=d.device_idx WHERE (%s)" % (" OR ".join(["d.device_idx=%d" % (x) for x in d_sel])))
                #print "SELECT d.name, d.device_idx, d.device_group, d.device_type, id.* FROM device d, instp_device id WHERE id.device=d.device_idx AND (%s)" % (" OR ".join(["d.device_idx=%d" % (x) for x in d_sel]))
                for db_rec in req.dc.fetchall():
                    dev_idx = db_rec["device_idx"]
                    if not dev_dict.has_key(dev_idx):
                        new_dev = cdef_device.device(db_rec["name"], dev_idx, db_rec["device_group"], db_rec["device_type"])
                        dev_var_dict = dev_tree.get_dev_struct(db_rec["device_idx"])["dv_name"]
                        new_dev.last_contact = dev_var_dict.get("package_server_last_contact", {"val_date" : None})["val_date"]
                        new_dev.client_version = dev_var_dict.get("package_client_version", {"val_str" : "not set"})["val_str"]
                        dev_dict[dev_idx] = new_dev
                        if refresh_d_button.check_selection(new_dev.get_suffix()) or refresh_all or refresh_dg_button.check_selection("%d" % (db_rec["device_group"])):
                            refresh_dg_button.check_selection("%d" % (db_rec["device_group"]))
                            refresh_list.append(db_rec["name"])
                    else:
                        new_dev = dev_dict[dev_idx]
                    if db_rec["inst_package"] in instp_idxs:
                        pack = ip_dict[pack_ipp_dict[db_rec["inst_package"]]]
                        if pack.device_already_used(dev_idx):
                            # remove duplicate instp_device entries in case of db errors
                            req.dc.execute("DELETE FROM instp_device WHERE instp_device_idx=%d" % (db_rec["instp_device_idx"]))
                        else:
                            pack.add_device(dev_idx)
                            act_ip = cdef_packages.instp_device("%s-%s-%s" % (pack.get_name(), pack["version"], pack["release"]), db_rec["instp_device_idx"])#, x["error_line_num"], x["error_lines"])
                            db_rec["install_time"] = db_rec["inst_time"]
                            iud_flags = ["install", "upgrade", "del"]
                            flags_set = [k for k in iud_flags if db_rec[k]]
                            if len(flags_set) != 1:
                                new_flag = "upgrade"
                                if flags_set and new_flag not in flags_set:
                                    new_flag = flags_set[0]
                                if len(flags_set):
                                    act_logs.add_warn("Package '%s' for device '%s' has wrong flags set: %s, changing to %s" % (act_ip.get_name(),
                                                                                                                                new_dev.get_name(),
                                                                                                                                ", ".join(flags_set),
                                                                                                                                new_flag),
                                                      "SQL")
                                    sql_alter_str = "UPDATE instp_device SET %s WHERE instp_device_idx=%d" % (", ".join(["%s=%d" % (k, k == new_flag and 1 or 0) for k in iud_flags if (k in flags_set and k != new_flag) or (k not in flags_set and k == new_flag)]),
                                                                                                              db_rec["instp_device_idx"])
                                    req.dc.execute(sql_alter_str)
                                    for k in iud_flags:
                                        db_rec[k] = 0
                                    db_rec[new_flag] = 1
                                    if new_dev.get_name() not in refresh_list:
                                        refresh_list.append(new_dev.get_name())
                                else:
                                    act_logs.add_warn("Package '%s' for device '%s' has no flags set" % (act_ip.get_name(),
                                                                                                         new_dev.get_name()),
                                                      "SQL")
                            if db_rec["status"] is None:
                                db_rec["status"] = ""
                            for k in ["install", "upgrade", "del", "nodeps", "forceflag", "install_time", "status", "inst_package", "error_line_num", "error_lines"]:
                                act_ip[k] = db_rec[k]
                            act_ip["device"] = dev_idx
                            # old code
                            ## new_dev.add_package(act_ip)
                            ## new_dev.pack_lut[pack.get_idx()] = x["instp_device_idx"]
                            # new code
                            new_dev.add_package(act_ip, pack)
                            act_ip.act_values_are_default()
            del_ips = []
            gt_assoc = assoc_command.check_selection("", "a0")
            gt_tstate = tstate_command.check_selection("", "a0")
            gt_nodep = nodep_flag.check_selection("", "a0")
            gt_force = force_flag.check_selection("", "a0")
            for ip_idx, ip in ip_dict.iteritems():
                if (ip["arch"] == show_arch or show_arch == "all") and an_re.search(ip.get_name()) and (not show_associated or ip.devices):
                    pack_name = "%s-%s-%s" % (ip.get_name(), ip["version"], ip["release"])
                    ip.show_it = 1
                    # check for changes
                    glob_assoc = assoc_command.check_selection(ip.get_suffix(), "a0")
                    glob_tstate = tstate_command.check_selection(ip.get_suffix(), "a0")
                    glob_nodep = nodep_flag.check_selection(ip.get_suffix(), "a0")
                    glob_force = force_flag.check_selection(ip.get_suffix(), "a0")
                    for dev_idx, dev in dev_dict.iteritems():
                        dev_refresh = 0
                        dev_name = dev.get_name()
                        loc_assoc  = glob_assoc  == "a0" and gt_assoc  or glob_assoc
                        loc_tstate = glob_tstate == "a0" and gt_tstate or glob_tstate
                        loc_nodep  = glob_nodep  == "a0" and gt_nodep  or glob_nodep
                        loc_force  = glob_force  == "a0" and gt_force  or glob_force
                        ipd = dev.get_instp_struct(ip)
                        if ipd:
                            if op_mode.startswith("i1"):
                                if deass_button.check_selection(ipd.get_suffix()):
                                    loc_assoc = "a1"
                                r_loc_tstate = tstate_command.check_selection(ipd.get_suffix(), "a0")
                                if r_loc_tstate == "a0" and loc_tstate != "a0":
                                    r_loc_tstate = loc_tstate
                                loc_tstate = r_loc_tstate
                                r_loc_nodep = nodep_flag.check_selection(ipd.get_suffix(), "a0")
                                if r_loc_nodep == "a0" and loc_nodep != "a0":
                                    r_loc_nodep = loc_nodep
                                loc_nodep = r_loc_nodep
                                r_loc_force = force_flag.check_selection(ipd.get_suffix(), "a0")
                                if r_loc_force == "a0" and loc_force != "a0":
                                    r_loc_force = loc_force
                                loc_force = r_loc_force
                        if ipd and loc_assoc == "a1":
                            if loc_tstate != "a0" or loc_nodep != "a0" or loc_force != "a0":
                                act_logs.add_warn("Cannot remove package %s and change target_state/flags at the same time" % (pack_name), "warn")
                            else:
                                if is_verbose:
                                    act_logs.add_ok("removing package %s from device %s" % (pack_name, dev_name), "OK")
                                del_ips.append(dev.delete_package_pack(ip))
                                #instp_idx = dev.get_instp_idx(ip)
                                #del dev.packages[instp_idx]
                                ip.devices.remove(dev_idx)
                                dev_refresh = 1
                        elif not ipd and loc_assoc == "a2":
                            ipd = cdef_packages.instp_device(pack_name, 0)
                            ipd["install_time"] = 0
                            ipd["nodeps"]    = loc_nodep  == "a1" and 1 or 0
                            ipd["forceflag"] = loc_force  == "a1" and 1 or 0
                            ipd["install"]   = loc_tstate == "a1" and 1 or 0
                            ipd["upgrade"]   = loc_tstate == "a2" and 1 or 0
                            ipd["del"]       = loc_tstate == "a3" and 1 or 0
                            ipd["device"]    = dev_idx
                            ipd["status"]    = ""
                            ipd["error_line_num"] = 0
                            ipd["error_lines"]    = ""
                            ipd["inst_package"]   = ip["inst_package_idx"]
                            ipd.commit_sql_changes(req.dc, 1, 1)
                            ip.add_device(dev_idx)
                            if is_verbose:
                                act_logs.add_ok("adding package %s to device %s" % (pack_name, dev_name), "OK")
                            dev.add_package(ipd, ip)
                            tstate_command.check_selection(ipd.get_suffix(), "a0")
                            nodep_flag.check_selection(ipd.get_suffix(), "a0")
                            force_flag.check_selection(ipd.get_suffix(), "a0")
                            deass_button.check_selection(ipd.get_suffix())
                            dev_refresh = 1
                        elif ipd:
                            #print loc_tstate, loc_nodep, loc_force, "<br>"
                            # check for changes
                            change_list = []
                            if loc_tstate in ["a1", "a2", "a3"]:
                                set_it = None
                                if loc_tstate == "a1" and not ipd["install"]:
                                    set_it = "install"
                                elif loc_tstate == "a2" and not ipd["upgrade"]:
                                    set_it = "upgrade"
                                elif loc_tstate == "a3" and not ipd["del"]:
                                    set_it = "del"
                                if set_it:
                                    change_list.append("tstate to %s" % (set_it == "del" and "erase" or set_it))
                                    ipd["install"] = 0
                                    ipd["upgrade"] = 0
                                    ipd["del"] = 0
                                    ipd[set_it] = 1
                                    dev_refresh = 1
                            if loc_nodep == "a1" and not ipd["nodeps"]:
                                ipd["nodeps"] = 1
                                dev_refresh = 1
                                change_list.append("setting --nodeps flag")
                            elif loc_nodep == "a2" and ipd["nodeps"]:
                                ipd["nodeps"] = 0
                                dev_refresh = 1
                                change_list.append("clearing --nodeps flag")
                            if loc_force == "a1" and not ipd["forceflag"]:
                                ipd["forceflag"] = 1
                                dev_refresh = 1
                                change_list.append("setting --force flag")
                            elif loc_force == "a2" and ipd["forceflag"]:
                                ipd["forceflag"] = 0
                                dev_refresh = 1
                                change_list.append("clearing --force flag")
                            if is_verbose and change_list:
                                act_logs.add_ok("change settings for package %s on device %s: %s" % (pack_name, dev_name, ", ".join(change_list)), "OK")
                            ipd.commit_sql_changes(req.dc, 1, 0)
                        if dev_refresh and dev_name not in refresh_list:
                            refresh_list.append(dev_name)
                else:
                    # remove instp_devices
                    for dev_idx, dev in dev_dict.iteritems():
                        dev.delete_package_pack(ip)
            if del_ips:
                if is_verbose:
                    act_logs.add_ok("removed %s" % (logging_tools.get_plural("package", len(del_ips))), "SQL")
                req.dc.execute("DELETE FROM instp_device WHERE %s" % (" OR ".join(["instp_device_idx=%d" % (x) for x in del_ips])))
            if refresh_list:
                tools.iterate_s_commands([tools.s_command(req, "package_server", 8007, "new_config", sorted(refresh_list), CONN_TIMEOUT)], scon_logs)
                    
        if act_logs:
            req.write(act_logs.generate_stack("Action log"))
        if scon_logs:
            req.write(scon_logs.generate_stack("Connection log"))
        req.write("<form action=\"%s.py?%s\" method = post>%s%s%s%s%s%s%s%s%s" % (req.module_name,
                                                                                  functions.get_sid(req),
                                                                                  verbose_button.create_hidden_var(),
                                                                                  arch_list.create_hidden_var(),
                                                                                  op_list.create_hidden_var(),
                                                                                  name_re.create_hidden_var(),
                                                                                  sort_list.create_hidden_var(),
                                                                                  show_associated_button.create_hidden_var(),
                                                                                  add_device_list_button.create_hidden_var(),
                                                                                  ignore_client_version_button.create_hidden_var(),
                                                                                  dev_tree.get_hidden_sel()))
        if op_mode == "m":
            show_maintenance(req, ip_dict, grp_dict, all_groups, groups_list, (del_button, method_list), assoc_command, tstate_command, nodep_flag, force_flag, sort_mode)
        elif op_mode == "s":
            ps_tree.parse_values()
            ps_tree.commit_changes()
            ps_tree.create_content()
            #show_sets(req)
        else:
            if d_sel:
                dev_table = html_tools.html_table(cls="normal")
                req.write("%s%s" % (html_tools.gen_hline("Selected %s in %s" % (logging_tools.get_plural("device", len(d_sel)),
                                                                                logging_tools.get_plural("devicegroup", len(dg_sel_eff))),
                                                         2),
                                    dev_table.get_header()))
                dict_keys = ["total", "upgrade", "install", "del", "---"]
                oline_idx = 1
                for dg in dg_sel_eff:
                    dev_table[1][1:op_mode.startswith("i0") and 8 or 13] = html_tools.content(dev_tree.get_sel_dev_str(dg), cls="devgroup")
                    dev_table[0][0] = html_tools.content("Name", type="th", cls="center")
                    dev_table[None]["class"] = "line0%d" % (oline_idx)
                    oline_idx = 1 - oline_idx
                    if op_mode.startswith("i0"):
                        dev_table[None][0] = html_tools.content(["Refresh: ", refresh_dg_button], "%d" % (dg), type="th", cls="center")
                        for what in ["contact", "version", "#", "Status", "keep/Upgrade/Inst/Erase", "Errors"]:
                            dev_table[None][0] = html_tools.content(what, type="th", cls="center")
                    else:
                        for what in ["Name", "arch", "Vers", "Rel", "Remove", "TState", "ActState", "nodeps", "force", "flags", "install time", "status"]:
                            dev_table[None][0] = html_tools.content(what, type="th", cls="center")
                    req.write(dev_table.flush_lines())
                    line_idx = 1
                    if op_mode.startswith("i0"):
                        # overview cache table
                        ov_c_table = []
                    for dev in [x for x in d_sel if x in dev_tree.get_sorted_dev_idx_list(dg)]:
                        act_dev = dev_dict[dev]
                        num_dict = dict([(key, 0) for key in dict_keys])
                        num_dict["total"] = len(act_dev.packages.keys())
                        # total lines, only used for detailed view [op_mode.startswith("i1")]
                        num_dict["lines"] = sum([act_pack["error_line_num"] and 2 or 1 for act_pack in act_dev.packages.values()])
                        for key in ["install", "upgrade", "del"]:
                            num_dict[key]              = len([x for x in act_dev.packages.values() if x[key]])
                            num_dict["%s_act" % (key)] = len([x for x in act_dev.packages.values() if x[key] and x["status"].startswith("ok")])
                        num_dict["---"] = len(act_dev.packages.keys()) - (num_dict["install"] + num_dict["upgrade"] + num_dict["del"])
                        num_dict["---_act"] = num_dict["---"]
                        num_dict["error"] = len([x for x in act_dev.packages.values() if x["status"].startswith("error")])
                        num_dict["wait"]  = len([x for x in act_dev.packages.values() if x["status"].startswith("w") or not x["status"]])
                        num_dict["ok"]    = len([x for x in act_dev.packages.values() if x["status"].startswith("ok")])
                        if num_dict["error"]:
                            line_pf = "line2"
                        elif num_dict["wait"]:
                            line_pf = "line3"
                        else:
                            line_pf = "line1"
                        if op_mode.startswith("i0"):
                            # actual line
                            act_ov_c_line = [{"content"           : act_dev.get_name(),
                                              "format"            : "left",
                                              "ignore"            : 1,
                                              "collapse_data"     : act_dev.get_name(),
                                              "collapse_function" : collapse_names,
                                              "key"               : "name"}]
                        else:
                            dev_table[0:1 + num_dict["lines"]][0] = html_tools.content("%s" % (act_dev.get_name()), cls="left")
                            dev_table[None]["class"] = "%s%d" % (line_pf, line_idx)
                        lc_state, lc_str = get_last_contact_state_and_str(act_dev.last_contact)
                        line_idx = 1 - line_idx
                        info_str = "%s OK%s%s" % (num_dict["total"] == num_dict["ok"] and "all" or "%d" % (num_dict["ok"]),
                                                  num_dict["error"] and ", %s" % (logging_tools.get_plural("error", num_dict["error"])) or "",
                                                  num_dict["wait"] and ", %d waiting" % (num_dict["wait"]) or "")
                        ov_str = " / ".join(["%d%s" % (num_dict[key],
                                                       num_dict[key] != num_dict["%s_act" % (key)] and " (act: %d)" % (num_dict["%s_act" % (key)]) or "") for key in
                                             ["---", "upgrade", "install", "del"]])
                        if op_mode.startswith("i0"):
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
                                                   "format"  : "center"},
                                                  {"content" : ov_str,
                                                   "format"  : "center"}])
                            if num_dict["error"]:
                                act_ov_c_line.append({"content" : "%s : %s" % (logging_tools.get_plural("Error", num_dict["error"]),
                                                                               ", ".join([x.get_name() for x in act_dev.packages.values() if x["status"].startswith("error")])),
                                                      "format"  : "left"})
                            else:
                                act_ov_c_line.append({"content" : "-",
                                                      "format"  : "center"})
                            ov_c_table.append((act_dev.get_suffix(), "%s%d" % (line_pf, line_idx), act_ov_c_line))
                        else:
                            dev_table[None][0:12] = html_tools.content(["Refresh: ", refresh_d_button, "; %s associated, package status: " % (logging_tools.get_plural("package", num_dict["total"])),
                                                                        info_str, ",\n state info: ", ov_str,
                                                                        ", last contact: %s" % (lc_str),
                                                                        ", package_client_version is %s" % (act_dev.client_version)], cls="left")
                        if op_mode.startswith("i1"):
                            dev_table.set_cursor(1, 2)
                            act_line_idx = 1
                            for ip in [act_dev.packages[x] for x in act_dev.get_sorted_instp_idx_list()]:
                                act_line_idx = 1 - act_line_idx
                                pack = ip_dict[pack_ipp_dict[ip["inst_package"]]]
                                dev_table.set_auto_cr(0)
                                if ip["error_line_num"]:
                                    dev_table[0:2][2] = html_tools.content(pack.get_name(), cls="left")
                                else:
                                    dev_table[0][2] = html_tools.content(pack.get_name(), cls="left")
                                if ip["status"].startswith("error"):
                                    act_line_pf = "line2"
                                elif ip["status"].startswith("w") or not ip["status"]:
                                    act_line_pf = "line3"
                                else:
                                    act_line_pf = "line1"
                                dev_table[None]["class"] = "%s%d" % (act_line_pf, act_line_idx)
                                dev_table.set_auto_cr()
                                dev_table[None][0] = html_tools.content(pack["arch"], cls="center")
                                dev_table[None][0] = html_tools.content(pack["version"], cls="center")
                                dev_table[None][0] = html_tools.content(pack["release"], cls="center")
                                dev_table[None][0] = html_tools.content(deass_button, ip.get_suffix(), cls="center")
                                dev_table[None][0] = html_tools.content(tstate_command, ip.get_suffix(), cls="center")
                                # actual target_state
                                if ip["install"]:
                                    act_ts = "install"
                                elif ip["upgrade"]:
                                    act_ts = "upgrade"
                                elif ip["del"]:
                                    act_ts = "erase"
                                else:
                                    act_ts = "---"
                                dev_table[None][0] = html_tools.content(act_ts, cls="center")
                                dev_table[None][0] = html_tools.content(nodep_flag, ip.get_suffix(), cls="center")
                                dev_table[None][0] = html_tools.content(force_flag, ip.get_suffix(), cls="center")
                                flag_field = []
                                if ip["nodeps"]:
                                    flag_field.append("--nodeps")
                                if ip["forceflag"]:
                                    flag_field.append("--force")
                                if not flag_field:
                                    flag_field.append("-")
                                dev_table[None][0] = html_tools.content(", ".join(flag_field), cls="center")
                                if ip["install_time"]:
                                    dev_table[None][0] = html_tools.content(time.strftime("%a, %d. %b %Y, %H:%M:%S", time.localtime(ip["install_time"])), cls="left")
                                else:
                                    dev_table[None][0] = html_tools.content("unknown", cls="left")
                                dev_table[None][0] = html_tools.content(ip["status"], cls="left")
                                if ip["error_line_num"]:
                                    act_c, act_y = dev_table.get_cursor()
                                    dev_table.set_cursor(act_c + 1, 2)
                                    dev_table[None]["class"] = "%s%d" % (act_line_pf, act_line_idx)
                                    dev_table[None][0:11] = html_tools.content("<br>".join(["%3d: %s" % (idx, line) for idx, line in zip(range(1, ip["error_line_num"] + 1), ip["error_lines"].split("\n"))]), cls="left")
                            req.write(dev_table.flush_lines(act_dev.get_suffix()))
                    if op_mode.startswith("i0"):
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
##                     req.write("<div class=\"center\">Refresh all: %s, refresh waiting: %s</div>\n" % (refresh_d_button(""),
##                                                                                                       refresh_d_button("w")))
            else:
                req.write(html_tools.gen_hline("No devices selected", 2))
            show_maintenance(req, ip_dict, grp_dict, all_groups, groups_list, (del_button, method_list), assoc_command, tstate_command, nodep_flag, force_flag, sort_mode, op_mode, dev_dict, show_associated, add_device_list)
        req.write("</form>\n")
