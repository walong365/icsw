#!/usr/bin/python-init -Ot
#
# Copyright (C) 2008,2009,2010,2011,2012,2013 Andreas Lang-Nevyjel, init.at
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
import commands
from initat.host_monitoring import limits, hm_classes
import os
import os.path
import logging_tools
import process_tools
import pprint
import time
import socket
import datetime
import glob
import server_command

OPENVPN_DIR = "/etc/openvpn"
EXPECTED_FILE = "/etc/sysconfig/host-monitoring.d/openvpn_expected"

class net_speed(object):
    def __init__(self):
        self.__last_update = None
        self.__act_rx, self.__act_tx = (0., 0.)
    def _get_value(self, diff_val, diff_time):
        val = max(0, min(10000000., diff_val / diff_time))
        return val
    def feed(self, rx, tx):
        act_time = time.time()
        last_update = self.__last_update
        self.__last_update = act_time
        prev_rx, prev_tx = (self.__act_rx,
                            self.__act_tx)
        # store
        self.__act_rx, self.__act_tx = (rx, tx)
        if last_update:
            diff_time = max(1, abs(last_update - self.__last_update))
            return (self._get_value(self.__act_rx - prev_rx, diff_time),
                    self._get_value(self.__act_tx - prev_tx, diff_time))
        else:
            return (0., 0.)
            
class _general(hm_classes.hm_module):
    def __init__(self, *args, **kwargs):
        hm_classes.hm_module.__init__(self, *args, **kwargs)
        # instance dict
        self.__inst_dict = {}
        # expected OpenVPN instances
        self.__expected = None
    def _exec_command(self, com, logger):
        stat, out = commands.getstatusoutput(com)
        if stat:
            logger.warning("cannot execute %s (%d): %s" % (com, stat, out))
            out = ""
        return out.split("\n")
    def init_machine_vector(self, mv):
        # register entries
        self.__base_mv_registered = False
        self.__client_dict = {}
        self.__last_status_update = None
    def update_machine_vector(self, mv):
        self.update_status()
        ovpn_keys = self.keys()
        num_total = len(ovpn_keys)
        if num_total and not self.__base_mv_registered:
            self.__base_mv_registered = True
            mv.register_entry("ovpn.total"      , 0, "Number of OpenVPN Instances")
            mv.register_entry("ovpn.operational", 0, "Number of OpenVPN Instances operational")
            mv.register_entry("ovpn.offline"    , 0, "Number of OpenVPN Instances offline")
        if self.__base_mv_registered:
            num_online = len([True for key in ovpn_keys if self[key].state])
            num_offline = num_total - num_online
            mv["ovpn.total"]       = num_total
            mv["ovpn.operational"] = num_online
            mv["ovpn.offline"]     = num_offline
        for ovpn_inst in [self[key] for key in ovpn_keys if self[key].ovpn_type == "server"]:
            ovpn_name = ovpn_inst.name.split(".")[0]
            clients = ovpn_inst.keys()
            if not ovpn_inst.mv_registered:
                ovpn_inst.mv_registered = True
                self.__client_dict[ovpn_name] = {}
                mv.register_entry("ovpn.%s.total"   % (ovpn_name), 0, "Number of clients total for $2")
                mv.register_entry("ovpn.%s.online"  % (ovpn_name), 0, "Number of clients online for $2")
                mv.register_entry("ovpn.%s.offline" % (ovpn_name), 0, "Number of clients offline for $2")
            num_online = len([True for key in clients if ovpn_inst[key]["online"]])
            num_offline = len(clients) - num_online
            mv["ovpn.%s.total" % (ovpn_name)]   =  len(clients)
            mv["ovpn.%s.online" % (ovpn_name)]  = num_online
            mv["ovpn.%s.offline" % (ovpn_name)] = num_offline
            # iterate over clients
            act_dict = self.__client_dict[ovpn_name]
            for client in clients:
                c_dict = ovpn_inst[client]
                client_dict = act_dict.setdefault(client, {"registered" : False,
                                                           "speed"     : net_speed()})
                c_pfix = "ovpn.%s.%s" % (ovpn_name, client)
                if not client_dict["registered"]:
                    client_dict["registered"] = True
                    mv.register_entry("%s.rx" % (c_pfix), 0., "bytes per seconds received by $3", "Byte/s", 1024)
                    mv.register_entry("%s.tx" % (c_pfix), 0., "bytes per seconds transmitted by $3", "Byte/s", 1024)
                act_rx, act_tx = client_dict["speed"].feed(c_dict["rx"], c_dict["tx"])
                mv["%s.rx" % (c_pfix)] = act_rx
                mv["%s.tx" % (c_pfix)] = act_tx
            #pprint.pprint(ovpn_inst.get_repr())
    def update_expected(self):
        ret_field = []
        if os.path.isfile(EXPECTED_FILE):
            if not self.__expected:
                self.__expected = process_tools.cached_file(EXPECTED_FILE, log_handle=self.log)
            self.__expected.update()
            ret_field = self.__expected.content.split("\n")
        else:
            self.__expected = None
            try:
                open(EXPECTED_FILE, "w").write("\n".join(["# Expected OpenVPN instances",
                                                          "# Format:",
                                                          "# DEVICE=<INSTANCE> <INSTANCE>",
                                                          "# where INSTANCE has the form",
                                                          "# instance_name:client1_name{,W|C}:client2_name,{W,C}",
                                                          "",
                                                          "#gatekeeper=lang-nevyjel:ehkcluster,W:test,E bla:x",
                                                          ""]))
            except:
                self.log("error creating %s: %s" % (EXPECTED_FILE,
                                                    process_tools.get_except_info()),
                         logging_tools.LOG_LEVEL_ERROR)
        return self._parse_expected(ret_field)
    def _parse_expected(self, in_field):
        ret_dict = {}
        lines = [line.strip() for line in in_field if line.strip() and not line.strip().startswith("#")]
        for line in lines:
            if line.count("=") == 1:
                dev_name, dev_stuff = line.split("=", 1)
                dev_dict = {}
                ret_dict[dev_name.strip()] = dev_dict
                instances = dev_stuff.split()
                for instance in instances:
                    inst_parts = instance.split(":")
                    inst_dict = {}
                    dev_dict[inst_parts.pop(0)] = inst_dict
                    for inst_part in inst_parts:
                        c_parts = inst_part.split(",")
                        client_name = c_parts.pop(0)
                        inst_dict[client_name] = limits.nag_STATE_CRITICAL
                        if c_parts and c_parts[0].lower() in ["w"]:
                            inst_dict[client_name] = limits.nag_STATE_WARNING
        return ret_dict
    def update_status(self):
        if self.__last_status_update is None or abs(self.__last_status_update - time.time()) > 5:
            # update
            self.__last_status_update = time.time()
            found_inst = []
            if os.path.isdir(OPENVPN_DIR):
                for entry in os.listdir(OPENVPN_DIR):
                    if entry.endswith(".conf") and not entry.startswith("."):
                        e_key = entry[:-5]
                        if self.__inst_dict.has_key(e_key):
                            try:
                                self.__inst_dict[e_key].update()
                            except:
                                self.log("unable to update instance %s: %s" % (entry,
                                                                               process_tools.get_except_info()),
                                         logging_tools.LOG_LEVEL_ERROR)
                            else:
                                found_inst.append(e_key)
                        else:
                            try:
                                new_inst = openvpn_instance(self.log, entry)
                            except:
                                self.log("unable to create new openvpn_instance for %s: %s" % (entry,
                                                                                               process_tools.get_except_info()),
                                         logging_tools.LOG_LEVEL_ERROR)
                            else:
                                self.__inst_dict[e_key] = new_inst
                                found_inst.append(e_key)
            old_inst = [key for key in self.__inst_dict.keys() if key not in found_inst]
            if old_inst:
                self.log("removing %s: %s" % (logging_tools.get_plural("instance", len(old_inst)),
                                              ", ".join(sorted(old_inst))))
                for inst in old_inst:
                    del self.__inst_dict[inst]
    def keys(self):
        return self.__inst_dict.keys()
    def __getitem__(self, key):
        return self.__inst_dict[key]

class openvpn_instance(object):
    def __init__(self, log_h, name):
        self.__log_handle = log_h
        self.name = name
        self.__conf_obj = process_tools.cached_file("%s/%s" % (OPENVPN_DIR, name),
                                                    log_handle=self.log)
        self.__status_name, self.__status_obj = ("", None)
        # save client_config_files
        self.__client_config_files = {}
        # for machinevector
        self.mv_registered = False
        # speed dict
        self.__speed_dict = {}
        self.update()
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_handle.log("[oi] %s" % (what), log_level)
    def keys(self):
        return self.__act_dict.keys()
    def __getitem__(self, key):
        return self.__act_dict[key]
    def update(self):
        self.ovpn_type, self.__device = (
            "unknown",
            "unknown",
        )
        self.__conf_obj.update()
        self.__ccd = None
        self.__verify_script = None
        for line in self.__conf_obj.content.split("\n"):
            line_p = line.strip().split()
            if line_p:
                key = line_p.pop(0)
                if line_p:
                    if key == "status":
                        stat_name = line_p[0]
                        if stat_name != self.__status_name:
                            self.__status_name = stat_name
                            self.__status_obj = process_tools.cached_file(self.__status_name)
                if key == "client":
                    self.ovpn_type = "client"
                elif key == "server":
                    self.ovpn_type = "server"
                elif key == "dev":
                    self.__device = line_p[0]
                elif key == "client-config-dir":
                    self.__ccd = line_p[0]
                elif key == "tls-verify":
                    self.__verify_script = line_p[0]
        if self.__ccd:
            self.__ccd = "%s/%s" % (OPENVPN_DIR, self.__ccd)
        self.state, self.status_str = (False, "no status file found")
        act_dict = {}
        if self.__status_obj:
            self.__status_obj.update()
            if self.__status_obj.content is not None:
                if self.ovpn_type == "client":
                    stat_lines = self.__status_obj.content.split("\n")
                    # default value
                    self.state, self.status_str = (False, "wrong version of client status file")
                    if stat_lines[0].startswith("OpenVPN STAT"):
                        stat_lines.pop(0)
                        upd_line = stat_lines.pop(0).split(",")
                        if upd_line[0] == "Updated":
                            act_time = time.time()
                            upd_time = time.mktime(time.strptime(upd_line[1]))
                            if abs(act_time - upd_time) > 60:
                                # client is dead
                                self.state, self.status_str = (False, "not connected")
                            else:
                                self.state, self.status_str = (True, "is connected")
                else:
                    stat_lines = self.__status_obj.content.split("\n")
                    if stat_lines[0].startswith("TITLE"):
                        act_mode = ""
                        for line in stat_lines:
                            line = line.strip().split(",")
                            if line and line[0]:
                                key = line.pop(0)
                                if key in ["TIME"]:
                                    cur_time = int(line[-1])
                                    keys = self.__speed_dict.keys()
                                    if cur_time not in keys:
                                        # remove oldest one
                                        if len(keys) > 1:
                                            del self.__speed_dict[min(keys)]
                                        self.__speed_dict[cur_time] = {}
                                        # get keys again
                                        keys = self.__speed_dict.keys()
                                    if len(keys) == 2:
                                        prev_speed_dict, cur_speed_dict = (self.__speed_dict[min(keys)], self.__speed_dict[max(keys)])
                                        diff_time = abs(keys[0] - keys[1])
                                    else:
                                        diff_time = None
                                elif key in ["CLIENT_LIST", "ROUTING_TABLE"]:
                                    if key == "CLIENT_LIST":
                                        c_name = line[0]
                                        act_dict[c_name] = {
                                            "online"    : True,
                                            "src"       : line[1],
                                            "remote"    : line[2],
                                            "rx"        : int(line[3]),
                                            "tx"        : int(line[4]),
                                            "connected" : int(line[6])
                                        }
                                        if diff_time:
                                            cur_speed_dict[c_name] = (int(line[3]), int(line[4]))
                                            if c_name in prev_speed_dict:
                                                act_dict[c_name].update({
                                                    "rxs" : abs(int(line[3]) - prev_speed_dict[c_name][0]) / diff_time,
                                                    "txs" : abs(int(line[4]) - prev_speed_dict[c_name][1]) / diff_time,
                                                })
                                    elif key == "ROUTING_TABLE":
                                        act_dict[line[1]]["reference"] = int(line[4])
                        # try to add client dirs
                        if self.__ccd:
                            for client_name in act_dict.keys():
                                cconf_name = "%s/%s" % (self.__ccd,
                                                        client_name)
                                if os.path.isfile(cconf_name):
                                    if not self.__client_config_files.has_key(cconf_name):
                                        self.__client_config_files[cconf_name] = process_tools.cached_file(cconf_name,
                                                                                                           log_handle=self.log)
                                    self.__client_config_files[cconf_name].update()
                                    cconf_object = self.__client_config_files[cconf_name]
                                    if cconf_object.content is not None:
                                        for client_line in cconf_object.content.split("\n"):
                                            line_split = client_line.strip().split()
                                            if line_split and line_split[0] == "ifconfig-push":
                                                act_dict.setdefault(client_name, {"oneline" : False})["client_ip"] = line_split[1]
                        self.state, self.status_str = (True, "%s connected" % (logging_tools.get_plural("client", len(act_dict.keys()))))
                    else:
                        self.state, self.status_str = (False, "wrong version of server status file")
            else:
                self.state, self.status_str = (False, "status file defined but unable to read")
        else:
            self.state, self.status_str = (False, "no status file defined")
        self.__act_dict = act_dict
    def get_repr(self):
        return {
            "state"             : self.state,
            "status"            : self.status_str,
            "has_verify_script" : True if self.__verify_script else False,
            "type"              : self.ovpn_type,
            "dict"              : self.__act_dict,
            "device"            : self.__device
        }
    
class certificate_status_command(hm_classes.hm_command):
    def __init__(self, name):
        hm_classes.hm_command.__init__(self, name, positional_arguments=True)
    def _get_pem_status(self, file_name):
        pem_com = "/usr/bin/openssl x509 -in %s -startdate -enddate -noout" % (file_name)
        c_stat, c_out = commands.getstatusoutput(pem_com)
        if not c_stat:
            act_dict = {}
            for line in c_out.split("\n"):
                if line.count("="):
                    key, value = [part.strip() for part in line.split("=", 1)]
                    if key.lower() in ["notbefore", "notafter"]:
                        time_st = datetime.datetime.strptime(value, "%b %d %H:%M:%S %Y %Z")
                        act_dict[key] = time_st
        else:
            act_dict = None
        return act_dict
    def __call__(self, srv_com, cm):
        pem_files = sum([glob.glob(s_glob) for s_glob in cm.arguments], [])
        home_dir = "/etc/openvpn"
        cert_dict, map_dict = ({}, {})
        if not pem_files:
            conf_files = [file_name for file_name in os.listdir(home_dir) if file_name.endswith(".conf")]
            for conf_file in conf_files:
                file_name = "%s/%s" % (home_dir, conf_file)
                lines = file(file_name, "r").read().split("\n")
                for line in lines:
                    l_parts = line.strip().split()
                    if len(l_parts) == 2:
                        key, value = l_parts
                        if key.lower() in ["ca", "cert"]:
                            map_dict[os.path.join(home_dir, value)] = file_name
            for dir_name, dir_list, file_list in os.walk(home_dir):
                pem_files.extend([os.path.join(dir_name, file_name) for file_name in file_list if file_name.endswith(".pem")])
        for file_name in pem_files:
            #file_name = "%s/%s" % (dir_name, pem_file)
            act_dict = self._get_pem_status(file_name)
            if act_dict:
                if map_dict.has_key(file_name):
                    act_dict["openvpn_config"] = map_dict[file_name]
                cert_dict[file_name] = act_dict
        srv_com["certificates"] = cert_dict
    def interpret(self, srv_com, cur_ns):
        cert_dict = srv_com["certificates"]
        return self._interpret(cert_dict)
    def interpret_old(self, result, parsed_coms):
        cert_dict = hm_classes.net_to_sys(result[3:])
        return self._interpret(cert_dict)
    def _interpret(self, cert_dict):
        num_dict = dict([(key, 0) for key in ["ok", "warn", "error", "total"]])
        errors = []
        act_time = datetime.datetime.now()
        for file_name in sorted(cert_dict.keys()):
            cert_info = cert_dict[file_name]
            start_diff_time, end_diff_time = ((act_time - cert_info["notBefore"]).days,
                                              (cert_info["notAfter"] - act_time).days)
            if cert_info.has_key("openvpn_config"):
                info_str = "%s (%s)" % (file_name,
                                        os.path.basename(cert_info["openvpn_config"]))
            else:
                info_str = file_name
            num_dict["total"] += 1
            if start_diff_time < 0:
                num_dict["error"] += 1
                errors.append("%s: will start in %s" % (info_str,
                                                        logging_tools.get_plural("day", abs(start_diff_time))))
            if end_diff_time < 0:
                num_dict["error"] += 1
                errors.append("%s: is expired since %s" % (info_str,
                                                           logging_tools.get_plural("day", abs(end_diff_time))))
            elif end_diff_time < 30:
                if end_diff_time < 14:
                    num_dict["error"] += 1
                else:
                    num_dict["error"] += 1
                    num_dict["warn"] += 1
                errors.append("%s: will expire in %s" % (info_str,
                                                         logging_tools.get_plural("day", abs(end_diff_time))))
        if num_dict["error"]:
            ret_state = limits.nag_STATE_CRITICAL
        elif num_dict["warn"]:
            ret_state = limits.nag_STATE_WARNING
        else:
            ret_state = limits.nag_STATE_OK
        return ret_state, "checked %s, %s%s" % (
            logging_tools.get_plural("certificate", num_dict["total"]),
            ", ".join([logging_tools.get_plural(key, num_dict[key]) for key in ["ok", "warn", "error"] if num_dict[key]]) or "no problems",
            "; %s" % (", ".join(sorted(errors))) if errors else "")
            
class openvpn_status_command(hm_classes.hm_command):
    def __init__(self, name):
        hm_classes.hm_command.__init__(self, name, positional_arguments=False)
        self.parser.add_argument("-i", dest="instance", type=str, default="ALL")
        self.parser.add_argument("-p", dest="peer", type=str, default="ALL")
    def __call__(self, srv_com, cur_ns):
        self.module.update_status()
        insts = self.module.keys()
        if insts:
            ret_dict = {}
            for inst in sorted(insts):
                ret_dict[inst] = self.module[inst].get_repr()
        else:
            ret_dict = {}
        srv_com["openvpn_instances"] = ret_dict
    def interpret_old(self, result, parsed_coms):
        inst_dict = hm_classes.net_to_sys(result[3:])
        return self._interpret(inst_dict, parsed_coms, self.NOGOOD_srv_com["host"].text)
    def interpret(self, srv_com, cur_ns):
        inst_dict = srv_com["openvpn_instances"]
        return self._interpret(inst_dict, cur_ns, srv_com["host"].text)
    def _interpret(self, res_dict, cur_ns, host):
        inst_name = cur_ns.instance
        peer_name = cur_ns.peer
        exp_dict = self.module.update_expected()
        # do we need the expected_dict ?
        if peer_name == "ALL":
            ret_state, res_field = (limits.nag_STATE_OK, [logging_tools.get_plural("instance", len(res_dict.keys()))])
            host_names = [host]
            host_exp_dict = None
            if exp_dict.has_key(host_names[-1]):
                host_exp_dict = exp_dict[host_names[-1]]
            else:
                try:
                    host_name = socket.gethostbyaddr(host)[0]
                except:
                    pass
                else:
                    if host_name != host:
                        host_names.append(host_name)
                    host_names.append(host_name.split(".")[0])
                    for host_name in host_names[1:]:
                        if exp_dict.has_key(host_name):
                            host_exp_dict = exp_dict[host_name]
                            break
            if host_exp_dict is None:
                ret_state, res_field = (limits.nag_STATE_WARNING, ["no host reference for %s" % (" or ".join(set(host_names)))])
        else:
            ret_state, res_field = (limits.nag_STATE_OK, [])
            host_exp_dict = None
        if inst_name != "ALL":
            check_instances = [inst_name]
        else:
            check_instances = res_dict.keys()
        for inst_name in sorted(check_instances):
            # iterate over instances
            if res_dict.has_key(inst_name):
                # instance found
                if type(res_dict[inst_name]) == type(()):
                    # old kind of result
                    inst_ok, inst_str, clients = res_dict[inst_name]
                    i_type, vpn_device, p_ip = (
                        "server",
                        "not set",
                        "")
                else:
                    # new kind
                    act_sdict = res_dict[inst_name]
                    inst_ok, inst_str, clients, i_type = (
                        act_sdict["state"],
                        act_sdict["status"],
                        act_sdict["dict"],
                        act_sdict["type"])
                    vpn_device = act_sdict.get("device", "not set")
                if inst_ok:
                    if i_type == "client":
                        res_field.append("%s (Client via %s)" % (inst_name,
                                                                 vpn_device))
                    elif i_type == "server":
                        if not act_sdict.get("has_verify_script", False):
                            ret_state = max(ret_state, limits.nag_STATE_WARNING)
                            res_field.append("no tls-verify script")
                        # peer == client
                        if peer_name != "ALL":
                            p_ip = clients.get(peer_name, {}).get("client_ip", "")
                            p_ip_str = " at %s" % (p_ip) if p_ip else ""
                            if clients.has_key(peer_name) and clients[peer_name].get("online", True):
                                peer_dict = clients[peer_name]
                                if peer_dict.has_key("remote"):
                                    remote_ip = peer_dict["remote"]
                                    if p_ip:
                                        # has p_ip, compare with remote_ip
                                        if remote_ip == p_ip:
                                            # same, ok
                                            pass
                                        else:
                                            # differ, oh-oh
                                            p_ip_str = "%s != %s" % (p_ip_str, remote_ip)
                                            ret_state = max(ret_state, limits.nag_STATE_WARNING)
                                    else:
                                        # no p_ip, set p_ip_str according to 
                                        p_ip_str = " at %s" % (remote_ip)
                                if "rxs" in peer_dict:
                                    res_field.append("%s (Srv on %s, client %s%s ok, %s/s %s/s) | rx=%d tx=%d" % (
                                        inst_name,
                                        vpn_device,
                                        peer_name,
                                        p_ip_str,
                                        logging_tools.get_size_str(peer_dict["rxs"]),
                                        logging_tools.get_size_str(peer_dict["txs"]),
                                        peer_dict["rxs"],
                                        peer_dict["txs"],
                                    ))
                                else:
                                    res_field.append("%s (Srv on %s, client %s%s ok)" % (
                                        inst_name,
                                        vpn_device,
                                        peer_name,
                                        p_ip_str))
                            else:
                                res_field.append("%s (Srv via %s, client %s%s not found)" % (
                                    inst_name,
                                    vpn_device,
                                    peer_name,
                                    p_ip_str))
                                ret_state = max(ret_state, limits.nag_STATE_CRITICAL)
                        else:
                            if host_exp_dict is not None and host_exp_dict.has_key(inst_name):
                                # check clients for found instance
                                for client in clients:
                                    if host_exp_dict[inst_name].has_key(client):
                                        host_exp_dict[inst_name][client] = limits.nag_STATE_OK
                            if clients:
                                res_field.append("%s (Srv via %s, %s: %s)" % (
                                    inst_name,
                                    vpn_device,
                                    logging_tools.get_plural("client", len(clients.keys())),
                                    ",".join(sorted(clients.keys()))))
                            else:
                                res_field.append("%s (no clients)" % (inst_name))
                    else:
                        res_field.append("%s (%s)" % (inst_name, i_type))
                else:
                    res_field.append("%s (%s)" % (inst_name, inst_str))
                    ret_state = max(ret_state, limits.nag_STATE_CRITICAL)
                # check for missing clients according to host_exp_dict
                if host_exp_dict is not None and i_type == "server":
                    if host_exp_dict.has_key(inst_name):
                        for client_name in sorted(host_exp_dict[inst_name].keys()):
                            nag_stat = host_exp_dict[inst_name][client_name]
                            if nag_stat:
                                res_field.append("%s.%s missing" % (inst_name,
                                                                    client_name))
                                ret_state = max(ret_state, nag_stat)
                    else:
                        res_field.append("no instance reference for %s" % (inst_name))
                        ret_state = max(ret_state, limits.nag_STATE_WARNING)
            else:
                res_field.append("no instance '%s' found" % (inst_name))
                ret_state = max(ret_state, limits.nag_STATE_CRITICAL)
        return ret_state, "%s: %s" % (limits.get_state_str(ret_state),
                                      ", ".join(res_field))

if __name__ == "__main__":
    print "This is a loadable module."
    sys.exit(0)
