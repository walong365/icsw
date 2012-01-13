#!/usr/bin/python-init -Ot
#
# Copyright (C) 2007,2008 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file belongs to the rrd-server package
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
""" rrd-server for storing collected data to rrd-databases """

import sys
import pkg_resources
pkg_resources.require("MySQL_python")
import MySQLdb
import threading
import time
import os
import getopt
import socket
import rrdtool
import configfile
import process_tools
import logging_tools
import server_command
import net_tools
import mysql_tools
import pprint
import threading_tools
import uuid_tools
import cPickle
import marshal
import shutil
import rrd_tools

BASE_NAME = "rrd-server"
SQL_ACCESS = "cluster_full_access"
PROG_NAME = "rrd-server-writer"
CAP_NAME = "rrd_server_writer"

# --------- connection objects ------------------------------------
class new_tcp_con(net_tools.buffer_object):
    # connection object for rrd-server
    def __init__(self, con_type, con_class, data, src, recv_queue, log_queue):
        self.__con_type = con_type
        self.__con_class = con_class
        #print "Init %s (%s) from %s" % (con_type, con_class, str(src))
        self.__src_host, self.__src_port = src
        self.__recv_queue = recv_queue
        self.__log_queue = log_queue
        net_tools.buffer_object.__init__(self)
        self.__init_time = time.time()
        self.__in_buffer = ""
        if data:
            self.__decoded = data
            if self.__con_type == "com":
                # should never occur
                self.__recv_queue.put(("com_con", self))
            else:
                self.__recv_queue.put(("node_con", self))
    def __del__(self):
        pass
    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        self.__log_queue.put(("log", (threading.currentThread().getName(), what, level)))
    def get_con_class(self):
        return self.__con_class
    def get_src_host(self):
        return self.__src_host
    def get_src_port(self):
        return self.__src_port
    def add_to_in_buffer(self, what):
        self.__in_buffer += what
        p1_ok, what = net_tools.check_for_proto_1_header(self.__in_buffer)
        if p1_ok:
            self.__decoded = what
            if self.__con_type == "com":
                self.__recv_queue.put(("com_con", self))
            else:
                self.__recv_queue.put(("node_con", self))
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
            if self.__con_type == "com":
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
        
# --------- connection objects ------------------------------------

class all_devices(object):
    def __init__(self, log_queue, glob_config, loc_config, db_con):
        self.__lut = {}
        self.__lock = threading.Lock()
        self.__log_queue = log_queue
        self.__glob_config, self.__loc_config = (glob_config, loc_config)
        self.__db_con = db_con
        self.__device_names = []
        self.log("all_devices struct init")
    def get_log_queue(self):
        return self.__log_queue
    def get_glob_config(self):
        return self.__glob_config
    def get_db_con(self):
        return self.__db_con
    def get_loc_config(self):
        return self.__loc_config
    def db_sync(self, dc, dev_idx, act_rrd_classes):
        found = False
        self._lock(self.__loc_config["VERBOSE"] > 0 or not self.__loc_config["DAEMON"])
        self.log("searching for device with idx %d in DB" % (dev_idx))
        dc.execute("SELECT d.name FROM device d where d.device_idx=%d" % (dev_idx))
        if dc.rowcount:
            dev_name = dc.fetchone()["name"]
            self[dev_name] = None
            new_dev_struct = rrd_device(dev_name, dev_idx, self)
            new_dev_struct.load_rrd_info(dc)
            new_dev_struct.create_rrd_database(dc, act_rrd_classes)
            self[dev_name] = new_dev_struct
            self[dev_idx] = new_dev_struct
            found = True
        self._release(self.__loc_config["VERBOSE"] > 0 or not self.__loc_config["DAEMON"])
        return found
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__log_queue.put(("log", (threading.currentThread().getName(), what, lev)))
    def _lock(self, verb):
        if verb:
            self.log("Acquiring lock for ad_struct")
        self.__lock.acquire()
    def _release(self, verb):
        if verb:
            self.log("Releasing lock for ad_struct")
        self.__lock.release()
    def keys(self, only_names=False):
        if only_names:
            return self.__device_names
        else:
            return self.__lut.keys()
    def has_key(self, key):
        return self.__lut.has_key(key)
    def __setitem__(self, key, val):
        if type(key) == type("") and key not in self.__device_names:
            self.__device_names.append(key)
        self.__lut[key] = val
    def __getitem__(self, key):
        return self.__lut[key]
    def __delitem__(self, key):
        if key in self.__device_names:
            self.__device_names.remove(key)
        del self.__lut[key]

class rrd_data(object):
    def __init__(self, device, descr):
        self.__device = device
        self.__descr = descr
        self.__descr_p = descr.split(".")
        self.__descr_p_safe = [x.replace("/", "") for x in self.__descr_p]
        self.__local_name = "%s/%s.rrd" % ("/".join(self.__descr_p_safe[:-1]),
                                           self.__descr_p_safe[-1])
        self.__last_update = time.time() - 10
        self.rrd_dir = None
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__device.log("%s: %s" % (self.__descr, what), lev)
    def create_rrd_database(self, rrd_dir, class_dict, force=False, check_for_changes=True):
        # fix, sometimes full_path expands to a unicode string...
        self.full_path = str("%s/%s" % (rrd_dir, self.__local_name))
        local_dir = os.path.dirname(self.full_path)
        if not os.path.isdir(local_dir):
            if os.path.isfile(local_dir):
                self.log("removing old file %s" % (local_dir), logging_tools.LOG_LEVEL_WARN)
                try:
                    os.unlink(local_dir)
                except:
                    self.log("error removing file %s: %s" % (local_dir, process_tools.get_except_info()),
                             logging_tools.LOG_LEVEL_CRITICAL)
            self.log("creating directory %s" % (local_dir))
            os.makedirs(local_dir)
        rebuild = force
        if os.path.isfile(self.full_path):
            if check_for_changes:
                rrd_info = rrd_tools.info(self.full_path)
                hb_value = rrd_info["ds"]["v0"]["minimal_heartbeat"]
                new_hb = class_dict["heartbeat"]
                if hb_value != new_hb:
                    self.log("heartbeat-value changed from %d to %d" % (hb_value,
                                                                        new_hb))
                    rrdtool.tune(*([self.full_path] + ["-h", "v0:%d" % (new_hb)]))
        else:
            self.log("rrd-file %s not found, creating" % (self.__local_name))
            rebuild = True
        if rebuild:
            start_time = time.time()
            self.log("Creating rrd-database (rrd_class %s)" % (class_dict["name"]))
            val_a = [self.full_path]
            val_a.append("-s %d" % (class_dict["step"]))
            val_a.append("DS:v0:GAUGE:%d:U:U" % (class_dict["heartbeat"]))
            for rra_idx, rra in class_dict["rras"].iteritems():
                val_a.append("RRA:%s:0.5:%d:%d" % (rra["cf"], rra["steps"], rra["rows"]))
            #print val_a
            try:
                c_ret = rrdtool.create(*val_a)
            except:
                self.log("rrd_create() throw an error (%s, %s): %s" % (logging_tools.get_plural("argument", len(val_a)),
                                                                       ", ".join(val_a),
                                                                       process_tools.get_except_info()),
                         logging_tools.LOG_LEVEL_ERROR)
            else:
                self.log("rrd_create() with %s returned %s" % (logging_tools.get_plural("tuple", len(val_a)), str(c_ret)))
            end_time = time.time()
            self.log("Took %s" % (logging_tools.get_diff_time_str(end_time - start_time)))
        return rebuild
    def store_values(self, in_list):
        success = False
        try:
            #if self.__descr.startswith("load.1"):
            #    print [self.__full_path] + in_list
            act_time = time.time()
            diff_time = abs(act_time - self.__last_update)
            if  diff_time < 2:
                self.log("last update only %s ago, waiting for 1 second" % (logging_tools.get_diff_time_str(diff_time)),
                         logging_tools.LOG_LEVEL_WARN)
                act_time = time.time()
            self.__last_update = act_time
            c_ret = rrdtool.update(*([self.full_path] + in_list))
        except:
            self.log("update raised exception: %s" % (process_tools.get_except_info()),
                     logging_tools.LOG_LEVEL_CRITICAL)
        else:
            success = True
            if c_ret is not None:
                self.log("update gave %s" % (c_ret))
        return success
        
def read_rrd_class_tree(dc):
    dc.execute("SELECT rc.*, ra.* FROM rrd_class rc LEFT JOIN rrd_rra ra ON ra.rrd_class=rc.rrd_class_idx")
    rrd_classes = {}
    for db_rec in dc.fetchall():
        if not rrd_classes.has_key(db_rec["rrd_class_idx"]):
            rrd_classes[db_rec["rrd_class_idx"]] = db_rec
            rrd_classes[db_rec["rrd_class_idx"]]["rras"] = {}
        if db_rec["rrd_rra_idx"]:
            rrd_classes[db_rec["rrd_class_idx"]]["rras"][db_rec["rrd_rra_idx"]] = db_rec
    return rrd_classes

class rrd_device(object):
    def __init__(self, name, dev_idx, ad_struct):
        self.name = name
        self.__ad_struct = ad_struct
        self.__defined_mibs, self.__mib_keys = ({}, [])
        # dictionary: key -> mib
        self.__mib_key_dict = {}
        self.mib_values = {}
        self.__log_queue = self.__ad_struct.get_log_queue()
        # device idx
        self.dev_idx = dev_idx
        # rrd root dir
        self.rrd_dir = ""
        # actual rrd-class
        self.act_rrd_class, self.act_rrd_class_idx = ({}, 0)
        self.init_mapping()
    def get_glob_config(self):
        return self.__ad_struct.get_glob_config()
    def get_loc_config(self):
        return self.__ad_struct.get_loc_config()
    def get_db_con(self):
        return self.__ad_struct.get_db_con()
    #def log(self, what, glob = 0):
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK, glob=False):
        self.__log_queue.put(("mach_log", (threading.currentThread().getName(), what, lev, self.name)))
        if glob:
            self.__log_queue.put(("log", (threading.currentThread().getName(), what, lev)))
    def init_mapping(self):
        # rrd data structs, key -> rrd_data type
        self.rrd_data = {}
    def get_rrd_set_index(self):
        return self.__rrd_set_index
    def load_rrd_info(self, dc, in_dict=None):
        # load rrd-data sets from database
        self.log("load_rrd_info() for device %s (index %d)" % (self.name, self.dev_idx))
        dc.execute("SELECT rs.rrd_set_idx FROM rrd_set rs WHERE rs.device=%d" % (self.dev_idx))
        if dc.rowcount:
            idx = dc.fetchone().values()[0]
            self.__rrd_set_index = idx
            self.log("found rrd_set with index %d" % (self.__rrd_set_index))
        else:
            idx = 0
            self.log("No rrd_set found for device")
    def _add_rrd_data(self, descr):
        new_rrd_data = rrd_data(self, descr)
        self.rrd_data[descr] = new_rrd_data
        new_rrd_data.create_rrd_database(self.rrd_dir, self.act_rrd_class, check_for_changes=True)
    def create_rrd_database(self, dc, act_rrd_classes, force=False):
        dc.execute("SELECT d.rrd_class FROM device d WHERE d.device_idx=%d" % (self.dev_idx))
        rrd_class = dc.fetchone()["rrd_class"]
        if rrd_class in act_rrd_classes.keys():
            self.log("actual rrd_class %d is valid (%s)" % (rrd_class,
                                                            act_rrd_classes[rrd_class]["name"]))
        else:
            if act_rrd_classes:
                rrd_class = act_rrd_classes.keys()[0]
                self.log("No rrd-class set, using %s as class (index %d)" % (act_rrd_classes[rrd_class]["name"],
                                                                             rrd_class))
                dc.execute("UPDATE device SET rrd_class=%d WHERE device_idx=%d" % (rrd_class, self.dev_idx))
            else:
                self.log("No rrd-classes defined, ERROR!!!", glob=True)
                rrd_class = 0
        if rrd_class:
            self.act_rrd_class = act_rrd_classes[rrd_class]
            self.act_rrd_class_idx = rrd_class
            tot_rows = sum([x["rows"] for x in self.act_rrd_class["rras"].values()], 0)
            self.log("Actual rrd-class consists of %s (%s)" % (logging_tools.get_plural("rra", len(self.act_rrd_class["rras"].keys())),
                                                               logging_tools.get_plural("row", tot_rows)))
        rebuild = force
        new_local_name = "%s.rrd" % (self.name)
        rrd_root_dir = self.get_glob_config()["RRD_DIR"]
        if not os.path.exists(rrd_root_dir):
            self.log("creating rrd-dir %s" % (rrd_root_dir))
            os.makedirs(rrd_root_dir)
        self.rrd_dir = "%s/%s" % (self.get_glob_config()["RRD_DIR"],
                                  new_local_name)
        self.log("rrd_dir set to %s" % (self.rrd_dir))
        dc.execute("SELECT rs.filename, rs.rrd_set_idx FROM rrd_set rs, device d WHERE rs.device=d.device_idx AND d.name='%s'" % (self.name))
        if dc.rowcount:
            mr = dc.fetchone()
            if not mr["filename"]:
                self.log("setting rrd_set filename to '%s'" % (new_local_name))
                mr["filename"] = new_local_name
                dc.execute("UPDATE rrd_set SET filename=%s WHERE rrd_set_idx=%s", (new_local_name,
                                                                                   mr["rrd_set_idx"]))
            # we have to rebuild if....
            if new_local_name != mr["filename"]:
                # the name of the device has changed
                if os.path.isdir(self.rrd_dir):
                    self.log("Name of rrd_set basedirectory has changed (from %s to %s), renaming directory ..." % (mr["filename"],
                                                                                                                    new_local_name),
                             logging_tools.LOG_LEVEL_WARN)
                    old_dir_name = "%s/%s" % (rrd_root_dir,
                                              mr["filename"])
                    if os.path.isdir(self.rrd_dir):
                        self.log("removing already existing new directory %s" % (self.rrd_dir),
                                 logging_tools.LOG_LEVEL_WARN)
                        try:
                            shutil.rmtree(self.rrd_dir)
                        except:
                            self.log("removing %s resulted in an error: %s" % (self.rrd_dir,
                                                                               process_tools.get_except_info()),
                                     logging_tools.LOG_LEVEL_ERROR)
                    if not os.path.isdir(self.rrd_dir):
                        self.log("renaming '%s' to '%s'" % (old_dir_name,
                                                            self.rrd_dir))
                        try:
                            os.rename(old_dir_name, self.rrd_dir)
                        except:
                            self.log("... got an error: %s" % (process_tools.get_except_info()),
                                     logging_tools.LOG_LEVEL_ERROR)
                else:
                    self.log("Name of rrd_set basedirectory has changed (from %s to %s), creating directory ..." % (mr["filename"],
                                                                                                                    new_local_name),
                             logging_tools.LOG_LEVEL_ERROR)
                    rebuild = True
                dc.execute("UPDATE rrd_set SET filename=%s WHERE rrd_set_idx=%s", (new_local_name,
                                                                                   mr["rrd_set_idx"]))
            else:
                # no database-file can be found
                if not os.path.isdir(self.rrd_dir):
                    self.log("rrd-dir %s not found, force rebuild" % (self.rrd_dir),
                             logging_tools.LOG_LEVEL_WARN)
                    rebuild = True
        else:
            mr = None
            rebuild = True
        if rebuild:
            self.log("rebuilding", logging_tools.LOG_LEVEL_WARN)
            if rrd_class:
                if mr:
                    self.log("Old rrd_set entry present, preserving rrd_data and rrd_set")
                    self.__rrd_set_index = mr["rrd_set_idx"]
                else:
                    self.log("No old rrd_set entry present, inserting new one",
                             logging_tools.LOG_LEVEL_WARN)
                    dc.execute("INSERT INTO rrd_set VALUES(0, %s, %s, null)", (self.dev_idx,
                                                                               new_local_name))
                    self.__rrd_set_index = dc.insert_id()
                act_class = act_rrd_classes[rrd_class]
                if not os.path.isdir(self.rrd_dir):
                    if os.path.isfile(self.rrd_dir):
                        self.log("removing old file %s" % (self.rrd_dir), logging_tools.LOG_LEVEL_WARN)
                        try:
                            os.unlink(self.rrd_dir)
                        except:
                            self.log("error removing file %s: %s" % (self.rrd_dir, process_tools.get_except_info()),
                                     logging_tools.LOG_LEVEL_CRITICAL)
                    self.log("Creating rrd-directory %s" % (self.rrd_dir))
                    os.makedirs(self.rrd_dir)
                if os.path.isdir(self.rrd_dir):
                    files_rem, dirs_rem = (0, 0)
                    for dir_path, dir_names, file_names in os.walk(self.rrd_dir, False):
                        for full_name in ["%s/%s" % (dir_path, file_name) for file_name in file_names]:
                            try:
                                os.unlink(full_name)
                            except:
                                self.log("error removing file %s: %s" % (full_name, process_tools.get_except_info()),
                                         logging_tools.LOG_LEVEL_CRITICAL)
                            else:
                                files_rem += 1
                        for full_name in ["%s/%s" % (dir_path, dir_name) for dir_name in dir_names]:
                            try:
                                os.rmdir(full_name)
                            except:
                                self.log("error removing dir %s: %s" % (full_name, process_tools.get_except_info()),
                                         logging_tools.LOG_LEVEL_CRITICAL)
                            else:
                                dirs_rem += 1
                    self.log("removed %s, %s under directory %s" % (logging_tools.get_plural("file", files_rem),
                                                                    logging_tools.get_plural("directory", dirs_rem),
                                                                    self.rrd_dir))
        return rebuild
    
class logging_thread(threading_tools.thread_obj):
    def __init__(self, glob_config, loc_config):
        self.__sep_str = "-" * 50
        self.__glob_config, self.__loc_config = (glob_config, loc_config)
        self.__machlogs, self.__glob_log, self.__glob_cache = ({}, None, [])
        threading_tools.thread_obj.__init__(self, "logging", queue_size=500, priority=10)
        self.register_func("log", self._log)
        self.register_func("mach_log", self._mach_log)
        self.register_func("set_ad_struct", self._set_ad_struct)
        self.register_func("set_queue_dict", self._set_queue_dict)
        self.register_func("update", self._update)
        self.register_func("delay_request", self._delay_request)
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
    def loop_end(self):
        for mach in self.__machlogs.keys():
            self.__machlogs[mach].write("Closing log")
            self.__machlogs[mach].close()
        self.__glob_log.write("Closed %s" % (logging_tools.get_plural("machine log", len(self.__machlogs.keys()))))
        self.__glob_log.write("Closing log")
        self.__glob_log.write("logging thread exiting (pid %d)" % (self.pid))
        self.send_pool_message(("remove_pid", (self.name, self.pid)))
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
                # if mach is None for name setting
                name = mach and mach.name or name
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
        
class command_thread(threading_tools.thread_obj):
    def __init__(self, glob_config, loc_config, db_con, log_queue):
        self.__db_con = db_con
        self.__log_queue = log_queue
        self.__glob_config, self.__loc_config = (glob_config, loc_config)
        threading_tools.thread_obj.__init__(self, "command", queue_size=100)
        self.register_func("set_queue_dict", self._set_queue_dict)
        self.register_func("set_ad_struct", self._set_ad_struct)
        self.register_func("com_con", self._com_con)
        self.register_func("set_net_stuff", self._set_net_stuff)
        self.__net_server = None
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__log_queue.put(("log", (self.name, what, lev)))
    def _set_ad_struct(self, ad_struct):
        self.log("got ad_struct")
        self.__ad_struct = ad_struct
    def thread_running(self):
        self.send_pool_message(("new_pid", (self.name, self.pid)))
    def loop_end(self):
        self.send_pool_message(("remove_pid", (self.name, self.pid)))
    def _set_queue_dict(self, q_dict):
        self.__queue_dict = q_dict
    def _set_net_stuff(self, (net_server)):
        self.log("Got net_server")
        self.__net_server = net_server
    def _com_con(self, tcp_obj):
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
            ret_str = "OK: all %d threads running, version %s" % (num_ok, self.__loc_config["VERSION_STRING"])
        else:
            ret_str = "ERROR: only %d of %d threads running, version %s" % (num_ok, num_threads, self.__loc_config["VERSION_STRING"])
        server_reply = server_command.server_reply()
        server_reply.set_ok_result(ret_str)
        tcp_obj.add_to_out_buffer(server_reply, "status")

class writer_thread(threading_tools.thread_obj):
    def __init__(self, glob_config, loc_config, db_con, log_queue):
        self.__db_con = db_con
        self.__log_queue = log_queue
        self.__glob_config, self.__loc_config = (glob_config, loc_config)
        threading_tools.thread_obj.__init__(self, "writer", queue_size=100)
        self.register_func("set_ad_struct", self._set_ad_struct)
        self.register_func("set_queue_dict", self._set_queue_dict)
        self.register_func("start_write", self._start_write)
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__log_queue.put(("log", (self.name, what, lev)))
    def loop_end(self):
        self.send_pool_message(("remove_pid", (self.name, self.pid)))
    def thread_running(self):
        self.send_pool_message(("new_pid", (self.name, self.pid)))
    def _set_queue_dict(self, q_dict):
        self.__queue_dict = q_dict
    def _set_ad_struct(self, ad_struct):
        self.log("got ad_struct")
        self.__ad_struct = ad_struct
    def _start_write(self):
        s_time = time.time()
        dc = self.__db_con.get_connection(SQL_ACCESS)
        act_rrd_classes = None
        dc.execute("SELECT ds.rrd_data_store_idx, ds.device FROM rrd_data_store ds ORDER BY ds.recv_time")
        dev_dict = {}
        for db_rec in dc.fetchall():
            dev_dict.setdefault(db_rec["device"], []).append(db_rec["rrd_data_store_idx"])
        dev_idxs = dev_dict.keys()
        unknown_devs = [idx for idx in dev_idxs if idx not in self.__ad_struct.keys()]
        if unknown_devs:
            # try to find the devices
            for idx in unknown_devs:
                if not act_rrd_classes:
                    act_rrd_classes = read_rrd_class_tree(dc)
                found = self.__ad_struct.db_sync(dc, idx, act_rrd_classes)
                if not found:
                    self.log("index %d not found, removing" % (idx))
                    del dev_dict[idx]
        unknown_devs = [idx for idx in dev_idxs if idx not in self.__ad_struct.keys()]
        if unknown_devs:
            self.log("Found %s in data_store: %s" % (logging_tools.get_plural("unknown device", len(unknown_devs)),
                                                     ", ".join(["%d" % (idx) for idx in sorted(unknown_devs)])),
                     logging_tools.LOG_LEVEL_ERROR)
        num_devs, num_updates, num_error, num_created, num_values = (0, 0, 0, 0, 0)
        # check for rrd_changes
        if dev_dict:
            sql_str = "SELECT d.rrd_class, d.device_idx FROM device d WHERE %s" % (" OR ".join(["d.device_idx=%d" % (dev_idx) for dev_idx in dev_dict.keys()]))
            dc.execute(sql_str)
            new_dict = dict([(db_rec["device_idx"], db_rec["rrd_class"]) for db_rec in dc.fetchall()])
            all_idxs = []
            # iterate over devices
            for dev_idx, ds_idxs in dev_dict.iteritems():
                # gather start time
                g_s_time = time.time()
                num_devs += 1
                act_dev = self.__ad_struct[dev_idx]
                if new_dict.has_key(dev_idx):
                    if act_dev.act_rrd_class_idx != new_dict[dev_idx]:
                        act_dev.log("rrd_class changed", logging_tools.LOG_LEVEL_WARN)
                        if not act_rrd_classes:
                            act_rrd_classes = read_rrd_class_tree(dc)
                        act_dev.create_rrd_database(dc, act_rrd_classes, force=True)
                all_idxs.extend(ds_idxs)
                if self.__glob_config["CHECK_FOR_SANE_TIMES"]:
                    sql_str = "SELECT * FROM rrd_data_store WHERE device=%d AND (%s) AND recv_time < %d ORDER BY recv_time" % (dev_idx,
                                                                                                                               " OR ".join(["rrd_data_store_idx=%d" % (idx) for idx in ds_idxs]),
                                                                                                                               time.time())
                else:
                    sql_str = "SELECT * FROM rrd_data_store WHERE device=%d AND (%s) ORDER BY recv_time" % (dev_idx,
                                                                                                            " OR ".join(["rrd_data_store_idx=%d" % (idx) for idx in ds_idxs]))
                dc.execute(sql_str)
                num_discard = 0
                # build data vector
                act_dv = {}
                for act_rec in dc.fetchall():
                    if type(act_rec["data"]) == type(""):
                        data_str = act_rec["data"]
                    else:
                        data_str = act_rec["data"].tostring()
                    try:
                        if data_str[0] in ["{", "["]:
                            act_data = marshal.loads(data_str)
                        else:
                            act_data = cPickle.loads(data_str)
                    except:
                        self.log("error unmarshaling / unpickling data_str", logging_tools.LOG_LEVEL_ERROR)
                    else:
                        if type(act_data) == type({}):
                            # old dict-type savestyle
                            for key, value in act_data.iteritems():
                                act_dv.setdefault(key, []).append("%d:%s" % (act_rec["recv_time"], value))
                        else:
                            # tuple
                            for key, value in act_data:
                                act_dv.setdefault(key, []).append("%d:%s" % (act_rec["recv_time"], value))
                dev_s_time = time.time()
                for act_key, data_list in act_dv.iteritems():
                    num_updates += 1
                    num_values += len(data_list)
                    if not act_dev.rrd_data.has_key(act_key):
                        act_dev._add_rrd_data(act_key)
                    if not act_dev.rrd_data[act_key].store_values(data_list):
                        num_error += 1
                        # try to recreate the rrd
                        if act_dev.rrd_data[act_key].create_rrd_database(act_dev.rrd_dir, act_dev.act_rrd_class, check_for_changes=False):
                            num_created += 1
                dev_e_time = time.time()
                act_dev.log("update of %s took %s (gathering took %s)" % (logging_tools.get_plural("set", len(act_dv.keys())),
                                                                          logging_tools.get_diff_time_str(dev_e_time - dev_s_time),
                                                                          logging_tools.get_diff_time_str(dev_s_time - g_s_time)))
                del act_dv
            all_idxs.sort()
            if all_idxs:
                self.log("removing %s from DB" % (logging_tools.get_plural("entry", len(all_idxs))))
                sql_str = "DELETE FROM rrd_data_store WHERE %s" % (" OR ".join(["rrd_data_store_idx=%d" % (idx) for idx in all_idxs]))
            dc.execute(sql_str)
        dc.release()
        e_time = time.time()
        self.log("wrote for %s (%s, %s, %s%s)" % (logging_tools.get_plural("device", num_devs),
                                                  logging_tools.get_plural("update", num_updates),
                                                  logging_tools.get_plural("error", num_error),
                                                  logging_tools.get_plural("value", num_values),
                                                  num_created and ", %s" % (logging_tools.get_plural("new rrd", num_created)) or ""))
        self.send_pool_message(("write_done", (e_time - s_time)))

class server_thread_pool(threading_tools.thread_pool):
    def __init__(self, db_con, g_config, loc_config):
        self.__log_cache, self.__log_queue = ([], None)
        self.__db_con = db_con
        self.__glob_config, self.__loc_config = (g_config, loc_config)
        threading_tools.thread_pool.__init__(self, "main", blocking_loop=False)
        self.__msi_block = self._init_msi_block()
        self.register_func("new_pid", self._new_pid)
        self.register_func("remove_pid", self._remove_pid)
        self.register_func("write_done", self._write_done)
        self.register_exception("int_error", self._int_error)
        self.register_exception("term_error", self._int_error)
        self.__log_queue = self.add_thread(logging_thread(self.__glob_config, self.__loc_config), start_thread=True).get_thread_queue()
        #self.register_exception("hup_error", self._hup_error)
        # log config
        self._log_config()
        # prepare directories
        #self._prepare_directories()
        dc = self.__db_con.get_connection(SQL_ACCESS)
        # re-insert config
        self._re_insert_config(dc)
        # global network settings
        self._init_rrd_classes(dc)
        self.__ad_struct = all_devices(self.__log_queue, self.__glob_config, self.__loc_config, self.__db_con)
        self.__log_queue.put(("set_ad_struct", self.__ad_struct))
        self.__ns = net_tools.network_server(timeout=2, log_hook=self.log, poll_verbose=self.__loc_config["VERBOSE"] > 1)
        #self._check_nfs_exports(dc)
        # start threads
        self.__act_col = 0
        self.__com_queue         = self.add_thread(command_thread(self.__glob_config, self.__loc_config, self.__db_con, self.__log_queue), start_thread=True).get_thread_queue()
        self.__writer_queue      = self.add_thread(writer_thread(self.__glob_config, self.__loc_config, self.__db_con, self.__log_queue), start_thread=True).get_thread_queue()
        self.__com_queue.put(("set_ad_struct", self.__ad_struct))
        self.__writer_queue.put(("set_ad_struct", self.__ad_struct))
        #        self._check_global_network_stuff(dc)
        self.__queue_dict = {"log_queue"         : self.__log_queue,
                             "command_queue"     : self.__com_queue,
                             "writer_queue"      : self.__writer_queue}
        self.__log_queue.put(("set_queue_dict", self.__queue_dict))
        self.__com_queue.put(("set_queue_dict", self.__queue_dict))
        self.__writer_queue.put(("set_queue_dict", self.__queue_dict))
        self.__com_queue.put(("set_net_stuff", (self.__ns)))
        dc.release()
        # uuid log
        my_uuid = uuid_tools.get_uuid()
        self.log("cluster_device_uuid is '%s'" % (my_uuid.get_urn()))
        self.__last_update = None
        # rrd_writer stepping control
        self.__last_rrd_write, self.__rrd_write_in_flight = (time.time() - 2 * self.__glob_config["RRD_WRITE_TICK"], False)
        self.__ns.add_object(net_tools.tcp_bind(self._new_tcp_command_con, port=self.__glob_config["COMMAND_PORT"], bind_retries=5, bind_state_call=self._bind_state_call, timeout=60))
    def _int_error(self, err_cause):
        if self["exit_requested"]:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            self.log("exit requested", logging_tools.LOG_LEVEL_WARN)
            self["exit_requested"] = True
            try:
                file(self.__loc_config["LOCK_FILE_NAME"], "w").write("init shutdown")
            except:
                self.log("error writing to %s: %s" % (self.__loc_config["LOCK_FILE_NAME"],
                                                      process_tools.get_except_info()),
                         logging_tools.LOG_LEVEL_ERROR)
            self.__ns.set_timeout(1)
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
        configfile.write_config(dc, CAP_NAME, self.__glob_config)
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        if self.__log_queue:
            if self.__log_cache:
                for c_what, c_lev in self.__log_cache:
                    self.__log_queue.put(("log", (self.name, "(delayed) %s" % (c_what), c_lev)))
                self.__log_cache = []
            self.__log_queue.put(("log", (self.name, what, lev)))
        else:
            self.__log_cache.append((what, lev))
    def _check_global_network_stuff(self, dc):
        self.log("Checking global network settings")
        dc.execute("SELECT i.ip,n.netdevice_idx,nw.network_idx FROM netdevice n, netip i, network nw WHERE n.device=%d AND i.netdevice=n.netdevice_idx AND i.network=nw.network_idx" % (self.__loc_config["RRD_SERVER_WRITER_IDX"]))
        glob_net_devices = {}
        for net_rec in dc.fetchall():
            n_d, n_i, n_w = (net_rec["netdevice_idx"],
                             net_rec["ip"],
                             net_rec["network_idx"])
            if not glob_net_devices.has_key(n_d):
                glob_net_devices[n_d] = []
            glob_net_devices[n_d].append((n_i, n_w))
        # get all network_device_types
        dc.execute("SELECT * FROM network_device_type")
        self.__loc_config["GLOBAL_NET_DEVICES"] = glob_net_devices
        self.__loc_config["GLOBAL_NET_DEVICE_DICT"] = dict([(x["identifier"], x["network_device_type_idx"]) for x in dc.fetchall()])
    def _init_msi_block(self):
        process_tools.save_pid(self.__loc_config["PID_NAME"])
        if self.__loc_config["DAEMON"]:
            self.log("Initialising meta-server-info block")
            msi_block = process_tools.meta_server_info(PROG_NAME)
            msi_block.add_actual_pid()
            msi_block.start_command = "/etc/init.d/%s start" % (PROG_NAME)
            msi_block.stop_command = "/etc/init.d/%s force-stop" % (PROG_NAME)
            msi_block.kill_pids = True
            msi_block.save_block()
        else:
            msi_block = None
        return msi_block
    def _new_ud_out_recv(self, data, src):
        self.__log_queue.put(("syslog_dhcp", data))
    def _new_tcp_command_con(self, sock, src):
        self.log("got command from host %s, port %d" % (src[0], src[1]))
        return new_tcp_con("com", "tcp", None, src, self.__com_queue, self.__log_queue)
    def _bind_state_call(self, **args):
        if args["state"].count("ok"):
            self.log("Bind to %s (type %s) sucessfull" % (args["port"], args["type"]))
        else:
            self.log("Bind to %s (type %s) NOT sucessfull" % (args["port"], args["type"]), logging_tools.LOG_LEVEL_CRITICAL)
            self.log("unable to bind to all ports, exiting", logging_tools.LOG_LEVEL_ERROR)
            self._int_error("bind problem")
    def loop_function(self):
        self.__ns.step()
        if self.__loc_config["VERBOSE"] or self["exit_requested"]:
            tqi_dict = self.get_thread_queue_info()
            tq_names = sorted(tqi_dict.keys())
            self.log("tqi: %s" % (", ".join(["%s: %3d of %3d" % (t_name, t_used, t_total) for (t_name, t_used, t_total) in [(t_name,
                                                                                                                             tqi_dict[t_name][1],
                                                                                                                             tqi_dict[t_name][0]) for t_name in tq_names] if t_used]) or "clean"))
        act_time = time.time()
        if not self.__last_update or abs(self.__last_update - act_time) > self.__glob_config["MAIN_TICK"]:
            self.__last_update = act_time
        self._write_stepping_control()
    def _write_done(self, time_needed):
        self.__rrd_write_in_flight = False
        self.log("rrd_write took %s" % (logging_tools.get_diff_time_str(time_needed)))
    def _write_stepping_control(self):
        act_time = time.time()
        if abs(self.__last_rrd_write - act_time) > self.__glob_config["RRD_WRITE_TICK"]:
            self.__last_rrd_write = act_time
            if self.__rrd_write_in_flight:
                self.log("rrd_write_tick reached but writing still in progress",
                         logging_tools.LOG_LEVEL_WARN)
            else:
                self.__rrd_write_in_flight = True
                self.__writer_queue.put("start_write")
    def thread_loop_post(self):
        process_tools.delete_pid(self.__loc_config["PID_NAME"])
        if self.__msi_block:
            self.__msi_block.remove_meta_block()
        try:
            os.unlink(self.__loc_config["LOCK_FILE_NAME"])
        except (IOError, OSError):
            pass
    def _init_rrd_classes(self, dc):
        dc.execute("SELECT c.name, COUNT(r.cf) AS rra_num FROM rrd_class c LEFT JOIN rrd_rra r ON r.rrd_class=c.rrd_class_idx GROUP BY c.name")
        if dc.rowcount:
            self.log("Found %s:" % (logging_tools.get_plural("rrd_class", dc.rowcount)))
            for stuff in dc.fetchall():
                self.log(" - class %30s, %s" % (stuff["name"], logging_tools.get_plural("rrd_set", stuff["rra_num"])))
        else:
            self.log("Inserting default rrd_class")
            # hearbeat is set to 90 for all classes (for SNMP devices)
            rrd_class_dict = {"standard_device" : {"step"      : 30,
                                                   "heartbeat" : 90,
                                                   "rras" : [(          30,              24 * 60 * 60, ["AVERAGE", "MAX", "MIN"]),
                                                             (      5 * 60,          7 * 24 * 60 * 60, ["AVERAGE", "MAX", "MIN"]),
                                                             (     15 * 60,      4 * 7 * 24 * 60 * 60, ["AVERAGE", "MAX", "MIN"]),
                                                             ( 4 * 60 * 60, 12 * 4 * 7 * 24 * 60 * 60, ["AVERAGE", "MAX", "MIN"])]},
                              "detail_device" : {"step"      : 30,
                                                 "heartbeat" : 90,
                                                 "rras" : [(     30,              24 * 60 * 60, ["AVERAGE", "MAX", "MIN"]),
                                                           ( 2 * 60,          7 * 24 * 60 * 60, ["AVERAGE", "MAX", "MIN"]),
                                                           ( 5 * 60,      4 * 7 * 24 * 60 * 60, ["AVERAGE", "MAX", "MIN"]),
                                                           (60 * 60, 12 * 4 * 7 * 24 * 60 * 60, ["AVERAGE", "MAX", "MIN"])]},
                              "snmp_device" : {"step"      : 90,
                                               "heartbeat" : 90,
                                               "rras" : [(         30,              24 * 60 * 60, ["AVERAGE", "MAX", "MIN"]),
                                                         (     5 * 60,          7 * 24 * 60 * 60, ["AVERAGE", "MAX", "MIN"]),
                                                         (    15 * 60,      4 * 7 * 24 * 60 * 60, ["AVERAGE", "MAX", "MIN"]),
                                                         (4 * 60 * 60, 12 * 4 * 7 * 24 * 60 * 60, ["AVERAGE", "MAX", "MIN"])]}}
            for class_name, class_stuff in rrd_class_dict.iteritems():
                dc.execute("INSERT INTO rrd_class SET name='%s', step=%d, heartbeat=%d" % (class_name,
                                                                                           class_stuff["step"], 
                                                                                           class_stuff["heartbeat"]))
                class_step = class_stuff["step"]
                set_idx = dc.insert_id()
                self.log(" - inserting class %s with %s (index %d)" % (class_name,
                                                                       logging_tools.get_plural("rra", len(class_stuff["rras"])),
                                                                       set_idx))
                for step, slots, cf_funcs in class_stuff["rras"]:
                    # max() needed, otherwise divbyzero
                    st_r = max(step, class_step) / class_step
                    st_s = slots / (class_step * st_r)
                    self.log(" ... inserting rras (%s: %s), timestep is %-16s, max time is %-24s (%s, %s)" % (logging_tools.get_plural("func", len(cf_funcs)),
                                                                                                              ", ".join(cf_funcs),
                                                                                                              logging_tools.get_plural("second", step),
                                                                                                              logging_tools.get_plural("second", slots),
                                                                                                              logging_tools.get_plural("step", st_r),
                                                                                                              logging_tools.get_plural("row", st_s)))
                    for cf_func in cf_funcs:
                        dc.execute("INSERT INTO rrd_rra SET rrd_class=%d, cf='%s', steps=%d, rows=%d" % (set_idx,
                                                                                                         cf_func,
                                                                                                         st_r,
                                                                                                         st_s))

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], "vdhCu:g:fk", ["help", "version", "no-mysql-log"])
    except getopt.GetoptError, bla:
        print "Cannot parse commandline (%s)!" % (bla)
        sys.exit(-1)
    long_host_name = socket.getfqdn(socket.gethostname())
    short_host_name = long_host_name.split(".")[0]
    # read version
    try:
        from rrd_server_writer_version import VERSION_STRING
    except ImportError:
        VERSION_STRING = "?.?"
    loc_config = configfile.configuration("local_config", {"PID_NAME"               : configfile.str_c_var("%s/%s" % (BASE_NAME, PROG_NAME)),
                                                           "SERVER_FULL_NAME"       : configfile.str_c_var(long_host_name),
                                                           "SERVER_SHORT_NAME"      : configfile.str_c_var(short_host_name),
                                                           "DAEMON"                 : configfile.bool_c_var(True),
                                                           "VERBOSE"                : configfile.int_c_var(0),
                                                           "RRD_SERVER_WRITER_IDX"  : configfile.int_c_var(0),
                                                           "LOG_SOURCE_IDX"         : configfile.int_c_var(0),
                                                           "NODE_SOURCE_IDX"        : configfile.int_c_var(0),
                                                           "GLOBAL_NET_DEVICES"     : configfile.dict_c_var({}),
                                                           "GLOBAL_NET_DEVICE_DICT" : configfile.dict_c_var({}),
                                                           "VERSION_STRING"         : configfile.str_c_var(VERSION_STRING),
                                                           "LOCK_FILE_NAME"         : configfile.str_c_var("/var/lock/%s/%s.lock" % (PROG_NAME, PROG_NAME)),
                                                           "FIXIT"                  : configfile.bool_c_var(False),
                                                           "CHECK"                  : configfile.bool_c_var(False),
                                                           "KILL_RUNNING"           : configfile.bool_c_var(True),
                                                           "MYSQL_LOG"              : configfile.bool_c_var(True),
                                                           "USER"                   : configfile.str_c_var("root"),
                                                           "GROUP"                  : configfile.str_c_var("root")})
    loc_config.parse_file("/etc/sysconfig/rrd-server-writer")
    pname = os.path.basename(sys.argv[0])
    for opt, arg in opts:
        if opt in ["-h", "--help"]:
            print "Usage: %s [-h|--help] [OPTIONS] where OPTIONS is one or more of" % (pname)
            print "  -h,--help        show this help"
            print "  --version        version info"
            print "  -d               enable debug mode (no forking)"
            print "  -f               create and fix needed files and directories"
            print "  -u user          run as user USER, default is '%s'" % (loc_config["USER"])
            print "  -g group         run as group GROUP, default is '%s'" % (loc_config["GROUP"])
            print "  -k               do not kill running %s" % (pname)
            print "  -v               be verbose"
            print "  --no-mysql-log   disable SQL-logging when running in daemon mode"
            sys.exit(0)
        if opt == "--version":
            print "%s, Version %s" % (PROG_NAME, loc_config["VERSION_STRING"])
            sys.exit(0)
        if opt == "-C":
            loc_config["CHECK"] = True
        if opt == "-d":
            loc_config["DAEMON"] = False
        if opt == "-f":
            loc_config["FIXIT"] = True
        if opt == "-u":
            loc_config["USER"] = arg
        if opt == "-g":
            loc_config["GROUP"] = arg
        if opt == "-k":
            loc_config["KILL_RUNNING"] = False
        if opt == "-v":
            loc_config["VERBOSE"] = True
        if opt == "--no-mysql-log":
            loc_config["MYSQL_LOG"] = False
    db_con = mysql_tools.dbcon_container(with_logging=(not loc_config["DAEMON"] and loc_config["MYSQL_LOG"]))
    try:
        dc = db_con.get_connection(SQL_ACCESS)
    except MySQLdb.OperationalError:
        sys.stderr.write(" Cannot connect to SQL-Server ")
        sys.exit(1)
    num_servers, loc_config["RRD_SERVER_WRITER_IDX"] = process_tools.is_server(dc, CAP_NAME)
    ret_state = 256
    if num_servers == 0:
        sys.stderr.write("Host %s is no %s" % (long_host_name, PROG_NAME))
        sys.exit(5)
    if loc_config["CHECK"]:
        sys.exit(0)
    if loc_config["KILL_RUNNING"]:
        kill_dict = process_tools.build_kill_dict(pname)
        for kill_pid, value in kill_dict.iteritems():
            log_str = "Trying to kill pid %d (%s) with signal 9 ..." % (kill_pid, value)
            try:
                os.kill(kill_pid, 9)
            except:
                log_str = "%s error (%s)" % (log_str, sys.exc_info()[0])
            else:
                log_str = "%s ok" % (log_str)
            logging_tools.my_syslog(log_str)
    g_config = configfile.read_global_config(dc, CAP_NAME, {"LOG_DIR"                   : configfile.str_c_var("/var/log/cluster/%s" % (PROG_NAME)),
                                                            "RRD_DIR"                   : configfile.str_c_var("/var/lib/rrd-server/rrds"),
                                                            "COMMAND_PORT"              : configfile.int_c_var(8016),
                                                            "SMTP_SERVER"               : configfile.str_c_var("localhost"),
                                                            "SMTP_SERVER_HELO"          : configfile.str_c_var("localhost"),
                                                            "RRD_PNG_DIR"               : configfile.str_c_var("/srv/www/htdocs/rrd-pngs"),
                                                            "MAIN_TICK"                 : configfile.int_c_var(30),
                                                            "RRD_WRITE_TICK"            : configfile.int_c_var(120),
                                                            "CHECK_FOR_SANE_TIMES"      : configfile.bool_c_var(True)})
    if num_servers > 1:
        print "Database error for host %s (%s): too many entries found (%d)" % (long_host_name, CAP_NAME, num_servers)
        dc.release()
    else:
        loc_config["LOG_SOURCE_IDX"] = process_tools.create_log_source_entry(dc, loc_config["RRD_SERVER_WRITER_IDX"], CAP_NAME, "RRD Server")
        if not loc_config["LOG_SOURCE_IDX"]:
            print "Too many log_sources with my id present, exiting..."
            dc.release()
        else:
            dc.release()
            if loc_config["FIXIT"]:
                process_tools.fix_directories(loc_config["USER"], loc_config["GROUP"], [g_config["LOG_DIR"],
                                                                                        g_config["RRD_DIR"],
                                                                                        "/var/run/%s" % (BASE_NAME),
                                                                                        {"name"     : g_config["RRD_PNG_DIR"],
                                                                                         "dir_mode ": 0777,
                                                                                         "walk_dir" : False},
                                                                                        "/etc/sysconfig/%s.d" % (BASE_NAME),
                                                                                        os.path.dirname(loc_config["LOCK_FILE_NAME"])])
            process_tools.fix_files(loc_config["USER"], loc_config["GROUP"], ["/var/log/%s.out" % (PROG_NAME),
                                                                              "/tmp/%s.out" % (PROG_NAME),
                                                                              loc_config["LOCK_FILE_NAME"]])
            process_tools.renice()
            process_tools.change_user_group(loc_config["USER"], loc_config["GROUP"])
            if loc_config["DAEMON"]:
                process_tools.become_daemon()
                process_tools.set_handles({"out" : (1, "%s.out" % (PROG_NAME)),
                                           "err" : (0, "/var/lib/logging-server/py_err")})
            else:
                print "Debugging %s ..." % (CAP_NAME)
            my_tp = server_thread_pool(db_con, g_config, loc_config)
            my_tp.thread_loop()
            #ret_state = server_code(num_retry, daemon, db_con)
    db_con.close()
    del db_con
    sys.exit(ret_state)

if __name__ == "__main__":
    main()
