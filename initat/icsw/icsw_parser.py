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

""" parser for icsw command """

import argparse
from .service.service_parser import Parser as ServiceParser
from .logwatch.logwatch_parser import Parser as LogwatchParser
from .license.license_parser import Parser as LicenseParser
try:
    from .setup.parser import Parser as SetupParser
except ImportError:
    SetupParser = None


class ICSWParser(object):
    def __init__(self):
        self._parser = argparse.ArgumentParser(prog="icsw")
        self._parser.add_argument("--logger", type=str, default="stdout", choices=["stdout", "logserver"], help="choose logging facility")
        sub_parser = self._parser.add_subparsers(help="sub-command help")
        ServiceParser().link(sub_parser)
        LogwatchParser().link(sub_parser)
        LicenseParser().link(sub_parser)
        if SetupParser is not None:
            SetupParser(sub_parser)

    def parse_args(self):
        opt_ns = self._parser.parse_args()
        return opt_ns
