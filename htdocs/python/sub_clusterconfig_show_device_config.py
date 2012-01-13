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

import html_tools
import logging_tools
import tools
import array

def get_sel_list(req, pf):
    return (html_tools.selection_list(req, pf, {"o0" : "show nothing",
                                                "o1" : "small for selected",
                                                "o2" : "small for all",
                                                "o3" : "with content for selected",
                                                "o4" : "with content for all",
                                                "o5" : "recreate, small for selected",
                                                "o6" : "recreate, small for all",
                                                "o7" : "recreate, with content for selected",
                                                "o8" : "recreate, with content for all"},
                                      initial_mode="n", log_validation_errors=0),
            "o0")
    
def create_config(req, dev_tree, dev_dict, change_log, sel_pf):
    create_conf = sel_pf in ["o5", "o6", "o7", "o8"]
    dg_sel, d_sel, dg_sel_eff = dev_tree.get_selection()
    srv_dict = {}
    if d_sel:
        for dg in dg_sel_eff:
            for dev in [x for x in d_sel if x in dev_tree.get_sorted_dev_idx_list(dg)]:
                act_dev = dev_dict[dev]
                if act_dev.get_bootserver():
                    srv_dict.setdefault(dev_dict[act_dev.get_bootserver()].get_name(), []).append(act_dev.get_name())
        if srv_dict:
            srv_dict = dict([(server, tools.s_command(req, "config_server", 8005, "create_config", nodes, 10, server)) for server, nodes in srv_dict.iteritems()])
            if create_conf:
                tools.iterate_s_commands(srv_dict.values(), change_log)
    return srv_dict
    
def show_config(req, dev_tree, dev_dict, srv_dict, sel_pf, selected_confs):
    if srv_dict and sel_pf != "o0":
        # extract flags
        create_conf = sel_pf in ["o5", "o6", "o7", "o8"]
        show_small = sel_pf in ["o1", "o2", "o5", "o6"]
        show_only_selected = sel_pf in ["o1", "o3", "o5", "o7"]
        dg_sel, d_sel, dg_sel_eff = dev_tree.get_selection()
        if show_small:
            header_list = ["type", "#ref", "uid", "gid", "mode", "dest", "info", "config"]
        else:
            header_list = ["type", "#ref", "uid", "gid", "mode", "dest", "config"]
        req.dc.execute("SELECT wc.* FROM wc_files wc WHERE %s ORDER BY wc.device, wc.dest_type, wc.dest" % (" OR ".join(["wc.device=%d" % (x) for x in d_sel])))
        for db_rec in req.dc.fetchall():
            dev_dict[db_rec["device"]].wc_files.append(db_rec)
        config_table = html_tools.html_table(cls="normal")
        req.write(html_tools.gen_hline("Config result", 2))
        req.write(config_table.get_header())
        for dg in dg_sel_eff:
            config_table[1][1 : len(header_list)] = html_tools.content(dev_tree.get_sel_dev_str(dg), cls="devgroup")
            req.write(config_table.flush_lines())
            line_idx = 1
            for dev in [x for x in d_sel if x in dev_tree.get_sorted_dev_idx_list(dg)]:
                act_dev = dev_dict[dev]
                line_idx = 1 - line_idx
                config_table[0]["class"] = "line0%d" % (line_idx)
                if act_dev.get_bootserver():
                    if create_conf:
                        s_reply = srv_dict[dev_dict[act_dev.get_bootserver()].get_name()].server_reply
                        if s_reply:
                            if s_reply.get_state():
                                config_table[None][0 : len(header_list)] = html_tools.content("%s on bootserver %s: error creating config (%d): %s; showing config from DB" % (act_dev.get_name(),
                                                                                                                                                                               dev_dict[act_dev.get_bootserver()].get_name(),
                                                                                                                                                                               s_reply.get_state(),
                                                                                                                                                                               s_reply.get_result()), cls="error")
                            else:
                                config_table[None][0 : len(header_list)] = html_tools.content("%s: %s" % (act_dev.get_name(), s_reply.get_node_result(act_dev.get_name())))
                        else:
                            config_table[None][0 : len(header_list)] = html_tools.content("no server-reply for %s from server %s" % (act_dev.get_name(), dev_dict[act_dev.get_bootserver()].get_name()),
                                                                                          cls="center",
                                                                                          type="th")
                    else:
                        config_table[None][0 : len(header_list)] = html_tools.content("%s on bootserver %s" % (act_dev.get_name(), dev_dict[act_dev.get_bootserver()].get_name()))
                    config_table[0]["class"] = "line0%d" % (line_idx)
                    for what in header_list:
                        config_table[None][0] = html_tools.content(what, type="th")
                    line1_idx = 0
                    for conf_file in act_dev.wc_files:
                        act_confs = conf_file["config"].split(",")
                        if not show_only_selected or len([True for act_conf in act_confs if act_conf in selected_confs]):
                            line1_idx = 1 - line1_idx
                            act_dt = conf_file["dest_type"]
                            if conf_file["error_flag"]:
                                config_table[0]["class"] = "errormin"
                            else:
                                config_table[0]["class"] = "line1%d" % (line1_idx)
                            config_table[None][0] = html_tools.content({"c" : "copy",
                                                                        "f" : "file",
                                                                        "l" : "link",
                                                                        "d" : "dir",
                                                                        "e" : "erase",
                                                                        "i" : "internal"}.get(act_dt, "%s is unknown type" % (str(act_dt))), cls="center")
                            config_table[None][0] = html_tools.content(act_dt == "i" and "-" or conf_file["disk_int"], cls="center")
                            config_table[None][0] = html_tools.content(act_dt == "i" and "-" or conf_file["uid"], cls="center")
                            config_table[None][0] = html_tools.content(act_dt == "i" and "-" or conf_file["gid"], cls="center")
                            config_table[None][0] = html_tools.content(act_dt == "i" and "-" or conf_file["mode"], cls="center")
                            config_table[None][0] = html_tools.content(conf_file["dest"], cls="left")
                            if show_small:
                                if act_dt in ["c", "l"]:
                                    info_str = "from %s" % (conf_file["source"])
                                elif act_dt in ["f"]:
                                    act_content = conf_file["content"]
                                    if type(conf_file["content"]) == type(array.array("b")):
                                        act_content = act_content.tostring()
                                    lines = act_content.split("\n")
                                    info_str = "%s in %s" % (logging_tools.get_plural("Byte", len(act_content)), logging_tools.get_plural("line", len(lines)))
                                else:
                                    info_str = "-"
                                config_table[None][0] = html_tools.content(info_str, cls="left")
                            config_table[None][0] = html_tools.content(conf_file["config"], cls="left")
                            if not show_small:
                                if act_dt in ["c", "l"]:
                                    config_table[0]["class"] = "line1%d" % (line1_idx)
                                    config_table[None][0 : 7] = html_tools.content("Source: %s" % (conf_file["source"]), cls="left")
                                elif act_dt in ["f"]:
                                    act_content = conf_file["content"]
                                    if type(conf_file["content"]) == type(array.array("b")):
                                        act_content = act_content.tostring()
                                    lines = act_content.split("\n")
                                    max_width, max_height = (min(max([len(x) for x in lines]), 100), min(len(lines), 20))
                                    act_ta = html_tools.text_area(req, "", min_col_col_size=30, max_col_size=max_width, min_row_size=1, max_row_size=max_height, readonly=1)
                                    act_ta[""] = act_content
                                    config_table[0]["class"] = "line1%d" % (line1_idx)
                                    config_table[None][0 : 7] = html_tools.content(act_ta, "", cls="left", beautify = 0)
                else:
                    config_table[None][0 : len(header_list)] = html_tools.content("%s: %s" % (act_dev.get_name(), "No bootserver; hence no config"))
                req.write(config_table.flush_lines())
        req.write(config_table.get_footer())
