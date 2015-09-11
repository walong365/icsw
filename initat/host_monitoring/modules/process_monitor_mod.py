# Copyright (C) 2001-2015 Andreas Lang-Nevyjel, init.at
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

""" process monitor """

import commands
import os
import re
import signal
import time

from initat.host_monitoring import hm_classes, limits
from initat.tools import affinity_tools, logging_tools, process_tools, config_store
import psutil

MIN_UPDATE_TIME = 10

# for affinity
AFFINITY_CSTORE = "hm.affinity-list"
HZ = 100


class AffinityStruct(object):
    def __init__(self, log_com, af_re):
        self.log_com = log_com
        self.affinity_re = af_re
        self.log("init")
        self.dict = {}
        # has to be None on first run to detect initial run
        self.last_update = None
        self.cpu_container = affinity_tools.CPUContainer()
        self.__counter = 0

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.log_com("[as] {}".format(what), log_level)

    def feed(self, p_dict):
        self.__counter += 1
        cur_time = time.time()
        proc_keys = set()
        for key, value in p_dict.iteritems():
            try:
                if value.is_running() and self.affinity_re.match(value.name()):
                    proc_keys.add(key)
            except psutil.NoSuchProcess:
                self.log("process {:d} has vanished".format(key), logging_tools.LOG_LEVEL_ERROR)
        used_keys = set(self.dict.keys())
        new_keys = proc_keys - used_keys
        old_keys = used_keys - proc_keys
        if new_keys:
            self.log(
                "{}: {}".format(
                    logging_tools.get_plural("new key", len(new_keys)),
                    ", ".join(["{:d}".format(new_key) for new_key in sorted(new_keys)])
                )
            )
            for new_key in new_keys:
                new_ps = self.cpu_container.get_proc_struct(p_dict[new_key])
                self.dict[new_key] = new_ps
                if new_ps.single_cpu_set:
                    # clear affinity mask on first run
                    self.log(
                        "clearing affinity mask for {} (cpu was {:d})".format(
                            unicode(new_ps),
                            new_ps.single_cpu_num
                        )
                    )
                    new_ps.clear_mask()
                if new_ps.single_cpu_set:
                    self.log(
                        "process {} is already pinned to cpu {:d}".format(
                            unicode(new_ps),
                            new_ps.single_cpu_num
                        )
                    )
                else:
                    self.log("added {}".format(unicode(new_ps)))
        if old_keys:
            self.log(
                "{}: {}".format(
                    logging_tools.get_plural("old key", len(old_keys)),
                    ", ".join(
                        [
                            "{}".format(unicode(self.dict[old_key])) for old_key in sorted(old_keys)
                        ]
                    )
                )
            )
            for old_key in old_keys:
                del self.dict[old_key]
        if self.last_update:
            diff_time = max(1, abs(cur_time - self.last_update))
            # print diff_time, proc_keys, used_keys
            sched_keys = set()
            for key in proc_keys & used_keys:
                cur_ps = self.dict[key]
                if not self.__counter % 5:
                    # re-read mask every 5 iterations
                    cur_ps.read_mask()
                try:
                    cur_ps.feed(p_dict[key], diff_time * HZ)
                except:
                    self.log(
                        "error updating {:d}: {}".format(
                            key,
                            process_tools.get_except_info()
                        ),
                        logging_tools.LOG_LEVEL_ERROR
                    )
                    cur_ps.clear_usage()
                else:
                    sched_keys.add(key)
            if sched_keys:
                self._reschedule(sched_keys)
        self.last_update = cur_time

    def _reschedule(self, keys):
        cpu_c = self.cpu_container
        cpu_c.clear_cpu_usage()
        # get core distribution scheme
        core_d = cpu_c.get_distribution_scheme(len(keys))
        core_list = [_entry for _entry in core_d.cpunum]
        if cpu_c.cds_changed(len(keys)):
            # reschedule all processes if the number of processes has changed
            self.log("rescheduling all processes", logging_tools.LOG_LEVEL_WARN)
            resched = set(keys)
        else:
            resched = set()
            for key in keys:
                cur_s = self.dict[key]
                if cur_s.single_cpu_set and cur_s.single_cpu_num in core_list:
                    cpu_c[cur_s.single_cpu_num].add_proc(cur_s)
                    core_list.remove(cur_s.single_cpu_num)
                else:
                    resched.add(key)
        if resched:
            self.log(
                "reschedule {} to {}".format(
                    logging_tools.get_plural("process", len(resched)),
                    logging_tools.get_plural("core", len(core_list)),
                )
            )
            for key, targ_cpu in zip(resched, core_list):
                cur_s = self.dict[key]
                # get optimal CPU (i.e. with lowest load)
                self.log(u"pinning process {} to core {:d}".format(unicode(cur_s), targ_cpu))
                if not cur_s.migrate(targ_cpu):
                    cur_s.read_mask()
                    if cur_s.single_cpu_set:
                        cpu_c.add_proc(cur_s)
                else:
                    self.log(
                        "some problem occured while pinning",
                        logging_tools.LOG_LEVEL_WARN
                    )
            # log final usage pattern
            self.log("usage pattern: {}".format(cpu_c.get_usage_str()))
        if self.__counter % 50 == 0:
            # log cpu usage
            self.log("usage pattern: {}".format(cpu_c.get_usage_str()))


class _general(hm_classes.hm_module):
    def init_module(self):
        # AFFINITY ist not set for relay mode
        self.check_affinity = self.main_proc.CC.CS["hm.enable.affinity.matcher"]
        self.log("affinity check is {}".format("enabled" if self.check_affinity else "disabled"))
        self.__affinity_dict = {}
        if self.check_affinity:
            self.load_store()
        else:
            self.feed_affinity = False

    def load_store(self):
        self.affinity_set = set()
        if config_store.ConfigStore.exists(AFFINITY_CSTORE):
            _afc = config_store.ConfigStore(AFFINITY_CSTORE, log_com=self.log)
            for _key in _afc.keys():
                self.affinity_set.add(_afc[_key])
        if self.affinity_set:
            self.feed_affinity = True
            self.log(
                "affinity_set ({:d}): {}".format(
                    len(self.affinity_set),
                    ",".join(self.affinity_set)
                )
            )
            affinity_re = re.compile("|".join(["(%s)" % (line) for line in self.affinity_set]))
            self.af_struct = AffinityStruct(self.log, affinity_re)
        else:
            self.log("affinity-cstore {} missing".format(AFFINITY_CSTORE), logging_tools.LOG_LEVEL_ERROR)
            self.feed_affinity = False

    def reload(self):
        if self.check_affinity:
            self.load_store()

    def init_machine_vector(self, mv):
        mv.register_entry("proc.total", 0, "total number of processes")
        for key, value in process_tools.PROC_INFO_DICT.iteritems():
            mv.register_entry("proc.{}".format(key), 0, value)

    def update_machine_vector(self, mv):
        pdict = process_tools.get_proc_list()
        if self.feed_affinity:
            self.af_struct.feed(pdict)
        pids = pdict.keys()
        n_dict = {key: 0 for key in process_tools.PROC_INFO_DICT.iterkeys()}
        # mem_mon_procs = []
        # mem_found_procs = {}
        for p_stuff in pdict.values():
            try:
                if p_stuff.status() in n_dict:
                    n_dict[p_stuff.status()] += 1
                else:
                    self.log(
                        "*** unknown process state '{}' for process {} (pid {:d})".format(
                            p_stuff.status(),
                            p_stuff.name(),
                            p_stuff.pid()
                        ),
                        logging_tools.LOG_LEVEL_ERROR
                    )
            except psutil.NoSuchProcess:
                pass
        for key, value in n_dict.iteritems():
            mv["proc.{}".format(key)] = value
        mv["proc.total"] = len(pids)


class procstat_command(hm_classes.hm_command):
    def __init__(self, name):
        hm_classes.hm_command.__init__(self, name, positional_arguments=True)
        self.parser.add_argument("-f", dest="filter", action="store_true", default=False)
        self.parser.add_argument("-w", dest="warn", type=int, default=0)
        self.parser.add_argument("-c", dest="crit", type=int, default=0)
        self.parser.add_argument("-Z", dest="zombie", default=False, action="store_true", help="ignore zombie processes")
        self.parser.add_argument("--cmdre", dest="cmdre", default="", type=str, help="regexp to match against the commandline")

    def __call__(self, srv_com, cur_ns):
        # s_time = time.time()
        if cur_ns.arguments:
            name_list = cur_ns.arguments
            if "cron" in name_list:
                name_list.append("crond")
        else:
            name_list = []
        _p_dict = {}
        for key, value in process_tools.get_proc_list(proc_name_list=name_list).iteritems():
            try:
                if value.is_running():
                    _p_dict[key] = value.as_dict(
                        attrs=[
                            "pid", "ppid", "uids", "gids", "name", "exe",
                            "cmdline", "status", "ppid", "cpu_affinity",
                        ]
                    )
            except psutil.NoSuchProcess:
                pass
        if cur_ns.arguments:
            # try to be smart about cron / crond
            t_dict = {key: value for key, value in _p_dict.iteritems() if value["name"] in cur_ns.arguments}
            if not t_dict and cur_ns.arguments[0] == "cron":
                t_dict = {key: value for key, value in _p_dict.iteritems() if value["name"] in ["crond"]}
            _p_dict = t_dict
        srv_com["process_tree"] = process_tools.compress_struct(_p_dict)
        srv_com["process_tree"].attrib["format"] = "2"
        # print len(srv_com["process_tree"].text)
        # e_time = time.time()
        # print e_time - s_time
        # print unicode(srv_com)

    def interpret(self, srv_com, cur_ns):
        result = srv_com["process_tree"]
        # pprint.pprint(result)
        if type(result) == dict:
            # old version, gives a dict
            _form = 0
        else:
            try:
                _result = process_tools.decompress_struct(result.text, version=int(result.get("format", "1")))
            except:
                return limits.nag_STATE_CRITICAL, "cannot decompress: {}".format(process_tools.get_except_info())
            # print result.text
        p_names = cur_ns.arguments
        zombie_ok_list = ["cron"]
        res_dict = {
            "ok": 0,
            "fail": 0,
            "kernel": 0,
            "userspace": 0,
            "zombie_ok": 0,
        }
        zombie_dict = {}
        if cur_ns.cmdre:
            _cmdre = re.compile(cur_ns.cmdre)
        else:
            _cmdre = None
        for _pid, value in result.iteritems():
            if _cmdre and not _cmdre.search(" ".join(value["cmdline"])):
                continue
            if _form < 2:
                _is_zombie = value["state"] == "Z"
            else:
                _is_zombie = value["status"] == psutil.STATUS_ZOMBIE
            if _is_zombie:
                zombie_dict.setdefault(value["name"], []).append(True)
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
        if len(p_names) == 1 and len(result) == 1:
            found_name = result.values()[0]["name"]
            if found_name != p_names[0]:
                p_names[0] = "{} instead of {}".format(found_name, p_names[0])
            # print p_names, result
        zombie_dict = {key: len(value) for key, value in zombie_dict.iteritems()}
        ret_state = max(ret_state, limits.check_floor(res_dict["ok"], cur_ns.warn, cur_ns.crit))
        ret_str = "{} running ({}{}{}{})".format(
            " + ".join(
                [
                    logging_tools.get_plural("{} process".format(key), res_dict[key]) for key in [
                        "userspace", "kernel"
                    ] if res_dict[key]
                ]
            ) or "nothing",
            ", ".join(sorted(p_names)) if p_names else "all",
            ", {} [{}]".format(
                logging_tools.get_plural("zombie", res_dict["fail"]),
                ", ".join(
                    [
                        "{}{}".format(
                            key,
                            " (x {:d})".format(
                                zombie_dict[key]
                            ) if zombie_dict[key] > 1 else ""
                        ) for key in sorted(zombie_dict)
                    ]
                ),
            ) if res_dict["fail"] else "",
            ", {}".format(
                logging_tools.get_plural("accepted zombie", res_dict["zombie_ok"])
            ) if res_dict["zombie_ok"] else "",
            ", cmdRE is {}".format(cur_ns.cmdre) if _cmdre else "",
        )
        return ret_state, ret_str

    def interpret_old(self, result, parsed_coms):
        result = hm_classes.net_to_sys(result[3:])
        shit_str = ""
        _ret_str, ret_state = ("OK", limits.nag_STATE_CRITICAL)
        _copy_struct = result.get("struct", None)
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
            rets = "{:d} processes running{}{}".format(
                result["num_ok"],
                zomb_str,
                shit_str
            )
        else:
            rets = "proc {} has {} running{}{}".format(
                result["name"],
                logging_tools.get_plural("instance", result["num_ok"]),
                zomb_str,
                shit_str
            )
        return ret_state, rets


class proclist_command(hm_classes.hm_command):
    def __init__(self, name):
        hm_classes.hm_command.__init__(self, name)
        self.parser.add_argument("-t", dest="tree", action="store_true", default=False)
        self.parser.add_argument("-c", dest="comline", action="store_true", default=False)
        self.parser.add_argument("-f", dest="filter", action="append", type=str, default=[])

    def __call__(self, srv_com, cur_ns):
        srv_com["psutil"] = "yes"
        srv_com["num_cores"] = psutil.cpu_count(logical=True)
        srv_com["process_tree"] = process_tools.compress_struct(
            process_tools.get_proc_list(
                attrs=[
                    "pid", "ppid", "uids", "gids", "name", "exe", "cmdline", "status", "ppid", "cpu_affinity",
                ]
            )
        )

    def interpret(self, srv_com, cur_ns):
        _fe = logging_tools.form_entry

        def proc_line(_ps, **kwargs):
            nest = kwargs.get("nest", 0)
            if _psutil:
                _affinity = _ps["cpu_affinity"]
                if len(_affinity) == num_cores:
                    _affinity = "-"
                else:
                    _affinity = ",".join(["{:d}".format(_core) for _core in _affinity])
                pass
            else:
                _affinity = _ps.get("affinity", "-")
            return [
                _fe("{}{:d}".format(" " * nest, _ps["pid"]), header="pid"),
                _fe(_ps["ppid"], header="ppid"),
                _fe(_ps["uids"][0] if _psutil else proc_stuff["uid"], header="uid"),
                _fe(_ps["gids"][0] if _psutil else proc_stuff["gid"], header="gid"),
                _fe(_ps["state"], header="state"),
                _fe(_ps.get("last_cpu", -1), header="cpu"),
                _fe(_affinity, header="aff"),
                _fe(_ps["out_name"], header="process"),
            ]

        def draw_tree(m_pid, nest=0):
            proc_stuff = result[m_pid]
            r_list = [proc_line(proc_stuff, nest=nest)]
            # _fe("%s%s" % (" " * nest, m_pid), header="pid"),
            for dt_entry in [draw_tree(y, nest + 2) for y in result[m_pid]["childs"]]:
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
        _psutil = "psutil" in srv_com
        if _psutil:
            num_cores = srv_com["*num_cores"]
            # unpack and cast pid to integer
            result = {
                int(key): value for key, value in process_tools.decompress_struct(result.text).iteritems()
            }
            for _val in result.itervalues():
                _val["state"] = process_tools.PROC_STATUSES_REV[_val["status"]]
        # print etree.tostring(srv_com.tree, pretty_print=True)
        ret_state = limits.nag_STATE_CRITICAL
        pids = sorted([key for key, value in result.iteritems() if name_re.match(value["name"])])
        for act_pid in pids:
            proc_stuff = result[act_pid]
            proc_name = proc_stuff["name"] if proc_stuff["exe"] else "[%s]" % (proc_stuff["name"])
            if comline_view:
                proc_name = " ".join(proc_stuff.get("cmdline")) or proc_name
            proc_stuff["out_name"] = proc_name
        ret_a = ["found {} matching {}".format(
            logging_tools.get_plural("process", len(pids)),
            name_re.pattern)]
        form_list = logging_tools.new_form_list()
        if tree_view:
            for act_pid in pids:
                result[act_pid]["childs"] = [pid for pid in pids if result[pid]["ppid"] == int(act_pid)]
            for init_pid in [pid for pid in pids if not result[pid]["ppid"]]:
                form_list.extend([add_line for add_line in draw_tree(init_pid)])
        else:
            form_list.extend([proc_line(result[_pid]) for _pid in pids])
        if form_list:
            ret_a.extend(str(form_list).split("\n"))
        return ret_state, "\n".join(ret_a)


class ipckill_command(hm_classes.hm_command):
    def __init__(self, name):
        hm_classes.hm_command.__init__(self, name, positional_arguments=True)
        self.parser.add_argument("--min-uid", dest="min_uid", type=int, default=0)
        self.parser.add_argument("--max-uid", dest="max_uid", type=int, default=65535)

    def __call__(self, srv_com, cur_ns):
        sig_str = "remove all all shm/msg/sem objects for uid {:d}:{:d}".format(
            cur_ns.min_uid,
            cur_ns.max_uid,
        )
        self.log(sig_str)
        srv_com["ipc_result"] = []
        for ipc_dict in [
            {"file": "shm", "key_name": "shmid", "ipcrm_opt": "m"},
            {"file": "msg", "key_name": "msqid", "ipcrm_opt": "q"},
            {"file": "sem", "key_name": "semid", "ipcrm_opt": "s"},
        ]:
            ipcv_file = "/proc/sysvipc/{}".format(ipc_dict["file"])
            _d_key = ipc_dict["file"]
            cur_typenode = srv_com.builder("ipc_list", ipctype=ipc_dict["file"])
            srv_com["ipc_result"].append(cur_typenode)
            try:
                ipcv_lines = open(ipcv_file, "r").readlines()
            except:
                cur_typenode.attrib["error"] = "error reading {}: {}".format(ipcv_file, process_tools.get_except_info())
                self.log(cur_typenode.attrib["error"], logging_tools.LOG_LEVEL_ERROR)
            else:
                try:
                    ipcv_header = [line.strip().split() for line in ipcv_lines[0:1]][0]
                    ipcv_lines = [[int(part) for part in line.strip().split()] for line in ipcv_lines[1:]]
                except:
                    cur_typenode.attrib["error"] = "error parsing {}: {}".format(
                        logging_tools.get_plural("ipcv_line", len(ipcv_lines)),
                        process_tools.get_except_info()
                    )
                    self.log(cur_typenode.attrib["error"], logging_tools.LOG_LEVEL_ERROR)
                else:
                    for ipcv_line in ipcv_lines:
                        act_dict = {key: value for key, value in zip(ipcv_header, ipcv_line)}
                        rem_node = srv_com.builder("rem_result", key="%d" % (act_dict[ipc_dict["key_name"]]))
                        if act_dict["uid"] >= cur_ns.min_uid and act_dict["uid"] <= cur_ns.max_uid:
                            key = act_dict[ipc_dict["key_name"]]
                            rem_com = "/usr/bin/ipcrm -{} {:d}".format(ipc_dict["ipcrm_opt"], key)
                            rem_stat, rem_out = commands.getstatusoutput(rem_com)
                            # stat, out = (1, "???")
                            if rem_stat:
                                rem_node.attrib.update(
                                    {
                                        "error": "1",
                                        "result": "error while executing command %s (%d): %s" % (rem_com, rem_stat, rem_out)
                                    }
                                )
                            else:
                                rem_node.attrib.update(
                                    {
                                        "error": "0",
                                        "result": "ok deleted %s (%s %d uid %d)" % (ipc_dict["file"], ipc_dict["key_name"], key, act_dict["uid"])
                                    }
                                )
                            cur_typenode.append(rem_node)
                    if not len(cur_typenode):
                        cur_typenode.attrib["info"] = "nothing to do"

    def interpret(self, srv_com, cur_ns):
        ok_list, error_list = (
            srv_com.xpath(".//ns:rem_result[@error='0']", smart_strings=False),
            srv_com.xpath(".//ns:rem_result[@error='1']", smart_strings=False)
        )
        return limits.nag_STATE_CRITICAL if error_list else limits.nag_STATE_OK, "removed {}{}".format(
            logging_tools.get_plural("entry", len(ok_list)),
            ", error for {}".format(logging_tools.get_plural("entry", len(error_list))) if error_list else ""
        )


class signal_command(hm_classes.hm_command):
    info_str = "send signal to processes"

    def __init__(self, name):
        hm_classes.hm_command.__init__(self, name, positional_arguments=True)
        self.parser.add_argument("--signal", dest="signal", type=int, default=15)
        self.parser.add_argument("--min-uid", dest="min_uid", type=int, default=0)
        self.parser.add_argument("--max-uid", dest="max_uid", type=int, default=65535)
        self.parser.add_argument("--exclude", dest="exclude", type=str, default="")
        self.__signal_dict = {
            getattr(signal, name): name for name in dir(signal) if name.startswith("SIG") and not name.startswith("SIG_")
        }

    def get_signal_string(self, cur_sig):
        return self.__signal_dict.get(cur_sig, "#%d" % (cur_sig))

    def __call__(self, srv_com, cur_ns):
        def priv_check(key, what):
            _name, _uid = (what.name(), what.uids()[0])
            if include_list:
                if _name in include_list or "{:d}".format(what.pid) in include_list:
                    # take it and everything beneath
                    return 1
                else:
                    # do not take it
                    return 0
            if _name in exclude_list:
                # do not take leaf and stop iteration
                return -1
            else:
                if _uid >= cur_ns.minuid and _uid <= cur_ns.max_uid:
                    # take it
                    return 1
                else:
                    # do not take it
                    return 0
        # check arguments
        exclude_list = [_entry for _entry in cur_ns.exclude.split(",") if _entry.strip()]
        include_list = [_entry for _entry in cur_ns.arguments if _entry.strip()]
        srv_com["signal_list"] = []
        if not include_list and not exclude_list:
            self.log("refuse to operate without include or exclude list", logging_tools.LOG_LEVEL_ERROR)
        else:
            sig_str = "signal {:d}[{}] (uid {:d}:{:d}), exclude_list is {}, include_list is {}".format(
                cur_ns.signal,
                self.get_signal_string(cur_ns.signal),
                cur_ns.min_uid,
                cur_ns.max_uid,
                ", ".join(exclude_list) or "<empty>",
                ", ".join(include_list) or "<empty>"
            )
            self.log(sig_str)
            pid_list = find_pids(process_tools.get_proc_list(), priv_check)
            for struct in pid_list:
                try:
                    _name = struct.name()
                    _cmdline = struct.cmdline()
                    # print struct, cur_ns.signal
                    os.kill(struct.pid, cur_ns.signal)
                except:
                    info_str, is_error = (process_tools.get_except_info(), True)
                else:
                    info_str, is_error = ("sent {:d} to {:d} ({})".format(cur_ns.signal, struct.pid, _name), False)
                self.log(
                    "{:d}: {}".format(
                        struct.pid,
                        info_str
                    ),
                    logging_tools.LOG_LEVEL_ERROR if is_error else logging_tools.LOG_LEVEL_OK
                )
                srv_com["signal_list"].append(
                    srv_com.builder(
                        "signal",
                        _name,
                        error="1" if is_error else "0",
                        result=info_str,
                        cmdline=" ".join(_cmdline)
                    )
                )
        srv_com["signal_list"].attrib.update(
            {
                "signal": "{:d}".format(cur_ns.signal)
            }
        )

    def interpret(self, srv_com, cur_ns):
        ok_list, error_list = (
            srv_com.xpath(".//ns:signal[@error='0']/text()", smart_strings=False),
            srv_com.xpath(".//ns:signal[@error='1']/text()", smart_strings=False)
        )
        cur_sig = int(srv_com["signal_list"].attrib["signal"])
        return limits.nag_STATE_CRITICAL if error_list else limits.nag_STATE_OK, "sent {:d}[{}] to {}{}".format(
            cur_sig,
            self.get_signal_string(cur_sig),
            logging_tools.get_plural("process", len(ok_list) + len(error_list)),
            " ({})".format(logging_tools.get_plural("problem", len(error_list))) if error_list else ""
        )


def find_pids(ptree, check):
    def search(_dict, add, start):
        # external check.
        # if 1 is returned, all subsequent process are added
        # if 0 is returned, the actual add-value is used
        # if -1 is returned, the add value is set to zero and all subsequent checks are disabled
        try:
            new_add = check(start, _dict[start])
        except psutil.NoSuchProcess:
            r_list = []
        else:
            if new_add == -1:
                add = 0
            elif new_add == 1:
                add = 1
            if add:
                r_list, add = ([_dict[start]], 1)
            else:
                r_list = []
            if new_add >= 0:
                p_dict = {_sp.pid: _sp for _sp in ptree.itervalues() if _sp.is_running() and _sp.ppid() == start}
                if p_dict:
                    for pid in p_dict.keys():
                        r_list.extend(search(p_dict, add, pid))
        return r_list
    return search(ptree, 0, ptree.keys()[0])
