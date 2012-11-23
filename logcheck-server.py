#!/usr/bin/python-init -Otu
# -*- coding: utf-8 -*-
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008,2011,2012 Andreas Lang-Nevyjel
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
""" logcheck-server (to be run on a syslog_server) """

import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

import time
import datetime
import re
import shutil
import configfile
import commands
import stat
import process_tools
import logging_tools
import threading_tools
import marshal
import pprint
import server_command
import gzip
import cluster_location
import bz2
import struct
import config_tools
from django.db.models import Q

try:
    from logcheck_server_version import VERSION_STRING
except ImportError:
    VERSION_STRING = "?.?"

SYSLOG_THREAD_STR = "syslog-thread-test"

SERVER_PORT = 8014
SCAN_TEXT_PREFIX = ".scan"

LOGREADER_DATE_VARNAME   = "logsrv_logreader_date"
LOGREADER_OFFSET_VARNAME = "logsrv_logreader_offset"

SQL_ACCESS = "cluster_full_access"

# ---------------------------------------------------------------------
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
        self.__ad_struct.release_read_lock()
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

class server_process(threading_tools.process_pool):
    def __init__(self, options):
        self.__log_cache, self.__log_template = ([], None)
        threading_tools.process_pool.__init__(self, "main", zmq=True, zmq_debug=global_config["ZMQ_DEBUG"])
        self.__pid_name = global_config["PID_NAME"]
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context)
        self.__msi_block = self._init_msi_block()
        self._re_insert_config()
        self.register_exception("int_error", self._int_error)
        self.register_exception("term_error", self._int_error)
        # log config
        self._log_config()
        # prepare directories
        self._prepare_directories()
        # enable syslog_config
        self._enable_syslog_config()
        self.__options = options
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        if self.__log_template:
            while self.__log_cache:
                self.__log_template.log(*self.__log_cache.pop(0))
            self.__log_template.log(lev, what)
        else:
            self.__log_cache.append((lev, what))
    def _int_error(self, err_cause):
        if self["exit_requested"]:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            self["exit_requested"] = True
    def _prepare_directories(self):
        for cur_dir in [global_config["SYSLOG_DIR"]]:
            if not os.path.isdir(cur_dir):
                try:
                    os.mkdir(cur_dir)
                except:
                    self.log("error creating %s: %s" % (
                        cur_dir,
                        process_tools.get_except_info()),
                             logging_tools.LOG_LEVEL_ERROR)
    def _log_config(self):
        self.log("Config info:")
        for line, log_level in global_config.get_log(clear=True):
            self.log(" - clf: [%d] %s" % (log_level, line))
        conf_info = global_config.get_config_info()
        self.log("Found %d valid config-lines:" % (len(conf_info)))
        for conf in conf_info:
            self.log("Config : %s" % (conf))
    def _re_insert_config(self):
        self.log("re-insert config")
        cluster_location.write_config("syslog_server", global_config)
    def process_start(self, src_process, src_pid):
        mult = 2
        process_tools.append_pids(self.__pid_name, src_pid, mult=mult)
        if self.__msi_block:
            self.__msi_block.add_actual_pid(src_pid, mult=mult)
            self.__msi_block.save_block()
    def _init_msi_block(self):
        process_tools.save_pid(self.__pid_name, mult=3)
        process_tools.append_pids(self.__pid_name, pid=configfile.get_manager_pid(), mult=2)
        self.log("Initialising meta-server-info block")
        msi_block = process_tools.meta_server_info(self.__pid_name)
        msi_block.add_actual_pid(mult=3)
        msi_block.add_actual_pid(act_pid=configfile.get_manager_pid(), mult=2)
        msi_block.start_command = "/etc/init.d/logcheck-server start"
        msi_block.stop_command = "/etc/init.d/logcheck-server force-stop"
        msi_block.kill_pids = True
        msi_block.save_block()
        return msi_block
    def loop_end(self):
        self._disable_syslog_config()
        process_tools.delete_pid(self.__pid_name)
        if self.__msi_block:
            self.__msi_block.remove_meta_block()
    def loop_post(self):
        self.__log_template.close()
    # syslog stuff
    def _enable_syslog_config(self):
        syslog_exe_dict = dict([(key, value) for key, value in process_tools.get_proc_list().iteritems() if value and value.get("exe", "") and value["exe"].count("syslog")])
        syslog_type = None
        for key, value in syslog_exe_dict.iteritems():
            self.log("syslog process found: %6d = %s" % (key, value["exe"]))
            if value["exe"].endswith("rsyslogd"):
                syslog_type = "rsyslogd"
        self.log("syslog type found: %s" % (syslog_type or "none"))
        self.__syslog_type = syslog_type
        if self.__syslog_type == "rsyslogd":
            self._enable_rsyslog()
        elif self.__syslog_type == "syslog-ng":
            self._enable_syslog_ng()
    def _disable_syslog_config(self):
        if self.__syslog_type == "rsyslogd":
            self._disable_rsyslog()
        elif self.__syslog_type == "syslog-ng":
            self._disable_syslog_ng()
    def _enable_syslog_ng(self):
        self.log("not implemented", logging_tools.LOG_LEVEL_CRITICAL)
    def _disable_syslog_ng(self):
        self.log("not implemented", logging_tools.LOG_LEVEL_CRITICAL)
    def _enable_rsyslog(self):
        rsyslog_lines = [
            '# UDP Syslog Server:',
            '$ModLoad imudp.so         # provides UDP syslog reception',
            '$UDPServerRun 514         # start a UDP syslog server at standard port 514',
            '',
            '$template prog_log,"%s/%%HOSTNAME%%/%%$YEAR%%/%%$MONTH%%/%%$DAY%%/%%programname%%"' % (global_config["SYSLOG_DIR"]),
            '$template full_log,"%s/%%HOSTNAME%%/%%$YEAR%%/%%$MONTH%%/%%$DAY%%/log"' % (global_config["SYSLOG_DIR"]),
            '',
            '$DirCreateMode 0755',
            '',
            '$FileCreateMode 0644',
            '*.* ?prog_log',
            '',
            '$FileCreateMode 0644',
            '*.* ?full_log',
        ]
        slcn = "/etc/rsyslog.d/logcheck_server.conf"
        file(slcn, "w").write("\n".join(rsyslog_lines))
        self._restart_syslog()
    def _disable_rsyslog(self):
        slcn = "/etc/rsyslog.d/logcheck_server.conf"
        if os.path.isfile(slcn):
            os.unlink(slcn)
        self._restart_syslog()
    def _restart_syslog(self):
        for syslog_rc in ["/etc/init.d/syslog", "/etc/init.d/syslog-ng"]:
            if os.path.isfile(syslog_rc):
                break
        stat, out_f = process_tools.submit_at_command("%s restart" % (syslog_rc), 0)
        self.log("restarting %s gave %d:" % (syslog_rc, stat))
        for line in out_f:
            self.log(line)
        

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
        self.__com_queue  = self.add_thread(com_thread(self.__glob_config, self.__loc_config, self.__db_con, self.__log_queue), start_thread=True).get_thread_queue()
        self.__queue_dict = {"logging_queue" : self.__log_queue,
                             "com_queue"     : self.__com_queue}
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
    #def _enable_syslog_config(self):
        #LOCAL_FILTER_NAME = "f_messages"
        #my_name = threading.currentThread().getName()
        #slcn = "/etc/syslog-ng/syslog-ng.conf"
        #if os.path.isfile(slcn):
            ## start of shiny new modification code, right now only used to get the name of the /dev/log source
            #dev_log_source_name = "src"
            #try:
                #act_conf = logging_tools.syslog_ng_config()
            #except:
                #self.log("Unable to parse config: %s, using '%s' as /dev/log-source" % (process_tools.get_except_info(),
                                                                                        #dev_log_source_name),
                         #logging_tools.LOG_LEVEL_ERROR)
            #else:
                #source_key = "/dev/log"
                #source_dict = act_conf.get_dict_sort(act_conf.get_multi_object("source"))
                #if source_dict.has_key(source_key):
                    #dev_log_source_name = source_dict[source_key][0]
                    #self.log("'%s'-key in config, using '%s' as /dev/log-source" % (source_key,
                                                                                    #dev_log_source_name))
                #else:
                    #self.log("'%s'-key not in config, using '%s' as /dev/log-source" % (source_key,
                                                                                        #dev_log_source_name),
                             #logging_tools.LOG_LEVEL_WARN)
            #self.log("Trying to rewrite syslog-ng.conf for logcheck-server ...")
            #try:
                #act_conf = [x.rstrip() for x in file(slcn, "r").readlines()]
                ## remove net-related loglines (to ensure that throttle-messages are always sent to logcheck-server at first)
                #orig_conf = []
                #for line in act_conf:
                    #if not re.match(".*destination\(hosts.*", line):
                        #orig_conf.append(line)
                ## check for logcheck-server-lines and/or dhcp-lines
                #opt_list = ["throttle", "logcheck_server", "throttle_filter", "net_source", "host_dest", "host_log", "threadcheck_filter", "local_log"]
                #opt_dict = dict([(x, 0) for x in opt_list])
                #for line in orig_conf:
                    #if re.match("^.*destination.logcheck.*$", line):
                        #opt_dict["logcheck_server"] = True
                    #if re.match("^.*filter f_throttle.*$", line):
                        #opt_dict["throttle_filter"] = True
                    #if re.match("^.*filter f_threadcheck.*$", line):
                        #opt_dict["threadcheck_filter"] = True
                    #if re.match("^.*source net.*$", line):
                        #opt_dict["net_source"] = True
                    #if re.match("^.*destination hosts.*$", line):
                        #opt_dict["host_dest"] = True
                    #if re.match("^.*destination\(hosts.*$", line):
                        #opt_dict["host_log"] = True
                    #if re.match("^.*log.*source.*%s.*filter%s.*$" % (dev_log_source_name, LOCAL_FILTER_NAME), line):
                        #opt_dict["local_log"] = True
                #self.log("after parsing: %s" % (", ".join(["%s: %d" % (x, opt_dict[x]) for x in opt_list])))
                #logcheck_server_lines = []
                #if not opt_dict["throttle_filter"]:
                    #logcheck_server_lines.extend(["",
                                                  #'filter f_throttle   { facility(kern) and message("CPU");};'])
                #if not opt_dict["threadcheck_filter"]:
                    #logcheck_server_lines.extend(["",
                                                  #'filter f_threadcheck   { message("%s");};' % (SYSLOG_THREAD_STR)])
                #if not opt_dict["net_source"]:
                    #logcheck_server_lines.extend(["",
                                                  #'source net { udp(ip("0.0.0.0") port(514));};'])
                #if not opt_dict["host_dest"]:
                    #logcheck_server_lines.extend(["",
                                                  #'destination hosts_web { file("%s/$HOST/$YEAR/$MONTH/$DAY/log"       dir_perm(0755) perm(0644) create_dirs(yes) ); };' % (self.__glob_config["SYSLOG_DIR"]),
                                                  #'destination hosts     { file("%s/$HOST/$YEAR/$MONTH/$DAY/$FACILITY" dir_perm(0755)            create_dirs(yes) ); };' % (self.__glob_config["SYSLOG_DIR"])])
                #if not opt_dict["host_log"]:
                    #logcheck_server_lines.extend(["",
                                                  #'log { source(net); destination(hosts)    ; };',
                                                  #'log { source(net); destination(hosts_web); };'])
                #if not opt_dict["logcheck_server"]:
                    #logcheck_server_lines.extend(["",
                                                  #'destination logcheck { unix-dgram("%s") ;};' % (self.__glob_config["SYSLOG_SOCKET"]),
                                                  #"",
                                                  #'log {           source(%s); source(net); filter(f_threadcheck); destination(logcheck);};' % (dev_log_source_name),
                                                  #'log {           source(%s); source(net); filter(f_throttle)   ; destination(logcheck);};' % (dev_log_source_name),
                                                  #""])
                #if not opt_dict["local_log"]:
                    #logcheck_server_lines.extend(["",
                                                  #'log { source(%s); filter(%s); destination(hosts);     };' % (dev_log_source_name, LOCAL_FILTER_NAME),
                                                  #'log { source(%s); filter(%s); destination(hosts_web); };' % (dev_log_source_name, LOCAL_FILTER_NAME),
                                                  #""])
                #if logcheck_server_lines:
                    #out_str = "\n".join([x.strip() for x in logcheck_server_lines])
                    #while out_str.count("\n\n\n"):
                        #out_str = out_str.replace("\n\n\n", "\n\n")
                    #logcheck_server_lines = out_str.split("\n")
                    #for ml in logcheck_server_lines:
                        #self.log("adding line to %s : %s" % (slcn, ml))
                    #out_str = "\n".join([x.strip() for x in orig_conf + logcheck_server_lines + [""]])
                    ## eliminate double-rets
                    #while out_str.count("\n\n\n"):
                        #out_str = out_str.replace("\n\n\n", "\n\n")
                    #file(slcn, "w").write(out_str)
                    #self._restart_syslog_ng()
                #else:
                    #self.log("%s seems to be OK, leaving unchanged..." % (slcn))
                #self.log("... done")
            #except:
                #self.log("Something went wrong while trying to modify '%s' : %s, help..." % (slcn, process_tools.get_except_info()),
                         #logging_tools.LOG_LEVEL_ERROR)
        #else:
            #self.log("config file '%s' not present" % (slcn),
                     #logging_tools.LOG_LEVEL_ERROR)
    #def get_syslog_rc_script(self):
        #for scr_name in ["/etc/init.d/syslog", "/etc/init.d/syslog-ng"]:
            #if os.path.isfile(scr_name):
                #break
        #return scr_name
    #def _restart_syslog_ng(self):
        #old_pids = [key for key, value in process_tools.get_proc_list().iteritems() if value["name"] == "syslog-ng"]
        #stat, out = commands.getstatusoutput("%s stop" % (self.get_syslog_rc_script()))
        #self.log("stopping syslog-ng gave (%d) %s" % (stat, out))
        #new_pids = [key for key, value in process_tools.get_proc_list().iteritems() if value["name"] == "syslog-ng"]
        #if old_pids == new_pids:
            #self.log("cannot stop syslog-ng, killing via 9", logging_tools.LOG_LEVEL_ERROR)
            #for old_pid in old_pids:
                #os.kill(old_pid, 9)
        #rv, log_parts = process_tools.submit_at_command("%s start" % (self.get_syslog_rc_script()), 0)
        #for lp in log_parts:
            #self.log(" - %s" % (lp))
    #def _disable_syslog_config(self):
        #self.log("Trying to rewrite syslog-ng.conf for normal operation ...")
        #slcn = "/etc/syslog-ng/syslog-ng.conf"
        #try:
            #orig_conf = [x.rstrip() for x in file(slcn, "r").readlines()]
            #new_conf = []
            #del_lines = []
            #for line in orig_conf:
                #if re.match("^.*destination.logcheck.*$", line):
                    #del_lines.append(line)
                #else:
                    #new_conf.append(line)
            #if del_lines:
                #self.log("Found %s:" % (logging_tools.get_plural("logcheck-server-related line", len(del_lines))))
                #for dl in del_lines:
                    #self.log("  removing : %s" % (dl))
                ## remove double empty-lines
                #new_conf_2, last_line = ([], None)
                #for line in new_conf:
                    #if line == last_line and last_line == "":
                        #pass
                    #else:
                        #new_conf_2.append(line)
                    #last_line = line
                #file(slcn, "w").write("\n".join(new_conf_2))
                #self._restart_syslog_ng()
            #else:
                #self.log("Found no logcheck-server-related lines, leaving %s untouched" % (slcn),
                         #logging_tools.LOG_LEVELERROR)
            #self.log("... done")
        #except:
            #self.log("Something went wrong while trying to modify '%s', help..." % (slcn),
                     #logging_tools.LOG_LEVEL_ERROR)

global_config = configfile.get_global_config(process_tools.get_programm_name())

def main():
    long_host_name, mach_name = process_tools.get_fqdn()
    prog_name = global_config.name()
    global_config.add_config_entries([
        ("DEBUG"               , configfile.bool_c_var(False, help_string="enable debug mode [%(default)s]", short_options="d", only_commandline=True)),
        ("ZMQ_DEBUG"           , configfile.bool_c_var(False, help_string="enable 0MQ debugging [%(default)s]", only_commandline=True)),
        ("PID_NAME"            , configfile.str_c_var(os.path.join(prog_name, prog_name))),
        ("KILL_RUNNING"        , configfile.bool_c_var(True, help_string="kill running instances [%(default)s]")),
        ("FORCE"               , configfile.bool_c_var(False, help_string="force running [%(default)s]", action="store_true", only_commandline=True)),
        ("CHECK"               , configfile.bool_c_var(False, help_string="only check for server status", action="store_true", only_commandline=True, short_options="C")),
        ("LOG_DESTINATION"     , configfile.str_c_var("uds:/var/lib/logging-server/py_log_zmq")),
        ("USER"                , configfile.str_c_var("idlog", help_string="user to run as [%(default)s]")),
        ("GROUP"               , configfile.str_c_var("idg", help_string="group to run as [%(default)s]")),
        ("LOG_NAME"            , configfile.str_c_var(prog_name)),
        ("VERBOSE"             , configfile.int_c_var(0, help_string="set verbose level [%(default)d]", short_options="v", only_commandline=True)),
    ])
    global_config.parse_file()
    options = global_config.handle_commandline(description="%s, version is %s" % (prog_name,
                                                                                  VERSION_STRING),
                                               add_writeback_option=True,
                                               positional_arguments=False)
    global_config.write_file()
    sql_info = config_tools.server_check(server_type="syslog_server")
    if not sql_info.effective_device:
        print "not a syslog_server"
        sys.exit(5)
    if global_config["CHECK"]:
        sys.exit(0)
    ret_state = 256
    if sql_info.device:
        global_config.add_config_entries([("SERVER_IDX", configfile.int_c_var(sql_info.effective_device.pk, database=False))])
    else:
        global_config.add_config_entries([("SERVER_IDX", configfile.int_c_var(0, database=False))])
    if not global_config["SERVER_IDX"] and not global_config["FORCE"]:
        sys.stderr.write(" %s is no syslog-server, exiting..." % (long_host_name))
        sys.exit(5)
    cluster_location.read_config_from_db(global_config, "syslog_server", [
        ("SYSLOG_DIR"             , configfile.str_c_var("/var/log/hosts")),
        ("COMPORT"                , configfile.int_c_var(SERVER_PORT)),
        ("KEEP_LOGS_UNCOMPRESSED" , configfile.int_c_var(2)),
        ("KEEP_LOGS_TOTAL"        , configfile.int_c_var(30)),
        ("INITIAL_LOGCHECK"       , configfile.bool_c_var(False)),
        ("LOGSCAN_TIME"           , configfile.int_c_var(60, info="time in minutes between two logscan iterations"))
    ])
    #if fixit:
        #process_tools.fix_directories(loc_config["USER"], loc_config["GROUP"], [g_config["LOG_DIR"], g_config["SYSLOG_SOCKET_DIR"], "/var/run/logcheck-server"])
    process_tools.renice()
    # need root rights to change syslog and log rotation
    #global_config.set_uid_gid(global_config["USER"], global_config["GROUP"])
    #process_tools.change_user_group(global_config["USER"], global_config["GROUP"])
    if not global_config["DEBUG"]:
        # become daemon and wait 2 seconds
        process_tools.become_daemon(wait = 2)
        process_tools.set_handles({"out" : (1, "logcheck"),
                                   "err" : (0, "/var/lib/logging-server/py_err")})
    else:
        print "Debugging logcheck_server"
    ret_state = server_process(options).loop()
    sys.exit(ret_state)

if __name__ == "__main__":
    main()
