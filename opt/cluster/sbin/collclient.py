#!/usr/bin/python3-init -Ot
# -*- coding: utf-8 -*-
#
# Copyright (C) 2011-2017 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw-client
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
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

""" client for host-monitoring """

import os
import sys
import argparse

if not __file__.startswith("/opt/cluster"):
    _add_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    if _add_path not in sys.path:
        sys.path.insert(0, _add_path)

from initat.host_monitoring import main
from initat.icsw.service.instance import InstanceXML


def local_main():
    my_parser = argparse.ArgumentParser()
    my_parser.add_argument(
        "-i",
        dest="IDENTITY_STRING",
        type=str,
        default="collclient",
        help="identity string [%(default)s]"
    )
    my_parser.add_argument(
        "--timeout",
        dest="TIMEOUT",
        default=10,
        type=int,
        help="set timeout [%(default)d]"
    )
    my_parser.add_argument(
        "-p",
        dest="COMMAND_PORT",
        default=InstanceXML(quiet=True).get_port_dict("host-monitoring", command=True),
        type=int,
        help="set comport [%(default)d]"
    )
    my_parser.add_argument(
        "--host",
        dest="HOST",
        type=str,
        default="localhost",
        help="set target host [%(default)s]"
    )
    my_parser.add_argument(
        dest="ARGUMENTS",
        nargs="+",
        help="additional arguments"
    )

    sys.exit(main.main(options=my_parser.parse_args()))

if __name__ == "__main__":
    local_main()
