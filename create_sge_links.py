#!/usr/bin/python-init -Ot
# -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2005,2007,2008,2012 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
# 
# This file is part of rms-tools
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

import sys
import os
import os.path
import commands
import shutil

def read_base_config():
    files_ok = True
    var_dict = {}
    for var_name in ["SGE_%s" % (var_name) for var_name in ["ROOT", "CELL", "SERVER"]]:
        file_name = "/etc/sge_%s" % (var_name.split("_")[1].lower())
        if not os.path.isfile(file_name):
            print "File %s not found" % (file_name)
            files_ok = False
        else:
            var_dict[var_name] = file(file_name, "r").read().split("\n")[0].strip()
    if not files_ok:
        print "exiting ..."
        sys.exit(1)
    return var_dict

def call_command(com):
    stat, out = commands.getstatusoutput(com)
    if stat:
        print "Calling %s resulted in an error (%d):" % (com, stat)
        print out
        sys.exit(3)
    else:
        print "Calling %s successfull" % (com)
    return out.split("\n")

def create_blu_links(var_dict):
    # deprecated, do not use
    sys.exit(0)
    t_dirs = dict([("%s/%s" % (var_dict["SGE_ROOT"], x), {}) for x in ["bin", "lib", "utilbin"]])
    all_kvers, all_mach_types = ([], [])
    for t_dir in t_dirs.keys():
        for ent in os.listdir(t_dir):
            if ent.count("-"):
                k_ver, mach_type = ent.split("-", 1)
                if k_ver not in all_kvers:
                    all_kvers.append(k_ver)
                if mach_type not in all_mach_types:
                    all_mach_types.append(mach_type)
                full_dir = "%s/%s" % (t_dir, ent)
                if os.path.isdir(full_dir):
                    if os.path.islink(full_dir):
                        # is_link
                        t_dirs[t_dir][ent] = "l"
                    else:
                        # is_dir
                        t_dirs[t_dir][ent] = "d"
        for mach_type in all_mach_types:
            for k_ver in all_kvers:
                ent = "%s-%s" % (k_ver, mach_type)
                if t_dirs[t_dir].get(ent, None) == "d":
                    # primary dir
                    t_dirs[t_dir][ent] = "p"
    all_prim_ents = []
    for t_dir in t_dirs.keys():
        os.chdir(t_dir)
        for prim_ent in [k for k, v in t_dirs[t_dir].iteritems() if v == "p"]:
            if prim_ent not in all_prim_ents:
                all_prim_ents.append(prim_ent)
        for mach_type in all_mach_types:
            for k_ver in all_kvers:
                ent = "%s-%s" % (k_ver, mach_type)
                if not os.path.exists(ent):
                    prim_ent = [k for k, v in t_dirs[t_dir].iteritems() if v == "p" and k.endswith(mach_type)]
                    if prim_ent:
                        prim_ent = prim_ent[0]
                        print "Linking from %s to %s" % (ent, prim_ent)
                        os.symlink(prim_ent, ent)
                    else:
                        print "No entries found for mach_type %s, skipping" % (mach_type)
    # primary architecture
    return all_prim_ents

def remove_py_files(var_dict):
    for dir_path, dir_names, file_names in os.walk(var_dict["SGE_ROOT"]):
        for file_name in file_names:
            if [True for x in [".pyo", ".pyc", ".py"] if file_name.endswith(x)]:
                os.unlink("%s/%s" % (dir_path, file_name))

def copy_files(var_dict, src_name, dst_dir):
    file_name = "%s/%s" % (var_dict["SGE_DIST_DIR"], src_name)
    if os.path.isfile(file_name):
        sge_files = file(file_name, "r").read().split("\n")[0].split()
        for file_name in sge_files:
            shutil.copy2("%s/%s" % (var_dict["SGE_DIST_DIR"], file_name),
                         "%s/%s" % (var_dict["SGE_ROOT"], dst_dir))
    else:
        print "cannot find file %s, exiting ..." % (file_name)
        sys.exit(5)

def generate_links(l_dict):
    for l_target, l_sources in l_dict.iteritems():
        t_dir, t_file = os.path.split(l_target)
        for l_source in l_sources:
            s_dir, s_file = os.path.split(l_source)
            os.chdir(s_dir)
            com_path = os.path.commonprefix([t_dir, s_dir])
            up_dirs = ""
            if len(s_dir[len(com_path):]):
                up_dirs = "/".join([".."] * ((s_dir[len(com_path):]).count("/") + 1)) + "/"
            up_dirs += t_dir[len(com_path):]
            if up_dirs:
                l2_target = "%s/%s" % (up_dirs, t_file)
            else:
                l2_target = t_file
            if os.path.islink(s_file):
                link_targ = os.readlink(s_file)
                if not os.path.isabs(link_targ):
                    link_targ = os.path.realpath(os.path.join(s_dir, link_targ))
                if link_targ != l_target:
                    print "Removing link %s (pointing to %s instead of %s)" % (s_file, link_targ, l_target)
                    os.unlink(s_file)
            if not os.path.islink(s_file):
                print "Linking from %s to %s" % (s_file, l2_target)
                os.symlink(l2_target, s_file)
        
def main():
    # read basic vars
    var_dict = read_base_config()
    var_dict["SGE_DIST_DIR"] = "/opt/cluster/sge"
    # check for util-dir
    util_dir = "%s/util" % (var_dict["SGE_ROOT"])
    if not os.path.isdir(util_dir):
        print "Dir '%s' not found, exiting ..."
        sys.exit(2)
    # get SGE_ARCH
    var_dict["SGE_ARCH"] = call_command("%s/util/arch" % (var_dict["SGE_ROOT"]))[0]
    # show variables
    for key, value in var_dict.iteritems():
        print "%-12s : %s" % (key, value)
    # create bin/lib/utilbin links
    #all_archs = create_blu_links(var_dict)
    # check for missing dirs
    mis_dirs = ["%s/%s" % (var_dict["SGE_ROOT"], x) for x in ["bin/noarch",
                                                              "3rd_party",
                                                              "3rd_party/prologue.d",
                                                              "3rd_party/epilogue.d"]]
    for mis_dir in mis_dirs:
        if not os.path.isdir(mis_dir):
            print "Creating directory %s ..." % (mis_dir)
            os.mkdir(mis_dir)
    # remove python-files
    remove_py_files(var_dict)
    # copy sge-files
    copy_files(var_dict, ".sge_files", "bin/noarch")
    # copy 3rdparty-files
    copy_files(var_dict, ".party_files", "3rd_party")
    # build link dict
    link_dict = {"%s/3rd_party/proepilogue.py" % (var_dict["SGE_ROOT"]) : ["%s/3rd_party/%s" % (var_dict["SGE_ROOT"], x) for x in [
        "prologue",
        "epilogue",
        "lamstart",
        "lamstop",
        "pestart",
        "pestop",
        "mvapich2start",
        "mvapich2stop"]]}
    generate_links(link_dict)

if __name__ == "__main__":
    main()
