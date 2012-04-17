#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008,2009,2010 Andreas Lang-Nevyjel
#
# this file is part of cluster-backbone
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
""" generates the inital ramdisk for clusterboot """

import sys
import os, os.path
import getopt
import commands
import re
import tempfile
import shutil
import copy
import stat
import statvfs
import pprint
import logging_tools
import process_tools
import server_command
try:
    import mysql_tools
except ImportError:
    mysql_tools = None
import socket
import time
import configfile
import gzip
import fnmatch

MOD_REFUSE_LIST = ["3w-9xxx", "3w-xxxx", "af_packet", "ata_piix",
                   "autofs", "eata", "gdth",
                   "jbd", "libata", "mptbase",
                   "mptctl", "mptscsih", "reiserfs",
                   "sata_promise", "sata_via",
                   "scsi_mod", "sg", "sym53c8xx", "unix"]

LINUXRC_NAMES = ["init", "linuxrc"]

stage1_dir_dict = {0 : ["var/empty",
                        "sys",
                        "dev/pts"],
                   1 : ["root", "tmp", "dev", "etc/pam.d", "proc",
                        "var/run", "var/log", "sbin", "usr/lib", "usr/share"]}
stage1_file_dict = {0 : ["inetd", "xinetd", "in.rshd", "tcpd", "in.rlogind", "whoami", "ntpdate", "ps", "rmmod", "rmmod.old", "lsmod.old", "depmod.old",
                         "insmod.old", "modprobe.old", "route", "free", "arp", "login", "mount.nfs", "lsof"],
                    1 : ["readlink", "ethtool", "cp", "mount", "cat", "ls", "mount", "mkdir", "find", "head",
                         "tar", "gunzip", "umount", "rmdir", "egrep", "fgrep", "grep", "rm", "chmod", "basename",
                         "sed", "dmesg", "ping", "mknod", "true", "false", "logger", "modprobe", "bash", "load_firmware.sh",
                         "lsmod", "depmod", "insmod", "mkfs.ext2",
                         "ifconfig", "pivot_root", "init", "tell_mother", "bzip2", "bunzip2", "cut", "tr", "chroot",
                         "killall", "seq", "hoststatus", "chown", "ldconfig",
                         "df", "wc", "tftp", "mkfifo", "sleep", "reboot", "stty", "reset", "du", "tail", "lspci", "tee"]}

stage2_dir_dict = {0 : ["sys",
                        "var/empty"],
                   1 : ["root", "tmp", "dev", "etc/pam.d", "proc",
                        "var/run", "var/log", "dev/pts", "sbin", "usr/lib", "usr/share"]}
stage2_file_dict = {0 : ["inetd", "xinetd", "mkfs.xfs", "rmmod.old", "lsmod.old", "depmod.old", "insmod.old",
                         "modprobe.old", "in.rshd", "in.rlogind", "mount.nfs"],
                    1 : ["ethtool", "sh", "strace", "bash", "echo", "cp", "mount", "cat", "ls", "mount", "mkdir",
                         "df", "tar", "gzip", "gunzip", "umount", "rmdir", "egrep", "fgrep", "grep", "basename",
                         "rm", "chmod", "ps", "touch", "sed", "dd", "sync", "dmesg", "ping", "mknod", "usleep",
                         "sleep", "login", "true", "false", "logger", "fsck", "modprobe", "lsmod",
                         "rmmod", "depmod", "insmod", "mkfs.ext2", "mv",
                         "mkfs.ext3", "mkfs.ext4", "fdisk", "sfdisk", "parted", "ifconfig", "mkfs.reiserfs", "mkswap",
                         "reboot", "halt", "shutdown", "init", "route", "tell_mother", "date", "tune2fs",
                         ["syslogd", "syslog-ng", "rsyslogd"], "bzip2", "bunzip2", "cut", "tr", "chroot", "whoami", "killall", "head", "tail",
                         "seq", "tcpd", "hoststatus", "ldconfig", "sort", "dirname", "vi", "hostname", "lsof",
                         "chown", "wc", ["portmap", "rpcbind"], "klogd", "arp", "ln", "find", "tftp", "uname", "rsync", "stty", "reset", "id", "lspci"]}

stageloc_dir_dict = {0 : ["sys",
                          "var/empty"],
                     1 : ["root", "tmp", "dev", "etc/pam.d", "proc",
                          "var/run", "var/log", "dev/pts", "sbin", "usr/lib", "usr/share"]}
stageloc_file_dict = {0 : ["inetd", "xinetd", "mkfs.xfs", "rmmod.old", "lsmod.old", "depmod.old", "insmod.old",
                           "modprobe.old", "in.rshd", "in.rlogind", "mount.nfs"],
                      1 : ["awk", "ethtool", "sh", "strace", "bash", "echo", "cp", "mount", "cat", "ls", "mount", "mkdir",
                           "df", "tar", "gzip", "gunzip", "umount", "rmdir", "egrep", "fgrep", "grep", "basename",
                           "rm", "chmod", "ps", "touch", "sed", "dd", "sync", "dmesg", "ping", "mknod", "usleep",
                           "sleep", "login", "true", "false", "logger", "fsck", "modprobe", "lsmod",
                           "rmmod", "depmod", "insmod", "mkfs.ext2", "mv", "pivot_root",
                           "mkfs.ext3", "mkfs.ext4", "fdisk", "sfdisk", "parted", "ifconfig", "mkfs.reiserfs", "mkswap",
                           "reboot", "halt", "shutdown", "init", "route", "tell_mother", "date", "tune2fs",
                           ["syslogd", "syslog-ng", "rsyslogd"], "bzip2", "bunzip2", "cut", "tr", "chroot", "whoami", "killall", "head", "tail",
                           "seq", "tcpd", "hoststatus", "ldconfig", "sort", "dirname", "vi", "hostname", "lsof",
                           "chown", "wc", ["portmap", "rpcbind"], "klogd", "arp", "ln", "find", "tftp", "uname", "rsync", "stty", "reset", "id", "lspci"]}

def make_debian_fixes(in_dict):
    for key, val in in_dict.iteritems():
        # remove /dev/pts from stage-dicts
        if "dev/pts" in val:
            val.remove("dev/pts")
        # vi is maybe a bloated bastard, use vim.tiny or forget it
        if "vi" in val:
            val.remove("vi")
            val.append("vim.tiny")
            
def get_size_str(b_size):
    if b_size > 1024*1024*1024:
        return "%6.2f GB" % (float(b_size) / (1024 * 1024 * 1024))
    elif b_size > 1024*1024:
        return "%6.2f MB" % (float(b_size) / (1024 * 1024))
    elif b_size > 1024:
        return "%6.2f kB" % (float(b_size) / (1024))
    else:
        return "%6d  B" % (b_size)

def norm_path(in_path):
    in_path = os.path.normpath(in_path)
    while in_path.count("//"):
        in_path = in_path.replace("//", "/")
    return in_path

def eliminate_symlinks(root_dir, in_path):
    dir_path = norm_path(os.path.dirname(in_path))
    path_parts = [x for x in dir_path.split("/") if x]
    real_path = ""
    act_path = ""#%s" % (path_parts.pop(0))
    for p_part in path_parts:
        act_path = "%s/%s" % (act_path, p_part)
        if os.path.islink(act_path):
            l_target = os.readlink(act_path)
            if l_target.startswith("/"):
                real_path = "%s%s" % (root_dir, l_target)
            else:
                real_path = "%s/%s" % (real_path, l_target)
        else:
            real_path = "%s/%s" % (real_path, p_part)
    return "%s/%s" % (real_path, os.path.basename(in_path))

def get_module_dependencies(kern_dir, mod_list):
    mod_names = [key.endswith(".ko") and key[:-3] or (key.endswith(".o") and key[:-2] or key) for key in mod_list]
    matches_found = []
    mod_dict = {}
    for act_dir, dir_names, file_names in os.walk(kern_dir):
        for f_name in file_names:
            mod_name = f_name.endswith(".ko") and f_name[:-3] or (f_name.endswith(".o") and f_name[:-2] or f_name)
            match_list = [match_name for match_name in mod_names if fnmatch.fnmatch(mod_name, match_name)]
            if match_list:
                matches_found.extend(match_list)
                mod_dict[mod_name] = "%s/%s" % (act_dir, f_name)
    dep_file = "%s/lib/modules/" % (kern_dir)
    if os.path.isdir(dep_file): 
        dep_file = "%s/%s/modules.dep" % (dep_file, os.listdir(dep_file)[0])
    #print dep_file
    req_dep = [x for x in mod_dict.values() if x]
    if os.path.isfile(dep_file):
        dep_lines = [x.replace("\t", " ").strip() for x in file(dep_file, "r").read().split("\n") if x.strip()]
        dep_lines2 = []
        #print dep_lines
        add_next_line = 0
        for dep_line in dep_lines:
            if dep_line.endswith("\\"):
                anl = 1
                dep_line = dep_line[:-1]
            else:
                anl = 0
            if add_next_line:
                dep_lines2[-1] += " %s" % (dep_line)
            else:
                dep_lines2 += [dep_line]
            add_next_line = anl
        #print dep_lines2
        dep_dict = dict([q for q in [y.replace("//", "/").split(":") if y.startswith(kern_dir) else (os.path.normpath("%s/%s" % (kern_dir, y))).replace("//", "/").split(":") for y in dep_lines2 if y] if len(q) == 2])
        auto_dep = copy.deepcopy(req_dep)
        auto_dep.sort()
        while True:
            next_dep = copy.deepcopy(auto_dep)
            for dep in auto_dep:
                if dep in dep_dict:
                    #print dep, dep_dict[dep]
                    for next_d in dep_dict[dep].strip().split():
                        if next_d.startswith(kern_dir):
                            act_d = next_d
                        else:
                            act_d = os.path.normpath("%s/%s" % (kern_dir, next_d))
                        if act_d not in next_dep and act_d not in req_dep:
                            next_dep += [act_d]
            next_dep.sort()
            if auto_dep == next_dep:
                break
            auto_dep = copy.deepcopy(next_dep)
        auto_dep = [x for x in auto_dep if x not in req_dep]
    else:
        auto_dep = []
    not_found_mods = [key for key in mod_names if not key in matches_found]
    found_mods     = [value for key, value in mod_dict.iteritems() if value]
    fw_lines = []
    for f_module in found_mods:
        fw_stat, fw_out = commands.getstatusoutput("modinfo %s" % (f_module))
        if fw_stat:
            print "Error calling modinfo for %s (%d): %s" % (f_module,
                                                             fw_stat,
                                                             fw_out)
        else:
            loc_fw_lines = [line.split(":")[1].strip() for line in fw_out.split("\n") if line.lower().startswith("firmware:")]
            if loc_fw_lines:
                print "found %s for module %s: %s" % (logging_tools.get_plural("firmware file", len(loc_fw_lines)),
                                                      f_module,
                                                      ", ".join(loc_fw_lines))
                fw_lines.extend(loc_fw_lines)
            else:
                print "no firmware files needed for %s" % (f_module)
                
    return found_mods + auto_dep, not_found_mods, fw_lines

def which(file_name, sp):
    for p_p in sp:
        full = "%s/%s" % (p_p, file_name)
        if os.path.isfile(full):
            break
    else:
        full = None
    if full:
        act = os.path.normpath(full)
        full = [full]
        # follow symlinks
        while os.path.islink(act):
            next = os.path.normpath(os.readlink(act))
            if not next.startswith("/"):
                next = os.path.normpath("%s/%s" % (os.path.dirname(act), next))
            if verbose > 1:
                print "  following link from %s to %s" % (act, next)
            act = next
            full += [act]
    if full:
        return [os.path.normpath(x) for x in full]
    else:
        return full

def get_lib_list(in_f):
    stat, out = commands.getstatusoutput("ldd %s" % (" ".join(in_f)))
    lib_l = []
    out_l = [x.strip() for x in out.split("\n")]
    found_list = []
    for out_line in out_l:
        if out_line.endswith(":") and out_line[:-1] in in_f:
            act_bin = out_line[:-1]
            found_list += [act_bin]
        elif out_line.startswith("ldd:"):
            # ldd-warning or error line
            pass
        else:
            if re.search("not a dynamic", out_line):
                pass
            else:
                if len(out_line.split()) > 2:
                    #print "***", x, len(x.split())
                    lib = out_line.split()[2]
                    if not lib.startswith("(") and not lib in lib_l:
                        lib_l += [lib]
                elif len(out_line.split()) == 2:
                    lib = out_line.split()[0]
                    if not lib in lib_l:
                        lib_l += [lib]
    for lib in lib_l:
        new_lib = None
        if lib.startswith("/lib/tls"):
            new_lib = "/lib/%s" % (lib.split("/")[-1])
        elif lib.startswith("/lib64/tls"):
            new_lib = "/lib64/%s" % (lib.split("/")[-1])
        if new_lib:
            if new_lib not in lib_l:
                lib_l += [new_lib]
    # eliminate symlinks from lib-list
    lib_l2 = []
    for lib in lib_l:
        while os.path.islink(lib):
            next = os.readlink(lib)
            if not next.startswith("/"):
                next = os.path.normpath("%s/%s" % (os.path.dirname(lib), next))
            if verbose > 1:
                print "  following link from %s to %s" % (lib, next)
            lib = next
        lib_l2 += [lib]
    lib_l2 = [norm_path(x) for x in lib_l2]
    lib_l2.sort()
    return lib_l2

def populate_it(stage_num, temp_dir, in_dir_dict, in_file_dict, stage_add_dict, ignore_errors, show_content, add_modules):
    in_file_dict[0].extend(stage_add_dict[0])
    in_file_dict[1].extend(stage_add_dict[1])
    # make some corrections for stupid debian
    if os.path.isfile("/etc/debian_version"):
        make_debian_fixes(in_dir_dict)
        make_debian_fixes(in_file_dict)
    # rewrite dir and file dict
    dir_dict, file_dict = ({}, {})
    for sev, names in in_dir_dict.iteritems():
        for name in names:
            dir_dict[name] = sev
    choice_dict, choice_idx, choices_found, choice_lut = ({}, 0, {}, {})
    for sev, names in in_file_dict.iteritems():
        for name in names:
            if type(name) == type(""):
                file_dict[name] = sev
            else:
                choice_idx += 1
                choice_lut[choice_idx] = name
                for p_name in name:
                    choice_dict[p_name] = choice_idx
                    file_dict[p_name] = sev
    
    root_64bit = get_system_bitcount("/")
    pam_dir = "/lib%s/security" % ({0 : "",
                                    1 : "64"}[root_64bit])
    main_lib_dir = "/lib%s" % ({0 : "",
                                1 : "64"}[root_64bit])
    dir_dict[pam_dir] = 1
    dir_dict["/etc/xinetd.d"] = 0
    sev_dict = {"W" : 0,
                "E" : 0}
    if ignore_errors:
        err_sev = "W"
    else:
        err_sev = "E"
    if verbose:
        print "checking availability of %d directories ..." % (len(dir_dict.keys()))
    # check availability of directories
    for dir, severity in [(os.path.normpath("/%s" % (x)), {0 : "W",
                                                           1 : "E"}[y]) for x, y in dir_dict.iteritems()]:
        if not os.path.isdir(dir):
            print " %s dir '%s' not found" % (severity, dir)
            sev_dict[severity] += 1
    if verbose:
        print "checking availability of %d files ..." % (len(file_dict.keys()))
    new_file_dict = {}
    path = [x for x in os.environ["PATH"].split(":")] + ["/lib/mkinitrd/bin"]
    for f_name, severity in [(x, {0 : "W", 1 : err_sev}[y]) for x, y in file_dict.iteritems()]:
        full_path = which(f_name, path)
        if not full_path:
            if f_name in choice_dict.keys():
                pass
            else:
                print " %s file '%s' not found" % (severity, os.path.basename(f_name))
                sev_dict[severity] += 1
        else:
            for full in full_path:
                if full not in new_file_dict.keys():
                    if f_name != os.path.basename(full) and verbose:
                        print "  adding file '%s' (triggered by '%s')" % (full, f_name)
                    new_file_dict[full] = severity
                    if f_name in choice_dict.keys():
                        choices_found[f_name] = choice_dict[f_name]
    if choice_dict:
        # check choices
        for c_idx, p_cns in choice_lut.iteritems():
            c_found = [p_cn for p_cn in p_cns if p_cn in choices_found.keys()]
            c_found.sort()
            if c_found:
                print "  for choice_idx %d (%s) we found %d of %d: %s" % (c_idx, ", ".join(p_cns), len(c_found), len(p_cns), ", ".join(c_found))
            else:
                print "  for choice_idx %d (%s) we found nothing of %d" % (c_idx, ", ".join(p_cns), len(p_cns))
                sev_dict[{0 : "W", 1 : err_sev}[file_dict[p_cns[0]]]] += 1
    pam_lib_list = []
    if stage_num == 2:
        # init simple pam-stack
        pam_lib_list = ["pam_permit.so"]
    if verbose:
        print "Resolving libraries ..."
    pam_lib_list = [norm_path("/%s/%s" % (pam_dir, x)) for x in pam_lib_list]
    if stage_num == 2 or stage_num == 1:
        for special_lib in os.listdir(main_lib_dir):
            if special_lib.startswith("libnss") or special_lib.startswith("libnsl"):
                if not [x for x in [re.match(".*%s.*" % (x), special_lib) for x in ["win", "ldap", "hesiod", "nis"]] if x]:
                    pam_lib_list += [os.path.normpath("/%s/%s" % (main_lib_dir, special_lib))]
    new_libs = get_lib_list(new_file_dict.keys() + pam_lib_list) + pam_lib_list
    lib_dict = {}
    if verbose:
        print "  ... found %d distinct libraries" % (len(new_libs))
    for new_lib in new_libs:
        lib_dict[new_lib] = "E"
    if verbose:
        print "resolving directories of %d files and libraries ..." % (len(lib_dict.keys()) + len(new_file_dict.keys()))
    dir_list = dir_dict.keys()
    for nd in [os.path.dirname(x) for x in lib_dict.keys() + new_file_dict.keys()]:
        if not nd in dir_list:
            dir_list += [nd]
    if verbose:
        print " ... found %d distinct directories" % (len(dir_list))
    # create missing entries
    for dir_name, dir_mode in [("/dev/pts", 0755)]:
        if not os.path.isdir(dir_name):
            if verbose > 1:
                print "created directory %s (mode %o)" % (dir_name, dir_mode)
            os.mkdir(dir_name)
            os.chmod(dir_name, dir_mode)
    for file_name, file_type, file_mode, major, minor, file_owner, file_group in [("/dev/ram0"   , "b", 0640, 1, 0, 0, 0),
                                                                                  ("/dev/ram1"   , "b", 0640, 1, 1, 0, 0),
                                                                                  ("/dev/ram2"   , "b", 0640, 1, 2, 0, 0),
                                                                                  ("/dev/console", "c", 0600, 5, 1, 0, 0)]:
        if not os.path.exists(file_name):
            if file_type == "b":
                os.mknod(file_name, file_mode | stat.S_IFBLK, os.makedev(major, minor))
            elif file_type == "c":
                os.mknod(file_name, file_mode | stat.S_IFCHR, os.makedev(major, minor))
            os.chown(file_name, file_owner, file_group)
            os.chmod(file_name, file_mode)
            print "created %s device %s (mode %o, major.minor %d.%d, owner.group %d.%d)" % ("block" if file_type == "b" else "char",
                                                                                            file_name,
                                                                                            file_mode,
                                                                                            major,
                                                                                            minor,
                                                                                            file_owner,
                                                                                            file_group)
            # check for block file
            
    for dev_file in ["console", "ram", "ram0", "ram1", "ram2", "null", "zero", "fd0", "xconsole", "ptmx"]:
        new_file_dict[os.path.normpath("/dev/%s" % (dev_file))] = "E"
    for etc_file in ["protocols", "host.conf", "login.defs"]:
        new_file_dict[os.path.normpath("/etc/%s" % (etc_file))] = "W"
    print "Number of dirs / files / libraries: %d / %d / %d" % (len(dir_list),
                                                                len(new_file_dict.keys()),
                                                                len(new_libs))
    print "Starting creating of directory-history under '%s' ..." % (temp_dir)
    for orig_dir in [norm_path("/%s" % (x)) for x in dir_list if x]:
        path_parts = [x for x in orig_dir.split("/") if x]
        path_walk = ["/%s" % (path_parts.pop(0))]
        for pp in path_parts:
            path_walk.append("%s/%s" % (path_walk[-1], pp))
        for orig_path in path_walk:
            target_dir = norm_path("%s/%s" % (temp_dir, orig_path))
            if verbose > 2:
                print "Checking directory %s (after eliminate_symlinks: %s)" % (orig_path, eliminate_symlinks(temp_dir, target_dir))
            if not os.path.isdir(eliminate_symlinks(temp_dir, target_dir)):
                if os.path.islink(orig_path):
                    link_target = os.readlink(orig_path)
                    # create a link
                    if verbose > 1:
                        print "Generating link from %s to %s" % (orig_path, link_target)
                    os.symlink(link_target, target_dir)
                else:
                    if verbose > 1:
                        print "creating directory %s" % (orig_path)
                    os.makedirs(eliminate_symlinks(temp_dir, target_dir))
    os.chmod("%s/tmp" % (temp_dir), 01777)
    file_list = []
    #pprint.pprint(lib_dict)
    strip_files = []
    new_files = new_file_dict.keys()
    new_files.sort()
    act_file, num_files = (0, len(new_files))
    if verbose:
        print "Copying files ..."
    for file_name in new_files:
        act_file += 1
        dest_file = "%s/%s" % (temp_dir, file_name)
        if os.path.islink(file_name):
            os.symlink(os.readlink(file_name), eliminate_symlinks(temp_dir, dest_file))
            if verbose > 1:
                print "%3d linking from %s to %s" % (act_file, os.readlink(file_name), file_name)
        elif os.path.isfile(file_name):
            if verbose > 1:
                f_size = os.stat(file_name)[stat.ST_SIZE]
                f_free = os.statvfs(temp_dir)[statvfs.F_BFREE] * os.statvfs(temp_dir)[statvfs.F_BSIZE]
                print "%3d of %3d, %s, %s free, file %s" % (act_file, num_files, get_size_str(f_size), get_size_str(f_free), file_name)
            shutil.copy2(file_name, eliminate_symlinks(temp_dir, dest_file))
            file_list.append(file_name)
            if os.path.isfile(dest_file) and not os.path.islink(dest_file):
                strip_files += [dest_file]
        elif os.path.exists(file_name):
            file_stat = os.stat(file_name)
            if stat.S_ISCHR(file_stat.st_mode):
                if verbose > 1:
                    print "%3d character device %s" % (act_file, file_name)
                # character device
                os.mknod(dest_file, 0600|stat.S_IFCHR,
                         os.makedev(os.major(file_stat.st_rdev),
                                    os.minor(file_stat.st_rdev)))
            elif stat.S_ISBLK(file_stat.st_mode):
                if verbose > 1:
                    print "%3d block device %s" % (act_file, file_name)
                # block device
                os.mknod(dest_file, 0600|stat.S_IFBLK,
                         os.makedev(os.major(file_stat.st_rdev),
                                    os.minor(file_stat.st_rdev)))
            else:
                if verbose > 1:
                    print "%3d unknown file %s (possibly Unix Domain Socket?)" % (act_file, file_name)
        else:
            if verbose > 1:
                print "%3d *** file not found: %s" % (act_file, file_name)
    # stage1 links for bash->ash, sh->ash
    # stupid code, fixme
#     if stage_num == 1:
#         for name in "sh", "bash":
#             src_name, dst_name = ("bin/ash", "%s/bin/%s" % (temp_dir, name))
#             if os.path.isfile(dst_name):
#                 if os.path.isfile("%s/%s" % (temp_dir, src_name)) or os.path.islink("%s/%s" % (temp_dir, src_name)):
#                     pass
#                 else:
#                     if verbose > 1:
#                         print "Generating link from %s to %s" % (src_name, dst_name)
#                     act_pwd = os.getcwd()
#                     os.chdir(temp_dir)
#                     os.symlink(name, src_name)
#                     os.chdir(act_pwd)
    new_libs = lib_dict.keys()
    new_libs.sort()
    act_lib, num_libs = (0, len(new_libs))
    if verbose:
        print "Copying libraries ..."
    for lib_name in new_libs:
        act_lib += 1
        if os.path.isfile(lib_name):
            dest_file = norm_path("%s/%s" % (temp_dir, lib_name))
            if os.path.islink(lib_name):
                os.symlink(os.readlink(lib_name), eliminate_symlinks(temp_dir, dest_file))
            elif os.path.isfile(lib_name):
                if verbose > 1:
                    l_size = os.stat(lib_name)[stat.ST_SIZE]
                    free_stat = os.statvfs(temp_dir)
                    l_free = free_stat[statvfs.F_BFREE] * free_stat[statvfs.F_BSIZE]
                    print "%3d of %3d, %s, %s free, lib %s" % (act_lib, num_libs, get_size_str(l_size), get_size_str(l_free), lib_name)
                file_list.append(lib_name)
                shutil.copy2(lib_name, eliminate_symlinks(temp_dir, dest_file))
                if os.path.isfile(dest_file) and not os.path.islink(dest_file):
                    strip_files += [dest_file]
        else:
            if verbose > 1:
                print "%3d unknown library %s" % (act_lib, lib_name)
    if strip_files:
        free_stat = os.statvfs(temp_dir)
        free_before = free_stat[statvfs.F_BFREE] * free_stat[statvfs.F_BSIZE]
        strip_stat, strip_out = commands.getstatusoutput("strip -s %s" % (" ".join(strip_files)))
        free_stat = os.statvfs(temp_dir)
        free_after = free_stat[statvfs.F_BFREE] * free_stat[statvfs.F_BSIZE]
        print "size saved by stripping: %s" % (get_size_str(free_after-free_before))
    # default shell
    def_shell = {1 : "/bin/bash",
                 2 : "/bin/bash",
                 3 : "/bin/bash"}[stage_num]
    # pci ids
    pci_f_names = ["/usr/share/pci.ids", "/usr/share/misc/pci.ids", "/usr/share/hwdata/pci.ids", "/NOT_FOUND"]
    for pci_f_name in pci_f_names:
        if os.path.isfile(pci_f_name):
            break
    # generate special files
    sfile_dict = {"/etc/passwd" : ["root::0:0:root:/root:%s" % (def_shell),
                                   "bin::1:1:bin:/bin/:%s" % (def_shell),
                                   "daemon::2:2:daemon:/sbin:%s" % (def_shell)],
                  "/etc/shadow" : ["root:GobeG9LDR.gqU:12198:0:10000::::",
                                   "bin:*:8902:0:10000::::"],
                  "/etc/services" : ["nfs     2049/tcp",
                                     "nfs     2049/udp",
                                     "ntp      123/tcp",
                                     "ntp      123/udp",
                                     "time      37/tcp",
                                     "time      37/udp",
                                     "syslog   514/udp",
                                     "shell    514/tcp",
                                     "login    513/tcp",
                                     "tftp      69/udp"],
                  "/etc/group" : ["root:*:0:root",
                                  "bin:*:1:root,bin,daemon",
                                  "tty:*:5:",
                                  "wheel:x:10:"],
                  "/etc/nsswitch.conf" : ["passwd:     files",
                                          "group:      files",
                                          "hosts:      files",
                                          "networks:   files",
                                          "services:   files",
                                          "protocols:  files",
                                          "rpc:        files",
                                          "ethers:     files",
                                          "netmasks:   files",
                                          "netgroup:   files",
                                          "publickey:  files",
                                          "bootparams: files",
                                          "aliases:    files",
                                          "shadow:     files"],
                  "/etc/pam.d/other" : ["auth     required pam_permit.so",
                                        "account  required pam_permit.so",
                                        "password required pam_permit.so",
                                        "session  required pam_permit.so"],
                  "/etc/inetd.conf" : ["shell stream tcp nowait root /usr/sbin/tcpd in.rshd -L",
                                       "login stream tcp nowait root /usr/sbin/tcpd in.rlogind"],
                  "/etc/hosts.allow" : ["ALL: ALL"],
                  "/etc/ld.so.conf" : ["/usr/x86_64-suse-linux/lib64",
                                       "/usr/x86_64-suse-linux/lib",
                                       "/usr/local/lib",
                                       "/lib64",
                                       "/lib",
                                       "/lib64/tls",
                                       "/lib/tls",
                                       "/usr/lib64",
                                       "/usr/lib",
                                       "/usr/local/lib64"]}
    if os.path.isfile(pci_f_name):
        sfile_dict["/usr/share/pci.ids"] = file(pci_f_name, "r").read().split("\n")
    sfile_dict["/etc/xinetd.conf"] = {1 : ["defaults",
                                           "{",
                                           "    instances       = 60",
                                           "    log_type        = FILE /tmp/syslog_log",
                                           "    cps             = 25 30",
                                           "}",
                                           "service login",
                                           "{",
                                           "    disable          = no",
                                           "    socket_type      = stream",
                                           "    protocol         = tcp",
                                           "    wait             = no",
                                           "    user             = root",
                                           "    log_on_success  += USERID",
                                           "    log_on_failure  += USERID",
                                           "    server           = /usr/sbin/in.rlogind",
                                           "}",
                                           "service shell",
                                           "{",
                                           "    disable          = no",
                                           "    socket_type      = stream",
                                           "    protocol         = tcp",
                                           "    wait             = no",
                                           "    user             = root",
                                           "    log_on_success  += USERID",
                                           "    log_on_failure  += USERID",
                                           "    server           = /usr/sbin/in.rshd",
                                           "}"],
                                       2 : ["defaults",
                                           "{",
                                           "    instances       = 60",
                                           "    log_type        = SYSLOG authpriv",
                                           "    log_on_success  = HOST PID",
                                           "    log_on_failure  = HOST",
                                           "    cps             = 25 30",
                                           "}",
                                           "service login",
                                           "{",
                                           "    disable          = no",
                                           "    socket_type      = stream",
                                           "    protocol         = tcp",
                                           "    wait             = no",
                                           "    user             = root",
                                           "    log_on_success  += USERID",
                                           "    log_on_failure  += USERID",
                                           "    server           = /usr/sbin/in.rlogind",
                                           "}",
                                           "service shell",
                                           "{",
                                           "    disable          = no",
                                           "    socket_type      = stream",
                                           "    protocol         = tcp",
                                           "    wait             = no",
                                           "    user             = root",
                                           "    log_on_success  += USERID",
                                           "    log_on_failure  += USERID",
                                           "    server           = /usr/sbin/in.rshd",
                                           "}"],
                                       3 : []}[stage_num]
    if add_modules:
        sfile_dict["/etc/add_modules"] = ["%s %s" % (mod_name, mod_option) for mod_name, mod_option in add_modules]
    for sfile_name, sfile_content in sfile_dict.iteritems():
        file("%s/%s" % (temp_dir, sfile_name), "w").write("\n".join(sfile_content + [""]))
    # ldconfig call
    ld_stat, out = commands.getstatusoutput("chroot %s /sbin/ldconfig" % (temp_dir))
    if ld_stat:
        print "Error calling /sbin/ldconfig"
        sev_dict["E"] += 1
    else:
        os.unlink("%s/sbin/ldconfig" % (temp_dir))
    # check size (not really needed, therefore commented out)
    #blks_total, blks_used, blks_free = commands.getstatusoutput("df --sync -k %s" % (temp_dir))[1].split("\n")[1].strip().split()[1:4]
    #blks_initrd = commands.getstatusoutput("du -ks %s" % (temp_dir))[1].split("\n")[0].strip().split()[0]
    #print blks_total, blks_used, blks_free, blks_initrd
    if not sev_dict["E"]:
        print "INITDIR %s" % (temp_dir)
    if show_content:
        file_list.sort()
        dir_list.sort()
        print "\n".join(["cd %s" % (x) for x in dir_list])
        print "\n".join(["cf %s" % (x) for x in file_list])
    #shutil.rmtree(temp_dir)
    return 1

def find_free_loopdevice():
    lo_start, lo_end, lo_found = (0, 8, -1)
    for lo in range(lo_start, lo_end):
        lo_dev = "/dev/loop%d" % (lo)
        c_stat, out = commands.getstatusoutput("losetup %s 2>&1 >& /dev/null" % (lo_dev))
        if c_stat == 256:
            lo_found = lo
            break
    return lo_found

def get_system_bitcount(root_dir):
    init_file = "%s/sbin/init" % (root_dir)
    while os.path.islink(init_file):
        print "following link %s ..." % (init_file)
        init_file = os.path.join(os.path.dirname(init_file), os.readlink(init_file))
    if not os.path.isfile(init_file):
        print "'%s' is not the root of a valid system (/sbin/init not found), exiting..." % (root_dir)
        sys.exit(1)
    stat, out = commands.getstatusoutput("file %s" % (init_file))
    if stat:
        print "error determining the filetype of %s (%d): %s" % (init_file, stat, out)
        sys.exit(1)
    elf_str, elf_bit = out.split(":")[1].strip().split()[0:2]
    if elf_str.lower() != "elf":
        print "error binary type '%s' unknown, exiting..." % (elf_str)
        sys.exit(1)
    if elf_bit.lower().startswith("32"):
        sys_64bit = 0
    else:
        sys_64bit = 1
    return sys_64bit
        
def main():
    script = sys.argv[0]
    script_basename = os.path.basename(script)
    # check runmode
    if script_basename.endswith("local.py"):
        main_local()
    else:
        main_normal()

def main_local():
    global verbose
    script = sys.argv[0]
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hs:d:ilv0:1:", ["help", "modules="])
    except getopt.GetoptError, why:
        print "Error parsing commandline : %s" % (str(why))
        sys.exit(1)
    stage_num, verbose, temp_dir, ignore_errors, show_content, add_modules = (1, 0, None, 0, 0, [])
    stage_add_dict = {0 : [],
                      1 : [],
                      2 : []}
    for opt, arg in opts:
        if opt in ["-h", "--help"]:
            print "Usage : %s [OPTIONS] kerneldir" % (os.path.basename(script))
            print "  where OPTIONS is one or more of"
            print " -h, --help      this help"
            print " -s 1|2          set stage to build, defaults to %d" % (stage_num)
            print " -d TEMPDIR      temporary directory for creating of the stage-disc"
            print " -v              be verbose"
            print " -i              ignore errors (missing files)"
            print " -l              show content"
            print " -0 FILES        add to stage_dict (key 0)"
            print " -1 FILES        add to stage_dict (key 1)"
            print " --modules MODS  modules to load at stage1"
            sys.exit(0)
        if opt == "--modules":
            add_modules = [mod_arg.split(":", 1) for mod_arg in arg.split(",")]
        if opt == "-i":
            ignore_errors = 1
        if opt == "-l":
            show_content = 1
        if opt == "-v":
            verbose += 1
        if opt == "-d":
            temp_dir = arg
        if opt == "-0":
            stage_add_dict[0] = arg.split(",")
        if opt == "-1":
            stage_add_dict[1] = arg.split(",")
        if opt == "-s":
            try:
                stage_num = max(1, min(3, int(arg)))
            except:
                print "Cannot parse stage_number '%s', exiting..." % (arg)
                sys.exit(1)
    if not temp_dir:
        print "Error, need temp_dir ..."
        sys.exit(1)
    print "Generating stage%d initrd, verbosity level is %d ..." % (stage_num, verbose)
    if stage_num == 1:
        stage_ok = populate_it(stage_num, temp_dir, stage1_dir_dict, stage1_file_dict, stage_add_dict, ignore_errors, show_content, add_modules)
    elif stage_num == 2:
        stage_ok = populate_it(stage_num, temp_dir, stage2_dir_dict, stage2_file_dict, stage_add_dict, ignore_errors, show_content, add_modules)
    else:
        stage_ok = populate_it(stage_num, temp_dir, stageloc_dir_dict, stageloc_file_dict, stage_add_dict, ignore_errors, show_content, add_modules)
    sys.exit(stage_ok)

def do_show_kernels(dev_assoc):
    try:
        import mysql_tools
    except ImportError:
        print "Need mysql_tools support for this function"
        sys.exit(1)
    dbcon = mysql_tools.dbcon_container()
    dc = dbcon.get_connection()
    kern_dict = {}
    out_list = logging_tools.form_list()
    if dev_assoc:
        out_list.set_format_string(1, "d", "")
        out_list.set_format_string(3, "d", "")
        out_list.set_format_string(5, "d", "")
        out_list.set_header_string(0, ["Kernel", "#d", "drivers", "#new", "Device list (new mode)", "#old", "Device list (old mode)"])
        dc.execute("SELECT d.name AS devname, k.name AS kernname, n.devname AS netname, n.driver FROM device d, kernel k, netdevice n WHERE d.new_kernel=k.kernel_idx AND n.device=d.device_idx AND n.netdevice_idx=d.bootnetdevice ORDER by d.name")
        for db_rec in dc.fetchall():
            kern_dict.setdefault(db_rec["kernname"], {}).setdefault(db_rec["driver"], []).append(("new", db_rec["devname"], db_rec["netname"]))
        dc.execute("SELECT d.name AS devname, k.name AS kernname, n.devname AS netname, n.driver FROM device d, kernel k, netdevice n WHERE d.newkernel=k.name AND d.new_kernel != k.kernel_idx AND n.device=d.device_idx AND n.netdevice_idx=d.bootnetdevice ORDER by d.name")
        for db_rec in dc.fetchall():
            kern_dict.setdefault(db_rec["kernname"], {}).setdefault(db_rec["driver"], []).append(("old", db_rec["devname"], db_rec["netname"]))
        k_names = kern_dict.keys()
        k_names.sort()
        for k_name in k_names:
            k_stuff = kern_dict[k_name]
            drv_dict = {}
            for d_name, mach_list in k_stuff.iteritems():
                new_list = ["%s" % y for x, y, z in mach_list if x == "new"]
                old_list = ["%s" % y for x, y, z in mach_list if x == "old"]
                drv_dict[d_name] = {"new" : new_list,
                                    "old" : old_list}
            drvs = drv_dict.keys()
            drvs.sort()
            drvs_str = ", ".join(drvs)
            if len(drvs) > 1:
                out_list.add_line((k_name,
                                   len(drvs),
                                   drvs_str,
                                   sum([len(drv_dict[x]["new"]) for x in drvs]),
                                   ", ".join(["%s: %s" % (x, logging_tools.compress_list(drv_dict[x]["new"])) for x in drvs if drv_dict[x]["new"]]),
                                   sum([len(drv_dict[x]["old"]) for x in drvs]),
                                   ", ".join(["%s: %s" % (x, logging_tools.compress_list(drv_dict[x]["old"])) for x in drvs if drv_dict[x]["old"]])))
            else:
                out_list.add_line((k_name,
                                   len(drvs),
                                   drvs_str,
                                   sum([len(drv_dict[x]["new"]) for x in drvs]),
                                   ", ".join([logging_tools.compress_list(drv_dict[x]["new"]) for x in drvs if drv_dict[x]["new"]]),
                                   sum([len(drv_dict[x]["old"]) for x in drvs]),
                                   ", ".join([logging_tools.compress_list(drv_dict[x]["old"]) for x in drvs if drv_dict[x]["old"]])))
    else:
        out_list.set_header_string(0, ["Kernel", "initrd_version", "initrd_built", "modules"])
        dc.execute("SELECT k.* FROM kernel k ORDER BY k.name")
        for db_rec in dc.fetchall():
            kern_dict[db_rec["name"]] = db_rec
        k_names = kern_dict.keys()
        k_names.sort()
        for k_name in k_names:
            k_stuff = kern_dict[k_name]
            mod_list = (k_stuff["module_list"] or "").split(",")
            out_list.add_line((k_name,
                               k_stuff["initrd_version"],
                               k_stuff["initrd_built"] and k_stuff["initrd_built"].strftime("%d. %b %Y %H:%M:%S") or "<not set>",
                               k_stuff["module_list"] and "(%d) %s" % (len(mod_list),
                                                                       ", ".join(mod_list)) or "NONE"))
    if len(out_list):
        print out_list
    else:
        print "Empty list"
    dc.release()
    del dbcon
    sys.exit(0)
    
def log_it(what):
    print " - %s" % (what)
    
def main_normal():
    global verbose
    script = sys.argv[0]
    local_script = "%s_local.py" % (script[:-3])
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hs:6m:M:r:vkilDS:T:LqfFt", ["help", "grub", "lilo", "modules=", "set-master-server"])
    except getopt.GetoptError, why:
        print "Error parsing commandline : %s" % (str(why))
        sys.exit(1)
    loc_config = configfile.configuration("local_config", {"VERBOSE"             : configfile.int_c_var(0),
                                                           "IGNORE_ERRORS"       : configfile.bool_c_var(False),
                                                           "KEEP_DIRS"           : configfile.bool_c_var(False),
                                                           "DO_DEPMOD_CALL"      : configfile.bool_c_var(True),
                                                           "SUPRESS_TRANSFER"    : configfile.bool_c_var(True),
                                                           "FORCE_KERNEL_SERVER" : configfile.bool_c_var(False),
                                                           "FORCE_MYSQL_SERVER"  : configfile.bool_c_var(False),
                                                           "QUIET_MODE"          : configfile.bool_c_var(False),
                                                           "SHOW_KERNELS"        : configfile.int_c_var(0),
                                                           "KERNEL_64_BIT"       : configfile.int_c_var(0),
                                                           "INIT_SIZE"           : configfile.int_c_var(0),
                                                           "SHOW_CONTENT"        : configfile.bool_c_var(False),
                                                           "STAGE_SOURCE_DIR"    : configfile.str_c_var("/opt/cluster/lcs"),
                                                           "STAGE_DEST_DIR"      : configfile.str_c_var(""),
                                                           "KERNEL_DIR"          : configfile.str_c_var(""),
                                                           "ROOT_DIR"            : configfile.str_c_var("/"),
                                                           "ADD_GRUB_BINARIES"   : configfile.bool_c_var(False),
                                                           "ADD_LILO_BINARIES"   : configfile.bool_c_var(False),
                                                           "SET_MASTER_SERVER"   : configfile.bool_c_var(False),
                                                           "ADD_MODULES"         : configfile.array_c_var([])})
    mods, mods_file = ([], None)
    stage_add_dict = {1 : {0 : [],
                           1 : []},
                      2 : {0 : [],
                           1 : []},
                      3 : {0 : [],
                           1 : []}}
    for opt, arg in opts:
        if opt in ["-h", "--help"]:
            print "Usage : %s [OPTIONS] kerneldir" % (os.path.basename(script))
            print "  where OPTIONS is one or more of"
            print " -h, --help           this help"
            print " -m MODS              comma-separated list of kernel-modules to include in the first stage"
            print " -M MODFILE           read list of kernel-modules from this file"
            print "                       o if neither -m or -M is used the latest setting from the db is used"
            print "                       o use -m \"\" to clear module list"
            print " -s SIZE              set the size for the initial ramdisk, is automatically extracted from .config"
            print " -6                   force 64bit Kernel"
            print " -r DIR               set rootdir to DIR, default is '%s'" % (loc_config["ROOT_DIR"])
            print " -v                   increase level of verbosity"
            print " -k                   keep stage1/2 directories after generation"
            print " -i                   ignore errors (missing files)"
            print " -l                   list dirs and files"
            print " -D                   skip depmod-call"
            print " -S                   sets source stage_dir (default is %s)" % (loc_config["STAGE_SOURCE_DIR"])
            print " -T                   sets target stage_dir (default is equal to kernel directory)"
            print " -L                   gives an overview of the used kernels and drivers, use twice to show device association"
            print " -q                   quiet (except errors)"
            print " -f                   ignore if no mysql-tools"
            print " -F                   ignore if no kernel-server"
            print " -t                   transfer to mother_servers"
            print " --grub               add grub binaries"
            print " --lilo               add lilo binaries"
            print " --set-master-server  sets master-server of kernel to local server_idx"
            print " --modules ARGS  additional modules to load in stage1, comma-separated: mod1[:mod1_options][,mod2[:mod2_options]]"
            sys.exit(0)
        if opt in ["--lilo", "--grub"]:
            loc_config["ADD_%s_BINARIES" % (opt.upper())] = True
        if opt == "--set-master-server":
            loc_config["SET_MASTER_SERVER"] = True
        if opt == "-t":
            loc_config["SUPRESS_TRANSFER"] = False
        if opt == "-D":
            loc_config["DO_DEPMOD_CALL"] = False
        if opt == "-f":
            loc_config["FORCE_MYSQL_SERVER"] = True
        if opt == "-F":
            loc_config["FORCE_KERNEL_SERVER"] = True
        if opt == "-q":
            loc_config["QUIET_MODE"] = True
        if opt == "-S":
            loc_config["STAGE_SOURCE_DIR"] = arg
        if opt == "-T":
            loc_config["STAGE_DEST_DIR"] = arg
        if opt == "-M":
            mods_file = arg
        if opt == "-i":
            loc_config["IGNORE_ERRORS"] = True
        if opt == "-l":
            loc_config["SHOW_CONTENT"] = True
        if opt == "-k":
            loc_config["KEEP_DIRS"] = True
        if opt == "-v":
            loc_config["VERBOSE"] += 1
        if opt == "-m":
            mods = [x.strip() for x in arg.split(",")]
        if opt == "-6":
            loc_config["KERNEL_64_BIT"] = 1
        if opt == "-L":
            loc_config["SHOW_KERNELS"] += 1
        if opt == "--modules":
            add_mods = []
            for line in arg.split(","):
                if line.count(":"):
                    mod_name, mod_option = line.split(":", 1)
                else:
                    mod_name, mod_option = (line, "")
                if mod_name.endswith(".o"):
                    mod_name = mod_name[:-2]
                elif mod_name.endswith(".ko"):
                    mod_name = mod_name[:-3]
                add_mods.append((mod_name, mod_option))
            loc_config["ADD_MODULES"] = add_mods
        if opt == "-s":
            try:
                loc_config["INIT_SIZE"] = int(arg)
            except:
                print "Cannot parse initsize '%s', exiting..." % (arg)
                sys.exit(1)
        if opt == "-r":
            if os.path.isdir(arg):
                loc_config["ROOT_DIR"] = arg
            else:
                print "'%s' is not a directory, exiting..."
                sys.exit(1)
    if loc_config["SHOW_KERNELS"]:
        do_show_kernels(loc_config["SHOW_KERNELS"]==2)
    if not args:
        print "No kernel-dir given, exiting"
        sys.exit(1)
    loc_config["KERNEL_DIR"] = args[0]
    kernel_name = os.path.split(os.path.normpath(loc_config["KERNEL_DIR"]))[1]
    if not kernel_name:
        print "Cannot extract kernel_name from %s" % (loc_config["KERNEL_DIR"])
        sys.exit(1)
    if not os.path.isfile("%s/bzImage" % (loc_config["KERNEL_DIR"])):
        print "Found no kernel (bzImage) under %s, exiting" % (loc_config["KERNEL_DIR"])
        sys.exit(1)
    long_host_name = socket.getfqdn(socket.gethostname())
    short_host_name = long_host_name.split(".")[0]
    if mysql_tools:
        dbcon = mysql_tools.dbcon_container()
        dc = dbcon.get_connection()
    else:
        dbcon = None
    # kernel_server idx
    kernel_server_idx = 0
    if dbcon:
        # check for kernel_server
        import config_tools
        ks_check = config_tools.server_check(dc=dc, server_type="kernel_server")
        if not ks_check.num_servers:
            if loc_config["FORCE_KERNEL_SERVER"]:
                print "Host '%s' is not a kernel_server but continuing due to force flag, just building initrd" % (short_host_name)
                ms_dict = {}
            else:
                print "Host '%s' is not a kernel_server, exiting ..." % (short_host_name)
                sys.exit(1)
        else:
            kernel_server_idx = ks_check.server_device_idx
            dc.execute("SELECT d.name, d.device_idx FROM device d INNER JOIN device_config dc INNER JOIN new_config c INNER JOIN device_group dg LEFT JOIN device d2 ON d2.device_idx = dg.device WHERE d.device_group=dg.device_group_idx AND dc.new_config=c.new_config_idx AND (dc.device=d.device_idx OR dc.device=d2.device_idx) AND c.name='mother_server'")
            mother_servers = [x["name"] for x in dc.fetchall()]
            # get local netdevices
            dc.execute("SELECT n.netdevice_idx FROM netdevice n WHERE n.device=%d" % (ks_check.server_device_idx))
            all_ids = [x["netdevice_idx"] for x in dc.fetchall()]
            dc.execute("SELECT d.name, i.ip, h.value, i.alias FROM netip i, hopcount h, netdevice n, device d WHERE i.netdevice=n.netdevice_idx AND n.netdevice_idx=h.d_netdevice AND n.device=d.device_idx AND (%s) AND (%s) ORDER BY h.value, d.name" % (" OR ".join(["d.name='%s'" % (x) for x in mother_servers]),
                                                                                                                                                                                                                                                                 " OR ".join(["h.s_netdevice=%d" % (x) for x in all_ids])))
            ms_dict = {}
            for db_rec in dc.fetchall():
                if not ms_dict.has_key(db_rec["name"]):
                    ms_dict[db_rec["name"]] = (db_rec["ip"], db_rec["alias"])
            print "Host '%s' is a kernel_server (device_idx %d), found %s: %s" % (short_host_name,
                                                                                  ks_check.server_device_idx,
                                                                                  logging_tools.get_plural("mother_server", len(mother_servers)),
                                                                                  ", ".join(["%s [%s]" % (k, ms_dict.get(k, ("not reachable", "not reachable"))[0]) for k in mother_servers]))
    else:
        if loc_config["FORCE_MYSQL_SERVER"]:
            print "Cannot connect to SQL database, just building initrd"
            ms_dict = {}
        else:
            print "Cannot connect to SQL database, exiting ..."
            sys.exit(1)
    if len(args) != 1:
        print "Need exactly one directory as argument (given: %d)" % (len(args))
        sys.exit(1)
    if not os.path.isdir(loc_config["KERNEL_DIR"]):
        print "Need a directory as argument ('%s' is not a directory)" % (loc_config["KERNEL_DIR"])
        sys.exit(1)
    elif not os.path.isabs(loc_config["KERNEL_DIR"]):
        print "Need an absoult path as argument ('%s' is a relative path)" % (loc_config["KERNEL_DIR"])
        sys.exit(1)
    kernel_idx, kernel_stuff = (0, None)
    if dbcon:
        target_path = os.path.normpath(loc_config["KERNEL_DIR"])
        dc.execute("SELECT * FROM kernel k WHERE k.name=%s", kernel_name)
        if dc.rowcount:
            kernel_stuff = dc.fetchone()
            kernel_idx = kernel_stuff["kernel_idx"]
            print "Found kernel at path '%s' (name %s) in database (kernel_idx is %d)" % (target_path, kernel_name, kernel_idx)
            if kernel_stuff["xen_host_kernel"]:
                print " - kernel for Xen-hosts"
            if kernel_stuff["xen_guest_kernel"]:
                print " - kernel for Xen-guests"
            if kernel_server_idx:
                if kernel_server_idx != kernel_stuff["master_server"]:
                    if loc_config["SET_MASTER_SERVER"]:
                        print "setting master_server of kernel to local kernel_server_idx"
                        dc.execute("UPDATE kernel SET master_server=%s WHERE kernel_idx=%s", (kernel_server_idx,
                                                                                                    kernel_idx))
                    else:
                        print "server_device_idx for kernel_server differs from master_server from DB, exiting (override with --set-master-server)"
                        sys.exit(0)
        else:
            print "*** Cannot find a kernel at path '%s' (name %s) in database" % (target_path, kernel_name)
    # build list of modules
    act_mods = []
    take_modules_from_db = (mods == [] and not mods_file)
    if not take_modules_from_db:
        if mods_file:
            if os.path.isfile(mods_file):
                mods.extend([y for y in [x.strip() for x in file(mods_file, "r").read().split("\n")] if y])
            else:
                print "cannot read mods_file '%s', exiting..." % (mods_file)
                sys.exit(1)
        for mod in mods:
            if mod.endswith(".o"):
                mod = mod[:-2]
            elif mod.endswith(".ko"):
                mod = mod[:-3]
            if mod and mod not in MOD_REFUSE_LIST:
                act_mods.append(mod)
    if loc_config["ADD_MODULES"]:
        act_mods.extend([mod_name for mod_name, mod_option in loc_config["ADD_MODULES"]])
    act_mods.sort()
    # check type of build-dir linux (32/64 bit)
    build_arch_64bit = get_system_bitcount(loc_config["ROOT_DIR"])
    local_arch_64bit = get_system_bitcount("/")
    if build_arch_64bit > local_arch_64bit:
        print "don't known how to build 64bit initrds on a 32bit System, exiting..."
        sys.exit(1)
    # try to get kernel config
    wrong_config_name = "%s/config" % (loc_config["KERNEL_DIR"])
    if os.path.isfile(wrong_config_name):
        print
        print " *** Found %s, please move to .config" % (wrong_config_name)
        print
    if os.path.isfile("%s/.config" % (loc_config["KERNEL_DIR"])):
        conf_lines = [y for y in [x.strip() for x in file("%s/.config" % (loc_config["KERNEL_DIR"]), "r").read().split("\n") if x.strip()] if not y.strip().startswith("#")]
        conf_dict = dict([x.split("=", 1) for x in conf_lines])
    else:
        print "Warning, no kernel_config %s/.config found" % (loc_config["KERNEL_DIR"])
        conf_dict = {}
    # set initsize if not already set
    if not loc_config["INIT_SIZE"]:
        loc_config["INIT_SIZE"] = int(conf_dict.get("CONFIG_BLK_DEV_RAM_SIZE", "16384"))
    # check for 64bit Kernel
    if not loc_config["KERNEL_64_BIT"]:
        loc_config["KERNEL_64_BIT"] = conf_dict.has_key("CONFIG_X86_64")
    if not local_arch_64bit and loc_config["KERNEL_64_BIT"]:
        print "/ is 32bit and Kernel 64 bit, exiting"
        sys.exit(1)
    if build_arch_64bit and not loc_config["KERNEL_64_BIT"]:
        print "build_architecture under %s is 64bit and Kernel 32 bit, exiting" % (loc_config["ROOT_DIR"])
        sys.exit(1)
    # check for kernel version
    if os.path.isdir("%s/lib/modules" % (loc_config["KERNEL_DIR"])):
        kverdirs = os.listdir("%s/lib/modules" % (loc_config["KERNEL_DIR"]))
        if len(kverdirs) > 1:
            print "More than one KernelVersionDirectory found: %s" % (", ".join(kverdirs))
            sys.exit(1)
        elif len(kverdirs) == 0:
            print "No KernelVersionDirectory found below '%s/lib/modules'" % (loc_config["KERNEL_DIR"])
            sys.exit(1)
        kverdir = kverdirs[0]
        if loc_config["DO_DEPMOD_CALL"]:
            depmod_call = "depmod -aeb %s %s" % (loc_config["KERNEL_DIR"], kverdir)
            if not loc_config["QUIET_MODE"]:
                print "Doing depmod_call '%s' ..." % (depmod_call)
            c_stat, out = commands.getstatusoutput(depmod_call)
            if c_stat:
                print " - some error occured (%d): %s" % (c_stat, out)
                sys.exit(1)
    else:
        kverdir = os.path.basename(os.path.normpath(loc_config["KERNEL_DIR"]))
        print "No lib/modules directory found under '%s', setting kernel_version to %s" % (loc_config["KERNEL_DIR"], kverdir)
    bit_dict = {0 : "32",
                1 : "64"}
    # check availability of stages
    for stage in ["1", "2", "3", "local"]:
        fname = "/%s/stage%s" % (loc_config["STAGE_SOURCE_DIR"], stage)
        if not os.path.isfile(fname):
            print "Cannot find stage %s file %s in stage_dir %s" % (stage, fname, loc_config["STAGE_SOURCE_DIR"])
            sys.exit(1)
    free_lo_dev = find_free_loopdevice()
    if free_lo_dev == -1:
        print "Cannot find free loopdevice, exiting..."
        sys.exit(1)
    loop_dev = "/dev/loop%d" % (free_lo_dev)
    # read uuid
    import uuid_tools
    my_uuid = uuid_tools.get_uuid()
    if not loc_config["QUIET_MODE"]:
        print "cluster_device_uuid is %s" % (my_uuid.get_urn())
        print "Kernel directory is '%s', initsize is %d kBytes" % (loc_config["KERNEL_DIR"], loc_config["INIT_SIZE"])
        print "  kernel_version is %s, %s-bit kernel" % (kverdir, bit_dict[loc_config["KERNEL_64_BIT"]])
        print "  build_dir is '%s', %s-bit linux" % (loc_config["ROOT_DIR"], bit_dict[build_arch_64bit])
        print "  local_system is a %s-bit linux" % (bit_dict[local_arch_64bit])
        print "  stage source directory is %s" % (loc_config["STAGE_SOURCE_DIR"])
        print "  stage target directory is %s" % (loc_config["STAGE_DEST_DIR"] and loc_config["STAGE_DEST_DIR"] or loc_config["KERNEL_DIR"])
        print "  will create three flavours:"
        print "    - use mkfs.cramfs to build stage1 initrd"
        print "    - create a cpio-archive for stage1 initrd"
        print "    - use loopdevice %s to build stage1 initrd" % (loop_dev)
    stage_add_dict[1][1].append("run-init")
    stage_add_dict[3][1].append("run-init")
    # add boot-load specific files
    if loc_config["ADD_GRUB_BINARIES"]:
        if not loc_config["QUIET_MODE"]:
            print "  adding grub-binaries"
        stage_add_dict[2][1].extend(["grub", "grub-install"])
    if loc_config["ADD_LILO_BINARIES"]:
        if not loc_config["QUIET_MODE"]:
            print "  adding lilo-binaries"
        stage_add_dict[2][1].extend(["lilo"])
    # get kernel-module dependencies
    if kernel_idx:
        if take_modules_from_db:
            if kernel_stuff["target_module_list"]:
                act_mods = [x.strip() for x in kernel_stuff["target_module_list"].split(",") if x.strip() not in MOD_REFUSE_LIST]
            else:
                act_mods = []
            print "Using module_list from database: %s, %s" % (logging_tools.get_plural("module", len(act_mods)),
                                                               ", ".join(act_mods))
        else:
            print "Saving module_list to database: %s, %s" % (logging_tools.get_plural("module", len(act_mods)),
                                                              ", ".join(act_mods))
            dc.execute("UPDATE kernel SET target_module_list='%s' WHERE kernel_idx=%d" % (",".join(act_mods),
                                                                                                kernel_idx))
    if act_mods:
        all_mods, del_mods, fw_files = get_module_dependencies(loc_config["KERNEL_DIR"], act_mods)
        all_mods = [x for x in all_mods if x not in MOD_REFUSE_LIST]
        act_mods.sort()
        all_mods.sort()
        del_mods.sort()
        if not loc_config["QUIET_MODE"]:
            print "  %s given: %s; %s not found, %s have to be installed" % (logging_tools.get_plural("kernel module", len(act_mods)),
                                                                             ", ".join(act_mods),
                                                                             logging_tools.get_plural("module", len(del_mods)),
                                                                             logging_tools.get_plural("module", len(all_mods)))
        if loc_config["VERBOSE"] and not loc_config["QUIET_MODE"]:
            for mod in del_mods:
                print " - (not found) : %s" % (mod)
            for mod in all_mods:
                print " + (found) : %s" % (mod)
    else:
        all_mods, fw_files = ([], [])
        if not loc_config["QUIET_MODE"]:
            print "  no kernel-modules given"
    if kernel_idx:
        base_mods = [".".join(os.path.basename(x).split(".")[0:-1]) for x in all_mods]
        base_mods.sort()
        if kernel_stuff["module_list"]:
            last_base_mods = [x.strip() for x in kernel_stuff["module_list"].split(",")]
        else:
            last_base_mods = []
        if last_base_mods == base_mods:
            print "Updating database (modules are the same)...",
        else:
            print "Updating database (modules changed from %s to %s)..." % (last_base_mods and ", ".join(last_base_mods) or "<None>",
                                                                            base_mods and ", ".join(base_mods) or "<None>"),
        dc.execute("UPDATE kernel SET module_list='%s', initrd_built=NOW() WHERE kernel_idx=%d" % (",".join(base_mods),
                                                                                                         kernel_idx))
        print "ok"
    if loc_config["ROOT_DIR"] != "/":
        loc_src, loc_dst = (script, os.path.normpath("%s/%s" % (loc_config["ROOT_DIR"], os.path.basename(local_script))))
        if not loc_config["QUIET_MODE"]:
            print "  copying %s to %s" % (loc_src, loc_dst)
        shutil.copy(loc_src, loc_dst)
    # setting up loopdevice for stage1
    stage1_lo_file     = os.path.normpath("/%s/initrd_lo" % (loc_config["STAGE_DEST_DIR"] and loc_config["STAGE_DEST_DIR"] or loc_config["KERNEL_DIR"]))
    stage1_cramfs_file = os.path.normpath("/%s/initrd_cramfs" % (loc_config["STAGE_DEST_DIR"] and loc_config["STAGE_DEST_DIR"] or loc_config["KERNEL_DIR"]))
    stage1_cpio_file   = os.path.normpath("/%s/initrd_cpio" % (loc_config["STAGE_DEST_DIR"] and loc_config["STAGE_DEST_DIR"] or loc_config["KERNEL_DIR"]))
    stage2_file        = os.path.normpath("/%s/initrd_stage2.gz" % (loc_config["STAGE_DEST_DIR"] and loc_config["STAGE_DEST_DIR"] or loc_config["KERNEL_DIR"]))
    stageloc_file      = os.path.normpath("/%s/initrd_local" % (loc_config["STAGE_DEST_DIR"] and loc_config["STAGE_DEST_DIR"] or loc_config["KERNEL_DIR"]))
    for del_file in [stage1_lo_file, stage1_cramfs_file, stage1_cpio_file, stage2_file, stageloc_file]:
        if os.path.isfile(del_file):
            os.unlink(del_file)
        if os.path.isfile("%s.gz" % (del_file)):
            os.unlink("%s.gz" % (del_file))
    stage1_dir   = tempfile.mkdtemp(".stage1_dir"  , "/%s/tmp/.rdc_" % (loc_config["ROOT_DIR"]))
    stage2_dir   = tempfile.mkdtemp(".stage2_dir"  , "/%s/tmp/.rdc_" % (loc_config["ROOT_DIR"]))
    stageloc_dir = tempfile.mkdtemp(".stageloc_dir", "/%s/tmp/.rdc_" % (loc_config["ROOT_DIR"]))
    stat_out = []
    stat_out += [("dd"       , commands.getstatusoutput("dd if=/dev/zero of=%s bs=1024 count=%d" % (stage1_lo_file, loc_config["INIT_SIZE"])))]
    stat_out += [("losetup"  , commands.getstatusoutput("losetup %s %s" % (loop_dev, stage1_lo_file)))]
    stat_out += [("mkfs.ext2", commands.getstatusoutput("mkfs.ext2 -F -v -m 0 -b 1024 %s %d" % (stage1_lo_file, loc_config["INIT_SIZE"])))]
    stat_out += [("mount"    , commands.getstatusoutput("mount -o loop -t ext2 %s %s" % (stage1_lo_file, stage1_dir)))]
    if len([err_name for name, (err_name, y) in stat_out if err_name]):
        print "Something went wrong during setup of stage1:"
        for name, (err_name, y) in stat_out:
            print "%s (%d) : \n%s" % (name, err_name, "\n".join([" - %s" % (z) for z in y.split("\n")]))
        sys.exit(-1)
    stage_targ_dirs = [stage1_dir, stage2_dir, stageloc_dir]
    stage_dirs, del_dirs = ([], [])
    for stage in range(1, 4):
        if not loc_config["QUIET_MODE"]:
            print "Generating stage%s initrd ..." % ({1 : "1",
                                                      2 : "2",
                                                      3 : "local"}[stage])
        act_stage_dir = stage_targ_dirs[stage - 1]
        loc_root_dir = "/".join([""] + act_stage_dir.split("/")[-2:])
        loc_args = " ".join(["-v"] * loc_config["VERBOSE"])
        if loc_config["IGNORE_ERRORS"]:
            loc_args += " -i "
        if loc_config["SHOW_CONTENT"]:
            loc_args += " -l "
        if loc_config["ROOT_DIR"] != "/":
            gen_com = "chroot %s /%s %s -d %s -s %d" % (loc_config["ROOT_DIR"], os.path.basename(local_script), loc_args, loc_root_dir, stage)
        else:
            gen_com = "%s %s -s %d -d %s " % (local_script, loc_args, stage, loc_root_dir)
        gen_com = "%s %s" % (gen_com, " ".join(["-%d %s" % (im_key, ",".join(stage_add_dict[stage][im_key])) for im_key in [0, 1] if stage_add_dict[stage][im_key]]))
        if loc_config["ADD_MODULES"] and stage in [1, 3]:
            gen_com = "%s --modules %s" % (gen_com, ",".join(["%s:%s" % (mod_name, mod_option) for mod_name, mod_option in loc_config["ADD_MODULES"]]))
        if not loc_config["QUIET_MODE"]:
            print gen_com
        c_stat, out = commands.getstatusoutput(gen_com)
        if loc_config["VERBOSE"] and not loc_config["QUIET_MODE"]:
            print "\n".join([" - %s" % (x) for x in out.split("\n")])
        act_stage_dir = [y.split()[1].strip() for y in [x.strip() for x in out.strip().split("\n")] if y.startswith("INITDIR")]
        if act_stage_dir:
            stage_dirs += ["%s/%s" % (loc_config["ROOT_DIR"], act_stage_dir[0])]
        else:
            print "Error generating stage%d dir" % (stage)
            print "\n".join(["  - %s" % (x) for x in out.split("\n") if x.strip().startswith("E ")])
        del_dirs += [os.path.normpath("%s/%s" % (loc_config["ROOT_DIR"], loc_root_dir))]
    stage_dirs_ok = len(stage_dirs) == len(stage_targ_dirs)
    if stage_dirs_ok:
        for linuxrc_name in LINUXRC_NAMES:
            # stage1 stuff
            stage1_dest = "/%s/%s" % (stage_dirs[0], linuxrc_name)
            shutil.copy2("/%s/stage1" % (loc_config["STAGE_SOURCE_DIR"]), stage1_dest)
            os.chmod(stage1_dest, 0744)
            os.chown(stage1_dest, 0, 0)
            # stagelocal stuff
            stageloc_dest = "/%s/%s" % (stage_dirs[2], linuxrc_name)
            shutil.copy2("/%s/stagelocal" % (loc_config["STAGE_SOURCE_DIR"]), stageloc_dest)
            os.chmod(stageloc_dest, 0744)
            os.chown(stageloc_dest, 0, 0)
        # add kernel-modules to stage1 / stageloc
        for kmod_targ_dir in [stage_dirs[0], stage_dirs[2]]:
            kmod_dir = "/%s/lib/modules/%s/kernel/drivers" % (kmod_targ_dir, kverdir)
            os.makedirs(kmod_dir)
            if all_mods:
                for mod in [x for x in all_mods if x]:
                    shutil.copy2(mod, kmod_dir)
        # add firmware-files to stage1 / tageloc
        for kmod_targ_dir in [stage_dirs[0], stage_dirs[2]]:
            fw_dir = "/%s/lib/firmware/%s" % (kmod_targ_dir, kverdir)
            fw_dir_2 = "/%s/lib/firmware" % (kmod_targ_dir)
            os.makedirs(fw_dir)
            if fw_files:
                for fw_file in fw_files:
                    fw_src_file = "/%s/lib/firmware/%s/%s" % (loc_config["KERNEL_DIR"], kverdir, fw_file) 
                    if os.path.isfile(fw_src_file):
                        loc_fw_dir = "/%s/%s" % (fw_dir, os.path.dirname(fw_file))
                        loc_fw_dir_2 = "/%s/%s" % (fw_dir_2, os.path.dirname(fw_file))
                        if not os.path.isdir(loc_fw_dir):
                            os.makedirs(loc_fw_dir)
                        if not os.path.isdir(loc_fw_dir_2):
                            os.makedirs(loc_fw_dir_2)
                        shutil.copy2(fw_src_file, loc_fw_dir)
                        shutil.copy2(fw_src_file, loc_fw_dir_2)
                    else:
                        print "*** cannot read firmware-file %s" % (fw_src_file)
    # umount stage1_dir
    act_dir = os.getcwd()
    stat_out = []
    stat_out += [("mkfs.cramfs", commands.getstatusoutput("mkfs.cramfs -n initrd_stage1 %s %s" % (stage1_dir, stage1_cramfs_file)))]
    stat_out += [("cpio"       , commands.getstatusoutput("cd %s ; find %s -printf \"%%P\\n\" | cpio -c -o > %s ; cd %s" % (stage1_dir, stage1_dir, stage1_cpio_file, act_dir)))]
    stat_out += [("umount"     , commands.getstatusoutput("umount %s" % (stage1_dir))),
                 ("losetup"    , commands.getstatusoutput("losetup -d %s" % (loop_dev)))]
    # stageloc setup
    stat_out += [("cpio"       , commands.getstatusoutput("cd %s ; find %s -printf \"%%P\\n\" | cpio -c -o > %s ; cd %s" % (stageloc_dir, stageloc_dir, stageloc_file, act_dir)))]
    if [x for name, (x, y) in stat_out if x]:
        print "Something went wrong during finish of stage1:"
        for name, (err_name, y) in stat_out:
            print "%s (%d) : \n%s" % (name, err_name, "\n".join([" - %s" % (z) for z in y.split("\n")]))
    if stage_dirs_ok:
        for s1_type, s1_file in [("lo"    , stage1_lo_file),
                                 ("cramfs", stage1_cramfs_file),
                                 ("cpio"  , stage1_cpio_file)]:
            print "Compressing stage1 (%7s) ... " % (s1_type),
            s_time = time.time()
            o_s1_size = os.stat(s1_file)[stat.ST_SIZE]
            # zip stage1
            gzip.GzipFile("%s.gz" % (s1_file), "wb", 1).write(file(s1_file, "rb").read())
            os.unlink(s1_file)
            s1_file = "%s.gz" % (s1_file)
            n_s1_size = os.stat(s1_file)[stat.ST_SIZE]
            e_time = time.time()
            print "from %s to %s in %s" % (get_size_str(o_s1_size),
                                           get_size_str(n_s1_size),
                                           logging_tools.get_diff_time_str(e_time - s_time))
        print "Compressing stage2 ............. ",
        s_time = time.time()
        o_s2_size = 0
        for dir_name, dir_list, file_list in os.walk(stage_targ_dirs[1]):
            for file_name in ["%s/%s" % (dir_name, x) for x in file_list]:
                if os.path.isfile(file_name):
                    o_s2_size += os.stat(file_name)[stat.ST_SIZE]
        # create stage2
        commands.getstatusoutput("tar cpsjf %s -C %s ." % (stage2_file, stage_targ_dirs[1]))
        n_s2_size = os.stat(stage2_file)[stat.ST_SIZE]
        e_time = time.time()
        print "from %s to %s in %s" % (get_size_str(o_s2_size),
                                       get_size_str(n_s2_size),
                                       logging_tools.get_diff_time_str(e_time - s_time))
        print "Compressing stageloc ........... ",
        s_time = time.time()
        o_sl_size = os.stat(stageloc_file)[stat.ST_SIZE]
        # zip stage1
        gzip.GzipFile("%s.gz" % (stageloc_file), "wb", 1).write(file(stageloc_file, "rb").read())
        os.unlink(stageloc_file)
        stageloc_file = "%s.gz" % (stageloc_file)
        n_sl_size = os.stat(stageloc_file)[stat.ST_SIZE]
        e_time = time.time()
        print "from %s to %s in %s" % (get_size_str(o_sl_size),
                                       get_size_str(n_sl_size),
                                       logging_tools.get_diff_time_str(e_time - s_time))
    if kernel_idx:
        dc.execute("UPDATE kernel SET stage1_lo_present=%s, stage1_cpio_present=%s, stage1_cramfs_present=%s, stage2_present=%s WHERE kernel_idx=%s", (1,
                                                                                                                                                       1,
                                                                                                                                                       1,
                                                                                                                                                       1,
                                                                                                                                                       kernel_idx))
    if dbcon:
        dc.release()
    # cleaning up
    if loc_config["ROOT_DIR"] != "/":
        os.unlink(loc_dst)
    if not stage_dirs_ok:
        print "Stage directories not OK, exiting..."
        sys.exit(0)
    if not loc_config["KEEP_DIRS"]:
        for del_dir in del_dirs:
            if not loc_config["QUIET_MODE"]:
                print "removing directory %s ..." % (del_dir)
            shutil.rmtree(del_dir)
    if not loc_config["SUPRESS_TRANSFER"]:
        uuid_connected = [my_uuid]
        print "command_stack is not longer available, please copy from hand"
##         send_list = command_stack.send_list([command_stack.send_data(stage1_file),
##                                              command_stack.send_data(stage2_file),
##                                              command_stack.send_str("quit")], log_it, CS_BLOCK_SIZE)
##         for ms_name, (ms_ip, ms_alias) in ms_dict.iteritems():
##             # get uuid for all mother-server
##             errnum, data = msock.single_tcp_connection((ms_ip, 8004, server_command.server_command(command="get_uuid")), None, timeout=10)
##             if errnum:
##                 print "error receiving uuid from %s (IP %s) (%d): %s" % (ms_name, ms_ip, errnum, data)
##             else:
##                 try:
##                     s_reply = server_command.server_reply(data)
##                 except:
##                     print "error build server_reply from data from %s (IP %s) (%d): %s" % (ms_name, ms_ip, errnum, data[0:15])
##                 else:
##                     server_uuid = uuid_tools.UUID(s_reply.get_result().split()[1])
##                     if server_uuid in uuid_connected:
##                         print "uuid %s for %s (IP %s) already in connected list, skipping..." % (server_uuid, ms_name, ms_ip)
##                     else:
##                         uuid_connected.append(server_uuid)
##                         send_list.init_instance()
##                         if ms_ip == "127.0.0.1" or ms_name == short_host_name:
##                             print "Motherserver %s (IP %s, alias %s) seems to be local, skipping ..." % (ms_name, ms_ip, ms_alias or "<EMPTY>")
##                         else:
##                             print "Transfering stages to motherserver %s (IP %s, alias %s) ..." % (ms_name, ms_ip, ms_alias or "<EMPTY>")
##                             tcp_stat, tcp_out = msock.single_tcp_connection((ms_ip, 8001, (send_list, send_list)), None, 10)
##                             if tcp_stat:
##                                 print " - gave error (%d): %s" % (tcp_stat, tcp_out)
    return

if __name__ == "__main__":
    main()
