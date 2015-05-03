#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001-2009,2011-2015 Andreas Lang-Nevyjel, init.at
#
# this file is part of python-modules-base
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

""" container for service checks """

import os
import stat
import subprocess
import signal
import sys

from lxml.builder import E  # @UnresolvedImport
from initat.tools import logging_tools
from initat.tools import process_tools
import psutil

from .constants import *


class Service(object):
    _COMPAT_DICT = {
        "rms-server": "rms_server",
        "logcheck-server": "logcheck",
    }

    def __init__(self, entry, log_com):
        self.__log_com = log_com
        self.name = entry.attrib["name"]
        self.__entry = entry
        self.__attrib = dict(self.__entry.attrib)

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_com(u"[srv {}] {}".format(self.name, what), log_level)

    @property
    def entry(self):
        return self.__entry

    @property
    def init_script_name(self):
        return os.path.join("/etc", "init.d", self.__attrib["init_script_name"])

    @property
    def msi_name(self):
        c_name = self.__attrib["meta_server_name"]
        _path = os.path.join("/var", "lib", "meta-server", c_name)
        # compat layer for buggy specs
        if not os.path.exists(_path) and c_name in self._COMPAT_DICT:
            _alt_path = os.path.join("/var", "lib", "meta-server", self._COMPAT_DICT[c_name])
            if os.path.exists(_alt_path):
                _path = _alt_path
        return _path

    @property
    def old_binary(self):
        # returns name of old binary
        _old_bin = self.__entry.findtext(".//old-binary")
        if _old_bin:
            _old_bin = _old_bin.strip()
        else:
            _old_bin = self.name
        return _old_bin

    @property
    def prog_title(self):
        _prog_title = self.__entry.findtext(".//programm-title")
        if _prog_title:
            _prog_title = _prog_title.strip()
        else:
            _prog_title = "icsw.{}".format(self.name)
        return _prog_title

    @property
    def prog_name(self):
        _prog_name = self.__entry.findtext(".//programm-name")
        if _prog_name:
            _prog_name = _prog_name.strip()
        else:
            _prog_name = self.name
        return _prog_name

    @property
    def module_name(self):
        _mod_name = self.__entry.findtext(".//module-name")
        if _mod_name:
            _mod_name = _mod_name.strip()
        else:
            _mod_name = "initat.{}.main".format(self.name.replace("-", "_"))
        return _mod_name

    @property
    def is_ok(self):
        # return True if the service in entry is running
        _si = self.__entry.find(".//state_info")
        if _si is not None:
            _state = int(_si.get("state"))
            return True if _state == SERVICE_OK else False
        else:
            return False

    def check(self, act_proc_dict, refresh=True, config_tools=None):
        if self.__entry.find("result") is not None:
            if refresh:
                # remove current result record
                self.__entry.remove(self.__entry.find("result"))
            else:
                # result record already present, return
                return
        dev_config = []
        if config_tools is not None:
            if self.__entry.find(".//config_names/config_name") is not None:
                # dev_config = config_tools.device_with_config(entry.findtext(".//config_names/config_name"))
                _conf_names = [_entry.text for _entry in self.__entry.findall(".//config_names/config_name")]
                for _conf_name in _conf_names:
                    _cr = config_tools.server_check(server_type=_conf_name)
                    if _cr.effective_device:
                        dev_config.append(_cr)
        _result = E.result()
        self.__entry.append(_result)

        if self.__attrib["check_type"] == "simple":
            self._check_simple(_result)
        elif self.__attrib["check_type"] == "meta":
            self._check_meta(_result, act_proc_dict)
        elif self.__attrib["check_type"] == "pid_file":
            self._check_pid_file(_result, act_proc_dict)
        else:
            _result.append(E.state_info("unknown check_type '{}'".format(self.__attrib["check_type"]), state="1"))

        act_state = int(_result.find("state_info").attrib["state"])
        if self.__attrib["runs_on"] == "server":
            if dev_config:  # is not None:
                sql_info = ", ".join([_dc.server_info_str for _dc in dev_config])
            else:
                act_state = SERVICE_NOT_CONFIGURED
                sql_info = "not configured"
                # update state info
                _state_info = _result.find("state_info")
                _state_info.text = "not configured"
                _state_info.attrib["state"] = "{:d}".format(act_state)
        else:
            sql_info = self.__attrib["runs_on"]
        if type(sql_info) == str:
            _result.append(
                E.sql_info(str(sql_info))
            )
        else:
            _result.append(
                E.sql_info("{} ({})".format(
                    sql_info.server_info_str,
                    sql_info.config_name),
                )
            )
        if self.__entry.get("runs_on") in ["client", "server"] and act_state != SERVICE_NOT_INSTALLED:
            _result.attrib["version_ok"] = "0"
            try:
                if "version_file" in self.__attrib:
                    _path = self.__attrib["version_file"]
                else:
                    _path = "%{{INIT_BASE}}/{runs_on}_version.py".format(**self.__attrib)
                _path = _path.replace("%{INIT_BASE}", INIT_BASE)
                _lines = file(_path, "r").read().split("\n")
                _vers_lines = [_line for _line in _lines if _line.startswith("VERSION_STRING")]
                if _vers_lines:
                    _result.attrib["version_ok"] = "1"
                    _result.attrib["version"] = _vers_lines[0].split("=", 1)[1].strip().replace('"', "").replace("'", "")
                else:
                    _result.attrib["version"] = "no version lines found in '{}'".format(_path)
            except:
                _result.attrib["version"] = "error getting version: {}".format(process_tools.get_except_info())

    def _check_simple(self, result):
        init_script_name = self.init_script_name
        if os.path.isfile(init_script_name):
            act_pids = []
            for _proc in psutil.process_iter():
                try:
                    if _proc.is_running() and _proc.name() == self.__attrib["process_name"]:
                        act_pids.append(_proc.pid)
                except psutil.NoSuchProcess:
                    pass
            if act_pids:
                act_state, act_str = (SERVICE_OK, "running")
                self._add_pids(result, act_pids)
            else:
                act_state, act_str = (SERVICE_DEAD, "not running")
        else:
            act_state, act_str = (SERVICE_NOT_INSTALLED, "not installed")
        result.append(
            E.state_info(
                act_str,
                check_source="simple",
                state="{:d}".format(act_state),
                proc_info_str=act_str,
            ),
        )

    def _check_meta(self, result, act_proc_dict):
        init_script_name = self.init_script_name
        c_name = self.__attrib["meta_server_name"]
        ms_name = self.msi_name
        if os.path.exists(ms_name):
            # TODO : cache msi files
            ms_block = process_tools.meta_server_info(ms_name)
            start_time = ms_block.start_time
            # if not ms_block.check_block(act_proc_dict):
            #    print self.name, ms_block.pid_check_string
            diff_dict = {key: value for key, value in ms_block.bound_dict.iteritems() if value}
            diff_threads = sum(ms_block.bound_dict.values())
            act_pids = ms_block.pids_found
            num_started = len(act_pids)
            if diff_threads:
                act_state = SERVICE_DEAD
                num_found = num_started
            else:
                act_state = SERVICE_OK
                num_found = num_started
            num_diff = diff_threads
            # print ms_block.pids, ms_block.pid_check_string
            result.append(
                E.state_info(
                    *[
                        E.diff_info(
                            pid="{:d}".format(key),
                            diff="{:d}".format(value)
                        ) for key, value in diff_dict.iteritems()
                    ],
                    check_source="meta",
                    num_started="{:d}".format(num_started),
                    num_found="{:d}".format(num_found),
                    num_diff="{:d}".format(num_diff),
                    start_time="{:d}".format(int(start_time)),
                    state="{:d}".format(act_state),
                    proc_info_str=self._get_proc_info_str(
                        num_started,
                        num_found,
                        num_diff,
                        len(act_pids),
                        diff_dict,
                        True if int(self.entry.attrib["any_threads_ok"]) else False,
                    )
                ),
            )
            # print act_pids, ms_block.pids
            self._add_pids(result, act_pids, main_pid=ms_block.get_main_pid(), msi_block=ms_block)
        else:
            self._add_non_running(result, check_init_script=False)

    def _check_pid_file(self, result, act_proc_dict):
        name = self.name
        pid_file_name = self.__attrib["pid_file_name"]
        if not pid_file_name.startswith("/"):
            pid_file_name = os.path.join("/var", "run", pid_file_name)
        if os.path.isfile(pid_file_name):
            start_time = os.stat(pid_file_name)[stat.ST_CTIME]
            act_pids = [int(line.strip()) for line in file(pid_file_name, "r").read().split("\n") if line.strip().isdigit()]
            act_state, num_started, num_found = self._check_processes(act_pids, act_proc_dict)
            num_diff = 0
            diff_dict = {}
            result.append(
                E.state_info(
                    *[
                        E.diff_info(
                            pid="{:d}".format(key),
                            diff="{:d}".format(value)
                        ) for key, value in diff_dict.iteritems()
                    ],
                    check_source="pid",
                    num_started="{:d}".format(num_started),
                    num_found="{:d}".format(num_found),
                    num_diff="{:d}".format(num_diff),
                    start_time="{:d}".format(start_time),
                    state="{:d}".format(act_state),
                    proc_info_str=self._get_proc_info_str(
                        num_started,
                        num_found,
                        num_diff,
                        len(act_pids),
                        diff_dict,
                        True if int(self.entry.attrib["any_threads_ok"]) else False,
                    )
                ),
            )
            self._add_pids(result, act_pids)
        else:
            self._add_non_running(result)

    def _get_proc_info_str(self, num_started, num_found, num_diff, num_pids, diff_dict, any_ok):
        if any_ok:
            ret_str = "{} running".format(logging_tools.get_plural("thread", num_found))
        else:
            if diff_dict:
                diff_str = ", [diff: {}]".format(
                    ", ".join(
                        [
                            "{:d}: {:d}".format(_key, _value) for _key, _value in diff_dict.iteritems()
                        ]
                    )
                )
            else:
                diff_str = ""
            if num_diff < 0:
                ret_str = "{} {} missing{}".format(
                    logging_tools.get_plural("thread", -num_diff),
                    num_diff == 1 and "is" or "are",
                    diff_str,
                )
                da_name = "critical"
            elif num_diff > 0:
                ret_str = "{} too much{}".format(
                    logging_tools.get_plural("thread", num_diff),
                    diff_str,
                )
                da_name = "warning"
            else:
                ret_str = "the thread is running" if num_started == 1 else "{}{} ({}) running".format(
                    "all " if num_pids > 1 else "",
                    logging_tools.get_plural("process", num_pids),
                    logging_tools.get_plural("thread", num_started),
                )
        return ret_str

    def _check_processes(self, pids, act_proc_dict):
        name = self.name
        any_ok = True if int(self.__attrib["any_threads_ok"]) else False
        unique_pids = {
            key: pids.count(key) for key in set(pids)
        }
        pids_found = {
            key: act_proc_dict[key].num_threads() for key in set(pids) if key in act_proc_dict
        }
        num_started = sum(unique_pids.values()) if unique_pids else 0
        num_found = sum(pids_found.values()) if pids_found else 0
        # check for extra Nagios2.x thread
        if any_ok and num_found:
            ret_state = SERVICE_OK
        elif num_started == num_found:
            ret_state = SERVICE_OK
        else:
            ret_state = SERVICE_NOT_CONFIGURED
        return ret_state, num_started, num_found

    def _add_non_running(self, result, check_init_script=True):
        init_script_name = self.init_script_name
        if os.path.isfile(init_script_name) or check_init_script is False:
            act_state = SERVICE_DEAD
            result.append(
                E.state_info(
                    "no threads",
                    state="{:d}".format(act_state),
                )
            )
        else:
            act_state = SERVICE_NOT_INSTALLED
            result.append(
                E.state_info(
                    "not installed",
                    state="{:d}".format(act_state),
                )
            )

    def _add_pids(self, result, act_pids, main_pid=None, msi_block=None):
        # print "+", main_pid
        if act_pids:
            result.append(
                E.pids(
                    *[
                        E.pid(
                            "{:d}".format(cur_pid),
                            count="{:d}".format(act_pids.count(cur_pid)),
                            main="1" if cur_pid == main_pid else "0",
                        ) for cur_pid in set(act_pids)
                    ]
                )
            )
            mem_dict = {
                cur_pid: process_tools.get_mem_info(cur_pid) for cur_pid in set(act_pids)
            }

            _mem_info = E.memory_info(
                "{:d}".format(
                    sum(mem_dict.values()),
                ) if act_pids else "",
                valid="1" if act_pids else "0",
            )
            if msi_block and act_pids:
                _mem_info.append(
                    E.details(
                        *[
                            E.mem("{:d}".format(_value), name=msi_block.get_process_name(_key)) for _key, _value in mem_dict.iteritems()
                        ]
                    )
                )
            result.append(_mem_info)

    # action commands
    def action(self, action, act_proc_dict):
        return {
            "stop": self.stop,
            "start": self.start,
            "cleanup": self.cleanup,
            "wait": self.wait,
            "debug": self.debug,
        }[action](act_proc_dict)

    def wait(self, act_proc_dict):
        return

    def stop(self, act_proc_dict):
        if not int(self.__entry.get("startstop", "1")):
            return
        if self.__entry.get("check_type") == "simple":
            self._handle_service_rc("stop")
        else:
            self._stop_service_py()

    def start(self, act_proc_dict):
        if not int(self.__entry.get("startstop", "1")):
            return
        if self.__entry.get("check_type") == "simple":
            self._handle_service_rc("start")
        else:
            self._start_service_py()

    def cleanup(self, act_proc_dict):
        if not int(self.__entry.get("startstop", "1")):
            return
        if self.__entry.get("check_type") == "simple":
            return
        _meta_pids = set([int(_val.text) for _val in self.__entry.findall(".//pids/pid")])
        _proc_pids = self._find_pids_by_name(act_proc_dict)
        _all_pids = _meta_pids | _proc_pids
        if _all_pids:
            for _pid in _all_pids:
                try:
                    os.kill(_pid, 9)
                except OSError:
                    self.log("process {:d} has vanished".format(_pid), logging_tools.LOG_LEVEL_ERROR)
                else:
                    self.log("sent signal 9 to {:d}".format(_pid))
        # remove meta server
        ms_name = self.msi_name
        if os.path.exists(ms_name):
            self.log("removing msi-block {}".format(ms_name))
            os.unlink(ms_name)

    def debug(self, act_proc_dict):
        if not int(self.__entry.get("startstop", "1")):
            return
        if self.__entry.get("check_type") == "simple":
            return
        else:
            self._debug_py()

    def _debug_py(self):
        # ignore sigint to catch keyboard interrupt
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        arg_list = self._generate_py_arg_list(debug=True)
        arg_list.append("--debug")
        self.log("debug, arg_list is '{}'".format(" ".join(arg_list)))
        subprocess.call(" ".join(arg_list), shell=True)

    def _stop_service_py(self):
        _main_pids = [int(_val.text) for _val in self.__entry.findall(".//pids/pid[@main='1']")]
        _meta_pids = [int(_val.text) for _val in self.__entry.findall(".//pids/pid")]
        # print etree.tostring(entry, pretty_print=True)
        # print _main_pids, _meta_pids
        if len(_meta_pids):
            try:
                if _main_pids:
                    os.kill(_main_pids[0], 15)
                    self.log("sent signal 15 to {:d}".format(_main_pids[0]))
                else:
                    os.kill(_meta_pids[0], 15)
                    self.log("sent signal 15 to {:d}".format(_meta_pids[0]))
            except OSError:
                self.log("process vanished: {}".format(process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
        else:
            self.log("no pids to kill")

    def _handle_service_rc(self, command):
        process_tools.call_command("{} {}".format(self.init_script_name, command), self.log)

    def _start_service_py(self):
        arg_list = self._generate_py_arg_list()
        self.log("starting: {}".format(" ".join(arg_list)))
        if not os.fork():
            subprocess.call(arg_list + ["-d"])
            os._exit(1)
        else:
            _child_pid, _child_state = os.wait()

    def _generate_py_arg_list(self, debug=False):
        cur_name = self.name
        _prog_name = self.prog_name
        _prog_title = self.prog_title
        arg_dict = {_val.get("key"): _val.text.strip() for _val in self.__entry.findall(".//arg[@key]")}
        _module_name = self.__entry.get("module", self.module_name)
        if debug:
            _daemon_path = os.path.split(os.path.split(os.path.dirname(__file__))[0])[0]
        else:
            _daemon_path = "/opt/python-init/lib/python/site-packages/initat"
        _arg_list = [
            os.path.join(_daemon_path, "tools", "daemonize.py"),
            "--progname",
            _prog_name,
            "--modname",
            _module_name,
            "--proctitle",
            _prog_title,
        ]
        for _add_key in ["user", "group", "groups"]:
            if _add_key in arg_dict:
                _arg_list.extend(
                    [
                        "--{}".format(_add_key),
                        arg_dict[_add_key],
                    ]
                )
        if self.__entry.find("nice-level"):
            _arg_list.extend(
                [
                    "--nice",
                    "{:d}".format(int(self.__entry.findtext("nice-level").strip())),
                ]
            )
        # check access rights
        for _dir_el in self.__entry.findall(".//access-rights/dir[@value]"):
            _dir = _dir_el.get("value")
            if not os.path.isdir(_dir) and int(_dir_el.get("create", "0")):
                os.makedirs(_dir)
            if os.path.isdir(_dir):
                os.chown(
                    _dir,
                    process_tools.get_uid_from_name(_dir_el.get("user", "root"))[0],
                    process_tools.get_gid_from_name(_dir_el.get("group", "root"))[0],
                )
        for _file_el in self.__entry.findall(".//access-rights/file[@value]"):
            if os.path.isfile(_file_el.get("value")):
                os.chown(
                    _file_el.get("value"),
                    process_tools.get_uid_from_name(_file_el.get("user", "root"))[0],
                    process_tools.get_gid_from_name(_file_el.get("group", "root"))[0],
                )
        return _arg_list

    def _find_pids_by_name(self, act_proc_dict):
        _new_title = self.prog_title
        _old_bins = self.old_binary.strip().split(",")
        # print _new_title, "old_bins", _old_bins
        _pid_list = set()
        for _key, _value in act_proc_dict.iteritems():
            try:
                _cmdline = _value.cmdline()
            except:
                pass
            else:
                if _cmdline:
                    _cmdline = sum([_part.strip().split() for _part in _cmdline], [])
                    if _cmdline[0] == _new_title:
                        # print "+", _cmdline, _new_title
                        _pid_list.add(_key)
                    elif _cmdline[0].endswith("python-init"):
                        # print _cmdline
                        _icsw_found, _old_found = (any([_part.count("icsw") or _part.count("check_scripts") for _part in _cmdline]), False)
                        # print "*", _cmdline
                        for _part in _cmdline:
                            if any([_part.count(_old_bin) for _old_bin in _old_bins]):
                                # match
                                _old_found = True
                        # print _old_found, _icsw_found
                        if _old_found and not _icsw_found:
                            _pid_list.add(_key)
        # print "found", _pid_list
        return _pid_list
