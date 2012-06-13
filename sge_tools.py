#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008,2012 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of rms-tools
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
""" tools for the SGE """

import commands
import sys
import re
import time
import os.path
import datetime
import pprint
import logging_tools
import server_command
import process_tools
import zmq
from lxml import etree

SQL_ACCESS = "cluster_full_access"

def compress_list(ql, queues = None):
    # node prefix, postfix, start_string, end_string
    # not exactly the same as the version in logging_tools
    def add_p(np, ap, s_str, e_str):
        if s_str == e_str:
            return "%s%s%s" % (np, s_str, ap)
        elif int(s_str) + 1 == int(e_str):
            return "%s%s%s/%s%s" % (np, s_str, ap, e_str, ap)
        else:
            return "%s%s%s-%s%s" % (np, s_str, ap, e_str, ap)
    if not queues or queues == "-":
        q_list = []
    else:
        q_list = [x.strip() for x in queues.split(",")]
    pf_re = re.compile("^(?P<pef>\D+)(?P<num>\d*)(?P<pof>.*)$")
    pf_q_re = re.compile("^(?P<pef>.+@\D+)(?P<num>\d*)(?P<pof>.*)$")
    ql.sort()
    nc_dict = {}
    for q_name in ql:
        if q_name.count("@"):
            pf_m = pf_q_re.match(q_name)
        else:
            pf_m = pf_re.match(q_name)
        pef = pf_m.group("pef")
        if len(q_list) == 1 and pef.startswith("%s@" % (q_list[0])):
            pef = pef[len(q_list[0])+1:]
        idx = pf_m.group("num")
        pof = pf_m.group("pof").split(".")[0]
        if idx:
            i_idx = int(idx)
        else:
            i_idx = 0
        nc_dict.setdefault(pef, {}).setdefault(pof, {})[i_idx] = idx
    nc_a = []
    for pef in nc_dict.keys():
        for pof, act_l in nc_dict[pef].iteritems():
            s_idx = None
            for e_idx in sorted(act_l.keys()):
                e_num = act_l[e_idx]
                if s_idx is None:
                    s_idx, s_num = (e_idx, e_num)
                    l_num, l_idx = (s_num, s_idx)
                else:
                    if e_idx == l_idx+1:
                        pass
                    else:
                        nc_a.append(add_p(pef, pof, s_num, l_num))
                        s_num, s_idx = (e_num, e_idx)
                    l_num, l_idx = (e_num, e_idx)
            if pef:
                nc_a.append(add_p(pef, pof, s_num, l_num))
    return ",".join(nc_a)

def str_to_sec(in_str):
    if in_str == "---":
        sec = in_str
    else:
        is_f = [int(x) for x in in_str.split()[0].split(":")]
        sec, mult = (0, 0)
        while len(is_f):
            sec = sec * mult + is_f.pop(0)
            if len(is_f) > 2:
                mult = 24
            else:
                mult = 60
    return sec

def sec_to_str(in_sec):
    if in_sec == "---":
        out_f = "---"
    else:
        if in_sec >= 0:
            diff_d = int(in_sec / (3600 * 24))
            dt = in_sec - 3600 * 24 * diff_d
            diff_h = int(dt / 3600)
            dt -= 3600 * diff_h
            diff_m = int(dt / 60)
            dt -= diff_m * 60
            #if diff_d:
            out_f = "%s%02d:%02d:%02d" % (diff_d and "%2d:" % (diff_d) or "", diff_h, diff_m, dt)
            #else:
            #    out_f = "%2d:%02d:%02d" % (diff_h, diff_m, dt)
        else:
            out_f = "????"
    return out_f


class sge_complex(object):
    def __init__(self, c_type, name, in_dict, opt_dict):
        # complex_type, can be
        # i ..... init
        # o ..... other (?)
        # s ..... system
        self.complex_type = c_type
        self.name = name
        self.__opt_dict = opt_dict
        # in_dict for system (o/s) resources is simply {name: True}
        if self.complex_type == "i":
            self.__internal_dict = {}
            for postfix, default in [("pe"     , "serial"),
                                     ("num_min", 1       ),
                                     ("num_max", 1       ),
                                     ("mt_time", "0:10:0"),
                                     ("m_time" , "0:10:0")]:
                self.__internal_dict[postfix] = in_dict.get("%s_%s" % (self.name, postfix), default)
        else:
            self.__internal_dict = dict([(k, v) for k, v in in_dict.iteritems()])
        self.__internal_dict["queues"] = {}
    def get_complex_type(self):
        return self.complex_type
    def __getitem__(self, key):
        return self.__internal_dict[key]
    def add_queue_host(self, q_name, h_name):
        if h_name:
            self.__internal_dict["queues"].setdefault(q_name, set())
            if type(h_name) != type(""):
                self.__internal_dict["queues"][q_name].update(h_name)
            else:
                self.__internal_dict["queues"][q_name].add(h_name)
    def get_queues(self, q_name=""):
        if q_name:
            return ", ".join([sub_list for sub_list in logging_tools.compress_list(self["queues"][q_name]).split(", ")])
        else:
            return ", ".join([", ".join(["%s@%s" % (q_name, sub_list) for sub_list in logging_tools.compress_list(self["queues"][q_name]).split(", ")]) for q_name in sorted(self["queues"].keys())])
    def get_waiting(self, j_dict, q_list):
        # return number of waiting jobs for this complex (wrt to the  queues in q_list)
        num = 0
        for job_id, job_stuff in j_dict.iteritems():
            if not job_stuff.running:
                if job_stuff.get("hard_req_queue", "") in q_list:
                    if len([True for hreq in job_stuff.get("hard_request", []) if hreq["name"] == self.name]):
                        num += 1
        return num
    def get_running(self, j_dict, q_list):
        # return number of running jobs for this complex (wrt to the  queues in q_list)
        num = 0
        for job_id, job_stuff in j_dict.iteritems():
            if job_stuff.running:
                if job_stuff.get_running_queue() in q_list:
                    if len([True for hreq in job_stuff.get("hard_request", []) if hreq["name"] == self.name]):
                        num += 1
        return num
    def get_hq_list(self, h_dict, q_list):
        if q_list == [""]:
            q_list = sorted(self["queues"].keys())
        ret_list = []
        for q_name in q_list:
            for h_name in self["queues"][q_name]:
                act_h = h_dict[h_name]
                ret_list.append((act_h.get_queue_state(q_name),
                                 act_h.get_slots_used(q_name),
                                 act_h.get_slots_total(q_name)))
        return ret_list
    def _OLD_add_queue(self, q_name):
        if q_name not in self.__internal_dict["queues"]:
            self.__internal_dict["queues"].append(q_name)
    def get_internal_dict(self):
        return self.__internal_dict
    def get(self, key, default):
        return self.__internal_dict.get(key, default)
    def get_name(self):
        return self.name
    def get_resources(self):
        if self.complex_type == "i":
            return [self.name]
        else:
            return [x for x in self.__internal_dict.keys()]
    def set_form_str(self, fl, opt_dict={}):
        if opt_dict.get("show_per_queue_stat", 0):
            headers = ["Complex", "Queue"]
            fl.set_format_string(1, "s", "")
            start_idx = 3
        else:
            headers = ["Complex"]
            start_idx = 2
        headers.extend(["pe-list", "#minslots", "#maxslots", "time", "time/node", "wait", "run", "#total", "#up", "#avail"])
        fl.set_format_string(start_idx    , "d", "")
        fl.set_format_string(start_idx + 1, "d", "")
        fl.set_format_string(start_idx + 2, "s", "")
        fl.set_format_string(start_idx + 3, "s", "")
        num_dec = 5
        if self.__opt_dict.get("check_serial_jobs", 0):
            headers.extend(["#s", "#sa"])
            num_dec += 2
        #num_dec += 1
        if opt_dict.get("detailed_error_stats", 0):
            headers.extend(["#alarm", "#Err", "#unk", "#Sub",  "#sus", "#dis"])
            num_dec += 6
        else:
            headers.extend(["#alarm", "#EuSsd"])
            num_dec += 2
        for i in range(num_dec):
            fl.set_format_string(start_idx + 4 + i, "d", "")
        if opt_dict.get("show_per_queue_stat", 0):
            headers.extend(["Nodes"])
        else:
            headers.extend(["Queues"])
        fl.set_header_string(0, headers)
    def get_repr_parts(self, queue_dict, job_r_dict, job_w_dict, opt_dict={}):
        # check_serial_jobs is no longer supported
        all_q = sorted(queue_dict.keys())
        ql_uc = [q for q in all_q if self.name in queue_dict[q].i_cs]
        sge_queues = []
        for sge_queue in [x.split("@")[0] for x in ql_uc if x.count("@")]:
            if sge_queue not in sge_queues:
                sge_queues.append(sge_queue)
        sge_queues.sort()
        if opt_dict.get("show_per_queue_stat", 0):
            search_queues = sge_queues + ["---"]
        else:
            search_queues = [""]
        ret_fields = []
        for search_queue in search_queues:
            if search_queue:
                act_ql_uc = [x for x in ql_uc if x.split("@")[0] == search_queue]
                act_hosts = [x.split("@")[1] for x in ql_uc if x.split("@")[0] == search_queue]
            else:
                act_ql_uc = ql_uc
                act_hosts = ql_uc
            #ql_s          = [q for q in act_ql_uc if "serial"  in queue_dict[q].i_cs]
            alarm_list    = [x for x in act_ql_uc if "a" in queue_dict[x].q_s]
            ql_up      = [x for x in act_ql_uc if "u" not in queue_dict[x].q_s]
            if opt_dict.get("detailed_error_stats", 0):
                err_list      = [x for x in act_ql_uc if "E" in queue_dict[x].q_s]
                unk_list      = [x for x in act_ql_uc if "u" in queue_dict[x].q_s]
                sub_list      = [x for x in act_ql_uc if "S" in queue_dict[x].q_s]
                susp_list     = [x for x in act_ql_uc if "s" in queue_dict[x].q_s]
                disabled_list = [x for x in act_ql_uc if "d" in queue_dict[x].q_s]
                ql_avail      = [x for x in ql_up   if x not in sub_list and x not in disabled_list and x not in susp_list and x not in err_list]
            else:
                err_list   = [x for x in act_ql_uc if [1 for y in ["E", "u", "S", "s", "d"] if y in queue_dict[x].q_s]]
                ql_avail   = [x for x in ql_up   if x not in err_list]
            #ql_s_up       = [x for x in ql_s  if "u" not in queue_dict[x].q_s]
            #ql_s_avail = [x for x in ql_s_up if x not in sub_list and x not in disabled_list and x not in susp_list]
            if search_queue:
                for ji, act_j in job_r_dict.iteritems():
                    for dq in [x for x in act_j.queue_dict.keys() if self.name in queue_dict[x].i_cs and x in ql_avail and act_j.queue == search_queue]:
                        ql_avail.remove(dq)
                if search_queue == "---":
                    num_r = len([True for j in job_r_dict.keys() if self.name in job_r_dict[j].get_complex().split(",") and job_r_dict[j].get_queue().split("@")[0] not in search_queues])
                    num_w = len([True for j in job_w_dict.keys() if self.name in job_w_dict[j].get_complex().split(",") and job_w_dict[j].get_queue().split("@")[0] not in search_queues])
                else:
                    #print search_queue, [job_r_dict[j].get_queue().split("@")[0] for j in job_r_dict.keys()]
                    num_r = len([True for j in job_r_dict.keys() if self.name in job_r_dict[j].get_complex().split(",") and job_r_dict[j].get_queue().split("@")[0] == search_queue])
                    num_w = len([True for j in job_w_dict.keys() if self.name in job_w_dict[j].get_complex().split(",") and job_w_dict[j].get_queue().split("@")[0] == search_queue])
            else:
                for ji, act_j in job_r_dict.iteritems():
                    for dq in [x for x in act_j.queue_dict.keys() if self.name in queue_dict[x].i_cs and x in ql_avail]:
                        ql_avail.remove(dq)
                #for dq in [x for x in act_j.queue_dict.keys() if self.name in queue_dict[x].i_cs and x in ql_s_avail]:
                #    ql_s_avail.remove(dq)
                num_r = len([True for j in job_r_dict.keys() if self.name in job_r_dict[j].get_complex().split(",")])
                num_w = len([True for j in job_w_dict.keys() if self.name in job_w_dict[j].get_complex().split(",")])
            if search_queue:
                ret_f = [self.name, search_queue]
            else:
                ret_f = [self.name]
            ret_f.extend([self.__internal_dict.get("pe", "---"),
                          self.__internal_dict.get("num_min", "-"),
                          self.__internal_dict.get("num_max", "-"),
                          sec_to_str(str_to_sec(self.__internal_dict.get("mt_time", "---"))),
                          sec_to_str(str_to_sec(self.__internal_dict.get("m_time", "---"))),
                          num_w,
                          num_r,
                          len(act_ql_uc),
                          len(ql_up),
                          len(ql_avail)])
            #if self.__opt_dict.get("check_serial_jobs", 0):
            #    ret_f.extend([len(ql_s), len(ql_s_avail)])
            if act_hosts or opt_dict.get("show_empty_complexes", 0):
                if opt_dict.get("detailed_error_stats", 0):
                    ret_f.extend([len(alarm_list), len(err_list), len(unk_list), len(sub_list), len(susp_list), len(disabled_list), compress_list(act_hosts)])
                else:
                    ret_f.extend([len(alarm_list), len(err_list), compress_list(act_hosts)])
                ret_fields.append(ret_f)
        return ret_fields
    def __repr__(self):
        return "complex_type %s, complex_name %s, keys: %s" % (self.complex_type,
                                                               self.name,
                                                               ",".join(self.__internal_dict.keys()))

class job(object):
    def __init__(self, uid, opt_dict = {}):
        self.complexes = []
        self.uid = uid
        self.id = uid.split(".")[0]
        if self.uid == self.id:
            self.t_id = ""
        else:
            self.t_id = uid.split(".")[1]
        self.host_dict = {}
        self.queue_dict = {}
        self.num = 1
        self.set_pe()
        self.set_queue()
        self.depends = []
        self.set_h_rt()
        self.__opt_dict = opt_dict
    def get_num(self):
        return self.num
    def set_tickets(self, tckts):
        self.tickets = tckts
    def set_priority(self, pri):
        self.priority = pri
    def set_depend(self, deps):
        self.depends += deps
    def modify_status(self, queue_dict):
        any_error = 0
        for q_n in self.queue_dict.keys():
            if "u" in queue_dict[q_n].get_status():
                any_error = 1
        if any_error:
            self.status += "E"
    def get_depends(self):
        return ",".join(self.depends)
    def get_tickets(self):
        return self.tickets
    def get_priority(self):
        return self.priority
    def add_host(self, host, n_type):
        self.host_dict[host] = n_type
        #self.num = len(self.host_dict)
    def add_queue(self, queue, n_type, slots=1):
        #print self.queue_dict, queue
        self.queue_dict.setdefault(queue, [])
        self.queue_dict[queue].extend([n_type] * slots)
        self.num = sum([len(x) for x in self.queue_dict.values()])
    def simplify_queue_name(self):
        if self.queue and self.queue.count("@"):
            q_name = self.queue.split("@")[0]
            if len([True for q_n in [x.split("@")[0] for x in self.queue_dict.keys() if x.count("@")] if q_n == q_name]) == len(self.queue_dict.keys()):
                self.queue = q_name
    def get_nodes(self):
        j_a = {}
        for q_name, qt in self.queue_dict.iteritems():
            for aq_st in ["MASTER", "SLAVE"]:
                num_aq_st = qt.count(aq_st)
                if num_aq_st:
                    j_a.setdefault(aq_st, [])
                    if num_aq_st > 1:
                        j_a[aq_st].append("%s(%d)" % (q_name, num_aq_st))
                    elif num_aq_st:
                        j_a[aq_st].append(q_name)
        n_l = []
        for jak in sorted(j_a.keys()):
            n_l.append(compress_list(j_a[jak], self.get_queue()))
        return ",".join(n_l)
    def set_user(self, user):
        self.user = user
    def get_id(self):
        return int(self.id)
    def get_uid(self):
        return self.uid
    def get_taw(self):
        return "%2s" % (self.t_id)
    def set_type(self, in_type):
        self.j_t = in_type
    def set_name(self, in_name):
        self.name = in_name
    def get_name(self):
        return self.name
    def set_status(self, stat):
        self.status = stat
    def get_status(self, output=False):
        if output and self.__opt_dict.get("show_stat", 0) > 1:
            stat_lod = {"q" : "queued",
                        "d" : "deleted",
                        "h" : "hold",
                        "r" : "running",
                        "R" : "Restarted",
                        "s" : "suspended",
                        "S" : "Subordinated",
                        "t" : "transfering",
                        "T" : "Threshold",
                        "w" : "waiting",
                        "o" : "orphaned"}
            return ",".join(["(%s)%s" % (c, stat_lod.get(c, "?unknown")[1:]) for c in self.status])
        else:
            return self.status
    def set_complex(self, compl):
        if not compl in self.complexes:
            self.complexes.append(compl)
            self.complexes.sort()
    def get_complex(self):
        #print complexes[self.complex]["time"]
        return ",".join(self.complexes)
    def set_h_rt(self, h_rt = None):
        if h_rt:
            self.h_rt = str_to_sec(h_rt)
        else:
            self.h_rt = 0
    def get_h_rt(self):
        return self.h_rt
    def is_waiting(self):
        return "q" in self.get_status()
    def get_perc(self):
        if self.is_waiting():
            return [""]
        else:
            if self.get_h_rt():
                if self.__opt_dict.get("show_perc", 0):
                    return ["%5.5s %%" % ("%5.1f" % (float(100.*self.get_run_secs()/self.get_h_rt()))),
                            "%5.5s %%" % ("%5.1f" % (float(100.*(self.get_h_rt()-self.get_run_secs())/self.get_h_rt())))]
                else:
                    return [sec_to_str((int(self.get_h_rt() - self.get_run_secs())))]
            else:
                if self.__opt_dict.get("show_perc", 0):
                    return [sec_to_str(-1), sec_to_str(-1)]
                else:
                    return [sec_to_str(-1)]
    def set_sq_time(self, in_date=None, in_time=None):
        if in_date and in_time:
            self.sq_date = in_date
            self.sq_time = in_time
            self.sq_dt = time.strptime("%s %s" % (self.sq_date, self.sq_time), "%m/%d/%Y %H:%M:%S")
        else:
            self.sq_dt = time.localtime()
        self.sq_ds = time.mktime(self.sq_dt)
    def get_sq_time(self):
        dt = self.sq_dt
        act_time = time.localtime()
        diff_days = (datetime.date(act_time[0], act_time[1], act_time[2]) - datetime.date(dt[0], dt[1], dt[2])).days
        if diff_days < 2:
            if diff_days == 1:
                return "yesterday %2d:%02d:%02d" % (dt[3], dt[4], dt[5])
            elif diff_days == 0:
                return "today %2d:%02d:%02d" % (dt[3], dt[4], dt[5])
            else:
                return "%d days ago %2d:%02d:%02d" % (diff_days, dt[3], dt[4], dt[5])
        else:
            return "%2d. %3s %04d %2d:%02d:%02d" % (dt[2], time.strftime("%b", dt), dt[0], dt[3], dt[4], dt[5])
    def get_run_secs(self):
        lc_t = time.localtime()
        off_t = lc_t[8] * 3600 * 0
        diff_t = time.time() + off_t - self.sq_ds
        return diff_t
    def get_run_time(self):
        return sec_to_str(self.get_run_secs())
    def set_pri(self, p_in):
        self.pri = p_in
    def get_pri(self):
        return self.pri
    def get_user(self):
        return self.user
    def set_queue(self, queue = None):
        self.queue = queue
    def get_queue(self):
        return self.queue or "-"
    def set_pe(self, pe_req = None):
        if pe_req:
            self.pe_req, self.pe_num = pe_req.split()
        else:
            self.pe_req, self.pe_num = (None, 1)
    def get_pe_num(self):
        if self.is_waiting():
            return self.pe_num
        else:
            return self.num
    def get_pe_info(self):
        if self.is_waiting():
            if self.pe_req:
                return "%s(%s)" % (self.pe_req, self.pe_num)
            else:
                return self.pe_num
        else:
            if self.pe_req:
                return "%s(%s)" % (self.pe_req, self.pe_num)
            else:
                return self.pe_num
    def get_type(self, act_queue):
        if self.num == 1:
            j_t = "SINGLE"
        else:
            if act_queue:
                aq_types = self.queue_dict[act_queue]
                j_a = []
                for aq_st in ["MASTER", "SLAVE"]:
                    if aq_st in aq_types:
                        num_aq_st = aq_types.count(aq_st)
                        if num_aq_st > 1:
                            j_a.append("%s(%d)" % (aq_st, num_aq_st))
                        elif num_aq_st:
                            j_a.append(aq_st)
                j_t = "+".join(j_a)
            else:
                j_a = [x for x in self.queue_dict.keys() if "MASTER" in self.queue_dict[x]]
                j_a.extend([x for x in self.queue_dict.keys() if "SLAVE" in self.queue_dict[x]])
                j_t = " + ".join(j_a)
        return "%6s" % j_t
    def get_mean_load(self, queue_dict):
        n_q = len(self.queue_dict)
        if n_q:
            mean_load, max_load = (0.0, 0.0)
            for n_name in self.queue_dict.keys():
                max_load = max(max_load, queue_dict[n_name].load)
                mean_load += queue_dict[n_name].load
            mean_load /= n_q
            if n_q == 1:
                mm_rat = 100.
            else:
                if max_load == 0.:
                    mm_rat = 0
                else:
                    mm_rat = int((n_q / (max_load * float(n_q - 1.)) * mean_load + 1./float( 1. - n_q)) * 100.)
            return "%.2f (%3d %%)" % (mean_load, mm_rat)
        else:
            return ""
    def set_form_str(self, fl, job_type="r"):
        headers = ["Id", "ta", "Name", "#slots", "user", "stat", "complex", "queue"]
        fl.set_format_string(0, "d")
        # name
        fl.set_format_string(2, "s", "")
        # slots
        fl.set_format_string(3, "s", "")
        # user
        fl.set_format_string(4, "s", "")
        # stat
        fl.set_format_string(5, "s", "")
        # complex
        fl.set_format_string(6, "s", "")
        # queue
        fl.set_format_string(7, "s", "")
        if job_type == "r":
            if self.__opt_dict.get("show_time_info", 1):
                headers.extend(["start time", "run time"])
                fl.set_format_string(8, "s", "")
                fl.set_format_string(9, "s", "")
            if self.__opt_dict.get("show_perc"):
                headers.append("used")
            headers.extend(["left", "load (eff.)"])
            if self.__opt_dict.get("node_flag", 0):
                headers.append("Queues")
        else:
            if self.__opt_dict.get("show_time_info", 1):
                headers.extend(["queue time", "wait time"])
                fl.set_format_string(8, "s", "")
                fl.set_format_string(9, "s", "")
                start_row = 10
            else:
                start_row = 8
            headers.extend(["h_rt", "priority", "depends"])
            fl.set_format_string(start_row, "s", "")
            fl.set_format_string(start_row + 1, ".4f", "")
            fl.set_format_string(start_row + 2, "s", "")
        fl.set_header_string(0, headers)
    def get_repr_parts(self, queue_dict):
        ret_f = [self.get_id(), self.get_taw(), self.get_name(), self.get_pe_info()]
        ret_f.extend([self.get_user(), self.get_status(True), self.get_complex(), self.get_queue()])
        if self.__opt_dict.get("show_time_info", 1):
            ret_f.extend([self.get_sq_time(), self.get_run_time()])
        if self.is_waiting():
            ret_f.extend([sec_to_str(self.get_h_rt()), self.get_tickets(), self.get_depends()])
        else:
            ret_f += self.get_perc() + [self.get_mean_load(queue_dict)]
            if self.__opt_dict.get("node_flag", 0):
                ret_f.append(self.get_nodes())
        return ret_f
    def get_info(self, act_queue = None):
        ret_str = "%s %s (%d) %s" % (self.get_uid(), self.get_user(), self.num, self.get_type(act_queue))
        return ret_str

class queue(object):
    def __init__(self, name, opt_dict = {}):
        self.name = name
        self.i_cs = []
        self.jobs = {}
        self.mem_dict = {}
        self.access_info = {"userlists" : "all",
                            "projects"  : "all"}
        self.__opt_dict = opt_dict
        self.set_status()
        self.set_seq_no()
    def set_queue_access(self, q_a):
        # userlist
        if not q_a["user_lists"]  and not q_a["xuser_lists"]:
            # access for all users
            pass
        elif q_a["user_lists"] and not q_a["xuser_lists"]:
            # only users enlisted in user_lists are allowed to access queue
            self.access_info["userlists"] = " or ".join(q_a["user_lists"])
        elif not q_a["user_lists"] and q_a["xuser_lists"]:
            # users enlisted in xuser_lists are not allowed to access queue
            self.access_info["userlists"] = " and ".join(["not %s" % (x) for x in q_a["xuser_lists"]])
        else:
            # only users enlisted in user_lists and not listed in xusers_lists are allowed to acess the queue
            self.access_info["userlists"] = " or ".join([x for x in q_a["user_lists"] if x not in q_a["xuser_lists"]])
        # projects
        if not q_a["projects"]  and not q_a["xprojects"]:
            # access for all projects
            pass
        elif q_a["projects"] and not q_a["xprojects"]:
            # only projects enlisted in projects are allowed to access queue
            self.access_info["projects"] = " or ".join(q_a["projects"])
        elif not q_a["projects"] and q_a["xprojects"]:
            # projects enlisted in xprojects are not allowed to access queue
            self.access_info["projects"] = " and ".join(["not %s" % (x) for x in q_a["xprojects"]])
        else:
            # only projects enlisted in projects and not listed in xprojects_lists are allowed to acess the queue
            self.access_info["projects"] = " or ".join([x for x in q_a["projects"] if x not in q_a["xprojects"]])
    def set_mem_dict_entry(self, name, val):
        self.mem_dict[name] = val
    def set_seq_no(self, sq=0):
        self.__seq = sq
    def get_seq_no(self):
        return self.__seq
    def set_host(self, name):
        self.host = name.split(".")[0]
    def get_host(self):
        return self.host
    def set_type(self, q_t):
        self.q_t = q_t
    def set_arch(self, q_a):
        self.q_a = q_a
    def set_status(self, q_s="?"):
        if q_s:
            self.q_s = q_s
        else:
            self.q_s = "-"
    def get_status(self):
        return self.q_s
    def set_slots(self, s_u, s_t):
        self.s_u = int(s_u)
        self.s_t = int(s_t)
    def set_load(self, load):
        self.load = load
    def add_job(self, j_id, j_type):
        self.jobs.setdefault(j_id, 0)
        self.jobs[j_id] += 1
        #if j_id not in self.jobs, keys():
        #    self.jobs += [j_id]
    def add_init_complex(self, i_c):
        if i_c not in self.i_cs:
            self.i_cs.append(i_c)
            self.i_cs.sort()
    def get_full_type(self):
        if self.__opt_dict.get("show_type", 0) > 1:
            type_lod = {"B" : "Batch",
                        "I" : "Interactive",
                        "C" : "Checkpointing",
                        "P" : "Parallel",
                        "T" : "Transfer"}
            return ",".join(["(%s)%s" % (c, type_lod[c][1:]) for c in self.q_t])
        else:
            return self.q_t
    def get_full_status(self):
        if self.__opt_dict.get("show_stat", 0) > 1:
            stat_lod = {"-" : "-",
                        "u" : "unknown",
                        "a" : "alarm",
                        "A" : "alarm",
                        "C" : "calendar suspended",
                        "s" : "suspended",
                        "S" : "subordinate",
                        "d" : "disabled",
                        "D" : "disabled",
                        "E" : "error"}
            return ",".join(["(%s)%s" % (c, stat_lod[c][1:]) for c in self.q_s])
        else:
            return self.q_s
    def get_init_complexes(self):
        if len(self.i_cs):
            return ",".join(self.i_cs)
        else:
            return "-"
    def get_jobs(self, job_r_dict, job_s_dict):
        if len(self.jobs.keys()):
            job_d = {}
            for job, num in self.jobs.iteritems():
                if job_r_dict.has_key(job):
                    job_str = job_r_dict[job].get_info(self.name)
                elif job_s_dict.has_key(job):
                    job_str = "[%s]" % (job_s_dict[job].get_info(self.name))
                else:
                    job_str = None
                if job_str:
                    job_d.setdefault(job_str, 0)
                    job_d[job_str] += num
            # remove duplicates
            return ", ".join([job_d[key] > 1 and "%s x %d" % (key, job_d[key]) or "%s" % (key) for key in sorted(job_d.keys())])
        else:
            return "-"
    def get_repr_parts(self, queue_dict, job_r_dict, job_s_dict, job_w_dict):
        qname = self.name
        qspl = qname.split("@")
        if len(qspl) == 2:
            if qspl[1].split(".")[0] == self.host:
                qname = qspl[0]
        ret_f = [qname, self.host]
        if self.__opt_dict.get("show_seq_no", 0):
            ret_f.append(self.get_seq_no())
        if self.__opt_dict.get("show_type", 0):
            ret_f.append(self.get_full_type())
        if self.__opt_dict.get("show_stat", 0):
            ret_f.append(self.get_full_status())
        ret_f.extend([self.load, self.s_u, self.s_t, self.get_init_complexes()])
        if self.__opt_dict.get("include_access", 0):
            ret_f.extend([self.access_info["userlists"], self.access_info["projects"]])
        if self.__opt_dict.get("show_mem_info", 0):
            for m_type in ["virtual_total", "virtual_free"]:
                if self.mem_dict.has_key(m_type):
                    ret_f.append(self.mem_dict[m_type])
                else:
                    ret_f.append("???")
        ret_f.extend([self.get_jobs(job_r_dict, job_s_dict)])
        return ret_f
    def set_form_str(self, fl):
        headers = ["Queue", "Host"]
        act_idx = 2
        if self.__opt_dict.get("show_seq_no", 0):
            headers.append("seq")
            fl.set_format_string(act_idx, "d", "")
            act_idx += 1
        if self.__opt_dict.get("show_type", 0):
            headers.append("type")
            act_idx += 1
        if self.__opt_dict.get("show_stat", 0):
            headers.append("stat")
            act_idx += 1
        headers.extend(["load", "su", "st", "complex"])
        fl.set_format_string(act_idx, ".2f", "")
        act_idx += 1
        fl.set_format_string(act_idx, "d", "")
        act_idx += 1
        if self.__opt_dict.get("include_access", 0):
            headers.extend(["userlists", "projects"])
        if self.__opt_dict.get("show_mem_info", 0):
            headers.extend(["v_tot", "v_free"])
        headers.append("jobs")
        fl.set_header_string(0, headers)
    def __repr__(self):
        ret_str = "%-12s : %4s %4s %3.2f %d/%d %-s %-s" % (self.name, self.get_full_type(), self.get_full_status(), self.load, self.s_u, self.s_t, self.get_init_complexes(), self.get_jobs({}, {}))
        return ret_str
    
class sge_host(object):
    def __init__(self, top_el):
        self.name = top_el.attrib["name"]
        self.__value_dict = {}
        for sub_el in top_el.xpath("resourcevalue[@dominance='hl']"):
            self[sub_el.attrib["name"]] = sub_el.text
        for node_el in top_el.xpath("queue"):
            self.__value_dict.setdefault("queues", {})[node_el.attrib["name"]] = dict([(
                {"type_string" : "type",
                 "state_string" : "status",
                 "slots" : "total",
                 "slots_used" : "used"}.get(q_el.attrib["name"], q_el.attrib["name"]), q_el.text) for q_el in node_el.xpath("queuevalue")])
    def _str_to_memory(self, in_str):
        return int(float(in_str[:-1]) * {"k" : 1024,
                                         "m" : 1024 * 1024,
                                         "g" : 1024 * 1024 * 1024,
                                         "t" : 1024 * 1024 * 1024 * 0124}.get(in_str[-1].lower(), 1.))
    def get_value_dict(self):
        return self.__value_dict
    def _memory_to_str(self, in_val):
        pf_list = ["", "k", "M", "G", "T"]
        act_pf = pf_list.pop(0)
        while in_val > 1024:
            act_pf = pf_list.pop(0)
            in_val /= 1024.
        return "%.2f %sB" % (in_val,
                             act_pf)
    def keys(self):
        return self.__value_dict.keys()
    def has_key(self, key):
        return self.__value_dict.has_key(key)
    def get(self, key, default_value):
        return self.__value_dict.get(key, default_value)
    def __setitem__(self, key, value):
        if key.split("_")[-1] in ["total", "used", "free"]:
            self.__value_dict[key] = self._str_to_memory(value)
        elif key in ["num_proc"]:
            self.__value_dict[key] = int(value.split(".")[0])
        elif key in ["arch", "m_topology", "m_topology_inuse"]:
            self.__value_dict[key] = value
        else:
            self.__value_dict[key] = float(value)
    def __getitem__(self, key):
        return self.__value_dict[key]
    def get_complex_info(self, act_queue):
        cvs = act_queue["complex_values"]
        c_values = cvs.get("", {})
        for key, value in cvs.get(self.name, {}).iteritems():
            c_values[key] = value
        return ",".join(sorted(c_values.keys())) or "-"
    def get_memory_info(self, key):
        if self.has_key(key):
            return self._memory_to_str(self[key])
        else:
            return "???"
    def get_queue_type(self, q_name, long=False):
        if long:
            return ",".join(["(%s)%s" % (act_st, {"B" : "Batch",
                                                  "I" : "Interactive",
                                                  "C" : "Checkpointing",
                                                  "P" : "Parallel",
                                                  "T" : "Transfer"}[act_st][1:]) for act_st in self["queues"][q_name]["type"]])
        else:
            return self["queues"][q_name]["type"]
    def get_queue_state(self, q_name, long=False):
        if long:
            return ",".join(["(%s)%s" % (act_st, {"-" : "-",
                                                  "u" : "unknown",
                                                  "a" : "alarm",
                                                  "A" : "alarm",
                                                  "C" : "calendar suspended",
                                                  "s" : "suspended",
                                                  "S" : "subordinate",
                                                  "d" : "disabled",
                                                  "D" : "disabled",
                                                  "E" : "error"}[act_st][1:]) for act_st in self["queues"][q_name]["status"]])
        else:
            return self["queues"][q_name]["status"]
    def get_avg_load(self, q_name):
        return "%.2f" % (self.get("load_avg", 0.))
    def get_slots_used(self, q_name):
        return self["queues"][q_name]["used"]
    def get_slots_total(self, q_name):
        return self["queues"][q_name]["total"]
    def get_user_lists(self, act_q):
        pos_list = " or ".join(act_q["user_lists"].get("", []) + act_q["user_lists"].get(self.name, []))
        neg_list = " or ".join(act_q["xuser_lists"].get("", []) + act_q["xuser_lists"].get(self.name, []))
        return self._get_pos_neg_result(pos_list, neg_list)
    def get_project_lists(self, act_q):
        pos_list = " or ".join(act_q["projects"].get("", []) + act_q["projects"].get(self.name, []))
        neg_list = " or ".join(act_q["xprojects"].get("", []) + act_q["xprojects"].get(self.name, []))
        return self._get_pos_neg_result(pos_list, neg_list)
    def _get_pos_neg_result(self, p_list, n_list):
        if not p_list and not n_list:
            return "all"
        elif not n_list:
            return p_list
        elif not p_list:
            return "not (%s)" % (n_list)
        else:
            return "%s and not (%s)" % (p_list, n_list)
    def get_seq_no(self, act_q):
        return int((act_q["seq_no"].get(self.name, act_q["seq_no"][""]))[0])
    def get_init_complexes(self, act_q, i_complexes):
        c_list = act_q["complex_values"].get("", {}).keys() + act_q["complex_values"].get(self.name, {}).keys()
        return ",".join(sorted(set([c_name for c_name in c_list if c_name in i_complexes])))
    def get_pe_list(self, act_q):
        return ",".join(sorted(set(act_q["pe_list"].get("", []) + act_q["pe_list"].get(self.name, []))))
    def get_job_info(self, job_dict, j_list):
        if j_list:
            # output dict
            loc_dict = {}
            for j_id, j_type in sorted(j_list):
                job = job_dict[j_id]
                # old shitty code, in fact jobs where the pe has a controlling master defined have one slot too much
                # jobs with a controlling master have 2 mem_usage fields, other only 1
                #if job.has_key("mem_usage"):
                #    num_mem_usage = len(job["mem_usage"])
                #else:
                #    num_mem_usage = 1
                num_slots = len(job["master"])
                loc_dict.setdefault(j_id, {"owner"   : job["JB_owner"],
                                           "state"   : job["state"],
                                           "slots"   : num_slots,
                                           # buggy, FIXME, we have to use pe-info
                                           #"cmaster" : True if num_mem_usage == 2 else False,
                                           "list"    : []})
                if num_slots > 1:
                    loc_dict[j_id]["list"].append(j_type)
                else:
                    loc_dict[j_id]["list"].append("SINGLE")
            j_ids = sorted(loc_dict.keys())
            ret_list = []
            for j_id in j_ids:
                job = loc_dict[j_id]
                # FIXME
                #if job["cmaster"] and "SLAVE" in job["list"]:
                #    # remove one slave for jobs with an controlling master
                #    job["list"].remove("SLAVE")
                type_list = ["%s%s" % ("%d x " % (s_count) if s_count > 1 else "", s_type) for s_count, s_type in [(job["list"].count(a_type), a_type) for a_type in ["MASTER", "SLAVE", "SINGLE"]] if s_count]
                job_spec = "%s %s (%d) %s" % (j_id,
                                              job["owner"],
                                              job["slots"],
                                              ", ".join(type_list))
                
                if "s" in job["state"].lower():
                    job_spec = "[%s]" % (job_spec)
                ret_list.append(job_spec)
            return ",".join(ret_list)
        else:
            return "-"
    def show(self):
        pprint.pprint(self.__value_dict)
        
class sge_job(object):
    def __init__(self, job_el):
        # mapping:
        # JB_name        : name
        # JB_owner       : user
        # tasks          : if set task id
        # JAT_start_time : job starttime
        # we store everything as string, conversion to int / float only on the frontend or for sorting
        # running or pending
        prim_state = job_el.attrib["state"]
        self.running = {"running" : True,
                        "pending" : False}[prim_state]
        # store values
        self.__value_dict = {}
        for sub_el in job_el:
            self.add_tag(sub_el)
    def get_id(self):
        if self.has_key("tasks"):
            return "%s.%s" % (self["JB_job_number"], self["tasks"])
        else:
            return self["JB_job_number"]
    def add_tag(self, sub_el):
        tag_name = sub_el.tag
        if sub_el.attrib:
            sub_el.attrib["value"] = sub_el.text
            self.__value_dict.setdefault(tag_name, []).append(sub_el.attrib)
        else:
            if tag_name in ["queue_name", "master", "mem_usage"]:
                self.__value_dict.setdefault(tag_name, []).append(sub_el.text)
            elif tag_name.endswith("time"):
                self.__value_dict[tag_name] = self._sgetime_to_sec(sub_el.text)
            elif tag_name.startswith("predecessor_jobs"):
                self.__value_dict.setdefault(tag_name, []).append(sub_el.text)
            else:
                self.__value_dict[tag_name] = sub_el.text
    def get(self, key, def_value):
        return self.__value_dict.get(key, def_value)
    def __getitem__(self, key):
        return self.__value_dict[key]
    def keys(self):
        return self.__value_dict.keys()
    def has_key(self, key):
        return self.__value_dict.has_key(key)
    def _sgetime_to_sec(self, in_str):
        return datetime.datetime.strptime(in_str, "%Y-%m-%dT%H:%M:%S")
    def merge_job(self, other_job):
        for key in other_job.keys():
            if not self.has_key(key):
                self.__value_dict[key] = other_job[key]
            elif key in ["queue_name", "master", "mem_usage"]:
                # as of SGE 6.1u4 (?) we have only one mem_usage per node
                self.__value_dict[key].extend(other_job[key])
    def get_state(self, long=False):
        if long:
            return ",".join(["(%s)%s" % (act_st, {"q" : "queued",
                                                  "d" : "deleted",
                                                  "h" : "hold",
                                                  "r" : "running",
                                                  "R" : "Restarted",
                                                  "s" : "suspended",
                                                  "S" : "Subordinated",
                                                  "t" : "transfering",
                                                  "T" : "Threshold",
                                                  "w" : "waiting",
                                                  "o" : "orphaned"}[act_st][1:]) for act_st in self["state"]])
        else:
            return self["state"]
    def get_pe_info(self, pe_type):
        # can be grantet_PE or granted_pe
        pe_info = self.get("%s_PE" % (pe_type), None) or self.get("%s_pe" % (pe_type), None)
        if pe_info:
            # simplify it
            pe_info = pe_info[0]
            return "%s(%s)" % (pe_info["name"],
                               pe_info["value"])
        else:
            return "-"
    def get_init_requests(self, compl_dict):
        own_reqs = [stuff["name"] for stuff in self.get("hard_request", []) if stuff["value"].lower() == "true"]
        init_compls = [key for key, value in compl_dict.iteritems() if value.complex_type == "i"]
        return [i_name for i_name in init_compls if i_name in own_reqs]
    def get_running_queue(self):
        return [q_name.split("@")[0] for q_name, q_type in zip(self["queue_name"], self["master"]) if q_type == "MASTER"][0]
    def get_master_node(self):
        return [q_name.split("@")[1] for q_name, q_type in zip(self["queue_name"], self["master"]) if q_type == "MASTER"][0]
    def get_requested_queue(self):
        return self.get("hard_req_queue", "---")
    def get_running_nodes(self):
        # returns a beautified list of hosts, MASTER host is first
        master_qs = [q_name.split("@")[1].split(".")[0] for q_name, q_type in zip(self["queue_name"], self["master"]) if q_type == "MASTER"]
        slave_qs = [q_name.split("@")[1].split(".")[0] for q_name, q_type in zip(self["queue_name"], self["master"]) if q_type == "SLAVE"]
        return ",".join([part for part in [logging_tools.compress_list(master_qs, separator=","),
                                           logging_tools.compress_list(slave_qs, separator=",")] if part.strip()])
    def get_load_info(self, qhost_dict):
        node_names = set([q_name.split("@")[1].split(".")[0] for q_name in self["queue_name"]])
        load_list = []
        for n_name in node_names:
            if qhost_dict.has_key(n_name):
                if qhost_dict[n_name].has_key("load_avg"):
                    load_list.append(qhost_dict[n_name]["load_avg"])
        if load_list:
            mean_load = sum(load_list) / len(load_list)
            num_nodes = len(load_list)
            if num_nodes == 1:
                eff = 100
            else:
                max_load = max(load_list)
                if max_load:
                    eff = int((num_nodes / (max_load * float(num_nodes - 1)) * mean_load + 1./float(1 - num_nodes)) * 100)
                else:
                    eff = 0
            return "%.2f (%3d %%)" % (mean_load, eff)
        else:
            return "???"
        print load_list
    def get_start_time(self):
        s_time = self["JAT_start_time"]
        return logging_tools.get_relative_dt(s_time)
    def get_queue_time(self):
        q_time = self["JB_submission_time"]
        return logging_tools.get_relative_dt(q_time)
    def get_run_time(self):
        # returns time running
        run_time = abs(datetime.datetime.now() - self["JAT_start_time"])
        days = run_time.days
        secs = run_time.seconds
        return sec_to_str(24 * 3600 * days + secs)
    def get_wait_time(self):
        # returns time waiting in queue
        run_time = abs(datetime.datetime.now() - self["JB_submission_time"])
        days = run_time.days
        secs = run_time.seconds
        return sec_to_str(24 * 3600 * days + secs)
    def get_left_time(self):
        h_rt_req = [stuff for stuff in self.get("hard_request", []) if stuff["name"].lower() == "h_rt"]
        if h_rt_req:
            run_time = abs(datetime.datetime.now() - self["JAT_start_time"])
            h_rt = datetime.timedelta(0, int(h_rt_req[0]["value"]))
            left_time = abs(run_time - h_rt)
            return sec_to_str(left_time.days * 24 * 3600 + left_time.seconds)
        else:
            return "???"
    def get_h_rt_time(self):
        h_rt_req = [stuff for stuff in self.get("hard_request", []) if stuff["name"].lower() == "h_rt"]
        if h_rt_req:
            try:
                h_rt = datetime.timedelta(0, int(h_rt_req[0]["value"]))
            except:
                h_rt = datetime.timedelta(3600)
            return sec_to_str(h_rt.days * 24 * 3600 + h_rt.seconds)
        else:
            return "???"
    def get_priority(self):
        return "%.4f" % (float(self["JAT_prio"]))
    def get_dependency_info(self):
        if self.has_key("predecessor_jobs"):
            return "%d: %s" % (len(self["predecessor_jobs"]),
                               ",".join(sorted(self["predecessor_jobs"])))
        else:
            return ""
    def show(self):
        pprint.pprint(self.__value_dict)

class sge_info(object):
    def __init__(self, **args):
        """ arguments :
        verbose            : enables verbose messages
        sge_dict           : env_dict for accessing the SGE direct
        log_command        : how to handle log events (defaults to syslog)
        is_active          : flag, if set to false no direct calls to the SGE will be made
        thread_safe        : flag, if set locks update calls againts concurrent threads
        run_initial_update : flag, if set to false no initial update_call will be made
        init_dicts         : default values for the various dicts (for webfrontend)
        update_pref        : dict where the update preferences are stored (direct, server)
        ignore_dicts       : dicts to ignore
        server             : name of server to connect, defaults to localhost
        """
        self.__verbose = args.get("verbose", 0)
        self.__sge_dict = args.get("sge_dict", {})
        self.__log_com = args.get("log_command", args.get("log_com", None))
        # active: has sge_dict and can make calls to the system
        self.__is_active = args.get("is_active", True)
        self.__server = args.get("server", "localhost")
        # key : (relevance, call)
        setup_dict = {"hostgroup" : (0, self._check_hostgroup_dict),
                      "queueconf" : (1, self._check_queueconf_dict),
                      "complexes" : (2, self._check_complexes_dict),
                      "qhost"     : (3, self._check_qhost_dict),
                      "qstat"     : (4, self._check_qstat_dict)}
        self.__valid_dicts = [v_key for bla, v_key in sorted([(rel, key) for key, (rel, s_call) in setup_dict.iteritems()]) if v_key not in args.get("ignore_dicts", [])]
        self.__update_call_dict = dict([(key, s_call) for key, (rel, s_call) in setup_dict.iteritems()])
        self.__update_pref_dict = dict([(key, args.get("update_pref", {}).get(key, ["direct", "server"])) for key in self.__valid_dicts])
        self.__timeout_dicts = dict([(key, {"hostgroup" : 300,
                                            "qstat"     : 2}.get(key, 120)) for key in self.__valid_dicts])
        if self.__is_active:
            self._sanitize_sge_dict()
        self._init_update(args.get("init_dicts", {}))
        if args.get("run_initial_update", True) and self.__is_active:
            self.update()
    def __del__(self):
        pass
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        if self.__log_com:
            self.__log_com("[si] %s" % (what), log_level)
        else:
            logging_tools.my_syslog("[si] %s" % (what), log_level)
    def __getitem__(self, key):
        return self.__act_dicts[key]
    def get(self, key, def_value):
        return self.__act_dicts.get(key, def_value)
    def _init_update(self, start_dict):
        self.__upd_dict = dict([(key, 0.) for key in self.__valid_dicts])
        self.__act_dicts = dict([(key, {}) for key in self.__valid_dicts])
        for key, value in start_dict.iteritems():
            self.__act_dicts[key] = value
            self.__upd_dict[key] = time.time()
    def get_updated_dict(self, dict_name, **args):
        if self._check_for_update(dict_name):
            self.__act_dicts[dict_name] = self.__update_call_dict[dict_name]()
        return self.__act_dicts[dict_name]
    def update(self, **kwargs):
        upd_dicts = kwargs.get("update_list", self.__valid_dicts)
        # determine which dicts to update
        dicts_to_update = [dict_name for dict_name in upd_dicts if self._check_for_update(dict_name, kwargs.get("force_update", False))]
        #print "to update: ", dicts_to_update
        server_update = [dict_name for dict_name in dicts_to_update if (self.__update_pref_dict[dict_name] + ["not set"])[0] == "server"]
        if server_update:
            srv_name = self.__server
            s_time = time.time()
            # try server_update
            # new fancy 0MQ code
            zmq_context = zmq.Context(1)
            client = zmq_context.socket(zmq.DEALER)
            client.setsockopt(zmq.IDENTITY, "sge_tools:%d" % (os.getpid()))
            client.setsockopt(zmq.LINGER, 100)
            client.connect("tcp://%s:8009" % (srv_name))
            srv_com = server_command.srv_command(command="get_config")
            my_poller = zmq.Poller()
            my_poller.register(client, zmq.POLLIN)
            client.send_unicode(unicode(srv_com))
            timeout_secs = kwargs.get("timeout", 5)
            poll_result = my_poller.poll(timeout=timeout_secs * 1000)
            if poll_result:
                recv = client.recv_unicode()
            else:
                print "timeout after %d seconds" % (timeout_secs)
                recv = None
            client.close()
            zmq_context.term()
            try:
                srv_reply = server_command.srv_command(source=recv)
            except:
                pass
            else:
                for key in server_update:
                    full_key = "sge:%s" % (key)
                    if full_key in srv_reply:
                        self.__act_dicts[key] = srv_reply[full_key]
                        dicts_to_update.remove(key)
            e_time = time.time()
            if self.__verbose > 0:
                self.log("%s (server %s) took %s" % (", ".join(server_update),
                                                     srv_name,
                                                     logging_tools.get_diff_time_str(e_time - s_time)))
        for dict_name in dicts_to_update:
            s_time = time.time()
            self.__act_dicts[dict_name] = self.__update_call_dict[dict_name]()
            e_time = time.time()
            if self.__verbose > 0:
                self.log("%s (direct) took %s" % (dict_name,
                                                  logging_tools.get_diff_time_str(e_time - s_time)))
    def _sanitize_sge_dict(self):
        if not self.__sge_dict.has_key("SGE_ROOT"):
            if os.environ.has_key("SGE_ROOT"):
                # use SGE_ROOT from environment
                self.__sge_dict["SGE_ROOT"] = os.environ["SGE_ROOT"]
            else:
                try:
                    self.__sge_dict["SGE_ROOT"] = file("/etc/sge_root", "r").read().split()[0]
                except:
                    self.log("cannot read sge_root: %s" % (process_tools.get_except_info()),
                             logging_tools.LOG_LEVEL_ERROR)
                    self.__sge_dict["SGE_ROOT"] = "NO_SGE_ROOT_SET"
        if not self.__sge_dict.has_key("SGE_CELL"):
            if os.environ.has_key("SGE_CELL"):
                # use SGE_CELL from environment
                self.__sge_dict["SGE_CELL"] = os.environ["SGE_CELL"]
            else:
                try:
                    self.__sge_dict["SGE_CELL"] = file("/etc/sge_cell", "r").read().split()[0]
                except:
                    self.log("cannot read sge_cell: %s" % (process_tools.get_except_info()),
                             logging_tools.LOG_LEVEL_ERROR)
                    self.__sge_dict["SGE_CELL"] = "NO_SGE_CELL_SET"
        if not self.__sge_dict.has_key("SGE_ARCH"):
            c_stat, c_out = self._execute_command("/%s/util/arch" % (self.__sge_dict["SGE_ROOT"]))
            if c_stat:
                self.__sge_dict["SGE_ARCH"] = "NO_SGE_ARCH_SET"
            else:
                self.__sge_dict["SGE_ARCH"] = c_out
    def _check_for_update(self, d_name, force=False):
        act_time = time.time()
        if not self.__upd_dict[d_name] or abs(self.__upd_dict[d_name] - act_time) > self.__timeout_dicts[d_name] or force:
            do_upd = True
            self.__upd_dict[d_name] = act_time
        else:
            do_upd = False
        return do_upd
    def _get_com_name(self, c_name):
        return "/%s/bin/%s/%s" % (self.__sge_dict["SGE_ROOT"],
                                  self.__sge_dict["SGE_ARCH"],
                                  c_name)
    def _execute_command(self, command, **kwargs):
        # fancy, fancy
        os.environ["SGE_CELL"] = self.__sge_dict["SGE_CELL"]
        os.environ["SGE_SINGLE_LINE"] = "1"
        s_time = time.time()
        c_stat, c_out = commands.getstatusoutput(command)
        e_time = time.time()
        if c_stat:
            self.log("command '%s' gave (%d) in %s: %s" % (command,
                                                           c_stat,
                                                           logging_tools.get_diff_time_str(e_time - s_time),
                                                           c_out))
        if kwargs.get("simple_split", False) and not c_stat:
            c_out = [line.split(None, 1) for line in c_out.split("\n")]
        return c_stat, c_out
    def _check_queueconf_dict(self):
        qconf_dict = {}
        qconf_com = self._get_com_name("qconf")
        c_stat, c_out = self._execute_command("%s -sql" % (qconf_com),
                                              simple_split=True)
        if not c_stat:
            c_stat, c_out = self._execute_command("%s -sq %s" % (qconf_com,
                                                                 " ".join([line[0] for line in c_out])),
                                                  simple_split=True)
            if not c_stat:
                # sanitize act_q_dict
                act_q_dict = None
                # interpret queueconf
                act_q_name = ""
                for key, value in c_out:
                    if key == "qname":
                        if act_q_name:
                            qconf_dict[act_q_name] = act_q_dict
                        act_q_name, act_q_dict = (value, {})
                    act_q_dict[key] = value
                if act_q_name:
                    qconf_dict[act_q_name] = act_q_dict
        return qconf_dict
    def _check_hostgroup_dict(self):
        hgroup_dict = {}
        qconf_com = self._get_com_name("qconf")
        c_stat, c_out = self._execute_command("%s -shgrpl" % (qconf_com))
        self.__act_dicts["hostgroup"] = {}
        if not c_stat:
            for hgrp_name in c_out.split("\n"):
                c_stat, c_out = self._execute_command("%s -shgrp %s" % (qconf_com,
                                                                        hgrp_name),
                                                      simple_split=True)
                if not c_stat:
                    hgroup_dict[hgrp_name] = dict([(key, value) for key, value in c_out])
        return hgroup_dict
    def _check_complexes_dict(self):
        complex_dict = {}
        qconf_com = self._get_com_name("qconf")
        c_stat, c_out = self._execute_command("%s -sc" % (qconf_com))
        if not c_stat:
            for line in c_out.split("\n"):
                line = line.strip()
                if not line.startswith("#"):
                    for compl_name in line.split()[:2]:
                        if compl_name.strip() and not complex_dict.has_key(compl_name):
                            complex_dict[compl_name] = sge_complex("o" if compl_name in ["hostname", "qname", "q", "h"] else "s", compl_name, {compl_name : True}, {})
        return complex_dict
    def _check_qhost_dict(self):
        qstat_com = self._get_com_name("qhost")
        c_stat, c_out = self._execute_command("%s -F -q -xml" % (qstat_com))
        qhost_dict = {}
        xml_tree = etree.fromstring(c_out)
        for cur_queue in xml_tree.xpath(".//host[not(@name='global')]"):
            act_host = sge_host(cur_queue)
            qhost_dict[act_host.name] = act_host
        return qhost_dict
    def _check_qstat_dict(self):
        qstat_com = self._get_com_name("qstat")
        # -u * is important to get all jobs
        c_stat, c_out = self._execute_command("%s -u \* -r -t -ext -urg -pri -xml" % (qstat_com))
        job_dict = {}
        xml_tree = etree.fromstring(c_out)
        for cur_job in xml_tree.xpath(".//job_list"):
            act_job = sge_job(cur_job)
            job_dict[act_job.get_id()] = act_job
        self.__act_dicts["qstat"] = job_dict
        return job_dict
    def _parse_sge_values(self, old_dict, has_values):
        if type(old_dict) == type({}):
            # already transformed
            return old_dict
        # parse values of form GLOBAL,[node_spec=LOCAL],...
        act_vals = []
        for part in old_dict.split("["):
            if part.endswith(","):
                part = part[:-1]
            if part.endswith("]"):
                part = part[:-1]
            act_vals.append(part)
        all_args = act_vals.pop(0)
        sub_dict = {"" : all_args}
        for act_val in act_vals:
            node_name, args = act_val.split("=", 1)
            if node_name.startswith("@"):
                node_names = self["hostgroup"][node_name]["hostlist"].split()
            else:
                node_names = [node_name]
            for node_name in node_names:
                sub_dict[node_name.split(".")[0]] = args
        if has_values:
            # parse arguments
            for key, value in sub_dict.iteritems():
                sub_dict[key] = dict([(s_key, s_value) for s_key, s_value in [entry.split("=", 1) for entry in value.split(",") if entry.count("=")]])
        else:
            for key, value in sub_dict.iteritems():
                sub_dict[key] = [entry for entry in value.split() if entry not in ["NONE"]]
        return sub_dict
    def expand_host_list(self, q_name, shorten_names=False):
        # expand host_list of queue q_name if not already expanded
        act_q = self["queueconf"][q_name]
        if type(act_q["hostlist"]) == type(""):
            act_q["hostlist"] = sorted(list(set(sum([self["hostgroup"][entry]["hostlist"].split() if entry.startswith("@") else [entry] for entry in act_q["hostlist"].split() if entry != "NONE"], []))))
            if shorten_names:
                act_q["hostlist"] = [entry.split(".")[0] for entry in act_q["hostlist"]]

if __name__ == "__main__":
    print "This is a loadable module, exiting..."
    sys.exit(0)
