#!/usr/bin/python -Ot
# -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2012 Andreas Lang-Nevyjel, init.at
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
import cPickle
import session_handler
from init.cluster.backbone.models import session_data, user
from django.db.models import Q
    
def module_info():
    return {"si" : {"description"           : "Session info",
                    "default"               : 0,
                    "enabled"               : 1,
                    "left_string"           : "Session Info",
                    "right_string"          : "View session history",
                    "priority"              : -120,
                    "capability_group_name" : "user"}}

##class session(object):
##    def __init__(self, in_dict):
##        self.__session_idx = in_dict["session_data_idx"]
##        self.__login, self.__logout = (in_dict["login_time"],
##                                       in_dict["logout_time"])
##        self.__remote = in_dict["remote_addr"]
##        self.__id = in_dict["session_id"]
##        self.__shm_id = session_handler.generate_shm_id(self.__id)
##        if in_dict["forced_logout"]:
##            self.__forced = True
##        else:
##            self.__forced = False
##        self.set_user()
##        self.set_type()
##        self.__value, self.__shm_value = (None, None)
##    def set_value(self, val=None):
##        self.__value = val
##    def set_shm_value(self, val=None):
##        self.__shm_value = val
##    def get_value_source(self):
##        return self.__shm_value and "shm" or "db"
##    def get_value(self):
##        if self.__shm_value:
##            return self.__shm_value
##        else:
##            return self.__value
##    def get_page_views(self):
##        if self.get_value():
##            return self.get_value().get("page_views", 0)
##        else:
##            return 0
##    def set_type(self, with_php=0):
##        self.__with_php = with_php
##    def get_type(self):
##        if self.__with_php:
##            return "compat"
##        else:
##            return "pure"
##    def was_forced(self):
##        return self.__forced
##    def set_user(self, uname="unknown", alias=""):
##        self.__user = uname
##        self.__alias = alias
##    def get_user(self):
##        if self.__alias:
##            return "%s (alias %s)" % (self.__user, self.__alias)
##        else:
##            return self.__user
##    def __strftime(self, dt):
##        today = dt.today()
##        if today.year == dt.year and today.month == dt.month and today.day == dt.day:
##            return dt.strftime("today, %H:%M:%S")
##        else:
##            return dt.strftime("%d. %b. %Y, %H:%M:%S")
##    def get_login_tuple(self):
##        return (self.__login.year, self.__login.month, self.__login.day)
##    def get_login_date(self):
##        return self.__login.strftime("%d. %b. %Y")
##    def get_login_time(self):
##        return self.__login.strftime("%H:%M:%S")
##    def get_logout_time(self):
##        if self.__logout:
##            return self.__strftime(self.__logout)
##        else:
##            return "still active"
##    def get_session_length(self):
##        if self.__logout:
##            delta = self.__logout - self.__login
##            return str(delta)
##        else:
##            return "still active"
##    def get_remote_addr(self):
##        return self.__remote
##    def get_id(self):
##        return self.__id
##    def get_shm_id(self):
##        return self.__shm_id
    
def fetch_session_tree(req, mode):
    # fetch user info
    user_dict = dict([(cur_user.pk, cur_user) for cur_user in user.objects.all()])
    for cur_user in user_dict.itervalues():
        cur_user.count = 0
    if mode == 1:
        # only active
        all_sessions = session_data.objects.filter(Q(logout_time=None)).order_by("login_time")
    else:
        # all
        all_sessions = session_data.objects.all().order_by("login_time")
    for act_session in all_sessions:
        act_session.value = cPickle.loads(str(act_session.value))
        if act_session.user_id and act_session.user_id in user_dict:
            act_session.user = user_dict[act_session.user_id]
            user_dict[act_session.user_id].count += 1
    # fetch shm-session info
    return all_sessions, user_dict

def process_page(req):
    if req.conf["genstuff"].has_key("AUTO_RELOAD"):
        del req.conf["genstuff"]["AUTO_RELOAD"]

    functions.write_header(req)
    functions.write_body(req)

    sv_list = html_tools.selection_list(req, "svm", {1 : "show active sessions",
                                                     2 : "show all sessions"})
    sm_list = html_tools.selection_list(req, "smm", {1 : "sort by logintime",
                                                     2 : "sort by user and logintime"})
    select_button = html_tools.submit_button(req, "select")

    act_sv_mode = sv_list.check_selection("", 1)
    act_sm_mode = sm_list.check_selection("", 1)
    session_tree, user_dict = fetch_session_tree(req, act_sv_mode)
    user_time_sel_dict = html_tools.selection_list(req, "std", log_validation_errors=0)
    if act_sm_mode == 1:
        # build time_dict
        time_dict = {}
        for s_entry in session_tree:
            act_login = (s_entry.login_time.year, s_entry.login_time.month, s_entry.login_time.day)
            time_dict.setdefault(act_login, []).append(s_entry)
        times = sorted(time_dict.keys())
        act_range, act_range_dict, act_range_idx = ([], {}, 0)
        user_time_sel_dict[-1] = "all %s" % (logging_tools.get_plural("entry", len(session_tree)))
        for t_entry in times:
            act_range.extend(time_dict[t_entry])
            if len(act_range) > 10 or t_entry == times[-1]:
                act_range_dict[act_range_idx] = act_range
                if act_range[0].login_time.strftime("%d. %b. %Y") == act_range[-1].login_time.strftime("%d. %b. %Y"):
                    user_time_sel_dict[act_range_idx] = "%s, %s" % (act_range[0].login_time.strftime("%d. %b. %Y"),
                                                                    logging_tools.get_plural("entry", len(act_range)))
                else:
                    user_time_sel_dict[act_range_idx] = "%s - %s, %s" % (act_range[0].login_time.strftime("%d. %b. %Y"),
                                                                         act_range[-1].login_time.strftime("%d. %b. %Y"),
                                                                         logging_tools.get_plural("entry", len(act_range)))
                act_range = []
                act_range_idx += 1
    else:
        # build user dict
        user_dict = {}
        for s_entry in session_tree:
            act_user = s_entry.get_user()
            user_dict.setdefault(act_user, []).append(s_entry)
        users = sorted(user_dict.keys())
        user_time_sel_dict[-1] = "all %s (%s)" % (logging_tools.get_plural("user", len(users)),
                                                  logging_tools.get_plural("session", sum([len(x) for x in user_dict.values()])))
        act_range_idx, act_range_dict = (0, {})
        for act_user in users:
            act_range_dict[act_range_idx] = user_dict[act_user]
            user_time_sel_dict[act_range_idx] = "%s (%s)" % (act_user,
                                                             logging_tools.get_plural("session", len(user_dict[act_user])))
            act_range_idx += 1
    
    req.write("<form action=\"%s.py?%s\" method=post>" % (req.module_name,
                                                          functions.get_sid(req)))
    act_range_idx = user_time_sel_dict.check_selection("", 0)
    req.write(html_tools.gen_hline("Actual displaymode is %s, %s, showing %s, %s:" % (sv_list(""),
                                                                                      sm_list(""),
                                                                                      user_time_sel_dict(""),
                                                                                      select_button("")), 2, False))
    if session_tree:
        s_table = html_tools.html_table(cls = "user")
        s_table[0]["class"] = "line00"
        # sorted by time
        if act_sm_mode == 1:
            act_session_dict = act_range_dict.get(act_range_idx, session_tree)
            users = [None]
            head_line = [("user"      , "l"),
                         ("ID"        , "c"),
                         ("source"    , "c"),
                         ("type"      , "c"),
                         ("address"   , "r"),
                         ("logintime" , "c"),
                         ("logouttime", "c"),
                         ("duration"  , "c"),
                         ("forced"    , "c"),
                         ("views"     , "c")]
        else:
            act_session_dict = act_range_dict.get(act_range_idx, session_tree)
            head_line = [("ID"        , "c"),
                         ("source"    , "c"),
                         ("type"      , "c"),
                         ("address"   , "c"),
                         ("logintime" , "c"),
                         ("logouttime", "c"),
                         ("duration"  , "c"),
                         ("forced"    , "c"),
                         ("views"     , "c")]
            if act_range_idx >= 0:
                users = [users[act_range_idx]]
        for what, form in head_line:
            s_table[None][0] = html_tools.content(what, type="th", cls={"c" : "center",
                                                                        "l" : "left",
                                                                        "r" : "right"}[form])
        line_idx = 1
        for user in users:
            last_login = (0, 0, 0)
            if user:
                s_table[0]["class"] = "line00"
                s_table[None][0:9] = html_tools.content("User %s, %s" % (user,
                                                                         logging_tools.get_plural("session", len(user_dict[user]))), cls="center", type="th")
            for s_entry in act_session_dict:
                if not user or s_entry.get_user() == user:
                    act_login = (s_entry.login_time.year, s_entry.login_time.month, s_entry.login_time.day)
                    if act_login != last_login:
                        last_login = act_login
                        s_table[0]["class"] = "line01"
                        s_table[None][0:user and 9 or 10] = html_tools.content(s_entry.login_time.strftime("%d. %b. %Y"), cls="center", type="th")
                    line_idx = 1 - line_idx
                    s_table[0]["class"] = "line1%d" % (line_idx)
                    if not user:
                        s_table[None][0] = html_tools.content(unicode(s_entry.user), cls="left")
                    is_my_session = s_entry.session_id == req.session_data.get_session_id()
                    s_table[None][0] = html_tools.content("%s%s" % (s_entry.session_id,
                                                                    is_my_session and " (*)" or ""), cls="centerfix")
                    s_table[None][0] = html_tools.content("db", cls="center")
                    s_table[None][0] = html_tools.content("pure", cls="center")
                    s_table[None][0] = html_tools.content(s_entry.remote_addr, cls="center")
                    s_table[None][0] = html_tools.content(s_entry.login_time.strftime("%H:%M:%S"), cls="center")
                    s_table[None][0] = html_tools.content("still active" if not s_entry.logout_time else s_entry.logout_time.strftime("%d. %b. %Y, %H:%M:%S"), cls="right")
                    s_table[None][0] = html_tools.content("still active" if not s_entry.logout_time else logging_tools.get_diff_time_str((s_entry.logout_time - s_entry.login_time).seconds), cls="right")
                    s_table[None][0] = html_tools.content(" (*)" if s_entry.forced_logout else "", cls="center")
                    s_table[None][0] = html_tools.content("%d" % (s_entry.value.get("page_views", 0)), cls="center")
        req.write(s_table(""))
    req.write("</form>")
    
