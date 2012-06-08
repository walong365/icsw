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
""" modify personal settings page """

import functions
import logging_tools
import tools
import html_tools
import cdef_user
import random
import crypt
from init.cluster.backbone.models import user, session_data, user_var
from django.db.models import Q

def module_info():
    return {"mp" : {"description"           : "Modify personal userdata (pwd)",
                    "default"               : 0,
                    "enabled"               : 1,
                    "left_string"           : "Modify personal userdata",
                    "right_string"          : "Modify personal userdata",
                    "priority"              : -100,
                    "capability_group_name" : "user"},
            "mpsh" : {"default"                : 0,
                      "enabled"                : 1,
                      "description"            : "Show hidden user vars",
                      "mother_capability_name" : "mp"}}

def show_login_info(req, act_ug_tree, action_log):
    act_group = act_ug_tree.get_group(req.session_data.user_info.group_id)
    act_user = act_group.get_user(req.session_data.user_info.pk)
    line_idx = 0
    req.write(html_tools.gen_hline("Information about your account", 2))
    info_table = html_tools.html_table(cls="user")
    info_table[0]["class"]    = "line10"
    info_table[None][0] = html_tools.content("Loginname:", cls="right", type="th")
    info_table[None][0] = html_tools.content(act_user.login, cls="left", type="th")
    info_table[None][0] = html_tools.content("Userid:", cls="right", type="th")
    info_table[None][0] = html_tools.content("%d" % (act_user.uid), cls="left", type="th")
    info_table[0][0]    = html_tools.content("Primary group:", cls="right")
    info_table[None][0] = html_tools.content("%s (%d)" % (act_group.groupname, act_group.gid), cls="left")
    sgroup_names = act_ug_tree.get_group_names([cur_g.pk for cur_g in act_user.get_secondary_groups()])
    #[k for k, v in group_dict.iteritems() if v.get_idx() in act_user.get_secondary_group_idxs()]
    info_table[None][0] = html_tools.content(sgroup_names and "%s:" % (logging_tools.get_plural("Secondary group", len(sgroup_names))) or "no secondary groups", cls="right")
    info_table[None][0] = html_tools.content(", ".join(sgroup_names) or "&nbsp;", cls="left")
    info_table[0][0]    = html_tools.content("Home dir:", cls="right")
    info_table[None][0] = html_tools.content(act_ug_tree.build_export_str(act_group, act_user, "home"), cls="left")
    info_table[None][0] = html_tools.content("Scratch dir:", cls="right")
    info_table[None][0] = html_tools.content(act_ug_tree.build_export_str(act_group, act_user, "scratch"), cls="left")
    if req.user_info.capability_ok("mp"):
        all_shells = cdef_user.read_possible_shells()
        shell_list = html_tools.selection_list(req, "shells", {}, sort_new_keys=0, title="login shell")
        shell_idx, act_shell_idx = (0, 0)
        for shell in all_shells:
            if shell == act_user.shell:
                act_shell_idx = shell_idx
            shell_list[shell_idx] = shell
            shell_idx += 1
        info_fs = [("titan", 8 , ""), ("vname", 16, ""), ("nname", 16, ""),
                   ("email", 32, ""), ("pager", 32, ""), ("tel",   32, ""), ("aliases", 32, ""),
                   ("com",   48, "user comment"), ("pass1", 8 , ""), ("pass2", 8 , "")]
        field_dict = {}
        for info_f, show_size, title in info_fs:
            is_pass = info_f.startswith("pass")
            field_dict[info_f] = html_tools.text_field(req, "u%s" % (info_f), size=(is_pass and 8 or 255), display_len=show_size, is_password=is_pass, title=title)
        # init fields
        new_dict = {}
        user_change = False
        for info_f, show_size, title in info_fs:
            db_name = info_f in ["aliases"] and info_f or "user%s" % (info_f)
            if info_f.startswith("pass"):
                new_dict[info_f] = field_dict[info_f].check_selection("", "")
                field_dict[info_f][""] = ""
            else:
                act_v = getattr(act_user, db_name)
                new_dict[info_f] = field_dict[info_f].check_selection("", act_v)
                if act_v != new_dict[info_f]:
                    setattr(act_user, db_name, new_dict[info_f])
                    user_change = True
        if new_dict["pass1"] or new_dict["pass2"]:
            if new_dict["pass2"] == new_dict["pass1"]:
                if len(new_dict["pass1"]) < 5:
                    action_log.add_warn("cannot change password", "password must have at least 5 chars")
                else:
                    act_user.passwordf = crypt.crypt(new_dict["pass1"], "".join([chr(random.randint(97, 122)) for x in range(16)]))
                    user_change = True
            else:
                action_log.add_warn("cannot change password", "the two passwords differ")
        # new shell
        new_shell = shell_list.check_selection("", act_shell_idx)
        if new_shell != act_shell_idx:
            act_user["shell"] = all_shells[new_shell]
            user_change = True
        if user_change:
            act_user.save()
            #act_user.commit_sql_changes(req.dc, 1, 0, 0)
##            err_list, warn_list, ok_list = act_user.build_change_lists("altered ", " for user %s" % (act_user["login"]), 1, 0, 1)
##            action_log.add_errors(err_list)
##            action_log.add_warns(warn_list)
##            action_log.add_oks(ok_list)
            tools.signal_yp_ldap_server(req, action_log)
        info_table[0][0]    = html_tools.content("Responsible persion:", cls="right")
        resp_pers = (" ".join([act_user.usertitan, act_user.uservname, act_user.usernname])).strip()
        info_table[None][0] = html_tools.content([field_dict["titan"], " ", field_dict["vname"], " ", field_dict["nname"]], cls="left")
        info_table[None][0] = html_tools.content("Telefon:", cls="right")
        info_table[None][0] = html_tools.content(field_dict["tel"], cls="left")
        info_table[0][0]    = html_tools.content("E-Mail:", cls="right")
        info_table[None][0] = html_tools.content(field_dict["email"], cls="left")
        info_table[None][0] = html_tools.content("Pager:", cls="right")
        info_table[None][0] = html_tools.content(field_dict["pager"], cls="left")
        info_table[0][0] = html_tools.content("Comment:", cls="right")
        info_table[None][0] = html_tools.content(field_dict["com"], cls="left")
        info_table[None][0] = html_tools.content("Password:", cls="right")
        info_table[None][0] = html_tools.content(field_dict["pass1"], cls="left")
        info_table[0][0] = html_tools.content("Shell:", cls="right")
        info_table[None][0] = html_tools.content(shell_list, cls="left")
        info_table[None][0] = html_tools.content("again:", cls="right")
        info_table[None][0] = html_tools.content(field_dict["pass2"], cls="left")
        info_table[0][0] = html_tools.content("Aliases:", cls="right")
        info_table[None][0:3] = html_tools.content(field_dict["aliases"], cls="left")
    else:
        info_table[0][0]    = html_tools.content("Responsible persion:", cls="right")
        resp_pers = (" ".join([act_user["usertitan"], act_user["uservname"], act_user["usernname"]])).strip()
        info_table[None][0] = html_tools.content(resp_pers or "---", cls="left")
        info_table[None][0] = html_tools.content("Telefon:", cls="right")
        info_table[None][0] = html_tools.content(act_user["usertel"] or "---", cls="left")
        info_table[0][0]    = html_tools.content("E-Mail:", cls="right")
        info_table[None][0] = html_tools.content(act_user["useremail"] or "---", cls="left")
        info_table[None][0] = html_tools.content("Pager:", cls="right")
        info_table[None][0] = html_tools.content(act_user["userpager"] or "---", cls="left")
        info_table[0][0] = html_tools.content("Comment:", cls="right")
        info_table[None][0] = html_tools.content(act_user["usercom"] or "---", cls="left")
        info_table[None][0] = html_tools.content("Shell:", cls="right")
        info_table[None][0] = html_tools.content(act_user["shell"] or "---", cls="left")
        info_table[0][0] = html_tools.content("Aliases:", cls="right")
        info_table[None][0:3] = html_tools.content(act_user["aliases"] or "no aliases set", cls="left")
    if req.user_info.capability_ok("mp"):
        req.write("<form action=\"%s.py?%s\" method=post>" % (req.module_name,
                                                              functions.get_sid(req)))
    req.write(info_table(""))
    show_var_names = []
##    if req.user_info.capability_ok("mpsh"):
##        show_var_names = act_user.get_user_var_names(include_hidden=True)
##    else:
##        show_var_names = act_user.get_user_var_names()
    if show_var_names:
        req.write(html_tools.gen_hline("%s found" % (logging_tools.get_plural("User variable", len(show_var_names))), 3))
        var_table = html_tools.html_table(cls="normal")
        var_table[0]["class"] = "line01"
        for h_name in ["Name", "Type", "Hidden", "Value", "Description"]:
            var_table[None][0] = html_tools.content(h_name, cls="center", type="th")
        line_idx = 0
        for var_name in show_var_names:
            var_table[0]["class"] = "line1%d" % (line_idx)
            user_var = act_user.get_user_var(var_name)
            line_idx = 1 - line_idx
            var_table[None][0] = html_tools.content(user_var.name, cls="left")
            var_table[None][0] = html_tools.content(user_var.get_type_str(), cls="center")
            var_table[None][0] = html_tools.content(user_var.hidden and "yes" or "no", cls="center")
            var_table[None][0] = html_tools.content(user_var.get_value_str(), cls="center")
            var_table[None][0] = html_tools.content(user_var.description, cls="left")
        req.write(var_table(""))
    else:
        req.write(html_tools.gen_hline("No user_vars to display found", 3))
    if req.user_info.capability_ok("mp"):
        select_button = html_tools.submit_button(req, "submit")
        req.write("<div class=\"center\">%s</div></form>" % (select_button("")))
    

def process_page(req):
    if req.conf["genstuff"].has_key("AUTO_RELOAD"):
        del req.conf["genstuff"]["AUTO_RELOAD"]

    functions.write_header(req)
    functions.write_body(req)

    action_log = html_tools.message_log()

    act_ug_tree = cdef_user.user_group_tree(req)

    show_login_info(req, act_ug_tree, action_log)
    req.write(action_log.generate_stack("Log"))
        
    act_group = act_ug_tree.get_group(req)
    cap_headline, cap_table = cdef_user.show_capability_info(req, act_ug_tree, act_group, req.user_info, None)
    req.write("%s%s" % (html_tools.gen_hline(cap_headline, 2),
                        cap_table and cap_table("") or ""))
