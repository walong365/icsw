# -*- coding: utf-8 -*-
#
# Copyright (C) 2001-2008,2010-2015 Andreas Lang-Nevyjel
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

import os
import signal
import stat
import time

from initat.meta_server.config import global_config
from initat.tools import configfile
from initat.tools import logging_tools
from initat.tools import mail_tools
from initat.tools import process_tools
from initat.tools import server_command
from initat.tools import threading_tools
from initat.tools import server_mixins
from initat.tools import inotify_tools
import zmq
from initat.host_monitoring import hm_classes
from initat.client_version import VERSION_STRING


class main_process(threading_tools.process_pool, server_mixins.network_bind_mixin):
    def __init__(self):
        self.__log_cache, self.__log_template = ([], None)
        threading_tools.process_pool.__init__(self, "main", zmq_debug=global_config["ZMQ_DEBUG"])
        # check for correct rights
        self._check_dirs()
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context)
        self._init_msi_block()
        self._init_network_sockets()
        self._init_inotify()
        self.register_exception("int_error", self._sigint)
        self.register_exception("term_error", self._sigint)
        # init stuff for mailing
        self.__new_mail = mail_tools.mail(None, "{}@{}".format(global_config["FROM_NAME"], global_config["FROM_ADDR"]), global_config["TO_ADDR"])
        self.__new_mail.set_server(global_config["MAILSERVER"], global_config["MAILSERVER"])
        # msi dict
        self.__last_update_time = time.time() - 2 * global_config["MIN_CHECK_TIME"]
        self.__last_memcheck_time = time.time() - 2 * global_config["MIN_MEMCHECK_TIME"]
        self._init_meminfo()
        self._show_config()
        self._scan_meta_dir()
        self.register_timer(self._check, 30, instant=True)

    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        if self.__log_template:
            self.__log_template.log(lev, what)
        else:
            self.__log_cache.append((lev, what))

    def _init_inotify(self):
        self.__watcher = inotify_tools.InotifyWatcher(log_com=self.log)
        self.__watcher.add_watcher(
            "main",
            global_config["MAIN_DIR"],
            inotify_tools.IN_CLOSE_WRITE | inotify_tools.IN_DELETE,
            self._inotify_event,
        )
        # register watcher fd with 0MQ poller
        self.register_poller(self.__watcher._fd, zmq.POLLIN, self._inotify_check)

    def _inotify_check(self, *args, **kwargs):
        try:
            self.__watcher.process()
        except:
            self.log(
                "exception occured in watcher.process(): {}".format(
                    process_tools.get_except_info()
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
        else:
            pass

    def _inotify_event(self, *args, **kwargs):
        _event = args[0]
        if _event.mask & inotify_tools.IN_DELETE:
            self._delete_msi_by_file_name(_event.pathname)
        elif _event.mask & inotify_tools.IN_CLOSE_WRITE:
            self._update_or_create_msi_by_file_name(_event.pathname)

    def _check_dirs(self):
        main_dir = global_config["MAIN_DIR"]
        if not os.path.isdir(main_dir):
            self.log("creating {}".format(main_dir))
            os.mkdir(main_dir)
        cur_stat = os.stat(main_dir)[stat.ST_MODE]
        new_stat = cur_stat | stat.S_IWGRP | stat.S_IRGRP | stat.S_IRUSR | stat.S_IWUSR | stat.S_IWOTH | stat.S_IROTH
        if cur_stat != new_stat:
            self.log(
                "modifing stat of {} from {:o} to {:o}".format(
                    main_dir,
                    cur_stat,
                    new_stat,
                )
            )
            os.chmod(main_dir, new_stat)

    def _init_msi_block(self):
        # store pid name because global_config becomes unavailable after SIGTERM
        self.__pid_name = global_config["PID_NAME"]
        process_tools.save_pids(self.__pid_name, mult=3)
        _spm = global_config.single_process_mode()
        if not _spm:
            process_tools.append_pids(self.__pid_name, pid=configfile.get_manager_pid(), mult=2)
        self.log("Initialising meta-server-info block")
        msi_block = process_tools.meta_server_info("meta-server")
        msi_block.add_actual_pid(mult=3, fuzzy_ceiling=7, process_name="main")
        if not _spm:
            msi_block.add_actual_pid(act_pid=configfile.get_manager_pid(), mult=2, process_name="manager")
        msi_block.start_command = "/etc/init.d/meta-server start"
        msi_block.stop_command = "/etc/init.d/meta-server force-stop"
        msi_block.kill_pids = True
        msi_block.save_block()
        self.__msi_block = msi_block

    def _sigint(self, err_cause):
        if self["exit_requested"]:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            self["exit_requested"] = True

    def _init_network_sockets(self):
        self.network_bind(
            bind_port=global_config["COM_PORT"],
            bind_to_localhost=True,
            pollin=self._recv_command,
            client_type="meta",
        )
        conn_str = process_tools.get_zmq_ipc_name("vector", s_name="collserver", connect_to_root_instance=True)
        if hm_classes and global_config["TRACK_CSW_MEMORY"]:
            vector_socket = self.zmq_context.socket(zmq.PUSH)  # @UndefinedVariable
            vector_socket.setsockopt(zmq.LINGER, 0)  # @UndefinedVariable
            vector_socket.connect(conn_str)
        else:
            vector_socket = None
        self.vector_socket = vector_socket
        # memory info send dict
        self.mis_dict = {}

    def _get_msi_block(self, srv_com):
        # check if a valid msi-block name is stored in arg_list
        _msi_block = None
        _args = srv_com["*arg_list"].strip()
        if _args:
            msi_name = _args.split()[0]
            if msi_name in self.__msi_dict:
                _msi_block = self.__msi_dict[msi_name]
            else:
                srv_com.set_result("msi block '{}' does not exist".format(msi_name), server_command.SRV_REPLY_STATE_ERROR)
        else:
            srv_com.set_result("no args given", server_command.SRV_REPLY_STATE_ERROR)
        return _msi_block

    def _check_srv_com_msi_block(self, srv_com, msi_block):
        if msi_block:
            msi_block.check_block()
            srv_com.set_result(
                "{}, {}".format(
                    msi_block.get_info(),
                    msi_block.pid_check_string,
                ),
                server_command.SRV_REPLY_STATE_OK if msi_block.pid_checks_failed == 0 else server_command.SRV_REPLY_STATE_ERROR,
            )
        else:
            srv_com.set_result(
                "no MSI-block defined",
                SRV_REPLY_STATE_WARN,
            )

    def _recv_command(self, zmq_sock):
        src_id = zmq_sock.recv()
        more = zmq_sock.getsockopt(zmq.RCVMORE)  # @UndefinedVariable
        if more:
            data = zmq_sock.recv()
            more = zmq_sock.getsockopt(zmq.RCVMORE)  # @UndefinedVariable
            srv_com = server_command.srv_command(source=data)
            self.log("got command '{}' from '{}'".format(
                srv_com["command"].text,
                srv_com["source"].attrib["host"]))
            srv_com.update_source()
            srv_com.set_result("ok")
            if srv_com["command"].text == "status":
                self._check_srv_com_msi_block(srv_com, self.__msi_block)
            elif srv_com["*command"] in ["msi_exists", "msi_stop", "msi_restart", "msi_force_stop", "msi_force_restart"]:
                msi_block = self._get_msi_block(srv_com)
                if msi_block is not None:
                    self._handle_msi_command(srv_com, msi_block)
            elif srv_com["command"].text == "version":
                srv_com.set_result("version is {}".format(VERSION_STRING))
            else:
                srv_com.set_result(
                    "unknown command '{}'".format(srv_com["command"].text),
                    server_command.SRV_REPLY_STATE_ERROR
                )
            try:
                zmq_sock.send_unicode(src_id, zmq.SNDMORE | zmq.NOBLOCK)  # @UndefinedVariable
                zmq_sock.send_unicode(unicode(srv_com), zmq.NOBLOCK)  # @UndefinedVariable
            except:
                self.log(
                    "error sending reply to {}: {}".format(
                        src_id,
                        process_tools.get_except_info(),
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
        else:
            self.log(
                "cannot receive more data, already got '{}'".format(
                    src_id
                ),
                logging_tools.LOG_LEVEL_ERROR
            )

    def _show_config(self):
        try:
            for log_line, log_level in global_config.get_log():
                self.log("Config info : [{:d}] {}".format(log_level, log_line))
        except:
            self.log("error showing configfile log, old configfile ? ({})".format(process_tools.get_except_info()),
                     logging_tools.LOG_LEVEL_ERROR)
        conf_info = global_config.get_config_info()
        self.log("Found {}:".format(logging_tools.get_plural("valid configline", len(conf_info))))
        for conf in conf_info:
            self.log("Config : {}".format(conf))

    def loop_end(self):
        process_tools.delete_pid(self.__pid_name)
        if self.__msi_block:
            self.__msi_block.remove_meta_block()

    def _handle_msi_command(self, srv_com, msi_block):
        command = srv_com["*command"]
        if command == "msi_exists":
            srv_com.set_result("msi block {} exists".format(msi_block.name))
        else:
            self.log("processing command {} for block {}".format(command, msi_block.name))
            if command in ["msi_force_stop", "msi_stop"]:
                if msi_block.stop_command:
                    _com = msi_block.stop_command
                    if not command.count("force"):
                        _com = _com.replace("force-stop", "stop")
                    self._force_stop = _com.replace("force-stop", "stop").replace("stop", "force-stop")
                    if self._force_stop != _com:
                        self.log("registering force-stop command {}".format(self._force_stop))
                    else:
                        self._force_stop = None
                    self._call_command(msi_block.stop_command, srv_com)
                else:
                    srv_com.set_result("no stop_command given for {}".format(msi_block.name), server_command.SRV_REPLY_STATE_ERROR)
            elif command in ["msi_restart", "msi_force_restart"]:
                if msi_block.stop_command and msi_block.start_command:
                    _com = msi_block.stop_command
                    if not command.count("force"):
                        _com = _com.replace("force-stop", "stop")
                    self._srv_com = srv_com
                    self._force_stop = _com.replace("force-stop", "stop").replace("stop", "force-stop")
                    if self._force_stop != _com:
                        self.log("registering force-stop command {}".format(self._force_stop))
                    else:
                        self._force_stop = None
                    self._call_command(_com, srv_com)
                    # needed ?
                    time.sleep(0.5)
                    self._call_command(msi_block.start_command, srv_com, merge_reply=True)
                    self._srv_com = None
                else:
                    srv_com.set_result("no stop or start command given for {}".format(msi_block.name), server_command.SRV_REPLY_STATE_ERROR)

    def _alarm(self, *args, **kwargs):
        signal.signal(signal.SIGALRM, signal.SIG_IGN)
        if self._force_stop:
            self.log("sigalarm called, starting force-stop", logging_tools.LOG_LEVEL_ERROR)
            self._call_command(self._force_stop, self._srv_com, merge_reply=True, init_alarm=False)
        else:
            self.log("sigalarm called but no force-stop command set", logging_tools.LOG_LEVEL_ERROR)

    def _call_command(self, act_command, srv_com=None, merge_reply=False, init_alarm=True):
        # call command directly
        s_time = time.time()
        if init_alarm:
            signal.signal(signal.SIGALRM, self._alarm)
            signal.alarm(7)
        if os.path.isfile(act_command.split()[0]):
            ret_code, _stdout, _stderr = process_tools.call_command(act_command, self.log)
        else:
            ret_code, _stdout, _stderr = (1, "", u"command '{}' does not exist".format(act_command))
        if init_alarm:
            signal.signal(signal.SIGALRM, signal.SIG_IGN)
        e_time = time.time()
        if srv_com is not None:
            _r_str, _r_state = (
                "returncode is {:d} for '{}' in {}".format(
                    ret_code,
                    act_command,
                    logging_tools.get_diff_time_str(e_time - s_time),
                ),
                server_command.SRV_REPLY_STATE_OK if ret_code == 0 else server_command.SRV_REPLY_STATE_ERROR,
            )
            if merge_reply:
                _prev_r_str, _prev_r_state = srv_com.get_log_tuple(map_to_log_level=False)
                _r_str = "{}, {}".format(_prev_r_str, _r_str)
                _r_state = max(_prev_r_state, _r_state)
            srv_com.set_result(
                _r_str,
                _r_state,
            )

    def _init_meminfo(self):
        self.__last_meminfo_keys, self.__act_meminfo_line = ([], 0)

    def _scan_meta_dir(self):
        # initial scan
        _list = []
        if os.path.isdir(global_config["MAIN_DIR"]):
            for fname in os.listdir(global_config["MAIN_DIR"]):
                full_name = os.path.join(global_config["MAIN_DIR"], fname)
                new_meta_info = self._read_msi_from_disk(full_name)
                if new_meta_info:
                    _list.append(new_meta_info)
        self.__msi_dict = {msi.name: msi for msi in _list}
        # build file lut
        self.__file_lut = {msi.file_name: msi.name for msi in self.__msi_dict.itervalues()}
        all_names = sorted(self.__msi_dict.keys())
        self.log(
            "{} found: {}".format(
                logging_tools.get_plural("meta_info_block", len(all_names)),
                ", ".join(all_names)
            )
        )

    def _check(self):
        act_time = time.time()
        if abs(act_time - self.__last_update_time) < global_config["MIN_CHECK_TIME"]:
            self.log(
                "last check only {} ago ({:.2f} needed), skipping...".format(
                    logging_tools.get_diff_time_str(abs(act_time - self.__last_update_time)),
                    global_config["MIN_CHECK_TIME"],
                ),
                logging_tools.LOG_LEVEL_WARN
            )
        else:
            self.__last_update_time = act_time
            self._check_processes()

    def _check_processes(self):
        act_time = time.time()
        del_list = []
        mem_info_dict = {}
        act_pid_dict = process_tools.get_proc_list()
        _check_mem = act_time > self.__last_memcheck_time + global_config["MIN_MEMCHECK_TIME"] and global_config["TRACK_CSW_MEMORY"]
        if _check_mem:
            self.__last_memcheck_time = act_time
        # import pprint
        # pprint.pprint(act_pid_dict)
        # print act_pid_list
        problems = []
        for key, struct in self.__msi_dict.iteritems():
            if struct.check_block(act_pid_dict):
                problems.append((key, struct))
            else:
                # check memory consumption if everything is ok
                if struct.check_memory and _check_mem:
                    pids = struct.get_unique_pids()
                    if pids:
                        # only count memory for one pid
                        mem_info_dict[key] = {pid: (struct.get_process_name(pid), process_tools.get_mem_info(pid)) for pid in pids}
        for key, struct in problems:
            pids_failed_time = abs(struct.get_last_pid_check_ok_time() - act_time)
            do_sthg = (struct.pid_checks_failed >= 2 and pids_failed_time >= global_config["FAILED_CHECK_TIME"])
            self.log(
                "*** unit {} (pid check failed for {}, {}): {} remaining, grace time {}, {}".format(
                    key,
                    logging_tools.get_plural("time", struct.pid_checks_failed),
                    struct.pid_check_string,
                    logging_tools.get_plural("grace_period", max(0, 2 - struct.pid_checks_failed)),
                    logging_tools.get_plural("second", global_config["FAILED_CHECK_TIME"] - pids_failed_time),
                    do_sthg and "starting countermeasures" or "still waiting...",
                ),
                logging_tools.LOG_LEVEL_WARN
            )
            if do_sthg:
                mail_text = [
                    "check failed for {}: {}".format(
                        key,
                        struct.pid_check_string),
                    "starting repair sequence",
                    "",
                ]
                self.log(
                    "*** starting repair sequence",
                    logging_tools.LOG_LEVEL_WARN
                )
                if struct.stop_command:
                    self._call_command(struct.stop_command)
                    mail_text.extend(
                        [
                            "issued the stop command : {} in 1 minute".format(struct.stop_command),
                            "",
                        ]
                    )
                if struct.kill_pids:
                    kill_info = struct.kill_all_found_pids()
                    self.log(
                        "  *** kill info: {}".format(kill_info),
                        logging_tools.LOG_LEVEL_WARN
                    )
                    mail_text.extend(
                        [
                            "trying to kill the remaining pids, kill info : {}".format(kill_info),
                            "",
                        ]
                    )
                if struct.start_command:
                    self._call_command(struct.start_command)
                    mail_text.extend(
                        [
                            "issued the start command : {} in 2 minutes".format(struct.start_command),
                            "",
                        ]
                    )
                self.__new_mail.init_text()
                self.__new_mail.set_subject("problem with {} on {} (meta-server)".format(key, global_config["SERVER_FULL_NAME"]))
                self.__new_mail.append_text(mail_text)
                struct.remove_meta_block()
                _sm_stat, log_lines = self.__new_mail.send_mail()
                for line in log_lines:
                    self.log(line)
                del_list.append(key)
        if _check_mem and mem_info_dict:
            self._show_meminfo(mem_info_dict)
        if del_list:
            del_list.sort()
            self.log(
                "removed {}: {}".format(
                    logging_tools.get_plural("block", len(del_list)),
                    ", ".join(del_list)
                )
            )
            for d_p in del_list:
                self._delete_msi_by_name(d_p)

    def _read_msi_from_disk(self, file_name):
        new_meta_info = process_tools.meta_server_info(file_name, self.log)
        if new_meta_info.name:
            self.log(
                "read meta_info_block for {} (file {}, info: {})".format(
                    new_meta_info.name,
                    file_name,
                    new_meta_info.get_info()
                )
            )
        else:
            self.log(
                "error reading meta_info_block from {} (name returned None)".format(file_name),
                logging_tools.LOG_LEVEL_ERROR
            )
            new_meta_info = None
        return new_meta_info

    def _delete_msi_by_name(self, msi_name):
        msi = self.__msi_dict[msi_name]
        self.log("removing MSI-block {}".format(msi_name))
        del self.__file_lut[msi.file_name]
        del self.__msi_dict[msi.name]

    def _delete_msi_by_file_name(self, file_name):
        if file_name in self.__file_lut:
            self._delete_msi_by_name(self.__file_lut[file_name])
        else:
            self.log(
                "MSI for file_name {} not defined".format(
                    file_name
                ),
                logging_tools.LOG_LEVEL_ERROR
            )

    def _update_or_create_msi_by_file_name(self, file_name):
        if file_name in self.__file_lut:
            cur_meta_info = self.__msi_dict[self.__file_lut[file_name]]
            new_meta_info = self._read_msi_from_disk(file_name)
            if new_meta_info:
                self.__msi_dict[new_meta_info.name] = new_meta_info
                new_meta_info.set_last_pid_check_ok_time(cur_meta_info.get_last_pid_check_ok_time())
                new_meta_info.pid_checks_failed = cur_meta_info.pid_checks_failed
                # self.log("updated MSI-block for {}".format(new_meta_info.name))
            else:
                self._delete_msi_by_file_name(file_name)
        else:
            # create new msi
            new_meta_info = self._read_msi_from_disk(file_name)
            if new_meta_info:
                self.__msi_dict[new_meta_info.name] = new_meta_info
                self.__file_lut[new_meta_info.file_name] = new_meta_info.name

    def _show_meminfo(self, mem_info_dict):
        act_time = time.time()
        self.__act_meminfo_line += 1
        act_meminfo_keys = sorted(mem_info_dict.keys())
        if act_meminfo_keys != self.__last_meminfo_keys or self.__act_meminfo_line > 100:
            self.__act_meminfo_line = 0
            self.__last_meminfo_keys = act_meminfo_keys
            self.log(
                "Memory info mapping: {}".format(
                    ", ".join(
                        [
                            "{:d}: {}".format(
                                act_meminfo_keys.index(key) + 1,
                                key
                            ) for key in act_meminfo_keys
                        ]
                    )
                )
            )
        if hm_classes and self.vector_socket:
            drop_com = server_command.srv_command(command="set_vector")
            mv_valid = act_time + 2 * global_config["MIN_MEMCHECK_TIME"]
            my_vector = drop_com.builder("values")
            # handle removal of old keys, track pids, TODO, FIXME
            old_keys = set(self.mis_dict.keys())
            new_keys = set()
            for key in act_meminfo_keys:
                tot_mem = 0
                for proc_name, mem_usage in mem_info_dict[key].itervalues():
                    tot_mem += mem_usage
                    f_key = (key, proc_name)
                    info_str = "memory usage of {} ({})".format(key, proc_name)
                    if f_key not in self.mis_dict:
                        self.mis_dict[f_key] = hm_classes.mvect_entry("mem.icsw.{}.{}".format(key, proc_name), info=info_str, default=0, unit="Byte", base=1024)
                    self.mis_dict[f_key].update(mem_usage)
                    self.mis_dict[f_key].info = info_str
                    self.mis_dict[f_key].valid_until = mv_valid
                    new_keys.add(f_key)
                    my_vector.append(self.mis_dict[f_key].build_xml(drop_com.builder))
                if proc_name not in self.mis_dict:
                    self.mis_dict[key] = hm_classes.mvect_entry(
                        "mem.icsw.{}.total".format(key),
                        info="memory usage of {}".format(key),
                        default=0,
                        unit="Byte",
                        base=1024
                    )
                self.mis_dict[key].update(tot_mem)
                self.mis_dict[key].valid_until = mv_valid
                new_keys.add(key)
                my_vector.append(self.mis_dict[key].build_xml(drop_com.builder))
            drop_com["vector"] = my_vector
            drop_com["vector"].attrib["type"] = "vector"
            self.vector_socket.send_unicode(unicode(drop_com))
            del_keys = old_keys - new_keys
            if del_keys:
                self.log("removing {} from mis_dict".format(logging_tools.get_plural("key", len(del_keys))))
                for del_key in del_keys:
                    del self.mis_dict[del_key]
        self.log(
            "Memory info: {}".format(
                " / ".join(
                    [
                        process_tools.beautify_mem_info(
                            sum(
                                [
                                    value[1] for value in mem_info_dict.get(key, {}).itervalues()
                                ]
                            ),
                            short=True
                        ) for key in act_meminfo_keys
                    ]
                )
            )
        )

    def loop_post(self):
        self.network_unbind()
        # close vector socket if set
        if self.vector_socket:
            self.vector_socket.close()
        self.__log_template.close()
