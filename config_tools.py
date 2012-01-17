#!/usr/bin/python-init -Ot
#
# Copyright (C) 2007,2008 Andreas Lang-Nevyjel, init.at
#
# this file is part of python-modules-base
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
""" module to operate with config and ip relationsships in the database """

import sys
import re
import os
import commands
import pprint
import configfile
import array

class server_check(object):
    """ is called server_check, but can also be used for nodes """
    def __init__(self, **args):
        dc = args.get("dc", None)
        self.__server_type = args["server_type"]
        self.short_host_name = args.get("short_host_name", os.uname()[1])
        self.__fetch_network_info = args.get("fetch_network_info", True)
        self.__network_info_fetched = False
        self._check(dc)
    def _check(self, dc):
        # device_idx from database
        self.device_idx = 0
        # server origin, one of unknown,
        # ...... real (hostname matches and config set local)
        # ...... meta (hostname matches and config set to meta_device)
        # ...... virtual (hostname mismatch, ip match)
        # ...... virtual meta (hostname mismatch, ip match, config set to meta_device)
        self.server_origin = "unknown"
        # info string
        self.server_info_str = "not set"
        # config idx, index of new_config
        self.config_idx = 0
        # server config idx, index of device for which the config is set
        self.server_config_idx = 0
        # name of device which has the config
        self.server_config_name = ""
        # server device idx, index of device with matching hostname / ip
        self.server_device_idx = 0
        # number of servers found
        self.num_servers = 0
        # list of ip-addresses for server
        self.ip_list = []
        # list of netdevice-idxs for server
        self.netdevice_idx_list = []
        # lookup table netdevice_idx -> list of ips
        self.netdevice_ip_lut = {}
        # lookup table ip -> netdevice_idx
        self.ip_netdevice_lut = {}
        # lookup table ip -> network identifier
        self.ip_identifier_lut = {}
        self.real_server_name = self.__server_type
        # set dummy config_name
        self.config_name = self.__server_type
        # config variable dict
        self.__config_vars = {}
        if dc:
            self._db_check(dc)
    def _db_check(self, dc):
        if self.__server_type.count("%"):
            self.__match_str = " LIKE('%s')" % (self.__server_type)
            self.__server_type_info_str = "%s (with wildcard)" % (self.__server_type.replace("%", ""))
        else:
            self.__match_str = "='%s'" % (self.__server_type)
            self.__server_type_info_str = self.__server_type
        # at first resolve device_idx
        dc.execute("SELECT d.device_idx FROM device d WHERE d.name=%s", self.short_host_name)
        if dc.rowcount:
            self.device_idx = dc.fetchone()["device_idx"]
        else:
            self.device_idx = 0
        dc.execute("SELECT d.device_idx, dc.new_config, c.name AS confname, dc.device FROM device d " + \
                   "INNER JOIN device_config dc INNER JOIN new_config c INNER JOIN device_group dg LEFT JOIN device d2 ON d2.device_idx=dg.device " + \
                   "WHERE d.device_group=dg.device_group_idx AND dc.new_config=c.new_config_idx AND (dc.device=d.device_idx OR dc.device=d2.device_idx) AND c.name%s AND d.device_idx=%d" % (self.__match_str, self.device_idx))
        all_servers = dc.fetchall()
        self.num_servers = len(all_servers)
        if self.num_servers == 1:
            # name matches -> 
            self._set_srv_info(dc, all_servers[0], "real", "meta", "hostname '%s'" % (self.short_host_name))
            if self.__fetch_network_info:
                # fetch ip_info only if needed
                self._fetch_network_info(dc)
        else:
            # fetch ip_info
            self._fetch_network_info(dc)
            self._db_check_ip(dc)
    def fetch_config_vars(self, dc):
        if self.config_idx:
            # dict of local vars without specified host
            l_var_wo_host = {}
            # code from configfile.py
            for short, what_value in [("str" , configfile.str_c_var),
                                      ("int" , configfile.int_c_var),
                                      ("blob", configfile.str_c_var)]:
                sql_str = "SELECT cv.* FROM config_%s cv WHERE cv.new_config=%d ORDER BY cv.name" % (short, self.config_idx)
                dc.execute(sql_str)
                for db_rec in [rec for rec in dc.fetchall() if rec["name"]]:
                    if db_rec["name"].count(":"):
                        var_global = False
                        local_host_name, var_name = db_rec["name"].split(":", 1)
                    else:
                        var_global = True
                        local_host_name, var_name = (self.short_host_name, db_rec["name"])
                    if type(db_rec["value"]) == type(array.array("b")):
                        new_val = what_value(db_rec["value"].tostring(), source="%s_table" % (short))
                    elif short == "int":
                        new_val = what_value(int(db_rec["value"]), source="%s_table" % (short))
                    else:
                        new_val = what_value(db_rec["value"], source="%s_table" % (short))
                    new_val.set_is_global(var_global)
                    if local_host_name == self.short_host_name:
                        if var_name.upper() in self and self.is_fixed(var_name.upper()):
                            # present value is fixed, keep value, only copy global / local status
                            self.copy_flag(var_name.upper(), new_val)
                        else:
                            self[var_name.upper()] = new_val
                    elif local_host_name == "":
                        l_var_wo_host[var_name.upper()] = new_val
            # check for vars to insert
            for wo_var_name, wo_var in l_var_wo_host.iteritems():
                if not wo_var_name in self or self.get_source(wo_var_name) == "default":
                    self[wo_var_name] = wo_var
    def has_key(self, var_name):
        return var_name in self.__config_vars
    def __contains__(self, var_name):
        return var_name in self.__config_vars
    def keys(self):
        return self.__config_vars.keys()
    def is_fixed(self, var_name):
        return self.__config_vars[var_name].is_fixed()
    def copy_flag(self, var_name, new_var):
        self.__config_vars[var_name].set_is_global(new_var.is_global())
    def get_source(self, var_name):
        return self.__config_vars[var_name].get_source()
    def __setitem__(self, var_name, var_value):
        self.__config_vars[var_name] = var_value
    def __getitem__(self, var_name):
        return self.__config_vars[var_name].get_value()
    def _set_srv_info(self, dc, srv_rec, sdsc_eq, sdsc_neq, s_info_str):
        self.server_device_idx, self.server_config_idx = (srv_rec["device_idx"], srv_rec["device"])
        dc.execute("SELECT d.name FROM device d WHERE d.device_idx=%d" % (self.server_config_idx))
        self.server_config_name = dc.fetchone()["name"]
        self.config_idx = srv_rec["new_config"]
        self.config_name = srv_rec["confname"]
        if self.server_device_idx == self.server_config_idx:
            self.server_origin = sdsc_eq
        else:
            self.server_origin = sdsc_neq
        self.server_info_str = "%s '%s'-server via %s" % (self.server_origin,
                                                          self.__server_type_info_str,
                                                          s_info_str)
    def _fetch_network_info(self, dc, **args):
        if not self.__network_info_fetched or args.get("force", False):
            dc.execute("SELECT d.device_idx, n.netdevice_idx, n.devname, i.netip_idx, i.ip, nt.identifier FROM network nw, network_type nt, device d LEFT JOIN netdevice n ON d.device_idx=n.device LEFT JOIN netip i ON i.netdevice=n.netdevice_idx WHERE d.name=%s AND i.network=nw.network_idx AND nw.network_type=nt.network_type_idx", (self.short_host_name))
            # clear old instances
            self.ip_list, self.netdevice_idx_list = ([], [])
            self.netdevice_ip_lut, self.ip_netdevice_lut, self.ip_identifier_lut, self.identifier_ip_lut = ({}, {}, {}, {})
            for db_rec in dc.fetchall():
                if db_rec["ip"]:
                    # only check these with a valid ip
                    if db_rec["netdevice_idx"] not in self.netdevice_idx_list:
                        self.netdevice_idx_list.append(db_rec["netdevice_idx"])
                    if db_rec["ip"] not in self.ip_list:
                        self.ip_list.append(db_rec["ip"])
                    self.netdevice_ip_lut.setdefault(db_rec["netdevice_idx"], []).append(db_rec["ip"])
                    self.ip_netdevice_lut[db_rec["ip"]] = db_rec["netdevice_idx"]
                    self.ip_identifier_lut[db_rec["ip"]] = db_rec["identifier"]
                    self.identifier_ip_lut.setdefault(db_rec["identifier"], []).append(db_rec["ip"])
            self.__network_info_fetched = True
            #print self.netdevice_ip_lut, self.ip_netdevice_lut
    def _db_check_ip(self, dc):
        # check for virtual-device
        dc.execute("SELECT d.name, d.device_idx, dc.new_config, c.name AS confname, dc.device, i.ip FROM netip i " + \
                   "INNER JOIN netdevice n INNER JOIN device_config dc INNER JOIN new_config c INNER JOIN device d INNER JOIN device_group dg " + \
                   "LEFT JOIN device d2 ON d2.device_idx=dg.device WHERE d.device_group=dg.device_group_idx AND n.device=d.device_idx AND i.netdevice=n.netdevice_idx " + \
                   "AND (d2.device_idx=dc.device OR n.device=dc.device) AND dc.new_config=c.new_config_idx AND c.name%s" % (self.__match_str))
        all_ips_dict = {}
        for db_rec in [y for y in dc.fetchall() if y["ip"] != "127.0.0.1"]:
            if db_rec["ip"] not in self.ip_list:
                all_ips_dict[db_rec["ip"]] = {"device_idx" : db_rec["device_idx"],
                                              "device"     : db_rec["device"],
                                              "new_config" : db_rec["new_config"],
                                              "name"       : db_rec["name"],
                                              "confname"   : db_rec["confname"]}
        c_stat, out = commands.getstatusoutput("/sbin/ifconfig")
        if not c_stat:
            self_ips = []
            for line in [x for x in [y.strip() for y in out.strip().split("\n")] if x.startswith("inet")]:
                ip_m = re.match("^inet.*addr:(?P<ip>\S+)\s+.*$", line)
                if ip_m:
                    self_ips.append(ip_m.group("ip"))
            for ai in all_ips_dict.keys():
                if ai in self_ips:
                    #dc.execute("SELECT d.device_idx FROM device d WHERE d.name='%s'" % (short_host_name))
                    self.num_servers = 1
                    self._set_srv_info(dc, all_ips_dict[ai], "virtual", "virtual meta", "IP-address %s" % (ai))
                    break
    def get_route_to_other_device(self, dc, other, **args):
        # at first fetch the network info if necessary
        self._fetch_network_info(dc, force=True)
        other._fetch_network_info(dc, force=True)
        # format of return list: value, network_id, (self.netdevice_idx, [list of self.ips]), (other.netdevice_idx, [list of other.ips])
        ret_list = []
        if self.netdevice_idx_list and other.netdevice_idx_list:
            # skip if any of both netdevice_idx_lists are empty
            # get peer_information
            sql_str = "SELECT * FROM hopcount WHERE (%s) AND (%s) ORDER BY value" % (" OR ".join(["s_netdevice=%d" % (idx) for idx in self.netdevice_idx_list]),
                                                                                     " OR ".join(["d_netdevice=%d" % (idx) for idx in other.netdevice_idx_list]))
            dc.execute(sql_str)
            for db_rec in dc.fetchall():
                # dicts identifier -> ips
                source_ip_lut, dest_ip_lut = ({}, {})
                for s_ip in self.netdevice_ip_lut[db_rec["s_netdevice"]]:
                    source_ip_lut.setdefault(self.ip_identifier_lut[s_ip], []).append(s_ip)
                for d_ip in other.netdevice_ip_lut[db_rec["d_netdevice"]]:
                    dest_ip_lut.setdefault(other.ip_identifier_lut[d_ip], []).append(d_ip)
                common_identifiers = [key for key in source_ip_lut.keys() if key in dest_ip_lut]
                if common_identifiers:
                    for act_id in common_identifiers:
                        add_actual = True
                        if "filter_ip" in args:
                            if args["filter_ip"] not in source_ip_lut[act_id] and args["filter_ip"] not in dest_ip_lut[act_id]:
                                add_actual = False
                        if add_actual:
                            ret_list.append((db_rec["value"],
                                             act_id,
                                             (db_rec["s_netdevice"], source_ip_lut[act_id]),
                                             (db_rec["d_netdevice"], dest_ip_lut[act_id])))
                else:
                    if args.get("allow_route_to_other_networks", False):
                        if "p" in dest_ip_lut and "o" in source_ip_lut:
                            add_actual = True
                            if "filter_ip" in args:
                                if args["filter_ip"] not in source_ip_lut["o"] and args["filter_ip"] not in dest_ip_lut["p"]:
                                    add_actual = False
                            if add_actual:
                                ret_list.append((db_rec["value"],
                                                 "o",
                                                 (db_rec["s_netdevice"], source_ip_lut["o"]),
                                                 (db_rec["d_netdevice"], dest_ip_lut["p"])))
        return ret_list
    def report(self):
        return "short_host_name is %s (idx %d), server_origin is %s, server_device_idx is %d, server_config_idx is %d, info_str is \"%s\"" % (self.short_host_name,
                                                                                                                                              self.device_idx,
                                                                                                                                              self.server_origin,
                                                                                                                                              self.server_device_idx,
                                                                                                                                              self.server_config_idx,
                                                                                                                                              self.server_info_str)
        
class device_with_config(object):
    def __init__(self, config_name, dc, **args):
        self.__config_name = config_name
        if self.__config_name.count("%"):
            self.__match_str = " LIKE('%s')" % (self.__config_name)
        else:
            self.__match_str = "='%s'" % (self.__config_name)
        self._check(dc, **args)
    def _check(self, dc, **args):
        self.__dict = {"device" : {},
                       "config" : {}}
        # locates devices with the given config_name
        # right now we are fetching a little bit too much ...
        sql_str = "SELECT d.name, d.device_idx, dc.new_config, c.name AS confname, dc.device FROM device d " + \
            "INNER JOIN device_config dc INNER JOIN new_config c INNER JOIN device_group dg LEFT JOIN device d2 ON d2.device_idx=dg.device " + \
            "WHERE d.device_group=dg.device_group_idx AND dc.new_config=c.new_config_idx AND (dc.device=d.device_idx OR dc.device=d2.device_idx) AND c.name%s" % (self.__match_str)
        dc.execute(sql_str)
        for db_rec in dc.fetchall():
            conf_server_struct = server_check(dc=dc,
                                              server_type=db_rec["confname"],
                                              short_host_name=db_rec["name"],
                                              fetch_network_info=True)
            self.__dict["config"].setdefault(db_rec["confname"], []).append(conf_server_struct)
            self.__dict["device"][db_rec["name"]] = server_check(dc=dc,
                                                                 server_type=db_rec["confname"],
                                                                 short_host_name=db_rec["name"],
                                                                 fetch_network_info=True)
        self.set_key_type("device")
    def set_key_type(self, k_type):
        self.__key_type = k_type
    def keys(self):
        return self.__dict[self.__key_type].keys()
    def has_key(self, key):
        return key in self.__dict[self.__key_type]
    def __contains__(self, key):
        return key in self.__dict[self.__key_type]
    def get(self, key, def_value):
        return self.__dict[self.__key_type].get(key, def_value)
    def __getitem__(self, key):
        return self.__dict[self.__key_type][key]
    def __len__(self):
        return len(self.__dict[self.__key_type].keys())

if __name__ == "__main__":
    print "Loadable module, exiting ..."
    sys.exit(1)
