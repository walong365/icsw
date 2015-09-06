#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001-2006,2013-2015 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file belongs to cluster-backbone-tools
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

import sys
import time

from initat.tools import logging_tools, uuid_tools


def log_com(a, b):
    print "[{:>6s}] {}".format(logging_tools.get_log_level_str(b), a)


def restart_services():
    from initat.icsw.service import transition, container, instance
    srv_list = ["host-monitoring", "cluster-server"]
    print(
        "restarting {}: {}".format(
            logging_tools.get_plural("service", len(srv_list)),
            ", ".join(srv_list),
        )
    )
    cur_c = container.ServiceContainer(log_com)
    cur_t = transition.ServiceTransition(
        "restart",
        srv_list,
        cur_c,
        instance.InstanceXML(log_com).tree,
        log_com,
    )
    while True:
        _left = cur_t.step(cur_c)
        if _left:
            time.sleep(1)
        else:
            break
    print("done")


def main(opt_ns):
    cur_uuid = uuid_tools.get_uuid()
    new_uuid = uuid_tools.get_uuid(renew=True)
    _check_uuid = uuid_tools.get_uuid()
    if _check_uuid == cur_uuid:
        print(" *** error changing uuid from {} to {}".format(cur_uuid, new_uuid))
        sys.exit(-1)
    else:
        print("changed uuid from {} to {}".format(cur_uuid, new_uuid))
        restart_services()
        sys.exit(0)
