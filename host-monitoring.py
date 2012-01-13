#!/usr/bin/python-init -Otu
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008,2009,2010,2011 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
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
""" host monitor """

import time
import sys
import os
import struct
import socket
import signal
import getopt
import threading_tools
import logging_tools
import net_tools
import process_tools
import configfile
import textwrap
import difflib
import limits
import hm_classes
import uuid_tools
import server_command
import fnmatch
import pprint
import optparse

# non-critical functions
try:
    import mysql_tools
except ImportError:
    mysql_tools = None

try:
    import inotify_tools
except ImportError:
    inotify_tools = None
    
try:
    from collserver_version import VERSION_STRING
except ImportError:
    VERSION_STRING = "unknown-unknown"

STR_LEN              = 256
STD_PORT             = 2001
STD_COM_PORT         = 2005
RELAYER_PORT         = 2004
RELAY_REQUEST_HEADER = "RREQ"

class error(Exception):
    def __init__(self, value="Not set"):
        Exception.__init__(self)
        self.value = value
    def __str__(self):
        return self.value

class term_error(error):
    def __init__(self):
        error.__init__(self)
    
class alarm_error(error):
    def __init__(self):
        error.__init__(self)
    
class int_error(error):
    def __init__(self):
        error.__init__(self)

def sig_term_handler(signum, frame):
    raise term_error

def sig_alarm_handler(signum, frame):
    raise alarm_error

def sig_int_handler(signum, frame):
    raise int_error

def prepare_server_request(comline, in_dict, **args):
    mod_stuff, ret_str = (None, "")
    net = args.get("from_net")
    if comline:
        command = comline.split()[0]
        if not command:
            ret_str = "unknown NULL command"
        elif type(command) != type(""):
            ret_str = "unknown type of command"
        elif command in in_dict.keys():
            mod_stuff = in_dict[command]
            if mod_stuff.net_only and not net:
                ret_str, mod_stuff = ("error only available via network", None)
            elif mod_stuff.relay_call:
                ret_str, mod_stuff = ("error not a relay call", None)
        else:
            ret_str = "unknown command %s" % (command)
    else:
        ret_str = "unknown NULL command"
    return ret_str, mod_stuff

# ----------------------------------------------------------
# built-in functions

class my_modclass(hm_classes.hm_fileinfo):
    def __init__(self, **args):
        hm_classes.hm_fileinfo.__init__(self, "global", "global stuff", **args)

class status_command(hm_classes.hmb_command):
    def __init__(self, **args):
        hm_classes.hmb_command.__init__(self, "status", **args)
    def server_call(self, cm):
        #print dir(mod_info)#+mod_info.get_thread_pool()
        try:
            rets = file("/var/run/.hoststat", "r").readlines()[0].strip()
        except:
            rets = "hoststat file not found: %s" % (process_tools.get_except_info())
        else:
            pass
        tp = self.thread_pool
        if tp:
            num_threads, num_ok = (tp.num_threads(False),
                                   tp.num_threads_running(False))
            if num_ok == num_threads:
                rets = "ok all %d threads running, %s" % (num_ok, rets)
            else:
                rets = "error only %d of %d threads running, %s" % (num_ok, num_threads, rets)
        else:
            rets = "warning no thread_pool found, %s" % (rets)
        return rets
    def client_call(self, result, parsed_coms):
        return limits.nag_STATE_OK, "Host status: %s" % (result)

class poweroff_command(hm_classes.hmb_command):
    def __init__(self, **args):
        hm_classes.hmb_command.__init__(self, "poweroff", **args)
    def server_call(self, cm):
        return "not supported"
    def client_call(self, result, parsed_coms):
        if result.split()[0] == "poweroff":
            return limits.nag_STATE_OK, "Host is doing a poweroff"
        else:
            return limits.nag_STATE_WARNING, "Host returned %s" % (result)
        
class reboot_command(hm_classes.hmb_command):
    def __init__(self, **args):
        hm_classes.hmb_command.__init__(self, "reboot", **args)
    def server_call(self, cm):
        return "not supported"
    def client_call(self, result, parsed_coms):
        if result.split()[0] == "rebooting":
            return limits.nag_STATE_OK, "Host is rebooting"
        else:
            return limits.nag_STATE_WARNING, "Host returned %s" % (result)
        
class halt_command(hm_classes.hmb_command):
    def __init__(self, **args):
        hm_classes.hmb_command.__init__(self, "halt", **args)
    def server_call(self, cm):
        return "not supported"
    def client_call(self, result, parsed_coms):
        if result.split()[0] == "rebooting":
            return limits.nag_STATE_OK, "Host is halting"
        else:
            return limits.nag_STATE_WARNING, "Host returned %s" % (result)
        
class version_command(hm_classes.hmb_command):
    def __init__(self, **args):
        hm_classes.hmb_command.__init__(self, "version", **args)
    def server_call(self, cm):
        return VERSION_STRING
    def client_call(self, result, parsed_coms):
        return limits.nag_STATE_OK, "Server version: %s" % (result)
        
class exit_command(hm_classes.hmb_command):
    def __init__(self, **args):
        hm_classes.hmb_command.__init__(self, "exit", **args)
        
class direct_command(hm_classes.hmb_command):
    def __init__(self, **args):
        hm_classes.hmb_command.__init__(self, "direct", **args)
        
class relay_info_command(hm_classes.hmb_command):
    def __init__(self, **args):
        hm_classes.hmb_command.__init__(self, "relay_info", **args)
        self.special_hook = "relay_info"
        self.relay_call = True

class dummy_class(object):
    def __init__(self):
        pass
    
# end of built-in functions
# ----------------------------------------------------------

class all_modules(object):
    def __init__(self, glob_config, logger):
        self.__glob_config = glob_config
        self.__modules, self.__commands = ({}, {})
        self._load_modules(logger)
        self.module_init("i", logger)
    def add_module(self, module):
        self.__modules[module.name] = module
        self.__last_module = module
    def add_command(self, command):
        self.__commands[command.name] = command
        self.__last_module.add_command(command)
    def module_keys(self):
        return self.__modules.keys()
    def get_module(self, mod_name):
        return self.__modules[mod_name]
    def _load_modules(self, logger):
        #print "Loading..."
        self.load_errors = []
        logger.info("Searching for modules in %s ..." % (self.__glob_config["MODULE_DIR"]))
        sys.path.append(self.__glob_config["MODULE_DIR"])
        for file_n in ["self"] + os.listdir(self.__glob_config["MODULE_DIR"]):
            if file_n.endswith("_mod.py") or file_n == "self":
                if file_n == "self":
                    modname = "global"
                    found_class_names = [obj_name for obj_name in globals().keys() if type(globals()[obj_name]) == type(dummy_class) and issubclass(globals()[obj_name], hm_classes.hm_fileinfo)]
                    found_com_names = [obj_name for obj_name in globals().keys() if type(globals()[obj_name]) == type(dummy_class) and issubclass(globals()[obj_name], hm_classes.hmb_command)]
                    newmod = None
                else:
                    modname = file_n[:-7]
                    if modname in self.__glob_config["DISABLED_MODULES"]:
                        logger.warning("   module '%s' is disabled" % (modname))
                    else:
                        logger.info("  checking file '%s' (module %s)" % (file_n, modname))
                        try:
                            newmod = __import__("%s_mod" % (modname), globals(), [], [])
                        except:
                            log_str = "  error importing module '%s': %s" % (modname,
                                                                             process_tools.get_except_info())
                            self.load_errors.append(log_str.strip())
                            logger.error(log_str)
                            found_class_names, found_com_names = ([], [])
                        else:
                            found_class_names = [obj_name for obj_name in dir(newmod) if type(getattr(newmod, obj_name)) == type(dummy_class) and issubclass(getattr(newmod, obj_name), hm_classes.hm_fileinfo)]
                            found_com_names = [obj_name for obj_name in dir(newmod) if type(getattr(newmod, obj_name)) == type(dummy_class) and issubclass(getattr(newmod, obj_name), hm_classes.hmb_command)]
                if found_class_names and found_com_names:
                    for fi_class_name in found_class_names:
                        try:
                            # instantiate class
                            if modname == "global":
                                fi_class = globals()[fi_class_name](module=newmod,
                                                                    logger=logger)
                            else:
                                fi_class = getattr(newmod, fi_class_name)(module=newmod,
                                                                          logger=logger)
                        except:
                            log_str = "something went wrong while trying to init module %s: %s" % (fi_class_name,
                                                                                                   process_tools.get_except_info())
                            self.load_errors.append(log_str.strip())
                            logger.error(log_str)
                        else:
                            logger.info("instantiated module %s in file %s" % (fi_class_name,
                                                                              modname))
                            self.add_module(fi_class)
                            for f_com_name in found_com_names:
                                try:
                                    # instantiate command
                                    if modname == "global":
                                        new_com = globals()[f_com_name](module=fi_class,
                                                                        module_name=modname)
                                    else:
                                        new_com = getattr(newmod, f_com_name)(module=fi_class,
                                                                              module_name=modname)
                                except:
                                    log_str = "something went wrong while trying to init command %s: %s" % (f_com_name,
                                                                                                            process_tools.get_except_info())
                                    self.load_errors.append(log_str.strip())
                                    logger.error(log_str)
                                else:
                                    logger.info("instantiated command %s in file %s (module %s)" % (f_com_name,
                                                                                                    modname,
                                                                                                    fi_class_name))
                                    self.add_command(new_com)
    def module_init(self, mode, logger, **args):
        logger.info("module_init called with mode '%s'" % (mode))
        pridict = {}
        for modname in self.module_keys():
            pridict.setdefault(self.get_module(modname).priority, []).append(modname)
        for pri in sorted(pridict.keys(), reverse=True):
            for modname in pridict[pri]:
                actmod = self.get_module(modname)
                if hasattr(actmod, "init"):
                    logger.info("  calling init() for module %s (priority %d)" % (modname, pri))
                    try:
                        actmod.init(mode, logger, self.__glob_config["BASEDIR_NAME"], mc_dict=self, **args)
                    except:
                        logger.error(" Something went wrong while calling init() : %s ***" % (process_tools.get_except_info()))
                else:
                    logger.info("  module %s has no init() function, skipping..." % (modname))
    def keys(self):
        return self.__commands.keys()
    def __getitem__(self, key):
        #print key
        return self.__commands[key]
    def iteritems(self):
        return self.__commands.iteritems()

class file_watcher(object):
    def __init__(self, glob_config, my_thread, **args):
        self.__glob_config = glob_config
        self.__thread = my_thread
        self.__queue = my_thread.get_thread_queue()
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
        if not inotify_tools:
            raise ValueError, "No inotify_tools found"
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
            self.log("unregistering from inotify watcher (%s, %s)" % (logging_tools.get_plural("file", len(self.__act_files)),
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
        self.__thread.log("[fw %s, %s] %s" % (self.fw_id, self.mode, what), lev)
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
                #if os.path.isfile
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
            
class inotify_thread(threading_tools.thread_obj):
    def __init__(self, logger, command_queue):
        self.__command_queue = command_queue
        self.__logger = logger
        threading_tools.thread_obj.__init__(self, "inotify", queue_size=100, loop_function=self._check)
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__logger.log(lev, what)
    def thread_running(self):
        self.send_pool_message(("new_pid", self.pid))
        self.__my_watcher = inotify_tools.inotify_watcher()
        self.__command_queue.put(("set_inotify_watcher", self.__my_watcher))
    def _check(self):
        try:
            self.__my_watcher.check(5000)
        except:
            # catch bugs in pyinotify
            self.log("error calling check: %s" % (process_tools.get_except_info()),
                     logging_tools.LOG_LEVEL_CRITICAL)

class background_thread(threading_tools.thread_obj):
    def __init__(self, glob_config, mc_dict, logger):
        self.__glob_config  = glob_config
        self.__logger       = logger
        self.__mc_dict = mc_dict
        self.__queue_dict = {}
        threading_tools.thread_obj.__init__(self, "background", queue_size=100)
        self.register_func("set_message_proc_queue", self._set_mp_queue)
        self.register_func("process_server_req", self._proc_serv_req)
    def thread_running(self):
        self.send_pool_message(("new_pid", self.pid))
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__logger.log(lev, what)
    def loop_end(self):
        if self.__glob_config["START_INOTIFY_THREAD"]:
            file("%s/exit.fw_internal" % (self.__glob_config["BASEDIR_NAME"]), "w").write("exit")
    def _set_mp_queue(self, mpq):
        self.__mp_queue = mpq
    def _proc_serv_req(self, (mod_stuff, what, src_addr)):
        s_time = time.time()
        result = mod_stuff(what, self.__logger, addr=src_addr, thread_pool=self.get_thread_pool())
        e_time = time.time()
        self.log("calling %s took %s" % (what, logging_tools.get_diff_time_str(e_time - s_time)))
        self.__mp_queue.put(("immediate_result", (what, result, e_time - s_time)))

class cached_result(object):
    def __init__(self, mod_stuff, logger, what, result=None):
        self.__mod_stuff = mod_stuff
        self.__logger = logger
        self.__com_line = what
        self.__last_update = 0
        if result:
            self.set_result(result, 1)
        else:
            self.__last_run_time = 5
        self.__request_times = []
        self.request()
    def set_result(self, result, run_time):
        self.__last_result = result
        self.__last_update = time.time()
        self.__last_run_time = run_time
    def get_result(self):
        return self.__last_result
    def get_cached_result(self):
        return self.__last_result
    def cache_timeout(self):
        return self.get_cache_freshness() > self.__mod_stuff.cache_timeout
    def get_cache_freshness(self):
        return abs(time.time() - self.__last_update)
    def request(self):
        self.__request_times.append(time.time())
        if len(self.__request_times) > 10:
            self.__request_times.pop(0)
        # check mean_time
        if len(self.__request_times) > 1:
            self.__mean_request_time = sum([self.__request_times[idx + 1] - self.__request_times[idx] for idx in range(0, len(self.__request_times) - 1)]) / (len(self.__request_times) - 1)
        else:
            # dummy value
            self.__mean_request_time = 600
        self.__next_request = self.__request_times[-1] + self.__mean_request_time - self.__last_run_time - 10
        return self.__next_request
    
class message_proc_thread(threading_tools.thread_obj):
    def __init__(self, glob_config, mc_dict, logger):
        """ processes messages from external """
        self.__glob_config  = glob_config
        self.__logger       = logger
        self.__mc_dict = mc_dict
        threading_tools.thread_obj.__init__(self, "message_proc", queue_size=100)
        self.register_func("register_queue", self._register_queue)
        self.register_func("in_bytes", self._tcp_in)
        self.register_func("set_background_queue", self._set_bg_queue)
        self.register_func("immediate_result", self._immediate_result)
        self.register_func("set_net_server", self._set_net_server)
        self.register_func("inotify_event", self._inotify_event)
        self.register_func("set_inotify_watcher", self._set_inotify_watcher)
        self.register_func("command", self._command)
        self.register_func("update", self._update)
        self.send_pool_message(("get_net_server", self.get_thread_queue()))
        # queue dict
        self.__queue_dict = {}
        # cache for none-immediate commands (comline -> cached_result)
        self.__nim_cache = {}
        # time dict for precalling, not implemented right now
        self.__pc_dict = {}
        # netserver
        self.__net_server = None
        # file_watcher dict
        self.__file_watcher_dict = ({})
        # background queue
        self.__bg_queue = None
    def thread_running(self):
        self.send_pool_message(("new_pid", self.pid))
        self.__inotify_queue, self.__inotify_watcher = (None, None)
        if inotify_tools and inotify_tools.inotify_ok():
            if self.__glob_config["START_INOTIFY_THREAD"]:
                self.log("inotify_tools ok")
                self.__inotify_queue = self.get_thread_pool().add_thread(inotify_thread(self.__logger, self.get_thread_queue()), start_thread=True).get_thread_queue()
            else:
                self.log("inotify_tools ok but thread is disabled", logging_tools.LOG_LEVEL_WARN)
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__logger.log(lev, what)
    def _set_net_server(self, ns):
        self.log("NetServer set")
        self.__net_server = ns
    def _register_queue(self, (func_name, d_queue)):
        self.log("Registering external queue for function '%s'" % (func_name))
        self.__queue_dict[func_name] = d_queue
    def _set_bg_queue(self, bgq):
        self.__bg_queue = bgq
    def _immediate_result(self, (com_line, result, run_time)):
        self.__nim_cache[com_line].set_result(result, run_time)
    def _tcp_in(self, tcp_stuff):
        what = tcp_stuff.get_decoded_in_str()
        first_str = what.split()[0]
        if first_str in self.__queue_dict:
            self.__queue_dict[first_str].put((what.split()[0], tcp_stuff))
        else:
            src_addr = (tcp_stuff.get_src_host(), tcp_stuff.get_src_port())
            ret_str, mod_stuff = prepare_server_request(what, self.__mc_dict, from_net=True)
            if mod_stuff:
                if mod_stuff.is_immediate:
                    ret_str = mod_stuff(what, self.__logger, addr=src_addr, thread_pool=self.get_thread_pool())
                else:
                    # check for last_cache
                    if what in self.__nim_cache:
                        c_result = self.__nim_cache[what]
                        next_request_time = c_result.request()
                        if c_result.cache_timeout() or not self.__bg_queue:
                            # too old -> call and cache
                            # cache entry too old, retry
                            s_time = time.time()
                            ret_str = mod_stuff(what, self.__logger, addr=src_addr, thread_pool=self.get_thread_pool())
                            e_time = time.time()
                            c_result.set_result(ret_str, e_time - s_time)
                        else:
                            # fresh enough -> return and call
                            ret_str = c_result.get_cached_result()
                            self.__bg_queue.put(("process_server_req", (mod_stuff, what, src_addr)))
                    else:
                        self.log("first call for %s" % (what))
                        # first call -> call and cache
                        ret_str = mod_stuff(what, self.__logger, addr=src_addr, thread_pool=self.get_thread_pool())
                        c_result = cached_result(mod_stuff, self.__logger, what, ret_str)
                        self.__nim_cache[what] = c_result
            tcp_stuff.add_to_out_buffer(ret_str)
    def _update(self):
        remove_ids = []
        for fw_id, fw_struct in self.__file_watcher_dict.iteritems():
            if not fw_struct.inotify():
                # huh ? FIXME, argument missing
                fw_struct.update()
            fw_struct.hello()
            if fw_struct.do_exit():
                remove_ids.append(fw_id)
        if remove_ids:
            self.log("removing %s: %s" % (logging_tools.get_plural("watcher_id", len(remove_ids)),
                                          ", ".join(remove_ids)))
            for rem_id in remove_ids:
                self._remove_file_watcher(rem_id)
    def _command(self, (tcp_obj, srv_com)):
        command = srv_com.get_command()
        com_func = {"register_file_watcher"   : self._register_file_watcher,
                    "unregister_file_watcher" : self._unregister_file_watcher}.get(command, None)
        if com_func:
            state, result = com_func(tcp_obj, srv_com)
        else:
            state, result = (server_command.SRV_REPLY_STATE_ERROR,
                             "unknown command %s" % (command))
        tcp_obj.add_to_out_buffer(server_command.server_reply(state=state,
                                                              result=result))
    def send_srv_command(self, file_watcher, host, port, srv_com):
        self.__net_server.add_object(net_tools.tcp_con_object(self._new_tcp_con,
                                                              target_host=host,
                                                              target_port=port,
                                                              bind_retries=1,
                                                              rebind_wait_time=1,
                                                              connect_state_call=self._tcp_connect_call,
                                                              add_data=(file_watcher, srv_com)))
    def _inotify_event(self, (fw, event)):
        fw._inotify_event(event)
    def _set_inotify_watcher(self, inotify_watcher):
        self.log("Got inotify_watcher")
        self.__inotify_watcher = inotify_watcher
        if inotify_tools and inotify_tools.inotify_ok():
            self._init_file_watcher(mode="content", id="internal", dir=self.__glob_config["BASEDIR_NAME"], match="*.fw_internal", target_server="localhost", target_port=0)
    def get_inotify_watcher(self):
        return self.__inotify_watcher
    def _new_tcp_con(self, sock):
        act_file_watcher, srv_com = sock.get_add_data()
        return net_tools.simple_con_obj(act_file_watcher, command=srv_com, protcoll=1)
    def _tcp_connect_call(self, **args):
        if args["state"] == "error":
            fw = args["socket"].get_add_data()[0]
            fw.set_error(net_tools.NET_CONNECTION_REFUSED, "connection error")
    def _register_file_watcher(self, tcp_obj, srv_com):
        opt_dict = srv_com.get_option_dict()
        return self._init_file_watcher(**opt_dict)
    def _init_file_watcher(self, **opt_dict):
        try:
            new_fw = file_watcher(self.__glob_config, self, **opt_dict)
        except ValueError, what:
            self.log("error initialising new file_watcher: %s" % (what), logging_tools.LOG_LEVEL_ERROR)
            ret_state, ret_str = (server_command.SRV_REPLY_STATE_ERROR, what)
        else:
            if new_fw.fw_id in self.__file_watcher_dict:
                self.log("cannot add new file_watcher with ID %s: already present" % (new_fw.fw_id), logging_tools.LOG_LEVEL_ERROR)
                ret_state, ret_str = (server_command.SRV_REPLY_STATE_ERROR, "file_watcher with ID %s already present" % (new_fw.fw_id))
                del new_fw
            else:
                self.__file_watcher_dict[new_fw.fw_id] = new_fw
                self.log("added file_watcher with id %s to dict" % (new_fw.fw_id))
                ret_state, ret_str = (server_command.SRV_REPLY_STATE_OK, "ok added file_watcher with id %s" % (new_fw.fw_id))
        return ret_state, ret_str
    def _remove_file_watcher(self, fw_id):
        if fw_id:
            if fw_id in self.__file_watcher_dict:
                self.__file_watcher_dict[fw_id].close()
                del self.__file_watcher_dict[fw_id]
                ret_state, ret_str = server_command.SRV_REPLY_STATE_OK, "ok removed ID %s" % (fw_id)
            else:
                self.log("cannot remove file_watcher entry with id %s (present: %s)" % (fw_id,
                                                                                        self.__file_watcher_dict and ", ".join(self.__file_watcher_dict.keys()) or "none"), logging_tools.LOG_LEVEL_ERROR)
                ret_state, ret_str = server_command.SRV_REPLY_STATE_ERROR, "ID %s not found" % (fw_id)
        else:
            self.log("empty file_watcher id", logging_tools.LOG_LEVEL_ERROR)
            ret_state, ret_str = server_command.SRV_REPLY_STATE_ERROR, "empty ID"
        return ret_state, ret_str
    def _unregister_file_watcher(self, tcp_obj, srv_com):
        opt_dict = srv_com.get_option_dict()
        needed_keys = ["id"]
        missing_keys = [key for key in needed_keys if not key in opt_dict]
        if missing_keys:
            ret_state, ret_str = (server_command.SRV_REPLY_STATE_ERROR, "%s missing: %s" % (logging_tools.get_plural("key", len(missing_keys)),
                                                                                            ", ".join(sorted(missing_keys))))
        else:
            fw_id = opt_dict["id"]
            ret_state, ret_str = self._remove_file_watcher(fw_id)
        return ret_state, ret_str
        
# --------- connection objects ------------------------------------

class simple_tcp_obj(net_tools.buffer_object):
    # connects to a foreign host-monitor
    def __init__(self, stc, dst_host, send_str):
        self.__stc = stc
        self.__dst_host = dst_host
        self.__send_str = send_str
        net_tools.buffer_object.__init__(self)
    def setup_done(self):
        self.add_to_out_buffer(net_tools.add_proto_1_header(self.__send_str, True))
    def out_buffer_sent(self, send_len):
        if send_len == len(self.out_buffer):
            self.out_buffer = ""
            self.socket.send_done()
        else:
            self.out_buffer = self.out_buffer[send_len:]
    def add_to_in_buffer(self, what):
        self.in_buffer += what
        p1_ok, p1_data = net_tools.check_for_proto_1_header(self.in_buffer)
        if p1_ok:
            self.__stc.set_host_result(self.__dst_host, p1_data)
            self.delete()
    def report_problem(self, flag, what):
        self.__stc.set_host_error(self.__dst_host, "%s : %s" % (net_tools.net_flag_to_str(flag), what))
        self.delete()

class new_relay_con(net_tools.buffer_object):
    # receiving connection object for local relayer
    def __init__(self, sock, src, d_queue):
        self.__d_queue = d_queue
        net_tools.buffer_object.__init__(self)
    def __del__(self):
        #print "- del new_relay_con"
        pass
    def add_to_in_buffer(self, what):
        self.in_buffer += what
        is_p1, what = net_tools.check_for_proto_1_header(self.in_buffer)
        if is_p1:
            if len(what) > 6:
                if what.startswith(RELAY_REQUEST_HEADER) and what[4].isdigit() and what[5].isdigit():
                    self.__d_queue.put(("relay_recv_ok", (int(what[4]), int(what[5]), what[6:], self)))
                else:
                    self.send_return({"ret_str"  : "wrong header",
                                      "ret_code" : limits.nag_STATE_CRITICAL})
            else:
                self.send_return({"ret_str"  : "short header",
                                  "ret_code" : limits.nag_STATE_CRITICAL})
    def send_return(self, what):
        self.lock()
        self.__send_str = hm_classes.sys_to_net(what)
        if self.socket:
            self.add_to_out_buffer(net_tools.add_proto_1_header(self.__send_str))
        else:
            pass
        self.unlock()
    def out_buffer_sent(self, send_len):
        if send_len == len(self.out_buffer):
            self.out_buffer = ""
            self.socket.send_done()
            self.close()
        else:
            self.out_buffer = self.out_buffer[send_len:]
    def report_problem(self, flag, what):
        self.__d_queue.put("relay_recv_error")
        self.close()
        #print "nrc_problem", flag, what

class simple_con(net_tools.buffer_object):
    # connects to a foreign host-monitor
    def __init__(self, act_con, d_queue):
        self.__act_con = act_con
        self.__send_str = act_con.get_effective_comline()
        self.__d_queue = d_queue
        net_tools.buffer_object.__init__(self)
    def setup_done(self):
        self.add_to_out_buffer(net_tools.add_proto_1_header(self.__send_str, True))
    def out_buffer_sent(self, send_len):
        if send_len == len(self.__send_str) + 8:
            self.out_buffer = ""
            self.socket.send_done()
        else:
            self.out_buffer = self.out_buffer[send_len:]
    def add_to_in_buffer(self, what):
        self.in_buffer += what
        is_p1, what = net_tools.check_for_proto_1_header(self.in_buffer)
        if is_p1:
            self.__act_con.get_parser_queue().put(("ok_relay_result", (self.__act_con, what)))
            self.__act_con = None
            self.delete()
    def report_problem(self, flag, what):
        self.__act_con.get_parser_queue().put(("send_error", (self.__act_con, what)))
        self.__act_con = None
        self.delete()

class simple_relay_con(net_tools.buffer_object):
    # connection object from local_host_relayer to foreign host_relayer
    def __init__(self, act_con, d_queue):
        self.__act_con = act_con
        self.__d_queue = d_queue
        net_tools.buffer_object.__init__(self)
        self.__send_str = self.__act_con.get_unrelayed_data()
    def setup_done(self):
        self.add_to_out_buffer(net_tools.add_proto_1_header(self.__send_str, True))
    def out_buffer_sent(self, send_len):
        if send_len == len(self.__send_str) + 8:
            self.out_buffer = ""
            self.socket.send_done()
        else:
            self.out_buffer = self.out_buffer[send_len:]
    def add_to_in_buffer(self, what):
        is_p1, what = net_tools.check_for_proto_1_header(what)
        if is_p1:
            self.__act_con.get_parser_queue().put(("relay_send_ok", (self.__act_con, what)))
            self.__act_con = None
            self.delete()
    def report_problem(self, flag, what):
        self.__d_queue.put(("relay_send_error", (self.__act_con, flag, what)))
        self.__act_con = None
        self.delete()

def parse_icmp_flags(in_str):
    log_lines = []
    in_f = in_str.split()
    if len(in_f) > 1:
        option_dict = {"flood_ping" : False,
                       "fast_mode"  : False,
                       "timeout"    : 10.0,
                       "num_ping"   : 3,
                       "host_list"  : []}
        # remove command
        in_f.pop(0)
        # parse options
        while True:
            if in_f[0].count("="):
                key, value = in_f.pop(0).split("=")
                if key in option_dict:
                    option_dict[key] = {"t" : True,
                                        "f" : False}.get(value.lower()[0], option_dict[key])
                else:
                    log_lines.append(("unknown key '%s' for ping_remote" % (key), logging_tools.LOG_LEVEL_ERROR))
            else:
                break
        if in_f:
            option_dict["host_list"] = in_f.pop(0).split(",")
            if len(in_f) == 2:
                val_1_str, val_2_str = (in_f[0], in_f[1])
                # interpret settings, stuff with a '.' in it is the timeout
                try:
                    if val_1_str.count("."):
                        option_dict["timeout"]  = int(float(val_1_str))
                        option_dict["num_ping"] = int(float(val_2_str))
                    else:
                        option_dict["timeout"]  = int(float(val_2_str))
                        option_dict["num_ping"] = int(float(val_1_str))
                except:
                    option_dict["num_ping"], option_dict["timeout"] = (3, 10)
                    log_lines.append(("Error converting num_ping / timeout (%s), using %d / %d" % (process_tools.get_except_info(),
                                                                                                   option_dict["num_ping"],
                                                                                                   option_dict["timeout"]), logging_tools.LOG_LEVEL_ERROR))
            log_lines.append(("starting ping to %s: %s (options: %s)" % (logging_tools.get_plural("host", len(option_dict["host_list"])),
                                                                         ", ".join(option_dict["host_list"]),
                                                                         ", ".join(["%s=%s" % (key, str(value)) for key, value in option_dict.iteritems() if key not in ["host_list"]])),
                              logging_tools.LOG_LEVEL_OK))
            
            ret_obj = option_dict
        else:
            ret_obj = "error host-list missing"
    else:
        ret_obj = "error wrong number of arguments (%d < 1)" % (len(in_f))
    return ret_obj, log_lines
    
class new_tcp_con(net_tools.buffer_object):
    # connection object for host-monitor (collserver)
    def __init__(self, sock, src, pm_queue, logger, ping_obj):
        self.__src_host, self.__src_port = src
        self.__pm_queue = pm_queue
        self.__logger = logger
        self.__ping_obj = ping_obj
        net_tools.buffer_object.__init__(self)
        self.__init_time = time.time()
        self.__in_buffer = ""
    def __del__(self):
        pass
    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        self.__logger.log(level, what)
    def get_src_host(self):
        return self.__src_host
    def get_src_port(self):
        return self.__src_port
    def add_to_in_buffer(self, what):
        self.__in_buffer += what
        p1_ok, what = net_tools.check_for_proto_1_header(self.__in_buffer)
        if p1_ok:
            self.__decoded = what
            if what.startswith("ping_remote "):
                # special hook for ping_remote
                self._do_icmp_call(what)
            else:
                self.__pm_queue.put(("in_bytes", self))
    def _do_icmp_call(self, in_str):
        option_dict, log_lines = parse_icmp_flags(in_str)
        for log_line, log_level in log_lines:
            if log_level > logging_tools.LOG_LEVEL_OK:
                self.log(log_line, log_level)
        if type(option_dict) == type(""):
            self.add_to_out_buffer(option_dict)
        else:
            self.__ping_obj.add_icmp_client(net_tools.icmp_client(host_list=option_dict["host_list"],
                                                                  num_ping=option_dict["num_ping"],
                                                                  timeout=option_dict["timeout"],
                                                                  fast_mode=option_dict["fast_mode"],
                                                                  finish_call=self._icmp_finish,
                                                                  flood_ping=option_dict["flood_ping"]))
    def _icmp_finish(self, icmp_obj):
        self.log("reporting ping-result")
        self.add_to_out_buffer("ok %s" % (hm_classes.sys_to_net(icmp_obj.get_result())))
    def add_to_out_buffer(self, what):
        self.lock()
        if self.socket:
            self.out_buffer = net_tools.add_proto_1_header(what)
            self.socket.ready_to_send()
        else:
            self.log("timeout, other side has closed connection (%s)" % (self.__decoded),
                     logging_tools.LOG_LEVEL_ERROR)
        self.unlock()
    def out_buffer_sent(self, d_len):
        if d_len == len(self.out_buffer):
            self.__pm_queue = None
            self.log("command %s from %s (port %d) took %s" % (self.__decoded,
                                                               self.__src_host,
                                                               self.__src_port,
                                                               logging_tools.get_diff_time_str(abs(time.time() - self.__init_time))))
            self.close()
        else:
            self.out_buffer = self.out_buffer[d_len:]
            #self.socket.ready_to_send()
    def get_decoded_in_str(self):
        return self.__decoded
    def report_problem(self, flag, what):
        self.close()

class new_com_con(net_tools.buffer_object):
    # connection object for complex commands to host-monitor (collserver)
    def __init__(self, sock, src, pm_queue, logger):
        self.__src_host, self.__src_port = src
        self.__pm_queue = pm_queue
        self.__logger   = logger
        net_tools.buffer_object.__init__(self)
        self.__init_time = time.time()
        self.__in_buffer = ""
    def __del__(self):
        pass
    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        self.__logger.log(level, what)
    def get_src_host(self):
        return self.__src_host
    def get_src_port(self):
        return self.__src_port
    def add_to_in_buffer(self, what):
        self.__in_buffer += what
        p1_ok, what = net_tools.check_for_proto_1_header(self.__in_buffer)
        if p1_ok:
            try:
                srv_com = server_command.server_command(what)
            except:
                self.log("no server_command from %s (port %d)" % (self.__src_host, self.__src_port))
                self.add_to_out_buffer("error no server_command")
                self.__decoded = what
            else:
                self.__decoded = "srv_com %s" % (srv_com.get_command())
                self.__pm_queue.put(("command", (self, srv_com)))
    def add_to_out_buffer(self, what):
        self.lock()
        self._log_finished()
        if self.socket:
            self.out_buffer = net_tools.add_proto_1_header(what)
            self.socket.ready_to_send()
        else:
            self.log("timeout, other side has closed connection")
        self.unlock()
    def _log_finished(self):
        self.log("command %s from %s (port %d) took %s" % (self.__decoded,
                                                           self.__src_host,
                                                           self.__src_port,
                                                           logging_tools.get_diff_time_str(abs(time.time() - self.__init_time))))
    def out_buffer_sent(self, d_len):
        if d_len == len(self.out_buffer):
            self.__pm_queue = None
            self.close()
        else:
            self.out_buffer = self.out_buffer[d_len:]
            #self.socket.ready_to_send()
    def get_decoded_in_str(self):
        return self.__decoded
    def report_problem(self, flag, what):
        self.close()

# --------- connection objects ------------------------------------

class server_thread_pool(threading_tools.thread_pool):
    def __init__(self, glob_config, logger, mc_dict):
        self.__glob_config  = glob_config
        self.__logger       = logger
        self.__mc_dict      = mc_dict
        threading_tools.thread_pool.__init__(self, "main", blocking_loop=False, stack_size=2 * 1024 * 1024)
        process_tools.save_pid("collserver/collserver")
        self.__msi_block = self._init_msi_block()
        self.register_exception("int_error", self._int_error)
        self.register_exception("term_error", self._int_error)
        self._log_config()
        self._check_uuid()
        self.__ns = net_tools.network_server(timeout=2, log_hook=self.log, poll_verbose=self.__glob_config["VERBOSE"] > 1)
        try:
            self.__ping_obj = net_tools.icmp_bind()
        except:
            self.log("unable to init raw_socket", logging_tools.LOG_LEVEL_ERROR)
            self.__ping_obj = None
        else:
            self.__ns.add_object(self.__ping_obj)
        self.__ss_queue = self.add_thread(message_proc_thread(self.__glob_config, self.__mc_dict, self.__logger), start_thread=True).get_thread_queue()
        if self.__glob_config["START_BACKGROUND_THREAD"]:
            self.__bg_queue = self.add_thread(background_thread(self.__glob_config, self.__mc_dict, self.__logger), start_thread=True).get_thread_queue()
            # register queues
            self.__ss_queue.put(("set_background_queue", self.__bg_queue))
            self.__bg_queue.put(("set_message_proc_queue", self.__ss_queue))
        self.__ns.add_object(net_tools.tcp_bind(self._new_com_con,
                                                port=self.__glob_config["COMMAND_LISTEN_PORT"],
                                                bind_retries=self.__glob_config["BIND_RETRIES"],
                                                bind_state_call=self._bind_state_call,
                                                timeout=120))
        self.__ns.add_object(net_tools.tcp_bind(self._new_tcp_con,
                                                port=self.__glob_config["LISTEN_PORT"],
                                                bind_retries=self.__glob_config["BIND_RETRIES"],
                                                bind_state_call=self._bind_state_call,
                                                timeout=120))
        self.__ns.add_object(net_tools.udp_bind(self._new_udp_con,
                                                port=self.__glob_config["LISTEN_PORT"],
                                                bind_retries=self.__glob_config["BIND_RETRIES"],
                                                bind_state_call=self._bind_state_call,
                                                timeout=120))
        # register funcs
        self.register_func("new_pid", self._new_pid)
        self.register_func("get_net_server", self._get_net_server)
        # start module subthreads
        self.__hourly_wakeups, self.__thread_queue_list = ([], [])
        self.__mc_dict.module_init("s", self.__logger, thread_pool=self, ping_object=self.__ping_obj)
        all_threads_ok = True
        for actmod_name in self.__mc_dict.module_keys():
            actmod = self.__mc_dict.get_module(actmod_name)
            try:
                if actmod.has_own_thread:
                    self.log("Starting sub-thread for module %s ..." % (actmod.name))
                    act_t_queue = self.add_thread(actmod.start_thread(self.__logger),
                                                  start_thread=True).get_thread_queue()
                    self.__thread_queue_list.append(act_t_queue)
                    act_t_queue.put(("register_call_queue", self.__ss_queue))
                if actmod.needs_hourly_wakeup_call():
                    self.__hourly_wakeups.append(actmod)
            except:
                all_threads_ok = False
                exc_str = "error spawning subthread for module %s: %s" % (actmod_name,
                                                                          process_tools.get_except_info())
                self.log(exc_str,
                         logging_tools.LOG_LEVEL_CRITICAL)
                print " - %s" % (exc_str)
        if not all_threads_ok:
            self.log("not all sub_threads spawned, exiting",
                     logging_tools.LOG_LEVEL_ERROR)
            self._int_error("subthread_spawn_error")
        # time stats
        self.__last_update = None
        self.__last_mi_time, self.__latest_hour = (0, time.localtime()[3])
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__logger.log(lev, what)
    def _get_net_server(self, d_queue):
        d_queue.put(("set_net_server", self.__ns))
    def _new_pid(self, new_pid):
        self.log("received new_pid message")
        process_tools.append_pids("collserver/collserver", new_pid)
        if self.__msi_block:
            self.__msi_block.add_actual_pid(new_pid)
            self.__msi_block.save_block()
    def thread_exited(self, thread_name, thread_pid):
        self.log("thread %s (%d) exited" % (thread_name, thread_pid))
        process_tools.remove_pids("collserver/collserver", thread_pid)
        if self.__msi_block:
            self.__msi_block.remove_actual_pid(thread_pid)
            self.__msi_block.save_block()
    def _new_tcp_con(self, sock, src):
        return new_tcp_con(sock, src, self.__ss_queue, self.__logger, self.__ping_obj)
    def _new_com_con(self, sock, src):
        return new_com_con(sock, src, self.__ss_queue, self.__logger)
    def _new_udp_con(self, data, frm):
        self.log("got data via UDP from %s" % (str(frm)), logging_tools.LOG_LEVEL_WARN)
    def _bind_state_call(self, **args):
        if args["state"] == "error":
            self.log("unable to bind to all ports, exiting", logging_tools.LOG_LEVEL_ERROR)
            self._int_error("bind problem")
        elif args["state"] == "ok":
            self.__ns.set_timeout(self.__glob_config["FLOOD_MODE"] and 0.1 or (self.__glob_config["DAEMONIZE"] and self.__glob_config["MAIN_TIMER"] or 5))
    def _init_msi_block(self):
        if self.__glob_config["DAEMONIZE"]:
            self.log("Initialising meta-server-info block")
            msi_block = process_tools.meta_server_info("collserver")
            msi_block.add_actual_pid()
            msi_block.start_command = "/etc/init.d/host-monitoring start"
            msi_block.stop_command = "/etc/init.d/host-monitoring force-stop"
            msi_block.kill_pids = True
            msi_block.save_block()
        else:
            msi_block = None
        return msi_block
    def _log_config(self):
        self.log("Basic turnaround-time is %d seconds" % (self.__glob_config["MAIN_TIMER"]))
        self.log("basedir_name is '%s'" % (self.__glob_config["BASEDIR_NAME"]))
        self.log("Config info:")
        for line, log_level in self.__glob_config.get_log(clear=True):
            self.log(" - clf: [%d] %s" % (log_level, line))
        conf_info = self.__glob_config.get_config_info()
        self.log("Found %d valid config-lines:" % (len(conf_info)))
        for conf in conf_info:
            self.log("Config : %s" % (conf))
    def _check_uuid(self):
        self.log("cluster_device_uuid is '%s'" % (uuid_tools.get_uuid().get_urn()))
    def _int_error(self, err_cause):
        if self["exit_requested"]:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            self["exit_requested"] = True
            self.__ns.set_timeout(0.1)
    def loop_function(self):
        if not self.__glob_config["DAEMONIZE"]:
            print time.ctime(), ", ".join(["%s: %d of %d used" % (name, act_used, max_size) for name, (max_size, act_used) in self.get_thread_queue_info().iteritems()])
        self.__ns.step()
        #if not self["exit_requested"]:
        act_time, act_hour = (int(time.time()), time.localtime()[3])
        if act_hour != self.__latest_hour:
            self.__latest_hour = act_hour
            for act_mod in self.__hourly_wakeups:
                act_mod.hourly_wakeup_call(self.__logger)
        if abs(act_time - self.__last_mi_time) > 60 or not self.__last_mi_time:
            self.__last_mi_time = act_time
            self.log("Actual memory consumption: %s" % (process_tools.beautify_mem_info()))
        if self.__last_update:
            if self.__last_update > act_time:
                self.log("Clock skew detected, adjusting last_update from %.2f to %.2f" % (self.__last_update, act_time - self.__glob_config["MAIN_TIMER"] / 2.), logging_tools.LOG_LEVEL_WARN)
                self.__last_update = act_time - self.__glob_config["MAIN_TIMER"] / 2.
            act_wait = min(self.__glob_config["MAIN_TIMER"], self.__glob_config["MAIN_TIMER"] - (act_time - self.__last_update))
        else:
            act_wait = 0
        if act_wait <= 0 or self.__glob_config["FLOOD_MODE"]:
            for act_t_q in self.__thread_queue_list + [self.__ss_queue]:
                try:
                    act_t_q.put("update")
                except:
                    self.log("error sending update message: %s" % (process_tools.get_except_info()),
                             logging_tools.LOG_LEVEL_ERROR)
            self.__last_update = int(time.time())
            act_wait += self.__glob_config["MAIN_TIMER"]
    def thread_loop_post(self):
        process_tools.delete_pid("collserver/collserver")
        if self.__msi_block:
            self.__msi_block.remove_meta_block()
    
class act_con(object):
    # connection in progress, initiated on the client (calling) side (not visible on the server side)
    def __init__(self, **args):#host, port, pid=0, direct=0):
        self.__ret_code, self.__ret_str, self.error = (limits.nag_STATE_UNKNOWN, "<not set>", False)
        if "in_data" in args:
            # try to interpret in_data
            try:
                self._parse_packed_data(args["in_data"], args["size_info"])
            except ValueError, what:
                self.set_state(limits.nag_STATE_CRITICAL, "error parsing data")
            else:
                self.__rreq_header = args.get("rreq_header", RELAY_REQUEST_HEADER)
        else:
            self.host = args["host"]
            self.port = args["port"]
            self.pid = args.get("pid", 0)
            self.__direct = args.get("direct", 0)
            self.__full_comline = args.get("comline")
        self._preparse_com_line()
        self.__relay_socket = args.get("relay_socket", None)
        self.__message_queue = args.get("message_queue", None)
        self.__flush_queue = args.get("flush_queue", None)
        self.init_time = args.get("init_time", time.time())
        self.__com_struct = None
    def __del__(self):
        #print "*** remove act_con_object"
        pass
    def get_unrelayed_data(self):
        # return packed unrelayed data-string
        return "%s%s" % (self.__rreq_header,
                         struct.pack("@l6i%ds%ds" % (len(self.host), len(self.__full_comline)),
                                     1,
                                     self.pid,
                                     self.port,
                                     self.__direct,
                                     0,
                                     len(self.host),
                                     len(self.__full_comline),
                                     self.host,
                                     self.__full_comline))
    def _parse_packed_data(self, data, (other_long_len, other_int_len, long_len, int_len)):
        header_len = other_long_len + 6 * other_int_len
        data_len = len(data)
        if data_len < header_len:
            raise ValueError, "received message with only %s (need at least %s)" % (logging_tools.get_plural("byte", data_len),
                                                                                    logging_tools.get_plural("byte", header_len))
        else:
            if other_long_len == long_len:
                datatype, self.pid, self.port, self.__direct, relayer_len, dhost_len, command_len = struct.unpack("@l6i", data[0:header_len])
            else:
                if long_len == 4:
                    # i am 32 bit, foreign host is 64 bit
                    datatype, self.pid, self.port, self.__direct, relayer_len, dhost_len, command_len = struct.unpack("@q6i", data[0:header_len])
                else:
                    # i am 64 bit, foreign host is 32 bit
                    datatype, self.pid, self.port, self.__direct, relayer_len, dhost_len, command_len = struct.unpack("@i6i", data[0:header_len])
            self.relayer        = data[header_len : header_len + relayer_len]
            self.host           = data[header_len + relayer_len             : header_len + relayer_len + dhost_len              ]
            self.__full_comline = data[header_len + relayer_len + dhost_len : header_len + relayer_len + dhost_len + command_len].strip()
    def _preparse_com_line(self):
        # check for pseudo-relay (ping-command with <IP_A>:<IP_B> notation)
        self.__com_parts = self.__full_comline.split()
        if len(self.__com_parts) > 1:
            if self.__com_parts[0] == "ping" and self.__com_parts[1].count(":"):
                h_part = self.__com_parts[1].split(":")
                self.relayer = h_part[0]
                self.host = ":".join(h_part[1:])
                self.__com_parts[1] = self.host
                self.__full_comline = " ".join(self.__com_parts)
    def set_parser_queue(self, pt_queue):
        self.__parser_queue = pt_queue
    def get_parser_queue(self):
        return self.__parser_queue
    def get_com_struct(self):
        return self.__com_struct
    def get_timeout(self):
        return self.__timeout
    def get_log_str(self):
        return "proc %i: got command '%s' for host '%s', port: %d (spid: %d)" % (os.getpid(), self.__full_comline, self.host, self.port, self.pid)
    def get_act_state_and_str(self):
        return self.__ret_code, self.__ret_str
    def set_state(self, code, what="<not set>"):
        if type(code) == type(()):
            code, what = code
        self.__ret_code, self.__ret_str = (code, what)
        self.error = self.__ret_code > 0
    def get_num_com_parts(self):
        return len(self.__com_parts)
    def get_com_part(self, idx):
        return self.__com_parts[idx]
    def get_parsed_arguments(self):
        return self.__parsed_com_args
    def get_unparsed_arguments(self):
        return self.__unparsed_com_args
    def get_full_comline(self):
        return self.__full_comline
    def get_effective_comline(self):
        if self.__direct == 2:
            return str(server_command.server_command(command=self.__base_com))
        else:
            return " ".join([self.__base_com] + self.__unparsed_com_args)
    def send_return_message(self, logger):
        if self.__relay_socket:
            #print "sock", self.__ret_str, self.__ret_code
            self.__relay_socket.send_return({"ret_str"  : self.__ret_str,
                                             "ret_code" : self.__ret_code})
        else:
            #print "shm", self.__ret_str, self.__ret_code
            #print "Sending ipc_return to pid %d (code %d)" % (return_pid, ret_code)
            if type(self.__ret_str) != type(""):
                logger.error("return_value is not string: %s (type %s), code %d, host %s, port %d, commline %s" % (str(self.__ret_str),
                                                                                                                   str(type(self.__ret_str)),
                                                                                                                   self.__ret_code,
                                                                                                                   self.host,
                                                                                                                   self.port,
                                                                                                                   str(self.__full_comline)))
                self.__ret_str = str(self.__ret_str)
            idx, t_idx = (0, len(self.__ret_str))
            while idx <= t_idx:
                n_idx = idx + STR_LEN - 1
                e_idx = min(n_idx, t_idx)
                try:
                    msg_str = struct.pack("@l6i%ds" % (e_idx - idx),
                                          self.pid,
                                          0,
                                          0,
                                          n_idx <= t_idx and 1 or 0,
                                          0,
                                          self.__ret_code,
                                          e_idx - idx,
                                          self.__ret_str[idx : e_idx])
                except:
                    logger.error("Cannot send ipc_return (ret_str %s, ret_code %s, return_pid %s, types %s %s %s)" % (self.__ret_str,
                                                                                                                      str(self.__ret_code),
                                                                                                                      str(self.pid),
                                                                                                                      str(type(self.__ret_str)),
                                                                                                                      str(type(self.__ret_code)),
                                                                                                                      str(type(self.pid))))
                    break
                else:
                    idx = n_idx
                    self.__message_queue.send(msg_str)
            if self.__flush_queue:
                self.__flush_queue.put(("finished", (self.pid, self.init_time)))
    def set_com_par(self, in_dict, timeout):
        # timeout
        self.__timeout = timeout
        # parsed command arguments
        self.__parsed_com_args = []
        # unparsed command arguments
        self.__unparsed_com_args = []
        com_d = None
        if self.__com_parts:
            self.__base_com = self.__com_parts.pop(0)
        else:
            self.set_state(limits.nag_STATE_CRITICAL, "Error: no command given.")
            raise ValueError
        if self.__direct:
            # direct command (direct connection to foreign port, no connection to host-monitoring)
            # rebuild comline (no double-spaces)
            self.__full_comline = " ".join([self.__base_com] + self.__com_parts)
            self.__com_struct = in_dict["direct"]
            com_d = in_dict["direct"]
        elif not self.__base_com in in_dict.keys():
            guess_list = ", ".join(difflib.get_close_matches(self.__base_com, in_dict.keys()))
            self.set_state(limits.nag_STATE_CRITICAL, "Error: command %s not found (did you meant: %s)." % (self.__base_com,
                                                                                                            guess_list or "none found"))
            raise ValueError
        else:
            com_d = in_dict[self.__base_com]
            self.__com_struct = com_d
            # override timeout
            if com_d.timeout and not self.__timeout:
                self.__timeout = com_d.timeout
            short_opts, long_opts = (com_d.short_client_opts,
                                     com_d.long_client_opts)
            try:
                opts, left_args = getopt.getopt(self.__com_parts, short_opts, long_opts)
            except getopt.GetoptError, why:
                self.set_state(limits.nag_STATE_CRITICAL, "Commandline error for client %s (%s)!" % (self.__base_com, why))
                raise ValueError
            else:
                try:
                    if short_opts or long_opts:
                        ok, why, self.__parsed_com_args = com_d.process_client_args(opts)
                    else:
                        ok, why, self.__parsed_com_args = (True, "ok", [])
                except:
                    self.set_state(limits.nag_STATE_CRITICAL, "Error parsing client args: %s" % (process_tools.get_except_info()))
                    raise ValueError
                else:
                    # rebuild comline
                    self.__unparsed_com_args = left_args
                    if not ok:
                        self.set_state(limits.nag_STATE_CRITICAL, "Error parsing client args: %s" % (why))
                        raise ValueError
        return self.__com_struct
    def process_return(self, in_dict, retstr, logger=None):
        if type(retstr) != type(""):
            self.set_state(limits.nag_STATE_CRITICAL, "cannot parse non-string type %s in process_return()" % (str(type(retstr))))
        else:
            if self.__direct == 2:
                # parse server reply
                try:
                    server_rep = server_command.server_reply(retstr)
                except:
                    self.set_state(limits.nag_STATE_CRITICAL, "cannot parse server_reply for command %s from %s" % (self.__base_com, self.host))
                else:
                    rep_state, rep_str = server_rep.get_state_and_result()
                    if rep_state == server_command.SRV_REPLY_STATE_OK:
                        loc_state = limits.nag_STATE_OK
                    elif rep_state == server_command.SRV_REPLY_STATE_WARN:
                        loc_state = limits.nag_STATE_WARNING
                    elif rep_state == server_command.SRV_REPLY_STATE_UNSET:
                        loc_state = limits.nag_STATE_UNKNOWN
                    else:
                        loc_state = limits.nag_STATE_CRITICAL
                    self.set_state(loc_state, rep_str)
            else:
                ret_split = retstr.split()
                header = ret_split.pop(0)
                footer = " ".join(ret_split)
                if len(footer) == 0:
                    footer = "N/A (no answer)"
                if header == "int_error":
                    self.set_state(limits.nag_STATE_CRITICAL, "Problem connecting to %s" % (self.host))
                elif header == "error":
                    self.set_state(limits.nag_STATE_CRITICAL, "Client error for command %s on %s: %s" % (self.__base_com, self.host, footer))
                elif header == "invalid":
                    self.set_state(limits.nag_STATE_WARNING , "Invalid operand for command %s on %s: %s" % (self.__base_com, self.host, footer))
                elif header == "unknown":
                    self.set_state(limits.nag_STATE_WARNING , "Unknown command %s on %s" % (self.__base_com, self.host))
                elif header == None:
                    self.set_state(limits.nag_STATE_CRITICAL, "Command %s on host %s returned no data" % (self.__base_com, self.host))
                else:
                    if self.__direct:
                        if retstr.lower().startswith("ok"):
                            self.set_state(limits.nag_STATE_OK      , retstr)
                        elif retstr.lower().startswith("warn"):
                            self.set_state(limits.nag_STATE_WARNING , retstr)
                        else:
                            self.set_state(limits.nag_STATE_CRITICAL, retstr)
                    else:
                        if self.__base_com in in_dict.keys():
                            if hasattr(self.__com_struct, "client_call_ext"):
                                try:
                                    self.set_state(self.__com_struct.client_call_ext(return_string=retstr,
                                                                                     parsed_command_args=self.__parsed_com_args,
                                                                                     host=self.host,
                                                                                     args=self.__com_parts))
                                except:
                                    full_info = process_tools.exception_info()
                                    log_str = "Error postprocessing return %s via _ext callfor command %s on %s: %s" % (retstr,
                                                                                                                        self.__base_com,
                                                                                                                        self.host,
                                                                                                                        "\n".join(full_info.log_lines))
                                else:
                                    log_str = ""
                            elif hasattr(self.__com_struct, "client_call"):
                                try:
                                    self.set_state(self.__com_struct.client_call(retstr, self.__parsed_com_args))
                                except:
                                    full_info = process_tools.exception_info()
                                    log_str = "Error postprocessing return %s for command %s on %s: %s" % (retstr,
                                                                                                           self.__base_com,
                                                                                                           self.host,
                                                                                                           "\n".join(full_info.log_lines))
                                else:
                                    log_str = ""
                            else:
                                log_str = "Error postprocessing return %s for command %s on %s: no client_command defined" % (retstr, self.__base_com, self.host)
                            if log_str:
                                if logger:
                                    logger.info(log_str)
                                self.set_state(limits.nag_STATE_CRITICAL, log_str)
                        else:
                            self.set_state(limits.nag_STATE_WARNING, "Unknown return %s for command %s on %s" % (retstr, self.__base_com, self.host))

def create_relay_info_str(act_c, tm_dict, parser_used, start_time):
    crs = act_c.get_parsed_arguments()
    if not len(crs):
        tot_com = sum([x["num"] for x in tm_dict.values()])
        max_parse_time, max_tot_time = (max([x["max_parse_time"] for x in tm_dict.values()] + [0.]),
                                        max([x["max_total_time"] for x in tm_dict.values()] + [0.]))
        ret_str = "ok %d parser threads, %d (%d) commands served since %s, %.2f / %.2f" % (len(parser_used.keys()),
                                                                                           len(tm_dict.keys()),
                                                                                           tot_com,
                                                                                           time.ctime(start_time),
                                                                                           max_parse_time,
                                                                                           max_tot_time)
    elif crs[0] == "command":
        if len(crs) != 2:
            ret_str = "ok %s served: %s" % (logging_tools.get_plural("command", len(tm_dict.keys())),
                                            ", ".join(["%s (%d)" % (x, y["num"]) for x, y in tm_dict.iteritems()]))
        else:
            command = crs[1]
            if command in tm_dict:
                ret_str = "ok command %s: %s served, %.2f / %.2f" % (command,
                                                                     logging_tools.get_plural("time", tm_dict[command]["num"]),
                                                                     tm_dict[command]["max_parse_time"],
                                                                     tm_dict[command]["max_total_time"])
            else:
                ret_str = "ok command %s never served" % (command)
    else:
        ret_str = "error unknown option %s" % (crs[0])
    return ret_str
    
class flush_thread(threading_tools.thread_obj):
    def __init__(self, glob_config, message_q, logger):
        self.__glob_config  = glob_config
        self.__logger       = logger
        self.__message_queue = message_q
        threading_tools.thread_obj.__init__(self, "flush", queue_size=100)
        self.register_func("finished", self._finished)
        self.__finish_list = []
        self.__flush_counter = 0
    def thread_running(self):
        self.send_pool_message(("new_pid", self.pid))
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__logger.log(lev, what)
    def _finished(self, (pid, init_time)):
        self.__finish_list.append((pid, init_time))
        self.__flush_counter = (self.__flush_counter - 1) % 10
        if not self.__flush_counter:
            act_plist = process_tools.get_process_id_list()
            act_time = time.time()
            new_flist = []
            for c_pid, init_time in self.__finish_list:
                # check if initial call is old enough (say 60 seconds)
                tdiff = act_time - init_time
                # fragment to old, clock skewed or calling process dead:
                if abs(tdiff) > 60 or c_pid not in act_plist:
                    # delete pending requests
                    num, b_len = (0, 0)
                    data = True
                    while data:
                        data = self.__message_queue.receive(type = c_pid)
                        if data:
                            b_len += len(data)
                            num += 1
                    if num:
                        self.log("flushed %s (%d bytes) for pid %d" % (logging_tools.get_plural("message fragment", num),
                                                                       b_len,
                                                                       c_pid))
                else:
                    new_flist.append((c_pid, init_time))
            self.__finish_list = new_flist

class relay_parser_thread(threading_tools.thread_obj):
    def __init__(self, glob_config, name, relay_queue, mc_dict, logger):
        self.__glob_config  = glob_config
        self.__logger       = logger
        self.__relay_queue = relay_queue
        self.__mc_dict     = mc_dict
        threading_tools.thread_obj.__init__(self, name, queue_size=100)
        self.register_func("ok_relay_result", self._ok_relay_result)
        self.register_func("send_error", self._send_error)
        self.register_func("icmp_result", self._icmp_result)
        self.register_func("relay_send_ok", self._relay_send_ok)
    def thread_running(self):
        self.send_pool_message(("new_pid", self.pid))
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__logger.log(lev, what)
    def _relay_send_ok(self, (act_con, what)):
        try:
            in_dict = hm_classes.net_to_sys(what)
        except:
            act_con.set_state(limits.nag_STATE_CRITICAL, "unpacking return_dict: %s" % (process_tools.get_except_info()))
        else:
            if "pid" in in_dict:
                # old format
                act_con.set_state(in_dict["state"], in_dict["result"])
            else:
                # new format
                act_con.set_state(in_dict["ret_code"], in_dict["ret_str"])
        act_con.send_return_message(self.__logger)
    def _ok_relay_result(self, (my_act_con, what)):
        my_act_con.process_return(self.__mc_dict, what, self.__logger)
        my_act_con.send_return_message(self.__logger)
    def _send_error(self, (my_act_con, ret_str)):
        my_act_con.set_state(limits.nag_STATE_CRITICAL, ret_str)
        my_act_con.send_return_message(self.__logger)
    def _icmp_result(self, (my_act_con, res_dict)):
        ping_res = res_dict.values()[0]
        if type(ping_res) == type(""):
            ret_code, ret_str = (limits.nag_STATE_CRITICAL, "error: %s" % (ping_res))
        else:
            if not ping_res["received"]:
                ret_code, state = (limits.nag_STATE_CRITICAL, "Critical")
            elif ping_res["timeout"] > int(ping_res["send"] / 2):
                ret_code, state = (limits.nag_STATE_WARNING, "Warning")
            else:
                ret_code, state = (limits.nag_STATE_OK, "OK")
            if not ping_res["received"]:
                ret_str = "%s: no reply from %s (%s sent)" % (state,
                                                              res_dict.keys()[0],
                                                              logging_tools.get_plural("packet", ping_res["send"]))
            else:
                msec = ping_res["mean_time"] * 1000
                ret_str = "%s: %d%% loss of %s from %s (%s avg)" % (state,
                                                                    int(100 * ping_res["timeout"] / ping_res["send"]),
                                                                    logging_tools.get_plural("packet", ping_res["send"]),
                                                                    res_dict.keys()[0],
                                                                    logging_tools.get_diff_time_str(ping_res["mean_time"]))
        my_act_con.set_state(ret_code, ret_str)
        my_act_con.send_return_message(self.__logger)
        
class network_thread(threading_tools.thread_obj):
    def __init__(self, glob_config, relay_queue, logger):
        self.__glob_config = glob_config
        self.__logger      = logger
        self.__relay_queue = relay_queue
        self.__msi_block   = None
        threading_tools.thread_obj.__init__(self, "network", loop_function=self._loop_function, queue_size=100)
        self.register_func("set_msi_block", self._set_msi_block)
    def thread_running(self):
        self.__ns = net_tools.network_server(timeout=2, log_hook=self.log, poll_verbose=False)
        self.__ns.add_object(net_tools.tcp_bind(self._new_tcp_con,
                                                port=self.__glob_config["RELAYER_LISTEN_PORT"],
                                                bind_retries=self.__glob_config["BIND_RETRIES"],
                                                bind_state_call=self._bind_state_call,
                                                timeout=1))
        try:
            self.__ping_obj = net_tools.icmp_bind()
        except:
            self.log("unable to init raw-socket", logging_tools.LOG_LEVEL_ERROR)
            self.__ping_obj = None
        else:
            self.__ns.add_object(self.__ping_obj)
            self.__relay_queue.put(("set_ping_obj", self.__ping_obj))
        self.send_pool_message(("new_pid", self.pid))
        self.send_pool_message(("set_net_server", self.__ns))
        self.__relay_queue.put(("set_net_server", self.__ns))
        self.__relay_queue.put("wakeup_main_thread")
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__logger.log(lev, what)
    def _set_msi_block(self, msi_block):
        self.log("msi_block set")
        self.__msi_block = msi_block
    def _loop_function(self):
        self.__ns.step()
        if self.__msi_block:
            self.log("heartbeat (%s)" % (time.ctime()))
            self.__msi_block.heartbeat()
    def _bind_state_call(self, **args):
        if args["state"] == "error":
            self.log("unable to bind to all ports, exiting", logging_tools.LOG_LEVEL_ERROR)
            self.send_pool_message(("int_error", "unable to bind to all ports"))
        elif args["state"] == "ok":
            self.__ns.set_timeout(self.__glob_config["FLOOD_MODE"] and 0.1 or (self.__glob_config["DAEMONIZE"] and 60 or 5))
            self.__relay_queue.put(("set_net_server", self.__ns))
    def _new_tcp_con(self, sock, src):
        return new_relay_con(sock, src, self.__relay_queue)

        
class relay_thread(threading_tools.thread_obj):
    def __init__(self, glob_config, flush_queue, mes_queue, mc_dict, logger):
        self.__glob_config = glob_config
        self.__logger      = logger
        threading_tools.thread_obj.__init__(self, "relay", queue_size=100)
        self.__message_queue  = mes_queue
        self.__flush_queue    = flush_queue
        self.__mc_dict        = mc_dict
        self.register_func("new_ipc_request", self._new_ipc_request)
        self.register_func("reload", self._reload)
        self.register_func("new_pid", self._new_pid)
        self.register_func("send_error", self._send_error)
        self.register_func("set_net_server", self._set_net_server)
        self.register_func("set_ping_obj", self._set_ping_obj)
        self.register_func("spawn_threads", self._init_threads)
        self.register_func("wakeup_main_thread", self.any_message_send)
        self.register_func("set_net_server", self._set_net_server)
        self.register_func("relay_send_error", self._relay_send_error)
        self.register_func("relay_recv_error", self._relay_recv_error)
        self.register_func("relay_recv_ok", self._relay_recv_ok)
        self.register_func("set_msi_block", self._set_msi_block)
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__logger.log(lev, what)
    def thread_running(self):
        self.__net_server, self.__ping_object = (None, None)
        self.send_pool_message(("new_pid", self.pid))
        self._fetch_relay_config()
        self.__glob_config.add_config_entries({"LONG_LEN" : configfile.int_c_var(struct.calcsize("@l")),
                                            "INT_LEN"  : configfile.int_c_var(struct.calcsize("@i"))})
        self.__rreq_header = "%s%d%d" % (RELAY_REQUEST_HEADER, self.__glob_config["LONG_LEN"], self.__glob_config["INT_LEN"])
    def _new_pid(self, what):
        self.send_pool_message(("new_pid", what))
    def _init_threads(self, num_threads):
        self.log("Spawning %s" % (logging_tools.get_plural("parser_thread", num_threads)))
        self.__parser_queues, self.__parser_used = ({}, {})
        for i in range(num_threads):
            pt_name = "parser_%d" % (i)
            self.__parser_queues[pt_name] = self.get_thread_pool().add_thread(relay_parser_thread(self.__glob_config, pt_name, self.get_thread_queue(), self.__mc_dict, self.__logger), start_thread=True).get_thread_queue()
            self.__parser_used[pt_name] = 0
        self.__network_queue = self.get_thread_pool().add_thread(network_thread(self.__glob_config, self.get_thread_queue(), self.__logger), start_thread=True).get_thread_queue()
        #self._init_
    def _set_msi_block(self, msi_block):
        self.__network_queue.put(("set_msi_block", msi_block))
    def _relay_send_error(self, (my_act_con, flag, what)):
        # i am the sending relayer
        my_act_con.set_state(limits.nag_STATE_CRITICAL, "send_error: %s" % (what.startswith("error ") and what[6:] or what))
    def _relay_recv_error(self):
        # i am the receiving relayer
        self.log("relay_receive_error", logging_tools.LOG_LEVEL_ERROR)
    def _relay_recv_ok(self, (other_long_len, other_int_len, in_str, relay_socket)):
        my_actc = act_con(in_data=in_str, size_info=(other_long_len, other_int_len, self.__glob_config["LONG_LEN"], self.__glob_config["INT_LEN"]), relay_socket=relay_socket)
        if my_actc.error:
            my_actc.send_return_message(self.__logger)
        else:
            self._request_ok(my_actc)
    def any_message_send(self):
        send_str = "wakeup"
        self.__message_queue.send(struct.pack("@l%ds" % (len(send_str)), 1, send_str))
    def _set_net_server(self, ns):
        self.log("NetServer set")
        self.__net_server = ns
    def _set_ping_obj(self, po):
        self.log("PingObject set")
        self.__ping_object = po
    def _new_ipc_request(self, (data, init_time)):
        new_actc = act_con(message_queue=self.__message_queue, in_data=data, init_time=init_time, size_info=(self.__glob_config["LONG_LEN"], self.__glob_config["INT_LEN"], self.__glob_config["LONG_LEN"], self.__glob_config["INT_LEN"]), rreq_header=self.__rreq_header, flush_queue=self.__flush_queue)
        if new_actc.error:
            new_actc.send_return_message(self.__logger)
        else:
            # get and install parser
            self._request_ok(new_actc)
    def _request_ok(self, new_actc):
        act_parser = [x for x, y in self.__parser_used.iteritems() if y == min(self.__parser_used.values())][0]
        new_actc.set_parser_queue(self.__parser_queues[act_parser])
        if new_actc.relayer:
            if self.__net_server:
                if new_actc.relayer in self.__relay_config:
                    con_host, con_port = ("127.0.0.1", self.__relay_config[new_actc.relayer])
                else:
                    con_host, con_port = (new_actc.relayer, self.__glob_config["RELAYER_LISTEN_PORT"])
                self.__net_server.add_object(net_tools.tcp_con_object(self._new_relay_tcp_con,
                                                                      connect_state_call=self._connect_state_call,
                                                                      connect_timeout_call=self._connect_timeout,
                                                                      timeout=10,
                                                                      bind_retries=1,
                                                                      rebind_wait_time=1,
                                                                      target_port=con_port,
                                                                      target_host=con_host,
                                                                      add_data=new_actc))
            else:
                new_actc.set_state(limits.nag_STATE_CRITICAL, "no net_server")
                new_actc.send_return_message(self.__logger)
        else:
            try:
                hmb_com = new_actc.set_com_par(self.__mc_dict, 60.)
            except ValueError:
                new_actc.send_return_message(self.__logger)
            else:
                if hmb_com.relay_call:
                    if hmb_com.special_hook == "ping":
                        if self.__ping_object:
                            option_dict, log_lines = parse_icmp_flags(new_actc.get_full_comline())
                            for log_line, log_level in log_lines:
                                if log_level > logging_tools.LOG_LEVEL_OK or self.__glob_config["VERBOSE"]:
                                    self.log(log_line, log_level)
                            if type(option_dict) == type(""):
                                new_actc.set_state(limits.nag_STATE_CRITICAL, option_dict)
                                new_actc.send_return_message(self.__logger)
                            else:
                                self.__ping_object.add_icmp_client(net_tools.icmp_client(host_list=option_dict["host_list"],
                                                                                         num_ping=option_dict["num_ping"],
                                                                                         timeout=option_dict["timeout"],
                                                                                         fast_mode=option_dict["fast_mode"],
                                                                                         finish_call=self._icmp_finish,
                                                                                         flood_ping=option_dict["flood_ping"],
                                                                                         add_data=new_actc))
                                self.__parser_used[act_parser] += 1
                        else:
                            new_actc.set_state(limits.nag_STATE_CRITICAL, "no ping_object")
                            new_actc.send_return_message(self.__logger)
                    else:
                        new_actc.set_state(limits.nag_STATE_CRITICAL, "invalid special_hook '%s'" % (hmb_com.special_hook or "not set"))
                        new_actc.send_return_message(self.__logger)
                else:
                    if self.__net_server:
                        self.__net_server.add_object(net_tools.tcp_con_object(self._new_tcp_con,
                                                                              connect_state_call=self._connect_state_call,
                                                                              connect_timeout_call=self._connect_timeout,
                                                                              timeout=new_actc.get_timeout(),
                                                                              bind_retries=1,
                                                                              rebind_wait_time=1,
                                                                              target_port=new_actc.port,
                                                                              target_host=new_actc.host,
                                                                              add_data=new_actc))
                        self.__parser_used[act_parser] += 1
                    else:
                        new_actc.set_state(limits.nag_STATE_CRITICAL, "no net_server")
                        new_actc.send_return_message(self.__logger)
    def _icmp_finish(self, icmp_obj):
        my_act_con = icmp_obj.get_add_data()
        my_act_con.get_parser_queue().put(("icmp_result", (my_act_con, icmp_obj.get_result())))
    def _connect_timeout(self, sock):
        self.get_thread_queue().put(("send_error", (sock.get_add_data(), "connect timeout")))
        sock.close()
    def _connect_state_call(self, **args):
        if args["state"] == "error":
            self.get_thread_queue().put(("send_error", (args["socket"].get_add_data(), "relayer connection error")))
    def _new_tcp_con(self, sock):
        return simple_con(sock.get_add_data(), self.get_thread_queue())
    def _new_relay_tcp_con(self, sock):
        return simple_relay_con(sock.get_add_data(), self.get_thread_queue())
    def _reload(self):
        self.log("Got update-request")
        self._fetch_relay_config()
    def _send_error(self, stuff):
        my_act_con, what = stuff
        my_act_con.get_parser_queue().put(("send_error", (my_act_con, what)))
    def _fetch_relay_config(self):
        if mysql_tools:
            db_con = mysql_tools.dbcon_container()
            try:
                dc = db_con.get_connection("cluster_full_access")
            except:
                self.log("Cannot open db-connection: %s" % (process_tools.get_except_info()),
                         logging_tools.LOG_LEVEL_ERROR)
            else:
                self.log("Fetching config for advanced relaying from db ...")
                dc.execute("SELECT d.name, dv.val_int, d.device_idx FROM device d, device_variable dv WHERE dv.device=d.device_idx AND dv.name='SSH_TUNNEL_PORT'")
                r_dict, idx_dict, p_dict = ({}, {}, {})
                for db_rec in dc.fetchall():
                    r_dict[db_rec["name"]] = db_rec["val_int"]
                    idx_dict[db_rec["device_idx"]] = db_rec["name"]
                if idx_dict:
                    dc.execute("SELECT n.device, i.ip FROM netdevice n, netip i, network nw, network_type nt WHERE i.netdevice=n.netdevice_idx AND i.network=nw.network_idx AND nw.network_type=nt.network_type_idx AND nt.identifier != 'l' AND (%s)" % (" OR ".join(["n.device=%d" % (v) for v in idx_dict.keys()])))
                    for db_rec in dc.fetchall():
                        p_dict[db_rec["ip"]] = r_dict[idx_dict[db_rec["device"]]]
                if p_dict:
                    self.log("Found %s:" % (logging_tools.get_plural("entry", len(p_dict.keys()))))
                    for ip in sorted(p_dict.keys()):
                        self.log("-%15s : port %d" % (ip, p_dict[ip]))
                else:
                    self.log("Found no entries")
                self.__relay_config = p_dict
                dc.release()
            del db_con
        else:
            self.log("no mysql_tools", logging_tools.LOG_LEVEL_WARN)
            self.__relay_config = {}
        
class relay_thread_pool(threading_tools.thread_pool):
    def __init__(self, glob_config, logger, mc_dict):
        num_threads = 6
        self.__glob_config = glob_config
        self.__logger      = logger
        self.__mc_dict     = mc_dict
        threading_tools.thread_pool.__init__(self, "main", blocking_loop=False)
        process_tools.save_pid("collrelay/collrelay")
        self.__msi_block = self._init_msi_block()
        self.register_exception("int_error", self._int_error)
        self.register_exception("term_error", self._int_error)
        self.register_exception("hup_error", self._hup_error)
        self.register_func("new_pid", self._new_pid)
        self.register_func("set_net_server", self._set_net_server)
        self.register_func("int_error", self._int_error)
        self._set_net_server(None)
        self._check_msg_settings()
        if not self._init_relay_key("/var/run/relay_key.ipc"):
            self._int_error("unable to create msgqueue")
        else:
            self.__flush_queue        = self.add_thread(flush_thread(self.__glob_config, self.__message_queue, self.__logger),
                                                        start_thread=True).get_thread_queue()
            self.__relay_thread_queue = self.add_thread(relay_thread(self.__glob_config, self.__flush_queue, self.__message_queue, mc_dict, self.__logger),
                                                        start_thread=True).get_thread_queue()
            self.__relay_thread_queue.put(("spawn_threads", num_threads))
            self.__relay_thread_queue.put(("set_msi_block", self.__msi_block))
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__logger.log(lev, what)
    def _set_net_server(self, ns):
        self.__net_server = ns
        self.log("NetServer set")
    def _init_msi_block(self):
        if self.__glob_config["DAEMONIZE"]:
            self.log("Initialising meta-server-info block")
            msi_block = process_tools.meta_server_info("collrelay")
            msi_block.add_actual_pid()
            msi_block.start_command = "/etc/init.d/host-relay start"
            msi_block.stop_command = "/etc/init.d/host-relay force-stop"
            msi_block.kill_pids = True
            msi_block.heartbeat_timeout = 60
            msi_block.save_block()
        else:
            msi_block = None
        return msi_block
    def _new_pid(self, new_pid):
        self.log("received new_pid message")
        process_tools.append_pids("collrelay/collrelay", new_pid)
        if self.__msi_block:
            self.__msi_block.add_actual_pid(new_pid)
            self.__msi_block.save_block()
    def _int_error(self, err_cause):
        self.log("_int_error() called, cause %s" % (str(err_cause)), logging_tools.LOG_LEVEL_WARN)
        if self["exit_requested"]:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            self["exit_requested"] = True
            self._break_netserver()
    def _break_netserver(self):
        if self.__net_server:
            self.log("Sending break to netserver")
            self.__net_server.break_call()
    def _hup_error(self, err_cause):
        self.__relay_thread_queue.put("reload")
    def _check_msg_settings(self):
        msg_dir = "/proc/sys/kernel/"
        t_dict = {"max" : {"info"  : "maximum number of bytes in a message"},
                  "mni" : {"info"  : "number of message-queue identifiers"},
                  "mnb" : {"info"  : "initial value for msg_qbytes",
                           "value" : 655360}}
        for key, ipc_s in t_dict.iteritems():
            r_name = "msg%s" % (key)
            f_name = "%s%s" % (msg_dir, r_name)
            if os.path.isfile(f_name):
                value = int(file(f_name, "r").read().strip())
                self.log("value of %s (%s) is %d" % (r_name, ipc_s["info"], value))
                if "value" in ipc_s and ipc_s["value"] != value:
                    try:
                        file(f_name, "w").write("%d\n" % (ipc_s["value"]))
                    except:
                        self.log("Cannot alter value of %s (%s) to %d: %s" % (f_name,
                                                                              ipc_s["info"],
                                                                              ipc_s["value"],
                                                                              process_tools.get_except_info()),
                                 logging_tools.LOG_LEVEL_WARN)
                    else:
                        self.log("Altered value of %s (%s) from %d to %d" % (f_name,
                                                                             ipc_s["info"],
                                                                             value,
                                                                             ipc_s["value"]))
                                                                             
            else:
                self.log("file %s not readable" % (f_name), logging_tools.LOG_LEVEL_WARN)
    def _init_relay_key(self, key_f_name):
        self.__message_key_file_name = key_f_name
        success = False
        self.__message_queue = None
        try:
            import pyipc
        except:
            self.log("Cannot load pyipc-module: %s" % (process_tools.get_except_info()),
                     logging_tools.LOG_LEVEL_CRITICAL)
            return success
        else:
            self.__pyipc_mod = pyipc
        try:
            old_key = int(file(key_f_name, "r").read().split("\n")[0].strip())
        except:
            pass
        else:
            try:
                message_q = pyipc.MessageQueue(old_key)
            except:
                self.log("Can't create MessageQueue with with old key %d" % (old_key),
                         logging_tools.LOG_LEVEL_WARN)
            else:
                pyipc.removeIPC(message_q)
        if self.__glob_config["IPC_KEY"] > 0:
            try:
                message_q = pyipc.MessageQueue(self.__glob_config["IPC_KEY"], pyipc.IPC_CREAT | 0666)
            except:
                self.log("Can't allocate given IPC MessageKey %d" % (self.__glob_config["IPC_KEY"]),
                         logging_tools.LOG_LEVEL_CRITICAL)
                ret_code = limits.nag_STATE_CRITICAL
            else:
                self.__message_queue = message_q
                success = True
        else:
            # auto-allocate message-queue
            first_key = 100
            last_key = 2000
            for act_key in xrange(first_key, last_key):
                try:
                    message_q = pyipc.MessageQueue(act_key, 0666)
                except:
                    try:
                        message_q = pyipc.MessageQueue(act_key, pyipc.IPC_CREAT | 0666)
                    except:
                        try:
                            pyipc.removeIPC(message_q)
                        except:
                            pass
                    else:
                        self.__glob_config["IPC_KEY"] = act_key
                else:
                    self.__glob_config["IPC_KEY"] = act_key
                if self.__glob_config["IPC_KEY"] > 0:
                    success = True
                    self.__message_queue = message_q
                    break
            if not self.__glob_config["IPC_KEY"]:
                self.log("Can't allocate an IPC MessageQueue in the key range [ %d : %d ]" % (first_key, last_key), logging_tools.LOG_LEVEL_CRITICAL)
        if success:
            # write relay-key
            # at first, delete it if possible
            if os.path.isfile(key_f_name):
                try:
                    os.unlink(key_f_name)
                except:
                    self.log("Error unlinking %s: %s" % (key_f_name,
                                                         process_tools.get_except_info()),
                             logging_tools.LOG_LEVEL_ERROR)
            # now (re-)create it
            try:
                file(key_f_name, "w").write("%d\n" % (self.__glob_config["IPC_KEY"]))
            except:
                self.log("Can't write IPC MessageQueue-key %d to file %s: %s" % (self.__glob_config["IPC_KEY"],
                                                                                 key_f_name,
                                                                                 process_tools.get_except_info()),
                         logging_tools.LOG_LEVEL_ERROR)
            else:
                self.log("wrote IPC MessageQueue-key %d to file %s" % (self.__glob_config["IPC_KEY"], key_f_name))
            if self.__glob_config["VERBOSE"]:
                self.log("allocated IPC MessageQueue with key %d" % (self.__glob_config["IPC_KEY"]))
        return success
    def loop_function(self):
        if self.__message_queue:
            recv_flag = self["exit_requested"] and self.__pyipc_mod.IPC_NOWAIT or 0
            data = self.__message_queue.receive(type = 1, flags = recv_flag)
            if not data:
                time.sleep(0.1)
                self._break_netserver()
            elif data.endswith("wakeup"):
                pass
            else:
                self.__relay_thread_queue.put(("new_ipc_request", (data, time.time())))
        else:
            # wait for exit
            time.sleep(1)
    def _force_flush_queue(self):
        num = 0
        if self.__message_queue:
            while True:
                data = self.__message_queue.receive()
                if data:
                    num += 1
                else:
                    break
        return num
    def thread_loop_post(self):
        # femove message-queue
        nflush = self._force_flush_queue()
        try:
            self.__pyipc_mod.removeIPC(self.__message_queue)
        except:
            self.log("unable to destroy the message-queue with MessageKey %d (after flushing %d messages): %s" % (self.__glob_config["IPC_KEY"],
                                                                                                                  nflush,
                                                                                                                  process_tools.get_except_info()),
                     logging_tools.LOG_LEVEL_WARN)
        else:
            self.log("destroyed the message-queue with MessageKey %d (%d messages flushed)" % (self.__glob_config["IPC_KEY"], nflush))
        try:
            os.unlink(self.__message_key_file_name)
        except:
            pass
        process_tools.delete_pid("collrelay/collrelay")
        if self.__msi_block:
            self.__msi_block.remove_meta_block()
        
class multiple_tcp_con(object):
    def __init__(self, glob_config, logger, mc_dict, command, hosts, res_dict):
        self.__glob_config = glob_config
        self.__logger      = logger
        self.__hosts = hosts
        self.__res_dict = res_dict
        self.__net_send = net_tools.network_send(timeout=self.__glob_config["CLIENT_TIMEOUT"], log_hook=self.log, verbose=False)
        self.__mc_dict = mc_dict
        self.__con_dicts = {}
        ns_ok = False
        for h_name in hosts:
            if not h_name in self.__res_dict:
                act_c = act_con(host=h_name, port=self.__glob_config["LISTEN_PORT"], comline=command)
                self.__con_dicts[h_name] = act_c
                try:
                    act_c.set_com_par(mc_dict, self.__glob_config["CLIENT_TIMEOUT"])
                except ValueError:
                    self.__res_dict[h_name] = act_c.get_act_state_and_str()
                else:
                    if self.__glob_config["USE_NET"]:
                        ns_ok = True
                        self.__net_send.add_object(net_tools.tcp_con_object(self._new_tcp_con,
                                                                            connect_state_call=self._connect_state_call,
                                                                            connect_timeout_call=self._connect_timeout,
                                                                            target_host=act_c.host,
                                                                            target_port=act_c.port,
                                                                            timeout=act_c.get_timeout(),
                                                                            bind_retries=1,
                                                                            rebind_wait_time=2))
                    else:
                        # local call
                        src_addr = ("local", 0)
                        data, mod_stuff = prepare_server_request(act_c.get_effective_comline(), mc_dict, from_net=False)
                        if mod_stuff:
                            data = mod_stuff(act_c.get_effective_comline(), self.__logger, addr=src_addr)
                        if data:
                            act_c.process_return(mc_dict, data)
                            self.__res_dict[h_name] = act_c.get_act_state_and_str()
        if ns_ok:
            self.__net_send.step()
            while not self.__net_send.exit_requested() and self.__net_send.get_num_objects():
                self.__net_send.step()
    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        self.__logger.log(level, what)
    def _connect_timeout(self, sock):
        self.set_host_error(sock.get_target_host(), "connect timeout")
        sock.close()
    def _connect_state_call(self, **args):
        if args["state"] == "error":
            self.set_host_error(args["host"], "Error cannot connect")
    def _new_tcp_con(self, sock):
        d_h = sock.get_target_host()
        return simple_tcp_obj(self, d_h, self.__con_dicts[d_h].get_effective_comline())
    def set_host_error(self, hst, what):
        self.__con_dicts[hst].set_state(limits.nag_STATE_CRITICAL, "Error: %s" % (what))
        self.__res_dict[hst] = self.__con_dicts[hst].get_act_state_and_str()
    def set_host_result(self, hst, what):
        p1_head, what = net_tools.check_for_proto_1_header(what)
        self.__con_dicts[hst].process_return(self.__mc_dict, what)
        self.__res_dict[hst] = self.__con_dicts[hst].get_act_state_and_str()
    def get_result(self):
        return self.__res_dict
    
class single_tcp_con(object):
    def __init__(self, glob_config, act_c):
        self.__glob_config = glob_config
        self.data = None
        self.__act_c = act_c
        self.__net_send = net_tools.network_send(timeout=self.__glob_config["CLIENT_TIMEOUT"], log_hook=self.log, verbose=False)
        self.__net_send.add_object(net_tools.tcp_con_object(self._new_tcp_con,
                                                            connect_state_call=self._connect_state_call,
                                                            connect_timeout_call=self._connect_timeout,
                                                            target_host=act_c.host,
                                                            target_port=act_c.port,
                                                            timeout=act_c.get_timeout(),
                                                            bind_retries=1,
                                                            rebind_wait_time=2))
        self.__net_send.step()
        while not self.__net_send.exit_requested() and self.__net_send.get_num_objects():
            self.__net_send.step()
    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        print "w, l", what, level
    def _connect_timeout(self, sock):
        self.set_host_error(sock.get_target_host(), "connect timeout")
        sock.close()
    def _connect_state_call(self, **args):
        if args["state"] == "error":
            self.__act_c.set_state(limits.nag_STATE_CRITICAL, "Error cannot connect")
    def _new_tcp_con(self, sock):
        return simple_tcp_obj(self, self.__act_c.host, self.__act_c.get_effective_comline())
    def set_host_error(self, hst, what):
        self.__act_c.set_state(limits.nag_STATE_CRITICAL, "Error: %s" % (what))
    def set_host_result(self, hst, what):
        p1_head, what = net_tools.check_for_proto_1_header(what)
        self.data = what
    
def get_hosts_from_db(groups):
    hosts = []
    db_con = mysql_tools.dbcon_container()
    dc = db_con.get_connection("cluster_full_access")
    if "LIST" in groups:
        dc.execute("SELECT dg.name AS dg_name, d.name FROM device_group dg, device_type dt, device d WHERE d.device_group = dg.device_group_idx AND d.device_type=dt.device_type_idx AND dt.identifier='H'")
        dg_dict = {}
        for db_rec in dc.fetchall():
            dg_dict.setdefault(db_rec["dg_name"], [])
            dg_dict[db_rec["dg_name"]].append(db_rec["name"])
        dg_names = sorted(dg_dict.keys())
        print "%s defined: %s" % (logging_tools.get_plural("devicegroup", len(dg_names)),
                                  ", ".join(dg_names))
        for dg_name in dg_names:
            print "\n".join(["  %-16s: - %3d hosts: %s" % (dg_name, len(dg_dict[dg_name]), logging_tools.compress_list(dg_dict[dg_name]))])
        hosts = []
    else:
        dc.execute("SELECT d.name FROM device d, device_group dg, device_type dt WHERE dt.device_type_idx = d.device_type AND dg.device_group_idx = d.device_group AND (%s) AND dt.identifier='H'" % (" OR ".join([x.count("%") and "dg.name LIKE('%s')" % (x) or "dg.name='%s'" % (x) for x in groups])))
        hosts += [x["name"] for x in dc.fetchall()]
        if not hosts:
            print "No hosts found for %s: %s" % (logging_tools.get_plural("group", len(groups)),
                                                 ", ".join(groups))
    dc.release()
    del db_con
    return hosts

def do_client_code(glob_config, logger, hosts, command, mc_dict):
    ret = limits.nag_STATE_UNKNOWN
    # sort hosts
    hosts = sorted(set([host for host in hosts]))
    res_dict = {}
    if glob_config["PRE_PING"] and len(hosts) > 1:
        s_time = time.time()
        if glob_config["SHOW_HEADERS"]:
            print "Checking reachability of %s (%s, command %s, timeout is %d) ..." % (logging_tools.get_plural("host", len(hosts)),
                                                                                       logging_tools.compress_list(hosts),
                                                                                       command,
                                                                                       glob_config["CLIENT_TIMEOUT"]),
        r_dict = net_tools.ping_hosts(hosts, glob_config["BIND_RETRIES"], 4.0)
        e_time = time.time()
        if glob_config["SHOW_HEADERS"]:
            if not r_dict:
                print "no permission to create a raw-socket"
            else:
                print "done in %s" % (logging_tools.get_diff_time_str(e_time - s_time))
        num_dict = dict([(x, []) for x in ["down", "up", "unknown"]])
        for h_name, stuff in r_dict.iteritems():
            if type(stuff) == type(""):
                num_dict["unknown"].append(h_name)
                res_dict[h_name] = (5, stuff)
            elif stuff["received"] == 0:
                num_dict["down"].append(h_name)
                res_dict[h_name] = (5, "down")
            else:
                num_dict["up"].append(h_name)
        if glob_config["SHOW_HEADERS"]:
            print "stat: %s" % (", ".join(["%s %s (%s)" % (logging_tools.get_plural("host", len(num_dict[x])),
                                                           x,
                                                           logging_tools.compress_list(num_dict[x])) for x in ["down", "up", "unknown"] if num_dict[x]]))
    s_time = time.time()
    # connection code, also handles no-net connections
    stc = multiple_tcp_con(glob_config, logger, mc_dict, command, hosts, res_dict)
    res_dict = stc.get_result()
    e_time = time.time()
    fl = logging_tools.form_list()
    fl.set_format_string(0, "s", "-", "", " :")
    fl.set_format_string(1, "d", "-", "", " :")
    last_idx_set = 1
    for h_name in hosts:
        act_ret, ret_str = res_dict[h_name]
        ret_lines = ret_str.split("\n")
        first_line = ret_lines.pop(0)
        ret_parts = [x.strip() for x in first_line.split(";")]
        if len(ret_parts) > last_idx_set:
            last_idx_set += 1
            fl.set_format_string(last_idx_set, "s", "-", "", ";")
        fl.add_line([h_name, act_ret] + ret_parts)
        for r_line in ret_lines:
            if glob_config["SHOW_HOST_NAME"]:
                fl.add_line([h_name, r_line])
            else:
                fl.add_line(r_line)
        ret = max(ret, act_ret)
    if glob_config["SHOW_HEADERS"]:
        fl.add_line(["contacted %s in %s" % (logging_tools.get_plural("device", len(hosts)),
                                             logging_tools.get_diff_time_str(e_time - s_time))])
    return fl, ret

class my_options(optparse.OptionParser):
    def __init__(self, glob_config):
        self.__glob_config = glob_config
        optparse.OptionParser.__init__(self,
                                       usage="%prog [GENERAL OPTIONS] [SERVER/RELAY OPTIONS] command [CLIENT OPTIONS]",
                                       add_help_option=False)
        self.disable_interspersed_args()
        self.add_option("-h", "--help", help="help", action="callback", callback=self.show_help)
        self.add_option("--longhelp", help="this help (long version)", action="callback", callback=self.show_help)
        self.add_option("--options", help="show internal options and flags (for dev)", action="callback", callback=self.show_help)
        self.add_option("-d", dest="daemonize", default=True, action="store_false", help="do not run in debug mode (no forking)") 
        self.add_option("-k", dest="kill_running", default=True, action="store_false", help="do not kill running instances")
        self.add_option("-v", dest="verbose", default=0, action="count", help="increase verbosity [%default]")
        self.add_option("-V", action="callback", callback=self.show_version, help="show Version")
        self.add_option("-l", dest="show_log_queue", default=False, action="store_true", help="show logging output [%default]")
        self.add_option("-b", dest="basedir_name", type="str", default="/etc/sysconfig/host-monitoring.d", help="base name for various config files [%default]")
        self.add_option("-m", dest="opmode", type="str", default="", help="set operation mode, default to auto-detect")
        # server options
        server_group = optparse.OptionGroup(self, "server options")
        server_group.add_option("-r", dest="bind_retries", type="int", default=5, help="number of retries to bind to socket (server) or number of relay threads (relayer) [%default]")
        server_group.add_option("-p", dest="listen_port", type="int", default=STD_PORT, help="set port to listen to [%default]")
        server_group.add_option("-t", dest="main_timer", type="int", default=60, help="set main timer (server) or timeout (client) [%default]")
        self.add_option_group(server_group)
        # relayer options
        relayer_group = optparse.OptionGroup(self, "relayer options")
        relayer_group.add_option("-n", dest="ipc_key", default=0, type="int", help="key of the IPC Messagequeue (default is [%default], autoseek)")
        relayer_group.add_option("-f", dest="flood_mode", default=False, action="store_true", help="enable flood mode (faster pings, [%default])")
        self.add_option_group(relayer_group)
        # client options
        client_group = optparse.OptionGroup(self, "client options")
        client_group.add_option("-P", dest="pre_ping", default=True, action="store_false", help="disable pre-ping for client mode")
        client_group.add_option("-G", dest="groups", type="str", default="", help="groups(s) to connect to, comma separated [%default], only usable whith db connection")
        client_group.add_option("--host", dest="hosts", type="str", default="", help="host(s) to connect to, comma separated [%default]")
        client_group.add_option("--use-net", "--local", dest="use_net", default=True, action="store_false", help="use client-instance for call")
        client_group.add_option("--no-headers", dest="show_headers", default=True, action="store_false", help="dont show headers for client mode")
        self.add_option_group(client_group)
        #
        self.add_option("--check-kerio", dest="check_kerio", default=False, action="store_true", help="check kerio stats [%default]")
        self.add_option("--check-nameserver", dest="check_nameserver", default=False, action="store_true", help="check nameserver stats [%default]")
        self.add_option("--no-inotify", dest="start_inotify_thread", default=True, action="store_false", help="disable inotify thread")
        self.add_option("--no-background", dest="start_background_thread", default=True, action="store_false", help="disable background thread")
        self.add_option("--show-host-name", dest="show_host_name", action="store_true", default=False, help="show hostname in every line of client-mode output")
        self.add_option("--disabled-modules", dest="disabled_modules", type="str", default="", help="list of modules to disable [%default]")
    def show_help(self, option, opt_str, value, *args, **kwargs):
        self.print_help()
        logger = logging_tools.get_logger(self.__glob_config["LOG_NAME"],
                                          self.__glob_config["LOG_DESTINATION"],
                                          init_logger=True)
        # load modules
        mc_dict = all_modules(self.__glob_config, logger)
        module_keys = sorted(mc_dict.module_keys())
        print "\nOverview of %s:" % (logging_tools.get_plural("loaded module", len(module_keys)))
        out_list = logging_tools.new_form_list()
        for key in module_keys:
            mod = mc_dict.get_module(key)
            out_list.append((logging_tools.form_entry(mod.name, header="Name"),
                               logging_tools.form_entry(mod.info or "None", header="Info")))
        print out_list
        print "\nOverview of %s:" % (logging_tools.get_plural("function", len(mc_dict.keys())))
        cd_keys = sorted(mc_dict.keys())
        if str(option) == "--options":
            out_list = logging_tools.new_form_list()
            for com in cd_keys:
                func_d = mc_dict[com]
                out_list.append((logging_tools.form_entry(com, header="Name"),
                                 logging_tools.form_entry(func_d.module_name, header="Module"),
                                 logging_tools.form_entry(func_d.relay_call   and "*" or "-", header="relay_call"),
                                 logging_tools.form_entry(func_d.net_only     and "*" or "-", header="net_only"),
                                 logging_tools.form_entry(func_d.special_hook or "-", header="special_hook")))
            print out_list
        else:
            lu_dict = {}
            for com in cd_keys:
                func_d = mc_dict[com]
                mname = func_d.module_name
                if not mname in lu_dict:
                    lu_dict[mname] = []
                lu_dict[mname].append(func_d)
            for mod_src in lu_dict.keys():
                print ("\n--- mod %s (%s) %s " % (mod_src, logging_tools.get_plural("function", len(lu_dict[mod_src])), "-" * 80))[:100]
                for func_d in lu_dict[mod_src]:
                    print "  %-20s %s" % (func_d.name, str(func_d.help_str))
                    if str(option) == "--longhelp":
                        for h_type, opt_str, info_str in [(a, b, c) for a, b, c in [("Server", func_d.short_server_info, func_d.long_server_info),
                                                                                    ("Client", func_d.short_client_info, func_d.long_client_info)] if b and c]:
                            out_lines = textwrap.wrap(info_str, 50)
                            out_lines = ["%44s%s" % (x, y) for x, y in zip(["    %-18s %-20s " % ("%s Options" % (h_type), opt_str)] + [""]*(len(out_lines)-1), out_lines)]
                            print "\n".join(out_lines)
        sys.exit(-0)
    def show_version(self, option, opt_str, value, *args, **kwargs):
        print "Version %s" % (VERSION_STRING)
        sys.exit(-0)
    def parse(self):
        options, args = self.parse_args()
        # copy options
        self.__glob_config["DAEMONIZE"]               = options.daemonize
        self.__glob_config["VERBOSE"]                 = options.verbose
        self.__glob_config["SHOW_HEADERS"]            = options.show_headers
        self.__glob_config["CHECK_KERIO"]             = options.check_kerio
        self.__glob_config["CHECK_NAMESERVER"]        = options.check_nameserver
        self.__glob_config["FLOOD_MODE"]              = options.flood_mode
        self.__glob_config["PRE_PING"]                = options.pre_ping
        self.__glob_config["SHOW_HOST_NAME"]          = options.show_host_name
        self.__glob_config["START_INOTIFY_THREAD"]    = options.start_inotify_thread
        self.__glob_config["START_BACKGROUND_THREAD"] = options.start_background_thread
        self.__glob_config["USE_NET"]                 = options.use_net
        self.__glob_config["IPC_KEY"]                 = int(options.ipc_key)
        self.__glob_config["BIND_RETRIES"]            = int(options.bind_retries)
        self.__glob_config["LISTEN_PORT"]             = int(options.listen_port)
        self.__glob_config["MAIN_TIMER"]              = int(options.main_timer)
        self.__glob_config["CLIENT_TIMEOUT"]          = int(options.main_timer)
        self.__glob_config["DISABLED_MODULES"]        = [entry.strip() for entry in options.disabled_modules.split(",") if entry.strip()]
        self.__glob_config["BASEDIR_NAME"]            = options.basedir_name
        if not options.opmode:
            if self.__glob_config["PROGRAM_NAME"] == "collclient.py":
                options.opmode = "c"
            elif self.__glob_config["PROGRAM_NAME"] == "collrelay.py":
                options.opmode = "r"
            elif self.__glob_config["PROGRAM_NAME"] == "collserver.py":
                options.opmode = "s"
            else:
                options.opmode = "s"
        groups = [entry.strip() for entry in options.groups.split(",") if entry.strip()]
        hosts = [entry.strip() for entry in options.hosts.split(",") if entry.strip()]
        if groups and mysql_tools:
            hosts = get_hosts_from_db(groups)
        elif not hosts:
            hosts = [self.__glob_config["LONG_HOST_NAME"]]
        options.hosts = hosts
        self.__glob_config["LOG_NAME"] = {"c" : "collclient",
                                          "s" : "collserver",
                                          "r" : "collrelay"}.get(options.opmode, "unknown_opmode_%s" % (options.opmode))
        if options.show_log_queue:
            self.__glob_config["LOG_DESTINATION"] = "stdout"
        return options, args
        
def main():
    signal.signal(signal.SIGTERM, sig_term_handler), 
    signal.signal(signal.SIGINT , sig_int_handler )
    # read global configfile
    glob_config = configfile.configuration("hostmon")
    glob_config.add_config_entries({"MODULE_DIR"              : configfile.str_c_var("/usr/local/sbin/modules"),
                                    "BASEDIR_NAME"            : configfile.str_c_var("/etc/sysconfig/host-monitoring.d"),
                                    "VERBOSE"                 : configfile.int_c_var(0),
                                    "LISTEN_PORT"             : configfile.int_c_var(STD_PORT),
                                    "COMMAND_LISTEN_PORT"     : configfile.int_c_var(STD_COM_PORT),
                                    "RELAYER_LISTEN_PORT"     : configfile.int_c_var(RELAYER_PORT),
                                    "DAEMONIZE"               : configfile.bool_c_var(True),
                                    "SHOW_HEADERS"            : configfile.bool_c_var(True),
                                    "MAIN_TIMER"              : configfile.int_c_var(60),
                                    "CLIENT_TIMEOUT"          : configfile.int_c_var(60),
                                    "BIND_RETRIES"            : configfile.int_c_var(5),
                                    "USE_NET"                 : configfile.bool_c_var(True),
                                    "IPC_KEY"                 : configfile.int_c_var(0),
                                    "FLOOD_MODE"              : configfile.bool_c_var(False),
                                    "PROGRAM_NAME"            : configfile.str_c_var("not set"),
                                    "LONG_HOST_NAME"          : configfile.str_c_var("not set"),
                                    "LOG_NAME"                : configfile.str_c_var("host-monitoring"),
                                    "LOG_DESTINATION"         : configfile.str_c_var("uds:/var/lib/logging-server/py_log"),
                                    "PRE_PING"                : configfile.bool_c_var(True),
                                    "RELAY_CONNECT_TIMEOUT"   : configfile.int_c_var(5),
                                    "FW_FAIL_COUNTER"         : configfile.int_c_var(60),
                                    "START_INOTIFY_THREAD"    : configfile.bool_c_var(True),
                                    "START_BACKGROUND_THREAD" : configfile.bool_c_var(True),
                                    "DISABLED_MODULES"        : configfile.array_c_var([]),
                                    "CHECK_NAMESERVER"        : configfile.bool_c_var(False),
                                    "CHECK_KERIO"             : configfile.bool_c_var(False),
                                    "SHOW_HOST_NAME"          : configfile.bool_c_var(False)})
    glob_config.parse_file("/etc/sysconfig/host-monitoring")
    glob_config["LONG_HOST_NAME"] = socket.getfqdn(socket.gethostname())
    glob_config["PROGRAM_NAME"] = os.path.basename(sys.argv[0])
    loc_options, loc_args = my_options(glob_config).parse()
    # determine module_path
    euid = os.geteuid()
    if euid == 666 or os.getcwd() == "/usr/local/share/home/local/development/host-monitoring":
        glob_config["MODULE_DIR"] = "/usr/local/share/home/local/development/host-monitoring/modules"
    elif euid == 500 or os.getcwd() in ["/usr/local/share/home/local/development/host-monitoring",
                                        "/home/local/development/host-monitoring"]:
        glob_config["MODULE_DIR"] = "%s/modules" % (os.getcwd())
    else:
        glob_config["MODULE_DIR"] = "/usr/local/sbin/modules"
    logger = logging_tools.get_logger(glob_config["LOG_NAME"],
                                      glob_config["LOG_DESTINATION"],
                                      init_logger=True)
    if loc_options.kill_running:
        process_tools.kill_running_processes(glob_config["PROGRAM_NAME"])
    mc_dict = all_modules(glob_config, logger)
    if mc_dict.load_errors:
        print "Error loading all modules, exiting ..."
        print "\n".join([" - %s" % (line) for line in mc_dict.load_errors])
        sys.exit(1)
    # init modules
    all_ok = True
    for actmod_name in mc_dict.module_keys():
        actmod = mc_dict.get_module(actmod_name)
        ok = actmod.check_global_config(glob_config)
        if not ok:
            all_ok = False
            print "Error parsing global configs in module %s" % (actmod.name)
    if not all_ok:
        sys.exit(limits.nag_STATE_CRITICAL)
    # process server args for all loaded modules
    for actmod_name in mc_dict.module_keys():
        actmod = mc_dict.get_module(actmod_name)
        all_ok = True
        if hasattr(actmod, "process_server_args"):
            logger.info("Calling process_server_args() for module %s" % (actmod.name))
            logger.set_prefix("  psa(), mod %s: " % (actmod.name))
            ok, why = actmod.process_server_args(glob_config, logger)
            if not ok:
                all_ok = False
                logger.error("Error parsing server-arguments in module %s : %s" % (actmod.name, str(why)))
            logger.set_prefix()
        if not all_ok:
            sys.exit(limits.nag_STATE_CRITICAL)
    if loc_options.opmode == "c":
        if loc_options.hosts:
            command = " ".join(loc_args) or "version"
            try:
                out_list, ret_code = do_client_code(glob_config, logger, loc_options.hosts, command, mc_dict)
                print out_list
            except int_error:
                print "Got int, exiting ..."
                ret_code = 5
        else:
            ret_code = limits.nag_STATE_UNKNOWN
    elif loc_options.opmode in ["s", "r"]:
        handledict = {"s" : {"out"    : (1, "collserver.out"),
                             "err"    : (0, "/var/lib/logging-server/py_err"),
                             "strict" : False},
                      "r" : {"out"    : (1, "collrelay.out") ,
                             "err"    : (0, "/var/lib/logging-server/py_err")}}
        run_dict = {"s" : "collserver",
                    "r" : "collrelay"}
        process_tools.renice()
        if glob_config["DAEMONIZE"]:
            process_tools.become_daemon()
            # to suppress stream_flush errors when exiting
            old_stdout, old_stderr = (sys.stdout, sys.stderr)
            hc_ok = process_tools.set_handles(handledict[loc_options.opmode])
        else:
            hc_ok = 1
            print "Debugging %s" % (run_dict[loc_options.opmode])
        if hc_ok:
            if loc_options.opmode == "s":
                thread_pool = server_thread_pool(glob_config, logger, mc_dict)
            elif loc_options.opmode == "r":
                thread_pool = relay_thread_pool(glob_config, logger, mc_dict)
            thread_pool.thread_loop()
            ret_code = limits.nag_STATE_OK
        else:
            print "Cannot modify handles, exiting..."
            ret_code = limits.nag_STATE_CRITICAL
        if glob_config["DAEMONIZE"] and hc_ok != 2:
            process_tools.handles_write_endline()
            sys.stdout, sys.stderr = (old_stdout, old_stderr)
    else:
        print "Unknown opmode, exiting..."
        ret_code = -1
    logger.log_command("CLOSE")
    sys.exit(ret_code)

if __name__ == "__main__":
    main()
