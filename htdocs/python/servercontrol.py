#!/usr/bin/python -Ot
# -*- coding: utf-8 -*-
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2012 Andreas Lang-Nevyjel, init.at
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
import html_tools
import tools
import logging_tools
import server_command
import time

def module_info():
    return {"csc" : {"description"           : "Server configuration",
                     "enabled"               : 1,
                     "default"               : 0,
                     "left_string"           : "Servercontrol",
                     "right_string"          : "Control the clusterservers",
                     "priority"              : 0,
                     "capability_group_name" : "conf"}}

# server_task: cluster_task on a given node
class server_task(object):
    def __init__(self, req, ct_type, ct_name, host_name, in_dict):
        self.__ct_name = ct_name
        self.__host_name = host_name
        # server or node
        self.__ct_type = ct_type
        # parse dict
        self.__state = in_dict["state"]
        self.__state_info = in_dict.get("state_info", "old version")
        self.__pids = in_dict.get("pids", {})
        self.__mem_info = in_dict.get("mem", None)
        self.__sql_info = in_dict.get("sql", None)
        self.__html_sel_list = html_tools.selection_list(req, "ctc", {}, sort_new_keys=0, auto_reset=1)
        self.__c_dict = {}
        self.__html_sel_list[0] = " -- nothing --"
        if self.is_running():
            self.__c_dict[2] = "stop"
        else:
            self.__c_dict[1] = "start"
        self.__c_dict[3] = "restart"
        for c_key in sorted(self.__c_dict.keys()):
            self.__html_sel_list[c_key] = self.__c_dict[c_key]
    def get_host_name(self):
        return self.__host_name
    def get_suffix(self):
        return self.__suffix
    def set_html_suffix(self, suffix):
        self.__suffix = suffix
        act_ct_mode = self.__html_sel_list.check_selection(self.__suffix, 0)
        if act_ct_mode not in self.__c_dict.keys():
            act_ct_mode = 0
        self.__serv_mode = self.__c_dict.get(act_ct_mode, "")
    def get_service_mode(self):
        return self.__serv_mode
    def get_html_sel_list(self):
        return self.__html_sel_list
    def is_configured(self):
        if self.__ct_type == "node":
            if self.__state == 5:
                return False
            else:
                return True
        else:
            if type(self.__sql_info) == type({}):
                # old cluster-servers
                return self.__sql_info["num_srv"] and True or False
            else:
                return self.__sql_info.num_servers and True or False
    def is_running(self):
        #print self.__ct_type, self.__ct_name, self.__host_name, self.__state, self.__state_info
        if self.__state:
            return False
        else:
            if type(self.__state_info) == type(""):
                if self.__state_info.lower() == "running":
                    self.__run_info = "running"
                    return True
                else:
                    return False
            else:
                num_r, num_f, r_time = self.__state_info
                self.__run_info = "running"
                return num_r == num_f
    def get_run_info(self, with_pids):
        if with_pids and type(self.__state_info) == type(()):
            num_r, num_f, r_time = self.__state_info
            return "%s %s [%s]" % (logging_tools.get_plural("thread", num_r),
                                   self.__run_info,
                                   ",".join(["%d%s" % (k, self.__pids[k] > 1 and " (%d)" % (self.__pids[k]) or "") for k in sorted(self.__pids.keys())]))
        else:
            return self.__run_info
    def get_memory_info(self):
        ms = self.__mem_info
        if ms is None:
            return "???"
        else:
            if ms < 1024:
                return "%d Bytes" % (ms)
            elif ms < 1024 * 1024:
                return "%.2f kBytes" % (ms / 1024.)
            else:
                return "%.2f MBytes" % (ms / (1024. * 1024.))
    def get_time_info(self):
        if type(self.__state_info) == type(()):
            num_r, num_f, pid_time = self.__state_info
            diff_time  = max(0, time.mktime(time.localtime()) - pid_time)
            diff_days  = int(diff_time / (3600 * 24))
            diff_hours = int((diff_time - 3600 * 24 * diff_days) / 3600)
            diff_mins  = int((diff_time - 3600 * (24 * diff_days + diff_hours)) / 60 )
            diff_secs  = int(diff_time - 60 * (60 * (24 * diff_days + diff_hours) + diff_mins))
            return " for %s%02d:%02d:%02d (%s)" % (diff_days and "%s, " % (logging_tools.get_plural("day", diff_days)) or "",
                                                   diff_hours, diff_mins, diff_secs,
                                                   time.strftime("%a, %d. %b %Y, %H:%M:%S", time.localtime(pid_time)))
        else:
            return "N/A"
    def get_sql_info(self):
        if self.__ct_type == "node":
            return "N/A"
        else:
            if type(self.__sql_info) == type(""):
                return self.__sql_info
            else:
                sql_dict = self.__sql_info
                return "%s (%s)" %  (sql_dict["server_str"],
                                     sql_dict["real_server_name"])
            


# cluster_task: general task
class cluster_task(object):
    def __init__(self, req, name, in_dict):
        self.__req = req
        self.__name = name
        self.__hosts = []
        self.__server_task_dict = {}
        self.__task_type = type(in_dict["sql"]) == type("") and "node" or "server"
    def get_task_name(self):
        return self.__name
    def add_host(self, host, in_dict):
        self.__hosts.append(host)
        self.__hosts.sort()
        self.__server_task_dict[host] = server_task(self.__req, self.__task_type, self.__name, host, in_dict)
    def set_html_suffixes(self, ct_lut, host_lut):
        [v.set_html_suffix("ct_%d_%d" % (ct_lut[self.__name], host_lut[k])) for k, v in self.__server_task_dict.iteritems()]
    def get_host_server_task(self, host):
        return self.__server_task_dict[host]
    def has_host(self, host):
        return host in self.__hosts
    def get_hosts(self):
        return self.__hosts
    def get_task_type(self):
        return self.__task_type
        
def parse_cluster_tasks(req, st_dict, host_name, in_dict):
    in_dict = in_dict.get("server_status", {})
    for c_found in in_dict.get("check_list", []):
        if c_found not in st_dict.keys():
            st_dict[c_found] = cluster_task(req, c_found, in_dict[c_found])
        st_dict[c_found].add_host(host_name, in_dict[c_found])
        #print host_name, in_dict[c_found]

class active_server(object):
    def __init__(self, req, host_name, c_list, idx):
        self.__host_name = host_name
        self.__idx = idx
        self.__command_list = c_list
        if self.__command_list:
            self.__c_sel_list = html_tools.selection_list(req, "cselc", {}, sort_new_keys=0, auto_reset=1)
            self.__c_sel_options  = html_tools.text_field(req, "cselo", size=128, display_len=32, auto_reset=1)
            self.__c_sel_list[0] = " -- nothing --"
            self.__c_lut = {}
            act_idx = 0
            for com_list in self.__command_list:
                act_idx += 1
                self.__c_lut[act_idx] = com_list
                self.__c_sel_list[act_idx] = "%2d: %s" % (act_idx, com_list)
            self.__act_com = self.__c_lut.get(self.__c_sel_list.check_selection(self.get_suffix(), 0), "")
            self.__act_options = self.__c_sel_options.check_selection(self.get_suffix(), "")
        else:
            self.__act_com, self.__act_options = ("", "")
        # virtual server
        self.__virtuals = []
        self.set_sc_result()
        self.set_uuid()
        self.set_version()
    def get_device_name(self):
        return "%s%s" % (self.__host_name,
                         self.__virtuals and " (vs: %s)" % (" ".join(self.__virtuals)) or "")
    def add_virtual_server(self, vs_name):
        self.__virtuals.append(vs_name)
        self.__virtuals.sort()
    def set_uuid(self, uuid="not set"):
        self.__uuid = uuid
    def get_uuid(self):
        return self.__uuid
    def set_version(self, version="not set"):
        self.__version = version
    def get_version(self):
        return self.__version
    def set_sc_result(self, state="-", ret_v="-"):
        self.__res_state = state
        self.__res_return = ret_v
    def get_sc_result(self):
        return self.__res_state, self.__res_return
    def get_host_name(self):
        return self.__host_name
    def get_num_commands(self):
        return len(self.__command_list)
    def get_sel_list(self):
        return self.__c_sel_list
    def get_sel_options(self):
        return self.__c_sel_options
    def get_suffix(self):
        return "c%d" % (self.__idx)
    def get_act_command(self):
        return self.__act_com
    
def parse_server_commands(req, sc_dict, host_name, in_dict, lut):
    # new server is a virtual one
    is_virtual = False
    in_list = in_dict.get("public_commands", [])
    act_uuid = in_dict.get("uuid", None)
    if act_uuid:
        # check for other servers with the same uuid (e.g. virtual servers)
        used_uuid_dict = dict([(v.get_uuid(), k) for k, v in sc_dict.iteritems() if v.get_uuid()])
        if used_uuid_dict.has_key(act_uuid):
            sc_dict[used_uuid_dict[act_uuid]].add_virtual_server(host_name)
            is_virtual = True
    if not is_virtual:
        sc_dict[host_name] = active_server(req, host_name, sorted(in_list), lut[host_name])
        if act_uuid:
            sc_dict[host_name].set_uuid(act_uuid)
        if in_dict.has_key("version"):
            sc_dict[host_name].set_version(in_dict["version"])
    return is_virtual, host_name
    
def process_page(req):
    if req.conf["genstuff"].has_key("AUTO_RELOAD"):
        del req.conf["genstuff"]["AUTO_RELOAD"]
    functions.write_header(req)
    functions.write_body(req)
    # additional info
    add_info = html_tools.selection_list(req, "add_info", {"m" : "Show memory Consumption",
                                                           "t" : "Show run time",
                                                           "p" : "Show PID info",
                                                           "s" : "Show SQL info"}, multiple=1, size=2)
    infos_set = add_info.check_selection("", [])
    # server connection log
    scon_logs = html_tools.message_log()
    s_names = req.conf["server"].get("server", {}).keys()
    host_lut = dict([(k, s_names.index(k) + 1) for k in sorted(s_names)])
    all_hosts, virtual_hosts = ([], [])
    c_list = []
    for s_name, s_ip in req.conf["server"].get("server", {}).iteritems():
        all_hosts.append(s_name)
        c_list.append(tools.s_command(req, "server", 8004, "check_server", [], 10, s_name))
    all_hosts.sort()
    tools.iterate_s_commands(c_list, scon_logs)
    st_dict, sc_dict = ({}, {})
    ok_hosts = []
    for sc in c_list:
        if sc.server_reply:
            if sc.get_state() != "e":
                #print sc.server_reply["result:server_info"]
                is_virtual, act_host_name = parse_server_commands(req, sc_dict, sc.get_hostname(), sc.server_reply["result:server_info"], host_lut)
                if is_virtual:
                    virtual_hosts.append(act_host_name)
                else:
                    ok_hosts.append(sc.get_hostname())
                    parse_cluster_tasks(req, st_dict, sc.get_hostname(), sc.server_reply["result:server_info"])
            else:
                pass
    virtual_hosts.sort()
    ok_hosts.sort()
    real_hosts = [x for x in all_hosts if x not in virtual_hosts]
    # generate lookup tables host->idx and idx->host, task->idx and idx->task
    all_cluster_tasks = st_dict.keys()
    ct_lut = dict([(x, all_cluster_tasks.index(x) + 1) for x in sorted(all_cluster_tasks)])
    [x.set_html_suffixes(ct_lut, host_lut) for x in st_dict.values()]
    # server commands
    c_list = []
    for s_name, s_stuff in sc_dict.iteritems():
        act_com = s_stuff.get_act_command()
        if act_com:
            c_list.append(tools.s_command(req, "server", 8004, act_com, [], 10, s_name))
    tools.iterate_s_commands(c_list, scon_logs)
    for sc in c_list:
        if sc.server_reply:
            sc_dict[sc.get_hostname()].set_sc_result(sc.get_state(), sc.get_return())
    c_list = []
    for ct_stuff in st_dict.values():
        for act_st in [ct_stuff.get_host_server_task(x) for x in real_hosts if ct_stuff.has_host(x)]:
            act_mode = act_st.get_service_mode()
            if act_mode:
                c_list.append(tools.s_command(req, "server", 8004, server_command.server_command(command="modify_service", option_dict={"service" : ct_stuff.get_task_name(),
                                                                                                                                        "mode"    : act_mode}), [], 10, act_st.get_host_name()))
    tools.iterate_s_commands(c_list, scon_logs)
    submit_button = html_tools.submit_button(req, "submit")
    select_button = html_tools.submit_button(req, "select")
    low_submit = html_tools.checkbox(req, "sub")
    low_submit[""] = 1
    sel_table = html_tools.html_table(cls = "blindsmall")
    sel_table[0][0] = html_tools.content(["Additional info: ", add_info, ", ", select_button], "", cls="center")
    req.write("<form action=\"%s.py?%s\" method=post>%s</form>\n" % (req.module_name,
                                                                     functions.get_sid(req),
                                                                     sel_table("")))
    tt_dict = {}
    for key, value in st_dict.iteritems():
        tt_dict.setdefault(value.get_task_type(), []).append(key)
    req.write("<form action=\"%s.py?%s\" method=post>\n" % (req.module_name,
                                                            functions.get_sid(req)))
    if st_dict:
        req.write(html_tools.gen_hline("Found %s on %s%s:" % (logging_tools.get_plural("Cluster task", len(st_dict.keys())),
                                                              logging_tools.get_plural("host", len(all_hosts) - len(virtual_hosts)),
                                                              virtual_hosts and " (%s)" % (logging_tools.get_plural("virtual host", len(virtual_hosts))) or ""), 2))
        out_table = html_tools.html_table(cls="normalsmall")
        for act_type in sorted(tt_dict.keys()):
            out_table[0]["class"] = "line01"
            out_table[None][0: 1 + 2 * len(real_hosts)] = html_tools.content("Type %s, %s" % (act_type,
                                                                                              logging_tools.get_plural("cluster task", len(tt_dict[act_type]))),
                                                                             type="th", cls="center")
            out_table[0]["class"] = "line00"
            out_table[None][0] = html_tools.content("Name", cls="center")
            for real_host in real_hosts:
                if sc_dict.has_key(real_host):
                    out_table[None][0:2] = html_tools.content("device %s" % (sc_dict[real_host].get_device_name()), cls="center")
                else:
                    out_table[None][0:2] = html_tools.content(real_host, cls="errorcenter")
            line_idx = 0
            for ct_name in sorted(tt_dict[act_type]):
                act_ct = st_dict[ct_name]
                line_idx = 1 - line_idx
                out_table[0]["class"] = "line1%d" % (line_idx)
                out_table[None][0] = html_tools.content(ct_name, cls="left")
                for host in real_hosts:
                    if act_ct.has_host(host):
                        act_st = act_ct.get_host_server_task(host)
                        if act_st.is_configured():
                            is_running = act_st.is_running()
                            if is_running:
                                info_parts = [act_st.get_run_info("p" in infos_set)]
                                if "m" in infos_set:
                                    info_parts.append(act_st.get_memory_info())
                                if "t" in infos_set:
                                    info_parts.append(act_st.get_time_info())
                                if "s" in infos_set:
                                    info_parts.append(act_st.get_sql_info())
                                out_table[None][0] = html_tools.content(", ".join(info_parts), cls="center")
                            else:
                                out_table[None][0] = html_tools.content("not running", cls="errorcenter")
                            out_table[None][0] = html_tools.content(act_st.get_html_sel_list(), act_st.get_suffix(), cls="center")
                        else:
                            out_table[None][0:2] = html_tools.content(" n/c ", cls="warncenter")
                    else:
                        # no info
                        if host in ok_hosts:
                            out_table[None][0:2] = html_tools.content("&nbsp;", cls="center")
                        else:
                            out_table[None][0:2] = html_tools.content(" n/c ", cls="errormin")
        req.write(out_table(""))
    else:
        req.write(html_tools.gen_hline("Found no Cluster tasks on %s" % (logging_tools.get_plural("host", len(all_hosts))), 2))
    if ok_hosts:
        req.write(html_tools.gen_hline("Found %s:" % (logging_tools.get_plural("active and reachable server", len(ok_hosts))), 2))
        com_table = html_tools.html_table(cls="normalsmall")
        com_table[0]["class"] = "line01"
        for h_line in ["Server", "UUID", "Version", "#coms", "command", "options", "latest result"]:
            com_table[None][0] = html_tools.content(h_line, type="th", cls="center")
        line_idx = 0
        for host in ok_hosts:
            line_idx = 1 - line_idx
            com_table[0]["class"] = "line1%d" % (line_idx)
            act_server = sc_dict[host]
            com_table[None][0] = html_tools.content(host, cls="left")
            if act_server.get_num_commands():
                com_table[None][0] = html_tools.content(act_server.get_uuid(), cls="left")
                com_table[None][0] = html_tools.content(act_server.get_version(), cls="center")
                com_table[None][0] = html_tools.content("%d" % (act_server.get_num_commands()), cls="center")
                com_table[None][0] = html_tools.content(act_server.get_sel_list(), act_server.get_suffix(), cls="center")
                com_table[None][0] = html_tools.content(act_server.get_sel_options(), act_server.get_suffix(), cls="center")
                com_table[None][0] = html_tools.content(", ".join([str(x) for x in list(act_server.get_sc_result())]), act_server.get_suffix(), cls="center")
            else:
                com_table[None][0:6] = html_tools.content("no commands found", cls="center")
        req.write(com_table(""))
        req.write("%s<div class=\"center\">%s</div>\n" % (add_info.create_hidden_var(),
                                                          submit_button("")))
    else:
        req.write(html_tools.gen_hline("Found no active and reachable server", 2))
    req.write("</form>\n")
    req.write(scon_logs.generate_stack("Server connection log"))
