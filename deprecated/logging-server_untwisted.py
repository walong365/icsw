#!/usr/bin/python-init -Ot
# -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008 Andreas Lang-Nevyjel (lang-nevyjel@init.at)
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of logging-server
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
""" logging server """

import sys
import os
import pwd
import grp
import re
import time
import logging_tools
import net_logging_tools
import mail_tools
import process_tools
import net_tools
import threading_tools
import socket
import configfile
import getopt
import marshal
import cPickle
import stat
import struct
import logging
import logging.config
import logging.handlers
import logging_server_version
import server_command

SEP_STR = "-" * 50

class tcp_recv_obj(net_tools.buffer_object):
    def __init__(self, src, log_queue):
        self.__log_queue = log_queue
        net_tools.buffer_object.__init__(self)
    def add_to_in_buffer(self, what):
        #print "Got", what
        self.__log_queue.put(("log_tcp", what))
        self.add_to_out_buffer(net_tools.add_proto_1_header("ok", True))
    def out_buffer_sent(self, send_len):
        if send_len == len(self.out_buffer):
            #self.socket.send_done()
            self.close()
            self.__log_queue = None
    def __del__(self):
        pass
            
class simple_con(net_tools.buffer_object):
    def __init__(self, mode, fw_id, s_str, d_queue):
        self.__mode = mode
        self.__fw_id = fw_id
        self.__send_str = s_str
        self.__d_queue = d_queue
        net_tools.buffer_object.__init__(self)
    def setup_done(self):
        if self.__mode == "udp":
            self.add_to_out_buffer(self.__send_str)
        else:
            self.add_to_out_buffer(net_tools.add_proto_1_header(self.__send_str, True))
    def out_buffer_sent(self, send_len):
        if send_len == len(self.out_buffer):
            self.out_buffer = ""
            self.socket.send_done()
            if self.__mode == "udp":
                self.__d_queue.put(("send_ok", (self.__fw_id, "udp_send")))
                self.delete()
        else:
            self.out_buffer = self.out_buffer[send_len:]
    def add_to_in_buffer(self, what):
        self.__d_queue.put(("send_ok", (self.__fw_id, "got %s" % (what))))
        self.delete()
    def report_problem(self, flag, what):
        self.__d_queue.put(("send_error", (self.__fw_id, "%s: %s" % (net_tools.net_flag_to_str(flag),
                                                                     what))))
        self.delete()

class error_gather_thread(threading_tools.thread_obj):
    def __init__(self, log_queue, glob_config):
        # config
        self.__glob_config = glob_config
        self.__log_queue = log_queue
        self.__logger = logging_tools.get_logger("thread.eg", "threadqueue", target_queue=self.__log_queue, pre_tuple="int_log")
        threading_tools.thread_obj.__init__(self, "error_gather", queue_size=10)
        self.__ll_re1 = re.compile("^(?P<pid>\d+)\|(?P<ppid>\d+)\|(?P<uid>\d+)\|(?P<gid>\d+)\|(?P<name>\S+)\|(?P<state>\S+)\|(?P<str>.*)$",
                                   re.MULTILINE | re.DOTALL)
        self.__ll_re2 = re.compile("^(?P<pid>\d+):(?P<str>.*)$",
                                   re.MULTILINE | re.DOTALL)
    def thread_running(self):
        self.send_pool_message(("new_pid", self.pid))
        self.__proc_dict = {}
        if self.__glob_config["TRACE_PROC"]:
            self.get_proc_dict()
        if self.__glob_config["SEND_INITIAL_MAIL"]:
            self.log("Sending initial message")
            self._send_mail("logging_server test from %s@%s" % (self.__glob_config["LONG_HOST_NAME"], process_tools.get_cluster_name()),
                            "Initial mail after start from %s" % (self.__glob_config["LONG_HOST_NAME"]))
        self.__eg_dict = {}
        self.register_func("update", self._update)
        self.register_func("err_uds", self._err_uds)
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK, dst="log"):
        if dst != "log":
            print "********", what, lev
        self.__logger.log(lev, what, extra={"handle" : dst})
    def get_proc_dict(self, timeout=300):
        #pdict = {}
        s_fields = ["name", "state"]
        i_fields = ["pid", "uid", "gid", "ppid"]
        set_pids = []
        act_time = time.time()
        for pid in [x for x in os.listdir("/proc") if x.isdigit()]:
            ipid = int(pid)
            try:
                stat_lines = [(x.split() + ["", ""])[0:2] for x in file("/proc/%d/status" % (ipid), "r").read().split("\n")]
            except:
                pass
            else:
                t_dict = {"set" : act_time}
                for what, rest in stat_lines:
                    r_what = what.lower()[:-1]
                    if r_what in s_fields:
                        t_dict[r_what] = rest
                    elif r_what in i_fields:
                        t_dict[r_what] = int(rest)
                if t_dict["pid"] == ipid:
                    set_pids.append(ipid)
                    self.__proc_dict[ipid] = t_dict
        del_pids = [k for k, v in self.__proc_dict.iteritems() if abs(act_time - v["set"]) > timeout]
        for dp in del_pids:
            del self.__proc_dict[dp]
    def receive_any_message(self):
        if self.__glob_config["TRACE_PROC"]:
            self.get_proc_dict()
    def loop_end(self):
        self._check_error_dict(True)
    def _err_uds(self, in_str):
        if in_str[0:8].isdigit():
            if int(in_str[1:8]) == len(in_str) - 8:
                in_str = in_str[8:]
            else:
                self.log("Error in proto_V1 in_str '%s', interpreting as proto_V0" % (in_str), logging_tools.LOG_LEVEL_ERROR)
        if in_str:
            ls_m1 = self.__ll_re1.match(in_str)
            ls_m2 = self.__ll_re2.match(in_str)
            if ls_m1:
                pid = int(ls_m1.group("pid"))
                log_str = ls_m1.group("str")
                uid, gid = (int(ls_m1.group("uid")), int(ls_m1.group("gid")))
                try:
                    uname = pwd.getpwuid(uid)[0]
                except:
                    uname = "<unknown>"
                try:
                    gname = grp.getgrgid(gid)[0]
                except:
                    gname = "<unknown>"
                pid_str = "%s (uid %d [%s], gid %d [%s])" % (ls_m1.group("name"), uid, uname, gid, gname)
            elif ls_m2:
                pid = int(ls_m2.group("pid"))
                log_str = ls_m2.group("str")
                if pid in self.__proc_dict:
                    try:
                        uname = pwd.getpwuid(self.__proc_dict[pid]["uid"])[0]
                    except:
                        uname = "<unknown>"
                    try:
                        gname = grp.getgrgid(self.__proc_dict[pid]["gid"])[0]
                    except:
                        gname = "<unknown>"
                    pid_str = "%s (uid %d [%s], gid %d [%s])" % (self.__proc_dict[pid]["name"], self.__proc_dict[pid]["uid"], uname, self.__proc_dict[pid]["gid"], gname)
                else:
                    pid_str = "unknown"
            else:
                pid_str, log_str = ("unknown", in_str)
            for str_p in log_str.split("\n"):
                self.log("from pid %d (%s): %s" % (pid, pid_str, str_p), logging_tools.LOG_LEVEL_ERROR, "err_py")
            if not pid in self.__eg_dict:
                self.__eg_dict[pid] = {"last_update" : time.time(),
                                       "strings"     : [],
                                       "proc_info"   : pid_str}
            self.__eg_dict[pid]["last_update"] = time.time()
            self.__eg_dict[pid]["strings"].extend(log_str.split("\n"))
    def _update(self):
        self._check_error_dict()
        self.send_pool_message("eg_update_ok")
    def _check_error_dict(self, force=False):
        c_name = process_tools.get_cluster_name()
        mails_sent = 0
        s_time = time.time()
        ep_dels = []
        for ep, es in self.__eg_dict.iteritems():
            t_diff = s_time - es["last_update"]
            if force or (t_diff < 0 or t_diff > 60):
                subject = "Python error for pid %d on %s@%s" % (ep, self.__glob_config["LONG_HOST_NAME"], c_name)
                msg_body = "\n".join(["Processinfo %s" % (es["proc_info"])] +
                                     ["%3d %s" % (x[0] + 1, x[1]) for x in zip(range(len(es["strings"])),
                                                                               es["strings"])])
                self._send_mail(subject, msg_body)
                mails_sent += 1
                ep_dels.append(ep)
        for epd in ep_dels:
            del self.__eg_dict[epd]
        e_time = time.time()
        if mails_sent:
            self.log("Sent %s in %.2f seconds" % (logging_tools.get_plural("mail", mails_sent),
                                                  e_time - s_time))
    def _send_mail(self, subject, msg_body):
        new_mail = mail_tools.mail(subject,
                                   "%s@%s" % (self.__glob_config["FROM_NAME"], self.__glob_config["FROM_ADDR"]),
                                   self.__glob_config["TO_ADDR"],
                                   msg_body)
        new_mail.set_server(self.__glob_config["MAILSERVER"],
                            self.__glob_config["MAILSERVER"])
        try:
            send_stat, log_lines = new_mail.send_mail()
            for log_line in log_lines:
                self.log(" - (%d) %s" % (send_stat, log_line),
                         logging_tools.LOG_LEVEL_OK)
        except:
            self.log("error sending mail: %s" % (process_tools.get_except_info()),
                     logging_tools.LOG_LEVEL_CRITICAL)
        
class tail_object(object):
    def __init__(self, log_queue, follow_queue, glob_config, idx, to_id, name, timeout, target_host, target_port, con_mode):
        self.__to_id = to_id
        self.__idx = idx
        self.__glob_config = glob_config
        self.log_queue = log_queue
        self.__logger = logging_tools.get_logger("thread.to", "threadqueue", target_queue=self.log_queue, pre_tuple="int_log")
        self.__follow_queue = follow_queue
        self.name = name
        if timeout.isdigit():
            self.__timeout = int(timeout)
        else:
            raise ValueError, "timeout '%s' is not an integer" % (timeout)
        if target_port.isdigit():
            self.__target_port = int(target_port)
        else:
            raise ValueError, "targetport '%s' is not an integer" % (target_port)
        self.__target_host = target_host
        self.__fd = None
        self.log("initialised, file %s, target %s (port %d), check every %s" % (self.name,
                                                                                self.__target_host,
                                                                                self.__target_port,
                                                                                logging_tools.get_plural("second" ,self.__timeout)))
        self.set_con_mode(con_mode)
        self.send_id = 0
        #self.send_dict, self.send_num = ({}, {})
        self.__last_read = None
        self.__line_send_counter, self.__line_send_bytes = (0, 0)
        # line cache
        self.__line_cache = []
        # send object
    def get_id(self):
        return "%s.%d" % (self.__to_id, self.__idx)
    def set_con_mode(self, cm):
        self.__con_mode = cm
        if self.__con_mode == "tcp":
            self.log("  connection mode set to %s -> multi-line transfers" % (self.__con_mode))
        else:
            self.log("  connection mode set to %s -> single-line transfers" % (self.__con_mode))
    def set_reopen_counter(self, roc):
        self.initial_reopen_counter = roc
        self.reopen_count = roc
        self.log("  reopen_counter is set to %d" % (self.reopen_count))
    def reinit_roc(self):
        if not self.reopen_count:
            self.reopen_count = self.initial_reopen_counter
            self.log("Re-initialising reopen_counter to %d" % (self.reopen_count))
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__logger.log(lev, "tail_object %s.%d: %s" % (self.__to_id, self.__idx, what))
    def my_open(self, reopen=0):
        success, log_str = (False, "")
        if os.path.isfile(self.name):
            try:
                self.__fd = file(self.name, "r")
            except:
                log_str = "Error opening file %s: %s, insufficient rights?" % (self.name,
                                                                               process_tools.get_except_info())
                self.__fd = None
                self.reopen_count = 0
            else:
                success = True
                self.__fd.seek(0, 2)
                self.where = self.__fd.tell()
                self.log("seeking to the end of the file (position %d) ..." % (self.where))
        else:
            log_str = "No such file"
        return success, log_str
    def read_lines(self, net_server):
        act_time = time.time()
        if not self.__last_read or abs(self.__last_read - act_time) >= self.__timeout:
            self.__last_read = act_time
            self.__read_lines2(net_server)
        if self.reopen_count or self.__fd:
            return abs(self.__last_read + self.__timeout - act_time)
        else:
            return None
    def __read_lines2(self, net_server):
        # returns timeout
        line_cache = []
        if self.__fd:
            while True:
                if self.__fd:
                    try:
                        line = self.__fd.readline().rstrip()
                    except IOError, what:
                        self.log("an IOError occured: %s" % (str(what)))
                        break
                    else:
                        if not line:
                            fd_results = os.fstat(self.__fd.fileno())
                            try:
                                st_results = os.stat(self.name)
                            except OSError:
                                self.log("*** File Missing ?")
                                st_results = fd_results
                            if st_results.st_ino == fd_results.st_ino:
                                break
                            else:
                                self.log("changed inode numbers from %d to %d" % (fd_results.st_ino, st_results.st_ino))
                                self.__fd = None
                                self.reinit_roc()
                        else:
                            line_cache.append(line)
                            if self.__glob_config["LOG_LINES"]:
                                self.log("Got line : %s" % (line))
                else:
                    self.log("self.__fd is None")
                    break
        if not self.__fd and self.reopen_count:
            open_ok, open_err_str = self.my_open(reopen = 1)
            if not open_ok:
                self.reopen_count -= 1
                self.log("open failed: %s, (reopen_counter is %3d of %3d)" % (open_err_str,
                                                                              self.reopen_count,
                                                                              self.initial_reopen_counter),
                         logging_tools.LOG_LEVEL_ERROR)
                if self.reopen_count < 1 and not self.__fd:
                    self.reopen_count = 0
                    self.log("reopen-counter is zero, disabling further open() attempts...")
        if line_cache:
            self.add_line_cache(line_cache, net_server)
        return self.__timeout
    def _send_call(self, args):
        return simple_con(self.__con_mode, self.get_id(), args.get_add_data(), self.__follow_queue)
    def _con_state_call(self, **args):
        if args["state"] == "error":
            self.log("error connecting to host %s (port %d)" % (args["host"], args["port"]),
                     logging_tools.LOG_LEVEL_ERROR)
    def add_line_cache(self, lc, ns):
        self.__line_cache.extend(lc)
        self.check_for_send(ns)
    def check_for_send(self, ns):
        if self.__line_cache:
            self.send_line_cache(ns)
    def send_line_cache(self, ns):
        self.send_id += 1
        if self.__con_mode == "tcp":
            ns.add_object(net_tools.tcp_con_object(self._send_call,
                                                   bind_retries=1,
                                                   rebind_wait_time=1,
                                                   connect_state_call = self._con_state_call,
                                                   target_host = self.__target_host,
                                                   target_port = self.__target_port,
                                                   add_data = self.get_send_str()))
        else:
            ns.add_object(net_tools.udp_con_object(self._send_call,
                                                   bind_retries=1,
                                                   rebind_wait_time=1,
                                                   connect_state_call = self._con_state_call,
                                                   target_host = self.__target_host,
                                                   target_port = self.__target_port,
                                                   add_data = self.get_send_str()))
        if self.__line_send_counter >= self.__glob_config["LOG_SEND_COUNTER"]:
            self.log("Sent %s (%s) to %s (port %d, mode %s)" % (logging_tools.get_plural("line", self.__line_send_counter),
                                                                logging_tools.get_plural("byte", self.__line_send_bytes),
                                                                self.__target_host,
                                                                self.__target_port,
                                                                self.__con_mode))
            self.__line_send_counter, self.__line_send_bytes = (0, 0)
    def get_send_str(self):
        if self.__con_mode == "tcp":
            send_lines = self.__line_cache
            self.__line_cache = []
        else:
            send_lines = [self.__line_cache.pop(0)]
        self.__line_send_counter += len(send_lines)
        self.__line_send_bytes += sum([len(line) for line in send_lines])
        send_str = server_command.sys_to_net({"host"    : self.__glob_config["SHORT_HOST_NAME"],
                                              "id"      : self.get_id(),
                                              "content" : send_lines})
        return send_str
    def close(self):
        if self.__fd:
            self.log("Closing...")
            self.__fd.close()
    def __del__(self):
        self.close()

class tail_follow_thread(threading_tools.thread_obj):
    def __init__(self, log_queue, ns, glob_config):
        # config
        self.__glob_config = glob_config
        self.__log_queue = log_queue
        self.__net_server = ns
        self.__logger = logging_tools.get_logger("thread.tf", "threadqueue", target_queue=self.__log_queue, pre_tuple="int_log")
        threading_tools.thread_obj.__init__(self, "tail_follow", queue_size = 100)
        self.register_func("update", self._update)
        self.register_func("send_ok", self._send_ok)
        self.register_func("send_error", self._send_error)
    def thread_running(self):
        self.send_pool_message(("new_pid", self.pid))
        self.set_min_loop_time(1)
        self.__read_time, self.__tail_dict, self.__run_idx = (None, {}, 0)
    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        self.__logger.log(level, what)
    def _send_ok(self, (f_id, in_str)):
        # send for f_id ok
        if f_id in self.__tail_dict:
            #print "SEND", f_id
            self.__tail_dict[f_id].check_for_send(self.__net_server)
    def _send_error(self, (f_id, in_str)):
        self.log("Error in sending for %s: %s" % (f_id, in_str),
                 logging_tools.LOG_LEVEL_ERROR)
    def _update(self):
        if os.path.isfile(self.__glob_config["TAIL_FILE_NAME"]):
            parse_file = True
            if self.__read_time:
                if os.stat(self.__glob_config["TAIL_FILE_NAME"])[stat.ST_CTIME] > self.__read_time:
                    self.log("tail_file '%s' changed, discarding old %s" % (self.__glob_config["TAIL_FILE_NAME"],
                                                                            logging_tools.get_plural("tail object",
                                                                                                     len(self.__tail_dict.keys()))),
                             logging_tools.LOG_LEVEL_WARN)
                    for key, value in self.__tail_dict.iteritems():
                        value.close()
                        del value
                    self.__tail_dict = {}
                else:
                    parse_file = False
            if parse_file:
                self.__read_time = time.time()
                try:
                    tail_lines = [x.strip() for x in file(self.__glob_config["TAIL_FILE_NAME"], "r").read().rstrip().split("\n") if not x.startswith("#")]
                except:
                    self.log("Cannot read tail-file %s (%s)" % (self.__glob_config["TAIL_FILE_NAME"], process_tools.get_except_info()),
                             logging_tools.LOG_LEVEL_ERROR)
                else:
                    for line, lnum in zip(tail_lines, xrange(1, len(tail_lines)+1)):
                        r_line = line.strip()
                        if not r_line.startswith("#") and r_line.count(":") == 5:
                            self.__run_idx += 1
                            try:
                                new_to = tail_object(self.__log_queue, self.get_thread_queue(), self.__glob_config, self.__run_idx, *r_line.split(":"))
                                new_to.set_reopen_counter(self.__glob_config["REOPEN_COUNT"])
                            except:
                                self.log("error parsing line %d (%s): %s" % (lnum,
                                                                             r_line,
                                                                             process_tools.get_except_info()),
                                         logging_tools.LOG_LEVEL_ERROR)
                            else:
                                self.__tail_dict[new_to.get_id()] = new_to
                        else:
                            self.log("wrong syntax in tail_file in line %d" % (lnum),
                                     logging_tools.LOG_LEVEL_WARN)
                    self.log("found %s%s" % (logging_tools.get_plural("tail_object",
                                                                      len(self.__tail_dict.keys())),
                                             ": %s" % (", ".join(self.__tail_dict.keys())) if self.__tail_dict else ""))
        else:
            if not self.__read_time:
                self.log("No tail-file %s found" % (self.__glob_config["TAIL_FILE_NAME"]), logging_tools.LOG_LEVEL_WARN)
    def loop_start(self):
        self._update()
        for t_name, t_stuff in self.__tail_dict.iteritems():
            open_ok, open_err_str = t_stuff.my_open()
            if not open_ok:
                t_stuff.log(open_err_str)
        self.__last_rroc_time = time.time()
    def any_message_received(self):
        act_time = time.time()
        if abs(act_time - self.__last_rroc_time) > 3600:
            self.__last_rroc_time = act_time
            for t_name, t_stuff in self.__tail_dict.iteritems():
                t_stuff.reinit_roc()
        self.set_min_loop_time(min([10] + [z for z in [y.read_lines(self.__net_server) for x, y in self.__tail_dict.iteritems()] if z != None]))

class logging_thread(threading_tools.thread_obj):
    def __init__(self, glob_config):
        # config
        self.__glob_config = glob_config
        # handles
        self.__handles, self.__log_buffer = ({}, [])
        threading_tools.thread_obj.__init__(self, "log", queue_size=100, priority=10)
        # statistics
        self.__num_write, self.__num_close, self.__num_open = (0, 0, 0)
        self.register_func("int_log", self._int_log)
        self.register_func("log_uds", self._log_uds)
        self.register_func("log_udp", self._log_uds)
        self.register_func("log_tcp", self._log_uds)
        self.register_func("update" , self._update)
        if not os.path.isdir(self.__glob_config["LOG_DESTINATION"]):
            try:
                os.makedirs(self.__glob_config["LOG_DESTINATION"])
            except:
                dname = "/tmp"
        init_log_lines = ["logging_thread %s is now awake (pid %d)" % (self.name, self.pid)]
        # internal log sources
        int_names = ["log", "log_py", "err_py"]
        for name in int_names:
            handle, log_lines = self.get_python_handle(name)
            init_log_lines.extend(log_lines)
        # input cache
        self._init_input_cache()
        init_log_lines.append("opened handles for %s" % (", ".join(self.__handles.keys())))
        self.write_log_lines(init_log_lines)
        self.__last_stat_time = None
    def thread_running(self):
        self.send_pool_message(("new_pid", self.pid))
    def _init_input_cache(self):
        self.__in_cache = ""
    def _update(self):
        c_handles = sorted([key for key, value in self.__handles.iteritems() if isinstance(value, logging_tools.logfile) and value.check_for_temp_close()])
        if c_handles:
            self.log("temporarily closing %s: %s" % (logging_tools.get_plural("handle", len(c_handles)),
                                                     ", ".join(c_handles)))
        # check for close
        c_handles = []
        for key in self.__handles.iterkeys():
            if not os.path.isdir("/proc/%d" % (self.__handles[key].process_id)):
                c_handles.append(key)
        for c_handle in c_handles:
            self.remove_handle(c_handle)
    def any_message_received(self):
        act_time = time.time()
        if not self.__last_stat_time or abs(act_time - self.__last_stat_time) > self.__glob_config["STATISTICS_TIMER"]:
            self.__last_stat_time = act_time
            self.__num_write += 1
            self.log("logstat (open/close/written): %d / %d / %d, mem_used is %s" % (self.__num_open,
                                                                                     self.__num_close,
                                                                                     self.__num_write,
                                                                                     process_tools.beautify_mem_info()))
            self.__num_open, self.__num_close, self.__num_write = (0, 0, 0)
    def log(self, what, level=logging_tools.LOG_LEVEL_OK, dst="log"):
        if dst in self.__handles:
            self.__handles[dst].log(level, what)
    def _log_uds(self, in_str):
        num_lines = 0
        decode = True
        while decode:
            decode = False
            # iterate until as much as possible is decoded
            if in_str[0:8].isdigit():
                if int(in_str[1:8]) == len(in_str) - 8:
                    in_str = in_str[8:]
                else:
                    self.log("Error in proto_V1 in_str '%s', interpreting as proto_V0" % (in_str), logging_tools.LOG_LEVEL_ERROR)
            try:
                log_com, in_str, python_log_com = self.decode_in_str(in_str)
            except:
                self.log("error reconstructing log-command (len of in_str: %d): %s" % (len(in_str),
                                                                                       process_tools.get_except_info()),
                         logging_tools.LOG_LEVEL_ERROR)
                self._init_input_cache()
            else:
                if log_com:
                    self._init_input_cache()
                    if not python_log_com:
                        new_log_com = logging.LogRecord(log_com.get_name(with_sub_names=1),
                                                        logging_tools.map_old_to_new_level(log_com.get_log_level()),
                                                        "not set",
                                                        1,
                                                        log_com.get_log_str(),
                                                        (),
                                                        None)
                        new_log_com.host = log_com.get_host()
                        new_log_com.threadName = log_com.get_thread()
                        log_com.close()
                        del log_com
                        log_com = new_log_com
                        python_log_com = True
                    handle, log_lines = self.get_python_handle(log_com)
                    if log_lines:
                        self.write_log_lines(log_lines)
                    log_msg = log_com.msg
                    is_command = False
                    if type(log_msg) == type(""):
                        if log_msg.lower().startswith("<lch>") and log_msg.lower().endswith("</lch>"):
                            is_command = True
                            log_com = log_msg[5:-6]
                            if log_com == "CLOSE":
                                self.remove_handle(handle.handle_name)
                            elif log_com.startswith("set_file_size"):
                                try:
                                    file_size = int(log_com.split()[1])
                                except:
                                    pass
                                else:
                                    for f_handle in handle.handlers:
                                        if hasattr(f_handle, "set_max_bytes"):
                                            f_handle.set_max_bytes(file_size)
                    if not is_command or (is_command and self.__glob_config["LOG_COMMANDS"]):
                        try:
                            handle.handle(log_com)
                        except:
                            self.log("error handling log_com '%s'" % (str(log_com)),
                                     logging_tools.LOG_LEVEL_ERROR)
                        else:
                            num_lines += 1
                    del log_com
                    if in_str:
                        decode = True
                else:
                    self.log("error reconstructing log-command (len of in_str: %d): no log_com (possibly very long log_str)" % (len(in_str)),
                             logging_tools.LOG_LEVEL_ERROR)
                    self.__in_cache = in_str
        if num_lines > 1:
            self.log("received multi-line with %s" % (logging_tools.get_plural("line", num_lines)))
    def decode_in_str(self, in_str):
        python_log_com = False
        if self.__in_cache:
            in_str = "%s%s" % (self.__in_cache, in_str)
        if in_str.startswith("bpd"):
            bpd_vers = int(in_str[3])
            if bpd_vers == 1:
                pre_offset = 32
                pre_stuff = list(struct.unpack("=6if", in_str[4:pre_offset]))
            elif bpd_vers == 2:
                pre_offset = 36
                pre_stuff = list(struct.unpack("=6id", in_str[4:pre_offset]))
            elif bpd_vers == 3:
                pre_offset = 40
                pre_stuff = list(struct.unpack("=7id", in_str[4:pre_offset]))
            else:
                raise ValueError, "unknown bpd_version %d" % (bpd_vers)
            log_lev = pre_stuff.pop(0)
            log_time = pre_stuff.pop(-1)
            f_str = "".join("%ds" % (x) for x in pre_stuff)
            needed_len  = sum(pre_stuff)
            available_len = len(in_str) - pre_offset
            if needed_len > available_len:
                self.log("more data needed (%d < %d)" % (available_len,
                                                         needed_len),
                         logging_tools.LOG_LEVEL_WARN)
                log_com, ret_str = (None, in_str)
            else:
                if bpd_vers == 2:
                    log_name, log_command, log_host, log_thread, log_str = struct.unpack(f_str, in_str[pre_offset : pre_offset + sum(pre_stuff)])
                    log_com = net_logging_tools.log_command(log_name, log_command, log_str, log_lev, log_host, log_time, log_thread, tasklet="")
                else:
                    log_name, log_command, log_host, log_thread, log_tasklet, log_str = struct.unpack(f_str, in_str[pre_offset : pre_offset + sum(pre_stuff)])
                    log_com = net_logging_tools.log_command(log_name, log_command, log_str, log_lev, log_host, log_time, log_thread, tasklet=log_tasklet)
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
                try:
                    # try to interpert as logRecord
                    log_com = logging.makeLogRecord(in_dict)
                except:
                    # failure, try log_com
                    log_com = net_logging_tools.log_command(in_dict.get("name", "unknown_name"),
                                                            log_str=in_dict["log_str"],
                                                            level  =in_dict.get("log_level", logging_tools.LOG_LEVEL_OK),
                                                            host   =in_dict.get("host", "unknown_host"),
                                                            thread =in_dict.get("thread", "unknown_thread"))
                else:
                    python_log_com = True
                ret_str = ""
            else:
                raise ValueError, "Unable to dePickle or deMarshal string"
        return log_com, ret_str, python_log_com
    def _int_log(self, args):
        if type(args) == type(()):
            print "****"
            t_name, what, level, h_name = args
            if self.__handles:
                if self.__log_buffer:
                    for t_n, what_inner, log_lev in self.__log_buffer:
                        self.__num_write += 1
                        self.__handles[h_name].log(log_lev, what_inner)
                        #self.__handles[h_name].write("%-6s(%s) (delayed) %s" % (logging_tools.get_log_level_str(log_lev), t_n, what_inner))
                    self.__log_buffer = []
                self.__num_write += 1
                print "+", h_name
                self.__handles[h_name].log(level, what)
                #self.__handles[h_name].write("%-6s(%s) %s" % (logging_tools.get_log_level_str(level), t_name, what))
            else:
                self.__log_buffer.append((t_name, what, level))
        else:
            if self.__handles:
                while self.__log_buffer:
                    act_rec = self.__log_buffer.pop(0)
                    if hasattr(act_rec, "handle"):
                        t_handle = act_rec.handle
                    else:
                        t_handle = "log"
                    self.__handles[t_handle].handle(last_rec)
                if hasattr(args, "handle"):
                    t_handle = args.handle
                else:
                    t_handle = "log"
                self.__handles[t_handle].handle(args)
            else:
                self.__log_buffer.append(record)
    def remove_handle(self, h_name):
        self.log("closing handle %s" % (h_name))
        self.__num_close += 1
        handle = self.__handles[h_name]
        if isinstance(handle, logging.Logger):
            handle.info("closed %s by pid %d" % (h_name, self.pid))
            for sub_h in handle.handlers:
                handle.removeHandler(sub_h)
                sub_h.close()
        else:
            handle.write("closed %s by pid %d" % (h_name, self.pid))
            handle.close()
        del self.__handles[h_name]
    def write_log_lines(self, l_lines):
        for log_line in l_lines:
            self.log(log_line)
    #def get_handle(self, h_name):
        #log_strs = []
        #if not self.__handles.has_key(h_name):
            #full_name = "%s/%s" % (self.__glob_config["LOG_DESTINATION"], h_name)
            #base_dir, base_name = (os.path.dirname(full_name),
                                   #os.path.basename(full_name))
            #log_strs.append("attempting to create log_file '%s' in dir '%s'" % (base_name, base_dir))
            ## iterate until base_dir could be created
            #while 1:
                #if os.path.isfile(base_dir) and not os.path.isfile("%s.d" % (base_dir)):
                    #base_dir = "%s.d" % (base_dir)
                    #full_name = "%s/%s" % (base_dir, base_name)
                #if not os.path.isdir(base_dir):
                    #try:
                        #os.makedirs(base_dir)
                    #except OSError:
                        #log_strs.append("cannot create directory %s (basename %s): %s" % (base_dir,
                                                                                          #base_name,
                                                                                          #process_tools.get_except_info()))
                        #base_dir = "/".join(base_dir.split("/")[0:-1])
                        #full_name = "%s/%s" % (base_dir, base_name)
                    #else:
                        #log_strs.append("created directory %s (basename %s)" % (base_dir,
                                                                                #obase_name))
                        #break
                #else:
                    #break
            ##logging.config.fileConfig("logging.conf", {"file_name" : full_name})
            #print h_name
            #logger = logging.getLogger(h_name)
            ##print logging.root.manager.loggerDict.keys()
            ##print dir(base_logger)
            ##print "***", logger_name, base_logger, logger
            #form = logging.Formatter(self.__glob_config["LOG_FORMAT"],
                                     #self.__glob_config["DATE_FORMAT"])
            #logger.setLevel(logging.DEBUG)
            #new_h = logging_tools.new_logfile(full_name, maxBytes=1000000)
            #new_h.setFormatter(form)
            #logger.addHandler(new_h)
            #logger.process_id = 1
            #new_h = logger
            ##new_h = logging_tools.logfile(full_name)
            #self.__num_open += 1
            #new_h.info(SEP_STR)#, header=0)
            #new_h.info("opened %s (file %s in %s) by pid %d" % (full_name, base_name, base_dir, self.pid))
            #self.__handles[h_name] = new_h
            #log_strs.append("added handle %s (file %s in dir %s), total open: %s" % (h_name,
                                                                                     #base_name,
                                                                                     #base_dir,
                                                                                     #logging_tools.get_plural("handle", len(self.__handles.keys()))))
        #return self.__handles[h_name], log_strs
    def get_python_handle(self, record):
        log_strs = []
        if type(record) == type(""):
            # special type for direct handles (log, log_py, err_py)
            sub_dirs = []
            record_name, record_process = ("init.at.%s" % (record),
                                           os.getpid())
        else:
            if not hasattr(record, "host"):
                # no host set: use local machine name
                record.host = process_tools.get_machine_name()
            sub_dirs = [record.host]
            record_name, record_process = (record.name,
                                           record.process)
        init_logger = record_name.startswith("init.at.")
        if init_logger:
            # init.at logger, create subdirectories
            logger_name = record_name
            # generate list of dirs and file_name
            scr1_name = record_name[8:].replace("\.", "#").replace(".", "/").replace("#", ".")
            for path_part in os.path.dirname(scr1_name).split(os.path.sep):
                if path_part:
                    if sub_dirs:
                        sub_dirs.append("%s/%s.d" % (sub_dirs[-1], path_part))
                    else:
                        sub_dirs.append("%s.d" % (path_part))
            if sub_dirs:
                h_name = "%s/%s" % (sub_dirs[-1], os.path.basename(scr1_name))
            else:
                h_name = os.path.basename(scr1_name)
        else:
            logger_name = record_name
            h_name = "%s/%s" % (record.host, record_name)
        if h_name in self.__handles:
            if record_process != self.__handles[h_name].process_id:
                self.remove_handle(h_name)
        if not h_name in self.__handles:
            log_strs.append("logger '%s' (logger_type %s) requested" % (record_name,
                                                                        "init.at" if init_logger else "native"))
            full_name = "%s/%s" % (self.__glob_config["LOG_DESTINATION"], h_name)
            base_dir, base_name = (os.path.dirname(full_name),
                                   os.path.basename(full_name))
            log_strs.append("attempting to create log_file '%s' in dir '%s'" % (base_name, base_dir))
            # add new sub_dirs
            sub_dirs = []
            for new_sub_dir in os.path.dirname(h_name).split("/"):
                if not sub_dirs:
                    sub_dirs.append(new_sub_dir)
                else:
                    sub_dirs.append("%s/%s" % (sub_dirs[-1], new_sub_dir))
            # create sub_dirs
            for sub_dir in sub_dirs:
                act_dir = "%s/%s" % (self.__glob_config["LOG_DESTINATION"], sub_dir)
                if not os.path.isdir(act_dir):
                    try:
                        os.makedirs(act_dir)
                    except OSError:
                        log_strs.append("cannot create directory %s: %s" % (act_dir,
                                                                            process_tools.get_except_info()))
                    else:
                        log_strs.append("created directory %s" % (act_dir))
            # init logging config
            #logging.config.fileConfig("logging.conf", {"file_name" : full_name})
            #base_logger = logging.getLogger("init.at")
            logger = logging.getLogger(logger_name)
            logger.propagate = 0
            #print logging.root.manager.loggerDict.keys()
            #print dir(base_logger)
            #print "***", logger_name, base_logger, logger
            form = logging.Formatter(self.__glob_config["LOG_FORMAT"],
                                     self.__glob_config["DATE_FORMAT"])
            logger.setLevel(logging.DEBUG)
            new_h = logging_tools.new_logfile(full_name, maxBytes=1000000)
            new_h.setFormatter(form)
            self.__num_open += 1
            logger.addHandler(new_h)
            # save process_id to handle open / close
            logger.process_id = record_process
            logger.handle_name = h_name
            self.__handles[h_name] = logger
            logger.info(SEP_STR)
            logger.info("opened %s (file %s in %s) by pid %d" % (full_name, base_name, base_dir, self.pid))
            log_strs.append("added handle %s (file %s in dir %s), total open: %s" % (h_name,
                                                                                     base_name,
                                                                                     base_dir,
                                                                                     logging_tools.get_plural("handle", len(self.__handles.keys()))))
        return self.__handles[h_name], log_strs
    def loop_end(self):
        self.__num_write += 3
        self.log("closing %d handles" % (len(self.__handles.keys())))
        self.log("logging thread exiting (pid %d)" % (self.pid))
        self.log("statistics (open/close/written): %d / %d / %d" % (self.__num_open, self.__num_close, self.__num_write))
        for close_key in self.__handles.keys():
            self.remove_handle(close_key)

class server_thread_pool(threading_tools.thread_pool):
    def __init__(self, glob_config):
        self.__glob_config = glob_config
        self.__logger, self.__log_queue, self.__log_buffer, self.__eg_queue = (None, None, [], None)
        threading_tools.thread_pool.__init__(self, "main", blocking_loop=False)
        self.register_exception("int_error", self._int_error)
        self.register_exception("term_error", self._int_error)
        self.register_func("new_pid", self._new_pid)
        self.register_func("eg_update_ok", self._eg_update_ok)
        self.__egu_ok = True
        # msi_block
        self._init_msi_block()
        # log thread
        self.__log_queue = self.add_thread(logging_thread(self.__glob_config), start_thread=True).get_thread_queue()
        # set logger
        self.__logger = logging_tools.get_logger("thread.%s" % (self.name), "threadqueue", target_queue=self.__log_queue, pre_tuple="int_log")
        # error gather thread
        self.__eg_queue = self.add_thread(error_gather_thread(self.__log_queue, self.__glob_config), start_thread=True).get_thread_queue()
        # bind dict, bind_state
        self.__udb_dict, self.__bind_state = ({}, {})
        self.__ns = net_tools.network_server(timeout=1, log_hook=self.log, poll_verbose=False)
        # tail stuff
        self.__tail_queue = None
        self._bind_ubds()
    def _int_error(self, err_cause):
        if self["exit_requested"]:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            self.__udb_dict = {}
            self["exit_requested"] = True
            self.__ns.set_timeout(0.1)
    def _new_pid(self, new_pid):
        self.log("received new_pid message")
        process_tools.append_pids("logserver/logserver", new_pid)
        if self.__msi_block:
            self.__msi_block.add_actual_pid(new_pid)
            self.__msi_block.save_block()
    def _init_msi_block(self):
        process_tools.append_pids("logserver/logserver")
        if self.__glob_config["DAEMON"]:
            self.log("Initialising meta-server-info block")
            msi_block = process_tools.meta_server_info("logserver")
            msi_block.add_actual_pid()
            msi_block.set_start_command("/etc/init.d/logging-server start")
            msi_block.set_stop_command("/etc/init.d/logging-server force-stop")
            msi_block.set_kill_pids()
            msi_block.save_block()
        else:
            msi_block = None
        self.__msi_block = msi_block
    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        if self.__logger:
            while self.__log_buffer:
                c_lev, c_what = self.__log_buffer.pop(0)
                self.__logger.log(c_lev, c_what)
            self.__logger.log(level, what)
        else:
            if self["exit_requested"]:
                print "post", what, level
            else:
                self.__log_buffer.append((level, what))
    def loop_start(self):
        self.log("configured FROM_ADDR: '%s', FROM_NAME: '%s'" % (self.__glob_config["FROM_ADDR"], self.__glob_config["FROM_NAME"]))
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
        for conf in self.__glob_config.get_config_info():
            self.log("Config: %s" % (conf))
    def loop_end(self):
        self.__ns.close_objects()
        del self.__ns
    def thread_loop_post(self):
        process_tools.delete_pid("logserver/logserver")
        if self.__msi_block:
            self.__msi_block.remove_meta_block()
    def loop_function(self):
        if not self.__tail_queue:
            if os.path.isfile(self.__glob_config["TAIL_FILE_NAME"]):
                self.log("Starting tail-thread ...")
                self.__tail_queue = self.add_thread(tail_follow_thread(self.__log_queue, self.__ns, self.__glob_config), start_thread=True).get_thread_queue()
            else:
                self.log("no tail_file %s found" % (self.__glob_config["TAIL_FILE_NAME"]),
                         logging_tools.LOG_LEVEL_WARN)
        self.__ns.step()
        self.__log_queue.put("update")
        if self.__egu_ok:
            # only send update if previous one was acked
            self.__egu_ok = False
            self.__eg_queue.put("update")
        if self.__tail_queue:
            self.__tail_queue.put("update")
    def _eg_update_ok(self):
        self.__egu_ok = True
    def _bind_ubds(self):
        self.log("populating udb_dict")
        self.__udb_dict["OUT"] = self.__ns.add_object(net_tools.unix_domain_bind(self._new_ud_out_recv, socket=self.__glob_config["OUT_HANDLE"], mode=0666, bind_state_call=self._bind_state_call))[0]
        self.__udb_dict["ERR"] = self.__ns.add_object(net_tools.unix_domain_bind(self._new_ud_err_recv, socket=self.__glob_config["ERR_HANDLE"], mode=0666, bind_state_call=self._bind_state_call))[0]
        self.__udb_dict["LOG"] = self.__ns.add_object(net_tools.unix_domain_bind(self._new_ud_log_recv, socket=self.__glob_config["LOG_HANDLE"], mode=0666, bind_state_call=self._bind_state_call))[0]
        self.__udb_dict["NET_UDP"] = self.__ns.add_object(net_tools.udp_bind(self._new_udp_recv, port=self.__glob_config["LISTEN_PORT"], timeout=60, bind_retries=5, bind_state_call=self._bind_state_call))[0]
        self.__udb_dict["NET_TCP"] = self.__ns.add_object(net_tools.tcp_bind(self._new_tcp_con, port=self.__glob_config["LISTEN_PORT"], timeout=60, bind_retries=5, bind_state_call=self._bind_state_call))[0]
        #print self.
    def _bind_state_call(self, **args):
        ro_wait = 1
        id_str = "%s_%s" % (args["type"], str(args["port"]))
        self.__bind_state[id_str] = args["state"]
        num_ok = self.__bind_state.values().count("ok")
        num_not_ok = len(self.__bind_state.keys()) - num_ok
        self.log("bind_state_dict has now %s, %d ok%s" % (logging_tools.get_plural("key", len(self.__bind_state.keys())),
                                                          num_ok,
                                                          num_not_ok and ", %d not ok" % (num_not_ok) or ""))
        if num_ok + num_not_ok == 5:
            if num_not_ok:
                self.log("Unable to bind to all sockets, exiting ...", logging_tools.LOG_LEVEL_CRITICAL)
                c_flag = False
            else:
                self.log("Successfully bound to all sockets, setting timeout to 60 seconds, testing connection")
                self.__ns.set_timeout(60)
                log_template = net_logging_tools.log_command(self.__glob_config["INTERNAL_CHECK_NAME"])
                log_template.set_destination("uds_nb:%s" % (self.__glob_config["LOG_HANDLE"]))
                errnum, errstr = log_template.log("test")
                log_template.close()
                self.log(" ... done (%d, %s)" % (errnum, errstr))
                if errnum:
                    self.log("Closing unix_domain sockets and reopening after %s ..." % (logging_tools.get_plural("seconds", ro_wait)), logging_tools.LOG_LEVEL_ERROR)
                    for key in ["OUT", "ERR", "LOG", "NET_UDP", "NET_TCP"]:
                        self.__udb_dict[key].close()
                        del self.__udb_dict[key]
                    self._bind_ubds()
                    time.sleep(ro_wait)
                else:
                    self.log("removing lockfile")
                    process_tools.delete_lockfile(self.__glob_config["LOCKFILE_NAME"])
            # clear bind_state dict
            for k in self.__bind_state.keys():
                del self.__bind_state[k]
    def _new_ud_out_recv(self, data, src):
        self.__log_queue.put(("py_out", data))
    def _new_ud_err_recv(self, data, src):
        self.__eg_queue.put(("err_uds", data))
    def _new_ud_log_recv(self, data, src):
        #in_len = struct.unpack(">L", data[0:4])[0]
        #data = "%08d%s" % (in_len, data[4:])
        self.__log_queue.put(("log_uds", data))
    def _new_udp_recv(self, data, src):
        #in_len = struct.unpack(">L", data[0:4])[0]
        #data = "%08d%s" % (in_len, data[4:])
        self.__log_queue.put(("log_udp", data))
    def _new_tcp_con(self, sock, src):
        return tcp_recv_obj(src, self.__log_queue)
        
def main():
    long_host_name = socket.getfqdn(socket.gethostname())
    short_host_name = long_host_name.split(".")[0]
    try:
        opts, args = getopt.getopt(sys.argv[1:], "dhF:t:iu:g:fk", ["--help"])
    except getopt.GetoptError, bla:
        print "Commandline error: %s" % (process_tools.get_except_info())
        sys.exit(1)
    cf_name = "/etc/sysconfig/logging-server"
    pname = os.path.basename(sys.argv[0])
    glob_config = configfile.configuration("logserver", {"MAILSERVER"          : configfile.str_c_var("localhost"),
                                                         "FROM_NAME"           : configfile.str_c_var("pyerror"),
                                                         "FROM_ADDR"           : configfile.str_c_var(socket.getfqdn()),
                                                         "LOG_FORMAT"          : configfile.str_c_var("%(asctime)s : %(levelname)-5s (%(threadName)s) %(message)s"),
                                                         "DATE_FORMAT"         : configfile.str_c_var("%a %b %d %H:%M:%S %Y"),
                                                         "OUT_HANDLE"          : configfile.str_c_var("/var/lib/logging-server/py_out"),
                                                         "ERR_HANDLE"          : configfile.str_c_var("/var/lib/logging-server/py_err"),
                                                         "LOG_HANDLE"          : configfile.str_c_var("/var/lib/logging-server/py_log"),
                                                         "LOG_DESTINATION"     : configfile.str_c_var("/var/log/cluster/logging-server"),
                                                         "LOCKFILE_NAME"       : configfile.str_c_var("/var/lock/logserver/logging_server.lock"),
                                                         "TRACE_PROC"          : configfile.int_c_var(0),
                                                         "REOPEN_COUNT"        : configfile.int_c_var(30),
                                                         "LISTEN_PORT"         : configfile.int_c_var(8011),
                                                         "INTERNAL_CHECK_NAME" : configfile.str_c_var("logging_server_check"),
                                                         "STATISTICS_TIMER"    : configfile.int_c_var(600),
                                                         "LOG_LINES"           : configfile.int_c_var(0),
                                                         "LOG_SEND_COUNTER"    : configfile.int_c_var(10),
                                                         "TAIL_FILE_NAME"      : configfile.str_c_var("/etc/sysconfig/logging-server.d/tail"),
                                                         "LOG_COMMANDS"        : configfile.bool_c_var(True),
                                                         "KILL_RUNNING"        : configfile.bool_c_var(True),
                                                         "USER"                : configfile.str_c_var("root"),
                                                         "GROUP"               : configfile.str_c_var("root"),
                                                         "FIXIT"               : configfile.bool_c_var(False),
                                                         "TO_ADDR"             : configfile.str_c_var("lang-nevyjel@init.at"),
                                                         "SEND_INITIAL_MAIL"   : configfile.bool_c_var(False),
                                                         "LONG_HOST_NAME"      : configfile.str_c_var(long_host_name),
                                                         "SHORT_HOST_NAME"     : configfile.str_c_var(short_host_name)})
    glob_config.parse_file(cf_name)
    # always set FROM_ADDR
    glob_config["FROM_ADDR"] = socket.getfqdn()
    # daemon has to be a local variable, otherwise system startup can be severly damaged
    daemon = True
    process_tools.delete_lockfile(glob_config["LOCKFILE_NAME"], None, 0)
    for opt, arg in opts:
        if opt in ("-h", "--help"):
            print "Usage: %s [ OPTIONS ]" % (pname)
            print "Version is %s" % (logging_server_version.VERSION_STRING)
            print "where OPTIONS are:"
            print "  -h, --help     this help"
            print "  -F CFILE       give name of alternate configfile (default is %s)" % (cf_name)
            print "  -d             run in debug mode (no daemonizing)"
            print "  -t TO_ADDR     sets the to_addr, default is %s" % (glob_config["TO_ADDR"])
            print "  -i             sends an initial testmail"
            print "  -f             create and fix needed files and directories"
            print "  -u user        run as user USER, default is %s" % (glob_config["USER"])
            print "  -g group       run as group GROUP, default is %s" % (glob_config["USER"])
            print "  -k             do not kill running %s" % (pname)
            print "  options for configfile:"
            for k in glob_config.keys():
                print "     %-20s: %s" % (k, str(glob_config[k]))
            sys.exit(0)
        elif opt in ["-t"]:
            glob_config["TO_ADDR"] = arg
        elif opt in ["-i"]:
            glob_config["SEND_INITIAL_MAIL"] = 1
        elif opt in ["-F"]:
            cf_name = arg
        elif opt == "-d":
            daemon = False
        elif opt == "-f":
            glob_config["FIXIT"] = True
        elif opt == "-u":
            glob_config["USER"] = arg
        elif opt == "-g":
            glob_config["GROUP"] = arg
        elif opt == "-k":
            glob_config["KILL_RUNNING"] = False
    if glob_config["FIXIT"]:
        process_tools.fix_directories(glob_config["USER"], glob_config["GROUP"], [os.path.dirname(glob_config["OUT_HANDLE"]),
                                                                                  "/var/run/logserver",
                                                                                  "/var/lock/logserver",
                                                                                  "/etc/sysconfig/logging-server.d",
                                                                                  "/var/log/cluster/logging-server",
                                                                                  glob_config["LOG_DESTINATION"]])
    try:
        os.chmod("/var/lib/logging-server", 0777)
    except:
        pass
    if glob_config["KILL_RUNNING"]:
        process_tools.kill_running_processes(pname)
    glob_config["LONG_HOST_NAME"] = long_host_name
    glob_config["SHORT_HOST_NAME"] = short_host_name
    glob_config.write_file(cf_name, True)
    glob_config.add_config_dict({"DAEMON" : configfile.bool_c_var(daemon)})
    process_tools.renice()
    process_tools.change_user_group(glob_config["USER"], glob_config["GROUP"])
    if glob_config["FROM_ADDR"] in ["linux.site", "localhost", "localhost.localdomain"]:
        glob_config["FROM_ADDR"] = socket.getfqdn()
    process_tools.create_lockfile(glob_config["LOCKFILE_NAME"])
    if glob_config["DAEMON"]:
        process_tools.become_daemon(mother_hook = process_tools.wait_for_lockfile,
                                    mother_hook_args = (glob_config["LOCKFILE_NAME"], 1))
        process_tools.set_handles("logging-server")
    else:
        print "Debugging logging-server"
    thread_pool = server_thread_pool(glob_config)
    thread_pool.thread_loop()
    ret_code = 0
    if glob_config["DAEMON"]:
        process_tools.handles_write_endline()
    process_tools.delete_lockfile(glob_config["LOCKFILE_NAME"], None, 0)
    sys.exit(ret_code)

if __name__ == "__main__":
    main()
