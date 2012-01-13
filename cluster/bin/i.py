#!/usr/bin/python -Ot
#
# Copyright (C) 2001,2002,2003,2004,2005,2006 Andreas Lang, init.at
#
# Send feedback to: <lang@init.at>
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

import sys
import MySQLdb
import MySQLdb.cursors, MySQLdb.converters
import mysql_tools
import getopt
import configfile
import os
import os.path
import commands

def main():

    try:
        opts, args = getopt.getopt(sys.argv[1:], "r:i:p:")
    except:
        print "Error parsing commandline %s" % (" ".join(sys.argv[:]))
        sys.exit(-1)
    image_idx, root_dir, single_package = (0, "/", None)
    for opt, arg in opts:
        if opt == "-r":
            if os.path.isdir(arg):
                root_dir = arg
                print "Setting root-directory to %s" % (root_dir)
            else:
                print "Error: '%s' is not a valid directory" % (arg)
                sys.exit(-1)
        if opt == "-i":
            try:
                image_idx = int(arg)
            except:
                print "Error parsing image index %s" % (arg)
                sys.exit(-1)
        if opt == "-p":
            if os.path.isfile(arg):
                single_package = arg
                print "Checking single-package %s" % (single_package)
            else:
                print "Cannot find single package path %s" % (arg)
                sys.exit(-1)
    form_str = "--queryformat=\"n%{NAME}\\nv%{VERSION}\\nr%{RELEASE}\\na%{ARCH}\\ns%{SIZE}\\nS%{SUMMARY}\\ni%{INSTALLTIME}\\nd%{DISTRIBUTION}\\nV%{VENDOR}\\ng%{GROUP}\\nt%{BUILDTIME}\\nh%{BUILDHOST}\\np%{PACKAGER}\\n\""
    if single_package:
        query_str = "rpm -qp %s %s" % (single_package, form_str)
    else:
        query_str = "chroot %s rpm -qa %s" % (root_dir, form_str)
    stat, p_list = commands.getstatusoutput(query_str)
    if stat:
        print "Error while executing '%s' [%d]: %s" % (query_str, stat, str(p_list))
    else:
        glob_dict = {}
        dbcon = mysql_tools.db_con()
        # read architecture/vendor/distribution tables
        for what in ["architecture", "vendor", "distribution"]:
            stuff = {}
            dbcon.dc.execute("SELECT * FROM %s" % (what))
            for x in dbcon.dc.fetchall():
                stuff[x[what]] = x
            glob_dict[what] = stuff
        #print ":", architecture, vendor, distribution
        rel_dict = {"n" : ("name"        , "s", 1), "r" : ("release", "s", 1), "a" : ("architecture", "s", 2), "v" : ("version"  , "s", 1), "s" : ("size"        , "i", 1), 
                    "S" : ("summary"     , "s", 1), "g" : ("pgroup" , "s", 1), "t" : ("buildtime"   , "i", 1), "h" : ("buildhost", "s", 1), "p" : ("packager"    , "s", 1), 
                    "d" : ("distribution", "s", 2), "V" : ("vendor" , "s", 2), "i" : ("install_time", "i", 0)}
        packages = {}
        # parse p_list
        num_p = 0
        act_p = None
        for pfix, p_str in [(y[0], y[1:].strip()) for y in [x.strip() for x in p_list.split("\n")] if len(y[1:].strip())]:
            #print pfix, p_str
            if pfix == "n":
                act_p = {"name":p_str, "write_db_entry":1}
            else:
                if act_p:
                    if pfix in rel_dict.keys():
                        dname, d_type, p_entry = rel_dict[pfix]
                        if d_type == "s":
                            act_p[dname] = p_str
                        else:
                            if p_str == "(none)":
                                p_str = "0"
                            try:
                                act_p[dname] = int(p_str)
                            except:
                                act_p[dname] = 0
                                print "Error converting %s to int (%s), setting to %d" % (p_str, dname, act_p[dname])
                    else:
                        print "Error: postfix %s not in dictionary (%s)" % (pfix, ", ".join(rel_dict.keys()))
                    if pfix == "p":
                        num_p += 1
                        # check for new architecture/vendor/distribution
                        for what in ["architecture", "vendor", "distribution"]:
                            if not glob_dict[what].has_key(act_p[what]):
                                sql_str, sql_tuple = ("INSERT INTO %s VALUES(0, %%s, null)" % (what), act_p[what])
                                dbcon.dc.execute(sql_str, sql_tuple)
                                dbcon.dc.execute("SELECT * FROM %s WHERE BINARY %s=%%s" % (what, what), (act_p[what]))
                                new_w = dbcon.dc.fetchone()
                                glob_dict[what][new_w[what]] = new_w
                                print "New %s %s" % (what, act_p[what])
                        packages.setdefault(act_p["name"], []).append(act_p)
                        act_p = None
                else:
                    print "Error while parsing (act_p is None for type %s [%s])" % (pfix, p_str)
        print "Found %d valid packages" % (num_p)
        # dictionary package_idx=>package
        p_idx_dict = {}
        dbcon.dc.execute("SELECT p.package_idx, p.name, p.version, p.release, d.distribution, a.architecture, p.buildhost, p.buildtime, p.packager FROM package p, distribution d, architecture a WHERE p.distribution=d.distribution_idx AND p.architecture=a.architecture_idx")
        for db_pack in dbcon.dc.fetchall():
            if packages.has_key(db_pack["name"]):
                for pack in packages[db_pack["name"]]:
                    if pack["version"] == db_pack["version"] and pack["release"] == db_pack["release"] and pack["distribution"] == db_pack["distribution"] and pack["architecture"] == db_pack["architecture"]:
                        #print "Has "+db_pack["name"]
                        pack["package_idx"] = db_pack["package_idx"]
                        p_idx_dict[db_pack["package_idx"]] = pack
                        if pack["buildhost"] == db_pack["buildhost"] and pack["buildtime"] == db_pack["buildtime"] and pack["packager"] == db_pack["packager"]:
                            pack["write_db_entry"] = 0
                        else:
                            # modify existing package
                            pass
        for p_name, pack in packages.iteritems():
            for pack in [x for x in packages[p_name] if x["write_db_entry"]]:
                if pack.has_key("package_idx"):
                    # modify
                    sql_str, sql_tuple = ("UPDATE package SET buildtime=%s, buildhost=%s, packager=%s WHERE package_idx=%s", (pack["buildtime"], 
                                                                                                                              pack["buildhost"], 
                                                                                                                              pack["packager"],
                                                                                                                              pack["package_idx"]))
                    dbcon.dc.execute(sql_str)
                else:
                    sql_a, tuple_f = ([], [])
                    for key in rel_dict.keys():
                        name, e_type, p_entry = rel_dict[key]
                        if p_entry:
                            sql_a.append(name == "release" and "`%s`=%%s" % (name) or "%s=%%s" % (name))
                            if e_type == "s":
                                if p_entry == 1:
                                    tuple_f.append(pack[name])
                                else:
                                    tuple_f.append(glob_dict[name][pack[name]][name+"_idx"])
                            else:
                                tuple_f.append(pack[name])
                    sql_str = "INSERT INTO package SET %s" % (", ".join(sql_a))
                    dbcon.dc.execute(sql_str, tuple_f)
                    pack["package_idx"] = dbcon.dc.insert_id()
                    p_idx_dict[pack["package_idx"]] = pack
                pack["write_db_entry"] = 0
        if image_idx:
            dbcon.dc.execute("SELECT * FROM image i WHERE i.image_idx=%d" % (image_idx))
            im_info = dbcon.dc.fetchone()
            if im_info:
                p_idx_list = []
                # build package_idx list
                for p_name in packages.keys():
                    p_idx_list += [x["package_idx"] for x in packages[p_name]]
                # get pi_connection
                dbcon.dc.execute("SELECT pi.pi_connection_idx, pi.package, pi.install_time FROM pi_connection pi WHERE pi.image=%d" % (image_idx))
                # which packages to drop
                drop_list = []
                # which packages to insert
                add_list = p_idx_list
                # which packages to refresh (new install_time)
                refresh_list = []
                for db_i in dbcon.dc.fetchall():
                    if db_i["package"] in add_list:
                        add_list.remove(db_i["package"])
                        if db_i["install_time"] != p_idx_dict[db_i["package"]]["install_time"]:
                            refresh_list += [(db_i["pi_connection_idx"], db_i["package"])]
                    else:
                        drop_list += [db_i["pi_connection_idx"]]
                for ws, wl in [("Added", add_list), ("Deleted", drop_list), ("Refreshed", [x[0] for x in refresh_list])]:
                    print "%10s  (%4d) : %s" % (ws, len(wl), ", ".join(["%d" % (x) for x in wl]))
                if add_list:
                    for add_idx in add_list:
                        sql_str = "INSERT INTO pi_connection VALUES(0, %d, %d, %d, null)" % (add_idx, image_idx, p_idx_dict[add_idx]["install_time"])
                        dbcon.dc.execute(sql_str)
                if drop_list:
                    sql_str = "DELETE FROM pi_connection WHERE (%s)" % (" OR ".join(["pi_connection_idx=%d" % (x) for x in drop_list]))
                    dbcon.dc.execute(sql_str)
                if refresh_list:
                    for pi_c_idx, p_idx in refresh_list:
                        sql_str = "UPDATE pi_connection SET install_time=%d WHERE pi_connection_idx=%d" % (p_idx_dict[p_idx]["install_time"], pi_c_idx)
                        dbcon.dc.execute(sql_str)
            else:
                print "No image found with image_index %d" % (image_idx)
        if single_package:
            print "pidx %d" % (packages.values()[0][0]["package_idx"])
            print "pname %s" % (packages.values()[0][0]["name"])
        #print packages
  
if __name__ == "__main__":
    main()
    
