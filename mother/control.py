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
import ipvx_tools
from django.db import connection
from twisted.internet import reactor
from twisted.python import log
from init.cluster.backbone.models import kernel, device, hopcount
from django.db.models import Q
import process_tools

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
        machine.__unique_keys = set()
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
    @staticmethod
    def get_device(dev_spec):
        return machine.__lut.get(dev_spec, None)
    @staticmethod
    def iterate(com_name, *args, **kwargs):
        for u_key in machine.__unique_keys:
            cur_dev = machine.get_device(u_key)
            if hasattr(cur_dev, com_name):
                cur_dev.log("call '%s'" % (com_name))
                getattr(cur_dev, com_name)(*args, **kwargs)
            else:
                cur_dev.log("call '%s' not defined" % (com_name), logging_tools.LOG_LEVEL_WARN)
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
                    srv_ips = list(set(machine.process.sc.identifier_ip_lut.get(cur_id, [])) & set(machine.process.sc.netdevice_ip_lut[srv_dev.pk]))
                    if srv_ips and not cur_ip.ip in server_ip_dict:
                        server_ip_dict[cur_ip.ip] = {"identifier" : cur_id,
                                                     "ip"         : srv_ips[0] if srv_ips else None}
                    if cur_id == "b" and srv_ips:
                        self.set_maint_ip(cur_ip)
                    if cur_ip.ip not in ip_dict:
                        ip_dict[cur_ip.ip] = ip_dict
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
        self.refresh_device()
        self.check_network_settings()
        if self.is_node:
            if self.device.new_kernel:
                if not self.device.stage1_flavour:
                    self.device.stage1_flavour = "cpio"
                    self.log("setting stage1_flavour to '%s'" % (self.device.stage1_flavour))
                    self.device.save()
                if not self.device.prod_link:
                    self.log("no production link set", logging_tools.LOG_LEVEL_WARN)
                    prod_net = None
                else:
                    prod_net = self.device.prod_link
                    self.log("production network is %s" % (unicode(prod_net)))
                if self.device.new_state:
                    new_kernel = self.device.new_kernel
                    new_state = self.device.new_state
                    self.log("refresh for target_state %s, kernel %s" % (unicode(self.device.new_state),
                                                                         unicode(new_kernel)))
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
                    elif not os.path.isfile(stage_dest) or (os.path.isfile(stage_dest) and os.stat(stage_source)[stat.ST_MTIME] > os.stat(stage_dest)[stat.ST_MTIME]):
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
                    if not getattr(new_kernel, "stage1_%s_present" % (self.device.stage1_flavour)):
                        self.log("requested stage1_flavour '%s' not present" % (self.device.stage1_flavour),
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
                if self.device.stage1_flavour == "cpio":
                    root_str = ""
                else:
                    root_str = "root=/dev/ram0"
                append_string = (" ".join([
                    root_str,
                    "init=/linuxrc rw nbd=%s,%s,%d,%s %s" % (self.bootnetdevice.devname,
                                                             self.bootnetdevice.driver,
                                                             self.bootnetdevice.ethtool_options,
                                                             self.bootnetdevice.driver_options.replace(" ", ur"§"),
                                                             self.device.kernel_append)])).strip().replace("  ", " ").replace("  ", " ")
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
    def ping(self, seq_str, target, num_pings, timeout):
        self.log("ping to %s (%d, %.2f) [%s]" % (target, num_pings, timeout, seq_str))
        cur_time = time.time()
        self[seq_str] = {"host"       : target,
                         "num"        : num_pings,
                         "timeout"    : timeout,
                         "start"      : cur_time,
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
                self.__twisted_process.send_ping_result(key, value["sent"], value["recv_ok"], all_times, ", ".join(value["error_list"]))
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
        reactor.listenWith(icmp_twisted.icmp_port, self.icmp_protocol)
        self.register_func("ping", self._ping)
        self._ping("qweqwe", "127.0.0.1", 4, 5.0)
    def _ping(self, *args, **kwargs):
        self.icmp_protocol.ping(*args)
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)
    def send_result(self, src_id, srv_com, data):
        print "sr", src_id, srv_com, data
        #self.send_to_socket(self.__relayer_socket, ["twisted_result", src_id, srv_com, data])
    def send_ping_result(self, *args):
        print args
        #self.send_to_socket(self.__relayer_socket, ["twisted_ping_result"] + list(args))
    def loop_post(self):
        self.twisted_observer.close()
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
        # close database connection
        connection.close()
        self.sc = config_tools.server_check(server_type="mother")
        if "b" in self.sc.identifier_ip_lut:
            self.server_ip = self.sc.identifier_ip_lut["b"][0]
            self.log("IP address in boot-net is %s" % (self.server_ip))
        else:
            self.server_ip = None
            self.log("no IP address in boot-net", logging_tools.LOG_LEVEL_ERROR)
        machine.setup(self)
        machine.sync()
        self.register_func("refresh", self._refresh)
        #self.kernel_dev = config_tools.server_check(server_type="kernel_server")
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)
    def _refresh(self, *args, **kwargs):
        # use kwargs to specify certain devices
        machine.iterate("refresh_target_kernel")
    def loop_post(self):
        machine.shutdown()
        self.__log_template.close()
