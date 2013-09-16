#!/usr/bin/python-init -Ot
# -*- coding: utf-8 -*-
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008,2010,2011,2012,2013 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of meta-server
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
""" meta-server, server process """

import configfile
import logging_tools
import mail_tools
import os
import process_tools
import threading_tools
import time
import server_command
import stat
import zmq
from initat.meta_server.config import global_config

try:
    from meta_server_version import VERSION_STRING
except ImportError:
    VERSION_STRING = "?.?"

class main_process(threading_tools.process_pool):
    def __init__(self):
        self.__log_cache, self.__log_template = ([], None)
        threading_tools.process_pool.__init__(self, "main", zmq=True, zmq_debug=global_config["ZMQ_DEBUG"])
        self.renice()
        if not global_config["DEBUG"]:
            process_tools.set_handles(
                {
                    "out" : (1, "meta-server.out"),
                    "err" : (0, "/var/lib/logging-server/py_err")},
                    zmq_context=self.zmq_context)
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context)
        # threading_tools.twisted_main_thread.__init__(self, "main")
        # self.install_signal_handlers()
        # self.add_thread(twisted_thread("twisted", global_config), start_thread=True)
        self._init_msi_block()
        self._init_network_sockets()
        self.register_exception("int_error", self._sigint)
        self.register_exception("term_error", self._sigint)
        # init stuff for mailing
        self.__new_mail = mail_tools.mail(None, "%s@%s" % (global_config["FROM_NAME"], global_config["FROM_ADDR"]), global_config["TO_ADDR"])
        self.__new_mail.set_server(global_config["MAILSERVER"], global_config["MAILSERVER"])
        # check
        self.__check_dict = {}
        self.__last_update_time = time.time() - 2 * global_config["MIN_CHECK_TIME"]
        self.__problem_list = []
        self._init_meminfo()
        self._show_config()
        act_commands = self._check_for_new_info([])
        self._do_commands(act_commands)
        self.register_timer(self._check, 60, instant=True)
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        if self.__log_template:
            self.__log_template.log(lev, what)
        else:
            self.__log_cache.append((lev, what))
    def _init_msi_block(self):
        # store pid name because global_config becomes unavailable after SIGTERM
        self.__pid_name = global_config["PID_NAME"]
        process_tools.save_pids(self.__pid_name, mult=3)
        print self.__pid_name
        process_tools.append_pids(self.__pid_name, pid=configfile.get_manager_pid(), mult=2)
        if True: # not self.__options.DEBUG:
            self.log("Initialising meta-server-info block")
            msi_block = process_tools.meta_server_info("meta-server")
            msi_block.add_actual_pid(mult=3)
            msi_block.add_actual_pid(act_pid=configfile.get_manager_pid(), mult=2)
            msi_block.start_command = "/etc/init.d/meta-server start"
            msi_block.stop_command = "/etc/init.d/meta-server force-stop"
            msi_block.kill_pids = True
            # msi_block.heartbeat_timeout = 60
            msi_block.save_block()
        else:
            msi_block = None
        self.__msi_block = msi_block
    def _sigint(self, err_cause):
        if self["exit_requested"]:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            self["exit_requested"] = True
    def _init_network_sockets(self):
        client = self.zmq_context.socket(zmq.ROUTER)
        # client.setsockopt(zmq.IDENTITY, "ms")
        try:
            client.bind("tcp://*:%d" % (global_config["COM_PORT"]))
        except zmq.core.error.ZMQError:
            self.log("error binding to %d: %s" % (global_config["COM_PORT"],
                                                  process_tools.get_except_info()),
                     logging_tools.LOG_LEVEL_CRITICAL)
            raise
        else:
            self.register_poller(client, zmq.POLLIN, self._recv_command)
        self.network_socket = client
    def _recv_command(self, zmq_sock):
        src_id = zmq_sock.recv()
        more = zmq_sock.getsockopt(zmq.RCVMORE)
        if more:
            data = zmq_sock.recv()
            more = zmq_sock.getsockopt(zmq.RCVMORE)
            srv_com = server_command.srv_command(source=data)
            self.log("got command '%s' from '%s'" % (
                srv_com["command"].text,
                srv_com["source"].attrib["host"]))
            srv_com.update_source()
            srv_com["result"] = {"state" : server_command.SRV_REPLY_STATE_OK,
                                 "reply" : "ok"}
            if srv_com["command"].text == "status":
                srv_com["result"].attrib["reply"] = "ok process is running"
            elif srv_com["command"].text == "version":
                srv_com["result"].attrib["reply"] = "version is %s" % (VERSION_STRING)
            else:
                srv_com["result"].attrib.update({"reply" : "unknown command '%s'" % (srv_com["command"].text),
                                                 "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR)})
            zmq_sock.send_unicode(src_id, zmq.SNDMORE)
            zmq_sock.send_unicode(unicode(srv_com))
        else:
            self.log("cannot receive more data, already got '%s'" % (src_id),
                     logging_tools.LOG_LEVEL_ERROR)
    def _show_config(self):
        try:
            for log_line, log_level in global_config.get_log():
                self.log("Config info : [%d] %s" % (log_level, log_line))
        except:
            self.log("error showing configfile log, old configfile ? (%s)" % (process_tools.get_except_info()),
                     logging_tools.LOG_LEVEL_ERROR)
        conf_info = global_config.get_config_info()
        self.log("Found %s:" % (logging_tools.get_plural("valid configline", len(conf_info))))
        for conf in conf_info:
            self.log("Config : %s" % (conf))
    def loop_end(self):
        process_tools.delete_pid(self.__pid_name)
        if self.__msi_block:
            self.__msi_block.remove_meta_block()
    def _do_commands(self, act_commands):
        for act_command in act_commands:
            self._submit_at_command(act_command, 1)
    def _submit_at_command(self, com, when):
        _c_stat, log_lines = process_tools.submit_at_command(com, when)
        for line in log_lines:
            self.log(line)
    def _init_meminfo(self):
        self.__last_meminfo_keys, self.__act_meminfo_line = ([], 0)
    def _check_for_new_info(self, problem_list):
        # problem_list: list of problematic blocks we have to check
        change, act_commands = (False, [])
        if os.path.isdir(global_config["MAIN_DIR"]):
            for fname in os.listdir(global_config["MAIN_DIR"]):
                full_name = "%s/%s" % (global_config["MAIN_DIR"], fname)
                if fname == ".command":
                    try:
                        act_commands = [
                            s_line for s_line in [
                                line.strip() for line in file(full_name, "r").read().split("\n")
                            ] if not s_line.startswith("#") and s_line
                        ]
                    except:
                        self.log("error reading %s file %s: %s" % (fname, full_name, process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
                        act_commands = []
                    else:
                        act_time = time.localtime()
                        new_name = "%s_%04d%02d%02d_%02d:%02d:%02d" % (fname, act_time[0], act_time[1], act_time[2], act_time[3], act_time[4], act_time[5])
                        self.log("read %s from %s file %s, renaming to %s" % (logging_tools.get_plural("command", len(act_commands)), fname, full_name, new_name))
                        try:
                            os.rename(full_name, "%s/%s" % (global_config["MAIN_DIR"], new_name))
                        except:
                            self.log("error renaming %s to %s: %s" % (fname, new_name, process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
                        else:
                            pass
                elif fname.startswith(".command_"):
                    pass
                elif fname.endswith(".hb"):
                    # ignore heartbeat files
                    pass
                else:
                    fn_dict = dict([(m_block.get_file_name(), m_block) for m_block in self.__check_dict.itervalues()])
                    if not full_name in fn_dict:
                        new_meta_info = process_tools.meta_server_info(full_name)
                        nm_name = new_meta_info.get_name()
                        if nm_name:
                            self.__check_dict[nm_name] = new_meta_info
                            self.log("discovered new meta_info_block for %s (file %s, info: %s)" % (new_meta_info.get_name(), full_name, new_meta_info.get_info()))
                            change = True
                        else:
                            self.log("error reading meta_info_block %s (get_name() returned None)" % (fname),
                                     logging_tools.LOG_LEVEL_ERROR)
                    else:
                        file_time = os.stat(full_name)[stat.ST_MTIME]
                        if file_time > fn_dict[full_name].file_init_time or fname in problem_list:
                            new_meta_info = process_tools.meta_server_info(full_name)
                            nm_name = new_meta_info.get_name()
                            if nm_name:
                                # copy checks_failed info
                                new_meta_info.set_last_pid_check_ok_time(self.__check_dict[nm_name].get_last_pid_check_ok_time())
                                new_meta_info.pid_checks_failed = self.__check_dict[nm_name].pid_checks_failed
                                self.__check_dict[nm_name] = new_meta_info
                                self.log("updated meta_info_block for %s (from file %s, info: %s)" % (new_meta_info.get_name(), full_name, new_meta_info.get_info()))
                                change = True
        del_list = []
        for cname in self.__check_dict.keys():
            full_name = "%s/%s" % (global_config["MAIN_DIR"], cname)
            if not os.path.isfile(full_name):
                self.log("removed meta_info_block for %s (file %s no longer present)" % (cname, full_name))
                del_list.append(cname)
                change = True
        for d_p in del_list:
            del self.__check_dict[d_p]
        if change:
            all_names = sorted(self.__check_dict.keys())
            self.log("%s present: %s" % (logging_tools.get_plural("meta_info_block", len(all_names)), ", ".join(all_names)))
        return act_commands
    def _check(self):
        act_time = time.time()
        if abs(act_time - self.__last_update_time) < global_config["MIN_CHECK_TIME"]:
            self.log("last check only %s ago (%.2f needed), skipping..." % (logging_tools.get_diff_time_str(abs(act_time - self.__last_update_time)),
                                                                            global_config["MIN_CHECK_TIME"]),
                     logging_tools.LOG_LEVEL_WARN)
        else:
            self.__last_update_time = act_time
            act_commands = self._check_for_new_info(self.__problem_list)
            self._do_commands(act_commands)
            del_list = []
            mem_info_dict = {}
            act_pid_list = process_tools.get_process_id_list(True, True)
            act_pid_dict = process_tools.get_proc_list()
            problem_list = []
            for key, struct in self.__check_dict.iteritems():
                struct.check_block(act_pid_list, act_pid_dict)
                if struct.pid_checks_failed or struct.heartbeat_checks_failed:
                    problem_list.append(key)
                    pids_failed_time = abs(struct.get_last_pid_check_ok_time() - act_time)
                    heartbeat_failed_time = abs(struct.get_last_heartbeat_check_ok_time() - act_time)
                    do_sthg_pids = (struct.pid_checks_failed >= 2 and pids_failed_time > global_config["FAILED_CHECK_TIME"])
                    do_sthg_hb = (struct.heartbeat_checks_failed >= 2 and heartbeat_failed_time > global_config["FAILED_CHECK_TIME"])
                    do_sthg = do_sthg_pids or do_sthg_hb
                    if do_sthg_pids:
                        self.log("*** pid check failed for %s: %s" % (key, struct.get_problem_str_pids()),
                                 logging_tools.LOG_LEVEL_WARN)
                    if do_sthg_hb:
                        self.log("*** heartbeat check failed for %s: %s" % (key, struct.get_problem_str_hb()),
                                 logging_tools.LOG_LEVEL_WARN)
                    self.log("*** %s (pid: %d, hb: %d): %s remaining, grace time %s, %s" % (
                        key,
                        struct.pid_checks_failed,
                        struct.heartbeat_checks_failed,
                        logging_tools.get_plural("grace_period", max(0, 2 - max(struct.pid_checks_failed, struct.heartbeat_checks_failed))),
                        logging_tools.get_plural("second", global_config["FAILED_CHECK_TIME"] - max(pids_failed_time, heartbeat_failed_time)),
                        do_sthg and "starting countermeasures" or "still waiting..."),
                             logging_tools.LOG_LEVEL_WARN)
                    if do_sthg:
                        # first submit the at-commands
                        if struct.stop_command:
                            self._submit_at_command(struct.stop_command, 1)
                        if struct.start_command:
                            self._submit_at_command(struct.start_command, 2)
                        self.__new_mail.init_text()
                        self.__new_mail.set_subject("problem with %s on %s (meta-server)" % (key, global_config["SERVER_FULL_NAME"]))
                        self.__new_mail.append_text(["check failed for %s: %s, %s" % (
                            key,
                            struct.get_problem_str_pids() if do_sthg_pids else "pids OK",
                            struct.get_problem_str_hb() if do_sthg_hb else "HB ok"),
                                                     "starting repair sequence",
                                                     ""])
                        self.log("*** starting repair sequence",
                             logging_tools.LOG_LEVEL_WARN)
                        if struct.kill_pids:
                            kill_info = struct.kill_all_found_pids()
                            self.log("  *** kill info: %s" % (kill_info),
                                     logging_tools.LOG_LEVEL_WARN)
                            self.__new_mail.append_text(["trying to kill the remaining pids, kill info : %s" % (kill_info),
                                                         ""])
                        if struct.stop_command:
                            self.__new_mail.append_text(["issued the stop command : %s" % (struct.stop_command),
                                                         ""])
                        if struct.start_command:
                            self.__new_mail.append_text(["issued the start command : %s" % (struct.start_command),
                                                         ""])
                        struct.remove_meta_block()
                        _sm_stat, log_lines = self.__new_mail.send_mail()
                        for line in log_lines:
                            self.log(line)
                        del_list.append(key)
                else:
                    # check memory consumption if everything is ok
                    if struct.check_memory:
                        pids = struct.get_unique_pids()
                        if pids:
                            # only count memory for one pid
                            mem_info_dict[key] = sum([process_tools.get_mem_info(cur_pid) for cur_pid in pids])
                        else:
                            mem_info_dict[key] = 0
            if mem_info_dict:
                self.__act_meminfo_line += 1
                act_meminfo_keys = sorted(mem_info_dict.keys())
                if act_meminfo_keys != self.__last_meminfo_keys or self.__act_meminfo_line > 100:
                    self.__act_meminfo_line = 0
                    self.__last_meminfo_keys = act_meminfo_keys
                    self.log("Memory info mapping: %s" % (", ".join(["%d: %s" % (act_meminfo_keys.index(k) + 1, k) for k in act_meminfo_keys])))
                self.log("Memory info: %s" % (" / ".join([process_tools.beautify_mem_info(mem_info_dict[k], 1) for k in act_meminfo_keys])))

            if del_list:
                del_list.sort()
                self.log("removed %s: %s" % (logging_tools.get_plural("block", len(del_list)), ", ".join(del_list)))
                for d_p in del_list:
                    del self.__check_dict[d_p]
    def loop_post(self):
        self.network_socket.close()
        self.__log_template.close()
