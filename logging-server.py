#!/usr/bin/python-init -Ot
# -*- coding: utf-8 -*-
#
# Copyright (C) 2009,2010,2011,2012,2013 Andreas Lang-Nevyjel (lang-nevyjel@init.at)
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
""" logging server, central logging facility """

import configfile
import cPickle
import grp
import io_stream_helper
import logging
import logging_server_version
import logging_tools
import mail_tools
import os
import pprint
import process_tools
import pwd
import socket
import sys
import threading_tools
import time
import zmq
from twisted.internet import reactor
from twisted.internet.protocol import DatagramProtocol

SEP_STR = "-" * 50

class twisted_log_receiver(DatagramProtocol):
    def __init__(self, t_process):
        self.__process = t_process
    def datagramReceived(self, in_str, addr):
        if in_str[0:8].isdigit():
            self.__process.log_recv(in_str[8:])
        else:
            self.__process.log("invalid header", logging_tools.LOG_LEVEL_ERROR)


class twisted_process(threading_tools.process_obj):
    def process_init(self):
        self.__log_socket = self.connect_to_socket("receiver")
        # init twisted reactor
        # self._got_udp = udp_log_receiver()
        # tcp_factory = Factory()
        # tcp_factory.protocol = tcp_log_receiver
        # reactor.listenUDP(8004, self._got_udp)
        # reactor.listenTCP(8004, tcp_factory)
        bind_errors = 0
        log_recv = twisted_log_receiver(self)
        for h_name in ["LOG", "ERR", "OUT"]:
            h_name = global_config["%s_HANDLE" % (h_name)]
            if os.path.isfile(h_name):
                try:
                    os.unlink(h_name)
                except:
                    self.log(
                        "error removing (stale) UDS-handle %s: %s" % (
                            h_name,
                            process_tools.get_except_info()),
                        logging_tools.LOG_LEVEL_ERROR)
                else:
                    self.log("remove stale UDS-handle %s" % (h_name))
            try:
                reactor.listenUNIXDatagram(h_name, log_recv)
            except:
                self.log(
                    "cannot listen to UDS %s: %s" % (
                        h_name,
                        process_tools.get_except_info()),
                    logging_tools.LOG_LEVEL_ERROR)
                bind_errors += 1
            else:
                self.log("listening on UDS %s" % (h_name))
        try:
            reactor.listenUDP(global_config["LISTEN_PORT"], log_recv)
        except:
            self.log(
                "cannot listen to UDP port %d: %s" % (
                    global_config["LISTEN_PORT"],
                    process_tools.get_except_info()),
                logging_tools.LOG_LEVEL_ERROR)
            bind_errors += 1
        if bind_errors:
            self.send_pool_message("startup_error", bind_errors)
    def log_recv(self, raw_data):
        self.send_to_socket(self.__log_socket, ["log_recv", raw_data])
    def loop_post(self):
        self.log("closing receiver socket")
        self.__log_socket.close()
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.send_to_socket(self.__log_socket, ["log", what, log_level])

class log_receiver(threading_tools.process_obj):
    def process_init(self):
        self.__log_cache = []
        self.__handles = {}
        threading_tools.process_obj.process_init(self)
        self.register_func("log_recv", self._log_recv)
        self.register_func("log", self.log)
        self.register_func("update", self._update)
        os.umask(2)
        self.__num_write, self.__num_close, self.__num_open = (0, 0, 0)
        self.log("logging_process %s is now awake (pid %d)" % (self.name, self.pid))
        int_names = ["log", "log_py", "err_py"]
        for name in int_names:
            handle = self.get_python_handle(name)
        self.log("opened handles for %s" % (", ".join(self.__handles.keys())))
        self._flush_log_cache()
        self.__last_stat_time = time.time()
        # error gather dict
        self.__eg_dict = {}
        self.__stat_timer = global_config["STATISTICS_TIMER"]
    def log(self, what, level=logging_tools.LOG_LEVEL_OK, dst="log", **kwargs):
        if dst in self.__handles:
            cur_dst = self.__handles[dst]
            # check for open handles
            if dst != "log":
                for cur_handle in cur_dst.handlers:
                    if not os.path.exists(cur_handle.baseFilename):
                        self.log(
                            "reopening file %s for %s" % (
                                cur_handle.baseFilename,
                                dst))
                        cur_handle.stream = cur_handle._open()
            # print dir(cur_dst)
            if "src_thread" in kwargs or "src_process" in kwargs:
                # build record to log src_thread
                cur_record = logging.makeLogRecord({
                    "threadName" : kwargs.get("src_thread", kwargs.get("src_process", "???")),
                    "process"    : kwargs.get("src_pid", 0),
                    "msg"        : what,
                    "levelno"    : level,
                    "levelname"  : logging_tools.get_log_level_str(level)})
                cur_dst.handle(cur_record)
            else:
                cur_dst.log(level, what) # , extra={"threadName" : kwargs.get("src_thread", "bla")})
        else:
            self.__log_cache.append((dst, what, level))
    def _flush_log_cache(self):
        for dst, what, level in self.__log_cache:
            self.log(what, level, dst=dst)
        self.__log_cache = []
    def _feed_error(self, in_dict):
        try:
            # get error string
            error_f = [
                in_dict.get("exc_text", "") or "", 
                in_dict.get("error_str", "") or "",
            ]
            error_str = ("\n".join([line for line in error_f if line.rstrip()]))
            if error_str:
                error_f = error_str.split("\n")
            else:
                self.log("cannot extract error_str, using dump of error_dict", logging_tools.LOG_LEVEL_ERROR)
                error_f = []
                for key in sorted(in_dict.iterkeys()):
                    try:
                        error_f.append(u"  %-20s : %s" % (key, unicode(in_dict[key])))
                    except:
                        error_f.append(u"  error logging key '%s' : %s" % (
                            key,
                            process_tools.get_except_info(),
                            ))

            self.__eg_dict.setdefault(in_dict["pid"], {
                "last_update" : time.time(),
                "errors"      : [],
                "proc_dict"   : in_dict})["errors"].extend(error_f)
            # log to err_py
            try:
                uname = pwd.getpwuid(in_dict.get("uid", -1))[0]
            except:
                uname = "<unknown>"
            try:
                gname = grp.getgrgid(in_dict.get("gid", -1))[0]
            except:
                gname = "<unknown>"
            pid_str = "%s (uid %d [%s], gid %d [%s])" % (
                in_dict.get("name", "N/A"),
                in_dict.get("uid", 0),
                uname,
                in_dict.get("gid", 0),
                gname)
            for err_line in error_f:
                self.log("from pid %d (%s): %s" % (
                    in_dict.get("pid", 0),
                    pid_str,
                    err_line.rstrip()),
                         logging_tools.LOG_LEVEL_ERROR,
                         "err_py")
        except:
            self.log("error in handling error_dict: %s" % (process_tools.get_except_info()),
                     logging_tools.LOG_LEVEL_ERROR)
    def _get_process_info(self, es_dict):
        p_dict = es_dict.get("proc_dict", {})
        return "name %s, ppid %d, uid %d, gid %d" % (
            p_dict.get("name", "N/A"),
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
                subject = "Python error for pid %d on %s@%s (%s)" % (
                    ep,
                    global_config["LONG_HOST_NAME"], c_name,
                    process_tools.get_machine_name())
                msg_body = "\n".join(["Processinfo %s" % (self._get_process_info(es))] +
                                     ["%3d %s" % (line_num + 1, line) for line_num, line in enumerate(es["errors"])])
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
        new_mail = mail_tools.mail(
            subject,
            "%s@%s" % (global_config["FROM_NAME"], global_config["FROM_ADDR"]),
            global_config["TO_ADDR"],
            msg_body)
        new_mail.set_server(global_config["MAILSERVER"],
                            global_config["MAILSERVER"])
        try:
            send_stat, log_lines = new_mail.send_mail()
            for log_line in log_lines:
                self.log(" - (%d) %s" % (send_stat, log_line),
                         logging_tools.LOG_LEVEL_OK)
        except:
            self.log("error sending mail: %s" % (process_tools.get_except_info()),
                     logging_tools.LOG_LEVEL_CRITICAL)
    def any_message_received(self):
        act_time = time.time()
        self.__num_write += 1
        if not self.__last_stat_time or abs(act_time - self.__last_stat_time) > self.__stat_timer or self.__num_write % 10000 == 0:
            self.__last_stat_time = act_time
            self.log("logstat (open/close/written): %d / %d / %d, mem_used is %s" % (
                self.__num_open,
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
    def _update(self, **kwargs):
        c_handles = sorted([key for key, value in self.__handles.iteritems() if isinstance(value, logging_tools.new_logfile) and value.check_for_temp_close()])
        if c_handles:
            self.log("temporarily closing %s: %s" % (logging_tools.get_plural("handle", len(c_handles)),
                                                     ", ".join(c_handles)))
        # check for close
        # c_handles = []
        # for key in self.__handles.iterkeys():
        #    if not os.path.isdir("/proc/%d" % (self.__handles[key].process_id)):
        #        c_handles.append(key)
        for c_handle in c_handles:
            self.remove_handle(c_handle)
        self._check_error_dict()
    def decode_in_str(self, in_str):
        python_log_com = False
        try:
            in_dict = cPickle.loads(in_str)
        except:
            in_dict = {}
        if in_dict:
            # pprint.pprint(in_dict)
            if in_dict.has_key("IOS_type"):
                self.log("got error_dict (pid %d)" % (in_dict["pid"]),
                         logging_tools.LOG_LEVEL_ERROR)
                self._feed_error(in_dict)
                log_com, ret_str, python_log_com = (None, "", False)
            else:
                log_com, ret_str, python_log_com = (logging.makeLogRecord(in_dict), "", True)
        else:
            if in_str == "meta-server-test":
                log_com, ret_str, python_log_com = (None, "", False)
            else:
                raise ValueError, "Unable to dePickle or deMarshal string (%s)" % (unicode(in_str[0:10]))
        return log_com, ret_str, python_log_com
    def get_python_handle(self, record):
        log_strs = []
        if type(record) == type(""):
            # special type for direct handles (log, log_py, err_py)
            sub_dirs = []
            record_host = "localhost"
            record_name, record_process, record_parent_process = (
                "init.at.%s" % (record),
                os.getpid(),
                os.getppid())
        else:
            if not hasattr(record, "host"):
                # no host set: use local machine name
                record.host = process_tools.get_machine_name()
            sub_dirs = [record.host]
            record_host = record.host
            record_name, record_process, record_parent_process = (record.name,
                                                                  record.process,
                                                                  getattr(record, "ppid", 0))
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
            if not (set([record_process, record_parent_process]) &
                    set([self.__handles[h_name].process_id,
                         self.__handles[h_name].parent_process_id])) and not self.__handles[h_name].ignore_process_id:
                self.remove_handle(h_name)
        if not h_name in self.__handles:
            self.log("logger '%s' (logger_type %s) requested" % (logger_name,
                                                                 "init.at" if init_logger else "native"))
            full_name = "%s/%s" % (global_config["LOG_DESTINATION"], h_name)
            base_dir, base_name = (os.path.dirname(full_name),
                                   os.path.basename(full_name))
            self.log("attempting to create log_file '%s' in dir '%s'" % (base_name, base_dir))
            # add new sub_dirs
            sub_dirs = []
            for new_sub_dir in os.path.dirname(h_name).split("/"):
                if not sub_dirs:
                    sub_dirs.append(new_sub_dir)
                else:
                    sub_dirs.append("%s/%s" % (sub_dirs[-1], new_sub_dir))
            # create sub_dirs
            for sub_dir in sub_dirs:
                act_dir = os.path.join(global_config["LOG_DESTINATION"], sub_dir)
                if not os.path.isdir(act_dir):
                    try:
                        os.makedirs(act_dir)
                    except OSError:
                        self.log("cannot create directory %s: %s" % (act_dir,
                                                                     process_tools.get_except_info()))
                    else:
                        self.log("created directory %s" % (act_dir))
            # init logging config
            # logging.config.fileConfig("logging.conf", {"file_name" : full_name})
            # base_logger = logging.getLogger("init.at")
            logger = logging.getLogger(logger_name)
            logger.propagate = 0
            # print logging.root.manager.loggerDict.keys()
            # print dir(base_logger)
            # print "***", logger_name, base_logger, logger
            form = logging_tools.my_formatter(global_config["LOG_FORMAT"],
                                              global_config["DATE_FORMAT"])
            logger.setLevel(logging.DEBUG)
            full_name = full_name.encode("ascii", errors="replace")
            new_h = logging_tools.new_logfile(full_name, max_bytes=1000000, max_age_days=global_config["MAX_AGE_FILES"])
            form.set_max_line_length(global_config["MAX_LINE_LENGTH"])
            new_h.setFormatter(form)
            self.__num_open += 1
            logger.addHandler(new_h)
            # save process_id to handle open / close
            logger.process_id = record_process
            logger.parent_process_id = record_parent_process
            # set ignore_process_id flag, usefull for apache process / threadpools
            logger.ignore_process_id = False
            logger.handle_name = h_name
            self.__handles[h_name] = logger
            logger.info(SEP_STR)
            logger.info("opened %s (file %s in %s) by pid %s" % (full_name, base_name, base_dir, self.pid))
            self.log("added handle %s (file %s in dir %s), total open: %s" % (
                h_name,
                base_name,
                base_dir,
                logging_tools.get_plural("handle", len(self.__handles.keys()))))
        return self.__handles[h_name]
    def _log_recv(self, in_str, **kwargs):
        self.any_message_received()
        # print "received from %s: %s" % (str(addr), str(data))
        # self.transport.write("ok")
        try:
            log_com, in_str, python_log_com = self.decode_in_str(in_str)
        except:
            self.log(
                "error reconstructing log-command (len of in_str: %d): %s" % (
                    len(in_str),
                    process_tools.get_except_info()),
                logging_tools.LOG_LEVEL_ERROR)
        else:
            if log_com:
                if not python_log_com:
                    # seldom used, remove ? FIXME
                    new_log_com = logging.LogRecord(
                        log_com.get_name(with_sub_names=1),
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
                handle = self.get_python_handle(log_com)
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
                                print "**"
                                pass
                            else:
                                for f_handle in handle.handlers:
                                    f_handle.formatter.set_max_line_length(line_length)
                        elif log_msg.lower() == "ignore_process_id":
                            handle.ignore_process_id = True
                        else:
                            self.log("unknown command '%s'" % (log_msg),
                                     logging_tools.LOG_LEVEL_ERROR)
                if not is_command or (is_command and global_config["LOG_COMMANDS"]):
                    try:
                        handle.handle(log_com)
                    except:
                        self.log(
                            "error handling log_com '%s': %s" % (
                                str(log_com),
                                process_tools.get_except_info()),
                            logging_tools.LOG_LEVEL_ERROR)
                del log_com
            elif in_str:
                self.log("error reconstructing log-command (len of in_str: %d): no log_com (possibly very long log_str)" % (len(in_str)),
                         logging_tools.LOG_LEVEL_ERROR)
            else:
                # error_dict
                pass
    def loop_end(self):
        self._check_error_dict(force=True)
        self.__num_write += 3
        self.log("closing %d handles" % (len(self.__handles.keys())))
        self.log("logging process exiting (pid %d)" % (self.pid))
        self.log("statistics (open/close/written): %d / %d / %d" % (self.__num_open, self.__num_close, self.__num_write))
        for close_key in self.__handles.keys():
            self.remove_handle(close_key)

class main_process(threading_tools.process_pool):
    def __init__(self, options):
        self.__options = options
        threading_tools.process_pool.__init__(self, "main", stack_size=2 * 1024 * 1024, zmq=True, zmq_debug=global_config["ZMQ_DEBUG"])
        process_tools.delete_lockfile(global_config["LOCKFILE_NAME"])
        self.register_exception("int_error", self._int_error)
        self.register_exception("term_error", self._int_error)
        self.register_func("startup_error", self._startup_error)
        self.renice()
        self._init_msi_block()
        self.add_process(log_receiver("receiver", priority=50), start=True)
        self._log_config()
        self._init_network_sockets()
        self.add_process(twisted_process("twisted"), twisted=True, start=True)
        self.register_timer(self._heartbeat, 30, instant=True)
        self.register_timer(self._update, 60)
    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        if not self["exit_requested"]:
            pass
            # self.send_to_process("receiver", "log", what, level)
        else:
            logging_tools.my_syslog(what, level)
    def _startup_error(self, src_name, src_pid, num_errors):
        self.log("%s during startup, exiting" % (logging_tools.get_plural("bind error", num_errors)),
                 logging_tools.LOG_LEVEL_ERROR)
        self._int_error("bind problem")
    def _int_error(self, err_cause):
        if self["exit_requested"]:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            self.log("exit requested", logging_tools.LOG_LEVEL_WARN)
            self["exit_requested"] = True
    def _log_config(self):
        self.log("Config info:")
        for line, log_level in global_config.get_log(clear=True):
            self.log(" - clf: [%d] %s" % (log_level, line))
        conf_info = global_config.get_config_info()
        self.log("Found %d valid config-lines:" % (len(conf_info)))
        for conf in conf_info:
            self.log("Config : %s" % (conf))
    def _remove_handles(self):
        any_removed = False
        for act_hname in self.__open_handles:
            if os.path.exists(act_hname):
                self.log("removing previous handle %s" % (act_hname))
                os.unlink(act_hname)
                any_removed = True
        if any_removed:
            time.sleep(0.5)
    def _init_network_sockets(self):
        self.__open_handles = [io_stream_helper.zmq_socket_name(global_config[h_name]) for h_name in ["LOG_HANDLE", "ERR_HANDLE", "OUT_HANDLE"]] + \
            [global_config[h_name] for h_name in ["LOG_HANDLE", "ERR_HANDLE", "OUT_HANDLE"]]
        self._remove_handles()
        client = self.zmq_context.socket(zmq.PULL)
        for h_name in ["LOG_HANDLE", "ERR_HANDLE", "OUT_HANDLE"]:
            client.bind(io_stream_helper.zmq_socket_name(global_config[h_name], check_ipc_prefix=True))
            os.chmod(io_stream_helper.zmq_socket_name(global_config[h_name]), 0777)
        self.register_poller(client, zmq.POLLIN, self._recv_data)
        self.std_client = client
    def _heartbeat(self):
        if self.__msi_block:
            self.__msi_block.heartbeat()
    def _update(self):
        self.send_to_process("receiver", "update")
    def _recv_data(self, zmq_socket):
        # zmq_socket.recv()
        in_data = zmq_socket.recv()
        self.send_to_process("receiver", "log_recv", in_data)
    def process_start(self, src_process, src_pid):
        process_tools.append_pids("logserver/logserver", src_pid, mult=3)
        if self.__msi_block:
            self.__msi_block.add_actual_pid(src_pid, mult=3)
            self.__msi_block.save_block()
    def _init_msi_block(self):
        process_tools.save_pids("logserver/logserver", mult=3)
        process_tools.append_pids("logserver/logserver", pid=configfile.get_manager_pid(), mult=4)
        if not self.__options.DEBUG:
            self.log("Initialising meta-server-info block")
            msi_block = process_tools.meta_server_info("logserver")
            msi_block.add_actual_pid(mult=3)
            msi_block.add_actual_pid(act_pid=configfile.get_manager_pid(), mult=4)
            msi_block.start_command = "/etc/init.d/logging-server start"
            msi_block.stop_command = "/etc/init.d/logging-server force-stop"
            msi_block.kill_pids = True
            msi_block.heartbeat_timeout = 60
            msi_block.save_block()
        else:
            msi_block = None
        self.__msi_block = msi_block
    def loop_post(self):
        self._remove_handles()
        process_tools.delete_pid("logserver/logserver")
        if self.__msi_block:
            self.__msi_block.remove_meta_block()
        self.std_client.close()

global_config = configfile.get_global_config("logging-server")

def main():
    long_host_name, mach_name = process_tools.get_fqdn()
    global_config.add_config_entries([
        ("MAILSERVER"          , configfile.str_c_var("localhost", help_string="mailserver for sending [%(default)s]", short_options="M")),
        ("DEBUG"               , configfile.bool_c_var(False, help_string="enable debug mode [%(default)s]", short_options="d", only_commandline=True)),
        ("ZMQ_DEBUG"           , configfile.bool_c_var(False, help_string="enable 0MQ debugging [%(default)s]", only_commandline=True)),
        ("FROM_NAME"           , configfile.str_c_var("pyerror")),
        ("FROM_ADDR"           , configfile.str_c_var(socket.getfqdn())),
        ("LOG_FORMAT"          , configfile.str_c_var("%(asctime)s : %(levelname)-5s (%(threadName)s.%(process)d) %(message)s")),
        ("DATE_FORMAT"         , configfile.str_c_var("%a %b %d %H:%M:%S %Y")),
        ("OUT_HANDLE"          , configfile.str_c_var("/var/lib/logging-server/py_out")),
        ("ERR_HANDLE"          , configfile.str_c_var("/var/lib/logging-server/py_err")),
        ("LOG_HANDLE"          , configfile.str_c_var("/var/lib/logging-server/py_log")),
        ("LOG_DESTINATION"     , configfile.str_c_var("/var/log/cluster/logging-server")),
        ("LOCKFILE_NAME"       , configfile.str_c_var("/var/lock/logserver/logging_server.lock")),
        ("LISTEN_PORT"         , configfile.int_c_var(8011)),
        ("STATISTICS_TIMER"    , configfile.int_c_var(600)),
        ("LOG_COMMANDS"        , configfile.bool_c_var(True)),
        ("KILL_RUNNING"        , configfile.bool_c_var(True)),
        ("MAX_AGE_FILES"       , configfile.int_c_var(365, help_string="max age for logfiles in days [%(default)i]", short_options="age")),
        ("USER"                , configfile.str_c_var("idlog", help_string="run as user [%(default)s]", short_options="u")),
        ("GROUP"               , configfile.str_c_var("idg", help_string="run as group [%(default)s]", short_options="g")),
        ("TO_ADDR"             , configfile.str_c_var("lang-nevyjel@init.at", help_string="mail address to send error-mails [%(default)s]")),
        ("LONG_HOST_NAME"      , configfile.str_c_var(long_host_name)),
        ("MAX_LINE_LENGTH"     , configfile.int_c_var(0))])
    global_config.parse_file()
    options = global_config.handle_commandline(description="logging server, version is %s" % (logging_server_version.VERSION_STRING))
    if global_config["KILL_RUNNING"]:
        process_tools.kill_running_processes(exclude=configfile.get_manager_pid())
    # daemon has to be a local variable, otherwise system startup can be severly damaged
    lockfile_name = global_config["LOCKFILE_NAME"]
    # attention: global_config is not longer present after the TERM signal
    process_tools.delete_lockfile(lockfile_name, None, 0)
    try:
        os.chmod("/var/lib/logging-server", 0777)
        os.chmod("/var/log/cluster/sockets", 0777)
    except:
        pass
    global_config.write_file()
    # process_tools.renice()
    # not very beautiful ...
    configfile.enable_config_access(global_config["USER"], global_config["GROUP"])
    process_tools.change_user_group(global_config["USER"], global_config["GROUP"])
    process_tools.create_lockfile(global_config["LOCKFILE_NAME"])
    if not options.DEBUG:
        process_tools.become_daemon(mother_hook=process_tools.wait_for_lockfile,
                                    mother_hook_args=(global_config["LOCKFILE_NAME"], 1))
        process_tools.set_handles("logging-server")
    else:
        print "Debugging logging-server"
    main_process(options).loop()
    if not options.DEBUG:
        process_tools.handles_write_endline()
    process_tools.delete_lockfile(lockfile_name, None, 0)
    sys.exit(0)

if __name__ == "__main__":
    main()
