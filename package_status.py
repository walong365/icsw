#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001-2007,2009,2014 Andreas Lang-Nevyjel lang-nevyjel@init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of package-tools
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
""" shows package status """

import getopt
import logging_tools
import os
import re
import sys
import time

SQL_ACCESS = "cluster_full_access"

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], "d:g:s:thnSGH", ["help"])
    except getopt.GetoptError, why:
        print "Error parsing commandline %s: %s" % (" ".join(sys.argv[1:]), str(why))
        sys.exit(-1)
    dev_list, group_list, show_it, state_str, show_no_ok, show_only_ea, group_by_devgroup, show_headers = ([], [], 0, "-IUD", 0, 0, 0, 1)
    for opt, arg in opts:
        if opt in ["-h", "--help"]:
            print "Usage: %s [ OPTIONS ] [ regexp-list for package-names ]" % (os.path.basename(sys.argv[0]))
            print "where OPTIONS is one of:"
            print "  -t           enable display of install date/time"
            print "  -d DEVS      comma-separated list of devices to check"
            print "  -g GROUPS    comma-separated list of groups to check"
            print "  -s STATESTR  show (and count) only packages where state (-,I, D) is in STATESTR"
            print "  -n           show (and count) only packages where the status_str does not start with 'ok '"
            print "  -S           show only nodes with effective associated packages"
            print "  -G           group by devicegroup"
            print "  -H           suppress header"
            sys.exit(0)
        if opt == "-H":
            show_headers = 0
        if opt == "-d":
            dev_list = [x.strip() for x in arg.split(",")]
        if opt == "-g":
            group_list = [x.strip() for x in arg.split(",")]
        if opt == "-t":
            show_it = 1
        if opt == "-s":
            state_str = arg
        if opt == "-n":
            show_no_ok = 1
        if opt == "-S":
            show_only_ea = 1
        if opt == "-G":
            group_by_devgroup = 1
    # print "*",args
    dbcon = mysql_tools.dbcon_container()
    dc = dbcon.get_connection(SQL_ACCESS)
    sql_str = "SELECT d.name, dg.name AS dgname FROM device d, device_group dg, device_type dt WHERE d.device_group = dg.device_group_idx AND d.device_type = dt.device_type_idx AND dt.identifier='H'"
    dc.execute(sql_str)
    dev_dict = {"" : {"num_tot"  : 0,
                     "num_p"    : 0,
                     "packages" : {}}}
    group_dict = {}
    for x in dc.fetchall():
        act_dev, act_group = (x["name"], x["dgname"])
        if (act_dev in dev_list or act_group in group_list) or (not dev_list and not group_list):
            group_dict.setdefault(act_group, []).append(act_dev)
            dev_dict[act_dev] = {"num_tot" : 0, "num_p" : 0, "packages" : {}}
    if not dev_dict:
        print "No devices found, exiting ..."
        sys.exit(1)
    sql_str = "SELECT d.name, p.name AS pname, id.install, id.del, id.upgrade, id.nodeps, id.forceflag, ip.native, id.status, UNIX_TIMESTAMP(id.install_time) AS install_time, p.version, p.release, a.architecture FROM architecture a, device d, inst_package ip, instp_device id, package p WHERE p.architecture=a.architecture_idx AND id.device=d.device_idx AND id.inst_package=ip.inst_package_idx AND ip.package=p.package_idx AND (%s)" % (" OR ".join(["d.name='%s'" % (x) for x in dev_dict.keys()]))
    dc.execute(sql_str)
    for x in dc.fetchall():
        if x["install"]:
            t_state = "I"
        elif x["del"]:
            t_state = "D"
        elif x["upgrade"]:
            t_state = "U"
        else:
            t_state = "-"
        x["t_state"] = t_state
        add_it = 1
        if t_state not in state_str:
            add_it = 0
        if show_no_ok and x["status"].lower().startswith("ok "):
            add_it = 0
        act_dev, act_pack, act_ver, act_rel, act_arch = (x["name"], x["pname"], x["version"], x["release"], x["architecture"])
        if args and add_it:
            add_it = [1 for arg in args if re.search(arg, act_pack)]
        if add_it:
            dev_dict[act_dev]["packages"].setdefault(act_pack, {}).setdefault(act_ver, {}).setdefault(act_rel, {})[act_arch] = x
            dev_dict[act_dev]["num_tot"] += 1
            dev_dict[""]["packages"].setdefault(act_pack, {}).setdefault(act_ver, {}).setdefault(act_rel, {})[act_arch] = x # .setdefault(act_arch, [])
            dev_dict[""]["num_tot"] += 1
    dc.release()
    if group_by_devgroup:
        hosts = []
        for x in sorted(group_dict.keys()):
            hosts.extend(sorted(group_dict[x]))
    else:
        hosts = sorted(dev_dict.keys())
    for host in [x for x in hosts if x and (not show_only_ea or (show_only_ea and dev_dict[x]["packages"]))]:
        packs = dev_dict[host]["packages"]
        dev_dict[host]["num_p"] = len(dev_dict[host]["packages"].keys())
        out_list = logging_tools.form_list()
        for p_name in sorted(packs.keys()):
            p_stuff = packs[p_name]
            for p_ver in sorted(p_stuff.keys()):
                for p_rel in sorted(p_stuff[p_ver].keys()):
                    for p_arch in sorted(p_stuff[p_ver][p_rel].keys()):
                        i_stuff = packs[p_name][p_ver][p_rel][p_arch]
                        flags = []
                        if i_stuff["nodeps"]:
                            flags.append("nod")
                        if i_stuff["forceflag"]:
                            flags.append("ffl")
                        if i_stuff["native"]:
                            flags.append("native")
                        flags = ",".join(flags)
                        t_state = i_stuff["t_state"]
                        stat_str = " ".join(i_stuff["status"].split("\n"))
                        if show_it:
                            if i_stuff["install_time"]:
                                i_time = time.strftime("%d. %b %Y %H:%M:%S", time.localtime(i_stuff["install_time"]))
                            else:
                                i_time = "???"
                            out_list.add_line((host, p_name, t_state, flags, p_ver, p_rel, i_stuff["architecture"], i_time, stat_str))
                            # print "  %-35s %s %12s %10s-%-10s %10s %21s, %s" % (p_name, t_state, flags, p_ver, p_rel, i_stuff["architecture"], i_time, stat_str)
                        else:
                            out_list.add_line((host, p_name, t_state, flags, p_ver, p_rel, i_stuff["architecture"], stat_str))
                            # print "  %-35s %s %12s %10s-%-10s %10s %s" % (p_name, t_state, flags, p_ver, p_rel, i_stuff["architecture"], stat_str)
        if out_list:
            out_list.set_format_string(4, "s", "")
            out_list.set_format_string(6, "s", "")
            if show_headers:
                print "device %20s : %4d packages (%4d with unique names) associated" % (host, dev_dict[host]["num_p"], dev_dict[host]["num_tot"])
            print out_list

if __name__ == "__main__":
    print "not ready right now, please wait for rewrite"
    sys.exit(1)
    main()
