# Copyright (C) 2001-2008,2012-2017 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# this file is part of icsw-server-server
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
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
""" cluster-config-server, partition setup"""

import os

from initat.tools import logging_tools
from django.db.models import Q
from initat.cluster.backbone.models import partition, sys_partition


class icswPartitionSetup(object):
    def __init__(self, conf, log_com):
        self.__log_com = log_com
        self.__config = conf
        self._generate()

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_com("[PS] {}".format(what), log_level)

    def _generate(self):
        root_dev = None
        part_valid = False
        part_list = partition.objects.filter(
            Q(partition_disc__partition_table=self.__config.conf_dict["device"].partition_table)
        ).select_related(
            "partition_disc",
            "partition_disc__partition_table",
            "partition_fs",
        )
        if len(part_list):
            part_valid = True
            disc_dict, fstab, sfdisk, parted = ({}, [], [], [])
            fspart_dict = {}
            first_disc, root_part, root_part_type = (None, None, None)
            old_pnum, act_pnum = (0, 0)
            lower_size, upper_size = (0, 0)
            for cur_part in part_list:
                cur_disc = cur_part.partition_disc
                cur_pt = cur_disc.partition_table
                if root_dev is None:
                    root_dev = self.__config.conf_dict["device"].partdev
                    # partition prefix for cciss partitions
                    part_pf = "p" if root_dev.count("cciss") else ""
                is_valid, pt_name = (cur_pt.valid, cur_pt.name)
                if not is_valid:
                    part_valid = False
                    break
                act_pnum, act_disc = (cur_part.pnum, cur_disc.disc)
                if not first_disc:
                    first_disc = act_disc
                if act_disc == first_disc:
                    act_disc = root_dev
                fs_name = cur_part.partition_fs.name
                disc_dict.setdefault(act_disc, {})
                if act_pnum:
                    disc_dict[act_disc][act_pnum] = cur_part
                # generate sfdisk-entry
                while old_pnum < act_pnum - 1:
                    old_pnum += 1
                    sfdisk.append(",0, ")
                # ATTN: The unit of partition.size is bytes, however the file
                # system utilities expect MB.
                if cur_part and fs_name != "ext":
                    if cur_part.size:
                        upper_size += cur_part.size / (1024 ** 2)
                    else:
                        # to be replaced by stage2 by actual upper size
                        upper_size = 0
                else:
                    upper_size = 0
                parted.append(
                    "mkpart {} {} {} {}".format(
                        fs_name == "ext" and "extended" or (act_pnum < 5 and "primary" or "logical"),
                        {
                            "ext3": "ext2",
                            "ext4": "ext2",
                            "btrfs": "ext2",
                            "xfs": "ext2",
                            "biosboot": "",
                            "swap": "linux-swap",
                            "lvm": "ext2",
                            "ext": ""
                        }.get(fs_name, fs_name),
                        "{:d}".format(int(lower_size)),
                        fs_name == "ext" and "_" or ("{:d}".format(int(upper_size)) if upper_size else "_")
                    )
                )
                if fs_name == "lvm":
                    parted.append("set %d lvm on" % (act_pnum))
                if upper_size:
                    lower_size = upper_size
                else:
                    upper_size = lower_size
                if cur_part.size and fs_name != "ext":
                    sfdisk.append(
                        ",%d,0x%s" % (
                            cur_part.size / (1024 ** 2),
                            cur_part.partition_hex
                        )
                    )
                else:
                    sfdisk.append(",,0x%s" % (cur_part.partition_hex))
                fs = fs_name or "auto"
                if (cur_part.mountpoint and fs_name != "ext") or fs_name == "swap":
                    act_part = "%s%s%d" % (act_disc, part_pf, act_pnum)
                    mp = cur_part.mountpoint if cur_part.mountpoint else fs
                    if mp == "/":
                        root_part, root_part_type = (act_part, fs)
                    if fs not in fspart_dict:
                        fspart_dict[fs] = []
                    fspart_dict[fs].append(act_part)
                    fstab.append(
                        "%-20s %-10s %-10s %-10s %d %d" % (
                            act_part,
                            mp,
                            fs,
                            cur_part.mount_options and cur_part.mount_options or "rw",
                            cur_part.fs_freq,
                            cur_part.fs_passno,
                        )
                    )
                old_pnum = act_pnum
            self.log(
                "  creating partition info for partition_table '%s' (root_device %s, partition postfix is '%s')" % (
                    pt_name,
                    root_dev,
                    part_pf,
                )
            )
            if part_valid:
                for sys_part in sys_partition.objects.filter(Q(partition_table=self.__config.conf_dict["device"].partition_table)):
                    fstab.append("%-20s %-10s %-10s %-10s %d %d" % (
                        sys_part.name,
                        sys_part.mountpoint,
                        sys_part.name,
                        sys_part.mount_options and sys_part.mount_options or "rw",
                        0,
                        0))
                self.fspart_dict, self.root_part, self.root_part_type, self.fstab, self.sfdisk, self.parted = (
                    fspart_dict,
                    root_part,
                    root_part_type,
                    fstab,
                    sfdisk,
                    parted,
                )
                # logging
                for what, name in [
                    (fstab, "fstab "),
                    (sfdisk, "sfdisk"),
                    (parted, "parted")
                ]:
                    self.log("Content of %s (%s):" % (name, logging_tools.get_plural("line", len(what))))
                    for line_num, line in zip(range(len(what)), what):
                        self.log(" - {:3d} {}".format(line_num + 1, line))
            else:
                _err_str = "Partition-table '{}' is not valid".format(pt_name)
                self.log(_err_str, logging_tools.LOG_LEVEL_ERROR)
                raise ValueError(_err_str)
        else:
            _err_str = "Partition setup has no partitions on physical discs"
            self.log(_err_str, logging_tools.LOG_LEVEL_ERROR)
            raise ValueError(_err_str)

    def create_part_files(self, pinfo_dir):
        if self.fspart_dict:
            for pn, pp in self.fspart_dict.items():
                open("%s/%sparts" % (pinfo_dir, pn), "w").write("\n".join(pp + [""]))
            for file_name, content in [
                ("rootpart", self.root_part),
                ("rootparttype", self.root_part_type),
                ("fstab", "\n".join(self.fstab)),
                ("sfdisk", "\n".join(self.sfdisk)),
                ("parted", "\n".join(self.parted))
            ]:
                open(os.path.join(pinfo_dir, file_name), "w").write("{}\n".format(content))
