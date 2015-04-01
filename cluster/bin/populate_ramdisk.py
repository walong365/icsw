#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001-2010,2012,2014 Andreas Lang-Nevyjel
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

import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

from django.db.models import Q
from initat.cluster.backbone.models import kernel, initrd_build
import argparse
import commands
import config_tools
import datetime
import fnmatch
import net_tools
import gzip
import logging_tools
import module_dependency_tools
import process_tools
import re
import server_command
import shutil
import stat
import statvfs
import tempfile
import time
import uuid_tools

MOD_REFUSE_LIST = [
    "3w-9xxx", "3w-xxxx", "af_packet", "ata_piix",
    "autofs", "eata", "gdth",
    "jbd", "libata", "mptbase",
    "mptctl", "mptscsih", "reiserfs",
    "sata_promise", "sata_via",
    "scsi_mod", "sg", "sym53c8xx", "unix",
]

LINUXRC_NAMES = ["init", "linuxrc"]

stage1_dir_dict = {
    0 : [
        "var/empty",
        "sys",
        "dev/pts"
        ],
    1 : [
        "root", "tmp", "dev", "etc/pam.d", "proc",
        "var/run", "var/log", "sbin", "usr/lib", "usr/share"]}

stage1_file_dict = {
    0 : [
        "inetd", "xinetd", "in.rshd", "tcpd", "in.rlogind", "whoami", "ntpdate", "sntp", "ps", "rmmod", "rmmod.old", "lsmod.old", "depmod.old",
        "insmod.old", "modprobe.old", "route", "free", "arp", "login", "mount.nfs", "lsof", "xz",
        ],
    1 : [
        "readlink", "ethtool", "cp", "mount", "cat", "ls", "mount", "mkdir", "find", "head",
        "tar", "gunzip", "umount", "rmdir", "egrep", "fgrep", "grep", "rm", "chmod", "basename",
        "sed", "dmesg", "ping", "mknod", "true", "false", "logger", "modprobe", "bash", "load_firmware.sh",
        "lsmod", "depmod", "insmod", "mkfs.ext2", "date",
        "ifconfig", "pivot_root", "switch_root", "init", "tell_mother_zmq", "bzip2", "bunzip2", "cut", "tr", "chroot",
        "killall", "seq", "hoststatus_zmq", "chown", "ldconfig", "which",
        "df", "wc", "tftp", "mkfifo", "sleep", "reboot", "stty", "reset", "du", "tail", "lspci", "tee",
    ]
}

stage2_dir_dict = {
    0 : [
        "sys",
        "var/empty",
        ],
    1 : [
        "root", "tmp", "dev", "etc/pam.d", "proc",
        "var/run", "var/log", "dev/pts", "sbin", "usr/lib", "usr/share",
    ]
}

stage2_file_dict = {
    0 : [
        "inetd", "xinetd", "mkfs.xfs", "mkfs.btrfs", "rmmod.old", "lsmod.old", "depmod.old", "insmod.old",
        "modprobe.old", "in.rshd", "in.rlogind", "mount.nfs", "xz", "mkfs.reiserfs",
        ],
    1 : [
        "ethtool", "sh", "strace", "bash", "echo", "cp", "mount", "cat", "ls", "mount", "mkdir",
        "df", "tar", "gzip", "gunzip", "umount", "rmdir", "egrep", "fgrep", "grep", "basename",
        "rm", "chmod", "ps", "touch", "sed", "dd", "sync", "dmesg", "ping", "mknod", "usleep",
        "sleep", "login", "true", "false", "logger", "fsck", "modprobe", "lsmod",
        "rmmod", "depmod", "insmod", "mkfs.ext2", "mv", "udevadm", "which",
        "mkfs.ext3", "mkfs.ext4", "fdisk", "sfdisk", "parted", "ifconfig", "mkswap",
        "reboot", "halt", "shutdown", "init", "route", "tell_mother_zmq", "date", "tune2fs",
        ["syslogd", "syslog-ng", "rsyslogd"], "bzip2", "bunzip2", "cut", "tr", "chroot", "whoami", "killall", "head", "tail",
        "seq", "tcpd", "hoststatus_zmq", "ldconfig", "sort", "dirname", "vi", "hostname", "lsof",
        "chown", "wc", ["portmap", "rpcbind"], "klogd", "arp", "ln", "find", "tftp", "uname", "rsync", "stty", "reset", "id", "lspci",
    ]
}

stageloc_dir_dict = {
    0 : [
        "sys",
        "var/empty",
        ],
    1 : [
        "root", "tmp", "dev", "etc/pam.d", "proc",
        "var/run", "var/log", "dev/pts", "sbin", "usr/lib", "usr/share",
    ]
}

stageloc_file_dict = {
    0 : [
        "inetd", "xinetd", "mkfs.xfs", "rmmod.old", "lsmod.old", "depmod.old", "insmod.old",
        "modprobe.old", "in.rshd", "in.rlogind", "mount.nfs", "mkfs.reiserfs",
        ],
    1 : [
        "awk", "ethtool", "sh", "strace", "bash", "echo", "cp", "mount", "cat", "ls", "mount", "mkdir",
        "df", "tar", "gzip", "gunzip", "umount", "rmdir", "egrep", "fgrep", "grep", "basename",
        "rm", "chmod", "ps", "touch", "sed", "dd", "sync", "dmesg", "ping", "mknod", "usleep",
        "sleep", "login", "true", "false", "logger", "fsck", "modprobe", "lsmod",
        "rmmod", "depmod", "insmod", "mkfs.ext2", "mv", "pivot_root",
        "mkfs.ext3", "mkfs.ext4", "fdisk", "sfdisk", "parted", "ifconfig", "mkswap",
        "reboot", "halt", "shutdown", "init", "route", "tell_mother_zmq", "date", "tune2fs",
        ["syslogd", "syslog-ng", "rsyslogd"], "bzip2", "bunzip2", "cut", "tr", "chroot", "whoami", "killall", "head", "tail",
        "seq", "tcpd", "hoststatus_zmq", "ldconfig", "sort", "dirname", "vi", "hostname", "lsof",
        "chown", "wc", ["portmap", "rpcbind"], "klogd", "arp", "ln", "find", "tftp", "uname", "rsync", "stty", "reset", "id", "lspci",
    ]
}

def make_debian_fixes(in_dict):
    for _key, val in in_dict.iteritems():
        # remove /dev/pts from stage-dicts
        if "dev/pts" in val:
            val.remove("dev/pts")
        # vi is maybe a bloated bastard, use vim.tiny or forget it
        if "vi" in val:
            val.remove("vi")
            val.append("vim.tiny")

def get_size_str(b_size):
    if b_size > 1024 * 1024 * 1024:
        return "%6.2f GB" % (float(b_size) / (1024 * 1024 * 1024))
    elif b_size > 1024 * 1024:
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
    # do NOT use os.path.join here
    dir_path = norm_path(os.path.dirname(in_path))
    path_parts = [x for x in dir_path.split("/") if x]
    real_path = ""
    act_path = "" # %s" % (path_parts.pop(0))
    for p_part in path_parts:
        act_path = "{}/{}".format(act_path, p_part)
        if os.path.islink(act_path):
            l_target = os.readlink(act_path)
            if l_target.startswith("/"):
                real_path = "{}{}".format(root_dir, l_target)
            else:
                real_path = "{}/{}".format(real_path, l_target)
        else:
            real_path = "{}/{}".format(real_path, p_part)
    return "{}/{}".format(real_path, os.path.basename(in_path))

def _shorten_module_name(mod_name):
    return mod_name.endswith(".ko") and mod_name[:-3] or (mod_name.endswith(".o") and mod_name[:-2] or mod_name)

def get_module_dependencies(kern_dir, mod_list):
    # pure module names
    mod_names = [_shorten_module_name(key) for key in mod_list]
    # list of modules with postfix
    matches_found = set()
    # lut: short_name -> full name (with postfix but without path)
    mod_dict = {}
    # lut: module with with postfix -> full path
    file_dict = {}
    for act_dir, _dir_names, file_names in os.walk(kern_dir):
        for f_name in file_names:
            mod_name = f_name[:-3] if f_name.endswith(".ko") else (f_name[:-2] if f_name.endswith(".o") else f_name)
            # print f_name, mod_name
            file_dict[f_name] = os.path.join(act_dir, f_name)
            match_list = [match_name for match_name in mod_names if fnmatch.fnmatch(mod_name, match_name)]
            if match_list:
                matches_found.add(f_name)
    dep_file = "{}/lib/modules/".format(kern_dir)
    if os.path.isdir(dep_file):
        dep_file = "{}/{}/modules.dep".format(dep_file, os.listdir(dep_file)[0])
    if os.path.isfile(dep_file):
        dep_lines = [line.replace("\t", " ").strip() for line in file(dep_file, "r").read().split("\n") if line.strip()]
        dep_lines2 = []
        add_next_line = False
        for dep_line in dep_lines:
            if dep_line.endswith("\\"):
                anl = True
                dep_line = dep_line[:-1]
            else:
                anl = False
            if add_next_line:
                dep_lines2[-1] += " {}".format(dep_line)
            else:
                dep_lines2 += [dep_line]
            add_next_line = anl
        # simplify
        dep_lines2 = [line.replace("//", "/").replace("//", "/").split(":") for line in dep_lines2]
        dep_dict = dict([(key, value.strip().split()) for key, value in [entry for entry in dep_lines2 if len(entry) == 2]])
        _kernel_mod_dict = dict([(os.path.basename(key), key) for key in dep_dict.iterkeys()])
        kernel_lut_dict = dict([(key, os.path.basename(key)) for key in dep_dict.iterkeys()])
        dep_dict = dict([(os.path.basename(key), set([kernel_lut_dict[m_path] for m_path in value])) for key, value in dep_dict.iteritems()])
        m_iter = 0
        while True:
            cur_size = len(matches_found)
            m_iter += 1
            if verbose:
                print " - {:2d} {}".format(m_iter, ", ".join(sorted(list(matches_found))))
            for cur_match in list(matches_found):
                matches_found |= set(dep_dict[cur_match])
            if len(matches_found) == cur_size:
                break
    # update mod_dict
    for entry in matches_found:
        mod_dict[_shorten_module_name(entry)] = entry
    not_found_mods = [key for key in mod_names if key not in mod_dict]
    found_mods = [value for key, value in mod_dict.iteritems()]
    fw_lines = []
    for f_module in found_mods:
        fw_stat, fw_out = commands.getstatusoutput("modinfo {}".format(file_dict[f_module]))
        if fw_stat:
            print "Error calling modinfo for {} ({:d}): {}".format(
                f_module,
                fw_stat,
                fw_out)
        else:
            loc_fw_lines = [line.split(":")[1].strip() for line in fw_out.split("\n") if line.lower().startswith("firmware:")]
            if loc_fw_lines:
                print "found {} for module {}: {}".format(
                    logging_tools.get_plural("firmware file", len(loc_fw_lines)),
                    f_module,
                    ", ".join(loc_fw_lines))
                fw_lines.extend(loc_fw_lines)
            else:
                print "no firmware files needed for {}".format(f_module)
    return [file_dict[entry] for entry in matches_found], not_found_mods, fw_lines

def which(file_name, sp):
    for p_p in sp:
        full = "{}/{}".format(p_p, file_name)
        if os.path.isfile(full):
            break
    else:
        full = None
    if full:
        act = os.path.normpath(full)
        full = [full]
        # follow symlinks
        while os.path.islink(act):
            _next = os.path.normpath(os.readlink(act))
            if not _next.startswith("/"):
                _next = os.path.normpath("{}/{}".format(os.path.dirname(act), _next))
            if verbose > 1:
                print "  following link from {} to {}".format(act, _next)
            act = _next
            full += [act]
    if full:
        return [os.path.normpath(entry) for entry in full]
    else:
        return full

def get_lib_list(in_f):
    _stat, out = commands.getstatusoutput("ldd {}".format(" ".join(in_f)))
    lib_l = []
    out_l = [line.strip() for line in out.split("\n")]
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
                    # print "***", x, len(x.split())
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
            new_lib = "/lib/{}".format(lib.split("/")[-1])
        elif lib.startswith("/lib64/tls"):
            new_lib = "/lib64/{}".format(lib.split("/")[-1])
        elif lib.startswith("/opt/cluster/lib64/"):
            new_lib = "/lib64/{}".format(lib.split("/")[-1])
        if new_lib:
            if new_lib not in lib_l:
                lib_l += [new_lib]
    # eliminate symlinks from lib-list
    lib_l2 = []
    for lib in lib_l:
        while os.path.islink(lib):
            next_link = os.readlink(lib)
            if not next_link.startswith("/"):
                next_link = os.path.normpath("{}/{}".format(os.path.dirname(lib), next_link))
            if verbose > 1:
                print "  following link from {} to {}".format(lib, next_link)
            lib = next_link
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
    pam_dir = "/lib{}/security".format(
        {
            0 : "",
            1 : "64"
        }[root_64bit])
    rsyslog_dir = "/lib{}/rsyslog".format(
        {
            0 : "",
            1 : "64"
        }[root_64bit])
    rsyslog_dirs = ["/usr{}".format(rsyslog_dir), rsyslog_dir]
    main_lib_dir = "/lib{}".format(
        {
            0 : "",
            1 : "64"
        }[root_64bit])
    dir_dict[pam_dir] = 1
    for rsyslog_dir in rsyslog_dirs:
        dir_dict[rsyslog_dir] = 0
    dir_dict["/etc/xinetd.d"] = 0
    sev_dict = {"W" : 0,
                "E" : 0}
    if ignore_errors:
        err_sev = "W"
    else:
        err_sev = "E"
    if verbose:
        print "checking availability of {:d} directories ...".format(len(dir_dict.keys()))
    # check availability of directories
    for _dir, severity in [(os.path.normpath("/{}".format(x)), {
        0 : "W",
        1 : "E"}[y]) for x, y in dir_dict.iteritems()]:
        if not os.path.isdir(_dir):
            print " {} dir '{}' not found".format(severity, _dir)
            sev_dict[severity] += 1
    if verbose:
        print "checking availability of {:d} files ...".format(len(file_dict.keys()))
    new_file_dict = {}
    path = [x for x in os.environ["PATH"].split(":")] + ["/lib/mkinitrd/bin"]
    for f_name, severity in [(x, {0 : "W", 1 : err_sev}[y]) for x, y in file_dict.iteritems()]:
        full_path = which(f_name, path)
        if not full_path:
            if f_name in choice_dict.keys():
                pass
            else:
                print " {} file '{}' not found".format(severity, os.path.basename(f_name))
                sev_dict[severity] += 1
        else:
            for full in full_path:
                if full not in new_file_dict.keys():
                    if f_name != os.path.basename(full) and verbose:
                        print "  adding file '{}' (triggered by '{}')".format(full, f_name)
                    new_file_dict[full] = severity
                    if f_name in choice_dict.keys():
                        choices_found[f_name] = choice_dict[f_name]
    if choice_dict:
        # check choices
        for c_idx, p_cns in choice_lut.iteritems():
            c_found = [p_cn for p_cn in p_cns if p_cn in choices_found.keys()]
            c_found.sort()
            if c_found:
                print "  for choice_idx {:d} ({}) we found {:d} of {:d}: {}".format(c_idx, ", ".join(p_cns), len(c_found), len(p_cns), ", ".join(c_found))
            else:
                # better error handling, fixme
                print "  for choice_idx {:d} ({}) we found nothing of {:d}".format(c_idx, ", ".join(p_cns), len(p_cns))
                sev_dict[{0 : "W", 1 : err_sev}[file_dict[p_cns[0]]]] += 1
    pam_lib_list = []
    if stage_num == 2:
        # init simple pam-stack
        pam_lib_list = ["pam_permit.so"]
    if verbose:
        print "Resolving libraries ..."
    pam_lib_list = [norm_path("/{}/{}".format(pam_dir, _lib)) for _lib in pam_lib_list]
    for rsyslog_dir in rsyslog_dirs:
        if os.path.isdir(rsyslog_dir):
            pam_lib_list.extend([norm_path("{}/{}".format(rsyslog_dir, entry)) for entry in os.listdir(rsyslog_dir)])
    if stage_num in [1, 2]:
        for special_lib in os.listdir(main_lib_dir):
            if special_lib.startswith("libnss") or special_lib.startswith("libnsl"):
                if not [x for x in [re.match(".*{}.*".format(x), special_lib) for x in ["win", "ldap", "hesiod", "nis"]] if x]:
                    pam_lib_list += [os.path.normpath("/{}/{}".format(main_lib_dir, special_lib))]
    new_libs = get_lib_list(new_file_dict.keys() + pam_lib_list) + pam_lib_list
    lib_dict = {}
    if verbose:
        print "  ... found {:d} distinct libraries".format(len(new_libs))
    for new_lib in new_libs:
        lib_dict[new_lib] = "E"
    if verbose:
        print "resolving directories of {:d} files and libraries ...".format(len(lib_dict.keys()) + len(new_file_dict.keys()))
    dir_list = dir_dict.keys()
    for nd in [os.path.dirname(x) for x in lib_dict.keys() + new_file_dict.keys()]:
        if not nd in dir_list:
            dir_list += [nd]
    if verbose:
        print " ... found {:d} distinct directories".format(len(dir_list))
    # create missing entries
    for dir_name, dir_mode in [("/dev/pts", 0755)]:
        if not os.path.isdir(dir_name):
            if verbose > 1:
                print "created directory {} (mode {:o})".format(dir_name, dir_mode)
            os.mkdir(dir_name)
            os.chmod(dir_name, dir_mode)
    for file_name, file_type, file_mode, major, minor, file_owner, file_group in [
        ("/dev/ram0"   , "b", 0640, 1, 0, 0, 0),
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
            print "created {} device {} (mode {:o}, major.minor {:d}.{:d}, owner.group {:d}.{:d})".format(
                "block" if file_type == "b" else "char",
                file_name,
                file_mode,
                major,
                minor,
                file_owner,
                file_group)
            # check for block file

    for dev_file in ["console", "ram", "ram0", "ram1", "ram2", "null", "zero", "fd0", "xconsole", "ptmx"]:
        new_file_dict[os.path.normpath("/dev/{}".format(dev_file))] = "E"
    for etc_file in ["protocols", "host.conf", "login.defs"]:
        new_file_dict[os.path.normpath("/etc/{}".format(etc_file))] = "W"
    print "Number of dirs / files / libraries: {:d} / {:d} / {:d}".format(
        len(dir_list),
        len(new_file_dict.keys()),
        len(new_libs))
    print "Starting creating of directory-history under '{}' ...".format(temp_dir)
    for orig_dir in [norm_path("/{}".format(x)) for x in dir_list if x]:
        path_parts = [x for x in orig_dir.split("/") if x]
        path_walk = ["{}".format(path_parts.pop(0))]
        for pp in path_parts:
            path_walk.append("{}/{}".format(path_walk[-1], pp))
        # sys.exit(0)
        for orig_path in path_walk:
            target_dir = norm_path("{}/{}".format(temp_dir, orig_path))
            if verbose > 2:
                print "Checking directory {} (after eliminate_symlinks: {})".format(orig_path, eliminate_symlinks(temp_dir, target_dir))
            if not os.path.isdir(eliminate_symlinks(temp_dir, target_dir)):
                if os.path.islink(orig_path):
                    link_target = os.readlink(orig_path)
                    # create a link
                    if verbose > 1:
                        print "Generating link from {} to {}".format(orig_path, link_target)
                    os.symlink(link_target, target_dir)
                else:
                    if verbose > 1:
                        print "creating directory {}".format(orig_path)
                    os.makedirs(eliminate_symlinks(temp_dir, target_dir))
    os.chmod("{}/tmp".format(temp_dir), 01777)
    file_list = []
    # pprint.pprint(lib_dict)
    strip_files = []
    new_files = new_file_dict.keys()
    new_files.sort()
    act_file, num_files = (0, len(new_files))
    if verbose:
        print "Copying files ..."
    for file_name in new_files:
        act_file += 1
        dest_file = "{}/{}".format(temp_dir, file_name)
        if os.path.islink(file_name):
            os.symlink(os.readlink(file_name), eliminate_symlinks(temp_dir, dest_file))
            if verbose > 1:
                print "{:4d} linking from {} to {}".format(act_file, os.readlink(file_name), file_name)
        elif os.path.isfile(file_name):
            if verbose > 1:
                f_size = os.stat(file_name)[stat.ST_SIZE]
                f_free = os.statvfs(temp_dir)[statvfs.F_BFREE] * os.statvfs(temp_dir)[statvfs.F_BSIZE]
                print "{:4d} of {:4d}, {}, {} free, file {}".format(act_file, num_files, get_size_str(f_size), get_size_str(f_free), file_name)
            shutil.copy2(file_name, eliminate_symlinks(temp_dir, dest_file))
            file_list.append(file_name)
            if os.path.isfile(dest_file) and not os.path.islink(dest_file):
                strip_files += [dest_file]
        elif os.path.exists(file_name):
            file_stat = os.stat(file_name)
            if stat.S_ISCHR(file_stat.st_mode):
                if verbose > 1:
                    print "{:4d} character device {}".format(act_file, file_name)
                # character device
                os.mknod(dest_file, 0600 | stat.S_IFCHR,
                         os.makedev(os.major(file_stat.st_rdev),
                                    os.minor(file_stat.st_rdev)))
            elif stat.S_ISBLK(file_stat.st_mode):
                if verbose > 1:
                    print "{:4d} block device {}".format(act_file, file_name)
                # block device
                os.mknod(dest_file, 0600 | stat.S_IFBLK,
                         os.makedev(os.major(file_stat.st_rdev),
                                    os.minor(file_stat.st_rdev)))
            else:
                if verbose > 1:
                    print "{:4d} unknown file {} (possibly Unix Domain Socket?)".format(act_file, file_name)
        else:
            if verbose > 1:
                print "{:4d} *** file not found: {}".format(act_file, file_name)
    # stage1 links for bash->ash, sh->ash
    new_libs = lib_dict.keys()
    new_libs.sort()
    num_libs = len(new_libs)
    if verbose:
        print "Copying libraries ..."
    for act_lib, lib_name in enumerate(new_libs, start=1):
        if os.path.isfile(lib_name):
            if lib_name.startswith("/opt/cluster"):
                target_lib_name = "/{}".format(lib_name.split("/", 3)[3])
            else:
                target_lib_name = lib_name
            dest_file = norm_path("{}/{}".format(temp_dir, target_lib_name))
            if os.path.islink(lib_name):
                os.symlink(os.readlink(lib_name), eliminate_symlinks(temp_dir, dest_file))
            elif os.path.isfile(lib_name):
                if verbose > 1:
                    l_size = os.stat(lib_name)[stat.ST_SIZE]
                    free_stat = os.statvfs(temp_dir)
                    l_free = free_stat[statvfs.F_BFREE] * free_stat[statvfs.F_BSIZE]
                    print "{:4d} of {:4d}, {}, {} free, lib {}{}".format(
                        act_lib,
                        num_libs,
                        get_size_str(l_size),
                        get_size_str(l_free),
                        lib_name,
                        " (map to {})".format(target_lib_name) if target_lib_name != lib_name else "")
                file_list.append(lib_name)
                shutil.copy2(lib_name, eliminate_symlinks(temp_dir, dest_file))
                if os.path.isfile(dest_file) and not os.path.islink(dest_file):
                    strip_files += [dest_file]
        else:
            if verbose > 1:
                print "{:4d} unknown library {}".format(act_lib, lib_name)
    if strip_files:
        free_stat = os.statvfs(temp_dir)
        free_before = free_stat[statvfs.F_BFREE] * free_stat[statvfs.F_BSIZE]
        _strip_stat, _strip_out = commands.getstatusoutput("strip -s {}".format(" ".join(strip_files)))
        free_stat = os.statvfs(temp_dir)
        free_after = free_stat[statvfs.F_BFREE] * free_stat[statvfs.F_BSIZE]
        print "size saved by stripping: {}".format(get_size_str(free_after - free_before))
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
    sfile_dict = {
        "/etc/passwd" : ["root::0:0:root:/root:{}".format(def_shell),
                         "bin::1:1:bin:/bin/:{}".format(def_shell),
                         "daemon::2:2:daemon:/sbin:{}".format(def_shell)],
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
                             "/usr/local/lib64"],
        "/etc/netconfig" : ['udp        tpi_clts      v     inet     udp     -       -',
                            'tcp        tpi_cots_ord  v     inet     tcp     -       -',
                            'udp6       tpi_clts      v     inet6    udp     -       -',
                            'tcp6       tpi_cots_ord  v     inet6    tcp     -       -',
                            'rawip      tpi_raw       -     inet      -      -       -',
                            'local      tpi_cots_ord  -     loopback  -      -       -',
                            'unix       tpi_cots_ord  -     loopback  -      -       -']}
    if os.path.isfile(pci_f_name):
        sfile_dict["/usr/share/pci.ids"] = file(pci_f_name, "r").read().split("\n")
    sfile_dict["/etc/xinetd.conf"] = {
        1 : [
            "defaults",
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
        sfile_dict["/etc/add_modules"] = ["{} {}".format(mod_name, mod_option) for mod_name, mod_option in add_modules]
    for sfile_name, sfile_content in sfile_dict.iteritems():
        file("{}/{}".format(temp_dir, sfile_name), "w").write("\n".join(sfile_content + [""]))
    # ldconfig call
    ld_stat, _out = commands.getstatusoutput("chroot {} /sbin/ldconfig".format(temp_dir))
    if ld_stat:
        print "Error calling /sbin/ldconfig"
        sev_dict["E"] += 1
    else:
        os.unlink("{}/sbin/ldconfig".format(temp_dir))
    # check size (not really needed, therefore commented out)
    # blks_total, blks_used, blks_free = commands.getstatusoutput("df --sync -k %s" % (temp_dir))[1].split("\n")[1].strip().split()[1:4]
    # blks_initrd = commands.getstatusoutput("du -ks %s" % (temp_dir))[1].split("\n")[0].strip().split()[0]
    # print blks_total, blks_used, blks_free, blks_initrd
    if not sev_dict["E"]:
        print "INITDIR {}".format(temp_dir)
    if show_content:
        file_list.sort()
        dir_list.sort()
        print "\n".join(["cd {}".format(x) for x in dir_list])
        print "\n".join(["cf {}".format(x) for x in file_list])
    # shutil.rmtree(temp_dir)
    return 1

def find_free_loopdevice():
    _c_stat, c_out = commands.getstatusoutput("losetup -a")
    used_loops = [line.split(":", 1)[0] for line in c_out.split("\n")]
    lo_found = -1
    for cur_lo in xrange(0, 8):
        if "/dev/loop{:d}".format(cur_lo) not in used_loops:
            lo_found = cur_lo
            break
    return lo_found

def get_system_bitcount(root_dir):
    init_file = norm_path("{}/sbin/init".format(root_dir))
    while os.path.islink(init_file):
        print "following link {} ...".format(init_file)
        init_file = os.path.join(os.path.dirname(init_file), os.readlink(init_file))
    if not os.path.isfile(init_file):
        print "'{}' is not the root of a valid system (/sbin/init not found), exiting...".format(root_dir)
        sys.exit(1)
    stat, out = commands.getstatusoutput("file {}".format(init_file))
    if stat:
        print "error determining the filetype of {} ({:d}): {}".format(init_file, stat, out)
        sys.exit(1)
    elf_str, elf_bit = out.split(":")[1].strip().split()[0:2]
    if elf_str.lower() != "elf":
        print "error binary type '{}' unknown, exiting...".format(elf_str)
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
    elif script_basename == "copy_local_kernel.sh":
        main_copy()
    else:
        main_normal()

class base_arg_mixin(object):
    def add_base_args(self):
        self.add_argument("-m", "--modules", dest="modules", default="", type=str, help="comma-separated list of kernel-modules to include in the first stage [%(default)s]")
    def base_parse(self, cur_args):
        cur_args.modules = list(set([entry.strip() for entry in cur_args.modules.strip().split(",") if entry.strip()]))

class copy_arg_parser(argparse.ArgumentParser, base_arg_mixin):
    def __init__(self):
        im_dir = os.getenv("IMAGE_ROOT", "/")
        kern_dir = os.path.join(im_dir, "lib", "modules")
        argparse.ArgumentParser.__init__(self, epilog="searching kernels in '{}' (root directory can be changed by setting IMAGE_ROOT)".format(kern_dir))
        local_kernels = [entry for entry in os.listdir(kern_dir) if os.path.isdir(os.path.join(kern_dir, entry, "kernel"))]
        if not local_kernels:
            print "No kernels found beneath {}, exiting ...".format(kern_dir)
            sys.exit(1)
        self.add_argument("--target-dir", type=str, default="/opt/cluster/system/tftpboot/kernels", help="set target directory [%(default)s]")
        self.add_argument("kernel", nargs="?", choices=local_kernels, type=str, default=local_kernels[0], help="kernel to copy [%(default)s]")
        self.add_argument("--clean", default=False, action="store_true", help="clear target directory if it already exists [%(default)s]")
        self.add_argument("--init", default=False, action="store_true", help="init system directories if missing [%(default)s]")
        self.add_argument("--rescan", default=False, action="store_true", help="rescan kernels after successfull copy [%(default)s]")
        self.add_argument("--build", default=False, action="store_true", help="build initial ramdisk, implies rescan [%(default)s]")
        self.add_base_args()
    def parse(self):
        cur_args = self.parse_args()
        if cur_args.build:
            cur_args.rescan = True
        cur_args.image_root = os.getenv("IMAGE_ROOT", "/")
        self.base_parse(cur_args)
        return cur_args

class local_arg_parser(argparse.ArgumentParser, base_arg_mixin):
    def __init__(self):
        argparse.ArgumentParser.__init__(self)
        self.add_argument("-s", dest="stage_num", type=int, default=1, choices=[1, 2, 3], help="set stage to build [%(default)d]")
        self.add_argument("-l", dest="show_content", default=False, action="store_true", help="list dirs and files [%(default)s]")
        self.add_argument("-i", dest="ignore_errors", default=False, action="store_true", help="ignore errors (missing files), [%(default)s]")
        self.add_argument("-0", dest="stage_0_files", default="", type=str, help="add to stage_dict (key 0) [%(default)s]")
        self.add_argument("-1", dest="stage_1_files", default="", type=str, help="add to stage_dict (key 1) [%(default)s]")
        self.add_argument("-d", dest="temp_dir", default="", type=str, help="temporary directory for creating of the stage-disc [%(default)s]")
        self.add_argument("-v", "--verbose", dest="verbose", default=0, action="count", help="increase verbosity [%(default)d]")
        self.add_base_args()
    def parse(self):
        cur_args = self.parse_args()
        cur_args.stage_0_files = [entry.strip() for entry in cur_args.stage_0_files.strip().split(",") if entry.strip()]
        cur_args.stage_1_files = [entry.strip() for entry in cur_args.stage_1_files.strip().split(",") if entry.strip()]
        self.base_parse(cur_args)
        return cur_args

def main_copy():
    global verbose
    copy_args = copy_arg_parser().parse()
    lib_dir = os.path.join(copy_args.image_root, "lib", "modules", copy_args.kernel)
    firm_dir = os.path.join(copy_args.image_root, "lib", "firmware")
    # firm_dir_local = os.path.join(firm_dir, copy_args.kernel)
    target_dir = os.path.join(copy_args.target_dir, copy_args.kernel)
    do_it = True
    if not os.path.isdir(copy_args.target_dir):
        if copy_args.init:
            os.makedirs(copy_args.target_dir)
        else:
            print "system target directory {} does not exist".format(
                copy_args.target_dir,
                )
            do_it = False
    if not os.path.isdir(lib_dir):
        print "source directory {} missing".format(lib_dir)
        do_it = False
    if os.path.isdir(target_dir):
        if copy_args.clean:
            shutil.rmtree(target_dir)
        else:
            print "target directory {} already exists".format(target_dir)
            do_it = False
    system_map_file = os.path.join(copy_args.image_root, "boot", "System.map-{}".format(copy_args.kernel))
    vmlinuz_file = os.path.join(copy_args.image_root, "boot", "vmlinuz-{}".format(copy_args.kernel))
    config_file = os.path.join(copy_args.image_root, "boot", "config-{}".format(copy_args.kernel))
    if not os.path.isfile(system_map_file):
        print "system.map file {} does not exist".format(system_map_file)
        do_it = False
    if not os.path.isfile(vmlinuz_file):
        print "vmlinuz file {} does not exist".format(vmlinuz_file)
        do_it = False
    # print "*", copy_args
    if not do_it:
        sys.exit(2)
    else:
        print "copying kernel from source directory {} to target directory {}".format(
            lib_dir,
            target_dir,
        )
        print "  system.map : {}".format(system_map_file)
        print "  vmlinuz    : {}".format(vmlinuz_file)
        print "  config     : {}".format(config_file)
        # previous source / build link
        build_lt = get_link_target(lib_dir, "build")
        source_lt = get_link_target(lib_dir, "source")
        os.makedirs(target_dir)
        print "\nCopying system.map and vmlinuz"
        shutil.copy(system_map_file, os.path.join(target_dir, "System.map"))
        shutil.copy(vmlinuz_file, os.path.join(target_dir, "bzImage"))
        if os.path.isfile(config_file):
            print "\ncopying config file"
            shutil.copy(config_file, os.path.join(target_dir, ".config"))
        # modules
        t_lib_dir = os.path.join(target_dir, "lib", "modules", copy_args.kernel)
        print "\nCopying modules {} -> {}".format(lib_dir, t_lib_dir)
        shutil.copytree(lib_dir, t_lib_dir)
        # firmware
        t_firm_dir = os.path.join(target_dir, "lib", "firmware")
        print "\nCopying firmware {} -> {}".format(firm_dir, t_firm_dir)
        shutil.copytree(firm_dir, t_firm_dir)
        # local firmware
        # print "\nCopying local firmware {} -> {}".format(firm_dir_local, t_firm_dir)
        # shutil.copytree(firm_dir_local, t_firm_dir)
        print "\nGenerating dummy initrd_lo.gz"
        file(os.path.join(target_dir, "initrd_lo.gz"), "w").close()
        # print build_lt, source_lt
        if build_lt:
            os.symlink(build_lt, os.path.join(lib_dir, "build"))
        if source_lt:
            os.symlink(source_lt, os.path.join(lib_dir, "source"))
        if copy_args.rescan:
            rescan_kernels()
            if copy_args.build:
                sys.argv = ["populate_ramdisk.py", "-i", "--set-master-server", target_dir]
                if copy_args.modules:
                    sys.argv.extend(["-m", ",".join(copy_args.modules)])
                main_normal()
                rescan_kernels()

def rescan_kernels():
    srv_com = server_command.srv_command(command="rescan_kernels")
    _conn_str = "tcp://localhost:8000"
    # connection object
    _conn = net_tools.zmq_connection(
        "copy_local_kernel",
        timeout=30,
        )
    result = _conn.add_connection(_conn_str, srv_com)
    if result is None:
        res_str, res_state = (
            "got no result (conn_str is {})".format(_conn_str),
            logging_tools.LOG_LEVEL_CRITICAL,
        )
    else:
        res_str, res_state = result.get_log_tuple()
    print "[{}] {}".format(logging_tools.map_log_level_to_log_status(res_state), res_str)

def get_link_target(lib_dir, link_name):
    link_file = os.path.join(lib_dir, link_name)
    if os.path.islink(link_file):
        link_target = os.readlink(link_file)
        os.unlink(link_file)
    else:
        link_target = ""
    return link_target

def main_local():
    global verbose
    local_args = local_arg_parser().parse()
    _script = sys.argv[0]
    stage_add_dict = {0 : local_args.stage_0_files,
                      1 : local_args.stage_1_files,
                      2 : []}
    if not local_args.temp_dir:
        print "Error, need temp_dir ..."
        sys.exit(1)
    verbose = local_args.verbose
    print "Generating stage{:d} initrd, verbosity level is {:d} ...".format(local_args.stage_num, local_args.verbose)
    if local_args.stage_num == 1:
        stage_ok = populate_it(local_args.stage_num, local_args.temp_dir, stage1_dir_dict, stage1_file_dict, stage_add_dict, local_args.ignore_errors, local_args.show_content, local_args.modules)
    elif local_args.stage_num == 2:
        stage_ok = populate_it(local_args.stage_num, local_args.temp_dir, stage2_dir_dict, stage2_file_dict, stage_add_dict, local_args.ignore_errors, local_args.show_content, local_args.modules)
    else:
        stage_ok = populate_it(local_args.stage_num, local_args.temp_dir, stageloc_dir_dict, stageloc_file_dict, stage_add_dict, local_args.ignore_errors, local_args.show_content, local_args.modules)
    sys.exit(stage_ok)

def do_show_kernels(dev_assoc):
    out_list = logging_tools.new_form_list(none_string="---")
    if dev_assoc:
        all_kernels = kernel.objects.prefetch_related("new_kernel", "new_kernel__bootnetdevice").all().order_by("name")
        for cur_k in all_kernels:
            drivers = sorted(list(set([cur_dev.bootnetdevice.driver for cur_dev in cur_k.new_kernel.all() if cur_dev.bootnetdevice_id])))
            out_list.append(
                [
                    logging_tools.form_entry(cur_k.name, header="Kernel"),
                    logging_tools.form_entry(len(drivers), header="#drivers"),
                    logging_tools.form_entry(", ".join(drivers) or None, header="drivers"),
                    logging_tools.form_entry(cur_k.new_kernel.count(), header="#devices"),
                    logging_tools.form_entry(logging_tools.compress_list(sorted([cur_dev.name for cur_dev in cur_k.new_kernel.all()])) or None, header="#devices"),
                    ])
    else:
        all_kernels = kernel.objects.all().order_by("name")
        for cur_k in all_kernels:
            # k_stuff = kern_dict[k_name]
            # target module list
            t_mod_list = cur_k.target_module_list.split(",") if cur_k.target_module_list else []
            # module list in build
            b_mod_list = cur_k.module_list.split(",") if cur_k.module_list else []
            out_list.append([
                logging_tools.form_entry(cur_k.name, header="Kernel"),
                logging_tools.form_entry(cur_k.initrd_version, header="initrd_version"),
                logging_tools.form_entry(cur_k.initrd_built.strftime("%d. %b %Y %H:%M:%S") if cur_k.initrd_built else "<not set>", header="initrd_built"),
                logging_tools.form_entry("({:d}) {}".format(len(t_mod_list), ", ".join(t_mod_list)) if t_mod_list else None, header="target modules"),
                logging_tools.form_entry("({:d}) {}".format(len(b_mod_list), ", ".join(b_mod_list)) if b_mod_list else None, header="built modules"),
                ])
    if len(out_list):
        print out_list
    else:
        print "Empty list"
    sys.exit(0)

def log_it(what):
    print " - {}".format(what)

class arg_parser(argparse.ArgumentParser):
    def __init__(self):
        argparse.ArgumentParser.__init__(self)
        self.add_argument("-v", "--verbose", dest="verbose", default=0, action="count", help="increase verbosity [%(default)d]")
        self.add_argument("-6", dest="kernel_64_bit", default=False, action="store_true", help="force 64-bit Kernel [%(default)s]")
        self.add_argument("-k", dest="keep_dirs", default=False, action="store_true", help="keep stage 2 directories [%(default)s]")
        self.add_argument("-i", dest="ignore_errors", default=False, action="store_true", help="ignore errors (missing files), [%(default)s]")
        self.add_argument("-D", dest="do_depmod_call", default=True, action="store_false", help="skip depmod-call [%(default)s]")
        self.add_argument("-q", dest="quiet", default=False, action="store_true", help="quiet (except errors) [%(default)s]")
        self.add_argument("-t", dest="supress_transfer", default=True, action="store_false", help="transfer to other mother_server(s) [%(default)s]")
        self.add_argument("-m", dest="modules", default="", type=str, help="comma-separated list of kernel-modules to include in the first stage [%(default)s]")
        self.add_argument("--grub", dest="add_grub_binaries", default=False, action="store_true", help="add grub binaries in stage1 [%(default)s]")
        self.add_argument("--lilo", dest="add_lilo_binaries", default=False, action="store_true", help="add lilo binaries in stage1 [%(default)s]")
        self.add_argument("-l", dest="show_content", default=False, action="store_true", help="list dirs and files [%(default)s]")
        self.add_argument("-L", dest="show_kernels", default=0, action="count", help="gives an overview of the used kernels and drivers, use twice to show device association [%(default)d]")
        self.add_argument("-S", dest="stage_source_dir", default="/opt/cluster/lcs", type=str, help="source directory of stage files [%(default)s]")
        self.add_argument("-T", dest="stage_target_dir", default="", type=str, help="target directory of init files [%(default)s]")
        self.add_argument("-r", dest="root_dir", default="/", type=str, help="set rootdir [%(default)s]")
        self.add_argument("-s", dest="init_size", default=0, type=int, help="set the size for the initial ramdisk, is automatically extracted from .config [%(default)d]")
        self.add_argument("-F", dest="force_kernel_server", default=False, action="store_true", help="ignore if no kernel-server [%(default)s]")
        self.add_argument("--set-master-server", default=False, action="store_true", help="sets master-server of kernel to local server_idx [%(default)s]")
        self.add_argument("-M", dest="modules_file", default="", type=str, help="read list of kernel-modules from this file, if neither -m or -M is used the latest setting from the db is used")
        self.add_argument("--insert-kernel", default=False, action="store_true", help="add kernel to database (if not already present) [%(default)s]")
        # self.add_argument("--insert", dest="db_insert", default=False, action="store_true", help="insert kernel into database (if not already present) [%(default)s]")
        self.add_argument(dest="kernel_dir", default="", nargs="?")
    def parse(self):
        cur_args = self.parse_args()
        if not os.path.isdir(cur_args.root_dir):
            print "root_dir '{}' is no directory".format(cur_args.root_dir)
            sys.exit(0)
        cur_args.modules = [entry.strip() for entry in cur_args.modules.strip().split(",") if entry.strip()]
        return cur_args

def main_normal():
    global verbose
    start_time = time.time()
    my_args = arg_parser().parse()
    verbose = my_args.verbose
    script = sys.argv[0]
    local_script = "{}_local.py".format(script[:-3])
    stage_add_dict = {
        1 : {
            0 : [],
            1 : []},
        2 : {
            0 : [],
            1 : []},
        3 : {
            0 : [],
            1 : []}}
# #    for opt, arg in opts:
# #        if opt in ["-h", "--help"]:
# #            print " -M MODFILE           read list of kernel-modules from this file"
# #            print "                       o if neither -m or -M is used the latest setting from the db is used"
# #            print "                       o use -m \"\" to clear module list"
# #            print " --modules ARGS  additional modules to load in stage1, comma-separated: mod1[:mod1_options][,mod2[:mod2_options]]"
# #            sys.exit(0)
# #        if opt == "--modules":
# #            add_mods = []
# #            for line in arg.split(","):
# #                if line.count(":"):
# #                    mod_name, mod_option = line.split(":", 1)
# #                else:
# #                    mod_name, mod_option = (line, "")
# #                if mod_name.endswith(".o"):
# #                    mod_name = mod_name[:-2]
# #                elif mod_name.endswith(".ko"):
# #                    mod_name = mod_name[:-3]
# #                add_mods.append((mod_name, mod_option))
# #            loc_config["ADD_MODULES"] = add_mods
    if my_args.show_kernels:
        do_show_kernels(my_args.show_kernels == 2)
        sys.exit(1)
    if not my_args.kernel_dir:
        print "No kernel-dir given, exiting"
        sys.exit(1)
    kernel_name = os.path.split(os.path.normpath(my_args.kernel_dir))[1]
    if not kernel_name:
        print "Cannot extract kernel_name from {}".format(my_args.kernel_dir)
        sys.exit(1)
    if not os.path.isfile(os.path.join(my_args.kernel_dir, "bzImage")):
        print "Found no kernel (bzImage) under {}, exiting".format(my_args.kernel_dir)
        sys.exit(1)
    _long_host_name, short_host_name = process_tools.get_fqdn()
    # kernel_server idx
    kernel_server_idx = 0
    # check for kernel_server
    mother_configs = config_tools.device_with_config("kernel_server")
    ks_check = config_tools.server_check(server_type="kernel_server")
    if not ks_check.effective_device:
        if my_args.force_kernel_server:
            print "Host '{}' is not a kernel_server but continuing due to force flag, just building initrd".format(short_host_name)
        else:
            print "Host '{}' is not a kernel_server, exiting ...".format(short_host_name)
            sys.exit(1)
    else:
        kernel_server_idx = ks_check.effective_device.pk
        mother_list = mother_configs["kernel_server"]
        print "Host '{}' is a kernel_server (device_idx {:d}), found {}: {}".format(
            short_host_name,
            ks_check.effective_device.pk,
            logging_tools.get_plural("mother_server", len(mother_list)),
            ", ".join(["{} [{}]".format(
                unicode(cur_entry.effective_device),
                ", ".join(cur_entry.simple_ip_list)) for cur_entry in mother_list]))
    if not os.path.isdir(my_args.kernel_dir):
        print "Need a directory as argument ('{}' is not a directory)".format(my_args.kernel_dir)
        sys.exit(1)
    elif not os.path.isabs(my_args.kernel_dir):
        print "Need an absoult path as argument ('{}' is a relative path)".format(my_args.kernel_dir)
        sys.exit(1)
    target_path = os.path.normpath(my_args.kernel_dir)
    try:
        my_kernel = kernel.objects.get(Q(name=kernel_name))
    except kernel.DoesNotExist:
        # if my_args.db_insert:
        #    print "*** Cannot find a kernel at path '%s' (%s at %s) in database, inserting..." % #(my_args.kernel_dir, kernel_name, target_path)
        if my_args.insert_kernel:
            print "+++ kernel at path '{}' ({} at {}) not found in database, creating".format(my_args.kernel_dir, kernel_name, target_path)
            my_kernel = kernel(name=kernel_name, master_server=ks_check.effective_device.pk)
            my_kernel.save()
        else:
            print "*** Cannot find a kernel at path '{}' ({} at {}) in database".format(my_args.kernel_dir, kernel_name, target_path)
        my_kernel = None
    if my_kernel:
        my_build = initrd_build(
            kernel=my_kernel
            )
        my_build.save()
    else:
        my_build = None
    if my_kernel:
        print "Found kernel at path '{}' ({} at {}) in database (kernel_idx is {:d})".format(my_args.kernel_dir, kernel_name, target_path, my_kernel.pk)
        if my_kernel.xen_host_kernel:
            print " - kernel for Xen-hosts"
        if my_kernel.xen_guest_kernel:
            print " - kernel for Xen-guests"
        if kernel_server_idx:
            if kernel_server_idx != my_kernel.master_server:
                if my_args.set_master_server:
                    print "setting master_server of kernel to local kernel_server_idx"
                    my_kernel.master_server = kernel_server_idx
                    my_kernel.save()
                else:
                    print "server_device_idx ({:d}) for kernel_server differs from master_server from DB ({}), exiting (override with --set-master-server)".format(
                        kernel_server_idx,
                        my_kernel.master_server,
                        )
                    sys.exit(0)
    # build list of modules
    act_mods = []
    take_modules_from_db = (my_args.modules == [] and not my_args.modules_file)
    if not take_modules_from_db:
        if my_args.modules_file:
            if os.path.isfile(my_args.modules_file):
                act_mods.extend([line.strip() for line in file(my_args.modules_file, "r").read().split("\n") if line.strip()])
            else:
                print "cannot read mods_file '{}', exiting...".format(my_args.modules_file)
                sys.exit(1)
        for mod in my_args.modules:
            if mod.endswith(".o"):
                mod = mod[:-2]
            elif mod.endswith(".ko"):
                mod = mod[:-3]
            if mod and mod not in MOD_REFUSE_LIST:
                act_mods.append(mod)
    my_args.add_modules = []
    # if my_args.loc_config["ADD_MODULES"]:
    #    act_mods.extend([mod_name for mod_name, mod_option in loc_config["ADD_MODULES"]])
    act_mods.sort()
    # check type of build-dir linux (32/64 bit)
    build_arch_64bit = get_system_bitcount(my_args.root_dir)
    local_arch_64bit = get_system_bitcount("/")
    if build_arch_64bit > local_arch_64bit:
        print "don't known how to build 64bit initrds on a 32bit System, exiting..."
        sys.exit(1)
    # try to get kernel config
    wrong_config_name = os.path.join(my_args.kernel_dir, "config")
    if os.path.isfile(wrong_config_name):
        print
        print " *** Found {}, please move to .config".format(wrong_config_name)
        print
    if os.path.isfile(os.path.join(my_args.kernel_dir, ".config")):
        conf_lines = [y for y in [x.strip() for x in file(os.path.join(my_args.kernel_dir, ".config"), "r").read().split("\n") if x.strip()] if not y.strip().startswith("#")]
        conf_dict = dict([x.split("=", 1) for x in conf_lines])
    else:
        print "Warning, no kernel_config {}/.config found".format(my_args.kernel_dir)
        conf_dict = {}
    # set initsize if not already set
    if not my_args.init_size:
        my_args.init_size = int(conf_dict.get("CONFIG_BLK_DEV_RAM_SIZE", "32768"))
    # check for 64bit Kernel
    if not my_args.kernel_64_bit:
        my_args.kernel_64_bit = "CONFIG_X86_64" in conf_dict
    if not local_arch_64bit and my_args.kernel_64_bit:
        print "/ is 32bit and Kernel 64 bit, exiting"
        sys.exit(1)
    if build_arch_64bit and not my_args.kernel_64_bit:
        print "build_architecture under {} is 64bit and Kernel 32 bit, exiting".format(my_args.root_dir)
        sys.exit(1)
    # modules.tar.bz2 present ?
    mod_bz2_file = os.path.join(my_args.kernel_dir, "modules.tar.bz2")
    mod_bz2_present = os.path.exists(mod_bz2_file)
    # check for kernel version
    if os.path.isdir("{}/lib/modules".format(my_args.kernel_dir)):
        kverdirs = os.listdir("{}/lib/modules".format(my_args.kernel_dir))
        if len(kverdirs) > 1:
            print "More than one KernelVersionDirectory found: {}".format(", ".join(kverdirs))
            sys.exit(1)
        elif len(kverdirs) == 0:
            print "No KernelVersionDirectory found below '{}/lib/modules'".format(my_args.kernel_dir)
            sys.exit(1)
        kverdir = kverdirs[0]

        if my_args.do_depmod_call:
            lib_dir = os.path.join(my_args.kernel_dir, "lib", "modules", kverdir)
            # content of modules.dep
            mdep_file = os.path.join(lib_dir, "modules.dep")
            if os.path.isfile(mdep_file):
                pre_content = file(mdep_file, "r").read()
            else:
                pre_content = ""
            depmod_call = "depmod -aeb {} {}".format(my_args.kernel_dir, kverdir)
            if not my_args.quiet:
                print "Doing depmod_call '{}' ...".format(depmod_call)
            c_stat, out = commands.getstatusoutput(depmod_call)
            if c_stat:
                print " - some error occured ({:d}): {}".format(c_stat, out)
                sys.exit(1)
            if os.path.isfile(mdep_file):
                post_content = file(mdep_file, "r").read()
                if pre_content != post_content:
                    mod_bz2_present = False
                    print "modules.dep file '{}' has changed, rebuilding {}".format(mdep_file, mod_bz2_file)
            else:
                print "no modules.dep file '{}' found, exiting".format(mdep_file)
                sys.exit(1)
    else:
        kverdir = os.path.basename(os.path.normpath(my_args.kernel_dir))
        print "No lib/modules directory found under '{}', setting kernel_version to {}".format(my_args.kernel_dir, kverdir)
    if not mod_bz2_present:
        print "(re)creating {}".format(mod_bz2_file)
        if os.path.exists(mod_bz2_file):
            os.unlink(mod_bz2_file)
        t_stat, t_out = commands.getstatusoutput("cd {} ; tar cpsjf modules.tar.bz2 lib".format(my_args.kernel_dir))
        print "... gave ({:d}) {}".format(t_stat, t_out)
        if t_stat:
            sys.exit(t_stat)
    bit_dict = {0 : "32",
                1 : "64"}
    # check availability of stages
    for stage in ["1", "2", "3", "local"]:
        fname = "/{}/stage{}".format(my_args.stage_source_dir, stage)
        if not os.path.isfile(fname):
            print "Cannot find stage {} file {} in stage_dir {}".format(stage, fname, my_args.stage_source_dir)
            sys.exit(1)
    free_lo_dev = find_free_loopdevice()
    if free_lo_dev == -1:
        print "Cannot find free loopdevice, exiting..."
        sys.exit(1)
    loop_dev = "/dev/loop{:d}".format(free_lo_dev)
    # read uuid
    my_uuid = uuid_tools.get_uuid()
    if not my_args.quiet:
        print "cluster_device_uuid is {}".format(my_uuid.get_urn())
        print "Kernel directory is '%s', initsize is %d kBytes" % (my_args.kernel_dir, my_args.init_size)
        print "  using loopdevice %s" % (loop_dev)
        print "  kernel_version is %s, %s-bit kernel" % (kverdir, bit_dict[my_args.kernel_64_bit])
        print "  build_dir is '%s', %s-bit linux" % (my_args.root_dir, bit_dict[build_arch_64bit])
        print "  local_system is a %s-bit linux" % (bit_dict[local_arch_64bit])
        print "  stage source directory is %s" % (my_args.stage_source_dir)
        print "  stage target directory is %s" % (my_args.stage_target_dir and my_args.stage_target_dir or my_args.kernel_dir)
        print "  will create three flavours:"
        print "    - use mkfs.cramfs to build stage1 initrd"
        print "    - create a cpio-archive for stage1 initrd"
        print "    - use loopdevice %s to build stage1 initrd" % (loop_dev)
    stage_add_dict[1][1].append("run-init")
    stage_add_dict[3][1].append("run-init")
    # add boot-load specific files
    if my_args.add_grub_binaries:
        if not my_args.quiet:
            print "  adding grub-binaries"
        stage_add_dict[2][1].extend(["grub", "grub-install"])
    if my_args.add_lilo_binaries:
        if not my_args.quiet:
            print "  adding lilo-binaries"
        stage_add_dict[2][1].extend(["lilo"])
    # get kernel-module dependencies
    if my_kernel:
        if take_modules_from_db:
            if my_kernel.target_module_list:
                act_mods = [line.strip() for line in my_kernel.target_module_list.split(",") if line.strip() not in MOD_REFUSE_LIST]
            else:
                act_mods = []
            print "Using module_list from database: %s, %s" % (
                logging_tools.get_plural("module", len(act_mods)),
                ", ".join(act_mods))
        else:
            print "Saving module_list to database: %s, %s" % (
                logging_tools.get_plural("module", len(act_mods)),
                ", ".join(act_mods))
            my_kernel.target_module_list = ",".join(act_mods)
            my_kernel.save()
    if act_mods:
        dep_h = module_dependency_tools.dependency_handler(my_args.kernel_dir)
        dep_h.resolve(act_mods, verbose=verbose)
        all_mods, del_mods, fw_files = (
            dep_h.module_list,
            dep_h.error_list,
            dep_h.firmware_list)
        all_mods = [x for x in all_mods if x not in MOD_REFUSE_LIST]
        act_mods.sort()
        all_mods.sort()
        del_mods.sort()
        if not my_args.quiet:
            print "  %s given: %s; %s not found, %s have to be installed" % (
                logging_tools.get_plural("kernel module", len(act_mods)),
                ", ".join(act_mods),
                logging_tools.get_plural("module", len(del_mods)),
                logging_tools.get_plural("module", len(all_mods)))
        if my_args.verbose and not my_args.quiet:
            for mod in del_mods:
                print " - (not found) : %s" % (mod)
            for mod in all_mods:
                print " + (found) : %s" % (mod)
    else:
        all_mods, fw_files = ([], [])
        if not my_args.quiet:
            print "  no kernel-modules given"
    if my_kernel:
        base_mods = [".".join(os.path.basename(x).split(".")[0:-1]) for x in all_mods]
        base_mods.sort()
        if my_kernel.module_list:
            last_base_mods = map(lambda x: x.strip(), my_kernel.module_list.split(","))
        else:
            last_base_mods = []
        if last_base_mods == base_mods:
            print "Updating database (modules are the same)...",
        else:
            print "Updating database (modules changed from %s to %s)..." % (
                last_base_mods and ", ".join(last_base_mods) or "<None>",
                base_mods and ", ".join(base_mods) or "<None>"),
        my_kernel.module_list = ",".join(base_mods)
        my_kernel.initrd_build = datetime.datetime.now()
        my_kernel.save()
        print "ok"
    if my_args.root_dir != "/":
        loc_src, loc_dst = (script, os.path.normpath("%s/%s" % (my_args.root_dir, os.path.basename(local_script))))
        if not my_args.quiet:
            print "  copying %s to %s" % (loc_src, loc_dst)
        shutil.copy(loc_src, loc_dst)
    # setting up loopdevice for stage1
    stage1_lo_file = os.path.normpath("/%s/initrd_lo" % (my_args.stage_target_dir and my_args.stage_target_dir or my_args.kernel_dir))
    stage1_cramfs_file = os.path.normpath("/%s/initrd_cramfs" % (my_args.stage_target_dir and my_args.stage_target_dir or my_args.kernel_dir))
    stage1_cpio_file = os.path.normpath("/%s/initrd_cpio" % (my_args.stage_target_dir and my_args.stage_target_dir or my_args.kernel_dir))
    stage2_file = os.path.normpath("/%s/initrd_stage2.gz" % (my_args.stage_target_dir and my_args.stage_target_dir or my_args.kernel_dir))
    stageloc_file = os.path.normpath("/%s/initrd_local" % (my_args.stage_target_dir and my_args.stage_target_dir or my_args.kernel_dir))
    for del_file in [stage1_lo_file, stage1_cramfs_file, stage1_cpio_file, stage2_file, stageloc_file]:
        if os.path.isfile(del_file):
            os.unlink(del_file)
        if os.path.isfile("%s.gz" % (del_file)):
            os.unlink("%s.gz" % (del_file))
    stage1_dir = tempfile.mkdtemp(".stage1_dir"  , "/%s/tmp/.rdc_" % (my_args.root_dir))
    stage2_dir = tempfile.mkdtemp(".stage2_dir"  , "/%s/tmp/.rdc_" % (my_args.root_dir))
    stageloc_dir = tempfile.mkdtemp(".stageloc_dir", "/%s/tmp/.rdc_" % (my_args.root_dir))
    stat_out = []
    stat_out += [("dd"       , commands.getstatusoutput("dd if=/dev/zero of=%s bs=1024 count=%d" % (stage1_lo_file, my_args.init_size)))]
    stat_out += [("losetup"  , commands.getstatusoutput("losetup %s %s" % (loop_dev, stage1_lo_file)))]
    stat_out += [("mkfs.ext2", commands.getstatusoutput("mkfs.ext2 -F -v -m 0 -b 1024 %s %d" % (stage1_lo_file, my_args.init_size)))]
    stat_out += [("mount"    , commands.getstatusoutput("mount -o loop -t ext2 %s %s" % (stage1_lo_file, stage1_dir)))]
    if len([err_name for name, (err_name, line) in stat_out if err_name]):
        print "Something went wrong during setup of stage1:"
        for name, (err_name, line) in stat_out:
            print "%s (%d) : \n%s" % (name, err_name, "\n".join([" - %s" % (part) for part in line.split("\n")]))
        sys.exit(-1)
    stage_targ_dirs = [stage1_dir, stage2_dir, stageloc_dir]
    stage_dirs, del_dirs = ([], [])
    for stage in range(1, 4):
        if not my_args.quiet:
            print "Generating stage%s initrd ..." % ({1 : "1",
                                                      2 : "2",
                                                      3 : "local"}[stage])
        act_stage_dir = stage_targ_dirs[stage - 1]
        loc_root_dir = "/".join([""] + act_stage_dir.split("/")[-2:])
        loc_args = " ".join(["-v"] * my_args.verbose)
        if my_args.ignore_errors:
            loc_args += " -i "
        if my_args.show_content:
            loc_args += " -l "
        if my_args.root_dir != "/":
            gen_com = "chroot %s /%s %s -d %s -s %d" % (my_args.root_dir, os.path.basename(local_script), loc_args, loc_root_dir, stage)
        else:
            gen_com = "%s %s -s %d -d %s " % (local_script, loc_args, stage, loc_root_dir)
        gen_com = "%s %s" % (gen_com, " ".join(["-%d %s" % (im_key, ",".join(stage_add_dict[stage][im_key])) for im_key in [0, 1] if stage_add_dict[stage][im_key]]))
        if my_args.add_modules and stage in [1, 3]:
            gen_com = "%s --modules %s" % (gen_com, ",".join(["%s:%s" % (mod_name, mod_option) for mod_name, mod_option in my_args.add_modules]))
        if not my_args.quiet:
            print gen_com
        c_stat, out = commands.getstatusoutput(gen_com)
        if my_args.verbose and not my_args.quiet:
            print "\n".join([" - %s" % (x) for x in out.split("\n")])
        act_stage_dir = [y.split()[1].strip() for y in [x.strip() for x in out.strip().split("\n")] if y.startswith("INITDIR")]
        if act_stage_dir:
            stage_dirs += ["%s/%s" % (my_args.root_dir, act_stage_dir[0])]
        else:
            print "Error generating stage%d dir" % (stage)
            print "\n".join(["  - %s" % (x) for x in out.split("\n") if x.strip().startswith("E ")])
        del_dirs += [os.path.normpath("%s/%s" % (my_args.root_dir, loc_root_dir))]
    stage_dirs_ok = len(stage_dirs) == len(stage_targ_dirs)
    if stage_dirs_ok:
        for linuxrc_name in LINUXRC_NAMES:
            # stage1 stuff
            stage1_dest = "/%s/%s" % (stage_dirs[0], linuxrc_name)
            shutil.copy2("/%s/stage1" % (my_args.stage_source_dir), stage1_dest)
            os.chmod(stage1_dest, 0744)
            os.chown(stage1_dest, 0, 0)
            # stagelocal stuff
            stageloc_dest = "/%s/%s" % (stage_dirs[2], linuxrc_name)
            shutil.copy2("/%s/stagelocal" % (my_args.stage_source_dir), stageloc_dest)
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
                    found = False
                    fw_src_files = [
                        "/{}/lib/firmware/{}/{}".format(my_args.kernel_dir, kverdir, fw_file),
                        "/{}/lib/firmware/{}".format(my_args.kernel_dir, fw_file),
                    ]
                    for fw_src_file in fw_src_files:
                        if os.path.isfile(fw_src_file):
                            loc_fw_dir = "/%s/%s" % (fw_dir, os.path.dirname(fw_file))
                            loc_fw_dir_2 = "/%s/%s" % (fw_dir_2, os.path.dirname(fw_file))
                            if not os.path.isdir(loc_fw_dir):
                                os.makedirs(loc_fw_dir)
                            if not os.path.isdir(loc_fw_dir_2):
                                os.makedirs(loc_fw_dir_2)
                            shutil.copy2(fw_src_file, loc_fw_dir)
                            shutil.copy2(fw_src_file, loc_fw_dir_2)
                            found = True
                            break
                    if not found:
                        print "*** cannot read firmware-file (one of {})".format(", ".join(fw_src_files))
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
        for dir_name, _dir_list, file_list in os.walk(stage_targ_dirs[1]):
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
    if my_kernel:
        for stage1_flav in ["lo", "cpio", "cramfs"]:
            setattr(my_kernel, "stage1_%s_present" % (stage1_flav), True)
        my_kernel.stage2_present = True
        if not my_kernel.initrd_version:
            my_kernel.initrd_version = 0
        my_kernel.initrd_version += 1
        my_kernel.initrd_built = datetime.datetime.now()
        my_kernel.save()
    # cleaning up
    if my_args.root_dir != "/":
        os.unlink(loc_dst)
    if not stage_dirs_ok:
        print "Stage directories not OK, exiting..."
        sys.exit(-1)
    if not my_args.keep_dirs:
        for del_dir in del_dirs:
            if not my_args.quiet:
                print "removing directory %s ..." % (del_dir)
            shutil.rmtree(del_dir)
    if not my_args.supress_transfer:
        _uuid_connected = [my_uuid]
        print "command_stack is not longer available, please copy from hand"
    end_time = time.time()
    if my_build:
        my_build.run_time = int(end_time - start_time)
        my_build.success = True if stage_dirs_ok else False
        my_build.save()
# #         send_list = command_stack.send_list([command_stack.send_data(stage1_file),
# #                                              command_stack.send_data(stage2_file),
# #                                              command_stack.send_str("quit")], log_it, CS_BLOCK_SIZE)
# #         for ms_name, (ms_ip, ms_alias) in ms_dict.iteritems():
# #             # get uuid for all mother-server
# #             errnum, data = msock.single_tcp_connection((ms_ip, 8004, server_command.server_command(command="get_uuid")), None, timeout=10)
# #             if errnum:
# #                 print "error receiving uuid from %s (IP %s) (%d): %s" % (ms_name, ms_ip, errnum, data)
# #             else:
# #                 try:
# #                     s_reply = server_command.server_reply(data)
# #                 except:
# #                     print "error build server_reply from data from %s (IP %s) (%d): %s" % (ms_name, ms_ip, errnum, data[0:15])
# #                 else:
# #                     server_uuid = uuid_tools.UUID(s_reply.get_result().split()[1])
# #                     if server_uuid in uuid_connected:
# #                         print "uuid %s for %s (IP %s) already in connected list, skipping..." % (server_uuid, ms_name, ms_ip)
# #                     else:
# #                         uuid_connected.append(server_uuid)
# #                         send_list.init_instance()
# #                         if ms_ip == "127.0.0.1" or ms_name == short_host_name:
# #                             print "Motherserver %s (IP %s, alias %s) seems to be local, skipping ..." % (ms_name, ms_ip, ms_alias or "<EMPTY>")
# #                         else:
# #                             print "Transfering stages to motherserver %s (IP %s, alias %s) ..." % (ms_name, ms_ip, ms_alias or "<EMPTY>")
# #                             tcp_stat, tcp_out = msock.single_tcp_connection((ms_ip, 8001, (send_list, send_list)), None, 10)
# #                             if tcp_stat:
# #                                 print " - gave error (%d): %s" % (tcp_stat, tcp_out)
    return

if __name__ == "__main__":
    main()
