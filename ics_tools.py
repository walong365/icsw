#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001-2008,2011-2014 Andreas Lang-Nevyjel, init.at
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

from __future__ import print_function
import argparse
import logging_tools
import os
import process_tools
import stat
import sys
import time

MS_DIR = "/var/lib/meta-server"


def check_threads(pid_file, options):  # overview_mode, full_status):
    ret_state, ret_str = (7, "")
    if pid_file:
        if os.path.isfile(pid_file):
            pid_base_name = os.path.basename(pid_file).split(".")[0]
            ms_filename = os.path.join(MS_DIR, pid_base_name)
            if os.path.exists(ms_filename):
                ms_block = process_tools.meta_server_info(ms_filename)
                ms_block.check_block()
                bound_dict = ms_block.bound_dict
                num_miss = sum([abs(val) for val in bound_dict.values()])
                pids = ms_block.pids_found
                pid_time = os.stat(ms_filename)[stat.ST_CTIME]
                num_started = len(pids)
                if num_miss:
                    num_found = num_started + num_miss
                else:
                    num_found = num_started
            else:
                pid_time = os.stat(pid_file)[stat.ST_CTIME]
                pids = [int(pid_int) for pid_int in [pid_part.strip() for pid_part in file(pid_file, "r").read().split()] if pid_int and pid_int.isdigit()]
                unique_pids, pids_found = (
                    {pid: pids.count(pid) for pid in pids},
                    {pid: 0 for pid in pids}
                )
                for pid in unique_pids.keys():
                    stat_f = "/proc/{:d}/status".format(pid)
                    if os.path.isfile(stat_f):
                        stat_dict = {
                            part[0].lower(): part[1].strip() for part in [
                                line.split(":", 1) for line in [
                                    s_line.strip() for s_line in file(stat_f, "r").read().replace("\t", " ").split("\n") if s_line.count(":")
                                ]
                            ]
                        }
                        if "threads" in stat_dict:
                            pids_found[pid] = int(stat_dict["threads"])
                        else:
                            pids_found[pid] = 1
                bound_dict = {}
                for key in set(unique_pids):
                    bound_dict[key] = unique_pids[key] - pids_found[key]
                num_started = unique_pids and reduce(lambda x, y: x + y, unique_pids.values()) or 0
                num_found = pids_found and reduce(lambda x, y: x + y, pids_found.values()) or 0
                num_miss = num_started - num_found
            if num_miss:
                if not options.overview_mode:
                    ret_str = ", ".join(["{:d}: {}".format(
                        cur_pid,
                        "{:d} {}".format(
                            abs(bound_dict[cur_pid]),
                            "missing" if bound_dict[cur_pid] < 0 else "too many",
                        ) if bound_dict[cur_pid] else "OK",
                        ) for cur_pid in sorted(bound_dict.iterkeys())]) or "no PIDs"
            else:
                if options.overview_mode:
                    if num_started == 1:
                        ret_str = "the thread is running"
                    else:
                        ret_str = "all {:d} threads running".format(num_started)
                    if options.full_status:
                        diff_time = max(0, time.mktime(time.localtime()) - pid_time)
                        diff_days = int(diff_time / (3600 * 24))
                        diff_hours = int((diff_time - 3600 * 24 * diff_days) / 3600)
                        diff_mins = int((diff_time - 3600 * (24 * diff_days + diff_hours)) / 60)
                        diff_secs = int(diff_time - 60 * (60 * (24 * diff_days + diff_hours) + diff_mins))
                        ret_str += " for {}{:02d}:{:02d}:{:02d} ({})".format(
                            diff_days and "{}, ".format(logging_tools.get_plural("day", diff_days)) or "",
                            diff_hours, diff_mins, diff_secs,
                            time.strftime("%a, %d. %b %Y, %H:%M:%S", time.localtime(pid_time))
                        )
                ret_state = 0
        else:
            if not options.overview_mode:
                ret_str = "PID-file not found"
    else:
        if not options.overview_mode:
            ret_str = "no PID-file given and $SERVER_PID unset"
    return ret_state, ret_str


def main():
    my_parser = argparse.ArgumentParser()
    my_parser.add_argument("-o", dest="overview_mode", default=False, action="store_true", help="overview mode [%(default)s]")
    my_parser.add_argument("-f", dest="full_status", default=False, action="store_true", help="full status [%(default)s]")
    my_parser.add_argument("args", nargs="+")
    options = my_parser.parse_args()
    if options.args:
        pid_file = options.args[0]
    else:
        pid_file = os.getenv("SERVER_PID")
    ret_state, ret_str = check_threads(pid_file, options)
    print(ret_str, end="")
    sys.exit(ret_state)

if __name__ == "__main__":
    main()
