#!/usr/bin/python-init -Ot
#
# Copyright (C) 2015 Andreas Lang-Nevyjel, init.at
#
# this file is part of icsw-client
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

""" entry point for the icsw command for NOCTUA, CORVUS and NESTOR """

import os
import sys


def main():
    from initat.icsw.icsw_parser import ICSWParser
    options = ICSWParser().parse_args()
    options.execute(options)

if __name__ == "__main__":
    if __package__ is None:
        _add_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        if _add_path not in sys.path:
            sys.path.insert(0, _add_path)
    main()
