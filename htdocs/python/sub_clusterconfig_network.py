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

import logging_tools
import html_tools
import tools
import sys
import cdef_network
import cdef_device
import ipvx_tools
import random
import pprint

RANDOM_XEN_MAC_PREFIX = "00:16:3e:00"

def add_default_networks(net_t_tree, net_dt_tree, dc):
    def net_ins(dc, in_dict):
        in_keys = in_dict.keys()
        dc.execute("INSERT INTO network SET %s" % (", ".join(["%s=%%s" % (k) for k in in_keys])), tuple([in_dict[k] for k in in_keys]))
    net_t_lut  = dict([(v["identifier"], k) for k, v in net_t_tree.iteritems()])
    net_dt_lut = dict([(v["identifier"], k) for k, v in net_dt_tree.iteritems()])
    lo_net_dict = {"identifier"     : "loopback",
                   "network_type"   : net_t_lut["l"],
                   "master_network" : 0,
                   "short_names"    : 1,
                   "name"           : "localdomain",
                   "penalty"        : 1,
                   "postfix"        : "",
                   "info"           : "Loopback network",
                   "network"        : "127.0.0.0",
                   "netmask"        : "255.0.0.0",
                   "broadcast"      : "127.255.255.255",
                   "gateway"        : "0.0.0.0",
                   "gw_pri"         : 0}
    prod_net_dict = {"identifier"     : "prod",
                     "network_type"   : net_t_lut["p"],
                     "master_network" : 0,
                     "short_names"    : 1,
                     "name"           : "init.prod",
                     "penalty"        : 1,
                     "postfix"        : "",
                     "info"           : "Production network",
                     "network"        : "172.16.0.0",
                     "netmask"        : "255.255.0.0",
                     "broadcast"      : "172.16.255.255",
                     "gateway"        : "0.0.0.0",
                     "gw_pri"         : 0}
    boot_net_dict = {"identifier"     : "boot",
                     "network_type"   : net_t_lut["b"],
                     "master_network" : 0,
                     "short_names"    : 1,
                     "name"           : "init.boot",
                     "penalty"        : 1,
                     "postfix"        : "i",
                     "info"           : "Boot/Maintenance network",
                     "network"        : "172.17.0.0",
                     "netmask"        : "255.255.0.0",
                     "broadcast"      : "172.17.255.255",
                     "gateway"        : "0.0.0.0",
                     "gw_pri"         : 0}
    mpi_net_dict = {"identifier"     : "mpi",
                    "network_type"   : net_t_lut["s"],
                    "master_network" : 0,
                    "short_names"    : 1,
                    "name"           : "init.mpi",
                    "penalty"        : 1,
                    "postfix"        : "mp",
                    "info"           : "MPI network",
                    "network"        : "10.0.0.0",
                    "netmask"        : "255.255.0.0",
                    "broadcast"      : "10.0.255.255",
                    "gateway"        : "0.0.0.0",
                    "gw_pri"         : 0}
    ext_net_dict = {"identifier"     : "ext",
                    "network_type"   : net_t_lut["o"],
                    "master_network" : 0,
                    "short_names"    : 0,
                    "name"           : "init.at",
                    "penalty"        : 1,
                    "postfix"        : "",
                    "info"           : "External network",
                    "network"        : "192.168.1.0",
                    "netmask"        : "255.255.255.0",
                    "broadcast"      : "192.168.1.255",
                    "gateway"        : "192.168.1.1",
                    "gw_pri"         : 0}
    apc_net_dict = {"identifier"     : "apc",
                    "network_type"   : net_t_lut["o"],
                    "master_network" : 0,
                    "short_names"    : 1,
                    "name"           : "init.apc",
                    "penalty"        : 1,
                    "postfix"        : "",
                    "info"           : "APC network",
                    "network"        : "172.18.0.0",
                    "netmask"        : "255.255.0.0",
                    "broadcast"      : "172.18.255.255",
                    "gateway"        : "0.0.0.0",
                    "gw_pri"         : 0}
    # not beautifull but working
    net_ins(dc, lo_net_dict)
    dc.execute("INSERT INTO network_network_device_type SET network=%d, network_device_type=%d" % (dc.insert_id(), net_dt_lut["lo"]))
    net_ins(dc, prod_net_dict)
    mpi_net_dict["master_network"] = dc.insert_id()
    dc.execute("INSERT INTO network_network_device_type SET network=%d, network_device_type=%d" % (dc.insert_id(), net_dt_lut["eth"]))
    net_ins(dc, boot_net_dict)
    dc.execute("INSERT INTO network_network_device_type SET network=%d, network_device_type=%d" % (dc.insert_id(), net_dt_lut["eth"]))
    net_ins(dc, mpi_net_dict)
    dc.execute("INSERT INTO network_network_device_type SET network=%d, network_device_type=%d" % (dc.insert_id(), net_dt_lut["eth"]))
    net_ins(dc, ext_net_dict)
    dc.execute("INSERT INTO network_network_device_type SET network=%d, network_device_type=%d" % (dc.insert_id(), net_dt_lut["eth"]))
    net_ins(dc, apc_net_dict)
    dc.execute("INSERT INTO network_network_device_type SET network=%d, network_device_type=%d" % (dc.insert_id(), net_dt_lut["eth"]))

class new_network_vs(html_tools.validate_struct):
    def __init__(self, req, network_type_field, network_type_dict, master_list, ntt_dict):
        new_dict = {"identifier"                 : {"he"  : html_tools.text_field(req, "id" , size=120, display_len=20),
                                                    "new" : 1,
                                                    "vf"  : self.validate_id,
                                                    "def" : ""},
                    "mnt"                        : (self.validate_master_type, {"network_type"   : {"he"  : network_type_field,
                                                                                                    "def" : [k for k, v in ntt_dict.iteritems() if v["identifier"] == "p"][0]},
                                                                                "master_network" : {"he"  : master_list,
                                                                                                    "def" : 0}}),
                    "name"                       : {"he"  : html_tools.text_field(req, "nn" ,  size=60, display_len=20),
                                                    "vf"  : self.validate_name,
                                                    "def" : "test.net"},
                    "postfix"                    : {"he"  : html_tools.text_field(req, "sf" ,   size=4,  display_len=4),
                                                    "vf"  : self.validate_postfix,
                                                    "def" : ""},
                    "gw_pri"                     : {"he"  : html_tools.text_field(req, "gwp",   size=6,  display_len=6),
                                                    "vf"  : self.validate_gw_pri,
                                                    "def" : 0},
                    "info"                       : {"he"  : html_tools.text_field(req, "ni" , size=120, display_len=20),
                                                    "def" : "New network"},
                    "penalty"                    : {"he"  : html_tools.text_field(req, "pe" ,   size=6,  display_len=6),
                                                    "vf"  : self.validate_penalty,
                                                    "def" : 0},
                    "nwc"                        : (self.validate_network, {"network"   : {"he"  : html_tools.text_field(req, "nw", size=15, display_len=15),
                                                                                           "def" : "192.168.1.0"},
                                                                            "netmask"   : {"he"  : html_tools.text_field(req, "nm", size=15, display_len=15),
                                                                                           "def" : "255.255.255.0"},
                                                                            "broadcast" : {"he"  : html_tools.text_field(req, "bc", size=15, display_len=15),
                                                                                           "def" : "192.168.1.255"},
                                                                            "gateway"   : {"he"  : html_tools.text_field(req, "gw", size=15, display_len=15),
                                                                                           "def" : "0.0.0.0"}}),
                    "short_names"                : {"he"  : html_tools.checkbox(req, "sn"),
                                                    "def" : True},
                    "write_bind_config"          : {"he"  : html_tools.checkbox(req, "wb"),
                                                    "def" : True},
                    "write_other_network_config" : {"he"  : html_tools.checkbox(req, "wo"),
                                                    "def" : False},
                    "del"                        : {"he"  : html_tools.checkbox(req, "del"),
                                                    "del" : 1},
                    "ntc"                        : (self.validate_netdevice_type, dict([(k, {"he"   : html_tools.checkbox(req, "ndt%s" % (v["identifier"])),
                                                                                             "ndb"  : True,
                                                                                             "dbmr" : self.ndt_read_mapper}) for k, v in network_type_dict.iteritems()] + [("database_info", {"field_name" : "nw_types",
                                                                                                                                                                                              "def_name"   : "network_device_types",
                                                                                                                                                                                              "def"        : []})])),
                    "range"                      : (self.validate_range, {"start_range" : {"he"  : html_tools.text_field(req, "rs", size=15, display_len=15),
                                                                                           "def" : "0.0.0.0",
                                                                                           "pri" : -20},
                                                                          "end_range"   : {"he"  : html_tools.text_field(req, "re", size=15, display_len=15),
                                                                                           "def" : "0.0.0.0",
                                                                                           "pri" : -20}})}
        html_tools.validate_struct.__init__(self, req, "Network", new_dict)
        self.__ntc = network_type_dict
        self.__ntt = ntt_dict
    def validate_range(self):
        zero_ip = ipvx_tools.ipv4("0.0.0.0")
        ipv4_list = ["start_range", "end_range"]
        nw_ipv4, nm_ipv4 = (ipvx_tools.ipv4(self.new_val_dict["network"]),
                            ipvx_tools.ipv4(self.new_val_dict["netmask"]))
        ip_dict, err_list = ({}, [])
        for what in ipv4_list:
            try:
                ip_dict[what] = ipvx_tools.ipv4(self.new_val_dict[what])
            except ValueError:
                err_list.append(what)
        if err_list:
            raise ValueError, ("IPV4 error: %s" % (", ".join(err_list)), dict([(what, (self.old_val_dict[what], "IPV4", [(what, self.old_val_dict[what])])) for what in err_list]))
        if len([True for x in ipv4_list if not ip_dict[x]]) == 1:
            raise ValueError, ("need two valid IPV4 addresses for range", dict([(what, ("0.0.0.0", "IPV4", [(what, "0.0.0.0")])) for what in ipv4_list]))
        new_dict = {}
        for what in ipv4_list:
            if ip_dict[what] != zero_ip:
                if ip_dict[what] & nm_ipv4 != nw_ipv4:
                    new_dict[what] = (ip_dict[what] & ~nm_ipv4) | nw_ipv4
        if new_dict:
            raise ValueError, ("%s not in network range" % (", ".join(new_dict.keys())), dict([(k, (str(new_dict[k]), "IPV4", [(k, str(new_dict[k]))])) for k in new_dict.keys()]))
        if ip_dict["start_range"] > ip_dict["end_range"]:
            raise ValueError, ("swapping range parameters", {"end_range"   : (str(ip_dict["start_range"]), "range", [("end_range"  , str(ip_dict["start_range"]))]),
                                                             "start_range" : (str(ip_dict["end_range"])  , "range", [("start_range", str(ip_dict["end_range"]  ))])})
        for what in ipv4_list:
            self.new_val_dict[what] = str(ip_dict[what])
    def validate_master_type(self):
        self.old_b_val_dict["network_type"] = self.__ntt[self.old_val_dict["network_type"]]["description"]
        self.new_b_val_dict["network_type"] = self.__ntt[self.new_val_dict["network_type"]]["description"]
    def ndt_read_mapper(self, k):
        return k in self.old_val_dict["nw_types"]
    def validate_id(self):
        new_id = self.new_val_dict["identifier"]
        if new_id != new_id.strip():
            raise ValueError, "no spaces allowed"
        elif not new_id.strip() and self.get_db_obj().get_idx():
            raise ValueError, "must not be empty"
        elif new_id in self.names:
            raise ValueError, "already used"
    def validate_name(self):
        pass
    def validate_postfix(self):
        if not self.new_val_dict["postfix"] or self.new_val_dict["postfix"].isalnum():
            pass
        else:
            raise ValueError, "illegal postfix"
    def validate_gw_pri(self):
        if tools.is_number(self.new_val_dict["gw_pri"].strip()):
            self.new_val_dict["gw_pri"] = int(self.new_val_dict["gw_pri"].strip())
        else:
            raise ValueError, "not an integer"
    def validate_penalty(self):
        if tools.is_number(self.new_val_dict["penalty"].strip()):
            pen = int(self.new_val_dict["penalty"].strip())
            if pen >= 0:
                self.new_val_dict["penalty"] = pen
            else:
                raise ValueError, "must be >= 0"
        else:
            raise ValueError, "not an integer"
    def validate_network(self):
        ip_dict, err_list = ({}, [])
        ipv4_list = ["network", "netmask", "broadcast", "gateway"]
        for what in ipv4_list:
            try:
                ip_dict[what] = ipvx_tools.ipv4(self.new_val_dict[what])
            except ValueError:
                err_list.append(what)
        if err_list:
            raise ValueError, ("IPV4 error: %s" % (", ".join(err_list)), dict([(what, (self.old_val_dict[what], "IPV4", [(what, self.old_val_dict[what])])) for what in err_list]))
        elif ip_dict["network"] & ip_dict["netmask"] != ip_dict["network"]:
            raise ValueError, ("netmask / network mismatch", dict([(k, (self.old_val_dict[k], "IPV4", [(k, self.old_val_dict[k])])) for k in ["network"]]))
        elif ip_dict["network"] | (~ip_dict["netmask"]) != ip_dict["broadcast"]:
            raise ValueError, ("broadcast mismatch", dict([(k, (self.old_val_dict[k], "IPV4", [(k, self.old_val_dict[k])])) for k in ["broadcast"]]))
        elif (ip_dict["gateway"] & ip_dict["netmask"] != ip_dict["network"]) and ip_dict["gateway"] != ipvx_tools.ipv4("0.0.0.0"):
            raise ValueError, ("gateway mismatch", dict([(k, (self.old_val_dict[k], "IPV4", [(k, self.old_val_dict[k])])) for k in ["gateway"]]))
    def validate_netdevice_type(self):
        # rather large routine, could be a one-liner
        nw_s = self.old_val_dict["nw_types"]
        self.old_b_val_dict["nw_types"] = ", ".join([self.__ntc[k]["identifier"] for k in nw_s]) or "empty list"
        for key in self.__ntc.keys():
            value = self.new_val_dict[key]
            if value and not key in nw_s:
                nw_s.append(key)
            elif not value and key in nw_s:
                nw_s.remove(key)
        self.new_val_dict["nw_types"] = nw_s
        self.new_b_val_dict["nw_types"] = ", ".join([self.__ntc[k]["identifier"] for k in nw_s]) or "empty list"
    
def get_net_trees(req, change_log):
    net_t_tree = tools.get_network_type_dict(req.dc)
    if not net_t_tree:
        change_log.add_ok("Adding default network_types", "ok")
        req.dc.execute("INSERT INTO network_type VALUES%s" % (",".join(["(0,'%s','%s',null)" % (x, y) for x, y in [("b", "boot network"      ),
                                                                                                                   ("p", "production network"),
                                                                                                                   ("s", "slave network"     ),
                                                                                                                   ("o", "other network"     ),
                                                                                                                   ("l", "local network"     )]])))
        net_t_tree = tools.get_network_type_dict(req.dc)
    net_dt_tree = tools.get_network_device_type_dict(req.dc)
    if not net_dt_tree:
        change_log.add_ok("Adding default network_device_types", "ok")
        req.dc.execute("INSERT INTO network_device_type VALUES%s" % (",".join(["(0, '%s', '%s', %d, null)" % (x, y, z) for x, y, z in [("lo"   , "loopback devices"       ,  6),
                                                                                                                                       ("eth"  , "ethernet devices"       ,  6),
                                                                                                                                       ("myri" , "myrinet devices"        ,  6),
                                                                                                                                       ("xenbr", "xen bridge devices"     ,  6),
                                                                                                                                       ("tun"  , "ethernet tunnel devices",  6),
                                                                                                                                       ("ib"   , "infiniband devices"     , 20)]
                                                                               ])))
        net_dt_tree = tools.get_network_device_type_dict(req.dc)
    return net_t_tree, net_dt_tree
    
class new_network_device_type_vs(html_tools.validate_struct):
    def __init__(self, req):
        new_dict = {"identifier"  : {"he"  : html_tools.text_field(req, "nci",  size=16, display_len=8),
                                     "new" : 1,
                                     "vf"  : self.validate_identifier,
                                     "def" : ""},
                    "description" : {"he"  : html_tools.text_field(req, "ncd", size=64, display_len=32),
                                     "def" : "New device type"},
                    "mac_bytes"   : {"he"  : html_tools.text_field(req, "ncm", size=6, display_len=6),
                                     "vf"  : self.validate_mac,
                                     "def" : 6},
                    "del"         : {"he"  : html_tools.checkbox(req, "ntd", auto_reset=True),
                                     "del" : 1}}
        html_tools.validate_struct.__init__(self, req, "Network device type", new_dict)
    def validate_identifier(self):
        if self.new_val_dict["identifier"] in self.identifiers:
            self.new_val_dict["identifier"] = self.old_val_dict["identifier"]
            raise ValueError, "already used"
    def validate_mac(self):
        if self.new_val_dict["mac_bytes"].strip().isdigit():
            self.new_val_dict["mac_bytes"] = int(self.new_val_dict["mac_bytes"].strip())
        else:
            raise ValueError, "not an integer"

def show_netdevice_classes(req):
    low_submit = html_tools.checkbox(req, "sub")
    change_log = html_tools.message_log()
    ndt_vs = new_network_device_type_vs(req)
    net_t_tree, shadow_net_dt_tree = get_net_trees(req, change_log)
    # generate editable tree
    net_dt_tree = {}
    for idx, stuff in shadow_net_dt_tree.iteritems():
        net_dt_tree[idx] = cdef_network.network_device_type(stuff["identifier"], stuff["network_device_type_idx"], stuff)
        net_dt_tree[idx].act_values_are_default()
    net_dt_tree[0] = cdef_network.network_device_type(ndt_vs.get_default_value("identifier"), 0, ndt_vs.get_default_dict())
    net_dt_tree[0].act_values_are_default()
    net_tree = tools.get_network_dict(req.dc)
    req.dc.execute("SELECT network_device_type, COUNT(network_device_type) AS c FROM netdevice GROUP BY network_device_type")
    nw_dict = tools.ordered_dict()
    for nw_idx, nw_stuff in net_tree.iteritems():
        nw_dict[nw_stuff["network_idx"]] = cdef_network.network(nw_stuff["name"], nw_stuff["network_idx"], nw_stuff)
        nw_dict[nw_stuff["network_idx"]].act_values_are_default()
        nw_dict[nw_stuff["network_idx"]].usecount = nw_stuff["usecount"]
    net_class_dict = dict([(x["network_device_type"], x["c"]) for x in req.dc.fetchall()])
    nt_descr = html_tools.text_field(req, "ntd", size=64, display_len=32)
    for ndc_idx in net_dt_tree.keys():
        ndc_stuff = net_dt_tree[ndc_idx]
        ndc_stuff.count_nd = net_class_dict.get(ndc_idx, 0)
        ndc_stuff.count_nw = len([True for x in nw_dict.itervalues() if x.has_network_device_type(ndc_idx)])
        ndt_vs.identifiers = [x["identifier"] for x in net_dt_tree.values() if x["identifier"] and x["identifier"] != ndc_stuff["identifier"]]
        ndt_vs.link_object(ndc_idx, ndc_stuff)
        ndt_vs.check_for_changes()
        if not ndt_vs.check_delete():
            ndt_vs.process_changes(change_log, net_dt_tree)
        ndt_vs.unlink_object()
    if ndt_vs.get_delete_list():
        for del_idx in ndt_vs.get_delete_list():
            change_log.add_ok("Deleted network device class '%s'" % (net_dt_tree[del_idx]["identifier"]), "SQL")
            del net_dt_tree[del_idx]
        req.dc.execute("DELETE FROM network_device_type WHERE %s" % (" OR ".join(["network_device_type_idx=%d" % (x) for x in ndt_vs.get_delete_list()])))
    used_ids = [ndc_stuff["identifier"] for ndc_stuff in net_dt_tree.itervalues()]
    # check for new network_device_class
    for ndc_idx, ndc_stuff in net_t_tree.iteritems():
        ndc_stuff["count"] = len([1 for x in nw_dict.itervalues() if x["network_type"] == ndc_idx and x.get_idx()])
        new_descr = nt_descr.check_selection("%d" % (ndc_idx), ndc_stuff["description"])
        if new_descr != ndc_stuff["description"]:
            ndc_stuff["description"] = new_descr
            req.dc.execute("UPDATE network_type SET description=%s WHERE network_type_idx=%s", (new_descr, ndc_idx))
            change_log.add_ok("Changed description of network_type '%s' to '%s'" % (ndc_stuff["identifier"], ndc_stuff["description"]), "SQL")
    req.write(change_log.generate_stack("Action log"))
    # netdevice_class table
    class_table = html_tools.html_table(cls="normalsmall")
    class_table[0]["class"] = "line00"
    for what in ["Prefix", "Description", "# of MAC-Bytes", "count (devs/nets)"]:
        class_table[None][0] = html_tools.content(what, type="th")
    row0_idx = 0
    for ndc_idx in tools.get_ordered_idx_list(net_dt_tree, "identifier") + [0]:
        ndc_stuff = net_dt_tree[ndc_idx]
        line0_class = "line1%d" % (row0_idx)
        row0_idx = 1 - row0_idx
        class_table[0]["class"] = line0_class
        class_table[None][0] = html_tools.content(ndt_vs.get_he("identifier"), ndc_stuff.get_suffix(), cls="left")
        class_table[None][0] = html_tools.content(ndt_vs.get_he("description"), ndc_stuff.get_suffix(), cls="left")
        class_table[None][0] = html_tools.content(ndt_vs.get_he("mac_bytes"), ndc_stuff.get_suffix(), cls="center")
        if ndc_idx:
            if ndc_stuff.count_nd or ndc_stuff.count_nw:
                class_table[None][0] = html_tools.content("%d / %d" % (ndc_stuff.count_nd,
                                                                       ndc_stuff.count_nw), cls="center")
            else:
                class_table[None][0] = html_tools.content(["del:", ndt_vs.get_he("del")], ndc_stuff.get_suffix(), cls="errorcenter")
        else:
            class_table[None][0] = html_tools.content("&nbsp;", cls="center")
    # netdevice_type table
    type_table = html_tools.html_table(cls="normalsmall")
    for what in ["identifier", "Description", "count"]:
        type_table[1][0] = html_tools.content(what, type="th")
    type_table[1]["class"] = "line00"
    row0_idx = 0
    for ndc_idx, ndc_stuff in net_t_tree.iteritems():
        line0_class = "line1%d" % (row0_idx)
        row0_idx = 1 - row0_idx
        type_table[0][0]    = html_tools.content(ndc_stuff["identifier"], cls="center")
        type_table[None]["class"] = line0_class
        type_table[None][0] = html_tools.content(nt_descr, "%d" % (ndc_idx), cls="left")
        type_table[None][0] = html_tools.content(ndc_stuff["count"] and "%d" % (ndc_stuff["count"]) or "-", cls="center")
    # meta table
    meta_table = html_tools.html_table(cls="blindsmall")
    meta_table[0][0]    = html_tools.content(class_table, cls="top")
    meta_table[None][0] = html_tools.content(type_table , cls="top")
    req.write("%s%s" % (html_tools.gen_hline("%s and %s defined" % ("%d netdevice classes" % (len(net_dt_tree.keys())),
                                                                    "%d network types" % (len(net_t_tree.keys()))), 2),
                        meta_table("")))
    low_submit[""] = 1
    submit_button = html_tools.submit_button(req, "submit")
    submit_button.set_class("", "button")
    req.write("%s<div class=\"center\">%s</div>\n" % (low_submit.create_hidden_var(),
                                                      submit_button("")))
    

def show_cluster_networks(req):#, sub_sel):
    change_log = html_tools.message_log()
    net_t_tree, net_dt_tree = get_net_trees(req, change_log)
    net_tree = tools.get_network_dict(req.dc)
    if not net_tree:
        change_log.add_ok("Adding default networks", "ok")
        add_default_networks(net_t_tree, net_dt_tree, req.dc)
        net_tree = tools.get_network_dict(req.dc)
    # add usecount
    req.dc.execute("SELECT nw.network_idx, COUNT(nw.network_idx) AS usecount FROM device d, netdevice nd, netip ip, network nw, network_type nt WHERE " + \
                       "nd.device=d.device_idx AND ip.netdevice=nd.netdevice_idx AND ip.network=nw.network_idx AND nw.network_type=nt.network_type_idx GROUP BY nw.network_idx")
    for stuff in req.dc.fetchall():
        net_tree[stuff["network_idx"]]["usecount"] = stuff["usecount"]
    type_field = html_tools.selection_list(req, "nt", {})
    low_submit = html_tools.checkbox(req, "sub")
    sub = low_submit.check_selection("")
    for nt_idx, nt_stuff in net_t_tree.iteritems():
        type_field[nt_idx] = "%s (%s)" % (nt_stuff["identifier"], nt_stuff["description"])
    master_field = html_tools.selection_list(req, "mn", {})
    master_field[0] = "--- not set ---"
    nw_dict = tools.ordered_dict()
    for nw_idx, nw_stuff in net_tree.iteritems():
        if net_t_tree[nw_stuff["network_type"]]["identifier"] == "p":
            master_field[nw_idx] = "%s (%s, %s)" % (nw_stuff["identifier"], nw_stuff["name"], nw_stuff["network"])
        nw_dict[nw_stuff["network_idx"]] = cdef_network.network(nw_stuff["name"], nw_stuff["network_idx"], nw_stuff)
        nw_dict[nw_stuff["network_idx"]].act_values_are_default()
        nw_dict[nw_stuff["network_idx"]].usecount = nw_stuff["usecount"]
    master_field.mode_is_normal()
    type_field.mode_is_normal()
    network_vs = new_network_vs(req, type_field, net_dt_tree, master_field, net_t_tree)
    nw_dict[0] = cdef_network.network(network_vs.get_default_value("name"), 0, network_vs.get_default_dict())
    network_vs.set_submit_mode(sub)
    for nw_idx in nw_dict.keys():
        nw_stuff = nw_dict[nw_idx]
        network_vs.names = [nw_dict[x]["identifier"] for x in nw_dict.keys() if x != nw_idx and x]
        network_vs.link_object(nw_idx, nw_stuff)
        network_vs.check_for_changes()
        if not network_vs.check_delete():
            network_vs.process_changes(change_log, nw_dict)
        network_vs.unlink_object()
    if network_vs.get_delete_list():
        for del_idx in network_vs.get_delete_list():
            change_log.add_ok("Deleted network '%s'" % (nw_dict[del_idx]["identifier"]), "SQL")
            del nw_dict[del_idx]
        sql_str = "DELETE FROM network WHERE %s" % (" OR ".join(["network_idx=%d" % (x) for x in network_vs.get_delete_list()]))
        req.dc.execute(sql_str)
        sql_str = "DELETE FROM network_network_device_type WHERE %s" % (" OR ".join(["network=%d" % (x) for x in network_vs.get_delete_list()]))
        req.dc.execute(sql_str)
    # generate list of nw_sf
    nw_sf_olist = tools.get_ordered_idx_list(nw_dict, "identifier")
    # check for slave networks without master
    for nw_sf in [nw_dict[k] for k in nw_sf_olist]:
        #print nw_sf["network_type"]
        if net_t_tree[nw_sf["network_type"]]["identifier"] == "s" and not nw_sf["master_network"]:
            change_log.add_warn("Slave Network '%s' has no associated master network" % (nw_sf["name"]), "config error")
    req.write(change_log.generate_stack("Action log"))

    req.write(html_tools.gen_hline("ClusterNetwork config, %s defined" % (logging_tools.get_plural("network", len(nw_dict.keys())-1)), 2))
    out_table = html_tools.html_table(cls="normalsmall")
    req.write(out_table.get_header())
    row0_idx = 0
    for nw_stuff in [nw_dict[n] for n in nw_sf_olist + [0]]:
        line_len = 3
        if not nw_stuff.get_idx():
            out_table[1]["class"] = "lineh"
            out_table[1][1:line_len] = html_tools.content("New Network", type="th", cls="center")
            req.write(out_table.flush_lines())
        line0_class = "line0%d" % (row0_idx)
        line1_class = "line1%d" % (row0_idx)
        row0_idx = 1-row0_idx
        out_table[1:6]["class"] = line0_class
        out_table[2:5]["class"] = line1_class
        out_table[1:6][1]  = html_tools.content(network_vs.get_he("identifier"), cls="left")
        node_name = "node001"
        nw_bits = ipvx_tools.ipv4(nw_stuff["netmask"]).netmask_bits()
        nw_class = "class %s" % ({8  : "A",
                                  16 : "B",
                                  24 : "C"}.get(nw_bits, "unknown"))
        out_table[1][2:line_len] = html_tools.content("Info: %s, %s will result in %s%s, %s%s" % (nw_class,
                                                                                                  node_name,
                                                                                                  "%s%s.%s" % (node_name, nw_stuff["postfix"], nw_stuff["name"]),
                                                                                                  nw_stuff["short_names"] and " and %s%s" % (node_name, nw_stuff["postfix"]) or "",
                                                                                                  "%d possible IPs" % (2**(32 - nw_bits) - 2),
                                                                                                  nw_stuff.usecount and ", used by %s" % (logging_tools.get_plural("IP address", nw_stuff.usecount)) or ""),
                                                      cls="left")
        if not nw_stuff.get_idx() or nw_stuff.usecount:
            start_row = 2
        else:
            start_row = 3
            out_table[2:5][2] = html_tools.content(network_vs.get_he("del"), cls="errormin")
        #out_table[2][9:line_len] = html_tools.content([], cls="left")
        out_table[2][start_row : 3] = html_tools.content(["Type: "                         , network_vs.get_he("network_type"),
                                                          ", Master (for slave networks): ", network_vs.get_he("master_network"),
                                                          ", penalty: "                    , network_vs.get_he("penalty"),
                                                          ", gateway priority: "           , network_vs.get_he("gw_pri")], cls="left")
        out_table[3][start_row : 3] = html_tools.content(["Postfix: "             , network_vs.get_he("postfix"),
                                                          ", Name: "              , network_vs.get_he("name"),
                                                          ", Info: "              , network_vs.get_he("info"),
                                                          "; flags: Short Names: ", network_vs.get_he("short_names"),
                                                          "write BIND: "          , network_vs.get_he("write_bind_config"),
                                                          "force write config: "  , network_vs.get_he("write_other_network_config")], cls="left")
        out_table[4][start_row : 3] = html_tools.content(["Network: "    , network_vs.get_he("network"),
                                                          ", netmask: "  , network_vs.get_he("netmask"),
                                                          ", broadcast: ", network_vs.get_he("broadcast"),
                                                          ", gateway: "  , network_vs.get_he("gateway")], cls="left")
        out_table[5][start_row : 3] = html_tools.content(["Free range for auto-IP: " , network_vs.get_he("start_range"),
                                                          " - "                      , network_vs.get_he("end_range")], cls="left")
        out_f = ["Network device classes:"]
        for idx, stuff in net_dt_tree.iteritems():
            out_f.extend([" %s" % (stuff["identifier"]), network_vs.get_he(idx), " (%s [%d]),\n" % (stuff["description"], stuff["mac_bytes"])])
        out_table[6][2:line_len] = html_tools.content(out_f, cls="left")
        req.write(out_table.flush_lines(nw_stuff.get_suffix()))
    low_submit[""] = 1
    submit_button = html_tools.submit_button(req, "submit")
    submit_button.set_class("", "button")
    req.write("%s%s<div class=\"center\">%s</div>\n" % (out_table.get_footer(),
                                                        low_submit.create_hidden_var(),
                                                        submit_button("")))

def get_netspeed_str(in_bps):
    if in_bps >= 1000000000:
        return "10Gbps" if in_bps == 10000000000 else ("1Gbps" if in_bps == 1000000000 else "%.2fGbps" % (in_bps / 1000000000))
    elif in_bps >= 100000000:
        return in_bps == 100000000 and "100Mbps" or "%.1fMbps" % (in_bps / 100000000)
    elif in_bps >= 10000000:
        return in_bps == 10000000 and "10Mbps" or "%.1fMbps" % (in_bps / 10000000)
    else:
        return "%.2fkbps" % (in_bps / 1000000)
    
def show_device_networks(req, dev_tree, sub_sel):
    dg_sel, d_sel, dg_sel_eff = dev_tree.get_selection()
    change_log  = html_tools.message_log()
    net_tree    = tools.get_network_dict(req.dc)
    # refresh hardwareinfo button
    refresh_hw = html_tools.checkbox(req, "fhw", auto_reset=True)
    # fetch network_info button
    fetch_network_info = html_tools.checkbox(req, "fbi", auto_reset=True)
    netdev_speeds = tools.get_netdevice_speed(req.dc)
    netdev_speed_sel_list = html_tools.selection_list(req, "nds", {}, sort_new_keys=False)
    netdev_speed_dict = {}
    for nd_idx, ns_stuff in netdev_speeds.iteritems():
        netdev_speed_dict[nd_idx] = "%s%s%s" % (get_netspeed_str(ns_stuff["speed_bps"]),
                                                ns_stuff["check_via_ethtool"] and ", check" or "",
                                                ns_stuff["full_duplex"] and ", full duplex" or "")
        netdev_speed_sel_list[nd_idx] = netdev_speed_dict[nd_idx]
    netdev_speed_sel_list.mode_is_normal()
    net_sel_list = html_tools.selection_list(req, "nw", {})
    for net_idx, network in net_tree.iteritems():
        net_sel_list[net_idx] = network["nw_info"]
    net_sel_list.add_pe_key("", 0, {"name" : "auto select"})
    autoneg_dict = {0 : "default",
                    1 : "on"     ,
                    3 : "off"    }
    autoneg_sel_list = html_tools.selection_list(req, "naut", autoneg_dict)
    duplex_dict = {0 : "default",
                   1 : "full"   ,
                   3 : "half"   }
    duplex_sel_list =  html_tools.selection_list(req, "ndup", duplex_dict)
    speed_dict = {0 : "default" ,
                  1 : "10 MBit" ,
                  3 : "100 MBit",
                  5 : "1 GBit"  ,
                  7 : "10 GBit" }
    speed_sel_list = html_tools.selection_list(req, "nspd", speed_dict)
    # switch lists to normal mode
    net_sel_list.mode_is_normal()
    autoneg_sel_list.mode_is_normal()
    duplex_sel_list.mode_is_normal()
    speed_sel_list.mode_is_normal()
    # build device_dict
    req.dc.execute("SELECT d.device_idx, d.bootnetdevice, d.bootserver, d.device_group, d.device_type, d.relay_device, d.xen_guest FROM device d WHERE (%s)" % (" OR ".join(["d.device_idx=%d" % (x) for x in d_sel])))
    # bootserver dict
    bootserver_dict = {}
    # device dict and lut
    dev_dict, dev_lut_dict = ({}, {})
    for db_rec in req.dc.fetchall():
        d_idx = db_rec["device_idx"]
        new_dev = cdef_device.device(dev_tree.get_dev_name(d_idx), d_idx, db_rec["device_group"], db_rec["device_type"])
        new_dev.set_bootserver(db_rec["bootserver"])
        new_dev.set_xen_guest(db_rec["xen_guest"])
        new_dev.relay_device = db_rec["relay_device"]
        if db_rec["bootserver"]:
            bootserver_dict.setdefault(db_rec["bootserver"], {})
        new_dev.set_bootnetdevice(db_rec["bootnetdevice"])
        dev_dict[d_idx] = new_dev
        dev_lut_dict[new_dev.get_name()] = new_dev
    # get bootserver_names
    if bootserver_dict:
        req.dc.execute("SELECT d.name, d.device_idx FROM device d WHERE (%s)" % (" OR ".join(["d.device_idx=%d" % (x) for x in bootserver_dict.keys()])))
        for db_rec in req.dc.fetchall():
            bootserver_dict[db_rec["device_idx"]]["name"] = db_rec["name"]
            bootserver_dict[db_rec["device_idx"]]["action_dict"] = {}
    refresh_dict, refresh_list = ({}, [])
    fetch_network_info_dict, network_info_list = ({}, [])
    # relaying devices
    relay_devices = html_tools.selection_list(req, "rdevs", {0 : "--- none ---"}, sort_new_keys=False)
    for dg in dg_sel_eff:
        for dev in [x for x in d_sel if x in dev_tree.get_sorted_dev_idx_list(dg)]:
            act_dev = dev_dict[dev]
            relay_devices[act_dev.get_idx()] = "%s (%s)" % (act_dev.get_name(), dev_tree.get_devg_name(dg))
    relay_devices.mode_is_normal()
    # copied from below
    net_copy_source    = html_tools.selection_list(req, "ncs", {}, auto_reset=True)
    # relay-device change?
    relay_device_changed = False
    copy_dev_idx = 0
    for dg in dg_sel_eff:
        for dev in [x for x in d_sel if x in dev_tree.get_sorted_dev_idx_list(dg)]:
            act_dev = dev_dict[dev]
            new_rd = relay_devices.check_selection(act_dev.get_suffix(), act_dev.relay_device)
            if new_rd != act_dev.relay_device:
                relay_device_changed = True
                change_log.add_ok("Changing relay-device for device '%s'" % (act_dev.get_name()), "SQL")
                act_dev.relay_device = new_rd
                req.dc.execute("UPDATE device SET relay_device=%d WHERE device_idx=%d" % (act_dev.relay_device, dev))
            rf_hw = refresh_hw.check_selection(act_dev.get_suffix(), 0)
            if act_dev.get_bootserver() and rf_hw:
                refresh_dict.setdefault(bootserver_dict[act_dev.get_bootserver()]["name"], []).append(act_dev.get_name())
                refresh_list.append(act_dev.get_name())
            fetch_bi = fetch_network_info.check_selection(act_dev.get_suffix(), 0)
            if act_dev.get_bootserver() and fetch_bi:
                fetch_network_info_dict.setdefault(bootserver_dict[act_dev.get_bootserver()]["name"], []).append(act_dev.get_name())
                network_info_list.append(act_dev.get_name())
            copy_dev_idx += 1
            net_copy_source["d%04d" % (copy_dev_idx)] = {"name" : "%s (%s)" % (act_dev.get_name(), dev_tree.get_devg_name(dg)),
                                                         "idx"  : act_dev.get_idx()}
    net_copy_source.mode_is_normal()
    # do we have to refresh some devices or fetch network infos ?
    fni_commands = [tools.s_command(req, "mother_server", 8001, "fetch_network_info", nodes, 10, bs) for bs, nodes in fetch_network_info_dict.iteritems()]
    tools.iterate_s_commands([tools.s_command(req, "mother_server", 8001, "refresh_hwi", nodes, 10, bs) for bs, nodes in refresh_dict.iteritems()] + fni_commands , change_log)
    if fni_commands:
        req.write(change_log.generate_stack("Action log"))
        return
    # fetch tree
    net_dt_tree = tools.get_network_device_type_dict(req.dc)
    # default value for eth-prefix
    all_ndt_identifiers = [x["identifier"] for x in net_dt_tree.values()]
    if not all_ndt_identifiers:
        # fixme
        print "No NetworkDeviceTypes found, exiting..."
        sys.exit(0)
    if "eth" in all_ndt_identifiers or not all_ndt_identifiers:
        nndn_default = "eth"
    else:
        nndn_default = all_ndt_identifiers[0]
    nndn_default_idx = [k for k, v in net_dt_tree.iteritems() if v["identifier"] == nndn_default][0]
    # add network_info from db
    req.dc.execute("SELECT d.device_idx, n.*, i.* FROM device d LEFT JOIN netdevice n ON n.device=d.device_idx LEFT JOIN netip i ON i.netdevice=n.netdevice_idx WHERE (%s)" % (" OR ".join(["d.device_idx=%d" % (x) for x in d_sel])))
    for db_rec in req.dc.fetchall():
        dev_dict[db_rec["device_idx"]].add_network_stuff(db_rec)
    # set as default
    for db_rec in dev_dict.values():
        db_rec.set_values_as_default()
    # fetch all IP addresses
    req.dc.execute("SELECT DISTINCT nw.network_idx,i.ip FROM netip i, netdevice n, device d, network nw WHERE i.network=nw.network_idx AND i.netdevice=n.netdevice_idx AND n.device=d.device_idx ORDER BY nw.network_idx,i.ip")
    used_ip_dict = {}
    for db_rec in req.dc.fetchall():
        used_ip_dict.setdefault(db_rec["network_idx"], []).append(db_rec["ip"])
    # get bootserver_names
    if bootserver_dict:
        req.dc.execute("SELECT d.name, d.device_idx FROM device d WHERE (%s)" % (" OR ".join(["d.device_idx=%d" % (x) for x in bootserver_dict.keys()])))
        for db_rec in req.dc.fetchall():
            bootserver_dict[db_rec["device_idx"]]["name"] = db_rec["name"]
            bootserver_dict[db_rec["device_idx"]]["action_dict"] = {}
    # get all peers refering to one of the selected devices
    req.dc.execute("SELECT d.device_idx, p.* FROM device d LEFT JOIN netdevice n ON n.device=d.device_idx LEFT JOIN peer_information p ON (p.s_netdevice=n.netdevice_idx OR p.d_netdevice=n.netdevice_idx) WHERE (%s)" % (" OR ".join(["d.device_idx=%d" % (x) for x in d_sel])))
    for db_rec in req.dc.fetchall():
        s_nd, d_nd = (db_rec["s_netdevice"], db_rec["d_netdevice"])
        if s_nd and d_nd:
            act_dev = dev_dict[db_rec["device_idx"]]
            # save peer information
            act_dev.add_peer_information(db_rec)
    p_list = []
    for dev in dev_dict.values():
        p_list.extend(dev.get_peers())
    fe_peers = {}
    # get all routing netdevices and all endpoints of the found peers
    peer_list = html_tools.selection_list(req, "fp", {}, auto_reset=True)
    peer_list["p0"] = "--- none ---"
    req.dc.execute("SELECT d.device_idx, n.netdevice_idx, d.name, n.devname, n.penalty, n.routing, i.ip FROM device d, netdevice n LEFT JOIN netip i ON i.netdevice=n.netdevice_idx WHERE n.device=d.device_idx AND (%sn.routing)" % (p_list and "%s OR " % (" OR ".join(["n.netdevice_idx=%d" % (x) for x in p_list])) or ""))
    for db_rec in req.dc.fetchall():
        #print "*", x, "<br>"
        idx = db_rec["netdevice_idx"]
        if not fe_peers.has_key(idx):
            fe_peers[idx] = db_rec
            fe_peers[idx]["ips"] = []
        if db_rec["ip"]:
            fe_peers[idx]["ips"].append(db_rec["ip"])
    for idx, db_rec in fe_peers.iteritems():
        if db_rec["routing"]:
            peer_list["p%d" % (idx)] = {"name" : "%s%s on %s (penalty %d)" % (db_rec["devname"],
                                                                              " (%s)" % ("/".join([ip for ip in db_rec["ips"]])) if db_rec["ips"] else "",
                                                                              db_rec["name"],
                                                                              db_rec["penalty"]),
                                        "idx"  : idx}
    found_ndevs = fe_peers.keys()
    # get all bridges
    req.dc.execute("SELECT d.name, n.* FROM netdevice n, device d WHERE n.device=d.device_idx AND n.is_bridge")
    bridge_dict = {}
    for db_rec in req.dc.fetchall():
        bridge_dict.setdefault(db_rec["devname"], []).append(db_rec)
    bridge_list = html_tools.selection_list(req, "brl", {}, sort_new_keys=False)
    bridge_list[""] = "---"
    for br_name in sorted(bridge_dict.keys()):
        bridge_list[br_name] = "%s on %s: %s" % (br_name,
                                                 logging_tools.get_plural("device", len(bridge_dict[br_name])),
                                                 logging_tools.compress_list([db_rec["name"] for db_rec in bridge_dict[br_name]]))
    bridge_list.mode_is_normal()
    missing_netdevices = [x for x in p_list if x not in found_ndevs]
    if missing_netdevices:
        change_log.add_warn("Deleting the peer_information referencing %s" % (logging_tools.get_plural("missing netdevice", len(missing_netdevices))), "ok")
        sql_str = "DELETE FROM peer_information WHERE %s OR %s" % (" OR ".join(["s_netdevice=%d" % (x) for x in missing_netdevices]),
                                                                   " OR ".join(["d_netdevice=%d" % (x) for x in missing_netdevices]))
        req.dc.execute(sql_str)
        for act_dev in dev_dict.values():
            act_dev.remove_defective_peers(missing_netdevices)
    net_copy           = html_tools.checkbox(req, "nc",  auto_reset=True)
    ndev_del           = html_tools.checkbox(req, "dnd", auto_reset=True)
    ndev_name          = html_tools.text_field(req, "ndn" ,  size=16, display_len=12)
    ndev_drv           = html_tools.text_field(req, "ndd" ,  size=32, display_len=12)
    ndev_drv_options   = html_tools.text_field(req, "nddo", size=224, display_len=12)
    # initiate ndev_macadr_fields
    ndev_macadrs, ndev_fake_macadrs = ({}, {})
    for key, value in net_dt_tree.iteritems():
        mb = value["mac_bytes"]
        ndev_macadrs[key]      = html_tools.text_field(req, "ndm" , size=mb * 3 - 1, display_len=mb * 3 - 1)
        ndev_fake_macadrs[key] = html_tools.text_field(req, "ndfm", size=mb * 3 - 1, display_len=mb * 3 - 1)
    ndev_penalty       = html_tools.text_field(req, "ndp" ,  size=6, display_len=6 )
    net_ip_alias       = html_tools.text_field(req, "nda" , size=32, display_len=12)
    net_ip_alias_excl  = html_tools.checkbox(req, "ndax")
    net_ip             = html_tools.text_field(req, "ni", size=15, display_len=15)
    net_ip_del         = html_tools.checkbox(req, "dni", auto_reset=True)
    peer_del           = html_tools.checkbox(req, "pd" , auto_reset=True)
    peer_penalty       = html_tools.text_field(req, "npp", size=8, display_len=4)
    dhcp_device_button = html_tools.checkbox(req, "ddh")
    mac_random_button  = html_tools.checkbox(req, "macr", auto_reset=True)
    routing_button     = html_tools.checkbox(req, "dr")
    descr_field        = html_tools.text_field(req, "ddescr", size=255, display_len=16)
    vlan_id_field      = html_tools.text_field(req, "dvlan", size=6, display_len=5)
    # field dictionaries
    # netdevice
    ndc_lut = {"devname"         : {ndev_name             : None,
                                    "compound"            : "devmac"},
               "macadr"          : {ndev_macadrs[nndn_default_idx] : None,
                                    "compound"            : "devmac"},
               "fake_macadr"     : {ndev_fake_macadrs[nndn_default_idx] : None,
                                    "compound"            : "devmac"},
               "driver"          : {ndev_drv              : None},
               "driver_options"  : {ndev_drv_options      : None},
               "netdevice_speed" : {netdev_speed_sel_list : None,
                                    "speed_dict"          : netdev_speed_dict},
               "penalty"         : {ndev_penalty          : None},
               "dhcp_device"     : {dhcp_device_button    : None,
                                    "button_list"         : [dhcp_device_button.get_name()]},
               "routing"         : {routing_button        : None,
                                    "button_list"         : [routing_button.get_name()]},
               "bridge_name"     : {bridge_list           : None},
               "description"     : {descr_field           : None},
               "vlan_id"         : {vlan_id_field         : None},
               "ethtool_options" : {autoneg_sel_list      : "getset_autoneg_value",
                                    duplex_sel_list       : "getset_duplex_value",
                                    speed_sel_list        : "getset_speed_value",
                                    "autoneg_dict"        : autoneg_dict,
                                    "speed_dict"          : speed_dict,
                                    "duplex_dict"         : duplex_dict}
               }
    # netip
    nic_lut = {"ip"         : {net_ip            : None,
                               "net_tree"        : net_tree,
                               "used_ips"        : used_ip_dict,
                               "compound"        : "netip"},
               "network"    : {net_sel_list      : "getset_network",
                               "net_tree"        : net_tree,
                               "used_ips"        : used_ip_dict,
                               "compound"        : "netip"},
               "alias"      : {net_ip_alias      : None},
               "alias_excl" : {net_ip_alias_excl : None,
                               "button_list"     : [net_ip_alias_excl.get_name()]}
               }
    # low-submit stuff
    low_submit = html_tools.checkbox(req, "sub")
    sub = low_submit.check_selection("")
    # new netdevice dict
    new_ndev_dict = {"netdevice_idx"       : -1,
                     "devname"             : nndn_default,
                     "macadr"              : "00:00:00:00:00:00",
                     "driver_options"      : "",
                     "netdevice_speed"     : 1,
                     # changed (26.12.2007)
                     "driver"              : "e100",
                     "routing"             : 0,
                     "description"         : "",
                     "penalty"             : 1,
                     "dhcp_device"         : 0,
                     "device"              : 0,
                     "ethtool_options"     : 0,
                     "fake_macadr"         : "00:00:00:00:00:00",
                     "bridge_name"         : "",
                     "network_device_type" : 0,
                     "is_bridge"           : 0,
                     "vlan_id"             : 0}
    # new netip dict
    new_netip_dict = {"netip_idx"  : -1,
                      "alias"      : "",
                      "alias_excl" : 0,
                      "ip"         : "0.0.0.0",
                      "network"    : 0,
                      "netdevice"  : 0}
    # user log_source_idx
    user_log_source_idx = req.log_source.get("user", {"log_source_idx" : 0})["log_source_idx"]
    ip_del_list = []
    nd_del_list = []
    peer_del_list = []
    # add global-change device
    new_dev = cdef_device.device("&lt;global&gt;", 0, 0, 0)
    new_dev.add_network_stuff(new_ndev_dict)
    dev_dict[0] = new_dev
    glob_nd = new_dev.get_netdevice_struct(-1)
    glob_nd.set_fields(ndc_lut)
    ndc_lut["devname"]["net_dt_tree"]  = net_dt_tree
    ndc_lut["devname"]["net_dt_lut"]   = dict([(v["identifier"], k) for k, v in net_dt_tree.iteritems()])
    ndc_lut["devname"]["act_dev"]      = new_dev
    ndc_lut["devname"]["hw_refreshed"] = 0
    glob_nd.check_for_changes(ndc_lut, sub)
    glob_nd.add_network_stuff(new_netip_dict)
    glob_nd.get_ip(-1).set_fields(nic_lut)
    glob_ndev_del = ndev_del.check_selection(glob_nd.get_suffix())
    glob_ndev_name = glob_nd["devname"]
    # global netip
    net_sel_list.add_pe_key(glob_nd.get_new_netip_suffix(), 0, {"name" : "auto select"})
    glob_net_ip_del = net_ip_del.check_selection(glob_nd.get_new_netip_suffix(), 0)
    glob_net_ip = net_ip.check_selection(glob_nd.get_new_netip_suffix(), new_netip_dict["ip"])
    glob_net_network = net_sel_list.check_selection(glob_nd.get_new_netip_suffix(), 0)
    net_ip[glob_nd.get_new_netip_suffix()] = new_netip_dict["ip"]
    # peer fields
    new_glob_peer = peer_list.check_selection(glob_nd.get_suffix(), "p0")
    new_glob_peer_penalty = peer_penalty.check_selection(glob_nd.get_suffix(), "1")
    new_glob_vlan_id = vlan_id_field.check_selection(glob_nd.get_suffix(), "0")
    #print "*%s*%s*%s*<br>" % (glob_net_ip_del, glob_net_ip, glob_net_network)
    #err_list, warn_list, ok_list = glob_nd.build_change_lists("set ", " for global change", 0, 1, 1)
    #change_log.add_errors(err_list)
    #change_log.add_warns(warn_list)
    #change_log.add_oks(ok_list)
    #print "<br>*%s*<br>" % (glob_ndev_name)
    # rebuild hopcount-table
    rebuild_hopcount, rebuild_hc_causes = (0, {})
    # rewrite etc_hosts
    rebuild_etc_hosts, rebuild_eh_causes = (0, {})
    # ip_change flag
    # ip_change_cause: {device}->[causes]
    ip_change_flag, ip_change_causes = (0, {})
    # check for global adapt-flag
    adapt_all_nets = net_copy.check_selection("", 0)
    copy_dev_idx = 0
    # command list
    ss_list = []
    for dg in dg_sel_eff:
        for dev in [x for x in d_sel if x in dev_tree.get_sorted_dev_idx_list(dg)]:
            act_dev = dev_dict[dev]
            # dictionary of used networks
            used_nets = {}
            # add new netdevice
            ndc_lut["devname"]["act_dev"] = act_dev
            ndc_lut["devname"]["hw_refreshed"] = act_dev.get_name() in refresh_list + network_info_list
            # actual bootnetdevice
            had_bnd = act_dev.get_bootnetdevice()
            if had_bnd and had_bnd in act_dev.net_tree.keys():
                bnd_name, bnd_mac, bnd_drv, bnd_opts, bnd_eth_opts = (act_dev.get_netdevice_struct(had_bnd)["devname"],
                                                                      act_dev.get_netdevice_struct(had_bnd)["macadr"],
                                                                      act_dev.get_netdevice_struct(had_bnd)["driver"],
                                                                      act_dev.get_netdevice_struct(had_bnd)["driver_options"],
                                                                      act_dev.get_netdevice_struct(had_bnd)["ethtool_options"])
            else:
                bnd_name, bnd_mac, bnd_drv, bnd_opts, bnd_eth_opts = (None, None, None, None, None)
            adapted = 0
            src_net = net_copy.check_selection(act_dev.get_suffix(), 0)
            src_net_dev = net_copy_source.check_selection(act_dev.get_suffix(), 0)
            if (src_net or adapt_all_nets) and src_net_dev:
                src_net_dev = net_copy_source.list_dict[src_net_dev]["idx"]
                if src_net_dev != dev:
                    src_dev = dev_dict[src_net_dev]
                    adapted = 1
                    adapted_status, netdev_ok, netip_ok, peer_ok = (1, 0, 0, 0)
                    for act_nd in src_dev.get_sorted_netdevice_list():
                        if act_nd.get_idx() > 0:
                            netdev_ok += 1
                            # copy netdevice instance
                            new_nd = act_nd.copy_instance()
                            # set device idx
                            new_nd["device"] = dev
                            # clear macadr
                            new_nd["macadr"] = ":".join(["00"] * len(new_nd["macadr"].split(":")))
                            # generate db-entry
                            new_nd.commit_sql_changes(req.dc, 1, 1)
                            # set new netip_suffix
                            new_nd.set_new_netip_suffix()
                            # sort netdevice into device
                            act_dev.enqueue_new_netdevice(new_nd, 0)
                            # new type
                            new_nd_type = [k for k, v in net_dt_tree.iteritems() if new_nd.get_name().startswith(v["identifier"])][0]
                            # modify ndc_lut
                            ndc_lut["macadr"]      = {ndev_macadrs[new_nd_type]      : None,
                                                      "compound"                     : "devmac"}
                            ndc_lut["fake_macadr"] = {ndev_fake_macadrs[new_nd_type] : None,
                                                      "compound"                     : "devmac"}
                            # set html-fields
                            new_nd.set_fields(ndc_lut)
                            # add new-netip field
                            new_nd.add_network_stuff(new_netip_dict)
                            # set html-fields
                            new_nd.get_ip(-1).set_fields(nic_lut)
                            # reset delete-field
                            ndev_del[new_nd.get_suffix()] = 0
                            # add autoselect field for new-netip field
                            net_sel_list.add_pe_key_ref(new_nd.get_new_netip_suffix(), 0)
                            # peer fields
                            peer_list.check_selection(new_nd.get_suffix(), "p0")
                            peer_penalty.check_selection(new_nd.get_suffix(), "1")
                            # vlan id
                            vlan_id_field.check_selection(new_nd.get_suffix(), "0")
                            # copy netips
                            for act_ip in act_nd.get_sorted_netip_list():
                                if act_ip.get_idx() > 0:
                                    # copy netip instance
                                    new_ip = act_ip.copy_instance()
                                    # clear error flag
                                    ipv4_error = 0
                                    if net_tree[new_ip["network"]]["ntident"] != "l":
                                        try:
                                            # increase netip
                                            new_ipv4 = ipvx_tools.ipv4(new_ip["ip"]) + ipvx_tools.ipv4("0.0.0.1")
                                        except ValueError:
                                            change_log.add_error("Cannot increase IPv4 Address '%s' by one for netdevice %s, device %s" % (new_ip["ip"], new_nd.get_name(), act_dev.get_name()), "ValueError")
                                            ipv4_error = 1
                                        else:
                                            if new_ipv4.network_matches(net_tree[new_ip["network"]]):
                                                new_ip["ip"] = str(new_ipv4)
                                            else:
                                                change_log.add_error("Cannot increase IPv4 Address '%s' by one for netdevice %s, device %s" % (new_ip["ip"], new_nd.get_name(), act_dev.get_name()), "NetworkError")
                                                ipv4_error = 1
                                    else:
                                        pass
                                    if not ipv4_error:
                                        netip_ok += 1
                                        # set netdevice idx
                                        new_ip["netdevice"] = new_nd.get_idx()
                                        # generate db-entry
                                        new_ip.commit_sql_changes(req.dc, 1, 1)
                                        # sort netip into netdevice
                                        new_nd.enqueue_new_netip(new_ip, 0)
                                        # set html-fields
                                        new_ip.set_fields(nic_lut)
                                        # add to used_ip_dict
                                        used_ip_dict.setdefault(new_ip["network"], []).append(new_ip["ip"])
                                        # reset delete-field
                                        net_ip_del[new_ip.get_suffix()] = 0
                                        ip_change_causes.setdefault(act_dev.get_name(), []).append("new ip added")
                                    else:
                                        adapted_status = 0
                            for peer_idx in act_nd.get_peer_idxs():
                                act_pen, act_pep = (act_nd.get_penalty(peer_idx), act_nd.get_peer_endpoint(peer_idx))
                                if act_pep == act_nd.get_idx():
                                    act_pep = new_nd.get_idx()
                                peer_ok += 1
                                req.dc.execute("INSERT INTO peer_information SET s_netdevice=%d, d_netdevice=%d, penalty=%d" % (new_nd.get_idx(), act_pep, act_pen))
                                new_pe_idx = req.dc.insert_id()
                                new_nd.add_peer_information(new_pe_idx, act_pep, act_pen)
                                if fe_peers.has_key(act_pep):
                                    fe_peer = fe_peers[act_pep]
                                    if dev_dict.has_key(fe_peer["device_idx"]):
                                        try:
                                            fe_nd = dev_dict[fe_peer["device_idx"]].get_netdevice_struct(fe_peer["netdevice_idx"])
                                        except KeyError:
                                            pass
                                        else:
                                            fe_nd.add_peer_information(new_pe_idx, new_nd.get_idx(), act_pen)
                                fe_peers[new_nd.get_idx()] = {"device_idx"    : act_dev.get_idx(),
                                                              "name"          : act_dev.get_name(),
                                                              "devname"       : new_nd.get_name(),
                                                              "penalty"       : new_nd["penalty"],
                                                              "netdevice_idx" : new_nd.get_idx(),
                                                              "routing"       : new_nd["routing"]}
                                peer_del[new_nd.get_peer_suffix(new_pe_idx)] = 0
                                peer_penalty[new_nd.get_peer_suffix(new_pe_idx)] = act_pen
                                # vlan id
                                #act_vlan_id = act_nd.get_vlan_id()
                                # 
                                # vlan_id_field[new_nd.get_peer_suffix(new_pe_idx)] = act_vlan_id
                                #if dev_dict.has_key(act_pep):
                                    # foreign netdevice
                                #    fe_nd = dev_dict[act_pep]
                    # generate field for new netdevice
                    # modify ndc_lut
                    ndc_lut["macadr"]      = {ndev_macadrs[nndn_default_idx]      : None,
                                              "compound"                          : "devmac"}
                    ndc_lut["fake_macadr"] = {ndev_fake_macadrs[nndn_default_idx] : None,
                                              "compound"                          : "devmac"}
                    act_dev.add_network_stuff(new_ndev_dict)
                    # get struct
                    new_nd = act_dev.get_netdevice_struct(-1)
                    # set new netip-suffix
                    new_nd.set_new_netip_suffix(act_dev.get_new_netip_suffix())
                    # set html-fields
                    new_nd.set_fields(ndc_lut)
                    # add new netip-field
                    new_nd.add_network_stuff(new_netip_dict)
                    # set html-fields
                    new_nd.get_ip(-1).set_fields(nic_lut)
                    # add autoselect field for new-netip field
                    net_sel_list.add_pe_key_ref(act_dev.get_new_netip_suffix(), 0)
                    # peer fields
                    peer_list.check_selection(new_nd.get_suffix(), "p0")
                    peer_penalty.check_selection(new_nd.get_suffix(), "1")
                    adapt_str = "Adapting network for %s from %s (%s, %s, %s)" % (act_dev.get_name(),
                                                                                  src_dev.get_name(),
                                                                                  logging_tools.get_plural("netdevice", netdev_ok),
                                                                                  logging_tools.get_plural("netip", netip_ok),
                                                                                  logging_tools.get_plural("peer", peer_ok))
                    if adapted_status:
                        change_log.add_ok(adapt_str, "copy")
                    else:
                        change_log.add_warn(adapt_str, "copy")
                    # rebuild hocpount table
                    rebuild_hopcount = 1
                    rebuild_hc_causes["adapted_network"] = 1
                else:
                    change_log.add_error("Cannot adapt network from myself (device %s)" % (act_dev.get_name()), "error")
            if not adapted:
                act_dev.add_network_stuff(new_ndev_dict)
                for act_nd in act_dev.get_sorted_netdevice_list():
                    possible_nd_types = [k for k, v in net_dt_tree.iteritems() if act_nd.get_name().startswith(v["identifier"])]
                    if possible_nd_types:
                        act_nd_type = possible_nd_types[0]
                    else:
                        act_nd_type = 0
                    # mac_bytes
                    #print "%s has %d mac_bytes" % (act_nd.get_name(), net_dt_tree[act_nd_type]["mac_bytes"]), "<br>"
                    # modify ndc_lut
                    ndc_lut["macadr"]      = {ndev_macadrs[act_nd_type]      : None,
                                              "compound"                     : "devmac"}
                    ndc_lut["fake_macadr"] = {ndev_fake_macadrs[act_nd_type] : None,
                                              "compound"                     : "devmac"}
                    nic_lut["ip"]["netdevice"] = act_nd
                    #print "%s %s - %s %s<br>" % ("-"*10, act_dev.get_name(), act_nd.get_name(), "-"*10)
                    if ndev_del.check_selection(act_nd.get_suffix()) or (act_nd.get_name() == glob_ndev_name and glob_ndev_del):
                        change_log.add_ok("Deleting netdevice '%s' on device %s" % (act_nd.get_name(), act_dev.get_name()), "del")
                        act_dev.delete_network_device(act_nd.get_idx())
                        nd_del_list.append(act_nd.get_idx())
                        ip_del_list.extend(act_nd.get_ip_idxs())
                        # rebuild hocpount table
                        rebuild_hopcount = 1
                        rebuild_hc_causes["netdevice_deleted"] = 1
                        ip_change_causes.setdefault(act_dev.get_name(), []).append("netdevice deleted")
                    else:
                        #ndn = ndev_name.check_selection(act_nd.get_suffix(), act_nd.get_name())
                        # is_new_netdevice is 1 if we are handling the prototype for a new netdevice
                        # add_new_netdevice is 1 if is_new_netdevice == 1 and we are actually adding a new netdevice
                        is_new_netdevice, add_new_netdevice = (act_nd.get_idx() < 0, 0)
                        ndev_macadrs[act_nd_type].check_selection(act_nd.get_suffix(), act_nd["macadr"])
                        if (ndev_name.check_selection(act_nd.get_suffix(), act_nd["devname"]).strip() == glob_ndev_name or is_new_netdevice) and (glob_ndev_name != nndn_default and not glob_ndev_del):
                            rd_dict = {"netdevice_speed" : glob_nd.get_suffix(),
                                       "fake_macadr"     : "m" in sub_sel and glob_nd.get_suffix() or act_nd.get_suffix(),
                                       "dhcp_device"     : "m" in sub_sel and glob_nd.get_suffix() or act_nd.get_suffix(),
                                       "driver"          : "h" in sub_sel and glob_nd.get_suffix() or act_nd.get_suffix(),
                                       "driver_options"  : "h" in sub_sel and glob_nd.get_suffix() or act_nd.get_suffix(),
                                       "ethtool_options" : "h" in sub_sel and glob_nd.get_suffix() or act_nd.get_suffix(),
                                       "routing"         : "p" in sub_sel and glob_nd.get_suffix() or act_nd.get_suffix(),
                                       "penalty"         : "p" in sub_sel and glob_nd.get_suffix() or act_nd.get_suffix()
                                       }
                        else:
                            rd_dict = {}
                        if is_new_netdevice:
                            # add new netdevice
                            if ndev_name.check_selection(act_nd.get_suffix(), act_nd["devname"]).strip() == nndn_default and glob_ndev_name != nndn_default and not glob_ndev_del and glob_ndev_name not in act_dev.get_netdevice_names():
                                rd_dict["devname"] = glob_nd.get_suffix()
                        if mac_random_button.check_selection(act_nd.get_suffix()):
                            while True:
                                random_mac = "%s:%02x:%02x" % (RANDOM_XEN_MAC_PREFIX,
                                                               random.randrange(0, 255),
                                                               random.randrange(0, 255))
                                req.dc.execute("SELECT * FROM netdevice WHERE macadr=%s", (random_mac))
                                if not req.dc.rowcount:
                                    break
                            ndev_macadrs[act_nd_type].set_sys_value(act_nd.get_suffix(), random_mac)
                        act_nd.check_for_changes(ndc_lut, sub, rd_dict)
                        # generate info string
                        if is_new_netdevice:
                            new_ndev_name = act_nd["devname"]
                            ndev_name[act_dev.get_new_netdevice_suffix()] = nndn_default
                            ndev_macadrs[act_nd_type][act_dev.get_new_netdevice_suffix()] = "00:00:00:00:00:00"
                            ndev_fake_macadrs[act_nd_type][act_dev.get_new_netdevice_suffix()] = "00:00:00:00:00:00"
                            alter_str, info_str = ("set ", " for new netdevice on device '%s'" % (act_dev.get_name()))
                            change = 0
                            num_e, num_w, num_ok = act_nd.get_num_field()
                            add_new_netdevice = new_ndev_name != nndn_default and not num_e
                            # set a valid netip-suffix for the new netdevice (to avoid stuff like <abc>-1<YYY>)
                            act_nd.set_new_netip_suffix(act_dev.get_new_netip_suffix())
                            show_log = add_new_netdevice or num_e or num_w
                        else:
                            alter_str, info_str = ("altered ", " for netdevice '%s' on device '%s'" % (act_nd.get_name(), act_dev.get_name()))
                            change = 1
                            add_new_netdevice = 0
                            show_log = 1
                        act_nd.add_network_stuff(new_netip_dict)
                        err_list, warn_list, ok_list = act_nd.build_change_lists(alter_str, info_str, change, is_new_netdevice, 1)
                        if show_log:
                            change_log.add_errors(err_list)
                            change_log.add_warns(warn_list)
                        if not is_new_netdevice or (is_new_netdevice and add_new_netdevice):
                            change_log.add_oks(ok_list)
                            if is_new_netdevice:
                                # copy the netdevice instance
                                old_nd = act_nd.copy_instance()
                                old_nd.set_suffix(act_dev.get_new_netdevice_suffix())
                                old_nd.set_new_netip_suffix(act_dev.get_new_netip_suffix())
                                old_nd.add_network_stuff(new_netip_dict)
                                old_nd.get_ip(-1).set_fields(nic_lut)
                                net_sel_list.add_pe_key_ref(old_nd.get_new_netip_suffix(), 0)
                                # set device idx
                                act_nd["device"] = dev
                                # generate db-entry
                                act_nd.commit_sql_changes(req.dc, 1, 1)
                                # new netip suffix
                                act_nd.set_new_netip_suffix()
                                # enqueue
                                act_dev.enqueue_new_netdevice(act_nd)
                                # set fields
                                act_nd.set_fields(ndc_lut)
                                ndev_del[act_nd.get_suffix()] = 0
                                act_dev.add_netdevice(old_nd)
                                # copy selection
                                #print act_dev.get_new_netip_suffix(), act_nd.get_new_netip_suffix(), "...<br>"
                                for field in net_sel_list, net_ip, net_ip_alias, net_ip_alias_excl:
                                    field.copy_selection(act_dev.get_new_netip_suffix(), act_nd.get_new_netip_suffix())
                                for field in peer_list, peer_penalty:
                                    field.copy_selection(old_nd.get_suffix(), act_nd.get_suffix())
                                # new network device type
                                new_nd_type = [k for k, v in net_dt_tree.iteritems() if act_nd.get_name().startswith(v["identifier"])][0]
                                # set mac/fake_mac
                                #print "%s has %d mac_bytes" % (act_nd.get_name(), net_dt_tree[new_nd_type]["mac_bytes"]), "<br>"
                                ndev_macadrs[new_nd_type][act_nd.get_suffix()] = act_nd["macadr"]
                                ndev_fake_macadrs[new_nd_type][act_nd.get_suffix()] = act_nd["fake_macadr"]
                                mac_random_button[act_nd.get_suffix()] = 0
                                peer_list.check_selection(old_nd.get_suffix(), "p0")
                                peer_penalty.check_selection(old_nd.get_suffix(), "1")
                                # check for loopback <-> loopback peer
                                if act_nd["devname"].startswith("lo"):
                                    new_penalty = 1
                                    req.dc.execute("INSERT INTO peer_information SET s_netdevice=%d, d_netdevice=%d, penalty=%d" % (act_nd.get_idx(), act_nd.get_idx(), new_penalty))
                                    new_pe_idx = req.dc.insert_id()
                                    act_nd.add_peer_information(new_pe_idx, act_nd.get_idx(), new_penalty)
                                    peer_del[act_nd.get_peer_suffix(new_pe_idx)] = 0
                                    peer_penalty[act_nd.get_peer_suffix(new_pe_idx)] = act_nd.get_penalty(new_pe_idx)
                                    fe_peers[act_nd.get_idx()] = {"device_idx"    : act_dev.get_idx(),
                                                                  "name"          : act_dev.get_name(),
                                                                  "devname"       : act_nd.get_name(),
                                                                  "penalty"       : act_nd["penalty"],
                                                                  "netdevice_idx" : act_nd.get_idx(),
                                                                  "routing"       : act_nd["routing"]}
                                    change_log.add_ok("Adding peer %s for loopback-device '%s' on device %s" % (act_nd.get_peer_information(new_pe_idx, fe_peers), act_nd.get_name(), act_dev.get_name()), "ok")
                                    # rebuild hocpount table
                                    rebuild_hopcount = 1
                                    rebuild_hc_causes["new_peer"] = 1
                                ip_change_causes.setdefault(act_dev.get_name(), []).append("netdevice added")
                            else:
                                act_nd.commit_sql_changes(req.dc, 1)
                                # FIXME, add rebuild_hopcount here if necessary
                            # loop over ip-stuff
                            for act_ip in act_nd.get_sorted_netip_list():
                                if glob_net_network != "0":
                                    if act_ip["network"] == glob_net_network and glob_ndev_name == act_nd["devname"] and glob_net_ip_del:
                                        net_ip_del.set_sys_value(act_ip.get_suffix(), 1)
                                if net_ip_del.check_selection(act_ip.get_suffix(), 0):
                                    change_log.add_ok("Delete IP %s from netdevice %s on device %s" % (act_ip.get_name(), act_nd.get_name(), act_dev.get_name()), "OK")
                                    ip_del_list += [act_ip.get_idx()]
                                    act_nd.delete_ip(act_ip.get_idx())
                                    rebuild_etc_hosts = 1
                                    rebuild_eh_causes["del_ip"] = 1
                                    ip_change_causes.setdefault(act_dev.get_name(), []).append("ip deleted")
                                else:
                                    is_new_netip, add_netip = (act_ip.get_idx() < 0, 0)
                                    if is_new_netip and "i" in sub_sel and glob_ndev_name == act_nd["devname"] and glob_net_ip != "0.0.0.0":
                                        rd_dict = {"ip"         : glob_nd.get_new_netip_suffix(),
                                                   "network"    : glob_nd.get_new_netip_suffix(),
                                                   "alias"      : glob_nd.get_new_netip_suffix(),
                                                   "alias_excl" : glob_nd.get_new_netip_suffix()}
                                    else:
                                        rd_dict = {}
                                    if "i" in sub_sel:
                                        old_ip_val, old_alias_val, old_alias_excl_val = (act_ip["ip"].strip(),
                                                                                         act_ip["alias"].strip(),
                                                                                         act_ip["alias_excl"])
                                        act_ip.check_for_changes(nic_lut, sub, rd_dict)
                                        if is_new_netip:
                                            new_netip_name = act_ip["ip"]
                                            alter_str, info_str = ("set ", " for new ip on netdevice '%s' (device '%s')" % (act_nd.get_name(), act_dev.get_name()))
                                            change = 0
                                            num_e, num_w, num_ok = act_ip.get_num_field()
                                            #print new_netip_name, num_e, num_w, num_ok, "<br>"
                                            add_new_netip = new_netip_name != "0.0.0.0" and not num_e
                                            show_log = add_new_netip or num_e or num_w
                                            if rd_dict and act_ip["network"]:
                                                if net_tree[act_ip["network"]]["ntident"] != "l":
                                                    # increase IP-address if not a loopback-network
                                                    net_ip.set_sys_value(glob_nd.get_new_netip_suffix(), str(ipvx_tools.ipv4(net_ip.check_selection(glob_nd.get_new_netip_suffix())) + ipvx_tools.ipv4("0.0.0.1")))
                                            # check for localhost alias
                                            if act_ip["alias"] == "localhost" and not act_ip["alias_excl"]:
                                                act_ip["alias_excl"] = 1
                                        else:
                                            alter_str, info_str = ("altered ", " for ip %s on netdevice '%s' (device '%s')" % (act_ip["ip"], act_nd.get_name(), act_dev.get_name()))
                                            change = 1
                                            add_new_netip = 0
                                            show_log = 1
                                        err_list, warn_list, ok_list = act_ip.build_change_lists(alter_str, info_str, change, is_new_netip, 1)
                                        if show_log:
                                            change_log.add_errors(err_list)
                                            change_log.add_warns(warn_list)
                                        if not is_new_netip or (is_new_netip and add_new_netip):
                                            used_nets.setdefault(act_ip["network"], []).append((act_ip["ip"], act_nd.get_name()))
                                            change_log.add_oks(ok_list)
                                            if is_new_netip:
                                                # copy the netip instance
                                                old_ip = act_ip.copy_instance()
                                                old_ip.set_suffix(act_nd.get_new_netip_suffix())
                                                if act_ip["ip"] == "127.0.0.1":
                                                    if not act_ip["alias_excl"]:
                                                        act_ip["alias_excl"] = 1
                                                    if not act_ip["alias"]:
                                                        act_ip["alias"] = "localhost"
                                                    if act_ip["alias"] != "localhost":
                                                        change_log.add_warn("new IP for localhost on %s has wrong alias '%s'" % (act_dev.get_name(),
                                                                                                                                 act_ip["alias"]), "config")
                                                        
                                                #print act_ip["netdevice"], old_ip["netdevice"],"<br>"
                                                net_ip[old_ip.get_suffix()] = new_netip_dict["ip"]
                                                net_sel_list[old_ip.get_suffix()] = new_netip_dict["network"]
                                                net_ip_alias[old_ip.get_suffix()] = new_netip_dict["alias"]
                                                net_ip_alias_excl[old_ip.get_suffix()] = 0
                                                act_ip["netdevice"] = act_nd.get_idx()
                                                used_ip_dict.setdefault(act_ip["network"], []).append(act_ip["ip"])
                                                act_ip.commit_sql_changes(req.dc, 1, 1, 0)
                                                act_nd.enqueue_new_netip(act_ip)
                                                act_ip.set_fields(nic_lut)
                                                net_ip_del[act_ip.get_suffix()] = 0
                                                act_nd.add_netip(old_ip)
                                                #err_list, warn_list, ok_list = act_ip.build_change_lists(alter_str, info_str, 1, 0, 1)
                                                rebuild_etc_hosts = 1
                                                rebuild_eh_causes["new_ip"] = 1
                                                ip_change_causes.setdefault(act_dev.get_name(), []).append("ip added")
                                            else:
                                                act_ip.commit_sql_changes(req.dc, 1, 0)
                                                if old_ip_val != act_ip["ip"].strip():
                                                    rebuild_etc_hosts = 1
                                                    rebuild_eh_causes["change_ip"] = 1
                                                    ip_change_causes.setdefault(act_dev.get_name(), []).append("ip changed")
                                                if old_alias_val != act_ip["alias"]:
                                                    rebuild_etc_hosts = 1
                                                    rebuild_eh_causes["change_ip"] = 1
                                                    ip_change_causes.setdefault(act_dev.get_name(), []).append("alias changed")
                                                if old_alias_excl_val != act_ip["alias_excl"]:
                                                    rebuild_etc_hosts = 1
                                                    rebuild_eh_causes["change_ip"] = 1
                                                    ip_change_causes.setdefault(act_dev.get_name(), []).append("alias_exclusive flag changed")
                            net_sel_list.add_pe_key_ref(act_nd.get_new_netip_suffix(), 0)

                            # peer stuff
                            for peer_idx in act_nd.get_peer_idxs():
                                if peer_del.check_selection(act_nd.get_peer_suffix(peer_idx), 0):
                                    # peer deletion
                                    if peer_idx not in peer_del_list:
                                        peer_del_list.append(peer_idx)
                                    change_log.add_ok("Deleting peer %s from netdevice '%s' on device %s" % (act_nd.get_peer_information(peer_idx, fe_peers), act_nd.get_name(), act_dev.get_name()), "deleted")
                                    pep_idx = act_nd.get_peer_endpoint(peer_idx)
                                    if pep_idx != act_nd.get_idx():
                                        # delete peer from foreign netdevice (pep_idx)
                                        if fe_peers.has_key(pep_idx):
                                            fe_peer = fe_peers[pep_idx]
                                            if dev_dict.has_key(fe_peer["device_idx"]):
                                                try:
                                                    fe_nd = dev_dict[fe_peer["device_idx"]].get_netdevice_struct(fe_peer["netdevice_idx"])
                                                except KeyError:
                                                    change_log.add_error("Cannot remove peer_informatione, netdevice deleted ? (netdevice '%s' on device %s)" % (act_nd.get_name(), act_dev.get_name()), "keyError")
                                                else:
                                                    fe_nd.delete_peer(peer_idx)
                                    act_nd.delete_peer(peer_idx)
                                    # rebuild hocpount table
                                    rebuild_hopcount = 1
                                    rebuild_hc_causes["peer_deleted"] = 1
                                else:
                                    new_p = peer_penalty.check_selection(act_nd.get_peer_suffix(peer_idx), str(act_nd.get_penalty(peer_idx)))
                                    # check validity of peer_penalty
                                    if new_p.isdigit() and int(new_p) > 0:
                                        new_p = int(new_p)
                                        if new_p != act_nd.get_penalty(peer_idx):
                                            change_log.add_ok("Altered peer_penalty %s to netdevice '%s' on device %s to %d" % (act_nd.get_peer_information(peer_idx, fe_peers), act_nd.get_name(), act_dev.get_name(), new_p), "ok")
                                            pep_idx = act_nd.get_peer_endpoint(peer_idx)
                                            # correct foreign netdevice
                                            if fe_peers.has_key(pep_idx):
                                                fe_peer = fe_peers[pep_idx]
                                                if dev_dict.has_key(fe_peer["device_idx"]):
                                                    try:
                                                        fe_nd = dev_dict[fe_peer["device_idx"]].get_netdevice_struct(fe_peer["netdevice_idx"])
                                                    except KeyError:
                                                        pass
                                                    else:
                                                        fe_nd.set_penalty(peer_idx, new_p)
                                                        peer_penalty.set_sys_value(fe_nd.get_peer_suffix(peer_idx), str(new_p))
                                                        peer_penalty[fe_nd.get_peer_suffix(peer_idx)] = str(new_p)
                                            act_nd.set_penalty(peer_idx, new_p)
                                            req.dc.execute("UPDATE peer_information SET penalty=%d WHERE peer_information_idx=%d" % (new_p, peer_idx))
                                            # rebuild hocpount table
                                            rebuild_hopcount = 1
                                            rebuild_hc_causes["modified_peer"] = 1
                                    else:
                                        change_log.add_error("Cannot alter peer_penalty %s to netdevice '%s' on device %s" % (act_nd.get_peer_information(peer_idx, fe_peers), act_nd.get_name(), act_dev.get_name()), "peer_penalty must be > 0")
                                        peer_penalty[act_nd.get_peer_suffix(peer_idx)] = str(act_nd.get_penalty(peer_idx))
                            new_peer = peer_list.check_selection(act_nd.get_suffix(), "p0")
                            new_peer_penalty = peer_penalty.check_selection(act_nd.get_suffix(), "1")
                            if glob_ndev_name == act_nd["devname"] and new_glob_peer != "p0":
                                new_peer         = new_glob_peer
                                new_peer_penalty = new_glob_peer_penalty
                            if new_peer != "p0":
                                # check validity of peer_penalty
                                if new_peer_penalty.isdigit() and int(new_peer_penalty) > 0:
                                    new_penalty = int(new_peer_penalty)
                                    new_pe = fe_peers[peer_list[new_peer]["idx"]]
                                    if new_pe["netdevice_idx"] in act_nd.get_peers():
                                        change_log.add_error("Cannot add new peer to netdevice '%s' on device %s" % (act_nd.get_name(), act_dev.get_name()), "peer already used")
                                    else:
                                        # rebuild hocpount table
                                        rebuild_hopcount = 1
                                        rebuild_hc_causes["new_peer"] = 1
                                        req.dc.execute("INSERT INTO peer_information SET s_netdevice=%d, d_netdevice=%d, penalty=%d" % (act_nd.get_idx(), new_pe["netdevice_idx"], new_penalty))
                                        new_pe_idx = req.dc.insert_id()
                                        act_nd.add_peer_information(new_pe_idx, new_pe["netdevice_idx"], new_penalty)
                                        if dev_dict.has_key(new_pe["device_idx"]):
                                            # add peer stuff to other device
                                            fe_nd = dev_dict[new_pe["device_idx"]].get_netdevice_struct(new_pe["netdevice_idx"])
                                            fe_nd.add_peer_information(new_pe_idx, act_nd.get_idx(), new_penalty)
                                            # create foreign-peer info
                                            fe_peers[act_nd.get_idx()] = {"device_idx"    : act_dev.get_idx(),
                                                                          "name"          : act_dev.get_name(),
                                                                          "devname"       : act_nd.get_name(),
                                                                          "penalty"       : act_nd["penalty"],
                                                                          "netdevice_idx" : act_nd.get_idx(),
                                                                          "routing"       : act_nd["routing"]}
                                        change_log.add_ok("Adding peer %s from netdevice '%s' on device %s" % (act_nd.get_peer_information(new_pe_idx, fe_peers), act_nd.get_name(), act_dev.get_name()), "ok")
                                        peer_del[act_nd.get_peer_suffix(new_pe_idx)] = 0
                                        peer_penalty[act_nd.get_peer_suffix(new_pe_idx)] = act_nd.get_penalty(new_pe_idx)
                                else:
                                    change_log.add_error("Cannot add new peer to netdevice '%s' on device %s" % (act_nd.get_name(), act_dev.get_name()), "peer_penalty must be >= 0")
                            peer_penalty[act_nd.get_suffix()] = "1"
                        else:
                            net_sel_list.add_pe_key_ref(act_dev.get_new_netip_suffix(), 0)
                            net_ip[act_dev.get_new_netip_suffix()] = new_netip_dict["ip"]
                            net_ip_alias.check_selection(act_dev.get_new_netip_suffix(), new_netip_dict["alias"])
                            net_ip_alias_excl.check_selection(act_dev.get_new_netip_suffix())
                            net_sel_list.check_selection(act_dev.get_new_netip_suffix(), new_netip_dict["network"])
                            peer_list.check_selection(act_nd.get_suffix(), "p0")
                            peer_penalty.check_selection(act_nd.get_suffix(), "1")
            warn_nets = dict([(k, v) for k, v in used_nets.iteritems() if len(v) > 1])
            if warn_nets:
                change_log.add_warn("%s used more than once (device %s): %s" % (logging_tools.get_plural("net", len(warn_nets.keys())),
                                                                                act_dev.get_name(),
                                                                                "; ".join(["%s: %s" % (net_tree[k]["name"],", ".join(["%s on %s" % (a, b) for a, b in v])) for k, v in warn_nets.iteritems()])), "Routing problem")
            num_bnd, first_bnd = (0, 0)
            for act_nd in act_dev.get_sorted_netdevice_list():
                for act_ip in act_nd.get_sorted_netip_list():
                    ip_nw = act_ip["network"]
                    if ip_nw:
                        if net_tree.has_key(ip_nw):
                            if net_tree[ip_nw]["ntident"] == "l" and act_ip["ip"] == "127.0.0.1":
                                if act_ip["alias"] != "localhost" or not act_ip["alias_excl"]:
                                    change_log.add_warn("loopback IP %s on device %s has wrong alias settings ('%s', is_exclusive: %s)" % (act_ip["ip"],
                                                                                                                                           act_dev.get_name(),
                                                                                                                                           act_ip["alias"],
                                                                                                                                           {0 : "off",
                                                                                                                                            1 : "on"}[act_ip["alias_excl"]]), "config")
                            if net_tree[ip_nw]["ntident"] == "b":
                                if not num_bnd:
                                    first_bnd = act_nd
                                num_bnd += 1
                        else:
                            change_log.add_warn("Network id %d not defined" % (ip_nw), "config")
            #print had_bnd, num_bnd, first_bnd, "<br>"
            if (had_bnd and num_bnd) or (not had_bnd and not num_bnd):
                # no changes
                pass
            elif had_bnd:
                # delete bootnetdevice
                change_log.add_ok("Deleting Bootnetdevice from device '%s'" % (act_dev.get_name()), "removed")
                act_dev.set_bootnetdevice(0)
                act_dev.add_sql_changes({"bootnetdevice" : 0})
                act_dev.add_log_entry(user_log_source_idx,
                                      req.user_info.get_idx(),
                                      req.log_status.get("i", {"log_status_idx" : 0})["log_status_idx"],
                                      "deleting bootnetdevice")
            else:
                # add bootnetdevice
                act_dev.set_bootnetdevice(first_bnd.get_idx())
                change_log.add_ok("Setting Bootnetdevice to '%s' for device '%s'" % (first_bnd.get_name(), act_dev.get_name()), "ok")
                act_dev.add_sql_changes({"bootnetdevice" : first_bnd.get_idx()})
                act_dev.add_log_entry(user_log_source_idx,
                                      req.user_info.get_idx(),
                                      req.log_status.get("i", {"log_status_idx" : 0})["log_status_idx"],
                                      "setting bootnetdevice to '%s'" % (first_bnd.get_name()))
            # handle change of the bootnetdevice-macadr
            # if the new macaddress is equal to 00:00:00:00:00:00 we assume no new bootnd
            act_bnd_name, act_bnd_drv, act_bnd_opts, act_bnd_eth_opts = (None, None, None, None)
            if num_bnd:
                if first_bnd["macadr"] == "00:00:00:00:00:00":
                    num_bnd = 0
                else:
                    act_bnd_name, act_bnd_drv, act_bnd_opts, act_bnd_eth_opts = (first_bnd["devname"],
                                                                                 first_bnd["driver"],
                                                                                 first_bnd["driver_options"],
                                                                                 first_bnd["ethtool_options"])
            # determine write/delete/update_macadr action
            mac_action = None
            if (not had_bnd) or (not num_bnd):
                # no previous bootmacaddress
                if (not num_bnd):
                    # no new bootmac or new bootmac empty, do nothing
                    pass
                else:
                    # set new bnd macadr
                    mac_action = "alter_macadr"
            else:
                # previous bootmacaddress
                if (not num_bnd):
                    # no new bootmac or new bootmac empty, delete macadr
                    mac_action = "delete_macadr"
                elif bnd_mac != first_bnd["macadr"]:
                    # new bootmac and changed, change
                    mac_action = "alter_macadr"
                else:
                    # new bootmac boot not changed, do nothing
                    pass
            # do we have to refresh the target state (driver/driver_option change?)
            ts_action = None
            if (bnd_name != act_bnd_name or bnd_drv != act_bnd_drv or bnd_opts != act_bnd_opts or bnd_eth_opts != act_bnd_eth_opts) and (num_bnd):
                ts_action = "refresh_tk"
            if act_dev.get_bootserver():
                if mac_action:
                    bootserver_dict[act_dev.get_bootserver()]["action_dict"].setdefault(mac_action, []).append(act_dev.get_name())
                if ts_action:
                    bootserver_dict[act_dev.get_bootserver()]["action_dict"].setdefault(ts_action, []).append(act_dev.get_name())
            if copy_dev_idx:
                net_copy_source[act_dev.get_suffix()] = "d%04d" % (copy_dev_idx)
            else:
                net_copy_source[act_dev.get_suffix()] = None
            copy_dev_idx += 1
            act_dev.commit_sql_changes(req.dc)
    #for
    for dev_name in ip_change_causes.keys():
        act_dev = dev_lut_dict[dev_name]
        if act_dev.get_bootserver():
            bootserver_dict[act_dev.get_bootserver()]["action_dict"].setdefault("ip_changed", []).append(dev_name)
    #print ip_change_causes, bootserver_dict
    # generate ss_list
    for bs_idx, bs_stuff in bootserver_dict.iteritems():
        for action, host_list in bs_stuff["action_dict"].iteritems():
            ss_list.append(tools.s_command(req, "mother_server", 8001, action, host_list, 10, bs_stuff["name"]))
    if rebuild_hopcount:
        ss_list.extend(tools.rebuild_hopcount(req, change_log, rebuild_hc_causes))
    elif rebuild_etc_hosts:
        ss_list.extend(tools.rebuild_etc_hosts(req, change_log, rebuild_eh_causes))
    if rebuild_etc_hosts or relay_device_changed:
        # no nagios-signaling when changing the hopcount-table !
        tools.signal_nagios_config_server(req, change_log)
    ndev_name[glob_nd.get_suffix()] = nndn_default
    if ip_del_list:
        change_log.add_warn("Deleting %s" % (logging_tools.get_plural("netip", len(ip_del_list))), "ok")
        req.dc.execute("DELETE FROM netip WHERE %s" % (" OR ".join(["netip_idx=%d" % (x) for x in ip_del_list])))
    if peer_del_list:
        change_log.add_warn("Deleting %s" % (logging_tools.get_plural("peer_information", len(peer_del_list))), "ok")
        req.dc.execute("DELETE FROM peer_information WHERE %s" % (" OR ".join(["peer_information_idx=%d" % (x) for x in peer_del_list])))
    if nd_del_list:
        req.dc.execute("DELETE FROM netdevice WHERE %s" % (" OR ".join(["netdevice_idx=%d" % (x) for x in nd_del_list])))
        change_log.add_warn("Deleting the peer_information referencing %s" % (logging_tools.get_plural("deleted netdevice", len(nd_del_list))), "ok")
        sql_str = "DELETE FROM peer_information WHERE %s OR %s" % (" OR ".join(["s_netdevice=%d" % (x) for x in nd_del_list]),
                                                                   " OR ".join(["d_netdevice=%d" % (x) for x in nd_del_list]))
        req.dc.execute(sql_str)
        for act_dev in dev_dict.values():
            act_dev.remove_defective_peers(nd_del_list)
    tools.iterate_s_commands(ss_list, change_log)
    # save device logs
    log_entries = sum([dev.get_log_entries() for dev in dev_dict.itervalues()], [])
    if log_entries:
        form_str = ",".join([x for x, y in log_entries])
        form_data = tuple(sum([list(y) for x, y in log_entries], []))
        req.dc.execute("INSERT INTO devicelog VALUES%s" % (form_str), form_data)
    req.write(change_log.generate_stack("Action log"))
    req.write(html_tools.gen_hline(dev_tree.get_sel_dev_str(), 2))
    out_table = html_tools.html_table(cls="normal")
    req.write(out_table.get_header())
    nw_adapt_possible = 0
    row0_idx = 0
    sub_str = "".join([x for x in ["m", "h", "p"] if x in sub_sel])
    fls_g = {""    : ["nc"           ],
             "m"   : ["nc" , "m"     ],
             "h"   : ["nhc"          ],
             "p"   : ["npc"          ],
             "hp"  : ["npc", "h"     ],
             "mh"  : ["nhc", "m"     ],
             "mp"  : ["npc", "m"     ],
             "mhp" : ["npc", "h", "m"]}[sub_str]
    for dg in dg_sel_eff + [0]:
        if dg:
            out_table[1][1:4] = html_tools.content(dev_tree.get_sel_dev_str(dg), cls="devgroup")
            dev_list = [dev_dict[x] for x in d_sel if x in dev_tree.get_sorted_dev_idx_list(dg)]
        else:
            out_table[1][1:4] = html_tools.content("Global settings", cls="devgroup")
            dev_list = [dev_dict[0]]
        req.write(out_table.flush_lines())
        for act_dev in dev_list:
            dev_idx = act_dev.get_idx()
            #print "*", act_dev.get_name(), dev_idx, "<br>"
            line0_class = "line0%d" % (row0_idx)
            row0_idx = 1 - row0_idx
            # second_line_string_generator
            out_table[1]["class"] = line0_class
            #out_table[1:num_nd][1] = html_tools.content(act_dev.get_name(), cls="left")
            hidden_f = []
            if dev_idx:
                out_table[1][2:4] = html_tools.content(["%s, %s, %s %s" % (logging_tools.get_plural("netdevice", act_dev.get_number_of_netdevices()),
                                                                           logging_tools.get_plural("netip", act_dev.get_number_of_ips()),
                                                                           logging_tools.get_plural("peer", act_dev.get_number_of_peers()),
                                                                           "(%d local)" % (act_dev.get_number_of_peers()-act_dev.get_number_of_peers(1))),
                                                        ",\n refresh hardwareinfo: ",
                                                        refresh_hw,
                                                        ",\n fetch networkinfo: ",
                                                        fetch_network_info,
                                                        ", relaying device: ",
                                                        relay_devices], cls="left")
                first_line_open = False
                act_line = 1
            else:
                act_line = 0
                first_line_open = True
            row1_idx = 0
            for act_nd in act_dev.get_sorted_netdevice_list():
                act_nd.check_for_virtual_netdevice()
                act_nd_type = [k for k, v in net_dt_tree.iteritems() if act_nd.get_name().startswith(v["identifier"])][0]
                nd_is_boot_dev = act_dev.netdevice_is_bootnetdevice(act_nd.get_idx())
                if act_nd.get_idx() > 0:
                    line1_class, input_class = ("line1%d" % (row1_idx), None)
                else:
                    line1_class, input_class = (line0_class, line0_class)
                if input_class:
                    for f_mac in [ndev_macadrs[act_nd_type], ndev_fake_macadrs[act_nd_type], dhcp_device_button, mac_random_button,
                                  autoneg_sel_list, duplex_sel_list, speed_sel_list, ndev_drv, ndev_drv_options, routing_button, descr_field, ndev_penalty, vlan_id_field]:
                        f_mac.set_class(act_nd.get_suffix(), input_class)
                row1_idx = 1 - row1_idx
                # generate strings
                dc_descr, dc_id = (net_dt_tree.get(act_nd["network_device_type"], {}).get("description", "unknown"),
                                   net_dt_tree.get(act_nd["network_device_type"], {}).get("identifier", "unknown"))
                if dc_descr.endswith(" devices"):
                    dc_descr = dc_descr[:-len(" devices")]
                string_dict = {"c" : ["DeviceClass: %s" % (dc_descr), ", description:", descr_field, " vlan ID:", vlan_id_field],
                               "," : [","],
                               " " : [" "]}
                if dc_id not in ["lo"]:
                    if not act_nd["is_bridge"] and not act_nd.is_virtual and not (dev_idx and act_dev.get_xen_guest()):
                        string_dict["n"] = ["Target speed:", netdev_speed_sel_list]
                    # not mac and autoneg-config for loopback devices
                    if "m" in sub_sel and not act_nd.is_virtual:
                        if net_dt_tree[act_nd_type]["mac_bytes"]:
                            if act_nd["is_bridge"]:
                                string_dict["m"] = ["MACaddr: %s" % (act_nd["macadr"])]
                            else:
                                string_dict["m"] = ["MACaddr:", ndev_macadrs[act_nd_type], "\n, fake MACaddr:", ndev_fake_macadrs[act_nd_type], "\n, force write DHCP Address:", dhcp_device_button]
                                if dev_idx and act_dev.get_xen_guest():
                                    string_dict["m"].extend([", random MAC-Address:", mac_random_button, " connected to bridge", bridge_list])
                        else:
                            string_dict["m"] = ["no MAC-Address available"]
                    else:
                        hidden_f.extend([x.create_hidden_var(act_nd.get_suffix()) for x in [ndev_macadrs[act_nd_type], ndev_fake_macadrs[act_nd_type], dhcp_device_button]])
                    if "h" in sub_sel and not act_nd.is_virtual and not (dev_idx and act_dev.get_xen_guest()):
                        string_dict["h"] = ["Autonegotiation:", autoneg_sel_list, "\nDuplex ", duplex_sel_list, "\nSpeed ", speed_sel_list, "\nDriver:", ndev_drv, "\nDriver options:", ndev_drv_options]
                    else:
                        hidden_f.extend([x.create_hidden_var(act_nd.get_suffix()) for x in [autoneg_sel_list, duplex_sel_list, speed_sel_list, ndev_drv, ndev_drv_options]])
                if "p" in sub_sel:
                    string_dict["p"] = ["forwarding:", routing_button, "\npenalty:", ndev_penalty]
                else:
                    hidden_f.extend([x.create_hidden_var(act_nd.get_suffix()) for x in [routing_button, ndev_penalty, vlan_id_field]])
                if not first_line_open:
                    out_table[act_line + 1]["class"] = line1_class
                first_line_open = False
                colspan = 1 if (act_nd.get_idx() > 0 or not dev_idx) else 2
                # generate first/second line strings
                line_idx = act_line
                for s_keys in fls_g:
                    act_line_f = sum([string_dict[key] for key in s_keys if string_dict.has_key(key)], [])
                    if act_line_f:
                        line_idx += 1
                        if line_idx != act_line + 1:
                            out_table[line_idx]["class"] = line1_class
                        out_table[line_idx][5-colspan : 4] = html_tools.content(act_line_f, act_nd.get_suffix(), cls="left")
                if colspan == 1:
                    out_table[act_line + 1:line_idx][3] = html_tools.content(ndev_del, act_nd.get_suffix(), cls="errormin")
                out_table.set_cursor(line_idx, 1)
                if not act_nd["is_bridge"]:
                    if "i" in sub_sel:
                        for act_ip in act_nd.get_sorted_netip_list():
                            ip_list = [net_ip, net_sel_list, "\n, Alias:", net_ip_alias, "\n, exclusive:", net_ip_alias_excl]
                            if act_ip.get_idx() > 0 or not dev_idx:
                                out_table[0]["class"] = "ok"
                                out_table[None][3] = html_tools.content(net_ip_del, act_ip.get_suffix(), cls="errormin")
                                out_table[None][4] = html_tools.content(ip_list, act_ip.get_suffix())
                            else:
                                out_table[0]["class"] = "warn"
                                out_table[None][3:4] = html_tools.content(["New IP "] + ip_list, act_ip.get_suffix())
                if "p" in sub_sel:
                    for act_p in act_nd.get_peer_idxs():
                        out_table[0]["class"] = "ok"
                        out_table[None][3] = html_tools.content(peer_del, act_nd.get_peer_suffix(act_p), cls="errormin")
                        out_table[None][4] = html_tools.content([act_nd.get_peer_pre_information(act_p, fe_peers),
                                                                 peer_penalty,
                                                                 act_nd.get_peer_post_information(act_p, fe_peers)], act_nd.get_peer_suffix(act_p), cls="left")
                    out_table[0]["class"] = "warn"
                    out_table[None][3:4] = html_tools.content(["New peer to ", peer_list, " with penalty ", peer_penalty], act_nd.get_suffix())
                else:
                    hidden_f.extend([peer_list.create_hidden_var(act_nd.get_suffix())])
                next_line = out_table.get_line_num()
                out_table[act_line + 1 : next_line][2] = html_tools.content([ndev_name, nd_is_boot_dev and "&nbsp;(B)" or ""], act_nd.get_suffix())
                act_line = next_line
            out_table.set_cursor(next_line, 0)
            if not dev_idx:
                out_table[0]["class"] = line0_class
                out_table[None][2:4] = html_tools.content([net_copy, "Adapt all networks (for %s possible)" % (logging_tools.get_plural("device", nw_adapt_possible))] if nw_adapt_possible else "no network adaption possible", "")
            elif not act_dev.get_number_of_netdevices():
                out_table[0]["class"] = line0_class
                out_table[None][2:4] = html_tools.content([net_copy, " Adapt Network from device ", net_copy_source], act_dev.get_suffix())
                nw_adapt_possible += 1
            out_table[1:out_table.get_line_num()][1] = html_tools.content(act_dev.get_name(), cls="left")
            if hidden_f:
                req.write("\n".join([x for x in hidden_f if x] + [""]))
            req.write(out_table.flush_lines(act_dev.get_suffix()))
    low_submit[""] = 1
    submit_button = html_tools.submit_button(req, "submit")
    submit_button.set_class("", "button")
    req.write("%s%s<div class=\"center\">%s</div>\n" % (out_table.get_footer(),
                                                        low_submit.create_hidden_var(),
                                                        submit_button("")))
    #del out_table
