#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file belongs to the rrd-server package
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
""" rrd-server for collecting history-data """

import sys
import MySQLdb
import re
import threading
import time
import os
import getopt
import socket
import rrdtool
import configfile
import process_tools
import logging_tools
import server_command
import net_tools
import mail_tools
import mysql_tools
import pprint
import threading_tools
import uuid_tools
import colorsys
try:
    import bz2
except ImportError:
    bz2 = None
# SNMP imports
import pyasn1.codec.ber
from pysnmp.entity.rfc3413.oneliner import cmdgen

# reserved log-file names
RLFN = ["c_events"]

SQL_ACCESS = "cluster_full_access"

def get_float_str(val):
    try:
        r_str = "%.2f" % (float(val))
    except TypeError:
        r_str = "%s [%s]" % (str(val), sys.exc_info()[1])
    return r_str

def get_time_str(val):
    try:
        if type(val) == type(2):
            r_str = "%s" % (time.ctime(val))
        else:
            r_str = "%s" % (time.ctime(float(val)))
    except (TypeError, ValueError):
        r_str = "%s [%s]" % (str(val), sys.exc_info()[1])
    return r_str

# --------- connection objects ------------------------------------
class node_con_obj(net_tools.buffer_object):
    # connects to a foreign node
    def __init__(self, dev_struct, dst_host, (send_str, mach_struct, target_queue)):
        self.__dev_struct = dev_struct
        self.__dst_host = dst_host
        self.__send_str = send_str
        self.__mach_struct = mach_struct
        self.__target_queue = target_queue
        net_tools.buffer_object.__init__(self)
    def __del__(self):
        pass
    def setup_done(self):
        self.add_to_out_buffer(net_tools.add_proto_1_header(self.__send_str, True))
    def out_buffer_sent(self, send_len):
        if send_len == len(self.out_buffer):
            self.out_buffer = ""
            self.socket.send_done()
        else:
            self.out_buffer = self.out_buffer[send_len:]
    def add_to_in_buffer(self, what):
        self.in_buffer += what
        p1_ok, p1_data = net_tools.check_for_proto_1_header(self.in_buffer)
        if p1_ok:
            self.__target_queue.put(("node_ok_result", (self.__dev_struct, self.__send_str, p1_data)))
            self.delete()
    def report_problem(self, flag, what):
        self.__target_queue.put(("node_error_result", (self.__dev_struct, self.__send_str, flag, what)))
        self.delete()

class new_tcp_con(net_tools.buffer_object):
    # connection object for rrd-server
    def __init__(self, con_type, con_class, data, src, recv_queue, log_queue):
        self.__con_type = con_type
        self.__con_class = con_class
        #print "Init %s (%s) from %s" % (con_type, con_class, str(src))
        self.__src_host, self.__src_port = src
        self.__recv_queue = recv_queue
        self.__log_queue = log_queue
        net_tools.buffer_object.__init__(self)
        self.__init_time = time.time()
        self.__in_buffer = ""
        if data:
            self.__decoded = data
            if self.__con_type == "com":
                # should never occur
                self.__recv_queue.put(("com_con", self))
            else:
                self.__recv_queue.put(("node_con", self))
    def __del__(self):
        pass
    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        self.__log_queue.put(("log", (threading.currentThread().getName(), what, level)))
    def get_con_class(self):
        return self.__con_class
    def get_src_host(self):
        return self.__src_host
    def get_src_port(self):
        return self.__src_port
    def add_to_in_buffer(self, what):
        self.__in_buffer += what
        p1_ok, what = net_tools.check_for_proto_1_header(self.__in_buffer)
        if p1_ok:
            self.__decoded = what
            if self.__con_type == "com":
                self.__recv_queue.put(("com_con", self))
            else:
                self.__recv_queue.put(("node_con", self))
    def add_to_out_buffer(self, what, new_in_str=""):
        self.lock()
        # to give some meaningful log
        if new_in_str:
            self.__decoded = new_in_str
        if self.socket:
            self.out_buffer = net_tools.add_proto_1_header(what)
            self.socket.ready_to_send()
        else:
            self.log("timeout, other side has closed connection")
        self.unlock()
    def out_buffer_sent(self, d_len):
        if d_len == len(self.out_buffer):
            self.__recv_queue = None
            if self.__con_type == "com":
                self.log("command %s from %s (port %d) took %s" % (self.__decoded.replace("\n", "\\n"),
                                                                   self.__src_host,
                                                                   self.__src_port,
                                                                   logging_tools.get_diff_time_str(abs(time.time() - self.__init_time))))
            self.close()
        else:
            self.out_buffer = self.out_buffer[d_len:]
    def get_decoded_in_str(self):
        return self.__decoded
    def report_problem(self, flag, what):
        self.close()
        
class new_tcp_con_forbid(net_tools.buffer_object):
    # connection object for rrd-server when server is shutting down (return error)
    def __init__(self, con_type, con_class, src, log_queue):
        self.__con_type = con_type
        self.__con_class = con_class
        #print "Init %s (%s) from %s" % (con_type, con_class, str(src))
        self.__src_host, self.__src_port = src
        self.__log_queue = log_queue
        net_tools.buffer_object.__init__(self)
        self.__init_time = time.time()
        self.__in_buffer = ""
    def __del__(self):
        pass
    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        self.__log_queue.put(("log", (threading.currentThread().getName(), what, level)))
    def add_to_in_buffer(self, what):
        self.__in_buffer += what
        p1_ok, what = net_tools.check_for_proto_1_header(self.__in_buffer)
        if p1_ok:
            self.__decoded = what
            try:
                server_com = server_command.server_command(self.__decoded)
            except:
                self.add_to_out_buffer("error shutting down")
            else:
                self.add_to_out_buffer(server_command.server_reply(state=server_command.SRV_REPLY_STATE_ERROR, result="shutting down"), "error shutting down")
    def add_to_out_buffer(self, what, new_in_str=""):
        self.lock()
        # to give some meaningful log
        if new_in_str:
            self.__decoded = new_in_str
        if self.socket:
            self.out_buffer = net_tools.add_proto_1_header(what)
            self.socket.ready_to_send()
        else:
            self.log("timeout, other side has closed connection")
        self.unlock()
    def out_buffer_sent(self, d_len):
        if d_len == len(self.out_buffer):
            self.__recv_queue = None
            if self.__con_type == "com":
                self.log("command %s from %s (port %d) took %s" % (self.__decoded.replace("\n", "\\n"),
                                                                   self.__src_host,
                                                                   self.__src_port,
                                                                   logging_tools.get_diff_time_str(abs(time.time() - self.__init_time))))
            self.close()
        else:
            self.out_buffer = self.out_buffer[d_len:]
            #self.socket.ready_to_send()
    def report_problem(self, flag, what):
        self.close()
# --------- connection objects ------------------------------------

class all_devices(object):
    def __init__(self, log_queue, glob_config, loc_config, db_con):
        self.__lut = {}
        self.__lock = threading.Lock()
        self.__log_queue = log_queue
        self.__glob_config, self.__loc_config = (glob_config, loc_config)
        self.__db_con = db_con
        self.__device_names = []
        # device_group dict
        self.__device_group_dict = {}
        self.__device_group_names = []
        self.log("all_devices struct init")
    def get_glob_config(self):
        return self.__glob_config
    def get_db_con(self):
        return self.__db_con
    def get_loc_config(self):
        return self.__loc_config
    def get_log_queue(self):
        return self.__log_queue
    def is_an_ip(self, key):
        if key.count(".") == 3 and len([True for x in key.split(".") if x.isdigit()]):
            return True
        else:
            return False
    def _get_ip_lists(self, dc, devices):
        srv_idxs = [self.__loc_config["RRD_SERVER_IDX"]]
        # get real server_idx
        dc.execute("SELECT d.device_idx FROM device d WHERE d.name='%s'" % (self.__loc_config["SERVER_SHORT_NAME"]))
        if dc.rowcount:
            my_srv_idx = dc.fetchone()["device_idx"]
            if my_srv_idx != self.__loc_config["RRD_SERVER_IDX"]:
                self.log("server_idx from db (%d) differs from short_host_name server_idx (%d)" % (self.__loc_config["RRD_SERVER_IDX"], my_srv_idx),
                         logging_tools.LOG_LEVEL_WARN)
                srv_idxs.append(my_srv_idx)
        else:
            self.log("short_host_name '%s' not in database, strange ..." % (self.__loc_config["SERVER_SHORT_NAME"]),
                     logging_tools.LOG_LEVEL_ERROR)
        dc.execute("SELECT i.ip, n.netdevice_idx FROM netdevice n, netip i, network nw WHERE (%s) AND i.netdevice=n.netdevice_idx AND i.network=nw.network_idx" % (" OR ".join(["n.device=%d" % (x) for x in srv_idxs])))
        all_netdevs = {}
        for db_rec in dc.fetchall():
            all_netdevs.setdefault(db_rec["netdevice_idx"], []).append(db_rec["ip"])
        sql_str = "SELECT DISTINCT d.name, i.ip, i.alias, i.alias_excl, nw.network_idx, n.netdevice_idx, n.devname, nt.identifier, nw.name AS " + \
                  "domain_name, nw.postfix, nw.short_names, h.value FROM device d, netip i, netdevice n, network nw, network_type nt, hopcount h WHERE " + \
                  "nt.network_type_idx=nw.network_type AND i.network=nw.network_idx AND n.device=d.device_idx AND i.netdevice=n.netdevice_idx AND n.netdevice_idx=h.s_netdevice AND " + \
                  "(%s) AND (%s) ORDER BY h.value, d.name" % (" OR ".join(["h.d_netdevice=%d" % (x) for x in all_netdevs]),
                                                              " OR ".join(["d.name='%s'" % (x) for x in devices]))
        dc.execute(sql_str)
        return dc.fetchall()
    def db_sync(self, dc, new_list=[]):
        self._lock(self.__loc_config["VERBOSE"] > 0 or not self.__loc_config["DAEMON"])
        # fetch snmp-classes
        dc.execute("SELECT * FROM snmp_class")
        snmp_classes = dict([(x["snmp_class_idx"], x) for x in dc.fetchall()])
        if new_list:
            new_list.sort()
            ip_re = re.compile("^\d+\.\d+\.\d+\.\d+$")
            self.log("Syncing from database for name/ip-list %s" % (logging_tools.compress_list(new_list)))
            ip_list   = [x for x in new_list if ip_re.match(x)]
            name_list = [x for x in new_list if not ip_re.match(x)]
            if ip_list:
                sql_str = "SELECT DISTINCT d.name FROM device d INNER JOIN device_type dt LEFT JOIN netdevice n ON n.device=d.device_idx LEFT JOIN " + \
                          "netip i ON i.netdevice=n.netdevice_idx LEFT JOIN network nw ON i.network=nw.network_idx LEFT JOIN network_type nt ON nw.network_type=nt.network_type_idx WHERE " + \
                          "d.device_type=dt.device_type_idx AND (dt.identifier='H' OR dt.identifier='NB' OR dt.identifier='AM' OR dt.identifier='MD') AND %s" % (" OR ".join(["i.ip='%s'" % (x) for x in ip_list]))
                dc.execute(sql_str)
                add_names = [x["name"] for x in dc.fetchall()]
                if add_names:
                    self.log("Found %s (%s) for %s (%s)" % (logging_tools.get_plural("name", len(add_names)),
                                                            logging_tools.compress_list(add_names),
                                                            logging_tools.get_plural("ip", len(ip_list)),
                                                            ", ".join(ip_list)))
                    name_list.extend(add_names)
                else:
                    self.log("Found no names for %s (%s) in database" % (logging_tools.get_plural("ip", len(ip_list)),
                                                                         ", ".join(ip_list)))
            if not name_list:
                sql_add_str = None
            else:
                sql_add_str = " AND (%s)" % (" OR ".join(["d.name='%s'" % (x) for x in name_list]))
        else:
            sql_add_str = ""
            self.log("Syncing from database for all devices ")
        discovered_devices = {}
        if sql_add_str is not None:
            # first task: select all devices that matches the given ip/name-combination
            s_time = time.time()
            sql_str = "SELECT d.name, d.snmp_class, d.device_idx, d.device_group, d.save_rrd_vectors, dg.cluster_device_group, dt.identifier, dt.description, i.ip, nt.identifier AS ntidentifier FROM " + \
                      "device d INNER JOIN device_type dt INNER JOIN device_group dg LEFT JOIN netdevice n ON n.device=d.device_idx LEFT JOIN netip i ON i.netdevice=n.netdevice_idx LEFT JOIN " + \
                      "network nw ON i.network=nw.network_idx LEFT JOIN network_type nt ON nw.network_type=nt.network_type_idx WHERE d.device_group=dg.device_group_idx AND " + \
                      "d.device_type=dt.device_type_idx AND (dt.identifier='H' OR dt.identifier='NB' OR dt.identifier='AM' OR dt.identifier='MD')%s" % (sql_add_str)
            dc.execute(sql_str)
            e_time = time.time()
            self.log(" - SQL for device discovery took %s" % (logging_tools.get_diff_time_str(e_time - s_time)))
            for db_rec in dc.fetchall():
                if not discovered_devices.has_key(db_rec["name"]):
                    discovered_devices[db_rec["name"]] = dict([(k, db_rec.get(k, {})) for k in ["snmp_class", "device_idx", "device_group", "cluster_device_group", "identifier", "description", "ips", "save_rrd_vectors"]])
                if db_rec["ip"]:
                    discovered_devices[db_rec["name"]]["ips"][db_rec["ip"]] = {"identifier" : db_rec["ntidentifier"], 
                                                                               "value"      : None}
        # check for devices with rrd-client or rrd-server attribute
        if discovered_devices:
            sql_str = "SELECT DISTINCT d.name FROM device d INNER JOIN device_group dg INNER JOIN new_config c INNER JOIN device_config dc INNER JOIN device_type dt LEFT JOIN " + \
                      "device d2 ON d2.device_idx=dg.device WHERE d.device_group=dg.device_group_idx AND (dc.device=d2.device_idx OR dc.device=d.device_idx) AND dc.new_config=c.new_config_idx AND " + \
                      "dt.device_type_idx=d.device_type AND (c.name='rrd_client' OR c.name='rrd_server') AND (%s)" % (" OR ".join(["d.name='%s'" % (x) for x in discovered_devices.keys()]))
            dc.execute(sql_str)
            rrd_client_devs = [dev["name"] for dev in dc.fetchall()]
        else:
            rrd_client_devs = []
        no_client_devices = []
        for dev_name, dev_stuff in discovered_devices.iteritems():
            if dev_name in rrd_client_devs or dev_stuff["identifier"] in ["MD", "AM", "NB"]:
                pass
            else:
                no_client_devices.append(dev_name)
        if no_client_devices:
            self.log("removing %s (no rrd_client or wrong device_type): %s" % (logging_tools.get_plural("device", len(no_client_devices)),
                                                                               logging_tools.compress_list(no_client_devices)),
                     logging_tools.LOG_LEVEL_WARN)
            for ncd in no_client_devices:
                del discovered_devices[ncd]
        del_keys = []
        if discovered_devices:
            con_lists = self._get_ip_lists(dc, discovered_devices.keys())
            #pprint.pprint(con_lists)
            for connection in con_lists:
                #print "dx:", connection
                for ck in ["value"]:
                    #print "d0:", discovered_devices.keys()
                    #print "d1:", discovered_devices[connection["name"]].keys()
                    #print "d2:", discovered_devices[connection["name"]]["ips"].keys()
                    #print "d3:", connection["ip"]
                    if discovered_devices[connection["name"]]["ips"].has_key(connection["ip"]):
                        #print "d4:", discovered_devices[connection["name"]]["ips"][connection["ip"]].keys()
                        if connection.has_key(ck):
                            discovered_devices[connection["name"]]["ips"][connection["ip"]][ck] = connection[ck]
                    else:
                        del_keys.append(connection["name"])
        if del_keys:
            self.log("%s not reachable (incomplete routing table?) : %s" % (logging_tools.get_plural("device", len(del_keys)),
                                                                            logging_tools.compress_list(del_keys)))
            for del_key in del_keys:
                del discovered_devices[del_key]
        #pprint.pprint(discovered_devices)
        if discovered_devices:
            # actutal rrd_classes
            act_rrd_classes = read_rrd_class_tree(dc)
            # remove unconnected ips/devices
            del_dev_names = []
            for dev_name, dev_stuff in discovered_devices.iteritems():
                del_ips = [x for x in dev_stuff["ips"].keys() if dev_stuff["ips"][x]["value"] == None]
                for del_ip in del_ips:
                    del dev_stuff["ips"][del_ip]
                if not dev_stuff["ips"] and dev_stuff["identifier"] not in ["MD"]:
                    del_dev_names.append(dev_name)
            if del_dev_names:
                self.log("Removing %s (not reachable): %s" % (logging_tools.get_plural("device", len(del_dev_names)),
                                                              logging_tools.compress_list(del_dev_names)))
                for del_dev_name in del_dev_names:
                    del discovered_devices[del_dev_name]
            sql_str = "SELECT d.name, rs.rrd_set_idx, rd.* FROM rrd_set rs INNER JOIN device d LEFT JOIN rrd_data rd ON rd.rrd_set=rs.rrd_set_idx WHERE " + \
                      "rs.device=d.device_idx AND (%s) " % (" OR ".join(["d.name='%s'" % (x) for x in discovered_devices.keys()])) + \
                      "ORDER BY d.name, rs.rrd_set_idx, rd.rrd_data_idx"
            s_time = time.time()
            dc.execute(sql_str)
            e_time = time.time()
            self.log(" - SQL for rrd_data discovery took %s" % (logging_tools.get_diff_time_str(e_time - s_time)))
            s_time = time.time()
            rrd_data_dict, rrd_data_idxs = ({}, [])
            for db_rec in dc.fetchall():
                rrd_data_dict.setdefault(db_rec["name"], {})
                if db_rec["rrd_set_idx"]:
                    rrd_data_dict[db_rec["name"]].setdefault(db_rec["rrd_set_idx"], [])
                    if db_rec["rrd_data_idx"] and db_rec["rrd_data_idx"] not in rrd_data_idxs:
                        rrd_data_idxs.append(db_rec["rrd_data_idx"])
                        rrd_data_dict[db_rec["name"]][db_rec["rrd_set_idx"]].append(dict([(k, db_rec[k]) for k in ["rrd_data_idx", "descr", "descr1", "descr2", "descr3", "descr4", "unit", "info", "from_snmp", "base", "factor", "var_type", "date"]] + [("events", {})]))
            e_time = time.time()
            self.log(" - data reordering took %s" % (logging_tools.get_diff_time_str(e_time - s_time)))
            for new_name in sorted(discovered_devices.keys()):
                new_mach = discovered_devices[new_name]
                if not self.has_key(new_name):
                    log_str = "Discovered new device '%s' (type %s [%s], %s)" % (new_name,
                                                                                 new_mach["description"],
                                                                                 new_mach["identifier"],
                                                                                 new_mach["save_rrd_vectors"] and "save vectors" or "do not save vectors")
                    if not new_mach["snmp_class"]:
                        # correct snmp_class
                        new_mach["snmp_class"] = snmp_classes.keys()[0]
                        log_str += ", snmp_class not set, using %d" % (new_mach["snmp_class"])
                    self.log(log_str)
                    nt = new_mach["identifier"]
                    if new_mach["ips"]:
                        pure_ip_list = new_mach["ips"].keys()
                        self.log("Add new device '%s' with %s (%s)" % (new_name,
                                                                       logging_tools.get_plural("ip address", len(pure_ip_list))
                                                                       , ", ".join(sorted(pure_ip_list))))
                    else:
                        self.log("Add new META-device '%s'" % (new_name))
                    act_snmp_class = snmp_classes[new_mach["snmp_class"]]
                    self.log("  New device has snmp_class %s (%s, %d secs update frequence)" % (act_snmp_class["name"],
                                                                                                act_snmp_class["descr"],
                                                                                                act_snmp_class["update_freq"]))
                    if nt == "NB":
                        new_device = netbotz(new_name, pure_ip_list, new_mach["device_idx"], self, "NB")
                    elif nt == "H":
                        new_device = machine(new_name, pure_ip_list, new_mach["device_idx"], self, "H")
                    elif nt == "AM":
                        new_device = machine(new_name, pure_ip_list, new_mach["device_idx"], self, "AM")
                    elif nt == "MD":
                        new_device = meta_device(new_name, new_mach["cluster_device_group"], new_mach["device_idx"], self, "MD")
                    else:
                        self.log("Cannot interpret identifier %s for device %s" % (nt, new_name))
                        new_device = None
                    if new_device:
                        if new_mach.has_key("device_group"):
                            new_device.set_device_group(new_mach["device_group"])
                        new_device.set_snmp_class(act_snmp_class)
                        new_device.save_vectors = new_mach["save_rrd_vectors"]
                        self[new_name] = new_device
                        # init rrd-databases
                        #print "* init", new_name
                        if new_device.create_rrd_database(dc, act_rrd_classes):
                            #print "* recr", new_name
                            # rrd created, rewrite rrd_data_dict
                            if new_device.get_rrd_set_index():
                                rrd_data_dict[new_name] = {new_device.get_rrd_set_index() : []}
                        #print "* load", new_name
                        new_device.load_rrd_info(dc, rrd_data_dict.get(new_name, {}))
                        #print "* done", new_name
                        if isinstance(new_device, meta_device):
                            self.__device_group_names.append(new_name)
                            self.__device_group_dict[new_name] = new_device
                            self.__device_group_dict[new_device.get_device_group()] = new_device
                        new_device.log("Device %s added" % (new_name))
                        new_device.release_change_lock()
                else:
                    # check for change of ip-addresses
                    act_dev = self[new_name]
                    new_ips, old_ips = (sorted(new_mach["ips"].keys()),
                                        sorted(act_dev.get_ip_list()))
                    if new_ips != old_ips:
                        act_dev.log("Changing list of IP-Adresses from %s (old) to %s (new)" % (", ".join(old_ips),
                                                                                                ", ".join(new_ips)))
                        act_dev.acquire_change_lock()
                        act_dev.set_ip_list(new_ips)
                        act_dev.release_change_lock()
            self._reload_cluster_events(dc)
        else:
            self.log("No device(s) with name/ip %s found" % (logging_tools.compress_list(new_list)))
        self._release(self.__loc_config["VERBOSE"] > 0 or not self.__loc_config["DAEMON"])
    def _reload_cluster_events(self, dc):
        dev_dict = dict([(self[dev_name].dev_idx, dev_name) for dev_name in self.keys(True)])
        sql_str = "SELECT c.*, r.descr FROM ccl_event c, rrd_data r WHERE c.rrd_data=r.rrd_data_idx AND (%s)" % (" OR ".join(["c.device=%d" % (x) for x in dev_dict.keys()]))
        dc.execute(sql_str)
        event_dict = {}
        for db_rec in dc.fetchall():
            event_dict.setdefault(db_rec["device"], {}).setdefault(db_rec["descr"], {})[db_rec["ccl_event_idx"]] = db_rec
        for dev_idx, event_stuff in event_dict.iteritems():
            self[dev_dict[db_rec["device"]]].set_cluster_events(event_stuff, dc)
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
    def keys(self, only_names=False):
        if only_names:
            return self.__device_names
        else:
            return self.__lut.keys()
    def has_key(self, key):
        return self.__lut.has_key(key)
    def __setitem__(self, key, val):
        if not self.is_an_ip(key):
            self.__device_names.append(key)
        self.__lut[key] = val
    def __getitem__(self, key):
        return self.__lut[key]
    def __delitem__(self, key):
        if key in self.__device_names:
            self.__device_names.remove(key)
        del self.__lut[key]
    def iteritems(self):
        return od_iteritems_iterator(self)
    # device group functions
    def get_device_group_keys(self, only_names=False):
        if only_names:
            return self.__device_group_names
        else:
            return self.__device_group_dict.keys()
    def has_device_group_key(self, key):
        return self.__device_group_dict.has_key(key)
    def get_device_group(self, key):
        return self.__device_group_dict[key]

class trace_var(object):
    def __init__(self, key, stuff, dc, log_queue, mach_struct, full_info):
        self.mach_struct = mach_struct
        self.mach_name = self.mach_struct.name
        self.__glob_config = self.mach_struct.get_glob_config()
        self.__loc_config = self.mach_struct.get_loc_config()
        self.key = key
        self.info = full_info
        self.idx = stuff["ccl_event_idx"]
        self.refresh(stuff)
        self.clear_cache()
        self.__log_pfix = "[%s] " % (self.mach_name)
        self.__tlf_name = "c_events"
        self.__log_queue = log_queue
        self.src_idx = 0
        self.log("  Added ccl_event for key %s, %s" % (key, self.get_inf_str()))
        self.get_event_info(dc)
        self.init_rrd()
    def __del__(self):
        pass
    def close(self):
        self.log("closing event")
    def init_rrd(self):
        self.__rrd_name = None
        if not os.path.exists(self.__glob_config["TRACE_DIR"]):
            os.makedirs(self.__glob_config["TRACE_DIR"])
        self.__rrd_name = "%s/%s_%s_%d.rrd" % (self.__glob_config["TRACE_DIR"], self.mach_name, self.key, self.idx)
        self.log("creating rrd-file %s for machine %s (key %s)" % (self.__rrd_name, self.mach_name, self.key))
        init_a = [self.__rrd_name,
                  "-s 30",
                  "DS:v0:GAUGE:120:U:U",
                  "RRA:MIN:0.5:1:256",
                  "RRA:MAX:0.5:1:256",
                  "RRA:AVERAGE:0.5:1:256"]
        c_ret = rrdtool.create(*init_a)
        self.log("rrd_create() with %s returned '%s'" % (logging_tools.get_plural("tuple", len(init_a)), str(c_ret)))
    def refresh(self, in_dict):
        self.hysteresis = in_dict["hysteresis"]
        self.threshold = in_dict["threshold"]
        self.threshold_class = in_dict["threshold_class"]
        self.disabled = in_dict["disabled"]
    def create_rrd_graph(self):
        self.rrd_graph_name = None
        if self.__rrd_name:
            self.rrd_graph_name = "%s/%s_%s_%d.png" % (self.__glob_config["TRACE_DIR"], self.mach_name, self.key, self.idx)
            graph_a = [self.rrd_graph_name, "-A", "-s -1800"]
            graph_a.append("--title='%s'" % ("Trace of %s on %s" % (self.key, self.mach_name)))
            graph_a.extend(["-w %d" % (self.__glob_config["TRACE_VAR_WIDTH"]),
                            "-h %d" % (self.__glob_config["TRACE_VAR_HEIGHT"]),
                            "DEF:v0=%s:v0:MAX" % (self.__rrd_name),
                            "DEF:v1=%s:v0:MIN" % (self.__rrd_name),
                            "CDEF:vmin=v0,UN,0,*,%f,+" % (self.threshold - self.hysteresis / 2.),
                            "CDEF:vmean=v0,UN,0,*,%f,+" % (self.threshold),
                            "CDEF:vmax=v0,UN,0,*,%f,+" % (self.hysteresis),
                            "AREA:vmin#ffffff",
                            "STACK:vmax#cccccc",
                            "LINE2:vmean#880088",
                            "LINE2:v0#ff0000:'Maximum'",
                            "LINE2:v1#00ff00:'Minimum'"])
            start_time = time.time()
            try:
                c_ret = rrdtool.graph(*graph_a)
            except:
                self.log("rrd_graph() with %s terminated with an error: %s (%s)" % (logging_tools.get_plural("tuple", len(graph_a)),
                                                                                    str(sys.exc_info()[0]),
                                                                                    str(sys.exc_info()[1])))
                self.log("tuples: %s " % (" ".join(graph_a)))
                self.rrd_graph_name = None
            else:
                end_time = time.time()
                if type(c_ret) == type(()):
                    c_ret = " x ".join([str(x) for x in list(c_ret)])
                self.log("rrd_graph() with %s returned %s (took %.2f seconds)" % (logging_tools.get_plural("tuple", len(graph_a)), c_ret, end_time - start_time))
    def log(self, log_str, log_lev=logging_tools.LOG_LEVEL_OK):
        self.mach_struct.log("[CE] %s" % (log_str), log_lev)
        #self.__log_queue.put(log_message(log_str, self.mach_name))
        #self.__log_queue.put(log_message(self.__log_pfix + log_str, self.__tlf_name))
    def clear_cache(self):
        # clears cache of logged values and trigger_flag
        self.last_triggered = "-"
        self.__cache = []
        self.__max_cache_size = self.__glob_config["TRACE_CACHE_SIZE"]
    def get_class_dict(self):
        return {1  : "ascending",
                0  : "crossing",
                -1 : "descending"}
    def get_inf_str(self):
        return "idx %d, threshold %.2f, hysteresis %.2f, %s limit" % (self.idx, self.threshold, self.hysteresis, self.get_class_dict()[self.threshold_class])
    def get_event_info(self, dc):
        # return classlist, device_location_list, mail_list and device_dict
        # classlist
        m_dict = {"devices"  : {},
                  "servers"  : {},
                  "event"    : None,
                  "disabled" : 0}
        dc.execute("SELECT dc2.* FROM ccl_event c INNER JOIN device_class dc LEFT JOIN device_class dc2 ON dc2.priority <= dc.priority WHERE c.ccl_event_idx=%d AND c.device_class=dc.device_class_idx" % (self.idx))
        m_dict["classes"] = dict([(x["classname"], x) for x in dc.fetchall()])
        # device locations
        dc.execute("SELECT dl.* FROM device_location dl, ccl_dloc_con dc WHERE dc.ccl_event=%d AND dc.device_location=dl.device_location_idx" % (self.idx))
        m_dict["locations"] = dict([(x["location"], x) for x in dc.fetchall()])
        # mail list
        dc.execute("SELECT u.useremail, u.uservname, u.usernname, u.login FROM user u, ccl_user_con cu WHERE cu.user=u.user_idx AND cu.ccl_event=%d" % (self.idx))
        m_dict["users"] = dict([(x["login"], x) for x in dc.fetchall()])
        # correct email-addresses
        for login, stuff in m_dict["users"].iteritems():
            if not stuff["useremail"]:
                stuff["useremail"] = "lang-nevyjel@init.at"
        # device groups
        dc.execute("SELECT dg.* FROM device_group dg, ccl_dgroup_con cd WHERE cd.device_group = dg.device_group_idx AND cd.ccl_event=%d" % (self.idx))
        m_dict["device_groups"] = dict([(x["name"], x) for x in dc.fetchall()])
        # devices (with bootserver)
        if m_dict["classes"] and m_dict["locations"] and m_dict["device_groups"]:
            dc.execute("SELECT d.name, d.device_idx, dt.identifier, d2.name AS server FROM device_type dt, device d LEFT JOIN device d2 ON d.bootserver=d2.device_idx WHERE " + \
                       "dt.device_type_idx=d.device_type AND dt.identifier != 'MD' AND (%s OR d.device_class=0) " % (" OR ".join(["d.device_class=%d" % (x["device_class_idx"]) for x in m_dict["classes"].values()])) + \
                       "AND (%s OR d.device_location=0) " % (" OR ".join(["d.device_location=%d" % (x["device_location_idx"]) for x in m_dict["locations"].values()])) + \
                       "AND (%s)" % (" OR ".join(["d.device_group=%d" % (x["device_group_idx"]) for x in m_dict["device_groups"].values()])))
            for db_rec in dc.fetchall():
                m_dict["devices"][db_rec["name"]] = db_rec
                if db_rec["server"]:
                    if not db_rec["server"] in m_dict["servers"].keys():
                        m_dict["servers"][db_rec["server"]] = {"ip_list"     : self._find_host_route(dc, db_rec["server"]),
                                                               "device_dict" : {}}
                    m_dict["servers"][db_rec["server"]]["device_dict"][db_rec["device_idx"]] = db_rec["name"]
                else:
                    self.log("  No controlling server for device %s defined" % (db_rec["name"]))
        # disabled/enabled
        dc.execute("SELECT ccl.disabled FROM ccl_event ccl WHERE ccl.ccl_event_idx=%d" % (self.idx))
        m_dict["disabled"] = dc.fetchone()["disabled"]
        # cluster event
        dc.execute("SELECT c.* FROM cluster_event c, ccl_event cl WHERE cl.ccl_event_idx=%d AND cl.cluster_event=c.cluster_event_idx" % (self.idx))
        ev_list = dc.fetchall()
        if ev_list:
            m_dict["event"] = ev_list[0]
        #pprint.pprint(m_dict)
        return m_dict
    def add_to_cache(self, in_time, what, write_into_cache=True):
        if write_into_cache:
            self.__cache.append((what, in_time))
        if self.__rrd_name:
            try:
                rrdtool.update(*([self.__rrd_name] + ["%d:%s" % (int(in_time), str(what))]))
            except:
                self.log("error updating rrd: %s " % (sys.exc_info()[1]))
    def add_value(self, value, ins_time):
        triggered = None
        new_v_added, last_cv = (0, None)
        # last value of cache
        if self.__cache:
            last_cv = self.__cache[-1][0]
        # check validity of value
        if value == "U":
            if last_cv is None:
                self.log("Trying to add unknown value '%s' (not float), no cache defined up to now..." % (value))
            else:
                self.log("Trying to add unknown value '%s' (not float), using last value from cache (%s)" % (value, get_float_str(last_cv)))
                # add latest value again
                self.add_to_cache(ins_time, last_cv)
        else:
            try:
                value = float(value)
            except ValueError:
                if self.__cache:
                    self.log("Error adding value '%s' (not float), using last value from cache (%s)" % (value, get_float_str(last_cv)))
                    # add latest value again
                    self.add_to_cache(ins_time, last_cv)
                else:
                    self.log("Error adding value '%s' (not float), cache empty" % (value))
            else:
                self.add_to_cache(ins_time, value)
                new_v_added = 1
        if new_v_added:
            if self.last_triggered != "-":
                if abs(self.threshold - value) > self.hysteresis/2.:
                    log_str = "Clearing triggered_flag (was: %s) for key %s (%s)" % (self.last_triggered, self.key, self.get_inf_str())
                    self.log(log_str)
                    self.last_triggered = "-"
                    log_str = "  last 2 cache entries (latest first): %s, %s" % (get_float_str(self.__cache[-1][0]), get_float_str(self.__cache[-2][0]))
                    self.log(log_str)
        if len(self.__cache) > self.__max_cache_size:
            self.__cache = [x for x in self.__cache[1:]]
        # enough data to check for events?
        if len(self.__cache) >= 2:
            trigger_asc  = (self.__cache[-1][0] >= self.threshold and self.threshold >= self.__cache[-2][0] and self.__cache[-1][0] > self.__cache[-2][0])
            trigger_desc = (self.__cache[-1][0] <= self.threshold and self.threshold <= self.__cache[-2][0] and self.__cache[-1][0] < self.__cache[-2][0])
            if self.threshold_class in [0, 1] and trigger_asc:
                #print self.__cache[-1][0] >= self.threshold, self.threshold >= self.__cache[-2][0], self.__cache[-1][0] > self.__cache[-2][0]
                triggered = "A"
            elif self.threshold_class in [-1, 0] and trigger_desc:
                triggered = "D"
                #print self.cache[-1][0] <= self.threshold, self.threshold <= self.cache[-2][0], self.cache[-1][0] < self.cache[-2][0]
            if triggered:
                self.log("-" * 70)
                self.log(self.get_trigger_str(triggered))
                inf_str = self.get_inf_str()
                if self.last_triggered != "-":
                    log_str = "  Ignore triggered (%s) event for key %s (%s), last_triggerd is %s" % (triggered, self.key, inf_str, self.last_triggered)
                    self.log(log_str)
                    #print "NT : ", triggered
                else:
                    log_str = "  Event triggered (%s) for key %s (%s)" % (triggered, self.key, inf_str)
                    self.log(log_str)
                    self.last_triggered = triggered
                    self.trigger((int(ins_time) + int(self.__cache[-2][1]))/2)
                self.log("-" * 70)
        return triggered
    def get_trigger_str(self, trig_str):
        dir_dict = {"A" : ">",
                    "D" : "<"}
        return "%s event triggered [cache_size: %d] : %s (now) %s %s (tresh) %s %s (last)" % (self.get_class_dict()[self.threshold_class],
                                                                                              len(self.__cache),
                                                                                              get_float_str(self.__cache[-1][0]),
                                                                                              dir_dict[trig_str],
                                                                                              get_float_str(self.threshold),
                                                                                              dir_dict[trig_str],
                                                                                              get_float_str(self.__cache[-2][0]))
    def trigger(self, ins_time):
        dc = self.mach_struct.get_db_con().get_connection(SQL_ACCESS)
        # get event-info dict
        e_dict = self.get_event_info(dc)
        self.add_to_cache(time.time() +  1, self.__cache[-1][0], False)
        self.add_to_cache(time.time() + 15, self.__cache[-1][0], False)
        self.add_to_cache(time.time() + 29, self.__cache[-1][0], False)
        self.create_rrd_graph()
        self.log("  info:")
        # classes / locations
        info_list = []
        info_list.append("ccl_event on device %s ('%s', key %s, index %d)" % (self.mach_name, self.info, self.key, self.idx))
        info_list.append(self.get_trigger_str(self.last_triggered))
        if e_dict["event"]:
            info_list.append("cluster-event defined: %s (%s, %s)" % (e_dict["event"]["name"],
                                                                     e_dict["event"]["description"],
                                                                     e_dict["event"]["command"] or "no command for mother"))
            ev_idx = e_dict["event"]["cluster_event_idx"]
        else:
            info_list.append("no cluster-event defined")
            ev_idx = 0
        if e_dict["disabled"]:
            info_list.extend(["",
                              "this event is disabled"])
        info_list.append("")
        dump_size = min(len(self.__cache), 10)
        info_list.append("Cache dump: ")
        for idx in range(1, dump_size):
            info_list.append("%s : %s" % (get_time_str(self.__cache[-idx][1]), get_float_str(self.__cache[-idx][0])))
        info_list.append("")
        info_list.append("  responsible for %s (%s), %s (%s) and %s (%s)" % (logging_tools.get_plural("class", len(e_dict["classes"])),
                                                                             ", ".join(["%s [pri %d]" % (x["classname"], x["priority"]) for x in e_dict["classes"].values()]),
                                                                             logging_tools.get_plural("location", len(e_dict["locations"])),
                                                                             ", ".join(["%s" % (x["location"]) for x in e_dict["locations"].values()]),
                                                                             logging_tools.get_plural("device_group", len(e_dict["device_groups"])),
                                                                             ", ".join(["%s" % (x["name"]) for x in e_dict["device_groups"].values()])))
        if e_dict["devices"]:
            srv_dict = {}
            for node_name, server_name in [(x["name"], x["server"]) for x in e_dict["devices"].values()]:
                srv_dict.setdefault(server_name, []).append(node_name)
                srv_dict[server_name].sort()
            info_list.append("  list of devices: %s" % ("; ".join(["on %s: %s" % (k, logging_tools.compress_list(v)) for k, v in srv_dict.iteritems()])))
        else:
            info_list.append("  no devices associated")
        # mail-stuff
        if e_dict["users"]:
            info_list.extend(["", "  %s associated with this ccl_event" % (logging_tools.get_plural("user", len(e_dict["users"])))])
            for key, value in e_dict["users"].iteritems():
                info_list.append("    %s (%s)" % (value["login"], value["useremail"]))
        else:
            info_list.extend(["", "  no users associated with this ccl_event"])
        if len(e_dict["servers"].keys()):
            info_list.extend(["", "  %s found:" % (logging_tools.get_plural("controlling server", len(e_dict["servers"])))])
            for key, value in e_dict["servers"].iteritems():
                ip_list = value["ip_list"] or ["<unreachable>"]
                info_list.append("    %s at ip %s (%s)" % (key, value["ip_list"][0], logging_tools.get_plural("device", len(value["device_dict"].keys()))))
        else:
            info_list.extend(["", "  no controlling server found"])
        subject_pre_str = ""
        if not e_dict["disabled"] and e_dict["event"]:
            # passive log-entries
            for key, value in e_dict["devices"].iteritems():
                dev_idx = value["device_idx"]
                dc.execute("INSERT INTO ccl_event_log SET device=%s, ccl_event=%s, cluster_event=%s, passive=1", (dev_idx,
                                                                                                                  self.idx,
                                                                                                                  ev_idx))
            
            # active log-entry
            dc.execute("INSERT INTO ccl_event_log SET device=%s, ccl_event=%s, cluster_event=%s, passive=0", (self.mach_struct.dev_idx,
                                                                                                              self.idx,
                                                                                                              ev_idx))
            # contact the various mothers
            for key, value in e_dict["servers"].iteritems():
                ip_list = value["ip_list"]
                if e_dict["event"]["command"]:
                    if ip_list:
                        info_list.extend(["", "  sending '%s' to server %s (port %d, IP %s)" % (e_dict["event"]["command"], key, 8001, ip_list[0])])
                        m_com = e_dict["event"]["command"].split()
                        m_base = m_com.pop(0)
                        m_rest = " ".join(m_com)
                        server_com = server_command.server_command(command=m_base)
                        server_com.set_nodes(value["device_dict"].values())
                        for dev_idx, dev_name in value["device_dict"].iteritems():
                            if m_rest:
                                server_com.set_node_command(dev_name, m_rest)
                            mysql_tools.device_log_entry(dc,
                                                         dev_idx,
                                                         self.__loc_config["LOG_SOURCE_IDX"],
                                                         0,
                                                         log_status["i"]["log_status_idx"],
                                                         "issuing command %s%s: %s, %s" % (m_base,
                                                                                           m_rest and " (%s)" % (m_rest) or "",
                                                                                           self.info,
                                                                                           self.get_trigger_str(self.last_triggered)))
                        errnum, ret_str = net_tools.single_connection(host=ip_list[0],
                                                                      port=8001,
                                                                      command=server_com.create_string(),
                                                                      timeout=30).iterate()
                        if m_base != "ping":
                            subject_pre_str = "*** "
                        if errnum:
                            response = ret_str
                            server_repl = None
                        else:
                            try:
                                server_repl = server_command.server_reply(ret_str)
                            except ValueError:
                                response = "error decoding server_reply"
                                server_repl = None
                            else:
                                response = server_repl.get_result()
                        info_list.append("  got as response: %s" % (response))
                        if server_repl:
                            node_res = server_repl.get_node_results()
                            res_match = re.compile("^(?P<pre>.*) (?P<ip>\d+\.\d+\.\d+\.\d+) (?P<post>.*)$")
                            res_dict = {}
                            for dev_name, dev_res in node_res.iteritems():
                                rm = res_match.match(dev_res)
                                if rm:
                                    act_res, act_node_name = ("%s %s" % (rm.group("pre").strip(), rm.group("post").strip()), "%s (%s)" % (dev_name, rm.group("ip")))
                                else:
                                    act_res, act_node_name = (dev_res, dev_name)
                                res_dict.setdefault(act_res, []).append(act_node_name)
                                res_dict[act_res].sort()
                            for res in sorted(res_dict.keys()):
                                info_list.append("    %s (%s) : %s " % (res, logging_tools.get_plural("device", len(res_dict[res])), ", ".join(res_dict[res])))
                    else:
                        info_list.append("  server %s is unreachable" % (key))
                else:
                    info_list.extend(["", "no command defined"])
        if e_dict["users"]:
            self.send_mail("cluster_event@%s" % (self.__loc_config["SERVER_FULL_NAME"]),
                           [x["useremail"] for x in e_dict["users"].values()],
                           "%sCluster Event on %s (%s)" % (subject_pre_str, self.mach_name, self.info),
                           info_list,
                           self.rrd_graph_name and [self.rrd_graph_name] or [])
        for line in info_list:
            self.log("- %s" % (line))
        dc.release()
        #pprint.pprint(info_list)
    def send_mail(self, from_addr, to, subject, text_f, bin_objs=[]):
        new_mail = mail_tools.mail(subject, from_addr, to, text_f)
        new_mail.set_server(self.__glob_config["SMTP_SERVER"], self.__glob_config["SMTP_SERVER_HELO"])
        for bin_obj in bin_objs:
            new_mail.add_binary_object(bin_obj)
        stat, log_lines = new_mail.send_mail()
        for log_line in log_lines:
            self.log(" - %s" % (log_line))
        del new_mail
    def _get_network_type_indices_and_net_devices(self, cc):
        # fetch all network_type indices
        cc.execute("SELECT nt.network_type_idx, nt.identifier FROM network_type nt")
        all_nw_idxs = cc.fetchall()
        # valid network_type indices
        valid_nwt_list = [x["network_type_idx"] for x in all_nw_idxs if x["identifier"] not in ["l"]]
        # invalid network_type indices
        invalid_nwt_list = [x["network_type_idx"] for x in all_nw_idxs if x["identifier"] in ["l"]]
        srv_idxs = [self.__loc_config["RRD_SERVER_IDX"]]
        # get real server_idx
        cc.execute("SELECT d.device_idx FROM device d WHERE d.name='%s'" % (self.__loc_config["SERVER_SHORT_NAME"]))
        if cc.rowcount:
            my_srv_idx = cc.fetchone()["device_idx"]
            if my_srv_idx != self.__loc_config["RRD_SERVER_IDX"]:
                self.log("server_idx from db (%d) differs from short_host_name server_idx (%d)" % (self.__loc_config["RRD_SERVER_IDX"], my_srv_idx),
                         logging_tools.LOG_LEVEL_WARN)
                srv_idxs.append(my_srv_idx)
        else:
            self.log("short_host_name '%s' not in database, strange ..." % (self.__loc_config["SERVER_SHORT_NAME"]),
                     logging_tools.LOG_LEVEL_WARN)
        cc.execute("SELECT i.ip, n.netdevice_idx FROM netdevice n, netip i, network nw WHERE (%s) AND i.netdevice=n.netdevice_idx AND i.network=nw.network_idx" % (" OR ".join(["n.device=%d" % (x) for x in srv_idxs])))
        glob_net_devices = {}
        for db_rec in cc.fetchall():
            n_d, n_i = (db_rec["netdevice_idx"], db_rec["ip"])
            glob_net_devices.setdefault(n_d, []).append(n_i)
        return valid_nwt_list, invalid_nwt_list, glob_net_devices
    def _find_host_route(self, dc, name, valid_nwt_list=None, invalid_nwt_list=None, glob_net_devices=None):
        if not (valid_nwt_list and invalid_nwt_list and glob_net_devices):
            valid_nwt_list, invalid_nwt_list, glob_net_devices = self._get_network_type_indices_and_net_devices(dc)
        if name == self.__loc_config["SERVER_SHORT_NAME"]:
            ip_list = ["127.0.0.1"]
        else:
            ip_list = []
        dc.execute("SELECT i.ip, n.netdevice_idx, nw.network_type FROM device d, netdevice n, netip i, network nw WHERE n.device=d.device_idx AND i.netdevice=n.netdevice_idx AND i.network=nw.network_idx AND d.name='%s'" % (name))
        # valid and invalid ip-dict
        loc_net_devices = {"i" : {}, "v" : {}}
        for db_rec in dc.fetchall():
            n_d, n_i, n_t = (db_rec["netdevice_idx"], db_rec["ip"], db_rec["network_type"])
            if n_t in valid_nwt_list:
                n_t = "v"
            else:
                n_t = "i"
            loc_net_devices[n_t].setdefault(n_d, [])
            #if not loc_net_devices[n_t].has_key(n_d):
            #    loc_net_devices[n_t][n_d] = []
            loc_net_devices[n_t][n_d].append(n_i)
        if loc_net_devices["v"]:
            nw_type = "v"
        elif loc_net_devices["i"]:
            nw_type = "i"
            self.log("Found no valid net_devices for device '%s' but %d invalid ones (a very well-configured Cluster...)" % (name, len(loc_net_devices["i"].keys())),
                     logging_tools.LOG_LEVEL_WARN)
        else:
            nw_type = None
        if nw_type:
            src_str_s = " OR ".join(["h.s_netdevice=%d" % (x) for x in glob_net_devices])
            dev_str_d = " OR ".join(["h.d_netdevice=%d" % (x) for x in loc_net_devices[nw_type].keys()])
            dc.execute("SELECT h.s_netdevice, h.d_netdevice FROM hopcount h WHERE (%s) AND (%s) ORDER BY h.value" % (src_str_s, dev_str_d))
            for hc in dc.fetchall():
                if hc["s_netdevice"] in glob_net_devices.keys():
                    net_idx = hc["d_netdevice"]
                else:
                    net_idx = hc["s_netdevice"]
                if loc_net_devices[nw_type].has_key(net_idx):
                    ipl = loc_net_devices[nw_type][net_idx]
                    for act_ip in ipl:
                        if act_ip not in ip_list:
                            ip_list.append(act_ip)
            if ip_list:
                self.log("Found %s to reach device %s: %s" % (logging_tools.get_plural("IP-adress", len(ip_list)),
                                                              name, ",".join(ip_list)))
            else:
                self.log("Cannot add host '%s' (empty ip_list -> cannot reach host)" % (name),
                         logging_tools.LOG_LEVEL_WARN)
        else:
            self.log("refuse to add device '%s' without netdevices" % (name),
                     logging_tools.LOG_LEVEL_WARN)
        return ip_list
    

class snmp_device(object):
    def __init__(self, name, ad_struct):
        self.name = name
        self.__ad_struct = ad_struct
        self.__defined_mibs, self.__mib_keys = ({}, [])
        # dictionary: key -> mib
        self.__mib_key_dict = {}
        self.mib_values = {}
        self.set_snmp_update_speed()
        self.__log_queue = self.__ad_struct.get_log_queue()
        # to init last_update 
        self.update_start()
    def is_meta_device(self):
        return False
    def get_name(self):
        # return beautified name
        my_name = self.name
        if self.is_meta_device():
            if my_name.startswith("METADEV_"):
                return "%s (metadevice)" % (my_name[8:])
            else:
                return my_name
        else:
            return my_name
    def get_real_name(self):
        return self.name
    def get_glob_config(self):
        return self.__ad_struct.get_glob_config()
    def get_loc_config(self):
        return self.__ad_struct.get_loc_config()
    def get_db_con(self):
        return self.__ad_struct.get_db_con()
    def get_log_queue(self):
        return self.__log_queue
    def get_ad_struct(self):
        return self.__ad_struct
    #def log(self, what, glob = 0):
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK, glob=False):
        self.__log_queue.put(("mach_log", (threading.currentThread().getName(), what, lev, self.name)))
        if glob:
            self.__log_queue.put(("log", (threading.currentThread().getName(), what, lev)))
    def set_snmp_class(self, snmp_class):
        self.snmp_class_name = snmp_class["name"]
        self.snmp_class_descr = snmp_class["descr"]
        self.set_snmp_update_speed(snmp_class["update_freq"])
    def set_snmp_update_speed(self, speed=60):
        # update_speed is the maximum value for update_counter
        # num_updates gets increased by one every time an update occurs
        self.__update_speed = max(1, int(speed / self.get_glob_config()["MAIN_TICK"]))
        self.__update_counter = self.__update_speed
        # got increased to zero as soon as update_start is called once
        self.num_updates = -1
    def need_snmp_update(self):
        return True
        self.__update_counter -= 1
        if not self.__update_counter:
            self.__update_counter = self.__update_speed
            return True
        else:
            return False
    def update_start(self):
        self.num_updates += 1
        self.last_snmp_update = time.time()
    def add_mib(self, name, mib, key, info, factor):
        self.__mib_keys.append(key)
        self.__mib_keys.sort()
        p_mib = tuple([int(x) for x in mib.split(".") if x])
        self.__defined_mibs[p_mib] = {"name"        : name,
                                      "key"         : key,
                                      "info"        : info,
                                      "last_update" : 0.,
                                      "factor"      : factor}
        self.mib_values[p_mib] = "U"
        self.__mib_key_dict[key] = p_mib
    def get_factor(self, mib):
        return self.__defined_mibs[mib]["factor"]
    def get_mib_keys(self):
        return self.__mib_keys
    def mibs_defined(self):
        return len(self.__defined_mibs)
    def get_defined_mibs(self):
        return self.__defined_mibs.keys()
    def get_defined_mibs_dict(self):
        return self.__defined_mibs
    def invalidate_illegal_mibs(self, timeout=120):
        act_time = time.time()
        inv_mibs = [x for x in self.__defined_mibs.keys() if self.__defined_mibs[x]["last_update"] < act_time - timeout and self.mib_values[x] == "U"]
        for mib in inv_mibs:
            self.mib_values[mib] = "U"
    def num_valid_mibs(self):
        return len([x for x in self.__defined_mibs.keys() if self.mib_values[x] != "U"])
    def get_mib_value(self, mib):
        return self.mib_values[mib]
    def get_mib_value_by_key(self, key):
        return self.mib_values[self.__mib_key_dict[key]]
    def set_mib(self, mib, stuff):
        # store with correcting factor
        self.mib_values[mib] = stuff * self.__defined_mibs[mib]["factor"]
        self.log("Setting mib '%s' to the corrected value %s" % (mib, str(self.mib_values[mib])))
        self.__defined_mibs[mib]["last_update"] = time.time()
        
## #class snmp_dispatcher(asynrole.manager):
## class snmp_dispatcher(object):
##     def __init__(self, mib_name, log_queue, error_hook=None, got_hook=None):
##         asynrole.manager.__init__(self, (self.send_done, None))
##         self.__log_queue = log_queue
##         self.__mib_con = validate_container(mib_name, self.__log_queue)
##         self.__mib_con.read_from_file()
##         self.__mib_con.write_to_file()
##         self.pending = []
##         self.timeout = 5
##         self.err_hook = error_hook
##         self.ticket_num = 0
##         if got_hook:
##             self.got_hook = got_hook
##         else:
##             self.got_hook = self.handle_ret
##     def close(self):
##         self.__mib_con.write_to_file()
##         asynrole.manager.close(self)
##     #def delete_timeout(self):
##     #    idx = 0
##     #    for (req, dst, expire, got_hook, ticket_num) in self.pending:
##     #        if expire > 
##     #        idx++
##     def send_set(self, dst, args, got_hook=None, port=161):
##         # increase ticket number
##         ver = alpha.protoVersions[alpha.protoVersionId1]
##         req = ver.Message()
##         req.apiAlphaSetCommunity(args[0])
##         req.apiAlphaSetPdu(ver.SetRequestPdu())
##         s_arg = []
##         for mib, m_type, val in args[1:]:
##             if m_type == "i":
##                 s_arg.append((mib, ver.Integer(val)))
##             elif m_type == "a":
##                 s_arg.append((mib, ver.IpAddress(val)))
##             else:
##                 s_arg.append((mib, ver.OctetString(val)))
##         req.apiAlphaGetPdu().apiAlphaSetVarBindList(*s_arg)
##         # send set
##         asynrole.manager.send(self, req.berEncode(), (dst, port))
##         self.ticket_num += 1
##         # copy own got_hook if not set explicitly
##         if not got_hook:
##             got_hook = self.got_hook
##         self.pending.append((req, (dst, port), time.time() + self.timeout, got_hook, self.ticket_num))
##         return self.ticket_num
##     def send_get(self, dst, args, got_hook=None, port=161):
##         ver = alpha.protoVersions[alpha.protoVersionId1]
##         req = ver.Message()
##         req.apiAlphaSetCommunity(args[0])
##         req.apiAlphaSetPdu(ver.GetRequestPdu())
##         req.apiAlphaGetPdu().apiAlphaSetVarBindList(*[(x, ver.Null()) for x in args[1:]])
##         # send get
##         asynrole.manager.send(self, req.berEncode(), (dst, port))
##         self.ticket_num += 1
##         if not got_hook:
##             got_hook = self.got_hook
##         self.pending.append((req, (dst, port), time.time() + self.timeout, got_hook, self.ticket_num))
##         return self.ticket_num
##     def handle_ret(self, *args):
##         # dummy got_hook
##         is_error, src, ticket_num, ret_dict = args
##         print is_error, src, ret_dict
##     def error_hook(self, err_str):
##         # dummy err_hook
##         if self.err_hook:
##             self.err_hook(err_str)
##         else:
##             print err_str
##     def send_done(self, manager, cbtx, (answer, src), (exc_type, exc_value, exc_traceback)):
##         # handles both get and set requestes
##         is_err = False
##         if exc_type is not None:
##             is_err, err_str = (True, "%s %s %s" % (str(exc_type), str(exc_value), str(exc_traceback)))
##             self.error_hook(err_str)
##             return
##         ver = alpha.protoVersions[alpha.protoVersionId1]
##         rsp = ver.Message()
##         rsp.berDecode(answer)
##         idx = 0
##         for (req, dst, expire, got_hook, ticket_num) in self.pending:
##             rem = 0
##             try:
##                 if req.apiAlphaMatch(rsp):
##                     rem = 1
##             except pysnmp.asn1.error.BadArgumentError:
##                 pass
##             if rem:
##                 self.pending.pop(idx)
##                 break
##             idx += 1
##         else:
##             is_err, err_str = (True, "WARNING: dropping unmatched (late) response: \n%s" % (str(rsp)))
##             self.error_hook(err_str)
##             return
##         ret_dict = {}
##         errorstat = rsp.apiAlphaGetPdu().apiAlphaGetErrorStatus()
##         if errorstat:
##             is_err, err_str = (True, errorstat)
##             ret_dict = err_str
##         else:
##             for var in rsp.apiAlphaGetPdu().apiAlphaGetVarBindList():
##                 oid, val = var.apiAlphaGetOidVal()
##                 ret_dict[oid.get()] = val.get()
##         got_hook(is_err, src, ticket_num, ret_dict, self.__mib_con)

class validate_container(object):
    def __init__(self, file_name, log_queue):
        self.__file_name = file_name
        self.__log_queue = log_queue
        self.__dict = {}
    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        self.__log_queue.put(("log", (threading.currentThread().getName(), "vcon: %s" % (what), level)))
    def read_from_file(self):
        if os.path.isfile(self.__file_name):
            try:
                mib_th_lines = file(self.__file_name, "r").read().split("\n")
            except IOError:
                self.log("cannot read '%s': %s (%s)" % (self.__file_name,
                                                        str(sys.exc_info()[0]),
                                                        str(sys.exc_info()[1])))
            else:
                for line in mib_th_lines:
                    self.feed_line(line)
    def write_to_file(self):
        try:
            fh = file(self.__file_name, "w")
        except IOError:
            self.log("Cannot open %s for writing: %s (%s)" % (self.__file_name,
                                                              str(sys.exc_info()[0]),
                                                              str(sys.exc_info()[1])))
        else:
            for mib in sorted(self.__dict.keys()):
                mib_stuff = self.__dict[mib]
                fh.write("\n".join(mib_stuff.get_file_lines() + [""]))
            fh.close()
            self.log("wrote %s" % (self.__file_name))
    def feed_line(self, line):
        s_line = line.strip()
        if not s_line.startswith("#"):
            l_p = s_line.split()
            if len(l_p) == 3:
                mib_name = l_p[0]
                if not self.__dict.has_key(mib_name):
                    self.__dict[mib_name] = snmp_validate_struct(mib_name, self.__log_queue)
                self.__dict[mib_name].feed_line(line)
    def validate_mib(self, mib, value):
        if not self.__dict.has_key(mib):
            self.__dict[mib] = snmp_validate_struct(mib, self.__log_queue)
        return self.__dict[mib].feed_value(value)
                
class snmp_validate_struct(object):
    def __init__(self, mib, log_queue):
        self.__mib = mib
        self.__log_queue = log_queue
        self.__th_dict = {"min"         : None,
                          "max"         : None,
                          "min_correct" : None,
                          "max_correct" : None,
                          "min_ignore"  : None,
                          "max_ignore"  : None}
        self.log("init")
    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        self.__log_queue.put(("log", (threading.currentThread().getName(), "mib %s: %s" % (self.__mib, what) , level)))
    def feed_line(self, line):
        if not line.strip().startswith("#"):
            line_p = line.strip().split()
            if len(line_p) == 3:
                mib, th_name, th = line_p
                if th.lower != "none":
                    try:
                        th_f = float(th)
                    except:
                        pass
                    else:
                        if mib == self.__mib and self.__th_dict.has_key(th_name):
                            self.__th_dict[th_name] = th_f
                            self.log("setting %s to %.2f" % (th_name, th_f))
                        else:
                            self.log("unknown th_key '%s'" % (th_name))
    def feed_value(self, value):
        if self.__th_dict["min"] is None or value < self.__th_dict["min"]:
            self.__th_dict["min"] = value
            self.log("setting minimum value to %.2f" % (value))
        if self.__th_dict["max"] is None or value > self.__th_dict["max"]:
            self.__th_dict["max"] = value
            self.log("setting maximum value to %.2f" % (value))
        if self.__th_dict["min_ignore"] is not None and value < self.__th_dict["min_ignore"]:
            self.log("ignoring value %.2f because lower than min_ignore value %.2f" % (value, self.__th_dict["min_ignore"]))
            value = None
        elif self.__th_dict["max_ignore"] is not None and value > self.__th_dict["max_ignore"]:
            self.log("ignoring value %.2f because higher than max_ignore value %.2f" % (value, self.__th_dict["max_ignore"]))
            value = None
        elif self.__th_dict["min_correct"] is not None and value < self.__th_dict["min_correct"]:
            value = self.__th_dict["min_correct"]
            self.log("limiting value from %.2f to min_correct value %.2f" % (value, self.__th_dict["min_correct"]))
        elif self.__th_dict["max_correct"] is not None and value > self.__th_dict["max_correct"]:
            value = self.__th_dict["max_correct"]
            self.log("limiting value from %.2f to max_correct value %.2f" % (value, self.__th_dict["max_correct"]))
        return value
    def get_file_lines(self):
        f_lines = ["# MIB %s" % (self.__mib)]
        for th_name in sorted(self.__th_dict.keys()):
            th = self.__th_dict[th_name]
            if th is None:
                f_lines.append("%s %s None" % (self.__mib, th_name))
            else:
                f_lines.append("%s %s %.2f" % (self.__mib, th_name, th))
        f_lines.append("")
        return f_lines

class device_vector(object):
    def __init__(self, recv_time, recv_type, recv_version, vector):
        # float
        self.recv_time = recv_time
        # string (udp, tcp, snmp)
        self.recv_type = recv_type
        # integer
        self.vector_version = recv_version
        # array
        self.vector = vector
        # counter for meta_devices
        self.md_counter = 0
    def __repr__(self):
        return "device vector, receive_time is %.2f, recv_type is %s, version is %d, %d elements" % (self.recv_time,
                                                                                                     self.recv_type,
                                                                                                     self.vector_version,
                                                                                                     len(self.vector))
    
class rrd_data(object):
    def __init__(self, device, descr, rrd_data_idx):
        self.__device = device
        self.__descr = descr
        self.__descr_p = descr.split(".")
        self.__descr_p_safe = [x.replace("/", "") for x in self.__descr_p]
        self.__local_name = "%s/%s.rrd" % ("/".join(self.__descr_p_safe[:-1]),
                                           self.__descr_p_safe[-1])
        self.__info_mapping = {}
        self.__last_update = time.time()
        self.to_correct = False
        # real_type (for meta-devices : the sum is real, max/mean/min is virtual)
        if descr.split(".")[-1].endswith("_sum") or not descr.split(".")[-1].count("_"):
            self.__real_type = True
            self.__virtual_type = ""
        else:
            self.__real_type = False
            self.__virtual_type = descr.split(".")[-1].split("_")[-1]
        self.set_from_snmp()
        # index of rrd_data in DB
        self.set_rrd_data_index(rrd_data_idx)
    def update(self, in_dict):
        for key, value in in_dict.iteritems():
            self[key] = value
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__device.log("%s: %s" % (self.__descr, what), lev)
    def set_rrd_data_index(self, di):
        self.__rrd_data_index = di
    def get_rrd_data_index(self):
        return self.__rrd_data_index
    def set_from_snmp(self, fs=False):
        self.__from_snmp = fs
    def __setitem__(self, key, value):
        self.__info_mapping[key] = value
        if key == "factor":
            if value not in [1, 1., 1L]:
                self.to_correct = True
            else:
                self.to_correct = False
    def __getitem__(self, key):
        return self.__info_mapping[key]
    def get_info_map(self):
        return self.__info_mapping
    def is_real_type(self):
        return self.__real_type
    def get_virtual_type(self):
        return self.__virtual_type
    def create_rrd_database(self, rrd_dir, class_dict, force=False, check_for_changes=True):
        self.full_path = "%s/%s" % (rrd_dir, self.__local_name)
        local_dir = os.path.dirname(self.full_path)
        if not os.path.isdir(local_dir):
            if os.path.isfile(local_dir):
                self.log("removing old file %s" % (local_dir), logging_tools.LOG_LEVEL_WARN)
                try:
                    os.unlink(local_dir)
                except:
                    self.log("error removing file %s: %s" % (local_dir, process_tools.get_except_info()),
                             logging_tools.LOG_LEVEL_CRITICAL)
            self.log("creating directory %s" % (local_dir))
            os.makedirs(local_dir)
        rebuild = force
        if os.path.isfile(self.full_path):
            if check_for_changes:
                rrd_info = rrdtool.info(self.full_path)
                hb_value = rrd_info["ds"]["v0"]["minimal_heartbeat"]
                new_hb = class_dict["heartbeat"]
                if hb_value != new_hb:
                    self.log("heartbeat-value changed from %d to %d" % (hb_value,
                                                                        new_hb))
                    rrdtool.tune(*([self.full_path] + ["-h", "v0:%d" % (new_hb)]))
        else:
            self.log("rrd-file %s not found, creating" % (self.__local_name))
            rebuild = True
        if rebuild:
            start_time = time.time()
            self.log("Creating rrd-database (rrd_class %s)" % (class_dict["name"]))
            val_a = [self.full_path]
            val_a.append("-s %d" % (class_dict["step"]))
            val_a.append("DS:v0:GAUGE:%d:U:U" % (class_dict["heartbeat"]))
            for rra_idx, rra in class_dict["rras"].iteritems():
                val_a.append("RRA:%s:0.5:%d:%d" % (rra["cf"], rra["steps"], rra["rows"]))
            #print val_a
            c_ret = rrdtool.create(*val_a)
            self.log("rrd_create() with %s returned %s" % (logging_tools.get_plural("tuple", len(val_a)), str(c_ret)))
            end_time = time.time()
            self.log("Took %s" % (logging_tools.get_diff_time_str(end_time - start_time)))
    def store_values(self, in_list):
        try:
            #if self.__descr.startswith("load.1"):
            #    print [self.__full_path] + in_list
            act_time = time.time()
            diff_time = abs(act_time - self.__last_update)
            if  diff_time < 2:
                self.log("last update only %s ago, waiting for 1 second" % (logging_tools.get_diff_time_str(diff_time)),
                         logging_tools.LOG_LEVEL_WARN)
                time.sleep(2)
                act_time = time.time()
            self.__last_update = act_time
            c_ret = rrdtool.update(*([self.full_path] + in_list))
        except:
            self.log("update raised exception: %s" % (process_tools.get_except_info()), logging_tools.LOG_LEVEL_CRITICAL)
        else:
            if c_ret is not None:
                self.log("update gave %s" % (c_ret))
    def correct_value(self, value):
        if type(value) in [type(0), type(0L), type(0.)]:
            return value * self.__info_mapping["factor"]
        else:
            return value
    def get_db_info_str(self):
        return "key %-24s for db_index %4d (%s)" % (self.__descr,
                                                    self.__rrd_data_index,
                                                    self.get_info_str())
    def get_info_str(self):
        return "%s unit %8s, base %4d, factor %8.3f, var_type %s, %s" % (self.__real_type and "[*]" or "[-]",
                                                                         "'%s'" % (self.__info_mapping["unit"]),
                                                                         self.__info_mapping["base"],
                                                                         self.__info_mapping["factor"],
                                                                         self.__info_mapping["var_type"],
                                                                         self.__info_mapping["info"])
class b_mon_keys(object):
    def __init__(self):
        self.__keys = {}
    def add_key(self, k):
        k_s = k.split(".")
        head_k = k_s.pop(0)
        if not self.__keys.has_key(head_k):
            self.__keys[head_k] = b_mon_keys()
        if k_s:
            self.__keys[head_k].add_key(".".join(k_s))
    def get_num_keys(self):
        return len(self.__keys.keys())
    def get_list(self):
        all_keys = sorted(self.__keys.keys())
        # check for zero-sublist
        if not [True for k in all_keys if self.__keys[k].get_num_keys()] and not [True for k in all_keys if not k[-1].isdigit()]:
            ret_list = [[logging_tools.compress_list(all_keys)]]
        else:
            ret_list = []
            for k in all_keys:
                if self.__keys[k].get_num_keys():
                    sub_list = self.__keys[k].get_list()
                    ret_list.extend([["%s." % (k)] + sub_list[0]] + [[""] + x for x in sub_list[1:]])
                else:
                    ret_list.append([k])
        return ret_list
    def get_string(self):
        all_keys = sorted(self.__keys.keys())
        # check for zero-sublist
        if not [True for k in all_keys if self.__keys[k].get_num_keys()] and not [True for k in all_keys if not k[-1].isdigit()]:
            ret_list = [logging_tools.compress_list(all_keys)]
        else:
            ret_list = []
            for k in all_keys:
                if self.__keys[k].get_num_keys():
                    ret_list.append("%s.(%s)" % (k,
                                                 self.__keys[k].get_string()))
                else:
                    ret_list.append(k)
        return ",".join(ret_list)
        
def read_rrd_class_tree(dc):
    dc.execute("SELECT rc.*, ra.* FROM rrd_class rc LEFT JOIN rrd_rra ra ON ra.rrd_class=rc.rrd_class_idx")
    rrd_classes = {}
    for db_rec in dc.fetchall():
        if not rrd_classes.has_key(db_rec["rrd_class_idx"]):
            rrd_classes[db_rec["rrd_class_idx"]] = db_rec
            rrd_classes[db_rec["rrd_class_idx"]]["rras"] = {}
        if db_rec["rrd_rra_idx"]:
            rrd_classes[db_rec["rrd_class_idx"]]["rras"][db_rec["rrd_rra_idx"]] = db_rec
    return rrd_classes

class rrd_device(snmp_device):
    def __init__(self, name, iplist, dev_idx, ad_struct, dev_type):
        snmp_device.__init__(self, name, ad_struct)
        self.__meta_dev = None
        self.device_type = dev_type
        # default value
        self.ip_list = []
        # list of valid ip-addresses
        self.set_ip_list(iplist)
        # device idx
        self.dev_idx = dev_idx
        # init rrd-cache
        self.init_rrd_cache()
        self.set_lv_tt()
        # rrd root dir
        self.rrd_dir = ""
        # actual rrd-class
        self.act_rrd_class, self.act_rrd_class_idx = ({}, 0)
        # rrd filename
        self.rrd_name = None
        # time of last update
        self.last_update = time.time() - 120
        # data lock, can be acquired from more than one thread at one time, work only if no change_lock is active
        self.__data_lock_num = 0
        self.__data_lock_possible = True
        # change lock, ignores read_locks
        self.__change_lock = threading.RLock()
        self.lockers = []
        self.init_rrd()
        self.init_mapping()
        self.acquire_change_lock()
        self.set_device_group()
        self.__max_cache_size, self.__max_cache_time = (self.get_glob_config()["MAX_CACHE_SIZE"],
                                                        self.get_glob_config()["MAX_CACHE_TIME"])
        self.__md_keep_counter = self.get_glob_config()["METADEVICE_KEEP_COUNTER"]
        self.save_vectors = False
    def set_save_vectors(self, save_vectors):
        self.__save_vectors = save_vectors
        self.log("save_vectors is %s" % (self.__save_vectors and "enabled" or "disabled"))
    def get_save_vectors(self):
        return self.__save_vectors
    save_vectors = property(get_save_vectors, set_save_vectors)
    def get_device_type(self):
        return self.device_type
    def set_device_group(self, dg=0):
        self.device_group = dg
        if self.device_group:
            self.log("Device_group set to %d" % (self.device_group))
        else:
            self.log("Device_group cleared")
    def get_device_group(self):
        return self.device_group
    def init_rrd_cache(self):
        self.__rrd_vectors = []
        self.__num_vectors, self.__num_slots = (0, 0)
        self.rrd_cache_init = time.time()
    def set_lv_tt(self, v_time=None, v_type=None):
        if v_time is None:
            # init
            self.__latest_vector_time = 0
            self.__latest_vector_type = "???"
            self.__time_vector = []
        else:
            if len(self.__time_vector) > 20:
                self.__time_vector.pop(0)
            if self.__latest_vector_time:
                self.__time_vector.append(v_time - self.__latest_vector_time)
            self.__latest_vector_time = v_time
            self.__latest_vector_type = v_type
    def get_lv_tt(self):
        return (self.__latest_vector_time,
                self.__latest_vector_type,
                self.__time_vector and sum(self.__time_vector) / len(self.__time_vector) or 0)
    def set_meta_dev_descr(self, cc):
        self.__meta_dev = None
        ad_struct = self.get_ad_struct()
        meta_dev = None
        if ad_struct.has_device_group_key(self.get_device_group()):
            md_is_cdg =  False
            meta_dev = ad_struct.get_device_group(self.get_device_group())
            if meta_dev.dev_idx == self.dev_idx:
                cdg_list = [ad_struct.get_device_group(x) for x in ad_struct.get_device_group_keys(True) if ad_struct.get_device_group(x).is_cdg()]
                if cdg_list:
                    # search cdg
                    meta_dev = cdg_list[0]
                    if meta_dev.dev_idx == self.dev_idx:
                        self.log("set_meta_dev_descr(), found no meta-device (i am the cluster_device_group)")
                        meta_dev = None
                    else:
                        self.log("set_meta_dev_descr(), found meta-device %s (cluster_device_group)" % (meta_dev.name))
                        md_is_cdg =  True
                else:
                    self.log("set_meta_dev_descr(), found no meta-device (no cluster_device_group)")
                    meta_dev = None
            else:
                self.log("set_meta_dev_descr(), found meta-device %s" % (meta_dev.name))
            if meta_dev:
                self.__meta_dev = meta_dev
                meta_dev.acquire_change_lock()
                self.log("save_rrd_cache() for metadevice called")
                meta_dev.save_rrd_cache()
                own_keys = self.__act_refs
                add_keys = []
                for mdd in self.get_glob_config()["METADEV_KEYS"]:
                    if mdd.endswith("."):
                        add_keys.extend([x for x in own_keys if x.startswith(mdd)])
                    else:
                        add_keys.extend([x for x in own_keys if x == mdd         ])
                if self.is_meta_device():
                    add_keys = [x for x in add_keys if self.rrd_data[x].is_real_type()]
                else:
                    add_keys = [x for x in add_keys if self.rrd_data[x].is_real_type() and x in self.__act_refs]
                # make keys unique
                add_keys = dict([(x, True) for x in add_keys]).keys()
                meta_dev.register_child_rrd(self.name)
                self.log("Reporting %s to meta-device" % (logging_tools.get_plural("key", len(add_keys))))
                md_mapping = {}
                for key in sorted(add_keys):
                    info_map = self.rrd_data[key].get_info_map()
                    if info_map["var_type"] == "i":
                        def_val = 0
                    else:
                        def_val = 0.
                    if info_map["info"].endswith("[sum]"):
                        info_map["info"] = info_map["info"][:-6]
                    if key.endswith("_sum"):
                        new_key = key[:-4]
                    else:
                        new_key = key
                    md_mapping[new_key] = self.__act_refs.index(key)
                    meta_dev.sync_rrd_info_insert(cc, "%s_sum"   % (new_key), "%s [sum]"   % (info_map["info"]), 0, info_map["base"], info_map["factor"], info_map["unit"], def_val)
                    # mean / max / min / smart value
                    meta_dev.sync_rrd_info_insert(cc, "%s_mean"  % (new_key), "%s [mean]"  % (info_map["info"]), 0, info_map["base"], info_map["factor"], info_map["unit"], def_val)
                    meta_dev.sync_rrd_info_insert(cc, "%s_max"   % (new_key), "%s [max]"   % (info_map["info"]), 0, info_map["base"], info_map["factor"], info_map["unit"], def_val)
                    meta_dev.sync_rrd_info_insert(cc, "%s_min"   % (new_key), "%s [min]"   % (info_map["info"]), 0, info_map["base"], info_map["factor"], info_map["unit"], def_val)
                    meta_dev.sync_rrd_info_insert(cc, "%s_smart" % (new_key), "%s [smart]" % (info_map["info"]), 0, info_map["base"], info_map["factor"], info_map["unit"], def_val)
                meta_dev.set_meta_rrd_mapping()
                meta_dev.set_child_mapping(self.name, md_mapping)
                meta_dev.release_change_lock()
                # only call if meta_dev is not the cluster_meta_device
                if not md_is_cdg:
                    meta_dev.set_meta_dev_descr(cc)
        else:
            self.log("set_meta_dev_descr(), found no meta-device (device_group has not meta_device)")
    def save_child_vector(self, child_dev, raw_vector):
        self.acquire_change_lock()
        if child_dev.name not in self.__child_mappings.keys():
            self.log("child %s not in mapping table, checking ..." % (child_dev.name),
                     logging_tools.LOG_LEVEL_WARN)
            dc = self.get_db_con().get_connection(SQL_ACCESS)
            child_dev.set_meta_dev_descr(dc)
            dc.release()
        self.__child_vectors[child_dev.name] = raw_vector
        self.release_change_lock()
    def flush_metadevice_vectors(self, dc):
        act_time = time.time()
        if self.__last_cv_update <= act_time - self.get_glob_config()["METADEV_TIMEOUT"] or self.__last_cv_update > act_time or (self.__last_cv_update-act_time) < 0.01:
            self.acquire_change_lock()
            upd_timestamp = int(abs(act_time - self.__last_cv_update) / 2 + self.__last_cv_update)
            self.__last_cv_update = act_time
            # generate vector
            if self.__child_vectors:
                my_keys = self.rrd_data.keys()
                remove_keys = []
                tot_dict = {}
                for child_name, child_vector in self.__child_vectors.iteritems():
                    child_vector.md_counter += 1
                    if child_vector.md_counter > self.__md_keep_counter:
                        remove_keys.append(child_name)
                        self.log("removed child %s because too old (%d > %d)" % (child_name,
                                                                                 child_vector.md_counter,
                                                                                 self.__md_keep_counter),
                                 logging_tools.LOG_LEVEL_WARN)
                    else:
                        for key, value in self.__child_mappings[child_name].iteritems():
                            if type(child_vector.vector[value]) != type(""):
                                # remove 'U' values (snmp-stuff)
                                tot_dict.setdefault(key, []).append(child_vector.vector[value])
                val_dict = dict([("%s_sum"  % (k), sum(v)         ) for k, v in tot_dict.iteritems()] + 
                                [("%s_max"  % (k), max(v)         ) for k, v in tot_dict.iteritems()] +
                                [("%s_min"  % (k), min(v)         ) for k, v in tot_dict.iteritems()] +
                                [("%s_mean" % (k), sum(v) / len(v)) for k, v in tot_dict.iteritems()])
                # log lines
                log_lines = []
                for key, data in tot_dict.iteritems():
                    # process the smart part
                    smart_vec, del_vec = ([x for x in data], [])
                    target_len = max(int(len(data) * 0.7), 2)
                    while len(smart_vec) > target_len:
                        act_mv = sum(smart_vec) / float(len(smart_vec))
                        diff_t = [abs(x - act_mv) for x in smart_vec]
                        diff_idx = diff_t.index(max(diff_t))
                        del_vec.append(smart_vec[diff_idx])
                        del smart_vec[diff_idx]
                    if del_vec:
                        log_lines.append("removed %s for %s: %s" % (logging_tools.get_plural("value", len(del_vec)),
                                                                    key,
                                                                    ", ".join(["%s" % (get_float_str(x)) for x in del_vec])))
                    val_dict["%s_smart" % (key)] = sum(smart_vec)/float(len(smart_vec))
                my_vector = device_vector(upd_timestamp, "meta", self.get_adv_version(), [val_dict.get(key, "U") for key in self.__act_refs])
                if self.get_loc_config()["VERBOSE"]:
                    self.log("metadevice info: %s, %s" % (logging_tools.get_plural("source device", len(self.__child_vectors.keys())),
                                                          logging_tools.compress_list(self.__child_vectors.keys())))
                # cache vector for this metadevice
                self.cache_rrd_vector([my_vector])
                for r_key in remove_keys:
                    del self.__child_vectors[r_key]
            else:
                self.log("no child vectors defined", logging_tools.LOG_LEVEL_WARN)
            self.release_change_lock()
    def register_child_rrd(self, child_name):
        if child_name not in self.__meta_dev_childs:
            self.__meta_dev_childs.append(child_name)
            self.__meta_dev_childs.sort()
            self.log("Child '%s' added to child_rrd_list (now %s in list: %s)" % (child_name,
                                                                                  logging_tools.get_plural("child", len(self.__meta_dev_childs)),
                                                                                  logging_tools.compress_list(self.__meta_dev_childs)))
    
    def is_child_rrd_known(self, child_name):
        return child_name in self.__meta_dev_childs
    def set_child_mapping(self, child_name, md_mapping):
        if child_name in self.__meta_dev_childs:
            self.acquire_change_lock()
            self.log("ccm(): mapping from %s to %s for %s" % (child_name,
                                                              self.name,
                                                              logging_tools.get_plural("key", len(md_mapping.keys()))))
            self.__child_mappings[child_name] = md_mapping
            if self.__child_vectors.has_key(child_name):
                del self.__child_vectors[child_name]
            self.release_change_lock()
        else:
            self.log("Child '%s' called create_child_mapping() but unknown to me" % (child_name), logging_tools.LOG_LEVEL_WARN)
    def rrd_cache_size(self):
        return self.__num_vectors, self.__num_slots
    def save_rrd_cache(self):
        # saves rrd_cache to disk
        num_vecs = len(self.__rrd_vectors)
        if num_vecs:
            s_time = time.time()
            # vectors to store, vectors to delete
            store_vectors, delete_vectors = ([], [])
            last_vec_time = 0
            for vec in self.__rrd_vectors:
                if vec.recv_time > last_vec_time and vec.vector_version == self.get_adv_version():
                    last_vec_time = vec.recv_time
                    store_vectors.append(vec)
                else:
                    if vec.vector_version != self.get_adv_version():
                        delete_vectors.append(("version", vec))
                    else:
                        delete_vectors.append(("time", vec))
            if delete_vectors:
                self.log("Removing %s from store list: %s" % (logging_tools.get_plural("vector", len(delete_vectors)),
                                                              ", ".join(["%s (%s)" % (get_time_str(vec.recv_time), cause) for cause, vec in delete_vectors])),
                         logging_tools.LOG_LEVEL_WARN)
                delete_vectors = []
            if store_vectors:
                num_store_vecs = len(store_vectors)
                first_vec = get_time_str(int(float(store_vectors[0].recv_time)))
                last_vec = get_time_str(int(float(store_vectors[-1].recv_time)))
                if num_store_vecs == 1:
                    rrd_vec_info_str = "%d rrd_vector (from %s)" % (num_store_vecs,
                                                                    first_vec)
                else:
                    rrd_vec_info_str = "%d rrd_vectors (first from %s, last from %s, step is %s)" % (num_store_vecs,
                                                                                                     first_vec,
                                                                                                     last_vec,
                                                                                                     logging_tools.get_diff_time_str((store_vectors[-1].recv_time - store_vectors[0].recv_time) / (num_store_vecs - 1)))
                store_dict = {}
                for store_vec in store_vectors:
                    for value, rrd_data in zip(store_vec.vector, self.rrd_update_list):
                        if rrd_data:
                            store_dict.setdefault(rrd_data, []).append("%s:%s" % (store_vec.recv_time, str(value)))
                # data gathering end_time
                ge_time = time.time()
                if self.save_vectors:
                    for rrd_data, upd_list in store_dict.iteritems():
                        rrd_data.store_values(upd_list)
                    e_time = time.time()
                    self.log("saving of %s successful (%s, gathering: %s, saving: %s)" % (rrd_vec_info_str,
                                                                                          logging_tools.get_plural("rrd_data", len(store_dict.keys())),
                                                                                          logging_tools.get_diff_time_str(ge_time - s_time),
                                                                                          logging_tools.get_diff_time_str(e_time - ge_time)))
                else:
                    self.log("handling of %s successful (%s, gathering: %s)" % (rrd_vec_info_str,
                                                                                logging_tools.get_plural("rrd_data", len(store_dict.keys())),
                                                                                logging_tools.get_diff_time_str(ge_time - s_time)))
##                 else:
##                     self.log("RRD-Database not found, forcing rebuild of datafile")
##                     self.create_rrd_database(dc, force = True)
            else:
                e_time = time.time()
                self.log("No vectors to store (took %s) ..." % (logging_tools.get_diff_time_str(e_time - s_time)))
            self.init_rrd_cache()
        return num_vecs
    def get_ip_list(self):
        return self.ip_list
    def set_ip_list(self, ipl):
        old_ip_list = [x for x in self.ip_list]
        self.ip_list = ipl
        for old_ip in [ip for ip in old_ip_list if ip not in ipl]:
            del self.get_ad_struct()[old_ip]
        for new_ip in [ip for ip in ipl if ip not in old_ip_list]:
            self.get_ad_struct()[new_ip] = self
    def get_ip(self):
        if self.ip_list:
            return self.ip_list[0]
        else:
            return None
    def init_rrd(self):
        # deepcopy of last refs
        self.__saved_refs = []
        self.init_meta_device()
    def init_meta_device(self):
        # child vectors (only valid for meta-device)
        self.__child_vectors = {}
        self.__last_cv_update = time.time()
        self.__meta_dev_childs = []
        self.__child_mappings = {}
    def get_rrd_set_index(self):
        return self.__rrd_set_index
    def init_mapping(self):
        # rrd_set_index (index of rrd-database entry)
        self.__rrd_set_index = 0
        # rrd data structs, key -> rrd_data type
        self.rrd_data = {}
        # actual rrd-mapping
        # mapping-vector from snmp-mib to rrd-vector
        self.__rrd_snmp_mapping_dict = {}
        # event dictionary
        self.rrd_event_dict = {}
        # actual refs
        self.__act_refs = []
        # dict of active events (descr=>index)
        self.active_event_dict = {}
    def has_normal_rrd_sources(self):
        # returns 1 of the rrd-device has some none-snmp datasources
        return self.__has_normal_rrd_sources
    def acquire_change_lock(self):
        # lock change(write)_lock
        l_s_time = time.time()
        self.__change_lock.acquire()
        self.__data_lock_possible = False
        diff_time = abs(time.time() - l_s_time)
        if diff_time > 1:
            self.log("Waited for change_lock for %s" % (logging_tools.get_diff_time_str(diff_time)),
                     logging_tools.LOG_LEVEL_WARN)
    def release_change_lock(self):
        # unlock change_lock
        self.__data_lock_possible = True
        self.__change_lock.release()
    def acquire_data_lock(self):
        # lock data_lock
        l_s_time = time.time()
        while not self.__data_lock_possible:
            # ugly
            time.sleep(2)
        self.__data_lock_num += 1
        diff_time = abs(time.time() - l_s_time)
        if diff_time > 1:
            self.log("Waited for data_lock for %s" % (logging_tools.get_diff_time_str(diff_time)),
                     logging_tools.LOG_LEVEL_WARN)
    def release_data_lock(self):
        # unlock data_lock
        self.__data_lock_num -= 1
##     def delete_rrd_data(self, what, cc):
##         self.acquire_change_lock()
##         log_str = None
##         del_ok = 0
##         if what not in self.__act_refs:
##             # only delete it if it's not in use right now
##             try:
##                 done = cc.execute("DELETE FROM rrd_data WHERE rrd_index=%d AND rrd_set=%d" % (self.rrd_data[what].get_rrd_index(), self.__rrd_set_index))
##             except:
##                 ret_str = "mysql problem"
##             else:
##                 if done:
##                     if what in self.rrd_data.keys():
##                         ret_str = "OK deleted"
##                         del_ok = 1
##                         del self.rrd_data[what]
##                         if self.rrd_reverse_index_mapping.has_key(what):
##                             del self.rrd_reverse_index_mapping[what]
##                         if self.rrd_event_dict.has_key(what):
##                             del self.rrd_event_dict[what]
##                     else:
##                         ret_str = "key %s not known (?)" % (what)
##                 else:
##                     ret_str = "executing sql delete"
##         else:
##             ret_str = "key in use"
##         if del_ok:
##             log_str = "Succesfully deleted %s" % (what)
##         else:
##             log_str = "cannot delete %s because %s" % (what, ret_str)
##         self.release_change_lock()
##         return del_ok, ret_str, log_str
    def load_rrd_info(self, dc, in_dict=None):
        self.acquire_change_lock()
        self.init_mapping()
        # load rrd-data sets from database
        self.log("load_rrd_info() for device %s (index %d), %s" % (self.name, self.dev_idx, in_dict and "in_dict present" or "no in_dict"))
        if in_dict is not None:
            idx = (in_dict.keys() + [0])[0]
        else:
            dc.execute("SELECT rs.rrd_set_idx FROM rrd_set rs WHERE rs.device=%d" % (self.dev_idx))
            if dc.rowcount:
                idx = dc.fetchone().values()[0]
            else:
                idx = 0
        if idx:
            self.__rrd_set_index = idx
            if in_dict is not None:
                self.log("found %d saved rrd-data info (source: in_dict)" % (len(in_dict[idx])))
                set_list = in_dict[idx]
            else:
                dc.execute("SELECT rd.*, ccl.* FROM rrd_data rd LEFT JOIN ccl_event ccl ON ccl.rrd_data=rd.rrd_data_idx WHERE rd.rrd_set=%d ORDER BY rd.descr" % (self.__rrd_set_index))
                self.log("found %d saved rrd-data info (source: DB)" % (dc.rowcount))
                set_list = dc.fetchall()
            keys_found = 0
            first_rrd = True
            for set_p in set_list:
                descr = set_p["descr"]
                if not self.rrd_data.has_key(descr):
                    keys_found += 1
                    new_rrd_data = rrd_data(self, descr, set_p["rrd_data_idx"])
                    self.rrd_data[descr] = new_rrd_data
                    for key in ["info", "unit", "base", "factor", "var_type"]:
                        new_rrd_data[key] = set_p[key]
                    new_rrd_data.set_from_snmp(set_p["from_snmp"])
                    if self.get_loc_config()["VERBOSE"] > 1:
                        self.log("found %s" % (new_rrd_data.get_db_info_str()))
                    if in_dict:
                        for idx, ev_set in set_p["events"].iteritems():
                            print "EVENT"
                            self.rrd_event_dict.setdefault(descr, {})[idx] = trace_var(descr, ev_set, dc, self.get_log_queue(), self, self.rrd_data[descr]["info"])
                    new_rrd_data.create_rrd_database(self.rrd_dir, self.act_rrd_class, check_for_changes=first_rrd)
                if in_dict is None:
                    if set_p["ccl_event_idx"]:
                        self.rrd_event_dict.setdefault(descr, {})[set_p["ccl_event_idx"]] = trace_var(descr, set_p, dc, self.get_log_queue(), self, self.rrd_data[descr]["info"])
                first_rrd = False
            self.log("found %s" % (logging_tools.get_plural("key", keys_found)))
            self.load_snmp_stuff(dc)
            self.set_rrd_mapping(dc, None)
            self.set_meta_dev_descr(dc)
        else:
            self.log("No rrd_set found for device")
        self.release_change_lock()
    def set_cluster_events(self, new_ev_dict, dc):
        self.acquire_change_lock()
        # build list of present and new events
        act_event_list, new_event_list = ([], [])
        for descr, ev_stuff in self.rrd_event_dict.iteritems():
            act_event_list.extend([(descr, ev) for ev in ev_stuff.keys()])
        for descr, ev_stuff in new_ev_dict.iteritems():
            new_event_list.extend([(descr, ev) for ev in ev_stuff.keys()])
        if act_event_list or new_event_list:
            events_to_add = [x for x in new_event_list if x not in act_event_list]
            events_to_remove = [x for x in act_event_list if x not in new_event_list]
            events_to_refresh = [x for x in act_event_list if x in new_event_list]
            self.log("SCE: %s to add, %s to remove, %s to refresh" % (logging_tools.get_plural("event", events_to_add),
                                                                      logging_tools.get_plural("event", events_to_remove),
                                                                      logging_tools.get_plural("event", events_to_refresh)))
            for descr, idx in events_to_add:
                self.rrd_event_dict.setdefault(descr, {})[idx] = trace_var(descr, new_ev_dict[descr][idx], dc, self.get_log_queue(), self, self.rrd_data.get(descr, {"info" : "not set"})["info"])
            for descr, idx in events_to_remove:
                self.rrd_event_dict[descr][idx].close()
                del self.rrd_event_dict[descr][idx]
            for descr, idx in events_to_refresh:
                self.rrd_event_dict[descr][idx].refresh(new_ev_dict[descr][idx])
                self.rrd_event_dict[descr][idx].get_event_info(dc)
        self._map_active_events(dc)
        self.release_change_lock()
    def load_snmp_stuff(self, cc):
        sql_str = "SELECT s.* FROM device d INNER JOIN device_config dc INNER JOIN new_config c INNER JOIN snmp_config cs INNER JOIN snmp_mib s INNER JOIN device_group dg " + \
                  "LEFT JOIN device d2 ON d2.device_idx=dg.device WHERE d.device_group=dg.device_group_idx AND dc.new_config=c.new_config_idx AND " + \
                  "(dc.device=d.device_idx OR dc.device=d2.device_idx) AND cs.new_config=c.new_config_idx AND cs.snmp_mib=s.snmp_mib_idx AND d.name='%s'" % (self.name)
        cc.execute(sql_str)
        # performance can be improved by taking into account that the snmp-info is group by device.name
        for snmp_stuff in cc.fetchall():
            #print snmp_stuff
            self.log("adding SNMP-mib %s (rrd_key %s, name %s, description %s)" % (snmp_stuff["mib"], snmp_stuff["rrd_key"], snmp_stuff["name"], snmp_stuff["descr"]))
            self.add_mib(snmp_stuff["name"], snmp_stuff["mib"], snmp_stuff["rrd_key"], snmp_stuff["descr"], snmp_stuff["factor"])
            if snmp_stuff["var_type"] == "i":
                def_val = 0
            else:
                def_val = 0.
            self.sync_rrd_info_insert(cc, snmp_stuff["rrd_key"], snmp_stuff["descr"], 1, snmp_stuff["base"], snmp_stuff["factor"], snmp_stuff["unit"], def_val)
    def sync_rrd_info_insert(self, dc, key, info, from_snmp=False, base=1, factor=1., unit="", def_value=0):
        # inserts the new rrd-data
        key_p = (key.split(".") + ["", "", "", ""])[0:4]
        # expand info-string
        r_info = info
        for idx in range(len(key_p)):
            r_info = r_info.replace("$%d" % (idx + 1), key_p[idx])
        loc_dict = {"info"     : r_info,
                    "unit"     : unit,
                    "base"     : base,
                    "factor"   : factor,
                    "var_type" : {type(0)   : "i",
                                  type(0L)  : "i",
                                  type(0.0) : "f"}[type(def_value)]}
        # key already present ?
        if not self.rrd_data.has_key(key):
            new_rrd_data = rrd_data(self, key, 0)
            self.rrd_data[key] = new_rrd_data
            new_rrd_data.update(loc_dict)
##             for k, v in loc_dict.iteritems():
##                 new_rrd_data[k] = v
            new_rrd_data.set_from_snmp(from_snmp)
            self.rrd_event_dict[key] = {}
            # get rrd-index [in rrd_vector] for new key
            sql_tuple = tuple([self.__rrd_set_index,
                               key] +
                              key_p +
                              [unit,
                               r_info,
                               from_snmp,
                               base,
                               factor,
                               loc_dict["var_type"]])
            sql_str = "INSERT INTO rrd_data VALUES(0%s, null)" % (", %s" * len(sql_tuple))
            dc.execute(sql_str, sql_tuple)
            new_rrd_data.set_rrd_data_index(int(dc.insert_id()))
            new_rrd_data.create_rrd_database(self.rrd_dir, self.act_rrd_class)
            self.log("inserted %s" % (new_rrd_data.get_db_info_str()))
        else:
            for sub_key in ["info", "unit", "base", "factor", "var_type"]:
                if self.rrd_data[key][sub_key] != loc_dict[sub_key]:
                    # update info
                    self.rrd_data[key][sub_key] = loc_dict[sub_key]
                    sql_str, sql_tuple = ("UPDATE rrd_data SET %s=%%s WHERE rrd_data_idx=%%s" % (sub_key), (loc_dict[sub_key],
                                                                                                            self.rrd_data[key].get_rrd_data_index()))
                    dc.execute(sql_str, sql_tuple)
    def set_meta_rrd_mapping(self):
        #sets act_refs for meta-device
        # increase adv-version
        self.set_adv_version(self.get_adv_version() + 1)
        self.log("bumping adv_version to %d" % (self.get_adv_version()))
        rrd_data_list, ref_list = ([], [])
        for key, rrd_data in self.rrd_data.iteritems():
            rrd_data_list.append(rrd_data)
            ref_list.append(key)
        self.__act_refs = ref_list
        self.rrd_update_list = rrd_data_list
        self.anything_to_correct = len([True for rrd_data in self.rrd_update_list if rrd_data.to_correct]) > 0
        self.active_event_dict = dict([(act_key, (self.__act_refs.index(act_key), self.rrd_event_dict[act_key].values())) for act_key in self.__act_refs if self.rrd_event_dict.has_key(act_key)])
        # clean active_event_dict
        aed_keys = []
        for key, (rrd, ev_list) in self.active_event_dict.iteritems():
            if not ev_list:
                aed_keys.append(key)
        if aed_keys:
            aed_keys.sort()
            self.log("remove %s (empty event_list): %s" % (logging_tools.get_plural("key", len(aed_keys)),
                                                           ", ".join(aed_keys)),
                     logging_tools.LOG_LEVEL_WARN)
            for aed_key in aed_keys:
                del self.active_event_dict[aed_key]
        if self.active_event_dict:
            self.log("found %s with one or more active events:" % (logging_tools.get_plural("rrd_data_set", len(self.active_event_dict.keys()))))
            for key, (rrd_idx, ev_list) in self.active_event_dict.iteritems():
                self.log("%-30s : %d (%s)" % (key, rrd_idx, logging_tools.get_plural("event", len(ev_list))))
    def set_rrd_mapping(self, cc, refs):
        # calculate the mapping of the actual machvector to the needed rrd-database-vector
        #print "rrd_mapping for device %s (%d) : : " % (self.name, len(refs)), self.dev_idx, self.rrd_name, refs
        self.log("Mapping info called %s" % (refs and "with references" or "without references"))
        self.__act_refs = []
        if refs is None:
            self.log("Using saved references (%d entries)..." % (len(self.__saved_refs)))
            refs = self.__saved_refs
        else:
            self.__saved_refs = [x for x in refs]
        #print "R : ", refs
        mib_keys = self.get_mib_keys()
        if len(refs) + len(mib_keys):
            max_len = max([len(x[0]) for x in refs + mib_keys])
        else:
            max_len = 1
        form_str_2 = "  key %%-%ds from index %%d" % (max_len)
        self.__has_normal_rrd_sources = False
        rrd_data_list = []
        found_keys_dict = {"direct" : b_mon_keys(),
                           "snmp"   : b_mon_keys()}
        for ref_key in refs:
            if self.rrd_data.has_key(ref_key):
                add_func = self.rrd_data[ref_key]
                found_keys_dict["direct"].add_key(ref_key)
                self.__has_normal_rrd_sources = True
            else:
                add_func = None
            self.__act_refs.append(ref_key)
            rrd_data_list.append(add_func)
        for mib_key in mib_keys:
            if self.rrd_data.has_key(mib_key):
                add_func = self.rrd_data[mib_key]
                found_keys_dict["snmp"].add_key(mib_key)
            else:
                add_func = None
            self.__act_refs.append(mib_key)
            rrd_data_list.append(add_func)
        #if self.name == "BRATWI-U4104":
        #    print self.__act_refs
        self.rrd_update_list = rrd_data_list
        self.anything_to_correct = len([True for rrd_data in self.rrd_update_list if rrd_data.to_correct]) > 0
        out_form = logging_tools.form_list()
        for key_type, bm_stuff in found_keys_dict.iteritems():
            # short form
            out_form.add_line(["[%s]" % (key_type), logging_tools.get_plural("key", len(bm_stuff.get_list()))])
            #for k_list in bm_stuff.get_list():
            #    out_form.add_line(["[%s]" % (key_type)] + k_list)
        for line in str(out_form).split("\n"):
            self.log(line)
    def _map_active_events(self, dc):
        # dict of descriptors one or more events are defined
        self.log("mapping active_events")
        self.active_event_dict = dict([(act_key, (self.__act_refs.index(act_key), self.rrd_event_dict[act_key].values())) for act_key in self.__act_refs if self.rrd_event_dict.has_key(act_key)])
        if self.active_event_dict:
            self.log("found %s with one or more active events:" % (logging_tools.get_plural("rrd_data_set", len(self.active_event_dict.keys()))))
            for key, (rrd_idx, ev_list) in self.active_event_dict.iteritems():
                self.log("%-30s : %d (%s)" % (key, rrd_idx, logging_tools.get_plural("event", len(ev_list))))
    def correct_rrd_vector(self, val_list):
        # correct received val_list
        if self.anything_to_correct:
            for vec in val_list:
                vec.vector = [rrd_data.correct_value(value) for value, rrd_data in zip(vec.vector, self.rrd_update_list)]
    def cache_rrd_vector(self, val_list):
        # caches an rrd_vector for the device
        act_time = time.time()
        upd_diff = abs(self.last_update - act_time)
        #print self.name, act_time, upd_diff
        if upd_diff < 0.5:
            # when the system is under heavy load this problem can oocur
            self.log("Last update only %s ago, continuing ...." % (logging_tools.get_diff_time_str(upd_diff)),
                     logging_tools.LOG_LEVEL_WARN)
        self.last_update = act_time
        for dev_vec in val_list:
            # extend with mib-values
            dev_vec.vector.extend([self.get_mib_value_by_key(mib_key) for mib_key in self.get_mib_keys()])
            # check for evecnts
            if self.active_event_dict:
                for descr, (act_idx, ev_list) in self.active_event_dict.iteritems():
                    act_value = dev_vec.vector[act_idx]
                    for ev_stuff in ev_list:
                        ev_stuff.add_value(act_value, dev_vec.recv_time)
        self.acquire_change_lock()
        # adds a vector to the device
        act_time = time.time()
        if val_list:
            self.__rrd_vectors.extend(val_list)
            self.__num_vectors += len(val_list)
            self.__num_slots += sum([len(x.vector) for x in val_list])
            if self.__meta_dev:
                self.__meta_dev.save_child_vector(self, val_list[-1])
            self.set_lv_tt(val_list[-1].recv_time, val_list[-1].recv_type)
        if len(self.__rrd_vectors) > self.__max_cache_size or act_time > self.rrd_cache_init + self.__max_cache_time or act_time < self.rrd_cache_init:
            self.save_rrd_cache()
        self.release_change_lock()
    def create_rrd_database(self, dc, act_rrd_classes, force=False):
        self.acquire_change_lock()
        dc.execute("SELECT d.rrd_class FROM device d WHERE d.device_idx=%d" % (self.dev_idx))
        rrd_class = dc.fetchone()["rrd_class"]
        if rrd_class in act_rrd_classes.keys():
            self.log("actual rrd_class %d is valid (%s)" % (rrd_class,
                                                            act_rrd_classes[rrd_class]["name"]))
        else:
            if act_rrd_classes:
                rrd_class = act_rrd_classes.keys()[0]
                self.log("No rrd-class set, using %s as class (index %d)" % (act_rrd_classes[rrd_class]["name"],
                                                                             rrd_class))
                dc.execute("UPDATE device SET rrd_class=%d WHERE device_idx=%d" % (rrd_class, self.dev_idx))
            else:
                self.log("No rrd-classes defined, ERROR!!!", glob=True)
                rrd_class = 0
        if rrd_class:
            self.act_rrd_class = act_rrd_classes[rrd_class]
            self.act_rrd_class_idx = rrd_class
            tot_rows = sum([x["rows"] for x in self.act_rrd_class["rras"].values()], 0)
            self.log("Actual rrd-class consists of %s (%s)" % (logging_tools.get_plural("rra", len(self.act_rrd_class["rras"].keys())),
                                                               logging_tools.get_plural("row", tot_rows)))
        rebuild = force
        new_local_name = "%s.rrd" % (self.name)
        rrd_root_dir = self.get_glob_config()["RRD_DIR"]
        if not os.path.exists(rrd_root_dir):
            self.log("creating rrd-dir %s" % (rrd_root_dir))
            os.makedirs(rrd_root_dir)
        self.rrd_dir = "%s/%s" % (self.get_glob_config()["RRD_DIR"],
                                  new_local_name)
        self.log("rrd_dir set to %s" % (self.rrd_dir))
        if self.device_type == "MD":
            old_child_rrds = sorted([x for x in self.__meta_dev_childs])
        dc.execute("SELECT rs.filename, rs.rrd_set_idx FROM rrd_set rs, device d WHERE rs.device=d.device_idx AND d.name='%s'" % (self.name))
        if dc.rowcount:
            mr = dc.fetchone()
            # we have to rebuild if....
            if new_local_name != mr["filename"]:
                # the name of the device has changed
                self.log("Name of rrd_set basedirectory has changed (from %s to %s), forcing rebuild..." % (mr["filename"],
                                                                                                            new_local_name),
                         logging_tools.LOG_LEVEL_WARN)
                rebuild = True
            else:
                # no database-file can be found
                if not os.path.isdir(self.rrd_dir):
                    self.log("rrd-dir %s not found, force rebuild" % (self.rrd_dir),
                             logging_tools.LOG_LEVEL_WARN)
                    rebuild = True
                else:
                    # no rebuild necessary
                    self.init_meta_device()
        else:
            mr = None
            rebuild = True
        if rebuild:
            self.init_rrd_cache()
            self.init_mapping()
            self.init_rrd()
            if mr:
                self.log("Removing old db-entries")
                # clear old database-entries
                dc.execute("DELETE FROM rrd_data WHERE rrd_set=%d" % (mr["rrd_set_idx"]))
                dc.execute("DELETE FROM rrd_set WHERE rrd_set_idx=%d" % (mr["rrd_set_idx"]))
            if rrd_class:
                act_class = act_rrd_classes[rrd_class]
                self.init_meta_device()
                dc.execute("INSERT into rrd_set VALUES(0, %s, %s, null)", (self.dev_idx,
                                                                           new_local_name))
                self.__rrd_set_index = dc.insert_id()
                if not os.path.isdir(self.rrd_dir):
                    if os.path.isfile(self.rrd_dir):
                        self.log("removing old file %s" % (self.rrd_dir), logging_tools.LOG_LEVEL_WARN)
                        try:
                            os.unlink(self.rrd_dir)
                        except:
                            self.log("error removing file %s: %s" % (self.rrd_dir, process_tools.get_except_info()),
                                     logging_tools.LOG_LEVEL_CRITICAL)
                    self.log("Creating rrd-directory %s" % (self.rrd_dir))
                    os.makedirs(self.rrd_dir)
                if os.path.isdir(self.rrd_dir):
                    files_rem, dirs_rem = (0, 0)
                    for dir_path, dir_names, file_names in os.walk(self.rrd_dir, False):
                        for full_name in ["%s/%s" % (dir_path, file_name) for file_name in file_names]:
                            try:
                                os.unlink(full_name)
                            except:
                                self.log("error removing file %s: %s" % (full_name, process_tools.get_except_info()),
                                         logging_tools.LOG_LEVEL_CRITICAL)
                            else:
                                files_rem += 1
                        for full_name in ["%s/%s" % (dir_path, dir_name) for dir_name in dir_names]:
                            try:
                                os.rmdir(full_name)
                            except:
                                self.log("error removing dir %s: %s" % (full_name, process_tools.get_except_info()),
                                         logging_tools.LOG_LEVEL_CRITICAL)
                            else:
                                dirs_rem += 1
                    self.log("removed %s, %s under directory %s" % (logging_tools.get_plural("file", files_rem),
                                                                    logging_tools.get_plural("directory", dirs_rem),
                                                                    self.rrd_dir))
        self.release_change_lock()
        return rebuild
    
class netbotz(rrd_device):
    def __init__(self, name, lipl, idx, ad_struct, dev_type):
        rrd_device.__init__(self, name, lipl, idx, ad_struct, dev_type)
        # picture dir
        self.__pic_dir = "%s/%s" % (self.get_glob_config()["NB_PIC_DIR"], self.ip_list[0])
        # actual picture file
        self.__pic_file = "%s/actual" % (self.__pic_dir)
        self.init_hash_array()
        self.__del_day = -1
        self.__first_call = True
        self.set_adv_version(0)
    def get_adv_version(self):
        return self.__adv_version
    def set_adv_version(self, adv):
        self.__adv_version = adv
    def init_hash_array(self):
        # Hash array
        self.hash_array = ""
    def _first_call(self, dc):
        path_re = re.compile("^%s/(?P<year>\d+)/(?P<month>\d+)/(?P<day>\d+)/(?P<hour>\d+)/(?P<minute>\d+)_(?P<second>\d+)\.jpg$" % (self.__pic_dir))
        self.__first_call = False
        self.log("First call, searching for pictures not in the database")
        dc.execute("SELECT path FROM netbotz_picture WHERE device=%d" % (self.dev_idx))
        found_paths = [x["path"] for x in dc.fetchall()]
        pics_added = 0
        for dir_path, dir_names, file_names in os.walk(self.__pic_dir):
            for fn in ["%s/%s" % (dir_path, x) for x in file_names if x.endswith(".jpg")]:
                fn_match = path_re.match(fn)
                if fn not in found_paths and fn_match:
                    pics_added += 1
                    dc.execute("INSERT INTO netbotz_picture SET device=%s, %s, path=%%s" % (self.dev_idx,
                                                                                            ", ".join(["%s=%d" % (x, int(fn_match.group(x))) for x in ["year", "month", "day", "hour", "minute", "second"]])), (fn))
        self.log("Added %s to database" % (logging_tools.get_plural("picture", pics_added)))
    def _check_for_delete(self, dc, netbotz_time):
        self.__del_day = netbotz_time[2]
        # delete old pictures every day at 20:00
        del_time = time.time() - 3600 * 24 * self.get_glob_config()["NETBOTZ_PICTURE_KEEP_DAYS"]
        self.log("Deleting old pictures")
        dir_del_ok = True
        while dir_del_ok:
            del_dirs = []
            for dir_path, dir_names, file_names in os.walk(self.__pic_dir):
                if not file_names and not dir_names:
                    del_dirs.append(dir_path)
                for fn in ["%s/%s" % (dir_path, x) for x in file_names if x.endswith(".jpg")]:
                    if os.path.getmtime(fn) - del_time < 0:
                        os.unlink(fn)
            dir_del_ok = False
            dirs_removed = []
            for del_dir in del_dirs:
                try:
                    os.rmdir(del_dir)
                except:
                    self.log("*** error removing dir '%s': %s" % (del_dir,
                                                                  process_tools.get_except_info()),
                             logging_tools.LOG_LEVEL_ERROR)
                else:
                    dirs_removed.append(del_dir)
                    dir_del_ok = True
            if dirs_removed:
                self.log("Removed %s: %s" % (logging_tools.get_plural("directory", len(dirs_removed)),
                                             ", ".join(dirs_removed)))
        dc.execute("DELETE FROM netbotz_picture WHERE ABS(UNIX_TIMESTAMP(date) - UNIX_TIMESTAMP()) > %d" % (3600 * 24 * self.get_glob_config()["NETBOTZ_PICTURE_KEEP_DAYS"]))
    def feed_line(self, args, files):
        netbotz_time = time.localtime(int(args["BOTZTIME"]))
        num_sensors = int(args["NUMSENSORS"])
        log_str = "connect, %s, %s" % (logging_tools.get_plural("sensor", num_sensors),
                                       logging_tools.get_plural("picture", len(files.keys())))
        self.log(log_str)
        # copy actual image to data-dir
        dc = self.get_db_con().get_connection(SQL_ACCESS)
        if self.__first_call:
            self._first_call(dc)
        if netbotz_time[3] == 20 and netbotz_time[2] != self.__del_day:
            self._check_for_delete(dc, netbotz_time)
        fname = "%02d_%02d.jpg" % (netbotz_time[4], netbotz_time[5])
        fdir = "%s/%04d/%02d/%02d/%02d" % (self.__pic_dir, netbotz_time[0], netbotz_time[1], netbotz_time[2], netbotz_time[3])
        if not os.path.exists(fdir):
            try:
                os.makedirs(fdir)
            except:
                self.log("Error creating dir %s: %s" % (fdir,
                                                        process_tools.get_except_info()),
                         logging_tools.LOG_LEVEL_ERROR)
            else:
                self.log("Creating dir %s" % (fdir))
        targ_file = "%s/%s" % (fdir, fname)
        if files:
            file_content = files.values()[0][1]
            try:
                file(targ_file, "w").write(file_content)
            except:
                self.log("error writing file to %s: %s" % (targ_file,
                                                           process_tools.get_except_info()),
                         logging_tools.LOG_LEVEL_ERROR)
            else:
                if os.path.isfile(targ_file):
                    os.chmod(targ_file, 0644)
                    dc.execute("INSERT INTO netbotz_picture SET device=%s, %s, path=%%s" % (self.dev_idx,
                                                                                            ", ".join(["%s=%d" % (x, y) for x, y in zip(["year", "month", "day", "hour", "minute", "second"],
                                                                                                                                        netbotz_time[0:6])])), (targ_file))
                else:
                    self.log("file '%s' not found (NB-Picture)" % (targ_file),
                             logging_tools.LOG_LEVEL_ERROR)
        else:
            self.log("no picture provided", logging_tools.LOG_LEVEL_WARN)
        # parse parts
        valid_sensor_types = ["TEMP", "HUMI", "AFLW"]
        valid_sensor_nums = [num for num in range(num_sensors) if args["SENSORTYPE_%d" % (num)] in valid_sensor_types]
        act_mvect, ref_list, dev_vector = ({}, [], [])
        for vsn in valid_sensor_nums:
            s_name = args["SENSORTYPE_%d" % (vsn)].lower()
            s_name = {"aflw" : "flow",
                      "humi" : "hum"}.get(s_name, s_name)
            act_mvect[s_name] = {"info"  : args["SENSORLABEL_%d" % (vsn)],
                                 "value" : float(args["SENSORVALUE_%d" % (vsn)].lower()),
                                 "units" : args["SENSORVALUEUNITS_%d" % (vsn)],
                                 "descr" : args["SENSORTYPE_%d" % (vsn)]}
            dev_vector.append(act_mvect[s_name]["value"])
            ref_list.append(s_name)
        act_hash_array = [x for x in ref_list]
        if act_hash_array != self.hash_array:
            self.log("hash_array has changed")
            self.acquire_change_lock()
            self.hash_array = act_hash_array
            for key in act_mvect.keys():
                self.sync_rrd_info_insert(dc,
                                          key,
                                          act_mvect[key]["info"])
            self.set_rrd_mapping(dc, ref_list)
            self.set_meta_dev_descr(dc)
            self.release_change_lock()
        dc.release()
        # cache vector for netbotz drops
        self.cache_rrd_vector([device_vector(time.time(), "loc", 0, dev_vector)])
        
class machine(rrd_device):
    def __init__(self, name, lipl, idx, ad_struct, dev_type):
        rrd_device.__init__(self, name, lipl, idx, ad_struct, dev_type)
        self.set_adv_version()
        self.set_adv_cache()
        self.__adv_lock = threading.Lock()
        self.__open_coms, self.__num_waiting_for_coms = ({}, 0)
    def get_adv_lock(self):
        act_time = time.time()
        la = self.__adv_lock.acquire(0)
        if la:
            self.__adv_lock_time = act_time
        else:
            if abs(self.__adv_lock_time - act_time) > self.get_glob_config()["ADV_LOCK_TIMEOUT"]:
                self.log("deleting adv_lock (timeout)")
                self.release_adv_lock("timeout")
                la = self.__adv_lock.acquire(0)
        return la
    def release_adv_lock(self, cause):
        self.log("release adv_lock cause: %s" % (cause))
        self.__adv_lock.release()
    def get_adv_version(self):
        return self.__adv_version
    def set_adv_version(self, vers=-1):
        self.__adv_version, self.__adv_valid = (vers, False)
    def set_adv_cache(self, vector_list=None):
        self.__adv_cache = vector_list
    def _release_adv_cache(self):
        if self.__adv_cache:
            self._add_to_cache(self.__adv_cache)
        self.__adv_cache = None
        self.release_adv_lock("success %s" % (self.name))
        self.__adv_valid = True
    def _decode_devcom_result(self, in_data):
        if in_data.startswith("ok "):
            try:
                version, mvect = process_tools.net_to_sys(in_data[3:])
            except:
                self.log("Error decoding devcom_result (len %d): %s" % (len(in_data),
                                                                        process_tools.get_except_info()),
                         logging_tools.LOG_LEVEL_ERROR)
                version, mvect = (None, None)
        else:
            self.log("devcom_result starts with '%s' ('ok ' needed)" % (in_data[0:3]),
                     logging_tools.LOG_LEVEL_ERROR)
            version, mvect = (None, None)
        return version, mvect
    def _decode_data(self, in_data, in_class):
        recv_list, mv_type = (None, 2)
        if in_data.startswith("ok "):
            try:
                recv_list = process_tools.net_to_sys(in_data[3:])
            except:
                recv_list = None
        # header for compressed vectors
        elif in_data.startswith("cok "):
            if bz2:
                try:
                    recv_decr = bz2.decompress(in_data[4:])
                except:
                    self.log("Error decompressing DeviceVector (length %d): %s" % (len(in_data),
                                                                                   process_tools.get_except_info()),
                             logging_tools.LOG_LEVEL_ERROR)
                else:
                    try:
                        recv_list = process_tools.net_to_sys(recv_decr)
                    except:
                        self.log("Error unpickling decompressed DeviceVector (length %d): %s" % (len(recv_decr),
                                                                                                 process_tools.get_except_info()),
                                 logging_tools.LOG_LEVEL_ERROR)
                        recv_list = None
            else:
                self.log("No bz2-lib for decompressing bz2-compressed DeviceVector (length %d): %s" % (len(in_data),
                                                                                                       process_tools.get_except_info()),
                         logging_tools.LOG_LEVEL_ERROR)
        if recv_list:
            recv_list = [device_vector(x, in_class, y, z) for x, y, z in recv_list]
        else:
            sparts = in_data.split(":")
            try:
                act_vers = int(sparts.pop(0))
            except ValueError:
                self.log("Cannot parse DeviceVector (length %d): %s, tried old and new version..." % (len(in_data),
                                                                                                      process_tools.get_except_info()),
                         logging_tools.LOG_LEVEL_ERROR)
                #print "ERROR", recv, len(recv), recv, name, source_ip
            else:
                recv_list = [device_vector(time.time(), in_class, act_vers, sparts)]
                mv_type = 1
        return recv_list, mv_type
    def feed_line(self, source_ip, in_data, in_class, net_server, target_queue):
        if self.__open_coms:
            self.__num_waiting_for_coms += 1
            if self.__num_waiting_for_coms > 20:
                self.log("Waited too long for subcommands to finish (%s, iteration %d), clearing open_coms" % (", ".join(self.__open_coms.keys()),
                                                                                                               self.__num_waiting_for_coms),
                         logging_tools.LOG_LEVEL_ERROR)
                self.__open_coms, self.__num_waiting_for_coms = ({}, 0)
            else:
                self.log("Still waiting for subcommands to finish (%s, iteration %d)" % (", ".join(self.__open_coms.keys()),
                                                                                         self.__num_waiting_for_coms),
                         logging_tools.LOG_LEVEL_WARN)
        else:
            #print name, self.adv_valid, self.adv_vers
            # determine version
            recv_list, mv_type = self._decode_data(in_data, in_class)
            if recv_list:
                # all_vers is a list of all versions
                all_vers = [x.vector_version for x in recv_list]
                highest_version = max(all_vers)
                if all_vers.count(highest_version) != len(all_vers):
                    self.log("the %s had different versions: %s" % (logging_tools.get_plural("received device-vector", len(all_vers)),
                                                                    ",".join(["%d" % (x) for x in all_vers])),
                             logging_tools.LOG_LEVEL_WARN)
                    old_len = len(recv_list)
                    recv_list = [x for x in recv_list if x.vector_version == highest_version]
                    self.log("dumping %s (of %d)" % (logging_tools.get_plural("device vector", old_len - len(recv_list)),
                                                     old_len),
                             logging_tools.LOG_LEVEL_WARN)
                if not self.__adv_valid or (self.get_adv_version() != highest_version):
                    # invalid version, we have to reconnect
                    if net_server:
                        if self.get_adv_lock():
                            self.set_adv_cache(recv_list)
                            self.set_adv_version(highest_version)
                            self.log("Reconnect to device to learn about DeviceVector Version %d (type %d)" % (highest_version, mv_type))
                            if mv_type == 2:
                                com_list = ["get_mvector"]
                            else:
                                com_list = ["get_mvect_ref", "get_mvect_info"]
                            self.__open_coms = dict([(com, None) for com in com_list])
                            for com in com_list:
                                net_server.add_object(net_tools.tcp_con_object(self._new_tcp_con,
                                                                               connect_state_call = self._connect_state_call,
                                                                               connect_timeout_call = self._connect_timeout,
                                                                               target_host = source_ip,
                                                                               target_port = self.get_glob_config()["COLLSERVER_PORT"],
                                                                               timeout = 20,
                                                                               bind_retries = 1,
                                                                               rebind_wait_time = 1,
                                                                               add_data = (com, self, target_queue)))
                        else:
                            self.log("adv_lock still active (strange...)",
                                     logging_tools.LOG_LEVEL_WARN)
                    else:
                        self.log("No net-server set, skipping request", logging_tools.LOG_LEVEL_WARN)
                else:
                    self._add_to_cache(recv_list)
    def _add_to_cache(self, recv_list):
        self.correct_rrd_vector(recv_list)
        # cache vector for connections from hosts
        self.cache_rrd_vector(recv_list)
    def _connect_state_call(self, **args):
        if args["state"] == "error":
            dev_com, dev_struct, target_queue = args["socket"].get_add_data()
            self.log("error connecting (command %s)" % (dev_com), logging_tools.LOG_LEVEL_ERROR)
            args["socket"].delete()
    def _connect_timeout(self, sock):
        dev_com, dev_struct, target_queue = sock.get_add_data()
        self.log("timeout while connecting (command %s)" % (dev_com), logging_tools.LOG_LEVEL_ERROR)
        sock.delete()
        sock.close()
    def _new_tcp_con(self, sock):
        return node_con_obj(self, sock.get_target_host(), sock.get_add_data())
    def _result_error(self, dev_com, flag, what, collect_queue):
        self.log("Error (%d): %s for command %s" % (flag, what, dev_com), logging_tools.LOG_LEVEL_ERROR)
        if self.__open_coms.has_key(dev_com):
            self.__open_coms[dev_com] = "error %s (%d)" % (what, flag)
            self._check_for_finished_coms(dev_com, collect_queue)
        else:
            self.log("Got error answer for unknown dev_com %s" % (dev_com),
                     logging_tools.LOG_LEVEL_ERROR)
    def _result_ok(self, dev_com, in_data, collect_queue):
        if self.__open_coms.has_key(dev_com):
            dec_version, dec_data = self._decode_devcom_result(in_data)
            if dec_version is None:
                pass
            else:
                self.log("got valid answer for %s" % (dev_com))
                self.__open_coms[dev_com] = (dec_version, dec_data)
            self._check_for_finished_coms(dev_com, collect_queue)
        else:
            self.log("Got answer for unknown dev_com %s" % (dev_com),
                     logging_tools.LOG_LEVEL_ERROR)
    def _check_for_finished_coms(self, dev_com, collect_queue):
        waiting_coms = [k for k, v in self.__open_coms.iteritems() if v is None]
        if waiting_coms:
            self.log("Still waiting for %s: %s" % (logging_tools.get_plural("device command", len(waiting_coms)),
                                                   ", ".join(waiting_coms)))
        else:
            # check for errors
            error_coms = sorted([k for k, v in self.__open_coms.iteritems() if type(v) == type("")])
            if error_coms:
                self.log("%s returned with error: %s" % (logging_tools.get_plural("command", len(error_coms)),
                                                         ", ".join(error_coms)),
                         logging_tools.LOG_LEVEL_ERROR)
                self.release_adv_lock("connection problem")
            else:
                if dev_com == "get_mvector":
                    m_version, m_vect = self.__open_coms[dev_com]
                else:
                    # FIXME
                    self.log("do not know how to handle mv_type 1 answers",
                             logging_tools.LOG_LEVEL_CRITICAL)
                    m_version = None
                if m_version is not None:
                    if m_version == self.get_adv_version():
                        self._decode_device_commands(m_version, m_vect, collect_queue)
                    else:
                        self.log("Received machvector has a wrong Version number (%d != %d)" % (m_version,
                                                                                                self.get_adv_version()),
                                 logging_tools.LOG_LEVEL_ERROR)
                        self.release_adv_lock("version problem")
            # clear open_device commands
            self.__open_coms = {}
    def _decode_device_commands(self, m_version, m_vector, collect_queue):
        self.acquire_change_lock()
        mv_keys = [x[0] for x in m_vector]
        self.log("Received correct machvector Version %d (%s)" % (m_version,
                                                                  logging_tools.get_plural("key", len(mv_keys))))
        m_vector = dict(m_vector)
        dc = self.get_db_con().get_connection(SQL_ACCESS)
        for mv_key in mv_keys:
            info_p = m_vector[mv_key]["i"]
            self.sync_rrd_info_insert(dc,
                                      mv_key,
                                      m_vector[mv_key]["i"],
                                      False,
                                      m_vector[mv_key].get("b", 1),
                                      m_vector[mv_key].get("f", 1.),
                                      m_vector[mv_key].get("u", ""),
                                      m_vector[mv_key].get("v", 0))
        self.set_rrd_mapping(dc, mv_keys)
        self.set_meta_dev_descr(dc)
        dc.release()
        self.release_change_lock()
        collect_queue.put(("release_adv_cache", (self)))

class meta_device(rrd_device):
    def __init__(self, name, cdg, idx, ad_struct, dev_type):
        rrd_device.__init__(self, name, [], idx, ad_struct, dev_type)
        self.cdg_flag = cdg
        if self.cdg_flag:
            self.log("*** cluster_device_group (CDG) ***")
        self.set_adv_version(0)
    def get_adv_version(self):
        return self.__adv_version
    def set_adv_version(self, adv):
        self.__adv_version = adv
    def is_cdg(self):
        return self.cdg_flag
    def is_meta_device(self):
        return True
        
def get_ip_lists(dc, devices, all_netdevs):
    sql_str = "SELECT DISTINCT d.name, i.ip, i.alias, i.alias_excl, nw.network_idx, n.netdevice_idx, n.devname, nt.identifier, nw.name AS domain_name, nw.postfix, nw.short_names, h.value FROM " + \
              "device d, netip i, netdevice n, network nw, network_type nt, hopcount h WHERE nt.network_type_idx=nw.network_type AND i.network=nw.network_idx AND " + \
              "n.device=d.device_idx AND i.netdevice=n.netdevice_idx AND n.netdevice_idx=h.s_netdevice AND (%s) AND (%s) ORDER BY h.value, d.name" % (" OR ".join(["h.d_netdevice=%d" % (x) for x in all_netdevs]),
                                                                                                                                                      " OR ".join(["d.name='%s'" % (x) for x in devices]))
    dc.execute(sql_str)
    return dc.fetchall()

class logging_thread(threading_tools.thread_obj):
    def __init__(self, glob_config, loc_config):
        self.__sep_str = "-" * 50
        self.__glob_config, self.__loc_config = (glob_config, loc_config)
        self.__machlogs, self.__glob_log, self.__glob_cache = ({}, None, [])
        threading_tools.thread_obj.__init__(self, "logging", queue_size=500, priority=10)
        self.register_func("log", self._log)
        self.register_func("mach_log", self._mach_log)
        self.register_func("set_ad_struct", self._set_ad_struct)
        self.register_func("set_queue_dict", self._set_queue_dict)
        self.register_func("update", self._update)
        self.register_func("delay_request", self._delay_request)
        self.register_func("remove_handle", self._remove_handle)
        self.__ad_struct = {}
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
        self.__queue_dict = q_dict
    def loop_end(self):
        for mach in self.__machlogs.keys():
            self.__machlogs[mach].write("Closing log")
            self.__machlogs[mach].close()
        self.__glob_log.write("Closed %s" % (logging_tools.get_plural("machine log", len(self.__machlogs.keys()))))
        self.__glob_log.write("Closing log")
        self.__glob_log.write("logging thread exiting (pid %d)" % (self.pid))
        self.send_pool_message(("remove_pid", (self.name, self.pid)))
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
    def __init__(self, dev_struct):
        self.__dev_struct = dev_struct
        self.__ticket_num = 0
        self.set_community, self.get_community = ("private", "public")
        # FIXME
        self.__pending = {}
        self.__start_time = time.time()
        self.__sets, self.__gets = ([], [])
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__dev_struct.log(what, lev)
    def add_set(self, dst, set_list):
        self.__sets.append((dst, set_list))
    def add_get(self, dst, get_list):
        self.__gets.append((dst, get_list))
    def init_send(self, acg):
        for dst, set_list in self.__sets:
            self.__ticket_num += 1
            try:
                # FIXME
                acg.asyncSetCmd(cmdgen.CommunityData("localhost", self.set_community, 0),
                                cmdgen.UdpTransportTarget(("%s" % (dst), 161)), 
                                tuple(set_list),
                                (self.get_set_recv, self.__ticket_num))
            except (socket.gaierror, socket.error):
                self.log("error sending SNMP set command: %s" % (process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
                self.__pending[self.__ticket_num] = snmp_result("send_set_error")
            else:
                self.log("sent %s (community %s)" % (logging_tools.get_plural("set", len(set_list)),
                                                     self.set_community))
                self.__pending[self.__ticket_num] = snmp_result()
        for dst, get_list in self.__gets:
            self.__ticket_num += 1
            try:
                # FIXME
                acg.asyncGetCmd(cmdgen.CommunityData("localhost", self.get_community, 0),
                                cmdgen.UdpTransportTarget((dst, 161)), 
                                tuple(get_list),
                                (self.get_set_recv, self.__ticket_num))
            except (socket.gaierror, socket.error):
                self.log("error sending SNMP get command: %s" % (process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
                self.__pending[self.__ticket_num] = snmp_result("send_get_error")
            else:
                self.log("sent %s (community %s)" % (logging_tools.get_plural("get", len(get_list)),
                                                     self.get_community))
                self.__pending[self.__ticket_num] = snmp_result()
        self._check_change()
    def get_set_recv(self, send_request_handle, error_indication, error_status, error_index, var_list, tick_num):
        if error_indication:
            if error_indication.lower() == "requesttimedout":
                # timeout
                self.log("deleting request with ticket_num %d" % (tick_num))
                self.__pending[tick_num].set_error("timeout error", error_indication)
            else:
                print error_indication, type(error_indication)
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
            
            for tick_stuff in sum([self.__pending[key].var_list for key in act_dict["o"]], []):
                if type(tick_stuff) == type(()):
                    tick_stuff = [tick_stuff]
                for oid, value in tick_stuff:
                    try:
                        self.__dev_struct.set_mib(oid, float(str(value)))
                    except:
                        self.log("cannot cast '%s' to float: %s" % (str(value), process_tools.get_except_info()),
                                 logging_tools.LOG_LEVEL_ERROR)
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
    def _set_queue_dict(self, q_dict):
        self.__queue_dict = q_dict
    def _init_acg(self):
        self.log("init AsynCommandGenerator")
        self.__acg = cmdgen.AsynCommandGenerator()
    def _new_snmp_batch(self, snmp_batch):
        self.log("init new snmp_batch")
        snmp_batch.init_send(self.__acg)
    def loop_end(self):
        self.send_pool_message(("remove_pid", (self.name, self.pid)))
    def _busy_loop(self):
        if self.__acg and self.__acg.snmpEngine.transportDispatcher:
            if self.__is_asleep:
                self.__is_asleep = False
            if self.__acg.snmpEngine.transportDispatcher.jobsArePending():
                self.log("transportDispatcher valid and jobs pending, starting dispatcher")
                try:
                    self.__acg.snmpEngine.transportDispatcher.runDispatcher(20.0)
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
        else:
            if not self.__is_asleep:
                self.__is_asleep = True
                self.log("transportDispatcher not valid, enter sleep mode")
        if self.__is_asleep:
            mes_list = self.inner_loop(True)

class snmp_update_thread(threading_tools.thread_obj):
    def __init__(self, glob_config, loc_config, db_con, log_queue):
        self.__db_con = db_con
        self.__log_queue = log_queue
        self.__glob_config, self.__loc_config = (glob_config, loc_config)
        threading_tools.thread_obj.__init__(self, "snmp_update", queue_size=100)
        self.register_func("set_queue_dict", self._set_queue_dict)
        self.register_func("update", self._update)
        self.register_func("set_ad_struct", self._set_ad_struct)
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__log_queue.put(("log", (self.name, what, lev)))
    def thread_running(self):
        self.send_pool_message(("new_pid", (self.name, self.pid)))
    def loop_end(self):
        self.send_pool_message(("remove_pid", (self.name, self.pid)))
    def _set_queue_dict(self, q_dict):
        self.__queue_dict = q_dict
    def _set_ad_struct(self, ad_struct):
        self.log("got ad_struct")
        self.__ad_struct = ad_struct
    def _update(self):
        dc = self.__db_con.get_connection(SQL_ACCESS)
        devs_to_check = [x for x in self.__ad_struct.keys(True) if self.__ad_struct[x].mibs_defined() and self.__ad_struct[x].need_snmp_update()]
        if devs_to_check:
            self.log("sending snmp_update request to %s: %s" % (logging_tools.get_plural("device", len(devs_to_check)),
                                                                logging_tools.compress_list(devs_to_check)))
            for dev in devs_to_check:
                act_dev = self.__ad_struct[dev]
                act_dev.invalidate_illegal_mibs()
                if (act_dev.num_updates and not act_dev.has_normal_rrd_sources()) and act_dev.num_valid_mibs():
                    # cache vector SNMP-only devices
                    act_dev.cache_rrd_vector([device_vector(act_dev.last_snmp_update, "snmp", act_dev.get_adv_version(), [])])
                act_dev.update_start()
                if not act_dev.is_meta_device():
                    new_batch = snmp_batch_class(act_dev)
                    new_batch.add_get(act_dev.get_ip(), act_dev.get_defined_mibs())
                    self.__queue_dict["snmp_send_queue"].put(("new_snmp_batch", new_batch))
        for devg_to_flush in self.__ad_struct.get_device_group_keys(True):
            self.__ad_struct[devg_to_flush].flush_metadevice_vectors(dc)
        dc.release()

class report_thread(threading_tools.thread_obj):
    def __init__(self, glob_config, loc_config, db_con, log_queue):
        self.__db_con = db_con
        self.__log_queue = log_queue
        self.__glob_config, self.__loc_config = (glob_config, loc_config)
        threading_tools.thread_obj.__init__(self, "report", queue_size=100)
        self.register_func("set_queue_dict", self._set_queue_dict)
        self.register_func("set_ad_struct", self._set_ad_struct)
        self.register_func("report_latest_max_min_average", self._report_lmma)
        self.register_func("draw_graphs", self._draw_graphs)
        self.__net_server = None
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__log_queue.put(("log", (self.name, what, lev)))
    def _set_ad_struct(self, ad_struct):
        self.log("got ad_struct")
        self.__ad_struct = ad_struct
    def _set_queue_dict(self, q_dict):
        self.__queue_dict = q_dict
    def thread_running(self):
        self.send_pool_message(("new_pid", (self.name, self.pid)))
    def loop_end(self):
        self.send_pool_message(("remove_pid", (self.name, self.pid)))
    def _report_lmma(self, (node_res, report_devs, s_com, tcp_obj)):
        opt_dict = s_com.get_option_dict()
        needed_rrds = opt_dict["rrds"]
        start_time, end_time = (opt_dict["start_time"],
                                opt_dict["end_time"])
        report_start_time = time.time()
        self.log("fetching latest/max/min/average for %s on %s: %s" % (logging_tools.get_plural("rrd_data", len(needed_rrds)),
                                                                       logging_tools.get_plural("device", len(report_devs)),
                                                                       logging_tools.compress_list(report_devs)))
        dev_rep_dict = {}
        for report_dev in report_devs:
            dev_struct = self.__ad_struct[report_dev]
            dev_rep_dict[dev_struct.name] = {}
            dev_struct.acquire_data_lock()
            fetch_rrds = []
            for needed_rrd in needed_rrds:
                if dev_struct.rrd_data.has_key(needed_rrd):
                    fetch_rrds.append(needed_rrd)
                    #dev_rep_dict[dev_struct.name][needed_rrd] = (1, 2, 3)
                else:
                    dev_rep_dict[dev_struct.name][needed_rrd] = "error not present"
            if fetch_rrds:
                rrd_graph_args = ["/dev/null",
                                  "-s",
                                  "-%d" % (start_time * 60),
                                  "-e", "-%d" % (end_time * 60)]
                act_idx = 0
                for fetch_rrd in fetch_rrds:
                    act_rrd_data = dev_struct.rrd_data[fetch_rrd]
                    act_idx += 1
                    # Minimum part
                    rrd_graph_args.extend(["DEF:min%d=%s:v0:MIN" % (act_idx, act_rrd_data.full_path),
                                           "VDEF:d%dmin=min%d,MINIMUM" % (act_idx, act_idx),
                                           "PRINT:d%dmin:min\:%s\:%%14.6le" % (act_idx, fetch_rrd)])
                    # Maximum part
                    rrd_graph_args.extend(["DEF:max%d=%s:v0:MAX" % (act_idx, act_rrd_data.full_path),
                                           "VDEF:d%dmax=max%d,MAXIMUM" % (act_idx, act_idx),
                                           "PRINT:d%dmax:max\:%s\:%%14.6le" % (act_idx, fetch_rrd)])
                    # Average part
                    rrd_graph_args.extend(["DEF:av%d=%s:v0:AVERAGE" % (act_idx, act_rrd_data.full_path),
                                           "VDEF:d%dav=av%d,AVERAGE" % (act_idx, act_idx),
                                           "PRINT:d%dav:average\:%s\:%%14.6le" % (act_idx, fetch_rrd)])
                    # Last part
                    rrd_graph_args.extend(["VDEF:d%dlast=av%d,LAST" % (act_idx, act_idx),
                                           "PRINT:d%dlast:last\:%s\:%%14.6le" % (act_idx, fetch_rrd)])
                #print rrd_graph_args
                try:
                    rrd_res = rrdtool.graph(*rrd_graph_args)
                except:
                    dev_struct.log("Error fetching graph info: %s" % (process_tools.get_except_info()),
                                   logging_tools.LOG_LEVEL_ERROR)
                    for fetch_rrd in fetch_rrds:
                        dev_rep_dict[dev_struct.name][fetch_rrds] = "error fetching"
                else:
                    size_x, size_y, out_list = rrd_res
                    for f_type, fetch_rrd, value_str in [x.split(":") for x in out_list]:
                        if value_str.strip().lower() == "nan":
                            value = "nan"
                        else:
                            try:
                                value = float(value_str)
                            except:
                                value = None
                        dev_rep_dict[dev_struct.name].setdefault(fetch_rrd, {})[f_type] = value
                        #print "\n".join(out_list)
            dev_struct.release_data_lock()
        report_end_time = time.time()
        self.log("fetching on %s took %s" % (logging_tools.get_plural("device", len(report_devs)),
                                             logging_tools.get_diff_time_str(report_end_time - report_start_time)))
        tcp_obj.add_to_out_buffer(server_command.server_reply(state = server_command.SRV_REPLY_STATE_OK,
                                                              result = "ok fetched",
                                                              node_results = node_res,
                                                              node_dicts = dev_rep_dict))
    def _draw_graphs(self, (node_res, report_devs, s_com, tcp_obj)):
        opt_dict = s_com.get_option_dict()
        needed_rrds = opt_dict["rrds"]
        start_time, end_time = (opt_dict["start_time"],
                                opt_dict["end_time"])
        graph_width, graph_height = (opt_dict["width"],
                                     opt_dict["height"])
        draw_start_time = time.time()
        rrd_options = opt_dict["rrd_options"]
        rrd_compounds = opt_dict["rrd_compounds"]
        self.log("drawing graphs for %s on %s: %s" % (logging_tools.get_plural("rrd_data", len(needed_rrds)),
                                                      logging_tools.get_plural("device", len(report_devs)),
                                                      logging_tools.compress_list(report_devs)))
        compound_results = {}
        g_idx = 0
        for comp_name in rrd_compounds["compound_list"]:
            compound_results[comp_name] = {}
            comp_list = rrd_compounds[comp_name]
            g_idx += 1
            #print comp_name, comp_list
            dev_rep_dict = {}
            for report_dev in report_devs:
                dev_struct = self.__ad_struct[report_dev]
                dev_rep_dict[dev_struct.name] = {}
                dev_struct.acquire_data_lock()
                fetch_rrds = []
                for needed_rrd in comp_list:
                    if dev_struct.rrd_data.has_key(needed_rrd):
                        fetch_rrds.append(needed_rrd)
                        #dev_rep_dict[dev_struct.name][needed_rrd] = (1, 2, 3)
                    else:
                        dev_rep_dict[dev_struct.name][needed_rrd] = "error not present"
                if fetch_rrds:
                    dev_options = opt_dict.get("device_options", {}).get(dev_struct.get_real_name(), {})
                    #print dev_struct.get_name(), dev_options
                    graph_file_name = "%s/graph_%d" % (self.__glob_config["RRD_DIR"], g_idx)
                    abs_start_time = time.localtime(time.time() - start_time * 60)
                    abs_end_time = time.localtime(time.time() - end_time * 60)
                    start_form_str = "%a, %d. %b %Y %H:%M:%S"
                    if abs_start_time[0:3] == abs_end_time[0:3]:
                        end_form_str = "%H:%M:%S"
                    elif abs_start_time[0] == abs_end_time[0]:
                        end_form_str = "%a, %d. %b %H:%M:%S"
                    else:
                        end_form_str = "%a, %d. %b %Y %H:%M:%S"
                    rrd_graph_args = [graph_file_name,
                                      "-t %s on %s (from %s to %s)" % (comp_name,
                                                                       dev_struct.get_name(),
                                                                       time.strftime(start_form_str, abs_start_time),
                                                                       time.strftime(end_form_str, abs_end_time)),
                                      "-s -%d" % (start_time * 60),
                                      "-e -%d" % (end_time * 60),
                                      "-E",
                                      "-w %d" % (graph_width),
                                      "-h %d" % (graph_height),
                                      "-W init.at Clustersoftware",
                                      "-c",
                                      "BACK#ffffff"]
                    if dev_options:
                        # draw hbars
                        if dev_options.has_key("hbars"):
                            check_keys = [x for x in dev_options["hbars"].keys() if x in comp_list]
                            hbar_list = sum([dev_options["hbars"][ck] for ck in check_keys], [])
                            if hbar_list:
                                for act_pri in sorted(set([(x["pri"]) for x in hbar_list]).keys()):
                                    for draw_hbar in [x for x in hbar_list if x["pri"] == act_pri]:
                                        if draw_hbar.has_key("upper"):
                                            rrd_graph_args.extend(["LINE0:%.7f#%s" % (draw_hbar["lower"],
                                                                                      draw_hbar["color"]),
                                                                   "AREA:%.7f#%s::STACK" % (draw_hbar["upper"] - draw_hbar["lower"],
                                                                                            draw_hbar["color"])])
                                            if draw_hbar.get("outline", False):
                                                rrd_graph_args.extend(["LINE1:%.7f#000000" % (draw_hbar["lower"]),
                                                                       "LINE1:%.7f#000000" % (draw_hbar["upper"])])
                                        else:
                                            rrd_graph_args.extend(["HRULE:%.7f#%s" % (draw_hbar["lower"],
                                                                                      draw_hbar["color"])])
                    # get longest descr
                    max_descr_len = 0
                    for draw_mode in ["AREAOUTLINE", "AREA", "LINE3", "LINE2", "LINE1"]:
                        for fetch_rrd in fetch_rrds:
                            rrd_option = rrd_options[fetch_rrd]
                            if not rrd_option.has_key("descr"):
                                rrd_option["descr"] = fetch_rrd
                            if rrd_option["mode"] == draw_mode:
                                for mma in ["min", "average", "max"]:
                                    if rrd_option[mma]:
                                        max_descr_len = max(max_descr_len, len(rrd_option["descr"]) + len(mma) + 3)
                    act_idx = 0
                    for draw_mode in ["AREAOUTLINE", "AREA", "LINE3", "LINE2", "LINE1"]:
                        for fetch_rrd in fetch_rrds:
                            rrd_option = rrd_options[fetch_rrd]
                            if not rrd_option.has_key("descr"):
                                rrd_option["descr"] = fetch_rrd
                            if rrd_option["mode"] == draw_mode:
                                act_rrd_data = dev_struct.rrd_data[fetch_rrd]
                                act_idx += 1
                                # Minimum part
                                for mma in ["min", "average", "max"]:
                                    if rrd_option[mma]:
                                        rrd_graph_args.extend(self._create_draw_args(act_idx, act_rrd_data.full_path, rrd_option, mma, max_descr_len))
                    if dev_options:
                        # draw vrules
                        if dev_options.has_key("vrules"):
                            # build legend dict
                            l_dict = {}
                            for vr_time, vr_options in dev_options["vrules"].iteritems():
                                act_text = vr_options.get("text", "")
                                if act_text:
                                    if l_dict.has_key(act_text):
                                        l_dict[act_text] += 1
                                    else:
                                        l_dict[act_text] = 1
                            for text in l_dict.keys():
                                if l_dict[text] > 1:
                                    l_dict[text] = "%s (x %d)" % (text, l_dict[text])
                                else:
                                    l_dict[text] = text
                            for vr_time, vr_options in dev_options["vrules"].iteritems():
                                act_text = vr_options.get("text", "")
                                if act_text and l_dict.has_key(act_text):
                                    print_text = l_dict[act_text]
                                    del l_dict[act_text]
                                    act_text = print_text
                                else:
                                    act_text = ""
                                rrd_graph_args.append("VRULE:%d#%s%s" % (vr_time,
                                                                         vr_options.get("color", "000000"),
                                                                         act_text and ":%s" % (act_text) or ""))
                    #print " ".join(rrd_graph_args)
                    #print rrd_graph_args
                    draw_time_start = time.time()
                    try:
                        rrd_res = rrdtool.graph(*rrd_graph_args)
                    except:
                        dev_struct.log("Error fetching graph info: %s" % (process_tools.get_except_info()),
                                       logging_tools.LOG_LEVEL_ERROR)
                        for fetch_rrd in fetch_rrds:
                            for fetch_rrd in fetch_rrds:
                                dev_rep_dict[dev_struct.name][fetch_rrd] = "error drawing"
                    else:
                        draw_time_end = time.time()
                        dev_struct.log("Creating the graph in %s resulted in %s" % (logging_tools.get_diff_time_str(draw_time_end - draw_time_start),
                                                                                    str(rrd_res)))
                        compound_results[comp_name][dev_struct.name] = file(graph_file_name, "r").read()
                dev_struct.release_data_lock()
        draw_end_time = time.time()
        self.log("fetching on %s took %s" % (logging_tools.get_plural("device", len(report_devs)),
                                             logging_tools.get_diff_time_str(draw_end_time - draw_start_time)))
        tcp_obj.add_to_out_buffer(server_command.server_reply(state = server_command.SRV_REPLY_STATE_OK,
                                                              result = "ok drawn",
                                                              node_results = node_res,
                                                              option_dict = compound_results),
                                  "draw_graph")
    def _create_draw_args(self, act_idx, full_path, rrd_option, mma, max_len):
        mma_short = {"average" : "aver"}.get(mma, mma)
        act_color = rrd_option["color"]
        if mma in ["min", "max"]:
            # modify colors for min/max
            hue, lev, sat = colorsys.rgb_to_hls(*[float(int(x, 16)) / 256. for x in [act_color[0:2], act_color[2:4], act_color[4:]]])
            if mma == "min":
                hue -= 0.1
            else:
                hue += 0.1
            act_color = "".join(["%02x" % (x * 255) for x in list(colorsys.hls_to_rgb(max(min(hue, 1), 0), lev, sat))])
        act_dat_name = "%s%d" % (mma, act_idx)
        ret_f = ["DEF:%s=%s:v0:%s" % (act_dat_name,
                                      full_path,
                                      mma.upper())]
        if full_path.count("/net/"):
            # cap Network readings above  1 GB/s to zero
            new_dat_name = "n%s" % (act_dat_name)
            if full_path.count("/eth"):
                cap_val = 120000000
            else:
                cap_val = 1000000000
            ret_f.extend(["CDEF:%s=%d,%s,GT,%s,PREV,IF" % (new_dat_name,
                                                           cap_val,
                                                           act_dat_name,
                                                           act_dat_name)])
            act_dat_name = new_dat_name
        report_names = {"max"  : "%smax" % (act_dat_name),
                        "min"  : "%smin" % (act_dat_name),
                        "ave"  : "%save" % (act_dat_name),
                        "last" : "%slast" % (act_dat_name)}
        ret_f.extend(["VDEF:%s=%s,MAXIMUM" % (report_names["max"],
                                              act_dat_name),
                      "VDEF:%s=%s,MINIMUM" % (report_names["min"],
                                              act_dat_name),
                      "VDEF:%s=%s,AVERAGE" % (report_names["ave"],
                                              act_dat_name),
                      "VDEF:%s=%s,LAST" % (report_names["last"],
                                           act_dat_name)])
        if rrd_option.get("invert", False):
            new_dat_name = "i%s" % (act_dat_name)
            ret_f.extend(["CDEF:%s=-1,%s,*" % (new_dat_name,
                                               act_dat_name)])
            act_dat_name = new_dat_name
        smooth_minutes = rrd_option.get("smooth", 0)
        if smooth_minutes:
            new_dat_name = "s%s" % (act_dat_name)
            ret_f.extend(["CDEF:%s=%s,%d,TREND" % (new_dat_name,
                                                   act_dat_name,
                                                   smooth_minutes * 60)])
            act_dat_name = new_dat_name
        act_mode = rrd_option["mode"]
        if act_mode == "AREAOUTLINE":
            ret_f.extend(["%s:%s#%s:%s" % ("AREA",
                                           act_dat_name,
                                           act_color,
                                           ("%%-%ds" % (max_len)) % ("%s (%s)" % (rrd_option["descr"], mma_short))),
                          "%s:%s#%s" % ("LINE1",
                                        act_dat_name,
                                        "000000")])
        else:
            ret_f.extend(["%s:%s#%s:%s" % (rrd_option["mode"],
                                           act_dat_name,
                                           act_color,
                                           ("%%-%ds" % (max_len)) % ("%s (%s)" % (rrd_option["descr"], mma_short)))])
        ret_f.extend(["GPRINT:%s:max %%6.1lf%%s" % (report_names["max"]),
                      "GPRINT:%s:min %%6.1lf%%s" % (report_names["min"]),
                      "GPRINT:%s:average %%6.1lf%%s" % (report_names["ave"]),
                      "GPRINT:%s:last %%6.1lf%%s\l" % (report_names["last"])])
        return ret_f

class command_thread(threading_tools.thread_obj):
    def __init__(self, glob_config, loc_config, db_con, log_queue):
        self.__db_con = db_con
        self.__log_queue = log_queue
        self.__glob_config, self.__loc_config = (glob_config, loc_config)
        threading_tools.thread_obj.__init__(self, "command", queue_size=100)
        self.register_func("set_queue_dict", self._set_queue_dict)
        self.register_func("set_ad_struct", self._set_ad_struct)
        self.register_func("com_con", self._com_con)
        self.register_func("set_net_stuff", self._set_net_stuff)
        self.__net_server = None
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__log_queue.put(("log", (self.name, what, lev)))
    def _set_ad_struct(self, ad_struct):
        self.log("got ad_struct")
        self.__ad_struct = ad_struct
    def thread_running(self):
        self.send_pool_message(("new_pid", (self.name, self.pid)))
    def loop_end(self):
        self.send_pool_message(("remove_pid", (self.name, self.pid)))
    def _set_queue_dict(self, q_dict):
        self.__queue_dict = q_dict
    def _set_net_stuff(self, (net_server)):
        self.log("Got net_server")
        self.__net_server = net_server
    def _com_con(self, tcp_obj):
        in_data = tcp_obj.get_decoded_in_str()
        try:
            server_com = server_command.server_command(in_data)
        except:
            tcp_obj.add_to_out_buffer("error no valid server_command")
            self.log("Got invalid data from host %s (port %d): %s" % (tcp_obj.get_src_host(),
                                                                      tcp_obj.get_src_port(),
                                                                      in_data[0:20]),
                     logging_tools.LOG_LEVEL_WARN)
        else:
            srv_com_name = server_com.get_command()
            call_func = {"status"                : self._status,
                         "device_status"         : self._device_status,
                         "device_flush"          : self._device_flush,
                         "netbotz_drop"          : self._netbotz_drop,
                         "report_lmma"           : self._report_latest_max_min_average,
                         "reload_cluster_events" : self._reload_cluster_events,
                         "check_device_settings" : self._check_device_settings,
                         "draw_graphs"           : self._draw_graphs}.get(srv_com_name, None)
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
    def _status(self, tcp_obj, s_com):
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
    def _reload_cluster_events(self, tcp_obj, s_com):
        tcp_obj.add_to_out_buffer(server_command.server_reply(state = server_command.SRV_REPLY_STATE_OK,
                                                              result = "ok reloading cluster_events"),
                                  "reload_cluster_events ok")
        self.__queue_dict["collect_queues"][0].put("reload_cluster_events")
    def _get_node_res_dict(self, node_names, ok_str):
        node_res, ok_nodes = ({}, [])
        for node_name in node_names:
            if self.__ad_struct.has_key(node_name):
                node_res[node_name] = "ok %s" % (ok_str)
                ok_nodes.append(node_name)
            else:
                node_res[node_name] = "error not found"
        return node_res, ok_nodes
    def _check_device_settings(self, tcp_obj, s_com):
        node_res, check_devs = self._get_node_res_dict(s_com.get_nodes(), "settings checked")
        if check_devs:
            self.__queue_dict["collect_queues"][0].put(("check_devices", check_devs))
        tcp_obj.add_to_out_buffer(server_command.server_reply(state = server_command.SRV_REPLY_STATE_OK,
                                                              result = "ok checked device_settings",
                                                              node_results = node_res),
                                  "device_settings checked for %s" % (logging_tools.get_plural("device", len(check_devs))))
    def _device_status(self, tcp_obj, s_com):
        node_res, ok_nodes = self._get_node_res_dict(s_com.get_nodes(), "is rrd_client")
        node_dicts = dict([(node_name, self.__ad_struct[node_name].get_lv_tt()) for node_name in ok_nodes])
        tcp_obj.add_to_out_buffer(server_command.server_reply(state = server_command.SRV_REPLY_STATE_OK,
                                                              result = "ok checked status",
                                                              node_results = node_res,
                                                              node_dicts = node_dicts),
                                  "device_status result for %s" % (logging_tools.get_plural("device", len(ok_nodes))))
    def _device_flush(self, tcp_obj, s_com):
        node_res, flush_devs = self._get_node_res_dict(s_com.get_nodes(), "flush started")
        if flush_devs and self.__loc_config["CACHING"]:
            self.__queue_dict["collect_queues"][0].put(("flush_devices", flush_devs))
        tcp_obj.add_to_out_buffer(server_command.server_reply(state = server_command.SRV_REPLY_STATE_OK,
                                                              result = "ok flushed",
                                                              node_results = node_res))
    def _report_latest_max_min_average(self, tcp_obj, s_com):
        node_res, rep_devs = self._get_node_res_dict(s_com.get_nodes(), "")
        if self.__loc_config["CACHING"]:
            self.__queue_dict["collect_queues"][0].put(("flush_devices", rep_devs))
        self.__queue_dict["report_queue"].put(("report_latest_max_min_average", (node_res, rep_devs, s_com, tcp_obj)))
    def _draw_graphs(self, tcp_obj, s_com):
        node_res, rep_devs = self._get_node_res_dict(s_com.get_nodes(), "")
        if self.__loc_config["CACHING"]:
            self.__queue_dict["collect_queues"][0].put(("flush_devices", rep_devs))
        self.__queue_dict["report_queue"].put(("draw_graphs", (node_res, rep_devs, s_com, tcp_obj)))
    def _netbotz_drop(self, tcp_obj, s_com):
        self.__queue_dict["collect_queues"][0].put(("netbotz_drop", s_com.get_option_dict()))
        tcp_obj.add_to_out_buffer(server_command.server_reply(state = server_command.SRV_REPLY_STATE_OK,
                                                              result = "ok got it"),
                                  "got netbotz_drop command")

class reconnect_thread(threading_tools.thread_obj):
    def __init__(self, glob_config, loc_config, db_con, log_queue):
        self.__db_con = db_con
        self.__log_queue = log_queue
        self.__glob_config, self.__loc_config = (glob_config, loc_config)
        threading_tools.thread_obj.__init__(self, "reconnect", queue_size=100, loop_function=self._busy_loop)
        self.register_func("set_queue_dict", self._set_queue_dict)
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__log_queue.put(("log", (self.name, what, lev)))
    def loop_end(self):
        self.send_pool_message(("remove_pid", (self.name, self.pid)))
    def thread_running(self):
        self.send_pool_message(("new_pid", (self.name, self.pid)))
        self.__ns = net_tools.network_server(timeout=2, log_hook=self.log, poll_verbose=self.__loc_config["VERBOSE"] > 1)
    def _set_queue_dict(self, q_dict):
        self.__queue_dict = q_dict
        for col_queue in self.__queue_dict["collect_queues"]:
            col_queue.put(("set_net_stuff", (self.__ns)))
    def _busy_loop(self):
        self.__ns.step()
        
class dbsync_thread(threading_tools.thread_obj):
    def __init__(self, glob_config, loc_config, db_con, log_queue):
        self.__db_con = db_con
        self.__log_queue = log_queue
        self.__glob_config, self.__loc_config = (glob_config, loc_config)
        threading_tools.thread_obj.__init__(self, "dbsync", queue_size=100)
        self.register_func("set_ad_struct", self._set_ad_struct)
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__log_queue.put(("log", (self.name, what, lev)))
    def loop_end(self):
        self.send_pool_message(("remove_pid", (self.name, self.pid)))
    def thread_running(self):
        self.send_pool_message(("new_pid", (self.name, self.pid)))
    def _set_ad_struct(self, ad_struct):
        self.log("got ad_struct")
        self.__ad_struct = ad_struct
        dc = self.__db_con.get_connection(SQL_ACCESS)
        self.__ad_struct.db_sync(dc)
        dc.release()
        self.send_pool_message("db_sync_done")
        
class receiver_thread(threading_tools.thread_obj):
    def __init__(self, glob_config, loc_config, db_con, log_queue, num_collect_threads):
        self.__db_con = db_con
        self.__log_queue = log_queue
        self.__glob_config, self.__loc_config = (glob_config, loc_config)
        self.__num_collect_threads = num_collect_threads
        threading_tools.thread_obj.__init__(self, "receiver", queue_size=100, loop_function=self._busy_loop)
        self.register_func("set_queue_dict", self._set_queue_dict)
        self.register_func("init_network_connections", self._init_network_connections)
        self["exit_requested"] = False
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__log_queue.put(("log", (self.name, what, lev)))
    def loop_end(self):
        self.send_pool_message(("remove_pid", (self.name, self.pid)))
    def thread_running(self):
        self.send_pool_message(("new_pid", (self.name, self.pid)))
        self.__act_col = 0
        self.__ns = net_tools.network_server(timeout=2, log_hook=self.log, poll_verbose=self.__loc_config["VERBOSE"] > 1)
    def _set_queue_dict(self, q_dict):
        self.__queue_dict = q_dict
    def _init_network_connections(self):
        self.__ns.add_object(net_tools.tcp_bind(self._new_tcp_node_con, port=self.__glob_config["COLLECTOR_PORT"], bind_retries=5, bind_state_call=self._bind_state_call, timeout=15))
        self.__ns.add_object(net_tools.udp_bind(self._new_udp_node_con, port=self.__glob_config["COLLECTOR_PORT"], bind_retries=5, bind_state_call=self._bind_state_call, timeout=15))
    def _bind_state_call(self, **args):
        if args["state"].count("ok"):
            self.log("Bind to %s (type %s) sucessfull" % (args["port"], args["type"]))
        else:
            # FIXME
            self.log("Bind to %s (type %s) NOT sucessfull" % (args["port"], args["type"]), logging_tools.LOG_LEVEL_CRITICAL)
            self.log("unable to bind to all ports, exiting", logging_tools.LOG_LEVEL_ERROR)
            self._int_error("bind problem")
    def _new_tcp_node_con(self, sock, src):
        if self["exit_requested"]:
            return new_tcp_con_forbid("node", "tcp", src, self.__log_queue)
        else:
            if self.__num_collect_threads > 1:
                self.__act_col = (self.__act_col + 1) % self.__num_collect_threads
            return new_tcp_con("node", "tcp", None, src, self.__queue_dict["collect_queues"][self.__act_col], self.__log_queue)
    def _new_udp_node_con(self, data, src):
        if self["exit_requested"]:
            return new_tcp_con_forbid("node", "udp", src, self.__log_queue)
        else:
            if self.__num_collect_threads > 1:
                # not needed
##                 qs_dict = dict([(num, self.__queue_dict["collect_queues"][num].qsize()) for num in range(self.__num_collect_threads)])
##                 print qs_dict
                self.__act_col = (self.__act_col + 1) % self.__num_collect_threads
            return new_tcp_con("node", "udp", data, src, self.__queue_dict["collect_queues"][self.__act_col], self.__log_queue)
        #self.__bind_state[id_str] = args["state"]
    def _busy_loop(self):
        self.__ns.step()
        
class nodecon_thread(threading_tools.thread_obj):
    def __init__(self, glob_config, loc_config, db_con, log_queue, num_collect_threads):
        self.__db_con = db_con
        self.__log_queue = log_queue
        self.__glob_config, self.__loc_config = (glob_config, loc_config)
        self.__num_collect_threads = num_collect_threads
        threading_tools.thread_obj.__init__(self, "nodecon", queue_size=1000)
        self.register_func("set_queue_dict", self._set_queue_dict)
        self.register_func("set_ad_struct", self._set_ad_struct)
        self.register_func("node_ok_result", self._node_ok_result)
        self.register_func("node_error_result", self._node_error_result)
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__log_queue.put(("log", (self.name, what, lev)))
    def loop_end(self):
        self.send_pool_message(("remove_pid", (self.name, self.pid)))
    def _set_ad_struct(self, ad_struct):
        self.log("got ad_struct")
        self.__ad_struct = ad_struct
    def thread_running(self):
        self.send_pool_message(("new_pid", (self.name, self.pid)))
        self.__act_col = 0
    def _set_queue_dict(self, q_dict):
        self.__queue_dict = q_dict
    def _node_ok_result(self, (dev_struct, com, result)):
        s_time = time.time()
        dev_struct._result_ok(com, result, self.__queue_dict["collect_queues"][self.__act_col])
        if self.__num_collect_threads > 1:
            self.__act_col = (self.__act_col + 1) % self.__num_collect_threads
    def _node_error_result(self, (dev_struct, com, flag, what)):
        dev_struct._result_error(com, flag, what, self.__queue_dict["collect_queues"][self.__act_col])
        if self.__num_collect_threads > 1:
            self.__act_col = (self.__act_col + 1) % self.__num_collect_threads

class collect_thread(threading_tools.thread_obj):
    def __init__(self, glob_config, loc_config, db_con, log_queue, t_num):
        self.__db_con = db_con
        self.__log_queue = log_queue
        self.__glob_config, self.__loc_config = (glob_config, loc_config)
        self.__collect_thread_num = t_num
        threading_tools.thread_obj.__init__(self, "collect_%d" % (self.__collect_thread_num), queue_size=100)
        self.register_func("set_queue_dict", self._set_queue_dict)
        self.register_func("set_ad_struct", self._set_ad_struct)
        self.register_func("node_con", self._node_con)
        self.register_func("set_net_stuff", self._set_net_stuff)
        self.register_func("release_adv_cache", self._release_adv_cache)
        self.register_func("flush_devices", self._flush_devices)
        self.register_func("check_devices", self._check_devices)
        self.register_func("netbotz_drop", self._netbotz_drop)
        self.register_func("reload_cluster_events", self._reload_cluster_events)
        self.__net_server = None
        self.__flush_with_lock_info = False
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__log_queue.put(("log", (self.name, what, lev)))
    def _set_ad_struct(self, ad_struct):
        self.log("got ad_struct")
        self.__ad_struct = ad_struct
    def thread_running(self):
        self.send_pool_message(("new_pid", (self.name, self.pid)))
    def _set_queue_dict(self, q_dict):
        self.__queue_dict = q_dict
    def _set_net_stuff(self, (net_server)):
        self.log("Got net_server")
        self.__net_server = net_server
    def _node_con(self, in_obj):
        in_data, src_ip, in_class = (in_obj.get_decoded_in_str(),
                                     in_obj.get_src_host(),
                                     in_obj.get_con_class())
        
        if self.__ad_struct.has_key(src_ip):
            if in_class == "tcp":
                in_obj.add_to_out_buffer("ok got it")
            act_dev = self.__ad_struct[src_ip]
            if isinstance(act_dev, machine):
                f_stime = time.time()
                act_dev.feed_line(src_ip, in_data, in_class, self.__net_server, self.__queue_dict["nodecon_queue"])
                f_etime = time.time()
                if f_etime - f_stime > 1:
                    self.log("Feed_time for IP %s (device %s) is %s" % (src_ip,
                                                                        act_dev.name,
                                                                        logging_tools.get_diff_time_str(f_etime - f_stime)),
                             logging_tools.LOG_LEVEL_WARN)
            else:
                self.log("Connect from IP %s, associated device '%s' is not of type machine" % (src_ip,
                                                                                                act_dev.name),
                         logging_tools.LOG_LEVEL_ERROR)
        else:
            if in_class == "tcp":
                in_obj.add_to_out_buffer("invalid src_ip, checking database")
            self.log("Got request from invalid ip %s (class %s)" % (src_ip,
                                                                    in_class),
                     logging_tools.LOG_LEVEL_WARN)
            dc = self.__db_con.get_connection(SQL_ACCESS)
            self.__ad_struct.db_sync(dc, [src_ip])
            dc.release()
    def _reload_cluster_events(self):
        self.log("Reloading cluster_events")
        dc = self.__db_con.get_connection(SQL_ACCESS)
        self.__ad_struct._reload_cluster_events(dc)
        dc.release()
    def _netbotz_drop(self, opt_dict):
        args, files = (opt_dict["args"],
                       opt_dict["files"])
        src_ip = args["BOTZIP"]
        if self.__ad_struct.has_key(src_ip):
            act_dev = self.__ad_struct[src_ip]
            act_dev.feed_line(args, files)
        else:
            self.log("Got netbotz_drop for unknown IP-Address %s" % (src_ip),
                     logging_tools.LOG_LEVEL_ERROR)
    def _release_adv_cache(self, dev_struct):
        dev_struct._release_adv_cache()
    def _flush_devices(self, dev_names):
        num_devs = len(dev_names)
        flush_start_time = time.time()
        self.log("Flushing %s: %s" % (logging_tools.get_plural("device", num_devs),
                                      logging_tools.compress_list(dev_names)))
        idx = 0
        for name in dev_names:
            idx += 1
            dev = self.__ad_struct[name]
            s_time = time.time()
            dev.acquire_data_lock()
            num_vecs = dev.save_rrd_cache()
            dev.release_data_lock()
            e_time = time.time()
            self.log(" flushed %12s, %4d of %4d (device %s) in %s" % (logging_tools.get_plural("vector", num_vecs),
                                                                      idx,
                                                                      num_devs,
                                                                      name,
                                                                      logging_tools.get_diff_time_str(e_time - s_time)))
            if self.__flush_with_lock_info:
                file(self.__loc_config["LOCK_FILE_NAME"], "w").write("%d of %d," % (idx, num_devs))
        flush_end_time = time.time()
        self.log("Flushing %s took %s" % (logging_tools.get_plural("device", num_devs),
                                          logging_tools.get_diff_time_str(flush_end_time - flush_start_time)))
    def _check_devices(self, dev_names):
        num_devs = len(dev_names)
        check_start_time = time.time()
        dc = self.__db_con.get_connection(SQL_ACCESS)
        dc.execute("SELECT d.name, d.save_rrd_vectors, d.rrd_class FROM device d WHERE %s" % (" OR ".join(["d.name='%s'" % (name) for name in dev_names])))
        check_dict = dict([(db_rec["name"], db_rec) for db_rec in dc.fetchall()])
        new_rrd_classes = read_rrd_class_tree(dc)
        self.log("Checking %s: %s" % (logging_tools.get_plural("device", num_devs),
                                      logging_tools.compress_list(dev_names)))
        idx = 0
        for name in dev_names:
            idx += 1
            if check_dict.has_key(name):
                dev = self.__ad_struct[name]
                s_time = time.time()
                dev.acquire_change_lock()
                dev.save_vectors = check_dict[name]["save_rrd_vectors"]
                if dev.act_rrd_class_idx != check_dict[name]["rrd_class"]:
                    dev.create_rrd_database(dc, new_rrd_classes, True)
                dev.release_change_lock()
                e_time = time.time()
                self.log(" checked %4d of %4d (device %s) in %s" % (idx,
                                                                    num_devs,
                                                                    name,
                                                                    logging_tools.get_diff_time_str(e_time - s_time)))
            else:
                self.log("device %s not in check_dict, strange ..." % (name), logging_tools.LOG_LEVEL_WARN)
        check_end_time = time.time()
        dc.release()
        self.log("Checking %s took %s" % (logging_tools.get_plural("device", num_devs),
                                          logging_tools.get_diff_time_str(check_end_time - check_start_time)))
    def loop_end(self):
        dev_names = sorted(self.__ad_struct.keys(True))
        self.__flush_with_lock_info = True
        if not self.__collect_thread_num:
            self._flush_devices(dev_names)
        self.send_pool_message(("remove_pid", (self.name, self.pid)))

class server_thread_pool(threading_tools.thread_pool):
    def __init__(self, db_con, g_config, loc_config):
        self.__log_cache, self.__log_queue = ([], None)
        self.__db_con = db_con
        self.__glob_config, self.__loc_config = (g_config, loc_config)
        threading_tools.thread_pool.__init__(self, "main", blocking_loop=False)
        self.__msi_block = self._init_msi_block()
        self.register_func("new_pid", self._new_pid)
        self.register_func("remove_pid", self._remove_pid)
        self.register_func("db_sync_done", self._db_sync_done)
        self.register_exception("int_error", self._int_error)
        self.register_exception("term_error", self._int_error)
        self.__log_queue = self.add_thread(logging_thread(self.__glob_config, self.__loc_config), start_thread=True).get_thread_queue()
        #self.register_exception("hup_error", self._hup_error)
        # log config
        self._log_config()
        # prepare directories
        #self._prepare_directories()
        dc = self.__db_con.get_connection(SQL_ACCESS)
        # re-insert config
        self._re_insert_config(dc)
        # global network settings
        self._init_rrd_classes(dc)
        self._init_cluster_events(dc)
        self.__ad_struct = all_devices(self.__log_queue, self.__glob_config, self.__loc_config, self.__db_con)
        self.__log_queue.put(("set_ad_struct", self.__ad_struct))
        self.__ns = net_tools.network_server(timeout=2, log_hook=self.log, poll_verbose=self.__loc_config["VERBOSE"] > 1)
        #self._check_nfs_exports(dc)
        # start threads
        self.__collect_queues = []
        self.__num_collect_threads = self.__glob_config["NUM_COLLECT_THREADS"]
        self.__act_col = 0
        for t_num in range(0, self.__num_collect_threads):
            self.__collect_queues.append(self.add_thread(collect_thread(self.__glob_config, self.__loc_config, self.__db_con, self.__log_queue, t_num), start_thread=True).get_thread_queue())
        self.__reconnect_queue   = self.add_thread(reconnect_thread(self.__glob_config, self.__loc_config, self.__db_con, self.__log_queue), start_thread=True).get_thread_queue()
        self.__dbsync_queue      = self.add_thread(dbsync_thread(self.__glob_config, self.__loc_config, self.__db_con, self.__log_queue), start_thread=True).get_thread_queue()
        self.__receiver_queue    = self.add_thread(receiver_thread(self.__glob_config, self.__loc_config, self.__db_con, self.__log_queue, t_num), start_thread=True).get_thread_queue()
        self.__snmp_send_queue   = self.add_thread(snmp_send_thread(self.__glob_config, self.__loc_config, self.__db_con, self.__log_queue), start_thread=True).get_thread_queue()
        self.__snmp_update_queue = self.add_thread(snmp_update_thread(self.__glob_config, self.__loc_config, self.__db_con, self.__log_queue), start_thread=True).get_thread_queue()
        self.__com_queue         = self.add_thread(command_thread(self.__glob_config, self.__loc_config, self.__db_con, self.__log_queue), start_thread=True).get_thread_queue()
        self.__report_queue      = self.add_thread(report_thread(self.__glob_config, self.__loc_config, self.__db_con, self.__log_queue), start_thread=True).get_thread_queue()
        self.__nodecon_queue     = self.add_thread(nodecon_thread(self.__glob_config, self.__loc_config, self.__db_con, self.__log_queue, self.__glob_config["NUM_COLLECT_THREADS"]), start_thread=True).get_thread_queue()
        self.__dbsync_queue.put(("set_ad_struct", self.__ad_struct))
        for col_queue in self.__collect_queues:
            col_queue.put(("set_ad_struct", self.__ad_struct))
        self.__snmp_update_queue.put(("set_ad_struct", self.__ad_struct))
        self.__com_queue.put(("set_ad_struct", self.__ad_struct))
        self.__report_queue.put(("set_ad_struct", self.__ad_struct))
        self.__nodecon_queue.put(("set_ad_struct", self.__ad_struct))
        #        self._check_global_network_stuff(dc)
        self.__queue_dict = {"log_queue"         : self.__log_queue,
                             "collect_queues"    : self.__collect_queues,
                             "snmp_send_queue"   : self.__snmp_send_queue,
                             "snmp_update_queue" : self.__snmp_update_queue,
                             "command_queue"     : self.__com_queue,
                             "report_queue"      : self.__report_queue,
                             "nodecon_queue"     : self.__nodecon_queue,
                             "reconnect_queue"   : self.__reconnect_queue,
                             "receive_queue"     : self.__receiver_queue}
        self.__log_queue.put(("set_queue_dict", self.__queue_dict))
        for col_queue in self.__collect_queues:
            col_queue.put(("set_queue_dict", self.__queue_dict))
        self.__com_queue.put(("set_queue_dict", self.__queue_dict))
        self.__snmp_send_queue.put(("set_queue_dict", self.__queue_dict))
        self.__snmp_update_queue.put(("set_queue_dict", self.__queue_dict))
        self.__report_queue.put(("set_queue_dict", self.__queue_dict))
        self.__nodecon_queue.put(("set_queue_dict", self.__queue_dict))
        self.__reconnect_queue.put(("set_queue_dict", self.__queue_dict))
        self.__receiver_queue.put(("set_queue_dict", self.__queue_dict))
        self.__com_queue.put(("set_net_stuff", (self.__ns)))
        dc.release()
        # uuid log
        my_uuid = uuid_tools.get_uuid()
        self.log("cluster_device_uuid is '%s'" % (my_uuid.get_urn()))
        self.__last_update = None
    def _int_error(self, err_cause):
        if self["exit_requested"]:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            self.log("exit requested", logging_tools.LOG_LEVEL_WARN)
            self["exit_requested"] = True
            file(self.__loc_config["LOCK_FILE_NAME"], "w").write("init shutdown")
            self.__ns.set_timeout(1)
    def _new_pid(self, (thread_name, new_pid)):
        self.log("received new_pid message from thread %s" % (thread_name))
        process_tools.append_pids(self.__loc_config["PID_NAME"], new_pid)
        if self.__msi_block:
            self.__msi_block.add_actual_pid(new_pid)
            self.__msi_block.save_block()
    def _remove_pid(self, (thread_name, rem_pid)):
        self.log("received remove_pid message from thread %s" % (thread_name))
        process_tools.remove_pids(self.__loc_config["PID_NAME"], rem_pid)
        if self.__msi_block:
            self.__msi_block.remove_actual_pid(rem_pid)
            self.__msi_block.save_block()
    def _db_sync_done(self):
        self.log("db_sync finished, initialising network-connections")
        self.__ns.add_object(net_tools.tcp_bind(self._new_tcp_command_con, port=self.__glob_config["COMMAND_PORT"], bind_retries=5, bind_state_call=self._bind_state_call, timeout=60))
        self.__receiver_queue.put("init_network_connections")
    def _log_config(self):
        self.log("Config info:")
        while self.__glob_config.log_array:
            self.log(" - clf: %s" % (self.__glob_config.log_array.pop(0)))
        conf_info = self.__glob_config.get_config_info()
        self.log("Found %d valid global config-lines:" % (len(conf_info)))
        for conf in conf_info:
            self.log("Config : %s" % (conf))
        conf_info = self.__loc_config.get_config_info()
        self.log("Found %d valid local config-lines:" % (len(conf_info)))
        for conf in conf_info:
            self.log("Config : %s" % (conf))
    def _re_insert_config(self, dc):
        self.log("re-insert config")
        configfile.write_config(dc, "rrd_server", self.__glob_config)
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        if self.__log_queue:
            if self.__log_cache:
                for c_what, c_lev in self.__log_cache:
                    self.__log_queue.put(("log", (self.name, "(delayed) %s" % (c_what), c_lev)))
                self.__log_cache = []
            self.__log_queue.put(("log", (self.name, what, lev)))
        else:
            self.__log_cache.append((what, lev))
    def _check_global_network_stuff(self, dc):
        self.log("Checking global network settings")
        dc.execute("SELECT i.ip,n.netdevice_idx,nw.network_idx FROM netdevice n, netip i, network nw WHERE n.device=%d AND i.netdevice=n.netdevice_idx AND i.network=nw.network_idx" % (self.__loc_config["RRD_SERVER_IDX"]))
        glob_net_devices = {}
        for net_rec in dc.fetchall():
            n_d, n_i, n_w = (net_rec["netdevice_idx"],
                             net_rec["ip"],
                             net_rec["network_idx"])
            if not glob_net_devices.has_key(n_d):
                glob_net_devices[n_d] = []
            glob_net_devices[n_d].append((n_i, n_w))
        # get all network_device_types
        dc.execute("SELECT * FROM network_device_type")
        self.__loc_config["GLOBAL_NET_DEVICES"] = glob_net_devices
        self.__loc_config["GLOBAL_NET_DEVICE_DICT"] = dict([(x["identifier"], x["network_device_type_idx"]) for x in dc.fetchall()])
##     def _prepare_directories(self):
##         self.log("Checking directories ...")
##         for d_dir in [self.__glob_config["TFTP_DIR"], self.__glob_config["ETHERBOOT_DIR"], self.__glob_config["CONFIG_DIR"], self.__glob_config["KERNEL_DIR"]]:
##             if not os.path.isdir(d_dir):
##                 self.log("trying to create directory %s" % (d_dir))
##                 try:
##                     os.makedirs(d_dir)
##                 except:
##                     pass
##         for d_link, s_link in [(self.__glob_config["TFTP_LINK"], self.__glob_config["TFTP_DIR"])]:
##             if not os.path.islink(d_link):
##                 self.log("Trying to create link from %s to %s" % (d_link, s_link))
##                 try:
##                     os.symlink(s_link, d_link)
##                 except:
##                     pass
    def _init_msi_block(self):
        process_tools.save_pid(self.__loc_config["PID_NAME"])
        if self.__loc_config["DAEMON"]:
            self.log("Initialising meta-server-info block")
            msi_block = process_tools.meta_server_info("rrd-server")
            msi_block.add_actual_pid()
            msi_block.set_start_command("/etc/init.d/rrd-server start")
            msi_block.set_stop_command("/etc/init.d/rrd-server force-stop")
            msi_block.set_kill_pids()
            msi_block.save_block()
        else:
            msi_block = None
        return msi_block
    def _new_ud_out_recv(self, data, src):
        self.__log_queue.put(("syslog_dhcp", data))
    def _new_tcp_command_con(self, sock, src):
        self.log("got command from host %s, port %d" % (src[0], src[1]))
        if self["exit_requested"]:
            return new_tcp_con_forbid("com", "tcp", src, self.__log_queue)
        else:
            return new_tcp_con("com", "tcp", None, src, self.__com_queue, self.__log_queue)
    def _bind_state_call(self, **args):
        if args["state"].count("ok"):
            self.log("Bind to %s (type %s) sucessfull" % (args["port"], args["type"]))
        else:
            # FIXME
            self.log("Bind to %s (type %s) NOT sucessfull" % (args["port"], args["type"]), logging_tools.LOG_LEVEL_CRITICAL)
            self.log("unable to bind to all ports, exiting", logging_tools.LOG_LEVEL_ERROR)
            self._int_error("bind problem")
    def loop_function(self):
        self.__ns.step()
        if self.__loc_config["VERBOSE"] or self["exit_requested"]:
            tqi_dict = self.get_thread_queue_info()
            tq_names = sorted(tqi_dict.keys())
            self.log("tqi: %s" % (", ".join(["%s: %3d of %3d" % (t_name, t_used, t_total) for (t_name, t_used, t_total) in [(t_name,
                                                                                                                             tqi_dict[t_name][1],
                                                                                                                             tqi_dict[t_name][0]) for t_name in tq_names] if t_used]) or "clean"))
        act_time = time.time()
        if not self.__last_update or abs(self.__last_update - act_time) > self.__glob_config["MAIN_TICK"]:
            self.__last_update = act_time
            self.__snmp_update_queue.put("update")
    def thread_loop_post(self):
        process_tools.delete_pid("rrd-server/rrd-server")
        if self.__msi_block:
            self.__msi_block.remove_meta_block()
        try:
            os.unlink(self.__loc_config["LOCK_FILE_NAME"])
        except (IOError, OSError):
            pass
    def _init_rrd_classes(self, dc):
        dc.execute("SELECT c.name, COUNT(r.cf) AS rra_num FROM rrd_class c LEFT JOIN rrd_rra r ON r.rrd_class=c.rrd_class_idx GROUP BY c.name")
        if dc.rowcount:
            self.log("Found %s:" % (logging_tools.get_plural("rrd_class", dc.rowcount)))
            for stuff in dc.fetchall():
                self.log(" - class %30s, %s" % (stuff["name"], logging_tools.get_plural("rrd_set", stuff["rra_num"])))
        else:
            self.log("Inserting default rrd_class")
            # hearbeat is set to 90 for all classes (for SNMP devices)
            rrd_class_dict = {"standard_device" : {"step"      : 30,
                                                   "heartbeat" : 90,
                                                   "rras" : [(          30,              24 * 60 * 60, ["AVERAGE", "MAX", "MIN"]),
                                                             (      5 * 60,          7 * 24 * 60 * 60, ["AVERAGE", "MAX", "MIN"]),
                                                             (     15 * 60,      4 * 7 * 24 * 60 * 60, ["AVERAGE", "MAX", "MIN"]),
                                                             ( 4 * 60 * 60, 12 * 4 * 7 * 24 * 60 * 60, ["AVERAGE", "MAX", "MIN"])]},
                              "detail_device" : {"step"      : 30,
                                                 "heartbeat" : 90,
                                                 "rras" : [(     30,              24 * 60 * 60, ["AVERAGE", "MAX", "MIN"]),
                                                           ( 2 * 60,          7 * 24 * 60 * 60, ["AVERAGE", "MAX", "MIN"]),
                                                           ( 5 * 60,      4 * 7 * 24 * 60 * 60, ["AVERAGE", "MAX", "MIN"]),
                                                           (60 * 60, 12 * 4 * 7 * 24 * 60 * 60, ["AVERAGE", "MAX", "MIN"])]},
                              "snmp_device" : {"step"      : 90,
                                               "heartbeat" : 90,
                                               "rras" : [(         30,              24 * 60 * 60, ["AVERAGE", "MAX", "MIN"]),
                                                         (     5 * 60,          7 * 24 * 60 * 60, ["AVERAGE", "MAX", "MIN"]),
                                                         (    15 * 60,      4 * 7 * 24 * 60 * 60, ["AVERAGE", "MAX", "MIN"]),
                                                         (4 * 60 * 60, 12 * 4 * 7 * 24 * 60 * 60, ["AVERAGE", "MAX", "MIN"])]}}
            for class_name, class_stuff in rrd_class_dict.iteritems():
                dc.execute("INSERT INTO rrd_class SET name='%s', step=%d, heartbeat=%d" % (class_name,
                                                                                           class_stuff["step"], 
                                                                                           class_stuff["heartbeat"]))
                class_step = class_stuff["step"]
                set_idx = dc.insert_id()
                self.log(" - inserting class %s with %s (index %d)" % (class_name,
                                                                       logging_tools.get_plural("rra", len(class_stuff["rras"])),
                                                                       set_idx))
                for step, slots, cf_funcs in class_stuff["rras"]:
                    # max() needed, otherwise divbyzero
                    st_r = max(step, class_step) / class_step
                    st_s = slots / (class_step * st_r)
                    self.log(" ... inserting rras (%s: %s), timestep is %-16s, max time is %-24s (%s, %s)" % (logging_tools.get_plural("func", len(cf_funcs)),
                                                                                                              ", ".join(cf_funcs),
                                                                                                              logging_tools.get_plural("second", step),
                                                                                                              logging_tools.get_plural("second", slots),
                                                                                                              logging_tools.get_plural("step", st_r),
                                                                                                              logging_tools.get_plural("row", st_s)))
                    for cf_func in cf_funcs:
                        dc.execute("INSERT INTO rrd_rra SET rrd_class=%d, cf='%s', steps=%d, rows=%d" % (set_idx,
                                                                                                         cf_func,
                                                                                                         st_r,
                                                                                                         st_s))
    def _init_cluster_events(self, dc):
        ev_dict = {"only mail" : {"description" : "sends only mails",
                                 "color"       : "888888",
                                 "command"     : ""},
                   "halt"      : {"description" : "Halts a machine",
                                  "color"       : "ff0000",
                                  "command"     : "halt"},
                   "poweroff"  : {"description" : "Power-offs a machine",
                                  "color"       : "00ff00",
                                  "command"     : "poweroff"},
                   "ping"      : {"description" : "Pings a machine",
                                  "color"       : "0000ff",
                                  "command"     : "ping"},
                   "apcoff"    : {"description" : "Switches off a machine",
                                  "color"       : "00ffff",
                                  "command"     : "apc_dev off"},
                   "apcon"     : {"description" : "Switches on a machine",
                                  "color"       : "ff00ff",
                                  "command"     : "apc_dev on"},
                   "apcreboot" : {"description" : "Reboots a machine",
                                  "color"       : "0ff0ff",
                                  "command"     : "apc_dev reboot"}}
        dc.execute("SELECT c.* FROM cluster_event c ORDER BY c.name")
        found_events = dict([(x["name"], x) for x in dc.fetchall()])
        ev_inserted = [x for x in ev_dict.keys() if x not in found_events.keys()]
        refresh_events = [key for key, stuff in found_events.iteritems() if stuff["command"] != ev_dict[key]["command"]]
        if found_events:
            self.log("Found %s: %s" % (logging_tools.get_plural("cluster_event", len(found_events.keys())),
                                       ", ".join(found_events.keys())))
        else:
            self.log("Found no defined cluster-events")
        if refresh_events:
            self.log("Refreshing %s: %s" % (logging_tools.get_plural("cluster_event", len(refresh_events)),
                                            ", ".join(refresh_events)))
            for rf in refresh_events:
                dc.execute("UPDATE cluster_event SET command=%s, color=%s, description=%s WHERE name=%s", (ev_dict[rf]["command"],
                                                                                                           ev_dict[rf]["color"],
                                                                                                           ev_dict[rf]["description"],
                                                                                                           rf))
        if ev_inserted:
            self.log("Inserting %s: %s" % (logging_tools.get_plural("cluster_event", len(ev_inserted)),
                                           ", ".join(ev_inserted)))
            for ev_name in ev_inserted:
                dc.execute("INSERT INTO cluster_event SET %s" % (", ".join(["%s=%%s" % (key) for key in ["name"] + ev_dict[ev_name].keys()])),
                           tuple([ev_name] + [ev_dict[ev_name][key] for key in ev_dict[ev_name].keys()]))

def modify_sysctl():
    sys_ctl_dict = {"net.core.rmem_max"     : 1310710,
                    "net.core.rmem_default" : 1310710}
    for key, value in sys_ctl_dict.iteritems():
        full_path = "/".join(["", "proc", "sys"] + key.split("."))
        if os.path.isfile(full_path):
            try:
                file(full_path, "w").write("%d" % (value))
            except:
                pass
        
def main():
    global device_group_dict, log_status
    # global device_dictionary; has entries in the form ip->device and name->device
    #device_dict = {}
    # global device_group_dictionary; has entries in the form devicegroup_idx->meta_device and devicegroup_name->meta_device
    device_group_dict = {}
    try:
        opts, args = getopt.getopt(sys.argv[1:], "vdhCu:g:fk", ["help", "version", "no-mysql-log"])
    except getopt.GetoptError, bla:
        print "Cannot parse commandline (%s)!" % (bla)
        sys.exit(-1)
    long_host_name = socket.getfqdn(socket.gethostname())
    short_host_name = long_host_name.split(".")[0]
    # read version
    try:
        from rrd_server_version import VERSION_STRING
    except ImportError:
        VERSION_STRING = "?.?"
    loc_config = configfile.configuration("local_config", {"PID_NAME"               : configfile.str_c_var("rrd-server/rrd-server"),
                                                           "SERVER_FULL_NAME"       : configfile.str_c_var(long_host_name),
                                                           "SERVER_SHORT_NAME"      : configfile.str_c_var(short_host_name),
                                                           "DAEMON"                 : configfile.bool_c_var(True),
                                                           "VERBOSE"                : configfile.int_c_var(0),
                                                           "RRD_SERVER_IDX"         : configfile.int_c_var(0),
                                                           "LOG_SOURCE_IDX"         : configfile.int_c_var(0),
                                                           "NODE_SOURCE_IDX"        : configfile.int_c_var(0),
                                                           "GLOBAL_NET_DEVICES"     : configfile.dict_c_var({}),
                                                           "GLOBAL_NET_DEVICE_DICT" : configfile.dict_c_var({}),
                                                           "VERSION_STRING"         : configfile.str_c_var(VERSION_STRING),
                                                           "LOCK_FILE_NAME"         : configfile.str_c_var("/var/lock/rrd-server/rrd-server.lock"),
                                                           # flag: do we cache at all ?
                                                           "CACHING"                : configfile.bool_c_var(True)})
    check, kill_running, mysql_log = (False, True, True)
    user, group, fixit = ("root", "root", False)
    pname = os.path.basename(sys.argv[0])
    for opt, arg in opts:
        if opt in ["-h", "--help"]:
            print "Usage: %s [-h|--help] [OPTIONS] where OPTIONS is one or more of" % (pname)
            print "  -h,--help        show this help"
            print "  --version        version info"
            print "  -d               enable debug mode (no forking)"
            print "  -f               create and fix needed files and directories"
            print "  -u user          run as user USER"
            print "  -g group         run as group GROUP"
            print "  -k               do not kill running %s" % (pname)
            print "  -v               be verbose"
            print "  --no-mysql-log   disable SQL-logging when running in daemon mode"
            sys.exit(0)
        if opt == "--version":
            print "rrd-server, Version %s" % (loc_config["VERSION_STRING"])
            sys.exit(0)
        if opt == "-C":
            check = True
        if opt == "-d":
            loc_config["DAEMON"] = False
        if opt == "-f":
            fixit = True
        if opt == "-u":
            user = arg
        if opt == "-g":
            group = arg
        if opt == "-k":
            kill_running = False
        if opt == "-v":
            loc_config["VERBOSE"] = True
        if opt == "--no-mysql-log":
            mysql_log = False

    db_con = mysql_tools.dbcon_container(with_logging=(not loc_config["DAEMON"] and mysql_log))
    try:
        dc = db_con.get_connection(SQL_ACCESS)
    except MySQLdb.OperationalError:
        sys.stderr.write(" Cannot connect to SQL-Server ")
        sys.exit(1)
    num_servers, loc_config["RRD_SERVER_IDX"] = process_tools.is_server(dc, "rrd_server")
    ret_state = 256
    if num_servers == 0:
        sys.stderr.write("Host %s is no rrd-server" % (long_host_name))
        sys.exit(5)
    if check:
        sys.exit(0)
    if kill_running:
        kill_dict = process_tools.build_kill_dict(pname)
        for kill_pid, value in kill_dict.iteritems():
            log_str = "Trying to kill pid %d (%s) with signal 9 ..." % (kill_pid, value)
            try:
                os.kill(kill_pid, 9)
            except:
                log_str = "%s error (%s)" % (log_str, sys.exc_info()[0])
            else:
                log_str = "%s ok" % (log_str)
            logging_tools.my_syslog(log_str)
    g_config = configfile.read_global_config(dc, "rrd_server", {"LOG_DIR"                   : configfile.str_c_var("/var/log/cluster/rrd-server"),
                                                                "RRD_DIR"                   : configfile.str_c_var("/var/lib/rrd-server/rrds"),
                                                                "TRACE_DIR"                 : configfile.str_c_var("/var/lib/rrd-server/trace_vars"),
                                                                "COLLECTOR_PORT"            : configfile.int_c_var(8002),
                                                                "COMMAND_PORT"              : configfile.int_c_var(8003),
                                                                "COLLSERVER_PORT"           : configfile.int_c_var(2001),
                                                                "MAX_CACHE_SIZE"            : configfile.int_c_var(128),
                                                                "MAX_CACHE_TIME"            : configfile.int_c_var(3600),
                                                                "SMTP_SERVER"               : configfile.str_c_var("localhost"),
                                                                "SMTP_SERVER_HELO"          : configfile.str_c_var("localhost"),
                                                                "METADEV_KEYS"              : configfile.array_c_var(["load.", "mem.", "num.", "vms.", "net.", "temp.", "apc.", "snmp."]),
                                                                "NB_PIC_DIR"                : configfile.str_c_var("/srv/www/htdocs/nb-pics"),
                                                                "RRD_PNG_DIR"               : configfile.str_c_var("/srv/www/htdocs/rrd-pngs"),
                                                                "METADEV_TIMEOUT"           : configfile.int_c_var(60),
                                                                "TRACE_CACHE_SIZE"          : configfile.int_c_var(128),
                                                                "TRACE_VAR_WIDTH"           : configfile.int_c_var(400),
                                                                "TRACE_VAR_HEIGHT"          : configfile.int_c_var(200),
                                                                "SHOW_DETAILED_CACHE_INFO"  : configfile.int_c_var(0),
                                                                "RRD_COM_TIMEOUT"           : configfile.int_c_var(1),
                                                                "MAIN_TICK"                 : configfile.int_c_var(30),
                                                                "NETBOTZ_PICTURE_KEEP_DAYS" : configfile.int_c_var(30),
                                                                "ADV_LOCK_TIMEOUT"          : configfile.int_c_var(300),
                                                                "MAX_MEMORY_USAGE"          : configfile.int_c_var(300),
                                                                "METADEVICE_KEEP_COUNTER"   : configfile.int_c_var(5),
                                                                "NUM_COLLECT_THREADS"       : configfile.int_c_var(1)})
    if not g_config["MAX_CACHE_SIZE"] or not g_config["MAX_CACHE_TIME"]:
        loc_config["CACHING"] = False
    if num_servers > 1:
        print "Database error for host %s (rrd_server): too many entries found (%d)" % (long_host_name, num_servers)
        dc.release()
    else:
        loc_config["LOG_SOURCE_IDX"] = process_tools.create_log_source_entry(dc, loc_config["RRD_SERVER_IDX"], "rrd_server", "RRD Server")
        if not loc_config["LOG_SOURCE_IDX"]:
            print "Too many log_sources with my id present, exiting..."
            dc.release()
        else:
            log_status  = process_tools.get_all_log_status(dc)
            dc.release()
            if fixit:
                process_tools.fix_directories(user, group, [g_config["LOG_DIR"],
                                                            g_config["RRD_DIR"],
                                                            g_config["TRACE_DIR"],
                                                            "/var/run/rrd-server",
                                                            g_config["NB_PIC_DIR"],
                                                            {"name"     : g_config["RRD_PNG_DIR"],
                                                             "dir_mode ": 0777,
                                                             "walk_dir" : False},
                                                            "/etc/sysconfig/rrd-server.d",
                                                            os.path.dirname(loc_config["LOCK_FILE_NAME"])])
            process_tools.fix_files(user, group, ["/var/log/rrd-server.out", "/tmp/rrd-server.out", loc_config["LOCK_FILE_NAME"]])
            process_tools.renice()
            modify_sysctl()
            process_tools.change_user_group(user, group)
            if loc_config["DAEMON"]:
                process_tools.become_daemon()
                process_tools.set_handles({"out" : (1, "rrd-server.out"),
                                           "err" : (0, "/var/lib/logging-server/py_err")})
            else:
                print "Debugging rrd_server..."
            my_tp = server_thread_pool(db_con, g_config, loc_config)
            my_tp.thread_loop()
            #ret_state = server_code(num_retry, daemon, db_con)
    db_con.close()
    del db_con
    sys.exit(ret_state)

if __name__ == "__main__":
    main()
