#!/usr/bin/python -Ot
# -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2009 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
# 
# This file belongs to webfrontend
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
""" fetches a subtree of the configtree """

import cPickle
import array

def process_page(req):
    req.content_type = "unknown/binary; name=\"config\""
    req.headers_out["Content-Disposition"] = "filename=\"config\""
    req.send_http_header()
    config_idx = req.sys_args.get("config", None)
    if config_idx:
        sql_str = "SELECT c.*, ct.name AS ctname, ct.description AS ctdescription FROM new_config c, new_config_type ct WHERE c.new_config_type=ct.new_config_type_idx AND (%s)" % (" OR ".join(["c.new_config_idx=%s" % (x) for x in config_idx]))
        ct_dict, c_dict, s_dict = ({}, {}, {})
        req.dc.execute(sql_str)
        for db_rec in req.dc.fetchall():
            ct_dict.setdefault(db_rec["new_config_type"], dict([(k[2:], db_rec[k]) for k in ["ctname", "ctdescription"]]))
            c_dict.setdefault(db_rec["new_config_idx"], dict([(k, db_rec[k]) for k in ["name", "description", "priority", "new_config_type"]]))
        # fetch ints, strs, blobs and scripts
        for what in ["int", "str", "blob", "script"]:
            sql_str = "SELECT * FROM config_%s WHERE (%s)" % (what, " OR ".join(["new_config=%d" % (x) for x in c_dict.keys()]))
            req.dc.execute(sql_str)
            for db_rec in req.dc.fetchall():
                if type(db_rec["value"]) == type(array.array("b")):
                    db_rec["value"] = db_rec["value"].tostring()
                c_dict[db_rec["new_config"]].setdefault(what, {})[db_rec["config_%s_idx" % (what)]] = dict([(k, db_rec[k]) for k in ["name", "descr", "value"] + (what == "script" and ["enabled", "priority"] or [])])
        # commands
        sql_str = "SELECT nc.*,ct.name AS ct_name FROM ng_check_command nc LEFT JOIN ng_check_command_type ct ON ct.ng_check_command_type_idx=nc.ng_check_command_type WHERE (%s)" % (" OR ".join(["nc.new_config=%d" % (x) for x in c_dict.keys()]))
        req.dc.execute(sql_str)
        for db_rec in req.dc.fetchall():
            c_dict[db_rec["new_config"]].setdefault("ng_check_command", {})[db_rec["ng_check_command_idx"]] = dict([(k, db_rec[k]) for k in ["name", "command_line", "description", "ct_name"]])
        # snmp stuff
        sql_str = "SELECT s.*, sc.new_config FROM snmp_mib s LEFT JOIN snmp_config sc ON sc.snmp_mib=s.snmp_mib_idx AND (%s)" % (" OR ".join(["sc.new_config=%s" % (x) for x in config_idx]))
        req.dc.execute(sql_str)
        for db_rec in req.dc.fetchall():
            if not s_dict.has_key(db_rec["snmp_mib_idx"]):
                s_dict[db_rec["snmp_mib_idx"]] = dict([(k, db_rec[k]) for k in ["name", "descr", "mib", "rrd_key", "unit", "base", "factor", "var_type", "special_command"]] + [("new_configs", [])])
            if db_rec["new_config"]:
                s_dict[db_rec["snmp_mib_idx"]]["new_configs"].append(c_dict[db_rec["new_config"]]["name"])
        #print ct_dict
        #print c_dict
        #print s_dict
        result = cPickle.dumps((ct_dict, c_dict, s_dict))
        req.write(result)
    else:
        req.write("no config_idx specified")
