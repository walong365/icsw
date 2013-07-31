#!/usr/bin/python-init -Otu
# -*- coding: utf-8 -*-
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008,2011,2012,2013 Andreas Lang-Nevyjel
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
import pprint
import server_command
import gzip
import cluster_location
import bz2
import config_tools
from django.db import connection
from django.db.models import Q
from initat.cluster.backbone.models import device

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

class machine(object):
    #def __init__(self, name, idx, ips={}, log_queue=None):
    @staticmethod 
    def g_log(what, log_level=logging_tools.LOG_LEVEL_OK):
        machine.srv_proc.log("[m] %s" % (what), log_level)
    @staticmethod
    def setup(srv_proc):
        machine.srv_proc = srv_proc
        machine.g_log("init")
        machine.dev_dict = {}
    @staticmethod
    def rotate_logs():
        machine.g_log("starting log rotation")
        s_time = time.time()
        ext_coms = []
        for dev in machine.dev_dict.itervalues():
            ext_coms.extend(dev._rotate_logs())
        machine.g_log("rotatet in %s, %s" % (
            logging_tools.get_diff_time_str(time.time() - s_time),
            logging_tools.get_plural("external command", len(ext_coms))))
    @staticmethod
    def db_sync():
        machine.g_log("start sync")
        s_time = time.time()
        all_devs = device.objects.all().prefetch_related(
            "netdevice_set",
            "netdevice_set__net_ip_set",
            "netdevice_set__net_ip_set__network",
            "netdevice_set__net_ip_set__network__network_type",
        )
        for cur_dev in all_devs:
            if cur_dev.name in machine.dev_dict:
                cur_mach = machine.dev_dict[cur_dev.name]
            else:
                cur_mach = machine(cur_dev)
            cur_mach.add_ips(cur_dev)
        machine.g_log("synced in %s" % (logging_tools.get_diff_time_str(time.time() - s_time)))
    def __init__(self, cur_dev):
        self.device = cur_dev
        self.name = cur_dev.name
        machine.dev_dict[self.name] = self
        self.log("Added to dict")
        self.__ip_dict = {}
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        machine.srv_proc.log("[%s] %s" % (self.name,
                                          what), log_level)
    def add_ips(self, cur_dev):
        any_changes = False
        for cur_nd in cur_dev.netdevice_set.all():
            for cur_ip in cur_nd.net_ip_set.all():
                if cur_ip.ip not in self.__ip_dict:
                    any_changes = True
                    if cur_ip.domain_tree_node:
                        self.__ip_dict[cur_ip.ip] = (cur_ip.domain_tree_node.node_postfix, cur_ip.network.network_type.identifier)
                    else:
                        self.__ip_dict[cur_ip.ip] = ("", cur_ip.network.network_type.identifier)
        if any_changes:
            self.log_ip_info()
            self.generate_syslog_dirs()
    def log_ip_info(self):
        if self.__ip_dict:
            self.log("IP information:")
            for ip in sorted(self.__ip_dict.keys()):
                nw_postfix, net_type = self.__ip_dict[ip]
                self.log(" IP %15s, postfix %-5s (type %-5s), full name is %s%s" % (
                    ip,
                    nw_postfix and "'%s'" % (nw_postfix) or "''",
                    net_type == "p" and "%s [*]" % (net_type) or net_type,
                    self.name,
                    nw_postfix))
        else:
            self.log("No IPs set")
    def generate_syslog_dirs(self):
        link_array = [("d", "%s/%s" % (global_config["SYSLOG_DIR"], self.name))]
        for ip, (nw_postfix, net_type) in self.__ip_dict.iteritems():
            if nw_postfix:
                link_array.append(("l", "%s/%s%s" % (global_config["SYSLOG_DIR"], self.name, nw_postfix)))
            if net_type != "l" or (net_type == "l" and self.name == global_config["SERVER_SHORT_NAME"]):
                link_array.append(("l", "%s/%s" % (global_config["SYSLOG_DIR"], ip)))
        self.process_link_array(link_array)
    def process_link_array(self, l_array):
        for pt, ps in l_array:
            if pt == "d":
                if not os.path.isdir(ps):
                    self.log("pla(): Creating directory %s" % (ps))
                    try:
                        os.mkdir(ps)
                    except:
                        self.log("  ...something went wrong for mkdir(): %s" % (process_tools.get_except_info()),
                                 logging_tools.LOG_LEVEL_ERROR)
            elif pt == "l":
                if type(ps) in [str, unicode]:
                    dest = self.name
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
                                self.log("  ...something went wrong for unlink(): %s" % (
                                    process_tools.get_except_info()),
                                         logging_tools.LOG_LEVEL_ERROR)
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
                            self.log("  ...something went wrong for unlink(): %s" % (process_tools.get_except_info()),
                                     logging_tools.LOG_LEVEL_ERROR)
                        try:
                            self.log("pla(): rmtree %s" % (ps))
                            shutil.rmtree(ps, 1)
                        except:
                            self.log("  ...something went wrong for rmtree(): %s" % (process_tools.get_except_info()),
                                     logging_tools.LOG_LEVEL_ERROR)
                    try:
                        self.log("pla(): symlink from %s to %s" % (ps, dest))
                        os.symlink(dest, ps)
                    except:
                        self.log("  ...something went wrong for symlink(): %s" % (process_tools.get_except_info()),
                                 logging_tools.LOG_LEVEL_ERROR)
    def _rotate_logs(self):
        ext_coms = []
        dirs_found, dirs_proc, files_proc, files_error, files_del, dirs_del = (0, 0, 0, 0, 0, 0)
        start_time = time.time()
        log_start_dir = os.path.join(global_config["SYSLOG_DIR"], self.name)
        if os.path.isdir(log_start_dir):
            lsd_len = len(log_start_dir)
            self.log("starting walk for rotate_logs() in %s" % (log_start_dir))
            # directories processeds
            start_time = time.time()
            for root_dir, sub_dirs, files in os.walk(log_start_dir):
                dirs_found += 1
                if root_dir.startswith(log_start_dir):
                    root_dir_p = [int(entry) for entry in root_dir[lsd_len:].split("/") if entry.isdigit()]
                    if len(root_dir_p) in [1, 2]:
                        # check for deletion of empty month-dirs
                        if not sub_dirs:
                            if len(root_dir_p) == 1:
                                host_info_str = "(dir %04d)" % (root_dir_p[0])
                            else:
                                host_info_str = "(dir %04d/%02d)" % (root_dir_p[0],
                                                                     root_dir_p[1])
                            err_files, ok_files = ([], [])
                            for file_name in files:
                                old_file = os.path.join(root_dir, file_name)
                                try:
                                    os.unlink(old_file)
                                except IOError:
                                    err_files.append(old_file)
                                else:
                                    ok_files.append(old_file)
                            if err_files:
                                self.log("Had problems deleting %s %s: %s" % (
                                    logging_tools.get_plural("file", len(err_files)),
                                    host_info_str,
                                    ", ".join(err_files)))
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
                                self.log("Deleted %s %s: %s" % (
                                    logging_tools.get_plural("file", len(ok_files)),
                                    host_info_str,
                                    ", ".join(ok_files)))
                                files_del += len(ok_files)
                    elif len(root_dir_p) == 3:
                        dir_time = time.mktime([
                            root_dir_p[0],
                            root_dir_p[1],
                            root_dir_p[2],
                            0,
                            0,
                            0,
                            0,
                            0,
                            0])
                        day_diff = int((start_time - dir_time) / (3600 * 24))
                        host_info_str = "(dir %04d/%02d/%02d)" % (
                            root_dir_p[0],
                            root_dir_p[1],
                            root_dir_p[2])
                        if day_diff > max(1, global_config["KEEP_LOGS_TOTAL"]):
                            err_files, ok_files = ([], [])
                            for file_name in [x for x in files]:
                                old_file = os.path.join(root_dir, file_name)
                                try:
                                    os.unlink(old_file)
                                except IOError:
                                    err_files.append(old_file)
                                else:
                                    ok_files.append(old_file)
                            if err_files:
                                self.log("Had problems deleting %s %s: %s" % (
                                    logging_tools.get_plural(
                                        "file",
                                        len(err_files)),
                                    host_info_str,
                                    ", ".join(err_files)))
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
                                self.log("Deleted %s %s: %s" % (
                                    logging_tools.get_plural("file", len(ok_files)),
                                    host_info_str,
                                    ", ".join(ok_files)))
                                files_del += len(ok_files)
                        elif day_diff > max(1, global_config["KEEP_LOGS_UNCOMPRESSED"]):
                            dirs_proc += 1
                            err_files, ok_files = ([], [])
                            old_size, new_size = (0, 0)
                            for file_name in [entry for entry in files if not entry.endswith(".gz") and not entry.startswith(SCAN_TEXT_PREFIX)]:
                                old_file = os.path.join(root_dir, file_name)
                                new_file = os.path.join(root_dir, "%s.gz" % (file_name))
                                ext_coms.append("compress %s %s")
                                #try:
                                    #old_f_size = os.stat(old_file)[stat.ST_SIZE]
                                    #new_fh = gzip.open(new_file, "wb", 4)
                                    #new_fh.write(file(old_file, "r").read())
                                    #new_fh.close()
                                    #new_f_size = os.stat(new_file)[stat.ST_SIZE]
                                #except:
                                    #err_files.append(file_name)
                                #else:
                                    #old_size += old_f_size
                                    #new_size += new_f_size
                                    #ok_files.append(file_name)
                                    #os.unlink(old_file)
                            #if err_files:
                                #self.log("Had problems compressing %s %s: %s" % (logging_tools.get_plural("file", len(err_files)), host_info_str, ", ".join(err_files)))
                                #files_error += len(err_files)
                            #if ok_files:
                                #self.log("Compressed %s %s: %s" % (logging_tools.get_plural("file", len(ok_files)), host_info_str, ", ".join(ok_files)))
                                #files_proc += len(ok_files)
                            #if err_files or ok_files:
                                #self.log("Stats for directory %s: Saved %s (%.2f %%, new size: %s, orig size: %s)" % (root_dir,
                                                                                                                      #logging_tools.get_size_str(old_size - new_size),
                                                                                                                      #100. * (float(old_size - new_size) / float(max(1, old_size))),
                                                                                                                      #logging_tools.get_size_str(new_size),
                                                                                                                      #logging_tools.get_size_str(old_size)))
            self.log("Found %s, checked %s in %.2f seconds (%s ok, %s error)" % (
                logging_tools.get_plural("directory", dirs_found),
                logging_tools.get_plural("directory", dirs_proc),
                time.time() - start_time,
                logging_tools.get_plural("file", files_proc),
                logging_tools.get_plural("file", files_error)))
            self.log("finished walk for rotate_logs(), found %s, checked %s, deleted %s in %.2f seconds (%s ok, deleted %s, %s error)" % (
                logging_tools.get_plural("directory", dirs_found),
                logging_tools.get_plural("directory", dirs_proc),
                logging_tools.get_plural("directory", dirs_del),
                time.time() - start_time,
                logging_tools.get_plural("file", files_proc),
                logging_tools.get_plural("file", files_del),
                logging_tools.get_plural("file", files_error)))
        else:
            self.log("log_start_dir %s not found, no log-rotate ..." % (log_start_dir))
        return ext_coms

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
        machine.setup(self)
        self.register_timer(self._sync_machines, 3600, instant=True)
        self.register_timer(self._rotate_logs, 3600 * 12, instant=True)
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
    def _sync_machines(self):
        connection.close()
        machine.db_sync()
    def _rotate_logs(self):
        connection.close()
        machine.rotate_logs()
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
        """ do not forget to enclose the local ruleset in $RuleSet local / $DefaultRuleset local """
        rsyslog_lines = [
            '# UDP Syslog Server:',
             '$ModLoad imudp.so         # provides UDP syslog reception',
            '',
            '$template prog_log,"%s/%%FROMHOST-IP%%/%%$YEAR%%/%%$MONTH%%/%%$DAY%%/%%programname%%"' % (global_config["SYSLOG_DIR"]),
            '$template full_log,"%s/%%FROMHOST-IP%%/%%$YEAR%%/%%$MONTH%%/%%$DAY%%/log"' % (global_config["SYSLOG_DIR"]),
            '',
            '$RuleSet remote',
            '$DirCreateMode 0755',
            '',
            '$FileCreateMode 0644',
            '*.* ?prog_log',
            '',
            '$FileCreateMode 0644', 
            '*.* ?full_log',
            '',
            '$InputUDPServerBindRuleset remote',
            '$UDPServerRun 514         # start a UDP syslog server at standard port 514',
            '',
            '$RuleSet RSYSLOG_DefaultRuleset',
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
        ("SERVER_SHORT_NAME"      , configfile.str_c_var(mach_name)),
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
