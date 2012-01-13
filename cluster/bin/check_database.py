#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008,2009 Andreas Lang-Nevyjel, init.at
#
# this file is part of cluster-backbone
#
# Send feedback to: <lang-nevyjel@init.at>
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
""" database compare """

import sys
import logging_tools
import mysql_tools
import pprint
import getopt
import os.path
import process_tools

def create_key_line(in_f):
    if in_f["Key"] == "MUL":
        return "KEY %s (%s)" % (in_f["Field"], in_f["Field"])
    elif in_f["Key"] == "PRI":
        return "PRIMARY KEY (%s)" % (in_f["Field"])
    else:
        return None

def generate_key_lines(in_list):
    act_key = {"type"    : "",
               "unique"  : False,
               "columns" : []}
    key_list = []
    for entry in in_list:
        if act_key["type"] != entry["Key_name"]:
            if act_key["type"]:
                key_list.append(act_key)
                act_key = {"type"    : "",
                           "name"    : "",
                           "columns" : []}
            act_key["type"] = entry["Key_name"]
            act_key["unique"] = not entry["Non_unique"]
        act_key["columns"].append(entry["Column_name"])
    # to avoid adding an empty key
    if act_key["type"]:
        key_list.append(act_key)
    ret_dict = {}
    for act_key in key_list:
        col_str = ",".join(["`%s`" % (col_name) for col_name in act_key["columns"]])
        if act_key["type"] == "PRIMARY":
            ret_dict[act_key["type"]] = "PRIMARY KEY (%s)" % (col_str)
        else:
            ret_dict[act_key["type"]] = "%sKEY `%s` (%s)" % ("UNIQUE " if act_key["unique"] else "",
                                                             act_key["type"],
                                                             col_str)
    return ret_dict
        
def check_fields(in_dict):
    if in_dict["Engine"].lower() == "innodb":
        if in_dict["Comment"].lower().count("innodb free"):
            new_comment = in_dict["Comment"][0:in_dict["Comment"].index("InnoDB")].strip()
            if new_comment.endswith(";"):
                new_comment = new_comment[:-1]
            in_dict["Comment"] = new_comment

def create_line(in_f):
    l_type = in_f["Type"]
    line_f = ["`%s`" % (in_f["Field"]), l_type]
    if in_f["Null"] != "YES":
        line_f.append("not null")
    if in_f["Key"] == "UNI":
        # refer to create_key_line
        #line_f.append("unique")
        pass
    elif in_f["Key"] == "PRI":
        # refer to create_key_line
        #line_f.append("primary key")
        pass
    elif in_f["Key"] == "MUL":
        # refer to create_key_line
        pass
    if in_f["Extra"]:
        line_f.append(in_f["Extra"])
    def_str = ""
    if in_f["Default"]:
        if l_type.startswith("varchar") or l_type.startswith("char") or l_type.startswith("text") or l_type in ["time", "datetime"] or l_type.startswith("enum"):
            def_str = "'%s'" % (in_f["Default"])
        else:
            def_str = in_f["Default"]
    elif l_type == "text" or l_type.startswith("varchar"):
        def_str = "''"
    if def_str is not None and def_str != "":
        line_f.append("default %s" % (def_str))
    line = " ".join(line_f)
    return line
    
def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], "h", ["verify", "help"])
    except:
        print "Error parsing commandline %s: %s (%s)" % (" ".join(sys.argv[1:]), process_tools.get_except_info())
        sys.exit(1)
    verify = False
    pname = os.path.basename(sys.argv[0])
    for opt, arg in opts:
        if opt in ["-h", "--help"]:
            print "Usage: %s [OPTIONS] db_one db_two" % (pname)
            print " where options is one or more of"
            print "  -h, --help          this help"
            print "  --verify            verify existing database (can be time-consuming)"
            sys.exit(1)
        if opt == "--verify":
            verify = True
    if len(args) not in [2, 4]:
        print "Need 2 arguments (and optional an access_file and an access_name): old and new database, [access_file, access_name]"
        sys.exit(-1)
    old_db_name, new_db_name = (args[0], args[1])
    if len(args) == 4:
        access_file, access_name = (args[2], args[3])
    else:
        access_file, access_name = ("/etc/sysconfig/cluster/db_access", "cluster_full_access")
    print "Old Databasename is '%s', new database name is '%s'" % (old_db_name, new_db_name)
    print "USE %s;" % (old_db_name)
    db_con = mysql_tools.dbcon_container(cf_name=access_file)
    try:
        old_dc = db_con.get_connection(access_name, database_name=old_db_name)
    except:
        print "Cannot access old DB '%s' via %s: %s" % (old_db_name,
                                                        access_name,
                                                        process_tools.get_except_info())
        sys.exit(-1)
    try:
        new_dc = db_con.get_connection(access_name, database_name=new_db_name)
    except:
        print "Cannot access new DB '%s' via %s: %s" % (new_db_name,
                                                        access_name,
                                                        process_tools.get_except_info())
        sys.exit(-1)
    old_dc.execute("SHOW TABLE STATUS")
    new_dc.execute("SHOW TABLE STATUS")
    old_tables = dict([(db_rec["Name"], db_rec) for db_rec in old_dc.fetchall()])
    new_tables = dict([(db_rec["Name"], db_rec) for db_rec in new_dc.fetchall()])
    if verify:
        old_dc.execute("CHECK TABLE %s" % (", ".join(old_tables.keys())))
        all_checks = old_dc.fetchall()
        check_res_dict = {}
        for db_rec in all_checks:
            r_x = dict([(k.lower(), v) for k, v in db_rec.iteritems()])
            if r_x["msg_text"].lower() != "ok":
                check_res_dict.setdefault(r_x["table"], []).append((r_x["msg_text"], r_x["msg_type"], r_x["op"]))
        if check_res_dict:
            not_ok_tables = check_res_dict.keys()
            not_ok_tables.sort()
            stop_it = False
            print "Found %s which are not ok: %s" % (logging_tools.get_plural("table", len(not_ok_tables)),
                                                     ", ".join(not_ok_tables))
            for not_ok_table in not_ok_tables:
                print "%-40s: %s" % (not_ok_table, ", ".join(["%s: %s %s" % (z, y, x) for x, y, z in check_res_dict[not_ok_table]]))
                if [True for x, y, z in check_res_dict[not_ok_table] if x.lower().count("error")]:
                    stop_it = True
            if stop_it:
                print "Cannot continue"
                sys.exit(0)
    tables_to_create = [tb_name for tb_name in new_tables.keys() if tb_name not in old_tables.keys()]
    tables_to_delete = [tb_name for tb_name in old_tables.keys() if tb_name not in new_tables.keys()]
    tables_to_check  = [tb_name for tb_name in new_tables.keys() if tb_name     in old_tables.keys()]
    if tables_to_delete:
        print "\n".join(["DROP TABLE IF EXISTS %s;" % (tb_name) for tb_name in tables_to_delete])
    for nt in tables_to_create:
        new_f = []
        for check_f in ["Engine", "Comment"]:
            check_fields(new_tables[nt])
            if new_tables[nt][check_f]:
                new_f.append("%s='%s'" % (check_f.upper(), new_tables[nt][check_f]))
        print "CREATE TABLE %s (" % (nt)
        new_dc.execute("DESCRIBE %s" % (nt))
        all_raw_lines = new_dc.fetchall()
        all_lines = [create_line(x) for x in all_raw_lines]
        new_dc.execute("SHOW INDEX FROM %s" % (nt))
        all_keys = generate_key_lines(new_dc.fetchall()).values()
        print ",\n".join(["  %s" % (x) for x in all_lines + all_keys])
        print ") %s;" % (" ".join(new_f))
    for ct in tables_to_check:#["image", "sge_complex", "cluster_functionality"]:#tables_to_check:
        # compare table settings
        alter_f = []
        for check_f in ["Engine", "Comment"]:
            check_fields(old_tables[ct])
            check_fields(new_tables[ct])
            if old_tables[ct][check_f] != new_tables[ct][check_f]:
                alter_f.append("%s='%s'" % (check_f.upper(), new_tables[ct][check_f]))
        if alter_f:
            print "ALTER TABLE %s %s;" % (ct, ", ".join(alter_f))
        old_dc.execute("DESCRIBE %s" % (ct))
        new_dc.execute("DESCRIBE %s" % (ct))
        old_lines = old_dc.fetchall()
        new_lines = new_dc.fetchall()
        old_line_names = [db_rec["Field"] for db_rec in old_lines]
        new_line_names = [db_rec["Field"] for db_rec in new_lines]
        old_line_dict = dict([(db_rec["Field"], db_rec) for db_rec in old_lines])
        new_line_dict = dict([(db_rec["Field"], db_rec) for db_rec in new_lines])
        if old_lines != new_lines:
            #print "-" * 20
            #print ct
            changed = True
            while changed:
                lines_to_check = [x for x in old_line_names if x in old_line_names and x in new_line_names]
                changed = False
                old_to_new_map, new_to_old_map = (dict([(old_line_names.index(x), new_line_names.index(x)) for x in lines_to_check]),
                                                  dict([(new_line_names.index(x), old_line_names.index(x)) for x in lines_to_check]))
                #print old_to_new_map, new_to_old_map
                #for o_i in [x for x in range(len(old_line_names)) if not old_to_new_map.has_key(x)]:
                #    print "*** ALTER TABLE %s DROP %s;" % (ct, old_line_names[o_i])
                #print new_line_names
                #print old_line_names
                for n_i in range(len(new_line_names)):
                    if new_to_old_map.has_key(n_i):
                        o_i = new_to_old_map[n_i]
                        if n_i != o_i:
                            if o_i < n_i:
                                # will be corrected by an ALTER / INSERT statement
                                pass
                            else:
                                print "ALTER TABLE %s DROP %s;" % (ct, old_line_names[n_i])
                                del old_line_dict[old_line_names[n_i]]
                                del old_line_names[n_i]
                                changed = True
                                break
                        else:
                            if old_line_dict.has_key(old_line_names[o_i]):
                                new_line, old_line = (create_line(new_line_dict[new_line_names[n_i]]),
                                                      create_line(old_line_dict[old_line_names[o_i]]))
                                #if ct == "netdevice":
                                #    pprint.pprint(new_line_dict[new_line_names[n_i]])
                                #    print new_line
                                #    print old_line
                                #new_key_line, old_key_line = (create_key_line(new_line_dict[new_line_names[n_i]]),
                                #                              create_key_line(old_line_dict[old_line_names[o_i]]))
                                if new_line != old_line:# or new_key_line != old_key_line:
                                    old_line_dict[old_line_names[o_i]] = new_line_dict[new_line_names[n_i]]
                                    if new_line != old_line:
                                        print "ALTER TABLE %s MODIFY %s;" % (ct, new_line)
#                                     if new_key_line != old_key_line:
#                                         if new_key_line:
#                                             print "ALTER TABLE %s ADD %s;" % (ct, new_key_line)
#                                         else:
#                                             # a little hack but OK
#                                             print "ALTER TABLE %s DROP %s;" % (ct, old_key_line.split("(")[0])
                                    changed = True
                                    break
                    else:
                        print "ALTER TABLE %s ADD %s AFTER %s;" % (ct, create_line(new_line_dict[new_line_names[n_i]]), new_line_names[n_i - 1])
                        old_line_names.insert(old_line_names.index(new_line_names[n_i - 1]) + 1, new_line_names[n_i])
                        old_line_dict[new_line_names[n_i]] = new_line_dict[new_line_names[n_i]]
                        changed = True
                        break
            if old_to_new_map != new_to_old_map:
                print "Error converting %s" % (ct)
                sys.exit(-2)
        # check keys
        old_dc.execute("SHOW INDEX FROM %s" % (ct))
        new_dc.execute("SHOW INDEX FROM %s" % (ct))
        old_keys = generate_key_lines(old_dc.fetchall())
        new_keys = generate_key_lines(new_dc.fetchall())
        for key_to_add in [key for key in new_keys.keys() if key not in old_keys.keys()]:
            print "ALTER TABLE %s ADD %s;" % (ct, new_keys[key_to_add])
        for key_to_del in [key for key in old_keys.keys() if key not in new_keys.keys()]:
            print "ALTER TABLE %s DROP KEY %s;" % (ct, key_to_del)
        for key_to_alter in [key for key in old_keys.keys() if key in new_keys.keys() and new_keys[key] != old_keys[key]]:
            print "ALTER TABLE %s DROP KEY `%s`;" % (ct, key_to_alter)
            print "ALTER TABLE %s ADD %s;" % (ct, new_keys[key_to_alter])
    old_dc.release()
    new_dc.release()
    del db_con
    
if __name__ == "__main__":
    main()
