#!/usr/bin/python-init -Ot
#
# -*- coding: utf-8 -*-
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008,2010,2011,2012,2013 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of rms-tools
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
""" pro/epilogue script """

import sys

# clean sys.path
sys.path = [entry for entry in sys.path if entry.startswith("/opt")]

import pwd, grp
import time
import stat
import socket
import os
import os.path
import logging_tools
import process_tools
import configfile
import pprint
import server_command
import net_tools
import threading_tools
import zmq
    
SEP_LEN = 70
LOCAL_IP = "127.0.0.1"
#PROFILE_PREFIX = ".mon"
CONFIG_FILE_NAME = "proepilogue.conf"

def sec_to_str(in_sec):
    diff_d = int(in_sec / (3600 * 24))
    dt = in_sec - 3600 * 24 * diff_d
    diff_h = int(dt / 3600)
    dt -= 3600 * diff_h
    diff_m = int(dt / 60)
    dt -= diff_m * 60
    #if diff_d:
    out_f = "%2d:%02d:%02d:%02d" % (diff_d, diff_h, diff_m, dt)
    #else:
    #    out_f = "%2d:%02d:%02d" % (diff_h, diff_m, dt)
    return out_f


class job_thread(threading_tools.thread_obj):
    def __init__(self, glob_config, opt_dict, net_server):
        self.__glob_config = glob_config
        self.__opt_dict = opt_dict
        self.__net_server = net_server
        self._init_log_template()
        threading_tools.thread_obj.__init__(self, "job", loop_function=self._loop)
        self._init_exit_code()
        self.register_func("result_ok", self._result_ok)
        self.register_func("result_error", self._result_error)
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK, **args):
        if self.__logger:
            self.__logger.log(log_level, what)
        else:
            self.__log_template.log(what, log_level)
        if args.get("do_print", False):
            self._print("%s%s" % ("[%s] " % (logging_tools.get_log_level_str(log_level)) if log_level != logging_tools.LOG_LEVEL_OK else "", what))
        if log_level != logging_tools.LOG_LEVEL_OK:
            self.send_pool_message(("log", (what, log_level)))
    def _log_arguments(self):
        out_list = logging_tools.new_form_list()
        for key in sorted(self.__opt_dict.keys()):
            out_list.append([logging_tools.form_entry(key, header="key"),
                             logging_tools.form_entry(str(type(self.__opt_dict[key])), header="type"),
                             logging_tools.form_entry(self.__opt_dict[key], header="value")])
        for line in str(out_list).split("\n"):
            self.log(line)
##    def _set_localhost_stuff(self):
##        try:
##            self.__opt_dict["HOST_IP"] = socket.gethostbyname(self.__opt_dict["HOST_SHORT"])
##        except:
##            self.log("cannot resolve host_name '%s': %s" % (self.__opt_dict["HOST_SHORT"],
##                                                            process_tools.get_except_info()),
##                     logging_tools.LOG_LEVEL_ERROR)
##            self.__opt_dict["HOST_IP"] = "127.0.0.1"
##    def _copy_environments(self):
##        self.__env_dict = dict([(key, str(os.environ[key])) for key in os.environ.keys()])
##        self.__env_int_dict = dict([(key, value) for key, value in [line.split("=", 1) for line in file("%s/config" % (self.__env_dict["SGE_JOB_SPOOL_DIR"]), "r").read().strip().split("\n") if line.count("=")]])
    # loop functions
    def loop_start(self):
        # OLD CODE, be aware
        self.__send_idx, self.__pending_dict = (0, {})
        self.__start_time = time.time()
        self.send_pool_message(("log", "log_name is %s" % (self.__log_name)))
        # copy environment
        self._copy_environments()
        # populate glob_config
        self._parse_server_addresses()
        self._set_localhost_stuff()
        # populate opt_dict
        self._parse_sge_env()
        self._check_user()
        self._parse_job_script()
        self._log_arguments()
        self._read_config()
        #self._log_config()
        #self.write_file("aha", "/etc/hosts")
        #self.write_file("aha", "/etc/services")
        if self.is_start_call():
            self._log_environments()
            self._log_limits()
        if self.is_proepilogue_call():
            self._write_proepi_header()
        elif self.is_pe_call():
            self._write_pe_header()
        if self.is_start_call():
            self._write_run_info()
    def _loop(self):
        self.log("starting inner loop")
        if self.__opt_dict["CALLER_NAME_SHORT"] == "prologue":
            self._prologue()
        elif self.__opt_dict["CALLER_NAME_SHORT"] == "epilogue":
            self._epilogue()
        elif self.is_pe_start_call():
            self._pe_start()
        elif self.is_pe_stop_call():
            self._pe_stop()
        else:
            pass
        self.log("ending inner loop")
        self.send_pool_message(("done", self.__return_value))
        self.__net_server.break_call()
        self.inner_loop(force_wait=True)
    def loop_end(self):
        if self.__opt_dict["CALLER_NAME_SHORT"] == "epilogue":
            self._log_resources()
        self.__end_time = time.time()
        if self.is_proepilogue_call():
            self._write_proepi_footer()
        elif self.is_pe_call():
            self._write_pe_footer()
        self.log("took %s" % (logging_tools.get_diff_time_str(self.__end_time - self.__start_time)))
        if self.__log_template:
            self.__log_template.set_command_and_send("close_log")
        else:
            self.__logger.log_command("CLOSE")
    # different runtypes
    def _prologue(self):
        self._send_tag("job_start", queue_list=[self.__opt_dict["HOST_SHORT"]])
        self._kill_foreign_pids([LOCAL_IP])
        self._remove_foreign_ipcs([LOCAL_IP])
        if self.__glob_config.get("UMOUNT_CALL", True):
            self._umount_nfs_mounts([LOCAL_IP])
        self._create_wrapper_script()
        if self.__opt_dict.get("MONITOR_JOBS", True):
            self._start_monitor_threads([LOCAL_IP], "%s.s" % (self.__opt_dict["FULL_JOB_ID"]))
    def _epilogue(self):
        self._send_tag("job_stop", queue_list=[self.__opt_dict["HOST_SHORT"]])
        if self.__opt_dict.get("MONITOR_JOBS", True):
            self._collect_monitor_threads([LOCAL_IP], "%s.s" % (self.__opt_dict["FULL_JOB_ID"]))
            self._stop_monitor_threads([LOCAL_IP], "%s.s" % (self.__opt_dict["FULL_JOB_ID"]))
            self._show_monitor_info()
        self._kill_foreign_pids([LOCAL_IP])
        self._remove_foreign_ipcs([LOCAL_IP])
        if self.__glob_config.get("UMOUNT_CALL", True):
            self._umount_nfs_mounts([LOCAL_IP])
        self._kill_stdout_stderr_childs()
        self._delete_wrapper_script()
    def _pe_start(self):
        self.log("pe_start called")
        self._generate_hosts_file()
        self._send_tag("pe_start", queue_list=self.__node_list)
        self._write_hosts_file("save")
        self._show_pe_hosts()
        # check reachability of user-homes
        self._check_homedir(self.__node_list)
        if not self.__return_value:
            self._flight_check("preflight")
        if not self.__return_value:
            # check if exit_code is still ok
            self._kill_foreign_pids(self.__node_list)
            self._remove_foreign_ipcs(self.__node_list)
            if self.__glob_config.get("UMOUNT_CALL", True):
                self._umount_nfs_mounts(self.__node_list)
            if self.__opt_dict.get("MONITOR_JOBS", True):
                self._start_monitor_threads(self.__node_list, "%s.p" % (self.__opt_dict["FULL_JOB_ID"]))
            # determine how to establish the lam universe
            if self.__opt_dict["CALLER_NAME_SHORT"] == "lamstart":
                self._call_command("lamboot", "%%s -v %s" % (self.__opt_dict["HOSTFILE_PLAIN_MPI"]), hold_on_error=True, error_str="lamboot not found")
    def _pe_stop(self):
        self.log("pe_stop called")
        self._generate_hosts_file()
        self._send_tag("pe_stop", queue_list=self.__node_list)
        self._show_pe_hosts()
        self._write_hosts_file("keep")
        if self.__opt_dict.get("MONITOR_JOBS", True):
            self._collect_monitor_threads(self.__node_list, "%s.p" % (self.__opt_dict["FULL_JOB_ID"]))
            self._stop_monitor_threads(self.__node_list, "%s.p" % (self.__opt_dict["FULL_JOB_ID"]))
        if self.__opt_dict["CALLER_NAME_SHORT"] == "lamstop":
            self._call_command(["lamwipe", "wipe"], "%%s -v %s" % (self.__opt_dict["HOSTFILE_PLAIN_MPI"]), hold_on_error=False, error_str="lamwipe or wipe not found")
        self._kill_foreign_pids(self.__node_list)
        self._remove_foreign_ipcs(self.__node_list)
        if self.__glob_config.get("UMOUNT_CALL", True):
            self._umount_nfs_mounts(self.__node_list)
        self._flight_check("postflight")
        self._write_hosts_file("delete")
    # helper functions
    # for pe (parallel)
    # job monitor stuff
    def _start_monitor_threads(self, con_list, mon_id):
        self.log("Starting monitor threads with id %s on %s" % (mon_id,
                                                                logging_tools.get_plural("node", len(con_list))))
        self._collserver_command(dict([(con_entry, ("start_monitor", mon_id)) for con_entry in con_list]), result_type="o")
    def _stop_monitor_threads(self, con_list, mon_id):
        self.log("Stoping monitor threads with id %s on %s" % (mon_id,
                                                               logging_tools.get_plural("node", len(con_list))))
        self._collserver_command(dict([(con_entry, ("stop_monitor", mon_id)) for con_entry in con_list]), result_type="o")
    def _collect_monitor_threads(self, con_list, mon_id):
        self.log("Collecting monitor threads with id %s on %s" % (mon_id,
                                                                  logging_tools.get_plural("node", len(con_list))))
        self.__act_monitor_dict = {}
        self._collserver_command(dict([(con_entry, ("monitor_info", mon_id)) for con_entry in con_list]), result_type="o", decode_func=self._decode_monitor_result)
        self.log("got monitor dicts for %s: %s" % (logging_tools.get_plural("host", len(self.__act_monitor_dict.keys())),
                                                   logging_tools.compress_list(self.__act_monitor_dict.keys())))
        mon_file = "/tmp/.monitor_%s" % (mon_id)
        try:
            open(mon_file, "w").write(server_command.sys_to_net(self.__act_monitor_dict))
        except:
            self.log("cannot write monitor file %s: %s" % (mon_file,
                                                           process_tools.get_except_info()),
                     logging_tools.LOG_LEVEL_ERROR)
    def _show_monitor_info(self):
        # read mon_dicts
        mon_dict = {}
        for key, postfix in [("serial", "s"),
                             ("parallel", "p")]:
            mon_file = "/tmp/.monitor_%s.%s" % (self.__opt_dict["FULL_JOB_ID"],
                                                postfix)
            if os.path.isfile(mon_file):
                try:
                    mon_stuff = server_command.net_to_sys(open(mon_file, "r").read())
                except:
                    self.log("cannot read %s monitor data from %s: %s" % (key,
                                                                          mon_file,
                                                                          process_tools.get_except_info()),
                             logging_tools.LOG_LEVEL_ERROR)
                else:
                    mon_dict[key] = mon_stuff
                    try:
                        os.unlink(mon_file)
                    except:
                        self.log("cannot remove %s monitor data file %s: %s" % (key,
                                                                                mon_file,
                                                                                process_tools.get_except_info()),
                                 logging_tools.LOG_LEVEL_ERROR)
            else:
                self.log("no %s monitor_file %s" % (key,
                                                    mon_file),
                         logging_tools.LOG_LEVEL_WARN)
        # show data
        for mon_key in sorted(mon_dict.keys()):
            mon_stuff = mon_dict[mon_key]
            mon_hosts = mon_stuff.keys()
            self._print("")
            self._print("%s monitor data found for %s: %s" % (mon_key,
                                                              logging_tools.get_plural("host", len(mon_hosts)),
                                                              logging_tools.compress_list(mon_hosts)))
        self._print("")
    # general
    def _add_script_var(self, key, value):
        var_file = self._get_var_script_name()
        self.log("adding variable (%s=%s) to var_file %s" % (key,
                                                             value,
                                                             var_file))
        file(var_file, "a").write("export %s=%s\n" % (key, value))
##    def _parse_job_script(self):
##        if os.environ.has_key("JOB_SCRIPT"):
##            script_file = os.environ["JOB_SCRIPT"]
##            try:
##                lines = [line.strip() for line in file(script_file, "r").read().split("\n")]
##            except:
##                self.log("Cannot read Scriptfile '%s' (%s)" % (script_file,
##                                                               process_tools.get_except_info()),
##                         logging_tools.LOG_LEVEL_ERROR)
##            else:
##                if self.__opt_dict["CALLER_NAME_SHORT"] == "prologue":
##                    s_list = logging_tools.new_form_list()
##                else:
##                    s_list = None
##                num_lines, num_sge, num_init = (len(lines), 0, 0)
##                init_dict = {}
##                for line, line_num in zip(lines, xrange(len(lines))):
##                    if s_list is not None:
##                        s_list.append([logging_tools.form_entry(line_num + 1, header="line"),
##                                       logging_tools.form_entry(line, header="content")])
##                    if line.startswith("#$ "):
##                        num_sge += 1
##                    elif line.startswith("#init "):
##                        # valid init-keys:
##                        # MONITOR=<type>
##                        # MONITOR_KEYS=<key_list;>
##                        # MONITOR_FULL_KEY_LIST=<true>
##                        # TRIGGER_ERROR (flag, triggers error)
##                        # EXTRA_WAIT=x (waits for x seconds)
##                        num_init += 1
##                        line_parts = [x.split("=", 1) for x in line[5:].strip().split(",")]
##                        self.log("found #init-line '%s'" % (line))
##                        if line_parts:
##                            for key, value in [x for x in line_parts if len(x) == 2]:
##                                key, value = (key.strip().upper(), value.strip().lower())
##                                if key and value:
##                                    init_dict[key] = value
##                                    self.log("recognised init option '%s' (value '%s')" % (key, value))
##                                    self.__opt_dict.add_config_dict({key : configfile.str_c_var(value, source="jobscript")})
##                            for key in [x[0].strip().upper() for x in line_parts if len(x) == 1]:
##                                init_dict[key] = True
##                                self.log("recognised init option '%s' (value '%s')" % (key, True))
##                                self.__opt_dict.add_config_dict({key : configfile.bool_c_var(True, source="jobscript")})
##                self.log("Scriptfile '%s' has %d lines (%s and %s)" % (script_file,
##                                                                       num_lines,
##                                                                       logging_tools.get_plural("SGE related line", num_sge),
##                                                                       logging_tools.get_plural("init.at related line", num_init)))
##                if s_list:
##                    self.write_file("jobscript", str(s_list).split("\n"), linenumbers=False)
##        else:
##            self.log("environ has no JOB_SCRIPT key", logging_tools.LOG_LEVEL_WARN)
##    def _parse_server_addresses(self):
##        for src_file, key, default in [("/etc/motherserver", "MOTHER_SERVER", "localhost"),
##                                       ("/etc/sge_server"  , "SGE_SERVER"   , "localhost")]:
##            try:
##                act_val = file(src_file, "r").read().split()[0]
##            except:
##                self.log("cannot read %s from %s: %s" % (key,
##                                                         src_file,
##                                                         process_tools.get_except_info()),
##                         logging_tools.LOG_LEVEL_ERROR)
##                act_val = default
##            self.__glob_config.add_config_dict({key : configfile.str_c_var(act_val, source=src_file)})
##    def _parse_sge_env(self):
##        # pe name
##        if os.environ.has_key("PE") and os.environ.has_key("PE_HOSTFILE"):
##            self.__opt_dict["PE"] = os.environ["PE"]
##        else:
##            self.__opt_dict["PE"] = ""
##        # TASK_ID
##        if os.environ.has_key("SGE_TASK_FIRST") and os.environ.has_key("SGE_TASK_LAST") and os.environ.has_key("SGE_TASK_ID") and os.environ.has_key("SGE_TASK_STEPSIZE"):
##            if os.environ["SGE_TASK_ID"] == "undefined":
##                self.__opt_dict["TASK_ID"] = 0
##            else:
##                try:
##                    self.__opt_dict["TASK_ID"] = int(os.environ["SGE_TASK_ID"])
##                except:
##                    self.log("error extracting SGE_TASK_ID: %s" % (process_tools.get_except_info()),
##                             logging_tools.LOG_LEVEL_ERROR)
##                    self.__opt_dict["TASK_ID"] = 0
##                else:
##                    pass
##        else:
##            self.__opt_dict["TASK_ID"] = 0
##        self.__opt_dict["FULL_JOB_ID"] = "%s%s" % (self.__opt_dict["JOB_ID"],
##                                                   ".%s" % (self.__opt_dict["TASK_ID"]) if self.__opt_dict["TASK_ID"] else "")
##    def _check_user(self):
##        try:
##            pw_data = pwd.getpwnam(self.__opt_dict["JOB_OWNER"])
##        except KeyError:
##            pw_data = None
##            uid, gid, group = (0, 0, "unknown")
##            self.log("Unknown user '%s', using ('%s', %d, %d) as (group, uid, gid)" % (self.__opt_dict["JOB_OWNER"],
##                                                                                       group,
##                                                                                       uid,
##                                                                                       gid),
##                     logging_tools.LOG_LEVEL_ERROR)
##        else:
##            uid = pw_data[2]
##            gid = pw_data[3]
##            try:
##                grp_data = grp.getgrgid(gid)
##            except KeyError:
##                group = "unknown"
##                self.log("Unknown group-id %d for user '%s', using %s as group" % (gid,
##                                                                                   user,
##                                                                                   group),
##                         logging_tools.LOG_LEVEL_ERROR)
##            else:
##                group = grp_data[0]
##        self.__opt_dict["GROUP"] = group
##        self.__opt_dict["UID"] = uid
##        self.__opt_dict["GID"] = gid
    def _call_command(self, com_names, arg_form="%s", **args):
        # args: retries (default 2)
        max_retries = args.get("retries", 2)
        ret_val = 1
        if type(com_names) == type(""):
            com_names = [com_names]
        s_time = time.time()
        self.log("call_command for %s (%s), (argument_formstring is '%s')" % (logging_tools.get_plural("command", len(com_names)),
                                                                              ", ".join(com_names),
                                                                              arg_form))
        for com_name in com_names:
            path_field = []
            com = arg_form % com_name
            compath_found = ""
            if com_name.startswith("/"):
                path_field = ["/"]
                if os.path.exists(com_name):
                    compath_found = com_name
            else:
                for path in sorted(dict([(x.strip(), 0) for x in os.environ.get("PATH", "").split(":") if x.startswith("/")]).keys()):
                    compath_found = "%s/%s" % (path, com_name)
                    path_field.append(path)
                    if os.path.exists(compath_found):
                        break
                else:
                    compath_found = ""
            if compath_found:
                self.log("starting command '%s' (full path of executable %s is %s), %s" % (com,
                                                                                           com_name,
                                                                                           compath_found,
                                                                                           logging_tools.get_plural("retry", max_retries)))
                for idx in range(max_retries):
                    out_file, err_file = ("/tmp/.output_%s" % (self.__opt_dict["FULL_JOB_ID"]),
                                          "/tmp/.error_%s" % (self.__opt_dict["FULL_JOB_ID"]))
                    cs_time = time.time()
                    ret_val = os.system("%s >%s 2>%s" % (com,
                                                         out_file,
                                                         err_file))
                    ce_time = time.time()
                    out_lines = [line.rstrip() for line in open(out_file, "r").read().split("\n") if len(line.strip())]
                    err_lines = [line.rstrip() for line in open(err_file, "r").read().split("\n") if len(line.strip())]
                    out_log_name = "extcom_%d_%s" % (idx + 1,
                                                     com.replace("/", "_").replace(" ", "_").replace("__", "_").replace("__", "_"))
                    self.log("Saving output (%s) / error (%s) [return value %d] to %s.(e|o) (call took %s)" % (logging_tools.get_plural("line", len(out_lines)),
                                                                                                               logging_tools.get_plural("line", len(err_lines)),
                                                                                                               ret_val,
                                                                                                               out_log_name,
                                                                                                               logging_tools.get_diff_time_str(ce_time - cs_time)),
                             logging_tools.LOG_LEVEL_ERROR if ret_val else logging_tools.LOG_LEVEL_OK)
                    if ret_val:
                        self.log("calling %s (retry %d of %d) returned an error (took %s): %d" % (com,
                                                                                                  idx + 1,
                                                                                                  max_retries,
                                                                                                  logging_tools.get_diff_time_str(ce_time - cs_time),
                                                                                                  ret_val),
                                 logging_tools.LOG_LEVEL_ERROR,
                                 do_print=True)
                    else:
                        self.log("calling %s (retry %d of %d) successful in %s" % (com,
                                                                                   idx + 1,
                                                                                   max_retries,
                                                                                   logging_tools.get_diff_time_str(ce_time - cs_time)),
                                 do_print=True)
                    self.write_file("%s.o" % (out_log_name), out_lines)
                    self.write_file("%s.e" % (out_log_name), err_lines)
                    try:
                        os.unlink(out_file)
                        os.unlink(err_file)
                    except:
                        self.log("error removing %s and/or %s: %s" % (out_file,
                                                                      err_file,
                                                                      process_tools.get_except_info()),
                                 logging_tools.LOG_LEVEL_ERROR)
                    if ret_val:
                        # only show output if an error occured
                        if out_lines:
                            self._print("Standard output (iteration %d, %s):" % (idx + 1,
                                                                                 logging_tools.get_plural("line", len(out_lines))))
                            self._print("\n".join([" . %s" % (line) for line in out_lines]))
                        if err_lines:
                            self._print("Error output (iteration %d, %s):" % (idx + 1,
                                                                              logging_tools.get_plural("line", len(err_lines))))
                            self._print("\n".join([" * %s" % (line) for line in err_lines]))
                    if not ret_val:
                        break
            else:
                self.log("No executable for '%s' (command %s) found, searched in %s:" % (com,
                                                                                         com_name,
                                                                                         logging_tools.get_plural("path", len(path_field))),
                         logging_tools.LOG_LEVEL_ERROR,
                         do_print=True)
                for path in path_field:
                    self.log(" - %s" % (path),
                             do_print=True)
            if not ret_val:
                break
        e_time = time.time()
        self.log("call_command for %s took %s" % (com_name,
                                                  logging_tools.get_diff_time_str(e_time - s_time)))
        if ret_val:
            self._set_exit_code("error calling %s" % (", ".join(com_names)), 2)
            if args.get("hold_on_error", False):
                # hold the job
                self._send_tag("hold",
                               error=args.get("error_str", "error in call_command (%s)" % (", ".join(com_names))),
                               fail_objects=[self.__opt_dict["FULL_JOB_ID"]])
    # local kill stuff
    # network related calls (highlevel)
    def _send_tag(self, tag_name, **args):
        s_time = time.time()
        self.log("Sending tag '%s' to host %s, port %d" % (tag_name,
                                                           self.__glob_config["SGE_SERVER"],
                                                           self.__glob_config.get("SGE_SERVER_PORT", 8009)))
        opt_dict = {"host"       : self.__opt_dict["HOST_SHORT"],
                    "full_host"  : self.__opt_dict["HOST_LONG"],
                    "origin"     : "proepilogue",
                    "job_id"     : self.__opt_dict["FULL_JOB_ID"],
                    "job_num"    : self.__opt_dict["JOB_ID"],
                    "task_id"    : self.__opt_dict["TASK_ID"],
                    "queue_name" : self.__opt_dict["QUEUE"],
                    "job_name"   : self.__opt_dict["JOB_NAME"],
                    "queue_list" : [],
                    "pe_name"    : self.__opt_dict["PE"],
                    "uid"        : self.__opt_dict["UID"],
                    "gid"        : self.__opt_dict["GID"]}
        for key, value in args.iteritems():
            self.log(" - adding key %s (value %s) to opt_dict" % (key,
                                                                  str(value)))
            opt_dict[key] = value
        state, result = self._send_to_sge_server(server_command.server_command(command=tag_name,
                                                                               option_dict=opt_dict))
        e_time = time.time()
        if state:
            self.log("sent in %s, got (%d): %s" % (logging_tools.get_diff_time_str(e_time - s_time),
                                                   result.get_state(),
                                                   result.get_result()))
        else:
            self.log("some error occured (spent %s): %s" % (logging_tools.get_diff_time_str(e_time - s_time),
                                                            result),
                     logging_tools.LOG_LEVEL_ERROR)
    def _send_to_sge_server(self, act_com):
        self.__send_idx += 1
        send_idx = self.__send_idx
        self.__pending_dict[send_idx] = None
        self.__net_server.add_object(net_tools.tcp_con_object(self._new_tcp_con,
                                                              connect_state_call=self._connect_state_call,
                                                              connect_timeout_call=self._connect_timeout,
                                                              target_host=self.__glob_config["SGE_SERVER"],
                                                              target_port=self.__glob_config.get("SGE_SERVER_PORT", 8009),
                                                              timeout=10,
                                                              bind_retries=1,
                                                              rebind_wait_time=2,
                                                              add_data=(send_idx, "s", str(act_com))))
        while not self.__pending_dict[send_idx]:
            # not beautiful but working
            self.inner_loop(force_wait=True)
        ret_state, ret_value = self.__pending_dict[send_idx]
        return ret_state, ret_value
    def _kill_foreign_pids(self, con_list):
        # killall foreign ips if configured
        if self.__glob_config["BRUTAL_CLEAR_MACHINES"]:
            min_kill_uid = self.__glob_config["MIN_KILL_UID"]
            self.log("Trying to kill all processes with uid >= %d on %s" % (min_kill_uid,
                                                                            logging_tools.get_plural("node", len(con_list))))
            self._collserver_command(dict([(con_entry, ("pskill", "9 %d sge_shepherd,portmap" % (min_kill_uid))) for con_entry in con_list]),
                                     result_type="o")
    def _remove_foreign_ipcs(self, con_list):
        # killall foreign ipcs if configured
        if self.__glob_config["BRUTAL_CLEAR_MACHINES"]:
            min_kill_uid = self.__glob_config["MIN_KILL_UID"]
            self.log("Trying to remove all IPCS-objects with uid >= %d on %s" % (min_kill_uid,
                                                                                 logging_tools.get_plural("node", len(con_list))))
            self._collserver_command(dict([(con_entry, ("ipckill", "%d" % (min_kill_uid))) for con_entry in con_list]),
                                     result_type="o")
    def _decode_umount_result(self, res_dict, **args):
        ok_list, err_list = (res_dict.get("ok_list", []),
                             res_dict.get("err_list", []))
        return "umount result: %d OK%s, %s%s" % (len(ok_list),
                                                 " (%s)" % (", ".join([x[0] for x in ok_list])) if ok_list else "",
                                                 logging_tools.get_plural("problem", len(err_list)),
                                                 " (%s)" % (", ".join([x[0] for x in err_list])) if err_list else "")
    def _umount_nfs_mounts(self, con_list):
        # umounts unneeded mountpoints
        self.log("Trying to umount all unneded NFS-mounts on %s" % (logging_tools.get_plural("node", len(con_list))))
        self._collserver_command(dict([(con_entry, ("umount", "")) for con_entry in con_list]), decode_func=self._decode_umount_result)
    def _check_homedir(self, con_list):
        user_name = self.__env_dict["USER"]
        self.log("Checking reachability of homedir for user %s on %s" % (user_name,
                                                                         logging_tools.get_plural("node", len(con_list))))
        res_dict = self._collserver_command(dict([(con_entry, ("homedir", user_name)) for con_entry in con_list]), result_type="o")
        error_nodes = []
        for key, (res_ok, res_value) in res_dict.iteritems():
            if res_ok:
                if res_value.startswith("ok "):
                    pass
                else:
                    error_nodes.append(key)
            else:
                if type(res_value) == type(()) and res_value[1].lower().count("timeout"):
                    # not really ok ...
                    pass
                else:
                    error_nodes.append(key)
        if error_nodes:
            self.log("no userhome on %s: %s" % (logging_tools.get_plural("node", len(error_nodes)),
                                                logging_tools.compress_list(error_nodes)),
                     logging_tools.LOG_LEVEL_ERROR,
                     do_print=True)
            self._send_tag("disable",
                           error="no homedir",
                           fail_objects=["%s@%s" % (self.__opt_dict["QUEUE"], failed_host) for failed_host in error_nodes])
            self._set_exit_code("homedir reachability", 99)
    def _flight_check(self, flight_type):
        s_time = time.time()
        ping_com = "ping_remote fast_mode=True"
        self.log("starting flight_check %s, ping_com is '%s'" % (flight_type,
                                                                 ping_com))
        
        all_ips = sum([node_stuff["ip_list"] for node_stuff in self.__node_dict.itervalues()], [])
        all_nfs_ips = [node_stuff["ip"] for node_stuff in self.__node_dict.itervalues()]
        # build connection dict
        con_dict = {}
        for node_name in self.__node_list:
            con_dict[node_name] = {"result"  : None,
                                   "retries" : 2,
                                   "ips"     : all_ips}
        self.log(" - %s %s: %s to check" % (logging_tools.get_plural("node", len(self.__node_list)),
                                            logging_tools.compress_list(self.__node_list),
                                            logging_tools.get_plural("IP", len(all_ips))))
        max_pending = self.__glob_config["SIMULTANEOUS_PINGS"]
        ping_packets = self.__glob_config["PING_PACKETS"]
        ping_timeout = self.__glob_config["PING_TIMEOUT"]
        pings_pending = 0
        pending_ids, pending_dict, nodes_waiting = ([], {}, [])
        while True:
            # iterate until all results are set
            # step 1 : send as many pings as needed
            to_send = [key for key, value in con_dict.iteritems() if (value["result"] is None) and (key not in nodes_waiting)]
            send_dict = {}
            while to_send and pings_pending < max_pending:
                #print "sending", to_send, pings_pending, max_pending
                act_node_name = to_send.pop(0)
                send_dict[act_node_name] = (ping_com, "%s %d %.2f" % (",".join(con_dict[act_node_name]["ips"]),
                                                                      ping_packets,
                                                                      ping_timeout))
                pings_pending += ping_packets
            if send_dict:
                act_pend_dict = self._collserver_command(send_dict, 
                                                         only_send=True,
                                                         timeout=ping_timeout + 5)
                nodes_waiting.extend(act_pend_dict.values())
                pending_ids.extend(act_pend_dict.keys())
                for key, value in act_pend_dict.iteritems():
                    # store reference
                    pending_dict[key] = value
            # step 2: wait for pings to return
            self.inner_loop(force_wait=True)
            act_finished = [p_id for p_id in pending_ids if self.__pending_dict[p_id]]
            #print "done", act_finished
            for fin_id in act_finished:
                pending_ids.remove(fin_id)
                pings_pending -= ping_packets
                ret_state, ret_value = self.__pending_dict[fin_id]
                #print "id %d gave:" % (fin_id), ret_state, ret_value
                act_node_name = pending_dict[fin_id]
                nodes_waiting.remove(act_node_name)
                #self.log("got for %s: %s" % (act_node_name, str(self.__pending_dict[fin_id])))
                con_dict[act_node_name]["retries"] -= 1
                con_dict[act_node_name]["result"] = (ret_state, ret_value)
                if not ret_state and con_dict[act_node_name]["retries"]:
                    # we only retry the ping if the connection to the collserver fails
                    con_dict[act_node_name]["result"] = None
            if not [True for key, value in con_dict.iteritems() if not value["result"]]:
                break
        # interpret result
        res_dict = dict([(key, dict([(ip, False) for ip in [self.__node_dict[key]["ip"]] + value["ips"]])) for key, value in con_dict.iteritems()])
        ip_fail_dict, reach_dict = ({}, {})
        for key, value in con_dict.iteritems():
            res_ok, res_stuff = value["result"]
            if res_ok:
                # node itself is ok
                res_dict[key][self.__node_dict[key]["ip"]] = True
                for sub_key, sub_res in res_stuff.iteritems():
                    reach_dict.setdefault(sub_key, {"total"  : 0,
                                                    "actual" : 0,
                                                    "state"  : "ok"})
                    reach_dict[sub_key]["total"] += 1
                    if type(sub_res) == type({}) and sub_res["received"]:
                        res_dict[key][sub_key] = True
                        reach_dict[sub_key]["actual"] += 1
                    else:
                        local_ip = sub_key in self.__node_dict[key]["ip_list"]
                        self.log("unable to contact %s IP %s from node %s%s" % ("local" if local_ip else "remote",
                                                                                sub_key,
                                                                                key,
                                                                                " (result is '%s')" % (sub_res) if type(sub_res) == type("") else ""),
                                    logging_tools.LOG_LEVEL_ERROR)
                        ip_fail_dict.setdefault(sub_key, []).append((key, local_ip))
            else:
                self.log("unable to contact node %s: %s" % (key,
                                                            res_stuff),
                         logging_tools.LOG_LEVEL_ERROR)
        # remove ip_failures 
        #pprint.pprint(res_dict)
        #pprint.pprint(con_dict)
        #pprint.pprint(ip_fail_dict)
        #pprint.pprint(reach_dict)
        # failed ips
        failed_ips = sorted([key for key, value in reach_dict.iteritems() if value["actual"] != value["total"]])
        error_hosts = set()
        if failed_ips:
            for fail_ip in failed_ips:
                ip_dict = reach_dict[fail_ip]
                ip_dict["status"] = "warn" if ip_dict["actual"] else "fail"
            self.log("%s failed: %s" % (logging_tools.get_plural("IP", len(failed_ips)),
                                        ", ".join(["%s (%s)" % (fail_ip, reach_dict[fail_ip]["status"]) for fail_ip in failed_ips])),
                     logging_tools.LOG_LEVEL_WARN)
            error_ips = set([fail_ip for fail_ip in failed_ips if reach_dict[fail_ip]["status"] == "fail"])
            if error_ips:
                error_hosts = set([key for key, value in self.__node_dict.iteritems() if error_ips.intersection(set(value["ip_list"]))])
                self.log("%s: %s (%s: %s)" % (logging_tools.get_plural("error host", len(error_hosts)),
                                              ", ".join(error_hosts),
                                              logging_tools.get_plural("error IP", len(error_ips)),
                                              ", ".join(error_ips)),
                         logging_tools.LOG_LEVEL_ERROR,
                         do_print=True)
                # disable the queues
                self._send_tag("disable",
                               error="connection problem",
                               fail_objects=["%s@%s" % (self.__opt_dict["QUEUE"], failed_host) for failed_host in error_hosts])
                # hold the job
                self._send_tag("hold",
                               error="connection problem",
                               fail_objects=[self.__opt_dict["FULL_JOB_ID"]])
                self._set_exit_code("connection problems", 1)
        e_time = time.time()
        self.log("%s took %s" % (flight_type, logging_tools.get_diff_time_str(e_time - s_time)))
    def _collserver_command(self, con_dict, **args):
        # args:
        # result_type is on of 's' for srv_reply, 'p' for packaged struct or anything else for no interpretation
        # only_send: just send and return immediately with the dict of sender_ids -> target_host
        # timeout: timeout for command
        con_list = con_dict.keys()
        res_type = args.get("result_type", "p")
        self.log("sending command to %s (result type %s): %s" % (logging_tools.get_plural("host", len(con_list)),
                                                                 res_type,
                                                                 logging_tools.compress_list(con_list)))
        disp_list = {}
        for key, value in con_dict.iteritems():
            disp_list.setdefault(value, []).append(key)
        for val in sorted(disp_list.keys()):
            self.log(" - %s to %s: %s" % (str(val),
                                          logging_tools.get_plural("node", len(disp_list[val])),
                                          logging_tools.compress_list(disp_list[val])))
        s_time = time.time()
        pend_list, ip_dict = ([], {})
        for con_ip in con_list:
            self.__send_idx += 1
            send_idx = self.__send_idx
            pend_list.append(send_idx)
            ip_dict[send_idx] = con_ip
            self.__pending_dict[send_idx] = None
            self.__net_server.add_object(net_tools.tcp_con_object(self._new_tcp_con,
                                                                  connect_state_call=self._connect_state_call,
                                                                  connect_timeout_call=self._connect_timeout,
                                                                  target_host=con_ip,
                                                                  target_port=self.__glob_config.get("COLLSERVER_PORT", 2001),
                                                                  timeout=args.get("timeout", 10),
                                                                  bind_retries=1,
                                                                  rebind_wait_time=2,
                                                                  add_data=(send_idx, res_type, "%s %s" % con_dict[con_ip])))
        if args.get("only_send", False):
            return ip_dict
        while True:
            # not beautiful but working
            self.inner_loop(force_wait=True)
            if not [True for p_id in pend_list if not self.__pending_dict[p_id]]:
                break
        # transform results
        for key in pend_list:
            if self.__pending_dict[key][0] == True and args.has_key("decode_func"):
                self.__pending_dict[key] = (True, args["decode_func"](self.__pending_dict[key][1], host=ip_dict[key]))
        ret_dict = dict([(ip_dict[s_idx], self.__pending_dict[s_idx]) for s_idx in pend_list])
        e_time = time.time()
        self.log(" - contacted %s in %s" % (logging_tools.get_plural("address", len(con_list)),
                                            logging_tools.get_diff_time_str(e_time - s_time)))
        # log results
        results = dict([(key, {}) for key in ["ok", "error"]])
        for key, (ok_flag, result) in ret_dict.iteritems():
            if ok_flag:
                if type(result) == type(""):
                    results["ok"].setdefault(result, []).append(key)
                else:
                    results["ok"].setdefault(str(type(result)), []).append(key)
            else:
                results["error"].setdefault(result, []).append(key)
        for res_key in sorted(results.keys()):
            res_struct = results[res_key]
            if res_struct:
                self.log(" - got %s:" % (logging_tools.get_plural("different %s result" % (res_key), len(res_struct.keys()))),
                         logging_tools.LOG_LEVEL_OK if res_key in ["ok"] else logging_tools.LOG_LEVEL_ERROR)
                for sub_res_key in sorted(res_struct.keys()):
                    self.log("   - %s: %s" % (sub_res_key, logging_tools.compress_list(res_struct[sub_res_key])),
                             logging_tools.LOG_LEVEL_OK if res_key in ["ok"] else logging_tools.LOG_LEVEL_ERROR)
        return ret_dict
    # network related calls (lowlevel)
    def _connect_timeout(self, sock):
        # to escape from waiting loop
        self.get_thread_queue().put(("result_error", (sock.get_add_data()[0], -1, "connect timeout")))
        sock.close()
    def _connect_state_call(self, **args):
        if args["state"] == "error":
            send_id, send_type, send_str = args["socket"].get_add_data()
            # to escape from waiting loop
            self.get_thread_queue().put(("result_error", (send_id, -1, "connect timeout")))
    def _new_tcp_con(self, sock):
        return None
        #return simple_tcp_obj(self.get_thread_queue(), sock.get_add_data())
    def _result_ok(self, (s_id, s_type, res_str)):
        if s_type == "s":
            # srv_command
            try:
                srv_reply = server_command.server_reply(res_str)
            except:
                self.__pending_dict[s_id] = (False, (-1, "error decoding '%s': %s" % (res_str,
                                                                                      process_tools.get_except_info())))
            else:
                self.__pending_dict[s_id] = (True, srv_reply)
        elif s_type == "p":
            # packed struct
            if res_str.startswith("ok "):
                try:
                    res_struct = server_command.net_to_sys(res_str[3:])
                except:
                    self.__pending_dict[s_id] = (False, (-1, "error unpacking '%s': %s" % (res_str,
                                                                                           process_tools.get_except_info())))
                else:
                    self.__pending_dict[s_id] = (True, res_struct)
            else:
                self.__pending_dict[s_id] = (False, (-1, res_str))
        else:
            self.__pending_dict[s_id] = (True, res_str)
    def _result_error(self, (s_id, e_flag, e_cause)):
        self.log("problem for send_id %d: %s (%d)" % (s_id,
                                                      e_cause,
                                                      e_flag),
                 logging_tools.LOG_LEVEL_ERROR)
        self.__pending_dict[s_id] = (False, (e_flag, e_cause))
    # calls to determine the actual runmode
    # headers / footers
        
class my_thread_pool(threading_tools.thread_pool):
    def __init__(self, opt_dict):
        self.__opt_dict = opt_dict
        # init gonfig
        self.__glob_config = configfile.configuration("proepilogue", {
            "LOG_NAME"              : configfile.str_c_var("proepilogue"),
            "LOG_DESTINATION"       : configfile.str_c_var("uds:/var/lib/logging-server/py_log"),
            "MAX_RUN_TIME"          : configfile.int_c_var(60),
            "SEP_LEN"               : configfile.int_c_var(80),
            "HAS_MPI_INTERFACE"     : configfile.bool_c_var(True),
            "MPI_POSTFIX"           : configfile.str_c_var("mp"),
            "BRUTAL_CLEAR_MACHINES" : configfile.bool_c_var(False),
            "SIMULTANEOUS_PINGS"    : configfile.int_c_var(128),
            "PING_PACKETS"          : configfile.int_c_var(5),
            "PING_TIMEOUT"          : configfile.float_c_var(5.0),
            "MIN_KILL_UID"          : configfile.int_c_var(110),
            "UMOUNT_CALL"           : configfile.bool_c_var(True)})
        self._init_log_template()
        threading_tools.thread_pool.__init__(self, "proepilogue", blocking_loop=False)
        self.register_exception("int_error", self._int_error)
        self.register_exception("term_error", self._int_error)
        self.register_func("set_exit_code", self._set_exit_code)
        self.register_func("log", self.log)
        self.register_func("done", self._done)
        self._set_sge_environment()
        self._read_config()
        self._log_arguments()
        self.exit_code = -1
        self.__runtime_exceeded = False
        self.__start_time = time.time()
        self._init_netserver()
        self.__job_thread = self.add_thread(job_thread(self.__glob_config, self.__opt_dict, self.__netserver), start_thread=True).get_thread_queue()
##    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK, **args):
##        if type(what) == type(()):
##            what, log_level = what
##        if self.__logger:
##            self.__logger.log(log_level, what)
##        else:
##            self.__log_template.log(what, log_level)
##        if args.get("do_print", False):
##            self._print("%s%s" % ("[%s] " % (logging_tools.get_log_level_str(log_level)) if log_level != logging_tools.LOG_LEVEL_OK else "", what))
##    def _print(self, what):
##        try:
##            print what
##        except:
##            self.log("cannot print '%s': %s" % (what,
##                                                process_tools.get_except_info()),
##                     logging_tools.LOG_LEVEL_ERROR)
##    
##    def set_exit_code(self, exit_code):
##        self.__exit_code = exit_code
##        self.log("exit_code set to %d" % (self.__exit_code))
##    def get_exit_code(self):
##        return self.__exit_code
##    exit_code = property(get_exit_code, set_exit_code)
##    def _set_exit_code(self, ex_code):
##        self.exit_code = ex_code
##    def _init_netserver(self):
##        self.__netserver = net_tools.network_server(timeout=4, log_hook=self.log)
##    def _read_config(self):
##        # reading the config
##        conf_dir = "%s/3rd_party" % (self.__glob_config["SGE_ROOT"])
##        if not os.path.isdir(conf_dir):
##            self.log("no config_dir %s found, using defaults" % (conf_dir),
##                     logging_tools.LOG_LEVEL_ERROR,
##                     do_print=True)
##        else:
##            conf_file = "%s/proepilogue.conf" % (conf_dir)
##            if not os.path.isfile(conf_file):
##                self.log("no config_file %s found, using defaults" % (conf_file),
##                         logging_tools.LOG_LEVEL_ERROR,
##                         do_print=True)
##                self._print("Copy the following lines to %s :" % (conf_file))
##                self._print("")
##                self._print("[global]")
##                for key in sorted(self.__glob_config.keys()):
##                    if not key.startswith("SGE_"):
##                        # don't write SGE_* stuff
##                        self._print("%s = %s" % (key, str(self.__glob_config[key])))
##                self._print("")
##            else:
##                self.__glob_config.add_config_dict({"CONFIG_FILE" : configfile.str_c_var(conf_file)})
##                self.log("reading config from %s" % (conf_file))
##                self.__glob_config.parse_file(conf_file)
##    def _set_sge_environment(self):
##        for v_name, v_src in [("SGE_ROOT", "/etc/sge_root"), ("SGE_CELL", "/etc/sge_cell")]:
##            if os.path.isfile(v_src):
##                v_val = file(v_src, "r").read().strip()
##                self.log("Setting environment-variable '%s' to %s" % (v_name, v_val))
##            else:
##                self.log("Cannot assign environment-variable '%s', problems *ahead ..." % (v_name),
##                         logging_tools.LOG_LEVEL_ERROR)
##                #sys.exit(1)
##            self.__glob_config.add_config_dict({v_name : configfile.str_c_var(v_val, source=v_src)})
##        if self.__glob_config.has_key("SGE_ROOT") and self.__glob_config.has_key("SGE_CELL"):
##            self.__glob_config.add_config_dict({"SGE_VERSION" : configfile.str_c_var("6", source="intern")})
    def _log_arguments(self):
        out_list = logging_tools.new_form_list()
        for key in sorted(self.__opt_dict.keys()):
            out_list.append([logging_tools.form_entry(key, header="key"),
                             logging_tools.form_entry(self.__opt_dict[key], header="value")])
        for line in str(out_list).split("\n"):
            self.log(line)
##    def _init_log_template(self):
##        logger, log_template = (None, None)
##        try:
##            logger = logging_tools.get_logger(self.__glob_config["LOG_NAME"],
##                                              self.__glob_config["LOG_DESINATION"],
##                                              init_logger=True)
##        except:
##            log_template = net_logging_tools.log_command(self.__glob_config["LOG_NAME"], thread_safe=True, thread="proepilogue")
##            log_template.set_destination(self.__glob_config["LOG_DESTINATION"])
##            log_template.set_command_and_send("open_log")
##            log_template.set_command("log")
##        self.__log_template = log_template
##        self.__logger = logger
##    def _close_logs(self):
##        if self.__log_template:
##            self.__log_template.set_command_and_send("close_log")
##        else:
##            self.__logger.log_command("CLOSE")
    def _int_error(self, err_cause):
        self.log("_int_error() called, cause %s" % (str(err_cause)), logging_tools.LOG_LEVEL_WARN)
        if self["exit_requested"]:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            self["exit_requested"] = True
            self.__netserver.set_timeout(0.1)
            self._break_netserver()
    def _done(self, ret_value):
        self.exit_code = ret_value
        self._int_error("done")
##    def _break_netserver(self):
##        if self.__netserver:
##            self.log("Sending break to netserver")
##            self.__netserver.break_call()
    def loop_function(self):
        act_time = time.time()
        run_time = abs(act_time - self.__start_time)
        if run_time > 2 * self.__glob_config["MAX_RUN_TIME"]:
            self.log("terminating myself",
                     logging_tools.LOG_LEVEL_CRITICAL)
            os.kill(self.pid, 9)
        elif run_time > self.__glob_config["MAX_RUN_TIME"]:
            if not self.__runtime_exceeded:
                self.__runtime_exceeded = True
                self.log("max runtime of %s exceeded, exiting" % (logging_tools.get_diff_time_str(self.__glob_config["MAX_RUN_TIME"])),
                        logging_tools.LOG_LEVEL_ERROR)
                self.stop_thread("job")
                self.exit_code = 2
                self._int_error("runtime")
        self.__netserver.step()
##    def thread_loop_post(self):
##        del self.__netserver
##        self.log("execution time: %s" % (logging_tools.get_diff_time_str(time.time() - self.__start_time)))
##        self._close_logs()
##        #process_tools.delete_pid("collserver/collserver")
##        #if self.__msi_block:
##        #    self.__msi_block.remove_meta_block()
    
##class my_opt_parser(optparse.OptionParser):
##    def __init__(self):
##        optparse.OptionParser.__init__(self)
##        self.__error = False
##    def parse(self):
##        options, args = self.parse_args()
##        if len(args) not in [5, 8]:
##            print "Unable to determine execution mode, exiting (%s: %s)" % (logging_tools.get_plural("argument", len(sys.argv)),
##                                                                            ", ".join(args))
##            self.__error = True
##        if self.__error:
##            return None
##        else:
##            opt_dict = self._set_options(options, args)
##            return opt_dict
##    def _set_options(self, options, args):
##        opt_dict = {"CALLER_NAME"       : os.path.basename(sys.argv[0]),
##                    "CALLER_NAME_SHORT" : os.path.basename(sys.argv[0]).split(".")[0]}
##        if len(args) == 5:
##            opt_dict["PROLOGUE"] = True
##            # copy pro/epilogue options
##            opt_dict["HOST_LONG"] = args.pop(0)
##            opt_dict["HOST_SHORT"] = opt_dict["HOST_LONG"].split(".")[0]
##            opt_dict["JOB_OWNER"] = args.pop(0)
##            opt_dict["JOB_ID"] = args.pop(0)
##            opt_dict["JOB_NAME"] = args.pop(0)
##            opt_dict["QUEUE"] = args.pop(0)
##        elif len(args) == 8:
##            opt_dict["PROLOGUE"] = False
##            # copy pestart/stop options
##            opt_dict["HOST_LONG"] = args.pop(0)
##            opt_dict["HOST_SHORT"] = opt_dict["HOST_LONG"].split(".")[0]
##            opt_dict["JOB_OWNER"] = args.pop(0)
##            opt_dict["JOB_ID"] = args.pop(0)
##            opt_dict["JOB_NAME"] = args.pop(0)
##            opt_dict["QUEUE"] = args.pop(0)
##            opt_dict["PE_HOSTFILE"] = args.pop(0)
##            opt_dict["PE"] = args.pop(0)
##            opt_dict["PE_SLOTS"] = args.pop(0)
##        return opt_dict
##    def error(self, what):
##        print "Error parsing arguments: %s" % (what)
##        self.__error = True

class client(object):
    """ client to connect to, needed for 0MQ-related stuff """
    def __init__(self, addr, port):
        self.addr = addr
        self.port = port
        self.target_str = "tcp://%s:%d" % (self.addr, self.port)
        self.log("add to dict")
        client.c_dict[self.target_str] = self
        client.c_dict[self.addr] = self
        client.target_dict[self.target_str] = self
        self.zmq_id = None
        self.send_list = []
        self.recv_list = []
        self.connected = False
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        client.log_com("[%s] %s" % (self.target_str, what), log_level)
    @staticmethod
    def setup(log_com, zmq_context):
        client.c_dict = {}
        client.target_dict = {}
        client.log_com = log_com
        client.zmq_context = zmq_context
        client.dsc_id = "sgepe_discovery_%s:%d" % (process_tools.get_machine_name(),
                                                   os.getpid())
        client.router_id = "sgepe_router_%s:%d" % (process_tools.get_machine_name(),
                                                   os.getpid())
        client.socket = zmq_context.socket(zmq.ROUTER)
        client.socket.setsockopt(zmq.IDENTITY, client.router_id)
        client.socket.setsockopt(zmq.LINGER, 0)
        client.socket.setsockopt(zmq.SNDHWM, 100)
        client.socket.setsockopt(zmq.RCVHWM, 100)
        client.socket.setsockopt(zmq.BACKLOG, 100)
        client.socket.setsockopt(zmq.TCP_KEEPALIVE, 1)
        client.socket.setsockopt(zmq.TCP_KEEPALIVE_IDLE, 300)
        log_com("init client struct (%s, %s)" % (client.dsc_id,
                                                 client.router_id))
    @staticmethod
    def close():
        client.socket.close()
    @staticmethod
    def get_client(key):
        return client.c_dict[key]
    @staticmethod
    def discover_0mq(**kwargs):
        t_sock = client.zmq_context.socket(zmq.PUSH)
        r_sock = client.zmq_context.socket(zmq.SUB)
        r_sock.setsockopt(zmq.SUBSCRIBE, client.dsc_id)
        #t_sock.setsockopt(zmq.IDENTITY, client.dsc_id)
        t_sock.connect(process_tools.get_zmq_ipc_name("command", s_name="collserver"))
        r_sock.connect(process_tools.get_zmq_ipc_name("result", s_name="collserver"))
        srv_com = server_command.srv_command(command="load", identity=client.dsc_id)
        t_sock.send_unicode(unicode(srv_com))
        # tight inner loop to let the dust settle
        if not r_sock.poll(10):
            t_sock.send_unicode(unicode(srv_com))
        t_sock.close()
        data = [r_sock.recv()]
        while r_sock.getsockopt(zmq.RCVMORE):
            data.append(r_sock.recv_unicode())
        print data
        r_sock.close()
        return
        timeout = kwargs.get("timeout", 2)
        local_poller = zmq.Poller()
        dsc_lut = {}
        for t_addr, c_struct in client.target_dict.iteritems():
            dsc_socket = client.zmq_context.socket(zmq.DEALER)
            dsc_socket.setsockopt(zmq.IDENTITY, client.dsc_id)
            dsc_socket.setsockopt(zmq.LINGER, 100)
            dsc_socket.connect(t_addr)
            dsc_socket.send_unicode(unicode(server_command.srv_command(command="get_0mq_id", target_ip=c_struct.addr)))
            local_poller.register(dsc_socket, zmq.POLLIN)
            c_struct.dsc_socket = dsc_socket
            dsc_lut[dsc_socket] = c_struct
        s_time = time.time()
        while time.time() < abs(s_time + timeout):
            for cur_sock, cur_type in local_poller.poll(1000):
                if cur_type == zmq.POLLIN:
                    #print cur_sock, cur_type, dsc_lut, zmq.POLLIN, zmq.POLLOUT, zmq.POLLERR
                    c_struct = dsc_lut[cur_sock]
                    zmq_id = server_command.srv_command(source=cur_sock.recv_unicode())["zmq_id"].text
                    c_struct.zmq_id = zmq_id
                    c_struct.log("0MQ id is %s" % (c_struct.zmq_id))
                    client.c_dict[zmq_id] = c_struct
                    if kwargs.get("connect", True):
                        client.socket.connect(c_struct.target_str)
                        c_struct.connected = True
            if all([c_struct.zmq_id != None for c_struct in client.target_dict.itervalues()]):
                break
        client.log_com("discovery took %s, %s tried, %s" % (
            logging_tools.get_diff_time_str(abs(time.time() - s_time)),
            logging_tools.get_plural("host", len(client.target_dict)),
            logging_tools.get_plural("error", len(dsc_lut))),
                   logging_tools.LOG_LEVEL_OK if not dsc_lut else logging_tools.LOG_LEVEL_ERROR)
        dsc_lut = None
        for c_struct in client.target_dict.itervalues():
            c_struct.dsc_socket.close()
            c_struct.dsc_socket = None
        # some time to let things settle, receive
        time.sleep(0.001)
    def send(self, srv_com):
        client.socket.send_unicode(self.zmq_id, zmq.SNDMORE)
        client.socket.send_unicode(unicode(srv_com))
        self.send_list.append(time.time())
    def recv(self, srv_com):
        self.send_list.pop(0)
        self.result = srv_com
    @staticmethod
    def send_srv_command(srv_com, **kwargs):
        return {}
        local_poller = zmq.Poller()
        local_poller.register(client.socket, zmq.POLLIN)
        timeout = kwargs.get("timeout", 5)
        num_resend = kwargs.get("resend", 1)
        send_list = set()
        pending = 0
        for t_addr, c_struct in client.target_dict.iteritems():
            if c_struct.connected:
                c_struct.send(srv_com)
                pending += 1
                c_struct.resend_counter = num_resend
                send_list.add(t_addr)
        while pending:
            poll_result = local_poller.poll(timeout=1000 * timeout / 10)
            if poll_result:
                data = [client.socket.recv_unicode()]
                while client.socket.getsockopt(zmq.RCVMORE):
                    data.append(client.socket.recv_unicode())
                c_struct = client.c_dict[data.pop(0)]
                c_struct.recv(server_command.srv_command(source=data[0]))
                pending -= 1
            else:
                cur_time = time.time()
                to_structs = [value for value in client.target_dict.itervalues() if value.send_list and abs(value.send_list[0] - cur_time) > timeout]
                for t_struct in to_structs:
                    t_struct.send_list.pop(0)
                    if t_struct.resend_counter:
                        t_struct.resend_counter -= 1
                        t_struct.log("timeout triggered, resending", logging_tools.LOG_LEVEL_WARN)
                        t_struct.send(srv_com)
                    else:
                        t_struct.result = None
                        t_struct.log("timeout triggered", logging_tools.LOG_LEVEL_ERROR)
                        pending -= 1
        return dict([(key, client.target_dict[key].result) for key in send_list])
        
class job_object(object):
    def __init__(self, p_pool):
        self.p_pool = p_pool
        self.__log_dir = time.strftime("%Y/%m/%d/%%s%%s") % (
            global_config["JOB_ID"],
            ".%s" % (os.environ["SGE_TASK_ID"]) if os.environ.get("SGE_TASK_ID", "undefined") != "undefined" else "")
        self.__log_name = "%s" % (self.__log_dir)
        self.__log_template = logging_tools.get_logger(
            "%s.%s/log" % (global_config["LOG_NAME"],
                           self.__log_name.replace(".", "\.")),
            global_config["LOG_DESTINATION"],
            zmq=True,
            context=self.p_pool.zmq_context)
        self._init_exit_code()
    def _init_exit_code(self):
        self.p_pool["return_value"] = 0
    def _set_exit_code(self, cause, exit_code):
        self.p_pool["return_value"] = exit_code
        self.log("setting exit_code to %d because of %s" % (exit_code,
                                                            cause),
                 logging_tools.LOG_LEVEL_ERROR)
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK, **kwargs):
        self.__log_template.log(lev, what)
        if kwargs.get("do_print", False):
            self._print("%s%s" % ("[%s] " % (logging_tools.get_log_level_str(lev)) if lev != logging_tools.LOG_LEVEL_OK else "", what))
        if lev != logging_tools.LOG_LEVEL_OK or kwargs.get("pool", False):
            self.p_pool.log(what, lev)
    def _print(self, what):
        try:
            print what
        except:
            self.log("cannot print '%s': %s" % (what,
                                                process_tools.get_except_info()),
                     logging_tools.LOG_LEVEL_ERROR)
    # wrapper script tools
    def _get_wrapper_script_name(self):
        return  "%s/%s.new" % (os.path.dirname(self.__env_dict["JOB_SCRIPT"]),
                               global_config["FULL_JOB_ID"])
    def _get_var_script_name(self):
        return  "%s/%s.var" % (os.path.dirname(self.__env_dict["JOB_SCRIPT"]),
                               global_config["FULL_JOB_ID"])
    def _create_wrapper_script(self):
        # only sensible if sge_starter_method for queue is set
        src_file = self.__env_dict["JOB_SCRIPT"]
        dst_file = self._get_wrapper_script_name()
        var_file = self._get_var_script_name()
        if not dst_file.startswith("/"):
            self.log("refuse to create wrapper script %s" % (dst_file),
                     logging_tools.LOG_LEVEL_ERROR)
            return
        self.log("Creating wrapper-script (%s for %s)" % (dst_file,
                                                          src_file))
        shell_path, shell_start_mode = (self.__env_int_dict.get("shell_path", "/bin/bash"),
                                        self.__env_int_dict.get("shell_start_mode", "posix_compliant"))
        cluster_queue_name = global_config["JOB_QUEUE"]
        self.log("shell_path is '%s', shell_start_mode is '%s'" % (shell_path,
                                                                   shell_start_mode))
        #cpuset_dir_name = "%s/cpuset" % (g_config["SGE_ROOT"])
        do_cpuset = False
        no_cpuset_cause = []
        if no_cpuset_cause:
            self.log("not using cpuset because: %s" % (", ".join(no_cpuset_cause)))
        if shell_start_mode == "posix_compliant" and shell_path:
            df_lines = ["#!%s" % ("/bin/sh"),
                        "echo 'wrapper_script, no cpu_set'",
                        "export BASH_ENV=$HOME/.bashrc",
                        ". %s" % (var_file),
                        "exec %s %s $*" % (shell_path, src_file),
                        ""]
        else:
            df_lines = ["#!%s" % ("/bin/sh"),
                        "echo 'wrapper_script, no cpu_set'",
                        "export BASH_ENV=$HOME/.bashrc",
                        ". %s" % (var_file),
                        "exec %s $*" % (src_file),
                        ""]
        file(dst_file, "w").write("\n".join(df_lines))
        file(var_file, "w").write("#!/bin/bash\n")
        self.write_file("wrapper_script", df_lines)
        os.chmod(dst_file, 0755)
        os.chmod(var_file, 0755)
        os.chown(var_file, global_config["UID"], global_config["GID"])
    def _delete_wrapper_script(self):
        env_keys = sorted(self.__env_int_dict.keys())
        src_file = self.__env_dict["JOB_SCRIPT"]
        dst_file = self._get_wrapper_script_name()
        if not dst_file.startswith("/"):
            self.log("refuse to delete wrapper script %s" % (dst_file),
                     logging_tools.LOG_LEVEL_ERROR)
            return
        self.log("Deleting wrapper-script (%s for %s)" % (dst_file,
                                                          src_file))
        if os.path.isfile(dst_file):
            try:
                os.unlink(dst_file)
            except:
                self.log("error deleting %s: %s" % (dst_file,
                                                    process_tools.get_except_info()),
                         logging_tools.LOG_LEVEL_ERROR)
            else:
                self.log("deleted %s" % (dst_file))
        else:
            self.log("no such file: %s" % (dst_file),
                     logging_tools.LOG_LEVEL_ERROR)
    def _add_script_var(self, key, value):
        var_file = self._get_var_script_name()
        self.log("adding variable (%s=%s) to var_file %s" % (key,
                                                             value,
                                                             var_file))
        try:
            file(var_file, "a").write("export %s=%s\n" % (key, value))
        except:
            self.log("error writing to %s: %s" % (var_file,
                                                  process_tools.get_except_info()),
                     logging_tools.LOG_LEVEL_ERROR)
    def is_start_call(self):
        return global_config["CALLER_NAME"] in ["prologue",
                                                "lamstart",
                                                "mvapich2start",
                                                "pvmstart",
                                                "pestart"]
    def is_pe_start_call(self):
        return global_config["CALLER_NAME"] in ["lamstart",
                                                "pestart",
                                                "pvmstart",
                                                "mvapich2start"]
    def is_pe_stop_call(self):
        return global_config["CALLER_NAME"] in ["lamstop",
                                                "pestop",
                                                "pvmstop",
                                                "mvapich2stop"]
    def is_proepilogue_call(self):
        return global_config["CALLER_NAME"] in ["prologue",
                                                      "epilogue"]
    def is_pe_call(self):
        return global_config["CALLER_NAME"] in ["lamstart",
                                                "pestart",
                                                "pvmstart",
                                                "mvapich2start",
                                                "lamstop",
                                                "pestop",
                                                "pvmstop",
                                                "mvapich2stop"]
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
    def write_file(self, name, content, **args):
        ss_time = time.time()
        logger = logging_tools.get_logger("%s.%s/%s" % (global_config["LOG_NAME"],
                                                        self.__log_dir.replace(".", "\."),
                                                        name),
                                          global_config["LOG_DESTINATION"],
                                          zmq=True,
                                          context=self.p_pool.zmq_context)
        if type(content) == type("") and content.startswith("/"):
            # content is a filename
            content = file(content, "r").read().split("\n")
        if type(content) == type(""):
            content = content.split("\n")
        log_str = "content '%s', %s:" % (name,
                                         logging_tools.get_plural("line", len(content)))
        logger.log(logging_tools.LOG_LEVEL_OK, log_str)
        if args.get("linenumbers", True):
            for line_num, line in zip(xrange(len(content)), content):
                log_str = "%3d %s" % (line_num + 1, line)
                logger.log(logging_tools.LOG_LEVEL_OK, log_str)
        else:
            for line in content:
                logger.log(logging_tools.LOG_LEVEL_OK, line)
        se_time = time.time()
        self.log("storing content to file %s (%s) in %s" % (name,
                                                            logging_tools.get_plural("line", len(content)),
                                                            logging_tools.get_diff_time_str(se_time - ss_time)))
        logger.close()
    def _copy_environments(self):
        self.__env_dict = dict([(key, str(os.environ[key])) for key in os.environ.keys()])
        if "SGE_JOB_SPOOL_DIR" in self.__env_dict:
            self.__env_int_dict = dict([(key, value) for key, value in [line.split("=", 1) for line in file("%s/config" % (self.__env_dict["SGE_JOB_SPOOL_DIR"]), "r").read().strip().split("\n") if line.count("=")]])
        else:
            self.__env_int_dict = {}
    def _parse_server_addresses(self):
        for src_file, key, default in [("/etc/motherserver", "MOTHER_SERVER", "localhost"),
                                       ("/etc/sge_server"  , "SGE_SERVER"   , "localhost")]:
            if os.path.isfile(src_file):
                try:
                    act_val = file(src_file, "r").read().split()[0]
                except:
                    self.log("cannot read %s from %s: %s" % (
                        key,
                        src_file,
                        process_tools.get_except_info()),
                             logging_tools.LOG_LEVEL_ERROR)
                    act_val = default
            else:
                self.log("file %s does not exist (key %s)" % (
                    src_file,
                    key),
                         logging_tools.LOG_LEVEL_ERROR)
                act_val = default
            global_config.add_config_entries([(key, configfile.str_c_var(act_val, source=src_file))])
    def _set_localhost_stuff(self):
        try:
            host_ip = socket.gethostbyname(global_config["HOST_SHORT"])
        except:
            self.log("cannot resolve host_name '%s': %s" % (global_config["HOST_SHORT"],
                                                            process_tools.get_except_info()),
                     logging_tools.LOG_LEVEL_ERROR)
            host_ip = "127.0.0.1"
        global_config.add_config_entries([("HOST_IP", configfile.str_c_var(host_ip, source="env"))])
    def _parse_job_script(self):
        if os.environ.has_key("JOB_SCRIPT"):
            script_file = os.environ["JOB_SCRIPT"]
            try:
                lines = [line.strip() for line in file(script_file, "r").read().split("\n")]
            except:
                self.log("Cannot read Scriptfile '%s' (%s)" % (script_file,
                                                               process_tools.get_except_info()),
                         logging_tools.LOG_LEVEL_ERROR)
            else:
                if global_config["CALLER_NAME"] == "prologue":
                    s_list = logging_tools.new_form_list()
                else:
                    s_list = None
                num_lines, num_sge, num_init = (len(lines), 0, 0)
                init_dict = {}
                for line, line_num in zip(lines, xrange(len(lines))):
                    if s_list is not None:
                        s_list.append([logging_tools.form_entry(line_num + 1, header="line"),
                                       logging_tools.form_entry(line, header="content")])
                    if line.startswith("#$ "):
                        num_sge += 1
                    elif line.startswith("#init "):
                        # valid init-keys:
                        # MONITOR=<type>
                        # MONITOR_KEYS=<key_list;>
                        # MONITOR_FULL_KEY_LIST=<true>
                        # TRIGGER_ERROR (flag, triggers error)
                        # EXTRA_WAIT=x (waits for x seconds)
                        num_init += 1
                        line_parts = [x.split("=", 1) for x in line[5:].strip().split(",")]
                        self.log("found #init-line '%s'" % (line))
                        if line_parts:
                            for key, value in [x for x in line_parts if len(x) == 2]:
                                key, value = (key.strip().upper(), value.strip().lower())
                                if key and value:
                                    init_dict[key] = value
                                    self.log("recognised init option '%s' (value '%s')" % (key, value))
                                    global_config.add_config_entries([(key, configfile.str_c_var(value, source="jobscript"))])
                            for key in [x[0].strip().upper() for x in line_parts if len(x) == 1]:
                                init_dict[key] = True
                                self.log("recognised init option '%s' (value '%s')" % (key, True))
                                global_config.add_config_entries([(key, configfile.bool_c_var(True, source="jobscript"))])
                self.log("Scriptfile '%s' has %d lines (%s and %s)" % (script_file,
                                                                       num_lines,
                                                                       logging_tools.get_plural("SGE related line", num_sge),
                                                                       logging_tools.get_plural("init.at related line", num_init)))
                if s_list:
                    try:
                        self.write_file("jobscript", str(s_list).split("\n"), linenumbers=False)
                    except:
                        self.log("error writing jobscript: %s" % (process_tools.get_except_info()), logging_tools.LOG_LEVEL_CRITICAL)
        else:
            self.log("environ has no JOB_SCRIPT key", logging_tools.LOG_LEVEL_WARN)
    def _parse_sge_env(self):
        # pe name
        if os.environ.has_key("PE") and os.environ.has_key("PE_HOSTFILE"):
            global_config.add_config_entries([("PE", configfile.str_c_var(os.environ["PE"], source="env"))])
        else:
            global_config.add_config_entries([("PE", configfile.str_c_var("", source="env"))])
        # TASK_ID
        if os.environ.has_key("SGE_TASK_FIRST") and os.environ.has_key("SGE_TASK_LAST") and os.environ.has_key("SGE_TASK_ID") and os.environ.has_key("SGE_TASK_STEPSIZE"):
            if os.environ["SGE_TASK_ID"] == "undefined":
                task_id = 0
            else:
                try:
                    task_id = int(os.environ["SGE_TASK_ID"])
                except:
                    self.log("error extracting SGE_TASK_ID: %s" % (process_tools.get_except_info()),
                             logging_tools.LOG_LEVEL_ERROR)
                    task_id = 0
                else:
                    pass
        else:
            task_id = 0
        full_job_id = "%s%s" % (global_config["JOB_ID"],
                                ".%d" % (task_id) if task_id else "")
        global_config.add_config_entries([("TASK_ID", configfile.int_c_var(task_id, source="env")),
                                          ("FULL_JOB_ID", configfile.str_c_var(full_job_id, source="env"))])
    def _check_user(self):
        try:
            pw_data = pwd.getpwnam(global_config["JOB_OWNER"])
        except KeyError:
            pw_data = None
            uid, gid, group = (0, 0, "unknown")
            self.log("Unknown user '%s', using ('%s', %d, %d) as (group, uid, gid)" % (
                global_config["JOB_OWNER"],
                group,
                uid,
                gid),
                     logging_tools.LOG_LEVEL_ERROR)
        else:
            uid = pw_data[2]
            gid = pw_data[3]
            try:
                grp_data = grp.getgrgid(gid)
            except KeyError:
                group = "unknown"
                self.log("Unknown group-id %d for user '%s', using %s as group" % (gid,
                                                                                   global_config["JOB_OWNER"],
                                                                                   group),
                         logging_tools.LOG_LEVEL_ERROR)
            else:
                group = grp_data[0]
        global_config.add_config_entries([
            ("GROUP", configfile.str_c_var(group, source="env")),
            ("UID"  , configfile.int_c_var(uid, source="env")),
            ("GID"  , configfile.int_c_var(gid, source="env"))
        ])
    def get_stat_str(self, ret_value):
        stat_dict = {0 : "OK",
                     1 : "Error",
                     2 : "Warning"}
        return stat_dict.get(ret_value, "unknown ret_value %d" % (ret_value))
    def _write_proepi_header(self):
        sep_str = "-" * global_config["SEP_LEN"]
        self._print(sep_str)
        self._print("Starting %s for job %s, %s at %s" % (global_config["CALLER_NAME"],
                                                          global_config["FULL_JOB_ID"],
                                                          self.get_owner_str(),
                                                          time.ctime(time.time())))
        self.log("writing %s-header for job %s, %s" % (global_config["CALLER_NAME"],
                                                       global_config["FULL_JOB_ID"],
                                                       self.get_owner_str()))
        self.log("Jobname is '%s' in queue '%s'" % (global_config["JOB_NAME"],
                                                    global_config["JOB_QUEUE"]),
                 do_print=True)
    def _write_proepi_footer(self):
        sep_str = "-" * global_config["SEP_LEN"]
        self.log("writing %s-footer for job %s, return value is %d (%s)" % (global_config["CALLER_NAME"],
                                                                            global_config["FULL_JOB_ID"],
                                                                            self.p_pool["return_value"],
                                                                            self.get_stat_str(self.p_pool["return_value"])))
        spent_time = logging_tools.get_diff_time_str(self.__end_time - self.__start_time)
        self._print("%s finished for job %s, status %s, spent %s" % (global_config["CALLER_NAME"],
                                                                     global_config["FULL_JOB_ID"],
                                                                     self.get_stat_str(self.p_pool["return_value"]),
                                                                     spent_time))
        self.log("%s took %s" % (global_config["CALLER_NAME"],
                                 spent_time))
        self._print(sep_str)
    def _write_pe_header(self):
        sep_str = "-" * global_config["SEP_LEN"]
        self._print(sep_str)
        self._print("Starting %s for job %s, %s at %s" % (global_config["CALLER_NAME"],
                                                          global_config["FULL_JOB_ID"],
                                                          self.get_owner_str(),
                                                          time.ctime(time.time())))
        self.log("writing %s-header for job %s, %s" % (global_config["CALLER_NAME"],
                                                       global_config["FULL_JOB_ID"],
                                                       self.get_owner_str()))
    def _write_pe_footer(self):
        sep_str = "-" * global_config["SEP_LEN"]
        self.log("writing %s-footer for job %s, return value is %d (%s)" % (global_config["CALLER_NAME"],
                                                                            global_config["FULL_JOB_ID"],
                                                                            self.p_pool["return_value"],
                                                                            self.get_stat_str(self.p_pool["return_value"])))
        spent_time = logging_tools.get_diff_time_str(self.__end_time - self.__start_time)
        self._print("%s finished for job %s, status %s, spent %s" % (global_config["CALLER_NAME"],
                                                                     global_config["FULL_JOB_ID"],
                                                                     self.get_stat_str(self.p_pool["return_value"]),
                                                                     spent_time))
        self.log("%s took %s" % (global_config["CALLER_NAME"],
                                 spent_time))
        self._print(sep_str)
    def get_owner_str(self):
        return "user %s (%d), group %s (%d)" % (global_config["JOB_OWNER"],
                                                global_config["UID"],
                                                global_config["GROUP"],
                                                global_config["GID"])
    def _write_run_info(self):
        self.log("running on host %s (IP %s)" % (global_config["HOST_SHORT"],
                                                 global_config["HOST_IP"]),
                 do_print=True)
    def _log_environments(self):
        out_list = logging_tools.new_form_list()
        for key in sorted(self.__env_dict.keys()):
            out_list.append([logging_tools.form_entry(key, header="Key"),
                             logging_tools.form_entry(self.__env_dict[key], header="Value")])
        self.write_file("env_%s" % (global_config["CALLER_NAME"]), str(out_list).split("\n"))
        out_list = logging_tools.new_form_list()
        for key in sorted(self.__env_int_dict.keys()):
            out_list.append([logging_tools.form_entry(key, header="Key"),
                             logging_tools.form_entry(self.__env_int_dict[key], header="Value")])
        self.write_file("env_int_%s" % (global_config["CALLER_NAME"]), str(out_list).split("\n"))
    def _read_config(self):
        if "CONFIG_FILE" in global_config:
            sections = ["queue_%s" % (global_config["JOB_QUEUE"]),
                        "node_%s" % (global_config["HOST_SHORT"])]
            if self.is_pe_call():
                sections.append("pe_%s" % (global_config["PE"]))
                sections.append("queue_%s_pe_%s" % (global_config["JOB_QUEUE"],
                                                    global_config["PE"]))
            self.log("scanning configfile %s for %s: %s" % (global_config["CONFIG_FILE"],
                                                            logging_tools.get_plural("section", len(sections)),
                                                            ", ".join(sections)))
            for section in sections:
                try:
                    global_config.parse_file(global_config["CONFIG_FILE"],
                                             section=section)
                except:
                    self.log("error scanning for section %s: %s" % (section,
                                                                    process_tools.get_except_info()),
                             logging_tools.LOG_LEVEL_ERROR)
            try:
                for line, log_level in global_config.get_log(clear=True):
                    self.log(line, log_level)
            except:
                self.log("error getting config_log: %s" % (process_tools.get_except_info()),
                         logging_tools.LOG_LEVEL_ERROR)
        else:
            self.log("no key CONFIG_FILE in glob_config, strange ...",
                     logging_tools.LOG_LEVEL_WARN)
    def _log_resources(self):
        res_used = {}
        jsd = os.environ.get("SGE_JOB_SPOOL_DIR", "")
        if jsd:
            usage_file = "%s/usage" % (jsd)
            if os.path.isfile(usage_file):
                try:
                    ufl = dict([[part.strip() for part in line.strip().split("=", 1)] for line in file(usage_file, "r").read().split("\n") if line.count("=")])
                except:
                    self.log("error reading usage_file %s: %s" % (usage_file,
                                                                  process_tools.get_except_info()),
                             logging_tools.LOG_LEVEL_ERROR)
                else:
                    try:
                        if ufl.has_key("ru_wallclock"):
                            res_used["time_wall"] = sec_to_str(int(ufl["ru_wallclock"]))
                        if ufl.has_key("start_time") and ufl.has_key("end_time"):
                            res_used["elapsed"] = sec_to_str(int(ufl["end_time"]) - int(ufl["start_time"]))
                        if ufl.has_key("exit_status"):
                            res_used["exit_status"] = str(ufl["exit_status"])
                        if ufl.has_key("ru_utime"):
                            res_used["time_user"] = sec_to_str(int(ufl["ru_utime"]))
                        if ufl.has_key("ru_stime"):
                            res_used["time_system"] = sec_to_str(int(ufl["ru_stime"]))
    ##                     if ufl.has_key("ru_ixrss"):
    ##                         res_used["shared memory size"] = str(ufl["ru_ixrss"])
    ##                     if ufl.has_key("ru_isrss"):
    ##                         res_used["memory size"] = str(ufl["ru_isrss"])
                    except:
                        pass
            else:
                self.log("no useage file in %s" % (jsd),
                         logging_tools.LOG_LEVEL_ERROR)
        else:
            self.log("no SGE_JOB_SPOOL_DIR in os.environ defined",
                     logging_tools.LOG_LEVEL_ERROR)
        if res_used:
            self._print("Resources used:")
            log_res = []
            out_list = logging_tools.new_form_list()
            #f_str = "%%%ds : %%s%%s" % (max([len(x) for x in res_used.keys()]))
            for key, value in [(key, res_used[key]) for key in sorted(res_used.keys())]:
                ext_str = ""
                if key == "exit_status":
                    try:
                        i_val = int(value)
                    except:
                        pass
                    else:
                        ext_str = {0   : "no failure",
                                   1   : "error before job",
                                   2   : "before writing config",
                                   3   : "before writing pid",
                                   4   : "before writing pid",
                                   5   : "reading config file",
                                   6   : "setting processor set",
                                   7   : "before prolog",
                                   8   : "in prolog",
                                   9   : "before pestart",
                                   10  : "in pestart",
                                   11  : "before job",
                                   12  : "before pestop",
                                   13  : "in pestop",
                                   14  : "before epilogue",
                                   15  : "in epilog",
                                   16  : "releasing processor set",
                                   24  : "migrating",
                                   25  : "rescheduling",
                                   26  : "opening output file",
                                   27  : "searching requested shell",
                                   28  : "changing to working directory",
                                   100 : "assumedly after job"}.get(i_val, "")
                        if i_val == 99:
                            self._set_exit_code("requeue requested", i_val)
                        ext_str = " (%s)" % (ext_str) if ext_str else ""
                out_list.append([logging_tools.form_entry(key, header="key"),
                                 logging_tools.form_entry(value, header="value"),
                                 logging_tools.form_entry(ext_str, header="info")])
                log_res.append("%s:%s%s" % (key, value, ext_str))
            self._print("\n".join(["  %s" % (line) for line in str(out_list).split("\n")]))
            self.log("reported %d resources: %s" % (len(log_res), ", ".join(log_res)))
        else:
            self.log("No resources found", do_print=True)
    def _log_limits(self):
        # read limits
        r_dict = {}
        try:
            import resource
        except ImportError:
            pass
        available_resources = [key for key in dir(resource) if key.startswith("RLIMIT")]
        for av_r in available_resources:
            try:
                r_dict[av_r] = resource.getrlimit(getattr(resource, av_r))
            except ValueError:
                r_dict[av_r] = "invalid resource"
            except:
                r_dict[av_r] = None
        if r_dict:
            res_keys = sorted(r_dict.keys())
            self.log("%s defined" % (logging_tools.get_plural("limit", len(res_keys))))
            res_list = logging_tools.new_form_list()
            for key in res_keys:
                val = r_dict[key]
                if type(val) == type(""):
                    info_str = val
                elif type(val) == type(()):
                    info_str = "%8d (hard), %8d (soft)" % val
                else:
                    info_str = "None (error?)"
                res_list.append([logging_tools.form_entry(key, header="key"),
                                 logging_tools.form_entry(info_str, header="value")])
            self.write_file("limits_%s" % (global_config["CALLER_NAME"]),
                            str(res_list).split("\n"))
        else:
            self.log("no limits found, strange ...", logging_tools.LOG_LEVEL_WARN)
    def _generate_hosts_file(self):
        orig_file, new_file = (self.__env_dict["PE_HOSTFILE"],
                               "/tmp/%s_%s" % (os.path.basename(self.__env_dict["PE_HOSTFILE"]),
                                                                global_config["FULL_JOB_ID"]))
        # node_file ok
        nf_ok = False
        if os.path.isfile(orig_file):
            try:
                node_list = [line.strip() for line in file(orig_file, "r").readlines() if line.strip()]
            except:
                self.log("Cannot read node_file %s: %s" % (orig_file,
                                                           process_tools.get_except_info()),
                         logging_tools.LOG_LEVEL_ERROR)
            else:
                nf_ok = True
                self.__node_list = [node_name.split(".")[0] for node_name in [line.split()[0] for line in node_list]]
                node_dict = dict([(node_name.split(".")[0], {"num" : int(node_num)}) for node_name, node_num in [line.split()[0 : 2] for line in node_list]])
        else:
            self.log("No node_file name '%s' found" % (orig_file),
                     logging_tools.LOG_LEVEL_ERROR)
        if not nf_ok:
            # dummy default node dict
            self.__node_list = [global_config["HOST_SHORT"]]
            node_dict = {global_config["HOST_SHORT"] : {"num" : 1}}
        # node_list is now a dict {short host-name : {num : #instnaces }}
        if not global_config.get("HAS_MPI_INTERFACE", True):
            # no mpi-interfaces
            pass
        else:
            mpi_postfix = global_config.get("MPI_POSTFIX", "mp")
            self.log("using mpi_postfix '%s' for PE '%s' on queue '%s'" % (mpi_postfix,
                                                                           global_config["PE"],
                                                                           global_config["JOB_QUEUE"]))
            for key, value in node_dict.iteritems():
                value["mpi_name"] = "%s%s" % (key, mpi_postfix)
        # resolve names
        for node_name in self.__node_list:
            node_stuff = node_dict[node_name]
            try:
                node_ip = socket.gethostbyname(node_name)
            except:
                self.log("error resolving %s to IP: %s" % (node_name,
                                                           process_tools.get_except_info()),
                         logging_tools.LOG_LEVEL_ERROR)
                node_ip = node_name
            node_stuff["ip"] = node_ip
            node_stuff["ip_list"] = [node_ip]
            if node_stuff.has_key("mpi_name"):
                try:
                    mpi_ip = socket.gethostbyname(node_stuff["mpi_name"])
                except:
                    self.log("error resolving %s to IP: %s" % (node_stuff["mpi_name"],
                                                               process_tools.get_except_info()),
                             logging_tools.LOG_LEVEL_ERROR)
                    mpi_ip = node_stuff["mpi_name"]
                node_stuff["mpi_ip"] = mpi_ip
                node_stuff["ip_list"].append(mpi_ip)
        self.log("content of node_list")
        content = pprint.PrettyPrinter(indent=1, width=10).pformat(self.__node_list)
        for line in content.split("\n"):
            self.log(" - %s" % (line))
        self.log("content of node_dict")
        content = pprint.PrettyPrinter(indent=1, width=10).pformat(node_dict)
        for line in content.split("\n"):
            self.log(" - %s" % (line))
        self.__node_dict = node_dict
    def _write_hosts_file(self, action):
        # generate various versions of host-file
        for var_name, file_name, generator in [# to be compatible
                                               # short file without MPI/IB-Interfacepostfix
                                               ("HOSTFILE_SHORT"     , "/tmp/pe_hostfile_s_%s" % (global_config["FULL_JOB_ID"])     , self._whf_short),
                                               ("HOSTFILE_OLD"       , "/tmp/pe_hostfile_%s" % (global_config["FULL_JOB_ID"])       , self._whf_plain),
                                               ("HOSTFILE_PLAIN_MPI" , "/tmp/hostfile_plain_mpi_%s" % (global_config["FULL_JOB_ID"]), self._whf_plain_mpi),
                                               ("HOSTFILE_PLAIN"     , "/tmp/hostfile_plain_%s" % (global_config["FULL_JOB_ID"])    , self._whf_plain),
                                               ("HOSTFILE_WITH_CPUS" , "/tmp/hostfile_wcpu_%s" % (global_config["FULL_JOB_ID"])     , self._whf_wcpu),
                                               ("HOSTFILE_WITH_SLOTS", "/tmp/hostfile_wslot_%s" % (global_config["FULL_JOB_ID"])    , self._whf_wslot)]:
            #("PE_HOSTFILE"        , "/tmp/hostfile_sge_%s" % (global_config["FULL_JOB_ID"]), self._whf_sge)]:
            global_config.add_config_entries([(var_name, configfile.str_c_var(file_name))])
            self._add_script_var(var_name, file_name)
            if action == "save":
                open(file_name, "w").write("\n".join(generator()) + "\n")
            elif action == "delete":
                if os.path.isfile(file_name):
                    try:
                        os.unlink(file_name)
                    except:
                        self.log("cannot remove %s: %s" % (file_name,
                                                           process_tools.get_except_info()),
                                 logging_tools.LOG_LEVEL_ERROR)
    def _show_pe_hosts(self):
        # show pe_hosts
        self._print("  %s defined: %s" % (logging_tools.get_plural("NFS host", len(self.__node_list)),
                                          ", ".join(["%s (%s, %d)" % (node_name,
                                                                      self.__node_dict[node_name]["ip"],
                                                                      self.__node_dict[node_name]["num"]) for node_name in self.__node_list])))
        # mpi hosts
        mpi_nodes = [node_name for node_name in self.__node_list if self.__node_dict[node_name].has_key("mpi_name")]
        self._print("  %s defined: %s" % (logging_tools.get_plural("MPI host", len(mpi_nodes)),
                                          ", ".join(["%s (on %s, %s, %d)" % (self.__node_dict[node_name]["mpi_name"],
                                                                             node_name,
                                                                             self.__node_dict[node_name]["mpi_ip"],
                                                                             self.__node_dict[node_name]["num"]) for node_name in mpi_nodes]) or "---"))
    def _get_mpi_name(self, n_name):
        return self.__node_dict[n_name].get("mpi_name", n_name)
    def _whf_short(self):
        return self.__node_list
    def _whf_plain_mpi(self):
        return sum([[self._get_mpi_name(node_name)] * self.__node_dict[node_name]["num"] for node_name in self.__node_list], [])
    def _whf_plain(self):
        return sum([[node_name] * self.__node_dict[node_name]["num"] for node_name in self.__node_list], [])
    def _whf_wcpu(self):
        return ["%s cpu=%d" % (self._get_mpi_name(node_name), self.__node_dict[node_name]["num"]) for node_name in self.__node_list]
    def _whf_wslot(self):
        return ["%s max_slots=%d" % (self._get_mpi_name(node_name), self.__node_dict[node_name]["num"]) for node_name in self.__node_list]
    def _whf_sge(self):
        # like PE_HOSTFILE just with the Parallel Interfaces
        return ["%s %d %s@%s <NULL>" % (self._get_mpi_name(node_name),
                                        self.__node_dict[node_name]["num"],
                                        global_config["JOB_QUEUE"],
                                        node_name) for node_name in self.__node_list]
    def _prologue(self):
        client.setup(self.log, self.p_pool.zmq_context)
        self._create_wrapper_script()
        #conn_str = process_tools.get_zmq_ipc_name("command", s_name="collserver")
        #vector_socket = self.p_pool.zmq_context.socket(zmq.REQ)
        #vector_socket.connect(conn_str)
        #vector_socket.send_unicode(unicode(server_command.srv_command(command="load")))
        #print vector_socket.recv_unicode()
        #client("127.0.0.1", 2001)
        #client("192.168.44.25", 2001)
        # discovery part
        #client.discover_0mq()
        # send command
        #print client.send_srv_command(server_command.srv_command(command="load"), timeout=0.1, resend=5)
        client.close()
        yield False
    def _epilogue(self):
        self._delete_wrapper_script()
        yield False
    def _pe_start(self):
        self.log("pe_start called")
        self._generate_hosts_file()
        #self._send_tag("pe_start", queue_list=self.__node_list)
        self._write_hosts_file("save")
        self._show_pe_hosts()
        # check reachability of user-homes
        #self._check_homedir(self.__node_list)
        #if not self.__return_value:
        #    self._flight_check("preflight")
        #if not self.__return_value:
        #    # check if exit_code is still ok
        #    self._kill_foreign_pids(self.__node_list)
        #    self._remove_foreign_ipcs(self.__node_list)
        yield False
    def _pe_stop(self):
        self.log("pe_stop called")
        self._generate_hosts_file()
        #self._send_tag("pe_stop", queue_list=self.__node_list)
        self._show_pe_hosts()
        self._write_hosts_file("keep")
        #self._kill_foreign_pids(self.__node_list)
        #self._remove_foreign_ipcs(self.__node_list)
        #if self.__glob_config.get("UMOUNT_CALL", True):
        #    self._umount_nfs_mounts(self.__node_list)
        #self._flight_check("postflight")
        self._write_hosts_file("delete")
        yield False
    def loop_function(self):
        self.__start_time = time.time()
        self.log("log_name is %s/%s" % (global_config["LOG_NAME"], self.__log_name), pool=True)
        # copy environment
        self._copy_environments()
        # populate glob_config
        self._parse_server_addresses()
        self._set_localhost_stuff()
        # populate opt_dict
        self._parse_sge_env()
        self._check_user()
        self._parse_job_script()
        self._read_config()
        self._show_config()
        # just for testing
        #self.write_file("aha", "/etc/hosts")
##        for i in xrange(10):
##            time.sleep(1)
##            yield True
        if self.is_start_call():
            self._log_environments()
            self._log_limits()
        if self.is_proepilogue_call():
            self._write_proepi_header()
        elif self.is_pe_call():
            self._write_pe_header()
        if self.is_start_call():
            self._write_run_info()
        if "JOB_SCRIPT" in self.__env_dict:
            self.log("starting inner loop for %s" % (global_config["CALLER_NAME"]))
            if global_config["CALLER_NAME"] == "prologue":
                sub_func = self._prologue
            elif global_config["CALLER_NAME"] == "epilogue":
                sub_func = self._epilogue
            elif self.is_pe_start_call():
                sub_func = self._pe_start
            elif self.is_pe_stop_call():
                sub_func = self._pe_stop
            else:
                sub_func = None
            if sub_func is None:
                self.log("unknown runmode %s" % (global_config["CALLER_NAME"]),
                         logging_tools.LOG_LEVEL_ERROR)
            else:
                for p_res in sub_func():
                    if p_res:
                        yield p_res
            self.log("ending inner loop")
        else:
            self.log("no JOB_SCRIPT in env_dict, skipping inner loop", logging_tools.LOG_LEVEL_ERROR)
        if global_config["CALLER_NAME"] == "epilogue":
            self._log_resources()
        self.__end_time = time.time()
        if self.is_proepilogue_call():
            self._write_proepi_footer()
        elif self.is_pe_call():
            self._write_pe_footer()
        self.log("took %s" % (logging_tools.get_diff_time_str(self.__end_time - self.__start_time)))
        yield None
##        print "ce"
##        a = 0
##        for i in xrange(5):
##            print "*", i, a
##            a += i
##            yield a + 1
##            #yield 
    def close(self):
        self.__log_template.close()
        
class process_pool(threading_tools.process_pool):
    def __init__(self):
        self.start_time = time.time()
        self.global_config = global_config
        self.__log_cache, self.__log_template = ([], None)
        self.log("-" * SEP_LEN)
        threading_tools.process_pool.__init__(self, "main", zmq=True,
                                              blocking_loop=False,
                                              #zmq_debug=True,
                                              zmq_contexts=1,
                                              loop_granularity=100)
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context)
        self.install_signal_handlers()
        self.register_exception("int_error", self._sigint)
        self.register_exception("term_error", self._sigint)
        self._set_sge_environment()
        self._read_config()
        self._show_config()
        self._job = job_object(p_pool=self)
        self.loop_function = self._job.loop_function
        #self["return_value"] = "a"
        self.register_timer(self._force_exit, global_config["MAX_RUN_TIME"])
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK, **kwargs):
        if self.__log_template:
            while self.__log_cache:
                cur_lev, cur_what = self.__log_cache.pop(0)
                self.__log_template.log(cur_lev, cur_what)
            self.__log_template.log(lev, what)
        else:
            self.__log_cache.append((lev, what))
        if kwargs.get("do_print", False):
            self._print("%s%s" % ("[%s]" % (logging_tools.get_log_level_str(lev)) if lev != logging_tools.LOG_LEVEL_OK else "",
                                  what))
    def _print(self, what):
        try:
            print what
        except:
            self.log("cannot print '%s': %s" % (what,
                                                process_tools.get_except_info()),
                     logging_tools.LOG_LEVEL_ERROR)
    def _sigint(self, err_cause):
        if self["exit_requested"]:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            self["exit_requested"] = True
    def _force_exit(self):
        self.log("forcing exit", logging_tools.LOG_LEVEL_WARN)
        self["exit_requested"] = True
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
    def _set_sge_environment(self):
        for v_name, v_src in [("SGE_ROOT", "/etc/sge_root"),
                              ("SGE_CELL", "/etc/sge_cell")]:
            if os.path.isfile(v_src):
                v_val = file(v_src, "r").read().strip()
                self.log("Setting environment-variable '%s' to %s" % (v_name, v_val))
            else:
                self.log("Cannot assign environment-variable '%s', problems ahead ..." % (v_name),
                         logging_tools.LOG_LEVEL_ERROR)
                #sys.exit(1)
            global_config.add_config_entries([
                (v_name, configfile.str_c_var(v_val, source=v_src))])
        if "SGE_ROOT" in global_config and "SGE_CELL" in global_config:
            global_config.add_config_entries([
                ("SGE_VERSION", configfile.str_c_var("6", source="intern"))])
    def _read_config(self):
        # reading the config
        conf_dir = "%s/3rd_party" % (global_config["SGE_ROOT"])
        if not os.path.isdir(conf_dir):
            self.log("no config_dir %s found, using defaults" % (conf_dir),
                     logging_tools.LOG_LEVEL_ERROR,
                     do_print=True)
        else:
            conf_file = os.path.join(conf_dir, CONFIG_FILE_NAME)
            if not os.path.isfile(conf_file):
                self.log("no config_file %s found, using defaults" % (conf_file),
                         logging_tools.LOG_LEVEL_ERROR,
                         do_print=True)
                self._print("Copy the following lines to %s :" % (conf_file))
                self._print("")
                self._print("[global]")
                for key in [c_key for c_key in sorted(global_config.keys()) if not c_key.startswith("SGE_") and global_config.get_source(c_key) == "default"]:
                    # don't write SGE_* stuff
                    self._print("%s=%s" % (key, str(global_config[key])))
                self._print("")
            else:
                global_config.add_config_entries([("CONFIG_FILE", configfile.str_c_var(conf_file))])
                self.log("reading config from %s" % (conf_file))
                global_config.parse_file(global_config["CONFIG_FILE"])
    def loop_end(self):
        self.log("execution time was %s" % (logging_tools.get_diff_time_str(time.time() - self.start_time)))
    def loop_post(self):
        self._job.close()
        self.__log_template.close()
        
#for key in sorted(global_config.keys()):
#    print key, type(global_config[key]), global_config[key]
            
def new_main_code():
    ret_value = 1
##    opt_dict = my_opt_parser().parse()
##    if opt_dict:
##        hs_ok = process_tools.set_handles({"err" : (0, "/var/lib/logging-server/py_err")}, error_only = True)
##        my_tp = my_thread_pool(opt_dict)
##        my_tp.thread_loop()
##        ret_value = my_tp.exit_code
    return ret_value

global_config = configfile.get_global_config(process_tools.get_programm_name())

def zmq_main_code():
    # brand new 0MQ-based code
    global_config.add_config_entries([
        ("DEBUG"                , configfile.bool_c_var(False, help_string="enable debug mode [%(default)s]", short_options="d", only_commandline=True)),
        ("LOG_DESTINATION"      , configfile.str_c_var("uds:/var/lib/logging-server/py_log_zmq")),
        ("LOG_NAME"             , configfile.str_c_var("proepilogue")),
        ("MAX_RUN_TIME"         , configfile.int_c_var(60)),
        ("SEP_LEN"              , configfile.int_c_var(80)),
        ("HAS_MPI_INTERFACE"    , configfile.bool_c_var(True)),
        ("MPI_POSTFIX"          , configfile.str_c_var("mp")),
        ("BRUTAL_CLEAR_MACHINES", configfile.bool_c_var(False)),
        ("SIMULTANEOUS_PINGS"   , configfile.int_c_var(128)),
        ("PING_PACKETS"         , configfile.int_c_var(5)),
        ("PING_TIMEOUT"         , configfile.float_c_var(5.0)),
        ("MIN_KILL_UID"         , configfile.int_c_var(110)),
        ("UMOUNT_CALL"          , configfile.bool_c_var(True))
    ])
    global_config.parse_file()
    options = global_config.handle_commandline(add_writeback_option=True,
                                               positional_arguments=True)
    _exit = False
    if len(options.arguments) in [5, 8]:
        global_config.add_config_entries([
            ("HOST_LONG", configfile.str_c_var(options.arguments[0], source="cmdline")),
            ("JOB_OWNER", configfile.str_c_var(options.arguments[1], source="cmdline")),
            ("JOB_ID"   , configfile.str_c_var(options.arguments[2], source="cmdline")),
            ("JOB_NAME" , configfile.str_c_var(options.arguments[3], source="cmdline")),
            ("JOB_QUEUE", configfile.str_c_var(options.arguments[4], source="cmdline"))
        ])
        if len(options.arguments) == 8:
            global_config.add_config_entries([
                ("PE_HOSTFILE", configfile.str_c_var(options.arguments[5], source="cmdline")),
                ("PE"         , configfile.str_c_var(options.arguments[6], source="cmdline")),
                ("PE_SLOTS"   , configfile.str_c_var(options.arguments[7], source="cmdline"))
            ])
    else:
        print "Unable to determine execution mode for %s, exiting (%d args)" % (
            global_config.name(),
            len(options.arguments))
        _exit = True
    if not _exit:
        cf_time = time.localtime(os.stat(configfile.__file__.replace(".pyc", ".py").replace(".pyo", ".py"))[stat.ST_MTIME])
        if (cf_time.tm_year, cf_time.tm_mon, cf_time.tm_mday) < (2012, 5, 1):
            print "your python-modules-base are too old, please upgrade (%d, %d, %d)" % (cf_time.tm_year, cf_time.tm_mon, cf_time.tm_mday)
            return 0
        else:
            # add more entries
            global_config.add_config_entries([
                ("HOST_SHORT" , configfile.str_c_var(global_config["HOST_LONG"].split(".")[0], source="cmdline")),
                ("CALLER_NAME", configfile.str_c_var(global_config.name(), source="cmdline")),
                ("HOST_IP"    , configfile.str_c_var("unknown", source="cmdline")),
            ])
            return process_pool().loop()
    else:
        return -1
    
if __name__ == "__main__":
    sys.exit(zmq_main_code())
