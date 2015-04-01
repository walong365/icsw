#!/usr/bin/python-init -Ot
#
# Copyright (c) 2001,2002,2003,2004,2005,2006,2008 Andreas Lang-Nevyjel, lang-nevyjel@init.at
#
# this file is part of python-modules-base
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License
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
import process_tools
import getopt
import config_tools
import os
try:
    import mysql_tools
except ImportError:
    mysql_tools = None

SQL_ACCESS = "cluster_full_access"

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hinv", ["help"])
    except getopt.GetoptError, bla:
        print "Error parsing commandline %s: %s" % (
            " ".join(sys.argv[1:]),
            process_tools.get_except_info())
        sys.exit(1)
    if len(args) != 1:
        print "Need server_type_name"
        sys.exit(1)
    server_type = args[0]
    pname = os.path.basename(sys.argv[0])
    show_type, verbose = ("i", False)
    for opt, arg in opts:
        if opt in ["-h", "--help"]:
            print "Usage: %s [OPTIONS] server_type_name" % (pname)
            print " where options is one or more of"
            print "  -h, --help          this help"
            print "  -i                  show device_idx (default)"
            print "  -n                  show real_server_name"
            print "  -v                  be verbose"
            sys.exit(1)
        if opt in ["-i", "-n"]:
            show_type = opt[-1]
        if opt == "-v":
            verbose = True
    if mysql_tools:
        db_con = mysql_tools.dbcon_container()
        try:
            dc = db_con.get_connection(SQL_ACCESS)
        except:
            print "cannot get sql-connection"
            sys.exit(1)
    else:
        print "no mysql_tools found"
        sys.exit(1)
    srv_check = config_tools.server_check(dc=dc, server_type=server_type)
    dc.release()
    if verbose:
        print srv_check.report()
    if srv_check.num_servers == 1 and srv_check.server_device_idx:
        if show_type == "i":
            print srv_check.server_device_idx
        else:
            print srv_check.short_host_name
        sys.exit(0)
    else:
        print "Num_servers=%d" % (srv_check.num_servers)
        sys.exit(1)

if __name__ == "__main__":
    main()
    
