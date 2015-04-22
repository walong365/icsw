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

sys.path.insert(0, "/usr/local/share/home/local/development/git/icsw/")

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

from lxml import etree  # @UnresolvedImport
from lxml.builder import E  # @UnresolvedImport
import argparse
import commands
import datetime
from initat.tools import logging_tools
from initat.tools import process_tools
import psutil
import stat
import subprocess
import time

try:
    from django.conf import settings
except:
    settings = None
    config_tools = None
else:
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

EXTRA_SERVER_DIR = "/opt/cluster/etc/extra_servers.d"

# return values
SERVICE_OK = 0
SERVICE_DEAD = 1
SERVICE_NOT_INSTALLED = 5
# also if config not set or insufficient licenses
SERVICE_NOT_CONFIGURED = 6


def check_processes(name, pids, pid_thread_dict, any_ok):
    ret_state = SERVICE_NOT_CONFIGURED
    unique_pids = {key: pids.count(key) for key in set(pids)}
    pids_found = {key: pid_thread_dict.get(key, 1) for key in set(pids)}
    num_started = sum(unique_pids.values()) if unique_pids else 0
    num_found = sum(pids_found.values()) if pids_found else 0
    # check for extra Nagios2.x thread
    if any_ok and num_found:
        ret_state = SERVICE_OK
    elif num_started == num_found:
        ret_state = SERVICE_OK
    return ret_state, num_started, num_found


def get_instance_xml():
    instance_xml = E.instances()
    # check for additional instances
    if os.path.isdir(EXTRA_SERVER_DIR):
        for entry in os.listdir(EXTRA_SERVER_DIR):
            if entry.endswith(".xml"):
                try:
                    add_inst_list = etree.fromstring(open(os.path.join(EXTRA_SERVER_DIR, entry), "r").read())  # @UndefinedVariable
                except:
                    print(
                        "cannot read entry '{}' from {}: {}".format(
                            entry,
                            EXTRA_SERVER_DIR,
                            process_tools.get_except_info(),
                        )
                    )
                else:
                    for sub_inst in add_inst_list.findall("instance"):
                        instance_xml.append(sub_inst)
    for cur_el in instance_xml.findall("instance"):
        name = cur_el.attrib["name"]
        for key, def_value in [
            ("runs_on", "server"),
            ("any_threads_ok", "0"),
            ("pid_file_name", "{}.pid".format(name)),
            ("init_script_name", name),
            ("startstop", "1"),
            ("checked", "0"),
            ("to_check", "0"),
            ("process_name", name),
            ("meta_server_name", name),
        ]:
            if key not in cur_el.attrib:
                cur_el.attrib[key] = def_value
    return instance_xml


class ServiceContainer(object):
    def __init__(self, log_com):
        self.__log_com = log_com

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_com(u"[SrvC] {}".format(what), log_level)

    def get_default_ns(self):
        def_ns = argparse.Namespace(
            all=True,
            instance=[],
            system=[],
            server=[],
            client=[],
            memory=True,
            database=True,
            pid=True,
            time=True,
            thread=True,
            no_database=False,
            version=True,
        )
        return def_ns

    def _check_simple(self, entry):
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
            else:
                act_state, act_str = (SERVICE_DEAD, "not running")
        else:
            act_state, act_str = (SERVICE_NOT_INSTALLED, "not installed")
        entry.append(E.state_info(act_str, state="{:d}".format(act_state)))
        entry.attrib["check_source"] = "simple"

    def _check_meta(self, entry):
        init_script_name = os.path.join("/etc", "init.d", entry.attrib["init_script_name"])
        c_name = entry.attrib["meta_server_name"]
        ms_name = os.path.join("/var", "lib", "meta-server", c_name)
        if os.path.exists(ms_name):
            pid_time = os.stat(ms_name)[stat.ST_CTIME]
            ms_block = process_tools.meta_server_info(ms_name)
            ms_block.check_block(self.__pid_thread_dict, self.__act_proc_dict)
            diff_dict = {key: value for key, value in ms_block.bound_dict.iteritems() if value}
            diff_threads = sum(ms_block.bound_dict.values())
            act_pids = ms_block.pids_found
            num_started = len(act_pids)
            if diff_threads:
                act_state = SERVICE_NOT_CONFIGURED
                num_found = num_started
                num_diff = diff_threads
            else:
                act_state = SERVICE_OK
                num_found = num_started
                num_diff = 0
            # print ms_block.pids, ms_block.pid_check_string
            entry.attrib["check_source"] = "meta"
            entry.append(
                E.state_info(
                    *[
                        E.diff_info(
                            pid="{:d}".format(key),
                            diff="{:d}".format(value)
                        ) for key, value in diff_dict.iteritems()
                    ],
                    num_started="{:d}".format(num_started),
                    num_found="{:d}".format(num_found),
                    num_diff="{:d}".format(num_diff),
                    pid_time="{:d}".format(pid_time),
                    state="{:d}".format(act_state)
                ),
            )
        else:
            if os.path.isfile(init_script_name):
                act_state = SERVICE_DEAD
                entry.append(
                    E.state_info(
                        "no threads",
                        state="{:d}".format(act_state),
                    )
                )
            else:
                act_state = SERVICE_NOT_INSTALLED
                entry.append(
                    E.state_info(
                        "not installed",
                        state="{:d}".format(act_state),
                    )
                )

    def _check_pid_file(self, entry):
        name = entry.attrib["name"]
        pid_file_name = entry.attrib["pid_file_name"]
        if not pid_file_name.startswith("/"):
            pid_file_name = os.path.join("/var", "run", pid_file_name)
        pid_time = os.stat(pid_file_name)[stat.ST_CTIME]
        act_pids = [int(line.strip()) for line in file(pid_file_name, "r").read().split("\n") if line.strip().isdigit()]
        act_state, num_started, num_found = check_processes(name, act_pids, self.__pid_thread_dict, True if int(entry.attrib["any_threads_ok"]) else False)
        num_diff = 0
        diff_dict = {}
        entry.attrib["check_source"] = "pid"
        entry.append(
            E.state_info(
                *[
                    E.diff_info(
                        pid="{:d}".format(key),
                        diff="{:d}".format(value)
                    ) for key, value in diff_dict.iteritems()
                ],
                num_started="{:d}".format(num_started),
                num_found="{:d}".format(num_found),
                num_diff="{:d}".format(num_diff),
                pid_time="{:d}".format(pid_time),
                state="{:d}".format(act_state)
            ),
        )

    def check_system(self, opt_ns):
        INIT_BASE = "/opt/python-init/lib/python/site-packages/initat"
        instance_xml = get_instance_xml()
        set_all_servers = True if (opt_ns.server == ["ALL"] or opt_ns.instance == ["ALL"]) else False
        set_all_clients = True if (opt_ns.client == ["ALL"] or opt_ns.instance == ["ALL"]) else False
        set_all_system = True if (opt_ns.system == ["ALL"] or opt_ns.instance == ["ALL"]) else False
        if set_all_servers:
            opt_ns.server = instance_xml.xpath(".//*[@runs_on='server']/@name", smart_strings=False)
        if set_all_clients:
            opt_ns.client = instance_xml.xpath(".//*[@runs_on='client']/@name", smart_strings=False)
        if set_all_system:
            opt_ns.system = instance_xml.xpath(".//*[@runs_on='system']/@name", smart_strings=False)
        for cur_el in instance_xml.xpath(".//instance[@runs_on]", smart_strings=False):
            if cur_el.attrib["name"] in getattr(opt_ns, cur_el.attrib["runs_on"]) or cur_el.attrib["name"] in opt_ns.instance:
                cur_el.attrib["to_check"] = "1"
        self.__act_proc_dict = process_tools.get_proc_list_new()
        self.__pid_thread_dict = process_tools.get_process_id_list(True, True)
        _prev_db_check = None
        for entry in instance_xml.xpath("instance[@to_check='1']"):
            dev_config = []
            if config_tools and not opt_ns.no_database and entry.find(".//config_names/config_name") is not None:
                # dev_config = config_tools.device_with_config(entry.findtext(".//config_names/config_name"))
                _conf_names = [_entry.text for _entry in entry.findall(".//config_names/config_name")]
                for _conf_name in _conf_names:
                    _cr = config_tools.server_check(server_type=_conf_name, prev_check=_prev_db_check)
                    _prev_db_check = _cr
                    if _cr.effective_device:
                        dev_config.append(_cr)

            name = entry.attrib["name"]
            entry.attrib["checked"] = "1"
            act_pids = []
            init_script_name = os.path.join("/etc", "init.d", entry.attrib["init_script_name"])
            if entry.attrib["check_type"] == "simple":
                self._check_simple(entry)
            elif entry.attrib["check_type"] == "meta":
                self._check_meta(entry)
            elif entry.attrib["check_type"] == "pid_file":
                self._check_pid_file(entry)
            else:
                entry.append(E.state_info("unknown check_type '{}'".format(entry.attrib["check_type"]), state="1"))
            entry.append(
                E.pids(
                    *[E.pid("{:d}".format(cur_pid), count="{:d}".format(act_pids.count(cur_pid))) for cur_pid in set(act_pids)]
                )
            )
            act_state = int(entry.find("state_info").attrib["state"])
            if entry.attrib["runs_on"] == "server":
                if dev_config:  # is not None:
                    sql_info = ", ".join([_dc.server_info_str for _dc in dev_config])
                else:
                    act_state = SERVICE_NOT_CONFIGURED
                    sql_info = "not configured"
                    # update state info
                    _state_info = entry.find("state_info")
                    _state_info.text = "not configured"
                    _state_info.attrib["state"] = "{:d}".format(act_state)
            else:
                sql_info = entry.attrib["runs_on"]
            if type(sql_info) == str:
                entry.append(
                    E.sql_info(str(sql_info))
                )
            else:
                entry.append(
                    E.sql_info("{} ({})".format(
                        sql_info.server_info_str,
                        sql_info.config_name),
                    )
                )
            entry.append(
                E.memory_info(
                    "{:d}".format(sum(process_tools.get_mem_info(cur_pid) for cur_pid in set(act_pids))) if act_pids else "",
                )
            )
            if entry.get("runs_on") in ["client", "server"] and act_state != SERVICE_NOT_INSTALLED:
                entry.attrib["version_ok"] = "0"
                try:
                    _path = "%{INIT_BASE}/{runs_on}_version.py".replace("%{INIT_BASE}", INIT_BASE).format(**dict(entry.attrib))
                    _lines = file(_path, "r").read().split("\n")
                    _vers_lines = [_line for _line in _lines if _line.startswith("VERSION_STRING")]
                    if _vers_lines:
                        entry.attrib["version_ok"] = "1"
                        entry.attrib["version"] = _vers_lines[0].split("=", 1)[1].strip().replace('"', "").replace("'", "")
                    else:
                        entry.attrib["version"] = "no version lines found in '{}'".format(_path)
                except:
                    entry.attrib["version"] = "error getting version: {}".format(process_tools.get_except_info())
        return instance_xml




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
        key: "{}{}{}".format(col_str_dict[wc], value, col_str_dict[3]) for key, (wc, value) in rc_dict.iteritems()
    }
    out_bl = logging_tools.new_form_list()
    types = ["client", "server", "system"]
    _list = sum([res_xml.xpath("instance[@checked='1' and @runs_on='{}']".format(_type)) for _type in types], [])
    for act_struct in _list:
        cur_line = [logging_tools.form_entry(act_struct.attrib["name"], header="Name")]
        cur_line.append(logging_tools.form_entry(act_struct.attrib["runs_on"], header="type"))
        cur_line.append(logging_tools.form_entry(act_struct.attrib.get("check_source", "N/A"), header="source"))
        if opt_ns.time or opt_ns.thread:
            s_info = act_struct.find("state_info")
            if "num_started" not in s_info.attrib:
                cur_line.append(logging_tools.form_entry(s_info.text))
            else:
                num_started, num_found, num_diff, pid_time, any_ok = (
                    int(s_info.get("num_started")),
                    int(s_info.get("num_found")),
                    int(s_info.get("num_diff")),
                    int(s_info.get("pid_time", "0")),
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
                if opt_ns.time:
                    if pid_time:
                        diff_time = max(0, time.mktime(time.localtime()) - pid_time)
                        diff_days = int(diff_time / (3600 * 24))
                        diff_hours = int((diff_time - 3600 * 24 * diff_days) / 3600)
                        diff_mins = int((diff_time - 3600 * (24 * diff_days + diff_hours)) / 60)
                        diff_secs = int(diff_time - 60 * (60 * (24 * diff_days + diff_hours) + diff_mins))
                        ret_str += ", stable since {}{:02d}:{:02d}:{:02d} ({})".format(
                            diff_days and "{}, ".format(logging_tools.get_plural("day", diff_days)) or "",
                            diff_hours,
                            diff_mins,
                            diff_secs,
                            time.strftime("%a, %d. %b %Y, %H:%M:%S", time.localtime(pid_time)))
                    else:
                        ret_str += ", no pid found"
                cur_line.append(logging_tools.form_entry(ret_str, header="Thread and time info" if opt_ns.time else "Thread info"))
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
            cur_mem = act_struct.find("memory_info").text
            if cur_mem.isdigit():
                mem_str = process_tools.beautify_mem_info(int(cur_mem))
            else:
                # no pids hence no memory info
                mem_str = "no pids"
            cur_line.append(logging_tools.form_entry_right(mem_str, header="Memory"))
        if opt_ns.version:
            if "version" in act_struct.attrib:
                _version = act_struct.attrib["version"]
            else:
                _version = ""
            cur_line.append(logging_tools.form_entry_right(_version, header="Version"))
        cur_state = int(act_struct.find("state_info").get("state", "1"))
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


def do_action_xml(opt_ns, res_xml, mode):
    structs = res_xml.xpath("instance[@checked='1' and @startstop='1']")
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


def main():
    my_parser = argparse.ArgumentParser()
    my_parser.add_argument("-t", dest="thread", action="store_true", default=False, help="thread overview (%(default)s)")
    my_parser.add_argument("-T", dest="time", action="store_true", default=False, help="full time info (implies -t,  %(default)s)")
    my_parser.add_argument("-p", dest="pid", action="store_true", default=False, help="show pid info (%(default)s)")
    my_parser.add_argument("-d", dest="database", action="store_true", default=False, help="show database info (%(default)s)")
    my_parser.add_argument("-m", dest="memory", action="store_true", default=False, help="memory consumption (%(default)s)")
    my_parser.add_argument("-a", dest="almost_all", action="store_true", default=False, help="almost all of the above, except time and DB info (%(default)s)")
    my_parser.add_argument("-A", dest="all", action="store_true", default=False, help="all of the above (%(default)s)")
    my_parser.add_argument("-q", dest="quiet", default=False, action="store_true", help="be quiet [%(default)s]")
    my_parser.add_argument("-v", dest="version", default=False, action="store_true", help="show version info [%(default)s]")
    my_parser.add_argument("--instance", type=str, nargs="+", default=[], help="general instance names (%(default)s)")
    my_parser.add_argument("--client", type=str, nargs="+", default=[], help="client entity names (%(default)s)")
    my_parser.add_argument("--server", type=str, nargs="+", default=[], help="server entity names (%(default)s)")
    my_parser.add_argument("--system", type=str, nargs="+", default=[], help="system entity names (%(default)s)")
    my_parser.add_argument("--mode", type=str, default="show", choices=["show", "stop", "start", "restart"], help="operation mode [%(default)s]")
    my_parser.add_argument("--force", default=False, action="store_true", help="call force-stop if available [%(default)s]")
    my_parser.add_argument("--failed", default=False, action="store_true", help="show only instances in failed state [%(default)s]")
    my_parser.add_argument("--every", default=0, type=int, help="check again every N seconds, only available for show [%(default)s]")
    my_parser.add_argument("--no-database", default=False, action="store_true", help="disable use of database [%(default)s]")
    cur_c = ServiceContainer(log_com)
    opt_ns = my_parser.parse_args()
    if opt_ns.all or opt_ns.almost_all:
        opt_ns.thread = True
        opt_ns.pid = True
        opt_ns.memory = True
        opt_ns.version = True
    if opt_ns.all:
        opt_ns.time = True
        opt_ns.database = True
    if os.getuid():
        print("Not running as root, information may be incomplete, disabling display of memory")
        opt_ns.memory = False
    ret_xml = cur_c.check_system(opt_ns)
    if not len(ret_xml.xpath("instance[@checked='1']")):
        print("Nothing to do")
        sys.exit(1)

    if opt_ns.mode == "show":
        _iter = 0
        while True:
            try:
                show_xml(opt_ns, ret_xml, _iter)
                if opt_ns.every:
                    time.sleep(opt_ns.every)
                    ret_xml = check_system(opt_ns)
                    _iter += 1
                else:
                    break
            except KeyboardInterrupt:
                print("exiting...")
                break
    elif opt_ns.mode in ["start", "stop", "restart"]:
        do_action_xml(opt_ns, ret_xml, opt_ns.mode)

if __name__ == "__main__":
    main()
