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
""" commandline client to install packages """

import getopt
import logging_tools
import net_tools
import os
import re
import server_command
import sys
import time

SQL_ACCESS = "cluster_full_access"

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], "p:v:r:a:f:P:hg:A:s", ["help", "dryrun", "del", "inst", "up"])
    except getopt.GetoptError, why:
        print "Error parsing commandline %s: %s" % (" ".join(sys.argv[1:]), str(why))
        sys.exit(-1)
    pack_name, dryrun, version, release, ass_mode, flags, targ_mode, groups, arch, signal = (None, 0, None, None, "keep", [], "-", [], None, 0)
    ps_file = "/etc/packageserver"
    if os.path.isfile(ps_file):
        try:
            package_server = file(ps_file, "r").read().split("\n")[0].strip()
        except:
            package_server = "localhost"
        else:
            pass
    else:
        package_server = "localhost"
    for opt, arg in opts:
        if opt in ["-h", "--help"]:
            print "Usage: %s [ OPTIONS ] [ regexp-list of host-names ]" % (os.path.basename(sys.argv[0]))
            print "where OPTIONS is one of:"
            print "  --dryrun          do nothing"
            print "  -s                just signal the package-server"
            print "  -p NAME           Name of package to install (basename of full name with-version-release appended)"
            print "  -A ARCH           Architecture of package to install, default to '%s' (if only one package is found take the architecture)" % (arch)
            print "  -v VERSION        Version to install, default: latest version"
            print "  -r RELEASE        Release to install, default: latest release"
            print "  -a ASSOCIATE      Assoication mode, one of set, del or keep (default is %s)" % (ass_mode)
            print "  --inst            flag to install the selected packages"
            print "  --up              flag to upgrade the selected packages"
            print "  --del             flag to delete the selected packages"
            print "  -g GROUP          comma-separated list of devicegroups"
            print "  -f FLAG           flags to set for the rpm-commands; one or more of (n)odeps or (f)orce, (c)lear; default is no flags (or keep flags)"
            print "  -P SERVER         set package_server to SERVER, default is %s" % (package_server)
            sys.exit(0)
        if opt == "-g":
            groups = [x.strip() for x in arg.strip().split(",")]
        if opt == "-P":
            package_server = arg
        if opt == "-s":
            signal = 1
        if opt == "-A":
            arch = arg
        if opt == "--dryrun":
            dryrun = 1
        if opt == "-p":
            pack_name = arg
        if opt == "-v":
            version = arg
        if opt == "-r":
            release = arg
        if opt == "--inst":
            targ_mode = "i"
        if opt == "--up":
            targ_mode = "u"
        if opt == "--del":
            targ_mode = "d"
        if opt == "-a":
            if arg in ["set", "del", "keep"]:
                ass_mode = arg
            else:
                print "Unknown associaton mode '%s', exiting" % (arg)
                sys.exit(1)
        if opt == "-f":
            for arg_p in arg:
                if arg_p in ["n", "f", "c"]:
                    flags.append(arg_p)
                else:
                    print "Unknown flag '%s' in argument '%s' for -f" % (arg_p, arg)
                    sys.exit(1)
    if dryrun:
        print "Doing a dryrun, changing no database structures..."
    dbcon = mysql_tools.dbcon_container()
    dc = dbcon.get_connection(SQL_ACCESS)
    if not args and not groups:
        print "No device-regexps or groups found, exiting..."
        dc.execute("SELECT dg.name, COUNT(d.name) AS devcount FROM device_group dg INNER JOIN device d INNER JOIN device_config dc INNER JOIN new_config c INNER JOIN device_type dt LEFT JOIN " + \
                   "device d2 ON d2.device_idx=dg.device WHERE dg.device_group_idx=d.device_group AND (dc.device=d.device_idx OR dc.device=d2.device_idx) AND dc.new_config=c.new_config_idx AND " + \
                   "d.device_type=dt.device_type_idx AND dt.identifier='H' AND c.name='package_client' GROUP BY dg.name")
        print "  - possible Devicegroups:"
        for db_rec in dc.fetchall():
            print "%20s: %s" % (db_rec["name"], logging_tools.get_plural("device", db_rec["devcount"]))
        dc.release()
        sys.exit(2)
    # find devices
    dc.execute("SELECT d.device_idx,d.name,dg.name AS dgname FROM device_group dg INNER JOIN device d INNER JOIN device_config dc INNER JOIN new_config c INNER JOIN device_type dt LEFT JOIN " + \
               "device d2 ON d2.device_idx=dg.device WHERE dg.device_group_idx=d.device_group AND (dc.device=d.device_idx OR dc.device=d2.device_idx) AND dc.new_config=c.new_config_idx AND " + \
               "d.device_type=dt.device_type_idx AND dt.identifier='H' AND c.name='package_client' ORDER BY d.name")
    all_devs = dc.fetchall()
    use_devs = []
    for dev in all_devs:
        add_it = 0
        for group in groups:
            if dev["dgname"] == group:
                add_it = 1
        for arg in args:
            if re.search(arg, dev["name"]):
                add_it = 1
        if add_it:
            use_devs.append(dev)
    if not use_devs:
        print "No devices found with config package_client in one of the %d device_groups %s or matching at least one of the %d device-regexps: %s" % (len(groups), ", ".join(groups), len(args), ", ".join(args))
        dc.release()
        sys.exit(4)
    if not signal:
        if not pack_name:
            print "No package name given, exiting..."
            dc.release()
            sys.exit(2)
        if pack_name.endswith("rpm"):
            pack_name_new = ".".join(pack_name.split(".")[:-2])
            print "  *** warn: package_name '%s' ends with 'rpm', correcting to %s" % (pack_name, pack_name_new)
            pack_name = pack_name_new
        # find package
        sql_str = "SELECT i.inst_package_idx, p.version,p.release,p.name,a.architecture FROM inst_package i, package p, architecture a WHERE i.package=p.package_idx AND p.architecture=a.architecture_idx AND (p.name='%s' OR CONCAT(p.name, '-',p.version,'-',p.release)='%s') ORDER BY i.inst_package_idx DESC" % (pack_name, pack_name)
        dc.execute(sql_str)
        all_packs = dc.fetchall()
        if not all_packs:
            print "No packages with name '%s' found, exiting..." % (pack_name)
            dc.release()
            sys.exit(3)
        found_packs = []
        for db_rec in all_packs:
            if ((version and db_rec["version"] == version) or not version) and ((release and db_rec["release"] == release) or not release) and ((arch and db_rec["architecture"] == arch) or not arch):
                found_packs.append(db_rec)
        if not found_packs:
            print "No packages matching the given version '%s' / release '%s' / architecture %s found, exiting ..." % (str(version), str(release), str(arch))
            dc.release()
            sys.exit(3)
        use_pack = found_packs.pop(0)
        print "Using package named '%s' (version %s, release %s) ..." % (use_pack["name"], use_pack["version"], use_pack["release"])
        dev_dict = dict([(x["device_idx"], {"name" : x["name"],
                                            "ipds" : None}) for x in use_devs])
        print "Operating on %s: %s" % (logging_tools.get_plural("device", len(use_devs)), logging_tools.compress_list([x["name"] for x in use_devs]))
        # check if we have to add/remove one or more instp_device structs
        sql_str = "SELECT i.* FROM instp_device i WHERE inst_package=%d AND (%s)" % (use_pack["inst_package_idx"], " OR ".join(["i.device=%d" % (x["device_idx"]) for x in use_devs]))
        dc.execute(sql_str)
        # check for ass_mode del
        out_list = {}
        for db_rec in dc.fetchall():
            if ass_mode == "del":
                out_list.setdefault("Removing instp_device entry", []).append(dev_dict[db_rec["device"]]["name"])
                # print "Removing instp_device entry for device '%s' ..." %
                if not dryrun:
                    dc.execute("DELETE FROM instp_device WHERE instp_device_idx=%d" % (db_rec["instp_device_idx"]))
            else:
                dev_dict[db_rec["device"]]["ipds"] = db_rec
                out_list.setdefault("instp_device entry present, ok for association mode '%s'" % (ass_mode), []).append(dev_dict[db_rec["device"]]["name"])
                # print "instp_device entry for device '%s' present, ok for association_mode '%s'" % (dev_dict[x["device"]]["name"], ass_mode)
        for what, dev_list in out_list.iteritems():
            print "%s for devices %s" % (what, logging_tools.compress_list(dev_list))
        # check for ass_mode set
        out_list = {}
        for d_idx, ds in dev_dict.iteritems():
            if not ds["ipds"]:
                if ass_mode == "set":
                    out_list.setdefault("Adding instp_device entry", []).append(ds["name"])
                    # print "Adding instp_device entry for device '%s' ..." % (ds["name"])
                    if not dryrun:
                        dc.execute("INSERT INTO instp_device SET inst_package=%s, device=%s", (use_pack["inst_package_idx"], d_idx))
                        dc.execute("SELECT i.* FROM instp_device i WHERE i.instp_device_idx=%d" % (dc.insert_id()))
                        ds["ipds"] = dc.fetchone()
                else:
                    out_list.setdefault("instp_device entry not present, ok for association mode '%s'" % (ass_mode), []).append(ds["name"])
                    # print "instp_device entry for device '%s' not set, ok for association_mode '%s'" % (ds["name"], ass_mode)
        for what, dev_list in out_list.iteritems():
            print "%s for devices %s" % (what, logging_tools.compress_list(dev_list))
        # check for change in target_state
        out_list = {}
        for d_idx, ds in dev_dict.iteritems():
            if ds["ipds"]:
                sql_c_f = []
                # flags
                ipds = ds["ipds"]
                of_f = []
                if ipds["nodeps"]:
                    of_f.append("--nodeps")
                if ipds["forceflag"]:
                    of_f.append("--force")
                if flags:
                    if "c" in flags:
                        nf_f = ["<clear flags>"]
                        if ipds["nodeps"]:
                            sql_c_f.append("nodeps=0")
                        if ipds["forceflag"]:
                            sql_c_f.append("forceflag=0")
                        if of_f == ["<no flags>"]:
                            nf_f = []
                    else:
                        nf_f = []
                        if "n" in flags:
                            if not ipds["nodeps"]:
                                sql_c_f.append("nodeps=1")
                                nf_f.append("--nodeps")
                        else:
                            if ipds["nodeps"]:
                                sql_c_f.append("nodeps=0")
                                nf_f.append("no --nodeps")
                        if "f" in flags:
                            if not ipds["forceflag"]:
                                sql_c_f.append("forceflag=1")
                                nf_f.append("--force")
                        else:
                            if ipds["forceflag"]:
                                sql_c_f.append("forceflag=0")
                                nf_f.append("no --force")
                    if nf_f:
                        flag_str = "changing flags from '%s' to '%s'" % (", ".join(of_f), ", ".join(nf_f))
                    else:
                        flag_str = "keeping flags at '%s'" % (", ".join(of_f))
                else:
                    flag_str = "keeping flags at '%s'" % (", ".join(of_f))
                # target mode
                long_targ_mode = {"i" : "install",
                                  "d" : "del",
                                  "u" : "upgrade",
                                  "-" : "keep"}[targ_mode]
                if targ_mode != "-":
                    targ_str = "setting mode to '%s'" % (long_targ_mode)
                    sql_c_f.extend(["%s=0" % (x) for x in ["del", "upgrade", "install"] if ipds[x]] + ["%s=1" % (long_targ_mode)])
                else:
                    targ_str = "leaving mode at '%s'" % (([x for x in ["del", "upgrade", "install"] if ipds[x]] + ["keep"])[0])
                out_list.setdefault(targ_str, {}).setdefault(flag_str, []).append(ds["name"])
                if not dryrun and sql_c_f:
                    dc.execute("UPDATE instp_device SET %s WHERE instp_device_idx=%d" % (",".join(sql_c_f), ipds["instp_device_idx"]))
        for targ_str, targ_stuff in out_list.iteritems():
            for flag_str, dev_list in targ_stuff.iteritems():
                print "%s, %s for %s: %s" % (targ_str, flag_str, logging_tools.get_plural("device", len(dev_list)), logging_tools.compress_list(dev_list))
    act_to = 5 + int(len(use_devs) / 10)
    dc.release()
    print "Signaling package-server at '%s' about new config, timeout set to %d seconds ..." % (package_server, act_to),
    s_time = time.time()
    serv_com = server_command.server_command(command="new_config")
    serv_com.set_nodes([x["name"] for x in use_devs])
    stat, ret_str = net_tools.single_connection(host=package_server,
                                                port=8007,
                                                command=serv_com.create_string()).iterate()
    print " ... took %.2f seconds" % (time.time() - s_time)
    if stat:
        print "Error (%d): %s" % (stat, ret_str)
    else:
        try:
            server_repl = server_command.server_reply(ret_str)
        except ValueError:
            print "Error decoding server-reply: %s" % (sys.exc_info()[1])
        else:
            result_dict, res_dict = (server_repl.get_node_results(), {})
            for dev in [x["name"] for x in use_devs]:
                res_dict.setdefault(result_dict.get(dev, "error array empty (internal error)"), []).append(dev)
            for key, value in res_dict.iteritems():
                print " - %s for %s: %s" % (key,
                                            logging_tools.get_plural("device", len(value)),
                                            logging_tools.compress_list(value))
    sys.exit(stat)

if __name__ == "__main__":
    print "not ready right now, please wait for rewrite"
    sys.exit(1)
    main()

