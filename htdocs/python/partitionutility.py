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
""" modify partition settings """

import functions
import html_tools
import tools
import cdef_basics
import logging_tools
import pprint
import re

def module_info():
    return {"pu" : {"description"           : "Partition configuration",
                    "enabled"               : 1,
                    "default"               : 0,
                    "left_string"           : "Partition utility",
                    "right_string"          : "Show and modify the various Partitions",
                    "priority"              : -100,
                    "capability_group_name" : "conf"}}

class new_sys_partition_vs(html_tools.validate_struct):
    def __init__(self, req):
        self.__sysfs_keys = ["proc",
                             "sysfs",
                             "debugfs",
                             "securityfs",
                             "usbfs",
                             "devpts",
                             "nfsd",
                             "rpc_pipefs",
                             "configfs"]
        self.__sysfs_dict = dict([(key, key) for key in self.__sysfs_keys])
        new_dict = {"mountpoint"    : {"he"  : html_tools.text_field(req, "syspm", size=127, display_len=32),
                                       "new" : True,
                                       "vf"  : self.validate_mountpoint,
                                       "def" : ""},
                    "name"          : {"he"  : html_tools.selection_list(req, "syspn", self.__sysfs_dict, sort_new_keys=True, initial_mode="n"),
                                       "vf"  : self.validate_name,
                                       "def" : self.__sysfs_keys[0]},
                    "mount_options" : {"he"  : html_tools.text_field(req, "syspo",  size=127, display_len=32),
                                       "vf"  : self.validate_mount_options,
                                       "def" : "rw"},
                    "del"           : {"he"  : html_tools.checkbox(req, "syspd", auto_reset=True),
                                       "del" : 1}}
        html_tools.validate_struct.__init__(self, req, "sys partition", new_dict)
    def validate_name(self):
        if self.new_val_dict["name"] in self.used_names:
            raise ValueError, "Type %s already used" % (self.new_val_dict["name"])
    def validate_mountpoint(self):
        np = self.new_val_dict["mountpoint"]
        if np.count(" ") or not np.startswith("/"):
            raise ValueError, "Mountpoint is not valid"
        if np in self.used_paths:
            raise ValueError, "Mountpoint %s already used" % (self.new_val_dict["mountpoint"])
    def validate_mount_options(self):
        pass

class new_disc_vs(html_tools.validate_struct):
    def __init__(self, req):
        new_dict = {"disc" : {"he"  : html_tools.text_field(req, "ndn", size=127, display_len=32),
                              "new" : True,
                              "vf"  : self.validate_disc,
                              "def" : ""},
                    "del"  : {"he"  : html_tools.checkbox(req, "discdel", auto_reset=True),
                              "del" : 1}}
        html_tools.validate_struct.__init__(self, req, "disc", new_dict)
    def validate_disc(self):
        n_dn = self.new_val_dict["disc"]
        if n_dn in self.used_discs:
            raise ValueError, "Disc %s already used" % (n_dn)
        if not n_dn.startswith("/dev/"):
            raise ValueError, "Discname  %s invalid (has to start with /dev/" % (n_dn)

class new_partition_vs(html_tools.validate_struct):
    def __init__(self, req, fs_tree):
        self.__fs_tree = fs_tree
        filesystem_ent = html_tools.selection_list(req, "fsfs", {0 : "not set"}, sort_new_keys=False)
        for key in self.__fs_tree.keys():
            p_fs = self.__fs_tree[key]
            filesystem_ent[p_fs.idx] = p_fs.name
        filesystem_ent.mode_is_normal()
        size_postfix = html_tools.selection_list(req, "fspf", {1 : "MB",
                                                               2 : "GB",
                                                               3 : "TB"}, sort_new_keys=True, initall_mode="n", auto_reset=True)
        fs_freq_ent = html_tools.selection_list(req, "fsfreq", {0 : "0",
                                                                1 : "1"}, sort_new_keys=False, initial_mode="n")
        fs_passno_ent = html_tools.selection_list(req, "fspassno", {0 : "0",
                                                                    1 : "1",
                                                                    2 : "2"}, sort_new_keys=False, initial_mode="n")
        self.__hex_dict = {int("00", 16) : "Empty",
                           int("01", 16) : "DOS 12-bit FAT",
                           int("02", 16) : "XENIX root",
                           int("03", 16) : "XENIX /usr",
                           int("04", 16) : "DOS 3.0+ 16-bit FAT (up to 32M)",
                           int("05", 16) : "DOS 3.3+ Extended Partition",
                           int("06", 16) : "DOS 3.31+ 16-bit FAT (over 32M)",
                           #int("07", 16) : "OS/2 IFS (e.g., HPFS)",
                           int("07", 16) : "Windows NT NTFS/Advanced Unix",
                           #int("07", 16) : "QNX2.x pre-1988 (see below under IDs 4d-4f)",
                           int("08", 16) : "OS/2 (v1.0-1.3 only)",
                           int("08", 16) : "AIX boot partition",
                           int("08", 16) : "SplitDrive",
                           int("08", 16) : "Commodore DOS",
                           int("08", 16) : "DELL partition spanning multiple drives",
                           int("08", 16) : "QNX 1.x and 2.x ('qny')",
                           int("09", 16) : "AIX data partition",
                           int("09", 16) : "Coherent filesystem",
                           int("09", 16) : "QNX 1.x and 2.x ('qnz')",
                           int("0a", 16) : "OS/2 Boot Manager",
                           int("0a", 16) : "Coherent swap partition",
                           int("0a", 16) : "OPUS",
                           int("0b", 16) : "WIN95 OSR2 32-bit FAT",
                           int("0c", 16) : "WIN95 OSR2 32-bit FAT, LBA-mapped",
                           int("0e", 16) : "WIN95: DOS 16-bit FAT, LBA-mapped",
                           int("0f", 16) : "WIN95: Extended partition, LBA-mapped",
                           int("10", 16) : "OPUS (?)",
                           int("11", 16) : "Hidden DOS 12-bit FAT",
                           int("12", 16) : "Configuration/diagnostics partition",
                           int("14", 16) : "Hidden DOS 16-bit FAT <32M",
                           int("16", 16) : "Hidden DOS 16-bit FAT >=32M",
                           int("17", 16) : "Hidden IFS (e.g., HPFS)",
                           int("18", 16) : "AST SmartSleep Partition",
                           int("19", 16) : "Unused",
                           int("1b", 16) : "Hidden WIN95 OSR2 32-bit FAT",
                           int("1c", 16) : "Hidden WIN95 OSR2 32-bit FAT, LBA-mapped",
                           int("1e", 16) : "Hidden WIN95 16-bit FAT, LBA-mapped",
                           int("20", 16) : "Unused",
                           int("21", 16) : "Reserved",
                           int("21", 16) : "Unused",
                           int("22", 16) : "Unused",
                           int("23", 16) : "Reserved",
                           int("24", 16) : "NEC DOS 3.x",
                           int("26", 16) : "Reserved",
                           int("31", 16) : "Reserved",
                           int("32", 16) : "NOS",
                           int("33", 16) : "Reserved",
                           int("34", 16) : "Reserved",
                           int("35", 16) : "JFS on OS/2 or eCS ",
                           int("36", 16) : "Reserved",
                           int("38", 16) : "THEOS ver 3.2 2gb partition",
                           int("39", 16) : "Plan 9 partition",
                           int("39", 16) : "THEOS ver 4 spanned partition",
                           int("3a", 16) : "THEOS ver 4 4gb partition",
                           int("3b", 16) : "THEOS ver 4 extended partition",
                           int("3c", 16) : "PartitionMagic recovery partition",
                           int("3d", 16) : "Hidden NetWare",
                           int("40", 16) : "Venix 80286",
                           int("41", 16) : "Linux/MINIX (sharing disk with DRDOS)",
                           int("41", 16) : "Personal RISC Boot",
                           int("41", 16) : "PPC PReP (Power PC Reference Platform) Boot",
                           int("42", 16) : "Linux swap (sharing disk with DRDOS)",
                           int("42", 16) : "SFS (Secure Filesystem)",
                           int("42", 16) : "Windows 2000 dynamic extended partition marker",
                           int("43", 16) : "Linux native (sharing disk with DRDOS)",
                           int("44", 16) : "GoBack partition",
                           int("45", 16) : "Boot-US boot manager",
                           int("45", 16) : "Priam",
                           int("45", 16) : "EUMEL/Elan ",
                           int("46", 16) : "EUMEL/Elan ",
                           int("47", 16) : "EUMEL/Elan ",
                           int("48", 16) : "EUMEL/Elan ",
                           int("4a", 16) : "Mark Aitchison's ALFS/THIN lightweight filesystem for DOS",
                           int("4a", 16) : "AdaOS Aquila (Withdrawn)",
                           int("4c", 16) : "Oberon partition",
                           int("4d", 16) : "QNX4.x",
                           int("4e", 16) : "QNX4.x 2nd part",
                           int("4f", 16) : "QNX4.x 3rd part",
                           int("4f", 16) : "Oberon partition",
                           int("50", 16) : "OnTrack Disk Manager (older versions) RO",
                           int("50", 16) : "Lynx RTOS",
                           int("50", 16) : "Native Oberon (alt)",
                           int("51", 16) : "OnTrack Disk Manager RW (DM6 Aux1)",
                           int("51", 16) : "Novell",
                           int("52", 16) : "CP/M",
                           int("52", 16) : "Microport SysV/AT",
                           int("53", 16) : "Disk Manager 6.0 Aux3",
                           int("54", 16) : "Disk Manager 6.0 Dynamic Drive Overlay",
                           int("55", 16) : "EZ-Drive",
                           int("56", 16) : "Golden Bow VFeature Partitioned Volume.",
                           int("56", 16) : "DM converted to EZ-BIOS",
                           int("57", 16) : "DrivePro",
                           int("57", 16) : "VNDI Partition",
                           int("5c", 16) : "Priam EDisk",
                           int("61", 16) : "SpeedStor",
                           int("63", 16) : "Unix System V (SCO, ISC Unix, UnixWare, ...), Mach, GNU Hurd",
                           int("64", 16) : "PC-ARMOUR protected partition",
                           int("64", 16) : "Novell Netware 286, 2.xx",
                           int("65", 16) : "Novell Netware 386, 3.xx or 4.xx",
                           int("66", 16) : "Novell Netware SMS Partition",
                           int("67", 16) : "Novell",
                           int("68", 16) : "Novell",
                           int("69", 16) : "Novell Netware 5+, Novell Netware NSS Partition",
                           int("6e", 16) : "??",
                           int("70", 16) : "DiskSecure Multi-Boot",
                           int("71", 16) : "Reserved",
                           int("73", 16) : "Reserved",
                           int("74", 16) : "Reserved",
                           int("74", 16) : "Scramdisk partition",
                           int("75", 16) : "IBM PC/IX",
                           int("76", 16) : "Reserved",
                           int("77", 16) : "M2FS/M2CS partition",
                           int("77", 16) : "VNDI Partition",
                           int("78", 16) : "XOSL FS",
                           int("7e", 16) : "Unused",
                           int("7f", 16) : "Unused",
                           int("80", 16) : "MINIX until 1.4a",
                           int("81", 16) : "MINIX since 1.4b, early Linux",
                           int("81", 16) : "Mitac disk manager",
                           #int("82", 16) : "Prime",
                           #int("82", 16) : "Solaris x86",
                           int("82", 16) : "Linux swap",
                           int("83", 16) : "Linux native partition",
                           int("84", 16) : "OS/2 hidden C: drive",
                           int("84", 16) : "Hibernation partition",
                           int("85", 16) : "Linux extended partition",
                           int("86", 16) : "Old Linux RAID partition superblock",
                           int("86", 16) : "NTFS volume set",
                           int("87", 16) : "NTFS volume set",
                           int("8a", 16) : "Linux Kernel Partition (used by AiR-BOOT)",
                           int("8b", 16) : "Legacy Fault Tolerant FAT32 volume",
                           int("8c", 16) : "Legacy Fault Tolerant FAT32 volume using BIOS extd INT 13h",
                           int("8d", 16) : "Free FDISK hidden Primary DOS FAT12 partitition",
                           int("8e", 16) : "Linux Logical Volume Manager partition",
                           int("90", 16) : "Free FDISK hidden Primary DOS FAT16 partitition",
                           int("91", 16) : "Free FDISK hidden DOS extended partitition",
                           int("92", 16) : "Free FDISK hidden Primary DOS large FAT16 partitition",
                           int("93", 16) : "Hidden Linux native partition",
                           int("93", 16) : "Amoeba",
                           int("94", 16) : "Amoeba bad block table",
                           int("95", 16) : "MIT EXOPC native partitions",
                           int("97", 16) : "Free FDISK hidden Primary DOS FAT32 partitition",
                           int("98", 16) : "Free FDISK hidden Primary DOS FAT32 partitition (LBA)",
                           int("98", 16) : "Datalight ROM-DOS Super-Boot Partition",
                           int("99", 16) : "DCE376 logical drive",
                           int("9a", 16) : "Free FDISK hidden Primary DOS FAT16 partitition (LBA)",
                           int("9b", 16) : "Free FDISK hidden DOS extended partitition (LBA)",
                           int("9f", 16) : "BSD/OS",
                           int("a0", 16) : "Laptop hibernation partition",
                           int("a1", 16) : "Laptop hibernation partition",
                           int("a1", 16) : "HP Volume Expansion (SpeedStor variant)",
                           int("a3", 16) : "Reserved",
                           int("a4", 16) : "Reserved",
                           int("a5", 16) : "BSD/386, 386BSD, NetBSD, FreeBSD",
                           int("a6", 16) : "OpenBSD",
                           int("a7", 16) : "NEXTSTEP",
                           int("a8", 16) : "Mac OS-X",
                           int("a9", 16) : "NetBSD",
                           int("aa", 16) : "Olivetti Fat 12 1.44MB Service Partition",
                           int("ab", 16) : "Mac OS-X Boot partition",
                           int("ab", 16) : "GO! partition",
                           int("ae", 16) : "ShagOS filesystem",
                           int("af", 16) : "ShagOS swap partition",
                           int("b0", 16) : "BootStar Dummy",
                           int("b1", 16) : "Reserved",
                           int("b3", 16) : "Reserved",
                           int("b4", 16) : "Reserved",
                           int("b6", 16) : "Reserved",
                           int("b6", 16) : "Windows NT mirror set (master), FAT16 file system",
                           int("b7", 16) : "Windows NT mirror set (master), NTFS file system",
                           int("b7", 16) : "BSDI BSD/386 filesystem",
                           int("b8", 16) : "BSDI BSD/386 swap partition",
                           int("bb", 16) : "Boot Wizard hidden",
                           int("be", 16) : "Solaris 8 boot partition",
                           int("c0", 16) : "CTOS",
                           int("c0", 16) : "REAL/32 secure small partition",
                           int("c0", 16) : "NTFT Partition",
                           int("c0", 16) : "DR-DOS/Novell DOS secured partition",
                           int("c1", 16) : "DRDOS/secured (FAT-12)",
                           int("c2", 16) : "Reserved for DR-DOS 7+",
                           int("c2", 16) : "Hidden Linux",
                           int("c3", 16) : "Hidden Linux swap",
                           int("c4", 16) : "DRDOS/secured (FAT-16, < 32M)",
                           int("c5", 16) : "DRDOS/secured (extended)",
                           int("c6", 16) : "DRDOS/secured (FAT-16, >= 32M)",
                           int("c6", 16) : "Windows NT corrupted FAT16 volume/stripe set",
                           int("c7", 16) : "Windows NT corrupted NTFS volume/stripe set",
                           int("c7", 16) : "Syrinx boot",
                           int("c8", 16) : "Reserved",
                           int("c9", 16) : "Reserved",
                           int("ca", 16) : "Reserved",
                           int("cb", 16) : "reserved for DRDOS/secured (FAT32)",
                           int("cc", 16) : "reserved for DRDOS/secured (FAT32, LBA)",
                           int("cd", 16) : "CTOS Memdump? ",
                           int("ce", 16) : "reserved for DRDOS/secured (FAT16, LBA)",
                           int("d0", 16) : "REAL/32 secure big partition",
                           int("d1", 16) : "Old Multiuser DOS secured FAT12",
                           int("d4", 16) : "Old Multiuser DOS secured FAT16 <32M",
                           int("d5", 16) : "Old Multiuser DOS secured extended partition",
                           int("d6", 16) : "Old Multiuser DOS secured FAT16 >=32M",
                           int("d8", 16) : "CP/M-86",
                           int("da", 16) : "Non-FS Data",
                           int("db", 16) : "Digital Research CP/M, Concurrent CP/M, Concurrent DOS",
                           int("db", 16) : "CTOS (Convergent Technologies OS -Unisys)",
                           int("db", 16) : "KDG Telemetry SCPU boot",
                           int("dd", 16) : "Hidden CTOS Memdump? ",
                           int("de", 16) : "Dell PowerEdge Server utilities (FAT fs)",
                           int("df", 16) : "DG/UX virtual disk manager partition",
                           int("df", 16) : "BootIt EMBRM",
                           int("e0", 16) : "Reserved by ",
                           int("e1", 16) : "DOS access or SpeedStor 12-bit FAT extended partition",
                           int("e3", 16) : "DOS R/O or SpeedStor",
                           int("e4", 16) : "SpeedStor 16-bit FAT extended partition < 1024 cyl.",
                           int("e5", 16) : "Tandy DOS with logical sectored FAT",
                           int("e5", 16) : "Reserved",
                           int("e6", 16) : "Reserved",
                           int("eb", 16) : "BeOS",
                           int("ed", 16) : "Reserved for Matthias Paul's Spryt*x",
                           int("ee", 16) : "Indication that this legacy MBR is followed by an EFI header",
                           int("ef", 16) : "Partition that contains an EFI file system",
                           int("f0", 16) : "Linux/PA-RISC boot loader",
                           int("f1", 16) : "SpeedStor",
                           int("f2", 16) : "DOS 3.3+ secondary partition",
                           int("f3", 16) : "Reserved",
                           int("f4", 16) : "SpeedStor large partition",
                           int("f4", 16) : "Prologue single-volume partition",
                           int("f5", 16) : "Prologue multi-volume partition",
                           int("f6", 16) : "Reserved",
                           int("f9", 16) : "pCache",
                           int("fa", 16) : "Bochs",
                           int("fb", 16) : "VMware File System partition",
                           int("fc", 16) : "VMware Swap partition",
                           int("fd", 16) : "Linux raid partition with autodetect using persistent superblock",
                           int("fe", 16) : "SpeedStor > 1024 cyl.",
                           int("fe", 16) : "LANstep",
                           int("fe", 16) : "IBM PS/2 IML (Initial Microcode Load) partition,",
                           int("fe", 16) : "Windows NT Disk Administrator hidden partition",
                           int("fe", 16) : "Linux Logical Volume Manager partition (old)",
                           int("ff", 16) : "Xenix Bad Block Table"}
        new_dict = {"pnum"           : {"he"  : html_tools.text_field(req, "npp", size=4, display_len=4),
                                        "new" : True,
                                        "vf"  : self._validate_pnum,
                                        "def" : ""},
                    "mountpoint"     : {"he"  : html_tools.text_field(req, "npm", size=127, display_len=32),
                                        "vf"  : self.validate_mountpoint,
                                        "def" : ""},
                    "p_size"         : (self._validate_size, {"size"    : {"he"  : html_tools.text_field(req, "nps", size=16, display_len=12),
                                                                           "def" : 50},
                                                              "size_pf" : {"he"  : size_postfix,
                                                                           "def" : 1,
                                                                           "ndb" : True}}),
                    "warn_threshold" : {"he"  : html_tools.text_field(req, "warn_th", size=5, display_len=5),
                                        "vf"  : self._validate_warn_th,
                                        "def" : 0},
                    "crit_threshold" : {"he"  : html_tools.text_field(req, "crit_th", size=5, display_len=5),
                                        "vf"  : self._validate_crit_th,
                                        "def" : 0},
                    "bootable"       : {"he"  : html_tools.checkbox(req, "npbf"),
                                        "def" : False},
                    "mount_options"  : {"he"  : html_tools.text_field(req, "npmo", size=127, display_len=32),
                                        "vf"  : self.validate_mountpoint,
                                        "def" : ""},
                    "fs_freq"        : {"he"  : fs_freq_ent,
                                        "def" : 0},
                    "fs_passno"      : {"he"  : fs_passno_ent,
                                        "def" : 0},
                    "del"            : {"he"  : html_tools.checkbox(req, "partdel", auto_reset=True),
                                        "del" : 1},
                    "filesys"        : (self._validate_filesys, {"partition_hex" : {"he"  : html_tools.text_field(req, "nph", size=2, display_len=2),
                                                                                    "def" : "83"},
                                                                 "partition_fs"  : {"he"  : filesystem_ent,
                                                                                    "def" : self.__fs_tree.get_hexid_fs_mapping("83")[0]}})}
        html_tools.validate_struct.__init__(self, req, "partition", new_dict)
    def get_hex_info(self, h_code):
        h_int = int(h_code, 16)
        return self.__hex_dict.get(h_int, "hex_code %s not known" % (h_code))
    def _validate_filesys(self):
        err_cause, err_list = (None, [])
        try:
            h_int = int(self.new_val_dict["partition_hex"], 16)
        except:
            err_cause, err_list = ("Partition HexCode must be a hexadecimal number", ["partition_hex"])
        else:
            self.new_val_dict["partition_hex"] = "%02x" % (h_int)
            hex_changed = self.new_val_dict["partition_hex"] != self.old_val_dict["partition_hex"]
            if self.__fs_tree.has_hexid_fs_mapping(h_int):
                if self.new_val_dict["partition_fs"] not in self.__fs_tree.get_hexid_fs_mapping(h_int):
                    if hex_changed:
                        # check for valid partition-fs
                        if self.__fs_tree.has_hexid_fs_mapping(h_int):
                            new_part_fs = self.__fs_tree.get_hexid_fs_mapping(h_int)[0]
                            raise ValueError, ("Setting partition_fs to %d" % (new_part_fs), {"partition_fs" : (new_part_fs,
                                                                                                                "Hexcode",
                                                                                                                [("partition_fs", new_part_fs)])})
                        else:
                            # invalid fs_type, revert to previous setting
                            err_cause, err_list = ("Filesystem not valid for partition code", hex_changed and ["partition_hex", "partition_fs"] or ["partition_fs"])
                    else:
                        # see if we can find a valid hex-id
                        if self.new_val_dict["partition_fs"]:
                            new_hexp = self.__fs_tree[self.new_val_dict["partition_fs"]].hexid
                            raise ValueError, ("Setting partition_hex to %s" % (new_hexp), {"partition_hex" : (new_hexp,
                                                                                                               "Hexcode",
                                                                                                               [("partition_hex", new_hexp)])})
        if err_cause:
            raise ValueError, (err_cause, dict([(what, (self.old_val_dict[what], "Hexcode", [(what, self.old_val_dict[what])])) for what in err_list]))
    def _validate_pnum(self):
        n_pn = self.new_val_dict["pnum"]
        try:
            num_pn = int(n_pn)
        except:
            raise ValueError, "Partition number must be an integer"
        else:
            if num_pn in self.used_partitions:
                raise ValueError, "Partition number %d already used" % (num_pn)
            self.new_val_dict["pnum"] = num_pn
    def _validate_warn_th(self):
        n_th = self.new_val_dict["warn_threshold"]
        try:
            num_th = int(n_th)
        except:
            raise ValueError, "Size must be an integer"
        else:
            self.new_val_dict["warn_threshold"] = num_th
    def _validate_crit_th(self):
        n_th = self.new_val_dict["crit_threshold"]
        try:
            num_th = int(n_th)
        except:
            raise ValueError, "Size must be an integer"
        else:
            self.new_val_dict["crit_threshold"] = num_th
    def _validate_size(self):
        n_size = self.new_val_dict["size"]
        try:
            num_size = int(n_size)
        except:
            raise ValueError, "Size must be an integer"
        else:
            self.new_val_dict["size"] = num_size * {1 : 1,
                                                    2 : 1000,
                                                    3 : 1000 * 1000}[self.new_val_dict["size_pf"]]
            self.get_he("size")[self.get_suffix()] = "%d" % (self.new_val_dict["size"])
    def validate_mountpoint(self):
        pass
##         n_dn = self.new_val_dict["disc"]
##         if n_dn in self.used_discs:
##             raise ValueError, "Disc %s already used" % (n_dn)
##         if not n_dn.startswith("/dev/"):
##             raise ValueError, "Discname  %s invalid (has to start with /dev/" % (n_dn)

class sys_partition(cdef_basics.db_obj):
    def __init__(self, part_table_idx, idx, init_dict):
        cdef_basics.db_obj.__init__(self, "sysp_%d_%d" % (part_table_idx, idx), idx)
        self.set_valid_keys({"name"            : "s",
                             "mountpoint"      : "s",
                             "mount_options"   : "s",
                             "partition_table" : "i"},
                            ["partition_table"])
        self.init_sql_changes({"table" : "sys_partition",
                               "idx"   : self.idx})
        self.set_parameters(init_dict)
        self.partition_table = part_table_idx
    def copy_instance(self):
        new_sp = sys_partition(self.partition_table, self.get_idx(), {})
        new_sp.copy_keys(self)
        return new_sp
    
class partition(cdef_basics.db_obj):
    def __init__(self, disc_idx, idx, init_dict):
        cdef_basics.db_obj.__init__(self, "part_%d" % (idx), idx)
        self.set_valid_keys({"mountpoint"     : "s",
                             "partition_disc" : "i",
                             "pnum"           : "i",
                             "mount_options"  : "s",
                             "bootable"       : "b",
                             "size"           : "i",
                             "fs_freq"        : "i",
                             "fs_passno"      : "i",
                             "partition_fs"   : "i",
                             "partition_hex"  : "i",
                             "warn_threshold" : "i",
                             "crit_threshold" : "i"},
                            ["partition_table"])
        self.init_sql_changes({"table" : "partition",
                               "idx"   : self.idx})
        self.set_parameters(init_dict)
        self.disc = disc_idx
        self.__partitions = {}
        self._init_settings()
        #print "new partition"
    def copy_instance(self):
        new_sp = partition(self.disc, self.get_idx(), {})
        new_sp.copy_keys(self)
        return new_sp
    def _init_settings(self):
        self.linux_partition = False
        self.extended_partition = False
    def _check_settings(self, part_tree):
        self.swap_partition = self["partition_hex"] == "82"
        self.extended_partition = self["partition_hex"] in ["05", "0f", "3b", "42",
                                                            "85", "91", "9b", "c5",
                                                            "d5", "e1", "e4"]
        self.valid = True
        if part_tree.part_fs_tree.has_hexid_fs_mapping(self["partition_hex"]):
            self.linux_partition = True
            fs_map = part_tree.part_fs_tree.get_hexid_fs_mapping(self["partition_hex"])
            if self["partition_fs"] not in fs_map:
                self.valid = False

class partition_disc(cdef_basics.db_obj):
    def __init__(self, part_table_idx, idx, init_dict):
        cdef_basics.db_obj.__init__(self, "disc_%d" % (idx), idx)
        self.set_valid_keys({"disc"            : "s",
                             "partition_table" : "i"},
                            ["partition_table"])
        self.init_sql_changes({"table" : "partition_disc",
                               "idx"   : self.idx})
        self.set_parameters(init_dict)
        self.partition_table = part_table_idx
        self.__partitions = {}
    def get_num_partitions(self):
        return len([key for key in self.__partitions.keys() if key])
    def add_new_entries(self, vs_dict):
        if vs_dict:
            self.__partition_vs = vs_dict["partition"]
        if self.idx:
            new_partition = partition(self.idx, 0, self.__partition_vs.get_default_dict())
            new_partition.set_suffix("%snp" % (self.get_suffix()))
            new_partition["partition_disc"] = self.idx
            new_partition.act_values_are_default()
            self.__partitions[new_partition.idx] = new_partition
    def add_partition(self, db_rec):
        if not self.__partitions.has_key(db_rec["partition_idx"]):
            new_part = partition(self.idx, db_rec["partition_idx"], db_rec)
            self.__partitions[new_part.idx] = new_part
            new_part.act_values_are_default()
    def copy_instance(self):
        new_sp = partition_disc(self.partition_table, self.get_idx(), {})
        new_sp.copy_keys(self)
        new_sp.__partition_vs = self.__partition_vs
        return new_sp
    def post_create_func(self):
        self.add_new_entries({})
    def check_for_changes(self, req, sub, change_log, part_tree):
        self.__partition_vs.set_submit_mode(sub)
        self.__partition_vs.set_old_db_obj_idx("%snp" % (self.get_suffix()))
        for partition_idx in self._get_partition_keys():
            partition_stuff = self.__partitions[partition_idx]
            self.__partition_vs.used_partitions = [self.__partitions[key]["pnum"] for key in self._get_partition_keys() if key and key != partition_idx]
            self.__partition_vs.link_object(partition_idx, partition_stuff)
            self.__partition_vs.check_for_changes()
            if not self.__partition_vs.check_delete():
                self.__partition_vs.process_changes(change_log, self.__partitions)
            self.__partition_vs.unlink_object()
        if self.__partition_vs.get_delete_list():
            for del_idx in self.__partition_vs.get_delete_list():
                change_log.add_ok("Deleted partition '%s'" % (self.__partitions[del_idx]["pnum"]), "SQL")
                del self.__partitions[del_idx]
            req.dc.execute("DELETE FROM partition WHERE %s" % (" OR ".join(["partition_idx=%d" % (x) for x in self.__partition_vs.get_delete_list()])))
        for partition_idx in self.__partitions.keys():
            partition_stuff = self.__partitions[partition_idx]
            partition_stuff._check_settings(part_tree)
    def _get_partition_keys(self):
        has_zero_part = self.__partitions.has_key(0)
        p_dict = dict([(value["pnum"], key) for key, value in self.__partitions.iteritems() if key])
        p_keys = [p_dict[key] for key in sorted(p_dict.keys())]
        if has_zero_part:
            p_keys.append(0)
        return p_keys
    def get_part_table(self, req):
        p_table = html_tools.html_table(cls="blind")
        p_table[0]["class"] = "line00"
        for what in ["part", "bf", "partition type", "fs", "size / th", "mountpoint", "mount options", "freq", "pass", "&nbsp;"]:
            p_table[None][0] = html_tools.content(what, cls="center", type="th")
        line_idx = 1
        for p_idx in self._get_partition_keys():
            line_idx = 1 - line_idx
            act_p = self.__partitions[p_idx]
            if act_p.extended_partition:
                act_class = "line00"
            elif act_p.linux_partition:
                act_class = act_p.valid and "line1%d" % (line_idx) or "error"
            else:
                act_class = "line01"
            p_table[0]["class"] = act_class
            p_table[None][0] = html_tools.content(["%s" % (self["disc"]), self.__partition_vs.get_he("pnum")], act_p.get_suffix())
            p_table[None][0] = html_tools.content(self.__partition_vs.get_he("bootable"), act_p.get_suffix(), cls="center")
            p_table[None][0] = html_tools.content(["HexID 0x", self.__partition_vs.get_he("partition_hex"), ", ", self.__partition_vs.get_hex_info(act_p["partition_hex"])], act_p.get_suffix())
            if act_p.linux_partition:
                p_table[None][0] = html_tools.content(self.__partition_vs.get_he("partition_fs"), act_p.get_suffix(), cls="left")
            else:
                p_table[None][0] = html_tools.content("&nbsp;")
            if act_p.extended_partition:
                p_table[None][0] = html_tools.content("&nbsp;")
            else:
                p_table[None][0] = html_tools.content([self.__partition_vs.get_he("size"),
                                                       self.__partition_vs.get_he("size_pf"),
                                                       self.__partition_vs.get_he("warn_threshold"),
                                                       self.__partition_vs.get_he("crit_threshold")], act_p.get_suffix())
            if act_p.linux_partition:
                if act_p.swap_partition:
                    p_table[None][0:4] = html_tools.content("Swap", cls="center")
                else:
                    p_table[None][0] = html_tools.content(self.__partition_vs.get_he("mountpoint"), act_p.get_suffix())
                    p_table[None][0] = html_tools.content(self.__partition_vs.get_he("mount_options"), act_p.get_suffix())
                    p_table[None][0] = html_tools.content(self.__partition_vs.get_he("fs_freq"), act_p.get_suffix(), cls="center")
                    p_table[None][0] = html_tools.content(self.__partition_vs.get_he("fs_passno"), act_p.get_suffix(), cls="center")
            else:
                p_table[None][0:4] = html_tools.content("&nbsp;")
            if p_idx:
                p_table[None][0] = html_tools.content(self.__partition_vs.get_he("del"), act_p.get_suffix(), cls="errormin")
            else:
                p_table[None][0] = html_tools.content("&nbsp;")
        return p_table

class partition_table(object):
    def __init__(self, db_rec):
        self.idx = db_rec["partition_table_idx"]
        self.name = db_rec["name"]
        #print "new_pt", self.idx, self.name
        self.description = db_rec["description"]
        self.valid = db_rec["valid"]
        self.modify_bootloader = db_rec["modify_bootloader"]
        self.__discs, self.__sys_partitions = ({}, {})
    def add_new_entries(self, vs_dict):
        self.__sys_p_vs = vs_dict["sys_partition"]
        self.__disc_vs  = vs_dict["disc"]
        new_sys_p = sys_partition(self.idx, -self.idx, self.__sys_p_vs.get_default_dict())
        new_sys_p["partition_table"] = self.idx
        new_sys_p.act_values_are_default()
        new_disc = partition_disc(self.idx, -self.idx, self.__disc_vs.get_default_dict())
        new_disc["partition_table"] = self.idx
        new_disc.act_values_are_default()
        self.__sys_partitions[new_sys_p.idx] = new_sys_p
        self.__discs[new_disc.idx] = new_disc
        # add new entries to existing discs
        for d_idx, d_stuff in self.__discs.iteritems():
            d_stuff.add_new_entries(vs_dict)
    def get_info(self):
        return "%s, %s" % (logging_tools.get_plural("disc", len([key for key in self.__discs.keys() if key > 0])),
                           logging_tools.get_plural("partition", sum([self[d_idx].get_num_partitions() for d_idx in self.__discs.keys()], 0)))
    def add_disc(self, db_rec):
        if not self.__discs.has_key(db_rec["partition_disc_idx"]):
            new_disc = partition_disc(self.idx, db_rec["partition_disc_idx"], db_rec)
            self.__discs[new_disc.idx] = new_disc
            new_disc.act_values_are_default()
    def add_partition(self, db_rec):
        self.__discs[db_rec["partition_disc_idx"]].add_partition(db_rec)
    def add_sys_partition(self, db_rec):
        new_sys_p = sys_partition(self.idx, db_rec["sys_partition_idx"], db_rec)
        new_sys_p.act_values_are_default()
        self.__sys_partitions[new_sys_p.idx] = new_sys_p
    def __getitem__(self, key):
        return self.__discs[key]
    def check_for_changes(self, req, sub, change_log, part_tree):
        # system partitions
        self.__sys_p_vs.set_submit_mode(sub)
        self.__sys_p_vs.set_old_db_obj_idx("min%d" % (self.idx))
        for sys_idx in self.__sys_partitions.keys():
            sys_stuff = self.__sys_partitions[sys_idx]
            self.__sys_p_vs.link_object(sys_idx, sys_stuff)
            self.__sys_p_vs.used_names = [value["name"] for key, value in self.__sys_partitions.iteritems() if key > 0 and key != sys_idx]
            self.__sys_p_vs.used_paths = [value["mountpoint"] for key, value in self.__sys_partitions.iteritems() if key > 0 and key != sys_idx]
            self.__sys_p_vs.check_for_changes()
            if not self.__sys_p_vs.check_delete():
                self.__sys_p_vs.process_changes(change_log, self.__sys_partitions)
            self.__sys_p_vs.unlink_object()
        if self.__sys_p_vs.get_delete_list():
            for del_idx in self.__sys_p_vs.get_delete_list():
                change_log.add_ok("Deleted sys_partition '%s'" % (self.__sys_partitions[del_idx]["name"]), "SQL")
                del self.__sys_partitions[del_idx]
            req.dc.execute("DELETE FROM sys_partition WHERE %s" % (" OR ".join(["sys_partition_idx=%d" % (x) for x in self.__sys_p_vs.get_delete_list()])))
        # discs
        self.__disc_vs.set_submit_mode(sub)
        for disc_idx in self.__discs.keys():
            disc_stuff = self.__discs[disc_idx]
            if disc_idx:
                disc_stuff.check_for_changes(req, sub, change_log, part_tree)
            self.__disc_vs.link_object(disc_idx, disc_stuff)
            self.__disc_vs.used_discs = [value["disc"] for key, value in self.__discs.iteritems() if key and key != disc_idx]
            self.__disc_vs.check_for_changes()
            if not self.__disc_vs.check_delete():
                self.__disc_vs.process_changes(change_log, self.__discs)
            self.__disc_vs.unlink_object()
        if self.__disc_vs.get_delete_list():
            for del_idx in self.__disc_vs.get_delete_list():
                change_log.add_ok("Deleted disc '%s'" % (self.__discs[del_idx]["disc"]), "SQL")
                del self.__discs[del_idx]
            req.dc.execute("DELETE FROM partition WHERE %s" % (" OR ".join(["partition_disc=%d" % (x) for x in self.__disc_vs.get_delete_list()])))
            req.dc.execute("DELETE FROM partition_disc WHERE %s" % (" OR ".join(["partition_disc_idx=%d" % (x) for x in self.__disc_vs.get_delete_list()])))
    def _get_sys_partition_keys(self):
        return [key for key in self.__sys_partitions.keys() if key > 0] + [-self.idx]
    def _get_disc_keys(self):
        return [key for key in self.__discs.keys() if key > 0] + [-self.idx]
    def show_table(self, req):
        sysp_table = html_tools.html_table(cls="blind")
        sysp_table[0]["class"] = "line00"
        for what in ["Type", "Mount point", "Mount options", "del"]:
            sysp_table[None][0] = html_tools.content(what, cls="center", type="th")
        line_idx = 0
        for sys_idx in self._get_sys_partition_keys():
            sys_p = self.__sys_partitions[sys_idx]
            line_idx = 1 - line_idx
            sysp_table[0]["class"] = "line1%d" % (line_idx)
            sysp_table[None][0] = html_tools.content(self.__sys_p_vs.get_he("name"), sys_p.get_suffix(), cls="center")
            if sys_idx > 0:
                sysp_table[None][0] = html_tools.content(self.__sys_p_vs.get_he("mountpoint"), sys_p.get_suffix(), cls="center")
            else:
                sysp_table[None][0] = html_tools.content(["New: ", self.__sys_p_vs.get_he("mountpoint")], sys_p.get_suffix(), cls="center")
            sysp_table[None][0] = html_tools.content(self.__sys_p_vs.get_he("mount_options"), sys_p.get_suffix(), cls="center")
            if sys_idx > 0:
                sysp_table[None][0] = html_tools.content(self.__sys_p_vs.get_he("del"), sys_p.get_suffix(), cls="errormin")
            else:
                sysp_table[None][0] = html_tools.content("&nbsp;")
        disc_table = html_tools.html_table(cls="normal")
        disc_table[0]["class"] = "line00"
        disc_table[None][0:2] = html_tools.content("System partitions", type="th", cls="center")
        disc_table[0]["class"] = "black"
        disc_table[None][0:2] = html_tools.content(sysp_table, cls="left")
        disc_table[0]["class"] = "line00"
        disc_table[None][0:2] = html_tools.content("Physical discs and partitions", type="th", cls="center")
        for disc_idx in self._get_disc_keys():
            disc = self.__discs[disc_idx]
            line_idx = 1 - line_idx
            disc_table[0]["class"] = "white"
            if disc_idx > 0:
                disc_table[None][0] = html_tools.content(["Discname: ", self.__disc_vs.get_he("disc")], disc.get_suffix(), cls="left")
                disc_table[None][0] = html_tools.content(self.__disc_vs.get_he("del"), disc.get_suffix(), cls="errormin")
                disc_table[0]["class"] = "black"
                disc_table[None][0:2] = html_tools.content(disc.get_part_table(req), cls="blind")
            else:
                disc_table[None][0:2] = html_tools.content(["New disc: ", self.__disc_vs.get_he("disc")], disc.get_suffix(), cls="left")
        req.write("%s%s" % (html_tools.gen_hline("Partition setup %s" % (self.name), 3),
                            disc_table("")))
            
class partition_tree(object):
    def __init__(self, req, action_log):
        self.__req = req
        self.action_log = action_log
        pt_parts = ["partition_table_idx", "name", "description", "valid", "modify_bootloader"]
        pd_parts = ["partition_disc_idx", "disc"]
        p_parts  = ["partition_idx", "mountpoint", "partition_fs", "partition_hex", "size", "mount_options", "pnum", "bootable", "fs_freq", "fs_passno",
                    "warn_threshold", "crit_threshold"]
        sys_parts = ["name", "mountpoint", "mount_options"]
        # new partition tree
        self.new_part_field = html_tools.text_field(req, "npname", size=127, display_len=32, auto_reset=True)
        self.part_fs_tree = partition_fs_tree(req, action_log)
        # init validate structures
        self._init_vs()
        # normal partitions
        req.dc.execute("SELECT %s, %s, %s FROM partition_table pt LEFT JOIN partition_disc pd ON pd.partition_table=pt.partition_table_idx " % (", ".join(["pt.%s" % (x) for x in pt_parts]),
                                                                                                                                                ", ".join(["pd.%s" % (x) for x in pd_parts]),
                                                                                                                                                ", ".join(["p.%s" % (x) for x in p_parts])) +
                       "LEFT JOIN partition p ON p.partition_disc=pd.partition_disc_idx ORDER BY pt.name, pd.disc, p.pnum")
        self.__partitions, self.__lut = ({}, {})
        for db_rec in req.dc.fetchall():
            if not self.__partitions.has_key(db_rec["partition_table_idx"]):
                self._add_partition_table(db_rec)
            if db_rec["partition_disc_idx"]:
                self.add_disc(db_rec)
                if db_rec["partition_idx"]:
                    self.add_partition(db_rec)
        # system partitions
        if self.__partitions:
            req.dc.execute("SELECT * FROM sys_partition WHERE %s" % (" OR ".join(["partition_table=%d" % (x) for x in self.__partitions.keys()])))
            for db_rec in req.dc.fetchall():
                self.__partitions[db_rec["partition_table"]].add_sys_partition(db_rec)
        # add default partitions
        for p_idx, p_stuff in self.__partitions.iteritems():
            p_stuff.add_new_entries(self.__vs_dict)
        # build partition sel_list
        self._build_partition_sel_list()
        self._check_act_selection()
            #pprint.pprint(db_rec)
    def check_for_new_partition(self):
        pt_parts = ["partition_table_idx", "name", "description", "valid", "modify_bootloader"]
        new_p_n = self.new_part_field.check_selection("", "")
        if new_p_n:
            if new_p_n in self.__lut.keys():
                self.action_log.add_warn("Partition named '%s' already exists" % (new_p_n), "internal")
            else:
                self.action_log.add_ok("Creating partition setup with name '%s'" % (new_p_n), "sql")
                self.__req.dc.execute("INSERT INTO partition_table SET name=%s, description=%s", (new_p_n,
                                                                                                  "new partitiontable"))
                self.__req.dc.execute("SELECT %s FROM partition_table pt" % (", ".join(["pt.%s" % (x) for x in pt_parts])))
                for db_rec in self.__req.dc.fetchall():
                    self._add_partition_table(db_rec)
                for p_idx, p_stuff in self.__partitions.iteritems():
                    p_stuff.add_new_entries(self.__vs_dict)
                self._build_partition_sel_list()
                self._check_act_selection()
    def _build_partition_sel_list(self):
        self.sel_list = html_tools.selection_list(self.__req, "psl", {}, size=5, multiple=False, sort_new_keys=False)
        for p_name in sorted([x for x in self.__lut.keys() if type(x) == type("")]):
            act_p = self[p_name]
            self.sel_list[act_p.idx] = "%s: %s" % (p_name,
                                                   act_p.get_info())
    def _init_vs(self):
        self.__vs_dict = {"sys_partition" : new_sys_partition_vs(self.__req),
                          "disc"          : new_disc_vs(self.__req),
                          "partition"     : new_partition_vs(self.__req, self.part_fs_tree)}
    def _add_partition_table(self, db_rec):
        new_pt = partition_table(db_rec)
        self.__partitions[new_pt.idx] = new_pt
        self.__lut[new_pt.name] = new_pt
        self.__lut[new_pt.idx]  = new_pt
    def add_disc(self, db_rec):
        self.__partitions[db_rec["partition_table_idx"]].add_disc(db_rec)
    def add_partition(self, db_rec):
        self.__partitions[db_rec["partition_table_idx"]].add_partition(db_rec)
    def has_key(self, key):
        return self.__lut.has_key(key)
    def _check_act_selection(self):
        if self.__lut:
            self.selected_partition = self.sel_list.check_selection("", sorted(self.__lut.keys())[0])
        else:
            self.selected_partition = self.sel_list.check_selection("", 0)
        #print self.selected_partitions
    def __getitem__(self, key):
        return self.__lut[key]

class partition_fs(object):
    def __init__(self, db_rec):
        self.idx = db_rec["partition_fs_idx"]
        self.name = db_rec["name"]
        self.descr = db_rec["descr"]
        self.hexid = db_rec["hexid"]
        self.identifier = db_rec["identifier"]
        
class partition_fs_tree(object):
    def __init__(self, req, action_log):
        self.action_log = action_log
        needed_names_dict = {"reiserfs": ("f", "ReiserFS Filesystem"  , "83"),
                             "ext2"    : ("f", "Extended 2 Filesystem", "83"),
                             "ext3"    : ("f", "Extended 3 Filesystem", "83"),
                             "swap"    : ("s", "SwapSpace"            , "82"),
                             "ext"     : ("e", "Extended Partition"   , "0f"),
                             "empty"   : ("d", "Empty Partition"      , "00"),
                             "lvm"     : ("l", "LVM Partition"        , "8e")}
        self._read_fs_tree(req.dc)
        act_names = [x.name for x in self.__fs_tree.values()]
        db_changes = 0
        needed_names = needed_names_dict.keys()
        for needed_name in needed_names:
            if needed_name not in act_names:
                db_changes += 1
                req.dc.execute("INSERT INTO partition_fs VALUES(0, %s, %s, %s, %s, null)", (tuple([needed_name] + list(needed_names_dict[needed_name]))))
        if db_changes:
            action_log.add_ok("Inserted %s into partition_fs" % (logging_tools.get_plural("record", db_changes)),
                              "sql")
            self._read_fs_tree(req.dc)
    def _read_fs_tree(self, dc):
        # inv_lut: dictionary, hexid -> fs_idxs
        self.__fs_tree, self.__fs_lut, self.__inv_lut = ({}, {}, {})
        dc.execute("SELECT * FROM partition_fs")
        for db_rec in dc.fetchall():
            new_p_fs = partition_fs(db_rec)
            self.__fs_tree[db_rec["partition_fs_idx"]] = new_p_fs
            self.__fs_lut[new_p_fs.idx] = new_p_fs
            self.__fs_lut[new_p_fs.name] = new_p_fs
            self.__inv_lut.setdefault(int(new_p_fs.hexid, 16), []).append(new_p_fs.idx)
            self.__inv_lut.setdefault(new_p_fs.hexid, []).append(new_p_fs.idx)
    def has_hexid_fs_mapping(self, part_id):
        return self.__inv_lut.has_key(part_id)
    def get_hexid_fs_mapping(self, part_id):
        return self.__inv_lut[part_id]
    def keys(self):
        return [key for key in self.__fs_lut.keys() if type(key) == type("")]
    def __getitem__(self, key):
        return self.__fs_lut[key]
            
class server_check_tree(object):
    def __init__(self, req, action_log):
        self.__req = req
        self.__action_log = action_log
        # get all devices
        self.__req.dc.execute("SELECT d.name, d.device_idx FROM device d, device_type dt WHERE d.device_type=dt.device_type_idx AND dt.identifier='H'")
        self.__servers = dict([(db_rec["name"], db_rec["device_idx"]) for db_rec in self.__req.dc.fetchall()])
        if self.__servers:
            # build index lut, dangerous, can change
            srv_names = sorted(self.__servers.keys())
            self.__srv_lut = dict([(value, key) for key, value in self.__servers.iteritems()])
            self.srv_fetch_list = html_tools.selection_list(req, "psfl", {},
                                                            sort_new_keys=False,
                                                            multiple=True,
                                                            size=5, auto_reset=True)
        else:
            self.srv_fetch_list = None
        self.link_partition_table()
    def check_fetch(self):
        act_fetch_sel = self.srv_fetch_list.check_selection("", [])
        if act_fetch_sel:
            ds_command = tools.s_command(self.__req, "server", 8004, "fetch_partition_info", [], 30, None, {"devname" : ",".join([self.__srv_lut[idx] for idx in act_fetch_sel])})
            tools.iterate_s_commands([ds_command], self.__action_log)
    def link_partition_table(self, p_table=None):
        self.__partition_table = p_table
        self.modify_sel_list()
    def modify_sel_list(self):
        # modifies the display strings of the selection list
        old_mode = self.srv_fetch_list.get_mode()
        for name in sorted(self.__servers.keys()):
            pt_name = "%s_part" % (name)
            if self.__partition_table and self.__partition_table.has_key(pt_name):
                s_string = "%s, partition_table read" % (name)
            else:
                s_string = name
            self.srv_fetch_list[self.__servers[name]] = s_string
        self.srv_fetch_list.restore_mode(old_mode)
        
def handle_fetch_existing(req, action_log, s_check_tree):
    sel_table = html_tools.html_table(cls="blindsmall")
    s_check_tree.check_fetch()
    sel_table[0][0] = html_tools.content(s_check_tree.srv_fetch_list)
    req.write(sel_table(""))
    
def handle_overview(req, action_log, part_tree, main_mode):
    low_submit = html_tools.checkbox(req, "sub")
    sub = low_submit.check_selection("")
    low_submit[""] = 1
    part_tree.check_for_new_partition()
    sel_table = html_tools.html_table(cls="blindsmall")
    sel_table[0][0] = html_tools.content(part_tree.sel_list)
    sel_table[0][0] = html_tools.content(html_tools.submit_button(req, "select"), cls="center")
    req.write("%s</form>" % (sel_table("")))
    req.write("<form action=\"%s.py?%s\" method = post>%s%s" % (req.module_name,
                                                                functions.get_sid(req),
                                                                main_mode.create_hidden_var(""),
                                                                part_tree.sel_list.create_hidden_var("")))
    if part_tree.selected_partition:
        for sel_p_idx in [part_tree.selected_partition]:
            sel_p = part_tree[sel_p_idx]
            sel_p.check_for_changes(req, sub, action_log, part_tree)
            sel_p.show_table(req)
    else:
        req.write(html_tools.gen_hline("No partition table selected", 2))
    req.write("<div class=\"center\">New partition table: %s%s</div>" % (part_tree.new_part_field(""),
                                                                         low_submit.create_hidden_var("")))

def process_page(req):
    if req.conf["genstuff"].has_key("AUTO_RELOAD"):
        del req.conf["genstuff"]["AUTO_RELOAD"]
    functions.write_header(req)
    functions.write_body(req)
    main_mode_field = html_tools.text_field(req, "mode")
    act_main_mode = main_mode_field.check_selection("", "ov")
    action_log = html_tools.message_log()
    part_tree = partition_tree(req, action_log)
    s_check_tree = server_check_tree(req, action_log)
    s_check_tree.link_partition_table(part_tree)
    mode_table = html_tools.html_table(cls="blind")
    for col_field, mm, descr in [(0   , "ov", "Overview and modify"),
                                 (None, "fe", "Fetch exisiting")]:
        mode_table[col_field][0] = html_tools.content("<a href=\"%s.py?%s&mode=%s\">%s<a>" % (req.module_name,
                                                                                              functions.get_sid(req),
                                                                                              mm,
                                                                                              descr), cls="center")
    req.write(mode_table(""))
    select_button = html_tools.submit_button(req, "select")
    submit_button = html_tools.submit_button(req, "submit")
    req.write("<form action=\"%s.py?%s\" method = post>%s" % (req.module_name,
                                                              functions.get_sid(req),
                                                              main_mode_field.create_hidden_var("")))
    if act_main_mode == "fe":
        handle_fetch_existing(req, action_log, s_check_tree)
    elif act_main_mode == "ov":
        handle_overview(req, action_log, part_tree, main_mode_field)
    req.write("<div class=\"center\">%s</div>" % (submit_button()))
    req.write("</form>")
    req.write(action_log.generate_stack("Log"))

class table_iterator(object):
    def __init__(self, **args):
        self.__num_iterators = args.get("num_iterators", 1)
        self.__iterators = [1 for idx in xrange(self.__num_iterators)]
    def get_iterator(self, idx):
        self.__iterators[idx] = 1 - self.__iterators[idx]
        return self.__iterators[idx]

class db_object(object):
    def __init__(self, req, **args):
        self.__req = req
        self.db_rec = args["db_rec"]
        self.__primary_db = args["primary_db"]
        self.__index_field = args["index_field"]
        self.db_change_list = set()
    def __getitem__(self, key):
        return self.db_rec[key]
    def __setitem__(self, key, value):
        # when called via the __setitem__ the db will get changed
        self.db_change_list.add(key)
        self.db_rec[key] = value
    def commit_db_changes(self, primary_idx):
        if self.db_change_list:
            sql_str, sql_tuple = (", ".join(["%s=%%s" % (key) for key in self.db_change_list]),
                                  tuple([self[key] for key in self.db_change_list]))
            self.__req.dc.execute("UPDATE %s SET %s WHERE %s=%d" % (self.__primary_db,
                                                                    sql_str,
                                                                    self.__index_field,
                                                                    primary_idx),
                                  sql_tuple)
    def expand(self, ret_f):
        attr_re = re.compile("(?P<pre_str>.*){(?P<attr_spec>.*)}(?P<post_str>.*)")
        new_f = []
        for act_p in ret_f:
            if act_p.startswith("*"):
                # no expansion
                pass
            else:
                while act_p.count("{") and act_p.count("}"):
                    attr_m = attr_re.match(act_p)
                    src, src_name = attr_m.group("attr_spec").split(".", 1)
                    if src == "db":
                        var_val = self[src_name]
                    elif src == "attr":
                        var_val = getattr(self, src_name)
                    else:
                        var_val = "unknown src %s (src_name %s)" % (src, src_name)
                    act_p = "%s%s%s" % (attr_m.group("pre_str"),
                                        var_val,
                                        attr_m.group("post_str"))
            new_f.append(act_p)
        return new_f

class genstuff(db_object):
    def __init__(self, req, **args):
        self.__req = req
        self.__root = args["root"]
        self.__template = args.get("template", False)
        db_object.__init__(self, self.__req, db_rec=args.get("db_rec", {}),
                           primary_db="genstuff",
                           index_field="genstuff_idx")
        if args.get("create", False):
            # reate new entitiy
            self.__req.dc.execute("INSERT INTO genstuff SET name=%s", (self["name"]))
            # get dictionary from db to get the correct default-values
            self.__req.dc.execute("SELECT * FROM genstuff WHERE genstuff_idx=%d" % (self.__req.dc.insert_id()))
            self.db_rec = self.__req.dc.fetchone()
        if not self.__template:
            self.unique_id = "gs%d" % (self["genstuff_idx"])
            self.idx = self["genstuff_idx"]
    def create_content(self, act_ti):
        req = self.__req
        if self.__template:
            ret_f = ["New: <input name=\"%s\" value=\"\"/>" % (self.__root.get_new_idx("genstuff"))]
        else:
            ret_f = ["<input name=\"{attr.unique_id}n\" value=\"{db.value}\"/>",
                     "<input name=\"{attr.unique_id}v\" value=\"{db.name}\">",
                     "<input type=checkbox name=\"{attr.unique_id}del\" />"]
        return "<tr class=\"line1%d\"><td>%s</td></tr>" % (act_ti.get_iterator(0),
                                                           "".join(self.expand(ret_f)))
#     def __getitem__(self, key):
#         return super(genstuff, self).__getitem__(key)
    def feed_args(self, args):
        if self.__template:
            new_name = args.get(self.__root.get_new_idx("genstuff"), "")
            if new_name:
                # validate new_args
                pass
                # generate new genstuff
                self.__root.add_leaf("genstuff", genstuff(self.__req, root=self.__root, create=True, db_rec={"name" : new_name}))
        else:
            if args.has_key("%sn" % (self.unique_id)):
                if args.has_key("%sdel" % (self.unique_id)):
                    # delete entry
                    self.__root.delete("genstuff", self)
                    self.__req.dc.execute("DELETE FROM genstuff WHERE genstuff_idx=%d" % (self.idx))
                else:
                    new_name = args["%sn" % (self.unique_id)]
                    new_value = args["%sv" % (self.unique_id)]
                    if self["name"] != new_name:
                        self["name"] = new_name
                    if self["value"] != new_value:
                        self["value"] = new_value
    def commit_changes(self):
        self.commit_db_changes(self.idx)

class genstuff_tree(object):
    def __init__(self, req):
        self.req = req
        self.__dict = {"genstuff" : {}}
    def read_from_db(self):
        self.req.dc.execute("SELECT * FROM genstuff")
        for db_rec in self.req.dc.fetchall():
            new_gs = genstuff(self.req, db_rec=db_rec, root=self)
            self.add_leaf("genstuff", new_gs)
        self.__new_gs = genstuff(self.req, template=True, root=self)
    def add_leaf(self, tree_name, new_gs):
        self.__dict[tree_name][new_gs.idx] = new_gs
    def validate_tree(self):
        pass
    def get_new_idx(self, tree_name):
        return "new%s" % (tree_name)
    def delete(self, tree_name, obj):
        del self.__dict[tree_name][obj.idx]
    def parse_values(self):
        args = self.req.sys_args
        for gs_stuff in self.__dict["genstuff"].values() + [self.__new_gs]:
            gs_stuff.feed_args(args)
    def commit_changes(self):
        args = self.req.sys_args
        for gs_stuff in self.__dict["genstuff"].values():
            gs_stuff.commit_changes()
    def create_content(self):
        req = self.req
        act_ti = table_iterator()
        table_content = []
        for gs_idx, gs_stuff in self.__dict["genstuff"].iteritems():
            table_content.append(gs_stuff.create_content(act_ti))
        table_content.append(self.__new_gs.create_content(act_ti))
        req.write("<table>%s</table>" % ("\n".join(table_content)))
        print "\n".join(table_content)

def process_page_2(req):
    if req.conf["genstuff"].has_key("AUTO_RELOAD"):
        del req.conf["genstuff"]["AUTO_RELOAD"]
    functions.write_header(req)
    functions.write_body(req)
    req.write("<form action=\"%s.py?%s\" method = post>" % (req.module_name,
                                                            functions.get_sid(req)))
    tt = genstuff_tree(req)
    tt.read_from_db()
    tt.validate_tree()
    tt.parse_values()
    tt.commit_changes()
    tt.create_content()
    req.write(html_tools.submit_button(req, "select")(""))
    req.write("</form>")
