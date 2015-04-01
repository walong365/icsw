#!/usr/bin/python-init -Ot
# -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
# 
# This file is part of logcheck-server
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

import getopt
import msock
import signal
import select
import time
import syslog
import os
import os.path
import datetime
import sys
import thread
import threading
import Queue
import MySQLdb
import re
import shutil
import pty
import configfile
import socket
import commands
import stat
import types
import process_tools
import logging_tools
import net_logging_tools
import net_tools
import threading_tools
import mysql_tools
import marshal
import cPickle
import pickle
import pprint
import server_command
import gzip
import bz2
import struct
import config_tools

SYSLOG_THREAD_STR = "syslog-thread-test"

SCAN_TEXT_PREFIX = ".scan"
SCAN_TEXT_FILE   = "%s_info" % (SCAN_TEXT_PREFIX)
SCAN_DICT_FILE   = "%s_struct.bz2" % (SCAN_TEXT_PREFIX)
SCAN_IGNORE_FILE = "%s_ignore" % (SCAN_TEXT_PREFIX)

LOGREADER_DATE_VARNAME   = "logsrv_logreader_date"
LOGREADER_OFFSET_VARNAME = "logsrv_logreader_offset"

SQL_ACCESS = "cluster_full_access"

# ---------------------------------------------------------------------
# connection object
class new_tcp_con(net_tools.buffer_object):
    def __init__(self, src, recv_queue, log_queue):
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
            self.__recv_queue.put(("con", self))
    def add_to_out_buffer(self, what, new_in_str=""):
        self.lock()
        # to give some meaningful log
        if new_in_str:
            self.__decoded = new_in_str
        if self.socket:
            self.out_buffer = net_tools.add_proto_1_header(what)
            self.socket.ready_to_send()
        else:
            self.log("timeout, other side has closed connection")
        self.unlock()
    def out_buffer_sent(self, d_len):
        if d_len == len(self.out_buffer):
            self.__recv_queue = None
            self.log("command %s from %s (port %d) took %s" % (self.__decoded.replace("\n", "\\n"),
                                                               self.__src_host,
                                                               self.__src_port,
                                                               logging_tools.get_diff_time_str(abs(time.time() - self.__init_time))))
            self.close()
        else:
            self.out_buffer = self.out_buffer[d_len:]
    def get_decoded_in_str(self):
        return self.__decoded
    def report_problem(self, flag, what):
        self.close()

class node_con_obj(net_tools.buffer_object):
    # connects to a foreign node
    def __init__(self, com_thread, dst_host, send_str):
        self.__target_queue = com_thread.get_thread_queue()
        self.__dst_host = dst_host
        self.__send_str = send_str
        net_tools.buffer_object.__init__(self)
    def __del__(self):
        pass
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
            self.__target_queue.put("node_ok_result")
            self.delete()
    def report_problem(self, flag, what):
        self.__target_queue.put("node_error_result")
        self.delete()
# ---------------------------------------------------------------------

class throttle_thread(threading_tools.thread_obj):
    def __init__(self, glob_config, loc_config, db_con, log_queue):
        self.__db_con = db_con
        self.__log_queue = log_queue
        self.__glob_config, self.__loc_config = (glob_config, loc_config)
        threading_tools.thread_obj.__init__(self, "throttle", queue_size=100)
        self.register_func("update", self._update)
        self.register_func("set_ad_struct", self._set_ad_struct)
        self.register_func("throttle", self._throttle)
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__log_queue.put(("log", (self.name, what, lev)))
    def thread_running(self):
        self.send_pool_message(("new_pid", (self.name, self.pid)))
        self.__throttle_dict = {}
        self.__last_check = time.time()
        self.__last_db_sync_time = time.time()
    def _set_ad_struct(self, ad_struct):
        self.log("got ad_struct")
        self.__ad_struct = ad_struct
        self._update()
    def _log_dict(self):
        if self.__throttle_dict:
            num_th = len(self.__throttle_dict.keys())
            self.log("Got throttling messages from %s: %s" % (logging_tools.get_plural("device", num_th),
                                                              ", ".join(["%s (%d)" % (x, reduce(lambda a, b: a + b, [z["num"] for z in self.__throttle_dict[x].itervalues()])) for x in self.__throttle_dict.keys()])))
            mes_list = []
            for ml in reduce(lambda a, b: a + b, [x.keys() for x in self.__throttle_dict.itervalues()], []):
                if ml not in mes_list:
                    mes_list.append(ml)
            mes_list.sort()
            for mes in mes_list:
                act_list = []
                for dev, stuff in self.__throttle_dict.iteritems():
                    if mes in stuff.keys():
                        act_list.append("%s (%d)" % (dev, stuff[mes]["num"]))
                        self.log("* throttle message '%-40s': %4d times (%s)" % (mes, stuff[mes]["num"], dev))
                act_list.sort()
                self.log(" - message %-40s: %2d devices: %s" % (mes, len(act_list), ", ".join(act_list)))
    def _update(self):
        act_time = time.time()
        if act_time - self.__last_check > 60. or act_time < self.__last_check:
            self.__last_check = act_time
            self._log_dict()
            self.__throttle_dict = {}
    def _throttle(self, (mach, mes_str)):
        self.__throttle_dict.setdefault(mach, {}).setdefault(mes_str, {"first" : time.time(), "num" : 0})
        self.__throttle_dict[mach][mes_str]["num"] += 1
        self.__throttle_dict[mach][mes_str]["last"] = time.time()

class scan_thread(threading_tools.thread_obj):
    def __init__(self, glob_config, loc_config, db_con, log_queue):
        self.__db_con = db_con
        self.__log_queue = log_queue
        self.__glob_config, self.__loc_config = (glob_config, loc_config)
        threading_tools.thread_obj.__init__(self, "scan", queue_size=100)
        self.register_func("update", self._update)
        self.register_func("set_ad_struct", self._set_ad_struct)
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__log_queue.put(("log", (self.name, what, lev)))
    def _set_ad_struct(self, ad_struct):
        self.log("got ad_struct")
        self.__ad_struct = ad_struct
        self._update()
    def thread_running(self):
        self.send_pool_message(("new_pid", (self.name, self.pid)))
        self.__last_scan_time = time.time() - self.__glob_config["LOGSCAN_TIME"] * 60 * 2
    def _update(self):
        act_time = time.time()
        if abs(act_time - self.__last_scan_time) > self.__glob_config["LOGSCAN_TIME"] * 60:
            dc = self.__db_con.get_connection(SQL_ACCESS)
            self.__ad_struct.acquire_read_lock()
            dev_names = sorted([key for key in self.__ad_struct.keys() if not self.__ad_struct.is_an_ip(key)])
            s_time = time.time()
            self.log("starting scanning of logs for %s: %s" % (logging_tools.get_plural("device", len(dev_names)),
                                                               logging_tools.compress_list(dev_names)))
            for dev_name in dev_names:
                dev_struct = self.__ad_struct[dev_name]
                dev_struct.scan_logs(dc)
            self.__ad_struct.release_read_lock()
            e_time = time.time()
            self.log(" ... log_scanning took %s" % (logging_tools.get_diff_time_str(e_time - s_time)))
            self.__last_scan_time = act_time
            dc.release()

class sql_thread(threading_tools.thread_obj):
    def __init__(self, glob_config, loc_config, db_con, log_queue):
        self.__db_con = db_con
        self.__log_queue = log_queue
        self.__glob_config, self.__loc_config = (glob_config, loc_config)
        threading_tools.thread_obj.__init__(self, "sql", queue_size=100)
        self.register_func("update"      , self._update_db)
        self.register_func("insert_value", self._insert_value_db)
        self.register_func("insert_set"  , self._insert_set_db)
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__log_queue.put(("log", (self.name, what, lev)))
    def thread_running(self):
        self.send_pool_message(("new_pid", (self.name, self.pid)))
        self._init_start_time()
        self.__dc = self.__db_con.get_connection(SQL_ACCESS)
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

def time_to_int(in_str):
    # transforms time (hh:mm:ss) to integer
    t_spl = [int(x) for x in in_str.split(":")]
    return t_spl[2] + 60 * (t_spl[1] + 60 * t_spl[0])

def int_to_time(in_int):
    # transforms time (hh:mm:ss) to integer
    hours = int(in_int / 3600)
    mins  = int((in_int - 3600 * hours) / 60)
    secs  = in_int - 60 * (mins + 60 * hours)
    return "%02d:%02d:%02d" % (hours, mins, secs)

class machine(object):
    #def __init__(self, name, idx, ips={}, log_queue=None):
    def __init__(self, name, ad_struct, idx, dc, ip_dict, rescan):
        # machine name
        self.__name = name
        # all_devices struct
        self.__ad_struct = ad_struct
        # config array
        self.__glob_config, self.__loc_config = (self.__ad_struct.get_glob_config(),
                                                 self.__ad_struct.get_loc_config())
        # all ips
        self.__ip_dict = ip_dict
        # set log_queue
        self.set_log_queue(self.__ad_struct.get_log_queue())
        # machine idx
        self.__device_idx = idx
        # device variables
        self.__dev_vars = {}
        # add to global devname_dict
        self.__ad_struct[self.__name] = self
        self.log("Added myself to devname_dict")
        self.log_ip_info()
        self.generate_syslog_dirs()
        self.init_log_pointer(dc, rescan)
        # just for test
        #self.scan_logs(dc)
    def get_glob_config(self):
        return self.__glob_config
    def init_log_pointer(self, dc, rescan):
        # default value for log-reader (find first record on disc)
        log_start_dir = "%s/%s" % (self.__glob_config["SYSLOG_DIR"], self.__name)
        lsd_len = len(log_start_dir)
        rd_dict = {}
        if os.path.isdir(log_start_dir):
            for root_dir, sub_dirs, files in os.walk(log_start_dir):
                if root_dir.startswith(log_start_dir):
                    root_dir_p = [int(x) for x in root_dir[lsd_len:].split("/") if x.isdigit()]
                    if len(root_dir_p) == 3:
                        rd_dict.setdefault(root_dir_p[0], {}).setdefault(root_dir_p[1], []).append(root_dir_p[2])
        if rd_dict:
            min_year = sorted(rd_dict.keys())[0]
            min_month = sorted(rd_dict[min_year].keys())[0]
            min_day = sorted(rd_dict[min_year][min_month])[0]
            self.log("Found oldest logfile for %04d-%02d-%02d" % (min_year, min_month, min_day))
        else:
            min_year, min_month, min_day = time.localtime()[0:3]
            self.log("Unable to determine oldest logfile, using %04d-%02d-%02d" % (min_year, min_month, min_day))
        act_logreader_time = datetime.datetime(min_year, min_month, min_day, 0, 0, 0)
        self.__latest_lr_time   = self.modify_device_variable(dc, LOGREADER_DATE_VARNAME  , "actual position of logreader (date)"  , "d", act_logreader_time, False, rescan)
        self.__latest_lr_offset = self.modify_device_variable(dc, LOGREADER_OFFSET_VARNAME, "actual position of logreader (offset)", "i", 0                 , False, rescan)
    def scan_logs(self, dc):
        target_time = datetime.datetime(*time.localtime()[0:3])
        start_time = self.__latest_lr_time.replace()
        if start_time > target_time:
            self.log("start_time %s > target_time %s, skipping scan" % (str(start_time),
                                                                        str(target_time)),
                     logging_tools.LOG_LEVEL_ERROR)
        else:
            day_td = datetime.timedelta(1)
            check_path = []
            while True:
                check_path.append((start_time.year, start_time.month, start_time.day))
                if start_time.year == target_time.year and start_time.month == target_time.month and start_time.day == target_time.day:
                    break
                else:
                    start_time += day_td
            self.log("Checking logs, %s in path: %s" % (logging_tools.get_plural("entry", len(check_path)),
                                                        ", ".join(["%04d-%02d-%02d" % (x, y, z) for x, y, z in check_path])))
            self.log("offset for first path is %d" % (self.__latest_lr_offset))
            act_offset = self.__latest_lr_offset
            ok_year, ok_month, ok_day, ok_offset = (0, 0, 0, 0)
            for c_year, c_month, c_day in check_path:
                file_base_name = "%s/%s/%04d/%02d/%02d/log" % (self.__glob_config["SYSLOG_DIR"], self.__name, c_year, c_month, c_day)
                file_base_name_gz = "%s.gz" % (file_base_name)
                if os.path.isfile(file_base_name):
                    r_name = file_base_name
                    file_h = file(r_name, "r")
                elif os.path.isfile(file_base_name_gz):
                    r_name = file_base_name_gz
                    file_h = gzip.open(r_name, "r")
                else:
                    file_h = None
                if file_h:
                    self.log("Found file %s for %04d-%02d-%02d, seeking to offset %d" % (r_name, c_year, c_month, c_day, act_offset))
                    if act_offset:
                        file_h.seek(act_offset)
                        act_offset = 0
                    ok_year, ok_month, ok_day = (c_year, c_month, c_day)
                    file_h.read()
                    ok_offset = file_h.tell()
                    file_h.close()
                else:
                    self.log("no file found for %04d-%02d-%02d" % (c_year, c_month, c_day))
            if ok_year:
                self.log("saving actual position...")
                self.__latest_lr_time   = self.modify_device_variable(dc, LOGREADER_DATE_VARNAME  , "actual position of logreader (date)"  , "d", datetime.datetime(ok_year, ok_month, ok_day), True)
                self.__latest_lr_offset = self.modify_device_variable(dc, LOGREADER_OFFSET_VARNAME, "actual position of logreader (offset)", "i", ok_offset                                   , True)
    def modify_device_variable(self, dc, var_name, var_descr, var_type, var_value, modify=False, reinit=False):
        var_type_name = "val_%s" % ({"s" : "str" ,
                                     "i" : "int" ,
                                     "b" : "blob",
                                     "t" : "time",
                                     "d" : "date"}[var_type])
        if not self.__dev_vars.has_key(var_name):
            dc.execute("SELECT dv.device_variable_idx, dv.%s FROM device_variable dv WHERE dv.device=%d AND dv.name=%%s" % (var_type_name,
                                                                                                                            self.__device_idx), (var_name))
            reinit_var = True
            if dc.rowcount:
                line = dc.fetchone()
                if reinit:
                    self.log("Deleting found device_variable %s (idx %d)" % (var_name, line["device_variable_idx"]))
                    dc.execute("DELETE FROM device_variable WHERE device_variable_idx=%d" % (line["device_variable_idx"]))
                else:
                    reinit_var = False
                    self.__dev_vars[var_name] = {"idx"   : line["device_variable_idx"],
                                                 "value" : line[var_type_name]}
                    self.log("Found device_variable named '%s' (idx %d), value %s" % (var_name, self.__dev_vars[var_name]["idx"], str(self.__dev_vars[var_name]["value"])))
            if reinit_var:
                dc.execute("INSERT INTO device_variable SET device=%%s, name=%%s, description=%%s, var_type=%%s, %s=%%s" % (var_type_name), (self.__device_idx,
                                                                                                                                             var_name,
                                                                                                                                             var_descr,
                                                                                                                                             var_type,
                                                                                                                                             var_value))
                self.__dev_vars[var_name] = {"idx"   : dc.insert_id(),
                                             "value" : var_value}
                self.log("Creating device_variable named '%s' (idx %d), value %s" % (var_name, self.__dev_vars[var_name]["idx"], str(self.__dev_vars[var_name]["value"])))
                
        if self.__dev_vars[var_name]["value"] != var_value and modify:
            # modify variable
            dc.execute("UPDATE device_variable SET %s=%%s, description=%%s WHERE device_variable_idx=%d" % (var_type_name,
                                                                                                            self.__dev_vars[var_name]["idx"]), (var_value,
                                                                                                                                                var_descr))
            self.__dev_vars[var_name]["value"] = var_value
            if not dc.rowcount:
                self.log("UPDATE resulted in no rowchange, checking for device_variable '%s' ..." % (var_name))
                # in case the device_variable was deleted while the package-server was running
                dc.execute("SELECT dv.device_variable_idx FROM device_variable dv WHERE dv.device=%s AND dv.name=%s", (self.__device_idx,
                                                                                                                       var_name))
                if not dc.rowcount:
                    dc.execute("INSERT INTO device_variable SET device=%s, name=%s, description=%s, var_type=%s", (self.__device_idx,
                                                                                                                   var_name,
                                                                                                                   var_descr,
                                                                                                                   var_type))
                    self.__dev_vars[var_name] = {"idx"   : dc.insert_id(),
                                                 "value" : None}
                    self.log("Creating device_variable named '%s' (idx %d)" % (var_name, self.__dev_vars[var_name]["idx"]))
                dc.execute("UPDATE device_variable SET %s=%%s WHERE device_variable_idx=%%s" % (var_type_name), (var_value,
                                                                                                                 self.__dev_vars[var_name]["idx"]))
                self.__dev_vars[var_name]["value"] = var_value
        return self.__dev_vars[var_name]["value"]
    def log_ip_info(self):
        self.__contact_ip = None
        if self.__ip_dict:
            self.log("IP information:")
            for ip in sorted(self.__ip_dict.keys()):
                nw_postfix, net_type = self.__ip_dict[ip]
                self.log(" IP %15s, postfix %-5s (type %-5s), full name is %s%s" % (ip,
                                                                                    nw_postfix and "'%s'" % (nw_postfix) or "''",
                                                                                    net_type == "p" and "%s [*]" % (net_type) or net_type,
                                                                                    self.__name,
                                                                                    nw_postfix))
                if net_type == "p":
                    self.__contact_ip = ip
        else:
            self.log("No IPs set")
    def check_for_changed_ips(self, new_ip_dict):
        old_ips = sorted(self.__ip_dict.keys())
        new_ips = sorted(new_ip_dict.keys())
        if old_ips != new_ips:
            self.log("IPs have changed...")
            self.__ip_dict = new_ip_dict
            self.log_ip_info()
            self.generate_syslog_dirs()
    def get_name(self):
        return self.__name
    def set_log_queue(self, log_queue):
        self.__log_queue = log_queue
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK, glob=0):
        if self.__log_queue:
            if glob == 0 or glob == 2:
                self.__log_queue.put(("mach_log", (threading.currentThread().getName(), what, lev, self.__name)))
            if glob > 0:
                self.__log_queue.put(("log", (threading.currentThread().getName(), what, lev)))
        else:
            print "Log for machine %s: %s" % (self.__name, what)
    def generate_syslog_dirs(self):
        link_array = [("d", "%s/%s" % (self.__glob_config["SYSLOG_DIR"], self.__name))]
        for ip, (nw_postfix, net_type) in self.__ip_dict.iteritems():
            if nw_postfix:
                link_array.append(("l", "%s/%s%s" % (self.__glob_config["SYSLOG_DIR"], self.__name, nw_postfix)))
            if net_type != "l" or (net_type == "l" and self.__name == self.__loc_config["SERVER_SHORT_NAME"]):
                link_array.append(("l", "%s/%s" % (self.__glob_config["SYSLOG_DIR"], ip)))
        self.process_link_array(link_array)
    def process_link_array(self, l_array):
        for pt, ps in l_array:
            if pt == "d":
                if not os.path.isdir(ps):
                    try:
                        self.log("pla(): Creating directory %s" % (ps))
                        os.mkdir(ps)
                    except:
                        self.log("  ...something went wrong for mkdir(): %s" % (process_tools.get_except_info()))
            elif pt == "l":
                if type(ps) == type(""):
                    dest = self.__name
                else:
                    ps, dest = ps
                create_link = False
                if not os.path.islink(ps):
                    create_link = True
                else:
                    if os.path.exists(ps):
                        old_dest = os.readlink(ps)
                        if old_dest != dest:
                            try:
                                os.unlink(ps)
                            except OSError:
                                self.log("  ...something went wrong for unlink(): %s" % (process_tools.get_except_info()))
                            else:
                                self.log(" removed wrong link (%s pointed to %s instead of %s)" % (ps, old_dest, dest))
                                create_link = True
                    else:
                        pass
                if create_link:
                    if os.path.exists(ps):
                        try:
                            self.log("pla(): Unlink %s" % (ps))
                            os.unlink(ps)
                        except:
                            self.log("  ...something went wrong for unlink(): %s" % (process_tools.get_except_info()))
                        try:
                            self.log("pla(): rmtree %s" % (ps))
                            shutil.rmtree(ps, 1)
                        except:
                            self.log("  ...something went wrong for rmtree(): %s" % (process_tools.get_except_info()))
                    try:
                        self.log("pla(): symlink from %s to %s" % (ps, dest))
                        os.symlink(dest, ps)
                    except:
                        self.log("  ...something went wrong for symlink(): %s" % (process_tools.get_except_info()))
    def exists_scaninfo(self, year, month, day):
        log_target_dir = "%s/%s/%04d/%02d/%02d" % (self.__glob_config["SYSLOG_DIR"], self.__name, year, month, day)
        return os.path.isfile("%s/%s" % (log_target_dir, SCAN_DICT_FILE))
    def scaninfo_mtime(self, year=0, month=0, day=0):
        log_target_dir = "%s/%s" % (self.__glob_config["SYSLOG_DIR"], self.__name)
        for what, length in [(year , 4),
                             (month, 2),
                             (day  , 2)]:
            if int(what):
                log_target_dir = ("%%s/%%0%dd" % (length)) % (log_target_dir, int(what))
        scan_file = "%s/%s" % (log_target_dir, SCAN_DICT_FILE)
        if os.path.isfile(scan_file):
            sdf_mtime = os.stat(scan_file)[stat.ST_MTIME]
        else:
            sdf_mtime = 0
        return sdf_mtime
    def scan_log_dirs(self, reparse):
        start_time = time.time()
        dirs_found, dirs_proc, files_proc, files_error = (0, 0, 0, 0)
        logcheck_src_ignore = self.__glob_config.get("LOGCHECK_SRC_IGNORE", [])
        ignore_prefixes, ignore_prefixes_count = ({}, {})
        k_ts_re = re.compile("^\[\s*\d+\\.\d*\]\s*(?P<what>.*)$")
        for src_ign_header in ["kernel"]:
            ignore_prefixes[src_ign_header] = self.__glob_config.get("%s_IGNORE_PREFIXES" % (src_ign_header.upper()), [])
            ignore_prefixes_count[src_ign_header] = 0
        log_start_dir = "%s/%s" % (self.__glob_config["SYSLOG_DIR"], self.__name)
        if os.path.isdir(log_start_dir):
            act_time = time.localtime()
            self.log("log_start_dir %s found, start scanning in mode" % (log_start_dir))
            lsd_len = len(log_start_dir)
            self.log("starting walk for scan_log_dirs() in %s" % (log_start_dir))
            # directories processeds
            start_time = time.time()
            for root_dir, sub_dirs, files in os.walk(log_start_dir):
                dirs_found += 1
                if root_dir.startswith(log_start_dir):
                    root_dir_p = [int(x) for x in root_dir[lsd_len:].split("/") if x.isdigit()]
                    if len(root_dir_p) == 3 and sum([abs(x - y) for x, y in zip(root_dir_p[0:3], list(act_time[0:3]))]) != 0:
                        dirs_proc += 1
                        if not os.path.isfile("%s/%s" % (root_dir, SCAN_DICT_FILE)) or reparse:
                            dir_time = time.mktime([root_dir_p[0],
                                                    root_dir_p[1],
                                                    root_dir_p[2],
                                                    0,
                                                    0,
                                                    0,
                                                    0,
                                                    0,
                                                    0])
                            files_proc += 1
                            n_f_name, c_f_name = ("%s/log" % (root_dir),
                                                  "%s/log.gz" % (root_dir))
                            line_dict, ignore_count, num_lines = ({}, dict([(k, 0) for k in logcheck_src_ignore]), 0)
                            try:
                                if os.path.isfile(n_f_name):
                                    act_file_size = os.stat(n_f_name)[stat.ST_SIZE]
                                    if act_file_size > self.__glob_config["MAX_PARSE_FILE_SIZE"]:
                                        self.log("Skipping file %s (too big: %d > %d)" % (n_f_name, act_file_size, self.__glob_config["MAX_PARSE_FILE_SIZE"]))
                                        file_h = None
                                    else:
                                        file_h = file(n_f_name, "r")
                                elif os.path.isfile(c_f_name):
                                    act_file_size = os.stat(c_f_name)[stat.ST_SIZE]
                                    if act_file_size > self.__glob_config["MAX_PARSE_FILE_SIZE"] / 10:
                                        self.log("Skipping file %s (too big: %d > %d)" % (c_f_name, act_file_size, self.__glob_config["MAX_PARSE_FILE_SIZE"] / 10))
                                        file_h = None
                                    else:
                                        file_h = gzip.open(c_f_name, "r")
                                else:
                                    file_h = None
                                if file_h:
                                    rep_counter, last_pid = (0, 0)
                                    # cache of last result
                                    last_src, last_what, last_time = (None, None, None)
                                    for line in file_h:
                                        num_lines += 1
                                        line_p = line.strip().split(None, 4)
                                        if len(line_p) == 5 and line_p[3].startswith(self.__name) and line_p[4].count(":"):
                                            src, what = [x.strip() for x in line_p[4].split(":", 1)]
                                            if src.endswith("]"):
                                                if src.startswith("["):
                                                    src_p = src[1:].split("[")
                                                    src, src_pid = (src_p[0][:-1], int(src_p[1][:-1]))
                                                else:
                                                    src_p = src.split("[")
                                                    src, src_pid = (src_p[0], int(src_p[1][:-1]))
                                            else:
                                                src_pid = 0
                                            src = src.split()[0].lower()
                                            if src.startswith("/"):
                                                src = "FILE_REFERENCE"
                                            elif src.count("/"):
                                                src = src.split("/")[0]
                                            if src in logcheck_src_ignore:
                                                ignore_count[src] += 1
                                            else:
                                                # handle kernel-timestamps (ignore them)
                                                if src == "kernel":
                                                    k_re = k_ts_re.match(what)
                                                    if k_re:
                                                        what = k_re.group("what")
                                                add_it = True
                                                if src in ignore_prefixes.keys():
                                                    if [1 for x in ignore_prefixes[src] if what.startswith(x)]:
                                                        add_it = False
                                                        ignore_prefixes_count[src] += 1
                                                if add_it:
                                                    try:
                                                        int_time = time_to_int(line_p[2])
                                                    except:
                                                        self.log("Error transforming time '%s' to integer: %s" % (line_p[2],
                                                                                                                  process_tools.get_except_info()),
                                                                 logging_tools.LOG_LEVEL_ERROR)
                                                    else:
                                                        if last_src == src and last_what == what and abs(int_time - last_time) < 60:
                                                            rep_counter += 1
                                                        else:
                                                            if last_src:
                                                                if rep_counter > 1:
                                                                    # ignore pid
                                                                    line_dict.setdefault(last_src, {}).setdefault(last_what, []).append((rep_counter, last_time))
                                                                else:
                                                                    if last_pid:
                                                                        line_dict.setdefault(last_src, {}).setdefault(last_what, []).append((1, last_time, last_pid))
                                                                    else:
                                                                        line_dict.setdefault(last_src, {}).setdefault(last_what, []).append(int_time)
                                                            last_src, last_what, last_time, last_pid, rep_counter = (src, what, int_time, src_pid, 1)
                                    file_h.close()
                                    if last_src:
                                        if rep_counter > 1:
                                            # ignore pid
                                            line_dict.setdefault(last_src, {}).setdefault(last_what, []).append((rep_counter, last_time))
                                        else:
                                            if last_pid:
                                                line_dict.setdefault(last_src, {}).setdefault(last_what, []).append((1, last_time, last_pid))
                                            else:
                                                line_dict.setdefault(last_src, {}).setdefault(last_what, []).append(int_time)
                            except IOError:
                                self.log("IOError reading log-file %s or %s: %s (%s)" % (n_f_name,
                                                                                         c_f_name,
                                                                                         process_tools.get_except_info()),
                                         logging_tools.LOG_LEVEL_ERROR)
                                files_error += 1
                            except:
                                self.log("General Error while reading log-file %s or %s: %s" % (n_f_name,
                                                                                                os.path.basename(c_f_name),
                                                                                                process_tools.get_except_info()),
                                         logging_tools.LOG_LEVEL_ERROR)
                                files_error += 1
                            save_scaninfo(self, root_dir_p[0], root_dir_p[1], root_dir_p[2], line_dict, num_lines, ignore_count)
    ##                                 print self.__name, root_dir_p[0:3]
    ##                                 if line_dict:
    ##                                     for k, v in line_dict.iteritems():
    ##                                         print k
    ##                                         for what, times in v.iteritems():
    ##                                             print len(times), what
            self.log("finished walk for scan_log_dirs() found %s, checked %s in %.2f seconds (%s scanned, %s error)" % (logging_tools.get_plural("directory", dirs_found),
                                                                                                                        logging_tools.get_plural("directory", dirs_proc),
                                                                                                                        time.time() - start_time,
                                                                                                                        logging_tools.get_plural("file", files_proc),
                                                                                                                        logging_tools.get_plural("file", files_error)))
        else:
            self.log("log_start_dir %s not found, no syslog-scanning..." % (log_start_dir))
        return dirs_found, dirs_proc, files_proc, files_error
    def rotate_logs(self):
        dirs_found, dirs_proc, files_proc, files_error, files_del, dirs_del = (0, 0, 0, 0, 0, 0)
        start_time = time.time()
        log_start_dir = "%s/%s" % (self.__glob_config["SYSLOG_DIR"], self.__name)
        if os.path.isdir(log_start_dir):
            lsd_len = len(log_start_dir)
            self.log("starting walk for rotate_logs() in %s" % (log_start_dir))
            # directories processeds
            start_time = time.time()
            for root_dir, sub_dirs, files in os.walk(log_start_dir):
                dirs_found += 1
                if root_dir.startswith(log_start_dir):
                    root_dir_p = [int(x) for x in root_dir[lsd_len:].split("/") if x.isdigit()]
                    if len(root_dir_p) in [1, 2]:
                        # check for deletion of empty month-dirs
                        if not sub_dirs:
                            if len(root_dir_p) == 1:
                                host_info_str = "(dir %04d)" % (root_dir_p[0])
                            else:
                                host_info_str = "(dir %04d/%02d)" % (root_dir_p[0],
                                                                     root_dir_p[1])
                            err_files, ok_files = ([], [])
                            for file_name in [x for x in files]:
                                old_file = "%s/%s" % (root_dir, file_name)
                                try:
                                    os.unlink(old_file)
                                except IOError:
                                    err_files.append(old_file)
                                else:
                                    ok_files.append(old_file)
                            if err_files:
                                self.log("Had problems deleting %s %s: %s" % (logging_tools.get_plural("file", len(err_files)), host_info_str, ", ".join(err_files)))
                                files_error += len(err_files)
                            else:
                                # try to delete directory
                                try:
                                    os.rmdir(root_dir)
                                except:
                                    pass
                                else:
                                    dirs_del += 1
                            if ok_files:
                                self.log("Deleted %s %s: %s" % (logging_tools.get_plural("file", len(ok_files)), host_info_str, ", ".join(ok_files)))
                                files_del += len(ok_files)
                    elif len(root_dir_p) == 3:
                        dir_time = time.mktime([root_dir_p[0],
                                                root_dir_p[1],
                                                root_dir_p[2],
                                                0,
                                                0,
                                                0,
                                                0,
                                                0,
                                                0])
                        day_diff = int((start_time-dir_time) / (3600 * 24))
                        host_info_str = "(dir %04d/%02d/%02d)" % (root_dir_p[0],
                                                                  root_dir_p[1],
                                                                  root_dir_p[2])
                        if day_diff > max(1, self.__glob_config["KEEP_LOGS_TOTAL"]):
                            err_files, ok_files = ([], [])
                            for file_name in [x for x in files]:
                                old_file = "%s/%s" % (root_dir, file_name)
                                try:
                                    os.unlink(old_file)
                                except IOError:
                                    err_files.append(old_file)
                                else:
                                    ok_files.append(old_file)
                            if err_files:
                                self.log("Had problems deleting %s %s: %s" % (logging_tools.get_plural("file", len(err_files)), host_info_str, ", ".join(err_files)))
                                files_error += len(err_files)
                            else:
                                # try to delete directory
                                try:
                                    os.rmdir(root_dir)
                                except:
                                    pass
                                else:
                                    dirs_del += 1
                            if ok_files:
                                self.log("Deleted %s %s: %s" % (logging_tools.get_plural("file", len(ok_files)), host_info_str, ", ".join(ok_files)))
                                files_del += len(ok_files)
                        elif day_diff > max(1, self.__glob_config["KEEP_LOGS_UNCOMPRESSED"]):
                            dirs_proc += 1
                            err_files, ok_files = ([], [])
                            old_size, new_size = (0, 0)
                            for file_name in [x for x in files if not x.endswith(".gz") and not x.startswith(SCAN_TEXT_PREFIX)]:
                                old_file = "%s/%s" % (root_dir, file_name)
                                new_file = "%s/%s.gz" % (root_dir, file_name)
                                try:
                                    old_f_size = os.stat(old_file)[stat.ST_SIZE]
                                    new_fh = gzip.open(new_file, "wb", 4)
                                    new_fh.write(file(old_file, "r").read())
                                    new_fh.close()
                                    new_f_size = os.stat(new_file)[stat.ST_SIZE]
                                except:
                                    err_files.append(file_name)
                                else:
                                    old_size += old_f_size
                                    new_size += new_f_size
                                    ok_files.append(file_name)
                                    os.unlink(old_file)
                            if err_files:
                                self.log("Had problems compressing %s %s: %s" % (logging_tools.get_plural("file", len(err_files)), host_info_str, ", ".join(err_files)))
                                files_error += len(err_files)
                            if ok_files:
                                self.log("Compressed %s %s: %s" % (logging_tools.get_plural("file", len(ok_files)), host_info_str, ", ".join(ok_files)))
                                files_proc += len(ok_files)
                            if err_files or ok_files:
                                self.log("Stats for directory %s: Saved %s (%.2f %%, new size: %s, orig size: %s)" % (root_dir,
                                                                                                                      logging_tools.get_size_str(old_size - new_size),
                                                                                                                      100. * (float(old_size - new_size) / float(max(1, old_size))),
                                                                                                                      logging_tools.get_size_str(new_size),
                                                                                                                      logging_tools.get_size_str(old_size)))
            self.log("Found %s, checked %s in %.2f seconds (%s ok, %s error)" % (logging_tools.get_plural("directory", dirs_found),
                                                                                 logging_tools.get_plural("directory", dirs_proc),
                                                                                 time.time() - start_time,
                                                                                 logging_tools.get_plural("file", files_proc),
                                                                                 logging_tools.get_plural("file", files_error)))
            self.log("finished walk for rotate_logs(), found %s, checked %s, deleted %s in %.2f seconds (%s ok, deleted %s, %s error)" % (logging_tools.get_plural("directory", dirs_found),
                                                                                                                                          logging_tools.get_plural("directory", dirs_proc),
                                                                                                                                          logging_tools.get_plural("directory", dirs_del),
                                                                                                                                          time.time() - start_time,
                                                                                                                                          logging_tools.get_plural("file", files_proc),
                                                                                                                                          logging_tools.get_plural("file", files_del),
                                                                                                                                          logging_tools.get_plural("file", files_error)))
        else:
            self.log("log_start_dir %s not found, no log-rotate ..." % (log_start_dir))
        return dirs_found, dirs_proc, files_proc, files_error, files_del, dirs_del

def concentrate_scaninfo(mach_struct):
    log_start_dir = "%s/%s" % (mach_struct.get_glob_config()["SYSLOG_DIR"], mach_struct.get_name())
    if os.path.isdir(log_start_dir):
        mach_struct.log("log_start_dir %s found, start concentrating of scaninfo" % (log_start_dir))
        lsd_len = len(log_start_dir)
        start_time = time.time()
        mach_struct.log("starting walk for concentrate_scaninfo() in %s" % (log_start_dir))
        # directories processed
        for root_dir, sub_dirs, files in os.walk(log_start_dir, 0):
            if root_dir.startswith(log_start_dir):
                concentrate = False
                root_dir_p = [int(x) for x in root_dir[lsd_len:].split("/") if x.isdigit()]
                if len(root_dir_p) == 2:
                    year, month = (int(root_dir_p[0]),
                                   int(root_dir_p[1]))
                    mtime = mach_struct.scaninfo_mtime(year, month)
                    if mtime:
                        sub_times = [1 for x in [mach_struct.scaninfo_mtime(year, month, day) for day in [int(x) for x in sub_dirs if x.isdigit()]] if x and x > mtime]
                        concentrate = sub_times and True or False
                    else:
                        concentrate = True
                    if concentrate:
                        month_dict = {}
                        # concentrate day-info
                        for day in [int(x) for x in sub_dirs if x.isdigit()]:
                            day_dict = load_scaninfo_dict(mach_struct, year, month, day)
                            for target, t_struct in day_dict.iteritems():
                                for what, time_info in t_struct.iteritems():
                                    month_dict.setdefault(target, {}).setdefault(what, {})[day] = time_info
                        save_scaninfo(mach_struct, year, month, 0, month_dict)
                elif len(root_dir_p) == 1:
                    year = int(root_dir_p[0])
                    mtime = mach_struct.scaninfo_mtime(year)
                    if mtime:
                        sub_times = [1 for x in [mach_struct.scaninfo_mtime(year, month) for month in [int(x) for x in sub_dirs if x.isdigit()]] if x and x > mtime]
                        concentrate = sub_times and True or False
                    else:
                        concentrate = True
                    if concentrate:
                        year_dict = {}
                        # concentrate month-info
                        for month in [int(x) for x in sub_dirs if x.isdigit()]:
                            month_dict = load_scaninfo_dict(mach_struct, year, month)
                            for target, t_struct in month_dict.iteritems():
                                for what, day_dict in t_struct.iteritems():
                                    year_dict.setdefault(target, {}).setdefault(what, {})[month] = day_dict
                        save_scaninfo(mach_struct, year, 0, 0, year_dict)
                elif len(root_dir_p) == 0:
                    mtime = mach_struct.scaninfo_mtime()
                    if mtime:
                        sub_times = [1 for x in [mach_struct.scaninfo_mtime(year) for year in [int(x) for x in sub_dirs if x.isdigit()]] if x and x > mtime]
                        concentrate = sub_times and True or False
                    else:
                        concentrate = True
                    if concentrate:
                        mach_dict = {}
                        # concentrate year-info
                        for year in [int(x) for x in sub_dirs if x.isdigit()]:
                            year_dict = load_scaninfo_dict(mach_struct, year)
                            for target, t_struct in year_dict.iteritems():
                                for what, month_dict in t_struct.iteritems():
                                    mach_dict.setdefault(target, {}).setdefault(what, {})[year] = month_dict
                        save_scaninfo(mach_struct, 0, 0, 0, mach_dict)
        mach_struct.log("finished walk for concentrate_scaninfo() in %s in %.2f seconds" % (log_start_dir,
                                                                                            time.time() - start_time))
                    
def load_scaninfo_dict(mach_struct, year=0, month=0, day=0):
    def check_valid(in_stuff):
        valid = True
        if type(in_stuff) == type({}):
            for k, v in in_stuff.iteritems():
                if not check_valid(v):
                    valid = False
        elif type(in_stuff) == type([]):
            for v in in_stuff:
                if not check_valid(v):
                    valid = False
        else:
            if type(in_stuff) == type(()) and type(in_stuff[0]) == type(""):
                valid = False
        return valid
    ret_dict = {}
    log_target_dir = "%s/%s" % (mach_struct.get_glob_config()["SYSLOG_DIR"], mach_struct.get_name())
    for what, length in [(year , 4),
                         (month, 2),
                         (day  , 2)]:
        if int(what):
            log_target_dir = ("%%s/%%0%dd" % (length)) % (log_target_dir, int(what))
    if not os.path.isdir(log_target_dir):
        mach_struct.log("cannot load scan_info from %s (directory does not exist)" % (log_target_dir))
    else:
        scan_file_name = "%s/%s" % (log_target_dir, SCAN_DICT_FILE)
        if os.path.isfile(scan_file_name):
            try:
                ret_dict = cPickle.loads(bz2.decompress(file(scan_file_name, "r").read()))
            except:
                mach_struct.log("Error while reading scan-file in %s: %s" % (log_target_dir,
                                                                             process_tools.get_except_info()),
                                logging_tools.LOG_LEVEL_ERROR)
                ret_dict = {}
            else:
                # check dict for validity
                if not check_valid(ret_dict):
                    mach_struct.log("Dictionary from file %s is not valid, deleting ..." % (scan_file_name))
                    ret_dict = {}
                    try:
                        os.unlink(scan_file_name)
                    except:
                        mach_struct.log("Error while removing file %s: %s" % (scan_file_name,
                                                                              process_tools.get_except_info()),
                                        logging_tools.LOG_LEVEL_ERROR)
    return ret_dict

def save_scaninfo(mach_struct, year, month, day, s_dict, num_lines=0, ignore_dict={}):
    def get_str(stuff):
        if type(stuff) == type(()):
            if len(stuff) == 2:
                # format rep_counter, time
                return "%s%s" % (int_to_time(stuff[1]), stuff[0] > 1 and "[%d]" % (stuff[0]) or "")
            else:
                # format rep_counter(==1), time, pid
                return "%s%s(%d)" % (int_to_time(stuff[1]), stuff[0] > 1 and "[%d]" % (stuff[0]) or "", stuff[2])
        else:
            # simple timestamp
            return int_to_time(stuff)
    def iter_write_times(file_h, in_dict, act_level, pre_list=[]):
        if type(in_dict) == type({}):
            act_dts = sorted(in_dict.keys())
            if act_level == 4:
                f_str = "%s-"
            else:
                f_str = "%%0%dd-" % ({0 : 2,
                                      1 : 2,
                                      2 : 2,
                                      3 : 4}[act_level])
            act_pre_list = [x for x in pre_list]
            for act_dt in act_dts:
                iter_write_times(file_h, in_dict[act_dt], act_level-1, act_pre_list + [f_str % (act_dt)])
                #act_pre_list = [" " * len(x) for x in pre_list]
        else:
            file_h.write("  %s%s\n" % (pre_list and "%s " % (("".join(pre_list))[:-1]) or "", " ".join([get_str(stuff) for stuff in in_dict])))
    def iter_sub_entries(in_dict):
        if type(in_dict) == type({}):
            num_e = 0
            for act_dt, sub_dict in in_dict.iteritems():
                num_e += iter_sub_entries(sub_dict)
        else:
            num_e = len(in_dict)
        return num_e
    if mach_struct.get_name():
        log_target_dir = "%s/%s" % (mach_struct.get_glob_config()["SYSLOG_DIR"], mach_struct.get_name())
    else:
        log_target_dir = mach_struct.get_glob_config()["SYSLOG_DIR"]
    ignore_count = len([1 for k, v in ignore_dict.iteritems() if v])
    info_str = ""
    for what, length in [(year , 4),
                         (month, 2),
                         (day  , 2)]:
        if what:
            add_part       = ("%%0%dd" % (length)) % (what)
            log_target_dir = "%s/%s" % (log_target_dir, add_part)
            info_str       = "%s/%s" % (info_str, add_part)
    if not info_str:
        info_str = mach_struct.get_name()
    if info_str and info_str.startswith("/"):
        info_str = info_str[1:]
    if not os.path.isdir(log_target_dir):
        mach_struct.log("cannot save scan_info to %s (directory does not exist)" % (log_target_dir))
    else:
        #mach_struct.log("cannot save scan_info to %s (directory does not exist)" % (os.path.dirname(log_target_name)))
        try:
            num_targets, num_whats = (0, 0)
            si_file = file("%s/%s" % (log_target_dir, SCAN_TEXT_FILE), "w")
            targets = sorted(s_dict.keys())
            for target in targets:
                num_targets += 1
                whats = sorted(s_dict[target].keys())
                for what in whats:
                    num_whats += 1
                    si_file.write("%s %d %s\n" % (target, iter_sub_entries(s_dict[target][what]), what))
                    td_dict = s_dict[target][what]
                    # level, 0 is the lowest (per-day basis), then month, year and device
                    if day:
                        level = 0
                    elif month:
                        level = 1
                    elif year:
                        level = 2
                    else:
                        if mach_struct.get_name():
                            level = 3
                        else:
                            level = 4
                    iter_write_times(si_file, td_dict, level)
            si_file.close()
            file("%s/%s" % (log_target_dir, SCAN_DICT_FILE), "w").write(bz2.compress(cPickle.dumps(s_dict)))
            if ignore_dict:
                file("%s/%s" % (log_target_dir, SCAN_IGNORE_FILE), "w").write("\n".join(["%s: %d" % (k, v) for k, v in ignore_dict.iteritems()] + [""]))
        except IOError:
            mach_struct.log("IOError while creating scan-files in %s: %s" % (log_target_dir,
                                                                             process_tools.get_except_info()),
                            logging_tools.LOG_LEVEL_ERROR)
        else:
            mach_struct.log("ScanInfo for %s%s: %s%s, %s%s" % (info_str,
                                                               num_lines and " (%s scanned)" % (logging_tools.get_plural("line", num_lines)) or "",
                                                               logging_tools.get_plural("source", num_targets),
                                                               targets and " (%s)" % (", ".join(targets)) or "",
                                                               logging_tools.get_plural("string", num_whats),
                                                               ignore_dict and " and %s of %s" % (logging_tools.get_plural("ignored source", ignore_count),
                                                                                                  logging_tools.get_plural("source", len(ignore_dict.keys()))) or ""))
            
class all_devices(object):
    def __init__(self, log_queue, glob_config, loc_config, db_con, **args):
        self.__lut = {}
        self.__lock = threading.Lock()
        self.__log_queue = log_queue
        self.__glob_config, self.__loc_config = (glob_config, loc_config)
        self.__db_con = db_con
        self.log("all_devices struct init")
        self.__change_lock = threading.Lock()
        self.__write_lock  = threading.Lock()
        self.__readers = 0
        self.__timeout = args.get("timeout", 5)
        self.__verbose = args.get("verbose", False)
    def is_an_ip(self, key):
        if key.count(".") == 3 and len([True for x in key.split(".") if x.isdigit()]):
            return True
        else:
            return False
    def acquire_write_lock(self):
        if self.__verbose:
            self.log("trying to acquire write-lock")
        w_lock = False
        while not w_lock:
            self.__change_lock.acquire()
            if not self.__readers:
                # no readers, try to get write_lock
                w_lock = self.__write_lock.acquire(False)
            if not w_lock:
                self.__change_lock.release()
                if self.__verbose:
                    self.log(" ... not successfull, sleeping for %d seconds" % (self.__timeout))
                time.sleep(self.__timeout)
        self.__change_lock.release()
        if self.__verbose:
            self.log("successfully acquired write-lock")
    def release_write_lock(self):
        if self.__verbose:
            self.log("releasing write-lock")
        self.__change_lock.acquire()
        self.__write_lock.release()
        self.__change_lock.release()
    def acquire_read_lock(self):
        if self.__verbose:
            self.log("trying to acquire read-lock")
        r_lock = False
        while not r_lock:
            self.__change_lock.acquire()
            # can we get a write_lock ?
            r_lock = self.__write_lock.acquire(False)
            # no, writer active
            if not r_lock:
                self.__change_lock.release()
                if self.__verbose:
                    self.log(" ... not successfull, sleeping for %d seconds" % (self.__timeout))
                time.sleep(self.__timeout)
        self.__readers += 1
        self.__write_lock.release()
        self.__change_lock.release()
        if self.__verbose:
            self.log("successfully acquired read-lock")
    def release_read_lock(self):
        if self.__verbose:
            self.log("releasing read-lock")
        self.__change_lock.acquire()
        self.__readers -= 1
        self.__change_lock.release()
    def get_log_queue(self):
        return self.__log_queue
    def get_glob_config(self):
        return self.__glob_config
    def get_loc_config(self):
        return self.__loc_config
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__log_queue.put(("log", (threading.currentThread().getName(), what, lev)))
    def db_sync(self, rescan=False):
        self.log("Checking for new devices")
        sql_add_str = ""
        dc = self.__db_con.get_connection(SQL_ACCESS)
        # newer use ips from slave networks
        dc.execute("SELECT d.name, d.device_idx, ip.ip, dt.identifier, nw.postfix, nt.identifier AS nettype FROM network nw, device d, netip ip, netdevice nd, device_type dt, network_type nt WHERE " + \
                   "dt.device_type_idx=d.device_type AND ip.netdevice=nd.netdevice_idx AND ip.network=nw.network_idx AND nd.device=d.device_idx AND nt.network_type_idx=nw.network_type AND nt.identifier != 's' ORDER BY d.name, nd.devname, ip.ip")
        mach_stuff = {}
        for mach in dc.fetchall():
            name = mach["name"]
            if not mach_stuff.has_key(name):
                mach_stuff[name] = {"device_idx" : mach["device_idx"],
                                    "identifier" : mach["identifier"],
                                    "ips"        : {}}
            if mach["ip"] not in mach_stuff[name]["ips"].keys():
                mach_stuff[name]["ips"][mach["ip"]] = (mach["postfix"], mach["nettype"])
        self.acquire_write_lock()
        for name in sorted(mach_stuff.keys()):
            act_mach_stuff = mach_stuff[name]
            if act_mach_stuff["identifier"] == "H":
                if not self.__lut.has_key(name):
                    newmach = machine(name, self, act_mach_stuff["device_idx"], dc, act_mach_stuff["ips"], rescan)
                else:
                    self.__lut[name].check_for_changed_ips(act_mach_stuff["ips"])
        self.release_write_lock()
        self.log("  ... done")
        dc.release()
    def keys(self):
        return self.__lut.keys()
    def has_key(self, key):
        return self.__lut.has_key(key)
    def __setitem__(self, key, val):
        self.__lut[key] = val
    def __getitem__(self, key):
        return self.__lut[key]
    def __delitem__(self, key):
        del self.__lut[key]

class cluster_struct(object):
    # used to emulate the mach_struct structure in save/load/concentrate scaninfo
    def __init__(self, log_queue, glob_config):
        self.__log_queue = log_queue
        self.__glob_config = glob_config
    def set_name(self, name):
        self.__name = name
    def get_name(self):
        return self.__name
    def get_glob_config(self):
        return self.__glob_config
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__log_queue.put(("log", (threading.currentThread().getName(), what, lev)))
    def __del__(self):
        self.__log_queue.put(("log", (threading.currentThread().getName(), "deleting cluster_struct", logging_tools.LOG_LEVEL_OK)))

class logcheck_thread(threading_tools.thread_obj):
    def __init__(self, glob_config, loc_config, db_con, log_queue):
        self.__db_con = db_con
        self.__log_queue = log_queue
        self.__glob_config, self.__loc_config = (glob_config, loc_config)
        threading_tools.thread_obj.__init__(self, "logcheck", queue_size=100)
        self.register_func("set_ad_struct", self._set_ad_struct)
        self.register_func("set_queue_dict", self._set_queue_dict)
        self.register_func("set_variable_dict", self._set_variable_dict)
    def _set_queue_dict(self, q_dict):
        self.__queue_dict = q_dict
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__log_queue.put(("log", (self.name, what, lev)))
    def thread_running(self):
        self.send_pool_message(("new_pid", (self.name, self.pid)))
    def _set_ad_struct(self, ad_struct):
        self.log("got ad_struct")
        self.__ad_struct = ad_struct
    def loop_end(self):
        self.send_pool_message(("remove_pid", (self.name, self.pid)))
    def _set_variable_dict(self, v_dict):
        self._scan(v_dict)
        self.send_pool_message(("request_exit", self.name))
    def _scan(self, v_dict):
        start_time = time.time()
        self.__ad_struct.acquire_read_lock()
        dev_names = sorted(self.__ad_struct.keys())
        dirs_found, dirs_proc, files_proc, files_error, files_del, dirs_del = (0, 0, 0, 0, 0, 0)
        for name in dev_names:
            mach_struct = self.__ad_struct[name]
            l_dirs_found, l_dirs_proc, l_files_proc, l_files_error, l_files_del, l_dirs_del = mach_struct.rotate_logs()
            dirs_found  += l_dirs_found
            dirs_proc   += l_dirs_proc
            files_proc  += l_files_proc
            files_error += l_files_error
            files_del   += l_files_del
            dirs_del    += l_dirs_del
        self.log("Found %s, rotated %s, deleted %s in %s (%s ok, deleted %s, %s error)" % (logging_tools.get_plural("directory", dirs_found),
                                                                                           logging_tools.get_plural("directory", dirs_proc),
                                                                                           logging_tools.get_plural("directory", dirs_del),
                                                                                           logging_tools.get_diff_time_str(time.time() - start_time),
                                                                                           logging_tools.get_plural("file", files_proc),
                                                                                           logging_tools.get_plural("file", files_del),
                                                                                           logging_tools.get_plural("file", files_error)))
        start_time = time.time()
        dirs_found, dirs_proc, files_proc, files_error = (0, 0, 0, 0)
        for name in dev_names:
            mach_struct = self.__ad_struct[name]
            l_dirs_found, l_dirs_proc, l_files_proc, l_files_error = mach_struct.scan_log_dirs(v_dict["reparse"])
            dirs_found  += l_dirs_found
            dirs_proc   += l_dirs_proc
            files_proc  += l_files_proc
            files_error += l_files_error
            concentrate_scaninfo(mach_struct)
        self.__ad_struct.release_read_lock()
        self.log("Found %s, checked %s in %s (%s scanned, %s error)" % (logging_tools.get_plural("directory", dirs_found),
                                                                        logging_tools.get_plural("directory", dirs_proc),
                                                                        logging_tools.get_diff_time_str(time.time() - start_time),
                                                                        logging_tools.get_plural("file", files_proc),
                                                                        logging_tools.get_plural("file", files_error)))
        # concentrate all devices
        start_time = time.time()
        self.log("Concentrating device-logs")
        log_start_dir = "%s" % (self.__glob_config["SYSLOG_DIR"])
        if os.path.isdir(log_start_dir):
            c_dict = {}
            c_struct = cluster_struct(self.__log_queue, self.__glob_config)
            for dev_name in dev_names:
                self.log(" device %-20s (%3d of %3d)" % (dev_name,
                                                         dev_names.index(dev_name),
                                                         len(dev_names)))
                c_struct.set_name(dev_name)
                dev_dict = load_scaninfo_dict(c_struct)
                for target, t_struct in dev_dict.iteritems():
                    for what, year_dict in t_struct.iteritems():
                        c_dict.setdefault(target, {}).setdefault(what, {})[dev_name] = year_dict
                del dev_dict
                #dev_dict = None
                c_struct.set_name("")
            self.log("saving scaninfo")
            save_scaninfo(c_struct, 0, 0, 0, c_dict)
            del c_struct
            del c_dict
        self.log("finished in %s" % (logging_tools.get_diff_time_str(time.time() - start_time)))
        if v_dict["restart_after_run"]:
            self.log("restarting logcheck-server via cluster-server")
            self.__queue_dict["com_queue"].put(("send_string", ("localhost", 8004, server_command.server_command(command="modify_service",
                                                                                                                 option_dict={"service" : "logcheck-server",
                                                                                                                              "mode"    : "restart"}))))
        
class com_thread(threading_tools.thread_obj):
    def __init__(self, glob_config, loc_config, db_con, log_queue):
        self.__db_con = db_con
        self.__log_queue = log_queue
        self.__glob_config, self.__loc_config = (glob_config, loc_config)
        threading_tools.thread_obj.__init__(self, "com", queue_size=100)
        self.register_func("set_queue_dict", self._set_queue_dict)
        self.register_func("set_netserver", self._set_netserver)
        self.register_func("con", self._con)
        self.register_func("send_string", self._send_string)
        self.register_func("node_ok_result", self._node_ok_result)
        self.register_func("node_error_result", self._node_error_result)
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__log_queue.put(("log", (self.name, what, lev)))
    def loop_end(self):
        self.send_pool_message(("remove_pid", (self.name, self.pid)))
    def thread_running(self):
        self.send_pool_message(("new_pid", (self.name, self.pid)))
        self._set_netserver(None)
    def _set_queue_dict(self, q_dict):
        self.__queue_dict = q_dict
    def _set_netserver(self, ns):
        self.__ns = ns
        self.log("Netserver is %s" % (self.__ns and "set" or "not set"))
    def _con(self, tcp_obj):
        in_data = tcp_obj.get_decoded_in_str()
        try:
            server_com = server_command.server_command(in_data)
        except:
            tcp_obj.add_to_out_buffer("error no valid server_command")
            self.log("Got invalid data from host %s (port %d): %s" % (tcp_obj.get_src_host(),
                                                                      tcp_obj.get_src_port(),
                                                                      in_data[0:20]),
                     logging_tools.LOG_LEVEL_WARN)
        else:
            srv_com_name = server_com.get_command()
            call_func = {"status" : self._status}.get(srv_com_name, None)
            if call_func:
                call_func(tcp_obj, server_com)
            else:
                self.log("Got unknown server_command '%s' from host %s (port %d)" % (srv_com_name,
                                                                                     tcp_obj.get_src_host(),
                                                                                     tcp_obj.get_src_port()),
                         logging_tools.LOG_LEVEL_WARN)
                res_str = "unknown command %s" % (srv_com_name)
                tcp_obj.add_to_out_buffer(server_command.server_reply(state=server_command.SRV_REPLY_STATE_ERROR, result=res_str),
                                          res_str)
    def _status(self, tcp_obj, s_com):
        tp = self.get_thread_pool()
        num_threads, num_ok = (tp.num_threads(False),
                               tp.num_threads_running(False))
        if num_ok == num_threads:
            ret_str = "ok all %d threads running, version %s" % (num_ok, self.__loc_config["VERSION_STRING"])
        else:
            ret_str = "error only %d of %d threads running, version %s" % (num_ok, num_threads, self.__loc_config["VERSION_STRING"])
        server_reply = server_command.server_reply()
        server_reply.set_ok_result(ret_str)
        tcp_obj.add_to_out_buffer(server_reply, "status")
    def _send_string(self, (t_host, t_port, t_com)):
        self.log("Sending string (length %s) to %s (port %d)" % (logging_tools.get_plural("byte", len(t_com)),
                                                                 t_host,
                                                                 t_port))
        self.__ns.add_object(net_tools.tcp_con_object(self._new_tcp_con,
                                                      connect_state_call = self._connect_state_call,
                                                      connect_timeout_call = self._connect_timeout,
                                                      target_host = t_host,
                                                      target_port = t_port,
                                                      timeout = 20,
                                                      bind_retries = 1,
                                                      rebind_wait_time = 1,
                                                      add_data = t_com))
    def _connect_state_call(self, **args):
        if args["state"] == "error":
            dev_com = args["socket"].get_add_data()
            self.log("error connecting (command %s)" % (dev_com.get_command()), logging_tools.LOG_LEVEL_ERROR)
            args["socket"].delete()
    def _connect_timeout(self, sock):
        dev_com = sock.get_add_data()
        self.log("timeout while connecting (command %s)" % (dev_com.get_command()), logging_tools.LOG_LEVEL_ERROR)
        sock.delete()
        sock.close()
    def _new_tcp_con(self, sock):
        return node_con_obj(self, sock.get_target_host(), sock.get_add_data())
    def _node_ok_result(self):
        self.log("command send")
    def _node_error_result(self):
        self.log("command not send", logging_tools.LOG_LEVEL_ERROR)

class logging_thread(threading_tools.thread_obj):
    def __init__(self, glob_config, loc_config):
        self.__sep_str = "-" * 50
        self.__glob_config, self.__loc_config = (glob_config, loc_config)
        self.__machlogs, self.__glob_log, self.__glob_cache = ({}, None, [])
        threading_tools.thread_obj.__init__(self, "logging", queue_size=100, priority=10)
        self.register_func("log", self._log)
        self.register_func("mach_log", self._mach_log)
        self.register_func("set_ad_struct", self._set_ad_struct)
        self.register_func("set_queue_dict", self._set_queue_dict)
        self.register_func("update", self._update)
        self.register_func("udp_recv", self._udp_recv)
        self.register_func("remove_handle", self._remove_handle)
        self.__ad_struct = {}
        self._build_regexp()
        self._init_syslog_connection_check()
    def thread_running(self):
        self.send_pool_message(("new_pid", (self.name, self.pid)))
        root = self.__glob_config["LOG_DIR"]
        if not os.path.exists(root):
            os.makedirs(root)
        glog_name = "%s/log" % (root)
        self.__glob_log = logging_tools.logfile(glog_name)
        self.__glob_log.write(self.__sep_str)
        self.__glob_log.write("Opening log")
        self.__delay_array = []
    def _build_regexp(self):
        sys.path.append("/usr/local/sbin")
        log_lines, sys_dict = process_tools.fetch_sysinfo()
        # determine correct regexp
        if sys_dict["version"] in ["8.0", "8.1"] and sys_dict["vendor"] != "redhat":
            self.log("System Version is < SUSE 8.2, using non-standard regexp for syslog-ng messages")
            self.__line_re = re.compile("^\<\d+\>(?P<time>\S+\s+\S+\s+\S+)\s+(?P<facility>\S+):\s+(?P<message>.*)$")
        else:
            self.log("System Version is >= SUSE 8.2 or RedHat, using standard regexp for syslog-ng messages")
            self.__line_re = re.compile("^\<\d+\>(?P<time>\S+\s+\S+\s+\S+)\s+(?P<host>\S+)\s+(?P<facility>\S+):\s+(?P<message>.*)$")
    def _udp_recv(self, data):
        in_line = data.strip()
        line_m = self.__line_re.match(in_line)
        if line_m:
            mess_str = line_m.group("message").strip()
            if mess_str.startswith(SYSLOG_THREAD_STR):
                self._syslog_connection(False)
            else:
                self.log("log_line %s is unknown (from syslogger)" % (mess_str),
                         logging_tools.LOG_LEVEL_WARN)
        else:
            try:
                log_com, ret_str = self._decode_in_str(data)
            except:
                self.log("error reconstructing in_data (len of data: %d): %s" % (len(data),
                                                                                 process_tools.get_except_info()),
                         logging_tools.LOG_LEVEL_ERROR)
            else:
                log_line = log_com and log_com.get_log_line() or ret_str
                if log_line.count(SYSLOG_THREAD_STR):
                    self._syslog_connection(True)
                else:
                    self.log("log_line %s is unknown (direct)" % (log_line), logging_tools.LOG_LEVEL_WARN)
                if log_com:
                    log_com.close()
                    del log_com
    def _syslog_connection(self, direct):
        if direct:
            # direct connection
            restart = False
            self.__check_state += 1
            if self.__check_state > 1:
                if self.__check_state > self.__check_state_threshold:
                    self.log("syslog thread_check status %d > threshold %d" % (self.__check_state,
                                                                               self.__check_state_threshold),
                             logging_tools.LOG_LEVEL_ERROR)
                    self.send_pool_message("restart_syslog")
                    self._init_syslog_connection_check()
                    self.__syslog_state_ok = False
                else:
                    self.log("syslog thread_check status is now %d (threshold: %d)" % (self.__check_state,
                                                                                       self.__check_state_threshold),
                             logging_tools.LOG_LEVEL_WARN)
        else:
            # connection vi syslogger
            if self.__check_state > 1:
                self.log("reseting syslog check_state to 0", logging_tools.LOG_LEVEL_WARN)
            self.__check_state = 0
            if not self.__syslog_state_ok:
                self.__syslog_state_ok = True
                self.log("syslog_state is now ok")
    def _init_syslog_connection_check(self):
        self.__csok_iter = 0
        self.__check_state = 0
        self.__check_state_threshold = self.__glob_config["SYSLOG_OK_ITER"]
        self.__syslog_state_ok = False
    def _decode_in_str(self, in_str):
        if in_str.startswith("bpd"):
            bpd_vers = int(in_str[3])
            if bpd_vers == 1:
                pre_offset = 32
                pre_stuff = list(struct.unpack("6if", in_str[4:pre_offset]))
            elif bpd_vers == 2:
                pre_offset = 36
                pre_stuff = list(struct.unpack("6id", in_str[4:pre_offset]))
            else:
                raise ValueError, "unknown bpd_version %d" % (bpd_vers)
            log_lev = pre_stuff.pop(0)
            log_time = pre_stuff.pop(-1)
            f_str = "".join("%ds" % (x) for x in pre_stuff)
            log_name, log_command, log_host, log_thread, log_str = struct.unpack(f_str, in_str[pre_offset:pre_offset + sum(pre_stuff)])
            log_com = net_logging_tools.log_command(log_name, log_command, log_str, log_lev, log_host, log_time, log_thread)
            ret_str = in_str[pre_offset + sum(pre_stuff):]
        else:
            try:
                in_dict = cPickle.loads(in_str)
            except:
                try:
                    in_dict = marshal.loads(in_str)
                except:
                    in_dict = {}
            if in_dict:
                log_com = net_logging_tools.log_command(in_dict.get("name", "unknown_name"),
                                                        log_str=in_dict["log_str"],
                                                        level  =in_dict.get("log_level", logging_tools.LOG_LEVEL_OK),
                                                        host   =in_dict.get("host", "unknown_host"),
                                                        thread =in_dict.get("thread", "unknown_thread"))
                ret_str = ""
            else:
                raise ValueError, "Unable to dePickle or deMarshal string"
        return log_com, ret_str
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
        self.__dhcp_queue = q_dict["dhcp_queue"]
    def loop_end(self):
        for mach in self.__machlogs.keys():
            self.__machlogs[mach].write("Closing log")
            self.__machlogs[mach].close()
        self.__glob_log.write("Closed %s" % (logging_tools.get_plural("machine log", len(self.__machlogs.keys()))))
        self.__glob_log.write("Closing log")
        self.__glob_log.write("logging thread exiting (pid %d)" % (self.pid))
        self.__glob_log.close()
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self._mach_log((self.name, what, lev, ""))
    def _log(self, (s_thread, what, lev)):
        self._mach_log((s_thread, what, lev, ""))
    def _mach_log(self, (s_thread, what, lev, mach)):
        if mach == "":
            handle, pre_str = (self.__glob_log, "")
        else:
            handle, pre_str = self._get_handle(mach)
        if handle is None:
            self.__glob_cache.append((s_thread, what, lev, mach))
        else:
            log_act = []
            if self.__glob_cache:
                for c_s_thread, c_what, c_lev, c_mach in self.__glob_cache:
                    c_handle, c_pre_str = self._get_handle(c_mach)
                    self._handle_log(c_handle, c_s_thread, c_pre_str, c_what, c_lev, c_mach)
                self.__glob_cache = []
            self._handle_log(handle, s_thread, pre_str, what, lev, mach)
    def _handle_log(self, handle, s_thread, pre_str, what, lev, mach):
        handle.write("%-5s(%s) : %s%s" % (logging_tools.get_log_level_str(lev),
                                          s_thread,
                                          pre_str,
                                          what))
    def _remove_handle(self, name):
        self.log("Closing log for device %s" % (name))
        self._mach_log((self.name, "(%s) : Closing log" % (self.name), logging_tools.LOG_LEVEL_OK, name))
        self.__machlogs[name].close()
        del self.__machlogs[name]
    def _get_handle(self, name):
        devname_dict = {}
        if self.__machlogs.has_key(name):
            handle, pre_str = (self.__machlogs[name], "")
        else:
            if self.__ad_struct.has_key(name):
                mach = self.__ad_struct[name]
                name = mach.name
                machdir = "%s/%s" % (self.__glob_config["LOG_DIR"], name)
                if not os.path.exists(machdir):
                    self.log("Creating dir %s for %s" % (machdir, name))
                    os.makedirs(machdir)
                self.__machlogs[name] = logging_tools.logfile("%s/log" % (machdir))
                self.__machlogs[name].write(self.__sep_str)
                self.__machlogs[name].write("Opening log")
                #glog.write("# of open machine logs: %d" % (len(self.__machlogs.keys())))
                handle, pre_str = (self.__machlogs[name], "")
            else:
                handle, pre_str = (self.__glob_log, "device %s: " % (name))
        return (handle, pre_str)

class server_thread_pool(threading_tools.thread_pool):
    def __init__(self, db_con, g_config, loc_config):
        self.__log_cache, self.__log_queue = ([], None)
        self.__db_con = db_con
        self.__glob_config, self.__loc_config = (g_config, loc_config)
        threading_tools.thread_pool.__init__(self, "main", blocking_loop=False)
        self.__msi_block = self._init_msi_block()
        self.register_exception("int_error", self._int_error)
        self.register_exception("term_error", self._int_error)
        self.register_exception("hup_error", self._hup_error)
        self.register_func("new_pid", self._new_pid)
        self.register_func("remove_pid", self._remove_pid)
        self.register_func("request_exit", self._request_exit)
        self.register_func("restart_syslog", self._restart_syslog_ng)
        self.__log_queue = self.add_thread(logging_thread(self.__glob_config, self.__loc_config), start_thread=True).get_thread_queue()
        # syslog_check_counter
        self.__syslog_check_counter, self.__syslog_check_num = (0, self.__glob_config["SYSLOG_CHECK_ERROR"])
        self.__bind_state_dict = {}
        self.__ns = net_tools.network_server(timeout=2, log_hook=self.log, poll_verbose=self.__loc_config["VERBOSE"] > 1)
        self.__ns.add_object(net_tools.unix_domain_bind(self._new_ud_recv, socket=self.__glob_config["SYSLOG_SOCKET"], mode=0666, bind_state_call=self._bind_state_call))[0]
        self.__ns.add_object(net_tools.tcp_bind(self._new_tcp_con, port=self.__glob_config["COMPORT"], bind_retries=5, bind_state_call=self._bind_state_call, timeout=15))
        # run_idx for syslog-check
        self.__run_idx = 0
        # prepare directories
        self._prepare_directories()
        # log config
        self._log_config()
        # enable syslog_config
        self._enable_syslog_config()
        dc = self.__db_con.get_connection(SQL_ACCESS)
        # re-insert config
        self._re_insert_config(dc)
        self.__ad_struct = all_devices(self.__log_queue, self.__glob_config, self.__loc_config, self.__db_con)
        self.__ad_struct.db_sync()
        self.__sql_queue  = self.add_thread(sql_thread(self.__glob_config, self.__loc_config, self.__db_con, self.__log_queue), start_thread=True).get_thread_queue()
        self.__scan_queue = self.add_thread(scan_thread(self.__glob_config, self.__loc_config, self.__db_con, self.__log_queue), start_thread=True).get_thread_queue()
        self.__com_queue  = self.add_thread(com_thread(self.__glob_config, self.__loc_config, self.__db_con, self.__log_queue), start_thread=True).get_thread_queue()
        self.__queue_dict = {"logging_queue" : self.__log_queue,
                             "sql_queue"     : self.__sql_queue,
                             "scan_queue"    : self.__scan_queue,
                             "com_queue"     : self.__com_queue}
        self.__scan_queue.put(("set_ad_struct", self.__ad_struct))
        self.__com_queue.put(("set_queue_dict", self.__queue_dict))
        self.__com_queue.put(("set_netserver", self.__ns))
        dc.release()
        lc_run_time = self.__glob_config["LOGCHECK_RUN_TIME"]
        try:
            self.__lc_hour, self.__lc_min = [int(x) for x in lc_run_time.split(":")]
        except:
            self.__lc_hour, self.__lc_min = (2, 0)
            self.log("Cannot parse logcheck_run_time '%s', using %02d:%02d: %s" % (lc_run_time,
                                                                                   self.__lc_hour,
                                                                                   self.__lc_min,
                                                                                   process_tools.get_except_info()),
                     logging_tools.LOG_LEVEL_ERROR)
        self.__last_update_wday, self.__logcheck_queue = (None, None)
        force_start_logcheck = self.__glob_config["INITIAL_LOGCHECK"]
        if not self.__loc_config["INIT_SCAN"]:
            force_start_logcheck = False
        if self.__loc_config["FORCE_INIT_PARSE"]:
            force_start_logcheck = True
        if force_start_logcheck:
            act_time = time.localtime()
            act_hour, act_min = (act_time[3], act_time[4])
            if abs(act_hour - self.__lc_hour) < 3:
                force_start_logcheck = False
                self.log("act_time %02d:%02d to close to logcheck_time %02d:%02d, no initial logcheck_run" % (act_hour,
                                                                                                              act_min,
                                                                                                              self.__lc_hour,
                                                                                                              self.__lc_min))
                self.__last_update_wday = act_time[6]
        self.log("last_update_weekday is %s, force_start_logcheck is %s" % (str(self.__last_update_wday) or "<not set>",
                                                                            force_start_logcheck and "enabled" or "disabled"))
        self.__force_start_logcheck = True
    def _new_pid(self, (thread_name, new_pid)):
        self.log("received new_pid message from thread %s" % (thread_name))
        process_tools.append_pids(self.__loc_config["PID_NAME"], new_pid)
        if self.__msi_block:
            self.__msi_block.add_actual_pid(new_pid)
            self.__msi_block.save_block()
    def _remove_pid(self, (thread_name, rem_pid)):
        self.log("received remove_pid message from thread %s" % (thread_name))
        process_tools.remove_pids(self.__loc_config["PID_NAME"], rem_pid)
        if self.__msi_block:
            self.__msi_block.remove_actual_pid(rem_pid)
            self.__msi_block.save_block()
    def _request_exit(self, name):
        self.log("thread %s requests exit" % (name))
        self.stop_thread(name)
        self.__logcheck_queue = None
    def _re_insert_config(self, dc):
        self.log("re-insert config")
        configfile.write_config(dc, "logcheck_server", self.__glob_config)
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        if self.__log_queue:
            if self.__log_cache:
                for c_what, c_lev in self.__log_cache:
                    self.__log_queue.put(("log", (self.name, "(delayed) %s" % (c_what), c_lev)))
                self.__log_cache = []
            self.__log_queue.put(("log", (self.name, what, lev)))
        else:
            self.__log_cache.append((what, lev))
    def _bind_state_call(self, **args):
        id_str = "%s_%s" % (args["type"], str(args["port"]))
        self.__bind_state_dict[id_str] = args["state"]
        num_ok = self.__bind_state_dict.values().count("ok")
        num_not_ok = len(self.__bind_state_dict.keys()) - num_ok
        self.log("bind_state_dict has now %s, %d ok%s" % (logging_tools.get_plural("key", len(self.__bind_state_dict.keys())),
                                                          num_ok,
                                                          num_not_ok and ", %d not ok" % (num_not_ok) or ""))
        if num_ok + num_not_ok == 2:
            if num_not_ok:
                self.log("Unable to bind to all sockets, exiting ...", logging_tools.LOG_LEVEL_CRITICAL)
                self._int_error("bind error")
            else:
                self.log("Successfully bound to all sockets, setting timeout to 60 seconds, testing connection")
                self.__ns.set_timeout(10)
            # clear bind_state dict
            for k in self.__bind_state_dict.keys():
                del self.__bind_state_dict[k]
    def _new_tcp_con(self, sock, src):
        self.log("got command from host %s, port %d" % (src[0], src[1]))
        return new_tcp_con(src, self.__com_queue, self.__log_queue)
    def _new_ud_recv(self, data, src):
        self.__log_queue.put(("udp_recv", data))
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
    def _init_msi_block(self):
        process_tools.save_pid(self.__loc_config["PID_NAME"])
        if self.__loc_config["DAEMON"]:
            self.log("Initialising meta-server-info block")
            msi_block = process_tools.meta_server_info("logcheck-server")
            msi_block.add_actual_pid()
            msi_block.set_start_command("/etc/init.d/logcheck-server start")
            msi_block.set_stop_command("/etc/init.d/logcheck-server force-stop")
            msi_block.set_kill_pids()
            msi_block.save_block()
        else:
            msi_block = None
        return msi_block
    def _hup_error(self, err_cause):
        self.log("Got SIGHUP, force-starting logcheck_thread", logging_tools.LOG_LEVEL_WARN)
        self.__force_start_logcheck = True
    def _int_error(self, err_cause):
        if self["exit_requested"]:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            self.__ns.set_timeout(0.2)
            self.log("exit requested", logging_tools.LOG_LEVEL_WARN)
            self._disable_syslog_config()
            self["exit_requested"] = True
    def thread_loop_post(self):
        process_tools.delete_pid(self.__loc_config["PID_NAME"])
        if self.__msi_block:
            self.__msi_block.remove_meta_block()
    def _prepare_directories(self):
        for d in [self.__glob_config["SYSLOG_DIR"]]:
            if not os.path.isdir(d):
                try:
                    os.mkdir(d)
                except:
                    pass
    def loop_function(self):
        self.__ns.step()
        if self.__loc_config["VERBOSE"]:
            tqi_dict = self.get_thread_queue_info()
            tq_names = sorted(tqi_dict.keys())
            self.log("tqi: %s" % (", ".join(["%s: %3d of %3d" % (t_name, t_used, t_total) for (t_name, t_used, t_total) in [(t_name,
                                                                                                                             tqi_dict[t_name][1],
                                                                                                                             tqi_dict[t_name][0]) for t_name in tq_names] if t_used]) or "clean"))
        self._check_syslog_connection()
        act_time = time.localtime()
        if (act_time[6] != self.__last_update_wday and act_time[3] == self.__lc_hour and act_time[4] in [self.__lc_min]) or self.__force_start_logcheck:
            if self.__force_start_logcheck:
                self.log("force-starting logcheck-thread")
                self.__force_start_logcheck = False
                restart_after_run = False
            else:
                restart_after_run = True
            self.__last_update_wday = act_time[6]
            if self.__logcheck_queue:
                self.log("logcheck_thread already running", logging_tools.LOG_LEVEL_WARN)
            else:
                self.log("starting locheck_thread")
                self.__logcheck_queue = self.add_thread(logcheck_thread(self.__glob_config, self.__loc_config, self.__db_con, self.__log_queue), start_thread=True).get_thread_queue()
                self.__logcheck_queue.put(("set_ad_struct", self.__ad_struct))
                self.__logcheck_queue.put(("set_queue_dict", self.__queue_dict))
                self.__logcheck_queue.put(("set_variable_dict", {"reparse"           : self.__loc_config["REPARSE"],
                                                                 "restart_after_run" : restart_after_run}))
    def _check_syslog_connection(self):
        self.__syslog_check_counter -= 1
        if self.__syslog_check_counter < 0:
            self.__run_idx = (self.__run_idx + 1) % 10
            # send the SYSLOG_THREAD_STR to the syslog-ng facility and directly to our syslog-socket to check the connectivity
            logging_tools.my_syslog("%s-%d" % (SYSLOG_THREAD_STR, self.__run_idx))
            log_template = net_logging_tools.log_command(self.__glob_config["INTERNAL_CHECK_NAME"])
            log_template.set_destination("uds_nb:%s" % (self.__glob_config["SYSLOG_SOCKET"]))
            errnum, errstr = log_template.log(SYSLOG_THREAD_STR)
            if errnum:
                self.log("Sending %s to %s gave (%d) %s" % (SYSLOG_THREAD_STR,
                                                            self.__glob_config["SYSLOG_SOCKET"],
                                                            errnum,
                                                            errstr),
                         logging_tools.LOG_LEVEL_ERROR)
            self.__syslog_check_counter = self.__syslog_check_num
            log_template.close()
    def _enable_syslog_config(self):
        LOCAL_FILTER_NAME = "f_messages"
        my_name = threading.currentThread().getName()
        slcn = "/etc/syslog-ng/syslog-ng.conf"
        if os.path.isfile(slcn):
            # start of shiny new modification code, right now only used to get the name of the /dev/log source
            dev_log_source_name = "src"
            try:
                act_conf = logging_tools.syslog_ng_config()
            except:
                self.log("Unable to parse config: %s, using '%s' as /dev/log-source" % (process_tools.get_except_info(),
                                                                                        dev_log_source_name),
                         logging_tools.LOG_LEVEL_ERROR)
            else:
                source_key = "/dev/log"
                source_dict = act_conf.get_dict_sort(act_conf.get_multi_object("source"))
                if source_dict.has_key(source_key):
                    dev_log_source_name = source_dict[source_key][0]
                    self.log("'%s'-key in config, using '%s' as /dev/log-source" % (source_key,
                                                                                    dev_log_source_name))
                else:
                    self.log("'%s'-key not in config, using '%s' as /dev/log-source" % (source_key,
                                                                                        dev_log_source_name),
                             logging_tools.LOG_LEVEL_WARN)
            self.log("Trying to rewrite syslog-ng.conf for logcheck-server ...")
            try:
                act_conf = [x.rstrip() for x in file(slcn, "r").readlines()]
                # remove net-related loglines (to ensure that throttle-messages are always sent to logcheck-server at first)
                orig_conf = []
                for line in act_conf:
                    if not re.match(".*destination\(hosts.*", line):
                        orig_conf.append(line)
                # check for logcheck-server-lines and/or dhcp-lines
                opt_list = ["throttle", "logcheck_server", "throttle_filter", "net_source", "host_dest", "host_log", "threadcheck_filter", "local_log"]
                opt_dict = dict([(x, 0) for x in opt_list])
                for line in orig_conf:
                    if re.match("^.*destination.logcheck.*$", line):
                        opt_dict["logcheck_server"] = True
                    if re.match("^.*filter f_throttle.*$", line):
                        opt_dict["throttle_filter"] = True
                    if re.match("^.*filter f_threadcheck.*$", line):
                        opt_dict["threadcheck_filter"] = True
                    if re.match("^.*source net.*$", line):
                        opt_dict["net_source"] = True
                    if re.match("^.*destination hosts.*$", line):
                        opt_dict["host_dest"] = True
                    if re.match("^.*destination\(hosts.*$", line):
                        opt_dict["host_log"] = True
                    if re.match("^.*log.*source.*%s.*filter%s.*$" % (dev_log_source_name, LOCAL_FILTER_NAME), line):
                        opt_dict["local_log"] = True
                self.log("after parsing: %s" % (", ".join(["%s: %d" % (x, opt_dict[x]) for x in opt_list])))
                logcheck_server_lines = []
                if not opt_dict["throttle_filter"]:
                    logcheck_server_lines.extend(["",
                                                  'filter f_throttle   { facility(kern) and match("CPU");};'])
                if not opt_dict["threadcheck_filter"]:
                    logcheck_server_lines.extend(["",
                                                  'filter f_threadcheck   { match("%s");};' % (SYSLOG_THREAD_STR)])
                if not opt_dict["net_source"]:
                    logcheck_server_lines.extend(["",
                                                  'source net { udp(ip("0.0.0.0") port(514));};'])
                if not opt_dict["host_dest"]:
                    logcheck_server_lines.extend(["",
                                                  'destination hosts_web { file("%s/$HOST/$YEAR/$MONTH/$DAY/log"       dir_perm(0755) perm(0644) create_dirs(yes) ); };' % (self.__glob_config["SYSLOG_DIR"]),
                                                  'destination hosts     { file("%s/$HOST/$YEAR/$MONTH/$DAY/$FACILITY" dir_perm(0755)            create_dirs(yes) ); };' % (self.__glob_config["SYSLOG_DIR"])])
                if not opt_dict["host_log"]:
                    logcheck_server_lines.extend(["",
                                                  'log { source(net); destination(hosts)    ; };',
                                                  'log { source(net); destination(hosts_web); };'])
                if not opt_dict["logcheck_server"]:
                    logcheck_server_lines.extend(["",
                                                  'destination logcheck { unix-dgram("%s") ;};' % (self.__glob_config["SYSLOG_SOCKET"]),
                                                  "",
                                                  'log {           source(%s); source(net); filter(f_threadcheck); destination(logcheck);};' % (dev_log_source_name),
                                                  'log {           source(%s); source(net); filter(f_throttle)   ; destination(logcheck);};' % (dev_log_source_name),
                                                  ""])
                if not opt_dict["local_log"]:
                    logcheck_server_lines.extend(["",
                                                  'log { source(%s); filter(%s); destination(hosts);     };' % (dev_log_source_name, LOCAL_FILTER_NAME),
                                                  'log { source(%s); filter(%s); destination(hosts_web); };' % (dev_log_source_name, LOCAL_FILTER_NAME),
                                                  ""])
                if logcheck_server_lines:
                    out_str = "\n".join([x.strip() for x in logcheck_server_lines])
                    while out_str.count("\n\n\n"):
                        out_str = out_str.replace("\n\n\n", "\n\n")
                    logcheck_server_lines = out_str.split("\n")
                    for ml in logcheck_server_lines:
                        self.log("adding line to %s : %s" % (slcn, ml))
                    out_str = "\n".join([x.strip() for x in orig_conf + logcheck_server_lines + [""]])
                    # eliminate double-rets
                    while out_str.count("\n\n\n"):
                        out_str = out_str.replace("\n\n\n", "\n\n")
                    file(slcn, "w").write(out_str)
                    self._restart_syslog_ng()
                else:
                    self.log("%s seems to be OK, leaving unchanged..." % (slcn))
                self.log("... done")
            except:
                self.log("Something went wrong while trying to modify '%s' : %s, help..." % (slcn, process_tools.get_except_info()),
                         logging_tools.LOG_LEVEL_ERROR)
        else:
            self.log("config file '%s' not present" % (slcn),
                     logging_tools.LOG_LEVEL_ERROR)
    def get_syslog_rc_script(self):
        for scr_name in ["/etc/init.d/syslog", "/etc/init.d/syslog-ng"]:
            if os.path.isfile(scr_name):
                break
        return scr_name
    def _restart_syslog_ng(self):
        old_pids = [key for key, value in process_tools.get_proc_list().iteritems() if value["name"] == "syslog-ng"]
        stat, out = commands.getstatusoutput("%s stop" % (self.get_syslog_rc_script()))
        self.log("stopping syslog-ng gave (%d) %s" % (stat, out))
        new_pids = [key for key, value in process_tools.get_proc_list().iteritems() if value["name"] == "syslog-ng"]
        if old_pids == new_pids:
            self.log("cannot stop syslog-ng, killing via 9", logging_tools.LOG_LEVEL_ERROR)
            for old_pid in old_pids:
                os.kill(old_pid, 9)
        rv, log_parts = process_tools.submit_at_command("%s start" % (self.get_syslog_rc_script()), 0)
        for lp in log_parts:
            self.log(" - %s" % (lp))
    def _disable_syslog_config(self):
        self.log("Trying to rewrite syslog-ng.conf for normal operation ...")
        slcn = "/etc/syslog-ng/syslog-ng.conf"
        try:
            orig_conf = [x.rstrip() for x in file(slcn, "r").readlines()]
            new_conf = []
            del_lines = []
            for line in orig_conf:
                if re.match("^.*destination.logcheck.*$", line):
                    del_lines.append(line)
                else:
                    new_conf.append(line)
            if del_lines:
                self.log("Found %s:" % (logging_tools.get_plural("logcheck-server-related line", len(del_lines))))
                for dl in del_lines:
                    self.log("  removing : %s" % (dl))
                # remove double empty-lines
                new_conf_2, last_line = ([], None)
                for line in new_conf:
                    if line == last_line and last_line == "":
                        pass
                    else:
                        new_conf_2.append(line)
                    last_line = line
                file(slcn, "w").write("\n".join(new_conf_2))
                self._restart_syslog_ng()
            else:
                self.log("Found no logcheck-server-related lines, leaving %s untouched" % (slcn),
                         logging_tools.LOG_LEVELERROR)
            self.log("... done")
        except:
            self.log("Something went wrong while trying to modify '%s', help..." % (slcn),
                     logging_tools.LOG_LEVEL_ERROR)

##         threading.Thread(name="socket_request", target=socket_server_thread_code, args = [main_queue, log_queue, sreq_queue, sreq_queue, nserver, msi_block]).start()

def main():
    long_host_name = socket.getfqdn(socket.gethostname())
    short_host_name = long_host_name.split(".")[0]
    try:
        opts, args = getopt.getopt(sys.argv[1:], "dvCu:g:fkh", ["version", "help", "reparse", "noscan", "rescan", "initparse"])
    except:
        print "Error parsing commandline %s" % (" ".join(sys.argv[:]))
        sys.exit(1)
    try:
        from logcheck_server_version import VERSION_STRING
    except ImportError:
        VERSION_STRING = "?.?"
    loc_config = configfile.configuration("local_config", {"PID_NAME"               : configfile.str_c_var("logcheck-server/logcheck-server"),
                                                           "DAEMON"                 : configfile.bool_c_var(True),
                                                           "SERVER_FULL_NAME"       : configfile.str_c_var(long_host_name),
                                                           "SERVER_SHORT_NAME"      : configfile.str_c_var(short_host_name),
                                                           "VERBOSE"                : configfile.int_c_var(0),
                                                           "CHECK"                  : configfile.bool_c_var(False),
                                                           "KILL_RUNNING"           : configfile.bool_c_var(True),
                                                           "REPARSE"                : configfile.bool_c_var(False),
                                                           "INIT_SCAN"              : configfile.bool_c_var(True),
                                                           "RESCAN"                 : configfile.bool_c_var(False),
                                                           "FORCE_INIT_PARSE"       : configfile.bool_c_var(False),
                                                           "USER"                   : configfile.str_c_var("root"),
                                                           "GROUP"                  : configfile.str_c_var("root"),
                                                           "LOGCHECK_SERVER_IDX"    : configfile.int_c_var(0),
                                                           "LOG_SOURCES"            : configfile.dict_c_var({}),
                                                           "LOG_STATUS"             : configfile.dict_c_var({}),
                                                           "LOG_SOURCE_IDX"         : configfile.int_c_var(0),
                                                           "VERSION_STRING"         : configfile.str_c_var(VERSION_STRING)})
    fixit = False
    pname = os.path.basename(sys.argv[0])
    for opt, arg in opts:
        if opt in ["-h", "--help"]:
            print "Usage: %s [OPTIONS]" % (pname)
            print " where options is one or more of"
            print "  -h,--help           this help"
            print "  --version           version info"
            print "  -d                  no daemonizing"
            print "  -f                  fix directory permissions"
            print "  -C                  check if i am a logcheck-server"
            print "  -u [USER]           set user to USER"
            print "  -g [GROUP]          set group to GROUP"
            print "  -k                  kill running instances of logcheck-server"
            print "  --reparse           reparse all logs (can be very time-consuming, use with care)"
            print "  --initparse         force initial logscan (e.g. concentration call), overriding config"
            print "  --noscan            disable initial logscan (e.g. concentration call)"
            print "  --rescan            force scanning of all available logs (not from last savepoint)"
            sys.exit(1)
        if opt == "--version":
            print "logcheck-server, Version %s" % (loc_config["VERSION_STRING"])
            sys.exit(0)
        if opt == "-d":
            loc_config["DAEMON"] = False
        if opt == "-v":
            loc_config["VERBOSE"] += 1
        if opt == "-C":
            loc_config["CHECK"] = True
        if opt == "-f":
            fixit = True
        if opt == "-u":
            loc_config["USER"] = arg
        if opt == "-g":
            loc_config["GROUP"] = arg
        if opt == "-k":
            loc_config["KILL_RUNNING"] = False
        if opt == "--reparse":
            loc_config["REPARSE"] = True
        if opt == "--noscan":
            loc_config["INIT_SCAN"] = False
        if opt == "--rescan":
            loc_config["RESCAN"] = True
        if opt == "--initparse":
            loc_config["FORCE_INIT_PARSE"] = True
    db_con = mysql_tools.dbcon_container(with_logging=not loc_config["DAEMON"])
    try:
        dc = db_con.get_connection(SQL_ACCESS)
    except MySQLdb.OperationalError:
        sys.stderr.write(" Cannot connect to SQL-Server ")
        sys.exit(1)
    sql_info = config_tools.server_check(dc=dc, server_type="logcheck_server")
    loc_config["LOGCHECK_SERVER_IDX"] = sql_info.server_device_idx
    if not loc_config["LOGCHECK_SERVER_IDX"]:
        sys.stderr.write(" Host %s is no logcheck-server " % (long_host_name))
        sys.exit(5)
    if loc_config["CHECK"]:
        sys.exit(0)
    if loc_config["KILL_RUNNING"]:
        kill_dict = process_tools.build_kill_dict(pname)
        for k, v in kill_dict.iteritems():
            log_str = "Trying to kill pid %d (%s) with signal 9 ..." % (k, v)
            try:
                os.kill(k, 9)
            except:
                log_str = "%s error (%s)" % (log_str, process_tools.get_except_info())
            else:
                log_str = "%s ok" % (log_str)
            logging_tools.my_syslog(log_str)
    g_config = configfile.read_global_config(dc, "logcheck_server", {"LOG_DIR"                : configfile.str_c_var("/var/log/cluster/logcheck-server"),
                                                                     "SYSLOG_DIR"             : configfile.str_c_var("/var/log/hosts"),
                                                                     "COMPORT"                : configfile.int_c_var(8014),
                                                                     "KEEP_LOGS_UNCOMPRESSED" : configfile.int_c_var(2),
                                                                     "KEEP_LOGS_TOTAL"        : configfile.int_c_var(30),
                                                                     "INITIAL_LOGCHECK"       : configfile.int_c_var(0),
                                                                     "LOGSCAN_TIME"           : configfile.int_c_var(60, info="time in minutes between two logscan iterations"),
                                                                     "DB_RESYNC_TIME"         : configfile.int_c_var(60),
                                                                     "SYSLOG_SOCKET_DIR"      : configfile.str_c_var("/var/lib/logcheck-server"),
                                                                     "SYSLOG_SOCKET_NAME"     : configfile.str_c_var("syslog"),
                                                                     "SYSLOG_OK_ITER"         : configfile.int_c_var(5),
                                                                     "SYSLOG_CHECK_OK"        : configfile.int_c_var(10),
                                                                     "SYSLOG_CHECK_ERROR"     : configfile.int_c_var(1),
                                                                     "MAX_PARSE_FILE_SIZE"    : configfile.int_c_var(200 * 1024 * 1024),
                                                                     "LOGCHECK_RUN_TIME"      : configfile.str_c_var("02:00"),
                                                                     "INTERNAL_CHECK_NAME"    : configfile.str_c_var("logcheck_server_check"),
                                                                     "LOGCHECK_SRC_IGNORE"    : configfile.array_c_var(["postfix",
                                                                                                                        "ypbind",
                                                                                                                        "syslogd",
                                                                                                                        "syslog-ng",
                                                                                                                        "sshd",
                                                                                                                        "in.rshd",
                                                                                                                        "slapd",
                                                                                                                        "rshd",
                                                                                                                        "pam_rhosts_auth",
                                                                                                                        "automount",
                                                                                                                        "python",
                                                                                                                        "python2.4",
                                                                                                                        "python-init",
                                                                                                                        "ntpd",
                                                                                                                        "mpd",
                                                                                                                        "ntpdate",
                                                                                                                        "modprobe",
                                                                                                                        "hoststatus",
                                                                                                                        "tell_mother",
                                                                                                                        "logger",
                                                                                                                        "crontab",
                                                                                                                        "FILE_REFERENCE"]),
                                                                     "KERNEL_IGNORE_PREFIXES" : configfile.array_c_var(["nat_", "ftl_"])})
    g_config.add_config_dict({"SYSLOG_SOCKET" : configfile.str_c_var("%s/%s" % (g_config["SYSLOG_SOCKET_DIR"], g_config["SYSLOG_SOCKET_NAME"]))})
    if fixit:
        process_tools.fix_directories(loc_config["USER"], loc_config["GROUP"], [g_config["LOG_DIR"], g_config["SYSLOG_SOCKET_DIR"], "/var/run/logcheck-server"])
    ret_state = 256
    loc_config["LOG_SOURCE_IDX"] = process_tools.create_log_source_entry(dc, loc_config["LOGCHECK_SERVER_IDX"], "logcheck", "Logcheck Server")
    if not loc_config["LOG_SOURCE_IDX"]:
        print "Too many log_sources with my id found, exiting..."
        dc.release()
    else:
        loc_config["LOG_SOURCES"] = process_tools.get_all_log_sources(dc)
        loc_config["LOG_STATUS"]  = process_tools.get_all_log_status(dc)
        process_tools.renice()
        if loc_config["DAEMON"]:
            # become daemon and wait 2 seconds
            process_tools.become_daemon(wait = 2)
            process_tools.set_handles({"out" : (1, "logcheck"),
                                       "err" : (0, "/var/lib/logging-server/py_err")})
        else:
            print "Debugging logcheck"
        dc.release()
        my_tp = server_thread_pool(db_con, g_config, loc_config)
        my_tp.thread_loop()
        #ret_state = server_code(daemon, reparse, init_scan, rescan, force_init_parse, db_con)
    db_con.close()
    del db_con
    sys.exit(ret_state)

if __name__ == "__main__":
    main()
