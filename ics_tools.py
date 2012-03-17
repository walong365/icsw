#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008,2011,2012 Andreas Lang-Nevyjel, init.at
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
""" checks the status of python server processes """

import sys
import os
import logging_tools
import process_tools
import stat
import time
import getopt

FULL_STATUS_VAR_NAME = "PY_FULL_STATUS"

def check_threads(pid_file, overview_mode, full_status):
    ret_state, ret_str = (7, "")
    if pid_file:
        has_t_key = False
        if os.path.isfile(pid_file):
            pid_time = os.stat(pid_file)[stat.ST_CTIME]
            pids = [int(pid_int) for pid_int in [pid_part.strip() for pid_part in file(pid_file, "r").read().split()] if pid_int and pid_int.isdigit()]
            unique_pids, pids_found = (dict([(pid, 0) for pid in pids]),
                                       dict([(pid, 0) for pid in pids]))
            for pid in pids:
                unique_pids[pid] += 1
            for pid in unique_pids.keys():
                stat_f = "/proc/%d/status" % (pid)
                if os.path.isfile(stat_f):
                    stat_dict = dict([(z[0].lower(), z[1].strip()) for z in [y.split(":", 1) for y in [x.strip() for x in file(stat_f, "r").read().replace("\t", " ").split("\n") if x.count(":")]]])
                    if "threads" in stat_dict:
                        has_t_key = True
                        pids_found[pid] = int(stat_dict["threads"])
                    else:
                        pids_found[pid] = 1
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
            num_started = unique_pids and reduce(lambda x, y : x + y, unique_pids.values()) or 0
            num_found = pids_found and reduce(lambda x, y : x + y, pids_found.values()) or 0
            num_miss = num_started - num_found
            if num_miss > 0:
                if not overview_mode:
                    ret_str = "%s %s missing (from %s)" % (logging_tools.get_plural("thread", num_miss),
                                                           num_miss == 1 and "is" or "are",
                                                           ",".join(["pid %d" % (p) for p in unique_pids.keys() if unique_pids[p] != pids_found[p]]))
            elif num_miss < 0:
                if not overview_mode:
                    ret_str = "%s too much (from %s)" % (logging_tools.get_plural("thread", -num_miss),
                                                         ",".join(["pid %d" % (p) for p in unique_pids.keys() if unique_pids[p] != pids_found[p]]))
            else:
                if overview_mode:
                    if num_started == 1:
                        ret_str = "the thread is running"
                    else:
                        ret_str = "all %d threads running" % (num_started)
                    if full_status:
                        diff_time  = max(0, time.mktime(time.localtime()) - pid_time)
                        diff_days  = int(diff_time / (3600 * 24))
                        diff_hours = int((diff_time - 3600 * 24 * diff_days) / 3600)
                        diff_mins  = int((diff_time - 3600 * (24 * diff_days + diff_hours)) / 60 )
                        diff_secs  = int(diff_time - 60 * (60 * (24 * diff_days + diff_hours) + diff_mins))
                        ret_str += " for %s%02d:%02d:%02d (%s)" % (diff_days and "%s, " % (logging_tools.get_plural("day", diff_days)) or "",
                                                                   diff_hours, diff_mins, diff_secs,
                                                                   time.strftime("%a, %d. %b %Y, %H:%M:%S", time.localtime(pid_time)))
                ret_state = 0
        else:
            if not overview_mode:
                ret_str = "PID-file not found"
    else:
        if not overview_mode:
            ret_str = "no PID-file given and $SERVER_PID unset"
    return ret_state, ret_str

def main():
    ret_state = 7
    prog_name = sys.argv.pop(0)
    overview_mode = False
    try:
        opts, args = getopt.getopt(sys.argv[:], "of")
    except:
        print "Error parsing commandline %s: %s" % (" ".join(sys.argv[1:]),
                                                    process_tools.get_except_info())
    else:
        overview_mode, full_status = (False, False)
        for opt, arg in opts:
            if opt == "-o":
                overview_mode = True
            if opt == "-f":
                full_status = True
        if os.getenv(FULL_STATUS_VAR_NAME):
            full_status = True
        if args:
            pid_file = args[0]
        else:
            pid_file = os.getenv("SERVER_PID")
        ret_state, ret_str = check_threads(pid_file, overview_mode, full_status)
        print ret_str, 
    sys.exit(ret_state)
  
if __name__ == "__main__":
    main()
