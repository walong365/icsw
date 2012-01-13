#!/usr/bin/python-init -Ot
# -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2001,2002,2003,2004,2005,2006 Andreas Lang, init.at
#
# Send feedback to: <lang@init.at>
# 
# This file is part of mother
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

## try:
##     import psyco
##     psyco.full()
## except ImportError:
##     pass

import getopt
import msock
import signal
import select
import time
import syslog
import os, os.path
import sys
import thread
import threading
import Queue
import MySQLdb
import re
import shutil
import pty
import configfile
import socket
import commands
import stat
import types
import process_tools
import logging_tools
import mysql_tools
import marshal
import cPickle
import pprint
import server_command
import gzip
import command_stack
import uuid_tools
import md5

from pysnmp.asn1.error import ValueConstraintError
from pysnmp.asn1.encoding.ber.error import TypeMismatchError
from pysnmp.proto.api import alpha
import pysnmp.mapping.udp.error
import pysnmp.proto.api.generic
from pysnmp.error import PySnmpError

try:
    from mother_version import VERSIONSTRING
except ImportError:
    VERSIONSTRING = "?.?"

#SYSLOG_THREAD_TSTR = "syslog-thread-test"
#SYSLOG_THREAD_CSTR = "syslog-thread-check"

LIST_TAGKERNEL = ["installation",
                  "installation_clean",
                  "boot",
                  "boot_normal",
                  "boot_rescue",
                  "boot_clean"]
LIST_DOSBOOT   = ["boot_dos"]
LIST_MEMTEST   = ["memtest"]
LIST_BOOTLOCAL = ["boot_local"]

def start_at_command(com, diff_time="+1 minutes"):
    if os.path.isfile("/etc/redhat-release"):
        pre_time_str = "now "
    else:
        pre_time_str = ""
    log_parts = []
    cstat, cout = commands.getstatusoutput("echo %s | /usr/bin/at %s%s" % (com, pre_time_str, diff_time))
    log_parts.append("Starting command '%s' at time '%s' resulted in (stat %d)" % (com, diff_time, cstat))
    for line in cout.split("\n"):
        log_parts.append("- %s" % (line))
    return cstat, log_parts

def get_size_str(b):
    if b > 1024*1024*1024:
        return "%6.2f GB" % (float(b) / (1024*1024*1024))
    elif b > 1024*1024:
        return "%6.2f MB" % (float(b) / (1024*1024))
    elif b > 1024:
        return "%6.2f kB" % (float(b) / (1024))
    else:
        return "%6d  B" % (b)

def get_error_str():
    exc_info = sys.exc_info()
    return "%s (%s)" % (str(exc_info[0]), str(exc_info[1]))

class pending_req:
    ip_match = re.compile("^(\d+)\.(\d+)\.(\d+)\.(\d+)$")
    def __init__(self, server_command, key, command, sub_states=0):
        self.server_command = server_command
        self.key = key
        self.command = command
        self.__devices = []
        self.__dev_mapping = {}
        # do we have to check sub-states ?
        self.__sub_states = sub_states
        # dictionary [machine]->[ip]->state_of_command
        self.__open_devs = {}
        # dictionary [machine]->[ip]->state_of_sub_command (for example a ping to give a status-warn message)
        self.__open_devs_sub = {}
        # dictionary [machine]->temporary req_state
        self.__dev_temp_req_state = {}
        # locking dictionary [machine]->lock_flag
        self.__dev_locked = {}
        self.__dev_states = {}
    def get_key(self):
        return self.key
    def get_command(self):
        return self.command
    def add_dev(self, dev, log_queue):
        self.__devices.append(dev)
        self.add_dev_mapping(dev)
        my_name = threading.currentThread().getName()
        # examind main dictionaries
        ip_list, mach_name, num_tries = (None, "", 2)
        while num_tries:
            #print "***", mach, num_tries
            num_tries -= 1
            if self.ip_match.match(dev) and devip_dict.has_key(dev):
                #print "IP %s to %s" % (command, mach)
                mach_name = devip_dict[dev].name
                ip_list = [dev]
                break
            elif devname_dict.has_key(dev):
                #print "Name %s to %s" % (command, mach)
                mach_name = dev
                ip_list = devname_dict[dev].ip_dict.keys()
                if not ip_list:
                    log_queue.put(("L", (my_name, "Empty IP-List for device %s, examining database..." % (mach_name))))
                    database_sync(threading.currentThread().getName(), log_queue, [dev], [])
                    ip_list = devname_dict[dev].ip_dict.keys()
                break
            # check for new machine
            if num_tries:
                log_queue.put(("L", (my_name, "Key %s not found in mach_dict or devname_dict, examining database..." % (dev))))
                database_sync(threading.currentThread().getName(), log_queue, [dev], [])
            else:
                log_queue.put(("L", (my_name, "Key %s not found in mach_dict or devname_dict" % (dev))))
        if ip_list and devname_dict.has_key(mach_name):
            mach_struct = devname_dict[mach_name]
            self.add_dev_mapping(dev, mach_name)
            return ip_list, mach_name, mach_struct
        else:
            log_queue.put(("L", (my_name, "Device %s not found in database" % (dev))))
            return None, None, None
        #self.__dev_mapping[dev] = None
    def get_devices(self):
        return self.__devices
    def add_dev_mapping(self, dev, dev_name=None):
        if dev_name:
            if not self.__open_devs.has_key(dev_name):
                self.__dev_temp_req_state[dev_name] = {}
                self.__open_devs[dev_name] = {}
                self.__dev_locked[dev_name] = 1
                self.__open_devs_sub[dev_name] = {}
        self.__dev_mapping[dev] = dev_name
    def dev_is_locked(self, dev_name):
        return self.__dev_locked[dev_name]
    def unlock_device(self, dev_name):
        self.__dev_locked[dev_name] = 0
    def set_dev_temp_req_state(self, dev_name, what):
        self.__dev_temp_req_state[dev_name] = what
    def get_dev_temp_req_state(self, dev_name):
        return self.__dev_temp_req_state[dev_name]
    def get_dev_mapping(self):
        return self.__dev_mapping
    def set_dev_state(self, dev_name, state = "not set"):
        self.__dev_states[dev_name] = state
    def get_dev_state(self, dev_name):
        return self.__dev_states[dev_name]
    def clear_dev_ip_state(self, dev_name, ip):
        #print "*", dev_name, ip
        self.__open_devs[dev_name][ip] = 0
        self.clear_dev_ip_sub_state(dev_name, ip)
    def clear_dev_ip_sub_state(self, dev_name, ip):
        #print "sdiss", dev_name, ip, stat
        self.__open_devs_sub[dev_name][ip] = 0
    def set_dev_ip_state(self, dev_name, ip, stat):
        #print "*", dev_name, ip
        self.__open_devs[dev_name][ip] = stat
    def set_dev_ip_sub_state(self, dev_name, ip, stat = 0):
        #print "sdiss", dev_name, ip, stat
        self.__open_devs_sub[dev_name][ip] = stat
    def device_ip_in_request(self, dev_name, ip):
        return (ip in self.__open_devs[dev_name])
    def any_state_set_ok(self, dev_name):
        return (max(self.__open_devs[dev_name].values()) == 1)
    def all_states_set_and_error(self, dev_name):
        return (max(self.__open_devs[dev_name].values()) == -1)
    def any_sub_states_set_and_ok(self, dev_name):
        #print dev_name, max(self.__open_devs_sub[dev_name].values())
        return (max(self.__open_devs_sub[dev_name].values()) == 1)
    def all_sub_states_set(self, dev_name):
        # returns 1(TRUE) if all sub_states are set (error or ok) or any sub_state is ok or no sub_states are being used
        return (not self.__sub_states or len(self.__open_devs_sub[dev_name]) == 0 or len([x for x in self.__open_devs_sub[dev_name].values() if not x]) == 0 or (1 in self.__open_devs_sub[dev_name].values()))
    def all_states_set(self):
##         # returns 1 if all main-states for all devices are set and {no sub-states are open for error-states in main checks}
        # check if there are any locked devices
        return max(self.__dev_locked.values() + [0]) == 0

class machine:
    #def __init__(self, name, idx, ips={}, log_queue=None):
    def __init__(self, name, idx, log_queue, dc):
        # copy verbose-level
        self.verbose = g_config["VERBOSE"]
        # machine name
        self.name = name
        # set log_queue
        self.set_log_queue(log_queue)
        # clear reachable flag
        self.set_reachable_flag(False)
        # init locking structure
        self.init_lock()
        # machine idx
        self.device_idx = idx
        # add to global devname_dict
        if not devname_dict.has_key(self.name):
            devname_dict[self.name] = self
            self.log("Added myself to devname_dict")
        # ip dictionary; ip->networktype
        self.ip_dict = {}
        #self.set_ip_dict(ips)
        # actual net [(P)roduction, (M)aintenance, (T)est or (O)ther] / IP-address
        self.__act_net, self.__act_ip = ("?", "?")
        # usefull initial values
        self.__last_ip_set, self.__last_ip_ok_set = (time.time() - g_config["DEVICE_MONITOR_TIME"],
                                                     time.time() + g_config["DEVICE_REBOOT_TIME"])
        # boot netdevice, driver for boot netdevice and options
        self.bootnetdevice_name, self.boot_netdriver, self.ethtool_options, self.boot_netdriver_options = (None, None, 0, "")
        # maintenance ip address (and hex) (also sets the node-flag)
        self.set_maint_ip()
        # init hwi delay_counter
        self.clear_hwi_delay_counter()
        self.set_use_count()
        self.check_network_settings(dc)
        self.set_recv_req_state()
        self.set_device_mode()
    def set_device_mode(self, dm=0):
        self.__device_mode = dm
        self.log("Setting device_mode to %s and updating ip_ok_time" % {0 : "no check",
                                                                        1 : "auto reboot (sw)",
                                                                        2 : "auto reboot (hw)"}[self.__device_mode])
        self.__last_ip_ok_set = time.time()
    def get_device_mode(self):
        return self.__device_mode
    def set_reachable_flag(self, r):
        self.__reachable = r
    def get_reachable_flag(self):
        return self.__reachable
    def get_name(self):
        return self.name
    def set_use_count(self, val=0):
        self.use_count = val
        if self.verbose:
            self.log("Setting use_count to %d" % (self.use_count))
    def incr_use_count(self, why=None, incr=1):
        self.use_count += incr
        if self.verbose:
            self.log("incrementing use_count to %d (%s)" % (self.use_count, why or "<unknown>"))
    def decr_use_count(self, why=None, decr=1):
        self.use_count -= decr
        if self.verbose:
            self.log("decrementing use_count to %d (%s)" % (self.use_count, why or "<unknown>"))
    def get_use_count(self):
        return self.use_count
    def device_log_entry(self, user, status, what, sql_queue, log_source="node"):
        if type(log_source) == type(""):
            log_src_idx = log_sources[log_source]["log_source_idx"]
        else:
            log_src_idx = log_source
        sql_queue.put(("S", ("IV", "devicelog", mysql_tools.get_device_log_entry(self.device_idx, log_src_idx, user, log_status[status]["log_status_idx"], what))))
    def clear_hwi_delay_counter(self):
        self.hwi_delay_counter = 0
    def incr_hwi_delay_counter(self):
        self.hwi_delay_counter += 1
    def get_hwi_delay_counter(self):
        return self.hwi_delay_counter
    def set_log_queue(self, log_queue):
        self.log_queue = log_queue
    def log(self, what, glob=0):
        if self.log_queue:
            if glob == 0 or glob == 2:
                self.log_queue.put(("L", (threading.currentThread().getName(), what, self.name)))
            if glob > 0:
                self.log_queue.put(("L", (threading.currentThread().getName(), what)))
        else:
            print "Log for machine %s: %s" % (self.name, what)
    def set_lock(self, why):
        # locks are mapped to lock-classes (for instance, a device can be locked by a refresh_hwi-lock AND a status-lock
        lock_class = self.lock_mapping.get(why, "general")
        self.lock[lock_class] = why
        if self.verbose:
            self.log("Setting lock to %s (class %s)" % (str(why), lock_class))
        self.incr_use_count("lock %s" % (why))
    def init_lock(self):
        self.lock_mapping = {"refresh_hwi"     : "hwi_lock",
                             "refresh_hwi2"    : "hwi_lock",
                             "resync_config"   : "net_lock",
                             "restart_network" : "net_lock",
                             "readdots"        : "readfile_lock",
                             "apc_com"         : "apc_lock",
                             "apc_com2"        : "apc_lock",
                             "apc_dev"         : "apc_lock",
                             "apc_dev2"        : "apc_lock"}
        if self.verbose:
            self.log("Init locking-structure")
        self.lock = {"general" : None}
        for x in self.lock_mapping.values():
            self.lock.setdefault(x, None)
    def get_lock(self, why):
        lock_class = self.lock_mapping.get(why, "general")
        return self.lock[lock_class]
    def release_lock(self, why):
        lock_class = self.lock_mapping.get(why, "general")
        if self.lock.has_key(lock_class):
            if not self.lock[lock_class]:
                self.log("*** error lock-class %s (%s) already released" % (lock_class, str(why)))
            else:
                self.lock[lock_class] = None
                if self.verbose:
                    self.log("Releasing lock (%s, lock_class %s)" % (str(why), lock_class))
        else:
            self.log("*** error trying to release nonexistent lock-class %s (%s)" % (lock_class, str(why)))
        self.decr_use_count("lock %s" % (why))
    def check_network_settings(self, dc):
        dc.execute("SELECT d.bootnetdevice, d.bootserver, d.reachable_via_bootserver, nd.macadr,nd.devname,nd.ethtool_options,nd.driver,nd.driver_options,ip.ip,ip.network,nt.identifier,nw.postfix,nw.identifier as netident,nw.network_type,nd.netdevice_idx FROM device d, netip ip, netdevice nd, network nw, network_type nt WHERE ip.netdevice=nd.netdevice_idx AND nd.device=d.device_idx AND ip.network=nw.network_idx AND nw.network_type=nt.network_type_idx AND nt.identifier != 's' AND d.name='%s' AND d.bootserver=%d ORDER BY nd.devname,ip.ip" % (self.name, mother_server_idx))
        net_dict = {}
        bootnetdevice, bootnetdevice_name = (None, None)
        dev_upd_stuff = []
        loc_ip_dict = {}
        dev_updated = False
        for x in dc.fetchall():
            self.set_reachable_flag(x["reachable_via_bootserver"] and True or False)
            if x["bootnetdevice"] == x["netdevice_idx"]:
                bootnetdevice, bootnetdevice_name = (x["bootnetdevice"], x["devname"].split(":", 1)[0])
            #print "bs for %s : %d" % (self.name, x["bootserver"]), mother_server_idx
            net_dict.setdefault(x["netdevice_idx"], {"devname"         : x["devname"],
                                                     "driver"          : x["driver"],
                                                     "driver_options"  : x["driver_options"],
                                                     "ethtool_options" : x["ethtool_options"],
                                                     "netdevice_idx"   : x["netdevice_idx"],
                                                     "ipl"             : {}})["ipl"].setdefault(x["ip"], [x["ip"], x["macadr"], x["network"], x["identifier"], x["netident"], x["postfix"]])
        if net_dict:
            netok_list = []
            src_str_s = " OR ".join(["h.s_netdevice=%d" % (x) for x in glob_net_devices.keys()])
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
                    for server_ip in [glob_net_devices[x] for x in rev_dict[ndev_idx]]:
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
                                       ("l", ("%s/%s" % (g_config["ETHERBOOT_DIR"], self.name), self.maint_ip))])
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
                self.log("Cannot add device %s (empty ip_list -> cannot reach host)" % (self.name), 2)
        else:
            self.log("refuse to add device without netdevices")
            self.log_queue.put(("L", (threading.currentThread().getName(), "refuse to add device %s without netdevices" % (self.name))))
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
                del devip_dict[act_key]
        for act_key in ips.keys():
            if not self.ip_dict.has_key(act_key):
                self.log("Adding ip %s to IP-dictionary" % (act_key))
                devip_dict[act_key] = self
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
                        self.log("  ...something went wrong for mkdir(): %s" % (get_error_str()))
            elif pt == "l":
                if type(ps) == type(""):
                    dest = self.name
                else:
                    ps, dest = ps
                create_link = 0
                if not os.path.islink(ps):
                    create_link = 1
                else:
                    if os.path.exists(ps):
                        old_dest = os.readlink(ps)
                        if old_dest != dest:
                            try:
                                os.unlink(ps)
                            except OSError:
                                self.log("  ...something went wrong for unlink(): %s" % (get_error_str()))
                            else:
                                self.log(" removed wrong link (%s pointed to %s instead of %s)" % (ps, old_dest, dest))
                                create_link = 1
                    else:
                        pass
                if create_link:
                    if os.path.exists(ps):
                        try:
                            self.log("pla(): Unlink %s" % (ps))
                            os.unlink(ps)
                        except:
                            self.log("  ...something went wrong for unlink(): %s" % (get_error_str()))
                        try:
                            self.log("pla(): rmtree %s" % (ps))
                            shutil.rmtree(ps, 1)
                        except:
                            self.log("  ...something went wrong for rmtree(): %s" % (get_error_str()))
                    try:
                        self.log("pla(): symlink from %s to %s" % (ps, dest))
                        os.symlink(dest, ps)
                    except:
                        self.log("  ...something went wrong for symlink(): %s" % (get_error_str()))
    def set_bootnetdevice_name(self, bdev=None):
        if self.bootnetdevice_name != bdev:
            self.log("Changing bootnetdevice_name from '%s' to '%s'" % (self.bootnetdevice_name, bdev))
            self.bootnetdevice_name = bdev
    def set_maint_ip(self, ip=None, mac=None):
        if ip:
            hex_ip = "".join(["%02X"%int(x) for x in ip.split(".")])
            if self.maint_ip != ip or self.maint_mac != mac:
                self.log("Changing maintenance IP and MAC from %s (%s) [%s] to %s (%s) [%s] and setting node-flag" % (self.maint_ip, self.maint_ip_hex, self.maint_mac, ip, hex_ip, mac))
                self.node = 1
                self.maint_ip = ip
                self.maint_ip_hex = hex_ip
                self.maint_mac = mac
        else:
            self.log("Clearing maintenance IP and MAC (and node-flag)")
            self.maint_ip = None
            self.maint_ip_hex = None
            self.maint_mac = None
            self.node = 0
    def set_boot_netdriver(self, driver="eepro100", ethtool_options=0, options=""):
        if driver != self.boot_netdriver or ethtool_options != self.ethtool_options or options != self.boot_netdriver_options:
            self.log("Changing boot_netdriver/ethtool_options/netdriver_options from '%s / %d / %s' to '%s / %d / %s'" % (str(self.boot_netdriver), self.ethtool_options, str(self.boot_netdriver_options), str(driver), ethtool_options, str(options)))
        self.boot_netdriver = driver
        self.ethtool_options = ethtool_options
        self.boot_netdriver_options = options
    def set_req_state(self, what, sql_queue):
        self.req_state = what
        sql_queue.put(("S", ("U", "device", "reqstate='%s' WHERE name='%s'" % (MySQLdb.escape_string(what.strip()), self.name))))
    def set_recv_state(self, what, sql_queue):
        self.recv_state = what
        sql_queue.put(("S", ("U", "device", "recvstate='%s' WHERE name='%s'" % (MySQLdb.escape_string(what.strip()), self.name))))
    def get_recv_req_state(self):
        return self.recv_state, self.req_state
    def set_recv_req_state(self, recv_state = "not set", req_state="not set"):
        self.recv_state, self.req_state = (recv_state, req_state)
    def get_act_net(self):
        return self.__act_net
    def get_act_ip(self):
        return self.__act_ip
    def get_last_ip_set(self):
        return self.__last_ip_set
    def get_last_ip_ok_set(self):
        return self.__last_ip_ok_set
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
        for table, del_field in [("pci_entry", "device_idx"), ("hw_entry", "device")]:
            sql_str = "DELETE FROM %s WHERE %s=%d" % (table, del_field, self.device_idx)
            try:
                dc.execute(sql_str)
            except:
                self.log("  Error clearing data from table %s" % (table))
    def insert_hardware_info(self, dc, ret_str, sql_queue):
        mac_change = 0
        self.clear_hardware_info(dc)
        self.log("Saving hardware-info from string with len %d (first 3 Bytes: '%s')" % (len(ret_str), ret_str[0:min(3, len(ret_str))]))
        if ret_str.startswith("ok"):
            try:
                hwi_res = server_command.net_to_sys(ret_str[3:])
            except:
                loc_error, ret_str = (1, "unpacking dictionary")
            else:
                loc_error, ret_str = (0, "update successful")
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
                                    sql_parts = [("domain", "%d" % (domain)),
                                                 ("bus"   , "%d" % (bus)),
                                                 ("slot"  , "%d" % (slot)),
                                                 ("func"  , "%d" % (func))]
                                    for key in [x for x in act_s.keys() if x not in [y[0] for y in sql_parts]]:
                                        value = act_s[key]
                                        if type(value) == type(""):
                                            sql_parts.append((key, "'%s'" % (mysql_tools.my_escape(value))))
                                        else:
                                            sql_parts.append((key, "%d" % (value)))
                                    sql_queue.put(("S", ("IS", "pci_entry", "device_idx=%d,%s" % (self.device_idx, ",".join(["%s=%s" % (x[0], x[1]) for x in sql_parts])))))
                                    num_pci += 1
                    try:
                        hw_dict = server_command.net_to_sys(hwi_res["mach"][3:])
                    except:
                        self.log("  error unpickling mach-dict ")
                        hw_dict = {}
                    else:
                        pass
                else:
                    hw_dict = hwi_res
                sql_str = "SELECT ht.hw_entry_type_idx, ht.identifier FROM hw_entry_type ht"
                dc.execute(sql_str)
                hw_e_dict = {}
                for stuff in dc.fetchall():
                    hw_e_dict[stuff["identifier"]] = stuff["hw_entry_type_idx"]
                sql_array = []
                # handle cpus
                if hw_dict.has_key("cpus"):
                    # new style
                    for cpu in hw_dict["cpus"]:
                        if cpu["type"].lower() == "uml":
                            sql_array.append(("cpu", "0", "null", "'%s'" % (cpu["type"]), "null"))
                        else:
                            sql_array.append(("cpu", "%d" % (int(float(cpu["speed"]))), "null", "'%s'" % (cpu["type"]), "null"))
                else:
                    # old style
                    for cpunum in range(hw_dict["num_cpus"]):
                        sql_array.append(("cpu", hw_dict["cpu_speed"], "null", "'%s'" % (hw_dict["cpu_type"]), "null"))
                # gfx-card
                if hw_dict.has_key("gfx"):
                    sql_array.append(("gfx", "null", "null", "'%s'" % (hw_dict["gfx"]), "null"))
                if hw_dict.has_key("mem_total") and hw_dict.has_key("swap_total"):
                    sql_array.append(("mem", "%d" % (hw_dict["mem_total"]), "%d" % (hw_dict["swap_total"]), "null", "null"))
                if hw_dict.has_key("rw_size") and hw_dict.has_key("num_rw"):
                    if hw_dict["num_rw"]:
                        sql_array.append(("disks", "%d" % (hw_dict["num_rw"]), "%d" % (hw_dict["rw_size"]), "null", "null"))
                if hw_dict.has_key("num_ro"):
                    if hw_dict["num_ro"]:
                        sql_array.append(("cdroms", "%d" % (hw_dict["num_ro"]), "null", "null", "null"))
                for stuff in sql_array:
                    sql_queue.put(("S", ("IV", "hw_entry", "0,%d,%d,%s,null" % (self.device_idx, hw_e_dict[stuff[0]], ",".join(stuff[1:])))))
                    num_hw += 1
                nn_changed = []
                if hwi_res.has_key("mac"):
                    mac_dict = server_command.net_to_sys(hwi_res["mac"][3:])
                    sql_str = "SELECT n.devname,n.netdevice_idx,n.macadr,n.fake_macadr FROM netdevice n WHERE n.device=%d" % (self.device_idx)
                    dc.execute(sql_str)
                    for x in dc.fetchall():
                        # check for altered macadress (ignoring fake_macaddresses)
                        if mac_dict.has_key(x["devname"]) and (x["macadr"] != mac_dict[x["devname"]] and x["fake_macadr"] != mac_dict[x["devname"]]):
                            nn_changed.append(x["devname"])
                            self.log("  - set macadr of %s to %s" % (x["devname"], mac_dict[x["devname"]]))
                            dc.execute("UPDATE netdevice SET macadr='%s' WHERE netdevice_idx=%d" % (mac_dict[x["devname"]], x["netdevice_idx"]))
                self.log("  inserted %d pci-entries and %d hw-entries, corrected %d MAC-addresses (%s)" % (num_pci, num_hw, len(nn_changed), ", ".join(nn_changed)))
                mac_change = len(nn_changed)
        else:
            loc_error, ret_str = (1, "return string does not start with ok")
        self.log("  returning with %d (%s)" % (loc_error, ret_str))
        return loc_error, ret_str, mac_change
    def get_pxe_file_name(self):
        return "%s/pxelinux.0" % (self.get_etherboot_dir())
    def get_net_file_name(self):
        return "%s/bootnet" % (self.get_etherboot_dir())
    def get_etherboot_dir(self):
        if self.maint_ip:
            return "%s/%s" % (g_config["ETHERBOOT_DIR"], self.maint_ip)
        else:
            return None
    def get_pxelinux_dir(self):
        if self.maint_ip:
            return "%s/%s/pxelinux.cfg" % (g_config["ETHERBOOT_DIR"], self.maint_ip)
        else:
            return None
    def get_config_dir(self):
        if self.maint_ip:
            return "%s/%s" % (g_config["CONFIG_DIR"], self.maint_ip)
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
                    self.log("*** error removing pxe-boot file %s" % (entry))
                else:
                    self.log("removing pxe-boot file %s" % (entry))
    def write_netboot_config(self):
        ether_pf = "/usr/lib/etherboot"
        mcdir = "%s/%s/" % (g_config["CONFIG_DIR"], self.maint_ip)
        if os.path.isdir(mcdir):
            lilo_nb_f = file("%s/netboot_lilo" % (mcdir), "w")
            disk_nb_f = file("%s/netboot_disk" % (mcdir), "w")
            if self.boot_netdriver:
                netdrv_name = self.boot_netdriver
                self.log("Network-driver defined for NET-boot is %s" % (netdrv_name))
            else:
                netdrv_name = "eepro100"
                self.log("No network-driver defined for NET-boot, using %s" % (netdrv_name))
            for what_f, dir_name in [(disk_nb_f, "dsk"),
                                     (lilo_nb_f, "zlilo")]:
                src_name = "%s/%s/%s.%s" % (ether_pf, dir_name, netdrv_name, dir_name)
                if os.path.isfile(src_name):
                    what_f.write(file(src_name, "r").read())
                else:
                    self.log("*** sourcefile %s not found" % (src_name))
                what_f.close()
    def write_dosboot_config(self, eepro100_pxe):
        os.symlink("../../images/dos_image", self.get_net_file_name())
        file(self.get_pxe_file_name(), "w").write(eepro100_pxe)
    def write_memtest_config(self):
        pxe_dir = self.get_pxelinux_dir()
        if pxe_dir:
            if os.path.isdir(pxe_dir):
                self.clear_ip_mac_files()
                file(self.get_ip_file_name()    , "w").write("DEFAULT ../../images/memtest.bin\n")
                file(self.get_ip_mac_file_name(), "w").write("DEFAULT ../../images/memtest.bin\n")
                if (os.path.isdir(self.get_etherboot_dir())):
                    file(self.get_pxe_file_name(), "w").write(g_config["PXELINUX_0"])
        else:
            self.log("*** pxelinux_dir() returned NONE")
    def write_localboot_config(self):
        if self.get_pxelinux_dir():
            if os.path.isdir(self.get_pxelinux_dir()):
                self.clear_ip_mac_files()
                for name in [self.get_ip_file_name(), self.get_ip_mac_file_name()]:
                    file(name, "w").write("\n".join(["DEFAULT linux",
                                                     "LABEL linux",
                                                     "IMPLICIT 0",
                                                     "LOCALBOOT 0",
                                                     ""]))
                file(self.get_pxe_file_name(), "w").write(g_config["PXELINUX_0"])
    def get_append_line(self, k_append):
        return "root=0100 rw init=/linuxrc nbd=%s,%s,%d,%s %s" % (self.bootnetdevice_name, self.boot_netdriver, self.ethtool_options, self.boot_netdriver_options.replace(" ", r"§"), k_append)
    def write_kernel_config(self, sql_queue, kernel_name, kernel_append, s_ip, s_netmask, check=0):
        kern_dst_dir = self.get_etherboot_dir()
        if kern_dst_dir:
            if os.path.isdir(kern_dst_dir):
                for file_name in ["i", "k"]:
                    fname = "%s/%s" % (kern_dst_dir, file_name)
                    if not check:
                        if os.path.islink(fname):
                            os.unlink(fname)
                for stage_name in ["stage2", "stage3"]:
                    stage_source = "/usr/local/cluster/lcs/%s" % (stage_name)
                    stage_dest  ="%s/%s" % (kern_dst_dir, stage_name)
                    if not os.path.isfile(stage_source):
                        self.log("Error, cannot find %s_source '%s'..." % (stage_name, stage_source))
                    elif not os.path.isfile(stage_dest) or (os.path.isfile(stage_dest) and os.stat(stage_source)[stat.ST_MTIME] > os.stat(stage_dest)[stat.ST_MTIME]):
                        self.log("Copying %s from %s to %s ..." % (stage_name, stage_source, stage_dest))
                        file(stage_dest, "w").write(file(stage_source, "r").read())
                kern_base_dir = "../../kernels/%s" % (kernel_name)
                kern_abs_base_dir = "%s/kernels/%s" % (g_config["TFTP_DIR"], kernel_name)
                if os.path.isdir(kern_abs_base_dir):
                    for abs_src, src, dst in [("%s/bzImage" % (kern_abs_base_dir)  , "%s/bzImage" % (kern_base_dir)  , "%s/k" % (kern_dst_dir)),
                                              ("%s/initrd.gz" % (kern_abs_base_dir), "%s/initrd.gz" % (kern_base_dir), "%s/i" % (kern_dst_dir))]:
                        if os.path.isfile(abs_src):
                            c_link = 1
                            if check:
                                if os.path.islink(dst):
                                    act_dst = os.readlink(dst)
                                    if src == act_dst:
                                        self.log("Link %s is still valid (points to %s)" % (dst, act_dst))
                                        c_link = 0
                                    else:
                                        os.unlink(dst)
                                elif os.path.isfile(dst):
                                    os.unlink(dst)
                            if c_link:
                                #print "symlink()", src, dst
                                os.symlink(src, dst)
                        else:
                            self.log("Error: source %s for symlink() does not exist" % (abs_src))
                            if check:
                                if os.path.islink(dst):
                                    os.unlink(dst)
                else:
                    self.log("Error: source_kernel_dir %s does not exist" % (kern_abs_base_dir))
                    self.device_log_entry(0, "e", "error kernel_dir dir '%s' not found" % (kern_abs_base_dir), sql_queue, log_source_idx)
                append_string = self.get_append_line(kernel_append)
                self.clear_ip_mac_files([self.get_ip_mac_file_base_name()])
                total_append_string = "initrd=i ip=%s:%s::%s %s" % (self.maint_ip, s_ip, shorten_netmask(s_netmask), append_string)
                pxe_lines = []
                if g_config["NODE_BOOT_DELAY"]:
                    pxe_lines.extend(["TIMEOUT %d" % (g_config["NODE_BOOT_DELAY"]),
                                      "PROMPT 1"])
                pxe_lines.extend(["DISPLAY menu",
                                  "LABEL linux",
                                  "    KERNEL k",
                                  "    APPEND %s" % (total_append_string),
                                  ""])
                if g_config["FANCY_PXE_INFO"]:
                    menu_lines = ["\x0c\x0f20%s\x0f07" % (("init.at Bootinfo, %s%s" % (time.ctime(), 80*" "))[0:79])]
                else:
                    menu_lines = ["",
                                  ("init.at Bootinfo, %s%s" % (time.ctime(), 80*" "))[0:79]]
                menu_lines.extend(["Name / IP      : %-30s, %s" % (self.get_name(), self.maint_ip),
                                   "Server / IP    : %-30s, %s" % (short_host_name, s_ip),
                                   "Netmask        : %s (%s)" % (s_netmask, shorten_netmask(s_netmask)),
                                   "MACAddress     : %s" % (self.maint_mac.lower()),
                                   "Kernel to boot : %s" % (kernel_name),
                                   "Kernel options : %s" % (append_string),
                                   "will boot %s" % (g_config["NODE_BOOT_DELAY"] and "in %s" % (logging_tools.get_plural("second", int(g_config["NODE_BOOT_DELAY"]/10))) or "immediately"),
                                   "",
                                   ""])
                file(self.get_ip_file_name()    , "w").write("\n".join(pxe_lines))
                file(self.get_ip_mac_file_name(), "w").write("\n".join(pxe_lines))
                file(self.get_menu_file_name()  , "w").write("\n".join(menu_lines))
                if g_config["PXEBOOT"]:
                    file(self.get_pxe_file_name(), "w").write(g_config["PXELINUX_0"])
            else:
                self.log("Error: directory %s does not exist" % (kern_dst_dir))
                self.device_log_entry(1, "e", "error etherboot dir '%s' not found" % (kern_dst_dir), sql_queue)
        else:
            self.log("Error: etherboot-dir not defined")

def shorten_netmask(msk):
    return {"255.255.255.0" : "C", "255.255.0.0" : "B", "255.0.0.0" : "A"}.get(msk, msk)

class outlet:
    def __init__(self, number=0):
        self.number = number
        self.v_dict = {}
        for k, dv in [("state"            , "?"),
                      ("name"             , "not used"),
                      ("power_on_delay"   , 0),
                      ("power_off_delay"  , 0),
                      ("reboot_delay"     , 0),
                      ("t_power_on_delay" , 0),
                      ("t_power_off_delay", 0),
                      ("t_reboot_delay"   , 5),
                      ("slave_device"     , 0),
                      ("idx"              , 0),
                      ("apc_type"         , "")]:
            self[k] = dv
    def get_number(self):
        return self.number
    def __setitem__(self, key, value):
        self.v_dict[key] = value
    def __getitem__(self, key):
        return self.v_dict[key]
    
class apc(machine):
    def __init__(self, name, idx, log_queue, dc):
        machine.__init__(self, name, idx, log_queue, dc)
        # get apc_device
        dc.execute("SELECT * FROM apc_device WHERE device=%d" % (self.device_idx))
        if dc.rowcount:
            self.log("apc_device struct found")
            self.__apc_device_idx = dc.fetchone()["apc_device_idx"]
        else:
            self.log("Creating apc_device struct")
            dc.execute("INSERT INTO apc_device SET device=%d" % (self.device_idx))
            self.__apc_device_idx = dc.insert_id()
        # error dictionary
        self.error_dict = {}
        # pending transfer ids
        self.pending_send_ids = {}
        # pending return keys
        self.pending_ret_keys = {}
        # info strings
        self.pending_info_strs = {}
        self.outlets = {}
        zero_outlet = outlet(0)
        self.outlets[zero_outlet.get_number()] = zero_outlet
        for i in range(1, 9):
            new_outlet = outlet(i)
            self.outlets[new_outlet.get_number()] = new_outlet
    def add_pending_double(self, snmp_com, send_id, loc_key, mibs, mib_types, mib_values, info_strs):
        self.pending_send_ids[send_id] = loc_key
        if not self.pending_ret_keys.has_key(loc_key):
            self.error_dict[loc_key] = 0
            self.pending_ret_keys[loc_key] = {}
            self.pending_info_strs[loc_key] = {}
        self.pending_ret_keys[loc_key][send_id] = mibs
        self.pending_info_strs[loc_key][send_id] = info_strs
        self.log("Adding pending request (%s, send_id %d, loc_key %d, %d mibs, %d pending)" % (snmp_com, send_id, loc_key, len(mibs), self.loc_key_pending(loc_key)))
        if mib_types:
            for line in [" - mib %-40s : %-40s (%s, %s)" % (x, self.mib_to_str(x, 1), y, str(z)) for x, y, z in zip(mibs, mib_types, mib_values)]:
                self.log(line)
        else:
            for line in [" - mib %-40s : %s" % (x, self.mib_to_str(x, 1)) for x in mibs]:
                self.log(line)
        #print "akt (apd):", self.pending_ret_keys, self.pending_send_ids
    def get_info_strs(self, key):
        ret_strs = []
        for s_key, strs in self.pending_info_strs[key].iteritems():
            ret_strs.extend(strs)
        return ret_strs
    def del_pending_double(self, send_id, loc_key, mibs = [], val_dict={}):
        if len(mibs):
            for mib in mibs:
                self.pending_ret_keys[loc_key][send_id].remove(mib)
        else:
            self.error_dict[loc_key] = 1
            try:
                self.pending_ret_keys[loc_key][send_id] = []
            except:
                raise IndexError, "%d %d" % (loc_key, send_id)
        self.log("Request answer (send_id %d, loc_key %d, %s, %d pending)" % (send_id, loc_key, (mibs and "%d mibs" % (len(mibs))) or "error (mo mibs)", self.loc_key_pending(loc_key)))
        for line in [" - mib %-40s: %s [%s]" % (x, self.mib_to_str(x, 1), self.get_mib_val_str(x, val_dict.get(x, "<???>"))[2]) for x in mibs]:
            self.log(line)
        #print "akt (dpd):", self.pending_ret_keys, self.pending_send_ids
    def loc_key_pending(self, loc_key=None):
        if loc_key is not None:
            pending = max([len(x) for x in self.pending_ret_keys[loc_key].values()])
        else:
            pending = 0
            for k, v in self.pending_ret_keys.iteritems():
                pending += len(v.values())
        return pending
    def has_pending_send_id(self, send_id):
        #print "***", send_id, self.pending_send_ids
        if self.pending_send_ids.has_key(send_id):
            return self.pending_send_ids[send_id]
        else:
            return 0
    def del_ret_key(self, ret_key):
        d_tid = [x for x in self.pending_send_ids.keys() if self.pending_send_ids[x] == ret_key]
        for send_id in d_tid:
            del self.pending_send_ids[send_id]
        del self.pending_ret_keys[ret_key]
        del self.pending_info_strs[ret_key]
        del self.error_dict[ret_key]
    def refresh_from_database(self, dc):
        if self.__apc_device_idx:
            sql_str = "SELECT power_on_delay, reboot_delay, apc_type FROM apc_device WHERE apc_device_idx=%d" % (self.__apc_device_idx)
            dc.execute(sql_str)
            set = dc.fetchone()
            for w in ["power_on_delay", "reboot_delay", "apc_type"]:
                self.outlets[0][w] = set[w]
        else:
            self.outlets[0]["apc_type"] = "unknown"
        sql_str = "SELECT m.outlet, m.state, m.t_power_on_delay, m.t_power_off_delay, m.t_reboot_delay, m.slave_device, m.msoutlet_idx AS idx FROM msoutlet m WHERE m.device=%d" % (self.device_idx)
        dc.execute(sql_str)
        if dc.rowcount:
            for set in dc.fetchall():
                outlet = set["outlet"]
                for w in ["state", "t_power_on_delay", "t_power_off_delay", "t_reboot_delay", "slave_device", "idx"]:
                    self.outlets[outlet][w] = set[w]
            self.log("read APC and outlet info from database")
        else:
            self.log("No outlet-info found, waiting for update from APC...")
    def read_names_from_database(self, dc):
        slave_devs = [self.outlets[i]["slave_device"] for i in range(1, 9) if self.outlets[i]["slave_device"]]
        if slave_devs:
            sql_str = "SELECT d.name,m.outlet FROM device d, msoutlet m WHERE m.slave_device=d.device_idx AND (%s)" % (" OR ".join(["d.device_idx=%d" % (x) for x in slave_devs]))
            dc.execute(sql_str)
            for res in dc.fetchall():
                self.outlets[res["outlet"]]["name"] = res["name"]
    def write_to_database(self, dc):
        if self.__apc_device_idx:
            sql_str = "UPDATE apc_device SET power_on_delay=%d, reboot_delay=%d, apc_type='%s' WHERE apc_device_idx=%d" % (self.outlets[0]["power_on_delay"],
                                                                                                                           self.outlets[0]["reboot_delay"],
                                                                                                                           mysql_tools.my_escape(self.outlets[0]["apc_type"]),
                                                                                                                           self.__apc_device_idx)
            dc.execute(sql_str)
        for i in range(1, 9):
            act_out = self.outlets[i]
            if act_out["idx"]:
                sql_str = "UPDATE msoutlet SET state='%s', power_on_delay=%d, power_off_delay=%d, reboot_delay=%d WHERE msoutlet_idx=%d" % (act_out["state"], act_out["power_on_delay"], act_out["power_off_delay"], act_out["reboot_delay"], act_out["idx"])
            else:
                sql_str = "INSERT INTO msoutlet VALUES(0,%d,0,'',%d,'%s',%d,%d,%d,0,0,0,null)" % (self.device_idx, i, act_out["state"], act_out["power_on_delay"], act_out["power_off_delay"], act_out["reboot_delay"])
            #print sql_str
            try:
                dc.execute(sql_str)
            except MySQLdb.Warning, what:
                self.log("+++ MySQL Warning excpetion has been thrown for '%s': %s" % (sql_str, str(what)))
            else:
                if sql_str.startswith("INSERT"):
                    self.outlets[i]["idx"] = dc.insert_id()
        self.log("wrote APC and outlet info to database")
    def update_outlet_after_trap(self, dc, trap_num, trap_dict):
        name_mib = ".1.3.6.1.4.1.318.2.3.3.0"
        #print trap_dict, trap_num
        if trap_dict.has_key(name_mib):
            trap_name = trap_dict[name_mib]
            outlet_num = ([k for k, v in self.outlets.iteritems() if v["name"] == trap_name] + [0])[0]
            if outlet_num and trap_num in [268, 269]:
                act_outlet = self.outlets[outlet_num]
                act_outlet["state"] = {268 : "on",
                                       269 : "off"}[trap_num]
                sql_str = "UPDATE msoutlet SET state='%s' WHERE msoutlet_idx=%d" % (act_outlet["state"],
                                                                                    act_outlet["idx"])
                self.log("Setting outlet %d to state '%s' because of trap (name of outlet: '%s')" % (outlet_num, act_outlet["state"], trap_name))
                dc.execute(sql_str)
        else:
            self.log("Got unknown trap (trap_num %d, trap_dict: %s)" % (trap_num, ", ".join(["%s:%s" % (str(k), str(v)) for k,v in trap_dict.iteritems()])))
    def get_mib_state_str(self, val):
        return {1 : "on",
                2 : "off",
                3 : "reboot",
                4 : "unknown",
                5 : "on*",
                6 : "off*",
                7 : "reboot*"}[val]
    def get_mib_val_str(self, mib, mib_val):
        what, o_num = self.mib_to_str(mib)
        if what == "state":
            mib_val = self.get_mib_state_str(mib_val)
        return what, o_num, mib_val
    def set_mib(self, mib, mib_val):
        what, o_num, val_str = self.get_mib_val_str(mib, mib_val)#self.mib_to_str(mib)
        self.outlets[o_num][what] = val_str
    def mib_to_str(self, mib, simple=0):
        ret_str, o_num = ("???", 0)
        mib_parts = [int(x) for x in mib.split(".") if x]
        if mib.startswith(".1.3.6.1.4.1.318.1.1.4.5.2.1."):
            o_num = mib_parts[-1]
            ret_str = {2 : "power_on_delay", 3 : "name", 4 : "power_off_delay", 5 : "reboot_delay"}[mib_parts[-2]]
        elif mib.startswith(".1.3.6.1.4.1.318.1.1.4.4.2.1.3."):
            o_num = mib_parts[-1]
            ret_str = "state"
        elif mib.startswith(".1.3.6.1.4.1.318.1.1.4.3"):
            ret_str = {1 : "power_on_delay", 2 : "reboot_delay"}[mib_parts[-2]]
        elif mib.startswith(".1.3.6.1.4.1.318.1.1.4.1.4.0"):
            o_num, ret_str = (0, "apc_type")
        elif mib.startswith(".1.3.6.1.4.1.318.2.1.2.1.2."):
            ret_str = "trap receiver %d" % (mib_parts[-1])
        elif mib.startswith(".1.3.6.1.2.1.1."):
            ret_str = {4 : "contact", 5 : "name"}[mib_parts[-2]]
        if simple:
            if o_num:
                return "%s on outlet %d" % (ret_str, o_num)
            else:
                return ret_str
        else:
            return ret_str, o_num
    def gen_command_mib(self):
        return ".1.3.6.1.4.1.318.1.1.4.2.1.0"
    def power_on_delay_mib(self):
        return ".1.3.6.1.4.1.318.1.1.4.3.1.0"
    def reboot_delay_mib(self):
        return ".1.3.6.1.4.1.318.1.1.4.3.2.0"
    def name_mib(self):
        return ".1.3.6.1.2.1.1.5.0"
    def contact_mib(self):
        return ".1.3.6.1.2.1.1.4.0"
    def apc_type_mib(self):
        return ".1.3.6.1.4.1.318.1.1.4.1.4.0"
    def outlet_state_mib(self, num):
        return ".1.3.6.1.4.1.318.1.1.4.4.2.1.3.%d" % (num)
    def outlet_power_on_time_mib(self, num):
        return ".1.3.6.1.4.1.318.1.1.4.5.2.1.2.%d" % (num)
    def outlet_name_mib(self, num):
        return ".1.3.6.1.4.1.318.1.1.4.5.2.1.3.%d" % (num)
    def outlet_power_off_time_mib(self, num):
        return ".1.3.6.1.4.1.318.1.1.4.5.2.1.4.%d" % (num)
    def outlet_reboot_duration_mib(self, num):
        return ".1.3.6.1.4.1.318.1.1.4.5.2.1.5.%d" % (num)
    def trap_receiver_mib(self, num=1):
        return ".1.3.6.1.4.1.318.2.1.2.1.2.%d" % (num)
    def build_snmp_commands(self, com_strs, dbcon, log_queue):
        dbcon.dc.init_logs()
        if type(com_strs) == types.StringType:
            com_strs = [com_strs]
        error, add_snmp_coms = (0, [])
        if self.ip_dict:
            act_ip = self.ip_dict.keys()[0]
            #act_ip = "-1"
            for com_str in com_strs:
                for arg_parts in [x.split("=") for x in com_str.split(":")]:
                    com = arg_parts.pop(0)
                    set_args, get_args = ([], [])
                    set_info_strs, get_info_strs = ([], [])
                    if com == "update":
                        set_info_strs.append("update from db")
                        self.refresh_from_database(dbcon.dc)
                        self.read_names_from_database(dbcon.dc)
                        set_args.extend([(self.name_mib(), "s", self.name), (self.contact_mib(), "s", "lang@init.at")])
                        for i in range(1, 9):
                            set_args.extend([(self.outlet_power_on_time_mib(i),   "i", self.outlets[i]["t_power_on_delay"]),
                                             (self.outlet_power_off_time_mib(i),  "i", self.outlets[i]["t_power_off_delay"]),
                                             (self.outlet_reboot_duration_mib(i), "i", self.outlets[i]["t_reboot_delay"] or 5)])
                            get_args.extend([self.outlet_state_mib(i)])
                            set_args.append((self.outlet_name_mib(i), "s", self.outlets[i]["name"]))
                        get_args.extend([self.power_on_delay_mib(), self.reboot_delay_mib(), self.apc_type_mib()])
                        apc_ip = self.ip_dict.keys()[0]
                        server_ip = self.get_server_ip_addr(apc_ip)
                        if server_ip:
                            set_args.append((self.trap_receiver_mib(), "a", server_ip))
                    elif com == "refresh":
                        get_info_strs.append("refresh from apc")
                        for i in range(1, 9):
                            get_args.extend([self.outlet_power_on_time_mib(i),
                                             self.outlet_power_off_time_mib(i),
                                             self.outlet_reboot_duration_mib(i),
                                             self.outlet_state_mib(i)])
                        get_args.extend([self.power_on_delay_mib(), self.reboot_delay_mib(), self.apc_type_mib()])
                    elif com == "gc":
                        set_info_strs.append("gen_command %d" % (int(arg_parts[0])))
                        set_args.append((self.gen_command_mib()   , "i", int(arg_parts[0])))
                    elif com.startswith("c"):
                        set_info_strs.append("outlet %d to %s" % (int(com[1]), self.get_mib_state_str(int(arg_parts[0]))))
                        set_args.append((self.outlet_state_mib(int(com[1])), "i", int(arg_parts[0])))
                    else:
                        error = 1
                        log_queue.put(("L", (threading.currentThread().getName(), "Got unknown SNMP-command '%s' for apc '%s'" % (com, self.name))))
                    l_a = []
                    if set_args:
                        add_snmp_coms.append((act_ip, set_info_strs, "S", self, ["private"] + set_args))
                        l_a.append(logging_tools.get_plural("set command", len(set_args) / 3))
                    if get_args:
                        add_snmp_coms.append((act_ip, get_info_strs, "G", self, ["public"] + get_args))
                        l_a.append(logging_tools.get_plural("get command", len(get_args) / 2))
                    log_queue.put(("L", (threading.currentThread().getName(), "'%s' resulted in %s" % (",".join(com_strs), " and ".join(l_a)), self.name)))
        else:
            error = 1
        return error, add_snmp_coms
            
    
class snmp_dispatcher:
    def __init__(self, net_server, dest_queue, log_queue, timeout=10.):
        self.pending = {}
        self.log_queue = log_queue
        self.ticket_num = 0
        self.dest_queue = dest_queue
        self.set_timeout(timeout)
        self.udp_sock = net_server.new_udp_socket({"r" : self.dest_queue, "e" : self.dest_queue, "l" : self.dest_queue})
    def log(self, what):
        self.log_queue.put(("L", (threading.currentThread().getName(), what)))
    def fileno(self):
        return self.udp_sock.fileno()
    def set_timeout(self, timeout=10.):
        self.timeout = timeout
    def get_ticket_num(self):
        self.ticket_num += 1
        return self.ticket_num
    def send_set(self, dst, args, got_hook=None, port=161):
        ver = alpha.protoVersions[alpha.protoVersionId1]
        req = ver.Message()
        req.apiAlphaSetCommunity(args[0])
        req.apiAlphaSetPdu(ver.SetRequestPdu())
        s_arg = []
        for mib, type, val in args[1:]:
            if type == "i":
                s_arg.append((mib, ver.Integer(val)))
            elif type == "a":
                s_arg.append((mib, ver.IpAddress(val)))
            else:
                s_arg.append((mib, ver.OctetString(val)))
        req.apiAlphaGetPdu().apiAlphaSetVarBindList(*s_arg)
        self.udp_sock.sendto(req.berEncode(), (dst, port))
        self.ticket_num += 1
        self.pending[self.ticket_num] = (req, (dst, port), time.time() + self.timeout)
        return self.ticket_num
    def send_get(self, dst, args, got_hook=None, port=161):
        ver = alpha.protoVersions[alpha.protoVersionId1]
        req = ver.Message()
        req.apiAlphaSetCommunity(args[0])
        req.apiAlphaSetPdu(ver.GetRequestPdu())
        req.apiAlphaGetPdu().apiAlphaSetVarBindList(*[(x, ver.Null()) for x in args[1:]])
        self.udp_sock.sendto(req.berEncode(), (dst, port))
        # increment actual ticket number
        self.ticket_num += 1
        self.pending[self.ticket_num] = (req, (dst, port), time.time() + self.timeout)
        return self.ticket_num
    def check_for_timeout(self):
        act_time = time.time()
        d_list = []
        for ticket_num, (req, (dst, port), d_time) in self.pending.iteritems():
            if act_time >= d_time:
                d_list.append(ticket_num)
                self.log("deleting request with ticket_num %d (dst %s, timeout)" % (ticket_num, dst))
                self.dest_queue.put(("mserr", (0, (("X", 0), (dst, port), (110, "timeout")), ticket_num)))
        for d in d_list:
            del self.pending[d]
        #print "%d requests pending" % (len(self.pending)), time.time()
    def num_pending(self):
        return len(self.pending.keys())
    def send_done(self, answer):
        # handles both get and set requestes
        errnum, errstr, ticket_num, ret_dict = (0, "ok", 0, {})
        ver = alpha.protoVersions[alpha.protoVersionId1]
        rsp = ver.Message()
        rsp.berDecode(answer)
        if not errnum:
            for ticket_num, (req, (dst, port), d_time) in self.pending.iteritems():
                rem = 0
                try:
                    if req.apiAlphaMatch(rsp):
                        rem = 1
                except pysnmp.asn1.error.BadArgumentError:
                    pass
                if rem:
                    del self.pending[ticket_num]
                    break
            else:
                errnum, errstr = (1, "WARNING: dropping unmatched (late) response: \n%s" % (str(rsp)))
        if not errnum:
            errorstat = rsp.apiAlphaGetPdu().apiAlphaGetErrorStatus()
            if errorstat:
                errnum, errstr = (1, errorstat)
                ret_dict = errstr
            else:
                for var in rsp.apiAlphaGetPdu().apiAlphaGetVarBindList():
                    oid, val = var.apiAlphaGetOidVal()
                    ret_dict[oid.get()] = val.get()
        return errnum, errstr, ticket_num, ret_dict
    def decode_trap_answer(self, answer):
        trap_num, source_ip, ret_dict, err_str = (0, "", {}, "")
        metareq = alpha.MetaMessage()
        try:
            metareq.decode(answer)
        except TypeMismatchError:
            err_str = "TypeMismatchError: %s (%s)" % (str(sys.exc_info()[0]),
                                                      str(sys.exc_info()[1]))
        else:
            req = metareq.apiAlphaGetCurrentComponent()
            if req.apiAlphaGetPdu().apiAlphaGetPduType() == alpha.trapPduType:
                pdu = req.apiAlphaGetPdu()
                if req.apiAlphaGetProtoVersionId() == alpha.protoVersionId1:
                    enterprise = pdu.apiAlphaGetEnterprise().get()
                    trap_num, source_ip = (int(pdu.apiAlphaGetSpecificTrap().get()),
                                        pdu.apiAlphaGetAgentAddr().get())
                    for varBind in pdu.apiAlphaGetVarBindList():
                        oid, val = varBind.apiAlphaGetOidVal()
                        ret_dict[oid.get()] = val.get()
        return source_ip, trap_num, ret_dict, err_str
        
    #got_hook(error, src, ticket_num, ret_dict)

def snmp_disp_thread(main_queue, log_queue, own_queue, node_queue, net_server, msi_block):
    dbcon = mysql_tools.db_con()
    my_name = threading.currentThread().getName()
    my_pid = os.getpid()
    process_tools.append_pids("mother/mother")
    if msi_block:
        msi_block.add_actual_pid()
        msi_block.save_block()
    log_queue.put(("L", (my_name, "proc %d: %s-thread for mother is now awake" % (my_pid, my_name))))
    cm = snmp_dispatcher(net_server, own_queue, log_queue, g_config["SNMP_MAIN_TIMEOUT"])
    # dictionary, mapping between local key and external key
    ret_key_dict = {}
    # dictionary, mapping between local key and external command (apc_com* or apc_dev*)
    ret_com_dict = {}
    # dictionary, mapping between local key and external device
    ret_dev_dict = {}
    # actual requested timeout
    main_timeout = None
    # udp-socket valid ?
    udp_sock_valid = 0
    # actual local key
    loc_key = 0
    c_flag = 1
    while c_flag:
        mes_type, mes_arg = own_queue.get()
        #print time.time(), mes_type, len(str(mes_arg))
        if mes_type == "I":
            mes_arg, mes_thread = mes_arg
            if mes_arg == "exit":
                c_flag = 0
                break
            elif mes_arg == "update":
                cm.check_for_timeout()
            else:
                print "mes_arg:", mes_arg
        elif mes_type == "SM":
            # commands to add if no error occurs
            # if ret_key is 0 no reply has to be sent
            ret_com, ret_key, ret_device, snmp_dev, snmp_args = mes_arg
            #print "***", mes_arg
            if udp_sock_valid:
                dbcon.dc.init_logs()
                loc_key += 1
                ret_key_dict[loc_key] = ret_key
                ret_com_dict[loc_key] = ret_com
                ret_dev_dict[loc_key] = ret_device
                if devip_dict.has_key(snmp_dev):
                    u_apc = devip_dict[snmp_dev]
                else:
                    u_apc = devname_dict[snmp_dev]
                log_queue.put(("L", (my_name, "key mapping %d (loc) -> %s" % (loc_key, (ret_key_dict[loc_key] and "%d (send reply)" % (ret_key_dict[loc_key])) or "send no reply"), u_apc.name)))
                error, add_snmp_coms = u_apc.build_snmp_commands(snmp_args, dbcon, log_queue)
                if error:
                    node_queue.put(("ER", (ret_com_dict[loc_key], ret_dev_dict[loc_key], 0, "error decoding snmp_coms", ret_key)))
                else:
                    check_devs = []
                    for snmp_ip, snmp_info_strs, snmp_com, act_dev, snmp_args in add_snmp_coms:
                        dev_error = 0
                        if snmp_com == "S":
                            mib_list   = [snmp_args[i][0] for i in range(1, len(snmp_args))]
                            mib_types  = [snmp_args[i][1] for i in range(1, len(snmp_args))]
                            mib_values = [snmp_args[i][2] for i in range(1, len(snmp_args))]
                            #print "SNMP set to %s :" % (snmp_ip), snmp_args
                            try:
                                send_id = cm.send_set(snmp_ip, snmp_args)
                            except (pysnmp.mapping.udp.error.NetworkError, socket.gaierror, socket.error):
                                act_dev.log("Error sending SNMP-set to %s" % (snmp_ip))
                                # insert dummy-double
                                send_id = cm.get_ticket_num()
                                dev_error = 1
                        else:
                            mib_list = [snmp_args[i] for i in range(1, len(snmp_args))]
                            mib_types, mib_values = ([], [])
                            #print "SNMP get from %s :" % (snmp_ip), snmp_args
                            try:
                                send_id = cm.send_get(snmp_ip, snmp_args)
                            except (pysnmp.mapping.udp.error.NetworkError, socket.gaierror, socket.error):
                                act_dev.log("Error sending SNMP-get to %s" % (snmp_ip))
                                # insert dummy-double
                                send_id = cm.get_ticket_num()
                                dev_error = 1
                        act_dev.add_pending_double(snmp_com, send_id, loc_key, mib_list, mib_types, mib_values, snmp_info_strs)
                        if dev_error:
                            act_dev.del_pending_double(send_id, loc_key)
                            if act_dev not in check_devs:
                                check_devs.append(act_dev)
                    for cd in check_devs:
                        if not act_dev.loc_key_pending(loc_key) and loc_key:
                            act_dev.log("set/get-error: Sending reply-string (%s) for snmp-command (loc_key %d, ret_key %d)" % ({0 : "ok",
                                                                                                                                 1 : "error"}[act_dev.error_dict[loc_key]],
                                                                                                                                loc_key,
                                                                                                                                ret_key_dict[loc_key]))
                            if ret_key:
                                node_queue.put(("ER", (ret_com_dict[loc_key],
                                                       ret_dev_dict[loc_key],
                                                       act_dev.error_dict[loc_key],
                                                       "error %s done (%s)" % (act_dev.name, ", ".join(act_dev.get_info_strs(loc_key))),
                                                       ret_key_dict[loc_key])))
                                act_dev.del_ret_key(loc_key)
            else:
                log_queue.put(("L", (my_name, "UDP socket not valid, bouncing message (key %d, snmp_dev %s, com_len %d)" % (ret_key, snmp_dev, len(snmp_args)))))
                own_queue.put(("SM", mes_arg))
        elif mes_type == "mslog":
            fileno, (loc_addr, other_addr, log_str), key = mes_arg
            log_queue.put(("L", (my_name, log_str)))
            if fileno == cm.fileno():
                log_queue.put(("L", (my_name, " - UDP-Socket is now valid")))
                udp_sock_valid = 1
        elif mes_type in ["mserr", "msrcv"]:
            dbcon.dc.init_logs()
            fileno, (loc_addr, other_addr, in_str), key = mes_arg
            if type(loc_addr) == type(()):
                loc_ip, loc_port = loc_addr
            else:
                loc_ip, loc_port = (None, None)
            if loc_port == 162:
                if mes_type == "msrcv":
                    source_ip, trap_num, trap_dict, err_str = cm.decode_trap_answer(in_str)
                    if err_str:
                        log_queue.put(("L", (my_name, "error decoding trap_answer: %s" % (err_str))))
                    elif source_ip and trap_num and trap_dict:
                        if devip_dict.has_key(source_ip):
                            a_apc = devip_dict[source_ip]
                            a_apc.update_outlet_after_trap(dbcon.dc, trap_num, trap_dict)
            else:
                if mes_type == "msrcv":
                    error, errstr, key, ret_dict = cm.send_done(in_str)
                else:
                    try:
                        act_fileno = cm.fileno()
                    except:
                        act_fileno = fileno
                    if fileno == act_fileno:
                        log_queue.put(("L", (my_name, " - re-initializing UDP-Socket")))
                        # try to initialize to socket again
                        del cm
                        cm = snmp_dispatcher(net_server, own_queue, 30)
                        time.sleep(2)
                    error, errstr = in_str
                    ret_dict = None
                # proceed if state is ok or timeout:
                #print error, mes_type
                if other_addr:
                    host, port = other_addr
                    if devip_dict.has_key(host):
                        a_apc = devip_dict[host]
                    else:
                        a_apc = devname_dict[host]
                    if a_apc.loc_key_pending():
                        act_key = a_apc.has_pending_send_id(key)
                        if error:
                            log_queue.put(("L", (my_name, "Error: %s on device %s (port %d)" % (errstr, host, port))))
                            #print "Error:", args
                            # delete all pending requests of actual key
                            a_apc.del_pending_double(key, act_key)
                        else:
                            #print "from %s (key %d):" % (host, key), stuff
                            for mib in ret_dict.keys():
                                # delete references to pending mibs
                                a_apc.del_pending_double(key, act_key, [mib], ret_dict)
                                # save state
                                a_apc.set_mib(mib, ret_dict[mib])
                        if not a_apc.loc_key_pending(act_key):
                            a_apc.write_to_database(dbcon.dc)
                        if act_key:
                            if not a_apc.loc_key_pending(act_key):
                                log_queue.put(("L", (my_name,
                                                     "Sending reply-string (%s) for snmp-command (loc_key %d, ret_key %d)" % ({0 : "ok", 1 : "error"}[a_apc.error_dict[act_key]],
                                                                                                                              act_key,
                                                                                                                              ret_key_dict[act_key]),
                                                     a_apc.name)))
                                node_queue.put(("ER", (ret_com_dict[act_key],
                                                       ret_dev_dict[act_key],
                                                       a_apc.error_dict[act_key],
                                                       "ok %s done (%s)" % (a_apc.name, ", ".join(a_apc.get_info_strs(act_key))),
                                                       ret_key_dict[act_key])))
                                a_apc.del_ret_key(act_key)
                    else:
                        print ret_dict.keys()
                        log_queue.put(("L", (my_name, "Ignoring SNMP-result (error: %d)" % (error), host)))
                else:
                    print loc_addr, other_addr
                    log_queue.put(("L", (my_name, "Got error %d (%s, other_addr not set)" % (error, errstr))))

        else:
            print mes_type, mes_arg
        if cm.num_pending():
            wish_timeout = 2
        else:
            wish_timeout = 30
        if wish_timeout != main_timeout:
            log_queue.put(("L", (my_name, "No SNMP-requests pending")))
            main_queue.put(("I", ("set_timeout %d" % (wish_timeout), my_name)))
            main_timeout = wish_timeout
    log_queue.put(("L", (my_name, "proc %d: %s-thread for mother exiting" % (my_pid, my_name))))
    main_queue.put(("I", ("exiting", my_name)))
    
class command_class:
    # defaults: no spreading, port number is 0, no pre-ping, no tcp-connection, real_command=command
    def __init__(self, name):
        self.com_name = name
        self.set_port()
        self.set_spread()
        self.set_tcp_connection()
        self.set_pre_ping()
        self.set_real_command()
        self.set_parallel_throttling()
        self.set_pending_request()
        self.set_needed_sql_fields()
        # for handling of parallel throttled commands
        self.__devs_added = 0
        self.__actual_delay = 0
        self.delay_dict = {}
    def add_device(self, mach, log_queue, net_server, q_dict):
        ip_list, mach_name, mach_struct = self.pr.add_dev(mach, log_queue)
        c_flag = 0
        if mach_struct:
            if self.get_parallel_throttling():
                if self.__devs_added == g_config["SIMULTANEOUS_REBOOTS"]:
                    self.__devs_added = 0
                    self.__actual_delay += g_config["REBOOT_DELAY"]
            self.__devs_added += 1
            if self.__actual_delay:
                self.pr.set_dev_state(mach_name, "ok delaying %s for %d seconds" % (self.get_name(), self.__actual_delay))
                mach_struct.log("delaying %s for %d seconds" % (self.get_name(), self.__actual_delay))
                self.pr.unlock_device(mach_name)
                self.delay_dict.setdefault(self.__actual_delay, []).append(mach)
            else:
                if not self.get_spread():
                    # only contact the device itself
                    ip_list = [mach]
                if mach_struct.get_lock(self.get_name()):
                    already_used = 0
                    for ip in ip_list:
                        if self.pr.device_ip_in_request(mach_name, ip):
                            already_used = 1
                        else:
                            self.pr.set_dev_ip_state(mach_name, ip, -1)
                    if not already_used:
                        self.pr.set_dev_state(mach_name, "error locked by %s" % (mach_struct.get_lock(self.get_name())))
                        self.pr.unlock_device(mach_name)
                else:
                    mach_struct.set_lock(self.get_name())
                    if hasattr(self, "pre_command"):
                        self.pre_command(mach_struct, q_dict)
                    if self.get_spread():
                        mach_struct.set_actual_ip()
                    self.pr.set_dev_state(mach_name)
                    for ip in ip_list:
                        # clear dev_name-ip state and sub-state
                        self.pr.clear_dev_ip_state(mach_name, ip)
                        if self.get_tcp_connection():
                            act_com = self.get_real_command(self.get_name())
                            mach_struct.log("Sending command %s to %s (port %d)" % (act_com, ip, self.get_port()))
                            net_server.new_tcp_connection({"e" : q_dict["dest"],
                                                           "r" : q_dict["dest"],
                                                           "l" : q_dict["dest"]}, (ip, self.get_port(), act_com), (self.pr.get_key(), act_com), timeout=3.5)
                            if self.get_pre_ping():
                                mach_struct.log("  - adding ping to ip %s" % (ip))
                                net_server.new_ping(ip, self.pr.get_key(), 3, 3.5, {"r" : q_dict["dest"],
                                                                                    "e" : q_dict["dest"]})
                        elif hasattr(self, "post_call"):
                            self.post_call(mach_struct, ip, mach_name, q_dict)
                        else:
                            mach_struct.log("Sending ping to %s" % (ip))
                            # simple ping
                            net_server.new_ping(ip, self.pr.get_key(), 3, 3.5, {"r" : q_dict["dest"],
                                                                                "e" : q_dict["dest"]})
                    c_flag = 1
        if c_flag:
            return ip_list, mach_name, mach_struct
        else:
            return None, None, None
    def handle_sql_requests(self, log_queue, net_server, q_dict):
        if self.__needed_sql_fields:
            sql_str = "SELECT d.name,%s FROM device d WHERE %s" % (",".join(["d.%s" % (x) for x in self.__needed_sql_fields]),
                                                            " OR ".join(["d.name='%s'" % (x) for x in self.pr.get_devices()]))
            q_dict["database"].dc.execute(sql_str)
            for x in q_dict["database"].dc.fetchall():
                if devname_dict.has_key(x["name"]):
                    self.db_change_call(devname_dict[x["name"]], x)
    def set_needed_sql_fields(self, f=[]):
        if type(f) != type([]):
            f = [f]
        self.__needed_sql_fields = f
    def set_pending_request(self, pr=None):
        self.pr = pr
    def get_pending_request(self):
        return self.pr
    def set_parallel_throttling(self, pt=0):
        self.pt = 0
    def get_parallel_throttling(self):
        return self.pt
    def get_name(self):
        return self.com_name
    def set_pre_ping(self, pre_ping=0):
        self.pre_ping = pre_ping
    def get_pre_ping(self):
        return self.pre_ping
    def set_spread(self, spreading=0):
        self.spread = spreading
    def get_spread(self):
        return self.spread
    def set_port(self, port=0):
        self.port = port
    def get_port(self):
        return self.port
    def set_tcp_connection(self, tcp_connection=0):
        self.tcp_connection = tcp_connection
    def get_tcp_connection(self):
        return self.tcp_connection
    def set_real_command(self, rcom=None):
        self.real_command = rcom
    def get_real_command(self, default=""):
        if self.real_command:
            return self.real_command
        else:
            return default
    def __repr__(self):
        return "command %s, port %d, pre_ping %d, spreading %d" % (self.get_name(),
                                                                   self.get_port(),
                                                                   self.get_pre_ping(),
                                                                   self.get_spread())

class ping_command(command_class):
    def __init__(self):
        command_class.__init__(self, "ping")
        self.set_spread(1)
        
class status_command(command_class):
    def __init__(self):
        command_class.__init__(self, "status")
        self.set_spread(1)
        self.set_pre_ping(1)
        self.set_tcp_connection(1)
        self.set_port(2002)

# the difference between reboot and reboot_nd is that if you call reboot (without _nd) with many nodes the reboot
# sequence will be delayed for certain nodes (to reduce the load imposed to the server)
class reboot_command(command_class):
    def __init__(self):
        command_class.__init__(self, "reboot")
        self.set_spread(1)
        self.set_tcp_connection(1)
        self.set_port(2002)
        self.set_parallel_throttling(1)

class halt_command(command_class):
    def __init__(self):
        command_class.__init__(self, "halt")
        self.set_spread(1)
        self.set_tcp_connection(1)
        self.set_port(2002)

class poweroff_command(command_class):
    def __init__(self):
        command_class.__init__(self, "poweroff")
        self.set_spread(1)
        self.set_tcp_connection(1)
        self.set_port(2002)

class reboot_nd_command(command_class):
    def __init__(self):
        command_class.__init__(self, "reboot_nd")
        self.set_spread(1)
        self.set_tcp_connection(1)
        self.set_port(2002)

class refresh_hwi_command(command_class):
    def __init__(self):
        command_class.__init__(self, "refresh_hwi")
        self.set_spread(1)
        self.set_tcp_connection(1)
        self.set_port(2001)
        self.set_real_command("hwinfo --raw")
    def pre_command(self, mach_struct, q_dict):
        mach_struct.clear_hardware_info(q_dict["database"].dc)

class readdots_command(command_class):
    def __init__(self):
        command_class.__init__(self, "readdots")
    def post_call(self, mach_struct, ip, mach_name, q_dict):
        q_dict["config"].put(("C", (self.get_name(), q_dict["dest"], mach_name, self.pr.get_key())))

class device_mode_change_command(command_class):
    def __init__(self):
        command_class.__init__(self, "device_mode_change")
        self.set_needed_sql_fields("device_mode")
    def db_change_call(self, mach_struct, db_s):
        mach_struct.set_device_mode(db_s["device_mode"])
    def post_call(self, mach_struct, ip, mach_name, q_dict):
        log_str = "checked for device_mode change"
        mach_struct.log(log_str)
        self.pr.unlock_device(mach_name)
        self.pr.set_dev_state(mach_name, log_str)
        mach_struct.release_lock(self.get_name())

class refresh_tk_command(command_class):
    def __init__(self):
        command_class.__init__(self, "refresh_tk")
    def post_call(self, mach_struct, ip, mach_name, q_dict):
        q_dict["config"].put(("C", (self.get_name(), q_dict["dest"], mach_name, self.pr.get_key())))

class remove_bs_command(command_class):
    def __init__(self):
        command_class.__init__(self, "remove_bs")
    def post_call(self, mach_struct, ip, mach_name, q_dict):
        log_str = "changed bootserver (removed from me)"
        mach_struct.log(log_str)
        self.pr.set_dev_ip_state(mach_name, ip, 1)
        self.pr.set_dev_state(mach_name, log_str)
        self.pr.unlock_device(mach_name)
        mach_struct.release_lock(self.get_name())
        q_dict["log"].put(("I", ("remove %s" % (mach_struct.name), threading.currentThread().getName())))
        del devname_dict[mach_struct.name]
        del mach_struct

class new_bs_command(command_class):
    def __init__(self):
        command_class.__init__(self, "new_bs")
    def post_call(self, mach_struct, ip, mach_name, q_dict):
        log_str = "changed bootserver (i am the new one)"
        mach_struct.check_network_settings(q_dict["database"].dc)
        mach_struct.log(log_str)
        q_dict["config"].put(("C", ("refresh_all", None, mach_name, None)))
        self.pr.set_dev_ip_state(mach_name, ip, 1)
        self.pr.set_dev_state(mach_name, log_str)
        self.pr.unlock_device(mach_name)
        mach_struct.release_lock(self.get_name())

class ip_changed_command(command_class):
    def __init__(self):
        command_class.__init__(self, "ip_changed")
    def post_call(self, mach_struct, ip, mach_name, q_dict):
        log_str = "checking IP addresses"
        mach_struct.check_network_settings(q_dict["database"].dc)
        mach_struct.log(log_str)
        q_dict["config"].put(("C", ("refresh_all", None, mach_name, None)))
        self.pr.set_dev_ip_state(mach_name, ip, 1)
        self.pr.set_dev_state(mach_name, log_str)
        self.pr.unlock_device(mach_name)
        dhcpd_com = server_command.server_command(command="alter_macadr", nodes=[mach_name])
        q_dict["dhcpd"].put(("D", dhcpd_com))
        mach_struct.release_lock(self.get_name())

class apc_com_command(command_class):
    def __init__(self):
        command_class.__init__(self, "apc_com")
    def post_call(self, mach_struct, ip, mach_name, q_dict):
        q_dict["snmp"].put(("SM", (self.get_name(), self.pr.get_key(), ip, ip, add_args.split(","))))

class apc_com2_command(command_class):
    def __init__(self):
        command_class.__init__(self, "apc_com2")
    def post_call(self, mach_struct, ip, mach_name, q_dict):
        q_dict["snmp"].put(("SM", (self.get_name(), self.pr.get_key(), ip, ip, self.pr.server_command.get_node_command(mach_name).split(","))))

class apc_dev_command(command_class):
    def __init__(self):
        command_class.__init__(self, "apc_dev")
    def post_call(self, mach_struct, ip, mach_name, q_dict):
        add_args = self.pr.server_command.get_node_command(mach_name).split(",")
        log_str = ""
        if add_args:
            if add_args[0] in ["on", "off", "reboot"]:
                q_dict["database"].dc.execute("SELECT d2.name, ms.outlet, i.ip FROM device d, msoutlet ms, netdevice nd, netip i LEFT JOIN device d2 ON d2.device_idx = ms.device WHERE ms.slave_device=d.device_idx AND nd.device=d2.device_idx AND i.netdevice=nd.netdevice_idx AND d.name='%s'" % (mach_name))
                all_apc_cons = q_dict["database"].dc.fetchall()
                if all_apc_cons:
                    x = all_apc_cons[0]
                    q_dict["snmp"].put(("SM", (self.get_name(), self.pr.get_key(), mach_name, x["ip"], ["c%d=%d" % (x["outlet"], {"on" : 1, "off" : 2, "reboot" : 3}[add_args[0]])])))
                else:
                    log_str = "no apc connected"
            else:
                log_str = "Unknown %s command '%s'" % (self.get_name(), add_args[0])
        else:
            log_str = "Need command for %s" % (self.get_name())
        if log_str:
            mach_struct.log(log_str)
            self.pr.set_dev_ip_state(mach_name, ip, 1)
            self.pr.set_dev_state(mach_name, log_str)
            self.pr.unlock_device(mach_name)
            mach_struct.release_lock(self.get_name())

def node_control(main_queue, log_queue, own_queue, config_queue, net_server, snmp_queue, dhcpd_queue, sql_queue, sreq_queue, msi_block):
    my_name = threading.currentThread().getName()
    my_pid = os.getpid()
    process_tools.append_pids("mother/mother")
    if msi_block:
        msi_block.add_actual_pid()
        msi_block.save_block()
    dbcon = mysql_tools.db_con()
    log_queue.put(("L", (my_name, "proc %d: %s-thread for mother is now awake" % (my_pid, my_name))))
    pending_reqs = {}
    # command dictionary
    # port ....... port to connect to (-1 for no host connection, 0 for ping)
    # add_ping ... adds a sub-ping to the command (for example status)
    # ct ......... identifier of a thread to signal
    # delay ...... delays the request for some nodes
    
    # build valid_command_list
    valid_commands = []
    # commands which work only on a per-machine base (don't try all IPs)
    no_spread_commands = []
    # commands which work for all IPs (status, ping and so on)
    spread_commands = []
    for name in [x for x in globals().keys() if x.endswith("_command")]:
        obj = globals()[name]
        if type(obj) == types.ClassType:
            act_com = name[:-8]
            valid_commands.append(act_com)
            test_com = globals()[name]()
            if test_com.get_spread():
                spread_commands.append(act_com)
            else:
                no_spread_commands.append(act_com)
            del test_com
    valid_commands.sort()
    no_spread_commands.sort()
    spread_commands.sort()
    log_queue.put(("L", (my_name, "valid commands     (%2d) : %s" % (len(valid_commands),     ", ".join(valid_commands)    ))))
    log_queue.put(("L", (my_name, "no_spread_commands (%2d) : %s" % (len(no_spread_commands), ", ".join(no_spread_commands)))))
    log_queue.put(("L", (my_name, "spread_commands    (%2d) : %s" % (len(spread_commands),    ", ".join(spread_commands)   ))))
    com_dict = {"ping"           : {"spread"   : 1},
                "status"         : {"port"     : 2002,
                                    "add_ping" : 1,
                                    "spread"   : 1,
                                    "tcp_con"  : 1},
                "refresh_hwi"    : {"port"     : 2001,
                                    "command"  : "hwinfo --raw",
                                    "spread"   : 1,
                                    "tcp_con"  : 1},
                "refresh_hwi2"   : {"port"     : 2001,
                                    "command"  : "machinfo -r",
                                    "spread"   : 1,
                                    "tcp_con"  : 1},
                "restart_network": {"port"     : 2001,
                                    "command"  : "call_script /etc/init.d/network restart",
                                    "spread"   : 1,
                                    "tcp_con"  : 1},
                "propagate"      : {"port"     : 2001,
                                    "command"  : "resync_config",
                                    "tcp_con"  : 1},
                "readdots"       : {"subtype"  : "config"},
                "refresh_tk"     : {"subtype"  : "config"},
                "remove_bs"      : {"subtype"  : "control"},
                "new_bs"         : {"subtype"  : "control"},
                "reboot"         : {"port"     : 2002,
                                    "spread"   : 1,
                                    "tcp_con"  : 1},
                "reboot_nd"      : {"port"     : 2002,
                                    "spread"   : 1,
                                    "tcp_con"  : 1},
                "halt"           : {"port"     : 2002,
                                    "spread"   : 1,
                                    "tcp_con"  : 1},
                "poweroff"       : {"port"     : 2002,
                                    "spread"   : 1,
                                    "tcp_con"  : 1},
                "apc_com"        : {"subtype"  : "snmp",
                                    "add_arg"  : 1},
                "apc_com2"       : {"subtype"  : "snmp",
                                    "add_arg"  : 1},
                "apc_dev"        : {"subtype"  : "snmp",
                                    "add_arg"  : 1},
                "apc_dev2"       : {"subtype"  : "snmp",
                                    "add_arg"  : 1}
                }
    act_idx = 0
    # queue dict
    q_dict = {"dest"     : own_queue,
              "config"   : config_queue,
              "snmp"     : snmp_queue,
              "log"      : log_queue,
              "dhcpd"    : dhcpd_queue,
              "database" : dbcon}
    # device_mode stuff
    devices_to_monitor = [k for k, v in devname_dict.iteritems() if v.get_device_mode()]
    devices_to_monitor.sort()
    log_queue.put(("L", (my_name, "%s to monitor: %s" % (logging_tools.get_plural("device", len(devices_to_monitor)),
                                                         ", ".join(devices_to_monitor)))))
    # mapping between external ids and (unique) local ids
    glob_loc_id = 0
    while 1:
        #print len(pending_reqs.keys()), time.time()
        # get request
        mes_type, mes_arg = own_queue.get()
        # internal mesage
        if mes_type == "I":
            mes_arg, mes_thread = mes_arg
            if mes_arg == "exit":
                log_queue.put(("L", (my_name, "Got internal message from %s : %s" % (mes_thread, mes_arg))))
                break
            elif mes_arg == "update":
                if devices_to_monitor:
                    act_time = time.time()
                    # build accurate ping_list and reboot_dict
                    ping_list, reboot_dict = ([], {})
                    rb_type_dict = {1 : "reboot (software)",
                                    2 : "reboot (hardware)"}
                    for dev_name in devices_to_monitor:
                        if devname_dict.has_key(dev_name):
                            dev_struct = devname_dict[dev_name]
                            if dev_struct.get_device_mode():
                                if abs(dev_struct.get_last_ip_set() - act_time) >= g_config["DEVICE_MONITOR_TIME"]:
                                    ping_list.append(dev_name)
                                if dev_struct.get_last_ip_ok_set() and abs(dev_struct.get_last_ip_ok_set() - act_time) >= g_config["DEVICE_REBOOT_TIME"]:
                                    reboot_dict.setdefault(dev_struct.get_device_mode(), []).append(dev_name)
                                    dev_struct.device_log_entry(0, "w", "doing a %s (not reachable for %d seconds)" % (rb_type_dict[dev_struct.get_device_mode()],
                                                                                                                       (dev_struct.get_last_ip_ok_set() - act_time)), sql_queue, log_source_idx)
                    if ping_list:
                        ping_list.sort()
                        log_queue.put(("L", (my_name, "<devicemonitor> Sending ping to %s: %s" % (logging_tools.get_plural("device", len(ping_list)),
                                                                                                  logging_tools.compress_list(ping_list)))))
                        own_queue.put(("R", server_command.server_command(command="ping", nodes=ping_list)))
                    for rb_type, rb_list in reboot_dict.iteritems():
                        log_queue.put(("L", (my_name, "<devicemonitor> Doing a %s on %s: %s" % (rb_type_dict[rb_type],
                                                                                                logging_tools.get_plural("device", len(rb_list)),
                                                                                                logging_tools.compress_list(rb_list)))))
                        if rb_type == 1:
                            own_queue.put(("R", server_command.server_command(command="reboot", nodes=rb_list)))
                        else:
                            own_queue.put(("R", server_command.server_command(command="apc_dev", nodes=rb_list, node_commands=dict([(k, "reboot") for k in rb_list]))))
            else:
                log_queue.put(("L", (my_name, "Got unknown internal_message '%s'" % (str(mes_arg)))))
        else:
            if mes_type == "R":
                #ret_queue, ext_id, command, machines, add_args=mes_arg
                server_com = mes_arg
                command = server_com.get_command()
                # check for delay
                if command in valid_commands:
                    dbcon.dc.init_logs()
                    glob_loc_id += 1
                    # init pending request
                    new_pr = pending_req(server_com, glob_loc_id, command)
                    new_com = globals()["%s_command" % (command)]()
                    new_com.set_pending_request(new_pr)
                    #print new_pr, new_com
                    # iterate over devices
                    log_queue.put(("L", (my_name, "got command %s (key %s) for %s: %s" % (command,
                                                                                          str(server_com.get_key()),
                                                                                          logging_tools.get_plural("node", len(server_com.get_nodes())),
                                                                                          logging_tools.compress_list(server_com.get_nodes())))))
                    for mach in server_com.get_nodes():
                        # add machine (name or ip) to new_pr
                        ip_list, mach_name, mach_struct = new_com.add_device(mach, log_queue, net_server, q_dict)
                    new_com.handle_sql_requests(log_queue, net_server, q_dict)
                    new_devices_to_monitor = [k for k, v in devname_dict.iteritems() if v.get_device_mode()]
                    new_devices_to_monitor.sort()
                    if devices_to_monitor != new_devices_to_monitor:
                        devices_to_monitor = new_devices_to_monitor
                        log_queue.put(("L", (my_name, "%s to monitor: %s" % (logging_tools.get_plural("device", len(devices_to_monitor)),
                                                                             ", ".join(devices_to_monitor)))))
                    pending_reqs[glob_loc_id] = new_com
                    for delay, mach_list in new_com.delay_dict.iteritems():
                        log_queue.put(("L", (my_name, "Delaying reboot for %s for %d seconds: %s" % (logging_tools.get_plural("device", len(mach_list)),
                                                                                                     delay,
                                                                                                     ", ".join(mach_list)))))
                        server_com = server_command.server_command(command="reboot_nd", nodes=mach_list)
                        log_queue.put(("D", (own_queue, ("R", server_com), delay)))
                else:
                    log_queue.put(("L", (my_name, "Unknown command %s" % (command))))
                    if server_com.get_queue():
                        res_com = server_command.server_reply()
                        res_com.set_error_result("unrecognized command")
                        sreq_queue.put(("CR", (server_com.get_key(), res_com)))
            elif mes_type in ["ER", "msrcv", "mserr"]:
                # command is not a ping
                command_is_ping = 0
                if mes_type == "ER":
                    command, ip, error, ret_str, loc_id = mes_arg
                else:
                    loc_id, ((loc_ip, loc_port), ip, ret_str), add_data = mes_arg
                    if loc_ip.startswith("raw ping"):
                        # command is a ping
                        command_is_ping = 1
                        num, sent, recv, loss, dmin, davg, dmax, d_time = ret_str                    
                        ret_str = "%s ping" % (ip)
                        if recv:
                            error, ret_str = (0, "ok %s" % (ret_str))
                        else:
                            error, ret_str = (1, "error %s" % (ret_str))
                    else:
                        loc_id, command = add_data
                        if mes_type == "msrcv":
                            error, ip          = (0, ip[0])
                        else:
                            error, ip, ret_str = (1, ip[0], ret_str[1])
                if pending_reqs.has_key(loc_id):
                    act_com = pending_reqs[loc_id]
                    command = act_com.get_name()
                    act_pr = act_com.get_pending_request()
                    if devname_dict.has_key(ip):
                        mach_struct = devname_dict[ip]
                    else:
                        mach_struct = devip_dict[ip]
                    mach_name = mach_struct.name
                    sub_command = (command == "status" and command_is_ping)
##                     if mach_name == "node091":
##                         print sub_command, command, loc_id, mes_arg
                    #print "****", error,mach_name
                    if error:
                        # command resulted in an error, in errors we are only interested for the main-command
                        if sub_command:
                            act_pr.set_dev_ip_sub_state(mach_name, ip ,-1)
                        else:
                            com_state = -1
                    else:
                        com_state, loc_error = (1, 0)
                        mach_struct.set_actual_ip(ip)
                        if act_pr.get_command() == "status":
                            if sub_command:                                # sub-command (sort of a bypass), we set the sub-state for this device to 1 (device pingable)
                                mach_struct.log("got ICMP response, setting ip to '%s' (sub_state to 1)" % (ip))
                                act_pr.set_dev_ip_sub_state(mach_name, ip, 1)
                                if act_pr.get_dev_state(mach_name) == "not set":
                                    act_pr.set_dev_state(mach_name, "warn %s" % (ret_str))
                                    act_pr.set_dev_temp_req_state(mach_name, "warn %s %s (%s)" % (ip, ret_str, mach_struct.get_act_net()))
                            else:
                                mach_struct.set_req_state("ok %s %s (%s)" % (ip, ret_str, mach_struct.get_act_net()), sql_queue)
                        elif act_pr.get_command() in ["refresh_hwi", "refresh_hwi2"]:
                            # delete delay-lock
                            mach_struct.clear_hwi_delay_counter()
                            if ret_str.startswith("unknown command"):
                                # fallback-solution for older systems
                                mach_struct.incr_hwi_delay_counter()
                                mach_struct.log("Old collserver installed on target host, trying machinfo after %d seconds" % (g_config["HWI_DELAY_TIME"]))
                                server_com = server_command.server_command(command="refresh_hwi2", nodes=[mach_name])
                                log_queue.put(("DL", (own_queue, ("R", server_com), g_config["HWI_DELAY_TIME"])))
                                loc_error, ret_str = (1, "old software detected, enabling bypass...")
                            else:
                                loc_error, ret_str, mac_change = mach_struct.insert_hardware_info(dbcon.dc, ret_str, sql_queue)
                                if mac_change:
                                    mach_struct.log("%s has been changed, trying to restart network on target node" % (logging_tools.get_plural("MAC Address", mac_change)))
                                    server_com = server_command.server_command(command="resync_config", nodes=[mach_name])
                                    own_queue.put(("R", server_com))
                                #print "RS:", ret_str
                        elif act_pr.get_command() in ["resync_config"]:
                            mach_struct.log("Result for %s: %s" % (act_pr.get_command(), ret_str))
                            if ret_str.startswith("ok "):
                                mach_struct.log("trying to restart network")
                                server_com = server_command.server_command(command="restart_network", nodes=[mach_name])
                                own_queue.put(("R", server_com))
                        elif act_pr.get_command() in ["restart_network"]:
                            mach_struct.log("Result for %s: %s" % (act_pr.get_command(), ret_str))
                        if not sub_command:
                            mach_struct.log("got answer, setting state to '%s'" % (ret_str))
                            if loc_error:
                                act_pr.set_dev_state(mach_name, "error %s" % (ret_str))
                            else:
                                act_pr.set_dev_state(mach_name, "%s" % (ret_str))
                    #print "***********", valid, sub_command
                    # this (set_dev_ip_state() and all_states_set_and_error()) raises a key-error (sometimes) (was fixed in early 2005 [at least i hope...]) !!!
                    if act_pr.dev_is_locked(mach_name):
                        if not sub_command:
                            act_pr.set_dev_ip_state(mach_name, ip, com_state)
                        #print "+", loc_id, act_pr.any_state_set_ok(mach_name)
##                         if mach_name == "node091":
##                             print loc_id, act_pr.any_state_set_ok(mach_name)
                        if act_pr.any_state_set_ok(mach_name):
                            act_pr.unlock_device(mach_name)
                        elif act_pr.all_states_set_and_error(mach_name):
                            # all checks in the main-path resulted in an error
                            # any sub-commands ok ?
                            if act_pr.any_sub_states_set_and_ok(mach_name):
                                act_pr.unlock_device(mach_name)
                                # some sub-checks were ok -> this is our new status
                                if act_pr.get_command() == "status":
                                    mach_struct.set_req_state(act_pr.get_dev_temp_req_state(mach_name), sql_queue)
                            elif not act_pr.all_sub_states_set(mach_name):
                                # not all sub-check have yet returned -> maybe we get a positive result so wait until also all sub-checks are through
                                pass
                            else:
                                act_pr.unlock_device(mach_name)
                                if not sub_command:
                                    if act_pr.get_command() in ["refresh_hwi", "refresh_hwi2"]:
                                        if mach_struct.get_hwi_delay_counter() == g_config["HWI_MAX_RETRIES"]:
                                            mach_struct.log("HWI delay-counter for reached maximum value of %d, giving up and clearing counter..." % (g_config["HWI_MAX_RETRIES"]))
                                            mach_struct.clear_hwi_delay_counter()
                                        else:
                                            mach_struct.incr_hwi_delay_counter()
                                            mach_struct.log("Error getting new HWI, delaying request for %d seconds (counter: %d of %d)" % (g_config["HWI_DELAY_TIME"],
                                                                                                                                            mach_struct.get_hwi_delay_counter(),
                                                                                                                                            g_config["HWI_MAX_RETRIES"]))
                                            server_com = server_command.server_command(command="refresh_hwi", nodes=[mach_name])
                                            log_queue.put(("DL", (own_queue, ("R", server_com), g_config["HWI_DELAY_TIME"])))
                                    act_pr.set_dev_state(mach_name, "error %s" % (ret_str))
                                    if act_pr.get_command() == "status":
                                        mach_struct.set_req_state("error %s %s: not found" % (ret_str, mach_name), sql_queue)
                        if not act_pr.dev_is_locked(mach_name):
                            mach_struct.release_lock(act_pr.get_command())
                        # machine is unreachable
                else:
                    # late response (for example timeouts on the bootnet)
                    #print "Late response:", mes_type, mes_arg
                    pass
            elif mes_type == "N":
                mach_struct, ip, (src_host, src_port), in_str, in_time = mes_arg
                mach_struct.set_actual_ip(ip)
                mach_struct.log("Got request from src %s:%d (net %s): %s" % (src_host,
                                                                             src_port,
                                                                             mach_struct.get_act_net(),
                                                                             in_str))
                write_recvstate = 1
                if len(in_str):
                    if in_str.startswith("mother connection"):
                        dbcon.dc.execute("UPDATE device SET last_boot='%s' WHERE name='%s'" % (time.ctime(in_time), mach_struct.name))
                        mach_struct.clear_hardware_info(dbcon.dc)
                    elif in_str.startswith("boot "):
                        mach_struct.device_log_entry(1, "i", in_str, sql_queue)
                    elif in_str.startswith("starting"):
                        startmesp = in_str.split()
                        mach_struct.device_log_entry(2, "i", "start %s" % (" ".join(startmesp[1:])), sql_queue)
                    elif in_str.startswith("down to runlevel"):
                        downmesp = in_str.split()
                        if len(downmesp) == 4:
                            try:
                                trunlevel = int(downmesp[3])
                            except:
                                mach_struct.log("*** error parsing runlevel '%s'" % (downmesp[3]))
                            else:
                                if trunlevel == 6:
                                    mach_struct.device_log_entry(3, "i", "reboot", sql_queue)
                                elif trunlevel == 0:
                                    mach_struct.device_log_entry(4, "i", "halt", sql_queue)
                        else:
                            mach_struct.log("*** error runlevel string has wrong format (need 4 parts): '%s'" % (in_str))
                    elif in_str.startswith("up to runlevel"):
                        act_idx += 1
                        mach_struct.log("got 'up to runlevel' string, requesting hardware-info")
                        server_com = server_command.server_command(command="refresh_hwi")
                        server_com.set_key("pi%d" % (act_idx))
                        server_com.set_nodes([ip])
                        own_queue.put(("R", server_com))
                    elif in_str == "start syslog":
                        mach_struct.log("node restart_syslog")
                    elif in_str.startswith("installing new kernel"):
                        dbcon.dc.execute("UPDATE device SET last_kernel='%s' WHERE name='%s'" % (time.ctime(in_time), mach_struct.name))
                    elif in_str == "installing":
                        dbcon.dc.execute("UPDATE device SET last_install='%s' WHERE name='%s'" % (time.ctime(in_time), mach_struct.name))
                    elif in_str.startswith("*"):
                        write_recvstate = 0
                        mach_struct.device_log_entry(0, "i", in_str[1:], sql_queue)
                if write_recvstate:
                    mach_struct.set_recv_state("%s (%s)" % (in_str.strip(), mach_struct.get_act_net()), sql_queue)
            else:
                print mes_type, mes_arg
            # check for finished calls
            del_ids = [x for x in pending_reqs.keys() if pending_reqs[x].get_pending_request().all_states_set()]
            for act_id in del_ids:
                act_pr = pending_reqs[act_id].get_pending_request()
                mach_map = act_pr.get_dev_mapping()
                ret_sa, ret_dict, node_dict = ([], {}, {})
                for mach in act_pr.get_devices():
                    if mach_map[mach] and devname_dict.has_key(mach_map[mach]):
                        ret_sa.append(act_pr.get_dev_state(mach_map[mach]))
                        ret_dict[mach_map[mach]] = act_pr.get_dev_state(mach_map[mach])
                        mach_struct = devname_dict[mach_map[mach]]
                        recv_state, req_state = mach_struct.get_recv_req_state()
                        node_dict[mach_map[mach]] = {"recv_state" : recv_state,
                                                     "req_state"  : req_state}
                    else:
                        ret_sa.append("error Key not found")
                        ret_dict[mach] = "error Key not found"
                server_com = act_pr.server_command
                ret_queue = server_com.get_queue()
                if ret_queue:
                    res_com = server_command.server_reply()
                    res_com.set_node_results(ret_dict)
                    res_com.set_ok_result("ok")
                    res_com.set_node_dicts(node_dict)
                    sreq_queue.put(("CR", (server_com.get_key(), res_com)))
                del pending_reqs[act_id]
            #print "pending:", pending_reqs.keys()
    log_queue.put(("L", (my_name, "proc %d: %s-thread for mother exiting" % (my_pid, my_name))))
    main_queue.put(("I", ("exiting", my_name)))

class error(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return self.value

class term_error(error):
    def __init__(self):
        pass
    
class alarm_error(error):
    def __init__(self):
        pass
    
class stop_error(error):
    def __init__(self):
        pass
    
class int_error(error):
    def __init__(self):
        pass

def sig_term_handler(signum, frame):
    #sys.stderr.write("SIGTERM\n")
    raise term_error

def sig_alarm_handler(signum, frame):
    raise alarm_error

def sig_int_handler(signum, frame):
    #sys.stderr.write("SIGINT\n")
    raise int_error

def sig_tstp_handler(signum, frame):
    raise stop_error
    
def logging_thread(main_queue, log_queue, loc_con, dhcpd_queue, msi_block):
    def get_handle(name):
        pre_str = ""
        if machlogs.has_key(name):
            handle = machlogs[name]
        else:
            if devname_dict.has_key(name):
                mach = devname_dict[name]
                name = mach.name
                machdir = "%s/%s" % (root, name)
                if not os.path.exists(machdir):
                    glog.write("Creating dir %s for %s" % (machdir, name))
                    os.makedirs(machdir)
                machlogs[name] = logging_tools.logfile("%s/log" % (machdir))
                machlogs[name].write(sep_str)
                machlogs[name].write("Opening log")
                #glog.write("# of open machine logs: %d" % (len(machlogs.keys())))
                handle = machlogs[name]
            else:
                handle, pre_str = (glog, "device %s: " % (name))
        return (handle, pre_str)
    def logit(arg):
        if len(arg) == 2:
            log_thread, text = arg
            handle, pre_str = (glog, "")
        else:
            log_thread, text, name = arg
            handle, pre_str = get_handle(name)
        handle.write("(%s) : %s%s" % (log_thread, pre_str, text))
    my_name = threading.currentThread().getName()
    my_pid = os.getpid()
    process_tools.append_pids("mother/mother")
    if msi_block:
        msi_block.add_actual_pid()
        msi_block.save_block()
    # stuff for the syslog-capturer
    sys.path.append("/usr/local/sbin")
    sys.path.append("/usr/local/sbin/modules")
    import machinfo_mod
    sys_dict = cPickle.loads(machinfo_mod.sysinfo_s(None, [])[3:])
    # determine correct regexp
    if sys_dict["version"] in ["8.0", "8.1"] and sys_dict["vendor"] != "redhat":
        log_queue.put(("L", (my_name, "System Version is < SUSE 8.2, using non-standard regexp for syslog-ng messages")))
        linem = re.compile("^\<\d+\>(?P<time>\S+\s+\S+\s+\S+)\s+(?P<facility>\S+):\s+(?P<message>.*)$")
    else:
        log_queue.put(("L", (my_name, "System Version is >= SUSE 8.2 or RedHat, using standard regexp for syslog-ng messages")))
        linem = re.compile("^\<\d+\>(?P<time>\S+\s+\S+\s+\S+)\s+(?P<host>\S+)\s+(?P<facility>\S+):\s+(?P<message>.*)$")

    fname = "/var/lib/mother/syslog"
    dhcpd = re.compile("^DHCPDISCOVER from (?P<macaddr>\S+) via .*$")
    dhcpo = re.compile("^DHCPOFFER on (?P<ip>\S+) to (?P<macaddr>\S+) via .*$")
    dhcpr = re.compile("^DHCPREQUEST for (?P<ip>\S+) .*from (?P<macaddr>\S+) via .*$")
    dhcpa = re.compile("^DHCPACK on (?P<ip>\S+) to (?P<macaddr>\S+) via .*$")
    
    root = g_config["LOG_DIR"]
    sep_str = "-" * 50
    if not os.path.exists(root):
        os.makedirs(root)
    log_queue.put(("L", (my_name, "logging_thread is now awake (pid %d)" % (my_pid))))
    glog_name = "%s/log" % (root)
    glog = logging_tools.logfile(glog_name)
    glog.write(sep_str)
    glog.write("Opening log")
    main_queue.put(("I", ("alive", my_name)))
    machlogs = {}
    # check_state for connection to syslog-ng
    # 0 .... waiting for something
    # +n ... received so many syslog_thread_cstr
    # number of iterations we had contact to the syslogger
    csok_iter = 0
    check_state = 0
    check_state_th = 2
    # delay-array
    d_array = []
    while 1:
        mes_type, mes_arg = log_queue.get()
        act_time = time.time()
        if mes_type == "I":
            mes_arg, mes_thread = mes_arg
            if mes_arg == "exit":
                break
            elif mes_arg == "update":
                # handle delay-requests
                new_d_array = []
                for ret_queue, ret_obj, r_time in d_array:
                    if r_time < act_time:
                        #print "***", ret_queue, ret_obj
                        ret_queue.put(ret_obj)
                    else:
                        new_d_array.append((ret_queue, ret_obj, r_time))
                d_array = new_d_array
            elif mes_arg.startswith("remove"):
                machs = mes_arg.split()[1:]
                for mach in machs:
                    logit((mes_thread, "Closing log for device %s" % (mach)))
                    machlogs[mach].write("(%s) : Closing log" % (my_name))
                    machlogs[mach].close()
                    del machlogs[mach]
            else:
                print "mes_arg:", mes_arg
        elif mes_type == "DL":
            # handle delay-requests
            ret_queue, ret_obj, delay = mes_arg
            d_array.append((ret_queue, ret_obj, act_time+delay))
        elif mes_type == "ML":
            logging_tools.my_syslog(str(mes_arg))
        elif mes_type == "L":
            logit(mes_arg)
        elif mes_type == "mslog":
            key, (loc_addr, other_addr, log_str), add_data = mes_arg
            logit((my_name, log_str, None))
        elif mes_type == "msrcv":
            key, ((loc_addr, loc_port), other_addr, recv), add_data = mes_arg
            if loc_addr == fname:
                lines = linem.match(recv)
                #print "*", instr, "+", lines
                if lines:
                    mess_str = lines.group("message").strip()
                    if lines.group("facility") == "dhcpd":
                        for line in [x for x in [y.strip() for y in recv.split("\n")] if x]:
                            logit((my_name, "got line %s from dhcp-server" % (line), None))
                        for tstr, tre in [("DISCOVER", dhcpd),
                                          ("OFFER"   , dhcpo),
                                          ("REQUEST" , dhcpr),
                                          ("ACK"     , dhcpa)]:
                            dhcp_s = tre.match(mess_str)
                            if dhcp_s:
                                if tstr == "DISCOVER":
                                    ip = "---";
                                else:
                                    ip = dhcp_s.group("ip")
                                server_com = server_command.server_command(command="server_message")
                                server_com.set_option_dict({"sm_type" : tstr,
                                                            "ip"      : ip,
                                                            "mac"     : dhcp_s.group("macaddr"),
                                                            "message" : mess_str})
                                dhcpd_queue.put(("D", server_com))#["server_message", None, tstr, ip, dhcp_s.group("macaddr"), mess_str]))
                                break
                        else:
                            logit((my_name, "No match: *** %s ***" % (mess_str), None))
                    else:
                        logit((my_name, "Got unparsed log-string '%s'" % (recv.strip()), None))
            else:
                print "mes_type/mes_arg:", mes_type, mes_arg
        else:
            print "mes_type/mes_arg:", mes_type, mes_arg
    for mach in machlogs.keys():
        machlogs[mach].write("Closing log")
        machlogs[mach].close()
    glog.write("Closed %d machine logs" % (len(machlogs.keys())))
    glog.write("Closing log")
    glog.write("logging thread exiting (pid %d)" % (my_pid))
    glog.close()
    main_queue.put(("I", ("exiting", my_name)))

def get_kernel_name(dc, k_n, k_idx):
    if g_config["PREFER_KERNEL_NAME"]:
        dc.execute("SELECT k.name FROM kernel k WHERE k.name='%s'" % (mysql_tools.my_escape(k_n)))
    else:
        dc.execute("SELECT k.name FROM kernel k WHERE k.kernel_idx=%d" % (k_idx))
    if dc.rowcount:
        rk_n = dc.fetchone()["name"]
    else:
        rk_n = k_n
    return rk_n

def throttle_thread(main_queue, log_queue, own_queue, msi_block):
    def log_dict():
        if throttle_dict:
            num_th = len(throttle_dict.keys())
            log_queue.put(("L", (my_name, "Got throttling messages from %d devices: %s" % (num_th, ", ".join(["%s (%d)" % (x, reduce(lambda a, b:a+b, [z["num"] for z in throttle_dict[x].itervalues()])) for x in throttle_dict.keys()])))))
            mes_list = []
            for ml in reduce(lambda a, b:a+b, [x.keys() for x in throttle_dict.itervalues()], []):
                if ml not in mes_list:
                    mes_list.append(ml)
            mes_list.sort()
            for mes in mes_list:
                act_list = []
                for dev, stuff in throttle_dict.iteritems():
                    if mes in stuff.keys():
                        act_list.append("%s (%d)" % (dev, stuff[mes]["num"]))
                        log_queue.put(("L", (my_name, "* throttle message '%-40s': %4d times" % (mes, stuff[mes]["num"]), dev)))
                act_list.sort()
                log_queue.put(("L", (my_name, " - message %-40s: %2d devices: %s" % (mes, len(act_list), ", ".join(act_list)))))
    my_name = threading.currentThread().getName()
    my_pid = os.getpid()
    process_tools.append_pids("mother/mother")
    if msi_block:
        msi_block.add_actual_pid()
        msi_block.save_block()
    log_queue.put(("L", (my_name, "proc %d: %s-thread for mother is now awake" % (my_pid, my_name))))
    throttle_dict = {}
    last_check = time.time()
    while 1:
        mes_type, mes_arg = own_queue.get()
        if mes_type == "I":
            mes_arg, mes_thread = mes_arg
            if mes_arg == "exit":
                break
            elif mes_arg == "update":
                act_time = time.time()
                if act_time-last_check > 60. or act_time < last_check:
                    last_check = act_time
                    log_dict()
                    throttle_dict = {}
            else:
                print "mes_arg:", mes_arg
        elif mes_type == "T":
            mach, mes_str = mes_arg
            throttle_dict.setdefault(mach, {}).setdefault(mes_str, {"first" : time.time(), "num" : 0})
            throttle_dict[mach][mes_str]["num"] += 1
            throttle_dict[mach][mes_str]["last"] = time.time()
    log_dict()
    log_queue.put(("L", (my_name, "proc %d: %s-thread for mother exiting" % (my_pid, my_name))))
    main_queue.put(("I", ("exiting", my_name)))

def sql_thread_code(main_queue, log_queue, own_queue, msi_block):
    my_name, my_pid = (threading.currentThread().getName(), os.getpid())
    process_tools.append_pids("mother/mother")
    if msi_block:
        msi_block.add_actual_pid()
        msi_block.save_block()
    log_queue.put(("L", (my_name, "proc %d: %s-thread for mother is now awake" % (my_pid, my_name))))
    last_check = time.time()
    num_written, num_update, num_ins_v, num_ins_s = (0, 0, 0, 0)
    start_time = time.time()
    dbcon = mysql_tools.db_con()
    while 1:
        mes_type, mes_arg = own_queue.get()
        if mes_type == "I":
            mes_arg, mes_thread = mes_arg
            if mes_arg == "exit":
                break
            elif mes_arg == "update":
                act_time = time.time()
                if act_time - last_check > 60. or act_time < last_check:
                    last_check = act_time
            else:
                print "mes_arg:", mes_arg
        elif mes_type == "S":
            sql_type, sql_table, sql_data = mes_arg
            if sql_type == "U":
                sql_str = "UPDATE %s SET %s" % (sql_table, sql_data)
                num_update += 1
            elif sql_type == "IV":
                sql_str = "INSERT INTO %s VALUES(%s)" % (sql_table, sql_data)
                num_ins_v += 1
            elif sql_type == "IS":
                sql_str = "INSERT INTO %s SET %s" % (sql_table, sql_data)
                num_ins_s += 1
            dbcon.dc.execute(sql_str)
            num_written += 1
            if num_written > 50:
                act_time = time.time()
                log_queue.put(("L", (my_name, "wrote %d entries (%s, %s [with values], %s [with set]) in %.2f seconds" % (num_written,
                                                                                                                          logging_tools.get_plural("update", num_update),
                                                                                                                          logging_tools.get_plural("insert", num_ins_v),
                                                                                                                          logging_tools.get_plural("insert", num_ins_s),
                                                                                                                          act_time - start_time))))
                num_written, num_update, num_ins_v, num_ins_s = (0, 0, 0, 0)
                dbcon.dc.init_logs()
                start_time = act_time
    del dbcon
    log_queue.put(("L", (my_name, "proc %d: %s-thread for mother exiting" % (my_pid, my_name))))
    main_queue.put(("I", ("exiting", my_name)))

def dhcpd_thread(main_queue, log_queue, own_queue, net_server, sql_queue, sreq_queue, msi_block):
    my_name = threading.currentThread().getName()
    my_pid = os.getpid()
    process_tools.append_pids("mother/mother")
    log_queue.put(("L", (my_name, "proc %d: %s-thread for mother is now awake" % (my_pid, my_name))))
    if msi_block:
        msi_block.add_actual_pid()
        msi_block.save_block()
    dbcon = mysql_tools.db_con()
    dbcon.dc.enable_logging(False)
    num_server, server_idx = process_tools.is_server(dbcon.dc, "mother_server")
    dbcon.dc.execute("SELECT i.ip,nw.netmask FROM netip i, netdevice n, network nw, device d, device_config dc, new_config c, network_type nt WHERE dc.device=d.device_idx AND dc.new_config=c.new_config_idx AND c.name='mother_server' AND i.netdevice=n.netdevice_idx AND nw.network_idx=i.network AND nt.identifier='b' AND nt.network_type_idx=nw.network_type AND n.device=d.device_idx AND d.device_idx=%d" % (server_idx))
    server_ip = dbcon.dc.fetchone()
    if server_ip:
        log_queue.put(("L", (my_name, "IP in bootnet at %s (netmask %s)" % (server_ip["ip"], server_ip["netmask"]))))
    else:
        log_queue.put(("L", (my_name, "found no IP in bootnet")))
    om_error = re.compile("^can't (.*) object: (.*)$")
    while 1:
        mes_type, mes_arg = own_queue.get()
        if mes_type == "I":
            mes_arg, mes_thread = mes_arg
            if mes_arg == "exit":
                break
            else:
                print "mes_arg:", mes_arg
        elif mes_type == "D":
            dbcon.dc.init_logs()
            # write to macbootlog if the mac-address is set
            server_com = mes_arg
            it_com = server_com.get_command()
            key = server_com.get_key()
            if it_com == "server_message":
                server_opts = server_com.get_option_dict()
                sm_type     = server_opts["sm_type"]
                ip          = server_opts["ip"]
                mac         = server_opts["mac"]
                full_string = server_opts["message"]
                mach_idx = 0
                if ip:
                    if devip_dict.has_key(ip):
                        mach = devip_dict[ip]
                        mach.incr_use_count()
                        dbcon.dc.execute("SELECT s.status,d.name,d.bootserver,n.devname,n.macadr,d.dhcp_mac,n.netdevice_idx,d.newkernel,d.new_kernel,d.kernel_append FROM device d, netdevice n, netip i LEFT JOIN status s ON d.newstate=s.status_idx WHERE i.netdevice=n.netdevice_idx AND n.device=d.device_idx AND i.ip='%s'" % (ip))
                        dev_list = dbcon.dc.fetchall()
                        if len(dev_list):
                            first_dev = dev_list[0]
                            boot_server, dev_name = (first_dev["bootserver"], first_dev["name"])
                            if boot_server != mother_server_idx:
                                log_queue.put(("L", (my_name, "Not responsible for device '%s' (ip %s); bootserver has idx %d" % (dev_name, ip, boot_server))))
                            else:
                                mach_idx = mach.device_idx
                                if first_dev["dhcp_mac"]:
                                    dbcon.dc.execute("UPDATE device SET dhcp_mac=0 WHERE name='%s'" % (mach.name))
                                    log_queue.put(("L", (my_name, "Clearing dhcp_mac flag for device '%s' (using ip %s)" % (dev_name, ip), dev_name)))
                                else:
                                    log_queue.put(("L", (my_name, "dhcp_mac flag for device '%s' (using ip %s) already cleared" % (dev_name, ip), dev_name)))
                                mach.device_log_entry(5, "i", "got ipaddr (%s)" % (sm_type), sql_queue)
                                mach.set_recv_state("got IPaddress via DHCP", sql_queue)
                                if first_dev["status"] in LIST_TAGKERNEL:
                                    new_kernel_name = get_kernel_name(dbcon.dc, first_dev["newkernel"], first_dev["new_kernel"])
                                    mach.write_kernel_config(sql_queue, new_kernel_name, first_dev["kernel_append"], server_ip["ip"], server_ip["netmask"], 1)
                                elif first_dev["status"] in LIST_DOSBOOT:
                                    # we dont handle dosboot right now, FIXME
                                    pass
                                elif first_dev["status"] in LIST_MEMTEST:
                                    mach.write_memtest_config()
                                elif first_dev["status"] in LIST_BOOTLOCAL:
                                    mach.write_localboot_config()
                                # check if the macadr from the database matches the received mac
                                if first_dev["macadr"] != mac:
                                    log_queue.put(("L", (my_name, "*** got wrong macadr (DHCP: %s, database: %s), fixing " % (mac, first_dev["macadr"]), dev_name)))
                                    dbcon.dc.execute("UPDATE netdevice SET macadr='00:00:00:00:00:00' WHERE macadr='%s'" % (mac))
                                    dbcon.dc.execute("UPDATE netdevice SET macadr='%s' WHERE netdevice_idx=%d" % (mac, first_dev["netdevice_idx"]))
                        else:
                            log_queue.put(("L", (my_name, "Device with IP %s not found in database" % (ip))))
                        mach.decr_use_count()
                            
                if sm_type == "DISCOVER":
                    if re.match("^.*no free leases.*$", full_string):
                        dbcon.dc.execute("SELECT d.name, nd.devname, nd.netdevice_idx, d.bootserver FROM netdevice nd, device d WHERE nd.device=d.device_idx AND nd.macadr='%s'" % (mac))
                        mac_list = dbcon.dc.fetchall()
                        if len(mac_list):
                            mac_entry = mac_list[0]
                            if mac_entry["bootserver"] and mac_entry["bootserver"] != mother_server_idx:
                                # dhcp-DISCOVER request need not to be answered (other Server responsible)
                                sql_queue.put(("S", ("IV", "macbootlog", "0,%d,'%s','%s','%s',%d,null" % (0, sm_type, "OTHER", mac, log_source_idx))))
                                log_queue.put(("L", (my_name, "DHCPDISCOVER for macadr %s (device %s, %s): other bootserver (%d)" % (mac, mac_entry["name"], mac_entry["devname"], mac_entry["bootserver"]))))
                            else:
                                # dhcp-DISCOVER request can not be answered (macadress already used in DB)
                                sql_queue.put(("S", ("IV", "macbootlog", "0,%d,'%s','%s','%s',%d,null" % (0, sm_type, "REJECT", mac, log_source_idx))))
                                log_queue.put(("L", (my_name, "DHCPDISCOVER for macadr %s (device %s, %s): address already used" % (mac, mac_entry["name"], mac_entry["devname"]))))
                        else:
                            dbcon.dc.execute("SELECT nd.netdevice_idx, d.name, d.device_idx, d.bootserver FROM netdevice nd, device d WHERE d.dhcp_mac=1 AND d.bootnetdevice=nd.netdevice_idx AND nd.device=d.device_idx ORDER by d.name")
                            ndidx_list = dbcon.dc.fetchall()
                            if len(ndidx_list):
                                for nd in ndidx_list:
                                    if nd["bootserver"]:
                                        if nd["bootserver"] == mother_server_idx:
                                            ins_idx = nd["netdevice_idx"]
                                            dev_name = nd["name"]
                                            dbcon.dc.execute("SELECT macadr FROM mac_ignore WHERE macadr='%s'" % (mac))
                                            if dbcon.dc.rowcount:
                                                log_queue.put(("L", (my_name, "Ignoring MAC-Adress '%s' (in ignore-list)" % (mac))))
                                                sql_queue.put(("S", ("macbootlog", "IV", "0,%d,'%s','%s','%s',%d,null" % (0, sm_type, "IGNORELIST", mac, log_source_idx))))
                                            else:
                                                log_queue.put(("L", (my_name, "Setting bootmacaddress of device '%s' to '%s'" % (dev_name, mac))))
                                                dbcon.dc.execute("UPDATE device SET dhcp_mac=0 WHERE name='%s'" % (dev_name))
                                                dbcon.dc.execute("UPDATE netdevice SET macadr='%s' WHERE netdevice_idx=%d" % (mac, ins_idx))
                                                dbcon.dc.execute("SELECT d.device_idx FROM device d WHERE d.name='%s'" % (dev_name))
                                                didx = dbcon.dc.fetchone()["device_idx"]
                                                sql_queue.put(("S", ("IV", "devicelog", mysql_tools.get_device_log_entry(didx, log_sources["node"]["log_source_idx"], 0, log_status["i"]["log_status_idx"], mac))))
                                                own_com = server_command.server_command(command="alter_macadr", nodes=[dev_name])
                                                own_queue.put(("D", own_com))
                                                # set the mac-address
                                                sql_queue.put(("S", ("IV", "macbootlog", "0,%d,'%s','%s','%s',%d, null" % (nd["device_idx"], sm_type, "SET", mac, log_source_idx))))
                                            break
                                        else:
                                            log_queue.put(("L", (my_name, "Not responsible for device '%s' (ip %s); bootserver has idx %d" % (nd["name"], ip, nd["bootserver"]))))
                                            break
                                    else:
                                        log_queue.put(("L", (my_name, "Greedy device %s has no bootserver associated" % (nd["name"]), nd["name"])))
                            else:
                                # ignore mac-address (no greedy devices)
                                sql_queue.put(("S", ("IV", "macbootlog", "0,%d,'%s','%s','%s',%d,null" % (0, sm_type, "IGNORE", mac, log_source_idx))))
                                log_queue.put(("L", (my_name, "No greedy devices found for MAC-Address %s" % (mac))))
                    else:
                        # dhcp-DISCOVER request got an answer
                        sql_queue.put(("S", ("IV", "macbootlog", "0,%d,'%s','%s','%s',%d,null" % (0, sm_type, "---", mac, log_source_idx))))
                else:
                    # non dhcp-DISCOVER request
                    sql_queue.put(("S", ("IV", "macbootlog", "0,%d,'%s','%s','%s',%d,null" % (mach_idx, sm_type, ip, mac, log_source_idx))))
            if it_com in ["alter_macadr", "delete_macadr", "write_macadr"]:
                nodes = server_com.get_nodes()
                log_queue.put(("L", (my_name, "got command %s (key %s), %s%s" % (it_com, key,
                                                                                 logging_tools.get_plural("node", len(nodes)),
                                                                                 nodes and ": %s" % (", ".join([str(x) for x in nodes])) or ""))))
                sql_str = "SELECT nd.macadr,d.name,i.ip,d.dhcp_written,d.dhcp_write,d.dhcp_error, nd.dhcp_device,nt.identifier,nd.netdevice_idx FROM netdevice nd, device d, netip i, network nw, network_type nt WHERE nd.device=d.device_idx AND i.netdevice=nd.netdevice_idx AND ((d.bootnetdevice=nd.netdevice_idx AND nt.identifier='b') OR nd.dhcp_device=1) AND nw.network_type=nt.network_type_idx AND i.network=nw.network_idx AND d.bootserver=%d" % (mother_server_idx)
                all_rets_dict = {}
                if len(nodes):
                    sql_str += " AND (%s)" % (" OR ".join(["d.name='%s'" % (x) for x in nodes]))
                    for x in nodes:
                        all_rets_dict[x] = "warn no SQL-result"
                dbcon.dc.execute(sql_str)
                mach_dict = {}
                for x in dbcon.dc.fetchall():
                    if not mach_dict.has_key(x["name"]):
                        mach_dict[x["name"]] = x
                    else:
                        if x["identifier"] == "b" and mach_dict[x["name"]]["identifier"] != "b":
                            mach_dict[x["name"]]["ip"] = x["ip"]
                empty_result = 1
                # additional flags 
                add_flags = []
                for machdat in mach_dict.values():
                    empty_result = 0
                    #print "-----------------------------"
                    #print it_com, "::", machdat
                    if devname_dict.has_key(machdat["name"]):
                        mach = devname_dict[machdat["name"]]
                        if mach.maint_ip:
                            ip_to_write, ip_to_write_src = (mach.maint_ip, "maint_ip")
                        elif machdat["dhcp_device"]:
                            if len(mach.ip_dict.keys()) == 1:
                                ip_to_write, ip_to_write_src = (mach.ip_dict.keys()[0], "first ip of ip_dict.keys()")
                            else:
                                ip_to_write, ip_to_write_src = (None, "")
                        else:
                            ip_to_write, ip_to_write_src = (None, "")
                        mach.incr_use_count()
                        dhcp_written, dhcp_write, dhcp_last_error = (machdat["dhcp_written"], machdat["dhcp_write"], machdat["dhcp_error"])
                        # list of om_shell commands
                        om_shell_coms, err_lines = ([], [])
                        #print mach.name, it_com, force_flag, dhcp_write, dhcp_written
                        # try to determine om_shell_coms
                        if it_com == "alter_macadr":
                            if dhcp_written:
                                if dhcp_write and ip_to_write:
                                    om_shell_coms = ["delete", "write"]
                                else:
                                    om_shell_coms = ["delete"]
                            else:
                                if dhcp_write and ip_to_write:
                                    om_shell_coms = ["write"]
                                else:
                                    om_shell_coms = ["delete"]
                        elif it_com == "write_macadr":
                            if dhcp_write and ip_to_write:
                                om_shell_coms = ["write"]
                            else:
                                om_shell_coms = []
                        elif it_com == "delete_macadr":
                            if dhcp_write:
                                om_shell_coms = ["delete"]
                            else:
                                om_shell_coms = []
                        log_queue.put(("L", (my_name, "transformed dhcp_com %s to %s: %s (%s)" % (it_com,
                                                                                                  logging_tools.get_plural("om_shell_command", len(om_shell_coms)),
                                                                                                  ", ".join(om_shell_coms),
                                                                                                  ip_to_write and "ip %s from %s" % (ip_to_write, ip_to_write_src) or "no ip"),
                                             machdat["name"])))
                        # global success of all commands
                        g_success = 1
                        # dict of dev_fields to change
                        dev_sql_fields = {}
                        for om_shell_com in om_shell_coms:
                            om_array = ['server 127.0.0.1',
                                        'port 7911',
                                        'connect',
                                        'new host',
                                        'set name = "%s"' % (machdat["name"])]
                            if om_shell_com == "write":
                                om_array.extend(['set hardware-address = %s' % (machdat["macadr"]),
                                                 'set hardware-type = 1',
                                                 'set ip-address=%s' % (machdat["ip"])])
                                if g_config["NETBOOT"]:
                                    om_array.extend(['set statements = "'+
                                                     'supersede host-name = \\"%s\\" ;' % (machdat["name"])+
                                                     'if substring (option vendor-class-identifier, 0, 9) = \\"PXEClient\\" { '+
                                                     'filename = \\"etherboot/%s/pxelinux.0\\" ; ' % (ip_to_write)+
                                                     '} '+
                                                     'if substring (option vendor-class-identifier, 0, 9) = \\"Etherboot\\" { '+
                                                     'filename = \\"etherboot/%s/bootnet\\" ; ' % (ip_to_write)+
                                                     'option vendor-encapsulated-options 3c:09:45:74:68:65:72:62:6f:6f:74:ff;'+
                                                     '} "'])
                                else:
                                    om_array.extend(['set statements = "'+
                                                     'supersede host-name = \\"%s\\" ;' % (machdat["name"])+
                                                     'if substring (option vendor-class-identifier, 0, 9) = \\"PXEClient\\" { '+
                                                     'filename = \\"etherboot/%s/pxelinux.0\\" ; ' % (ip_to_write)+
                                                     '} "'])
                                om_array.append('create')
                            elif om_shell_com == "delete":
                                om_array.extend(['open',
                                                 'remove'])
                            else:
                                log_queue.put(("L", (my_name, "Internal error: Unknown om_shell command %s" % (om_shell_com))))
                            #print om_array
                            log_queue.put(("L", (my_name, "starting omshell for command %s (%s)" % (om_shell_com,
                                                                                                    ip_to_write and "ip %s from %s" % (ip_to_write, ip_to_write_src) or "no ip"),
                                                 machdat["name"])))
                            (errnum, outstr) = commands.getstatusoutput("echo -e '%s' | /usr/bin/omshell" % ("\n".join(om_array)))
                            #print errnum, outstr
                            if errnum == 0:
                                for line in [x.strip()[2:].strip() for x in outstr.split("\n") if x.strip().startswith(">")]:
                                    if len(line):
                                        if not line.startswith(">") and not line.startswith("obj:"):
                                            omm = om_error.match(line)
                                            if omm:
                                                #print mach.name, ":", omm.group(1), "*", omm.group(2)
                                                #print om_array
                                                errnum, g_success, errline = (1, 0, line)
                                                errfac, errstr = (omm.group(1), omm.group(2))
                                        elif re.match("^.*connection refused.*$", line):
                                            errnum, g_success, errline = (1, 0, line)
                                            errfac, errstr = ("connection refused", "server")
                            else:
                                g_success = 0
                                errline, errstr, errfac = ("command error", "error", "omshell")
                            if errnum:
                                log_queue.put(("L", (my_name, "omshell for command %s returned error %s (%s)" % (om_shell_com, errline, errstr), machdat["name"])))
                                log_queue.put(("L", (my_name, "error: %s" % (errline), mach.name)))
                            else:
                                log_queue.put(("L", (my_name, "finished omshell for command %s successfully" % (om_shell_com), machdat["name"])))
                            # error handling
                            #print "++++", act_com, "---", mach.name, dhcp_written
                            new_dhcp_written = None
                            if errnum:
                                if errstr == "key conflict":
                                    new_dhcp_written = 0
                                elif errstr == "already exists":
                                    new_dhcp_written = 1
                                elif errstr == "not found":
                                    new_dhcp_written = 0
                                errline = "dhcp-error: %s (%s)" % (errstr, errfac)
                                err_lines.append("%s: %s" % (om_shell_com, errline))
                            else:
                                err_lines.append("%s: ok" % (om_shell_com))
                                if om_shell_com == "write":
                                    new_dhcp_written = 1
                                elif om_shell_com == "delete":
                                    new_dhcp_written = 0
                            if new_dhcp_written is not None:
                                dhcp_written = new_dhcp_written
                                dev_sql_fields["dhcp_written"] = "%d" % (dhcp_written)
                            if dhcp_write:
                                dhw_0 = "write"
                            else:
                                dhw_0 = "no write"
                            if dhcp_written:
                                dhw_1 = "written"
                            else:
                                dhw_1 = "not written"
                            log_queue.put(("L", (my_name, "dhcp_info: %s/%s, mac-address is %s" % (dhw_0, dhw_1, machdat["macadr"]), machdat["name"])))
                        if g_success:
                            loc_result = "ok done"
                        else:
                            loc_result = "error: %s" % ("/".join(err_lines))
                        if not om_shell_coms:
                            om_shell_coms = ["<nothing>"]
                        dhcp_act_error = loc_result
                        if dhcp_act_error != dhcp_last_error:
                            dev_sql_fields["dhcp_error"] = "'%s'" % (mysql_tools.my_escape(dhcp_act_error))
                        log_queue.put(("L", (my_name, "dhcp command(s) %s (om: %s) result: %s" % (it_com,
                                                                                                  ", ".join(om_shell_coms),
                                                                                                  loc_result), machdat["name"])))
                        all_rets_dict[machdat["name"]] = loc_result
                        if dev_sql_fields:
                            sql_str = "UPDATE device SET %s WHERE name='%s'" % (", ".join(["%s=%s" % (x, y) for x, y in dev_sql_fields.iteritems()]), mach.name)
                            dbcon.dc.execute(sql_str)
                        mach.decr_use_count()
                    else:
                        log_queue.put(("L", (my_name, "error maintenance IP (write_macadr) not set for node %s" % (machdat["name"]))))
                        all_rets_dict[machdat["name"]] = "error maintenance IP (write_macadr) not set for node %s" % (machdat["name"])
                if empty_result:
                    log_queue.put(("L", (my_name, "SQL-Query %s gave empty result ?" % (sql_str))))
                if key:
                    res_com = server_command.server_reply()
                    res_com.set_node_results(all_rets_dict)
                    if empty_result:
                        res_com.set_warn_result("empty SQL result")
                    else:
                        res_com.set_ok_result("ok")
                    sreq_queue.put(("CR", (key, res_com)))
        else:
            print "mes_arg:", mes_arg
    log_queue.put(("L", (my_name, "proc %d: %s-thread for mother exiting" % (my_pid, my_name))))
    main_queue.put(("I", ("exiting", my_name)))

def configure_thread(main_queue, log_queue, own_queue, sql_queue, msi_block):
    my_name = threading.currentThread().getName()
    my_pid = os.getpid()
    process_tools.append_pids("mother/mother")
    if msi_block:
        msi_block.add_actual_pid()
        msi_block.save_block()
    log_queue.put(("L", (my_name, "proc %d: %s-thread for mother is now awake" % (my_pid, my_name))))
    # get server ip and netmask
    dbcon = mysql_tools.db_con()
    num_server, server_idx = process_tools.is_server(dbcon.dc, "mother_server")
    dbcon.dc.execute("SELECT i.ip, nw.netmask FROM netip i, netdevice n, network nw, device d, device_config dc, new_config c, network_type nt WHERE dc.device=d.device_idx AND dc.new_config=c.new_config_idx AND c.name='mother_server' AND i.netdevice=n.netdevice_idx AND nw.network_idx=i.network AND nt.identifier='b' AND nt.network_type_idx=nw.network_type AND n.device=d.device_idx AND d.device_idx=%d" % (server_idx))
    server_ip = dbcon.dc.fetchone()
    if server_ip:
        log_queue.put(("L", (my_name, "IP in bootnet at %s (netmask %s)" % (server_ip["ip"], server_ip["netmask"]))))
    else:
        log_queue.put(("L", (my_name, "found no IP in bootnet")))
    del dbcon
    #print "**", server_ip
    ether_pf = "/usr/lib/etherboot"
    pxe_pf = "%s/pxelinux.cfg" % (g_config["TFTP_DIR"])
    eepro100_pxe_fn = "/usr/lib/etherboot/pxe/eepro100.pxe"
    if os.path.isfile(eepro100_pxe_fn):
        eepro100_pxe = file(eepro100_pxe_fn, "r").read()
    else:
        eepro100_pxe = None
    # check etherboot
    #for w, s in [("NET", netboot_ok), ("PXE", pxeboot_ok)]:
    #    log_queue.put(("L", (my_name, "%sboot status: %d (%s)" % (w, s, {0 : "error", 1 : "OK"}[s]))))
    while 1:
        mes_type, mes_arg = own_queue.get()
        if mes_type == "I":
            mes_arg, mes_thread = mes_arg
            if mes_arg == "exit":
                break
            else:
                print "mes_arg:", mes_arg
        elif mes_type == "C":
            dbcon = mysql_tools.db_con()
            what, r_queue, mach, key = mes_arg
            #print what, r_queue, mach, key
#            mach = it.mach
            if what in ["refresh_tk", "refresh_all"]:
                mach_struct = devname_dict[mach]
                mach_struct.incr_use_count()
                mach_struct.check_network_settings(dbcon.dc)
                if mach_struct.node:
                    dbcon.dc.execute("SELECT d.newkernel, d.new_kernel, s.status, d.kernel_append, d.prod_link, d.bootnetdevice FROM device d, status s, device_type dt, netdevice n WHERE d.name='%s' AND d.newstate=s.status_idx AND d.device_type=dt.device_type_idx AND dt.identifier='H' AND n.device=d.device_idx AND n.netdevice_idx=d.bootnetdevice" % (mach_struct.name))
                    newk = dbcon.dc.fetchone()
                    #print dbcon,newk, mach.name
                    if newk:
                        refresh_str = "refresh for target_state %s" % (newk["status"])
                        prod_link = newk["prod_link"]
                        if prod_link:
                            dbcon.dc.execute("SELECT nw.identifier, nw.name FROM network nw WHERE nw.network_idx=%d" % (prod_link))
                            pnet = dbcon.dc.fetchone()
                            if pnet:
                                prod_net = pnet["identifier"]
                                refresh_str += ", production net %s (%s)" % (prod_net, pnet["name"])
                        else:
                            prod_net = None
                        if newk["status"] in LIST_TAGKERNEL:
                            new_kernel_name = get_kernel_name(dbcon.dc, newk["newkernel"], newk["new_kernel"])
                            refresh_str += " and kernel %s" % (new_kernel_name)
                        ret_str = "ok starting %s" % (refresh_str)
                        mach_struct.log(ret_str)
                        if r_queue:
                            r_queue.put(("ER", (what, mach, 0, ret_str, key)))
                        # generate netboot-drivers for disk and lilo
                        if g_config["NETBOOT"]:
                            mach_struct.write_netboot_config()
                        # delete old pxe/net files
                        pxe_file = mach_struct.get_pxe_file_name()
                        net_file = mach_struct.get_net_file_name()
                        # remove old bootpxe
                        if os.path.exists(pxe_file):
                            os.unlink(pxe_file)
                        # unlink net_file only if we change to memtest/dosboot
                        if ((not newk["status"] in LIST_TAGKERNEL) or os.path.islink(net_file)) and os.path.exists(net_file):
                            os.unlink(net_file)
                        # pxe and net kernel boot config
                        #print ip_to_write, newk["status"], lIST_TAGKERNEL
                        if newk["status"] in LIST_TAGKERNEL:
                            #print newk.keys(), server_ip
                            # unlink old initrd/kernel links
                            if server_ip:
                                mach_struct.write_kernel_config(sql_queue, new_kernel_name, newk["kernel_append"], server_ip["ip"], server_ip["netmask"])
                                if g_config["NETBOOT"]:
                                    # check if we have to rebuild the kernel
                                    kernel_src_name = "%s/kernels/%s/bzImage" % (g_config["TFTP_DIR"], new_kernel_name)
                                    initrd_src_name = "%s/kernels/%s/initrd.gz" % (g_config["TFTP_DIR"], new_kernel_name)
                                    if os.path.exists(kernel_src_name) and os.path.exists(initrd_src_name):
                                        kernel_src_mtime = os.stat(kernel_src_name)[stat.ST_MTIME]
                                        initrd_src_mtime = os.stat(initrd_src_name)[stat.ST_MTIME]
                                        rebuild = 1
                                        if os.path.exists(net_file):
                                            kernel_dst_mtime = os.stat(net_file)[stat.ST_MTIME]
                                            rebuild = (max(kernel_src_mtime, initrd_src_mtime) >= kernel_dst_mtime)
                                        else:
                                            rebuild = 1
                                        if rebuild:
                                            if os.path.isfile("/usr/bin/mkelf-linux"):
                                                rebuild_com = "/usr/bin/mkelf-linux %s %s --output=%s -d /dev/ram0 --append=\"%s\" --ip=%s:%s:0.0.0.0:%s:%s" % (kernel_src_name, initrd_src_name, net_file, mach_struct.get_append_line(newk["kernel_append"]), mach_struct.maint_ip, server_ip["ip"], server_ip["netmask"], mach_struct.name)
                                                print rebuild_com
                                            else:
                                                rebuild_com = "/usr/bin/mknbi-linux %s -r %s -o %s -d /dev/ram0 -a \"%s\" -i %s:%s:0.0.0.0:%s" % (kernel_src_name, initrd_src_name, net_file, mach_struct.get_append_line(newk["kernel_append"]), mach_struct.maint_ip, server_ip["ip"], server_ip["netmask"])
                                            mach_struct.log("Starting system() call: '%s'" % (rebuild_com))
                                            os.system(rebuild_com)
                        elif newk["status"] in LIST_DOSBOOT:
                            mach_struct.write_dosboot_config(eepro100_pxe)
                        elif newk["status"] in LIST_MEMTEST:
                            mach_struct.write_memtest_config()
                        elif newk["status"] in LIST_BOOTLOCAL:
                            mach_struct.write_localboot_config()
                        #  else:
                        #    print "Netboot not available"
                        #    print mach.maint_ip, mach.boot_type
                        log_queue.put(("L", (my_name, "refresh (tk) finished", mach_struct.name)))
                    else:
                        log_queue.put(("L", (my_name, "newk not defined", mach_struct.name)))
                        if r_queue:
                            r_queue.put(("ER", (what, mach, 0, "error newk not defined", key)))
                else:
                    if r_queue:
                        r_queue.put(("ER", (what, mach, 0, "error not node", key)))
                mach_struct.decr_use_count()
            if what in ["readdots", "refresh_all"]:
                mach_struct = devname_dict[mach]
                mach_struct.incr_use_count()
                if not mach_struct.node:
                    log_queue.put(("L", (my_name, "not node, checking network settings", mach_struct.name)))
                    mach_struct.check_network_settings(dbcon.dc)
                if mach_struct.node:
                    c_dir = mach_struct.get_config_dir()
                    log_queue.put(("L", (my_name, "starting readdots in '%s'" % (c_dir), mach_struct.name)))
                    hlist = [(".version"  , "imageversion"       , None             ),
                             (".imagename", "actimage"           , None             ),
                             (".imagename", "act_image"          , "image"          ),
                             (".kernel"   , "actkernel"          , None             ),
                             (".kernel"   , "act_kernel"         , "kernel"         ),
                             (".kversion" , "kernelversion"      , None             ),
                             (".parttype" , "act_partition_table", "partition_table"),
                             (None        , "act_kernel_build"   , None             )]
                    dbcon.dc.execute("SELECT %s FROM device d WHERE d.name='%s'" % (", ".join(["d.%s" % (b) for a, b, c in hlist]), mach_struct.name))
                    act_conf = dbcon.dc.fetchone()
                    s_list = []
                    num_tried, num_ok = (0, 0)
                    for filen, dbentry, orig_db in hlist:
                        if filen:
                            num_tried += 1
                            try:
                                line = file("%s/%s" % (c_dir, filen), "r").readline().strip()
                            except:
                                pass
                            else:
                                num_ok += 1
                                if orig_db:
                                    dbcon.dc.execute("SELECT x.%s_idx FROM %s x WHERE x.name='%s'" % (orig_db, orig_db, MySQLdb.escape_string(line)))
                                    if dbcon.dc.rowcount:
                                        line = int(dbcon.dc.fetchone()["%s_idx" % (orig_db)])
                                    else:
                                        line = 0
                                if act_conf[dbentry] != line:
                                    act_conf[dbentry] = line
                                    if type(line) == type(2):
                                        s_list.append("%s=%d" % (dbentry, line))
                                    else:
                                        s_list.append("%s='%s'" % (dbentry, MySQLdb.escape_string(line)))
                    # dirty hack
                    if act_conf["act_kernel"] and act_conf["actkernel"] and act_conf["kernelversion"]:
                        if re.match("^(\d+)\.(\d+)$", act_conf["kernelversion"]):
                            log_queue.put(("L", (my_name, " - dirty hack to guess act_kernel_build (act_kernel %d, act_version %s)" % (act_conf["act_kernel"], act_conf["kernelversion"]), mach_struct.name)))
                            dbcon.dc.execute("SELECT kernel_build_idx FROM kernel_build WHERE kernel=%d AND version=%d AND release=%d" % (act_conf["act_kernel"],
                                                                                                                                          int(act_conf["kernelversion"].split(".")[0]),
                                                                                                                                          int(act_conf["kernelversion"].split(".")[1])))
                            if dbcon.dc.rowcount:
                                line = dbcon.dc.fetchone()["kernel_build_idx"]
                                if act_conf["act_kernel_build"] != line:
                                    s_list.append("act_kernel_build=%d" % (line))
                        else:
                            log_queue.put(("L", (my_name, "*** cannot parse kernelversion '%s'" % (act_conf["kernelversion"]), mach_struct.name)))
                    if len(s_list):
                        dbcon.dc.execute("UPDATE device SET %s WHERE name='%s'" % (", ".join(s_list), mach_struct.name))
                    num_changed = len(s_list)
                    ret_str = "ok read %d changed dotfiles" % (num_changed)
                    log_queue.put(("L", (my_name, "readdots finished (%d tried, %d ok, %d changed%s)" % (num_tried, num_ok, num_changed, (num_changed and " [%s]" % (",".join(s_list)) or "")), mach_struct.name)))
                else:
                    ret_str = "error %s is not a node (network settings checked)" % (mach)
                if r_queue:
                    r_queue.put(("ER", (what, mach, 0, ret_str, key)))
                mach_struct.decr_use_count()
            else:
                pass
            del dbcon
        else:
            log_queue.put(("L", (my_name, "Got unknown message type %s (%s)" % (mes_type, mes_arg))))
    log_queue.put(("L", (my_name, "proc %d: %s-thread for mother exiting" % (my_pid, my_name))))
    main_queue.put(("I", ("exiting", my_name)))

def prepare_directories():
    for d in [g_config["TFTP_DIR"], g_config["ETHERBOOT_DIR"], g_config["CONFIG_DIR"]]:
        if not os.path.isdir(d):
            try:
                os.mkdir(d)
            except:
                pass

def database_sync(my_name, log_queue, new_names = [], new_ips = []):
    dbcon = mysql_tools.db_con()
    if not new_names:
        log_queue.put(("L", (my_name, "Checking for bootdev->netbootdevice changes")))
        dbcon.dc.execute("DESCRIBE device")
        all_fields = [x["Field"] for x in dbcon.dc.fetchall()]
        if "bootdev" in all_fields:
            db_ok = dbcon.dc.execute("SELECT d.name,d.device_idx,n.netdevice_idx,d.bootdev,n.devname FROM device d, netdevice n, netip ip, network nw, network_type nt WHERE ip.netdevice=n.netdevice_idx AND ip.network=nw.network_idx AND n.device=d.device_idx AND d.bootserver=%d AND nt.network_type_idx=nw.network_type AND nt.identifier='b' AND NOT d.bootnetdevice" % (mother_server_idx))
            if db_ok:
                for x in dbcon.dc.fetchall():
                    log_queue.put(("L", (my_name, " adapting device '%s' (index %d), bootdev '%s' -> bootnetdevice %d" % (x["name"], x["device_idx"], x["devname"], x["netdevice_idx"]))))
                    dbcon.dc.execute("UPDATE device SET bootnetdevice=%d WHERE name='%s'" % (x["netdevice_idx"], x["name"]))
        log_queue.put(("L", (my_name, "Checking for network type changes (x->o)")))
        db_ok = dbcon.dc.execute("SELECT nw.name,nw.network_idx FROM network nw, network_type nt WHERE nw.network_type=nt.network_type_idx AND nt.identifier='x'")
        if db_ok:
            all_net_idx = dict([(x["network_idx"], x["name"]) for x in dbcon.dc.fetchall()])
            if all_net_idx:
                log_queue.put(("L", (my_name, "Modifying network_type of %d networks: %s" % (len(all_net_idx.keys()), ", ".join(["'%s'" % (x) for x in all_net_idx.values()])))))
                dbcon.dc.execute("SELECT nt.network_type_idx FROM network_type nt WHERE nt.identifier='o'")
                new_nt_idx = dbcon.dc.fetchone()["network_type_idx"]
                sql_str = "UPDATE network SET network_type=%d,write_bind_config=0 WHERE (%s)" % (new_nt_idx, " OR ".join(["network_idx=%d" % (x) for x in all_net_idx.keys()]))
                dbcon.dc.execute(sql_str)
            #log_queue.
        log_queue.put(("L", (my_name, "Checking for netdevice.alias->netip.alias changes")))
        dbcon.dc.execute("DESCRIBE netdevice")
        all_fields = [x["Field"] for x in dbcon.dc.fetchall()]
        if "alias" in all_fields:
            dbcon.dc.execute("SELECT n.netdevice_idx,n.alias,i.netip_idx,i.alias AS netip_alias FROM netdevice n LEFT JOIN netip i ON i.netdevice=n.netdevice_idx ORDER BY n.netdevice_idx")
            for x in dbcon.dc.fetchall():
                if x["alias"] and not x["netip_alias"] and x["netip_idx"]:
                    if x["alias"] == "localhost":
                        dbcon.dc.execute("UPDATE netip SET alias='%s',alias_excl=1 WHERE netip_idx=%d" % (mysql_tools.my_escape(x["alias"]), x["netip_idx"]))
                    else:
                        dbcon.dc.execute("UPDATE netip SET alias='%s' WHERE netip_idx=%d" % (mysql_tools.my_escape(x["alias"]), x["netip_idx"]))
        # check for missing network_device_type_indices
        if glob_ndt_dict:
            dbcon.dc.execute("SELECT n.netdevice_idx,n.devname,n.network_device_type FROM netdevice n")
            for x in dbcon.dc.fetchall():
                new_ndt_idx = [glob_ndt_dict[y] for y in glob_ndt_dict.keys() if x["devname"].startswith(y)][0]
                if new_ndt_idx != x["network_device_type"]:
                    dbcon.dc.execute("UPDATE netdevice SET network_device_type=%d WHERE netdevice_idx=%d" % (new_ndt_idx, x["netdevice_idx"]))
    if new_names:
        sql_add_str = "AND (%s)" % (" OR ".join(["d.name='%s'" % (x) for x in new_names]))
    elif new_ips:
        sql_add_str = "AND (%s)" % (" OR ".join(["ip.ip='%s'" % (x) for x in new_ip]))
    else:
        sql_add_str = ""
    # newer use ips from slave networks
    dbcon.dc.execute("SELECT d.name,d.device_mode,d.device_idx,ip.ip,dt.identifier,d.recvstate,d.reqstate FROM network nw, device d, netip ip, netdevice nd, device_type dt, network_type nt WHERE dt.device_type_idx=d.device_type AND ip.netdevice=nd.netdevice_idx AND ip.network=nw.network_idx AND nd.device=d.device_idx AND d.bootserver=%d AND nt.network_type_idx=nw.network_type AND nt.identifier != 's' %s ORDER BY d.name,nd.devname,ip.ip" % (mother_server_idx, sql_add_str))
    mach_stuff = {}
    for mach in dbcon.dc.fetchall():
        name = mach["name"]
        if not mach_stuff.has_key(name):
            mach_stuff[name] = {"device_idx"  : mach["device_idx"],
                                "identifier"  : mach["identifier"],
                                "recvstate"   : mach["recvstate"],
                                "reqstate"    : mach["reqstate"],
                                "device_mode" : mach["device_mode"]}
    for name, mach_stuff in mach_stuff.iteritems():
        dbcon.dc.init_logs()
        if not devname_dict.has_key(name):
            #print "*", name, mach_stuff[name]
            if mach_stuff["identifier"] == "H":
                newmach = machine(name, mach_stuff["device_idx"], log_queue, dbcon.dc)
                newmach.set_recv_req_state(mach_stuff["recvstate"], mach_stuff["reqstate"])
                newmach.set_device_mode(mach_stuff["device_mode"])
            elif mach_stuff["identifier"] == "AM":
                napc = apc(name, mach_stuff["device_idx"], log_queue, dbcon.dc)
                napc.set_recv_req_state(mach_stuff["recvstate"], mach_stuff["reqstate"])
        else:
            log_queue.put(("L", (my_name, "Device %s already in internal dictionaries, checking network settings ..." % (name))))
            devname_dict[name].check_network_settings(dbcon.dc)
    del dbcon

# main thread. Handles keyboard interrupts (for interactive mode) and listens to the various sockets

class recv_mother_status(command_stack.recv_obj):
    def __init__(self):
        command_stack.recv_obj.__init__(self, "mother_status")
    def feed_sc(self, srv_com, cs, loc_data, data):
        ret_str = self.feed(cs, loc_data, data)
        s_reply = server_command.server_reply()
        if ret_str.startswith("ok"):
            s_reply.set_ok_result(ret_str)
        else:
            s_reply.set_error_result(ret_str)
        return s_reply
    def feed(self, cs, loc_data, data):
        num_threads = len(run_thread_list)
        num_ok = len([x for x in [y.isAlive() for y in run_thread_list] if x])
        if num_ok == num_threads:
            ret_str = "ok all %s running" % (logging_tools.get_plural("thread", num_ok))
        else:
            ret_str = "error only %d of %s running" % (num_ok,
                                                       logging_tools.get_plural("thread", num_threads))
        return ret_str
        
class recv_hopcount_table_changed(command_stack.recv_obj):
    def __init__(self):
        command_stack.recv_obj.__init__(self, "hopcount_table_changed")
    def feed_sc(self, srv_com, cs, loc_data, data):
        ret_str = self.feed(cs, loc_data, data)
        s_reply = server_command.server_reply()
        if ret_str.startswith("ok"):
            s_reply.set_ok_result(ret_str)
        else:
            s_reply.set_error_result(ret_str)
        return s_reply
    def feed(self, cs, loc_data, data):
        all_nodes = devname_dict.keys()
        all_nodes.sort()
        self.log(cs, "hopcount_table_changed, working on %s: %s" % (logging_tools.get_plural("node", len(all_nodes)),
                                                                    logging_tools.compress_list(all_nodes)))
        q_dict = cs.get_command_stack().get_queue_dict()
        q_dict["node"].put(("R", server_command.server_command(command = "ip_changed", nodes=all_nodes)))
        ret_str = "ok working on %s" % (logging_tools.get_plural("node", len(all_nodes)))
        return ret_str
        
class recv_check_kernel_dir(command_stack.recv_obj):
    def __init__(self):
        command_stack.recv_obj.__init__(self, "check_kernel_dir")
        self.__thread_running = False
    def feed_sc(self, srv_com, cs, loc_data, data):
        ret_str = self.feed(cs, loc_data, data, srv_com)
        if type(ret_str) == type(""):
            s_reply = server_command.server_reply()
            if ret_str.startswith("ok"):
                s_reply.set_ok_result(ret_str)
            else:
                s_reply.set_error_result(ret_str)
        else:
            s_reply = ret_str
        return s_reply
    def set_thread_running_state(self, ts):
        self.__thread_running = ts
    def feed(self, cs, loc_data, data, srv_com=None):
        if self.__thread_running:
            ret_str = "ok already running"
        else:
            q_dict = cs.get_command_stack().get_queue_dict()
            msi_block = cs.get_command_stack().get_msi_block()
            q_dict["sreq"].put(("TI", ("kernel_check_thread")))
            kct_code = threading.Thread(name = "kernel_check_thread", target=kernel_check_thread_code, args = [q_dict["sreq"], q_dict["log"], None, msi_block, srv_com])
            kct_code.start()
            self.__thread_running = True
            ret_str = None
        return ret_str

class kernel(object):
    def __init__(self, name, root_dir, log_queue, dc):
        # meassure the lifetime
        self.__slots__ = []
        self.__start_time = time.time()
        self.__db_idx = 0
        self.__dc = dc
        self.name = name
        self.root_dir = root_dir
        self.path = os.path.normpath("%s/%s" % (self.root_dir, self.name))
        self.__bz_path = "%s/bzImage" % (self.path)
        self.__initrd_path = "%s/initrd.gz" % (self.path)
        self.__option_dict = {"database"   : False}
        self.__log_queue = log_queue
        self.__thread_name = threading.currentThread().getName()
        self.__initrd_built = None
        if not os.path.isdir(self.path):
            raise IOError, "kernel_dir %s is not a directory" % (self.path)
        if not os.path.isfile(self.__bz_path):
            raise IOError, "kernel_dir %s has no bzImage" % (self.path)
        if not os.path.isfile(self.__initrd_path):
            raise IOError, "kernel_dir %s has no initrd.gz" % (self.path)
        # init db-Fields
        self.__checks = []
        self.__db_kernel = {"name"         : self.name,
                            "target_dir"   : self.path,
                            "initrd_built" : None,
                            "module_list"  : ""}
        self.check_md5_sums()
    def log(self, what):
        self.__log_queue.put(("L", (self.__thread_name, "%s: %s" % (self.name, what))))
    def check_md5_sums(self):
        bzimage_md5_name, initrd_md5_name = (os.path.normpath("%s/.bzImage_md5" % (self.path)),
                                             os.path.normpath("%s/.initrd_md5" % (self.path)))
        new_bz5 = True
        if os.path.isfile(bzimage_md5_name) and os.path.isfile(initrd_md5_name):
            try:
                if os.stat(self.__bz_path)[stat.ST_MTIME] < os.stat(bzimage_md5_name) and os.stat(self.__initrd_path)[stat.ST_MTIME] < os.stat(initrd_md5_name):
                    new_bz5 = False
            except:
                self.log("*** Error checking timestamps for MD5, trying to recreate MD5 sums (%s): %s" % (str(sys.exc_info()[0]),
                                                                                                          str(sys.exc_info()[1])))
            else:
                self.__option_dict["bzimage.md5"] = file(bzimage_md5_name, "r").read()
                self.__option_dict["initrd.md5"] = file(initrd_md5_name, "r").read()
        if new_bz5:
            self.__checks.append("MD5")
            bzimage_md5 = md5.new(file(self.__bz_path, "r").read())
            initrd_md5  = md5.new(file(self.__initrd_path, "r").read())
            self.__option_dict["bzimage.md5"] = bzimage_md5.hexdigest()
            self.__option_dict["initrd.md5"] = initrd_md5.hexdigest()
            file(bzimage_md5_name, "w").write(self.__option_dict["bzimage.md5"])
            file(initrd_md5_name, "w").write(self.__option_dict["initrd.md5"])
    def set_db_kernel(self, db_k):
        self.__db_kernel = db_k
        self.__option_dict["database"] = True
        self.__db_idx = db_k["kernel_idx"]
    def get_db_kernel(self):
        return self.__db_kernel
    db_kernel = property(get_db_kernel, set_db_kernel)
    def check_initrd_modules(self):
        # update initrd_built and module_list from initrd.gz
        tfile_name = "%s/.initrd_check" % (g_config["LOG_DIR"])
        tdir_name  = "%s/.initrd_mdir" % (g_config["LOG_DIR"])
        if self.__db_kernel["initrd_built"] == None:
            self.__checks.append("initrd")
            initrd_built = os.stat(self.__initrd_path)[stat.ST_MTIME]
            self.__db_kernel["initrd_built"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(initrd_built))
            if self.__db_idx:
                self.__dc.execute("UPDATE kernel SET initrd_built=FROM_UNIXTIME(%d) WHERE kernel_idx=%d" % (initrd_built,
                                                                                                            self.__db_idx))
            try:
                file(tfile_name, "w").write(gzip.open(self.__initrd_path, "r").read())
            except:
                self.log("*** error reading %s (%s): %s" % (self.__initrd_path,
                                                            str(sys.exc_info()[0]),
                                                            str(sys.exc_info()[1])))
            else:
                if not os.path.isdir(tdir_name):
                    os.mkdir(tdir_name)
                m_com = "mount -o loop %s %s" % (tfile_name, tdir_name)
                um_com = "umount %s" % (tdir_name)
                cstat, out = commands.getstatusoutput(m_com)
                if cstat:
                    self.log("error mounting tempfile %s to %s: %s" % (tfile_name, tdir_name, out))
                else:
                    mod_dict = {}
                    for dir_name, dir_list, file_list in os.walk("%s/lib/modules" % (tdir_name)):
                        for mod_name in [x.split(".")[0] for x in file_list if x.count(".")]:
                            mod_dict.setdefault(mod_name, 0)
                    mod_list = mod_dict.keys()
                    mod_list.sort()
                    mod_list = ",".join(mod_list)
                    if mod_list:
                        self.log("found %s: %s" % (logging_tools.get_plural("module", len(mod_list.split(","))),
                                                   mod_list))
                    else:
                        self.log("found no modules")
                    if self.__db_idx:
                        if mod_list != self.__db_kernel["module_list"]:
                            self.__db_kernel["module_list"] = mod_list
                            if self.__db_idx:
                                self.__dc.execute("UPDATE kernel SET module_list='%s' WHERE kernel_idx=%d" % (mysql_tools.my_escape(self.__db_kernel["module_list"]),
                                                                                                              self.__db_idx))
                    cstat, out = commands.getstatusoutput(um_com)
                    if cstat:
                        self.log("error unmounting tempfile %s from %s: %s" % (tfile_name, tdir_name, out))
                os.rmdir(tdir_name)
                os.unlink(tfile_name)
        else:
            self.log("initrd_built already set")
    def check_comment(self):
        self.__checks.append("comment")
        comment_file = "%s/.comment" % (self.root_dir)
        if os.path.isfile(comment_file):
            try:
                comment = " ".join([x.strip() for x in file(comment_file, "r").read().split("\n")])
            except:
                self.log("*** error reading comment-file '%s'" % (comment_file))
                comment = ""
            else:
                pass
        else:
            comment = ""
        self.__db_kernel["comment"] = comment
        if self.__db_idx:
            self.__dc.execute("UPDATE kernel SET comment='%s' WHERE kernel_idx=%d" % (mysql_tools.my_escape(comment), self.__db_idx))
    def check_version_file(self):
        self.__checks.append("versionfile")
        kernel_version, k_ver, k_rel = (self.name.split("_")[0], 1, 1)
        if kernel_version == self.name:
            config_name = ""
        else:
            config_name = self.name[len(kernel_version) + 1 :]
        build_mach = ""
        version_file = "%s/.version" % (self.root_dir)
        if os.path.isfile(version_file):
            try:
                version_dict = dict([y.split("=", 1) for y in [x.strip() for x in file(version_file, "r").read().split("\n") if x.count("=")]])
            except:
                self.log("*** error parsing version-file '%s'" % (version_file))
            else:
                version_dict = dict([(x.lower(), y) for x, y in version_dict.iteritems()])
                if version_dict.get("kernelversion", kernel_version) != kernel_version:
                    self.log("*** warning: parsed kernel_version '%s' != version_file version '%s', using info from version_file" % (kernel_version, version_dict["kernelversion"]))
                    kernel_version = version_dict["kernelversion"]
                if version_dict.get("configname", config_name) != config_name:
                    self.log("*** warning: parsed config_name '%s' != version_file config_name '%s', using info from version_file" % (config_name, version_dict["configname"]))
                    config_name = version_dict["configname"]
                if version_dict.has_key("version"):
                    k_ver, k_rel = [int(x) for x in version_dict["version"].split(".", 1)]
                if version_dict.has_key("buildmachine"):
                    build_mach = version_dict["buildmachine"].split(".")[0]
                    self.__option_dict["kernel_is_local"] = build_mach == short_host_name
        if config_name:
            config_name = "/usr/src/configs/.config_%s" % (config_name)
        self.__db_kernel["kernel_version"] = kernel_version
        self.__db_kernel["version"] = k_ver
        self.__db_kernel["release"] = k_rel
        self.__db_kernel["config_name"] = config_name
        return build_mach
    def check_bzimage_file(self):
        self.__checks.append("bzImage")
        major, minor, patchlevel = [""] * 3
        build_mach = ""
        cstat, out = commands.getstatusoutput("file %s" % (self.__bz_path))
        if cstat:
            self.log("*** error, cannot file '%s' (%d): %s" % (self.__bz_path, cstat, out))
        else:
            for line in [x.strip().lower() for x in out.split(",")]:
                if line.startswith("version"):
                    vers_str = line.split()[1]
                    vers_parts = vers_str.split(".")
                    major, minor = (vers_parts.pop(0), vers_parts.pop(0))
                    patchlevel = ".".join(vers_parts)
                if line.count("@"):
                    build_mach = line.split("@", 1)[1].split(")")[0]
        self.__db_kernel["major"] = major
        self.__db_kernel["minor"] = minor
        self.__db_kernel["patchlevel"] = patchlevel
        return build_mach
    def check_kernel_dir(self):
        # if not in database read values from disk
        self.log("Checking directory %s ..." % (self.path))
        self.check_comment()
        kernel_build_machine_fvf = self.check_version_file()
        kernel_build_machine_vfc = self.check_bzimage_file()
        # determine build_machine
        if kernel_build_machine_fvf:
            build_mach = kernel_build_machine_fvf
        elif kernel_build_machine_vfc:
            build_mach = kernel_build_machine_vfc
        elif g_config["SET_DEFAULT_BUILD_MACHINE"]:
            build_mach = short_host_name
        else:
            build_mach = ""
        build_mach_idx = 0
        if build_mach:
            if build_mach:
                self.__dc.execute("SELECT d.device_idx FROM device d WHERE d.name='%s'" % (build_mach))
                if self.__dc.rowcount:
                    build_mach_idx = self.__dc.fetchone()["device_idx"]
        self.__option_dict["build_machine"] = build_mach
        self.__db_kernel["build_machine"] = build_mach
        self.__db_kernel["device"] = build_mach_idx
    def set_option_dict_values(self):
        # local kernel ?
        self.__option_dict["kernel_is_local"] = (self.__db_kernel["build_machine"] or "").split(".")[0] == short_host_name
        self.__option_dict["build_machine"] = self.__db_kernel["build_machine"]
    def insert_into_database(self):
        self.__checks.append("SQL insert")
        sql_ks = ", ".join(["%s=%s" % (k, type(v) == type(0) and "%d" % (v) or "'%s'" % (mysql_tools.my_escape(v))) for k, v in self.__db_kernel.iteritems()])
        self.__dc.execute("INSERT INTO kernel SET %s" % (sql_ks))
        self.__db_idx = self.__dc.insert_id()
        self.log("inserted new kernel at idx %d" % (self.__db_idx))
        sql_kbs = ", ".join(["%s=%s" % (k, type(v) == type(0) and "%d" % (v) or "'%s'" % (mysql_tools.my_escape(v))) for k, v in [(a, self.__db_kernel[a]) for a in ["version",
                                                                                                                                                                     "release",
                                                                                                                                                                     "build_machine",
                                                                                                                                                                     "device"]]] + ["kernel=%d" % (self.__db_idx)])
        self.__dc.execute("INSERT INTO kernel_build SET %s" % (sql_kbs))
        self.log("inserted kernel_build at idx %d" % (self.__dc.insert_id()))
        self.__option_dict["database"] = True
    def check_for_db_insert(self, ext_opt_dict):
        ins = False
        if not self.__option_dict["database"]:
            # check for insert_all or insert_list
            if ext_opt_dict["insert_all_found"] or self.name in ext_opt_dict["kernels_to_insert"]:
                # check for kernel locality
                kl_ok = self.__option_dict["kernel_is_local"]
                if not kl_ok:
                    if g_config["IGNORE_KERNEL_BUILD_MACHINE"] or ext_opt_dict["ignore_kernel_build_machine"]:
                        self.log("ignore kernel build_machine (global: %s, local: %s)" % (str(g_config["IGNORE_KERNEL_BUILD_MACHINE"]),
                                                                                          str(ext_opt_dict["ignore_kernel_build_machine"])))
                        kl_ok = True
                if not kl_ok:
                    self.log("*** kernel is not local (%s)" % (self.__option_dict["build_machine"]))
                else:
                    ins = True
        return ins
    def log_statistics(self):
        t_diff = time.time() - self.__start_time
        self.log("needed %.4f seconds, %s: %s" % (t_diff,
                                                  logging_tools.get_plural("check", len(self.__checks)),
                                                  ", ".join(self.__checks)))
    def get_option_dict(self):
        return self.__option_dict
        
def kernel_check_thread_code(ret_queue, log_queue, own_queue, msi_block, srv_com):
    my_name = threading.currentThread().getName()
    my_pid = os.getpid()
    process_tools.append_pids("mother/mother")
    log_queue.put(("L", (my_name, "proc %d: %s-thread for mother is now awake" % (my_pid, my_name))))
    if msi_block:
        msi_block.add_actual_pid()
        msi_block.save_block()
    if srv_com:
        ext_opt_dict = srv_com.get_option_dict()
        srv_reply = server_command.server_reply()
    else:
        ext_opt_dict = {}
        srv_reply = None
    opt_dict = dict([(k, ext_opt_dict.get(k, v)) for k, v in {"ignore_kernel_build_machine" : 0,
                                                              "kernels_to_insert"           : [],
                                                              "insert_all_found"            : 0}.iteritems()])
    log_queue.put(("L", (my_name, "option_dict as %s: %s" % (logging_tools.get_plural("key", len(opt_dict.keys())),
                                                             ", ".join(["%s (%s, %s)" % (k, str(type(v)), str(v)) for k, v in opt_dict.iteritems()])))))
    kernels_found, problems = ({}, [])
    # send reply now or do we need more data ?
    reply_now = opt_dict["insert_all_found"] == 1
    if srv_com:
        srv_reply.set_option_dict({"kernels_found" : kernels_found,
                                   "problems"      : problems})
    if srv_com and reply_now:
        srv_reply.set_ok_result("starting check of kernel_dir")
        ret_queue.put(("CR", (srv_com.get_key(), srv_reply)))
    dbcon = mysql_tools.db_con()
    dbcon.dc.execute("SELECT * FROM kernel ORDER BY name")
    if dbcon.dc.rowcount > 0:
        any_found_in_database = True
        all_kernels = dict([(x["name"], x) for x in dbcon.dc.fetchall()])
    else:
        any_found_in_database = False
        all_kernels = {}
    kct_start = time.time()
    log_queue.put(("L", (my_name, "Checking for kernels (%d already in database) ..." % (len(all_kernels.keys())))))
    # check number of mothers in this cluster
    dbcon.dc.execute("SELECT d.name, d.device_idx FROM device d, device_config dc, new_config c, device_group dg LEFT JOIN device d2 ON d2.device_idx = dg.device WHERE d.device_group=dg.device_group_idx AND dc.new_config=c.new_config_idx AND (dc.device=d.device_idx OR dc.device=d2.device_idx) AND c.name='mother_server'")
    mother_servers = [x["name"] for x in dbcon.dc.fetchall()]
    mother_servers.sort()
    log_queue.put(("L", (my_name, "found %s: %s" % (logging_tools.get_plural("mother_server", len(mother_servers)),
                                                    ", ".join(mother_servers)))))
    if opt_dict["kernels_to_insert"]:
        log_queue.put(("L", (my_name, " - only %s to insert: %s" % (logging_tools.get_plural("kernels", len(opt_dict["kernels_to_insert"])),
                                                                    ", ".join(opt_dict["kernels_to_insert"])))))
    if not os.path.isdir(g_config["TFTP_DIR"]):
        log_queue.put(("L", (my_name, "*** error: TFTP_DIR '%s' is not a directory" % (g_config["TFTP_DIR"]))))
        problems.append("TFTP_DIR '%s' is not a directory" % (g_config["TFTP_DIR"]))
    else:
        kern_dir = "%s/kernels" % (g_config["TFTP_DIR"])
        if not os.path.isdir(kern_dir):
            log_queue.put(("L", (my_name, "*** error: kernel_dir '%s' is not a directory" % (kern_dir))))
            problems.append("kernel_dir '%s' is not a directory" % (kern_dir))
        else:
            for entry in os.listdir(kern_dir):
                try:
                    act_kernel = kernel(entry, kern_dir, log_queue, dbcon.dc)
                except IOError, what:
                    log_queue.put(("L", (my_name, "*** error: %s" % (str(what)))))
                    problems.append(str(what))
                else:
                    if act_kernel.name in all_kernels.keys():
                        act_kernel.db_kernel = all_kernels[act_kernel.name]
                        act_kernel.check_initrd_modules()
                        act_kernel.check_comment()
                    else:
                        act_kernel.check_kernel_dir()
                    act_kernel.set_option_dict_values()
                    # determine if we should insert the kernel into the database
                    if act_kernel.check_for_db_insert(opt_dict):
                        act_kernel.check_initrd_modules()
                        act_kernel.insert_into_database()
                    kernels_found[act_kernel.name] = act_kernel.get_option_dict()
                    act_kernel.log_statistics()
                    del act_kernel
    kct_end = time.time()
    log_queue.put(("L", (my_name, "checking of kernel_dir took %.2f seconds" % (kct_end - kct_start))))
    del dbcon
    process_tools.remove_pids("mother/mother")
    if msi_block:
        msi_block.remove_actual_pid()
        msi_block.save_block()
    log_queue.put(("L", (my_name, "proc %d: %s-thread for mother exiting" % (my_pid, my_name))))
    ret_queue.put(("I", ("exiting", my_name)))
    # send reply after term-message
    if srv_com and not reply_now:
        srv_reply.set_ok_result("check kernel_dir")
        ret_queue.put(("CR", (srv_com.get_key(), srv_reply)))

class mother_command_stack(command_stack.command_stack):
    def __init__(self, net_server, queue_dict, msi_block):
        self.__queue_dict = queue_dict
        self.__name = threading.currentThread().getName()
        self.__msi_block = msi_block
        command_stack.command_stack.__init__(self, "mother_command_stack", net_server, {})
        self.add_command(recv_mother_status())
        self.add_command(recv_check_kernel_dir())
        self.add_command(recv_hopcount_table_changed())
    def log(self, what):
        self.__queue_dict["log"].put(("L", (self.__name, what)))
    def get_queue_dict(self):
        return self.__queue_dict
    def get_msi_block(self):
        return self.__msi_block
    def unknown_command(self, stream, com, srv_com, add_data):
        if not srv_com:
            # check for simple command
            stream.set_delete()
            ret_str = "error got unknown command %s (via SimpleText)" % (com)
        else:
            if com in ["alter_macadr", "write_macadr", "delete_macadr"]:
                self.__queue_dict["dhcpd"].put(("D", srv_com))
                ret_str = None
            elif com in ["reboot", "reboot_nd", "halt", "ping", "status", "refresh_tk", "readdots",
                         "refresh_hwi", "apc_dev", "apc_dev2", "apc_com", "apc_com2", "poweroff",
                         "remove_bs", "new_bs", "propagate", "ip_changed", "device_mode_change"]:
                srv_com.set_queue(self.__queue_dict["sreq"])
                self.__queue_dict["node"].put(("R", srv_com))
                ret_str = None
            else:
                stream.set_delete()
                ret_str = server_command.server_reply()
                ret_str.set_error_result("got unknown command %s (via ServerRequest)" % (com))
        return ret_str
    
def socket_server_thread_code(main_queue, log_queue, own_queue, dhcpd_queue, sreq_queue, node_queue, new_serv, msi_block):
    my_name = threading.currentThread().getName()
    my_pid = os.getpid()
    process_tools.append_pids("mother/mother")
    if msi_block:
        msi_block.add_actual_pid()
        msi_block.save_block()
    log_queue.put(("L", (my_name, "proc %d: %s-thread for mother is now awake" % (my_pid, my_name))))
    ip_match = re.compile("^(?P<ip>\d+\.\d+\.\d+\.\d+)(?P<stuff>.*)$")
    c_flag = 1
    bind_state = {}
    mcs = mother_command_stack(new_serv,
                               {"log"   : log_queue,
                                "dhcpd" : dhcpd_queue,
                                "node"  : node_queue,
                                "sreq"  : sreq_queue},
                               msi_block)
    running_threads = []
    while c_flag:
        mes_type, mes_arg = own_queue.get()
        if mes_type == "I":
            mes_arg, mes_thread = mes_arg
            if mes_arg == "exit":
                c_flag = 0
            elif mes_arg == "update":
                mcs.hello()
            elif mes_arg == "exiting":
                if mes_thread in running_threads:
                    running_threads.remove(mes_thread)
                    mcs.get_command("check_kernel_dir").set_thread_running_state(False)
                    log_queue.put(("L", (my_name, "removed %s from running_thread_list" % (mes_thread))))
                else:
                    log_queue.put(("L", (my_name, "cannot remove %s from running_thread_list" % (mes_thread))))
            else:
                log_queue.put(("L", (my_name, "got unknown message_type '%s'" % (mes_type))))
        elif mes_type == "TI":
            running_threads.append(mes_arg)
            log_queue.put(("L", (my_name, "%s running: %s" % (logging_tools.get_plural("thread", len(running_threads)),
                                                              ", ".join(running_threads)))))
        elif mes_type == "mslog":
            key, (loc_addr, other_addr, log_str), add_data = mes_arg
            log_queue.put(("L", (my_name, log_str)))
            if re.match("^Bind .* failed$", log_str):
                bind_state[loc_addr[1]] = "error"
            elif re.match("^Bind .* ok$", log_str):
                bind_state[loc_addr[1]] = "ok"
            if len(bind_state.keys()) == 2:
                if "error" in bind_state.values():
                    log_queue.put(("L", (my_name, "Binding to all ifs/sockets failed, exiting...")))
                    main_queue.put(("I", ("bind_error", my_name)))
                else:
                    log_queue.put(("L", (my_name, "Binding to all ifs/sockets ok")))
                    main_queue.put(("I", ("bind_ok", my_name)))
        elif mes_type == "mserr":
            key, (loc_addr, other_addr, (errnum, err_str)), add_data = mes_arg
            log_queue.put(("L", (my_name, "An error has occured: %d (%s)" % (errnum, err_str))))
        elif mes_type == "msrcv":
            key, ((loc_ip, loc_port), (source_host, source_port), recv), add_data = mes_arg
            if loc_port == g_config["NODEPORT"]:
                #print "N", mes_arg
                ipm = ip_match.match(recv)
                if ipm:
                    ip, recv = (ipm.group(1), ipm.group(2))
                else:
                    ip = source_host
                dev_name = devip_dict.get(ip, None)
                if dev_name:
                    ret_str = "Processed request from ip %s (%s)" % (ip, dev_name.get_name())
                    node_queue.put(("N", (dev_name, ip, (source_host, source_port), recv.strip(), time.time())))
                else:
                    ret_str = "Invalid source ip %s" % (ip)
                    log_queue.put(("L", (my_name, "Got invalid request from ip %s, port %d: %s" % (source_host, source_port, recv))))
                new_serv.set_result(key, ret_str)
            else:
                # feed into mother command stack
                mcs.feed(mes_type, mes_arg)
        elif mes_type == "FC":
            command = mes_arg
            dummy_cs = mcs.get_dummy_stream()
            log_queue.put(("L", (my_name, "Feeding server_command %s into dummy_stream" % (command.get_command()))))
            dummy_cs.feed(command, None)
            del dummy_cs
        elif mes_type == "CR":
            key, result = mes_arg
            mcs.feed_result(key, result)
        else:
            log_queue.put(("L", (my_name, "Error got unknown message type %s" % (mes_type))))
    if running_threads:
        while running_threads:
            log_queue.put(("L", (my_name, "waiting for %s to finish: %s" % (logging_tools.get_plural("thread", len(running_threads)),
                                                                            ", ".join(running_threads)))))
            mes_type, mes_arg = own_queue.get()
            if mes_type == "I":
                mes_arg, mes_thread = mes_arg
                if mes_arg == "exiting":
                    if mes_thread in running_threads:
                        running_threads.remove(mes_thread)
                        log_queue.put(("L", (my_name, "removed %s from running_thread_list" % (mes_thread))))
                    else:
                        log_queue.put(("L", (my_name, "cannot remove %s from running_thread_list" % (mes_thread))))
            else:
                log_queue.put(("L", (my_name, "got unknown message_type '%s'" % (mes_type))))
            
    log_queue.put(("L", (my_name, "proc %d: %s-thread for mother exiting" % (my_pid, my_name))))
    main_queue.put(("I", ("exiting", my_name)))

def check_netboot_functionality():
    g_config.add_config_dict({"PXEBOOT" : configfile.int_c_var(0, "default"),
                              "NETBOOT" : configfile.int_c_var(0, "default")})
    log_lines = []
    pxe_paths = ["/usr/share/syslinux/pxelinux.0", "/usr/lib/syslinux/pxelinux.0"]
    for pxe_path in pxe_paths:
        if os.path.isfile(pxe_path):
            try:
                pxelinux_0 = file(pxe_path, "r").read()
            except:
                log_lines.append("*** Found no pxelinux.0 in %s" % (pxe_path))
            else:
                g_config.add_config_dict({"PXEBOOT"    : configfile.int_c_var(1, "filesystem"),
                                          "PXELINUX_0" : configfile.blob_c_var(pxelinux_0, "filesystem")})
                log_lines.append("Found pxelinux.0 in %s" % (pxe_path))
                break
    ether_pf = "/usr/lib/etherboot"
    if os.path.isdir(ether_pf):
        try:
            lilo_eb_bin = file("%s/img/eepro100.img" % (ether_pf)).read()
        except:
            log_lines.append("*** Found no eepro100.img")
        else:
            g_config.add_config_dict({"NETBOOT" : configfile.int_c_var(1, "filesystem")})
            log_lines.append("Found eepro100.img")
    return log_lines

def check_nfs_exports(dbcon):
    log_lines = []
    if g_config["MODIFY_NFS_CONFIG"]:
        exp_file = "/etc/exports"
        if os.path.isfile(exp_file):
            act_exports = dict([(x[0], " ".join(x[1:])) for x in [y.strip().split() for y in file(exp_file, "r").read().split("\n")] if len(x) > 1 and x[0].startswith("/")])
            log_lines.append("found /etc/exports file with %s:" % (logging_tools.get_plural("export entrie", len(act_exports))))
            for act_exp, where in act_exports.iteritems():
                log_lines.append("  - %-30s to %s" % (act_exp, where))
        else:
            log_lines.append("found no /etc/exports file, creating new one ...")
            act_exports = {}
        valid_nt_ids = ["p", "b"]
        dbcon.dc.execute("SELECT nw.network, nw.netmask FROM network nw, network_type nt WHERE nt.network_type_idx=nw.network_type AND (%s)" % (" OR ".join(["nt.identifier='%s'" % (x) for x in valid_nt_ids])))
        exp_dict = {"etherboot" : "ro",
                    "kernels"   : "ro",
                    "images"    : "ro",
                    "config"    : "rw"}
        new_exports = {}
        exp_nets = ["%s/%s" % (x["network"], x["netmask"]) for x in dbcon.dc.fetchall()]
        if exp_nets:
            for exp_dir, rws in exp_dict.iteritems():
                act_exp_dir = "%s/%s" % (g_config["TFTP_DIR"], exp_dir)
                if not act_exp_dir in act_exports:
                    new_exports[act_exp_dir] = " ".join(["%s(%s,no_root_squash,async)" % (exp_net, rws) for exp_net in exp_nets])
        if new_exports:
            file(exp_file, "a").write("\n".join(["%-30s %s" % (x, y) for x, y in new_exports.iteritems()] + [""]))
            at_command = "/etc/init.d/nfsserver restart"
            at_stat, add_log_lines = start_at_command(at_command)
            log_lines.append("starting the at-command '%s' gave %d:" % (at_command, at_stat))
            log_lines.extend(add_log_lines)
    return log_lines

def get_network_type_indizes_and_net_devices(cc):
    # invalid network_type indizes
    cc.execute("SELECT i.ip,n.netdevice_idx,nw.network_idx FROM netdevice n, netip i, network nw WHERE n.device=%d AND i.netdevice=n.netdevice_idx AND i.network=nw.network_idx" % (mother_server_idx))
    glob_net_devices = {}
    for n in cc.fetchall():
        n_d, n_i, n_w = (n["netdevice_idx"], n["ip"], n["network_idx"])
        if not glob_net_devices.has_key(n_d):
            glob_net_devices[n_d] = []
        glob_net_devices[n_d].append((n_i, n_w))
    # get all network_device_types
    cc.execute("SELECT * FROM network_device_type")
    ndt_dict = dict([(x["identifier"], x["network_device_type_idx"]) for x in cc.fetchall()])
    return glob_net_devices, ndt_dict

def server_code(daemon):
    global devip_dict, devname_dict, glob_net_devices, main_queue, run_thread_list, glob_ndt_dict
    def log_hook(what):
        log_queue.put(("L", (threading.currentThread().getName(), what)))
    def new_pid_hook(arg):
        process_tools.append_pids("mother/mother", arg)
    signal.signal(signal.SIGTERM, sig_term_handler )
    signal.signal(signal.SIGINT , sig_int_handler  )
    signal.signal(signal.SIGTSTP, sig_tstp_handler )
    signal.signal(signal.SIGALRM, sig_alarm_handler)

    # database handle
    dbcon = mysql_tools.db_con()

    run_thread_list = [threading.currentThread()]
    my_name = threading.currentThread().getName()
    my_pid = os.getpid()
    # log lines for logging-threads
    log_lines = []
    # save pid
    process_tools.save_pid("mother/mother")
    # create directories if necessary
    prepare_directories()
    # get netboot_functionality (etherboot/netboot)
    log_lines.extend(check_netboot_functionality())
    # init queues
    log_lines.extend(check_nfs_exports(dbcon))
    log_queue    = Queue.Queue(100)
    main_queue   = Queue.Queue(100)
    node_queue   = Queue.Queue(1000)
    config_queue = Queue.Queue(100)
    dhcpd_queue  = Queue.Queue(100)
    sreq_queue   = Queue.Queue(100)
    snmp_queue   = Queue.Queue(500)
    sql_queue    = Queue.Queue(500)
    #throttle_queue = Queue.Queue(100)
    #syslog_check_num, syslog_check_counter = (6, 0)
    del_queues, update_queues = ([], [])
    ret_state = 1
    try:
        if daemon:
            log_queue.put(("L", (threading.currentThread().getName(), "Initialising meta-server-info block")))
            msi_block = process_tools.meta_server_info("mother")
            msi_block.add_actual_pid()
            msi_block.set_start_command("/etc/init.d/mother start")
            msi_block.set_stop_command("/etc/init.d/mother force-stop")
            msi_block.set_kill_pids()
            msi_block.save_block()
        else:
            msi_block = None
        log_thread = threading.Thread(name = "log", target=logging_thread, args = [main_queue, log_queue, mysql_tools.db_con(), dhcpd_queue, msi_block])
        run_thread_list.append(log_thread)
        log_thread.start()
        for log_line in log_lines:
            log_queue.put(("L", (my_name, log_line)))
        enable_syslog_config(log_queue)
        # wait for alive-message from logging-thread
        mes_type, mes_arg = main_queue.get()
        log_queue.put(("L", (my_name, "Main-Thread has pid %d" % (my_pid))))
        # log config
        for conf in g_config.get_config_info():
            log_queue.put(("L", (my_name, "Config : %s" % (conf))))
        # re-insert config
        configfile.write_config(dbcon.dc, "mother_server", g_config)

        # read uuid
        my_uuid = uuid_tools.get_uuid()
        log_queue.put(("L", (my_name, "cluster_device_uuid is '%s'" % (my_uuid.get_urn()))))
        glob_net_devices, glob_ndt_dict = get_network_type_indizes_and_net_devices(dbcon.dc)
        #print "Syncing database..."
        devip_dict, devname_dict = ({}, {})
        database_sync(my_name, log_queue)
        #print "done"

        # start the permament subthreads
        # network-server
        nserver = msock.is_net_server(log_hook=log_hook, new_pid_hook=new_pid_hook)
        nserver.set_new_message_format(1)
        nserver.set_timeout(2)

        nc_thread = threading.Thread(name="nodecontrol", target=node_control, args = [main_queue, log_queue, node_queue, config_queue, nserver, snmp_queue, dhcpd_queue, sql_queue, sreq_queue, msi_block])
        run_thread_list.append(nc_thread)
        nc_thread.start()
        cf_thread = threading.Thread(name="config", target=configure_thread, args = [main_queue, log_queue, config_queue, sql_queue, msi_block])
        run_thread_list.append(cf_thread)
        cf_thread.start()
        dh_thread = threading.Thread(name="dhcp", target=dhcpd_thread, args = [main_queue, log_queue, dhcpd_queue, nserver, sql_queue, sreq_queue, msi_block])
        run_thread_list.append(dh_thread)
        dh_thread.start()
        sm_thread = threading.Thread(name="snmp_dispatcher", target=snmp_disp_thread, args = [main_queue, log_queue, snmp_queue, node_queue, nserver, msi_block])
        run_thread_list.append(sm_thread)
        sm_thread.start()
        #th_thread = threading.Thread(name="throttle", target=throttle_thread, args = [main_queue, log_queue, throttle_queue, msi_block])
        #run_thread_list.append(th_thread)
        #th_thread.start()
        sql_thread = threading.Thread(name="sql", target=sql_thread_code, args = [main_queue, log_queue, sql_queue, msi_block])
        run_thread_list.append(sql_thread)
        sql_thread.start()
        del_queues.extend([node_queue, config_queue, dhcpd_queue, snmp_queue, sql_queue])
        update_queues.extend([log_queue, snmp_queue, sql_queue, sreq_queue, node_queue])
        # fill dhcpd-server
        dhcpd_queue.put(("D", server_command.server_command(command="alter_macadr")))
        # rewrite all config files
        for m in devname_dict.keys():
            mach = devname_dict[m]
            if isinstance(mach, machine):
                config_queue.put(("C", ("refresh_all", None, mach.name, 0)))

        n_retry = 5
        act_timeout = 5
        log_queue.put(("L", (my_name, "Setting timeout() for net-server to %d seconds" % (act_timeout))))
        nserver.set_timeout(act_timeout)
        nserver.new_tcp_bind({"r" : sreq_queue,
                              "e" : sreq_queue,
                              "l" : sreq_queue}, (g_config["NODEPORT"], "", n_retry, 5))
        nserver.new_tcp_bind({"r" : sreq_queue,
                              "e" : sreq_queue,
                              "l" : sreq_queue}, (g_config["COMPORT"], "", n_retry, 5))
        nserver.new_udp_bind({"r" : snmp_queue,
                              "e" : snmp_queue,
                              "l" : snmp_queue}, (162, "", n_retry, 5))
        nserver.new_unix_domain_bind({"r" : log_queue,
                                      "e" : log_queue,
                                      "l" : log_queue}, ("/var/lib/mother/syslog", "0660", n_retry, 5), None, 0, 0)
        threading.Thread(name="socket_request", target=socket_server_thread_code, args = [main_queue, log_queue, sreq_queue, dhcpd_queue, sreq_queue, node_queue, nserver, msi_block]).start()
        del_queues.append(sreq_queue)
        # check for new kernels
        sreq_queue.put(("FC", (server_command.server_command(command="check_kernel_dir", option_dict={"insert_all_found" : 1}))))
        log_queue.put(("L", (my_name, "entering main-loop")))
        bind_state = 1
        last_apc_update = None
        while 1:
            try:
                mes_type, mes_arg = main_queue.get_nowait()
            except Queue.Empty:
                pass
            else:
                if mes_type == "I":
                    mes_arg, mes_thread = mes_arg
                    if mes_arg.startswith("set_timeout"):
                        act_timeout = int(mes_arg.split()[1])
                        log_queue.put(("L", (my_name, "Setting timeout() for net-server to %d seconds" % (act_timeout))))
                        nserver.set_timeout(act_timeout)
                    elif mes_arg == "bind_error":
                        break
                    elif mes_arg == "exiting":
                        pass
                    else:
                        bind_state = 0
            for q in update_queues:
                q.put(("I", ("update", my_name)))
            if not last_apc_update or abs(last_apc_update - time.time()) > g_config["APC_REPROGRAMM_TIME"]:
                last_apc_update = time.time()
                for m in devname_dict.keys():
                    mach = devname_dict[m]
                    if isinstance(mach, apc):
                        log_queue.put(("L", (my_name, "Reprogramming APC %s" % (mach.name))))
                        snmp_queue.put(("SM", ("apc_com", 0, mach.name, mach.name, ["update"])))
            nserver.step(1)
    except term_error:
        log_queue.put(("L", (my_name, "proc %d: Got term-signal" % (my_pid))))
    except stop_error:
        log_queue.put(("L", (my_name, "proc %d: Got stop-signal" % (my_pid))))
    except int_error:
        log_queue.put(("L", (my_name, "proc %d: Got int-signal" % (my_pid))))
    for q in del_queues:
        q.put(("I", ("exit", my_name)))
    disable_syslog_config(log_queue)
    # force exit of syslog-thread
    log_queue.put(("L", (my_name, "Sending exit to syslog-thread")))
    msock.single_unix_domain_connection("/var/lib/mother/syslog", "exit")
    num_wait = len(del_queues)
    while num_wait:
        mes_type, mes_arg = main_queue.get()
        if mes_type == "I":
            mes_arg, mes_thread = mes_arg
            if mes_arg == "exiting":
                log_queue.put(("L", (my_name, "Thread %s exited" % (mes_thread))))
                num_wait -= 1
    # at last we finish the logging-thread
    log_queue.put(("I", ("exit", my_name)))
    while 1:
        mes_type, mes_arg = main_queue.get()
        if mes_type == "I":
            mes_arg, mes_thread = mes_arg
            if mes_arg == "exiting":
                logging_tools.my_syslog("Mother: Thread %s exited" % (mes_thread))
                break
    process_tools.delete_pid("mother/mother")
    if msi_block:
        msi_block.remove_meta_block()
    return ret_state

def enable_syslog_config(log_queue):
    my_name = threading.currentThread().getName()
    slcn = "/etc/syslog-ng/syslog-ng.conf"
    if os.path.isfile(slcn):
        log_queue.put(("L", (my_name, "Trying to rewrite syslog-ng.conf for mother ...")))
        try:
            orig_conf = [x.rstrip() for x in file(slcn, "r").readlines()]
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
            log_queue.put(("L", (my_name, "after parsing: %s" % (", ".join(["%s: %d" % (x, opt_dict[x]) for x in opt_list])))))
            if not opt_dict["mother"]:
                mother_lines = []
                if not opt_dict["dhcp_filter"]:
                    mother_lines.extend(['',
                                         'filter f_dhcp       { match("DHCP") ; };'])
                if opt_dict["dhcp"]:
                    log_queue.put(("L", (my_name, "dhcp-source found, so it seems that the DHCPD is running chrooted() ...")))
                    mother_lines.extend(['',
                                         'destination dhcpmother { unix-dgram("/var/lib/mother/syslog") ;};',
                                         '',
                                         'log { source(dhcp); source(src); filter(f_dhcp)    ; destination(dhcpmother); };'])
                else:
                    log_queue.put(("L", (my_name, "dhcp-source not found, so it seems that the DHCPD is NOT running chrooted() ...")))
                    mother_lines.extend(['',
                                         'destination dhcpmother { unix-dgram("/var/lib/mother/syslog") ;};',
                                         '',
                                         'log {               source(src); filter(f_dhcp)    ; destination(dhcpmother);};'])
                for ml in mother_lines:
                    log_queue.put(("L", (my_name, "adding line to %s : %s" % (slcn, ml))))
                file(slcn, "w").write("\n".join(orig_conf + mother_lines + [""]))
            else:
                log_queue.put(("L", (my_name, "%s seems to be OK, leaving unchanged..." % (slcn))))
            log_queue.put(("L", (my_name, "...done")))
        except:
            log_queue.put(("L", (my_name, "Something went wrong while trying to modify '%s', help..." % (slcn))))
    else:
        log_queue.put(("L", (my_name, "config file '%s' not present" % (slcn))))
    
def disable_syslog_config(log_queue):
    my_name = threading.currentThread().getName()
    log_queue.put(("L", (my_name, "Trying to rewrite syslog-ng.conf for normal operation ...")))
    slcn = "/etc/syslog-ng/syslog-ng.conf"
    try:
        orig_conf = [x.rstrip() for x in file(slcn, "r").readlines()]
        new_conf = []
        del_lines = []
        for line in orig_conf:
            if re.match("^.*mother.*$", line):
                del_lines.append(line)
            else:
                new_conf.append(line)
        if del_lines:
            log_queue.put(("L", (my_name, "Found %s:" % (logging_tools.get_plural("mother-related line", len(del_lines))))))
            for dl in del_lines:
                log_queue.put(("L", (my_name, "  removing : %s" % (dl))))
            # remove double empty-lines
            new_conf_2, last_line = ([], None)
            for line in new_conf:
                if line == last_line and last_line == "":
                    pass
                else:
                    new_conf_2.append(line)
                last_line = line
            file(slcn, "w").write("\n".join(new_conf_2))
        else:
            log_queue.put(("L", (my_name, "Found no mother-related lines, leaving %s untouched" % (slcn))))
        log_queue.put(("L", (my_name, "...done")))
    except:
        log_queue.put(("L", (my_name, "Something goes wrong while trying to modify '%s', help..." % (slcn))))

def main():
    global g_config, long_host_name, short_host_name, mother_server_idx, log_source_idx, log_sources, log_status

    try:
        opts, args = getopt.getopt(sys.argv[1:], "dvCu:g:fkh", ["version", "help"])
    except:
        exc_info = sys.exc_info()
        print "Error parsing commandline %s: %s (%s)" % (" ".join(sys.argv[1:]), str(exc_info[0]).strip(), str(exc_info[1]).strip())
        sys.exit(1)

    daemon, verbose, check, kill_running = (1, 0, 0, 1)
    user, group, fixit = ("root", "root", 0)
    pname = os.path.basename(sys.argv[0])
    for opt, arg in opts:
        if opt in ["-h", "--help"]:
            print "Usage: %s [OPTIONS]" % (pname)
            print " where options is one or more of"
            print "  -h, --help          this help"
            print "  --version           version info"
            print "  -d                  no daemonizing"
            print "  -f                  fix directory permissions"
            print "  -C                  check if i am a mother-server"
            print "  -u [USER]           set user to USER"
            print "  -g [GROUP]          set group to GROUP"
            print "  -k                  kill running instances of mother"
            sys.exit(1)
        if opt == "--version":
            print "mother, Version %s" % (VERSIONSTRING)
            sys.exit(0)
        if opt == "-d":
            daemon = 0
        if opt == "-v":
            verbose = 1
        if opt == "-C":
            check = 1
        if opt == "-f":
            fixit = 1
        if opt == "-u":
            user = arg
        if opt == "-g":
            group = arg
        if opt == "-k":
            kill_running = 0
    try:
        db_c = mysql_tools.db_con()
    except MySQLdb.OperationalError:
        sys.stderr.write(" Cannot connect to SQL-Server ")
        sys.exit(1)
    long_host_name = socket.getfqdn(socket.gethostname())
    short_host_name = long_host_name.split(".")[0]
    num_servers, mother_server_idx = process_tools.is_server(db_c.dc, "mother_server")
    if num_servers == 0:
        sys.stderr.write(" Host %s is no mother-server " % (long_host_name))
        sys.exit(5)
    if check:
        sys.exit(0)
    if kill_running:
        kill_dict = process_tools.build_kill_dict(pname)
        for k, v in kill_dict.iteritems():
            log_str = "Trying to kill pid %d (%s) with signal 9 ..." % (k, v)
            try:
                os.kill(k, 9)
            except:
                log_str = "%s error (%s)" % (log_str, get_error_str())
            else:
                log_str = "%s ok" % (log_str)
            logging_tools.my_syslog(log_str)
    g_config = configfile.read_global_config(db_c.dc, "mother_server", {"LOG_DIR"                     : configfile.str_c_var("/var/log/cluster/mother"),
                                                                        "TFTP_DIR"                    : configfile.str_c_var("/tftpboot"),
                                                                        "ETHERBOOTDIR_OFFSET"         : configfile.str_c_var("etherboot"),
                                                                        "CONFIGDIR_OFFSET"            : configfile.str_c_var("config"),
                                                                        "NODEPORT"                    : configfile.int_c_var(8000),
                                                                        "COMPORT"                     : configfile.int_c_var(8001),
                                                                        "HWI_MAX_RETRIES"             : configfile.int_c_var(10),
                                                                        "HWI_DELAY_TIME"              : configfile.int_c_var(30),
                                                                        "SNMP_MAIN_TIMEOUT"           : configfile.int_c_var(10),
                                                                        "VERBOSE"                     : configfile.int_c_var(verbose),
                                                                        "IGNORE_KERNEL_BUILD_MACHINE" : configfile.int_c_var(0),
                                                                        "SET_DEFAULT_BUILD_MACHINE"   : configfile.int_c_var(0),
                                                                        "PREFER_KERNEL_NAME"          : configfile.int_c_var(1),
                                                                        "SIMULTANEOUS_REBOOTS"        : configfile.int_c_var(8),
                                                                        "REBOOT_DELAY"                : configfile.int_c_var(15),
                                                                        "NODE_BOOT_DELAY"             : configfile.int_c_var(0),
                                                                        "MODIFY_NFS_CONFIG"           : configfile.int_c_var(1),
                                                                        "FANCY_PXE_INFO"              : configfile.int_c_var(0),
                                                                        "KEEP_LOGS_TIMEOUT"           : configfile.int_c_var(7),
                                                                        "APC_REPROGRAMM_TIME"         : configfile.int_c_var(3600, info="looptime in seconds to reprogramm APCs"),
                                                                        "DEVICE_MONITOR_TIME"         : configfile.int_c_var(240, info="time in seconds to check for downnodes"),
                                                                        "DEVICE_REBOOT_TIME"          : configfile.int_c_var(600, info="after this time a device is rebooted")})
    g_config.add_config_dict({"ETHERBOOT_DIR" : configfile.str_c_var("%s/%s" % (g_config["TFTP_DIR"], g_config["ETHERBOOTDIR_OFFSET"])),
                              "CONFIG_DIR"    : configfile.str_c_var("%s/%s" % (g_config["TFTP_DIR"], g_config["CONFIGDIR_OFFSET"]))})
    if fixit:
        process_tools.fix_directories(user, group, [g_config["LOG_DIR"], "/var/lib/mother", "/var/run/mother", g_config["ETHERBOOT_DIR"]])
    ret_state = 256
    if num_servers > 1:
        print "Database error for host %s (mother_server): too many entries found (%d)" % (long_host_name, num_servers)
    else:
        log_source_idx = process_tools.create_log_source_entry(db_c.dc, mother_server_idx, "mother", "Mother Server")
        if not log_source_idx:
            print "Too many log_sources with my id present, exiting..."
        else:
            process_tools.create_log_source_entry(db_c.dc, 0, "node", "Cluster node", "String written by one of the nodes")
            log_sources = process_tools.get_all_log_sources(db_c.dc)
            log_status  = process_tools.get_all_log_status(db_c.dc)
            db_c = None
            process_tools.renice()
            if daemon:
                # become daemon and wait 2 seconds
                process_tools.become_daemon(wait = 2)
                process_tools.set_handles({"out" : (1, "mother"),
                                           "err" : (0, "/var/lib/logging-server/py_err")})
            else:
                print "Debugging mother"

            ret_state = server_code(daemon)
    if db_c:
        del db_c
    sys.exit(ret_state)

if __name__ == "__main__":
    main()
