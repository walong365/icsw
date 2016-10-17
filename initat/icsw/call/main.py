#
# -*- coding: utf-8 -*-
#
# Copyright (C) 2001-2010,2013-2015 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw-server
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
""" call commands for given subsystems """

from __future__ import print_function, unicode_literals

import sys
import time

from initat.tools import logging_tools


def call_cs(cmd, options):
    from initat.cluster_server import main
    return main.main(["-c"] + [cmd] + options.args[1:])


def main(options):
    _cmd = options.args[0]
    print(
        "Calling command '{}' for subsystem '{}'".format(
            _cmd,
            options.subsys
        )
    )
    print()
    s_time = time.time()
    ret_code = {
        # "host-monitoring": call_hm_help,
        "cluster-server": call_cs,
    }[options.subsys](_cmd, options)
    e_time = time.time()
    print()
    print(
        "Call took {}, returned {}".format(
            logging_tools.get_diff_time_str(e_time - s_time),
            str(ret_code)
        )
    )
    sys.exit(ret_code)
