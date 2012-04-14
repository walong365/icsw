#!/usr/bin/python -Ot
#
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
""" controls the apcs """

import functions
import logging_tools
import time
import tools
import html_tools
import cdef_device
    
DISCREET_APCS = ["AP9606"]
CONTINUOUS_APCS = ["AP7920", "rpdu"]

OUTLET_PONDS  = [0, 15, 30, 45, 1 * 60, 2 * 60, 5 * 60, -1]
OUTLET_POFFDS = [0, 15, 30, 45, 1 * 60, 2 * 60, 5 * 60, -1]
OUTLET_REBDS  = [5, 10, 15, 20, 30, 45, 60]
APC_PONDS     = OUTLET_PONDS

def module_info():
    return {"apc" : {"description"           : "APC control",
                     "default"               : 0,
                     "enabled"               : 1,
                     "left_string"           : "APC control",
                     "right_string"          : "APC control",
                     "priority"              : -100,
                     "capability_group_name" : "conf"}}

def apc_config(req, apc_tree, apc_dict, bs_dict, dev_dict, act_dev_sel):
    # change_log
    change_log = html_tools.message_log()
    # which apcs to display full
    apc_full_idx_list = apc_tree.get_selection()[1]
    # which outlets to display
    dev_show_list = act_dev_sel
    # get apcs to display partially
    apc_partial_idx_list = [k2 for k2 in dict([(k, True) for k in sum([[apc_idx for apc_idx, apc_name, out_num in dev_dict[x]["outlets"]] for x in act_dev_sel], [])]).keys() if k2 not in apc_full_idx_list]
    # names of apcs to show (full or partially)
    apc_show_names = sorted([apc_tree.get_dev_name(x) for x in apc_full_idx_list + apc_partial_idx_list])
    if not apc_show_names:
        req.write(html_tools.gen_hline("Nothing selected", 2))
    else:
        # init apc_command
        outlet_command = html_tools.selection_list(req, "apcc", dict([(k, {"pri" : k,
                                                                           "name" : v}) for k, v in cdef_device.apc_outlet_states.iteritems()]),
                                                auto_reset=True)
        apc_command = html_tools.selection_list(req, "apcc", dict([(k, {"pri" : k,
                                                                        "name" : v}) for k, v in cdef_device.apc_master_states.iteritems()]),
                                                auto_reset=True)
        apc_sync_obj = html_tools.checkbox(req, "sync", auto_reset=True)
        p_on_delay  = html_tools.text_field(req, "apcpon" , display_len=6, size=6)
        p_off_delay = html_tools.text_field(req, "apcpoff", display_len=6, size=6)
        reboot_dur  = html_tools.text_field(req, "apcreb" , display_len=6, size=6)
        # action_dict for mother_command
        flag_action_dict = {}
        # init table
        config_table = html_tools.html_table(cls="normal")
        header_list = ["Outlet", "Used", "State", "Command", "p_on_delay", "p_off_delay", "reboot_duration", "synced"]
        config_table[0]["class"] = "line00"
        for header in header_list:
            config_table[None][0] = html_tools.content(header, cls="center", type="th")
        apc_sync_list = []
        apc_line_idx = 0
        for apc_name in apc_show_names:
            apc_idx = apc_tree.get_dev_idx(apc_name)
            apc_struct = apc_dict[apc_idx]
            devg_dict, info_str, device_list = get_apc_outlet_info_str(apc_struct)
            # header
            apc_line_idx = 1 - apc_line_idx
            config_table[0]["class"] = "line0%d" % (apc_line_idx)
            full_config = apc_idx in apc_full_idx_list
            apc_info_str = "%s, %s, %s, controlling server is %s" % (apc_struct.get_apc_type(),
                                                                     apc_struct.get_apc_version(),
                                                                     logging_tools.get_plural("outlet", apc_struct.get_num_outlets()),
                                                                     apc_struct.get_bootserver_name())
            if full_config:
                config_table[None][0 : len(header_list)] = html_tools.content("Apc %s [%s], (full config), %s" % (apc_name,
                                                                                                                  apc_info_str,
                                                                                                                  info_str), cls="center", type="th")
            else:
                config_table[None][0 : len(header_list)] = html_tools.content("Apc %s [%s], (partially config), %s" % (apc_name,
                                                                                                                       apc_info_str,
                                                                                                                       info_str), cls="center", type="th")
            apc_pfix ="a%d" % (apc_idx)
            line_idx = 0
            apc_change_log = []
            apc_is_in_sync, sync_apc = (True, False)
            for out_num, out_struct in apc_struct.outlets.iteritems():
                if full_config or out_struct["name"] in act_dev_sel:
                    line_pfix = "%so%d" % (apc_pfix, out_num)
                    apc_info = "%s/o%d" % (apc_name, out_num)
                    outlet_com = outlet_command.check_selection(line_pfix, 0)
                    if outlet_com:
                        apc_struct.add_outlet_command(out_num, outlet_com)
                    # check delays
                    change_f = [check_delay(change_log, p_on_delay , line_pfix, out_struct, "t_pond" , -1, 7200, apc_info),
                                check_delay(change_log, p_off_delay, line_pfix, out_struct, "t_poffd", -1, 7200, apc_info),
                                check_delay(change_log, reboot_dur , line_pfix, out_struct, "t_rebd" ,  5,   60, apc_info)]
                    if len([True for changed, new_val in change_f if changed]):
                        db_str_field = []
                        for (changed, new_val), db_field_name in zip(change_f, ["t_power_on_delay", "t_power_off_delay", "t_reboot_delay"]):
                            if changed:
                                db_str_field.append("%s=%d" % (db_field_name, new_val))
                                apc_change_log.append("%s of outlet %d to %d" % (db_field_name, out_num, new_val))
                                sync_apc = True
                        db_str = "UPDATE msoutlet SET %s WHERE msoutlet_idx=%d" % (", ".join(db_str_field), out_struct["db_idx"])
                        req.dc.execute(db_str)
                    # check settings for sync
                    out_sync = len([True for n in ["pond", "poffd", "rebd"] if out_struct[n] == out_struct["t_%s" % (n)]]) == 3
                    line_idx = 1 - line_idx
                    config_table[0]["class"] = "line1%d" % (line_idx)
                    config_table[None][0] = html_tools.content("%d" % (out_num), cls="left")
                    config_table[None][0] = html_tools.content(out_struct["name"] and "%s%s" % (out_struct["name"], out_struct["info"] and " (%s)" % (out_struct["info"]) or "") or "---", cls="left")
                    config_table[None][0] = html_tools.content(out_struct["state"], cls="center")
                    config_table[None][0] = html_tools.content(outlet_command, line_pfix, cls="center")
                    config_table[None][0] = html_tools.content(p_on_delay, line_pfix, cls="center")
                    config_table[None][0] = html_tools.content(p_off_delay, line_pfix, cls="center")
                    config_table[None][0] = html_tools.content(reboot_dur, line_pfix, cls="center")
                    if out_sync:
                        config_table[None][0] = html_tools.content("yes", cls="okmin")
                    else:
                        config_table[None][0] = html_tools.content("no", cls="errormin")
                        apc_is_in_sync = False
            if full_config:
                apc_com = apc_command.check_selection(apc_pfix, 0)
                if apc_com:
                    apc_struct.add_apc_command(apc_com)
                dummy_struct = {"cold_delay" : apc_struct.get_apc_delays()[0]}
                changed, new_val = check_delay(change_log, p_on_delay, apc_pfix, dummy_struct, "cold_delay", -1, 7200, apc_name)
                if changed:
                    sync_apc = True
                    req.dc.execute("UPDATE apc_device SET power_on_delay=%d WHERE apc_device_idx=%d" % (new_val, apc_struct.get_apc_device_idx()))
                    apc_change_log.append("power_on_delay of apc to %d" % (new_val))
                config_table[0]["class"] = "line0%d" % (apc_line_idx)
                config_table[None][0:3] = html_tools.content("apc global settings", cls="left")
                config_table[None][0] = html_tools.content(apc_command, apc_pfix, cls="center")
                config_table[None][0] = html_tools.content(p_on_delay, apc_pfix, cls="center")
                if apc_sync_obj.check_selection(apc_pfix):
                    sync_apc = True
                config_table[None][0:2] = html_tools.content(["send sync request: ", apc_sync_obj], apc_pfix, cls="left")
                if apc_is_in_sync:
                    config_table[None][0] = html_tools.content("yes", cls="okmin")
                else:
                    config_table[None][0] = html_tools.content("no", cls="errormin")
            # check flags and logs
            if sync_apc:
                apc_sync_list.append(apc_idx)
            if apc_change_log:
                change_log.add_ok("Changes of %s: set %s" % (apc_name, ", ".join(apc_change_log)), "sql")
        for apc_struct in apc_dict.values():
            act_bs, act_com_str = (apc_struct.get_bootserver(), apc_struct.get_command_str())
            if act_bs and act_com_str:
                flag_action_dict.setdefault(act_bs, {}).setdefault(apc_struct.get_name(), []).append(act_com_str)
            if apc_struct.get_idx() in apc_sync_list:
                flag_action_dict.setdefault(act_bs, {}).setdefault(apc_struct.get_name(), []).append("update")
        mother_coms = []
        for bs_idx, targets in flag_action_dict.iteritems():
            act_targ_dict = dict([(k, ":".join(v)) for k, v in targets.iteritems()])
            mother_coms.append(tools.s_command(req, "mother_server", 8001, "apc_com", act_targ_dict, 10, bs_dict[bs_idx]))
        tools.iterate_s_commands(mother_coms, change_log)
        submit_button = html_tools.submit_button(req, "Submit")
        submit_button.set_class("", "button")
        out_str = "%s%s%s<div class=\"center\">%s</form>\n" % (change_log.generate_stack("Action log"),
                                                               html_tools.gen_hline("Please edit", 2),
                                                               config_table(""),
                                                               submit_button(""))
        req.write(out_str)

def check_delay(change_log, html_obj, line_pfix, struct, def_name, min_val, max_val, apc_info):
    default_val = struct[def_name]
    if default_val == -1:
        def_str = "never"
    else:
        def_str = str(default_val)
    # check default_value
    if default_val < min_val or default_val > max_val:
        change_log.add_warn("default_value %d wrong for %s" % (default_val, apc_info), "not in bound [%d, %d]" % (min_val, max_val))
        default_val = min_val
        force_changed = True
    else:
        force_changed = False
    new_val = html_obj.check_selection(line_pfix, def_str).strip()
    # interpret never input
    if new_val.lower() == "never":
        new_val = "-1"
    if new_val == "-1":
        new_val = -1
    elif new_val.isdigit():
        new_val = int(new_val)
    else:
        change_log.add_warn("cannot parse new_value %s for %s" % (new_val, apc_info), "parse")
        new_val = default_val
    if new_val >= min_val and new_val <= max_val:
        pass
    else:
        change_log.add_warn("cannot set new_value %d for %s" % (new_val, apc_info), "not in bound [%d, %d]" % (min_val, max_val))
        new_val = default_val
    changed = new_val != default_val
    if new_val == -1:
        new_val_str = "never"
    else:
        new_val_str = str(new_val)
    # set new values
    html_obj[line_pfix] = new_val_str
    struct[def_name] = new_val
    return changed or force_changed, new_val
    
def apc_power_on_delays(req, apc_dict, bs_dict):
    red_flag = html_tools.checkbox(req, "red")
    if red_flag.check_selection(""):
        # get all devices with their device-types
        req.dc.execute("SELECT d.device_idx, dt.identifier FROM device d, device_type dt WHERE d.device_type=dt.device_type_idx")
        dt_dict = dict([(rec["device_idx"], {"id"        : rec["identifier"],
                                             "is_server" : False}) for rec in req.dc.fetchall()])
        req.dc.execute("SELECT d.device_idx FROM device d INNER JOIN device_config dc INNER JOIN new_config c INNER JOIN device_group dg LEFT JOIN device d2 ON d2.device_idx = dg.device WHERE d.device_group=dg.device_group_idx AND dc.new_config=c.new_config_idx AND (dc.device=d.device_idx OR dc.device=d2.device_idx) AND c.name='server'")
        for rec in req.dc.fetchall():
            dt_dict[rec["device_idx"]]["is_server"] = True
        sql_coms = []
        act_dist = {}
        # actual distribution
        for t_a in [t for t in APC_PONDS if t >= 0]:
            for t_b in [u for u in OUTLET_PONDS if u >= 0]:
                act_dist.setdefault(t_a + t_b, 0)
        # try to add for 800 devices
        s_time = time.time()
        act_apc_pond_idx = 0
        for high_pri in [0]:
            for apc_idx, apc_stuff in apc_dict.iteritems():
                num_devs = apc_stuff.get_num_devices_set()
                dev_types = [dt_dict[x] for x in apc_stuff.get_device_idxs()]
                if num_devs:
                    is_important_apc = len([True for k in dev_types if k["id"] in ["R", "S"] or k["is_server"]]) and True or False
                else:
                    is_important_apc = False
                #print "*", apc_idx, is_important_apc
                pon_d, reb_d = apc_stuff.get_apc_delays()
                act_apc_pond = APC_PONDS[act_apc_pond_idx]
                if act_apc_pond != pon_d:
                    apc_stuff.set_apc_delays(act_apc_pond, reb_d)
                    sql_coms.append("UPDATE apc_device SET power_on_delay=%d WHERE apc_device_idx=%d" % (act_apc_pond,
                                                                                                         apc_stuff.get_apc_device_idx()))
                act_apc_pond_idx += 1
                if APC_PONDS[act_apc_pond_idx] == -1:
                    act_apc_pond_idx = 0
                # distribute outlet_ponds to minimize number of concurrent power-ons
                for j in apc_stuff.get_outlet_nums():
                    # cycle through all 8 outlets
                    lut = dict([(act_dist[x], x) for x in [act_apc_pond + z for z in OUTLET_PONDS if z >= 0]])
                    min_lut_key = min(lut.keys())
                    act_outlet_pond = lut[min_lut_key] - act_apc_pond
                    act_dist[act_outlet_pond + act_apc_pond] += 1
                    if apc_stuff.get_outlet_var(j, "t_pond") != act_outlet_pond:
                        apc_stuff.set_outlet_var(j, "t_pond", act_outlet_pond)
                        sql_coms.append("UPDATE msoutlet SET t_power_on_delay=%d WHERE device=%d AND outlet=%d" % (act_outlet_pond,
                                                                                                                   apc_idx,
                                                                                                                   j))

            #apc_stuff.commit_sql_changes(req.dc, 0, 0, 1)
        for sql_com in sql_coms:
            req.dc.execute(sql_com)
        e_time = time.time()
        req.write(html_tools.gen_hline("Rewrote SQL-Database in %.2f seconds (%s)" % (e_time - s_time,
                                                                                      logging_tools.get_plural("SQL command", len(sql_coms))), 2))
    apc_lut = {}
    p_on_d_dict = {}
    for apc_idx, apc_stuff in apc_dict.iteritems():
        on = apc_stuff.get_outlet_nums()
        pon_d, reb_d = apc_stuff.get_apc_delays()
        apc_lut[apc_stuff.get_name()] = apc_idx
        for num in on:
            act_o_stuff = apc_stuff.get_outlet(num)
            if max(pon_d, act_o_stuff["t_pond"]) == -1:
                act_pon_d = -1
            else:
                act_pon_d = pon_d + act_o_stuff["t_pond"]
            p_on_d_dict.setdefault(act_pon_d, {}).setdefault(apc_stuff.get_name(), []).append((act_o_stuff["name"], num))
    info_table = html_tools.html_table(cls="normal")
    header_list = ["Power-on Delay", "#tot", "APC", "Outlet(s)"]
    info_table[0]["class"] = "line00"
    for header in header_list:
        info_table[None][0] = html_tools.content(header, cls="center", type="th")
    apc_type_dict = dict([(x, "discreet"  ) for x in DISCREET_APCS  ] +
                         [(x, "continuous") for x in CONTINUOUS_APCS])
    s_line = 2
    line_idx = 1
    for p_on_d in sorted(p_on_d_dict.keys()):
        act_line = s_line
        act_num = 0
        for apc_name in sorted(p_on_d_dict[p_on_d].keys()):
            apc_stuff = apc_dict[apc_lut[apc_name]]
            line_idx = 1 - line_idx
            act_outlets = p_on_d_dict[p_on_d][apc_name]
            out_f = [logging_tools.compress_num_list([onum for name, onum in act_outlets])]
            act_names = sorted([name for name, onum in act_outlets if name])
            if act_names:
                out_f.append(", ".join(["%s (outlet %d)" % (name, [onum for s_name, onum in act_outlets if s_name == name][0]) for name in act_names]))
            info_table[act_line]["class"] = "line1%d" % (line_idx)
            info_table[act_line][3] = html_tools.content("%s (%s)" % (apc_name,
                                                                      apc_type_dict.get(apc_stuff.get_apc_type(), "unknown [%s]" % (apc_stuff.get_apc_type()))), cls="left")
            info_table[act_line][4] = html_tools.content("; ".join(out_f), cls="left")
            act_num += len(act_outlets)
            act_line += 1
        info_table[s_line:act_line - 1][1] = html_tools.content("%s" % ({-1 : "never",
                                                                         0  : "immediately"}.get(p_on_d, logging_tools.get_plural("second", p_on_d))), cls="left")
        info_table[s_line:act_line - 1][2] = html_tools.content("%d" % (act_num), cls="left")
        s_line = act_line
    
    submit_button = html_tools.submit_button(req, "Submit")
    submit_button.set_class("", "button")
    red_flag[""] = 1
    out_str = "%s<div class=\"center\">Redistribute: %s%s</form>\n" % (info_table(""),
                                                                       submit_button(""),
                                                                       red_flag.create_hidden_var(""))
    req.write(out_str)

def apc_overview(req, apc_dict, bs_dict):
    scons_log = html_tools.message_log()
    bs_2_dict = {}
    for apc in apc_dict.values():
        if bs_dict.has_key(apc.get_bootserver()):
            bs_2_dict.setdefault(bs_dict[apc.get_bootserver()], []).append(apc.get_name())
            bs_2_dict[bs_dict[apc.get_bootserver()]].sort()
    c_dict, apc_bs_lut = ({}, {})
    for bs_name, apc_list in bs_2_dict.iteritems():
        c_dict[bs_name] = tools.s_command(req, "mother_server", 8001, "ping", apc_list, 10, bs_name)
        for apc_name in apc_list:
            apc_bs_lut[apc_name] = bs_name
    tools.iterate_s_commands(c_dict.values(), scons_log)
    apc_lut = {}
    #req.write(scons_log.generate_stack("Server connections"))
    for apc_idx, apc_struct in apc_dict.iteritems():
        apc_name = apc_struct.get_name()
        apc_struct.set_act_state(c_dict[apc_bs_lut[apc_name]].server_reply.get_node_result(apc_name))
        apc_lut[apc_name] = apc_idx
    apc_names = sorted(apc_lut.keys())
    down_names = [x for x in apc_names if apc_dict[apc_lut[x]].up_state == 0]
    req.write(html_tools.gen_hline("Overview of %s%s" % (logging_tools.get_plural("APC", len(apc_names)),
                                                         down_names and " (%d down)" % (len(down_names)) or ""), 2))
    info_table = html_tools.html_table(cls="normal")
    header_list = ["Name", "Type", "Version", "bootserver", "state", "IP", "outlets", "devgroups", "devices"]
    info_table[0]["class"] = "line00"
    for header in header_list:
        info_table[None][0] = html_tools.content(header, cls="center", type="th")
    line_idx = 1
    for apc_name in apc_names:
        apc_struct = apc_dict[apc_lut[apc_name]]
        line_idx = 1 - line_idx
        info_table[0]["class"] = apc_struct.up_state and "line1%d" % (line_idx) or "error"
        info_table[None][0] = html_tools.content(apc_name, cls="left")
        info_table[None][0] = html_tools.content(apc_struct.get_apc_type(), cls="center")
        info_table[None][0] = html_tools.content(apc_struct.get_apc_version(), cls="center")
        info_table[None][0] = html_tools.content(apc_struct.get_bootserver_name(), cls="center")
        info_table[None][0] = html_tools.content(apc_struct.get_act_state(), cls="center")
        info_table[None][0] = html_tools.content(apc_struct.ip, cls="center")
        devg_dict, info_str, device_list = get_apc_outlet_info_str(apc_struct)
        info_table[None][0] = html_tools.content(info_str, cls="center")
        info_table[None][0] = html_tools.content(", ".join(["%s (%d)" % (k, len(v)) for k, v in devg_dict.iteritems()]) or "no devices attached", cls="left")
        info_table[None][0] = html_tools.content(", ".join(device_list) or "no devices attached", cls="left")
    req.write(info_table(""))

def get_apc_outlet_info_str(apc_struct):
    devg_dict, devs = ({}, [])
    num_outlets = apc_struct.get_num_outlets()
    if num_outlets:
        for out_num, out_struct in apc_struct.outlets.iteritems():
            if out_struct["name"]:
                devs.append("%s (%d)" % (out_struct["name"], out_num))
                devg_dict.setdefault(out_struct["device_group_name"], []).append(out_struct["name"])
        devs.sort()
        if len(devs) == num_outlets:
            info_str = "all %d used" % (num_outlets)
        elif not len(devs):
            info_str = "none of %d used" % (num_outlets)
        else:
            info_str = "%s of %d used" % (len(devs) and str(len(devs)) or "none",
                                          num_outlets)
    else:
        info_str = "none found"
    return devg_dict, info_str, devs
    
def process_page(req):
    if req.conf["genstuff"].has_key("AUTO_RELOAD"):
        del req.conf["genstuff"]["AUTO_RELOAD"]
    functions.write_header(req)
    functions.write_body(req)
    # init log and status
    tools.init_log_and_status_fields(req)
    # apc tree
    apc_tree = tools.display_list(req)
    apc_tree.query(["AM"],
                   ["comment", "device_group", "device_type", "n.macadr", "n.devname", "n.netdevice_idx", "i.ip", "a.power_on_delay", "a.reboot_delay", "a.apc_type", "a.apc_device_idx", "a.version_info", "a.num_outlets"], 
                   [("netdevice", "n"), ("netip", "i"), ("apc_device", "a")],
                   ["d.bootserver", "n.device=d.device_idx", "i.netdevice=n.netdevice_idx", "a.device=d.device_idx"])
    # global selector
    glob_sel = html_tools.selection_list(req, "add_info", {"a" : "APC Overview",
                                                           "b" : "APC config",
                                                           "c" : "Power-on delays"})
    act_glob_sel = glob_sel.check_selection("", "a")
    if not apc_tree.devices_found():
        req.write(html_tools.gen_hline("No APCs found", 2))
    else:
        bs_list, apc_dict = ([], {})
        for ag in apc_tree.get_sorted_devg_idx_list():
            for apc in apc_tree.get_sorted_dev_idx_list(ag):
                apc_struct = apc_tree.get_dev_struct(apc)
                new_apc = cdef_device.apc(apc_struct["name"], apc_struct["device_idx"], apc_struct["device_group"], apc_struct["device_type"])
                apc_dict[new_apc.get_idx()] = new_apc
                new_apc.set_apc_delays(apc_struct["power_on_delay"], apc_struct["reboot_delay"])
                new_apc.set_apc_type_and_version(apc_struct["apc_type"], apc_struct["version_info"])
                new_apc.set_num_outlets(apc_struct["num_outlets"])
                new_apc.set_apc_device_idx(apc_struct["apc_device_idx"])
                new_apc.ip = apc_struct["ip"]
                if apc_struct["bootserver"]:
                    bs_list.append(apc_struct["bootserver"])
                    new_apc.set_bootserver(apc_struct["bootserver"])
        sql_str = "SELECT d.device_idx, d.name, dg.name AS device_group_name, d2.name AS slave_name, d2.device_idx AS slave_device_idx, m.* FROM device d, msoutlet m LEFT JOIN device d2 ON d2.device_idx=m.slave_device LEFT JOIN device_group dg ON dg.device_group_idx=d2.device_group WHERE m.device=d.device_idx AND (%s)" % (" OR ".join(["d.device_idx=%d" % (x) for x in apc_dict.keys()]))
        # lut: idx -> name
        dev_dict, dev_lut = ({}, {})
        req.dc.execute(sql_str)
        for rec in req.dc.fetchall():
            act_apc = apc_dict[rec["device_idx"]]
            act_apc.add_outlet(rec["outlet"], rec)
            if rec["slave_device_idx"]:
                act_apc.set_device(rec["outlet"], rec["slave_device_idx"], rec["slave_name"], rec["slave_info"], rec["device_group_name"])
                dev_dict.setdefault(rec["slave_name"], {"idx" : rec["slave_device_idx"], "outlets" : []})["outlets"].append((rec["device_idx"], rec["name"], rec["outlet"]))
                dev_lut[rec["slave_device_idx"]] = rec["slave_name"]
        dev_sel = html_tools.selection_list(req, "dev_sel", {}, size=5, sort_new_keys=0, multiple=True)
        for dev_name in sorted(dev_dict.keys()):
            dev_stuff = dev_dict[dev_name]
            dev_sel[dev_stuff["idx"]] = "%s on %s (%s)" % (dev_name, logging_tools.get_plural("outlet", len(dev_stuff["outlets"])), ",".join(["%s/%d" % (x, y) for n, x, y in dev_stuff["outlets"]]))
        act_dev_sel = dev_sel.check_selection("", [])
        if bs_list:
            req.dc.execute("SELECT d.device_idx, d.name FROM device d WHERE (%s)" % (" OR ".join(["d.device_idx=%d" % (x) for x in bs_list])))
            bs_dict = dict([(x["device_idx"], x["name"]) for x in req.dc.fetchall()])
        else:
            bs_dict = {}
        for ag in apc_tree.get_sorted_devg_idx_list():
            for apc in apc_tree.get_sorted_dev_idx_list(ag):
                apc_struct = apc_dict[apc]
                if apc_struct.get_bootserver():
                    bs_name = bs_dict.get(apc_struct.get_bootserver(), "<not found>")
                    apc_struct.set_bootserver(apc_struct.get_bootserver(), bs_name)
                    bs_string = "bs=%s" % (bs_name)
                else:
                    bs_string = "no bs"
                apc_tree.get_dev_struct(apc)["post_str"] = " %s" % (bs_string)
        submit_button = html_tools.submit_button(req, "select")
        submit_button.set_class("", "button")
        sel_table = html_tools.html_table(cls = "blindsmall")
        sel_table[0][0] = html_tools.content(apc_tree, "devg", cls="center")
        sel_table[None][0] = html_tools.content(apc_tree, "dev", cls="center")
        sel_table[None][0] = html_tools.content(dev_sel, "", cls="center")
        sel_table[0][0:3] = html_tools.content(["Actual displaytype is ", glob_sel, ", ", submit_button], cls="center")
        out_str = "<form action=\"%s.py?%s\" method = post>\n%s</form>\n" % (req.module_name, functions.get_sid(req),
                                                                             sel_table(""))
        req.write(out_str)
        out_str = "<form action=\"%s.py?%s\" method = post>%s%s%s" % (req.module_name,
                                                                      functions.get_sid(req),
                                                                      glob_sel.create_hidden_var(""),
                                                                      dev_sel.create_hidden_var(""),
                                                                      apc_tree.get_hidden_sel())
        req.write(out_str)
        if act_glob_sel == "a":
            apc_overview(req, apc_dict, bs_dict)
        elif act_glob_sel == "b":
            apc_config(req, apc_tree, apc_dict, bs_dict, dev_dict, [dev_lut[x] for x in act_dev_sel])
        elif act_glob_sel == "c":
            apc_power_on_delays(req, apc_dict, bs_dict)
        else:
            req.write(html_tools.gen_hline("Unsupported mode '%s'" % (act_glob_sel), 2))
        req.write("</form>\n")
        
