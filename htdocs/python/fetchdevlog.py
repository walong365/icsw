#!/usr/bin/python -Ot
# -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2001,2002,2003,2004,2005,2007,2008 Andreas Lang-Nevyjel, init.at
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
""" fetch device logs """

import functions
import cdef_device
import tools
import pprint

def db_time_to_str(dbt, with_secs=0):
    year, month, day, day_name, time_str = (dbt[0 : 4], dbt[4:7], dbt[7:9], dbt[9:12], dbt[12:])
    ret_str = "%s, %s. %s %s" % (day_name, day, month, year)
    if with_secs:
        ret_str += " %s" % (time_str)
    return ret_str

def show_device_history(req, act_dev_idx, user_dict, **args):
    verbose = args.get("verbose", False)
    text_mode = args.get("text_mode", False)
    max_lines = args.get("max_lines", 0)
    header_type = args.get("header_type", "div")
    dh_ok_state = {1 : [1, 2, 3, 4],
                   2 : [3, 4],
                   3 : [1, 5],
                   4 : [1, 5],
                   5 : [1, 5]}
    dh_reboot_states = [3, 4]
    if text_mode:
        space_chr, newline_chr, max_ll = (" ", "<cl>", 10000)
    else:
        space_chr, newline_chr, max_ll = ("&nbsp;", "&lt;cl&gt;", args.get("width", 160))
    dh_ok_str = "-" * min(max_ll, 80)
    dh_crash_str = ("-- Crash %s" % (dh_ok_str))[0 : len(dh_ok_str)]
    # store device idx->name pairs
    req.dc.execute("SELECT 1 FROM devicelog WHERE device=%s" % (act_dev_idx))
    total_len = req.dc.rowcount
    loc_dev_lut = {}
    req.dc.execute("SELECT d.*, DATE_FORMAT(d.date, '%%Y%%b%%d%%a%%H:%%i:%%s') AS odate FROM devicelog d WHERE d.device=%s ORDER BY d.date DESC%s" % (act_dev_idx,
                                                                                                                                                      " LIMIT %d" % (max_lines) if max_lines else ""))
    if req.dc.rowcount:
        all_recs = list(req.dc.fetchall())
        all_recs.reverse()
        if text_mode:
            out_str = "Device history (%d lines)" % (len(all_recs))
        else:
            target = ("fetchdevlog.py?%s&dev=%d" % (functions.get_sid(req), act_dev_idx))
            out_str = "<%s class=\"enter\">Device history (%d of %d lines), <a href=\"%s\" type=\"text/plain\">show complete log</a>" % (header_type,
                                                                                                                                         len(all_recs), total_len , target)
        if verbose:
            out_str += ", first entry: %s, latest entry: %s" % (db_time_to_str(all_recs[0]["odate"] , 1),
                                                                db_time_to_str(all_recs[-1]["odate"], 1))
        if text_mode:
            out_str += "\n"
        else:
            out_str += "</%s><div class=\"center\">" % (header_type)
        out_f, act_state, last_state = ([], -1, -1)
        for db_rec in all_recs:
            #for log_source, user, log_status, log_str, log_time in all_recs:
            user = db_rec["user"]
            act_log_id = req.log_status_lut.get(db_rec["log_status"], {"identifier" : "u"})["identifier"]
            if act_log_id not in ["n", "i"]:
                act_log_stat_str = "(%s) " % (act_log_id)
            else:
                act_log_stat_str = ""
            act_lsd = req.log_source_lut.get(db_rec["log_source"], {"identifier" : "UNKNOWN %d" % (db_rec["log_source"])})
            if act_lsd["identifier"] == "user":
                out_f.append(("%suser %s: %s" % (act_log_stat_str, user_dict.get(user, {"login" : "unknown"})["login"], db_rec["text"]), db_rec["odate"], act_log_id))
                #act_state=-1
            else:
                if act_lsd["identifier"] in ["node", "mother"] and user:
                    last_state = act_state
                    act_state = user
                    #out_f.append(("[%d %d %d %s]" % (user, act_state, last_state, str(dh_ok_state.get(last_state, "???"))),
                    #              0,
                    #              "c"))
                    if last_state != -1:
                        if not act_state in dh_ok_state[last_state]:
                            out_f.append((dh_crash_str, 0, "c"))
                if act_lsd["device"]:
                    if not loc_dev_lut.has_key(act_lsd["device"]):
                        req.dc.execute("SELECT name FROM device WHERE device_idx=%d" % (act_lsd["device"]))
                        if req.dc.rowcount:
                            loc_dev_lut[act_lsd["device"]] = req.dc.fetchone()["name"]
                        else:
                            loc_dev_lut[act_lsd["device"]] = "dev_idx %d" % (act_lsd["device"])
                out_f.append(("%s*%s%s: %s" % (act_log_stat_str,
                                               act_lsd["identifier"],
                                               " %s" % (loc_dev_lut[act_lsd["device"]]) if act_lsd["device"] else "",
                                               db_rec["text"]), db_rec["odate"], act_log_id))
                if act_state in dh_reboot_states:
                    out_f.append((dh_ok_str, 0, "c"))
        out_f.reverse()
        if not text_mode:
            out_str += "<select size=\"10\" class=\"fullwidth\">"
        last_day = -1
        for out_line, out_time, log_id in out_f:
            if out_time:
                day, time_str = (out_time[7:9], out_time[12:])
                if day != last_day:
                    if text_mode:
                        out_str += "\n%s\n\n" % (db_time_to_str(out_time))
                    else:
                        out_str += "<option class=\"monodate\">%s</option>\n" % (db_time_to_str(out_time))
                    last_day = day
                o_class, out_line = (log_id in ["n", "i", "w"] and "monook" or "monoerror","%s : %s" % (time_str, out_line))
            else:
                o_class = "monoerror"
            out_parts, pre_str, out_lines = (out_line.split(), "", [])
            while out_parts:
                act_ol = ""
                while len(act_ol) <= max_ll and out_parts:
                    act_ol = "%s %s" % (act_ol, out_parts.pop(0))
                if act_ol:
                    out_lines.append(pre_str + act_ol.strip() + (out_parts and newline_chr or ""))
                pre_str = space_chr * 11
            if text_mode:
                out_str += "".join(["%s\n" % (x) for x in out_lines])
            else:
                out_str += "".join(["<option class=\"%s\">%s</option>\n" % (o_class, x) for x in out_lines])
        if not text_mode:
            out_str += "</select></div>\n"
    else:
        out_str = "No devicehistory"
    return out_str
    
def process_page(req):
    req.content_type = "text/plain"
    req.headers_out["Content-Disposition"] = "filename=\"devicelog\""
    req.send_http_header()
    dev_idx = req.sys_args.get("dev", None)
    if dev_idx:
        tools.init_log_and_status_fields(req)
        req.write(show_device_history(req, dev_idx, tools.get_user_list(req.dc, [], True), verbose=True, text_mode=True))
    else:
        req.write("device_idx not specified")
