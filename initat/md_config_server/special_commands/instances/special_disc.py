# Copyright (C) 2008-2015 Andreas Lang-Nevyjel, init.at
#
# this file is part of md-config-server
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
""" special call for disc monitoring """

from django.db.models import Q
from initat.cluster.backbone.models import partition, lvm_lv
from initat.md_config_server.special_commands.base import SpecialBase
from initat.tools import logging_tools


class special_disc(SpecialBase):
    class Meta:
        info = "Discs via collserver"
        command_line = "$USER2$ -m $HOSTADDRESS$ df -w ${ARG1:85} -c ${ARG2:95} $ARG3$"
        description = "queries the partition on the target system via collserver"

    def _call(self):
        part_dev = self.host.partdev
        first_disc = None
        part_list = []
        _po = partition.objects  # @UndefinedVariable
        for part_p in _po.filter(
            Q(partition_disc__partition_table=self.host.act_partition_table)
        ).select_related(
            "partition_fs"
        ).prefetch_related(
            "partition_disc"
        ).order_by(
            "partition_disc__disc",
            "pnum"
        ):
            act_disc, act_pnum = (part_p.partition_disc.disc, part_p.pnum)
            if not first_disc:
                first_disc = act_disc
            if act_disc == first_disc and part_dev:
                act_disc = part_dev
            if "dev/mapper" in act_disc:
                part_pf = "-part"
            elif "cciss" in act_disc or "ida" in act_disc:
                part_pf = "p"
            else:
                part_pf = ""
            if act_pnum:
                act_part = "{}{}{}".format(act_disc, part_pf, "{:d}".format(act_pnum) if act_pnum else "")
            else:
                # handle special case for unpartitioned disc
                act_part = act_disc
            if part_p.partition_fs.hexid == "82":
                # swap partiton
                self.log("ignoring {} (is swap)".format(act_part))
            else:
                # which partition to check
                check_part = act_part
                if check_part.startswith("/"):
                    warn_level, crit_level = (
                        part_p.warn_threshold,
                        part_p.crit_threshold)
                    warn_level_str, crit_level_str = (
                        "{:d}".format(warn_level if warn_level else 85),
                        "{:d}".format(crit_level if crit_level else 95))
                    if part_p.mountpoint.strip():
                        part_list.append(
                            (
                                part_p.mountpoint,
                                check_part,
                                warn_level_str,
                                crit_level_str
                            )
                        )
                else:
                    self.log(
                        "Diskcheck on host {} requested an illegal partition {} -> skipped".format(
                            self.host["name"],
                            act_part
                        ),
                        logging_tools.LOG_LEVEL_WARN
                    )
        # LVM-partitions
        for lvm_part in lvm_lv.objects.filter(Q(lvm_vg__partition_table=self.host.act_partition_table)).select_related("lvm_vg").order_by("name"):
            if lvm_part.mountpoint:
                warn_level, crit_level = (
                    lvm_part.warn_threshold or 0,
                    lvm_part.crit_threshold or 0
                )
                warn_level_str, crit_level_str = (
                    "{:d}".format(warn_level if warn_level else 85),
                    "{:d}".format(crit_level if crit_level else 95)
                )
                part_list.append(
                    (
                        "{} (LVM)".format(lvm_part.mountpoint),
                        "/dev/mapper/{}-{}".format(lvm_part.lvm_vg.name, lvm_part.name),
                        warn_level_str,
                        crit_level_str
                    )
                )
        # manual setting-dict for df
        sc_array = []
        for info_name, p_name, w_lev, c_lev in part_list:
            self.log(
                "  P: %-40s: %-40s (w: %-5s, c: %-5s)" % (
                    info_name,
                    p_name,
                    w_lev or "N/S",
                    c_lev or "N/S"
                )
            )
            sc_array.append(self.get_arg_template(info_name, arg3=p_name, w=w_lev, c=c_lev))
        return sc_array
