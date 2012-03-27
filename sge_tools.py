#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008 Andreas Lang-Nevyjel, init.at
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
try:
    import subprocess
except ImportError:
    subprocess = None
import sys
import re
import time
import os.path
import cPickle
import datetime
import pprint
import threading
import logging_tools
import net_tools
import server_command
import process_tools
import shelve
import fcntl

SQL_ACCESS = "cluster_full_access"

def execute_command(args):
    if type(args) == type(""):
        args = args.split()
    if subprocess and False:
        # not reliable, FIXME
        sp_obj = subprocess.Popen(args, 0, None, None, subprocess.PIPE, subprocess.PIPE)
        stat = sp_obj.wait()
        out_lines = sp_obj.stdout.read().strip().split("\n")
        err_lines = [line for line in sp_obj.stderr.read().strip().split("\n") if line]
    else:
        stat, out_lines = commands.getstatusoutput(" ".join(args))
        err_lines = []
        out_lines = out_lines.strip().split("\n")
    return stat, (out_lines, err_lines)

def expand_job_id(j_id):
    if j_id.isdigit():
        return [j_id]
    else:
        j_split = j_id.split(".")
        if len(j_split) == 2:
            return ["%s.%s" % (j_split[0], x) for x in expand_array_id(j_split[1])]
        else:
            raise ValueError, "Cannot parse job_id '%s', exiting..." % (j_id)
    
def expand_array_id(a_id):
    r_id = []
    parts = a_id.split(",")
    for part in parts:
        if part.isdigit():
            r_id.append(int(part))
        else:
            am = re.match("(?P<s_idx>\d+)-(?P<e_idx>\d+):(?P<step>\d+)$", part)
            bm = re.match("(?P<s_idx>\d+)-(?P<e_idx>\d+)$", part)
            if am:
                r_id += range(int(am.group("s_idx")), int(am.group("e_idx")) + 1, int(am.group("step")))
            elif bm:
                r_id += range(int(bm.group("s_idx")), int(bm.group("e_idx")) + 1)
            else:
                raise ValueError, "Cannot parse array_id '%s', exiting..." % (a_id)
    return r_id

def collapse_job_ids(j_ids):
    if j_ids:
        if j_ids[0].isdigit():
            return j_ids
        else:
            return ["%s.%s" % (x.split(".")[0], y) for y in collapse_array_ids([x.split(".")[1] for x in j_ids])]
    else:
        return j_ids
    
def collapse_array_ids(a_ids):
    s_ids = sorted([int(x) for x in a_ids])
    s_idx, e_idx, step = (None, None, None)
    r_array = []
    for val in s_ids:
        if not s_idx:
            s_idx = val
        elif e_idx:
            if val == e_idx+step:
                e_idx = val
            else:
                if s_idx+step == e_idx:
                    r_array.extend(["%d" % (s_idx), "%d" % (e_idx)])
                else:
                    r_array.append("%d-%d:%d" % (s_idx, e_idx, step))
                s_idx, e_idx, step = (val, None, None)
        else:
            e_idx = val
            step = e_idx-s_idx
    if s_idx:
        if e_idx:
            if s_idx+step == e_idx:
                r_array.extend(["%d" % (s_idx), "%d" % (e_idx)])
            else:
                r_array.append("%d-%d:%d" % (s_idx, e_idx, step))
        else:
            r_array.append("%d" % (s_idx))
    return [",".join(r_array)]

def transform_sge_output(in_lines, post_process=False):
    # process sge long_lines
    out_lines, act_line = ([], "")
    for line in in_lines:
        if line.endswith("\\"):
            act_line += "%s " % (line[:-1].lstrip())
        else:
            act_line += line.lstrip()
            out_lines.append(act_line)
            act_line = ""
    if act_line:
        out_lines.append(act_line)
    if post_process:
        out_lines = [x.strip().split(None, 1) for x in out_lines]
    return out_lines

def get_access_dict(sge_dict):
    qconf_com = "/%s/bin/%s/qconf -sq $(/%s/bin/%s/qconf -sql)" % (sge_dict["SGE_ROOT"],
                                                                   sge_dict["SGE_ARCH"],
                                                                   sge_dict["SGE_ROOT"],
                                                                   sge_dict["SGE_ARCH"])
    queue_access_dict = {}
    a_stat, (a_out, a_err) = execute_command(qconf_com)
    if a_stat:
        raise StandardError, "error calling %s (%d): %s" % (qconf_com, a_stat, "\n".join(a_out + a_err))
    access_keys = ["qname", "user_lists", "xuser_lists", "projects", "xprojects"]
    new_a_out = transform_sge_output(a_out, True)
    valid_keys = ["user_lists",
                  "xuser_lists",
                  "projects",
                  "xprojects"]
    act_qname = None
    for key, value in new_a_out:
        if key == "qname":
            act_qname = value
            queue_access_dict[act_qname] = {"ALL" : dict([(x, None) for x in valid_keys])}
        elif act_qname and key in valid_keys and value != "NONE":
            if value.count(","):
                # ","-separated list
                v_parts = [x.strip() for x in value.split(",")]
                for v_part in v_parts:
                    if v_part == "NONE":
                        # ignore default values
                        pass
                    elif v_part.startswith("["):
                        node_name, access_list = v_part[1:-1].split("=", 1)
                        node_name = node_name.split(".")[0]
                        access_list = [x.strip() for x in access_list.strip().split()]
                        if not queue_access_dict[act_qname].has_key(node_name):
                            queue_access_dict[act_qname][node_name] = dict([(x, None) for x in valid_keys])
                        queue_access_dict[act_qname][node_name][key] = access_list
                    else:
                        queue_access_dict[act_qname]["ALL"][key] = [v_part]
            else:
                # space separated
                queue_access_dict[act_qname]["ALL"][key] = value.split()
    return queue_access_dict

class sc_values_iterator(object):
    def __init__(self, sc, sk):
        self.__sc, self.__kl = (sc, sk)
    def __iter__(self):
        self.__index = 0
        return self
    def next(self):
        if self.__index == len(self.__kl):
            raise StopIteration
        act_key = self.__kl[self.__index]
        self.__index += 1
        return self.__sc[act_key]

class sc_iterkeys_iterator(object):
    def __init__(self, sc, sk):
        self.__sc, self.__kl = (sc, sk)
    def __iter__(self):
        self.__index = 0
        return self
    def next(self):
        if self.__index == len(self.__kl):
            raise StopIteration
        act_key = self.__kl[self.__index]
        self.__index += 1
        return act_key
    def index(self, k):
        return self.__kl.index(k)
    def __getitem__(self, k):
        return self.__kl[k]
    def __len__(self):
        return len(self.__kl)

class sc_iteritems_iterator(object):
    def __init__(self, sc, sk):
        self.__sc, self.__kl = (sc, sk)
    def __iter__(self):
        self.__index = 0
        return self
    def next(self):
        if self.__index == len(self.__kl):
            raise StopIteration
        act_key = self.__kl[self.__index]
        self.__index += 1
        return act_key, self.__sc[act_key]
    def index(self, k):
        return self.__kl.index(k)
    def __len__(self):
        return len(self.__kl)

class co_complexes(object):
    # checked-out version of sge_complexes
    def __init__(self, sge_cs):
        sge_cs.lock()
        self.complexes = dict([(k, co_complex(v)) for k, v in sge_cs.iteritems()])
        sge_cs.unlock()
        # build lookup-tables
        self.complex_names = sorted(self.complexes.keys())
        self.complex_types = {}
        for name, value in self.complexes.iteritems():
            self.complex_types.setdefault(value.complex_type, []).append(name)
    def __getitem__(self, key):
        return self.complexes[key]
    def has_key(self, key):
        return self.complexes.has_key(key)
    def get(self, key, def_value):
        return self.complexes.get(key, def_value)
    def keys(self):
        return self.complexes.keys()
        
class sge_complexes(object):
    def __init__(self, sge_arch, sge_root, sge_cell, opt_dict):
        self.__access_lock = threading.RLock()
        self.__sge_arch, self.__sge_root, self.__sge_cell = (sge_arch, sge_root, sge_cell)
        self.__opt_dict = opt_dict
        self.__complexes = {}
        self.__sge60 = not os.path.isfile("/%s/%s/common/product_mode" % (self.__sge_root, self.__sge_cell))
        self.set_update_timeout()
        if self.__sge60:
            self.update = self.update_60
        else:
            self.update = self.update_53
        # check for db reachability
        self.__db_reachable = False
        try:
            import mysql_tools
        except:
            pass
        else:
            try:
                db_con = mysql_tools.dbcon_container()
            except:
                pass
            else:
                try:
                    dc = db_con.get_connection(SQL_ACCESS)
                except:
                    db_con = None
                else:
                    self.__db_reachable = True
                    self.__db_con, self.__dc = (db_con, dc)
        self.update()
    def __del__(self):
        if self.__db_reachable:
            self.__dc.release()
            del self.__dc
            del self.__db_con
    def check_out_dict(self):
        # check out dict of complexes
        return co_complexes(self)
    def set_update_timeout(self, to=30*60):
        self.__update_timeout = to
        self.__last_timeout = time.time() - 2 * self.__update_timeout
    def lock(self):
        self.__access_lock.acquire()
    def unlock(self):
        self.__access_lock.release()
    def get_update_ok(self):
        return self.__update_ok
    def post_update(self):
        if self.__update_ok:
            self.__complex_keys = sorted(self.__complexes.keys())
        else:
            self.__complex_keys = []
    # functions to emulate dict
    def has_key(self, key):
        return key in self.__complex_keys
    def __getitem__(self, key):
        return self.__complexes[key]
    def iterkeys(self):
        return sc_keys_iterator(self, self.__complex_keys)
    def keys(self):
        return self.__complex_keys
    def values(self):
        return sc_values_iterator(self, self.__complex_keys)
    def iteritems(self):
        return sc_iteritems_iterator(self, self.__complex_keys)
    def get_log_lines(self):
        return self.__log_lines
    def update_60(self, force_update=False):
        act_time = time.time()
        self.__log_lines = []
        if abs(act_time - self.__last_timeout) > self.__update_timeout or force_update:
            self.__last_timeout = act_time
            self.lock()
            self.__update_ok = True
            self.__complexes = {}
            log_header = "Trying to get complexes in SGE 6.x mode..."
            if self.__db_reachable:
                self.__dc.execute("SELECT * FROM sge_complex")
                for db_rec in self.__dc.fetchall():
                    # init.at complexes, sge_queues need the complex defined in their config
                    name = db_rec["name"]
                    t_dict = {"%s_num_min" % (name) : db_rec.get("pe_slots_min", 1),
                              "%s_num_max" % (name) : db_rec.get("pe_slots_max", 1),
                              "%s_mt_time" % (name) : db_rec["total_time"],
                              "%s_m_time" % (name)  : db_rec["slot_time"],
                              "%s_queue" % (name)   : db_rec["default_queue"]
                              }
                    self.__complexes[name] = sge_complex("i", name, t_dict, self.__opt_dict)
                stat, (out, err_lines) = execute_command("/%s/bin/%s/qconf -sc" % (self.__sge_root, self.__sge_arch))
                if stat:
                    self.__log_lines.append("Error retrieving list of complexes (%d): '%s'" % (stat, "\n".join(out + err_lines)))
                else:
                    head = out.pop(0).lower()[1:].split()
                    c_lines = [x.strip().split() for x in out if not x.startswith("#")]
                    for line in [x for x in c_lines if x]:
                        for compl in [line[0], line[1]]:
                            if compl not in self.__complexes.keys():
                                t_dict = {compl : True}
                                # check for init.at meta-complex
                                if compl not in ["hostname", "qname", "q", "h"]:
                                    self.__complexes[compl] = sge_complex("o", compl, t_dict, self.__opt_dict)
                                else:
                                    self.__complexes[compl] = sge_complex("s", compl, t_dict, self.__opt_dict)
                # read queue config and add to complexes if necessary
                stat, (queue_list, err_lines) = execute_command("/%s/bin/%s/qconf -sq $(/%s/bin/%s/qconf -sql)" % (self.__sge_root,
                                                                                                                   self.__sge_arch,
                                                                                                                   self.__sge_root,
                                                                                                                   self.__sge_arch))
                if stat:
                    self.__log_lines.append("Error retrieving list of queues (%s): '%s'" % (stat, "\n".join(queue_list + err_lines)))
                else:
                    queue_list = transform_sge_output(queue_list, True)
                    for in_key, in_value in queue_list:
                        if in_key == "qname":
                            act_qname = in_value
                        elif in_key == "complex_values":
                            # remove spaces
                            while in_value.count(" "):
                                in_value = in_value.replace(" ", "")
                            # separate node part
                            new_list, is_node, sub_val = ([], False, [])
                            for act_val in [x.strip() for x in in_value.lower().split(",")]:
                                if act_val.startswith("["):
                                    is_node = True
                                if is_node:
                                    sub_val.append(act_val)
                                else:
                                    new_list.append(act_val)
                                if act_val.endswith("]"):
                                    new_list.append(",".join(sub_val))
                                    is_node, sub_val = (False, [])
                            for c_val in new_list:
                                if c_val.startswith("["):
                                    c_val = c_val[1:-1].split("=", 1)[1]
                                    sub_vals = c_val.split(",")
                                else:
                                    sub_vals = [c_val]
                                for act_c_val in sub_vals:
                                    if act_c_val.count("="):
                                        key, val = act_c_val.split("=", 1)
                                    else:
                                        key, val = (act_c_val, True)
                                    if self.__complexes.has_key(key) and val:
                                        self.__complexes[key].add_queue(act_qname)
            else:
                if os.environ.has_key("SGE_SERVER"):
                    sge_server = os.environ["SGE_SERVER"]
                else:
                    if os.path.isfile("/etc/sge_server"):
                        try:
                            sge_server = file("/etc/sge_server", "r").read().split("\n")[0].strip()
                        except:
                            self.__update_ok = False
                    else:
                        self.__update_ok = False
                if self.__update_ok:
                    errnum, data = net_tools.single_connection(host=sge_server, port=8009, command=server_command.server_command(command="get_complexes")).iterate()
                    if errnum:
                        self.__update_ok = False
                    else:
                        try:
                            srv_reply = server_command.server_reply(data)
                        except:
                            self.__update_ok = False
                        else:
                            if srv_reply.get_state() == server_command.SRV_REPLY_STATE_OK:
                                co_compl = srv_reply.get_option_dict()["co_complexes"]
                                self.__log_lines.append("recevied checked_out complexes (%s)" % (logging_tools.get_plural("byte", len(data[3:]))))
                                # build complexes from checked_out version
                                self.__complexes = dict([(k, sge_complex(co_compl[k].complex_type, k, co_compl[k].get_internal_dict(), self.__opt_dict)) for k in co_compl.complex_names])
                            else:
                                self.__update_ok = False
            self.post_update()
            self.unlock()
            if self.__log_lines:
                self.__log_lines.insert(0, log_header)
    def update_53(self, force_update=False):
        act_time = time.time()
        self.__log_lines = []
        if abs(act_time - self.__last_timeout) > self.__update_timeout or force_update:
            self.__last_timeout = act_time
            self.lock()
            self.__complexes = {}
            self.__update_ok = True
            log_header = "Trying to get complexes in SGE 5.3 mode..."
            stat, (out, err_lines) = execute_command("/%s/bin/%s/qconf -scl" % (self.__sge_root, self.__sge_arch))
            if stat:
                self.__log_lines.append("Error retrieving list of complexes (%d): '%s'" % (stat, "\n".join(out + err_lines)))
            else:
                c_list = [x for x in [y.strip() for y in out] if y not in ["xhost", "xqueue"]]
                for compl in c_list:
                    stat, (out, err_lines) = execute_command("/%s/bin/%s/qconf -sc %s" % (self.__sge_root, self.__sge_arch, compl))
                    if not stat:
                        head = out.pop(0).lower()[1:].split()
                        c_lines = [x.strip().split() for x in out if not x.startswith("#")]
                        #complexes[compl] = {}
                        t_dict = {}
                        c_type, c_name = ("s", None)
                        for line in [x for x in c_lines if x]:
                            new_dict = {}
                            for head_p in head:
                                new_dict[head_p] = line.pop(0)
                            t_dict[new_dict["name"]] = new_dict
                            if not re.match("^.*_.*$", new_dict["name"]):
                                c_name = new_dict["name"]
                        # check for init.at meta-complex
                        if c_type == "i":
                            self.__complexes[c_name] = sge_complex("i", c_name, t_dict, self.__opt_dict)
                        elif compl not in ["host", "queue"]:
                            self.__complexes[compl] = sge_complex("o", compl, t_dict, self.__opt_dict)
                        else:
                            self.__complexes[compl] = sge_complex(c_type, compl, t_dict, self.__opt_dict)
            self.post_update()
            self.unlock()
            if self.__log_lines:
                self.__log_lines.insert(0, log_header)

def compress_list(ql, queues = None):
    # node prefix, postfix, start_string, end_string
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

class co_complex(object):
    # checked-out version of sge_complex
    def __init__(self, sge_c):
        self.name = sge_c.name
        self.complex_type = sge_c.get_complex_type()
        self.__internal_dict = dict([(k, v) for k, v in sge_c.get_internal_dict().iteritems()])
    def __getitem__(self, key):
        return self.__internal_dict[key]
    def get(self, key, def_val):
        return self.__internal_dict.get(key, def_val)
    def get_internal_dict(self):
        return self.__internal_dict
    def get_resources(self):
        if self.complex_type == "i":
            return [self.name]
        else:
            return [x for x in self.__internal_dict.keys()]
    def get_complex_type(self):
        return self.complex_type

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
    def add_queue(self, queue, n_type, slots = 1):
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
    
class cluster_queue(object):
    def __init__(self, config, in_lines):
        self.__sge_config = config
        self.__value_dict = {}
        for key, value in in_lines:
            self[key] = value
    def __setitem__(self, key, value):
        if key == "hostlist":
            self.__value_dict[key] = self._parse_hostlist(value)
        else:
            self.__value_dict[key] = value
    def _parse_hostlist(self, in_list):
        return in_list.split()
    def __getitem__(self, key):
        return self.__value_dict[key]
    
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
    def __init__(self, name):
        self.name = name
        self.__value_dict = {}
    def _str_to_memory(self, in_str):
        return int(float(in_str[:-1]) * {"k" : 1024,
                                         "m" : 1024 * 1024,
                                         "g" : 1024 * 1024 * 1024,
                                         "t" : 1024 * 1024 * 1024 * 0124}.get(in_str[-1].lower(), 1.))
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
    def add_queue(self, q_parts):
        q_name = q_parts.pop(0)
        q_type = q_parts.pop(0)
        slotcount = [int(part) for part in q_parts.pop(0).split("/")]
        if len(slotcount) == 3:
            slots_reserved, slots_used, slots_total = slotcount
        else:
            slots_used, slots_total = slotcount
        if q_parts:
            q_status = q_parts[0]
        else:
            q_status = "-"
        self.__value_dict.setdefault("queues", {})[q_name] = {"type"   : q_type,
                                                              "used"   : slots_used,
                                                              "total"  : slots_total,
                                                              "status" : q_status}
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
    def __init__(self, prim_state):
        # mapping:
        # JB_name        : name
        # JB_owner       : user
        # tasks          : if set task id
        # JAT_start_time : job starttime
        # we store everything as string, conversion to int / float only on the frontend or for sorting
        # running or pending
        self.running = {"running" : True,
                        "pending" : False}[prim_state]
        # store values
        self.__value_dict = {}
    def get_id(self):
        if self.has_key("tasks"):
            return "%s.%s" % (self["JB_job_number"], self["tasks"])
        else:
            return self["JB_job_number"]
    def add_tag(self, tag_name, tag_dict, tag_value):
        if tag_dict:
            tag_dict["value"] = tag_value
            self.__value_dict.setdefault(tag_name, []).append(tag_dict)
        else:
            if tag_name in ["queue_name", "master", "mem_usage"]:
                self.__value_dict.setdefault(tag_name, []).append(tag_value)
            elif tag_name.endswith("time"):
                self.__value_dict[tag_name] = self._sgetime_to_sec(tag_value)
            elif tag_name.startswith("predecessor_jobs"):
                self.__value_dict.setdefault(tag_name, []).append(tag_value)
            else:
                self.__value_dict[tag_name] = tag_value
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
        update_pref        : dict where the update preferences are stored (direct, filecache, server)
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
        if args.get("thread_safe", True):
            self.__access_lock = threading.RLock()
        else:
            self.__access_lock = None
        if self.__is_active:
            self._sanitize_sge_dict()
            self._check_db_link()
        self._init_update(args.get("init_dicts", {}))
        if args.get("run_initial_update", True) and self.__is_active:
            self.update()
    def __del__(self):
        if self.__db_con:
            self.__db_con.close()
            del self.__db_con
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
    def _lock(self):
        if self.__access_lock:
            self.__access_lock.acquire()
    def _unlock(self):
        if self.__access_lock:
            self.__access_lock.release()
    def get_updated_dict(self, dict_name, **args):
        self._lock()
        if self._check_for_update(dict_name):
            self.__act_dicts[dict_name] = self.__update_call_dict[dict_name]()
        self._unlock()
        return self.__act_dicts[dict_name]
    def update(self, **args):
        self._lock()
        upd_dicts = args.get("update_list", self.__valid_dicts)
        # determine which dicts to update
        dicts_to_update = [dict_name for dict_name in upd_dicts if self._check_for_update(dict_name, args.get("force_update", False))]
        #print "to update: ", dicts_to_update
        server_update = [dict_name for dict_name in dicts_to_update if (self.__update_pref_dict[dict_name] + ["not set"])[0] == "server"]
        if server_update:
            srv_name = self.__server
            s_time = time.time()
            # try server_update
            errnum, data = net_tools.single_connection(mode="tcp",
                                                       host=srv_name,
                                                       port=8009,
                                                       command=server_command.server_command(command="get_config",
                                                                                             option_dict={"needed_dicts" : server_update}),
                                                       timeout=10.0,
                                                       protocoll=1).iterate()
            if not errnum:
                try:
                    srv_reply = server_command.server_reply(data)
                except:
                    pass
                else:
                    for key, value in srv_reply.get_option_dict().iteritems():
                        dicts_to_update.remove(key)
                        self.__act_dicts[key] = value
            else:
                self.log("error getting dicts from server %s (%d): %s" % (srv_name,
                                                                          errnum,
                                                                          str(data)),
                         logging_tools.LOG_LEVEL_ERROR)
            e_time = time.time()
            if self.__verbose > 0:
                self.log("%s (server %s) took %s" % (", ".join(server_update),
                                                     srv_name,
                                                     logging_tools.get_diff_time_str(e_time - s_time)))
        filecache_update = [dict_name for dict_name in dicts_to_update if (self.__update_pref_dict[dict_name] + ["not set"])[0] == "filecache"]
        if dict_name in filecache_update:
            db_file_name = "/tmp/jsi/jsi_db_%s" % (dict_name)
            lock_file_name = "%s.LOCK" % (db_file_name)
            # update is needed
            s_time = time.time()
            if os.path.isfile(db_file_name) and not args.get("no_file_cache", False):
                cached = True
                lf = file(lock_file_name, "w")
                fcntl.flock(lf, fcntl.LOCK_SH)
                my_shelve = shelve.open(db_file_name)
                self.__act_dicts[dict_name] = my_shelve["a"]
                my_shelve.close()
                fcntl.flock(lf, fcntl.LOCK_UN)
                lf.close()
            else:
                cached = False
                self.__act_dicts[dict_name] = self.__update_call_dict[dict_name]()
            e_time = time.time()
            if self.__verbose > 0:
                self.log("%s (fc) took %s" % (dict_name,
                                              logging_tools.get_diff_time_str(e_time - s_time)))
        for dict_name in dicts_to_update:
            s_time = time.time()
            self.__act_dicts[dict_name] = self.__update_call_dict[dict_name]()
            e_time = time.time()
            if self.__verbose > 0:
                self.log("%s (direct) took %s" % (dict_name,
                                                  logging_tools.get_diff_time_str(e_time - s_time)))
#             # write db back, test
#             if not cached:
#                 old_mask = os.umask(0)
#                 lf = file(lock_file_name, "w")
#                 fcntl.flock(lf, fcntl.LOCK_EX)
#                 test_db = shelve.open(db_file_name, "c")
#                 test_db["a"] = self[dict_name]
#                 test_db.sync()
#                 # important, sync
#                 test_db.close()
#                 fcntl.flock(lf, fcntl.LOCK_UN)
#                 lf.close()
#                 os.umask(old_mask)
        self._unlock()
    def _check_db_link(self):
        db_con = False
        try:
            import mysql_tools
        except:
            pass
        else:
            try:
                db_con = mysql_tools.dbcon_container()
            except:
                pass
            else:
                try:
                    dc = db_con.get_connection(SQL_ACCESS)
                except:
                    db_con = None
                else:
                    dc.release()
        self.__db_con = db_con
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
    def _execute_command(self, command, **args):
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
        if args.get("simple_split", False) and not c_stat:
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
        if self.__db_con:
            dc = self.__db_con.get_connection(SQL_ACCESS)
            dc.execute("SELECT * FROM sge_complex")
            for db_rec in dc.fetchall():
                # init.at complexes, sge_queues need the complex defined in their config
                name = db_rec["name"]
                t_dict = {"%s_num_min" % (name) : db_rec.get("pe_slots_min", 1),
                          "%s_num_max" % (name) : db_rec.get("pe_slots_max", 1),
                          "%s_mt_time" % (name) : db_rec["total_time"],
                          "%s_m_time" % (name)  : db_rec["slot_time"],
                          "%s_queue" % (name)   : db_rec["default_queue"]
                          }
                complex_dict[name] = sge_complex("i", name, t_dict, {})# self.__opt_dict)
            dc.release()
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
        c_stat, c_out = self._execute_command("%s -F -q" % (qstat_com))
        qhost_dict = {}
        if not c_stat:
            lines = c_out.split("\n")
            # remove header, separator and global
            lines.pop(0)
            lines.pop(0)
            lines.pop(0)
            # dummy act_host, sometimes we have global values (license stuff and so on) for the global host
            act_host = None
            for line in lines:
                if line[0] != " ":
                    act_host = sge_host(line.split()[0].split(".")[0])
                    qhost_dict[act_host.name] = act_host
                elif act_host:
                    line = line.strip()
                    if line.count(":"):
                        key, value = line.split(":", 1)[1].split("=", 1)
                        act_host[key] = value
                    else:
                        act_host.add_queue(line.split())
        return qhost_dict
    def _check_qstat_dict(self):
        qstat_com = self._get_com_name("qstat")
        # -u * is important
        c_stat, c_out = self._execute_command("%s -u \* -r -t -ext -urg -pri -xml" % (qstat_com))
        job_dict = {}
        if not c_stat:
            # helper dicts for parsing
            lines = c_out.split("\n")
            # remove xml header
            lines.pop(0)
            for line in lines:
                line = line.strip()
                tag_head = line.split(">")[0][1:].split()
                tag = tag_head.pop(0)
                tag_dict = dict([(key, value[1:-1]) for key, value in [tag_list.split("=", 1) for tag_list in tag_head]])
                tag_value = line[len(tag) + 2 : - (len(tag) + 3)]
                if tag in ["job_info", "queue_info", "/job_info", "/queue_info"]:
                    # ignore, just dummy parser
                    pass
                elif tag in ["job_list", "/job_list"]:
                    if tag == "job_list":
                        act_job = sge_job(tag_dict["state"])
                    else:
                        job_id = act_job.get_id()
                        if job_dict.has_key(job_id):
                            job_dict[job_id].merge_job(act_job)
                        else:
                            job_dict[job_id] = act_job
                else:
                    if tag_dict:
                        # tag_value starts after tag_dict
                        tag_value = tag_value.split(">")[1]
                    act_job.add_tag(tag, tag_dict, tag_value)
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

def get_all_dicts(sge_compls, user_list, job_list, sge_dict, opt_dict = {}, c_opts=""):
    # (sge_arch, sge_root, sge_cell)
    # improved version, only for sge6.x
    queue_dict, job_r_dict, job_s_dict, job_w_dict, ticket_dict, pri_dict = ({}, {}, {}, {}, {}, {})
    if opt_dict.get("include_access", 0):
        queue_access_dict = get_access_dict(sge_dict)
    else:
        queue_access_dict = {}
    # modify job_list
    act_job_list = []
    for j in job_list:
        act_job_list += expand_job_id(j)
    job_list = act_job_list
    all_resources, init_resources, other_resources = ([], [], [])
    other_res_rev_dict = {}
    all_complexes = sge_compls.complex_names
    sys_resources = ["queue", "host", "calendar"]
    for c_type, compl_list in sge_compls.complex_types.iteritems():
        for compl in compl_list:
            act_compl = sge_compls[compl]
            all_resources.extend(act_compl.get_resources())
            if c_type == "i":
                init_resources.extend(act_compl.get_resources())
            elif c_type == "o":
                other_resources.extend(act_compl.get_resources())
                for res in act_compl.get_resources():
                    other_res_rev_dict[res] = compl
    time_stamps = []
    time_stamps.append(("start", time.time()))
    qstat_com = "/%s/bin/%s/qstat -F -r -ext -urg -pri %s" % (sge_dict["SGE_ROOT"],
                                                              sge_dict["SGE_ARCH"],
                                                              c_opts)

    #print qstat_com
    stat, (out, err_lines) = execute_command(qstat_com)
    if stat:
        raise StandardError, "error calling %s (%d): %s" % (qstat_com, stat, "\n".join(out + err_lines))
    time_stamps.append(("process", time.time()))
    # separator
    sep_str = "-" * 20
    # dirty hack
    job_id_list = []
    # drop first line
    out.pop(0)
    if out:
        # append end-line
        out.append("EXIT")
        next_line = ""
        while out:
            if next_line:
                act_line = next_line
            else:
                act_line = out.pop(0)
            if act_line.startswith(sep_str):
                # start new queue
                queue_parts = out.pop(0).split()
                if len(queue_parts) == 5:
                    queue_name, queue_type, queue_slot_info, queue_load, queue_arch = queue_parts
                    queue_status = "-"
                elif len(queue_parts) == 6:
                    queue_name, queue_type, queue_slot_info, queue_load, queue_arch, queue_status = queue_parts
                else:
                    print "Queue parts have len %d: %s" % (len(queue_parts), " ".join(queue_parts))
                    sys.exit(-1)
                act_queue = queue(queue_name, opt_dict)
                queue_dict[queue_name] = act_queue
                #print "q", queue_name
                r_q_name = queue_name.split("@")[0]
                host_name = queue_name.split("@")[1].split(".")[0]
                if opt_dict.get("include_access", 0) and queue_access_dict.has_key(r_q_name):
                    act_queue.set_queue_access(queue_access_dict[r_q_name].get(host_name, queue_access_dict[r_q_name]["ALL"]))
                act_queue.set_type(queue_type)
                act_queue.set_arch(queue_arch)
                act_queue.set_status(queue_status)
                if queue_load.lower() == "-na-":
                    act_queue.set_load(0)
                else:
                    act_queue.set_load(float(queue_load))
                s_used, s_total = queue_slot_info.split("/")
                act_queue.set_slots(s_used, s_total)
                next_line = out.pop(0).strip()
                while next_line[0] in ["h", "q", "g"]:
                    rav_stuff, val_stuff = next_line.split(":", 1)
                    rav_src_dom, rav_src = rav_stuff
                    val_name, val_value = val_stuff.split("=", 1)
                    if rav_stuff == "qv":
                        if val_name in other_resources:
                            act_queue.add_init_complex(other_res_rev_dict[val_name])
                        elif val_name in init_resources or (val_name in all_resources and val_name not in sys_resources):
                            act_queue.add_init_complex(val_name)
                        else:
                            print "*", rav_src_dom, rav_src, val_name, val_value
                    elif rav_stuff == "hl":
                        if val_name in ["virtual_free", "virtual_total"]:
                            act_queue.set_mem_dict_entry(val_name, val_value)
                        else:
                            # other host-related stuff can be feeded into the queue
                            pass
                    elif rav_stuff == "qf":
                        if val_name == "hostname":
                            act_queue.set_host(val_value)
                        elif val_name in init_resources:
                            act_queue.add_init_complex(val_name)
                        elif val_name == "seq_no":
                            act_queue.set_seq_no(int(float(val_value)))
                    else:
                        # other stuff like consumables can be processed here
                        #print "+", rav_src_dom, rav_src, val_name, val_value
                        pass
                    next_line = out.pop(0).strip()
                    if not next_line:
                        break
                if next_line.startswith(sep_str):
                    pass
            else:
                act_job = None
                line_parts = act_line.split()
                lp_len = len(line_parts)
                if lp_len in [24, 25, 27, 28]:
                    # 25/28 for task_array jobs
                    job_id = line_parts.pop(0)
                    job_pri = float(line_parts.pop(0))
                    line_parts.pop(0)
                    job_npprio = line_parts.pop(0)
                    job_ntckts = line_parts.pop(0)
                    line_parts.pop(0)
                    line_parts.pop(0)
                    line_parts.pop(0)
                    line_parts.pop(0)
                    job_ppri = line_parts.pop(0)
                    job_name = line_parts.pop(0)
                    job_user = line_parts.pop(0)
                    job_project = line_parts.pop(0)
                    job_department = line_parts.pop(0)
                    job_status = line_parts.pop(0)
                    start_date = line_parts.pop(0)
                    start_time = line_parts.pop(0)
                    if lp_len in [25, 28]:
                        array_id = line_parts.pop(-1)
                    else:
                        array_id = None
                    if lp_len in [27, 28]:
                        cpu_time_used = line_parts.pop(0)
                        mem_used      = line_parts.pop(0)
                        io_used       = line_parts.pop(0)
                    tickets    = int(line_parts.pop(0))
                    ov_tickets = line_parts.pop(0)
                    op_tickets = line_parts.pop(0)
                    fp_tickets = line_parts.pop(0)
                    sp_tickets = line_parts.pop(0)
                    act_share  = line_parts.pop(0)
                    slots_used = int(line_parts.pop(0))
                    if array_id:
                        job_id_list = ["%s.%s" % (job_id, x) for x in expand_array_id(array_id)]
                    else:
                        job_id_list = [job_id]
                    if not opt_dict.get("expand_array_jobs", 0):
                        job_id_list = collapse_job_ids(job_id_list)
                    for job_id in job_id_list:
                        if job_user in (user_list or [job_user]):
                            if lp_len in [27, 28]:
                                if "s" in job_status or "S" in job_status:
                                    if not job_s_dict.has_key(job_id):
                                        job_s_dict[job_id] = job(job_id, opt_dict)
                                    act_job = job_s_dict[job_id]
                                else:
                                    if not job_r_dict.has_key(job_id):
                                        job_r_dict[job_id] = job(job_id, opt_dict)
                                    act_job = job_r_dict[job_id]
                            else:
                                if not job_w_dict.has_key(job_id):
                                    job_w_dict[job_id] = job(job_id, opt_dict)
                                act_job = job_w_dict[job_id]
                        else:
                            # dummy job, should be improved to NONE
                            act_job = job(job_id, opt_dict)
                        act_job.set_user(job_user)
                        act_job.set_name(job_name)
                        act_job.set_pri(float(job_pri))
                        act_job.set_status(job_status)
                        act_job.set_sq_time()
                        act_job.set_sq_time(start_date, start_time)
                        if "r" in job_status or "s" in job_status or "S" in job_status:
                            act_job_type = cpu_time_used.lower() == "na" and "SLAVE" or "MASTER"
                            act_job.add_queue(act_queue.name, act_job_type, slots_used)
                            act_job.add_host(act_queue.host, act_job_type)
                            act_job.set_type(act_job_type)
                            for sl in range(int(slots_used)):
                                act_queue.add_job(job_id, act_job_type)
                        if lp_len in [24, 25]:
                            act_job.set_priority(job_pri)
                            act_job.set_tickets(job_pri)
                            ticket_dict.setdefault(tickets, []).append(job_id)
                            pri_dict.setdefault(job_pri, []).append(job_id)
                        # new job, running
                        if line_parts:
                            print line_parts
                if act_job:
                    next_line = out.pop(0)
                    while next_line.startswith(" " * 7):
                        if next_line.count(":"):
                            res_name, res_stuff = [x.strip() for x in next_line.split(":", 1)]
                            res_name = res_name.lower()
                        else:
                            res_stuff = next_line.strip()
                        if res_stuff.strip():
                            if res_name == "requested pe":
                                act_job.set_pe(res_stuff)
                            elif res_name in ["hard requested queues", "master task hard requested queues", "master queue"]:
                                act_job.set_queue(res_stuff)
                            elif res_name == "predecessor jobs":
                                act_job.set_depend([x.strip() for x in res_stuff.split(",")])
                            elif res_name == "full jobname":
                                act_job.set_name(res_stuff)
                            elif res_name == "hard resources":
                                hr_name, hr_value = res_stuff.split("=", 1)
                                hr_value = hr_value.split()[0].lower()
                                if hr_value == "true":
                                    act_job.set_complex(hr_name)
                                elif hr_name == "h_rt":
                                    act_job.set_h_rt(hr_value)
                                elif hr_name == "qname":
                                    act_job.set_queue(hr_value)
                                else:
                                    #print hr_name, hr_value
                                    pass
                            else:
                                #print res_name, res_stuff
                                pass
                        next_line = out.pop(0)
                else:
                    if act_line.startswith("#") or act_line.count("PENDING JOBS"):
                        pass
                    else:
                        print lp_len, act_line
            if next_line == "EXIT":
                break
    # build dict queue->init.at complex
    queue_ic_dict = {}
    # old code, not working any more (need queues-property of init.at complex)
    #for ic in [x for x in sge_compls.values() if x.get_complex_type() == "i"]:
    #    if ic["queue"]:
    #        queue_ic_dict[ic["queue"]] = ic
    # delete invalid jobs if requested
    if opt_dict.get("only_valid_jobs", 0):
        del_j_ids = [k for k, v in job_w_dict.iteritems() if "E" in v.get_status() or "h" in v.get_status()]
        for del_j_id in del_j_ids:
            del job_w_dict[del_j_id]
        # correct ticket dict
        ticks_to_check = [k for k, v in ticket_dict.iteritems() if len([True for x in del_j_ids if x in v])]
        for tick_del in ticks_to_check:
            for del_j_id in [x for x in del_j_ids if x in ticket_dict[tick_del]]:
                ticket_dict[tick_del].remove(del_j_id)
    for j_dict in [job_r_dict, job_s_dict, job_w_dict]:
        for j_id, act_job in j_dict.iteritems():
            act_job.modify_status(queue_dict)
            # set complex for jobs where only the queue is given
            j_q, j_c = (act_job.get_queue(), act_job.get_complex())
            if j_q != "-" and not j_c and queue_ic_dict.has_key(j_q):
                act_job.set_complex(queue_ic_dict[j_q].get_name())
                # FIXME, unsupported
##             elif j_q == "-" and j_c and sge_compls.has_key(j_c) and sge_compls[j_c].get("queue", None):
##                 act_job.set_queue(sge_compls[j_c]["queue"])
            # append queue to all nodes
            act_job.simplify_queue_name()
    #print queue_ic_dict
    time_stamps.append(("end", time.time()))
    opt_dict["time_stamps"] = time_stamps
    return queue_dict, job_r_dict, job_s_dict, job_w_dict, ticket_dict, pri_dict

def cq_test():
    act_si = sge_info(verbose=1,
                      update_pref={"qhost"     : ["server", "direct"],
                                   "complexes" : ["server", "direct"],
                                   "hostgroup" : ["server", "direct"],
                                   "qstat"     : ["direct"],
                                   "queueconf" : ["server"]})
    #sjs(act_si)
    #sns(act_si)
    #scs(act_si)
#     print act_
#     all_cq = sge_config(sge_dict)
#     print len(cPickle.dumps(all_cq))
#     print all_cq.expand_host_list(all_cq.get_cluster_queue("hell.q")["hostlist"])
    sys.exit(0)

if __name__ == "__main__":
    cq_test()
    print "This is a loadable module, exiting..."
    sys.exit(0)
