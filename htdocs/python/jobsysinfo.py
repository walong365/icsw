#!/usr/bin/python -Ot
# -*- coding: utf-8 -*-
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008,2009 Andreas Lang-Nevyjel, init.at
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
import re
import sge_tools
import os
import filter_class

USERNAME_REGEXP = False

def module_info():
    return {"rms" : {"description" : "Resource managment system",
                     "priority"    : 40},
            "jsyi" : {"description"           : "Jobsystem information (SGE)",
                      "enabled"               : True,
                      "default"               : True,
                      "left_string"           : "Jobsystem info",
                      "right_string"          : "Information about running and waiting jobs",
                      "priority"              : 40,
                      "capability_group_name" : "rms"},
            "sacl" : {"default"                : False,
                      "enabled"                : True,
                      "description"            : "Show all cells",
                      "mother_capability_name" : "jsyi"},
            "jsko" : {"default"                : False,
                      "enabled"                : True,
                      "description"            : "Kill jobs from other users",
                      "mother_capability_name" : "jsyi"},
            "jsoi" : {"default"                : False,
                      "enabled"                : True,
                      "description"            : "Show stdout / stderr and filewatch-info for all users",
                      "mother_capability_name" : "jsyi"}}

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
            #conf_info = self.conf.get_config_info()
            #for conf in conf_info:
            #    print conf
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        print what, log_level
    def set_filter(self, filter):
        self.__filter = filter
    def check_settings(self):
        # sort list
        self.sort_list = html_tools.selection_list(self.__req, "sort%s" % (self.name), {}, sort_new_keys=False)
        for sort_type in ["user names", "job ids"]:
            self.sort_list["%s0" % (sort_type[0:2])] = "%s (ascending)" % (sort_type)
            self.sort_list["%s1" % (sort_type[0:2])] = "%s (descending)" % (sort_type)
        saved_sort = self.__req.user_info.get_user_var_value("_jsi_sort", "us0")
        self.act_sort_list = self.sort_list.check_selection("", saved_sort)
        # only my jobs / user_name reg
        self.only_my_jobs = html_tools.checkbox(self.__req, "omj%s" % (self.name))
        self.username_regexp = html_tools.text_field(self.__req, "omjr%s" % (self.name), size=128, display_len=16)
        saved_my_jobs = self.__req.user_info.get_user_var_value("_jsi_my_jobs", False)
        saved_username_regexp = self.__req.user_info.get_user_var_value("_jsi_username_regexp", ".*")
        if self.__active_submit:
            self.act_my_jobs = self.only_my_jobs.check_selection("")
        else:
            self.act_my_jobs = self.only_my_jobs.check_selection("", saved_my_jobs)
        if self.__active_submit and USERNAME_REGEXP:
            self.act_username_regexp = self.username_regexp.check_selection("")
        else:
            if USERNAME_REGEXP:
                self.act_username_regexp = self.username_regexp.check_selection("", saved_username_regexp)
            else:
                self.act_username_regexp = ".*"
        try:
            self.username_re = re.compile(self.act_username_regexp)
        except:
            self.act_username_regexp = self.username_regexp.check_selection("", ".*")
            self.username_re = re.compile(self.act_username_regexp)
        # job command
        self.job_command = html_tools.selection_list(self.__req, "jcom", {0 : "---",
                                                                          1 : "delete",
                                                                          2 : "force-delete"}, sort_new_keys = False, auto_reset=True)
        self.filewatch_option_list = html_tools.selection_list(self.__req, "fwo%s" % (self.name), {0 : "only info",
                                                                                                   1 : "display",
                                                                                                   2 : "display reverse"}, sort_new_keys=False)
        saved_fwo = self.__req.user_info.get_user_var_value("_jsi_fwo", 0)
        self.act_filewatch_option = self.filewatch_option_list.check_selection("", saved_fwo)
        if self.__active_submit:
            self.__req.user_info.modify_user_var("_jsi_sort", self.act_sort_list)
            self.__req.user_info.modify_user_var("_jsi_my_jobs", self.act_my_jobs)
            self.__req.user_info.modify_user_var("_jsi_fwo", self.act_filewatch_option)
            self.__req.user_info.modify_user_var("_jsi_username_regexp", self.act_username_regexp)
    def server_valid(self):
        needed_keys = ["SGE_CELL", "SGE_VERSION", "SGE_RELEASE", "SGE_ARCH"]
        missing_keys = sorted([key for key in needed_keys if not self.conf.has_key(key)])
        if missing_keys:
            self.__action_log.add_error("Some keys missing: %s" % (", ".join(missing_keys)), "SGE")
            is_valid = False
        else:
            is_valid = True
        return is_valid
    def __getitem__(self, key):
        return self.conf[key]
    def get_rms_dicts(self, act_rms_tree):
        success = False
        ds_command = tools.s_command(self.__req, "sge_server", 8009, "get_config", [], 10, self.name, add_dict={"needed_dicts"       : ["hostgroup", "queueconf", "qhost", "complexes", "qstat"],
                                                                                                                "fetch_output_info"  : True,
                                                                                                                "get_filewatch_info" : True,
                                                                                                                "get_cwd_info"       : True,
                                                                                                                "update_list"        : ["qhost", "qstat"],
                                                                                                                "user_name"          : self.__req.session_data.user,
                                                                                                                "ignore_user_name"   : self.__req.user_info.capability_ok("jsoi")})
        tools.iterate_s_commands([ds_command], self.__action_log)
        if ds_command.server_reply:
            if ds_command.get_state() == "o":
                try:
                    self.__sge_info = sge_tools.sge_info(is_active=False,
                                                         log_command=self.log,
                                                         init_dicts=ds_command.server_reply.get_option_dict())
                except:
                    self.__action_log.add_error("Error building sge_info: %s" % (process_tools.get_except_info()), "internal")
                else:
                    success = True
            else:
                self.__action_log.add_error("Error connecting to sge-server", "SGE")
        if success:
            f_name_dict = {}
            for job_name, job_struct in self.__sge_info["qstat"].iteritems():
                for h_name, f_name in job_struct.get("output_info", {}).iteritems():
                    f_name_dict[f_name] = (job_name, h_name)
            if f_name_dict:
                ds_command = tools.s_command(self.__req, "server", 8004, "get_file_info", [], 10, self.name, add_dict={"file_names" : f_name_dict.keys()})
                tools.iterate_s_commands([ds_command], self.__action_log)
                if ds_command.server_reply:
                    if ds_command.get_state() == "o":
                        file_info_dict = ds_command.server_reply.get_option_dict()
                        for f_name, f_stat in file_info_dict.iteritems():
                            job_uid, h_name = f_name_dict[f_name]
                            self.__sge_info["qstat"][job_uid]["output_info"][h_name] = f_stat
                    else:
                        self.__action_log.add_error("Error connecting to cluster-server", "SGE")
        return success
    def _get_display_id_list(self, in_dict):
        job_keys = in_dict.keys()
        if self.act_my_jobs:
            job_keys = [job_id for job_id in job_keys if in_dict[job_id]["JB_owner"] == self.__req.user_info["login"]]
        # check for username_re
        job_keys = [job_id for job_id in job_keys if self.username_re.match(in_dict[job_id]["JB_owner"])]
        if self.__filter:
            job_keys = [job_id for job_id in job_keys if self.__filter.job_is_ok(in_dict[job_id])]
        new_id_list = []
        for job_id, task_id in sorted([job_id.count(".") and tuple([x.isdigit() and int(x) or x for x in job_id.split(".")]) or (int(job_id), -1) for job_id in job_keys]):
            if type(task_id) == type(""):
                new_id_list.append("%d.%s" % (job_id, task_id))
            elif task_id > 0:
                new_id_list.append("%d.%d" % (job_id, task_id))
            else:
                new_id_list.append("%d" % (job_id))
        id_list = new_id_list
        id_list.sort()
        if self.act_sort_list.startswith("jo"):
            if self.act_sort_list == "jo0":
                pass
            elif self.act_sort_list == "jo1":
                id_list.reverse()
        elif self.act_sort_list.startswith("us"):
            user_dict = {}
            for job_id in id_list:
                job = in_dict[job_id]
                user_dict.setdefault(job["JB_owner"], []).append(job_id)
            users = user_dict.keys()
            users.sort()
            if self.act_sort_list == "us1":
                users.reverse()
            id_list = sum([user_dict[user] for user in users], [])
        return id_list
    def check_for_changes(self):
        del_list, force_del_list = ([], [])
        act_dict = self.__sge_info["qstat"]
        check_list = self._get_display_id_list(act_dict)
        for check_id in check_list:
            act_job = act_dict[check_id]
            if act_job["JB_owner"] == self.__req.user_info["login"] or self.__req.user_info.capability_ok("jsko"):
                act_com = self.job_command.check_selection(check_id, 0)
                if act_com == 1:
                    del_list.append(check_id)
                elif act_com == 2:
                    force_del_list.append(check_id)
        com_list = []
        if del_list:
            self.__action_log.add_warn("deleting %s: %s" % (logging_tools.get_plural("job", len(del_list)),
                                                            ", ".join(del_list)), "SGE")
            com_list.append(tools.s_command(self.__req, "sge_server", 8009, "delete_jobs", [], 10, self.name, add_dict={"job_ids" : del_list}))
        if force_del_list:
            self.__action_log.add_warn("force-deleting %s: %s" % (logging_tools.get_plural("job", len(force_del_list)),
                                                                  ", ".join(force_del_list)), "SGE")
            com_list.append(tools.s_command(self.__req, "sge_server", 8009, "force_delete_jobs", [], 10, self.name, add_dict={"job_ids" : force_del_list}))
        if com_list:
            tools.iterate_s_commands(com_list, self.__action_log)
    def show_running_jobs(self):
        proc_dict = process_tools.get_proc_list()
        act_dict = dict([(key, value) for key, value in self.__sge_info["qstat"].iteritems() if value.running])
        if act_dict:
            display_list = self._get_display_id_list(act_dict)
            if display_list:
                self.__req.write(html_tools.gen_hline("Showing %s" % (logging_tools.get_plural("running job", len(display_list))),
                                                      2))
                jr_table = html_tools.html_table(cls="normal")
                jr_table[0]["class"] = "line00"
                for what in ["User", "JobID", "State", "JobName", "Command", "PE info", "Queue", "Nodes", "Mean load", "start time", "run time", "Runlimit", "stdout", "stderr"]:
                    jr_table[None][0] = html_tools.content(what, type="th")
                #pprint.pprint([x for x in dir(act_dict[display_list[0]]) if x.startswith("get")])
                line1_idx = 0
                for display_id in display_list:
                    act_job = act_dict[display_id]
                    full_job_id = act_job.get_id()
                    # special dicts
                    std_oe_dict = self.__sge_info["qstat"][full_job_id].get("output_info", {})
                    fw_dict = self.__sge_info["qstat"][full_job_id].get("filewatch_info", {})
                    cwd = self.__sge_info["qstat"][full_job_id].get("cwd_info", {}).get("cwd", "/NOT_FOUND")
                    job_height = 1
                    if fw_dict:
                        if self.act_filewatch_option:
                            job_height += len(fw_dict.keys())
                        else:
                            job_height += 1
                    line1_idx = 1 - line1_idx
                    jr_table[0]["class"] = "line1%d" % (line1_idx)
                    jr_table[None:job_height][0] = html_tools.content(act_job["JB_owner"], cls="left")
                    # FIXME, XXX, Dirty hack for Liebherr (Kusnevskis, 1.7.2009, 14:15:25)
                    show_job_id = full_job_id
                    try:
                        rsm_pid = file("%s/ProcessId" % (cwd), "r").read().strip()
                    except:
                        print process_tools.get_except_info()
                    else:
                        if full_job_id != rsm_pid:
                            ppid_list = process_tools.build_ppid_list(proc_dict, int(rsm_pid))
                            try:#ue:#cur_pid in proc_dict:
                                mono_list = [cur_pid for cur_pid in ppid_list if proc_dict[cur_pid]["name"] == "mono"]
                            except:
                                mono_list = []
                            if mono_list:
                                show_job_id = "%s (%s)" % (full_job_id,
                                                           ",".join(["%d" % (cur_pid) for cur_pid in mono_list[:-1]]))
                            else:
                                show_job_id = "%s (%s)" % (full_job_id,
                                                           ",".join(["%d" % (cur_pid) for cur_pid in ppid_list]))
                    jr_table[None:job_height][0] = html_tools.content(show_job_id, cls="center")
                    jr_table[None][0] = html_tools.content(act_job.get_state(), cls="center")
                    jr_table[None][0] = html_tools.content(act_job["JB_name"], cls="center")
                    if act_job["JB_owner"] == self.__req.user_info["login"] or self.__req.user_info.capability_ok("jsko"):
                        jr_table[None][0] = html_tools.content(self.job_command, display_id, cls="center")
                    else:
                        jr_table[None][0] = html_tools.content("n / a", display_id, cls="center")
                    jr_table[None][0] = html_tools.content(act_job.get_pe_info("granted"), cls="center")
                    jr_table[None][0] = html_tools.content(act_job.get_running_queue(), cls="center")
                    jr_table[None][0] = html_tools.content(act_job.get_running_nodes(), cls="center")
                    jr_table[None][0] = html_tools.content(act_job.get_load_info(self.__sge_info["qhost"]), cls="center")
                    jr_table[None][0] = html_tools.content(act_job.get_start_time(), cls="center")
                    jr_table[None][0] = html_tools.content(act_job.get_run_time(), cls="center")
                    #if act_job.get_h_rt():
                    #    run_limit = logging_tools.get_time_str(act_job.get_h_rt())
                    #else:
                    #    run_limit = "---"
                    jr_table[None][0] = html_tools.content(act_job.get_left_time(), cls="center")
                    for path_name in ["out", "err"]:
                        path_var = std_oe_dict.get("std%s_path" % (path_name), "")
                        if type(path_var) == type(""):
                            if path_var:
                                jr_table[None][0] = html_tools.content("found", cls="center")
                            else:
                                jr_table[None][0] = html_tools.content("---", cls="center")
                        else:
                            if path_var["found"]:
                                file_size = path_var["stat"].st_size
                                if file_size:
                                    target = "fetchfilecontent.py?%s&server=%s&file=%s" % (functions.get_sid(self.__req), self.name, path_var["name"])
                                    jr_table[None][0] = html_tools.content("<a href=\"%s\" type=\"text/plain\">%s</a>" % (target, logging_tools.get_size_str(path_var["stat"].st_size, long_version=True)), cls="center")
                                else:
                                    jr_table[None][0] = html_tools.content("empty", cls="center")
                            else:
                                jr_table[None][0] = html_tools.content("N / A", cls="center")
                    if fw_dict:
                        all_fw_keys = fw_dict.keys()
                        if self.act_filewatch_option:
                            for fw_key in sorted(all_fw_keys):
                                fw_struct = fw_dict[fw_key]
                                jr_table[0]["class"] = "line1%d" % (line1_idx)
                                out_f = ["<div class=\"center\">"]
                                fw_lines = fw_struct["content"].split("\n")
                                if self.act_filewatch_option == 2:
                                    fw_lines.reverse()
                                num_lines = len(fw_lines)
                                out_f.append("key %s (file %s), %s in %s, last update %s" % (fw_key,
                                                                                             fw_struct["name"],
                                                                                             logging_tools.get_size_str(len(fw_struct["content"]), long_version=True),
                                                                                             logging_tools.get_plural("line", num_lines),
                                                                                             time.ctime(fw_struct["update"])))
                                ta_height = min(max(3, num_lines - 1), 10)
                                out_f.append("</div><div class=\"center\">")
                                out_f.append("<textarea style=\"width=100%%; font-family:monospace ; font-style:normal ; font-size:9pt ; \" cols=\"100\" rows=\"%d\" readonly >%s</textarea>\n" % (ta_height,
                                                                                                                                                                                                   "\n".join(fw_lines)))
                                out_f.append("</div>")
                                jr_table[None][3:14] = html_tools.content("".join(out_f), cls="left")
                        else:
                            fw_info_str = "%s: %s" % (logging_tools.get_plural("filewatch key", len(all_fw_keys)),
                                                      ", ".join(["%s (%s in %s, last update %s)" % (fw_key,
                                                                                                    logging_tools.get_size_str(len(fw_dict[fw_key]["content"]), long_version=True),
                                                                                                    logging_tools.get_plural("line", len(fw_dict[fw_key]["content"].split("\n"))),
                                                                                                    time.ctime(fw_dict[fw_key]["update"])) for fw_key in sorted(all_fw_keys)]))
                            jr_table[0]["class"] = "line1%d" % (line1_idx)
                            jr_table[None][3:14] = html_tools.content(fw_info_str, cls="left")
                self.__req.write(jr_table(""))
                return []
            else:
                return ["No running jobs for active filter"]
        else:
            return ["No running jobs"]
    def show_waiting_jobs(self):
        act_dict = dict([(key, value) for key, value in self.__sge_info["qstat"].iteritems() if not value.running])
        if act_dict:
            display_list = self._get_display_id_list(act_dict)
            if display_list:
                self.__req.write(html_tools.gen_hline("Showing %s" % (logging_tools.get_plural("waiting job", len(act_dict.keys()))),
                                                      2))
                jw_table = html_tools.html_table(cls="normal")
                jw_table[0]["class"] = "line00"
                for what in ["User", "JobID", "State", "JobName", "Command", "PE info", "queue", "submit time", "wait time", "Runlimit"]:
                    jw_table[None][0] = html_tools.content(what, type="th")
                #pprint.pprint([x for x in dir(act_dict[display_list[0]]) if x.startswith("get")])
                line1_idx = 0
                for display_id in display_list:
                    line1_idx = 1 - line1_idx
                    jw_table[0]["class"] = "line1%d" % (line1_idx)
                    act_job = act_dict[display_id]
                    jw_table[None][0] = html_tools.content(act_job["JB_owner"], cls="left")
                    jw_table[None][0] = html_tools.content(act_job.get_id(), cls="center")
                    jw_table[None][0] = html_tools.content(act_job.get_state(), cls="center")
                    jw_table[None][0] = html_tools.content(act_job["JB_name"], cls="center")
                    if act_job["JB_owner"] == self.__req.user_info["login"] or self.__req.user_info.capability_ok("jsko"):
                        jw_table[None][0] = html_tools.content(self.job_command, display_id, cls="center")
                    else:
                        jw_table[None][0] = html_tools.content("n / a", display_id, cls="center")
                    jw_table[None][0] = html_tools.content(act_job.get_pe_info("requested"), cls="center")
                    jw_table[None][0] = html_tools.content(act_job.get_requested_queue(), cls="center")
                    jw_table[None][0] = html_tools.content(act_job.get_queue_time(), cls="center")
                    jw_table[None][0] = html_tools.content(act_job.get_wait_time(), cls="center")
#                     if act_job.get_h_rt():
#                         run_limit = logging_tools.get_time_str(act_job.get_h_rt())
#                     else:
#                         run_limit = "---"
                    jw_table[None][0] = html_tools.content(act_job.get_h_rt_time(), cls="center")
                self.__req.write(jw_table(""))
                return []
            else:
                return ["No waiting jobs for active filter"]
        else:
            return ["No waiting jobs"]
        
class rms_tree(object):
    def __init__(self, req, action_log, active_submit):
        self.__req = req
        self.__dc = req.dc
        self.cell_list = html_tools.selection_list(self.__req, "cellsel", {}, sort_new_key=False)
        self._read_filters()
        self.__sge_server, self.active_sge_servers = ({}, [])
        for s_name, s_ip in self.__req.conf["server"].get("sge_server", {}).iteritems():
            new_sge_server = sge_server(self.__req, action_log, s_name, s_ip, active_submit)
            if new_sge_server.server_valid():
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
            self[self.active_sge_server].check_settings()
            self[self.active_sge_server].set_filter(self.get_act_filter(active_submit))
    def single_server(self):
        return len(self.active_sge_servers) == 1
    def __getitem__(self, key):
        return self.__sge_server[key]
    def num_filters(self):
        return len(self.__filters)
    def _read_filters(self):
        self.__filters = []
        sub_dirs = [os.path.dirname(self.__req.environ["SCRIPT_FILENAME"]),
                    "%s/jobsysinfo.d" % (os.path.dirname(self.__req.environ["SCRIPT_FILENAME"]))]
        for sub_dir in sub_dirs:
            if sub_dir not in sys.path:
                sys.path.append(sub_dir)
        for file_n in [entry for entry in os.listdir(sub_dir) if entry.endswith("_filter.py")]:
            try:
                newmod = __import__(file_n[:-3], globals(), [], [])
            except:
                print file_n, process_tools.get_except_info()
                pass
            else:
                found_filters = [obj_name for obj_name in dir(newmod) if type(getattr(newmod, obj_name)) == type(filter_class.filter_class)]# and issubclass(getattr(newmod, obj_name), filter_class.filter_class)]
                for found_filter in found_filters:
                    self.__filters.append(getattr(newmod, found_filter)())
        for sub_dir in sub_dirs:
            if sub_dir in sys.path:
                sys.path.remove(sub_dir)
        if self.__filters:
            self.__filter_list = html_tools.selection_list(self.__req, "filter", {}, sort_new_keys=False)
            f_names = dict([(filter.name, filter) for filter in self.__filters])
            for f_name in sorted(f_names.keys()):
                self.__filter_list[self.__filters.index(f_names[f_name])] = f_name
            self.__filter_list.mode_is_normal()
    def get_filter_list(self):
        return self.__filter_list
    def get_act_filter(self, active_submit):
        if self.__filters:
            saved_my_filter = self.__req.user_info.get_user_var_value("_jsi_filter", 0)
            if active_submit:
                act_filter_idx = self.__filter_list.check_selection("", 0)
            else:
                act_filter_idx = self.__filter_list.check_selection("", saved_my_filter)
            if act_filter_idx == None:
                act_filter_idx = 0
            if active_submit:
                self.__req.user_info.modify_user_var("_jsi_filter", act_filter_idx)
            act_filter = self.__filters[act_filter_idx]
        else:
            act_filter = None
        return act_filter

def process_page(req):
    functions.write_header(req)
    functions.write_body(req)
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
        if act_sge_server.get_rms_dicts(act_rms_tree):
            out_line = ["Sort method: %s" % (act_sge_server.sort_list("")),
                        "only my jobs: %s" % (act_sge_server.only_my_jobs(""))]
            if USERNAME_REGEXP:
                out_line.append("username regexp: %s" % (act_sge_server.username_regexp("")))
            if act_rms_tree.num_filters() > 1:
                out_line.append("filter: %s" % (act_rms_tree.get_filter_list()("")))
            out_line.append("filewatch: %s, %s</div>" % (act_sge_server.filewatch_option_list(""),
                                                         submit_button("")))
                                              
            req.write("<div class=\"center\">%s</div>" % (", ".join(out_line)))
            act_sge_server.check_for_changes()
            bottom_line = []
            bottom_line.extend(act_sge_server.show_running_jobs())
            bottom_line.extend(act_sge_server.show_waiting_jobs())
            if bottom_line:
                req.write(html_tools.gen_hline(", ".join(bottom_line), 2))
        req.write(action_log.generate_stack("Action log", show_only_errors=True, show_only_warnings=True))
        req.write("%s<div class=\"center\">%s</div>\n" % (low_submit.create_hidden_var(),
                                                          submit_button()))
        req.write("</form>")
    else:
        req.write(html_tools.gen_hline("User has no access to any SGE-Cell", 2))
        req.write(action_log.generate_stack("Action log", show_only_errors=True, show_only_warnings=True))
