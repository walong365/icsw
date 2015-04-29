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
import datetime
import time

from . import instance
from . import container
from ..dummy_logger import stdout_logger as log_com


def show_form_list(form_list, _iter):
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
    if os.getuid():
        print("Not running as root, information may be incomplete, disabling display of memory")
        opt_ns.memory = False
    inst_xml = instance.InstanceXML(log_com).tree
    cur_c = container.ServiceContainer(log_com)

    if opt_ns.subcom == "status":
        cur_c.check_system(opt_ns, inst_xml)
        _iter = 0
        while True:
            try:
                form_list = cur_c.instance_to_form_list(opt_ns, inst_xml)
                show_form_list(form_list, _iter)
                if opt_ns.every:
                    time.sleep(opt_ns.every)
                    cur_c.check_system(opt_ns, inst_xml)
                    _iter += 1
                else:
                    break
            except KeyboardInterrupt:
                print("exiting...")
                break
    elif opt_ns.subcom in ["start", "stop", "restart", "debug"]:
        cur_c.actions(opt_ns, inst_xml)
