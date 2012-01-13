#!/usr/bin/python
#
# Copyright (C) 2001,2002,2003,2004,2005,2006 Andreas Lang
#
# this file is part of cluster-backbone
#
# Send feedback to: <lang@init.at>
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

def main():
    opt_dict = {"full_strip"    : False,
                "remove_hashes" : False}
    f_names = []
    for f_name in sys.argv[1:]:
        if f_name == "-s":
            opt_dict["full_strip"] = True
        elif f_name == "-c":
            opt_dict["remove_hashes"] = True
        elif f_name == "-h":
            print "Usage: %s [ARGS] Files" % (os.path.basename(sys.argv[0]))
            print "where ARGS is one or more of"
            print " -h      this help"
            print " -s      strip files (remove empty lines)"
            print " -c      remove hashes from config files"
            sys.exit(0)
        else:
            f_names.append(f_name)
    for f_name in f_names:
        obj_name = "%s_object" % (os.path.basename(f_name.replace(".", "_").replace("-", "_")))
        f_lines = [x.rstrip() for x in file(f_name).read().split("\n") if x]
        if opt_dict["full_strip"]:
            f_lines = [x.strip() for x in f_lines]
        if opt_dict["remove_hashes"]:
            f_lines = [x for x in f_lines if not x.startswith("#")]
        print "%s = config.add_file_object('%s')" % (obj_name, f_name)
        p_line = " " * (len(obj_name) + 5)
        print "%s += [%s]" % (obj_name, (",\n%s" % (p_line)).join(["'%s'" % (x.replace("'", '"').replace("\\", "\\\\")) for x in f_lines]))

if __name__ == "__main__":
    main()
