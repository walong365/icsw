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
# You should have received a copy of t GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
""" device object definitions """

import logging_tools
import cdef_basics
import cdef_network
from basic_defs import IMMEDIATE_APC_OPERATIONS_ALLOWED

class device_group(cdef_basics.db_obj):
    def __init__(self, name, idx):
        cdef_basics.db_obj.__init__(self, name, idx, "g")
        self.init_sql_changes({"table" : "device_group",
                               "idx"   : self.idx})
        self.set_meta_device()
        self.configs = []
    def add_config(self, c_idx):
        self.configs.append(c_idx)
    def del_config(self, c_idx):
        self.configs.remove(c_idx)
    def has_config(self, c_idx):
        return c_idx in self.configs
    def get_num_configs(self, sub_set = []):
        return len([x for x in self.configs if x in sub_set])
    def set_meta_device(self, name = None, idx = 0):
        self.meta_device_name = None
        self.meta_device_idx = idx
    def has_meta_device(self):
        return self.meta_device_idx and 1 or 0
    def get_meta_device_idx(self):
        return self.meta_device_idx
    def set_descr(self, descr):
        self.descr = descr
    def get_descr(self):
        return self.descr

class device_variable(cdef_basics.db_obj):
    def __init__(self, name, idx, v_type, init_dict={}):
        cdef_basics.db_obj.__init__(self, name, idx, v_type)
        self.set_valid_keys({"name"        : "s",
                             "is_public"   : "i",
                             "device"      : "i",
                             "description" : "s"},
                            ["device"])
        self.init_sql_changes({"table" : "device_variable",
                               "idx"   : self.get_idx()})
        if init_dict:
            self.set_parameters(init_dict)
        self.set_type(v_type, init_dict)
    def get_long_type(self):
        return {"s" : "str",
                "i" : "int",
                "b" : "blob",
                "t" : "time",
                "d" : "date"}[self.var_type]
    def get_beautify_type(self):
        return {"s" : "String",
                "i" : "Int",
                "b" : "Blob",
                "t" : "Time",
                "d" : "Date"}[self.var_type]
    def get_type(self):
        return self.var_type
    def get_var_val_name(self):
        return "val_%s" % (self.get_long_type())
    def set_type(self, v_type, def_dict={}):
        self.var_type = v_type
        t_name, t_type = {"s" : ("str" , "s"),
                          "i" : ("int" , "i"),
                          "b" : ("blob", "s"),
                          "t" : ("time", "s"),
                          "d" : ("date", "s")}[v_type]
        self.set_valid_keys({"var_type"          : "s",
                             "val_%s" % (t_name) : t_type},
                            ["device"])
        self["var_type"] = v_type
        val_name = self.get_var_val_name()
        if def_dict and def_dict.has_key(val_name):
            self[val_name] = def_dict[val_name]
    def copy_instance(self, new_type):
        new_dv = device_variable(self.get_name(), self.get_idx(), self.get_type())
        new_dv.copy_keys(self)
        return new_dv
    
class device(cdef_basics.db_obj):
##     ok_req_match = re.compile("^ok\s+(?P<ip>\d+\.\d+\.\d+\.\d+)\s+(?P<state>.*)\s+\((?P<net>\S+)\)$")
##     warn_req_match = re.compile("^warn\s+(?P<ip>\d+\.\d+\.\d+\.\d+)\s+(?P<state>.*)\s+\((?P<net>\S+)\)$")
##     recv_match = re.compile("^(?P<state>.*)\s+\((?P<net>.+)\)$")
    def __init__(self, name, idx, group_idx, type_idx):
        cdef_basics.db_obj.__init__(self, name, idx, "d")
        self.set_valid_keys({"snmp_class"       : "d",
                             "device_class"     : "d",
                             "ng_ext_host"      : "d",
                             "nagios_checks"    : "d",
                             "root_passwd"      : "s",
                             "ng_device_templ"  : "d",
                             "device_location"  : "s"},
                            [])
        self.bootserver = 0
        self.group_idx = group_idx
        self.type_idx = type_idx
        self.apc_cons, self.ibc_cons = ([], [])
        self.set_act_state()
        self.set_req_recv_state()
        self.init_sql_changes({"table" : "device",
                               "idx"   : self.idx})
        self.init_device_flags()
        self.set_comment()
        self.set_bootnetdevice()
        self.net_tree, self.net_lut = ({}, {})
        self.hw_dict, self.pci_dict, self.dmi_dict, self.hw_last_update = ({}, {}, {}, 0)
        self.packages, self.pack_lut = ({}, {})
        self.net_dict = {}
        self.configs = []
        self.wc_files = []
        self.variables = {}
        self.set_new_device_variable_suffix()
        self.__log_entries = []
    def set_new_device_variable_suffix(self):
        self.ndvs = "%sdv" % (self.get_suffix())
    def get_new_device_variable_suffix(self):
        return self.ndvs
    def add_device_variable(self, in_dict):
        new_var = device_variable(in_dict["name"], in_dict["device_variable_idx"], in_dict["var_type"], in_dict)
        if in_dict["device_variable_idx"]  ==  0:
            new_var.set_suffix(self.get_new_device_variable_suffix())
        self.variables[new_var.get_idx()] = new_var
        new_var.act_values_are_default()
    def add_config(self, c_idx):
        self.configs.append(c_idx)
    def del_config(self, c_idx):
        self.configs.remove(c_idx)
    def has_config(self, c_idx):
        return c_idx in self.configs
    def get_num_configs(self, sub_set=[]):
        return len([x for x in self.configs if x in sub_set])
    # old code
##     def add_package(self, ip_p):
##         self.packages[ip_d.get_idx()] = ip_d
    # new code
    def add_package(self, instp_s, pack_s):
        self.packages[instp_s.get_idx()] = instp_s
        self.pack_lut[pack_s.get_idx()] = instp_s.get_idx()
    def delete_package_pack(self, pack_s):
        if self.pack_lut.has_key(pack_s.get_idx()):
            del_idx = self.pack_lut[pack_s.get_idx()]
            del self.packages[self.pack_lut[pack_s.get_idx()]]
        else:
            del_idx = 0
        return del_idx
    def get_instp_struct(self, pack_s):
        if self.pack_lut.has_key(pack_s.get_idx()):
            return self.packages[self.pack_lut[pack_s.get_idx()]]
        else:
            return None
    def get_instp_idx(self, pack_s):
        return self.pack_lut.get(pack_s.get_idx(), 0)
    def get_sorted_instp_idx_list(self):
        name_dict, all_idxs = ({}, [])
        for key, value in self.packages.iteritems():
            name_dict.setdefault(value.get_name(), []).append(key)
        for name in sorted(name_dict.keys()):
            all_idxs.extend(name_dict[name])
        return all_idxs
    def set_last_hw_update(self, last_upd=0):
        self.hw_last_update = max(self.hw_last_update, last_upd)
    def get_last_hw_update(self):
        return self.hw_last_update
    def get_device_type(self):
        return self.type_idx
    def set_xen_device(self, x_idx):
        self.xen_device = x_idx
    def get_xen_device(self):
        return self.xen_device
    def set_xen_guest(self, value):
        self.xen_guest = value
    def get_xen_guest(self):
        return self.xen_guest
    def set_show_in_bootcontrol(self, value):
        self.show_in_bootcontrol = value
    def get_show_in_bootcontrol(self):
        return self.show_in_bootcontrol
    def set_device_type(self, t_idx):
        self.type_idx = t_idx
    def set_comment(self, comment=""):
        self.comment = comment
    def get_comment(self):
        return self.comment
    def get_device_group(self):
        return self.group_idx
    def set_device_group(self, g_idx):
        self.group_idx = g_idx
    def set_bootserver(self, boot_s_idx, server_name="<not set>"):
        self.bootserver = boot_s_idx
        self.bootserver_name = server_name
    def get_bootserver(self):
        return self.bootserver
    def get_bootserver_name(self):
        return self.bootserver_name
    def init_device_flags(self):
        self.flags = []
    def add_device_flag(self, fl):
        if fl not in self.flags:
            self.flags.append(fl)
    def get_device_flags(self):
        return self.flags
    def add_log_entry(self, log_source, user, log_status, log_str):
        self.__log_entries.append(("(0, %s, %s, %s, %s, %s, null)", (self.idx,
                                                                     log_source,
                                                                     user,
                                                                     log_status,
                                                                     log_str)))
    def get_log_entries(self):
        return self.__log_entries
    def add_apc_connection(self, apc_dev, outlet, state, info):
        self.apc_cons.append((apc_dev, outlet, state, info))
    def add_ibc_connection(self, ibc_dev, blade, state, info):
        self.ibc_cons.append((ibc_dev, blade, state, info))
    def remove_apc_connection(self, apc_dev, outlet):
        new_cons = []
        for apc_idx, apc_outlet, state, info in self.apc_cons:
            if apc_idx == apc_dev and apc_outlet == outlet:
                pass
            else:
                new_cons.append((apc_idx, apc_outlet, state, info))
        self.apc_cons = new_cons
    def remove_ibc_connection(self, ibc_dev, blade):
        new_cons = []
        for ibc_idx, ibc_blade, state, info in self.ibc_cons:
            if ibc_idx == ibc_dev and ibc_blade == blade:
                pass
            else:
                new_cons.append((ibc_idx, ibc_blade, state, info))
        self.ibc_cons = new_cons
    def get_connection_info(self, apc_dict, ibc_dict):
        con_list = []
        if self.apc_cons:
            con_list.append("%s (%s)" % (logging_tools.get_plural("APC", len(self.apc_cons), 1),
                                         ", ".join(["%s/%d" % (apc_dict[apc_idx].name, outlet) for apc_idx, outlet, state, info in self.apc_cons])))
        if self.ibc_cons:
            con_list.append("%s (%s)" % (logging_tools.get_plural("IBC", len(self.ibc_cons), 1),
                                         ", ".join(["%s/%d" % (ibc_dict[ibc_idx].name, blade) for ibc_idx, blade, state, info in self.ibc_cons])))
        return "connected to %s" % (", ".join(con_list)) if con_list else "no APC or IBC connections"
    def get_outlet_suffix(self, ai_idx, o_b_num):
        return "%s_%d_%d" % (self.get_suffix(), ai_idx, o_b_num)
    def get_act_state(self):
        return self.__state
    def get_recv_state(self):
        return self.__recv_state
    def get_req_state(self):
        return self.__req_state
    def get_act_net(self):
        return self.act_net
    def _split_state(self, in_state):
        state_parts = in_state.split(":", 3)
        if len(state_parts) == 4:
            up_state = {"o" : 1,
                        "w" : 2,
                        "e" : 0}.get(state_parts[0], -1)
            act_net = state_parts[2] or "???"
            state = state_parts[3]
            if state.lower().startswith("error"):
                # device reachable but something wrong with info string
                up_state = 2
        else:
            up_state, act_net, state = (-1, "???", "error parsing %s" % (in_state))
        return up_state, act_net, state
    def set_act_state(self, state="e:::not set"):
        self.up_state, self.act_net, self.__state = self._split_state(state)
    def set_req_recv_state(self, req_state=None, recv_state=None):
        self.act_net = "???"
        if not req_state:
            req_state = "e:::not set"
        if not recv_state:
            recv_state = "not set"
        # remove net part of recv_state
        if recv_state.endswith(")"):
            recv_state = recv_state.split("(")[0].strip()
        self.__recv_state = recv_state
        self.up_state, self.act_net, self.__req_state = self._split_state(req_state)
    def set_kernel_info(self, nk_str, nk_idx, ak_str, ak_idx, akb_idx, act_kv, kern_par, s1_flavour):
        self.new_kernel_str = nk_str
        self.new_kernel_idx = nk_idx
        self.act_kernel_str = ak_str
        self.act_kernel_idx = ak_idx
        self.act_kernel_build_idx = akb_idx
        self.act_kernel_version = act_kv
        self.act_kernel_par, self.new_kernel_par = (kern_par, kern_par)
        self.stage1_flavour = s1_flavour
    def get_kernel_parameter(self):
        return self.new_kernel_par
    def get_stage1_flavour(self):
        return self.stage1_flavour
    def set_stage1_flavour(self, flav):
        self.stage1_flavour = flav
        self.add_sql_changes({"stage1_flavour" : self.stage1_flavour})
        self.add_device_flag("t")
    def get_act_kernel_str(self, all_kernels):
        if all_kernels.has_key(self.act_kernel_idx):
            act_kern = all_kernels[self.act_kernel_idx]
            build_list = [x for x in act_kern.get("build_list", []) if x["idx"] == self.act_kernel_build_idx]
            if build_list:
                build_info = build_list[0]
                if build_info["version"] == act_kern["version"] and build_info["release"] == act_kern["release"] and self.act_kernel_idx == self.new_kernel_idx:
                    build_info = "same"
                else:
                    build_info = "%s.%s on %s, %s" % (build_info["version"], build_info["release"], build_info["build_machine"], build_info["date"])
            else:
                build_info = "???"
            return "%s [%s]" % (act_kern["name"], build_info)
        else:
            if self.act_kernel_str:
                return "%s [%s]" % (self.act_kernel_str, self.act_kernel_version)
            else:
                return "&lt;no valid kernel set&gt;"
    def get_new_kernel_idx(self, all_kernels):
        if self.new_kernel_idx:
            if all_kernels.has_key(self.new_kernel_idx):
                idx = all_kernels[self.new_kernel_idx]["kernel_idx"]
            else:
                idx = 0
        else:
            idx = ([v["kernel_idx"] for v in all_kernels.values() if v["name"] == self.new_kernel_str] + [0])[0]
        return idx
    def set_new_kernel_idx(self, nk_idx, all_kernels):
        self.new_kernel_idx = nk_idx
        if all_kernels.has_key(self.new_kernel_idx):
            self.add_sql_changes({"new_kernel" : self.new_kernel_idx,
                                  "newkernel"  : all_kernels[self.new_kernel_idx]["name"]})
        else:
            self.add_sql_changes({"new_kernel" : self.new_kernel_idx,
                                  "newkernel"  : "unknown"})
        self.add_device_flag("t")
    def set_partition_info(self, p_idx, ap_idx):
        self.new_partition_idx = p_idx
        self.act_partition_idx = ap_idx
    def get_new_partition_idx(self, p_dict):
        return p_dict.get(self.new_partition_idx, {"partition_table_idx" : 0})["partition_table_idx"]
    def get_act_partition_str(self, p_dict):
        if p_dict.has_key(self.act_partition_idx):
            if self.new_partition_idx == self.act_partition_idx:
                return "same"
            else:
                return p_dict[self.act_partition_idx]["name"]
        else:
            return "&lt;no valid partition set&gt;"
    def set_image_info(self, n_im, n_idx, a_im, a_idx, im_v):
        self.new_image_str = n_im
        self.new_image_idx = n_idx
        self.act_image_str = a_im
        self.act_image_idx = a_idx
        self.act_image_version = im_v
    def get_new_image_idx(self, im_dict):
        idx = 0
        for i in im_dict.values():
            if i["name"] == self.new_image_str:
                idx = i["image_idx"]
        return idx
    def get_act_image_str(self, i_dict):
        if self.act_image_str:
            ret_str = "%s [%s]" % (self.act_image_str, self.act_image_version)
            if self.new_image_str:
                for i in i_dict.values():
                    if i["name"] == self.new_image_str:
                        if "%d.%d" % (i["version"], i["release"]) == self.act_image_version:
                            ret_str = "same"
        else:
            ret_str = "&lt;no valid image set&gt;"
        return ret_str
    def set_new_image(self, n_idx, n_i):
        self.new_image_idx = n_idx
        self.new_image_str = n_i
        self.add_sql_changes({"new_image" : self.new_image_idx,
                              "newimage"  : self.new_image_str})
    def check_image_idx(self, image_dict):
        if image_dict.get(self.new_image_idx, {"name" : ""})["name"] != self.new_image_str:
            self.new_image_idx = ([k for k, v in image_dict.iteritems() if v["name"] == self.new_image_str]+[0])[0]
            self.add_sql_changes({"new_image" : self.new_image_idx})
        if image_dict.get(self.act_image_idx, {"name" : ""})["name"] != self.act_image_str:
            self.act_image_idx = ([k for k, v in image_dict.iteritems() if v["name"] == self.new_image_str]+[0])[0]
            self.add_sql_changes({"act_image" : self.act_image_idx})
    def set_bootnetdevice(self, bnd = 0):
        self.bootnetdevice = bnd
    def get_bootnetdevice(self):
        return self.bootnetdevice
    def set_mac_info(self, devname, macadr, dhcp_mac, dhcp_driver, dhcp_driver_options, netdevice_idx):
        self.netdevname = devname
        self.macadr = macadr
        self.dhcp_mac = dhcp_mac
        self.dhcp_driver = dhcp_driver
        self.dhcp_driver_options = dhcp_driver_options
        self.netdevice_idx = netdevice_idx
        self.modify_sql_changes({"n" : {"table" : "netdevice",
                                        "idx"   : self.netdevice_idx}})
    def get_netdevice_name(self):
        return self.netdevname
    def set_dhcp_info(self, dhcp_write, dhcp_written, dhcp_error, dhcp_mac=None):
        self.dhcp_write = dhcp_write
        self.dhcp_written = dhcp_written
        self.dhcp_error = dhcp_error
        if dhcp_mac:
            self.dhcp_mac = dhcp_mac
    def get_dhcp_error(self):
        return self.dhcp_error
    def get_dhcp_write_flag(self):
        return self.dhcp_write
    def get_mac_address(self):
        return self.macadr
    def get_mac_driver(self):
        return self.dhcp_driver
    def dhcp_info_is_ok(self):
        return self.dhcp_written and self.dhcp_error == "ok done" and not self.dhcp_mac
    def get_dhcp_info(self):
        return ", ".join([self.dhcp_written and "dhcp_address is written" or "dhcp_address is not written",
                          self.dhcp_error or "unknown last result"])
    def get_greedy_info(self):
        return "greedy mode is %s" % (self.dhcp_mac and "enabled" or "disabled")
    def get_greedy_mode(self):
        return self.dhcp_mac
    def set_greedy_mode(self, gm):
        self.dhcp_mac = gm
        self.add_sql_changes({"dhcp_mac" : gm})
    def set_mac_address(self, mac):
        self.macadr = mac
    def set_new_mac_address(self, mac):
        self.set_mac_address(mac)
        self.add_sql_changes({"macadr" : self.macadr}, "n")
    def set_new_mac_driver(self, drv):
        self.dhcp_driver = drv
        self.add_sql_changes({"driver" : self.dhcp_driver}, "n")
        self.add_device_flag("t")
    def set_dhcp_write_flag(self, fl):
        self.dhcp_write = fl
        self.add_sql_changes({"dhcp_write" : self.dhcp_write})
    def add_network_stuff(self, in_dict):
        n_idx = in_dict["netdevice_idx"]
        if n_idx:
            if not self.net_tree.has_key(n_idx):
                new_ndev = cdef_network.netdevice(in_dict["devname"], in_dict["netdevice_idx"])
                if n_idx < 0:
                    new_ndev.set_suffix(self.get_new_netdevice_suffix())
                new_ndev.set_parameters(in_dict)
                self.net_tree[new_ndev.get_idx()] = new_ndev
                self.net_lut[in_dict["devname"]] = new_ndev.get_idx()
            self.net_tree[n_idx].add_network_stuff(in_dict)
    def set_values_as_default(self):
        for act_val in self.net_tree.values():
            act_val.set_values_as_default()
    def add_netdevice(self, new_ndev):
        self.net_tree[new_ndev.get_idx()] = new_ndev
        self.net_lut[new_ndev.get_name()] = new_ndev.get_idx()
    def enqueue_new_netdevice(self, n_dev, has_old = 1):
        # change name of netdevice and correct dict
        new_name = n_dev["devname"]
        new_idx = n_dev.get_idx()
        if has_old:
            old_name = n_dev.get_name()
            old_idx = -1
            del self.net_lut[old_name]
            del self.net_tree[old_idx]
        n_dev.set_name(new_name)
        #print "alter_netdevice_name from %s to %s<br>" % (old_name, new_name)
        self.net_lut[new_name] = new_idx
        self.net_tree[new_idx] = n_dev
    def delete_network_device(self, n_idx):
        del self.net_lut[self.net_tree[n_idx].get_name()]
        del self.net_tree[n_idx]
    def get_number_of_netdevices(self):
        return len([x for x in self.net_tree.keys() if x > 0])
    def get_number_of_ips(self):
        return reduce(lambda x, y: x + y, [nd.get_number_of_ips() for nd in self.net_tree.values()])
    def get_sorted_netdevice_list(self):
        new_ndev = [x.get_name() for x in self.net_tree.itervalues() if x.get_idx()  ==  -1]
        if new_ndev:
            new_ndev = new_ndev[0]
        else:
            new_ndev = None
        ndl = sorted([x for x in self.net_lut.keys() if x != new_ndev])
        #print "***",new_ndev, ", ", [x.get_idx() for x in self.net_tree.itervalues()], ", ",ndl, "<br>"
        if new_ndev:
            ndl.append(new_ndev)
        return [self.net_tree[self.net_lut[x]] for x in ndl]
    def get_netdevice_struct(self, nd_idx):
        return self.net_tree[nd_idx]
    def get_netdevice_names(self, ignore_idx = None):
        if ignore_idx:
            return [self.net_tree[x].get_name() for x in self.net_tree.keys() if x != ignore_idx]
        else:
            return [x.get_name() for x in self.net_tree.values()]
    def get_new_netdevice_suffix(self):
        return "%snn" % (self.get_suffix())
    def get_new_netip_suffix(self):
        return "%sni" % (self.get_suffix())
    def netdevice_is_bootnetdevice(self, nd_idx):
        return self.bootnetdevice == nd_idx
    def add_peer_information(self, peer_info):
        if peer_info["s_netdevice"] in self.net_tree.keys():
            self.net_tree[peer_info["s_netdevice"]].add_peer_information(peer_info["peer_information_idx"], peer_info["d_netdevice"], peer_info["penalty"])
        else:
            self.net_tree[peer_info["d_netdevice"]].add_peer_information(peer_info["peer_information_idx"], peer_info["s_netdevice"], peer_info["penalty"])
    def get_peers(self, only_foreign = 0):
        ps = []
        for ndev in self.net_tree.values():
            ps.extend(ndev.get_peers())
        if only_foreign:
            ps = [x for x in ps if x not in self.net_tree.keys()]
        return ps
    def get_number_of_peers(self, only_foreign = 0):
        return len(self.get_peers(only_foreign))
    def remove_defective_peers(self, missing):
        for ndev in self.net_tree.values():
            ndev.remove_defective_peers(missing)
    def __repr__(self):
        return "%s (idx %d)" % (self.name, self.idx)

if IMMEDIATE_APC_OPERATIONS_ALLOWED:
    apc_outlet_states = {0 : "---",
                         1 : "Immediate on",
                         2 : "Immediate off",
                         3 : "Immediate reboot",
                         5 : "Delayed on",
                         6 : "Delayed off",
                         7 : "Delayed reboot"}
    apc_master_states = {0 : "---",
                         1 : "Immediate on",
                         2 : "Immediate off",
                         3 : "Immediate reboot",
                         4 : "Sequenced on",
                         5 : "Sequenced off",
                         6 : "Sequenced reboot"}
else:
    apc_outlet_states = {0 : "---",
                         2 : "Immediate off",
                         5 : "Delayed on",
                         6 : "Delayed off",
                         7 : "Delayed reboot"}
    apc_master_states = {0 : "---",
                         2 : "Immediate off",
                         4 : "Sequenced on",
                         5 : "Sequenced off",
                         6 : "Sequenced reboot"}

ibc_blade_states = {0 : "---",
                    1 : "On",
                    2 : "Off",
                    3 : "Reboot"}

class apc(device):
    def __init__(self, name, idx, group_idx, type_idx):
        device.__init__(self, name, idx, group_idx, type_idx)
        self.outlets = {}
        self.set_apc_type_and_version()
        self.set_num_outlets()
        self.apc_com_sep = ","
        self.__command = ""
    def set_apc_delays(self, power_on_delay, reboot_delay):
        self.__power_on_delay = power_on_delay
        self.__reboot_delay = reboot_delay
    def get_apc_delays(self):
        return (self.__power_on_delay, self.__reboot_delay)
    def set_apc_device_idx(self, adi):
        self.__apc_device_idx = adi
    def get_apc_device_idx(self):
        return self.__apc_device_idx
    def set_num_outlets(self, num=0):
        self.__num_outlets = num
    def get_num_outlets(self):
        return self.__num_outlets
    def set_apc_type_and_version(self, t_str="unknown / not set", v_info=""):
        self.__apc_type = t_str
        if v_info:
            self.__apc_version = v_info[1:].split(v_info[0])
        else:
            self.__apc_version = []
    def get_apc_version(self):
        if len(self.__apc_version) > 4:
            return "%s (%s, %s)" % (self.__apc_version[-2],
                                    self.__apc_version[-5],
                                    self.__apc_version[-4])
        else:
            return "unknown"
    def get_apc_type(self):
        return self.__apc_type
    def valid_apc(self):
        return self.outlets and True or False
    def get_outlet_nums(self):
        return sorted(self.outlets.keys())
    def get_outlet(self, num):
        return self.outlets[num]
    def set_device(self, out_num, dev_idx, name, slave_info, device_group_name = "not set"):
        self.outlets[out_num]["device"] = dev_idx
        self.outlets[out_num]["name"] = name
        self.outlets[out_num]["info"] = slave_info
        self.outlets[out_num]["device_group_name"] = device_group_name
    def remove_device(self, out_num):
        self.outlets[out_num]["device"] = 0
        self.outlets[out_num]["name"] = ""
        self.outlets[out_num]["info"] = ""
        self.outlets[out_num]["device_group_name"] = ""
    def get_device_idxs(self):
        return [x["device"] for x in self.outlets.values() if x["device"]]
    def get_num_devices_set(self):
        return len([x for x  in self.outlets.values() if x["device"]])
    def get_free_list(self):
        return sorted([k for k, v in self.outlets.iteritems() if not v["device"]])
    def add_outlet(self, out_num, in_dict):
        self.outlets[out_num] = {"info"    : in_dict.get("slave_info"       , "<not set>"),
                                 "state"   : in_dict.get("state"            , "<not set>"),
                                 "pond"    : in_dict.get("power_on_delay"   , 0),
                                 "t_pond"  : in_dict.get("t_power_on_delay" , 0),
                                 "poffd"   : in_dict.get("power_off_delay"  , 0),
                                 "t_poffd" : in_dict.get("t_power_off_delay", 0),
                                 "rebd"    : in_dict.get("reboot_delay"     , 0),
                                 "t_rebd"  : in_dict.get("t_reboot_delay"   , 0),
                                 "device"  : 0,
                                 "name"    : "",
                                 "command" : [],
                                 "db_idx"  : in_dict.get("msoutlet_idx", 0)}
    def get_outlet_var(self, out_num, key):
        return self.outlets[out_num][key]
    def set_outlet_var(self, out_num, key, value):
        self.outlets[out_num][key] = value
    def get_apc_com_list(self, req, html_tools):
        apc_cl = html_tools.selection_list(req, "apcc")
        for idx, name in apc_outlet_states.iteritems():
            apc_cl[idx] = name
        apc_cl.mode_is_normal()
        return apc_cl
    def add_outlet_command(self, outlet, command):
        self.outlets[outlet]["command"].append(("c", (command)))
    def add_apc_command(self, command):
        self.__command = command
        # hack, FIXME
        for o_idx in self.outlets.keys():
            self.add_outlet_command(o_idx, self.__command)
    def get_command_str(self):
        return self.apc_com_sep.join([z for z in [self.apc_com_sep.join(["%s%d=%d" % (a, y, b) for a, b in x["command"]]) for y, x in self.outlets.iteritems()] if z])
    def get_log_str(self, outlet, command):
        return "apc command %s (apc %s, outlet %d)" % (apc_outlet_states.get(int(command), "unknown"), self.name, outlet)
    
class ibc(device):
    def __init__(self, name, idx, group_idx, type_idx):
        device.__init__(self, name, idx, group_idx, type_idx)
        self.blades = {}
        self.set_ibc_type()
        self.ibc_com_sep = ","
    def set_ibc_device_idx(self, adi):
        self.__apc_device_idx = adi
    def get_ibc_device_idx(self):
        return self.__apc_device_idx
    def set_ibc_type(self, in_type = "unknown / not set"):
        if in_type:
            self.__ibc_type = in_type
    def get_ibc_type(self):
        return self.__ibc_type
    def valid_ibc(self):
        return self.blades and True or False
    def get_blade_nums(self):
        return sorted(self.blades.keys())
    def set_device(self, blade_num, dev_idx, name, slave_info, device_group_name = "not set"):
        self.blades[blade_num]["device"] = dev_idx
        self.blades[blade_num]["name"] = name
        self.blades[blade_num]["info"] = slave_info
        self.blades[blade_num]["device_group_name"] = device_group_name
    def remove_device(self, blade_num):
        self.blades[blade_num]["device"] = 0
        self.blades[blade_num]["name"] = ""
        self.blades[blade_num]["info"] = ""
        self.blades[blade_num]["device_group_name"] = ""
    def get_device_idxs(self):
        return [x["device"] for x in self.blades.values() if x["device"]]
    def get_num_devices_set(self):
        return len([x for x  in self.blades.values() if x["device"]])
    def get_free_list(self):
        return sorted([k for k, v in self.blades.iteritems() if not v["device"]])
    def add_blade(self, blade_num, in_dict):
        self.blades[blade_num] = {"info"         : in_dict.get("slave_info", "<not set>"),
                                  "state"        : in_dict.get("state"     , "<not set>"),
                                  "blade_exists" : in_dict.get("blade_exists", 0),
                                  "device"       : 0,
                                  "name"         : "",
                                  "command"      : [],
                                  "db_idx"       : in_dict.get("ibc_connection_idx", 0)}
    def get_outlet_var(self, blade_num, key):
        return self.blades[blade_num][key]
    def set_outlet_var(self, blade_num, key, value):
        self.blades[blade_num][key] = value
    def get_ibc_com_list(self, req, html_tools):
        ibc_cl = html_tools.selection_list(req, "ibcc")
        for idx, name in ibc_blade_states.iteritems():
            ibc_cl[idx] = name
        ibc_cl.mode_is_normal()
        return ibc_cl
    def add_blade_command(self, blade, command):
        self.blades[blade]["command"].append(("c", (command)))
    def get_command_str(self):
        return self.ibc_com_sep.join([z for z in
                                      [self.ibc_com_sep.join(["%s%d=%d" % (a, y, b) for a, b in x["command"]]) for y, x in self.blades.iteritems()]
                                      if z])
    def get_log_str(self, blade, command):
        return "ibc command %s (blade %d)" % (ibc_blade_states.get(int(command), "unknown"), blade)
