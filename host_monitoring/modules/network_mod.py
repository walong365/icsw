#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008,2009,2010,2012 Andreas Lang-Nevyjel, init.at
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

import sys
import time
import threading
from host_monitoring import limits
import copy
from host_monitoring import hm_classes
import net_tools
import os.path
import commands
import process_tools
import server_command
import re
import logging_tools
import pprint
from lxml import etree
from lxml.builder import E

# name of total-device
TOTAL_DEVICE_NAME = "all"
# name of bonding info filename
#BONDFILE_NAME = "bondinfo"
# devices to check
NET_DEVICES = ["eth", "lo", "myr", "ib", "xenbr", "vmnet", "tun", "tap", TOTAL_DEVICE_NAME]
# devices for detailed statistics
DETAIL_DEVICES = ["eth", "tun", "tap"]
# devices for ethtool
ETHTOOL_DEVICES = ["eth", "peth", "tun", "tap"]
# devices to check for xen-host
XEN_DEVICES = ["vif"]
# minimum update time
MIN_UPDATE_TIME = 4

REMOTE_PING_FILE = "/etc/sysconfig/host-monitoring.d/remote_ping"

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
            self.log("not ethtool found", logging_tools.LOG_LEVEL_WARN)
        self.ethtool_path = None
    def init_machine_vector(self, mv):
        self.act_nds = netspeed(self.ethtool_path)#self.bonding_devices)
    def update_machine_vector(self, mv):
        try:
            self._net_int(mv)
        except:
            self.log("error in net_int:",
                     logging_tools.LOG_LEVEL_ERROR)
            for log_line in process_tools.exception_info().log_lines:
                self.log(" - %s" % (log_line), logging_tools.LOG_LEVEL_ERROR)
    def _net_int(self, mvect):
        act_time = time.time()
        time_diff = act_time - self.last_update
        if time_diff < 0:
            self.log("(net_int) possible clock-skew detected, adjusting (%s since last request)" % (logging_tools.get_diff_time_str(time_diff)),
                     logging_tools.LOG_LEVEL_WARN)
            self.last_update = act_time
        elif time_diff < MIN_UPDATE_TIME:
            self.log("(net_int) too many update requests, skipping this one (last one %s ago; %d seconds minimum)" % (logging_tools.get_diff_time_str(time_diff),
                                                                                                                      MIN_UPDATE_TIME),
                     logging_tools.LOG_LEVEL_WARN)
        else:
            self.act_nds.update()
            self.last_update = time.time()
        nd_dict = self.act_nds.make_speed_dict()
        #print nd_dict
        if nd_dict:
            # add total info
            total_dict = {}
            for key, stuff in nd_dict.iteritems():
                for s_key, s_value in stuff.iteritems():
                    total_dict.setdefault(s_key, 0)
                    total_dict[s_key] += s_value
            nd_dict[TOTAL_DEVICE_NAME] = total_dict
    ##         import pprint
    ##         pprint.pprint(nd_dict)
        for key in [x for x in self.dev_dict.keys() if not nd_dict.has_key(x)]:
            mvect.unregister_entry("net.%s.rx" % (key))
            mvect.unregister_entry("net.%s.tx" % (key))
            if [True for x in DETAIL_DEVICES if key.startswith(x)]:
                mvect.unregister_entry("net.%s.rxerr"   % (key))
                mvect.unregister_entry("net.%s.txerr"   % (key))
                mvect.unregister_entry("net.%s.rxdrop"  % (key))
                mvect.unregister_entry("net.%s.txdrop"  % (key))
                mvect.unregister_entry("net.%s.carrier" % (key))
        for key in [x for x in nd_dict.keys() if not self.dev_dict.has_key(x)]:
            mvect.register_entry("net.%s.rx" % (key), 0, "bytes per second received by $2"   , "Byte/s", 1024)
            mvect.register_entry("net.%s.tx" % (key), 0, "bytes per second transmitted by $2", "Byte/s", 1024)
            if [True for x in DETAIL_DEVICES if key.startswith(x)]:
                mvect.register_entry("net.%s.rxerr"   % (key), 0, "receive error packets per second on $2"   , "1/s", 1000)
                mvect.register_entry("net.%s.txerr"   % (key), 0, "transmit error packets per second on $2"  , "1/s", 1000)
                mvect.register_entry("net.%s.rxdrop"  % (key), 0, "received packets dropped per second on $2", "1/s", 1000)
                mvect.register_entry("net.%s.txdrop"  % (key), 0, "received packets dropped per second on $2", "1/s", 1000)
                mvect.register_entry("net.%s.carrier" % (key), 0, "carrier errors per second on $2"          , "1/s", 1000)
        self.dev_dict = nd_dict
        for key in self.dev_dict.keys():
            mvect["net.%s.rx" % (key)] = self.dev_dict[key]["rx"]
            mvect["net.%s.tx" % (key)] = self.dev_dict[key]["tx"]
            if [True for x in DETAIL_DEVICES if key.startswith(x)]:
                mvect["net.%s.rxerr"   % (key)] = self.dev_dict[key]["rxerr"]
                mvect["net.%s.txerr"   % (key)] = self.dev_dict[key]["txerr"]
                mvect["net.%s.rxdrop"  % (key)] = self.dev_dict[key]["rxdrop"]
                mvect["net.%s.txdrop"  % (key)] = self.dev_dict[key]["txdrop"]
                mvect["net.%s.carrier" % (key)] = self.dev_dict[key]["carrier"]
        return
        # check for ping_hosts
        if not self._mvect_phd_synced:
            self._mvect_phd_synced = True
            for key in self._mvect_phd:
                r_key = key.replace(".", "_")
                for s_key in ["min", "mean", "max"]:
                    mvect.reg_entry("ping.%s.%s" % (r_key, s_key), 0.0, "%s latency for %s" % (s_key, self.ping_hosts[key]) , "s", 1000)
        for key, res in self._mvect_phd.iteritems():
            r_key = key.replace(".", "_")
            for s_key in ["min", "mean", "max"]:
                mvect.reg_update(logger, "ping.%s.%s" % (r_key, s_key), res["latency_%s" % (s_key)] if res["reached"] else None)
        if self.ping_hosts:
            self.ping_object.add_icmp_client(net_tools.icmp_client(host_list=self.ping_hosts.keys(),
                                                                   num_ping=3,
                                                                   timeout=5.0,
                                                                   fast_mode=False,
                                                                   finish_call=self._icmp_finish,
                                                                   flood_ping=False))
    
class my_modclass(hm_classes.hm_fileinfo):
    def __init__(self, **args):
        hm_classes.hm_fileinfo.__init__(self,
                                        "network",
                                        "monitors important network parameters (throughput etc.)",
                                        **args)
    def init(self, mode, logger, basedir_name, **kwargs):
        #print "Init module "+NAME+" for mode %s" % (mode)
        if mode == "i":
            self.dev_dict = {}
            self.bonding_devices = {}
            # check bridges
            self._check_for_bridges(logger)
        elif mode == "s" and "ping_object" in kwargs:
            self.ping_hosts = {}
            self.ping_object = kwargs["ping_object"]
            if os.path.isfile(REMOTE_PING_FILE):
                for line in file(REMOTE_PING_FILE, "r").readlines():
                    line = line.strip()
                    if line and not line.startswith("#"):
                        line_parts = line.strip().split()
                        if len(line_parts) == 1:
                            self.ping_hosts[line_parts[0]] = line_parts[0]
                        else:
                            self.ping_hosts[line_parts[0]] = " ".join(line_parts[1:])
            if self.ping_hosts:
                logger.log("initiated remote_pinger with %s: %s" % (logging_tools.get_plural("remote host", len(self.ping_hosts)),
                                                                    ", ".join(sorted(self.ping_hosts))))
            self._init_mvect_ping_hosts()
    def process_server_args(self, glob_config, logger):
        #print "Processing ", opts
        ok, why = (1, "")
        if os.path.isfile("%s/%s" % (glob_config["BASEDIR_NAME"], BONDFILE_NAME)):
            bdevs = [y for y in [x.strip() for x in file("%s/%s" % (glob_config["BASEDIR_NAME"], BONDFILE_NAME), "r").readlines()]]
            try:
                for bdev in bdevs:
                    bdl = bdev.split("=")
                    self.bonding_devices[bdl[0]] = bdl[1].split(":")
            except:
                ok, why = (0, "Error parsing bonding devices.")
        return ok, why
    def process_client_args(self, opts, hmb):
        ok, why = (1, "")
        my_lim = limits.limits()
        for opt, arg in opts:
            if hmb.name == "net":
                #print opt, arg
                if opt == "-w":
                    if my_lim.set_warn_val(arg) == 0:
                        ok, why = (0, "Can't parse warning value !")
                if opt == "-c":
                    if my_lim.set_crit_val(arg) == 0:
                        ok, why = (0, "Can't parse critical value !")
                if opt == "-s":
                    my_lim.set_add_var("sc", arg)
                if opt == "-d":
                    my_lim.set_add_var("dp", arg)
            if hmb.name in ["bridge_info", "network_info"]:
                if opt in ("-r", "--raw"):
                    my_lim.set_add_flags("R")
        return ok, why, [my_lim]
    def init_m_vect(self, mv, logger):
        self.last_update = time.time()
        self.act_nds = netspeed(self.bonding_devices)
    def update_m_vect(self, mv, logger):
        int_error = "IntError"
        try:
            self._net_int(mv, logger)
        except int_error:
            print "update_m_vect: %s" % (process_tools.get_except_info())
    def _net_int(self, mvect, logger):
        act_time = time.time()
        time_diff = act_time - self.last_update
        self.act_nds.lock()
        if time_diff < 0:
            logger.warning("(net_int) possible clock-skew detected, adjusting (%s since last request)" % (logging_tools.get_diff_time_str(time_diff)))
            self.last_update = act_time
        elif time_diff < MIN_UPDATE_TIME:
            logger.warning("(net_int) too many update requests, skipping this one (last one %s ago; %d seconds minimum)" % (logging_tools.get_diff_time_str(time_diff),
                                                                                                                            MIN_UPDATE_TIME))
        else:
            self.act_nds.update()
            self.last_update = time.time()
        nd_dict = self.act_nds.make_speed_dict()
        if nd_dict:
            # add total info
            total_dict = {}
            for key, stuff in nd_dict.iteritems():
                for s_key, s_value in stuff.iteritems():
                    total_dict.setdefault(s_key, 0)
                    total_dict[s_key] += s_value
            nd_dict[TOTAL_DEVICE_NAME] = total_dict
    ##         import pprint
    ##         pprint.pprint(nd_dict)
        self.act_nds.unlock()
        for key in [x for x in self.dev_dict.keys() if not nd_dict.has_key(x)]:
            mvect.unreg_entry("net.%s.rx" % (key))
            mvect.unreg_entry("net.%s.tx" % (key))
            if [True for x in DETAIL_DEVICES if key.startswith(x)]:
                mvect.unreg_entry("net.%s.rxerr"   % (key))
                mvect.unreg_entry("net.%s.txerr"   % (key))
                mvect.unreg_entry("net.%s.rxdrop"  % (key))
                mvect.unreg_entry("net.%s.txdrop"  % (key))
                mvect.unreg_entry("net.%s.carrier" % (key))
        for key in [x for x in nd_dict.keys() if not self.dev_dict.has_key(x)]:
            mvect.reg_entry("net.%s.rx" % (key), 0, "bytes per second received by $2"   , "Byte/s", 1024)
            mvect.reg_entry("net.%s.tx" % (key), 0, "bytes per second transmitted by $2", "Byte/s", 1024)
            if [True for x in DETAIL_DEVICES if key.startswith(x)]:
                mvect.reg_entry("net.%s.rxerr"   % (key), 0, "receive error packets per second on $2"   , "1/s", 1000)
                mvect.reg_entry("net.%s.txerr"   % (key), 0, "transmit error packets per second on $2"  , "1/s", 1000)
                mvect.reg_entry("net.%s.rxdrop"  % (key), 0, "received packets dropped per second on $2", "1/s", 1000)
                mvect.reg_entry("net.%s.txdrop"  % (key), 0, "received packets dropped per second on $2", "1/s", 1000)
                mvect.reg_entry("net.%s.carrier" % (key), 0, "carrier errors per second on $2"          , "1/s", 1000)
        self.dev_dict = nd_dict
        for key in self.dev_dict.keys():
            mvect.reg_update(logger, "net.%s.rx" % (key), self.dev_dict[key]["rx"])
            mvect.reg_update(logger, "net.%s.tx" % (key), self.dev_dict[key]["tx"])
            if [True for x in DETAIL_DEVICES if key.startswith(x)]:
                mvect.reg_update(logger, "net.%s.rxerr"   % (key), self.dev_dict[key]["rxerr"])
                mvect.reg_update(logger, "net.%s.txerr"   % (key), self.dev_dict[key]["txerr"])
                mvect.reg_update(logger, "net.%s.rxdrop"  % (key), self.dev_dict[key]["rxdrop"])
                mvect.reg_update(logger, "net.%s.txdrop"  % (key), self.dev_dict[key]["txdrop"])
                mvect.reg_update(logger, "net.%s.carrier" % (key), self.dev_dict[key]["carrier"])
        # check for ping_hosts
        if not self._mvect_phd_synced:
            self._mvect_phd_synced = True
            for key in self._mvect_phd:
                r_key = key.replace(".", "_")
                for s_key in ["min", "mean", "max"]:
                    mvect.reg_entry("ping.%s.%s" % (r_key, s_key), 0.0, "%s latency for %s" % (s_key, self.ping_hosts[key]) , "s", 1000)
        for key, res in self._mvect_phd.iteritems():
            r_key = key.replace(".", "_")
            for s_key in ["min", "mean", "max"]:
                mvect.reg_update(logger, "ping.%s.%s" % (r_key, s_key), res["latency_%s" % (s_key)] if res["reached"] else None)
        if self.ping_hosts:
            self.ping_object.add_icmp_client(net_tools.icmp_client(host_list=self.ping_hosts.keys(),
                                                                   num_ping=3,
                                                                   timeout=5.0,
                                                                   fast_mode=False,
                                                                   finish_call=self._icmp_finish,
                                                                   flood_ping=False))
    def _init_mvect_ping_hosts(self):
        self._mvect_phd_synced = False
        self._mvect_phd = dict([(key, {"reached"      : True,
                                       "latency_min"  : 0.0,
                                       "latency_mean" : 0.0,
                                       "latency_max"  : 0.0,
                                       "info"         : value}) for key, value in self.ping_hosts.iteritems()])
    def _icmp_finish(self, icmp_obj):
        for host, res in icmp_obj.get_result().iteritems():
            if host in self._mvect_phd:
                if res["received"]:
                    self._mvect_phd[host].update({"reached"      : True,
                                                  "latency_min"  : res["min_time"],
                                                  "latency_mean" : res["mean_time"],
                                                  "latency_max"  : res["max_time"]})
                else:
                    self._mvect_phd[host]["reached"] = False
    def _check_for_bridges(self, logger):
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
            b_dict[ent] = {"interfaces" : os.listdir("%s/brif" % (loc_dir))}
            for key in ["address", "addr_len", "features", "flags", "mtu"]:
                value = file("%s/%s" % (loc_dir, key), "r").read().strip()
                if value.isdigit():
                    b_dict[ent][key] = int(value)
                elif value.startswith("0x"):
                    b_dict[ent][key] = int(value, 16)
                else:
                    b_dict[ent][key] = value
        return b_dict
    def _check_for_networks(self, logger):
        n_dict = {}
        ip_com = "ip addr show"
        c_stat, c_out = commands.getstatusoutput(ip_com)
        if c_stat:
            logger.error("error calling %s (%d): %s" % (ip_com,
                                                        c_stat,
                                                        c_out))
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
                        dev_dict = {"idx"      : int(act_net_num),
                                    "flags"    : flags[1:-1].split(","),
                                    "features" : f_dict,
                                    "links"    : {},
                                    "inet"     : []}
                        n_dict[act_net_name.strip()] = dev_dict
                    else:
                        logger.error("cannot parse line %s" % (line))
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
    def __init__(self, name, mapping, ethtool_path):
        self.name = name
        self.nd_mapping = mapping
        self.ethtool_path = ethtool_path
        self.nd_keys = set(self.nd_mapping) - set([None])
        self.invalidate()
        self.__history = []
        self.__check_ethtool = any([self.name.startswith(check_name) for check_name in ETHTOOL_DEVICES])
        self.last_update = time.time() - 3600
        self.update_ethtool()
    def invalidate(self):
        self.found = False
    def feed(self, cur_line):
        self.found = True
        line_dict = dict([(key, long(value)) for key, value in zip(self.nd_mapping, cur_line.split()) if key])
        if len(self.__history) > ND_HIST_SIZE:
            self.__history = self.__history[1:]
        self.__history.append((time.time(), line_dict))
        #print "*", self.name, self.get_speed()
    def get_speed(self):
        res_dict = dict([(key, []) for key in self.nd_keys])
        if self.__history:
            last_time, last_dict = self.__history[0]
            for cur_time, cur_dict in self.__history[1:]:
                if cur_time > last_time:
                    diff_time = max(1, cur_time - last_time)
                    for key in self.nd_keys:
                        res_dict[key].append(min(1024 * 1024 * 1024 * 1024, max(0, (cur_dict[key] - last_dict[key]) / diff_time)))
                last_time, last_dict = (cur_time, cur_dict)
        res_dict = dict([(key, sum(value) / len(value) if len(value) else 0.) for key, value in res_dict.iteritems()])
        return res_dict
    def update_ethtool(self):
        cur_time = time.time()
        if cur_time > self.last_update + 30:
            res_dict = {}
            if self.__check_ethtool and self.ethtool_path:
                ce_stat, ce_out = commands.getstatusoutput("%s %s" % (self.ethtool_path, self.name))
                if not ce_stat:
                    res_dict = dict([(key.lower(), value.strip()) for key, value in [line.strip().split(":", 1) for line in ce_out.split("\n") if line.count(":")] if len(value.strip())])
            self.last_update = cur_time
            self.ethtool_results = res_dict
    def get_xml(self, srv_com):
        cur_speed = self.get_speed()
        result = srv_com.builder(
            "device_%s" % (self.name),
            srv_com.builder("values",
                            *[srv_com.builder(key, "%.2f" % (value)) for key, value in cur_speed.iteritems()]
                            )
        )
        if self.ethtool_results:
            result.append(
                srv_com.builder("ethtool",
                    *[srv_com.builder("value", value, name=key) for key, value in self.ethtool_results.iteritems()]
                )
            )
        return result
        
class netspeed(object):
    def __init__(self, ethtool_path):#, bonding = None):
        self.ethtool_path = ethtool_path
        cur_head = sum([part.split() for part in file("/proc/net/dev", "r").readlines()[1].strip().split("|")], [])
        if len(cur_head) == 17:
            self.nd_mapping = ["rx", None, "rxerr", "rxdrop", None, None, None, None,
                               "tx", None, "txerr", "txdrop", None, None, "carrier", None]
        else:
            raise ValueError, "unknown /proc/net/dev layout"
        self.nst_size = 10
        self.__o_time, self.__a_time = (0., time.time() - 1.1)
        self.__o_stat, self.__a_stat = ({}, {})
        self.nst = {}
        self.devices = {}
        # ethtool info
        self.ethtool_dict = {}
        # extra info (infiniband and so on)
        self.extra_dict = {}
        #self.__b_array = bonding
        self.__idx_dict = {"rx"      : 0,
                           "tx"      : 8,
                           "rxerr"   : 2,
                           "txerr"   : 10,
                           "rxdrop"  : 3,
                           "txdrop"  : 11,
                           "carrier" : 14}
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
##        r_dict = {}
##        for ifn, s_list in self.nst.iteritems():
##            speed = dict([(k, 0) for k in self.__keys])
##            num = len(s_list) - 1
##            if not num:
##                if self.nst[ifn]:
##                    speed = s_list[0]
##            else:
##                while len(s_list) > 1:
##                    act_speed = s_list.pop(0)
##                    for k in self.__keys:
##                        speed[k] += act_speed[k] / num
##            r_dict[ifn] = speed
##        return r_dict
        return dict([(key, self[key].get_speed()) for key in self.keys()])
    def update(self):
        ntime = time.time()
        if abs(ntime - self.__a_time) > 1:
            try:
                line_list = [(dev_name.strip(), dev_stats) for dev_name, dev_stats in [line.split(":", 1) for line in file("/proc/net/dev", "r").read().split("\n") if line.count(":")]]
                ndev_dict = dict([(dev_name.strip(), [long(cur_val) for cur_val in dev_stats.split()]) for dev_name, dev_stats in [line.split(":", 1) for line in file("/proc/net/dev", "r").read().split("\n") if line.count(":")]])
            except:
                pass
            else:
                # invalidate devices
                for key in self.keys():
                    self[key].invalidate()
                for key, value in line_list:
                    if key not in self:
                        self[key] = net_device(key, self.nd_mapping, self.ethtool_path)
                    self[key].feed(value)
                    self[key].update_ethtool()
            self.__a_time = ntime
        return
        if False:
            if False:
                self.__o_stat, self.__o_time = (self.__a_stat,
                                                self.__a_time)
                self.__a_stat, self.__a_time = (dict([(key, dict([(x, value[y]) for x, y in self.__idx_dict.iteritems()])) for key, value in ndev_dict.iteritems()]),
                                                ntime)
                # handle bonding devices, FIXME, take from /sys/class
##                if self.__b_array:
##                    for bdn, bdl in self.__b_array.iteritems():
##                        add = True
##                        b_vals = dict([(x, 0L) for x in self.__keys])
##                        for bdl_e in bdl:
##                            if not self.__a_stat.has_key(bdl_e):
##                                add = False
##                                break
##                            else:
##                                for k in self.__keys:
##                                    b_vals[k] += self.__a_stat[bdl_e][k]
##                        if add:
##                            self.__a_stat[bdn] = b_vals
                t_diff = self.__a_time - self.__o_time
                for if_name, act_io in self.__a_stat.iteritems():
                    if [True for key in NET_DEVICES if if_name.startswith(key)]:
                        if if_name in self.__o_stat:
##                            if if_name.startswith("eth") and self.__o_stat.has_key("p%s" % (if_name)) and self.__a_stat.has_key("p%s" % (if_name)):
##                                old_io, act_io = (self.__o_stat["p%s" % (if_name)],
##                                                  self.__a_stat["p%s" % (if_name)])
##                            else:
                            old_io = self.__o_stat[if_name]
                            speed = {}
                            for d_name in self.__keys:
                                sub = act_io[d_name] - old_io[d_name]
                                while sub < 0:
                                    sub += sys.maxint
                                # cap insane values (above 1 TByte)
                                if sub > max(sys.maxint / 8, 1024 * 1024 * 1024 * 1024):
                                    sub = 0
                                speed[d_name] = int(sub / t_diff)
                            if if_name not in self.nst:
                                self.nst[if_name] = []
                            if len(self.nst[if_name]) > self.nst_size:
                                self.nst[if_name].pop(0)
                            self.nst[if_name].append(speed)
                    elif [True for x in XEN_DEVICES if if_name.startswith(x)]:
                        self.__is_xen_host = True
                # remove unknown netdevices from speed_dict
                self.ethtool_dict, self.extra_dict = ({}, {})
                for ifn in self.__a_stat.keys():
                    etht_dict = {}
                    if [True for check_name in ETHTOOL_DEVICES if ifn.startswith(check_name)]:
                        if self.ethtool_path:
                            if ifn.startswith("eth") and self.__a_stat.has_key("p%s" % (ifn)):
                                stat, out = commands.getstatusoutput("%s p%s" % (self.ethtool_path, ifn))
                            else:
                                stat, out = commands.getstatusoutput("%s %s" % (self.ethtool_path, ifn))
                        else:
                            stat, out = (1, "ethtool_path not set")
                        if not stat:
                            etht_dict = dict([(k.lower().strip(), v.lower().strip()) for k, v in [y for y in [x.strip().split(":", 1) for x in out.split("\n")] if len(y) == 2] if len(v) and k.lower() in ["speed", "duplex", "link detected"]])
                    elif ifn.startswith("ib"):
                        # simple mapping, FIXME
                        if ifn[2:].isdigit():
                            port_dir = "/sys/class/infiniband/mthca0/ports/%d" % (int(ifn[2]) + 1)
                            if os.path.isdir(port_dir):
                                for entry in os.listdir(port_dir):
                                    if entry in ["state", "phys_state", "rate"]:
                                        etht_dict[entry] = open("%s/%s" % (port_dir, entry), "r").read().strip()
                                counter_path = "%s/counters" % (port_dir)
                                if os.path.isdir(counter_path):
                                    ex_dict = {}
                                    for entry in os.listdir(counter_path):
                                        try:
                                            ex_dict[entry] = int(open("%s/%s" % (counter_path, entry), "r").read().strip())
                                        except:
                                            pass
                                    if ex_dict:
                                        self.extra_dict[ifn] = ex_dict
                    if etht_dict:
                        self.ethtool_dict[ifn] = etht_dict
                #pprint.pprint(self.nst)
        else:
            self.__a_time = ntime

class ping_sp_struct(hm_classes.subprocess_struct):
    seq_num = 0
    def __init__(self, srv_com, target_host, num_pings, timeout):
        hm_classes.subprocess_struct.__init__(self, srv_com, "")
        self.target_host, self.num_pings, self.timeout = (target_host, num_pings, timeout)
        ping_sp_struct.seq_num += 1
        self.seq_str = "ping_%d" % (ping_sp_struct.seq_num)
    def run(self):
        self.tart_time = time.time()
        return ("ping", self.seq_str, self.target_host, self.num_pings, self.timeout)
    def process(self, *args):
        id_str, num_sent, num_received, time_field, error_str = args
        self.terminated = True
        cur_b = self.srv_com.builder
        self.srv_com["result"] = cur_b("ping_result",
                                       error_str,
                                       cur_b("times",
                                             *[cur_b("time", "%.4f" % (cur_time)) for cur_time in time_field]),
                                       target=self.target_host,
                                       num_sent="%d" % (num_sent),
                                       num_received="%d" % (num_received))
        self.send_return()
        self.terminated = True
    class Meta:
        max_usage = 128
        twisted = True
        use_popen = False
 
class ping_command(hm_classes.hm_command):
    info_str = "ping command"
    def __init__(self, name):
        hm_classes.hm_command.__init__(self, name, positional_arguments=True)
    def __call__(self, srv_com, cur_ns):
        args = cur_ns.arguments
        if len(args) == 3:
            target_host, num_pings, timeout = args
        elif len(args) == 2:
            target_host, num_pings = args
            timeout = 5.0
        elif len(args) == 1:
            target_host = args[0]
            num_pings, timeout = (3, 5)
        else:
            srv_com["result"].attrib.update({"reply" : "wrong number of arguments (%d)" % (len(args)),
                                             "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR)})
            cur_sps, target_host = (None, None)
        if target_host:
            num_pings, timeout = (min(32, max(1, int(num_pings))),
                                  max(0.1, float(timeout)))
            cur_sps = ping_sp_struct(srv_com, target_host, num_pings, timeout)
        return cur_sps
    def interpret(self, srv_com, cur_ns):
        ping_res = srv_com["result:ping_result"]
        target = ping_res.attrib["target"]
        if ping_res.text:
            return limits.nag_STATE_CRITICAL, "%s: %s" % (target, ping_res.text)
        else:
            time_f = map(float, srv_com.xpath(ping_res, "ns:times/ns:time/text()"))
            if time_f:
                max_time, min_time, mean_time = (max(time_f),
                                                 min(time_f),
                                                 sum(time_f) / len(time_f))
            else:
                max_time, min_time, mean_time = (None, None, None)
            num_sent, num_received = (int(ping_res.attrib["num_sent"]),
                                      int(ping_res.attrib["num_received"]))
            if num_sent == num_received:
                ret_state = limits.nag_STATE_OK
            elif num_received == 0:
                ret_state = limits.nag_STATE_CRITICAL
            else:
                ret_state = limits.nag_STATE_WARNING
            if num_received == 0:
                return ret_state, "%s: no reply (%s sent)" % (target,
                                                              logging_tools.get_plural("packet", num_sent))
            else:
                if mean_time is not None:
                    if mean_time < 0.01:
                        time_info = "%.2f ms mean time" % (1000 * mean_time)
                    else:
                        time_info = "%.4f s mean time" % (mean_time)
                else:
                    time_info = "no time info"
                return ret_state, "%s: %d of %d (%s)" % (target,
                                                         num_received,
                                                         num_sent,
                                                         time_info)
    
class net_command(hm_classes.hm_command):
    info_str = "network information"
    def __init__(self, name):
        hm_classes.hm_command.__init__(self, name, positional_arguments=True)
        self.parser.add_argument("-w", dest="warn", type=str)
        self.parser.add_argument("-c", dest="crit", type=str)
        self.parser.add_argument("-s", dest="speed", type=str)
        self.parser.add_argument("-d", dest="duplex", type=str)
    def __call__(self, srv_com, cur_ns):
        if not "arguments:arg0" in srv_com:
            srv_com["result"].attrib.update({"reply" : "missing argument",
                                              "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR)})
        else:
            net_device = srv_com["arguments:arg0"].text.strip()
            if net_device in self.module.act_nds:
                srv_com["device"] = self.module.act_nds[net_device].get_xml(srv_com)
            else:
                srv_com["result"].attrib.update({"reply" : "netdevice %s not found" % (net_device),
                                                 "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR)})
    def _parse_duplex_str(self, in_dup):
        if in_dup.lower().count("unk"):
            return "unknown"
        elif in_dup.lower()[0] == "f":
            return "full"
        elif in_dup.lower()[0] == "h":
            return "half"
        else:
            raise ValueError, "Cannot parse duplex_string '%s'" % (in_dup)
    def _parse_speed_str(self, in_str):
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
                raise ValueError, "Cannot parse postfix '%s' of target_speed" % ("%s%s%s" % (pfix, post, per_sec and "/s" or ""))
            targ_speed = {""  : 1,
                          "k" : 1000,
                          "m" : 1000 * 1000,
                          "g" : 1000 * 1000 * 1000,
                          "t" : 1000 * 1000 * 1000 * 1000}[pfix] * num * mult
            return targ_speed
        elif in_str_l.startswith("unkn"):
            return -1
        else:
            raise ValueError, "Cannot parse target_speed"
    def beautify_speed(self, i_val):
        f_val = float(i_val)
        if f_val < 500.:
            return "%.0f B/s" % (f_val)
        f_val /= 1024.
        if f_val < 500.:
            return "%.2f kB/s" % (f_val)
        f_val /= 1024.
        if f_val < 500.:
            return "%.2f MB/s" % (f_val)
        f_val /= 1024.
        return "%.2f GB/s" % (f_val)
    def interpret(self, srv_com, cur_ns):
        dev_name = srv_com["arguments:arg0"].text
        value_tree = srv_com["device:device_%s:values" % (dev_name)]
        try:
            ethtool_tree = srv_com["device:device_%s:ethtool" % (dev_name)]
        except:
            ethtool_tree = []
        value_dict = dict([(el.tag.split("}")[-1], float(el.text)) for el in value_tree])
        # build ethtool helper dict
        ethtool_dict = {"link detected" : "yes"}
        ethtool_dict.update(dict([(el.get("name"), el.text) for el in ethtool_tree]))
        ethtool_dict["duplex"] = self._parse_duplex_str(ethtool_dict.get("duplex", "unknown"))
        ethtool_dict["speed"] = self._parse_speed_str(ethtool_dict.get("speed", "unknown"))
        connected = ethtool_dict["link detected"] == "yes"
        max_rxtx = max([value_dict["rx"], value_dict["tx"]])
        if cur_ns.warn:
            cur_ns.warn = self._parse_speed_str(cur_ns.warn)
        if cur_ns.crit:
            cur_ns.crit = self._parse_speed_str(cur_ns.crit)
        add_errors, add_oks, ret_state = ([], [],
                                          limits.check_ceiling(max_rxtx, cur_ns.warn, cur_ns.crit))
        if not connected:
            add_errors.append("No cable connected?")
            ret_state = max(ret_state, limits.nag_STATE_WARNING)
        if cur_ns.speed and connected:
            target_speed = self._parse_speed_str(cur_ns.speed)
            if ethtool_dict.get("speed", -1) != -1:
                if target_speed == ethtool_dict["speed"]:
                    add_oks.append("target_speed %s" % (ethtool_dict["speed"]))
                else:
                    add_errors.append("target_speed differ: %s (target) != %s (measured)" % (self.beautify_speed(targ_speed_bit), ethtool_dict["speed"]))
                    ret_state = max(ret_state, limits.nag_STATE_CRITICAL)
            else:
                add_errors.append("Cannot check target_speed: no ethtool information")
                ret_state = max(ret_state, limits.nag_STATE_CRITICAL)
        return ret_state, "%s, %s rx; %s tx%s%s" % (
            dev_name,
            self.beautify_speed(value_dict["rx"]),
            self.beautify_speed(value_dict["tx"]),
            add_oks and "; %s" % ("; ".join(add_oks)) or "",
            add_errors and "; %s" % ("; ".join(add_errors)) or "")
    def interpret_old(self, result, parsed_coms):
        def b_str(i_val):
            f_val = float(i_val)
            if f_val < 500.:
                return "%.0f B/s" % (f_val)
            f_val /= 1024.
            if f_val < 500.:
                return "%.2f kB/s" % (f_val)
            f_val /= 1024.
            if f_val < 500.:
                return "%.2f MB/s" % (f_val)
            f_val /= 1024.
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
                pfix *= {"g" : 1000 * 1000 * 1000,
                         "m" : 1000 * 1000,
                         "k" : 1000}.get(parts[0][0].lower(), 1)
            except:
                raise ValueError, "Cannot parse ib_speed '%s'" % (in_str)
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
                    raise ValueError, "Cannot parse postfix '%s' of target_speed" % ("%s%s%s" % (pfix, post, per_sec and "/s" or ""))
                targ_speed = {""  : 1,
                              "k" : 1000,
                              "m" : 1000 * 1000,
                              "g" : 1000 * 1000 * 1000,
                              "t" : 1000 * 1000 * 1000 * 1000}[pfix] * num * mult
                return targ_speed
            elif in_str_l.startswith("unkn"):
                return -1
            else:
                raise ValueError, "Cannot parse target_speed"
        def parse_duplex_str(in_dup):
            if in_dup.lower().count("unk"):
                return "unknown"
            elif in_dup.lower()[0] == "f":
                return "full"
            elif in_dup.lower()[0] == "h":
                return "half"
            else:
                raise ValueError, "Cannot parse duplex_string '%s'" % (in_dup)
        result = hm_classes.net_to_sys(result[3:])
        if result.has_key("rx"):
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
        if parsed_coms.speed:
            if device.startswith("ib"):
                if ethtool_stuff.has_key("state"):
                    if ethtool_stuff["state"][0] == "4":
                        # check if link is up
                        try:
                            targ_speed_bit = parse_speed_bit(parsed_coms.speed)
                        except ValueError:
                            return limits.nag_STATE_CRITICAL, "Error parsing target_speed '%s' for net: %s" % (parsed_coms.speed,
                                                                                                               process_tools.get_except_info())
                        else:
                            if ethtool_stuff.has_key("rate"):
                                if targ_speed_bit == parse_ib_speed_bit(ethtool_stuff["rate"]):
                                    add_oks.append("target_speed %s" % (ethtool_stuff["rate"]))
                                else:
                                    add_errors.append("target_speed differ: %s (target) != %s (measured)" % (bit_str(targ_speed_bit), ethtool_stuff["rate"]))
                            else:
                                add_errors.append("no rate entry found")
                                ret_state, state = (limits.nag_STATE_CRITICAL, "Error")
                    else:
                        add_errors.append("Link has wrong state (%s)" % (ethtool_stuff["state"]))
                        ret_state, state = (limits.nag_STATE_CRITICAL, "Error")
                else:
                    # no state, cannot check if up or down
                    add_errors.append("Cannot check target_speed: no state information")
                    ret_state, state = (limits.nag_STATE_CRITICAL, "Error")
                    connected = False
            else:
                if connected:
                    if ethtool_stuff.has_key("speed"):
                        try:
                            targ_speed_bit = parse_speed_bit(parsed_coms.speed)
                        except ValueError:
                            return limits.nag_STATE_CRITICAL, "Error parsing target_speed '%s' for net: %s" % (parsed_coms.speed,
                                                                                                               process_tools.get_except_info())
                        else:
                            if targ_speed_bit == parse_speed_bit(ethtool_stuff["speed"]):
                                add_oks.append("target_speed %s" % (ethtool_stuff["speed"]))
                            else:
                                if parse_speed_bit(ethtool_stuff["speed"]) == -1:
                                    connected = False
                                else:
                                    add_errors.append("target_speed differ: %s (target) != %s (measured)" % (bit_str(targ_speed_bit), ethtool_stuff["speed"]))
                                ret_state, state = (limits.nag_STATE_CRITICAL, "Error")
                    else:
                        add_errors.append("Cannot check target_speed: no ethtool information")
                        ret_state, state = (limits.nag_STATE_CRITICAL, "Error")
        if parsed_coms.duplex and not device.startswith("ib"):
            if connected:
                if ethtool_stuff.has_key("duplex"):
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
                                ret_state, state = (limits.nag_STATE_CRITICAL, "Error")
                else:
                    add_errors.append("Cannot check duplex mode: no ethtool information")
                    ret_state, state = (limits.nag_STATE_CRITICAL, "Error")
        if not connected:
            add_errors.append("No cable connected?")
            ret_state = max(ret_state, limits.nag_STATE_WARNING)
            state = limits.get_state_str(ret_state)
        report_device = result.get("report_device", device)
        return ret_state, "%s, %s rx; %s tx%s%s%s" % (device,
                                                      b_str(result[rx_str]),
                                                      b_str(result[tx_str]),
                                                      add_oks and "; %s" % ("; ".join(add_oks)) or "",
                                                      add_errors and "; %s" % ("; ".join(add_errors)) or "",
                                                      report_device != device and "; reporting device is %s" % (report_device) or "")
        
class net_command_old(hm_classes.hmb_command):
    def __init__(self, **args):
        hm_classes.hmb_command.__init__(self, "net", **args)
        self.help_str = "returns the througput of netdevice NET"
        self.net_only = True
        self.short_client_info = "-w N1, -c N2, -s target speed, -d duplex"
        self.long_client_info = "sets the warning or critical value to N1/N2"
        self.short_client_opts = "w:c:s:d:"
        self.short_server_info = BONDFILE_NAME
        self.long_server_info = "comma seperated list of bonding-device definitions bondX=ethY:ethZ"
    def server_call(self, cm):
        try:
            if len(cm) == 1:
                netdev_name = cm[0]
                report_netdev_name = netdev_name
                self.module_info.act_nds.lock()
                nds = self.module_info.act_nds.make_speed_dict()
                ethtool_dict = copy.deepcopy(self.module_info.act_nds.ethtool_dict)
                extra_dict   = copy.deepcopy(self.module_info.act_nds.extra_dict)
                self.module_info.act_nds.unlock()
                # check for eth0-request if only one eth-device is specified (for xen-driven hosts)
                if not nds.has_key(netdev_name) and self.module_info.act_nds.is_xen_host():
                    # check for other netdevice if only one eth-device can be found
                    eth_devs = [x for x in nds.keys() if x.startswith("eth")]
                    if netdev_name.startswith("eth") and len(eth_devs) == 1:
                        report_netdev_name = eth_devs[0]
                if nds.has_key(report_netdev_name):
                    ethtool_info = ethtool_dict.get(report_netdev_name, None)
                    # map to pethX for xen-machines
                    if not ethtool_info and report_netdev_name.startswith("eth"):
                        ethtool_info = ethtool_dict.get("p%s" % (report_netdev_name), None)
                    rets = "ok %s" % (hm_classes.sys_to_net({"device"        : netdev_name,
                                                             "rx"            : nds[report_netdev_name]["rx"],
                                                             "tx"            : nds[report_netdev_name]["tx"],
                                                             "ethtool"       : ethtool_info,
                                                             "extra"         : extra_dict.get(report_netdev_name, {}),
                                                             "report_device" : report_netdev_name}))
                else:
                    rets = "invalid netdevice %s" % (netdev_name)
            else:
                rets = "error wrong number of arguments "
            return rets
        except:
            return "error %s" % (process_tools.get_except_info())
    def client_call(self, result, parsed_coms):
        def b_str(i_val):
            f_val = float(i_val)
            if f_val < 500.:
                return "%.0f B/s" % (f_val)
            f_val /= 1024.
            if f_val < 500.:
                return "%.2f kB/s" % (f_val)
            f_val /= 1024.
            if f_val < 500.:
                return "%.2f MB/s" % (f_val)
            f_val /= 1024.
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
                pfix *= {"g" : 1000 * 1000 * 1000,
                         "m" : 1000 * 1000,
                         "k" : 1000}.get(parts[0][0].lower(), 1)
            except:
                raise ValueError, "Cannot parse ib_speed '%s'" % (in_str)
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
                    raise ValueError, "Cannot parse postfix '%s' of target_speed" % ("%s%s%s" % (pfix, post, per_sec and "/s" or ""))
                targ_speed = {""  : 1,
                              "k" : 1000,
                              "m" : 1000 * 1000,
                              "g" : 1000 * 1000 * 1000,
                              "t" : 1000 * 1000 * 1000 * 1000}[pfix] * num * mult
                return targ_speed
            elif in_str_l.startswith("unkn"):
                return -1
            else:
                raise ValueError, "Cannot parse target_speed"
        result = hm_classes.net_to_sys(result[3:])
        if result.has_key("rx"):
            rx_str, tx_str = ("rx", "tx")
        else:
            rx_str, tx_str = ("in", "out")
        maxs = max(result[rx_str], result[tx_str])
        ret_state, state = lim.check_ceiling(maxs)
        add_errors, add_oks = ([], [])
        device = result.get("device", "eth0")
        ethtool_stuff = result.get("ethtool", {})
        if ethtool_stuff is None:
            ethtool_stuff = {}
        connected = False if ethtool_stuff.get("link detected", "yes") == "no" else True
        if lim.has_add_var("sc"):
            if device.startswith("ib"):
                if ethtool_stuff.has_key("state"):
                    if ethtool_stuff["state"][0] == "4":
                        # check if link is up
                        try:
                            targ_speed_bit = parse_speed_bit(lim.get_add_var("sc"))
                        except ValueError:
                            return limits.nag_STATE_CRITICAL, "Error parsing target_speed '%s' for net: %s" % (lim.get_add_var("sc"),
                                                                                                               process_tools.get_except_info())
                        else:
                            if ethtool_stuff.has_key("rate"):
                                if targ_speed_bit == parse_ib_speed_bit(ethtool_stuff["rate"]):
                                    add_oks.append("target_speed %s" % (ethtool_stuff["rate"]))
                                else:
                                    add_errors.append("target_speed differ: %s (target) != %s (measured)" % (bit_str(targ_speed_bit), ethtool_stuff["rate"]))
                            else:
                                add_errors.append("no rate entry found")
                                ret_state, state = (limits.nag_STATE_CRITICAL, "Error")
                    else:
                        add_errors.append("Link has wrong state (%s)" % (ethtool_stuff["state"]))
                        ret_state, state = (limits.nag_STATE_CRITICAL, "Error")
                else:
                    # no state, cannot check if up or down
                    add_errors.append("Cannot check target_speed: no state information")
                    ret_state, state = (limits.nag_STATE_CRITICAL, "Error")
                    connected = False
            else:
                if connected:
                    if ethtool_stuff.has_key("speed"):
                        try:
                            targ_speed_bit = parse_speed_bit(lim.get_add_var("sc"))
                        except ValueError:
                            return limits.nag_STATE_CRITICAL, "Error parsing target_speed '%s' for net: %s" % (lim.get_add_var("sc"),
                                                                                                               process_tools.get_except_info())
                        else:
                            if targ_speed_bit == parse_speed_bit(ethtool_stuff["speed"]):
                                add_oks.append("target_speed %s" % (ethtool_stuff["speed"]))
                            else:
                                if parse_speed_bit(ethtool_stuff["speed"]) == -1:
                                    connected = False
                                else:
                                    add_errors.append("target_speed differ: %s (target) != %s (measured)" % (bit_str(targ_speed_bit), ethtool_stuff["speed"]))
                                ret_state, state = (limits.nag_STATE_CRITICAL, "Error")
                    else:
                        add_errors.append("Cannot check target_speed: no ethtool information")
                        ret_state, state = (limits.nag_STATE_CRITICAL, "Error")
        if lim.has_add_var("dp") and not device.startswith("ib"):
            if connected:
                if ethtool_stuff.has_key("duplex"):
                    try:
                        targ_duplex = parse_duplex_str(lim.get_add_var("dp"))
                    except ValueError:
                        return limits.nag_STATE_CRITICAL, "Error parsing target_duplex '%s' for net: %s" % (lim.get_add_var("dp"),
                                                                                                            process_tools.get_except_info())
                    else:
                        if targ_duplex == parse_duplex_str(ethtool_stuff["duplex"]):
                            add_oks.append("duplex_mode is %s" % (ethtool_stuff["duplex"]))
                        else:
                            if connected:
                                if parse_duplex_str(ethtool_stuff["duplex"]) == "unknown":
                                    connected = False
                                else:
                                    add_errors.append("duplex_mode differ: %s != %s" % (lim.get_add_var("dp"), ethtool_stuff["duplex"]))
                                ret_state, state = (limits.nag_STATE_CRITICAL, "Error")
                else:
                    add_errors.append("Cannot check duplex mode: no ethtool information")
                    ret_state, state = (limits.nag_STATE_CRITICAL, "Error")
        if not connected:
            add_errors.append("No cable connected?")
            ret_state = max(ret_state, limits.nag_STATE_WARNING)
            state = limits.get_state_str(ret_state)
        report_device = result.get("report_device", device)
        return ret_state, "%s: %s, %s rx; %s tx%s%s%s" % (state,
                                                          device,
                                                          b_str(result[rx_str]),
                                                          b_str(result[tx_str]),
                                                          add_oks and "; %s" % ("; ".join(add_oks)) or "",
                                                          add_errors and "; %s" % ("; ".join(add_errors)) or "",
                                                          report_device != device and "; reporting device is %s" % (report_device) or "")

class bridge_command(hm_classes.hmb_command):
    def __init__(self, **args):
        hm_classes.hmb_command.__init__(self, "bridge_info", **args)
        self.help_str = "returns Bridge information"
        self.short_client_info = "-r, --raw"
        self.long_client_info = "sets raw-output (for scripts)"
        self.short_client_opts = "r"
        self.long_client_opts = ["raw"]
    def server_call(self, cm):
        bridge_dict = self.module_info._check_for_bridges(self.logger)
        return "ok %s" % (hm_classes.sys_to_net(bridge_dict))
    def client_call(self, result, parsed_coms):
        lim = parsed_coms[0]
        raw_output = lim.get_add_flag("R")
        if raw_output:
            return limits.nag_STATE_OK, result[3:]
        else:
            bridge_dict = hm_classes.net_to_sys(result[3:])
            br_names = sorted(bridge_dict.keys())
            out_f = ["found %s:" % (logging_tools.get_plural("bridge", len(br_names)))]
            for br_name in br_names:
                br_stuff = bridge_dict[br_name]
                out_f.append("%-16s: mtu %4d, flags 0x%x, features 0x%x, %s: %s" % (br_name,
                                                                                    br_stuff["mtu"],
                                                                                    br_stuff["flags"],
                                                                                    br_stuff["features"],
                                                                                    logging_tools.get_plural("interface", len(br_stuff["interfaces"])),
                                                                                    ", ".join(sorted(br_stuff["interfaces"]))))
            return limits.nag_STATE_OK, "ok %s" % ("\n".join(out_f))

class network_info_command(hm_classes.hmb_command):
    def __init__(self, **args):
        hm_classes.hmb_command.__init__(self, "network_info", **args)
        self.help_str = "returns Network information"
        self.short_client_info = "-r, --raw"
        self.long_client_info = "sets raw-output (for scripts)"
        self.short_client_opts = "r"
        self.long_client_opts = ["raw"]
    def server_call(self, cm):
        network_dict = self.module_info._check_for_networks(self.logger)
        bridge_dict = self.module_info._check_for_bridges(self.logger)
        return "ok %s" % (hm_classes.sys_to_net({"net"    : network_dict,
                                                 "bridge" : bridge_dict}))
    def client_call(self, result, parsed_coms):
        lim = parsed_coms[0]
        raw_output = lim.get_add_flag("R")
        if raw_output:
            return limits.nag_STATE_OK, result[3:]
        else:
            net_dict = hm_classes.net_to_sys(result[3:])
            bridge_dict = net_dict["bridge"]
            net_dict    = net_dict["net"]
            net_names = sorted(net_dict.keys())
            out_f = []
            out_list = logging_tools.form_list()
            out_list.set_header_string(0, ["name", "bridge", "flags", "features"])
            for net_name in net_names:
                net_stuff = net_dict[net_name]
                out_list.add_line((net_name,
                                   "yes" if net_name in bridge_dict.keys() else "no",
                                   ",".join(net_stuff["flags"]),
                                   ", ".join(["%s=%s" % (key, str(net_stuff["features"][key])) for key in sorted(net_stuff["features"].keys())]) if net_stuff["features"] else "none"))
                for net in net_stuff["inet"]:
                    out_list.add_line(("  - %s" % (net)))
            return limits.nag_STATE_OK, "ok found %s:\n%s" % (logging_tools.get_plural("network device", len(net_names)),
                                                              str(out_list))
        
if __name__ == "__main__":
    print "This is a loadable module."
    sys.exit(0)
