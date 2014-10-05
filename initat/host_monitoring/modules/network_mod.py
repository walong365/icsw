# Copyright (C) 2001-2014 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that i will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
""" network througput and status information """

from initat.host_monitoring import hm_classes, limits
from initat.host_monitoring.config import global_config
import commands
import datetime
import logging_tools
import os
import pprint  # @UnusedImport
import process_tools
import psutil
import re
import server_command
import stat
import subprocess
import time

# name of total-device
TOTAL_DEVICE_NAME = "all"
# name of bonding info filename
# BONDFILE_NAME = "bondinfo"
# devices to check
NET_DEVICES = ["eth", "lo", "myr", "ib", "xenbr", "vmnet", "tun", "tap", TOTAL_DEVICE_NAME]
# devices for detailed statistics
DETAIL_DEVICES = ["eth", "tun", "tap"]
# devices for ethtool
ETHTOOL_DEVICES = ["eth", "peth", "tun", "tap", "en"]
# devices for ibv_devinfo
IBV_DEVICES = ["ib"]
# devices to check for xen-host
XEN_DEVICES = ["vif"]
# minimum update time
MIN_UPDATE_TIME = 4
# argus path
ARGUS_TARGET = "/tmp/argus"
# min free size: 128 MB
ARGUS_MIN_FREE = 128 * 1024 * 1024
# max age of files : 4 weeks
ARGUS_MAX_AGE = 3600 * 24 * 7 * 4
# max file size before wrap: 32 MB
ARGUS_MAX_FILE_SIZE = 32 * 1024 * 1024


class argus_proc(object):
    def __init__(self, proc, interface, arg_path):
        self.interface = interface
        _now = datetime.datetime.now()
        self.target_file = os.path.join(ARGUS_TARGET, _now.strftime("argus_%%s_%Y-%m-%d_%H:%M:%S") % (self.interface))
        self.command = "%s -i %s -w %s" % (arg_path, interface, self.target_file)
        self.create_day = _now.day
        self.popen = None
        self.proc = proc
        self.start_time = time.time()
        # if not a popen call
        self.terminated = False
        self.log("commandline is '%s'" % (self.command))
        self.run()

    def check_file_size(self):
        _wrap = False
        if os.path.isfile(self.target_file):
            try:
                cur_size = os.stat(self.target_file)[stat.ST_SIZE]
            except:
                self.log("cannot access {}: {}".format(self.target_file, process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
                _wrap = True
            else:
                if cur_size > ARGUS_MAX_FILE_SIZE:
                    _wrap = True
                    self.log(
                        "wrapping because file is too big ({} > {})".format(
                            logging_tools.get_size_str(cur_size),
                            logging_tools.get_size_str(ARGUS_MAX_FILE_SIZE),
                        ),
                        logging_tools.LOG_LEVEL_WARN
                    )
                elif datetime.datetime.now().day != self.create_day:
                    _wrap = True
                    self.log("wrapping because of new day has started")
        return _wrap

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.proc.log("[ar %s] %s" % (self.interface, what), log_level)

    def run(self):
        self.popen = subprocess.Popen(self.command, shell=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
        self.log("pid is {:d}".format(self.popen.pid))

    def communicate(self):
        if self.popen:
            try:
                return self.popen.communicate()
            except:
                self.log(u"error in communicate: {}".format(process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
                return ("", "")
        else:
            return ("", "")

    def finished(self):
        self.result = self.popen.poll()
        return self.result

    def terminate(self):
        self.popen.kill()


class compress_job(object):
    def __init__(self, proc, cmd, f_name):
        self.f_name = f_name
        self.command = "%s %s" % (cmd, os.path.join(ARGUS_TARGET, f_name))
        self.proc = proc
        self.log("start")
        self.run()

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.proc.log("[compress %s] %s" % (self.f_name, what), log_level)

    def run(self):
        self.popen = subprocess.Popen(self.command, shell=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)

    def finished(self):
        self.result = self.popen.poll()
        return self.result

    def communicate(self):
        if self.popen:
            try:
                return self.popen.communicate()
            except:
                self.log(u"error in communicate: {}".format(process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
                return ("", "")
        else:
            return ("", "")


class _general(hm_classes.hm_module):
    class Meta:
        # high priority to set ethtool_path before init_machine_vector
        priority = 10

    def init_module(self):
        self.dev_dict = {}
        self.last_update = time.time()
        # search ethtool
        ethtool_path = process_tools.find_file("ethtool")
        if ethtool_path:
            self.log("ethtool found at %s" % (ethtool_path))
        else:
            self.log("no ethtool found", logging_tools.LOG_LEVEL_WARN)
        self.ethtool_path = ethtool_path
        s_path = []
        if os.path.isdir("/opt/ofed"):
            s_path = s_path + ["/usr/ofed/sbin", "/opt/ofed/bin"]
        ibv_devinfo_path = process_tools.find_file("ibv_devinfo", s_path=s_path)
        if ibv_devinfo_path:
            self.log("ibv_devinfo found at %s" % (ibv_devinfo_path))
        else:
            self.log("no ibv_devinfo found", logging_tools.LOG_LEVEL_WARN)
        self.ibv_devinfo_path = ibv_devinfo_path
        iptables_path = process_tools.find_file("iptables")
        if iptables_path:
            self.log("iptables found at %s" % (iptables_path))
        else:
            self.log("no iptables found", logging_tools.LOG_LEVEL_WARN)
        self.iptables_path = iptables_path
        # check for argus
        argus_path = process_tools.find_file("argus")
        if argus_path:
            self.log("argus found at %s" % (argus_path))
        else:
            self.log("no argus found", logging_tools.LOG_LEVEL_WARN)
        if global_config.get("RUN_ARGUS", False) and argus_path:
            self.log("argus monitoring is enabled")
            if not os.path.isdir(ARGUS_TARGET):
                os.mkdir(ARGUS_TARGET)
            # kill all argus jobs
            kill_procs = [_proc for _proc in psutil.process_iter() if _proc.is_running() and _proc.name() == "argus"]
            if kill_procs:
                self.log("killing {}: {}".format(
                    logging_tools.get_plural("argus process", len(kill_procs)),
                    ", ".join(["{:d}".format(_proc.pid) for _proc in sorted(kill_procs)]),
                    ))
                [_proc.kill() for _proc in kill_procs]
            self.__bzip2_path = process_tools.find_file("bzip2")
            self.__argus_path = argus_path
            self.__argus_interfaces = set()
            self.__argus_map = {}
            self.__argus_ignore = re.compile("^(lo|vnet.*|usb.*)$")
            self.__compress_jobs = []
            self._compress_files()
        else:
            self.__argus_map = {}
            self.__argus_path = None

    @property
    def argus_map(self):
        return self.__argus_map

    def _check_free_space(self):
        _stat = os.statvfs(ARGUS_TARGET)
        _cur_free = _stat.f_bavail * _stat.f_bsize
        if _cur_free > ARGUS_MIN_FREE:
            return True
        else:
            self.log(
                "not enough free space for {}: {} < {}".format(
                    ARGUS_TARGET,
                    logging_tools.get_size_str(_cur_free),
                    logging_tools.get_size_str(ARGUS_MIN_FREE),
                )
            )
            return False

    def _compress_files(self):
        if os.path.isdir(ARGUS_TARGET) and self.__bzip2_path:
            _in_flight = [struct.target_file for struct in self.__argus_map.itervalues()]
            try:
                _files = [entry for entry in os.listdir(ARGUS_TARGET) if not entry.count(".") and entry not in _in_flight]
                _bz2_files = [entry for entry in os.listdir(ARGUS_TARGET) if entry.endswith(".bz2")]
                if _files:
                    cur_time = time.time()
                    _to_delete = [
                        entry for entry in os.listdir(ARGUS_TARGET) if abs(os.stat(os.path.join(ARGUS_TARGET, entry))[stat.ST_CTIME] - cur_time) > ARGUS_MAX_AGE
                    ]
                    _to_compress = [entry for entry in _files if entry not in _to_delete]
                    _to_delete.extend([entry for entry in _bz2_files if entry[:-4] in _to_compress])
                    if _to_delete:
                        self.log("%s to delete: %s" % (
                            logging_tools.get_plural("file", len(_to_delete)),
                            ", ".join(sorted(_to_delete))
                            ))
                        [os.unlink(os.path.join(ARGUS_TARGET, _file)) for _file in _to_delete]
                    if _to_compress:
                        self.__compress_jobs.extend([compress_job(self, self.__bzip2_path, _file) for _file in _to_compress])
            except:
                self.log("error handling compressed / old files: %s" % (process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)

    def stop_module(self):
        for _cur_if, _struct in self.__argus_map.iteritems():
            # _struct.terminate()
            if _struct.finished() is None:
                _struct.terminate()
            self._handle_ended_job(_struct)
        # time.sleep(60)

    def _handle_ended_job(self, struct):
        for log_type, data in zip([logging_tools.LOG_LEVEL_OK, logging_tools.LOG_LEVEL_ERROR], struct.communicate()):
            for line in data.split("\n"):
                if line.strip():
                    struct.log(line, log_type)

    def _check_argus(self):
        _current_if = set(
            [
                _val.strip() for _val in [
                    line.split(":")[0] for line in file("/proc/net/dev", "r").read().split("\n") if not line.count("|")
                ] if _val.strip() and not self.__argus_ignore.match(_val.strip())
            ]
        )
        _new_if = _current_if - self.__argus_interfaces
        if self._check_free_space():
            for new_if in _new_if:
                _operstate = "/sys/class/net/%s/operstate" % (new_if)
                if os.path.isfile(_operstate) and file(_operstate, "r").read().strip() not in ["down"]:
                    self.__argus_map[new_if] = argus_proc(self, new_if, self.__argus_path)
                    self.__argus_interfaces.add(new_if)
        _failed = set()
        for cur_if, _struct in self.__argus_map.iteritems():
            _stop = False
            if _struct.finished() is None:
                if _struct.check_file_size():
                    # filesize is too big (or too old), wrap
                    _struct.terminate()
                    _struct.finished()
                    _stop = True
            else:
                _stop = True
            if _stop:
                self._handle_ended_job(_struct)
                _failed.add(cur_if)
                self._compress_files()
        if self.__compress_jobs:
            _done = [entry for entry in self.__compress_jobs if entry.finished() is not None]
            self.log("%s, %d done" % (
                logging_tools.get_plural("compress job", len(self.__compress_jobs)),
                len(_done)))
            for _cj in _done:
                self._handle_ended_job(_cj)
            self.__compress_jobs = [entry for entry in self.__compress_jobs if entry.result is None]
        if _failed:
            for _entry in _failed:
                self.log("removed interface %s" % (_entry), logging_tools.LOG_LEVEL_WARN)
                del self.__argus_map[_entry]
                self.__argus_interfaces.remove(_entry)

    def init_machine_vector(self, mv):
        self.act_nds = netspeed(self.ethtool_path, self.ibv_devinfo_path)  # self.bonding_devices)
        mv.register_entry("net.count.tcp", 0, "number of TCP connections", "1", 1)
        mv.register_entry("net.count.udp", 0, "number of UDP connections", "1", 1)

    def update_machine_vector(self, mv):
        if self.__argus_path:
            self._check_argus()
        try:
            self._net_int(mv)
        except:
            self.log(
                "error in net_int:",
                logging_tools.LOG_LEVEL_ERROR
            )
            for log_line in process_tools.exception_info().log_lines:
                self.log(" - {}".format(log_line), logging_tools.LOG_LEVEL_ERROR)

    def _check_iptables(self, req_chain):
        """ req_chain can be:
        None ............. return everything
        <type> ........... only chains of a given type
        <type>.<chain> ... exactly specified chain
        """
        res_dict = {"required_chain": req_chain}
        if req_chain.count("."):
            req_c_name = req_chain.split(".")[1].upper()
            res_dict["detail_level"] = 2
        else:
            req_c_name = ""
            res_dict["detail_level"] = 1 if req_chain else 0
        if self.iptables_path:
            for t_type in ["filter", "nat", "mangle", "raw", "security"]:
                if not req_chain or req_chain.startswith(t_type):
                    c_com = "%s -t %s -L -n" % (self.iptables_path, t_type)
                    t_dict = {}
                    res_dict[t_type] = t_dict
                    for line in subprocess.check_output(c_com, shell=True).split("\n"):
                        if line.startswith("Chain"):
                            parts = line.strip().split()
                            c_name = parts[1]
                            if not req_c_name or c_name.startswith(req_c_name):
                                use_chain = True
                            else:
                                use_chain = False
                            if use_chain:
                                t_dict[c_name] = {
                                    "policy": parts[-1][:-1],
                                }
                                t_dict[c_name]["lines"] = -1
                        elif line.strip():
                            if use_chain:
                                t_dict[c_name]["lines"] += 1
                    if not res_dict[t_type]:
                        del res_dict[t_type]
        return res_dict

    def _net_int(self, mvect):
        act_time = time.time()
        time_diff = act_time - self.last_update
        if time_diff < 0:
            self.log(
                "(net_int) possible clock-skew detected, adjusting ({} since last request)".format(
                    logging_tools.get_diff_time_str(time_diff)
                ),
                logging_tools.LOG_LEVEL_WARN
            )
            self.last_update = act_time
        elif time_diff < MIN_UPDATE_TIME:
            self.log(
                "(net_int) too many update requests, skipping this one (last one {} ago; {:d} seconds minimum)".format(
                    logging_tools.get_diff_time_str(time_diff),
                    int(MIN_UPDATE_TIME)
                ),
                logging_tools.LOG_LEVEL_WARN
            )
        else:
            self.act_nds.update()
            self.last_update = time.time()
        # tcp / udp connections
        for _type in ["tcp", "udp"]:
            _filename = "/proc/net/{}".format(_type)
            try:
                _lines = len(file(_filename, "r").readlines()) - 1
            except:
                self.log("error reading {}: {}".format(_filename, process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
                _lines = 0
            mvect["net.count.{}".format(_type)] = _lines
        nd_dict = self.act_nds.make_speed_dict()
        # pprint.pprint(nd_dict)
        if nd_dict:
            # add total info
            total_dict = {}
            for key, stuff in nd_dict.iteritems():
                for s_key, s_value in stuff.iteritems():
                    total_dict.setdefault(s_key, 0)
                    total_dict[s_key] += s_value
            nd_dict[TOTAL_DEVICE_NAME] = total_dict
        for key in [_key for _key in self.dev_dict.keys() if _key not in nd_dict]:
            _pf = "net.{}".format(_key)
            mvect.unregister_entry("{}.rx".format(key))
            mvect.unregister_entry("{}.tx".format(key))
            if any([key.startswith(x) for x in DETAIL_DEVICES]):
                mvect.unregister_entry("{}.rxerr".format(_pf))
                mvect.unregister_entry("{}.txerr".format(_pf))
                mvect.unregister_entry("{}.rxdrop".format(_pf))
                mvect.unregister_entry("{}.txdrop".format(_pf))
                mvect.unregister_entry("{}.carrier".format(_pf))
        for key in [_key for _key in nd_dict.keys() if _key not in self.dev_dict]:
            _pf = "net.{}".format(key)
            mvect.register_entry("{}.rx".format(_pf), 0, "bytes per second received by $2", "Byte/s", 1000)
            mvect.register_entry("{}.tx".format(_pf), 0, "bytes per second transmitted by $2", "Byte/s", 1000)
            if [True for x in DETAIL_DEVICES if key.startswith(x)]:
                mvect.register_entry("{}.rxerr".format(_pf), 0, "receive error packets per second on $2", "1/s", 1000)
                mvect.register_entry("{}.txerr".format(_pf), 0, "transmit error packets per second on $2", "1/s", 1000)
                mvect.register_entry("{}.rxdrop".format(_pf), 0, "received packets dropped per second on $2", "1/s", 1000)
                mvect.register_entry("{}.txdrop".format(_pf), 0, "received packets dropped per second on $2", "1/s", 1000)
                mvect.register_entry("{}.carrier".format(_pf), 0, "carrier errors per second on $2", "1/s", 1000)
        self.dev_dict = nd_dict
        for key in self.dev_dict.keys():
            _pf = "net.{}".format(key)
            mvect["{}.rx".format(_pf)] = self.dev_dict[key]["rx"]
            mvect["{}.tx".format(_pf)] = self.dev_dict[key]["tx"]
            if any([key.startswith(_x) for _x in DETAIL_DEVICES]):
                mvect["{}.rxerr".format(_pf)] = self.dev_dict[key]["rxerr"]
                mvect["{}.txerr".format(_pf)] = self.dev_dict[key]["txerr"]
                mvect["{}.rxdrop".format(_pf)] = self.dev_dict[key]["rxdrop"]
                mvect["{}.txdrop".format(_pf)] = self.dev_dict[key]["txdrop"]
                mvect["{}.carrier".format(_pf)] = self.dev_dict[key]["carrier"]
        return

    def _check_for_bridges(self):
        b_dict = {}
        virt_dir = "/sys/devices/virtual/net"
        net_dir = "/sys/class/net"
        # dict of ent/dir keys with brdige-info
        bdir_dict = {}
        if os.path.isdir(virt_dir):
            # check for bridges in virt_dir
            for ent in os.listdir(virt_dir):
                if os.path.isdir("%s/%s/bridge" % (virt_dir, ent)):
                    loc_dir = "%s/%s" % (virt_dir, ent)
                    bdir_dict[ent] = loc_dir
        elif os.path.isdir(net_dir):
            # check for bridges in net_dir
            for ent in os.listdir(net_dir):
                if os.path.isdir("%s/%s/bridge" % (net_dir, ent)):
                    bdir_dict[ent] = "%s/%s" % (net_dir, ent)
        for ent, loc_dir in bdir_dict.iteritems():
            b_dict[ent] = {"interfaces": os.listdir(os.path.join(loc_dir, "brif"))}
            for key in ["address", "addr_len", "features", "flags", "mtu"]:
                _f_name = os.path.join(loc_dir, key)
                if os.path.exists(_f_name):
                    value = file(_f_name, "r").read().strip()
                    if value.isdigit():
                        b_dict[ent][key] = int(value)
                    elif value.startswith("0x"):
                        b_dict[ent][key] = int(value, 16)
                    else:
                        b_dict[ent][key] = value
        return b_dict

    def _check_for_networks(self):
        n_dict = {}
        ip_com = "ip addr show"
        c_stat, c_out = commands.getstatusoutput(ip_com)
        if c_stat:
            self.log(
                "error calling {} ({:d}): {}".format(
                    ip_com,
                    c_stat,
                    c_out
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
        else:
            lines = c_out.split("\n")
            dev_dict = {}
            for line in lines:
                if line[0].isdigit():
                    if line.count(":") == 2:
                        act_net_num, act_net_name, info = line.split(":")
                        info = info.split()
                        flags = info.pop(0)
                        f_dict = {}
                        while info:
                            key = info.pop(0)
                            if info:
                                value = info.pop(0)
                                if value.isdigit():
                                    value = int(value)
                                f_dict[key] = value
                        dev_dict = {
                            "idx": int(act_net_num),
                            "flags": flags[1:-1].split(","),
                            "features": f_dict,
                            "links": {},
                            "inet": []
                        }
                        n_dict[act_net_name.strip()] = dev_dict
                    else:
                        self.log("cannot parse line %s" % (line), logging_tools.LOG_LEVEL_ERROR)
                        dev_dict = {}
                else:
                    if dev_dict:
                        line_parts = line.split()
                        if line_parts[0].startswith("link/"):
                            link_type = line_parts[0][5:]
                            if link_type == "loopback":
                                dev_dict["links"].setdefault(link_type, []).append(True)
                            else:
                                dev_dict["links"].setdefault(link_type, []).append(" ".join(line_parts[1:]))
                        elif line_parts[0] == "inet":
                            dev_dict["inet"].append(" ".join(line_parts[1:]))
        return n_dict

ND_HIST_SIZE = 5


class net_device(object):
    def __init__(self, name, mapping, ethtool_path, ibv_devinfo_path):
        self.name = name
        self.nd_mapping = mapping
        self.ethtool_path = ethtool_path
        self.ibv_devinfo_path = ibv_devinfo_path
        self.nd_keys = set(self.nd_mapping) - set([None])
        self.invalidate()
        self.__history = []
        self.__driver_info = None
        self.__check_ethtool = any([self.name.startswith(check_name) for check_name in ETHTOOL_DEVICES])
        self.__check_ibv_devinfo = any([self.name.startswith(check_name) for check_name in IBV_DEVICES])
        self.last_update = time.time() - 3600
        # set defaults
        self.perfquery_path = None
        self.ethtool_results = {}
        self.ibv_results = {}
        if self.name.startswith("ib"):
            self.ibv_map = {
                "portrcvdata": "rx",
                "portxmitdata": "tx",
            }
            self.perfquery_path = process_tools.find_file("perfquery")
        self.update()

    def update(self):
        if self.name.startswith("ib"):
            self.update_ibv_devinfo()
        else:
            self.update_ethtool()

    def invalidate(self):
        self.found = False

    def feed(self, cur_line):
        # print self.name, cur_line, self.ibv_results, self.perfquery_path
        line_dict = {key: long(value) for key, value in zip(self.nd_mapping, cur_line.split()) if key}
        if self.ibv_results and self.perfquery_path:
            if "port_lid" in self.ibv_results and "port_lid" in self.ibv_results:
                p_stat, p_out = commands.getstatusoutput("%s -x %d %d" % (
                    self.perfquery_path,
                    self.ibv_results["port_lid"],
                    self.ibv_results["port"]))
                if not p_stat:
                    for line in p_out.split("\n"):
                        if line.count(":"):
                            key, value = line.split(":", 1)
                            key = key.strip().lower()
                            value = value.replace(".", "").strip().lower()
                            if key in self.ibv_map:
                                line_dict[self.ibv_map[key]] += int(value)
        self.found = True
        if len(self.__history) > ND_HIST_SIZE:
            self.__history = self.__history[1:]
        self.__history.append((time.time(), line_dict))
        # print "*", self.name, self.get_speed()

    def get_speed(self):
        res_dict = {key: [] for key in self.nd_keys}
        if self.__history:
            last_time, last_dict = self.__history[0]
            for cur_time, cur_dict in self.__history[1:]:
                if cur_time > last_time:
                    diff_time = max(1, cur_time - last_time)
                    for key in self.nd_keys:
                        res_dict[key].append(min(1000 * 1000 * 1000 * 1000 * 1000, max(0, (cur_dict[key] - last_dict[key]) / diff_time)))
                last_time, last_dict = (cur_time, cur_dict)
        res_dict = {key: sum(value) / len(value) if len(value) else 0. for key, value in res_dict.iteritems()}
        return res_dict

    def update_ibv_devinfo(self):
        cur_time = time.time()
        if cur_time > self.last_update + 30:
            res_dict = {}
            if self.__check_ibv_devinfo and self.ibv_devinfo_path:
                ib_stat, ib_out = commands.getstatusoutput("%s -v" % (self.ibv_devinfo_path))
                cur_port, hca_id = (None, None)
                if not ib_stat:
                    for line in ib_out.split("\n"):
                        line = line.strip()
                        if line.count(":"):
                            key, value = line.split(":", 1)
                            key = key.strip()
                            value = value.strip()
                            if key == "hca_id":
                                hca_id = value
                                cur_port = None
                            elif key == "port":
                                cur_port = int(value)
                                res_dict[(hca_id, cur_port)] = {
                                    "port": cur_port,
                                    "hca_id": hca_id,
                                    }
                            elif cur_port and hca_id:
                                if value.isdigit():
                                    value = int(value)
                                if key.count("["):
                                    key = key.split("[")[0].lower()
                                    res_dict[(hca_id, cur_port)].setdefault(key, []).append(value)
                                else:
                                    res_dict[(hca_id, cur_port)][key] = value
            self.last_update = cur_time
            if res_dict:
                port_spec = None
                # get address from sys to evaluate ib-port
                addr_file = "/sys/class/net/%s/address" % (self.name)
                if os.path.isfile(addr_file):
                    ib_addr = file(addr_file, "r").read().strip().replace(":", "").lower()[-8:]
                    for ref_spec, struct in res_dict.iteritems():
                        gid_list = struct.get("gid", "")
                        if type(gid_list) != list:
                            gid_list = [gid_list]
                        gid_list = [entry.replace(":", "").lower()[-8:] for entry in gid_list]
                        if ib_addr in gid_list:
                            port_spec = ref_spec
                            break
                self.ibv_results = res_dict.get(port_spec, {})
            else:
                self.ibv_results = {}

    def update_ethtool(self):
        cur_time = time.time()
        if cur_time > self.last_update + 30:
            res_dict = {}
            if self.__check_ethtool and self.ethtool_path:
                if not self.__driver_info:
                    ce_stat, ce_out = commands.getstatusoutput("%s -i %s" % (self.ethtool_path, self.name))
                    if not ce_stat:
                        res_dict = {
                            key.lower(): value.strip() for key, value in [
                                line.strip().split(":", 1) for line in ce_out.split("\n") if line.count(":")
                            ] if len(value.strip())}
                        self.__driver_info = res_dict.get("driver", "driver unknown")
                    else:
                        self.__driver_info = "driver unknown"
                ce_stat, ce_out = commands.getstatusoutput("%s %s" % (self.ethtool_path, self.name))
                if not ce_stat:
                    res_dict = {
                        key.lower(): value.strip() for key, value in [
                            line.strip().split(":", 1) for line in ce_out.split("\n") if line.count(":")
                        ] if len(value.strip())
                    }
                    res_dict["driver"] = self.__driver_info
            self.last_update = cur_time
            self.ethtool_results = res_dict

    def get_xml(self, srv_com):
        cur_speed = self.get_speed()
        result = srv_com.builder(
            "device_%s" % (self.name),
            srv_com.builder(
                "values",
                *[
                    srv_com.builder(key, "%.2f" % (value)) for key, value in cur_speed.iteritems()
                ]
            )
        )
        if self.ethtool_results:
            result.append(
                srv_com.builder(
                    "ethtool",
                    *[
                        srv_com.builder("value", value, name=key) for key, value in self.ethtool_results.iteritems()
                    ]
                )
            )
        if self.ibv_results:
            result.append(
                srv_com.builder(
                    "ibv",
                    *[
                        srv_com.builder("value", str(value), name=key) for key, value in self.ibv_results.iteritems()
                    ]
                )
            )
        if self.name.startswith("bond"):
            # add bonding info if present
            try:
                result.append(
                    srv_com.builder("bond_info", file("/proc/net/bonding/%s" % (self.name), "r").read())
                )
            except:
                pass
        return result


class netspeed(object):
    def __init__(self, ethtool_path, ibv_devinfo_path):
        self.ethtool_path = ethtool_path
        self.ibv_devinfo_path = ibv_devinfo_path
        cur_head = sum([part.split() for part in file("/proc/net/dev", "r").readlines()[1].strip().split("|")], [])
        if len(cur_head) == 17:
            self.nd_mapping = [
                "rx", None, "rxerr", "rxdrop", None, None, None, None,
                "tx", None, "txerr", "txdrop", None, None, "carrier", None
            ]
        else:
            raise ValueError("unknown /proc/net/dev layout")
        self.nst_size = 10
        self.__o_time, self.__a_time = (0., time.time() - 1.1)
        self.__o_stat, self.__a_stat = ({}, {})
        self.nst = {}
        self.devices = {}
        # ethtool info
        self.ethtool_dict = {}
        # extra info (infiniband and so on)
        self.extra_dict = {}
        # self.__b_array = bonding
        self.__idx_dict = {
            "rx": 0,
            "tx": 8,
            "rxerr": 2,
            "txerr": 10,
            "rxdrop": 3,
            "txdrop": 11,
            "carrier": 14
        }
        self.__keys = set(self.__idx_dict.keys())
        self.__is_xen_host = False
        try:
            self.update()
        except:
            pass

    def __getitem__(self, key):
        return self.devices[key]

    def __setitem__(self, key, value):
        self.devices[key] = value

    def __contains__(self, key):
        return key in self.devices

    def keys(self):
        return self.devices.keys()

    def is_xen_host(self):
        return self.__is_xen_host

    def make_speed_dict(self):
        return {key: self[key].get_speed() for key in self.keys()}

    def update(self):
        ntime = time.time()
        if abs(ntime - self.__a_time) > 1:
            try:
                line_list = [
                    (dev_name.strip(), dev_stats) for dev_name, dev_stats in [
                        line.split(":", 1) for line in file("/proc/net/dev", "r").read().split("\n") if line.count(":")
                    ]
                ]
            except:
                pass
            else:
                # invalidate devices
                for key in self.keys():
                    self[key].invalidate()
                for key, value in line_list:
                    if key not in self:
                        self[key] = net_device(key, self.nd_mapping, self.ethtool_path, self.ibv_devinfo_path)
                    self[key].feed(value)
                    self[key].update()
            self.__a_time = ntime


class ping_sp_struct(hm_classes.subprocess_struct):
    seq_num = 0

    class Meta:
        max_usage = 512
        direct = True
        use_popen = False
        id_str = "ping"

    def __init__(self, srv_com, target_spec, num_pings, timeout):
        hm_classes.subprocess_struct.__init__(self, srv_com, "")
        self.target_spec, self.num_pings, self.timeout = (target_spec, num_pings, timeout)
        ping_sp_struct.seq_num += 1
        self.seq_str = "ping_%d" % (ping_sp_struct.seq_num)

    def run(self):
        self.tart_time = time.time()
        return ("ping", self.seq_str, self.target_spec, self.num_pings, self.timeout)

    def process(self, *args):
        self.terminated = True
        cur_b = self.srv_com.builder
        if len(self.target_spec) == 1:
            # single host ping
            _id_str, num_sent, num_received, time_field, error_str = args
            self.srv_com["result"] = cur_b(
                "ping_result",
                error_str,
                cur_b(
                    "times",
                    *[
                        cur_b("time", "%.4f" % (cur_time)) for cur_time in time_field
                    ]
                ),
                target=self.target_spec[0],
                num_sent="%d" % (num_sent),
                num_received="%d" % (num_received)
            )
        else:
            # multi host ping
            _id_str, res_list = args
            res_el = cur_b("ping_results", num_hosts="%d" % (len(self.target_spec)))
            for t_host, num_sent, num_received, time_field, error_str in res_list:
                host_el = cur_b(
                    "ping_result",
                    error_str,
                    cur_b(
                        "times",
                        *[
                            cur_b("time", "%.4f" % (cur_time)) for cur_time in time_field
                        ]
                    ),
                    target=t_host,
                    num_sent="%d" % (num_sent),
                    num_received="%d" % (num_received)
                )
                res_el.append(host_el)
            self.srv_com["result"] = res_el
        self.send_return()
        self.terminated = True
    # def __del__(self):
    #    print "dp"


class argus_status_command(hm_classes.hm_command):
    info_str = "checks argus processes"

    def __init__(self, name):
        hm_classes.hm_command.__init__(self, name)
        self.parser.add_argument("-w", dest="warn", type=int, help="warning level, minimum processes")
        self.parser.add_argument("-c", dest="crit", type=int, help="critical level, minimum processes")

    def __call__(self, srv_com, cur_ns):
        # if not cur_ns.arguments:
        srv_com["argus_interfaces"] = self.module.argus_map.keys()

    def interpret(self, srv_com, cur_ns):
        arg_list = srv_com["*argus_interfaces"]
        proc_l = limits.limits(cur_ns.warn, cur_ns.crit)
        ret_state, _str = proc_l.check_floor(len(arg_list))
        return ret_state, "%s running: %s" % (
            logging_tools.get_plural("argus process", len(arg_list)),
            ", ".join(sorted(arg_list))
        )


class ping_command(hm_classes.hm_command):
    info_str = "ping command"

    def __init__(self, name):
        hm_classes.hm_command.__init__(self, name, positional_arguments=True)
        self.ping_match = re.compile("^(?P<rta>\d+),(?P<loss>\d+)%{0,1}$")
        self.parser.add_argument("-w", dest="warn", type=str, help="warning level, format is <RTA in ms>,<LOSS in %%>%%")
        self.parser.add_argument("-c", dest="crit", type=str, help="critical level, format is <RTA in ms>,<LOSS in %%>%%")

    def __call__(self, srv_com, cur_ns):
        args = cur_ns.arguments
        if len(args) == 3:
            target_host, num_pings, timeout = args
        elif len(args) == 2:
            target_host, num_pings = args
            timeout = 5.0
        elif len(args) == 1:
            target_host = args[0]
            num_pings, timeout = (3, 5.0)
        else:
            srv_com.set_result("wrong number of arguments (%d)" % (len(args)), server_command.SRV_REPLY_STATE_ERROR)
            cur_sps, target_host = (None, None)
        if target_host:
            num_pings, timeout = (
                min(32, max(1, int(float(num_pings)))),
                max(0.1, float(timeout))
            )
            cur_sps = ping_sp_struct(srv_com, [entry.strip() for entry in target_host.split(",")], num_pings, timeout)
        return cur_sps

    def _interpret_wc(self, in_str, def_value, num_sent):
        cur_m = self.ping_match.match(in_str or "")
        if cur_m:
            return (int(cur_m.group("rta")), int((float(cur_m.group("loss")) * num_sent) / 100))
        else:
            return def_value

    def interpret(self, srv_com, cur_ns):
        if "result:ping_results" in srv_com:
            ping_res_list = srv_com["result:ping_results"]
        else:
            ping_res_list = [srv_com["result:ping_result"]]
        ret_state, ret_f = (limits.nag_STATE_OK, [])
        multi_ping = len(ping_res_list) > 1
        if multi_ping:
            ret_f.append(logging_tools.get_plural("target", len(ping_res_list)))
        for ping_res in ping_res_list:
            target = ping_res.attrib["target"]
            if ping_res.text:
                ret_state = max(ret_state, limits.nag_STATE_CRITICAL)
                ret_f.append("%s: %s" % (target, ping_res.text))
            else:
                time_f = map(float, srv_com.xpath("ns:times/ns:time/text()", start_el=ping_res, smart_strings=False))
                if time_f:
                    max_time, min_time, mean_time = (
                        max(time_f),
                        min(time_f),
                        sum(time_f) / len(time_f))
                else:
                    max_time, min_time, mean_time = (None, None, None)
                num_sent, num_received = (int(ping_res.attrib["num_sent"]),
                                          int(ping_res.attrib["num_received"]))
                w_rta, w_loss = self._interpret_wc(cur_ns.warn, (100000, num_sent - 1), num_sent)
                c_rta, c_loss = self._interpret_wc(cur_ns.crit, (100000, num_sent), num_sent)
                num_loss = num_sent - num_received
                if mean_time is not None:
                    rta_ms = mean_time * 1000
                    if num_loss >= c_loss or rta_ms > c_rta:
                        ret_state = max(ret_state, limits.nag_STATE_CRITICAL)
                    elif num_loss >= w_loss or rta_ms > w_rta:
                        ret_state = max(ret_state, limits.nag_STATE_WARNING)
                else:
                    if num_loss >= c_loss:
                        ret_state = max(ret_state, limits.nag_STATE_CRITICAL)
                    elif num_loss >= w_loss:
                        ret_state = max(ret_state, limits.nag_STATE_WARNING)
                if num_received == 0:
                    ret_f.append(
                        "%s: no reply (%s sent) | rta=0.0 min=0.0 max=0.0 sent=%d loss=%d" % (
                            target,
                            logging_tools.get_plural("packet", num_sent),
                            num_sent,
                            num_sent,
                        )
                    )
                else:
                    if mean_time is not None:
                        if mean_time < 0.01:
                            time_info = "%.2f ms mean time" % (1000 * mean_time)
                        else:
                            time_info = "%.4f s mean time" % (mean_time)
                        timing_str = "rta=%.6f min=%.6f max=%.6f" % (
                            mean_time,
                            min_time,
                            max_time,
                            )
                    else:
                        time_info = "no time info"
                        timing_str = "rta=0.0 min=0.0 max=0.0"
                    ret_f.append(
                        "%s: %d of %d (%s) | %s sent=%d loss=%d" % (
                            target,
                            num_received,
                            num_sent,
                            time_info,
                            timing_str,
                            num_sent,
                            num_sent - num_received,
                        )
                    )
        if multi_ping:
            # remove performance data for multi-ping
            ret_f = [entry.split("|")[0].strip() for entry in ret_f]
        return ret_state, ", ".join(ret_f)


class net_command(hm_classes.hm_command):
    info_str = "network information"

    def __init__(self, name):
        hm_classes.hm_command.__init__(self, name, positional_arguments=True, arguments_name="interface")
        self.parser.add_argument("-w", dest="warn", type=str)
        self.parser.add_argument("-c", dest="crit", type=str)
        self.parser.add_argument("-s", dest="speed", type=str)
        self.parser.add_argument("--duplex", dest="duplex", type=str)

    def __call__(self, srv_com, cur_ns):
        if "arguments:arg0" not in srv_com:
            srv_com.set_result(
                "missing argument",
                server_command.SRV_REPLY_STATE_ERROR
            )
        else:
            net_device = srv_com["arguments:arg0"].text.strip()
            if net_device in self.module.act_nds:
                srv_com["device"] = self.module.act_nds[net_device].get_xml(srv_com)
            else:
                srv_com.set_result(
                    "netdevice %s not found" % (net_device),
                    server_command.SRV_REPLY_STATE_ERROR,
                )

    def _parse_duplex_str(self, in_dup):
        if in_dup.lower().count("unk") or in_dup == "-":
            return "unknown"
        elif in_dup.lower()[0] == "f":
            return "full"
        elif in_dup.lower()[0] == "h":
            return "half"
        else:
            raise ValueError("Cannot parse duplex_string '%s'" % (in_dup))

    def _parse_speed_str(self, in_str):
        in_str_l = in_str.lower().strip()
        in_p = re.match("^(?P<num>[\d.]+)\s*(?P<post>\S*)$", in_str_l)
        if in_p:
            num, post = (int(float(in_p.group("num"))), in_p.group("post"))
            pfix = ""
            for act_pfix in ["k", "m", "g", "t"]:
                if post.startswith(act_pfix):
                    pfix = act_pfix
                    post = post[1:]
                    break
            if post.endswith("/s"):
                per_sec = True
                post = post[:-2]
            elif post == "bps":
                per_sec = True
                post = post[:-2]
            else:
                per_sec = False
            if post in ["byte", "bytes"]:
                mult = 8
            elif post in ["b", "bit", "bits", "baud", ""]:
                mult = 1
            else:
                raise ValueError("Cannot parse postfix '%s' of target_speed" % ("%s%s%s" % (pfix, post, per_sec and "/s" or "")))
            targ_speed = {
                "": 1,
                "k": 1000,
                "m": 1000 * 1000,
                "g": 1000 * 1000 * 1000,
                "t": 1000 * 1000 * 1000 * 1000
            }[pfix] * num * mult
            return targ_speed
        elif in_str_l.startswith("unkn") or in_str_l == "-":
            return -1
        else:
            raise ValueError("Cannot parse target_speed '%s'" % (in_str))

    def beautify_speed(self, i_val):
        f_val = float(i_val)
        if f_val < 500.:
            return "%.0f B/s" % (f_val)
        f_val /= 1000.
        if f_val < 500.:
            return "%.2f kB/s" % (f_val)
        f_val /= 1000.
        if f_val < 500.:
            return "%.2f MB/s" % (f_val)
        f_val /= 1000.
        return "%.2f GB/s" % (f_val)

    def interpret(self, srv_com, cur_ns):
        dev_name = srv_com["arguments:arg0"].text
        value_tree = srv_com["device:device_%s:values" % (dev_name)]
        try:
            ethtool_tree = srv_com["device:device_%s:ethtool" % (dev_name)]
        except:
            ethtool_tree = []
        try:
            ibv_tree = srv_com["device:device_%s:ibv" % (dev_name)]
        except:
            ibv_tree = []
        value_dict = {el.tag.split("}")[-1]: float(el.text) for el in value_tree}
        # build ethtool helper dict
        ethtool_dict = {"link detected": "yes"}
        ethtool_dict.update({el.get("name"): el.text for el in ethtool_tree})
        ethtool_dict["duplex"] = self._parse_duplex_str(ethtool_dict.get("duplex", "unknown"))
        ethtool_dict["speed"] = self._parse_speed_str(ethtool_dict.get("speed", "unknown"))
        ibv_dict = {el.get("name"): el.text for el in ibv_tree}
        if ethtool_dict.get("speed", -1) < 0 and ethtool_dict.get("driver", None) in ["virtio_net"]:
            # set ethtool speed/duplex to 10G/full
            ethtool_dict["speed"] = 10 * 1000 * 1000 * 1000
            ethtool_dict["duplex"] = "full"
        connected = ethtool_dict["link detected"] == "yes"
        max_rxtx = max([value_dict["rx"], value_dict["tx"]])
        if cur_ns.warn:
            cur_ns.warn = self._parse_speed_str(cur_ns.warn)
        if cur_ns.crit:
            cur_ns.crit = self._parse_speed_str(cur_ns.crit)
        add_errors, add_oks, ret_state = (
            [],
            [],
            limits.check_ceiling(max_rxtx, cur_ns.warn, cur_ns.crit)
        )
        if not connected:
            add_errors.append("No cable connected?")
            ret_state = max(ret_state, limits.nag_STATE_WARNING)
        else:
            if not any([dev_name.startswith(prefix) for prefix in ETHTOOL_DEVICES]):
                # not a ethtool-capable device
                if dev_name.startswith("bond"):
                    bond_info = srv_com["device:device_%s" % (dev_name)].findtext(".//ns0:bond_info", namespaces={"ns0": server_command.XML_NS})
                    if bond_info:
                        bond_dict = {}
                        cur_dict = bond_dict
                        # parse bond dict
                        for line in bond_info.split("\n"):
                            if line.strip() and line.count(":"):
                                key, value = line.strip().split(":", 1)
                                value = value.strip()
                                if value.isdigit():
                                    value = int(value)
                                key = key.strip().lower().replace(" ", "_")
                                if key == "slave_interface":
                                    cur_dict = {}
                                    bond_dict.setdefault("slaves", {}).setdefault(value, cur_dict)
                                else:
                                    if key == "speed":
                                        value = self._parse_speed_str(value)
                                    elif key == "duplex":
                                        value = self._parse_duplex_str(value)
                                    cur_dict[key] = value
                        if "slaves" in bond_dict:
                            add_oks.append("%s found: %s" % (logging_tools.get_plural("slave", len(bond_dict["slaves"])),
                                                             ", ".join(sorted(bond_dict["slaves"].keys()))))
                            for slave_name in sorted(bond_dict["slaves"]):
                                slave_dict = bond_dict["slaves"][slave_name]
                                ret_state = self._check_speed(slave_name, cur_ns, slave_dict["speed"], add_oks, add_errors, ret_state)
                                ret_state = self._check_duplex(slave_name, cur_ns, slave_dict["duplex"], add_oks, add_errors, ret_state)
                        else:
                            add_errors.append("no slaves found")
                            ret_state = max(ret_state, limits.nag_STATE_CRITICAL)
                    else:
                        add_errors.append("no bonding info found")
                        ret_state = max(ret_state, limits.nag_STATE_CRITICAL)
                elif dev_name.startswith("ib"):
                    if cur_ns.speed:
                        # get speed from ibv_dict
                        if "active_speed" in ibv_dict and "active_width" in ibv_dict:
                            target_speed = self._parse_speed_str(cur_ns.speed)
                            ib_speed, ib_width = (
                                self._parse_speed_str(ibv_dict["active_speed"].split("(")[0].strip()),
                                int(ibv_dict["active_width"].lower().split("x")[0]))
                            ib_speed *= ib_width
                            ret_state = self._compare_speed("", add_oks, add_errors, ret_state, target_speed, ib_speed)
                        else:
                            add_errors.append("no speed info found")
                            ret_state = max(ret_state, limits.nag_STATE_CRITICAL)
                        # pprint.pprint(ibv_dict)
                        # print ethtool_dict, dev_name, cur_ns
            else:
                if cur_ns.speed and cur_ns.speed != "-":
                    ret_state = self._check_speed(None, cur_ns, ethtool_dict.get("speed", -1), add_oks, add_errors, ret_state)
                if cur_ns.duplex and cur_ns.duplex != "-":
                    ret_state = self._check_duplex(None, cur_ns, ethtool_dict.get("duplex", None), add_oks, add_errors, ret_state)
        if ibv_dict:
            # add ib info
            cur_state = ibv_dict.get("state", "no state set")
            if cur_state.lower().count("port_active"):
                add_oks.append("IB state: %s" % (cur_state))
            else:
                add_errors.append("IB state: %s" % (cur_state))
                ret_state = max(ret_state, limits.nag_STATE_CRITICAL)
        return ret_state, "%s, %s rx; %s tx%s%s | rx=%d tx=%d" % (
            dev_name,
            self.beautify_speed(value_dict["rx"]),
            self.beautify_speed(value_dict["tx"]),
            add_oks and "; %s" % ("; ".join(add_oks)) or "",
            add_errors and "; %s" % ("; ".join(add_errors)) or "",
            value_dict["rx"],
            value_dict["tx"],
        )

    def _check_speed(self, dev_name, cur_ns, dev_str, add_oks, add_errors, ret_state):
        str_prefix = "%s: " % (dev_name) if dev_name else ""
        target_speed = self._parse_speed_str(cur_ns.speed)
        if dev_str != -1:
            ret_state = self._compare_speed(str_prefix, add_oks, add_errors, ret_state, target_speed, dev_str)
        else:
            add_errors.append("%sCannot check target_speed: no ethtool information" % (str_prefix))
            ret_state = max(ret_state, limits.nag_STATE_CRITICAL)
        return ret_state

    def _compare_speed(self, str_prefix, add_oks, add_errors, ret_state, target_speed, dev_speed):
        if target_speed == dev_speed:
            add_oks.append("%starget_speed %s" % (str_prefix, self.beautify_speed(dev_speed)))
        else:
            add_errors.append(
                "%starget_speed differ: %s (target) != %s (measured)" % (
                    str_prefix,
                    self.beautify_speed(target_speed),
                    self.beautify_speed(dev_speed)
                )
            )
            ret_state = max(ret_state, limits.nag_STATE_CRITICAL)
        return ret_state

    def _check_duplex(self, dev_name, cur_ns, duplex_str, add_oks, add_errors, ret_state):
        str_prefix = "%s: " % (dev_name) if dev_name else ""
        if duplex_str is not None:
            ethtool_duplex = self._parse_duplex_str(duplex_str)
            target_duplex = self._parse_duplex_str(cur_ns.duplex)
            if target_duplex == ethtool_duplex:
                add_oks.append("%sduplex is %s" % (str_prefix, target_duplex))
            else:
                add_errors.append("%sduplex differs: %s (target) != %s (measured)" % (str_prefix, target_duplex, ethtool_duplex))
                ret_state = max(ret_state, limits.nag_STATE_CRITICAL)
        else:
            add_errors.append("%sCannot check duplex mode: not present in ethtool information" % (str_prefix))
            ret_state = max(ret_state, limits.nag_STATE_CRITICAL)
        return ret_state

    def interpret_old(self, result, parsed_coms):
        def b_str(i_val):
            f_val = float(i_val)
            if f_val < 500.:
                return "%.0f B/s" % (f_val)
            f_val /= 1000.
            if f_val < 500.:
                return "%.2f kB/s" % (f_val)
            f_val /= 1000.
            if f_val < 500.:
                return "%.2f MB/s" % (f_val)
            f_val /= 1000.
            return "%.2f GB/s" % (f_val)

        def bit_str(i_val):
            if i_val < 500:
                return "%d B/s" % (i_val)
            i_val /= 1000
            if i_val < 500:
                return "%d kB/s" % (i_val)
            i_val /= 1000
            if i_val < 500:
                return "%d MB/s" % (i_val)
            i_val /= 1000
            return "%d GB/s" % (i_val)

        def parse_ib_speed_bit(in_str):
            # parse speed for ib rate and return bits/sec
            parts = in_str.split()
            try:
                pfix = int(parts.pop(0))
                pfix *= {
                    "g": 1000 * 1000 * 1000,
                    "m": 1000 * 1000,
                    "k": 1000
                }.get(parts[0][0].lower(), 1)
            except:
                raise ValueError("Cannot parse ib_speed '%s'" % (in_str))
            return pfix

        def parse_speed_bit(in_str):
            in_str_l = in_str.lower().strip()
            in_p = re.match("^(?P<num>\d+)\s*(?P<post>\S*)$", in_str_l)
            if in_p:
                num, post = (int(in_p.group("num")), in_p.group("post"))
                pfix = ""
                for act_pfix in ["k", "m", "g", "t"]:
                    if post.startswith(act_pfix):
                        pfix = act_pfix
                        post = post[1:]
                        break
                if post.endswith("/s"):
                    per_sec = True
                    post = post[:-2]
                else:
                    per_sec = False
                if post in ["byte", "bytes"]:
                    mult = 8
                elif post in ["b", "bit", "bits", "baud", ""]:
                    mult = 1
                else:
                    raise ValueError("Cannot parse postfix '%s' of target_speed" % ("%s%s%s" % (pfix, post, per_sec and "/s" or "")))
                targ_speed = {
                    "": 1,
                    "k": 1000,
                    "m": 1000 * 1000,
                    "g": 1000 * 1000 * 1000,
                    "t": 1000 * 1000 * 1000 * 1000
                }[pfix] * num * mult
                return targ_speed
            elif in_str_l.startswith("unkn"):
                return -1
            else:
                raise ValueError("Cannot parse target_speed")

        def parse_duplex_str(in_dup):
            if in_dup.lower().count("unk"):
                return "unknown"
            elif in_dup.lower()[0] == "f":
                return "full"
            elif in_dup.lower()[0] == "h":
                return "half"
            else:
                raise ValueError("Cannot parse duplex_string '%s'" % (in_dup))
        result = hm_classes.net_to_sys(result[3:])
        if "rx" in result:
            rx_str, tx_str = ("rx", "tx")
        else:
            rx_str, tx_str = ("in", "out")
        maxs = max(result[rx_str], result[tx_str])
        ret_state = limits.check_ceiling(maxs, parsed_coms.warn, parsed_coms.crit)
        add_errors, add_oks = ([], [])
        device = result.get("device", "eth0")
        ethtool_stuff = result.get("ethtool", {})
        if ethtool_stuff is None:
            ethtool_stuff = {}
        connected = False if ethtool_stuff.get("link detected", "yes") == "no" else True
        if parsed_coms.speed == "-" or device == "lo":
            parsed_coms.speed = ""
        if parsed_coms.duplex == "-" or device == "lo":
            parsed_coms.duplex = ""
        if parsed_coms.speed:
            if device.startswith("ib"):
                if "state" in ethtool_stuff:
                    if ethtool_stuff["state"][0] == "4":
                        # check if link is up
                        try:
                            targ_speed_bit = parse_speed_bit(parsed_coms.speed)
                        except ValueError:
                            return limits.nag_STATE_CRITICAL, "Error parsing target_speed '%s' for net: %s" % (
                                parsed_coms.speed,
                                process_tools.get_except_info())
                        else:
                            if "rate" in ethtool_stuff:
                                if targ_speed_bit == parse_ib_speed_bit(ethtool_stuff["rate"]):
                                    add_oks.append("target_speed %s" % (ethtool_stuff["rate"]))
                                else:
                                    add_errors.append("target_speed differ: %s (target) != %s (measured)" % (bit_str(targ_speed_bit), ethtool_stuff["rate"]))
                            else:
                                add_errors.append("no rate entry found")
                                ret_state = limits.nag_STATE_CRITICAL
                    else:
                        add_errors.append("Link has wrong state (%s)" % (ethtool_stuff["state"]))
                        ret_state = limits.nag_STATE_CRITICAL
                else:
                    # no state, cannot check if up or down
                    add_errors.append("Cannot check target_speed: no state information")
                    ret_state = limits.nag_STATE_CRITICAL
                    connected = False
            else:
                if connected:
                    if "speed" in ethtool_stuff:
                        try:
                            targ_speed_bit = parse_speed_bit(parsed_coms.speed)
                        except ValueError:
                            return limits.nag_STATE_CRITICAL, "Error parsing target_speed '{}' for net: {}".format(
                                parsed_coms.speed,
                                process_tools.get_except_info())
                        else:
                            if targ_speed_bit == parse_speed_bit(ethtool_stuff["speed"]):
                                add_oks.append("target_speed %s" % (ethtool_stuff["speed"]))
                            else:
                                if parse_speed_bit(ethtool_stuff["speed"]) == -1:
                                    connected = False
                                else:
                                    add_errors.append("target_speed differ: %s (target) != %s (measured)" % (bit_str(targ_speed_bit), ethtool_stuff["speed"]))
                                ret_state = limits.nag_STATE_CRITICAL
                    else:
                        add_errors.append("Cannot check target_speed: no ethtool information")
                        ret_state = limits.nag_STATE_CRITICAL
        if parsed_coms.duplex and not device.startswith("ib"):
            if connected:
                if "duplex" in ethtool_stuff:
                    try:
                        targ_duplex = parse_duplex_str(parsed_coms.duplex)
                    except ValueError:
                        return limits.nag_STATE_CRITICAL, "Error parsing target_duplex '%s' for net: %s" % (parsed_coms.duplex,
                                                                                                            process_tools.get_except_info())
                    else:
                        if targ_duplex == parse_duplex_str(ethtool_stuff["duplex"]):
                            add_oks.append("duplex_mode is %s" % (ethtool_stuff["duplex"]))
                        else:
                            if connected:
                                if parse_duplex_str(ethtool_stuff["duplex"]) == "unknown":
                                    connected = False
                                else:
                                    add_errors.append("duplex_mode differ: %s != %s" % (parsed_coms.duplex, ethtool_stuff["duplex"]))
                                ret_state = limits.nag_STATE_CRITICAL
                else:
                    add_errors.append("Cannot check duplex mode: no ethtool information")
                    ret_state = limits.nag_STATE_CRITICAL
        if not connected:
            add_errors.append("No cable connected?")
            ret_state = max(ret_state, limits.nag_STATE_WARNING)
        report_device = result.get("report_device", device)
        return ret_state, "{}, {} rx; {} tx{}{}{}".format(
            device,
            b_str(result[rx_str]),
            b_str(result[tx_str]),
            add_oks and "; %s" % ("; ".join(add_oks)) or "",
            add_errors and "; %s" % ("; ".join(add_errors)) or "",
            report_device != device and "; reporting device is %s" % (report_device) or ""
        )


class bridge_info_command(hm_classes.hm_command):
    info_str = "bridge information"

    def __call__(self, srv_com, cur_ns):
        srv_com["bridges"] = self.module._check_for_bridges()

    def interpret(self, srv_com, cur_ns):
        bridge_dict = srv_com["bridges"]
        br_names = sorted(bridge_dict.keys())
        out_f = ["found {}:".format(logging_tools.get_plural("bridge", len(br_names)))]
        for br_name in br_names:
            br_stuff = bridge_dict[br_name]
            out_f.append(
                "{:<16s}: mtu {:4d}, flags 0x{:x}, features {}, {}: {}".format(
                    br_name,
                    br_stuff["mtu"],
                    br_stuff["flags"],
                    "0x{:x}".format(br_stuff["features"]) if "features" in br_stuff else "---",
                    logging_tools.get_plural("interface", len(br_stuff["interfaces"])),
                    ", ".join(sorted(br_stuff["interfaces"]))
                )
            )
        return limits.nag_STATE_OK, "%s" % ("\n".join(out_f))


class network_info_command(hm_classes.hm_command):
    info_str = "network information"

    def __call__(self, srv_com, cur_ns):
        srv_com["bridges"] = self.module._check_for_bridges()
        srv_com["networks"] = self.module._check_for_networks()

    def interpret(self, srv_com, cur_ns):
        bridge_dict = srv_com["bridges"]
        net_dict = srv_com["networks"]
        net_names = sorted(net_dict.keys())
        out_list = logging_tools.new_form_list()
        for net_name in net_names:
            net_stuff = net_dict[net_name]
            out_list.append(
                [
                    logging_tools.form_entry(net_name, header="name"),
                    logging_tools.form_entry("yes" if net_name in bridge_dict.keys() else "no", header="bridge"),
                    logging_tools.form_entry(",".join(net_stuff["flags"]), header="flags"),
                    logging_tools.form_entry(
                        ", ".join(
                            [
                                "{}={}".format(
                                    key,
                                    str(net_stuff["features"][key])
                                ) for key in sorted(net_stuff["features"].keys())
                            ]
                        ) if net_stuff["features"] else "none",
                        header="features"
                    )
                    ]
                )
            for link_key in sorted(net_stuff["links"]):
                link_stuff = net_stuff["links"][link_key]
                if type(link_stuff[0]) == bool:
                    link_str = ""
                else:
                    link_str = " ".join(link_stuff)
                out_list.append([logging_tools.form_entry("  - link/%s%s" % (link_key, ": %s" % (link_str) if link_str else ""))])
            for net in net_stuff["inet"]:
                out_list.append([logging_tools.form_entry("  - inet %s" % (net))])
        return limits.nag_STATE_OK, "found %s:\n%s" % (logging_tools.get_plural("network device", len(net_names)),
                                                       str(out_list))


class iptables_info_command(hm_classes.hm_command):
    info_str = "iptables information"

    def __init__(self, name):
        hm_classes.hm_command.__init__(self, name, positional_arguments=True)
        self.parser.add_argument("-w", dest="warn", type=str)
        self.parser.add_argument("-c", dest="crit", type=str)

    def __call__(self, srv_com, cur_ns):
        if "arguments:arg0" in srv_com:
            req_chain = srv_com["arguments:arg0"].text.strip()
        else:
            req_chain = ""
        srv_com["rules_stat"] = self.module._check_iptables(req_chain)

    def interpret(self, srv_com, cur_ns):
        res_dict = srv_com["rules_stat"]
        detail_level, required_chain = (res_dict.pop("detail_level"), res_dict.pop("required_chain"))
        if not res_dict:
            return limits.nag_STATE_CRITICAL, "No chains found according to filter (%s, %d)" % (required_chain, detail_level)
        else:
            ret_state = limits.nag_STATE_OK
            all_chains = sum([c_dict.keys() for c_dict in res_dict.itervalues()], [])
            num_lines = sum([sum([c_dict["lines"] for _c_key, c_dict in t_dict.iteritems()], 0) for _t_key, t_dict in res_dict.iteritems()], 0)
            if cur_ns.crit is not None and num_lines < cur_ns.crit:
                ret_state = max(ret_state, limits.nag_STATE_CRITICAL)
            elif cur_ns.warn is not None and num_lines < cur_ns.warn:
                ret_state = max(ret_state, limits.nag_STATE_WARNING)
            return ret_state, "{}{} ({}, {:d}): {}".format(
                logging_tools.get_plural("chain", len(all_chains)),
                " (%s)" % (all_chains[0]) if len(all_chains) == 1 else "",
                required_chain or "ALL",
                detail_level,
                logging_tools.get_plural("rule", num_lines)
            )


class ntpq_struct(hm_classes.subprocess_struct):
    class Meta:
        max_usage = 2
        id_str = "ntpq"
        verbose = False

    def __init__(self, log_com, srv_com):
        self.__log_com = log_com
        hm_classes.subprocess_struct.__init__(
            self,
            srv_com,
            "/usr/sbin/ntpq -p",
        )

    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        self.__log_com("[ntpq] %s" % (what), level)

    def process(self):
        if self.run_info["result"]:
            self.srv_com.set_result(
                "error (%d): %s" % (self.run_info["result"], self.read().strip()),
                server_command.SRV_REPLY_STATE_ERROR,
            )
        else:
            output = self.read()
            self.srv_com["output"] = output


class ntp_status_command(hm_classes.hm_command):
    info_str = "show NTP status"

    def __call__(self, srv_com, cur_ns):
        cur_ntpq_s = ntpq_struct(
            self.log,
            srv_com,
        )
        return cur_ntpq_s

    def interpret(self, srv_com, cur_ns):
        _lines = srv_com["*output"].split("\n")
        if len(_lines) > 1:
            _peers = {}
            _peer_types = {}
            for _line in _lines[2:]:
                if _line.strip():
                    peer_name = _line[1:].split()[0]
                    _peers[peer_name] = _line[0]
                    _peer_types.setdefault(_line[0], []).append(peer_name)
            ret_state = limits.nag_STATE_OK
            if "*" in _peer_types:
                primary_peer = _peer_types["*"][0]
                if primary_peer == "LOCAL(0)":
                    ret_state = max(ret_state, limits.nag_STATE_WARNING)
            else:
                primary_peer = None
                ret_state = max(ret_state, limits.nag_STATE_CRITICAL)
            if "+" in _peer_types:
                good_peers = set(_peer_types["+"])
            else:
                good_peers = set()
            ignored_peers = set(_peers) - (good_peers | set([primary_peer]))
            return ret_state, "%s defined, %s" % (
                logging_tools.get_plural("peer", len(_peers)),
                ", ".join([entry for entry in [
                    "primary is {}".format(primary_peer) if primary_peer else "",
                    "good: {}".format(", ".join(sorted(good_peers))) if good_peers else "",
                    "ignored: {}".format(", ".join(sorted(ignored_peers))) if ignored_peers else "",
                ] if entry]))
        else:
            return limits.nag_STATE_CRITICAL, _lines[0]
