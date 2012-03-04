#!/usr/bin/python-init -Ot
#
# -*- coding: utf-8 -*-
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008,2009,2011 Andreas Lang-Nevyjel, init.at
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
""" machine information """

import sys
import os
import re
import time
import posix
from host_monitoring import limits
import pci_database
import cpu_database
import process_tools
import commands
from host_monitoring import hm_classes
import pprint
import logging_tools
import uuid_tools
import statvfs
import partition_tools
from lxml import etree
from lxml.builder import E
import argparse
import tempfile
import base64
import bz2
import server_command
import subprocess

nw_classes = ["ethernet", "network", "infiniband"]

class _general(hm_classes.hm_module):
    def init_module(self):
        self.local_lvm_info = partition_tools.lvm_struct("bin")
        self.disk_dict, self.vmstat_dict, self.disk_stat = ({}, {}, {})
        self.disk_dict_last_update = 0
        self.last_vmstat_time = None
    def _proc_stat_info(self, first_line=None):
        if first_line is None:
            first_line = open("/proc/stat").readline().strip().split()
        if len(first_line) >= 9:
            # kernel 2.5 and above with additional steal-value
            stat_list = frozenset(["user", "nice", "sys", "idle", "iowait", "irq", "softirq", "steal"])
            kernel = 26
        elif len(first_line) == 8:
            # kernel 2.5 and above
            stat_list = frozenset(["user", "nice", "sys", "idle", "iowait", "irq", "softirq"])
            kernel = 25
        else:
            # up to kernel 2.4
            stat_list = frozenset(["user", "nice", "sys", "idle"])
            kernel = 24
        self.stat_list, self.kernel = (stat_list, kernel)
        return stat_list
    def _rescan_valid_disk_stuff(self):
        self.log("checking valid block_device names and major numbers")
        valid_block_devs, valid_major_nums = ({}, {})
        try:
            block_devs_dict, block_part = ({}, False)
            block_ignore_list = ["loop", "ram", "ramdisk", "fd", "sr", "nbd"]
            for line in open("/proc/devices", "r").readlines():
                line = line.strip().lower()
                if line.startswith("block device"):
                    block_part = True
                elif block_part:
                    lp = line.split(None, 1)
                    if lp[0].isdigit() and lp[1] not in block_ignore_list:
                        block_devs_dict[int(lp[0])] = lp[1]
            block_dir = "/sys/block"
            if os.path.isdir(block_dir):
                for entry in os.listdir(block_dir):
                    dev_file = "%s/%s/dev" % (block_dir, entry)
                    if os.path.isfile(dev_file):
                        major, minor = [int(x) for x in open(dev_file, "r").read().strip().split(":")]
                        if block_devs_dict.has_key(major):
                            dev_name = entry.replace("!", "/")
                            valid_block_devs[dev_name] = major
                            valid_major_nums.setdefault(major, []).append(dev_name)
                            self.log("   adding %-14s (major %3d, minor %3d) to block_device_list" % (dev_name, major, minor))
                            #print dev_name, block_devs_dict[major], minor
        except:
            self.log("error in rescan_valid_disk_stuff: %s" % (process_tools.get_except_info()), logging_tools.LOG_LEVEL_CRITICAL)
        else:
            self.log("Found %s and %s: %s; %s" % (logging_tools.get_plural("device_name", len(valid_block_devs.keys())),
                                                  logging_tools.get_plural("major number", len(valid_major_nums.keys())),
                                                  ", ".join(valid_block_devs.keys()),
                                                  ", ".join(["%d" % (x) for x in valid_major_nums.keys()])))
        self.valid_block_devs, self.valid_major_nums = (valid_block_devs,
                                                        valid_major_nums)
    def init_machine_vector(self, mv):
        mv.register_entry("load.1"           , 0., "load average of the last $2 minute")
        mv.register_entry("load.5"           , 0., "load average of the last $2 minutes")
        mv.register_entry("load.15"          , 0., "load average of the last $2 minutes")
        mv.register_entry("mem.avail.phys"   , 0, "available physical memory"       , "Byte", 1024, 1024)
        mv.register_entry("mem.avail.swap"   , 0, "available swap memory"           , "Byte", 1024, 1024) 
        mv.register_entry("mem.avail.total"  , 0, "available total memory"          , "Byte", 1024, 1024) 
        mv.register_entry("mem.free.phys"    , 0, "free physical memory"            , "Byte", 1024, 1024)
        mv.register_entry("mem.free.phys.bc" , 0, "free physical memory without b+c", "Byte", 1024, 1024)
        mv.register_entry("mem.free.swap"    , 0, "free swap memory"                , "Byte", 1024, 1024)
        mv.register_entry("mem.free.total"   , 0, "free total memory"               , "Byte", 1024, 1024)
        mv.register_entry("mem.free.total.bc", 0, "free total memory without b+c"   , "Byte", 1024, 1024)
        mv.register_entry("mem.used.phys"    , 0, "used physical memory"            , "Byte", 1024, 1024)
        mv.register_entry("mem.used.phys.bc" , 0, "used physical memory with b+c"   , "Byte", 1024, 1024)
        mv.register_entry("mem.used.swap"    , 0, "used swap memory"                , "Byte", 1024, 1024)
        mv.register_entry("mem.used.total"   , 0, "used total memory"               , "Byte", 1024, 1024)
        mv.register_entry("mem.used.total.bc", 0, "used total memory with b+c"      , "Byte", 1024, 1024)
        mv.register_entry("mem.used.buffers" , 0, "memory used for buffers"         , "Byte", 1024, 1024)
        mv.register_entry("mem.used.cached"  , 0, "memory used for caches"          , "Byte", 1024, 1024)
        mv.register_entry("mem.used.shared"  , 0, "shared memory"                   , "Byte", 1024, 1024)
        # check for /proc/stat
        stat_list = self._proc_stat_info()
        for what in stat_list:
            mv.register_entry("vms.%s" % (what), 0., "percentage of time spent for $2 (total)", "%")
        self.cpu_list = []
        for stuff in [line.strip().split()[0] for line in file("/proc/stat", "r").readlines() if line.strip().startswith("cpu")]:
            if stuff != "cpu":
                self.cpu_list.append(stuff[3:])
        if not self.cpu_list:
            self.cpu_list = ["0"]
        if len(self.cpu_list) > 1:
            for cpu_idx in self.cpu_list:
                for what in stat_list:
                    mv.register_entry("vms.%s.p%s" % (what, cpu_idx), 0., "percentage of time spent for $2 on cpu %s" % (cpu_idx), "%")
        mv.register_entry("num.interrupts", 0, "number of interrupts per second"      , "1/s")
        mv.register_entry("num.context"   , 0, "number of context switches per second", "1/s")
        #mv.register_entry("blks.in"       , 0, "number of blocks read per second"     , "1/s")
        #mv.register_entry("blks.out"      , 0, "number of blocks written per second"  , "1/s")
        mv.register_entry("swap.in"       , 0, "number of swap pages brought in"      , "1/s")
        mv.register_entry("swap.out"      , 0, "number of swap pages brought out"     , "1/s")
        self._rescan_valid_disk_stuff()
    def _cpuinfo_int(self, srv_com):
        return cpu_database.global_cpu_info().get_send_dict(srv_com)
    def _load_int(self):
        return [float(x) for x in open("/proc/loadavg", "r").read().strip().split()[0:3]]
    def _mem_int(self):
        valid_keys = set(["MemTotal", "MemFree", "Buffers", "Cached", "SwapTotal", "SwapFree", "MemShared"])
        p_dict = dict([r_line.strip().split()[:2] for r_line in open("/proc/meminfo", "r").readlines() if r_line.strip().endswith("kB")])
        return dict([(key, int(p_dict.get("%s:" % (key), "0"))) for key in valid_keys])
    def _df_int(self, mvect=None):
        act_time, update_dict = (time.time(), False)
        if mvect or abs(self.disk_dict_last_update - act_time) > 90:
            update_dict = True
        if update_dict:
            self.disk_dict_last_update = act_time
            ram_match = re.compile("^.*/ram\d+$")
            smount_lines = [line.strip().split() for line in open("/etc/mtab", "r").readlines()]
            link_set, mount_list = (set(), [])
            for line in smount_lines:
                if line[2] not in ["none"] and line[0].startswith("/") and not ram_match.match(line[0]) and line[0].startswith("/dev/"):
                    mount_list.append(line)
                    if os.path.islink(line[0]):
                        link_set.add((os.path.normpath(os.path.join(os.path.dirname(line[0]),
                                                                    os.readlink(line[0]))),
                                      line[0]))
            #print self.disk_dict
            n_dict = {}
            for mnt in mount_list:
                try:
                    osres = os.statvfs(mnt[1])
                except:
                    pass
                else:
                    fact = float(osres[statvfs.F_FRSIZE]) / (1024.)
                    try:
                        blocks, bfree, bavail = int(osres[statvfs.F_BLOCKS]), int(osres[statvfs.F_BFREE]), int(osres[statvfs.F_BAVAIL])
                    except:
                        pass
                    else:
                        if blocks:
                            sizetot = blocks * fact
                            sizeused = (blocks - bfree) * fact
                            sizeavail = bavail * fact
                            sizefree = sizetot - sizeused
                            proc = int((100.*float(blocks - bfree)) / float(blocks - bfree + bavail))
                            n_dict[mnt[0]] = [mnt[1], proc, int(sizetot), int(sizeused), int(sizefree)]
            for link_dst, link_src in link_set:
                n_dict[link_dst] = n_dict[link_src]
        else:
            n_dict = self.disk_dict
        if mvect:
            # delete old keys
            for key in self.disk_dict:
                if key not in n_dict:
                    mvect.unregister_entry("df.%s.f" % (key))
                    mvect.unregister_entry("df.%s.u" % (key))
                    mvect.unregister_entry("df.%s.t" % (key))
            for key in n_dict:
                if key not in self.disk_dict:
                    mvect.register_entry("df.%s.f" % (key), 0., "free space on $2 (%s)" % (n_dict[key][0]), "Byte", 1000, 1000)
                    mvect.register_entry("df.%s.u" % (key), 0., "used space on $2 (%s)" % (n_dict[key][0]), "Byte", 1000, 1000)
                    mvect.register_entry("df.%s.t" % (key), 0., "size of $2 (%s)"       % (n_dict[key][0]), "Byte", 1000, 1000)
            self.disk_dict = n_dict
            for key in self.disk_dict:
                mvect["df.%s.f" % (key)] = self.disk_dict[key][4]
                mvect["df.%s.u" % (key)] = self.disk_dict[key][3]
                mvect["df.%s.t" % (key)] = self.disk_dict[key][2]
        else:
            return n_dict
    def _vmstat_int(self, mvect):
        act_time = time.time()
        # disk_stat format: device -> (sectors read/written, milliseconds spent read/written)
        stat_dict, disk_stat = ({}, {})
        for line in [cur_line.strip().split() for cur_line in open("/proc/stat", "r").readlines() if cur_line.strip()]:
            if line[0].startswith("cpu"):
                stat_dict[line[0]] = [long(x) for x in line[1:]]
            elif line[0] == "ctxt":
                stat_dict["ctxt"] = long(line[1])
            elif line[0] == "intr":
                stat_dict["intr"] = long(line[1])
            elif line[0] == "swap":
                stat_dict["swap"] = [long(line[1]), long(line[2])]
        if os.path.isfile("/proc/diskstats"):
            try:
                ds_dict = dict([(parts[2].strip(), [int(parts[0]), int(parts[1])] + [long(cur_val) for cur_val in parts[3:]]) for parts in [line.strip().split() for line in open("/proc/diskstats", "r").readlines()] if len(parts) == 14])# and y[2].strip() in self.valid_block_devs.keys()])
            except:
                pass
            else:
                # get list of mounts
                try:
                    mount_list = [line.strip().split()[0].split("/", 2)[2] for line in open("/proc/mounts", "r").readlines() if line.startswith("/dev")]
                except:
                    # cannot read, take all devs
                    mount_list = ds_dict.keys()
                else:
                    #print mount_list
                    pass
                # get unique devices
                ds_keys_ok_by_name = sorted([key for key in ds_dict.iterkeys() if key in self.valid_block_devs])
                # sort out partition stuff
                last_name = ""
                ds_keys_ok_by_major = []
                for d_name in sorted([key for key, value in ds_dict.iteritems() if value[0] in self.valid_major_nums.keys()]):
                    if last_name and not (d_name.startswith("dm-") or d_name.startswith("md")) and d_name.startswith(last_name):
                        pass
                    else:
                        ds_keys_ok_by_major.append(d_name)
                        last_name = d_name
                if ds_keys_ok_by_name != ds_keys_ok_by_major:
                    self._rescan_valid_disk_stuff(logger)
                    ds_keys_ok_by_major = ds_keys_ok_by_name
                    self.local_lvm_info.update()
                mounted_lvms = {}
                if self.local_lvm_info.lvm_present:
                    for loc_lvm_name, loc_lvm_info in self.local_lvm_info.lv_dict.get("lv", {}).iteritems():
                        lv_k_major, lv_k_minor = (int(loc_lvm_info["kernel_major"]),
                                                  int(loc_lvm_info["kernel_minor"]))
                        if lv_k_major in self.valid_major_nums.keys():
                            mount_dev = "%s/%s" % (loc_lvm_info["vg_name"],
                                                   loc_lvm_info["name"])
                            mounted_lvms[mount_dev] = "%s-%d" % (self.valid_major_nums[lv_k_major][0].split("-")[0], lv_k_minor)
                # problem: LVM devices are not handled properly
                dev_list = [ds_key for ds_key in ds_keys_ok_by_name if [True for m_entry in mount_list if m_entry.startswith(ds_key)]] + \
                           [value for key, value in mounted_lvms.iteritems() if key in mount_list]
                for dl in dev_list:
                    disk_stat[dl] = (ds_dict[dl][4],
                                     ds_dict[dl][8],
                                     ds_dict[dl][5],
                                     ds_dict[dl][9],
                                     ds_dict[dl][11])
                disk_stat["total"] = []
                for idx in range(5):
                    disk_stat["total"].append(sum([disk_stat[x][idx] for x in dev_list]))
                dev_list.append("total")
                unique_dev_list = dev_list
                #print "dd", dev_list, disk_stat
        #print dev_list, disk_stat
        #stat_dict["disk_io"] = [blks_read, blks_written]
        stat_d = {}
        if self.last_vmstat_time is not None:
            tdiff = act_time - self.last_vmstat_time
##            if self.mach_arch == "alpha":
##                vms_tdiff = tdiff * 1024. / 100.
##            else:
            vms_tdiff = tdiff
            if "ctxt" in stat_dict and "ctxt" in self.vmstat_dict:
                mvect["num.context"] = int((stat_dict["ctxt"] - self.vmstat_dict["ctxt"]) / tdiff)
            for cpu_str, name_p in [("cpu", "")] + ([("cpu%s" % (cpu_idx), ".p%s" % (cpu_idx)) for cpu_idx in self.cpu_list] if len(self.cpu_list) > 1 else []):
                if cpu_str in stat_dict and cpu_str in self.vmstat_dict:
                    for idx, name in enumerate(self.stat_list):
                        mvect["vms.%s%s" % (name, name_p)] = float(sub_wrap(stat_dict[cpu_str][idx], self.vmstat_dict[cpu_str][idx]) / vms_tdiff)
                else:
                    break
            if "intr" in stat_dict and "intr" in self.vmstat_dict:
                mvect["num.interrupts"] = int(sub_wrap(stat_dict["intr"], self.vmstat_dict["intr"]) / tdiff)
            if "swap" in stat_dict and "swap" in self.vmstat_dict:
                for name, idx in [("in", 0), ("out", 1)]:
                    mvect["swap.%s" % (name)] = int(sub_wrap(stat_dict["swap"][idx], self.vmstat_dict["swap"][idx]) / tdiff)
            #print unique_dev_list
            for act_disk in unique_dev_list:
                if not self.disk_stat.has_key(act_disk):
                    info_str = act_disk == "total" and "total" or "on /dev/$2"
                    mvect.register_entry("io.%s.blks.read" % (act_disk)   , 0 , "number of blocks read per second %s" % (info_str)   , "1/s")
                    mvect.register_entry("io.%s.blks.written" % (act_disk), 0 , "number of blocks written per second %s" % (info_str), "1/s")
                    mvect.register_entry("io.%s.time.read" % (act_disk)   , 0., "milliseconds spent reading %s" % (info_str)         , "s"  )
                    mvect.register_entry("io.%s.time.written" % (act_disk), 0., "milliseconds spent writing %s" % (info_str)         , "s"  )
                    mvect.register_entry("io.%s.time.io" % (act_disk)     , 0., "milliseconds spent doing IO %s" % (info_str)        , "s"  )
            for old_disk in self.disk_stat.keys():
                if not disk_stat.has_key(old_disk):
                    mvect.unregister_entry("io.%s.blks.read" % (old_disk))
                    mvect.unregister_entry("io.%s.blks.written" % (old_disk))
                    mvect.unregister_entry("io.%s.time.read" % (old_disk))
                    mvect.unregister_entry("io.%s.time.written" % (old_disk))
                    mvect.unregister_entry("io.%s.time.io" % (old_disk))
            for act_disk in [dev for dev in unique_dev_list if dev in self.disk_stat]:
                #print act_disk, disk_stat[act_disk]
                for idx, what in [(0, "read"), (1, "written")]:
                    mvect["io.%s.blks.%s" % (act_disk, what)] = int(sub_wrap(disk_stat[act_disk][idx], self.disk_stat[act_disk][idx]) / tdiff)
                for idx, what in [(2, "read"), (3, "written"), (4, "io")]:
                    mvect["io.%s.time.%s" % (act_disk, what)] = float(sub_wrap(disk_stat[act_disk][idx], self.disk_stat[act_disk][idx]) / (1000 * tdiff))
            self.vmstat_dict = stat_dict
            self.disk_stat = disk_stat
        else:
            tdiff = None
        self.last_vmstat_time = act_time
    def update_machine_vector(self, mv):
        try:
            load_list = self._load_int()
        except:
            load_list = [0., 0., 0.]
        mv["load.1"]  = load_list[0]
        mv["load.5"]  = load_list[1]
        mv["load.15"] = load_list[2]
        try:
            mem_list = self._mem_int()
        except:
            mv["mem.avail.phys"]    = 0
            mv["mem.avail.swap"]    = 0
            mv["mem.avail.total"]   = 0
            mv["mem.free.phys"]     = 0
            mv["mem.free.phys.bc"]  = 0
            mv["mem.free.swap"]     = 0
            mv["mem.free.total"]    = 0
            mv["mem.free.total.bc"] = 0
            mv["mem.used.phys"]     = 0
            mv["mem.used.phys.bc"]  = 0
            mv["mem.used.swap"]     = 0
            mv["mem.used.total"]    = 0
            mv["mem.used.total.bc"] = 0
            mv["mem.used.buffers"]  = 0
            mv["mem.used.cached"]   = 0
            mv["mem.used.shared"]   = 0
        else:
            mv["mem.avail.phys"]    = mem_list["MemTotal"]
            mv["mem.avail.swap"]    = mem_list["SwapTotal"]
            mv["mem.avail.total"]   = mem_list["MemTotal"]  + mem_list["SwapTotal"]
            mv["mem.free.phys"]     = mem_list["MemFree"]
            mv["mem.free.phys.bc"]  = mem_list["MemFree"]   + mem_list["Buffers"]   + mem_list["Cached"]
            mv["mem.free.swap"]     = mem_list["SwapFree"]
            mv["mem.free.total"]    = mem_list["MemFree"]   + mem_list["SwapFree"]
            mv["mem.free.total.bc"] = mem_list["MemFree"]   + mem_list["Buffers"]   + mem_list["Cached"]   + mem_list["SwapFree"]
            mv["mem.used.phys"]     = mem_list["MemTotal"]  - (mem_list["MemFree"]  + mem_list["Buffers"]  + mem_list["Cached"])
            mv["mem.used.phys.bc"]  = mem_list["MemTotal"]  - mem_list["MemFree"]
            mv["mem.used.swap"]     = mem_list["SwapTotal"] - mem_list["SwapFree"]
            mv["mem.used.total"]    = mem_list["MemTotal"]  + mem_list["SwapTotal"] - (mem_list["MemFree"] + mem_list["SwapFree"] + mem_list["Buffers"] + mem_list["Cached"])
            mv["mem.used.total.bc"] = mem_list["MemTotal"]  + mem_list["SwapTotal"] - (mem_list["MemFree"] + mem_list["SwapFree"])
            mv["mem.used.buffers"]  = mem_list["Buffers"]
            mv["mem.used.cached"]   = mem_list["Cached"]
            mv["mem.used.shared"]   = mem_list["MemShared"]
        try:
            self._df_int(mv)
        except:
            self.log("error calling _df_int(): %s" % (process_tools.get_except_info()), logging_tools.LOG_LEVEL_CRITICAL)
        try:
            self._vmstat_int(mv)
        except:
            self.log("error calling _vmstat_int(): %s" % (process_tools.get_except_info()), logging_tools.LOG_LEVEL_CRITICAL)
        #if self.__check_nameserver:
        #    self._check_nameserver_stats(logger, mv)
    def _partinfo_int(self):
        my_disk_lut = partition_tools.disk_lut()
        #IGNORE_LVM_PARTITIONS = False
        dev_dict, sys_dict = ({}, {})
        read_err_list = []
        try:
            mount_list = [x.strip().split() for x in open("/proc/mounts", "r").read().split("\n") if x.strip()]
        except:
            read_err_list.append("/proc/mounts")
        try:
            devices_list = [x.strip().split() for x in open("/proc/devices", "r").read().split("\n") if x.strip()]
        except:
            read_err_list.append("/proc/devices")
        try:
            fstab_list = [x.strip().split() for x in open("/etc/fstab", "r").read().split("\n") if x.strip()]
        except:
            read_err_list.append("/etc/fstab")
        try:
            parts_list = [y[0:4] for y in [x.strip().split() for x in open("/proc/partitions", "r").read().split("\n") if x.strip()] if len(y) >=4]
        except:
            read_err_list.append("/proc/partitions")
        try:
            real_root_dev = int(open("/proc/sys/kernel/real-root-dev", "r").read().strip())
        except:
            read_err_list.append("/proc/sys/kernel/real-root-dev")
        if read_err_list:
            ret_str = "error reading %s" % (" and ".join(read_err_list))
        else:
            ret_str = ""
            # build devices-dict
            while True:
                stuff = devices_list.pop(0)
                if stuff[0].lower().startswith("block"):
                    break
            devices_dict = dict([(int(x), y) for x, y in devices_list])
            #print devices_dict
            # build partition-dict
            part_dict, real_root_dev_name = ({}, None)
            for major, minor, blocks, part_name in parts_list:
                if major.isdigit() and minor.isdigit() and blocks.isdigit():
                    major = int(major)
                    minor = int(minor)
                    if major * 256 + minor == real_root_dev:
                        real_root_dev_name = part_name
                    blocks = int(blocks)
                    if not minor or not part_name[-1].isdigit():
                        dev_dict["/dev/%s" % (part_name)] = {}
                    part_dict.setdefault(major, {}).setdefault(minor, (part_name, blocks))
            if not real_root_dev_name and real_root_dev:
                real_root_list = [x[0] for x in mount_list if x[1] == "/" and x[0] != "rootfs"]
                if real_root_list:
                    real_root_dev = real_root_list[0]
                    if not real_root_dev.startswith("/"):
                        ret_str = "error determining real_root_device"
            if not real_root_dev_name:
                # try to get root-dev-name from /dev/root
                if os.path.islink("/dev/root"):
                    real_root_dev_name = os.readlink("/dev/root")
                    if real_root_dev_name.startswith("/dev/"):
                        real_root_dev_name = real_root_dev_name[5:]
            # still no real_root_dev_name: try /etc/mtab
            if not real_root_dev_name:
                if os.path.isfile("/etc/mtab"):
                    root_list = [parts[0] for parts in [line.split() for line in open("/etc/mtab", "r").read().split("\n") if line.strip()] if len(parts) > 2 and parts[1] == "/"]
                    if root_list:
                        real_root_dev_name = root_list[0]
                        if real_root_dev_name.startswith("/dev/"):
                            real_root_dev_name = real_root_dev_name[5:]
            if not ret_str:
                # partition lookup dict
                part_lut = {}
                # fetch fdisk information
                for dev in dev_dict.keys():
                    stat, out = commands.getstatusoutput("/sbin/fdisk -l %s" % (dev))
                    if stat:
                        ret_str = "error reading partition table of %s (%d): %s" % (dev, stat, out)
                        break
                    lines = [[z for z in [y.strip() for y in x.strip().split()] if z != "*"] for x in out.split("\n") if x.startswith(dev)]
                    for stuff in lines:
                        part    = stuff.pop(0)
                        start   = stuff.pop(0)
                        end     = stuff.pop(0)
                        size    = stuff.pop(0)
                        hextype = stuff.pop(0)
                        info = " ".join(stuff)
                        if size.endswith("+"):
                            size = size[:-1]
                        start = int(start)
                        end  = int(start)
                        size = int(size) / 1000
                        hextype = "0x%02x" % (int(hextype, 16))
                        part_num = part[len(dev):]
                        dev_dict[dev][part_num] = {"size"    : size,
                                                   "hextype" : hextype,
                                                   "info"    : info}
                        part_lut[part] = (dev, part_num)
                # kick empty devices
                empty_dev_list = [k for k, v in dev_dict.iteritems() if not v]
                for ed in empty_dev_list:
                    del dev_dict[ed]
                if not ret_str:
                    if not dev_dict:
                        # no device_dict up to now, maybe xen-machine, check part_dict
                        for major, m_stuff in part_dict.iteritems():
                            for minor, part_stuff in m_stuff.iteritems():
                                part_name, part_size = part_stuff
                                dev_name = part_name
                                while dev_name[-1].isdigit():
                                    dev_name = dev_name[:-1]
                                part_num = int(part_name[len(dev_name):])
                                dev_name = "/dev/%s" % (dev_name)
                                if not dev_dict.has_key(dev_name):
                                    dev_dict[dev_name] = {}
                                dev_dict[dev_name]["%d" % (part_num)] = {"size"    : part_size / 1024,
                                                                         "hextype" : "0x00",
                                                                         "info"    : ""}
                                part_lut["/dev/%s" % (part_name)] = (dev_name, "%d" % (part_num))
                    # automount mointpoints
                    auto_mps = []
                    # drop unneeded entries
                    real_mounts, sys_mounts = ([], [])
                    parts_found = []
                    for part, mp, fstype, opts, dump, fsck in mount_list:
                        # rewrite from by-id to real device
                        if part.count("by-id"):
                            part = os.path.normpath(os.path.join(part, "..", os.readlink(part)))
                        if part not in parts_found:
                            parts_found.append(part)
                            if fstype in ["subfs", "autofs"]:
                                pass
                            elif part == "rootfs" or part.startswith("automount(") or part.count(":"):
                                if part.startswith("automount("):
                                    auto_mps.append(mp)
                            else:
                                if part == "/dev/root":
                                    part = "/dev/%s" % (real_root_dev_name)
                                if part.startswith("/") and part != mp:
                                    if ([x for x in auto_mps if mp.startswith(x)]):
                                        # ignore automounted stuff
                                        pass
                                    elif part.startswith("/dev/loop"):
                                        # ignore loop mounted stuff
                                        pass
                                    else:
                                        real_mounts.append((part, mp, fstype, opts, int(dump), int(fsck)))
                                        if not part_lut.has_key(part):
                                            # check for LVM-partition
                                            try:
                                                if part.startswith("/dev/mapper"):
                                                    vg_name, lv_name = part.split("/")[3].split("-")
                                                else:
                                                    vg_name, lv_name = part.split("/")[2:4]
                                            except:
                                                self.log("error splitting path %s: %s" % (part,
                                                                                          process_tools.get_except_info()),
                                                         logging_tools.LOG_LEVEL_ERROR)
                                            else:
                                                #print self.local_lvm_info
                                                act_lv = self.local_lvm_info.lv_dict["lv"][lv_name]
                                                act_lv["mount_options"] = {"mountpoint" : mp,
                                                                           "fstype"     : fstype,
                                                                           "options"    : opts,
                                                                           "dump"       : int(dump),
                                                                           "fsck"       : int(fsck)}
                                        else:
                                            dev, part_num = part_lut[part]
                                            dev_dict[dev][part_num]["mountpoint"] = mp
                                            dev_dict[dev][part_num]["fstype"]     = fstype
                                            dev_dict[dev][part_num]["options"]    = opts
                                            dev_dict[dev][part_num]["dump"]       = int(dump)
                                            dev_dict[dev][part_num]["fsck"]       = int(fsck)
                                            if not dev_dict[dev][part_num]["info"]:
                                                if fstype not in ["swap"]:
                                                    dev_dict[dev][part_num]["hextype"] = "0x83"
                                                    dev_dict[dev][part_num]["info"] = "Linux"
                                                else:
                                                    dev_dict[dev][part_num]["hextype"] = "0x82"
                                                    dev_dict[dev][part_num]["info"] = "Linux swap / Solaris"
                                            # add lookup
                                            local_lut = {}
                                            for add_key in sorted(my_disk_lut.get_top_keys()):
                                                if my_disk_lut[add_key].has_key(part):
                                                    local_lut[add_key] = my_disk_lut[(add_key, part)]
                                            dev_dict[dev][part_num]["lut"] = local_lut
                                else:
                                    if part == mp:
                                        part = "none"
                                    if not sys_dict.has_key(part) or not len([x for x in sys_dict[part] if x["mountpoint"] == mp]):
                                        sys_dict.setdefault(part, []).append({"mountpoint" : mp,
                                                                              "fstype"     : fstype,
                                                                              "options"    : opts})
                                        sys_mounts.append((part, mp, fstype, opts))
                    ret_str = ""
        return ret_str, dev_dict, sys_dict

class my_modclass(hm_classes.hm_fileinfo):
    def __init__(self, **args):
        hm_classes.hm_fileinfo.__init__(self,
                                        "machinfo",
                                        "returns basic hardware information about this machine",
                                        **args)
    def init(self, mode, logger, basedir_name, **args):
        mtype = os.uname()[4]
        if re.match("^i.*86$", mtype) or re.match("^x86.64$", mtype):
            self.mach_arch = "i386"
        else:
            self.mach_arch = "alpha"
        if mode == "i":
            self.vdict, self.cdict = pci_database.get_pci_dicts()
            conf_file = "/etc/sysconfig/ethtool/config"
            if not os.path.isdir(os.path.dirname(conf_file)):
                try:
                    os.mkdir(os.path.dirname(conf_file))
                except:
                    logger.error("cannot create directory %s: %s" % (os.path.dirname(conf_file),
                                                                     process_tools.get_except_info()))
            try:
                conf_data = open(conf_file, "w")
            except:
                logger.error("cannot open file %s for writing:: %s" % (conf_file,
                                                                       process_tools.get_except_info()))
            else:
                net_dir = "/sys/class/net"
                drv_dict = {}
                if os.path.isdir(net_dir):
                    for entry in os.listdir(net_dir):
                        device_link = "%s/%s/device" % (net_dir, entry)
                        driver_link = "%s/%s/driver" % (net_dir, entry)
                        if not os.path.islink(driver_link):
                            driver_link = "%s/driver" % (device_link)
                        if os.path.islink(device_link) and os.path.islink(driver_link):
                            driver   = os.path.basename(os.path.normpath("%s/%s/%s" % (net_dir, entry, os.readlink(driver_link))))
                            pci_info = os.path.basename(os.path.normpath("%s/%s/%s" % (net_dir, entry, os.readlink(device_link))))
                            drv_dict.setdefault(driver, []).append(entry)
                            conf_data.write("pci_%s=\"%s\"\n" % (entry, pci_info))
                            conf_data.write("drv_%s=\"%s\"\n" % (entry, driver))
                            #print entry, pci_info, driver
                for driv_name, driv_nets in drv_dict.iteritems():
                    conf_data.write("net_%s=\"%s\"\n" % (driv_name, " ".join(driv_nets)))
                conf_data.close()
            #self._rescan_valid_disk_stuff(logger)
            # check for lvm-bins
            self.local_lvm_info = partition_tools.lvm_struct("bin")
            self.cpu_list = ["0"]
            self.disk_dict, self.vmstat_dict, self.disk_stat = ({}, {}, {})
            self.disk_dict_last_update = 0
            self.last_time = 0.
    def process_server_args(self, glob_config, logger):
        self.__glob_config = glob_config
        self.__check_nameserver = False
        if self.__glob_config["CHECK_NAMESERVER"]:
            rndc_bin_locs = ["/usr/sbin/rndc"]
            for rndc_bin_loc in rndc_bin_locs:
                if os.path.isfile(rndc_bin_loc):
                    self.__check_nameserver, self.__rndc_com = (True, rndc_bin_loc)
                    logger.info("enabled nameserver stats")
                    self.__nameserver_dict, self.__nameserver_check = ({}, time.time())
        return (True, "")
    def process_client_args(self, opts, hmb):
        ok, why = (1, "")
        my_lim = limits.limits()
        cpu_range = limits.range_parameter("cpuspeed")
        for opt, arg in opts:
            #print opt, arg
            if hmb.name in ["machinfo", "pciinfo", "hwinfo", "cpuinfo", "lvminfo", "dmiinfo"]:
                if opt in ("-r", "--raw"):
                    my_lim.set_add_flags("R")
            if hmb.name in ["lvminfo"]:
                my_lim.set_add_flags("L")
            if opt == "-w":
                if my_lim.set_warn_val(arg) == 0:
                    ok = 0
                    why = "Can't parse warning value !"
            if opt == "-c":
                if my_lim.set_crit_val(arg) == 0:
                    ok = 0
                    why = "Can't parse critical value !"
            if hmb.name in ["cpuinfo"]:
                if opt == "--cpulow":
                    cpu_range.set_lower_boundary(arg)
                if opt == "--cpuhigh":
                    cpu_range.set_upper_boundary(arg)
            if hmb.name in ["general"]:
                if opt in ["-l", "-A"]:
                    my_lim.set_add_flags("l")
                if opt in ["-u", "-A"]:
                    my_lim.set_add_flags("u")
                if opt in ["-i", "-A"]:
                    my_lim.set_add_flags("i")
                if opt in ["-k", "-A"]:
                    my_lim.set_add_flags("k")
                if opt in ["-d", "-A"]:
                    my_lim.set_add_flags("d")
        return ok, why, [my_lim, cpu_range]
    def proc_stat_info(self, first_line):
        if len(first_line) >= 9:
            # kernel 2.5 and above with additional steal-value
            what_list = ["user", "nice", "sys", "idle", "iowait", "irq", "softirq", "steal"]
            kernel = 26
        elif len(first_line) == 8:
            # kernel 2.5 and above
            what_list = ["user", "nice", "sys", "idle", "iowait", "irq", "softirq"]
            kernel = 26
        else:
            # up to kernel 2.4
            what_list = ["user", "nice", "sys", "idle"]
            kernel = 24
        return what_list, kernel
    # initialises machine vector
    def _mem_int(self):
        m_dict = dict([(s_pair[0][0:-1], s_pair[1]) for s_pair in [l_split.split() for l_split in [r_line.strip() for r_line in open("/proc/meminfo", "r").readlines()]
                                                                   if l_split.endswith("kB")]
                       if len(s_pair) > 1])
        m_array = {}
        for s_key in ["MemTotal", "MemFree", "Buffers", "Cached", "SwapTotal", "SwapFree", "MemShared"]:
            if m_dict.has_key(s_key):
                m_array[s_key.lower()] = int(m_dict[s_key])
            else:
                m_array[s_key.lower()] = 0
        return m_array
    def _load_int(self):
        return [float(x) for x in open("/proc/loadavg", "r").read().strip().split()[0:3]]
    def _partinfo_int(self):
        my_disk_lut = partition_tools.disk_lut()
        #IGNORE_LVM_PARTITIONS = False
        dev_dict, sys_dict = ({}, {})
        read_err_list = []
        try:
            mount_list = [x.strip().split() for x in open("/proc/mounts", "r").read().split("\n") if x.strip()]
        except:
            read_err_list.append("/proc/mounts")
        try:
            devices_list = [x.strip().split() for x in open("/proc/devices", "r").read().split("\n") if x.strip()]
        except:
            read_err_list.append("/proc/devices")
        try:
            fstab_list = [x.strip().split() for x in open("/etc/fstab", "r").read().split("\n") if x.strip()]
        except:
            read_err_list.append("/etc/fstab")
        try:
            parts_list = [y[0:4] for y in [x.strip().split() for x in open("/proc/partitions", "r").read().split("\n") if x.strip()] if len(y) >=4]
        except:
            read_err_list.append("/proc/partitions")
        try:
            real_root_dev = int(open("/proc/sys/kernel/real-root-dev", "r").read().strip())
        except:
            read_err_list.append("/proc/sys/kernel/real-root-dev")
        if read_err_list:
            ret_str = "error reading %s" % (" and ".join(read_err_list))
        else:
            ret_str = ""
            # build devices-dict
            while True:
                stuff = devices_list.pop(0)
                if stuff[0].lower().startswith("block"):
                    break
            devices_dict = dict([(int(x), y) for x, y in devices_list])
            #print devices_dict
            # build partition-dict
            part_dict, real_root_dev_name = ({}, None)
            for major, minor, blocks, part_name in parts_list:
                if major.isdigit() and minor.isdigit() and blocks.isdigit():
                    major = int(major)
                    minor = int(minor)
                    if major * 256 + minor == real_root_dev:
                        real_root_dev_name = part_name
                    blocks = int(blocks)
                    if not minor or not part_name[-1].isdigit():
                        dev_dict["/dev/%s" % (part_name)] = {}
                    part_dict.setdefault(major, {}).setdefault(minor, (part_name, blocks))
            if not real_root_dev_name and real_root_dev:
                real_root_list = [x[0] for x in mount_list if x[1] == "/" and x[0] != "rootfs"]
                if real_root_list:
                    real_root_dev = real_root_list[0]
                    if not real_root_dev.startswith("/"):
                        ret_str = "error determining real_root_device"
            if not real_root_dev_name:
                # try to get root-dev-name from /dev/root
                if os.path.islink("/dev/root"):
                    real_root_dev_name = os.readlink("/dev/root")
                    if real_root_dev_name.startswith("/dev/"):
                        real_root_dev_name = real_root_dev_name[5:]
            # still no real_root_dev_name: try /etc/mtab
            if not real_root_dev_name:
                if os.path.isfile("/etc/mtab"):
                    root_list = [parts[0] for parts in [line.split() for line in open("/etc/mtab", "r").read().split("\n") if line.strip()] if len(parts) > 2 and parts[1] == "/"]
                    if root_list:
                        real_root_dev_name = root_list[0]
                        if real_root_dev_name.startswith("/dev/"):
                            real_root_dev_name = real_root_dev_name[5:]
            if not ret_str:
                # partition lookup dict
                part_lut = {}
                # fetch fdisk information
                for dev in dev_dict.keys():
                    stat, out = commands.getstatusoutput("/sbin/fdisk -l %s" % (dev))
                    if stat:
                        ret_str = "error reading partition table of %s (%d): %s" % (dev, stat, out)
                        break
                    lines = [[z for z in [y.strip() for y in x.strip().split()] if z != "*"] for x in out.split("\n") if x.startswith(dev)]
                    for stuff in lines:
                        part    = stuff.pop(0)
                        start   = stuff.pop(0)
                        end     = stuff.pop(0)
                        size    = stuff.pop(0)
                        hextype = stuff.pop(0)
                        info = " ".join(stuff)
                        if size.endswith("+"):
                            size = size[:-1]
                        start = int(start)
                        end  = int(start)
                        size = int(size) / 1000
                        hextype = "0x%02x" % (int(hextype, 16))
                        part_num = part[len(dev):]
                        dev_dict[dev][part_num] = {"size"    : size,
                                                   "hextype" : hextype,
                                                   "info"    : info}
                        part_lut[part] = (dev, part_num)
                # kick empty devices
                empty_dev_list = [k for k, v in dev_dict.iteritems() if not v]
                for ed in empty_dev_list:
                    del dev_dict[ed]
                if not ret_str:
                    if not dev_dict:
                        # no device_dict up to now, maybe xen-machine, check part_dict
                        for major, m_stuff in part_dict.iteritems():
                            for minor, part_stuff in m_stuff.iteritems():
                                part_name, part_size = part_stuff
                                dev_name = part_name
                                while dev_name[-1].isdigit():
                                    dev_name = dev_name[:-1]
                                part_num = int(part_name[len(dev_name):])
                                dev_name = "/dev/%s" % (dev_name)
                                if not dev_dict.has_key(dev_name):
                                    dev_dict[dev_name] = {}
                                dev_dict[dev_name]["%d" % (part_num)] = {"size"    : part_size / 1024,
                                                                         "hextype" : "0x00",
                                                                         "info"    : ""}
                                part_lut["/dev/%s" % (part_name)] = (dev_name, "%d" % (part_num))
                    # automount mointpoints
                    auto_mps = []
                    # drop unneeded entries
                    real_mounts, sys_mounts = ([], [])
                    parts_found = []
                    for part, mp, fstype, opts, dump, fsck in mount_list:
                        # rewrite from by-id to real device
                        if part.count("by-id"):
                            part = os.path.normpath(os.path.join(part, "..", os.readlink(part)))
                        if part not in parts_found:
                            parts_found.append(part)
                            if fstype in ["subfs", "autofs"]:
                                pass
                            elif part == "rootfs" or part.startswith("automount(") or part.count(":"):
                                if part.startswith("automount("):
                                    auto_mps.append(mp)
                            else:
                                if part == "/dev/root":
                                    part = "/dev/%s" % (real_root_dev_name)
                                if part.startswith("/") and part != mp:
                                    if ([x for x in auto_mps if mp.startswith(x)]):
                                        # ignore automounted stuff
                                        pass
                                    elif part.startswith("/dev/loop"):
                                        # ignore loop mounted stuff
                                        pass
                                    else:
                                        real_mounts.append((part, mp, fstype, opts, int(dump), int(fsck)))
                                        if not part_lut.has_key(part):
                                            # check for LVM-partition
                                            try:
                                                if part.startswith("/dev/mapper"):
                                                    vg_name, lv_name = part.split("/")[3].split("-")
                                                else:
                                                    vg_name, lv_name = part.split("/")[2:4]
                                            except:
                                                self.log("error splitting path %s: %s" % (part,
                                                                                          process_tools.get_except_info()),
                                                         logging_tools.LOG_LEVEL_ERROR)
                                            else:
                                                #print self.local_lvm_info
                                                act_lv = self.local_lvm_info.lv_dict["lv"][lv_name]
                                                act_lv["mount_options"] = {"mountpoint" : mp,
                                                                           "fstype"     : fstype,
                                                                           "options"    : opts,
                                                                           "dump"       : int(dump),
                                                                           "fsck"       : int(fsck)}
                                        else:
                                            dev, part_num = part_lut[part]
                                            dev_dict[dev][part_num]["mountpoint"] = mp
                                            dev_dict[dev][part_num]["fstype"]     = fstype
                                            dev_dict[dev][part_num]["options"]    = opts
                                            dev_dict[dev][part_num]["dump"]       = int(dump)
                                            dev_dict[dev][part_num]["fsck"]       = int(fsck)
                                            if not dev_dict[dev][part_num]["info"]:
                                                if fstype not in ["swap"]:
                                                    dev_dict[dev][part_num]["hextype"] = "0x83"
                                                    dev_dict[dev][part_num]["info"] = "Linux"
                                                else:
                                                    dev_dict[dev][part_num]["hextype"] = "0x82"
                                                    dev_dict[dev][part_num]["info"] = "Linux swap / Solaris"
                                            # add lookup
                                            local_lut = {}
                                            for add_key in sorted(my_disk_lut.get_top_keys()):
                                                if my_disk_lut[add_key].has_key(part):
                                                    local_lut[add_key] = my_disk_lut[(add_key, part)]
                                            dev_dict[dev][part_num]["lut"] = local_lut
                                else:
                                    if part == mp:
                                        part = "none"
                                    if not sys_dict.has_key(part) or not len([x for x in sys_dict[part] if x["mountpoint"] == mp]):
                                        sys_dict.setdefault(part, []).append({"mountpoint" : mp,
                                                                              "fstype"     : fstype,
                                                                              "options"    : opts})
                                        sys_mounts.append((part, mp, fstype, opts))
                    ret_str = ""
        return ret_str, dev_dict, sys_dict
    def _vmstat_int(self, logger, mvect):
        lines = open("/proc/stat", "r").read().split("\n")
        act_time = time.time()
        # disk_stat format: device -> (sectors read/written, milliseconds spent read/written)
        stat_dict, disk_stat = ({}, {})
        kernel, what_list = (None, None)
        for lines in [x.split() for x in [y.strip() for y in lines] if x]:
            if lines[0].startswith("cpu"):
                stat_dict[lines[0]] = [long(x) for x in lines[1:]]

                if not kernel:
                    what_list, kernel = self.proc_stat_info(lines)
            elif lines[0] == "ctxt":
                stat_dict["ctxt"] = long(lines[1])
            elif lines[0] == "intr":
                stat_dict["intr"] = long(lines[1])
            elif lines[0] == "swap":
                stat_dict["swap"] = [long(lines[1]), long(lines[2])]
            elif lines[0] == "disk_io:":
                blks_read, blks_written = (0, 0)
                for io in [[y.strip() for y in x.split(":")[1][1:-1].split(",")] for x in lines[1:]]:
                    blks_read += long(io[2])
                    blks_written += long(io[4])
                disk_stat["total"] = (blks_read, blks_written, 0, 0, 0)
                dev_list, unique_dev_list = (["total"], ["total"])
                #stat_dict["disk_io"] = []
            # check for diskstats-file
        if os.path.isfile("/proc/diskstats"):
            try:
                ds_dict = dict([(y[2].strip(), [int(y[0]), int(y[1])] + [long(z) for z in y[3:]]) for y in [x.strip().split() for x in open("/proc/diskstats", "r").read().split("\n")] if len(y) == 14])# and y[2].strip() in self.valid_block_devs.keys()])
            except:
                pass
            else:
                # get list of mounts
                try:
                    mount_list = [y.split("/", 2)[2] for y in [x.strip().split()[0] for x in open("/proc/mounts", "r").read().split("\n") if x.startswith("/dev/")]]
                except:
                    # cannot read, take all devs
                    mount_list = ds_dict.keys()
                else:
                    pass
                # get unique devices
                ds_keys_ok_by_name = sorted([key for key, value in ds_dict.iteritems() if key in self.valid_block_devs.keys()])
                # sort out partition stuff
                last_name = ""
                ds_keys_ok_by_major = []
                for d_name in sorted([key for key, value in ds_dict.iteritems() if value[0] in self.valid_major_nums.keys()]):
                    if last_name and not (d_name.startswith("dm-") or d_name.startswith("md")) and d_name.startswith(last_name):
                        pass
                    else:
                        ds_keys_ok_by_major.append(d_name)
                        last_name = d_name
                if ds_keys_ok_by_name != ds_keys_ok_by_major:
                    self._rescan_valid_disk_stuff(logger)
                    ds_keys_ok_by_major = ds_keys_ok_by_name
                    self.local_lvm_info.update()
                mounted_lvms = {}
                if self.local_lvm_info.lvm_present:
                    for loc_lvm_name, loc_lvm_info in self.local_lvm_info.lv_dict.get("lv", {}).iteritems():
                        lv_k_major, lv_k_minor = (int(loc_lvm_info["kernel_major"]),
                                                  int(loc_lvm_info["kernel_minor"]))
                        if lv_k_major in self.valid_major_nums.keys():
                            mount_dev = "%s/%s" % (loc_lvm_info["vg_name"],
                                                   loc_lvm_info["name"])
                            mounted_lvms[mount_dev] = "%s-%d" % (self.valid_major_nums[lv_k_major][0].split("-")[0], lv_k_minor)
                # problem: LVM devices are not handled properly
                dev_list = [x for x in ds_keys_ok_by_name if [True for y in mount_list if y.startswith(x)]] + \
                           [value for key, value in mounted_lvms.iteritems() if key in mount_list]
                for dl in dev_list:
                    disk_stat[dl] = (ds_dict[dl][4],
                                     ds_dict[dl][8],
                                     ds_dict[dl][5],
                                     ds_dict[dl][9],
                                     ds_dict[dl][11])
                disk_stat["total"] = []
                for idx in range(5):
                    disk_stat["total"].append(sum([disk_stat[x][idx] for x in dev_list]))
                dev_list.append("total")
                unique_dev_list = dev_list
        #print dev_list, disk_stat
        #stat_dict["disk_io"] = [blks_read, blks_written]
        if not what_list:
            what_list = ["user", "nice", "sys", "idle"]
        stat_d = {}
        if self.last_time != 0.:
            tdiff = act_time - self.last_time
            if self.mach_arch == "alpha":
                vms_tdiff = tdiff * 1024. / 100.
            else:
                vms_tdiff = tdiff
            if stat_dict.has_key("ctxt") and self.vmstat_dict.has_key("ctxt"):
                mvect.reg_update(logger, "num.context", int((stat_dict["ctxt"] - self.vmstat_dict["ctxt"]) / tdiff))
            for cpui in ["-"] + self.cpu_list:
                cpustr = "cpu"
                name_p = ""
                if cpui != "-":
                    cpustr += cpui
                    name_p = ".p%s" % (cpui)
                    if len(self.cpu_list) < 2:
                        break
                if stat_dict.has_key(cpustr) and self.vmstat_dict.has_key(cpustr):
                    idx = 0
                    for name in what_list:
                        mvect.reg_update(logger, "vms.%s%s" % (name, name_p), float(sub_wrap(stat_dict[cpustr][idx], self.vmstat_dict[cpustr][idx]) / vms_tdiff))
                        idx += 1
                else:
                    break
            if stat_dict.has_key("intr") and self.vmstat_dict.has_key("intr"):
                mvect.reg_update(logger, "num.interrupts", int(sub_wrap(stat_dict["intr"], self.vmstat_dict["intr"]) / tdiff))
            if stat_dict.has_key("swap") and self.vmstat_dict.has_key("swap"):
                for name, idx in [("in", 0), ("out", 1)]:
                    mvect.reg_update(logger, "swap.%s" % (name), int(sub_wrap(stat_dict["swap"][idx], self.vmstat_dict["swap"][idx]) / tdiff))
            for act_disk in unique_dev_list:
                if not self.disk_stat.has_key(act_disk):
                    info_str = act_disk == "total" and "total" or "on /dev/$2"
                    mvect.reg_entry("io.%s.blks.read" % (act_disk)   , 0 , "number of blocks read per second %s" % (info_str)   , "1/s")
                    mvect.reg_entry("io.%s.blks.written" % (act_disk), 0 , "number of blocks written per second %s" % (info_str), "1/s")
                    mvect.reg_entry("io.%s.time.read" % (act_disk)   , 0., "milliseconds spent reading %s" % (info_str)         , "s"  )
                    mvect.reg_entry("io.%s.time.written" % (act_disk), 0., "milliseconds spent writing %s" % (info_str)         , "s"  )
                    mvect.reg_entry("io.%s.time.io" % (act_disk)     , 0., "milliseconds spent doing IO %s" % (info_str)        , "s"  )
            for old_disk in self.disk_stat.keys():
                if not disk_stat.has_key(old_disk):
                    mvect.unreg_entry("io.%s.blks.read" % (old_disk))
                    mvect.unreg_entry("io.%s.blks.written" % (old_disk))
                    mvect.unreg_entry("io.%s.time.read" % (old_disk))
                    mvect.unreg_entry("io.%s.time.written" % (old_disk))
                    mvect.unreg_entry("io.%s.time.io" % (old_disk))
            for act_disk in [d for d in unique_dev_list if self.disk_stat.has_key(d)]:
                #print act_disk, disk_stat[act_disk]
                for idx, what in [(0, "read"), (1, "written")]:
                    mvect.reg_update(logger, "io.%s.blks.%s" % (act_disk, what), int(sub_wrap(disk_stat[act_disk][idx], self.disk_stat[act_disk][idx]) / tdiff))
                for idx, what in [(2, "read"), (3, "written"), (4, "io")]:
                    mvect.reg_update(logger, "io.%s.time.%s" % (act_disk, what), float(sub_wrap(disk_stat[act_disk][idx], self.disk_stat[act_disk][idx]) / (1000 * tdiff)))
            self.vmstat_dict = stat_dict
            self.disk_stat = disk_stat
        else:
            tdiff = None
        self.last_time = act_time
    def _df_int(self, logger, mvect=None):
        act_time, update_dict = (time.time(), False)
        if mvect or abs(self.disk_dict_last_update - act_time) > 90:
            update_dict = True
        if update_dict:
            self.disk_dict_last_update = act_time
            ram_match = re.compile("^.*/ram\d+$")
            dev_match = re.compile("^/dev/.*$")
            smount_lines = [line.strip().split() for line in open("/etc/mtab", "r").readlines()]
            link_list = []
            mlist = []
            for line in smount_lines:
                if line[2] not in ["none"] and line[0].startswith("/") and not ram_match.match(line[0]) and dev_match.match(line[0]):
                    mlist.append(line)
                    if os.path.islink(line[0]):
                        link_list.append((os.path.normpath(os.path.join(os.path.dirname(line[0]),
                                                                        os.readlink(line[0]))),
                                          line[0]))
            #print self.disk_dict
            n_dict = {}
            for mnt in mlist:
                try:
                    osres = os.statvfs(mnt[1])
                except:
                    pass
                else:
                    fact = float(osres[statvfs.F_FRSIZE]) / (1024.)
                    try:
                        blocks, bfree, bavail = int(osres[statvfs.F_BLOCKS]), int(osres[statvfs.F_BFREE]), int(osres[statvfs.F_BAVAIL])
                    except:
                        pass
                    else:
                        if blocks:
                            sizetot = blocks * fact
                            sizeused = (blocks - bfree) * fact
                            sizeavail = bavail * fact
                            sizefree = sizetot - sizeused
                            proc = int((100.*float(blocks - bfree)) / float(blocks - bfree + bavail))
                            n_dict[mnt[0]] = [mnt[1], proc, int(sizetot), int(sizeused), int(sizefree)]
            for link_dst, link_src in link_list:
                n_dict[link_dst] = n_dict[link_src]
        else:
            n_dict = self.disk_dict
        if mvect:
            # delete old keys
            for key in self.disk_dict.keys():
                if not n_dict.has_key(key):
                    mvect.unreg_entry("df.%s.f" % (key))
                    mvect.unreg_entry("df.%s.u" % (key))
                    mvect.unreg_entry("df.%s.t" % (key))
            for key in n_dict.keys():
                if not self.disk_dict.has_key(key):
                    mvect.reg_entry("df.%s.f" % (key), 0, "free space on $2 (%s)" % (n_dict[key][0]), "Byte", 1000, 1000)
                    mvect.reg_entry("df.%s.u" % (key), 0, "used space on $2 (%s)" % (n_dict[key][0]), "Byte", 1000, 1000)
                    mvect.reg_entry("df.%s.t" % (key), 0, "size of $2 (%s)"       % (n_dict[key][0]), "Byte", 1000, 1000)
            self.disk_dict = n_dict
            for key in self.disk_dict.keys():
                mvect.reg_update(logger, "df.%s.f" % (key), self.disk_dict[key][4])
                mvect.reg_update(logger, "df.%s.u" % (key), self.disk_dict[key][3])
                mvect.reg_update(logger, "df.%s.t" % (key), self.disk_dict[key][2])
        else:
            return n_dict
    def _check_nameserver_stats(self, logger, mv):
        c_stat, c_out = commands.getstatusoutput("%s stats" % (self.__rndc_com))
        #print "cns:", c_stat, c_out
        if c_stat:
            logger.error("error querying nameserver (%d): %s" % (c_stat, c_out))
        else:
            stat_f_name = "/var/lib/named/log/named.stats"
            if os.path.isfile(stat_f_name):
                stat_dict = {}
                for line in open(stat_f_name, "r").read().split("\n"):
                    if line.strip():
                        if line.startswith("+++"):
                            stat_dict = {}
                        elif line.startswith("---"):
                            pass
                        else:
                            line_spl = line.split()
                            stat_dict[line_spl[0]] = int(line_spl[1])
                #print stat_dict
                act_time = time.time()
                diff_time = abs(act_time - self.__nameserver_check)
                for key, value in stat_dict.iteritems():
                    if not self.__nameserver_dict.has_key(key):
                        mv.reg_entry("ns.query.%s" % (key), 0., "namserver query %s per minute" % (key), "1/min")
                        diff_value = 0
                    else:
                        diff_value = (stat_dict[key] - self.__nameserver_dict[key])
                    mv.reg_update(logger, "ns.query.%s" % (key), diff_value * 60. / diff_time)
                self.__nameserver_dict, self.__nameserver_check = (stat_dict, act_time)
                try:
                    os.unlink(stat_f_name)
                except:
                    logger.error("error removing %s: %s" % (stat_f_name,
                                                            process_tools.get_except_info()))
            else:
                logger.error("no file named '%s' found" % (stat_f_name))

class df_command(hm_classes.hm_command):
    def __init__(self, name):
        hm_classes.hm_command.__init__(self, name, positional_arguments=True)
        self.parser.add_argument("-w", dest="warn", type=float)
        self.parser.add_argument("-c", dest="crit", type=float)
        self.__disk_lut = partition_tools.disk_lut()
    def _get_size_str(self, in_b):
        pf_list = ["k", "M", "G", "T", "E", "P"]
        rst = float(in_b)
        while rst > 1024:
            pf_list.pop(0)
            rst /= 1024.
        return "%.2f %sB" % (rst, pf_list[0])
    def __call__(self, srv_com, cur_ns):
        if not "arguments:arg0" in srv_com:
            srv_com["result"].attrib.update({"reply" : "missing argument",
                                             "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR)})
        else:
            disk = srv_com["arguments:arg0"].text.strip()
            if disk.startswith("/dev/mapper"):
                if os.path.islink(disk):
                    disk = os.path.normpath(os.path.join(os.path.dirname(disk),
                                                         os.readlink(disk)))
            if disk.startswith("/dev/disk/by-"):
                try:
                    mapped_disk = self.__disk_lut[disk]
                except:
                    mapped_disk = "not found"
            else:
                mapped_disk = disk
            try:
                n_dict = self.module._df_int()
            except:
                return "error reading /etc/mtab"
            if disk == "ALL":
                srv_com.set_dictionary("df_result", dict([(disk, {"mountpoint" : n_dict[disk][0],
                                                                  "perc"       : n_dict[disk][1],
                                                                  "used"       : n_dict[disk][3],
                                                                  "total"      : n_dict[disk][2]}) for disk in n_dict.keys()]))
            else:
                if not mapped_disk in n_dict:
                    # id is just a guess, FIXME
                    try:
                        all_maps = self.__disk_lut["id"][mapped_disk]
                    except KeyError:
                        print "+"
                        return "error invalid partition %s (key is %s)" % (disk,
                                                                           mapped_disk)
                    else:
                        disk_found = False
                        for mapped_disk in ["/dev/disk/by-id/%s" % (cur_map) for cur_map in all_maps]:
                            if mapped_disk in n_dict:
                                disk_found = True
                                break
                        if not disk_found:
                            print "+*"
                            return "error invalid partition %s" % (disk)
                srv_com.set_dictionary("df_result", {"part"        : disk,
                                                     "mapped_disk" : mapped_disk,
                                                     "mountpoint"  : n_dict[mapped_disk][0],
                                                     "perc"        : n_dict[mapped_disk][1],
                                                     "used"        : n_dict[mapped_disk][3],
                                                     "total"       : n_dict[mapped_disk][2]})
    def interpret(self, srv_com, cur_ns):
        result = server_command.srv_command.tree_to_dict(srv_com["df_result"])
        print result
        if result.has_key("perc"):
            # single-partition result
            ret_state = limits.check_ceiling(result["perc"], cur_ns.warn, cur_ns.crit)
            if result.has_key("mapped_disk"):
                part_str = "%s (is %s)" % (result["mapped_disk"], result["part"])
            else:
                part_str = result["part"]
            return ret_state, "%.0f %% (%s of %s%s) used on %s" % (result["perc"],
                                                                   self._get_size_str(result["used"]),
                                                                   self._get_size_str(result["total"]),
                                                                   ", mp %s" % (result["mountpoint"]) if result.has_key("mountpoint") else "",
                                                                   part_str)
        else:
            # all-partition result
            max_stuff = {"perc" : -1}
            all_parts = sorted(result.keys())
            for part_name in all_parts:
                d_stuff = result[part_name]
                if d_stuff["perc"] > max_stuff["perc"]:
                    max_stuff = d_stuff
                    max_part = part_name
            ret_state = limits.check_ceiling(max_stuff["perc"], cur_ns.warn, cur_ns.crit)
            return ret_state, "%.0f %% used on %s (%s, %s)" % (max_stuff["perc"],
                                                               max_part,
                                                               max_stuff["mountpoint"],
                                                               logging_tools.get_plural("partition", len(all_parts)))
    def interpret_old(self, result, parsed_coms):
        result = hm_classes.net_to_sys(result[3:])
        if result.has_key("perc"):
            # single-partition result
            ret_state = limits.check_ceiling(result["perc"], parsed_coms.warn, parsed_coms.crit)
            if result.has_key("mapped_disk"):
                part_str = "%s (is %s)" % (result["mapped_disk"], result["part"])
            else:
                part_str = result["part"]
            return ret_state, "%.0f %% (%s of %s%s) used on %s" % (result["perc"],
                                                                   self._get_size_str(result["used"]),
                                                                   self._get_size_str(result["total"]),
                                                                   ", mp %s" % (result["mountpoint"]) if result.has_key("mountpoint") else "",
                                                                   part_str)
        else:
            # all-partition result
            max_stuff = {"perc" : -1}
            all_parts = sorted(result.keys())
            for part_name in all_parts:
                d_stuff = result[part_name]
                if d_stuff["perc"] > max_stuff["perc"]:
                    max_stuff = d_stuff
                    max_part = part_name
            ret_state = limits.check_ceiling(max_stuff["perc"], parsed_coms.warn, parsed_coms.crit)
            return ret_state, "%.0f %% used on %s (%s, %s)" % (max_stuff["perc"],
                                                               max_part,
                                                               max_stuff["mountpoint"],
                                                               logging_tools.get_plural("partition", len(all_parts)))

class get_uuid_command(hm_classes.hm_command):
    def __call__(self, srv_com, cur_ns):
        srv_com["uuid"] = uuid_tools.get_uuid().get_urn()
    def interpret(self, srv_com, cur_ns):
        try:
            return limits.nag_STATE_OK, "uuid is %s" % (srv_com["uuid"].text)
        except:
            return limits.nag_STATE_CRITICAL, "uuid not found"
    def interpret_old(self, result, parsed_coms):
        act_state = limits.nag_STATE_OK
        return act_state, "ok uuid is %s" % (result.split()[1])

class swap_command(hm_classes.hm_command):
    def __init__(self, name):
        hm_classes.hm_command.__init__(self, name, positional_arguments=False)
        self.parser.add_argument("-w", dest="warn", type=float)
        self.parser.add_argument("-c", dest="crit", type=float)
    def __call__(self, srv_com, cur_ns):
        srv_com.set_dictionary("mem", self.module._mem_int())
    def interpret(self, srv_com, cur_ns):
        swap_total, swap_free = (srv_com.get_int("mem:SwapTotal"),
                                 srv_com.get_int("mem:SwapFree"))
        if swap_total == 0:
            return limits.nag_STATE_CRITICAL, "no swap space found"
        else:
            swap = 100 * float(swap_total - swap_free) / swap_total
            ret_state = limits.check_ceiling(swap, cur_ns.warn , cur_ns.crit)
            return ret_state, "%d %% of %s swap" % (swap,
                                                    logging_tools.get_size_str(swap_total * 1024))
    def interpret_old(self, result, parsed_coms):
        def k_str(i_val):
            f_val = float(i_val)
            if f_val < 1024:
                return "%0.f kB" % (f_val)
            f_val /= 1024.
            if f_val < 1024.:
                return "%.2f MB" % (f_val)
            f_val /= 1024.
            return "%.2f GB" % (f_val)
        result = hm_classes.net_to_sys(result[3:])
        swaptot, swapfree = (int(result["swaptotal"]), 
                             int(result["swapfree"]))
        if swaptot == 0:
            return limits.nag_STATE_CRITICAL, "%s: no swap space found" % (limits.get_state_str(limits.nag_STATE_CRITICAL))
        else:
            swap = 100 * (swaptot - swapfree) / swaptot
            ret_state = limits.check_ceiling(swap, parsed_coms.warn, parsed_coms.crit)
            return ret_state, "swapinfo: %d %% of %s swap" % (swap, k_str(swaptot))

class mem_command(hm_classes.hm_command):
    def __init__(self, name):
        hm_classes.hm_command.__init__(self, name, positional_arguments=False)
        self.parser.add_argument("-w", dest="warn", type=float)
        self.parser.add_argument("-c", dest="crit", type=float)
    def __call__(self, srv_com, cur_ns):
        srv_com.set_dictionary("mem", self.module._mem_int())
    def interpret(self, srv_com, cur_ns):
        mem_total, mem_free = (srv_com.get_int("mem:MemTotal"),
                               srv_com.get_int("mem:MemFree") + srv_com.get_int("mem:Buffers") + srv_com.get_int("mem:Cached"))
        swap_total, swap_free = (srv_com.get_int("mem:SwapTotal"),
                                 srv_com.get_int("mem:SwapFree"))
        all_total = mem_total + swap_total
        all_free = mem_free + swap_free
        mem_p  = 100 * (1 if mem_total == 0  else float(mem_total - mem_free) / mem_total)
        swap_p = 100 * (1 if swap_total == 0 else float(swap_total - swap_free) / swap_total)
        all_p  = 100 * (1 if all_total == 0  else float(all_total - all_free) / all_total)
        ret_state = limits.check_ceiling(all_p, cur_ns.warn, cur_ns.crit)
        return ret_state, "meminfo: %d %% of %s phys, %d %% of %s tot" % (mem_p,
                                                                          logging_tools.get_size_str(mem_total * 1024),
                                                                          all_p,
                                                                          logging_tools.get_size_str(all_total * 1024))
    def interpret_old(self, result, parsed_coms):
        def k_str(i_val):
            f_val = float(i_val)
            if f_val < 1024:
                return "%0.f kB" % (f_val)
            f_val /= 1024.
            if f_val < 1024.:
                return "%.2f MB" % (f_val)
            f_val /= 1024.
            return "%.2f GB" % (f_val)
        result = hm_classes.net_to_sys(result[3:])
        memtot = int(result["memtotal"])
        memfree = int(result["memfree"]) + int(result["buffers"]) + int(result["cached"])
        if memtot == 0:
            memp = 100
        else:
            memp = 100 * (memtot - memfree) / memtot
        swaptot = int(result["swaptotal"])
        swapfree = int(result["swapfree"])
        if swaptot == 0:
            swapp = 100
        else:
            swapp = 100 * (swaptot - swapfree) / swaptot
        alltot = memtot + swaptot
        allfree = memfree + swapfree
        if alltot == 0:
            allp = 100
        else: 
            allp = 100 * (alltot - allfree) / alltot
        ret_state = limits.check_ceiling(max(allp, memp), parsed_coms.warn, parsed_coms.crit)
        return ret_state, "meminfo: %d %% of %s phys, %d %% of %s tot" % (memp, k_str(memtot), allp, k_str(alltot))

class sysinfo_command(hm_classes.hm_command):
    def __init__(self, name):
        hm_classes.hm_command.__init__(self, name, positional_arguments=True)
    def __call__(self, srv_com, cur_ns):
        root_dir = srv_com.get("arguments:arg0", "/")
        log_lines, sys_dict = process_tools.fetch_sysinfo(root_dir)
        for log_line, log_lev in log_lines:
            self.log(log_line, log_lev)
        imi_file = "/%s/.imageinfo" % (root_dir)
        if os.path.isfile(imi_file):
            srv_com.set_dictionary("imageinfo", dict([(key.strip(), value.strip()) for key, value in [line.strip().lower().split("=", 1) for line in open(imi_file, "r").readlines() if line.count("=")]]))
        srv_com.set_dictionary("sysinfo", sys_dict)
    def interpret(self, srv_com, cur_ns):
        need_keys = set(["vendor", "version", "arch"])
        miss_keys = [key for key in need_keys if not "sysinfo:%s" % (key) in srv_com]
        if miss_keys:
            return limits.nag_STATE_CRITICAL, "%s missing : %s" % (logging_tools.get_plural("key", len(mis_keys)), ", ".join(mis_keys))
        else:
            ret_str = "Distribution is %s version %s on an %s" % (srv_com["sysinfo:vendor"].text,
                                                                  srv_com["sysinfo:version"].text,
                                                                  srv_com["sysinfo:arch"].text)
            if "imageinfo" in srv_com:
                if "imageinfo:image_name" in srv_com and "imageinfo:image_version" in srv_com:
                    ret_str += ", image is %s (version %s)" % (srv_com["imageinfo:image_name"], srv_com["imageinfo:image_version"])
                else:
                    ret_str += ", no image info"
            return limits.nag_STATE_OK, ret_str
        
class load_command(hm_classes.hm_command):
    info_string = "load information"
    def __init__(self, name):
        hm_classes.hm_command.__init__(self, name, positional_arguments=False)
        self.parser.add_argument("-w", dest="warn", type=float)
        self.parser.add_argument("-c", dest="crit", type=float)
    def __call__(self, srv_com, cur_ns):
        cur_load = self.module._load_int()
        srv_com["load1"] = "%.2f" % (cur_load[0])
        srv_com["load5"] = "%.2f" % (cur_load[1])
        srv_com["load15"] = "%.2f" % (cur_load[2])
    def interpret(self, srv_com, cur_ns):
        load_1, load_5, load_15 = (float(srv_com["load1"].text),
                                   float(srv_com["load5"].text),
                                   float(srv_com["load15"].text))
        max_load = max([load_1, load_5, load_15])
        ret_state = limits.nag_STATE_OK
        if cur_ns.warn is not None:
            ret_state = max(ret_state, limits.nag_STATE_WARNING if max_load >= cur_ns.warn else limits.nag_STATE_OK)
        if cur_ns.crit is not None:
            ret_state = max(ret_state, limits.nag_STATE_CRITICAL if max_load >= cur_ns.crit else limits.nag_STATE_OK)
        return ret_state, "load (1/5/15): %.2f %.2f %.2f" % (load_1, load_5, load_15)
    def interpret_old(self, result, parsed_coms):
        result = hm_classes.net_to_sys(result[3:])
        load1  = float(result["load1"])
        load5  = float(result["load5"])
        load15 = float(result["load15"])
        maxload = max(load1, load5, load15)
        print parsed_coms
        ret_state = limits.check_ceiling(maxload, parsed_coms.warn, parsed_coms.crit)
        ret_str = "load (1/5/15): %.2f %.2f %.2f" % (load1, load5, load15)
        return ret_state, ret_str

class uptime_command(hm_classes.hm_command):
    info_string = "update information"
    def __call__(self, srv_com, cur_ns):
##        cur_sps = hm_classes.subprocess_struct(srv_com, "ps auxw", self._process)
##        return cur_sps
##        return hm_classes.subprocess_struct(srv_com, "ps auxw ; sleep 10")
##    def _process(self, sps):
##        print sps.read()
##        srv_com = sps.srv_com
        upt_data = [int(float(value)) for value in open("/proc/uptime", "r").read().strip().split()]
        srv_com["uptime"] = "%d" % (upt_data[0])
        if len(upt_data) > 1:
            srv_com["idle"] = "%d" % (upt_data[1])
    def interpret(self, srv_com, cur_ns):
        uptime_int = int(srv_com["uptime"].text)
        up_m = int(uptime_int) / 60
        up_d = int(up_m / (60 * 24))
        up_h = int((up_m - up_d * (60 * 24)) / 60)
        up_m = up_m - 60 * (up_d * 24 + up_h)
        return limits.nag_STATE_OK, "up for %s, %d:%02d" % (logging_tools.get_plural("day", up_d),
                                                            up_h,
                                                            up_m)
    def interpret_old(self, result, parsed_coms):
        result = hm_classes.net_to_sys(result[3:])
        return limits.nag_STATE_OK, "OK: Up for %s days, %s hours and %s mins" % (result["up_days"], result["up_hours"], result["up_minutes"])

class date_command(hm_classes.hm_command):
    info_string = "return date"
    def __call__(self, srv_com, cur_ns):
        srv_com["local_time"] = int(time.time())
    def interpret(self, srv_com, cur_ns):
        warn_diff, err_diff = (10, 5 * 60)
        local_date = time.time()
        remote_date = int(srv_com["local_time"].text)
        diff_time = int(abs(remote_date - local_date))
        if diff_time > err_diff:
            return limits.nag_STATE_CRITICAL, "%s (diff %d > %d seconds)" % (time.ctime(remote_date),
                                                                              diff_time,
                                                                              err_diff)
        elif diff_time > warn_diff:
            return limits.nag_STATE_WARNING, "%s (diff %d > %d seconds)" % (time.ctime(remote_date),
                                                                                  diff_time,
                                                                                  warn_diff)
        else:
            return limits.nag_STATE_OK, "OK: %s" % (time.ctime(remote_date))
    def interpret_old(self, result, parsed_coms):
        warn_diff, err_diff = (10, 5 * 60)
        local_date = time.time()
        remote_date = hm_classes.net_to_sys(result[3:])["date"]
        if type(remote_date) == type(""):
            remote_date = time.mktime(time.strptime(remote_date))
        diff_time = int(abs(remote_date - local_date))
        if diff_time > err_diff:
            return limits.nag_STATE_CRITICAL, "ERROR: %s (diff %d > %d seconds)" % (time.ctime(remote_date),
                                                                                    diff_time,
                                                                                    err_diff)
        elif diff_time > warn_diff:
            return limits.nag_STATE_WARNING, "WARN: %s (diff %d > %d seconds)" % (time.ctime(remote_date),
                                                                                  diff_time,
                                                                                  warn_diff)
        else:
            return limits.nag_STATE_OK, "OK: %s" % (time.ctime(remote_date))

class general_command(hm_classes.hmb_command):
    def __init__(self, **args):
        hm_classes.hmb_command.__init__(self, "general", **args)
        self.help_str = "returns an overview of the host"
        self.short_client_info = "-A -l -u -i -k -d"
        self.long_client_info = "Show (A)ll, (l)oad, (u)ptime, (i)mage, (k)ernel, (d)ate"
        self.short_client_opts = "Aluikd"
    def server_call(self, cm):
        big_dict = {}
        for com_ent in [machinfo_command, date_command, uptime_command, load_command, sysinfo_command]:
            local_result = com_ent(module=self.module_info)("general %s" % (" ".join(cm)), self.logger, addr=("local", 0))
            what_dict = hm_classes.net_to_sys(local_result[3:])
            for key in what_dict.keys():
                big_dict[key] = what_dict[key]
        return "ok %s" % (hm_classes.sys_to_net(big_dict))
    def client_call(self, result, parsed_coms):
        lim = parsed_coms[0]
        cmm = hm_classes.net_to_sys(result[3:])
        out_field = []
        #print cmm
        if lim.get_add_flag("k"):
            out_field.append("Linux %-14s" % ("%(kernel_version)s (%(arch)s)" % cmm))
        if lim.get_add_flag("i"):
            if cmm.has_key("imageinfo"):
                if cmm["imageinfo"].has_key("image_name") and cmm["imageinfo"].has_key("image_version"):
                    image_field = ["%(image_name)s %(image_version)s" % cmm["imageinfo"]]
            else:
                image_field = ["<no imageinfo>"]
            image_field.append("(%(vendor)s %(version)s)" % cmm)
            out_field.append(" ".join(image_field))
        if lim.get_add_flag("d"):
            out_field.append("%(date)s" % cmm)
        if lim.get_add_flag("u"):
            out_field.append("up for %(up_days)3s days %(up_hours)2s:%(up_minutes)02d" % cmm)
        if lim.get_add_flag("l"):
            out_field.append("load %(load1)5s %(load5)5s %(load15)5s" % cmm)
        return limits.nag_STATE_OK, "; ".join(out_field)#"%s (%s); %s; %s" % (kernel_str, ", ".join(image_field), up_str, load_str)

class hwinfo_command(hm_classes.hmb_command):
    def __init__(self, **args):
        hm_classes.hmb_command.__init__(self, "hwinfo", **args)
        self.help_str = "returns hardware and pci specific information"
        self.short_client_info = "-r, --raw"
        self.long_client_info = "sets raw-output (for scripts)"
        self.short_client_opts = "r"
        self.long_client_opts = ["raw"]
    def server_call(self, cm):
        src_addr = ("local", 0)
        full_com = "hwinfo %s" % (" ".join(cm))
        return "ok %s" % (hm_classes.sys_to_net({"mach" : machinfo_command(module=self.module_info)(full_com, self.logger, addr=src_addr),
                                                 "pci"  : pciinfo_command(module=self.module_info)(full_com, self.logger, addr=src_addr),
                                                 "mac"  : macinfo_command(module=self.module_info)(full_com, self.logger, addr=src_addr),
                                                 "dmi"  : dmiinfo_command(module=self.module_info)(full_com, self.logger, addr=src_addr),
                                                 "uuid" : uuid_tools.get_uuid().get_urn()}))
    def client_call(self, result, parsed_coms):
        lim = parsed_coms[0]
        raw_output = lim.get_add_flag("R")
        if raw_output:
            return limits.nag_STATE_OK, result[3:]
        else:
            cmr = hm_classes.net_to_sys(result[3:])
            mi_s, mi_o = machinfo_command().client_call(cmr["mach"], parsed_coms)
            pci_s, pci_o = pciinfo_command().client_call(cmr["pci"], parsed_coms)
            return max(mi_s, pci_s), mi_o + pci_o

class macinfo_command(hm_classes.hm_command):
    def __call__(self, srv_com, cur_ns):
        valid_devs = ["eth", "myri", "ib", "vmnet"]
        net_dict = {}
        try:
            net_dir = "/sys/class/net"
            if os.path.isdir(net_dir):
                for net in [entry for entry in os.listdir(net_dir) if [True for postfix in valid_devs if entry.startswith(postfix)]]:
                    addr_file = "%s/%s/address" % (net_dir, net)
                    if os.path.isfile(addr_file):
                        net_dict[net.lower()] = open(addr_file, "r").read().strip().lower()
            else:
                c_stat, out = commands.getstatusoutput("ip link show")
                if not c_stat:
                    # ip link show successfull
                    head_match = re.compile("^(?P<idx>\d+):\s+(?P<devname>\S+):.*$")
                    tail_match = re.compile("^\s*(?P<bla>\S+)/(?P<blub>\S+)\s+(?P<macadr>\S+).*$")
                    act_name, act_mac = (None, None)
                    for hm, tm in [(head_match.match(entry), tail_match.match(entry)) for entry in [line.rstrip() for line in out.split("\n")]]:
                        if hm:
                            act_name, act_mac = (hm.group("devname").lower(), None)
                        elif tm:
                            act_mac = tm.group("macadr").lower()
                        if act_name and act_mac:
                            if [True for x in valid_devs if act_name.startswith(x)] and len(act_name.split(":")) == 1:
                                net_dict[act_name] = act_mac
                            act_name, act_mac = (None, None)
                else:
                    # try via ifconfig
                    net_match = re.compile("(?P<devname>\S+)\s+.*addr\s+(?P<macadr>\S+)\s*$")
                    c_stat, out = commands.getstatusoutput("/sbin/ifconfig -a")
                    if not c_stat:
                        for act_name, act_mac in [(entry.group("devname").lower(), entry.group("macadr").lower()) for entry in [net_match.match(line.strip()) for line in out.split("\n")] if entry]:
                            if [True for postfix in valid_devs if act_name.startswith(postfix)] and len(act_name.split(":")) == 1:
                                net_dict[act_name] = act_mac
        except:
            pass
        srv_com.set_dictionary("macinfo", net_dict)
    def interpret(self, srv_com, cur_ns):
        if "macinfo" in srv_com:
            mac_list = []
            for sub_el in srv_com["macinfo"]:
                mac_list.append("%s (%s)" % (sub_el.tag.split("}")[1], sub_el.text))
            return limits.nag_STATE_OK, "%s: %s" % (logging_tools.get_plural("device", len(mac_list)),
                                                    ", ".join(sorted(mac_list)))
        else:
            return limits.nag_STATE_CRITICAL, "no macaddresses found"
    def interpret_old(self, result, parsed_coms):
        if result.startswith("ok"):
            net_dict = hm_classes.net_to_sys(result[3:])
            return limits.nag_STATE_OK, "%d ether-devices found: %s" % (len(net_dict.keys()), ", ".join(["%s (%s)" % (k, net_dict[k]) for k in net_dict.keys()]))
        else:
            return limits.nag_STATE_CRITICAL, "error parsing return"

class umount_command(hm_classes.hmb_command):
    def __init__(self, **args):
        hm_classes.hmb_command.__init__(self, "umount", **args)
        self.help_str = "unmounts all unused nfs-mounts"
    def server_call(self, cm):
        ignore_list = [x.strip() for x in cm if x.strip()]
        mount_dict = get_nfs_mounts()
        auto_list = [m_point for src, m_point in mount_dict.get("autofs", [])]
        if mount_dict and auto_list:
            ok_list, err_list = ([], [])
            for src, m_point in mount_dict.get("nfs", []):
                # mount points must not be in ignore list and have to be below an automount-directory
                if not [True for ignore_part in ignore_list if m_point.startswith(ignore_part)] and [True for a_mpoint in auto_list if m_point.startswith(a_mpoint)]:
                    stat, out = commands.getstatusoutput("umount %s" % (m_point))
                    if stat:
                        # unify out-lines
                        out_l = []
                        for line in [x.startswith(m_point) and x[len(m_point) + 1:].strip() or x for x in [y.startswith("umount:") and y[7:].strip() or y.strip() for y in out.split("\n")]]:
                            if line not in out_l:
                                out_l.append(line)
                        err_list.append((src, m_point, stat, " ".join(out_l)))
                        self.log("umounting %s: %s (%d)" % (m_point, " ".join(out_l), stat),
                                 logging_tools.LOG_LEVEL_ERROR)
                    else:
                        ok_list.append((src, m_point))
                        self.log("ok umounting %s" % (m_point))
            ok_list.sort()
            err_list.sort()
            return "ok %s" % (hm_classes.sys_to_net({"ok_list"  : ok_list,
                                                     "err_list" : err_list}))
        else:
            return "ok %s" % (hm_classes.sys_to_net({}))
    def client_call(self, result, parsed_coms):
        if result.startswith("ok "):
            um_dict = hm_classes.net_to_sys(result[3:])
            str_f = []
            ret_state = limits.nag_STATE_OK
            if um_dict.get("ok_list", []):
                str_f.append("%s: %s" % (logging_tools.get_plural("ok umount", len(um_dict["ok_list"])),
                                         ", ".join(["%s from %s" % (x[1], x[0]) for x in um_dict["ok_list"]])))
            if um_dict.get("err_list", []):
                ret_state = limits.nag_STATE_WARNING
                str_f.append("%s: %s" % (logging_tools.get_plural("error umount", len(um_dict["err_list"])),
                                         ", ".join(["%s from %s (%d, %s)" % (x[1], x[0], x[2], x[3]) for x in um_dict["err_list"]])))
            if not str_f:
                str_f.append("nothing to umount")
            return ret_state, "; ".join(str_f)
        else:
            return limits.nag_STATE_CRITICAL, "error: %s" % (result)

class pciinfo_command(hm_classes.hm_command):
    def __call__(self, srv_com, cur_ns):
        srv_com.set_dictionary("pci", pci_database.get_actual_pci_struct(*pci_database.get_pci_dicts()))
    def interpret(self, srv_com, cur_ns):
        def _short(in_tag):
            return in_tag.split("}")[1]
        def _short_tag(in_el):
            return int(_short(in_el.tag)[1:])
        cmr_b = []
        for domain in srv_com["pci"]:
            for bus in domain:
                for slot in bus:
                    for func in slot:
                        s_dict = dict([(_short(cur_el.tag), cur_el.text) for cur_el in func])
                        out_str = "%04x:%02x:%02x.%x %s: %s %s" % (_short_tag(domain), _short_tag(bus), _short_tag(slot), _short_tag(func),
                                                                   s_dict["subclassname"],
                                                                   s_dict["vendorname"],
                                                                   s_dict["devicename"])
                        if s_dict["revision"] != "00":
                            out_str = "%s (rev %s)" % (out_str, s_dict["revision"])
                        cmr_b.append(out_str)
        return limits.nag_STATE_OK, "\n".join(cmr_b)

class machinfo_command(hm_classes.hmb_command):
    def __init__(self, **args):
        hm_classes.hmb_command.__init__(self, "machinfo", **args)
        self.help_str = "returns hardware specific information"
        self.short_client_info = "-r, --raw"
        self.long_client_info = "sets raw-output (for scripts) or list-mode"
        self.short_client_opts = "r"
        self.long_client_opts = ["raw"]
    def server_call(self, cm):
        hw_dict = {}
        hw_dict["hostname"] = posix.environ["HOSTNAME"]
        if posix.environ.has_key("MACHTYPE"):
            hw_dict["machine_type"] = posix.environ["MACHTYPE"].split("-")[0]
        else:
            hw_dict["machine_type"] = "i686"
        try:
            meml = open("/proc/meminfo", "r").read().split("\n")
            pcid = pci_database.get_actual_pci_struct(self.module_info.vdict, self.module_info.cdict)
            partl = open("/proc/partitions", "r").read().split("\n")
            hw_dict["kernel_version"] = open("/proc/sys/kernel/osrelease", "r").read().split("\n")[0]
            devl = open("/proc/devices", "r").read().split("\n")
            while not devl[0].lower().startswith("block"):
                del devl[0]
            del devl[0]
            ide_devl, scsi_l_devl, scsi_devl = ([], [], [])
            for dev in devl:
                devi = dev.strip().split()
                if len(devi) > 1:
                    if re.match("ide.*", devi[1]):
                        ide_devl.append(int(devi[0]))
                    elif re.match("(sd|ida|cciss).*", devi[1]):
                        scsi_l_devl.append((int(devi[0]), devi[1]))
                        scsi_devl.append(int(devi[0]))
            ide_hdl, ide_cdl = ([], [])
            try:
                idedn = "/proc/ide"
                for entr in os.listdir(idedn):
                    fn = "%s/%s" % (idedn, entr)
                    if os.path.islink(fn):
                        fn = os.readlink(fn)
                        drive = os.path.basename(fn)
                        media = open("%s/%s/media" % (idedn, fn), "r").read().split("\n")[0].strip()
                        if media == "cdrom":
                            ide_cdl.append(drive)
                        elif media == "disk":
                            ide_hdl.append(drive)
            except:
                pass
        except:
            return "error %s" % (process_tools.get_except_info())
        hw_dict["cpus"] = self.module_info._cpuinfo_int()
        memd = self.module_info._mem_int()
        hw_dict["mem_total"] = memd["memtotal"]
        hw_dict["swap_total"] = memd["swaptotal"]
        gfx = "<UNKNOWN / not set>"
        for pd in pcid.keys():
            for k0 in pcid[pd].keys():
                for k1 in pcid[pd][k0].keys():
                    for k2 in pcid[pd][k0][k1].keys():
                        actd = pcid[pd][k0][k1][k2]
                        dev_str = "%s (rev %s)" % (actd.get("devicename", "<no key devicename>"), actd.get("revision", "<no key revision>"))
                        if actd["class"] == "03":
                            gfx = dev_str
        hw_dict["gfx"] = gfx
        num_hd, num_cd = (len(ide_hdl), len(ide_cdl))
        num_str = 0
        try:
            scsil = open("/proc/scsi/scsi", "r").readlines()
        except:
            scsil = []
        channel, id_num, lun = (0, 0, 0)
        for line in scsil:
            lm = re.match("^.*ost:\s+\S+\s+.*annel:\s+(\d+)\s+.*d:\s+(\d+)\s+.*un:\s+(\d+).*$", line)
            if lm:
                channel = abs(int(lm.group(1)))
                id_num = abs(int(lm.group(2)))
                lun = abs(int(lm.group(3)))
            lm = re.match("^\s+Type:\s+([\S]+).*$", line)
            if lm:
                if lm.group(1) == "Direct-Access":
                    num_hd += 1
                elif lm.group(1) == "CD-ROM":
                    # removed as of 20.2.2008
                    #if channel + id_num + lun > 0:
                    num_cd += 1
                    channel = 0
                    id_num = 0
                    lun = 0
                elif lm.group(1) == "Sequential-Access":
                    num_str += 1
        size_hd = 0
        for major, name in scsi_l_devl:
            sn = re.match("^([a-z]+).*$", name)
            if sn:
                if sn.group(1) == "cciss":
                    drv_dir = "cciss"
                elif sn.group(1) == "ida":
                    drv_dir = "cpqarray"
                else:
                    drv_dir = None
                if drv_dir:
                    try:
                        snf = open("/proc/driver/%s/%s" % (drv_dir, name), "r").read().split("\n")
                    except:
                        pass
                    else:
                        for snl in snf:
                            if snl.startswith("cciss/c"):
                                # cciss part
                                num_hd += 1
                                size_str = snl.split()[1]
                                size_hd += float(size_str[:-2]) * {"k" : 1000,
                                                                   "m" : 1000 * 1000,
                                                                   "g" : 1000 * 1000 * 1000,
                                                                   "t" : 1000 * 1000 * 1000 * 1000}.get(size_str[-2].lower(), 1) / (1000 * 1000)
                            else:
                                snfm = re.match("^.*:[^=]+=(\d+)[^=]+=(\d+)$", snl)
                                if snfm:
                                    mb = int(float(snfm.group(1)) * float(snfm.group(2)) / (1000. * 1000.))
                                    size_hd += mb
                                    num_hd += 1
        for line in partl:
            lm = re.match("^\s*(\d+)\s+(\d+)\s+(\d+)\s+(\D+)(\s+.*$|$)", line)
            if lm:
                major = int(lm.group(1))
                minor = int(lm.group(2))
                size  = int(lm.group(3))
                part  = lm.group(4)
                if major in ide_devl:
                    if part in ide_hdl:
                        size_hd = size_hd + size / 1000
                elif major in scsi_devl:
                    size_hd = size_hd + size / 1000
        hw_dict["num_ro"] = num_cd
        hw_dict["num_rw"] = num_hd
        hw_dict["rw_size"] = float(size_hd / 1000.)
        #print hw_dict
        return "ok %s" % (hm_classes.sys_to_net(hw_dict))
    def client_call(self, result, parsed_coms):
        lim = parsed_coms[0]
        raw_output = lim.get_add_flag("R")
        if raw_output:
            return limits.nag_STATE_OK, result[3:]
        else:
            cmr = hm_classes.net_to_sys(result[3:])
            cpu_info = cmr["cpus"]
            if type(cpu_info) == type([]):
                # old cpu_info
                return limits.nag_STATE_OK, "%1d %25s, %4s MHz , %4.0f MB, %6.2f MB Swap, %7d GB on %2d disk, %2d CD-Rom, Gfx: %-20s" % (len(cpu_info),
                                                                                                                                         trim_string(str(cpu_info[0].get("type", "not_set"))),
                                                                                                                                         cpu_info[0].get("speed", 0),
                                                                                                                                         cmr["mem_total"] / 1024.,
                                                                                                                                         cmr["swap_total"] / 1024.,
                                                                                                                                         cmr["rw_size"],
                                                                                                                                         cmr["num_rw"],
                                                                                                                                         cmr["num_ro"],
                                                                                                                                         cmr["gfx"])
            else:
                cpu_info["parse"] = True
                cpu_info = cpu_database.global_cpu_info(**cpu_info)
                # new cpu_info
                first_cpu = cpu_info[cpu_info.cpu_idxs()[0]]
                return limits.nag_STATE_OK, "%1d %25s, %4s MHz , %4.0f MB, %6.2f MB Swap, %7d GB on %2d disk, %2d CD-Rom, Gfx: %-20s" % (cpu_info.num_cores(),
                                                                                                                                         trim_string(first_cpu.get("model name", "unknown brand")),
                                                                                                                                         first_cpu.get("speed", 0),
                                                                                                                                         cmr["mem_total"] / 1024.,
                                                                                                                                         cmr["swap_total"] / 1024.,
                                                                                                                                         cmr["rw_size"],
                                                                                                                                         cmr["num_rw"],
                                                                                                                                         cmr["num_ro"],
                                                                                                                                         cmr["gfx"])

class cpuflags_command(hm_classes.hm_command):
    def __call__(self, srv_com, cur_ns):
        srv_com["proclines"] = server_command.compress(file("/proc/cpuinfo", "r").read())
    def interpret(self, srv_com, cur_ns):
        # most likely source: http://www.softeng.rl.ac.uk/st/archive/SoftEng/SESP/html/SoftwareTools/vtune/users_guide/mergedProjects/analyzer_ec/mergedProjects/reference_olh/mergedProjects/instructions/instruct32_hh/vc46.htm
        flag_lut = {"FPU"    : "Floating Point Unit On-Chip. The processor contains an x87 FPU.",
                    "VME"    : "Virtual 8086 Mode Enhancements. Virtual 8086 mode enhancements, including CR4.VME for controlling the feature, CR4.PVI for protected mode virtual interrupts, software interrupt indirection, expansion of the TSS with the software indirection bitmap, and EFLAGS.VIF and EFLAGS.VIP flags.",
                    "DE"     : "Debugging Extensions. Support for I/O breakpoints, including CR4.DE for controlling the feature, and optional trapping of accesses to DR4 and DR5.",
                    "PSE"    : "Page Size Extension. Large pages of size 4Mbyte are supported, including CR4.PSE for controlling the feature, the defined dirty bit in PDE (Page Directory Entries), optional reserved bit trapping in CR3, PDEs, and PTEs.",
                    "TSC"    : "Time Stamp Counter. The RDTSC instruction is supported, including CR4.TSD for controlling privilege.",
                    "MSR"    : "Model Specific Registers RDMSR and WRMSR Instructions. The RDMSR and WRMSR instructions are supported. Some of the MSRs are implementation dependent.",
                    "PAE"    : "Physical Address Extension. Physical addresses greater than 32 bits are supported: extended page table entry formats, an extra level in the page translation tables is defined, 2 Mbyte pages are supported instead of 4 Mbyte pages if PAE bit is 1. The actual number of address bits beyond 32 is not defined, and is implementation specific.",
                    "MCE"    : "Machine Check Exception. Exception 18 is defined for Machine Checks, including CR4.MCE for controlling the feature. This feature does not define the model-specific implementations of machine-check error logging, reporting, and processor shutdowns. Machine Check exception handlers may have to depend on processor version to do model specific processing of the exception, or test for the presence of the Machine Check feature.",
                    "CX8"    : "CMPXCHG8B Instruction. The compare-and-exchange 8 bytes (64 bits) instruction is supported (implicitly locked and atomic).",
                    "APIC"   : "APIC On-Chip. The processor contains an Advanced Programmable Interrupt Controller (APIC), responding to memory mapped commands in the physical address range FFFE0000H to FFFE0FFFH (by default - some processors permit the APIC to be relocated).",
                    "SEP"    : "SYSENTER and SYSEXIT Instructions. The SYSENTER and SYSEXIT and associated MSRs are supported.",
                    "MTRR"   : "Memory Type Range Registers. MTRRs are supported. The MTRRcap MSR contains feature bits that describe what memory types are supported, how many variable MTRRs are supported, and whether fixed MTRRs are supported.",
                    "PGE"    : "PTE Global Bit. The global bit in page directory entries (PDEs) and page table entries (PTEs) is supported, indicating TLB entries that are common to different processes and need not be flushed. The CR4.PGE bit controls this feature.",
                    "MCA"    : "Machine Check Architecture. The Machine Check Architecture, which provides a compatible mechanism for error reporting in P6 family, Pentium 4, and Intel Xeon processors is supported. The MCG_CAP MSR contains feature bits describing how many banks of error reporting MSRs are supported.",
                    "CMOV"   : "Conditional Move Instructions. The conditional move instruction CMOV is supported. In addition, if x87 FPU is present as indicated by the CPUID.FPU feature bit, then the FCOMI and FCMOV instructions are supported.",
                    "PAT"    : "Page Attribute Table. Page Attribute Table is supported. This feature augments the Memory Type Range Registers (MTRRs), allowing an operating system to specify attributes of memory on a 4K granularity through a linear address.",
                    "PSE-36" : "32-Bit Page Size Extension. Extended 4-MByte pages that are capable of addressing physical memory beyond 4 GBytes are supported. This feature indicates that the upper four bits of the physical address of the 4-MByte page is encoded by bits 13-16 of the page directory entry.",
                    "PSN"    : "Processor Serial Number. The processor supports the 96-bit processor identification number feature and the feature is enabled.",
                    "CLFLSH" : "CLFLUSH Instruction. CLFLUSH Instruction is supported.",
                    "DS"     : "Debug Store. The processor supports the ability to write debug information into a memory resident buffer. This feature is used by the branch trace store (BTS) and precise event-based sampling (PEBS) facilities (see Chapter 15, Debugging and Performance Monitoring, in the IA-32 Intel Architecture Software Developer's Manual, Volume 3).",
                    "ACPI"   : "Thermal Monitor and Software Controlled Clock Facilities. The processor implements internal MSRs that allow processor temperature to be monitored and processor performance to be modulated in predefined duty cycles under software control.",
                    "MMX"    : "Intel MMX Technology. The processor supports the Intel MMX technology.",
                    "FXSR"   : "FXSAVE and FXRSTOR Instructions. The FXSAVE and FXRSTOR instructions are supported for fast save and restore of the floating point context. Presence of this bit also indicates that CR4.OSFXSR is available for an operating system to indicate that it supports the FXSAVE and FXRSTOR instructions.",
                    "SSE"    : "SSE. The processor supports the SSE extensions.",
                    "SSE2"   : "SSE2. The processor supports the SSE2 extensions.",
                    "SS"     : "Self Snoop. The processor supports the management of conflicting memory types by performing a snoop of its own cache structure for transactions issued to the bus.",
                    "HTT"    : "Hyper-Threading Technology. The processor implements Hyper-Threading technology.",
                    "TM"     : "Thermal Monitor. The processor implements the thermal monitor automatic thermal control circuitry (TCC).",
                    "PBE"    : "Pending Break Enable. The processor supports the use of the FERR#/PBE# pin when the processor is in the stop-clock state (STPCLK# is asserted) to signal the processor that an interrupt is pending and that the processor should return to normal operation to handle the interrupt. Bit 10 (PBE enable) in the IA32_MISC_ENABLE MSR enables this capability."}
        flag_dict = {}
        for line in server_command.decompress(srv_com["proclines"].text).split("\n"):
            if line.count(":"):
                key, value = [part.strip() for part in line.split(":", 1)]
                if key == "processor":
                    cpu_num = int(value)
                elif key == "flags":
                    flag_dict[cpu_num] = sorted(value.split())
        ret_lines = ["found %s:" % (logging_tools.get_plural("CPU", len(flag_dict.keys())))]
        for cpu_num in sorted(flag_dict.keys()):
            cpu_flags = flag_dict[cpu_num]
            ret_lines.append("CPU %2d: %s" % (cpu_num, logging_tools.get_plural("flag", len(cpu_flags))))
            for flag in cpu_flags:
                ret_lines.append("  %-15s : %s" % (flag, flag_lut.get(flag.upper(), flag)[:140]))
        ret_state = limits.nag_STATE_OK
        return ret_state, "\n".join(ret_lines)
        
class cpuinfo_command(hm_classes.hm_command):
    def __call__(self, srv_com, cur_ns):
        srv_com["cpuinfo"] = self.module._cpuinfo_int(srv_com)
    def interpret(self, srv_com, cur_ns):
        ret_state, pre_str = (limits.nag_STATE_OK, "OK")
        header_errors = []
        out_list = logging_tools.new_form_list()
        try:
            cpu_info = cpu_database.global_cpu_info(xml=srv_com.tree, parse=True)
        except:
            join_str, head_str = ("; ", "error decoding cpu_info: %s" % (process_tools.get_except_info()))
            exc_info = process_tools.exception_info()
            print "\n".join(exc_info.log_lines)
        else:
            for cpu in [cpu_info[cpu_idx] for cpu_idx in cpu_info.cpu_idxs()]:
                if cpu.get("online", True):
                    cpu_speed = cpu["speed"]
                    bnd_str = ""
                    #if cpu_range.has_boundaries_set():
                    #    if cpu_range.in_boundaries(cpu_speed):
                    #        bnd_str = "(in range [%d, %d])" % (cpu_range.get_lower_boundary(), cpu_range.get_upper_boundary())
                    #    else:
                    #        ret_state, pre_str = (limits.nag_STATE_CRITICAL, "Error")
                    #        bnd_str = "(not in range [%d, %d])" % (cpu_range.get_lower_boundary(), cpu_range.get_upper_boundary())
                    #        header_errors.append("core %d (%d) not in range [%d, %d]" % (cpu["core_num"], cpu_speed, cpu_range.get_lower_boundary(), cpu_range.get_upper_boundary()))
                    out_list.append([logging_tools.form_entry(cpu["core_num"], header="core"),
                                     logging_tools.form_entry(cpu_speed, header="speed"),
                                     logging_tools.form_entry(cpu["socket_num"], header="socket"),
                                     logging_tools.form_entry(cpu.get_cache_info_str(), header="cache"),
                                     logging_tools.form_entry(cpu["cpu_id"], header="cpu_id"),
                                     logging_tools.form_entry(trim_string(cpu.get("model name", "unknown brand")), header="brand"),
                                     logging_tools.form_entry(bnd_str, header="problems")])
                else:
                    out_list.append([logging_tools.form_entry(cpu["core_num"], header="core"),
                                     logging_tools.form_entry(0, header="speed"),
                                     logging_tools.form_entry(0, header="socket"),
                                     logging_tools.form_entry("---", header="cache"),
                                     logging_tools.form_entry("---", header="cpu_id"),
                                     logging_tools.form_entry("---", header="brand"),
                                     logging_tools.form_entry("offline")])
            join_str, head_str = ("\n", "%s: %s, %s%s" % (pre_str,
                                                          logging_tools.get_plural("socket", cpu_info.num_sockets()),
                                                          logging_tools.get_plural("core", cpu_info.num_cores()),
                                                          ", %s" % (", ".join(header_errors)) if header_errors else ""))
        return ret_state, join_str.join([head_str] + str(out_list).split("\n"))#ret_f)

class lvminfo_command(hm_classes.hm_command):
    def __call__(self, srv_com, cur_ns):
        self.module.local_lvm_info.update()
        srv_com["lvm_dict"] = server_command.compress(self.module.local_lvm_info.generate_send_dict(), pickle=True)
    def interpret(self, srv_com, cur_ns):
        lvm_dict = server_command.decompress(srv_com["lvm_dict"].text, pickle=True)
        print lvm_dict
        lv_stuff = partition_tools.lvm_struct("dict", source_dict=lvm_dict)
        if lv_stuff.lvm_present:
            lv_elements = ["pv", "vg", "lv"]
            if True:#list_mode:
                out_f = ["%s:" % (", ".join([logging_tools.get_plural("%s element" % (lv_element), len(lv_stuff.lv_dict.get(lv_element, {}).keys())) for lv_element in lv_elements]))]
                for lv_element in lv_elements:
                    act_el_dict = lv_stuff.lv_dict.get(lv_element, {})
                    for el_name, act_el in act_el_dict.iteritems():
                        out_f.append("%s %-20s: %s" % (lv_element, el_name, act_el["uuid"]))
                return limits.nag_STATE_OK, "ok %s" % ("\n".join(out_f))
            else:
                return limits.nag_STATE_OK, "ok %s" % (lv_stuff.get_info())
        else:
            return limits.nag_STATE_OK, "ok no LVM-binaries found"

class partinfo_command(hm_classes.hm_command):
    def __call__(self, srv_com, cur_ns):
        self.module.local_lvm_info.update()
        ret_str, dev_dict, sys_dict = self.module._partinfo_int()
        srv_com["ret_str"] = ret_str
        srv_com["dev_dict"] = server_command.compress(dev_dict, marshal=True)
        srv_com["sys_dict"] = server_command.compress(sys_dict, marshal=True)
        srv_com["lvm_dict"] = server_command.compress(self.module.local_lvm_info.generate_send_dict(), pickle=True)
    def interpret(self, srv_com, cur_ns):
        dev_dict, sys_dict, lvm_dict = (server_command.decompress(srv_com["dev_dict"].text, marshal=True),
                                        server_command.decompress(srv_com["sys_dict"].text, marshal=True),
                                        server_command.decompress(srv_com["lvm_dict"].text, pickle=True))
        lvm_stuff = partition_tools.lvm_struct("dict", source_dict=lvm_dict)
        all_disks = sorted(dev_dict.keys())
        all_sys = sorted(sys_dict.keys())
        ret_f = ["found %s and %s:" % (logging_tools.get_plural("disc"         , len(all_disks)),
                                       logging_tools.get_plural("special mount", len(all_sys  )))]
        to_list = logging_tools.new_form_list()
        #to_list.set_format_string(2, pre_string="(", post_string=")")
        #to_list.set_format_string(3, left="", post_string=" MB,")
        ret_f.append("Partition overview")
        for disk in all_disks:
            all_parts = sorted(dev_dict[disk].keys())
            for part in all_parts:
                part_stuff = dev_dict[disk][part]
                part_name = "%s%s" % (disk, part)
                if part_stuff.has_key("mountpoint"):
                    mount_info = "fstype %s, opts %s, (%d/%d)" % (part_stuff["fstype"],
                                                                  part_stuff["options"],
                                                                  part_stuff["dump"],
                                                                  part_stuff["fsck"])
                else:
                    mount_info = ""
                lut_info = part_stuff.get("lut", None)
                if lut_info:
                    lut_keys = sorted(lut_info.keys())
                    lut_str = "; ".join(["%s: %s" % (lut_key, ",".join(sorted(lut_info[lut_key]))) for lut_key in lut_keys])
                else:
                    lut_str = "---"
                to_list.append([logging_tools.form_entry(part_name, header="partition"),
                                logging_tools.form_entry(part_stuff["hextype"], header="hex"),
                                logging_tools.form_entry(part_stuff["info"], header="info"),
                                logging_tools.form_entry_right(part_stuff["size"], header="size (MB)"),
                                logging_tools.form_entry(part_stuff.get("mountpoint", "none"), header="mountpoint"),
                                logging_tools.form_entry(mount_info, header="info"),
                                logging_tools.form_entry(lut_str, header="lut")])
        ret_f.extend(str(to_list).split("\n"))
        ret_f.append("System partition overview")
        to_list = logging_tools.new_form_list()
        for disk in all_sys:
            sys_stuff = sys_dict[disk]
            if type(sys_stuff) == type({}):
                sys_stuff = [sys_stuff]
            for s_stuff in sys_stuff:
                to_list.append([logging_tools.form_entry(disk, header="part"),
                                logging_tools.form_entry(s_stuff["fstype"], header="type"),
                                logging_tools.form_entry(s_stuff["options"], header="option"),
                                logging_tools.form_entry(s_stuff["mountpoint"], header="mountpoint")])
        ret_f.extend(str(to_list).split("\n"))
        if lvm_stuff.lvm_present:
            ret_f.append("lvminfo: %s" % (lvm_stuff.get_info()))
        return limits.nag_STATE_OK, "\n".join(ret_f)

class dmiinfo_command(hm_classes.hm_command):
    def __call__(self, srv_com, cur_ns):
        dmi_stat, dmi_result = commands.getstatusoutput("/opt/cluster/bin/dmidecode")
        with tempfile.NamedTemporaryFile()  as tmp_file:
            dmi_stat, dmi_result = commands.getstatusoutput("/opt/cluster/bin/dmidecode --dump-bin %s" % (tmp_file.name))
            srv_com["dmi_dump"] = server_command.compress(file(tmp_file.name, "r").read())
    def interpret(self, srv_com, cur_ns):
        with tempfile.NamedTemporaryFile()  as tmp_file:
            file(tmp_file.name, "w").write(server_command.decompress(srv_com["dmi_dump"].text))
            dmi_stat, dmi_result = commands.getstatusoutput("/opt/cluster/bin/dmidecode --from-dump %s" % (tmp_file.name))
            # decode dmi-info
            dec_lines = []
            for line in dmi_result.split("\n"):
                n_level = 0
                while line.startswith("\t"):
                    n_level += 1
                    line = line[1:]
                line = line.strip()
                dec_lines.append((n_level, line))
            dmi_struct = {"info"    : [],
                          "handles" : []}
            # info
            while True:
                if dec_lines[0][1].lower().startswith("handle"):
                    break
                n_level, line = dec_lines.pop(0)
                if not line:
                    break
                else:
                    dmi_struct["info"].append(line)
            # handles
            while True:
                n_level, h_info = dec_lines.pop(0)
                if h_info.lower().startswith("invalid"):
                    break
                if len(h_info.split(",")) < 3:
                    h_info = "%s, %s" % (h_info, dec_lines.pop(0)[1])
                top_level, info_str = dec_lines.pop(0)
                h_info_spl = [part.strip().split() for part in h_info.split(",")]
                handle_dict = {"info"     : info_str,
                               "handle"   : int(h_info_spl[0][1], 16),
                               "dmi_type" : int(h_info_spl[1][2]),
                               "length"   : int(h_info_spl[2][0]),
                               "content"  : {}}
                while True:
                    n_level, line = dec_lines.pop(0)
                    if n_level == top_level + 1:
                        try:
                            key, value = line.split(":", 1)
                        except:
                            self.log("error decoding dmi-line %s: %s" % (line,
                                                                         process_tools.get_except_info()),
                                     logging_tools.LOG_LEVEL_ERROR)
                        else:
                            handle_dict["content"][key.strip()] = value.strip()
                    elif n_level == top_level + 2:
                        if key and type(handle_dict["content"][key]) != type([]):
                            handle_dict["content"][key] = []
                        handle_dict["content"][key].append(line)
                    else:
                        while line.strip():
                            n_level, line = dec_lines.pop(0)
                        break
                dmi_struct["handles"].append(handle_dict)
                if handle_dict["dmi_type"] == 127:
                    break
            #pprint.pprint(dmi_struct)
            out_f = dmi_struct["info"]
            for handle in dmi_struct["handles"]:
                out_f.extend(["",
                              handle["info"]])
                for c_key in sorted(handle["content"].keys()):
                    c_value = handle["content"][c_key]
                    if type(c_value) == type([]):
                        out_f.append("    %s:" % (c_key))
                        for sub_value in c_value:
                            out_f.append("        %s" % (sub_value))
                    else:
                        out_f.append("    %s: %s" % (c_key, c_value))
            return limits.nag_STATE_OK, "ok %s" % ("\n".join(out_f))

# helper routines
def get_nfs_mounts():
    m_dict = {}
    try:
        for line in open("/proc/mounts", "r").read().split("\n"):
            line_split = line.strip().split()
            if len(line_split) == 6:
                m_dict.setdefault(line_split[2], []).append((line_split[0], line_split[1]))
    except:
        pass
    return m_dict

def sub_wrap(val_1, val_0):
    sub = val_1 - val_0
    while sub < 0:
        sub += sys.maxint
    if sub > sys.maxint / 8:
        sub = 0
    return sub

def trim_string(in_str):
    while in_str.count("  "):
        in_str = in_str.replace("  ", " ")
    return in_str.strip()
    
if __name__ == "__main__":
    print "This is a loadable module."
    sys.exit(0)
