# -*- coding: utf-8 -*-
#
# Copyright (C) 2013-2015 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of host-monitoring
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

""" host-monitoring, inotify thread """

import fnmatch
import os
import stat
import time

from initat.host_monitoring.config import global_config
from initat.tools import inotify_tools, logging_tools, process_tools, server_command, \
    threading_tools, uuid_tools
import zmq


class HMFileWatcher(object):
    global_id = 1

    def __init__(self, process_obj, **kwargs):
        self.__process = process_obj
        self.mode = kwargs.get("mode", "content")
        self.comment = kwargs.get("comment", "")
        # verbose flag
        self.__verbose = global_config["VERBOSE"]
        # exit flag
        self.__exit_flag = False
        # check for valid id, target_server and target_port
        self.fw_id = "fw{}".format(HMFileWatcher.global_id)  # args.get("id", "")
        self.send_id = kwargs["send_id"]
        HMFileWatcher.global_id += 1
        # files and dirs
        self.__act_files, self.__act_dirs = (set([]), [])
        self.__new_files = []
        self.__use_inotify = "poll" not in kwargs
        # simple filter, for instance to check for loop output in OUTCAR
        self.line_filter = kwargs.get("line_filter", "").lower()
        # if not self.fw_id:
        #    raise ValueError, "ID not given or empty ID"
        if self.mode == "content":
            # watch the content of files
            self.target_server = kwargs.get("target_server", "")
            if not self.target_server:
                raise ValueError("target_server not given or empty")
            try:
                self.target_port = int(kwargs.get("target_port", ""))
            except:
                raise ValueError("target_port not given or not integer")
            # name of file to check
            if "name" in kwargs:
                self.search_mode = "file"
                self.__new_files = set([kwargs["name"]])
                if not self.__new_files:
                    raise ValueError("name of file to watch not given or empty")
                self.__fixed_name = True
            elif "dir" in kwargs and "match" in kwargs:
                self.search_mode = "dir"
                self.dir_name, self.match_name = (os.path.normpath(kwargs["dir"]), kwargs["match"])
                if not self.dir_name or not self.match_name:
                    raise ValueError("dir or match not given or empty")
                self.__new_files = set([])
                self.__fixed_name = False
            else:
                raise ValueError("neither file_name nor dir/match info given")
        elif self.mode == "timeout":
            # check for timeout on files or dirs
            if "dir" in kwargs:
                self.dir_name = os.path.normpath(kwargs["dir"])
            else:
                raise ValueError("no directory name given for timeout check")
            self.search_mode = "dir"
            if "timeout" in kwargs:
                self.__timeout = int(kwargs["timeout"])
            else:
                raise ValueError("no timeout given for timeout check")
            if "action" in kwargs:
                self.__action = kwargs["action"]
            else:
                raise ValueError("no action given for timeout check")
        else:
            raise ValueError("unknown mode {}".format(self.mode))
        self.log("created filewatcher object (mode is {})".format(self.mode))
        for args_key in sorted(kwargs.keys()):
            self.log(" - {:<20s}: {}".format(args_key, kwargs[args_key]))
        # check for inotify-support
        self.__inotify_support = (self.__process.inotify_watcher and True or False) if self.__use_inotify else False
        self.__inotify_link = False
        if self.mode == "content":
            self._init_content_mode()
        elif self.mode == "timeout":
            self._init_timeout_mode()
        # process of shutting down ?
        self.__shutdown = False

    def do_exit(self):
        return self.__exit_flag

    def _init_content_mode(self):
        self.hello = self._hello_blind
        # directories to search
        self.content, self.__content_update = ({}, time.time())
        self.num_fail = 0
        self._search_dir(False)

    def _init_timeout_mode(self):
        self.hello = self._hello_timeout
        self.__last_update = time.time()
        self._search_dir(True)

    def inotify(self):
        return self.__inotify_link

    def close(self):
        self.__shutdown = True
        self._remove_inotify_link()
        self.log("exiting")

    def _remove_inotify_link(self):
        # check for inotify-support
        if self.__inotify_link:
            self.log("unregistering from inotify watcher ({}, {})".format(
                logging_tools.get_plural("file", len(self.__act_files)),
                logging_tools.get_plural("directory", len(self.__act_dirs))))
            if self.__act_files:
                for act_file in self.__act_files:
                    self.__process.inotify_watcher.remove_watcher(self.fw_id, act_file)
            if self.__act_dirs:
                for act_dir in self.__act_dirs:
                    self.__process.inotify_watcher.remove_watcher(self.fw_id, act_dir)
            self.__inotify_link = False

    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__process.log("[fw {}, {}] {}".format(self.fw_id, self.mode, what), lev)

    def _search_dir(self, any_change):
        if any_change:
            reg_mask = inotify_tools.IN_MODIFY | inotify_tools.IN_CLOSE_WRITE | inotify_tools.IN_DELETE | inotify_tools.IN_CREATE | inotify_tools.IN_DELETE_SELF
        else:
            reg_mask = inotify_tools.IN_CLOSE_WRITE | inotify_tools.IN_DELETE | inotify_tools.IN_CREATE | inotify_tools.IN_DELETE_SELF
        if self.__inotify_support:
            if self.search_mode == "file":
                for act_file in self.__new_files:
                    if os.path.isfile(act_file):
                        self._register_file(act_file)
                self.__new_files = set([])
                self.__inotify_link = True
            else:
                if self.dir_name:
                    act_dirs = [self.dir_name]
                    for dir_path, _dir_names, file_names in os.walk(self.dir_name):
                        if dir_path not in act_dirs:
                            act_dirs.append(dir_path)
                        if self.mode == "content":
                            match_files = [
                                f_name for f_name in [
                                    os.path.join(dir_path, p_name) for p_name in fnmatch.filter(file_names, self.match_name)
                                ] if f_name not in self.__act_files
                            ]
                            if match_files:
                                for m_file in match_files:
                                    self._register_file(m_file)
                    act_dirs = [os.path.normpath(act_dir) for act_dir in act_dirs]
                    new_dirs = [dir_name for dir_name in act_dirs if dir_name not in self.__act_dirs]
                    old_dirs = sorted([dir_name for dir_name in self.__act_dirs if dir_name not in act_dirs])
                    if new_dirs:
                        self.log(
                            "registering to inotify watcher (mask {:d} [{}], {}: {})".format(
                                reg_mask,
                                inotify_tools.mask_to_str(reg_mask),
                                logging_tools.get_plural("directory", len(new_dirs)),
                                ", ".join(sorted(new_dirs))
                            )
                        )
                        for add_dir in new_dirs:
                            self.__process.inotify_watcher.add_watcher(
                                self.fw_id,
                                add_dir,
                                reg_mask,
                                self._process_event
                            )
                        self.__act_dirs.extend(new_dirs)
                    if old_dirs:
                        self.log(
                            "removing {}: {}".format(
                                logging_tools.get_plural("directory", len(old_dirs)),
                                ", ".join(old_dirs)
                            )
                        )
                        for del_dir in old_dirs:
                            self.__act_dirs.remove(del_dir)
                            self.__process.inotify_watcher.remove_watcher(self.fw_id, del_dir)
                    self.__inotify_link = True
        else:
            if self.search_mode == "file":
                # not used right now, FIXME
                pass
            else:
                for dir_path, _dir_names, file_names in os.walk(self.dir_name):
                    if self.mode == "content":
                        for m_file in [os.path.join(dir_path, p_name) for p_name in fnmatch.filter(file_names, self.match_name)]:
                            self._register_file(m_file)

    def _process_event(self, event):
        if self.__verbose:
            self.log(
                "Got inotify_event for path '{}', name '{}' (mask 0x{:x} [{}], dir is {})".format(
                    event.path,
                    event.name,
                    event.mask,
                    inotify_tools.mask_to_str(event.mask),
                    event.dir
                )
            )
        self.update(event)

    def _hello_timeout(self):
        act_time = time.time()
        act_to = abs(act_time - self.__last_update)
        if act_to > self.__timeout:
            if os.path.isdir(self.dir_name):
                self.log(
                    "timeout of {} > {} reached".format(
                        logging_tools.get_diff_time_str(act_to),
                        logging_tools.get_diff_time_str(self.__timeout)))
                # if os.path.isfile
                if os.path.isfile(self.__action.split()[0]):
                    _start_ok, log_lines = process_tools.submit_at_command(self.__action)
                    for line in log_lines:
                        self.log(line)
                else:
                    self.log(
                        "cannot submit '{}' (command not found)".format(
                            self.__action.split()[0]
                        ),
                        logging_tools.LOG_LEVEL_WARN
                    )
                self.__last_update = act_time
            else:
                self.log("watch_directory {} no longer present, exiting".format(self.dir_name),
                         logging_tools.LOG_LEVEL_WARN)
                self.__exit_flag = True

    def _hello_blind(self):
        pass

    def _register_file(self, new_file):
        if self.__use_inotify:
            if new_file not in self.__act_files:
                self.__act_files.add(new_file)
                reg_mask = inotify_tools.IN_MODIFY | inotify_tools.IN_CLOSE_WRITE | \
                    inotify_tools.IN_DELETE | inotify_tools.IN_DELETE_SELF | inotify_tools.IN_CREATE
                self.log(
                    "adding file {} to inotify_watcher (mask {:d} [{}])".format(
                        new_file,
                        reg_mask,
                        inotify_tools.mask_to_str(reg_mask)
                    )
                )
                self.__process.inotify_watcher.add_watcher(
                    self.fw_id,
                    new_file,
                    reg_mask,
                    self._process_event)
                self._check_content(new_file)
        else:
            if new_file not in self.__act_files:
                self.__act_files.add(new_file)
            self._check_content(new_file)

    def update(self, event=None):
        if self.mode == "timeout":
            self.__last_update = time.time()
        if event:
            # path for inotify based operation
            if event.name:
                full_path = os.path.join(event.path, event.name)
            else:
                full_path = event.path
            if event.mask & inotify_tools.IN_CREATE:
                if event.mask & inotify_tools.IN_ISDIR:
                    # new dir created
                    self.log("new directory created, checking list")
                    self._search_dir(False)
                else:
                    if self.mode == "content":
                        # new file created
                        if event.name and fnmatch.fnmatch(event.name, self.match_name):
                            # match pattern ?
                            if self.__inotify_support:
                                new_file = os.path.join(event.path, event.name)
                                if new_file not in self.__act_files:
                                    self._register_file(new_file)
                            else:
                                self.log("No inotify_support found", logging_tools.LOG_LEVEL_ERROR)
            elif event.mask & (inotify_tools.IN_DELETE_SELF | inotify_tools.IN_DELETE):
                if event.dir:
                    self.log("directory deleted, checking list")
                    if full_path == self.dir_name:
                        self.log("root directory deleted, triggering exit")
                        self.__exit_flag = True
                    else:
                        self._search_dir(False)
                else:
                    if self.mode == "content":
                        if event.mask & inotify_tools.IN_DELETE_SELF:
                            if event.path in self.__act_files:
                                del_file = event.path
                                self.log("removing file {} from inotify_watcher".format(del_file))
                                self.__act_files.remove(del_file)
                                self.__process.inotify_watcher.remove_watcher(self.fw_id, del_file)
                            else:
                                # delete for unwatched filed
                                pass
            else:
                if self.mode == "content":
                    if full_path not in self.__act_files and fnmatch.fnmatch(event.name, self.match_name):
                        self._register_file(full_path)
                    if full_path in self.__act_files:
                        self._check_content(full_path)
        else:
            # path for non-inotify based operation
            self._search_dir(False)

    def _check_content(self, f_name):
        try:
            new_content = file(f_name, "r").read()
        except:
            self.log(
                "error reading file {}: {}".format(
                    f_name,
                    process_tools.get_except_info()
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
        else:
            if self.__verbose:
                self.log("checking content of {}".format(f_name))
            if self.line_filter:
                if self.__verbose:
                    self.log("applying line_filter '{}'".format(self.line_filter))
                new_content = "\n".join([_line for _line in new_content.split("\n") if _line.lower().count(self.line_filter)])
            if new_content != self.content.get(f_name, ""):
                self.log(
                    "content of {} has changed (old: {}, new: {})".format(
                        f_name,
                        logging_tools.get_plural("byte", len(self.content.get(f_name, ""))),
                        logging_tools.get_plural("byte", len(new_content))
                    )
                )
                self.__content_update = time.time()
                self.content[f_name] = new_content
                if self.target_port:
                    # send content
                    self.log(
                        "init sending of {} to {} (port {:d})".format(
                            logging_tools.get_plural("byte", len(self.content.get(f_name, ""))),
                            self.target_server,
                            self.target_port
                        )
                    )
                    try:
                        file_stat = os.stat(f_name)
                        send_com = server_command.srv_command(
                            command="file_watch_content",
                            name=f_name,
                            uid="{:d}".format(file_stat[stat.ST_UID]),
                            gid="{:d}".format(file_stat[stat.ST_GID]),
                            mode="{:d}".format(file_stat[stat.ST_MODE]),
                            comment=self.comment,
                            content=self.content.get(f_name, ""),
                            last_change="{:d}".format(int(file_stat[stat.ST_MTIME])),
                            id=self.fw_id,
                            send_id=self.send_id,
                            update=self.__content_update
                        )
                    except:
                        self.log(
                            "cannot init file_content: {}".format(
                                process_tools.get_except_info()
                            ),
                            logging_tools.LOG_LEVEL_ERROR
                        )
                    else:
                        self.__process.send_to_server(
                            self.target_server,
                            self.target_port,
                            send_com)


class HMInotifyProcess(threading_tools.process_obj):
    def process_init(self):
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], context=self.zmq_context)
        self.__watcher = inotify_tools.InotifyWatcher()
        # was INOTIFY_IDLE_TIMEOUT in global_config, now static
        self.__idle_timeout = 5
        # self.__watcher.add_watcher("internal", "/etc/sysconfig/host-monitoring.d", inotify_tools.IN_CREATE | inotify_tools.IN_MODIFY, self._trigger)
        self.__file_watcher_dict = {}
        self.__target_dict = {}
        # self.register_func("connection", self._connection)
        self.send_pool_message("register_callback", "register_file_watch", "fw_handle")
        self.send_pool_message("register_callback", "unregister_file_watch", "fw_handle")
        self.register_exception("term_error", self._sigint)
        self.allow_signal(15)
        self.register_func("fw_handle", self._fw_handle)
        # register watcher fd with 0MQ poller
        self.register_poller(self.__watcher._fd, zmq.POLLIN, self._inotify_check)
        self.log("idle_timeout is {:d}".format(self.__idle_timeout))
        self.register_timer(self._fw_timeout, 1000)

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)

    def _sigint(self, err_cause):
        self.log(" got sigint '{}'".format(err_cause), logging_tools.LOG_LEVEL_ERROR)

    def _trigger(self, event):
        print event, "*", dir(event)

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

    def _fw_timeout(self):
        remove_ids = []
        for fw_id, fw_struct in self.__file_watcher_dict.iteritems():
            if not fw_struct.inotify():
                # huh ? FIXME, argument missing
                fw_struct.update()
            fw_struct.hello()
            if fw_struct.do_exit():
                remove_ids.append(fw_id)
        if remove_ids:
            self.log(
                "removing {}: {}".format(
                    logging_tools.get_plural("watcher_id", len(remove_ids)),
                    ", ".join(remove_ids)
                )
            )
            dummy_com = server_command.srv_command(command="dummy")
            dummy_com["result"] = None
            for rem_id in remove_ids:
                self._unregister_file_watch(dummy_com, {"id": rem_id})

    @property
    def inotify_watcher(self):
        return self.__watcher

    def _fw_handle(self, *args, **kwargs):
        src_id, data = args
        srv_com = server_command.srv_command(source=data)
        in_com = srv_com["command"].text
        args = {}
        if "arguments" in srv_com:
            for entry in srv_com["arguments"]:
                _val = entry.text
                if _val.lower() in ["true", "false"]:
                    _val = bool(_val)
                elif _val.isdigit():
                    _val = int(_val)
                # if
                args[entry.tag.split("}")[-1]] = _val
        self.log("got '{}', {}: {}".format(
            in_com,
            logging_tools.get_plural("argument", len(args)),
            ", ".join(["{}='{}' ({})".format(key, value, type(value)) for key, value in args.iteritems()])
            ))
        args = {key.replace("-", "_"): value for key, value in args.iteritems()}
        found_keys = set(args.keys())
        needed_keys = {
            "register_file_watch": set(
                [
                    "send_id", "mode", "target_server", "target_port", "dir", "match"
                ]
            ),
            "unregister_file_watch": set(
                [
                    "id"
                ]
            ),
        }.get(in_com, set())
        if needed_keys & found_keys == needed_keys:
            # set default return value
            srv_com.set_result(
                "got command {}".format(in_com)
            )
            try:
                getattr(self, "_{}".format(in_com))(srv_com, args)
            except:
                exc_info = process_tools.exception_info()
                for line in exc_info.log_lines:
                    self.log("  {}".format(line), logging_tools.LOG_LEVEL_ERROR)
                srv_com.set_result(
                    "error processing '{}': {}".format(in_com, exc_info.except_info),
                    server_command.SRV_REPLY_STATE_CRITICAL
                )
            log_str, log_level = srv_com.get_log_tuple()
            self.log("result: {}".format(log_str), log_level)
        else:
            srv_com.set_result(
                "command {}, keys missing: {}".format(in_com, ", ".join(needed_keys - found_keys)),
                server_command.SRV_REPLY_STATE_ERROR
            )
        self.send_pool_message("callback_result", src_id, unicode(srv_com))

    def _register_file_watch(self, cur_com, kwargs):
        new_fw = HMFileWatcher(self, **kwargs)
        self.__file_watcher_dict[new_fw.fw_id] = new_fw
        cur_com.set_result(
            "{}".format(new_fw.fw_id)
        )

    def _unregister_file_watch(self, cur_com, kwargs):
        fw_id = kwargs["id"]
        if fw_id:
            if fw_id in self.__file_watcher_dict:
                self.__file_watcher_dict[fw_id].close()
                del self.__file_watcher_dict[fw_id]
                cur_com.set_result(
                    "ok removed ID {}".format(fw_id),
                )
            else:
                self.log("cannot remove HMFileWatcher entry with id {} (present: {})".format(
                    fw_id,
                    self.__file_watcher_dict and ", ".join(self.__file_watcher_dict.keys()) or "none"), logging_tools.LOG_LEVEL_ERROR)
                cur_com.set_result(
                    "ID {} not found".format(fw_id),
                    server_command.SRV_REPLY_STATE_ERROR
                )
        else:
            cur_com.set_result(
                "ID {} not found".format(fw_id),
                server_command.SRV_REPLY_STATE_ERROR
            )

    def send_to_server(self, target_server, target_port, srv_com):
        targ_str = "tcp://{}:{:d}".format(target_server, target_port)
        if targ_str not in self.__target_dict:
            send_socket = self.zmq_context.socket(zmq.DEALER)  # @UndefinedVariable
            send_socket.setsockopt(zmq.LINGER, 0)  # @UndefinedVariable
            send_socket.setsockopt(zmq.IDENTITY, "{}_csin".format(uuid_tools.get_uuid().get_urn()))  # @UndefinedVariable
            send_socket.connect(targ_str)
            send_socket.setsockopt(zmq.SNDHWM, 16)  # @UndefinedVariable
            send_socket.setsockopt(zmq.RCVHWM, 16)  # @UndefinedVariable
            send_socket.setsockopt(zmq.RECONNECT_IVL_MAX, 500)  # @UndefinedVariable
            send_socket.setsockopt(zmq.RECONNECT_IVL, 200)  # @UndefinedVariable
            send_socket.setsockopt(zmq.TCP_KEEPALIVE, 1)  # @UndefinedVariable
            send_socket.setsockopt(zmq.TCP_KEEPALIVE_IDLE, 300)  # @UndefinedVariable
            self.log("init connection to {}".format(targ_str))
            self.__target_dict[targ_str] = send_socket
        self.__target_dict[targ_str].send_unicode(unicode(srv_com))

    def loop_post(self):
        for targ_str, targ_sock in self.__target_dict.iteritems():
            self.log("closing socket to {}".format(targ_str))
            targ_sock.close()
        self.__log_template.close()
