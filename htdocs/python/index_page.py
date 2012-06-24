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
from init.cluster.backbone.models import capability, only_wf_perms
from django.db.models import Q
from django.core.urlresolvers import reverse

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
    out_table = html_tools.html_table(cls="text")
    if req.session_data:
        ui = req.user_info
        header_table[1:2][1] = html_tools.content("<a class=\"init\" href=\"http://www.init.at\" target=\"_top\"><img alt=\"Init.at logo\" src=\"/icons-init/kopflogo.png\" border=0></a>", cls="centersmall")
        header_table[1][2] = html_tools.content(cluster_name, cls="centerlarge")
        header_table[2][2] = html_tools.content("Welcome, %s, to the webfrontend" % (ui.login), cls="centerlarge")
        header_table[1:2][3] = html_tools.content("<a class=\"init\" href=\"http://www.init.at\" target=\"_top\"><img alt=\"Init.at logo\" src=\"/icons-init/kopflogo.png\" border=0></a>", cls="centersmall")
        req.write(header_table(""))
        req.write("<div>&nbsp;</div>")
        #req.write("<form action=\"logincheck.py?%s\" method=post>\n" % (functions.get_sid(req)))
        req.write("<form action=\"%s\" method=post>\n" % (reverse("session:logout")))
        # hack, just temporarly
        my_caps = capability.objects.filter(Q(name__in=only_wf_perms(ui.get_all_permissions())))
        for grp_stuff in my_caps:
            if grp_stuff.left_string:
                mapped_str = ""
                act_target = "%s.py" % (grp_stuff.modulename)
                out_table[0][0] = html_tools.content("<a href=\"%s?%s\">%s%s</a>%s" % (act_target,
                                                                                       functions.get_sid(req),
                                                                                       grp_stuff.left_string,
                                                                                       " (pri %d)" % (grp_stuff.priority) if SHOW_INDEX_PRI == 1 else "",
                                                                                       mapped_str))
                out_table[None][0] = html_tools.content(grp_stuff.right_string)
        sub_pre_str, submit_button = ("logged in as %s%s" % (ui.login,
                                                             req.session_data.is_alias_login and " (via alias %s)" % (req.session_data.alias) or ""), html_tools.submit_button(req, "logout"))
    req.write(out_table(""))
    req.write("<div class=\"center\">%s%s</div>\n</form>\n" % (sub_pre_str,
                                                               submit_button()))
