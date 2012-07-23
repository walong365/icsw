#!/usr/bin/python-init -Otu
# -*- coding: utf-8 -*-
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008,2009,2012 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
# 
# This file is part of mother
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FTNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
""" mother daemon """

import sys
import time
import os
import os.path
import threading
import re
import zmq
import shutil
# transition fix
import configfile
import cluster_location
import socket
import stat
import process_tools
import logging_tools
import pkg_resources
pkg_resources.require("MySQL_python")
import mysql_tools
import MySQLdb
import pprint
import server_command
import uuid_tools
import cpu_database
import ipvx_tools
import threading_tools
import net_tools
import config_tools
import kernel_sync_tools
# SNMP imports
import pkg_resources
pkg_resources.require("pyasn1")
import pyasn1.codec.ber
from pysnmp.entity.rfc3413.oneliner import cmdgen
from pysnmp.carrier.asynsock import dispatch
from pysnmp.carrier.asynsock import dgram
from pysnmp.proto import rfc1902
from pysnmp.proto import api
from mother.config import global_config
from django.db.models import Q
import mother.kernel
import mother.command
import mother.control
from init.cluster.backbone.models import network

SQL_ACCESS = "cluster_full_access"

# definition of device state for
# <STATE>:<IP>:<NET>:<STRING>
# where
# ... STATE is (o)k, (w)arn or (e)rror (w)arn if status was requested but only ping found)
# ... IP is the answering IP-Adresse
# ... NET ist the recognized network
# ... STRING is a descriptive string

# --------- connection objects ------------------------------------

##class node_con_obj(net_tools.buffer_object):
##    # connects to a foreign node
##    def __init__(self, com, dst_ip, (send_str, mach_struct)):
##        self.__command = com
##        self.__dst_ip = dst_ip
##        self.__send_str = send_str
##        self.__mach_struct = mach_struct
##        net_tools.buffer_object.__init__(self)
##    def __del__(self):
##        pass
##    def setup_done(self):
##        self.add_to_out_buffer(net_tools.add_proto_1_header(self.__send_str, True))
##    def out_buffer_sent(self, send_len):
##        if send_len == len(self.out_buffer):
##            self.out_buffer = ""
##            self.socket.send_done()
##        else:
##            self.out_buffer = self.out_buffer[send_len:]
##    def add_to_in_buffer(self, what):
##        self.in_buffer += what
##        p1_ok, p1_data = net_tools.check_for_proto_1_header(self.in_buffer)
##        if p1_ok:
##            self.__command._result_ok(self.__mach_struct, self.__dst_ip, p1_data)
##            #self.__stc.set_host_result(self.__dst_ip, p1_data)
##            self.delete()
##    def report_problem(self, flag, what):
##        self.__command._result_error(self.__mach_struct, self.__dst_ip, "%s (code %d)" % (what, flag))
##        #self.__stc.set_host_error(self.__dst_ip, "%s : %s" % (net_tools.net_flag_to_str(flag), what))
##        self.delete()
##
##class new_tcp_con(net_tools.buffer_object):
##    # connection object for mother
##    def __init__(self, con_type, sock, src, recv_queue, log_queue):
##        self.__con_type = con_type
##        self.__src_host, self.__src_port = src
##        self.__recv_queue = recv_queue
##        self.__log_queue = log_queue
##        net_tools.buffer_object.__init__(self)
##        self.__init_time = time.time()
##        self.__in_buffer = ""
##    def __del__(self):
##        pass
##    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
##        self.__log_queue.put(("log", (threading.currentThread().getName(), what, level)))
##    def get_src_host(self):
##        return self.__src_host
##    def get_src_port(self):
##        return self.__src_port
##    def add_to_in_buffer(self, what):
##        self.__in_buffer += what
##        p1_ok, p1_dec = net_tools.check_for_proto_1_header(self.__in_buffer)
##        if p1_ok:
##            self.__decoded = p1_dec
##            if self.__con_type == "com":
##                self.__recv_queue.put(("in_bytes", self))
##            else:
##                self.__recv_queue.put(("node_con", self))
##    def add_to_out_buffer(self, what, new_in_str=""):
##        self.lock()
##        # to give some meaningful log
##        if new_in_str:
##            self.__decoded = new_in_str
##        if self.socket:
##            self.out_buffer = net_tools.add_proto_1_header(what)
##            self.socket.ready_to_send()
##        else:
##            self.log("timeout, other side has closed connection")
##        self.unlock()
##    def out_buffer_sent(self, d_len):
##        if d_len == len(self.out_buffer):
##            self.__recv_queue = None
##            if self.__con_type == "com":
##                self.log("command %s from %s (port %d) took %s" % (self.__decoded.replace("\n", "\\n"),
##                                                                   self.__src_host,
##                                                                   self.__src_port,
##                                                                   logging_tools.get_diff_time_str(abs(time.time() - self.__init_time))))
##            self.close()
##        else:
##            self.out_buffer = self.out_buffer[d_len:]
##            #self.socket.ready_to_send()
##    def get_decoded_in_str(self):
##        return self.__decoded
##    def report_problem(self, flag, what):
##        self.__log_queue.put(("log", (threading.currentThread().getName(), "error for connection from %s (port %d): %s (%d)" % (self.__src_host,
##                                                                                                                                self.__src_port,
##                                                                                                                                what,
##                                                                                                                                flag),
##                                      logging_tools.LOG_LEVEL_ERROR)))
##        self.close()

# --------- connection objects ------------------------------------

class all_devices(object):
    def __init__(self, log_queue, glob_config, loc_config, db_con):
        self.__lut = {}
        self.__lock = threading.Lock()
        self.__log_queue = log_queue
        self.__glob_config, self.__loc_config = (glob_config, loc_config)
        self.__db_con = db_con
        self.log("all_devices struct init")
    def get_db_con(self):
        return self.__db_con
    def get_glob_config(self):
        return self.__glob_config
    def get_loc_config(self):
        return self.__loc_config
    def get_log_queue(self):
        return self.__log_queue
    def is_an_ip(self, key):
        if key.count(".") == 3 and len([True for x in key.split(".") if x.isdigit()]):
            return True
        else:
            return False
    def db_sync(self, dc, new_names=[], new_ips=[]):
        self._lock(self.__loc_config["VERBOSE"] > 0 or not self.__loc_config["DAEMON"])
        if not new_names:
            # database settings
            self.log("Checking for bootdev->netbootdevice changes")
            dc.execute("DESCRIBE device")
            all_fields = [x["Field"] for x in dc.fetchall()]
            if "bootdev" in all_fields:
                db_ok = dc.execute("SELECT d.name, d.device_idx, n.netdevice_idx, d.bootdev, n.devname FROM device d, netdevice n, netip ip, network nw, network_type nt " + \
                                   "WHERE ip.netdevice=n.netdevice_idx AND ip.network=nw.network_idx AND n.device=d.device_idx AND d.bootserver=%d AND nt.network_type_idx=nw.network_type AND nt.identifier='b' AND NOT d.bootnetdevice" % (self.__loc_config["MOTHER_SERVER_IDX"]))
                if db_ok:
                    for sql_rec in dc.fetchall():
                        self.log(" adapting device '%s' (index %d), bootdev '%s' -> bootnetdevice %d" % (sql_rec["name"], sql_rec["device_idx"], sql_rec["devname"], sql_rec["netdevice_idx"]))
                        dc.execute("UPDATE device SET bootnetdevice=%d WHERE name='%s'" % (sql_rec["netdevice_idx"], sql_rec["name"]))
            self.log("Checking for network type changes (x->o)")
            db_ok = dc.execute("SELECT nw.name,nw.network_idx FROM network nw, network_type nt WHERE nw.network_type=nt.network_type_idx AND nt.identifier='x'")
            if db_ok:
                all_net_idx = dict([(sql_rec["network_idx"], sql_rec["name"]) for sql_rec in dc.fetchall()])
                if all_net_idx:
                    self.log("Modifying network_type of %d networks: %s" % (len(all_net_idx.keys()), ", ".join(["'%s'" % (sql_rec) for sql_rec in all_net_idx.values()])))
                    dc.execute("SELECT nt.network_type_idx FROM network_type nt WHERE nt.identifier='o'")
                    new_nt_idx = dc.fetchone()["network_type_idx"]
                    sql_str = "UPDATE network SET network_type=%d,write_bind_config=0 WHERE (%s)" % (new_nt_idx, " OR ".join(["network_idx=%d" % (sql_rec) for sql_rec in all_net_idx.keys()]))
                    dc.execute(sql_str)
                #log_queue.
            self.log("Checking for netdevice.alias->netip.alias changes")
            dc.execute("DESCRIBE netdevice")
            all_fields = [x["Field"] for x in dc.fetchall()]
            if "alias" in all_fields:
                dc.execute("SELECT n.netdevice_idx,n.alias,i.netip_idx,i.alias AS netip_alias FROM netdevice n LEFT JOIN netip i ON i.netdevice=n.netdevice_idx ORDER BY n.netdevice_idx")
                for sql_rec in dc.fetchall():
                    if sql_rec["alias"] and not sql_rec["netip_alias"] and sql_rec["netip_idx"]:
                        if sql_rec["alias"] == "localhost":
                            dc.execute("UPDATE netip SET alias=%s,alias_excl=1 WHERE netip_idx=%s", (sql_rec["alias"], sql_rec["netip_idx"]))
                        else:
                            dc.execute("UPDATE netip SET alias=%s WHERE netip_idx=%s", (sql_rec["alias"], sql_rec["netip_idx"]))
            # check for missing network_device_type_indices
            if self.__loc_config["GLOBAL_NET_DEVICE_DICT"]:
                dc.execute("SELECT n.netdevice_idx,n.devname,n.network_device_type FROM netdevice n")
                for sql_rec in dc.fetchall():
                    all_ndt_idxs = [self.__loc_config["GLOBAL_NET_DEVICE_DICT"][y] for y in self.__loc_config["GLOBAL_NET_DEVICE_DICT"].keys() if sql_rec["devname"].startswith(y)]
                    if all_ndt_idxs:
                        new_ndt_idx = all_ndt_idxs[0]
                        if new_ndt_idx != sql_rec["network_device_type"]:
                            dc.execute("UPDATE netdevice SET network_device_type=%d WHERE netdevice_idx=%d" % (new_ndt_idx, sql_rec["netdevice_idx"]))
                    else:
                        self.log("not network_device_type found", logging_tools.LOG_LEVEL_ERROR)
        if new_names:
            sql_add_str = "AND (%s)" % (" OR ".join(["d.name='%s'" % (x) for x in new_names]))
        elif new_ips:
            sql_add_str = "AND (%s)" % (" OR ".join(["ip.ip='%s'" % (x) for x in new_ips]))
        else:
            sql_add_str = ""
        sql_str = "SELECT d.name, d.device_mode, d.device_idx, dt.identifier, d.recvstate, d.reqstate FROM device d, device_type dt WHERE dt.device_type_idx=d.device_type AND d.bootserver=%d %s ORDER BY d.name" % (self.__loc_config["MOTHER_SERVER_IDX"], sql_add_str)
        dc.execute(sql_str)
        for mach in dc.fetchall():
            name = mach["name"]
            if not self.__lut.has_key(name):
                if mach["identifier"] == "H":
                    newmach = machine(name, mach["device_idx"], dc, self)
                    newmach.set_recv_req_state(mach["recvstate"], mach["reqstate"])
                    newmach.set_device_mode(mach["device_mode"])
                elif mach["identifier"] == "S":
                    newmach = switch(name, mach["device_idx"], dc, self)
                    newmach.set_recv_req_state(mach["recvstate"], mach["reqstate"])
                elif mach["identifier"] == "AM":
                    napc = apc(name, mach["device_idx"], dc, self)
                    napc.set_recv_req_state(mach["recvstate"], mach["reqstate"])
                elif mach["identifier"] == "IBC":
                    napc = ibc(name, mach["device_idx"], dc, self)
                    napc.set_recv_req_state(mach["recvstate"], mach["reqstate"])
            else:
                self.log("Device %s already in internal dictionaries, checking network settings ..." % (name))
                self.__lut[name].check_network_settings(dc)
        self._release(self.__loc_config["VERBOSE"] > 0 or not self.__loc_config["DAEMON"])
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__log_queue.put(("log", (threading.currentThread().getName(), what, lev)))
    def _lock(self, verb):
        if verb:
            self.log("Acquiring lock for ad_struct")
        self.__lock.acquire()
    def _release(self, verb):
        if verb:
            self.log("Releasing lock for ad_struct")
        self.__lock.release()
    def keys(self):
        return self.__lut.keys()
    def has_key(self, key):
        return self.__lut.has_key(key)
    def __setitem__(self, key, val):
        self.__lut[key] = val
    def __getitem__(self, key):
        return self.__lut[key]
    def __delitem__(self, key):
        if self.__lut.has_key(key):
            del self.__lut[key]
        else:
            self.log("no key '%s' found in lut" % (key),
                     logging_tools.LOG_LEVEL_ERROR)
    def iteritems(self):
        return od_iteritems_iterator(self)
        
class od_iteritems_iterator(object):
    def __init__(self, od):
        self.__od = od
        self.__kl = self.__od.keys()
    def __iter__(self):
        self.__index = 0
        return self
    def next(self):
        if self.__index == len(self.__kl):
            raise StopIteration
        act_key = self.__kl[self.__index]
        self.__index += 1
        return act_key, self.__od[act_key]
    def __repr__(self):
        return "{%s}" % (", ".join(["'%s' : %s" % (k, v) for k, v in self.__iter__()]))
        
class machine(object):
    #def __init__(self, name, idx, ips={}, log_queue=None):
    def __init__(self, name, idx, dc, ad_struct):
        # set dicts
        self.__glob_config, self.__loc_config = (ad_struct.get_glob_config(),
                                                 ad_struct.get_loc_config())
        self.__ad_struct = ad_struct
        # machine name
        self.name = name
        # set log_queue
        self.set_log_queue(ad_struct.get_log_queue())
        # clear reachable flag
        self.set_reachable_flag(False)
        # init locking structure
        self.init_lock()
        # machine idx
        self.device_idx = idx
        # init device_mode
        self.set_device_mode()
        # add to global devname_dict
        if not ad_struct.has_key(self.name):
            ad_struct[self.name] = self
            self.log("Added myself (%s) to ad_struct" % (self.name))
        # ip dictionary; ip->networktype
        self.ip_dict = {}
        #self.set_ip_dict(ips)
        # actual net [(P)roduction, (M)aintenance, (T)est or (O)ther] / IP-address
        self.__act_net, self.__act_ip = ("?", "?")
        # usefull initial values
        self.__last_ip_set, self.__last_ip_ok_set = (time.time() - self.__glob_config["DEVICE_MONITOR_TIME"],
                                                     time.time() + self.__glob_config["DEVICE_REBOOT_TIME"])
        # boot netdevice, driver for boot netdevice and options
        self.bootnetdevice_name, self.boot_netdriver, self.ethtool_options, self.boot_netdriver_options = (None, None, 0, "")
        # maintenance ip address (and hex) (also sets the node-flag)
        self.set_maint_ip()
        # init hwi delay_counter
        self.clear_hwi_delay_counter()
        self.set_use_count()
        self.check_network_settings(dc)
        self.set_recv_req_state()
        self.set_last_reset_time()
    def get_db_con(self):
        return self.__ad_struct.get_db_con()
    def set_device_mode(self, dm=0):
        self.__device_mode = dm
        self.log("Setting device_mode to %s and updating ip_ok_time" % {0 : "no check",
                                                                        1 : "auto reboot (sw)",
                                                                        2 : "auto reboot (hw)"}[self.__device_mode])
        self.__last_ip_ok_set = time.time()
    def get_community_strings(self, dc):
        dc.execute("SELECT s.* FROM snmp_class s, device d WHERE s.snmp_class_idx=d.snmp_class AND d.device_idx=%d" % (self.device_idx))
        if dc.rowcount:
            db_rec = dc.fetchone()
        else:
            db_rec = {"read_community"  : "public",
                      "write_community" : "private"}
        # FIXME, hack for buggy db
        if db_rec["write_community"] == "write" and db_rec["read_community"] == "public":
            db_rec["write_community"] = "private"
        return {"read_community"  : db_rec["read_community"],
                "write_community" : db_rec["write_community"]}
    def get_device_mode(self):
        return self.__device_mode
    def set_reachable_flag(self, reachable):
        self.__reachable = reachable
    def get_reachable_flag(self):
        return self.__reachable
    def get_name(self):
        return self.name
    def set_use_count(self, val=0):
        self.use_count = val
        if self.__loc_config["VERBOSE"]:
            self.log("Setting use_count to %d" % (self.use_count))
    def incr_use_count(self, why, incr=1):
        self.use_count += incr
        if self.__loc_config["VERBOSE"]:
            self.log("incrementing use_count to %d (%s)" % (self.use_count, why))
    def decr_use_count(self, why, decr=1):
        self.use_count -= decr
        if self.__loc_config["VERBOSE"]:
            self.log("decrementing use_count to %d (%s)" % (self.use_count, why))
    def get_use_count(self):
        return self.use_count
    def device_log_entry(self, user, status, what, sql_queue, log_src_idx):
        sql_str, sql_tuple = mysql_tools.get_device_log_entry_part(self.device_idx, log_src_idx, user, self.__loc_config["LOG_STATUS"][status]["log_status_idx"], what)
        sql_queue.put(("insert_value", ("devicelog", sql_str, sql_tuple)))
    def parse_received_str(self, in_str, dc, sql_queue, node_idx):
        self.device_log_entry(0, "i", in_str, sql_queue, node_idx)
        if in_str.startswith("got kernel"):
            kern_name = in_str.split()[2]
            dc.execute("SELECT k.kernel_idx FROM kernel k WHERE k.name=%s", kern_name)
            upd_list = []
            if dc.rowcount:
                kern_idx = dc.fetchone()["kernel_idx"]
                upd_list.extend([("act_kernel", kern_idx),
                                 ("actkernel", kern_name)])
                kb_idx = 0
                try:
                    kern_ver, kern_rel = in_str.split()[3].split(".")
                    kern_ver, kern_rel = (int(kern_ver[1:]),
                                          int(kern_rel[:-1]))
                except:
                    k_m = re.match("\(.* version (?P<version>\S+), release (?P<release>\S+)\)", in_str)
                    if k_m:
                        kern_ver = k_m.group("version")
                        kern_rel = k_m.group("release")
                    else:
                        kern_ver, kern_rel = (None, None)
                try:
                    kern_ver, kern_rel = (int(kern_ver), int(kern_rel))
                except:
                    dc.execute("SELECT kernel_build_idx, version, `release` FROM kernel_build WHERE kernel=18 ORDER BY date DESC LIMIT 1")
                    if dc.rowcount:
                        kb_stuff = dc.fetchone()
                        kb_idx, kern_ver, kern_rel = (kb_stuff["kernel_build_idx"],
                                                      kb_stuff["version"],
                                                      kb_stuff["release"])
                                                               
                else:
                    dc.execute("SELECT kernel_build_idx FROM kernel_build WHERE kernel=%d AND version=%d and `release`=%d" % (kern_idx,
                                                                                                                              kern_ver,
                                                                                                                              kern_rel))
                    if dc.rowcount:
                        kb_idx = dc.fetchone()["kernel_build_idx"]
                if kb_idx:
                    upd_list.extend([("kernelversion", "%d.%d" % (kern_ver, kern_rel)),
                                     ("act_kernel_build", "%d" % (kb_idx))])
            if upd_list:
                sql_queue.put(("update", ("device", "%s WHERE name=%%s" % (", ".join(["%s=%%s" % (x) for x, y in upd_list])),
                                          tuple([y for x, y in upd_list] + [self.name]))))
    def clear_hwi_delay_counter(self):
        self.hwi_delay_counter = 0
    def incr_hwi_delay_counter(self):
        self.hwi_delay_counter += 1
    def get_hwi_delay_counter(self):
        return self.hwi_delay_counter
    def set_log_queue(self, log_queue):
        self.log_queue = log_queue
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK, glob=0):
        if self.log_queue:
            if glob == 0 or glob == 2:
                self.log_queue.put(("mach_log", (threading.currentThread().getName(), what, lev, self.name)))
            if glob > 0:
                self.log_queue.put(("log", (threading.currentThread().getName(), what, lev)))
        else:
            print "Log for machine %s: %s" % (self.name, what)
    def set_lock(self, why):
        # locks are mapped to lock-classes (for instance, a device can be locked by a refresh_hwi-lock AND a status-lock
        lock_class = self.lock_mapping.get(why, "general")
        self.lock[lock_class] = why
        if self.__loc_config["VERBOSE"]:
            self.log("Setting lock to %s (class %s)" % (str(why), lock_class))
        self.incr_use_count("lock %s" % (why))
    def init_lock(self):
        self.lock_mapping = {"refresh_hwi"        : "hwi_lock",
                             "fetch_network_info" : "hwi_lock",
                             "resync_config"      : "net_lock",
                             "restart_network"    : "net_lock",
                             "readdots"           : "readfile_lock",
                             "apc_com"            : "apc_lock",
                             "apc_dev"            : "apc_lock",
                             "apc_dev2"           : "apc_lock"}
        if self.__loc_config["VERBOSE"]:
            self.log("Init locking-structure")
        self.lock = {"general" : None}
        for lock_val in self.lock_mapping.values():
            self.lock.setdefault(lock_val, None)
    def get_lock(self, why):
        lock_class = self.lock_mapping.get(why, "general")
        return self.lock[lock_class]
    def release_lock(self, why):
        lock_class = self.lock_mapping.get(why, "general")
        if self.lock.has_key(lock_class):
            if not self.lock[lock_class]:
                self.log("lock-class %s (%s) already released" % (lock_class, str(why)),
                         logging_tools.LOG_LEVEL_ERROR)
            else:
                self.lock[lock_class] = None
                if self.__loc_config["VERBOSE"]:
                    self.log("Releasing lock (%s, lock_class %s)" % (str(why), lock_class))
        else:
            self.log("trying to release nonexistent lock-class %s (%s)" % (lock_class, str(why)),
                     logging_tools.LOG_LEVEL_ERROR)
        self.decr_use_count("lock %s" % (why))
    def check_network_settings(self, dc):
        sql_str = "SELECT d.bootnetdevice, d.bootserver, d.reachable_via_bootserver, nd.macadr, nd.devname, nd.ethtool_options, nd.driver, nd.driver_options, ip.ip, ip.network, nt.identifier, nw.postfix, nw.identifier as netident, nw.network_type, nd.netdevice_idx FROM " + \
                  "device d, netip ip, netdevice nd, network nw, network_type nt WHERE " + \
                  "ip.netdevice=nd.netdevice_idx AND nd.device=d.device_idx AND ip.network=nw.network_idx AND nw.network_type=nt.network_type_idx AND nt.identifier != 's' AND d.name='%s' AND d.bootserver=%d ORDER BY nd.devname,ip.ip" % (self.name, self.__loc_config["MOTHER_SERVER_IDX"])
        dc.execute(sql_str)
        net_dict = {}
        bootnetdevice, bootnetdevice_name = (None, None)
        dev_upd_stuff = []
        loc_ip_dict = {}
        dev_updated = False
        for net_rec in dc.fetchall():
            self.set_reachable_flag(net_rec["reachable_via_bootserver"] and True or False)
            if net_rec["bootnetdevice"] == net_rec["netdevice_idx"]:
                bootnetdevice, bootnetdevice_name = (net_rec["bootnetdevice"], net_rec["devname"].split(":", 1)[0])
            #print "bs for %s : %d" % (self.name, net_rec["bootserver"]), loc_config["MOTHER_SERVER_IDX"]
            net_dict.setdefault(net_rec["netdevice_idx"], {"devname"         : net_rec["devname"],
                                                           "driver"          : net_rec["driver"],
                                                           "driver_options"  : net_rec["driver_options"],
                                                           "ethtool_options" : net_rec["ethtool_options"],
                                                           "netdevice_idx"   : net_rec["netdevice_idx"],
                                                           "ipl"             : {}})["ipl"].setdefault(net_rec["ip"], [net_rec["ip"], net_rec["macadr"], net_rec["network"], net_rec["identifier"], net_rec["netident"], net_rec["postfix"]])
        if net_dict:
            netok_list = []
            src_str_s = " OR ".join(["h.s_netdevice=%d" % (x) for x in self.__loc_config["GLOBAL_NET_DEVICES"].keys()])
            dev_str_d = " OR ".join(["h.d_netdevice=%d" % (x) for x in net_dict.keys()])
            dc.execute("SELECT h.s_netdevice, h.d_netdevice FROM hopcount h WHERE (%s) AND (%s) ORDER BY h.value" % (src_str_s, dev_str_d))
            # reverse-dictionary to own netdevices
            rev_dict = {}
            for hc in dc.fetchall():
                net_idx, my_idx = (hc["d_netdevice"], hc["s_netdevice"])
                rev_dict.setdefault(net_idx, []).append(my_idx)
                if net_dict.has_key(net_idx):
                    netok_list.append(net_idx)
            if netok_list:
                link_array = []#("d", "%s/%s" % (g_config["SYSLOG_DIR"], self.name))]
                server_ip_dict = {}
                maint_ip, maint_mac = (None, None)
                for ndev_idx in netok_list:
                    server_ips = []
                    for server_ip in [self.__loc_config["GLOBAL_NET_DEVICES"][x] for x in rev_dict[ndev_idx]]:
                        server_ips += server_ip
                    net_stuff = net_dict[ndev_idx]
                    for ip, mac, net_idx, nt_ident, nw_ident, nw_postfix in net_stuff["ipl"].values():
                        # get corresponding server_ips
                        server_ips = [x for x in server_ips if x[1] == net_idx]
                        if server_ips:
                            server_ip_dict[ip] = server_ips[0][0]
                        else:
                            server_ip_dict[ip] = None
                        # set network identifier
                        loc_ip_dict[ip] = nw_ident
                        if nt_ident == "b" and net_stuff["netdevice_idx"] == bootnetdevice:
                            maint_ip, maint_mac = (ip, mac)
                            driver, driver_ethtool_options, driver_options = (net_stuff["driver"], net_stuff["ethtool_options"], net_stuff["driver_options"])
                        #if nw_postfix:
                        #    link_array.append(("l", "%s/%s%s" % (g_config["SYSLOG_DIR"], self.name, nw_postfix)))
                #print net_dict
                self.log("Found %s : %s" % (logging_tools.get_plural("ip-address", len(loc_ip_dict.keys())), ", ".join(loc_ip_dict.keys())))
                # change maint_ip
                self.set_maint_ip(maint_ip, maint_mac)
                if self.get_etherboot_dir():
                    link_array.extend([("d", self.get_etherboot_dir()),
                                       ("d", self.get_pxelinux_dir()),
                                       ("l", ("%s/%s" % (self.__glob_config["ETHERBOOT_DIR"], self.name), self.maint_ip))])
                    dev_upd_stuff.append("etherboot_valid=1")
                    dc.execute("UPDATE device SET etherboot_valid=1 WHERE name='%s'" % (self.name))
                else:
                    self.log("Error: etherboot-directory (maint_ip) not defined")
                    dev_upd_stuff.append("etherboot_valid=0")
                # set bootnetdevice
                self.set_bootnetdevice_name(bootnetdevice_name)
                if maint_ip:
                    self.set_boot_netdriver(driver, driver_ethtool_options, driver_options)
                self.process_link_array(link_array)
                self.set_ip_dict(loc_ip_dict)
                # set server_reverse_ip dict
                self.set_server_ip_dict(server_ip_dict)
                if not self.get_reachable_flag():
                    self.set_reachable_flag(True)
                    self.log("Setting reachable flag")
                    dev_upd_stuff.append("reachable_via_bootserver=1")
                dev_updated = True
            else:
                self.log("Cannot add device %s (empty ip_list -> cannot reach host)" % (self.name),
                         logging_tools.LOG_LEVEL_WARN)
        else:
            self.log("refuse to add device without netdevices")
        if not dev_updated:
            self.set_maint_ip(None, None)
            if self.get_reachable_flag():
                self.set_reachable_flag(False)
                self.log("Clearing reachable flag")
                dev_upd_stuff.append("reachable_via_bootserver=0")
            self.set_ip_dict(loc_ip_dict)
        if dev_upd_stuff:
            dc.execute("UPDATE device SET %s WHERE name='%s'" % (", ".join(dev_upd_stuff), self.name))
        self.log("actual settings: %s" % (self.get_reachable_flag() and "reachable" or "not reachable"))
        # check for deleting of old ip-dicts
    def set_ip_dict(self, ips):
        for act_key in self.ip_dict.keys():
            if not ips.has_key(act_key):
                self.log("Removing IP %s from IP-dictionary" % (act_key))
                del self.__ad_struct[act_key]
        for act_key in ips.keys():
            if not self.ip_dict.has_key(act_key):
                self.log("Adding ip %s to IP-dictionary" % (act_key))
                self.__ad_struct[act_key] = self
        self.ip_dict = ips
    def get_server_ip_addr(self, own_ip):
        return self.server_ip_dict.get(own_ip, None)
    def set_server_ip_dict(self, sip_dict):
        self.log("Found %s:" % (logging_tools.get_plural("valid device->server ip-mapping", len(sip_dict.keys()))))
        for my_ip, s_ip in sip_dict.iteritems():
            self.log("  %s -> %s" % (my_ip, s_ip))
        self.server_ip_dict = sip_dict
    def process_link_array(self, l_array):
        for pt, ps in l_array:
            if pt == "d":
                if not os.path.isdir(ps):
                    try:
                        self.log("pla(): Creating directory %s" % (ps))
                        os.mkdir(ps)
                    except:
                        self.log("  ...something went wrong for mkdir(): %s" % (process_tools.get_except_info()))
            elif pt == "l":
                if type(ps) == type(""):
                    dest = self.name
                else:
                    ps, dest = ps
                create_link = False
                if not os.path.islink(ps):
                    create_link = True
                else:
                    if os.path.exists(ps):
                        old_dest = os.readlink(ps)
                        if old_dest != dest:
                            try:
                                os.unlink(ps)
                            except OSError:
                                self.log("  ...something went wrong for unlink(): %s" % (process_tools.get_except_info()))
                            else:
                                self.log(" removed wrong link (%s pointed to %s instead of %s)" % (ps, old_dest, dest))
                                create_link = True
                    else:
                        pass
                if create_link:
                    if os.path.exists(ps):
                        try:
                            self.log("pla(): Unlink %s" % (ps))
                            os.unlink(ps)
                        except:
                            self.log("  ...something went wrong for unlink(): %s" % (process_tools.get_except_info()))
                        try:
                            self.log("pla(): rmtree %s" % (ps))
                            shutil.rmtree(ps, 1)
                        except:
                            self.log("  ...something went wrong for rmtree(): %s" % (process_tools.get_except_info()))
                    try:
                        self.log("pla(): symlink from %s to %s" % (ps, dest))
                        os.symlink(dest, ps)
                    except:
                        self.log("  ...something went wrong for symlink(): %s" % (process_tools.get_except_info()))
    def set_bootnetdevice_name(self, bdev=None):
        if self.bootnetdevice_name != bdev:
            self.log("Changing bootnetdevice_name from '%s' to '%s'" % (self.bootnetdevice_name, bdev))
            self.bootnetdevice_name = bdev
    def set_maint_ip(self, ip=None, mac=None):
        if ip:
            hex_ip = "".join(["%02X" % (int(x)) for x in ip.split(".")])
            if self.maint_ip != ip or self.maint_mac != mac:
                self.log("Changing maintenance IP and MAC from %s (%s) [%s] to %s (%s) [%s] and setting node-flag" % (self.maint_ip, self.maint_ip_hex, self.maint_mac, ip, hex_ip, mac))
                self.node = True
                self.maint_ip = ip
                self.maint_ip_hex = hex_ip
                self.maint_mac = mac
        else:
            self.log("Clearing maintenance IP and MAC (and node-flag)")
            self.maint_ip = None
            self.maint_ip_hex = None
            self.maint_mac = None
            self.node = False
    def set_boot_netdriver(self, driver="eepro100", ethtool_options=0, options=""):
        if driver != self.boot_netdriver or ethtool_options != self.ethtool_options or options != self.boot_netdriver_options:
            self.log("Changing boot_netdriver/ethtool_options/netdriver_options from '%s / %d / %s' to '%s / %d / %s'" % (str(self.boot_netdriver), self.ethtool_options, str(self.boot_netdriver_options), str(driver), ethtool_options, str(options)))
        self.boot_netdriver = driver
        self.ethtool_options = ethtool_options
        self.boot_netdriver_options = options
    def set_req_state(self, what, sql_queue):
        self.req_state = what
        sql_queue.put(("update", ("device", "reqstate=%s WHERE name=%s", (what.strip(), self.name))))
    def set_recv_state(self, what, sql_queue):
        self.recv_state = what
        sql_queue.put(("update", ("device", "recvstate=%s WHERE name=%s", (what.strip(), self.name))))
    def get_recv_req_state(self):
        return self.recv_state, self.req_state
    def set_recv_req_state(self, recv_state = "error not set", req_state="error not set"):
        self.recv_state, self.req_state = (recv_state, req_state)
    def get_act_net(self):
        return self.__act_net
    def get_act_ip(self):
        return self.__act_ip
    def get_last_ip_set(self):
        return self.__last_ip_set
    def get_last_ip_ok_set(self):
        return self.__last_ip_ok_set
    def get_last_reset_time(self):
        return self.__last_reset_time
    def set_last_reset_time(self):
        self.__last_reset_time = time.time()
    def set_actual_ip(self, ip=None):
        self.__last_ip_set = time.time()
        if ip:
            self.__last_ip_ok_set = time.time()
            self.__act_ip = ip
            if self.ip_dict.has_key(self.__act_ip):
                self.__act_net = self.ip_dict[self.__act_ip]
                log_str = "Setting network properties to defined ip %s (network: %s)" % (self.__act_ip, self.__act_net)
            else:
                ik = self.__act_ip
                self.__act_ip, self.__act_net = ("?", "?")
                log_str = "Setting network properties to undefined ip %s (network: %s) because of illegal key %s" % (self.__act_ip, self.__act_net, ik)
        else:
            self.__act_ip, self.__act_net = ("?", "?")
            log_str = "Setting network properties to undefined ip %s (network: %s)" % (self.__act_ip, self.__act_net)
        #self.log(log_str)
    def clear_hardware_info(self, dc):
        self.log("Clearing hardware-info ...")
        # do not clear cpu_info automatically
        #dc.execute("UPDATE device SET cpu_info='' WHERE device_idx=%s", self.device_idx)
        # clear hw_entry
        for table, del_field in [("pci_entry", "device_idx"), ("hw_entry", "device")]:
            sql_str = "DELETE FROM %s WHERE %s=%d" % (table, del_field, self.device_idx)
            try:
                dc.execute(sql_str)
            except:
                self.log("  Error clearing data from table %s" % (table))
        # clear dmi-entries
        sql_str = "SELECT de.dmi_entry_idx, dk.dmi_key_idx, dek.dmi_ext_key_idx FROM dmi_entry de LEFT JOIN dmi_key dk ON de.dmi_entry_idx=dk.dmi_entry LEFT JOIN dmi_ext_key dek ON dk.dmi_key_idx=dek.dmi_key WHERE de.device=%d" % (self.device_idx)
        dc.execute(sql_str)
        del_keys = dict([(key, set()) for key in ["dmi_entry", "dmi_key", "dmi_ext_key"]])
        for db_rec in dc.fetchall():
            for dk, dk_s in del_keys.iteritems():
                if db_rec["%s_idx" % (dk)]:
                    dk_s.add(db_rec["%s_idx" % (dk)])
        for dk, keys in del_keys.iteritems():
            if keys:
                self.log("removing %s" % (logging_tools.get_plural("%s key" % (dk), len(keys))))
                dc.execute("DELETE FROM %s WHERE %s" % (dk, " OR ".join(["%s_idx=%d" % (dk, idx) for idx in keys])))
    def _add_netdevice(self, dc, set_dict):
        set_dict["device"] = self.device_idx
        dc.execute("INSERT INTO netdevice SET %s" % (", ".join(["%s=%%s" % (key) for key in sorted(set_dict.keys())])),
                   tuple([set_dict[key] for key in sorted(set_dict.keys())]))
        act_nd_idx = dc.insert_id()
        dc.execute("SELECT * FROM netdevice WHERE netdevice_idx=%d" % (act_nd_idx))
        nd_dict = dc.fetchone()
        nd_dict["ips"] = []
        return act_nd_idx, nd_dict
    def insert_network_info(self, dc, ret_str, sql_queue):
        loc_error = False
        self.log("Saving network-info from string with len %d (first 3 Bytes: '%s')" % (len(ret_str), ret_str[0:min(3, len(ret_str))]))
        if ret_str.startswith("ok"):
            net_dict = server_command.net_to_sys(ret_str[3:])
            # known netdevice_types
            dc.execute("SELECT * FROM network_device_type")
            all_nd_types = dict([(db_rec["network_device_type_idx"], db_rec) for db_rec in dc.fetchall()])
            # known netdevice speeds
            dc.execute("SELECT * FROM netdevice_speed")
            all_nd_speeds = dict([(db_rec["netdevice_speed_idx"], db_rec) for db_rec in dc.fetchall()])
            # known networks
            dc.execute("SELECT * FROM network")
            all_networks = dict([(db_rec["network_idx"], db_rec) for db_rec in dc.fetchall()])
            # get old networks
            dc.execute("SELECT n.*, i.ip FROM netdevice n LEFT JOIN netip i ON i.netdevice=n.netdevice_idx WHERE n.device=%d" % (self.device_idx))
            act_ndict = {}
            for db_rec in dc.fetchall():
                if not act_ndict.has_key(db_rec["devname"]):
                    db_rec["ips"] = []
                    act_ndict[db_rec["devname"]] = db_rec
                if db_rec["ip"]:
                    act_ndict[db_rec["devname"]]["ips"].append(db_rec["ip"])
            present_devs = dict([(db_rec["devname"], db_rec) for db_rec in dc.fetchall()])
            num_dict = dict([(key, 0) for key in ["netdev_added",
                                                  "netdev_refreshed",
                                                  "ip_added",
                                                  "peers_added",
                                                  "no_network_found"]])
            for net_name in sorted(net_dict["net"].iterkeys()):
                net_stuff = net_dict["net"][net_name]
                is_bridge = net_name in net_dict["bridge"].keys()
                is_loopback = net_name in ["lo"]
                if is_bridge or [True for check_name in ["eth", "lo"] if net_name.startswith(check_name)]:
                    # check for network device type
                    found_ids = [key for key, value in all_nd_types.iteritems() if net_name.startswith(value["identifier"])]
                    if found_ids:
                        act_nd_type = found_ids[0]
                    else:
                        new_descr = "netdevice %s from %s" % (net_name,
                                                              self.name)
                        net_type_name = net_name
                        while net_type_name[-1].isdigit():
                            net_type_name = net_type_name[:-1]
                        br_stuff = net_dict["bridge"][net_name]
                        mac_bytes = len(br_stuff["address"].replace(":", "")) / 2
                        dc.execute("INSERT INTO network_device_type SET identifier=%s, description=%s, mac_bytes=%s", (net_type_name,
                                                                                                                       new_descr,
                                                                                                                       mac_bytes))
                        act_nd_type = dc.insert_id()
                        all_nd_types[act_nd_type] = {"network_device_type_idx" : dc.insert_id(),
                                                     "identifier"              : net_type_name,
                                                     "description"             : new_descr}
                    info_str = "netdevice %s (%s), type is %s" % (net_name,
                                                                  "bridge" if is_bridge else "no bridge",
                                                                  all_nd_types[act_nd_type]["description"])
                    # dict for netdevice
                    set_dict = {}
                    # check macadr
                    if net_stuff.get("links", {}).has_key("ether"):
                        set_dict["macadr"] = net_stuff["links"]["ether"][0].split()[0]
                    if net_name in act_ndict.keys():
                        nd_dict = act_ndict[net_name]
                        act_nd_idx = nd_dict["netdevice_idx"]
                        self.log("refreshing %s" % (info_str))
                        if set_dict:
                            dc.execute("UPDATE netdevice SET %s WHERE netdevice_idx=%d" % (", ".join(["%s=%%s" % (key) for key in sorted(set_dict.keys())]),
                                                                                           act_nd_idx),
                                       tuple([set_dict[key] for key in sorted(set_dict.keys())]))
                            num_dict["netdev_refreshed"] += 1
                    else:
                        set_dict["devname"] = net_name
                        set_dict["penalty"] = 1
                        set_dict["network_device_type"] = act_nd_type
                        set_dict["netdevice_speed"] = all_nd_speeds.keys()[0]
                        if is_bridge:
                            set_dict["is_bridge"] = 1
                            set_dict["routing"] = 1
                        act_nd_idx, nd_dict = self._add_netdevice(dc, set_dict)
                        num_dict["netdev_added"] += 1
                        act_ndict[net_name] = nd_dict
                        self.log("adding new %s" % (info_str))
                        if is_loopback:
                            self.log("  - adding peer_information for loopback device")
                            dc.execute("INSERT INTO peer_information SET s_netdevice=%d, d_netdevice=%d, penalty=1" % (act_nd_idx,
                                                                                                                       act_nd_idx))
                            num_dict["peers_added"] += 1
                    #print net_name, net_stuff
                    for new_ip in net_stuff["inet"]:
                        ip_addr, net_bits = new_ip.split()[0].split("/")
                        netdev_name = new_ip.split()[-1]
                        if nd_dict["devname"] != netdev_name:
                            if act_ndict.has_key(netdev_name):
                                nd_dict = act_ndict[netdev_name]
                                act_nd_idx = nd_dict["netdevice_idx"]
                            else:
                                act_nd_idx, nd_dict = self._add_netdevice(dc, {"devname"             : netdev_name,
                                                                               "penalty"             : 1,
                                                                               "network_device_type" : act_nd_type,
                                                                               "netdevice_speed"     : all_nd_speeds.keys()[0]})
                                num_dict["netdev_added"] += 1
                                act_ndict[net_name] = nd_dict
                                self.log("adding new (possibly virtual) netdevice %s" % (nd_dict["devname"]))
                        if ip_addr not in nd_dict["ips"]:
                            ipv4 = ipvx_tools.ipv4(ip_addr)
                            network_idx = ipv4.find_matching_network(all_networks)
                            if network_idx:
                                num_dict["ip_added"] += 1
                                ip_set_dict = {"netdevice" : act_nd_idx,
                                               "ip"        : ip_addr,
                                               "penalty"   : 1,
                                               "network"   : network_idx}
                                #"network"   : }
                                if is_loopback:
                                    ip_set_dict["alias"]      = "localhost"
                                    ip_set_dict["alias_excl"] = 1
                                dc.execute("INSERT INTO netip SET %s" % (", ".join(["%s=%%s" % (key) for key in sorted(ip_set_dict.keys())])),
                                           tuple([ip_set_dict[key] for key in sorted(ip_set_dict.keys())]))
                                self.log(" - added netip %s" % (ip_set_dict["ip"]))
                            else:
                                self.log("find no matching network for ip %s" % (ip_addr),
                                         logging_tools.LOG_LEVEL_ERROR)
                                num_dict["no_network_found"] += 1
            if num_dict["no_network_found"]:
                ret_state = "warn"
            else:
                ret_state = "ok"
            ret_str = "%s got network_info (%s)" % (ret_state,
                                                    ", ".join(["%d %s" % (value, key) for key, value in num_dict.iteritems() if value]) if sum(num_dict.values()) else "nothing done")
        else:
            loc_error, ret_str = (True, "error return string does not start with ok")
        return loc_error, ret_str
    def insert_hardware_info(self, dc, ret_str, sql_queue):
        macs_changed = 0
        self.clear_hardware_info(dc)
        self.log("Saving hardware-info from string with len %d (first 3 Bytes: '%s')" % (len(ret_str), ret_str[0:min(3, len(ret_str))]))
        if ret_str.startswith("ok"):
            ret_f = []
            try:
                hwi_res = server_command.net_to_sys(ret_str[3:])
            except:
                loc_error, ret_str = (True , "unpacking dictionary")
            else:
                loc_error, ret_str = (False, "update successful")
                num_pci, num_hw = (0, 0)
                if hwi_res.has_key("pci"):
                    pci_dict = server_command.net_to_sys(hwi_res["pci"][3:])
                    num_d = 0
                    first_d = pci_dict
                    while type(first_d) == type({}):
                        if first_d:
                            num_d += 1
                            first_d = first_d.values()[0]
                        else:
                            break
                    if num_d == 4:
                        pci_dict = {int("0000", 16) : pci_dict}
                    for domain in pci_dict.keys():
                        for bus in pci_dict[domain].keys():
                            for slot in pci_dict[domain][bus].keys():
                                for func in pci_dict[domain][bus][slot].keys():
                                    act_s = pci_dict[domain][bus][slot][func]
                                    sql_parts = [("device_idx", self.device_idx),
                                                 ("domain"    , domain),
                                                 ("bus"       , bus),
                                                 ("slot"      , slot),
                                                 ("func"      , func)]
                                    for key in [x for x in act_s.keys() if x not in [y[0] for y in sql_parts]]:
                                        sql_parts.append((key, act_s[key]))
                                    sql_queue.put(("insert_set", ("pci_entry", ", ".join(["%s=%%s" % (x[0]) for x in sql_parts]), tuple([x[1] for x in sql_parts]))))
                                    num_pci += 1
                    ret_f.append(logging_tools.get_plural("pci entry", num_pci))
                    try:
                        hw_dict = server_command.net_to_sys(hwi_res["mach"][3:])
                    except:
                        self.log("  error unpickling mach-dict ")
                        hw_dict = {}
                    else:
                        pass
                    if hwi_res.has_key("dmi"):
                        if hwi_res["dmi"].startswith("ok "):
                            added_dict = dict([(key, 0) for key in ["entry", "key", "ext_key"]])
                            # decode dmi-info
                            dmi_dict = server_command.net_to_sys(hwi_res["dmi"][3:])
                            for handle in sorted(dmi_dict["handles"]):
                                dc.execute("INSERT INTO dmi_entry SET device=%s, dmi_type=%s, handle=%s, dmi_length=%s, info=%s", (self.device_idx,
                                                                                                                                   handle["dmi_type"],
                                                                                                                                   handle["handle"],
                                                                                                                                   handle["length"],
                                                                                                                                   handle["info"]))
                                added_dict["entry"] += 1
                                dmi_entry_idx = dc.insert_id()
                                for key, value in handle["content"].iteritems():
                                    added_dict["key"] += 1
                                    if type(value) == type([]):
                                        dc.execute("INSERT INTO dmi_key SET dmi_entry=%s, key_string=%s, value_string=''", (dmi_entry_idx,
                                                                                                                            key))
                                        dmi_key_idx = dc.insert_id()
                                        for ext_value in value:
                                            dc.execute("INSERT INTO dmi_ext_key SET dmi_key=%s, ext_value_string=%s", (dmi_key_idx,
                                                                                                                       ext_value))
                                            added_dict["ext_key"] += 1
                                    else:
                                        dc.execute("INSERT INTO dmi_key SET dmi_entry=%s, key_string=%s, value_string=%s", (dmi_entry_idx,
                                                                                                                            key,
                                                                                                                            value))
                            self.log("  Added %s" % (", ".join([logging_tools.get_plural("dmi_%s key" % (key), num) for key, num in added_dict.iteritems()])))
                            ret_f.append(logging_tools.get_plural("dmi entry", sum(added_dict.values())))
                        else:
                            self.log("error reading dmi-info from host: %s" % (hwi_res["dmi"]),
                                     logging_tools.LOG_LEVEL_ERROR)
                else:
                    hw_dict = hwi_res
                dc.execute("SELECT ht.hw_entry_type_idx, ht.identifier FROM hw_entry_type ht")
                hw_e_dict = dict([(stuff["identifier"], stuff["hw_entry_type_idx"]) for stuff in dc.fetchall()])
                sql_array = []
                # handle cpus
                if hw_dict.has_key("cpus"):
                    # new style
                    cpu_info = hw_dict["cpus"]
                    if type(cpu_info) == type([]):
                        # old style (simple list)
                        for cpu in hw_dict["cpus"]:
                            if cpu.get("type", "").lower() == "uml":
                                sql_array.append(("cpu", 0, None, cpu.get("type", ""), None))
                            else:
                                sql_array.append(("cpu", int(float(cpu["speed"])), None, cpu.get("type", ""), None))
                    else:
                        # new style (dict for global_cpu_info)
                        cpu_info["parse"] = True
                        try:
                            cpu_info = cpu_database.global_cpu_info(**cpu_info)
                            for cpu in [cpu_info[cpu_idx] for cpu_idx in cpu_info.cpu_idxs()]:
                                if cpu.get("online", True):
                                    if cpu.has_key("simple"):
                                        # old style
                                        sql_array.append(("cpu", int(float(cpu[(1, "eax")]["speed"].value)), None, cpu["simple"]["brand"], None))
                                    else:
                                        # new style
                                        sql_array.append(("cpu", int(float(cpu["speed"])), None, cpu["model name"], None))
                        except:
                            self.log(" error creating cpu_database info: %s" % (process_tools.get_except_info()),
                                     logging_tools.LOG_LEVEL_CRITICAL)
                        else:
                            dc.execute("UPDATE device SET cpu_info=%s WHERE device_idx=%s", (server_command.sys_to_net(cpu_info),
                                                                                             self.device_idx))
                else:
                    # old style
                    for cpunum in range(hw_dict["num_cpus"]):
                        sql_array.append(("cpu", hw_dict["cpu_speed"], None, hw_dict["cpu_type"], None))
                # gfx-card
                if hw_dict.has_key("gfx"):
                    sql_array.append(("gfx", None, None, hw_dict["gfx"], None))
                if hw_dict.has_key("mem_total") and hw_dict.has_key("swap_total"):
                    sql_array.append(("mem", hw_dict["mem_total"], hw_dict["swap_total"], None, None))
                if hw_dict.has_key("rw_size") and hw_dict.has_key("num_rw"):
                    if hw_dict["num_rw"]:
                        sql_array.append(("disks", hw_dict["num_rw"], hw_dict["rw_size"], None, None))
                if hw_dict.has_key("num_ro"):
                    if hw_dict["num_ro"]:
                        sql_array.append(("cdroms", hw_dict["num_ro"], None, None, None))
                for stuff in sql_array:
                    sql_queue.put(("insert_value", ("hw_entry",
                                                    "0, %s, %s, %s, %s, %s, %s, null",
                                                    tuple([self.device_idx, hw_e_dict[stuff[0]]] + list(stuff)[1:]))))
                    num_hw += 1
                nn_changed = []
                if hwi_res.has_key("mac"):
                    mac_dict = dict([(value, {"devname" : key,
                                              "ips"     : []}) for key, value in server_command.net_to_sys(hwi_res["mac"][3:]).iteritems()])
                    sql_str = "SELECT n.devname, n.netdevice_idx, n.macadr, n.fake_macadr, i.ip FROM netdevice n LEFT JOIN netip i ON i.netdevice=n.netdevice_idx WHERE n.device=%d" % (self.device_idx)
                    dc.execute(sql_str)
                    # build netdevice_dict
                    nd_dict = {}
                    for db_rec in dc.fetchall():
                        if not nd_dict.has_key(db_rec["devname"]):
                            nd_dict[db_rec["devname"]] = {"ips"         : [],
                                                          "idx"         : db_rec["netdevice_idx"],
                                                          "macadr"      : db_rec["macadr"],
                                                          "fake_macadr" : db_rec["fake_macadr"]}
                        if db_rec["ip"]:
                            nd_dict[db_rec["devname"]]["ips"].append(db_rec["ip"])
                    # system arp table
                    act_arp_dict = process_tools.get_arp_dict()
                    # recognized ip addresses (ip -> (devname, macadr))
                    ips_actual = {}
                    for key, value in act_arp_dict.iteritems():
                        if mac_dict.has_key(key):
                            mac_dict[key]["ips"].append(value)
                            ips_actual[value] = (mac_dict[key]["devname"], key)
                    # devices which can be modified (present in db)
                    devs_to_modify = nd_dict.keys()
                    # devices which are already modifed or checked (for db and sys)
                    db_devs_modified, sys_devs_modified = ([], [])
                    # first step: modify devices found in arp-table
                    for ip, (devname, macadr) in ips_actual.iteritems():
                        # search db_devname via ipaddress
                        db_devname = [key for key, value in nd_dict.iteritems() if ip in value["ips"]]
                        if db_devname:
                            db_devname = db_devname[0]
                            db_devs_modified.append(db_devname)
                            sys_devs_modified.append(devname)
                            if macadr != nd_dict[db_devname]["macadr"]:
                                self.log("macaddr for device %s (from db, %s on host) differs (db: %s, host: %s)" % (devname,
                                                                                                                     db_devname,
                                                                                                                     nd_dict[db_devname]["macadr"],
                                                                                                                     macadr),
                                         logging_tools.LOG_LEVEL_WARN)
                                dc.execute("UPDATE netdevice SET macadr='%s' WHERE netdevice_idx=%d" % (macadr, nd_dict[db_devname]["idx"]))
                        else:
                            self.log("Found no db_entry for ip %s (device on node %s, macaddress %s)" % (ip, devname, macadr),
                                     logging_tools.LOG_LEVEL_ERROR)
                    # second step: insert macinfo for all other found devices
                    for db_devname, db_stuff in nd_dict.iteritems():
                        if db_devname not in db_devs_modified:
                            # search db_devname in mac_dict from device
                            macadr = [key for key, value in mac_dict.iteritems() if value["devname"] == db_devname and value["devname"] not in sys_devs_modified]
                            if macadr:
                                macadr = macadr[0]
                                db_devs_modified.append(db_devname)
                                sys_devs_modified.append(db_devname)
                                if nd_dict[db_devname]["macadr"] != macadr:
                                    self.log("macaddr for device %s (from db, same on host) differs (db: %s, host: %s)" % (db_devname,
                                                                                                                           nd_dict[db_devname]["macadr"],
                                                                                                                           macadr),
                                             logging_tools.LOG_LEVEL_WARN)
                                    dc.execute("UPDATE netdevice SET macadr='%s' WHERE netdevice_idx=%d" % (macadr, nd_dict[db_devname]["idx"]))
                    left_from_host = sorted([(key, value) for key, value in mac_dict.iteritems() if not value["devname"] in sys_devs_modified])
                    if left_from_host:
                        self.log("Unparsed info from host (%s): %s" % (logging_tools.get_plural("entry", len(left_from_host)),
                                                                       ", ".join(["%s [%s]" % (value["devname"], key) for key, value in left_from_host])),
                                 logging_tools.LOG_LEVEL_ERROR)
                    #for net_rec in dc.fetchall():
                    #    # check for altered macadress (ignoring fake_macaddresses)
                    #    if mac_dict.has_key(net_rec["devname"]) and (net_rec["macadr"] != mac_dict[net_rec["devname"]] and net_rec["fake_macadr"] != mac_dict[net_rec["devname"]]):
                    #        nn_changed.append(net_rec["devname"])
                    #        self.log("  - set macadr of %s to %s" % (net_rec["devname"], mac_dict[net_rec["devname"]]))
                self.log("  inserted %d pci-entries and %d hw-entries, corrected %s" % (num_pci,
                                                                                        num_hw,
                                                                                        "%s (%s)" % (logging_tools.get_plural("MAC-address", len(nn_changed)),
                                                                                                     ", ".join(nn_changed)) if nn_changed else "no MAC-addresses"))
                macs_changed = len(nn_changed)
            if ret_f:
                ret_str = ", ".join(ret_f)
        else:
            loc_error, ret_str = (True, "return string does not start with ok")
        self.log("  returning with %s (%s)" % (loc_error and "error" or "no error", ret_str))
        return loc_error, ret_str, macs_changed
    def get_pxe_file_name(self):
        return "%s/pxelinux.0" % (self.get_etherboot_dir())
    def get_mboot_file_name(self):
        return "%s/mboot.c32" % (self.get_etherboot_dir())
    def get_net_file_name(self):
        return "%s/bootnet" % (self.get_etherboot_dir())
    def get_etherboot_dir(self):
        if self.maint_ip:
            return "%s/%s" % (self.__glob_config["ETHERBOOT_DIR"], self.maint_ip)
        else:
            return None
    def get_pxelinux_dir(self):
        if self.maint_ip:
            return "%s/%s/pxelinux.cfg" % (self.__glob_config["ETHERBOOT_DIR"], self.maint_ip)
        else:
            return None
    def get_config_dir(self):
        if self.maint_ip:
            return "%s/%s" % (self.__glob_config["CONFIG_DIR"], self.maint_ip)
        else:
            return None
    def get_menu_file_name(self):
        return "%s/menu" % (self.get_etherboot_dir())
    def get_ip_file_name(self):
        return "%s/%s" % (self.get_pxelinux_dir(), self.maint_ip_hex)
    def get_ip_mac_file_base_name(self):
        return "01-%s" % (self.maint_mac.lower().replace(":", "-"))
    def get_ip_mac_file_name(self):
        return "%s/%s" % (self.get_pxelinux_dir(), self.get_ip_mac_file_base_name())
    def clear_ip_mac_files(self, except_list=[]):
        # clears all ip_mac_files except the ones listed in except_list
        pxe_dir = self.get_pxelinux_dir()
        for entry in os.listdir(pxe_dir):
            if entry.startswith("01-") and not entry in except_list:
                try:
                    os.unlink("%s/%s" % (pxe_dir, entry))
                except:
                    self.log("error removing pxe-boot file %s" % (entry),
                             logging_tools.LOG_LEVEL_ERROR)
                else:
                    self.log("removing pxe-boot file %s" % (entry))
    def write_dosboot_config(self, eepro100_pxe):
        os.symlink("../../images/dos_image", self.get_net_file_name())
        open(self.get_pxe_file_name(), "w").write(eepro100_pxe)
    def write_memtest_config(self):
        pxe_dir = self.get_pxelinux_dir()
        if pxe_dir:
            if os.path.isdir(pxe_dir):
                self.clear_ip_mac_files()
                open(self.get_ip_file_name()    , "w").write("DEFAULT ../../images/memtest.bin\n")
                open(self.get_ip_mac_file_name(), "w").write("DEFAULT ../../images/memtest.bin\n")
                if (os.path.isdir(self.get_etherboot_dir())):
                    if self.__glob_config["PXEBOOT"]:
                        open(self.get_pxe_file_name(), "w").write(self.__glob_config["PXELINUX_0"])
                    else:
                        self.log("not PXEBOOT capable (PXELINUX_0 not found)", logging_tools.LOG_LEVEL_ERROR)
        else:
            self.log("pxelinux_dir() returned NONE",
                     logging_tools.LOG_LEVEL_ERROR)
    def write_localboot_config(self):
        if self.get_pxelinux_dir():
            if os.path.isdir(self.get_pxelinux_dir()):
                self.clear_ip_mac_files()
                for name in [self.get_ip_file_name(), self.get_ip_mac_file_name()]:
                    open(name, "w").write("\n".join(["DEFAULT linux",
                                                     "LABEL linux",
                                                     "IMPLICIT 0",
                                                     "LOCALBOOT 0",
                                                     ""]))
                if self.__glob_config["PXEBOOT"]:
                    open(self.get_pxe_file_name(), "w").write(self.__glob_config["PXELINUX_0"])
                else:
                    self.log("not PXEBOOT capable (PXELINUX_0 not found)", logging_tools.LOG_LEVEL_ERROR)
    def write_kernel_config(self, sql_queue, kernel_stuff, kernel_append, s_ip, s_netmask, loc_config, stage1_flavour, check=False):
        kern_dst_dir = self.get_etherboot_dir()
        if kern_dst_dir:
            if os.path.isdir(kern_dst_dir):
                for file_name in ["i", "k", "x"]:
                    fname = "%s/%s" % (kern_dst_dir, file_name)
                    if not check:
                        if os.path.islink(fname):
                            os.unlink(fname)
                for stage_name in ["stage2", "stage3"]:
                    stage_source = "/opt/cluster/lcs/%s" % (stage_name)
                    stage_dest  ="%s/%s" % (kern_dst_dir, stage_name)
                    if not os.path.isfile(stage_source):
                        self.log("Error, cannot find %s_source '%s'..." % (stage_name, stage_source))
                    elif not os.path.isfile(stage_dest) or (os.path.isfile(stage_dest) and os.stat(stage_source)[stat.ST_MTIME] > os.stat(stage_dest)[stat.ST_MTIME]):
                        self.log("Copying %s from %s to %s ..." % (stage_name, stage_source, stage_dest))
                        open(stage_dest, "w").write(open(stage_source, "r").read())
                kernel_name = kernel_stuff["name"]
                #print kernel_stuff
                kern_base_dir = "../../kernels/%s" % (kernel_name)
                kern_abs_base_dir = "%s/kernels/%s" % (self.__glob_config["TFTP_DIR"], kernel_name)
                unlink_field = ["%s/k" % (kern_dst_dir),
                                "%s/i" % (kern_dst_dir),
                                "%s/x" % (kern_dst_dir)]
                valid_links = []
                if os.path.isdir(kern_abs_base_dir):
                    # check if requested flavour is ok
                    if not kernel_stuff["stage1_%s_present" % (stage1_flavour)]:
                        self.log("requested stage1_flavour '%s' not present" % (stage1_flavour),
                                 logging_tools.LOG_LEVEL_ERROR)
                    else:
                        link_field = [("%s/bzImage" % (kern_abs_base_dir)                     , "%s/bzImage" % (kern_base_dir)                     , "%s/k" % (kern_dst_dir)),
                                      ("%s/initrd_%s.gz" % (kern_abs_base_dir, stage1_flavour), "%s/initrd_%s.gz" % (kern_base_dir, stage1_flavour), "%s/i" % (kern_dst_dir))]
                        if kernel_stuff["xen_host_kernel"]:
                            link_field.append(("%s/xen.gz" % (kern_abs_base_dir), "%s/xen.gz" % (kern_base_dir), "%s/x" % (kern_dst_dir)))
                        for abs_src, src, dst in link_field:
                            if kernel_name:
                                if os.path.isfile(abs_src):
                                    c_link = True
                                    if check:
                                        if os.path.islink(dst):
                                            act_dst = os.readlink(dst)
                                            if src == act_dst:
                                                #self.log("Link %s is still valid (points to %s)" % (dst, act_dst))
                                                valid_links.append(dst)
                                                c_link = False
                                            else:
                                                os.unlink(dst)
                                        elif os.path.isfile(dst):
                                            os.unlink(dst)
                                    if c_link:
                                        self.log("Linking from %s to %s" % (dst, src))
                                        #print "symlink()", src, dst
                                        os.symlink(src, dst)
                                        valid_links.append(dst)
                                else:
                                    self.log("source %s for symlink() does not exist" % (abs_src),
                                             logging_tools.LOG_LEVEL_ERROR)
                                    if not check:
                                        valid_links.append(dst)
                else:
                    self.log("source_kernel_dir %s does not exist" % (kern_abs_base_dir),
                             logging_tools.LOG_LEVEL_ERROR)
                    self.device_log_entry(0,
                                          "e",
                                          "error kernel_dir dir '%s' not found" % (kern_abs_base_dir),
                                          sql_queue,
                                          loc_config["LOG_SOURCE_IDX"])
                if unlink_field:
                    unlink_field = [l_path for l_path in unlink_field if os.path.islink(l_path) and not l_path in valid_links]
                    if unlink_field:
                        self.log("Removing %s: %s" % (logging_tools.get_plural("dead link", len(unlink_field)),
                                                      ", ".join(unlink_field)))
                        for l_path in unlink_field:
                            try:
                                os.unlink(l_path)
                            except:
                                self.log("error removing link %s: %s" % (l_path,
                                                                         process_tools.get_except_info()),
                                         logging_tools.LOG_LEVEL_ERROR)
                if stage1_flavour == "cpio":
                    root_str = ""
                else:
                    root_str = "root=/dev/ram0"
                append_string = (" ".join([root_str,
                                           "init=/linuxrc rw nbd=%s,%s,%d,%s %s" % (self.bootnetdevice_name,
                                                                                    self.boot_netdriver,
                                                                                    self.ethtool_options,
                                                                                    self.boot_netdriver_options.replace(" ", r"§"),
                                                                                    kernel_append)])).strip().replace("  ", " ").replace("  ", " ")
                self.clear_ip_mac_files([self.get_ip_mac_file_base_name()])
                if kernel_stuff["xen_host_kernel"]:
                    append_field = ["x dom0_mem=524288",
                                    "k console=tty0 ip=%s:%s::%s %s" % (self.maint_ip, s_ip, ipvx_tools.get_network_name_from_mask(s_netmask), append_string),
                                    "i"]
                else:
                    total_append_string = "initrd=i ip=%s:%s::%s %s" % (self.maint_ip, s_ip, ipvx_tools.get_network_name_from_mask(s_netmask), append_string)
                pxe_lines = []
                if self.__glob_config["NODE_BOOT_DELAY"]:
                    pxe_lines.extend(["TIMEOUT %d" % (self.__glob_config["NODE_BOOT_DELAY"]),
                                      "PROMPT 1"])
                pxe_lines.extend(["DISPLAY menu",
                                  "DEFAULT linux auto"])
                if kernel_name:
                    if kernel_stuff["xen_host_kernel"]:
                        pxe_lines.extend(["LABEL linux",
                                          "    KERNEL mboot.c32",
                                          "    APPEND %s" % (" --- ".join(append_field))])
                    else:
                        pxe_lines.extend(["LABEL linux",
                                          "    KERNEL k",
                                          "    APPEND %s" % (total_append_string)])
                pxe_lines.extend([""])
                if self.__glob_config["FANCY_PXE_INFO"]:
                    menu_lines = ["\x0c\x0f20%s\x0f07" % (("init.at Bootinfo, %s%s" % (time.ctime(), 80 * " "))[0:79])]
                else:
                    menu_lines = ["",
                                  ("init.at Bootinfo, %s%s" % (time.ctime(), 80 * " "))[0:79]]
                menu_lines.extend(["Nodename  , IP : %-30s, %s" % (self.get_name(), self.maint_ip),
                                   "Servername, IP : %-30s, %s" % (loc_config["SERVER_SHORT_NAME"], s_ip),
                                   "Netmask        : %s (%s)" % (s_netmask, ipvx_tools.get_network_name_from_mask(s_netmask)),
                                   "MACAddress     : %s" % (self.maint_mac.lower()),
                                   "Stage1 flavour : %s" % (stage1_flavour),
                                   "Kernel to boot : %s" % (kernel_name or "<no kernel set>"),
                                   "Kernel options : %s" % (append_string or "<none set>"),
                                   "will boot %s" % ("in %s" % (logging_tools.get_plural("second", int(self.__glob_config["NODE_BOOT_DELAY"] / 10))) if self.__glob_config["NODE_BOOT_DELAY"] else "immediately"),
                                   "",
                                   ""])
                open(self.get_ip_file_name()    , "w").write("\n".join(pxe_lines))
                open(self.get_ip_mac_file_name(), "w").write("\n".join(pxe_lines))
                open(self.get_menu_file_name()  , "w").write("\n".join(menu_lines))
                if kernel_stuff["xen_host_kernel"]:
                    if self.__glob_config["XENBOOT"]:
                        open(self.get_mboot_file_name(), "w").write(self.__glob_config["MBOOT.C32"])
                    else:
                        self.log("not XENBOOT capable (MBOOT.C32 not found)", logging_tools.LOG_LEVEL_ERROR)
                if self.__glob_config["PXEBOOT"]:
                    open(self.get_pxe_file_name(), "w").write(self.__glob_config["PXELINUX_0"])
                else:
                    self.log("not PXEBOOT capable (PXELINUX_0 not found)", logging_tools.LOG_LEVEL_ERROR)
            else:
                self.log("Error: directory %s does not exist" % (kern_dst_dir))
                self.device_log_entry(1,
                                      "e",
                                      "error etherboot dir '%s' not found" % (kern_dst_dir),
                                      sql_queue,
                                      self.__loc_config["NODE_SOURCE_IDX"])
        else:
            self.log("Error: etherboot-dir not defined")

class outlet(object):
    def __init__(self, number=0):
        self.number = number
        self.v_dict = {}
        for key, dv in [("state"            , "?"),
                        ("name"             , "not used"),
                        ("power_on_delay"   , 0),
                        ("power_off_delay"  , 0),
                        ("reboot_delay"     , 0),
                        ("t_power_on_delay" , 0),
                        ("t_power_off_delay", 0),
                        ("t_reboot_delay"   , 5),
                        ("slave_device"     , 0),
                        ("idx"              , 0)]:
            self[key] = dv
    def get_number(self):
        return self.number
    def __setitem__(self, key, value):
        self.v_dict[key] = value
    def __getitem__(self, key):
        return self.v_dict[key]
    
class blade(object):
    def __init__(self, number=0):
        self.number = number
        self.v_dict = {}
        for key, dv in [("state"       , "?"),
                        ("name"        , "not used"),
                        ("slave_device", 0),
                        ("idx"         , 0),
                        ("blade_exists", 0)]:
            self[key] = dv
    def get_number(self):
        return self.number
    def __setitem__(self, key, value):
        self.v_dict[key] = value
    def __getitem__(self, key):
        return self.v_dict[key]
    
class switch(machine):
    def __init__(self, name, idx, dc, ad_struct):
        machine.__init__(self, name, idx, dc, ad_struct)
    
class apc(machine):
    def __init__(self, name, idx, dc, ad_struct):
        machine.__init__(self, name, idx, dc, ad_struct)
        # device keys
        self.__dev_keys = ["power_on_delay", "reboot_delay", "apc_type", "version_info", "num_outlets"]
        # internal stuff like type, power on / off
        self.__value_dict = {}
        self._init_apc_device_struct(dc)
        self._refresh_base_from_database(dc)
        # mib dict
        self.__mib_dict = {}
        ## outlets, too early to initialize
        #self.outlets = {}
    def update(self, command_queue):
        self.__command_queue = command_queue
        if not self.__value_dict["apc_type"]:
            # apc_type is not set, fetch basic values
            command_queue.put(("snmp_command_low_level", ("fetch_type", self, {"G" : self.apc_masterswitch_type_mibs()})))
        else:
            self.log("Reprogramming APC")
            command_queue.put(("snmp_command", ("reprogram",
                                                None,
                                                server_command.server_command(command="apc_com",
                                                                              nodes=[self.name],
                                                                              node_commands={self.name : "update"}))))
    def _init_apc_device_struct(self, dc):
        # get apc_device
        dc.execute("SELECT * FROM apc_device WHERE device=%d" % (self.device_idx))
        if dc.rowcount:
            self.log("apc_device struct found")
            self.__apc_device_idx = dc.fetchone()["apc_device_idx"]
        else:
            self.log("Creating apc_device struct")
            dc.execute("INSERT INTO apc_device SET device=%d" % (self.device_idx))
            self.__apc_device_idx = dc.insert_id()
        if self.__apc_device_idx:
            self.log("apc_device_idx is %d" % (self.__apc_device_idx))
        else:
            self.log("apc_device_idx not set", logging_tools.LOG_LEVEL_ERROR)
        self._set_apc_type()
    def _get_apc_type_str(self):
        return {0 : "unknown",
                1 : "ap7920 / rpdu",
                2 : "ap9606 / masterswitch"}.get(self.__apc_type, "unknown")
    def _apc_is_valid(self):
        return self.__apc_type and self.__value_dict["num_outlets"]
    def _set_apc_type(self, apc_type="", version_str=""):
        self.__apc_type = 0
        if version_str:
            in_split = version_str[1:].split(version_str[0])
            if len(in_split) > 4:
                apc_vers = in_split[-2]
                self.__apc_type = {("rpdu"        , "ap7920") : 1,
                                   ("rpdu"        , "ap7921") : 1,
                                   ("masterswitch", "ap9606") : 2,
                                   ("masterswitch", "ap7920") : 2,
                                   ("masterswitch", "ap7921") : 2,
                                   ("masterswitch", "ap7954") : 1,
                                   ("rpdu"        , "ap7954") : 1}.get((apc_type.lower(), apc_vers.lower()), 0)
        self.log("Setting apc_type according to apc_type '%s', version_info '%s' to %d (%s)" % (apc_type,
                                                                                                version_str,
                                                                                                self.__apc_type,
                                                                                                self._get_apc_type_str()))
        self._set_mibs()
    def _init_outlets(self):
        self.log("configuring outlet_struct for %s" % (logging_tools.get_plural("outlet", self.__value_dict["num_outlets"])))
        self.outlets = {}
        for i in range(1, self.__value_dict["num_outlets"] + 1):
            new_outlet = outlet(i)
            self.outlets[new_outlet.get_number()] = new_outlet
    def _set_mibs(self):
        self.log("settings mibs according to apc_type %d (%s)" % (self.__apc_type,
                                                                  self._get_apc_type_str()))
        if self.__apc_type == 1:
            # new rpdu mib
            self.__mib_dict = {"number_of_outlets" : (1, 3, 6, 1, 4, 1, 318, 1, 1, 12, 1, 8, 0),
                               "general_command"   : (1, 3, 6, 1, 4, 1, 318, 1, 1, 12, 3, 1, 1, 0),
                               "power_on_delay"    : (1, 3, 6, 1, 4, 1, 318, 1, 1, 12, 3, 1, 2, 0),
                               "name"              : (1, 3, 6, 1, 2, 1, 1, 5, 0),
                               "contact"           : (1, 3, 6, 1, 2, 1, 1, 4, 0),
                               "trap_mib"          : (1, 3, 6, 1, 4, 1, 318, 1, 1, 12, 3, 3, 1, 1, 1, 0),
                               "trap_receiver"     : (1, 3, 6, 1, 4, 1, 318, 2, 1, 2, 1, 2, 1)}
            
        elif self.__apc_type == 2:
            # old masterswitch mib
            self.__mib_dict = {"number_of_outlets" : (1, 3, 6, 1, 4, 1, 318, 1, 1, 4, 4, 1, 0),
                               "general_command"   : (1, 3, 6, 1, 4, 1, 318, 1, 1, 4, 2, 1, 0),
                               "power_on_delay"    : (1, 3, 6, 1, 4, 1, 318, 1, 1, 4, 3, 1, 0),
                               "reboot_delay"      : (1, 3, 6, 1, 4, 1, 318, 1, 1, 4, 3, 2, 0),
                               "name"              : (1, 3, 6, 1, 2, 1, 1, 5, 0),
                               "contact"           : (1, 3, 6, 1, 2, 1, 1, 4, 0),
                               "trap_mib"          : (1, 3, 6, 1, 4, 1, 318, 2, 3, 1, 0),
                               "trap_receiver"     : (1, 3, 6, 1, 4, 1, 318, 2, 1, 2, 1, 2, 1)}
        else:
            # unknown, clear all mibs
            self.__mib_dict = {}
        self._build_mib_lut()
    def _add_outlet_mibs(self):
        self.log("adding outlet_mibs for %s" % (logging_tools.get_plural("outlet", self.__value_dict["num_outlets"])))
        if self.__apc_type == 1:
            # new rpdu mib
            for o_num in range(1, self.__value_dict["num_outlets"] + 1):
                self.__mib_dict["state_%d" % (o_num)]           = (1, 3, 6, 1, 4, 1, 318, 1, 1, 12, 3, 3, 1, 1, 4, o_num)
                self.__mib_dict["name_%d" % (o_num)]            = (1, 3, 6, 1, 4, 1, 318, 1, 1, 12, 3, 4, 1, 1, 2, o_num)
                self.__mib_dict["power_on_delay_%d" % (o_num)]  = (1, 3, 6, 1, 4, 1, 318, 1, 1, 12, 3, 4, 1, 1, 4, o_num)
                self.__mib_dict["power_off_delay_%d" % (o_num)] = (1, 3, 6, 1, 4, 1, 318, 1, 1, 12, 3, 4, 1, 1, 5, o_num)
                self.__mib_dict["reboot_delay_%d" % (o_num)]    = (1, 3, 6, 1, 4, 1, 318, 1, 1, 12, 3, 4, 1, 1, 6, o_num)
        elif self.__apc_type == 2:
            # old masterswitch mib
            for o_num in range(1, self.__value_dict["num_outlets"] + 1):
                self.__mib_dict["state_%d" % (o_num)]           = (1, 3, 6, 1, 4, 1, 318, 1, 1, 4, 4, 2, 1, 3, o_num)
                self.__mib_dict["name_%d" % (o_num)]            = (1, 3, 6, 1, 4, 1, 318, 1, 1, 4, 5, 2, 1, 3, o_num)
                self.__mib_dict["power_on_delay_%d" % (o_num)]  = (1, 3, 6, 1, 4, 1, 318, 1, 1, 4, 5, 2, 1, 2, o_num)
                self.__mib_dict["power_off_delay_%d" % (o_num)] = (1, 3, 6, 1, 4, 1, 318, 1, 1, 4, 5, 2, 1, 4, o_num)
                self.__mib_dict["reboot_delay_%d" % (o_num)]    = (1, 3, 6, 1, 4, 1, 318, 1, 1, 4, 5, 2, 1, 5, o_num)
        self._build_mib_lut()
    def _build_mib_lut(self):
        self.__mib_lut = dict([(value, key) for key, value in self.__mib_dict.iteritems()])
    def _refresh_base_from_database(self, dc):
        if self.__apc_device_idx:
            sql_str = "SELECT %s FROM apc_device WHERE apc_device_idx=%d" % (", ".join(self.__dev_keys), self.__apc_device_idx)
            dc.execute(sql_str)
            db_set = dc.fetchone()
            for dev_key in self.__dev_keys:
                if dev_key.endswith("delay"):
                    def_val = 0
                else:
                    def_val = "unknown"
                self.__value_dict[dev_key] = db_set[dev_key] or def_val
        else:
            self.log("apc_device_idx not set", logging_tools.LOG_LEVEL_CRITICAL)
            self.__value_dict["apc_type"] = None
        self._invalidate_apc_type()
    def _invalidate_apc_type(self):
        self.log("invalidating apc_type (previous value: %s)" % (str(self.__value_dict["apc_type"])))
        self.__value_dict["apc_type"] = None
        self.__value_dict["num_outlets"] = 0
        self.__mib_dict = {}
    def refresh_from_database(self, dc):
        sql_str = "SELECT m.outlet, m.state, m.t_power_on_delay, m.t_power_off_delay, m.t_reboot_delay, m.slave_device, m.msoutlet_idx AS idx FROM msoutlet m WHERE m.device=%d ORDER BY m.outlet" % (self.device_idx)
        dc.execute(sql_str)
        if dc.rowcount:
            found_outlets, del_idxs = ([], [])
            for db_set in dc.fetchall():
                db_outlet = db_set["outlet"]
                if db_outlet in found_outlets:
                    self.log("found second entry for outlet %d, deleting" % (db_outlet),
                             logging_tools.LOG_LEVEL_ERROR)
                    del_idxs.append(db_set["idx"])
                else:
                    found_outlets.append(db_outlet)
                    for state_str in ["state", "t_power_on_delay", "t_power_off_delay", "t_reboot_delay", "slave_device", "idx"]:
                        if self.outlets.has_key(db_outlet):
                            self.outlets[db_outlet][state_str] = db_set[state_str]
                        else:
                            self.log("no outlet with index %d known (state_str is '%s', setting to '%s')" % (db_outlet,
                                                                                                             state_str,
                                                                                                             db_set[state_str]),
                                     logging_tools.LOG_LEVEL_ERROR)
            if del_idxs:
                dc.execute("DELETE FROM msoutlet WHERE %s" % (" OR ".join(["msoutlet_idx=%d" % (idx) for idx in del_idxs])))
            self.log("read APC and outlet info from database")
        else:
            self.log("No outlet-info found, waiting for update from APC...")
    def read_names_from_database(self, dc):
        slave_devs = [self.outlets[i]["slave_device"] for i in range(1, self.__value_dict["num_outlets"] + 1) if self.outlets[i]["slave_device"]]
        if slave_devs:
            sql_str = "SELECT d.name, m.outlet FROM device d, msoutlet m WHERE m.slave_device=d.device_idx AND m.device=%d AND (%s)" % (self.device_idx,
                                                                                                                                        " OR ".join(["d.device_idx=%d" % (x) for x in slave_devs]))
            dc.execute(sql_str)
            for res in dc.fetchall():
                self.outlets[res["outlet"]]["name"] = res["name"]
    def feed_snmp_results(self, source, vals):
        self.log("got %s from source %s" % (logging_tools.get_plural("value", len(vals)),
                                            source))
        if source == "fetch_type":
            prev_type = self.__value_dict["apc_type"]
            valid_vals = len([True for oid, val in vals if val])
            if valid_vals:
                vers_parts = [""]
                for oid, value in vals:
                    what, outlet_num, val_str = self.get_mib_val_str(oid, value)
                    vers_parts.append(str(val_str))
                sub_set = vals[0][0][-4]
                if sub_set == 4:
                    self.__value_dict["apc_type"] = "masterswitch"
                elif sub_set == 12:
                    self.__value_dict["apc_type"] = "rpdu"
                else:
                    self.__value_dict["apc_type"] = None
                self.__value_dict["version_info"] = ":".join(vers_parts)
                #print what, val_str
                    #self.__value_dict[what] = val_str
                if self.__value_dict["apc_type"] and not prev_type:
                    self.log("apc_type is now valid (%s), performing update" % (self.__value_dict["apc_type"]))
                    self._set_apc_type(self.__value_dict["apc_type"], self.__value_dict["version_info"])
                    self.__command_queue.put(("snmp_command_low_level", ("fetch_num_outlets", self, {"G" : [self.__mib_dict.get("number_of_outlets", ())]})))
            else:
                if vals:
                    sub_set = vals[0][0][-4]
                    if sub_set == 4:
                        self.log("trying fetch_type for new masterswitch mib", logging_tools.LOG_LEVEL_WARN)
                        self.__command_queue.put(("snmp_command_low_level", ("fetch_type", self, {"G" : self.apc_rpdu_type_mibs()})))
        elif source == "fetch_num_outlets":
            try:
                num_outlets = int(str(vals[0][1]))
            except:
                num_outlets = 0
            self.__value_dict["num_outlets"] = num_outlets
            self._init_outlets()
            self._add_outlet_mibs()
            self.log("number of outlets: %d" % (self.__value_dict["num_outlets"]))
            dc = self.get_db_con().get_connection(SQL_ACCESS)
            self.refresh_from_database(dc)
            self.write_to_database(dc)
            dc.release()
            if self._apc_is_valid():
                self.update(self.__command_queue)
        elif source == "reprogram":
            for oid, value in vals:
                what, outlet_num, val_str = self.get_mib_val_str(oid, value)
                if outlet_num:
                    self.outlets[outlet_num][what] = val_str
                else:
                    self.__value_dict[what] = val_str
            dc = self.get_db_con().get_connection(SQL_ACCESS)
            self.write_to_database(dc)
            dc.release()
    def write_to_database(self, dc):
        if self.__apc_device_idx:
            sql_str, sql_tuple = ("UPDATE apc_device SET %s WHERE apc_device_idx=%s" % (", ".join(["%s=%%s" % (key) for key in self.__dev_keys]),
                                                                                        self.__apc_device_idx),
                                  tuple([self.__value_dict[key] for key in self.__dev_keys]))
            dc.execute(sql_str, sql_tuple)
        for i in range(1, self.__value_dict["num_outlets"] + 1):
            act_out = self.outlets[i]
            if not act_out["idx"]:
                # check if outlet is already present
                sql_str = "SELECT * FROM msoutlet WHERE device=%d AND outlet=%d" % (self.device_idx,
                                                                                    i)
                dc.execute(sql_str)
                if dc.rowcount:
                    self.log("tried to insert already present outlet, fixed bug",
                             logging_tools.LOG_LEVEL_ERROR)
                    db_rec = dc.fetchone()
                    for state_str in ["state", "t_power_on_delay", "t_power_off_delay", "t_reboot_delay", "slave_device", "idx"]:
                        act_out[state_str] = db_rec[state_str]
            if act_out["idx"]:
                sql_str, sql_tuple = ("UPDATE msoutlet SET state=%s, power_on_delay=%s, power_off_delay=%s, reboot_delay=%s WHERE msoutlet_idx=%s", (act_out["state"],
                                                                                                                                                     act_out["power_on_delay"],
                                                                                                                                                     act_out["power_off_delay"],
                                                                                                                                                     act_out["reboot_delay"],
                                                                                                                                                     act_out["idx"]))
            else:
                sql_str, sql_tuple = ("INSERT INTO msoutlet SET device=%s, slave_info=%s, outlet=%s, state=%s, t_power_on_delay=%s, t_power_off_delay=%s, t_reboot_delay=%s", (self.device_idx,
                                                                                                                                                                               "",
                                                                                                                                                                               i,
                                                                                                                                                                               act_out["state"],
                                                                                                                                                                               act_out["power_on_delay"],
                                                                                                                                                                               act_out["power_off_delay"],
                                                                                                                                                                               act_out["reboot_delay"]))
            #print sql_str
            try:
                dc.execute(sql_str, sql_tuple)
            except MySQLdb.Warning, what:
                self.log("+++ MySQL Warning excpetion has been thrown for %s (%s): %s" % (sql_str,
                                                                                          str(sql_tuple),
                                                                                          process_tools.get_except_info()),
                         logging_tools.LOG_LEVEL_ERROR)
            else:
                if sql_str.startswith("INSERT"):
                    self.outlets[i]["idx"] = dc.insert_id()
        self.log("wrote APC and outlet info to database")
    # IBM Blade
    # ".1.3.6.1.4.1.2.3.51.2.22.1.6.1.1.8.(1-16)
    def get_mib_state_str(self, val):
        return {1 : "on",
                2 : "off",
                3 : "reboot",
                4 : "unknown",
                5 : "on*",
                6 : "off*",
                7 : "reboot*"}.get(val, "unknown")
    def get_mib_val_str(self, mib, mib_val):
        what, o_num = self.mib_to_str(mib)
        if what == "state":
            mib_val = self.get_mib_state_str(mib_val)
        return what, o_num, mib_val
    def mib_to_str(self, mib, simple=False):
        ret_str, o_num = ("???", 0)
        if self.__mib_lut.has_key(mib):
            ret_str = self.__mib_lut[mib]
            ret_split = ret_str.split("_")
            if ret_split[-1].isdigit():
                o_num = int(ret_split[-1])
                ret_str = "_".join(ret_split[:-1])
        if simple:
            if o_num:
                return "%s on outlet %d" % (ret_str, o_num)
            else:
                return ret_str
        else:
            return ret_str, o_num
    def apc_masterswitch_type_mibs(self):
        return [(1, 3, 6, 1, 4, 1, 318, 1, 1, 4, 1, 1, 0),
                (1, 3, 6, 1, 4, 1, 318, 1, 1, 4, 1, 2, 0),
                (1, 3, 6, 1, 4, 1, 318, 1, 1, 4, 1, 3, 0),
                (1, 3, 6, 1, 4, 1, 318, 1, 1, 4, 1, 4, 0),
                (1, 3, 6, 1, 4, 1, 318, 1, 1, 4, 1, 5, 0)]
    def apc_rpdu_type_mibs(self):
        return [(1, 3, 6, 1, 4, 1, 318, 1, 1, 12, 1, 1, 0),
                (1, 3, 6, 1, 4, 1, 318, 1, 1, 12, 1, 2, 0),
                (1, 3, 6, 1, 4, 1, 318, 1, 1, 12, 1, 3, 0),
                (1, 3, 6, 1, 4, 1, 318, 1, 1, 12, 1, 4, 0),
                (1, 3, 6, 1, 4, 1, 318, 1, 1, 12, 1, 5, 0),
                (1, 3, 6, 1, 4, 1, 318, 1, 1, 12, 1, 6, 0)]
    def build_snmp_commands(self, com_strs, dc):
        if type(com_strs) == type(""):
            com_strs = [com_strs]
        # for multiple commands (','-delimeted)
        com_strs = sum([part.split(",") for part in com_strs], [])
        error, add_snmp_coms = (False, {})
        # ip_dict set and apc_type valid
        if self.ip_dict and self.__value_dict["apc_type"]:
            act_ip = self.ip_dict.keys()[0]
            set_args, get_args = ([], [])
            #act_ip = "-1"
            for com_str in com_strs:
                for arg_parts in [x.split("=") for x in com_str.split(":")]:
                    com = arg_parts.pop(0)
                    if com == "update":
                        self.refresh_from_database(dc)
                        self.read_names_from_database(dc)
                        server_ip = self.get_server_ip_addr(act_ip)
                        # not working right now, shit
                        #if server_ip:
                        #set_args.extend([(self.__mib_dict["trap_receiver"], rfc1902.IpAddress(server_ip))])
                        set_args.extend([(self.__mib_dict["name"]         , rfc1902.OctetString(self.name)),
                                         (self.__mib_dict["contact"]      , rfc1902.OctetString("lang-nevyjel@init.at"))])
                        for i in range(1, self.__value_dict["num_outlets"] + 1):
                            set_args.extend([(self.__mib_dict["power_on_delay_%d" % (i)] , rfc1902.Integer32(self.outlets[i]["t_power_on_delay"])),
                                             (self.__mib_dict["power_off_delay_%d" % (i)], rfc1902.Integer32(self.outlets[i]["t_power_off_delay"])),
                                             (self.__mib_dict["reboot_delay_%d" % (i)]   , rfc1902.Integer32(self.outlets[i]["t_reboot_delay"] or 5))])
                            get_args.extend([self.__mib_dict["state_%d" % (i)]])
                            set_args.append((self.__mib_dict["name_%d" % (i)],
                                             rfc1902.OctetString(self.outlets[i]["name"])))
                        get_args.extend([self.__mib_dict["power_on_delay"]])
                        if self.__mib_dict.has_key("reboot_delay"):
                            get_args.extend([self.__mib_dict["reboot_delay"]])
                    elif com == "refresh":
                        for i in range(1, self.__value_dict["num_outlets"] + 1):
                            get_args.extend([self.__mib_dict["power_on_delay_%d" % (i)],
                                             self.__mib_dict["power_off_delay_%d" % (i)],
                                             self.__mib_dict["reboot_delay_%d" % (i)],
                                             self.__mib_dict["state_%d" % (i)]])
                        get_args.extend([self.__mib_dict["power_on_delay"]])
                        if self.__mib_dict.has_key("reboot_delay"):
                            get_args.extend([self.__mib_dict["reboot_delay"]])
                    elif com == "gc":
                        set_args.append((self.__mib_dict["general_command"], rfc1902.Integer32(int(arg_parts[0]))))
                    elif com.startswith("c"):
                        set_args.append((self.__mib_dict["state_%d" % (int(com[1:]))], rfc1902.Integer32(int(arg_parts[0]))))
                    else:
                        error = True
                        self.log("Got unknown SNMP-command '%s'", logging_tools.LOG_LEVEL_ERROR)
            l_a = []
            if set_args:
                add_snmp_coms["S"] = set_args
                l_a.append(logging_tools.get_plural("set command", len(set_args)))
            if get_args:
                add_snmp_coms["G"] = get_args
                l_a.append(logging_tools.get_plural("get command", len(get_args)))
            self.log("SNMP commands '%s' resulted in %s" % (",".join(com_strs), " and ".join(l_a)))
        else:
            error = True
        return error, add_snmp_coms
    def add_trap(self, trap):
        trap.link_device(self)
    def handle_trap(self, trap):
        var_binds = trap.var_binds
        if self.__mib_dict.has_key("trap_mib"):
            if trap.generic_trap == 6 and trap.specific_trap in [268, 269, 41, 42, 43]:
                outlet_num = 0
                for oid, value in var_binds:
                    if rfc1902.ObjectName(self.__mib_dict["trap_mib"]).isPrefixOf(oid):
                        outlet_num = value[0][0]._value
                if outlet_num:
                    # 268 ... on, 269 ... off
                    act_outlet = self.outlets[outlet_num]
                    act_outlet["state"] = {41  : "on",
                                           42  : "off",
                                           43  : "reboot",
                                           268 : "on",
                                           269 : "off"}[trap.specific_trap]
                    sql_str = "UPDATE msoutlet SET state='%s' WHERE msoutlet_idx=%d" % (act_outlet["state"],
                                                                                        act_outlet["idx"])
                    self.log("Setting outlet %d to state '%s' because of trap" % (outlet_num, act_outlet["state"]))
                    dc = self.get_db_con().get_connection(SQL_ACCESS)
                    dc.execute(sql_str)
                    dc.release()
                else:
                    self.log("unable to extract outlet_num", logging_tools.LOG_LEVEL_ERROR)
            else:
                raise KeyError
        else:
            self.log("trap_mib not set in mib_dict", logging_tools.LOG_LEVEL_ERROR)
    
class ibc(machine):
    def __init__(self, name, idx, dc, ad_struct):
        machine.__init__(self, name, idx, dc, ad_struct)
        # get apc_device
        dc.execute("SELECT * FROM ibc_device WHERE device=%d" % (self.device_idx))
        if dc.rowcount:
            self.log("ibc_device struct found")
            self.__ibc_device_idx = dc.fetchone()["ibc_device_idx"]
        else:
            self.log("Creating ibc_device struct")
            dc.execute("INSERT INTO ibc_device SET device=%d" % (self.device_idx))
            self.__ibc_device_idx = dc.insert_id()
        self.__blade_type, self.__num_blades = ("unknown", 0)
        self.blades = {}
    def update(self, command_queue):
        self.log("Reprogramming IBC")
        command_queue.put(("snmp_command", ("reprogram",
                                            None,
                                            server_command.server_command(command="apc_com",
                                                                          nodes=[self.name],
                                                                          node_commands={self.name : "update"}))))
    def refresh_from_database(self, dc):
        if self.__ibc_device_idx:
            sql_str = "SELECT blade_type, num_blades FROM ibc_device WHERE ibc_device_idx=%d" % (self.__ibc_device_idx)
            dc.execute(sql_str)
            db_set = dc.fetchone()
            self.__blade_type = db_set["blade_type"]
            self.__num_blades = db_set["num_blades"]
            if not self.blades:
                for i in range(1, self.__num_blades + 1):
                    new_blade = blade(i)
                    self.blades[new_blade.get_number()] = new_blade
        sql_str = "SELECT i.device, i.blade, i.state, i.slave_device, i.ibc_connection_idx AS idx, i.blade_exists FROM ibc_connection i WHERE i.device=%d" % (self.device_idx)
        dc.execute(sql_str)
        if dc.rowcount:
            for db_set in dc.fetchall():
                blade_num = db_set["blade"]
                for blade_sn in ["state", "slave_device", "idx"]:
                    self.blades[blade_num][blade_sn] = db_set[blade_sn]
            self.log("read IBC and blade info from database")
        else:
            self.log("No blade-info found, waiting for update from IBC...")
    def read_names_from_database(self, dc):
        slave_devs = [self.blades[i]["slave_device"] for i in range(1, self.__num_blades + 1) if self.blades[i]["slave_device"]]
        if slave_devs:
            sql_str = "SELECT d.name,i.blade FROM device d, ibc_connection i WHERE i.slave_device=d.device_idx AND (%s)" % (" OR ".join(["d.device_idx=%d" % (x) for x in slave_devs]))
            dc.execute(sql_str)
            for res in dc.fetchall():
                self.blades[res["blade"]]["name"] = res["name"]
    def write_to_database(self, db_con):
        dc = db_con.get_connection(SQL_ACCESS)
        if self.__ibc_device_idx:
            sql_str, sql_tuple = ("UPDATE ibc_device SET blade_type=%s, num_blades=%s WHERE ibc_device_idx=%s", (self.__blade_type,
                                                                                                                 self.__num_blades,
                                                                                                                 self.__ibc_device_idx))
            dc.execute(sql_str, sql_tuple)
        for i in range(1, self.__num_blades + 1):
            act_blade = self.blades[i]
            if act_blade["idx"]:
                sql_str, sql_tuple = "UPDATE ibc_connection SET state=%s, blade_exists=%s WHERE ibc_connection_idx=%s", (act_blade["state"],
                                                                                                                         act_blade["blade_exists"],
                                                                                                                         act_blade["idx"])
            else:
                sql_str, sql_tuple = "INSERT INTO ibc_connection SET device=%s, state=%s, blade=%s, blade_exists=%s", (self.device_idx,
                                                                                                                       act_blade["state"],
                                                                                                                       i,
                                                                                                                       act_blade["blade_exists"])
            try:
                dc.execute(sql_str, sql_tuple)
            except MySQLdb.Warning, what:
                self.log("+++ MySQL Warning excpetion has been thrown for '%s': %s" % (sql_str, str(what)))
            else:
                if sql_str.startswith("INSERT"):
                    self.blades[i]["idx"] = dc.insert_id()
        dc.release()
        self.log("wrote IBC and blade info to database")
    # IBM Blade
    # ".1.3.6.1.4.1.2.3.51.2.22.1.6.1.1.8.(1-16)
    def get_mib_state_str(self, val):
        return {1 : "on",
                2 : "off",
                3 : "reboot"}[val]
    def get_mib_val_str(self, mib, mib_val):
        what, o_num = self.mib_to_str(mib)
        if what == "state":
            mib_val = self.get_mib_state_str(mib_val)
        return what, o_num, mib_val
    def set_mib(self, mib, mib_val):
        what, o_num, val_str = self.get_mib_val_str(mib, mib_val)
        if o_num:
            self.blades[o_num][what] = val_str
        else:
            if what == "type":
                self.__blade_type = val_str
            elif what == "num":
                self.__num_blades = val_str
                if not self.blades and self.__num_blades:
                    for i in range(1, self.__num_blades + 1):
                        new_blade = blade(i)
                        self.blades[new_blade.get_number()] = new_blade
    def mib_to_str(self, mib, simple=0):
        ret_str, b_num = ("???", 0)
        if rfc1902.ObjectName((1, 3, 6, 1, 4, 1, 2, 3, 51, 2, 22, 1, 6, 1, 1, 4)).isPrefixOf(mib):
            b_num = mib[-1]
            ret_str = "state"
        if rfc1902.ObjectName((1, 3, 6, 1, 4, 1, 2, 3, 51, 2, 22, 1, 7, 1, 1, 5)).isPrefixOf(mib):
            b_num = mib[-1]
            ret_str = "name"
        elif rfc1902.ObjectName((1, 3, 6, 1, 4, 1, 318, 1, 1, 4, 1, 4, 0)).isPrefixOf(mib):
        # novartis new apcs
        #elif rfc1902.ObjectName((1, 3, 6, 1, 4, 1, 318, 1, 1, 12, 1, 5, 0)).isPrefixOf(mib):
            o_num, ret_str = (0, "apc_type")
        elif rfc1902.ObjectName((1, 3, 6, 1, 4, 1, 318, 2, 1, 2, 1, 2)).isPrefixOf(mib):
            ret_str = "trap receiver %d" % (mib[-1])
        elif rfc1902.ObjectName((1, 3, 6, 1, 4, 1, 2, 3, 51, 2, 5, 1, 0)).isPrefixOf(mib):
            ret_str = "name"
        elif rfc1902.ObjectName((1, 3, 6, 1, 4, 1, 2, 3, 51, 2, 4, 9, 3, 1, 1, 0)).isPrefixOf(mib):
            ret_str = "contact"
        elif rfc1902.ObjectName((1, 3, 6, 1, 4, 1, 2, 3, 51, 2, 2, 21, 1, 1, 7, 0)).isPrefixOf(mib):
            ret_str = "type"
        elif rfc1902.ObjectName((1, 3, 6, 1, 4, 1, 2, 3, 51, 2, 22, 4, 19, 0)).isPrefixOf(mib):
            ret_str = "num"
        elif rfc1902.ObjectName((1, 3, 6, 1, 4, 1, 2, 3, 51, 2, 22, 1, 7, 1, 1, 3)).isPrefixOf(mib):
            b_num = mib[-1]
            ret_str = "blade_exists"
        if simple:
            if b_num:
                return "%s on blade %d" % (ret_str, b_num)
            else:
                return ret_str
        else:
            return ret_str, b_num
    def feed_snmp_results(self, source, vals):
        self.log("ignoring %s from source %s" % (logging_tools.get_plural("value", len(vals)),
                                                 source))
    def gen_command_mib(self):
        return (1, 3, 6, 1, 4, 1, 318, 1, 1, 4, 2, 1, 0)
    def name_mib(self):
        return (1, 3, 6, 1, 4, 1, 2, 3, 51, 2, 4, 5, 1, 0)
    def contact_mib(self):
        return (1, 3, 6, 1, 4, 1, 2, 3, 51, 2, 4, 9, 3, 1, 1, 0)
    def ibc_type_mib(self):
        return (1, 3, 6, 1, 4, 1, 2, 3, 51, 2, 2, 21, 1, 1, 7, 0)
    def num_blades_mib(self):
        return (1, 3, 6, 1, 4, 1, 2, 3, 51, 2, 22, 4, 19, 0)
    def blade_state_mib(self, num):
        # imbAgents.netfinitySupportProcessorAgent.bladeCenterSnmpMIB.bladeCenter.processorBlade" = "3.51.2.22.1"
        return (1, 3, 6, 1, 4, 1, 2, 3, 51, 2, 22, 1, 6, 1, 1, 4, num)
    def blade_name_mib(self, num):
        return (1, 3, 6, 1, 4, 1, 2, 3, 51, 2, 22, 1, 7, 1, 1, 5, num)
    def blade_restart_mib(self, num):
        return (1, 3, 6, 1, 4, 1, 2, 3, 51, 2, 22, 1, 6, 1, 1, 8, num)
    def blade_on_off_mib(self, num):
        return (1, 3, 6, 1, 4, 1, 2, 3, 51, 2, 22, 1, 6, 1, 1, 7, num)
    def blade_exists_mib(self, num):
        return (1, 3, 6, 1, 4, 1, 2, 3, 51, 2, 22, 1, 7, 1, 1, 3, num)
    def trap_receiver_mib(self, num=1):
        return (1, 3, 6, 1, 4, 1, 318, 2, 1, 2, 1, 2, num)
    def build_snmp_commands(self, com_strs, dc):
        if type(com_strs) == type(""):
            com_strs = [com_strs]
        # for multiple commands (','-delimeted)
        com_strs = sum([part.split(",") for part in com_strs], [])
        error, add_snmp_coms = (False, {})
        if self.ip_dict:
            act_ip = self.ip_dict.keys()[0]
            #act_ip = "-1"
            for com_str in com_strs:
                for arg_parts in [x.split("=") for x in com_str.split(":")]:
                    com = arg_parts.pop(0)
                    set_args, get_args = ([], [])
                    if com == "update":
                        self.refresh_from_database(dc)
                        self.read_names_from_database(dc)
                        set_args.extend([(self.name_mib(), rfc1902.OctetString(self.name)),
                                         (self.contact_mib(), rfc1902.OctetString("lang-nevyjel@init.at"))])
                        for i in range(1, self.__num_blades + 1):
                            if self.blades[i]["blade_exists"]:
                                get_args.extend([self.blade_state_mib(i)])
                            set_args.append((self.blade_name_mib(i), rfc1902.OctetString(self.blades[i]["name"])))
                            get_args.extend([self.blade_exists_mib(i)])
                        get_args.extend([self.ibc_type_mib(), self.num_blades_mib()])
                    elif com == "refresh":
                        for i in range(1, self.__num_blades + 1):
                            if self.blades[i]["blade_exists"]:
                                get_args.extend([self.blade_state_mib(i)])
                        get_args.extend([self.ibc_type_mib(), self.num_blades_mib()])
                    elif com == "gc":
                        set_args.append((self.gen_command_mib()   , rfc1902.Integer32(int(arg_parts[0]))))
                    elif com.startswith("c"):
                        blade_num = int(com[1:])
                        if int(arg_parts[0]) == 3:
                            set_args.append((self.blade_restart_mib(blade_num), rfc1902.Integer32(1)))
                        elif int(arg_parts[0]) in [1, 2]:
                            set_args.append((self.blade_on_off_mib(blade_num), rfc1902.Integer32({1 : 1, 2: 0}[int(arg_parts[0])])))
                    else:
                        error = True
                        self.log("Got unknown SNMP-command '%s'", logging_tools.LOG_LEVEL_ERROR)
                    l_a = []
                    if set_args:
                        add_snmp_coms["S"] = set_args
                        l_a.append(logging_tools.get_plural("set command", len(set_args)))
                    if get_args:
                        add_snmp_coms["G"] = get_args
                        l_a.append(logging_tools.get_plural("get command", len(get_args)))
                    self.log("SNMP commands '%s' resulted in %s" % (",".join(com_strs), " and ".join(l_a)))
        else:
            error = True
        return error, add_snmp_coms
    
class snmp_trap(object):
    def __init__(self, transport_domain, transport_address, req_msg, pmod, msg_ver):
        if type(transport_address) == type(()):
            self.source_host, self.source_port = transport_address
        else:
            raise ValueError, "transport_address is not of type tuple"
        req_pdu = pmod.apiMessage.getPDU(req_msg)
        if req_pdu.isSameTypeWith(pmod.TrapPDU()):
            if msg_ver == api.protoVersion1:
                #print "Enterprise: %s" % (pmod.apiTrapPDU.getEnterprise(req_pdu).prettyPrint())
                #print "Agent Address: %s" % (pmod.apiTrapPDU.getAgentAddr(req_pdu).prettyPrint())
                self.agent_address = pmod.apiTrapPDU.getAgentAddr(req_pdu).prettyPrint()
                self.generic_trap = pmod.apiTrapPDU.getGenericTrap(req_pdu)
                self.specific_trap = pmod.apiTrapPDU.getSpecificTrap(req_pdu)
                #print "Uptime: %s" % (pmod.apiTrapPDU.getTimeStamp(req_pdu).prettyPrint())
                self.var_binds = pmod.apiTrapPDU.getVarBindList(req_pdu)
            else:
                self.var_binds = pmod.apiPDU.getVarBindList(req_pdu)
        else:
            raise ValueError, "is not same type"
        self.device = None
    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        self.device.log(what, level)
    def link_device(self, device):
        self.device = device
        self.log("Trap linked to device")
        if self.generic_trap == 4:
            self.log("Authentication error, strange ...", logging_tools.LOG_LEVEL_ERROR)
        else:
            self.log("generic.specific is %d.%d, %s" % (self.generic_trap,
                                                        self.specific_trap,
                                                        logging_tools.get_plural("var_bind", len(self.var_binds))))
            try:
                self.device.handle_trap(self)
            except KeyError:
                self.log("device does not know how to handle this trap", logging_tools.LOG_LEVEL_ERROR)
            #snmp_queue.put(("snmp_trap", (transport_address[0], int(pmod.apiTrapPDU.getSpecificTrap(req_pdu)), var_binds)))
            #print "Var-binds:"
            #for oid, val in self.__var_binds:
            #    print "%s = %s" % (oid, val)
        
class snmp_trap_thread(threading_tools.thread_obj):
    def __init__(self, glob_config, loc_config, db_con, log_queue):
        self.__db_con = db_con
        self.__log_queue = log_queue
        self.__glob_config, self.__loc_config = (glob_config, loc_config)
        threading_tools.thread_obj.__init__(self, "snmp_trap", queue_size=100, loop_function=self._busy_loop)
        self.register_func("set_queue_dict", self._set_queue_dict)
        self.register_func("set_ad_struct", self._set_ad_struct)
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__log_queue.put(("log", (self.name, what, lev)))
    def _set_ad_struct(self, ad_struct):
        self.log("got ad_struct")
        self.__ad_struct = ad_struct
    def thread_running(self):
        self.__is_asleep = False
        self.send_pool_message(("new_pid", (self.name, self.pid)))
        transport_disp = dispatch.AsynsockDispatcher()
        transport_disp.registerTransport(dgram.udp.domainName,
                                         dgram.udp.UdpSocketTransport().openServerMode(("", 162)))
        transport_disp.registerRecvCbFun(self._callback_func)
        transport_disp.registerTimerCbFun(self._timer_func)
        self.__transport_disp = transport_disp
        self.__transport_disp.jobStarted(1)
    def _set_queue_dict(self, q_dict):
        self.__queue_dict = q_dict
    def _busy_loop(self):
        try:
            self.__transport_disp.runDispatcher()
        except:
            self.log("Got an Error: %s" % (process_tools.get_except_info()),
                     logging_tools.LOG_LEVEL_ERROR)
    def _callback_func(self, t_disp, transport_domain, transport_address, whole_msg):
        while whole_msg:
            msg_ver = int(api.decodeMessageVersion(whole_msg))
            if api.protoModules.has_key(msg_ver):
                pmod = api.protoModules[msg_ver]
            else:
                self.log("Unsupported SNMP version %s" % (msg_ver),
                         logging_tools.LOG_LEVEL_WARN)
                pmod = None
            if pmod:
                #self.log("msg_ver is %s" % (msg_ver))
                try:
                    req_msg, whole_msg = pyasn1.codec.ber.decoder.decode(whole_msg, asn1Spec=pmod.Message())
                except pyasn1.type.error.ValueConstraintError:
                    self.log("ValueConstraintError triggered (authentication trap ?): %s" % (process_tools.get_except_info()),
                             logging_tools.LOG_LEVEL_ERROR)
                    whole_msg = None
                except:
                    self.log("error decoding SNMP_trap: %s" % (process_tools.get_except_info()),
                             logging_tools.LOG_LEVEL_ERROR)
                    whole_msg = None
                else:
                    try:
                        act_trap = snmp_trap(transport_domain, transport_address, req_msg, pmod, msg_ver)
                    except:
                        self.log("cannot create trap: %s" % (process_tools.get_except_info()),
                                 logging_tools.LOG_LEVEL_ERROR)
                    else:
                        if self.__ad_struct.has_key(act_trap.agent_address):
                            self.__ad_struct[act_trap.agent_address].add_trap(act_trap)
                        else:
                            self.log("agent_address %s not found in ad_struct" % (act_trap.agent_address),
                                     logging_tools.LOG_LEVEL_WARN)
    def _timer_func(self, *args):
        self.inner_loop()
        if not self["run_flag"]:
            self.__transport_disp.jobFinished(1)

class snmp_send_thread(threading_tools.thread_obj):
    def __init__(self, glob_config, loc_config, db_con, log_queue):
        self.__db_con = db_con
        self.__log_queue = log_queue
        self.__glob_config, self.__loc_config = (glob_config, loc_config)
        threading_tools.thread_obj.__init__(self, "snmp_send", queue_size=100, loop_function=self._busy_loop)
        self.register_func("set_queue_dict", self._set_queue_dict)
        self.register_func("new_snmp_batch", self._new_snmp_batch)
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__log_queue.put(("log", (self.name, what, lev)))
    def thread_running(self):
        self.__is_asleep = False
        self.send_pool_message(("new_pid", (self.name, self.pid)))
        self._init_acg()
        self.__new_batches = []
    def _set_queue_dict(self, q_dict):
        self.__queue_dict = q_dict
    def _init_acg(self):
        self.log("init AsynCommandGenerator")
        self.__acg = cmdgen.AsynCommandGenerator()
    def _new_snmp_batch(self, snmp_batch):
        self.__new_batches.append(snmp_batch)
    def _busy_loop(self):
        check_for_new_batches = False
        if self.__acg:
            if self.__acg.snmpEngine.transportDispatcher:
                if self.__is_asleep:
                    self.__is_asleep = False
                if self.__acg.snmpEngine.transportDispatcher.jobsArePending():
                    self.log("transportDispatcher valid and jobs pending, starting dispatcher (own q_size is %d)" % (self.get_thread_queue().qsize()))
                    try:
                        self.__acg.snmpEngine.transportDispatcher.runDispatcher()
                    except pyasn1.error.PyAsn1Error, what:
                        self.log("Got an PyAsn1Error: %s" % (what),
                                 logging_tools.LOG_LEVEL_CRITICAL)
                    except:
                        exc_info = process_tools.exception_info()
                        self.log("runDispatcher() threw an exception: %s" % (process_tools.get_except_info()),
                                 logging_tools.LOG_LEVEL_CRITICAL)
                        for line in exc_info.log_lines:
                            self.log(line, logging_tools.LOG_LEVEL_CRITICAL)
                if not self.__acg.snmpEngine.transportDispatcher.jobsArePending() and not self.__is_asleep:
                    self.__is_asleep = True
                    self.log("no more pending jobs, enter sleep mode")
                    check_for_new_batches = True
            else:
                check_for_new_batches = True
            if check_for_new_batches and self.__new_batches:
                self.log("init %s" % (logging_tools.get_plural("new snmp_batch", len(self.__new_batches))))
                for new_batch in self.__new_batches:
                    new_batch.init_send(self.__acg)
                self.__new_batches = []
                self.__is_asleep = False
                goto_sleep = False
            else:
                goto_sleep = True
        else:
            goto_sleep = True
        if goto_sleep:
            if not self.__is_asleep:
                self.__is_asleep = True
                self.log("transportDispatcher not valid, enter sleep mode")
        if self.__is_asleep:
            mes_list = self.inner_loop(True)

class snmp_result(object):
    def __init__(self, error=None):
        # state can be one of (e)rror, (w)ait or (o)k
        self.state = "w"
        if error:
            self.set_error("error while init()", error)
    def set_error(self, result, error):
        self.state, self.result_str, self.error = ("e", result, error)
    def set_result(self, var_list):
        self.state, self.var_list = ("o", var_list)
            
class snmp_batch_class(object):
    def __init__(self, com_source, int_com, dev_struct):
        self.__com_source = com_source
        self.__int_com = int_com
        self.__dev_struct = dev_struct
        self.__ticket_num = 0
        self.set_community, self.get_community = ("private", "public")
        # FIXME
        self.__pending = {}
        self.__start_time = time.time()
        self.__sets, self.__gets = ([], [])
    def set_community_strings(self, **args):
        if args.has_key("read_community"):
            self.get_community = args["read_community"]
        if args.has_key("write_community"):
            self.set_community = args["write_community"]
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__dev_struct.log(what, lev)
    def add_set(self, dst, set_list):
        self.__sets.append((dst, set_list))
    def add_get(self, dst, get_list):
        self.__gets.append((dst, get_list))
    def init_send(self, acg):
        for dst, set_list in self.__sets:
            if set_list == [()]:
                pass
            else:
                while True:
                    act_set_list = []
                    while set_list and len(act_set_list) < 32:
                        act_set_list.append(set_list.pop(0))
                    if act_set_list:
                        self.__ticket_num += 1
                        try:
                            # FIXME
                            acg.asyncSetCmd(cmdgen.CommunityData("localhost", self.set_community, 0),
                                            cmdgen.UdpTransportTarget(("%s" % (dst), 161)), 
                                            tuple(act_set_list),
                                            (self.get_set_recv, self.__ticket_num))
                        except (socket.gaierror, socket.error):
                            self.log("error sending SNMP set command: %s" % (process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
                            self.__pending[self.__ticket_num] = snmp_result("send_set_error")
                        else:
                            self.log("sent %s (community %s), source is %s" % (logging_tools.get_plural("set", len(act_set_list)),
                                                                               self.set_community,
                                                                               self.__com_source))
                            self.__pending[self.__ticket_num] = snmp_result()
                    else:
                        break
        for dst, get_list in self.__gets:
            if get_list == [()]:
                pass
            else:
                while True:
                    act_get_list = []
                    while get_list and len(act_get_list) < 32:
                        act_get_list.append(get_list.pop(0))
                    if act_get_list:
                        self.__ticket_num += 1
                        try:
                            # FIXME
                            acg.asyncGetCmd(cmdgen.CommunityData("localhost", self.get_community, 0),
                                            cmdgen.UdpTransportTarget((dst, 161)), 
                                            tuple(act_get_list),
                                            (self.get_set_recv, self.__ticket_num))
                        except (socket.gaierror, socket.error):
                            self.log("error sending SNMP get command: %s" % (process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
                            self.__pending[self.__ticket_num] = snmp_result("send_get_error")
                        else:
                            self.log("sent %s (community %s), source is %s" % (logging_tools.get_plural("get", len(act_get_list)),
                                                                               self.get_community,
                                                                               self.__com_source))
                            self.__pending[self.__ticket_num] = snmp_result()
                    else:
                        break
        self._check_change()
    def get_set_recv(self, send_request_handle, error_indication, error_status, error_index, var_list, tick_num):
        if error_indication:
            self.log("got error: %s" % (str(error_indication).lower()),
                     logging_tools.LOG_LEVEL_ERROR)
            print error_indication, type(error_indication)
            if True:#error_indication.lower() == "requesttimedout":
                # timeout
                self.log("deleting request with ticket_num %d" % (tick_num))
                self.__pending[tick_num].set_error("timeout", error_indication)
        else:
            if self.__pending.has_key(tick_num):
                self.__pending[tick_num].set_result(var_list)
            else:
                print "got response too late (ticket_num %d not found in dict)" % (tick_num)
        self._check_change()
    def _check_change(self):
        act_dict = dict([(key, []) for key in ["e", "o", "w"]])
        for key, value in self.__pending.iteritems():
            act_dict[value.state].append(key)
        if not act_dict["w"]:
            self.__end_time = time.time()
            self.log("SNMP commands done (%d ok, %d error, took %s)" % (len(act_dict["o"]),
                                                                        len(act_dict["e"]),
                                                                        logging_tools.get_diff_time_str(self.__end_time - self.__start_time)))
            self.__dev_struct.feed_snmp_results(self.__com_source, sum([self.__pending[key].var_list for key in act_dict["o"]], []))
            if self.__int_com:
                self.__dev_struct.release_lock(self.__int_com.com_name)
                self.__int_com.set_node_result(self.__dev_struct.name, "%s %s" % (len(act_dict["e"]) and "error" or "ok",
                                                                                  ", ".join([x for x in [len(act_dict["o"]) and "%s ok" % (logging_tools.get_plural("snmp_command", len(act_dict["o"]))) or "",
                                                                                                         len(act_dict["e"]) and "%s error" % (logging_tools.get_plural("snmp_command", len(act_dict["e"]))) or ""] if x])))
    def __repr__(self):
        act_dict = dict([(key, []) for key in ["e", "o", "w"]])
        for key, value in self.__pending.iteritems():
            act_dict[value.state].append(key)
        out_f = ["%s, %s:" % (self.__dev_struct.name,
                              logging_tools.get_plural("ticket", len(self.__pending.keys())))]
        out_f.append("  %d ok, %d pending, %d error" % (len(act_dict["o"]),
                                                        len(act_dict["w"]),
                                                        len(act_dict["e"])))
        return "\n".join(out_f)
        
class command_class(object):
    # defaults: port number is 0, no pre-ping, no command, real_command=command, no parallel-throttling
    def __init__(self, name, **args):
        self.com_name = name
        self.send_command = args.get("send_command", False)
        self.ping = args.get("ping", False)
        self.port = args.get("port", 0)
        self.real_command = args.get("real_command", self.com_name)
        self.parallel_throttling = args.get("parallel_throttling", False)
        self.needed_sql_fields = args.get("needed_sql_fields", [])
        # for handling of parallel throttled commands
        self.__devs_added = 0
        self.__actual_delay = 0
        self.delay_dict = {}
        self.dc = None
        # pending request part
        self.ip_match = re.compile("^(\d+)\.(\d+)\.(\d+)\.(\d+)$")
        # mapping (identifier, ip or name) -> name
        self.__dev_id_mapping = {}
        # mapping (name) -> (ip and name list)
        self.__inv_dev_mapping = {}
        # dictionary [machine_name]->[ip]->state_of_command, state key: 0 ... not set, 1 ... ok, -1 ... error
        self.__open_devs = {}
        # mapping from ip -> machine_id
        self.__ip_mapping = {}
        # mapping from machine_id -> ip
        self.__inv_ip_mapping = {}
        # results from contact_ids
        self.__ip_results = {}
        # dict, number of ips per device_name
        self.__num_ips = {}
        # return dicts
        self.__node_result_dict = {}
        self.__node_opt_dict = {}
        # open connections
        self.__connections_open = 0
    def __del__(self):
        if self.dc:
            self.dc.release()
            del self.dc
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__log_queue.put(("log", (threading.currentThread().getName(), what, lev)))
    def pre_command(self, mach_struct, q_dict, dc):
        pass
    def post_call(self, mach_struct):
        pass
    def link_objects(self, srv_com, net_server, icmp_obj, ad_struct, q_dict, db_con, glob_config, loc_config):
        self.srv_com = srv_com
        self.ad_struct = ad_struct
        self.queue_dict = q_dict
        self.__log_queue = q_dict["log_queue"]
        self.__glob_config, self.__loc_config = (glob_config, loc_config)
        # for handling of result calls
        self.dc = db_con.get_connection(SQL_ACCESS)
        # for initialising
        init_dc = db_con.get_connection(SQL_ACCESS)
        self.__device_ids = [x for x in srv_com.get_nodes()]
        self.__devs_pending = len(self.__device_ids)
        self.__dev_id_mapping = dict([(mach, None) for mach in self.__device_ids])
        self.__node_result_dict = dict([(mach, "error not set") for mach in self.__device_ids])
        self.__node_opt_dict = dict([(mach, "error not set") for mach in self.__device_ids])
        # lock setup stage, otherwise its possible to send a return value too early
        self.__setup = True
        dev_names_added = []
        for mach_id in self.__device_ids:
            # examine main dictionaries
            ip_list, mach_name, mach_struct = (None, "", None)
            if not self.ad_struct.has_key(mach_id):
                self.log("Key %s not found in ad_struct, examining database..." % (mach_id), logging_tools.LOG_LEVEL_WARN)
                self.ad_struct.db_sync(init_dc, [mach_id], [])
            if not self.ad_struct.has_key(mach_id):
                self.log("Device %s not found in database" % (mach_id), logging_tools.LOG_LEVEL_WARN)
            else:
                basic_setup_ok = True
                if self.ip_match.match(mach_id):
                    # contact ip-address
                    mach_name = self.ad_struct[mach_id].name
                    ip_list = [mach_id]
                else:
                    # contact name
                    mach_name = mach_id
                    ip_list = sorted(self.ad_struct[mach_id].ip_dict.keys())
                    if not ip_list:
                        self.log("Empty IP-List for device %s, examining database..." % (mach_name))
                        self.ad_struct.db_sync(init_dc, [mach_id], [])
                        ip_list = sorted(self.ad_struct[mach_id].ip_dict.keys())
                        if not ip_list:
                            self.log("IP-List still empty for %s after DB check" % (mach_name), logging_tools.LOG_LEVEL_ERROR)
                            basic_setup_ok = False
                if self.send_command or self.ping:
                    # ip-list (already sorted)
                    pass
                else:
                    # server-local command, no contact needed
                    ip_list = []
                mach_struct = self.ad_struct[mach_name]
                if self.__loc_config["VERBOSE"] > 2:
                    self.log("adding device %s (id %s, %s: %s)" % (mach_struct.name,
                                                                   mach_id,
                                                                   logging_tools.get_plural("IP address", len(ip_list)),
                                                                   ", ".join(ip_list)))
                self.add_dev_mapping(mach_id, mach_name, ip_list)
                if not basic_setup_ok:
                    self.__open_devs[mach_name] = ":".join(["e", "", "", "not reachable"])
                #return ip_list, mach_name, mach_struct
                if self.parallel_throttling:
                    if self.__devs_added == self.__glob_config["SIMULTANEOUS_REBOOTS"]:
                        self.__devs_added = 0
                        self.__actual_delay += self.__glob_config["REBOOT_DELAY"]
                self.__devs_added += 1
                if self.__actual_delay:
                    self.__open_devs[mach_name] = ":".join(["e", "", "", "delaying %s for %s" % (self.get_name(), logging_tools.get_plural("second", self.__actual_delay))])
                    mach_struct.log("delaying %s for %s" % (self.get_name(), logging_tools.get_plural("second", self.__actual_delay)))
                    self.delay_dict.setdefault(self.__actual_delay, []).append(mach_id)
                elif ip_list:
                    dev_already_locked = False
                    if mach_struct.get_lock(self.get_name()):
                        dev_already_locked = True
                        if mach_name not in dev_names_added:
                            mach_struct.log("... locked by %s" % (mach_struct.get_lock(self.get_name())),
                                            logging_tools.LOG_LEVEL_WARN)
                            self.__open_devs[mach_name] = ":".join(["e", "", "", "locked by %s" % (mach_struct.get_lock(self.get_name()))])
                        else:
                            dev_already_locked = False
                    else:
                        mach_struct.set_lock(self.get_name())
                        if hasattr(self, "pre_command"):
                            self.pre_command(mach_struct, self.queue_dict, init_dc)
                    # clear device
                    if not dev_already_locked:
                        dev_names_added.append(mach_name)
                        if self.__loc_config["VERBOSE"] > 0:
                            if self.send_command:
                                mach_struct.log("Sending command %s to %s (port %d)" % (self.real_command, ", ".join(ip_list), self.port))
                            if self.ping:
                                mach_struct.log("Sending ping to %s: %s" % (logging_tools.get_plural("IP", len(ip_list)),
                                                                            ", ".join(ip_list)))
                        for ip in ip_list:
                            # clear dev_name-ip state and sub-state
                            if self.send_command:
                                net_server.add_object(net_tools.tcp_con_object(self._new_tcp_con,
                                                                               connect_state_call=self._connect_state_call,
                                                                               connect_timeout_call=self._connect_timeout,
                                                                               target_host=ip,
                                                                               target_port=self.port,
                                                                               timeout=4,
                                                                               bind_retries=1,
                                                                               rebind_wait_time=1, add_data=(self.real_command, mach_struct)))
                                self.__connections_open += 1
                        if self.ping:
                            icmp_obj.add_icmp_client(net_tools.icmp_client(host_list=ip_list, num_ping=3, timeout=4, fast_mode=True, finish_call=self._icmp_finish, flood_ping=True, any_host_ok=True))
                self.post_call(mach_struct)
        self.__setup = False
        self._check_for_finished_req()
        self._handle_sql_requests(init_dc, net_server)
        init_dc.release()
    def _handle_sql_requests(self, init_dc, net_server):
        if self.needed_sql_fields:
            sql_str = "SELECT d.name, %s FROM device d WHERE %s" % (", ".join(["d.%s" % (x) for x in self.needed_sql_fields]),
                                                                    " OR ".join(["d.name='%s'" % (x) for x in self.__device_ids]))
            init_dc.execute(sql_str)
            for sql_rec in init_dc.fetchall():
                if self.ad_struct.has_key(sql_rec["name"]):
                    self.db_change_call(self.ad_struct[sql_rec["name"]], sql_rec)
    def _icmp_finish(self, icmp_obj):
        ping_res = icmp_obj.get_result()
        ping_is_main_command = (self.com_name == "ping")
        change_ips = [ping_ip for ping_ip, res in ping_res.iteritems() if type(res) == type({})]
        
        for change_ip in change_ips:
            self.__ip_results[change_ip]["icmp"] = (ping_res[change_ip]["received"] and "o" or "e", ping_res[change_ip])
        self._result_change(change_ips)
    def result_ok(self, dev_struct, state_str, in_data):
        dev_struct.log("ok result for command %s, %s, %s" % (self.com_name,
                                                             state_str,
                                                             logging_tools.get_plural("byte", len(in_data))))
        return state_str
    def result_warn(self, dev_struct, state_str):
        dev_struct.log("warn result for command %s, %s" % (self.com_name,
                                                           state_str),
                       logging_tools.LOG_LEVEL_WARN)
        return state_str
    def result_error(self, dev_struct, state_str):
        dev_struct.log("error result for command %s, %s" % (self.com_name,
                                                            state_str),
                       logging_tools.LOG_LEVEL_ERROR)
        return state_str
    def _result_error(self, dev_struct, ip, cause):
        # entry point from node_con_obj
        self.__ip_results[ip][self.port] = ("e", cause)
        self.__connections_open -= 1
        self._result_change([ip])
    def _result_ok(self, dev_struct, ip, what):
        # entry point from node_con_obj
        self.__connections_open -= 1
        self.__ip_results[ip][self.port] = ("o", what)
        self._result_change([ip])
    def _connect_timeout(self, sock):
        self.__connections_open -= 1
        self._result_error(sock.get_add_data()[1], sock.get_target_host(), "connect timeout")
        # remove references to command_class
        sock.delete()
        sock.close()
    def _connect_state_call(self, **args):
        if args["state"] == "error":
            self._result_error(args["socket"].get_add_data()[1], args["host"], "connect error")
            # remove references to command_class
            args["socket"].delete()
    def set_int_result(self, dev_struct, res_str):
        self.__open_devs[dev_struct.name] = res_str
        self._check_for_finished_req()
    def _result_change(self, ip_list):
        ids_to_check = frozenset(sum([self.__ip_mapping[ip] for ip in ip_list], []))
        devs_to_check = frozenset([self.__dev_id_mapping[id] for id in ids_to_check])
        #print "-" * 20, ip_list, ids_to_check, devs_to_check, "-" * 40
        for dev_name in [d_name for d_name in devs_to_check if not self.__open_devs[d_name]]:
            dev_struct = self.ad_struct[dev_name]
            num_ips = self.__num_ips[dev_name]
            ips_to_check = frozenset(sum([self.__inv_ip_mapping[id] for id in self.__inv_dev_mapping[dev_name]], []))
            ok_port_results    = dict(sum([[(ip, res_stuff) for res_port, (res_state, res_stuff) in self.__ip_results[ip].iteritems() if res_state == "o" and type(res_port) == type(0)] for ip in ips_to_check], []))
            error_port_results = dict(sum([[(ip, res_stuff) for res_port, (res_state, res_stuff) in self.__ip_results[ip].iteritems() if res_state == "e" and type(res_port) == type(0)] for ip in ips_to_check], []))
            ok_icmp_results    = dict(sum([[(ip, res_stuff) for res_port, (res_state, res_stuff) in self.__ip_results[ip].iteritems() if res_state == "o" and type(res_port) == type("")] for ip in ips_to_check], []))
            error_icmp_results = dict(sum([[(ip, res_stuff) for res_port, (res_state, res_stuff) in self.__ip_results[ip].iteritems() if res_state == "e" and type(res_port) == type("")] for ip in ips_to_check], []))
            state_str = ""
            if self.port:
                if ok_port_results:
                    ok_ip = ok_port_results.keys()[0]
                    ok_str = ok_port_results[ok_ip]
                    dev_struct.set_actual_ip(ok_ip)
                    state_str = ":".join(["o", ok_ip, dev_struct.get_act_net(), ok_str])
                elif len(error_port_results.keys()) == num_ips:
                    if self.ping:
                        if ok_icmp_results:
                            warn_ip = ok_icmp_results.keys()[0]
                            warn_dict = ok_icmp_results[warn_ip]
                            warn_str = "mean ping time %s" % (logging_tools.get_diff_time_str(warn_dict["mean_time"]))
                            dev_struct.set_actual_ip(warn_ip)
                            state_str = ":".join(["w", warn_ip, dev_struct.get_act_net(), warn_str])
                        elif len(error_icmp_results.keys()) == num_ips:
                            state_str = "e:::not reachable"
                            dev_struct.set_actual_ip()
                    else:
                        state_str = "e:::not reachable"
                        dev_struct.set_actual_ip()
            elif self.ping:
                if ok_icmp_results:
                    ok_ip = ok_icmp_results.keys()[0]
                    ok_dict = ok_icmp_results[ok_ip]
                    ok_str = "mean ping time %s" % (logging_tools.get_diff_time_str(ok_dict["mean_time"]))
                    dev_struct.set_actual_ip(ok_ip)
                    state_str = ":".join(["o", ok_ip, dev_struct.get_act_net(), ok_str])
                elif len(error_icmp_results.keys()) == num_ips:
                    state_str = "e:::not reachable"
                    dev_struct.set_actual_ip()
            if state_str:
                if state_str[0] == "o":
                    state_str = self.result_ok(dev_struct, state_str, ok_str)
                elif state_str[0] == "w":
                    state_str = self.result_warn(dev_struct, state_str)
                else:
                    state_str = self.result_error(dev_struct, state_str)
                recv_state, req_state = dev_struct.get_recv_req_state()
                dev_struct.release_lock(self.get_name())
                self.__open_devs[dev_name] = {"state"      : state_str,
                                              "recv_state" : recv_state,
                                              "req_state"  : req_state}
                self._check_for_finished_req()
    def _check_for_finished_req(self):
        if not self.__setup and not [True for val in self.__open_devs.itervalues() if not val]:
            #print "DONE", self
            # finished, phew...
            for mach in self.__device_ids:
                if self.__dev_id_mapping[mach] and self.ad_struct.has_key(self.__dev_id_mapping[mach]):
                    act_res = self.__open_devs[self.__dev_id_mapping[mach]]
                    if type(act_res) == type(""):
                        self.set_node_result(mach, act_res)
                    else:
                        self.set_node_result(mach, act_res["state"], {"recv_state" : act_res["recv_state"],
                                                                      "req_state"  : act_res["req_state"]})
                        
                else:
                    self.set_node_result(mach, "error Key not found")
    def set_node_result(self, n_name, node_result, node_opt=None):
        self.__node_result_dict[n_name] = node_result
        if node_opt is not None:
            self.__node_opt_dict[n_name] = node_opt
        self.__devs_pending -= 1
        if not self.__devs_pending:
            ret_queue = self.srv_com.get_queue()
            if ret_queue:
                srv_reply = server_command.server_reply()
                srv_reply.set_ok_result("ok")
                srv_reply.set_node_results(self.__node_result_dict)
                srv_reply.set_node_dicts(self.__node_opt_dict)
                ret_queue.put(("result_ready", (self.srv_com, srv_reply)))
            # delete myself
            del self
    def _new_tcp_con(self, sock):
        return node_con_obj(self, sock.get_target_host(), sock.get_add_data())
    def set_needed_sql_fields(self, field=[]):
        if type(field) != type([]):
            field = [field]
        self.__needed_sql_fields = field
    def get_name(self):
        return self.com_name
    def add_dev_mapping(self, dev_id, dev_name, ip_list):
        # add device mapping, we only contact devices specified in ip_list
        if not self.__open_devs.has_key(dev_name):
            self.__inv_dev_mapping[dev_name] = []
            self.__open_devs[dev_name] = ""
            self.__num_ips[dev_name] = len(ip_list)
        for ip in ip_list:
            self.__ip_mapping.setdefault(ip, []).append(dev_id)
            self.__inv_ip_mapping.setdefault(dev_id, []).append(ip)
            self.__ip_results[ip] = {}
        self.__inv_dev_mapping[dev_name].append(dev_id)
        self.__dev_id_mapping[dev_id] = dev_name
    def set_dev_state(self, dev_name, state = "error not set"):
        # sets the device state to a given string
        self.__dev_states[dev_name] = state
    def __repr__(self):
        return "deprecated"

class ping_command(command_class):
    def __init__(self):
        command_class.__init__(self, "ping", ping=True, broadcast=True)
        
class status_command(command_class):
    def __init__(self):
        command_class.__init__(self, "status", ping=True, port=2002, send_command=True)
    def result_ok(self, dev_struct, state_str, in_data):
        dev_struct.set_req_state(state_str,
                                 self.queue_dict["sql_queue"])
        return state_str
    def result_warn(self, dev_struct, state_str):
        dev_struct.set_req_state(state_str,
                                 self.queue_dict["sql_queue"])
        return state_str
    def result_error(self, dev_struct, state_str):
        dev_struct.set_req_state(state_str,
                                 self.queue_dict["sql_queue"])
        return state_str

# the difference between reboot and reboot_nd is that if you call reboot (without _nd) with many nodes the reboot
# sequence will be delayed for certain nodes (to reduce the load imposed to the server)
class reboot_command(command_class):
    def __init__(self):
        command_class.__init__(self, "reboot", port=2002, send_command=True, parallel_throttling=True)

class halt_command(command_class):
    def __init__(self):
        command_class.__init__(self, "halt", port=2002, send_command=True)

class poweroff_command(command_class):
    def __init__(self):
        command_class.__init__(self, "poweroff", port=2002, send_command=True)

class reboot_nd_command(command_class):
    def __init__(self):
        command_class.__init__(self, "reboot_nd", port=2002, send_command=True)

class refresh_hwi_command(command_class):
    def __init__(self):
        command_class.__init__(self, "refresh_hwi", port=2001, send_command=True, real_command="hwinfo --raw")
    def pre_command(self, mach_struct, q_dict, dc):
        mach_struct.clear_hardware_info(dc)
    def result_ok(self, dev_struct, state_str, in_data):
        dev_struct.clear_hwi_delay_counter()
        loc_error, ret_str, mac_change = dev_struct.insert_hardware_info(self.dc, in_data, self.queue_dict["sql_queue"])
        state_split = state_str.split(":")[:3]
        state_split.append(ret_str)
        return ":".join(state_split)
##         self.set_dev_ip_state(dev_struct.name, ip, 1)
##         if loc_error:
##             self.set_dev_state(dev_struct.name, "error %s" % (ret_str))
##         else:
##             self.set_dev_state(dev_struct.name, "%s" % (ret_str))
##         if loc_error:
##         if mac_change:
##             mach_struct.log("%s has been changed, trying to restart network on target node" % (logging_tools.get_plural("MAC Address", mac_change)))
##             server_com = server_command.srv_com(command="resync_config", nodes=[mach_name])
##             own_queue.put(("R", server_com))
    def result_error(self, dev_struct, cause):
        dev_struct.log("connect error for refresh_hwi", logging_tools.LOG_LEVEL_WARN)
        if not self.srv_com.get_queue():
            # not return queue specified, try it again
            if dev_struct.get_hwi_delay_counter() > 10:
                dev_struct.log("hwi_delay_counter > 10, giving up", logging_tools.LOG_LEVEL_ERROR)
                dev_struct.clear_hwi_delay_counter()
            else:
                dev_struct.incr_hwi_delay_counter()
                dev_struct.log("trying again after 5 seconds, sending again",
                               logging_tools.LOG_LEVEL_WARN)
                self.queue_dict["log_queue"].put(("delay_request", (self.queue_dict["control_queue"], ("server_com", server_command.server_command(command="refresh_hwi", nodes=[dev_struct.name])), 5)))

class fetch_network_info_command(command_class):
    def __init__(self):
        command_class.__init__(self, "fetch_network_info", port=2001, send_command=True, real_command="network_info --raw")
    def pre_command(self, mach_struct, q_dict, dc):
        mach_struct.clear_hardware_info(dc)
    def result_ok(self, dev_struct, state_str, in_data):
        dev_struct.clear_hwi_delay_counter()
        loc_error, ret_str = dev_struct.insert_network_info(self.dc, in_data, self.queue_dict["sql_queue"])
        return ret_str
        state_split = state_str.split(":")[:3]
        state_split.append(ret_str)
        return ":".join(state_split)
    def result_error(self, dev_struct, cause):
        dev_struct.log("connect error for fetch_network_info", logging_tools.LOG_LEVEL_WARN)

class readdots_command(command_class):
    def __init__(self):
        command_class.__init__(self, "readdots")
    def post_call(self, mach_struct):
        self.queue_dict["config_queue"].put(("readdots", (mach_struct.name, self)))

class device_mode_change_command(command_class):
    def __init__(self):
        command_class.__init__(self, "device_mode_change", needed_sql_fields=["device_mode"])
    def db_change_call(self, mach_struct, db_s):
        mach_struct.set_device_mode(db_s["device_mode"])
    def post_call(self, mach_struct):
        log_str = "checked for device_mode change"
        mach_struct.log(log_str)
        self.set_int_result(mach_struct, "changed device_mode")
        #self.set_dev_state(mach_name, log_str)
        #print "***"
        #mach_struct.release_lock(self.get_name())

class refresh_tk_command(command_class):
    def __init__(self):
        command_class.__init__(self, "refresh_tk")
    def post_call(self, mach_struct):
        self.queue_dict["config_queue"].put(("refresh_tk", (mach_struct.name, self)))

class remove_bs_command(command_class):
    def __init__(self):
        command_class.__init__(self, "remove_bs")
    def post_call(self, mach_struct):
        log_str = "changed bootserver (removed from me)"
        mach_struct.log(log_str)
        self.set_node_result(mach_struct.name, "ok got it")
        mach_struct.release_lock(self.get_name())
        self.queue_dict["log_queue"].put(("remove_handle", mach_struct.name))
        del self.ad_struct[mach_struct.name]
        del mach_struct

class new_bs_command(command_class):
    def __init__(self):
        command_class.__init__(self, "new_bs")
    def post_call(self, mach_struct):
        log_str = "changed bootserver (i am the new one)"
        mach_struct.check_network_settings(self.dc)
        mach_struct.log(log_str)
        self.queue_dict["config_queue"].put(("refresh_all", (mach_struct.name, None)))
        self.set_node_result(mach_struct.name, "ok got it")
        # set internal result ?

class ip_changed_command(command_class):
    def __init__(self):
        command_class.__init__(self, "ip_changed")
    def post_call(self, mach_struct):
        log_str = "checking IP addresses"
        mach_struct.check_network_settings(self.dc)
        mach_struct.log(log_str)
        self.queue_dict["config_queue"].put(("refresh_all", (mach_struct.name, None)))
        self.queue_dict["dhcp_queue"].put(("server_com", server_command.server_command(command="alter_macadr", nodes=[mach_struct.name])))
        self.set_node_result(mach_struct.name, "ok changed")

class apc_com_command(command_class):
    def __init__(self):
        command_class.__init__(self, "apc_com")
    def post_call(self, mach_struct):
        self.queue_dict["command_queue"].put(("snmp_command", ("apc_com_command", self, server_command.server_command(command="apc_com", nodes=[mach_struct.name], node_commands=self.srv_com.get_node_commands()))))

class apc_dev_command(command_class):
    def __init__(self):
        command_class.__init__(self, "apc_dev")
    def post_call(self, mach_struct):
        add_args = self.srv_com.get_node_command(mach_struct.name).split(",")
        log_str = ""
        if add_args:
            if add_args[0] in ["on", "off", "reboot"]:
                self.dc.execute("SELECT d2.name, ms.outlet, i.ip FROM device d INNER JOIN msoutlet ms INNER JOIN netdevice nd INNER JOIN netip i LEFT JOIN device d2 ON d2.device_idx = ms.device WHERE ms.slave_device=d.device_idx AND nd.device=d2.device_idx AND i.netdevice=nd.netdevice_idx AND d.name='%s'" % (mach_struct.name))
                all_apc_cons = self.dc.fetchall()
                if all_apc_cons:
                    act_con = all_apc_cons[0]
                    mach_struct.log("sending snmp_command (device %s, outlet %d)" % (act_con["name"],
                                                                                     act_con["outlet"]))
                    self.queue_dict["command_queue"].put(("snmp_command", ("apc_dev_command", None, server_command.server_command(command="apc_com",
                                                                                                                                  nodes=[act_con["name"]],
                                                                                                                                  node_commands={act_con["name"] : "c%d=%d" % (act_con["outlet"],
                                                                                                                                                                               {"on"     : 1,
                                                                                                                                                                                "off"    : 2,
                                                                                                                                                                                "reboot" : 3}[add_args[0]])}))))
                else:
                    log_str = "no apc connected"
            else:
                log_str = "Unknown %s command '%s'" % (self.get_name(), add_args[0])
        else:
            log_str = "Need command for %s" % (self.get_name())
        if log_str:
            mach_struct.log(log_str)
            self.set_node_result(mach_struct.name, log_str)
            #self.set_dev_ip_state(mach_struct.name, ip, 1)
            #self.set_dev_state(mach_struct.name, log_str)
            mach_struct.release_lock(self.get_name())
        else:
            self.set_node_result(mach_struct.name, "ok done")

class control_thread(threading_tools.thread_obj):
    def __init__(self, glob_config, loc_config, db_con, log_queue):
        self.__db_con = db_con
        self.__log_queue = log_queue
        self.__glob_config, self.__loc_config = (glob_config, loc_config)
        threading_tools.thread_obj.__init__(self, "control", queue_size=100)
        self.register_func("set_queue_dict", self._set_queue_dict)
        self.register_func("set_ad_struct", self._set_ad_struct)
        self.register_func("set_net_stuff", self._set_net_stuff)
        self.register_func("update", self._update)
        self.register_func("server_com", self._server_com)
        self.register_func("node_con", self._node_con)
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__log_queue.put(("log", (self.name, what, lev)))
    def _set_net_stuff(self, (ns, icmp_obj)):
        self.__net_server, self.__icmp_obj = (ns, icmp_obj)
    def _set_ad_struct(self, ad_struct):
        self.log("got ad_struct")
        self.__ad_struct = ad_struct
        self.__devices_to_monitor = []
        self._init_devices_to_monitor()
    def _init_devices_to_monitor(self):
        dtm = sorted([k for k, v in self.__ad_struct.iteritems() if v.get_device_mode() if not self.__ad_struct.is_an_ip(k)])
        if self.__devices_to_monitor != dtm:
            self.__devices_to_monitor = dtm
            if self.__devices_to_monitor:
                self.log("%s to monitor: %s" % (logging_tools.get_plural("device", len(self.__devices_to_monitor)),
                                                logging_tools.compress_list(self.__devices_to_monitor)))
            else:
                self.log("no devices to monitor")
    def thread_running(self):
        self.send_pool_message(("new_pid", (self.name, self.pid)))
        self.__dc = self.__db_con.get_connection(SQL_ACCESS)
        # command dictionary
        # port ....... port to connect to (-1 for no host connection, 0 for ping)
        # add_ping ... adds a sub-ping to the command (for example status)
        # ct ......... identifier of a thread to signal
        # delay ...... delays the request for some nodes

        # build valid_command_list
        self.__valid_commands = []
        # commands where something is sent to the device
        self.__send_commands = []
        # commands which are server-local
        self.__no_send_commands = []
        for name in [x for x in globals().keys() if x.endswith("_command")]:
            obj = globals()[name]
            if "link_objects" in dir(obj):
                act_com = name[:-8]
                self.__valid_commands.append(act_com)
                test_com = globals()[name]()
                if test_com.send_command:
                    self.__send_commands.append(act_com)
                else:
                    self.__no_send_commands.append(act_com)
                del test_com
        self.__valid_commands.sort()
        self.__send_commands.sort()
        self.__no_send_commands.sort()
        self.log("valid commands   (%2d) : %s" % (len(self.__valid_commands),   ", ".join(self.__valid_commands)  ))
        self.log("no_send_commands (%2d) : %s" % (len(self.__no_send_commands), ", ".join(self.__no_send_commands)))
        self.log("send_commands    (%2d) : %s" % (len(self.__send_commands),    ", ".join(self.__send_commands)   ))
        self.__devices_to_monitor = []
        self.__dc.release()
    def _set_queue_dict(self, q_dict):
        self.__queue_dict = q_dict
    def _update(self):
        if self.__devices_to_monitor:
            act_time = time.time()
            # build accurate ping_list and reboot_dict
            ping_list, reboot_dict = ([], {})
            rb_type_dict = {1 : "reboot (software)",
                            2 : "reboot (hardware)"}
            for dev_name in self.__devices_to_monitor:
                if self.__ad_struct.has_key(dev_name):
                    dev_struct = self.__ad_struct[dev_name]
                    if dev_struct.get_device_mode():
                        if abs(dev_struct.get_last_ip_set() - act_time) >= self.__glob_config["DEVICE_MONITOR_TIME"]:
                            ping_list.append(dev_name)
                        if dev_struct.get_last_ip_ok_set() and \
                               abs(dev_struct.get_last_ip_ok_set() - act_time) >= self.__glob_config["DEVICE_REBOOT_TIME"] and \
                               abs(dev_struct.get_last_reset_time() - act_time) >= self.__glob_config["DEVICE_REBOOT_TIME"]:
                            dev_struct.set_last_reset_time()
                            reboot_dict.setdefault(dev_struct.get_device_mode(), []).append(dev_name)
                            dev_struct.device_log_entry(0,
                                                        "w",
                                                        "doing a %s (not reachable for %d seconds)" % (rb_type_dict[dev_struct.get_device_mode()],
                                                                                                       abs(dev_struct.get_last_ip_ok_set() - act_time)),
                                                        self.__queue_dict["sql_queue"],
                                                        self.__loc_config["LOG_SOURCE_IDX"])
            if ping_list:
                ping_list.sort()
                self.log("<devicemonitor> Sending ping to %s: %s" % (logging_tools.get_plural("device", len(ping_list)),
                                                                     logging_tools.compress_list(ping_list)))
                self.get_thread_queue().put(("server_com", server_command.server_command(command="ping", nodes=ping_list)))
            for rb_type, rb_list in reboot_dict.iteritems():
                self.log("<devicemonitor> Doing a %s on %s: %s" % (rb_type_dict[rb_type],
                                                                   logging_tools.get_plural("device", len(rb_list)),
                                                                   logging_tools.compress_list(rb_list)))
                if rb_type == 1:
                    self.get_thread_queue().put(("server_com", server_command.server_command(command="reboot", nodes=rb_list)))
                else:
                    self.get_thread_queue().put(("server_com", server_command.server_command(command="apc_dev", nodes=rb_list, node_commands=dict([(k, "reboot") for k in rb_list]))))
    def _server_com(self, srv_com):
        command = srv_com.get_command()
        # check for delay
        if command in self.__valid_commands:
            # init pending request
            #new_pr = pending_request(srv_com, command, self.__log_queue)
            new_com = globals()["%s_command" % (command)]()
            # iterate over devices
            self.log("got command %s for %s: %s" % (command,
                                                    logging_tools.get_plural("node", len(srv_com.get_nodes())),
                                                    logging_tools.compress_list(srv_com.get_nodes())))
            new_com.link_objects(srv_com, self.__net_server, self.__icmp_obj, self.__ad_struct, self.__queue_dict, self.__db_con, self.__glob_config, self.__loc_config)
            self._init_devices_to_monitor()
##             new_devices_to_monitor = [k for k, v in devname_dict.iteritems() if v.get_device_mode()]
##             new_devices_to_monitor.sort()
##             if devices_to_monitor != new_devices_to_monitor:
##                 devices_to_monitor = new_devices_to_monitor
##                 if devices_to_monitor:
##                     log_queue.put(("L", (my_name, "%s to monitor: %s" % (logging_tools.get_plural("device", len(devices_to_monitor)),
##                                                                          logging_tools.compress_list(devices_to_monitor)))))
##                 else:
##                     log_queue.put(("L", (my_name, "no devices to monitor")))
            for delay, mach_list in new_com.delay_dict.iteritems():
                self.log("Delaying reboot for %s for %d seconds: %s" % (logging_tools.get_plural("device", len(mach_list)),
                                                                        delay,
                                                                        ", ".join(mach_list)))
                delayed_srv_com = server_command.server_command(command="reboot_nd", nodes=mach_list)
                self.__log_queue.put(("delay_request", (self.get_thread_queue(), ("server_com", delayed_srv_com), delay)))
        else:
            self.log("Unknown command %s" % (command), logging_tools.LOG_LEVEL_WARN)
            if srv_com.get_queue():
                res_com = server_command.server_reply()
                res_com.set_error_result("unrecognized command %s" % (command))
                srv_com.get_queue().put(("result_ready", (srv_com, res_com)))
    def _node_con(self, tcp_obj):
        in_data = tcp_obj.get_decoded_in_str()
        src_ip = tcp_obj.get_src_host()
        if self.__ad_struct.has_key(src_ip):
            tcp_obj.add_to_out_buffer("Processed request from ip %s" % (src_ip))
            dev_struct = self.__ad_struct[src_ip]
            dev_struct.log("Got request %s from ip %s" % (in_data, src_ip))
            act_time = time.time()
            # interpret in_string
            write_recvstate = True
            if in_data.startswith("mother connection"):
                self.__dc.execute("UPDATE device SET last_boot='%s' WHERE name='%s'" % (time.ctime(act_time), dev_struct.name))
                dev_struct.clear_hardware_info(self.__dc)
            elif in_data.startswith("boot "):
                dev_struct.device_log_entry(1,
                                            "i",
                                            in_data,
                                            self.__queue_dict["sql_queue"],
                                            self.__loc_config["NODE_SOURCE_IDX"])
            elif in_data.startswith("starting"):
                startmesp = in_data.split()
                dev_struct.device_log_entry(2,
                                            "i",
                                            "start %s" % (" ".join(startmesp[1:])),
                                            self.__queue_dict["sql_queue"],
                                            self.__loc_config["NODE_SOURCE_IDX"])
            elif in_data.startswith("down to runlevel"):
                downmesp = in_data.split()
                if len(downmesp) == 4:
                    try:
                        trunlevel = int(downmesp[3])
                    except:
                        dev_struct.log("parsing runlevel '%s'" % (downmesp[3]), logging_tools.LOG_LEVEL_ERROR)
                    else:
                        if trunlevel == 6:
                            dev_struct.device_log_entry(3,
                                                        "i",
                                                        "reboot",
                                                        self.__queue_dict["sql_queue"],
                                                        self.__loc_config["NODE_SOURCE_IDX"])
                        elif trunlevel == 0:
                            dev_struct.device_log_entry(4,
                                                        "i",
                                                        "halt",
                                                        self.__queue_dict["sql_queue"],
                                                        self.__loc_config["NODE_SOURCE_IDX"])
                else:
                    dev_struct.log("error runlevel string has wrong format (need 4 parts): '%s'" % (in_data), logging_tools.LOG_LEVEL_ERROR)
            elif in_data.startswith("up to runlevel"):
                dev_struct.log("got 'up to runlevel' string, requesting hardware-info")
                self.get_thread_queue().put(("server_com", server_command.server_command(command="refresh_hwi", nodes=[src_ip])))
            elif in_data == "start syslog":
                dev_struct.log("node restart_syslog")
            elif in_data.startswith("installing new kernel"):
                self.__dc.execute("UPDATE device SET last_kernel='%s' WHERE name='%s'" % (time.ctime(act_time), dev_struct.name))
            elif in_data == "installing":
                self.__dc.execute("UPDATE device SET last_install='%s' WHERE name='%s'" % (time.ctime(act_time), dev_struct.name))
            elif in_data.startswith("*"):
                write_recvstate = False
                dev_struct.parse_received_str(in_data[1:], self.__dc, self.__queue_dict["sql_queue"], self.__loc_config["NODE_SOURCE_IDX"])
            if write_recvstate:
                dev_struct.set_recv_state("%s (%s)" % (in_data.strip(), dev_struct.get_act_net()), self.__queue_dict["sql_queue"])
        else:
            tcp_obj.add_to_out_buffer("Invalid source ip %s" % (src_ip))
            self.log("Got invalid request from ip %s: %s" % (src_ip, in_data), logging_tools.LOG_LEVEL_WARN)

class logging_thread(threading_tools.thread_obj):
    def __init__(self, glob_config, loc_config):
        self.__sep_str = "-" * 50
        self.__glob_config, self.__loc_config = (glob_config, loc_config)
        self.__machlogs, self.__glob_log, self.__glob_cache = ({}, None, [])
        threading_tools.thread_obj.__init__(self, "logging", queue_size=100, priority=10)
        self.register_func("log", self._log)
        self.register_func("mach_log", self._mach_log)
        self.register_func("syslog_dhcp", self._syslog_dhcp)
        self.register_func("set_ad_struct", self._set_ad_struct)
        self.register_func("set_queue_dict", self._set_queue_dict)
        self.register_func("update", self._update)
        self.register_func("delay_request", self._delay_request)
        self.register_func("remove_handle", self._remove_handle)
        self.__ad_struct = {}
        self._build_regexp()
    def thread_running(self):
        self.send_pool_message(("new_pid", (self.name, self.pid)))
        root = self.__glob_config["LOG_DIR"]
        if not os.path.exists(root):
            os.makedirs(root)
        glog_name = "%s/log" % (root)
        self.__glob_log = logging_tools.logfile(glog_name)
        self.__glob_log.write(self.__sep_str)
        self.__glob_log.write("Opening log")
        # array of delay-requests
        self.__delay_array = []
    def _delay_request(self, (target_queue, arg, delay)):
        self.log("append to delay_array (delay=%s)" % (logging_tools.get_plural("second", delay)))
        self.__delay_array.append((target_queue, arg, time.time() + delay))
    def _update(self):
        # handle delay-requests
        act_time = time.time()
        new_d_array = []
        for target_queue, arg, r_time in self.__delay_array:
            if r_time < act_time:
                self.log("sending delayed object")
                target_queue.put(arg)
            else:
                new_d_array.append((target_queue, arg, r_time))
        self.__delay_array = new_d_array
    def _set_ad_struct(self, ad_struct):
        self.log("got ad_struct")
        self.__ad_struct = ad_struct
    def _set_queue_dict(self, q_dict):
        self.__dhcp_queue = q_dict["dhcp_queue"]
    def loop_end(self):
        for mach in self.__machlogs.keys():
            self.__machlogs[mach].write("Closing log")
            self.__machlogs[mach].close()
        self.__glob_log.write("Closed %s" % (logging_tools.get_plural("machine log", len(self.__machlogs.keys()))))
        self.__glob_log.write("Closing log")
        self.__glob_log.write("logging thread exiting (pid %d)" % (self.pid))
        self.__glob_log.close()
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self._mach_log((self.name, what, lev, ""))
    def _log(self, (s_thread, what, lev)):
        self._mach_log((s_thread, what, lev, ""))
    def _mach_log(self, (s_thread, what, lev, mach)):
        if mach == "":
            handle, pre_str = (self.__glob_log, "")
        else:
            handle, pre_str = self._get_handle(mach)
        if handle is None:
            self.__glob_cache.append((s_thread, what, lev, mach))
        else:
            log_act = []
            if self.__glob_cache:
                for c_s_thread, c_what, c_lev, c_mach in self.__glob_cache:
                    c_handle, c_pre_str = self._get_handle(c_mach)
                    self._handle_log(c_handle, c_s_thread, c_pre_str, c_what, c_lev, c_mach)
                self.__glob_cache = []
            self._handle_log(handle, s_thread, pre_str, what, lev, mach)
    def _handle_log(self, handle, s_thread, pre_str, what, lev, mach):
        handle.write("%-5s(%s) : %s%s" % (logging_tools.get_log_level_str(lev),
                                          s_thread,
                                          pre_str,
                                          what))
    def _build_regexp(self):
        sys.path.append("/usr/local/sbin")
        log_lines, sys_dict = process_tools.fetch_sysinfo()
        # determine correct regexp
        if sys_dict["version"] in ["8.0", "8.1"] and sys_dict["vendor"] != "redhat":
            self.log("System Version is < SUSE 8.2, using non-standard regexp for syslog-ng messages")
            self.__line_re = re.compile("^\<\d+\>(?P<time>\S+\s+\S+\s+\S+)\s+(?P<facility>\S+):\s+(?P<message>.*)$")
        else:
            self.log("System Version is >= SUSE 8.2 or RedHat, using standard regexp for syslog-ng messages")
            self.__line_re = re.compile("^\<\d+\>(?P<time>\S+\s+\S+\s+\S+)\s+(?P<host>\S+)\s+(?P<facility>\S+):\s+(?P<message>.*)$")
        self.__dhcp_discover = re.compile("^DHCPDISCOVER from (?P<macaddr>\S+) via .*$")
        self.__dhcp_offer    = re.compile("^DHCPOFFER on (?P<ip>\S+) to (?P<macaddr>\S+) via .*$")
        self.__dhcp_request  = re.compile("^DHCPREQUEST for (?P<ip>\S+) .*from (?P<macaddr>\S+) via .*$")
        self.__dhcp_answer   = re.compile("^DHCPACK on (?P<ip>\S+) to (?P<macaddr>\S+) via .*$")
    def _remove_handle(self, name):
        self.log("Closing log for device %s" % (name))
        self._mach_log((self.name, "(%s) : Closing log" % (self.name), logging_tools.LOG_LEVEL_OK, name))
        self.__machlogs[name].close()
        del self.__machlogs[name]
    def _get_handle(self, name):
        devname_dict = {}
        if self.__machlogs.has_key(name):
            handle, pre_str = (self.__machlogs[name], "")
        else:
            if self.__ad_struct.has_key(name):
                mach = self.__ad_struct[name]
                name = mach.name
                machdir = "%s/%s" % (self.__glob_config["LOG_DIR"], name)
                if not os.path.exists(machdir):
                    self.log("Creating dir %s for %s" % (machdir, name))
                    os.makedirs(machdir)
                self.__machlogs[name] = logging_tools.logfile("%s/log" % (machdir))
                self.__machlogs[name].write(self.__sep_str)
                self.__machlogs[name].write("Opening log")
                #glog.write("# of open machine logs: %d" % (len(self.__machlogs.keys())))
                handle, pre_str = (self.__machlogs[name], "")
            else:
                handle, pre_str = (self.__glob_log, "device %s: " % (name))
        return (handle, pre_str)
    def _syslog_dhcp(self, in_line):
        in_line = in_line.strip()
        line_m = self.__line_re.match(in_line)
        if line_m:
            mess_str = line_m.group("message").strip()
            if line_m.group("facility") == "dhcpd":
                for line in [y.strip() for y in in_line.split("\n") if y.strip()]:
                    self.log("got line %s from dhcp-server" % (line))
                for prefix, regexp in [("DISCOVER", self.__dhcp_discover),
                                       ("OFFER"   , self.__dhcp_offer),
                                       ("REQUEST" , self.__dhcp_request),
                                       ("ACK"     , self.__dhcp_answer)]:
                    dhcp_s = regexp.match(mess_str)
                    if dhcp_s:
                        if prefix == "DISCOVER":
                            ip = "---"
                        else:
                            ip = dhcp_s.group("ip")
                        server_com = server_command.server_command(command="syslog_line")
                        server_com.set_option_dict({"sm_type" : prefix,
                                                    "ip"      : ip,
                                                    "mac"     : dhcp_s.group("macaddr"),
                                                    "message" : mess_str})
                        self.__dhcp_queue.put(("server_com", server_com))
                        break
                else:
                    self.log("cannot parse line (match) '%s'" % (in_line), logging_tools.LOG_LEVEL_WARN)
            else:
                if in_line.count("syslog-thread-test"):
                    # string from logcheck-server, ignore
                    pass
                else:
                    self.log("cannot parse line (facility) '%s'" % (in_line), logging_tools.LOG_LEVEL_WARN)
        else:
            self.log("cannot parse line (general) '%s'" % (in_line), logging_tools.LOG_LEVEL_WARN)
        
def get_kernel_stuff(dc, glob_config, k_n, k_idx):
    if glob_config["PREFER_KERNEL_NAME"]:
        dc.execute("SELECT k.* FROM kernel k WHERE k.name=%s", (k_n))
    else:
        dc.execute("SELECT k.* FROM kernel k WHERE k.kernel_idx=%d" % (k_idx))
    if dc.rowcount:
        rk_n = dc.fetchone()
    else:
        rk_n = None
    return rk_n

class command_thread(threading_tools.thread_obj):
    def __init__(self, glob_config, loc_config, db_con, log_queue):
        """thread responsible for the receiving command and snmp dispathcer"""
        self.__db_con = db_con
        self.__log_queue = log_queue
        self.__glob_config, self.__loc_config = (glob_config, loc_config)
        threading_tools.thread_obj.__init__(self, "command", queue_size=200)
        self.register_func("in_bytes", self._in_bytes)
        self.register_func("set_queue_dict", self._set_queue_dict)
        self.register_func("result_ready", self._result_ready)
        self.register_func("set_ad_struct", self._set_ad_struct)
        self.register_func("snmp_command", self._snmp_command)
        self.register_func("snmp_command_low_level", self._snmp_command_low_level)
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__log_queue.put(("log", (self.name, what, lev)))
    def thread_running(self):
        self.send_pool_message(("new_pid", (self.name, self.pid)))
    def _set_ad_struct(self, ad_struct):
        self.log("got ad_struct")
        self.__ad_struct = ad_struct
    def _set_queue_dict(self, q_dict):
        self.__queue_dict = q_dict
    def _in_bytes(self, tcp_obj):
        in_data = tcp_obj.get_decoded_in_str()
        try:
            server_com = server_command.server_command(in_data)
        except:
            tcp_obj.add_to_out_buffer("no valid server_command")
            self.log("Got invalid data (no server_command) from host %s (port %d): %s" % (tcp_obj.get_src_host(),
                                                                                          tcp_obj.get_src_port(),
                                                                                          process_tools.get_except_info()),
                     logging_tools.LOG_LEVEL_WARN)
        else:
            srv_com_name = server_com.get_command()
            if srv_com_name in kernel_sync_tools.KNOWN_KERNEL_SYNC_COMMANDS:
                call_func = self._handle_kernel_req
            else:
                call_func = {"status"                 : self._status,
                             "alter_macadr"           : self._handle_macadr,
                             "write_macadr"           : self._handle_macadr,
                             "delete_macadr"          : self._handle_macadr,
                             "reboot"                 : self._handle_control_req,
                             "reboot_nd"              : self._handle_control_req,
                             "halt"                   : self._handle_control_req,
                             "ping"                   : self._handle_control_req,
                             "refresh_tk"             : self._handle_control_req,
                             "readdots"               : self._handle_control_req,
                             "refresh_hwi"            : self._handle_control_req,
                             "fetch_network_info"     : self._handle_control_req,
                             "apc_dev"                : self._handle_control_req,
                             "apc_dev2"               : self._handle_control_req,
                             "apc_com"                : self._handle_control_req,
                             "poweroff"               : self._handle_control_req,
                             "remove_bs"              : self._handle_control_req,
                             "new_bs"                 : self._handle_control_req,
                             "propagate"              : self._handle_control_req,
                             "ip_changed"             : self._handle_control_req,
                             "device_mode_change"     : self._handle_control_req,
                             "hopcount_table_changed" : self._hopcount_table_changed}.get(srv_com_name, None)
            if call_func:
                call_func(tcp_obj, server_com)
            else:
                self.log("Got unknown server_command '%s' from host %s (port %d)" % (srv_com_name,
                                                                                     tcp_obj.get_src_host(),
                                                                                     tcp_obj.get_src_port()),
                         logging_tools.LOG_LEVEL_WARN)
                res_str = "unknown command %s" % (srv_com_name)
                tcp_obj.add_to_out_buffer(server_command.server_reply(state=server_command.SRV_REPLY_STATE_ERROR, result=res_str),
                                          res_str)
    def _result_ready(self, (srv_com, srv_reply)):
        tcp_obj = srv_com.get_key()
        tcp_obj.add_to_out_buffer(srv_reply, "%s for %s: %s" % (srv_com.get_command(),
                                                                logging_tools.get_plural("device", len(srv_com.get_nodes())),
                                                                logging_tools.compress_list(srv_com.get_nodes()) or "NONE"))
    def _handle_control_req(self, tcp_obj, srv_com):
        srv_com.set_queue(self.get_thread_queue())
        # missuse of key
        srv_com.set_key(tcp_obj)
        self.__queue_dict["control_queue"].put(("server_com", srv_com))
    def _status(self, tcp_obj, s_com):
        if s_com.get_nodes():
            # node status
            self._handle_control_req(tcp_obj, s_com)
        else:
            tp = self.get_thread_pool()
            num_threads, num_ok = (tp.num_threads(False),
                                   tp.num_threads_running(False))
            if num_ok == num_threads:
                ret_str = "OK: all %d threads running, version %s" % (num_ok, self.__loc_config["VERSION_STRING"])
            else:
                ret_str = "ERROR: only %d of %d threads running, version %s" % (num_ok, num_threads, self.__loc_config["VERSION_STRING"])
            server_reply = server_command.server_reply()
            server_reply.set_ok_result(ret_str)
            tcp_obj.add_to_out_buffer(server_reply, "status")
    def _handle_macadr(self, tcp_obj, srv_com):
        srv_com.set_queue(self.get_thread_queue())
        srv_com.set_key(tcp_obj)
        self.__queue_dict["dhcp_queue"].put(("server_com", srv_com))
    def _handle_kernel_req(self, tcp_obj, srv_com):
        srv_com.set_queue(self.get_thread_queue())
        srv_com.set_key(tcp_obj)
        self.__queue_dict["kernel_queue"].put((srv_com.get_command(), srv_com))
    def _hopcount_table_changed(self, tcp_obj, srv_com):
        all_nodes = sorted([x for x in self.__ad_struct.keys() if not self.__ad_struct.is_an_ip(x)])
        self.log("hopcount_table_changed, working on %s: %s" % (logging_tools.get_plural("node", len(all_nodes)),
                                                                logging_tools.compress_list(all_nodes)))
        srv_reply = server_command.server_reply()
        srv_reply.set_ok_result("ok ack")
        tcp_obj.add_to_out_buffer(srv_reply, "ack")
        self.__queue_dict["control_queue"].put(("server_com", server_command.server_command(command = "ip_changed", nodes=all_nodes)))
    def _snmp_command(self, (com_source, int_com, srv_com)):
        dev_struct = self.__ad_struct[srv_com.get_nodes()[0]]
        snmp_com = srv_com.get_node_commands()[dev_struct.name]
        if not dev_struct.ip_dict:
            dev_struct.log("no ip found for snmp_command %s" % (snmp_com), logging_tools.LOG_LEVEL_ERROR)
            dev_struct.release_lock(int_com.com_name)
            int_com.set_node_result(dev_struct.name, "error no ip found for snmp_command '%s'" % (snmp_com))
        else:
            dc = self.__db_con.get_connection(SQL_ACCESS)
            error, add_snmp_coms = dev_struct.build_snmp_commands(snmp_com, dc)
            if error:
                dev_struct.log("error decoding snmp_coms '%s'" % (snmp_com), logging_tools.LOG_LEVEL_ERROR)
                dev_struct.release_lock(int_com.com_name)
                int_com.set_node_result(dev_struct.name, "error decoding snmp_coms '%s'" % (snmp_com))
            else:
                snmp_ip = dev_struct.ip_dict.keys()[0]
                snmp_batch = snmp_batch_class(com_source, int_com, dev_struct)
                snmp_batch.set_community_strings(**dev_struct.get_community_strings(dc))
                if add_snmp_coms.has_key("S"):
                    snmp_batch.add_set(snmp_ip, add_snmp_coms["S"])
                if add_snmp_coms.has_key("G"):
                    snmp_batch.add_get(snmp_ip, add_snmp_coms["G"])
                #self.log("init snmp_batch 1")
                self.__queue_dict["snmp_send_queue"].put(("new_snmp_batch", snmp_batch))
            dc.release()
    def _snmp_command_low_level(self, (com_source, dev_struct, add_snmp_coms)):
        if not dev_struct.ip_dict:
            dev_struct.log("no ip found for low_level snmp_command (source %s)" % (com_source), logging_tools.LOG_LEVEL_ERROR)
        else:
            snmp_ip = dev_struct.ip_dict.keys()[0]
            snmp_batch = snmp_batch_class(com_source, None, dev_struct)
            dc = self.__db_con.get_connection(SQL_ACCESS)
            snmp_batch.set_community_strings(**dev_struct.get_community_strings(dc))
            dc.release()
            if add_snmp_coms.has_key("S"):
                snmp_batch.add_set(snmp_ip, add_snmp_coms["S"])
            if add_snmp_coms.has_key("G"):
                snmp_batch.add_get(snmp_ip, add_snmp_coms["G"])
            #self.log("init snmp_batch 2")
            self.__queue_dict["snmp_send_queue"].put(("new_snmp_batch", snmp_batch))
        # send hello to sender_thread

##class sql_thread(threading_tools.thread_obj):
##    def __init__(self, glob_config, loc_config, db_con, log_queue):
##        self.__db_con = db_con
##        self.__log_queue = log_queue
##        self.__glob_config, self.__loc_config = (glob_config, loc_config)
##        threading_tools.thread_obj.__init__(self, "sql", queue_size=200)
##        self.register_func("update"      , self._update_db)
##        self.register_func("insert_value", self._insert_value_db)
##        self.register_func("insert_set"  , self._insert_set_db)
##    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
##        self.__log_queue.put(("log", (self.name, what, lev)))
##    def thread_running(self):
##        self.send_pool_message(("new_pid", (self.name, self.pid)))
##        self._init_start_time()
##        self.__dc = self.__db_con.get_connection(SQL_ACCESS)
##    def _init_start_time(self):
##        self.__start_time = time.time()
##        self.__num_written, self.__num_update, self.__num_ins_v, self.__num_ins_s = (0, 0, 0, 0)
##    def _check_written(self, force=False):
##        if not force:
##            self.__num_written += 1
##        if self.__num_written > 50 or force:
##            act_time = time.time()
##            self.log("wrote %d entries (%s, %s [with values], %s [with set]) in %s" % (self.__num_written,
##                                                                                       logging_tools.get_plural("update", self.__num_update),
##                                                                                       logging_tools.get_plural("insert", self.__num_ins_v),
##                                                                                       logging_tools.get_plural("insert", self.__num_ins_s),
##                                                                                       logging_tools.get_diff_time_str(act_time - self.__start_time)))
##            self._init_start_time()
##    def _update_db(self, args):
##        if len(args) == 2:
##            sql_table, sql_data = args
##            sql_args = None
##        else:
##            sql_table, sql_data, sql_args = args
##        self.__dc.execute("UPDATE %s SET %s" % (sql_table, sql_data), sql_args)
##        self.__num_update += 1
##        self._check_written()
##    def _insert_value_db(self, args):
##        if len(args) == 2:
##            sql_table, sql_data = args
##            sql_args = None
##        else:
##            sql_table, sql_data, sql_args = args
##        self.__dc.execute("INSERT INTO %s VALUES(%s)" % (sql_table, sql_data), sql_args)
##        self.__num_ins_v += 1
##        self._check_written()
##    def _insert_set_db(self, args):
##        if len(args) == 2:
##            sql_table, sql_data = args
##            sql_args = None
##        else:
##            sql_table, sql_data, sql_args = args
##        self.__dc.execute("INSERT INTO %s SET %s" % (sql_table, sql_data), sql_args)
##        self.__num_ins_s += 1
##        self._check_written()
##    def loop_end(self):
##        self._check_written(True)
##        self.__dc.release()

##class dhcp_thread(threading_tools.thread_obj):
##    def __init__(self, glob_config, loc_config, db_con, log_queue):
##        self.__db_con = db_con
##        self.__log_queue = log_queue
##        self.__glob_config, self.__loc_config = (glob_config, loc_config)
##        threading_tools.thread_obj.__init__(self, "dhcp", queue_size=100)
##        self.register_func("server_com", self._server_com)
##        self.register_func("set_ad_struct", self._set_ad_struct)
##        self.register_func("set_queue_dict", self._set_queue_dict)
##    def _set_queue_dict(self, q_dict):
##        self.__queue_dict = q_dict
##    def thread_running(self):
##        self.send_pool_message(("new_pid", (self.name, self.pid)))
##        self.__om_error_re = re.compile("^can't (.*) object: (.*)$")
##        dc = self.__db_con.get_connection(SQL_ACCESS)
##        dc.execute("SELECT i.ip,nw.netmask FROM netip i, netdevice n, network nw, device d, device_config dc, new_config c, network_type nt WHERE " + \
##                   "dc.device=d.device_idx AND dc.new_config=c.new_config_idx AND c.name='mother_server' AND i.netdevice=n.netdevice_idx AND nw.network_idx=i.network AND " + \
##                   "nt.identifier='b' AND nt.network_type_idx=nw.network_type AND n.device=d.device_idx AND d.device_idx=%d" % (self.__loc_config["MOTHER_SERVER_IDX"]))
##        self.__server_ip = dc.fetchone()
##        if self.__server_ip:
##            self.log("IP-Address in bootnet is %s (netmask %s)" % (self.__server_ip["ip"], self.__server_ip["netmask"]))
##        else:
##            self.log("found no IP-Adress in bootnet", logging_tools.LOG_LEVEL_WARN)
##        dc.release()
##    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
##        self.__log_queue.put(("log", (self.name, what, lev)))
##    def _set_ad_struct(self, ad_struct):
##        self.log("got ad_struct")
##        self.__ad_struct = ad_struct

class configure_thread(threading_tools.thread_obj):
    def __init__(self, glob_config, loc_config, db_con, log_queue):
        self.__db_con = db_con
        self.__log_queue = log_queue
        self.__glob_config, self.__loc_config = (glob_config, loc_config)
        threading_tools.thread_obj.__init__(self, "config", queue_size=100)
        self.register_func("set_queue_dict", self._set_queue_dict)
        self.register_func("set_ad_struct", self._set_ad_struct)
        self.register_func("refresh_tk", self._refresh_target_kernel)
        self.register_func("refresh_all", self._refresh_all)
        self.register_func("readdots", self._read_dot_files)
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__log_queue.put(("log", (self.name, what, lev)))
    def _set_ad_struct(self, ad_struct):
        self.log("got ad_struct")
        self.__ad_struct = ad_struct
    def thread_running(self):
        self.send_pool_message(("new_pid", (self.name, self.pid)))
        self.__dc = self.__db_con.get_connection(SQL_ACCESS)
        self.__dc.execute("SELECT i.ip,nw.netmask FROM netip i, netdevice n, network nw, device d, device_config dc, new_config c, network_type nt WHERE " + \
                          "dc.device=d.device_idx AND dc.new_config=c.new_config_idx AND c.name='mother_server' AND i.netdevice=n.netdevice_idx AND nw.network_idx=i.network AND " + \
                          "nt.identifier='b' AND nt.network_type_idx=nw.network_type AND n.device=d.device_idx AND d.device_idx=%d" % (self.__loc_config["MOTHER_SERVER_IDX"]))
        self.__server_ip = self.__dc.fetchone()
        if self.__server_ip:
            self.log("IP-Address in bootnet is %s (netmask %s)" % (self.__server_ip["ip"], self.__server_ip["netmask"]))
        else:
            self.log("found no IP-Adress in bootnet", logging_tools.LOG_LEVEL_WARN)
    def loop_end(self):
        self.__dc.release()
    def _set_queue_dict(self, q_dict):
        self.__dhcp_queue = q_dict["dhcp_queue"]
        self.__sql_queue  = q_dict["sql_queue"]
    def _refresh_all(self, (mach, int_com)):
        if mach == None:
            # refresh all machines
            for upd_name in [k for k, v in self.__ad_struct.iteritems() if not self.__ad_struct.is_an_ip(k)]:
                dev_struct = self.__ad_struct[upd_name]
                if isinstance(dev_struct, machine):
                    self._refresh_target_kernel((dev_struct.name, int_com))
                    self._read_dot_files((dev_struct.name, int_com))
        else:
            self._refresh_target_kernel((mach, int_com))
            self._read_dot_files((mach, int_com))
    def _refresh_target_kernel(self, (mach, int_com)):
        mach_struct = self.__ad_struct[mach]
        mach_struct.incr_use_count("refresh_tk")
        mach_struct.check_network_settings(self.__dc)
        if mach_struct.node:
            self.__dc.execute("SELECT d.device_idx, d.newkernel, d.new_kernel, s.status, d.kernel_append, d.prod_link, d.stage1_flavour, d.bootnetdevice FROM device d, status s, device_type dt, netdevice n WHERE d.name='%s' AND d.newstate=s.status_idx AND d.device_type=dt.device_type_idx AND dt.identifier='H' AND n.device=d.device_idx AND n.netdevice_idx=d.bootnetdevice" % (mach_struct.name))
            newk = self.__dc.fetchone()
            #print dbcon,newk, mach.name
            if newk:
                if not newk["stage1_flavour"]:
                    newk["stage1_flavour"] = "lo"
                    mach_struct.log("setting stage1_flavour to '%s'" % (newk["stage1_flavour"]))
                    self.__dc.execute("UPDATE device SET stage1_flavour=%s WHERE device_idx=%s", (newk["stage1_flavour"],
                                                                                                  newk["device_idx"]))
                refresh_str = "refresh for target_state %s" % (newk["status"])
                prod_link = newk["prod_link"]
                if prod_link:
                    self.__dc.execute("SELECT nw.identifier, nw.name FROM network nw WHERE nw.network_idx=%d" % (prod_link))
                    pnet = self.__dc.fetchone()
                    if pnet:
                        prod_net = pnet["identifier"]
                        refresh_str += ", production net %s (%s)" % (prod_net, pnet["name"])
                else:
                    prod_net = None
                if newk["status"] in self.__loc_config["LIST_TAG_KERNEL"]:
                    new_kernel_stuff = get_kernel_stuff(self.__dc, self.__glob_config, newk["newkernel"], newk["new_kernel"])
                    if new_kernel_stuff:
                        refresh_str += " and kernel %s" % (new_kernel_stuff["name"])
                    else:
                        refresh_str += ", kernel not set"
                else:
                    new_kernel_stuff = None
                ret_str = "ok starting %s" % (refresh_str)
                mach_struct.log(ret_str)
                if int_com:
                    int_com.set_int_result(mach_struct, ret_str)
                # delete old pxe/net files
                pxe_file = mach_struct.get_pxe_file_name()
                net_file = mach_struct.get_net_file_name()
                # remove old bootpxe
                if os.path.exists(pxe_file):
                    os.unlink(pxe_file)
                # unlink net_file only if we change to memtest/dosboot
                if ((not newk["status"] in self.__loc_config["LIST_TAG_KERNEL"]) or os.path.islink(net_file)) and os.path.exists(net_file):
                    os.unlink(net_file)
                # pxe and net kernel boot config
                #print ip_to_write, newk["status"], LIST_TAGKERNEL
                if newk["status"] in self.__loc_config["LIST_TAG_KERNEL"]:
                    #print newk.keys(), server_ip
                    # unlink old initrd/kernel links
                    if self.__server_ip and new_kernel_stuff:
                        mach_struct.write_kernel_config(self.__sql_queue,
                                                        new_kernel_stuff,
                                                        newk["kernel_append"],
                                                        self.__server_ip["ip"],
                                                        self.__server_ip["netmask"],
                                                        self.__loc_config,
                                                        newk["stage1_flavour"])
##                 elif newk["status"] in LIST_DOSBOOT:
##                     mach_struct.write_dosboot_config(eepro100_pxe)
                elif newk["status"] in self.__loc_config["LIST_MEMTEST"]:
                    mach_struct.write_memtest_config()
                elif newk["status"] in self.__loc_config["LIST_BOOTLOCAL"]:
                    mach_struct.write_localboot_config()
                mach_struct.log("refresh (tk) finished")
            else:
                mach_struct.log("newk not defined", logging_tools.LOG_LEVEL_WARN)
                if int_com:
                    int_com.set_int_result(mach_struct, "error newk not defined")
        else:
            if int_com:
                int_com.set_int_result(mach_struct, "error not node")
        mach_struct.decr_use_count("refresh_tk")
    def _read_dot_files(self, (mach, int_com)):
        mach_struct = self.__ad_struct[mach]
        mach_struct.incr_use_count("read_dots")
        if not mach_struct.node:
            mach_struct.log("not node, checking network settings", logging_tools.LOG_LEVEL_WARN)
            mach_struct.check_network_settings(self.__dc)
        if mach_struct.node:
            c_dir = mach_struct.get_config_dir()
            mach_struct.log("starting readdots in dir '%s'" % (c_dir))
            hlist = [(".version"  , "imageversion"       , None             ),
                     (".imagename", "actimage"           , None             ),
                     (".imagename", "act_image"          , "image"          ),
                     (".kernel"   , "actkernel"          , None             ),
                     (".kernel"   , "act_kernel"         , "kernel"         ),
                     (".kversion" , "kernelversion"      , None             ),
                     (".parttype" , "act_partition_table", "partition_table"),
                     (None        , "act_kernel_build"   , None             )]
            self.__dc.execute("SELECT %s FROM device d WHERE d.name='%s'" % (", ".join(["d.%s" % (b) for a, b, c in hlist]), mach_struct.name))
            act_conf = self.__dc.fetchone()
            s_list = []
            num_tried, num_ok = (0, 0)
            for filen, dbentry, orig_db in hlist:
                if filen:
                    num_tried += 1
                    try:
                        line = open("%s/%s" % (c_dir, filen), "r").readline().strip()
                    except:
                        pass
                    else:
                        num_ok += 1
                        if orig_db:
                            self.__dc.execute("SELECT x.%s_idx FROM %s x WHERE x.name=%%s" % (orig_db, orig_db), line)
                            if self.__dc.rowcount:
                                line = int(self.__dc.fetchone()["%s_idx" % (orig_db)])
                            else:
                                line = 0
                        if act_conf[dbentry] != line:
                            act_conf[dbentry] = line
                            s_list.append((dbentry, line))
            # dirty hack
            if act_conf["act_kernel"] and act_conf["actkernel"] and act_conf["kernelversion"]:
                if re.match("^(\d+)\.(\d+)$", act_conf["kernelversion"]):
                    mach_struct.log(" - dirty hack to guess act_kernel_build (act_kernel %d, act_version %s)" % (act_conf["act_kernel"], act_conf["kernelversion"]))
                    self.__dc.execute("SELECT kernel_build_idx FROM kernel_build WHERE kernel=%d AND version=%d AND `release`=%d" % (act_conf["act_kernel"],
                                                                                                                                    int(act_conf["kernelversion"].split(".")[0]),
                                                                                                                                    int(act_conf["kernelversion"].split(".")[1])))
                    if self.__dc.rowcount:
                        line = self.__dc.fetchone()["kernel_build_idx"]
                        if act_conf["act_kernel_build"] != line:
                            s_list.append(("act_kernel_build", line))
                else:
                    mach_struct.log("cannot parse kernelversion '%s'" % (act_conf["kernelversion"]), logging_tools.LOG_LEVEL_ERROR)
            if s_list:
                self.__dc.execute("UPDATE device SET %s WHERE name=%%s" % (", ".join(["%s=%%s" % (x) for x, y in s_list])), tuple([y for x, y in s_list] + [mach_struct.name]))
            num_changed = len(s_list)
            ret_str = "ok read %d changed dotfiles" % (num_changed)
            mach_struct.log("readdots finished (%d tried, %d ok, %d changed%s)" % (num_tried,
                                                                                   num_ok,
                                                                                   num_changed,
                                                                                   (num_changed and " [%s]" % (", ".join(["%s=%s" % (x, str(y)) for x, y in s_list])) or "")))
        else:
            ret_str = "error %s is not a node (network settings checked)" % (mach)
        if int_com:
            int_com.set_int_result(mach_struct, ret_str)
        mach_struct.decr_use_count("read_dots")

class server_process(threading_tools.process_pool):
    def __init__(self):
        self.__log_cache, self.__log_template = ([], None)
        self.__pid_name = global_config["PID_NAME"]
        threading_tools.process_pool.__init__(self, "main", zmq=True, zmq_debug=global_config["ZMQ_DEBUG"])
        self.register_exception("int_error", self._int_error)
        self.register_exception("term_error", self._int_error)
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context)
        # log config
        self._log_config()
        # prepare directories
        self._prepare_directories()
        # check netboot functionality
        self._check_netboot_functionality()
        # check nfs exports
        self._check_nfs_exports()
        self._enable_syslog_config()
        self.__msi_block = None#self._init_msi_block()
        self._init_subsys()
        my_uuid = uuid_tools.get_uuid()
        self.log("cluster_device_uuid is '%s'" % (my_uuid.get_urn()))
        if self._init_network_sockets():
            self.add_process(mother.kernel.kernel_sync_process("kernel"), start=True)
            self.add_process(mother.command.external_command_process("command"), start=True)
            self.add_process(mother.control.node_control_process("control"), start=True)
            self.add_process(mother.control.twisted_process("twisted"), twisted=True, start=True)
            #self.add_process(build_process("build"), start=True)
            #self.register_func("client_update", self._client_update)
            # send initial commands
            self.send_to_process(
                "kernel",
                "srv_command",
                unicode(server_command.srv_command(command="check_kernel_dir", insert_all_found="1"))
            )
        else:
            self._int_error("bind problem")
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        if self.__log_template:
            while self.__log_cache:
                self.__log_template.log(*self.__log_cache.pop(0))
            self.__log_template.log(lev, what)
        else:
            self.__log_cache.append((lev, what))
    def _init_subsys(self):
        self.log("init subsystems")
    def _int_error(self, err_cause):
        if self["exit_requested"]:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            self["exit_requested"] = True
    def _log_config(self):
        self.log("Config info:")
        for line, log_level in global_config.get_log(clear=True):
            self.log(" - clf: [%d] %s" % (log_level, line))
        conf_info = global_config.get_config_info()
        self.log("Found %d valid config-lines:" % (len(conf_info)))
        for conf in conf_info:
            self.log("Config : %s" % (conf))
    def loop_end(self):
        #config_control.close_clients()
        process_tools.delete_pid(self.__pid_name)
        if self.__msi_block:
            self.__msi_block.remove_meta_block()
    def loop_post(self):
        for open_sock in self.socket_dict.itervalues():
            open_sock.close()
        self.__log_template.close()
    def _init_network_sockets(self):
        success = True
        my_0mq_id = uuid_tools.get_uuid().get_urn()
        self.socket_dict = {}
        # get all ipv4 interfaces with their ip addresses, dict: interfacename -> IPv4
        for key, sock_type, bind_port, target_func in [
            ("router", zmq.ROUTER, global_config["SERVER_PUB_PORT"] , self._new_com),
            ("pull"  , zmq.PULL  , global_config["SERVER_PULL_PORT"], self._new_com),
            ]:
            client = self.zmq_context.socket(sock_type)
            client.setsockopt(zmq.IDENTITY, my_0mq_id)
            client.setsockopt(zmq.LINGER, 100)
            client.setsockopt(zmq.HWM, 256)
            client.setsockopt(zmq.BACKLOG, 1)
            conn_str = "tcp://*:%d" % (bind_port)
            try:
                client.bind(conn_str)
            except zmq.core.error.ZMQError:
                self.log("error binding to %s{%d}: %s" % (
                    conn_str,
                    sock_type, 
                    process_tools.get_except_info()),
                         logging_tools.LOG_LEVEL_CRITICAL)
                client.close()
                success = False
            else:
                self.log("bind to port %s{%d}" % (conn_str,
                                                  sock_type))
                self.register_poller(client, zmq.POLLIN, target_func)
                self.socket_dict[key] = client
        return success
    def _new_com(self, zmq_sock):
        print "nc"
        data = [zmq_sock.recv_unicode()]
        while zmq_sock.getsockopt(zmq.RCVMORE):
            data.append(zmq_sock.recv_unicode())
        if len(data) == 2:
            print data
            zmq_sock.send_unicode(data[0], zmq.SNDMORE)
            zmq_sock.send_unicode("ok")
        else:
            self.log("wrong number of data chunks (%d != 2)" % (len(data)),
                     logging_tools.LOG_LEVEL_ERROR)
    # utility calls
    def _prepare_directories(self):
        self.log("Checking directories ...")
        for d_dir in [global_config["TFTP_DIR"],
                      global_config["ETHERBOOT_DIR"],
                      global_config["CONFIG_DIR"],
                      global_config["KERNEL_DIR"]]:
            if not os.path.isdir(d_dir):
                self.log("trying to create directory %s" % (d_dir))
                try:
                    os.makedirs(d_dir)
                except:
                    pass
        for d_link, s_link in [(global_config["TFTP_LINK"], global_config["TFTP_DIR"])]:
            if not os.path.islink(d_link):
                self.log("Trying to create link from %s to %s" % (d_link, s_link))
                try:
                    os.symlink(s_link, d_link)
                except:
                    pass
    def _check_nfs_exports(self):
        log_lines = []
        if global_config["MODIFY_NFS_CONFIG"]:
            exp_file = "/etc/exports"
            if os.path.isfile(exp_file):
                act_exports = dict([(part[0], " ".join(part[1:])) for part in [line.strip().split() for line in open(exp_file, "r").read().split("\n")] if len(part) > 1 and part[0].startswith("/")])
                self.log("found /etc/exports file with %s:" % (logging_tools.get_plural("export entry", len(act_exports))))
                exp_keys = sorted(act_exports.keys())
                my_fm = logging_tools.form_list()
                for act_exp in exp_keys:
                    where = act_exports[act_exp]
                    my_fm.add_line([act_exp, where])
                if my_fm:
                    for line in str(my_fm).split("\n"):
                        self.log("  - %s" % (line))
            else:
                self.log("found no /etc/exports file, creating new one ...")
                act_exports = {}
            valid_nt_ids = ["p", "b"]
            valid_nets = network.objects.filter(Q(network_type__identifier__in=valid_nt_ids))
            exp_dict = {"etherboot" : "ro",
                        "kernels"   : "ro",
                        "images"    : "ro",
                        "config"    : "rw"}
            new_exports = {}
            exp_nets = ["%s/%s" % (cur_net.network, cur_net.netmask) for cur_net in valid_nets]
            if exp_nets:
                for exp_dir, rws in exp_dict.iteritems():
                    act_exp_dir = "%s/%s" % (global_config["TFTP_DIR"], exp_dir)
                    if not act_exp_dir in act_exports:
                        new_exports[act_exp_dir] = " ".join(["%s(%s,no_root_squash,async,no_subtree_check)" % (exp_net, rws) for exp_net in exp_nets])
            if new_exports:
                open(exp_file, "a").write("\n".join(["%-30s %s" % (x, y) for x, y in new_exports.iteritems()] + [""]))
                at_command = "/etc/init.d/nfsserver restart"
                at_stat, add_log_lines = process_tools.submit_at_command(at_command)
                self.log("starting the at-command '%s' gave %d:" % (at_command, at_stat))
                for log_line in add_log_lines:
                    self.log(log_line)
    def _enable_syslog_config(self):
        syslog_exe_dict = dict([(key, value) for key, value in process_tools.get_proc_list().iteritems() if value and value.get("exe", "") and value["exe"].count("syslog")])
        syslog_type = None
        for key, value in syslog_exe_dict.iteritems():
            self.log("syslog process found: %6d = %s" % (key, value["exe"]))
            if value["exe"].endswith("rsyslogd"):
                syslog_type = "rsyslogd"
        self.log("syslog type found: %s" % (syslog_type or "none"))
        self.__syslog_type = syslog_type
        if self.__syslog_type == "rsyslogd":
            pass
        elif self.__syslog_type == "syslog-ng":
            self._enable_syslog_ng()
    def _disable_syslog_config(self):
        if self.__syslog_type == "rsyslogd":
            pass
        elif self.__syslog_type == "syslog-ng":
            self._disable_syslog_ng()
    def _enable_syslog_ng(self):
        slcn = "/etc/syslog-ng/syslog-ng.conf"
        if os.path.isfile(slcn):
            # start of shiny new modification code, right now only used to get the name of the /dev/log source
            dev_log_source_name = "src"
            try:
                act_conf = logging_tools.syslog_ng_config()
            except:
                self.log("Unable to parse config: %s, using '%s' as /dev/log-source" % (process_tools.get_except_info(),
                                                                                        dev_log_source_name),
                         logging_tools.LOG_LEVEL_ERROR)

            else:
                source_key = "/dev/log"
                source_dict = act_conf.get_dict_sort(act_conf.get_multi_object("source"))
                if source_dict.has_key(source_key):
                    dev_log_source_name = source_dict[source_key][0]
                    self.log("'%s'-key in config, using '%s' as /dev/log-source" % (source_key,
                                                                                    dev_log_source_name))
                else:
                    self.log("'%s'-key not in config, using '%s' as /dev/log-source" % (source_key,
                                                                                        dev_log_source_name))
            self.log("Trying to rewrite syslog-ng.conf for mother ...")
            try:
                orig_conf = [x.rstrip() for x in open(slcn, "r").readlines()]
                # check for mother-lines and/or dhcp-lines
                opt_list = ["dhcp", "mother", "dhcp_filter"]
                opt_dict = dict([(x, 0) for x in opt_list])
                for line in orig_conf:
                    if re.match("^.*source dhcp.*$", line):
                        opt_dict["dhcp"] = 1
                    if re.match("^.*filter f_dhcp.*$", line):
                        opt_dict["dhcp_filter"] = 1
                    if re.match("^.*mother.*$", line):
                        opt_dict["mother"] = 1
                self.log("after parsing: %s" % (", ".join(["%s: %d" % (x, opt_dict[x]) for x in opt_list])))
                if not opt_dict["mother"]:
                    mother_lines = []
                    if not opt_dict["dhcp_filter"]:
                        # message() instead of match() since syslog-ng 2.1
                        mother_lines.extend(["",
                                             'filter f_dhcp       { message("DHCP") ; };'])
                    if opt_dict["dhcp"]:
                        self.log("dhcp-source found, so it seems that the DHCPD is running chrooted() ...")
                        mother_lines.extend(["",
                                             'destination dhcpmother { unix-dgram("%s") ;};' % (self.__glob_config["SYSLOG_UDS_NAME"]),
                                             "",
                                             'log { source(dhcp); source(%s); filter(f_dhcp)    ; destination(dhcpmother); };' % (dev_log_source_name)])
                    else:
                        self.log("dhcp-source not found, so it seems that the DHCPD is NOT running chrooted() ...")
                        mother_lines.extend(["",
                                             'destination dhcpmother { unix-dgram("%s") ;};' % (self.__glob_config["SYSLOG_UDS_NAME"]),
                                             "",
                                             'log {               source(%s); filter(f_dhcp)    ; destination(dhcpmother);};' % (dev_log_source_name)])
                    for ml in mother_lines:
                        self.log("adding line to %s : %s" % (slcn, ml))
                    open(slcn, "w").write("\n".join(orig_conf + mother_lines + [""]))
                else:
                    self.log("%s seems to be OK, leaving unchanged..." % (slcn))
                self.log("...done")
            except:
                self.log("Something went wrong while trying to modify '%s', help..." % (slcn), logging_tools.LOG_LEVEL_CRITICAL)
        else:
            self.log("config file '%s' not present" % (slcn), logging_tools.LOG_LEVEL_WARN)
        self._restart_syslog()
    def _disable_syslog_ng(self):
        self.log("Trying to rewrite syslog-ng.conf for normal operation ...")
        slcn = "/etc/syslog-ng/syslog-ng.conf"
        try:
            orig_conf = [x.rstrip() for x in open(slcn, "r").readlines()]
            new_conf = []
            del_lines = []
            for line in orig_conf:
                if re.match("^.*mother.*$", line):
                    del_lines.append(line)
                else:
                    new_conf.append(line)
            if del_lines:
                self.log("Found %s:" % (logging_tools.get_plural("mother-related line", len(del_lines))))
                for dl in del_lines:
                    self.log("  removing : %s" % (dl))
                # remove double empty-lines
                new_conf_2, last_line = ([], None)
                for line in new_conf:
                    if line == last_line and last_line == "":
                        pass
                    else:
                        new_conf_2.append(line)
                    last_line = line
                open(slcn, "w").write("\n".join(new_conf_2))
            else:
                self.log("Found no mother-related lines, leaving %s untouched" % (slcn))
            self.log("...done")
        except:
            self.log("Something went wrong while trying to modify '%s': %s, help..." % (slcn,
                                                                                        process_tools.get_except_info()),
                     logging_tools.LOG_LEVEL_ERROR)
        self._restart_syslog()
    def _restart_syslog(self):
        for syslog_rc in ["/etc/init.d/syslog", "/etc/init.d/syslog-ng"]:
            if os.path.isfile(syslog_rc):
                break
        stat, out_f = process_tools.submit_at_command("%s restart" % (syslog_rc), 0)
        self.log("restarting %s gave %d:" % (syslog_rc, stat))
        for line in out_f:
            self.log(line)
    def _check_netboot_functionality(self):
        global_config.add_config_entries([
            ("PXEBOOT", configfile.bool_c_var(False, source="default")),
            ("XENBOOT", configfile.bool_c_var(False, source="default"))])
        pxe_paths = ["%s/share/mother/syslinux/pxelinux.0" % (global_config["CLUSTER_DIR"])]
        for pxe_path in pxe_paths:
            if os.path.isfile(pxe_path):
                try:
                    pxelinux_0 = open(pxe_path, "r").read()
                except:
                    self.log("Cannot read pxelinux.0 from %s" % (pxe_path), logging_tools.LOG_LEVEL_WARN)
                else:
                    global_config.add_config_entries([
                        ("PXEBOOT"   , configfile.bool_c_var(True, source="filesystem")),
                        ("PXELINUX_0", configfile.blob_c_var(pxelinux_0, source="filesystem"))])
                    self.log("Found pxelinux.0 in %s" % (pxe_path))
                    break
            else:
                self.log("Found no pxelinux.0 in %s" % (pxe_path), logging_tools.LOG_LEVEL_WARN)
        mb32_paths = ["%s/share/mother/syslinux/mboot.c32" % (global_config["CLUSTER_DIR"])]
        for mb32_path in mb32_paths:
            if os.path.isfile(mb32_path):
                try:
                    mb32_0 = open(mb32_path, "r").read()
                except:
                    self.log("Cannot read mboot.c32 from %s" % (mb32_path), logging_tools.LOG_LEVEL_WARN)
                else:
                    global_config.add_config_entries([
                        ("XENBOOT"  , configfile.bool_c_var(True, source="filesystem")),
                        ("MBOOT.C32", configfile.blob_c_var(mb32_0, source="filesystem"))])
                    self.log("Found mboot.c32 in %s" % (mb32_path))
                    break
            else:
                self.log("Found no mboot.c32 in %s" % (mb32_path), logging_tools.LOG_LEVEL_WARN)

class server_thread_pool(threading_tools.thread_pool):
    def __init__(self, db_con, g_config, loc_config):
        self.__log_cache, self.__log_queue = ([], None)
        self.__db_con = db_con
        self.__glob_config, self.__loc_config = (g_config, loc_config)
        threading_tools.thread_pool.__init__(self, "main", blocking_loop=False)
        self.__msi_block = self._init_msi_block()
        self.register_func("new_pid", self._new_pid)
        self.register_func("restart_hoststatus", self._restart_hoststatus)
        self.register_func("macaddrs_written", self._macaddrs_written)
        self.register_exception("int_error", self._int_error)
        self.register_exception("term_error", self._int_error)
        #self.register_exception("hup_error", self._hup_error)
        # enable syslog config
        dc = self.__db_con.get_connection(SQL_ACCESS)
        # re-insert config
        self._re_insert_config(dc)
        self.__ns = net_tools.network_server(timeout=2, log_hook=self.log, poll_verbose=self.__loc_config["VERBOSE"] > 1)
        self.__icmp_obj = net_tools.icmp_bind()
        self.__ns.add_object(self.__icmp_obj)
        self.__syslog_udb = self.__ns.add_object(net_tools.unix_domain_bind(self._new_ud_out_recv, socket=self.__glob_config["SYSLOG_UDS_NAME"], mode=0666, bind_state_call=self._bind_state_call))[0]
        self.__ns.add_object(net_tools.tcp_bind(self._new_tcp_command_con, port=g_config["COMPORT"], bind_retries=5, bind_state_call=self._bind_state_call, timeout=120, in_buffer_size=65536))
        self.__ns.add_object(net_tools.tcp_bind(self._new_tcp_node_con, port=g_config["NODEPORT"], bind_retries=5, bind_state_call=self._bind_state_call, timeout=60))
        # global network settings
        self._check_global_network_stuff(dc)
        self.__ad_struct = all_devices(self.__log_queue, self.__glob_config, self.__loc_config, self.__db_con)
        # to enable logging
        self.__log_queue.put(("set_ad_struct", self.__ad_struct))
        self.__ad_struct.db_sync(dc)
        # start threads
        self.__sql_queue       = self.add_thread(sql_thread(self.__glob_config, self.__loc_config, self.__db_con, self.__log_queue), start_thread=True).get_thread_queue()
        self.__dhcp_queue      = self.add_thread(dhcp_thread(self.__glob_config, self.__loc_config, self.__db_con, self.__log_queue), start_thread=True).get_thread_queue()
        self.__com_queue       = self.add_thread(command_thread(self.__glob_config, self.__loc_config, self.__db_con, self.__log_queue), start_thread=True).get_thread_queue()
        self.__config_queue    = self.add_thread(configure_thread(self.__glob_config, self.__loc_config, self.__db_con, self.__log_queue), start_thread=True).get_thread_queue()
        self.__control_queue   = self.add_thread(control_thread(self.__glob_config, self.__loc_config, self.__db_con, self.__log_queue), start_thread=True).get_thread_queue()
        # copy stuff from glob_config to loc_config for kernel_sync_thread
        self.__glob_config.add_config_dict({"SERVER_SHORT_NAME" : configfile.str_c_var(self.__loc_config["SERVER_SHORT_NAME"]),
                                            "SQL_ACCESS"        : configfile.str_c_var(self.__loc_config["SQL_ACCESS"]),
                                            "SYNCER_ROLE"       : configfile.str_c_var("mother")})
##        self.__kernel_queue    = self.add_thread(kernel_sync_tools.kernel_sync_thread(self.__glob_config, self.__db_con, log_type="queue", log_queue=self.__log_queue), start_thread=True).get_thread_queue()
##        self.__snmp_send_queue = self.add_thread(snmp_send_thread(self.__glob_config, self.__loc_config, self.__db_con, self.__log_queue), start_thread=True).get_thread_queue()
##        self.__snmp_trap_queue = self.add_thread(snmp_trap_thread(self.__glob_config, self.__loc_config, self.__db_con, self.__log_queue), start_thread=True).get_thread_queue()
##        self.__dhcp_queue.put(("set_ad_struct", self.__ad_struct))
##        self.__config_queue.put(("set_ad_struct", self.__ad_struct))
##        self.__control_queue.put(("set_ad_struct", self.__ad_struct))
##        self.__com_queue.put(("set_ad_struct", self.__ad_struct))
##        self.__snmp_trap_queue.put(("set_ad_struct", self.__ad_struct))
##        self.__queue_dict = {"log_queue"       : self.__log_queue,
##                             "dhcp_queue"      : self.__dhcp_queue,
##                             "command_queue"   : self.__com_queue,
##                             "sql_queue"       : self.__sql_queue,
##                             "config_queue"    : self.__config_queue,
##                             "control_queue"   : self.__control_queue,
##                             "kernel_queue"    : self.__kernel_queue,
##                             "snmp_send_queue" : self.__snmp_send_queue}
##        self.__log_queue.put(("set_queue_dict", self.__queue_dict))
##        self.__com_queue.put(("set_queue_dict", self.__queue_dict))
##        self.__dhcp_queue.put(("set_queue_dict", self.__queue_dict))
##        self.__config_queue.put(("set_queue_dict", self.__queue_dict))
##        self.__control_queue.put(("set_queue_dict", self.__queue_dict))
##        self.__snmp_send_queue.put(("set_queue_dict", self.__queue_dict))
##        self.__snmp_trap_queue.put(("set_queue_dict", self.__queue_dict))
##        self.__control_queue.put(("set_net_stuff", (self.__ns, self.__icmp_obj)))
##        self.__kernel_queue.put(("set_net_stuff", self.__ns))
        if self.__loc_config["DAEMON"]:
            # only restart hoststatus when in daemon-mode
            self.__log_queue.put(("delay_request", (self.get_own_queue(), "restart_hoststatus", 5)))
        dc.release()
        self.__config_queue.put(("refresh_all", (None, None)))
        # uuid log
        # write dhcp-address
        self.__dhcp_queue.put(("server_com", server_command.server_command(command="alter_macadr",
                                                                           option_dict={"SIGNAL_MAIN_THREAD" : "macaddrs_written"})))
        # init apc-update-timestmamp
        self.__last_apc_update = None
##    def _int_error(self, err_cause):
##        if self["exit_requested"]:
##            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
##        else:
##            self.log("exit requested", logging_tools.LOG_LEVEL_WARN)
##            self._disable_syslog_config()
##            self["exit_requested"] = True
##    def _new_pid(self, (thread_name, new_pid)):
##        self.log("received new_pid message from thread %s" % (thread_name))
##        process_tools.append_pids(self.__loc_config["PID_NAME"], new_pid)
##        if self.__msi_block:
##            self.__msi_block.add_actual_pid(new_pid)
##            self.__msi_block.save_block()
    def _re_insert_config(self, dc):
        self.log("re-insert config")
        configfile.write_config(dc, "mother_server", self.__glob_config)
    def _restart_hoststatus(self):
        if os.path.isfile("/etc/init.d/hoststatus"):
            self.log("restart hoststatus (child)")
            c_stat, out_f = process_tools.submit_at_command("/etc/init.d/hoststatus restart", 0)
            self.log("restarting /etc/init.d/hoststatus gave %d:" % (c_stat))
            for line in out_f:
                self.log(line)
    def _macaddrs_written(self):
        self.log("all macaddresses refreshed from db, restarting dhcpd server")
        dhcp_init_file = "/etc/init.d/dhcpd"
        if os.path.isfile(dhcp_init_file):
            self.log("restart dhcp-server")
            c_stat, out_f = process_tools.submit_at_command("%s restart" % (dhcp_init_file), 0)
            self.log("restarting %s gave %d:" % (dhcp_init_file,
                                                 c_stat))
            for line in out_f:
                self.log(line)
        else:
            self.log("no %s found" % (dhcp_init_file),
                     logging_tools.LOG_LEVEL_ERROR)
##    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
##        if self.__log_queue:
##            if self.__log_cache:
##                for c_what, c_lev in self.__log_cache:
##                    self.__log_queue.put(("log", (self.name, "(delayed) %s" % (c_what), c_lev)))
##                self.__log_cache = []
##            self.__log_queue.put(("log", (self.name, what, lev)))
##        else:
##            self.__log_cache.append((what, lev))
##    def _check_global_network_stuff(self, dc):
##        self.log("Checking global network settings")
##        dc.execute("SELECT i.ip,n.netdevice_idx,nw.network_idx FROM netdevice n, netip i, network nw WHERE n.device=%d AND i.netdevice=n.netdevice_idx AND i.network=nw.network_idx" % (self.__loc_config["MOTHER_SERVER_IDX"]))
##        glob_net_devices = {}
##        for net_rec in dc.fetchall():
##            n_d, n_i, n_w = (net_rec["netdevice_idx"],
##                             net_rec["ip"],
##                             net_rec["network_idx"])
##            if not glob_net_devices.has_key(n_d):
##                glob_net_devices[n_d] = []
##            glob_net_devices[n_d].append((n_i, n_w))
##        # get all network_device_types
##        dc.execute("SELECT * FROM network_device_type")
##        self.__loc_config["GLOBAL_NET_DEVICES"] = glob_net_devices
##        self.__loc_config["GLOBAL_NET_DEVICE_DICT"] = dict([(x["identifier"], x["network_device_type_idx"]) for x in dc.fetchall()])
    def _init_msi_block(self):
        process_tools.save_pid(self.__loc_config["PID_NAME"])
        if self.__loc_config["DAEMON"]:
            self.log("Initialising meta-server-info block")
            msi_block = process_tools.meta_server_info("mother")
            msi_block.add_actual_pid()
            msi_block.start_command = "/etc/init.d/mother start"
            msi_block.stop_command = "/etc/init.d/mother force-stop"
            msi_block.kill_pids = True
            msi_block.save_block()
        else:
            msi_block = None
        return msi_block
    def _new_ud_out_recv(self, data, src):
        self.__log_queue.put(("syslog_dhcp", data))
    def _new_tcp_command_con(self, sock, src):
        return new_tcp_con("com", sock, src, self.__com_queue, self.__log_queue)
    def _new_tcp_node_con(self, sock, src):
        return new_tcp_con("node", sock, src, self.__control_queue, self.__log_queue)
    def _bind_state_call(self, **args):
        if args["state"].count("ok"):
            self.log("Bind to %s (type %s) sucessfull" % (args["port"], args["type"]))
        else:
            self.log("Bind to %s (type %s) NOT sucessfull" % (args["port"], args["type"]), logging_tools.LOG_LEVEL_CRITICAL)
            self.log("unable to bind to all ports, exiting", logging_tools.LOG_LEVEL_ERROR)
            self._int_error("bind problem")
        #self.__bind_state[id_str] = args["state"]
    def loop_function(self):
        self.__ns.step()
        if self.__loc_config["VERBOSE"]:
            tqi_dict = self.get_thread_queue_info()
            tq_names = sorted(tqi_dict.keys())
            self.log("tqi: %s" % (", ".join([t_used and "%s: %3d of %3d" % (t_name, t_used, t_total) or "%s: %3d" % (t_name, t_total) for (t_name, t_used, t_total) in [(t_name,
                                                                                                                                                                         tqi_dict[t_name][1],
                                                                                                                                                                         tqi_dict[t_name][0]) for t_name in tq_names]])))
        act_time = time.time()
        if not self.__last_apc_update or abs(self.__last_apc_update - act_time) > self.__glob_config["APC_REPROGRAMM_TIME"]:
            self.__last_apc_update = act_time
            for dev_name in [x for x in self.__ad_struct.keys() if not self.__ad_struct.is_an_ip(x)]:
                dev = self.__ad_struct[dev_name]
                if isinstance(dev, apc):
                    dev.update(self.__queue_dict["command_queue"])
                elif isinstance(dev, ibc):
                    dev.update(self.__queue_dict["command_queue"])
        for upd_q in [self.__log_queue, self.__control_queue]:
            upd_q.put("update")
    def thread_loop_post(self):
        process_tools.delete_pid(self.__loc_config["PID_NAME"])
        if self.__msi_block:
            self.__msi_block.remove_meta_block()
        
def main():
    long_host_name, mach_name = process_tools.get_fqdn()
    prog_name = global_config.name()
    global_config.add_config_entries([
        ("DEBUG"               , configfile.bool_c_var(False, help_string="enable debug mode [%(default)s]", short_options="d", only_commandline=True)),
        ("ZMQ_DEBUG"           , configfile.bool_c_var(False, help_string="enable 0MQ debugging [%(default)s]", only_commandline=True)),
        ("PID_NAME"            , configfile.str_c_var(os.path.join(prog_name, prog_name))),
        ("KILL_RUNNING"        , configfile.bool_c_var(True, help_string="kill running instances [%(default)s]")),
        ("FORCE"               , configfile.bool_c_var(False, help_string="force running [%(default)s]", action="store_true", only_commandline=True)),
        ("CHECK"               , configfile.bool_c_var(False, help_string="only check for server status", action="store_true", only_commandline=True, short_options="C")),
        ("LOG_DESTINATION"     , configfile.str_c_var("uds:/var/lib/logging-server/py_log_zmq")),
        ("LOG_NAME"            , configfile.str_c_var(prog_name)),
        ("USER"                , configfile.str_c_var("root", help_string="user to run as [%(default)s]")),
        ("GROUP"               , configfile.str_c_var("root", help_string="group to run as [%(default)s]")),
        ("LOG_DESTINATION"     , configfile.str_c_var("uds:/var/lib/logging-server/py_log_zmq")),
        ("LOG_NAME"            , configfile.str_c_var(prog_name)),
        ("MODIFY_NFS_CONFIG"   , configfile.bool_c_var(True, help_string="modify /etc/exports [%(default)s]", action="store_true")),
        ("VERBOSE"             , configfile.int_c_var(0, help_string="set verbose level [%(default)d]", short_options="v", only_commandline=True)),
        ("SERVER_PUB_PORT"     , configfile.int_c_var(8000, help_string="server publish port [%(default)d]")),
        ("SERVER_PULL_PORT"    , configfile.int_c_var(8001, help_string="server pull port [%(default)d]")),
    ])
    global_config.parse_file()
    VERSION_STRING = "???"
    options = global_config.handle_commandline(description="%s, version is %s" % (prog_name,
                                                                                  VERSION_STRING),
                                               add_writeback_option=True,
                                               positional_arguments=False)
    global_config.write_file()
    sql_info = config_tools.server_check(server_type="mother")
    if global_config["CHECK"]:
        sys.exit(0)
    if global_config["KILL_RUNNING"]:
        log_lines = process_tools.kill_running_processes(prog_name + ".py", exclude=configfile.get_manager_pid())
    cluster_location.read_config_from_db(global_config, "mother", [
        ("TFTP_LINK"                 , configfile.str_c_var("/tftpboot")),
        ("TFTP_DIR"                  , configfile.str_c_var("/usr/local/share/cluster/tftpboot")),
        ("CLUSTER_DIR"               , configfile.str_c_var("/opt/cluster")),
        ("NODE_PORT"                 , configfile.int_c_var(2001)),
        ("SERVER_SHORT_NAME"         , configfile.str_c_var(mach_name))])
    global_config.add_config_entries([
        ("CONFIG_DIR" , configfile.str_c_var("%s/%s" % (global_config["TFTP_DIR"], "config"))),
        ("ETHERBOOT_DIR", configfile.str_c_var("%s/%s" % (global_config["TFTP_DIR"], "etherboot"))),
        ("KERNEL_DIR" , configfile.str_c_var("%s/%s" % (global_config["TFTP_DIR"], "kernels")))])
##    if fixit:
##        process_tools.fix_directories(user, group, [g_config["LOG_DIR"], "/var/lib/mother", "/var/run/mother"])
#    if fixit:
#        process_tools.fix_directories(user, group, [g_config["LOG_DIR"], "/var/lib/mother", "/var/run/mother", g_config["ETHERBOOT_DIR"], g_config["KERNEL_DIR"]])
##    ret_state = 256
##    if num_servers > 1:
##        print "Database error for host %s (mother_server): too many entries found (%d)" % (loc_config["SERVER_SHORT_NAME"], num_servers)
##        dc.release()
##    else:
##        loc_config["LOG_SOURCE_IDX"] = process_tools.create_log_source_entry(dc, loc_config["MOTHER_SERVER_IDX"], "mother", "Mother Server")
##        if not loc_config["LOG_SOURCE_IDX"]:
##            print "Too many log_sources with my id present, exiting..."
##            dc.release()
##        else:
##            loc_config["NODE_SOURCE_IDX"] = process_tools.create_log_source_entry(dc, 0, "node", "Cluster node", "String written by one of the nodes")
##            loc_config["LOG_STATUS"] = process_tools.get_all_log_status(dc)
    process_tools.renice()
    if not global_config["DEBUG"]:
        # become daemon and wait 2 seconds
        process_tools.become_daemon(wait = 2)
        process_tools.set_handles({"out" : (1, "mother.out"),
                                   "err" : (0, "/var/lib/logging-server/py_err")})
    else:
        print "Debugging mother"
    ret_state = server_process().loop()
    sys.exit(ret_state)

if __name__ == "__main__":
    main()
