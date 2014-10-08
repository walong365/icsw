#!/usr/bin/python-init -Otu
#
# this file is part of python-modules-base
#
# Copyright (C) 2014 Andreas Lang-Nevyjel init.at
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

import argparse
import os
import process_tools
import sys

META_DIR = "/var/lib/meta-server"


def main():
    my_parser = argparse.ArgumentParser()
    my_parser.add_argument("--name", type=str, default="", help="process name to check against [%(default)s]")
    my_parser.add_argument("--meta", type=str, required=True, help="meta file to use (relative or absolute, when relative search in {} [%(defaults)s]".format(META_DIR))
    my_parser.add_argument("--signal", type=int, default=0, help="signal to send to the processes [%(default)s]")
    args = my_parser.parse_args()
    _msi = process_tools.meta_server_info(args.meta if args.meta.startswith("/") else os.path.join(META_DIR, args.meta))
    if _msi.parsed:
        _pids = sorted(set(_msi.get_pids(process_name=args.name or None)))
        if args.signal:
            for _pid in _pids:
                os.kill(_pid, args.signal)
        else:
            print(" ".join(["{:d}".format(_pid) for _pid in _pids]))
        sys.exit(0)
    else:
        print("MSI file is not valid")
        sys.exit(1)

if __name__ == "__main__":
    main()
