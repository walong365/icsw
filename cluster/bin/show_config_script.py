#!/usr/bin/python-init -Otu
#
# Copyright (C) 2001-2006,2014 Andreas Lang-Nevyjel
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

""" show config script for simple use in CSW """

import argparse
import datetime
import os
import process_tools

def main():
    my_parser = argparse.ArgumentParser()
    my_parser.add_argument("-s", dest="full_strip", default=False, action="store_true", help="strip all empty lines from file [%(default)s]")
    my_parser.add_argument("-c", dest="remove_hashes", default=False, action="store_true", help="remove all lines starting with hashes from file [%(default)s]")
    my_parser.add_argument("--full-path", dest="full_path", default=False, action="store_true", help="use full path for file objects [%(default)s]")
    my_parser.add_argument("files", nargs="+", help="files to operate on")
    options = my_parser.parse_args()
    for f_name in options.files:
        _obj_name = f_name if options.full_path else os.path.basename(f_name)
        for _rc in ["/", ".", "-"]:
            _obj_name = _obj_name.replace(_rc, "_")
        while _obj_name.startswith("_"):
            _obj_name = _obj_name[1:]
        obj_name = "%s_object" % (_obj_name)
        f_lines = [_line.rstrip() for _line in file(f_name).read().split("\n")]
        if options.full_strip:
            f_lines = [_line.strip() for _line in f_lines if _line.strip()]
        if options.remove_hashes:
            f_lines = [_line for _line in f_lines if not _line.startswith("#")]
        p_line = " " * 4
        print "# from %s (%s, host %s)" % (f_name, datetime.datetime.now(), process_tools.get_machine_name(short=False))
        print "%s = config.add_file_object('%s')" % (obj_name, f_name)
        print "%s += [\n%s]\n" % (
            obj_name,
            "".join(["%s'%s',\n" % (p_line, _line.replace("'", '"').replace("\\", "\\\\")) for _line in f_lines]))

if __name__ == "__main__":
    main()
