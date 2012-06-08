#!/usr/bin/python -Ot
# -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008,2009,2012 Andreas Lang-Nevyjel, init.at
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
import tools
import html_tools
import cdef_user
import random
import crypt
try:
    import smbpasswd
except:
    smbpasswd = None
import process_tools
from django.db.models import Q
from django.contrib.auth.models import Permission, Group, User
from init.cluster.backbone.models import capability, only_wf_perms, user, group, new_config, group_cap, user_cap, \
     user_group

def module_info():
    return {"user" : {"description" : "User configuration",
                      "priority"    : 10},
            "li" : {"description"           : "User config",
                    "default"               : False,
                    "enabled"               : True,
                    "left_string"           : "User configuration",
                    "right_string"          : "Create users and groups",
                    "priority"              : -60,
                    "capability_group_name" : "user"},
            "mg" : {"default"                : False,
                    "enabled"                : True,
                    "description"            : "Modify Groups",
                    "mother_capability_name" : "li"},
            "bg" : {"default"                : False,
                    "enabled"                : True,
                    "description"            : "Browse Groups",
                    "mother_capability_name" : "li"},
            "bu" : {"default"                : False,
                    "enabled"                : True,
                    "description"            : "Browse Users",
                    "mother_capability_name" : "li"},
            "mu" : {"default"                : False,
                    "enabled"                : True,
                    "description"            : "Modify Users",
                    "mother_capability_name" : "bu"},
            "sql" : {"default"                : False,
                     "enabled"                : True,
                     "description"            : "Display SQL statistics",
                     "mother_capability_name" : "li"},
            "prf" : {"default"                : False,
                     "enabled"                : True,
                     "description"            : "Profile webfrontend",
                     "mother_capability_name" : "li"}}

def _set_samba_password(user_dict, pass1):
    if smbpasswd:
        user_dict["nt_password"] = smbpasswd.nthash(pass1)
        user_dict["lm_password"] = smbpasswd.lmhash(pass1)
    else:
        # set dummy passwords
        user_dict["nt_password"] = ""
        user_dict["lm_password"] = ""

def get_system_user_ids():
    try:
        pwf = dict([(int(y[2]), y[0]) for y in [x.split(":") for x in file("/etc/passwd", "r").read().split("\n") if x.count(":") == 6] if y[2].isdigit()])
    except:
        pwf = {}
    return pwf

def get_system_group_ids():
    try:
        pwf = dict([(int(y[2]), y[0]) for y in [x.split(":") for x in file("/etc/group", "r").read().split("\n") if x.count(":") == 3] if y[2].isdigit()])
    except:
        pwf = {}
    return pwf

def generate_user_masks(req, act_ug_tree, action_log, op_mode):
    u_table = html_tools.html_table(cls = "user")
    hidden_list = []
    line_idx = 0
    g_names = act_ug_tree.get_all_group_names()
    u_names = act_ug_tree.get_all_user_names()
    active_field = html_tools.checkbox(req, "active")
    del_field = html_tools.checkbox(req, "del")
    rebuild_yp = False
    if op_mode == "bu":
        req.write(html_tools.gen_hline("Showing %s" % (logging_tools.get_plural("user", len(u_names))), 2))
        u_table[0]["class"] = "line00"
        for what, form in [("del"    , "c"),
                           ("name"   , "c"),
                           ("uid"    , "c"),
                           ("active" , "c"),
                           ("aliases", "c"),
                           ("comment", "c"),
                           ("mail"   , "c"),
                           ("info"   , "c"),
                           ("sgroups", "c"),
                           ("# caps" , "c")]:
            u_table[None][0] = html_tools.content(what, type="th", cls={"c" : "center",
                                                                        "l" : "left",
                                                                        "r" : "right"}[form])
        for g_name in g_names:
            act_group = act_ug_tree.get_group(g_name)
            u_table[0]["class"] = "line01"
            u_table[None][0:10] = html_tools.content("Group %s (gid %d, %s, %s)" % (g_name,
                                                                                   act_group.gid,
                                                                                   logging_tools.get_plural("user", act_group.get_num_users()),
                                                                                   logging_tools.get_plural("capability", act_group.get_num_capabilities())), type="th", cls="center")
            for u_name in u_names:
                act_user = act_ug_tree.get_user(u_name)
                if act_ug_tree.get_group(act_user.group_id).groupname == g_name:
                    u_idx = act_user.pk
                    active_field.check_selection(act_user.get_suffix(), act_user.active)
                    del_field[act_user.get_suffix()] = 0
                    line_idx = 1 - line_idx
                    u_table[0]["class"] = "line1%d" % (line_idx)
                    da_active = (act_user.pk != req.session_data.user_info.pk) and req.user_info.django_user.has_perm("backbone.wf_mu")
                    u_table[None][0] = html_tools.content(da_active and del_field or "---", act_user.get_suffix(), cls="errormin")
                    u_table[None][0] = html_tools.content(u_name, act_user.get_suffix(), cls="left")
                    u_table[None][0] = html_tools.content(str(act_user.uid), act_user.get_suffix(), cls="center")
                    u_table[None][0] = html_tools.content(da_active and active_field or (act_user.active and "yes" or "no"), act_user.get_suffix(), cls="center")
                    u_table[None][0] = html_tools.content(act_user.aliases or "---", act_user.get_suffix(), cls="center")
                    u_table[None][0] = html_tools.content(act_user.usercom or "---", act_user.get_suffix(), cls="center")
                    u_table[None][0] = html_tools.content(act_user.useremail or "---", act_user.get_suffix(), cls="right")
                    user_pers = (" ".join([act_user.usertitan, act_user.uservname, act_user.usernname])).strip()
                    u_table[None][0] = html_tools.content(user_pers or "---", cls="left")
                    u_table[None][0] = html_tools.content(act_user.get_secondary_groups() and ",".join(["%d" % (act_ug_tree.get_group(sg.pk)["gid"]) for sg in act_user.get_secondary_groups() if act_ug_tree.group_exists(x)]) or "---", cls="center")
                    u_table[None][0] = html_tools.content(act_user.get_num_capabilities() and "%d" % (act_user.get_num_capabilities()) or "---", cls="center")
        req.write("<form action=\"%s.py?%s&opmode=bux\" method=post>%s%s" % (req.module_name,
                                                                             functions.get_sid(req),
                                                                             "\n".join([x.create_hidden_var() for x in hidden_list]),
                                                                             u_table("")))

        submit_button = html_tools.submit_button(req, "submit")
    elif op_mode == "bux":
        del_list, act_list, inact_list = ([], [], [])
        for u_name in u_names:
            act_user = act_ug_tree.get_user(u_name)
            u_idx = act_user.pk
            if del_field.check_selection(act_user.get_suffix(), 0):
                del_list.append(u_idx)
            else:
                if u_idx != req.session_data.user_info.pk:
                    if active_field.check_selection(act_user.get_suffix(), 0) and not act_user.active:
                        act_list.append(u_idx)
                    elif not active_field.check_selection(act_user.get_suffix(), 0) and act_user.active:
                        inact_list.append(u_idx)
        if del_list or act_list or inact_list:
            del_field = html_tools.text_field(req, "de", size=1024, display_len=8)
            del_field.check_selection("", ":".join(["%d" % (x) for x in del_list]))
            act_field = html_tools.text_field(req, "sa", size=1024, display_len=8)
            act_field.check_selection("", ":".join(["%d" % (x) for x in act_list]))
            inact_field = html_tools.text_field(req, "sia", size=1024, display_len=8)
            inact_field.check_selection("", ":".join(["%d" % (x) for x in inact_list]))
            hidden_list.extend([del_field, act_field, inact_field])
            req.write(html_tools.gen_hline("Ok to %s ?" % (", ".join([x for x in [len(act_list)   and "activate %s" % (logging_tools.get_plural("user", len(act_list))) or "",
                                                                                  len(inact_list) and "deactivate %s" % (logging_tools.get_plural("user", len(inact_list))) or "",
                                                                                  len(del_list)   and "delete %s" % (logging_tools.get_plural("user", len(del_list))) or ""]
                                                                      if x]))
                                           , 2))
            
            req.write("<form action=\"%s.py?%s&opmode=bux2\" method=post>%s" % (req.module_name,
                                                                                functions.get_sid(req),
                                                                                "\n".join([x.create_hidden_var() for x in hidden_list])))
            submit_button = html_tools.submit_button(req, "modify")
        else:
            submit_button = None
    elif op_mode == "bux2":
        log_list = []
        for what, ft in [("deleted", "de"), ("inactivated", "sia"), ("activated", "sa")]:
            act_field = html_tools.text_field(req, ft, size=1024, display_len=8)
            act_list = [int(x) for x in act_field.check_selection("").split(":") if x]
            if act_list:
                log_list.append("%s %s" % (what, logging_tools.get_plural("user", len(act_list))))
                w_str = " OR ".join(["user_idx=%d" % (x) for x in act_list])
                w2_str = " OR ".join(["user=%d" % (x) for x in act_list])
                action_log.add_ok("%s %s: %s" % (what, logging_tools.get_plural("user", len(act_list)),
                                                 ", ".join([act_ug_tree.get_user(x).login for x in act_list])), "SQL")
                if ft == "de":
                    User.objects.filter(Q(username__in=user.objects.filter(Q(pk__in=act_list)).values_list("login", flat=True))).delete()
                    user.objects.filter(Q(pk__in=act_list)).delete()
                elif ft == "sa":
                    req.dc.execute("UPDATE user SET active=1 WHERE %s" % (w_str))
                elif ft == "sia":
                    req.dc.execute("UPDATE user SET active=0 WHERE %s" % (w_str))
        if log_list:
            rebuild_yp = True
        else:
            log_list = ["Nothing to do (?)"]
        req.write("%s<form action=\"%s.py?%s\" method=post>%s" % (html_tools.gen_hline(", ".join(log_list), 2),
                                                                  req.module_name,
                                                                  functions.get_sid(req),
                                                                  "\n".join([x.create_hidden_var() for x in hidden_list])))
        submit_button = html_tools.submit_button(req, "ok")
    if rebuild_yp:
        tools.signal_yp_ldap_server(req, action_log)
    return submit_button

def generate_group_masks(req, act_ug_tree, action_log, op_mode):
    g_table = html_tools.html_table(cls = "user")
    hidden_list = []
    line_idx = 0
    g_names = act_ug_tree.get_all_group_names()
    active_field = html_tools.checkbox(req, "active")
    del_field = html_tools.checkbox(req, "del")
    rebuild_yp = False
    if op_mode == "bg":
        req.write(html_tools.gen_hline("Showing %s" % (logging_tools.get_plural("group", len(g_names))), 2))
        g_table[0]["class"] = "line00"
        for what, form in [("del", "c"), ("name", "c"), ("gid", "c"), ("active", "c"), ("comment", "c"), ("mail", "r"), ("# users", "c"), ("# caps", "c"), ("Resp. Person", "r")]:
            g_table[None][0] = html_tools.content(what, type="th", cls={"c" : "center",
                                                                        "l" : "left",
                                                                        "r" : "right"}[form])
        for g_name in g_names:
            act_group = act_ug_tree.get_group(g_name)
            g_idx = act_group.pk
            active_field.check_selection(act_group.get_suffix(), act_group.active)
            del_field[act_group.get_suffix()] = 0
            line_idx = 1 - line_idx
            g_table[0]["class"] = "line1%d" % (line_idx)
            g_table[None][0] = html_tools.content(act_group.get_num_users() and "&nbsp;" or del_field, act_group.get_suffix(), cls="center")
            g_table[None][0] = html_tools.content(g_name, act_group.get_suffix(), cls="left")
            g_table[None][0] = html_tools.content(str(act_group.gid), act_group.get_suffix(), cls="center")
            g_table[None][0] = html_tools.content(act_group.pk == req.session_data.user_info.group_id and "yes" or active_field, act_group.get_suffix(), cls="center")
            g_table[None][0] = html_tools.content(act_group.groupcom or "---", act_group.get_suffix(), cls="center")
            g_table[None][0] = html_tools.content(act_group.respemail or "---", act_group.get_suffix(), cls="right")
            g_table[None][0] = html_tools.content(act_group.get_num_users() and str(act_group.get_num_users()) or "-", act_group.get_suffix(), cls="center")
            g_table[None][0] = html_tools.content(act_group.get_num_capabilities() and str(act_group.get_num_capabilities()) or "-", act_group.get_suffix(), cls="center")
            resp_pers = (" ".join([act_group.resptitan, act_group.respvname, act_group.respnname])).strip()
            g_table[None][0] = html_tools.content(resp_pers or "---", cls="left")
        req.write("<form action=\"%s.py?%s&opmode=bgx\" method=post>%s%s" % (req.module_name,
                                                                            functions.get_sid(req),
                                                                            "\n".join([x.create_hidden_var() for x in hidden_list]),
                                                                            g_table("")))

        submit_button = html_tools.submit_button(req, "submit")
    elif op_mode == "bgx2":
        log_list = []
        for what, ft in [("deleted"    , "de"),
                         ("inactivated", "sia"),
                         ("activated"  , "sa")]:
            act_field = html_tools.text_field(req, ft, size=1024, display_len=8)
            act_list = [int(x) for x in act_field.check_selection("").split(":") if x]
            if act_list:
                log_list.append("%s %s" % (what, logging_tools.get_plural("group", len(act_list))))
                w_str = " OR ".join(["ggroup_idx=%d" % (x) for x in act_list])
                action_log.add_ok("%s %s: %s" % (what, logging_tools.get_plural("group", len(act_list)), ", ".join([act_ug_tree.get_group(x).groupname for x in act_list])), "SQL")
                if ft == "de":
                    Group.objects.filter(Q(name__in=group.objects.filter(Q(pk__in=act_list)).values_list("groupname", flat=True))).delete()
                    group.objects.filter(Q(pk__in=act_list)).delete()
                elif ft == "sa":
                    req.dc.execute("UPDATE ggroup SET active=1 WHERE %s" % (w_str))
                elif ft == "sia":
                    req.dc.execute("UPDATE ggroup SET active=0 WHERE %s" % (w_str))
        if log_list:
            rebuild_yp = True
        else:
            log_list = ["Nothing to do (?)"]
        req.write("%s<form action=\"%s.py?%s\" method=post>%s" % (html_tools.gen_hline(", ".join(log_list), 2),
                                                                  req.module_name,
                                                                  functions.get_sid(req),
                                                                  "\n".join([x.create_hidden_var() for x in hidden_list])))
        submit_button = html_tools.submit_button(req, "ok")
    else:
        del_list, act_list, inact_list = ([], [], [])
        for g_name in g_names:
            act_group = act_ug_tree.get_group(g_name)
            g_idx = act_group.pk
            #print g_name, act_group.get_suffix(),active_field.check_selection(act_group.get_suffix())
            if del_field.check_selection(act_group.get_suffix(), 0):
                del_list.append(g_idx)
            else:
                if g_idx != req.session_data.user_info.group_id:
                    if active_field.check_selection(act_group.get_suffix(), 0) and not act_group.active:
                        act_list.append(g_idx)
                    elif not active_field.check_selection(act_group.get_suffix(), 0) and act_group.active:
                        inact_list.append(g_idx)
        if del_list or act_list or inact_list:
            del_field = html_tools.text_field(req, "de", size=1024, display_len=8)
            del_field.check_selection("", ":".join(["%d" % (x) for x in del_list]))
            act_field = html_tools.text_field(req, "sa", size=1024, display_len=8)
            act_field.check_selection("", ":".join(["%d" % (x) for x in act_list]))
            inact_field = html_tools.text_field(req, "sia", size=1024, display_len=8)
            inact_field.check_selection("", ":".join(["%d" % (x) for x in inact_list]))
            hidden_list.extend([del_field, act_field, inact_field])
            req.write(html_tools.gen_hline("Ok to %s ?" % (", ".join([x for x in [len(act_list)   and "activate %s" % (logging_tools.get_plural("group", len(act_list))) or "",
                                                                                  len(inact_list) and "deactivate %s" % (logging_tools.get_plural("group", len(inact_list))) or "",
                                                                                  len(del_list)   and "delete %s" % (logging_tools.get_plural("group", len(del_list)))]
                                                                      if x]))
                                           , 2))

            req.write("<form action=\"%s.py?%s&opmode=bgx2\" method=post>%s" % (req.module_name,
                                                                                functions.get_sid(req),
                                                                                "\n".join([x.create_hidden_var() for x in hidden_list])))
            submit_button = html_tools.submit_button(req, "modify")
        else:
            req.write(html_tools.gen_hline("Nothing to do", 2))
            req.write("<form action=\"%s.py?%s\" method=post>%s" % (req.module_name,
                                                                    functions.get_sid(req),
                                                                    "\n".join([x.create_hidden_var() for x in hidden_list])))
            submit_button = html_tools.submit_button(req, "ok")
    if rebuild_yp:
        tools.signal_yp_ldap_server(req, action_log)
    return submit_button

def generate_user_mask(req, act_ug_tree, action_log, op_mode, act_user = None):
    #print req.conf["server"]
    line_idx = 0
    name_field        = html_tools.text_field(req, "uname", size=15, display_len=15)
    rel_home_field    = html_tools.text_field(req, "rhome", size=15, display_len=15, title="relative to HOMESTART of group (leave empty for loginname)")
    rel_scratch_field = html_tools.text_field(req, "rscratch", size=15, display_len=15, title="relative to SCRATCHSTART of group (leave empty for loginname)")
    uid_list          = html_tools.selection_list(req, "uidl", {0 : "enter number:"}, sort_new_keys=False)
    uid_field         = html_tools.text_field(req, "uidn", size=8, display_len=8)
    uids_written, min_uid, max_uid = (0, 200, 65000)
    vname_field = html_tools.text_field(req, "vname", size=255, display_len=32)
    nname_field = html_tools.text_field(req, "nname", size=255, display_len=32)
    titan_field = html_tools.text_field(req, "titan", size=255, display_len=5)
    email_field = html_tools.text_field(req, "email", size=255, display_len=32)
    tel_field   = html_tools.text_field(req, "tel", size=255, display_len=32)
    pag_field   = html_tools.text_field(req, "pag", size=255, display_len=32)
    com_field   = html_tools.text_field(req, "com", size=255, display_len=48)
    pass1_field = html_tools.text_field(req, "pwd1", size=16, display_len=16, is_password=True)
    pass2_field = html_tools.text_field(req, "pwd2", size=16, display_len=16, is_password=True)
    alias_field = html_tools.text_field(req, "alias", size=256, display_len=48)
    cap_field   = html_tools.checkbox(req, "caps")
    # active
    act_field   = html_tools.checkbox(req, "active")
    # create quota
    create_quota_field = html_tools.checkbox(req, "quota")
    # cluster-contact
    ccontact_field     = html_tools.checkbox(req, "ccontact")
    sge_list, sge_lut, dc_list = (html_tools.selection_list(req, "sge", {}, multiple=True, sort_new_keys=False),
                                  {},
                                  [])
    # sge-user, ignore right now, FIXME
    if False:
        req.dc.execute("SELECT d.name, dc.device_config_idx, c.name AS confname, cs.name AS csname, cs.value FROM " + \
                       "device d, device_config dc, new_config c LEFT JOIN config_str cs ON cs.new_config=c.new_config_idx WHERE " + \
                       "c.name LIKE('sge_server%') AND c.new_config_idx=dc.new_config AND dc.device=d.device_idx ORDER BY d.name")
        for db_rec in req.dc.fetchall():
            if not sge_lut.has_key(db_rec["device_config_idx"]):
                dc_list.append(db_rec["device_config_idx"])
                sge_lut[db_rec["device_config_idx"]] = {"device"     : db_rec["name"],
                                                        "config"     : db_rec["confname"],
                                                        "name"       : db_rec["name"],
                                                        "cellname"   : "not set",
                                                        "user_count" : 0}
            if db_rec["csname"] == "cellname":
                sge_lut[db_rec["device_config_idx"]]["cellname"] = db_rec["value"]
    for user_stuff in act_ug_tree.get_all_users():
        for sge_s_idx in user_stuff.get_sge_servers():
            sge_lut[sge_s_idx]["user_count"] += 1
    prev_sge_server, prev_sge_server_count = (0, -1)
    for dc_idx in dc_list:
        sge_entry = sge_lut[dc_idx]
        sge_list[dc_idx] = "on %s (cell %s, %s)" % (sge_entry["name"], sge_entry["cellname"], logging_tools.get_plural("user", sge_entry["user_count"]))
        if sge_entry["user_count"] > prev_sge_server_count:
            prev_sge_server_count, prev_sge_server = (sge_entry["user_count"], dc_idx)
    # user-device-login
    udl_list, udl_lut = (html_tools.selection_list(req, "ulogin", {}, multiple=True, sort_new_keys=False),
                         {})
    if req.conf["server"].has_key("server"):
        srv_list = sorted(req.conf["server"]["server"].keys())
        if srv_list:
            req.dc.execute("SELECT d.name, d.device_idx FROM device d WHERE %s" % (" OR ".join(["d.name='%s'" % (name) for name in srv_list])))
            udl_lut = dict([(db_rec["name"], db_rec["device_idx"]) for db_rec in req.dc.fetchall()])
            for srv_name in srv_list:
                udl_list[udl_lut[srv_name]] = srv_name
    # fetch system user id
    sys_user_dict = get_system_user_ids()
    newuser_name, newuser_idx = ("newuser", 0)
    if act_user:
        used_uids = [x.uid for x in act_ug_tree.get_all_users() if act_user and not x.pk == act_user.pk]
        used_aliases = sum([x.aliases and x.aliases.split() or [] for x in act_ug_tree.get_all_users() if act_user and not x == act_user], [])
        act_uid = max(min_uid, act_user.uid - 10)
        used_names = [x.login for x in act_ug_tree.get_all_users() if act_user and not x == act_user]
        all_used_names = [x.login for x in act_ug_tree.get_all_users() if act_user]
        while newuser_name in used_names:
            newuser_idx += 1
            newuser_name = "newuser%d" % (newuser_idx)
    else:
        used_uids = [x.uid for x in act_ug_tree.get_all_users()]
        used_aliases = sum([x.aliases and x.aliases.split() or [] for x in act_ug_tree.get_all_users()], [])
        if used_uids:
            act_uid = max(min_uid, min(used_uids) - 10)
        else:
            act_uid = min_uid
        used_names = [x.login for x in act_ug_tree.get_all_users()]
        all_used_names = [x.login for x in act_ug_tree.get_all_users()]
        while newuser_name in used_names:
            newuser_idx += 1
            newuser_name = "newuser%d" % (newuser_idx)
    used_aliases = [x for x in used_aliases if x]
    try:
        dummy_set = set([0, 1])
    except:
        free_uids_str = ""
    else:
        free_uids_str = logging_tools.compress_num_list(set(xrange(min_uid, max_uid + 1)).difference(set(sys_user_dict.keys() + used_uids)))
    last_uid_written, mark_idx = (0, 0)
    while uids_written < 20:
        if act_uid in used_uids or act_uid in sys_user_dict.keys():
            act_uid += 1
        else:
            if not uids_written and op_mode == "cu":
                uid_field.check_selection("", act_uid)
            uids_written += 1
            if last_uid_written and act_uid != last_uid_written + 1:
                mark_idx -= 1
                uid_list[mark_idx] = {"name"     : "------ %s used ------" % (logging_tools.get_plural("uid", act_uid - last_uid_written - 1)),
                                      "disabled" : True}
            uid_list[act_uid] = "%d" % (act_uid)
            last_uid_written = act_uid
            act_uid += 1
    # primary / secondary group list
    pgroup_field, sgroup_field = (html_tools.selection_list(req, "pgroup", sort_new_keys=False),
                                  html_tools.selection_list(req, "sgroup", multiple=True, sort_new_keys=False))
    # home exports / scratch exports
    home_field, scratch_field = (html_tools.selection_list(req, "homedir", {0 : "None"}, sort_new_keys=False),
                                 html_tools.selection_list(req, "scratchdir", {0 : "None"}, sort_new_keys=False))
    num_homes, num_scratches = (0, 0)
    home_lut, scratch_lut = ({}, {})
    home_usecount, scratch_usecount, pgroup_usecount = ({}, {}, {})
    any_quota_ok = False
    for home_dev, home_infos in act_ug_tree.get_export_dict().get("homeexport", {}).iteritems():
        for home_idx, home_dir, quota_ok in home_infos:
            home_field[home_idx] = "%s on %s%s" % (home_dir, home_dev, quota_ok and "(quota capable)" or "")
            home_lut[home_idx] = home_dev
            home_usecount[home_idx] = 0
            if quota_ok:
                any_quota_ok = True
            num_homes += 1
    for scratch_dev, scratch_infos in act_ug_tree.get_export_dict().get("scratchexport", {}).iteritems():
        for scratch_idx, scratch_dir, quota_ok in scratch_infos:
            scratch_field[scratch_idx] = "%s on %s%s" % (scratch_dir, scratch_dev, quota_ok and "(quota capable)" or "")
            scratch_lut[scratch_idx] = scratch_dev
            scratch_usecount[scratch_idx] = 0
            if quota_ok:
                any_quota_ok = True
            num_scratches += 1
    for user_stuff in act_ug_tree.get_all_users():
        idx = user_stuff.pk
        if user_stuff.export_id and home_usecount.has_key(user_stuff.export_id):
            home_usecount[user_stuff.export_id] += 1
        if user_stuff.export_scr_id and scratch_usecount.has_key(user_stuff.export_scr_id):
            scratch_usecount[user_stuff.export_scr_id] += 1
        pgroup_usecount.setdefault(user_stuff.group_id, 0)
        pgroup_usecount[user_stuff.group_id] += 1
    if home_usecount:
        min_count = min(home_usecount.values())
        prefered_home = [k for k, v in home_usecount.iteritems() if v == min_count][0]
    else:
        prefered_home = 0
    if scratch_usecount:
        min_count = min(scratch_usecount.values())
        prefered_scratch = [k for k, v in scratch_usecount.iteritems() if v == min_count][0]
    else:
        prefered_scratch = 0
    prefered_pgroup = [k for k, v in pgroup_usecount.iteritems() if v == max(pgroup_usecount.values())][0]
    g_names = act_ug_tree.get_all_group_names()
    for g_name in g_names:
        g_group = act_ug_tree.get_group(g_name)
        pgroup_field[g_group.pk] = "%s [ gid = %d, homestart is '%s', scratchstart is '%s' ] " % (g_name, g_group.gid, g_group.homestart, g_group.scratchstart)
        sgroup_field[g_group.pk] = "%s [ gid = %d ] " % (g_name, g_group.gid)
    # shells
    all_shells = cdef_user.read_possible_shells()
    shell_list = html_tools.selection_list(req, "shells", {}, sort_new_keys=False)
    shell_idx, preferd_shell_idx, act_user_shell = (0, 0, 0)
    for shell in all_shells:
        if shell == "/bin/bash":
            preferd_shell_idx = shell_idx
        shell_list[shell_idx] = shell
        if act_user and act_user.shell == shell:
            act_user_shell = shell_idx
        shell_idx += 1
    # hidden vars
    hidden_list = []
    # flags: show_table, create_user
    show_table, rebuild_yp, ok_target, com_list, post_com_list = (True, False, "", [], [])
    new_pwd = None
    if op_mode == "cu":
        # create of new user
        name_field.check_selection("", newuser_name)
        rel_home_field.check_selection("", "")
        rel_scratch_field.check_selection("", "")
        act_user = user(login=newuser_name,
                        uid=0)
        #act_user.act_values_are_default()
        titan_field.check_selection("", "title")
        vname_field.check_selection("", "first name")
        nname_field.check_selection("", "last name")
        tel_field.check_selection("", "+43 1 ")
        pag_field.check_selection("", "")
        email_field.check_selection("", "")
        com_field.check_selection("", "User info")
        uid_list.check_selection("", 0)
        shell_list.check_selection("", preferd_shell_idx)
        act_field.check_selection("", 1)
        ccontact_field.check_selection("", 0)
        sge_list.check_selection("", [prev_sge_server])
        udl_list.check_selection("", [])
        pgroup_field.check_selection("", prefered_pgroup)
        sgroup_field.check_selection("", [])
        home_field.check_selection("", prefered_home)
        scratch_field.check_selection("", prefered_scratch)
        # generate new password
        new_pwd = process_tools.create_password(length=8)
        pass1_field.check_selection("", new_pwd)
        pass2_field.check_selection("", new_pwd)
        alias_field.check_selection("", "")
        create_quota_field.check_selection("", any_quota_ok)
        cap_dict = {}
        for cap_idx in act_ug_tree.cap_stack.get_all_cap_idxs():
            act_cap = act_ug_tree.cap_stack[cap_idx]
            act_val = cap_field.check_selection(act_cap.name, False)
            cap_dict[act_cap.name] = (act_val, act_cap.idx)
    elif op_mode == "mum":
        # modify user
        name_field.check_selection("", act_user.login)
        titan_field.check_selection("", act_user.usertitan)
        vname_field.check_selection("", act_user.uservname)
        nname_field.check_selection("", act_user.usernname)
        tel_field.check_selection("", act_user.usertel)
        email_field.check_selection("", act_user.useremail)
        tel_field.check_selection("", act_user.usertel)
        pag_field.check_selection("", act_user.userpager)
        email_field.check_selection("", act_user.useremail)
        com_field.check_selection("", act_user.usercom)
        shell_list.check_selection("", act_user_shell)
        uid_list.check_selection("", act_user.uid)
        uid_field.check_selection("", act_user.uid)
        pgroup_field.check_selection("", act_user.group_id)
        sgroup_field.check_selection("", [cur_g.pk for cur_g in act_user.get_secondary_groups()])
        pass1_field.check_selection("", "")
        pass2_field.check_selection("", "")
        alias_field.check_selection("", act_user.aliases or "")
        act_field.check_selection("", act_user.active)
        ccontact_field.check_selection("", act_user.cluster_contact)
        rel_home_field.check_selection("", act_user.home)
        rel_scratch_field.check_selection("", act_user.scratch)
        sge_list.check_selection("", act_user.get_sge_servers())
        # FIXME
        udl_list.check_selection("", [])#act_user.get_login_servers())
        hidden_uid = html_tools.text_field(req, "ulist", size=8, display_len=8)
        hidden_uid.check_selection("", str(act_user.uid))
        hidden_list.append(hidden_uid)
        cap_dict = {}
        for cap_idx in act_ug_tree.cap_stack.get_all_cap_idxs():
            act_cap = act_ug_tree.cap_stack[cap_idx]
            act_val = cap_field.check_selection(act_cap.name, act_user.capability_ok(act_cap.name))
            cap_dict[act_cap.name] = (act_val, act_cap.idx)
    elif op_mode == "muv":
        valid = True
        new_name = name_field.check_selection("")
        if new_name in act_ug_tree.get_all_user_names() and new_name != act_user.login:
            action_log.add_error("Username '%s' already used" % (new_name), "already used")
            valid = False
        titan, nname, vname, aliases = (titan_field.check_selection(""),
                                        nname_field.check_selection(""),
                                        vname_field.check_selection(""),
                                        alias_field.check_selection(""))
        tel, email, pager, comment = (tel_field.check_selection(""),
                                      email_field.check_selection(""),
                                      pag_field.check_selection(""),
                                      com_field.check_selection(""))
        rel_home_dir, rel_scratch_dir = (rel_home_field.check_selection("").strip() or new_name,
                                         rel_scratch_field.check_selection("").strip() or new_name)
        # sge_servers, FIXME
        if False:
            new_sge_servers, old_sge_servers = (sge_list.check_selection("", []), [x for x in act_user.get_sge_servers()])
            sge_add_servers    = [x for x in new_sge_servers if x not in old_sge_servers]
            sge_remove_servers = [x for x in old_sge_servers if x not in new_sge_servers]
            sge_keep_servers   = [x for x in new_sge_servers if x     in old_sge_servers]
            for new_s in sge_add_servers:
                act_user.add_sge_server(new_s)
            for old_s in sge_remove_servers:
                act_user.delete_sge_server(old_s)
            act_user["sge_servers"] = [x for x in act_user["sge_servers"]]
        # user-device-login, FIXME
        if False:
            new_udl_servers, old_udl_servers = (udl_list.check_selection("", []), [x for x in act_user.get_login_servers()])
            udl_add_servers    = [x for x in new_udl_servers if x not in old_udl_servers]
            udl_remove_servers = [x for x in old_udl_servers if x not in new_udl_servers]
            udl_keep_servers   = [x for x in new_udl_servers if x     in old_udl_servers]
            for new_s in udl_add_servers:
                act_user.add_login_server(new_s)
            for old_s in udl_remove_servers:
                act_user.delete_login_server(old_s)
            act_user["login_servers"] = [x for x in act_user["login_servers"]]
        #print "*", act_user["sge_servers"]
        if rel_home_dir.count("/"):
            action_log.add_error("Homedir '%s' not valid" % (rel_home_dir), "dir separator found")
            valid = False
        if [True for x in act_ug_tree.get_all_users() if rel_home_dir == x.home and rel_home_dir != act_user.home]:
            action_log.add_error("Homedir '%s' not valid" % (rel_home_dir), "already used")
            valid = False
        if rel_scratch_dir.count("/"):
            action_log.add_error("Scratchdir '%s' not valid" % (rel_scratch_dir), "dir separator found")
            valid = False
        if [True for x in act_ug_tree.get_all_users() if rel_scratch_dir == x.scratch and rel_scratch_dir != act_user.scratch]:
            action_log.add_error("Scratchdir '%s' not valid" % (rel_scratch_dir), "already used")
            valid = False
        is_active = act_field.check_selection("")
        if not is_active and act_user.pk == req.session_data.user_info.pk:
            action_log.add_warn("Cannot disable my own user", "error")
            valid = False
        new_uid, new_uid_f = (uid_list.check_selection(),
                              uid_field.check_selection())
        if new_uid == 0:
            if not new_uid_f.isdigit():
                action_log.add_warn("Entered uid is not an integer", "parse error")
                valid = False
            else:
                new_uid = int(new_uid_f)
        elif new_uid_f.isdigit() and new_uid == act_user.uid:
            new_uid = int(new_uid_f)
        pass1, pass2 = (pass1_field.check_selection(""),
                        pass2_field.check_selection(""))
        change_pass = True
        if pass1 != pass2:
            action_log.add_error("password not correctly entered", "user error")
            valid = False
        elif not (pass1 or pass2):
            # empty password -> keep old
            change_pass = False
        elif len(pass1) < 5:
            action_log.add_error("password not long enough (%s, must be at least 5 characters)" % (logging_tools.get_plural("character", len(pass1))), "user error")
            valid = False
        new_aliases = aliases and aliases.split() or []
        already_used_aliases = [x for x in new_aliases if x in used_aliases]
        if already_used_aliases:
            action_log.add_warn("%s already used: %s" % (logging_tools.get_plural("Alias", len(already_used_aliases)),
                                                         ", ".join(already_used_aliases)), "invalid aliases")
            valid = False
        already_used_aliases = [x for x in new_aliases if x in all_used_names]
        if already_used_aliases:
            action_log.add_warn("%s already used for login: %s" % (logging_tools.get_plural("Alias", len(already_used_aliases)),
                                                                   ", ".join(already_used_aliases)), "invalid aliases")
            valid = False
        if new_uid in used_uids:
            action_log.add_warn("uid is already used by user '%s'" % ([x.login for x in act_ug_tree.get_all_users() if x.uid == new_uid][0]), "invalid uid")
            valid = False
        elif new_uid in sys_user_dict.keys():
            action_log.add_warn("uid is already used by system user '%s'" % (sys_user_dict[new_uid]), "invalid uid")
            valid = False
        new_shell = shell_list.check_selection("")
        cluster_contact, sge_user = (ccontact_field.check_selection(),
                                     sge_list.check_selection("", []))
        new_pgroup = pgroup_field.check_selection("")
        old_sgroups = [cur_g.pk for cur_g in act_user.get_secondary_groups()]
        new_sgroups = [x for x in sgroup_field.check_selection("", []) if x != new_pgroup]
        if act_user.uid == req.user_info.uid:
            if act_user.uid != new_uid:
                action_log.add_warn("cannot change uid of actually logged-in user", "internal")
                valid = False
            if act_user.group_id != new_pgroup:
                action_log.add_warn("cannot change primary group of actually logged-in user", "internal")
                valid = False
        # change of pgroup / uid ?
        pg_uid_change = (act_user.uid != new_uid or act_user.group_id != new_pgroup)
        # change of login ?
        old_name = act_user.login
        login_change = (old_name != new_name)
        # change of homedir ?
        homedir_change = (act_user.home != rel_home_dir)
        if homedir_change:
            old_home_dir = act_user.home
        # change of scratchdir ?
        scratchdir_change = (act_user.scratch != rel_scratch_dir)
        if scratchdir_change:
            old_scratch_dir = act_user.scratch
        cap_dict = {}
        for cap_idx in act_ug_tree.cap_stack.get_all_cap_idxs():
            act_cap = act_ug_tree.cap_stack[cap_idx]
            act_val = cap_field.check_selection(act_cap.name)
            cap_dict[act_cap.name] = (act_val, act_cap.idx)
        if not valid:
            action_log.add_warn("Userdata is not valid", "please check")
            op_mode = "mum"
            hidden_uid = html_tools.text_field(req, "ulist", size=8, display_len=8)
            hidden_uid.check_selection("", str(act_user.uid))
            hidden_list.append(hidden_uid)
        else:
            mod_dict = {"uid"             : new_uid,
                        "active"          : is_active,
                        "group"           : group.objects.get(Q(pk=new_pgroup)),
                        "cluster_contact" : cluster_contact,
                        "login"           : new_name,
                        "uservname"       : vname,
                        "usernname"       : nname,
                        "usertitan"       : titan,
                        "usertel"         : tel,
                        "useremail"       : email,
                        "usercom"         : comment,
                        "aliases"         : aliases,
                        "userpager"       : pager,
                        "home"            : rel_home_dir,
                        "scratch"         : rel_scratch_dir}
            if change_pass:
                mod_dict["password"] = crypt.crypt(pass1, "".join([chr(random.randint(97, 122)) for x in range(16)]))
                _set_samba_password(mod_dict, pass1)
                act_user.django_user.set_password(pass1)
                act_user.django_user.save()
            for key, value in mod_dict.iteritems():
                setattr(act_user, key, value)
            act_user.save()
##            if sge_add_servers:
##                for sge_add in sge_add_servers:
##                    com_list.append(tools.s_command(req, sge_lut[sge_add]["config"]   , 8004, "create_sge_user", [], 20, None, {"username" : new_name}))
##            if sge_remove_servers:
##                for sge_remove in sge_remove_servers:
##                    com_list.append(tools.s_command(req, sge_lut[sge_remove]["config"], 8004, "delete_sge_user", [], 20, None, {"username" : old_name}))
##            if login_change and sge_keep_servers:
##                for sge_keep in sge_keep_servers:
##                    com_list.append(tools.s_command(req, sge_lut[sge_keep]["config"]  , 8004, "rename_sge_user", [], 20, None, {"old_username" : old_name,
##                                                                                                                                "username"     : new_name}))
            if homedir_change:
                if act_user.export:
                    com_list.append(tools.s_command(req, "server", 8004, "modify_user_dir", [], 20, home_lut[act_user.export], {"username"     : new_name,
                                                                                                                                   "old_dir_name" : old_home_dir,
                                                                                                                                   "export_type"  : "home"}))
            if scratchdir_change:
                if act_user.export_scr:
                    com_list.append(tools.s_command(req, "server", 8004, "modify_user_dir", [], 20, scratch_lut[act_user.export_scr], {"username"     : new_name,
                                                                                                                                          "old_dir_name" : old_scratch_dir,
                                                                                                                                          "export_type"  : "scratch"}))
            if pg_uid_change:
                if act_user.export:
                    com_list.append(tools.s_command(req, "server", 8004, "modify_user_uid_gid", [], 20, home_lut[act_user.export], {"username"    : new_name,
                                                                                                                                       "export_type" : "home"}))
                if act_user.export_scr:
                    com_list.append(tools.s_command(req, "server", 8004, "modify_user_uid_gid", [], 20, scratch_lut[act_user.export_scr], {"username"    : new_name,
                                                                                                                                              "export_type" : "scratch"}))
            #err_list, warn_list, ok_list = act_user.build_change_lists("altered ", " for user %s" % (act_user.login), 1, 0, 1)
            warn_list, err_list = ([], [])
            add_list, del_list, ok_list, del_names, add_names = ([], [], [], [], [])
            for cap_name, (set_cap, idx) in cap_dict.iteritems():
                #print cap_name, set_cap, act_group.has_capability(cap_name)
                if set_cap and not act_user.capability_ok(cap_name):
                    add_names.append("wf_%s" % (cap_name))
                    add_list.append(idx)
                    ok_list.append(("Added capability %s" % (cap_name), "sql"))
                elif not set_cap and act_user.capability_ok(cap_name, only_user=True):
                    del_names.append("wf_%s" % (cap_name))
                    del_list.append(idx)
                    ok_list.append(("Deleted capability %s" % (cap_name), "sql"))
            if add_list:
                for cap_add in add_list:
                    user_cap(capability=capability.objects.get(pk=cap_add),
                              user=act_user).save()
                act_user.django_user.user_permissions.add(*list(Permission.objects.filter(Q(codename__in=add_names))))
            if del_list:
                act_user.user_cap_set.filter(Q(capability__in=del_list)).delete()
                act_user.django_user.user_permissions.remove(*list(Permission.objects.filter(Q(codename__in=del_names))))
            # change secondary groups
            add_list, del_list = ([x for x in new_sgroups if x not in old_sgroups],
                                  [x for x in old_sgroups if x not in new_sgroups])
            print add_list, del_list
            if add_list:
                for sgroup in add_list:
                    act_user.django_user.groups.add(group.objects.get(Q(pk=sgroup)).django_group)
                    user_group(user=act_user,
                               group=group.objects.get(pk=sgroup)).save()
                ok_list.append(("Added %s: %s" % (logging_tools.get_plural("secondary group", len(add_list)),
                                                  ", ".join([act_ug_tree.get_group(x).groupname for x in add_list])), "sql"))
            if del_list:
                act_user.django_user.groups.remove(*[cur_group.django_group for cur_group in group.objects.filter(Q(pk__in=del_list))])
                user_group.objects.filter(Q(user=act_user) & Q(group__in=del_list)).delete()
                ok_list.append(("Deleted %s: %s" % (logging_tools.get_plural("secondary group", len(del_list)),
                                                    ", ".join([act_ug_tree.get_group(x).groupname for x in del_list])), "sql"))
            action_log.add_errors(err_list)
            action_log.add_warns(warn_list)
            action_log.add_oks(ok_list)
            if not ok_list:
                action_log.add_ok("Nothing to change", "-")
            else:
                rebuild_yp = True
            show_table = False
    elif op_mode == "mux":
        # delete user
        show_table = False
        if act_user.pk == req.session_data.user_info.pk:
            req.write(html_tools.gen_hline("Cannot delete current user", 2))
        else:
            req.write(html_tools.gen_hline("Really delete user '%s' ?" % (act_user.login), 2))
            ok_target = "mud"
            hidden_uid = html_tools.text_field(req, "ulist", size=8, display_len=8)
            hidden_uid.check_selection("", str(act_user.uid))
            hidden_list.append(hidden_uid)
    elif op_mode == "mud":
        # delete user
        show_table = False
        del_idx, del_name, del_group_idx = (act_user.pk, act_user.login, act_user.group_id)
        #del_group_name = [v.get_idx() for v in act_ug_tree.get_all_groups() if v.get_idx() == del_group_idx][0]
        action_log.add_ok("deleted user %s" % (act_user.login), "SQL")
        User.objects.filter(Q(username=act_user.login)).delete()
        act_user.delete()
        #act_ug_tree.get_group(del_group_name).del_user(del_idx)
        rebuild_yp = True
    elif op_mode == "cvu":
        # validate creation of new user
        valid = True
        new_name = name_field.check_selection("")
        rel_home_dir = rel_home_field.check_selection("") or new_name
        rel_scratch_dir = rel_scratch_field.check_selection("") or new_name
        if new_name in act_ug_tree.get_all_user_names():
            action_log.add_error("Username '%s' already used" % (new_name), "already used")
            valid = False
        titan, nname, vname, aliases = (titan_field.check_selection(""),
                                        nname_field.check_selection(""),
                                        vname_field.check_selection(""),
                                        alias_field.check_selection(""))
        tel, email, pager, comment = (tel_field.check_selection(""),
                                      email_field.check_selection(""),
                                      pag_field.check_selection(""),
                                      com_field.check_selection(""))
        pass1, pass2 = (pass1_field.check_selection(""),
                        pass2_field.check_selection(""))
        if pass1 != pass2:
            action_log.add_error("password not correctly entered", "user error")
            valid = False
        elif len(pass1) < 5:
            action_log.add_error("password not long enough (%s, must be at least 5 characters)" % (logging_tools.get_plural("character", len(pass1))), "user error")
            valid = False
        pgroup = pgroup_field.check_selection()
        sgroups = [x for x in sgroup_field.check_selection("", []) or [] if x != pgroup]
        new_shell = shell_list.check_selection("")
        is_active, ccontact, sge_user, create_quota = (act_field.check_selection(""),
                                                       ccontact_field.check_selection(""),
                                                       sge_list.check_selection("", []),
                                                       create_quota_field.check_selection(""))
        new_uid, new_uid_f = (uid_list.check_selection(),
                              uid_field.check_selection())
        if new_uid == 0:
            if not new_uid_f.isdigit():
                action_log.add_warn("Entered uid '%s' is not an integer" % (new_uid_f), "parse error")
                valid = False
            else:
                new_uid = int(new_uid_f)
        home_export = home_field.check_selection("", 0)
        scratch_export = scratch_field.check_selection("", 0)
        new_aliases = aliases and aliases.split() or []
        already_used_aliases = [x for x in new_aliases if x in used_aliases]
        if already_used_aliases:
            action_log.add_warn("%s already used: %s" % (logging_tools.get_plural("Alias", len(already_used_aliases)),
                                                         ", ".join(already_used_aliases)), "invalid aliases")
            valid = False
        already_used_aliases = [x for x in new_aliases if x in all_used_names]
        if already_used_aliases:
            action_log.add_warn("%s already used for login: %s" % (logging_tools.get_plural("Alias", len(already_used_aliases)),
                                                                   ", ".join(already_used_aliases)), "invalid aliases")
            valid = False
        if new_uid in used_uids:
            action_log.add_warn("uid is already used by user '%s'" % ([x.login for x in act_ug_tree.get_all_users() if x.uid == new_uid][0]), "invalid uid")
            valid = False
        elif new_uid in sys_user_dict.keys():
            action_log.add_warn("uid is already used by system user '%s'" % (sys_user_dict[new_uid]), "invalid uid")
            valid = False
        cap_dict = {}
        for cap_idx in act_ug_tree.cap_stack.get_all_cap_idxs():
            act_cap = act_ug_tree.cap_stack[cap_idx]
            act_val = cap_field.check_selection(act_cap.name)
            cap_dict[act_cap.name] = (act_val, act_cap.idx)
        if not valid:
            action_log.add_warn("Userdata is not valid", "please check")
            op_mode = "cu"
            act_user = user(login=new_name,
                            uid=0)
            #act_user.act_values_are_default()
        else:
            new_dict = {"uid"             : new_uid,
                        "active"          : is_active,
                        "group"           : group.objects.get(Q(pk=pgroup)),
                        "login"           : new_name,
                        "uservname"       : vname,
                        "usernname"       : nname,
                        "usertitan"       : titan,
                        "aliases"         : aliases,
                        "usertel"         : tel,
                        "useremail"       : email,
                        "userpager"       : pager,
                        "usercom"         : comment,
                        "shell"           : shell_list[new_shell]["name"],
                        "cluster_contact" : ccontact,
                        "export"          : home_export or None,
                        "export_scr"      : scratch_export or None,
                        "home"            : rel_home_dir,
                        "scratch"         : rel_scratch_dir,
                        "password"        : crypt.crypt(pass1, "".join([chr(random.randint(97, 122)) for x in range(16)]))}
            _set_samba_password(new_dict, pass1)
            act_user = user(uid=0)
            for key, value in new_dict.iteritems():
                setattr(act_user, key, value)
            if sge_user:
                for sge_u in sge_user:
                    act_user.add_sge_server(sge_u)
            # FIXME
            #act_user["sge_servers"] = [x for x in act_user["sge_servers"]]
            #act_user.act_values_are_default()
            act_user.save()
            new_du = act_user.create_django_user()
            new_du.groups.add(group.objects.get(Q(pk=pgroup)).django_group)
            new_du.set_password(pass1)
            new_du.save()
            #act_user.commit_sql_changes(req.dc, 1, 1, 0)
            for sgroup in sgroups:
                new_du.groups.add(group.objects.get(Q(pk=sgroup)).django_group)
                user_group(user=act_user,
                           group=group.objects.get(pk=sgroup)).save()
            #err_list, warn_list, ok_list = act_user.build_change_lists("set ", " for new_user %s" % (new_name), 0, 0, 1)
            add_list, del_list, ok_list, del_names, add_names = ([], [], [], [], [])
            for cap_name, (set_cap, idx) in cap_dict.iteritems():
                #print cap_name, set_cap, act_group.has_capability(cap_name)
                if set_cap and not act_user.capability_ok(cap_name):
                    add_names.append("wf_%s" % (cap_name))
                    add_list.append(idx)
                    ok_list.append(("Added capability %s" % (cap_name), "sql"))
                elif not set_cap and act_user.capability_ok(cap_name, only_user=True):
                    del_names.append("wf_%s" % (cap_name))
                    del_list.append(idx)
                    ok_list.append(("Deleted capability %s" % (cap_name), "sql"))
            if add_list:
                for cap_add in add_list:
                    user_cap(capability=capability.objects.get(pk=cap_add),
                              user=act_user).save()
                act_user.django_user.user_permissions.add(*list(Permission.objects.filter(Q(codename__in=add_names))))
            if del_list:
                act_user.user_cap_set.filter(Q(capability__in=del_list)).delete()
                act_user.django_user.user_permissions.remove(*list(Permission.objects.filter(Q(codename__in=del_names))))
            action_log.add_oks(ok_list)
            if home_export:
                com_list.append(tools.s_command(req, "server", 8004, "create_user_home", [], 20, home_lut[home_export], {"username" : new_name}))
            if scratch_export:
                com_list.append(tools.s_command(req, "server", 8004, "create_user_scratch", [], 20, scratch_lut[scratch_export], {"username" : new_name}))
            if sge_user:
                for sge_u in sge_user:
                    com_list.append(tools.s_command(req, sge_lut[sge_u]["config"], 8004, "create_sge_user", [], 20, None, {"username" : new_name}))
                    #req.dc.execute("INSERT INTO sge_user_con SET sge_config=%d, user=%d" % (sge_u, act_user.get_idx()))
            if create_quota:
                post_com_list.append(tools.s_command(req, "server", 8004, "create_user_quota", [], 20, home_lut[home_export], {"username" : new_name}))
            show_table, rebuild_yp = (False, True)
    if show_table:
        # build table
        u_table = html_tools.html_table(cls = "user")
        u_table[0]["class"] = "line10"
        if op_mode == "mub":
            u_table[None][0:4] = html_tools.content("Basic user information", cls="center", type="th")
            u_table[0][0]    = html_tools.content("Loginname:", cls="right")
            u_table[None][0] = html_tools.content(act_user.login, cls="left")
            u_table[None][0] = html_tools.content("User ID:", cls="right")
            u_table[None][0] = html_tools.content(act_user.uid, cls="left")
            pgroup_struct = [v for v in act_ug_tree.get_all_groups() if v.pk == act_user.group_id][0]
            sgroup_list   = [(v.get_idx(), v["gid"]) for v in act_ug_tree.get_all_groups() if v.get_idx() in act_user.get_secondary_group_idxs()]
            u_table[0][0]    = html_tools.content("Primary Group:", cls="right")
            u_table[None][0] = html_tools.content("%s [gid=%s]" % (pgroup_struct.groupname, pgroup_struct["gid"]), cls="left")
            u_table[None][0] = html_tools.content("%s :" % (logging_tools.get_plural("Secondary group", len(sgroup_list))), cls="right")
            u_table[None][0] = html_tools.content(", ".join(["%s [gid=%d]" % (x, y) for x, y in sgroup_list]) or "---", cls="left")
            u_table[0][0]    = html_tools.content("Shell:", cls="right")
            u_table[None][0] = html_tools.content(act_user.shell, cls="left")
            u_table[None][0] = html_tools.content("Active:", cls="right")
            u_table[None][0] = html_tools.content(act_user.active and "yes" or "no", cls="left")
            u_table[0][0]    = html_tools.content("Cluster contact:", cls="right")
            u_table[None][0] = html_tools.content(act_user["cluster_contact"] and "yes" or "no", cls="left")
            u_table[None][0] = html_tools.content("SGE user:", cls="right")
            act_sge_servers = act_user.get_sge_servers()
            u_table[None][0] = html_tools.content(act_sge_servers and ", ".join(["on %s" % (sge_lut[x]["device"]) for x in act_sge_servers]) or "no", cls="left")
            u_table[0][0]    = html_tools.content("Aliases:", cls="right")
            if act_user.aliases:
                alias_str = act_user.aliases
            else:
                alias_str = "None set"
            u_table[None][0:3] = html_tools.content(alias_str, cls="left")
            u_table[0]["class"] = "line10"
            u_table[None][0:4] = html_tools.content("Additional information", cls="center", type="th")
            u_table[0][0]    = html_tools.content("Name:", cls="right")
            pers_info = (" ".join([act_user["usertitan"], act_user["uservname"], act_user["usernname"]])).strip()
            u_table[None][0:3] = html_tools.content(pers_info or "---", cls="left")
            u_table[0][0]    = html_tools.content("Tel. number:", cls="right")
            u_table[None][0] = html_tools.content(act_user["usertel"] or "---", cls="left")
            u_table[None][0] = html_tools.content("Email address:", cls="right")
            u_table[None][0] = html_tools.content(act_user["useremail"] or "---", cls="left")
            u_table[0][0]    = html_tools.content("User comment:", cls="right")
            u_table[None][0] = html_tools.content(act_user["usercom"] or "---", cls="left")
            u_table[None][0] = html_tools.content("Pager address:", cls="right")
            u_table[None][0] = html_tools.content(act_user["userpager"] or "---", cls="left")
            # only show capabilities of user
            cap_headline, c_table = cdef_user.show_capability_info(req, act_ug_tree, pgroup_struct, act_user, None)
        else:
            u_table[None][0:2] = html_tools.content("Basic user information", cls="center", type="th")
            u_table[0][0]      = html_tools.content("Loginname:", cls="right")
            u_table[None][0]   = html_tools.content(name_field, cls="left")
            u_table[0][0]      = html_tools.content("User ID:", cls="right")
            u_table[None][0]   = html_tools.content([uid_list, " %d <= " % (min_uid), uid_field, " <= %d" % (max_uid), ", free uids: %s" % (free_uids_str)], cls="left")
            if not op_mode.startswith("mu"):
                pgroup_struct = [v for v in act_ug_tree.get_all_groups() if v.pk == prefered_pgroup][0]
                if num_homes:
                    u_table[0][0]    = html_tools.content("Create homedir in:", cls="right")
                    u_table[None][0] = html_tools.content(home_field, cls="left")
                if num_scratches:
                    u_table[0][0]    = html_tools.content("Create scratchdir in:", cls="right")
                    u_table[None][0] = html_tools.content(scratch_field, cls="left")
            else:
                pgroup_struct = [v for v in act_ug_tree.get_all_groups() if v.pk == act_user.group_id][0]
            u_table[0][0]      = html_tools.content("Primary group:", cls="right")
            u_table[None][0]   = html_tools.content(pgroup_field, cls="left")
            u_table[0][0]      = html_tools.content("Secondary group(s):", cls="right")
            u_table[None][0]   = html_tools.content(sgroup_field, cls="left")

            u_table[0][0]      = html_tools.content("Home directory:", cls="right")
            u_table[None][0]   = html_tools.content(rel_home_field, cls="left")
            u_table[0][0]      = html_tools.content("Scratch directory:", cls="right")
            u_table[None][0]   = html_tools.content(rel_scratch_field, cls="left")
            
            u_table[0][0]      = html_tools.content("Shell:", cls="right")
            u_table[None][0]   = html_tools.content(shell_list, cls="left")
            u_table[0][0]      = html_tools.content("Password:", cls="right")
            if new_pwd:
                u_table[None][0]   = html_tools.content([pass1_field, " (is now %s)" % (new_pwd)], cls="left")
            else:
                u_table[None][0]   = html_tools.content(pass1_field, cls="left")
            u_table[0][0]      = html_tools.content("Check password:", cls="right")
            u_table[None][0]   = html_tools.content(pass2_field, cls="left")
            # alias settings
            u_table[0][0]      = html_tools.content("Aliases:", cls="right")
            u_table[None][0]   = html_tools.content(alias_field, cls="left")
            u_table[0][0]      = html_tools.content("Active:", cls="right")
            u_table[None][0]   = html_tools.content(act_field, cls="left")
            u_table[0][0]      = html_tools.content("Clustercontact:", cls="right")
            u_table[None][0]   = html_tools.content(ccontact_field, cls="left")
            if sge_list:
                u_table[0][0]      = html_tools.content("Create SGE-user:", cls="right")
                u_table[None][0]   = html_tools.content(sge_list, cls="left")
            if udl_list:
                u_table[0][0]      = html_tools.content("Allow login (if none set allow all):", cls="right")
                u_table[None][0]   = html_tools.content(udl_list, cls="left")
            if any_quota_ok and not op_mode.startswith("mu"):
                u_table[0][0]    = html_tools.content("Create Quota entries:", cls="right")
                u_table[None][0] = html_tools.content(create_quota_field, cls="left")
            u_table[0]["class"] = "line10"
            u_table[None][0:2] = html_tools.content("Additional information", cls="center", type="th")
            u_table[0][0]      = html_tools.content("Name:", cls="right")
            u_table[None][0]   = html_tools.content([titan_field, " ", vname_field, " ", nname_field], cls="left")
            u_table[0][0]      = html_tools.content("Tel. number:", cls="right")
            u_table[None][0]   = html_tools.content(tel_field, cls="left")
            u_table[0][0]      = html_tools.content("Email address:", cls="right")
            u_table[None][0]   = html_tools.content(email_field, cls="left")
            u_table[0][0]      = html_tools.content("Pager address:", cls="right")
            u_table[None][0]   = html_tools.content(pag_field, cls="left")
            u_table[0][0]      = html_tools.content("User comment:", cls="right")
            u_table[None][0]   = html_tools.content(com_field, cls="left")
            # modify capabilities of existing user
            cap_headline, c_table = cdef_user.show_capability_info(req, act_ug_tree, pgroup_struct, act_user, cap_field)

        req.write(html_tools.gen_hline({"cu"  : "Please set the general properties of the new user:",
                                        "cvu" : "Some values are incorrect for the new user",
                                        "mub" : "Information about the user '%s'" % (act_user.login),
                                        "mum" : "Edit the general properties of user '%s'" % (act_user.login),
                                        "muv" : "Some values are incorrect for user '%s'" % (act_user.login)}.get(op_mode, "Invalid operation_mode %s" % (op_mode)), 2))
        submit_button = html_tools.submit_button(req, {"cu"  : "validate and create",
                                                       "mub" : "ok",
                                                       "mum" : "validate and change"}.get(op_mode, "unknown mode %s" % (op_mode)))
        req.write("<form action=\"%s.py?%s&opmode=%s\" method=post>%s%s%s%s" % (req.module_name,
                                                                                functions.get_sid(req),
                                                                                {"cu"  : "cvu",
                                                                                 "mub" : "mp",
                                                                                 "mum" : "muv"}.get(op_mode, "cu"),
                                                                                "\n".join([x.create_hidden_var() for x in hidden_list]),
                                                                                u_table(""),
                                                                                html_tools.gen_hline(cap_headline, 2),
                                                                                c_table and c_table("") or ""))
    else:
        submit_button = html_tools.submit_button(req, "ok")
        req.write("<form action=\"%s.py?%s%s\" method=post>%s" % (req.module_name,
                                                                  functions.get_sid(req),
                                                                  ok_target and "&opmode=%s" % (ok_target) or "",
                                                                  "\n".join([x.create_hidden_var() for x in hidden_list])))
    if rebuild_yp:
        tools.signal_yp_ldap_server(req, action_log)
    com_list.extend(post_com_list)
    if com_list:
        for com in com_list:
            tools.iterate_s_commands([com], action_log)
            if com.server_reply:
                pass
    return submit_button
        
def generate_group_mask(req, act_ug_tree, action_log, op_mode, act_group = None):
    line_idx = 0
    # init fields
    name_field    = html_tools.text_field(req, "gname", size=15, display_len=15)
    home_field    = html_tools.text_field(req, "hstart", size=255, display_len=32)
    scratch_field = html_tools.text_field(req, "sstart", size=255, display_len=32)
    vname_field   = html_tools.text_field(req, "vname", size=255, display_len=32)
    nname_field   = html_tools.text_field(req, "nname", size=255, display_len=32)
    titan_field   = html_tools.text_field(req, "titan", size=255, display_len=5)
    email_field   = html_tools.text_field(req, "email", size=255, display_len=32)
    tel_field     = html_tools.text_field(req, "tel", size=255, display_len=32)
    gcom_field    = html_tools.text_field(req, "gcom", size=255, display_len=48)
    com_field     = html_tools.text_field(req, "com", size=255, display_len=48)
    act_field     = html_tools.checkbox(req, "active")
    cap_field     = html_tools.checkbox(req, "caps")
    gid_list      = html_tools.selection_list(req, "gidl", {0 : "enter number:"}, sort_new_keys=False)
    gid_field     = html_tools.text_field(req, "gidn", size=8, display_len=8)
    gids_written, min_gid, max_gid = (0, 100, 65000)
    if act_group:
        used_gids = [x.gid for x in act_ug_tree.get_all_groups() if act_group and not x == act_group]
        act_gid = max(min_gid, act_group.gid - 10)
    else:
        used_gids = [act_ug_tree.get_group(g_name).gid for g_name in act_ug_tree.get_all_group_names()]
        if used_gids:
            act_gid = max(min_gid, min(used_gids) - 10)
        else:
            act_gid = min_gid
    last_gid_written, mark_idx = (0, 0)
    sys_group_dict = get_system_group_ids()
    free_gids_str = logging_tools.compress_num_list([x for x in xrange(min_gid, max_gid + 1) if x not in sys_group_dict.keys() and x not in used_gids])
    while gids_written < 20:
        if act_gid in used_gids or act_gid in sys_group_dict.keys():
            act_gid += 1
        else:
            if not gids_written and op_mode == "cg":
                gid_field.check_selection("", act_gid)
            gids_written += 1
            if last_gid_written and act_gid != last_gid_written + 1:
                mark_idx -= 1
                gid_list[mark_idx] = {"name"     : "------ %s used ------" % (logging_tools.get_plural("gid", act_gid - last_gid_written - 1)),
                                      "disabled" : 1}
            gid_list[act_gid] = "%d" % (act_gid)
            act_gid += 1
    # hidden vars
    hidden_list = []
    # flags: show_table, create_group
    show_table, create_group, rebuild_yp, ok_target = (True, 0, 0, "")
    if op_mode == "cg":
        # creation of new group
        name_field.check_selection("", "newgroup")
        home_field.check_selection("", "/home")
        scratch_field.check_selection("", "/p_scratch")
        titan_field.check_selection("", "title")
        vname_field.check_selection("", "first name")
        nname_field.check_selection("", "last name")
        tel_field.check_selection("", "+43 1 ")
        email_field.check_selection("", "")
        gcom_field.check_selection("", "Comment for the new group")
        com_field.check_selection("", "Responsible person for the new group")
        act_field.check_selection("", 1)
        gid_list.check_selection("", 0)
        act_group = group(
            gid=0,
            groupname="newgroup")
        #act_group.act_values_are_default()
        cap_dict = {}
        for cap_idx in act_ug_tree.cap_stack.get_all_cap_idxs():
            act_cap = act_ug_tree.cap_stack[cap_idx]
            act_val = cap_field.check_selection(act_cap.name, act_cap.defvalue)
            cap_dict[act_cap.name] = (act_val, act_cap.idx)
    elif op_mode == "mgm":
        # modify existing group
        name_field.check_selection("", act_group.groupname)
        home_field.check_selection("", act_group.homestart)
        scratch_field.check_selection("", act_group.scratchstart)
        titan_field.check_selection("", act_group.resptitan)
        vname_field.check_selection("", act_group.respvname)
        nname_field.check_selection("", act_group.respnname)
        tel_field.check_selection("", act_group.resptel)
        email_field.check_selection("", act_group.respemail)
        gcom_field.check_selection("", act_group.groupcom)
        com_field.check_selection("", act_group.respcom)
        act_field.check_selection("", act_group.active)
        gid_list.check_selection("", act_group.gid)
        gid_field.check_selection("", str(act_group.gid))
        hidden_gid = html_tools.text_field(req, "glist", size=8, display_len=8)
        hidden_gid.check_selection("", str(act_group.gid))
        hidden_list.append(hidden_gid)
        cap_dict = {}
        for cap_idx in act_ug_tree.cap_stack.get_all_cap_idxs():
            act_cap = act_ug_tree.cap_stack[cap_idx]
            act_val = cap_field.check_selection(act_cap.name, act_group.has_capability(act_cap.name))
            cap_dict[act_cap.name] = (act_val, act_cap.idx)
    elif op_mode == "mgv":
        # validate modification of existing group
        valid = True
        new_name = name_field.check_selection("")
        if new_name in act_ug_tree.get_all_group_names() and new_name != act_group.groupname:
            action_log.add_error("Groupname '%s' already used" % (new_name), "already used")
            valid = False
        home_start = home_field.check_selection("")
        if not cdef_user.validate_start_path(home_start, "home", action_log):
            valid = False
        scratch_start = scratch_field.check_selection("")
        if not cdef_user.validate_start_path(scratch_start, "scratch", action_log):
            valid = False
        titan, nname, vname = (titan_field.check_selection(""),
                               nname_field.check_selection(""),
                               vname_field.check_selection(""))
        tel, email, comment = (tel_field.check_selection(""),
                               email_field.check_selection(""),
                               com_field.check_selection(""))
        g_comment = gcom_field.check_selection("")
        is_active = act_field.check_selection("")
        if not is_active and act_group.pk == req.session_data.user_info.group_id:
            action_log.add_warn("Cannot disable my own group", "error")
            valid = False
        new_gid, new_gid_f = (gid_list.check_selection(),
                              gid_field.check_selection())
        if new_gid == 0:
            if not new_gid_f.isdigit():
                action_log.add_warn("Entered gid is not an integer", "parse error")
                valid = False
            else:
                new_gid = int(new_gid_f)
        cap_dict = {}
        for cap_idx in act_ug_tree.cap_stack.get_all_cap_idxs():
            act_cap = act_ug_tree.cap_stack[cap_idx]
            act_val = cap_field.check_selection(act_cap.name)
            cap_dict[act_cap.name] = (act_val, act_cap.idx)
        if not valid:
            action_log.add_warn("Groupdata is not valid", "please check")
            op_mode = "mgm"
            hidden_gid = html_tools.text_field(req, "glist", size=8, display_len=8)
            hidden_gid.check_selection("", str(act_group.gid))
            hidden_list.append(hidden_gid)
        else:
            mod_dict = {"gid"          : new_gid,
                        "active"       : is_active,
                        "ggroupname"   : new_name,
                        "homestart"    : home_start,
                        "scratchstart" : scratch_start,
                        "respvname"    : vname,
                        "respnname"    : nname,
                        "resptitan"    : titan,
                        "resptel"      : tel,
                        "respemail"    : email,
                        "respcom"      : comment,
                        "groupcom"     : g_comment}
            for key, value in mod_dict.iteritems():
                setattr(act_group, key, value)
            act_group.save()
##            act_group.update(mod_dict)
##            act_group.commit_sql_changes(req.dc, 1, 0, 0)
##            err_list, warn_list, ok_list = act_group.build_change_lists("altered ", " for group %s" % (act_group.groupname), 1, 0, 1)
            add_list, del_list, ok_list, del_names, add_names = ([], [], [], [], [])
            for cap_name, (c_set, idx) in cap_dict.iteritems():
                #print cap_name, set, act_group.has_capability(cap_name)
                if c_set and not act_group.has_capability(cap_name):
                    add_names.append("wf_%s" % (cap_name))
                    add_list.append(idx)
                    ok_list.append(("Added capability %s" % (cap_name), "sql"))
                elif not c_set and act_group.has_capability(cap_name):
                    del_names.append("wf_%s" % (cap_name))
                    del_list.append(idx)
                    ok_list.append(("Deleted capability %s" % (cap_name), "sql"))
            if add_list:
                for cap_add in add_list:
                    group_cap(capability=capability.objects.get(pk=cap_add),
                              group=act_group).save()
                act_group.django_group.permissions.add(*list(Permission.objects.filter(Q(codename__in=add_names))))
            if del_list:
                act_group.group_cap_set.filter(Q(capability__in=del_list)).delete()
                act_group.django_group.permissions.remove(*list(Permission.objects.filter(Q(codename__in=del_names))))
##            action_log.add_errors(err_list)
##            action_log.add_warns(warn_list)
            action_log.add_oks(ok_list)
            if not ok_list:
                action_log.add_ok("Nothing to change", "-")
            else:
                rebuild_yp = True
            show_table = False
    elif op_mode == "mgb":
        # browse group
        pass
    elif op_mode == "mgx":
        # delete group
        del_it = True
        show_table = False
        if act_group.get_num_users():
            action_log.add_error("cannot delete group %s" % (act_group.groupname), "%s defined" % (logging_tools.get_plural("user", act_group.get_num_users())))
            del_it = False
        if del_it:
            req.write(html_tools.gen_hline("Really delete group '%s' ?" % (act_group.groupname), 2))
            ok_target = "mgd"
        hidden_gid = html_tools.text_field(req, "glist", size=8, display_len=8)
        hidden_gid.check_selection("", str(act_group.gid))
        hidden_list.append(hidden_gid)
    elif op_mode == "mgd":
        show_table = False
        action_log.add_ok("deleted group %s" % (act_group.groupname), "SQL")
        act_group.django_group.delete()
        act_group.delete()
        #act_ug_tree.del_group(act_group.groupname)
    elif op_mode == "cvg":
        # validate creation of new group
        valid = True
        new_name = name_field.check_selection("")
        if new_name in act_ug_tree.get_all_group_names():
            action_log.add_error("Groupname '%s' already used" % (new_name), "already used")
            valid = False
        home_start = home_field.check_selection("")
        if not cdef_user.validate_start_path(home_start, "home", action_log):
            valid = False
        scratch_start = scratch_field.check_selection("")
        if not cdef_user.validate_start_path(scratch_start, "scratch", action_log):
            valid = False
        titan, nname, vname = (titan_field.check_selection(""),
                               nname_field.check_selection(""),
                               vname_field.check_selection(""))
        tel, email, comment = (tel_field.check_selection(""),
                               email_field.check_selection(""),
                               com_field.check_selection(""))
        g_comment = gcom_field.check_selection("")
        is_active = act_field.check_selection("")
        new_gid, new_gid_f = (gid_list.check_selection(),
                              gid_field.check_selection())
        if new_gid == 0:
            if not new_gid_f.isdigit():
                action_log.add_warn("Entered gid '%s' is not an integer" % (new_gid_f), "parse error")
                valid = False
            else:
                new_gid = int(new_gid_f)
        if new_gid in used_gids:
            action_log.add_warn("gid is already used by group '%s'" % (group.objects.get(Q(gid=new_gid)).groupname),
                                "invalid gid")
            valid = False
        elif new_gid in sys_group_dict.keys():
            action_log.add_warn("gid is already used by system group '%s'" % (sys_group_dict[new_gid]), "invalid gid")
            valid = False
        cap_dict = {}
        for cap_idx in act_ug_tree.cap_stack.get_all_cap_idxs():
            act_cap = act_ug_tree.cap_stack[cap_idx]
            act_val = cap_field.check_selection(act_cap.name, act_cap.defvalue)
            cap_dict[act_cap.name] = (act_val, act_cap.idx)
        #valid = False
        if not valid:
            action_log.add_warn("Groupdata is not valid", "please check")
            op_mode = "cg"
            act_group = group(groupname=new_name,
                              gid=0)
            #act_group.act_values_are_default()
        else:
            new_dict = {"gid"          : new_gid,
                        "active"       : is_active,
                        "ggroupname"   : new_name,
                        "homestart"    : home_start,
                        "scratchstart" : scratch_start,
                        "respvname"    : vname,
                        "respnname"    : nname,
                        "resptitan"    : titan,
                        "resptel"      : tel,
                        "respemail"    : email,
                        "respcom"      : comment,
                        "groupcom"     : g_comment}
            act_group = group(groupname=new_name,
                              gid=0)
            for key, value in new_dict.iteritems():
                setattr(act_group, key, value)
            #act_group.act_values_are_default()
            act_group.save()
            # new django group
            new_dg = act_group.create_django_group()
            # capabilities
            if any([x for x in cap_dict.values() if x[0]]):
                caps_to_set = capability.objects.filter(Q(pk__in=[cap_id for use_it, cap_id in cap_dict.values() if use_it]))
                for cap_to_set in caps_to_set:
                    group_cap(group=act_group,
                              capability=cap_to_set).save()
                new_dg.permissions.add(*list(Permission.objects.filter(Q(codename__in=["wf_%s" % (cur_cap.name) for cur_cap in caps_to_set]))))
##                act_group.django_group.permissions
##                req.dc.execute("INSERT INTO ggroupcap VALUES%s" % (",".join(["(0, %d, %d, null)" % (act_group.get_idx(), x[1]) for x in cap_dict.values() if x[0]])))
##            err_list, warn_list, ok_list = act_group.build_change_lists("set ", " for new_group %s" % (new_name), 0, 0, 1)
##            action_log.add_errors(err_list)
##            action_log.add_warns(warn_list)
##            action_log.add_oks(ok_list)
            show_table, rebuild_yp = (False, True)
    if rebuild_yp:
        tools.signal_yp_ldap_server(req, action_log)
    if show_table:
        # build table
        g_table = html_tools.html_table(cls = "user")
        g_table[0]["class"] = "line10"
        if op_mode == "mgb":
            g_table[None][0:4] = html_tools.content("Basic group information", cls="center")
            g_table[0][0]    = html_tools.content("Groupname:", cls="right")
            g_table[None][0] = html_tools.content(act_group.groupname, cls="left")
            g_table[None][0] = html_tools.content("Group ID:", cls="right")
            g_table[None][0] = html_tools.content(act_group["gid"], cls="left")
            g_table[0][0]    = html_tools.content("Homestart:", cls="right")
            g_table[None][0] = html_tools.content(act_group["homestart"], cls="left")
            g_table[None][0] = html_tools.content("Scratchstart:", cls="right")
            g_table[None][0] = html_tools.content(act_group["scratchstart"], cls="left")
            g_table[0][0]    = html_tools.content("Active:", cls="right")
            g_table[None][0:3] = html_tools.content(act_group.active and "yes" or "no", cls="left")
            g_table[0][0]    = html_tools.content("Group comment:", cls="right")
            g_table[None][0:3] = html_tools.content(act_group["groupcom"] or "---", cls="left")
            g_table[0]["class"] = "line10"
            g_table[None][0:4]  = html_tools.content("Responsible person and comment", cls="center")
            g_table[0][0]    = html_tools.content("Name:", cls="right")
            resp_pers = (" ".join([act_group["resptitan"], act_group["respvname"], act_group["respnname"]])).strip()
            g_table[None][0:3] = html_tools.content(resp_pers or "---", cls="left")
            g_table[0][0]    = html_tools.content("Tel. number:", cls="right")
            g_table[None][0] = html_tools.content(act_group["resptel"] or "---", cls="left")
            g_table[None][0] = html_tools.content("Email address:", cls="right")
            g_table[None][0] = html_tools.content(act_group["respemail"] or "---", cls="left")
            g_table[0][0]    = html_tools.content("Comment:", cls="right")
            g_table[None][0:3] = html_tools.content(act_group["respcom"] or "---", cls="left")
            # just show capabilities
            cap_headline, c_table = cdef_user.show_capability_info(req, act_ug_tree, act_group, None, None)
        else:
            g_table[None][0:2] = html_tools.content("Basic group information", cls="center")
            g_table[0][0]    = html_tools.content("Groupname:", cls="right")
            g_table[None][0] = html_tools.content(name_field, cls="left")
            g_table[0][0]    = html_tools.content("Group ID:", cls="right")
            g_table[None][0] = html_tools.content([gid_list, " %d <= " % (min_gid), gid_field, " <= %d" % (max_gid), ", free gids: %s" % (free_gids_str)], cls="left")
            g_table[0][0]    = html_tools.content("Homestart:", cls="right")
            g_table[None][0] = html_tools.content(home_field, cls="left")
            g_table[0][0]    = html_tools.content("Scratchstart:", cls="right")
            g_table[None][0] = html_tools.content(scratch_field, cls="left")
            g_table[0][0]    = html_tools.content("Active:", cls="right")
            g_table[None][0] = html_tools.content(act_field, cls="left")
            g_table[0][0]    = html_tools.content("Group comment:", cls="right")
            g_table[None][0] = html_tools.content(gcom_field, cls="left")
            g_table[0]["class"] = "line10"
            g_table[None][0:2] = html_tools.content("Responsible person and comment", cls="center")
            g_table[0][0]    = html_tools.content("Name:", cls="right")
            g_table[None][0] = html_tools.content([titan_field, " ", vname_field, " ", nname_field], cls="left")
            g_table[0][0]    = html_tools.content("Tel. number:", cls="right")
            g_table[None][0] = html_tools.content(tel_field, cls="left")
            g_table[0][0]    = html_tools.content("Email address:", cls="right")
            g_table[None][0] = html_tools.content(email_field, cls="left")
            g_table[0][0]    = html_tools.content("Comment:", cls="right")
            g_table[None][0] = html_tools.content(com_field, cls="left")
            # modify capabilities
            cap_headline, c_table = cdef_user.show_capability_info(req, act_ug_tree, act_group, None, cap_field)
        req.write(html_tools.gen_hline({"cg"  : "Please set the general properties of the new group:",
                                        "cvg" : "Some values are incorrect for the new group",
                                        "mgb" : "Information about the group '%s'" % (act_group.groupname),
                                        "mgm" : "Edit the general properties of group '%s'" % (act_group.groupname),
                                        "mgv" : "Some values are incorrect for group '%s'" % (act_group.groupname)}.get(op_mode, "Invalid operation_mode %s" % (op_mode)), 2))
        submit_button = html_tools.submit_button(req, {"cg"  : "validate and create",
                                                       "mgb" : "ok",
                                                       "mgm" : "validate and change"}.get(op_mode, "unknown mode %s" % (op_mode)))
        
        req.write("<form action=\"%s.py?%s&opmode=%s\" method=post>%s%s%s%s" % (req.module_name,
                                                                                functions.get_sid(req),
                                                                                {"cg" : "cvg",
                                                                                 "mgb" : "mp",
                                                                                 "mgm" : "mgv"}.get(op_mode, "cg"),
                                                                                "\n".join([x.create_hidden_var() for x in hidden_list]),
                                                                                g_table(""),
                                                                                html_tools.gen_hline(cap_headline, 2),
                                                                                c_table and c_table("") or ""))
        
    else:
        submit_button = html_tools.submit_button(req, "ok")
        req.write("<form action=\"%s.py?%s%s\" method=post>%s" % (req.module_name,
                                                                  functions.get_sid(req),
                                                                  ok_target and "&opmode=%s" % (ok_target) or "",
                                                                  "\n".join([x.create_hidden_var() for x in hidden_list])))
    return submit_button

def show_user_group_selection(req, act_ug_tree, group_options, user_options):
    # build tables for group/user options
    draw_group = req.user_info.capability_ok("mg") or req.user_info.capability_ok("bg")
    draw_user  = req.user_info.capability_ok("mu") or req.user_info.capability_ok("bu")
    #print req.sys_args
    if draw_group or draw_user:
        selgroup_button = html_tools.submit_button(req, "select")
        seluser_button  = html_tools.submit_button(req, "select")
        sel_table = html_tools.html_table(cls="blind")
        sel_table[0]["class"] = "blind"
        if draw_group:
            group_table = html_tools.html_table(cls="user")
            if req.user_info.capability_ok("mg"):
                group_table[0][0] = html_tools.content("<a href=\"%s.py?%s&opmode=cg\">Create Group</a>" % (req.module_name, functions.get_sid(req)), cls="right")
                group_table[None][0] = html_tools.content("Create a new group", cls="left")
            if req.user_info.capability_ok("bg"):
                group_table[0][0] = html_tools.content("<a href=\"%s.py?%s&opmode=bg\">Browse Group</a>" % (req.module_name, functions.get_sid(req)), cls="right")
                group_table[None][0] = html_tools.content("Browse all groups (%s found)" % (logging_tools.get_plural("group", act_ug_tree.get_num_groups())), cls="left")
            if req.user_info.capability_ok("mg"):
                group_list = html_tools.selection_list(req, "glist", {}, sort_new_keys=False)
                g_names = act_ug_tree.get_all_group_names()
                first_c, c_idx, first_idx = (None, -1, 0)
                for g_name in g_names:
                    if g_name[0] != first_c:
                        first_c = g_name[0]
                        group_list[c_idx] = {"name"     : " --- %s (%s) ---" % (first_c,
                                                                                logging_tools.get_plural("group", len([1 for x in g_names if x.startswith(first_c)]))),
                                             "disabled" : 1}
                        c_idx -= 1
                    g_stuff = act_ug_tree.get_group(g_name)
                    group_list[g_stuff.pk] = "%s%s (%d), %s defined" % ("" if g_stuff.active else "(*) ",
                                                                        g_name,
                                                                        g_stuff.gid,
                                                                        logging_tools.get_plural("user", g_stuff.get_num_users()))
                    if not first_idx:
                        first_idx = g_stuff.pk
                group_list.check_selection("", first_idx)
                group_table[0]["class"] = "line10"
                group_table[None][0:2] = html_tools.content([group_options, group_list], cls="center")
                group_table[0][0:2] = html_tools.content(selgroup_button, cls="center")
            sel_table[None][0] = html_tools.content(["<form action=\"%s.py?%s&opmode=mg\" method=post>" % (req.module_name, functions.get_sid(req)), group_table, "</form>"], cls="center")
        if draw_user:
            user_table = html_tools.html_table(cls="user")
            if req.user_info.capability_ok("mu"):
                user_table[0][0] = html_tools.content("<a href=\"%s.py?%s&opmode=cu\">Create User</a>" % (req.module_name, functions.get_sid(req)), cls="right")
                user_table[None][0] = html_tools.content("Create a new user", cls="left")
            if req.user_info.capability_ok("bu"):
                user_table[0][0] = html_tools.content("<a href=\"%s.py?%s&opmode=bu\">Browse User</a>" % (req.module_name, functions.get_sid(req)), cls="right")
                user_table[None][0] = html_tools.content("Browse all users (%s found)" % (logging_tools.get_plural("user", act_ug_tree.get_num_users())), cls="left")
            if req.user_info.capability_ok("mu"):
                user_list = html_tools.selection_list(req, "ulist", {}, sort_new_keys=False)
                u_names = act_ug_tree.get_all_user_names()
                first_c, c_idx, first_idx = (None, -1, 0)
                for u_name in u_names:
                    if u_name[0] != first_c:
                        first_c = u_name[0]
                        user_list[c_idx] = {"name"     : " --- %s (%s) ---" % (first_c,
                                                                               logging_tools.get_plural("user", len([1 for x in u_names if x.startswith(first_c)]))),
                                            "disabled" : 1}
                        c_idx -= 1
                    u_stuff = act_ug_tree.get_user(u_name)
                    g_stuff = act_ug_tree.get_group(u_stuff.group_id)
                    sec_groups = u_stuff.get_secondary_groups()
                    if sec_groups:
                        sec_groups = [(act_ug_tree.get_group(u.pk).groupname,
                                       act_ug_tree.get_group(u.pk).gid) for u in sec_groups if act_ug_tree.group_exists(u.pk)]
                    user_list[u_stuff.pk] = "%s (%d), pgroup %s (%d)%s" % (u_name,
                                                                           u_stuff.uid,
                                                                           g_stuff.groupname,
                                                                           g_stuff.gid,
                                                                           sec_groups and ", %s : %s" % (logging_tools.get_plural("secondary group", len(sec_groups)),
                                                                                                                ", ".join(["%s (%d)" % (gn, num) for gn, num in sec_groups])) or "")
                    if not first_idx:
                        first_idx = u_stuff.pk
                user_list.check_selection("", first_idx)
                user_table[0]["class"] = "line10"
                user_table[None][0:2] = html_tools.content([user_options, user_list], cls="center")
                user_table[0][0:2] = html_tools.content(seluser_button, cls="center")
            sel_table[None][0] = html_tools.content(["<form action=\"%s.py?%s&opmode=mu\" method=post>" % (req.module_name, functions.get_sid(req)), user_table, "</form>"], cls="center")
        req.write(html_tools.gen_hline("Options for %s / %s :" % (logging_tools.get_plural("group", len(act_ug_tree.get_all_group_names())),
                                                                  logging_tools.get_plural("user", sum([act_ug_tree.get_group(gn).get_num_users() for gn in act_ug_tree.get_all_group_names()]))), 2))
        req.write(sel_table(""))

def process_page(req):
    if req.conf["genstuff"].has_key("AUTO_RELOAD"):
        del req.conf["genstuff"]["AUTO_RELOAD"]
    functions.write_header(req)
    functions.write_body(req)
    action_log = html_tools.message_log()
    act_ug_tree = cdef_user.user_group_tree(req)
    opt_list = [("b", "Show"  ),
                ("m", "Edit"  ),
                ("x", "Delete")]
    group_options = html_tools.selection_list(req, "gopt", auto_reset=True)
    user_options = html_tools.selection_list(req, "uopt", auto_reset=True)
    for short, long_opt in opt_list:
        group_options[short] = long_opt
        user_options[short] = long_opt
    group_opts = group_options.check_selection("", "b")
    user_opts = user_options.check_selection("", "b")

    act_op_mode = req.sys_args.get("opmode", "")
    if act_op_mode in ["cg", "cvg", "mg", "mgv", "mgd"]:
        # mode description:
        # cg .... create group, initial call
        # cvg ... validatge new group (after initial call)
        # mg .... modify group, initial call
        # mgv ... validate modify group
        # mgd ... delete group
        if act_op_mode.startswith("mg"):
            if act_op_mode == "mg":
                act_op_mode = "mg%s" % (group_opts)
            act_group = act_ug_tree.get_group(int(req.sys_args["glist"]))
        else:
            act_group = None
        s_button = generate_group_mask(req, act_ug_tree, action_log, act_op_mode, act_group)
    elif act_op_mode in ["bg", "bgx", "bgx2"]:
        s_button = generate_group_masks(req, act_ug_tree, action_log, act_op_mode)
    elif act_op_mode in ["cu", "cvu", "mu", "muv", "mud"]:
        # mode description:
        # cu .... create user, initial call
        # cvu ... validatge new user (after initial call)
        # mu .... modify user, initial call
        # muv ... validate modify user
        # mud ... delete user
        if act_op_mode.startswith("mu"):
            if act_op_mode == "mu":
                act_op_mode = "mu%s" % (user_opts)
            act_user = act_ug_tree.get_user(int(req.sys_args["ulist"]))
        else:
            act_user = None
        s_button = generate_user_mask(req, act_ug_tree, action_log, act_op_mode, act_user)
    elif act_op_mode in ["bu", "bux", "bux2"]:
        s_button = generate_user_masks(req, act_ug_tree, action_log, act_op_mode)
    else:
        s_button = None
    if s_button:
        req.write("%s<div class=\"center\">%s</div></form>" % (action_log.generate_stack("Log"),
                                                               s_button("")))
    else:
        req.write(action_log.generate_stack("Log"))
        act_op_mode = ""
    if not act_op_mode:
        show_user_group_selection(req, act_ug_tree, group_options, user_options)
