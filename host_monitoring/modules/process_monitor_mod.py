#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2009,2010,2011 Andreas Lang-Nevyjel, init.at
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

import sys
import os
import os.path
import re
import time
import Queue
from host_monitoring import limits
import logging_tools
import process_tools
import copy
import commands
from host_monitoring import hm_classes
import threading_tools
import pprint
from lxml import etree
try:
    import mysql_tools
except ImportError:
    mysql_tools = None

MIN_UPDATE_TIME = 10

class _general(hm_classes.hm_module):
    def init_machine_vector(self, mv):
        mv.register_entry("proc.total"          , 0, "total number of processes")
        mv.register_entry("proc.run"            , 0, "number of running processes")
        mv.register_entry("proc.zombie"         , 0, "number of zombie processes")
        mv.register_entry("proc.uninterruptible", 0, "processes in uninterruptable sleep")
        mv.register_entry("proc.traced"         , 0, "processes stopped or traced")
        mv.register_entry("proc.sleeping"       , 0, "processes sleeping")
        mv.register_entry("proc.paging"         , 0, "processes paging")
        mv.register_entry("proc.dead"           , 0, "processes dead")
    def update_machine_vector(self, mv):
        pdict = process_tools.get_proc_list()
        pids = pdict.keys()
        sl_list = [("R", "run"            ),
                   ("Z", "zombie"         ),
                   ("D", "uninterruptible"),
                   ("T", "traced"         ),
                   ("S", "sleeping"       ),
                   ("W", "paging"         ),
                   ("X", "dead"           )]
        n_dict = dict([(key[0], 0) for key in sl_list])
        mem_mon_procs = []#self.__short_mon_procs
        mem_found_procs = {}
        for p_stuff in pdict.values():
            if n_dict.has_key(p_stuff["state"]):
                n_dict[p_stuff["state"]] += 1
            else:
                logger.log(logging_tools.LOG_LEVEL_ERROR,
                           "*** unknown process state '%s' for process %s (pid %d)" % (p_stuff["state"], p_stuff["name"], p_stuff["pid"]))
            if p_stuff.get("name", "") in mem_mon_procs:
                mem_found_procs.setdefault(p_stuff["name"], []).append(p_stuff["pid"])
##         print "-"
##         if new_mems or del_mems:
##             print new_mems, del_mems
##             print mem_found_dict["collserver"]
##             print mem_found_procs["collserver"]
        for short, l_info in sl_list:
            mv["proc.%s" % (l_info)] = n_dict[short]
        mv["proc.total"] = len(pids)

class my_modclass(hm_classes.hm_fileinfo):
    def __init__(self, **args):
        hm_classes.hm_fileinfo.__init__(self,
                                        "process_monitor",
                                        "gives you access to the list of running processes",
                                        **args)
        self.priority = 10
        self.has_own_thread = True
    def init(self, mode, logger, basedir_name, **args):
        if mode == "i":
            self.__loc_queue = Queue.Queue(10)
        self.__full_mon_procs = ["collserver.py",
                                 "snmp-relay.py",
                                 "collrelay.py",
                                 "logcheck-server.py",
                                 "cluster-server.py",
                                 "mother.py",
                                 "rrd-server.py",
                                 "cluster-config-server.py",
                                 "sge-server.py",
                                 "logging-server.py",
                                 "package-client.py",
                                 "nagios-config-server.py",
                                 "rrd-server-collector.py",
                                 "rrd-server-grapher.py",
                                 "rrd-server-writer.py",
                                 "cransys-server.py"]
        self.__short_mon_dict = dict([(x[0:15], x.endswith(".py") and x[:-3] or x) for x in self.__full_mon_procs])
        self.__short_mon_procs = self.__short_mon_dict.keys()
        # check number of running sql-threads ?
        self.__db_con = None
        if mysql_tools:
            try:
                db_con = mysql_tools.dbcon_container()
            except:
                pass
            else:
                try:
                    dc = db_con.get_connection("cluster_full_access")
                    try:
                        info = dc.get_db().stat()
                    except:
                        ok = False
                    else:
                        ok = True
                    dc.release()
                    if ok:
                        self.__db_con = db_con
                    else:
                        db_con.close()
                        del db_con
                except:
                    db_con.close()
                    del db_con
    def start_thread(self, logger):
        new_t = my_subthread(logger, self.__loc_queue)
        self.__t_queue = new_t.get_thread_queue()
        return new_t
    def send_thread(self, what):
        self.__t_queue.put(what)
        return self.__loc_queue.get()
    def init_m_vect(self, mv, logger):
        mv.reg_entry("proc.total"          , 0, "total number of processes")
        mv.reg_entry("proc.run"            , 0, "number of running processes")
        mv.reg_entry("proc.zombie"         , 0, "number of zombie processes")
        mv.reg_entry("proc.uninterruptible", 0, "processes in uninterruptable sleep")
        mv.reg_entry("proc.traced"         , 0, "processes stopped or traced")
        mv.reg_entry("proc.sleeping"       , 0, "processes sleeping")
        mv.reg_entry("proc.paging"         , 0, "processes paging")
        mv.reg_entry("proc.dead"           , 0, "processes dead")
        if self.__db_con:
            mv.reg_entry("sql.threads", 0, "threads running")
        self.__mem_infos_found = []
    def update_m_vect(self, mv, logger):
        pdict = self.send_thread("get_proc_list")
        pids = pdict.keys()
        sl_list = [("R", "run"            ),
                   ("Z", "zombie"         ),
                   ("D", "uninterruptible"),
                   ("T", "traced"         ),
                   ("S", "sleeping"       ),
                   ("W", "paging"         ),
                   ("X", "dead"           )]
        n_dict = dict(zip([x[0] for x in sl_list], [0] * len(sl_list)))
        mem_mon_procs = self.__short_mon_procs
        mem_found_procs = {}
        for p_stuff in pdict.values():
            if n_dict.has_key(p_stuff["state"]):
                n_dict[p_stuff["state"]] += 1
            else:
                logger.log(logging_tools.LOG_LEVEL_ERROR,
                           "*** unknown process state '%s' for process %s (pid %d)" % (p_stuff["state"], p_stuff["name"], p_stuff["pid"]))
            if p_stuff.get("name", "") in mem_mon_procs:
                mem_found_procs.setdefault(p_stuff["name"], []).append(p_stuff["pid"])
        mem_found_procs = dict([(self.__short_mon_dict[k], v) for k, v in mem_found_procs.iteritems()])
        mem_found_dict = {}
        for name, pid_list in mem_found_procs.iteritems():
            tot_size = 0
            for map_file_name in [y for y in ["/proc/%d/maps" % (x) for x in pid_list] if os.path.isfile(y)]:
                try:
                    map_lines = [[y.strip() for y in x.strip().split()] for x in  file(map_file_name, "r").read().split("\n") if x.strip()]
                except:
                    pass
                else:
                    tot_size = 0
                    for map_p in map_lines:
                        try:
                            mem_start, mem_end = map_p[0].split("-")
                            mem_start, mem_end = (int(mem_start, 16),
                                                  int(mem_end, 16))
                            mem_size = mem_end - mem_start
                            perm, offset, dev, inode = (map_p[1], int(map_p[2], 16), map_p[3], int(map_p[4]))
                            if not inode:
                                tot_size += mem_size
                        except:
                            self.log("parsing map_line of %s: %s" % (map_file_name, " ".join(map_p)),
                                     logging_tools.LOG_LEVEL_ERROR)
            if tot_size:
                mem_found_dict[name] = tot_size / 1024
        new_mems = sorted([x for x in mem_found_dict.keys() if x not in self.__mem_infos_found])
        del_mems = sorted([x for x in self.__mem_infos_found if x not in mem_found_dict.keys()])
##         print "-"
##         if new_mems or del_mems:
##             print new_mems, del_mems
##             print mem_found_dict["collserver"]
##             print mem_found_procs["collserver"]
        if new_mems:
            self.log("found %s to monitor: %s" % (logging_tools.get_plural("new process", len(new_mems)),
                                                  ", ".join(new_mems)))
        if del_mems:
            self.log("lost %s to monitor: %s" % (logging_tools.get_plural("process", len(del_mems)),
                                                 ", ".join(del_mems)))
        for new_mem in new_mems:
            mv.reg_entry("csi.mem.%s" % (new_mem), 0, "memory used by %s" % (new_mem), "Byte", 1024, 1024)
        for del_mem in del_mems:
            mv.unreg_entry("csi.mem.%s" % (del_mem))
        if del_mems or new_mems:
            self.__mem_infos_found = mem_found_dict.keys()
        for name, m_info in mem_found_dict.iteritems():
            mv.reg_update(logger, "csi.mem.%s" % (name), m_info)
        for short, l_info in sl_list:
            mv.reg_update(logger, "proc.%s" % (l_info), n_dict[short])
        mv.reg_update(logger, "proc.total", len(pids))
        if self.__db_con:
            db_con = self.__db_con.get_connection("cluster_full_access", catch_errors=True)
            if db_con.connection_valid():
                info_str = db_con.get_db().stat()
            else:
                info_str = ""
            db_con.release()
            info_d = {}
            key = None
            for what in [x.strip() for x in info_str.split() if x.strip()]:
                if what.endswith(":"):
                    key = what
                elif key:
                    info_d[key[:-1].lower()] = what
            if info_d.has_key("threads"):
                mv.reg_update(logger, "sql.threads", int(info_d["threads"]))
    def process_client_args(self, opts, hmb):
        ok, why = (1, "")
        my_lim = limits.limits()
        for opt, arg in opts:
            if hmb.name in ["procstat", "ps"]:
                if opt == "-w":
                    if my_lim.set_warn_val(arg) == 0:
                        ok, why = (0, "Can't parse warning value !")
                if opt == "-c":
                    if my_lim.set_crit_val(arg) == 0:
                        ok, why = (0, "Can't parse critical value !")
                if opt == "-Z":
                    if my_lim.get_add_flag("IZ"):
                        my_lim.set_add_flags(["IZ2"])
                    else:
                        my_lim.set_add_flags(["IZ"])
            elif hmb.name in ["proclist"]:
                if opt == "-t":
                    my_lim.set_add_flags(["t"])
                if opt == "-c":
                    my_lim.set_add_flags(["c"])
                if opt in ["-r", "--raw"]:
                    my_lim.set_add_flags(["R"])
        return ok, why, [my_lim]

class my_subthread(threading_tools.thread_obj):
    def __init__(self, logger, loc_queue):
        self.__logger = logger
        threading_tools.thread_obj.__init__(self, "process_mon", queue_size=100)
        self.__last_update = 0.
        self.__local_queue = loc_queue
        self.__act_plist = process_tools.get_proc_list(add_stat_info=True)
        self.register_func("update", self._update)
        self.register_func("get_proc_list", self._get_proc_list)
        self.add_ignore_func("register_call_queue")
    def thread_running(self):
        self.send_pool_message(("new_pid", os.getpid()))
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__logger.log(lev, what)
    def _update(self):
        act_time = time.time()
        time_diff = act_time - self.__last_update
        if time_diff < 0:
            self.log("(process_monitor) possible clock-skew detected, adjusting (%5.2f seconds since last request)" % (time_diff), logging_tools.LOG_LEVEL_WARN)
            self.__last_update = act_time
        elif time_diff < MIN_UPDATE_TIME:
            self.log("(process_monitor) too many update requests, skipping this one (last one %5.2f seconds ago; %d seconds minimum)" % (time_diff, MIN_UPDATE_TIME), logging_tools.LOG_LEVEL_WARN)
        else:
            self.__last_update = act_time
            new_plist = process_tools.get_proc_list(self.__act_plist, add_stat_info=True)
            if new_plist:
                self.__act_plist = new_plist
            else:
                self.log("got empty process_dict from process_tools.get_proc_list()",
                         logging_tools.LOG_LEVEL_WARN)
    def _get_proc_list(self):
        self.__local_queue.put(copy.deepcopy(self.__act_plist))

class procstat_command(hm_classes.hm_command):
    def __init__(self, name):
        hm_classes.hm_command.__init__(self, name, server_arguments=True, positional_arguments=True)
        self.server_parser.add_argument("-f", dest="filter", action="store_true", default=False)
        self.parser.add_argument("-w", dest="warn", type=int, default=0)
        self.parser.add_argument("-c", dest="crit", type=int, default=0)
    def __call__(self, srv_com, cur_ns):
        p_dict = process_tools.get_proc_list()
        if cur_ns.arguments:
            srv_com.set_dictionary("process_tree", dict([(key, value) for key, value in p_dict.iteritems() if value["name"] in cur_ns.arguments]))
        else:
            srv_com.set_dictionary("process_tree", p_dict)
    def interpret(self, srv_com, cur_ns):
        result = srv_com.tree_to_dict(srv_com.xpath(None, ".//ns:process_tree"))["process_tree"]
        #pprint.pprint(result)
        commands = cur_ns.arguments
        zombie_ok_list = ["cron"]
        res_dict = {"ok"        : 0,
                    "fail"      : 0,
                    "zombie_ok" : 0}
        for pid, value in result.iteritems():
            if value["state"] == "Z":
                if value["name"].lower() in zombie_ok_list:
                    res_dict["zombie_ok"] += 1
                else:
                    res_dict["fail"] += 1
            else:
                res_dict["ok"] += 1
        if res_dict["fail"]:
            ret_state = limits.nag_STATE_CRITICAL
        elif res_dict["zombie_ok"]:
            ret_state = limits.nag_STATE_WARNING
        else:
            ret_state = limits.nag_STATE_OK
        ret_state = max(ret_state, limits.check_floor(res_dict["ok"], cur_ns.warn, cur_ns.crit))
        ret_str = "%s running (%s%s%s)" % (logging_tools.get_plural("process", len(result)),
                                           ", ".join(sorted(commands)) if commands else "all",
                                           ", %d zombie" % (res_dict["fail"]) if res_dict["fail"] else "",
                                           ", %d accepted zombie" % (res_dict["zombie_ok"]) if res_dict["zombie_ok"] else "")
        return ret_state, ret_str
    def server_call(self, cm):
        if len(cm) > 1:
            return "error only one parameter allowed"
        elif len(cm):
            com, pn = ("single", cm[0])
        else:
            com, pn = ("all", "<NONE>")
        num_ok, num_fail, num_shit = (0, 0, 0)
        shit_list = ["cron"]
        act_plist = self.module_info.send_thread("get_proc_list")
        copy_struct = None
        for pid in sorted(act_plist.keys()):
            proc = act_plist[pid]
            # get real command name
            r_name = proc["name"]
            if proc["cmdline"]:
                r_name = proc["cmdline"][0].split()[0]
                if r_name.startswith("/"):
                    r_name = os.path.basename(r_name)
            if com == "all" or r_name  == pn:
                if com == "single":
                    copy_struct = proc
                if proc["state"] == "Z":
                    if r_name in shit_list:
                        num_shit += 1
                    else:
                        num_fail += 1
                else:
                    num_ok += 1
        return "ok %s" % (hm_classes.sys_to_net({"command"  : com,
                                                 "name"     : pn,
                                                 "num_ok"   : num_ok,
                                                 "num_fail" : num_fail,
                                                 "num_shit" : num_shit,
                                                 "struct"   : copy_struct}))
    def client_call(self, result, parsed_coms):
        lim = parsed_coms[0]
        result = hm_classes.net_to_sys(result[3:])
        shit_str = ""
        ret_str, ret_state = ("OK", limits.nag_STATE_CRITICAL)
        copy_struct = result.get("struct", None)
        if result["num_shit"] > 0:
            shit_str = " (%s)" % (logging_tools.get_plural("dead cron", result["num_shit"]))
        if result["num_fail"] > 0:
            zomb_str = " and %s" % (logging_tools.get_plural("Zombie", result["num_fail"]))
            if lim.get_add_flag("IZ2"):
                ret_state, ret_str = (limits.nag_STATE_OK, "Ok")
            elif lim.get_add_flag("IZ"):
                ret_state, ret_str = (limits.nag_STATE_WARNING, "Warning")
            else:
                ret_state, ret_str = (limits.nag_STATE_CRITICAL, "Critical")
        else:
            zomb_str = ""
            ret_state, ret_str = lim.check_floor(result["num_ok"])
        if result["command"] == "all":
            rets = "%s: %d processes running%s%s" % (ret_str,
                                                     result["num_ok"],
                                                     zomb_str,
                                                     shit_str)
        else:
            rets = "%s: proc %s has %s running%s%s" % (ret_str,
                                                       result["name"],
                                                       logging_tools.get_plural("instance", result["num_ok"]),
                                                       zomb_str,
                                                       shit_str)
        return ret_state, rets

class proclist_command(hm_classes.hm_command):
    def __init__(self, name):
        hm_classes.hm_command.__init__(self, name)
        self.parser.add_argument("-t", dest="tree", action="store_true", default=False)
        self.parser.add_argument("-c", dest="comline", action="store_true", default=False)
        self.parser.add_argument("-f", dest="filter", action="append", type=str, default=[])
##        self.help_str = "get the actual list of processes"
##        self.short_client_info = "-t -c -r --raw"
##        self.long_client_info = "enables treeview and display of the full command line, raw_mode via -r or --raw, rest are regexps for the process name"
##        self.short_client_opts = "tcr"
##        self.long_client_opts = ["raw"]
##        self.net_only = True
    def __call__(self, srv_com, cur_ns):
        p_dict = process_tools.get_proc_list()
        # slow but very flexible
        srv_com.set_dictionary("process_tree", p_dict)
##    def server_call(self, cm):
##        re_list = [re.compile(".*%s.*" % (x)) for x in cm]
##        if not re_list:
##            re_list = [re.compile(".")]
##        act_plist = self.module_info.send_thread("get_proc_list")
##        return "ok %s" % (hm_classes.sys_to_net(dict([(pid, val_dict) for pid, val_dict in act_plist.iteritems() if [True for p_match in re_list if p_match.match(val_dict["name"])]])))
    def interpret(self, srv_com, cur_ns):
        def draw_tree(m_pid, nest = 0):
            proc_stuff = result[m_pid]
            r_list = [("%s%s" % (" " * nest, m_pid),
                       result[m_pid]["ppid"],
                       result[m_pid]["uid"],
                       result[m_pid]["gid"],
                       result[m_pid]["state"],
                       result[m_pid].get("last_cpu", -1),
                       result[m_pid].get("affinity", "-"),
                       result[m_pid]["out_name"])]
            for dt_entry in [draw_tree(y, nest+2) for y in result[m_pid]["childs"]]:
                r_list.extend([z for z in dt_entry])
            return r_list
        tree_view = cur_ns.tree
        comline_view = cur_ns.comline
        if cur_ns.filter:
            name_re = re.compile("^.*%s.*$" % ("|".join(cur_ns.filter)), re.IGNORECASE)
            tree_view = False
        else:
            name_re = re.compile(".*")
        result = srv_com.tree_to_dict(srv_com.xpath(None, ".//ns:process_tree"))["process_tree"]
        #print etree.tostring(srv_com.tree, pretty_print=True)
        ret_str, ret_state = ("OK", limits.nag_STATE_CRITICAL)
        pids = sorted([key for key, value in result.iteritems() if name_re.match(value["name"])])
        for act_pid in pids:
            proc_stuff = result[act_pid]
            proc_name = proc_stuff["name"] if proc_stuff["exe"] else "[%s]" % (proc_stuff["name"])
            if comline_view:
                proc_name = " ".join(proc_stuff.get("cmdline")) or proc_name
            proc_stuff["out_name"] = proc_name
        ret_a = ["found %s matching %s" % (logging_tools.get_plural("process", len(pids)),
                                           name_re.pattern)]
        form_list = logging_tools.form_list()
        form_list.set_header_string(0, ["pid", "ppid", "uid", "gid", "state", "cpu", "aff", "process"])
        form_list.set_format_string(1, "d", "")
        form_list.set_format_string(2, "d", "-")
        if tree_view:
            for act_pid in pids:
                result[act_pid]["childs"] = [pid for pid in pids if result[pid]["ppid"] == act_pid]
            for init_pid in [pid for pid in pids if not result[pid]["ppid"]]:
                for add_line in draw_tree(init_pid):
                    form_list.add_line(add_line)
        else:
            for act_pid in pids:
                proc_stuff = result[act_pid]
                form_list.add_line((act_pid,
                                    proc_stuff["ppid"],
                                    proc_stuff["uid"],
                                    proc_stuff["gid"],
                                    proc_stuff["state"],
                                    proc_stuff.get("last_cpu", -1),
                                    proc_stuff.get("affinity", "-"),
                                    proc_stuff["out_name"]))
        if form_list:
            ret_a.extend(str(form_list).split("\n"))
        return ret_state, "\n".join(ret_a)
    def client_call(self, result, parsed_coms):
        def draw_tree(m_pid, nest = 0):
            proc_stuff = result[m_pid]
            r_list = [("%s%s" % (" " * nest, m_pid),
                       result[m_pid]["ppid"],
                       result[m_pid]["uid"],
                       result[m_pid]["gid"],
                       result[m_pid]["state"],
                       result[m_pid].get("last_cpu", -1),
                       result[m_pid].get("affinity", "-"),
                       result[m_pid]["out_name"])]
            for dt_entry in [draw_tree(y, nest+2) for y in result[m_pid]["childs"]]:
                r_list.extend([z for z in dt_entry])
            return r_list
        lim = parsed_coms[0]
        result = hm_classes.net_to_sys(result[3:])
        raw_output = lim.get_add_flag("R")
        ret_str, ret_state = ("OK", limits.nag_STATE_CRITICAL)
        if raw_output:
            return ret_state, result
        else:
            tree_view = lim.get_add_flag("t")
            comline_view = lim.get_add_flag("c")
            pids = sorted(result.keys())
            for act_pid in pids:
                proc_stuff = result[act_pid]
                proc_name = proc_stuff["name"] if proc_stuff["exe"] else "[%s]" % (proc_stuff["name"])
                if comline_view:
                    proc_name = " ".join(proc_stuff.get("cmdline")) or proc_name
                proc_stuff["out_name"] = proc_name
            ret_a = ["found %d processes" % (len(pids))]
            form_list = logging_tools.form_list()
            form_list.set_header_string(0, ["pid", "ppid", "uid", "gid", "state", "cpu", "aff", "process"])
            form_list.set_format_string(1, "d", "")
            form_list.set_format_string(2, "d", "-")
            if tree_view:
                for act_pid in pids:
                    result[act_pid]["childs"] = [pid for pid in pids if result[pid]["ppid"] == act_pid]
                for init_pid in [pid for pid in pids if not result[pid]["ppid"]]:
                    for add_line in draw_tree(init_pid):
                        form_list.add_line(add_line)
            else:
                for act_pid in pids:
                    proc_stuff = result[act_pid]
                    form_list.add_line((act_pid,
                                        proc_stuff["ppid"],
                                        proc_stuff["uid"],
                                        proc_stuff["gid"],
                                        proc_stuff["state"],
                                        proc_stuff.get("last_cpu", -1),
                                        proc_stuff.get("affinity", "-"),
                                        proc_stuff["out_name"]))
            ret_a.extend(str(form_list).split("\n"))
            return ret_state, "\n".join(ret_a)

class ipckill_command(hm_classes.hmb_command):
    def __init__(self, **args):
        hm_classes.hmb_command.__init__(self, "ipckill", **args)
        self.help_str = "deletes shared-memory segments and message queues"
        self.short_client_info = "MIN_UID[:MAX_UID]"
        self.long_client_info = "MIN_UID the minium uid to be killed, MAX_UID the maximum uid to be killed (optional)"
        self.log_level = 1
    def server_call(self, cm):
        if len(cm) != 1:
            return "invalid number of operands (%d != 1)" % (len(cm))
        else:
            if cm[0].isdigit():
                min_uid, max_uid = (int(cm[0]), 65536)
            else:
                min_uid, max_uid = tuple([int(x) for x in cm[0].split(":")])
            stat_dict = {}
            for ipc_dict in [{"file" : "shm", "key_name" : "shmid", "ipcrm_opt" : "m"},
                             {"file" : "msg", "key_name" : "msqid", "ipcrm_opt" : "q"},
                             {"file" : "sem", "key_name" : "semid", "ipcrm_opt" : "s"}]:
                ipcv_file = "/proc/sysvipc/%s" % (ipc_dict["file"])
                d_key = ipc_dict["file"]
                stat_dict[d_key] = []
                try:
                    ipcv_lines = open(ipcv_file, "r").readlines()
                except:
                    stat_dict[d_key].append("error reading %s" % (ipcv_file))
                else:
                    try:
                        ipcv_header = [x.strip().split() for x in ipcv_lines[0:1]][0]
                        ipcv_lines = [[int(y) for y in x.strip().split()] for x in ipcv_lines[1:]]
                    except:
                        stat_dict[d_key].append("error parsing %d ipcv_lines" % (len(ipcv_lines)))
                    else:
                        for ipcv_line in ipcv_lines:
                            act_dict = dict([(key, value) for key, value in zip(ipcv_header, ipcv_line)])
                            if act_dict["uid"] >= min_uid and act_dict["uid"] <= max_uid:
                                key = act_dict[ipc_dict["key_name"]]
                                com = "/usr/bin/ipcrm -%s %d" % (ipc_dict["ipcrm_opt"], key)
                                stat, out = commands.getstatusoutput(com)
                                #stat, out = (1, "???")
                                if stat:
                                    stat_dict[d_key].append("error while executing command %s (%d): %s" % (com, stat, out))
                                else:
                                    stat_dict[d_key].append("ok deleted %s (%s %d uid %d)" % (ipc_dict["file"], ipc_dict["key_name"], key, act_dict["uid"]))
                        if not stat_dict[d_key]:
                            stat_dict[d_key] = ["nothing to do"]
            log_str = ";".join(["%s:%s" % (x, ",".join(stat_dict[x])) for x in stat_dict.keys()])
            logging_tools.my_syslog(log_str)
            return "ok %s" % (log_str)
    def client_call(self, result, parsed_coms):
        ret_state, ret_str = (limits.nag_STATE_OK, result)
        return ret_state, ret_str
        
class pskill_command(hm_classes.hmb_command):
    def __init__(self, **args):
        hm_classes.hmb_command.__init__(self, "pskill", **args)
        self.help_str = "kills processes according to a given rule"
        self.short_client_info = "SIGNUM MIN_UID[:MAX_UID] EXCL_LIST"
        self.long_client_info = "SIGNUM sets the signal number, default is 9, MIN_UID the minium uid to be killed, MAX_UID the (optional) maximum UID, EXCL_LIST is a coma separated list of process heads to be excluded"
        self.log_level = 1
    def server_call(self, cm):
        def priv_check(key, what):
            if what["name"] in excl_list:
                return -1
            else:
                if what["uid"] >= min_uid and what["uid"] <= max_uid:
                    return 1
                else:
                    return 0
        if len(cm) != 3:
            return "invalid number of operands (%d != 3)" % (len(cm))
        else:
            signum = int(cm[0])
            if cm[1].isdigit():
                min_uid, max_uid = (int(cm[1]), 65536)
            else:
                min_uid, max_uid = tuple([int(x) for x in cm[1].split(":")])
            sig_str = "signal %d (uid %d:%d)" % (signum, min_uid, max_uid)
            excl_list = cm[2].split(",")
            kill_array, err_array = ([], [])
            pid_list = find_pids(process_tools.build_ps_tree(process_tools.get_proc_list()), priv_check)
            for struct in pid_list:
                # uhhh, baby
                try:
                    os.kill(int(struct["pid"]), signum)
                except OSError:
                    err_array.append(struct)
                else:
                    kill_array.append(struct)
            if err_array:
                log_str = "error sending %s to the following %s : %s" % (sig_str,
                                                                         logging_tools.get_plural("pid", len(err_array)),
                                                                         ", ".join(["%s (%d)" % (s["name"], s["pid"]) for s in err_array]))
                logging_tools.my_syslog(log_str)
                self.log(log_str, logging_tools.LOG_LEVEL_ERROR)
            if kill_array:
                log_str = "sent %s to the following %s : %s" % (sig_str,
                                                                logging_tools.get_plural("pid", len(kill_array)),
                                                                ", ".join(["%s (%d)" % (s["name"], s["pid"]) for s in kill_array]))
            else:
                log_str = "sent %s to no processes" % (sig_str)
            logging_tools.my_syslog(log_str)
            self.log(log_str)
            return "ok %s" % (log_str)
    def client_call(self, result, parsed_coms):
        ret_state, ret_str = (limits.nag_STATE_OK, result)
        return ret_state, ret_str

class signal_command(hm_classes.hmb_command):
    def __init__(self, **args):
        hm_classes.hmb_command.__init__(self, "signal", **args)
        self.help_str = "sends a given signal to a list of processes"
        self.short_client_info = "SIGNUM PID_LIST"
        self.long_client_info = "SIGNUM sets the signal number, PID_LIST is a coma separated list of process ids (the signal is also sended to all subprocesses)"
        self.log_level = 1
    def server_call(self, cm):
        def priv_check(key, what):
            if key in pid_list:
                return 1
            else:
                return 0
        if len(cm) < 2:
            return "invalid number of operands (%d < 2)" % (len(cm))
        else:
            signum = int(cm[0])
            pid_list = [int(x.strip()) for x in cm[1].split(",")]
            kill_array, err_array = ([], [])
            pid_list = find_pids(process_tools.build_ps_tree(process_tools.get_proc_list()), priv_check)
            for struct in pid_list:
                # uhhh, baby
                try:
                    os.kill(int(struct["pid"]), signum)
                except OSError:
                    err_array.append(struct)
                else:
                    kill_array.append(struct)
            if err_array:
                log_str = "error sending signal %d to the following %s : %s" % (signum,
                                                                                logging_tools.get_plural("pid", len(err_array)),
                                                                                ", ".join(["%s (%d)" % (s["name"], s["pid"]) for s in err_array]))
                logging_tools.my_syslog(log_str)
            if kill_array:
                log_str = "sent signal %d to the following %s : %s" % (signum,
                                                                       logging_tools.get_plural("pid", len(kill_array)),
                                                                       ", ".join(["%s (%d)" % (s["name"], s["pid"]) for s in kill_array]))
            else:
                log_str = "sent signal %d to no processes" % (signum)
            logging_tools.my_syslog(log_str)
            return "ok %s" % (log_str)
    def client_call(self, result, parsed_coms):
        ret_state, ret_str = (limits.nag_STATE_OK, result)
        return ret_state, ret_str

def find_pids(ptree, check):
    def search(dict, add, start):
        # external check.
        # if 1 is returned, all subsequent process are added
        # if 0 is returned, the actual add-value is used
        # if -1 is returned, the add value is set to zero and all subsequent checks are disabled
        new_add = check(start, dict[start])
        if new_add == -1:
            add = 0
        elif new_add == 1:
            add = 1
        if add:
            r_list, add = ([dict[start]], 1)
        else:
            r_list = []
        if dict[start]["childs"] and new_add >= 0:
            p_list = dict[start]["childs"].keys()
            for pid in p_list:
                r_list.extend(search(dict[start]["childs"], add, pid))
        return r_list
    return search(ptree, 0, ptree.keys()[0])

if __name__ == "__main__":
    print "This is a loadable module."
    sys.exit(0)
