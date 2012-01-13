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

import functions
import logging_tools
import html_tools
import tools
import time
import sys
import configfile
import process_tools
import pprint
import sge_tools

def module_info():
    return {"jsqm" : {"description"           : "Queue information (SGE)",
                      "enabled"               : True,
                      "default"               : True,
                      "left_string"           : "Queue information",
                      "right_string"          : "Show and modify Queue settings",
                      "priority"              : 50,
                      "capability_group_name" : "rms"}}

class sge_server(object):
    def __init__(self, req, action_log, name, ip_address, active_submit):
        self.__req = req
        self.__action_log = action_log
        self.__dc = req.dc
        self.__active_submit = active_submit
        self.name = name
        self.ip = ip_address
        is_server, self.server_idx, server_type, server_str, self.config_idx, real_server_name = process_tools.is_server(self.__dc, "sge_server", True, True, self.name)
        # server active for user ?
        self.active = False
        if self.__req.user_info.capability_ok("sacl"):
            # flag show all cells set
            self.active = True
        else:
            sql_str = "SELECT * FROM sge_user_con sc, device_config dc WHERE sc.user=%d AND sc.sge_config=dc.device_config_idx AND dc.new_config=%d" % (self.__req.session_data.user_idx, self.config_idx)
            self.__dc.execute(sql_str)
            if self.__dc.rowcount:
                # member of cell
                self.active = True
        if self.active:
            self.conf = configfile.read_global_config(self.__dc, "sge_server", host_name=self.name)
        # queue member
        self.__queue_member = html_tools.checkbox(self.__req, "qmem")
        self.__old_member_dict, self.__new_member_dict = ({}, {})
    def __getitem__(self, key):
        return self.conf[key]
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        print what, log_level
    def get_sge_configs(self, act_rms_tree):
        success = False
        self.queue_dict = {}
        ds_command = tools.s_command(self.__req, "sge_server", 8009, "get_config", [], 10, self.name)
        tools.iterate_s_commands([ds_command], self.__action_log)
        if ds_command.server_reply:
            if ds_command.get_state() == "o":
                opt_dict = ds_command.server_reply.get_option_dict()
                try:
                    self.__sge_info = sge_tools.sge_info(is_active=False,
                                                         log_command=self.log,
                                                         init_dicts=opt_dict)
                except:
                    self.__action_log.add_error("Error building sge_info: %s" % (process_tools.get_except_info()), "internal")
                    self.__sge_info = None
                else:
                    success = True
            else:
                self.__action_log.add_error("Error connecting to sge-server", "SGE")
        return success
    def show_queue_matrix(self):
        all_q_names = self.__sge_info["queueconf"].keys()
        all_e_hosts = self.__sge_info["qhost"].keys()
        if all_e_hosts and all_q_names:
            self.__req.write(html_tools.gen_hline("Queue Matrix, %s and %s" % (logging_tools.get_plural("Queue", len(all_q_names)),
                                                                               logging_tools.get_plural("Execution host", len(all_e_hosts))), 2))
            q_mat = html_tools.html_table(cls="normalsmall")
            q_mat[0]["class"] = "lineh"
            q_mat[None][0] = html_tools.content("Exec host \ Queue", type="th", cls="center")
            for q_name in all_q_names:
                self.__sge_info.expand_host_list(q_name, True)
                q_mat[None][0] = html_tools.content(q_name, type="th", cls="center")
                self.__new_member_dict[q_name] = {}
                self.__old_member_dict[q_name] = {}
            line_idx = 0
            for e_host in sorted(all_e_hosts):
                line_idx = 1 - line_idx
                q_mat[0]["class"] = "line1%d" % (line_idx)
                q_mat[None][0] = html_tools.content(e_host, cls="left")
                for q_name in all_q_names:
                    act_pf = "%dx%d" % (all_e_hosts.index(e_host),
                                        all_q_names.index(q_name))
                    self.__old_member_dict[q_name][e_host] = e_host in self.__sge_info["queueconf"][q_name]["hostlist"]
                    if self.__active_submit:
                        self.__new_member_dict[q_name][e_host] = self.__queue_member.check_selection(act_pf)
                    else:
                        self.__new_member_dict[q_name][e_host] = self.__old_member_dict[q_name][e_host]
                        self.__queue_member[act_pf] = self.__old_member_dict[q_name][e_host]
                    q_mat[None][0] = html_tools.content(self.__queue_member, act_pf, cls="center")
            self.__req.write(q_mat(""))
        else:
            self.__req.write(html_tools.gen_hline("No Queue Matrix (%s and %s)" % (logging_tools.get_plural("Queue", len(all_q_names)),
                                                                                   logging_tools.get_plural("Execution host", len(all_e_hosts))), 2))
    def check_for_changes(self):
        mod_dict = {"aattr" : {},
                    "dattr" : {}}
        for q_name, q_stuff in self.__old_member_dict.iteritems():
            for h_name, h_flag in q_stuff.iteritems():
                if h_flag and not self.__new_member_dict[q_name][h_name]:
                    mod_dict["dattr"].setdefault(q_name, []).append(h_name)
                elif not h_flag and self.__new_member_dict[q_name][h_name]:
                    mod_dict["aattr"].setdefault(q_name, []).append(h_name)
        
        com_list = []
        for com, com_stuff in mod_dict.iteritems():
            for q_name, h_list in com_stuff.iteritems():
                command = "-%s queue hostlist %s %s" % (com,
                                                        ",".join(h_list),
                                                        q_name)
                com_list.append(tools.s_command(self.__req, "sge_server", 8009, "call_qconf", [], 10, self.name, add_dict={"command" : command}))
        if com_list:
            tools.iterate_s_commands(com_list, self.__action_log)

class rms_tree(object):
    def __init__(self, req, action_log, active_submit):
        self.__req = req
        self.__dc = req.dc
        self.cell_list = html_tools.selection_list(self.__req, "cellsel", {}, sort_new_key=False)
        self.__sge_server, self.active_sge_servers = ({}, [])
        for s_name, s_ip in self.__req.conf["server"].get("sge_server", {}).iteritems():
            new_sge_server = sge_server(self.__req, action_log, s_name, s_ip, active_submit)
            self.__sge_server[s_name] = new_sge_server
            if new_sge_server.active:
                self.active_sge_servers.append(s_name)
                self.active_sge_servers.sort()
        if self.active_sge_servers:
            for srv in self.active_sge_servers:
                act_srv = self[srv]
                self.cell_list[srv] = "%s on %s (SGE %s.%s, architecture %s)" % (act_srv["SGE_CELL"],
                                                                                 act_srv.name,
                                                                                 act_srv["SGE_VERSION"],
                                                                                 act_srv["SGE_RELEASE"],
                                                                                 act_srv["SGE_ARCH"])
            self.cell_list.mode_is_normal()
            self.active_sge_server = self.cell_list.check_selection("", self.active_sge_servers[0])
    def single_server(self):
        return len(self.active_sge_servers) == 1
    def __getitem__(self, key):
        return self.__sge_server[key]

def process_page(req):
    functions.write_header(req)
    functions.write_body(req)
    if req.conf["genstuff"].has_key("AUTO_RELOAD"):
        del req.conf["genstuff"]["AUTO_RELOAD"]
    low_submit = html_tools.checkbox(req, "sub")
    action_log = html_tools.message_log()
    act_rms_tree = rms_tree(req, action_log, low_submit.check_selection(""))
    if act_rms_tree.active_sge_servers:
        low_submit[""] = 1
        submit_button = html_tools.submit_button(req, "submit")
        req.write("<form action=\"%s.py?%s\" method = post>" % (req.module_name,
                                                                functions.get_sid(req)))
        if not act_rms_tree.single_server():
            req.write(html_tools.gen_hline("User %s has access to %s: %s" % (req.user_info["login"],
                                                                             logging_tools.get_plural("SGE cell", len(act_rms_tree.active_sge_servers)),
                                                                             
                                                                             act_rms_tree.cell_list("")), 2, False))
        act_sge_server = act_rms_tree[act_rms_tree.active_sge_server]
        if act_sge_server.get_sge_configs(act_rms_tree):
            act_sge_server.show_queue_matrix()
            act_sge_server.check_for_changes()
        req.write(action_log.generate_stack("Action log"))
        req.write("%s<div class=\"center\">%s</div>\n" % (low_submit.create_hidden_var(),
                                                          submit_button()))
        req.write("</form>")
    else:
        req.write(html_tools.gen_hline("User has no access to any SGE-Cell", 2))
