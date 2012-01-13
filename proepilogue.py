#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008,2010,2011 Andreas Lang-Nevyjel, init.at
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
""" pro/epilogue script """

import sys
import threading
import Queue
import getopt
import pwd, grp
import time
import socket
import os
import os.path
import commands
import re
import shutil
import logging_tools
import process_tools
import configfile
import bz2
import types
import traceback
import fcntl
import pprint
import server_command
import net_tools
import threading_tools
try:
    import net_logging_tools
except ImportError:
    net_logging_tools = None
import optparse
# check for newest tools needed for new proepilogue
try:
    test_list = logging_tools.new_form_list()
except:
    NEW_CODE_OK = False
    # some dummy structs
else:
    NEW_CODE_OK = True
    del test_list
    sys.path.append("/usr/local/sbin")
    import hm_classes
    
SEP_LEN = 70
LOCAL_IP = "127.0.0.1"
PROFILE_PREFIX = ".mon"
CONFIG_FILE_NAME = "proepilogue.cf"

# old code below, beware
class message(object):
    mes_type = "?"
    arg = ""
    thread = ""
    time = 0.0
    def __init__(self, mes_type = "?", arg = ()):
        self.mes_type = mes_type
        self.arg = arg
        self.thread = threading.currentThread().getName()
        self.time = time.time()

# internal message (for thread communication)
# defined arg values:
# exit ...... request for exit
# exiting ... reply (yes, i'm exiting ;-) )
class internal_message(message):
    def __init__(self, arg = ()):
        message.__init__(self, "I", arg=arg)
    
# log message
class log_message(message):
    def __init__(self, str_val="", job_id=None, file_name="log"):
        message.__init__(self, "L", arg = (str_val, job_id, file_name))
    
class comsend_message(message):
    def __init__(self, arg):
        message.__init__(self, "CS", arg=arg)
        
class comsend_reply(message):
    def __init__(self, arg):
        message.__init__(self, "CR", arg=arg)
        
class set_ns(message):
    def __init__(self, arg):
        message.__init__(self, "SN", arg=arg)
        
class cpu(object):
    def __init__(self, num):
        self.__num = num
        self.set_occupied(False)
    def set_occupied(self, oc):
        self.__occupied = oc
    def is_occupied(self):
        return self.__occupied
    def __repr__(self):
        return "cpu %d (%s)" % (self.__num,
                                self.is_occupied() and "used" or "not used")
    
def parse_cpu_string(in_str, act_job):
    cpu_m0 = re.compile("^(?P<start>\d+)-(?P<end>\d+)$")
    r_cpus = []
    for in_cpu_p in [x.strip() for x in in_str.split(",")]:
        if in_cpu_p.isdigit():
            r_cpus.append(int(in_cpu_p))
        else:
            m0 = cpu_m0.match(in_cpu_p)
            if m0:
                c_min, c_max = (int(m0.group("start")),
                                int(m0.group("end")))
                r_cpus.extend(range(min(c_min, c_max), max(c_min, c_max) + 1))
            else:
                act_job.write("Cannot parse cpu-string '%s'" % (in_cpu_p))
    r_cpus = dict([(k, 0) for k in r_cpus]).keys()
    return r_cpus
    
class cpu_set(object):
    def __init__(self, act_job, dir_name, f_name):
        self.__cs_prefix = "cs"
        self.__act_job = act_job
        self.__file_name = f_name
        self.__dir_name = dir_name
        self.__occ_file_name = "%s.occ" % (f_name)
        self.init_from_file()
        self.read_occupation_from_file()
        self.__act_cpuset_filename = "%s/.cpuset_%s" % (self.__dir_name, self.__act_job.get_job_id())
    def log(self, what, glob=False):
        self.__act_job.log(what, glob)
    def read_cpuset_name(self):
        if os.path.exists(self.__act_cpuset_filename):
            self.__act_cpuset_name = file(self.__act_cpuset_filename, "r").read().split("\n")[0].strip().split()[1]
            self.log("read cpuset_name '%s' from disk" % (self.__act_cpuset_name), 1)
        else:
            self.__act_cpuset_name = None
            self.log("cannot read cpuset_name from disk (%s not found)" % (self.__act_cpuset_filename), 1)
    def increase_cpuset_name(self):
        cps_name = "%s/.act_cpuset_idxs" % (self.__dir_name)
        if os.path.isfile(cps_name):
            act_cps_idx = file(cps_name, "r").read().split("\n")[0].strip()
            try:
                act_cps_idx = int(act_cps_idx)
            except:
                act_cps_idx = 0
        else:
            act_cps_idx = 0
        act_cps_idx += 1
        if act_cps_idx > 1000000:
            act_cps_idx = 1
        file(cps_name, "w").write("%d" % (act_cps_idx))
        self.__act_cpuset_name = "%s%06d" % (self.__cs_prefix, act_cps_idx)
    def get_act_cpuset_name(self):
        return self.__act_cpuset_name
    def get_free_cpus(self):
        return sorted([k for k, v in self.__cpus.iteritems() if not v.is_occupied()])
    def get_occupied_cpus(self):
        return sorted([k for k, v in self.__cpus.iteritems() if v.is_occupied()])
    def init_from_file(self):
        in_dict = dict([(k.strip().lower(), v.strip()) for k, v in [x.strip().split("=", 1) for x in file(self.__file_name).read().split("\n") if x.strip() and x.count("=") and not x.strip().startswith("#")]])
        self.__flags = [x.strip().upper() for x in in_dict.get("flags", "EXCLUDE, MEMORY_LOCAL, MEMORY_EXCLUSIVE").split(",")]
        self.__cpus = dict([(k, cpu(k)) for k in parse_cpu_string(in_dict.get("cpus", "0"), self.__act_job)])
        self.__rules = [x.strip() for x in in_dict.get("rules", "x==x").split(",")]
    def read_occupation_from_file(self):
        if os.path.isfile(self.__occ_file_name):
            occ_l = [int(x) for x in file(self.__occ_file_name, "r").read().split("\n") if x.strip() and x.isdigit()]
            for occ in occ_l:
                if self.__cpus.has_key(occ):
                    if self.__cpus[occ].is_occupied():
                        self.__act_job.write("CPU %d already occupied..." % (occ))
                    else:
                        self.__cpus[occ].set_occupied(True)
                else:
                    self.__act_job.write("Trying to occupy unknown cpu %d" % (occ))
    def write_occupation_to_file(self):
        file(self.__occ_file_name, "w").write("\n".join(["%d" % (x) for x in self.get_occupied_cpus()] + [""]))
    def find_allocation_schemes(self, num_cpus):
        free_cpus = self.get_free_cpus()
        allocated_cpus = []
        found_lists = [[]]
        while True:
            new_lists = []
            for act_list in found_lists:
                if len(act_list):
                    prev_cpu = act_list[-1]
                else:
                    prev_cpu = None
                for free_cpu in [x for x in free_cpus if x not in act_list]:
                    if self.cpu_is_ok(free_cpu, prev_cpu):
                        new_lists.append(act_list + [free_cpu])
            found_lists = new_lists
            if not found_lists or max([len(x) for x in found_lists]) == num_cpus:
                break
        if found_lists:
            self.log("found %s for %s" % (logging_tools.get_plural("possible allocation scheme", len(found_lists)),
                                          logging_tools.get_plural("cpu", num_cpus)),
                     1)
        else:
            self.log(" *** found no allocation scheme for %s" % (logging_tools.get_plural("cpu", num_cpus)),
                     1)
        return found_lists
    def allocate_cpus(self, cpu_list):
        self.log("allocating cpu_list %s" % (logging_tools.compress_num_list(cpu_list)), 1)
        for act_cpu in cpu_list:
            self.__cpus[act_cpu].set_occupied(True)
    def free_cpus(self):
        if os.path.exists(self.__act_cpuset_filename):
            cpu_list = sorted([int(y) for y in [x for x in file(self.__act_cpuset_filename, "r").read().split("\n") if x.startswith("CPU")][0].split()[1].split(",")])
            self.log("Freeing %s from cpuset: %s" % (logging_tools.get_plural("cpu", len(cpu_list)),
                                                     ", ".join(["%d" % (x) for x in cpu_list])),
                     1)
            for cpu in cpu_list:
                self.__cpus[cpu].set_occupied(False)
        else:
            self.log("Cannot read cpuset-info from %s" % (self.__act_cpuset_filename), 1)
    def generate_cpuset(self, cpu_list):
        cs_lines = ["# %s" % (self.__act_cpuset_name)]
        cs_lines.extend([x for x in self.__flags])
        cs_lines.append("CPU %s" % (",".join(["%d" % (x) for x in cpu_list])))
        file(self.__act_cpuset_filename, "w").write("\n".join(cs_lines + [""]))
        os.chmod(self.__act_cpuset_filename, 0755)
        cpuset_com = "cpuset -q %s -c -f %s" % (self.__act_cpuset_name, self.__act_cpuset_filename)
        stat, out = commands.getstatusoutput(cpuset_com)
        self.log("status for cpuset_create_com '%s' : '%s' (%d)" % (cpuset_com, out, stat))
        if stat:
            succ = False
        else:
            succ = True
            self.log("Successully create cpuset %s for cpus %s" % (self.__act_cpuset_name,
                                                                   logging_tools.compress_num_list(cpu_list)))
        #if succ:
        #    stat, out = commands.getstatusoutput(
        return succ
    def remove_cpuset(self):
        if self.__act_cpuset_name:
            cpudel_com = "cpuset -q %s -d" % (self.__act_cpuset_name)
            stat, out = commands.getstatusoutput(cpudel_com)
            self.log("status for cpuset_del_com '%s' : '%s' (%d)" % (cpudel_com, out, stat))
            if stat:
                succ = False
            else:
                succ = True
                self.log("Successully deleted cpuset %s" % (self.__act_cpuset_name))
                os.unlink(self.__act_cpuset_filename)
    def cpu_is_ok(self, f_cpu, n_cpu):
        rules_ok = True
        for act_rule in self.__rules:
            if act_rule.startswith("!"):
                only_first = True
                act_rule = act_rule[1:]
            else:
                only_first = False
            
            try:
                do_ev = False
                if n_cpu != None or not act_rule.count("y"):
                    if only_first and n_cpu == None:
                        do_ev = True
                    elif not only_first:
                        do_ev = True
                if do_ev:
                    act_res = eval(act_rule)
                    if not act_res:
                        rules_ok = False
                    #print r, f_cpu, y, rules_ok
            except:
                self.log("Error in eval('%s') (x='%s', y='%s'): %s" % (act_rule,
                                                                       str(f_cpu),
                                                                       str(n_cpu),
                                                                       process_tools.get_except_info()),
                         1)
                rules_ok = False
        return rules_ok
        
class b_mon_keys(object):
    def __init__(self):
        self.__keys = {}
    def add_key(self, k):
        k_s = k.split(".")
        head_k = k_s.pop(0)
        if not self.__keys.has_key(head_k):
            self.__keys[head_k] = b_mon_keys()
        if k_s:
            self.__keys[head_k].add_key(".".join(k_s))
    def get_num_keys(self):
        return len(self.__keys.keys())
    def get_list(self):
        all_keys = sorted(self.__keys.keys())
        # check for zero-sublist
        if not [True for k in all_keys if self.__keys[k].get_num_keys()] and not [True for k in all_keys if not k[-1].isdigit()]:
            ret_list = [[logging_tools.compress_list(all_keys)]]
        else:
            ret_list = []
            for k in all_keys:
                if self.__keys[k].get_num_keys():
                    sub_list = self.__keys[k].get_list()
                    ret_list.extend([["%s." % (k)] + sub_list[0]] + [[""] + x for x in sub_list[1:]])
                else:
                    ret_list.append([k])
        return ret_list
    def get_string(self):
        all_keys = sorted(self.__keys.keys())
        # check for zero-sublist
        if not [True for k in all_keys if self.__keys[k].get_num_keys()] and not [True for k in all_keys if not k[-1].isdigit()]:
            ret_list = [logging_tools.compress_list(all_keys)]
        else:
            ret_list = []
            for k in all_keys:
                if self.__keys[k].get_num_keys():
                    ret_list.append("%s.(%s)" % (k,
                                                 self.__keys[k].get_string()))
                else:
                    ret_list.append(k)
        return ",".join(ret_list)
        
class rms(object):
    def __init__(self, rms_type, exec_mode=None):
        self.rms_type = rms_type
        if exec_mode:
            self.set_exec_mode(exec_mode)
    def set_exec_mode(self, mode="u"):
        self.exec_mode = mode
    def get_exec_mode(self):
        return self.exec_mode
    def get_exec_mode_long(self):
        return {"p"   : "prologue",
                "e"   : "epilogue",
                "ls"  : "lamstart",
                "le"  : "lamstop",
                "mvs" : "mvapich2start",
                "mve" : "mvapich2stop",
                "vs"  : "pvmstart",
                "ve"  : "pvmstop",
                "ps"  : "pestart",
                "pe"  : "pestop",
                "u"   : "unknown"}[self.exec_mode]
    def get_rms_type(self):
        return self.rms_type
    def get_rms_type_long(self):
        return {"s" : "SGE"}[self.rms_type]
    def nfs_to_mpi(self):
        return self.exec_mode in ["ls", "ps", "vs"]
    def nfs_to_infiniband(self):
        return self.exec_mode in ["mvs"]
    def infiniband_to_nfs(self):
        return self.exec_mode in ["mve"]
    def mpi_to_nfs(self):
        return self.exec_mode in ["le", "pe", "ve"]
    def is_primary_mode(self):
        # returns one of the actual mode is the first (for instance p -> ls -> le -> e)
        return (self.exec_mode in ["p", "u"])

class job(object):
    def __init__(self, job_num, task_id, log_queue):
        # job id
        self.job_num = int(job_num)
        self.set_task_id(task_id)
        self.log_queue = log_queue
        self.set_job_name()
        self.set_pe_name()
        self.set_user_group()
        self.set_queue_name()
        self.set_master_host()
        self.set_rms()
        self.set_local_host_stuff()
        self.set_ip_dict()
        self.set_name_dict()
    def write(self, what):
        try:
            print what
        except:
            self.log("error printing '%s': %s" % (what,
                                                  process_tools.get_except_info()))
    def set_ip_dict(self, ip_dict={}):
        self.ip_dict = ip_dict
    def set_name_dict(self, name_dict={}):
        self.name_dict = name_dict
    def set_pe_name(self, pe_name = None):
        self.pe_name = pe_name
    def get_ip_dict(self):
        return self.ip_dict
    def get_name_dict(self):
        return self.name_dict
    def get_pe_name(self):
        return self.pe_name
    def ip_to_name(self, ip):
        if ip == LOCAL_IP:
            return self.host_name
        else:
            return self.name_dict.get(ip, "<%s>" % (ip))
    def set_local_host_stuff(self):
        # local host stuff
        self.host_name = socket.gethostname()
        self.full_host_name = socket.getfqdn()
        try:
            self.host_ip = socket.gethostbyname(self.host_name)
        except:
            # IMS bugfix
            self.host_ip = "127.0.0.1"
    def set_task_id(self, t_id=None):
        self.task_id = t_id
    def get_task_id(self, normalize=False):
        if normalize:
            return self.task_id and "%d" % (self.task_id) or "1"
        else:
            return str(self.task_id)
    def get_local_host_name(self):
        return self.host_name
    def get_full_host_name(self):
        return self.full_host_name
    def get_local_host_ip(self):
        return self.host_ip
    def set_rms(self, rms=None):
        self.rms = rms
        self.set_node_list_name()
    def get_rms(self):
        return self.rms
    def log(self, out_str, out=0, f_name=None):
        if f_name:
            self.log_queue.put(log_message(out_str, self.get_job_id(), f_name))
        else:
            self.log_queue.put(log_message(out_str, self.get_job_id(), "log"))
        if out:
            self.write(out_str)
    def set_node_list_name(self):
        if self.rms:
            self.orig_node_list_name = os.getenv("PE_HOSTFILE")
            if self.orig_node_list_name:
                self.node_list_name = "/tmp/%s_%s" % (os.path.basename(self.orig_node_list_name), self.get_job_id())
            else:
                self.node_list_name = self.orig_node_list_name
        else:
            self.node_list_name = self.get_unset_str()
        self.log("Setting nodelist-filename to '%s'" % (self.node_list_name))
    def get_orig_node_list_name(self):
        return self.orig_node_list_name
    def get_node_list_name(self):
        return self.node_list_name
    def get_unset_str(self):
        return "<not set>"
    def get_job_num(self):
        return "%d" % (self.job_num)
    def get_job_id(self):
        if self.task_id:
            return "%d.%d" % (self.job_num, self.task_id)
        else:
            return "%d" % (self.job_num)
    def set_job_name(self, name="<not set>"):
        self.job_name = name
    def get_job_name(self):
        return self.job_name
    def set_user_group(self, user="root", group="root", u_id=0, g_id=0):
        self.user, self.group, self.uid, self.gid = (user, group, u_id, g_id)
    def get_user(self):
        return self.user
    def get_uid(self):
        return self.uid
    def get_group(self):
        return self.group
    def get_gid(self):
        return self.gid
    def set_queue_name(self, queue="<not set>"):
        self.queue_name = queue
    def get_queue_name(self):
        return self.queue_name
    def set_master_host(self, host="<not set>"):
        self.master_host = host
    def get_master_host(self):
        return self.master_host
    def get_owner_str(self, full=1):
        if full:
            return "user %s (%d), group %s (%d)" % (self.get_user(), self.get_uid(), self.get_group(), self.get_gid())
        else:
            return "%s (%d), %s (%d)" % (self.get_user(), self.get_uid(), self.get_group(), self.get_gid())
    def write_run_info(self, act_job):
        act_job.write("running on host %s [%s]" % (self.get_local_host_name(), self.get_local_host_ip()))
    def write_pe_header(self, act_job):
        self.log_queue.put(log_message("%s %s %s %s %s, %s %s " % ("pe", self.get_job_id(), self.get_rms().get_exec_mode_long(), self.get_rms().get_rms_type_long(), self.get_owner_str(0), self.get_job_name(), self.get_queue_name()), "general*"))
        sep_str = "-" * SEP_LEN
        act_job.write(sep_str)
        act_job.write("Starting %s for job %s, %s at %s" % (self.get_rms().get_exec_mode_long(), self.get_job_id(), self.get_owner_str(), time.ctime(time.time())))
        self.log("writing %s-header for job %s, %s" % (self.get_rms().get_exec_mode_long(), self.get_job_id(), self.get_owner_str()))
        if self.get_job_name() != self.get_unset_str():
            self.log("Jobname is '%s' in queue '%s'" % (self.get_job_name(), self.get_queue_name()), 1)
        return
    def get_stat_str(self, ret_value):
        stat_dict = {0 : "OK",
                     1 : "Error",
                     2 : "Warning"}
        return stat_dict.get(ret_value, "unknown ret_value %d" % (ret_value))
    def write_pe_footer(self, act_job, diff_time, ret_value):
        sep_str = "-" * SEP_LEN
        self.log("writing %s-footer for job %s, return value is %d (%s)" % (self.get_rms().get_exec_mode_long(), self.get_job_id(), ret_value, self.get_stat_str(ret_value)))
        act_job.write("%s finished for job %s, status %s, spent %s" % (self.get_rms().get_exec_mode_long(), self.get_job_id(), self.get_stat_str(ret_value), logging_tools.get_diff_time_str(diff_time)))
        self.log("%s took %s" % (self.get_rms().get_exec_mode_long(), logging_tools.get_diff_time_str(diff_time)))
        act_job.write(sep_str)
        return
    def write_mpi_header(self, act_job):
        self.log_queue.put(log_message("%s %s %s %s %s, %s %s " % ("pe", self.get_job_id(), self.get_rms().get_exec_mode_long(), self.get_rms().get_rms_type_long(), self.get_owner_str(0), self.get_job_name(), self.get_queue_name()), "general*"))
        sep_str = "-" * SEP_LEN
        act_job.write(sep_str)
        act_job.write("Starting %s for job %s, %s at %s" % (self.get_rms().get_exec_mode_long(), self.get_job_id(), self.get_owner_str(), time.ctime(time.time())))
        self.log("writing %s-header for job %s, %s" % (self.get_rms().get_exec_mode_long(), self.get_job_id(), self.get_owner_str()))
        if self.get_job_name() != self.get_unset_str():
            self.log("Jobname is '%s' in queue '%s'" % (self.get_job_name(), self.get_queue_name()), 1)
    def write_mpi_footer(self, act_job, diff_time, ret_value):
        sep_str = "-" * SEP_LEN
        self.log("writing %s-footer for job %s, return value is %d (%s)" % (self.get_rms().get_exec_mode_long(), self.get_job_id(), ret_value, self.get_stat_str(ret_value)))
        act_job.write("%s finished for job %s, status %s, spent %s" % (self.get_rms().get_exec_mode_long(), self.get_job_id(), self.get_stat_str(ret_value), logging_tools.get_diff_time_str(diff_time)))
        self.log("%s took %s" % (self.get_rms().get_exec_mode_long(), logging_tools.get_diff_time_str(diff_time)))
        act_job.write(sep_str)
    def log_config(self, conf_file):
        uid, gid = (os.getuid(), os.getgid())
        try:
            uname = pwd.getpwuid(uid)[0]
        except:
            uname = "<unknown>"
        try:
            gname = grp.getgrgid(gid)[0]
        except:
            gname = "<unknown>"
        self.log("Running with uid %d (%s), gid %d (%s)" % (uid, uname, gid, gname))
        log_config(self.log_queue, conf_file, log_append = self.get_job_id())
    def init_mvapich2_node_list(self, in_node_list):
        node_dict, node_list = ({}, [])
        for node in in_node_list:
            if node not in node_list:
                node_list.append(node)
                node_dict[node] = 0
            node_dict[node] += 1
        self.node_count = len(node_list)
        self.first_node = node_list.pop(0)
        self.first_node_cpu_count = node_dict[self.first_node]
        # write nodelistfile
        self.log("writing special mvapich2 nodefile")
        file(self.get_node_list_name(), "w").write("\n".join(["%s:%d" % (node_name, node_dict[node_name]) for node_name in node_list if node_name != self.first_node] + [""]))
    def show_node_lists(self, nfs_nl, mpi_nl):
        nfs_nl2 = sorted(dict([(x, True) for x in nfs_nl]).keys())
        mpi_nl2 = sorted(dict([(x, True) for x in mpi_nl]).keys())
        nfs_list = logging_tools.compress_list(nfs_nl2)
        mpi_list = logging_tools.compress_list(mpi_nl2)
        print "NFS Node-list (%s%s, %s): %s" % (nfs_list == mpi_list and "same as MPI-list, " or "",
                                                logging_tools.get_plural("node", len(nfs_nl2)),
                                                logging_tools.get_plural("slot", len(nfs_nl)),
                                                nfs_list)
        if nfs_list != mpi_list:
            print "MPI Node-list (%s, %s): %s" % (logging_tools.get_plural("node", len(mpi_nl2)),
                                                  logging_tools.get_plural("slot", len(mpi_nl)),
                                                  mpi_list)

def log_config(log_queue, conf_file, log_append=None):
    if conf_file:
        g_config.write_file(conf_file)
    for line in g_config.get_config_info():
        #log_queue.put(log_message("config %-20s : %-20s (%s, src %s)" % (k, str(g_config[k]), g_config.get_type(k), g_config.get_source(k)), log_append))
        log_queue.put(log_message("%s, src %s" % (line, log_append)))

def sec_to_str(in_sec):
    diff_d = int(in_sec / (3600 * 24))
    dt = in_sec - 3600 * 24 * diff_d
    diff_h = int(dt / 3600)
    dt -= 3600 * diff_h
    diff_m = int(dt / 60)
    dt -= diff_m * 60
    #if diff_d:
    out_f = "%2d:%02d:%02d:%02d" % (diff_d, diff_h, diff_m, dt)
    #else:
    #    out_f = "%2d:%02d:%02d" % (diff_h, diff_m, dt)
    return out_f

class new_con(net_tools.buffer_object):
    # connects to the package-server
    def __init__(self, (host, port, s_str, ret_queue, key)):
        self.__act_com = s_str
        self.__host = host
        self.__port = port
        self.__key = key
        self.__ret_queue = ret_queue
        net_tools.buffer_object.__init__(self)
    def setup_done(self):
        self.add_to_out_buffer(net_tools.add_proto_1_header(self.__act_com, True))
    def out_buffer_sent(self, send_len):
        #print self.__host, len(self.out_buffer), send_len, send_len == len(self.out_buffer)
        if send_len == len(self.out_buffer):
            self.out_buffer = ""
            self.socket.send_done()
        else:
            self.out_buffer = self.out_buffer[send_len:]
    def add_to_in_buffer(self, what):
        self.in_buffer += what
        p1_ok, p1_data = net_tools.check_for_proto_1_header(self.in_buffer)
        if p1_ok:
            #print "***", self.__host, "ok", len(p1_data)
            self.__ret_queue.put(comsend_reply((self.__key, self.__host, p1_data)))
            self.delete()
    def report_problem(self, flag, what):
        self.__ret_queue.put(comsend_reply((self.__key, self.__host, "error %s: %s" % (net_tools.net_flag_to_str(flag), what))))
        self.delete()

def network_thread(main_queue, log_queue, own_queue, comsend_queue, act_job):
    def log(arg, lev=logging_tools.LOG_LEVEL_OK):
        act_job.log("ns [%d]: %s" % (lev, arg))
    def log_hook(arg):
        act_job.log(arg)
    def error_hook(arg):
        err_num, err_str, add_data = arg
        got_hook((err_str, add_data), error = 1)
    def new_pid_hook(pid):
        act_job.log("is_net_server()-thread has pid %d" % (pid))
    def got_hook(arg, error = 0):
        result, (host, ret_queue, key) = arg
        if error:
            ret_queue.put(comsend_reply((key, host, "error %s" % (result))))
        else:
            ret_queue.put(comsend_reply((key, host, result)))
    def _connect_state_call(**args):
        if args["state"] == "error":
            host, port, s_str, ret_queue, key = args["socket"].get_add_data()
            ret_queue.put(comsend_reply((key, host, "error connecting")))
    def _connect_timeout(sock):
        host, port, s_str, ret_queue, key = sock.get_add_data()
        ret_queue.put(comsend_reply((key, host, "connect timeout")))
    def _new_server_connection(sock):
        return new_con(sock.get_add_data())
    if msi_block:
        msi_block.add_actual_pid()
        msi_block.save_block()
    my_name = threading.currentThread().getName()
    my_pid = os.getpid()
    log_queue.put(log_message("proc %d: %s-thread for proepilogue is now awake" % (my_pid, my_name)))
    act_job.log("Using new net_tools ...")
    ns = net_tools.network_server(timeout=2, log_hook=log, poll_verbose=False, exit_when_empty=True)
    ns.set_timeout(2)
    comsend_queue.put(set_ns(ns))
    c_flag = True
    while c_flag:
        try:
            it = own_queue.get_nowait()
        except Queue.Empty:
            it = None
        if it:
            if it.mes_type == "I":
                if it.arg == "exit":
                    c_flag = False
        ns.step()
    log_queue.put(log_message("proc %d: %s-thread for proepilogue exiting" % (my_pid, my_name)))
    if msi_block:
        msi_block.remove_actual_pid()
        msi_block.save_block()
    main_queue.put(internal_message("exiting"))
    
def comsend_thread(main_queue, log_queue, own_queue, network_queue, act_job):
    def log(arg, lev=logging_tools.LOG_LEVEL_OK):
        act_job.log("ns [%d]: %s" % (lev, arg))
    def log_hook(arg):
        act_job.log(arg)
    def error_hook(arg):
        err_num, err_str, add_data = arg
        got_hook((err_str, add_data), error = 1)
    def new_pid_hook(pid):
        act_job.log("is_net_server()-thread has pid %d" % (pid))
    def got_hook(arg, error = 0):
        result, (host, ret_queue, key) = arg
        if error:
            ret_queue.put(comsend_reply((key, host, "error %s" % (result))))
        else:
            ret_queue.put(comsend_reply((key, host, result)))
    def _connect_state_call(**args):
        if args["state"] == "error":
            host, port, s_str, ret_queue, key = args["socket"].get_add_data()
            ret_queue.put(comsend_reply((key, host, "error connecting")))
    def _connect_timeout(sock):
        host, port, s_str, ret_queue, key = sock.get_add_data()
        ret_queue.put(comsend_reply((key, host, "connect timeout")))
    def _new_server_connection(sock):
        return new_con(sock.get_add_data())
    if msi_block:
        msi_block.add_actual_pid()
        msi_block.save_block()
    my_name = threading.currentThread().getName()
    my_pid = os.getpid()
    log_queue.put(log_message("proc %d: %s-thread for proepilogue is now awake" % (my_pid, my_name)))
    act_job.log("Using new net_tools ...")
    ns = None
    delayed_objects = []
    c_flag = True
    while c_flag:
        it = own_queue.get()
        if it.mes_type == "I":
            if ns:
                ns.break_call()
            network_queue.put(internal_message("exit"))
            if it.arg == "exit":
                c_flag = False
            else:
                log_queue.put(log_message("Got unknown internal message: %s" % (it.arg)))
        elif it.mes_type == "SN":
            ns = it.arg
            if delayed_objects:
                for host, port, send_str, ret_queue, key in delayed_objects:
                    ns.add_object(net_tools.tcp_con_object(_new_server_connection, connect_state_call=_connect_state_call, connect_timeout_call=_connect_timeout, timeout=15, bind_retries=1, rebind_wait_time=1, target_port=port, target_host=host, add_data=(host, port, str(send_str).strip(), ret_queue, key)))
                delayed_objects = []
        elif it.mes_type == "CS":
            if ns:
                host, port, send_str, ret_queue, key = it.arg
                ns.add_object(net_tools.tcp_con_object(_new_server_connection, connect_state_call=_connect_state_call, connect_timeout_call=_connect_timeout, timeout=15, bind_retries=1, rebind_wait_time=1, target_port=port, target_host=host, add_data=(host, port, str(send_str).strip(), ret_queue, key)))
            else:
                delayed_objects.append(it.arg)
        else:
            log_queue.put(log_message("Got unknown message (type %s)" % (it.mes_type)))
    log_queue.put(log_message("proc %d: %s-thread for proepilogue exiting" % (my_pid, my_name)))
    if msi_block:
        msi_block.remove_actual_pid()
        msi_block.save_block()
    main_queue.put(internal_message("exiting"))
    
def logging_thread(main_queue, log_queue):
    def get_n_type(name, job_id):
        try:
            if os.path.isdir(name):
                n_type = "directory"
            else:
                n_type = "file"
        except:
            ret_list = [log_message("Unable to determine type of %s" % (name), job_id, "log")]
            n_type = "unknown"
        else:
            ret_list = []
        return ret_list, n_type
    def change_uid_gid(name, uid, gid, job_id):
        ret_list, n_type = get_n_type(name, job_id)
        try:
            os.chown(name, uid, gid)
        except:
            ret_list.append(log_message("Unable to change uid/gid of %s %s to %d/%d" % (n_type, name, uid, gid), job_id, "log"))
        else:
            ret_list.append(log_message("Changed uid/gid of %s %s to %d/%d" % (n_type, name, uid, gid), job_id, "log"))
        if job_id.startswith("general"):
            ret_list = []
        return ret_list
    def change_mode(name, job_id):
        ret_list, n_type = get_n_type(name, job_id)
        try:
            os.chmod(name, 0666)
        except:
            ret_list.append(log_message("Unable to change mode of %s %s to 0666" % (n_type, name), job_id, "log"))
        else:
            ret_list.append(log_message("Changed mode of %s %s to 0666" % (n_type, name), job_id , "log"))
        if job_id.startswith("general"):
            ret_list = []
        return ret_list
    
    if msi_block:
        msi_block.add_actual_pid()
        msi_block.save_block()
    divider = 1000
    my_name = threading.currentThread().getName()
    act_uid   , act_gid    = (os.getuid(), os.getgid())
    target_uid, target_gid = (act_uid    , act_gid    )
    job_dict = {}
    my_pid = os.getpid()
    root = g_config["LOG_DIR"]
    if not os.path.isdir(root):
        try:
            os.makedirs(root)
        except OSError:
            # we have to write to syslog
            logging_tools.my_syslog("Unable to create '%s' directory" % (root), 5)
        else:
            pass
    glog_name = "%s/log" % (root)
    glog = logging_tools.logfile(glog_name)
    if act_uid == 0 and act_gid == 0:
        os.chmod(glog_name, 0666)
    next_list = [log_message("-" * SEP_LEN)]
    next_list.append(log_message("proc %d: %s-thread for proepilogue is now awake" % (my_pid, my_name)))
    next_list.append(log_message("(%s) Opening log" % (my_name)))
    if g_config["MOTHER_SERVER"]:
        next_list.append(log_message("motherserver is %s" % (g_config["MOTHER_SERVER"])))
    else:
        next_list.append(log_message("no motherserver found (only reduced functionality)"))
    do_it = 1
    while do_it:
        act_le = next_list
        next_list = []
        act_le.append(log_queue.get())
        for it in act_le:
            if it.mes_type == "I":
                if type(it.arg) == type(""):
                    if it.arg == "exit":
                        do_it = 0
                    else:
                        next_list.append(log_message("got unknown internal-message with str '%s'" % (it.arg)))
                else:
                    log_str = "Trying to change target_uid / target_gid from (%d, %d) to (%d, %d)" % (target_uid, target_gid, it.arg[0], it.arg[1])
                    next_list.append(log_message(log_str))
                    target_uid, target_gid = it.arg
                    # change uid/gid for all job-logs
                    if target_uid != act_uid or target_gid != act_gid:
                        for jid, stuff in job_dict.iteritems():
                            if not os.path.isdir(stuff["dir"]):
                                try:
                                    os.makedirs(stuff["dir"])
                                except:
                                    next_list.append(log_message("Unable to create directory %s" % (stuff["dir"]), jid))
                                else:
                                    pass
                            next_list.extend(change_uid_gid(stuff["dir"], target_uid, target_gid, jid))
                            for h_name, h_stuff in stuff["add_handles"].iteritems():
                                next_list.extend(change_uid_gid(h_stuff["log_name"], target_uid, target_gid, jid))
                            if stuff.get("hist_name", ""):
                                next_list.extend(change_uid_gid(stuff["hist_name"], target_uid, target_gid, jid))
                                
            elif it.mes_type == "L":
                arg, j_id, f_name = it.arg
                if type(arg) == type(""):
                    arg = [arg]
                if j_id:
                    if j_id.endswith("*"):
                        j_id = j_id[:-1]
                        silent = 1
                    else:
                        silent = 0
                    if not job_dict.has_key(j_id):
                        try:
                            real_job_id = int(j_id.split(".")[0])
                        except ValueError:
                            new_dir = "%s/%s" % (root, j_id)
                        else:
                            lower_b = int(real_job_id / divider) * divider
                            upper_b = lower_b + divider - 1
                            new_dir = "%s/%d-%d/%s" % (root, lower_b, upper_b, j_id)
                        if os.path.isdir(new_dir):
                            hist_file_name = "%s/%s" % (new_dir, "history")
                        else:
                            try:
                                os.makedirs(new_dir)
                            except OSError:
                                logging_tools.my_syslog("Unable to create '%s' directory" % (new_dir), 5)
                                hist_file_name = "%s.%s" % (new_dir, "history")
                            else:
                                if target_uid != act_uid or target_gid != act_gid:
                                    next_list.extend(change_uid_gid(new_dir, target_uid, target_gid, j_id))
                                hist_file_name = "%s/%s" % (new_dir, "history")
                        new_hist = logging_tools.logfile(hist_file_name)
                        if target_uid != act_uid or target_gid != act_gid:
                            next_list.extend(change_uid_gid(hist_file_name, target_uid, target_gid, j_id))
                            next_list.extend(change_mode(hist_file_name, j_id))
                        job_dict[j_id] = {"silent"      : silent,
                                          "dir"         : new_dir,
                                          "hist_name"   : hist_file_name,
                                          "hist_handle" : new_hist,
                                          "add_handles" : {}}
                    if not job_dict[j_id]["add_handles"].has_key(f_name):
                        new_dir = job_dict[j_id]["dir"]
                        if os.path.isdir(new_dir):
                            log_file_name = "%s/%s" % (new_dir, f_name)
                        else:
                            log_file_name = "%s.%s" % (new_dir, f_name)
                        new_log = logging_tools.logfile(log_file_name)
                        if target_uid != act_uid or target_gid != act_gid:
                            next_list.extend(change_uid_gid(log_file_name, target_uid, target_gid, j_id))
                            next_list.extend(change_mode(log_file_name, j_id))
                        if not silent:
                            new_log.write("-" * SEP_LEN, header = 0)
                            new_log.write("(%s) Opening log" % (my_name))
                        job_dict[j_id]["add_handles"][f_name] = {"log_name"   : log_file_name,
                                                                 "log_handle" : new_log}
                        #job_dict[j_id]["hist_handle"].write("Opened %s for writing" % (job_dict[j_id]["log_name"]))
                    
                    act_handle = job_dict[j_id]["add_handles"][f_name]["log_handle"]
                    for act_line in arg:
                        act_handle.write("(%s) %s" % (it.thread, act_line))
                    if j_id == "general":
                        # write to all history handles also
                        for jid, stuff in job_dict.iteritems():
                            if stuff.has_key("hist_handle"):
                                for act_line in arg:
                                    stuff["hist_handle"].write("(%s) %s" % (it.thread, act_line))
                else:
                    for act_line in arg:
                        glog.write("(%s) %s" % (it.thread, act_line))
            else:
                glog.write("(%s) Got message with unknown type '%s'" % (it.thread, it.mes_type))
    glog.write("(%s) Closing log" % (my_name))
    for key in job_dict.keys():
        if not job_dict[key]["silent"]:
            for h_name, h_stuff in job_dict[key]["add_handles"].iteritems():
                h_stuff["log_handle"].write("(%s) Closing log" % (my_name))
        for h_name, h_stuff in job_dict[key]["add_handles"].iteritems():
            h_stuff["log_handle"].close()
        job_dict[key]["hist_handle"].close()
    glog.write("proc %d: %s-thread for proepilogue exiting" % (my_pid, my_name))
    glog.close()
    if msi_block:
        msi_block.remove_actual_pid()
        msi_block.save_block()
    main_queue.put(internal_message("exiting"))

def get_wrapper_script_name(act_job, act_env):
    dst_file = "%s/%s.%s.new" % (os.path.dirname(act_env["JOB_SCRIPT"]),
                                 act_job.get_job_num(),
                                 act_job.get_task_id(True))
    return dst_file
    
def delete_wrapper_script(act_rms, act_job, act_env):
    int_env = dict([(k, v) for k, v in [l.split("=", 1) for l in file("%s/config" % (act_env["SGE_JOB_SPOOL_DIR"]), "r").read().strip().split("\n") if l.count("=")]])
    env_keys = sorted(int_env.keys())
    src_file = act_env["JOB_SCRIPT"]
    dst_file = get_wrapper_script_name(act_job, act_env)
    if not dst_file.startswith("/"):
        act_job.log("refuse to delete wrapper script %s" % (dst_file))
        return
    act_job.log("Deleting wrapper-script (%s for %s)" % (dst_file,
                                                         src_file))
    if os.path.isfile(dst_file):
        try:
            os.unlink(dst_file)
        except:
            act_job.log("error deleting %s: %s" % (dst_file,
                                                   process_tools.get_except_info()))
        else:
            act_job.log("deleted %s" % (dst_file))
    else:
        act_job.log("no such file: %s" % (dst_file))
    if g_config["CPUSET_PE_NAME"] == int_env["pe"]:
        cpuset_dir_name = "%s/cpuset" % (g_config["SGE_ROOT"])
        cpuset_file_name = "%s/%s" % (cpuset_dir_name, int_env["queue"].split("@")[0])
        if os.path.isfile(cpuset_file_name):
            my_lockf = lock_cpuset(act_job)
            act_cpu_set = cpu_set(act_job, cpuset_dir_name, cpuset_file_name)
            act_cpu_set.read_cpuset_name()
            act_cpu_set.free_cpus()
            act_cpu_set.remove_cpuset()
            act_cpu_set.write_occupation_to_file()
            unlock_cpuset(act_job, my_lockf)
        else:
            act_job.log("Cannot find cpuset-file '%s', strange ..." % (cpuset_file_name), 1)
    
def lock_cpuset(act_job):
    cpuset_dir_name = "%s/cpuset" % (g_config["SGE_ROOT"])
    # return after lockfile for cpuset has been locked
    lock_file = "%s/.lock" % (cpuset_dir_name)
    my_lockf = file(lock_file, "w")
    act_job.log("Trying to lock file '%s' ..." % (lock_file))
    is_locked = False
    while not is_locked:
        try:
            fcntl.lockf(my_lockf.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError:
            act_job.log("... not successfull (%s, %s), waiting for %d seconds" % (process_tools.get_except_info(),
                                                                                  g_config["LOCK_ACQUIRE_WAIT_TIME"]))
            time.sleep(g_config["LOCK_ACQUIRE_WAIT_TIME"])
        else:
            is_locked = True
    act_job.log("File '%s' is now locked" % (lock_file))
    return my_lockf

def unlock_cpuset(act_job, lock_f):
    cpuset_dir_name = "%s/cpuset" % (g_config["SGE_ROOT"])
    lock_file = "%s/.lock" % (cpuset_dir_name)
    act_job.log("Unlock file '%s' ..." % (lock_file))
    fcntl.lockf(lock_f.fileno(), fcntl.LOCK_UN)
    lock_f.close()
    
def create_wrapper_script(act_rms, act_job, act_env):
    int_env = dict([(k, v) for k, v in [l.split("=", 1) for l in file("%s/config" % (act_env["SGE_JOB_SPOOL_DIR"]), "r").read().strip().split("\n") if l.count("=")]])
    env_keys = sorted(int_env.keys())
    src_file = act_env["JOB_SCRIPT"]
    dst_file = get_wrapper_script_name(act_job, act_env)
    if not dst_file.startswith("/"):
        act_job.log("refuse to create wrapper script %s" % (dst_file))
        return
    f_name = "env_int_%s" % (act_job.get_rms().get_exec_mode_long())
    act_job.log("Creating wrapper-script (%s for %s), internal dict has %s, logging to %s" % (dst_file,
                                                                                              src_file,
                                                                                              logging_tools.get_plural("key", len(env_keys)),
                                                                                              f_name))
    env_list = logging_tools.form_list()
    for env_key in env_keys:
        env_list.add_line((env_key, str(int_env[env_key])))
    act_job.log(str(env_list).split("\n"), 0, f_name)
    shell_path, shell_start_mode = (int_env.get("shell_path", "/bin/bash"),
                                    int_env.get("shell_start_mode", "posix_compliant"))
    cluster_queue_name = int_env["queue"].split("@")[0]
    act_job.log("shell_path is '%s', shell_start_mode is '%s'" % (shell_path,
                                                                  shell_start_mode))
    cpuset_dir_name = "%s/cpuset" % (g_config["SGE_ROOT"])
    do_cpuset = False
    no_cpuset_cause = []
    if g_config["CPUSET_PE_NAME"] == int_env["pe"]:
        num_cpus = int(int_env["pe_slots"])
        act_job.log("requested pe is '%s', trying to allocate a cpuset with %s on queue %s" % (int_env["pe"],
                                                                                               logging_tools.get_plural("cpu", num_cpus),
                                                                                               cluster_queue_name),
                    1)
        if os.path.isdir(cpuset_dir_name):
            cpuset_file_name = "%s/%s" % (cpuset_dir_name, cluster_queue_name)
            if os.path.isfile(cpuset_file_name):
                do_cpuset = True
            else:
                act_job.log("no cpuset-file '%s', doing normal startmethod" % (cpuset_file_name))
                no_cpuset_cause.append("no queue-local cpuset config %s" % (cpuset_file_name))
        else:
            act_job.log("no cpuset-dir %s" % (cpuset_dir_name))
            no_cpuset_cause.append("no cpuset-director %s" % (cpuset_dir_name))
        if do_cpuset:
            lock_f = lock_cpuset(act_job)
            act_cpu_set = cpu_set(act_job, cpuset_dir_name, cpuset_file_name)
            # generate new cpuset_name
            act_cpu_set.increase_cpuset_name()
            act_job.log("found cpuset-file at %s, cpuset_name is '%s'" % (cpuset_file_name,
                                                                          act_cpu_set.get_act_cpuset_name()), 1)
            a_lists = act_cpu_set.find_allocation_schemes(num_cpus)
            if a_lists:
                cpus = a_lists[0]
                act_cpu_set.allocate_cpus(cpus)
                act_cpu_set.generate_cpuset(cpus)
                cpu_set_name = act_cpu_set.get_act_cpuset_name()
            else:
                do_cpuset = False
                no_cpuset_cause.append("cannot allocate %s" % (logging_tools.get_plural("cpu", num_cpus)))
            act_cpu_set.write_occupation_to_file()
            unlock_cpuset(act_job, lock_f)
    if do_cpuset:
        if shell_start_mode == "posix_compliant" and shell_path:
            df_lines = ["#!%s" % ("/bin/sh"),
                        "echo 'wrapper_script, with cpu_set'",
                        "export BASH_ENV=$HOME/.bashrc",
                        "export CPUS=\"%s\"" % (" ".join(["%d" % (x) for x in cpus])),
                        "export NCPUS=%d" % (len(cpus)),
                        "exec cpuset -q %s -A %s %s $*" % (cpu_set_name, shell_path, src_file),
                        ""]
        else:
            df_lines = ["#!%s" % ("/bin/sh"),
                        "echo 'wrapper_script, with cpu_set'",
                        "export BASH_ENV=$HOME/.bashrc",
                        "export CPUS=\"%s\"" % (" ".join(["%d" % (x) for x in cpus])),
                        "export NCPUS=%d" % (len(cpus)),
                        "exec cpuset -q -A %s $*" % (cpu_set_name, src_file),
                        ""]
    else:
        if no_cpuset_cause:
            act_job.log("not using cpuset because: %s" % (", ".join(no_cpuset_cause)))
        if shell_start_mode == "posix_compliant" and shell_path:
            df_lines = ["#!%s" % ("/bin/sh"),
                        "export BASH_ENV=$HOME/.bashrc",
                        "exec %s %s $*" % (shell_path, src_file),
                        ""]
        else:
            df_lines = ["#!%s" % ("/bin/sh"),
                        "export BASH_ENV=$HOME/.bashrc",
                        "exec %s $*" % (src_file),
                        ""]
    df = file(dst_file, "w").write("\n".join(df_lines))
    act_job.log(["%3d : %s" % (num + 1, x) for num, x in zip(range(len(df_lines)), df_lines)], 0, "job_script_wrapper_%s" % (os.path.basename(dst_file)))
    os.chmod(dst_file, 0755)

def get_sge_resources():
    res_used = {}
    jsd = get_sge_job_spool_dir()
    if jsd != "notset":
        usage_file = "%s/usage" % (jsd)
        if os.path.isfile(usage_file):
            try:
                uf = file(usage_file, "r")
                ufl = dict([[y.strip() for y in x.strip().split("=", 1)] for x in uf.readlines()])
                uf.close()
            except:
                pass
            else:
                try:
                    if ufl.has_key("ru_wallclock"):
                        res_used["time_wall"] = sec_to_str(int(ufl["ru_wallclock"]))
                    if ufl.has_key("start_time") and ufl.has_key("end_time"):
                        res_used["elapsed"] = sec_to_str(int(ufl["end_time"]) - int(ufl["start_time"]))
                    if ufl.has_key("exit_status"):
                        res_used["exit_status"] = str(ufl["exit_status"])
                    if ufl.has_key("ru_utime"):
                        res_used["time_user"] = sec_to_str(int(ufl["ru_utime"]))
                    if ufl.has_key("ru_stime"):
                        res_used["time_system"] = sec_to_str(int(ufl["ru_stime"]))
##                     if ufl.has_key("ru_ixrss"):
##                         res_used["shared memory size"] = str(ufl["ru_ixrss"])
##                     if ufl.has_key("ru_isrss"):
##                         res_used["memory size"] = str(ufl["ru_isrss"])
                except:
                    pass
    return res_used
                
def get_sge_job_spool_dir():
    return os.getenv("SGE_JOB_SPOOL_DIR", "notset")

def get_sge_cell():
    return os.getenv("SGE_CELL", "notset")

def check_for_empty_string(name):
    v_value = g_config[name]
    if v_value in ["''", '""']:
        v_value = ""
    return v_value

def make_mpi_nodename(host):
    return "%s%s" % (host, check_for_empty_string("MPI_POSTFIX"))

def make_infiniband_nodename(host):
    return "%s%s" % (host, check_for_empty_string("INFINIBAND_POSTFIX"))

def make_normal_nodename(host, pf_name):
    pf_value = check_for_empty_string(pf_name)
    if pf_value and host.endswith(pf_value):
        return host[0 : -len(pf_value)]
    else:
        return host

def get_node_list(job):
    nf_ok = 0
    node_file = job.get_orig_node_list_name()
    if os.path.isfile(node_file):
        try:
            node_list = [x.strip() for x in file(node_file, "r").readlines() if len(x.strip())]
        except:
            job.log("Cannot read node_file %s" % (node_file))
        else:
            nf_ok = 1
            new_node_list = []
            for node_name, node_num in [x.split(" ")[0 : 2] for x in node_list]:
                new_node_list.extend([node_name.split(".")[0]] * int(node_num))
            node_list = new_node_list
    else:
        job.log("No node_file name '%s' found" % (node_file))
    if not nf_ok:
        node_list = [job.get_local_host_name()]
    # dictionary from all node-names to the normal nfs-names
    rtn_dict = dict(zip(node_list, node_list))
    if not g_config["HAS_MPI_INTERFACE"]:
        mpi_node_list = []
    else:
        if job.get_rms().nfs_to_infiniband():
            mpi_node_list = [make_infiniband_nodename(x) for x in node_list]
        elif job.get_rms().nfs_to_mpi():
            mpi_node_list = [make_mpi_nodename(x) for x in node_list]
        elif job.get_rms().infiniband_to_nfs():
            mpi_node_list = node_list
            node_list = [make_normal_nodename(x, "INFINIBAND_POSTFIX") for x in mpi_node_list]
            rtn_dict = dict(zip(node_list, node_list))
        elif job.get_rms().mpi_to_nfs():
            mpi_node_list = node_list
            node_list = [make_normal_nodename(x, "MPI_POSTFIX") for x in mpi_node_list]
            rtn_dict = dict(zip(node_list, node_list))
        for n_name, mpi_n in zip(node_list, mpi_node_list):
            rtn_dict[mpi_n] = n_name
    job.log("Nodelist consists of %s" % (logging_tools.get_plural("node", len(node_list))))
    job.log("NFS Node-list : %s" % (logging_tools.compress_list(node_list)))
    job.log("MPI Node-list : %s" % (logging_tools.compress_list(mpi_node_list)))
    # name mapping
    ip_dict = {}
    # ip mapping
    name_dict = {}
    # list of all ip-addresses
    ip_list = []
    # ips to connect (we don't connect to mpi-interfaces)
    con_list = []
    for node in node_list + mpi_node_list:
        if not ip_dict.has_key(node):
            try:
                ip = socket.gethostbyname(node)
            except:
                job.log("Error getting IP-address for node %s" % (node))
            else:
                ip_dict[node] = ip
                name_dict[ip] = rtn_dict[node]
                if not ip in ip_list:
                    ip_list.append(ip)
                    if node in node_list:
                        con_list.append(ip)
    job.set_ip_dict(ip_dict)
    job.set_name_dict(name_dict)
    return (nf_ok, node_list, mpi_node_list, ip_dict, name_dict, ip_list, con_list)

def write_node_list(in_list, job):
    node_file = job.get_node_list_name()
    try:
        node_f = file(node_file, "w").write("\n".join(in_list + [""]))
    except:
        job.log("Error writing node_file %s" % (node_file), 1)
        
def delete_node_list(job):
    node_file = job.get_node_list_name()
    try:
        os.unlink(node_file)
    except:
        job.log("Error deleting node_file %s" % (node_file), 1)
        
def kill_running_lam_daemons(send_queue, con_list, job):
    def _log(self, what, level=logging_tools.LOG_LEVEL_OK):
        job.log("(%d) %s" % (level, what))
    recv_queue = Queue.Queue(100)
    if g_config["KILL_RUNNING_LAM_DAEMONS"]:
        search_name = "-sessionsuffix"
        run_dict = {}
        num_send = len(con_list)
        job.log("Trying to get a list of all running lam-daemons on %s" % (logging_tools.get_plural("node", num_send)))
        for ip in con_list:
            command = "proclist"
            arg_str = "-r lamd"
            log_mes = " - Sending '%s' to ip %s, port %d, command %s" % (arg_str, ip, g_config["COLLSERVER_PORT"], command)
            job.log(log_mes)
            send_queue.put(comsend_message((ip, g_config["COLLSERVER_PORT"], "%s %s" % (command, arg_str), recv_queue, time.time())))
        for i in range(num_send):
            key, ip, ret_str = recv_queue.get().arg
            h_name = job.ip_to_name(ip)
            if ret_str.startswith("ok"):
                log_mess = ret_str
                try:
                    act_dict = server_command.net_to_sys(ret_str[3:])
                except:
                    job.log("Error converting answer from %s [%s], skipping..." % (h_name, ip))
                else:
                    job.log("Parsing answer from %s [%s]:" % (h_name, ip))
                    for pid, stuff in act_dict.iteritems():
                        cmdline = stuff.get("cmdline", [])
                        try:
                            s_idx = cmdline.index(search_name)
                        except ValueError:
                            job.log(" - pid %d (name %s) has no %s in his commandline, cannot determine job-id ..." % (pid, stuff["name"], search_name))
                        else:
                            if s_idx >= len(cmdline) - 1:
                                job.log(" - pid %d (name %s) has %s on last position in commandline, cannot determine job-id ..." % (pid, stuff["name"], search_name))
                            else:
                                suffix = cmdline[s_idx + 1]
                                log_str = " - pid %d (name %s) has %s %s" % (pid, stuff["name"], search_name, suffix)
                                sf_parts = suffix.strip().split("-")
                                sf_rms = sf_parts.pop(0)
                                sf_job_id = sf_parts.pop(0)
                                if sf_parts:
                                    sf_task_id = sf_parts.pop(0)
                                    if sf_task_id.isdigit():
                                        sf_task_id = int(sf_task_id)
                                    else:
                                        sf_task_id = None
                                else:
                                    sf_task_id = None
                                if sf_job_id.isdigit():
                                    sf_job_id = int(sf_job_id)
                                    real_job_id = "%d%s" % (sf_job_id, sf_task_id and ".%d" % (sf_task_id) or "")
                                    log_str += ", identified job with id %s" % (real_job_id)
                                    run_dict.setdefault(real_job_id, {})
                                    run_dict[real_job_id].setdefault(h_name, [])
                                    run_dict[real_job_id][h_name].append(pid)
                                else:
                                    log_str += ", no job identified"
                                job.log(log_str)
            else:
                log_mess = ret_str
            diff_time = time.time() - key
            job.log(" - Got answer for ip %s after %s (first 8 bytes): %s" % (ip, logging_tools.get_diff_time_str(diff_time), log_mess[:8]))
            if run_dict:
                for job_id, stuff in run_dict.iteritems():
                    job.log("Found %d lamd process for job %s on the following %s: %s" % (sum([len(x) for x in stuff.values()]),
                                                                                          job_id,
                                                                                          logging_tools.get_plural("host", len(stuff.keys())),
                                                                                          ", ".join(stuff.keys())))
                job.log("Requesting info about %s from %s: %s" % (logging_tools.get_plural("job", len(run_dict.keys())),
                                                                  g_config["SGE_SERVER"],
                                                                  ", ".join(run_dict.keys())))
                state, ret_str = net_tools.single_connection(host=g_config["SGE_SERVER"],
                                                             port=g_config["SGE_SERVER_PORT"],
                                                             command=server_command.server_command(command="check_job",
                                                                                                   option_dict={"job" : run_dict.keys()})).iterate()
                if ret_str.startswith("ok "):
                    try:
                        ret_dict = server_command.net_to_sys(ret_str[3:])
                    except:
                        job.log("Error unpickling return from sge-server regarding %d jobs" % (len(run_dict.keys())))
                    else:
                        for job_id, job_stuff in ret_dict["jobs"].iteritems():
                            if run_dict.has_key(job_id):
                                for host, host_num in job_stuff.get("hosts", {}).iteritems():
                                    if run_dict[job_id].has_key(host):
                                        job.log("  Removing %s (%s) for job %s on host %s" % (logging_tools.get_plural("pid", len(run_dict[job_id][h_name])),
                                                                                              ", ".join(["%d" % (x) for x in run_dict[job_id][h_name]]),
                                                                                              job_id,
                                                                                              host))
                                        del run_dict[job_id][host]
                        if run_dict:
                            del_ids = []
                            kill_dict = {}
                            for job_id, stuff in run_dict.iteritems():
                                if stuff:
                                    job.log("Have to kill %d lamd processes for job %s on the following %s: %s" % (sum([len(x) for x in stuff.values()]),
                                                                                                                   job_id,
                                                                                                                   logging_tools.get_plural("host", len(stuff.keys())),
                                                                                                                   ", ".join(stuff.keys())))
                                    for host, pid_list in stuff.iteritems():
                                        kill_dict.setdefault(host, [])
                                        kill_dict[host].extend(pid_list)
                                else:
                                    del_ids.append(job_id)
                            for del_id in del_ids:
                                del run_dict[del_id]
                            if kill_dict:
                                res_dict = net_tools.multiple_connections(log_hook=_log,
                                                                          target_list=[{"host"    : host,
                                                                                        "port"    : g_config["COLLSERVER_PORT"],
                                                                                        "command" : "signal 9 %s" % (",".join(["%d" % (x) for x in pid_list]))} for host, pid_list in kill_dict.iteritems()]).iterate()
                                for idx, target_stuff in res_dict.iteritems():
                                    was_error = target_stuff["errnum"]
                                    if was_error:
                                        job.log("error %d from %s: %s" % (target_stuff["errnum"],
                                                                          target_stuff["host"],
                                                                          target_stuff["ret_str"]))
                                    else:
                                        job.log("ok from %s: %s" % (target_stuff["host"],
                                                                    target_stuff["ret_str"]))
                                        
def kill_foreign_pids(send_queue, con_list, job):
    if g_config["CLEAR_MACHINES"]:
        clear_exclude_list = [x.strip() for x in g_config.get("CLEAR_EXCLUDE", "").split(",") if x.strip()]
        if job.get_queue_name() in clear_exclude_list:
            job.log("Not killing processes because queue %s is in clear_exclude_list %s" % (job.get_queue_name(), ", ".join(clear_exclude_list)))
        else:
            job.log("Trying to kill all processes with uid >= %d on %s" % (g_config["MIN_KILL_UID"], logging_tools.get_plural("node", len(con_list))))
            general_send(send_queue, con_list, job, "pskill", "9 %d sge_shepherd,portmap" % (g_config["MIN_KILL_UID"]))

def remove_foreign_ipcs(send_queue, con_list, job):
    if g_config["CLEAR_MACHINES"]:
        clear_exclude_list = [x.strip() for x in g_config.get("CLEAR_EXCLUDE", "").split(",") if x.strip()]
        if job.get_queue_name() in clear_exclude_list:
            job.log("Not removing IPC-objects because queue %s is in clear_exclude_list %s" % (job.get_queue_name(), ", ".join(clear_exclude_list)))
        else:
            job.log("Trying to remove all IPC-objects with uid >= %d on %s" % (g_config["MIN_KILL_UID"], logging_tools.get_plural("node", len(con_list))))
            general_send(send_queue, con_list, job, "ipckill", "%d" % (g_config["MIN_KILL_UID"]))

def umount_nfs_mounts(send_queue, con_list, job):
    def decode_umount(in_str):
        if in_str.startswith("ok "):
            try:
                res_dict = server_command.net_to_sys(in_str[3:])
            except:
                return "error decoding %s (first 10 Bytes)" % (in_str[:10])
            else:
                ok_list, err_list = (res_dict.get("ok_list", []),
                                     res_dict.get("err_list", []))
                return "umount result: %d OK (%s), %s (%s)" % (len(ok_list),
                                                               ", ".join([x[0] for x in ok_list]),
                                                               logging_tools.get_plural("problem", len(err_list)),
                                                               ", ".join([x[0] for x in err_list]))
        else:
            return in_str
    job.log("Trying to umount all unneeded NFS-mounts on %s" % (logging_tools.get_plural("node", len(con_list))))
    general_send(send_queue, con_list, job, "umount", "", decode_func=decode_umount)

def start_monitor_threads(send_queue, con_list, job, m_id):
    if g_config["MONITOR_JOBS"]:
        job.log("Trying to start the monitor_processes with id '%s' on %s" % (m_id, logging_tools.get_plural("node", len(con_list))))
        general_send(send_queue, con_list, job, "start_monitor", m_id)

def stop_monitor_threads(send_queue, con_list, job, m_id):
    if g_config["MONITOR_JOBS"]:
        job.log("Trying to stop the monitor_processes with id '%s' on %s" % (m_id, logging_tools.get_plural("node", len(con_list))))
        general_send(send_queue, con_list, job, "stop_monitor", m_id)

def general_send(send_queue, con_list, job, command, send_str, log_complete_string=1, decode_func=None):
    recv_queue = Queue.Queue(100)
    num_send = len(con_list)
    for ip in con_list:
        send_queue.put(comsend_message((ip, g_config["COLLSERVER_PORT"], "%s %s" % (command, send_str), recv_queue, time.time())))
    log_mes = " - Sending '%s' to %s: %s, port %d, command %s" % (send_str,
                                                                  logging_tools.get_plural("IP", len(con_list)),
                                                                  ", ".join(con_list),
                                                                  g_config["COLLSERVER_PORT"], command)
    job.log(log_mes)
    ret_dict, ret_dict_lut, time_dict = ({}, {}, {})
    for i in range(num_send):
        key, ip, ret_str = recv_queue.get().arg
        ret_dict[ip] = ret_str
        if log_complete_string:
            ret_dict_lut.setdefault(ret_str, []).append(ip)
        else:
            ret_dict_lut.setdefault(logging_tools.get_plural("byte", len(ret_str)), []).append(ip)
        time_dict[ip] = logging_tools.get_diff_time_str(time.time() - key)
    rdl_keys = sorted(ret_dict_lut.keys())
    job.log(" - Got %s:" % (logging_tools.get_plural("different answer", len(rdl_keys))))
    for rdl_key in rdl_keys:
        if decode_func:
            rdl_out_str = decode_func(rdl_key)
        else:
            rdl_out_str = rdl_key
        ip_list = ret_dict_lut[rdl_key]
        job.log(" - Got answer '%s' from %s: %s" % (rdl_out_str, logging_tools.get_plural("IP", len(ip_list)), ", ".join(ip_list)))
    return ret_dict

def collect_monitor_threads(send_queue, con_list, job, m_id, ip_dict, node_list=[], mpi_node_list=[]):
    recv_queue = Queue.Queue(100)
    mon_dict = {}
    if g_config["MONITOR_JOBS"]:
        num_send = len(con_list)
        job.log("Trying to collect the monitor_processes with id '%s' on %s" % (m_id, logging_tools.get_plural("node", num_send)))
        command = "monitor_info"
        arg_str = m_id
        for ip in con_list:
            send_queue.put(comsend_message((ip, g_config["COLLSERVER_PORT"], "%s %s" % (command, arg_str), recv_queue, time.time())))
        log_mes = " - Sending '%s' to %s: %s, port %d, command %s" % (arg_str,
                                                                      logging_tools.get_plural("IP", len(con_list)),
                                                                      ", ".join(con_list),
                                                                      g_config["COLLSERVER_PORT"], command)
        job.log(log_mes)
        for i in range(num_send):
            key, ip, ret_str = recv_queue.get().arg
            if ret_str.startswith("cok"):
                if bz2:
                    try:
                        ret_dict, log_mess = (server_command.net_to_sys(bz2.decompress(ret_str[4:])),
                                              "ok bz2-dict (size %s)" % (logging_tools.get_plural("byte", len(ret_str))))
                    except:
                        ret_dict, log_mess = ({}, "error cannot interpret %s" % (ret_str))
                else:
                    ret_dict, log_mess = ({}, "error no bz2-lib")
            elif ret_str.startswith("ok"):
                try:
                    ret_dict, log_mess = (server_command.net_to_sys(ret_str[3:]),
                                          "ok dict (size %s)" % (logging_tools.get_plural("byte", len(ret_str))))
                except:
                    ret_dict, log_mess = ({}, "error cannot interpret %s" % (ret_str))
            else:
                ret_dict, log_mess = ({}, "error cannot interpret %s" % (ret_str))
            diff_time = time.time() - key
            job.log(" - Got answer for ip %s after %s: %s" % (ip, logging_tools.get_diff_time_str(diff_time), log_mess))
            mon_dict[ip] = ret_dict
        if ip_dict:
            mon_dict["ip_dict"] = ip_dict
        # save dict
        f_name = "/tmp/.%s_%s" % (PROFILE_PREFIX, m_id)
        try:
            file(f_name, "w").write(server_command.sys_to_net(mon_dict))
        except:
            pass

def read_profiles(job):
    return (read_profile(job, "s"), read_profile(job, "p"))

def read_profile(job, pt):
    f_name = "/tmp/.%s_%s.%s" % (PROFILE_PREFIX, job.get_job_id(), pt)
    ret_dict = {}
    if os.path.isfile(f_name):
        try:
            ret_dict = server_command.net_to_sys(file(f_name, "r").read())
        except:
            job.log("error reading profile %s" % (f_name))
            ret_dict = {}
        else:
            try:
                os.unlink(f_name)
            except:
                job.log("error removing profile %s" % (f_name))
    else:
        job.log("no profile %s found" % (f_name))
    return ret_dict

def pretty_print(val, base):
    pf_idx = 0
    if base != 1:
        while val > base * 4:
            pf_idx += 1
            val = float(val) / base
    return val, ["", "k", "M", "G", "T", "E", "P"][pf_idx]

def prepare_output(vals):
    loc_f = []
    for v_t in ["min", "mean", "max"]:
        if vals.has_key("u"):
            act_v, p_str = pretty_print(vals[v_t] * vals["f"], vals["b"])
            unit = vals["u"]
        else:
            act_v, p_str = (vals[v_t], "")
            unit = "???"
        if type(act_v) in [types.IntType, types.LongType]:
            val = "%10d   " % (act_v)
        else:
            val = "%13.2f" % (act_v)
        vals["%s_str" % (v_t)] = ("%s %1s" % (val, p_str)).strip()
        vals["unit"] = unit
    
def get_local_net_dict():
    ndev_re = re.compile("^(?P<devname>\S+)\s+link encap.*$")
    ip_re = re.compile("^.*inet addr:(?P<ip>\S+)\s+.*$")
    n_dict = {}
    stat, out = commands.getstatusoutput("/sbin/ifconfig")
    if not stat:
        act_dev, act_ip = (None, None)
        for line in out.lower().split("\n"):
            ndev_m, ip_m = (ndev_re.match(line), ip_re.match(line))
            if ndev_m:
                act_dev = ndev_m.group("devname")
            if ip_m:
                act_ip = ip_m.group("ip")
            if act_dev and act_ip:
                n_dict[act_dev] = act_ip
                act_dev, act_ip = (None, None)
    return n_dict

def dump_profile(job, prof, pt):
    full_name = {"s" : "Serial (local)",
                 "p" : "Parallel"}[pt]
    if prof and type(prof) == type({}):
        m_info = g_config.get("MONITOR", "normal")
        if m_info not in ["normal", "detail"]:
            m_info = "normal"
        if pt == "s":
            m_info = "detail"
        mon_keys = [y for y in [x.strip() for x in g_config.get("MONITOR_KEYS", "").split(";")] if y]
        if not mon_keys:
            mon_keys = ["load"]
        prof_keys = prof.keys()
        if "ip_dict" in prof_keys:
            ip_dict, name_dict = (prof["ip_dict"], dict([(v, k) for k, v in prof["ip_dict"].iteritems()]))
            lu_keys = [name_dict[k] for k in prof_keys if k != "ip_dict"]
        else:
            ip_dict, name_dict = (dict([(x, x) for x in prof_keys]),
                                  dict([(x, x) for x in prof_keys]))
            lu_keys = prof_keys
        lu_keys.sort()
        # check for validity of profile data
        if [True for x in lu_keys if type(prof[ip_dict[x]]) != type({})]:
            job.log("*** profile_data has wrong format: %s" % (str(prof)), 1)
        else:
            name_len = max([len(x) for x in lu_keys])
            f_str = "%%-%ds (%%15s): %%s" % (name_len)
            # data dict, key dict
            d_dict, k_dict = ({}, {})
            # step 1: generate dictionaries, no output
            for ip in lu_keys:
                rk = ip_dict[ip]
                stuff = prof[rk].get("cache", {})
                d_dict[ip] = {}
                for key, value in stuff.iteritems():
                    value["mean"] = value["num"] and value["tot"] / value["num"] or 0
                    d_dict[ip][key] = value
                    k_dict.setdefault(key, []).append(rk)
                    prepare_output(value)
            gen_keys = sorted(k_dict.keys())
            # beautify keys
            b_keys = b_mon_keys()
            for k in gen_keys:
                b_keys.add_key(k)
            if g_config.has_key("MONITOR_FULL_KEY_LIST"):
                b_keys_list = logging_tools.form_list()
                b_keys_list.set_header_string(0, ["kp%d" % (x) for x in range(4)])
                for b_key_line in b_keys.get_list():
                    b_keys_list.add_line((b_key_line + ["", "", ""])[0:4])
            else:
                b_keys_list = b_keys.get_string()
            if not gen_keys:
                job.log("%s monitor data, no keys found" % (full_name), 1)
            else:
                job.write("")
                job.log("%s monitor data, display mode is %s%s:" % (full_name, m_info, pt == "p" and ", showing data for %s" % (logging_tools.get_plural("node", len((prof.get("ip_dict", {})).keys()))) or ""), 1)
                job.log("%s to display: %s" % (logging_tools.get_plural("key", len(mon_keys)), ", ".join(mon_keys)), 1)
                job.write("%s found:" % (logging_tools.get_plural("key", len(gen_keys))))
                job.write(str(b_keys_list))
                # step 2: transform network names to nfs / mpi (where possible)
                net_type_dict = {}
                if pt == "p":
                    loc_net_dict = get_local_net_dict()
                    for devname, ip in loc_net_dict.iteritems():
                        if ip in name_dict.keys():
                            net_type_dict[devname] = "%s(NFS)" % (devname)
                        elif devname == "lo":
                            net_type_dict[devname] = "lo"
                        else:
                            net_type_dict[devname] = "%s(MPI)" % (devname)
                # step 3: output
                if m_info == "normal":
                    gen_nodes = sorted(d_dict.keys())
                    for v_t in ["min", "mean", "max"]:
                        act_keys = [x for x in gen_keys if len([1 for y in mon_keys if x.startswith(y)])]
                        job.write("")
                        job.write("Monitored values for the %s values of %s:" % (v_t, logging_tools.get_plural("key", len(act_keys))))
                        out_f = logging_tools.form_list()
                        out_f.set_header_string(0, ["Key", "", "", ""] + gen_nodes + ["unit"])
                        for g_k in act_keys:
                            k_parts = [net_type_dict.get(p, p) for p in g_k.split(".")]
                            out_f.add_line((k_parts + [""] * 4)[0 : 4] +
                                           [d_dict[n].get(g_k, {"%s_str" % (v_t) : "---"})["%s_str" % (v_t)] for n in gen_nodes] +
                                           [([d_dict[n].get(g_k, {"unit" : "???"})["unit"] for n in gen_nodes] + ["???"])[0]])
                        job.write(str(out_f))
                elif m_info == "detail":
                    for ip in lu_keys:
                        rk = ip_dict[ip]
                        stuff = prof[rk].get("cache", {})
                        if stuff:
                            keys = sorted(stuff.keys())
                            act_keys = [x for x in keys if len([1 for y in mon_keys if x.startswith(y)])]
                            info_str = "%s found, showing %s" % (logging_tools.get_plural("key", len(keys)), logging_tools.get_plural("key", len(act_keys)))
                        else:
                            info_str = "no data from this node"
                        job.write("")
                        job.write(f_str % (ip, rk, info_str))
                        if stuff:
                            out_f = logging_tools.form_list()
                            out_f.set_header_string(0, ["Key", "", "", "", "count", "min", "mean", "max", "unit"])
                            #f_line = [("-", " ", 0), ("-", " ", 0), ("-", " ", 0), ("- ", " ", 0), ("", " ", 0), ("", " / ", 0), ("", " / ", 0), ("", " ", 0), ("-", "", 0)]
                            for key, value in [(x, stuff[x]) for x in act_keys]:
                                k_parts = [net_type_dict.get(p, p) for p in key.split(".")]
                                out_f.add_line((k_parts + [""] * 4)[0 : 4] + [value["num"]] + [value["%s_str" % (x)] for x in ["min", "mean", "max"]] + [value["unit"]])
                            job.write(str(out_f))
                else:
                    job.write("Unknown monitor mode '%s'" % (m_info))
                job.write("")
    else:
        if prof:
            job.log("wrong type for profile-data: %s" % (str(type(prof))))
        else:
            job.log("No %s monitor data" % (full_name), 1)

def send_startstop_tag(tag_name, send_queue, job, q_list):
    recv_queue = Queue.Queue(100)
    sge_cell = get_sge_cell()
    job.log(" - Sending tag '%s' to host %s, port %d (list %s)" % (tag_name, g_config["SGE_SERVER"], g_config["SGE_SERVER_PORT"], ",".join(q_list)))
    state, ret_str = net_tools.single_connection(host=g_config["SGE_SERVER"],
                                                 port=g_config["SGE_SERVER_PORT"],
                                                 command=server_command.server_command(command=tag_name,
                                                                                       option_dict={"host"       : job.get_local_host_name(),
                                                                                                    "full_host"  : job.get_full_host_name(),
                                                                                                    "origin"     : "proepilogue",
                                                                                                    "job_id"     : job.get_job_id(),
                                                                                                    "job_num"    : job.get_job_num(),
                                                                                                    "uid"        : job.get_uid(),
                                                                                                    "gid"        : job.get_gid(),
                                                                                                    "queue_name" : job.get_queue_name(),
                                                                                                    "job_name"   : job.get_job_name(),
                                                                                                    "queue_list" : q_list,
                                                                                                    "task_id"    : job.get_task_id(),
                                                                                                    "pe_name"    : job.get_pe_name()})).iterate()
    try:
        srv_reply = server_command.server_reply(ret_str)
    except:
        if ret_str.startswith("ok"):
            log_str = "Successfully sent tag %s to server %s (cell %s)" % (tag_name, g_config["SGE_SERVER"], sge_cell)
        else:
            log_str = "Some error occured while trying to sent tag %s to server %s:%d (cell %s): %s" % (tag_name, g_config["SGE_SERVER"], g_config["SGE_SERVER_PORT"], sge_cell, ret_str)
    else:
        ret_state, result = srv_reply.get_state_and_result()
        if ret_state:
            log_str = "Some error occured while trying to sent tag %s to server %s:%d (cell %s): %s (%d)" % (tag_name, g_config["SGE_SERVER"], g_config["SGE_SERVER_PORT"], sge_cell, result, ret_state)
        else:
            log_str = "Successfully sent tag %s to server %s (cell %s)" % (tag_name, g_config["SGE_SERVER"], sge_cell)
    job.log(log_str)
    return

def flight_check(f_type, send_queue, ip_dict, name_dict, ip_list, con_list, act_rms, job):
    def send_ping():
        pass
    recv_queue = Queue.Queue(100)
    sim_pings = g_config["SIMULTANEOUS_PINGS"]
    ret_val = 0
    job.log("Starting %s checks" % (f_type))
    job.log("Trying to connect to %s: %s" % (logging_tools.get_plural("host", len(con_list)), ", ".join(con_list)))
    num_send, send_dict, recv_dict = (0, {}, {})
    act_con_list = [x for x in con_list]
    fail_hosts_1, fail_hosts_2 = ([], [])
    job.log("IP-List (%s) is %s" % (logging_tools.get_plural("address", len(ip_list)),
                                    ", ".join(ip_list)))
    retry_list = []
    total_pings = 0
    host_retry_dict = dict([(x, 2) for x in act_con_list])
    command = "ping_remote fast_mode=True"
    num_to_recv = 0
    while act_con_list:
        act_num_to_recv, act_pings = (0, 0)
        pings_allowed_to_send = sim_pings
        while pings_allowed_to_send > 0 and act_con_list:
            ip = act_con_list.pop(0)
            check_ips = [x for x in ip_list if x != ip]
            if len(check_ips):
                host_retry_dict[ip] -= 1
                num_send += 1
                act_num_to_recv += 1
                long_arg_str = "%s %d %.2f" % (",".join(check_ips), g_config["PING_PACKETS"], g_config["PING_TIMEOUT"])
                short_arg_str = "<IP-List (except %s)> %d %.2f" % (ip, g_config["PING_PACKETS"], g_config["PING_TIMEOUT"])
                job.log(" - Sending '%s' to ip %s, port %d, command %s" % (short_arg_str, ip, g_config["COLLSERVER_PORT"], command))
                send_dict[ip] = check_ips
                send_queue.put(comsend_message((ip, g_config["COLLSERVER_PORT"], "%s %s" % (command, long_arg_str), recv_queue, time.time())))
                act_pings += len(check_ips)
                pings_allowed_to_send -= len(check_ips)
        job.log("initiated %s on %s" % (logging_tools.get_plural("ping", act_pings),
                                        logging_tools.get_plural("host", act_num_to_recv)))
        num_to_recv += act_num_to_recv
        while act_num_to_recv:
            act_num_to_recv -= 1
            key, ip, ret_str = recv_queue.get().arg
            host_failed = False
            if ret_str.startswith("ok"):
                log_mess = "ok (%d bytes of data, key %d)" % (len(ret_str) - 3, key)
                try:
                    res_raw = server_command.net_to_sys(ret_str[3:])
                except ValueError:
                    job.log("error decoding answer for key %d (ip %s): %s" % (key,
                                                                              ip,
                                                                              process_tools.get_except_info()))
                    host_failed = True
                else:
                    if type(res_raw) == type(()):
                        # old (pre net_tools) result
                        res_a, res_b = res_raw
                        if type(res_a) == type({}) and type(res_b) == type({}):
                            # new result version
                            ip_res_dict, ip_map = res_a, res_b
                        else:
                            # old result version
                            ip_map, ip_res_list = res_a, res_b
                    else:
                        # got dictionary
                        ip_map, ip_res_dict = (res_raw, None)
                    recv_dict[ip] = {ip : 1}
                    any_missing = 0
                    for d_ip in send_dict[ip]:
                        if type(ip_map) == type({}):
                            if ip_map.has_key(d_ip):
                                if type(ip_map[d_ip]) == type({}):
                                    num_sent, num_ok, loss = (ip_map[d_ip]["send"],
                                                              ip_map[d_ip]["received"],
                                                              ip_map[d_ip]["timeout"])
                                    if ip_map[d_ip].has_key("min_time"):
                                        min_time, mean_time, max_time = (ip_map[d_ip]["min_time"],
                                                                         ip_map[d_ip]["mean_time"],
                                                                         ip_map[d_ip]["max_time"])
                                    else:
                                        min_time, mean_time, max_time = (0., 0., 0.)
                                else:
                                    if len(ip_map[d_ip]) == 6:
                                        num_sent, num_ok, loss, min_time, mean_time, max_time = ip_map[d_ip]
                                    else:
                                        num_tot, num_sent, num_ok, loss, min_time, mean_time, max_time, duration = ip_map[d_ip]
                                if num_ok:
                                    recv_dict[ip][d_ip] = 1
                                else:
                                    recv_dict[ip][d_ip] = 0
                                    any_missing = 1
                            else:
                                job.log("missing ip in ip_map (key pair %s / %s), setting according recv_dict entry to -1" % (ip,
                                                                                                                              d_ip))
                                recv_dict[ip][d_ip] = -1
                        else:
                            job.log("wrong type for ip_map (%s): %s, (key pair %s / %s), setting according recv_dict entry to -1" % (str(type(ip_map)),
                                                                                                                                     str(ip_map),
                                                                                                                                     ip,
                                                                                                                                     d_ip))
                            recv_dict[ip][d_ip] = -1
                    if any_missing and ip not in retry_list:
                        retry_list.append(ip)
                        act_con_list.append(ip)
                        num_to_recv -= 1
            else:
                host_failed = True
            if host_failed and host_retry_dict[ip]:
                host_failed = False
                # reping
                job.log("retrying %s for ip %s" % (command, ip))
                check_ips = [x for x in ip_list if x != ip]
                host_retry_dict[ip] -= 1
                long_arg_str = "%s %d %f" % (",".join(check_ips), g_config["PING_PACKETS"], g_config["PING_TIMEOUT"])
                short_arg_str = "<IP-List (except %s)> %d %f" % (ip, g_config["PING_PACKETS"], g_config["PING_TIMEOUT"])
                job.log(" - Sending '%s' to ip %s, port %d, command %s" % (short_arg_str, ip, g_config["COLLSERVER_PORT"], command))
                send_dict[ip] = check_ips
                send_queue.put(comsend_message((ip, g_config["COLLSERVER_PORT"], "%s %s" % (command, long_arg_str), recv_queue, time.time())))
                act_num_to_recv += 1
                # for logging
                log_mess = ret_str
            if host_failed:
                # ok, this node is dead
                fail_hosts_1.append(name_dict[ip])
                num_to_recv -= 1
                log_mess = ret_str
                recv_dict[ip] = dict([(x, 0) for x in send_dict[ip] + [ip]])
                ret_val = 2
            diff_time = time.time() - key
            job.log(" - Got answer for ip %s (key %d) after %s: %s" % (ip, key, logging_tools.get_diff_time_str(diff_time), log_mess))
    retry_list.sort()
    if retry_list:
        job.log("Some problems were reported for %s (tried twice): %s" % (logging_tools.get_plural("IP", len(retry_list)),
                                                                          ", ".join(retry_list)), 1)
    t_avail_dict = dict([(x, 0) for x in ip_list])
    for s_ip in send_dict.keys():
        for d_ip in ip_list:
            t_avail_dict[d_ip] += recv_dict[s_ip][d_ip]
    # print connection matrix
    # check return values of all reachable collservers
    ip_lut_dict = dict([(v, k) for k, v in ip_dict.iteritems()])
    #print t_avail_dict, name_dict, ip_dict
    if t_avail_dict:
        if min(t_avail_dict.values()) < num_to_recv:
            min_fail = 99999
            job.log("Problem connecting to the following IP(s):", 1)
            for av_k in sorted(t_avail_dict.keys()):
                if t_avail_dict[av_k] < num_to_recv:
                    job.log("  %15s %-34s : %3d < %3d (from %s)" % (av_k, "(%s on %s)" % (ip_lut_dict.get(av_k, "unknown IF-name"),
                                                                                          name_dict.get(av_k, "unknown Node-name")),
                                                                    t_avail_dict[av_k],
                                                                    num_send,
                                                                    ", ".join([ip_lut_dict.get(x, x) for x in recv_dict.keys() if recv_dict[x].get(av_k, 1) == 0])), 1)
                    if t_avail_dict[av_k] < min_fail:
                        min_fail = t_avail_dict[av_k]
            fail_hosts_2.extend([name_dict[x] for x in t_avail_dict.keys() if t_avail_dict[x] == min_fail])
        elif num_to_recv == num_send:
            job.log("%s reachable" % (logging_tools.get_plural("IP-adress", len(ip_list))), 1)
        fail_hosts = fail_hosts_1 + [x for x in fail_hosts_2 if x not in fail_hosts_1]
        if len(fail_hosts):
            job.log("failed hosts: %s (%d)" % (", ".join(["%s [%s, %s]" % (x, ip_dict[x], ip_lut_dict.get(x, "unknown IF-name")) for x in fail_hosts]), len(fail_hosts)), 1)
            fail_nodes_str = " ".join(fail_hosts)
            if g_config.get("SGE_VERSION", "-") == "6":
                fail_queues_list = ["%s@%s" % (job.get_queue_name(), x) for x in fail_hosts]
            else:
                fail_queues_list = ["%s%s" % (x, g_config["QUEUE_POSTFIX"]) for x in fail_hosts]
            fail_queues_str = ",".join(fail_queues_list)
            sge_cell = get_sge_cell()
            command = "disable"
            job.log(" - Sending '%s' to host %s, port %d, command %s" % (fail_queues_str, g_config["SGE_SERVER"], g_config["SGE_SERVER_PORT"], command))
            state, ret_str = net_tools.single_connection(host=g_config["SGE_SERVER"],
                                                         port=g_config["SGE_SERVER_PORT"],
                                                         command=server_command.server_command(command=command,
                                                                                               option_dict={"host"         : job.get_local_host_name(),
                                                                                                            "full_host"    : job.get_full_host_name(),
                                                                                                            "origin"       : "proepilogue",
                                                                                                            "job_id"       : job.get_job_id(),
                                                                                                            "job_num"      : job.get_job_num(),
                                                                                                            "uid"          : job.get_uid(),
                                                                                                            "gid"          : job.get_gid(),
                                                                                                            "queue_name"   : job.get_queue_name(),
                                                                                                            "job_name"     : job.get_job_name(),
                                                                                                            "fail_objects" : fail_queues_list,
                                                                                                            "error"        : "connection problems",
                                                                                                            "task_id"      : job.get_task_id()})).iterate()
            if return_struct_is_valid(ret_str):
                log_str = "Successfully disabled the queues %s for cell %s on server %s" % (fail_queues_str, sge_cell, g_config["SGE_SERVER"])
            else:
                log_str = "Some error occured while trying to disable the queues %s for cell %s on server %s: %s" % (fail_queues_str, sge_cell, g_config["SGE_SERVER"], ret_str)
            job.write(log_str)
            command = "hold"
            job.log(" - Sending '%s' to host %s, port %d, command %s" % (job.get_job_id(), g_config["SGE_SERVER"], g_config["SGE_SERVER_PORT"], command))
            
            state, ret_str = net_tools.single_connection(host=g_config["SGE_SERVER"],
                                                         port=g_config["SGE_SERVER_PORT"],
                                                         command=server_command.server_command(command=command,
                                                                                               option_dict={"host"         : job.get_local_host_name(),
                                                                                                            "full_host"    : job.get_full_host_name(),
                                                                                                            "origin"       : "proepilogue",
                                                                                                            "job_id"       : job.get_job_id(),
                                                                                                            "job_num"      : job.get_job_num(),
                                                                                                            "uid"          : job.get_uid(),
                                                                                                            "gid"          : job.get_gid(),
                                                                                                            "queue_name"   : job.get_queue_name(),
                                                                                                            "job_name"     : job.get_job_name(),
                                                                                                            "fail_objects" : [job.get_job_id()],
                                                                                                            "error"        : "connection problems",
                                                                                                            "task_id"      : job.get_task_id()})).iterate()
            if return_struct_is_valid(ret_str):
                log_str = "Successfully set an operator hold on job %s for cell %s on server %s" % (job.get_job_id(), sge_cell, g_config["SGE_SERVER"])
            else:
                log_str = "Some error occured while trying to set an operator hold on job %s for cell %s on server %s: %s" % (job.get_job_id(), sge_cell, g_config["SGE_SERVER"], ret_str)
            job.write(log_str)
            job.log(log_str, 1)
            ret_val = 2
    else:
        job.log("Empty availability dictionary (all collservers dead?)", 1)
    if ret_val and g_config.get("AVAILABILITY_MATRIX", 0):
        job.write("Availability matrix")
        out_a = ["%15s" % (" ")]
        for d_key in ip_list:
            out_a.append("%15s (%2d)" % (d_key, t_avail_dict[d_key]))
        job.write("|".join(out_a))
        for s_key in sorted(recv_dict.keys()):
            out_a = ["%15s" % (s_key)]
            for d_key in ip_list:
                out_a.append((recv_dict[s_key][d_key] and "ok" or "ERROR").center(20))
            job.write("|".join(out_a))
    return ret_val

def return_struct_is_valid(in_str):
    try:
        srv_reply = server_command.server_reply(in_str)
    except:
        return False
    else:
        return srv_reply.state == server_command.SRV_REPLY_STATE_OK and True or False
    
def remove_dir(job, d_root):
    num_rem = 0
    try:
        shutil.rmtree("%s" % (d_root))
        num_rem += 1
    except:
        log_str = "Error removing all entries in work_dir %s (%s)" % (d_root, process_tools.get_except_info())
    else:
        if num_rem:
            log_str = "Removed all %d pending entries in work_dir %s" % (num_rem, d_root)
        else:
            log_str = "work_dir %s was already clean" % (d_root)
    job.log(log_str)

def call_ext_command(job, form_str, com_names, retries=1):
    ret_val, err_field = (1, [])
    path_field = []
    for com_name in com_names:
        com = form_str % com_name
        compath_found = ""
        if com.startswith("/"):
            path_field = ["/"]
            if os.path.exists(com_name):
                compath_found = com_name
        else:
            for path in sorted(dict([(x.strip(), 0) for x in os.environ.get("PATH", "").split(":") + g_config["EXTRA_PATH"].split(":") if x.startswith("/")]).keys()):
                compath_found = "%s/%s" % (path, com_name)
                path_field.append(path)
                if os.path.exists(compath_found):
                    break
            else:
                compath_found = ""
        if compath_found:
            job.log("starting command '%s' (full path of executable %s is %s), %s" % (com, com_name, compath_found, logging_tools.get_plural("retry", retries)), 1)
            for idx in range(retries):
                out_file = "/tmp/.output_%s" % (job.get_job_id())
                err_file = "/tmp/.error_%s" % (job.get_job_id())
                ret_val = os.system("%s > %s 2>%s" % (com, out_file, err_file))
                out_lines = [x.rstrip() for x in file(out_file, "r").read().split("\n") if len(x.strip())]
                err_lines = [x.rstrip() for x in file(err_file, "r").read().split("\n") if len(x.strip())]
                out_log_name = "extcom_%d_%s" % (idx + 1, com.replace("/", "_").replace(" ", "_").replace("__", "_").replace("__", "_"))
                job.log("Saving output (%s)/errors (%s) [return value %d] to %s.(e|o)" % (logging_tools.get_plural("line", len(err_lines)),
                                                                                          logging_tools.get_plural("line", len(out_lines)),
                                                                                          ret_val,
                                                                                          out_log_name))
                if ret_val:
                    job.log("calling %s (retry %d of %d) returned an error: %d" % (com, idx + 1, retries, ret_val), 1)
                    err_field.append("error during %s (%d)" % (com, ret_val))
                    ret_val = 1
                else:
                    job.log("calling %s (retry %d of %d) successful" % (com, idx + 1, retries), 1)
                for p_fix, what, f_pfix in [("-", out_lines, "o"),
                                            ("*", err_lines, "e")]:
                    line_num = 0
                    for line in what:
                        line_num += 1
                        job.log(" %s %4d : %s" % (p_fix, line_num, line), 0, "%s.%s" % (out_log_name, f_pfix))
                try:
                    os.unlink(out_file)
                    os.unlink(err_file)
                except:
                    pass
                if out_lines:
                    job.write("Standard output (iteration %d, %s):" % (idx + 1,
                                                                       logging_tools.get_plural("line", len(out_lines))))
                    for out_line in out_lines:
                        job.write(" . %s" % (out_line))
                if err_lines:
                    job.write("Error output (iteration %d, %s):" % (idx + 1,
                                                                    logging_tools.get_plural("line", len(err_lines))))
                    for err_line in err_lines:
                        job.write(" * %s" % (err_line))
                if not ret_val:
                    break
        else:
            job.log("No executable for '%s' (command %s) found, searched in %s:" % (com,
                                                                                    com_name,
                                                                                    logging_tools.get_plural("path", len(path_field))), 1)
            for path in path_field:
                job.log(" - %s" % (path), 1)
            err_field.append("executable for %s (%s) not found" % (com_name, com))
        if not ret_val:
            break
    if not err_field:
        err_field = ["ok"]
    return ret_val, com_name, ", ".join(err_field)
            
def modify_hostfile(send_queue, act_rms, job):
    recv_queue = Queue.Queue(100)
    job.write_run_info(job)
    sge_cell = get_sge_cell()
    nf_ok, node_list, mpi_node_list, ip_dict, name_dict, ip_list, con_list = get_node_list(job)
    if act_rms.get_exec_mode() in ["ls", "ps", "vs", "mvs"] and len(mpi_node_list):
        if act_rms.get_exec_mode() in ["mvs"]:
            job.init_mvapich2_node_list(mpi_node_list)
        else:
            write_node_list(mpi_node_list, job)
    else:
        write_node_list(node_list, job)
    #time.sleep(200)
    # send start/stop messages to server
    if act_rms.get_exec_mode() in ["ls", "ps", "vs", "mvs"]:
        tag_name = "pe_start"
        if g_config.get("MONITOR", "normal") != "none":
            start_monitor_threads(send_queue, con_list, job, "%s.p" % (job.get_job_id()))
        # show nfs/mpi node_list
        job.show_node_lists(node_list, mpi_node_list)
        kill_running_lam_daemons(send_queue, con_list, job)
        kill_foreign_pids(send_queue, con_list, job)
        remove_foreign_ipcs(send_queue, con_list, job)
        umount_nfs_mounts(send_queue, con_list, job)
    elif act_rms.get_exec_mode() in ["le", "pe", "ve"]:
        tag_name = "pe_stop"
        if g_config.get("MONITOR", "normal") != "none":
            collect_monitor_threads(send_queue, con_list, job, "%s.p" % (job.get_job_id()), ip_dict, node_list, mpi_node_list)
            stop_monitor_threads(send_queue, con_list, job, "%s.p" % (job.get_job_id()))
    else:
        tag_name = "unknown"
        kill_running_lam_daemons(send_queue, con_list, job)
        kill_foreign_pids(send_queue, con_list, job)
        remove_foreign_ipcs(send_queue, con_list, job)
    send_startstop_tag(tag_name, send_queue, job, node_list)
    if nf_ok:
        ret_val = flight_check("preflight", send_queue, ip_dict, name_dict, ip_list, con_list, act_rms, job)
    else:
        ret_val = 0
        job.log("Skipping postflight checks, exiting with %d" % (ret_val), 1)
    if ret_val == 0 and act_rms.get_exec_mode() in ["ls", "le", "vs", "ve", "mvs", "mve"]:
        if act_rms.get_exec_mode() == "ls":
            com = "lamboot"
            job.log("trying to start LAM via '%s', %s ..." % (com, logging_tools.get_plural("retry", g_config["LAM_START_RETRIES"])), 1)
            ret_val, act_com, err_str = call_ext_command(job, "%%s -v %s" % (job.get_node_list_name()), [com], g_config["LAM_START_RETRIES"])
        elif act_rms.get_exec_mode() == "le":
            com = ["lamwipe", "wipe"]
            job.log("trying to stop LAM via %s, %s ..." % (" OR ".join(["'%s'" % (x) for x in com]), logging_tools.get_plural("retry", g_config["LAM_STOP_RETRIES"])), 1)
            ret_val, act_com, err_str = call_ext_command(job, "%%s -v %s" % (job.get_node_list_name()), com, g_config["LAM_STOP_RETRIES"])
        elif act_rms.get_exec_mode() == "vs":
            com = "pvmstart"
            job.log("trying to start PVM via '%s', %s ..." % (com, logging_tools.get_plural("retry", 1)), 1)
            ret_val, act_com, err_str = call_ext_command(job, "echo 'halt' | %s", ["pvm"])
            ret_val, act_com, err_str = call_ext_command(job, "echo 'conf' | %%s -n%s %s" % (file(job.get_node_list_name(), "r").read().split("\n")[0].split()[0].strip(), job.get_node_list_name()), ["pvm"])
        elif act_rms.get_exec_mode() == "ve":
            com = "pvmstop"
            job.log("trying to stop PVM via '%s', %s ..." % (com, logging_tools.get_plural("retry", 1)), 1)
            ret_val, act_com, err_str = call_ext_command(job, "echo 'halt' | %s", ["pvm"])
        elif act_rms.get_exec_mode() == "mvs":
            com = "mpdboot"
            job.log("trying to start MVAPICH2 via '%s', %s ..." % (com, logging_tools.get_plural("retry", g_config["LAM_START_RETRIES"])), 1)
            ret_val, act_com, err_str = call_ext_command(job, "%%s -f %s --ncpus=%d --ifhn=%s -n %s -r rsh" % (job.get_node_list_name(),
                                                                                                               job.first_node_cpu_count,
                                                                                                               job.first_node,
                                                                                                               job.node_count), [com], g_config["LAM_START_RETRIES"])
        elif act_rms.get_exec_mode() == "mve":
            com = "mpdallexit"
            job.log("trying to stop MVAPICH2 via '%s', %s ..." % (com, logging_tools.get_plural("retry", g_config["LAM_STOP_RETRIES"])), 1)
            ret_val, act_com, err_str = call_ext_command(job, "%s", [com], g_config["LAM_STOP_RETRIES"])
        if ret_val:
            command = "hold"
            job.log(" - Sending '%s' to host %s, port %d, command %s" % (job.get_job_id(), g_config["SGE_SERVER"], g_config["SGE_SERVER_PORT"], command))
            state, ret_str = net_tools.single_connection(host=g_config["SGE_SERVER"],
                                                         port=g_config["SGE_SERVER_PORT"],
                                                         command=server_command.server_command(command=command,
                                                                                               option_dict={"host"         : job.get_local_host_name(),
                                                                                                            "full_host"    : job.get_full_host_name(),
                                                                                                            "origin"       : "proepilogue",
                                                                                                            "job_id"       : job.get_job_id(),
                                                                                                            "job_num"      : job.get_job_num(),
                                                                                                            "uid"          : job.get_uid(),
                                                                                                            "gid"          : job.get_gid(),
                                                                                                            "queue_name"   : job.get_queue_name(),
                                                                                                            "job_name"     : job.get_job_name(),
                                                                                                            "error"        : err_str,
                                                                                                            "fail_objects" : [job.get_job_id()],
                                                                                                            "node_list"    : node_list,
                                                                                                            "task_id"      : job.get_task_id()})).iterate()
            if return_struct_is_valid(ret_str):
                log_str = "Successfully set an operator hold on job %s for cell %s on server %s" % (job.get_job_id(), sge_cell, g_config["SGE_SERVER"])
            else:
                log_str = "Some error occured while trying to set an operator hold on job %s for cell %s on server %s: %s" % (job.get_job_id(), sge_cell, g_config["SGE_SERVER"], ret_str)
            job.log(log_str)
            job.write(log_str)
    if tag_name == "pe_stop":
        kill_running_lam_daemons(send_queue, con_list, job)
        kill_foreign_pids(send_queue, con_list, job)
        remove_foreign_ipcs(send_queue, con_list, job)
        umount_nfs_mounts(send_queue, con_list, job)
    if act_rms.get_exec_mode() in ["le", "pe", "ve", "mve"]:
        delete_node_list(job)
    return ret_val

def prologue(send_queue, act_rms, job):
    job.write_run_info(job)
    send_startstop_tag("job_start", send_queue, job, [job.get_local_host_name()])
    kill_running_lam_daemons(send_queue, [LOCAL_IP], job)
    kill_foreign_pids(send_queue, [LOCAL_IP], job)
    remove_foreign_ipcs(send_queue, [LOCAL_IP], job)
    umount_nfs_mounts(send_queue, [LOCAL_IP], job)
    if g_config.get("MONITOR", "normal") != "none":
        start_monitor_threads(send_queue, [LOCAL_IP], job, "%s.s" % (job.get_job_id()))
    ret_val = 0
    return ret_val

def epilogue(send_queue, act_rms, job, res_used, act_env):
    if res_used:
        job.write("Resources used:")
        log_res = []
        out_list = logging_tools.form_list()
        out_list.set_header_string(0, ["key", "value", "description"])
        #f_str = "%%%ds : %%s%%s" % (max([len(x) for x in res_used.keys()]))
        for key, value in [(key, res_used[key]) for key in sorted(res_used.keys())]:
            ext_str = ""
            if key == "exit_status":
                try:
                    i_val = int(value)
                except:
                    pass
                else:
                    ext_str = {0   : "no failure",
                               1   : "error before job",
                               2   : "before writing config",
                               3   : "before writing pid",
                               4   : "before writing pid",
                               5   : "reading config file",
                               6   : "setting processor set",
                               7   : "before prolog",
                               8   : "in prolog",
                               9   : "before pestart",
                               10  : "in pestart",
                               11  : "before job",
                               12  : "before pestop",
                               13  : "in pestop",
                               14  : "before epilogue",
                               15  : "in epilog",
                               16  : "releasing processor set",
                               24  : "migrating",
                               25  : "rescheduling",
                               26  : "opening output file",
                               27  : "searching requested shell",
                               28  : "changing to working directory",
                               100 : "assumedly after job"}.get(i_val, "")
                    ext_str = ext_str and " (%s)" % (ext_str) or ""
            out_list.add_line((key, value, ext_str))
            log_res.append("%s:%s%s" % (key, value, ext_str))
        job.write("\n".join(["  %s" % (x) for x in str(out_list).split("\n")]))
        job.log("reported %d resources: %s" % (len(log_res), ", ".join(log_res)))
    else:
        job.log("No resources found", 1)
    send_startstop_tag("job_stop", send_queue, job, [job.get_local_host_name()])
    kill_running_lam_daemons(send_queue, [LOCAL_IP], job)
    kill_foreign_pids(send_queue, [LOCAL_IP], job)
    remove_foreign_ipcs(send_queue, [LOCAL_IP], job)
    umount_nfs_mounts(send_queue, [LOCAL_IP], job)
    if g_config.get("MONITOR", "normal") != "none":
        collect_monitor_threads(send_queue, [LOCAL_IP], job, "%s.s" % (job.get_job_id()), {})
        stop_monitor_threads(send_queue, [LOCAL_IP], job, "%s.s" % (job.get_job_id()))
    ret_val = 0
    # check for job-profiling
    if g_config["MONITOR_JOBS"] and g_config.get("MONITOR", "normal") != "none":
        ser_dict, par_dict = read_profiles(job)
        dump_profile(job, ser_dict, "s")
        dump_profile(job, par_dict, "p")
    # send SIGKILL to all scripts with stdout/stderr in fd-table
    kill_stdout_stderr_childs(job, act_env)
    # iterate over scripts in epilogue.d directory
    call_scripts_in_dir(job, "%s/3rd_party/epilogue.d" % (g_config["SGE_ROOT"]))
    return ret_val

def kill_stdout_stderr_childs(job, act_env):
    sge_stdout_path = act_env["SGE_STDOUT_PATH"]
    sge_stderr_path = act_env["SGE_STDERR_PATH"]
    pid_dict = process_tools.get_proc_list()
    # build list of pids up to the init-process (pid 1)
    act_pid = os.getpid()
    my_exe_path = os.readlink("/proc/%d/exe" % (act_pid))
    job.log("sge_stdout_path: %s" % (sge_stdout_path))
    job.log("sge_stderr_path: %s" % (sge_stderr_path))
    job.log("my_exe_path: %s" % (my_exe_path))
    my_pid_list = [act_pid]
    while act_pid != 1:
        act_pid = pid_dict[act_pid]["ppid"]
        my_pid_list.append(act_pid)
    kill_pids = []
    check_paths = [x for x in [sge_stdout_path, sge_stderr_path] if x not in ["/dev/null"]]
    p_dir = "/proc"
    for p_id in os.listdir(p_dir):
        if p_id.isdigit():
            i_p_id = int(p_id)
            full_path = "%s/%s" % (p_dir, p_id)
            cwd_file = "%s/cwd" % (full_path)
            try:
                exe_path = os.readlink("%s/exe" % (full_path))
            except:
                exe_path = ""
            if exe_path != my_exe_path:
                try:
                    cwd_path = os.readlink(cwd_file)
                except:
                    pass
                else:
                    fd_dir = "%s/fd" % (full_path)
                    if os.path.isdir(fd_dir):
                        for fd_num in os.listdir(fd_dir):
                            try:
                                fd_path = "%s/%s" % (fd_dir, fd_num)
                                if os.path.islink(fd_path):
                                    link_target = os.readlink(fd_path)
                                    if link_target in check_paths:
                                        if i_p_id not in my_pid_list and i_p_id not in kill_pids:
                                            kill_pids.append(i_p_id)
                                        #print "+++", p_id, fd_path, link_target
                            except:
                                print "EXC:", process_tools.get_except_info()
    if kill_pids:
        job.log("trying to kill %s: %s" % (logging_tools.get_plural("pid", len(kill_pids)),
                                           ", ".join(["%d" % (x) for x in kill_pids])))
        for kill_pid in kill_pids:
            try:
                exe_path = os.readlink("/proc/%d/exe" % (kill_pid))
            except:
                exe_path = "<not readable>"
            job.log("trying to kill pid %d (exe_path %s)" % (kill_pid, exe_path))
            try:
                os.kill(kill_pid, 15)
            except:
                pass
        print "waiting for 10 seconds for %s to terminate ..." % (logging_tools.get_plural("task", len(kill_pids)))
        for w_idx in xrange(10):
            time.sleep(1)
            still_present_pids = []
            for kill_pid in kill_pids:
                if os.path.isdir("/proc/%d" % (kill_pid)):
                    still_present_pids.append(kill_pid)
            kill_pids = still_present_pids
            if not kill_pids:
                break
        if kill_pids:
            print "killing remaing %s ..." % (logging_tools.get_plural("task", len(kill_pids)))
            for kill_pid in kill_pids:
                try:
                    os.kill(kill_pid, 9)
                except:
                    pass
    
def call_scripts_in_dir(job, s_dir):
    if os.path.isdir(s_dir):
        job.log("Executing scripts in directory %s" % (s_dir))
        for ent in os.listdir(s_dir):
            full_path = "%s/%s" % (s_dir, ent)
            stat, out = commands.getstatusoutput(full_path)
            job.log("calling %s gave (%d): %s" % (full_path, stat, out))
    else:
        job.log("No script-directory %s found" % (s_dir))
    
def parse_script_variables(scr_name, log_queue, act_job):
    try:
        lines = [x.strip() for x in file(scr_name, "r").read().split("\n")]
    except:
        act_job.log("Cannot read Scriptfile '%s' (%s)" % (scr_name, process_tools.get_except_info()))
    else:
        if act_job.get_rms().get_exec_mode() == "p":
            s_name = "job_script"
            act_job.log("Saving job_script into %s" % (s_name))
        else:
            s_name = None
        num_lines, num_sge, num_init, line_num = (len(lines), 0, 0, 0)
        init_dict = {}
        for line in lines:
            line_num += 1
            if s_name:
                act_job.log("%4d : %s" % (line_num, line), 0, s_name)
            if line.startswith("#$ "):
                num_sge += 1
            elif line.startswith("#init "):
                # valid init-keys:
                # MONITOR=<type>
                # MONITOR_KEYS=<key_list;>
                # MONITOR_FULL_KEY_LIST=<true>
                # TRIGGER_ERROR (flag, triggers error)
                # EXTRA_WAIT=x (waits for x seconds)
                num_init += 1
                line_parts = [x.split("=", 1) for x in line[5:].strip().split(",")]
                act_job.log("found #init-line '%s'" % (line))
                if line_parts:
                    for key, value in [x for x in line_parts if len(x) == 2]:
                        key, value = (key.strip().upper(), value.strip().lower())
                        if key and value:
                            init_dict[key] = value
                            act_job.log("recognised init option '%s' (value '%s')" % (key, value))
                            g_config.add_config_dict({key : configfile.str_c_var(value, source="jobscript")})
                    for key in [x[0].strip().upper() for x in line_parts if len(x) == 1]:
                        init_dict[key] = True
                        act_job.log("recognised init option '%s' (value '%s')" % (key, True))
                        g_config.add_config_dict({key : configfile.bool_c_var(True, source="jobscript")})
        act_job.log("Scriptfile '%s' has %d lines (%d SGE-related lines and %d init.at-related lines)" % (scr_name, num_lines, num_sge, num_init))

def get_mode(start_name, args, num_args):
    # exec mode is p[prologue], e[epilogue], ls[lamstart], le[lamend], ps[parallelstart] or pe[parallelend]
    em_dict = {"lamstart"      : "ls",
               "lamstop"       : "le",
               "pestart"       : "ps",
               "pestop"        : "pe",
               "pvmstart"      : "vs",
               "pvmstop"       : "ve",
               "mvapich2start" : "mvs",
               "mvapich2stop"  : "mve"}
    batch_sys, exec_mode, act_rms = ("s", None, None)
    if num_args == 8:
        if em_dict.has_key(start_name):
            exec_mode = em_dict[start_name]
        else:
            exec_mode = "e"
    elif num_args == 5:
        if start_name == "prologue":
            exec_mode = "p"
        else:
            exec_mode = "e"
    if batch_sys:
        act_rms = rms(batch_sys, exec_mode)
    return act_rms

def get_task_id(log_queue):
    if os.environ.has_key("SGE_TASK_FIRST") and os.environ.has_key("SGE_TASK_LAST") and os.environ.has_key("SGE_TASK_ID") and os.environ.has_key("SGE_TASK_STEPSIZE"):
        try:
            t_id = int(os.environ["SGE_TASK_ID"])
        except:
            log_queue.put(log_message("error extracting SGE_TASK_ID"))
            t_id = None
        else:
            pass
    else:
        t_id = None
    return t_id

def get_pe_name():
    if os.environ.has_key("PE") and os.environ.has_key("PE_HOSTFILE"):
        pe_name = os.environ["PE"]
    else:
        pe_name = None
    return pe_name
    
def get_environment():
    return dict([(k, str(os.environ[k])) for k in os.environ.keys()])

def log_environment(act_job, act_env):
    f_name = "env_%s" % (act_job.get_rms().get_exec_mode_long())
    env_list = logging_tools.form_list()
    all_k = sorted(act_env.keys())
    act_job.log("%d environment variables defined, logging to %s" % (len(all_k),
                                                                     f_name))
    for k in all_k:
        env_list.add_line((k, act_env[k]))
    act_job.log(str(env_list).split("\n"), 0, f_name)
        
def log_resources(act_job):
    f_name = "res_%s" % (act_job.get_rms().get_exec_mode_long())
    act_resources = read_resources()
    res_keys = sorted(act_resources.keys())
    act_job.log("%s defined, logging to %s" % (logging_tools.get_plural("limit", len(res_keys)),
                                               f_name))
    res_list = logging_tools.form_list()
    for key in res_keys:
        val = act_resources[key]
        if type(val) == type(""):
            info_str = val
        elif type(val) == type(()):
            info_str = "%8d (hard), %8d (soft)" % val
        else:
            info_str = "None (error?)"
        res_list.add_line((key, info_str))
    act_job.log(str(res_list).split("\n"), 0, f_name)
        
def set_sge_environment():
    log_lines = []
    for v_name, v_src in [("SGE_ROOT", "/etc/sge_root"), ("SGE_CELL", "/etc/sge_cell")]:
        if os.path.isfile(v_src):
            v_val = file(v_src, "r").read().strip()
            log_lines.append("Setting environment-variable '%s' to %s" % (v_name, v_val))
        else:
            log_lines.append("error: Cannot assign environment-variable '%s', exiting..." % (v_name))
            #sys.exit(1)
        g_config.add_config_dict({v_name : configfile.str_c_var(v_val, source=v_src)})
    if g_config.has_key("SGE_ROOT") and g_config.has_key("SGE_CELL"):
        if os.path.isfile("/%s/%s/common/product_mode" % (g_config["SGE_ROOT"], g_config["SGE_CELL"])):
            g_config.add_config_dict({"SGE_VERSION" : configfile.str_c_var("5", source="intern")})
        else:
            g_config.add_config_dict({"SGE_VERSION" : configfile.str_c_var("6", source="intern")})
    return log_lines

def read_resources():
    r_dict = {}
    try:
        import resource
    except ImportError:
        pass
    available_resources = [x for x in dir(resource) if x.startswith("RLIMIT")]
    for av_r in available_resources:
        try:
            r_dict[av_r] = resource.getrlimit(getattr(resource, av_r))
        except ValueError:
            r_dict[av_r] = "invalid resource"
        except:
            r_dict[av_r] = None
    return r_dict

def main():
    msi_block = None
    kill_signal = 9
    if os.path.isfile("/tmp/.sge_debug"):
        r_v = main_2()
    else:
        try:
            r_v = main_2()
        except:
            r_v = 2
            tb = sys.exc_info()[2]
            exc_info = sys.exc_info()
            logging_tools.my_syslog("error processing main_2 (proepilogue), %s (%s), setting return value to %d" % (str(exc_info[0]),
                                                                                                                    str(exc_info[1]),
                                                                                                                    r_v))
            logging_tools.my_syslog("  - %s: %s" % (logging_tools.get_plural("argument", len(sys.argv)),
                                                    " ".join(sys.argv)), 10, 1)
            err_lines = ["Error: %s" % (process_tools.get_except_info())]
            for file_name, line_no, name, line in traceback.extract_tb(tb):
                err_lines.append("File '%s', line %d, in %s" % (file_name, line_no, name))
                if line:
                    err_lines.append(" - %d : %s" % (line_no, line))
            for err_line in err_lines:
                logging_tools.my_syslog(err_line, 10, 1)
            err_h = process_tools.io_stream("/var/lib/logging-server/py_err")
            err_h.write("\n".join(err_lines))
            err_h.close()
            # read msi_block
            if msi_block:
                kill_pids = sorted(dict([(k, 0) for k in [x for x in msi_block.get_pids() if x != os.getpid()]]).keys())
                if kill_pids:
                    logging_tools.my_syslog("sending %d to %s: %s" % (kill_signal,
                                                                      logging_tools.get_plural("pid", len(kill_pids)), ", ".join(["%d" % (x) for x in kill_pids])))
                    for kill_pid in kill_pids:
                        os.kill(kill_pid, kill_signal)
                else:
                    logging_tools.my_syslog("no pids to kill, killing myself (%d) ..." % (os.getpid()))
                    os.kill(os.getpid(), kill_signal)
            else:
                logging_tools.my_syslog("no msi_block found")
        else:
            pass
    return r_v


# --connection objects-------------------------------------
class simple_tcp_obj(net_tools.buffer_object):
    # connects to a foreign host-monitor
    def __init__(self, d_queue, (send_id, res_type, send_str)):
        self.__d_queue = d_queue
        self.__send_str = send_str
        self.__res_type = res_type
        self.__send_id = send_id
        net_tools.buffer_object.__init__(self)
    def setup_done(self):
        self.add_to_out_buffer(net_tools.add_proto_1_header(self.__send_str, True))
    def out_buffer_sent(self, send_len):
        if send_len == len(self.out_buffer):
            self.out_buffer = ""
            self.socket.send_done()
        else:
            self.out_buffer = self.out_buffer[send_len:]
    def add_to_in_buffer(self, what):
        self.in_buffer += what
        p1_ok, p1_data = net_tools.check_for_proto_1_header(self.in_buffer)
        if p1_ok:
            self.__d_queue.put(("result_ok", (self.__send_id, self.__res_type, p1_data)))
            self.delete()
    def report_problem(self, flag, what):
        self.__d_queue.put(("result_error", (self.__send_id, flag, what)))
        self.delete()
# ----------------------------------------------------

class job_thread(threading_tools.thread_obj):
    def __init__(self, glob_config, opt_dict, net_server):
        self.__glob_config = glob_config
        self.__opt_dict = opt_dict
        self.__net_server = net_server
        self._init_log_template()
        threading_tools.thread_obj.__init__(self, "job", loop_function=self._loop)
        self._init_exit_code()
        self.register_func("result_ok", self._result_ok)
        self.register_func("result_error", self._result_error)
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK, **args):
        if self.__logger:
            self.__logger.log(log_level, what)
        else:
            self.__log_template.log(what, log_level)
        if args.get("do_print", False):
            self._print("%s%s" % ("[%s] " % (logging_tools.get_log_level_str(log_level)) if log_level != logging_tools.LOG_LEVEL_OK else "", what))
        if log_level != logging_tools.LOG_LEVEL_OK:
            self.send_pool_message(("log", (what, log_level)))
    def _print(self, what):
        try:
            print what
        except:
            self.log("cannot print '%s': %s" % (what,
                                                process_tools.get_except_info()),
                     logging_tools.LOG_LEVEL_ERROR)
    def _init_log_template(self):
        self.__log_dir = time.strftime("%Y/%m/%d/%%s%%s") % (self.__opt_dict["JOB_ID"],
                                                             ".%s" % (os.environ["SGE_TASK_ID"]) if os.environ.has_key("SGE_TASK_ID") else "")
        self.__log_name = "%s/log" % (self.__log_dir)
        logger, log_template = (None, None)
        try:
            logger = logging_tools.get_logger("%s.%s" % (self.__glob_config["LOG_NAME"],
                                                         self.__log_name.replace(".", "\.")),
                                              self.__glob_config["LOG_DESTINATION"],
                                              init_logger=True)
        except:
            log_template = net_logging_tools.log_command("%s.d" % (self.__glob_config["LOG_NAME"]), thread_safe=True, thread="job")
            log_template.set_destination(self.__glob_config["LOG_DESTINATION"])
            log_template.set_sub_names(self.__log_name)
            log_template.set_command_and_send("open_log")
            log_template.set_command("log")
        self.__log_template = log_template
        self.__logger = logger
    def _log_arguments(self):
        out_list = logging_tools.new_form_list()
        for key in sorted(self.__opt_dict.keys()):
            out_list.append([logging_tools.form_entry(key, header="key"),
                             logging_tools.form_entry(str(type(self.__opt_dict[key])), header="type"),
                             logging_tools.form_entry(self.__opt_dict[key], header="value")])
        for line in str(out_list).split("\n"):
            self.log(line)
    def _read_config(self):
        if self.__glob_config.has_key("CONFIG_FILE"):
            sections = ["queue_%s" % (self.__opt_dict["QUEUE"]),
                        "node_%s" % (self.__opt_dict["HOST_SHORT"])]
            if self.is_pe_call():
                sections.append("pe_%s" % (self.__opt_dict["PE"]))
                sections.append("queue_%s_pe_%s" % (self.__opt_dict["QUEUE"],
                                                self.__opt_dict["PE"]))
            self.log("scanning configfile %s for %s: %s" % (self.__glob_config["CONFIG_FILE"],
                                                            logging_tools.get_plural("section", len(sections)),
                                                            ", ".join(sections)))
            for section in sections:
                try:
                    self.__glob_config.parse_file(self.__glob_config["CONFIG_FILE"],
                                                  section=section)
                except:
                    self.log("error scanning for section %s: %s" % (section,
                                                                    process_tools.get_except_info()),
                             logging_tools.LOG_LEVEL_ERROR)
            try:
                for line, log_level in self.__glob_config.get_log(clear=True):
                    self.log(line, log_level)
            except:
                self.log("error getting config_log: %s" % (process_tools.get_except_info()),
                         logging_tools.LOG_LEVEL_ERROR)
        else:
            self.log("no key CONFIG_FILE in glob_config, strange ...",
                     logging_tools.LOG_LEVEL_WARN)
    def _log_config(self):
        self.log("Config info:")
        try:
            for line, log_level in self.__glob_config.get_log(clear=True):
                self.log(" - clf: [%d] %s" % (log_level, line))
        except:
            self.log("error reading log from glob_config: %s" % (process_tools.get_except_info()),
                     logging_tools.LOG_LEVEL_ERROR)
        conf_info = self.__glob_config.get_config_info()
        self.log("Found %d valid config-lines:" % (len(conf_info)))
        for conf in conf_info:
            self.log("Config : %s" % (conf))
    def _set_localhost_stuff(self):
        try:
            self.__opt_dict["HOST_IP"] = socket.gethostbyname(self.__opt_dict["HOST_SHORT"])
        except:
            self.log("cannot resolve host_name '%s': %s" % (self.__opt_dict["HOST_SHORT"],
                                                            process_tools.get_except_info()),
                     logging_tools.LOG_LEVEL_ERROR)
            self.__opt_dict["HOST_IP"] = "127.0.0.1"
    def _write_run_info(self):
        self.log("running on host %s (IP %s)" % (self.__opt_dict["HOST_SHORT"],
                                                 self.__opt_dict["HOST_IP"]),
                 do_print=True)
    def get_stat_str(self, ret_value):
        stat_dict = {0 : "OK",
                     1 : "Error",
                     2 : "Warning"}
        return stat_dict.get(ret_value, "unknown ret_value %d" % (ret_value))
    def _copy_environments(self):
        self.__env_dict = dict([(key, str(os.environ[key])) for key in os.environ.keys()])
        self.__env_int_dict = dict([(key, value) for key, value in [line.split("=", 1) for line in file("%s/config" % (self.__env_dict["SGE_JOB_SPOOL_DIR"]), "r").read().strip().split("\n") if line.count("=")]])
    def _log_environments(self):
        out_list = logging_tools.new_form_list()
        for key in sorted(self.__env_dict.keys()):
            out_list.append([logging_tools.form_entry(key, header="Key"),
                             logging_tools.form_entry(self.__env_dict[key], header="Value")])
        self.write_file("env_%s" % (self.__opt_dict["CALLER_NAME_SHORT"]), str(out_list).split("\n"))
        out_list = logging_tools.new_form_list()
        for key in sorted(self.__env_int_dict.keys()):
            out_list.append([logging_tools.form_entry(key, header="Key"),
                             logging_tools.form_entry(self.__env_int_dict[key], header="Value")])
        self.write_file("env_int_%s" % (self.__opt_dict["CALLER_NAME_SHORT"]), str(out_list).split("\n"))
    def _log_limits(self):
        # read limits
        r_dict = {}
        try:
            import resource
        except ImportError:
            pass
        available_resources = [key for key in dir(resource) if key.startswith("RLIMIT")]
        for av_r in available_resources:
            try:
                r_dict[av_r] = resource.getrlimit(getattr(resource, av_r))
            except ValueError:
                r_dict[av_r] = "invalid resource"
            except:
                r_dict[av_r] = None
        if r_dict:
            res_keys = sorted(r_dict.keys())
            self.log("%s defined" % (logging_tools.get_plural("limit", len(res_keys))))
            res_list = logging_tools.new_form_list()
            for key in res_keys:
                val = r_dict[key]
                if type(val) == type(""):
                    info_str = val
                elif type(val) == type(()):
                    info_str = "%8d (hard), %8d (soft)" % val
                else:
                    info_str = "None (error?)"
                res_list.append([logging_tools.form_entry(key, header="key"),
                                 logging_tools.form_entry(info_str, header="value")])
            self.write_file("limits_%s" % (self.__opt_dict["CALLER_NAME_SHORT"]),
                            str(res_list).split("\n"))
        else:
            self.log("no limits found, strange ...", logging_tools.LOG_LEVEL_WARN)
    def _log_resources(self):
        res_used = {}
        jsd = os.environ.get("SGE_JOB_SPOOL_DIR", "")
        if jsd:
            usage_file = "%s/usage" % (jsd)
            if os.path.isfile(usage_file):
                try:
                    ufl = dict([[part.strip() for part in line.strip().split("=", 1)] for line in file(usage_file, "r").read().split("\n") if line.count("=")])
                except:
                    self.log("error reading usage_file %s: %s" % (usage_file,
                                                                  process_tools.get_except_info()),
                             logging_tools.LOG_LEVEL_ERROR)
                else:
                    try:
                        if ufl.has_key("ru_wallclock"):
                            res_used["time_wall"] = sec_to_str(int(ufl["ru_wallclock"]))
                        if ufl.has_key("start_time") and ufl.has_key("end_time"):
                            res_used["elapsed"] = sec_to_str(int(ufl["end_time"]) - int(ufl["start_time"]))
                        if ufl.has_key("exit_status"):
                            res_used["exit_status"] = str(ufl["exit_status"])
                        if ufl.has_key("ru_utime"):
                            res_used["time_user"] = sec_to_str(int(ufl["ru_utime"]))
                        if ufl.has_key("ru_stime"):
                            res_used["time_system"] = sec_to_str(int(ufl["ru_stime"]))
    ##                     if ufl.has_key("ru_ixrss"):
    ##                         res_used["shared memory size"] = str(ufl["ru_ixrss"])
    ##                     if ufl.has_key("ru_isrss"):
    ##                         res_used["memory size"] = str(ufl["ru_isrss"])
                    except:
                        pass
            else:
                self.log("no useage file in %s" % (jsd),
                         logging_tools.LOG_LEVEL_ERROR)
        else:
            self.log("no SGE_JOB_SPOOL_DIR in os.environ defined",
                     logging_tools.LOG_LEVEL_ERROR)
        if res_used:
            self._print("Resources used:")
            log_res = []
            out_list = logging_tools.new_form_list()
            #f_str = "%%%ds : %%s%%s" % (max([len(x) for x in res_used.keys()]))
            for key, value in [(key, res_used[key]) for key in sorted(res_used.keys())]:
                ext_str = ""
                if key == "exit_status":
                    try:
                        i_val = int(value)
                    except:
                        pass
                    else:
                        ext_str = {0   : "no failure",
                                   1   : "error before job",
                                   2   : "before writing config",
                                   3   : "before writing pid",
                                   4   : "before writing pid",
                                   5   : "reading config file",
                                   6   : "setting processor set",
                                   7   : "before prolog",
                                   8   : "in prolog",
                                   9   : "before pestart",
                                   10  : "in pestart",
                                   11  : "before job",
                                   12  : "before pestop",
                                   13  : "in pestop",
                                   14  : "before epilogue",
                                   15  : "in epilog",
                                   16  : "releasing processor set",
                                   24  : "migrating",
                                   25  : "rescheduling",
                                   26  : "opening output file",
                                   27  : "searching requested shell",
                                   28  : "changing to working directory",
                                   100 : "assumedly after job"}.get(i_val, "")
                        if i_val == 99:
                            self._set_exit_code("requeue requested", i_val)
                        ext_str = ext_str and " (%s)" % (ext_str) or ""
                out_list.append([logging_tools.form_entry(key, header="key"),
                                 logging_tools.form_entry(value, header="value"),
                                 logging_tools.form_entry(ext_str, header="info")])
                log_res.append("%s:%s%s" % (key, value, ext_str))
            self._print("\n".join(["  %s" % (line) for line in str(out_list).split("\n")]))
            self.log("reported %d resources: %s" % (len(log_res), ", ".join(log_res)))
        else:
            self.log("No resources found", do_print=True)
    # loop functions
    def loop_start(self):
        self.__send_idx, self.__pending_dict = (0, {})
        self.__start_time = time.time()
        self.send_pool_message(("log", "log_name is %s" % (self.__log_name)))
        # copy environment
        self._copy_environments()
        # populate glob_config
        self._parse_server_addresses()
        self._set_localhost_stuff()
        # populate opt_dict
        self._parse_sge_env()
        self._check_user()
        self._parse_job_script()
        self._log_arguments()
        self._read_config()
        self._log_config()
        #self.write_file("aha", "/etc/hosts")
        #self.write_file("aha", "/etc/services")
        if self.is_start_call():
            self._log_environments()
            self._log_limits()
        if self.is_proepilogue_call():
            self._write_proepi_header()
        elif self.is_pe_call():
            self._write_pe_header()
        if self.is_start_call():
            self._write_run_info()
    def _loop(self):
        self.log("starting inner loop")
        if self.__opt_dict["CALLER_NAME_SHORT"] == "prologue":
            self._prologue()
        elif self.__opt_dict["CALLER_NAME_SHORT"] == "epilogue":
            self._epilogue()
        elif self.is_pe_start_call():
            self._pe_start()
        elif self.is_pe_stop_call():
            self._pe_stop()
        else:
            pass
        self.log("ending inner loop")
        self.send_pool_message(("done", self.__return_value))
        self.__net_server.break_call()
        self.inner_loop(force_wait=True)
    def loop_end(self):
        if self.__opt_dict["CALLER_NAME_SHORT"] == "epilogue":
            self._log_resources()
        self.__end_time = time.time()
        if self.is_proepilogue_call():
            self._write_proepi_footer()
        elif self.is_pe_call():
            self._write_pe_footer()
        self.log("took %s" % (logging_tools.get_diff_time_str(self.__end_time - self.__start_time)))
        if self.__log_template:
            self.__log_template.set_command_and_send("close_log")
        else:
            self.__logger.log_command("CLOSE")
    # different runtypes
    def _prologue(self):
        self._send_tag("job_start", queue_list=[self.__opt_dict["HOST_SHORT"]])
        self._kill_foreign_pids([LOCAL_IP])
        self._remove_foreign_ipcs([LOCAL_IP])
        if self.__glob_config.get("UMOUNT_CALL", True):
            self._umount_nfs_mounts([LOCAL_IP])
        self._create_wrapper_script()
        if self.__opt_dict.get("MONITOR_JOBS", True):
            self._start_monitor_threads([LOCAL_IP], "%s.s" % (self.__opt_dict["FULL_JOB_ID"]))
    def _epilogue(self):
        self._send_tag("job_stop", queue_list=[self.__opt_dict["HOST_SHORT"]])
        if self.__opt_dict.get("MONITOR_JOBS", True):
            self._collect_monitor_threads([LOCAL_IP], "%s.s" % (self.__opt_dict["FULL_JOB_ID"]))
            self._stop_monitor_threads([LOCAL_IP], "%s.s" % (self.__opt_dict["FULL_JOB_ID"]))
            self._show_monitor_info()
        self._kill_foreign_pids([LOCAL_IP])
        self._remove_foreign_ipcs([LOCAL_IP])
        if self.__glob_config.get("UMOUNT_CALL", True):
            self._umount_nfs_mounts([LOCAL_IP])
        self._kill_stdout_stderr_childs()
        self._delete_wrapper_script()
    def _pe_start(self):
        self.log("pe_start called")
        self._generate_hosts_file()
        self._send_tag("pe_start", queue_list=self.__node_list)
        self._write_hosts_file("save")
        self._show_pe_hosts()
        # check reachability of user-homes
        self._check_homedir(self.__node_list)
        if not self.__return_value:
            self._flight_check("preflight")
        if not self.__return_value:
            # check if exit_code is still ok
            self._kill_foreign_pids(self.__node_list)
            self._remove_foreign_ipcs(self.__node_list)
            if self.__glob_config.get("UMOUNT_CALL", True):
                self._umount_nfs_mounts(self.__node_list)
            if self.__opt_dict.get("MONITOR_JOBS", True):
                self._start_monitor_threads(self.__node_list, "%s.p" % (self.__opt_dict["FULL_JOB_ID"]))
            # determine how to establish the lam universe
            if self.__opt_dict["CALLER_NAME_SHORT"] == "lamstart":
                self._call_command("lamboot", "%%s -v %s" % (self.__opt_dict["HOSTFILE_PLAIN_MPI"]), hold_on_error=True, error_str="lamboot not found")
    def _pe_stop(self):
        self.log("pe_stop called")
        self._generate_hosts_file()
        self._send_tag("pe_stop", queue_list=self.__node_list)
        self._show_pe_hosts()
        self._write_hosts_file("keep")
        if self.__opt_dict.get("MONITOR_JOBS", True):
            self._collect_monitor_threads(self.__node_list, "%s.p" % (self.__opt_dict["FULL_JOB_ID"]))
            self._stop_monitor_threads(self.__node_list, "%s.p" % (self.__opt_dict["FULL_JOB_ID"]))
        if self.__opt_dict["CALLER_NAME_SHORT"] == "lamstop":
            self._call_command(["lamwipe", "wipe"], "%%s -v %s" % (self.__opt_dict["HOSTFILE_PLAIN_MPI"]), hold_on_error=False, error_str="lamwipe or wipe not found")
        self._kill_foreign_pids(self.__node_list)
        self._remove_foreign_ipcs(self.__node_list)
        if self.__glob_config.get("UMOUNT_CALL", True):
            self._umount_nfs_mounts(self.__node_list)
        self._flight_check("postflight")
        self._write_hosts_file("delete")
    # helper functions
    # for pe (parallel)
    def _generate_hosts_file(self):
        orig_file, new_file = (self.__env_dict["PE_HOSTFILE"],
                               "/tmp/%s_%s" % (os.path.basename(self.__env_dict["PE_HOSTFILE"]),
                                                                self.__opt_dict["FULL_JOB_ID"]))
        # node_file ok
        nf_ok = False
        if os.path.isfile(orig_file):
            try:
                node_list = [line.strip() for line in file(orig_file, "r").readlines() if line.strip()]
            except:
                self.log("Cannot read node_file %s: %s" % (orig_file,
                                                           process_tools.get_except_info()),
                         logging_tools.LOG_LEVEL_ERROR)
            else:
                nf_ok = True
                self.__node_list = [node_name.split(".")[0] for node_name in [line.split()[0] for line in node_list]]
                node_dict = dict([(node_name.split(".")[0], {"num" : int(node_num)}) for node_name, node_num in [line.split()[0 : 2] for line in node_list]])
        else:
            self.log("No node_file name '%s' found" % (orig_file),
                     logging_tools.LOG_LEVEL_ERROR)
        if not nf_ok:
            # dummy default node dict
            self.__node_list = [self.__opt_dict["HOST_SHORT"]]
            node_dict = {self.__opt_dict["HOST_SHORT"] : {"num" : 1}}
        # node_list is now a dict {short host-name : {num : #instnaces }}
        if not self.__glob_config.get("HAS_MPI_INTERFACE", True):
            # no mpi-interfaces
            pass
        else:
            mpi_postfix = self.__glob_config.get("MPI_POSTFIX", "mp")
            self.log("using mpi_postfix '%s' for PE '%s' on queue '%s'" % (mpi_postfix,
                                                                           self.__opt_dict["PE"],
                                                                           self.__opt_dict["QUEUE"]))
            for key, value in node_dict.iteritems():
                value["mpi_name"] = "%s%s" % (key, mpi_postfix)
        # resolve names
        for node_name in self.__node_list:
            node_stuff = node_dict[node_name]
            try:
                node_ip = socket.gethostbyname(node_name)
            except:
                self.log("error resolving %s to IP: %s" % (node_name,
                                                           process_tools.get_except_info()),
                         logging_tools.LOG_LEVEL_ERROR)
                node_ip = node_name
            node_stuff["ip"] = node_ip
            node_stuff["ip_list"] = [node_ip]
            if node_stuff.has_key("mpi_name"):
                try:
                    mpi_ip = socket.gethostbyname(node_stuff["mpi_name"])
                except:
                    self.log("error resolving %s to IP: %s" % (node_stuff["mpi_name"],
                                                               process_tools.get_except_info()),
                             logging_tools.LOG_LEVEL_ERROR)
                    mpi_ip = node_stuff["mpi_name"]
                node_stuff["mpi_ip"] = mpi_ip
                node_stuff["ip_list"].append(mpi_ip)
        self.log("content of node_list")
        content = pprint.PrettyPrinter(indent=1, width=10).pformat(self.__node_list)
        for line in content.split("\n"):
            self.log(" - %s" % (line))
        self.log("content of node_dict")
        content = pprint.PrettyPrinter(indent=1, width=10).pformat(node_dict)
        for line in content.split("\n"):
            self.log(" - %s" % (line))
        self.__node_dict = node_dict
    def _write_hosts_file(self, action):
        # generate various versions of host-file
        for var_name, file_name, generator in [# to be compatible
                                               # short file without MPI/IB-Interfacepostfix
                                               ("HOSTFILE_SHORT"     , "/tmp/pe_hostfile_s_%s" % (self.__opt_dict["FULL_JOB_ID"])     , self._whf_short),
                                               ("HOSTFILE_OLD"       , "/tmp/pe_hostfile_%s" % (self.__opt_dict["FULL_JOB_ID"])       , self._whf_plain),
                                               ("HOSTFILE_PLAIN_MPI" , "/tmp/hostfile_plain_mpi_%s" % (self.__opt_dict["FULL_JOB_ID"]), self._whf_plain_mpi),
                                               ("HOSTFILE_PLAIN"     , "/tmp/hostfile_plain_%s" % (self.__opt_dict["FULL_JOB_ID"])    , self._whf_plain),
                                               ("HOSTFILE_WITH_CPUS" , "/tmp/hostfile_wcpu_%s" % (self.__opt_dict["FULL_JOB_ID"])     , self._whf_wcpu),
                                               ("HOSTFILE_WITH_SLOTS", "/tmp/hostfile_wslot_%s" % (self.__opt_dict["FULL_JOB_ID"])    , self._whf_wslot)]:
            #("PE_HOSTFILE"        , "/tmp/hostfile_sge_%s" % (self.__opt_dict["FULL_JOB_ID"]), self._whf_sge)]:
            self.__opt_dict[var_name] = file_name
            self._add_script_var(var_name, file_name)
            if action == "save":
                open(file_name, "w").write("\n".join(generator()) + "\n")
            elif action == "delete":
                if os.path.isfile(file_name):
                    try:
                        os.unlink(file_name)
                    except:
                        self.log("cannot remove %s: %s" % (file_name,
                                                           process_tools.get_except_info()),
                                 logging_tools.LOG_LEVEL_ERROR)
    def _show_pe_hosts(self):
        # show pe_hosts
        self._print("  %s defined: %s" % (logging_tools.get_plural("NFS host", len(self.__node_list)),
                                          ", ".join(["%s (%s, %d)" % (node_name,
                                                                      self.__node_dict[node_name]["ip"],
                                                                      self.__node_dict[node_name]["num"]) for node_name in self.__node_list])))
        # mpi hosts
        mpi_nodes = [node_name for node_name in self.__node_list if self.__node_dict[node_name].has_key("mpi_name")]
        self._print("  %s defined: %s" % (logging_tools.get_plural("MPI host", len(mpi_nodes)),
                                          ", ".join(["%s (on %s, %s, %d)" % (self.__node_dict[node_name]["mpi_name"],
                                                                             node_name,
                                                                             self.__node_dict[node_name]["mpi_ip"],
                                                                             self.__node_dict[node_name]["num"]) for node_name in mpi_nodes]) or "---"))
    def _get_mpi_name(self, n_name):
        return self.__node_dict[n_name].get("mpi_name", n_name)
    def _whf_short(self):
        return self.__node_list
    def _whf_plain_mpi(self):
        return sum([[self._get_mpi_name(node_name)] * self.__node_dict[node_name]["num"] for node_name in self.__node_list], [])
    def _whf_plain(self):
        return sum([[node_name] * self.__node_dict[node_name]["num"] for node_name in self.__node_list], [])
    def _whf_wcpu(self):
        return ["%s cpu=%d" % (self._get_mpi_name(node_name), self.__node_dict[node_name]["num"]) for node_name in self.__node_list]
    def _whf_wslot(self):
        return ["%s max_slots=%d" % (self._get_mpi_name(node_name), self.__node_dict[node_name]["num"]) for node_name in self.__node_list]
    def _whf_sge(self):
        # like PE_HOSTFILE just with the Parallel Interfaces
        return ["%s %d %s@%s <NULL>" % (self._get_mpi_name(node_name),
                                        self.__node_dict[node_name]["num"],
                                        self.__opt_dict["QUEUE"],
                                        node_name) for node_name in self.__node_list]
    # job monitor stuff
    def _start_monitor_threads(self, con_list, mon_id):
        self.log("Starting monitor threads with id %s on %s" % (mon_id,
                                                                logging_tools.get_plural("node", len(con_list))))
        self._collserver_command(dict([(con_entry, ("start_monitor", mon_id)) for con_entry in con_list]), result_type="o")
    def _stop_monitor_threads(self, con_list, mon_id):
        self.log("Stoping monitor threads with id %s on %s" % (mon_id,
                                                               logging_tools.get_plural("node", len(con_list))))
        self._collserver_command(dict([(con_entry, ("stop_monitor", mon_id)) for con_entry in con_list]), result_type="o")
    def _collect_monitor_threads(self, con_list, mon_id):
        self.log("Collecting monitor threads with id %s on %s" % (mon_id,
                                                                  logging_tools.get_plural("node", len(con_list))))
        self.__act_monitor_dict = {}
        self._collserver_command(dict([(con_entry, ("monitor_info", mon_id)) for con_entry in con_list]), result_type="o", decode_func=self._decode_monitor_result)
        self.log("got monitor dicts for %s: %s" % (logging_tools.get_plural("host", len(self.__act_monitor_dict.keys())),
                                                   logging_tools.compress_list(self.__act_monitor_dict.keys())))
        mon_file = "/tmp/.monitor_%s" % (mon_id)
        try:
            open(mon_file, "w").write(server_command.sys_to_net(self.__act_monitor_dict))
        except:
            self.log("cannot write monitor file %s: %s" % (mon_file,
                                                           process_tools.get_except_info()),
                     logging_tools.LOG_LEVEL_ERROR)
    def _show_monitor_info(self):
        # read mon_dicts
        mon_dict = {}
        for key, postfix in [("serial", "s"),
                             ("parallel", "p")]:
            mon_file = "/tmp/.monitor_%s.%s" % (self.__opt_dict["FULL_JOB_ID"],
                                                postfix)
            if os.path.isfile(mon_file):
                try:
                    mon_stuff = server_command.net_to_sys(open(mon_file, "r").read())
                except:
                    self.log("cannot read %s monitor data from %s: %s" % (key,
                                                                          mon_file,
                                                                          process_tools.get_except_info()),
                             logging_tools.LOG_LEVEL_ERROR)
                else:
                    mon_dict[key] = mon_stuff
                    try:
                        os.unlink(mon_file)
                    except:
                        self.log("cannot remove %s monitor data file %s: %s" % (key,
                                                                                mon_file,
                                                                                process_tools.get_except_info()),
                                 logging_tools.LOG_LEVEL_ERROR)
            else:
                self.log("no %s monitor_file %s" % (key,
                                                    mon_file),
                         logging_tools.LOG_LEVEL_WARN)
        # show data
        for mon_key in sorted(mon_dict.keys()):
            mon_stuff = mon_dict[mon_key]
            mon_hosts = mon_stuff.keys()
            self._print("")
            self._print("%s monitor data found for %s: %s" % (mon_key,
                                                              logging_tools.get_plural("host", len(mon_hosts)),
                                                              logging_tools.compress_list(mon_hosts)))
        self._print("")
    def _decode_monitor_result(self, arg, **args):
        #if type(arg) == type({}):
        src_host = args.get("host")
        if arg.startswith("cok"):
            if bz2:
                try:
                    ret_dict = server_command.net_to_sys(bz2.decompress(arg[4:]))
                except:
                    ret_dict = {}
                    self.log("cannot interpret %s from %s: %s" % (arg,
                                                                  src_host,
                                                                  process_tools.get_except_info()),
                             logging_tools.LOG_LEVEL_ERROR)
                else:
                    self.log("decoded bz2-dict with %s from %s" % (logging_tools.get_plural("byte", len(arg)),
                                                                   src_host))
            else:
                ret_dict = {}
                self.log("cannnot decode bz2 input from %s (no bz2 module found)" % (src_host),
                         logging_tools.LOG_LEVEL_ERROR)
        elif arg.startswith("ok"):
            try:
                ret_dict = server_command.net_to_sys(arg[3:])
            except:
                ret_dict = {}
                self.log("cannot interpret %s from %s: %s" % (arg,
                                                              src_host,
                                                              process_tools.get_except_info()),
                         logging_tools.LOG_LEVEL_ERROR)
            else:
                self.log("decoded dict with %s from %s" % (logging_tools.get_plural("byte", len(arg)),
                                                           src_host))
        else:
            ret_dict = {}
            self.log("cannot interpret result %s from %s" % (arg,
                                                             src_host),
                     logging_tools.LOG_LEVEL_ERROR)
        if ret_dict:
            # migrate old version to new version
            if ret_dict.has_key("cache"):
                for key, value in ret_dict["cache"].iteritems():
                    if type(value) == type({}):
                        try:
                            # convert to new style
                            if value.has_key("default"):
                                # new-style collserver
                                new_value = hm_classes.mvect_entry(key,
                                                                   default=value["default"],
                                                                   base=value["base"],
                                                                   factor=value["factor"],
                                                                   info=value["info"],
                                                                   unit=value["unit"])
                            else:
                                # old-style collserver
                                new_value = hm_classes.mvect_entry(key,
                                                                   default=value["d"],
                                                                   base=value["b"],
                                                                   factor=value["f"],
                                                                   info=value["i"],
                                                                   unit=value["u"])
                            # set monitor values
                            new_value.min_value = value["min"]
                            new_value.max_value = value["max"]
                            new_value.total_value = value["tot"]
                            new_value.num = value["num"]
                            ret_dict["cache"][key] = new_value
                        except:
                            self.log("cannot convert key %s (host %s): %s" % (key,
                                                                              src_host,
                                                                              process_tools.get_except_info()),
                                     logging_tools.LOG_LEVEL_ERROR)
            self.__act_monitor_dict[src_host] = ret_dict.get("cache", {})
        return "ok dict with %s (cache_dict has %s)" % (logging_tools.get_plural("key", len(ret_dict.keys())),
                                                        logging_tools.get_plural("key", len(ret_dict.get("cache", {}).keys())))
    # general
    def _add_script_var(self, key, value):
        var_file = self._get_var_script_name()
        self.log("adding variable (%s=%s) to var_file %s" % (key,
                                                             value,
                                                             var_file))
        file(var_file, "a").write("export %s=%s\n" % (key, value))
    def _parse_job_script(self):
        if os.environ.has_key("JOB_SCRIPT"):
            script_file = os.environ["JOB_SCRIPT"]
            try:
                lines = [line.strip() for line in file(script_file, "r").read().split("\n")]
            except:
                self.log("Cannot read Scriptfile '%s' (%s)" % (script_file,
                                                               process_tools.get_except_info()),
                         logging_tools.LOG_LEVEL_ERROR)
            else:
                if self.__opt_dict["CALLER_NAME_SHORT"] == "prologue":
                    s_list = logging_tools.new_form_list()
                else:
                    s_list = None
                num_lines, num_sge, num_init = (len(lines), 0, 0)
                init_dict = {}
                for line, line_num in zip(lines, xrange(len(lines))):
                    if s_list is not None:
                        s_list.append([logging_tools.form_entry(line_num + 1, header="line"),
                                       logging_tools.form_entry(line, header="content")])
                    if line.startswith("#$ "):
                        num_sge += 1
                    elif line.startswith("#init "):
                        # valid init-keys:
                        # MONITOR=<type>
                        # MONITOR_KEYS=<key_list;>
                        # MONITOR_FULL_KEY_LIST=<true>
                        # TRIGGER_ERROR (flag, triggers error)
                        # EXTRA_WAIT=x (waits for x seconds)
                        num_init += 1
                        line_parts = [x.split("=", 1) for x in line[5:].strip().split(",")]
                        self.log("found #init-line '%s'" % (line))
                        if line_parts:
                            for key, value in [x for x in line_parts if len(x) == 2]:
                                key, value = (key.strip().upper(), value.strip().lower())
                                if key and value:
                                    init_dict[key] = value
                                    self.log("recognised init option '%s' (value '%s')" % (key, value))
                                    self.__opt_dict.add_config_dict({key : configfile.str_c_var(value, source="jobscript")})
                            for key in [x[0].strip().upper() for x in line_parts if len(x) == 1]:
                                init_dict[key] = True
                                self.log("recognised init option '%s' (value '%s')" % (key, True))
                                self.__opt_dict.add_config_dict({key : configfile.bool_c_var(True, source="jobscript")})
                self.log("Scriptfile '%s' has %d lines (%s and %s)" % (script_file,
                                                                       num_lines,
                                                                       logging_tools.get_plural("SGE related line", num_sge),
                                                                       logging_tools.get_plural("init.at related line", num_init)))
                if s_list:
                    self.write_file("jobscript", str(s_list).split("\n"), linenumbers=False)
        else:
            self.log("environ has no JOB_SCRIPT key", logging_tools.LOG_LEVEL_WARN)
    def _parse_server_addresses(self):
        for src_file, key, default in [("/etc/motherserver", "MOTHER_SERVER", "localhost"),
                                       ("/etc/sge_server"  , "SGE_SERVER"   , "localhost")]:
            try:
                act_val = file(src_file, "r").read().split()[0]
            except:
                self.log("cannot read %s from %s: %s" % (key,
                                                         src_file,
                                                         process_tools.get_except_info()),
                         logging_tools.LOG_LEVEL_ERROR)
                act_val = default
            self.__glob_config.add_config_dict({key : configfile.str_c_var(act_val, source=src_file)})
    def _parse_sge_env(self):
        # pe name
        if os.environ.has_key("PE") and os.environ.has_key("PE_HOSTFILE"):
            self.__opt_dict["PE"] = os.environ["PE"]
        else:
            self.__opt_dict["PE"] = ""
        # TASK_ID
        if os.environ.has_key("SGE_TASK_FIRST") and os.environ.has_key("SGE_TASK_LAST") and os.environ.has_key("SGE_TASK_ID") and os.environ.has_key("SGE_TASK_STEPSIZE"):
            if os.environ["SGE_TASK_ID"] == "undefined":
                self.__opt_dict["TASK_ID"] = 0
            else:
                try:
                    self.__opt_dict["TASK_ID"] = int(os.environ["SGE_TASK_ID"])
                except:
                    self.log("error extracting SGE_TASK_ID: %s" % (process_tools.get_except_info()),
                             logging_tools.LOG_LEVEL_ERROR)
                    self.__opt_dict["TASK_ID"] = 0
                else:
                    pass
        else:
            self.__opt_dict["TASK_ID"] = 0
        self.__opt_dict["FULL_JOB_ID"] = "%s%s" % (self.__opt_dict["JOB_ID"],
                                                   ".%s" % (self.__opt_dict["TASK_ID"]) if self.__opt_dict["TASK_ID"] else "")
    def _check_user(self):
        try:
            pw_data = pwd.getpwnam(self.__opt_dict["JOB_OWNER"])
        except KeyError:
            pw_data = None
            uid, gid, group = (0, 0, "unknown")
            self.log("Unknown user '%s', using ('%s', %d, %d) as (group, uid, gid)" % (self.__opt_dict["JOB_OWNER"],
                                                                                       group,
                                                                                       uid,
                                                                                       gid),
                     logging_tools.LOG_LEVEL_ERROR)
        else:
            uid = pw_data[2]
            gid = pw_data[3]
            try:
                grp_data = grp.getgrgid(gid)
            except KeyError:
                group = "unknown"
                self.log("Unknown group-id %d for user '%s', using %s as group" % (gid,
                                                                                   user,
                                                                                   group),
                         logging_tools.LOG_LEVEL_ERROR)
            else:
                group = grp_data[0]
        self.__opt_dict["GROUP"] = group
        self.__opt_dict["UID"] = uid
        self.__opt_dict["GID"] = gid
    def get_owner_str(self):
        return "user %s (%d), group %s (%d)" % (self.__opt_dict["JOB_OWNER"],
                                                self.__opt_dict["UID"],
                                                self.__opt_dict["GROUP"],
                                                self.__opt_dict["GID"])
    def write_file(self, name, content, **args):
        ss_time = time.time()
        log_t, logger = (None, None)
        try:
            logger = logging_tools.get_logger("%s.%s.%s" % (self.__glob_config["LOG_NAME"],
                                                            self.__log_dir.replace(".", "\."),
                                                            name),
                                              self.__glob_config["LOG_DESTINATION"],
                                              init_logger=True)
        except:
            log_t = net_logging_tools.log_command("%s.d" % (self.__glob_config["LOG_NAME"]), thread="job")
            log_t.set_destination(self.__glob_config["LOG_DESTINATION"])
            log_t.set_sub_names("%s/%s" % (self.__log_dir, name))
            log_t.set_command_and_send("open_log")
            log_t.set_command_and_send("set_uid")
            log_t.set_command("log")
        if type(content) == type("") and content.startswith("/"):
            # content is a filename
            content = file(content, "r").read().split("\n")
        if type(content) == type(""):
            content = content.split("\n")
        log_str = "content '%s', %s:" % (name,
                                         logging_tools.get_plural("line", len(content)))
        if logger:
            logger.log(logging_tools.LOG_LEVEL_OK, log_str)
        else:
            log_t.log(log_str)
        if args.get("linenumbers", True):
            for line_num, line in zip(xrange(len(content)), content):
                log_str = "%3d %s" % (line_num + 1, line)
                if logger:
                    logger.log(logging_tools.LOG_LEVEL_OK, log_str)
                else:
                    log_t.log(log_str)
        else:
            for line in content:
                if logger:
                    logger.log(logging_tools.LOG_LEVEL_OK, line)
                else:
                    log_t.log(line)
        if log_t:
            log_t.set_command_and_send("close_log")
        else:
            logger.log_command("CLOSE")
        se_time = time.time()
        self.log("storing content to file %s (%s) in %s" % (name,
                                                            logging_tools.get_plural("line", len(content)),
                                                            logging_tools.get_diff_time_str(se_time - ss_time)))
    def _init_exit_code(self):
        self.__return_value = 0
    def _set_exit_code(self, cause, exit_code):
        self.__return_value = exit_code
        self.log("setting exit_code to %d because of %s" % (exit_code,
                                                            cause),
                 logging_tools.LOG_LEVEL_ERROR)
    def _call_command(self, com_names, arg_form="%s", **args):
        # args: retries (default 2)
        max_retries = args.get("retries", 2)
        ret_val = 1
        if type(com_names) == type(""):
            com_names = [com_names]
        s_time = time.time()
        self.log("call_command for %s (%s), (argument_formstring is '%s')" % (logging_tools.get_plural("command", len(com_names)),
                                                                              ", ".join(com_names),
                                                                              arg_form))
        for com_name in com_names:
            path_field = []
            com = arg_form % com_name
            compath_found = ""
            if com_name.startswith("/"):
                path_field = ["/"]
                if os.path.exists(com_name):
                    compath_found = com_name
            else:
                for path in sorted(dict([(x.strip(), 0) for x in os.environ.get("PATH", "").split(":") if x.startswith("/")]).keys()):
                    compath_found = "%s/%s" % (path, com_name)
                    path_field.append(path)
                    if os.path.exists(compath_found):
                        break
                else:
                    compath_found = ""
            if compath_found:
                self.log("starting command '%s' (full path of executable %s is %s), %s" % (com,
                                                                                           com_name,
                                                                                           compath_found,
                                                                                           logging_tools.get_plural("retry", max_retries)))
                for idx in range(max_retries):
                    out_file, err_file = ("/tmp/.output_%s" % (self.__opt_dict["FULL_JOB_ID"]),
                                          "/tmp/.error_%s" % (self.__opt_dict["FULL_JOB_ID"]))
                    cs_time = time.time()
                    ret_val = os.system("%s >%s 2>%s" % (com,
                                                         out_file,
                                                         err_file))
                    ce_time = time.time()
                    out_lines = [line.rstrip() for line in open(out_file, "r").read().split("\n") if len(line.strip())]
                    err_lines = [line.rstrip() for line in open(err_file, "r").read().split("\n") if len(line.strip())]
                    out_log_name = "extcom_%d_%s" % (idx + 1,
                                                     com.replace("/", "_").replace(" ", "_").replace("__", "_").replace("__", "_"))
                    self.log("Saving output (%s) / error (%s) [return value %d] to %s.(e|o) (call took %s)" % (logging_tools.get_plural("line", len(out_lines)),
                                                                                                               logging_tools.get_plural("line", len(err_lines)),
                                                                                                               ret_val,
                                                                                                               out_log_name,
                                                                                                               logging_tools.get_diff_time_str(ce_time - cs_time)),
                             logging_tools.LOG_LEVEL_ERROR if ret_val else logging_tools.LOG_LEVEL_OK)
                    if ret_val:
                        self.log("calling %s (retry %d of %d) returned an error (took %s): %d" % (com,
                                                                                                  idx + 1,
                                                                                                  max_retries,
                                                                                                  logging_tools.get_diff_time_str(ce_time - cs_time),
                                                                                                  ret_val),
                                 logging_tools.LOG_LEVEL_ERROR,
                                 do_print=True)
                    else:
                        self.log("calling %s (retry %d of %d) successful in %s" % (com,
                                                                                   idx + 1,
                                                                                   max_retries,
                                                                                   logging_tools.get_diff_time_str(ce_time - cs_time)),
                                 do_print=True)
                    self.write_file("%s.o" % (out_log_name), out_lines)
                    self.write_file("%s.e" % (out_log_name), err_lines)
                    try:
                        os.unlink(out_file)
                        os.unlink(err_file)
                    except:
                        self.log("error removing %s and/or %s: %s" % (out_file,
                                                                      err_file,
                                                                      process_tools.get_except_info()),
                                 logging_tools.LOG_LEVEL_ERROR)
                    if ret_val:
                        # only show output if an error occured
                        if out_lines:
                            self._print("Standard output (iteration %d, %s):" % (idx + 1,
                                                                                 logging_tools.get_plural("line", len(out_lines))))
                            self._print("\n".join([" . %s" % (line) for line in out_lines]))
                        if err_lines:
                            self._print("Error output (iteration %d, %s):" % (idx + 1,
                                                                              logging_tools.get_plural("line", len(err_lines))))
                            self._print("\n".join([" * %s" % (line) for line in err_lines]))
                    if not ret_val:
                        break
            else:
                self.log("No executable for '%s' (command %s) found, searched in %s:" % (com,
                                                                                         com_name,
                                                                                         logging_tools.get_plural("path", len(path_field))),
                         logging_tools.LOG_LEVEL_ERROR,
                         do_print=True)
                for path in path_field:
                    self.log(" - %s" % (path),
                             do_print=True)
            if not ret_val:
                break
        e_time = time.time()
        self.log("call_command for %s took %s" % (com_name,
                                                  logging_tools.get_diff_time_str(e_time - s_time)))
        if ret_val:
            self._set_exit_code("error calling %s" % (", ".join(com_names)), 2)
            if args.get("hold_on_error", False):
                # hold the job
                self._send_tag("hold",
                               error=args.get("error_str", "error in call_command (%s)" % (", ".join(com_names))),
                               fail_objects=[self.__opt_dict["FULL_JOB_ID"]])
    # local kill stuff
    def _kill_stdout_stderr_childs(self):
        sge_stdout_path = self.__env_dict["SGE_STDOUT_PATH"]
        sge_stderr_path = self.__env_dict["SGE_STDERR_PATH"]
        pid_dict = process_tools.get_proc_list()
        # build list of pids up to the init-process (pid 1)
        act_pid = os.getpid()
        my_exe_path = os.readlink("/proc/%d/exe" % (act_pid))
        self.log("sge_stdout_path: %s" % (sge_stdout_path))
        self.log("sge_stderr_path: %s" % (sge_stderr_path))
        self.log("my_exe_path: %s" % (my_exe_path))
        my_pid_list = [act_pid]
        while act_pid != 1:
            act_pid = pid_dict[act_pid]["ppid"]
            my_pid_list.append(act_pid)
        kill_pids = []
        check_paths = [act_p for act_p in [sge_stdout_path, sge_stderr_path] if act_p not in ["/dev/null"]]
        p_dir = "/proc"
        for p_id in [int(act_p) for act_p in os.listdir(p_dir) if act_p.isdigit()]:
            full_path = "%s/%d" % (p_dir, p_id)
            cwd_file = "%s/cwd" % (full_path)
            try:
                exe_path = os.readlink("%s/exe" % (full_path))
            except:
                exe_path = ""
            if exe_path != my_exe_path:
                try:
                    cwd_path = os.readlink(cwd_file)
                except:
                    pass
                else:
                    fd_dir = "%s/fd" % (full_path)
                    if os.path.isdir(fd_dir):
                        for fd_num in os.listdir(fd_dir):
                            try:
                                fd_path = "%s/%s" % (fd_dir, fd_num)
                                if os.path.islink(fd_path):
                                    link_target = os.readlink(fd_path)
                                    if link_target in check_paths:
                                        if i_p_id not in my_pid_list and i_p_id not in kill_pids:
                                            kill_pids.append(i_p_id)
                                        #print "+++", p_id, fd_path, link_target
                            except:
                                self.log("cannot read fd %s from %s: %s" % (str(fd_num),
                                                                            fd_dir,
                                                                            process_tools.get_except_info()),
                                         logging_tools.LOG_LEVEL_ERROR)
        if kill_pids:
            self.log("trying to kill %s: %s" % (logging_tools.get_plural("pid", len(kill_pids)),
                                                ", ".join(["%d" % (pid) for pid in sorted(kill_pids)])))
            for kill_pid in kill_pids:
                try:
                    exe_path = os.readlink("/proc/%d/exe" % (kill_pid))
                except:
                    exe_path = "<not readable>"
                self.log("trying to kill pid %d (exe_path %s)" % (kill_pid, exe_path))
                try:
                    os.kill(kill_pid, 15)
                except:
                    pass
            self.log("waiting for 10 seconds for %s to terminate ..." % (logging_tools.get_plural("task", len(kill_pids))),
                     do_print=True)
            for w_idx in xrange(10):
                time.sleep(1)
                still_present_pids = []
                for kill_pid in kill_pids:
                    if os.path.isdir("/proc/%d" % (kill_pid)):
                        still_present_pids.append(kill_pid)
                kill_pids = still_present_pids
                if not kill_pids:
                    break
            if kill_pids:
                self.log("killing remaing %s ..." % (logging_tools.get_plural("task", len(kill_pids))),
                         do_print=True)
                for kill_pid in kill_pids:
                    try:
                        os.kill(kill_pid, 9)
                    except:
                        pass
    # wrapper script tools
    def _get_wrapper_script_name(self):
        return  "%s/%s.new" % (os.path.dirname(self.__env_dict["JOB_SCRIPT"]),
                               self.__opt_dict["FULL_JOB_ID"])
    def _get_var_script_name(self):
        return  "%s/%s.var" % (os.path.dirname(self.__env_dict["JOB_SCRIPT"]),
                               self.__opt_dict["FULL_JOB_ID"])
    def _create_wrapper_script(self):
        # only sensible if sge_starter_method for queue is set
        src_file = self.__env_dict["JOB_SCRIPT"]
        dst_file = self._get_wrapper_script_name()
        var_file = self._get_var_script_name()
        if not dst_file.startswith("/"):
            self.log("refuse to create wrapper script %s" % (dst_file),
                     logging_tools.LOG_LEVEL_ERROR)
            return
        self.log("Creating wrapper-script (%s for %s)" % (dst_file,
                                                          src_file))
        shell_path, shell_start_mode = (self.__env_int_dict.get("shell_path", "/bin/bash"),
                                        self.__env_int_dict.get("shell_start_mode", "posix_compliant"))
        cluster_queue_name = self.__opt_dict["QUEUE"]
        self.log("shell_path is '%s', shell_start_mode is '%s'" % (shell_path,
                                                                   shell_start_mode))
        #cpuset_dir_name = "%s/cpuset" % (g_config["SGE_ROOT"])
        do_cpuset = False
        no_cpuset_cause = []
        if self.__glob_config.get("CPUSET_PE", "notset") == self.__opt_dict.get("PE", "unknown"):
            # not fixed
            num_cpus = int(int_env["pe_slots"])
            act_job.log("requested pe is '%s', trying to allocate a cpuset with %s on queue %s" % (int_env["pe"],
                                                                                                   logging_tools.get_plural("cpu", num_cpus),
                                                                                                   cluster_queue_name),
                        1)
            if os.path.isdir(cpuset_dir_name):
                cpuset_file_name = "%s/%s" % (cpuset_dir_name, cluster_queue_name)
                if os.path.isfile(cpuset_file_name):
                    do_cpuset = True
                else:
                    act_job.log("no cpuset-file '%s', doing normal startmethod" % (cpuset_file_name))
                    no_cpuset_cause.append("no queue-local cpuset config %s" % (cpuset_file_name))
            else:
                act_job.log("no cpuset-dir %s" % (cpuset_dir_name))
                no_cpuset_cause.append("no cpuset-director %s" % (cpuset_dir_name))
            if do_cpuset:
                lock_f = lock_cpuset(act_job)
                act_cpu_set = cpu_set(act_job, cpuset_dir_name, cpuset_file_name)
                # generate new cpuset_name
                act_cpu_set.increase_cpuset_name()
                act_job.log("found cpuset-file at %s, cpuset_name is '%s'" % (cpuset_file_name,
                                                                              act_cpu_set.get_act_cpuset_name()), 1)
                a_lists = act_cpu_set.find_allocation_schemes(num_cpus)
                if a_lists:
                    cpus = a_lists[0]
                    act_cpu_set.allocate_cpus(cpus)
                    act_cpu_set.generate_cpuset(cpus)
                    cpu_set_name = act_cpu_set.get_act_cpuset_name()
                else:
                    do_cpuset = False
                    no_cpuset_cause.append("cannot allocate %s" % (logging_tools.get_plural("cpu", num_cpus)))
                act_cpu_set.write_occupation_to_file()
                unlock_cpuset(act_job, lock_f)
        if do_cpuset:
            if shell_start_mode == "posix_compliant" and shell_path:
                df_lines = ["#!%s" % ("/bin/sh"),
                            "echo 'wrapper_script, with cpu_set'",
                            "export BASH_ENV=$HOME/.bashrc",
                            "export CPUS=\"%s\"" % (" ".join(["%d" % (x) for x in cpus])),
                            "export NCPUS=%d" % (len(cpus)),
                            ". %s" % (var_file),
                            "exec cpuset -q %s -A %s %s $*" % (cpu_set_name, shell_path, src_file),
                            ""]
            else:
                df_lines = ["#!%s" % ("/bin/sh"),
                            "echo 'wrapper_script, with cpu_set'",
                            "export BASH_ENV=$HOME/.bashrc",
                            "export CPUS=\"%s\"" % (" ".join(["%d" % (x) for x in cpus])),
                            "export NCPUS=%d" % (len(cpus)),
                            ". %s" % (var_file),
                            "exec cpuset -q -A %s $*" % (cpu_set_name, src_file),
                            ""]
        else:
            if no_cpuset_cause:
                self.log("not using cpuset because: %s" % (", ".join(no_cpuset_cause)))
            if shell_start_mode == "posix_compliant" and shell_path:
                df_lines = ["#!%s" % ("/bin/sh"),
                            "echo 'wrapper_script, no cpu_set'",
                            "export BASH_ENV=$HOME/.bashrc",
                            ". %s" % (var_file),
                            "exec %s %s $*" % (shell_path, src_file),
                            ""]
            else:
                df_lines = ["#!%s" % ("/bin/sh"),
                            "echo 'wrapper_script, no cpu_set'",
                            "export BASH_ENV=$HOME/.bashrc",
                            ". %s" % (var_file),
                            "exec %s $*" % (src_file),
                            ""]
        file(dst_file, "w").write("\n".join(df_lines))
        file(var_file, "w").write("#!/bin/bash\n")
        self.write_file("wrapper_script", df_lines)
        os.chmod(dst_file, 0755)
        os.chmod(var_file, 0755)
        os.chown(var_file, self.__opt_dict["UID"], self.__opt_dict["GID"])
    def _delete_wrapper_script(self):
        env_keys = sorted(self.__env_int_dict.keys())
        src_file = self.__env_dict["JOB_SCRIPT"]
        dst_file = self._get_wrapper_script_name()
        if not dst_file.startswith("/"):
            self.log("refuse to delete wrapper script %s" % (dst_file),
                     logging_tools.LOG_LEVEL_ERROR)
            return
        self.log("Deleting wrapper-script (%s for %s)" % (dst_file,
                                                          src_file))
        if os.path.isfile(dst_file):
            try:
                os.unlink(dst_file)
            except:
                self.log("error deleting %s: %s" % (dst_file,
                                                    process_tools.get_except_info()),
                         logging_tools.LOG_LEVEL_ERROR)
            else:
                self.log("deleted %s" % (dst_file))
        else:
            self.log("no such file: %s" % (dst_file),
                     logging_tools.LOG_LEVEL_ERROR)
        if self.__glob_config.get("CPUSET_PE", "notset") == self.__opt_dict.get("PE", "unknown"):
            cpuset_dir_name = "%s/cpuset" % (g_config["SGE_ROOT"])
            cpuset_file_name = "%s/%s" % (cpuset_dir_name, int_env["queue"].split("@")[0])
            if os.path.isfile(cpuset_file_name):
                my_lockf = lock_cpuset(act_job)
                act_cpu_set = cpu_set(act_job, cpuset_dir_name, cpuset_file_name)
                act_cpu_set.read_cpuset_name()
                act_cpu_set.free_cpus()
                act_cpu_set.remove_cpuset()
                act_cpu_set.write_occupation_to_file()
                unlock_cpuset(act_job, my_lockf)
            else:
                act_job.log("Cannot find cpuset-file '%s', strange ..." % (cpuset_file_name), 1)
    # network related calls (highlevel)
    def _send_tag(self, tag_name, **args):
        s_time = time.time()
        self.log("Sending tag '%s' to host %s, port %d" % (tag_name,
                                                           self.__glob_config["SGE_SERVER"],
                                                           self.__glob_config.get("SGE_SERVER_PORT", 8009)))
        opt_dict = {"host"       : self.__opt_dict["HOST_SHORT"],
                    "full_host"  : self.__opt_dict["HOST_LONG"],
                    "origin"     : "proepilogue",
                    "job_id"     : self.__opt_dict["FULL_JOB_ID"],
                    "job_num"    : self.__opt_dict["JOB_ID"],
                    "task_id"    : self.__opt_dict["TASK_ID"],
                    "queue_name" : self.__opt_dict["QUEUE"],
                    "job_name"   : self.__opt_dict["JOB_NAME"],
                    "queue_list" : [],
                    "pe_name"    : self.__opt_dict["PE"],
                    "uid"        : self.__opt_dict["UID"],
                    "gid"        : self.__opt_dict["GID"]}
        for key, value in args.iteritems():
            self.log(" - adding key %s (value %s) to opt_dict" % (key,
                                                                  str(value)))
            opt_dict[key] = value
        state, result = self._send_to_sge_server(server_command.server_command(command=tag_name,
                                                                               option_dict=opt_dict))
        e_time = time.time()
        if state:
            self.log("sent in %s, got (%d): %s" % (logging_tools.get_diff_time_str(e_time - s_time),
                                                   result.get_state(),
                                                   result.get_result()))
        else:
            self.log("some error occured (spent %s): %s" % (logging_tools.get_diff_time_str(e_time - s_time),
                                                            result),
                     logging_tools.LOG_LEVEL_ERROR)
    def _send_to_sge_server(self, act_com):
        self.__send_idx += 1
        send_idx = self.__send_idx
        self.__pending_dict[send_idx] = None
        self.__net_server.add_object(net_tools.tcp_con_object(self._new_tcp_con,
                                                              connect_state_call=self._connect_state_call,
                                                              connect_timeout_call=self._connect_timeout,
                                                              target_host=self.__glob_config["SGE_SERVER"],
                                                              target_port=self.__glob_config.get("SGE_SERVER_PORT", 8009),
                                                              timeout=10,
                                                              bind_retries=1,
                                                              rebind_wait_time=2,
                                                              add_data=(send_idx, "s", str(act_com))))
        while not self.__pending_dict[send_idx]:
            # not beautiful but working
            self.inner_loop(force_wait=True)
        ret_state, ret_value = self.__pending_dict[send_idx]
        return ret_state, ret_value
    def _kill_foreign_pids(self, con_list):
        # killall foreign ips if configured
        if self.__glob_config["BRUTAL_CLEAR_MACHINES"]:
            min_kill_uid = self.__glob_config["MIN_KILL_UID"]
            self.log("Trying to kill all processes with uid >= %d on %s" % (min_kill_uid,
                                                                            logging_tools.get_plural("node", len(con_list))))
            self._collserver_command(dict([(con_entry, ("pskill", "9 %d sge_shepherd,portmap" % (min_kill_uid))) for con_entry in con_list]),
                                     result_type="o")
    def _remove_foreign_ipcs(self, con_list):
        # killall foreign ipcs if configured
        if self.__glob_config["BRUTAL_CLEAR_MACHINES"]:
            min_kill_uid = self.__glob_config["MIN_KILL_UID"]
            self.log("Trying to remove all IPCS-objects with uid >= %d on %s" % (min_kill_uid,
                                                                                 logging_tools.get_plural("node", len(con_list))))
            self._collserver_command(dict([(con_entry, ("ipckill", "%d" % (min_kill_uid))) for con_entry in con_list]),
                                     result_type="o")
    def _decode_umount_result(self, res_dict, **args):
        ok_list, err_list = (res_dict.get("ok_list", []),
                             res_dict.get("err_list", []))
        return "umount result: %d OK%s, %s%s" % (len(ok_list),
                                                 " (%s)" % (", ".join([x[0] for x in ok_list])) if ok_list else "",
                                                 logging_tools.get_plural("problem", len(err_list)),
                                                 " (%s)" % (", ".join([x[0] for x in err_list])) if err_list else "")
    def _umount_nfs_mounts(self, con_list):
        # umounts unneeded mountpoints
        self.log("Trying to umount all unneded NFS-mounts on %s" % (logging_tools.get_plural("node", len(con_list))))
        self._collserver_command(dict([(con_entry, ("umount", "")) for con_entry in con_list]), decode_func=self._decode_umount_result)
    def _check_homedir(self, con_list):
        user_name = self.__env_dict["USER"]
        self.log("Checking reachability of homedir for user %s on %s" % (user_name,
                                                                         logging_tools.get_plural("node", len(con_list))))
        res_dict = self._collserver_command(dict([(con_entry, ("homedir", user_name)) for con_entry in con_list]), result_type="o")
        error_nodes = []
        for key, (res_ok, res_value) in res_dict.iteritems():
            if res_ok:
                if res_value.startswith("ok "):
                    pass
                else:
                    error_nodes.append(key)
            else:
                if type(res_value) == type(()) and res_value[1].lower().count("timeout"):
                    # not really ok ...
                    pass
                else:
                    error_nodes.append(key)
        if error_nodes:
            self.log("no userhome on %s: %s" % (logging_tools.get_plural("node", len(error_nodes)),
                                                logging_tools.compress_list(error_nodes)),
                     logging_tools.LOG_LEVEL_ERROR,
                     do_print=True)
            self._send_tag("disable",
                           error="no homedir",
                           fail_objects=["%s@%s" % (self.__opt_dict["QUEUE"], failed_host) for failed_host in error_nodes])
            self._set_exit_code("homedir reachability", 99)
    def _flight_check(self, flight_type):
        s_time = time.time()
        ping_com = "ping_remote fast_mode=True"
        self.log("starting flight_check %s, ping_com is '%s'" % (flight_type,
                                                                 ping_com))
        
        all_ips = sum([node_stuff["ip_list"] for node_stuff in self.__node_dict.itervalues()], [])
        all_nfs_ips = [node_stuff["ip"] for node_stuff in self.__node_dict.itervalues()]
        # build connection dict
        con_dict = {}
        for node_name in self.__node_list:
            con_dict[node_name] = {"result"  : None,
                                   "retries" : 2,
                                   "ips"     : all_ips}
        self.log(" - %s %s: %s to check" % (logging_tools.get_plural("node", len(self.__node_list)),
                                            logging_tools.compress_list(self.__node_list),
                                            logging_tools.get_plural("IP", len(all_ips))))
        max_pending = self.__glob_config["SIMULTANEOUS_PINGS"]
        ping_packets = self.__glob_config["PING_PACKETS"]
        ping_timeout = self.__glob_config["PING_TIMEOUT"]
        pings_pending = 0
        pending_ids, pending_dict, nodes_waiting = ([], {}, [])
        while True:
            # iterate until all results are set
            # step 1 : send as many pings as needed
            to_send = [key for key, value in con_dict.iteritems() if (value["result"] is None) and (key not in nodes_waiting)]
            send_dict = {}
            while to_send and pings_pending < max_pending:
                #print "sending", to_send, pings_pending, max_pending
                act_node_name = to_send.pop(0)
                send_dict[act_node_name] = (ping_com, "%s %d %.2f" % (",".join(con_dict[act_node_name]["ips"]),
                                                                      ping_packets,
                                                                      ping_timeout))
                pings_pending += ping_packets
            if send_dict:
                act_pend_dict = self._collserver_command(send_dict, 
                                                         only_send=True,
                                                         timeout=ping_timeout + 5)
                nodes_waiting.extend(act_pend_dict.values())
                pending_ids.extend(act_pend_dict.keys())
                for key, value in act_pend_dict.iteritems():
                    # store reference
                    pending_dict[key] = value
            # step 2: wait for pings to return
            self.inner_loop(force_wait=True)
            act_finished = [p_id for p_id in pending_ids if self.__pending_dict[p_id]]
            #print "done", act_finished
            for fin_id in act_finished:
                pending_ids.remove(fin_id)
                pings_pending -= ping_packets
                ret_state, ret_value = self.__pending_dict[fin_id]
                #print "id %d gave:" % (fin_id), ret_state, ret_value
                act_node_name = pending_dict[fin_id]
                nodes_waiting.remove(act_node_name)
                #self.log("got for %s: %s" % (act_node_name, str(self.__pending_dict[fin_id])))
                con_dict[act_node_name]["retries"] -= 1
                con_dict[act_node_name]["result"] = (ret_state, ret_value)
                if not ret_state and con_dict[act_node_name]["retries"]:
                    # we only retry the ping if the connection to the collserver fails
                    con_dict[act_node_name]["result"] = None
            if not [True for key, value in con_dict.iteritems() if not value["result"]]:
                break
        # interpret result
        res_dict = dict([(key, dict([(ip, False) for ip in [self.__node_dict[key]["ip"]] + value["ips"]])) for key, value in con_dict.iteritems()])
        ip_fail_dict, reach_dict = ({}, {})
        for key, value in con_dict.iteritems():
            res_ok, res_stuff = value["result"]
            if res_ok:
                # node itself is ok
                res_dict[key][self.__node_dict[key]["ip"]] = True
                for sub_key, sub_res in res_stuff.iteritems():
                    reach_dict.setdefault(sub_key, {"total"  : 0,
                                                    "actual" : 0,
                                                    "state"  : "ok"})
                    reach_dict[sub_key]["total"] += 1
                    if type(sub_res) == type({}) and sub_res["received"]:
                        res_dict[key][sub_key] = True
                        reach_dict[sub_key]["actual"] += 1
                    else:
                        local_ip = sub_key in self.__node_dict[key]["ip_list"]
                        self.log("unable to contact %s IP %s from node %s%s" % ("local" if local_ip else "remote",
                                                                                sub_key,
                                                                                key,
                                                                                " (result is '%s')" % (sub_res) if type(sub_res) == type("") else ""),
                                    logging_tools.LOG_LEVEL_ERROR)
                        ip_fail_dict.setdefault(sub_key, []).append((key, local_ip))
            else:
                self.log("unable to contact node %s: %s" % (key,
                                                            res_stuff),
                         logging_tools.LOG_LEVEL_ERROR)
        # remove ip_failures 
        #pprint.pprint(res_dict)
        #pprint.pprint(con_dict)
        #pprint.pprint(ip_fail_dict)
        #pprint.pprint(reach_dict)
        # failed ips
        failed_ips = sorted([key for key, value in reach_dict.iteritems() if value["actual"] != value["total"]])
        error_hosts = set()
        if failed_ips:
            for fail_ip in failed_ips:
                ip_dict = reach_dict[fail_ip]
                ip_dict["status"] = "warn" if ip_dict["actual"] else "fail"
            self.log("%s failed: %s" % (logging_tools.get_plural("IP", len(failed_ips)),
                                        ", ".join(["%s (%s)" % (fail_ip, reach_dict[fail_ip]["status"]) for fail_ip in failed_ips])),
                     logging_tools.LOG_LEVEL_WARN)
            error_ips = set([fail_ip for fail_ip in failed_ips if reach_dict[fail_ip]["status"] == "fail"])
            if error_ips:
                error_hosts = set([key for key, value in self.__node_dict.iteritems() if error_ips.intersection(set(value["ip_list"]))])
                self.log("%s: %s (%s: %s)" % (logging_tools.get_plural("error host", len(error_hosts)),
                                              ", ".join(error_hosts),
                                              logging_tools.get_plural("error IP", len(error_ips)),
                                              ", ".join(error_ips)),
                         logging_tools.LOG_LEVEL_ERROR,
                         do_print=True)
                # disable the queues
                self._send_tag("disable",
                               error="connection problem",
                               fail_objects=["%s@%s" % (self.__opt_dict["QUEUE"], failed_host) for failed_host in error_hosts])
                # hold the job
                self._send_tag("hold",
                               error="connection problem",
                               fail_objects=[self.__opt_dict["FULL_JOB_ID"]])
                self._set_exit_code("connection problems", 1)
        e_time = time.time()
        self.log("%s took %s" % (flight_type, logging_tools.get_diff_time_str(e_time - s_time)))
    def _collserver_command(self, con_dict, **args):
        # args:
        # result_type is on of 's' for srv_reply, 'p' for packaged struct or anything else for no interpretation
        # only_send: just send and return immediately with the dict of sender_ids -> target_host
        # timeout: timeout for command
        con_list = con_dict.keys()
        res_type = args.get("result_type", "p")
        self.log("sending command to %s (result type %s): %s" % (logging_tools.get_plural("host", len(con_list)),
                                                                 res_type,
                                                                 logging_tools.compress_list(con_list)))
        disp_list = {}
        for key, value in con_dict.iteritems():
            disp_list.setdefault(value, []).append(key)
        for val in sorted(disp_list.keys()):
            self.log(" - %s to %s: %s" % (str(val),
                                          logging_tools.get_plural("node", len(disp_list[val])),
                                          logging_tools.compress_list(disp_list[val])))
        s_time = time.time()
        pend_list, ip_dict = ([], {})
        for con_ip in con_list:
            self.__send_idx += 1
            send_idx = self.__send_idx
            pend_list.append(send_idx)
            ip_dict[send_idx] = con_ip
            self.__pending_dict[send_idx] = None
            self.__net_server.add_object(net_tools.tcp_con_object(self._new_tcp_con,
                                                                  connect_state_call=self._connect_state_call,
                                                                  connect_timeout_call=self._connect_timeout,
                                                                  target_host=con_ip,
                                                                  target_port=self.__glob_config.get("COLLSERVER_PORT", 2001),
                                                                  timeout=args.get("timeout", 10),
                                                                  bind_retries=1,
                                                                  rebind_wait_time=2,
                                                                  add_data=(send_idx, res_type, "%s %s" % con_dict[con_ip])))
        if args.get("only_send", False):
            return ip_dict
        while True:
            # not beautiful but working
            self.inner_loop(force_wait=True)
            if not [True for p_id in pend_list if not self.__pending_dict[p_id]]:
                break
        # transform results
        for key in pend_list:
            if self.__pending_dict[key][0] == True and args.has_key("decode_func"):
                self.__pending_dict[key] = (True, args["decode_func"](self.__pending_dict[key][1], host=ip_dict[key]))
        ret_dict = dict([(ip_dict[s_idx], self.__pending_dict[s_idx]) for s_idx in pend_list])
        e_time = time.time()
        self.log(" - contacted %s in %s" % (logging_tools.get_plural("address", len(con_list)),
                                            logging_tools.get_diff_time_str(e_time - s_time)))
        # log results
        results = dict([(key, {}) for key in ["ok", "error"]])
        for key, (ok_flag, result) in ret_dict.iteritems():
            if ok_flag:
                if type(result) == type(""):
                    results["ok"].setdefault(result, []).append(key)
                else:
                    results["ok"].setdefault(str(type(result)), []).append(key)
            else:
                results["error"].setdefault(result, []).append(key)
        for res_key in sorted(results.keys()):
            res_struct = results[res_key]
            if res_struct:
                self.log(" - got %s:" % (logging_tools.get_plural("different %s result" % (res_key), len(res_struct.keys()))),
                         logging_tools.LOG_LEVEL_OK if res_key in ["ok"] else logging_tools.LOG_LEVEL_ERROR)
                for sub_res_key in sorted(res_struct.keys()):
                    self.log("   - %s: %s" % (sub_res_key, logging_tools.compress_list(res_struct[sub_res_key])),
                             logging_tools.LOG_LEVEL_OK if res_key in ["ok"] else logging_tools.LOG_LEVEL_ERROR)
        return ret_dict
    # network related calls (lowlevel)
    def _connect_timeout(self, sock):
        # to escape from waiting loop
        self.get_thread_queue().put(("result_error", (sock.get_add_data()[0], -1, "connect timeout")))
        sock.close()
    def _connect_state_call(self, **args):
        if args["state"] == "error":
            send_id, send_type, send_str = args["socket"].get_add_data()
            # to escape from waiting loop
            self.get_thread_queue().put(("result_error", (send_id, -1, "connect timeout")))
    def _new_tcp_con(self, sock):
        return simple_tcp_obj(self.get_thread_queue(), sock.get_add_data())
    def _result_ok(self, (s_id, s_type, res_str)):
        if s_type == "s":
            # srv_command
            try:
                srv_reply = server_command.server_reply(res_str)
            except:
                self.__pending_dict[s_id] = (False, (-1, "error decoding '%s': %s" % (res_str,
                                                                                      process_tools.get_except_info())))
            else:
                self.__pending_dict[s_id] = (True, srv_reply)
        elif s_type == "p":
            # packed struct
            if res_str.startswith("ok "):
                try:
                    res_struct = server_command.net_to_sys(res_str[3:])
                except:
                    self.__pending_dict[s_id] = (False, (-1, "error unpacking '%s': %s" % (res_str,
                                                                                           process_tools.get_except_info())))
                else:
                    self.__pending_dict[s_id] = (True, res_struct)
            else:
                self.__pending_dict[s_id] = (False, (-1, res_str))
        else:
            self.__pending_dict[s_id] = (True, res_str)
    def _result_error(self, (s_id, e_flag, e_cause)):
        self.log("problem for send_id %d: %s (%d)" % (s_id,
                                                      e_cause,
                                                      e_flag),
                 logging_tools.LOG_LEVEL_ERROR)
        self.__pending_dict[s_id] = (False, (e_flag, e_cause))
    # calls to determine the actual runmode
    def is_start_call(self):
        return self.__opt_dict["CALLER_NAME_SHORT"] in ["prologue",
                                                        "lamstart",
                                                        "mvapich2start",
                                                        "pvmstart",
                                                        "pestart"]
    def is_pe_start_call(self):
        return self.__opt_dict["CALLER_NAME_SHORT"] in ["lamstart",
                                                        "pestart",
                                                        "pvmstart",
                                                        "mvapich2start"]
    def is_pe_stop_call(self):
        return self.__opt_dict["CALLER_NAME_SHORT"] in ["lamstop",
                                                        "pestop",
                                                        "pvmstop",
                                                        "mvapich2stop"]
    def is_proepilogue_call(self):
        return self.__opt_dict["CALLER_NAME_SHORT"] in ["prologue",
                                                        "epilogue"]
    def is_pe_call(self):
        return self.__opt_dict["CALLER_NAME_SHORT"] in ["lamstart",
                                                        "pestart",
                                                        "pvmstart",
                                                        "mvapich2start",
                                                        "lamstop",
                                                        "pestop",
                                                        "pvmstop",
                                                        "mvapich2stop"]
    # headers / footers
    def _write_proepi_header(self):
        sep_str = "-" * self.__glob_config["SEP_LEN"]
        self._print(sep_str)
        self._print("Starting %s for job %s, %s at %s" % (self.__opt_dict["CALLER_NAME_SHORT"],
                                                          self.__opt_dict["FULL_JOB_ID"],
                                                          self.get_owner_str(),
                                                          time.ctime(time.time())))
        self.log("writing %s-header for job %s, %s" % (self.__opt_dict["CALLER_NAME_SHORT"],
                                                       self.__opt_dict["FULL_JOB_ID"],
                                                       self.get_owner_str()))
        self.log("Jobname is '%s' in queue '%s'" % (self.__opt_dict["JOB_NAME"],
                                                    self.__opt_dict["QUEUE"]),
                 do_print=True)
    def _write_proepi_footer(self):
        sep_str = "-" * self.__glob_config["SEP_LEN"]
        self.log("writing %s-footer for job %s, return value is %d (%s)" % (self.__opt_dict["CALLER_NAME_SHORT"],
                                                                            self.__opt_dict["FULL_JOB_ID"],
                                                                            self.__return_value,
                                                                            self.get_stat_str(self.__return_value)))
        spent_time = logging_tools.get_diff_time_str(self.__end_time - self.__start_time)
        self._print("%s finished for job %s, status %s, spent %s" % (self.__opt_dict["CALLER_NAME_SHORT"],
                                                                     self.__opt_dict["FULL_JOB_ID"],
                                                                     self.get_stat_str(self.__return_value),
                                                                     spent_time))
        self.log("%s took %s" % (self.__opt_dict["CALLER_NAME"],
                                 spent_time))
        self._print(sep_str)
    def _write_pe_header(self):
        sep_str = "-" * self.__glob_config["SEP_LEN"]
        self._print(sep_str)
        self._print("Starting %s for job %s, %s at %s" % (self.__opt_dict["CALLER_NAME_SHORT"],
                                                          self.__opt_dict["FULL_JOB_ID"],
                                                          self.get_owner_str(),
                                                          time.ctime(time.time())))
        self.log("writing %s-header for job %s, %s" % (self.__opt_dict["CALLER_NAME_SHORT"],
                                                       self.__opt_dict["FULL_JOB_ID"],
                                                       self.get_owner_str()))
    def _write_pe_footer(self):
        sep_str = "-" * self.__glob_config["SEP_LEN"]
        self.log("writing %s-footer for job %s, return value is %d (%s)" % (self.__opt_dict["CALLER_NAME_SHORT"],
                                                                            self.__opt_dict["FULL_JOB_ID"],
                                                                            self.__return_value,
                                                                            self.get_stat_str(self.__return_value)))
        spent_time = logging_tools.get_diff_time_str(self.__end_time - self.__start_time)
        self._print("%s finished for job %s, status %s, spent %s" % (self.__opt_dict["CALLER_NAME_SHORT"],
                                                                     self.__opt_dict["FULL_JOB_ID"],
                                                                     self.get_stat_str(self.__return_value),
                                                                     spent_time))
        self.log("%s took %s" % (self.__opt_dict["CALLER_NAME"],
                                 spent_time))
        self._print(sep_str)
        
        
class my_thread_pool(threading_tools.thread_pool):
    def __init__(self, opt_dict):
        self.__opt_dict = opt_dict
        # init gonfig
        self.__glob_config = configfile.configuration("proepilogue", {"LOG_NAME"              : configfile.str_c_var("proepilogue"),
                                                                      "LOG_DESTINATION"       : configfile.str_c_var("uds:/var/lib/logging-server/py_log"),
                                                                      "MAX_RUN_TIME"          : configfile.int_c_var(60),
                                                                      "SEP_LEN"               : configfile.int_c_var(80),
                                                                      "HAS_MPI_INTERFACE"     : configfile.bool_c_var(True),
                                                                      "MPI_POSTFIX"           : configfile.str_c_var("mp"),
                                                                      "BRUTAL_CLEAR_MACHINES" : configfile.bool_c_var(False),
                                                                      "SIMULTANEOUS_PINGS"    : configfile.int_c_var(128),
                                                                      "PING_PACKETS"          : configfile.int_c_var(5),
                                                                      "PING_TIMEOUT"          : configfile.float_c_var(5.0),
                                                                      "MIN_KILL_UID"          : configfile.int_c_var(110),
                                                                      "UMOUNT_CALL"           : configfile.bool_c_var(True)})
        self._init_log_template()
        threading_tools.thread_pool.__init__(self, "proepilogue", blocking_loop=False)
        self.register_exception("int_error", self._int_error)
        self.register_exception("term_error", self._int_error)
        self.register_func("set_exit_code", self._set_exit_code)
        self.register_func("log", self.log)
        self.register_func("done", self._done)
        self._set_sge_environment()
        self._read_config()
        self._log_arguments()
        self.exit_code = -1
        self.__runtime_exceeded = False
        self.__start_time = time.time()
        self._init_netserver()
        self.__job_thread = self.add_thread(job_thread(self.__glob_config, self.__opt_dict, self.__netserver), start_thread=True).get_thread_queue()
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK, **args):
        if type(what) == type(()):
            what, log_level = what
        if self.__logger:
            self.__logger.log(log_level, what)
        else:
            self.__log_template.log(what, log_level)
        if args.get("do_print", False):
            self._print("%s%s" % ("[%s] " % (logging_tools.get_log_level_str(log_level)) if log_level != logging_tools.LOG_LEVEL_OK else "", what))
    def _print(self, what):
        try:
            print what
        except:
            self.log("cannot print '%s': %s" % (what,
                                                process_tools.get_except_info()),
                     logging_tools.LOG_LEVEL_ERROR)
    
    def set_exit_code(self, exit_code):
        self.__exit_code = exit_code
        self.log("exit_code set to %d" % (self.__exit_code))
    def get_exit_code(self):
        return self.__exit_code
    exit_code = property(get_exit_code, set_exit_code)
    def _set_exit_code(self, ex_code):
        self.exit_code = ex_code
    def _init_netserver(self):
        self.__netserver = net_tools.network_server(timeout=4, log_hook=self.log)
    def _read_config(self):
        # reading the config
        conf_dir = "%s/3rd_party" % (self.__glob_config["SGE_ROOT"])
        if not os.path.isdir(conf_dir):
            self.log("no config_dir %s found, using defaults" % (conf_dir),
                     logging_tools.LOG_LEVEL_ERROR,
                     do_print=True)
        else:
            conf_file = "%s/proepilogue.conf" % (conf_dir)
            if not os.path.isfile(conf_file):
                self.log("no config_file %s found, using defaults" % (conf_file),
                         logging_tools.LOG_LEVEL_ERROR,
                         do_print=True)
                self._print("Copy the following lines to %s :" % (conf_file))
                self._print("")
                self._print("[global]")
                for key in sorted(self.__glob_config.keys()):
                    if not key.startswith("SGE_"):
                        # don't write SGE_* stuff
                        self._print("%s = %s" % (key, str(self.__glob_config[key])))
                self._print("")
            else:
                self.__glob_config.add_config_dict({"CONFIG_FILE" : configfile.str_c_var(conf_file)})
                self.log("reading config from %s" % (conf_file))
                self.__glob_config.parse_file(conf_file)
    def _set_sge_environment(self):
        for v_name, v_src in [("SGE_ROOT", "/etc/sge_root"), ("SGE_CELL", "/etc/sge_cell")]:
            if os.path.isfile(v_src):
                v_val = file(v_src, "r").read().strip()
                self.log("Setting environment-variable '%s' to %s" % (v_name, v_val))
            else:
                self.log("Cannot assign environment-variable '%s', problems ahead ..." % (v_name),
                         logging_tools.LOG_LEVEL_ERROR)
                #sys.exit(1)
            self.__glob_config.add_config_dict({v_name : configfile.str_c_var(v_val, source=v_src)})
        if self.__glob_config.has_key("SGE_ROOT") and self.__glob_config.has_key("SGE_CELL"):
            self.__glob_config.add_config_dict({"SGE_VERSION" : configfile.str_c_var("6", source="intern")})
    def _log_arguments(self):
        out_list = logging_tools.new_form_list()
        for key in sorted(self.__opt_dict.keys()):
            out_list.append([logging_tools.form_entry(key, header="key"),
                             logging_tools.form_entry(self.__opt_dict[key], header="value")])
        for line in str(out_list).split("\n"):
            self.log(line)
    def _init_log_template(self):
        logger, log_template = (None, None)
        try:
            logger = logging_tools.get_logger(self.__glob_config["LOG_NAME"],
                                              self.__glob_config["LOG_DESINATION"],
                                              init_logger=True)
        except:
            log_template = net_logging_tools.log_command(self.__glob_config["LOG_NAME"], thread_safe=True, thread="proepilogue")
            log_template.set_destination(self.__glob_config["LOG_DESTINATION"])
            log_template.set_command_and_send("open_log")
            log_template.set_command("log")
        self.__log_template = log_template
        self.__logger = logger
    def _close_logs(self):
        if self.__log_template:
            self.__log_template.set_command_and_send("close_log")
        else:
            self.__logger.log_command("CLOSE")
    def _int_error(self, err_cause):
        self.log("_int_error() called, cause %s" % (str(err_cause)), logging_tools.LOG_LEVEL_WARN)
        if self["exit_requested"]:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            self["exit_requested"] = True
            self.__netserver.set_timeout(0.1)
            self._break_netserver()
    def _done(self, ret_value):
        self.exit_code = ret_value
        self._int_error("done")
    def _break_netserver(self):
        if self.__netserver:
            self.log("Sending break to netserver")
            self.__netserver.break_call()
    def loop_function(self):
        act_time = time.time()
        run_time = abs(act_time - self.__start_time)
        if run_time > 2 * self.__glob_config["MAX_RUN_TIME"]:
            self.log("terminating myself",
                     logging_tools.LOG_LEVEL_CRITICAL)
            os.kill(self.pid, 9)
        elif run_time > self.__glob_config["MAX_RUN_TIME"]:
            if not self.__runtime_exceeded:
                self.__runtime_exceeded = True
                self.log("max runtime of %s exceeded, exiting" % (logging_tools.get_diff_time_str(self.__glob_config["MAX_RUN_TIME"])),
                        logging_tools.LOG_LEVEL_ERROR)
                self.stop_thread("job")
                self.exit_code = 2
                self._int_error("runtime")
        self.__netserver.step()
    def thread_loop_post(self):
        del self.__netserver
        self.log("execution time: %s" % (logging_tools.get_diff_time_str(time.time() - self.__start_time)))
        self._close_logs()
        #process_tools.delete_pid("collserver/collserver")
        #if self.__msi_block:
        #    self.__msi_block.remove_meta_block()
    
class my_opt_parser(optparse.OptionParser):
    def __init__(self):
        optparse.OptionParser.__init__(self)
        self.__error = False
    def parse(self):
        options, args = self.parse_args()
        if len(args) not in [5, 8]:
            print "Unable to determine execution mode, exiting (%s: %s)" % (logging_tools.get_plural("argument", len(sys.argv)),
                                                                            ", ".join(args))
            self.__error = True
        if self.__error:
            return None
        else:
            opt_dict = self._set_options(options, args)
            return opt_dict
    def _set_options(self, options, args):
        opt_dict = {"CALLER_NAME"       : os.path.basename(sys.argv[0]),
                    "CALLER_NAME_SHORT" : os.path.basename(sys.argv[0]).split(".")[0]}
        if len(args) == 5:
            opt_dict["PROLOGUE"] = True
            # copy pro/epilogue options
            opt_dict["HOST_LONG"] = args.pop(0)
            opt_dict["HOST_SHORT"] = opt_dict["HOST_LONG"].split(".")[0]
            opt_dict["JOB_OWNER"] = args.pop(0)
            opt_dict["JOB_ID"] = args.pop(0)
            opt_dict["JOB_NAME"] = args.pop(0)
            opt_dict["QUEUE"] = args.pop(0)
        elif len(args) == 8:
            opt_dict["PROLOGUE"] = False
            # copy pestart/stop options
            opt_dict["HOST_LONG"] = args.pop(0)
            opt_dict["HOST_SHORT"] = opt_dict["HOST_LONG"].split(".")[0]
            opt_dict["JOB_OWNER"] = args.pop(0)
            opt_dict["JOB_ID"] = args.pop(0)
            opt_dict["JOB_NAME"] = args.pop(0)
            opt_dict["QUEUE"] = args.pop(0)
            opt_dict["PE_HOSTFILE"] = args.pop(0)
            opt_dict["PE"] = args.pop(0)
            opt_dict["PE_SLOTS"] = args.pop(0)
        return opt_dict
    def error(self, what):
        print "Error parsing arguments: %s" % (what)
        self.__error = True


def new_main_code():
    ret_value = 1
    opt_dict = my_opt_parser().parse()
    if opt_dict:
        hs_ok = process_tools.set_handles({"err" : (0, "/var/lib/logging-server/py_err")}, error_only = True)
        my_tp = my_thread_pool(opt_dict)
        my_tp.thread_loop()
        ret_value = my_tp.exit_code
    return ret_value

def main_2():
    global g_config, msi_block
    start_time = time.time()
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hd", ["help"])
    except getopt.GetoptError, bla:
        print "Cannot parse commandline (%s)" % (bla)
        sys.exit(-1)
    #sys.exit(0)
    ret_value = 1
    change_h = 1
    hs_ok = 0
    for opt, arg in opts:
        if opt in ["-h", "--help"]:
            print "Usage: %s [-h|--help] OPTIONS " % (os.path.basename(sys.argv[0]))
            print "where OPTIONS is one or more of:"
            print "   -d       don't change in/out-handles"
            sys.exit(0)
        if opt == "-d":
            change_h = 0
    if change_h:
        hs_ok = process_tools.set_handles({"err" : (0, "/var/lib/logging-server/py_err")}, error_only = 1)
    g_config = configfile.configuration("proepilogue", {"LOG_DIR"                  : configfile.str_c_var("/var/lib/proepilogue"),
                                                        "MPI_POSTFIX"              : configfile.str_c_var("mp"),
                                                        "INFINIBAND_POSTFIX"       : configfile.str_c_var("ib"),
                                                        "QUEUE_POSTFIX"            : configfile.str_c_var("q"),
                                                        "PING_TIMEOUT"             : configfile.float_c_var(10.0),
                                                        "PING_PACKETS"             : configfile.int_c_var(5),
                                                        "COLLSERVER_PORT"          : configfile.int_c_var(2001),
                                                        "SGE_SERVER_PORT"          : configfile.int_c_var(8009),
                                                        "MIN_KILL_UID"             : configfile.int_c_var(110),
                                                        "HAS_MPI_INTERFACE"        : configfile.int_c_var(1),
                                                        "CLEAR_MACHINES"           : configfile.int_c_var(0),
                                                        "CLEAR_EXCLUDE"            : configfile.str_c_var("", info="comma-separated list of queues to exclude from clearing"),
                                                        "KILL_RUNNING_LAM_DAEMONS" : configfile.int_c_var(0),
                                                        "SGE_SERVER"               : configfile.str_c_var("localhost"),
                                                        "MOTHER_SERVER"            : configfile.str_c_var("localhost"),
                                                        "MONITOR_JOBS"             : configfile.int_c_var(1),
                                                        "LAM_START_RETRIES"        : configfile.int_c_var(2),
                                                        "LAM_STOP_RETRIES"         : configfile.int_c_var(2),
                                                        "SIMULTANEOUS_PINGS"       : configfile.int_c_var(64),
                                                        "LOCK_ACQUIRE_WAIT_TIME"   : configfile.int_c_var(2),
                                                        "EXTRA_PATH"               : configfile.str_c_var(""),
                                                        "CPUSET_PE_NAME"           : configfile.str_c_var("cpus")})
    # always try to set sge-vars
    sge_env_log_lines = set_sge_environment()
    if g_config.has_key("SGE_ROOT"):
        g_config.parse_file("%s/3rd_party/%s" % (g_config["SGE_ROOT"],
                                                 CONFIG_FILE_NAME))
    g_config.parse_file("/etc/sysconfig/%s" % (CONFIG_FILE_NAME))
    for src, key, default in [("/etc/motherserver", "MOTHER_SERVER", "NONE"), ("/etc/sge_server", "SGE_SERVER", "localhost")]:
        try:
            val = file(src, "r").read().split("\n")[0].strip()
        except:
            val = default
            logging_tools.my_syslog("error reading %s for key %s, using default %s" % (src, key, val), log_lev=logging_tools.LOG_LEVEL_ERROR)
        g_config.add_config_dict({key : configfile.str_c_var(val, source=src)})
    #print "\n".join(g_config.get_log())
    #print g_config["MIN_KILL_UID"], type(g_config["CLEAR_MACHINES"])
    # init threads
    main_queue = Queue.Queue(200)
    log_queue = Queue.Queue(200)
    log_queue.put(log_message(sge_env_log_lines))
    wait_queues = []
    # init msi_block
    try:
        msi_block = process_tools.meta_server_info("proepilogue-%d" % (os.getpid()))
    except:
        msi_block = None
        msi_error = sys.exc_info()
    else:
        msi_block.add_actual_pid()
        msi_block.set_kill_pids()
        msi_block.save_block()
    threading.Thread(name="loggct_rmsing", target = logging_thread, args=[main_queue, log_queue]).start()
    if msi_block:
        log_queue.put(log_message("initialised msi_block"))
    else:
        log_queue.put(log_message("cannot initialse msi_block: %s" % (process_tools.get_except_info(exc_info=msi_error))))
    comsend_queue = Queue.Queue(200)
    network_queue = Queue.Queue(200)
    wait_queues.append(network_queue)
    # determine execution mode
    num_args = len(args)
    start_name = os.path.basename(sys.argv[0])
    log_queue.put(log_message("found %s: %s" % (logging_tools.get_plural("argument", num_args),
                                                "; ".join(args))))
    task_id = get_task_id(log_queue)
    act_rms = get_mode(start_name, args, num_args)
    if not act_rms:
        log_queue.put(log_message("Unknown execution mode (%d arguments, '%s')" % (num_args, " ".join(args))))
        if g_config.has_key("SGE_ROOT"):
            log_config(log_queue, "%s/3rd_party/%s" % (g_config["SGE_ROOT"],
                                                       CONFIG_FILE_NAME))
    else:
        res_used = get_sge_resources()
        #res_used = None
        user, job_name, queue_name = (args[1], args[3], args[4])
        act_job = job(args[2], task_id, log_queue)
        act_job.set_pe_name(get_pe_name())
        act_job.set_rms(act_rms)
        act_job.set_master_host(args[0])
        act_job.set_job_name(args[3])
        act_job.set_queue_name(args[4])
        try:
            pw_data = pwd.getpwnam(user)
        except KeyError:
            pw_data = None
            u_id, g_id, group = (0, 0, "unknown")
            act_job.log("Error: Unknown user '%s', using ('%s', %d, %d) as (group, uid, gid)" % (user, group, u_id, g_id))
        else:
            u_id = pw_data[2]
            g_id = pw_data[3]
            try:
                grp_data = grp.getgrgid(g_id)
            except KeyError:
                group = "unknown"
                job.log("Error: Unknown group-id %d for user '%s', using %s as group" % (g_id, user, group))
            else:
                group = grp_data[0]
        act_job.set_user_group(user, group, u_id, g_id)
        log_queue.put(internal_message((u_id, g_id)))
        if os.environ.has_key("JOB_SCRIPT"):
            parse_script_variables(os.environ["JOB_SCRIPT"], log_queue, act_job)
        act_env = get_environment()
        if act_rms.get_exec_mode() in ["p", "ps", "ls", "vs", "mvs"]:
            log_environment(act_job, act_env)
            log_resources(act_job)
        if g_config.get("TRIGGER_ERROR", False):
            trigger_error = 2/0
        if g_config.get("EXTRA_WAIT", 0):
            time.sleep(int(g_config["EXTRA_WAIT"]))
        threading.Thread(name="network_thread", target = network_thread, args=[main_queue, log_queue, network_queue, comsend_queue, act_job]).start()
        threading.Thread(name="comsend_thread", target = comsend_thread, args=[main_queue, log_queue, comsend_queue, network_queue, act_job]).start()
        act_job.log("found %d arguments: %s" % (num_args, "; ".join(args)))
        if msi_block:
            act_job.log("initialised msi_block")
        else:
            act_job.log("cannot initialse msi_block: %s (%s)" % (str(msi_error[0]),
                                                                 str(msi_error[1])))
        if act_job.get_rms().is_primary_mode():
            if g_config.has_key("SGE_ROOT"):
                act_job.log_config("%s/3rd_party/%s" % (g_config["SGE_ROOT"],
                                                        CONFIG_FILE_NAME))
        if act_rms.get_exec_mode() in ["p", "e"]:
            act_job.write_pe_header(act_job)
        else:
            act_job.write_mpi_header(act_job)
        if act_rms.get_exec_mode() == "p":
            # prologue
            ret_value = prologue(comsend_queue, act_rms, act_job)
        elif act_rms.get_exec_mode() == "e":
            # epilogue
            ret_value = epilogue(comsend_queue, act_rms, act_job, res_used, act_env)
        else:
            # only used for SGE
            ret_value = modify_hostfile(comsend_queue, act_rms, act_job)
        # create job_script for starter
        if act_rms.get_exec_mode() in ["p"]:
            create_wrapper_script(act_rms, act_job, act_env)
        elif act_rms.get_exec_mode() in ["e"]:
            delete_wrapper_script(act_rms, act_job, act_env)
        end_time = time.time()
        diff_time = end_time - start_time
        if act_rms.get_exec_mode() in ["p", "e"]:
            act_job.write_pe_footer(act_job, diff_time, ret_value)
        else:
            act_job.write_mpi_footer(act_job, diff_time, ret_value)
        # stop comsend-thread
        comsend_queue.put(internal_message("exit"))
        while True:
            it = main_queue.get()
            if it.mes_type == "I":
                if it.arg == "exiting":
                    log_queue.put(log_message("Thread %s exited" % (it.thread)))
                    break
    #time.sleep(30)
    if msi_block:
        log_queue.put(log_message("will remove meta-block when finished"))
    nthreads = len(wait_queues)
    for wq in wait_queues:
        wq.put(internal_message("exit"))
    while nthreads:
        it = main_queue.get()
        if it.mes_type == "I":
            if it.arg == "exiting":
                nthreads -= 1
                log_queue.put(log_message("Thread %s exited" % (it.thread)))
    log_queue.put(internal_message("exit"))
    while True:
        it = main_queue.get()
        if it.mes_type == "I":
            if it.arg == "exiting":
                break
    if change_h:
        if hs_ok:
            process_tools.handles_write_endline(error_only = 1)
    if msi_block:
        msi_block.remove_meta_block()
    return ret_value
    
if __name__ == "__main__":
    if NEW_CODE_OK:
        # check for deny-file for testing
        act_dir = os.path.dirname(sys.argv[0])
        if os.path.isfile("%s/NEW_PE_DENY" % (act_dir)):
            if os.uname()[1] in file("%s/NEW_PE_DENY" % (act_dir), "r").read().split("\n"):
                new_CODE_OK = False
    if NEW_CODE_OK:
        ret_v = new_main_code()
    else:
        loc_dir = "/usr/local/sbin/"
        script_name = os.path.basename(sys.argv[0])
        loc_file = "%s/%s" % (loc_dir, script_name)
        # check for proepilogue.py in /usr/local/sbin (to test local proepilogue.py's)
        if sys.argv[0] != loc_file and os.path.isfile(loc_file):
            logging_tools.my_syslog("starting local version of proepilogue.py (mode: %s)" % (script_name))
            os.execv(loc_file, sys.argv)
        ret_v = main()
    sys.exit(ret_v)
