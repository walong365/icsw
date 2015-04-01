#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008,2009,2011,2012,2013 Andreas Lang-Nevyjel, init.at
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

import sys
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

import commands
import stat
import time
import process_tools
import logging_tools
import extra_server_tools
import argparse
try:
    import config_tools
except:
    config_tools = None

def check_threads(name, pids, any_ok):
    ret_state = 7
    unique_pids = dict([(key, pids.count(key)) for key in set(pids)])
    pids_found = dict([(key, 0) for key in set(pids)])
    for pid in unique_pids.keys():
        stat_f = "/proc/%d/status" % (pid)
        if os.path.isfile(stat_f):
            stat_dict = dict([line.strip().lower().split(":", 1) for line in file(stat_f, "r").read().replace("\t", " ").split("\n") if line.count(":") and line.strip()])
            if "threads" in stat_dict:
                pids_found[pid] += int(stat_dict.get("threads", "1"))
            else:
                pids_found[pid] += 1
    num_started = sum(unique_pids.values()) if unique_pids else 0
    num_found = sum(pids_found.values()) if pids_found else 0
    # check for extra Nagios2.x thread
    if any_ok and num_found:
        ret_state = 0
    elif num_started == num_found:
        ret_state = 0
    return ret_state, num_started, num_found

def check_system(opt_ns):
    if not opt_ns.server and not opt_ns.node:
        set_default_nodes, set_default_servers = (True , True)
    else:
        set_default_nodes, set_default_servers = (False, False)
    if opt_ns.server == ["ALL"]:
        set_default_servers = True
    if opt_ns.node == ["ALL"]:
        set_default_nodes = True
    if set_default_nodes:
        opt_ns.node = [
            "hoststatus:simple:hoststatus_zmq",
            "logging-server",
            "meta-server",
            "host-monitoring",
            "package-client",
            "gmond:simple:gmond",
        ]
    if set_default_servers:
        opt_ns.server = [
            "logcheck-server",
            "package-server",
            "mother",
            "rrd-grapher",
            "sge-server",
            "cluster-server",
            "cluster-config-server",
            # "xen-server",
            "host-relay",
            "snmp-relay",
            "md-config-server"]
        if os.path.isfile("/etc/init.d/icinga"):
            opt_ns.server.append("monitoring:threads_by_pid_file:/opt/icinga/var/icinga.lock:1")
        elif os.path.isfile("/etc/init.d/nagios"):
            opt_ns.server.append("monitoring:threads_by_pid_file:/opt/nagios/var/nagios.lock:1")
        opt_ns.server.extend(extra_server_tools.extra_server_file().get_server_list())

    check_dict, check_list = ({}, [])
    for c_type in ["node", "server"]:
        c_list = getattr(opt_ns, c_type)
        for name in c_list:
            if name.count(":"):
                name, check_type = name.split(":", 1)
            else:
                check_type = "threads_by_pid_file"
            if check_type.count(":"):
                check_type, pid_file_name = check_type.split(":", 1)
            else:
                pid_file_name = ""
            if pid_file_name.count(":"):
                pid_file_name, any_ok = pid_file_name.split(":", 1)
                any_ok = True if int(any_ok) else False
            else:
                any_ok = False
            check_list.append(name)
            check_dict[name] = {"type"          : c_type,
                                "check_type"    : check_type,
                                # pid_file_name or process_name for simple check
                                "pid_file_name" : pid_file_name,
                                # any number of threads OK
                                "any_ok"        : any_ok,
                                "init_script"   : "/etc/init.d/%s" % (name)}
    ret_dict = {}
    if check_list:
    # pid-file mapping
        pid_file_map = {
            "host-monitoring"      : "collserver/collserver.pid",
            "logging-server"       : "logserver/logserver.pid",
            "meta-server"          : "meta-server.pid",
            "rrd-grapher"          : "rrd-grapher/rrd-grapher.pid",
            "host-relay"           : "collrelay/collrelay.pid",
            # "xen-server"           : "xen-server.pid",
            "cluster-server"       : "cluster-server.pid",
            "ansys"                : "ansys-server/ansys-server.pid",
            "cransys"              : "cransys-server/cransys-server.pid"}
        # server-type mapping
        server_type_map = {
            "mother"                : "mother_server",
            "logcheck-server"       : "syslog_server",
            "cluster-server"        : "server",
            "snmp-relay"            : "monitor_server",
            "cluster-config-server" : "config_server",
            "host-relay"            : "monitor_server",
            "monitoring"            : "monitor_server",
            "md-config-server"      : "monitor_server",
            "cransys"               : "cransys_server",
            "rrd-grapher"           : "rrd_server",
            "ansys"                 : "ansys_server"}
        # server-type to runlevel-name mapping
        runlevel_map = {
            "ansys"   : "ansys-server",
            "cransys" : "cransys-server"}
        act_proc_dict = process_tools.get_proc_list()
        stat_dict = {}
        if opt_ns.runlevel or opt_ns.all:
            for check in check_list:
                r_stat, out = commands.getstatusoutput("chkconfig --list %s" % (runlevel_map.get(check, check)))
                if r_stat:
                    stat_dict[check] = "Error getting config (%d): %s" % (r_stat, out)
                elif out.count(":") < 5:
                    stat_dict[check] = "Error getting config: %s" % (out)
                else:
                    stat_dict[check] = [line.strip().split(None, 1) for line in out.split("\n")][-1][1].lower()
                    stat_dict[check] = [int(k2) for k2, _val in [part.split(":") for part in stat_dict[check].split()] if _val == "on"]
        ret_dict["check_list"] = []
        for name in check_list:
            ret_dict["check_list"].append(name)
            check_struct = check_dict[name]
            act_info_dict = {"name" : name}
            act_pids = []
            if check_struct["check_type"] == "simple":
                if os.path.isfile(check_struct["init_script"]):
                    running_procs = [pid for pid in act_proc_dict.values() if pid["name"] == check_struct["pid_file_name"]]
                    if running_procs:
                        act_state, act_str = (0, "running")
                        act_pids = [p_struct["pid"] for p_struct in running_procs]
                    else:
                        act_state, act_str = (7, "not running")
                else:
                    act_state, act_str = (5, "not installed")
                act_info_dict["state_info"] = act_str
            elif check_struct["check_type"] == "threads_by_pid_file":
                pid_file_name = check_struct["pid_file_name"]
                if not pid_file_name:
                    pid_file_name = pid_file_map.get(name, "%s/%s.pid" % (name, name))
                if not pid_file_name.startswith("/"):
                    pid_file_name = "/var/run/%s" % (pid_file_name)
                if os.path.isfile(pid_file_name):
                    pid_time = os.stat(pid_file_name)[stat.ST_CTIME]
                    act_pids = [int(line.strip()) for line in file(pid_file_name, "r").read().split("\n") if line.strip().isdigit()]
                    act_state, num_started, num_found = check_threads(name, act_pids, check_struct["any_ok"])
                    act_info_dict["state_info"] = (num_started, num_found, pid_time)
                else:
                    if os.path.isfile(check_struct["init_script"]):
                        act_state = 7
                        act_info_dict["state_info"] = "no threads"
                    else:
                        act_state = 5
                        act_info_dict["state_info"] = "not installed"
            else:
                act_state = 1
                act_info_dict["state_info"] = "Unknown check_type '%s'" % (check_struct["check_type"])
            act_info_dict["pids"] = dict([(key, act_pids.count(key)) for key in set(act_pids)])
            if check_struct["type"] == "server":
                if config_tools:
                    srv_type = server_type_map.get(name, name.replace("-", "_"))
                    try:
                        sql_info = config_tools.server_check(server_type="%s" % (srv_type))
                    except:
                        sql_info = "no db_con"
                    else:
                        if not sql_info.effective_device:
                            act_state = 5
                else:
                    sql_info = "no db_con"
            else:
                sql_info = "node"
            act_info_dict["sql"] = sql_info
            if name in stat_dict:
                act_info_dict["runlevels"] = stat_dict[name]
            else:
                act_info_dict["runlevels"] = None
            act_info_dict["mem"] = act_pids and sum(process_tools.get_mem_info(cur_pid) for cur_pid in set(act_pids)) or None
            act_info_dict["state"] = act_state
            ret_dict[name] = act_info_dict
    return ret_dict

def get_default_ns():
    def_ns = argparse.Namespace(all=True, server=[], node=[], runlevel=True, memory=True, database=True, pid=True, time=True, thread=True)
    return def_ns

def main():
    my_parser = argparse.ArgumentParser()
    my_parser.add_argument("-t", dest="thread", action="store_true", default=False, help="thread overview (%(default)s)")
    my_parser.add_argument("-T", dest="time", action="store_true", default=False, help="full time info (implies -t,  %(default)s)")
    my_parser.add_argument("-p", dest="pid", action="store_true", default=False, help="show pid info (%(default)s)")
    my_parser.add_argument("-d", dest="database", action="store_true", default=False, help="show database info (%(default)s)")
    my_parser.add_argument("-r", dest="runlevel", action="store_true", default=False, help="runlevel info (%(default)s)")
    my_parser.add_argument("-m", dest="memory", action="store_true", default=False, help="memory consumption (%(default)s)")
    my_parser.add_argument("-a", dest="all", action="store_true", default=False, help="all of the above (%(default)s)")
    my_parser.add_argument("--node", type=str, nargs="+", default=[], help="node checks (%(default)s)")
    my_parser.add_argument("--server", type=str, nargs="+", default=[], help="server checks (%(default)s)")
    opt_ns = my_parser.parse_args()
    ret_dict = check_system(opt_ns)
    if not ret_dict:
        print "Nothing to check"
        sys.exit(1)
    # color strings (green / yellow / red / normal)
    col_str_dict = {0 : "\033[1;32m",
                    1 : "\033[1;33m",
                    2 : "\033[1;31m",
                    3 : "\033[m\017"}
    rc_dict = {0 : (0, "running"),
               1 : (2, "error"),
               5 : (1, "skipped"),
               6 : (1, "not install"),
               7 : (2, "dead")}
    rc_strs = dict([(key, "%s%s%s" % (col_str_dict[wc], value, col_str_dict[3]))
                    for key, (wc, value) in rc_dict.iteritems()])
    out_bl = logging_tools.form_list()
    head_l = ["Name"]
    if opt_ns.time or opt_ns.all:
        if opt_ns.thread or opt_ns.all:
            head_l.append("Thread and time info")
        else:
            head_l.append("Thread info")
    if opt_ns.pid or opt_ns.all:
        head_l.append("PIDs")
    if opt_ns.database or opt_ns.all:
        head_l.append("DB Info")
    if opt_ns.runlevel or opt_ns.all:
        head_l.append("runlevel(s)")
    if opt_ns.memory or opt_ns.all:
        head_l.append("Memory")
    head_l.append("state")
    out_bl.set_header_string(0, head_l)
    for name in ret_dict["check_list"]:
        act_struct = ret_dict[name]
        out_list = [name]
        if opt_ns.time or opt_ns.all:
            s_info = act_struct["state_info"]
            if type(s_info) == type(""):
                out_list.append(s_info)
            else:
                num_started, num_found, pid_time = s_info
                num_miss = num_started - num_found
                if num_miss > 0:
                    ret_str = "%s %s missing" % (
                        logging_tools.get_plural("thread", num_miss),
                        num_miss == 1 and "is" or "are")
                elif num_miss < 0:
                    ret_str = "%s too much" % (
                        logging_tools.get_plural("thread", -num_miss))
                else:
                    ret_str = "the thread is running" if num_started == 1 else "all %d threads running" % (num_started)
                if opt_ns.thread or opt_ns.all:
                    diff_time = max(0, time.mktime(time.localtime()) - pid_time)
                    diff_days = int(diff_time / (3600 * 24))
                    diff_hours = int((diff_time - 3600 * 24 * diff_days) / 3600)
                    diff_mins = int((diff_time - 3600 * (24 * diff_days + diff_hours)) / 60)
                    diff_secs = int(diff_time - 60 * (60 * (24 * diff_days + diff_hours) + diff_mins))
                    ret_str += ", pidfile unchanged since %s%02d:%02d:%02d (%s)" % (diff_days and "%s, " % (logging_tools.get_plural("day", diff_days)) or "",
                                                                                    diff_hours, diff_mins, diff_secs,
                                                                                    time.strftime("%a, %d. %b %Y, %H:%M:%S", time.localtime(pid_time)))
                out_list.append(ret_str)
        if opt_ns.pid or opt_ns.all:
            pid_dict = act_struct["pids"]
            if pid_dict:
                p_list = sorted(pid_dict.keys())
                if max(pid_dict.values()) == 1:
                    out_list.append(logging_tools.compress_num_list(p_list))
                else:
                    out_list.append(",".join(["%d%s" % (
                        key,
                        " (%d)" % (pid_dict[key]) if pid_dict[key] > 1 else "") for key in p_list]))
            else:
                out_list.append("no PIDs")
        if opt_ns.database or opt_ns.all:
            if type(act_struct["sql"]) == type(""):
                out_list.append(act_struct["sql"])
            else:
                out_list.append("%s (%s)" % (
                    act_struct["sql"].server_info_str,
                    act_struct["sql"].config_name))
        if opt_ns.runlevel or opt_ns.all:
            rlevs = act_struct["runlevels"]
            if type(rlevs) == type([]):
                if rlevs:
                    out_list.append("%s %s" % (
                        logging_tools.get_plural("level", rlevs, 0),
                        ", ".join(["%d" % (r_lev) for r_lev in rlevs])))
                else:
                    out_list.append("no levels")
            else:
                out_list.append("<no runlevel info>")
        if opt_ns.memory or opt_ns.all:
            out_list.append(act_struct["mem"] and process_tools.beautify_mem_info(act_struct["mem"]) or "no pids")
        out_list.append(rc_strs[act_struct["state"]])
        out_bl.add_line(out_list)
    print out_bl

if __name__ == "__main__":
    main()

