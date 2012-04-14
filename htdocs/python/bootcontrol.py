#!/usr/bin/python -Ot
#
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
""" bootcontrol """

import functions
import logging_tools
import os
import os.path
import time
import sys
import stat
import tools
import html_tools
import cdef_device
import fetchdevlog
import gzip
import basic_defs
import cdef_kernels

# some constants
MAX_DEVLOG_LEN    = 100
SYSLOG_LINE_LIMIT = 500

def module_info():
    return  {"bc" : {"description"           : "Boot control",
                     "default"               : 0,
                     "enabled"               : 1,
                     "left_string"           : "Boot control",
                     "right_string"          : "Boot control",
                     "priority"              : -100,
                     "capability_group_name" : "conf"}}

def show_device_syslog(req, act_dev, is_verbose):
    syslog_dir = "/var/log/hosts/%s" % (act_dev.get_name())
    log_list = html_tools.selection_list(req, "syslog%s" % (act_dev.get_suffix()), {})
    first_idx, act_idx, num_logs = (None, 9999, 0)
    first_time, last_time, last_week = (time.time() + 1000., 0., -1)
    log_dict = {}
    for root, dirs, files in os.walk(syslog_dir):
        if "log" in files or "log.gz" in files:
            try:
                time_tuple = time.strptime(root[len(syslog_dir) + 1:], "%Y/%m/%d")
            except ValueError:
                pass
            else:
                act_week = time.strftime("%W", time_tuple)
                if act_week != last_week and last_week != -1:
                    act_idx -= 1
                    log_list[act_idx] = {"name"     : "-" * 30,
                                         "disabled" : 1}
                last_week = act_week
                time_str = time.strftime("%a, %d. %b %Y<br>", time_tuple)
                act_time = time.mktime(time_tuple)
                first_time = min(first_time, act_time)
                last_time  = max(last_time, act_time)
                act_idx -= 1
                num_logs += 1
                if "log" in files:
                    log_dict[act_idx] = "%s/log" % (root)
                    log_list[act_idx] = "%s, %d bytes" % (time_str, os.stat(log_dict[act_idx])[stat.ST_SIZE])
                else:
                    log_dict[act_idx] = "%s/log.gz" % (root)
                    log_list[act_idx] = "%s, %d bytes (compressed)" % (time_str, os.stat(log_dict[act_idx])[stat.ST_SIZE])
    if num_logs:
        first_time = time.localtime(first_time)
        last_time  = time.localtime(last_time)
        out_str = "<div class=\"center\">"
        if is_verbose:
            out_str += "%s found, first %s, last %s, show log from " % (logging_tools.get_plural("Log", num_logs),
                                                                        time.strftime("%d. %b %Y", first_time),
                                                                        time.strftime("%d. %b %Y", last_time))
        act_log = log_list.check_selection("", act_idx)
        out_str += log_list()
        dev_name = act_dev.get_name()
        if log_dict.has_key(act_log):
            try:
                if log_dict[act_log].endswith(".gz"):
                    log_lines = gzip.open(log_dict[act_log], "r").readlines()
                else:
                    log_lines = open(log_dict[act_log], "r").readlines()
            except:
                out_str += "Error reading log: %s (%s)" % (str(sys.exc_info()[0]),
                                                           str(sys.exc_info()[1]))
            else:
                num_lines = len(log_lines)
                if num_lines > SYSLOG_LINE_LIMIT:
                    ll_pf, line_offset = (", showing only the last %d" % (SYSLOG_LINE_LIMIT), num_lines - SYSLOG_LINE_LIMIT)
                    del log_lines[:line_offset]
                else:
                    ll_pf, line_offset = ("", 0)
                lines = []
                for log_line in log_lines:
                    ll_split = log_line.strip().split(None, 4)
                    if len(ll_split) == 5:
                        # check for time
                        bla1, bla2, line_time, line_host, line_content = ll_split
                        # check for host prefix
                        if line_host.startswith(dev_name):
                            if line_host == dev_name:
                                pfix = ""
                            else:
                                pfix = "%s: " % (line_host[len(dev_name):])
                        else:
                            pfix = "%s: " % (line_host)
                        log_str = "%s%s: %s" % (pfix, line_time, line_content)
                        lines.append(log_str)
                    else:
                        lines.append(log_line)
                        print "Error : ", log_line, "<br>"
                target = "fetchlog.py?%s&log=%s" % (functions.get_sid(req), log_dict[act_log])
                out_str += " in %s%s, download <a href=\"%s\" type=\"text/plain\">complete log as plaintext</a></div>\n<div class=\"center\">" % (logging_tools.get_plural("line", num_lines), ll_pf, target)
                out_str += "<textarea style=\"width=100%%; font-family:monospace ; font-style:normal ; font-size:10pt ; \" cols=\"100\" rows=\"10\" readonly >%s</textarea>\n" % ("\n".join(lines))
        out_str += "</div>\n"
    else:
        out_str = "No syslogs found"
    return out_str
    
def handle_mac_changes(req, act_dev, infos_set, action_log, flags_lut, html_instances, glob_fields):
    mac_action_list, mac_address_field, write_mac_action_list, greedy_action_list, mac_driver_field = html_instances
    # always check for macadr-changes
    if "m" in infos_set:
        glob_mac_action, glob_mac_address, glob_greedy_action, glob_write_mac_action, glob_mac_driver = glob_fields
        act_mac, act_driver = (act_dev.get_mac_address(),
                               act_dev.get_mac_driver())
        mac_action = mac_action_list.check_selection(act_dev.get_suffix(), "a")
        if mac_action == "a" and glob_mac_action != "a":
            mac_action = glob_mac_action
        new_mac = mac_address_field.check_selection(act_dev.get_suffix(), act_mac)
        if mac_action == "c":
            new_mac = "00:00:00:00:00:00"
            mac_address_field[act_dev.get_suffix()] = new_mac
        if new_mac != act_mac:
            action_log.add_warn("Mac-address of %s changed from '%s' to '%s'" % (act_dev.get_name(),
                                                                                 act_mac,
                                                                                 new_mac), "DHCP")
        new_greedy = greedy_action_list.check_selection(act_dev.get_suffix(), "a")
        if new_greedy == "a" and glob_greedy_action != "a":
            new_greedy = glob_greedy_action
        if new_greedy != "a":
            greedy_action_list.mode_is_setup()
            act_dev.set_greedy_mode(greedy_action_list[new_greedy]["greedy"])
            act_dev.add_log_entry(req.ulsi,
                                  req.user_info.get_idx(),
                                  req.log_status.get("i", {"log_status_idx" : 0})["log_status_idx"],
                                  "%s greedy_mode" % ({0 : "disable", 1 : "enable"}[greedy_action_list[new_greedy]["greedy"]]))
            greedy_action_list.mode_is_normal()
        act_write_mac_action = act_dev.get_dhcp_write_flag() and "b" or "c"
        write_mac_action = write_mac_action_list.check_selection(act_dev.get_suffix(), act_write_mac_action)
        if glob_write_mac_action != "a" and write_mac_action != glob_write_mac_action:
            write_mac_action = glob_write_mac_action
            write_mac_action_list[act_dev.get_suffix()] = write_mac_action
        mac_com = None
        if write_mac_action != act_write_mac_action:
            act_dev.set_dhcp_write_flag(write_mac_action == "b" and 1 or 0)
            act_dev.add_log_entry(req.ulsi,
                                  req.user_info.get_idx(),
                                  req.log_status.get("i", {"log_status_idx" : 0})["log_status_idx"],
                                  "%s dhcp_write_flag" % ({"b" : "set", "c" : "cleared"}[write_mac_action]))
            mac_com = "m"
        if new_mac == act_mac and not glob_mac_address:
            mac_address_field[act_dev.get_suffix()] = new_mac
            new_mac = act_mac
        new_driver = mac_driver_field.check_selection(act_dev.get_suffix(), act_driver)
        if new_driver == act_driver and glob_mac_driver:
            new_driver = glob_mac_driver
        if new_driver != act_driver:
            mac_driver_field[act_dev.get_suffix()] = new_driver
            act_dev.set_new_mac_driver(new_driver)
            act_dev.add_log_entry(req.ulsi,
                                  req.user_info.get_idx(),
                                  req.log_status.get("i", {"log_status_idx" : 0})["log_status_idx"],
                                  "changed driver from '%s' to '%s'" % (act_driver, new_driver))
        if not new_mac.strip():
            new_mac = "00:00:00:00:00:00"
        new_mac = new_mac.lower()
        reset_macaddr = 1
        if mac_action != "a":
            if tools.is_mac_address(new_mac, 6) and act_mac != new_mac:
                reset_macaddr = 0
                act_dev.set_new_mac_address(new_mac)
                act_dev.add_log_entry(req.ulsi,
                                      req.user_info.get_idx(),
                                      req.log_status.get("i", {"log_status_idx" : 0})["log_status_idx"],
                                      "changed macaddress from '%s' to '%s'" % (act_mac, new_mac))
            # reset_macaddr is 1 if the macaddr is unchanged
            mac_com = "m"
        if mac_com:
            act_dev.add_log_entry(req.ulsi,
                                  req.user_info.get_idx(),
                                  req.log_status.get("i", {"log_status_idx" : 0})["log_status_idx"],
                                  "requested %s (with mac %s)" % (flags_lut[mac_com], act_dev.get_mac_address()))
            act_dev.add_device_flag(mac_com)
            dhcp_post_check = [act_dev.get_idx()]
        if reset_macaddr:
            mac_address_field[act_dev.get_suffix()] = act_mac
                #if act_mac != new_mac:
    else:
        if mac_address_field:
            act_mac, act_driver = (act_dev.get_mac_address(),
                                   act_dev.get_mac_driver())
            new_mac = mac_address_field.check_selection(act_dev.get_suffix(), act_mac)
            if new_mac != act_mac:
                action_log.add_warn("Mac-address of %s changed from '%s' to '%s'" % (act_dev.get_name(),
                                                                                     act_mac,
                                                                                     new_mac), "DHCP")

def handle_comment_changes(req, act_dev, infos_set, action_log, html_instances, glob_fields):
    comment_text_field, new_log_entry_field = html_instances
    glob_comment, glob_log_entry = glob_fields
    act_com = act_dev.get_comment()
    new_com = comment_text_field.check_selection(act_dev.get_suffix(), act_com)
    if new_com == act_com and glob_comment:
        new_com = glob_comment
    if act_com != new_com:
        comment_text_field[act_dev.get_suffix()] = new_com
        act_dev.add_sql_changes({"comment" : new_com})
        if new_com:
            log_str = "set comment to '%s'" % (new_com)
        else:
            log_str = "cleared comment"
        act_dev.add_log_entry(req.ulsi,
                              req.user_info.get_idx(),
                              req.log_status.get("i", {"log_status_idx" : 0})["log_status_idx"],
                              log_str)
        act_dev.set_comment(new_com)
    new_log = new_log_entry_field.check_selection(act_dev.get_suffix(), "")
    log_adds = []
    if new_log:
        log_adds.append(new_log)
    if glob_log_entry:
        log_adds.append(glob_log_entry)
    for add_log in log_adds:
        new_log_entry_field[act_dev.get_suffix()] = ""
        act_dev.add_log_entry(req.ulsi,
                              req.user_info.get_idx(),
                              req.log_status.get("i", {"log_status_idx" : 0})["log_status_idx"],
                              add_log)
    
def process_page(req):
    if req.conf["genstuff"].has_key("AUTO_RELOAD"):
        del req.conf["genstuff"]["AUTO_RELOAD"]
    functions.write_header(req)
    functions.write_body(req)
    # init log and status
    tools.init_log_and_status_fields(req)
    # add_info selection list
    add_info = html_tools.selection_list(req, "add_info", {"a" : "Power control" ,
                                                           "b" : "Target state",
                                                           "p" : "Partition"   ,
                                                           "i" : "Image"       ,
                                                           "k" : "Kernel"      ,
                                                           "c" : "Comment/Log" ,
                                                           "l" : "Device log"  ,
                                                           "m" : "MACAddress"  ,
                                                           "s" : "Syslog"      }, multiple=1, size=5)
    infos_set = add_info.check_selection("", [])
    # ping/reboot/halt/poweroff list, also action-dict
    prhp_list = html_tools.radio_list(req, "prhp", {"a0" : {"action" : "status"  , "post_str" : "status"  },
                                                    "a1" : {"action" : "reboot"  , "post_str" : "reboot"  },
                                                    "a2" : {"action" : "halt"    , "post_str" : "halt"    },
                                                    "a3" : {"action" : "poweroff", "post_str" : "poweroff"}},
                                      auto_reset=1)
    glob_prhp_action = prhp_list.check_selection("", "a0")
    # action log
    action_log = html_tools.message_log()
    # macbootlog_button
    bootlog_sel = html_tools.selection_list(req, "bls", {"b0" : "--- nothing ---",
                                                         "b1" : "macbootlog (full)",
                                                         "b2" : "macbootlog (last 40 entries)"})
    bootlog_action = bootlog_sel.check_selection("", "b0")
    dev_presel = []
    if bootlog_action != "b0":
        req.dc.execute("SELECT DISTINCT DATE_FORMAT(date,'%Y%m%d%a%b%u') AS mdate, COUNT(date) AS datec FROM macbootlog GROUP BY mdate DESC")
        act_mbl_date = time.strftime("%Y%m%d%a%b%W", time.localtime(time.time()))
        if req.dc.rowcount:
            all_mbl_dates = [(x["mdate"], x["datec"]) for x in req.dc.fetchall()]
        else:
            all_mbl_dates = [(act_mbl_date, 0)]
        mbl_list = html_tools.selection_list(req, "mbdate", {}, sort_new_keys=False)
        last_week = "-"
        for mbl_date, mbl_count in all_mbl_dates:
            act_week = mbl_date[14:16]
            if act_week != last_week:
                mbl_list["w%s" % (mbl_date[0 : 8])] =  {"name"     : "%s week %2d, %s" % ("--", int(act_week), "-" * 16),
                                                        "disabled" : 1}
                last_week = act_week
            mbl_list[mbl_date[0 : 8]] = "%s, %d. %s %d, %s" % (mbl_date[8:11], int(mbl_date[6:8]), mbl_date[11:14], int(mbl_date[0 : 4]), logging_tools.get_plural("entry", mbl_count))
        show_mbl_date = mbl_list.check_selection("", all_mbl_dates[0][0][0 : 8])
        # fetch mac_ignore entries
        req.dc.execute("SELECT DISTINCT macadr FROM mac_ignore")
        mac_ignore_list = [x["macadr"] for x in req.dc.fetchall()]
        mbl_query = "SELECT b.macadr, b.date, b.type, b.ip, DATE_FORMAT(b.date,'%H:%i:%s') as fdate, d.name, d.device_idx, d2.name AS bsname FROM log_source l, device d2, macbootlog b LEFT JOIN " + \
                    "device d ON d.device_idx=b.device WHERE b.log_source=l.log_source_idx AND l.device=d2.device_idx AND b.date > '%s000000' AND b.date < '%s235959' ORDER BY date DESC%s" % (show_mbl_date, show_mbl_date, bootlog_action == "b2" and " LIMIT 40" or "")
        mac_ignore_button = html_tools.checkbox(req, "mi")
        device_add_button = html_tools.checkbox(req, "ma")
        mac_ignore_remove = html_tools.checkbox(req, "mr")
        mac_checked, mac_ignore_drawn = ([], [])
        #print mbl_query
        req.dc.execute(mbl_query)
        all_mb_entries = req.dc.fetchall()
        mac_ignore_add_list, device_add_list = ([], [])
        if all_mb_entries:
            mbl_table = html_tools.html_table(cls = "normal")
            num_lines = (len(all_mb_entries)+1)/2
            mbl_info_str = ", found %s" % (logging_tools.get_plural("MAC-Bootlog entry", len(all_mb_entries)))
            idx, act_row, line_idx = (0, 1, 1)
            for act_entry in all_mb_entries:
                idx += 1
                if idx == num_lines+1:
                    mbl_table.set_cursor(0, 0)
                    act_row = 10
                if mbl_table.get_cursor()[0] == 0:
                    line_idx = 1-line_idx
                    mbl_table[0][act_row] = html_tools.content("Idx", type="th")
                    if act_row == 1:
                        mbl_table[None]["class"] = "line0%d" % (line_idx)
                    mbl_table[None][0] = html_tools.content("RequestType", type="th")
                    mbl_table[None][0] = html_tools.content("MACAddress" , type="th")
                    mbl_table[None][0] = html_tools.content("ignore"     , type="th")
                    mbl_table[None][0] = html_tools.content("add"        , type="th")
                    mbl_table[None][0] = html_tools.content("device"     , type="th")
                    mbl_table[None][0] = html_tools.content("server"     , type="th")
                    mbl_table[None][0] = html_tools.content("IP"         , type="th")
                    mbl_table[None][0] = html_tools.content("time"       , type="th")
                line_idx = 1-line_idx
                l0_idx, l1_idx = ("line0%d" % (line_idx), "line1%d" % (line_idx))
                mbl_table[0][act_row] = html_tools.content(idx, cls=l0_idx)
                if act_row == 1:
                    mbl_table[None]["class"] = l1_idx
                mbl_table[None][0] = html_tools.content("DHCP%s" % (act_entry["type"]))
                mbl_table[None][0] = html_tools.content(act_entry["macadr"], cls="center")
                if not act_entry["macadr"] in mac_checked:
                    mac_checked.append(act_entry["macadr"])
                    mac_wn = act_entry["macadr"].replace(":", "")
                    if act_entry["macadr"] in mac_ignore_list:
                        # check for unignore
                        if mac_ignore_remove.check_selection(mac_wn):
                            action_log.add_ok("Removed '%s' from MAC-ignore list" % (act_entry["macadr"]), "SQL")
                            req.dc.execute("DELETE FROM mac_ignore WHERE macadr='%s'" % (act_entry["macadr"]))
                            mac_ignore_list.remove(act_entry["macadr"])
                            mac_ignore_button.check_selection(mac_wn)
                    else:
                        if mac_ignore_button.check_selection(mac_wn):
                            action_log.add_ok("Adding '%s' to MAC-ignore list" % (act_entry["macadr"]), "SQL")
                            mac_ignore_list.append(act_entry["macadr"])
                            mac_ignore_add_list.append(act_entry["macadr"])
                if act_entry["macadr"] in mac_ignore_list:
                    mbl_table[None][0] = html_tools.content("I", cls="center")
                elif act_entry["macadr"] in mac_ignore_drawn:
                    mbl_table[None][0] = html_tools.content("---", cls="center")
                else:
                    mbl_table[None][0] = html_tools.content(mac_ignore_button, mac_wn, cls="center")
                    mac_ignore_drawn.append(act_entry["macadr"])
                if act_entry["device_idx"] and act_entry["device_idx"] not in device_add_list:
                    dev_suffix = "%d" % (act_entry["device_idx"])
                    if device_add_button.check_selection(dev_suffix):
                        dev_presel.append(str(act_entry["device_idx"]))
                    mbl_table[None][0] = html_tools.content(device_add_button, dev_suffix, cls="center")
                    device_add_list.append(act_entry["device_idx"])
                else:
                    mbl_table[None][0] = html_tools.content("---", cls="center")
                mbl_table[None][0] = html_tools.content(act_entry["name"] or "---", cls="center")
                mbl_table[None][0] = html_tools.content(act_entry["bsname"], cls="center")
                mbl_table[None][0] = html_tools.content(act_entry["ip"], cls="center")
                mbl_table[None][0] = html_tools.content(act_entry["fdate"], cls="center")
            if num_lines + 1 > mbl_table.get_cursor()[0]:
                mbl_table[0][act_row : 2 * (act_row - 1)] = html_tools.content("&nbsp;")
            if mac_ignore_add_list:
                req.dc.execute("INSERT INTO mac_ignore VALUES%s" % (",".join(["(0,'%s',null)" % (x) for x in mac_ignore_list])))
            if mac_ignore_list:
                mac_ignore_table = html_tools.html_table(cls="normalsmall")
                mac_ignore_list.sort()
                idx, line_idx = (0, 1)
                for act_entry in mac_ignore_list:
                    if not idx:
                        line_idx = 1-line_idx
                        mac_ignore_table[0][0] = html_tools.content("Idx", type="th")
                        mac_ignore_table[None]["class"] = "line0%d" % (line_idx)
                        mac_ignore_table[None][0] = html_tools.content("remove")
                        mac_ignore_table[None][0] = html_tools.content("MACAddress")
                        
                    line_idx = 1-line_idx
                    idx += 1
                    mac_ignore_table[0][0] = html_tools.content(idx, cls="line0%d" % (line_idx))
                    mac_ignore_table[None]["class"] = "line1%d" % (line_idx)
                    mac_wn = act_entry.replace(":", "")
                    mac_ignore_remove.check_selection(mac_wn)
                    mac_ignore_table[None][0] = html_tools.content(mac_ignore_remove, mac_wn, cls="center")
                    mac_ignore_table[None][0] = html_tools.content(act_entry)
            else:
                mac_ignore_table = None
        else:
            mbl_table = None
            mbl_info_str = ", found no MAC-Bootlog entries"
    else:
        mbl_table = None
        mbl_info_str = ""
    # verbose button
    verbose_button = html_tools.checkbox(req, "verb")
    is_verbose = verbose_button.check_selection()
    if is_verbose:
        scon_logs = html_tools.message_log()
    else:
        scon_logs = None
    dev_tree = tools.display_list(req)
    dev_desel_list = html_tools.selection_list(req, "ddss", {0 : "nothing",
                                                             1 : "ok devices",
                                                             2 : "warn devices",
                                                             3 : "both devices"}, inital_mode="n", auto_reset=True)
    # ok devices deselection
    dev_ok_desel_list   = html_tools.selection_list(req, "dokdl", {1 : "a"}, multiple=1, initial_mode="n", validate_set_value=False, validate_get_value=False)
    dev_warn_desel_list = html_tools.selection_list(req, "dwadl", {1 : "a"}, multiple=1, initial_mode="n", validate_set_value=False, validate_get_value=False)
    dev_desel_action = dev_desel_list.check_selection("", 0)
    dev_ok_desel   = dev_ok_desel_list.check_selection("", [])
    dev_warn_desel = dev_warn_desel_list.check_selection("", [])
    if dev_desel_action in [0, 2]:
        dev_ok_desel = []
    if dev_desel_action in [0, 1]:
        dev_warn_desel = []
    dev_tree.add_regexp_field()
    dev_tree.add_devsel_fields(tools.get_device_selection_lists(req.dc, req.user_info.get_idx()))
    dev_tree.add_device_preselection(dev_presel)
    dev_tree.remove_device_deselection(dev_ok_desel)
    dev_tree.remove_device_deselection(dev_warn_desel)
    dev_tree.query(["H", "S"], 
                   ["comment", "etherboot_valid", "dhcp_mac", "dhcp_written", "dhcp_write", "dhcp_error",
                    "n.macadr", "n.devname", "n.netdevice_idx", "n.driver", "n.driver_options", "reachable_via_bootserver"], 
                   [("netdevice", "n")],
                   ["d.bootserver", "n.netdevice_idx=d.bootnetdevice AND d.show_in_bootcontrol"])
    if not dev_tree.devices_found():
        req.write(html_tools.gen_hline("No devices found", 2))
    else:
        # fetch bootservers
        bootserver_dict = tools.boot_server_struct(req.dc, action_log)
        dg_sel, d_sel, dg_sel_eff = dev_tree.get_selection()
        num_f = {"greedy"            : 0,
                 "nodhcp"            : 0,
                 "etherboot_invalid" : 0,
                 "not_reachable"     : 0}
        for dg in dev_tree.get_sorted_devg_idx_list():
            for dev in dev_tree.get_sorted_dev_idx_list(dg):
                dev_struct = dev_tree.get_dev_struct(dev)
                if dev_struct["bootserver"]:
                    if bootserver_dict.has_key(dev_struct["bootserver"]):
                        bs_string = "bs=%s" % (bootserver_dict[dev_struct["bootserver"]])
                    else:
                        bs_string = "invalid bootserver %d" % (dev_struct["bootserver"])
                else:
                    bs_string = "no bs"
                prob_f, err_f = ([], [])
                if dev_struct["dhcp_mac"]:
                    prob_f.append("gr")
                    num_f["greedy"] += 1
                if not dev_struct["dhcp_written"]:
                    prob_f.append("dh")
                    num_f["nodhcp"] += 1
                if not dev_struct["etherboot_valid"]:
                    err_f.append("device has no valid etherboot directory")
                    prob_f.append("ed")
                    num_f["etherboot_invalid"] += 1
                if not dev_struct["reachable_via_bootserver"]:
                    err_f.append("device is not reachable")
                    prob_f.append("nr")
                    num_f["not_reachable"] += 1
                if prob_f:
                    dev_struct["class"] = "error"
                    dev_struct["error_str"] = ", ".join(err_f)
                    dev_struct["pre_str"] = "%s;" % (",".join(prob_f))
                else:
                    dev_struct["error_str"] = ""
                dev_struct["post_str"] = " %s" % (bs_string)
        ds_dict = dev_tree.get_device_selection_lists()
        sel_table = html_tools.html_table(cls = "blindsmall")
        sel_table[0][0] = html_tools.content(add_info)
        sel_table[None][0] = html_tools.content(dev_tree, "devg", cls="center")
        sel_table[None][0] = html_tools.content(dev_tree, "dev", cls="center")
        if ds_dict:
            sel_table[None][0] = html_tools.content(dev_tree, "sel", cls="center")
            col_span = 4
        else:
            col_span = 3
        # report for problem devices
        prob_f = []
        if num_f["greedy"]:
            prob_f.append(logging_tools.get_plural("greedy machine", num_f["greedy"]))
        if num_f["nodhcp"]:
            prob_f.append("%s without a valid DHCP-entry" % (logging_tools.get_plural("machine", num_f["nodhcp"])))
        if num_f["etherboot_invalid"]:
            prob_f.append("%s without a valid etherboot-dir" % (logging_tools.get_plural("machine", num_f["etherboot_invalid"])))
        if num_f["not_reachable"]:
            prob_f.append("%s not reachable" % (logging_tools.get_plural("machine", num_f["not_reachable"])))
        if prob_f:
            sel_table[0][1:col_span] = html_tools.content("Attention ! Found %s !" % (" and ".join(prob_f)), cls="center")
        sel_table[0][1:col_span] = html_tools.content(["Regexp for Groups ", dev_tree.get_devg_re_field(), " and devices ", dev_tree.get_dev_re_field(),
                                                       "\n, ", dev_tree.get_devsel_action_field(), " selection", dev_tree.get_devsel_field()], cls="center")
        select_button = html_tools.submit_button(req, "select")
        submit_button = html_tools.submit_button(req, "submit")
        low_submit = html_tools.checkbox(req, "sub")
        sub = low_submit.check_selection("")
        low_submit[""] = 1
        info_line = ["Verbose: ", verbose_button, ", macboot info: ", bootlog_sel]
        if bootlog_action != "b0":
            info_line.extend(["from ", mbl_list])
        info_line.extend(["\n, ", select_button])
        sel_table[0][1:col_span] = html_tools.content(info_line, cls="center")
        req.write("<form action=\"%s.py?%s\" method=post>%s</form>\n" % (req.module_name,
                                                                         functions.get_sid(req),
                                                                         sel_table("")))
        low_form_str = "<form action=\"%s.py?%s\" method=post>%s%s%s" % (req.module_name,
                                                                         functions.get_sid(req),
                                                                         add_info.create_hidden_var(),
                                                                         verbose_button.create_hidden_var(),
                                                                         bootlog_sel.create_hidden_var())
        dev_ok_desel, dev_warn_desel = ([], [])
        if not d_sel:
            req.write(html_tools.gen_hline("No devices selected%s" % (mbl_info_str), 2))
            req.write(low_form_str)
        else:
            # user log_source idx
            user_log_source_idx = req.log_source.get("user", {"log_source_idx" : 0})["log_source_idx"]
            # not beautifull but saves some space
            req.ulsi = user_log_source_idx
            # init target_states and prod_nets, target_state_lookup_table
            target_states, prod_nets = (html_tools.selection_list(req, "tstate", {}, sort_new_keys=True),
                                        {})
            # device mode
            devmode_dict = {0 : "no check",
                            1 : "auto reboot (sw)",
                            2 : "auto reboot (hw)"}
            device_mode_list = html_tools.selection_list(req, "dm", {}, sort_new_keys=False, auto_reset=True)
            device_mode_list[-1] = "-- keep --"
            for i in xrange(3):
                device_mode_list[i] = devmode_dict[i]
            device_mode_list.mode_is_normal()

            rsync_opt = html_tools.selection_list(req, "rso", {}, sort_new_keys=False)
            rsync_opt[0] = "-- keep --"
            rsync_opt[1] = "disable rsync"
            rsync_opt[2] = "only for install"
            rsync_opt[3] = "always"
            rsync_opt.mode_is_normal()

            glob_rsync_opt = html_tools.selection_list(req, "rso", {}, sort_new_keys=False)
            glob_rsync_opt[0] = "-- keep --"
            glob_rsync_opt[1] = "clear flag"
            glob_rsync_opt[2] = "only for install"
            glob_rsync_opt[3] = "for install and boot"
            glob_rsync_opt.mode_is_normal()
            
            rsync_compressed = html_tools.checkbox(req, "rsc")
            glob_rsync_compressed = html_tools.selection_list(req, "rsog", {}, sort_new_keys=False, auto_reset=1)
            glob_rsync_compressed[0] = "-- keep --"
            glob_rsync_compressed[1] = "enable compression"
            glob_rsync_compressed[2] = "disable compression"
            glob_rsync_c = glob_rsync_compressed.check_selection("", 0)
            
            glob_rsync_enabled = glob_rsync_opt.check_selection("", 0)
            glob_rsync_opt[""] = 0

            glob_device_mode = device_mode_list.check_selection("", -1)
            device_mode_list[""] = -1
            # propagate
            if basic_defs.DEVELOPMENT:
                prop_lut = {0 : "not set",
                            1 : "config",
                            2 : "image",
                            3 : "image and config"}
                prop_opt = html_tools.selection_list(req, "pr", {}, sort_new_keys=False)
                glob_prop_opt = html_tools.selection_list(req, "prg", {}, sort_new_keys=False)
                for prop_idx, prop_info in prop_lut.iteritems():
                    if prop_idx:
                        glob_prop_opt[prop_idx] = prop_info
                        prop_opt[prop_idx] = prop_info
                    else:
                        glob_prop_opt[0] = "-- keep --"
                        prop_opt[0] = "-- nothing --"
                prop_opt.mode_is_normal()
                glob_prop_opt.mode_is_normal()
                glob_propagate = glob_prop_opt.check_selection("", 0)
                glob_prop_opt[""] = 0
            
            target_states.add_pe_key("", "a", "---keep---")
            # get production networks
            req.dc.execute("SELECT nw.network_idx, nw.identifier, nw.name FROM network nw, network_type nt WHERE (nt.identifier='p') AND nw.network_type=nt.network_type_idx")
            for db_rec in req.dc.fetchall():
                prod_nets[db_rec["network_idx"]] = db_rec
                target_states["c_%d" % (db_rec["network_idx"])] = {"name"     : "--- Network %s ---" % (db_rec["identifier"]),
                                                                   "disabled" : 1}
            # get target states
            req.dc.execute("SELECT s.status_idx, s.status, s.prod_link FROM status s ORDER BY prod_link, status")
            # target_state lookup table and inverse table
            ts_lut, ts_inv_lut = ({0 : {}}, {})
            for db_rec in req.dc.fetchall():
                # generate key
                # no production link->key starts with 'a', else with 'b'
                # production link: add prod_link to key
                if db_rec["prod_link"]:
                    for pkey, pstuff in prod_nets.iteritems():
                        #target_states.add_
                        key = "c_%d_%s" % (pkey, db_rec["status"])
                        name = "%s into %s" % (db_rec["status"], pstuff["identifier"])
                        #name = db_rec["status"]
                        target_states[key] = {"name" : name,
                                              "idx"  : db_rec["status_idx"]}
                        ts_lut.setdefault(pkey, {})
                        ts_lut[pkey][db_rec["status_idx"]] = key
                        ts_inv_lut[key] = (pkey, db_rec["status_idx"])
                else:
                    key = "b_%s" % (db_rec["status"])
                    target_states[key] = {"name" : "%s" % (db_rec["status"]),
                                          "idx"  : db_rec["status_idx"]}
                    pkey = 0
                    ts_lut[pkey][db_rec["status_idx"]] = key
                    ts_inv_lut[key] = (pkey, db_rec["status_idx"])
            target_states.mode_is_normal()
            # get kernels
            all_kernels = cdef_kernels.fetch_kernel_tree(req, action_log)
            if "k" in infos_set:
                kernel_par_text_field = html_tools.text_field(req, "kpar", size=128, display_len=64)
                glob_kernel_par = kernel_par_text_field.check_selection("", "")
                all_kernels.build_selection_list()
                kernel_sel_list = all_kernels.selection_list
                glob_kernel = kernel_sel_list.check_selection("", -1)
                stage1_flavour_list = html_tools.selection_list(req, "s1flav", {"lo"     : "ext2 via Loopback",
                                                                                "cramfs" : "CramFS",
                                                                                "cpio"   : "CPIO"})
                stage1_flavour_list.add_pe_key("", "a", "---keep---")
                stage1_flavour_list.mode_is_normal()
                glob_stage1_flavour = stage1_flavour_list.check_selection("", "a")
            if "p" in infos_set:
                part_dict = tools.get_partition_dict(req.dc)
                part_sel_list = html_tools.selection_list(req, "part", {})
                part_sel_list.add_pe_key("", 0, "---keep actual---")
                for p_idx, p_part in part_dict.iteritems():
                    add_dict = {"idx"    : p_part["partition_table_idx"],
                                "name"   : "%s %s%s(%s minimum%s)" % (p_part["name"],
                                                                      (not p_part["valid"] and "[invalid]") or "",
                                                                      p_part["modify_bootloader"] and "[mbl]" or "",
                                                                      (p_part["tot_size"] > 500 and "%.2f GB" % (p_part["tot_size"]/1000.)) or (p_part["tot_size"] and "%d MB" % (p_part["tot_size"]) or "unknown"),
                                                                      (0 and " [%s, %s]" % (logging_tools.get_plural("disc", len(p_part["discs"])),
                                                                                            logging_tools.get_plural("partition", p_part["num_partitions"]))) or ""),
                                "nosort" : 1}
                    if not p_part["valid"]:
                        add_dict["class"] = "error"
                        add_dict["disabled"] = 1
                    part_sel_list[p_idx] = add_dict
                part_sel_list.mode_is_normal()
                glob_part = part_sel_list.check_selection("", 0)
            # images
            image_dict = tools.get_image_dict(req.dc)
            if "i" in infos_set:
                image_sel_list = html_tools.selection_list(req, "image", {}, sort_new_keys=False)
                image_sel_list.add_pe_key("", 0, "---keep actual---")
                all_bcs = set([image["bitcount"] for image in image_dict.itervalues()])
                im_name_lut = dict([(image["name"], key) for key, image in image_dict.iteritems()])
                add_idx = -1
                for act_bc in sorted(all_bcs):
                    add_idx -= 1
                    image_sel_list[add_idx] = {"name"     : "--- %s ---" % ("%d Bit images" % (act_bc) if act_bc else "images with unkown bitcount"),
                                               "disabled" : True,
                                               "class"    : "inverse"}
                    for im_name in sorted(im_name_lut.keys()):
                        im_idx = im_name_lut[im_name]
                        act_im = image_dict[im_idx]
                        if act_im["bitcount"] == act_bc:
                            size = 0
                            if act_im["size_string"]:
                                size = reduce(lambda x, y : x + y, [int(x) for x in act_im["size_string"].split(";") if x.isdigit()]) / 1000.
                            else:
                                size = 0
                            add_dict = {"idx"    : act_im["image_idx"],
                                        "name"   : "%s%s [%s.%s (type %s %s.%s)], %s, %s on %s" % (act_im["build_lock"] and "(*) " or "",
                                                                                                   act_im["name"],
                                                                                                   act_im["version"],
                                                                                                   act_im["release"],
                                                                                                   act_im["sys_vendor"] or "NOT SET",
                                                                                                   act_im["sys_version"] or "NOT SET",
                                                                                                   act_im["sys_release"],
                                                                                                   (size and "%.2f MB" % (size)) or "no size",
                                                                                                   act_im["odate"],
                                                                                                   act_im["build_machine"] or "<unknown>"),
                                        "nosort" : 1}
                            if act_im["build_lock"] or (not act_im["sys_vendor"] or not act_im["sys_release"]):
                                add_dict["class"] = "error"
                            image_sel_list[im_idx] = add_dict
                image_sel_list.mode_is_normal()
                glob_image = image_sel_list.check_selection("", 0)
            # init structures if needed
            if "c" in infos_set:
                comment_text_field = html_tools.text_field(req, "comment", size=32, display_len=32)
                glob_comment = comment_text_field.check_selection("", "")
                new_log_entry_field = html_tools.text_field(req, "log", size=127, display_len=40)
                glob_log_entry = new_log_entry_field.check_selection("", "")
            # always initialise the mac_address_field
            mac_address_field = html_tools.text_field(req, "mac", size=17, display_len=17)
            mac_action_list = html_tools.selection_list(req, "maca", {"a" : "keep",
                                                                      "b" : "alter",
                                                                      "c" : "clear"}, auto_reset=1)
            if "m" in infos_set:
                glob_mac_action = mac_action_list.check_selection("", "a")
                mac_driver_field  = html_tools.text_field(req, "md", size=32, display_len=17)
                glob_mac_address = mac_address_field.check_selection("", "")
                glob_mac_driver = mac_driver_field.check_selection("", "")
                write_mac_action_list = html_tools.selection_list(req, "macl", {"b" : "write DHCP address",
                                                                                "c" : "do not write DHCP address"},
                                                                  initial_mode="n")
                write_mac_action_list.add_pe_key("", "a", "keep")
                wf_action_list = html_tools.selection_list(req, "macw", {}, auto_reset = 1)
                glob_write_mac_action = write_mac_action_list.check_selection("", "a")
                greedy_action_list = html_tools.selection_list(req, "greedy", {"a" : "keep",
                                                                               "b" : {"name" : "enable" , "greedy" : 1},
                                                                               "c" : {"name" : "disable", "greedy" : 0}}, auto_reset=1)
                greedy_action_list.mode_is_normal()
                glob_greedy_action = greedy_action_list.check_selection("", "a")
                glob_mac_tuple = (glob_mac_action, glob_mac_address, glob_greedy_action, glob_write_mac_action, glob_mac_driver)
            else:
                # default value
                glob_mac_tuple = ()
                write_mac_action_list, greedy_action_list, mac_driver_field = (None, None, None)
            # lookup-table for flags
            flags_lut = {"t" : "refresh_tk",
                         "a" : "apc_com",
                         "m" : "alter_macadr",
                         "p" : "propagate",
                         "d" : "device_mode_change"}
            # flag action dict
            flag_action_dict = {}
            # action dict (ping, reboot, halt, poweroff)
            action_dict = {}
            # device selection string
            d_sel_str = " OR ".join(["d.device_idx=%d" % (x) for x in d_sel])
            d_sel_str2 = " OR ".join(["d.device=%d" % (x) for x in d_sel])
            # list of devices where we have to check the dhcp_flags
            dhcp_post_check = []
            # get devices
            req.dc.execute("SELECT d.name, dg.name AS dgname, d.device_group, dt.identifier, d.xen_guest, d.device_idx, d.bootnetdevice, d.bootserver, d.device_type, ms.device, ms.outlet, ms.state, ms.slave_info, d.newstate, d.rsync, d.device_mode, d.rsync_compressed, d.prod_link, d.comment, d.newkernel, " + \
                           "d.new_kernel, d.actkernel, d.act_kernel, d.act_kernel_build, d.kernelversion, d.kernel_append, d.stage1_flavour, d.partition_table, d.act_partition_table, d.newimage, d.new_image, d.actimage, d.act_image, d.imageversion, dg.device_group_idx, d.propagation_level FROM " + \
                           "device_group dg, device_type dt, device d LEFT JOIN msoutlet ms ON ms.slave_device=d.device_idx WHERE d.device_group = dg.device_group_idx AND d.device_type=dt.device_type_idx AND (%s)" % (d_sel_str))
            dev_dict = {}
            for db_rec in req.dc.fetchall():
                act_action = None
                if not dev_dict.has_key(db_rec["device_idx"]):
                    dev_struct = dev_tree.get_dev_struct(db_rec["device_idx"])
                    act_dev = cdef_device.device(db_rec["name"], db_rec["device_idx"], db_rec["device_group"], db_rec["device_type"])
                    act_dev.set_bootnetdevice(db_rec["bootnetdevice"])
                    act_dev.set_comment(db_rec["comment"])
                    act_dev.set_xen_device(db_rec["xen_guest"])
                    act_dev.set_kernel_info(db_rec["newkernel"], db_rec["new_kernel"], db_rec["actkernel"], db_rec["act_kernel"], db_rec["act_kernel_build"], db_rec["kernelversion"], db_rec["kernel_append"], db_rec["stage1_flavour"])
                    act_dev.set_partition_info(db_rec["partition_table"], db_rec["act_partition_table"])
                    act_dev.set_image_info(db_rec["newimage"], db_rec["new_image"], db_rec["actimage"], db_rec["act_image"], db_rec["imageversion"])
                    act_dev.set_mac_info(dev_struct["devname"], dev_struct["macadr"], dev_struct["dhcp_mac"], dev_struct["driver"], dev_struct["driver_options"], dev_struct["netdevice_idx"])
                    act_dev.set_dhcp_info(dev_struct["dhcp_write"], dev_struct["dhcp_written"], dev_struct["dhcp_error"], dev_struct["dhcp_mac"])
                    dev_dict[db_rec["device_idx"]] = act_dev
                    act_dev.device_mode = db_rec["device_mode"]
                    # set as default
                    act_dev.act_values_are_default()
                    # determine action for this device
                    act_action = prhp_list.check_selection(act_dev.get_suffix(), "a0")
                    if act_action == "a0":
                        act_action = glob_prhp_action
                    # set bootserver (if given)
                    act_bs = db_rec["bootserver"]
                    if act_bs:
                        act_dev.set_bootserver(act_bs)
                        action_dict.setdefault(act_bs, {})
                        if act_action:
                            action_dict[act_bs][db_rec["device_idx"]] = act_action
                    #print "aa", act_action, "<br>"
                    # copy rsync settings
                    rsync_enabled, rsync_c = (db_rec["rsync"], db_rec["rsync_compressed"])
                    act_dev.rsync, act_dev.rsync_compressed = (rsync_enabled, rsync_c)
                    # sect actual targe state:
                    act_ts = ts_lut.get(db_rec["prod_link"], {}).get(db_rec["newstate"], None)
                    if not act_ts:
                        act_ts = target_states.get_sort_list()
                    # check for target state
                    if "b" in infos_set:
                        # check device_mode
                        act_dev_mode = act_dev.device_mode
                        new_dev_mode = device_mode_list.check_selection(act_dev.get_suffix(), -1)
                        if glob_device_mode != -1:
                            new_dev_mode = glob_device_mode
                        if new_dev_mode >= 0 and act_dev_mode != new_dev_mode:
                            device_mode_list[act_dev.get_suffix()] = new_dev_mode
                            act_dev_mode = new_dev_mode
                            act_dev.add_sql_changes({"device_mode" : act_dev_mode})
                            act_dev.add_log_entry(req.ulsi,
                                                  req.user_info.get_idx(),
                                                  req.log_status.get("i", {"log_status_idx" : 0})["log_status_idx"],
                                                  "setting device_mode to '%s'" % (devmode_dict[act_dev_mode]))
                            act_dev.add_device_flag("d")
                        act_dev.device_mode = act_dev_mode
                        # check rsync
                        new_rsync = rsync_opt.check_selection(act_dev.get_suffix(), 0)
                        if sub:
                            new_rsync_c = rsync_compressed.check_selection(act_dev.get_suffix())
                        else:
                            new_rsync_c = rsync_compressed.check_selection(act_dev.get_suffix(), act_dev.rsync_compressed)
                        rsync_opt[act_dev.get_suffix()] = 0
                        new_rsync_c = {0 : new_rsync_c, 1 : 1, 2 : 0}[glob_rsync_c]
                        new_rsync   = {0 : glob_rsync_enabled}.get(new_rsync, new_rsync)
                        if new_rsync:
                            new_rsync_value = {1 : 0, 2 : 1, 3 : 2}[new_rsync]
                            act_dev.rsync = new_rsync_value
                            act_dev.add_sql_changes({"rsync" : new_rsync_value})
                            act_dev.add_log_entry(req.ulsi,
                                                  req.user_info.get_idx(),
                                                  req.log_status.get("i", {"log_status_idx" : 0})["log_status_idx"],
                                                  "setting rsync_opt to '%s'" % ({0 : "off",
                                                                                  1 : "on for install",
                                                                                  2 : "always"}[new_rsync_value]))
                            act_dev.add_device_flag("t")
                        if new_rsync_c != act_dev.rsync_compressed:
                            rsync_compressed[act_dev.get_suffix()] = new_rsync_c
                            act_dev.rsync_compressed = new_rsync_c
                            act_dev.add_sql_changes({"rsync_compressed" : new_rsync_c})
                            act_dev.add_log_entry(req.ulsi,
                                                  req.user_info.get_idx(),
                                                  req.log_status.get("i", {"log_status_idx" : 0})["log_status_idx"],
                                                  "%s rsync_compression" % ({0 : "disabling",
                                                                             1 : "enabling"}[new_rsync_c]))
                            act_dev.add_device_flag("t")
                        # check propagation
                        if basic_defs.DEVELOPMENT:
                            act_prop = db_rec["propagation_level"]
                            new_prop = prop_opt.check_selection(act_dev.get_suffix(), act_prop)
                            #prop_opt[act_dev.get_suffix()] = None
                            act_dev.propagation_level = act_prop
                            if glob_propagate:
                                new_prop = glob_propagate
                                prop_opt[act_dev.get_suffix()] = new_prop
                            if new_prop != act_prop:
                                act_dev.propagation_level = new_prop
                                act_dev.add_sql_changes({"propagation_level" : new_prop})
                                act_dev.add_log_entry(req.ulsi,
                                                      req.user_info.get_idx(),
                                                      req.log_status.get("i", {"log_status_idx" : 0})["log_status_idx"],
                                                      "setting propagation level to '%s'" % (prop_lut[new_prop]))
                                act_dev.add_device_flag("p")
                        # check new target state
                        glob_target_state = target_states.check_selection("", "a")#, ("a", None), 1)
                        new_ts = target_states.check_selection(act_dev.get_suffix(), act_ts)#
                        if new_ts == act_ts and glob_target_state != "a":
                            new_ts = glob_target_state
                            target_states[act_dev.get_suffix()] = new_ts
                        if new_ts != act_ts and new_ts:
                            if ts_inv_lut.has_key(new_ts):
                                act_dev.add_sql_changes({"newstate"  : ts_inv_lut[new_ts][1],
                                                         "prod_link" : ts_inv_lut[new_ts][0]})
                                target_states.mode_is_setup()
                                act_dev.add_log_entry(req.ulsi,
                                                      req.user_info.get_idx(),
                                                      req.log_status.get("i", {"log_status_idx" : 0})["log_status_idx"],
                                                      "setting target_state to '%s'" % (target_states[new_ts]["name"]))
                                target_states.mode_is_normal()
                                act_dev.add_device_flag("t")
                    # override if halt / poweroff
                    if act_action in ["a2", "a3"]:
                        act_dev.device_mode = 0
                        device_mode_list[act_dev.get_suffix()] = 0
                        act_dev.add_sql_changes({"device_mode" : 0})
                        act_dev.add_log_entry(req.ulsi,
                                              req.user_info.get_idx(),
                                              req.log_status.get("i", {"log_status_idx" : 0})["log_status_idx"],
                                              "setting device_mode to '%s' (because of command)" % (devmode_dict[0]))
                        act_dev.add_device_flag("d")
                    # check for additional flags
                    if "k" in infos_set:
                        act_new_kernel = act_dev.get_new_kernel_idx(all_kernels)
                        new_kernel = kernel_sel_list.check_selection(act_dev.get_suffix(), act_new_kernel)
                        if new_kernel == act_new_kernel and glob_kernel >= 0:
                            new_kernel = glob_kernel
                            #, (act_new_kernel, glob_kernel))
                        if act_new_kernel != new_kernel:
                            act_dev.set_new_kernel_idx(new_kernel, all_kernels)
                            kernel_sel_list[act_dev.get_suffix()] = new_kernel
                            act_dev.add_log_entry(req.ulsi,
                                                  req.user_info.get_idx(),
                                                  req.log_status.get("i", {"log_status_idx" : 0})["log_status_idx"],
                                                  new_kernel and "setting new_kernel to '%s' (version %s.%s)" % (all_kernels[act_dev.new_kernel_idx]["name"],
                                                                                                                 all_kernels[act_dev.new_kernel_idx]["version"],
                                                                                                                 all_kernels[act_dev.new_kernel_idx]["release"]) or "clearing new_kernel")
                        act_stage1_flavour = act_dev.get_stage1_flavour()
                        new_stage1_flavour = stage1_flavour_list.check_selection(act_dev.get_suffix(), act_stage1_flavour or "lo")
                        if new_stage1_flavour == act_stage1_flavour and glob_stage1_flavour != "a":
                            new_stage1_flavour = glob_stage1_flavour
                        if act_stage1_flavour != new_stage1_flavour:
                            act_dev.set_stage1_flavour(new_stage1_flavour)
                            stage1_flavour_list[act_dev.get_suffix()] = new_stage1_flavour
                            act_dev.add_log_entry(req.ulsi,
                                                  req.user_info.get_idx(),
                                                  req.log_status.get("i", {"log_status_idx" : 0})["log_status_idx"],
                                                  new_kernel and "setting stage1_flavour to '%s'" % (new_stage1_flavour))
                        act_kernel_par = act_dev.get_kernel_parameter()
                        new_kernel_par = kernel_par_text_field.check_selection(act_dev.get_suffix(), act_kernel_par)
                        if new_kernel_par == act_kernel_par and glob_kernel_par:
                            new_kernel_par = glob_kernel_par
                        if new_kernel_par != act_kernel_par:
                            kernel_par_text_field[act_dev.get_suffix()] = new_kernel_par
                            act_dev.add_sql_changes({"kernel_append" : new_kernel_par})
                            if new_kernel_par:
                                log_str = "set kernel_parameter to '%s'" % (new_kernel_par)
                            else:
                                log_str = "cleared kernel_parameter"
                            act_dev.add_log_entry(req.ulsi,
                                                  req.user_info.get_idx(),
                                                  req.log_status.get("i", {"log_status_idx" : 0})["log_status_idx"],
                                                  log_str)
                            act_dev.add_device_flag("t")
                            #print "****", new_kernel_par, act_kernel_par, "**<br>"
                        #print "tss : ", act_ts, new_ts, act_dev.name, target_states[new_ts]["idx"],ts_inv_lut[new_ts],"<br>"
                    if "p" in infos_set:
                        act_new_part = act_dev.get_new_partition_idx(part_dict)
                        new_part = part_sel_list.check_selection(act_dev.get_suffix(), act_new_part)
                        if new_part == act_new_part and glob_part:
                            new_part = glob_part
                        if new_part != act_new_part:
                            part_sel_list[act_dev.get_suffix()] = new_part
                            act_dev.new_partition_idx = new_part
                            act_dev.add_sql_changes({"partition_table" : act_dev.new_partition_idx})
                            act_dev.add_log_entry(req.ulsi,
                                                  req.user_info.get_idx(),
                                                  req.log_status.get("i", {"log_status_idx" : 0})["log_status_idx"],
                                                  "setting new_partition to '%s'" % (part_dict[act_dev.new_partition_idx]["name"]))

                    if "i" in infos_set:
                        act_new_image = act_dev.get_new_image_idx(image_dict)
                        new_image = image_sel_list.check_selection(act_dev.get_suffix(), act_new_image)
                        if new_image == act_new_image and glob_image:
                            new_image = glob_image
                        if new_image != act_new_image:
                            image_sel_list[act_dev.get_suffix()] = new_image
                            new_image_s = image_dict[new_image]
                            act_dev.set_new_image(new_image, new_image_s["name"])
                            act_dev.add_log_entry(req.ulsi,
                                                  req.user_info.get_idx(),
                                                  req.log_status.get("i", {"log_status_idx" : 0})["log_status_idx"],
                                                  "setting new_image to '%s' (version %s.%s)" % (new_image_s["name"],
                                                                                                 new_image_s["version"],
                                                                                                 new_image_s["release"]))
                        else:
                            act_dev.check_image_idx(image_dict)
                    handle_mac_changes(req, act_dev, infos_set, action_log, flags_lut,
                                       (mac_action_list, mac_address_field, write_mac_action_list, greedy_action_list, mac_driver_field),
                                       glob_mac_tuple)
                    if "c" in infos_set:
                        handle_comment_changes(req, act_dev, infos_set, action_log,
                                               (comment_text_field, new_log_entry_field),
                                               (glob_comment, glob_log_entry))
            apc_devs, apc_dict, ibc_devs, ibc_dict = ([], {}, [], {})
            apc_com_list, ibc_com_list = ("", "")
            # fetch apc-info
            req.dc.execute("SELECT d.name, d.device_idx, ms.device, ms.outlet, ms.state, ms.slave_info FROM device d, msoutlet ms WHERE ms.slave_device=d.device_idx AND (%s)" % (d_sel_str))
            for db_rec in req.dc.fetchall():
                dev_dict[db_rec["device_idx"]].add_apc_connection(db_rec["device"], db_rec["outlet"], db_rec["state"], db_rec["slave_info"])
                if not db_rec["device"] in apc_devs:
                    apc_devs.append(db_rec["device"])
            # fetch ibc-info
            req.dc.execute("SELECT d.name, d.device_idx, i.device, i.blade, i.state, i.slave_info FROM device d, ibc_connection i WHERE i.slave_device=d.device_idx AND (%s)" % (d_sel_str))
            for db_rec in req.dc.fetchall():
                dev_dict[db_rec["device_idx"]].add_ibc_connection(db_rec["device"], db_rec["blade"], db_rec["state"], db_rec["slave_info"])
                if not db_rec["device"] in ibc_devs:
                    ibc_devs.append(db_rec["device"])
            for dev_idx, act_dev in dev_dict.iteritems():
                dev_bs = act_dev.get_bootserver()
                if dev_bs:
                    for flag in act_dev.get_device_flags():
                        flag_action_dict.setdefault(dev_bs, {}).setdefault(flag, []).append(act_dev.get_name())
                act_dev.commit_sql_changes(req.dc)
            #print "<br>", dev_idx, act_dev.get_device_flags(), act_dev.get_sql_changes(), "<br>"
            # fetch APCs
            if apc_devs:
                # init apc list
                apc_com_list = None
                req.dc.execute("SELECT d.name, d.device_idx, d.device_group, d.device_type, d.bootserver, ms.* FROM device d LEFT JOIN msoutlet ms ON ms.device = d.device_idx WHERE (%s)" % (" OR ".join(["d.device_idx=%d" % (x) for x in apc_devs])))
                for db_rec in req.dc.fetchall():
                    apc_idx = db_rec["device_idx"]
                    if not apc_dict.has_key(apc_idx):
                        act_apc = cdef_device.apc(db_rec["name"], db_rec["device_idx"], db_rec["device_group"], db_rec["device_type"])
                        apc_dict[apc_idx] = act_apc
                        act_bs = db_rec["bootserver"]
                        if act_bs:
                            act_apc.set_bootserver(act_bs)
                        if not apc_com_list:
                            apc_com_list = act_apc.get_apc_com_list(req, html_tools)
                            glob_action = apc_com_list.check_selection("", 0)
                    else:
                        act_apc = apc_dict[apc_idx]
                    if db_rec["outlet"]:
                        act_apc.add_outlet(db_rec["outlet"], db_rec)
                        if dev_dict.has_key(db_rec["slave_device"]):
                            act_pf = dev_dict[db_rec["slave_device"]].get_outlet_suffix(db_rec["device"], db_rec["outlet"])
                            apc_command = apc_com_list.check_selection(act_pf, 0)
                            if not apc_command and glob_action:
                                apc_command = glob_action
                                apc_com_list[act_pf] = apc_command
                            if apc_command:
                                act_dev = dev_dict[db_rec["slave_device"]]
                                if apc_command in [2, 6] and act_dev.device_mode in [1, 2]:
                                    act_dev.device_mode = 0
                                    device_mode_list[act_dev.get_suffix()] = 0
                                    act_dev.add_sql_changes({"device_mode" : 0})
                                    act_dev.add_log_entry(req.ulsi,
                                                          req.user_info.get_idx(),
                                                          req.log_status.get("i", {"log_status_idx" : 0})["log_status_idx"],
                                                          "setting device_mode to '%s' (because of apc_command)" % (devmode_dict[0]))
                                    act_dev.add_device_flag("d")
                                act_apc.add_outlet_command(db_rec["outlet"], apc_command)
                                dev_dict[db_rec["slave_device"]].add_log_entry(req.ulsi,
                                                                               req.user_info.get_idx(),
                                                                               req.log_status.get("i", {"log_status_idx" : 0})["log_status_idx"],
                                                                               act_apc.get_log_str(db_rec["outlet"], apc_command))
                                #print apc_command, x["outlet"], act_apc.name, "*********<br>"
                for act_apc in apc_dict.itervalues():
                    act_bs, act_com_str = (act_apc.get_bootserver(), act_apc.get_command_str())
                    if act_bs and act_com_str:
                        flag_action_dict.setdefault(act_bs, {}).setdefault("a", {})[act_apc.get_name()] = act_com_str
                        #print "*", act_apc.get_command_str(), "*<br>"
            # fetch IBCs
            if ibc_devs:
                # init apc list
                ibc_com_list = None
                req.dc.execute("SELECT d.name, d.device_idx, d.device_group, d.device_type, d.bootserver, i.* FROM device d LEFT JOIN ibc_connection i ON i.device = d.device_idx WHERE (%s)" % (" OR ".join(["d.device_idx=%d" % (x) for x in ibc_devs])))
                for db_rec in req.dc.fetchall():
                    ibc_idx = db_rec["device_idx"]
                    if not ibc_dict.has_key(ibc_idx):
                        act_ibc = cdef_device.ibc(db_rec["name"], db_rec["device_idx"], db_rec["device_group"], db_rec["device_type"])
                        ibc_dict[ibc_idx] = act_ibc
                        act_bs = db_rec["bootserver"]
                        if act_bs:
                            act_ibc.set_bootserver(act_bs)
                        if not ibc_com_list:
                            ibc_com_list = act_ibc.get_ibc_com_list(req, html_tools)
                            glob_action = ibc_com_list.check_selection("", 0)
                    else:
                        act_ibc = ibc_dict[ibc_idx]
                    if db_rec["blade"]:
                        act_ibc.add_blade(db_rec["blade"], db_rec)
                        if dev_dict.has_key(db_rec["slave_device"]):
                            act_pf = dev_dict[db_rec["slave_device"]].get_outlet_suffix(db_rec["device"], db_rec["blade"])
                            ibc_command = ibc_com_list.check_selection(act_pf, 0)
                            if not ibc_command and glob_action:
                                ibc_command = glob_action
                                ibc_com_list[act_pf] = ibc_command
                            if ibc_command:
                                act_dev = dev_dict[db_rec["slave_device"]]
                                if ibc_command in [2] and act_dev.device_mode in [1, 2]:
                                    act_dev.device_mode = 0
                                    device_mode_list[act_dev.get_suffix()] = 0
                                    act_dev.add_sql_changes({"device_mode" : 0})
                                    act_dev.add_log_entry(req.ulsi,
                                                          req.user_info.get_idx(),
                                                          req.log_status.get("i", {"log_status_idx" : 0})["log_status_idx"],
                                                          "setting device_mode to '%s' (because of ibc_command)" % (devmode_dict[0]))
                                    act_dev.add_device_flag("d")
                                act_ibc.add_blade_command(db_rec["blade"], ibc_command)
                                dev_dict[db_rec["slave_device"]].add_log_entry(req.ulsi,
                                                                               req.user_info.get_idx(),
                                                                               req.log_status.get("i", {"log_status_idx" : 0})["log_status_idx"],
                                                                               act_ibc.get_log_str(db_rec["blade"], ibc_command))
                                #print apc_command, x["outlet"], act_apc.name, "*********<br>"
                for act_ibc in ibc_dict.itervalues():
                    act_bs, act_com_str = (act_ibc.get_bootserver(), act_ibc.get_command_str())
                    if act_bs and act_com_str:
                        flag_action_dict.setdefault(act_bs, {}).setdefault("a", {})[act_ibc.get_name()] = act_com_str
                        #print "*", act_ibc.get_command_str(), "*"
            ss_list = []
            # iterate over action_dict
            for short, stuff in prhp_list.list_dict.iteritems():
                for server, targets in [(bootserver_dict[y], x) for y, x in action_dict.iteritems() if short in x.values()]:
                    act_targets = [dev_tree.get_dev_name(x) for x, y in targets.iteritems() if y == short]
                    #print "<br>", short, server, act_targets
                    ss_list.append(tools.s_command(req, "mother_server", 8001, stuff["action"], act_targets, 10, server))
            post_commands = []
            # iterate over flag dict
            for bs_idx, flag_dict in flag_action_dict.iteritems():
                for flag, targets in flag_dict.iteritems():
                    #print "<br>", "mother_server", 8001, flags_lut[flag], " : ".join(targets), 10, bootserver_dict[bs_idx]["name"]
                    #print targets
                    post_commands.append(tools.s_command(req, "mother_server", 8001, flags_lut[flag], targets, 10, bootserver_dict[bs_idx]))
            tools.iterate_s_commands(ss_list, scon_logs)
            for ss in ss_list:
                #print ss.server_reply.get_node_results()
                if ss.server_reply:
                    for key, value in ss.server_reply.get_node_results().iteritems():
                        dev_dict[dev_tree.get_dev_idx(key)].set_act_state(value)
            tools.iterate_s_commands(post_commands, scon_logs)
            # readdots cycle
            rd_list = []
            for server, targets in [(bootserver_dict[y], x) for y, x in action_dict.iteritems()]:
                act_targets = [dev_tree.get_dev_name(x) for x, y in targets.iteritems()]
                rd_list.append(tools.s_command(req, "mother_server", 8001, "readdots", act_targets, 10, server))
            tools.iterate_s_commands(rd_list, scon_logs)
            if dhcp_post_check:
                req.dc.execute("SELECT d.device_idx, d.dhcp_write, d.dhcp_written, d.dhcp_error, n.macadr FROM device d, netdevice n WHERE n.netdevice_idx = d.bootnetdevice AND (%s)" % (" OR ".join(["d.device_idx=%d" % (x) for x in dhcp_post_check])))
                for db_rec in req.dc.fetchall():
                    act_dev = dev_dict[db_rec["device_idx"]]
                    act_dev.set_dhcp_info(db_rec["dhcp_write"], db_rec["dhcp_written"], db_rec["dhcp_error"])
                    act_dev.set_mac_address(db_rec["macadr"])
                    mac_address_field[act_dev.get_suffix()] = db_rec["macadr"]
            if scon_logs:
                req.write(scon_logs.generate_stack("Server connection log"))
            req.write(action_log.generate_stack("Log"))
            # save device logs
            log_entries = sum([dev.get_log_entries() for dev in dev_dict.itervalues()], [])
            if log_entries:
                form_str = ",".join([x for x, y in log_entries])
                form_data = tuple(sum([list(y) for x, y in log_entries], []))
                req.dc.execute("INSERT INTO devicelog VALUES%s" % (form_str), form_data)
            if "l" in infos_set:
                user_dict = tools.get_user_list(req.dc, [], True)
            # fetch device states
            req.dc.execute("SELECT d.device_idx, d.reqstate, d.recvstate FROM device d WHERE (%s)" % (d_sel_str))
            for db_rec in req.dc.fetchall():
                dev_dict[db_rec["device_idx"]].set_req_recv_state(db_rec["reqstate"], db_rec["recvstate"])
            out_str = "%s%s" % (html_tools.gen_hline("Selected %s in %s%s" % (logging_tools.get_plural("device", len(d_sel)),
                                                                              logging_tools.get_plural("devicegroup", len(dg_sel_eff)),
                                                                              mbl_info_str),
                                                     2),
                                low_form_str)
            num_apc_cons, num_ibc_cons = (0, 0)
            sel_table = html_tools.html_table(cls="normal")
            out_str += sel_table.get_header()
            req.write(out_str)
            for dg in dg_sel_eff:
                sel_table[1][1:8] = html_tools.content(dev_tree.get_sel_dev_str(dg), cls="devgroup")
                req.write(sel_table.flush_lines())
                for dev in [x for x in d_sel if x in dev_tree.get_sorted_dev_idx_list(dg)]:
                    act_dev = dev_dict[dev]
                    act_ds = dev_tree.get_dev_struct(dev)
                    if act_ds["error_str"]:
                        sel_table[0][2:8] = html_tools.content(act_ds["error_str"])
                    if "a" in infos_set:
                        if act_dev.apc_cons:
                            num_apc_cons += 1
                        elif act_dev.ibc_cons:
                            num_ibc_cons += 1
                    sel_table[0][2] = html_tools.content(prhp_list, cls="centersmall")
                    sel_table[None][0] = html_tools.content(prhp_list, cls="centersmall")
                    sel_table[None][0] = html_tools.content(prhp_list, cls="centersmall")
                    sel_table[None][0] = html_tools.content(prhp_list, cls="centersmall")
                    sel_table[None][0] = html_tools.content(act_dev.get_connection_info(apc_dict, ibc_dict), cls="left")
                    # check for deselection
                    #print "* %s * %s * %s * %s *" % (act_dev.get_act_state(), act_dev.get_recv_state(), act_dev.get_req_state(), act_dev.up_state)
                    if act_dev.get_act_state() == act_dev.get_recv_state() and act_dev.get_act_state() == act_dev.get_req_state() and act_dev.get_act_state().startswith("up to ") and act_dev.up_state == 1:
                        dev_ok_desel.append(dev)
                        act_state = "o"
                    elif act_dev.up_state == 2:
                        dev_warn_desel.append(dev)
                        act_state = "w"
                    else:
                        act_state = "e"
                    sel_table[None][0] = html_tools.content("info: %s" % (act_dev.get_act_state()), cls="left")
##                     sel_table[None][0] = html_tools.content("info: %s (%s)" % (act_dev.get_act_state(), act_state), cls="left")
                    sel_table[None][0] = html_tools.content(act_dev.get_act_net()   , cls="center")
                    
                    new_kernel = all_kernels.get(act_dev.new_kernel_idx, {})
                    new_kernel_bc = new_kernel.get("bitcount", 0)
                    new_image_bc = image_dict.get(act_dev.new_image_idx, {}).get("bitcount", 0)
                    # error lines
                    error_lines = {}#"bitcount" : 0,
                                   #"xen"      : 0}
                    if "b" in infos_set:
                        if basic_defs.DEVELOPMENT:
                            opt_list = ["tstate: ", target_states,
                                        ", rsync mode is %s, " % ({0 : "cleared",
                                                                   1 : "rsync for install",
                                                                   2 : "rsync always"}[act_dev.rsync]),
                                        rsync_opt,
                                        ", compressed transfer: ",
                                        rsync_compressed,
                                        ", propagation level: ",
                                        prop_opt,
                                        ", device_mode is %s, " % (devmode_dict[act_dev.device_mode]),
                                        device_mode_list]
                        else:
                            opt_list = ["tstate: ", target_states,
                                        ", rsync mode is %s, " % ({0 : "cleared",
                                                                   1 : "rsync for install",
                                                                   2 : "rsync always"}[act_dev.rsync]),
                                        rsync_opt,
                                        ", compressed transfer: ",
                                        rsync_compressed,
                                        ", device_mode is %s, " % (devmode_dict[act_dev.device_mode]),
                                        device_mode_list]
                        sel_table[0][2:8]    = html_tools.content(opt_list, cls="left")
                        if act_dev.get_recv_state() != act_dev.get_req_state() or act_dev.get_act_state() != act_dev.get_recv_state():
                            sel_table[0][2:5]    = html_tools.content("recv: %s" % (act_dev.get_recv_state()), cls="left")
                            sel_table[None][0:3] = html_tools.content("req: %s" % (act_dev.get_req_state())  , cls="left")
                    if not act_dev.rsync:
                        f_build = image_dict.get(act_dev.new_image_idx, {}).get("full_build", -1)
                        err_line = {0 : "last build was not a full build",
                                    -1 : "last build type was unknown"}.get(f_build, "")
                        if err_line:
                            sel_table[0][2:8] = html_tools.content("Image error: %s" % (err_line), cls="left")
                            error_lines["image_bt"] = sel_table.get_line_num()
                    #error_lines["image"] = 
                    if "a" in infos_set and (act_dev.apc_cons or act_dev.ibc_cons):
                        out_f = []
                        for apc_idx, outlet, state, info in act_dev.apc_cons:
                            apc_com_list[act_dev.get_outlet_suffix(apc_idx, outlet)] = None
                            out_f.extend(["%s/%d, state: %s, command:" % (apc_dict[apc_idx].get_name(),
                                                                          outlet,
                                                                          state),
                                          html_tools.content(apc_com_list, act_dev.get_outlet_suffix(apc_idx, outlet))])
                        for ibc_idx, blade, state, info in act_dev.ibc_cons:
                            ibc_com_list[act_dev.get_outlet_suffix(ibc_idx, blade)] = None
                            out_f.extend(["%s/%d, state: %s, command:" % (ibc_dict[ibc_idx].get_name(),
                                                                          blade,
                                                                          state),
                                          html_tools.content(ibc_com_list, act_dev.get_outlet_suffix(ibc_idx, blade))])
                        sel_table[0][2:8] = html_tools.content(out_f, cls="left")
                    if "k" in infos_set:
                        sel_table[0][2:8] = html_tools.content(["Kernel:", kernel_sel_list, ", stage1 flavour:", stage1_flavour_list, ", actual: %s" % (act_dev.get_act_kernel_str(all_kernels))])
                        sel_table[0][2:8] = html_tools.content(["Kernel parameter:", kernel_par_text_field])
                    if act_dev.get_xen_device():
                        if not new_kernel.get("xen_guest_kernel", False):
                            sel_table[0][2:8] = html_tools.content("XEN error: is xen_guest but kernel is no XEN-guest-kernel", cls="left")
                            error_lines["xen"] = sel_table.get_line_num()
                    if "i" in infos_set:
                        sel_table[0][2:8] = html_tools.content(["Image:",
                                                                image_sel_list,
                                                                ", actual: %s" % (act_dev.get_act_image_str(image_dict))])
                    if not new_kernel_bc or new_kernel_bc != new_image_bc:
                        sel_table[0][2:8] = html_tools.content("Bitcount error: Kernel is %s, image is %s" % ("%d Bit" % (new_kernel_bc) if new_kernel_bc else "unknown",
                                                                                                              "%d Bit" % (new_image_bc) if new_image_bc else "unknown"), cls="left")
                        error_lines["bitcount"] = sel_table.get_line_num()
                    if "p" in infos_set:
                        sel_table[0][2:8] = html_tools.content(["Partition:",
                                                                part_sel_list,
                                                                "actual: %s" % (act_dev.get_act_partition_str(part_dict))])
                    if "m" in infos_set:
                        greedy_action_list[act_dev.get_suffix()] = None
                        sel_table[0][2:6]    = html_tools.content(["MacAddress:",
                                                                   mac_address_field, " (", mac_action_list,
                                                                   ") on %s, driver:" % (act_dev.get_netdevice_name()),
                                                                   mac_driver_field,
                                                                   ", ",write_mac_action_list])
                        sel_table[None][0:2] = html_tools.content([act_dev.get_greedy_info(),  greedy_action_list])
                        if not act_dev.dhcp_info_is_ok():
                            sel_table[0][2:8] = html_tools.content([act_dev.get_dhcp_info()])
                    if "c" in infos_set:
                        new_log_entry_field[act_dev.get_suffix()] = ""
                        sel_table[0][2:6]    = html_tools.content(["Comment:", comment_text_field])
                        sel_table[None][0 : 2] = html_tools.content(["New log entry:", new_log_entry_field])
                    if "l" in infos_set:
                        sel_table[0][2:8] = html_tools.content(fetchdevlog.show_device_history(req, act_dev.idx, user_dict, verbose=is_verbose, max_lines=MAX_DEVLOG_LEN), cls="center", beautify = 0)
                    if "s" in infos_set:
                        sel_table[0][2:8] = html_tools.content(show_device_syslog(req, act_dev, is_verbose), cls="center", beautify = 0)
                    act_line = sel_table.get_cursor()[0]
                    sel_table[1:act_line]["class"] = {-1 : "devunknown",
                                                      0  : "devdown",
                                                      1  : "devup",
                                                      2  : "devwarn"}[act_dev.up_state]
                    for value in error_lines.itervalues():
                        if value:
                            sel_table[value]["class"] = "devdown"
                    sel_table[1:act_line][1] = html_tools.content(act_dev.get_name(), cls="left")
                    req.write(sel_table.flush_lines(act_dev.get_suffix()))
            req.write(sel_table.get_footer())
            if len(d_sel) > 1:
                sel_table = html_tools.html_table(cls="normalsmall")
                target_states[""] = None
                sel_table[0][0]    = html_tools.content("control:"              , cls="right")
                sel_table[None][0] = html_tools.content(prhp_list               , radio_suffix="p", cls="centersmall")
                sel_table[None][0] = html_tools.content(prhp_list, cls="centersmall")
                sel_table[None][0] = html_tools.content(prhp_list, cls="centersmall")
                sel_table[None][0] = html_tools.content(prhp_list, cls="left")
                if "b" in infos_set:
                    sel_table[0][0]        = html_tools.content("Target state:", cls="right")
                    sel_table[None][0 : 4] = html_tools.content(target_states, cls="left")
                    sel_table[0][0]        = html_tools.content("RSync mode:", cls="right")
                    sel_table[None][0 : 4] = html_tools.content([glob_rsync_opt,
                                                                 ", compression: ",
                                                                 glob_rsync_compressed], cls="left")
                    if basic_defs.DEVELOPMENT:
                        sel_table[0][0]        = html_tools.content("Propagate:", cls="right")
                        sel_table[None][0 : 4] = html_tools.content([glob_prop_opt], cls="left")
                    sel_table[0][0]        = html_tools.content("Device Mode:", cls="right")
                    sel_table[None][0 : 4] = html_tools.content([device_mode_list], cls="left")
                if "a" in infos_set and (num_apc_cons or num_ibc_cons):
                    if apc_com_list:
                        apc_com_list[""] = None
                    if ibc_com_list:
                        ibc_com_list[""] = None
                    sel_table[0][0]        = html_tools.content("Power control:", cls="right")
                    sel_table[None][0 : 4] = html_tools.content(sum([["%s: " % (pc_name), x, "; "] for pc_name, x in [("APC", apc_com_list),
                                                                                                                      ("IBC", ibc_com_list)] if x], []) or "---", cls="left" )
                if "k" in infos_set:
                    kernel_sel_list[""] = -1
                    sel_table[0][0]        = html_tools.content("Kernel:"      , cls="right")
                    sel_table[None][0 : 4] = html_tools.content([kernel_sel_list, ", stage1 flavour: ",
                                                                 stage1_flavour_list], cls="left" )
                    sel_table[0][0]        = html_tools.content("Kernel parameter:"  , cls="right")
                    sel_table[None][0 : 4] = html_tools.content(kernel_par_text_field, cls="left" )
                if "i" in infos_set:
                    image_sel_list[""] = None
                    sel_table[0][0]        = html_tools.content("Image:"      , cls="right")
                    sel_table[None][0 : 4] = html_tools.content(image_sel_list, cls="left" )
                if "p" in infos_set:
                    part_sel_list[""] = None
                    sel_table[0][0]        = html_tools.content("Partition:" , cls="right")
                    sel_table[None][0 : 4] = html_tools.content(part_sel_list, cls="left" )
                if "m" in infos_set:
                    mac_address_field[""] = ""
                    greedy_action_list[""] = None
                    sel_table[0][0]        = html_tools.content("MacAddress:", cls="right")
                    sel_table[None][0 : 4] = html_tools.content([mac_address_field, " (", mac_action_list, "), driver: ", mac_driver_field, ", ",
                                                                 write_mac_action_list,
                                                                 "\n, global greedy mode:", greedy_action_list], cls="left" )
                if "c" in infos_set:
                    comment_text_field[""] = ""
                    new_log_entry_field[""] = ""
                    sel_table[0][0]        = html_tools.content("Comment:"         , cls="right")
                    sel_table[None][0 : 4] = html_tools.content(comment_text_field , cls="left" )
                    sel_table[0][0]        = html_tools.content("New log:"         , cls="right")
                    sel_table[None][0 : 4] = html_tools.content(new_log_entry_field, cls="left" )
                sel_table[1:sel_table.get_cursor()[0]]["class"] = "devup"
                req.write(sel_table(""))
        if mbl_table:
            req.write(html_tools.gen_hline("MACBootlog table (%s)" % (logging_tools.get_plural("entry", len(all_mb_entries))), 3))
            req.write(mbl_table(""))
            if mac_ignore_table:
                req.write(html_tools.gen_hline("MACIgnore table has %s" % (logging_tools.get_plural("entry", len(mac_ignore_list))), 3))
                req.write(mac_ignore_table(""))
        dev_ok_desel_list[""]   = dev_ok_desel
        dev_warn_desel_list[""] = dev_warn_desel
        req.write("".join([dev_ok_desel_list.create_hidden_var(""),
                           dev_warn_desel_list.create_hidden_var(""),
                           low_submit.create_hidden_var(),
                           dev_tree.get_hidden_sel()]))
        if d_sel or mbl_table:
            req.write("<div class=\"center\">%s%s</div>\n</form>\n" % (d_sel and "deselect %s, " % (dev_desel_list("")) or "",
                                                                       submit_button("")))
            
