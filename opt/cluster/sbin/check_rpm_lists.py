#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001-2007,2015 Andreas Lang-Nevyjel
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

import commands
import sys
import getopt
import os
import os.path

from initat.tools import logging_tools
from initat.tools import process_tools


def parse_list(in_list):
    second_d = in_list.index(":", in_list.index(":") + 1) + 5
    return process_tools.net_to_sys(in_list[second_d:])


def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hd", ["version", "help"])
    except getopt.GetoptError, bla:
        print "Error parsing commandline %s: %s" % (" ".join(sys.argv[1:]),
                                                    process_tools.get_except_info())
        sys.exit(1)
    opt_dict = {"detailed_list": False}
    for opt, arg in opts:
        if opt in ["-h", "--help"]:
            print "Usage : %s [OPTIONS] host1[:dir1] host2[:dir2]" % (os.path.basename(sys.argv[0]))
            print "  where OPTIONS is one or more of"
            print " -h, --help      this help"
            print " -d              detailed list"
            sys.exit(0)
        if opt == "-d":
            opt_dict["detailed_list"] = True
    if len(args) != 2:
        print "Need host1[:dir1] and host2[:dir2] as argument"
        sys.exit(0)
    host_1, host_2 = args
    if host_1.count(":"):
        host_1, dir_1 = host_1.split(":", 1)
    else:
        dir_1 = "/"
    if host_2.count(":"):
        host_2, dir_2 = host_2.split(":", 1)
    else:
        dir_2 = "/"
    print "Comparing rpm_lists of %s (dir %s) and %s (dir %s)" % (host_1, dir_1, host_2, dir_2)
    stat_1, list_1 = commands.getstatusoutput("collclient.py --host %s rpmlist -r %s" % (host_1, dir_1))
    stat_2, list_2 = commands.getstatusoutput("collclient.py --host %s rpmlist -r %s" % (host_2, dir_2))
    if stat_1 or stat_2:
        print "error getting lists (%d / %d)" % (stat_1, stat_2)
        sys.exit(1)
    dict_1 = parse_list(list_1)
    dict_2 = parse_list(list_2)
    rpm_dict_1 = dict_1["rpm_dict"]
    rpm_dict_2 = dict_2["rpm_dict"]
    keys_1 = rpm_dict_1.keys()
    keys_2 = rpm_dict_2.keys()
    keys_1.sort()
    keys_2.sort()
    missing_in_1 = [x for x in keys_2 if x not in keys_1]
    missing_in_2 = [x for x in keys_1 if x not in keys_2]
    for missing_in, host, dir in [(missing_in_1, host_1, dir_1),
                                  (missing_in_2, host_2, dir_2)]:
        if missing_in:
            print "%s missing on %s (dir %s):" % (logging_tools.get_plural("package", len(missing_in)),
                                                  host,
                                                  dir)
            if opt_dict["detailed_list"]:
                print "\n".join(missing_in)
            else:
                print " ".join(missing_in)


if __name__ == "__main__":
    main()
