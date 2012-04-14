#!/usr/bin/python -Ot
# -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2001,2002,2003,2004,2005,2006 Andreas Lang-Nevyjel, init.at
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
""" nagios portal page """

import functions
import html_tools
import os

def module_info():
    return {"na" : {"default"               : 0,
                    "enabled"               : 1,
                    "description"           : "Monitoring daemon",
                    "left_string"           : "Monitoring Daemon",
                    "right_string"          : "Monitoring information",
                    "capability_group_name" : "info",
                    "priority"              : -20},
            "nap" : {"default"                : 0,
                     "enabled"                : 1,
                     "description"            : "Nagios Problems",
                     "mother_capability_name" : "na"},
            "nai" : {"default"                : 0,
                     "enabled"                : 1,
                     "description"            : "Nagios Misc",
                     "mother_capability_name" : "na"}}

def process_page(req):
    if req.conf["genstuff"].has_key("AUTO_RELOAD"):
        del req.conf["genstuff"]["AUTO_RELOAD"]
    functions.write_header(req)
    functions.write_body(req)
    main_table = html_tools.html_table(cls="blind")
    out_table = html_tools.html_table(cls="textsmall")
    req.dc.execute("SELECT dv.name, dv.val_str FROM device_variable dv, device d, device_group dg WHERE dg.cluster_device_group AND d.device_group=dg.device_group_idx AND dv.device=d.device_idx AND (dv.name='md_version' or dv.name='md_type')")
    ref_dict = {"md_version" : "unknown",
                "md_type"    : "unknown"}
    for db_rec in req.dc.fetchall():
        ref_dict[db_rec["name"]] = db_rec["val_str"]
    if ref_dict["md_type"] in ["nagios", "unknown"]:
        nag_vers_2x, nag_vers_3x = (False, False)
        if ref_dict["md_version"].startswith("2"):
            nag_vers_2x = True
        elif ref_dict["md_version"].startswith("3"):
            nag_vers_3x = True
        if nag_vers_2x or nag_vers_3x:
            def_class = "left"
            mon_list = [("tac.cgi"                                   , "Tactical Overview"),
                        ("status.cgi?host=all"                       , "Service detail"),
                        ("status.cgi?hostgroup=all&style=hostdetail" , "Host detail"),
                        ("status.cgi?hostgroup=all&style=overview"   , "Hostgroup overview"),
                        ("status.cgi?hostgroup=all&style=summary"    , "Hostgroup summary"),
                        ("status.cgi?hostgroup=all&style=grid"       , "Hostgroup grid"),
                        ("status.cgi?servicegroup=all&style=overview", "Servicegroup overview"),
                        ("status.cgi?servicegroup=all&style=summary" , "Servicegroup summary"),
                        ("status.cgi?servicegroup=all&style=grid"    , "Servicegroup grid")]
            prob_list = [("statusmap.cgi?host=all"                                                                       , "Status map"),
                         ("status.cgi?host=all&servicestatustypes=28"                                                    , "Service Problems"),
                         ("status.cgi?host=all&servicestatustypes=28&hoststatustypes=2&showdownhosts&serviceprops=262144", "Smart Service (HS)"),
                         ("status.cgi?host=all&servicestatustypes=28&hoststatustypes=2&showdownhosts"                    , "Smart Service (HS+SS)"),
                         ("status.cgi?hostgroup=all&style=hostdetail&hoststatustypes=12"                                 , "Host Problems"),
                         ("outages.cgi"                                                              , "Network outtages"),
                         ("hs0"                                                                      , None),
                         ("hs1"                                                                      , None),
                         ("extinfo.cgi?&type=3"                                                      , "Comments"),
                         ("extinfo.cgi?&type=6"                                                      , "Downtime")]
            other_list = [("trends.cgi"                   , "Trends"),
                          ("avail.cgi"                    , "Availability"),
                          ("histogram.cgi"                , "Alert Histogram"),
                          ("history.cgi?host=all"         , "Alert History"),
                          ("summary.cgi"                  , "Alert Summary"),
                          ("notifications.cgi?contact=all", "Notifications"),
                          ("showlog.cgi"                  , "Event Log"),
                          ("config.cgi"                   , "View config"),
                          ("extinfo.cgi?&type=0"          , "Process info"),
                          ("extinfo.cgi?&type=4"          , "Performance Info"),
                          ("extinfo.cgi?&type=7"          , "Scheduling Queue")]
        else:
            def_class = "center"
            mon_list = [("tac.cgi"                                  , "Tactical Overview"),
                        ("status.cgi?host=all"                      , "Service detail"),
                        ("status.cgi?hostgroup=all&style=hostdetail", "Host detail"),
                        ("status.cgi?hostgroup=all"                 , "Status Overview"),
                        ("status.cgi?hostgroup=all&style=summary"   , "Status Summary"),
                        ("status.cgi?hostgroup=all&style=grid"      , "Status Grid")]
            prob_list = [("status.cgi?host=all&servicestatustypes=248"                  , "Service Problems"),
                         ("status.cgi?hostgroup=all&style=hostdetail&hoststatustypes=12", "Host Problems"),
                         ("outages.cgi"                                                 , "Network outtages"),
                         ("statusmap.cgi?host=all"                                      , "Status map"),
                         ("extinfo.cgi?type=3"                                          , "Network health")]
            other_list = [("trends.cgi"                   , "Trends"),
                          ("avail.cgi"                    , "Availability Trends"),
                          ("histogram.cgi"                , "Alert Histogram"),
                          ("history.cgi?host=all"         , "Alert History"),
                          ("summary.cgi"                  , "Alert Summary"),
                          ("notifications.cgi?contact=all", "Notifications"),
                          ("showlog.cgi"                  , "Event Log"),
                          ("config.cgi"                   , "View config"),
                          ("extinfo.cgi?&type=3"          , "Comments"),
                          ("extinfo.cgi?&type=6"          , "Downtime"),
                          ("extinfo.cgi?&type=0"          , "Process info"),
                          ("extinfo.cgi?&type=4"          , "Performance Info"),
                          ("extinfo.cgi?&type=7"          , "Scheduling Queue")]
        line_idx = 0
        out_table[0]["class"] = "title"
        out_table[None][0] = html_tools.content("--General--", type="th", cls=def_class)
        line_idx = 1 - line_idx
        out_table[0]["class"] = "line1%d" % (line_idx)
        out_table[None][0] = html_tools.content("Nagios Version %s" % (ref_dict["md_version"]), cls="left")
        for targ, what in [("href=\"main.py?%s\" target=\"_top\"" % (functions.get_sid(req)), "Back to main page")]:
            line_idx = 1 - line_idx
            out_table[0]["class"] = "line1%d" % (line_idx)
            out_table[None][0] = html_tools.content("<a %s>%s</a>" % (targ, what), cls=def_class)
        if req.user_info and req.user_info.capability_ok("na"):
            out_table[0]["class"] = "title"
            out_table[None][0] = html_tools.content("--Monitoring--", type="th", cls=def_class)
            for targ, what in mon_list:
                line_idx = 1 - line_idx
                out_table[0]["class"] = "line1%d" % (line_idx)
                out_table[None][0] = html_tools.content("<a href=\"/nagios/cgi-bin/%s\" target=\"nagios\">%s</a>" % (targ, what), cls=def_class)
        if req.user_info and req.user_info.capability_ok("nap"):
            out_table[0]["class"] = "title"
            out_table[None][0] = html_tools.content("--Problems--", type="th", cls=def_class)
            for targ, what in prob_list:
                line_idx = 1 - line_idx
                out_table[0]["class"] = "line1%d" % (line_idx)
                if targ == "hs0":
                    out_table[None][0] = html_tools.content("Show Host:",cls="left")
                elif targ == "hs1":
                    out_table[None][0] = html_tools.content("\n".join(["<form method=\"get\" action=\"/nagios/cgi-bin/status.cgi\" target=\"nagios\">",
                                                                       "<input type=\"hidden\" name=\"navbarsearch\" value=\"1\" />",
                                                                       "<input type=\"text\" name=\"host\" size=\"15\" />",
                                                                       "</form>"]), cls="left")
                    # original code
                    #<td nowrap>
                    #<form method="get" action="/nagios/cgi-bin/status.cgi" target="main">
                    #<input type='hidden' name='navbarsearch' value='1'>
                    #<input type='text' name='host' size='15' class="NavBarSearchItem">
                    #</form>
                else:
                    out_table[None][0] = html_tools.content("<a href=\"/nagios/cgi-bin/%s\" target=\"nagios\">%s</a>" % (targ, what), cls=def_class)
        if req.user_info and req.user_info.capability_ok("nai"):
            out_table[0]["class"] = "title"
            out_table[None][0] = html_tools.content("--Other stuff--", type="th", cls=def_class)
            if os.path.isdir("/opt/nagios/shared/docs"):
                line_idx = 1 - line_idx
                out_table[0]["class"] = "line1%d" % (line_idx)
                out_table[None][0] = html_tools.content("<a href=\"/nagios/docs/index.html\" target=\"nagios\">Documentation</a>", cls=def_class)
            for targ, what in other_list:
                line_idx = 1 - line_idx
                out_table[0]["class"] = "line1%d" % (line_idx)
                out_table[None][0] = html_tools.content("<a href=\"/nagios/cgi-bin/%s\" target=\"nagios\">%s</a>" % (targ, what), cls=def_class)
        main_table[1][1] = html_tools.content("<a class=\"init\" href=\"http://www.init.at\" target=\"_top\"><img alt=\"Init.at logo\" src=\"/icons-init/kopflogo.png\" border=0></a>", cls="center")
        main_table[2][1] = html_tools.content(out_table, cls="centersmall")
        main_table[1:2][2] = html_tools.content("<iframe width=\"100%\" height=\"1024\" frameborder=\"0\" marginheight=\"0\" marginwidth=\"0\" name=\"nagios\" src=\"/nagios/cgi-bin/tac.cgi\" ></iframe>", cls="top")
    else:
        main_table[1][1] = html_tools.content("<iframe width=\"100%\" height=\"1200\" frameborder=\"0\" marginheight=\"0\" marginwidth=\"0\" name=\"nagios\" src=\"/icinga/\" ></iframe>", cls="top")
    req.write(main_table(""))
