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
    nag_list = cPickle.loads(sys.stdin.read())
    db_c = mysql_tools.db_con()
    for nag_obj in nag_list:
        conf_name = nag_obj["confname"]
        db_c.dc.execute("SELECT nc.new_config_idx, ng.name FROM new_config nc LEFT JOIN ng_check_command ng ON ng.new_config = nc.new_config_idx WHERE nc.name='%s'" % (conf_name))
        act_dict = {}
        for x in db_c.dc.fetchall():
            act_dict.setdefault(x["new_config_idx"], []).append(x["name"])
        if act_dict:
            act_idx = act_dict.keys()[0]
            if nag_obj["name"] in act_dict[act_idx]:
                print "Nagios command '%s' already present in config '%s'" % (nag_obj["name"], conf_name)
            else:
                print "Adding Nagios command '%s' (%s) to config '%s'" % (nag_obj["name"], nag_obj["description"], conf_name)
                db_c.dc.execute("INSERT INTO ng_check_command SET new_config=%d, name='%s', description='%s', command_line='%s'" % (act_idx, nag_obj["name"], nag_obj["description"], nag_obj["command_line"]))
        else:
            print "No config named '%s' found for nagios-command '%s'" %(conf_name, nag_obj["name"])
                
if __name__ == "__main__":
    main()
