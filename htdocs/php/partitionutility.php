<?php
//-*ics*- ,CAPG,name:'conf',descr:'Configuration',pri:-20
//-*ics*- ,CAP,name:'pu',descr:'Paritition utility',defvalue:0,enabled:1,scriptname:'/php/partitionutility.php',left_string:'Partition Utility',right_string:'Show and modify the various Partitions',pri:-100,capability_group_name:'conf'
//
// Copyright (C) 2001,2002,2003,2004 Andreas Lang, init.at
//
// Send feedback to: <lang@init.at>
// 
// This program is free software; you can redistribute it and/or modify
// it under the terms of the GNU General Public License Version 2 as
// published by the Free Software Foundation.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with this program; if not, write to the Free Software
// Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
//
function get_all_fs_types() {
    $mres=query("SELECT * FROM partition_fs");
    $fs=array();
    while ($mfr=mysql_fetch_object($mres)) $fs[$mfr->partition_fs_idx]=$mfr;
    return $fs;
}
function get_partition_tree() {
    $valid_array=array();
    $mres=query("SELECT pt.partition_table_idx,pt.name,pt.description,pt.valid,pt.modify_bootloader,pd.disc,pd.partition_disc_idx,p.mountpoint,p.partition_fs,p.partition_hex,p.size,p.mount_options,p.pnum,p.bootable,p.partition_idx,p.fs_freq,p.fs_passno FROM partition_table pt LEFT JOIN partition_disc pd ON pd.partition_table=pt.partition_table_idx LEFT JOIN partition p ON p.partition_disc=pd.partition_disc_idx ORDER BY pt.name,pd.disc,p.pnum");
    $pt=array();
    while ($mfr=mysql_fetch_object($mres)) {
        if (!in_array($mfr->partition_table_idx,array_keys($pt))) {
            $mfr->discs=array();
            $mfr->sys_partitions=array();
	    $valid_array[$mfr->partition_table_idx]=$mfr->valid;
            $pt[$mfr->partition_table_idx]=$mfr;
        }
        if ($mfr->disc) {
            if (!in_array($mfr->partition_disc_idx,array_keys($pt[$mfr->partition_table_idx]->discs))) {
                $mfr->plist=array();
                $mfr->partitions=array();
                $pt[$mfr->partition_table_idx]->discs[$mfr->partition_disc_idx]=$mfr;
            }
        }
        if ($mfr->pnum) {
            $pt[$mfr->partition_table_idx]->discs[$mfr->partition_disc_idx]->partitions[$mfr->pnum]=$mfr;
        }
    }
    // insert sys-partitions
    $mres=query("SELECT sp.* FROM sys_partition sp");
    while ($mfr=mysql_fetch_object($mres)) {
        if (in_array($mfr->partition_table,array_keys($pt))) $pt[$mfr->partition_table]->sys_partitions[$mfr->sys_partition_idx]=$mfr;
    }
    return array($pt,$valid_array);
}
function sanity_check_disc(&$pd,$key,$my_struct) {
    $pd->valid=1;
    $pd->ext_present=0;
    $pd->has_root_dir=0;
    $pd->mount_points=array();
    $pd->fs_size=0;
    $pd->swap_size=0;
    $pd->max_act_part_num=0;
    $p_array=array();
    $num_zero_size=0;
    $max_p_num=0;
    $min_zero_p_num=-1;
    foreach ($pd->partitions as $p_idx=>$p_stuff) {
        $max_p_num=$p_stuff->pnum;
        $hexid=substr("00{$p_stuff->partition_hex}",-2,2);
	$empty_part=(($hexid=="00") ? 1 : 0);
	$is_ext=(in_array($hexid,$GLOBALS["all_ext_ids"]) ? 1 : 0);
        $pd->partitions[$p_idx]->is_swap=0;
        $pd->partitions[$p_idx]->is_ext=0;
        $pd->partitions[$p_idx]->is_primary=0;
	$pd->partitions[$p_idx]->is_empty=$empty_part;
        $pd->max_act_part_num=max($pd->max_act_part_num,$p_stuff->pnum);
        if ($is_ext) {
            $pd->partitions[$p_idx]->is_ext=1;
            if ($p_stuff->pnum != 4) {
                //$pd->valid=0;
                //$my_struct->log_stack->add_message("Extended partition not located on partition 4 (table {$my_struct->pt->name}, disc $pd->disc)","Error",0);
            }
            if ($pd->ext_present) {
                $pd->valid=0;
                $my_struct->log_stack->add_message("More than one extended partition found (partition_table {$my_struct->pt->name}, disc $pd->disc)","Error",0);
            }
            $pd->ext_present=$p_stuff->pnum;
        } else if (in_array($hexid,array_keys($GLOBALS["all_fs_t2"])) && $GLOBALS["all_fs_t2"][$hexid]->identifier=="s") {
            $pd->partitions[$p_idx]->is_swap=1;
            $pd->swap_size+=$p_stuff->size;
        } else {
            $pd->mount_points[]=$p_stuff->mountpoint;
            if ($p_stuff->mountpoint=="/") {
                $pd->has_root_dir++;
            }
            if (!$p_stuff->size && !$empty_part) {
		if ($num_zero_size++) {
		    $pd->valid=0;
		    $my_struct->log_stack->add_message("More than one maximum-sized partition found (partition_table {$my_struct->pt->name}, disc $pd->disc)","Error",0);
		}
            }
            $pd->fs_size+=$p_stuff->size;
        }
        if (!$p_stuff->size && $min_zero_p_num == -1 && !$empty_part && !$is_ext) $min_zero_p_num=$p_stuff->pnum;
        if (!$pd->partitions[$p_idx]->is_ext && $pd->ext_present && $p_stuff->pnum > $pd->ext_present && $p_stuff->pnum <=4 && !$empty_part) {
            $pd->valid=0;
            $my_struct->log_stack->add_message("Primary partition $pd->disc$p_stuff->pnum found after extended (partition_table {$my_struct->pt->name}, disc $pd->disc)","Error",0);
        }
    }
    if ($min_zero_p_num > 0 && $min_zero_p_num < $max_p_num) {
        $pd->valid=0;
        $my_struct->log_stack->add_message("Maximum-sized partition is not the last one (partition_table {$my_struct->pt->name}, disc $pd->disc)","Error",0);
    }
    if ($pd->ext_present) {
        $pd->max_part_num=16;
    } else {
        $pd->max_part_num=4;
    }
    for ($i=1;$i < $pd->max_part_num+1;$i++) {
        if (!in_array($i,array_keys($pd->partitions))) $p_array[]=$i;
    }
    $pd->plist=$p_array;
    if ($pd->max_act_part_num > $pd->max_part_num) {
        $pd->valid=0;
        $my_struct->log_stack->add_message("Highest partition number too high ($pd->max_act_part_num > $pd->max_part_num, disc $pd->disc, partition_table {$my_struct->pt->name})","Error",0);
    }
}
function get_size_str($num) {
    $idx=0;
    while ($num > 1000) {
        $num/=1000;
        $idx++;
    }
    $s_tab=array("M","G","T");
    return sprintf("%.2f %sByte",$num,$s_tab[$idx]);
}
function get_disc_validity($val,$pd) {
    $val=min($val,$pd->valid);
    return $val;
}
function get_num_root_dirs($val,$pd) {
    return $val+$pd->has_root_dir;
}
function get_num_root_dirs_sysp($val,$pd) {
    return $val+($pd->mountpoint=="/" ? 1 : 0);
}
function get_mount_points($val,$pd) {
    return array_merge($val,$pd->mount_points);
}
function get_mount_points_sysp($val,$pd) {
    //return array_merge($val,array($pd->mountpoint));
    return array_merge(array($val->mountpoint),$pd);
}
function get_sysp_type($val,$pd) {
    return array_merge($val,array($pd->name));
}
function get_swap_size($val,$pd) {
    return $val+$pd->swap_size;
}
function get_fs_size($val,$pd) {
    return $val+$pd->fs_size;
}
function sanity_check_part(&$pt,$key,&$f_block) {
    $log_stack=&$f_block->log_stack;
    if (in_array($pt->partition_table_idx,$f_block->sel_parts)) {
	$my_struct->log_stack=$log_stack;
	$my_struct->pt=&$pt;
	$pt->valid=1;
	$pt->swap_size=0;
	$pt->fs_size=0;
	if (count($pt->discs)) {
	    // iterate over partition-stuff and set flags
	    array_walk($pt->discs,"sanity_check_disc",&$my_struct);
	    $pt->valid=min($pt->valid,array_reduce($pt->discs,"get_disc_validity",1));
	    $pt->swap_size=array_reduce($pt->discs,"get_swap_size",0);
	    $pt->fs_size=array_reduce($pt->discs,"get_fs_size",0);
	    $pt->has_root_dir=array_reduce($pt->discs,"get_num_root_dirs",0)+array_reduce($pt->sys_partitions,"get_num_root_dirs_sysp",0);
	    if ($pt->has_root_dir > 1) {
		$pt->valid=0;
		$log_stack->add_message(sprintf("Partition_table $pt->name has %d root-directories",$pt->has_root_dir),"Error",0);
	    } else if (!$pt->has_root_dir) {
		$pt->valid=0;
		$log_stack->add_message("Partition_table $pt->name has no root-directory","Error",0);
	    }
	    $pt->mount_points=array_merge(array_reduce($pt->discs,"get_mount_points",array()),array_reduce($pt->sys_partitions,"get_mount_points_sysp",array()));
	    $mpc=array_count_values($pt->mount_points);
	    foreach ($mpc as $mp=>$mpcount) {
		if ($mpcount > 1 && $mp) {
		    $pt->valid=0;
		    $log_stack->add_message("Partition_table $pt->name has $mpcount mountpoints $mp","Error",0);
		}
	    }
	    $pt->sysp_types=array_reduce($pt->sys_partitions,"get_sysp_type",array());
	    $mpc=array_count_values($pt->sysp_types);
	    foreach ($mpc as $mp=>$mpcount) {
		if ($mpcount > 1) {
		    $pt->valid=0;
		    $log_stack->add_message("Partition_table $pt->name has $mpcount sysp_partions of type $mp","Error",0);
		}
	    }
	} else {
	    $pt->valid=0;
	    $log_stack->add_message("Partition_table $pt->name has no discs connected","Error",0);
	}
    }
}
require_once "config.php";
require_once "mysql.php";
require_once "htmltools.php";
require_once "tools.php";
$vars=readgets();
if ($sys_config["ERROR"] == 1) {
    errorpage("No configfile.");
} else if (! $sys_config["pu_en"] == 1) {
    errorpage("You are not allowed to view this page.");
} else if (! $sys_config["SESSION"]) {
    errorpage("You are currently not logged in.");
} else {
    if (isset($sys_config["AUTO_RELOAD"])) unset($sys_config["AUTO_RELOAD"]);
    $varkeys=array_keys($vars);
    htmlhead();
    clusterhead($sys_config,"Partition utility page",$style="formate.css",
                array("th.new"=>array("background-color:#eeeeff","text-align:center"),
                      "td.new"=>array("background-color:#ddddee","text-align:center"),
                      "td.del"=>array("background-color:#ff8877","text-align:center"),
                      "td.name"=>array("background-color:#ddefdd","text-align:left"),
                      "td.discname"=>array("background-color:#ffee77","text-align:left"),
                      "th.fstype"=>array("background-color:#ddffdd","text-align:left"),
                      "td.fstype"=>array("background-color:#ccffcc","text-align:left"),
                      "th.bootable"=>array("background-color:#ddffdd","text-align:center"),
                      "td.bootable"=>array("background-color:#cceecc","text-align:center"),
                      "th.pnum"=>array("background-color:#dddddd","text-align:left"),
                      "td.pnum"=>array("background-color:#cccccc","text-align:left","white-space:nowrap"),
                      "th.fshex"=>array("background-color:#ccffcc","text-align:left"),
                      "td.fshex"=>array("background-color:#bbeebb","text-align:left","white-space:nowrap"),
                      "th.size"=>array("background-color:#ccffcc","text-align:left"),
                      "td.size"=>array("background-color:#bbeebb","text-align:left"),
                      "th.options"=>array("background-color:#ffffcc","text-align:left"),
                      "td.options"=>array("background-color:#eeeebb","text-align:left"),
                      "td.descr"=>array("background-color:#efdfdd","text-align:left"),
                      "td.valid"=>array("background-color:#88ff88","text-align:left"),
                      "th.dump"=>array("background-color:#ffffbb","text-align:center"),
                      "td.dump"=>array("background-color:#eeeeaa","text-align:center"),
                      "th.passno"=>array("background-color:#ffffaa","text-align:center"),
                      "td.passno"=>array("background-color:#eeee99","text-align:center"),
                      "td.invalid"=>array("background-color:#ff8888","text-align:left")
                      )
                );
    clusterbody($sys_config,"Partition utility",array("bc"));
  
    $DEFDNAME="/dev/hd";

    $ucl=usercaps($sys_db_con);
    if ($ucl["pu"]) {
        $all_type_array=array("00"=>"Empty",
                              "01"=>"DOS 12-bit FAT",
                              "02"=>"XENIX root",
                              "03"=>"XENIX /usr",
                              "04"=>"DOS 3.0+ 16-bit FAT (up to 32M)",
                              "05"=>"DOS 3.3+ Extended Partition",
                              "06"=>"DOS 3.31+ 16-bit FAT (over 32M)",
                              "07"=>"OS/2 IFS (e.g., HPFS)",
                              "07"=>"Windows NT NTFS/Advanced Unix",
                              "07"=>"QNX2.x pre-1988 (see below under IDs 4d-4f)",
                              "08"=>"OS/2 (v1.0-1.3 only)",
                              "08"=>"AIX boot partition",
                              "08"=>"SplitDrive",
                              "08"=>"Commodore DOS",
                              "08"=>"DELL partition spanning multiple drives",
                              "08"=>"QNX 1.x and 2.x ('qny')",
                              "09"=>"AIX data partition",
                              "09"=>"Coherent filesystem",
                              "09"=>"QNX 1.x and 2.x ('qnz')",
                              "0a"=>"OS/2 Boot Manager",
                              "0a"=>"Coherent swap partition",
                              "0a"=>"OPUS",
                              "0b"=>"WIN95 OSR2 32-bit FAT",
                              "0c"=>"WIN95 OSR2 32-bit FAT, LBA-mapped",
                              "0e"=>"WIN95: DOS 16-bit FAT, LBA-mapped",
                              "0f"=>"WIN95: Extended partition, LBA-mapped",
                              "10"=>"OPUS (?)",
                              "11"=>"Hidden DOS 12-bit FAT",
                              "12"=>"Configuration/diagnostics partition",
                              "14"=>"Hidden DOS 16-bit FAT <32M",
                              "16"=>"Hidden DOS 16-bit FAT >=32M",
                              "17"=>"Hidden IFS (e.g., HPFS)",
                              "18"=>"AST SmartSleep Partition",
                              "19"=>"Unused",
                              "1b"=>"Hidden WIN95 OSR2 32-bit FAT",
                              "1c"=>"Hidden WIN95 OSR2 32-bit FAT, LBA-mapped",
                              "1e"=>"Hidden WIN95 16-bit FAT, LBA-mapped",
                              "20"=>"Unused",
                              "21"=>"Reserved",
                              "21"=>"Unused",
                              "22"=>"Unused",
                              "23"=>"Reserved",
                              "24"=>"NEC DOS 3.x",
                              "26"=>"Reserved",
                              "31"=>"Reserved",
                              "32"=>"NOS",
                              "33"=>"Reserved",
                              "34"=>"Reserved",
                              "35"=>"JFS on OS/2 or eCS ",
                              "36"=>"Reserved",
                              "38"=>"THEOS ver 3.2 2gb partition",
                              "39"=>"Plan 9 partition",
                              "39"=>"THEOS ver 4 spanned partition",
                              "3a"=>"THEOS ver 4 4gb partition",
                              "3b"=>"THEOS ver 4 extended partition",
                              "3c"=>"PartitionMagic recovery partition",
                              "3d"=>"Hidden NetWare",
                              "40"=>"Venix 80286",
                              "41"=>"Linux/MINIX (sharing disk with DRDOS)",
                              "41"=>"Personal RISC Boot",
                              "41"=>"PPC PReP (Power PC Reference Platform) Boot",
                              "42"=>"Linux swap (sharing disk with DRDOS)",
                              "42"=>"SFS (Secure Filesystem)",
                              "42"=>"Windows 2000 dynamic extended partition marker",
                              "43"=>"Linux native (sharing disk with DRDOS)",
                              "44"=>"GoBack partition",
                              "45"=>"Boot-US boot manager",
                              "45"=>"Priam",
                              "45"=>"EUMEL/Elan ",
                              "46"=>"EUMEL/Elan ",
                              "47"=>"EUMEL/Elan ",
                              "48"=>"EUMEL/Elan ",
                              "4a"=>"Mark Aitchison's ALFS/THIN lightweight filesystem for DOS",
                              "4a"=>"AdaOS Aquila (Withdrawn)",
                              "4c"=>"Oberon partition",
                              "4d"=>"QNX4.x",
                              "4e"=>"QNX4.x 2nd part",
                              "4f"=>"QNX4.x 3rd part",
                              "4f"=>"Oberon partition",
                              "50"=>"OnTrack Disk Manager (older versions) RO",
                              "50"=>"Lynx RTOS",
                              "50"=>"Native Oberon (alt)",
                              "51"=>"OnTrack Disk Manager RW (DM6 Aux1)",
                              "51"=>"Novell",
                              "52"=>"CP/M",
                              "52"=>"Microport SysV/AT",
                              "53"=>"Disk Manager 6.0 Aux3",
                              "54"=>"Disk Manager 6.0 Dynamic Drive Overlay",
                              "55"=>"EZ-Drive",
                              "56"=>"Golden Bow VFeature Partitioned Volume.",
                              "56"=>"DM converted to EZ-BIOS",
                              "57"=>"DrivePro",
                              "57"=>"VNDI Partition",
                              "5c"=>"Priam EDisk",
                              "61"=>"SpeedStor",
                              "63"=>"Unix System V (SCO, ISC Unix, UnixWare, ...), Mach, GNU Hurd",
                              "64"=>"PC-ARMOUR protected partition",
                              "64"=>"Novell Netware 286, 2.xx",
                              "65"=>"Novell Netware 386, 3.xx or 4.xx",
                              "66"=>"Novell Netware SMS Partition",
                              "67"=>"Novell",
                              "68"=>"Novell",
                              "69"=>"Novell Netware 5+, Novell Netware NSS Partition",
                              "6e"=>"??",
                              "70"=>"DiskSecure Multi-Boot",
                              "71"=>"Reserved",
                              "73"=>"Reserved",
                              "74"=>"Reserved",
                              "74"=>"Scramdisk partition",
                              "75"=>"IBM PC/IX",
                              "76"=>"Reserved",
                              "77"=>"M2FS/M2CS partition",
                              "77"=>"VNDI Partition",
                              "78"=>"XOSL FS",
                              "7e"=>"Unused",
                              "7f"=>"Unused",
                              "80"=>"MINIX until 1.4a",
                              "81"=>"MINIX since 1.4b, early Linux",
                              "81"=>"Mitac disk manager",
                              "82"=>"Prime",
                              "82"=>"Solaris x86",
                              "82"=>"Linux swap",
                              "83"=>"Linux native partition",
                              "84"=>"OS/2 hidden C: drive",
                              "84"=>"Hibernation partition",
                              "85"=>"Linux extended partition",
                              "86"=>"Old Linux RAID partition superblock",
                              "86"=>"NTFS volume set",
                              "87"=>"NTFS volume set",
                              "8a"=>"Linux Kernel Partition (used by AiR-BOOT)",
                              "8b"=>"Legacy Fault Tolerant FAT32 volume",
                              "8c"=>"Legacy Fault Tolerant FAT32 volume using BIOS extd INT 13h",
                              "8d"=>"Free FDISK hidden Primary DOS FAT12 partitition",
                              "8e"=>"Linux Logical Volume Manager partition",
                              "90"=>"Free FDISK hidden Primary DOS FAT16 partitition",
                              "91"=>"Free FDISK hidden DOS extended partitition",
                              "92"=>"Free FDISK hidden Primary DOS large FAT16 partitition",
                              "93"=>"Hidden Linux native partition",
                              "93"=>"Amoeba",
                              "94"=>"Amoeba bad block table",
                              "95"=>"MIT EXOPC native partitions",
                              "97"=>"Free FDISK hidden Primary DOS FAT32 partitition",
                              "98"=>"Free FDISK hidden Primary DOS FAT32 partitition (LBA)",
                              "98"=>"Datalight ROM-DOS Super-Boot Partition",
                              "99"=>"DCE376 logical drive",
                              "9a"=>"Free FDISK hidden Primary DOS FAT16 partitition (LBA)",
                              "9b"=>"Free FDISK hidden DOS extended partitition (LBA)",
                              "9f"=>"BSD/OS",
                              "a0"=>"Laptop hibernation partition",
                              "a1"=>"Laptop hibernation partition",
                              "a1"=>"HP Volume Expansion (SpeedStor variant)",
                              "a3"=>"Reserved",
                              "a4"=>"Reserved",
                              "a5"=>"BSD/386, 386BSD, NetBSD, FreeBSD",
                              "a6"=>"OpenBSD",
                              "a7"=>"NEXTSTEP",
                              "a8"=>"Mac OS-X",
                              "a9"=>"NetBSD",
                              "aa"=>"Olivetti Fat 12 1.44MB Service Partition",
                              "ab"=>"Mac OS-X Boot partition",
                              "ab"=>"GO! partition",
                              "ae"=>"ShagOS filesystem",
                              "af"=>"ShagOS swap partition",
                              "b0"=>"BootStar Dummy",
                              "b1"=>"Reserved",
                              "b3"=>"Reserved",
                              "b4"=>"Reserved",
                              "b6"=>"Reserved",
                              "b6"=>"Windows NT mirror set (master), FAT16 file system",
                              "b7"=>"Windows NT mirror set (master), NTFS file system",
                              "b7"=>"BSDI BSD/386 filesystem",
                              "b8"=>"BSDI BSD/386 swap partition",
                              "bb"=>"Boot Wizard hidden",
                              "be"=>"Solaris 8 boot partition",
                              "c0"=>"CTOS",
                              "c0"=>"REAL/32 secure small partition",
                              "c0"=>"NTFT Partition",
                              "c0"=>"DR-DOS/Novell DOS secured partition",
                              "c1"=>"DRDOS/secured (FAT-12)",
                              "c2"=>"Reserved for DR-DOS 7+",
                              "c2"=>"Hidden Linux",
                              "c3"=>"Hidden Linux swap",
                              "c4"=>"DRDOS/secured (FAT-16, < 32M)",
                              "c5"=>"DRDOS/secured (extended)",
                              "c6"=>"DRDOS/secured (FAT-16, >= 32M)",
                              "c6"=>"Windows NT corrupted FAT16 volume/stripe set",
                              "c7"=>"Windows NT corrupted NTFS volume/stripe set",
                              "c7"=>"Syrinx boot",
                              "c8"=>"Reserved",
                              "c9"=>"Reserved",
                              "ca"=>"Reserved",
                              "cb"=>"reserved for DRDOS/secured (FAT32)",
                              "cc"=>"reserved for DRDOS/secured (FAT32, LBA)",
                              "cd"=>"CTOS Memdump? ",
                              "ce"=>"reserved for DRDOS/secured (FAT16, LBA)",
                              "d0"=>"REAL/32 secure big partition",
                              "d1"=>"Old Multiuser DOS secured FAT12",
                              "d4"=>"Old Multiuser DOS secured FAT16 <32M",
                              "d5"=>"Old Multiuser DOS secured extended partition",
                              "d6"=>"Old Multiuser DOS secured FAT16 >=32M",
                              "d8"=>"CP/M-86",
                              "da"=>"Non-FS Data",
                              "db"=>"Digital Research CP/M, Concurrent CP/M, Concurrent DOS",
                              "db"=>"CTOS (Convergent Technologies OS -Unisys)",
                              "db"=>"KDG Telemetry SCPU boot",
                              "dd"=>"Hidden CTOS Memdump? ",
                              "de"=>"Dell PowerEdge Server utilities (FAT fs)",
                              "df"=>"DG/UX virtual disk manager partition",
                              "df"=>"BootIt EMBRM",
                              "e0"=>"Reserved by ",
                              "e1"=>"DOS access or SpeedStor 12-bit FAT extended partition",
                              "e3"=>"DOS R/O or SpeedStor",
                              "e4"=>"SpeedStor 16-bit FAT extended partition < 1024 cyl.",
                              "e5"=>"Tandy DOS with logical sectored FAT",
                              "e5"=>"Reserved",
                              "e6"=>"Reserved",
                              "eb"=>"BeOS",
                              "ed"=>"Reserved for Matthias Paul's Spryt*x",
                              "ee"=>"Indication that this legacy MBR is followed by an EFI header",
                              "ef"=>"Partition that contains an EFI file system",
                              "f0"=>"Linux/PA-RISC boot loader",
                              "f1"=>"SpeedStor",
                              "f2"=>"DOS 3.3+ secondary partition",
                              "f3"=>"Reserved",
                              "f4"=>"SpeedStor large partition",
                              "f4"=>"Prologue single-volume partition",
                              "f5"=>"Prologue multi-volume partition",
                              "f6"=>"Reserved",
                              "f9"=>"pCache",
                              "fa"=>"Bochs",
                              "fb"=>"VMware File System partition",
                              "fc"=>"VMware Swap partition",
                              "fd"=>"Linux raid partition with autodetect using persistent superblock",
                              "fe"=>"SpeedStor > 1024 cyl.",
                              "fe"=>"LANstep",
                              "fe"=>"IBM PS/2 IML (Initial Microcode Load) partition,",
                              "fe"=>"Windows NT Disk Administrator hidden partition",
                              "fe"=>"Linux Logical Volume Manager partition (old)",
                              "ff"=>"Xenix Bad Block Table");
        // extended disk partition-types
        $all_ext_ids=array("05","0f","3b","42","85","91","9b","c5","d5","e1","e4");
        // disk size prefixes
        $all_size_pfixes=array(1000=>"MB",1000*1000=>"GB",1000*1000*1000=>"TB");
        // get all filesystems
        $all_filesystems=get_all_fs_types();
        // all sys-filesystems
        $all_sys_fs=array("proc","usbfs","devpts","sysfs","tmpfs");
        // remap filesystems
        $all_fs_t2=array();
        foreach ($all_filesystems as $fs_idx=>$fs_stuff) {
            $hexid=substr("00$fs_stuff->hexid",-2,2);
            $all_fs_t2[$hexid]=$fs_stuff;
        }
	if (is_set("sel_parts",&$vars)) {
	    $sel_parts=$vars["sel_parts"];
	} else {
	    $sel_parts=array();
	}
	$hidden_sel="";
	foreach ($sel_parts as $sel_part) $hidden_sel.="<input type=hidden name=\"sel_parts[]\" value=\"$sel_part\"/>\n";
        // simple protocol
        $log_stack_1=new messagelog();
        $log_stack_2=new messagelog();
        $log_stack_3=new messagelog();
        function get_d_name($s) { return $s->disc; }
        function get_p_num($s) { return $s->pnum; }
        // get partition-table tree
        list($pt_tree,$first_valid)=get_partition_tree();
        // check if the selected partitions are still valid
        $r_sel_parts=array();
        foreach ($sel_parts as $sel_p) {
            if (in_array($sel_p,array_keys($pt_tree))) $r_sel_parts[]=$sel_p;
        }
        $sel_parts=$r_sel_parts;
        // check for sanity
	$f_block=new StdClass();
	$f_block->log_stack=&$log_stack_1;
	$f_block->sel_parts=$sel_parts;
        array_walk($pt_tree,"sanity_check_part",$f_block);
        // check for changes in the pt-tree
        if (is_set("lowselect",&$vars)) {
	foreach ($sel_parts as $pt_idx) {
	    $pt_stuff=&$pt_tree[$pt_idx];
        //foreach ($pt_tree as $pt_idx=>$pt_stuff) {
            if (is_set("del_pt_$pt_idx",&$vars)) {
                $mres=query("SELECT * FROM partition_disc WHERE partition_table=$pt_idx");
                $pt_array=array();
                while ($mfr=mysql_fetch_object($mres)) $pt_array[]="partition_disc=$mfr->partition_disc_idx";
                if (count($pt_array)) {
                    $num_p_del=delete_from_table("partition",implode(" OR ",$pt_array));
                    $log_stack_2->add_message("Deleted $num_p_del partitions belonging to partition'{$pt_stuff->name}'","ok",1);
                    $num_pd_del=delete_from_table("partition_disc","partition_table=$pt_idx");
                    $log_stack_2->add_message("Deleted $num_pd_del partition_discs belonging to '{$pt_stuff->name}'","ok",1);
                }
                query("DELETE FROM partition_table WHERE partition_table_idx=$pt_idx");
                $log_stack_2->add_message("Deleted partition_table named '{$pt_stuff->name}'","ok",1);
                query("DELETE FROM sys_partition WHERE partition_table=$pt_idx");
                $log_stack_2->add_message("Deleted sys_partition_tables belonging to '{$pt_stuff->name}'","ok",1);
                unset($pt_tree[$pt_idx]);
            } else {
                if ($pt_stuff->modify_bootloader != is_set("mbl_$pt_idx", &$vars)) {
                    $pt_stuff->modify_bootloader = is_set("mbl_$pt_idx", &$vars);
                    update_table("partition_table","modify_bootloader={$pt_stuff->modify_bootloader} WHERE partition_table_idx=$pt_idx");
                }
                foreach ($pt_stuff->sys_partitions as $sysp_idx=>$sysp_stuff) {
                    $id="{$pt_idx}_{$sysp_idx}";
                    if (is_set("sysp_del_$id",&$vars)) {
                        $log_stack_2->add_message("Deleted sysp_partition type $sysp_stuff->name from partition_table '{$pt_stuff->name}'","ok",1);
                        query("DELETE FROM sys_partition WHERE sys_partition_idx=$sysp_idx");
                    } else {
                        $c_array=array();
                        if (isset($vars["sysp_mp_$id"]) && $vars["sysp_mp_$id"] != $sysp_stuff->mountpoint) {
                            $new_mp=$vars["sysp_mp_$id"];
                            $c_array[]="mountpoint='".mysql_escape_string($new_mp)."'";
                            $log_stack_2->add_message("Changed mountpoint of sys_partition $sysp_stuff->name (partition_table '{$pt_stuff->name}') to '$new_mp'","ok",1);
                        }
                        if (isset($vars["sysp_mo_$id"]) && $vars["sysp_mo_$id"] != $sysp_stuff->mount_options) {
                            $new_options=$vars["sysp_mo_$id"];
                            if (preg_match("/\s+/",$new_options)) {
                                $log_stack_2->add_message("Cannot change mount_options of syspartition type '$sysp_stuff->name'","options contains spaces",0);
                            } else {
                                $c_array[]="mount_options='".mysql_escape_string($new_options)."'";
                                $log_stack_2->add_message("Changed mount_options of sys_partition $sysp_stuff->name (partition_table '{$pt_stuff->name}') to '$new_options'","ok",1);
                            }
                        }
                        if ($c_array) {
                            update_table("sys_partition",implode(",",$c_array)." WHERE sys_partition_idx=$sysp_idx");
                        }
                    }
                }
                if (is_set("new_sysp_$pt_idx",&$vars) && $vars["new_sysp_$pt_idx"]) {
                    $new_sysp_type=$vars["new_sysp_$pt_idx"];
                    $mpoint=$vars["new_sysp_mp_$pt_idx"];
                    $options=$vars["new_sysp_mo_$pt_idx"];
                    if (preg_match("/\s+/",$options)) {
                        $log_stack_2->add_message("Cannot add new syspartition to partition_type $pt_stuff->name","options contains spaces",0);
                    } else {
                        $ins_idx=insert_table("sys_partition","0,$pt_idx,'".mysql_escape_string($new_sysp_type)."','".
                                              mysql_escape_string($mpoint)."','".mysql_escape_string($options)."',null");
                        $log_stack_2->add_message("Inserted new syspartition $new_sysp_type to partition_type $pt_stuff->name (mountpoint $mpoint, options '$options'","OK",1);
                    }
                }
                foreach ($pt_stuff->discs as $pd_idx=>$pd_stuff) {
                    if (is_set("del_disc_{$pt_idx}_{$pd_idx}",&$vars)) {
                        $num_p_del=delete_from_table("partition","partition_disc=$pd_idx");
                        $log_stack_2->add_message("Deleted $num_p_del partitions belonging to disc '{$pd_stuff->name}'","ok",1);
                        query("DELETE FROM partition_disc WHERE partition_disc_idx=$pd_idx");
                        $log_stack_2->add_message("Deleted disc $pd_stuff->name from partition_table '{$pt_stuff->name}'","ok",1);
                        unset($pt_stuff->discs[$pd_idx]);
                    } else {
                        $id="{$pt_idx}_{$pd_idx}";
                        foreach ($pd_stuff->partitions as $p_idx=>$p_stuff) {
                            $pid="{$id}_{$p_stuff->partition_idx}";
                            if (is_set("del_p_$pid",&$vars)) {
                                query("DELETE FROM partition WHERE partition_idx=$p_stuff->partition_idx");
                                $log_stack_2->add_message("Deleted partition $pd_stuff->disc$p_stuff->pnum from partition_table '{$pt_stuff->name}'","ok",1);
                                unset($pt_stuff->discs[$pd_idx]->partitions[$p_idx]);
                            } else {
                                // check for changes
                                $c_array=array();
                                // bootable-flag
                                if (is_set("boot_$pid",&$vars) xor $p_stuff->bootable) {
                                    $c_array[]="bootable=".strval(1-$p_stuff->bootable);
                                    $b_str=(($p_stuff->bootable) ? "Disabled" : "Enabled");
                                    $log_stack_2->add_message("$b_str bootable-Flag of partition $pd_stuff->disc$p_stuff->pnum (partition_table '{$pt_stuff->name}')","ok",1);
                                }
                                // dump/passno
                                if (isset($vars["p_dump_$pid"])) {
                                    $new_freq=$vars["p_dump_$pid"];
                                    $new_passno=$vars["p_passno_$pid"];
                                    if ($new_freq != $p_stuff->fs_freq || $new_passno != $p_stuff->fs_passno) {
                                        $c_array[]="fs_freq=$new_freq";
                                        $c_array[]="fs_passno=$new_passno";
                                        $log_stack_2->add_message("Setting freq and passno-field of partition $pd_stuff->disc$p_stuff->pnum to $new_freq / $new_passno (partition_table '{$pt_stuff->name}')","OK",1);
                                    }
                                }
                                // size
                                if (isset($vars["p_sz_$pid"]) && $vars["p_sz_$pid"] != $p_stuff->size) {
                                    $new_sz=$vars["p_sz_$pid"];
                                    if (preg_match("/^\d+$/",$new_sz)) {
                                        $log_stack_2->add_message("Canged size of partition $pd_stuff->disc$p_stuff->pnum from $p_stuff->size to $new_sz MByte (partition_table '{$pt_stuff->name}')","OK",1);
                                        $c_array[]="size=$new_sz";
                                    } else {
                                        $log_stack_2->add_message("Cannot change size of partition $pd_stuff->disc$p_stuff->pnum (partition_table '{$pt_stuff->name}')","not positive integer",0);
                                    }
                                }
                                // mount options
                                if (isset($vars["p_opt_$pid"]) && $vars["p_opt_$pid"] != $p_stuff->mount_options) {
                                    $new_opts=$vars["p_opt_$pid"];
                                    if (preg_match("/\s+/",$new_opts)) {
                                        $log_stack_2->add_message("Cannot change mount options of partition $pd_stuff->disc$p_stuff->pnum (partition_table '{$pt_stuff->name}')","options contains spaces",0);
                                    } else {
                                        $log_stack_2->add_message("Canged mount options of partition $pd_stuff->disc$p_stuff->pnum from '$p_stuff->mount_options' to '$new_opts' (partition_table '{$pt_stuff->name}')","OK",1);
                                        $c_array[]="mount_options='".mysql_escape_string($new_opts)."'";
                                    }
                                }
                                // mount point
                                if (isset($vars["p_mp_$pid"]) && $vars["p_mp_$pid"] != $p_stuff->mountpoint) {
                                    $new_mpoint=$vars["p_mp_$pid"];
                                    if (preg_match("/^\/.*$/",$new_mpoint)) {
                                        $c_array[]="mountpoint='".mysql_escape_string($new_mpoint)."'";
                                        $log_stack_2->add_message("Changed mountpoint of partition $pd_stuff->disc$p_stuff->pnum from '$p_stuff->mountpoint' to '$new_mpoint' (partition_table '{$pt_stuff->name}')","OK",1);
                                    } else {
                                        $log_stack_2->add_message("Cannot change mountpoint of partition $pd_stuff->disc$p_stuff->pnum (partition_table '{$pt_stuff->name}')","mountpoint syntax ($new_mpoint)",0);
                                    }
                                }
                                if ($c_array) {
                                    update_table("partition",implode(",",$c_array)." WHERE partition_idx=$p_stuff->partition_idx");
                                }
                            }
                        }
                        if (is_set("new_p_pnum_$id",&$vars) && $vars["new_p_pnum_$id"]) {
                            $used_p_idxs=array_map("get_p_num",$pd_stuff->partitions);
                            $ins_part=$vars["new_p_pnum_$id"];
                            if (in_array($ins_part,$used_p_idxs)) {
                                $log_stack_2->add_message("Cannot add new partition to partition_type $pt_stuff->name, disc $pd_stuff->disc","partition number already used",0);
                            } else {
                                $mpoint=trim($vars["new_p_mp_$id"]);
                                if (preg_match("/^\/.*$/",$mpoint)) {
                                    $hexid=$vars["new_p_fs_$id"];
                                    if ($hexid == "0") {
                                        $part_fs=0;
                                        $hexid=strtolower($vars["new_p_fsh_$id"]);
                                    } else {
                                        $part_fs=$hexid;
                                        $hexid=strtolower($all_filesystems[$hexid]->hexid);
                                    }
                                    $hexid=substr("00$hexid",-2,2);
                                    if (preg_match("/^[0-9a-z]{1,2}$/",$hexid)) {
                                        // now we have the mountpoint and the hexid
                                        if (is_set("new_p_sz_$id",&$vars)) {
                                            $p_size=$vars["new_p_sz_$id"];
                                        } else {
                                            $p_size="0";
                                        }
                                        if (preg_match("/^\d+$/",$p_size)) {
                                            $p_size=intval($p_size)*$vars["new_p_szd_$id"]/1000;
                                            $options=$vars["new_p_opt_$id"];
                                            if (preg_match("/\s+/",$options)) {
                                                $log_stack_2->add_message("Cannot add new partition to partition_type $pt_stuff->name, disc $pd_stuff->disc","options contains spaces",0);
                                            } else {
                                                // check for swap-space and ext-partition
                                                $is_swap=0;
                                                $is_ext=0;
                                                if (in_array($hexid,array_keys($all_fs_t2))) {
                                                    if ($all_fs_t2[$hexid]->identifier=="s") $is_swap=1;
                                                }
                                                if (in_array($hexid,$all_ext_ids)) $is_ext=1;
                                                if ($is_swap || $is_ext) {
                                                    $boot_f=0;
                                                    $dump_num=0;
                                                    $passno_num=0;
                                                    $mpoint="";
                                                    //if ($is_ext) {
                                                    //    print_r($used_p_idxs);
                                                    //}
                                                }  else {
                                                    if (is_set("new_p_boot_$id",&$vars)) {
                                                        $boot_f=1;
                                                    } else {
                                                        $boot_f=0;
                                                    }
                                                    $dump_num=$vars["new_p_dump_$id"];
                                                    $passno_num=$vars["new_p_passno_$id"];
                                                }
                                                $ins_idx=insert_table("partition","0,$pd_idx,'".mysql_escape_string($mpoint)."','$hexid',$p_size,'".mysql_escape_string($options).
                                                                      "',$ins_part,$boot_f,$dump_num,$passno_num,$part_fs,null");
                                                if ($ins_idx) {
                                                    //echo "<br>**$hexid**$mpoint**$p_size<br>";;
                                                    $log_stack_2->add_message("Added new partition to partition_type $pt_stuff->name, disc $pd_stuff->disc","OK",1);
                                                } else {
                                                    $log_stack_2->add_message("Cannot add new partition to partition_type $pt_stuff->name, disc $pd_stuff->disc","SQL Error",0);
                                                }
                                            }
                                        } else {
                                            $log_stack_2->add_message("Cannot add new partition to partition_type $pt_stuff->name, disc $pd_stuff->disc","parser error for size $p_size",0);
                                        }
                                    } else {
                                        $log_stack_2->add_message("Cannot add new partition to partition_type $pt_stuff->name, disc $pd_stuff->disc","wrong hexid for partition",0);
                                    }
                                } else {
                                    $log_stack_2->add_message("Cannot add new partition to partition_type $pt_stuff->name, disc $pd_stuff->disc","mount-point syntax ($mpoint)",0);
                                }
                            }
                        }
                    }
                }
                $disc_names=array_map("get_d_name",$pt_stuff->discs);
                //print_r($disc_names);
                if (is_set("new_discname_$pt_idx",&$vars) && $vars["new_discname_$pt_idx"] != $DEFDNAME) {
                    $nd_name=$vars["new_discname_$pt_idx"];
                    if (in_array($nd_name,$disc_names)) {
                        $log_stack_2->add_message("Cannot add new disc '$nd_name' to partition_table '$pt_stuff->name'","Disc already present",0);
                    } else {
                        if (preg_match("/^\/dev\/.*$/",$nd_name)) {
                            $ins_idx=insert_table("partition_disc","0,$pt_idx,'".mysql_escape_string($nd_name)."',0,null");
                            if ($ins_idx) {
                                $log_stack_2->add_message("Added new disc '$nd_name' to partition_table '$pt_stuff->name'","ok",1);
                            } else {
                                $log_stack_2->add_message("Cannot add new disc '$nd_name' to partition_table '$pt_stuff->name'","SQL Error",0);
                            }
                        } else {
                            $log_stack_2->add_message("Cannot add new disc to partition_table '$pt_stuff->name'","discname must start with '/dev/'",0);
                        }
                    }
                }
            }
        }
        if (is_set("new_pt",&$vars)) {
            if (is_set("new_name",&$vars)) {
                $new_pt_name=$vars["new_name"];
                $ins_idx=insert_table("partition_table","0,'".mysql_escape_string($new_pt_name)."','".mysql_escape_string($vars["new_descr"])."',0,1,null");
                if ($ins_idx) {
                    $log_stack_2->add_message("Added new partition_table named '$new_pt_name'","ok",1);
                } else {
                    $log_stack_2->add_message("Cannot add new partition_table named '$new_pt_name'","duplicate key?",0);
                }
            } else {
                $log_stack_2->add_message("Cannot add new partition_table","empty name",0);
            }
        }
    }
        // re-read partition-table tree
        list($pt_tree,$second_valid)=get_partition_tree();
	$f_block->log_stack=&$log_stack_3;
        array_walk($pt_tree,"sanity_check_part",$f_block);
	foreach ($first_valid as $pt_idx=>$valid1) {
	    if ($valid1 != $pt_tree[$pt_idx]->valid) {
		if ($valid1) {
		    $log_stack_3->add_message("Setting partition_table {$pt_tree[$pt_idx]->name} invalid","warn",2);
		} else {
		    $log_stack_3->add_message("Setting partition_table {$pt_tree[$pt_idx]->name} valid","ok",1);
		}
		update_table("partition_table","valid={$pt_tree[$pt_idx]->valid} WHERE partition_table_idx=$pt_idx");
	    }
	}
	// select box
	if (count(array_keys($pt_tree))) {
	    message("Please select the partition-tables to modify:");
            echo "<form action=\"{$sys_config['script_name']}?".write_sid()."\" method=post>";
	    echo "<div class=\"center\">\n";
	    echo "<table class=\"simplesmall\">";
	    echo "<tr><td><select name=\"sel_parts[]\" multiple size=5 >"; 
	    foreach ($pt_tree  as $pt_idx=>$pt_stuff) {
		echo "<option value=\"$pt_idx\" ";
		if (in_array($pt_idx,$sel_parts)) echo " selected "; 
		echo ">";
		if (!$pt_stuff->valid) echo "(*) ";
		if ($pt_stuff->modify_bootloader) echo "(mbl) ";
		echo "$pt_stuff->name";
		echo "</option>\n";
	    }
	    echo "</select></td></tr>\n";
	    echo "<tr><td><input type=submit value=\"select\"/></td></tr>\n";
	    echo "</table>";
	    echo "</center>\n";
	    echo "</form>\n";
	} else {
	    message("No partition-tables defined");
	}
        if ($log_stack_1->get_num_messages()) $log_stack_1->print_messages("Before altering");
        if ($log_stack_2->get_num_messages()) $log_stack_2->print_messages("While altering");
        if ($log_stack_3->get_num_messages()) $log_stack_3->print_messages("After altering");
        echo "<form action=\"{$sys_config['script_name']}?".write_sid()."\" method=post>";
	echo $hidden_sel;
    echo "<input type=hidden name=\"lowselect\" value=\"1\" />\n";
        echo "<div class=\"center\">\n";
        echo "<table class=\"normal\">";
	foreach ($sel_parts as $pt_idx) {
	    $pt_stuff=&$pt_tree[$pt_idx];
            echo "<tr><td class=\"del\" rowspan=\"2\"><input type=checkbox name=\"del_pt_$pt_idx\"/></td>\n";
            echo "<td class=\"name\">Name:<input size=\"20\" maxlength=\"50\" name=\"name_pt_$pt_idx\" value=\"$pt_stuff->name\"/></td>\n";
            echo "<td class=\"descr\">Description:<input size=\"40\" maxlength=\"250\" name=\"descr_pt_$pt_idx\" value=\"$pt_stuff->description\"/>\n";
            echo ", modify bootloader: <input type=checkbox name=\"mbl_$pt_idx\" ".($pt_stuff->modify_bootloader ? "checked" : "")." /></td>\n";
            if ($pt_stuff->valid) {
                echo "<td class=\"valid\">Table is valid</td>";
            } else {
                echo "<td class=\"invalid\">Table is invalid</td>";
            }
            echo "</tr>\n";
            echo "<tr><td class=\"blind\" colspan=\"3\"><table class=\"normal\">\n";
            // sys partitions
            echo "<tr><td class=\"blind\" colspan=\"9\"><table class=\"blind\">\n";
            foreach ($pt_stuff->sys_partitions as $sysp_idx=>$sysp_stuff) {
                $id="{$pt_idx}_{$sysp_idx}";
                echo "<tr><td class=\"pnum\"><input name=\"sysp_del_$id\" type=checkbox /> $sysp_stuff->name</td>\n";
                echo "<td class=\"name\"><input name=\"sysp_mp_$id\" value=\"$sysp_stuff->mountpoint\" size=\"20\" maxlength=\"62\"/></td>\n";
                echo "<td class=\"options\"><input name=\"sysp_mo_$id\" value=\"$sysp_stuff->mount_options\" size=\"30\" maxlength=\"200\"/></td>\n";
                echo "</tr>\n";
            }
            $id=$pt_idx;
            //echo "<td class=\"new\"><input type=checkbox name=\"new_sysp_$id\"/></td>\n";
            echo "<tr><td class=\"pnum\">";
            echo "<select name=\"new_sysp_$id\" >";
            echo "<option value=\"\" selected >None</option>\n";
            foreach ($all_sys_fs as $sys_fs_name) {
                echo "<option value=\"$sys_fs_name\">$sys_fs_name</option>\n";
            } 
            echo "</select>";
            echo "</td>\n";
            echo "<td class=\"name\"><input name=\"new_sysp_mp_$id\" value=\"/\" size=\"20\" maxlength=\"62\"/></td>\n";
            echo "<td class=\"options\"><input name=\"new_sysp_mo_$id\" maxlength=\"200\" size=\"30\" value=\"defaults\"/></td>\n";
            echo "</tr></table></td></tr>\n";
            foreach ($pt_stuff->discs as $d_idx=>$d_stuff) {
                $id="{$pt_idx}_{$d_idx}";
                echo "<tr>";
                //echo "<td class=\"blind\" ><table class=\"normal\">\n";
                //echo "<tr>";
                echo "<td class=\"discname\" colspan=\"9\">Disc Name:<input name=\"discname_$id\" size=\"40\" maxlength=\"62\" value=\"{$d_stuff->disc}\"/>";
                echo ", delete: <input type=checkbox name=\"del_disc_$id\"/>, ";
                echo get_size_str($d_stuff->fs_size)." Filesystem, ".get_size_str($d_stuff->swap_size)." swap";
                echo "</td>\n";
                echo "</tr>\n";
                echo "<tr><th class=\"pnum\">Partition</th>\n";
                echo "<th class=\"bootable\">boot</th>\n";
                echo "<th class=\"name\">MountPoint</th>\n";
                echo "<th class=\"fstype\">FsType</th>\n";
                echo "<th class=\"fshex\">PtID</th>\n";
                echo "<th class=\"size\">Size</th>\n";
                echo "<th class=\"options\">Mount Options</th>\n";
                echo "<th class=\"dump\">dump</th>\n";
                echo "<th class=\"passno\">pass</th>\n";
                echo "</tr>\n";
                foreach ($d_stuff->partitions as $p_idx=>$p_stuff) {
                    $pid="{$pt_idx}_{$d_idx}_{$p_stuff->partition_idx}";
                    $hexid=substr("00{$p_stuff->partition_hex}",-2,2);
                    echo "<tr>";
                    echo "<td class=\"pnum\">$d_stuff->disc$p_stuff->pnum, <input type=checkbox name=\"del_p_$pid\"/></td>\n";
                    if ($p_stuff->is_swap) {
                        $num_rows=4;
                    } else if ($p_stuff->is_ext) {
                        $num_rows=8;
                    } else if ($p_stuff->is_empty) {
                        $num_rows=8;
                    } else {
                        $num_rows=1;
                        echo "<td class=\"bootable\"><input type=checkbox name=\"boot_$pid\" ".($p_stuff->bootable ? " checked " : "")."/></td>\n";
                        echo "<td class=\"name\"><input name=\"p_mp_$pid\" value=\"$p_stuff->mountpoint\" size=\"20\" maxlength=\"62\"/></td>\n";
                        echo "<td class=\"fstype\">";
                        if ($p_stuff->partition_fs) {
                            echo $all_filesystems[$p_stuff->partition_fs]->descr;
                        } else {
                            echo htmlspecialchars("<unknown>");
                        }
                        echo "</td>\n";
                    }
                    echo "<td class=\"fshex\" colspan=\"$num_rows\">$hexid (".htmlspecialchars($all_type_array[$hexid]).")</td>\n";
                    if (!($p_stuff->is_ext || $p_stuff->is_empty)) {
                        echo "<td class=\"size\"><input name=\"p_sz_$pid\" value=\"$p_stuff->size\" maxlenght=\"20\" size=\"6\"/> MB</td>\n";
                        echo "<td class=\"options\"><input name=\"p_opt_$pid\" value=\"$p_stuff->mount_options\" maxlenght=\"200\" size=\"30\"/></td>\n";
                        if ($p_stuff->is_swap) {
                            echo "<td class=\"dump\">0</td>\n";
                            echo "<td class=\"passno\">0</td>\n";
                        } else {
                            echo "<td class=\"dump\"><select name=\"p_dump_$pid\">";
                            for ($i=0;$i<2;$i++) {
                                echo "<option value=\"$i\" ";
                                if ($p_stuff->fs_freq==$i) echo " selected ";
                                echo ">$i</option>\n";
                            }
                            echo "</select></td>\n";
                            echo "<td class=\"passno\"><select name=\"p_passno_$pid\">";
                            for ($i=0;$i<3;$i++) {
                                echo "<option value=\"$i\" ";
                                if ($p_stuff->fs_passno==$i) echo " selected ";
                                echo ">$i</option>\n";
                            }
                            echo "</select></td>\n";
                        }
                    }
                    echo "</tr>\n";
                }
                if (count($d_stuff->plist)) {
                    echo "<tr><td class=\"pnum\">$d_stuff->disc";
                    echo "<select name=\"new_p_pnum_$id\" />";
                    echo "<option value=\"0\" >None</option>\n";
                    foreach ($d_stuff->plist as $pnum) {
                        echo "<option value=\"$pnum\">$pnum</option>\n";
                    }
                    echo "</select></td>\n";
                    echo "<td class=\"bootable\"><input type=checkbox name=\"new_p_boot_$id\" /></td>\n";
                    echo "<td class=\"name\"><input name=\"new_p_mp_$id\" value=\"/\" size=\"20\" maxlength=\"62\"/></td>\n";
                    echo "<td class=\"fstype\"><select name=\"new_p_fs_$id\" >";
                    echo "<option value=\"0\">use Hex-id   ----></option>\n";
                    foreach ($all_filesystems as $fs_idx=>$fs_stuff) {
                        $hexid=substr("00{$fs_stuff->hexid}",-2,2);
                        echo "<option value=\"$fs_idx\" ";
                        if ($hexid == "83") echo " selected ";
                        echo ">[$hexid] $fs_stuff->descr ($fs_stuff->identifier)</option>\n";
                    }
                    echo "</select></td>\n";
                    echo "<td class=\"fshex\">0x<input size=\"3\" name=\"new_p_fsh_$id\" maxlength=\"2\" value=\"00\"/></td>\n";
                    echo "<td class=\"size\"><input value=\"50\" name=\"new_p_sz_$id\" maxlength=\"20\" size=\"6\" /> ";
                    echo "<select name=\"new_p_szd_$id\">";
                    foreach ($all_size_pfixes as $pfix=>$ptype) echo "<option value=\"$pfix\">$ptype</option>\n";
                    echo "</select></td>\n";
                    echo "<td class=\"options\"><input name=\"new_p_opt_$id\" maxlength=\"200\" size=\"30\" value=\"defaults\"/></td>\n";
                    echo "<td class=\"dump\"><select name=\"new_p_dump_$id\">";
                    echo "<option value=\"0\">0</option><option value=\"1\">1</option>\n";
                    echo "</select></td>\n";
                    echo "<td class=\"passno\"><select name=\"new_p_passno_$id\">";
                    echo "<option value=\"0\">0</option><option value=\"1\" >1</option><option value=\"2\" >2</option>\n";
                    echo "</select></td>\n";
                    echo "</tr>\n";
                }
                //echo "</table></td></tr>\n";
            }
            echo "<tr><td class=\"discname\" colspan=\"9\">Disc Name (change to add new):<input name=\"new_discname_$pt_idx\" size=\"40\" maxlength=\"62\" value=\"$DEFDNAME\"/></td>\n";
            echo "</tr>\n";
            echo "</table></td></tr>\n";
        }
        echo "<tr><td class=\"new\"><input type=checkbox name=\"new_pt\"/></td>\n";
        echo "<td class=\"name\">Name:<input size=\"20\" maxlength=\"50\" name=\"new_name\" value=\"newpt\"/></td>\n";
        echo "<td class=\"descr\" colspan=\"2\">Description:<input size=\"40\" maxlength=\"250\" name=\"new_descr\" value=\"New partitiontable\"/></td>\n";
        echo "</tr>\n";
        echo "</table>\n";
        echo "<input type=submit value=\"submit\"/>";
        echo "</div></form>\n";
        
    } else {
        message ("You are not allowed to access this page.");
    }
    writefooter($sys_config);
}
?>
