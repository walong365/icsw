#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001,2002,2003,2004,2005 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# this file belongs to host-monitoring
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

import commands
import pprint

def main():
    IGNORE_LVM_PARTITIONS= 1
    read_err_list = []
    try:
        mount_list = [x.strip().split() for x in file("/proc/mounts", "r").read().split("\n") if x.strip()]
    except:
        read_err_list.append("/proc/mounts")
    try:
        devices_list = [x.strip().split() for x in file("/proc/devices", "r").read().split("\n") if x.strip()]
    except:
        read_err_list.append("/proc/devices")
    try:
        fstab_list = [x.strip().split() for x in file("/etc/fstab", "r").read().split("\n") if x.strip()]
    except:
        read_err_list.append("/etc/fstab")
    try:
        parts_list = [y[0 : 4] for y in [x.strip().split() for x in file("/proc/partitions", "r").read().split("\n") if x.strip()] if len(y) >= 4]
    except:
        read_err_list.append("/proc/partitions")
    try:
        real_root_dev = int(file("/proc/sys/kernel/real-root-dev", "r").read().strip())
    except:
        read_err_list.append("/proc/sys/kernel/real-root-dev")
    if read_err_list:
        ret_str = "error reading %s" % (" and ".join(read_err_list))
    else:
        # build devices-dict
        while 1:
            stuff = devices_list.pop(0)
            if stuff[0].lower().startswith("block"):
                break
        devices_dict = dict([(int(x), y) for x, y in devices_list])
        #print devices_dict
        # build partition-dict
        part_dict, dev_dict, real_root_dev_name = ({}, {}, None)
        for major, minor, blocks, part_name in parts_list:
            if major.isdigit() and minor.isdigit() and blocks.isdigit():
                major, minor = (int(major), int(minor))
                if major * 256 + minor == real_root_dev:
                    real_root_dev_name = part_name
                blocks = int(blocks)
                if not minor:
                    dev_dict["/dev/%s" % (part_name)] = {}
                part_dict.setdefault(major, {}).setdefault(minor, (part_name, blocks))
        if not real_root_dev_name:
            ret_str = "error determining real_root_device"
        else:
            # partition lookup dict
            part_lut = {}
            ret_str  = ""
            # fetch fdisk information
            for dev in dev_dict.keys():
                stat, out= commands.getstatusoutput("/sbin/fdisk -l %s" % (dev))
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
                    info    = " ".join(stuff)
                    if size.endswith("+"):
                        size = size[:-1]
                    start = int(start)
                    end   = int(start)
                    size  = int(size)/1000
                    hextype  = "0x%02x" % (int(hextype, 16))
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
                # drop unneeded entries
                real_mounts, sys_mounts = ([], [])
                sys_dict = {}
                for part, mp, fstype, opts, dump, fsck in mount_list:
                    if part == "rootfs" or part.startswith("automount(") or part.count(":"):
                        pass
                    else:
                        if part == "/dev/root":
                            part = "/dev/%s" % (real_root_dev_name)
                        if part.startswith("/"):
                            real_mounts.append((part, mp, fstype, opts, int(dump), int(fsck)))
                            if not part_lut.has_key(part):
                                if IGNORE_LVM_PARTITIONS:
                                    pass
                                else:
                                    raise ValueError, "partion %s not found (LVM?)" % (part)
                            else:
                                dev, part_num = part_lut[part]
                                dev_dict[dev][part_num]["mountpoint"] = mp
                                dev_dict[dev][part_num]["fstype"]     = fstype
                                dev_dict[dev][part_num]["options"]    = opts
                                dev_dict[dev][part_num]["dump"]       = int(dump)
                                dev_dict[dev][part_num]["fsck"]       = int(fsck)
                        else:
                            sys_mounts.append((part, mp, fstype, opts))
                            sys_dict[part] = {"mountpoint" : mp,
                                              "fstype"     : fstype,
                                              "options"    : opts}
                    
##                 print "\n".join([" ".join(x) for x in real_mounts])
##                 print "-"*10
##                 print "\n".join([" ".join(x) for x in sys_mounts])
##                 print "-"*10
##                 print "\n".join([" ".join(x) for x in fstab_list])
##                 print "-"*10
##                 print "\n".join([" ".join(x) for x in parts_list])
##                 print "-"*10
                pprint.pprint(dev_dict)
                pprint.pprint(sys_dict)
            
if __name__ == "__main__":
    main()
