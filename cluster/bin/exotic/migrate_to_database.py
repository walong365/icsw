#!/usr/bin/python -Ot
# -*- coding: iso-8859-1 -*-
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
import nis
import mysql_tools

HOME_START = "/fs/home"

def main():
    db_con = mysql_tools.db_con()
    # find export-entry
    db_con.dc.execute("SELECT d.name, d.device_idx, dc.device_config_idx, c.name AS cname, cs.name AS csname, cs.value, c.new_config_idx FROM device d, device_config dc, new_config c, config_str cs, device_type dt WHERE dt.device_type_idx=d.device_type AND dt.identifier='H' AND dc.device=d.device_idx AND dc.new_config=c.new_config_idx AND cs.new_config=c.new_config_idx AND (cs.name LIKE('%export%'))")
    export_idx = 0
    for x in db_con.dc.fetchall():
        if x["csname"] == "homeexport":
            export_idx = x["new_config_idx"]
    if not export_idx:
        print "Found no valid export_idx"
        sys.exit(-1)
    
    db_con.dc.execute("SELECT * FROM ggroup")
    active_groups = dict([(x["ggroupname"], x) for x in db_con.dc.fetchall()])
    db_con.dc.execute("SELECT * FROM user")
    active_users = dict([(x["login"], x) for x in db_con.dc.fetchall()])
    yp_group = nis.cat("group")
    g_names = yp_group.keys()
    g_names.sort()
    yp_passwd = nis.cat("passwd")
    u_names = yp_passwd.keys()
    u_names.sort()
    if [x for x in active_groups.keys() if x in g_names]:
        print "Some groups found in yp already defined in DB : %s" % (", ".join([x for x in active_groups.keys() if x in g_names]))
        sys.exit(-1)
    if [x for x in active_users.keys() if x in u_names]:
        print "Some users found in yp already defined in DB : %s" % (", ".join([x for x in active_users.keys() if x in u_names]))
        sys.exit(-1)
    new_g_dict = {}
    gid_lut = {}
    for g_name in g_names:
        g_stuff = yp_group[g_name].split(":")
        gname, g_passwd, gid, add_users = g_stuff
        if g_name != gname:
            print "Error for group %s (g_name != gname)" % (g_name)
            sys.exit(-1)
        gid = int(gid)
        add_users = add_users.split(",")
        new_g_dict[g_name] = {"add_users" : add_users,
                              "gid"       : gid}
        print "Insert group %s" % (g_name)
        sql_str, sql_tuple = ("INSERT INTO ggroup SET active=1,ggroupname=%s,gid=%s,homestart=%s", (g_name,
                                                                                                    gid,
                                                                                                    HOME_START))
        db_con.dc.execute(sql_str, sql_tuple)
        new_g_dict[g_name]["db_idx"] = db_con.dc.insert_id()
        gid_lut[gid] = new_g_dict[g_name]["db_idx"]
    for u_name in u_names:
        u_stuff = yp_passwd[u_name].split(":")
        uname, u_passwd, uid, gid, u_info, u_home, u_shell = u_stuff
        if u_name != uname:
            print "Error for user %s (u_name != uname)" % (u_name)
            sys.exit(-1)
        uid = int(uid)
        gid = int(gid)
        sql_str = "INSERT INTO user SET active=1, login=%s, uid=%s, ggroup=%s, export=%s, home=%s, scratch=%s, shell=%s, password=%s, uservname=%s"
        if gid_lut.has_key(gid):
            print "Insert user %s" % (u_name)
            db_con.dc.execute(sql_str, (u_name,
                                        id,
                                        gid_lut[gid],
                                        export_idx,
                                        u_name,
                                        u_name,
                                        u_shell,
                                        u_passwd,
                                        u_info))
        else:
            print "No group found for user %s (gid=%d)" % (u_name, gid)
            
if __name__ == "__main__":
    main()
    
