#!/usr/bin/python-init -Ot
#
# Copyright (C) 2008,2009 Andreas Lang-Nevyjel, init.at
#
# this file is part of nagios-config-server
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
""" special task for configuring network """

import sys
import pprint
import re
import logging_tools
import pyipc
import struct
import os
import process_tools

def handle(s_check, host, dc, build_proc, valid_ip, **kwargs):
    sc_array = []
    eth_check = re.match(".*ethtool.*", s_check["command_name"])
    build_proc.mach_log("Starting special net, eth_check is %s" % ("on" if eth_check else "off"))
    # never check duplex and stuff for a loopback-device
    if eth_check:
        if host["xen_guest"]:
            # no ethtool_checks for xen_guests
            net_check_sql_str = "(0)"
        else:
            net_check_sql_str = "(ns.check_via_ethtool=1 AND n.devname != 'lo')"
    else:
        if host["xen_guest"]:
            # no ethtool_checks for xen_guests
            net_check_sql_str = "(1)"
        else:
            net_check_sql_str = "(ns.check_via_ethtool=0 OR n.devname = 'lo')"
    dc.execute("SELECT n.devname, n.speed, ns.speed_bps, n.description, ns.full_duplex FROM netdevice n, netdevice_speed ns WHERE ns.netdevice_speed_idx=n.netdevice_speed AND n.device=%d AND %s" % (host["device_idx"],
                                                                                                                                                                                                      net_check_sql_str))
    all_net_devs = [x for x in dc.fetchall() if not re.match("^.*:\S+$", x["devname"])]
    for net_dev in all_net_devs:
        name_with_descr = "%s%s" % (net_dev["devname"],
                                    " (%s)" % (net_dev["description"]) if net_dev["description"] else "")
        eth_opts = []
        if eth_check:
            eth_opts.extend([net_dev["full_duplex"] and "full" or "half", "%d" % (net_dev["speed_bps"])])
        eth_opts.extend(["%.0f" % (net_dev["speed_bps"] * 0.9),
                         "%.0f" % (net_dev["speed_bps"] * 0.95)])
        eth_opts.append(net_dev["devname"])
        build_proc.mach_log(" - netdevice %s with %s: %s" % (name_with_descr,
                                                             logging_tools.get_plural("option", len(eth_opts) - 1),
                                                             ", ".join(eth_opts[:-1])))
        sc_array.append((name_with_descr, eth_opts))
    return sc_array
            

if __name__ == "__main__":
    print "Loadable module, exiting"
    sys.exit(0)
    