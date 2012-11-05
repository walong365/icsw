#!/usr/bin/python-init -Otu
# -*- coding: utf-8 -*-
#
# Copyright (C) 2012 Andreas Lang-Nevyjel, init.at
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

import threading_tools
import logging_tools
from mother.config import global_config
import server_command
import pprint
import time
import os
import config_tools
import icmp_twisted
import copy
import uuid
import shutil
import stat
import re
import ipvx_tools
from lxml import etree
from django.db import connection
from twisted.internet import reactor
from twisted.python import log
from twisted.internet.error import CannotListenError
from initat.cluster.backbone.models import kernel, device, hopcount, image, macbootlog, mac_ignore, \
     cached_log_status, cached_log_source, log_source, devicelog
from django.db.models import Q
import process_tools
from mother.command_tools import simple_command

class machine(object):
    # store important device-related settings
    def __init__(self, dev):
        self.device = dev
        self.name = dev.name
        self.pk = dev.pk
        self.__log_template = logging_tools.get_logger(
            "%s.%s" % (global_config["LOG_NAME"],
                       self.name.replace(".", r"\.")),
            global_config["LOG_DESTINATION"],
            zmq=True,
            context=machine.process.zmq_context,
            init_logger=True)
        self.log("added client, type is %s" % (self.device.device_type.identifier))
        self.additional_lut_keys = set()
        self.init()
    def init(self):
        pass
    def close(self):
        del_keys = copy.deepcopy(self.additional_lut_keys)
        for add_key in del_keys:
            machine.del_lut_key(self, add_key)
        self.__log_template.close()
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)
    @staticmethod
    def setup(c_process):
        machine.process = c_process
        machine.g_log("init")
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
        machine.process.log("[mach] %s" % (what), log_level)
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
        machine.g_log("found %s: %s" % (logging_tools.get_plural("device", len(query)),
                                        logging_tools.compress_list([cur_dev.name for cur_dev in query])))
        for cur_dev in query:
            machine.set_device(cur_dev)
    @staticmethod
    def add_lut_key(obj, key):
        machine.__lut[key] = obj
        obj.additional_lut_keys.add(key)
    @staticmethod
    def del_lut_key(obj, key):
        del machine.__lut[key]
        obj.additional_lut_keys.remove(key)
    @staticmethod
    def set_device(new_dev):
        if new_dev.device_type.identifier == "H":
            new_mach = host(new_dev)
        else:
            new_mach = machine(new_dev)
        machine.__unique_keys.add(new_dev.pk)
        machine.__unique_names.add(new_dev.name)
        machine.__lut[new_dev.name] = new_mach
        machine.__lut[new_dev.pk] = new_mach
    @staticmethod
    def delete_device(dev_spec):
        mach = machine.get_device(dev_spec)
        if mach:
            mach.close()
            del machine.__lut[mach.name]
            del machine.__lut[mach.pk]
            machine.__unique_keys.remove(mach.pk)
            machine.__unique_names.remove(mach.name)
    @staticmethod
    def get_device(dev_spec):
        return machine.__lut.get(dev_spec, None)
    @staticmethod
    def iterate(com_name, *args, **kwargs):
        iter_keys = machine.__unique_keys & set(kwargs.pop("device_keys", machine.__unique_keys))
        for u_key in iter_keys:
            cur_dev = machine.get_device(u_key)
            if hasattr(cur_dev, com_name):
                cur_dev.log("call '%s'" % (com_name))
                getattr(cur_dev, com_name)(*args, **kwargs)
            else:
                cur_dev.log("call '%s' not defined" % (com_name), logging_tools.LOG_LEVEL_WARN)
    @staticmethod
    def iterate_xml(srv_com, com_name, *args, **kwargs):
        for cur_dev in srv_com.xpath(None, ".//ns:device[@pk]"):
            pk = int(cur_dev.attrib["pk"])
            cur_mach = machine.get_device(pk)
            if cur_mach is None:
                pass
            else:
                getattr(cur_mach, com_name)(cur_dev, *args, **kwargs)
    @staticmethod
    def ping(srv_com):
        keys = set(map(lambda x: int(x), srv_com.xpath(None, ".//ns:device/@pk"))) & set(machine.__unique_keys)
        cur_id = machine.ping_id
        ping_list = srv_com.builder("ping_list")
        for u_key in keys:
            cur_dev = machine.get_device(u_key)
            dev_node = srv_com.xpath(None, ".//ns:device[@pk='%d']" % (cur_dev.pk))[0]
            dev_node.attrib.update({"tried"  : "%d" % (len(cur_dev.ip_dict)),
                                    "ok"     : "0",
                                    "failed" : "0"})
            for ip in cur_dev.ip_dict.iterkeys():
                cur_id_str = "mp_%d" % (cur_id)
                cur_id += 1
                machine.process.send_to_socket(machine.process.twisted_socket, ["ping", cur_id_str, ip, 4, 3.0])
                ping_list.append(srv_com.builder("ping", cur_id_str, pk="%d" % (cur_dev.pk)))
        srv_com["ping_list"] = ping_list
        machine.ping_id = cur_id
    @staticmethod
    def interpret_result(srv_com, id_str, res_dict):
        node = srv_com.xpath(None, ".//ns:ping[text() = '%s']" % (id_str))[0]
        pk = int(node.attrib["pk"])
        ping_list = node.getparent()
        ping_list.remove(node)
        if not len(ping_list):
            pl_parent = ping_list.getparent()
            pl_parent.remove(ping_list)
            pl_parent.getparent().remove(pl_parent)
        machine.get_device(pk).interpret_loc_result(srv_com, res_dict)
        print srv_com.pretty_print()
    def interpret_loc_result(self, srv_com, res_dict):
        dev_node = srv_com.xpath(None, ".//ns:device[@pk='%d']" % (self.pk))[0]
        ip_list = self.ip_dict.keys()
        if res_dict["host"] in ip_list:
            if res_dict["recv_ok"]:
                dev_node.attrib["ok"] = "%d" % (int(dev_node.attrib["ok"]) + 1)
                dev_node.attrib["ip"] = res_dict["host"]
            else:
                dev_node.attrib["failed"] = "%d" % (int(dev_node.attrib["failed"]) + 1)
        else:
            self.log("got unknown ip '%s'" % (res_dict["host"]), logging_tools.LOG_LEVEL_ERROR)
    def add_ping_info(self, cur_dev):
        print "add_ping_info", etree.tostring(cur_dev)
        cur_dev.attrib["network"] = "unknown"
        cur_dev.attrib["network_state"] = "error"
        for key, value in self.ip_dict.iteritems():
            print key, value.network
    def set_ip_dict(self, in_dict):
        old_dict = self.ip_dict
        self.ip_dict = in_dict
        old_keys = set(old_dict.keys())
        new_keys = set(self.ip_dict.keys())
        for del_key in old_keys - new_keys:
            self.log("removing ip %s from lut" % (del_key))
            machine.del_lut_key(self, del_key)
        for new_key in new_keys - old_keys:
            self.log("adding ip %s to lut" % (new_key))
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
        self.set_recv_req_state()
        if not self.device.uuid:
            self.device.uuid = str(uuid.uuid4())
            self.log("setting uuid to %s" % (self.device.uuid))
        machine.add_lut_key(self, self.device.uuid)
        self.device.save()
    # machine related
    def set_maint_ip(self, ip=None):
        if ip:
            if self.maint_ip and (self.maint_ip.ip != ip.ip or self.maint_ip.netdevice.macaddr != ip.netdevice.macaddr):
                self.log("Changing maintenance IP and MAC from %s (%s) [%s] to %s (%s) [%s] and setting node-flag" % (
                    self.maint_ip.ip,
                    self.maint_ip.get_hex_ip(),
                    self.maint_ip.netdevice.macaddr,
                    ip.ip,
                    ip.get_hex_ip(),
                    ip.netdevice.macaddr))
            else:
                self.log("Setting maintenance IP and MAC to %s (%s) [%s] and setting node-flag" % (
                    ip.ip,
                    ip.get_hex_ip(),
                    ip.netdevice.macaddr))
            self.maint_ip = ip
            self.is_node = True
        else:
            self.log("Clearing maintenance IP and MAC (and node-flag)")
            self.maint_ip = None
            self.is_node = False
    def get_bnd(self):
        return self.__bnd
    def set_bnd(self, val):
        if val is None:
            self.log("clearing bootnetdevice")
            self.__bnd = val
        else:
            self.log("chaning bootnetdevice_name from '%s' to '%s'" % (self.__bnd.devname if self.__bnd else "unset", val))
            self.__bnd = val
    bootnetdevice = property(get_bnd, set_bnd)
    def get_sip_d(self):
        return self.__srv_ip_dict
    def set_sip_d(self, val):
        self.__srv_ip_dict = val
        if val is not None:
            self.log("Found %s:" % (logging_tools.get_plural("valid device->server ip-mapping", len(val.keys()))))
            for my_ip, s_ip in val.iteritems():
                self.log("  %-15s -> %-15s [%s]" % (my_ip, s_ip["ip"], s_ip["identifier"]))
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
            # get hopcount
            my_hc = hopcount.objects.filter(
                Q(s_netdevice__in=machine.process.sc.netdevice_idx_list) &
                Q(d_netdevice__in=nd_list)).order_by("value")
            for _ in my_hc:
                srv_dev, mach_dev = (machine.process.sc.nd_lut[_.s_netdevice_id], nd_lut[_.d_netdevice_id])
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
                        #ip_dict[cur_ip.ip] = ip_dict
                        # not sure ...
                        ip_dict[cur_ip.ip] = cur_ip
            self.log("found %s: %s" % (logging_tools.get_plural("IP-address", len(ip_dict)),
                                       ", ".join(sorted(ip_dict.keys()))))
            link_array = []
            if self.get_etherboot_dir():
                link_array.extend([("d", self.get_etherboot_dir()),
                                   ("d", self.get_pxelinux_dir()),
                                   ("l", ("%s/%s" % (global_config["ETHERBOOT_DIR"], self.name), self.maint_ip.ip))])
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
            self.log("Cannot add device %s (empty ip_list -> cannot reach host)" % (self.name),
                     logging_tools.LOG_LEVEL_WARN)
            self.device.reachable = False
        self.set_ip_dict(ip_dict)
        self.server_ip_dict = server_ip_dict
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
    def show_boot_netdriver(self):#, driver="eepro100", ethtool_options=0, options=""):
        self.log("current boot_netdriver/ethtool_options/netdriver_options is '%s' / %d (%s) / '%s'" % (
            self.maint_ip.netdevice.driver,
            self.maint_ip.netdevice.ethtool_options,
            self.maint_ip.netdevice.ethtool_string(),
            self.maint_ip.netdevice.driver_options))
    def get_etherboot_dir(self):
        if self.maint_ip:
            return "%s/%s" % (global_config["ETHERBOOT_DIR"], self.maint_ip.ip)
        else:
            return None
    def get_pxelinux_dir(self):
        if self.maint_ip:
            return "%s/%s/pxelinux.cfg" % (global_config["ETHERBOOT_DIR"], self.maint_ip.ip)
        else:
            return None
    def get_config_dir(self):
        if self.maint_ip:
            return "%s/%s" % (global_config["CONFIG_DIR"], self.maint_ip.ip)
        else:
            return None
    def get_pxe_file_name(self):
        return "%s/pxelinux.0" % (self.get_etherboot_dir())
    def get_mboot_file_name(self):
        return "%s/mboot.c32" % (self.get_etherboot_dir())
    def get_net_file_name(self):
        return "%s/bootnet" % (self.get_etherboot_dir())
    def get_menu_file_name(self):
        return "%s/menu" % (self.get_etherboot_dir())
    def get_ip_file_name(self):
        return "%s/%s" % (self.get_pxelinux_dir(), self.maint_ip.get_hex_ip())
    def get_ip_mac_file_base_name(self):
        return "01-%s" % (self.maint_ip.netdevice.macaddr.lower().replace(":", "-"))
    def get_ip_mac_file_name(self):
        return "%s/%s" % (self.get_pxelinux_dir(), self.get_ip_mac_file_base_name())
    def set_recv_req_state(self, recv_state = "error not set", req_state="error not set"):
        self.device.recvstate, self.device.reqstate = (recv_state, req_state)
    def refresh_target_kernel(self, *args, **kwargs):
        if kwargs.get("refresh", True):
            self.refresh_device()
            self.check_network_settings()
        if self.is_node:
            if self.device.new_kernel:
                if not self.device.stage1_flavour:
                    self.device.stage1_flavour = "cpio"
                    self.log("setting stage1_flavour to '%s'" % (self.device.stage1_flavour))
                    self.device.save(update_fields=["stage1_flavour"])
                if not self.device.prod_link:
                    self.log("no production link set", logging_tools.LOG_LEVEL_WARN)
                    prod_net = None
                else:
                    prod_net = self.device.prod_link
                    self.log("production network is %s" % (unicode(prod_net)))
                if self.device.new_state:
                    new_kernel = self.device.new_kernel
                    new_state = self.device.new_state
                    self.log("refresh for target_state %s, kernel %s, stage1_flavour %s" % (
                        unicode(self.device.new_state),
                        unicode(new_kernel),
                        self.device.stage1_flavour
                    ))
                else:
                    self.log("no state set", logging_tools.LOG_LEVEL_WARN)
                    new_state, new_kernel = (None, None)
                pxe_file = self.get_pxe_file_name()
                net_file = self.get_net_file_name()
                if os.path.exists(pxe_file):
                    os.unlink(pxe_file)
                if new_state:
                    if new_kernel and new_state.prod_link:
                        if machine.process.server_ip:
                            self.write_kernel_config(
                                new_kernel)
                            pass
                        else:
                            self.log("no server_ip set", logging_tools.LOG_LEVEL_ERROR)
                    elif new_state.boot_local:
                        # boot localboot
                        self.write_localboot_config()
                    elif new_state.memory_test:
                        # memory test
                        self.write_memtest_config()
                    else:
                        self.log("cannot handle new_state '%s'" % (unicode(new_state)),
                                 logging_tools.LOG_LEVEL_ERROR)
            else:
                self.log("new_kernel not set", logging_tools.LOG_LEVEL_ERROR)
        else:
            self.log("not node", logging_tools.LOG_LEVEL_WARN)
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
    def write_memtest_config(self):
        pxe_dir = self.get_pxelinux_dir()
        if pxe_dir:
            if os.path.isdir(pxe_dir):
                self.clear_ip_mac_files()
                open(self.get_ip_file_name()    , "w").write("DEFAULT ../../images/memtest.bin\n")
                open(self.get_ip_mac_file_name(), "w").write("DEFAULT ../../images/memtest.bin\n")
                if (os.path.isdir(self.get_etherboot_dir())):
                    if global_config["PXEBOOT"]:
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
                if global_config["PXEBOOT"]:
                    open(self.get_pxe_file_name(), "w").write(self.__glob_config["PXELINUX_0"])
                else:
                    self.log("not PXEBOOT capable (PXELINUX_0 not found)", logging_tools.LOG_LEVEL_ERROR)
    def write_kernel_config(self, new_kernel):
        kern_dst_dir = self.get_etherboot_dir()
        if kern_dst_dir:
            if os.path.isdir(kern_dst_dir):
                for file_name in ["i", "k", "x"]:
                    fname = "%s/%s" % (kern_dst_dir, file_name)
                    if os.path.islink(fname):
                        os.unlink(fname)
                for stage_name in ["stage2", "stage3"]:
                    stage_source = "%s/lcs/%s" % (global_config["CLUSTER_DIR"], 
                                                  stage_name)
                    stage_dest  ="%s/%s" % (kern_dst_dir, stage_name)
                    if not os.path.isfile(stage_source):
                        self.log("Error, cannot find %s_source '%s'..." % (stage_name, stage_source))
                    elif not os.path.isfile(stage_dest) or (os.path.isfile(stage_dest) and (os.stat(stage_source)[stat.ST_MTIME] > os.stat(stage_dest)[stat.ST_MTIME]) or os.stat(stage_source)[stat.ST_SIZE] != os.stat(stage_dest)[stat.ST_SIZE]):
                        self.log("Copying %s from %s to %s ..." % (stage_name, stage_source, stage_dest))
                        open(stage_dest, "w").write(open(stage_source, "r").read())
                #print kernel_stuff
                kern_base_dir = "../../kernels/%s" % (new_kernel.name)
                kern_abs_base_dir = "%s/kernels/%s" % (global_config["TFTP_DIR"], new_kernel.name)
                unlink_field = ["%s/k" % (kern_dst_dir),
                                "%s/i" % (kern_dst_dir),
                                "%s/x" % (kern_dst_dir)]
                valid_links = []
                if os.path.isdir(kern_abs_base_dir):
                    # check if requested flavour is ok
                    if not hasattr(new_kernel, "stage1_%s_present" % (self.device.stage1_flavour)):
                        self.log("requested stage1_flavour '%s' not known" % (
                            self.device.stage1_flavour),
                                 logging_tools.LOG_LEVEL_ERROR)
                    elif not getattr(new_kernel, "stage1_%s_present" % (self.device.stage1_flavour)):
                        self.log("requested stage1_flavour '%s' not present" % (
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
                        self.device.uuid,
                        self.device.kernel_append
                        )])).strip().replace("  ", " ").replace("  ", " ")
                self.clear_ip_mac_files([self.get_ip_mac_file_base_name()])
                if new_kernel.xen_host_kernel:
                    append_field = ["x dom0_mem=524288",
                                    "k console=tty0 ip=%s:%s::%s %s" % (self.maint_ip, s_ip, ipvx_tools.get_network_name_from_mask(s_netmask), append_string),
                                    "i"]
                else:
                    total_append_string = "initrd=i ip=%s:%s::%s %s" % (self.maint_ip.ip, machine.process.server_ip, ipvx_tools.get_network_name_from_mask(self.maint_ip.network.netmask), append_string)
                pxe_lines = []
                if global_config["NODE_BOOT_DELAY"]:
                    pxe_lines.extend(["TIMEOUT %d" % (global_config["NODE_BOOT_DELAY"]),
                                      "PROMPT 1"])
                pxe_lines.extend(["DISPLAY menu",
                                  "DEFAULT linux auto"])
                if new_kernel.name:
                    if new_kernel.xen_host_kernel:
                        pxe_lines.extend(["LABEL linux",
                                          "    KERNEL mboot.c32",
                                          "    APPEND %s" % (" --- ".join(append_field))])
                    else:
                        pxe_lines.extend(["LABEL linux",
                                          "    KERNEL k",
                                          "    APPEND %s" % (total_append_string)])
                pxe_lines.extend([""])
                if global_config["FANCY_PXE_INFO"]:
                    menu_lines = ["\x0c\x0f20%s\x0f07" % (("init.at Bootinfo, %s%s" % (time.ctime(), 80 * " "))[0:79])]
                else:
                    menu_lines = ["",
                                  ("init.at Bootinfo, %s%s" % (time.ctime(), 80 * " "))[0:79]]
                menu_lines.extend(["Nodename  , IP : %-30s, %s" % (self.device.name, self.maint_ip.ip),
                                   "Servername, IP : %-30s, %s" % (global_config["SERVER_SHORT_NAME"], machine.process.server_ip),
                                   "Netmask        : %s (%s)" % (self.maint_ip.network.netmask, ipvx_tools.get_network_name_from_mask(self.maint_ip.network.netmask)),
                                   "MACAddress     : %s" % (self.bootnetdevice.macaddr.lower()),
                                   "Stage1 flavour : %s" % (self.device.stage1_flavour),
                                   "Kernel to boot : %s" % (new_kernel.name or "<no kernel set>"),
                                   "device UUID    : %s" % (self.device.uuid),
                                   "Kernel options : %s" % (append_string or "<none set>"),
                                   "will boot %s" % ("in %s" % (logging_tools.get_plural("second", int(global_config["NODE_BOOT_DELAY"] / 10))) if global_config["NODE_BOOT_DELAY"] else "immediately"),
                                   "",
                                   ""])
                open(self.get_ip_file_name()    , "w").write("\n".join(pxe_lines))
                open(self.get_ip_mac_file_name(), "w").write("\n".join(pxe_lines))
                open(self.get_menu_file_name()  , "w").write("\n".join(menu_lines))
                if new_kernel.xen_host_kernel:
                    if self.__glob_config["XENBOOT"]:
                        open(self.get_mboot_file_name(), "w").write(self.__glob_config["MBOOT.C32"])
                    else:
                        self.log("not XENBOOT capable (MBOOT.C32 not found)", logging_tools.LOG_LEVEL_ERROR)
                if global_config["PXEBOOT"]:
                    open(self.get_pxe_file_name(), "w").write(global_config["PXELINUX_0"])
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
    def read_dot_files(self):
        if not self.is_node:
            self.log("not node, checking network settings", logging_tools.LOG_LEVEL_WARN)
            self.refresh_device()
            self.check_network_settings()
        if self.is_node:
            c_dir = self.get_config_dir()
            self.log("starting readdots in dir '%s'" % (c_dir))
            hlist = [(".version"  , "imageversion"       , None             ),
                     (".imagename", "actimage"           , None             ),
                     (".imagename", "act_image"          , "image"          ),
                     (".kernel"   , "actkernel"          , None             ),
                     (".kernel"   , "act_kernel"         , "kernel"         ),
                     (".kversion" , "kernelversion"      , None             ),
                     (".parttype" , "act_partition_table", "partition_table"),
                     (None        , "act_kernel_build"   , None             )]
            
            s_list = []
            num_tried, num_ok, num_found = (0, 0, 0)
            for file_name, dbentry, obj_name in hlist:
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
                            if obj_name:
                                set_obj = gobals()[obj_name].objects.get(Q(name=line))
                                print set_obj
    ##                            self.__dc.execute("SELECT x.%s_idx FROM %s x WHERE x.name=%%s" % (orig_db, orig_db), line)
    ##                            if self.__dc.rowcount:
    ##                                line = int(self.__dc.fetchone()["%s_idx" % (orig_db)])
    ##                            else:
    ##                                line = 0
                            print dbentry, line
                            #if act_conf[dbentry] != line:
                            #    act_conf[dbentry] = line
                            #    s_list.append((dbentry, line))
            # dirty hack
##            if act_conf["act_kernel"] and act_conf["actkernel"] and act_conf["kernelversion"]:
##                if re.match("^(\d+)\.(\d+)$", act_conf["kernelversion"]):
##                    mach_struct.log(" - dirty hack to guess act_kernel_build (act_kernel %d, act_version %s)" % (act_conf["act_kernel"], act_conf["kernelversion"]))
##                    self.__dc.execute("SELECT kernel_build_idx FROM kernel_build WHERE kernel=%d AND version=%d AND `release`=%d" % (act_conf["act_kernel"],
##                                                                                                                                    int(act_conf["kernelversion"].split(".")[0]),
##                                                                                                                                    int(act_conf["kernelversion"].split(".")[1])))
##                    if self.__dc.rowcount:
##                        line = self.__dc.fetchone()["kernel_build_idx"]
##                        if act_conf["act_kernel_build"] != line:
##                            s_list.append(("act_kernel_build", line))
##                else:
##                    mach_struct.log("cannot parse kernelversion '%s'" % (act_conf["kernelversion"]), logging_tools.LOG_LEVEL_ERROR)
            if s_list:
                self.__dc.execute("UPDATE device SET %s WHERE name=%%s" % (", ".join(["%s=%%s" % (x) for x, y in s_list])), tuple([y for x, y in s_list] + [mach_struct.name]))
            num_changed = len(s_list)
            self.log("readdots finished (%d tried, %d found, %d ok, %d changed%s)" % (
                num_tried,
                num_found,
                num_ok,
                num_changed,
                (num_changed and " [%s]" % (", ".join(["%s=%s" % (x, str(y)) for x, y in s_list])) or "")))
    def handle_mac_command(self, com_name):
        self.refresh_device()
        self.check_network_settings()
        if self.maint_ip:
            ip_to_write, ip_to_write_src = (self.maint_ip.ip, "maint_ip")
        elif self.bootnetdevice and self.bootnetdevice.dhcp_device:
            # FIXME
            if len(mach.ip_dict.keys()) == 1:
                ip_to_write, ip_to_write_src = (mach.ip_dict.keys()[0], "first ip of ip_dict.keys()")
            else:
                ip_to_write, ip_to_write_src = (None, "")
        else:
            ip_to_write, ip_to_write_src = (None, "")
        om_shell_coms, err_lines = ([], [])
        if com_name == "alter":
            if self.device.dhcp_written:
                if self.device.dhcp_write and ip_to_write:
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
        for om_shell_com in om_shell_coms:
            om_array = ['server 127.0.0.1',
                        'port 7911',
                        'connect',
                        'new host',
                        'set name = "%s"' % (self.device.name)]
            if om_shell_com == "write":
                om_array.extend(['set hardware-address = %s' % (self.device.bootnetdevice.macaddr),
                                 'set hardware-type = 1',
                                 'set ip-address=%s' % (self.maint_ip.ip)])
                om_array.extend(['set statements = "'+
                                 'supersede host-name = \\"%s\\" ;' % (self.device.name)+
                                 'if substring (option vendor-class-identifier, 0, 9) = \\"PXEClient\\" { '+
                                 'filename = \\"etherboot/%s/pxelinux.0\\" ; ' % (ip_to_write)+
                                 '} "'])
                om_array.append('create')
            elif om_shell_com == "delete":
                om_array.extend(['open',
                                 'remove'])
            simple_command.process.set_check_freq(200)
            simple_command("echo -e '%s' | /usr/bin/omshell" % ("\n".join(om_array)),
                           done_func=self.omshell_done,
                           stream_id="mac",
                           short_info=True,
                           add_info="omshell %s" % (com_name),
                           log_com=self.log,
                           info=om_shell_com)
    def omshell_done(self, om_sc):
        cur_out = om_sc.read()
        self.log("omshell finished with state %d (%d bytes)" % (om_sc.result,
                                                                len(cur_out)))
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
                    self.log("an error occured: %s (%s, %s)" % (line,
                                                                err_m.group("what"),
                                                                err_m.group("why")),
                             logging_tools.LOG_LEVEL_ERROR)
        update_obj = False
        if error_str:
            if error_str in ["key conflict", "not found"]:
                new_dhcp_written = False
            elif error_str in ["already exists"]:
                new_dhcp_written = True
            else:
                # unknown
                new_dhcp_written = None
        else:
            if om_sc.info == "write":
                new_dhcp_written = True
            elif om_sc.info == "delete":
                new_dhcp_written = False
        if new_dhcp_written is None:
            new_dhcp_written = self.device.dhcp_written
        # selective update
        self.log("storing state to db: dhcp_written=%s, dhcp_error='%s'" % (new_dhcp_written, error_str))
        self.device.dhcp_written = new_dhcp_written
        self.device.dhcp_error = error_str
        self.device.save(update_fields=["dhcp_written", "dhcp_error"])
    def feed_dhcp(self, in_dict, in_line):
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
            # no change dhcp-server
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
            self.device.recvstate = "got IP-Address via DHCP"
            change_fields.add("recvstate")
            if change_fields:
                self.device.save(update_fields=list(change_fields))
            if self.device.new_state:
                self.refresh_target_kernel(refresh=False)
    def nodeinfo(self, in_text, instance):
        self.log("got '%s' from %s" % (in_text, instance))
        return "ok got it"
         
class hm_icmp_protocol(icmp_twisted.icmp_protocol):
    def __init__(self, tw_process, log_template):
        self.__log_template = log_template
        icmp_twisted.icmp_protocol.__init__(self)
        self.__work_dict, self.__seqno_dict = ({}, {})
        self.__twisted_process = tw_process
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
        self.log("ping to %s (%d, %.2f) [%s]" % (target, num_pings, timeout, seq_str))
        cur_time = time.time()
        self[seq_str] = {"host"       : target,
                         "num"        : num_pings,
                         "timeout"    : timeout,
                         "start"      : cur_time,
                         "id"         : kwargs.get("id", ""),
                         # time between pings
                         "slide_time" : 0.1,
                         "sent"       : 0,
                         "recv_ok"    : 0,
                         "recv_fail"  : 0,
                         "error_list" : [],
                         "sent_list"  : {},
                         "recv_list"  : {}}
        self._update()
    def _update(self):
        cur_time = time.time()
        del_keys = []
        #pprint.pprint(self.__work_dict)
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
                        reactor.callLater(value["slide_time"] + 0.001, self._update)
                        reactor.callLater(value["timeout"] + value["slide_time"] * value["num"] + 0.001, self._update)
            # check for timeout
            for seq_to in [s_key for s_key, s_value in value["sent_list"].iteritems() if abs(s_value - cur_time) > value["timeout"] and s_key not in value["recv_list"]]:
                value["recv_fail"] += 1
                value["recv_list"][seq_to] = None
            # check for ping finish
            if value["error_list"] or (value["sent"] == value["num"] and value["recv_ok"] + value["recv_fail"] == value["num"]):
                all_times = [value["recv_list"][s_key] - value["sent_list"][s_key] for s_key in value["sent_list"].iterkeys() if value["recv_list"].get(s_key, None) != None]
                self.__twisted_process.send_ping_result(key, value)#["sent"], value["recv_ok"], all_times, ", ".join(value["error_list"]))
                del_keys.append(key)
        for del_key in del_keys:
            del self[del_key]
        #pprint.pprint(self.__work_dict)
    def received(self, dgram):
        if dgram.packet_type == 0 and dgram.ident == self.__twisted_process.pid & 0x7fff:
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

class twisted_process(threading_tools.process_obj):
    def process_init(self):
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context)
        #self.__relayer_socket = self.connect_to_socket("internal")
        my_observer = logging_tools.twisted_log_observer(global_config["LOG_NAME"],
                                                         global_config["LOG_DESTINATION"],
                                                         zmq=True,
                                                         context=self.zmq_context)
        log.startLoggingWithObserver(my_observer, setStdout=False)
        self.twisted_observer = my_observer
        # clear flag for extra twisted thread
        self.__extra_twisted_threads = 0
        self.icmp_protocol = hm_icmp_protocol(self, self.__log_template)
        try:
            reactor.listenWith(icmp_twisted.icmp_port, self.icmp_protocol)
        except CannotListenError:
            self.log("cannot listen on ICMP socket: %s" % (process_tools.get_except_info()),
                     logging_tools.LOG_LEVEL_ERROR)
            self.send_pool_message("process_exception", process_tools.get_except_info())
        else:
            self.register_func("ping", self._ping)
            self._ping("qweqwe", "127.0.0.1", 4, 5.0)
        self.control_socket = self.connect_to_socket("control")
    def _ping(self, *args, **kwargs):
        self.icmp_protocol.ping(*args, **kwargs)
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)
    def send_result(self, src_id, srv_com, data):
        print "sr", src_id, srv_com, data
        #self.send_to_socket(self.__relayer_socket, ["twisted_result", src_id, srv_com, data])
    def send_ping_result(self, *args):
        self.send_to_socket(self.control_socket, ["ping_result"] + list(args))
        #self.send_to_socket(self.__relayer_socket, ["twisted_ping_result"] + list(args))
    def loop_post(self):
        self.twisted_observer.close()
        self.control_socket.close()
        self.__log_template.close()
        #self.__relayer_socket.close()

class node_control_process(threading_tools.process_obj):
    def process_init(self):
        #, config, db_con, **args):
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
        # create connection to twisted process
        self.twisted_socket = self.connect_to_socket("twisted")
        machine.setup(self)
        machine.sync()
        self.register_func("refresh", self._refresh)
        self.register_func("alter_macaddr", self.alter_macaddr)
        self.register_func("ping_result", self._ping_result)
        self.register_timer(self._check_commands, 10)
        #self.kernel_dev = config_tools.server_check(server_type="kernel_server")
        self.register_func("syslog_line", self._syslog_line)
        self.register_func("status", self._status)
        self.register_func("nodeinfo", self._nodeinfo)
        # build dhcp res
        self.__dhcp_res = {
            "discover" : re.compile("(?P<program>\S+): DHCPDISCOVER from (?P<macaddr>\S+) via .*$"),
            "offer"    : re.compile("^(?P<program>\S+): DHCPOFFER on (?P<ip>\S+) to (?P<macaddr>\S+) via .*$"),
            "request"  : re.compile("^(?P<program>\S+): DHCPREQUEST for (?P<ip>\S+) .*from (?P<macaddr>\S+) via .*$"),
            "answer"   : re.compile("^(?P<program>\S+): DHCPACK on (?P<ip>\S+) to (?P<macaddr>\S+) via .*$")}
        self.pending_list = []
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)
    def _refresh(self, *args, **kwargs):
        if len(args):
            id_str, in_com = args
            in_com = server_command.srv_command(source=in_com)
            dev_list = map(lambda x: int(x), in_com.xpath(None, ".//ns:device/@pk"))
            machine.iterate("refresh_target_kernel", device_keys=dev_list)
            machine.iterate("read_dot_files", device_keys=dev_list)
        else:
            id_str, in_com = (None, None)
            # use kwargs to specify certain devices
            machine.iterate("refresh_target_kernel")
            machine.iterate("read_dot_files")
        if id_str:
            self.send_pool_message("send_return", id_str, unicode(in_com))
    def _status(self, zmq_id, in_com, *args, **kwargs):
        self.log("got status from id %s" % (zmq_id))
        in_com = server_command.srv_command(source=in_com)
        in_com["command"].attrib["zmq_id"] = zmq_id
        machine.ping(in_com)
        self.pending_list.append(in_com)
        #self.send_pool_message("send_return", zmq_id, unicode(in_com))
    def _ping_result(self, id_str, res_dict, **kwargs):
        new_pending = []
        for cur_com in self.pending_list:
            if len(cur_com.xpath(None, ".//ns:ping[text() = '%s']" % (id_str))):
                machine.interpret_result(cur_com, id_str, res_dict)
                if not cur_com.xpath(None, ".//ns:ping_list"):
                    machine.iterate_xml(cur_com, "add_ping_info")
                    self.send_pool_message("send_return", cur_com.xpath(None, ".//ns:command/@zmq_id")[0], unicode(cur_com))
                else:
                    new_pending.append(cur_com)
            else:
                new_pending.append(cur_com)
        self.pending_list = new_pending
    def _nodeinfo(self, id_str, node_text, **kwargs):
        node_id, instance = id_str.split(":", 1)
        cur_dev = machine.get_device(node_id)
        if cur_dev:
            ret_str = cur_dev.nodeinfo(node_text, instance)
        else:
            ret_str = "error no node with id '%s' found" % (node_id)
        self.send_pool_message("send_return", id_str, ret_str)
    def loop_post(self):
        machine.shutdown()
        self.twisted_socket.close()
        self.__log_template.close()
    def set_check_freq(self, cur_to):
        self.log("changing check_freq of check_commands to %d msecs" % (cur_to))
        self.change_timer(self._check_commands, cur_to)
    def _check_commands(self):
        simple_command.check()
        if simple_command.idle():
            self.set_loop_timer(1000)
    def _remove_macadr(self, machdat):
        # removes macadr from dhcp-server
        om_shell_coms = ["delete"]
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
                om_array.extend(['set statements = "'+
                                 'supersede host-name = \\"%s\\" ;' % (machdat["name"])+
                                 'if substring (option vendor-class-identifier, 0, 9) = \\"PXEClient\\" { '+
                                 'filename = \\"etherboot/%s/pxelinux.0\\" ; ' % (machdat["ip"])+
                                 '} "'])
                om_array.append('create')
            elif om_shell_com == "delete":
                om_array.extend(['open',
                                 'remove'])
            else:
                self.log("Internal error: Unknown om_shell command %s" % (om_shell_com), logging_tools.LOG_LEVEL_ERROR)
            #print om_array
            self.log("starting omshell for command %s" % (om_shell_com))
            (errnum, outstr) = commands.getstatusoutput("echo -e '%s' | /usr/bin/omshell" % ("\n".join(om_array)))
            self.log("got (%d) %s" % (errnum, logging_tools.get_plural("line", len(outstr.split("\n")))))
    def alter_macaddr(self, *args, **kwargs):
        if len(args):
            id_str, in_com = args
            in_com = server_command.srv_command(source=in_com)
            dev_list = in_com.xpath(None, ".//ns:device/@name")
            #print dev_list
            self._adw_macaddr("alter", nodes=dev_list)
            self.send_pool_message("send_return", id_str, unicode(in_com))
        else:
            self._adw_macaddr("alter")
    def _adw_macaddr(self, com_name, *args, **kwargs):
        #print "adw_macaddr", args, kwargs
        nodes = kwargs.get("nodes", machine.get_all_names(node_type=["H"]))
        self.log("got %s command for %s%s" % (
            com_name,
            logging_tools.get_plural("node", len(nodes)),
            nodes and ": %s" % (logging_tools.compress_list(nodes)) or ""))
        empty_result = True
        # additional flags 
        add_flags = []
        for mach_name in nodes:
            cur_dev = machine.get_device(mach_name)
            print "***", mach_name, cur_dev, type(cur_dev)
            cur_dev.handle_mac_command(com_name)
            #dhcp_written, dhcp_write, dhcp_last_error = (
            #    cur_dev.dhcp_wrmachdat["dhcp_written"], machdat["dhcp_write"], machdat["dhcp_error"])
            # list of om_shell commands
            #print mach.name, com_name, force_flag, dhcp_write, dhcp_written
            # try to determine om_shell_coms
            # global success of all commands
            #print om_array
            continue
            mach.log("starting omshell for command %s (%s)" % (om_shell_com,
                                                               ip_to_write and "ip %s from %s" % (ip_to_write, ip_to_write_src) or "no ip"))
            (errnum, outstr) = commands.getstatusoutput("echo -e '%s' | /usr/bin/omshell" % ("\n".join(om_array)))
            #print errnum, outstr
            if errnum == 0:
                for line in [x.strip()[2:].strip() for x in outstr.split("\n") if x.strip().startswith(">")]:
                    if len(line):
                        if not line.startswith(">") and not line.startswith("obj:"):
                            omm = self.__om_error_re.match(line)
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
                mach.log("omshell for command %s returned error %s (%s)" % (om_shell_com, errline, errstr), logging_tools.LOG_LEVEL_ERROR)
                mach.log("error: %s" % (errline), logging_tools.LOG_LEVEL_ERROR)
            else:
                mach.log("finished omshell for command %s successfully" % (om_shell_com))
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
                dev_sql_fields["dhcp_written"] = dhcp_written
            if dhcp_write:
                dhw_0 = "write"
            else:
                dhw_0 = "no write"
            if dhcp_written:
                dhw_1 = "written"
            else:
                dhw_1 = "not written"
            mach.log("dhcp_info: %s/%s, mac-address is %s" % (dhw_0, dhw_1, machdat["macadr"]))
            if not om_shell_coms:
                om_shell_coms = ["<nothing>"]
            dhcp_act_error = loc_result
            if dhcp_act_error != dhcp_last_error:
                dev_sql_fields["dhcp_error"] = dhcp_act_error
            mach.log("dhcp command(s) %s (om: %s) result: %s" % (com_name,
                                                                 ", ".join(om_shell_coms),
                                                                 loc_result))
            all_rets_dict[machdat["name"]] = loc_result
            if dev_sql_fields:
                dev_sql_keys = dev_sql_fields.keys()
                sql_str, sql_tuple = ("UPDATE device SET %s WHERE name=%%s" % (", ".join(["%s=%%s" % (x) for x in dev_sql_keys])),
                                      tuple([dev_sql_fields[x] for x in dev_sql_keys] + [mach.name]))
                dc.execute(sql_str, sql_tuple)
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
                self.log("got %s for unknown ip %s" % (in_dict["key"],
                                                       in_dict["ip"]), logging_tools.LOG_LEVEL_WARN)
                ip_dev = None
            else:
                if ip_dev.bootserver:
                    if ip_dev.bootserver.pk == self.sc.effective_device.pk:
                        boot_dev = machine.get_device(ip_dev.name)
                        boot_dev.log("parsed: %s" % (", ".join(["%s=%s" % (key, in_dict[key]) for key in sorted(in_dict.keys())])))
                        boot_dev.feed_dhcp(in_dict, in_line)
                    else:
                        self.log("got request %s for %s, not responsible" % (in_dict["key"],
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
                            machine.get_device(greedy_devs[0].name).feed_dhcp(in_dict, in_line)
                    else:
                        all_greedy_devs = device.objects.filter(Q(dhcp_mac=True)).select_related("bootnetdevice").order_by("name")
                        if all_greedy_devs:
                            self.log("found %s but none related to me" % (logging_tools.get_plural("greedy device", len(all_greedy_devs))), logging_tools.LOG_LEVEL_WARN)
                        else:
                            self.log("no greedy devices found for MAC-address %s or not responsible" % (in_dict["macaddr"]))
                else:
                    # reject entry because we are unable to answer the DHCP-Request
                    macbootlog(
                        entry_type=in_dict["key"],
                        ip_action="REJECT",
                        macaddr=in_dict["macaddr"].lower()
                    ).save()
                    # FIXME
                    self.log("FIXME, handling of DHCP-requests", logging_tools.LOG_LEVEL_ERROR)
##                    dc.execute("INSERT INTO macbootlog VALUES(0, %s, %s, %s, %s, %s, null)", (0, sm_type, "REJECT", mac, self.__loc_config["LOG_SOURCE_IDX"]))
##                    self.log("DHCPDISCOVER for macadr %s (device %s%s, %s%s): address already used" % (
##                        mac,
##                        mac_entry["name"],
##                        mac_entry["dhcp_mac"] and "[is greedy]" or "",
##                        mac_entry["devname"],
##                        mac_entry["netdevice_idx"] == mac_entry["bootnetdevice"] and "[is bootdevice]" or "[is not bootdevice]"))
##                    if mac_entry["netdevice_idx"] != mac_entry["bootnetdevice"]:
##                        dc.execute("INSERT INTO macbootlog VALUES(0, %s, %s, %s, %s, %s, null)", (0, sm_type, "MODIFY", mac, self.__loc_config["LOG_SOURCE_IDX"]))
##                        self.log("deleting macadr of netdevice %s on device %s (%s)" % (mac_entry["devname"],
##                                                                                        mac_entry["name"],
##                                                                                        mac))
##                        dc.execute("UPDATE netdevice SET macadr='00:00:00:00:00:00' WHERE netdevice_idx=%d" % (mac_entry["netdevice_idx"]))
##                        self._remove_macadr({"name"   : mac_entry["name"],
##                                             "ip"     : "",
##                                             "macadr" : mac})
##                    else:
##                        dc.execute("INSERT INTO macbootlog VALUES(0, %s, %s, %s, %s, %s, null)", (0, sm_type, "REJECT", mac, self.__loc_config["LOG_SOURCE_IDX"]))
            else:
                # discover request got an answer
                macbootlog(
                    entry_type=in_dict["key"],
                    ip_action="---",
                    macaddr=in_dict["macaddr"].lower()
                    ).save()
        else:
            # non-discover call, should have an ip-entry
            macbootlog(
                entry_type=in_dict["key"],
                device=ip_dev,
                ip_action=in_dict["ip"],
                macaddr=in_dict["macaddr"].lower()
                ).save()
        return
        dc = self.__db_con.get_connection(SQL_ACCESS)
        server_opts = s_com.get_option_dict()
        sm_type     = server_opts["sm_type"]
        ip          = server_opts["ip"]
        mac         = server_opts["mac"]
        full_string = server_opts["message"]
        mach_idx = 0
        if ip:
            if self.__ad_struct.has_key(ip):
                mach = self.__ad_struct[ip]
                mach.incr_use_count("syslog line")
        if sm_type == "DISCOVER":
            if re.match("^.*no free leases.*$", full_string):
                dc.execute("SELECT d.name, nd.devname, nd.netdevice_idx, d.bootserver, d.dhcp_mac, d.bootnetdevice FROM netdevice nd, device d WHERE nd.device=d.device_idx AND nd.macadr='%s'" % (mac))
                mac_list = dc.fetchall()
                if len(mac_list):
                    mac_entry = mac_list[0]
                    if mac_entry["bootserver"] and mac_entry["bootserver"] != self.__loc_config["MOTHER_SERVER_IDX"]:
                        # dhcp-DISCOVER request need not to be answered (other Server responsible)
                        dc.execute("INSERT INTO macbootlog VALUES(0, %s, %s, %s, %s, %s, null)", (0, sm_type, "OTHER", mac, self.__loc_config["LOG_SOURCE_IDX"]))
                        self.log("DHCPDISCOVER for macadr %s (device %s, %s): other bootserver (%d)" % (mac, mac_entry["name"], mac_entry["devname"], mac_entry["bootserver"]))
                    #else:
                    #    # dhcp-DISCOVER request can not be answered (macadress already used in DB)
                else:
                    pass
##                    dc.execute("SELECT nd.netdevice_idx, d.name, d.device_idx, d.bootserver FROM netdevice nd, device d WHERE d.dhcp_mac=1 AND d.bootnetdevice=nd.netdevice_idx AND nd.device=d.device_idx ORDER by d.name")
##                    ndidx_list = dc.fetchall()
##                    if len(ndidx_list):
##                        for nd in ndidx_list:
##                            if nd["bootserver"]:
##                                if nd["bootserver"] == self.__loc_config["MOTHER_SERVER_IDX"]:
##                                    ins_idx = nd["netdevice_idx"]
##                                    dev_name = nd["name"]
##                                    dc.execute("SELECT macadr FROM mac_ignore WHERE macadr='%s'" % (mac))
##                                    if dc.rowcount:
##                                        self.log("Ignoring MAC-Adress '%s' (in ignore-list)" % (mac))
##                                        dc.execute("INSERT INTO macbootlog VALUES (0, %s, %s, %s, %s, %s, null)", (0, sm_type, "IGNORELIST", mac, self.__loc_config["LOG_SOURCE_IDX"]))
##                                    else:
##                                        self.log("Setting bootmacaddress of device '%s' to '%s'" % (dev_name, mac))
##                                        dc.execute("UPDATE device SET dhcp_mac=0 WHERE name='%s'" % (dev_name))
##                                        dc.execute("UPDATE netdevice SET macadr='%s' WHERE netdevice_idx=%d" % (mac, ins_idx))
##                                        dc.execute("SELECT d.device_idx FROM device d WHERE d.name='%s'" % (dev_name))
##                                        didx = dc.fetchone()["device_idx"]
##                                        sql_str, sql_tuple = mysql_tools.get_device_log_entry_part(didx, self.__loc_config["NODE_SOURCE_IDX"], 0, self.__loc_config["LOG_STATUS"]["i"]["log_status_idx"], mac)
##                                        dc.execute("INSERT INTO devicelog VALUES(%s)" % (sql_str), sql_tuple)
##                                        self.get_thread_queue().put(("server_com", server_command.server_command(command="alter_macadr", nodes=[dev_name])))
##                                        # set the mac-address
##                                        dc.execute("INSERT INTO macbootlog VALUES(0, %s, %s, %s, %s, %s, null)", (nd["device_idx"], sm_type, "SET", mac, self.__loc_config["LOG_SOURCE_IDX"]))
##                                    break
##                                else:
##                                    self.log("Not responsible for device '%s' (ip %s); bootserver has idx %d" % (nd["name"], ip, nd["bootserver"]))
##                                    break
##                            else:
##                                self.log("Greedy device %s has no bootserver associated" % (nd["name"]), nd["name"])
##                    else:
##                        # ignore mac-address (no greedy devices)
##                        dc.execute("INSERT INTO macbootlog VALUES(0, %s, %s, %s, %s, %s, null)", (0, sm_type, "IGNORE", mac, self.__loc_config["LOG_SOURCE_IDX"]))
##                        self.log("No greedy devices found for MAC-Address %s" % (mac))
            else:
                # dhcp-DISCOVER request got an answer
                dc.execute("INSERT INTO macbootlog VALUES(0, %s, %s, %s, %s, %s, null)", (0, sm_type, "---", mac, self.__loc_config["LOG_SOURCE_IDX"]))
        else:
            # non dhcp-DISCOVER request
            dc.execute("INSERT INTO macbootlog VALUES(0, %s, %s, %s, %s, %s, null)", (mach_idx, sm_type, ip, mac, self.__loc_config["LOG_SOURCE_IDX"]))
        dc.release()
