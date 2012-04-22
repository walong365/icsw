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
""" commodity functions """

import time
import html_tools
import logging_tools
import cgi
from basic_defs import SESSION_ID_NAME, DEBUG
    
def get_sid(req):
    return "%s=%s" % (SESSION_ID_NAME, req.session_data.get_session_id())

def get_sid_value(req):
    return req.session_data.get_session_id()

def get_hidden_sid(req):
    return "<input type=hidden name=\"%s\" value=\"%s\"/>" % (SESSION_ID_NAME, req.session_data.get_session_id())

def html_head(req):
    req.write("<!DOCTYPE HTML PUBLIC \"-//W3C//DTD HTML 4.01//EN\" \"http://www.w3.org/TR/html4/strict.dtd\" >\n<html>\n")
    req.conf["start_time"] = time.time()

def write_header(req, style_file="formate.css", js_list=["jquery-1.2.3.min"]):
    out_f = ["<head>",
             "<meta name=\"generator\" content=\"init.at webfrontend python scripts\">",
             "<meta http-equiv=\"content-type\" content=\"text/html; charset=ISO-8859-1\">"]
    if req.conf.get("genstuff", {}).has_key("AUTO_RELOAD"):
        add_str = "<meta http-equiv=\"refresh\" content=\"%s" % (str(req.conf["genstuff"]["AUTO_RELOAD"]))
        if req.conf["genstuff"].has_key("RELOAD_TARGET"):
            add_str += "; URL=%s%s" % (req.conf["genstuff"]["RELOAD_TARGET"],
                                       req.session_data and "?%s" % (get_sid(req)) or "")
        out_f.append("%s\">" % (add_str))
    act_user = ""
    if req.user_info:
        act_user = req.user_info["login"]
        if req.session_data:
            if req.session_data.is_alias_login:
                act_user = "%s [via alias %s]" % (act_user, req.session_data.alias)
    out_f.extend(["<meta http-equiv=\"expires\" content=\"0\">",
                  "<meta http-equiv=\"pragma\" content=\"no-cache\">",
                  "<meta http-equiv=\"cache-control\" content=\"no-cache\">",
                  "<title>%s - %s (module %s%s)</title>" % (cgi.escape(req.conf["cluster_variables"]["CLUSTER_NAME"]["val_str"]),
                                                            cgi.escape(req.title),
                                                            cgi.escape(req.module_name),
                                                            act_user and ", user %s" % (cgi.escape(act_user)) or ""),
                  "<link rel=stylesheet type=\"text/css\" href=\"../static/%s\">" % (style_file)])
    if js_list:
        out_f.extend(["<script type=\"text/javascript\" src=\"../static/javascript/%s.js\">%s</script>" % (js_file,
                                                                                                           {"MochiKit" : "MochiKit = {__export__: false}"}.get(js_file, "")) for js_file in js_list])
    out_f.append("</head>")
    req.write("\n".join(out_f))

def write_link_line(req, vars_to_add):
    link_table = html_tools.html_table(cls = "linkline")
    link_table[0][0] = html_tools.content("<a href=\"logincheck.py\">Logout</a>", cls="left")
    for act_e in req.session_data.get_property("pages"):
        if act_e == "index":
            link_name = "Home"
        else:
            link_name = req.cap_stack[act_e].left_string
        if not link_name:
            link_name = "link_name not set: %s" % (act_e)
        link_table[None][0] = html_tools.content("<a href=\"%s.py?%s\">%s</a>" % (act_e,
                                                                                  "&".join([get_sid(req)] + vars_to_add),
                                                                                  link_name), cls="right")
    req.write(link_table(""))

def write_body(req):
    req.write("<body class=\"blind\">\n")
    
def write_error_footer(req):
    req.write(str(req.info_stack.generate_stack("Internal log for this page (%s):" % (logging_tools.get_plural("entry", req.info_stack.get_num_lines())))))
    # add profile log
    if req.conf.has_key("stats"):
        p_data = req.conf["stats"]
        p_data.sort_stats("cumulative")
        profile_table = html_tools.html_table(cls="normalsmall")
        profile_table[0]["class"] = "line00"
        for hs in ["calls", "total", "per call", "cumulated", "per call", "filename", "lineno", "function"]:
            profile_table[None][0] = html_tools.content(hs, cls="center", type="th")
        # hack, copied from pstats.py
        func_list, msg =  p_data.eval_print_amount(20, p_data.fcn_list[:], "")
        l_idx = 0
        for func_name in func_list:
            l_idx = 1 - l_idx
            profile_table[0]["class"] = "line1%d" % (l_idx)
            cc, nc, tt, ct, callers = p_data.stats[func_name]
            profile_table[None][0] = html_tools.content(cc == nc and "%d" % (nc) or "%d / %d" % (cc, nc), cls="right")
            profile_table[None][0] = html_tools.content(logging_tools.get_diff_time_str(tt)[:-6], cls="right")
            profile_table[None][0] = html_tools.content(nc and logging_tools.get_diff_time_str(tt / nc)[:-6] or "&nbsp;", cls="right")
            profile_table[None][0] = html_tools.content(logging_tools.get_diff_time_str(ct)[:-6], cls="right")
            profile_table[None][0] = html_tools.content(logging_tools.get_diff_time_str(ct / cc)[:-6] or "&nbsp;", cls="right")
            f_name, l_no, function = func_name
            profile_table[None][0] = html_tools.content(f_name, cls="left")
            profile_table[None][0] = html_tools.content("%d" % (l_no), cls="right")
            profile_table[None][0] = html_tools.content(function, cls="center")
        req.write("%s%s" % (html_tools.gen_hline("Profile info: %d function calls (%d primitive) in %.3f CPU seconds" % (p_data.total_calls,
                                                                                                                         p_data.prim_calls,
                                                                                                                         p_data.total_tt), 3),
                            str(profile_table(""))))
    # add sql-debug log
    if req.session_data and req.user_info and req.user_info.capability_ok("sql"):
        sql_stack = req.sql_stack
        sql_stack.set_layout("nril")
        sql_stack.set_table_class("text")
        if req.sql_exec_time > 1:
            sql_stack.log_ok(("total execution time: %s" % (logging_tools.get_diff_time_str(req.sql_exec_time)), "info"), 0)
        else:
            sql_stack.log_ok(("total execution time: %.2f msec" % (1000 * req.sql_exec_time), "info"), 0)
        sql_stack.set_pre_and_post_tags("<small>", "</small>")
        req.write(str(sql_stack.generate_stack("SQL log")))
    
def write_footer(req):
    req.conf["end_time"] = time.time()
    left_str = ["%s, page generated %s in %s" % (cgi.escape(req.conf["cluster_variables"]["CLUSTER_NAME"]["val_str"]),
                                                 time.ctime(req.conf["start_time"]),
                                                 logging_tools.get_diff_time_str(req.conf["end_time"] - req.conf["start_time"]))]
    if req.conf.get("genstuff", {}).has_key("AUTO_RELOAD"):
        left_str.append("reload after %s seconds" % (req.conf["genstuff"]["AUTO_RELOAD"]))
    left_class, right_class = ("left", "right")
    flags_field = []
    if req.conf.has_key("process_start_time"):
        flags_field.append("%s core" % (logging_tools.get_diff_time_str(req.conf["process_end_time"] - req.conf["process_start_time"])))
    if DEBUG:
        flags_field.append("Debug mode")
        left_class, right_class = ("warnleft", "warnright")
    if flags_field:
        left_str.append("(%s)" % (", ".join(flags_field)))
    if req.cluster_support:
        right_str = "<a href=\"mailto:%s?subject=Clusterrequest%%20from%%20%s\">&lt;contact support (%s)&gt;</a>\n" % ("%20".join([x["useremail"] for x in req.cluster_support]),
                                                                                                                       "Cluster",
                                                                                                                       ", ".join([x["login"] for x in req.cluster_support]))
    else:
        right_str = ""
    if req.user_info:
        if type(req.user_info) != type({}) and req.user_info.capability_ok("sql"):
            right_str += "&nbsp;&nbsp;".join(["",
                                              "%s," % (logging_tools.get_plural("SQL call", req.dc.get_exec_counter())),
                                              logging_tools.get_plural("error", req.dc.get_error_counter()),
                                              ""])
    right_str += "<a href=\"http://www.init.at\">www.init.at</a>&nbsp;,&nbsp;"
    right_str += "<a href=\"index.py%s\">Home</a>" % (req.session_data and "?%s" % (get_sid(req)) or "")
    out_table = html_tools.html_table(cls = "blind")
    out_table[1][1] = html_tools.content(", ".join(left_str) , cls = left_class)
    out_table[1][2] = html_tools.content(right_str , cls = right_class)
    req.write("<hr>\n%s" % (out_table("")))
    
def write_simple_footer(req):
    req.write("</body></html>\n")
