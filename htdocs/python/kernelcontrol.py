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
""" browse and add kernels """

import functions
import logging_tools
import os, os.path
import tools
import html_tools
import cdef_kernels
import pprint
    
def module_info():
    return {"kc" : {"description"           : "Kernel control",
                    "default"               : 0,
                    "enabled"               : 1,
                    "left_string"           : "Kernel control",
                    "right_string"          : "Check for kernels and modify initrds",
                    "priority"              : -90,
                    "capability_group_name" : "conf"}}

def scan_for_new_kernels(req, kernel_servers, action_log, kernel_tree):
    new_kernels = {}
    # get list from kernel_servers
    c_list = []
    for m_name, m_role in kernel_servers.iteritems():
        srv_found = False
        if req.conf["server"].get("mother_server", {}).has_key(m_name):
            c_list.append(tools.s_command(req, "mother_server", 8001, "check_kernel_dir", [], 10, m_name))
            srv_found = True
        if req.conf["server"].get("xen_server", {}).has_key(m_name):
            c_list.append(tools.s_command(req, "xen_server", 8019, "check_kernel_dir", [], 10, m_name))
            srv_found = True
        if not srv_found:
            action_log.add_error("No role (mother or xen) for %s found" % (str(m_name)), "internal")
    if c_list:
        tools.iterate_s_commands(c_list, action_log)
        for com in c_list:
            if com.get_state() == "o" and com.server_reply.get_option_dict():
                opt_dict = com.server_reply.get_option_dict()
                kernel_problems = {}
                for prob in sorted(opt_dict.get("problems", [])):
                    action_log.add_warn(prob, "mother")
#                     prob_type, prob_location, prob_cause = prob.split(None, 2)
#                     kern_name = os.path.basename(prob_location)
#                     kernel_problems.setdefault(kern_name, []).append((prob_type, prob_cause))
                if type(opt_dict.get("kernels_found", [])) == type({}):
                    action_log.add_warn("old-style mother found on %s" % (com.get_hostname()), "internal")
                else:
                    for k_found in opt_dict.get("kernels_found", []):
                        if k_found in kernel_tree.keys():
                            # no longer needed
                            pass
                        else:
                            if not new_kernels.has_key(k_found):
                                new_kernels[k_found] = cdef_kernels.new_kernel(req, k_found)
                            new_kernels[k_found].add_machine(com.get_hostname(), "mother" if com.port == 8001 else "xen")
#                     for k_found, k_stuff in opt_dict.get("kernels_found", {}).iteritems():
#                         if k_found in kernel_tree.keys():
#                             kernel_tree[k_found].add_kernel_info_from_machine(com.get_hostname(), k_stuff)
#                         elif not new_kernels.has_key(k_found):
#                             new_kernels[k_found] = cdef_kernels.new_kernel(req, k_found)
#                         new_kernels[k_found].add_kernel_info_from_machine(com.get_hostname(), k_stuff)
#                     for prob_kern, prob_list in kernel_problems.iteritems():
#                         print prob_kern, prob_list
#                         if kernel_tree.has_key(prob_kern):
#                             kernel_tree[prob_kern].add_problem_from_machine(com.get_hostname(), prob_list)
#                         elif notnew_kernels.has_key(prob_kern):
#                             new_kernels[prob_kern].add_problem_from_machine(com.get_hostname(), prob_list)
#                         else:
#                             for prob_type, prob_cause in prob_list:
#                                 action_log.add_warn("on server %s: %s" % (com.get_hostname(), "%s %s %s" % (prob_type, prob_kern, prob_cause)), "server")
    return new_kernels

def check_kernel_consistency(req, cons_dict, action_log, kernel_tree):
    # get list from kernel_servers
    send_dict = {}
    for k_name, m_names in cons_dict.iteritems():
        for m_name, m_role in m_names:
            send_dict.setdefault(m_name, []).append(k_name)
    c_list = []
    for m_name, k_list in send_dict.iteritems():
        srv_found = False
        if req.conf["server"].get("mother_server", {}).has_key(m_name):
            c_list.append(tools.s_command(req, "mother_server", 8001, "check_kernel_dir", [], 10, m_name, {"check_list" : k_list}))
            srv_found = True
        if req.conf["server"].get("xen_server", {}).has_key(m_name):
            c_list.append(tools.s_command(req, "xen_server", 8019, "check_kernel_dir", [], 10, m_name, {"check_list" : k_list}))
            srv_found = True
        if not srv_found:
            action_log.add_error("No role (mother or xen) for %s found" % (str(m_name)), "internal")
    if c_list:
        tools.iterate_s_commands(c_list, action_log)
        for com in c_list:
            if com.get_state() == "o" and com.server_reply.get_option_dict():
                opt_dict = com.server_reply.get_option_dict()
                kernel_problems = {}
                for prob in sorted(opt_dict.get("problems", [])):
                    prob_type, prob_location, prob_cause = prob.split(None, 2)
                    kern_name = os.path.basename(prob_location)
                    kernel_problems.setdefault(kern_name, []).append((prob_type, prob_cause))
                if type(opt_dict.get("kernels_found", [])) == type({}):
                    action_log.add_warn("old-style mother found on %s" % (com.get_hostname()), "internal")
                else:
                    for k_found in opt_dict.get("kernels_found", []):
                        pass
#                 for k_found, k_stuff in opt_dict.get("kernels_found", {}).iteritems():
#                     if k_found in kernel_tree.keys():
#                         kernel_tree[k_found].add_kernel_info_from_machine(com.get_hostname(), k_stuff)
#                 for prob_kern, prob_list in kernel_problems.iteritems():
#                     if kernel_tree.has_key(prob_kern):
#                         kernel_tree[prob_kern].add_problem_from_machine(com.get_hostname(), prob_list)

def sync_kernels(req, sync_list, action_log):
    # get list from kernel_servers
    send_dict = {}
    for k_name, (m_name, m_role), s_names in sync_list:
        send_dict.setdefault((m_name, m_role), {})[k_name] = s_names
    c_list = []
    for (m_name, m_role), opt_dict in send_dict.iteritems():
        if req.conf["server"].get("mother_server", {}).has_key(m_name) and m_role == "mother":
            c_list.append(tools.s_command(req, "mother_server", 8001, "sync_kernels", [], 10, m_name, opt_dict))
        elif req.conf["server"].get("xen_server", {}).has_key(m_name) and m_role == "xen":
            c_list.append(tools.s_command(req, "xen_server", 8019, "sync_kernels", [], 10, m_name, opt_dict))
        else:
            action_log.add_error("No role (mother or xen) for %s found" % (str(m_name)), "internal")
    if c_list:
        tools.iterate_s_commands(c_list, action_log)

def process_page(req):
    if req.conf["genstuff"].has_key("AUTO_RELOAD"):
        del req.conf["genstuff"]["AUTO_RELOAD"]
    functions.write_header(req)
    functions.write_body(req)
    #pprint.pprint(req.conf["server"])
    action_log = html_tools.message_log()
    # basic buttons
    select_button = html_tools.submit_button(req, "select")
    submit_button = html_tools.submit_button(req, "submit")
    scan_for_kernels = req.sys_args.has_key("fetchkernels")
    take_new_kernel_list = html_tools.selection_list(req, "tnk", {}, sort_new_keys=0, auto_reset=1)
    for idx, wtd in [(0, "-- nothing --"),
                     (1, "take"),
                     (2, "take and ignore build device")]:
        take_new_kernel_list[idx] = wtd
    take_new_kernel_list.mode_is_normal()
    # kernel server
    kernel_servers = req.conf["server"].get("kernel_server", {})
    # read kernel tree
    kernel_tree = cdef_kernels.fetch_kernel_tree(req, action_log)
    if scan_for_kernels:
        new_kernels = scan_for_new_kernels(req, kernel_servers, action_log, kernel_tree)
        new_kernel_names = sorted(new_kernels.keys())
        take_commands = []
        for nk_name in new_kernel_names:
            nk_stuff = new_kernels[nk_name]
            nk_device, nk_role = nk_stuff.get_take_device()
            nk_action = take_new_kernel_list.check_selection(nk_stuff.get_suffix(), 0)
            if nk_action:
                take_commands.append(tools.s_command(req, "kernel_server", 8001 if nk_role == "mother" else 8019, "check_kernel_dir", [], 10, nk_device, {"kernels_to_insert"           : [nk_name],
                                                                                                                                                          "ignore_kernel_build_machine" : nk_action == 2 and True or False}))
        if take_commands:
            tools.iterate_s_commands(take_commands, action_log)
            kernel_tree.fetch()
            kernel_tree.check_for_changes()
        for k_name in kernel_tree.keys():
            if new_kernels.has_key(k_name):
                del new_kernels[k_name]
        new_kernel_names = sorted(new_kernels.keys())
        req.write(html_tools.gen_hline("Found %s (%s in database):" % (logging_tools.get_plural("new kernel", len(new_kernels.keys())),
                                                                       logging_tools.get_plural("kernel", len(kernel_tree.keys()))),
                                       2))
        if new_kernels:
            req.write("<form action=\"%s.py?%s&fetchkernels\" method=post>" % (req.module_name,
                                                                           functions.get_sid(req)))
            #req.write(html_tools.gen_hline("Found %s not present in database on %s:" % (logging_tools.get_plural("new kernel", len(new_kernels.keys())),
            #                                                                            logging_tools.get_plural("server", len(mother_servers.keys()))), 3))
            nkern_table = html_tools.html_table(cls="normalsmall")
            nkern_table[0]["class"] = "line00"
            for head in ["Name", "Server", "action", "device"]:
                nkern_table[None][0] = html_tools.content(head, type="th", cls="center")
            req.write(nkern_table.get_header())
            req.write(nkern_table.flush_lines())
            line_idx = 1
            for nk_name in new_kernel_names:
                line_idx = 1 - line_idx
                act_kernel = new_kernels[nk_name]
                nkern_table[0]["class"] = "line1%d" % (line_idx)
                nkern_table[None][0] = html_tools.content(act_kernel.get_name()       , cls="left")
                nkern_table[None][0] = html_tools.content(act_kernel.get_server_info(), cls="left")
                nkern_table[None][0] = html_tools.content(take_new_kernel_list        , cls="left")
                nkern_table[None][0] = html_tools.content(act_kernel.get_device_list(), cls="left")
                req.write(nkern_table.flush_lines(act_kernel.get_suffix()))
            req.write(nkern_table.get_footer())
            req.write("<div class=\"center\">%s</div>%s%s</form>" % (submit_button(""),
                                                                     kernel_tree.disp_list.create_hidden_var(""),
                                                                     kernel_tree.kernel_regex.create_hidden_var("")))
        req.write("<div class=\"center\"><a href=\"%s.py?%s&%s[]=sk\">Return to Kernelpage</a></div></form>" % (req.module_name,
                                                                                                                functions.get_sid(req),
                                                                                                                kernel_tree.disp_list.name))
    else:
        kernel_tree.fetch_local_info()
        # check for kernel_delete
        kernel_tree.check_for_changes()
        cak_dict = kernel_tree.get_consistency_action_kernels()
        if cak_dict:
            # cons_check list
            cons_dict = dict([(name, kernel_tree.all_kernel_servers) for name, value in cak_dict.iteritems() if value == 1])
            if cons_dict:
                check_kernel_consistency(req, cons_dict, action_log, kernel_tree)
            # sync dict
            sync_list = [(name, (kernel_tree[name].master_name, kernel_tree[name].master_role), kernel_tree[name].get_kernel_machines(with_master=False) if value == 2 else \
                              [s_name for s_name in kernel_tree.all_kernel_servers if s_name != (kernel_tree[name].master_name, kernel_tree[name].master_role)]) for name, value in cak_dict.iteritems() if value in [2, 3]]
            #print cons_dict, sync_list
            if sync_list:
                sync_kernels(req, sync_list, action_log)
        req.write("<form action=\"%s.py?%s\" method=post><div class=\"center\">" % (req.module_name,
                                                                                    functions.get_sid(req)) + \
                      "Show %s, kernel_filter %s, %s</div></form>" % (kernel_tree.disp_list(""),
                                                                      kernel_tree.kernel_regex(""),
                                                                      select_button("")))
        req.write("<form action=\"%s.py?%s\" method=post>%s%s" % (req.module_name,
                                                                  functions.get_sid(req),
                                                                  kernel_tree.disp_list.create_hidden_var(""),
                                                                  kernel_tree.kernel_regex.create_hidden_var("")))
        k_found = False
        if kernel_tree:
            if len(kernel_tree.keys()):
                k_found = True
                req.write(html_tools.gen_hline("Found %s in database:" % (logging_tools.get_plural("kernel", len(kernel_tree.keys()))), 2))
                # show kernels
                kernel_tree.show_table()
            else:
                req.write(html_tools.gen_hline("Found no kernels in database", 2))
        else:
            req.write(html_tools.gen_hline("Found no kernels in database", 2))
        req.write("<div class=\"center\">%s<a href=\"%s.py?%s&fetchkernels\">Scan for new kernels</a></div></form>" % ("%s or " % (submit_button("")) if k_found else "",
                                                                                                                       req.module_name,
                                                                                                                       functions.get_sid(req)))
    req.write(action_log.generate_stack("Log"))
        
