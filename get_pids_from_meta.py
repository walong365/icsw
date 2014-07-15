#!/usr/bin/python-init -Otu
#
# this file is part of python-modules-base
#
# Copyright (C) 2013-2014 Andreas Lang-Nevyjel init.at
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

""" output the pids from a given meta file as strings """

import process_tools
import sys

def main():
    if len(sys.argv) > 1:
        _msi = process_tools.meta_server_info(sys.argv[1])
        print(" ".join(["{:d}".format(_pid) for _pid in sorted(set(_msi.get_pids()))]))
        sys.exit(0)
    else:
        print("no meta file given")
        sys.exit(1)

if __name__ == "__main__":
    main()

