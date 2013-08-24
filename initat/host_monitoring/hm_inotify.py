#!/usr/bin/python-init -Otu
# -*- coding: utf-8 -*-
#
# Copyright (C) 2013 Andreas Lang-Nevyjel
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

import configfile
import difflib
import fnmatch
import inotify_tools
import logging_tools
import netifaces
import os
import process_tools
import server_command
import threading_tools
import time
import uuid
import uuid_tools
import zmq

from lxml import etree # @UnresolvedImport
from lxml.builder import E # @UnresolvedImport

from initat.host_monitoring.config import global_config
from initat.host_monitoring.constants import TIME_FORMAT

class file_watcher(object):
    def __init__(self, process_obj, **args):
        self.__process = process_obj
        self.mode = args.get("mode", "content")
        # exit flag
        self.__exit_flag = False
        # check for valid id, target_server and target_port
        self.fw_id = args.get("id", "")
        # files and dirs
        self.__act_files, self.__act_dirs = (set([]), [])
        self.__new_files = []
        self.__use_inotify = not "poll" in args
        if not self.fw_id:
            raise ValueError, "ID not given or empty ID"
        if self.mode == "content":
            # watch the content of files
            self.target_server = args.get("target_server", "")
            if not self.target_server:
                raise ValueError, "target_server not given or empty"
            try:
                self.target_port = int(args.get("target_port", ""))
            except:
                raise ValueError, "target_port not given or not integer"
            # name of file to check
            if "name" in args:
                self.search_mode = "file"
                self.__new_files = set([args["name"]])
                if not self.__new_files:
                    raise ValueError, "name of file to watch not given or empty"
                self.__fixed_name = True
            elif "dir" in args and "match" in args:
                self.search_mode = "dir"
                self.dir_name, self.match_name = (os.path.normpath(args["dir"]), args["match"])
                if not self.dir_name or not self.match_name:
                    raise ValueError, "dir or match not given or empty"
                self.__new_files = set([])
                self.__fixed_name = False
            else:
                raise ValueError, "neither file_name nor dir/match info given"
        elif self.mode == "timeout":
            # check for timeout on files or dirs
            if "dir" in args:
                self.dir_name = os.path.normpath(args["dir"])
            else:
                raise ValueError, "no directory name given for timeout check"
            self.search_mode = "dir"
            if "timeout" in args:
                self.__timeout = int(args["timeout"])
            else:
                raise ValueError, "no timeout given for timeout check"
            if "action" in args:
                self.__action = args["action"]
            else:
                raise ValueError, "no action given for timeout check"
        else:
            raise ValueError, "unknown mode %s" % (self.mode)
        self.log("created filewatcher object (mode is %s)" % (self.mode))
        for args_key in sorted(args.keys()):
            self.log(" - %-20s: %s" % (args_key, args[args_key]))
        # check for inotify-support
        self.__inotify_support = (self.__thread.get_inotify_watcher() and True or False) if self.__use_inotify else False
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
        self.content, self.__content_send, self.__send_pending, self.__content_update = ({}, True, False, time.time())
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
            self.log("unregistering from inotify watcher (%s, %s)" % (
                logging_tools.get_plural("file", len(self.__act_files)),
                logging_tools.get_plural("directory", len(self.__act_dirs))))
            if self.__act_files:
                for act_file in self.__act_files:
                    self.__thread.get_inotify_watcher().remove_watcher(self.fw_id, act_file)
            if self.__act_dirs:
                for act_dir in self.__act_dirs:
                    self.__thread.get_inotify_watcher().remove_watcher(self.fw_id, act_dir)
            self.__inotify_link = False
    def set_result(self, what):
        self.__send_pending = False
        self.__content_send = True
        try:
            srv_res = server_command.server_reply(what)
        except:
            self.log("error decoding server_reply: %s" % (process_tools.get_except_info()),
                     logging_tools.LOG_LEVEL_ERROR)
        else:
            res_state = srv_res.get_state()
            self.log("send content (%d): %s" % (srv_res.get_state(),
                                                srv_res.get_result()))
            if res_state:
                self._problem("server at %s (port %d) returned an error" % (self.target_server,
                                                                            self.target_port))
            else:
                self._no_problem()
    def set_error(self, errnum, what):
        self.__send_pending = False
        self.log("error (%d): %s" % (errnum, what), logging_tools.LOG_LEVEL_ERROR)
        self._problem("network error (%d): %s" % (errnum, what))
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__process.log("[fw %s, %s] %s" % (self.fw_id, self.mode, what), lev)
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
                    for dir_path, dir_names, file_names in os.walk(self.dir_name):
                        if dir_path not in act_dirs:
                            act_dirs.append(dir_path)
                        if self.mode == "content":
                            match_files = [f_name for f_name in [os.path.join(dir_path, p_name) for p_name in fnmatch.filter(file_names, self.match_name)] if f_name not in self.__act_files]
                            if match_files:
                                for m_file in match_files:
                                    self._register_file(m_file)
                    act_dirs = [os.path.normpath(act_dir) for act_dir in act_dirs]
                    new_dirs = [dir_name for dir_name in act_dirs if dir_name not in self.__act_dirs]
                    old_dirs = sorted([dir_name for dir_name in self.__act_dirs if dir_name not in act_dirs])
                    if new_dirs:
                        self.log("registering to inotify watcher (mask %d [%s], %s: %s)" % (reg_mask,
                                                                                            inotify_tools.mask_to_str(reg_mask),
                                                                                            logging_tools.get_plural("directory", len(new_dirs)),
                                                                                            ", ".join(sorted(new_dirs))))
                        for add_dir in new_dirs:
                            self.__thread.get_inotify_watcher().add_watcher(self.fw_id,
                                                                            add_dir,
                                                                            reg_mask,
                                                                            self._process_event)
                        self.__act_dirs.extend(new_dirs)
                    if old_dirs:
                        self.log("removing %s: %s" % (logging_tools.get_plural("directory", len(old_dirs)),
                                                      ", ".join(old_dirs)))
                        for del_dir in old_dirs:
                            self.__act_dirs.remove(del_dir)
                            self.__thread.get_inotify_watcher().remove_watcher(self.fw_id, del_dir)
                    self.__inotify_link = True
        else:
            if self.search_mode == "file":
                # not used right now, FIXME
                pass
            else:
                for dir_path, dir_names, file_names in os.walk(self.dir_name):
                    if self.mode == "content":
                        for m_file in [os.path.join(dir_path, p_name) for p_name in fnmatch.filter(file_names, self.match_name)]:
                            self._register_file(m_file)
    def _process_event(self, event):
        self.__queue.put(("inotify_event", (self, event)))
    def _inotify_event(self, event):
        if not self.__shutdown:
            if self.__glob_config["VERBOSE"]:
                self.log("Got inotify_event for path '%s', name '%s' (mask 0x%x [%s], dir is %s)" % (event.path,
                                                                                                     event.name,
                                                                                                     event.mask,
                                                                                                     inotify_tools.mask_to_str(event.mask),
                                                                                                     event.dir))
            # shortcut, can be improved
            self.update(event)
    def _hello_timeout(self):
        act_time = time.time()
        act_to = abs(act_time - self.__last_update)
        if act_to > self.__timeout:
            if os.path.isdir(self.dir_name):
                self.log("timeout of %s > %s reached" % (logging_tools.get_diff_time_str(act_to),
                                                         logging_tools.get_diff_time_str(self.__timeout)))
                # if os.path.isfile
                if os.path.isfile(self.__action.split()[0]):
                    start_ok, log_lines = process_tools.submit_at_command(self.__action)
                    for line in log_lines:
                        self.log(line)
                else:
                    self.log("cannot submit '%s' (command not found)" % (self.__action.split()[0]),
                             logging_tools.LOG_LEVEL_WARN)
                self.__last_update = act_time
            else:
                self.log("watch_directory %s no longer present, exiting" % (self.dir_name),
                         logging_tools.LOG_LEVEL_WARN)
                self.__exit_flag = True
    def _hello_blind(self):
        pass
    def _register_file(self, new_file):
        if self.__use_inotify:
            if new_file not in self.__act_files:
                self.__act_files.add(new_file)
                reg_mask = inotify_tools.IN_MODIFY | inotify_tools.IN_CLOSE_WRITE | inotify_tools.IN_DELETE | inotify_tools.IN_DELETE_SELF | inotify_tools.IN_CREATE
                self.log("adding file %s to inotify_watcher (mask %d [%s])" % (new_file,
                                                                               reg_mask,
                                                                               inotify_tools.mask_to_str(reg_mask)))
                self.__thread.get_inotify_watcher().add_watcher(self.fw_id,
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
                                new_file = "%s/%s" % (event.path, event.name)
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
                                self.log("removing file %s from inotify_watcher" % (del_file))
                                self.__act_files.remove(del_file)
                                self.__thread.get_inotify_watcher().remove_watcher(self.fw_id, del_file)
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
            self.log("error reading file %s: %s" % (f_name,
                                                    process_tools.get_except_info()),
                     logging_tools.LOG_LEVEL_ERROR)
        else:
            if self.__glob_config["VERBOSE"]:
                self.log("checking content of %s" % (f_name))
            if new_content != self.content.get(f_name, ""):
                self.log("content of %s has changed (old: %s, new: %s)" % (f_name,
                                                                           logging_tools.get_plural("byte", len(self.content.get(f_name, ""))),
                                                                           logging_tools.get_plural("byte", len(new_content))))
                self.__content_update = time.time()
                self.content[f_name] = new_content
                self.__content_send = False
            if self.target_port:
                # send content
                if not self.__content_send and not self.__send_pending:
                    self.__send_pending = True
                    self.log("init sending of %s to %s (port %d)" % (logging_tools.get_plural("byte", len(self.content.get(f_name, ""))),
                                                                     self.target_server,
                                                                     self.target_port))
                    self.__thread.send_srv_command(self, self.target_server, self.target_port, server_command.server_command(command="file_watch_content",
                                                                                                                             option_dict={"name"    : f_name,
                                                                                                                                          "content" : self.content.get(f_name, ""),
                                                                                                                                          "id"      : self.fw_id,
                                                                                                                                          "update"  : self.__content_update}))
            else:
                # zero target_port, ignore sending
                self.__content_send = True
    def _problem(self, what):
        self.num_fail += 1
        self.log("%s (fail_counter is %d of %d)" % (what,
                                                    self.num_fail,
                                                    self.__glob_config["FW_FAIL_COUNTER"]),
                 logging_tools.LOG_LEVEL_WARN)
        if self.num_fail > self.__glob_config["FW_FAIL_COUNTER"]:
            self.log("fail_counter reached treshold, remove file_watcher",
                     logging_tools.LOG_LEVEL_CRITICAL)
            self.__thread._remove_file_watcher(self.fw_id)
    def _no_problem(self):
        if self.num_fail:
            self.log("clearing num_fail counter (was %d)" % (self.num_fail), logging_tools.LOG_LEVEL_WARN)
            self.num_fail = 0

class inotify_process(threading_tools.process_obj):
    def process_init(self):
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context)
        self.__relayer_socket = self.connect_to_socket("internal")
        self.__watcher = inotify_tools.inotify_watcher()
        self.register_timer(self._check, 1)
        # self.register_func("connection", self._connection)
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)
    def _check(self):
        self.__watcher.check(1000)
    def loop_post(self):
        self.__log_template.close()
        self.__relayer_socket.close()
