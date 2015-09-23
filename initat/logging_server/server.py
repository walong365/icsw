# -*- coding: utf-8 -*-
#
# Copyright (C) 2009-2015 Andreas Lang-Nevyjel (lang-nevyjel@init.at)
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

""" logging server, central logging facility, server-part """

import grp
import logging
import os
import pickle
import pwd
import resource
import stat
import time

from initat.logging_server.config import global_config
from initat.icsw.service import clusterid
from initat.tools import io_stream_helper, logging_tools, mail_tools, process_tools, threading_tools, \
    uuid_tools
from initat.tools.server_mixins import ICSWBasePool
import zmq

SEP_STR = "-" * 50


class main_process(ICSWBasePool):
    def __init__(self, options):
        self.__options = options
        # log structures
        self.__log_cache = []
        self.__handles = {}
        # which source keys use this handle
        self.__handle_usage = {}
        # number of usecounts
        self.__handle_usecount = {}
        self.__usecount_ts = time.time()
        threading_tools.process_pool.__init__(self, "main", stack_size=2 * 1024 * 1024, zmq=True)
        self.register_exception("int_error", self._int_error)
        self.register_exception("term_error", self._int_error)
        self.register_func("startup_error", self._startup_error)
        self.CC.init("logging-server", global_config, init_logging=False)
        self.CC.check_config(client=True)
        self.change_resource()
        self._init_msi_block()
        self._log_config()
        self._init_network_sockets()
        self.register_timer(self._update, 60)
        os.umask(2)
        self.__num_write, self.__num_close, self.__num_open = (0, 0, 0)
        self.__num_forward_ok, self.__num_forward_error = (0, 0)
        self.log("logging_process {} is now awake (pid {:d})".format(self.name, self.pid))
        int_names = ["log", "log_py", "err_py"]
        for name in int_names:
            _handle = self.get_python_handle(name)
        self.log("opened handles for {}".format(", ".join(self.__handles.keys())))
        self._flush_log_cache()
        self.__last_stat_time = time.time()
        # error gather dict
        self.__eg_dict = {}
        self.__stat_timer = 600

    def change_resource(self):
        cur_files = resource.getrlimit(resource.RLIMIT_OFILE)
        new_files = (cur_files[1], cur_files[1])
        self.log(
            "changed RLIMIT_OFILE from ({:d}, {:d}) to ({:d}, {:d})".format(
                cur_files[0],
                cur_files[1],
                new_files[0],
                new_files[1],
            )
        )
        resource.setrlimit(resource.RLIMIT_OFILE, new_files)
        self.log("fixing directory rights")
        try:
            os.chmod("/var/lib/logging-server", stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)
            os.chmod("/var/log/cluster/sockets", stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)
        except:
            pass

    def log(self, what, level=logging_tools.LOG_LEVEL_OK, dst="log", **kwargs):
        if not self["exit_requested"]:
            if dst in self.__handles:
                cur_dst = self.__handles[dst]
                # check for open handles
                if dst != "log":
                    for cur_handle in cur_dst.handlers:
                        if not os.path.exists(cur_handle.baseFilename):
                            self.log(
                                "reopening file {} for {}".format(
                                    cur_handle.baseFilename,
                                    dst
                                )
                            )
                            cur_handle.stream = cur_handle._open()
                # print dir(cur_dst)
                if "src_thread" in kwargs or "src_process" in kwargs:
                    # build record to log src_thread
                    cur_record = logging.makeLogRecord(
                        {
                            "threadName": kwargs.get("src_thread", kwargs.get("src_process", "???")),
                            "process": kwargs.get("src_pid", 0),
                            "msg": what,
                            "levelno": level,
                            "levelname": logging_tools.get_log_level_str(level)
                        }
                    )
                    cur_dst.handle(cur_record)
                else:
                    cur_dst.log(level, what)  # , extra={"threadName" : kwargs.get("src_thread", "bla")})
            else:
                self.__log_cache.append((dst, what, level))
        else:
            logging_tools.my_syslog(what, level)

    def _startup_error(self, src_name, src_pid, num_errors):
        self.log(
            "{} during startup, exiting".format(
                logging_tools.get_plural("bind error", num_errors)
            ),
            logging_tools.LOG_LEVEL_ERROR
        )
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
            self.log(" - clf: [{:d}] {}".format(log_level, line))
        conf_info = global_config.get_config_info()
        self.log("Found {:d} valid config-lines:".format(len(conf_info)))
        for conf in conf_info:
            self.log("Config : {}".format(conf))

    def _remove_handles(self):
        any_removed = False
        for act_hname in self.__open_handles:
            if os.path.exists(act_hname):
                self.log("removing previous handle {}".format(act_hname))
                os.unlink(act_hname)
                any_removed = True
        if any_removed:
            time.sleep(0.5)

    def _init_network_sockets(self):
        _log_base = "/var/lib/logging-server"
        _handle_names = [os.path.join(_log_base, "py_{}".format(_type)) for _type in ["out", "err", "log"]]
        self.__open_handles = [
            io_stream_helper.zmq_socket_name(h_name) for h_name in _handle_names
        ] + [
            h_name for h_name in _handle_names
        ]
        self._remove_handles()
        client = self.zmq_context.socket(zmq.PULL)  # @UndefinedVariable
        for h_name in _handle_names:
            client.bind(io_stream_helper.zmq_socket_name(h_name, check_ipc_prefix=True))
            os.chmod(io_stream_helper.zmq_socket_name(h_name), stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)
        self.network_bind(
            bind_port=global_config["COMMAND_PORT"],
            bind_to_localhost=True,
            pollin=self._recv_data,
            client_type="logging-server",
        )

        _fwd_string = self.CC.CS["log.forward.address"].strip()
        self.__only_forward = self.CC.CS["log.forward.exclusive"]
        if _fwd_string:
            _forward = process_tools.get_socket("PUSH", identity=uuid_tools.get_uuid().get_urn())
            self.log("connecting forward socket to {}".format(_fwd_string))
            try:
                _forward.connect(_fwd_string)
            except:
                self.log(" ... problem: {}".format(process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
                _forward = None
        else:
            _forward = None
        self.net_forwarder = _forward
        self.register_poller(client, zmq.POLLIN, self._recv_data)  # @UndefinedVariable
        self.std_client = client

    def _init_msi_block(self):
        process_tools.save_pids("logserver/logserver", mult=3)
        self.log("Initialising meta-server-info block")
        msi_block = process_tools.meta_server_info("logserver")
        # increased ceiling to 4, ALN 20150812
        msi_block.add_actual_pid(mult=3, fuzzy_ceiling=4, process_name="main")
        msi_block.kill_pids = True
        msi_block.save_block()
        self.__msi_block = msi_block

    def loop_end(self):
        self._check_error_dict(force=True)
        self.__num_write += 3
        self.log("closing {:d} handles".format(len(self.__handles.keys())))
        self.log("logging process exiting (pid {:d})".format(self.pid))
        self.log("statistics (open/close/written): {:d} / {:d} / {:d}".format(self.__num_open, self.__num_close, self.__num_write))
        key_list = list(self.__handles.keys())
        for close_key in key_list:
            self.remove_handle(close_key)

    def loop_post(self):
        self._remove_handles()
        process_tools.delete_pid("logserver/logserver")
        self.__msi_block.remove_meta_block()
        if self.net_forwarder:
            self.net_forwarder.close()
        self.network_unbind()
        self.std_client.close()

    def _flush_log_cache(self):
        for dst, what, level in self.__log_cache:
            self.log(what, level, dst=dst)
        self.__log_cache = []

    def _feed_error(self, in_dict):
        try:
            # error_str is set in io_stream_helper.io_stream
            error_str = u"{}{}".format(
                in_dict.get("exc_text", u"") or u"",
                in_dict.get("error_str", u"") or u"",
            )
            if not error_str:
                self.log("cannot extract error_str, using dump of error_dict", logging_tools.LOG_LEVEL_ERROR)
                error_f = []
                for key in sorted(in_dict.keys()):
                    try:
                        error_f.append(u"  {:<20s} : {}".format(key, unicode(in_dict[key])))
                    except:
                        error_f.append(
                            u"  error logging key '{}' : {}".format(
                                key,
                                process_tools.get_except_info(),
                            )
                        )
                error_str = "\n".join(error_f)
            cur_dict = self.__eg_dict.setdefault(
                in_dict["pid"], {
                    "last_update": time.time(),
                    # error as unicode
                    "error_str": u"",
                    # how many lines we have already logged
                    "lines_logged": 0,
                    "proc_dict": in_dict
                }
            )
            # append line to errors
            cur_dict["error_str"] = "{}{}".format(cur_dict["error_str"], error_str)
            # log to err_py
            try:
                uname = pwd.getpwuid(in_dict.get("uid", -1))[0]
            except:
                uname = "<unknown>"
            try:
                gname = grp.getgrgid(in_dict.get("gid", -1))[0]
            except:
                gname = "<unknown>"
            pid_str = "{} (uid {:d} [{}], gid {:d} [{}])".format(
                in_dict.get("name", "N/A"),
                in_dict.get("uid", 0),
                uname,
                in_dict.get("gid", 0),
                gname
            )
            # log to err_py
            _lines = cur_dict["error_str"].split("\n")
            # never log the last line, this line is either incomplete (\n missing) or empty (\n present)
            for err_line in _lines[cur_dict["lines_logged"]:-1]:
                self.log(
                    "from pid {:d} ({}): {}".format(
                        in_dict.get("pid", 0),
                        pid_str,
                        err_line.rstrip()
                    ),
                    logging_tools.LOG_LEVEL_ERROR,
                    "err_py"
                )
            cur_dict["lines_logged"] = len(_lines) - 1
        except:
            self.log(
                "error in handling error_dict: {}".format(
                    process_tools.get_except_info()
                ),
                logging_tools.LOG_LEVEL_ERROR
            )

    def _get_process_info(self, es_dict):
        p_dict = es_dict.get("proc_dict", {})
        return "name {}, ppid {:d}, uid {:d}, gid {:d}".format(
            p_dict.get("name", "N/A"),
            p_dict.get("ppid", 0),
            p_dict.get("uid", -1),
            p_dict.get("gid", -1)
        )

    def _check_error_dict(self, force=False):
        c_name = process_tools.get_cluster_name()
        mails_sent = 0
        s_time = time.time()
        ep_dels = []
        for ep, es in self.__eg_dict.items():
            t_diff = s_time - es["last_update"]
            if force or (t_diff < 0 or t_diff > 60):
                subject = "Python error for pid {:d} on {}@{} ({}, {})".format(
                    ep,
                    process_tools.get_fqdn()[0],
                    c_name,
                    process_tools.get_machine_name(),
                    clusterid.get_cluster_id() or "N/A",
                )
                err_lines = "".join(es["error_str"]).split("\n")
                msg_body = "\n".join(
                    [
                        "Processinfo {}".format(self._get_process_info(es))
                    ] +
                    [
                        "{:3d} {}".format(line_num + 1, line) for line_num, line in enumerate(err_lines)
                    ]
                )
                if self.CC.CS["log.send.errormails"]:
                    self._send_mail(subject, msg_body)
                    mails_sent += 1
                ep_dels.append(ep)
        for epd in ep_dels:
            del self.__eg_dict[epd]
        e_time = time.time()
        if mails_sent:
            self.log(
                "Sent {} in {}".format(
                    logging_tools.get_plural("mail", mails_sent),
                    logging_tools.get_diff_time_str(e_time - s_time)
                )
            )

    def _send_mail(self, subject, msg_body):
        new_mail = mail_tools.mail(
            subject,
            "{}@{}".format(
                self.CC.CS["log.mail.from.name"],
                process_tools.get_fqdn()[0],
            ),
            self.CC.CS["mail.target.address"],
            msg_body,
        )
        new_mail.set_server(self.CC.CS["mail.server"], self.CC.CS["mail.server"])
        try:
            send_stat, log_lines = new_mail.send_mail()
            for log_line in log_lines:
                self.log(
                    " - ({:d}) {}".format(send_stat, log_line),
                    logging_tools.LOG_LEVEL_OK
                )
        except:
            self.log(
                "error sending mail: {}".format(process_tools.get_except_info()),
                logging_tools.LOG_LEVEL_CRITICAL
            )

    def any_message_received(self):
        act_time = time.time()
        self.__num_write += 1
        if not self.__last_stat_time or abs(act_time - self.__last_stat_time) > self.__stat_timer or self.__num_write % 10000 == 0:
            last_stat_time = self.__last_stat_time
            self.__last_stat_time = act_time
            if self.__num_forward_ok or self.__num_forward_error:
                fwd_str = ", {:d} fwd ({:d} error)".format(
                    self.__num_forward_ok,
                    self.__num_forward_error,
                )
            else:
                fwd_str = ""
            self.log(
                "logstat (open/close/written): {:d} / {:d} / {:d} ({:.2f}/s), mem_used is {}{}".format(
                    self.__num_open,
                    self.__num_close,
                    self.__num_write,
                    (
                        self.__num_write / max(1, (act_time - last_stat_time))
                    ),
                    process_tools.beautify_mem_info(),
                    fwd_str,
                )
            )
            self.__num_open, self.__num_close, self.__num_write = (0, 0, 0)
            self.__num_forward_ok, self.__num_forward_error = (0, 0)

    def remove_handle(self, h_name):
        self.log("closing handle {}".format(h_name))
        self.__num_close += 1
        handle = self.__handles[h_name]
        if isinstance(handle, logging.Logger):
            handle.info("key / name : {} / {}".format(h_name, handle.handle_name))
            handle.info("closed {} by pid {:d} [logger]".format(h_name, self.pid))
            for sub_h in handle.handlers:
                handle.removeHandler(sub_h)
                sub_h.close()
        else:
            handle.write("closed {} by pid {:d} [plain]".format(h_name, self.pid))
            handle.close()
        del self.__handles[h_name]
        if h_name in self.__handle_usage:
            del self.__handle_usage[h_name]
            del self.__handle_usecount[h_name]

    def _update(self, **kwargs):
        c_handles = sorted([key for key, value in self.__handles.items() if isinstance(value, logging_tools.logfile) and value.check_for_temp_close()])
        if c_handles:
            self.log(
                "temporarily closing {}: {}".format(
                    logging_tools.get_plural("handle", len(c_handles)),
                    ", ".join(c_handles)
                )
            )
        for c_handle in c_handles:
            self.remove_handle(c_handle)
        self._check_error_dict()
        self._check_excess_log()

    def _check_excess_log(self):
        cur_time = time.time()
        diff_time = max(1, abs(cur_time - self.__usecount_ts))
        s_dict = {key: float(value) / diff_time for key, value in self.__handle_usecount.iteritems()}
        self.__handle_usecount = {key: 0 for key in self.__handle_usecount}
        # ("EXCESS_LIMIT", configfile.int_c_var(1000, help_string="log lines per second to trigger excess_log [%(default)s]")),
        # s_dict = {key: value for key, value in s_dict.iteritems() if value > global_config["EXCESS_LIMIT"]}
        # pprint.pprint(s_dict)

    def get_python_handle(self, record):
        if isinstance(record, basestring):
            # special type for direct handles (log, log_py, err_py)
            sub_dirs = []
            record_host = "localhost"
            record_name, record_process, record_parent_process = (
                "init.at.{}".format(record),
                os.getpid(),
                os.getppid()
            )
        else:
            if not hasattr(record, "host"):
                # no host set: use local machine name
                record.host = process_tools.get_machine_name()
            sub_dirs = [record.host]
            record_host = record.host
            record_name, record_process, record_parent_process = (
                record.name,
                record.process,
                getattr(record, "ppid", 0)
            )
        init_logger = record_name.startswith("init.at.")
        if init_logger:
            # init.at logger, create subdirectories
            # generate list of dirs and file_name
            scr1_name = record_name[8:].replace("\.", "#").replace(".", "/").replace("#", ".")
            for path_part in os.path.dirname(scr1_name).split(os.path.sep):
                if path_part:
                    path_part = "{}.d".format(path_part)
                    if sub_dirs:
                        sub_dirs.append(os.path.join(sub_dirs[-1], path_part))
                    else:
                        sub_dirs.append(path_part)
            if sub_dirs:
                h_name = os.path.join(sub_dirs[-1], os.path.basename(scr1_name))
            else:
                h_name = os.path.basename(scr1_name)
        else:
            h_name = os.path.join(record.host, record_name)
        # create logger_name
        logger_name = "{}.{}".format(record_host, record_name)
        if h_name in self.__handles:
            if not (
                {record_process, record_parent_process} &
                {self.__handles[h_name].process_id, self.__handles[h_name].parent_process_id}
            ) and not self.__handles[h_name].ignore_process_id:
                self.log(
                    "access mismatch detected for {}".format(
                        h_name,
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
                self.remove_handle(h_name)
        if h_name not in self.__handles:
            self.log(
                "logger '{}' (logger_type {}) requested".format(
                    logger_name,
                    "init.at" if init_logger else "native"
                )
            )
            full_name = os.path.join(self.CC.CS["log.logdir"], h_name)
            base_dir, base_name = (
                os.path.dirname(full_name),
                os.path.basename(full_name)
            )
            self.log("attempting to create log_file '{}' in dir '{}'".format(base_name, base_dir))
            # add new sub_dirs
            sub_dirs = []
            for new_sub_dir in os.path.dirname(h_name).split("/"):
                if not sub_dirs:
                    sub_dirs.append(new_sub_dir)
                else:
                    sub_dirs.append(os.path.join(sub_dirs[-1], new_sub_dir))
            # create sub_dirs
            for sub_dir in sub_dirs:
                act_dir = os.path.join(self.CC.CS["log.logdir"], sub_dir)
                if not os.path.isdir(act_dir):
                    try:
                        os.makedirs(act_dir)
                    except OSError:
                        self.log(
                            "cannot create directory {}: {}".format(
                                act_dir,
                                process_tools.get_except_info(),
                            )
                        )
                    else:
                        self.log("created directory {}".format(act_dir))
            # init logging config
            # logging.config.fileConfig("logging.conf", {"file_name" : full_name})
            # base_logger = logging.getLogger("init.at")
            logger = logging.getLogger(logger_name)
            # print "*", logger_name, h_name
            logger.propagate = 0
            # print logging.root.manager.loggerDict.keys()
            # print dir(base_logger)
            # print "***", logger_name, base_logger, logger
            form = logging_tools.my_formatter(
                self.CC.CS["log.format.line"],
                self.CC.CS["log.format.date"],
            )
            logger.setLevel(logging.DEBUG)
            full_name = full_name.encode("ascii", errors="replace")
            new_h = logging_tools.logfile(
                full_name,
                max_bytes=self.CC.CS["log.max.size.logs"],
                max_age_days=self.CC.CS["log.max.age.logs"],
            )
            form.set_max_line_length(self.CC.CS["log.max.line.length"])
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
            self.__handle_usage[h_name] = set()
            self.__handle_usecount[h_name] = 0
            logger.info(SEP_STR)
            logger.info("opened {} (file {} in {}) by pid {}".format(full_name, base_name, base_dir, self.pid))
            self.log(
                "added handle {} (file {} in dir {}), total open: {}".format(
                    h_name,
                    base_name,
                    base_dir,
                    logging_tools.get_plural("handle", len(self.__handles.keys()))
                )
            )
        return self.__handles[h_name]

    def _recv_data(self, zmq_socket):
        # zmq_socket.recv()
        in_str = zmq_socket.recv()
        self.any_message_received()
        if self.net_forwarder:
            # hooray for 0MQ
            try:
                self.net_forwarder.send(in_str, zmq.DONTWAIT)  # @UndefinedVariable
            except:
                self.__num_forward_error += 1
            else:
                self.__num_forward_ok += 1
            if self.__only_forward:
                return
        self.decode_in_str(in_str)

    def decode_in_str(self, in_str):
        try:
            in_dict = pickle.loads(in_str)
        except:
            in_dict = {}
        if in_dict:
            # pprint.pprint(in_dict)
            if "IOS_type" in in_dict:
                self.log("got error_dict (pid {:d}, {})".format(in_dict["pid"], logging_tools.get_plural("key", len(in_dict))))
                self._feed_error(in_dict)
            else:
                self._handle_log_com(logging.makeLogRecord(in_dict))
        else:
            if in_str == "meta-server-test":
                pass
                # log_com, ret_str, python_log_com = (None, "", False)
            else:
                self.log(
                    "error reconstructing log-command (len of in_str: {:d}): {}".format(
                        len(in_str),
                        process_tools.get_except_info()
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )

    def _handle_log_com(self, log_com):
        handle = self.get_python_handle(log_com)
        log_msg = log_com.msg
        try:
            src_key = (log_com.processName, log_com.threadName)
        except:
            src_key = ("main", "main")
        # needed ?
        if isinstance(log_msg, basestring) and log_msg.lower().startswith("<lch>") and log_msg.lower().endswith("</lch>"):
            log_it, is_command = (
                self._handle_command(handle, src_key, log_com, log_msg),
                True,
            )
        else:
            # flag to disable logging of close message (would polute the usage_cache)
            log_it, is_command = (True, False)
        if (not is_command or is_command) and log_it:
            self.__handle_usage[handle.handle_name].add(src_key)
            try:
                self.__handle_usecount[handle.handle_name] += 1
                if handle.disabled:
                    self.log(
                        "disabled was true for handler {}, re-renabled".format(handle.name),
                        logging_tools.LOG_LEVEL_ERROR,
                    )
                    handle.disabled = False
                handle.handle(log_com)
            except:
                self.log(
                    "error handling log_com '{}': {}".format(
                        str(log_com),
                        process_tools.get_except_info()
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
        del log_com

    def _handle_command(self, handle, src_key, log_com, log_msg):
        h_name = handle.handle_name
        log_msg = log_msg[5:-6]
        log_it = True
        if log_msg.lower() == "close":
            _close = True
            if h_name in self.__handle_usage:
                if src_key in self.__handle_usage[h_name]:
                    self.__handle_usage[h_name].remove(src_key)
                if self.__handle_usage[h_name]:
                    _close = False
            if _close:
                self.remove_handle(handle.handle_name)
            log_it = False
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
                # print("**")
                pass
            else:
                for f_handle in handle.handlers:
                    f_handle.formatter.set_max_line_length(line_length)
        elif log_msg.lower() == "ignore_process_id":
            handle.ignore_process_id = True
        else:
            self.log(
                "unknown command '{}'".format(log_msg),
                logging_tools.LOG_LEVEL_ERROR
            )
        return log_it
