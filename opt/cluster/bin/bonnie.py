#!/usr/bin/python-init -Otu
#
# Copyright (C) 2007-2008,2015 Andreas Lang-Nevyjel
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
""" parallel bonnie runs, deprecated """

import commands
from initat.tools import configfile
import getopt
import grp
from initat.tools import logging_tools
import os
from initat.tools import process_tools
import pwd
from initat.tools import server_command
import sys
from initat.tools import threading_tools
import time


class slave_thread(threading_tools.thread_obj):
    def __init__(self, loc_config, num, max_num, logger):
        self.__num, self.__max_num = (num, max_num)
        self.__loc_config = loc_config
        self.__logger = logger
        threading_tools.thread_obj.__init__(self, "slave_%d" % (num), queue_size=100)
        self.register_func("start_run", self._start_run)
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__logger.log(lev, what)
    def _sync(self):
        s_time = time.time()
        self.log("syncing...")
        stat, out = commands.getstatusoutput("sync")
        e_time = time.time()
        self.log("syncing took %s" % (logging_tools.get_diff_time_str(e_time - s_time)))
    def _start_run(self):
        if self.__loc_config["SYNC_LOCAL"]:
            self._sync()
        bonnie_args = "-x %d -d %s -s %d -u %d -g %d%s -q%s" % (self.__loc_config["NUM_TESTS"],
                                                                self.__loc_config["TMP_DIR"],
                                                                self.__loc_config["BONNIE_SIZE"],
                                                                self.__loc_config["UID"],
                                                                self.__loc_config["GID"],
                                                                (" -y" if self.__num > 1 else " -p %d" % (self.__max_num)) if self.__loc_config["WAIT_SEMAPHORE"] else "",
                                                                self.__loc_config["SET_RAM_SIZE"] and " -r %d" % (self.__loc_config["RAM_SIZE"]) or "")
        self.log("starting run (bonnie_args: %s)" % (bonnie_args))
        s_time = time.time()
        stat, result = commands.getstatusoutput("bonnie++ %s" % (bonnie_args))
        e_time = time.time()
        self.log("done in %s" % (logging_tools.get_diff_time_str(e_time - s_time)))
        result = result.split("\n")
        for line in result:
            self.log("out: %s" % (line), stat and logging_tools.LOG_LEVEL_WARN or logging_tools.LOG_LEVEL_OK)
        if self.__loc_config["SYNC_LOCAL"]:
            self._sync()
        if stat:
            result = []
        self.send_pool_message(("run_finished", (self.__num, {"output"      : result,
                                                              "run_time"    : e_time - s_time,
                                                              "bonnie_args" : bonnie_args})))

class server_thread_pool(threading_tools.thread_pool):
    def __init__(self, logger, loc_config):
        self.__logger = logger
        self.__loc_config = loc_config
        threading_tools.thread_pool.__init__(self, "main_thread")
        self.register_exception("int_error", self._int_error)
        self.register_exception("term_error", self._int_error)
        self.register_func("run_finished", self._run_finished)
        self.log("starting, uid is %d, gid is %d" % (self.__loc_config["UID"],
                                                     self.__loc_config["GID"]))
        self._breakup_thread_info()
        # spawn threads
        self.__stq_list = []
        for i in range(self.__max_threads):
            self.__stq_list.append(self.add_thread(slave_thread(self.__loc_config, i + 1, self.__max_threads, self.__logger), start_thread=True).get_thread_queue())
        # init runs
        self.__act_run = 0
        self._check_for_next_run()
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__logger.log(lev, what)
    def _breakup_thread_info(self):
        t_i_list = sorted(dict([(int(x), True) for x in self.__loc_config["THREADS"].split(":")]).keys())
        self.__num_runs = len(t_i_list)
        self.__thread_list = t_i_list
        self.__max_threads = t_i_list[-1]
        self.log("%s (%s), max_thread_count is %d" % (logging_tools.get_plural("run", self.__num_runs),
                                                      ", ".join(["%d" % (x) for x in self.__thread_list]),
                                                      self.__max_threads))
    def _sync(self):
        s_time = time.time()
        self.log("syncing...")
        stat, out = commands.getstatusoutput("sync")
        e_time = time.time()
        self.log("syncing took %s" % (logging_tools.get_diff_time_str(e_time - s_time)))
    def _int_error(self, err_cause):
        if self["exit_requested"]:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            self["exit_requested"] = True
    def _check_for_next_run(self):
        if not self.__act_run:
            self.log("init run_dict")
            self.__act_run += 1
            self.__act_run_dict = {"sysinfo" : process_tools.fetch_sysinfo()[1]}
        if not self.__act_run_dict.has_key(self.__act_run):
            self.log("init run_dict for run %d" % (self.__act_run))
            self.__act_run_dict[self.__act_run] = {"num_threads" : self.__thread_list[self.__act_run - 1],
                                                   "started"     : 0,
                                                   "ended"       : 0,
                                                   "results"     : {}}
            if self.__loc_config["SYNC_GLOBAL"]:
                self._sync()
            for num_t in range(self.__act_run_dict[self.__act_run]["num_threads"]):
                self.__act_run_dict[self.__act_run]["started"] += 1
                self.__stq_list[num_t].put(("start_run"))
        # check for finished run
        ard = self.__act_run_dict[self.__act_run]
        if ard["started"] == ard["ended"]:
            self.log("run %d finished" % (self.__act_run))
            if self.__loc_config["SYNC_GLOBAL"]:
                self._sync()
            self.log("Saving result to %s" % (self.__loc_config["RESULT_FILE"]))
            file(self.__loc_config["RESULT_FILE"], "w").write(server_command.sys_to_net(self.__act_run_dict))
            if self.__act_run == self.__num_runs:
                self.log("all runs finished, exiting")
                self._int_error("all runs finished")
            else:
                self.__act_run += 1
                self._check_for_next_run()
    def _run_finished(self, (t_num, result)):
        self.log("Got result from thread %d" % (t_num))
        self.__act_run_dict[self.__act_run]["results"][t_num] = result
        self.__act_run_dict[self.__act_run]["ended"] += 1
        self._check_for_next_run()

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], "u:g:d:ht:n:s:Sr:", ["help", "daemon", "sync-local", "sync-global"])
    except getopt.GetoptError, bla:
        print "Commandline error : %s" % (process_tools.get_except_info())
        sys.exit(2)
    pname = os.path.basename(sys.argv[0])
    user_name = pwd.getpwuid(os.getuid())[0]
    group_name = grp.getgrgid(os.getgid())[0]
    loc_config = configfile.configuration("bonnie", {"USER"            : configfile.str_c_var(user_name),
                                                     "GROUP"           : configfile.str_c_var(group_name),
                                                     "TMP_DIR"         : configfile.str_c_var("/tmp"),
                                                     "UID"             : configfile.int_c_var(0),
                                                     "GID"             : configfile.int_c_var(0),
                                                     "SET_RAM_SIZE"    : configfile.bool_c_var(False),
                                                     "RAM_SIZE"        : configfile.int_c_var(0),
                                                     "DAEMONIZE"       : configfile.bool_c_var(False),
                                                     "WAIT_SEMAPHORE"  : configfile.bool_c_var(True),
                                                     "SYNC_GLOBAL"     : configfile.bool_c_var(False),
                                                     "SYNC_LOCAL"      : configfile.bool_c_var(False),
                                                     "NUM_TESTS"       : configfile.int_c_var(1),
                                                     "BONNIE_SIZE"     : configfile.int_c_var(1024),
                                                     "LOG_NAME"        : configfile.str_c_var("bonnie"),
                                                     "LOG_DESTINATION" : configfile.str_c_var("uds:/var/lib/logging-server/py_log"),
                                                     "THREADS"         : configfile.str_c_var("1"),
                                                     "RESULT_FILE"     : configfile.str_c_var("/tmp/bonnie_res_%s" % (time.ctime().replace(" ", "_").replace("__", "_")))})
    for opt, arg in opts:
        if opt in ["-h", "--help"]:
            print "Usage: %s [OPTIONS]" % (pname)
            print "where OPTIONS are:"
            print " -h,--help       this help"
            print " -d DIR          sets scratch directory, default is %s" % (loc_config["TMP_DIR"])
            print " -u user         run as user USER, default is %s" % (loc_config["USER"])
            print " -g group        run as group GROUP, default is %s" % (loc_config["GROUP"])
            print " -t THREADS      set threads to start, <NUM>[:<NUM>[:<NUM>]], default is %s" % (loc_config["THREADS"])
            print " -n NUM          sets number of tests, default is %d" % (loc_config["NUM_TESTS"])
            print " -s SIZE         size, defaults to %d MB" % (loc_config["BONNIE_SIZE"])
            print " -r RAM          RAM size to set, as default the RAM-Size will be discovered automatically"
            print " -S              do not wait for semaphore"
            print " --daemon        daemonize"
            print " --sync-local    sync before and after every bonnie run (thread-local)"
            print " --sync-global   sync before and after every bonnie run (thread-global)"
            sys.exit(0)
        if opt == "-u":
            loc_config["USER"] = arg
        if opt == "-g":
            loc_config["GROUP"] = arg
        if opt == "-d":
            loc_config["TMP_DIR"] = arg
        if opt == "--daemon":
            loc_config["DAEMONIZE"] = True
        if opt == "-t":
            loc_config["THREADS"] = arg
        if opt == "-n":
            loc_config["NUM_TESTS"] = int(arg)
        if opt == "-s":
            loc_config["BONNIE_SIZE"] = int(arg)
        if opt == "-S":
            loc_config["WAIT_SEMAPHORE"] = False
        if opt == "--sync-local":
            loc_config["SYNC_LOCAL"] = True
        if opt == "--sync-global":
            loc_config["SYNC_GLOBAL"] = True
        if opt == "-r":
            loc_config["SET_RAM_SIZE"] = True
            loc_config["RAM_SIZE"] = int(arg)
    print "Results will be written to %s" % (loc_config["RESULT_FILE"])
    # check options
    if not os.path.isdir(loc_config["TMP_DIR"]):
        print "tmp_dir %s is no directory, exiting ..." % (loc_config["TMP_DIR"])
        sys.exit(1)
    try:
        loc_config["UID"] = pwd.getpwnam(loc_config["USER"])[2]
    except:
        print "cannot get uid: %s" % (process_tools.get_except_info())
        sys.exit(1)
    try:
        loc_config["GID"] = grp.getgrnam(loc_config["GROUP"])[2]
    except:
        print "cannot get gid: %s" % (process_tools.get_except_info())
        sys.exit(1)
    if loc_config["THREADS"]:
        if [True for x in loc_config["THREADS"].split(":") if not x.isdigit()]:
            print "Wrong thread_info %s, exiting ..." % (loc_config["THREADS"])
            sys.exit(0)
    else:
        print "empty thread_info, exiting ..."
        sys.exit(1)
    logger = logging_tools.get_logger(loc_config["LOG_NAME"],
                                      loc_config["LOG_DESTINATION"],
                                      init_logger=True)
    if loc_config["DAEMONIZE"]:
        process_tools.become_daemon()  # deprecated call
        hc_ok = process_tools.set_handles({"out"    : (1, "bonnie.out"),  # deprecated code
                                           "err"    : (0, "/var/lib/logging-server/py_err"),
                                           "strict" : 0})
    thread_pool = server_thread_pool(logger, loc_config)
    thread_pool.thread_loop()
    logger.info("CLOSE")


if __name__ == "__main__":
    print("code is currently deprecated, needs refacturing")
    # main()
