#!/usr/bin/python-init -Ot
#
# Copyright (C) 2008 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file belongs cluster-backbone
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
""" checks given databases for consistency """

import sys
import mysql_tools
import time
import logging_tools

SQL_ACCESS = "cluster_full_access"

def log(what, level=logging_tools.LOG_LEVEL_OK):
    print "[%d] %s" % (level, what)

def main():
    if len(sys.argv) == 1:
        print "Need some database names"
        sys.exit(-1)
    db_names = sys.argv[1:]
    db_con = mysql_tools.dbcon_container()
    dc = db_con.get_connection(SQL_ACCESS)
    for db_name in db_names:
        print "Checking database %s for consistency ..." % (db_name)
        s_time = time.time()
        dbv_struct = mysql_tools.db_validate(log, dc, database=db_name)
        dbv_struct.repair_tables()
        e_time = time.time()
        print "  check took %s" % (logging_tools.get_diff_time_str(e_time - s_time))
    dc.release()
    del db_con

if __name__ == "__main__":
    main()

