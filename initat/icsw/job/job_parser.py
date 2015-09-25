#!/usr/bin/python-init -OtB
# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 Andreas Lang-Nevyjel (lang-nevyjel@init.at)
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of logging-server
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
""" job helper functions """

import argparse
import os
import re

from initat.tools import process_tools


class Parser(object):
    def link(self, sub_parser, **kwargs):
        return self._add_job_parser(sub_parser)

    def _add_job_parser(self, sub_parser):
        _mach_name = process_tools.get_machine_name(short=True)
        parser = sub_parser.add_parser("job", help="job helper commands")
        parser.set_defaults(subcom="job", execute=self._execute)
        parser.add_argument("--job-id", default="", type=str, help="job ID (gets evaluated automatically via environ) [%(default)s]")
        parser.add_argument("--task-id", default=0, type=int, help="task ID (gets evaluated automatically via environ) [%(default)d]")
        parser.add_argument("--server-address", default="", type=str, help="RMS server address [%(default)s]")
        parser.add_argument("--server-port", default=8009, type=int, help="RMS server address [%(default)d]")
        parser.add_argument("--mode", default="info", type=str, choices=["info", "setvar"], help="job subcommand [%(default)s]")
        parser.add_argument("--name", default="", type=str, help="variable name [%(default)s]")
        parser.add_argument("--value", default="", type=str, help="variable value [%(default)s]")
        parser.add_argument("--unit", default="", type=str, help="variable unit [%(default)s]")
        return parser

    def _execute(self, opt_ns):
        from .main import main
        main(opt_ns)
