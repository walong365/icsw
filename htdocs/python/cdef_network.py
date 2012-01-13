#!/usr/bin/python -Ot
# -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
# 
# This file belongs to webfrontend
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
""" basic definitions for network handling """

import re
import cdef_basics
import tools
import ipvx_tools

def is_number(num):
    if type(num) in [type(0), type(0L)]:
        return True
    else:
        if len(num) > 1 and num.startswith("-"):
            num = num[1:]
        return num.isdigit()

def is_mac_address(mac, mac_bytes=6):
    return re.match("^%s$" % (":".join(["([a-f0-9]{2})"] * mac_bytes)), mac.lower())
    
class network_device_type(cdef_basics.db_obj):
    def __init__(self, netname, ndt_idx, init_dict={}):
        cdef_basics.db_obj.__init__(self, netname, ndt_idx, "ndt")
        self.init_sql_changes({"table" : "network_device_type",
                               "idx"   : self.idx})
        self.set_valid_keys({"identifier"  : "s",
                             "description" : "s",
                             "mac_bytes"   : "i"},
                            ["network_device_type_idx"])
        self.count_nd = 0
        self.count_nw = 0
        if init_dict:
            self.set_parameters(init_dict)
    def copy_instance(self):
        new_nw = network_device_type(self.get_name(), self.get_idx())
        new_nw.copy_keys(self)
        return new_nw

class network(cdef_basics.db_obj):
    def __init__(self, netname, network_idx, init_dict={}):
        cdef_basics.db_obj.__init__(self, netname, network_idx, "n")
        self.init_sql_changes({"table" : "network",
                               "idx"   : self.idx})
        self.set_valid_keys({"name"                       : "s",
                             "identifier"                 : "s",
                             "info"                       : "s",
                             "postfix"                    : "s",
                             "gw_pri"                     : "i",
                             "penalty"                    : "i",
                             "network"                    : "s",
                             "netmask"                    : "s",
                             "broadcast"                  : "s",
                             "gateway"                    : "s",
                             "short_names"                : "i",
                             "write_bind_config"          : "i",
                             "write_other_network_config" : "i",
                             "network_type"               : "i",
                             "master_network"             : "i",
                             "start_range"                : "s",
                             "end_range"                  : "s",
                             "nw_types"                   : ("f", "network_network_device_type", "network_device_type")},
                            ["network_idx"])
        self.__nw_types = []
        self.usecount = 0
        self["nw_types"] = []
        if init_dict:
            self.set_parameters(init_dict)
    def copy_instance(self):
        new_nw = network(self.get_name(), self.get_idx())
        new_nw.copy_keys(self)
        return new_nw
    def set_parameters(self, stuff):
        cdef_basics.db_obj.set_parameters(self, stuff)
        for db_rec in stuff["network_device_types"]:
            self.add_network_device_type(db_rec)
    def add_network_device_type(self, db_rec):
        if db_rec not in self.__nw_types:
            self.__nw_types.append(db_rec)
            self["nw_types"] = self.__nw_types
    def has_network_device_type(self, db_rec):
        return db_rec in self.__nw_types
    def remove_network_device_type(self, db_rec):
        if db_rec in self.__nw_types:
            self.__nw_types.remove(db_rec)
            self["nw_types"] = self.__nw_types
    def validate_master_type(self, new_dict, old_dict, stuff):
        net_t_tree = stuff["type_tree"]
        new_type, new_master = (new_dict["network_type"], new_dict["master_network"])
        new_id = net_t_tree[new_type]["identifier"]
        if new_id == "s" and not new_master:
            return 2, "need master network", {"reset" : 1}
        elif new_id != "s" and new_master:
            return 2, "master forbidden", {"reset" : 1}
        else:
            return 0, "ok", {}
    def html_out_filter_network_type(self, val, stuff):
        if val:
            return stuff["type_tree"][val]["description"]
        else:
            return "&lt;key %s not found&gt;" % (str(val))
                            
class netdevice(cdef_basics.db_obj):
    def __init__(self, devname, netdevice_idx):
        cdef_basics.db_obj.__init__(self, devname, netdevice_idx, "n")
        self.ips, self.ip_lut = ({}, {})
        self.peers = {}
        self.init_sql_changes({"table" : "netdevice",
                               "idx" : self.idx})
        self.set_valid_keys({"device"              : "i",
                             "netdevice_idx"       : "i",
                             "devname"             : "s",
                             "macadr"              : "s",
                             "driver_options"      : "s",
                             "netdevice_speed"     : "i",
                             "driver"              : "s",
                             "routing"             : "b",
                             "description"         : "s",
                             "penalty"             : "i",
                             "dhcp_device"         : "b",
                             "ethtool_options"     : "s",
                             "fake_macadr"         : "s",
                             "network_device_type" : "i",
                             "is_bridge"           : "i",
                             "bridge_name"         : "s",
                             "vlan_id"             : "i"},
                            ["netdevice_idx", "device"])
        self.set_new_netip_suffix()
    def copy_instance(self):
        new_nd = netdevice(self.get_name(), self.get_idx())
        new_nd.copy_keys(self)
        return new_nd
    def get_all_defined_ips(self, ignore_idx=None):
        if ignore_idx:
            return [x for x in self.ip_lut.keys() if self.ip_lut[x] != ignore_idx]
        else:
            return self.ip_lut.keys()
    def get_ip_idxs(self):
        return self.ips.keys()
    def has_ip_in_production_network(self):
        pass
    def add_network_stuff(self, in_dict):
        if type(in_dict) == type({}):
            i_idx = in_dict.get("netip_idx", 0)
            if i_idx:
                if not self.ips.has_key(i_idx) and in_dict["ip"] not in self.ip_lut.keys():
                    new_ip = netip(in_dict["ip"], in_dict["netip_idx"])
                    if i_idx < 0:
                        new_ip.set_suffix(self.get_new_netip_suffix())
                    new_ip.set_parameters(in_dict)
                    self.ips[i_idx] = new_ip
                    self.ip_lut[in_dict["ip"]] = i_idx
        else:
            # add an netip-object
            if not in_dict.get_name() in self.ip_lut.keys():
                i_idx = in_dict.get_idx()
                self.ips[i_idx] = in_dict
                self.ip_lut[in_dict.get_name()] = i_idx
    def set_values_as_default(self):
        for act_val in self.ips.values():
            act_val.act_values_are_default()
        self.act_values_are_default()
    def add_netip(self, n_ip):
        self.ips[n_ip.get_idx()] = n_ip
        self.ip_lut[n_ip.get_name()] = n_ip.get_idx()
    def delete_ip(self, ip_idx):
        del self.ip_lut[self.ips[ip_idx].get_name()]
        del self.ips[ip_idx]
    def enqueue_new_netip(self, n_ip, has_old=1):
        new_ip = n_ip["ip"]
        new_idx = n_ip.get_idx()
        if has_old:
            old_ip  = "0.0.0.0"
            old_idx = -1
            del self.ip_lut[old_ip]
            del self.ips[old_idx]
        n_ip.set_name(new_ip)
        self.ip_lut[new_ip] = n_ip.get_idx()
        self.ips[new_idx] = n_ip
    def get_vlan_id(self):
        return self["vlan_id"]
    def get_penalty(self, peer=0):
        if peer:
            return self.peers[peer]["penalty"]
        else:
            return self["penalty"]
    def get_number_of_ips(self):
        return len([x for x in self.ips.keys() if x > 0])
    def get_sorted_netip_list(self):
        new_netip = [x for x in self.ip_lut.keys() if x == "0.0.0.0"]
        if new_netip:
            new_netip = new_netip[0]
        else:
            new_netip = None
        ndl = [x for x in self.ip_lut.keys() if x!= new_netip]
        ndl.sort()
        if new_netip:
            ndl.append(new_netip)
        return [self.ips[self.ip_lut[x]] for x in ndl]
    def set_new_netip_suffix(self, nnip = None):
        if nnip:
            self.new_netip_suffix = nnip
        else:
            self.new_netip_suffix = "%sni" % (self.get_suffix())
            #print "Setting new_netip_suffix to %s<br>" % (self.new_netip_suffix)
            if self.ips.has_key(-1):
                self.ips[-1].set_suffix(self.new_netip_suffix)
    def get_new_netip_suffix(self):
        return self.new_netip_suffix
    def getset_autoneg_value(self, val = None, stuff=None):
        if val is None:
            return self["ethtool_options"] & 3
        else:
            self["ethtool_options"] = (self["ethtool_options"] & ~3)|int(val)
    def getset_duplex_value(self, val = None, stuff=None):
        if val is None:
            return (self["ethtool_options"] >> 2) & 3
        else:
            self["ethtool_options"] = (self["ethtool_options"] & (~12))|(int(val) << 2)
    def getset_speed_value(self, val=None, stuff=None):
        if val is None:
            return self["ethtool_options"] >> 4
        else:
            self["ethtool_options"] = (self["ethtool_options"] & 15)|(int(val) << 4)
    def html_out_filter_ethtool_options(self, val, stuff):
        int_val = int(val)
        autoneg_idx =  int_val       & 3
        duplex_idx  = (int_val >> 2) & 3
        speed_idx   =  int_val >> 4   
        return "autoneg %s, duplex %s, speed %s" % (stuff["autoneg_dict"][autoneg_idx],
                                                    stuff["duplex_dict" ][duplex_idx ],
                                                    stuff["speed_dict"  ][speed_idx  ])
    def html_out_filter_netdevice_speed(self, val, stuff):
        return stuff["speed_dict"].get(val, "<no info>")
    def add_peer_information(self, idx, other, penalty):
        self.peers[idx] = {"other" : other, "penalty" : penalty}
    def delete_peer(self, idx):
        del self.peers[idx]
    def get_peers(self, only_foreign=0):
        if only_foreign:
            return [x["other"] for x in self.peers.values() if x["other"] != self.get_idx()]
        else:
            return [x["other"] for x in self.peers.values()]
    def get_peer_idxs(self, only_foreign=0):
        if only_foreign:
            return [k for k, x in self.peers.iteritems() if x["other"] != self.get_idx()]
        else:
            return [k for k, x in self.peers.iteritems()]
    def get_peer_suffix(self, p_idx):
        return "p%s%d" % (self.get_suffix(), p_idx)
    def get_number_of_peers(self, only_foreign=0):
        if only_foreign:
            return len([1 for x in self.peers.values() if x["other"] != self.get_idx()])
        else:
            return len(self.peers.keys())
    def get_peer_endpoint(self, pe):
        return self.peers[pe]["other"]
    def get_peer_information(self, pe, fe_dict):
        ret_str = "%s %d %s" % (self.get_peer_pre_information(pe, fe_dict),
                            self.peers[pe]["penalty"],
                            self.get_peer_post_information(pe, fe_dict))
        return ret_str
    def get_peer_pre_information(self, pe, fe_dict):
        other = self.peers[pe]["other"]
        ret_str = "with penalty %d (%d + " % (self.get_penalty()+self.peers[pe]["penalty"]+fe_dict[other]["penalty"],
                                              self.get_penalty())
        return ret_str
    def get_peer_post_information(self, pe, fe_dict):
        other = self.peers[pe]["other"]
        ret_str = " + %d) to %s on %s" % (fe_dict[other]["penalty"],
                                          fe_dict[other]["devname"],
                                          fe_dict[other]["name"])
        return ret_str
    def set_penalty(self, p_idx, p_p=None):
        if p_p is None:
            self["penalty"] = p_idx
        else:
            self.peers[p_idx]["penalty"] = p_p
    def remove_defective_peers(self, missing):
        del_k = [k for k, x in self.peers.iteritems() if x["other"] in missing]
        for k in del_k:
            del self.peers[k]
    def get_ip(self, ip_idx):
        return self.ips[ip_idx]
    def check_for_virtual_netdevice(self):
        if self["devname"].count(":"):
            self.is_virtual = True
        else:
            self.is_virtual = False
    def validate_devmac(self, new_dict, old_dict, stuff):
        act_id_str = stuff["net_dt_tree"].get(self["network_device_type"], {}).get("identifier", "")
        #print "*", act_id_str
        if self["is_bridge"]:
            return 0, "ok", {}
        else:
            old_name, old_mac, old_fakemac = (old_dict["devname"], old_dict["macadr"], old_dict["fake_macadr"])
            new_name, new_mac, new_fakemac = (new_dict["devname"], new_dict["macadr"], new_dict["fake_macadr"])
            ndev_match = re.match("^(?P<prefix>\D+)(?P<number>\d*):*(?P<virtual>\S*)$", new_name)
            net_dt_tree = stuff["net_dt_tree"]
            all_ndt_identifiers = [x["identifier"] for x in net_dt_tree.values()]
            #print stuff, stuff["act_dev"].get_netdevice_names(self.get_idx()), "<br>"
            if stuff["hw_refreshed"]:
                return 0, "ok", {"reset" : 1, "change_dict" : {"macadr"      : old_dict["macadr"],
                                                               "fake_macadr" : old_dict["fake_macadr"]}}
            if not ndev_match:
                return 2, "parse error", {"no_log" : ["macadr", "fake_macadr"]}
            elif ndev_match.group("prefix") not in all_ndt_identifiers:
                return 2, "'%s' not in list of valid identifers (%s)" % (ndev_match.group("prefix"), ", ".join(all_ndt_identifiers)), {"no_log" : ["macadr", "fake_macadr"]}
            elif new_name in stuff["act_dev"].get_netdevice_names(self.get_idx()):
                return 2, "'%s' already used" % (new_name), {"no_log" : ["macadr", "fake_macadr"]}
            else:
                net_dt_idx   = stuff["net_dt_lut"][ndev_match.group("prefix")]
                net_dt_stuff = net_dt_tree[net_dt_idx]
                mac_bytes = net_dt_stuff["mac_bytes"]
                empty_mac = ":".join(["00"] * mac_bytes)
                ib_style = new_name.startswith("ib")
                if ib_style and not (is_mac_address(new_mac, mac_bytes) and is_mac_address(new_fakemac, mac_bytes)):
                    empty_short_mac = ":".join(["00"] * 6)
                    if new_mac == empty_short_mac and new_fakemac == empty_short_mac:
                        # set network_device_type
                        self["network_device_type"] = net_dt_idx
                        return 0, "ok", {"reset" : 1, "change_dict" : {"macadr"      : empty_mac,
                                                                       "fake_macadr" : empty_mac}}
                    else:
                        return 2, "no valid infiniband-style mac or fake_mac address", {"reset" : 1, "no_log" : ["devname"]}
                elif mac_bytes == 6 and not (is_mac_address(new_mac, mac_bytes) and is_mac_address(new_fakemac, mac_bytes)):
                    return 2, "no valid mac %s or fake_mac %s address" % (new_mac, new_fakemac), {"reset" : 1, "no_log" : ["devname"]}
                else:
                    # set network_device_type
                    self["network_device_type"] = net_dt_idx
                    return 0, "ok", {"reset" : 1, "change_dict" : {"devname"     : new_dict["devname"],
                                                                   "macadr"      : new_dict["macadr"],
                                                                   "fake_macadr" : new_dict["fake_macadr"]}}
        
    #def validate_macadr(self, new_val, old_val, stuff):
    #    if not is_mac_address(new_val):
    #        return 2, "no valid mac address", {}
    #    else:
    #        return 0, "ok", {}
##     def validate_speed(self, new_val, old_val, stuff):
##         if is_number(new_val):
##             if int(new_val) >= 0:
##                 return 0, "ok", {"integer" : 1, "reset" : 1}
##             else:
##                 return 1, "must be > 0", {}
##         else:
##             return 2, "must be an integer", {}
    def validate_penalty(self, new_val, old_val, stuff):
        if is_number(new_val):
            if int(new_val) >= 0:
                return 0, "ok", {"integer" : 1, "reset" : 1}
            else:
                return 1, "must be >= 0", {}
        else:
            return 2, "must be an integer", {}
    def validate_vlan_id(self, new_val, old_val, stuff):
        if is_number(new_val):
            if int(new_val) >= 0:
                return 0, "ok", {"integer" : 1, "reset" : 1}
            else:
                return 1, "must be >= 0", {}
        else:
            return 2, "must be an integer", {}
        
class netip(cdef_basics.db_obj):
    def __init__(self, ip, ip_idx):
        cdef_basics.db_obj.__init__(self, ip, ip_idx, "i")
        self.init_sql_changes({"table" : "netip",
                               "idx"   : self.idx})
        self.set_valid_keys({"ip"         : "s",
                             "netdevice"  : "i",
                             "network"    : "i",
                             "alias"      : "s",
                             "alias_excl" : "i",
                             #"penalty"   : "i",
                             "netip_idx"  : "i"},
                            ["netip_idx", "netdevice"])
        self["ip"] = ip
    def copy_instance(self):
        new_ip = netip(self.get_name(), self.get_idx())
        new_ip.copy_keys(self)
        return new_ip
    def get_sql_string(self):
        return ", ".join(["ip='%s'" % (self.get_name())] +
                         ["%s=%s" % (x, self[x]) for x in ["netdevice", "penalty", "network"]])
    def html_in_filter_network(self, val, stuff):
        if val and val in [str(x["network_idx"]) for x in stuff["net_tree"].values()]:
            return val
        else:
            return 0
    def html_out_filter_network(self, val, stuff):
        if val:
            return "'%s'" % (stuff["net_tree"].get(int(val), {"identifier":"no net found"})["identifier"])
        else:
            return "autoselect"
    def validate_netip(self, new_dict, old_dict, stuff):
        old_ip, old_net = (old_dict["ip"], old_dict["network"])
        new_ip, new_net = (new_dict["ip"], int(new_dict["network"]))
        if new_ip == "0.0.0.0" and new_net == 0:
            return 0, "ok", {"skip_set" : 1}
        elif new_ip == "0.0.0.0" and new_net:
            target_net = stuff["net_tree"][new_net]
            start_range, end_range = (ipvx_tools.ipv4(target_net["start_range"]),
                                      ipvx_tools.ipv4(target_net["end_range"]))
            if not start_range or not end_range:
                return 2, "no free range defined for auto_ip", {"reset" : 1}
            else:
                first_ip = start_range
                last_ip = end_range
                search_ip = first_ip
                while True:
                    if search_ip == last_ip:
                        break
                    elif str(search_ip) in stuff["used_ips"][new_net]:
                        search_ip += ipvx_tools.ipv4("0.0.0.1")
                    else:
                        break
                if search_ip == last_ip:
                    return 2, "no free netip found in range %s - %s" % (str(start_range),
                                                                        str(end_range)), {"reset" : 1}
                else:
                    return 0, "ok found free IP address", {"reset" : 1, "change_dict" : {"ip" : str(search_ip)}}
        try:
            new_ipv4 = ipvx_tools.ipv4(new_ip)
        except ValueError:
            return 2, "no IPV4 address", {"no_log" : ["network"]}
        else:
            if new_ip in stuff["netdevice"].get_all_defined_ips(self.get_idx()):
                return 2, "IP already defined on this netdevice", {"no_log" : ["network"]}
            else:
                if stuff["net_tree"].has_key(int(new_net)) and new_ipv4.network_matches(stuff["net_tree"][int(new_net)]):
                    t_network = int(new_net)
                else:
                    t_network = new_ipv4.find_matching_network(stuff["net_tree"])
                if t_network:
                    t_net_idx = t_network
                    #print ":::",old_net, ":", new_net, ":",t_net_idx, ":",t_network, "<br>"
                    #print ":::",type(old_net), ":",type(new_net), ":",type(t_net_idx), ":",type(t_network), "<br>"
                    if new_net == t_net_idx:
                        return 0, "ok", {"reset" : 1, "change_dict" : {"ip" : str(new_ipv4)}}
                    elif new_net == old_net or new_net == 0:
                        return 1, "changed network", {"reset" : 1, "change_dict" : {"network" : t_net_idx, "ip" : str(new_ipv4)}}
                    else:
                        if old_ip == new_ip:
                            return 2, "no matching network defined", {"reset" : 1, "no_log" : ["ip"]}
                        else:
                            return 2, "no matching network defined", {"reset" : 1}
                else:
                    return 2, "no matching network found", {"reset" : 1}
    def getset_network(self, val = None, stuff=None):
        if val is None:
            return self["network"]
        else:
            self["network"] = int(val)
        
