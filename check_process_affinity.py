#!/usr/bin/python-init -Ot
#
# Copyright (C) 2008-2009,2013-2014 Andreas Lang-Nevyjel
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
""" checks processor-affinity on a regular basis """

import affinity_tools
import configfile
import cpu_database
import logging_tools
import process_tools
import threading_tools
import time

class thread_pool(threading_tools.thread_pool):
    def __init__(self, config):
        self.__config = config
        self.__log_template = logging_tools.get_logger(self.__config["LOG_NAME"],
                                                       self.__config["LOG_DESTINATION"],
                                                       init_logger=True)
        threading_tools.thread_pool.__init__(self, "main", stack_size=2 * 1024 * 1024, blocking_loop=False)
        self.register_exception("int_error" , self._int_error)
        self.register_exception("term_error", self._int_error)
        self._write_config()
        self._get_cpu_info()
        self._log_config()
        self._init_proc_dict()
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)
    def _write_config(self):
        self.__config.write_file(self.__config["CONFIG_FILE"])
    def _int_error(self, err_cause):
        print "Got interrupt"
        if self["exit_requested"]:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            self.log("exit requested (cause %s)" % (err_cause),
                     logging_tools.LOG_LEVEL_WARN)
            self["exit_requested"] = True
    def _log_config(self):
        self.log("Config info:")
        for line, l_level in self.__config.get_log():
            self.log(" - clf: (%d) %s" % (l_level, line))
        conf_info = self.__config.get_config_info()
        self.log("Found %d valid config-lines:" % (len(conf_info)))
        for conf in conf_info:
            self.log("Config : %s" % (conf))
    def _get_cpu_info(self):
        self.__max_cpus = cpu_database.global_cpu_info(parse=True).num_cores()
        self.log("found %s" % (logging_tools.get_plural("core", self.__max_cpus)))
    def _add_affinity_struct(self, p_dict):
        for pid, p_stuff in p_dict.iteritems():
            if p_stuff.get("affinity", None):
                af_struct = affinity_tools.affinity_struct(pid, p_stuff["affinity"], self.__max_cpus)
                if (not af_struct.mask_set() and not self.__config["RESCHEDULE_UNSET"]) and self.__config["MODIFY_AFFINITY"]:
                    af_struct = None
                elif af_struct.single_cpu_set() and p_stuff["name"].count("/") and self.__config["EXCLUDE_KERNEL_THREADS"] and p_stuff["cmdline"] == []:
                    cpu_num = p_stuff["name"].split("/")[-1]
                    if cpu_num.isdigit() and int(cpu_num) == af_struct.get_single_cpu_num():
                        # discard kernel-threads
                        af_struct = None
            else:
                af_struct = None
            p_stuff["affinity_struct"] = af_struct
    def _add_process_usage(self, p_dict):
        diff_time = max(0.1, abs(self.__last_check_time - self.__check_time))
        for pid, p_stuff in p_dict.iteritems():
            old_stuff = self.__proc_dict.get(pid, {})
            if old_stuff.has_key("stat_info") and p_stuff.has_key("stat_info"):
                usage_dict = dict([(key, 100. * float(p_stuff["stat_info"]["%stime" % (key)] - old_stuff["stat_info"]["%stime" % (key)]) / (diff_time * self.__config["HZ"])) for key in ["u", "s"]])
                usage_dict["t"] = usage_dict["u"] + usage_dict["s"]
                p_stuff["usage"] = usage_dict
    def _modify_affinity(self, p_dict):
        proc_dict = dict([(cpu_num, []) for cpu_num in range(self.__max_cpus)])
        unset_list = []
        max_t_used = 0
        for pid, p_stuff in p_dict.iteritems():
            af_struct = p_stuff.get("affinity_struct", None)
            us_struct = p_stuff.get("usage", None)
            if af_struct and us_struct:
                cur_t_used = int(us_struct["t"])
                if cur_t_used > 0:
                    max_t_used = max(cur_t_used, max_t_used)
                    if af_struct.single_cpu_set():
                        for p_num in af_struct.get_proc_nums():
                            # format: process_num -> (pid, act_run_perc)
                            proc_dict[p_num].append((pid, cur_t_used))
                    elif self.__config["RESCHEDULE_UNSET"]:
                        unset_list.append(pid)
        # remove all process where cur_t_used < max_t_used / 10
        for cur_cpu, t_list in proc_dict.iteritems():
            proc_dict[cur_cpu] = [(pid, cur_t_used) for pid, cur_t_used in t_list if cur_t_used > (max_t_used / 10)]
        if unset_list:
            self.log("unset list (%d): %s" % (len(unset_list), ", ".join(["%d" % (cur_pid) for cur_pid in sorted(unset_list)])))
        # distribute pids so that all cpus have the same amount of pids (or 1 less)
        # pprint.pprint(proc_dict)
        while True:
            min_pids = min([len(p_list) for p_list in proc_dict.itervalues()])
            max_pids = max([len(p_list) for p_list in proc_dict.itervalues()])
            if min_pids in [max_pids - 1, max_pids]:
                if unset_list:
                    next_pid = unset_list.pop(0)
                    min_cpu = [cur_cpu for cur_cpu, p_list in proc_dict.iteritems() if len(p_list) == min_pids][0]
                    self.log("pinning pid %d to cpu %d" % (next_pid, min_cpu))
                    proc_dict[min_cpu].append((next_pid, 0))
                    p_dict[next_pid]["affinity_struct"].migrate(min_cpu)
                else:
                    break
            else:
                # find process with highest / lowest load
                max_p_num = [cpu_num for cpu_num, p_list in proc_dict.iteritems() if len(p_list) == max_pids][0]
                min_p_num = [cpu_num for cpu_num, p_list in proc_dict.iteritems() if len(p_list) == min_pids][0]
                migrate_pid, migrate_perc = proc_dict[max_p_num].pop(0)
                proc_dict[min_p_num].append((migrate_pid, migrate_perc))
                self.log("migrating pid %d from cpu %d to cpu %d" % (
                    migrate_pid,
                    max_p_num,
                    min_p_num))
                p_dict[migrate_pid]["affinity_struct"].migrate(min_p_num)
    def _init_proc_dict(self):
        self.__proc_dict = process_tools.get_proc_list(add_stat_info=True)
        self.__last_check_time = time.time()
    def _check_proc_dict(self):
        self.__check_time = time.time()
        act_proc_dict = process_tools.get_proc_list(add_stat_info=True)
        self._add_process_usage(act_proc_dict)
        self._add_affinity_struct(act_proc_dict)
        self._modify_affinity(act_proc_dict)
        self.__proc_dict = act_proc_dict
        self.__last_check_time = time.time()
    def loop_function(self):
        self._check_proc_dict()
        time.sleep(self.__config["MAIN_TIMER"] if not self["exit_requested"] else 1)

def main():
    loc_config = configfile.configuration(
        "affinity", {
            "VERBOSE"                : configfile.bool_c_var(False),
            "LOG_DESTINATION"        : configfile.str_c_var("uds:/var/lib/logging-server/py_log"),
            "LOG_NAME"               : configfile.str_c_var("affinity"),
            "CONFIG_FILE"            : configfile.str_c_var("/etc/sysconfig/affinity"),
            "MAIN_TIMER"             : configfile.int_c_var(15),
            "HZ"                     : configfile.int_c_var(100, info="kernel HZ value"),
            "MODIFY_AFFINITY"        : configfile.bool_c_var(True, info="only modify affinity (alter existing one)"),
            "RESCHEDULE_UNSET"       : configfile.bool_c_var(True, info="reschedule processes with unset affinity mask"),
            "EXCLUDE_KERNEL_THREADS" : configfile.bool_c_var(True, info="excludes kernel threads NAME/proc")})
    loc_config.parse_file(loc_config["CONFIG_FILE"])
    act_run = thread_pool(loc_config)
    act_run.thread_loop()

if __name__ == "__main__":
    main()
