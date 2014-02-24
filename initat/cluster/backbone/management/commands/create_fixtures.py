#!/usr/bin/python-init -Otu
#
# -*- coding: utf-8 -*-
#
# Copyright (C) 2013-2014 Andreas Lang-Nevyjel
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
""" creates the cluster fixtures """

from django.core.management.base import BaseCommand
from django.db.models import Q
from initat.cluster.backbone import factories

class Command(BaseCommand):
    option_list = BaseCommand.option_list
    help = ("Creates the cluster fixtures.")
    def handle(self, **options):
        print "creating fixtures..."
        # log source
        factories.LogSource(identifier="user", name="Cluster user", description="Clusteruser")
        # device type
        factories.DeviceType(identifier="H", description="Host", priority=0)
        factories.DeviceType(identifier="AM", description="APC Masterswitch", priority=10)
        factories.DeviceType(identifier="NB", description="Netbotz", priority=20)
        factories.DeviceType(identifier="S", description="Manageable Switch", priority= -10)
        factories.DeviceType(identifier="R", description="RAID box", priority= -20)
        factories.DeviceType(identifier="P", description="Printer", priority= -30)
        factories.DeviceType(identifier="MD", description="Meta device", priority=128)
        factories.DeviceType(identifier="IBC", description="IBM Blade center", priority= -40)
        factories.DeviceType(identifier="CD", description="Controlling Device", priority=30)
        # partition fs
        factories.PartitionFS(name="reiserfs", identifier="f", descr="ReiserFS Filesystem", hexid="83")
        factories.PartitionFS(name="ext2", identifier="f", descr="Extended 2 Fileystem", hexid="83")
        factories.PartitionFS(name="ext3", identifier="f", descr="Extended 3 Fileystem", hexid="83")
        factories.PartitionFS(name="ext4", identifier="f", descr="Extended 4 Fileystem", hexid="83")
        factories.PartitionFS(name="swap", identifier="s", descr="SwapSpace", hexid="82")
        factories.PartitionFS(name="ext", identifier="e", descr="Extended Partition", hexid="f")
        factories.PartitionFS(name="empty", identifier="d", descr="Empty Partition", hexid="0")
        factories.PartitionFS(name="lvm", identifier="l", descr="LVM Partition", hexid="8e")
        factories.PartitionFS(name="xfs", identifier="f", descr="XFS Filesystem", hexid="83")
        factories.PartitionFS(name="btrfs", identifier="f", descr="BTRFS Filesystem", hexid="83")
        factories.PartitionFS(name="ocfs2", identifier="f", descr="OCFS2 Filesystem", hexid="83")
        # log status
        factories.LogStatus(identifier="c", log_level=200, name="critical")
        factories.LogStatus(identifier="e", log_level=100, name="error")
        factories.LogStatus(identifier="w", log_level=50, name="warning")
        factories.LogStatus(identifier="i", log_level=0, name="info")
        factories.LogStatus(identifier="n", log_level= -50, name="notice")
        # hw entry type
        factories.HWEntryType(identifier="cpu", description="CPU", iarg0_descr="Speed in MHz", sarg0_descr="Model Type")
        factories.HWEntryType(identifier="mem", description="Memory", iarg0_descr="Physikal Memory", iarg1_descr="Virtual Memory")
        factories.HWEntryType(identifier="disks", description="Harddisks", iarg0_descr="Number of harddisks", iarg1_descr="total size")
        factories.HWEntryType(identifier="cdroms", description="CDRoms", iarg0_descr="Number of CD-Roms")
        factories.HWEntryType(identifier="gfx", description="Graphicscard", sarg0_descr="Type of Gfx")
        # status
        factories.Status(status="memtest", memory_test=True)
        factories.Status(status="boot_local", boot_local=True)
        factories.Status(status="boot_clean", prod_link=True, is_clean=True)
        factories.Status(status="installation_clean", prod_link=True, do_install=True, is_clean=True)
        factories.Status(status="boot", prod_link=True) # # FIXME ?
        factories.Status(status="installation", prod_link=True, do_install=True) # # FIXME ?
        # network device type
        factories.NetworkDeviceType(identifier="lo", name_re="^lo$", description="loopback devices", mac_bytes=6)
        factories.NetworkDeviceType(identifier="eth", name_re="^eth\d+$", description="ethernet devices", mac_bytes=6)
        factories.NetworkDeviceType(identifier="myri", name_re="^myri\d+$", description="myrinet devices", mac_bytes=6)
        factories.NetworkDeviceType(identifier="xenbr", name_re="^xenbr\d+$", description="xen bridge devices", mac_bytes=6)
        factories.NetworkDeviceType(identifier="tun", name_re="^tun\d+$", description="ethernet tunnel devices", mac_bytes=6)
        factories.NetworkDeviceType(identifier="ib", name_re="^ib\d+$", description="infiniband devices", mac_bytes=20)
        factories.NetworkDeviceType(identifier="bridge", name_re="^bridge\d+$", description="generic bridge", mac_bytes=6)
        factories.NetworkDeviceType(identifier="vlan", name_re="^vlan\d+$", description="VLAN device", mac_bytes=6)
        factories.NetworkDeviceType(identifier="en", name_re="^en(s|p)\d+$", description="Ethernet new scheme", mac_bytes=6)
        # network types
        factories.NetworkType(identifier="b", description="boot network")
        factories.NetworkType(identifier="p", description="production network")
        factories.NetworkType(identifier="s", description="slave network")
        factories.NetworkType(identifier="o", description="other network")
        factories.NetworkType(identifier="l", description="local network")
        # netdevice speed
        factories.NetDeviceSpeed(speed_bps=100000000, check_via_ethtool=True, full_duplex=True)
        factories.NetDeviceSpeed(speed_bps=100000000, check_via_ethtool=True, full_duplex=False)
        factories.NetDeviceSpeed(speed_bps=1000000000, check_via_ethtool=True, full_duplex=True)
        factories.NetDeviceSpeed(speed_bps=1000000000, check_via_ethtool=True, full_duplex=False)
        factories.NetDeviceSpeed(speed_bps=10000000000, check_via_ethtool=True, full_duplex=True)
        factories.NetDeviceSpeed(speed_bps=40000000000, check_via_ethtool=True, full_duplex=True)
        factories.NetDeviceSpeed(speed_bps=56000000000, check_via_ethtool=True, full_duplex=True)
        # host check command
        factories.HostCheckCommand(name="check-host-alive", command_line="$USER2$ -m localhost ping $HOSTADDRESS$ 5 5.0")
        factories.HostCheckCommand(name="check-host-alive-2", command_line="$USER2$ -m $HOSTADDRESS$ version")
        factories.HostCheckCommand(name="check-host-ok", command_line="$USER1$/check_dummy 0 up")
        factories.HostCheckCommand(name="check-host-down", command_line="$USER1$/check_dummy 2 down")
