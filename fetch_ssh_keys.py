#!/usr/bin/python-init -Otu
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007 Andreas Lang, init.at
#
# Send feedback to: <lang@init.at>
#
# this file is part of cluster-config-server
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
""" fetches the actual ssh-keys from devices and inserts them into the database """

import getopt
import mysql_tools
import logging_tools
import msock
import sys
import os
import os.path
import commands
import array
import tempfile

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], "ht:sx:", ["help"])
    except getopt.GetoptError, bla:
        print "Commandline error!", bla
        sys.exit(2)
    tmp_dir = "/tmp/.fsk"
    fetch_mode = "n"
    pname = os.path.basename(sys.argv[0])
    exclude_list = []
    for opt, arg in opts:
        if opt in ("-h", "--help"):
            print "Usage: %s [OPTIONS]" % (pname)
            print "where OPTIONS are:"
            print " -h,--help        this help"
            print " -t DIR           set tempdir to DIR, default is %s" % (tmp_dir)
            print " -s               fetch server keys via scp, default is node_keys"
            print " -x NODES         coma-separated list of nodes to be excluded"
            sys.exit(0)
        if opt == "-t":
            tmp_dir = arg
        if opt == "-s":
            fetch_mode = "s"
        if opt == "-x":
            exclude_list = [x.strip() for x in arg.split(",")]
    print "Using tempdir %s" % (tmp_dir)
    if not os.path.isdir(tmp_dir):
        os.mkdir(tmp_dir)
    db_con = mysql_tools.dbcon_container()
    dc = db_con.get_connection("cluster_full_access")
    if fetch_mode == "n":
        dc.execute("SELECT d.name, d.device_idx FROM device d INNER JOIN device_type dt INNER JOIN device_config dc INNER JOIN new_config nc INNER JOIN device_group dg LEFT JOIN device d2 ON d2.device_idx=dg.device WHERE " + \
                   "d.device_group=dg.device_group_idx AND d.device_type=dt.device_type_idx AND dt.identifier='H' AND (d.device_idx=dc.device OR d2.device_idx=dc.device) AND dc.new_config=nc.new_config_idx AND nc.name='node' ORDER BY d.name")
    else:
        dc.execute("SELECT d.name, d.device_idx FROM device d INNER JOIN device_type dt INNER JOIN device_config dc INNER JOIN new_config nc INNER JOIN device_group dg LEFT JOIN device d2 ON d2.device_idx=dg.device WHERE " + \
                   "d.device_group=dg.device_group_idx AND d.device_type=dt.device_type_idx AND dt.identifier='H' AND (d.device_idx=dc.device OR d2.device_idx=dc.device) AND dc.new_config=nc.new_config_idx AND nc.name='node' ORDER BY d.name")
        all_nodes = [x["name"] for x in dc.fetchall()]
        dc.execute("SELECT d.name, d.device_idx FROM device d, device_type dt WHERE d.device_type=dt.device_type_idx AND dt.identifier='H' %s ORDER BY d.name" % (all_nodes and " AND ".join(["d.name != '%s'" % (x) for x in all_nodes]) or ""))
    all_res = dc.fetchall()
    all_nodes = [x["name"] for x in all_res if x["name"] not in exclude_list]
    node_lut = dict([(x["name"], x["device_idx"]) for x in all_res if x["name"] in all_nodes])
    print "Found %s: %s" % (logging_tools.get_plural("node", len(all_nodes)),
                            logging_tools.compress_list(all_nodes))
    print "Pinging ... "
    err, r_dict = msock.single_icmp_ping(all_nodes, 3, 4.0, 1)
    if err:
        print "Something went wrong while ping: %d, %s" % (err, msock.long_err(err))
        sys.exit(-1)
    print "  ... done"
    key_types = ["rsa1", "rsa", "dsa"]
    needed_files = ["ssh_host_%s_key" % (x) for x in key_types]
    needed_files.extend(["%s.pub" % (x) for x in needed_files])
    key_names = [x.replace(".", "_") for x in needed_files]
    for node in all_nodes:
        sql_str = "SELECT dv.* FROM device d LEFT JOIN device_variable dv ON dv.device=d.device_idx WHERE d.name='%s' AND (%s)" % (node,
                                                                                                                                   " OR ".join(["dv.name='%s'" % (x) for x in key_names]))
        dc.execute(sql_str)
        found_keys = dict([(x["name"], type(x["val_blob"]) == type(array.array("b")) and x["val_blob"].tostring() or x["val_blob"]) for x in dc.fetchall()])
        node_dir = "%s/%s" % (tmp_dir, node)
        if not os.path.isdir(node_dir):
            os.mkdir(node_dir)
        recreate = False
        if not r_dict.has_key(node):
            if found_keys:
                print "%s not in result_dict but keys present" % (node)
            else:
                print "%s not in result_dict, recreating keys..." % (node)
                recreate = True
        else:
            if r_dict[node][0] == 0:
                if found_keys:
                    print "%s is unknown but keys present" % (node)
                else:
                    print "%s is unknown, recreate..." % (node)
                    recreate = True
            elif r_dict[node][2] == 0:
                if found_keys:
                    print "%s is down but keys present" % (node)
                else:
                    print "%s is down, recreate..." % (node)
                    recreate = True
            else:
                if len([True for x in needed_files if os.path.isfile("%s/%s" % (node_dir, x))]) != len(needed_files):
                    stat, out = commands.getstatusoutput("%scp root@%s:/etc/ssh/*key* %s" % (fetch_mode == "n" and "r" or "s", node, node_dir))
                    if stat:
                        print "  Something went wrong contacting %s: %s (%d)" % (node, out, stat)
                        recreate = False
                    else:
                        print "  copied keys from %s" % (node)
                file_dict = dict([(x, file("%s/%s" % (node_dir, x), "r").read()) for x in needed_files if os.path.isfile("%s/%s" % (node_dir, x))])
                if not found_keys:
                    print "%s: Inserting found keys into database..." % (node)
                    for nf in file_dict.keys():
                        nk = nf.replace(".", "_")
                        sql_str, sql_tuple = ("INSERT INTO device_variable SET device=%%s, name=%%s, var_type='b', description='SSH key %s', val_blob=%%s" % (nk), (node_lut[node],
                                                                                                                                                                    nk,
                                                                                                                                                                    file_dict[nf]))
                        dc.execute(sql_str, sql_tuple)
                else:
                    keys_ok = True
                    for file_name in needed_files:
                        key_name = file_name.replace(".", "_")
                        if file_dict.has_key(file_name) and found_keys.has_key(key_name):
                            if file_dict[file_name] != found_keys[key_name]:
                                keys_ok = False
                        else:
                            keys_ok = False
                    if keys_ok:
                        print "%s: Keys ok" % (node)
                    else:
                        print "*** %s: Keys not ok, strange ... " % (node)
        if recreate:
            for key_type in key_types:
                privfn = "ssh_host_%s_key" % (key_type)
                pubfn  = "ssh_host_%s_key_pub" % (key_type)
                dc.execute("DELETE FROM device_variable dv WHERE dv.device=%d AND (%s)" % (node_lut[node],
                                                                                                  " OR ".join(["dv.name='%s'" % (x) for x in [privfn, pubfn]])))
                sshkn = tempfile.mktemp("sshgen")
                sshpn = "%s.pub" % (sshkn)
                os.system("ssh-keygen -t %s -q -b 1024 -f %s -N ''" % (key_type, sshkn))
                found_keys[privfn] = file(sshkn, "r").read()
                found_keys[pubfn]  = file(sshpn, "r").read()
                os.unlink(sshkn)
                os.unlink(sshpn)
            print "%s: Inserting new keys into database..." % (node)
            for nk in found_keys.keys():
                sql_str, sql_tuple = ("INSERT INTO device_variable SET device=%%s, name=%%s, var_type='b', description='SSH key %s', val_blob=%%s" % (nk), (node_lut[node],
                                                                                                                                                            nk,
                                                                                                                                                            found_keys[nk]))
                dc.execute(sql_str, sql_tuple)
    dc.release()
    del db_con
            

if __name__ == "__main__":
    main()
