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
""" interface to the hardwareinfo / pciinfo maps """

import functions
import logging_tools
import html_tools
import tools
import time
import cdef_device
import cgi
import pprint
import cgi
import re
import cpu_database
import sys
import server_command
import array

def module_info():
    return {"info" : {"description" : "Information",
                      "priority"    : 10},
            "hwi" : {"default"               : 0,
                     "enabled"               : 1,
                     "description"           : "Hardware info",
                     "left_string"           : "Hardwareinfo",
                     "right_string"          : "Cluster hardware",
                     "capability_group_name" : "info",
                     "priority"              : -20},
            "uhw" : {"default"                : 0,
                     "enabled"                : 1,
                     "description"            : "Update hardware info",
                     "mother_capability_name" : "hwi"}}

def get_cpu_info(hw_dict, glob_hw_dict):
    #print hw_dict, "<br>"
    if hw_dict.has_key("cpu"):
        glob_hw_dict.setdefault("cpu", [])
        cpu_d = {}
        for cpu_stuff in hw_dict["cpu"]:
            glob_hw_dict["cpu"].append(cpu_stuff)
            cpu_info = "%s (%s)" % (cpu_stuff["sarg0"], cpu_stuff["iarg0"] > 1200 and "%.2f GHz" % (float(cpu_stuff["iarg0"])/1000.) or "%d MHz" % (cpu_stuff["iarg0"]))
            cpu_d.setdefault(cpu_info, 0)
            cpu_d[cpu_info] += 1
        return ", ".join(["%s%s" % (num > 1 and "%d x " % (num) or "", info) for info, num in cpu_d.iteritems()])
    else:
        return "< not set >"

def get_cpu_speed(hw_dict):
    if hw_dict.has_key("cpu"):
        cpu_d = {}
        for cpu_stuff in hw_dict["cpu"]:
            cpu_info = cpu_stuff["iarg0"]
            cpu_d.setdefault(cpu_info, 0)
            cpu_d[cpu_info] += 1
        return ", ".join(["%s%d" % (cpu_d[speed] > 1 and "%d x " % (cpu_d[speed]) or "", speed) for speed in sorted(cpu_d.keys())])
    else:
        return "< not set >"

def get_last_update_info(last_upd):
    if last_upd:
        return time.strftime("%a, %d. %b %Y, %H:%M:%S", time.localtime(last_upd))
    else:
        return "never"

def get_mem_str(mv):
    # mv in KB
    mv /= 1024
    if mv > 1024:
        return "%.2f GB" % (float(mv)/1024)
    else:
        return "%d MB" % (mv)
    
def get_mem_phys(hw_dict, glob_hw_dict):
    if hw_dict.has_key("mem"):
        glob_hw_dict.setdefault("mem", {"iarg0" : 0,
                                        "iarg1" : 0})
        glob_hw_dict["mem"]["iarg0"] += hw_dict["mem"]["iarg0"]
        return get_mem_str(hw_dict["mem"]["iarg0"])
    else:
        return "< not set >"

def get_mem_swap(hw_dict, glob_hw_dict):
    if hw_dict.has_key("mem"):
        if glob_hw_dict.has_key("mem"):
            glob_hw_dict["mem"]["iarg1"] += hw_dict["mem"]["iarg1"]
        return get_mem_str(hw_dict["mem"]["iarg1"])
    else:
        return "< not set >"

def get_disk_space(hw_dict, glob_hw_dict):
    if hw_dict.has_key("disks"):
        glob_hw_dict.setdefault("disks", {"iarg0" : 0,
                                          "iarg1" : 0})
        d_size, d_num = (hw_dict["disks"]["iarg1"],
                        hw_dict["disks"]["iarg0"])
        glob_hw_dict["disks"]["iarg0"] += d_num
        glob_hw_dict["disks"]["iarg1"] += d_size
        return "%s on %s" % (d_size > 1024 and "%.2f TB" % (float(d_size)/1000) or "%d GB" % (d_size), logging_tools.get_plural("disc", d_num))
    else:
        return "< not set >"

def get_gfx_info(hw_dict, gfx_dict):
    if hw_dict.has_key("gfx"):
        gfx_str = hw_dict["gfx"]["sarg0"]
        gfx_dict.setdefault(gfx_str, 0)
        gfx_dict[gfx_str] += 1
        return "(%d)" % (gfx_dict.keys().index(gfx_str) + 1)
    else:
        return "< not set >"

def process_page(req):
    if req.conf["genstuff"].has_key("AUTO_RELOAD"):
        del req.conf["genstuff"]["AUTO_RELOAD"]
    functions.write_header(req)
    functions.write_body(req)
    dev_tree = tools.display_list(req)
    dev_tree.add_regexp_field()
    dev_tree.add_devsel_fields(tools.get_device_selection_lists(req.dc, req.user_info.get_idx()))
    dev_tree.query(["H"],
                   ["comment", "bootserver"])
    # what to display
    disp_list = html_tools.selection_list(req, "dt", {"i" : "Device overview",
                                                      "p" : "PCI info",
                                                      "n" : "Network info",
                                                      "d" : "DMI info",
                                                      "c" : "CPU info"})
    act_disp = disp_list.check_selection("", "i")
    # filter field
    filter_field = html_tools.text_field(req, "ff", display_len=16, size=64)
    # action log
    action_log = html_tools.message_log()
    # verbose button
    verbose_button = html_tools.checkbox(req, "verb")
    is_verbose = verbose_button.check_selection()
    if is_verbose:
        scon_logs = html_tools.message_log()
    else:
        scon_logs = None
    if not dev_tree.devices_found():
        req.write(html_tools.gen_hline("No devices found", 2))
    else:
        update_button = html_tools.checkbox(req, "upd", auto_reset=1)
        upd_all = update_button.check_selection("")
        dg_sel, d_sel, dg_sel_eff = dev_tree.get_selection()
        for dg in dev_tree.get_sorted_devg_idx_list():
            for dev in dev_tree.get_sorted_dev_idx_list(dg):
                dev_struct = dev_tree.get_dev_struct(dev)
                if dev_struct["bootserver"]:
                    bs_name = dev_tree.get_dev_name(dev_struct["bootserver"])
                    bs_string = "bs=%s" % (bs_name)
                else:
                    bs_string = "no bs"
                dev_struct["post_str"] = ", %s" % (bs_string)
        ds_dict = dev_tree.get_device_selection_lists()
        sel_table = html_tools.html_table(cls="blindsmall")
        sel_table[0][0] = html_tools.content(dev_tree, "devg", cls="center")
        sel_table[None][0] = html_tools.content(dev_tree, "dev", cls="center")
        if ds_dict:
            sel_table[None][0] = html_tools.content(dev_tree, "sel", cls="center")
            col_span = 3
        else:
            col_span = 2
        # report for problem devices
        sel_table[0][1:col_span] = html_tools.content(["Regexp for Groups ", dev_tree.get_devg_re_field(), " and devices ", dev_tree.get_dev_re_field(),
                                                       "\n, ", dev_tree.get_devsel_action_field(), " selection", dev_tree.get_devsel_field()], cls="center")
        select_button = html_tools.submit_button(req, "select")
        submit_button = html_tools.submit_button(req, "submit")
        act_filter = filter_field.check_selection("", "")
        info_line = ["Verbose: ", verbose_button, ", display type: ", disp_list, ", filter. ", filter_field, ",\n ", select_button]
        sel_table[0][1:col_span] = html_tools.content(info_line, cls="center")
        req.write("<form action=\"%s.py?%s\" method=post>%s</form>\n" % (req.module_name,
                                                                         functions.get_sid(req),
                                                                         sel_table("")))
        if not d_sel:
            req.write(html_tools.gen_hline("No devices selected", 2))
        else:
            d_sel_str = " OR ".join(["d.device_idx=%d" % (x) for x in d_sel])
            req.dc.execute("SELECT d.device_type, d.bootnetdevice, d.bootserver, d.comment, d.device_idx, d.name, d.device_group, d.cpu_info, dg.name AS dgname FROM device d, device_group dg WHERE dg.device_group_idx=d.device_group AND (%s)" % (d_sel_str))
            dev_dict, update_dict, del_list = ({}, {}, [])
            for db_rec in req.dc.fetchall():
                act_dev = cdef_device.device(db_rec["name"], db_rec["device_idx"], db_rec["device_group"], db_rec["device_type"])
                dev_dict[db_rec["device_idx"]] = act_dev
                act_dev.set_bootnetdevice(db_rec["bootnetdevice"])
                act_dev.set_comment(db_rec["comment"])
                act_dev.set_bootserver(db_rec["bootserver"])
                if type(db_rec["cpu_info"]) == type(array.array("c")):
                    act_dev.cpu_info = db_rec["cpu_info"].tostring()
                else:
                    act_dev.cpu_info = db_rec["cpu_info"]
                # we have to check every update_button suffix
                upd = update_button.check_selection(act_dev.get_suffix()) or upd_all
                if upd and act_dev.get_bootserver():
                    bs_name = dev_tree.get_dev_name(act_dev.get_bootserver())
                    update_dict.setdefault(bs_name, [])
                    del_list.append(db_rec["device_idx"])
                    update_dict[bs_name].append(dev_tree.get_dev_name(db_rec["device_idx"]))
            if update_dict:
                for table, del_field in [("pci_entry", "device_idx"), ("hw_entry", "device")]:
                    sql_str = "DELETE FROM %s WHERE (%s)" % (table, " OR ".join(["%s=%d" % (del_field, x) for x in del_list]))
                    req.dc.execute(sql_str)
                upd_commands = []
                for server, nodes in update_dict.iteritems():
                    upd_commands.append(tools.s_command(req, "mother_server", 8001, "refresh_hwi", nodes, 10, server))
                tools.iterate_s_commands(upd_commands, scon_logs)
            if scon_logs:
                req.write(scon_logs.generate_stack("Server connections"))
            # fetch device info
            req.dc.execute("SELECT d.device_idx, hw.*, ht.*, UNIX_TIMESTAMP(hw.date) AS hwdate FROM device d LEFT JOIN hw_entry hw ON hw.device=d.device_idx LEFT JOIN hw_entry_type ht ON hw.hw_entry_type=ht.hw_entry_type_idx AND (%s)" % (d_sel_str))
            list_identifiers = ["cpu"]
            for db_rec in req.dc.fetchall():
                if db_rec["identifier"]:
                    act_dev = dev_dict[db_rec["device_idx"]]
                    act_dev.set_last_hw_update(db_rec["hwdate"])
                    if db_rec["identifier"] in list_identifiers:
                        act_dev.hw_dict.setdefault(db_rec["identifier"], [])
                        act_dev.hw_dict[db_rec["identifier"]].append(dict([(k, db_rec[k]) for k in ["iarg0", "iarg1", "sarg0", "sarg1"] if db_rec["%s_descr" % (k)] and db_rec[k] is not None]))
                    else:
                        act_dev.hw_dict[db_rec["identifier"]] = dict([(k, db_rec[k]) for k in ["iarg0", "iarg1", "sarg0", "sarg1"] if db_rec["%s_descr" % (k)] and db_rec[k] is not None])
            if act_disp in ["d"]:
                # fetch dmi-info
                sql_str = "SELECT de.*, dk.*, dek.* FROM dmi_entry de LEFT JOIN dmi_key dk ON de.dmi_entry_idx=dk.dmi_entry LEFT JOIN dmi_ext_key dek ON dk.dmi_key_idx=dek.dmi_key WHERE (%s)" % (" OR ".join(["de.device=%d" % (dev_idx) for dev_idx in d_sel]))
                req.dc.execute(sql_str)
                for db_rec in req.dc.fetchall():
                    act_dev = dev_dict[db_rec["device"]]
                    if db_rec["dmi_entry_idx"] not in act_dev.dmi_dict.keys():
                        act_dev.dmi_dict[db_rec["dmi_entry_idx"]] = {"dmi_type"   : db_rec["dmi_type"],
                                                                     "handle"     : db_rec["handle"],
                                                                     "info"       : db_rec["info"],
                                                                     "dmi_length" : db_rec["dmi_length"],
                                                                     "keys"       : {}}
                    # add keys
                    if db_rec["dmi_key_idx"]:
                        act_dev.dmi_dict[db_rec["dmi_entry_idx"]]["keys"][db_rec["key_string"]] = db_rec["value_string"]
            # fetch pci info
            req.dc.execute("SELECT d.device_idx, p.vendorname, p.devicename, p.revision, p.subclassname, p.domain, p.bus, p.slot, p.func, UNIX_TIMESTAMP(p.date) AS pdate FROM device d LEFT JOIN pci_entry p ON p.device_idx=d.device_idx WHERE (%s)" % (d_sel_str))
            for db_rec in req.dc.fetchall():
                if db_rec["vendorname"]:
                    act_dev = dev_dict[db_rec["device_idx"]]
                    act_dev.set_last_hw_update(db_rec["pdate"])
                    act_dev.pci_dict.setdefault(db_rec["domain"], {}).setdefault(db_rec["bus"], {}).setdefault(db_rec["slot"], {})[db_rec["func"]] = dict([(k, db_rec[k]) for k in ["vendorname", "devicename", "revision", "subclassname"]])
            # fetch network info
            req.dc.execute("SELECT d.device_idx, n.devname, nt.description, i.ip, n.macadr FROM network_device_type nt, device d LEFT JOIN netdevice n ON n.device=d.device_idx LEFT JOIN netip i ON i.netdevice=n.netdevice_idx WHERE nt.network_device_type_idx=n.network_device_type AND (%s)" % (d_sel_str))
            for db_rec in req.dc.fetchall():
                act_dev = dev_dict[db_rec["device_idx"]]
                if db_rec["devname"]:
                    act_dev.net_dict.setdefault(db_rec["devname"], {"description" : db_rec["description"],
                                                                    "macadr"      : db_rec["macadr"],
                                                                    "ips"         : []})
                if db_rec["ip"]:
                    act_dev.net_dict[db_rec["devname"]]["ips"].append(db_rec["ip"])
            out_str = html_tools.gen_hline("Selected %s in %s" % (logging_tools.get_plural("device", len(d_sel)),
                                                              logging_tools.get_plural("devicegroup", len(dg_sel_eff)))
                                         , 2)
            out_str += "<form action=\"%s.py?%s\" method=post>%s%s" % (req.module_name,
                                                                       functions.get_sid(req),
                                                                       verbose_button.create_hidden_var(),
                                                                       disp_list.create_hidden_var())
            hw_table = html_tools.html_table(cls="normal")
            out_str += hw_table.get_header()
            req.write(out_str)
            glob_hw_dict = {}
            gfx_dict = tools.ordered_dict()
            if act_disp == "i":
                max_length = 10
            elif act_disp == "n":
                max_length = 5
            elif act_disp == "d":
                max_length = 7
            else:
                max_length = 9
            for dg in dg_sel_eff:
                hw_table[1][1:max_length] = html_tools.content(dev_tree.get_sel_dev_str(dg), cls="devgroup")
                req.write(hw_table.flush_lines())
                hw_table[0][0] = html_tools.content("Name (comment)", type="th")
                hw_table[None]["class"] = "line00"
                if act_disp == "i":
                    for h_line in ["server", "update", "last updated", "cpu info", "cpu speed", "RAM", "Swap", "Disc", "Gfx"]:
                        hw_table[None][0] = html_tools.content(h_line, type="th")
                elif act_disp == "n":
                    for h_line in ["device", "MACAddress", "class", "IP(s)"]:
                        hw_table[None][0] = html_tools.content(h_line, type="th")
                elif act_disp == "d":
                    for h_line in ["handle", "dmi_type", "info", "length", "key", "value"]:
                        hw_table[None][0] = html_tools.content(h_line, type="th")
                elif act_disp == "c":
                    for h_line in ["server", "update", "cpu information"]:
                        hw_table[None][0] = html_tools.content(h_line, type="th")
                else:
                    for h_line in ["domain", "bus", "slot", "func", "subclass", "vendor", "device", "revision"]:
                        hw_table[None][0] = html_tools.content(h_line, type="th")
                req.write(hw_table.flush_lines())
                line_idx = 0
                for dev in [x for x in d_sel if x in dev_tree.get_sorted_dev_idx_list(dg)]:
                    line_idx = 1 - line_idx
                    act_dev = dev_dict[dev]
                    act_hw_dict, act_pci_dict = (act_dev.hw_dict, act_dev.pci_dict)
                    if act_disp == "i":
                        hw_table[1]["class"] = "line1%d" % (line_idx)
                        hw_table[None][0] = html_tools.content("%s%s" % (act_dev.get_name(),
                                                                         act_dev.get_comment() and " (%s)" % (act_dev.get_comment()) or ""),
                                                               cls="left")
                        hw_table[None][0] = html_tools.content(act_dev.get_bootserver() and dev_tree.get_dev_name(act_dev.get_bootserver()) or "&nbsp;", cls="center")
                        hw_table[None][0] = html_tools.content(act_dev.get_bootserver() and update_button or "&nbsp;", cls="center")
                        hw_table[None][0] = html_tools.content(get_last_update_info(act_dev.get_last_hw_update()), cls="center")
                        hw_table[None][0] = html_tools.content(get_cpu_info(act_hw_dict, glob_hw_dict), cls="center")
                        hw_table[None][0] = html_tools.content(get_cpu_speed(act_hw_dict), cls="center")
                        hw_table[None][0] = html_tools.content(get_mem_phys(act_hw_dict, glob_hw_dict), cls="center")
                        hw_table[None][0] = html_tools.content(get_mem_swap(act_hw_dict, glob_hw_dict), cls="center")
                        hw_table[None][0] = html_tools.content(get_disk_space(act_hw_dict, glob_hw_dict), cls="center")
                        hw_table[None][0] = html_tools.content(get_gfx_info(act_hw_dict, gfx_dict), cls="center")
                    elif act_disp == "d":
                        hw_table[1][2:max_length] = html_tools.content([act_dev.get_bootserver() and "on bootserver %s" % (dev_tree.get_dev_name(act_dev.get_bootserver())) or "no bootserver", ",\n update:",
                                                                        update_button, ", last updated: ",
                                                                        get_last_update_info(act_dev.get_last_hw_update()),
                                                                        "%s" % (act_dev.get_comment() and ",\n comment: %s" % (act_dev.get_comment()) or ""),
                                                                        ", cpu: %s" % (get_cpu_info(act_hw_dict, {}))],
                                                                       cls="left")
                        dmi_idx_dict = dict([(value["handle"], key) for key, value in act_dev.dmi_dict.iteritems()])
                        handle_line, key_line, ext_key_line = (2, 2, 2)
                        if act_filter:
                            act_filter_re = re.compile(act_filter)
                        else:
                            act_filter_re = None
                        line1_idx = line_idx
                        for handle_idx in sorted(dmi_idx_dict.keys()):
                            dmi_info = act_dev.dmi_dict[dmi_idx_dict[handle_idx]]
                            # show handle ?
                            show_handle = True
                            if act_filter_re and not act_filter_re.search(dmi_info["info"].lower()):
                                show_handle = False
                            if show_handle:
                                for sub_key in sorted(dmi_info["keys"].keys()):
                                    act_value = dmi_info["keys"][sub_key]
                                    if type(act_value) == type([]):
                                        line1_idx = 1 - line1_idx
                                        hw_table[key_line]["class"] = "line1%d" % (line1_idx)
                                        hw_table[key_line][6] = html_tools.content(sub_key, cls="left")
                                        hw_table[None][0] = html_tools.content(logging_tools.get_plural("value", len(act_value)), cls="left")
                                        key_line += 1
                                    else:
                                        line1_idx = 1 - line1_idx
                                        hw_table[key_line]["class"] = "line1%d" % (line1_idx)
                                        hw_table[key_line][6] = html_tools.content(sub_key, cls="left")
                                        hw_table[None][0] = html_tools.content(cgi.escape(act_value, 1), cls="left")
                                        key_line += 1
                                if handle_line == key_line:
                                    # no content
                                    line1_idx = 1 - line_idx
                                    hw_table[key_line]["class"] = "line1%d" % (line1_idx)
                                    hw_table[key_line][6:7] = html_tools.content("&nbsp;", cls="left")
                                    key_line += 1
                                hw_table[handle_line:key_line-1][2] = html_tools.content(dmi_info["handle"], cls="left")
                                hw_table[handle_line:key_line-1][3] = html_tools.content(dmi_info["dmi_type"], cls="left")
                                hw_table[handle_line:key_line-1][4] = html_tools.content(dmi_info["info"], cls="left")
                                hw_table[handle_line:key_line-1][5] = html_tools.content(dmi_info["dmi_length"], cls="left")
                                handle_line = key_line
                            #pprint.pprint(dmi_info)
                        hw_table[1:key_line-1][1] = html_tools.content(act_dev.get_name(), cls="left")
                        hw_table[1]["class"] = "line0%d" % (line_idx)
                    elif act_disp == "n":
                        all_nds = act_dev.net_dict.keys()
                        hw_table[1:len(all_nds) + 1][1] = html_tools.content(act_dev.get_name(), cls="left")
                        hw_table[None]["class"] = "line0%d" % (line_idx)
                        hw_table[None][2:5] = html_tools.content([act_dev.get_bootserver() and "on bootserver %s" % (dev_tree.get_dev_name(act_dev.get_bootserver())) or "no bootserver", ",\n update:",
                                                                  update_button, ", last updated: ",
                                                                  get_last_update_info(act_dev.get_last_hw_update()),
                                                                  "%s" % (act_dev.get_comment() and ",\n comment: %s" % (act_dev.get_comment()) or ""),
                                                                  ", cpu: %s" % (get_cpu_info(act_hw_dict, {}))],
                                                                 cls="left")
                        line1_idx = line_idx
                        nd_line = 1
                        for nd in sorted(all_nds):
                            nd_stuff = act_dev.net_dict[nd]
                            line1_idx = 1 - line1_idx
                            nd_line += 1
                            hw_table[nd_line][2] = html_tools.content(nd, cls="left")
                            hw_table[None][0] = html_tools.content(nd_stuff["macadr"], cls="center")
                            descr = nd_stuff["description"]
                            if descr.endswith(" devices"):
                                descr = descr[:-len(" devices")]
                            hw_table[None][0] = html_tools.content(descr, cls="center")
                            ips = sorted(nd_stuff["ips"])
                            if ips:
                                hw_table[None][0] = html_tools.content("(%d) %s" % (len(ips), ", ".join(ips)), cls="left")
                            else:
                                hw_table[None][0] = html_tools.content("---", cls="left")
                            if int(nd_stuff["macadr"].replace(":", ""), 16) or nd == "lo" or nd.count(":"):
                                hw_table[None]["class"] = "line1%d" % (line1_idx)
                            else:
                                hw_table[None]["class"] = "line2%d" % (line1_idx)
                    elif act_disp == "c":
                        hw_table[1]["class"] = "line1%d" % (line_idx)
                        hw_table[None][0] = html_tools.content("%s%s" % (act_dev.get_name(),
                                                                         act_dev.get_comment() and " (%s)" % (act_dev.get_comment()) or ""),
                                                               cls="left")
                        hw_table[None][0] = html_tools.content(act_dev.get_bootserver() and dev_tree.get_dev_name(act_dev.get_bootserver()) or "&nbsp;", cls="center")
                        hw_table[None][0] = html_tools.content(act_dev.get_bootserver() and update_button or "&nbsp;", cls="center")
                        if act_dev.cpu_info:
                            try:
                                cpu_info = server_command.net_to_sys(act_dev.cpu_info)
                            except:
                                cpu_info = None
                        else:
                            cpu_info = None
                        if cpu_info:
                            try:
                                cpu_info.parse_info()
                            except:
                                cpu_info = None
                        if cpu_info:
                            cpu_core_width = 40
                            cpu_core_height = 14
                            font_height = 12
                            layout = cpu_info.layout._get_layout_dict()
                            has_l3_cache = cpu_info.layout.has_l3_cache
                            socket_divs = []
                            for socket_num in sorted(layout.keys()):
                                socket_div = html_tools.div_box(cls="cpusocket",
                                                                inner_space=2,
                                                                top_space=font_height,
                                                                content="socket%d" % (socket_num))
                                domain_divs = []
                                for domain_num in sorted(layout[socket_num].keys()):
                                    domain_div = html_tools.div_box(blind=True,
                                                                    inner_space=1)
                                    die_divs = []
                                    for die_num in sorted(layout[socket_num][domain_num].keys()):
                                        die_div = html_tools.div_box(cls="cpudie",
                                                                     inner_space=2,
                                                                     content="die%d" % (die_num),
                                                                     top_space=font_height)
                                        core_divs = []
                                        # count the logical cores
                                        num_lc = 0
                                        for core_num in sorted(layout[socket_num][domain_num][die_num].keys()):
                                            core_div = html_tools.div_box(cls="cpucore",
                                                                          inner_space=1,
                                                                          content="core%d" % (core_num),
                                                                          top_space=font_height)
                                            lcore_divs = []
                                            for lcore_num in sorted(layout[socket_num][domain_num][die_num][core_num]):
                                                num_lc += 1
                                                lcore_div = html_tools.div_box(cls="cpulogcore",
                                                                               width=cpu_core_width,
                                                                               height=cpu_core_height,
                                                                               content="lcore%d" % (lcore_num))
                                                lcore_divs.append(lcore_div)
                                            core_div.set_childs(lcore_divs)
                                            core_divs.append(core_div)
                                        l2_cache_div = html_tools.div_box(cls="cpucache",
                                                                          width=(cpu_core_width + 4) * num_lc - 2 + 4 * len(core_divs),
                                                                          height=16,
                                                                          content="lev2c",
                                                                          next_right=False)
                                        die_div.set_childs([l2_cache_div,
                                                            html_tools.div_box(blind=True,
                                                                               inner_space=1,
                                                                               childs=core_divs,
                                                                               next_right=False)])
                                        die_divs.append(die_div)
                                    if has_l3_cache:
                                        l3_cache_div = html_tools.div_box(cls="cpucache",
                                                                          width=((cpu_core_width + 4) * num_lc - 2 + 4 * len(core_divs)) * len(die_divs) + 8 + 8 * (len(die_divs) - 1),
                                                                          height=16,
                                                                          content="lev3c",
                                                                          next_right=False)
                                        domain_div.set_childs([l3_cache_div,
                                                               html_tools.div_box(blind=True,
                                                                                  inner_space=1,
                                                                                  childs=die_divs,
                                                                                  next_right=False)])
                                    else:
                                        domain_div.set_childs(die_divs)
                                    domain_divs.append(domain_div)
                                socket_div.set_childs(domain_divs)
                                socket_divs.append(socket_div)
                            system_div = html_tools.div_box(position="relative",
                                                            childs=socket_divs,
                                                            top_space=14,
                                                            cls="cpusystem",
                                                            content="system")
                            system_div.layout()
                            cpu_total_table = html_tools.html_table(cls="blind")
                            cpu_info_table = html_tools.html_table(cls="blind")
                            cpu_info_table[0]["class"] = "lineh"
                            for h_name in ["core", "speed", "socket", "cache info", "cpu id", "model name"]:
                                cpu_info_table[None][0] = html_tools.content(h_name, cls="center", type="th")
                            for cpu in [cpu_info[cpu_idx] for cpu_idx in cpu_info.cpu_idxs()]:
                                cpu_info_table[0][0] = html_tools.content("%d" % (cpu["core_num"]), cls="center")
                                cpu_info_table[None][0] = html_tools.content("%d" % (cpu["speed"]), cls="center")
                                cpu_info_table[None][0] = html_tools.content("%d" % (cpu["socket_num"]), cls="center")
                                cpu_info_table[None][0] = html_tools.content(cpu.get_cache_info_str(), cls="center")
                                cpu_info_table[None][0] = html_tools.content(cpu["cpu_id"], cls="center")
                                cpu_info_table[None][0] = html_tools.content(cpu.get("model name", "unknown brand"), cls="left")
                            cpu_total_table[0][0] = html_tools.content("\n".join(system_div.get_lines()), cls="center")
                            cpu_total_table[None][0] = html_tools.content(cpu_info_table, cls="center")
                            hw_table[None][0] = cpu_total_table
                        else:
                            hw_table[None][0] = html_tools.content("no CPU information", cls="warncenter")
                    else:
                        hw_table[1][2:9] = html_tools.content([act_dev.get_bootserver() and "on bootserver %s" % (dev_tree.get_dev_name(act_dev.get_bootserver())) or "no bootserver", ",\n update:",
                                                               update_button, ", last updated: ",
                                                               get_last_update_info(act_dev.get_last_hw_update()),
                                                               "%s" % (act_dev.get_comment() and ",\n comment: %s" % (act_dev.get_comment()) or ""),
                                                               ", cpu: %s" % (get_cpu_info(act_hw_dict, {}))],
                                                              cls="left")
                        domain_line, bus_line, func_line, slot_line = (2, 2, 2, 2)
                        line1_idx = line_idx
                        for domain in sorted([x for x in act_pci_dict.keys()]):
                            for bus in sorted([x for x in act_pci_dict[domain].keys()]):
                                for func in sorted(act_pci_dict[domain][bus].keys()):
                                    for slot in sorted(act_pci_dict[domain][bus][func].keys()):
                                        hw_table[slot_line]["class"] = "line1%d" % (line1_idx)
                                        line1_idx = 1 - line1_idx
                                        slot_info = act_pci_dict[domain][bus][func][slot]
                                        hw_table[slot_line][5] = html_tools.content("%02x" % (slot or 0), cls="center")
                                        hw_table[None][0] = html_tools.content(slot_info["subclassname"], cls="left")
                                        hw_table[None][0] = html_tools.content(slot_info["vendorname"]  , cls="left")
                                        hw_table[None][0] = html_tools.content(slot_info["devicename"]  , cls="left")
                                        hw_table[None][0] = html_tools.content(slot_info["revision"]    , cls="center")
                                        slot_line += 1
                                    hw_table[func_line:slot_line-1][4] = html_tools.content("%02x" % (func or 0), cls="center")
                                    func_line = slot_line
                                hw_table[bus_line:slot_line-1][3] = html_tools.content("%02x" % (bus or 0), cls="center")
                                bus_line = slot_line
                            hw_table[domain_line:bus_line-1][2] = html_tools.content("%04x" % (domain or 0), cls="center")
                            domain_line = bus_line
                        hw_table[1:slot_line-1][1] = html_tools.content(act_dev.get_name(), cls="left")
                        hw_table[1]["class"] = "line0%d" % (line_idx)
                    req.write(hw_table.flush_lines(act_dev.get_suffix()))
            req.write(hw_table.get_footer())
            if act_disp == "i" and (len(d_sel) > 1 or gfx_dict):
                hw_table = html_tools.html_table(cls="normalsmall")
                if len(d_sel) > 1:
                    if gfx_dict:
                        req.write(html_tools.gen_hline("Global info and Gfx info", 3))
                    else:
                        req.write(html_tools.gen_hline("Global info", 3))
                    hw_table[0][0] = html_tools.content("update all", type="th")
                    hw_table[None]["class"] = "line01"
                    for h_line in ["cpu speed", "RAM", "Swap", "Disc"]:
                        hw_table[None][0] = html_tools.content(h_line, type="th")
                    hw_table[0][0] = html_tools.content(update_button, cls="center")
                    hw_table[None]["class"] = "line11"
                    hw_table[None][0] = html_tools.content(get_cpu_speed(glob_hw_dict), cls="center")
                    hw_table[None][0] = html_tools.content(get_mem_phys(glob_hw_dict, {}), cls="center")
                    hw_table[None][0] = html_tools.content(get_mem_swap(glob_hw_dict, {}), cls="center")
                    hw_table[None][0] = html_tools.content(get_disk_space(glob_hw_dict, {}), cls="center")
                if gfx_dict:
                    if len(d_sel) == 1:
                        req.write(html_tools.gen_hline("Gfx info", 3))
                    hw_table[0][0] = html_tools.content("Ref", type="th")
                    hw_table[None][0:4] = html_tools.content("Count x Type", type="th")
                    hw_table[None]["class"] = "line00"
                    line_idx = 1
                    for info, count in gfx_dict.iteritems():
                        line_idx = 1 - line_idx
                        hw_table[0][1] = html_tools.content("(%d)" % (gfx_dict.keys().index(info) + 1), cls="center")
                        hw_table[None]["class"] = "line1%d" % (line_idx)
                        hw_table[None][0:4] = html_tools.content(cgi.escape("%d x %s" % (count, info)), cls="left")
                req.write(hw_table(""))
            if len(d_sel) > 1 and act_disp != "i":
                req.write("<div class=\"center\">Update all: %s</div>\n" % (update_button("")))
            req.write("<div class=\"center\">%s</div>\n%s%s</form>\n" % (submit_button(""),
                                                                         dev_tree.get_hidden_sel(),
                                                                         filter_field.create_hidden_var("")))
            
