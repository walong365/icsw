#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001-2009,2011-2015 Andreas Lang-Nevyjel, init.at
#
# this file is part of python-modules-base
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

""" checks installed servers on system """

import os

import time
import datetime
import logging_tools

from . import instance
from . import container
from . import logging
from . import transition


def show_form_list(form_list):
    # color strings (green / blue / red / normal)
    d_map = {
        "ok": "\033[1;32m{}\033[m\017",
        "warning": "\033[1;34m{}\033[m\017",
        "critical": "\033[1;31m{}\033[m\017",
    }
    print(datetime.datetime.now().strftime("%a, %d. %b %Y %d %H:%M:%S"))
    form_list.display_attribute_map = d_map
    print(unicode(form_list))


def main(opt_ns):
    log_com = logging.get_logger(opt_ns.logger)
    if os.getuid():
        log_com("Not running as root, information may be incomplete, disabling display of memory", logging_tools.LOG_LEVEL_ERROR)
        opt_ns.memory = False
    inst_xml = instance.InstanceXML(log_com).tree
    cur_c = container.ServiceContainer(log_com)

    if opt_ns.subcom == "status":
        if opt_ns.interactive:
            from . import console
            console.main(opt_ns, cur_c, inst_xml)
        else:
            cur_c.check_system(opt_ns, inst_xml)
            form_list = cur_c.instance_to_form_list(opt_ns, inst_xml)
            show_form_list(form_list)
    elif opt_ns.subcom in ["start", "stop", "restart", "debug"]:
        cur_t = transition.ServiceTransition(opt_ns, cur_c, inst_xml, log_com)
        while True:
            _left = cur_t.step(cur_c)
            if _left:
                time.sleep(1)
            else:
                break
