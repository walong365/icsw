#!/usr/bin/python-init -Ot
#
# -*- coding: utf-8 -*-
#
# Copyright (C) 2001-2010,2013-2015 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of cluster-backbone
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
""" job subcommands """

import commands
import datetime
import os
import sys
import time

from initat.tools import logging_tools, process_tools


def _parse_environ(opts):
    for _src_file, _target in [
        ("/etc/sge_server", "server_address"),
    ]:
        if not getattr(opts, _target) and os.path.exists(_src_file):
            setattr(opts, _target, file(_src_file, "r").read().strip())
    if not opts.job_id:
        if "JOB_ID" in os.environ:
            opts.job_id = os.environ["JOB_ID"]
    if not opts.task_id:
        if "SGE_TASK_ID" in os.environ:
            try:
                opts.task_id = int(os.environ["SGE_TASK_ID"])
            except:
                opts.task_id = 0
    if opts.task_id:
        opts.full_job_id = "{}.{:d}".format(opts.job_id, opts.task_id)
    else:
        opts.full_job_id = opts.job_id


def show_info(opts):
    print("Settings for the job subcommand:")
    print("              JOB_ID: {}".format(opts.full_job_id or "---"))
    print("  RMS_SERVER_ADDRESS: {}".format(opts.server_address or "---"))
    print("     RMS_SERVER_PORT: {:d}".format(opts.server_port or 0))


def main(options):
    _parse_environ(options)
    if options.mode == "info":
        show_info(options)
    elif options.mode == "setvar":
        set_variable(options)
    else:
        print("Unknown job mode '{}'".format(opts.mode))
