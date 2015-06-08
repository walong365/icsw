#!/usr/bin/python-init -Ot
#
# -*- coding: utf-8 -*-
#
# Copyright (C) 2001-2008,2010-2015 Andreas Lang-Nevyjel, init.at
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
""" pro/epilogue script for SGE """

import sys

# clean sys.path, remove all paths not starting with /opt
sys.path = [entry for entry in sys.path if entry.startswith("/opt")]

import grp
import os
import pprint
import pwd
import socket
import stat
import time
try:
    from initat.tools import threading_tools
    from initat.tools import configfile
    from initat.tools import logging_tools
    from initat.tools import net_tools
    from initat.tools import process_tools
    from initat.tools import server_command
    NEW_CODE = True
except ImportError:
    # for running on nodes
    import threading_tools
    import configfile
    import net_tools
    import process_tools
    import server_command
    import logging_tools
    NEW_CODE = False


SEP_LEN = 70
LOCAL_IP = "127.0.0.1"
# PROFILE_PREFIX = ".mon"
CONFIG_FILE_NAME = "proepilogue.conf"
RMS_SERVER_PORT = 8009


def sec_to_str(in_sec):
    diff_d = int(in_sec / (3600 * 24))
    dt = in_sec - 3600 * 24 * diff_d
    diff_h = int(dt / 3600)
    dt -= 3600 * diff_h
    diff_m = int(dt / 60)
    dt -= diff_m * 60
    # if diff_d:
    out_f = "%2d:%02d:%02d:%02d" % (diff_d, diff_h, diff_m, dt)
    # else:
    #    out_f = "%2d:%02d:%02d" % (diff_h, diff_m, dt)
    return out_f


class job_object(object):
    def __init__(self, p_pool):
        self.p_pool = p_pool
        self.__log_dir = time.strftime("%Y/%m/%d/%%s%%s") % (
            global_config["JOB_ID"],
            ".{}".format(os.environ["SGE_TASK_ID"]) if os.environ.get("SGE_TASK_ID", "undefined") != "undefined" else "")
        self.__log_name = "{}".format(self.__log_dir)
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
            self.log(
                u"cannot print '{}': {}".format(
                    what,
                    process_tools.get_except_info()
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
    # wrapper script tools

    def _get_wrapper_script_name(self):
        return os.path.join(
            os.path.dirname(self.__env_dict["JOB_SCRIPT"]),
            "{}.new".format(global_config["FULL_JOB_ID"])
        )

    def _get_var_script_name(self):
        return os.path.join(
            os.path.dirname(self.__env_dict["JOB_SCRIPT"]),
            "{}.var".format(global_config["FULL_JOB_ID"])
        )

    def _create_wrapper_script(self):
        # only sensible if sge_starter_method for queue is set
        src_file = self.__env_dict["JOB_SCRIPT"]
        dst_file = self._get_wrapper_script_name()
        var_file = self._get_var_script_name()
        if not dst_file.startswith("/"):
            self.log("refuse to create wrapper script {}".format(dst_file),
                     logging_tools.LOG_LEVEL_ERROR)
            return
        self.log(
            "Creating wrapper-script ({} for {})".format(
                dst_file,
                src_file
            )
        )
        shell_path, shell_start_mode = (self.__env_int_dict.get("shell_path", "/bin/bash"),
                                        self.__env_int_dict.get("shell_start_mode", "posix_compliant"))
        # cluster_queue_name = global_config["JOB_QUEUE"]
        self.log("shell_path is '%s', shell_start_mode is '%s'" % (shell_path,
                                                                   shell_start_mode))
        # cpuset_dir_name = "%s/cpuset" % (g_config["SGE_ROOT"])
        no_cpuset_cause = []
        if no_cpuset_cause:
            self.log("not using cpuset because: {}".format(", ".join(no_cpuset_cause)))
        if shell_start_mode == "posix_compliant" and shell_path:
            df_lines = [
                "#!{}".format("/bin/sh"),
                "echo 'wrapper_script, no cpu_set'",
                "export BASH_ENV=$HOME/.bashrc",
                ". {}".format(var_file),
                "exec {} {} $*".format(shell_path, src_file),
                "",
            ]
        else:
            df_lines = [
                "#!{}".format("/bin/sh"),
                "echo 'wrapper_script, no cpu_set'",
                "export BASH_ENV=$HOME/.bashrc",
                ". {}".format(var_file),
                "exec {} $*".format(src_file),
                "",
            ]
        file(dst_file, "w").write("\n".join(df_lines))
        file(var_file, "w").write("#!/bin/bash\n")
        self.write_file("wrapper_script", df_lines)
        os.chmod(dst_file, 0755)
        os.chmod(var_file, 0755)
        os.chown(var_file, global_config["UID"], global_config["GID"])

    def _delete_wrapper_script(self):
        src_file = self.__env_dict["JOB_SCRIPT"]
        dst_file = self._get_wrapper_script_name()
        if not dst_file.startswith("/"):
            self.log("refuse to delete wrapper script {}".format(dst_file),
                     logging_tools.LOG_LEVEL_ERROR)
            return
        self.log("Deleting wrapper-script (%s for %s)" % (dst_file,
                                                          src_file))
        if os.path.isfile(dst_file):
            try:
                os.unlink(dst_file)
            except:
                self.log(
                    "error deleting {}: {}".format(
                        dst_file,
                        process_tools.get_except_info()
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
            else:
                self.log("deleted {}".format(dst_file))
        else:
            self.log("no such file: {}".format(dst_file),
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

    @property
    def is_start_call(self):
        return global_config["CALLER_NAME"] in ["prologue",
                                                "lamstart",
                                                "mvapich2start",
                                                "pvmstart",
                                                "pestart"]

    @property
    def is_pe_start_call(self):
        return global_config["CALLER_NAME"] in ["lamstart",
                                                "pestart",
                                                "pvmstart",
                                                "mvapich2start"]

    @property
    def is_pe_end_call(self):
        return global_config["CALLER_NAME"] in ["lamstop",
                                                "pestop",
                                                "pvmstop",
                                                "mvapich2stop"]

    @property
    def is_proepilogue_call(self):
        return global_config["CALLER_NAME"] in ["prologue",
                                                "epilogue"]

    @property
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
            self.log("Config : {}".format(conf))

    def write_file(self, name, content, **args):
        ss_time = time.time()
        logger = logging_tools.get_logger("%s.%s/%s" % (global_config["LOG_NAME"],
                                                        self.__log_dir.replace(".", "\."),
                                                        name),
                                          global_config["LOG_DESTINATION"],
                                          zmq=True,
                                          context=self.p_pool.zmq_context)
        if isinstance(content, basestring) and content.startswith("/"):
            # content is a filename
            content = file(content, "r").read().split("\n")
        if isinstance(content, basestring):
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
            self.__env_int_dict = dict(
                [
                    (key, value) for key, value in [
                        line.split("=", 1) for line in file(
                            os.path.join(
                                self.__env_dict["SGE_JOB_SPOOL_DIR"],
                                "config"
                            ),
                            "r"
                        ).read().strip().split("\n") if line.count("=")
                    ]
                ]
            )
        else:
            self.__env_int_dict = {}

    def _parse_server_addresses(self):
        for src_file, key, default in [
            ("/etc/motherserver", "MOTHER_SERVER", "localhost"),
            ("/etc/sge_server", "SGE_SERVER", "localhost")
        ]:
            if os.path.isfile(src_file):
                try:
                    act_val = file(src_file, "r").read().split()[0]
                except:
                    self.log(
                        "cannot read {} from {}: {}".format(
                            key,
                            src_file,
                            process_tools.get_except_info()
                        ),
                        logging_tools.LOG_LEVEL_ERROR
                    )
                    act_val = default
            else:
                self.log(
                    "file {} does not exist (key {})".format(
                        src_file,
                        key
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
                act_val = default
            global_config.add_config_entries([(key, configfile.str_c_var(act_val, source=src_file))])

    def _set_localhost_stuff(self):
        try:
            host_ip = socket.gethostbyname(global_config["HOST_SHORT"])
        except:
            self.log(
                "cannot resolve host_name '{}': {}".format(
                    global_config["HOST_SHORT"],
                    process_tools.get_except_info()
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
            host_ip = "127.0.0.1"
        global_config.add_config_entries([("HOST_IP", configfile.str_c_var(host_ip, source="env"))])

    def _parse_job_script(self):
        if "JOB_SCRIPT" in os.environ:
            script_file = os.environ["JOB_SCRIPT"]
            try:
                lines = [line.strip() for line in file(script_file, "r").read().split("\n")]
            except:
                self.log(
                    "cannot read scriptfile '{}' ({})".format(
                        script_file,
                        process_tools.get_except_info()
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
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
                self.log("Scriptfile '%s' has %d lines (%s and %s)" % (
                    script_file,
                    num_lines,
                    logging_tools.get_plural("SGE related line", num_sge),
                    logging_tools.get_plural("init.at related line", num_init)))
                if s_list:
                    try:
                        self.write_file("jobscript", str(s_list).split("\n"), linenumbers=False)
                    except:
                        self.log("error writing jobscript: {}".format(process_tools.get_except_info()), logging_tools.LOG_LEVEL_CRITICAL)
        else:
            self.log("environ has no JOB_SCRIPT key", logging_tools.LOG_LEVEL_WARN)

    def _parse_sge_env(self):
        # pe name
        if "PE" in os.environ and "PE_HOSTFILE" in os.environ:
            global_config.add_config_entries([("PE", configfile.str_c_var(os.environ["PE"], source="env"))])
        else:
            global_config.add_config_entries([("PE", configfile.str_c_var("", source="env"))])
        # TASK_ID
        if "SGE_TASK_FIRST" in os.environ and "SGE_TASK_LAST" in os.environ and "SGE_TASK_ID" in os.environ and "SGE_TASK_STEPSIZE" in os.environ:
            if os.environ["SGE_TASK_ID"] == "undefined":
                task_id = 0
            else:
                try:
                    task_id = int(os.environ["SGE_TASK_ID"])
                except:
                    self.log(
                        "error extracting SGE_TASK_ID: {}".format(process_tools.get_except_info()),
                        logging_tools.LOG_LEVEL_ERROR
                    )
                    task_id = 0
                else:
                    pass
        else:
            task_id = 0
        full_job_id = "{}{}".format(
            global_config["JOB_ID"],
            ".{:d}".format(task_id) if task_id else ""
        )
        global_config.add_config_entries(
            [
                ("TASK_ID", configfile.int_c_var(task_id, source="env")),
                ("FULL_JOB_ID", configfile.str_c_var(full_job_id, source="env"))
            ]
        )

    def _check_user(self):
        try:
            pw_data = pwd.getpwnam(global_config["JOB_OWNER"])
        except KeyError:
            pw_data = None
            uid, gid, group = (0, 0, "unknown")
            self.log(
                "Unknown user '{}', using ('{}', {:d}, {:d}) as (group, uid, gid)".format(
                    global_config["JOB_OWNER"],
                    group,
                    uid,
                    gid
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
        else:
            uid = pw_data[2]
            gid = pw_data[3]
            try:
                grp_data = grp.getgrgid(gid)
            except KeyError:
                group = "unknown"
                self.log(
                    "Unknown group-id {:d} for user '{}', using {} as group".format(
                        gid,
                        global_config["JOB_OWNER"],
                        group
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
            else:
                group = grp_data[0]
        global_config.add_config_entries(
            [
                ("GROUP", configfile.str_c_var(group, source="env")),
                ("UID", configfile.int_c_var(uid, source="env")),
                ("GID", configfile.int_c_var(gid, source="env"))
            ]
        )

    def get_stat_str(self, ret_value):
        stat_dict = {
            0: "OK",
            1: "Error",
            2: "Warning"
        }
        return stat_dict.get(ret_value, "unknown ret_value {:d}".format(ret_value))

    def _write_proepi_header(self):
        sep_str = "-" * global_config["SEP_LEN"]
        self._print(sep_str)
        self._print(
            "Starting {} for job {}, {} at {}".format(
                global_config["CALLER_NAME"],
                global_config["FULL_JOB_ID"],
                self.get_owner_str(),
                time.ctime(time.time())
            )
        )
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
        self.log(
            "{} took {}".format(
                global_config["CALLER_NAME"],
                spent_time
            )
        )
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
        self.log(
            "{} took {}".format(
                global_config["CALLER_NAME"],
                spent_time
            )
        )
        self._print(sep_str)

    def get_owner_str(self):
        return "user {} ({:d}), group {} ({:d})".format(
            global_config["JOB_OWNER"],
            global_config["UID"],
            global_config["GROUP"],
            global_config["GID"]
        )

    def _write_run_info(self):
        self.log(
            "running on host {} (IP {})".format(
                global_config["HOST_SHORT"],
                global_config["HOST_IP"]
            ),
            do_print=True
        )

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
            if self.is_pe_call:
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
            usage_file = os.path.join(jsd, "usage")
            if os.path.isfile(usage_file):
                try:
                    ufl = dict([[part.strip() for part in line.strip().split("=", 1)] for line in file(usage_file, "r").read().split("\n") if line.count("=")])
                except:
                    self.log(
                        "error reading usage_file {}: {}".format(
                            usage_file,
                            process_tools.get_except_info()
                        ),
                        logging_tools.LOG_LEVEL_ERROR
                    )
                else:
                    try:
                        if "ru_wallclock" in ufl:
                            res_used["time_wall"] = sec_to_str(int(ufl["ru_wallclock"]))
                        if "start_time" in ufl and "end_time" in ufl:
                            res_used["elapsed"] = sec_to_str(int(ufl["end_time"]) - int(ufl["start_time"]))
                        if "exit_status" in ufl:
                            res_used["exit_status"] = str(ufl["exit_status"])
                        if "ru_utime" in ufl:
                            res_used["time_user"] = sec_to_str(int(ufl["ru_utime"]))
                        if "ru_stime" in ufl:
                            res_used["time_system"] = sec_to_str(int(ufl["ru_stime"]))
    # #                     if ufl.has_key("ru_ixrss"):
    # #                         res_used["shared memory size"] = str(ufl["ru_ixrss"])
    # #                     if ufl.has_key("ru_isrss"):
    # #                         res_used["memory size"] = str(ufl["ru_isrss"])
                    except:
                        pass
            else:
                self.log(
                    "no useage file in {}".format(
                        jsd
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
        else:
            self.log(
                "no SGE_JOB_SPOOL_DIR in os.environ defined",
                logging_tools.LOG_LEVEL_ERROR
            )
        if res_used:
            self._print("Resources used:")
            log_res = []
            out_list = logging_tools.new_form_list()
            # f_str = "%%%ds : %%s%%s" % (max([len(x) for x in res_used.keys()]))
            for key, value in [(key, res_used[key]) for key in sorted(res_used.keys())]:
                ext_str = ""
                if key == "exit_status":
                    try:
                        i_val = int(value)
                    except:
                        pass
                    else:
                        ext_str = {
                            0: "no failure",
                            1: "error before job",
                            2: "before writing config",
                            3: "before writing pid",
                            4: "before writing pid",
                            5: "reading config file",
                            6: "setting processor set",
                            7: "before prolog",
                            8: "in prolog",
                            9: "before pestart",
                            10: "in pestart",
                            11: "before job",
                            12: "before pestop",
                            13: "in pestop",
                            14: "before epilogue",
                            15: "in epilog",
                            16: "releasing processor set",
                            24: "migrating",
                            25: "rescheduling",
                            26: "opening output file",
                            27: "searching requested shell",
                            28: "changing to working directory",
                            100: "assumedly after job"
                        }.get(i_val, "")
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
            self.log("{} defined".format(logging_tools.get_plural("limit", len(res_keys))))
            res_list = logging_tools.new_form_list()
            for key in res_keys:
                val = r_dict[key]
                if isinstance(val, basestring):
                    info_str = val
                elif type(val) == tuple:
                    info_str = "{:8d} (hard), {:8d} (soft)".format(val[0], val[1])
                else:
                    info_str = "None (error?)"
                res_list.append([logging_tools.form_entry(key, header="key"),
                                 logging_tools.form_entry(info_str, header="value")])
            for _line in unicode(res_list).split("\n"):
                self.log(_line)
            self.write_file(
                "limits_{}".format(
                    global_config["CALLER_NAME"]
                ),
                str(res_list).split("\n")
            )
        else:
            self.log("no limits found, strange ...", logging_tools.LOG_LEVEL_WARN)

    def _generate_hosts_file(self):
        if "PE_HOSTFILE" not in self.__env_dict:
            self.log("no PE_HOSTFILE found in environment", logging_tools.LOG_LEVEL_ERROR)
            self.__node_list, self.__node_dict = ([], {})
            return
        orig_file = self.__env_dict["PE_HOSTFILE"]
        # node_file ok
        nf_ok = False
        if os.path.isfile(orig_file):
            try:
                node_list = [line.strip() for line in file(orig_file, "r").readlines() if line.strip()]
            except:
                self.log(
                    "Cannot read node_file {}: {}".format(
                        orig_file,
                        process_tools.get_except_info()
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
            else:
                nf_ok = True
                self.__node_list = [node_name.split(".")[0] for node_name in [line.split()[0] for line in node_list]]
                try:
                    node_dict = dict([(node_name.split(".")[0], {"num": int(node_num)}) for node_name, node_num in [line.split()[0:2] for line in node_list]])
                except:
                    self.log(
                        "cannot interpret node_file {}: {}".format(
                            orig_file,
                            process_tools.get_except_info()
                        ),
                        logging_tools.LOG_LEVEL_ERROR
                    )
                    node_dict = dict([(node_name.split(".")[0], {"num": 1}) for node_name in node_list])
        else:
            self.log("No node_file name '%s' found" % (orig_file),
                     logging_tools.LOG_LEVEL_ERROR)
        if not nf_ok:
            # dummy default node dict
            self.__node_list = [global_config["HOST_SHORT"]]
            node_dict = {global_config["HOST_SHORT"]: {"num": 1}}
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
            if "mpi_name" in node_stuff:
                try:
                    mpi_ip = socket.gethostbyname(node_stuff["mpi_name"])
                except:
                    self.log("error resolving %s to IP: %s" % (node_stuff["mpi_name"],
                                                               process_tools.get_except_info()),
                             logging_tools.LOG_LEVEL_ERROR)
                    mpi_ip = node_stuff["mpi_name"]
                node_stuff["mpi_ip"] = mpi_ip
                node_stuff["ip_list"].append(mpi_ip)
        self.__node_dict = node_dict
        self._pprint(self.__node_list, "node_list")
        self._pprint(self.__node_dict, "node_dict")

    def _pprint(self, in_dict, in_name):
        content = pprint.PrettyPrinter(indent=1, width=10).pformat(in_dict)
        self.log("content of %s" % (in_name))
        for line in content.split("\n"):
            self.log(" - %s" % (line))

    def _write_hosts_file(self, action):
        # generate various versions of host-file
        for var_name, file_name, generator in [
            # to be compatible
            # short file without MPI/IB-Interfacepostfix
            ("HOSTFILE_SHORT", "/tmp/pe_hostfile_s_{}".format(global_config["FULL_JOB_ID"]), self._whf_short),
            ("HOSTFILE_OLD", "/tmp/pe_hostfile_{}".format(global_config["FULL_JOB_ID"]), self._whf_plain),
            ("HOSTFILE_PLAIN_MPI", "/tmp/hostfile_plain_mpi_{}".format(global_config["FULL_JOB_ID"]), self._whf_plain_mpi),
            ("HOSTFILE_PLAIN", "/tmp/hostfile_plain_{}".format(global_config["FULL_JOB_ID"]), self._whf_plain),
            ("HOSTFILE_WITH_CPUS", "/tmp/hostfile_wcpu_{}".format(global_config["FULL_JOB_ID"]), self._whf_wcpu),
            ("HOSTFILE_WITH_SLOTS", "/tmp/hostfile_wslot_{}".format(global_config["FULL_JOB_ID"]), self._whf_wslot)
        ]:
            # ("PE_HOSTFILE"        , "/tmp/hostfile_sge_%s" % (global_config["FULL_JOB_ID"]), self._whf_sge)]:
            global_config.add_config_entries([(var_name, configfile.str_c_var(file_name))])
            self._add_script_var(var_name, file_name)
            if action == "save":
                open(file_name, "w").write("\n".join(generator()) + "\n")
            elif action == "delete":
                if os.path.isfile(file_name):
                    try:
                        os.unlink(file_name)
                    except:
                        self.log(
                            "cannot remove {}: {}".format(
                                file_name,
                                process_tools.get_except_info()
                            ),
                            logging_tools.LOG_LEVEL_ERROR
                        )

    def _show_pe_hosts(self):
        # show pe_hosts
        self._print(
            "  {} defined: {}".format(
                logging_tools.get_plural("NFS host", len(self.__node_list)),
                ", ".join(
                    [
                        "{} ({} x {:d})".format(
                            node_name,
                            self.__node_dict[node_name]["ip"],
                            self.__node_dict[node_name]["num"]
                        ) for node_name in self.__node_list
                    ]
                ) or "---"
            )
        )
        # mpi hosts
        mpi_nodes = [node_name for node_name in self.__node_list if "mpi_name" in self.__node_dict[node_name]]
        self._print(
            "  {} defined: {}".format(
                logging_tools.get_plural("MPI host", len(mpi_nodes)),
                ", ".join(
                    [
                        "{} (on {}, {} x {:d})".format(
                            self.__node_dict[node_name]["mpi_name"],
                            node_name,
                            self.__node_dict[node_name]["mpi_ip"],
                            self.__node_dict[node_name]["num"]
                        ) for node_name in mpi_nodes
                    ]
                ) or "---"
            )
        )

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

    def _send_to_rms_server(self, srv_com, **kwargs):
        _added, _content = (0, 0)
        _job_dict = {}
        for _key in global_config.keys():
            if any([_key.lower().startswith(_pf) for _pf in ["job", "pe", "sge", "task"]]):
                _added += 1
                _value = global_config[_key]
                _job_dict[_key.lower()] = _value
                if isinstance(_value, basestring) and _value.startswith("/") and os.path.isfile(_value):
                    _content += 1
                    _job_dict["{}_content".format(_key.lower())] = file(_value, "r").read()
        srv_com["config"] = _job_dict
        self.log("added {:d} config keys to srv_com ({:d} content)".format(_added, _content))
        # add all keys from global_config
        _conn = net_tools.zmq_connection(
            "job_{}".format(global_config["FULL_JOB_ID"]),
            timeout=10)
        _conn_str = "tcp://{}:{:d}".format(global_config["SGE_SERVER"], RMS_SERVER_PORT)
        s_time = time.time()
        _res = _conn.add_connection(_conn_str, srv_com)
        e_time = time.time()
        self.log("connection to {} took {}".format(_conn_str, logging_tools.get_diff_time_str(e_time - s_time)))
        if _res is not None:
            self.log(*_res.get_log_tuple())
        else:
            self.log("no result (timeout ?)", logging_tools.LOG_LEVEL_ERROR)

    def _flight_check(self, flight_type):
        s_time = time.time()
        all_ips = sorted(list(set(sum([node_stuff["ip_list"] for node_stuff in self.__node_dict.itervalues()], []))))
        all_nfs_ips = [node_stuff["ip"] for node_stuff in self.__node_dict.itervalues()]
        reach_dict = dict([(cur_ip, {"sent": len(all_nfs_ips), "ok_from": [], "error_from": []}) for cur_ip in all_ips])
        # build connection dict
        self.log(" - {} {}: {} to check".format(
            logging_tools.get_plural("node", len(self.__node_list)),
            logging_tools.compress_list(self.__node_list),
            logging_tools.get_plural("IP", len(all_ips))))
        ping_packets = global_config["PING_PACKETS"]
        ping_timeout = global_config["PING_TIMEOUT"]
        arg_str = "{} {:d} {:.2f}".format(",".join(all_ips), ping_packets, float(ping_timeout))
        self.log(
            "starting flight_check {}, ping_arg is '{}'".format(
                flight_type,
                arg_str
            )
        )
        zmq_con = net_tools.zmq_connection("job_{}".format(global_config["FULL_JOB_ID"]))
        for targ_ip in all_nfs_ips:
            srv_com = server_command.srv_command(command="ping", init_ip="{}".format(targ_ip))
            srv_com["arguments:rest"] = arg_str
            for idx, cur_str in enumerate(arg_str.strip().split()):
                srv_com["arguments:arg{:d}".format(idx)] = cur_str
            zmq_con.add_connection("tcp://{}:2001".format(targ_ip), srv_com, multi=True)
        result = zmq_con.loop()
        failure_list = []
        for targ_ip, cur_res in zip(all_nfs_ips, result):
            if cur_res is not None:
                try:
                    for p_res in cur_res.xpath(".//ns:ping_result"):
                        was_ok = int(p_res.attrib["num_received"]) > 0
                        dest_ip = p_res.attrib["target"]
                        if was_ok:
                            reach_dict[dest_ip]["ok_from"].append(targ_ip)
                        else:
                            reach_dict[dest_ip]["error_from"].append(targ_ip)
                except:
                    # fallback to old code
                    try:
                        for p_res in cur_res.xpath(None, ".//ns:ping_result"):
                            was_ok = int(p_res.attrib["num_received"]) > 0
                            dest_ip = p_res.attrib["target"]
                            if was_ok:
                                reach_dict[dest_ip]["ok_from"].append(targ_ip)
                            else:
                                reach_dict[dest_ip]["error_from"].append(targ_ip)
                    except:
                        # old host-monitor, set all results to ok
                        self.log("error getting ping-results, continuing...", logging_tools.LOG_LEVEL_WARN)
            else:
                # node not reachable
                failure_list.append(targ_ip)
        self._pprint(reach_dict, "reach_dict")
        # simple rule: add all hosts which are not reachable from any other host to failure hosts
        for key, value in reach_dict.iteritems():
            if value["error_from"]:
                failure_list.append(key)
        failure_list = sorted(list(set(failure_list)))
        if failure_list:
            self.log(
                "failure list has {}: {}".format(
                    logging_tools.get_plural("entry", len(failure_list)),
                    ", ".join(failure_list),
                )
            )
#             if failure_list and False:
#                 error_hosts = set([key for key, value in self.__node_dict.iteritems() if error_ips.intersection(set(value["ip_list"]))])
#                 self.log("%s: %s (%s: %s)" % (logging_tools.get_plural("error host", len(error_hosts)),
#                                               ", ".join(error_hosts),
#                                               logging_tools.get_plural("error IP", len(error_ips)),
#                                               ", ".join(error_ips)),
#                          logging_tools.LOG_LEVEL_ERROR,
#                          do_print=True)
#                 # disable the queues
#                 self._send_tag("disable",
#                                error="connection problem",
#                                fail_objects=["%s@%s" % (self.__opt_dict["QUEUE"], failed_host) for failed_host in error_hosts])
#                 # hold the job
#                 self._send_tag("hold",
#                                error="connection problem",
#                                fail_objects=[self.__opt_dict["FULL_JOB_ID"]])
#                 self._set_exit_code("connection problems", 1)
        else:
            self.log("failure list is empty, good")
        e_time = time.time()
        self.log("{} took {}".format(flight_type, logging_tools.get_diff_time_str(e_time - s_time)))

    def _prologue(self):
        self._send_to_rms_server(server_command.srv_command(command="job_start"))
        self._create_wrapper_script()
        yield False

    def _epilogue(self):
        self._send_to_rms_server(server_command.srv_command(command="job_end"))
        self._delete_wrapper_script()
        yield False

    def _pe_start(self):
        self.log("pe_start called")
        self._generate_hosts_file()
        self._send_to_rms_server(server_command.srv_command(command="pe_start"))
        self._write_hosts_file("save")
        self._show_pe_hosts()
        self._flight_check("preflight")
        yield False

    def _pe_end(self):
        self.log("pe_end called")
        self._generate_hosts_file()
        self._send_to_rms_server(server_command.srv_command(command="pe_end"))
        self._show_pe_hosts()
        self._write_hosts_file("keep")
        self._flight_check("postflight")
        self._flight_check("postflight")
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
        # self.write_file("aha", "/etc/hosts")
# #        for i in xrange(10):
# #            time.sleep(1)
# #            yield True
        if self.is_start_call:
            self._log_environments()
            self._log_limits()
        if self.is_proepilogue_call:
            self._write_proepi_header()
        elif self.is_pe_call:
            self._write_pe_header()
        if self.is_start_call:
            self._write_run_info()
        if "JOB_SCRIPT" in self.__env_dict:
            self.log("starting inner loop for %s" % (global_config["CALLER_NAME"]))
            if global_config["CALLER_NAME"] == "prologue":
                sub_func = self._prologue
            elif global_config["CALLER_NAME"] == "epilogue":
                sub_func = self._epilogue
            elif self.is_pe_start_call:
                sub_func = self._pe_start
            elif self.is_pe_end_call:
                sub_func = self._pe_end
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
        if self.is_proepilogue_call:
            self._write_proepi_footer()
        elif self.is_pe_call:
            self._write_pe_footer()
        self.log("took {}".format(logging_tools.get_diff_time_str(self.__end_time - self.__start_time)))
        yield None

    def close(self):
        self.__log_template.close()


class process_pool(threading_tools.process_pool):
    def __init__(self, **kwargs):
        self.dummy_call = kwargs.get("dummy_call", False)
        self.start_time = time.time()
        self.__log_cache, self.__log_template = ([], None)
        self.log("-" * SEP_LEN)
        threading_tools.process_pool.__init__(
            self,
            "main",
            zmq=True,
            blocking_loop=False,
            # zmq_debug=True,
            zmq_contexts=1,
            loop_granularity=100
        )
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context)
        self.install_signal_handlers()
        self.register_exception("int_error", self._sigint)
        self.register_exception("term_error", self._sigint)
        self._set_sge_environment()
        self._read_config()
        self._show_config()
        if not self.dummy_call:
            self._job = job_object(p_pool=self)
            self.loop_function = self._job.loop_function
            # self["return_value"] = "a"
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
            self.log(
                "cannot print '{}': {}".format(
                    what,
                    process_tools.get_except_info()
                ),
                logging_tools.LOG_LEVEL_ERROR
            )

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
        for v_name, v_src in [
            ("SGE_ROOT", "/etc/sge_root"),
            ("SGE_CELL", "/etc/sge_cell")
        ]:
            if os.path.isfile(v_src):
                v_val = file(v_src, "r").read().strip()
                self.log("Setting environment-variable '%s' to %s" % (v_name, v_val))
            else:
                self.log("Cannot assign environment-variable '%s', problems ahead ..." % (v_name),
                         logging_tools.LOG_LEVEL_ERROR)
                # sys.exit(1)
            global_config.add_config_entries([
                (v_name, configfile.str_c_var(v_val, source=v_src))])
        if "SGE_ROOT" in global_config and "SGE_CELL" in global_config:
            global_config.add_config_entries([
                ("SGE_VERSION", configfile.str_c_var("6", source="intern"))])

    def _read_config(self):
        # reading the config
        conf_dir = os.path.join(global_config["SGE_ROOT"], "3rd_party")
        if not os.path.isdir(conf_dir):
            self.log("no config_dir %s found, using defaults" % (conf_dir),
                     logging_tools.LOG_LEVEL_ERROR,
                     do_print=True)
        else:
            conf_file = os.path.join(conf_dir, CONFIG_FILE_NAME)
            if not os.path.isfile(conf_file) or os.stat(conf_file)[stat.ST_SIZE] == 0:
                if not self.dummy_call:
                    self.log(
                        "no config_file %s found, using defaults" % (conf_file),
                        logging_tools.LOG_LEVEL_ERROR,
                        do_print=True)
                    print("Copy the following lines to %s :" % (conf_file))
                    print("")
                self.show_cnf()
            else:
                global_config.add_config_entries([("CONFIG_FILE", configfile.str_c_var(conf_file))])
                self.log("reading config from %s" % (conf_file))
                global_config.parse_file(global_config["CONFIG_FILE"])

    def show_cnf(self):
        print("[global]")
        for key in [c_key for c_key in sorted(global_config.keys()) if not c_key.startswith("SGE_") and global_config.get_source(c_key) == "default"]:
            # don't write SGE_* stuff
            print("%s=%s" % (key, str(global_config[key])))
        print("")

    def loop_end(self):
        self.log("execution time was {}".format(logging_tools.get_diff_time_str(time.time() - self.start_time)))

    def loop_post(self):
        self._job.close()
        self.__log_template.close()


if NEW_CODE:
    global_config = configfile.get_global_config(process_tools.get_programm_name(), single_process=True)
else:
    global_config = configfile.get_global_config(process_tools.get_programm_name())


def zmq_main_code():
    # brand new 0MQ-based code
    global_config.add_config_entries(
        [
            ("DEBUG", configfile.bool_c_var(False, help_string="enable debug mode [%(default)s]", short_options="d", only_commandline=True)),
            ("LOG_DESTINATION", configfile.str_c_var("uds:/var/lib/logging-server/py_log_zmq")),
            ("LOG_NAME", configfile.str_c_var("proepilogue")),
            ("MAX_RUN_TIME", configfile.int_c_var(60)),
            ("SEP_LEN", configfile.int_c_var(80)),
            ("HAS_MPI_INTERFACE", configfile.bool_c_var(True)),
            ("MPI_POSTFIX", configfile.str_c_var("mp")),
            ("BRUTAL_CLEAR_MACHINES", configfile.bool_c_var(False)),
            ("SIMULTANEOUS_PINGS", configfile.int_c_var(128)),
            ("PING_PACKETS", configfile.int_c_var(5)),
            ("PING_TIMEOUT", configfile.float_c_var(5.0)),
            ("MIN_KILL_UID", configfile.int_c_var(110)),
            ("UMOUNT_CALL", configfile.bool_c_var(True)),
        ]
    )
    global_config.parse_file()
    if NEW_CODE:
        options = global_config.handle_commandline(
            add_writeback_option=True,
            positional_arguments=True,
            positional_arguments_optional=True,
        )
    else:
        options = global_config.handle_commandline(
            add_writeback_option=True,
            positional_arguments=True,
        )
    _exit = False
    if len(options.arguments) in [5, 8]:
        global_config.add_config_entries(
            [
                ("HOST_LONG", configfile.str_c_var(options.arguments[0], source="cmdline")),
                ("JOB_OWNER", configfile.str_c_var(options.arguments[1], source="cmdline")),
                ("JOB_ID", configfile.str_c_var(options.arguments[2], source="cmdline")),
                ("JOB_NAME", configfile.str_c_var(options.arguments[3], source="cmdline")),
                ("JOB_QUEUE", configfile.str_c_var(options.arguments[4], source="cmdline")),
            ]
        )
        if len(options.arguments) == 8:
            global_config.add_config_entries(
                [
                    ("PE_HOSTFILE", configfile.str_c_var(options.arguments[5], source="cmdline")),
                    ("PE", configfile.str_c_var(options.arguments[6], source="cmdline")),
                    ("PE_SLOTS", configfile.str_c_var(options.arguments[7], source="cmdline"))
                ]
            )
    elif len(options.arguments) == 0:
        process_pool(dummy_call=True)
        _exit = True
    else:
        print "Unable to determine execution mode for %s, exiting (%d args)" % (
            global_config.name(),
            len(options.arguments))
        _exit = True
    if not _exit:
        cf_time = time.localtime(os.stat(configfile.__file__.replace(".pyc", ".py").replace(".pyo", ".py"))[stat.ST_MTIME])  # @UndefinedVariable
        if (cf_time.tm_year, cf_time.tm_mon, cf_time.tm_mday) < (2012, 5, 1):
            print "your python-modules-base are too old, please upgrade ({:d}, {:d}, {:d})".format(cf_time.tm_year, cf_time.tm_mon, cf_time.tm_mday)
            return 0
        else:
            # add more entries
            global_config.add_config_entries(
                [
                    ("HOST_SHORT", configfile.str_c_var(global_config["HOST_LONG"].split(".")[0], source="cmdline")),
                    ("CALLER_NAME", configfile.str_c_var(global_config.name(), source="cmdline")),
                    ("HOST_IP", configfile.str_c_var("unknown", source="cmdline")),
                ]
            )
            return process_pool().loop()
    else:
        return -1

if __name__ == "__main__":
    sys.exit(zmq_main_code())
