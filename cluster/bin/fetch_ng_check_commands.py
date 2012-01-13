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

import sys
import MySQLdb
import MySQLdb.cursors
import logging_tools
import mysql_tools
import cPickle

def main():
    db_c = mysql_tools.db_con()
    db_c.dc.execute("SELECT nc.name,nc.command_line,nc.description,c.name AS confname FROM ng_check_command nc, new_config c WHERE nc.new_config=c.new_config_idx")
    print cPickle.dumps(db_c.dc.fetchall())
        
if __name__ == "__main__":
    main()
