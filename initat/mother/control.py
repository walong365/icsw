# -*- coding: utf-8 -*-
#
# Copyright (C) 2012-2014 Andreas Lang-Nevyjel, init.at
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
""" node control related parts of mother """

from django.db import connection
from django.db.models import Q
from initat.cluster.backbone.models import kernel, device, image, macbootlog, mac_ignore, \
     cluster_timezone, cached_log_status, cached_log_source, log_source, devicelog, user
from initat.mother.command_tools import simple_command
from initat.mother.config import global_config
import config_tools
import configfile
import copy
import datetime
import icmp_class
import ipvx_tools
import logging_tools
import os
import pprint
import process_tools
import re
import select
import server_command
import shutil
import stat
import threading_tools
import time
import uuid

class machine(object):
    # store important device-related settings
    def __init__(self, dev):
        self.device = dev
        self.name = dev.name
        self.full_name = dev.full_name
        self.pk = dev.pk
        self.__log_source_idx = global_config["LOG_SOURCE_IDX"]
        self.__log_template = logging_tools.get_logger(
            "{}.{}".format(
                global_config["LOG_NAME"],
                self.name.replace(".", r"\.")),
            global_config["LOG_DESTINATION"],
            zmq=True,
            context=machine.process.zmq_context,
            init_logger=True)
        self.log("added client, type is {}".format(self.device.device_type.identifier))
        self.additional_lut_keys = set()
        self.ip_dict = {}
        self.init()
    def init(self):
        pass
    def close(self):
        del_keys = copy.deepcopy(self.additional_lut_keys)
        for add_key in del_keys:
            machine.del_lut_key(self, add_key)
        self.__log_template.close()
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK, device_log=False):
        self.__log_template.log(log_level, what)
    @staticmethod
    def setup(c_process):
        machine.process = c_process
        machine.eb_dir = global_config["ETHERBOOT_DIR"]
        machine.iso_dir = global_config["ISO_DIR"]
        machine.g_log("init (etherboot_dir={}, isos in{})".format(machine.eb_dir, machine.iso_dir))
        machine.__lut = {}
        # pks
        machine.__unique_keys = set()
        # names
        machine.__unique_names = set()
        machine.ping_id = 0
    @staticmethod
    def get_all_names(**kwargs):
        type_filter = kwargs.get("node_type", [])
        all_names = sorted(machine.__unique_names)
        if type_filter:
            all_names = [name for name in all_names if machine.get_device(name).device.device_type.identifier in type_filter]
        return all_names
    @staticmethod
    def shutdown():
        while machine.__lut:
            machine.delete_device(machine.__lut.keys()[0])
    @staticmethod
    def g_log(what, log_level=logging_tools.LOG_LEVEL_OK):
        machine.process.log("[mach] {}".format(what), log_level)
    @staticmethod
    def get_query(names=[], ips=[]):
        query = device.objects.filter(Q(bootserver=machine.process.sc.effective_device)).select_related("device_type").prefetch_related(
            "netdevice_set",
            "netdevice_set__net_ip_set",
            "netdevice_set__net_ip_set__network",
            "netdevice_set__net_ip_set__network__network_type")
        if names:
            query = query.filter(Q(name__in=names))
        if ips:
            query = query.filter(Q(netdevice__net_ip__ip__in=ips))
        return query
    def refresh_device(self):
        found_devs = machine.get_query(names=[self.device.name])
        if len(found_devs) == 1:
            self.device = found_devs[0]
        elif not len(found_devs):
            self.device = None
            self.log("device has vanished from database ...", logging_tools.LOG_LEVEL_ERROR)
    @staticmethod
    def sync(names=[], ips=[]):
        query = machine.get_query(names=names, ips=ips)
        machine.g_log(
            "found {}: {}".format(
                logging_tools.get_plural("device", len(query)),
                logging_tools.compress_list([cur_dev.name for cur_dev in query])))
        for cur_dev in query:
            machine.set_device(cur_dev)
    @staticmethod
    def add_lut_key(obj, key):
        if key in machine.__lut:
            machine.g_log("key '{}' already set in machine.__lut ({} set, obj is {})".format(
                key,
                machine.__lut[key].name,
                obj.name,
                ), logging_tools.LOG_LEVEL_ERROR)
        else:
            machine.__lut[key] = obj
            obj.additional_lut_keys.add(key)
    @staticmethod
    def del_lut_key(obj, key):
        # if key == "172.16.1.56":
        #    print "+", key
        del machine.__lut[key]
        obj.additional_lut_keys.remove(key)
    @staticmethod
    def set_device(new_dev):
        if new_dev.device_type.identifier == "H":
            new_mach = host(new_dev)
        elif new_dev.device_type.identifier == "CD":
            new_mach = controlling_device(new_dev)
        else:
            new_mach = machine(new_dev)
        machine.__unique_keys.add(new_dev.pk)
        machine.__unique_names.add(new_dev.full_name)
        machine.__lut[new_dev.full_name] = new_mach
        # short name, will not always work
        machine.__lut[new_dev.name] = new_mach
        machine.__lut[new_dev.pk] = new_mach
    @staticmethod
    def delete_device(dev_spec):
        mach = machine.get_device(dev_spec)
        if mach:
            mach.close()
            del machine.__lut[mach.full_name]
            del machine.__lut[mach.pk]
            try:
                del machine.__lut[mach.name]
            except:
                pass
            machine.__unique_keys.remove(mach.pk)
            machine.__unique_names.remove(mach.full_name)
    @staticmethod
    def get_device(dev_spec):
        if dev_spec in machine.__lut:
            return machine.__lut[dev_spec]
        else:
            machine.g_log("no device with spec '{}' found (not mother / bootserver ?)".format(
                str(dev_spec),
                ), logging_tools.LOG_LEVEL_ERROR)
            return None
    @staticmethod
    def iterate(com_name, *args, **kwargs):
        iter_keys = machine.__unique_keys & set(kwargs.pop("device_keys", machine.__unique_keys))
        for u_key in iter_keys:
            cur_dev = machine.get_device(u_key)
            if hasattr(cur_dev, com_name):
                cur_dev.log("call '{}'".format(com_name))
                getattr(cur_dev, com_name)(*args, **kwargs)
            else:
                cur_dev.log("call '{}' not defined".format(com_name), logging_tools.LOG_LEVEL_WARN)
    @staticmethod
    def iterate_xml(srv_com, com_name, *args, **kwargs):
        for cur_dev in srv_com.xpath(".//ns:device[@pk]", smart_strings=False):
            pk = int(cur_dev.attrib["pk"])
            cur_mach = machine.get_device(pk)
            if cur_mach is None:
                pass
            else:
                getattr(cur_mach, com_name)(cur_dev, *args, **kwargs)
    @staticmethod
    def ping(srv_com):
        # send ping(s) to all valid IPs of then selected devices
        keys = set(map(lambda x: int(x), srv_com.xpath(".//ns:device/@pk", smart_strings=False))) & set(machine.__unique_keys)
        cur_id = machine.ping_id
        _bldr = srv_com.builder()
        ping_list = _bldr.ping_list()
        for u_key in keys:
            cur_dev = machine.get_device(u_key)
            dev_node = srv_com.xpath(".//ns:device[@pk='{:d}']".format(cur_dev.pk), smart_strings=False)[0]
            tried = 0
            for ip in cur_dev.ip_dict.iterkeys():
                # omit slave and local networks, allow local networks for pinging the server ?
                if cur_dev.ip_dict[ip].network.network_type.identifier not in ["s", "l"]:
                    tried += 1
                    cur_id_str = "mp_{:d}".format(cur_id)
                    cur_id += 1
                    # init ping
                    machine.process.send_pool_message("ping", cur_id_str, ip, 4, 3.0, target="direct")
                    ping_list.append(_bldr.ping(cur_id_str, pk="{:d}".format(cur_dev.pk)))
            dev_node.attrib.update(
                {
                    "tried"  : "{:d}".format(tried),
                    "ok"     : "0",
                    "failed" : "0",
                }
            )
        srv_com["ping_list"] = ping_list
        if not len(ping_list):
            # remove ping_list if empty
            srv_com["ping_list"].getparent().remove(srv_com["ping_list"])
        # all master devices, format : master_device_id, master_net_ip
        # we ignore routing
        master_dev_list = set(device.objects.filter(Q(parent_device__child__in=keys)).select_related("netdevice_set__net_ip_set").values_list(
            "pk",
            "netdevice__net_ip__ip",
            "netdevice__net_ip__network__network_type__identifier",
            ))
        # create dict for master / slave relations
        _master_dict = {key : value for key, value, nwt in master_dev_list if value and nwt not in ["l"]}
        cd_ping_list = _bldr.cd_ping_list()
        if _master_dict:
            master_id = 0
            for master_pk, master_ip in _master_dict.iteritems():
                cur_id_str = "mps_{:d}".format(master_id)
                master_id += 1
                machine.process.send_pool_message("ping", cur_id_str, master_ip, 2, 3.0, target="direct")
                cd_ping_list.append(_bldr.cd_ping(cur_id_str, pk="{:d}".format(master_pk), pending="1"))
            srv_com["cd_ping_list"] = cd_ping_list
        machine.ping_id = cur_id
        # return True if at least one ping has been sent, otherwise false
        return True if len(ping_list) + len(cd_ping_list) else False
    @staticmethod
    def interpret_result(srv_com, id_str, res_dict):
        # interpret ping result
        node = srv_com.xpath(".//ns:ping[text() = '{}']".format(id_str), smart_strings=False)[0]
        pk = int(node.attrib["pk"])
        ping_list = node.getparent()
        ping_list.remove(node)
        machine.get_device(pk).interpret_local_result(srv_com, res_dict)
        if not len(ping_list):
            pl_parent = ping_list.getparent()
            pl_parent.remove(ping_list)
            pl_parent.getparent().remove(pl_parent)
    @staticmethod
    def interpret_cdping_result(srv_com, res_dict):
        _cdp_node = srv_com.xpath(".//ns:cd_ping_list/ns:cd_ping[text() = '{}']".format(res_dict["id"]))
        if len(_cdp_node):
            _cdp_node = _cdp_node[0]
            _cdp_node.attrib.update({
                "pending" : "0",
                "reachable" : "1" if res_dict["recv_ok"] else "0",
            })
        else:
            machine.g_log("unknown id_str '{}' for cdp_node".format(res_dict["id"]), logging_tools.LOG_LEVEL_ERROR)
    def interpret_local_result(self, srv_com, res_dict):
        # device-specific interpretation
        dev_node = srv_com.xpath(".//ns:device[@pk='{:d}']".format(self.pk), smart_strings=False)[0]
        ip_list = self.ip_dict.keys()
        if res_dict["host"] in ip_list:
            if res_dict["recv_ok"]:
                cur_ok = int(dev_node.attrib["ok"]) + 1
                dev_node.attrib["ok"] = "{:d}".format(cur_ok)
                dev_node.attrib["ip"] = res_dict["host"]
                if cur_ok == 1:
                    self.log("send hoststatus query to {}".format(res_dict["host"]))
                    machine.process.send_pool_message(
                        "contact_hoststatus",
                        self.device.get_boot_uuid() if self.ip_dict[dev_node.attrib["ip"]].network.network_type.identifier == "b" else self.device.uuid,
                        dev_node.attrib.get("soft_command", "status"),
                        dev_node.attrib["ip"])
                # remove other ping requests for this node
                for other_ping in srv_com.xpath(".//ns:ping[@pk='{:d}']".format(self.pk), smart_strings=False):
                    other_ping.getparent().remove(other_ping)
            else:
                dev_node.attrib["failed"] = "{:d}".format(int(dev_node.attrib["failed"]) + 1)
        else:
            self.log("got unknown ip '{}'".format(res_dict["host"]), logging_tools.LOG_LEVEL_ERROR)
    def add_ping_info(self, cur_dev):
        # print "add_ping_info", etree.tostring(cur_dev)
        if int(cur_dev.attrib["ok"]):
            cur_dev.attrib["network"] = self.ip_dict[cur_dev.attrib["ip"]].network.identifier
            # print self.ip_dict[cur_dev.attrib["ip"]]
        else:
            cur_dev.attrib["network"] = "unknown"
            cur_dev.attrib["network_state"] = "error"
        # for key, value in self.ip_dict.iteritems():
        #    print key, value.network
    def set_ip_dict(self, in_dict):
        old_dict = self.ip_dict
        self.ip_dict = in_dict
        old_keys = set(old_dict.keys())
        new_keys = set(self.ip_dict.keys())
        for del_key in old_keys - new_keys:
            self.log("removing ip {} from lut".format(del_key))
            machine.del_lut_key(self, del_key)
        for new_key in new_keys - old_keys:
            self.log("adding ip {} to lut".format(new_key))
            machine.add_lut_key(self, new_key)

class host(machine):
    def init(self):
        # clear ip_dict
        self.ip_dict = {}
        # clear maintenance ip/mac
        self.set_maint_ip()
        # hardware information counter
        self.hwi_delay_counter = 0
        # check network settings
        self.check_network_settings()
        # save changes done during init
        # do not overwrite states, preserve
        # self.set_recv_state()
        # self.set_req_state()
        # should now be handled in device_pre_save
        if not self.device.uuid:
            self.device.uuid = str(uuid.uuid4())
            self.log("setting uuid to {}".format(self.device.uuid))
        machine.add_lut_key(self, self.device.uuid)
        machine.add_lut_key(self, self.device.get_boot_uuid())
        self.device.save()
    # machine related
    def set_maint_ip(self, ip=None):
        if ip:
            if self.maint_ip and (self.maint_ip.ip != ip.ip or self.maint_ip.netdevice.macaddr != ip.netdevice.macaddr):
                self.log("Changing maintenance IP and MAC from {} ({}) [{}] to {} ({}) [{}] and setting node-flag".format(
                    self.maint_ip.ip,
                    self.maint_ip.get_hex_ip(),
                    self.maint_ip.netdevice.macaddr,
                    ip.ip,
                    ip.get_hex_ip(),
                    ip.netdevice.macaddr))
            else:
                self.log("Setting maintenance IP and MAC to {} ({}) [{}] and setting node-flag".format(
                    ip.ip,
                    ip.get_hex_ip(),
                    ip.netdevice.macaddr))
            self.maint_ip = ip
            self.is_node = True
        else:
            self.log("Clearing maintenance IP and MAC (and node-flag)")
            self.maint_ip = None
            self.dhcp_mac_written = None
            self.dhcp_ip_written = None
            self.is_node = False
    def get_bnd(self):
        return self.__bnd
    def set_bnd(self, val):
        if val is None:
            self.log("clearing bootnetdevice")
            self.__bnd = val
        else:
            self.log("changing bootnetdevice_name from '{}' to '{}'".format(self.__bnd.devname if self.__bnd else "unset", val))
            self.__bnd = val
    bootnetdevice = property(get_bnd, set_bnd)
    def get_sip_d(self):
        return self.__srv_ip_dict
    def set_sip_d(self, val):
        self.__srv_ip_dict = val
        if val is not None:
            self.log("Found {}:".format(logging_tools.get_plural("valid device->server ip-mapping", len(val.keys()))))
            for my_ip, s_ip in val.iteritems():
                self.log("  {:<15s} -> {:<15s} [{}]".format(my_ip, s_ip["ip"], s_ip["identifier"]))
    server_ip_dict = property(get_sip_d, set_sip_d)
    def check_network_settings(self):
        # bootnet device name
        self.bootnetdevice = None
        nd_list, nd_lut = (set(), {})
        for net_dev in self.device.netdevice_set.all():
            nd_list.add(net_dev.pk)
            nd_lut[net_dev.pk] = net_dev
            if self.device.bootnetdevice_id and net_dev.pk == self.device.bootnetdevice.pk:
                # set bootnetdevice_name
                self.bootnetdevice = net_dev
        # dict: my net_ip -> dict [identifier, ip] server_net_ip
        server_ip_dict = {}
        # dict: ip -> identifier
        ip_dict = {}
        if nd_list:
            machine.process.update_router_object()
            all_paths = sorted(
                machine.process.router_obj.get_ndl_ndl_pathes(
                    machine.process.sc.netdevice_idx_list,
                    nd_list,
                    only_endpoints=True,
                    add_penalty=True,
                )
            )
            # get hopcount
            # latest_gen = route_generation.objects.filter(Q(valid=True)).order_by("-pk")[0]
            # my_hc = hopcount.objects.filter(
                # Q(route_generation=latest_gen) &
                # Q(s_netdevice__in=machine.process.sc.netdevice_idx_list) &
                # Q(d_netdevice__in=nd_list)).order_by("value")
            for _ in all_paths:
                srv_dev, mach_dev = (machine.process.sc.nd_lut[_[1]], nd_lut[_[2]])
                for cur_ip in mach_dev.net_ip_set.all():
                    cur_id = cur_ip.network.network_type.identifier
                    srv_ips = list(set([srv_ip.ip for srv_ip in machine.process.sc.identifier_ip_lut.get(cur_id, [])]) & set([x2.ip for x2 in machine.process.sc.netdevice_ip_lut[srv_dev.pk]]))
                    if srv_ips and not cur_ip.ip in server_ip_dict:
                        server_ip_dict[cur_ip.ip] = {"identifier" : cur_id,
                                                     "ip"         : srv_ips[0] if srv_ips else None}
                    if cur_id == "b" and srv_ips:
                        self.set_maint_ip(cur_ip)
                    if cur_ip.ip not in ip_dict:
                        # definitely wrong, oh my...
                        # ip_dict[cur_ip.ip] = ip_dict
                        # not sure ...
                        ip_dict[cur_ip.ip] = cur_ip
            self.log(
                "found {}: {}".format(
                    logging_tools.get_plural("IP-address", len(ip_dict)),
                    ", ".join(sorted(ip_dict.keys()))))
            link_array = []
            if self.etherboot_dir:
                link_array.extend([("d", self.etherboot_dir),
                                   # ("d", self.pxelinux_dir),
                                   ("l", (os.path.join(global_config["ETHERBOOT_DIR"], self.name), self.maint_ip.ip)),
                                   # create a link in config dir, dangerous because cluster-config-server is running with restricted rights
                                   ("l", (os.path.join(global_config["CONFIG_DIR"], self.maint_ip.ip), self.name)),
                                ])
                self.device.etherboot_valid = True
            else:
                self.log("Error: etherboot-directory (maint_ip) not defined")
                self.device.etherboot_valid = False
            if self.maint_ip:
                self.show_boot_netdriver()
            self.process_link_array(link_array)
            self.log("Setting reachable flag")
            self.device.reachable = True
        else:
            self.log("Cannot add device {} (empty ip_list -> cannot reach host)".format(self.name),
                     logging_tools.LOG_LEVEL_WARN)
            self.device.reachable = False
        self.set_ip_dict(ip_dict)
        self.server_ip_dict = server_ip_dict
    def process_link_array(self, l_array):
        for pt, ps in l_array:
            if pt == "d":
                if not os.path.isdir(ps):
                    try:
                        self.log("pla(): Creating directory {}".format(ps))
                        os.mkdir(ps)
                    except:
                        self.log("  error creating {}: {}".format(ps, process_tools.get_except_info()))
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
                                self.log("  error unlinking {}: {}".format(ps, process_tools.get_except_info()))
                            else:
                                self.log(" removed wrong link ({} pointed to {} instead of {})".format(ps, old_dest, dest))
                                create_link = True
                    else:
                        pass
                if create_link:
                    if os.path.exists(ps):
                        try:
                            self.log("pla(): Unlink {}".format(ps))
                            os.unlink(ps)
                        except:
                            self.log("  error unlinking {}: {}".format(ps, process_tools.get_except_info()))
                        try:
                            self.log("pla(): rmtree {}".format(ps))
                            shutil.rmtree(ps, 1)
                        except:
                            self.log("  error in rmtree {}: {}".format(ps, process_tools.get_except_info()))
                    try:
                        self.log("pla(): symlink from {} to {}".format(ps, dest))
                        os.symlink(dest, ps)
                    except:
                        self.log("  error creating link from {} to {}: {}".format(ps, dest, process_tools.get_except_info()))
    def show_boot_netdriver(self): # , driver="eepro100", ethtool_options=0, options=""):
        self.log("current boot_netdriver/ethtool_options/netdriver_options is '{}' / {:d} ({}) / '{}'".format(
            self.maint_ip.netdevice.driver,
            self.maint_ip.netdevice.ethtool_options,
            self.maint_ip.netdevice.ethtool_string(),
            self.maint_ip.netdevice.driver_options))
    @property
    def etherboot_dir(self):
        if self.maint_ip:
            return os.path.join(self.eb_dir, self.maint_ip.ip)
        else:
            return None
    @property
    def config_dir(self):
        if self.maint_ip:
            return os.path.join(global_config["CONFIG_DIR"], self.maint_ip.ip)
        else:
            return None
    @property
    def menu_file_name(self):
        return os.path.join(self.etherboot_dir, "menu")
    @property
    def ip_file_name(self):
        return os.path.join(self.eb_dir, "pxelinux.cfg", self.maint_ip.get_hex_ip())
    @property
    def ip_mac_file_base_name(self):
        return "01-{}".format(self.maint_ip.netdevice.macaddr.lower().replace(":", "-"))
    @property
    def ip_mac_file_name(self):
        return os.path.join(self.eb_dir, "pxelinux.cfg", self.ip_mac_file_base_name)
    def set_recv_state(self, recv_state="error not set"):
        self.device.recvstate = recv_state
        self.device.recvstate_timestamp = cluster_timezone.localize(datetime.datetime.now())
    def set_req_state(self, req_state="error not set"):
        self.device.reqstate = req_state
        self.device.reqstate_timestamp = cluster_timezone.localize(datetime.datetime.now())
    def refresh_target_kernel(self, *args, **kwargs):
        if kwargs.get("refresh", True):
            self.refresh_device()
            self.check_network_settings()
        if self.is_node:
            # files to remove
            self._files_to_rm = set([self.ip_file_name, self.ip_mac_file_name, self.menu_file_name])
            if self.device.new_kernel:
                if not self.device.stage1_flavour:
                    self.device.stage1_flavour = "cpio"
                    self.log("setting stage1_flavour to '{}'".format(self.device.stage1_flavour))
                    self.device.save(update_fields=["stage1_flavour"])
                if not self.device.prod_link:
                    self.log("no production link set", logging_tools.LOG_LEVEL_WARN)
                    prod_net = None
                else:
                    prod_net = self.device.prod_link
                    self.log("production network is {}".format(unicode(prod_net)))
                if self.device.new_state:
                    new_kernel = self.device.new_kernel
                    new_state = self.device.new_state
                    self.log("refresh for target_state {}, kernel {}, stage1_flavour {}".format(
                        unicode(self.device.new_state),
                        unicode(new_kernel),
                        self.device.stage1_flavour
                    ))
                else:
                    self.log("no state set", logging_tools.LOG_LEVEL_WARN)
                    self.clear_kernel_links()
                    new_state, new_kernel = (None, None)
                if new_state:
                    if new_kernel and new_state.prod_link:
                        if machine.process.server_ip:
                            self.write_kernel_config(new_kernel)
                        else:
                            self.log("no server_ip set", logging_tools.LOG_LEVEL_ERROR)
                    elif new_state.boot_local:
                        # boot local
                        self.write_localboot_config()
                    elif new_state.memory_test:
                        # memory test
                        self.write_memtest_config()
                    elif new_state.boot_iso:
                        self.write_isoboot_config()
                    else:
                        self.log("cannot handle new_state '{}'".format(unicode(new_state)),
                                 logging_tools.LOG_LEVEL_ERROR)
            else:
                self.log("new_kernel not set", logging_tools.LOG_LEVEL_ERROR)
                # self.clear_ip_mac_files()
                self.clear_kernel_links()
            self.remove_files()
        else:
            self.log("not node", logging_tools.LOG_LEVEL_WARN)
    def remove_files(self):
        for _f_name in self._files_to_rm:
            try:
                os.unlink(os.path.join(_f_name))
            except:
                self.log(
                    "error removing file {}".format(
                        _f_name
                   ),
                    logging_tools.LOG_LEVEL_ERROR
                )
            else:
                self.log("removed file {}".format(_f_name))
    def clear_kernel_links(self):
        for link_name in ["i", "k"]:
            full_name = os.path.join(self.etherboot_dir, link_name)
            if os.path.islink(full_name):
                self.log("removing kernel link {}".format(full_name))
                os.unlink(full_name)
    def write_file(self, f_name, f_content, **kwargs):
        self._files_to_rm.remove(f_name)
        open(f_name, "w").write(f_content)
    def write_isoboot_config(self):
        if self.device.kernel_append:
            _iso = self.device.kernel_append
            self.log("using iso {} for booting".format(_iso))
            for name in [self.ip_file_name, self.ip_mac_file_name]:
                self.write_file(name, "\n".join([
                    "DEFAULT isoboot",
                    "LABEL isoboot",
                    "KERNEL memdisk",
                    "APPEND iso initrd=isos/{} raw".format(_iso),
                    ""])
                )
        else:
            self.log("no kernel_append (==iso filename) given", logging_tools.LOG_LEVEL_CRITICAL)
    def write_memtest_config(self):
        iso_files = [_entry for _entry in os.listdir(self.iso_dir) if _entry.startswith("memtest")]
        if iso_files:
            memtest_iso = iso_files[0]
            self.log("using iso {} for memtest".format(memtest_iso))
            for name in [self.ip_file_name, self.ip_mac_file_name]:
                self.write_file(name, "\n".join([
                    "DEFAULT memtest",
                    "LABEL memtest",
                    "KERNEL memdisk",
                    "APPEND iso initrd=isos/{} raw".format(memtest_iso),
                    ""]))
        else:
            self.log("no memtest iso found in {}".format(self.iso_dir), logging_tools.LOG_LEVEL_ERROR)
    def write_localboot_config(self):
        for name in [self.ip_file_name, self.ip_mac_file_name]:
            self.write_file(name, "\n".join([
                "DEFAULT linux",
                "LABEL linux",
                "IMPLICIT 0",
                "LOCALBOOT 0",
                ""]))
    def write_kernel_config(self, new_kernel):
        kern_dst_dir = self.etherboot_dir
        if kern_dst_dir:
            if os.path.isdir(kern_dst_dir):
                for file_name in ["i", "k", "x"]:
                    fname = os.path.join(kern_dst_dir, file_name)
                    if os.path.islink(fname):
                        os.unlink(fname)
                for stage_name in ["stage2", "stage3"]:
                    stage_source = "{}/lcs/{}".format(
                        global_config["CLUSTER_DIR"],
                        stage_name)
                    stage_dest = os.path.join(kern_dst_dir, stage_name)
                    if not os.path.isfile(stage_source):
                        self.log("Error, cannot find {}_source '{}'...".format(stage_name, stage_source))
                    elif not os.path.isfile(stage_dest) or (os.path.isfile(stage_dest) and (os.stat(stage_source)[stat.ST_MTIME] > os.stat(stage_dest)[stat.ST_MTIME]) or os.stat(stage_source)[stat.ST_SIZE] != os.stat(stage_dest)[stat.ST_SIZE]):
                        self.log("Copying {} from {} to {} ...".format(stage_name, stage_source, stage_dest))
                        open(stage_dest, "w").write(open(stage_source, "r").read())
                # print kernel_stuff
                kern_base_dir = "../../kernels/{}".format(new_kernel.name)
                kern_abs_base_dir = "{}/kernels/{}".format(global_config["TFTP_DIR"], new_kernel.name)
                unlink_field = ["{}/k".format(kern_dst_dir),
                                "{}/i".format(kern_dst_dir),
                                "{}/x".format(kern_dst_dir)]
                valid_links = []
                if os.path.isdir(kern_abs_base_dir):
                    # check if requested flavour is ok
                    if not hasattr(new_kernel, "stage1_{}_present".format(self.device.stage1_flavour)):
                        self.log("requested stage1_flavour '{}' not known".format(
                            self.device.stage1_flavour),
                                 logging_tools.LOG_LEVEL_ERROR)
                    elif not getattr(new_kernel, "stage1_{}_present".format(self.device.stage1_flavour)):
                        self.log("requested stage1_flavour '{}' not present".format(
                            self.device.stage1_flavour),
                                 logging_tools.LOG_LEVEL_ERROR)
                    else:
                        link_field = [
                            ("%s/bzImage" % (kern_abs_base_dir),
                             "%s/bzImage" % (kern_base_dir),
                             "%s/k" % (kern_dst_dir)),
                            ("%s/initrd_%s.gz" % (kern_abs_base_dir, self.device.stage1_flavour),
                             "%s/initrd_%s.gz" % (kern_base_dir, self.device.stage1_flavour),
                             "%s/i" % (kern_dst_dir))]
                        if new_kernel.xen_host_kernel:
                            link_field.append(("%s/xen.gz" % (kern_abs_base_dir), "%s/xen.gz" % (kern_base_dir), "%s/x" % (kern_dst_dir)))
                        for abs_src, src, dst in link_field:
                            if new_kernel.name:
                                if os.path.isfile(abs_src):
                                    c_link = True
                                    if os.path.islink(dst):
                                        act_dst = os.readlink(dst)
                                        if src == act_dst:
                                            # self.log("Link %s is still valid (points to %s)" % (dst, act_dst))
                                            valid_links.append(dst)
                                            c_link = False
                                        else:
                                            os.unlink(dst)
                                    elif os.path.isfile(dst):
                                        os.unlink(dst)
                                    if c_link:
                                        self.log("Linking from %s to %s" % (dst, src))
                                        # print "symlink()", src, dst
                                        os.symlink(src, dst)
                                        valid_links.append(dst)
                                else:
                                    self.log("source %s for symlink() does not exist" % (abs_src),
                                             logging_tools.LOG_LEVEL_ERROR)
                                    valid_links.append(dst)
                else:
                    self.log("source_kernel_dir %s does not exist" % (kern_abs_base_dir),
                             logging_tools.LOG_LEVEL_ERROR)
                    # self.device_log_entry(0,
                    #                      "e",
                    #                      "error kernel_dir dir '%s' not found" % (kern_abs_base_dir),
                    #                      sql_queue,
                    #                      loc_config["LOG_SOURCE_IDX"])
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
                if self.device.stage1_flavour == "cpio":
                    root_str = ""
                else:
                    root_str = "root=/dev/ram0"
                append_string = (" ".join([
                    root_str,
                    "init=/linuxrc rw nbd=%s,%s,%d,%s uuid=%s %s" % (
                        self.bootnetdevice.devname,
                        self.bootnetdevice.driver,
                        self.bootnetdevice.ethtool_options,
                        self.bootnetdevice.driver_options.replace(" ", ur"§"),
                        self.device.get_boot_uuid(),
                        self.device.kernel_append
                        )])).strip().replace("  ", " ").replace("  ", " ")
                # self.clear_ip_mac_files([self.ip_mac_file_base_name])
                if new_kernel.xen_host_kernel:
                    append_field = [
                        "x dom0_mem=524288",
                        "k console=tty0 ip=%s:%s::%s %s" % (
                            self.maint_ip.ip,
                            machine.process.server_ip,
                            ipvx_tools.get_network_name_from_mask(self.maint_ip.network.netmask),
                            append_string),
                        "i"]
                else:
                    total_append_string = "initrd={}/i ip={}:{}::{} {}".format(
                        self.maint_ip.ip,
                        self.maint_ip.ip,
                        machine.process.server_ip,
                        ipvx_tools.get_network_name_from_mask(self.maint_ip.network.netmask),
                        append_string)
                pxe_lines = []
                if global_config["NODE_BOOT_DELAY"]:
                    pxe_lines.extend(["TIMEOUT %d" % (global_config["NODE_BOOT_DELAY"]),
                                      "PROMPT 1"])
                pxe_lines.extend(["DISPLAY {}/menu".format(self.maint_ip.ip),
                                  "DEFAULT linux auto"])
                if new_kernel.name:
                    if new_kernel.xen_host_kernel:
                        pxe_lines.extend([
                            "LABEL linux",
                            "    KERNEL mboot.c32",
                            "    APPEND %s" % (" --- ".join(append_field))])
                    else:
                        pxe_lines.extend([
                            "LABEL linux",
                            "    KERNEL {}/k".format(self.maint_ip.ip),
                            "    APPEND %s" % (total_append_string)])
                pxe_lines.extend([""])
                if global_config["FANCY_PXE_INFO"]:
                    menu_lines = ["\x0c\x0f20%s\x0f07" % (("init.at Bootinfo, %s%s" % (time.ctime(), 80 * " "))[0:79])]
                else:
                    menu_lines = ["",
                                  ("init.at Bootinfo, %s%s" % (time.ctime(), 80 * " "))[0:79]]
                menu_lines.extend([
                    "Nodename  , IP : %-30s, %s" % (self.device.name, self.maint_ip.ip),
                    "Servername, IP : %-30s, %s" % (global_config["SERVER_SHORT_NAME"], machine.process.server_ip),
                    "Netmask        : %s (%s)" % (self.maint_ip.network.netmask, ipvx_tools.get_network_name_from_mask(self.maint_ip.network.netmask)),
                    "MACAddress     : %s" % (self.bootnetdevice.macaddr.lower()),
                    "Stage1 flavour : %s" % (self.device.stage1_flavour),
                    "Kernel to boot : %s" % (new_kernel.name or "<no kernel set>"),
                    "device UUID    : %s" % (self.device.get_boot_uuid()),
                    "Kernel options : %s" % (append_string or "<none set>"),
                    "target state   : %s" % (unicode(self.device.new_state) if self.device.new_state_id else "???"),
                    "will boot %s" % ("in %s" % (logging_tools.get_plural("second", int(global_config["NODE_BOOT_DELAY"] / 10))) if global_config["NODE_BOOT_DELAY"] else "immediately"),
                    "",
                    ""])
                self.write_file(self.ip_file_name    , "\n".join(pxe_lines))
                self.write_file(self.ip_mac_file_name, "\n".join(pxe_lines))
                self.write_file(self.menu_file_name  , "\n".join(menu_lines))
                if new_kernel.xen_host_kernel:
                    if global_config["XENBOOT"]:
                        open(self.mboot_file_name, "w").write(global_config["MBOOT.C32"])
                    else:
                        self.log("not XENBOOT capable (MBOOT.C32 not found)", logging_tools.LOG_LEVEL_ERROR)
            else:
                self.log("Error: directory {} does not exist".format(kern_dst_dir))
                # self.device_log_entry(1,
                #                      "e",
                #                      "error etherboot dir '%s' not found" % (kern_dst_dir),
                #                      sql_queue,
                #                      self.__loc_config["NODE_SOURCE_IDX"])
        else:
            self.log("Error: etherboot-dir not defined")
    def read_dot_files(self):
        if not self.is_node:
            self.log("not node, checking network settings", logging_tools.LOG_LEVEL_WARN)
            self.refresh_device()
            self.check_network_settings()
        if self.is_node:
            c_dir = self.config_dir
            if not os.path.isdir(c_dir):
                self.log("config_dir '{}' not found".format(c_dir), logging_tools.LOG_LEVEL_ERROR)
                return
            self.log("starting readdots in dir '{}'".format(c_dir))
            hlist = [(".version"  , "imageversion"       , None, None),
                     (".imagename", "actimage"           , None, None),
                     (".imagename", "act_image"          , image, "name"),
                     # (".kernel"   , "actkernel"          , None, None),
                     (".kernel"   , "act_kernel"         , kernel, "name"),
                     (".kversion" , "kernelversion"      , None, None),
                     # handled by cluster-config-server
                     # (".parttype" , "act_partition_table", partition_table, "name"),
                     (None        , "act_kernel_build"   , None, None)]
            s_dict = {}
            num_tried, num_ok, num_found = (0, 0, 0)
            for file_name, dbentry, set_obj, q_name in hlist:
                if file_name:
                    full_name = os.path.join(c_dir, file_name)
                    num_tried += 1
                    if os.path.exists(full_name):
                        num_found += 1
                        try:
                            line = open(full_name, "r").readline().strip()
                        except:
                            pass
                        else:
                            num_ok += 1
                            if set_obj:
                                try:
                                    new_obj = set_obj.objects.get(Q(**{q_name : line}))
                                except set_obj.DoesNotExist:
                                    self.log("no %s with %s=%s found" % (set_obj._meta.model_name, q_name, line), logging_tools.LOG_LEVEL_ERROR)
                                    new_obj = None
                                else:
                                    # print dbentry, line, new_obj.pk, getattr(self.device, "%s_id" % (dbentry))
                                    if new_obj.pk != getattr(self.device, "%s_id" % (dbentry)):
                                        s_dict[dbentry] = new_obj
                            else:
                                pass
                                # print "dbe", dbentry, line, self.device
            if s_dict:
                for key, value in s_dict.iteritems():
                    setattr(self.device, key, value)
                self.device.save(update_fields=s_dict.keys())
            num_changed = len(s_dict)
            self.log("readdots finished (%d tried, %d found, %d ok, %d changed%s)" % (
                num_tried,
                num_found,
                num_ok,
                num_changed,
                (num_changed and " [%s]" % (", ".join(["%s=%s" % (key, unicode(value)) for key, value in s_dict.iteritems()])) or "")))
    def handle_mac_command(self, com_name):
        self.refresh_device()
        self.check_network_settings()
        if self.maint_ip:
            ip_to_write, ip_to_write_src = (self.maint_ip.ip, "maint_ip")
        elif self.bootnetdevice and self.bootnetdevice.dhcp_device:
            # FIXME
            if self.ip_dict:
                ip_to_write, ip_to_write_src = (self.ip_dict.keys()[0], "first ip of ip_dict.keys()")
            else:
                ip_to_write, ip_to_write_src = (None, "")
        else:
            ip_to_write, ip_to_write_src = (None, "")
        om_shell_coms = []
        if com_name == "alter":
            if self.device.dhcp_written:
                if self.device.dhcp_write and ip_to_write:
                    if self.dhcp_mac_written == self.device.bootnetdevice.macaddr and self.dhcp_ip_written == ip_to_write:
                        self.log("MAC/IP in DHCP database up to date, not writing")
                        om_shell_coms = []
                    else:
                        om_shell_coms = ["delete", "write"]
                else:
                    om_shell_coms = ["delete"]
            else:
                if self.device.dhcp_write and ip_to_write:
                    om_shell_coms = ["write"]
                else:
                    om_shell_coms = ["delete"]
        elif com_name == "write":
            if self.device.dhcp_write and ip_to_write:
                om_shell_coms = ["write"]
            else:
                om_shell_coms = []
        elif com_name == "delete":
            if self.device.dhcp_write:
                om_shell_coms = ["delete"]
            else:
                om_shell_coms = []
        self.log("transformed dhcp_command %s to %s: %s (%s)" % (
            com_name,
            logging_tools.get_plural("om_shell_command", len(om_shell_coms)),
            ", ".join(om_shell_coms),
            ip_to_write and "ip %s from %s" % (ip_to_write, ip_to_write_src) or "no ip"))
        simple_command.process.set_check_freq(200)
        for om_shell_com in om_shell_coms:
            om_array = ['server 127.0.0.1',
                        'port 7911',
                        'connect',
                        'new host',
                        'set name = "%s"' % (self.device.name)]
            if om_shell_com == "write":
                om_array.extend(['set hardware-address = %s' % (self.device.bootnetdevice.macaddr),
                                 'set hardware-type = 1',
                                 'set ip-address=%s' % (ip_to_write)])
                om_array.extend(['set statements = "' +
                                 'supersede host-name = \\"%s\\" ;' % (self.device.name) +
                                 'if substring (option vendor-class-identifier, 0, 9) = \\"PXEClient\\" { ' +
                                 'filename = \\"etherboot/pxelinux.0\\" ; ' + # % (ip_to_write) +
                                 '} "'])
                om_array.append('create')
            elif om_shell_com == "delete":
                om_array.extend(['open',
                                 'remove'])
            om_array.append("")
            simple_command("echo -e '%s' | /usr/bin/omshell" % ("\n".join(om_array)),
                           done_func=self.omshell_done,
                           stream_id="mac",
                           short_info=True,
                           add_info="omshell %s" % (com_name),
                           log_com=self.log,
                           info=om_shell_com)
    def omshell_done(self, om_sc):
        cur_out = om_sc.read()
        self.log(
            "omshell finished with state {:d} ({:d} bytes)".format(
                om_sc.result,
                len(cur_out)
            )
        )
        error_re = re.compile("^.*can't (?P<what>.*) object: (?P<why>.*)$")
        lines = cur_out.split("\n")
        error_str = ""
        for line in lines:
            if line.lower().count("connection refused") or line.lower().count("dhcpctl_connect: no more"):
                self.log(line, logging_tools.LOG_LEVEL_ERROR)
                error_str = "connection refused"
            if line.startswith(">"):
                err_m = error_re.match(line)
                if err_m:
                    error_str = err_m.group("why")
                    self.log("an error occured: %s (%s, %s)" % (
                        line,
                        err_m.group("what"),
                        err_m.group("why")),
                             logging_tools.LOG_LEVEL_ERROR)
        if error_str:
            if error_str in ["key conflict", "not found"]:
                new_dhcp_written = False
            elif error_str in ["already exists"]:
                new_dhcp_written = True
            else:
                # unknown
                new_dhcp_written = None
            self.device.add_log(global_config["LOG_SOURCE_IDX"], logging_tools.LOG_LEVEL_ERROR, "DHCP: %s" % (error_str)).save()
        else:
            if om_sc.info == "write":
                new_dhcp_written = True
                self.dhcp_mac_written = self.device.bootnetdevice.macaddr
                self.dhcp_ip_written = self.maint_ip.ip
            elif om_sc.info == "delete":
                self.dhcp_mac_writte, self.dhcp_ip_written = (None, None)
                new_dhcp_written = False
            self.device.add_log(global_config["LOG_SOURCE_IDX"], logging_tools.LOG_LEVEL_OK, "DHCP %s ok" % (om_sc.info)).save()
        if new_dhcp_written is None:
            new_dhcp_written = self.device.dhcp_written
        # selective update
        self.log("storing state to db: dhcp_written=%s, dhcp_error='%s'" % (new_dhcp_written, error_str))
        self.device.dhcp_written = new_dhcp_written
        self.device.dhcp_error = error_str
        self.device.save(update_fields=["dhcp_written", "dhcp_error"])
    def feed_dhcp(self, in_dict, in_line):
        self.refresh_device()
        if in_dict["key"] == "discover":
            # dhcp feed, in most cases discover
            self.log("set macaddress of bootnetdevice to '%s'" % (in_dict["macaddr"]))
            self.bootnetdevice.macaddr = in_dict["macaddr"]
            self.bootnetdevice.save(update_fields=["macaddr"])
            self.device.dhcp_mac = False
            self.device.save(update_fields=["dhcp_mac"])
            devicelog.new_log(
                self.device,
                machine.process.node_src,
                cached_log_status("i"),
                "set macaddr of %s to %s" % (self.bootnetdevice.devname, in_dict["macaddr"]))
            macbootlog(
                device=self.device,
                macaddr=in_dict["macaddr"],
                entry_type=in_dict["key"],
                ip_action="SET").save()
            # no change to dhcp-server
            self.handle_mac_command("alter")
        else:
            change_fields = set()
            if self.device.dhcp_mac:
                # clear dhcp_mac
                self.log("clearing dhcp_mac")
                self.device.dhcp_mac = False
                change_fields.add("dhcp_mac")
            devicelog.new_log(
                self.device,
                machine.process.node_src,
                cached_log_status("i"),
                "DHCP / %s (%s)" % (in_dict["key"], in_dict["ip"]))
            self.set_recv_state("got IP-Address via DHCP")
            change_fields.add("recvstate")
            change_fields.add("recvstate_timestamp")
            if change_fields:
                self.device.save(update_fields=list(change_fields))
            if self.device.new_state:
                self.refresh_target_kernel(refresh=False)
    def nodeinfo(self, in_text, instance):
        self.log("got info '%s' from %s" % (in_text, instance))
        self.set_recv_state(in_text)
        self.device.save(update_fields=["recvstate", "recvstate_timestamp"])
        devicelog.new_log(
            self.device,
            machine.process.node_src,
            cached_log_status("i"),
            in_text)
        return "ok got it"
    def nodestatus(self, in_text, instance):
        self.log("got status '%s' from %s" % (in_text, instance))
        self.set_req_state(in_text)
        self.device.save(update_fields=["reqstate", "reqstate_timestamp"])

class controlling_device(machine):
    def init(self):
        # clear ip_dict
        self.ip_dict = {}
        # clear maintenance ip/mac
        self.set_maint_ip()
        # check network settings
        self.check_network_settings()
        # save changes done during init
        # do not overwrite states, preserve
        # self.set_recv_state()
        # self.set_req_state()
        # should now be handled in device_pre_save
        if not self.device.uuid:
            self.device.uuid = str(uuid.uuid4())
            self.log("setting uuid to {}".format(self.device.uuid))
        machine.add_lut_key(self, self.device.uuid)
        machine.add_lut_key(self, self.device.get_boot_uuid())
        self.device.save()
    # machine related
    def set_maint_ip(self, ip=None):
        if ip:
            if self.maint_ip and (self.maint_ip.ip != ip.ip or self.maint_ip.netdevice.macaddr != ip.netdevice.macaddr):
                self.log("Changing maintenance IP and MAC from {} ({}) [{}] to {} ({}) [{}] and setting node-flag".format(
                    self.maint_ip.ip,
                    self.maint_ip.get_hex_ip(),
                    self.maint_ip.netdevice.macaddr,
                    ip.ip,
                    ip.get_hex_ip(),
                    ip.netdevice.macaddr))
            else:
                self.log("Setting maintenance IP and MAC to {} ({}) [{}] and setting node-flag".format(
                    ip.ip,
                    ip.get_hex_ip(),
                    ip.netdevice.macaddr))
            self.maint_ip = ip
            self.is_node = True
        else:
            self.log("Clearing maintenance IP and MAC (and node-flag)")
            self.maint_ip = None
            self.dhcp_mac_written = None
            self.dhcp_ip_written = None
            self.is_node = False
    def get_bnd(self):
        return self.__bnd
    def set_bnd(self, val):
        if val is None:
            self.log("clearing bootnetdevice")
            self.__bnd = val
        else:
            self.log("changing bootnetdevice_name from '{}' to '{}'".format(self.__bnd.devname if self.__bnd else "unset", val))
            self.__bnd = val
    bootnetdevice = property(get_bnd, set_bnd)
    def get_sip_d(self):
        return self.__srv_ip_dict
    def set_sip_d(self, val):
        self.__srv_ip_dict = val
        if val is not None:
            self.log("Found {}:".format(logging_tools.get_plural("valid device->server ip-mapping", len(val.keys()))))
            for my_ip, s_ip in val.iteritems():
                self.log("  {:<15s} -> {:<15s} [{}]".format(my_ip, s_ip["ip"], s_ip["identifier"]))
    server_ip_dict = property(get_sip_d, set_sip_d)
    def check_network_settings(self):
        # bootnet device name
        self.bootnetdevice = None
        nd_list, nd_lut = (set(), {})
        for net_dev in self.device.netdevice_set.all():
            nd_list.add(net_dev.pk)
            nd_lut[net_dev.pk] = net_dev
            if self.device.bootnetdevice_id and net_dev.pk == self.device.bootnetdevice.pk:
                # set bootnetdevice_name
                self.bootnetdevice = net_dev
        # dict: my net_ip -> dict [identifier, ip] server_net_ip
        server_ip_dict = {}
        # dict: ip -> identifier
        ip_dict = {}
        if nd_list:
            machine.process.update_router_object()
            all_paths = sorted(
                machine.process.router_obj.get_ndl_ndl_pathes(
                    machine.process.sc.netdevice_idx_list,
                    nd_list,
                    only_endpoints=True,
                    add_penalty=True,
                )
            )
            # get hopcount
            # latest_gen = route_generation.objects.filter(Q(valid=True)).order_by("-pk")[0]
            # my_hc = hopcount.objects.filter(
                # Q(route_generation=latest_gen) &
                # Q(s_netdevice__in=machine.process.sc.netdevice_idx_list) &
                # Q(d_netdevice__in=nd_list)).order_by("value")
            for _ in all_paths:
                srv_dev, mach_dev = (machine.process.sc.nd_lut[_[1]], nd_lut[_[2]])
                for cur_ip in mach_dev.net_ip_set.all():
                    cur_id = cur_ip.network.network_type.identifier
                    srv_ips = list(set([srv_ip.ip for srv_ip in machine.process.sc.identifier_ip_lut.get(cur_id, [])]) & set([x2.ip for x2 in machine.process.sc.netdevice_ip_lut[srv_dev.pk]]))
                    if srv_ips and not cur_ip.ip in server_ip_dict:
                        server_ip_dict[cur_ip.ip] = {"identifier" : cur_id,
                                                     "ip"         : srv_ips[0] if srv_ips else None}
                    if cur_id == "b" and srv_ips:
                        self.set_maint_ip(cur_ip)
                    if cur_ip.ip not in ip_dict:
                        # definitely wrong, oh my...
                        # ip_dict[cur_ip.ip] = ip_dict
                        # not sure ...
                        ip_dict[cur_ip.ip] = cur_ip
            self.log(
                "found {}: {}".format(
                    logging_tools.get_plural("IP-address", len(ip_dict)),
                    ", ".join(sorted(ip_dict.keys()))))
            self.log("Setting reachable flag")
            self.device.reachable = True
        else:
            self.log("Cannot add device {} (empty ip_list -> cannot reach host)".format(self.name),
                     logging_tools.LOG_LEVEL_WARN)
            self.device.reachable = False
        self.set_ip_dict(ip_dict)
        self.server_ip_dict = server_ip_dict
    def set_recv_state(self, recv_state="error not set"):
        self.device.recvstate = recv_state
        self.device.recvstate_timestamp = cluster_timezone.localize(datetime.datetime.now())
    def set_req_state(self, req_state="error not set"):
        self.device.reqstate = req_state
        self.device.reqstate_timestamp = cluster_timezone.localize(datetime.datetime.now())
    def handle_mac_command(self, com_name):
        self.refresh_device()
        self.check_network_settings()
        if self.maint_ip:
            ip_to_write, ip_to_write_src = (self.maint_ip.ip, "maint_ip")
        elif self.bootnetdevice and self.bootnetdevice.dhcp_device:
            # FIXME
            if self.ip_dict:
                ip_to_write, ip_to_write_src = (self.ip_dict.keys()[0], "first ip of ip_dict.keys()")
            else:
                ip_to_write, ip_to_write_src = (None, "")
        else:
            ip_to_write, ip_to_write_src = (None, "")
        om_shell_coms = []
        if com_name == "alter":
            if self.device.dhcp_written:
                if self.device.dhcp_write and ip_to_write:
                    if self.dhcp_mac_written == self.device.bootnetdevice.macaddr and self.dhcp_ip_written == ip_to_write:
                        self.log("MAC/IP in DHCP database up to date, not writing")
                        om_shell_coms = []
                    else:
                        om_shell_coms = ["delete", "write"]
                else:
                    om_shell_coms = ["delete"]
            else:
                if self.device.dhcp_write and ip_to_write:
                    om_shell_coms = ["write"]
                else:
                    om_shell_coms = ["delete"]
        elif com_name == "write":
            if self.device.dhcp_write and ip_to_write:
                om_shell_coms = ["write"]
            else:
                om_shell_coms = []
        elif com_name == "delete":
            if self.device.dhcp_write:
                om_shell_coms = ["delete"]
            else:
                om_shell_coms = []
        self.log("transformed dhcp_command %s to %s: %s (%s)" % (
            com_name,
            logging_tools.get_plural("om_shell_command", len(om_shell_coms)),
            ", ".join(om_shell_coms),
            ip_to_write and "ip %s from %s" % (ip_to_write, ip_to_write_src) or "no ip"))
        simple_command.process.set_check_freq(200)
        for om_shell_com in om_shell_coms:
            om_array = ['server 127.0.0.1',
                        'port 7911',
                        'connect',
                        'new host',
                        'set name = "%s"' % (self.device.name)]
            if om_shell_com == "write":
                om_array.extend(['set hardware-address = %s' % (self.device.bootnetdevice.macaddr),
                                 'set hardware-type = 1',
                                 'set ip-address=%s' % (ip_to_write)])
                om_array.extend(['set statements = "' +
                                 'supersede host-name = \\"%s\\" ;' % (self.device.name) +
                                 'if substring (option vendor-class-identifier, 0, 9) = \\"PXEClient\\" { ' +
                                 'filename = \\"etherboot/pxelinux.0\\" ; ' + # % (ip_to_write) +
                                 '} "'])
                om_array.append('create')
            elif om_shell_com == "delete":
                om_array.extend(['open',
                                 'remove'])
            om_array.append("")
            simple_command("echo -e '%s' | /usr/bin/omshell" % ("\n".join(om_array)),
                           done_func=self.omshell_done,
                           stream_id="mac",
                           short_info=True,
                           add_info="omshell %s" % (com_name),
                           log_com=self.log,
                           info=om_shell_com)
    def omshell_done(self, om_sc):
        cur_out = om_sc.read()
        self.log(
            "omshell finished with state {:d} ({:d} bytes)".format(
                om_sc.result,
                len(cur_out)
            )
        )
        error_re = re.compile("^.*can't (?P<what>.*) object: (?P<why>.*)$")
        lines = cur_out.split("\n")
        error_str = ""
        for line in lines:
            if line.lower().count("connection refused") or line.lower().count("dhcpctl_connect: no more"):
                self.log(line, logging_tools.LOG_LEVEL_ERROR)
                error_str = "connection refused"
            if line.startswith(">"):
                err_m = error_re.match(line)
                if err_m:
                    error_str = err_m.group("why")
                    self.log("an error occured: %s (%s, %s)" % (
                        line,
                        err_m.group("what"),
                        err_m.group("why")),
                             logging_tools.LOG_LEVEL_ERROR)
        if error_str:
            if error_str in ["key conflict", "not found"]:
                new_dhcp_written = False
            elif error_str in ["already exists"]:
                new_dhcp_written = True
            else:
                # unknown
                new_dhcp_written = None
            self.device.add_log(global_config["LOG_SOURCE_IDX"], logging_tools.LOG_LEVEL_ERROR, "DHCP: %s" % (error_str)).save()
        else:
            if om_sc.info == "write":
                new_dhcp_written = True
                self.dhcp_mac_written = self.device.bootnetdevice.macaddr
                self.dhcp_ip_written = self.maint_ip.ip
            elif om_sc.info == "delete":
                self.dhcp_mac_writte, self.dhcp_ip_written = (None, None)
                new_dhcp_written = False
            self.device.add_log(global_config["LOG_SOURCE_IDX"], logging_tools.LOG_LEVEL_OK, "DHCP %s ok" % (om_sc.info)).save()
        if new_dhcp_written is None:
            new_dhcp_written = self.device.dhcp_written
        # selective update
        self.log("storing state to db: dhcp_written=%s, dhcp_error='%s'" % (new_dhcp_written, error_str))
        self.device.dhcp_written = new_dhcp_written
        self.device.dhcp_error = error_str
        self.device.save(update_fields=["dhcp_written", "dhcp_error"])
    def feed_dhcp(self, in_dict, in_line):
        self.refresh_device()
        if in_dict["key"] == "discover":
            # dhcp feed, in most cases discover
            self.log("set macaddress of bootnetdevice to '%s'" % (in_dict["macaddr"]))
            self.bootnetdevice.macaddr = in_dict["macaddr"]
            self.bootnetdevice.save(update_fields=["macaddr"])
            self.device.dhcp_mac = False
            self.device.save(update_fields=["dhcp_mac"])
            devicelog.new_log(
                self.device,
                machine.process.node_src,
                cached_log_status("i"),
                "set macaddr of %s to %s" % (self.bootnetdevice.devname, in_dict["macaddr"]))
            macbootlog(
                device=self.device,
                macaddr=in_dict["macaddr"],
                entry_type=in_dict["key"],
                ip_action="SET").save()
            # no change to dhcp-server
            self.handle_mac_command("alter")
        else:
            change_fields = set()
            if self.device.dhcp_mac:
                # clear dhcp_mac
                self.log("clearing dhcp_mac")
                self.device.dhcp_mac = False
                change_fields.add("dhcp_mac")
            devicelog.new_log(
                self.device,
                machine.process.node_src,
                cached_log_status("i"),
                "DHCP / %s (%s)" % (in_dict["key"], in_dict["ip"]))
            self.set_recv_state("got IP-Address via DHCP")
            change_fields.add("recvstate")
            change_fields.add("recvstate_timestamp")
            if change_fields:
                self.device.save(update_fields=list(change_fields))
            if self.device.new_state:
                self.refresh_target_kernel(refresh=False)

class hm_icmp_protocol(icmp_class.icmp_protocol):
    def __init__(self, process, log_template, verbose):
        self.__log_template = log_template
        self.__verbose = verbose
        icmp_class.icmp_protocol.__init__(self)
        self.__work_dict, self.__seqno_dict = ({}, {})
        self.__process = process
        self.init_socket()
        self.__process.register_socket(self.socket, select.POLLIN, self.received)
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, "[icmp] %s" % (what))
    def __setitem__(self, key, value):
        self.__work_dict[key] = value
    def __getitem__(self, key):
        return self.__work_dict[key]
    def __delitem__(self, key):
        for seq_key in self.__work_dict[key]["sent_list"].keys():
            if seq_key in self.__seqno_dict:
                del self.__seqno_dict[seq_key]
        del self.__work_dict[key]
    def ping(self, seq_str, target, num_pings, timeout, **kwargs):
        if self.__verbose:
            self.log("ping to %s (%d, %.2f) [%s]" % (target, num_pings, timeout, seq_str))
        cur_time = time.time()
        self[seq_str] = {
            "host"       : target,
            "num"        : num_pings,
            "timeout"    : timeout,
            "start"      : cur_time,
            "id"         : kwargs.get("id", seq_str),
            # time between pings
            "slide_time" : 0.1,
            "sent"       : 0,
            "recv_ok"    : 0,
            "recv_fail"  : 0,
            "error_list" : [],
            "sent_list"  : {},
            "recv_list"  : {},
        }
        self._update()
    def _update(self):
        cur_time = time.time()
        del_keys = []
        # pprint.pprint(self.__work_dict)
        for key, value in self.__work_dict.iteritems():
            if value["sent"] < value["num"]:
                if value["sent_list"]:
                    # send if last send was at least slide_time ago
                    to_send = max(value["sent_list"].values()) + value["slide_time"] < cur_time or value["recv_ok"] == value["sent"]
                else:
                    # always send
                    to_send = True
                if to_send:
                    value["sent"] += 1
                    try:
                        self.send_echo(value["host"])
                    except:
                        value["error_list"].append(process_tools.get_except_info())
                        self.log("error sending to %s: %s" % (value["host"],
                                                              ", ".join(value["error_list"])),
                                 logging_tools.LOG_LEVEL_ERROR)
                    else:
                        value["sent_list"][self.echo_seqno] = cur_time
                        self.__seqno_dict[self.echo_seqno] = key
                        self.__process.register_timer(self._update, value["slide_time"] + 0.001, oneshot=True)
                        self.__process.register_timer(self._update, value["timeout"], oneshot=True)
            # check for timeout
            for seq_to in [s_key for s_key, s_value in value["sent_list"].iteritems() if abs(s_value - cur_time) > value["timeout"] and s_key not in value["recv_list"]]:
                value["recv_fail"] += 1
                value["recv_list"][seq_to] = None
            # check for ping finish
            if value["error_list"] or (value["sent"] == value["num"] and value["recv_ok"] + value["recv_fail"] == value["num"]):
                all_times = [value["recv_list"][s_key] - value["sent_list"][s_key] for s_key in value["sent_list"].iterkeys() if value["recv_list"].get(s_key, None) != None]
                self.__process.send_ping_result(key, value) # ["sent"], value["recv_ok"], all_times, ", ".join(value["error_list"]))
                del_keys.append(key)
        for del_key in del_keys:
            del self[del_key]
        # pprint.pprint(self.__work_dict)
    def received(self, sock):
        recv_time = time.time()
        dgram = self.parse_datagram(sock.recv(1024))
        if dgram and dgram.packet_type == 0 and dgram.ident == self.__process.pid & 0x7fff:
            seqno = dgram.seqno
            if seqno not in self.__seqno_dict:
                self.log("got result with unknown seqno %d" % (seqno),
                         logging_tools.LOG_LEVEL_ERROR)
            else:
                value = self[self.__seqno_dict[seqno]]
                if not seqno in value["recv_list"]:
                    value["recv_list"][seqno] = time.time()
                    value["recv_ok"] += 1
            self._update()

class direct_process(threading_tools.process_obj):
    def process_init(self):
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context)
        self.__verbose = global_config["VERBOSE"]
        self.icmp_protocol = hm_icmp_protocol(self, self.__log_template, self.__verbose)
        self.register_func("ping", self._ping)
    def _ping(self, *args, **kwargs):
        self.icmp_protocol.ping(*args, **kwargs)
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)
    def send_ping_result(self, *args):
        self.send_pool_message("ping_result", *args, target="control")
    def loop_post(self):
        self.__log_template.close()

class node_control_process(threading_tools.process_obj):
    def process_init(self):
        # , config, db_con, **args):
        # needed keys in config:
        # TMP_DIR ....................... directory to create temporary files
        # SET_DEFAULT_BUILD_MACHINE ..... flag, if true sets the build_machine to local machine name
        # IGNORE_KERNEL_BUILD_MACHINE ... flag, if true discards kernel if build_machine != local machine name
        # KERNEL_DIR .................... kernel directory, usually /tftpboot/kernels
        # TFTP_DIR ...................... tftpboot directory (optional)
        # SQL_ACCESS .................... access string for database
        # SERVER_SHORT_NAME ............. short name of device
        # SYNCER_ROLE ................... syncer role, mother or xen
        # check log type (queue or direct)
        self.__log_template = logging_tools.get_logger(
            global_config["LOG_NAME"],
            global_config["LOG_DESTINATION"],
            zmq=True,
            context=self.zmq_context,
            init_logger=True)
        connection.close()
        self.node_src = cached_log_source("node", None)
        self.mother_src = log_source.objects.get(Q(pk=global_config["LOG_SOURCE_IDX"]))
        # close database connection
        simple_command.setup(self)
        self.sc = config_tools.server_check(server_type="mother_server")
        if "b" in self.sc.identifier_ip_lut:
            self.server_ip = self.sc.identifier_ip_lut["b"][0].ip
            self.log("IP address in boot-net is %s" % (self.server_ip))
        else:
            self.server_ip = None
            self.log("no IP address in boot-net", logging_tools.LOG_LEVEL_ERROR)
        self.router_obj = config_tools.router_object(self.log)
        self._setup_etherboot()
        machine.setup(self)
        machine.sync()
        self.register_func("refresh", self._refresh)
        # self.register_func("alter_macaddr", self.alter_macaddr)
        self.register_func("soft_control", self._soft_control)
        self.register_func("ping_result", self._ping_result)
        self.register_timer(self._check_commands, 10)
        # self.kernel_dev = config_tools.server_check(server_type="kernel_server")
        self.register_func("syslog_line", self._syslog_line)
        self.register_func("status", self._status)
        self.register_func("nodeinfo", self._nodeinfo)
        self.register_func("nodestatus", self._nodestatus)
        # build dhcp res
        self.__dhcp_res = {
            "discover" : re.compile("(?P<program>\S+): DHCPDISCOVER from (?P<macaddr>\S+) via .*$"),
            "offer"    : re.compile("^(?P<program>\S+): DHCPOFFER on (?P<ip>\S+) to (?P<macaddr>\S+) via .*$"),
            "request"  : re.compile("^(?P<program>\S+): DHCPREQUEST for (?P<ip>\S+) .*from (?P<macaddr>\S+) via .*$"),
            "answer"   : re.compile("^(?P<program>\S+): DHCPACK on (?P<ip>\S+) to (?P<macaddr>\S+) via .*$"),
        }
        self.pending_list = []
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)
    def _setup_etherboot(self):
        map_list = [
            ("pxelinux.0", "PXELINUX_0"),
            ("memdisk", "MEMDISK"),
            ("ldlinux.c32", "LDLINUX"),
            ("mboot.c32", "MBOOT.C32")
        ]
        file_names = set([f_name for f_name, _key in map_list])
        for _dir, _dir_list, _entry_list in os.walk(global_config["ETHERBOOT_DIR"], False):
            _del_dir = False
            if os.path.basename(_dir) == "pxelinux.cfg":
                del_files = _entry_list
                _del_dir = True
            else:
                del_files = set(_entry_list) & file_names
            if del_files:
                try:
                    [os.unlink(os.path.join(_dir, _file_name)) for _file_name in del_files]
                except:
                    pass
            if _del_dir:
                os.rmdir(_dir)
        for rel_name, key_name in map_list:
            t_file = os.path.join(global_config["ETHERBOOT_DIR"], rel_name)
            if key_name in global_config:
                try:
                    file(t_file, "wb").write(global_config[key_name])
                except:
                    self.log("cannot create {}: {}".format(t_file, process_tools.get_except_info()), logging_tools.LOG_LEVEL_CRITICAL)
                else:
                    self.log("created {}".format(t_file))
            else:
                self.log("key {} not found in global_config".format(key_name), logging_tools.LOG_LEVEL_CRITICAL)
        # cleanup pxelinux.cfg
        _cfg_dir = os.path.join(global_config["ETHERBOOT_DIR"], "pxelinux.cfg")
        if os.path.isdir(_cfg_dir):
            for _entry in os.listdir(_cfg_dir):
                try:
                    os.unlink(os.path.join(_cfg_dir, _entry))
                except:
                    pass
        else:
            os.mkdir(_cfg_dir)
        # setup isos
        _iso_dir = os.path.join(global_config["ETHERBOOT_DIR"], "isos")
        global_config.add_config_entries([
            ("ISO_DIR", configfile.str_c_var(_iso_dir)),
            ])
        if not os.path.isdir(_iso_dir):
            os.mkdir(_iso_dir)
        for entry in os.listdir(global_config["SHARE_DIR"]):
            _path = os.path.join(global_config["SHARE_DIR"], entry)
            if entry.startswith("memtest"):
                t_path = os.path.join(_iso_dir, entry)
                self.log("copy from {} to {}".format(_path, t_path))
                file(t_path, "wb").write(file(_path, "rb").read())
    def update_router_object(self):
        cur_time = time.time()
        if abs(cur_time - self.router_obj.latest_update) > 5:
            self.router_obj.check_for_update()
    def _refresh(self, *args, **kwargs):
        if len(args):
            id_str, in_com = args
            in_com = server_command.srv_command(source=in_com)
            dev_list = map(lambda x: int(x), in_com.xpath(".//ns:device/@pk", smart_strings=False))
            machine.iterate("refresh_target_kernel", device_keys=dev_list)
            machine.iterate("read_dot_files", device_keys=dev_list)
            machine.iterate("handle_mac_command", "alter", device_keys=dev_list)
        else:
            id_str, in_com = (None, None)
            # use kwargs to specify certain devices
            machine.iterate("refresh_target_kernel")
            machine.iterate("read_dot_files")
            machine.iterate("handle_mac_command", "alter")
        if id_str:
            in_com.set_result("ok refreshed", server_command.SRV_REPLY_STATE_OK)
            self.send_pool_message("send_return", id_str, unicode(in_com))
    def _soft_control(self, zmq_id, in_com, *args, **kwargs):
        # soft_control takes the same path as ping but uses a different hoststatus command (not status)
        self.log("got soft_control from id %s" % (zmq_id))
        in_com = server_command.srv_command(source=in_com)
        # set zmq_id in structure
        in_com["command"].attrib["zmq_id"] = zmq_id
        # log soft control
        if "user_id" in in_com:
            log_user = user.objects.get(Q(pk=in_com["user_id"].text))
        else:
            log_user = None
        for xml_dev in in_com.xpath(".//ns:devices/ns:device"):
            u_key = int(xml_dev.attrib["pk"])
            dev = machine.get_device(u_key)
            if dev is None:
                devicelog.new_log(device.objects.get(Q(pk=u_key)), self.mother_src, logging_tools.LOG_LEVEL_ERROR, "not a device", user=log_user)
            else:
                devicelog.new_log(dev.device, self.mother_src, logging_tools.LOG_LEVEL_OK, "soft control '%s'" % (xml_dev.attrib["soft_command"]), user=log_user)
        if not machine.ping(in_com):
            # no pings send
            self._add_ping_info(in_com)
        else:
            self.pending_list.append(in_com)
    def _status(self, zmq_id, in_com, *args, **kwargs):
        self.log("got status from id %s" % (zmq_id))
        in_com = server_command.srv_command(source=in_com)
        in_com["command"].attrib["zmq_id"] = zmq_id
        if not machine.ping(in_com):
            self._add_ping_info(in_com)
        else:
            self.pending_list.append(in_com)
        machine.iterate("read_dot_files", device_keys=[int(_val) for _val in in_com.xpath(".//ns:devices/ns:device/@pk")])
    def _ping_result(self, id_str, res_dict, **kwargs):
        # a ping has finished
        new_pending = []
        cd_ping = id_str.startswith("mps_")
        # print "pr", id_str
        for cur_com in self.pending_list:
            _processed = False
            if cd_ping:
                if cur_com.xpath(".//ns:cd_ping[text() = '%s']" % (id_str), smart_strings=False):
                    machine.interpret_cdping_result(cur_com, res_dict)
                    if not cur_com.xpath(".//ns:ping_list", smart_strings=False) and not cur_com.xpath(".//ns:cd_ping_list/ns:cd_ping[@pending='1']"):
                        self._add_ping_info(cur_com)
                        _processed = True
            else:
                if cur_com.xpath(".//ns:ping[text() = '%s']" % (id_str), smart_strings=False):
                    # interpret result
                    machine.interpret_result(cur_com, id_str, res_dict)
                    if not cur_com.xpath(".//ns:ping_list", smart_strings=False) and not cur_com.xpath(".//ns:cd_ping_list/ns:cd_ping[@pending='1']"):
                        self._add_ping_info(cur_com)
                        _processed = True
            if not _processed:
                new_pending.append(cur_com)
        self.pending_list = new_pending
    def _add_ping_info(self, cur_com):
        machine.iterate_xml(cur_com, "add_ping_info")
        # print "**", cur_com.pretty_print()
        self.send_pool_message("send_return", cur_com.xpath(".//ns:command/@zmq_id", smart_strings=False)[0], unicode(cur_com))
    def _nodeinfo(self, id_str, node_text, **kwargs):
        node_id, instance = id_str.split(":", 1)
        cur_dev = machine.get_device(node_id)
        if cur_dev:
            ret_str = cur_dev.nodeinfo(node_text, instance)
        else:
            ret_str = "error no node with id '%s' found" % (node_id)
        self.send_pool_message("send_return", id_str, ret_str)
    def _nodestatus(self, id_str, node_text, **kwargs):
        node_id, instance = id_str.split(":", 1)
        cur_dev = machine.get_device(node_id)
        if cur_dev:
            cur_dev.nodestatus(node_text, instance)
        else:
            self.log("error no node with id '%s' found" % (node_id), logging_tools.LOG_LEVEL_ERROR)
    def loop_post(self):
        machine.shutdown()
        self.__log_template.close()
    def set_check_freq(self, cur_to):
        self.log("changing check_freq of check_commands to %d msecs" % (cur_to))
        self.change_timer(self._check_commands, cur_to)
    def _check_commands(self):
        simple_command.check()
        if simple_command.idle():
            self.set_loop_timer(1000)
    # def alter_macaddr(self, *args, **kwargs):
    #    if len(args):
    #        id_str, in_com = args
    #        in_com = server_command.srv_command(source=in_com)
    #        dev_list = in_com.xpath(".//ns:device/@name", smart_strings=False)
    #        # print dev_list
    #        self._adw_macaddr("alter", nodes=dev_list)
    #        self.send_pool_message("send_return", id_str, unicode(in_com))
    #    else:
    #        self._adw_macaddr("alter")
    # def _adw_macaddr(self, com_name, *args, **kwargs):
    #    # print "adw_macaddr", args, kwargs
    #    nodes = kwargs.get("nodes", machine.get_all_names(node_type=["H"]))
    #    self.log("got %s command for %s%s" % (
    #        com_name,
    #        logging_tools.get_plural("node", len(nodes)),
    #        nodes and ": %s" % (logging_tools.compress_list(nodes)) or ""))
    #    for mach_name in nodes:
    #        cur_dev = machine.get_device(mach_name)
    #        # print "***", mach_name, cur_dev, type(cur_dev)
    #        if cur_dev:
    #            cur_dev.handle_mac_command(com_name)
    def _syslog_line(self, *args, **kwargs):
        in_line = args[0]
        if "DHCP" not in in_line:
            self.log("got dhcp_line %s, skip" % (in_line))
        else:
            for key, cur_re in self.__dhcp_res.iteritems():
                cur_m = cur_re.match(in_line)
                if cur_m:
                    break
            if not cur_m:
                self.log("cannot parse %s" % (in_line), logging_tools.LOG_LEVEL_ERROR)
            else:
                cur_dict = cur_m.groupdict()
                cur_dict["key"] = key
                self._handle_syslog(cur_dict, in_line)
    def _handle_syslog(self, in_dict, in_line):
        if "ip" in in_dict:
            try:
                ip_dev = device.objects.select_related("bootnetdevice").get(Q(netdevice__net_ip__ip=in_dict["ip"]))
            except device.DoesNotExist:
                self.log("got %s for unknown ip %s" % (
                    in_dict["key"],
                    in_dict["ip"]), logging_tools.LOG_LEVEL_WARN)
                ip_dev = None
            except device.MultipleObjectsReturned:
                self.log("got %s for multiple ip %s" % (
                    in_dict["key"],
                    in_dict["ip"]), logging_tools.LOG_LEVEL_WARN)
                ip_dev = None
            else:
                if ip_dev.bootserver:
                    if ip_dev.bootserver.pk == self.sc.effective_device.pk:
                        boot_dev = machine.get_device(ip_dev.name)
                        boot_dev.log("parsed: %s" % (", ".join(["%s=%s" % (key, in_dict[key]) for key in sorted(in_dict.keys())])))
                        boot_dev.feed_dhcp(in_dict, in_line)
                    else:
                        self.log(
                            "got request %s for %s, not responsible" % (
                                in_dict["key"],
                                ip_dev.name),
                            logging_tools.LOG_LEVEL_WARN)
                else:
                    self.log("no bootserver set for device %s, strange..." % (ip_dev.name), logging_tools.LOG_LEVEL_ERROR)
        if in_dict["key"] == "discover":
            self.log("parsed: %s" % (", ".join(["%s=%s" % (key, in_dict[key]) for key in sorted(in_dict.keys())])))
            if in_line.lower().count("no free leases"):
                # nothing found
                try:
                    used_dev = device.objects.get(Q(bootserver=self.sc.effective_device) & Q(netdevice__macaddr__iexact=in_dict["macaddr"].lower()))
                except device.DoesNotExist:
                    greedy_devs = device.objects.filter(Q(bootserver=self.sc.effective_device) & Q(dhcp_mac=True)).select_related("bootnetdevice").order_by("name")
                    if len(greedy_devs):
                        if mac_ignore.objects.filter(Q(macaddr__iexact=in_dict["macaddr"].lower())).count():
                            self.log("ignoring mac-address '%s' (in ignore_list)" % (in_dict["macaddr"]))
                            macbootlog(
                                entry_type=in_dict["key"],
                                ip_action="IGNORE",
                                macaddr=in_dict["macaddr"].lower()).save()
                        else:
                            # no feed to device
                            cur_mach = machine.get_device(greedy_devs[0].name)
                            if cur_mach:
                                cur_mach.feed_dhcp(in_dict, in_line)
                            else:
                                # FIXME
                                self.log("no device found with name '%s', resync ?" % (greedy_devs[0].name), logging_tools.LOG_LEVEL_ERROR)
                    else:
                        all_greedy_devs = device.objects.filter(Q(dhcp_mac=True)).select_related("bootnetdevice").order_by("name")
                        if all_greedy_devs:
                            self.log("found %s but none related to me" % (logging_tools.get_plural("greedy device", len(all_greedy_devs))), logging_tools.LOG_LEVEL_WARN)
                        else:
                            self.log("no greedy devices found for MAC-address %s or not responsible" % (in_dict["macaddr"]))
                else:
                    # reject entry because we are unable to answer the DHCP-Request
                    macbootlog.objects.create(
                        entry_type=in_dict["key"],
                        ip_action="REJECT",
                        macaddr=in_dict["macaddr"].lower()
                    )
            else:
                # discover request got an answer
                macbootlog.objects.create(
                    entry_type=in_dict["key"],
                    ip_action="---",
                    macaddr=in_dict["macaddr"].lower()
                )
        else:
            # non-discover call, should have an ip-entry
            macbootlog.objects.create(
                entry_type=in_dict["key"],
                device=ip_dev,
                ip_action=in_dict["ip"],
                macaddr=in_dict["macaddr"].lower()
            )
