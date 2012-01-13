#!/usr/bin/python -Ot
#
# Copyright (C) 2001,2002,2003,2004,2005 Andreas Lang, init.at
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

import os
import os.path
import sys
import configfile
import MySQLdb
import MySQLdb.cursors
import logging_tools
import mysql_tools
import array
import re

def main():
    db_c = mysql_tools.db_con()
    db_c.dc.execute("SELECT name, config_idx FROM config ORDER BY name")
    old_confs = dict([(x["name"], x["config_idx"]) for x in db_c.dc.fetchall()])
    db_c.dc.execute("SELECT name, new_config_idx FROM new_config ORDER BY name")
    new_confs = dict([(x["name"], x["new_config_idx"]) for x in db_c.dc.fetchall()])
    print old_confs
    print new_confs
    for new_name, new_idx in new_confs.iteritems():
      if old_confs.has_key(new_name):
        print "Modify ng_check_commands for '%s' ... " % (new_name)
        db_c.dc.execute("UPDATE ng_check_command SET new_config=%d WHERE config=%d" % (new_idx, old_confs[new_name]))
      else:
        print "No new_config for config '%s'" % (new_name)
        
if __name__ == "__main__":
    main()
