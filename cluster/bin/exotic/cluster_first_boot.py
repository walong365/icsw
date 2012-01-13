#!/usr/bin/python -Otu
#
# Copyright (C) 2001,2002,2003,2004,2005,2006 Andreas Lang
#
# this file is part of cluster-backbone
#
# Send feedback to: <lang@init.at>
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
import os
import mysql_tools
import logging_tools
import pprint
import time
import msock
import server_command

SQL_ACCESS = "cluster_full_access"
WAIT_TIME = 60 * 1

def mother_apc_com(apc_name, outlet_num, outlet_com):
    command = server_command.server_command(command="apc_com")
    command.set_nodes([apc_name])
    command.set_node_command(apc_name, "c%d=%d" % (outlet_num, outlet_com))
    errnum, data = msock.single_tcp_connection(("localhost", 8001, command), None, 10, 1)
    if errnum:
        print "An error occured (%d): %s" % (errnum, data)
        sys.exit(-1)
    try:
        server_reply = server_command.server_reply(data)
    except ValueError:
        print "Error: got no valid server reply, exiting..."
        sys.exit(-1)
    print "  result: ", server_reply.get_state_and_result()
    
def main():
    db_con = mysql_tools.dbcon_container(with_logging=False)
    try:
        dc = db_con.get_connection(SQL_ACCESS)
    except MySQLdb.OperationalError:
        print "cannot init SQL_cursor, exiting..."
        sys.exit(-1)
    print "SQL_cursor ok, getting device list"
    dc.execute("SELECT DISTINCT d.name, d.device_idx FROM device d INNER JOIN device_type dt INNER JOIN new_config c INNER JOIN device_config dc INNER JOIN device_group dg LEFT JOIN device d2 ON d2.device_idx=dg.device WHERE dg.device_group_idx=d.device_group AND dt.identifier='H' AND dt.device_type_idx=d.device_type AND dc.new_config=c.new_config_idx AND (d2.device_idx=dc.device OR d.device_idx=dc.device) AND c.name='node' ORDER BY dg.name, d.name")
    node_dict = dict([(db_rec["name"], db_rec["device_idx"]) for db_rec in dc.fetchall()])
    all_nodes = [x for x in node_dict.keys() if not x.startswith("big")]
    all_nodes.sort()
    if not all_nodes:
        print "found no nodes, exiting..."
        sys.exit(-1)
    print "found %s: %s" % (logging_tools.get_plural("node", len(all_nodes)),
                            logging_tools.compress_list(all_nodes))
    print "disabling greedy_mode on all nodes"
    sql_str = "UPDATE device SET dhcp_mac=0 WHERE (%s)" % (" OR ".join(["device_idx=%d" % (x) for x in node_dict.values()]))
    dc.execute(sql_str)
    for node_name in all_nodes:
        print "Node %s ..." % (node_name)
        dev_idx = node_dict[node_name]
        dc.execute("SELECT d.dhcp_mac, n.macadr FROM device d, netdevice n WHERE n.netdevice_idx=d.bootnetdevice AND d.device_idx=%d" % (dev_idx))
        res = dc.fetchone()
        if int(res["macadr"].replace(":", ""), 16):
            print "  Macaddress already set to %s, skipping" % (res["macadr"])
            continue
        dc.execute("SELECT d.device_idx, d.name, o.outlet FROM msoutlet o, device d WHERE d.device_idx=o.device AND o.slave_device=%d" % (dev_idx))
        outlets = dc.fetchall()
        if not outlets:
            print "  not connected to an APC, skipping"
            continue
        print "  connected to %s: %s" % (logging_tools.get_plural("APC", len(outlets)),
                                         ", ".join(["%s/outlet%d" % (x["name"], x["outlet"]) for x in outlets]))
        outlet = outlets[0]
        print "  turning on first outlet (%d) on %s ..." % (outlet["outlet"], outlet["name"])
        mother_apc_com(outlet["name"], outlet["outlet"], 1)
        print "  setting device greedy"
        dc.execute("UPDATE device SET dhcp_mac=1 WHERE device_idx=%d" % (dev_idx))
        print "  waiting for %s" % (logging_tools.get_plural("second", WAIT_TIME))
        start_time = time.time()
        act_time = start_time
        while abs(act_time - start_time) < WAIT_TIME:
            dc.execute("SELECT d.dhcp_mac FROM device d WHERE d.device_idx=%d" % (dev_idx))
            act_dhcp_state = dc.fetchone()["dhcp_mac"]
            print "(%d, %d to go)" % (act_dhcp_state, abs(abs(act_time - start_time) - WAIT_TIME)),
            if not act_dhcp_state:
                break
            time.sleep(10)
            act_time = time.time()
        if act_dhcp_state:
            print "** not successfull, turning machine off and disabling greedy mode"
            dc.execute("UPDATE device SET dhcp_mac=0 WHERE device_idx=%d" % (dev_idx))
        else:
            print "  successfull, turning machine off"
        mother_apc_com(outlet["name"], outlet["outlet"], 2)
    dc.release()

if __name__ == "__main__":
    main()
    
