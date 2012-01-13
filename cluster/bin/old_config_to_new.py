#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001,2002,2003,2004,2005,2006 Andreas Lang, init.at
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
    print "Converting old to new config ..."
    var_types=["str", "int", "blob"]
    for vt in var_types:
        print "deleting %s variables ..." % (vt)
        db_c.dc.execute("DELETE FROM config_%s WHERE new_config" % (vt))
    print "deleting scripts ..."
    db_c.dc.execute("DELETE FROM config_script WHERE new_config")
    print "deleting new_config ..."
    db_c.dc.execute("DELETE FROM new_config")
    print "deleting new_config_types ..."
    db_c.dc.execute("DELETE FROM new_config_type")
    print "converting config_types ..."
    new_c_types={}
    db_c.dc.execute("SELECT * FROM config_type")
    for x in db_c.dc.fetchall():
        db_c.dc.execute("INSERT INTO new_config_type SET name='%s',description='%s (%s)'" % (x["name"], x["description"] or "identifier", x["identifier"]))
        new_c_types[x["config_type_idx"]]=db_c.dc.insert_id()
    # delete device_configs
    db_c.dc.execute("DELETE * FROM device_config")
    # fetch all device_config/device pairs
    db_c.dc.execute("SELECT * FROM deviceconfig")
    all_confs={}
    for x in db_c.dc.fetchall():
        all_confs.setdefault(x["config"],[]).append(x["device"])
    # regexp-object for script parsing
    comment_re = re.compile("^\S*#.*$")
    command_re = re.compile("^(?P<com>\S+)\s+(?P<stuff>.*)$")
    # replace lists
    repl_list = [("%{net[name]}"          , "dev_dict[\"net\"][\"name\"]"          ),
                 ("%{net[network]}"       , "dev_dict[\"net\"][\"network\"]"       ),
                 ("%{net[netmask]}"       , "dev_dict[\"net\"][\"netmask\"]"       ),
                 ("%{node_if[0][devname]}", "dev_dict[\"node_if\"][0][\"devname\"]"),
                 ("%{node_if[0][ip]}"     , "dev_dict[\"node_if\"][0][\"ip\"]"     ),
                 ("%{node_if[0][netmask]}", "dev_dict[\"node_if\"][0][\"netmask\"]"),
                 ("%{node_if[0][gateway]}", "dev_dict[\"node_if\"][0][\"gateway\"]")]
    for server in ["yp_server", "name_server", "openpbs_server", "xntp_server", "syslog_server_ip", "rrd_server", "mother_server", "torque_server", "sge_server", "package_server", "host", "hostfq"]:
        repl_list.append(("%%{%s}" % (server)   ,"dev_dict[\"%s\"]" % (server)   ))
        repl_list.append(("%%{%s_ip}" % (server),"dev_dict[\"%s_ip\"]" % (server)))
    for stuff in ["nisdomainname", "uid", "gid", "cellname", "xntp_server", "sge_server"]:
        repl_list.append(("%%{%s}" % (stuff)   ,"dev_dict[\"%s\"]" % (stuff)   ))
    db_c.dc.execute("SELECT * FROM config")
    for x in db_c.dc.fetchall():
        print "converting config %s ..." % (x["name"])
        if not x["descr"]:
            x["descr"] = "description for %s" % (x["name"])
        db_c.dc.execute("INSERT INTO new_config SET name='%s',description='%s',priority=%d, new_config_type=%d" % (x["name"], x["descr"], x["priority"], new_c_types[x["config_type"]]))
        new_c_idx = db_c.dc.insert_id()
        # modify ng_check_commands
        db_c.dc.execute("UPDATE ng_check_command SET new_config=%d WHERE config=%d" % (new_c_idx, x["config_idx"]))
        # make device_config entries
        for device in all_confs.get(x["config_idx"],[]):
            db_c.dc.execute("INSERT INTO device_config SET device=%d, new_config=%d" % (device, new_c_idx))
        for vt in var_types:
            db_c.dc.execute("SELECT * FROM config_%s WHERE config=%d" % (vt, x["config_idx"]))
            for y in db_c.dc.fetchall():
                if not y["value"] and vt != "int":
                    y["value"] = "empty value"
                if y["name"] == "hwswconfig" and vt == "str":
                    lines = y["value"].replace("\r\n", "\n").split("\n")
                    print "  script: %s (%s)" % (y["name"], logging_tools.get_plural("line", len(lines)))
                    new_lines=[]
                    line_num = 0
                    # actual system
                    act_sys = ""
                    # list of used files
                    file_dict, file_idx, link_dict, link_idx, copy_dict, copy_idx, intent=({"act_sys" : {}}, 0,
                                                                                           {"act_sys" : {}}, 0,
                                                                                           {"act_sys" : {}}, 0, 0)
                    if x["name"] == "base":
                        # add default lines
                        new_lines.append("do_nets(config)")
                        new_lines.append("do_routes(config)")
                        new_lines.append("do_fstab(config)")
                    for line in lines:
                        line_num += 1
                        in_str = " "*intent*4
                        # transform lines
                        if comment_re.match(line) or not line:
                            new_lines += [line]
                        else:
                            com_re = command_re.match(line)
                            if com_re:
                                command, stuff=(com_re.group("com"), com_re.group("stuff"))
                                if command.startswith("@"):
                                    command = command[1:]
                                if command == "D":
                                    print " - transforming D to del_config() construct"
                                    new_lines.append("%sconfig.del_config(\"%s\")" % (in_str, stuff))
                                elif command in ["a", "c", "l"]:
                                    nsplit = stuff.split(" ", 1)
                                    if len(nsplit) < 2 and command not in ["a"]:
                                        print "*** PARSE_2 ERROR", line
                                    else:
                                        filename = nsplit[0]
                                        if command == "a":
                                            append = len(nsplit) == 2 and nsplit[1] or ""
                                            if not file_dict.setdefault(act_sys,{}).has_key(filename):
                                                print " - transforming a to new_file_object() construct"
                                                file_idx += 1
                                                file_dict[act_sys][filename] = "fo_%d" % (file_idx)
                                                new_lines.append("%s%s=config.add_file_object(\"%s\")" % (in_str, file_dict[act_sys][filename], filename))
                                            post_list=[]
                                            if append.find("%")>-1 and (append.find("%{IDENTIFIER}") < 0 and append.find("#%PAM-1.0") < 0):
                                                for r0, r1 in repl_list:
                                                    if append.find(r0) > -1:
                                                        append = append.replace(r0,"%s")
                                                        post_list.append(r1)
                                                if not post_list:
                                                    print "*** WARN %% used in '%s'" % (append)
                                            new_lines.append("%s%s+=\"%s\"%s" % (in_str, file_dict[act_sys][filename], append.replace("\"", "\\\""), post_list and "%%(%s)" % (",".join(post_list)) or ""))
                                        elif command == "c":
                                            if not copy_dict.setdefault(act_sys,{}).has_key(filename):
                                                print " - transforming c to new_copy_object() construct"
                                                copy_idx += 1
                                                copy_dict[act_sys][filename] = "co_%d" % (copy_idx)
                                                new_lines.append("%s%s=config.add_copy_object(\"%s\",\"%s\")" % (in_str, copy_dict[act_sys][filename], filename, nsplit[1].strip()))
                                        elif command == "l":
                                            link_idx += 1
                                            link_dict.setdefault(act_sys,{})[filename] = "lo_%d" % (link_idx)
                                            new_lines.append("%s%s=config.add_link_object(\"%s\",\"%s\")" % (in_str, link_dict[act_sys][filename], filename, nsplit[1].strip()))
                                elif command == "sfmode":
                                    print " - transform sfmode to config.set_file_mode()"
                                    new_lines.append("%sconfig.set_file_mode(\"%s\")" % (in_str, stuff))
                                elif command == "sdmode":
                                    print " - transform sdmode to config.set_dir_mode()"
                                    new_lines.append("%sconfig.set_dir_mode(\"%s\")" % (in_str, stuff))
                                elif command == "suid":
                                    print " - transform suid to config.set_uid()"
                                    if stuff == "%{uid}":
                                        stuff = "dev_dict[\"uid\"]"
                                    new_lines.append("%sconfig.set_uid(%s)" % (in_str, stuff))
                                elif command == "sgid":
                                    print " - transform sgid to config.set_gid()"
                                    if stuff == "%{gid}":
                                        stuff = "dev_dict[\"gid\"]"
                                    new_lines.append("%sconfig.set_gid(%s)" % (in_str, stuff))
                                elif command == "d":
                                    print " - transform d to new_dir_object()"
                                    new_lines.append("%sconfig.add_dir_object(\"%s\")" % (in_str, stuff))
                                elif command == "special":
                                    print " - transform special to do_XXX(config)"
                                    stuff = "do_%s" % ({"ssh":"ssh", "hosts":"etc_hosts", "hosts_equiv":"hosts_equiv"}[stuff.strip()])
                                    new_lines.append("%s%s(config)" % (in_str, stuff))
                                else:
                                    print "*** UNKNWON COMMAND ERR %s (%s)" % (command, stuff)
                            elif line.startswith("="):
                                print " - transform = to if"
                                if len(line) == 1:
                                    intent -= 1
                                    act_sys = ""
                                else:
                                    new_lines.append("if dev_dict[\"system\"][\"vendor\"] == \"%s\":" % (line[1:]))
                                    act_sys = line[1:]
                                    intent += 1
                            else:
                                print "*** PARSE_1 ERROR", line
                    #print "-"*10,"new script:", "-"*10
                    print "\n".join(["(%3d) %s" % (v0, v1) for v0, v1 in zip(range(1, len(new_lines) + 1), new_lines)])
                    #print "-"*30
                    db_c.dc.execute("INSERT INTO config_script SET name='%s',descr='%s',new_config=%d, value='%s'" % (y["name"], y["descr"], new_c_idx, mysql_tools.my_escape("\n".join(new_lines))))
                else:
                    print "  %s: %s" % (vt, y["name"])
                    if vt == "int":
                        vx = "%d" % (y["value"])
                    elif type(y["value"]) == type(array.array("b")):
                        vx = "'%s'" % (mysql_tools.my_escape(y["value"].tostring()))
                    else:
                        vx = "'%s'" % (mysql_tools.my_escape(y["value"]))
                    db_c.dc.execute("INSERT INTO config_%s SET name='%s',descr='%s',new_config=%d, value=%s" % (vt, y["name"], y["descr"], new_c_idx, vx))
        
if __name__ == "__main__":
    main()
