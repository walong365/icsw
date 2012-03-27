#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008,2009,2011 Andreas Lang-Nevyjel, init.at
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

import sys
import copy
import process_tools
import commands
import os
import getopt
import re
import configfile
import os.path
import socket
import time
import Queue
import threading
import logging_tools
import mysql_tools
import MySQLdb
import marshal
import cPickle
import mail_tools
import pwd
import grp
import pprint
import server_command
import net_tools
import threading_tools
import uuid_tools
import sge_tools
import config_tools
# import hm_classes for mvect_entry
sys.path.append("/usr/local/sbin")
import hm_classes

#from sge_server_messages import *

SERVER_CHECK_PORT = 8009
SQL_ACCESS = "cluster_full_access"

# ------------------- connection objects ------------------------------
class new_tcp_con(net_tools.buffer_object):
    # connection object for rrd-server
    def __init__(self, sock, src, recv_queue, log_queue):
        #print "Init %s (%s) from %s" % (con_type, con_class, str(src))
        self.__src_host, self.__src_port = src
        self.__recv_queue = recv_queue
        self.__log_queue = log_queue
        net_tools.buffer_object.__init__(self)
        self.__init_time = time.time()
        self.__in_buffer = ""
    def __del__(self):
        pass
    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        self.__log_queue.put(("log", (threading.currentThread().getName(), what, level)))
    def get_src_host(self):
        return self.__src_host
    def get_src_port(self):
        return self.__src_port
    def add_to_in_buffer(self, what):
        self.__in_buffer += what
        p1_ok, what = net_tools.check_for_proto_1_header(self.__in_buffer)
        if p1_ok:
            self.__decoded = what
            try:
                srv_com = server_command.server_command(self.__decoded)
            except:
                self.__log_str = "str_com %s" % (self.__decoded)
            else:
                self.__log_str = "srv_com %s" % (srv_com.get_command())
                self.__decoded = srv_com
            self.__recv_queue.put(("con", self))
    def add_to_out_buffer(self, what, log_str=""):
        self.lock()
        if log_str:
            self.__log_str = log_str
        if self.socket:
            self.out_buffer = net_tools.add_proto_1_header(what)
            self.socket.ready_to_send()
        else:
            self.log("timeout, other side has closed connection")
        self.unlock()
    def out_buffer_sent(self, d_len):
        if d_len == len(self.out_buffer):
            self.__recv_queue = None
            self.log("%s from %s (port %d) took %s (%s)" % (self.__log_str,
                                                            self.__src_host,
                                                            self.__src_port,
                                                            logging_tools.get_diff_time_str(abs(time.time() - self.__init_time)),
                                                            logging_tools.get_plural("byte", len(self.out_buffer))))
            self.close()
        else:
            self.out_buffer = self.out_buffer[d_len:]
            #self.socket.ready_to_send()
    def get_decoded_in_str(self):
        return self.__decoded
    def report_problem(self, flag, what):
        self.close()

class node_con_obj(net_tools.buffer_object):
    # connects to a foreign node
    def __init__(self, pj_struct, dst_host, dst_com):
        self.__pj_struct = pj_struct
        self.__dst_host = dst_host
        self.__dst_com = dst_com
        net_tools.buffer_object.__init__(self)
    def __del__(self):
        pass
    def setup_done(self):
        self.add_to_out_buffer(net_tools.add_proto_1_header(self.__dst_com, True))
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
            self.__pj_struct._host_ok(self.__dst_host, self.__dst_com, p1_data)
            self.delete()
    def report_problem(self, flag, what):
        self.__pj_struct._host_error(self.__dst_host, self.__dst_com)
        self.delete()
# ------------------- connection objects ------------------------------

class all_jobs(object):
    def __init__(self, log_queue, glob_config, loc_config):
        self.__log_queue = log_queue
        self.__glob_config, self.__loc_config = (glob_config, loc_config)
        self.__job_dict = {}
        self.__lock = threading.RLock()
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__log_queue.put(("log", (threading.currentThread().getName(), what, lev)))
    def job_log(self, job, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__log_queue.put(("special_log", (threading.currentThread().getName(), what, lev, job.log_path)))
    def lock(self):
        self.__lock.acquire()
    def release(self):
        self.__lock.release()
    def get_glob_config(self):
        return self.__glob_config
    def get_loc_config(self):
        return self.__loc_config
    def keys(self):
        return self.__job_dict.keys()
    def has_key(self, job_uid):
        return self.__job_dict.has_key(job_uid)
    def __delitem__(self, job_uid):
        self.lock()
        if self.__job_dict.has_key(job_uid):
            job_log_path = self.__job_dict[job_uid].log_path
            del self.__job_dict[job_uid]
            self.log("Remove job '%s' from job_dict, %s left" % (job_uid,
                                                                 logging_tools.get_plural("job", len(self.__job_dict.keys()))))
            self.__log_queue.put(("remove_handle", job_log_path))
        else:
            self.log("Cannot remove job '%s' from job_dict (not found)" % (job_uid),
                     logging_tools.LOG_LEVEL_WARN)
        self.release()
    def __getitem__(self, job_uid):
        return self.__job_dict[job_uid]
    def __setitem__(self, job_uid, new_job):
        self.__job_dict[job_uid] = new_job
        self.log("Added job %s to job_dict (contains now %s)" % (job_uid,
                                                                 logging_tools.get_plural("job", len(self.__job_dict.keys()))))
    def __del__(self):
        print "* del all_jobs *"
        
class cache_object(object):
    def __init__(self, log_queue, pos_ttl=3600, neg_ttl=0, **args):
        self.__log_queue = log_queue
        self.__cache = {}
        self.__cache_timestamps = {}
        self.__pos_ttl, self.__neg_ttl = (pos_ttl, neg_ttl)
        self.set_cache_miss_object(args.get("cache_miss_object", None))
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__log_queue.put(("log", (threading.currentThread().getName(), what, lev)))
    def get_cache_size(self):
        return len(self.__cache.keys())
    def set_cache_miss_object(self, def_co):
        self.__cache_miss_object = def_co
    def get_cache_object(self, dc, key):
        act_time = time.time()
        if self.__cache.has_key(key):
            if self.__pos_ttl and abs(self.__cache_timestamps[key] - act_time) > self.__pos_ttl:
                check = True
            else:
                check = False
                co = self.__cache[key]
        else:
            check = True
        if check:
            try:
                act_co = self.get_object(dc, key)
            except IndexError:
                if self.__cache.has_key(key):
                    del self.__cache[key]
                    del self.__cache_timestamps[key]
                co = self.__cache_miss_object
            else:
                self.__cache[key] = act_co
                self.__cache_timestamps[key] = act_time
                co = act_co
        return co
    
def net_to_sys(in_val):
    try:
        result = cPickle.loads(in_val)
    except:
        try:
            result = marshal.loads(in_val)
        except:
            raise ValueError
    return result

def sys_to_net(in_val):
    return cPickle.dumps(in_val)

class error(Exception):
    def __init__(self, value = None):
        self.value = value
    def __str__(self):
        return str(self.value)
    def get_value(self):
        return self.value

class term_error(error):
    def __init__(self):
        error.__init__(self)
    
class alarm_error(error):
    def __init__(self):
        error.__init__(self)
    
class stop_error(error):
    def __init__(self):
        error.__init__(self)
    
class int_error(error):
    def __init__(self):
        error.__init__(self)

class check_exc(error):
    def __init__(self, val = ()):
        error.__init__(self, val)

class hup_error(error):
    def __init__(self):
        pass
    
def call_command(command, log_com=None):
    start_time = time.time()
    stat, out = commands.getstatusoutput(command)
    end_time = time.time()
    log_lines = ["calling '%s' took %s, result (stat %d) is %s (%s)" % (command,
                                                                        logging_tools.get_diff_time_str(end_time - start_time),
                                                                        stat,
                                                                        logging_tools.get_plural("byte", len(out)),
                                                                        logging_tools.get_plural("line", len(out.split("\n"))))]
    if log_com:
        for log_line in log_lines:
            log_com(" - %s" % (log_line))
        if stat:
            for log_line in out.split("\n"):
                log_com(" - %s" % (log_line))
        return stat, out
    else:
        if stat:
            # append output to log_lines if error
            log_lines.extend([" - %s" % (line) for line in out.split("\n")])
        return stat, out, log_lines

def get_task_id(t_id):
    if t_id:
        if type(t_id) == type(0) or t_id.isdigit():
            return int(t_id)
        else:
            return 0
    else:
        return 0
    
class sge_project_cache(cache_object):
    def __init__(self, log_queue):
        cache_object.__init__(self, log_queue, 0, 0)
        self.set_cache_miss_object(0)
    def get_object(self, dc, name):
        dc.execute("SELECT s.sge_project_idx FROM sge_project s WHERE s.name=%s", name)
        if dc.rowcount:
            return dc.fetchone()["sge_project_idx"]
        else:
            self.log("Trying to get project info for project '%s'" % (name))
            stat, out = call_command("qconf -sprj %s" % (name), self.log)
            if stat:
                self.log("Cannot parse sge-project '%s'..." % (name), logging_tools.LOG_LEVEL_ERROR)
                raise IndexError
            else:
                out_d = dict([y for y in [x.strip().split(None, 1) for x in out.split("\n")] if len(y) > 1])
                if not out_d.has_key("name"):
                    out_d = {"name"    : "None",
                             "oticket" : 0,
                             "fshare"  : 0}
                    self.log("out_d has no 'name' key, using NONE (requested: %s)" % (name))
                dc.execute("INSERT INTO sge_project SET name=%s, oticket=%s, fshare=%s", (out_d["name"],
                                                                                          int(out_d["oticket"]),
                                                                                          int(out_d["fshare"])))
                self.log("Inserted sge_project '%s' into database (oticket %d, fshare %d)" % (out_d["name"], int(out_d["oticket"]), int(out_d["fshare"])))
                return dc.insert_id()

class sge_user_cache(cache_object):
    def __init__(self, log_queue):
        cache_object.__init__(self, log_queue, 0, 0)
        self.set_cache_miss_object(0)
    def get_object(self, dc, name):
        dc.execute("SELECT s.sge_user_idx FROM sge_user s WHERE s.name=%s", name)
        if dc.rowcount:
            self.log("fetched user '%s' from db" % (name))
            return dc.fetchone()["sge_user_idx"]
        else:
            stat, out = call_command("qconf -suser %s" % (name), self.log)
            if stat:
                self.log("Cannot parse sge-user '%s'..." % (name), logging_tools.LOG_LEVEL_ERROR)
                raise IndexError
            else:
                out_d = dict([y for y in [x.strip().split(None, 1) for x in out.split("\n")] if len(y) > 1])
                if out_d.has_key("name") and out_d.has_key("oticket") and out_d.has_key("fshare"):
                    dc.execute("INSERT INTO sge_user SET name=%s, oticket=%s, fshare=%s", (out_d["name"],
                                                                                           int(out_d["oticket"]),
                                                                                           int(out_d["fshare"])))
                    self.log("Inserted sge_user '%s' into database (oticket %d, fshare %d)" % (out_d["name"], int(out_d["oticket"]), int(out_d["fshare"])))
                    return dc.insert_id()
    
class sge_userlist_cache(cache_object):
    def __init__(self, log_queue):
        cache_object.__init__(self, log_queue, 0, 0)
        self.set_cache_miss_object(0)
        self.__sut_cache = sge_userlist_type_cache(log_queue)
    def get_object(self, dc, name_t):
        # name_t is a tuple: (name, ul_type)
        name, ul_type = name_t
        dc.execute("SELECT s.sge_userlist_idx FROM sge_userlist s WHERE s.name=%s", name)
        if dc.rowcount:
            self.log("fetched userlist '%s' from db" % (name))
            return dc.fetchone()["sge_userlist_idx"]
        else:
            stat, out = call_command("qconf -su %s" % (name), self.log)
            if stat:
                self.log("Cannot parse sge-userlist '%s'..." % (name), logging_tools.LOG_LEVEL_ERROR)
                raise IndexError
            else:
                out_d = dict([y for y in [x.strip().split(None, 1) for x in out.split("\n")] if len(y) > 1])
                ul_type_idx = self.__sut_cache.get_cache_object(dc, ul_type)
                if ul_type_idx:
                    dc.execute("INSERT INTO sge_userlist SET name=%s, oticket=%s, fshare=%s", (out_d["name"],
                                                                                               int(out_d["oticket"]),
                                                                                               int(out_d["fshare"])))
                    self.log("Inserted sge_userlist '%s' into database (type '%s', oticket %d, fshare %d)" % (ul_type, out_d["name"], int(out_d["oticket"]), int(out_d["fshare"])))
                    idx = dc.insert_id()
                    dc.execute("INSERT INTO sge_ul_ult SET sge_userlist=%d, sge_userlist_type=%d" % (idx, ul_type_idx))
                    return idx
                else:
                    self.log("Cannot add sge_userlist '%s'" % (name), logging_tools.LOG_LEVEL_ERROR)
                    raise IndexError

class sge_userlist_type_cache(cache_object):
    def __init__(self, log_queue):
        cache_object.__init__(self, log_queue, 0, 0)
        self.set_cache_miss_object(0)
    def get_object(self, dc, name):
        dc.execute("SELECT s.sge_userlist_type_idx FROM sge_userlist_type s WHERE s.name=%s", name)
        if dc.rowcount:
            self.log("fetched userlist_type '%s' from db" % (name))
            return dc.fetchone()["sge_userlist_type_idx"]
        else:
            dc.execute("INSERT INTO sge_userlist_type SET name=%s", name)
            self.log("Inserted sge_userlist_type '%s' into database" % (name))
            return dc.insert_id()

class sge_queue_cache(cache_object):
    def __init__(self, log_queue, glob_config):
        self.__glob_config = glob_config
        cache_object.__init__(self, log_queue, 0, 0)
        self.set_cache_miss_object(None)
    def get_object(self, dc, name):
        dc.execute("SELECT s.* FROM sge_queue s WHERE s.queue_name=%s", name)
        if dc.rowcount:
            self.log("fetched queue '%s' from db" % (name))
            out_d = dc.fetchone()
        else:
            self.log("created new queue '%s'" % (name))
            dc.execute("INSERT INTO sge_queue SET queue_name=%s", name)
            dc.execute("SELECT * FROM sge_queue WHERE sge_queue_idx=%d" % (dc.insert_id()))
            out_d = dc.fetchone()
        return out_d

class sge_host_cache(cache_object):
    def __init__(self, log_queue, glob_config):
        self.__glob_config = glob_config
        cache_object.__init__(self, log_queue, 0, 0)
        self.set_cache_miss_object(None)
    def get_object(self, dc, name):
        dc.execute("SELECT s.* FROM sge_host s WHERE s.host_name=%s", name)
        if dc.rowcount:
            self.log("fetched host '%s' from db" % (name))
            out_d = dc.fetchone()
        else:
            # check for device reference
            dc.execute("SELECT d.device_idx FROM device d WHERE d.name=%s", name)
            if dc.rowcount:
                dev_idx = dc.fetchone()["device_idx"]
            else:
                dev_idx = 0
            self.log("created new host '%s' (dev_idx is %d)" % (name,
                                                                dev_idx))
            dc.execute("INSERT INTO sge_host SET host_name=%s, device=%s", (name,
                                                                            dev_idx))
            dc.execute("SELECT * FROM sge_host WHERE sge_host_idx=%d" % (dc.insert_id()))
            out_d = dc.fetchone()
        return out_d
    
class queue(object):
    def __init__(self, queue_name, log_queue, queue_info, glob_config):
        self.__glob_config = glob_config
        #print j_dict
        try:
            self.sge_queue_idx = queue_info["sge_queue_idx"]
        except:
            print "***", queue_name, queue_info
            raise KeyError
        if queue_info["host_queue"]:
            self.__q_type_str, self.host_queue = ("SGE6.0 Hostqueue", 1)
        else:
            if self.__glob_config["SGE_VERSION"] == 6:
                self.__q_type_str, self.host_queue = ("SGE6.%d Clusterqueue" % (self.__glob_config["SGE_RELEASE"]), 0)
            else:
                self.__q_type_str, self.host_queue = ("SGE5.x Queue", 1)
        self.queue_name = queue_info["queue_name"]
        self.host_name = queue_info["host_name"]
        self.device = queue_info["device"]
    def get_info(self):
        if self.sge_queue_idx:
            return "%s %s%s" % (self.__q_type_str, self.queue_name, self.host_queue and "@%s" % (self.host_name) or "")
        else:
            return "unknown queue"
    def log(self, sql_queue, what):
        sql_queue.put(sql_thread_message(("IS", "sge_queue_log", "sge_queue=%s, log_str=%s", (self.sge_queue_idx, what))))
                            
class job(object):
    def __init__(self, aj_struct, job_dict, dc, queue_dict):
        self.__aj_struct = aj_struct
        self.job_host, self.full_job_host = ("unknown", "unknown")
        #print j_dict
        self.job_uid = job_dict["job_id"]
        self.__queue_dict = queue_dict
        dc.execute("SELECT * FROM sge_job WHERE job_uid='%s' ORDER BY sge_job_idx DESC" % (self.job_uid))
        if dc.rowcount:
            job_info = dc.fetchone()
            self.sge_job_idx = job_info["sge_job_idx"]
            self.job_uid = job_info["job_uid"]
            self.jobname = job_info["jobname"]
            self.jobnum = job_info["jobnum"]
            self.taskid = job_info["taskid"]
            self.log_path = job_info["log_path"] or "jobs/%s" % (self.job_uid)
        else:
            self.sge_job_idx = 0
            self.jobname = job_dict.get("job_name", "unknown")
            self.jobnum = int(job_dict.get("job_num", 0))
            self.taskid = get_task_id(job_dict.get("task_id", None))
            self.log_path = (time.strftime("jobs/%Y/%m/%d/%%s")) % (self.job_uid)
        if not self.sge_job_idx:
            # set owner and group
            try:
                gid_name = grp.getgrgid(job_dict["gid"])[0]
            except:
                gid_name = "unknown"
            try:
                uid_name = pwd.getpwuid(job_dict["uid"])[0]
            except:
                uid_name = "unknown"
            dc.execute("INSERT INTO sge_job SET job_uid=%s, jobname=%s, jobnum=%s, taskid=%s, jobowner=%s, jobgroup=%s, log_path=%s", (self.job_uid,
                                                                                                                                       self.jobname,
                                                                                                                                       self.jobnum,
                                                                                                                                       self.taskid,
                                                                                                                                       uid_name,
                                                                                                                                       gid_name,
                                                                                                                                       self.log_path))
            self.sge_job_idx = dc.insert_id()
            self.log("created job in DB (db_idx is %d)" % (self.sge_job_idx))
        else:
            self.log("resurrected job from DB (db_idx is %d)" % (self.sge_job_idx))
        self.__file_watch_dict = {}
        self._init_settings()
    def _init_settings(self):
        self.__value_dict = {}
        self.settings_ok = False
        self["stdout_path"] = ""
        self["stderr_path"] = ""
    def __setitem__(self, key, value):
        self.log("setting %s to '%s'" % (key, value))
        self.__value_dict[key] = value
    def get(self, key, default):
        return self.__value_dict.get(key, default)
    def __getitem__(self, key):
        return self.__value_dict[key]
    def _get_settings(self):
        gs_com = "%s/bin/%s/qstat -j %s" % (self.__aj_struct.get_glob_config()["SGE_ROOT"],
                                            self.__aj_struct.get_glob_config()["SGE_ARCH"],
                                            self.job_uid)
        self.log("trying to get settings via %s" % (gs_com))
        # parse output of qstat -j JOB and extract place of stdout / stderr
        stat, out, log_lines = call_command(gs_com)
        for log_line in log_lines:
            self.log(log_line, stat and logging_tools.LOG_LEVEL_ERROR or logging_tools.LOG_LEVEL_OK)
        if not stat:
            out_dict = dict([(key.strip(), value.strip()) for key, value in [out_line.strip().split(":", 1) for out_line in out.split("\n") if out_line.count(":")]])
            self.log("found %s for job" % (logging_tools.get_plural("key", len(out_dict.keys()))))
            self["owner"] = out_dict["owner"]
            if out_dict.has_key("job-array tasks"):
                stdout_path = out_dict.get("stdout_path_list", "$JOB_NAME.o$JOB_ID.$TASK_ID")
                stderr_path = out_dict.get("stderr_path_list", "$JOB_NAME.e$JOB_ID.$TASK_ID")
            else:
                stdout_path = out_dict.get("stdout_path_list", "$JOB_NAME.o$JOB_ID")
                stderr_path = out_dict.get("stderr_path_list", "$JOB_NAME.e$JOB_ID")
            self["stdout_path"] = self._var_replace(stdout_path, out_dict)
            self["stderr_path"] = self._var_replace(stderr_path, out_dict)
            self["cwd"] = out_dict.get("cwd", "/tmp")
            if self["stdout_path"]:
                self.settings_ok = True
    def _var_replace(self, path_v, var_dict):
        #pprint.pprint(var_dict)
        while True:
            if path_v.startswith("NONE:"):
                path_v = path_v[5:]
            else:
                break
        for var_name, var_value in [("$HOME"    , var_dict.get("sge_o_home", "NO_SGE_O_HOME")),
                                    ("$USER"    , var_dict["owner"]),
                                    ("$JOB_ID"  , var_dict["job_number"]),
                                    ("$JOB_NAME", var_dict["job_name"]),
                                    ("$HOSTNAME", self.full_job_host),
                                    ("$TASK_ID" , str(self.taskid))]:
            path_v = path_v.replace(var_name, var_value)
        if not path_v.startswith("/"):
            path_v = "%s/%s" % (var_dict["sge_o_workdir"], path_v)
        return path_v
    def get_datetime_str(self):
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    def db_log(self, what, log_level=logging_tools.LOG_LEVEL_OK, **args):
        #self.__queue_dict["sql_queue"].put(("insert_set", ("sge_log", "sge_job=%s, log_str=%s", (self.sge_job_idx, what))))
        self.__queue_dict["node_queue"].put(("job_log", (self.sge_job_idx,
                                                         args.get("queue_name", ""),
                                                         args.get("host_name", ""),
                                                         what,
                                                         log_level)))
        self.log(what)
    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        self.__aj_struct.job_log(self, what, level)
    def set_job_host(self, jh):
        self.job_host = jh
    def set_full_job_host(self, jh):
        self.full_job_host = jh
    def set_file_watch_content(self, fw_id, f_name, f_content, f_update):
        self.log("setting content of file_watch_id %s (name %s, len %s, update_time is %d)" % (fw_id,
                                                                                               f_name,
                                                                                               logging_tools.get_size_str(len(f_content), long_version=True),
                                                                                               f_update))
        self.__file_watch_dict[fw_id] = {"name"    : f_name,
                                         "content" : f_content,
                                         "update"  : f_update}
    def get_filewatch_info(self):
        return self.__file_watch_dict
    def add_event(self, dc, command, job_dict):
        if command == "job_start":
            self.set_job_host(job_dict.get("host", "unknown"))
            if job_dict.has_key("full_host"):
                self.set_full_job_host(job_dict["full_host"])
            else:
                self.set_full_job_host("%s.%s" % (job_dict.get("host", "unknown"), socket.getfqdn().split(".", 1)[1]))
            self.db_log("starting job in queue %s (full_host %s, host %s)" % (job_dict["queue_name"],
                                                                              self.full_job_host,
                                                                              self.job_host),
                        queue_name=job_dict["queue_name"],
                        host_name=self.job_host)
            # add new sge_job_run line
            self.__queue_dict["sql_queue"].put(("insert_set", ("sge_job_run", "sge_job=%s, masterq=%s, start_time=%s", (self.sge_job_idx,
                                                                                                                        job_dict["queue_name"],
                                                                                                                        self.get_datetime_str()))))
            self._get_settings()
        elif command == "job_stop":
            self.db_log("job ends in queue %s (host %s)" % (job_dict["queue_name"], job_dict.get("host", "uknown")),
                        queue_name=job_dict["queue_name"],
                        host_name=job_dict.get("host", ""))
            dc.execute("SELECT s.sge_job_run_idx FROM sge_job_run s WHERE s.sge_job=%d ORDER BY s.sge_job_run_idx DESC" % (self.sge_job_idx))
            if dc.rowcount:
                sjr_idx = dc.fetchone()["sge_job_run_idx"]
                self.__queue_dict["sql_queue"].put(("update", ("sge_job_run", "end_time=%s WHERE sge_job_run_idx=%s", (self.get_datetime_str(),
                                                                                                                       sjr_idx))))
            else:
                # no job_run found, log ...
                pass
            self.__queue_dict["mon_queue"].put(("check_job_accounting_delayed", (self.sge_job_idx, self.job_uid)))
        elif command in ["pe_start", "pe_stop"]:
            self.db_log("%s for pe %s (%d queues)" % (command, job_dict.get("pe_name", "UNKNOWN"), len(job_dict["queue_list"])))
            dc.execute("SELECT s.sge_job_run_idx FROM sge_job_run s WHERE s.sge_job=%d ORDER BY s.sge_job_run_idx DESC" % (self.sge_job_idx))
            if dc.rowcount:
                sjr_idx = dc.fetchone()["sge_job_run_idx"]
                if command == "pe_start":
                    # set pe-info
                    dc.execute("UPDATE sge_job_run SET granted_pe=%s, slots=%s WHERE sge_job_run_idx=%s", (job_dict["pe_name"],
                                                                                                           len(job_dict["queue_list"]),
                                                                                                           sjr_idx))
                    hn_dict = {}
                    for h_rec in job_dict["queue_list"]:
                        hn_dict.setdefault(h_rec, {"idx" : 0,
                                                   "num" : 0})["num"] += 1
                    dc.execute("SELECT d.device_idx, d.name FROM device d WHERE (%s)" % (" OR ".join(["d.name='%s'" % (x) for x in hn_dict.keys()])))
                    for db_rec in dc.fetchall():
                        hn_dict[db_rec["name"]]["idx"] = db_rec["device_idx"]
                    for name, stuff in hn_dict.iteritems():
                        self.__queue_dict["sql_queue"].put(("insert_value", ("sge_pe_host", "0, %s, %s, %s, %s, null", (sjr_idx,
                                                                                                                        stuff["idx"],
                                                                                                                        name,
                                                                                                                        stuff["num"]))))
        else:
            self.log("unknown event '%s'" % (command),
                     logging_tools.LOG_LEVEL_WARN)
            
def sec_to_time(secs):
    c_dict = {"d" : 3600 * 24,
              "h" : 3600,
              "m" : 60,
              "s" : 1}
    ret_f = []
    used = False
    for name in ["d", "h", "m", "s"]:
        val = c_dict[name]
        if name == "h":
            used = True
        iv = int(secs/val)
        if iv > 0 or used:
            used = True
            ret_f.append("%d" % (iv))
            secs -= val*iv
    return ":".join(ret_f)

# def logging_thread(m_queue, log_queue, msi_block):
#     my_name = threading.currentThread().getName()
#     mypid = os.getpid()
#     log_queue.put(log_ok_message("proc %d: logging-thread for sge-server is now awake" % (mypid)))
#     process_tools.append_pids("sge-server/sge-server")
#     if msi_block:
#         msi_block.add_actual_pid()
#         msi_block.save_block()
#     root = g_config["LOG_DIR"]
#     if not os.path.isdir(root):
#         try:
#             os.makedirs(root)
#         except OSError:
#             # we have to write to syslog
#             log_queue.put(log_error_message("Unable to create '%s' directory" % (root), 5))
#         else:
#             pass
#     log_dict = {}
#     for log_id, log_name, log_type in [("n", "log"        , "f"),
#                                        ("d", "log_disable", "f"),
#                                        ("e", "log_enable" , "f"),
#                                        ("j", "job_check"  , "d")]:
#         if log_type == "d":
#             glog_dir = "%s/%s" % (root, log_name)
#             if not os.path.isdir(glog_dir):
#                 try:
#                     os.makedirs(glog_dir)
#                 except OSError:
#                     log_queue.put(log_error_message("Unable to create '%s' directory" % (glog_dir), 5))
#                     glog_dir = root
#             glog_name = "%s/log" % (glog_dir)
#         else:
#             glog_name = "%s/%s" % (root, log_name)
#         log_h = logging_tools.logfile(glog_name)
#         log_h.write("-" * 50, header = 0)
#         log_h.write("(%s) Opening log %s" % (my_name, log_name))
#         log_dict[log_id] = log_h
#     while True:
#         it = log_queue.get()
#         if it.m_type == "I":
#             if it.arg == "exit":
#                 break
#             else:
#                 log_dict["n"].write("(%s) Got unknown internal message: %s" % (my_name, it.arg))
#         elif it.m_type == "L":
#             arg, level, log_ids = it.arg
#             for log_id in log_ids:
#                 if log_id.endswith("/"):
#                     new_log_dir, new_log_name = (log_id, "log")
#                 else:
#                     new_log_dir, new_log_name = (os.path.dirname(log_id), os.path.basename(log_id))
#                 if not log_dict.has_key(log_id):
#                     log_dir = "%s/%s" % (root, new_log_dir)
#                     if not os.path.isdir(log_dir):
#                         try:
#                             os.makedirs(log_dir)
#                         except OSError:
#                             log_dict["n"].write("(%s) Unable to create '%s' directory" % (my_name, log_dir))
#                             log_dir = root
#                         else:
#                             pass
#                     log_name = "%s/%s" % (log_dir, new_log_name)
#                     log_h = logging_tools.logfile(log_name)
#                     log_h.write("-" * 50, header=0)
#                     log_dict[log_id] = log_h
#                 if type(arg) != type([]):
#                     arg = [arg]
#                 for arg_line in arg:
#                     log_dict[log_id].write("%-4s (%s) %s" % (logging_tools.get_log_level_str(level), it.thread, arg_line))
#         elif it.m_type == "LC":
#             arg, log_ids = it.arg
#             if arg == "close":
#                 for log_id in log_ids:
#                     if log_dict.has_key(log_id):
#                         log_h = log_dict[log_id]
#                         log_h.write("(%s) Closing log" % (it.thread))
#                         log_h.close()
#                         del log_dict[log_id]
#                     else:
#                         log_dict["n"].write("(%s) Cannot close log_id %s (not found in log_id_list)" % (it.thread, log_id))
#             else:
#                 log_dict["n"].write("(%s) Got unknown log_command %s (%s)" % (it.thread, arg, ", ".join(log_ids)))
#         else:
#             log_dict["n"].write("(%s) Got message with unknown type '%s'" % (it.thread, it.m_type))
#     for log_id in log_dict.keys():
#         log_h = log_dict[log_id]
#         log_h.write("(%s) Closing log" % (my_name))
#         log_h.close()
#     if msi_block:
#         msi_block.remove_actual_pid()
#         msi_block.save_block()
#     #log_queue.put(log_ok_message("proc %d: logging-thread for sge-server exiting" % (mypid)))
#     m_queue.put(internal_message("exiting"))

# def process_epilogue(log_queue, mon_queue, job_mon_queue, check_dict, com_struct):
#     command = check_dict["command"]
#     delay_count = g_config["CLEAR_ITERATIONS"]
#     objects = check_dict.get("fail_objects", [])
#     job_id, job_num   = (check_dict["job_id"]    , check_dict["job_num"] )
#     uid, gid          = (check_dict["uid"]       , check_dict["gid"]     )
#     p_queue, job_name = (check_dict["queue_name"], check_dict["job_name"])
#     task_id = get_task_id(check_dict.get("task_id", None))
#     s_host = check_dict.get("host", "unknown")
#     why = check_dict.get("error", "<unknown>")
#     try:
#         uid_name = pwd.getpwuid(uid)[0]
#     except:
#         uid_name = "<unknown>"
#     try:
#         gid_name = grp.getgrgid(gid)[0]
#     except:
#         gid_name = "<unknown>"
#     com_str = "got command %s (%s) for %s, job_id %s, user %s (%d), group %s (%d) from host %s, reason: %s" % (command,
#                                                                                                                com_struct["command"],
#                                                                                                                logging_tools.get_plural(com_struct["object"], len(objects)),
#                                                                                                                job_id,
#                                                                                                                uid_name, uid,
#                                                                                                                gid_name, gid,
#                                                                                                                s_host,
#                                                                                                                why)
#     log_str = "got command %s for %s, user %s (%d), group %s (%d) from host %s, reason: %s" % (command,
#                                                                                                logging_tools.get_plural(com_struct["object"], len(objects)),
#                                                                                                uid_name, uid,
#                                                                                                gid_name, gid,
#                                                                                                s_host,
#                                                                                                why)
#     job_mon_queue.put(job_log_message({"job_uid" : job_id, "log_str" : log_str}))
#     mail_array = ["server         : sge-server",
#                   "",
#                   "Job information:",
#                   "job name : %s" % (job_name),
#                   "job-id   : %s" % (job_id),
#                   "job-num  : %s" % (job_num),
#                   "task id  : %s" % (str(task_id)),
#                   "",
#                   "User information:",
#                   "user  : %s (%d)" % (uid_name, uid),
#                   "group : %s (%d)" % (gid_name, gid),
#                   "",
#                   "Problem information:",
#                   "calling host  : %s" % (s_host),
#                   "primary queue : %s" % (p_queue),
#                   "object-type   : %s" % (com_struct["object"]),
#                   "action        : %s" % (command),
#                   "executing     : %s" % (com_struct["command"]),
#                   "reason        : %s" % (why)]
#     if objects:
#         mail_array.append("object list   : %s" % (",".join(objects)))
#     else:
#         mail_array.append("object list   : none given")
#     mail_array.append("")
#     log_queue.put(log_ok_message(com_str, ["n", "d"]))
#     if objects:
#         log_str = "object list: %s" % (",".join(objects))
#     else:
#         log_str = "object list: none given"
#     log_queue.put(log_ok_message(log_str, ["n", "d"]))
#     num_done = 0
#     for obj in objects:
#         stat, out = call_command(log_queue, "%s/bin/%s/%s %s" % (g_config["SGE_ROOT"], g_config["SGE_ARCH"], com_struct["command"], obj))
#         mail_array.append("executed command %s on object %s" % (com_struct["command"], obj))
#         mail_array.append("  result (%d): %s" % (stat, out))
#         log_str = "  executing command '%s %s', result: '%s'" % (com_struct["command"], obj, out)
#         log_queue.put(log_ok_message(log_str))
#         if not stat:
#             num_done += 1
#     if com_struct["object"] == "job" and command == "hold":
#         mail_array.append("")
#         mail_array.extend(["job hold will result in an error-state for queue %s on host %s, " % (p_queue, s_host), "will clear error in %d iterations" % (delay_count)])
#         mon_queue.put(monitor_message(("clear_queue_delayed", (p_queue, s_host, delay_count))))
#         if why.startswith("connection") and g_config["RETRY_AFTER_CONNECTION_PROBLEMS"]:
#             mail_array.append("")
#             mail_array.extend(["job hold because of an connection problem (MPI-Interface problem ?),", "will release job in %d iterations" % (delay_count)])
#             mon_queue.put(monitor_message(("release_job_delayed", (job_id, delay_count))))
#     if com_struct.has_key("mail"):
#         if com_struct["mail"]:
#             from_addr = g_config["FROM_ADDR"]
#             to_addrs = g_config["TO_ADDR"].split(",")
#             mail_subject = "sge problem - %s %s (%s)" % (command, com_struct["object"], job_id)
#             stat, log_strs = send_mail(from_addr, to_addrs, mail_subject, mail_array)
#             for l in log_strs:
#                 log_queue.put(log_ok_message(l))
#     ret_str = "ok %s on %d %s(s)" % (command, num_done, com_struct["object"])
#     return ret_str

def handle_got_id_call(log_queue, cc_dict, recv_dict):
    job_id = recv_dict.get("job_id", "not set")
    if cc_dict.has_key(job_id):
        real_job_id = None
        for line in [x.lower() for x in recv_dict["out_lines"]]:
            m = re.match("^your job (?P<id>\S+) .*$", line)
            if m:
                real_job_id = m.group("id")
        if real_job_id:
            cc_dict[job_id].set_real_job_id(real_job_id)
            ret_str = "ok exctracted %s" % (real_job_id)
        else:
            log_queue.put(log_error_message("Unable to extract job_id for %s from log_lines: %s" % (job_id,
                                                                                                    "; ".join(recv_dict["out_lines"]))))
            ret_str = "job_id not found"
    else:
        log_queue.put(log_error_message("Got unknown job_id '%s', not in cc_dict (%s)" % (job_id,
                                                                                          logging_tools.get_plural("key", len(cc_dict.keys())))))
        ret_str = "job_id '%s' unknown" % (job_id)
    return ret_str

class queue_request(object):
    def __init__(self, in_str):
        self.__parts = []
        if in_str:
            q_parts = [x.strip() for x in in_str.strip().split(",")]
            for q_part in q_parts:
                if q_part.count("@"):
                    queue_spec, node_spec = q_part.split("@", 1)
                    self.__parts.append((queue_spec.strip(), node_spec.strip()))
                else:
                    self.__parts.append((q_part.strip(), None))
        self.__num = len(self.__parts)
    def get_unique_cluster_queues(self):
        return dict([(x, True) for x, y in self.__parts]).keys()
    def __repr__(self):
        return "%d: %s" % (self.__num, ", ".join([y and "%s@%s" % (x, y) or x for x, y in self.__parts]))

class check_job(object):
    def __init__(self, check_dict, log_queue, sge_info, glob_config, loc_config):
        self.__start_time = time.time()
        self._set_act_thread()
        self.__id = str(self.__start_time)
        self.__log_queue = log_queue
        self.__glob_config, self.__loc_config = (glob_config, loc_config)
        self.__sge_info = sge_info
        loc_time = time.localtime()
        self.__target_log_pf = "job_check/%04d/%02d/%02d" % (loc_time[0], loc_time[1], loc_time[2])
        self.__log_pf = "%s/%s" % (self.__target_log_pf, self.__id)
        # generate pending-link
        self.__uid, self.__gid = (check_dict["uid"], check_dict["gid"])
        self.__append_args, self.__output = ([], [])
        self.__submit_flag = True
        self.parse_lines(check_dict["out_lines"])
    def get_submit_flag(self):
        return self.__submit_flag
    def _set_act_thread(self):
        self.__act_thread_name = threading.currentThread().getName()
    def get_pseudo_id(self):
        return self.__id
    def get_add_args(self):
        return " ".join(self.__append_args)
    def get_output_lines(self):
        return self.__output
    def set_real_job_id(self, rji):
        self.__job_id = rji
        self.glob_log("renaming job with pseudo-id %s to %s" % (self.__id,
                                                                self.__job_id))
        try:
            src_path = "%s/%s" % (self.__glob_config["LOG_DIR"], self.__log_pf)
            dst_path = "%s/%s/%s" % (self.__glob_config["LOG_DIR"], self.__target_log_pf, self.__job_id)
            os.rename(src_path, dst_path)
        except OSError:
            self.glob_log("error renaming %s to %s: %s (%s)" % (src_path,
                                                                dst_path,
                                                                str(sys.exc_info()[0]),
                                                                str(sys.exc_info()[1])))
        else:
            link_file_name = "%s/job_check/latest" % (self.__glob_config["LOG_DIR"])
            if os.path.isfile(link_file_name) or os.path.islink(link_file_name):
                os.unlink(link_file_name)
            os.symlink(dst_path[len(os.path.dirname(link_file_name)) + 1:], link_file_name)
    def glob_log(self, what, level=logging_tools.LOG_LEVEL_OK):
        self.__log_queue.put(("log", (self.__act_thread_name, what, level)))
    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        self.__log_queue.put(("special_log", (self.__act_thread_name, what, level, self.__log_pf)))
    def close_log(self):
        self.__log_queue.put(("close", (self.__log_pf)))
    def check_for_pe(self):
        is_pe, pe_num, pe_name = (False, 1, "serial")
        val = self.__check_dict.get("parallel environment", "")
        if val:
            is_pe = True
            pe_match = re.match("^\s*(?P<pe_name>\S+)\s*range:(?P<pe_range>.*)\s*$", val)
            if pe_match:
                pe_name, pe_num = (pe_match.group("pe_name").strip(),
                                   pe_match.group("pe_range").strip())
                pe_num_match = re.match("^(\d+[-|,])*(?P<pe_num>\d+)$", pe_num)
                if pe_num_match:
                    try:
                        pe_num = int(pe_num_match.group("pe_num"))
                    except ValueError:
                        raise check_exc(("e", "Error parsing integer pe_num '%s'" % (pe_num)))
                else:
                    raise check_exc(("e", "Error parsing pe_num '%s'" % (pe_num)))
            else:
                raise check_exc(("e", "Cannot parse pe-info '%s'" % (val)))
        self.__is_pe = is_pe
        self.__pe_num, self.__pe_name = (pe_num, pe_name)
    def is_pe(self):
        return self.__is_pe
    def get_pe_num(self):
        return self.__pe_num
    def get_pe_name(self):
        return self.__pe_name
    def check_for_lamboot_in_script(self):
        if self.__pe_name.count("lam"):
            for line_idx, line in zip(range(len(self.__script_lines)), self.__script_lines):
                if line.count("lamboot") and not line.strip().startswith("#"):
                    self.__output.append(("w", "Warning: lamboot-command found in line %d, not necessary for lam-pe" % (line_idx + 1)))
    def check_for_lam_path(self):
        if self.__env_dict.has_key("PATH") and self.__is_pe and self.__pe_name.count("lam"):
            if not self.__env_dict["PATH"].count("lam") and not self.__env_dict["PATH"].count("$PATH"):
                self.__output.append(("w", "Warning: PATH-variable misses component to LAM"))
    def build_resource_dict(self):
        res_dict = {}
        res_parts = [x.strip().split("=", 1) for x in self.__check_dict.get("hard resource_list", "").split(",") if x.strip()]
        for res_part in res_parts:
            res_part = [x.strip() for x in res_part]
            if len(res_part) == 2:
                key, value = res_part
                res_dict[key] = value
            else:
                key = res_part[0]
                res_dict[key] = True
        self.__resource_dict = res_dict
    def check_for_queue_requests(self, what=None):
        if what is None:
            self.__queue_requests = self.check_for_queue_requests("hard_queue_list")
            self.__master_queue_requests = self.check_for_queue_requests("master hard queue list")
        else:
            return queue_request(self.__check_dict.get(what, None))
    def build_queue_dict(self):
        # build queue_dict from complex_dict
        q_dict = {}
        for c_name in self.__sge_complexes.keys():
            for c_queue in self.__sge_complexes[c_name].get("queues", []):
                q_dict.setdefault(c_queue, []).append(c_name)
        return q_dict
    def parse_lines(self, in_lines):
        # unset prefixes
        unset_pfixes = ["job_number",
                        "submission_time",
                        "uid",
                        "gid",
                        "owner",
                        "group",
                        "sge_o_home",
                        "sge_o_log_name",
                        "sge_o_path",
                        "sge_o_shell",
                        "sge_o_workdir",
                        "sge_o_host",
                        "cwd",
                        "path_aliases",
                        "hard resource_list",
                        "notify",
                        "job_name",
                        "stderr_path_list",
                        "stdout_path_list",
                        "priority",
                        "verify",
                        "mail_list",
                        "env_list",
                        "script_size",
                        "script_file",
                        "parallel environment",
                        "hard_queue_list",
                        "master hard queue list"]
        check_dict = {}
        # extract script
        script_lines, script_mode = ([], False)
        for line in in_lines:
            line_s = line.split(":", 1)
            if line_s[0].startswith("parallel environment") or line_s[0].startswith("project"):
                script_mode = False
            if script_mode:
                script_lines.append(line)
                if sum([len(x) for x in script_lines]) >= int(check_dict.get("script_size", 0)) - len(script_lines) - 1:
                    script_mode = False
            else:
                pfix = line_s.pop(0)
                if pfix in unset_pfixes and line_s:
                    unset_pfixes.remove(pfix)
                    check_dict[pfix] = line_s.pop(0).strip()
                # handle script_ptr
                if line.startswith("script_ptr:"):
                    script_mode = True
        self.__check_dict = check_dict
        self.__script_lines = script_lines
        self.log("Checking %s for uid %d, gid %d (found %s, %s)" % (logging_tools.get_plural("line", len(in_lines)),
                                                                    self.__uid,
                                                                    self.__gid,
                                                                    logging_tools.get_plural("set postfix", len(check_dict.keys())),
                                                                    logging_tools.get_plural("unset postfix", len(unset_pfixes))))
        if unset_pfixes:
            unset_pfixes.sort()
            self.log("Unset: %s" % (", ".join(unset_pfixes)))
        self.log("Set:")
        pfix_out_list = logging_tools.form_list()
        short_keys = ["env_list", "sge_o_path"]
        for pfix_key in sorted(self.__check_dict.keys()):
            if pfix_key in short_keys:
                pfix_out_list.add_line(("-",
                                        pfix_key,
                                        ":",
                                        "<len %s>" % (logging_tools.get_plural("byte", len(self.__check_dict[pfix_key])))))
            else:
                pfix_out_list.add_line(("-",
                                        pfix_key,
                                        ":",
                                        self.__check_dict[pfix_key]))
        self.log(str(pfix_out_list).split("\n"))
        del pfix_out_list
        # log script
        self.log("script has %s:" % (logging_tools.get_plural("line", len(self.__script_lines))))
        s_line = 0
        for sl in self.__script_lines:
            s_line += 1
            self.log("%4d : %s" % (s_line, sl))
        # get complexes
        complex_names = self.__sge_complexes.complex_names
        all_c_types = sorted(self.__sge_complexes.complex_types.keys())
        self.log("found %s (%s)" % (logging_tools.get_plural("complex", len(complex_names)),
                                    logging_tools.get_plural("complex_type", len(all_c_types))))
        # log complexes and types, build resource_list
        all_resources = []
        for c_t in all_c_types:
            loc_keys = self.__sge_complexes.complex_types[c_t]
            self.log("Found %s with complex_type '%s:'" % (logging_tools.get_plural("key", len(loc_keys)),
                                                           c_t))
            # build dict
            log_dict = {}
            for c_key in loc_keys:
                log_dict.setdefault(c_key[0], []).append(c_key)
                all_resources.extend(self.__sge_complexes[c_key].get_resources())
            for log_key in sorted(log_dict.keys()):
                log_dict[log_key].sort()
                self.log("%2d with '%s': %s" % (len(log_dict[log_key]),
                                                log_key,
                                                ", ".join(log_dict[log_key])))
        # build dict queue->init.at complex
        #queue_ic_dict = dict([(x["queue"], x) for x in self.__sge_complexes.values() if x.get_complex_type() == "i" and x["queue"]])
        try:
            #print "qi:", queue_ic_dict
            #print "cd:", check_dict
            # scan for pe
            self.check_for_pe()
            if not self.is_pe() and self.__glob_config["STRICT_MODE"] and self.__glob_config["APPEND_SERIAL_COMPLEX"]:
                if "serial" in complex_names:
                    self.__append_args.append("-l serial")
                    self.log("Appended request for serial-complex")
                else:
                    raise check_exc(("e", "No serial-complex found (strict_mode)"))
            # build env_dict
            self.__env_dict = dict([(k, v) for k, v in [y for y in [x.split("=", 1) for x in check_dict.get("env_list", "").split(",")] if len(y) == 2]])
            self.__env_keys = sorted(self.__env_dict.keys())
            self.log("environment has %s: %s" % (logging_tools.get_plural("key", self.__env_keys),
                                                 ", ".join(self.__env_keys)))
            self.check_for_lamboot_in_script()
            self.check_for_lam_path()
            self.build_resource_dict()
            self.check_for_queue_requests()
##             hard_queue = self.__check_dict.get("hard_queue_list", None)
##             if hard_queue:
##                 hard_queue = hard_queue.split("@")[0]
##             master_queue = self.__check_dict.get("master hard queue list", None)
##             if master_queue:
##                 master_queue = master_queue.split("@")[0]
##             print hard_queue, master_queue
##             if master_queue and hard_queue:
##                 if master_queue != hard_queue:
##                     raise check_exc(("e", ""))
            # check for sge_complexes nowhere defined
            error_complexes = sorted([x for x in self.__resource_dict.keys() if x not in all_resources])
            if error_complexes:
                self.log("  rejected: %s: %s" % (logging_tools.get_plural("undefined complex", len(error_complexes)),
                                                 ", ".join(error_complexes)))
                raise check_exc(("e", "%s %s not defined" % (logging_tools.get_plural("complex", len(error_complexes)),
                                                             ", ".join(error_complexes))))
            # list if special complexes
            special_complex_names = ["serial"]
            special_complexes_found = []
            init_complexes_found = []
            for cpl in self.__resource_dict.keys():
                if cpl in special_complex_names:
                    special_complexes_found.append(cpl)
                    c_type = "special"
                elif cpl in self.__sge_complexes.complex_types.get("i", []):
                    init_complexes_found.append(cpl)
                    c_type = "init.at"
                else:
                    c_type = "system"
                self.log("  found complex %s (type %s)" % (cpl, c_type))
            # find queues which matches all init_complexes
            queues_from_init = None
            # complexes which are valid for the given queue
            complexes_from_queue = None
            if init_complexes_found:
                for i_c_f in init_complexes_found:
                    if queues_from_init is None:
                        queues_from_init = self.__sge_complexes[i_c_f]["queues"]
                    else:
                        queues_from_init = [x for x in queues_from_init if x in self.__sge_complexes[i_c_f]["queues"]]
                self.log("found %s matching %s (%s): %s" % (logging_tools.get_plural("cluster queue", len(queues_from_init)),
                                                            logging_tools.get_plural("init complex", len(init_complexes_found)),
                                                            ", ".join(init_complexes_found),
                                                            ", ".join(queues_from_init) or "none"))
                if queues_from_init == []:
                    raise check_exc(("e", "no queues found for requested complexes: %s" % (", ".join(init_complexes_found))))
            else:
                self.log("no init_complexes specified")
            # queue_dict, queue -> possible init_complexes
            queue_dict = self.build_queue_dict()
            # requested cluster-queues
            req_cq = sorted(self.__queue_requests.get_unique_cluster_queues())
            if req_cq:
                self.log("Queue Request (%d): %s" % (len(req_cq),
                                                     ", ".join(req_cq)))
                complexes_from_queue = queue_dict.get(req_cq[0], [])
            if queues_from_init is None and complexes_from_queue is None and self.__glob_config["STRICT_MODE"]:
                raise check_exc(("e", "no valid queue-complex mapping found"))
            # further checks or enough ?
            # complexes specified via queue and directly
            if complexes_from_queue and init_complexes_found:
                all_complexes = [c_name for c_name in complexes_from_queue if c_name in init_complexes_found]
                if not all_complexes:
                    raise check_exc(("e", "queue and complexes specified, no matching queue / complex combination found"))
            elif complexes_from_queue:
                all_complexes = complexes_from_queue
            elif init_complexes_found:
                all_complexes = init_complexes_found
            else:
                all_complexes = []
            for c_name in all_complexes:
                self._check_resources(c_name)
            #if req_cq :
            #    if not [True for x in req_cq 
            #if self.__queue_requests
            #print "qfi:", queues_from_init
        except check_exc, what:
            add_type = what.get_value()
            if len(add_type):
                if add_type[0] == "e":
                    self.__submit_flag = False
                self.__output.append(add_type)
        if self.__output:
            self.log("output has %s:" % (logging_tools.get_plural("line", len(self.__output))))
            for idx, (what, ret_str) in zip(range(len(self.__output)), self.__output):
                self.log("%-2d %4s : %s" % (idx, what, ret_str))
        else:
            self.log("no output")
    def _time_str_to_secs(self, in_str):
        try:
            in_int = [int(x) for x in in_str.split(":")]
        except:
            raise ValueError
        in_int.reverse()
        time_seconds = 0
        mult = [1, 60, 60 * 60, 24 * 60 * 60]
        while in_int:
            time_seconds += mult.pop(0) * in_int.pop(0)
        return time_seconds
    def _check_resources(self, c_name):
        act_res = self.__sge_complexes[c_name]
        if act_res.complex_type != "i":
            self.log("cannot compare check resources against non-init.at style complex %s" % (c_name),
                     logging_tools.LOG_LEVEL_WARN)
        else:
            self.log("checking resources against init.at complex %s" % (c_name))
            # check pe
            if self.__pe_num < act_res["num_min"] or self.__pe_num > act_res["num_max"]:
                raise check_exc(("e", "number of slots %d (PE %s) not in range [%d, %d]" % (self.__pe_num,
                                                                                            self.__pe_name,
                                                                                            act_res["num_min"],
                                                                                            act_res["num_max"])))
            if not self.__resource_dict.has_key("h_rt") and self.__glob_config["STRICT_MODE"]:
                raise check_exc(("e", "h_rt setting missing"))
            try:
                h_rt_node = self._time_str_to_secs(self.__resource_dict["h_rt"])
            except:
                raise check_exc(("e", "error parsing h_rt %s" % (self.__resource_dict["h_rt"])))
            h_rt_total = self.__pe_num * h_rt_node
            seconds_node, seconds_total = (self._time_str_to_secs(act_res["m_time"]),
                                           self._time_str_to_secs(act_res["mt_time"]))
            self.log("time requested (per node / total): %s / %s" % (logging_tools.get_diff_time_str(h_rt_node),
                                                                     logging_tools.get_diff_time_str(h_rt_total)))
            self.log("time granted   (per node / total): %s / %s" % (logging_tools.get_diff_time_str(seconds_node),
                                                                     logging_tools.get_diff_time_str(seconds_total)))
            err_cause = []
            if h_rt_node > seconds_node:
                err_cause.append("time per node exceeded (%s > %s)" % (logging_tools.get_diff_time_str(h_rt_node),
                                                                       logging_tools.get_diff_time_str(seconds_node)))
            if h_rt_total > seconds_total:
                err_cause.append("time total exceeded (%s > %s)" % (logging_tools.get_diff_time_str(h_rt_total),
                                                                    logging_tools.get_diff_time_str(seconds_total)))
            if err_cause:
                raise check_exc(("e", ", ".join(err_cause)))
        
class check_thread(threading_tools.thread_obj):
    def __init__(self, glob_config, loc_config, db_con, log_queue):
        """ check job submit requests """
        self.__db_con = db_con
        self.__log_queue = log_queue
        self.__glob_config, self.__loc_config = (glob_config, loc_config)
        threading_tools.thread_obj.__init__(self, "check", queue_size=200)
        self.register_func("set_queue_dict", self._set_queue_dict)
        self.register_func("set_aj_struct", self._set_aj_struct)
        self.register_func("check_submit_job", self._check_submit_job)
        self.register_func("got_final_job_id", self._got_final_job_id)
        # all_jobs_struct
        self.__aj_struct = None
        # jobs to check
        self.__check_dict = {}
        self._init_sge_info()
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK, special=[]):
        if not special:
            self.__log_queue.put(("log", (self.name, what, lev)))
        else:
            for spec in special:
                self.__log_queue.put(("special_log", (self.name, what, lev, spec)))
    def thread_running(self):
        self.send_pool_message(("new_pid", (self.name, self.pid)))
        self.__dc = self.__db_con.get_connection(SQL_ACCESS)
    def loop_end(self):
        self.__dc.release()
    def _set_queue_dict(self, q_dict):
        self.__queue_dict = q_dict
    def _set_aj_struct(self, aj_struct):
        self.log("Got aj_struct")
        self.__aj_struct = aj_struct
    def _init_sge_info(self):
        self.log("init sge_info")
        self.__sge_info = sge_tools.sge_info(log_command=self.log,
                                             run_initial_update=False,
                                             ignore_dicts=["qhost", "qstat"],
                                             sge_dict=dict([(key, self.__glob_config[key]) for key in ["SGE_ARCH", "SGE_ROOT", "SGE_CELL"]]))
    def _got_final_job_id(self, (opt_dict, tcp_obj)):
        tmp_id = opt_dict["job_id"]
        real_id = opt_dict["out_lines"][0].split()[2]
        if self.__check_dict.has_key(tmp_id):
            self.__check_dict[tmp_id].set_real_job_id(real_id)
            del self.__check_dict[tmp_id]
        else:
            self.log("temporay job_id %s (real job_id %s) not known, ignoring" % (tmp_id,
                                                                                  real_id))
        tcp_obj.add_to_out_buffer(server_command.server_reply(state=server_command.SRV_REPLY_STATE_OK,
                                                              result="ok"))
    def _check_submit_job(self, (opt_dict, tcp_obj)):
        self.__sge_info.update(no_file_cache=True, force_update=True)
        new_check_job = check_job(opt_dict, self.__log_queue, self.__sge_info.check_out_dict(), self.__glob_config, self.__loc_config)
        self.__check_dict[new_check_job.get_pseudo_id()] = new_check_job
        new_check_job.close_log()
        tcp_obj.add_to_out_buffer(server_command.server_reply(state=server_command.SRV_REPLY_STATE_OK,
                                                              result="ok",
                                                              option_dict={"submit_job"   : new_check_job.get_submit_flag(),
                                                                           "append_arg"   : new_check_job.get_add_args(),
                                                                           "temporary_id" : new_check_job.get_pseudo_id(),
                                                                           "out_list"     : new_check_job.get_output_lines()}))
        

def check_resource_hook(check_dict, log_queue, sge_complexes, job_id=None):
    start_time = time.time()
    out_lines = check_dict["outlines"]
    known_pfixes = ["job_number",
                    "submission_time",
                    "uid",
                    "gid",
                    "owner",
                    "group",
                    "sge_o_home",
                    "sge_o_log_name",
                    "sge_o_path",
                    "sge_o_shell",
                    "sge_o_workdir",
                    "sge_o_host",
                    "cwd",
                    "path_aliases",
                    "hard resource_list",
                    "notify",
                    "job_name",
                    "stderr_path_list",
                    "stdout_path_list",
                    "priority",
                    "verify",
                    "mail_list",
                    "env_list",
                    "script_size",
                    "script_file",
                    "parallel environment",
                    "hard_queue_list",
                    "master hard queue list"]
    out_dict = {}
    script_lines, script_mode = ([], False)
    for line in out_lines:
        line_s = line.split(":", 1)
        if line_s[0].startswith("parallel environment") or line_s[0].startswith("project"):
            script_mode = False
        if script_mode:
            script_lines.append(line)
            if reduce(lambda x, y : x + y, [len(x) for x in script_lines]) >= int(out_dict.get("script_size", 0)) - len(script_lines) - 1:
                script_mode = False
        else:
            pfix = line_s.pop(0)
            if pfix in known_pfixes and len(line_s) == 1:
                known_pfixes.remove(pfix)
                out_dict[pfix] = line_s.pop(0).strip()
            # handle script_ptr
            if line.startswith("script_ptr:"):
                script_mode = True
    out_dict["script_lines"] = script_lines
    #print out_dict["script_lines"]
    #print out_dict
    log_queue.put(log_ok_message("-" * 40, ["j"]))
    log_queue.put(log_ok_message("  Checking %s for uid %d, gid %d (found %d known postfixes)" % (logging_tools.get_plural("line", len(out_lines)),
                                                                                                  check_dict["uid"],
                                                                                                  check_dict["gid"],
                                                                                                  len(out_dict.keys())), ["j"]))
    sge_complexes.update()
    c_keys = sorted(sge_complexes.keys())
    all_c_types = []
    for c_t in [x.get_complex_type() for x in sge_complexes.values()]:
        if c_t not in all_c_types:
            all_c_types.append(c_t)
    all_c_types.sort()
    log_queue.put(log_ok_message("found %s (%s)" % (logging_tools.get_plural("complex", len(c_keys)),
                                                    logging_tools.get_plural("complex_type", len(all_c_types))), ["j"]))
    for c_t in all_c_types:
        loc_keys = []
        for c_key in c_keys:
            if sge_complexes[c_key].get_complex_type() == c_t:
                loc_keys.append(c_key)
        log_queue.put(log_ok_message("Found %s with complex_type '%s'" % (logging_tools.get_plural("key", len(loc_keys)), c_t), ["j"]))
        for c_key in loc_keys:
            compl = sge_complexes[c_key]
            log_queue.put(log_ok_message(" - %-20s" % (c_key), ["j"]))
    for pfix_key in sorted(out_dict.keys()):
        log_queue.put(log_ok_message(" - %-20s : %s" % (pfix_key, out_dict[pfix_key]), ["j"]))
    # build dict queue->init.at complex
    queue_ic_dict = {}
    for ic in [x for x in sge_complexes.values() if x.get_complex_type() == "i"]:
        for queue in ic.get("queues", []):
            queue_ic_dict[queue] = ic
    ret_list = []
    try:
        if out_dict.has_key("parallel environment"):
            value = out_dict["parallel environment"]
            is_pe = 1
            pe_match = re.match("^\s*(?P<pe_name>\S+)\s*range:(?P<pe_range>.*)\s*$", value)
            if pe_match:
                pe_name = pe_match.group("pe_name").strip()
                pe_num = pe_match.group("pe_range").strip()
                pe_n_match = re.match("^(\d+[-|,])*(?P<num>\d+)$", pe_num)
                if pe_n_match:
                    try:
                        pe_num = int(pe_n_match.group("num"))
                    except:
                        raise check_exc(("e", "Error reading integer pe-num %s" % (pe_num)))
                else:
                    raise check_exc(("e", "Cannot parse pe-num %s" % (pe_num)))
            else:
                raise check_exc(("e", "Cannot parse pe-info %s" % (value)))
        else:
            is_pe = 0
            pe_name, pe_num = ("serial", 1)
            if g_config["STRICT_MODE"] and g_config["APPEND_SERIAL_COMPLEX"]:
                if sge_complexes.has_key("serial"):
                    self.__append_args.append(" -l serial ")
                    log_queue.put(log_ok_message("  Append request for serial-complex", ["j"]))
                else:
                    raise check_exc(("e", "No serial-complex found (strict_mode)"))
        if out_dict.has_key("env_list"):
            env_dict = {}
            for k, v in [y for y in [x.split("=", 1) for x in out_dict["env_list"].split(",")] if len(y) == 2]:
                env_dict[k] = v
            if env_dict.has_key("PATH"):
                if is_pe:
                    if not env_dict["PATH"].count("lam") and pe_name.count("lam") and not re.match("^.*\$PATH.*$", env_dict["PATH"]):
                        raise check_exc(("e", "requested pe '%s' requires LAM-Path in $PATH" % (pe_name)))
        # check for lamboot-command in script in case of lam-pes
        if pe_name.count("lam"):
            l_idx = 0
            for line in out_dict["script_lines"]:
                l_idx += 1
                if re.match("^\s*lamboot.*$", line):
                    ret_list.append(("e", "Error: lamboot-command found in line %d, not necessary for lam-pe" % (l_idx)))
        # search h_rt
        resource_dict = {}
        if out_dict.has_key("hard resource_list"):
            line = out_dict["hard resource_list"]
            res_parts = line.split(",")
            if len(res_parts):
                for act_p in res_parts:
                    re_match = re.match("(?P<res_name>[^=]+)=(?P<res_value>.*)$", act_p)
                    if re_match:
                        resource_dict[re_match.group("res_name").strip()] = re_match.group("res_value").strip()
                    else:
                        if re.match("^[^=]+$", act_p):
                            resource_dict[act_p] = "1"
                        else:
                            raise check_exc(("e", "Cannot parse resource line %s" % (line)))
            else:
                raise check_exc(("e", "Cannot parse resource line %s" % (line)))
        #avail_d = {"pe":"serial","num":"1","time":"0:10:0"}
        avail_d, queue_given = (None, None)
        if out_dict.has_key("hard_queue_list"):
            queue_given = out_dict["hard_queue_list"]
            if queue_given.count("@"):
                queue_given = queue_given.split("@")[0]
        elif out_dict.has_key("master hard queue list"):
            queue_given = out_dict["master hard queue list"]
            if queue_given.count("@"):
                queue_given = queue_given.split("@")[0]
        # get complexes from monitor-thread queue
        all_resources = []
        for compl in sge_complexes.keys():
            all_resources += sge_complexes[compl].get_resources()
        e_compl = []
        # special resources
        s_resources = ["serial"]
        s_res_found = []
        for cpl in resource_dict.keys():
            if not cpl in all_resources:
                e_compl.append(cpl)
                continue
            c_type = "system"
            if cpl in s_resources:
                s_res_found.append(cpl)
                c_type = "special"
            elif cpl in sge_complexes.keys():
                #print "****",cpl, sge_complexes.keys()
                if sge_complexes[cpl].get_complex_type() == "i":
                    c_type = "init.at"
                    avail_d = sge_complexes[cpl].get_internal_dict()
            log_queue.put(log_ok_message("  found %s complex %s" % (c_type, cpl), ["j"]))
        if not avail_d and queue_given:
            # find init complex responsible for this queue
            avail_d = queue_ic_dict.get(queue_given, None)
            if avail_d:
                self.__append_args.append(" -l %s " % (avail_d.name))
                avail_d = avail_d.get_internal_dict()
        if not avail_d and len([x for x in sge_complexes.keys() if sge_complexes[x].get_complex_type() == "i"]) and g_config["STRICT_MODE"]:
            log_str = "rejected: no valid queue found (one of %s)" % (",".join([x for x in sge_complexes.keys() if sge_complexes[x].get_complex_type() == "i" and x not in s_resources]))
            raise check_exc(("e", log_str))
        if len(e_compl):
            log_queue.put(log_ok_message("  rejected: undefined complexes", ["j"]))
            raise check_exc(("e", "complex(es) %s not defined" % (",".join(e_compl))))
        if pe_name != "serial" and "serial" in s_res_found:
            raise check_exc(("e", "you requested the pe '%s' and the serial tag" % (pe_name)))
        if avail_d:
            res_dict = {"pe"      : avail_d["pe"].split(","),
                        "num_min" : avail_d["num_min"],
                        "num_max" : avail_d["num_max"],
                        "mt_time" : avail_d["mt_time"],
                        "m_time"  : avail_d["m_time"]}
            # FIXME
            #if is_pe and pe_name not in res_dict["pe"]:
            #    raise check_exc(("e", "your pe '%s' is not in list %s" % (pe_name, ",".join(res_dict["pe"]))))
        #print res_dict
        #print resource_dict
        if resource_dict.has_key("h_rt"):
            if avail_d:
                time_dict = {}
                for time_str, time_name in [(resource_dict["h_rt"], "wpe"),
                                            (res_dict["mt_time"]  , "at" ),
                                            (res_dict["m_time"]   , "a"  )]:
                    mult_array = [24*60*60, 60*60, 60, 1]
                    time_p = time_str.split(":")
                    if len(time_p) > 4:
                        raise check_exc(("e", "Error parsing resource %s" % (time_str)))
                    max_secs = 0
                    while len(time_p):
                        act_val = time_p.pop()
                        if not re.match("^\d+$", act_val):
                            raise check_exc(("e", "Error parsing integer %s in resource_value %s" % (act_val, time_str)))
                        try:
                            max_secs += int(act_val) * mult_array.pop()
                        except:
                            raise check_exc(("e", "Error parsing integer %s in resource_value %s (int_too_big ?)" % (act_val, time_str)))
                    time_dict[time_name] = max_secs
                if pe_num > int(res_dict["num_max"]):
                    log_str = "requested too many pe-slots (%d > %d, pe %s)" % (pe_num, int(res_dict["num_max"]), pe_name)
                    log_queue.put(log_ok_message("  rejected: %s" % (log_str), ["j"]))
                    raise check_exc(("e", "you have %s" % (log_str)))
                if pe_num < int(res_dict["num_min"]):
                    log_str = "requested too few pe-slots (%d < %d, pe %s)" % (pe_num, int(res_dict["num_min"]), pe_name)
                    log_queue.put(log_ok_message("  rejected: %s" % (log_str), ["j"]))
                    raise check_exc(("e", "you have %s" % (log_str)))
                time_dict["w"] = pe_num * time_dict["wpe"]
                if time_dict["w"] > time_dict["at"]:
                    log_str = "total time of %s (%s per pe-slot) exceeds configured time of %s" % (sec_to_time(time_dict["w"]), sec_to_time(time_dict["wpe"]), sec_to_time(time_dict["at"]))
                    log_queue.put(log_ok_message("  rejected: %s" % (log_str), ["j"]))
                    raise check_exc(("e", "Requested %s" % (log_str)))
                elif time_dict["wpe"] > time_dict["a"]:
                    log_str = "job time of %s exceeds configured maximal time per slot of %s" % (sec_to_time(time_dict["w"]), sec_to_time(time_dict["a"]))
                    log_queue.put(log_ok_message("  rejected: %s" % (log_str), ["j"]))
                    raise check_exc(("e", "Requested %s" % (log_str)))
        else:
            raise check_exc(("e", "No h_rt resource limit found"))
    except check_exc, what:
        add_t = what.get_value()
        if len(add_t):
            ret_list.append(add_t)
    s_dict = {}
    #print ret_list
    for a, b in ret_list:
        if a not in s_dict:
            s_dict[a] = 0
        if a == "e":
            log_queue.put(log_error_message("  error: %s" % (b), ["j"]))
        s_dict[a] += 1
    if s_dict:
        ret_str = ",".join(["%s: %d" % (a, s_dict[a]) for a in s_dict.keys()])
    else:
        ret_str = "<empty>"
    if not job_id:
        job_id = str(time.time())
    ret_list.append(("ID", job_id))
    log_queue.put(log_ok_message("finished processing request (took %.2f seconds), returning list: %s" % (time.time() - start_time, ret_str), ["j", "n"]))
    return "ok:%s" % (sys_to_net(ret_list)), job_id

class pending_job_info(object):
    def __init__(self, n_thread, tcp_obj, in_dict):
        # calling thread
        self.__thread = n_thread
        self.__tcp_obj = tcp_obj
        self.__job_dict = dict([(key, {"pending" : True,
                                       "result"  : "not set",
                                       "hosts"   : set([])}) for key in in_dict.get("job", [])])
        self.__host_dict = {}
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__thread.log("[pji] %s" % (what), log_level)
    def generate_requests(self, s_info):
        needed_hosts = set()
        for job_id in self.__job_dict.keys():
            if s_info["qstat"].has_key(job_id):
                if s_info["qstat"][job_id].running:
                    job_hosts = set([q_name.split("@")[1].split(".")[0] for q_name in s_info["qstat"][job_id]["queue_name"]])
                    self.__job_dict[job_id]["hosts"] = job_hosts
                    self.__job_dict[job_id]["result"] = "job is running on %s" % (logging_tools.get_plural("host", len(job_hosts)))
                    needed_hosts.update(job_hosts)
                else:
                    self.__job_dict[job_id]["pending"] = False
                    self.__job_dict[job_id]["result"] = "job is not running"
            else:
                self.__job_dict[job_id]["pending"] = False
                self.__job_dict[job_id]["result"] = "job not found"
        self.__host_dict = {}
        req_list = []
        for h_name in needed_hosts:
            self.__host_dict[h_name] = {"pending" : 2,
                                        "result"  : {}}
            for act_com in ["get_mvector", "proclist"]:
                req_list.append(net_tools.tcp_con_object(self._new_tcp_con,
                                                         connect_state_call = self._connect_state_call,
                                                         connect_timeout_call = self._connect_timeout,
                                                         target_host = h_name,
                                                         target_port = 2001,
                                                         timeout = 20,
                                                         bind_retries = 1,
                                                         rebind_wait_time = 1,
                                                         add_data=act_com))
        self._check_for_finish()
        return req_list
    def _connect_state_call(self, **args):
        if args["state"] == "error":
            t_host = args["host"]
            t_com = args["socket"].get_add_data()
            self.log("error connecting to host %s for command %s" % (t_host,
                                                                     t_com),
                     logging_tools.LOG_LEVEL_ERROR)
            args["socket"].delete()
            self._host_error(t_host, t_com)
    def _connect_timeout(self, sock):
        t_host = sock.get_target_host()
        t_com = sock.get_add_data()
        self.log("timeout while connecting to host %s for commmand %s" % (t_host, t_com),
                 logging_tools.LOG_LEVEL_ERROR)
        sock.delete()
        sock.close()
        self._host_error(t_host, t_com)
    def _host_error(self, h_name, t_com):
        self.log("got an error for host %s" % (h_name),
                 logging_tools.LOG_LEVEL_ERROR)
        self.__host_dict[h_name]["pending"] -= 1
        self.__host_dict[h_name]["result"][t_com] = "error connecting"
        self._check_for_finish()
    def _host_ok(self, h_name, h_com, res):
        if res.startswith("ok "):
            self.log("got a result from host %s for command %s" % (h_name, h_com))
            self.__host_dict[h_name]["pending"] -= 1
            result = cPickle.loads(res[3:])
            if h_com == "get_mvector":
                # transfer to new type
                if type(result[1][0][1]) == type({}):
                    result = (result[0], [(key, hm_classes.mvect_entry(key,
                                                                       default=v_dict["d"],
                                                                       info=v_dict["i"],
                                                                       unit=v_dict["u"],
                                                                       base=v_dict["b"],
                                                                       value=v_dict["v"],
                                                                       factor=v_dict["f"])) for key, v_dict in result[1]])
            self.__host_dict[h_name]["result"][h_com] = result
        else:
            self._host_error(h_name, h_com)
        self._check_for_finish()
    def _new_tcp_con(self, sock):
        return node_con_obj(self, sock.get_target_host(), sock.get_add_data())
    def _check_for_finish(self):
        if not [True for value in self.__host_dict.itervalues() if value["pending"]]:
            self.__tcp_obj.add_to_out_buffer(server_command.server_reply(state=server_command.SRV_REPLY_STATE_OK,
                                                                         result="checked %s" % (logging_tools.get_plural("job", len(self.__job_dict.keys()))), 
                                                                         option_dict={"hosts" : self.__host_dict,
                                                                                      "jobs"  : self.__job_dict}))
            del self

def prune_job_id(job_id):
    while True:
        # trim job_id
        if job_id.startswith('"'):
            job_id = job_id[1:]
        elif job_id.endswith('"'):
            job_id = job_id[:-1]
        elif job_id.endswith("'s"):
            job_id = job_id[:-2]
        elif job_id.endswith(":"):
            job_id = job_id[:-1]
        elif job_id.startswith("("):
            job_id = job_id[1:]
        elif job_id.endswith(")"):
            job_id = job_id[:-1]
        else:
            break
    return job_id
    
def prune_queue_id(queue_id):
    while True:
        # trim j_id
        if queue_id.startswith('"'):
            queue_id = queue_id[1:]
        elif queue_id.endswith('"'):
            queue_id = queue_id[:-1]
        else:
            break
    return queue_id
    
def job_monitor_thread_code(main_queue, log_queue, own_queue, mon_queue, sql_queue, sge_complexes, nss, msi_block):
    def get_job(job_uid, db_con, j_dict):
        if job_dict.has_key(job_uid):
            act_job = job_dict[job_uid]
        else:
            #print j_dict
            act_job = job(job_uid, db_con, j_dict, sql_queue)
            job_dict[job_uid] = act_job
            log_queue.put(log_ok_message("Added job %s to job_dict (contains now %s)" % (job_uid,
                                                                                         logging_tools.get_plural("job", len(job_dict.keys())))))
        return act_job
##     def get_queue(queue_name, db_con, log_queue):
##         if act_queue_dict.has_key(queue_name):
##             act_queue = act_queue_dict[queue_name]
##         else:
##             #print j_dict
##             act_queue = queue(sge_queue_cache_object, queue_name, db_con, log_queue)
##             act_queue_dict[queue_name] = act_queue
##             log_queue.put(log_ok_message("Added queue %s to act_queue_dict (contains now %s)" % (act_queue.get_info(),
##                                                                                               logging_tools.get_plural("queue", len(act_queue_dict.keys())))))
##         return act_queue
    my_name = threading.currentThread().getName()
    my_pid = os.getpid()
    process_tools.append_pids("%s/%s" % (self.__loc_config["SERVER_ROLE"],
                                         self.__loc_config["SERVER_ROLE"]))
    log_queue.put(log_ok_message("proc %d: %s-thread for %s is now awake" % (my_pid,
                                                                             self.__loc_config["SERVER_ROLE"],
                                                                             my_name)))
    if msi_block:
        msi_block.add_actual_pid()
        msi_block.save_block()
    job_dict = {}
    act_queue_dict = {}
    check_job_dict = {}
    db_con = mysql_tools.db_con()
    db_con.dc.enable_logging(False)
    # FIXME
    g_config = {}
    sge_queue_cache_object = sge_queue_cache(db_con.dc, log_queue, g_config)
    last_time = None
    while True:
        db_con.dc.init_logs()
        act_time = time.time()
##         if last_time:
##             print "*** wait, ", time.ctime(last_time),"; ",it.m_type, " took ",act_time-last_time, "(",it.arg, ")"
        it = own_queue.get()
        last_time = time.time()
        if hasattr(it, "type"):
            it.m_type = it.type
        if it.m_type == "I":
            if it.arg == "exit":
                break
            else:
                log_queue.put(log_error_message("Got unknown internal message: %s" % (it.arg)))
        elif it.m_type == "CJ":
            recv_dict, ret_key, machinfo = it.arg
            try:
                job_ids = recv_dict["job"]
            except:
                nss.set_result(ret_key, "error reading job-ids")
            else:
                try:
                    sge_dict = dict([(key, g_config[key]) for key in ["SGE_ARCH", "SGE_ROOT", "SGE_CELL"]])
                    queue_dict, job_r_dict, job_w_dict, ticket_dict, pri_dict = sge_tools.get_all_dicts(sge_complexes.check_out_dict(), "", job_ids, sge_dict, {"expand_array_jobs" : 1})
                except ValueError, what:
                    nss.set_result(ret_key, "error %s" % (what))
                except StandardError, what:
                    nss.set_result(ret_key, "error %s" % (what))
                else:
                    pj_obj = pending_job_info(ret_key)
                    ret_dict = {}
                    for jri in job_r_dict.keys():
                        q_names = dict([(x, len(y)) for x, y in job_r_dict[jri].queue_dict.iteritems()])
                        host_names = dict([(queue_dict[x].host, y) for x, y in q_names.iteritems()])
                        pj_obj.add_running_job(jri, q_names, host_names)
                    if not machinfo:
                        for host in pj_obj.get_open_hosts():
                            pj_obj.set_host_ok(host, "no info requested", 1)
                    for jwi in job_w_dict.keys():
                        pj_obj.add_waiting_job(jwi, job_w_dict[jwi].get_sq_time())
                    for node in pj_obj.get_open_hosts():
                        nss.new_tcp_connection({"e" : own_queue, "l" : own_queue, "r" : own_queue}, (node, 2001, "get_mvector"), ret_key, timeout = 3.)
                    check_job_dict[ret_key] = pj_obj
                    pass
                log_queue.put(log_ok_message("List of actual pending check_job_objects (%s): %s" % (logging_tools.get_plural("job", len(check_job_dict.keys())),
                                                                                                    ", ".join(["%s" % (str(x)) for x in check_job_dict.keys()]))))
        elif it.m_type == "QL":
            #print it.arg, job_dict.keys()
            queue_raw_str = it.arg
            try:
                queue_idx = queue_raw_str.index("queue")
                q_pre = queue_raw_str[0:queue_idx].strip()
                q_id, q_post = ([x.strip() for x in queue_raw_str[queue_idx + 5:].strip().split(None, 1)] + [""])[0:2]
                q_id = prune_queue_id(q_id)
            except:
                log_queue.put(log_critical_message("error extracting queue_id from '%s': %s (%s)" % (queue_raw_str,
                                                                                                     str(sys.exc_info()[0]),
                                                                                                     str(sys.exc_info()[1]))))
                log_str = None
            else:
                log_str = "%s [queue %s] %s" % (q_pre, q_id, q_post)
                try:
                    sge_queue_cache_object.get_cache_object(q_id).log(sql_queue, log_str)
                except AttributeError:
                    log_queue.put(log_error_message("Error, no sge_queue in cache_object found (q_id is '%s', raw_str '%s')" % (q_id, queue_raw_str)))
        elif it.m_type == "JL":
            #print it.arg, job_dict.keys()
            if type(it.arg) == type(""):
                job_raw_str = it.arg
                try:
                    job_idx = job_raw_str.index("job")
                    j_pre = job_raw_str[0:job_idx].strip()
                    j_id, j_post = ([x.strip() for x in job_raw_str[job_idx + 3:].strip().split(None, 1)] + [""])[0:2]
                    j_id = prune_job_id(j_id)
                except:
                    log_queue.put(log_critical_message("error extracting job_id from '%s': %s (%s)" % (job_raw_str,
                                                                                                       str(sys.exc_info()[0]),
                                                                                                       str(sys.exc_info()[1]))))
                    log_str = None
                else:
                    m = re.match("^(?P<jobnum>\d+)\.(?P<taskid>\d+)(?P<stuff>.*)$", j_id)
                    if m:
                        job_num, task_id = (int(m.group("jobnum")), int(m.group("taskid")))
                    else:
                        try:
                            job_num, task_id = (int(j_id), None)
                        except:
                            job_num, task_id = (0, None)
                            log_queue.put(log_error_message("Error parsing job_num/task_id from '%s' (raw_str was '%s'), using %d/%s" % (j_id,
                                                                                                                                         job_raw_str,
                                                                                                                                         job_num,
                                                                                                                                         str(task_id))))
                    # get list of valid ids
                    valid_task_uids = [x for x in job_dict.keys() if int(x.split(".")[0]) == job_num and len(x.split(".")) == 2]
                    valid_single_uids = [x for x in job_dict.keys() if x == "%d" % (job_num)]
                    if valid_single_uids:
                        task_id = None
                    elif valid_task_uids:
                        if not task_id:
                            task_id = int(valid_task_uids[0].split(".")[1])
                    else:
                        task_id = None
                    j_dict = {"job_num" : job_num}
                    if task_id:
                        job_uid = "%d.%d" % (job_num, task_id)
                        j_dict["task_id"] = task_id
                    else:
                        job_uid = "%d" % (job_num)
                    log_str = "%s [job %s] %s" % (j_pre, job_uid, j_post)
            else:
                job_uid, log_str = (it.arg["job_uid"], it.arg["log_str"])
                j_dict = {"job_uid" : job_uid}
            if log_str:
                get_job(job_uid, db_con, j_dict).log(log_str)
##         elif it.m_type == "JM":
##             j_dict, ret_key = it.arg
##             job_uid = j_dict["job_id"]
##             get_job(job_uid, db_con, j_dict).add_event(j_dict, mon_queue, sql_queue)
##             if ret_key:
##                 nss.set_result(ret_key, "ok")
##         elif it.m_type == "RM":
##             jobs = it.arg
##             for d_job in jobs:
##                 if job_dict.has_key(d_job):
##                     del job_dict[d_job]
##                     log_queue.put(log_ok_message("Remove job '%s' from job_dict, %d jobs left" % (d_job, len(job_dict.keys()))))
##                 else:
##                     log_queue.put(log_warn_message("Cannot remove job '%s' from job_dict (not found)" % (d_job)))
        elif it.m_type in ["msrcv", "mserr"]:
            if it.m_type == "msrcv":
                key, ((loc_ip, loc_port), (source_host, source_port), com), add_data = it.arg
                if add_data in check_job_dict.keys():
                    check_job_dict[add_data].set_host_ok(source_host, com)
                else:
                    log_queue.put(log_ok_message("Got msrcv from host %s (port %d): len %d" % (source_host, source_port, len(com))))
            elif it.m_type == "mserr":
                key, (loc_addr, (source_host, source_port), (err_num, err_str)), add_data = it.arg
                if add_data in check_job_dict.keys():
                    #print source_host
                    check_job_dict[add_data].set_host_error(source_host, err_num, err_str)
                else:
                    log_queue.put(log_error_message("Got mserr %d from host %s (port %d): %s" % (err_num, source_host, sorce_port, err_str)))
        # check for finished check_jobs
        send_keys = [x for x in check_job_dict.keys() if check_job_dict[x].all_hosts_done()]
        for key in send_keys:
            nss.set_result(key, "ok %s" % (sys_to_net(check_job_dict[key].get_dict())))
            del check_job_dict[key]
        if send_keys:
            if check_job_dict:
                log_queue.put(log_ok_message("List of actual pending check_job_objects (%d): %s" % (len(check_job_dict.keys()), ", ".join(["%d" % (x) for x in check_job_dict.keys()]))))
            else:
                log_queue.put(log_ok_message("List of actual pending check_job_objects is empty"))
    del db_con
    if msi_block:
        msi_block.remove_actual_pid()
        msi_block.save_block()
    log_queue.put(log_ok_message("proc %d: %s-thread for %s exiting" % (my_pid,
                                                                        self.__loc_config["SERVER_ROLE"],
                                                                        my_name)))
    main_queue.put(internal_message("exiting"))
    
class dev_name_cache(cache_object):
    def __init__(self, dc):
        cache_object.__init__(self, 3600, 0)
        self.set_cache_miss_object(0)
        self.__dc = dc
    def get_object(self, name):
        self.__dc.execute("SELECT device_idx FROM device WHERE name='%s'" % (name))
        if self.__dc.rowcount:
            return self.__dc.fetchone()["device_idx"]
        else:
            raise IndexError
        
def node_thread_code(main_queue, log_queue, own_queue, mon_queue, job_mon_queue, sql_thread_queue, sge_complexes, nss, keys, msi_block):
    global log_sources
    my_name = threading.currentThread().getName()
    my_pid = os.getpid()
    process_tools.append_pids("sge-server/sge-server")
    log_queue.put(log_ok_message("proc %d: %s-thread for sge-server is now awake" % (my_pid, my_name)))
    if msi_block:
        msi_block.add_actual_pid()
        msi_block.save_block()
    # sge message match-object
    sge_mo = re.compile("^(?P<date>[^\|]+)\|(?P<source>[^\|]+)\|(?P<host>[^\|]+)\|(?P<level>[^\|]+)\|(?P<logstr>.*)$")
    # mapping dictionary
    sge_level_dict = {"E" : "e", "W" : "w", "I" : "i", "C" : "c"}
    tcp_key, udp_key = keys
    log_queue.put(log_ok_message("Port keys: %d (tcp), %d (udp)" % (tcp_key, udp_key)))
    # command dictionary
    com_dict = {"disable"   : {"command" : "qmod -d"   , "object" : "queue", "mail" : True},
                "suspend"   : {"command" : "qmod -s"   , "object" : "queue", "mail" : True},
                "enable"    : {"command" : "qmod -e"   , "object" : "queue"               },
                "unsuspend" : {"command" : "qmod -us"  , "object" : "queue"               },
                "hold"      : {"command" : "qhold -h u", "object" : "job"  , "mail" : True}
                }
    db_con = mysql_tools.db_con()
    db_con.dc.enable_logging(False)
    pe_com_list = ["disable", "suspend", "enable", "unsuspend", "hold", "pe_start", "pe_stop", "job_start", "job_stop", "get_complexes"]
    all_com_list = pe_com_list + ["status"]
    # checked_job dict
    cc_dict = {}
    # cache of name->idx
    dname_cache = dev_name_cache(db_con.dc)
    while True:
        it = own_queue.get()
        if hasattr(it, "type"):
            it.m_type = it.type
        if it.m_type == "I":
            if it.arg == "exit":
                break
            else:
                log_queue.put(log_error_message("Got unknown internal message: %s" % (it.arg)))
        elif it.m_type == "mslog":
            key, ((loc_ip, loc_port), other_addr, log_str), add_data = it.arg
            #print it.arg
            log_queue.put(log_ok_message(log_str))
            m = re.match("^Bind to <(?P<type>\S+)>\s+.*\s+(?P<state>\S+)$", log_str)
            bind_type, bind_state = (None, None)
            if m:
                if m.group("state") in ["ok", "error"]:
                    bind_type, bind_state = (m.group("type").lower(), m.group("state").lower())
            if bind_state:
                main_queue.put(internal_message(("bindstate", loc_port, bind_type, bind_state)))
        elif it.m_type == "mserr":
            key, (loc_addr, other_addr, (errnum, err_str)), add_data = it.arg
            log_queue.put(log_error_message("An error has occured: %d (%s)" % (errnum, err_str)))
        elif it.m_type == "msrcv":
            key, ((loc_ip, loc_port), (source_host, source_port), com), add_data = it.arg
            if key == udp_key:
                ret_key = None
            else:
                ret_key = key
            #print key, host, port, len(com)
            # check for single-string command
            recv_com = None
            if com in all_com_list:
                recv_dict = {"command" : com}
            else:
                try:
                    recv_dict = net_to_sys(com)
                except:
                    log_queue.put(log_error_message("Error unpickling (and server_command) string (key %d) with len %d (first 5 Bytes: '%s') from %s, port %d" % (key, len(com), com[0:5], source_host, source_port)))
                    ret_str = "error unpickling"
                else:
                    try:
                        recv_com = server_command.server_command(com)
                    except:
                        recv_com = None
                    else:
                        recv_dict = None
            if recv_dict or recv_com:
                if recv_dict:
                    command = recv_dict.get("command", None)
                else:
                    command = recv_com.get_command()
                if command:
                    # dummy, FIXME
                    g_config = {}
                    if command == "status":
                        ret_str = check_status_hook()
                    elif command == "get_rms_dicts":
                        sge_dict = dict([(key, g_config[key]) for key in ["SGE_ARCH", "SGE_ROOT", "SGE_CELL"]])
                        queue_dict, job_r_dict, job_s_dict, job_w_dict, ticket_dict, pri_dict = sge_tools.get_all_dicts(sge_complexes.check_out_dict(), [], [], sge_dict, recv_com.get_option_dict(), "")
                        ret_str = str(server_command.server_reply(state=server_command.SRV_REPLY_STATE_OK,
                                                                  result="ok dicts",
                                                                  option_dict = {"queue_dict"       : queue_dict,
                                                                                 "job_run_dict"     : job_r_dict,
                                                                                 "job_suspend_dict" : job_s_dict,
                                                                                 "job_wait_dict"    : job_w_dict,
                                                                                 "ticket_dict"      : ticket_dict,
                                                                                 "priority_dict"    : pri_dict}))
                    elif command in ["delete_jobs", "force_delete_jobs"]:
                        job_list = recv_com.get_option_dict()["job_ids"]
                        call_command(log_queue, "/%s/bin/%s/qdel %s %s" % (g_config["SGE_ROOT"],
                                                                           g_config["SGE_ARCH"],
                                                                           command == "force_delete_jobs" and "-f" or "",
                                                                           " ".join(job_list)))
                        print job_list, command
                        ret_str = server_command.server_reply(state=server_command.SRV_REPLY_STATE_OK,
                                                              result="ok deleted")
                    elif command == "check":
                        if recv_dict["uid"] in [502, 500, 514]:
                            new_check_job = check_job(recv_dict, log_queue, sge_complexes)
                            cc_dict[new_check_job.get_pseudo_id()] = new_check_job
                            ret_str, job_id = (new_check_job.get_return(),
                                               new_check_job.get_pseudo_id())
                            #check_resource_hook(recv_dict, log_queue, new_check_job.get_pseudo_id())
                            new_check_job.close_log()
                        else:
                            ret_str, job_id = check_resource_hook(recv_dict, log_queue, sge_complexes)
                    elif command == "got_id":
                        ret_str = handle_got_id_call(log_queue, cc_dict, recv_dict)
                    elif command == "get_complexes":
                        ret_str = "ok %s" % (sys_to_net(sge_complexes.check_out_dict()))#update_complexes(log_queue)))
                    elif command == "check_job":
                        if recv_dict.has_key("job"):
                            job_mon_queue.put(check_job_message((recv_dict, ret_key, recv_dict.get("machinfo", 0))))
                            ret_str = None
                        else:
                            ret_str = "error need job-id to check"
##                     elif command in pe_com_list:
##                         if com_dict.has_key(command):
##                             ret_str = process_epilogue(log_queue, mon_queue, job_mon_queue, recv_dict, com_dict[command])
##                         else:
##                             if recv_dict.get("origin", "unknown") == "proepilogue":
##                                 #job_mon_queue.put(job_monitor_message((recv_dict, ret_key)))
##                                 ret_str = None
##                             else:
##                                 print "Unknown ", time.time(), command, recv_dict
##                                 ret_str = "ok %s on " % (command)
                    else:
                        ret_str = "error command '%s' unknown" % (command)
                else:
                    if recv_dict.has_key("type") and recv_dict.has_key("hostname") and recv_dict.has_key("lines"):
                        dev_idx = dname_cache.get_cache_object(recv_dict["hostname"])
                        if dev_idx:
                            tot_lines, sge_lines = (0, 0)
                            for line in recv_dict["lines"]:
                                tot_lines += 1
                                # check for generic sge-message
                                if line.count("|") >= 4:
                                    sge_lines += 1
                                    sge_date, sge_source, sge_host, sge_level, sge_str = [x.strip() for x in line.split("|", 4)]
                                    sge_level = sge_level_dict.get(sge_level, "c")
                                    sl_prefix = ""
                                    if sge_str.count("job"):
                                        sl_prefix += "*"
                                        job_mon_queue.put(job_log_message(sge_str))
                                    if sge_str.count("queue"):
                                        sl_prefix += "+"
                                        job_mon_queue.put(queue_log_message(sge_str))
                                    if sge_host != recv_dict["hostname"]:
                                        act_dev_idx = dname_cache.get_cache_object(sge_host)
                                    else:
                                        act_dev_idx = dev_idx
                                    if not log_sources.has_key("sg_%s" % (sge_source)):
                                        process_tools.create_log_source_entry(db_con.dc, 0, "sg_%s" % (sge_source), sge_source, "Generic SGE-Message from %s" % (sge_source))
                                        log_sources = process_tools.get_all_log_sources(db_con.dc)
                                        if log_sources.has_key(sge_source):
                                            log_queue.put(log_ok_message("Added sge_log_source %s successfull" % (sge_source)))
                                        else:
                                            log_queue.put(log_warn_message("Cannot add sge_log_source %s" % (sge_source)))
                                    sge_source = log_sources.get("sg_%s" % (sge_source), log_sources["sgeflat"])
                                    sql_str, sql_tuple = mysql_tools.get_device_log_entry_part(act_dev_idx, sge_source["log_source_idx"], 0, log_status[sge_level]["log_status_idx"], "%s%s" % (sl_prefix, sge_str))
                                    sql_thread_queue.put(sql_thread_message(("IV", "devicelog", sql_str, sql_tuple)))
                                else:
                                    sql_str, sql_tuple = mysql_tools.get_device_log_entry_part(dev_idx, log_sources["sgeflat"]["log_source_idx"], 0, log_status["i"]["log_status_idx"], line)
                                    sql_thread_queue.put(sql_thread_message(("IV", "devicelog", sql_str, sql_tuple)))
                            log_queue.put(log_ok_message("parsed %s (%s from %s), %s%s" % (logging_tools.get_plural("log-line", tot_lines),
                                                                                           recv_dict["type"],
                                                                                           recv_dict["hostname"],
                                                                                           logging_tools.get_plural("sge message", sge_lines),
                                                                                           tot_lines - sge_lines and " (%d other)" % (tot_lines - sge_lines) or "")))
                        else:
                            log_queue.put(log_warn_message("No host named '%s' found in database, logging %s ..." % (recv_dict["hostname"],
                                                                                                                     logging_tools.get_plural("line", len(recv_dict["lines"])))))
                            for line in recv_dict["lines"]:
                                log_queue.put(log_ok_message(" - %s" % (line.strip())))
                        ret_str = "ok got it"
                    else:
                        log_queue.put(log_error_message("Got unknown dict via key %d with %d entries from %s, port %d" % (key, len(recv_dict.keys()), source_host, source_port)))
                        ret_str = "error no command-key / log-message"
            # send return-string only if return-string is given and ret_key is set
            if ret_str:
                if recv_com:
                    nss.set_result(ret_key, ret_str)
                else:
                    if ret_str.startswith("error"):
                        log_queue.put(log_warn_message("*** %s" % (ret_str)))
                        if ret_key:
                            nss.set_result(ret_key, ret_str)
        else:
            log_queue.put(log_ok_message("Got unknown message (type %s)" % (it.m_type)))
    if msi_block:
        msi_block.remove_actual_pid()
        msi_block.save_block()
    del db_con
    log_queue.put(log_ok_message("proc %d: %s-thread for sge-server exiting" % (my_pid, my_name)))
    main_queue.put(internal_message("exiting"))
    
def monitor_thread_code(main_queue, log_queue, own_queue, job_mon_queue, sge_complexes, msi_block):
    # dummy, FIXME
    g_config = {}
    my_name = threading.currentThread().getName()
    my_pid = os.getpid()
    process_tools.append_pids("sge-server/sge-server")
    log_queue.put(log_ok_message("proc %d: %s-thread for sge-server is now awake" % (my_pid, my_name)))
    if msi_block:
        msi_block.add_actual_pid()
        msi_block.save_block()
    esd, nvn = ("/tmp/.machvect_es", "rms_ov")
    write_em = 0
    mon_com = "%s/utilbin/%s/sge_share_mon -c 1 -n -d '$'" % (g_config["SGE_ROOT"], g_config["SGE_ARCH"])
    mon_dir = "/var/spool/sge_fs"
    last_sge_account_time = time.time()
    ced_dict = {}
    rjd_dict = {}
    # jobcheck-dict
    jc_dict = {}
    if g_config["TRACE_FAIRSHARE"]:
        log_queue.put(log_ok_message("tracing of fairshare-tree is enabled"))
    else:
        log_queue.put(log_ok_message("tracing of fairshare-tree is disabled"))
    # init accounting-thread
    acc_queue = Queue.Queue(100)
    acc_thread = threading.Thread(name="accounting", target=accounting_thread, args = [own_queue, log_queue, acc_queue, msi_block, job_mon_queue])
    acc_thread.start()
    c_flag = True
    last_time = None
    last_wakeupcall_end_time = None
    while c_flag:
        act_time = time.time()
        #if last_time:
        #    print "+++ wait, ", time.ctime(last_time), "; ", it.m_type, " took ", act_time-last_time, "(", it.arg, ")"
        it = own_queue.get()
        last_time = time.time()
        if it.m_type == "I":
            if it.arg == "exit":
                c_flag = False
            elif it.arg == "wakeup":
                if last_wakeupcall_end_time and abs(last_wakeupcall_end_time - time.time()) < 10.0:
                    log_queue.put(log_warn_message("wakeup_call to soon after last one (%.2f seconds), ignoring..." % (abs(last_wakeupcall_end_time - time.time()))))
                else:
##                     start_time = time.time()
##                     if not write_em:
##                         write_em = init_em_call(log_queue, esd, nvn)
##                     if write_em:
##                         write_em_call(log_queue, esd, nvn, sge_complexes)
##                     jc_list = []
##                     for key in jc_dict.keys():
##                         jc_dict[key] -= 1
##                         if not jc_dict[key]:
##                             jc_list.append(key)
##                     if jc_list:
##                         for x in jc_list:
##                             del jc_dict[x]
##                         log_queue.put(log_ok_message("Checking accounting for %s (DB-idxs: %s), %s left in check_dict" % (logging_tools.get_plural("job", len(jc_list)),
##                                                                                                                           ", ".join(["%d" % (x) for x in jc_list]),
##                                                                                                                           logging_tools.get_plural("job", len(jc_dict.keys())))))
##                         acc_queue.put(read_accounting_message(jc_list))
##                         #read_sge_accounting(log_queue, jc_list, job_mon_queue)
                    #log_queue.put(log_ok_message("Got wakeup message"))
##                     del_keys = []
##                     for full_name, q_stuff in ced_dict.iteritems():
##                         q_stuff["num"] -= 1
##                         if q_stuff["num"]:
##                             log_strs = ["will clear error of queue %s on host %s (%s) in %d iterations" % (q_stuff["queue"], q_stuff["host"], full_name, q_stuff["num"])]
##                         else:
##                             del_keys.append(full_name)
##                             en_com = "%s/bin/%s/qmod -c %s" % (g_config["SGE_ROOT"], g_config["SGE_ARCH"], full_name)
##                             stat, out = call_command(log_queue, en_com)
##                             out_lines = [x for x in [y.strip() for y in out.strip().split("\n")] if x]
##                             if stat:
##                                 log_strs = ["error executing command %s for queue %s on %s (%d, %s):" % (en_com, q_stuff["queue"], q_stuff["host"], stat, logging_tools.get_plural("line", len(out_lines)))]
##                             else:
##                                 log_strs = ["successfully cleared error of queue %s on host %s (%d, %s)" % (q_stuff["queue"], q_stuff["host"], stat, logging_tools.get_plural("line", len(out_lines)))]
##                             log_strs.extend([" - %s" % (x) for x in out_lines])
##                         for log_str in log_strs:
##                             log_queue.put(log_ok_message(log_str, ["d", "e"]))
##                     for key in del_keys:
##                         del ced_dict[key]
##                     for job_id in rjd_dict.keys():
##                         rjd_dict[job_id] -= 1
##                         if rjd_dict[job_id]:
##                             log_str = "will release job %s in %d iterations" % (job_id, rjd_dict[job_id])
##                         else:
##                             del rjd_dict[job_id]
##                             en_com = "%s/bin/%s/qrls -h u %s" % (g_config["SGE_ROOT"], g_config["SGE_ARCH"], job_id)
##                             stat, out = call_command(log_queue, en_com)
##                             if stat:
##                                 log_str = "error executing command %s on job %s (%d): %s" % (en_com, job_id, stat, out)
##                             else:
##                                 log_str = "successfully released job %s (%d, %s)" % (job_id, stat, out)
##                         log_queue.put(log_ok_message(log_str, ["d", "e"]))
                    act_sge_account_time = time.time()
##                     if act_sge_account_time - g_config["CHECK_ACCOUNTING_TIMEOUT"] > last_sge_account_time:
##                         last_sge_account_time = act_sge_account_time
##                         acc_queue.put(read_accounting_message("CR"))
##                         #read_sge_accounting(log_queue, None, job_mon_queue)
##                     elif act_sge_account_time < last_sge_account_time:
##                         last_sge_account_time = act_sge_account_time
                    if g_config["TRACE_FAIRSHARE"]:
                        stat, out = call_command(log_queue, mon_com)
                        if stat:
                            log_queue.put(log_error_message("Error stat command '%s' resulted in error %d (%s)" % (mon_com, stat, out)))
                        else:
                            time_stamp = None
                            dest_handle = None
                            out_lines = out.strip().split("\n")
                            for line in out_lines:
                                line_p = [x.split("=", 1) for x in line.strip().split("$") if len(x)]
                                line_dict = {}
                                for a, b in line_p:
                                    line_dict[a] = b
                                if line_dict.has_key("curr_time") and not time_stamp:
                                    time_stamp = time.localtime(int(line_dict["curr_time"]))
                                    dest_file = "%s/%04d/%02d/%02d/%02d_%02d_%02d" % (mon_dir, time_stamp[0], time_stamp[1], time_stamp[2], time_stamp[3], time_stamp[4], time_stamp[5])
                                    dest_dir = os.path.dirname(dest_file)
                                    if not os.path.isdir(dest_dir):
                                        try:
                                            os.makedirs(dest_dir)
                                        except:
                                            print sys.exc_info()
                                            time_stamp = None
                                    if time_stamp:
                                        try:
                                            dest_handle = file(dest_file, "w")
                                        except:
                                            dest_handle = None
                                if line_dict.has_key("user_name") and dest_handle:
                                    needed_keys = ["short_target_share", "long_target_share", "actual_share", "level%", "total%"]
                                    user_keys = line_dict.keys()
                                    out_a = []
                                    for key in needed_keys:
                                        if key in user_keys:
                                            out_a.append(line_dict[key])
                                        else:
                                            break
                                    else:
                                        dest_handle.write("%s %s\n" % (line_dict["user_name"], " ".join(out_a)))
                                    #print line_dict["user_name"], line_dict
                            if dest_handle:
                                dest_handle.close()
                    end_time = time.time()
                    last_wakeupcall_end_time = end_time
                    log_queue.put(log_ok_message("wakeup stuff took %.2f seconds" % (end_time - start_time)))
                #print end_time-start_time
            else:
                log_queue.put(log_error_message("Error got unknown internal message %s" % (str(it.arg))))
##         elif it.m_type == "MM":
##             com, stuff = it.arg
##             if com == "clear_queue_delayed":
##                 queue, host, num = stuff
##                 full_name = "%s@%s" % (queue, host)
##                 if not ced_dict.has_key(full_name):
##                     ced_dict[full_name] = {"num" : num, "queue" : queue, "host" : host}
##                     log_str = "add queue %s on host %s (%s) to clear_queue_delayed dict, waiting %d iterations" % (queue, host, full_name, num)
##                     log_queue.put(log_ok_message(log_str, ["d", "e"]))
##                 else:
##                     log_str = "error adding queue %s on host %s (%s) to clear_queue_delayed dict, already there (still %d iterations)" % (queue, host, full_name, ced_dict[full_name]["num"])
##                     log_queue.put(log_error_message(log_str, ["d", "e"]))
##             elif com == "release_job_delayed":
##                 job_id, num = stuff
##                 if not rjd_dict.has_key(job_id):
##                     rjd_dict[job_id] = num
##                     log_str = "add job %s to release_job_delayed dict, waiting %d iterations" % (job_id, num)
##                 else:
##                     log_str = "error adding job %s to release_job_delayed dict, already there (still %d iterations)" % (job_id, rjd_dict[job_id])
##                 log_queue.put(log_ok_message(log_str, ["d", "e"]))
##             elif com == "check_job":
##                 db_idx, job_uid = stuff
##                 jc_dict[db_idx] = g_config["CHECK_ITERATIONS"]
##                 log_queue.put(log_ok_message("Adding job with uid %s to JobCheck-dict (counter: %d)" % (job_uid, jc_dict[db_idx])))
##             else:
##                 log_queue.put(log_error_message("Error got unknown monitor_message com %s" % (com)))
        else:
            log_queue.put(log_error_message("Error got unknown message type %s" % (it.m_type)))
    log_queue.put(log_ok_message("%s-thread got exit, shutting down" % (my_name)))
    for queue in ced_dict.keys():
        del ced_dict[queue]
        en_com = "%s/bin/%s/qmod -c %s" % (g_config["SGE_ROOT"], g_config["SGE_ARCH"], queue)
        stat, out = call_command(log_queue, en_com)
        if stat:
            log_str = "error executing command %s on queue %s (%d): %s" % (en_com, queue, stat, out)
            log_queue.put(log_error_message(log_str, ["d", "e"]))
        else:
            log_str = "successfully cleared error of queue %s (%d, %s)" % (queue, stat, out)
            log_queue.put(log_ok_message(log_str, ["d", "e"]))
##     jc_list = jc_dict.keys()
##     if jc_list:
##         for x in jc_list:
##             del jc_dict[x]
##         log_queue.put(log_ok_message("Checking accounting for %d jobs (DB-idxs: %s)" % (len(jc_list), ", ".join(["%d" % (x) for x in jc_list]))))
##         acc_queue.put(read_accounting_message(jc_list))
##         #read_sge_accounting(log_queue, jc_list, job_mon_queue)
    acc_queue.put(internal_message("exit"))
    while True:
        it = own_queue.get()
        if it.arg == "exiting":
            break
    if write_em:
        try:
            os.unlink("%s/%s.mvd" % (esd, nvn))
            os.unlink("%s/%s.mvv" % (esd, nvn))
        except:
            pass
    if msi_block:
        msi_block.remove_actual_pid()
        msi_block.save_block()
    log_queue.put(log_ok_message("proc %d: %s-thread for sge-server exiting" % (my_pid, my_name)))
    main_queue.put(internal_message("exiting"))
    
def send_mail(from_addr, to_addrs, subject, mail_array):
    new_mail = mail_tools.mail(subject, from_addr, to_addrs, mail_array)
    new_mail.set_server("localhost", "localhost")
    stat, log_lines = new_mail.send_mail()
    del new_mail
    return stat, log_lines

class logging_thread(threading_tools.thread_obj):
    def __init__(self, glob_config, loc_config):
        """ logging thread """
        self.__sep_str = "-" * 50
        self.__glob_config, self.__loc_config = (glob_config, loc_config)
        self.__speciallogs, self.__glob_log, self.__glob_cache = ({}, None, [])
        threading_tools.thread_obj.__init__(self, "logging", queue_size=100, priority=10)
        self.register_func("log", self._log)
        self.register_func("special_log", self._special_log)
        self.register_func("close", self._close)
        self.register_func("set_queue_dict", self._set_queue_dict)
        self.register_func("update", self._update)
        self.register_func("remove_handle", self._remove_handle)
        self.__ad_struct = {}
    def thread_running(self):
        self.send_pool_message(("new_pid", (self.name, self.pid)))
        root = self.__glob_config["LOG_DIR"]
        if not os.path.exists(root):
            os.makedirs(root)
        glog_name = "%s/log" % (root)
        self.__glob_log = logging_tools.logfile(glog_name)
        self.__glob_log.write(self.__sep_str)
        self.__glob_log.write("Opening log")
        self._special_log((self.name, "init", logging_tools.LOG_LEVEL_OK, "job_check"))
        # array of delay-requests
        self.__delay_array = []
    def _delay_request(self, (target_queue, arg, delay)):
        self.log("append to delay_array (delay=%s)" % (logging_tools.get_plural("second", delay)))
        self.__delay_array.append((target_queue, arg, time.time() + delay))
    def _update(self):
        # handle delay-requests
        act_time = time.time()
        new_d_array = []
        for target_queue, arg, r_time in self.__delay_array:
            if r_time < act_time:
                self.log("sending delayed object")
                target_queue.put(arg)
            else:
                new_d_array.append((target_queue, arg, r_time))
        self.__delay_array = new_d_array
    def _set_ad_struct(self, ad_struct):
        self.log("got ad_struct")
        self.__ad_struct = ad_struct
    def _set_queue_dict(self, q_dict):
        self.__queue_dict = q_dict
    def _close(self, special):
        if special in self.__speciallogs.keys():
            self.__speciallogs[special].write("Closing log")
            self.__speciallogs[special].close()
            self._log((self.name,
                       "closing log_key '%s'" % (special),
                       logging_tools.LOG_LEVEL_OK))
        else:
            self._log((self.name,
                       "no log_key '%s' found" % (special),
                       logging_tools.LOG_LEVEL_ERROR))
    def loop_end(self):
        for special in self.__speciallogs.keys():
            self.__speciallogs[special].write("Closing log")
            self.__speciallogs[special].close()
        self.__glob_log.write("Closed %s" % (logging_tools.get_plural("specialine log", len(self.__speciallogs.keys()))))
        self.__glob_log.write("Closing log")
        self.__glob_log.write("logging thread exiting (pid %d)" % (self.pid))
        self.__glob_log.close()
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self._special_log((self.name, what, lev, ""))
    def _log(self, (s_thread, what, lev)):
        self._special_log((s_thread, what, lev, ""))
    def _special_log(self, (s_thread, what, lev, special)):
        if special == "":
            handle, pre_str = (self.__glob_log, "")
        else:
            handle, pre_str = self._get_handle(special)
        if handle is None:
            self.__glob_cache.append((s_thread, what, lev, special))
        else:
            log_act = []
            if self.__glob_cache:
                for c_s_thread, c_what, c_lev, c_special in self.__glob_cache:
                    c_handle, c_pre_str = self._get_handle(c_special)
                    self._handle_log(c_handle, c_s_thread, c_pre_str, c_what, c_lev, c_special)
                self.__glob_cache = []
            self._handle_log(handle, s_thread, pre_str, what, lev, special)
    def _handle_log(self, handle, s_thread, pre_str, what, lev, special):
        if type(what) != type([]):
            what = [what]
        for line in what:
            handle.write("%-5s(%s) : %s%s" % (logging_tools.get_log_level_str(lev),
                                              s_thread,
                                              pre_str,
                                              line))
    def _remove_handle(self, name):
        self.log("Closing log for special %s" % (name))
        self._special_log((self.name, "(%s) : Closing log" % (self.name), logging_tools.LOG_LEVEL_OK, name))
        self.__speciallogs[name].close()
        del self.__speciallogs[name]
    def _get_handle(self, name):
        devname_dict = {}
        if self.__speciallogs.has_key(name):
            handle, pre_str = (self.__speciallogs[name], "")
        else:
            specialdir = "%s/%s" % (self.__glob_config["LOG_DIR"], name)
            if not os.path.exists(specialdir):
                self.log("Creating dir %s for %s" % (specialdir, name))
                os.makedirs(specialdir)
            self.__speciallogs[name] = logging_tools.logfile("%s/log" % (specialdir))
            self.__speciallogs[name].write(self.__sep_str)
            self.__speciallogs[name].write("Opening log")
            #glog.write("# of open specialine logs: %d" % (len(self.__speciallogs.keys())))
            handle, pre_str = (self.__speciallogs[name], "")
        return (handle, pre_str)

class accounting_thread(threading_tools.thread_obj):
    def __init__(self, glob_config, loc_config, db_con, log_queue):
        """ checks accounting information when requested to do so """
        self.__db_con = db_con
        self.__log_queue = log_queue
        self.__glob_config, self.__loc_config = (glob_config, loc_config)
        threading_tools.thread_obj.__init__(self, "accounting", queue_size=200, priority=5)
        self.register_func("set_queue_dict", self._set_queue_dict)
        self.register_func("read_accounting", self._read_accounting)
        self.register_func("set_aj_struct", self._set_aj_struct)
        self.__needed_keys = ["qsub_time", "start_time", "end_time"]
        # all_jobs_struct
        self.__aj_struct = None
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__log_queue.put(("log", (self.name, what, lev)))
    def _set_aj_struct(self, aj_struct):
        self.log("Got aj_struct")
        self.__aj_struct = aj_struct
    def thread_running(self):
        self.send_pool_message(("new_pid", (self.name, self.pid)))
        self.__sge_proj_cache = sge_project_cache(self.__log_queue)
        self.__sge_user_cache_obj = sge_user_cache(self.__log_queue)
        self.__sge_userlist_cache_obj = sge_userlist_cache(self.__log_queue)
    def _set_queue_dict(self, q_dict):
        self.__queue_dict = q_dict
    def _read_accounting(self, job_list):
        start_time = time.time()
        self.log("Starting sge_accounting for %s: %s" % (logging_tools.get_plural("DB idx", len(job_list)),
                                                         ", ".join(["%d" % (x) for x in job_list])))
        unset_jobs = []
        dc = self.__db_con.get_connection(SQL_ACCESS)
        sql_str = "SELECT s.jobnum, s.taskid, s.sge_job_idx, sr.sge_job_run_idx, sr.start_time, sr.end_time FROM sge_job s LEFT JOIN sge_job_run sr ON sr.sge_job = s.sge_job_idx WHERE (%s) ORDER BY sr.sge_job_run_idx" % (" OR ".join(["s.sge_job_idx=%d" % (x) for x in job_list]))
        dc.execute(sql_str)
        if dc.rowcount:
            unset_jobs.extend(list(dc.fetchall()))
        jobs_found = 0
        for job in unset_jobs:
            jobs_found += 1
            #print job
            acct = "-j %d" % (job["jobnum"])
            j_uid = "%d" % (job["jobnum"])
            if job["taskid"]:
                acct = "%s -t %d" % (acct, job["taskid"])
                j_uid = "%s.%d" % (j_uid, job["taskid"])
            stat, out = call_command("qacct %s" % (acct), self.log)
            if stat:
                if job:
                    self.log("Found no accounting-info for job %s" % (j_uid), logging_tools.LOG_LEVEL_WARN)
            else:
                j_ins_f = []
                jr_ins_f = {}
                out_d = dict([y for y in [x.strip().split(None, 1) for x in out.split("\n")] if len(y) > 1])
                for kn in self.__needed_keys:
                    if not kn in out_d.keys():
                        break
                else:
                    if out_d["qsub_time"] != "-/-":
                        try:
                            qsub_time = time.strptime(out_d["qsub_time"])
                        except ValueError:
                            self.log("Error parsing qsub-time %s" % (out_d["qsub_time"]), logging_tools.LOG_LEVEL_ERROR)
                        else:
                            j_ins_f.append("queue_time='%s'" % (time.strftime("%Y-%m-%d %H:%M:%S", qsub_time)))
                    for k in ["start_time", "end_time"]:
                        if out_d[k] != "-/-":
                            try:
                                x_time = time.strptime(out_d[k])
                            except ValueError:
                                self.log("Error parsing %s %s" % (k, out_d[k]), logging_tools.LOG_LEVEL_ERROR)
                            else:
                                jr_ins_f["%s_sge" % (k)] = time.strftime("%Y-%m-%d %H:%M:%S", x_time)
                    # check for optional keys
                    if out_d.has_key("exit_status"):
                        jr_ins_f["exit_status"] = out_d["exit_status"]
                    if out_d.has_key("failed"):
                        jf = out_d["failed"].split(":", 1)
                        if len(jf) > 1:
                            jfailed = int(jf[0].strip())
                            jfstr = jf[1].strip()
                        else:
                            jfailed = int(jf[0])
                            jfstr = ""
                        jr_ins_f["failed"] = jfailed
                        jr_ins_f["failed_str"] = jfstr
                    if out_d.has_key("account"):
                        jr_ins_f["account"] = out_d["account"]
                    if out_d.has_key("owner"):
                        sge_user_idx = self.__sge_user_cache_obj.get_cache_object(dc, out_d["owner"].strip())
                        if sge_user_idx:
                            j_ins_f.append("sge_user=%d" % (sge_user_idx))
                    if out_d.has_key("project"):
                        sge_prj_idx = self.__sge_proj_cache.get_cache_object(dc, out_d["project"].strip())
                        if sge_prj_idx:
                            jr_ins_f["sge_project"] = sge_prj_idx
                    if out_d.has_key("department"):
                        sge_dep_idx = self.__sge_userlist_cache_obj.get_cache_object(dc, (out_d["department"].strip(), "DEPT"))
                        if sge_dep_idx:
                            jr_ins_f["sge_userlist"] = sge_dep_idx
                    if out_d.has_key("ru_wallclock"):
                        jr_ins_f["sge_ru_wallclock"] = out_d["ru_wallclock"]
                    if out_d.has_key("cpu"):
                        jr_ins_f["sge_cpu"] = out_d["cpu"]
                    if out_d.has_key("mem"):
                        jr_ins_f["sge_mem"] = float(out_d["mem"])
                    if out_d.has_key("io"):
                        jr_ins_f["sge_io"] = float(out_d["io"])
                    if out_d.has_key("iow"):
                        jr_ins_f["sge_iow"] = float(out_d["iow"])
                    if out_d.has_key("maxvmem"):
                        mvm = out_d["maxvmem"]
                        if mvm.endswith("M"):
                            mvm = float(mvm[:-1])
                        elif mvm.endswith("G"):
                            mvm = float(mvm[:-1])*1024.
                        else:
                            mvm = float(mvm[:-1])
                        jr_ins_f["sge_maxvmem"] = mvm
                    ins_f = []
                    if j_ins_f and job["sge_job_idx"]:
                        dc.execute("UPDATE sge_job SET %s WHERE sge_job_idx=%d" % (", ".join(j_ins_f), job["sge_job_idx"]))
                        ins_f.append("job %d" % (job["sge_job_idx"]))
                    if jr_ins_f and job["sge_job_run_idx"]:
                        jr_ins_f["sge_parsed"] = 1
                        jr_ins_f_keys = jr_ins_f.keys()
                        sql_str, sql_tuple = ("UPDATE sge_job_run SET %s WHERE sge_job_run_idx=%d" % (", ".join(["%s=%%s" % (x) for x in jr_ins_f_keys]), job["sge_job_run_idx"]),
                                              [jr_ins_f[x] for x in jr_ins_f_keys])
                        dc.execute(sql_str, tuple(sql_tuple))
                        ins_f.append("job_run %d" % (job["sge_job_run_idx"]))
                    if ins_f:
                        self.log("Inserted accounting-info for job %s (%s)" % (j_uid, " and ".join(ins_f)))
                        del self.__aj_struct[j_uid]
                    # removed EXT_ACCOUNTING_HOOK (never used)
##                     ext_hook = g_config["EXT_ACCOUNTING_HOOK"]
##                     if ext_hook:
##                         # check hook_mapping
##                         exp_f = []
##                         for k, v in hook_mapping.iteritems():
##                             if out_d.has_key(k):
##                                 exp_f.append("%s='%s'" % (v, str(out_d[k])))
##                             else:
##                                 log_queue.put(log_warn_message("Key %s not found in dictionary" % (k)))
##                         # hook

##                         stat, out = call_command(log_queue, "export %s ; /tmp/test.sh " % (" ".join(exp_f)))
##                         if stat:
##                             log_queue.put(log_error_message("Calling external accounting_hook '%s' resulted in an error (%d): %s" % (ext_hook, stat, out)))
##                         else:
##                             log_queue.put(log_ok_message("Calling external accounting_hook '%s' result (ok): %s" % (ext_hook, out)))
        end_time = time.time()
        self.log(" ... sge_accounting took %s (%s)" % (logging_tools.get_diff_time_str(end_time - start_time),
                                                       logging_tools.get_plural("job", jobs_found)))
        dc.release()

class monitor_thread(threading_tools.thread_obj):
    def __init__(self, glob_config, loc_config, db_con, log_queue, sge_tools):
        """ monitors running jobs and writes information for host-monitoring (only time-consuming stuff) """
        self.__db_con = db_con
        self.__log_queue = log_queue
        self.__sge_tools = sge_tools
        self.__glob_config, self.__loc_config = (glob_config, loc_config)
        threading_tools.thread_obj.__init__(self, "monitor", queue_size=200)
        self.register_func("set_queue_dict", self._set_queue_dict)
        self.register_func("update", self._update)
        self.register_func("check_job_accounting_delayed", self._check_job_accounting_delayed)
        self.register_func("clear_queue_delayed", self._clear_queue_delayed)
        self.register_func("release_job_delayed", self._release_job_delayed)
        self.register_func("set_aj_struct", self._set_aj_struct)
        # job check dict for delayed accounting reporting
        self.__jc_dict = {}
        self.__last_wakeupcall_end_time = None
        self.__write_em_ok = False
        self.__esd, self.__nvn = ("/tmp/.machvect_es", "rms_ov")
        # clear queue / release job dict
        self.__clear_q_dict, self.__release_j_dict = ({}, {})
        # all_jobs_struct
        self.__aj_struct = None
        self._init_sge_info()
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK, special=[]):
        if not special:
            self.__log_queue.put(("log", (self.name, what, lev)))
        else:
            for spec in special:
                self.__log_queue.put(("special_log", (self.name, what, lev, spec)))
    def thread_running(self):
        self.send_pool_message(("new_pid", (self.name, self.pid)))
    def _set_queue_dict(self, q_dict):
        self.__queue_dict = q_dict
    def _set_aj_struct(self, aj_struct):
        self.log("Got aj_struct")
        self.__aj_struct = aj_struct
    def _init_sge_info(self):
        self.log("init sge_info")
        self.__sge_info = sge_tools.sge_info(log_command=self.log,
                                             run_initial_update=False,
                                             sge_dict=dict([(key, self.__glob_config[key]) for key in ["SGE_ARCH", "SGE_ROOT", "SGE_CELL"]]))
    def loop_end(self):
        self._check_jobs_for_accounting(True)
        self._clear_error_queues(True)
        self._release_hold_jobs(True)
    def _check_job_accounting_delayed(self, (job_db_idx, job_uid)):
        self.__jc_dict[job_db_idx] = self.__glob_config["CHECK_ITERATIONS"]
        self.log("Adding job with uid %s to JobCheck-dict (counter: %d)" % (job_uid, self.__jc_dict[job_db_idx]))
    def _update(self):
        act_time = time.time()
        if self.__last_wakeupcall_end_time and abs(self.__last_wakeupcall_end_time - act_time) < 10.0:
            self.log("wakeup_call to soon after last one (%s), ignoring..." % (logging_tools.get_diff_time_str(abs(self.__last_wakeupcall_end_time - act_time))),
                     logging_tools.LOG_LEVEL_WARN)
        else:
            start_time = time.time()
            # em_call (external monitor)
            if not self.__write_em_ok:
                self._init_em_call()
            if self.__write_em_ok:
                self._write_em_call()
            # delayed accounting check
            self._check_jobs_for_accounting()
            # clear queue dict
            self._clear_error_queues()
            # clear queue dict
            self._release_hold_jobs()
            end_time = time.time()
            self.log("wakeup stuff took %s" % (logging_tools.get_diff_time_str(end_time - start_time)))
    def _clear_queue_delayed(self, (queue_name, source_host, delay_count)):
        full_name = "%s@%s" % (queue_name, source_host)
        if not self.__clear_q_dict.has_key(full_name):
            self.__clear_q_dict[full_name] = {"num"   : delay_count,
                                              "queue" : queue_name,
                                              "host"  : source_host}
            self.log("add queue %s on host %s (%s) to clear_queue_delayed dict, waiting %d iterations" % (queue_name, source_host, full_name, delay_count),
                     special=["", "d", "e"])
        else:
            self.log("error adding queue %s on host %s (%s) to clear_queue_delayed dict, already there (still %d iterations)" % (queue_name, source_host, full_name, self.__clear_q_dict[full_name]["num"]),
                     logging_tools.LOG_LEVEL_WARN,
                     ["d", "e"])
    def _release_job_delayed(self, (job_id, delay_count)):
        if not self.__release_j_dict.has_key(job_id):
            self.__release_j_dict[job_id] = {"num" : delay_count}
            self.log("add job %s to release_job_delayed dict, waiting %d iterations" % (job_id, delay_count),
                     special=["d", "e"])
        else:
            self.log("error adding job %s to release_job_delayed dict, already there (still %d iterations)" % (job_id, self.__release_j_dict[job_id]),
                     logging_tools.LOG_LEVEL_WARN,
                     ["d", "e"])
    def _init_em_call(self):
        if not self.__write_em_ok:
            if os.path.isdir(self.__esd):
                self.log("initialising external machvector_data (dir %s, file %s)" % (self.__esd, self.__nvn))
                try:
                    file("%s/%s.mvd" % (self.__esd, self.__nvn), "w").write("\n".join(["rms.jobs.tot:0:Total jobs:1:1:1",
                                                                                       "rms.jobs.running:0:Total jobs running:1:1:1",
                                                                                       "rms.jobs.waiting:0:Total jobs waiting:1:1:1",
                                                                                       "rms.slots.tot:0:Total slots configured:1:1:1",
                                                                                       "rms.slots.present:0:Total slots (running + waiting):1:1:1",
                                                                                       "rms.slots.running:0:Total slots running:1:1:1",
                                                                                       "rms.slots.waiting:0:Total slots waiting:1:1:1",
                                                                                       "rms.queues.tot:0:Total queues:1:1:1",
                                                                                       "rms.queues.alarm:0:Total queues in alarm state:1:1:1",
                                                                                       "rms.queues.free:0:Total queues free:1:1:1",
                                                                                       "rms.queues.used:0:Total queues used:1:1:1",
                                                                                       "rms.queues.pused:0:Total queues partially used:1:1:1",
                                                                                       "rms.queues.subordinated:0:Total queues subordinated:1:1:1",
                                                                                       "rms.queues.suspended:0:Total queues suspended:1:1:1",
                                                                                       "rms.queues.disabled:0:Total queues disabled:1:1:1",
                                                                                       "rms.queues.unknown:0:Total queues in unknown state:1:1:1",
                                                                                       ""]))
                except:
                    self.log(" ... error: %s" % (process_tools.get_except_info()),
                             logging_tools.LOG_LEVEL_ERROR)
                else:
                    self.__write_em_ok = True
    def _write_em_call(self):
        start_time = time.time()
        # init dicts
        queue_rep_dict = dict([(key, 0) for key in ["tot", "alarm", "free", "used", "pused", "sub", "susp", "d", "unk"]])
        slot_dict      = dict([(key, 0) for key in ["tot", "run", "wait"]])
        job_dict       = dict([(key, 0) for key in ["tot", "run", "wait"]])
        try:
            self.__sge_info.update(no_file_cache=True, force_update=True)
        except ValueError, what:
            self.log("*** ValueError for write_em_call() %s: %s" % (str(what),
                                                                    process_tools.get_except_info()),
                     logging_tools.LOG_LEVEL_CRITICAL)
        except StandardError, what:
            self.log("*** StandardError for write_em_call() %s: %s" % (str(what),
                                                                       process_tools.get_except_info()),
                     logging_tools.LOG_LEVEL_CRITICAL)
        else:
            host_dict = {}
            # jobs
            for j_id, j_stuff in self.__sge_info["qstat"].iteritems():
                # job
                job_dict["tot"] += 1
                try:
                    if j_stuff.running:
                        # job running
                        job_dict["run"] += 1
                        slot_dict["run"] += len(j_stuff["queue_name"])
                    else:
                        job_dict["wait"] += 1
                        if j_stuff.has_key("requested_PE"):
                            slot_dict["wait"] += int(j_stuff["requested_PE"][0]["value"])
                        else:
                            slot_dict["wait"] += 1
                except:
                    self.log("error accounting job %s: %s" % (j_id,
                                                              process_tools.get_except_info()),
                             logging_tools.LOG_LEVEL_ERROR)
            # hosts
            for h_name, h_stuff in self.__sge_info["qhost"].iteritems():
                for q_name, q_stuff in h_stuff.get("queues", {}).iteritems():
                    # one host
                    queue_rep_dict["tot"] += 1
                    try:
                        # count slots
                        slot_dict["tot"] += q_stuff["total"]
                        if q_stuff["used"] == 0:
                            # free
                            queue_rep_dict["free"] += 1
                        elif q_stuff["used"] == q_stuff["total"]:
                            # used (full)
                            queue_rep_dict["used"] += 1
                        else:
                            # partial used
                            queue_rep_dict["pused"] += 1
                        if "a" in q_stuff["status"]:
                            # alarm state
                            queue_rep_dict["alarm"] += 1
                        if "S" in q_stuff["status"]:
                            # subordinated
                            queue_rep_dict["sub"] += 1
                        if "s" in q_stuff["status"]:
                            # suspended
                            queue_rep_dict["susp"] += 1
                        if "d" in q_stuff["status"]:
                            # disabled
                            queue_rep_dict["d"] += 1
                        if "u" in q_stuff["status"]:
                            # unknown
                            queue_rep_dict["unk"] += 1
                    except:
                        self.log("error accounting queue %s @ node %s: %s" % (q_name,
                                                                              h_name,
                                                                              process_tools.get_except_info()),
                                 logging_tools.LOG_LEVEL_ERROR)
            open("%s/%s.mvv" % (self.__esd, self.__nvn), "w").write("\n".join(["rms.jobs.tot:i:%d" % (job_dict["tot"]),
                                                                               "rms.jobs.running:i:%d" % (job_dict["run"]),
                                                                               "rms.jobs.waiting:i:%d" % (job_dict["wait"]),
                                                                               "rms.slots.tot:i:%d" % (slot_dict["tot"]),
                                                                               "rms.slots.present:i:%d" % (slot_dict["run"] + slot_dict["wait"]),
                                                                               "rms.slots.running:i:%d" % (slot_dict["run"]),
                                                                               "rms.slots.waiting:i:%d" % (slot_dict["wait"]),
                                                                               "rms.queues.tot:i:%d" % (queue_rep_dict["tot"]),
                                                                               "rms.queues.alarm:i:%d" % (queue_rep_dict["alarm"]),
                                                                               "rms.queues.free:i:%d" % (queue_rep_dict["free"]),
                                                                               "rms.queues.used:i:%d" % (queue_rep_dict["used"]),
                                                                               "rms.queues.pused:i:%d" % (queue_rep_dict["pused"]),
                                                                               "rms.queues.subordinated:i:%d" % (queue_rep_dict["sub"]),
                                                                               "rms.queues.suspended:i:%d" % (queue_rep_dict["susp"]),
                                                                               "rms.queues.disabled:i:%d" % (queue_rep_dict["d"]),
                                                                               "rms.queues.unknown:i:%d" % (queue_rep_dict["unk"]),
                                                                               ""]))
        end_time = time.time()
        self.log("write_em_call() took %s, %d queues total, %d jobs total" % (logging_tools.get_diff_time_str(end_time - start_time),
                                                                              queue_rep_dict["tot"],
                                                                              job_dict["tot"]))
    def _check_jobs_for_accounting(self, force=False):
        jc_list = []
        for key in self.__jc_dict.keys():
            self.__jc_dict[key] -= 1
            if not self.__jc_dict[key] or force:
                jc_list.append(key)
        if jc_list:
            jc_list.sort()
            for x in jc_list:
                del self.__jc_dict[x]
            self.log("Checking accounting for %s (DB-idxs: %s), %s left in check_dict" % (logging_tools.get_plural("job", len(jc_list)),
                                                                                          ", ".join(["%d" % (x) for x in jc_list]),
                                                                                          logging_tools.get_plural("job", len(self.__jc_dict.keys()))))
            self.__queue_dict["acc_queue"].put(("read_accounting", jc_list))
    def _clear_error_queues(self, force=False):
        del_keys, log_strs = ([], [])
        for full_name, q_stuff in self.__clear_q_dict.iteritems():
            q_stuff["num"] -= 1
            if q_stuff["num"] and not force:
                log_strs.append("will clear error of queue %s on host %s (%s) in %d iterations" % (q_stuff["queue"], q_stuff["host"], full_name, q_stuff["num"]))
            else:
                del_keys.append(full_name)
                en_com = "%s/bin/%s/qmod -c %s" % (self.__glob_config["SGE_ROOT"], self.__glob_config["SGE_ARCH"], full_name)
                stat, out = call_command(en_com, self.log)
                out_lines = out.split("\n")
                if not stat:
                    log_strs.append("successfully cleared error of queue %s on host %s (%s):" % (q_stuff["queue"],
                                                                                                 q_stuff["host"],
                                                                                                 logging_tools.get_plural("line", len(out_lines))))
                    log_strs.extend([" - %s" % (log_line) for log_line in out_lines])
        for log_str in log_strs:
            self.log(log_str, special=["d", "e"])
        for key in del_keys:
            del self.__clear_q_dict[key]
    def _release_hold_jobs(self, force=False):
        del_keys, log_strs = ([], [])
        for job_id, job_stuff in self.__release_j_dict.keys():
            job_stuff["num"] -= 1
            if job_stuff["num"] and not force:
                log_strs.append("will release job %s in %d iterations" % (job_id, job_stuff["num"]))
            else:
                del_keys.append(job_id)
                en_com = "%s/bin/%s/qrls -h u %s" % (self.__glob_config["SGE_ROOT"], self.__glob_config["SGE_ARCH"], job_id)
                stat, out = call_command(en_com, self.log)
                out_lines = out.split("\n")
                if not stat:
                    log_strs.append("successfully released job %s (%s)" % (job_id, logging_tools.get_plural("line", len(out_lines))))
                    log_strs.extend([" - %s" % (log_line) for log_line in out_lines])
        for log_str in log_strs:
            self.log(log_str, special=["d", "e"])
        for key in del_keys:
            del self.__release_j_dict[key]
        
class job_monitor_thread(threading_tools.thread_obj):
    def __init__(self, glob_config, loc_config, db_con, log_queue):
        """ handles requests from jobs """
        self.__db_con = db_con
        self.__log_queue = log_queue
        self.__glob_config, self.__loc_config = (glob_config, loc_config)
        threading_tools.thread_obj.__init__(self, "job_monitor", queue_size=200)
        self.register_func("set_queue_dict", self._set_queue_dict)
        self.register_func("job_com", self._job_com)
        self.register_func("set_aj_struct", self._set_aj_struct)
        # all_jobs_struct
        self.__aj_struct = None
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK, special=[]):
        if not special:
            self.__log_queue.put(("log", (self.name, what, lev)))
        else:
            for spec in special:
                self.__log_queue.put(("special_log", (self.name, what, lev, spec)))
    def thread_running(self):
        self.send_pool_message(("new_pid", (self.name, self.pid)))
        self.__dc = self.__db_con.get_connection(SQL_ACCESS)
    def loop_end(self):
        self.__dc.release()
    def _set_queue_dict(self, q_dict):
        self.__queue_dict = q_dict
    def _set_aj_struct(self, aj_struct):
        self.log("Got aj_struct")
        self.__aj_struct = aj_struct
    def _job_com(self, (tcp_obj, s_com)):
        command, opt_dict = (s_com.get_command(), s_com.get_option_dict())
        self._get_job(opt_dict).add_event(self.__dc, command, opt_dict)
        if tcp_obj:
            tcp_obj.add_to_out_buffer(server_command.server_reply(state=server_command.SRV_REPLY_STATE_OK,
                                                                  result="ok"))
    def _get_job(self, job_dict):
        job_uid = job_dict["job_id"]
        if self.__aj_struct.has_key(job_uid):
            act_job = self.__aj_struct[job_uid]
        else:
            act_job = job(self.__aj_struct, job_dict, self.__dc, self.__queue_dict)
            self.__aj_struct[job_uid] = act_job
        return act_job

class node_thread(threading_tools.thread_obj):
    def __init__(self, glob_config, loc_config, db_con, log_queue, sge_tools):
        """ receives requests from external sources """
        self.__sge_tools = sge_tools
        self.__db_con = db_con
        self.__log_queue = log_queue
        self.__glob_config, self.__loc_config = (glob_config, loc_config)
        threading_tools.thread_obj.__init__(self, "node", queue_size=200)
        self.register_func("set_queue_dict", self._set_queue_dict)
        self.register_func("con", self._con)
        self.register_func("set_aj_struct", self._set_aj_struct)
        self.register_func("send_tcp_return", self._send_tcp_return)
        self.register_func("update", self._update)
        self.register_func("set_netserver", self._set_netserver)
        self.register_func("udp_data", self._udp_data)
        self.register_func("job_log", self._job_log)
        # all_jobs_struct
        self.__aj_struct = None
        self.__com_dict = {"disable"   : {"command"   : "qmod -d",
                                          "object"    : "queue",
                                          "send_mail" : True},
                           "suspend"   : {"command"   : "qmod -s",
                                          "object"    : "queue",
                                          "send_mail" : True},
                           "enable"    : {"command"   : "qmod -e",
                                          "object"    : "queue"},
                           "unsuspend" : {"command"   : "qmod -us",
                                          "object"    : "queue"},
                           "hold"      : {"command"   : "qhold -h u",
                                          "object"    : "job",
                                          "send_mail" : True}}
        # init cache objects
        self._init_sge_cache_objects()
        self._init_sge_info()
        # setserver
        self.__ns = None
        self._test()
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK, special=[]):
        if not special:
            self.__log_queue.put(("log", (self.name, what, lev)))
        else:
            for spec in special:
                self.__log_queue.put(("special_log", (self.name, what, lev, spec)))
    def _test(self):
        return
        self._add_log_entry("quad", "quad01", "XX", "testentry")
        for line in open("/opt/sge60/zephcell/spool/qmaster/messages", "r").read().split("\n"):
            if line.strip():
                self._handle_content_line(line)
    def thread_running(self):
        self.send_pool_message(("new_pid", (self.name, self.pid)))
        #self.__dc = self.__db_con.get_connection(SQL_ACCESS)
    def _set_netserver(self, ns):
        self.log("got netserver")
        self.__ns = ns
    def _init_sge_cache_objects(self):
        self.__queue_cache = sge_queue_cache(self.__log_queue, self.__glob_config)
        self.__host_cache = sge_host_cache(self.__log_queue, self.__glob_config)
    def _init_sge_info(self):
        self.log("init sge_info")
        self.__sge_info = sge_tools.sge_info(log_command=self.log,
                                             run_initial_update=False,
                                             verbose=True if not self.__loc_config["DAEMON"] else False,
                                             sge_dict=dict([(key, self.__glob_config[key]) for key in ["SGE_ARCH", "SGE_ROOT", "SGE_CELL"]]))
        self._update()
    def _update(self):
        self.__sge_info.update(no_file_cache=True, force_update=True)
    def _update_selective(self, upd_list):
        self.__sge_info.update(no_file_cache=True, force_update=True, update_list=upd_list)
    def _set_aj_struct(self, aj_struct):
        self.log("Got aj_struct")
        self.__aj_struct = aj_struct
    def _set_queue_dict(self, q_dict):
        self.__queue_dict = q_dict
    def _udp_data(self, (src, in_data)):
        try:
            net_result = server_command.net_to_sys(in_data)
        except:
            self.log("got unparseable data from %s" % (str(src)),
                     logging_tools.LOG_LEVEL_ERROR)
        else:
            self._handle_possible_log_request(net_result)
    def _handle_possible_log_request(self, in_dict):
        """ parse log requests and insert them into the sge_log """
        if set(in_dict.keys()).issuperset(set(["content", "host", "id"])):
            for line in in_dict["content"]:
                self._handle_content_line(line)
        else:
            self.log("not enough keys in dict: %s" % (", ".join(sorted(in_dict.keys()))),
                     logging_tools.LOG_LEVEL_ERROR)
    def _handle_content_line(self, in_line):
        try:
            l_parts = in_line.split("|", 4)
            sql_date = l_parts[0]
            sql_dp = sql_date.split()[0].split("/")
            sql_date = "%s-%s-%s %s" % (sql_dp[2], sql_dp[0], sql_dp[1], sql_date.split()[1])
            log_level = {"e" : logging_tools.LOG_LEVEL_ERROR,
                         "c" : logging_tools.LOG_LEVEL_CRITICAL,
                         "w" : logging_tools.LOG_LEVEL_WARN,
                         "i" : logging_tools.LOG_LEVEL_OK}.get(l_parts[3].lower(), logging_tools.LOG_LEVEL_ERROR)
            found_names = {"queue" : "",
                           "host"  : l_parts[2].split(".")[0],
                           "job"   : ""}
            prev_part = ""
            for part in l_parts[4].lower().split():
                if prev_part == "queue":
                    found_names["queue"] = part
                elif prev_part in ["job"]:
                    if part not in ["does"]:
                        found_names["job"] = part
                elif prev_part in ["host"]:
                    found_names["host"] = part.split(".")[0]
                prev_part = part
            # sanitize stuff
            for key, value in found_names.iteritems():
                if value:
                    if value.endswith("'s"):
                        value = value[:-2]
                    if value[0] in ["'", '"']:
                        value = value[1:]
                    if value[-1] in ["'", '"']:
                        value = value[:-1]
                found_names[key] = value
            if found_names["queue"].count("@"):
                found_names["queue"], found_names["host"] = (found_names["queue"].split("@")[0],
                                                             found_names["queue"].split("@")[1].split(".")[0])
            # check for real job_id (task_id is sometimes logged, somtimes not)
            j_name = found_names["job"]
            if j_name:
                if j_name in self.__aj_struct.keys():
                    # match
                    pass
                elif not j_name.count(".") and "%s.1" % (j_name) in self.__aj_struct.keys():
                    # real job_name is task_job
                    found_names["job"] = "%s.1" % (j_name)
                elif j_name.count(".") and j_name.split(".")[0] in self.__aj_struct.keys():
                    # real job_name has no task_id
                    found_names["job"] = j_name.split(".")[0]
            # debug code
            if False:
                print "%-14s:%-14s:%-14s: %s" % (found_names["queue"],
                                                 found_names["host"],
                                                 found_names["job"],
                                                 in_line)
                print "*", found_names, self.__aj_struct.keys()
            if self.__aj_struct.has_key(found_names["job"]):
                job_idx = self.__aj_struct[found_names["job"]].sge_job_idx
            else:
                job_idx = 0
            self._add_log_entry(found_names["queue"],
                                found_names["host"],
                                job_idx,
                                l_parts[4],
                                log_level,
                                sql_date=sql_date)
        except:
            self.log("unable to parse line '%s': %s" % (in_line,
                                                        process_tools.get_except_info()),
                     logging_tools.LOG_LEVEL_ERROR)
    def _job_log(self, (job_idx, queue_name, host_name, log_str, log_level)):
        # called from job_struct
        self._add_log_entry(queue_name, host_name, job_idx, log_str, log_level)
    def _add_log_entry(self, q_name, h_name, job_id, log_text, log_level=logging_tools.LOG_LEVEL_OK, **args):
        dc = self.__db_con.get_connection(SQL_ACCESS)
        if q_name:
            queue_idx = self.__queue_cache.get_cache_object(dc, q_name)["sge_queue_idx"]
        else:
            queue_idx = 0
        if h_name:
            host_idx = self.__host_cache.get_cache_object(dc, h_name)["sge_host_idx"]
        else:
            host_idx = 0
        if type(job_id) != type(""):
            job_idx = job_id
        else:
            # get job_idx, FIXME
            if self.__aj_struct.has_key(job_id):
                job_idx = self.__aj_struct[job_id].sge_job_idx
            else:
                self.log("cannot get job_idx of job_id %s" % (job_id),
                         logging_tools.LOG_LEVEL_WARN)
                job_idx = 0
        sql_str, sql_tuple = ("INSERT INTO sge_log SET sge_job=%s, sge_queue=%s, sge_host=%s, log_level=%s, log_str=%s",
                              (job_idx,
                               queue_idx,
                               host_idx,
                               log_level,
                               log_text))
        if args.has_key("sql_date"):
            sql_str = "%s, date=%%s" % (sql_str)
            sql_tuple = tuple(list(sql_tuple) + [args["sql_date"]])
        dc.execute(sql_str, sql_tuple)
        dc.release()
    def _con(self, tcp_obj):
        server_com = tcp_obj.get_decoded_in_str()
        if type(server_com) == type(""):
            try:
                net_result = server_command.net_to_sys(server_com)
            except:
                tcp_obj.add_to_out_buffer("no valid server_command")
                self.log("Got invalid data (non-server_com) from host %s (port %d), starting with %s" % (tcp_obj.get_src_host(),
                                                                                                         tcp_obj.get_src_port(),
                                                                                                         server_com[0:10]),
                         logging_tools.LOG_LEVEL_WARN)
            else:
                # from tail_follow_thread
                tcp_obj.add_to_out_buffer("ok got it", "net_object")
                self._handle_possible_log_request(net_result)
        else:
            srv_com_name = server_com.get_command()
            call_func = {"status"             : self._status,
                         "job_start"          : self._job_com,
                         "job_stop"           : self._job_com,
                         "pe_start"           : self._job_com,
                         "pe_stop"            : self._job_com,
                         "disable"            : self._process_special_command,
                         "suspend"            : self._process_special_command,
                         "enable"             : self._process_special_command,
                         "unsuspend"          : self._process_special_command,
                         "hold"               : self._process_special_command,
                         "delete_jobs"        : self._delete_jobs,
                         "force_delete_jobs"  : self._delete_jobs,
                         "file_watch_content" : self._file_watch_content,
                         "check_submit_job"   : self._check_submit_job,
                         "check_job"          : self._check_job,
                         "got_final_job_id"   : self._got_final_job_id,
                         "get_complexes"      : self._get_complexes,
                         "get_config"         : self._get_config,
                         "call_qconf"         : self._call_qconf}.get(srv_com_name, None)
            if call_func:
                call_func(tcp_obj, server_com)
            else:
                self.log("Got unknown server_command '%s' from host %s (port %d)" % (srv_com_name,
                                                                                     tcp_obj.get_src_host(),
                                                                                     tcp_obj.get_src_port()),
                         logging_tools.LOG_LEVEL_WARN)
                res_str = "unknown command %s" % (srv_com_name)
                tcp_obj.add_to_out_buffer(server_command.server_reply(state=server_command.SRV_REPLY_STATE_ERROR, result=res_str))
    def _file_watch_content(self, tcp_obj, s_com):
        opt_dict = s_com.get_option_dict()
        f_name, f_content, fw_id, f_update = (opt_dict.get("name"   , ""),
                                              opt_dict.get("content", ""),
                                              opt_dict.get("id"     , ""),
                                              opt_dict.get("update" , time.time()))
        if fw_id.count(":"):
            job_id, fw_id = fw_id.split(":", 1)
            self.__aj_struct.lock()
            if not self.__aj_struct.has_key(job_id):
                # try to resurrect the job
                dc = self.__db_con.get_connection(SQL_ACCESS)
                self.__aj_struct[job_id] = job(self.__aj_struct,
                                               {"job_id" : job_id},
                                               dc,
                                               self.__queue_dict)
                dc.release()
            if self.__aj_struct.has_key(job_id):
                self.__aj_struct[job_id].set_file_watch_content(fw_id, f_name, f_content, f_update)
                state, result = (server_command.SRV_REPLY_STATE_OK, "ok set content")
            else:
                state, result = (server_command.SRV_REPLY_STATE_ERROR, "job with job_id '%s' not found" % (job_id))
            self.__aj_struct.release()
        else:
            state, result = (server_command.SRV_REPLY_STATE_ERROR, "id has wrong format (missing ':')")
        tcp_obj.add_to_out_buffer(server_command.server_reply(state=state,
                                                              result=result))
    def _check_submit_job(self, tcp_obj, s_com):
        self.__queue_dict["check_queue"].put(("check_submit_job", (s_com.get_option_dict(), tcp_obj)))
    def _got_final_job_id(self, tcp_obj, s_com):
        self.__queue_dict["check_queue"].put(("got_final_job_id", (s_com.get_option_dict(), tcp_obj)))
    def _get_complexes(self, tcp_obj, s_com):
        tcp_obj.add_to_out_buffer(server_command.server_reply(state=server_command.SRV_REPLY_STATE_OK,
                                                              result="complexes",
                                                              option_dict={"co_complexes" : self.__sge_info["complexes"]}))
    def _check_job(self, tcp_obj, s_com):
        self._update_selective(["qstat"])
        #pprint.pprint(in_dict)
        #print 
        new_pji = pending_job_info(self, tcp_obj, s_com.get_option_dict())
        req_list = new_pji.generate_requests(self.__sge_info)
        for req in req_list:
            self.__ns.add_object(req)
    def _get_config(self, tcp_obj, s_com):
        opt_dict = s_com.get_option_dict()
        needed_dicts = opt_dict.get("needed_dicts", ["hostgroup", "queueconf", "qhost", "complexes"])
        update_list = opt_dict.get("update_list", [])
        if update_list:
            self.log("updating %s: %s" % (logging_tools.get_plural("key", len(update_list)),
                                          ", ".join(sorted(update_list))))
            self._update_selective(update_list)
        self.log("reporting %s: %s" % (logging_tools.get_plural("dict", len(needed_dicts)),
                                       ", ".join(sorted(needed_dicts))))
        
        fo_info, gf_info, cwd_info = (opt_dict.get("fetch_output_info", False),
                                      opt_dict.get("get_filewatch_info", False),
                                      opt_dict.get("get_cwd_info", False))
        if fo_info or gf_info or cwd_info:
            dc = self.__db_con.get_connection(SQL_ACCESS)
            self.__aj_struct.lock()
            for job_uid, act_job in self.__sge_info["qstat"].iteritems():
                if not self.__aj_struct.has_key(job_uid):
                    new_job = job(self.__aj_struct,
                                  {"job_id"   : job_uid,
                                   "job_name" : act_job["JB_name"],
                                   "job_num"  : act_job.get_id(),
                                   "task_id"  : act_job.get("tasks", "")},
                                  dc,
                                  self.__queue_dict)
                    self.__aj_struct[job_uid] = new_job
                else:
                    new_job = self.__aj_struct[job_uid]
                if not new_job.settings_ok:
                    new_job._get_settings()
                if new_job.get("owner", "not known") == opt_dict.get("user_name", "not set") or opt_dict.get("ignore_user_name", False):
                    if fo_info:
                        act_job.add_tag("output_info", None, dict([(var_name, new_job.get(var_name, "")) for var_name in ["stdout_path",
                                                                                                                          "stderr_path"]]))
                    if gf_info:
                        act_job.add_tag("filewatch_info", None, new_job.get_filewatch_info())
                    if cwd_info:
                        act_job.add_tag("cwd_info", None, {"cwd" : new_job.get("cwd", "/tmp")})
            self.__aj_struct.release()
            dc.release()
        tcp_obj.add_to_out_buffer(server_command.server_reply(state=server_command.SRV_REPLY_STATE_OK,
                                                              result="config",
                                                              option_dict=dict([(key, self.__sge_info[key]) for key in needed_dicts])))
    def _call_qconf(self, tcp_obj, s_com):
        opt_dict = s_com.get_option_dict()
        if opt_dict.has_key("command"):
            stat, out = call_command("%s/bin/%s/qconf %s" % (self.__glob_config["SGE_ROOT"],
                                                             self.__glob_config["SGE_ARCH"],
                                                             opt_dict["command"]),
                                     self.log)
            if stat:
                ret_state = server_command.SRV_REPLY_STATE_ERROR
            else:
                ret_state = server_command.SRV_REPLY_STATE_OK
            tcp_obj.add_to_out_buffer(server_command.server_reply(state=ret_state,
                                                                  result="result is %s" % (out)))
        else:
            tcp_obj.add_to_out_buffer(server_command.server_reply(state=server_command.SRV_REPLY_STATE_ERROR,
                                                                  result="no command given"))
    def _status(self, tcp_obj, s_com):
        tp = self.get_thread_pool()
        num_threads, num_ok = (tp.num_threads(False),
                               tp.num_threads_running(False))
        if num_ok == num_threads:
            ret_str = "OK: all %d threads running, version %s" % (num_ok, self.__loc_config["VERSION_STRING"])
        else:
            ret_str = "ERROR: only %d of %d threads running, version %s" % (num_ok, num_threads, self.__loc_config["VERSION_STRING"])
        tcp_obj.add_to_out_buffer(server_command.server_reply(state=server_command.SRV_REPLY_STATE_OK,
                                                              result=ret_str))
    def _job_com(self, tcp_obj, s_com):
        if self.__glob_config["MONITOR_JOBS"]:
            self.__queue_dict["job_mon_queue"].put(("job_com", (tcp_obj, s_com)))
        else:
            tcp_obj.add_to_out_buffer(server_command.server_reply(state=server_command.SRV_REPLY_STATE_OK,
                                                                  result="ok"))
    def _delete_jobs(self, tcp_obj, s_com):
        command = s_com.get_command()
        job_list = s_com.get_option_dict()["job_ids"]
        forced_del = (command == "force_delete_jobs")
        self.log("%s was requested for %s: %s" % (forced_del and "force_delete" or "delete",
                                                  logging_tools.get_plural("job", len(job_list)),
                                                  ", ".join(job_list)))
        call_command("/%s/bin/%s/qdel %s %s" % (self.__glob_config["SGE_ROOT"],
                                                self.__glob_config["SGE_ARCH"],
                                                forced_del and "-f" or "",
                                                " ".join(job_list)), self.log)
        tcp_obj.add_to_out_buffer(server_command.server_reply(state=server_command.SRV_REPLY_STATE_OK,
                                                              result="delete %s" % (logging_tools.get_plural("job", len(job_list)))))
    def _send_tcp_return(self, (tcp_obj, send_obj)):
        tcp_obj.add_to_out_buffer(send_obj)
    def _process_special_command(self, tcp_obj, s_com):
        command = s_com.get_command()
        opt_dict = s_com.get_option_dict()
        com_struct = self.__com_dict.get(command)
        delay_count = self.__glob_config["CLEAR_ITERATIONS"]
        objects = opt_dict.get("fail_objects", [])
        job_id, job_num   = (opt_dict["job_id"]    , opt_dict["job_num"] )
        uid, gid          = (opt_dict["uid"]       , opt_dict["gid"]     )
        p_queue, job_name = (opt_dict["queue_name"], opt_dict["job_name"])
        task_id = get_task_id(opt_dict.get("task_id", None))
        s_host = opt_dict.get("host", "unknown")
        why = opt_dict.get("error", "<unknown>")
        try:
            uid_name = pwd.getpwuid(uid)[0]
        except:
            uid_name = "<unknown>"
        try:
            gid_name = grp.getgrgid(gid)[0]
        except:
            gid_name = "<unknown>"
        com_str = "got command %s (%s) for %s, job_id %s, user %s (%d), group %s (%d) from host %s, reason: %s" % (command,
                                                                                                                   com_struct["command"],
                                                                                                                   logging_tools.get_plural(com_struct["object"], len(objects)),
                                                                                                                   job_id,
                                                                                                                   uid_name, uid,
                                                                                                                   gid_name, gid,
                                                                                                                   s_host,
                                                                                                                   why)
        log_str = "got command %s for %s, user %s (%d), group %s (%d) from host %s, reason: %s" % (command,
                                                                                                   logging_tools.get_plural(com_struct["object"], len(objects)),
                                                                                                   uid_name, uid,
                                                                                                   gid_name, gid,
                                                                                                   s_host,
                                                                                                   why)
        # job log
        #self.__queue_dict["job_mon_queue"].putjob_mon_queue.put(job_log_message({"job_uid" : job_id, "log_str" : log_str}))
        mail_array = ["server         : %s" % (self.__loc_config["SERVER_ROLE"]),
                      "",
                      "Job information:",
                      "job name : %s" % (job_name),
                      "job-id   : %s" % (job_id),
                      "job-num  : %s" % (job_num),
                      "task id  : %s" % (str(task_id)),
                      "",
                      "User information:",
                      "user  : %s (%d)" % (uid_name, uid),
                      "group : %s (%d)" % (gid_name, gid),
                      "",
                      "Problem information:",
                      "calling host  : %s" % (s_host),
                      "primary queue : %s" % (p_queue),
                      "object-type   : %s" % (com_struct["object"]),
                      "action        : %s" % (command),
                      "executing     : %s" % (com_struct["command"]),
                      "reason        : %s" % (why)]
        if objects:
            mail_array.append("object list   : %s" % (",".join(objects)))
        else:
            mail_array.append("object list   : none given")
        mail_array.append("")
        self.log(com_str, special=["n", "d"])
        if objects:
            log_str = "object list: %s" % (",".join(objects))
        else:
            log_str = "object list: none given"
        self.log(log_str, special=["n", "d"])
        num_done = 0
        for obj in objects:
            stat, out = call_command("%s/bin/%s/%s %s" % (self.__glob_config["SGE_ROOT"], self.__glob_config["SGE_ARCH"], com_struct["command"], obj),
                                     self.log)
            mail_array.append("executed command %s on object %s" % (com_struct["command"], obj))
            mail_array.append("  result (%d): %s" % (stat, out))
            log_str = "  executing command '%s %s', result: '%s'" % (com_struct["command"], obj, out)
            self.log(log_str)
            if com_struct["object"] == "queue" and command == "disable":
                self._add_log_entry(obj.split("@")[0],
                                    obj.split("@")[1],
                                    job_id,
                                    "%s %s because of %s" % (command,
                                                             com_struct["object"],
                                                             why),
                                    logging_tools.LOG_LEVEL_ERROR)
            if not stat:
                num_done += 1
        # for mail
        obj_info, extra_info = ("", "")
        if com_struct["object"] == "job":
            obj_info = "ID %s" % (job_id)
            if command == "hold":
                self._add_log_entry(p_queue, s_host, job_id, "job hold because of %s" % (why), logging_tools.LOG_LEVEL_ERROR)
                mail_array.append("")
                mail_array.extend(["job hold will result in an error-state for queue %s on host %s, " % (p_queue, s_host), "will clear error in %d iterations" % (delay_count)])
                self.__queue_dict["mon_queue"].put(("clear_queue_delayed", (p_queue, s_host, delay_count)))
                if why.startswith("connection") and self.__glob_config["RETRY_AFTER_CONNECTION_PROBLEMS"]:
                    mail_array.append("")
                    mail_array.extend(["job hold because of an connection problem (MPI-Interface problem ?),", "will release job in %d iterations" % (delay_count)])
                    self.__queue_dict["mon_queue"].put(("release_job_delayed", (job_id, delay_count)))
        elif com_struct["object"] == "queue":
            obj_info = "%s: %s" % (logging_tools.get_plural("instance", len(objects)),
                                   ", ".join(sorted(objects)))
            extra_info = "Job ID is %s" % (job_id)
        if com_struct.get("send_mail", False):
            from_addr = self.__glob_config["FROM_ADDR"]
            to_addrs = self.__glob_config["TO_ADDR"].split(",")
            mail_subject = "sge problem - %s %s (%s)%s" % (command,
                                                           com_struct["object"],
                                                           obj_info if obj_info else job_id,
                                                           ", %s" % (extra_info) if extra_info else "")
            stat, log_strs = send_mail(from_addr, to_addrs, mail_subject, mail_array)
            for log_line in log_strs:
                self.log(log_line)
        ret_str = "ok %s on %d %s(s)" % (command, num_done, com_struct["object"])
        tcp_obj.add_to_out_buffer(server_command.server_reply(state=server_command.SRV_REPLY_STATE_OK, result=ret_str))

class sql_thread(threading_tools.thread_obj):
    def __init__(self, glob_config, loc_config, db_con, log_queue):
        self.__db_con = db_con
        self.__log_queue = log_queue
        self.__glob_config, self.__loc_config = (glob_config, loc_config)
        threading_tools.thread_obj.__init__(self, "sql", queue_size=200)
        self.register_func("update"        , self._update_db)
        self.register_func("insert_value"  , self._insert_value_db)
        self.register_func("insert_set"    , self._insert_set_db)
        self.register_func("set_queue_dict", self._set_queue_dict)
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__log_queue.put(("log", (self.name, what, lev)))
    def thread_running(self):
        self.send_pool_message(("new_pid", (self.name, self.pid)))
        self._init_start_time()
        self.__dc = self.__db_con.get_connection(SQL_ACCESS)
    def _set_queue_dict(self, q_dict):
        self.__queue_dict = q_dict
    def _init_start_time(self):
        self.__start_time = time.time()
        self.__num_written, self.__num_update, self.__num_ins_v, self.__num_ins_s = (0, 0, 0, 0)
    def _check_written(self, force=False):
        if not force:
            self.__num_written += 1
        if self.__num_written > 50 or force:
            act_time = time.time()
            self.log("wrote %d entries (%s, %s [with values], %s [with set]) in %s" % (self.__num_written,
                                                                                       logging_tools.get_plural("update", self.__num_update),
                                                                                       logging_tools.get_plural("insert", self.__num_ins_v),
                                                                                       logging_tools.get_plural("insert", self.__num_ins_s),
                                                                                       logging_tools.get_diff_time_str(act_time - self.__start_time)))
            self._init_start_time()
    def _update_db(self, args):
        if len(args) == 2:
            sql_table, sql_data = args
            sql_args = None
        else:
            sql_table, sql_data, sql_args = args
        self.__dc.execute("UPDATE %s SET %s" % (sql_table, sql_data), sql_args)
        self.__num_update += 1
        self._check_written()
    def _insert_value_db(self, args):
        if len(args) == 2:
            sql_table, sql_data = args
            sql_args = None
        else:
            sql_table, sql_data, sql_args = args
        self.__dc.execute("INSERT INTO %s VALUES(%s)" % (sql_table, sql_data), sql_args)
        self.__num_ins_v += 1
        self._check_written()
    def _insert_set_db(self, args):
        if len(args) == 2:
            sql_table, sql_data = args
            sql_args = None
        else:
            sql_table, sql_data, sql_args = args
        self.__dc.execute("INSERT INTO %s SET %s" % (sql_table, sql_data), sql_args)
        self.__num_ins_s += 1
        self._check_written()
    def loop_end(self):
        self._check_written(True)
        self.__dc.release()

class server_thread_pool(threading_tools.thread_pool):
    def __init__(self, db_con, g_config, loc_config):
        self.__log_cache, self.__log_queue = ([], None)
        self.__db_con = db_con
        self.__glob_config, self.__loc_config = (g_config, loc_config)
        threading_tools.thread_pool.__init__(self, "main", blocking_loop=False)
        self.__msi_block = self._init_msi_block()
        self.register_func("new_pid", self._new_pid)
        self.register_exception("int_error", self._int_error)
        self.register_exception("term_error", self._int_error)
        self._correct_sge_arch()
        self._set_sge_environment()
        self.__log_queue = self.add_thread(logging_thread(self.__glob_config, self.__loc_config), start_thread=True).get_thread_queue()
        self.__sql_queue = self.add_thread(sql_thread(self.__glob_config, self.__loc_config, self.__db_con, self.__log_queue), start_thread=True).get_thread_queue()
        self.__node_queue = self.add_thread(node_thread(self.__glob_config, self.__loc_config, self.__db_con, self.__log_queue, sge_tools), start_thread=True).get_thread_queue()
        self.__is_server = self.__loc_config["SERVER_ROLE"] == "sge_server"
        if self.__is_server:
            self.__check_queue = self.add_thread(check_thread(self.__glob_config, self.__loc_config, self.__db_con, self.__log_queue), start_thread=True).get_thread_queue()
            self.__acc_queue = self.add_thread(accounting_thread(self.__glob_config, self.__loc_config, self.__db_con, self.__log_queue), start_thread=True).get_thread_queue()
            self.__mon_queue = self.add_thread(monitor_thread(self.__glob_config, self.__loc_config, self.__db_con, self.__log_queue, sge_tools), start_thread=True).get_thread_queue()
            self.__job_mon_queue = self.add_thread(job_monitor_thread(self.__glob_config, self.__loc_config, self.__db_con, self.__log_queue), start_thread=True).get_thread_queue()
            q_dict = {"log_queue"     : self.__log_queue,
                      "sql_queue"     : self.__sql_queue,
                      "mon_queue"     : self.__mon_queue,
                      "node_queue"    : self.__node_queue,
                      "job_mon_queue" : self.__job_mon_queue,
                      "acc_queue"     : self.__acc_queue,
                      "check_queue"   : self.__check_queue}
        else:
            q_dict = {"log_queue"     : self.__log_queue,
                      "sql_queue"     : self.__sql_queue,
                      "node_queue"    : self.__node_queue}
        self.__all_jobs_struct = all_jobs(self.__log_queue, self.__glob_config, self.__loc_config)
        self.__log_queue.put(("set_queue_dict", q_dict))
        self.__sql_queue.put(("set_queue_dict", q_dict))
        self.__node_queue.put(("set_queue_dict", q_dict))
        if self.__is_server:
            self.__mon_queue.put(("set_queue_dict", q_dict))
            self.__job_mon_queue.put(("set_queue_dict", q_dict))
            self.__acc_queue.put(("set_queue_dict", q_dict))
            self.__check_queue.put(("set_queue_dict", q_dict))
        self.__node_queue.put(("set_aj_struct", self.__all_jobs_struct))
        if self.__is_server:
            self.__job_mon_queue.put(("set_aj_struct", self.__all_jobs_struct))
            self.__mon_queue.put(("set_aj_struct", self.__all_jobs_struct))
            self.__acc_queue.put(("set_aj_struct", self.__all_jobs_struct))
            self.__check_queue.put(("set_aj_struct", self.__all_jobs_struct))
        self.__pids_needed = len(q_dict.keys())
        self._log_config()
        dc = self.__db_con.get_connection(SQL_ACCESS)
        # re-insert config
        self._re_insert_config(dc)
        self.__ns = net_tools.network_server(timeout=2, log_hook=self.log, poll_verbose=self.__loc_config["VERBOSE"] > 1)
        self.__ns.add_object(net_tools.tcp_bind(self._new_tcp_connection, port=g_config["CHECK_PORT"], bind_retries=5, bind_state_call=self._bind_state_call, timeout=60))
        self.__ns.add_object(net_tools.udp_bind(self._new_udp_connection, port=g_config["CHECK_PORT"], bind_retries=5, bind_state_call=self._bind_state_call, timeout=60))
        dc.release()
        # uuid log
        my_uuid = uuid_tools.get_uuid()
        self.log("cluster_device_uuid is '%s'" % (my_uuid.get_urn()))
        if self.__is_server:
            self.__node_queue.put(("set_netserver", self.__ns))
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        if self.__log_queue:
            if self.__log_cache:
                for c_what, c_lev in self.__log_cache:
                    self.__log_queue.put(("log", (self.name, "(delayed) %s" % (c_what), c_lev)))
                self.__log_cache = []
            self.__log_queue.put(("log", (self.name, what, lev)))
        else:
            self.__log_cache.append((what, lev))
    def _int_error(self, err_cause):
        if self["exit_requested"]:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            self.log("exit requested", logging_tools.LOG_LEVEL_WARN)
            self["exit_requested"] = True
            self.__ns.set_timeout(0.5)
    def _new_tcp_connection(self, sock, src):
        return new_tcp_con(sock, src, self.__node_queue, self.__log_queue)
    def _new_udp_connection(self, data, src):
        self.__node_queue.put(("udp_data", (src, data)))
    def _bind_state_call(self, **args):
        if args["state"].count("ok"):
            self.log("Bind to %s (type %s) sucessfull" % (args["port"], args["type"]))
        else:
            # FIXME
            self.log("Bind to %s (type %s) NOT sucessfull" % (args["port"], args["type"]), logging_tools.LOG_LEVEL_CRITICAL)
            self.log("unable to bind to all ports, exiting", logging_tools.LOG_LEVEL_ERROR)
            self._int_error("bind problem")
    def _new_pid(self, (thread_name, new_pid)):
        self.log("received new_pid message from thread %s" % (thread_name))
        process_tools.append_pids(self.__loc_config["PID_NAME"], new_pid)
        if self.__msi_block:
            self.__msi_block.add_actual_pid(new_pid)
            self.__msi_block.save_block()
        self.__pids_needed -= 1
        if not self.__pids_needed:
            self.__ns.set_timeout(self.__loc_config["SERVER_SHORT_NAME"] == "tormentor" and 5 or 60)
    def _init_msi_block(self):
        process_tools.save_pid(self.__loc_config["PID_NAME"])
        if self.__loc_config["DAEMON"]:
            self.log("Initialising meta-server-info block")
            msi_block = process_tools.meta_server_info("sge-server")
            msi_block.add_actual_pid()
            msi_block.start_command = "/etc/init.d/sge-server start"
            msi_block.stop_command = "/etc/init.d/sge-server force-stop"
            msi_block.kill_pids = True
            msi_block.save_block()
        else:
            msi_block = None
        return msi_block
    def _log_config(self):
        self.log("Config info:")
        for line, log_level in self.__glob_config.get_log(clear=True):
            self.log(" - clf: [%d] %s" % (log_level, line))
        conf_info = self.__glob_config.get_config_info()
        self.log("Found %d valid global config-lines:" % (len(conf_info)))
        for conf in conf_info:
            self.log("Config : %s" % (conf))
        conf_info = self.__loc_config.get_config_info()
        self.log("Found %d valid local config-lines:" % (len(conf_info)))
        for conf in conf_info:
            self.log("Config : %s" % (conf))
    def _re_insert_config(self, dc):
        self.log("re-insert config")
        configfile.write_config(dc, self.__loc_config["SERVER_ROLE"], self.__glob_config)
    def thread_loop_post(self):
        process_tools.delete_pid(self.__loc_config["PID_NAME"])
        if self.__msi_block:
            self.__msi_block.remove_meta_block()
    def loop_function(self):
        self.__ns.step()
        if self.__loc_config["VERBOSE"] or self["exit_requested"]:
            tqi_dict = self.get_thread_queue_info()
            self.log("tqi: %s" % (", ".join([t_used and "%s: %3d of %3d" % (t_name, t_used, t_total) or "%s: %3d" % (t_name, t_total) for (t_name, t_used, t_total) in [(t_name,
                                                                                                                                                                         tqi_dict[t_name][1],
                                                                                                                                                                         tqi_dict[t_name][0]) for t_name in sorted(tqi_dict.keys())]])))
        if self.__is_server:
            self.__mon_queue.put("update")
        self.__node_queue.put("update")
        self.__log_queue.put("update")
    def _correct_sge_arch(self):
        if self.__glob_config["SGE_ARCH"].startswith("lx24"):
            new_arch = self.__glob_config["SGE_ARCH"].replace("lx24", "lx26")
            self.log("correcting SGE_ARCH from %s to %s" % (self.__glob_config["SGE_ARCH"],
                                                            new_arch))
            self.__glob_config["SGE_ARCH"] = new_arch
    def _set_sge_environment(self):
        for env_name in ["SGE_ROOT", "SGE_CELL"]:
            self.log("setting environment variable %s to %s" % (env_name, self.__glob_config[env_name]))
            os.environ[env_name] = self.__glob_config[env_name]

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], "dVvG:hCfg:u:k", ["help", "comp", "confp"])
    except getopt.GetoptError, bla:
        print "Commandline error!", bla
        sys.exit(2)
    long_host_name = socket.getfqdn(socket.gethostname())
    short_host_name = long_host_name.split(".")[0]
    # read version
    try:
        from sge_server_version import VERSION_STRING
    except ImportError:
        VERSION_STRING = "?.?"
    loc_config = configfile.configuration("local_config", {"PID_NAME"          : configfile.str_c_var("sge-server/sge-server"),
                                                           "SERVER_FULL_NAME"  : configfile.str_c_var(long_host_name),
                                                           "SERVER_SHORT_NAME" : configfile.str_c_var(short_host_name),
                                                           "DAEMON"            : configfile.bool_c_var(True),
                                                           "VERBOSE"           : configfile.int_c_var(0),
                                                           "SERVER_IDX"        : configfile.int_c_var(0),
                                                           "VERSION_STRING"    : configfile.str_c_var(VERSION_STRING),
                                                           "SERVER_ROLE"       : configfile.str_c_var("unset")})

    check, kill_running = (False, True)
    check_port = SERVER_CHECK_PORT
    user, group, groups, fixit = ("root", "root", [], False)
    pname = os.path.basename(sys.argv[0])
    for opt, arg in opts:
        if opt in ("-h", "--help"):
            print "Usage: %s [OPTIONS]" % (pname)
            print "where OPTIONS are:"
            print " -h,--help       this help"
            print " -d              run in debug mode (no forking)"
            print " -v              be verbose"
            print " -V              show version"
            print " --confp port    connect to given port for node requests, default is %d" % (check_port)
            print " -f              create and fix needed files and directories"
            print " -u user         run as user USER"
            print " -g group        run as group GROUP"
            print " -G groups       coma-separated list of additional groups"
            print " -k              do not kill running %s" % (pname)
            sys.exit(0)
        if opt == "-G":
            groups = [x.strip() for x in arg.strip().split(",")]
        if opt == "-C":
            check = True
        if opt == "-d":
            loc_config["DAEMON"] = False
        if opt == "-V":
            print "Version %s" % (VERSION_STRING)
            sys.exit(0)
        if opt == "-p":
            g_port = int(arg)
        if opt == "-v":
            loc_config["VERBOSE"] += 1
        if opt == "-f":
            fixit = True
        if opt == "-u":
            user = arg
        if opt == "-g":
            group = arg
    db_con = mysql_tools.dbcon_container(with_logging=not loc_config["DAEMON"])
    try:
        dc = db_con.get_connection(SQL_ACCESS)
    except MySQLdb.OperationalError:
        sys.stderr.write(" Cannot connect to SQL-Server ")
        sys.exit(1)
    ret_state = 256
    sql_s_info = config_tools.server_check(dc=dc, server_type="sge_server")
    sql_r_info = config_tools.server_check(dc=dc, server_type="sge_relayer")
    if sql_s_info.num_servers + sql_r_info.num_servers == 0:
        sys.stderr.write(" %s is no sge-server/relayer, exiting..." % (long_host_name))
        sys.exit(5)
    if check:
        sys.exit(0)
    if sql_s_info.num_servers:
        loc_config["SERVER_IDX"] = sql_s_info.server_device_idx
        loc_config["SERVER_ROLE"] = "sge_server"
    else:
        loc_config["SERVER_IDX"] = sql_r_info.server_device_idx
        loc_config["SERVER_ROLE"] = "sge_relayer"
    if kill_running:
        kill_dict = process_tools.build_kill_dict(pname)
        for k, v in kill_dict.iteritems():
            log_str = "Trying to kill pid %d (%s) with signal 9 ..." % (k, v)
            try:
                os.kill(k, 9)
            except:
                log_str = "%s error (%s)" % (log_str, sys.exc_info()[0])
            else:
                log_str = "%s ok" % (log_str)
            logging_tools.my_syslog(log_str)

    sge_dict = {}
    for v_name, v_src in [("SGE_ROOT", "/etc/sge_root"),
                          ("SGE_CELL", "/etc/sge_cell")]:
        if os.path.isfile(v_src):
            sge_dict[v_name] = file(v_src, "r").read().strip()
        else:
            print "error: Cannot read %s from file %s, exiting..." % (v_name, v_src)
            sys.exit(2)
    stat, sge_dict["SGE_ARCH"], log_lines = call_command("/%s/util/arch" % (sge_dict["SGE_ROOT"]))
    if stat:
        print "error Cannot evaluate SGE_ARCH"
        sys.exit(1)
    g_config = configfile.read_global_config(dc, loc_config["SERVER_ROLE"], {"LOG_DIR"                         : configfile.str_c_var("/var/log/cluster/%s" % (loc_config["SERVER_ROLE"].replace("_", "-"))),
                                                                             "CHECK_PORT"                      : configfile.int_c_var(check_port),
                                                                             "CHECK_ITERATIONS"                : configfile.int_c_var(3),
                                                                             "RETRY_AFTER_CONNECTION_PROBLEMS" : configfile.int_c_var(0),
                                                                             "FROM_ADDR"                       : configfile.str_c_var(loc_config["SERVER_ROLE"].replace("_", "-")),
                                                                             "TO_ADDR"                         : configfile.str_c_var("lang-nevyjel@init.at"),
                                                                             "SGE_ARCH"                        : configfile.str_c_var(sge_dict["SGE_ARCH"], fixed=True),
                                                                             "SGE_ROOT"                        : configfile.str_c_var(sge_dict["SGE_ROOT"], fixed=True),
                                                                             "SGE_CELL"                        : configfile.str_c_var(sge_dict["SGE_CELL"], fixed=True),
                                                                             "MONITOR_JOBS"                    : configfile.bool_c_var(True)})
    if loc_config["SERVER_ROLE"] == "sge_server":
        # server_mode
        g_config.add_config_dict({"TRACE_FAIRSHARE"          : configfile.int_c_var(0),
                                  "STRICT_MODE"              : configfile.int_c_var(0),
                                  "APPEND_SERIAL_COMPLEX"    : configfile.int_c_var(1),
                                  "CLEAR_ITERATIONS"         : configfile.int_c_var(1),
                                  "CHECK_ACCOUNTING_TIMEOUT" : configfile.int_c_var(300)})
    if os.path.isfile("/%s/%s/common/product_mode" % (g_config["SGE_ROOT"], g_config["SGE_CELL"])):
        g_config.add_config_dict({"SGE_VERSION"    : configfile.int_c_var(5),
                                  "SGE_RELEASE"    : configfile.int_c_var(3),
                                  "SGE_PATCHLEVEL" : configfile.int_c_var(0)})
    else:
        # try to get the actual version
        qs_com = "/%s/bin/%s/qconf" % (g_config["SGE_ROOT"],
                                       g_config["SGE_ARCH"])
        stat, vers_string, log_lines = call_command(qs_com)
        vers_line = vers_string.split("\n")[0].lower()
        if vers_line.startswith("ge") or vers_line.startswith("sge"):
            vers_part = vers_line.split()[1]
            major, minor = vers_part.split(".")
            minor, patchlevel = minor.split("u")
            patchlevel = patchlevel.split("_")[0]
            g_config.add_config_dict({"SGE_VERSION"    : configfile.int_c_var(int(major)),
                                      "SGE_RELEASE"    : configfile.int_c_var(int(minor)),
                                      "SGE_PATCHLEVEL" : configfile.int_c_var(int(patchlevel))})
        else:
            if g_config.has_key("SGE_VERSION") and g_config.has_key("SGE_RELEASE") and g_config.has_key("SGE_PATCHLEVEL"):
                pass
            else:
                print "Cannot determine GE Version via %s" % (qs_com)
                dc.release()
                sys.exit(-1)
    if sql_s_info.num_servers > 1 or sql_r_info.num_servers> 1:
        print "Database error for host %s (%s): too many entries found (%d)" % (long_host_name,
                                                                                loc_config["SERVER_ROLE"],
                                                                                sql_s_info.num_servers + sql_r_info.num_servers)
        dc.release()
    else:
        # get real server stuff
        log_source_idx = process_tools.create_log_source_entry(dc, loc_config["SERVER_IDX"], loc_config["SERVER_ROLE"], "SGE Server/relayer")
        log_sources = process_tools.get_all_log_sources(dc)
        log_status = process_tools.get_all_log_status(dc)
        process_tools.create_log_source_entry(dc, 0, "sgeflat", "SGE Message (unparsed)", "Info from the SunGridEngine")
        dc.release()
        if fixit:
            process_tools.fix_directories(user, group, [g_config["LOG_DIR"], "/var/run/sge-server"])
        process_tools.change_user_group(user, group, groups)
        if loc_config["DAEMON"]:
            process_tools.become_daemon()
            process_tools.set_handles({"out" : (1, loc_config["SERVER_ROLE"]),
                                       "err" : (0, "/var/lib/logging-server/py_err")})
        else:
            print "Debugging %s on %s" % (loc_config["SERVER_ROLE"],
                                          short_host_name)
        my_tp = server_thread_pool(db_con, g_config, loc_config)
        my_tp.thread_loop()
    db_con.close()
    del db_con
    sys.exit(ret_state)

if __name__ == "__main__":
    main()
