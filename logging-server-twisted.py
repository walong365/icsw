#!/usr/bin/python-init -Ot
# -*- coding: utf-8 -*-
#
# Copyright (C) 2009,2010 Andreas Lang-Nevyjel (lang-nevyjel@init.at)
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

from twisted.internet import reactor, task
from twisted.internet.protocol import Protocol, DatagramProtocol
from twisted.python import log
import logging_server_version
import logging_tools
import threading_tools
import time
import os
import sys
import process_tools
import struct
import marshal
import cPickle
import net_logging_tools
import pprint
import logging
import socket
import optparse
import configfile
import mail_tools
import pwd
import grp

SEP_STR = "-" * 50

class tcp_log_receiver(Protocol):
    #def __init__(self, log_recv):
        #Protocol.__init__(self)
        #self.__log_recv = log_recv
    def dataReceived(self, data):
        self.log_recv.datagramReceived(data, None)
        self.transport.write("ok")

class log_receiver(DatagramProtocol):
    def __init__(self, glob_config):
        self.pid = os.getpid()
        self.name = threading_tools.get_act_thread_name()
        self.__glob_config = glob_config
        self.__handles, self.__log_buffer = ({}, [])
        # input cache
        self._init_input_cache()
        self.__num_write, self.__num_close, self.__num_open = (0, 0, 0)
        init_log_lines = ["logging_thread %s is now awake (pid %d)" % (self.name, self.pid)]
        int_names = ["log", "log_py", "err_py"]
        for name in int_names:
            handle, log_lines = self.get_python_handle(name)
            init_log_lines.extend(log_lines)
        init_log_lines.append("opened handles for %s" % (", ".join(self.__handles.keys())))
        self.write_log_lines(init_log_lines)
        self.__last_stat_time = time.time()
        # error gather dict
        self.__eg_dict = {}
    def log(self, what, level=logging_tools.LOG_LEVEL_OK, dst="log"):
        if dst in self.__handles:
            cur_dst = self.__handles[dst]
            # check for open handles
            
            if dst != "log":
                for cur_handle in cur_dst.handlers:
                    if not os.path.exists(cur_handle.baseFilename):
                        self.log("reopening file %s for %s" % (cur_handle.baseFilename,
                                                               dst))
                        cur_handle.stream = cur_handle._open()
            cur_dst.log(level, what)
    def _init_input_cache(self):
        self.__datagram_buffer = ""
    def _feed_error(self, in_dict):
        try:
            self.__eg_dict.setdefault(in_dict["pid"], {"last_update" : time.time(),
                                                       "errors"      : [],
                                                       "proc_dict"   : in_dict})["errors"].append(in_dict["error_str"].rstrip())
            # log to err_py
            try:
                uname = pwd.getpwuid(in_dict.get("uid", -1))[0]
            except:
                uname = "<unknown>"
            try:
                gname = grp.getgrgid(in_dict.get("gid", -1))[0]
            except:
                gname = "<unknown>"
            pid_str = "%s (uid %d [%s], gid %d [%s])" % (in_dict.get("name", "N/A"),
                                                         in_dict.get("uid", 0),
                                                         uname,
                                                         in_dict.get("gid", 0),
                                                         gname)
            for err_line in in_dict["error_str"].rstrip().split("\n"):
                self.log("from pid %d (%s): %s" % (in_dict.get("pid", 0),
                                                   pid_str,
                                                   err_line.rstrip()),
                         logging_tools.LOG_LEVEL_ERROR,
                         "err_py")
        except:
            self.log("error in handling error_dict: %s" % (process_tools.get_except_info()),
                     logging_tools.LOG_LEVEL_ERROR)
    def _get_process_info(self, es_dict):
        p_dict = es_dict.get("proc_dict", {})
        return "name %s, ppid %d, uid %d, gid %d" % (p_dict.get("name", "N/A"),
                                                     p_dict.get("ppid", 0),
                                                     p_dict.get("uid", -1),
                                                     p_dict.get("gid", -1))
    def _check_error_dict(self, force=False):
        c_name = process_tools.get_cluster_name()
        mails_sent = 0
        s_time = time.time()
        ep_dels = []
        for ep, es in self.__eg_dict.iteritems():
            t_diff = s_time - es["last_update"]
            if force or (t_diff < 0 or t_diff > 60):
                subject = "Python error for pid %d on %s@%s" % (ep, self.__glob_config["LONG_HOST_NAME"], c_name)
                msg_body = "\n".join(["Processinfo %s" % (self._get_process_info(es))] +
                                     ["%3d %s" % (x[0] + 1, x[1]) for x in zip(range(len(es["errors"])),
                                                                               es["errors"])])
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
    def write_log_lines(self, l_lines):
        for log_line in l_lines:
            self.log(log_line)
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
    def remove_handle(self, h_name):
        self.log("closing handle %s" % (h_name))
        self.__num_close += 1
        handle = self.__handles[h_name]
        if isinstance(handle, logging.Logger):
            handle.info("key / name : %s / %s" % (h_name, handle.handle_name))
            handle.info("closed %s by pid %d [logger]" % (h_name, self.pid))
            for sub_h in handle.handlers:
                handle.removeHandler(sub_h)
                sub_h.close()
        else:
            handle.write("closed %s by pid %d [plain]" % (h_name, self.pid))
            handle.close()
        del self.__handles[h_name]
    def _update(self):
        c_handles = sorted([key for key, value in self.__handles.iteritems() if isinstance(value, logging_tools.new_logfile) and value.check_for_temp_close()])
        if c_handles:
            self.log("temporarily closing %s: %s" % (logging_tools.get_plural("handle", len(c_handles)),
                                                     ", ".join(c_handles)))
        # check for close
        #c_handles = []
        #for key in self.__handles.iterkeys():
        #    if not os.path.isdir("/proc/%d" % (self.__handles[key].process_id)):
        #        c_handles.append(key)
        for c_handle in c_handles:
            self.remove_handle(c_handle)
        self._check_error_dict()
    def decode_in_str(self, in_str):
        python_log_com = False
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
                if in_dict.has_key("IOS_type"):
                    self.log("got error_dict (pid %d)" % (in_dict["pid"]),
                             logging_tools.LOG_LEVEL_ERROR)
                    self._feed_error(in_dict)
                    log_com, ret_str, python_log_com = (None, "", False)
                else:
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
                if in_str == "meta-server-test":
                    log_com, ret_str, python_log_com = (None, "", False)
                else:
                    raise ValueError, "Unable to dePickle or deMarshal string (%s)" % (str(in_str[0:10]))
        return log_com, ret_str, python_log_com
    def get_python_handle(self, record):
        log_strs = []
        if type(record) == type(""):
            # special type for direct handles (log, log_py, err_py)
            sub_dirs = []
            record_host = "localhost"
            record_name, record_process = ("init.at.%s" % (record),
                                           os.getpid())
        else:
            if not hasattr(record, "host"):
                # no host set: use local machine name
                record.host = process_tools.get_machine_name()
            sub_dirs = [record.host]
            record_host = record.host
            record_name, record_process = (record.name,
                                           record.process)
        init_logger = record_name.startswith("init.at.")
        if init_logger:
            # init.at logger, create subdirectories
            logger_name = "%s.%s" % (record_host, record_name)
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
            if record_process != self.__handles[h_name].process_id and not self.__handles[h_name].ignore_process_id:
                self.remove_handle(h_name)
        if not h_name in self.__handles:
            log_strs.append("logger '%s' (logger_type %s) requested" % (logger_name,
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
            form = logging_tools.my_formatter(self.__glob_config["LOG_FORMAT"],
                                              self.__glob_config["DATE_FORMAT"])
            logger.setLevel(logging.DEBUG)
            new_h = logging_tools.new_logfile(full_name, max_bytes=1000000)
            form.set_max_line_length(self.__glob_config["MAX_LINE_LENGTH"])
            new_h.setFormatter(form)
            self.__num_open += 1
            logger.addHandler(new_h)
            # save process_id to handle open / close
            logger.process_id = record_process
            # set ignore_process_id flag, usefull for apache process / threadpools
            logger.ignore_process_id = False
            logger.handle_name = h_name
            self.__handles[h_name] = logger
            logger.info(SEP_STR)
            logger.info("opened %s (file %s in %s) by pid %d" % (full_name, base_name, base_dir, self.pid))
            log_strs.append("added handle %s (file %s in dir %s), total open: %s" % (h_name,
                                                                                     base_name,
                                                                                     base_dir,
                                                                                     logging_tools.get_plural("handle", len(self.__handles.keys()))))
        return self.__handles[h_name], log_strs
    def datagramReceived(self, in_str, addr):
        self.any_message_received()
        #print "received from %s: %s" % (str(addr), str(data))
        #self.transport.write("ok")
        if self.__datagram_buffer:
            in_str = "%s%s" % (self.__datagram_buffer, in_str)
            self.log("still %d bytes in datagram buffer, in_str has now %d bytes" % (len(self.__datagram_buffer),
                                                                                     len(in_str)),
                     logging_tools.LOG_LEVEL_WARN)
            self._init_input_cache()
        num_lines = 0
        decode = True
        while decode:
            decode = False
            # iterate until as much as possible is decoded
            if in_str[0:8].isdigit():
                cur_length = int(in_str[1:8])
                if cur_length > len(in_str) -8:
                    self.log("message part too small (need %d bytes, got %d)" % (cur_length, len(in_str) - 8),
                             logging_tools.LOG_LEVEL_WARN)
                    self.__datagram_buffer = in_str
                    break
                elif cur_length == len(in_str) - 8:
                    in_str = in_str[8:]
                else:
                    self.log("Error in proto_V1 in_str '%s', interpreting as proto_v0" % (in_str), logging_tools.LOG_LEVEL_ERROR)
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
                            log_msg = log_msg[5:-6]
                            if log_msg.lower() == "close":
                                self.remove_handle(handle.handle_name)
                            elif log_msg.lower().startswith("set_file_size"):
                                try:
                                    file_size = int(log_msg.split()[1])
                                except:
                                    pass
                                else:
                                    for f_handle in handle.handlers:
                                        if hasattr(f_handle, "set_max_bytes"):
                                            f_handle.set_max_bytes(file_size)
                            elif log_msg.lower().startswith("set_max_line_length"):
                                try:
                                    line_length = int(log_msg.split()[1])
                                except:
                                    pass
                                else:
                                    for f_handle in handle.handlers:
                                        f_handle.formatter.set_max_line_length(line_length)
                            elif log_msg.lower() == "ignore_process_id":
                                handle.ignore_process_id = True
                            else:
                                self.log("unknown command '%s'" % (log_msg),
                                         logging_tools.LOG_LEVEL_ERROR)
                    if not is_command or (is_command and self.__glob_config["LOG_COMMANDS"]):
                        try:
                            handle.handle(log_com)
                        except:
                            self.log("error handling log_com '%s': %s" % (str(log_com),
                                                                          process_tools.get_except_info()),
                                     logging_tools.LOG_LEVEL_ERROR)
                        else:
                            num_lines += 1
                    del log_com
                    if in_str:
                        decode = True
                elif in_str:
                    self.log("error reconstructing log-command (len of in_str: %d): no log_com (possibly very long log_str)" % (len(in_str)),
                             logging_tools.LOG_LEVEL_ERROR)
                    self._init_input_cache()
                else:
                    # error_dict
                    pass
        if num_lines > 1:
            self.log("received multi-line (%s)" % (logging_tools.get_plural("line", num_lines)))
    def loop_end(self):
        self._check_error_dict(force=True)
        self.__num_write += 3
        self.log("closing %d handles" % (len(self.__handles.keys())))
        self.log("logging thread exiting (pid %d)" % (self.pid))
        self.log("statistics (open/close/written): %d / %d / %d" % (self.__num_open, self.__num_close, self.__num_write))
        for close_key in self.__handles.keys():
            self.remove_handle(close_key)

# dervied from twisted_log_observer from logging_tools
class internal_twisted_log_observer(object):
    def __init__(self, recv_obj):
        self.__logger = recv_obj
        self.__last_cinfo = 0.0
    def __call__(self, in_dict):
        for line in in_dict["message"]:
            self.__logger.log(line, in_dict.get("log_level", logging_tools.LOG_LEVEL_OK))
        if in_dict["isError"]:
            if in_dict.get("why", None):
                self.__logger.log(in_dict["why"], logging_tools.LOG_LEVEL_CRITICAL)
            act_time = time.time()
            if abs(act_time - self.__last_cinfo) > 1:
                self.__logger.log("CINFO:%d" % (os.getpid()), logging_tools.LOG_LEVEL_CRITICAL)
                self.__last_cinfo = act_time
            for line in in_dict["failure"].getTraceback().split("\n"):
                self.__logger.log(line, logging_tools.LOG_LEVEL_CRITICAL)
        
class main_thread(threading_tools.twisted_main_thread):
    def __init__(self, glob_config, options):
        self.__glob_config = glob_config
        self.__options = options
        self.__log_recv = log_receiver(self.__glob_config)
        #self.__tcp_log_recv = tcp_log_receiver()#self.__log_recv)
        threading_tools.twisted_main_thread.__init__(self, "main")
        self.install_signal_handlers()
        self._init_msi_block()
        my_observer = internal_twisted_log_observer(self.__log_recv)
        log.startLoggingWithObserver(my_observer, setStdout=True)
        self._log_config()
    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        self.__log_recv.log(what, level)
    def _sigint(self):
        log.msg("got sigint")
        reactor.stop()
    def _sigterm(self):
        log.msg("got sigterm")
        reactor.stop()
    def _log_config(self):
        self.log("Config info:")
        for line, log_level in self.__glob_config.get_log(clear=True):
            self.log(" - clf: [%d] %s" % (log_level, line))
        conf_info = self.__glob_config.get_config_info()
        self.log("Found %d valid config-lines:" % (len(conf_info)))
        for conf in conf_info:
            self.log("Config : %s" % (conf))
    def _remove_handles(self):
        for act_shname in ["LOG", "ERR", "OUT"]:
            act_hname = self.__glob_config["%s_HANDLE" % (act_shname)]
            if os.path.exists(act_hname):
                self.log("removing previous handle %s" % (act_hname))
                os.unlink(act_hname)
    def run(self):
        log.msg("starting mainloop")
        self._remove_handles()
        #print dir(reactor)
        try:
            reactor.listenUDP(self.__glob_config["LISTEN_PORT"], self.__log_recv)
            #reactor.listenTCP(self.__glob_config["LISTEN_PORT"], self.__tcp_log_recv)
            reactor.listenUNIXDatagram(self.__glob_config["LOG_HANDLE"], self.__log_recv)
            reactor.listenUNIXDatagram(self.__glob_config["ERR_HANDLE"], self.__log_recv)
            reactor.listenUNIXDatagram(self.__glob_config["OUT_HANDLE"], self.__log_recv)
        except:
            print process_tools.get_except_info()
            self.log("error binding")
        else:
            self.log("removing lockfile")
            process_tools.delete_lockfile(self.__glob_config["LOCKFILE_NAME"])
            task.LoopingCall(self.__log_recv._update).start(60)
            task.LoopingCall(self._heartbeat).start(30)
            reactor.run(installSignalHandlers=False)
        self.__log_recv.loop_end()
        self.thread_loop_post()
    def _init_msi_block(self):
        process_tools.append_pids("logserver/logserver")
        if not self.__options.debug_mode:
            self.log("Initialising meta-server-info block")
            msi_block = process_tools.meta_server_info("logserver")
            msi_block.add_actual_pid()
            msi_block.start_command = "/etc/init.d/logging-server start"
            msi_block.stop_command = "/etc/init.d/logging-server force-stop"
            msi_block.kill_pids = True
            msi_block.heartbeat_timeout = 60
            msi_block.save_block()
        else:
            msi_block = None
        self.__msi_block = msi_block
    def thread_loop_post(self):
        self._remove_handles()
        process_tools.delete_pid("logserver/logserver")
        if self.__msi_block:
            self.__msi_block.remove_meta_block()
    def _heartbeat(self):
        if self.__msi_block:
            self.__msi_block.heartbeat()

class my_options(optparse.OptionParser):
    def __init__(self, glob_config):
        optparse.OptionParser.__init__(self, version=logging_server_version.VERSION_STRING)
        self.__glob_config = glob_config
        self.add_option("-d", action="store_true", dest="debug_mode", default=False, help="run in debug mode (no daemonizing) [%default]")
        self.add_option("-k", action="store_false", dest="kill_running", default=self.__glob_config["KILL_RUNNING"], help="disables killing of already running logging-server [%default]")
        self.add_option("-t", type="str", dest="to_addr", default=self.__glob_config["TO_ADDR"], help="mail address to send error-mails [%default]")
        self.add_option("-i", action="store_true", dest="send_initial_mail", default=self.__glob_config["SEND_INITIAL_MAIL"], help="enable sending of initial mails [%default]")
        self.add_option("-f", action="store_true", dest="fixit", default=self.__glob_config["FIXIT"], help="create and fix needed files and directories [%default]")
        self.add_option("-u", type="str", dest="user", default=self.__glob_config["USER"], help="run as user [%default]")
        self.add_option("-g", type="str", dest="group", default=self.__glob_config["GROUP"], help="run as group [%default]")
    def parse(self):
        options, args = self.parse_args()
        if args:
            print "Additional arguments found, exiting"
            sys.exit(0)
        self.__glob_config["SEND_INITIAL_MAIL"] = options.send_initial_mail
        self.__glob_config["KILL_RUNNING"] = options.kill_running
        self.__glob_config["TO_ADDR"] = options.to_addr
        self.__glob_config["FIXIT"]   = options.fixit
        self.__glob_config["USER"]    = options.user
        self.__glob_config["GROUP"]   = options.group
        return options

def main():
    long_host_name = socket.getfqdn(socket.gethostname())
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
                                                         "LISTEN_PORT"         : configfile.int_c_var(8011),
                                                         "STATISTICS_TIMER"    : configfile.int_c_var(600),
                                                         "LOG_COMMANDS"        : configfile.bool_c_var(True),
                                                         "KILL_RUNNING"        : configfile.bool_c_var(True),
                                                         "USER"                : configfile.str_c_var("idlog"),
                                                         "GROUP"               : configfile.str_c_var("idg"),
                                                         "FIXIT"               : configfile.bool_c_var(False),
                                                         "TO_ADDR"             : configfile.str_c_var("lang-nevyjel@init.at"),
                                                         "SEND_INITIAL_MAIL"   : configfile.bool_c_var(False),
                                                         "LONG_HOST_NAME"      : configfile.str_c_var(long_host_name),
                                                         "MAX_LINE_LENGTH"     : configfile.int_c_var(0)})
    glob_config.parse_file(cf_name)
    my_parser = my_options(glob_config)
    options = my_parser.parse()
    #opts, args = getopt.getopt(sys.argv[1:], "dhF:t:iu:g:fk", ["--help"])
    # always set FROM_ADDR
    glob_config["FROM_ADDR"] = socket.getfqdn()
    # daemon has to be a local variable, otherwise system startup can be severly damaged
    process_tools.delete_lockfile(glob_config["LOCKFILE_NAME"], None, 0)
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
    glob_config.write_file(cf_name, True)
    process_tools.renice()
    process_tools.change_user_group(glob_config["USER"], glob_config["GROUP"])
    if glob_config["FROM_ADDR"] in ["linux.site", "localhost", "localhost.localdomain"]:
        glob_config["FROM_ADDR"] = socket.getfqdn()
    process_tools.create_lockfile(glob_config["LOCKFILE_NAME"])
    if not options.debug_mode:
        process_tools.become_daemon(mother_hook = process_tools.wait_for_lockfile,
                                    mother_hook_args = (glob_config["LOCKFILE_NAME"], 1))
        process_tools.set_handles("logging-server")
    else:
        print "Debugging logging-server"
    main_thread(glob_config, options).run()
    if not options.debug_mode:
        process_tools.handles_write_endline()
    process_tools.delete_lockfile(glob_config["LOCKFILE_NAME"], None, 0)
    sys.exit(0)

if __name__ == "__main__":
    main()
    
