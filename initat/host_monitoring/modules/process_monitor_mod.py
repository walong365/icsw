#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2009,2010,2011,2012,2013 Andreas Lang-Nevyjel, init.at
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
import re
import signal
import commands
import pprint
import logging_tools
import process_tools
import threading_tools
from initat.host_monitoring import limits
from initat.host_monitoring import hm_classes
from lxml import etree

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
        sl_list = [
            ("R", "run"            ),
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
                self.log(
                    "*** unknown process state '%s' for process %s (pid %d)" % (
                        p_stuff["state"],
                        p_stuff["name"],
                        p_stuff["pid"]),
                logging_tools.LOG_LEVEL_ERROR)
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

class procstat_command(hm_classes.hm_command):
    def __init__(self, name):
        hm_classes.hm_command.__init__(self, name, server_arguments=True, positional_arguments=True)
        self.server_parser.add_argument("-f", dest="filter", action="store_true", default=False)
        self.parser.add_argument("-w", dest="warn", type=int, default=0)
        self.parser.add_argument("-c", dest="crit", type=int, default=0)
        self.parser.add_argument("-Z", dest="zombie", default=False, action="store_true", help="ignore zombie processes")
    def __call__(self, srv_com, cur_ns):
        p_dict = process_tools.get_proc_list()
        if cur_ns.arguments:
            srv_com["process_tree"] = dict([(key, value) for key, value in p_dict.iteritems() if value["name"] in cur_ns.arguments])
        else:
            srv_com["process_tree"] = p_dict
    def interpret(self, srv_com, cur_ns):
        result = srv_com["process_tree"]
        #pprint.pprint(result)
        commands = cur_ns.arguments
        zombie_ok_list = ["cron"]
        res_dict = {
            "ok"        : 0,
            "fail"      : 0,
            "kernel"    : 0,
            "userspace" : 0,
            "zombie_ok" : 0,
        }
        zombie_list = []
        for pid, value in result.iteritems():
            if value["state"] == "Z":
                zombie_list.append(value["name"])
                if value["name"].lower() in zombie_ok_list:
                    res_dict["zombie_ok"] += 1
                elif cur_ns.zombie:
                    res_dict["ok"] += 1
                else:
                    res_dict["fail"] += 1
            else:
                res_dict["ok"] += 1
            if value["exe"]:
                res_dict["userspace"] += 1
            else:
                res_dict["kernel"] += 1
        if res_dict["fail"]:
            ret_state = limits.nag_STATE_CRITICAL
        elif res_dict["zombie_ok"]:
            ret_state = limits.nag_STATE_WARNING
        else:
            ret_state = limits.nag_STATE_OK
        ret_state = max(ret_state, limits.check_floor(res_dict["ok"], cur_ns.warn, cur_ns.crit))
        ret_str = "%s running (%s%s%s)" % (
            " + ".join(
                [logging_tools.get_plural("%s process" % (key), res_dict[key]) for key in ["userspace", "kernel"] if res_dict[key]]) or "nothing",
            ", ".join(sorted(commands)) if commands else "all",
            ", %s [%s]" % (
                logging_tools.get_plural("zombie", res_dict["fail"]),
                ", ".join(sorted(zombie_list)),
                ) if res_dict["fail"] else "",
            ", %s" % (logging_tools.get_plural("accepted zombie", res_dict["zombie_ok"])) if res_dict["zombie_ok"] else "",
        )
        return ret_state, ret_str
    def interpret_old(self, result, parsed_coms):
        result = hm_classes.net_to_sys(result[3:])
        shit_str = ""
        ret_str, ret_state = ("OK", limits.nag_STATE_CRITICAL)
        copy_struct = result.get("struct", None)
        if parsed_coms.zombie:
            result["num_ok"] += result["num_fail"]
            result["num_fail"] = 0
        if result["num_shit"] > 0:
            shit_str = " (%s)" % (logging_tools.get_plural("dead cron", result["num_shit"]))
        if result["num_fail"] > 0:
            zomb_str = " and %s" % (logging_tools.get_plural("Zombie", result["num_fail"]))
        else:
            zomb_str = ""
            ret_state = limits.check_floor(result["num_ok"], parsed_coms.warn, parsed_coms.crit)
        if result["command"] == "all":
            rets = "%d processes running%s%s" % (
                result["num_ok"],
                zomb_str,
                shit_str)
        else:
            rets = "proc %s has %s running%s%s" % (
                result["name"],
                logging_tools.get_plural("instance", result["num_ok"]),
                zomb_str,
                shit_str)
        return ret_state, rets
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
        return "ok %s" % (hm_classes.sys_to_net({
            "command"  : com,
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
            rets = "%s: %d processes running%s%s" % (
                ret_str,
                result["num_ok"],
                zomb_str,
                shit_str)
        else:
            rets = "%s: proc %s has %s running%s%s" % (
                ret_str,
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
        srv_com["process_tree"] = p_dict
##    def server_call(self, cm):
##        re_list = [re.compile(".*%s.*" % (x)) for x in cm]
##        if not re_list:
##            re_list = [re.compile(".")]
##        act_plist = self.module_info.send_thread("get_proc_list")
##        return "ok %s" % (hm_classes.sys_to_net(dict([(pid, val_dict) for pid, val_dict in act_plist.iteritems() if [True for p_match in re_list if p_match.match(val_dict["name"])]])))
    def interpret(self, srv_com, cur_ns):
        def draw_tree(m_pid, nest = 0):
            proc_stuff = result[m_pid]
            r_list = [
                (
                    "%s%s" % (" " * nest, m_pid),
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
        result = srv_com["process_tree"]
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
                form_list.add_line((
                    act_pid,
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
    def interpret_old(self, result, parsed_coms):
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

class ipckill_command(hm_classes.hm_command):
    def __init__(self, name):
        hm_classes.hm_command.__init__(self, name, positional_arguments=True)
        self.server_arguments = True
        self.server_parser.add_argument("--min-uid", dest="min_uid", type=int, default=0)
        self.server_parser.add_argument("--max-uid", dest="max_uid", type=int, default=65535)
    def __call__(self, srv_com, cur_ns):
        sig_str = "remove all all shm/msg/sem objects for uid %d:%d" % (
            cur_ns.min_uid,
            cur_ns.max_uid,
        )
        self.log(sig_str)
        srv_com["ipc_result"] = []
        for ipc_dict in [
            {"file" : "shm", "key_name" : "shmid", "ipcrm_opt" : "m"},
            {"file" : "msg", "key_name" : "msqid", "ipcrm_opt" : "q"},
            {"file" : "sem", "key_name" : "semid", "ipcrm_opt" : "s"},
            ]:
            ipcv_file = "/proc/sysvipc/%s" % (ipc_dict["file"])
            d_key = ipc_dict["file"]
            cur_typenode = srv_com.builder("ipc_list", ipctype=ipc_dict["file"])
            srv_com["ipc_result"].append(cur_typenode)
            try:
                ipcv_lines = open(ipcv_file, "r").readlines()
            except:
                cur_typenode.attrib["error"] = "error reading %s: %s" % (ipcv_file, process_tools.get_except_info())
                self.log(cur_typenode.attrib["error"], logging_tools.LOG_LEVEL_ERROR)
            else:
                try:
                    ipcv_header = [line.strip().split() for line in ipcv_lines[0:1]][0]
                    ipcv_lines = [[int(part) for part in line.strip().split()] for line in ipcv_lines[1:]]
                except:
                    cur_typenode.attrib["error"] = "error parsing %d ipcv_lines: %s" % (len(ipcv_lines),
                                                                                        process_tools.get_except_info())
                    self.log(cur_typenode.attrib["error"], logging_tools.LOG_LEVEL_ERROR)
                else:
                    for ipcv_line in ipcv_lines:
                        act_dict = dict([(key, value) for key, value in zip(ipcv_header, ipcv_line)])
                        rem_node = srv_com.builder("rem_result", key="%d" % (act_dict[ipc_dict["key_name"]]))
                        if act_dict["uid"] >= cur_ns.min_uid and act_dict["uid"] <= cur_ns.max_uid:
                            key = act_dict[ipc_dict["key_name"]]
                            rem_com = "/usr/bin/ipcrmx -%s %d" % (ipc_dict["ipcrm_opt"], key)
                            rem_stat, rem_out = commands.getstatusoutput(rem_com)
                            #stat, out = (1, "???")
                            if rem_stat:
                                rem_node.attrib.update({
                                    "error"  : "1",
                                    "result" : "error while executing command %s (%d): %s" % (rem_com, rem_stat, rem_out)})
                            else:
                                rem_node.attrib.update({
                                    "error"  : "0",
                                    "result" : "ok deleted %s (%s %d uid %d)" % (ipc_dict["file"], ipc_dict["key_name"], key, act_dict["uid"])})
                            cur_typenode.append(rem_node)
                    if not len(cur_typenode):
                        cur_typenode.attrib["info"] = "nothing to do"
    def interpret(self, srv_com, cur_ns):
        ok_list, error_list = (srv_com.xpath(None, ".//ns:rem_result[@error='0']"),
                               srv_com.xpath(None, ".//ns:rem_result[@error='1']"))
        return limits.nag_STATE_CRITICAL if error_list else limits.nag_STATE_OK, "removed %s%s" % (
            logging_tools.get_plural("entry", len(ok_list)),
            ", error for %s" % (logging_tools.get_plural("entry", len(error_list))) if error_list else "")
        
class signal_command(hm_classes.hm_command):
    info_str = "send signal to processes"
    def __init__(self, name):
        hm_classes.hm_command.__init__(self, name, positional_arguments=True)
        self.server_arguments = True
        self.server_parser.add_argument("--signal", dest="signal", type=int, default=15)
        self.server_parser.add_argument("--min-uid", dest="min_uid", type=int, default=0)
        self.server_parser.add_argument("--max-uid", dest="max_uid", type=int, default=65535)
        self.server_parser.add_argument("--exclude", dest="exclude", type=str, default="")
        self.__signal_dict = dict([(getattr(signal, name), name) for name in dir(signal) if name.startswith("SIG") and not name.startswith("SIG_")])
    def get_signal_string(self, cur_sig):
        return self.__signal_dict.get(cur_sig, "#%d" % (cur_sig))
    def __call__(self, srv_com, cur_ns):
        def priv_check(key, what):
            if include_list:
                if what["name"] in include_list or "%d" % (what["pid"]) in include_list:
                    # take it and everything beneath
                    return 1
                else:
                    # do not take it
                    return 0
            if what["name"] in exclude_list:
                # do not take leaf and stop iteration
                return -1
            else:
                if what["uid"] >= cur_ns.min_uid and what["uid"] <= cur_ns.max_uid:
                    # take it 
                    return 1
                else:
                    # do not take it
                    return 0
        # check arguments
        exclude_list = cur_ns.exclude.split(",")
        include_list = cur_ns.arguments
        sig_str = "signal %d[%s] (uid %d:%d), exclude_list is %s, include_list is %s" % (
            cur_ns.signal,
            self.get_signal_string(cur_ns.signal),
            cur_ns.min_uid,
            cur_ns.max_uid,
            ", ".join(exclude_list) or "<empty>",
            ", ".join(include_list) or "<empty>"
        )
        self.log(sig_str)
        srv_com["signal_list"] = []
        pid_list = find_pids(process_tools.build_ps_tree(process_tools.get_proc_list()), priv_check)
        for struct in pid_list:
            try:
                os.kill(struct["pid"], cur_ns.signal)
            except:
                info_str, is_error = (process_tools.get_except_info(), True)
            else:
                info_str, is_error = ("sent %d to %d" % (cur_ns.signal, struct["pid"]), False)
            self.log("%d: %s" % (struct["pid"], info_str), logging_tools.LOG_LEVEL_ERROR if is_error else logging_tools.LOG_LEVEL_OK)
            srv_com["signal_list"].append(srv_com.builder("signal", struct["name"],
                                                          error="1" if is_error else "0",
                                                          result=info_str,
                                                          cmdline=" ".join(struct["cmdline"])))
        srv_com["signal_list"].attrib.update({"signal" : "%d" % (cur_ns.signal)})
    def interpret(self, srv_com, cur_ns):
        ok_list, error_list = (srv_com.xpath(None, ".//ns:signal[@error='0']/text()"),
                               srv_com.xpath(None, ".//ns:signal[@error='1']/text()"))
        cur_sig = int(srv_com["signal_list"].attrib["signal"])
        return limits.nag_STATE_CRITICAL if error_list else limits.nag_STATE_OK, "sent %d[%s] to %s%s" % (
            cur_sig,
            self.get_signal_string(cur_sig),
            logging_tools.get_plural("process", len(ok_list) + len(error_list)),
            " (%s)" % (logging_tools.get_plural("problem", len(error_list))) if error_list else "")

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
