#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of cluster-backbone
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
import mysql_tools
import getopt
import os
import os.path
import commands
import pprint
import time
import logging_tools

needed_packages = sorted(["python-init",
                          "ethtool-init",
                          "host-monitoring",
                          "meta-server",
                          "logging-server",
                          "package-client",
                          "loadmodules",
                          "python-modules-base",
                          "child"])

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], "r:i:hM", ["help"])
    except:
        print "Error parsing commandline %s" % (" ".join(sys.argv[:]))
        sys.exit(-1)
    image_idx, root_dir, source_path, do_chroot = (0, "/", "", True)
    for opt, arg in opts:
        if opt in ["-h", "--help"]:
            print "Usage: %s" % (os.path.basename(sys.argv[0]))
            print " -r <ROOT_DIR>       sets root_dir, default is '%s'" % (root_dir)
            print " -i <IDX>            set_image_idx (used for scripts)"
            print " -M                  do not use chroot-call"
            sys.exit(0)
        if opt == "-r":
            if os.path.isdir(arg):
                root_dir = arg
                print "Setting root-directory to %s" % (root_dir)
                source_path = "fs"
            else:
                print "Error: '%s' is not a valid directory" % (arg)
                sys.exit(-1)
        if opt == "-i":
            try:
                image_idx = int(arg)
            except:
                print "Error parsing image index %s" % (arg)
                sys.exit(-1)
            else:
                print "Setting image_idx to %d" % (image_idx)
                source_path = "db"
        if opt == "-M":
            do_chroot = False
    if not source_path:
        print "No source set (neither -r nor -i specified)"
        sys.exit(-1)
    packages, num_p = ({}, 0)
    if source_path == "fs":
        form_str = "--queryformat=\"n%{NAME}\\nv%{VERSION}\\nr%{RELEASE}\\na%{ARCH}\\ns%{SIZE}\\nS%{SUMMARY}\\ni%{INSTALLTIME}\\nd%{DISTRIBUTION}\\nV%{VENDOR}\\ng%{GROUP}\\nt%{BUILDTIME}\\nh%{BUILDHOST}\\np%{PACKAGER}\\n\""
        pack_mode = "rpm"
        if do_chroot:
            query_str = "chroot %s rpm -qa %s" % (root_dir, form_str)
        else:
            query_str = "rpm --root=%s -qa %s" % (root_dir, form_str)
        stat, p_list = commands.getstatusoutput(query_str)
        if stat:
            print "Error while executing '%s' [%d]: %s" % (query_str, stat, str(p_list))
            sys.exit(-1)
        rel_dict = {"n" : ("name"        , "s", 1), "r" : ("release", "s", 1), "a" : ("architecture", "s", 2), "v" : ("version"  , "s", 1), "s" : ("size"        , "i", 1), 
                    "S" : ("summary"     , "s", 1), "g" : ("pgroup" , "s", 1), "t" : ("buildtime"   , "i", 1), "h" : ("buildhost", "s", 1), "p" : ("packager"    , "s", 1), 
                    "d" : ("distribution", "s", 2), "V" : ("vendor" , "s", 2), "i" : ("install_time", "i", 0)}
        # parse p_list
        act_p = None
        for pfix, p_str in [(y[0], y[1:].strip()) for y in [x.strip() for x in p_list.split("\n")] if len(y[1:].strip())]:
            #print pfix, p_str
            if pfix == "n":
                act_p = {"name" : p_str}
            else:
                if act_p:
                    if pfix in rel_dict.keys():
                        dname, d_type, p_entry = rel_dict[pfix]
                        if d_type == "s":
                            act_p[dname] = p_str
                        else:
                            if p_str == "(none)":
                                p_str = "0"
                            try:
                                act_p[dname] = int(p_str)
                            except:
                                act_p[dname] = 0
                                print "Error converting %s to int (%s), setting to %d" % (p_str, dname, act_p[dname])
                    else:
                        print "Error: postfix %s not in dictionary (%s): %s" % (pfix,
                                                                                ", ".join(rel_dict.keys()),
                                                                                p_str)
                    if pfix == "p":
                        num_p += 1
                        packages.setdefault(act_p["name"], []).append(act_p)
                        act_p = None
                else:
                    print "Error while parsing (act_p is None for type %s [%s])" % (pfix, p_str)
    else:
        db_con = mysql_tools.dbcon_container()
        dc = db_con.get_connection("cluster_full_access")
        dc.execute("SELECT p.* FROM package p, pi_connection pi WHERE p.package_idx=pi.package AND pi.image=%d" % (image_idx))
        for x in dc.fetchall():
            num_p += 1
            packages.setdefault(x["name"], []).append(x)
        dc.release()
        del db_con
    print "Found %s" % (logging_tools.get_plural("valid clustersoftware package", (num_p)))
    pack_missing = [x for x in needed_packages if x not in sorted(packages.keys())]
    if pack_missing:
        print "*** %s missing: %s" % (logging_tools.get_plural("package", len(pack_missing)),
                                      ", ".join(pack_missing))
        sys.exit(1)
    else:
        print "all %s found" % (logging_tools.get_plural("package", needed_packages))
        sys.exit(0)
  
if __name__ == "__main__":
    main()
    
