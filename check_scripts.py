#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008,2009,2011,2012 Andreas Lang-Nevyjel, init.at
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
import getopt
import os
import commands
import stat
import time
import process_tools
import logging_tools
import extra_server_tools
import config_tools
try:
    import mysql_tools
except ImportError:
    mysql_tools = None
else:
    import MySQLdb
    
SQL_ACCESS = "cluster_full_access"

def check_threads(name, pids):
    ret_state = 7
    unique_pids, pids_found = ({}, {})
    for pid in pids:
        unique_pids.setdefault(pid, 0)
        pids_found.setdefault(pid, 0)
        unique_pids[pid] += 1
    # flag if 'threads'-key in status
    has_t_key = False
    for pid in unique_pids.keys():
        stat_f = "/proc/%d/status" % (pid)
        if os.path.isfile(stat_f):
            stat_dict = dict([(z[0].lower(), z[1].strip()) for z in [y.split(":", 1) for y in [x.strip() for x in file(stat_f, "r").read().replace("\t", " ").split("\n") if x.count(":")]]])
            if "threads" in stat_dict:
                has_t_key = True
                pids_found[pid] += int(stat_dict.get("threads", "1"))
            else:
                pids_found[pid] += 1
    if not has_t_key:
        dot_files = [x for x in os.listdir("/proc") if x.startswith(".") and x[1:].isdigit()]
        for df in dot_files:
            stat_f = "/proc/%s/status" % (df)
            if os.path.isfile(stat_f):
                stat_dict = dict([(z[0].lower(), z[1].strip()) for z in [y.split(":", 1) for y in [x.strip() for x in file(stat_f, "r").read().replace("\t", " ").split("\n") if x.count(":")]]])
                if "ppid" in stat_dict:
                    ppid = int(stat_dict["ppid"])
                    if ppid in pids_found:
                        pids_found[ppid] += 1
    num_started = unique_pids and sum(unique_pids.values()) or 0
    num_found = pids_found and sum(pids_found.values()) or 0
    # check for extra Nagios2.x thread
    if name == "nagios" and num_started == 1 and num_found == 2:
        num_started = 2
    if num_started == num_found:
        ret_state = 0
    return ret_state, num_started, num_found

def get_default_opt_dict():
    return dict([(key, False) for key in ["full_status", "overview_mode", "db_info", "runlevel_info", "mem_info", "pid_info"]])

def check_system(opt_dict, checks, db_cursor):
    if not checks.setdefault("server", []) and not checks.setdefault("node", []):
        set_default_nodes, set_default_servers = (True, True)
    else:
        set_default_nodes, set_default_servers = (False, False)
    if checks["server"] == ["ALL"]:
        set_default_servers = True
    if checks["node"] == ["ALL"]:
        set_default_nodes = True
    if set_default_nodes:
        checks["node"] = ["hoststatus:simple",
                          "logging-server",
                          "meta-server",
                          "host-monitoring",
                          "package-client"]
    if set_default_servers:
        checks["server"] = ["logcheck-server",
                            "package-server",
                            "mother",
                            "rrd-server-collector",
                            "rrd-server-writer",
                            "rrd-server-grapher",
                            "sge-server",
                            #"sge-relayer",
                            "cluster-server",
                            "cluster-config-server",
                            "xen-server",
                            "host-relay",
                            "snmp-relay",
                            "nagios-config-server",
                            "nagios:threads_by_pid_file:/opt/nagios/var/nagios.lock"]
        checks["server"].extend(extra_server_tools.extra_server_file().get_server_list())
    check_dict, check_list = ({}, [])
    for c_type, c_list in checks.iteritems():
        for name in c_list:
            if name.count(":"):
                name, check_type = name.split(":", 1)
            else:
                check_type = "threads_by_pid_file"
            if check_type.count(":"):
                check_type, pid_file_name = check_type.split(":", 1)
            else:
                pid_file_name = ""
            check_list.append(name)
            check_dict[name] = {"type"          : c_type,
                                "check_type"    : check_type,
                                "pid_file_name" : pid_file_name,
                                "init_script"   : "/etc/init.d/%s" % (name)}
    ret_dict = {}
    if check_list:
    # pid-file mapping
        pid_file_map = {"host-monitoring"      : "collserver/collserver.pid",
                        "logging-server"       : "logserver/logserver.pid",
                        "meta-server"          : "meta-server.pid",
                        "rrd-server-collector" : "rrd-server/rrd-server-collector.pid",
                        "rrd-server-writer"    : "rrd-server/rrd-server-writer.pid",
                        "rrd-server-grapher"   : "rrd-server/rrd-server-grapher.pid",
                        "host-relay"           : "collrelay/collrelay.pid",
                        "xen-server"           : "xen-server.pid",
                        "cluster-server"       : "cluster-server.pid",
                        "ansys"                : "ansys-server/ansys-server.pid",
                        "cransys"              : "cransys-server/cransys-server.pid"}
        # server-type mapping
        server_type_map = {"mother"                : "mother_server",
                           "cluster-server"        : "server",
                           "snmp-relay"            : "nagios_master",
                           "cluster-config-server" : "config_server",
                           "host-relay"            : "nagios_master",
                           "nagios"                : "nagios_master",
                           "nagios-config-server"  : "nagios_master",
                           "cransys"               : "cransys_server",
                           "ansys"                 : "ansys_server"}
        # server-type to runlevel-name mapping
        runlevel_map = {"ansys"   : "ansys-server",
                        "cransys" : "cransys-server"}
        act_proc_dict = process_tools.get_proc_list()
        stat_dict = {}
        if opt_dict["runlevel_info"]:
            for check in check_list:
                r_stat, out = commands.getstatusoutput("chkconfig --list %s" % (runlevel_map.get(check, check)))
                if r_stat:
                    stat_dict[check] = "Error getting config (%d): %s" % (r_stat, out)
                elif out.count(":") < 5:
                    stat_dict[check] = "Error getting config: %s" % (out)
                else:
                    stat_dict[check] = [line.strip().split(None, 1) for line in out.split("\n")][-1][1].lower()
                    stat_dict[check] = [int(k2) for k2, v in [x.split(":") for x in stat_dict[check].split()] if v == "on"]
        ret_dict["check_list"] = []
        for name in check_list:
            ret_dict["check_list"].append(name)
            check_struct = check_dict[name]
            act_info_dict = {"name" : name}
            act_pids = []
            if check_struct["check_type"] == "simple":
                if os.path.isfile(check_struct["init_script"]):
                    running_procs = [x for x in act_proc_dict.values() if x["name"] == name]
                    if running_procs:
                        act_state, act_str = (0, "running")
                        act_pids = [x["pid"] for x in running_procs]
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
                    act_pids = [int(x) for x in [y.strip() for y in file(pid_file_name, "r").read().split("\n")] if x]
                    
                    act_state, num_started, num_found = check_threads(name, act_pids)
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
            pid_dict = {}
            for act_pid in act_pids:
                pid_dict.setdefault(act_pid, 0)
                pid_dict[act_pid] += 1
            act_info_dict["pids"] = pid_dict
            if check_struct["type"] == "server":
                if db_cursor:
                    srv_type = server_type_map.get(name, name.replace("-", "_"))
                    sql_info = config_tools.server_check(dc=db_cursor, server_type="%s%%" % (srv_type))
                    if not sql_info.num_servers:
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
    
def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], "dtrTahmp", ["node=", "server=", "help"])
    except getopt.GetoptError:
        exc_info = sys.exc_info()
        print "Error parsing commandline %s: %s (%s)" % (" ".join(sys.argv[1:]), str(exc_info[0]).strip(), str(exc_info[1]).strip())
        sys.exit(-1)
    opt_dict = get_default_opt_dict()
    checks = {"node"   : [],
              "server" : []}
    for opt, arg in opts:
        if opt in ["-h", "--help"]:
            print "Usage: %s [options] [--node NODE-SCRIPTS] [--server SERVER-SCRIPTS]" % (os.path.basename(sys.argv[0]))
            print "  where options is one or more of"
            print "  -h, --help       this help"
            print "  -t               thread overview"
            print "  -T               full time info (implies -t)"
            print "  -p               show pid info"
            print "  -d               show database info"
            print "  -r               runlevel info"
            print "  -m               show info about memory consumption"
            print "  -a               all of the above"
            sys.exit(0)
        if opt == "-T":
            opt_dict["full_status"] = True
            opt_dict["overview_mode"] = True
        if opt == "-t":
            opt_dict["overview_mode"] = True
        if opt == "-p":
            opt_dict["pid_info"] = True
        if opt == "-r":
            opt_dict["runlevel_info"] = True
        if opt == "-d":
            opt_dict["db_info"] = True
        if opt == "-m":
            opt_dict["mem_info"] = True
        if opt == "-a":
            opt_dict = dict([(k, True) for k in opt_dict.keys()])
        if opt == "--node":
            checks["node"] = [x.strip() for x in arg.split(",")]
        if opt == "--server":
            checks["server"] = [x.strip() for x in arg.split(",")]
    if args:
        print "Some (%s) left unparsed: %s" % (logging_tools.get_plural("argument", args), " ".join(args))
        sys.exit(-1)
    if mysql_tools:
        db_con = mysql_tools.dbcon_container()
        try:
            dc = db_con.get_connection(SQL_ACCESS)
        except MySQLdb.OperationalError:
            dc = None
    else:
        dc = None
        print "Warning, no mysql_tools found"
    ret_dict = check_system(opt_dict, checks, dc)
    if dc:
        dc.release()
    if not ret_dict:
        print "Nothing to check"
        sys.exit(1)
    # color strings (green / yellow / red / normal)
    col_str_dict = {0 : "\033[1;32m",
                    1 : "\033[1;33m",
                    2 : "\033[1;31m",
                    3 : "\033[m\017"}
    rc_dict = {0 : (0, "running"    ),
               1 : (2, "error"      ),
               5 : (1, "skipped"    ),
               6 : (1, "not install"),
               7 : (2, "dead"       )}
    rc_strs = dict([(k, "%s%s%s" % (col_str_dict[wc], v, col_str_dict[3])) for k, (wc, v) in rc_dict.iteritems()])
    out_bl = logging_tools.form_list()
    head_l = ["Name"]
    if opt_dict["overview_mode"]:
        if opt_dict["full_status"]:
            head_l.append("Thread and time info")
        else:
            head_l.append("Thread info")
    if opt_dict["pid_info"]:
        head_l.append("PIDs")
    if opt_dict["db_info"]:
        head_l.append("DB Info")
    if opt_dict["runlevel_info"]:
        head_l.append("runlevel(s)")
    if opt_dict["mem_info"]:
        head_l.append("Memory")
    head_l.append("state")
    out_bl.set_header_string(0, head_l)
    for name in ret_dict["check_list"]:
        act_struct = ret_dict[name]
        out_list = [name]
        if opt_dict["overview_mode"]:
            s_info = act_struct["state_info"]
            if type(s_info) == type(""):
                out_list.append(s_info)
            else:
                num_started, num_found, pid_time = s_info
                num_miss = num_started - num_found
                if num_miss > 0:
                    ret_str = "%s %s missing" % (logging_tools.get_plural("thread", num_miss),
                                                 num_miss == 1 and "is" or "are")
                elif num_miss < 0:
                    ret_str = "%s too much" % (logging_tools.get_plural("thread", -num_miss))
                else:
                    ret_str = num_started == 1 and "the thread is running" or "all %d threads running" % (num_started)
                if opt_dict["full_status"]:
                    diff_time  = max(0, time.mktime(time.localtime()) - pid_time)
                    diff_days  = int(diff_time / (3600 * 24))
                    diff_hours = int((diff_time - 3600 * 24 * diff_days) / 3600)
                    diff_mins  = int((diff_time - 3600 * (24 * diff_days + diff_hours)) / 60 )
                    diff_secs  = int(diff_time - 60 * (60 * (24 * diff_days + diff_hours) + diff_mins))
                    ret_str += ", pidfile unchanged since %s%02d:%02d:%02d (%s)" % (diff_days and "%s, " % (logging_tools.get_plural("day", diff_days)) or "",
                                                                                    diff_hours, diff_mins, diff_secs,
                                                                                    time.strftime("%a, %d. %b %Y, %H:%M:%S", time.localtime(pid_time)))
                out_list.append(ret_str)
        if opt_dict["pid_info"]:
            pid_dict = act_struct["pids"]
            if pid_dict:
                p_list = pid_dict.keys()
                p_list.sort()
                if max(pid_dict.values()) == 1:
                    out_list.append(logging_tools.compress_num_list(p_list))
                else:
                    out_list.append(",".join(["%d%s" % (k, pid_dict[k] > 1 and " (%d)" % (pid_dict[k]) or "") for k in p_list]))
            else:
                out_list.append("no PIDs")
        if opt_dict["db_info"]:
            if type(act_struct["sql"]) == type(""):
                out_list.append(act_struct["sql"])
            else:
                out_list.append("%s (%s)" %  (act_struct["sql"].server_info_str,
                                              act_struct["sql"].config_name))
        if opt_dict["runlevel_info"]:
            rlevs = act_struct["runlevels"]
            if type(rlevs) == type([]):
                if rlevs:
                    out_list.append("%s %s" % (logging_tools.get_plural("level", rlevs, 0),
                                               ", ".join(["%d" % (x) for x in rlevs])))
                else:
                    out_list.append("no levels")
            else:
                out_list.append("<no runlevel info>")
        if opt_dict["mem_info"]:
            out_list.append(act_struct["mem"] and process_tools.beautify_mem_info(act_struct["mem"]) or "no pids")
        out_list.append(rc_strs[act_struct["state"]])
        out_bl.add_line(out_list)
    print out_bl
        
if __name__ == "__main__":
    main()
