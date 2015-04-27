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

""" checks installed servers on system """

import os
import sys

# sys.path.insert(0, "/usr/local/share/home/local/development/git/icsw/")

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

from lxml import etree  # @UnresolvedImport
from lxml.builder import E  # @UnresolvedImport
import argparse
import commands
import daemon
import datetime
from initat.tools import logging_tools
from initat.tools import process_tools
from initat.tools.io_stream_helper import io_stream
import psutil
import stat
import subprocess
import setproctitle
import importlib
import time

try:
    from django.conf import settings
except:
    settings = None
    config_tools = None
else:
    from django.db import connection
    try:
        _sm = settings.SATELLITE_MODE
    except:
        _sm = False
    if _sm:
        config_tools = None
    else:
        import django
        try:
            django.setup()
        except:
            config_tools = None
        else:
            from initat.tools import config_tools

SERVERS_DIR = "/opt/cluster/etc/servers.d"

# return values
SERVICE_OK = 0
SERVICE_DEAD = 1
SERVICE_NOT_INSTALLED = 5
# also if config not set or insufficient licenses
SERVICE_NOT_CONFIGURED = 6


class InstanceXML(object):
    def __init__(self, log_com):
        self.__log_com = log_com
        self.read()
        self.normalize()

    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        self.__log_com("[iXML] {}".format(what), level)

    def read(self):
        self.tree = E.instances()
        # check for additional instances
        if os.path.isdir(SERVERS_DIR):
            for entry in os.listdir(SERVERS_DIR):
                if entry.endswith(".xml"):
                    try:
                        add_inst_list = etree.fromstring(open(os.path.join(SERVERS_DIR, entry), "r").read())  # @UndefinedVariable
                    except:
                        self.log(
                            "cannot read entry '{}' from {}: {}".format(
                                entry,
                                SERVERS_DIR,
                                process_tools.get_except_info(),
                            ),
                            logging_tools.LOG_LEVEL_ERROR
                        )
                    else:
                        for sub_inst in add_inst_list.findall("instance"):
                            self.tree.append(sub_inst)

    def normalize(self):
        for cur_el in self.tree.findall("instance"):
            name = cur_el.attrib["name"]
            for key, def_value in [
                ("runs_on", "server"),
                ("any_threads_ok", "0"),
                ("pid_file_name", "{}.pid".format(name)),
                ("init_script_name", name),
                ("startstop", "1"),
                ("process_name", name),
                ("meta_server_name", name),
            ]:
                if key not in cur_el.attrib:
                    cur_el.attrib[key] = def_value


class ServiceContainer(object):
    INIT_BASE = "/opt/python-init/lib/python/site-packages/initat"
    _COMPAT_DICT = {
        "rms-server": "rms_server",
        "logcheck-server": "logcheck",
    }

    def __init__(self, log_com):
        self.__log_com = log_com

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_com(u"[SrvC] {}".format(what), log_level)

    def _check_simple(self, entry, result):
        init_script_name = os.path.join("/etc", "init.d", entry.attrib["init_script_name"])
        if os.path.isfile(init_script_name):
            act_pids = []
            for _proc in psutil.process_iter():
                try:
                    if _proc.is_running() and _proc.name() == entry.attrib["process_name"]:
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
        result.append(E.state_info(act_str, check_source="simple", state="{:d}".format(act_state)))

    def _check_meta(self, entry, result):
        init_script_name = os.path.join("/etc", "init.d", entry.attrib["init_script_name"])
        c_name = entry.attrib["meta_server_name"]
        ms_name = os.path.join("/var", "lib", "meta-server", c_name)
        # compat layer for buggy specs
        if not os.path.exists(ms_name) and c_name in self._COMPAT_DICT:
            _ms_name = os.path.join("/var", "lib", "meta-server", self._COMPAT_DICT[c_name])
            if os.path.exists(_ms_name):
                ms_name = _ms_name
        if os.path.exists(ms_name):
            ms_block = process_tools.meta_server_info(ms_name)
            start_time = ms_block.start_time
            ms_block.check_block(self.__act_proc_dict)
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
                    state="{:d}".format(act_state)
                ),
            )
            # print act_pids, ms_block.pids
            self._add_pids(result, act_pids, main_pid=ms_block.get_main_pid())
        else:
            self._add_non_running(entry, result, check_init_script=False)

    def _add_non_running(self, entry, result, check_init_script=True):
        init_script_name = os.path.join("/etc", "init.d", entry.attrib["init_script_name"])
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

    def _check_processes(self, entry, pids):
        name = entry.attrib["name"]
        any_ok = True if int(entry.attrib["any_threads_ok"]) else False
        unique_pids = {
            key: pids.count(key) for key in set(pids)
        }
        pids_found = {
            key: self.__act_proc_dict[key].num_threads() for key in set(pids) if key in self.__act_proc_dict
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

    def _check_pid_file(self, entry, result):
        name = entry.attrib["name"]
        pid_file_name = entry.attrib["pid_file_name"]
        if not pid_file_name.startswith("/"):
            pid_file_name = os.path.join("/var", "run", pid_file_name)
        if os.path.isfile(pid_file_name):
            start_time = os.stat(pid_file_name)[stat.ST_CTIME]
            act_pids = [int(line.strip()) for line in file(pid_file_name, "r").read().split("\n") if line.strip().isdigit()]
            act_state, num_started, num_found = self._check_processes(entry, act_pids)
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
                    state="{:d}".format(act_state)
                ),
            )
            self._add_pids(result, act_pids)
        else:
            self._add_non_running(entry, result)

    def _add_pids(self, result, act_pids, main_pid=None):
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
            result.append(
                E.memory_info(
                    "{:d}".format(
                        sum(process_tools.get_mem_info(cur_pid) for cur_pid in set(act_pids))
                    ) if act_pids else "",
                )
            )

    def check_service(self, opt_ns, entry, **kwargs):
        if not kwargs.get("use_cache", False):
            self.__act_proc_dict = process_tools.get_proc_list()
        if entry.find("result"):
            if kwargs.get("refresh", False):
                # remove current result record
                entry.remove(entry.find("result"))
            else:
                # result record already present, return
                return
        dev_config = []
        if config_tools and entry.find(".//config_names/config_name") is not None:
            # dev_config = config_tools.device_with_config(entry.findtext(".//config_names/config_name"))
            _conf_names = [_entry.text for _entry in entry.findall(".//config_names/config_name")]
            for _conf_name in _conf_names:
                _cr = config_tools.server_check(server_type=_conf_name)
                if _cr.effective_device:
                    dev_config.append(_cr)

        name = entry.attrib["name"]
        _result = E.result()
        entry.append(_result)
        init_script_name = os.path.join("/etc", "init.d", entry.attrib["init_script_name"])
        if entry.attrib["check_type"] == "simple":
            self._check_simple(entry, _result)
        elif entry.attrib["check_type"] == "meta":
            self._check_meta(entry, _result)
        elif entry.attrib["check_type"] == "pid_file":
            self._check_pid_file(entry, _result)
        else:
            _result.append(E.state_info("unknown check_type '{}'".format(entry.attrib["check_type"]), state="1"))
        act_state = int(_result.find("state_info").attrib["state"])
        if entry.attrib["runs_on"] == "server":
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
            sql_info = entry.attrib["runs_on"]
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
        if entry.get("runs_on") in ["client", "server"] and act_state != SERVICE_NOT_INSTALLED:
            _result.attrib["version_ok"] = "0"
            try:
                if "version_file" in entry.attrib:
                    _path = entry.attrib["version_file"]
                else:
                    _path = "%{{INIT_BASE}}/{runs_on}_version.py".format(**dict(entry.attrib))
                _path = _path.replace("%{INIT_BASE}", self.INIT_BASE)
                _lines = file(_path, "r").read().split("\n")
                _vers_lines = [_line for _line in _lines if _line.startswith("VERSION_STRING")]
                if _vers_lines:
                    _result.attrib["version_ok"] = "1"
                    _result.attrib["version"] = _vers_lines[0].split("=", 1)[1].strip().replace('"', "").replace("'", "")
                else:
                    _result.attrib["version"] = "no version lines found in '{}'".format(_path)
            except:
                _result.attrib["version"] = "error getting version: {}".format(process_tools.get_except_info())

    def get_instance_xml(self):
        return InstanceXML(self.__log_com).tree

    def apply_filter(self, opt_ns, instance_xml):
        check_list = instance_xml.xpath(".//instance[@runs_on]", smart_strings=False)
        if opt_ns.service:
            check_list = [_entry for _entry in check_list if _entry.get("name") in opt_ns.service]
        return check_list

    def check_system(self, opt_ns, instance_xml, **kwargs):
        check_list = self.apply_filter(opt_ns, instance_xml)
        self.__act_proc_dict = process_tools.get_proc_list()
        if kwargs.get("refresh", False):
            # delete all previous result records
            for _result in instance_xml.findall("instance/result"):
                _result.getparent().remove(_result)
        for entry in check_list:
            self.check_service(opt_ns, entry, use_cache=True)

    def actions(self, opt_ns, instance_xml):
        # mother of action, decide what to do
        check_list = self.apply_filter(opt_ns, instance_xml)
        self.__act_proc_dict = process_tools.get_proc_list()
        for entry in check_list:
            self.action(opt_ns, entry)

    def service_ok(self, entry):
        # return True if the service in entry is running
        _si = entry.find(".//state_info")
        if _si is not None:
            _state = int(_si.get("state"))
            return True if _state == SERVICE_OK else False
        else:
            return False

    def decide(self, opt_ns, entry):
        # based on the entry state and the command given in opt_ns decide what to do
        _state = self.service_ok(entry)
        _subcom = opt_ns.subcom
        _act_list = {
            False: {
                "start": ["cleanup", "start"],
                "stop": ["cleanup"],
                "restart": ["cleanup", "start"],
            },
            True: {
                "start": [],
                "stop": ["stop"],
                "restart": ["stop", "cleanup", "start"],
            }
        }[_state][_subcom]
        return _act_list

    def action(self, opt_ns, entry):
        self.check_service(opt_ns, entry)
        _action_list = self.decide(opt_ns, entry)
        if _action_list:
            print entry.get("name"), _action_list
        for _action in _action_list:
            {
                "stop": self.stop_service,
                "start": self.start_service,
                "cleanup": self.cleanup_service,
            }[_action](opt_ns, entry)

    def stop_service(self, opt_ns, entry):
        _main_pids = [int(_val.text) for _val in entry.findall(".//pids/pid[@main='1']")]
        _meta_pids = [int(_val.text) for _val in entry.findall(".//pids/pid")]
        # print etree.tostring(entry, pretty_print=True)
        if len(_meta_pids):
            if _main_pids:
                os.kill(_main_pids[0], 15)
            else:
                os.kill(_meta_pids[0], 15)
            # print "stop", _main_pids, _meta_pids

    def cleanup_service(self, opt_ns, entry):
        # print etree.tostring(entry)
        _meta_pids = set([int(_val.text) for _val in entry.findall(".//pids/pid")])
        _proc_pids = self._find_pids_by_name(entry)
        _all_pids = _meta_pids | _proc_pids
        if _all_pids:
            for _pid in _all_pids:
                os.kill(_pid, 9)
        # print "cleanup", _meta_pids, _proc_pids
        # import pprint
        # pprint.pprint(self.__act_proc_dict)

    def _find_pids_by_name(self, entry):
        _new_title = self._get_prog_title(entry)
        _old_bin = self._get_old_binary(entry)
        print _new_title, _old_bin
        _pid_list = set()
        for _key, _value in self.__act_proc_dict.iteritems():
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
                            if _part.count(_old_bin):
                                # match
                                _old_found = True
                        # print _old_found, _icsw_found
                        if _old_found and not _icsw_found:
                            _pid_list.add(_key)
        print "found", _pid_list
        return _pid_list

    def _get_old_binary(self, entry):
        # returns name of old binary
        _old_bin = entry.findtext(".//old-binary")
        if _old_bin:
            _old_bin = _old_bin.strip()
        else:
            _old_bin = entry.get("name")
        return _old_bin

    def _get_prog_title(self, entry):
        _prog_title = entry.findtext(".//programm-title")
        if _prog_title:
            _prog_title = _prog_title.strip()
        else:
            _prog_title = "icsw.{}".format(entry.get("name"))
        return _prog_title

    def _get_prog_name(self, entry):
        _prog_name = entry.findtext(".//programm-name")
        if _prog_name:
            _prog_name = _prog_name.strip()
        else:
            _prog_name = entry.attrib["name"]
        return _prog_name

    def _get_module_name(self, entry):
        _mod_name = entry.findtext(".//module-name")
        if _mod_name:
            _mod_name = _mod_name.strip()
        else:
            _mod_name = "initat.{}.main".format(entry.attrib["name"].replace("-", "_"))
        return _mod_name

    def start_service(self, opt_ns, entry):
        cur_name = entry.attrib["name"]
        _prog_name = self._get_prog_name(entry)
        _prog_title = self._get_prog_title(entry)
        arg_dict = {_val.get("key"): _val.text.strip() for _val in entry.findall(".//arg[@key]")}

        print arg_dict
        _module_name = entry.get("module", self._get_module_name(entry))
        _arg_list = [
            "/opt/python-init/lib/python/site-packages/initat/tools/daemonize.py",
            "-d",
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
        if entry.find("nice-level"):
            _arg_list.extend(
                [
                    "--nice",
                    "{:d}".format(int(entry.findtext("nice-level").strip())),
                ]
            )
        # check access rights
        for _file_el in entry.findall(".//access-rights/file[@value]"):
            if os.path.isfile(_file_el.get("value")):
                os.chown(
                    _file_el.get("value"),
                    process_tools.get_uid_from_name(_file_el.get("user", "root")),
                    process_tools.get_gid_from_name(_file_el.get("group", "root")),
                )
        print " ".join(_arg_list)
        if not os.fork():
            subprocess.call(_arg_list)
            os._exit(1)


def show_xml(opt_ns, res_xml, iteration=0):
    # color strings (green / blue / red / normal)
    col_str_dict = {
        0: "\033[1;32m",
        1: "\033[1;34m",
        2: "\033[1;31m",
        3: "\033[m\017",
    }
    rc_dict = {
        SERVICE_OK: (0, "running"),
        SERVICE_DEAD: (2, "error"),
        SERVICE_NOT_INSTALLED: (1, "not installed"),
        SERVICE_NOT_CONFIGURED: (1, "not configured"),
    }
    rc_strs = {
        key: "{}{}{}".format(
            col_str_dict[wc],
            value,
            col_str_dict[3]
        ) for key, (wc, value) in rc_dict.iteritems()
    }
    out_bl = logging_tools.new_form_list()
    types = ["client", "server", "system"]
    _list = sum(
        [
            res_xml.xpath("instance[result and @runs_on='{}']".format(_type)) for _type in types
        ],
        []
    )
    for act_struct in _list:
        _res = act_struct.find("result")
        cur_line = [logging_tools.form_entry(act_struct.attrib["name"], header="Name")]
        cur_line.append(logging_tools.form_entry(act_struct.attrib["runs_on"], header="type"))
        cur_line.append(logging_tools.form_entry(_res.find("state_info").get("check_source", "N/A"), header="source"))
        if opt_ns.thread:
            s_info = act_struct.find(".//state_info")
            if "num_started" not in s_info.attrib:
                cur_line.append(logging_tools.form_entry(s_info.text))
            else:
                num_started, num_found, num_diff, any_ok = (
                    int(s_info.get("num_started")),
                    int(s_info.get("num_found")),
                    int(s_info.get("num_diff")),
                    True if int(act_struct.attrib["any_threads_ok"]) else False
                )
                # print etree.tostring(act_struct, pretty_print=True)
                if any_ok:
                    ret_str = "{} running".format(logging_tools.get_plural("thread", num_found))
                else:
                    diffs_found = s_info.findall("diff_info")
                    if diffs_found:
                        diff_str = ", [diff: {}]".format(
                            ", ".join(
                                [
                                    "{:d}: {:d}".format(int(cur_diff.attrib["pid"]), int(cur_diff.attrib["diff"])) for cur_diff in diffs_found
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
                    elif num_diff > 0:
                        ret_str = "{} too much{}".format(
                            logging_tools.get_plural("thread", num_diff),
                            diff_str,
                        )
                    else:
                        ret_str = "the thread is running" if num_started == 1 else "all {:d} threads running".format(num_started)
                cur_line.append(logging_tools.form_entry(ret_str, header="Thread info"))
        if opt_ns.started:
            start_time = int(act_struct.find(".//state_info").get("start_time", "0"))
            if start_time:
                diff_time = max(0, time.mktime(time.localtime()) - start_time)
                diff_days = int(diff_time / (3600 * 24))
                diff_hours = int((diff_time - 3600 * 24 * diff_days) / 3600)
                diff_mins = int((diff_time - 3600 * (24 * diff_days + diff_hours)) / 60)
                diff_secs = int(diff_time - 60 * (60 * (24 * diff_days + diff_hours) + diff_mins))
                ret_str = "{}".format(
                    time.strftime("%a, %d. %b %Y, %H:%M:%S", time.localtime(start_time))
                )
            else:
                ret_str = "no start info found"
            cur_line.append(logging_tools.form_entry(ret_str, header="started"))
        if opt_ns.pid:
            pid_dict = {}
            for cur_pid in act_struct.findall(".//pids/pid"):
                pid_dict[int(cur_pid.text)] = int(cur_pid.get("count", "1"))
            if pid_dict:
                p_list = sorted(pid_dict.keys())
                if max(pid_dict.values()) == 1:
                    cur_line.append(logging_tools.form_entry(logging_tools.compress_num_list(p_list), header="pids"))
                else:
                    cur_line.append(
                        logging_tools.form_entry(
                            ",".join(["{:d}{}".format(
                                key,
                                " ({:d})".format(pid_dict[key]) if pid_dict[key] > 1 else "") for key in p_list]
                            ),
                            header="pids"
                        )
                    )
            else:
                cur_line.append(logging_tools.form_entry("no PIDs", header="pids"))
        if opt_ns.database:
            cur_line.append(logging_tools.form_entry(act_struct.findtext("sql_info"), header="DB info"))
        if opt_ns.memory:
            cur_mem = act_struct.find(".//memory_info")
            if cur_mem is not None:
                mem_str = process_tools.beautify_mem_info(int(cur_mem.text))
            else:
                # no pids hence no memory info
                mem_str = ""
            cur_line.append(logging_tools.form_entry_right(mem_str, header="Memory"))
        if opt_ns.version:
            if "version" in _res.attrib:
                _version = _res.attrib["version"]
            else:
                _version = ""
            cur_line.append(logging_tools.form_entry_right(_version, header="Version"))
        cur_state = int(act_struct.find(".//state_info").get("state", "1"))
        cur_line.append(logging_tools.form_entry(rc_strs[cur_state], header="status"))
        if not opt_ns.failed or (opt_ns.failed and cur_state in [SERVICE_DEAD, SERVICE_NOT_CONFIGURED]):
            out_bl.append(cur_line)
    print(datetime.datetime.now().strftime("%a, %d. %b %Y %d %H:%M:%S"))
    # _lines = unicode(out_bl).split("\n")
    # if iteration and len(_lines) > 2:
    #    print "\n".join(_lines[2:])
    # else:
    #    print "\n".join(_lines)
    print(unicode(out_bl))


def do_action_xml(opt_ns, res_xml):
    mode = opt_ns.mode
    if mode in ["restart", "start"]:
        structs = res_xml.xpath("instance[result and @startstop='1' and not (.//pid)]")
    elif mode in ["stop"]:
        structs = res_xml.xpath("instance[result and @startstop='1' and (.//pid)]")
    else:
        structs = []
    if not opt_ns.quiet:
        print(
            "{}ing {}: {}".format(
                mode,
                logging_tools.get_plural("instance", len(structs)),
                ", ".join([cur_el.attrib["name"] for cur_el in structs])
            )
        )
    for cur_el in structs:
        cur_name = cur_el.attrib["name"]
        init_script = os.path.join("/", "etc", "init.d", cur_el.get("init_script_name", cur_name))
        if os.path.exists(init_script):
            op_mode = "start" if mode == "start" else ("force-{}".format(mode) if opt_ns.force and int(cur_el.get("has_force_stop", "0")) else mode)
            cur_com = "{} {}".format(
                init_script, op_mode
            )
            if not opt_ns.quiet:
                print("calling {}".format(cur_com))
            _ret_val = subprocess.call(cur_com, shell=True)
        else:
            if not opt_ns.quiet:
                print(
                    "init-script '{}' for {} does not exist".format(
                        init_script,
                        cur_name,
                    )
                )


def log_com(what, log_level):
    print(u"[{}] {}".format(logging_tools.get_log_level_str(log_level), what))


class ICSWParser(object):
    def __init__(self):
        self._parser = argparse.ArgumentParser(prog="icsw")
        sub_parser = self._parser.add_subparsers(help="sub-command help")
        self._add_status_parser(sub_parser)
        self._add_start_parser(sub_parser)
        self._add_stop_parser(sub_parser)
        self._add_restart_parser(sub_parser)

    def _add_status_parser(self, sub_parser):
        _srvc = sub_parser.add_parser("status", help="service status")
        _srvc.set_defaults(subcom="status")
        _srvc.add_argument("-t", dest="thread", action="store_true", default=False, help="thread overview [%(default)s]")
        _srvc.add_argument("-s", dest="started", action="store_true", default=False, help="start info [%(default)s]")
        _srvc.add_argument("-p", dest="pid", action="store_true", default=False, help="show pid info [%(default)s]")
        _srvc.add_argument("-d", dest="database", action="store_true", default=False, help="show database info [%(default)s]")
        _srvc.add_argument("-m", dest="memory", action="store_true", default=False, help="memory consumption [%(default)s]")
        _srvc.add_argument("-a", dest="almost_all", action="store_true", default=False, help="almost all of the above, except start and DB info [%(default)s]")
        _srvc.add_argument("-A", dest="all", action="store_true", default=False, help="all of the above [%(default)s]")
        _srvc.add_argument("-v", dest="version", default=False, action="store_true", help="show version info [%(default)s]")
        self._add_iccs_sel(_srvc)
        # _srvc.add_argument("--mode", type=str, default="show", choices=["show", "stop", "start", "restart"], help="operation mode [%(default)s]")
        _srvc.add_argument("--failed", default=False, action="store_true", help="show only instances in failed state [%(default)s]")
        _srvc.add_argument("--every", default=0, type=int, help="check again every N seconds, only available for show [%(default)s]")

    def _add_start_parser(self, sub_parser):
        _act = sub_parser.add_parser("start", help="start service")
        _act.set_defaults(subcom="start")
        _act.add_argument("-q", dest="quiet", default=False, action="store_true", help="be quiet [%(default)s]")
        self._add_iccs_sel(_act)

    def _add_stop_parser(self, sub_parser):
        _act = sub_parser.add_parser("stop", help="stop service")
        _act.set_defaults(subcom="stop")
        _act.add_argument("-q", dest="quiet", default=False, action="store_true", help="be quiet [%(default)s]")
        self._add_iccs_sel(_act)

    def _add_restart_parser(self, sub_parser):
        _act = sub_parser.add_parser("restart", help="restart service")
        _act.set_defaults(subcom="restart")
        _act.add_argument("-q", dest="quiet", default=False, action="store_true", help="be quiet [%(default)s]")
        self._add_iccs_sel(_act)

    def _add_iccs_sel(self, _parser):
        _parser.add_argument("service", nargs="*", type=str, help="list of services")

    @staticmethod
    def get_default_ns():
        def_ns = argparse.Namespace(
            all=True,
            instance=[],
            system=[],
            server=[],
            client=[],
            memory=True,
            database=True,
            pid=True,
            started=True,
            thread=True,
            version=True,
        )
        return def_ns

    def parse_args(self):
        opt_ns = self._parser.parse_args()
        if hasattr(opt_ns, "instance"):
            if not opt_ns.instance and not opt_ns.client and not opt_ns.server and not opt_ns.system:
                opt_ns.instance = ["ALL"]
        if opt_ns.subcom == "status":
            if opt_ns.all or opt_ns.almost_all:
                opt_ns.thread = True
                opt_ns.pid = True
                opt_ns.memory = True
                opt_ns.version = True
            if opt_ns.all:
                opt_ns.started = True
        return opt_ns


def main():
    cur_c = ServiceContainer(log_com)
    opt_ns = ICSWParser().parse_args()
    if os.getuid():
        print("Not running as root, information may be incomplete, disabling display of memory")
        opt_ns.memory = False
    inst_xml = cur_c.get_instance_xml()
    # if not len(inst_xml.xpath("instance[result]")):
    #    print("Nothing to do")
    #    sys.exit(1)

    if opt_ns.subcom == "status":
        cur_c.check_system(opt_ns, inst_xml)
        _iter = 0
        while True:
            try:
                show_xml(opt_ns, inst_xml, _iter)
                if opt_ns.every:
                    time.sleep(opt_ns.every)
                    cur_c.check_system(opt_ns, inst_xml)
                    _iter += 1
                else:
                    break
            except KeyboardInterrupt:
                print("exiting...")
                break
    elif opt_ns.subcom in ["start", "stop", "restart"]:
        cur_c.actions(opt_ns, inst_xml)

if __name__ == "__main__":
    main()
