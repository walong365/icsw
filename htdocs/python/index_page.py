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
""" index page """

import functions
from basic_defs import SHOW_INDEX_PRI
import html_tools
import cdef_user
import os
from init.cluster.backbone.models import user, capability, only_wf_perms
from django.db.models import Q

def build_cap_dict(req):
    req.cap_stack = cdef_user.capability_stack(req)
    if req.session_data:
        req.cap_stack.add_user_rights(req, req.session_data.user_info)
    return
        
def process_page(req):
    if req.conf["genstuff"].has_key("AUTO_RELOAD"):
        del req.conf["genstuff"]["AUTO_RELOAD"]
    functions.write_header(req, js_list=["jquery-1.2.3.min"])
    functions.write_body(req)
    cluster_name = req.conf["cluster_variables"]["CLUSTER_NAME"].val_str
    header_table = html_tools.html_table(cls="head")
    if req.session_data:
        ui = req.user_info
        header_table[1:2][1] = html_tools.content("<a class=\"init\" href=\"http://www.init.at\" target=\"_top\"><img alt=\"Init.at logo\" src=\"/icons-init/kopflogo.png\" border=0></a>", cls="centersmall")
        header_table[1][2] = html_tools.content(cluster_name, cls="centerlarge")
        header_table[2][2] = html_tools.content("Welcome, %s, to the webfrontend" % (ui.login), cls="centerlarge")
        header_table[1:2][3] = html_tools.content("<a class=\"init\" href=\"http://www.init.at\" target=\"_top\"><img alt=\"Init.at logo\" src=\"/icons-init/kopflogo.png\" border=0></a>", cls="centersmall")
        req.write(header_table(""))
        req.write("<div>&nbsp;</div>")
        req.write("<form action=\"logincheck.py?%s\" method=post>\n" % (functions.get_sid(req)))
        out_table = html_tools.html_table(cls="text")
        # check for alternate link file
        alt_link_file_name = "/etc/sysconfig/cluster/webfrontend_alternate_links"
        if os.path.isfile(alt_link_file_name):
            link_map = dict([(key, value) for key, value in [line.strip().split(None, 1) for line in open(alt_link_file_name, "r").read().split("\n") if line.strip() and len(line.strip().split(None, 1)) > 1]])
        else:
            link_map = {}
        # check for direct links
        direct_link_name = "/etc/sysconfig/cluster/webfrontend_direct_links"
        if os.path.isfile(direct_link_name):
            # format: left_string, right_string, map
            dlink_map = [tuple(line.strip().split(",")) for line in file(direct_link_name, "r").read().split("\n") if line.strip() and line.count(",") == 2]
        else:
            dlink_map = []
        # hack, just temporarly
        my_caps = capability.objects.filter(Q(name__in=only_wf_perms(ui.get_all_permissions())))
        for grp_stuff in my_caps:
            if grp_stuff.left_string:
                mapped_str = ""
                if link_map.has_key(grp_stuff.modulename):
                    act_target = link_map[grp_stuff.modulename]
                    mapped_str = " [mapped]"
                    if not act_target.endswith(".py"):
                        act_target = "%s/%s.py" % (act_target, grp_stuff.modulename)
                else:
                    act_target = "%s.py" % (grp_stuff.modulename)
                out_table[0][0] = html_tools.content("<a href=\"%s?%s\">%s%s</a>%s" % (act_target,
                                                                                       functions.get_sid(req),
                                                                                       grp_stuff.left_string,
                                                                                       " (pri %d)" % (grp_stuff.priority) if SHOW_INDEX_PRI == 1 else "",
                                                                                       mapped_str))
                out_table[None][0] = html_tools.content(grp_stuff.right_string)
        if dlink_map:
            out_table[0]["class"] = "title"
            out_table[None][1:2] = html_tools.content("Direct links", cls="center")
            for left_string, right_string, target in dlink_map:
                out_table[0][0] = html_tools.content("<a href=\"%s\">%s</a>" % (target,
                                                                                left_string))
                out_table[None][0] = html_tools.content("%s" % (right_string))
        sub_pre_str, submit_button = ("logged in as %s%s" % (ui.login,
                                                             req.session_data.is_alias_login and " (via alias %s)" % (req.session_data.alias) or ""), html_tools.submit_button(req, "logout"))
    else:
        header_table[1:2][1] = html_tools.content("<a class=\"init\" href=\"http://www.init.at\" target=\"_top\"><img alt=\"Init.at logo\" src=\"/icons-init/kopflogo.png\" border=0></a>", cls="centersmall")
        header_table[1][2] = html_tools.content(cluster_name, cls="centerlarge")
        header_table[2][2] = html_tools.content("Welcome to the webfrontend", cls="centerlarge")
        header_table[1:2][3] = html_tools.content("<a class=\"init\" href=\"http://www.init.at\" target=\"_top\"><img alt=\"Init.at logo\" src=\"/icons-init/kopflogo.png\" border=0></a>", cls="centersmall")
        req.write(header_table(""))
        req.dc.execute("SELECT u.login FROM user u")
        if req.dc.rowcount:
            req.write(html_tools.gen_hline("Please enter your login information:", 3))
            users_defined = True
            # mmh, first shiny django-object usage :-)
            last_logins = user.objects.filter(session_data__remote_addr=req.environ["REMOTE_ADDR"]).order_by("-date")
            if last_logins:
                last_user = last_logins[0].login
            else:
                last_user = ""
        else:
            req.write(html_tools.gen_hline("First login, please enter the data for the admin user", 3))
            users_defined = False
            last_user = "admin"
        req.write("<form action=\"logincheck.py\" method=post>\n")
        out_table = html_tools.html_table(cls="textsmall")
        username_f = html_tools.text_field(req, "username", size=60, display_len=60)
        password_f = html_tools.text_field(req, "password", size=60, display_len=60, is_password=1)
        username_f[""] = last_user
        password_f[""] = ""
        out_table[0][0] = html_tools.content("Name:" if users_defined else "Admin user:"        , cls="right")
        out_table[None][0] = html_tools.content(username_f                                      , cls="left" )
        out_table[0][0] = html_tools.content("Password:" if users_defined else "Admin password:", cls="right")
        out_table[None][0] = html_tools.content(password_f                                      , cls="left" )
        sub_pre_str, submit_button = ("", html_tools.submit_button(req, "login"))
    req.write(out_table(""))
#     req.write("<a href=\"#\" class=\"codeButtonB\">test</a>")
#     req.write("<div class=\"test2\" style=\"display:none\"><a href=\"/\">home</a></div>")
#     req.write("\n".join(["<script type=\"text/javascript\">",
#                          "$(document).ready(function(){",
#                          "// Your code here",
#                          "});",
#                          '$("a.codeButtonB").click(function(){$("div.test2").toggle(); return false;});',
#                          "</script>"]))
    req.write("<div class=\"center\">%s%s</div>\n</form>\n" % (sub_pre_str,
                                                               submit_button()))
