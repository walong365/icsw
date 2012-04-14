#!/usr/bin/python-init -Otu
#
# Copyright (c) 2007,2008,2009,2012 Andreas Lang-Nevyjel, lang-nevyjel@init.at
#
# this file is part of cbc-tools
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License
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
import commands
import os

def get_intel_path(src_path, **args):
    for rel_path in ["intel64", "."]:
        if os.path.isdir("%s/%s" % (src_path,
                                    rel_path)):
            break
    return os.path.normpath("%s/%s" % (src_path,
                                       rel_path))

def get_add_paths_for_intel(intel_path):
    add_path_dict = {"LD_LIBRARY_PATH": [get_intel_path("%s/lib" % (intel_path))],
                     "PATH"           : [get_intel_path("%s/bin" % (intel_path))]}
    return add_path_dict

def get_short_version_for_intel(intel_path, command):
    stat, icom_out = commands.getstatusoutput("%s/%s -V" % (get_intel_path("%s/bin" % (intel_path)),
                                                            command))
    if stat:
        raise ValueError, "Cannot get Version from %s (%d): %s" % (command,
                                                                   stat,
                                                                   icom_out)
    icom_out_lines = icom_out.split("\n")
    first_line = icom_out_lines[0]
    small_version = first_line.split("_")[-1]
    if small_version.count(" "):
        # try to extract only last part of first line
        sv_parts = small_version.split()
        if len(sv_parts) > 5:
            # line splits
            if sv_parts[-2].lower() == "build":
                small_version = sv_parts[-3]
            else:
                small_version = sv_parts[-1]
        else:
            small_version = first_line.split()[-1]
    if small_version.count(" "):
        print "Small_version '%s' contains spaces (from first line '%s' of %s -V, exiting" % (small_version,
                                                                                              first_line,
                                                                                              command)
        small_version = ""
    else:
        small_parts = small_version.split(".")
        if len(small_parts) == 2 and small_version in ["11.1"]:
            # try to add missing part from path
            take_part = False
            for path_part in intel_path.split("/"):
                if take_part:
                    take_part = False
                    small_version ="%s.%s" % (small_version,
                                              path_part)
                elif path_part == small_version:
                    take_part = True
    return icom_out_lines, small_version

if __name__ == "__main__":
    print "Loadable module, exiting ..."
    sys.exit(-1)
    