#!/usr/bin/python3-init -Ot
#
# -*- coding: utf-8 -*-
#
# Copyright (C) 2001-2008,2010-2017 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw-server-server
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
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
sys.path = [
    entry for entry in sys.path if entry.startswith("/opt")
]

import argparse
import grp
import os
import pprint
import re
import pwd
import socket
import stat
import time
try:
    from initat.tools.configfile import StringConfigVar, IntegerConfigVar, BoolConfigVar
except:
    from initat.tools.configfile import str_c_var, int_c_var, bool_c_var
    StringConfigVar = str_c_var
    IntegerConfigVar = int_c_var
    BoolConfigVar = bool_c_var

from initat.tools import threading_tools, configfile, logging_tools, net_tools, \
    process_tools, server_command
from initat.icsw.service.instance import InstanceXML
HM_PORT = InstanceXML(quiet=True).get_port_dict("host-monitoring", command=True)


SEP_LEN = 70
LOCAL_IP = "127.0.0.1"
# PROFILE_PREFIX = ".mon"
CONFIG_FILE_NAME = "proepilogue.conf"
RMS_SERVER_PORT = 8009


SPECIAL_SCRIPT_NAMES = {"INTERACTIVE", "QLOGIN", "QRSH", "QRLOGIN"}


if hasattr(net_tools, "ZMQConnection"):
    ZMQConnection = net_tools.ZMQConnection
else:
    ZMQConnection = net_tools.zmq_connection


def sec_to_str(in_sec):
    diff_d = int(in_sec / (3600 * 24))
    dt = in_sec - 3600 * 24 * diff_d
    diff_h = int(dt / 3600)
    dt -= 3600 * diff_h
    diff_m = int(dt / 60)
    dt -= diff_m * 60
    out_f = "%2d:%02d:%02d:%02d" % (diff_d, diff_h, diff_m, dt)
    return out_f


def parse_file(global_config, file_name, section="global"):
    act_section = "global"
    pf1 = re.compile("^(?P<key>\S+)\s*=\s*(?P<value>.+)\s*$")
    pf2 = re.compile("^(?P<key>\S+)\s+(?P<value>.+)\s*$")
    sec_re = re.compile("^\[(?P<section>\S+)\]$")
    if os.path.isfile(file_name):
        try:
            lines = [line.strip() for line in open(file_name, "r").read().split("\n") if line.strip() and not line.strip().startswith("#")]
        except:
            global_config.log(
                "Error while reading file {}: {}".format(
                    file_name,
                    process_tools.get_except_info()
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
        else:
            for line in lines:
                sec_m = sec_re.match(line)
                if sec_m:
                    act_section = sec_m.group("section")
                else:
                    for mo in [pf1, pf2]:
                        ma = mo.match(line)
                        if ma:
                            break
                    if act_section == section:
                        if ma:
                            key, value = (ma.group("key"), ma.group("value"))
                            try:
                                cur_type = global_config.get_type(key)
                            except KeyError:
                                global_config.log(
                                    "Error: key {} not defined in dictionary for get_type".format(
                                        key
                                    ),
                                    logging_tools.LOG_LEVEL_ERROR
                                )
                            else:
                                # interpret using eval
                                if cur_type == "s":
                                    if value not in ["\"\""]:
                                        if value[0] == value[-1] and value[0] in ['"', "'"]:
                                            pass
                                        else:
                                            # escape strings
                                            value = "\"{}\"".format(value)
                                try:
                                    global_config[key] = (
                                        eval("{}".format(value)),
                                        "{}, sec {}".format(file_name, act_section)
                                    )
                                except KeyError:
                                    global_config.log(
                                        "Error: key {} not defined in dictionary".format(
                                            key
                                        ),
                                        logging_tools.LOG_LEVEL_ERROR
                                    )
                        else:
                            global_config.log(
                                "Error parsing line '{}'".format(
                                    str(line)
                                ),
                                logging_tools.LOG_LEVEL_ERROR
                            )
    else:
        global_config.log(
            "Cannot find file {}".format(
                file_name
            ),
            logging_tools.LOG_LEVEL_ERROR
        )


class RMSJob(object):
    def __init__(self, p_pool):
        self.p_pool = p_pool
        self.__log_dir = time.strftime("%Y/%m/%d/{}{}").format(
            global_config["JOB_ID"],
            ".{}".format(os.environ["SGE_TASK_ID"]) if os.environ.get("SGE_TASK_ID", "undefined") != "undefined" else ""
        )
        self.__log_name = "{}".format(self.__log_dir)
        self.__log_template = logging_tools.get_logger(
            "{}.{}/log".format(
                global_config["LOG_NAME"],
                self.__log_name.replace(".", "\.")
            ),
            global_config["LOG_DESTINATION"],
            zmq=True,
            context=self.p_pool.zmq_context
        )
        self._init_exit_code()

    def _init_exit_code(self):
        self.p_pool["return_value"] = 0

    def _set_exit_code(self, cause, exit_code):
        self.p_pool["return_value"] = exit_code
        self.log(
            "setting exit_code to {:d} because of {}".format(
                exit_code,
                cause
            ),
            logging_tools.LOG_LEVEL_ERROR
        )

    def log(self, what, lev=logging_tools.LOG_LEVEL_OK, **kwargs):
        self.__log_template.log(lev, what)
        if kwargs.get("do_print", False):
            self._print(
                "{}{}".format(
                    "[{}] ".format(
                        logging_tools.get_log_level_str(lev)
                    ) if lev != logging_tools.LOG_LEVEL_OK else "",
                    what
                )
            )
        if lev != logging_tools.LOG_LEVEL_OK or kwargs.get("pool", False):
            self.p_pool.log(what, lev)

    def _print(self, what):
        try:
            print(what)
        except:
            self.log(
                "cannot print '{}': {}".format(
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
            self.log(
                "refuse to create wrapper script {}".format(dst_file),
                logging_tools.LOG_LEVEL_ERROR
            )
            return
        self.log(
            "Creating wrapper-script ({} for {})".format(
                dst_file,
                src_file
            )
        )
        shell_path, shell_start_mode = (
            self.__env_int_dict.get("shell_path", "/bin/bash"),
            self.__env_int_dict.get("shell_start_mode", "posix_compliant")
        )
        # cluster_queue_name = global_config["JOB_QUEUE"]
        self.log(
            "shell_path is '{}', shell_start_mode is '{}'".format(
                shell_path,
                shell_start_mode
            )
        )
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
        open(dst_file, "w").write("\n".join(df_lines))
        open(var_file, "w").write("#!/bin/bash\n")
        self.write_file("wrapper_script", df_lines)
        os.chmod(dst_file, 0o755)
        os.chmod(var_file, 0o755)
        os.chown(var_file, global_config["UID"], global_config["GID"])

    def _delete_wrapper_script(self):
        src_file = self.__env_dict["JOB_SCRIPT"]
        dst_file = self._get_wrapper_script_name()
        if not dst_file.startswith("/"):
            self.log(
                "refuse to delete wrapper script {}".format(dst_file),
                logging_tools.LOG_LEVEL_ERROR
            )
            return
        self.log(
            "Deleting wrapper-script ({} for {})".format(
                dst_file,
                src_file
            )
        )
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
            self.log(
                "no such file: {}".format(dst_file),
                logging_tools.LOG_LEVEL_ERROR
            )

    def _add_script_var(self, key, value):
        var_file = self._get_var_script_name()
        self.log(
            "adding variable ({}={}) to var_file {}".format(
                key,
                value,
                var_file
            )
        )
        try:
            open(var_file, "a").write("export {}={}\n".format(key, value))
        except:
            self.log(
                "error writing to {}: {}".format(
                    var_file,
                    process_tools.get_except_info()
                ),
                logging_tools.LOG_LEVEL_ERROR
            )

    @property
    def is_start_call(self):
        return global_config["CALLER_NAME"] in [
            "prologue",
            "lamstart",
            "mvapich2start",
            "pvmstart",
            "pestart"
        ]

    @property
    def is_pe_start_call(self):
        return global_config["CALLER_NAME"] in [
            "lamstart",
            "pestart",
            "pvmstart",
            "mvapich2start"
        ]

    @property
    def is_pe_end_call(self):
        return global_config["CALLER_NAME"] in [
            "lamstop",
            "pestop",
            "pvmstop",
            "mvapich2stop"
        ]

    @property
    def is_proepilogue_call(self):
        return global_config["CALLER_NAME"] in [
            "prologue",
            "epilogue"
        ]

    @property
    def is_pe_call(self):
        return global_config["CALLER_NAME"] in [
            "lamstart",
            "pestart",
            "pvmstart",
            "mvapich2start",
            "lamstop",
            "pestop",
            "pvmstop",
            "mvapich2stop"
        ]

    def _show_config(self):
        try:
            for log_line, log_level in global_config.get_log():
                self.log("Config info : [{:d}] {}".format(log_level, log_line))
        except:
            self.log(
                "error showing configfile log, old configfile ? ({})".format(process_tools.get_except_info()),
                logging_tools.LOG_LEVEL_ERROR
            )
        conf_info = global_config.get_config_info()
        self.log("Found {}:".format(logging_tools.get_plural("valid configline", len(conf_info))))
        for conf in conf_info:
            self.log("Config : {}".format(conf))

    def write_file(self, name, content, **args):
        ss_time = time.time()
        logger = logging_tools.get_logger(
            "{}.{}/{}".format(
                global_config["LOG_NAME"],
                self.__log_dir.replace(".", "\."),
                name
            ),
            global_config["LOG_DESTINATION"],
            zmq=True,
            context=self.p_pool.zmq_context
        )
        if isinstance(content, str) and content.startswith("/"):
            # content is a filename
            content = open(content, "r").read().split("\n")
        if isinstance(content, str):
            content = content.split("\n")
        log_str = "content '{}', {}:".format(
            name,
            logging_tools.get_plural("line", len(content))
        )
        logger.log(logging_tools.LOG_LEVEL_OK, log_str)
        if args.get("linenumbers", True):
            for line_num, line in zip(range(len(content)), content):
                log_str = "{:3d} {}".format(line_num + 1, line)
                logger.log(logging_tools.LOG_LEVEL_OK, log_str)
        else:
            for line in content:
                logger.log(logging_tools.LOG_LEVEL_OK, line)
        se_time = time.time()
        self.log(
            "storing content to file {} ({}) in {}".format(
                name,
                logging_tools.get_plural("line", len(content)),
                logging_tools.get_diff_time_str(se_time - ss_time)
            )
        )
        logger.close()

    def _copy_environments(self):
        self.__env_dict = {key: str(os.environ[key]) for key in list(os.environ.keys())}
        if "SGE_JOB_SPOOL_DIR" in self.__env_dict:
            self.__env_int_dict = {
                key: value for key, value in [
                    line.split("=", 1) for line in open(
                        os.path.join(
                            self.__env_dict["SGE_JOB_SPOOL_DIR"],
                            "config"
                        ),
                        "r"
                    ).read().strip().split("\n") if line.count("=")
                ]
            }
        else:
            self.__env_int_dict = {}

    def _parse_server_addresses(self):
        for src_file, key, default in [
            ("/etc/motherserver", "MOTHER_SERVER", "localhost"),
            ("/etc/sge_server", "SGE_SERVER", "localhost")
        ]:
            if os.path.isfile(src_file):
                try:
                    act_val = open(src_file, "r").read().split()[0]
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
            global_config.add_config_entries([(key, StringConfigVar(act_val, source=src_file))])

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
        global_config.add_config_entries([("HOST_IP", StringConfigVar(host_ip, source="env"))])

    def _parse_job_script(self):
        self.script_is_special = False
        if "JOB_SCRIPT" in os.environ:
            script_file = os.environ["JOB_SCRIPT"]
            if script_file in SPECIAL_SCRIPT_NAMES:
                self.log("script_file {} is a special scriptfile".format(script_file))
                self.script_is_special = True
            else:
                try:
                    lines = [line.strip() for line in open(script_file, "r").read().split("\n")]
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
                        s_list = logging_tools.NewFormList()
                    else:
                        s_list = None
                    num_lines, num_sge, num_init = (len(lines), 0, 0)
                    init_dict = {}
                    for line, line_num in zip(lines, range(len(lines))):
                        if s_list is not None:
                            s_list.append(
                                [
                                    logging_tools.form_entry(line_num + 1, header="line"),
                                    logging_tools.form_entry(line, header="content")
                                ]
                            )
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
                            self.log("found #init-line '{}'".format(line))
                            if line_parts:
                                for key, value in [x for x in line_parts if len(x) == 2]:
                                    key, value = (key.strip().upper(), value.strip().lower())
                                    if key and value:
                                        init_dict[key] = value
                                        self.log("recognised init option '{}' (value '{}')".format(key, value))
                                        global_config.add_config_entries([(key, StringConfigVar(value, source="jobscript"))])
                                for key in [x[0].strip().upper() for x in line_parts if len(x) == 1]:
                                    init_dict[key] = True
                                    self.log("recognised init option '{}' (value '{}')".format(key, True))
                                    global_config.add_config_entries([(key, BoolConfigVar(True, source="jobscript"))])
                    self.log(
                        "Scriptfile '{}' has {} ({} and {})".format(
                            script_file,
                            logging_tools.get_plural("line", num_lines),
                            logging_tools.get_plural("SGE related line", num_sge),
                            logging_tools.get_plural("init.at related line", num_init)
                        )
                    )
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
            global_config.add_config_entries([("PE", StringConfigVar(os.environ["PE"], source="env"))])
        else:
            global_config.add_config_entries([("PE", StringConfigVar("", source="env"))])
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
                ("TASK_ID", IntegerConfigVar(task_id, source="env")),
                ("FULL_JOB_ID", StringConfigVar(full_job_id, source="env"))
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
                ("GROUP", StringConfigVar(group, source="env")),
                ("UID", IntegerConfigVar(uid, source="env")),
                ("GID", IntegerConfigVar(gid, source="env"))
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
        self.log(
            "writing {}-header for job {}, {}".format(
                global_config["CALLER_NAME"],
                global_config["FULL_JOB_ID"],
                self.get_owner_str()
            )
        )
        self.log(
            "Jobname is '{}' in queue '{}'".format(
                global_config["JOB_NAME"],
                global_config["JOB_QUEUE"]
            ),
            do_print=True
        )

    def _write_proepi_footer(self):
        sep_str = "-" * global_config["SEP_LEN"]
        self.log(
            "writing {}-footer for job {}, return value is {:d} ({})".format(
                global_config["CALLER_NAME"],
                global_config["FULL_JOB_ID"],
                self.p_pool["return_value"],
                self.get_stat_str(self.p_pool["return_value"])
            )
        )
        spent_time = logging_tools.get_diff_time_str(self.__end_time - self.__start_time)
        self._print(
            "{} finished for job {}, status {}, spent {}".format(
                global_config["CALLER_NAME"],
                global_config["FULL_JOB_ID"],
                self.get_stat_str(self.p_pool["return_value"]),
                spent_time
            )
        )
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
        self._print(
            "Starting {} for job {}, {} at {}".format(
                global_config["CALLER_NAME"],
                global_config["FULL_JOB_ID"],
                self.get_owner_str(),
                time.ctime(time.time())
            )
        )
        self.log(
            "writing {}-header for job {}, {}".format(
                global_config["CALLER_NAME"],
                global_config["FULL_JOB_ID"],
                self.get_owner_str()
            )
        )

    def _write_pe_footer(self):
        sep_str = "-" * global_config["SEP_LEN"]
        self.log(
            "writing {}-footer for job {}, return value is {:d} ({})".format(
                global_config["CALLER_NAME"],
                global_config["FULL_JOB_ID"],
                self.p_pool["return_value"],
                self.get_stat_str(self.p_pool["return_value"])
            )
        )
        spent_time = logging_tools.get_diff_time_str(self.__end_time - self.__start_time)
        self._print(
            "{} finished for job {}, status {}, spent {}".format(
                global_config["CALLER_NAME"],
                global_config["FULL_JOB_ID"],
                self.get_stat_str(self.p_pool["return_value"]),
                spent_time
            )
        )
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
        out_list = logging_tools.NewFormList()
        for key in sorted(self.__env_dict.keys()):
            out_list.append(
                [
                    logging_tools.form_entry(key, header="Key"),
                    logging_tools.form_entry(self.__env_dict[key], header="Value")
                ]
            )
        try:
            self.write_file("env_{}".format(global_config["CALLER_NAME"]), str(out_list).split("\n"))
        except:
            self.log("error creating env_ file: {}".format(process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
        out_list = logging_tools.NewFormList()
        for key in sorted(self.__env_int_dict.keys()):
            out_list.append(
                [
                    logging_tools.form_entry(key, header="Key"),
                    logging_tools.form_entry(self.__env_int_dict[key], header="Value")
                ]
            )
        try:
            self.write_file("env_int_{}".format(global_config["CALLER_NAME"]), str(out_list).split("\n"))
        except:
            self.log("error creating env_int_ file: {}".format(process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)

    def _read_config(self):
        if "CONFIG_FILE" in global_config:
            sections = [
                "queue_{}".format(global_config["JOB_QUEUE"]),
                "node_{}".format(global_config["HOST_SHORT"])
            ]
            if self.is_pe_call:
                sections.append("pe_{}".format(global_config["PE"]))
                sections.append(
                    "queue_{}_pe_{}".format(
                        global_config["JOB_QUEUE"],
                        global_config["PE"]
                    )
                )
            self.log(
                "scanning configfile {} for {}: {}".format(
                    global_config["CONFIG_FILE"],
                    logging_tools.get_plural("section", len(sections)),
                    ", ".join(sections)
                )
            )
            for section in sections:
                try:
                    parse_file(
                        global_config,
                        global_config["CONFIG_FILE"],
                        section=section
                    )
                except:
                    self.log(
                        "error scanning for section {}: {}".format(
                            section,
                            process_tools.get_except_info()
                        ),
                        logging_tools.LOG_LEVEL_ERROR
                    )
            try:
                for line, log_level in global_config.get_log(clear=True):
                    self.log(line, log_level)
            except:
                self.log(
                    "error getting config_log: {}".format(process_tools.get_except_info()),
                    logging_tools.LOG_LEVEL_ERROR
                )
        else:
            self.log(
                "no key CONFIG_FILE in glob_config, strange ...",
                logging_tools.LOG_LEVEL_WARN
            )

    def _log_resources(self):
        res_used = {}
        jsd = os.environ.get("SGE_JOB_SPOOL_DIR", "")
        if jsd:
            usage_file = os.path.join(jsd, "usage")
            if os.path.isfile(usage_file):
                try:
                    ufl = dict([[part.strip() for part in line.strip().split("=", 1)] for line in open(usage_file, "r").read().split("\n") if line.count("=")])
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
            out_list = logging_tools.NewFormList()
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
                        ext_str = " ({})".format(ext_str) if ext_str else ""
                out_list.append(
                    [
                        logging_tools.form_entry(key, header="key"),
                        logging_tools.form_entry(value, header="value"),
                        logging_tools.form_entry(ext_str, header="info")
                    ]
                )
                log_res.append("{}:{}{}".format(key, value, ext_str))
            self._print(
                "\n".join(
                    [
                        "  {}".format(line) for line in str(out_list).split("\n")
                    ]
                )
            )
            self.log(
                "reported {}: {}".format(
                    logging_tools.get_plural("resource", len(log_res)),
                    ", ".join(log_res)
                )
            )
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
            res_list = logging_tools.NewFormList()
            for key in res_keys:
                val = r_dict[key]
                if isinstance(val, str):
                    info_str = val
                elif isinstance(val, tuple):
                    info_str = "{:8d} (hard), {:8d} (soft)".format(val[0], val[1])
                else:
                    info_str = "None (error?)"
                res_list.append(
                    [
                        logging_tools.form_entry(key, header="key"),
                        logging_tools.form_entry(info_str, header="value")
                    ]
                )
            for _line in str(res_list).split("\n"):
                self.log(_line)
            self.write_file(
                "limits_{}".format(
                    global_config["CALLER_NAME"]
                ),
                str(res_list).split("\n")
            )
        else:
            self.log("no limits found, strange ...", logging_tools.LOG_LEVEL_WARN)

    def _generate_localhost_hosts_file(self):
        self.__node_list, self.__node_dict = (
            ["localhost"],
            {
                "localhost": {
                    "ip": LOCAL_IP,
                    "ip_list": [LOCAL_IP],
                }
            }
        )

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
                node_list = [
                    line.strip() for line in open(orig_file, "r").readlines() if line.strip()
                ]
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
                self.__node_list = [
                    node_name.split(".")[0] for node_name in [line.split()[0] for line in node_list]
                ]
                try:
                    node_dict = {
                        node_name.split(".")[0]: {
                            "num": int(node_num)
                        } for node_name, node_num in [line.split()[0:2] for line in node_list]
                    }
                except:
                    self.log(
                        "cannot interpret node_file {}: {}".format(
                            orig_file,
                            process_tools.get_except_info()
                        ),
                        logging_tools.LOG_LEVEL_ERROR
                    )
                    node_dict = {
                        node_name.split(".")[0]: {
                            "num": 1
                        } for node_name in node_list
                    }
        else:
            self.log(
                "No node_file name '{}' found".format(orig_file),
                logging_tools.LOG_LEVEL_ERROR
            )
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
            self.log(
                "using mpi_postfix '{}' for PE '{}' on queue '{}'".format(
                    mpi_postfix,
                    global_config["PE"],
                    global_config["JOB_QUEUE"]
                )
            )
            for key, value in node_dict.items():
                value["mpi_name"] = "{}{}".format(key, mpi_postfix)
        # resolve names
        for node_name in self.__node_list:
            node_stuff = node_dict[node_name]
            try:
                node_ip = socket.gethostbyname(node_name)
            except:
                self.log(
                    "error resolving {} to IP: {}".format(
                        node_name,
                        process_tools.get_except_info()
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
                node_ip = node_name
            node_stuff["ip"] = node_ip
            node_stuff["ip_list"] = [node_ip]
            if "mpi_name" in node_stuff:
                try:
                    mpi_ip = socket.gethostbyname(node_stuff["mpi_name"])
                except:
                    self.log(
                        "error resolving {} to IP: {}".format(
                            node_stuff["mpi_name"],
                            process_tools.get_except_info()
                        ),
                        logging_tools.LOG_LEVEL_ERROR
                    )
                    mpi_ip = node_stuff["mpi_name"]
                node_stuff["mpi_ip"] = mpi_ip
                node_stuff["ip_list"].append(mpi_ip)
        self.__node_dict = node_dict
        self._pprint(self.__node_list, "node_list")
        self._pprint(self.__node_dict, "node_dict")

    def _pprint(self, in_dict, in_name):
        content = pprint.PrettyPrinter(indent=1, width=10).pformat(in_dict)
        self.log("content of {}".format(in_name))
        for line in content.split("\n"):
            self.log(" - {}".format(line))

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
            global_config.add_config_entries([(var_name, StringConfigVar(file_name))])
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
        return ["{} cpu={:d}".format(self._get_mpi_name(node_name), self.__node_dict[node_name]["num"]) for node_name in self.__node_list]

    def _whf_wslot(self):
        return ["{} max_slots={:d}".format(self._get_mpi_name(node_name), self.__node_dict[node_name]["num"]) for node_name in self.__node_list]

    def _whf_sge(self):
        # like PE_HOSTFILE just with the Parallel Interfaces
        return [
            "{} {:d} {}@{} <NULL>".format(
                self._get_mpi_name(node_name),
                self.__node_dict[node_name]["num"],
                global_config["JOB_QUEUE"],
                node_name
            ) for node_name in self.__node_list
        ]

    def _send_to_rms_server(self, srv_com, **kwargs):
        _added, _content = (0, 0)
        _job_dict = {}
        for _key in list(global_config.keys()):
            if any([_key.lower().startswith(_pf) for _pf in ["job", "pe", "sge", "task"]]):
                _added += 1
                _value = global_config[_key]
                _job_dict[_key.lower()] = _value
                if isinstance(_value, str) and _value.startswith("/") and os.path.isfile(_value):
                    _content += 1
                    _job_dict["{}_content".format(_key.lower())] = open(_value, "r").read()
        srv_com["config"] = _job_dict
        self.log("added {:d} config keys to srv_com ({:d} content)".format(_added, _content))
        # add all keys from global_config
        _conn = ZMQConnection(
            "job_{}".format(global_config["FULL_JOB_ID"]),
            timeout=10
        )
        _conn_str = "tcp://{}:{:d}".format(global_config["SGE_SERVER"], RMS_SERVER_PORT)
        s_time = time.time()
        # we only send via a DEALER socket, no result required
        _conn.add_connection(_conn_str, srv_com, multi=True)
        e_time = time.time()
        self.log("connection to {} took {}".format(_conn_str, logging_tools.get_diff_time_str(e_time - s_time)))
        # if _res is not None:
        #     self.log(*_res.get_log_tuple())
        # else:
        #    self.log(
        #        "no result from {}, command was {} (timeout ?)".format(
        #            _conn_str,
        #            srv_com["*command"],
        #        ),
        #        logging_tools.LOG_LEVEL_ERROR
        #    )

    def _flight_check(self, flight_type):
        s_time = time.time()
        all_ips = sorted(list(set(sum([node_stuff["ip_list"] for node_stuff in self.__node_dict.values()], []))))
        all_nfs_ips = [node_stuff["ip"] for node_stuff in self.__node_dict.values()]
        reach_dict = {
            cur_ip: {
                "sent": len(all_nfs_ips),
                "ok_from": [],
                "error_from": []
            } for cur_ip in all_ips
        }
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
        zmq_con = ZMQConnection("job_{}".format(global_config["FULL_JOB_ID"]))
        for targ_ip in all_nfs_ips:
            srv_com = server_command.srv_command(command="ping", init_ip="{}".format(targ_ip))
            srv_com["arguments:rest"] = arg_str
            for idx, cur_str in enumerate(arg_str.strip().split()):
                srv_com["arguments:arg{:d}".format(idx)] = cur_str
            zmq_con.add_connection("tcp://{}:{:d}".format(targ_ip, HM_PORT), srv_com, multi=True)
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
        for key, value in reach_dict.items():
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
        else:
            self.log("failure list is empty, good")
        if global_config["REMOVE_IPCS"]:
            self.log(
                "sending ipckill to {} ({})".format(
                    logging_tools.get_plural("IP", len(all_nfs_ips)),
                    ", ".join(all_nfs_ips),
                )
            )
            # create a new zmq connection object
            zmq_con2 = ZMQConnection("job_{}".format(global_config["FULL_JOB_ID"]))
            for targ_ip in all_nfs_ips:
                srv_com = server_command.srv_command(command="ipckill")
                arg_str = "--min-uid {:d}".format(global_config["MIN_KILL_UID"])
                srv_com["arguments:rest"] = arg_str
                for idx, cur_str in enumerate(arg_str.strip().split()):
                    srv_com["arguments:arg{:d}".format(idx)] = cur_str
                zmq_con2.add_connection("tcp://{}:{:d}".format(targ_ip, HM_PORT), srv_com, multi=True)
            result = zmq_con2.loop()
            for _ip, _res in zip(all_nfs_ips, result):
                if _res is None:
                    self.log("got empty result from {}".format(_ip), logging_tools.LOG_LEVEL_ERROR)
                else:
                    _ret_str, _ret_state = _res.get_log_tuple()
                    self.log("from {} we got {}".format(_ip, _ret_str), _ret_state)
        e_time = time.time()
        self.log("{} took {}".format(flight_type, logging_tools.get_diff_time_str(e_time - s_time)))

    def _prologue(self):
        self._send_to_rms_server(server_command.srv_command(command="job_start"))
        if not self.script_is_special:
            self._create_wrapper_script()
        self._generate_localhost_hosts_file()
        self._flight_check("preflight")
        yield False

    def _epilogue(self):
        self._send_to_rms_server(server_command.srv_command(command="job_end"))
        if not self.script_is_special:
            self._delete_wrapper_script()
        self._generate_localhost_hosts_file()
        self._flight_check("postflight")
        yield False

    def _pe_start(self):
        self.log("pe_start called")
        self._generate_hosts_file()
        self._send_to_rms_server(server_command.srv_command(command="pe_start"))
        self._write_hosts_file("save")
        self._show_pe_hosts()
        self._flight_check("preflight/PE")
        yield False

    def _pe_end(self):
        self.log("pe_end called")
        self._generate_hosts_file()
        self._send_to_rms_server(server_command.srv_command(command="pe_end"))
        self._show_pe_hosts()
        self._write_hosts_file("keep")
        # not working for Liebherr, check
        # self._flight_check("postflight/PE")
        self._write_hosts_file("delete")
        yield False

    def loop_function(self):
        self.__start_time = time.time()
        self.log("log_name is {}/{}".format(global_config["LOG_NAME"], self.__log_name), pool=True)
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
            self.log("starting inner loop for {}".format(global_config["CALLER_NAME"]))
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
                self.log(
                    "unknown runmode {}".format(global_config["CALLER_NAME"]),
                    logging_tools.LOG_LEVEL_ERROR
                )
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


class ProcessPool(threading_tools.icswProcessPool):
    def __init__(self, **kwargs):
        self.dummy_call = kwargs.get("dummy_call", False)
        self.start_time = time.time()
        self.__log_cache, self.__log_template = ([], None)
        self.log("-" * SEP_LEN)
        threading_tools.icswProcessPool.__init__(
            self,
            "main",
            zmq=True,
            blocking_loop=False,
            # zmq_debug=True,
            zmq_contexts=1,
            loop_granularity=100
        )
        self.__log_template = logging_tools.get_logger(
            global_config["LOG_NAME"],
            global_config["LOG_DESTINATION"],
            zmq=True,
            context=self.zmq_context
        )
        self.install_signal_handlers()
        self.register_exception("int_error", self._sigint)
        self.register_exception("term_error", self._sigint)
        self._set_sge_environment()
        self._read_config()
        self._show_config()
        if not self.dummy_call:
            self._job = RMSJob(p_pool=self)
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
            self._print(
                "{}{}".format(
                    "[{}]".format(
                        logging_tools.get_log_level_str(lev)
                    ) if lev != logging_tools.LOG_LEVEL_OK else "",
                    what
                )
            )

    def _print(self, what):
        try:
            print(what)
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
                self.log("Config info : [{:d}] {}".format(log_level, log_line))
        except:
            self.log(
                "error showing configfile log, old configfile ? ({})".format(
                    process_tools.get_except_info()
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
        conf_info = global_config.get_config_info()
        self.log("Found {}:".format(logging_tools.get_plural("valid configline", len(conf_info))))
        for conf in conf_info:
            self.log("Config : {}".format(conf))

    def _set_sge_environment(self):
        for v_name, v_src in [
            ("SGE_ROOT", "/etc/sge_root"),
            ("SGE_CELL", "/etc/sge_cell")
        ]:
            if os.path.isfile(v_src):
                v_val = open(v_src, "r").read().strip()
                self.log("Setting environment-variable '{}' to {}".format(v_name, v_val))
            else:
                self.log(
                    "Cannot assign environment-variable '{}', problems ahead ...".format(v_name),
                    logging_tools.LOG_LEVEL_ERROR
                )
                # sys.exit(1)
            global_config.add_config_entries([
                (v_name, StringConfigVar(v_val, source=v_src))])
        if "SGE_ROOT" in global_config and "SGE_CELL" in global_config:
            global_config.add_config_entries([
                ("SGE_VERSION", StringConfigVar("6", source="intern"))])

    def _read_config(self):
        # reading the config
        conf_dir = os.path.join(global_config["SGE_ROOT"], "3rd_party")
        if not os.path.isdir(conf_dir):
            self.log(
                "no config_dir {} found, using defaults".format(conf_dir),
                logging_tools.LOG_LEVEL_ERROR,
                do_print=True
            )
        else:
            conf_file = os.path.join(conf_dir, CONFIG_FILE_NAME)
            if not os.path.isfile(conf_file) or os.stat(conf_file)[stat.ST_SIZE] == 0:
                if not self.dummy_call:
                    self.log(
                        "no config_file {} found, using defaults".format(conf_file),
                        logging_tools.LOG_LEVEL_ERROR,
                        do_print=True
                    )
                    print("Copy the following lines to {} :".format(conf_file))
                    print("")
                self.show_cnf()
            else:
                global_config.add_config_entries([("CONFIG_FILE", StringConfigVar(conf_file))])
                self.log("reading config from {}".format(conf_file))
                parse_file(global_config, global_config["CONFIG_FILE"])

    def show_cnf(self):
        print("[global]")
        for key in [c_key for c_key in sorted(global_config.keys()) if not c_key.startswith("SGE_") and global_config.get_source(c_key) == "default"]:
            # don't write SGE_* stuff
            print("{}={}".format(key, str(global_config[key])))
        print("")

    def loop_end(self):
        self.log("execution time was {}".format(logging_tools.get_diff_time_str(time.time() - self.start_time)))

    def loop_post(self):
        self._job.close()
        self.__log_template.close()


try:
    global_config = configfile.get_global_config(process_tools.get_programm_name(), single_process_mode=True)
except:
    # for old code
    global_config = configfile.get_global_config(process_tools.get_programm_name(), single_process=True)


def main_code():
    # brand new 0MQ-based code
    try:
        from initat.logging_server.constants import icswLogHandleTypes, get_log_path
        LPATH = get_log_path(icswLogHandleTypes.log_py)
    except:
        LPATH = "ipc:///var/lib/logging-server/py_log_zmq"
    global_config.add_config_entries(
        [
            ("LOG_DESTINATION", StringConfigVar("uds:{}".format(LPATH))),
            ("LOG_NAME", StringConfigVar("proepilogue")),
            ("MAX_RUN_TIME", IntegerConfigVar(60)),
            ("SEP_LEN", IntegerConfigVar(80)),
            ("HAS_MPI_INTERFACE", BoolConfigVar(True)),
            ("MPI_POSTFIX", StringConfigVar("mp")),
            ("REMOVE_IPCS", BoolConfigVar(False)),
            ("SIMULTANEOUS_PINGS", IntegerConfigVar(128)),
            ("PING_PACKETS", IntegerConfigVar(5)),
            ("PING_TIMEOUT", FloatConfigVar(5.0)),
            ("MIN_KILL_UID", IntegerConfigVar(110)),
            ("UMOUNT_CALL", BoolConfigVar(True)),
        ]
    )

    my_parser = argparse.ArgumentParser()
    my_parser.add_argument("arguments", nargs="*")
    options = my_parser.parse_args()
    _exit = False
    if len(options.arguments) in [5, 8]:
        global_config.add_config_entries(
            [
                ("HOST_LONG", StringConfigVar(options.arguments[0], source="cmdline")),
                ("JOB_OWNER", StringConfigVar(options.arguments[1], source="cmdline")),
                ("JOB_ID", StringConfigVar(options.arguments[2], source="cmdline")),
                ("JOB_NAME", StringConfigVar(options.arguments[3], source="cmdline")),
                ("JOB_QUEUE", StringConfigVar(options.arguments[4], source="cmdline")),
            ]
        )
        if len(options.arguments) == 8:
            global_config.add_config_entries(
                [
                    ("PE_HOSTFILE", StringConfigVar(options.arguments[5], source="cmdline")),
                    ("PE", StringConfigVar(options.arguments[6], source="cmdline")),
                    ("PE_SLOTS", StringConfigVar(options.arguments[7], source="cmdline"))
                ]
            )
    elif len(options.arguments) == 0:
        ProcessPool(dummy_call=True)
        _exit = True
    else:
        print(
            "Unable to determine execution mode for {}, exiting ({:d} args)".format(
                global_config.name(),
                len(options.arguments)
            )
        )
        _exit = True
    if not _exit:
        cf_time = time.localtime(os.stat(configfile.__file__.replace(".pyc", ".py").replace(".pyo", ".py"))[stat.ST_MTIME])
        if (cf_time.tm_year, cf_time.tm_mon, cf_time.tm_mday) < (2012, 5, 1):
            print(
                "your python-modules-base are too old, please upgrade ({:d}, {:d}, {:d})".format(
                    cf_time.tm_year,
                    cf_time.tm_mon,
                    cf_time.tm_mday
                )
            )
            return 0
        else:
            # add more entries
            global_config.add_config_entries(
                [
                    ("HOST_SHORT", StringConfigVar(global_config["HOST_LONG"].split(".")[0], source="cmdline")),
                    ("CALLER_NAME", StringConfigVar(global_config.name(), source="cmdline")),
                    ("HOST_IP", StringConfigVar("unknown", source="cmdline")),
                ]
            )
            return ProcessPool().loop()
    else:
        return -1

if __name__ == "__main__":
    sys.exit(main_code())
