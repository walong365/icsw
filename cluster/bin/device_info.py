#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001,2002,2003,2004,2005,2006 Andreas Lang, init.at
#
# Send feedback to: <lang@init.at>
# 
# This file belongs to cluster-backbone
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
import mysql_tools
import logging_tools
import getopt
import os
import os.path
import types

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], "h", ["help"])
    except:
        print "Error parsing commandline: %s" % (" ".join(sys.argv[:]))
        sys.exit(1)
    for opt, arg in opts:
        if opt in ["-h", "--help"]:
            print "Usage: %s [ OPTIONS ] devices" % (os.path.basename(sys.argv[0]))
            print " -h, --help    this help"
            print " devices       list of devices to query"
            sys.exit(0)
    if not args:
        print "Need some devicenames"
        sys.exit(0)
    devs = [x.strip() for x in args]
    devs.sort()
    print "Trying to get information about %s: %s" % (logging_tools.get_plural("device", len(devs)),
                                                      logging_tools.compress_list(devs))
    db_con = mysql_tools.db_con()
    db_con.dc.execute("SELECT d.name, d.device_idx FROM device d WHERE (%s)" % (" OR ".join(["d.name LIKE('%s%%')" % (x) for x in devs])))
    dev_dict = dict([(x["name"], x) for x in db_con.dc.fetchall()])
    devs_found = dev_dict.keys()
    devs_missing = [x for x in devs if x not in devs_found]
    if devs_missing:
        devs_missing.sort()
        print "%s not found (or wildcard?): %s" % (logging_tools.get_plural("device", len(devs_missing)),
                                                   logging_tools.compress_list(devs_missing))
    if devs_found:
        devs_found.sort()
        print "%s found: %s" % (logging_tools.get_plural("device", len(devs_found)),
                                logging_tools.compress_list(devs_found))
    for dev in devs_found:
        stuff = dev_dict[dev]
        db_con.dc.execute("SELECT n.devname, n.macadr, i.ip, nw.identifier, nt.identifier AS ntident FROM netdevice n INNER JOIN network nw INNER JOIN network_type nt LEFT JOIN netip i ON i.netdevice=n.netdevice_idx WHERE n.device=%d AND i.network=nw.network_idx AND nw.network_type=nt.network_type_idx ORDER BY n.devname, i.ip" % (stuff["device_idx"]))
        nd_dict = {}
        for x in db_con.dc.fetchall():
            nd_dict.setdefault(x["devname"], {"macadr" : x["macadr"], "ip_list" : []})
            nd_dict[x["devname"]]["ip_list"] += ["%15s (%8s, %s)" % (x["ip"], x["identifier"], x["ntident"])]
        nd_devs = nd_dict.keys()
        nd_devs.sort()
        db_con.dc.execute("SELECT d.name, o.outlet, o.state, o.slave_info FROM msoutlet o, device d WHERE d.device_idx=o.device AND o.slave_device=%d ORDER BY d.name, o.outlet" % (stuff["device_idx"]))
        apc_list = [x for x in db_con.dc.fetchall()]
        print "%-30s (idx %d), %s, %s" % (stuff["name"], stuff["device_idx"],
                                          logging_tools.get_plural("netdevice", len(nd_devs)),
                                          logging_tools.get_plural("APC connection", len(apc_list)))
        for nd_dev in nd_devs:
            nd_stuff = nd_dict[nd_dev]
            print "  netdev %-10s,  macadr %17s, %-6s: %s" % (nd_dev, nd_stuff["macadr"],
                                                              logging_tools.get_plural("IP", len(nd_stuff["ip_list"])),
                                                              ", ".join(nd_stuff["ip_list"]))
        for apc_info in apc_list:
            print " APC %s outlet %d (%s), state is %s" % (apc_info["name"], apc_info["outlet"], apc_info["slave_info"] or "no info", apc_info["state"])
            
if __name__ == "__main__":
    main()
    
