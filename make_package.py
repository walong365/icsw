#!/usr/bin/python-init -Otu
#
# Copyright (C) 2001-2007,2014 Andreas Lang-Nevyjel
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
""" fronted for creating packages """

import commands
import logging_tools
import os
import process_tools
import rpm_build_tools
import shutil
import sys
import time

def check_for_association(dc, p_idx, name, version, release, set_dict):
    dc.execute("SELECT p.*, p.package_idx, ip.inst_package_idx, ip.last_build, ip.location, ip.package FROM package p, inst_package ip WHERE ip.package=p.package_idx AND p.name='%s' AND p.version='%s' AND p.release='%s'" % (name, version, release))
    pip_dict = {}
    for stuff in dc.fetchall():
        pip_dict.setdefault(stuff["package_idx"], {})[stuff["inst_package_idx"]] = stuff
    write_entry = True
    if pip_dict.has_key(p_idx):
        for del_idx in pip_dict[p_idx].keys():
            if set_dict:
                if len([1 for sf in [pip_dict[p_idx][del_idx][key] == set_dict[key] for key in set_dict.keys() if key not in ["last_build"]] if not sf]) > 0:
                    is_same = False
                else:
                    is_same = True
            else:
                is_same = False
            if is_same:
                print "Package already has an inst_package Database-entry (%d) with the same content" % (del_idx)
                write_entry = False
            else:
                print "Package already has an inst_package Database-entry (%d)" % (del_idx)
                dc.execute("SELECT d.name FROM device d, instp_device ip WHERE ip.device=d.device_idx AND ip.inst_package=%d" % (del_idx))
                inst_devices = sorted([x["name"] for x in dc.fetchall()])
                keep_old = False
                while inst_devices:
                    print "  - package is associated with the following %s : %s" % (logging_tools.get_plural("device", len(inst_devices)),
                                                                                    logging_tools.compress_list(inst_devices))
                    print "  - remove associations (please enter yes, no or check to test again) : "
                    ret = None
                    while ret not in ["yes", "no", "check"]:
                        ret = getinput("  - [yes/no/check] : ")
                    if ret == "check":
                        dc.execute("SELECT d.name FROM device d, instp_device ip WHERE ip.device=d.device_idx AND ip.inst_package=%d" % (del_idx))
                        inst_devices = sorted([x["name"] for x in dc.fetchall()])
                        if not inst_devices:
                            print "  - associations have been removed, continuing..."
                    elif ret == "no":
                        print "  - keeping associations and old inst_package Database-entry and exiting at your own risk ... "
                        keep_old, write_entry = (True, False)
                        break
                    elif ret == "yes":
                        print "  - removing associations and exiting at your own risk ... "
                        dc.execute("DELETE FROM instp_device WHERE inst_package=%d" % (del_idx))
                        break
                if not keep_old:
                    print "Removing inst_package Database-entry (%d)" % (del_idx)
                    dc.execute("DELETE FROM inst_package WHERE inst_package_idx=%d" % (del_idx))
    return write_entry

def getinput(prompt=":"):
    while 1:
        ret = ""
        try:
            ret = raw_input(prompt)
        except KeyboardInterrupt:
            print "Ctrl-C"
        except EOFError:
            print "Ctrl-D"
        else:
            pass
        break
    return ret

def list_packages(list_arg, dc):
    all_packs = None
    sql_str = "SELECT ip.last_build,p.packager,ip.location,ip.last_build,p.name,p.version,p.release,a.architecture,p.size,p.summary FROM inst_package ip, package p, architecture a WHERE ip.package=p.package_idx AND p.architecture=a.architecture_idx"
    if "ALL" in list_arg:
        dc.execute(sql_str)
        all_packs = dc.fetchall()
        if len(all_packs):
            print "Showing %s:" % (logging_tools.get_plural("installable package", len(all_packs)))
        else:
            print "No installable packages found."
    else:
        dc.execute("%s AND (%s)" % (sql_str, " OR ".join(["p.name LIKE ('%s%%')" % (x) for x in list_arg])))
        all_packs = dc.fetchall()
        print "Showing %s matching name %s" % (logging_tools.get_plural("installable package", len(all_packs)),
                                               ", ".join(["'%s'" % (x) for x in list_arg]))
    if all_packs:
        out_fm = logging_tools.form_list()
        out_fm.set_header_string(0, ["Name", "Version", "Release", "packager", "pack_date", "arch", "size", "Summary"])
        for pack in all_packs:
            out_fm.add_line([pack["name"], pack["version"], pack["release"], pack["packager"], time.ctime(pack["last_build"]), pack["architecture"], str(pack["size"]), pack["summary"]])
        print str(out_fm)

def delete_package(dc, name, version, release):
    sql_str = "SELECT p.* FROM inst_package ip, package p WHERE ip.package=p.package_idx AND p.name='%s' AND p.version='%s' AND p.release='%s'" % (name, version, release)
    dc.execute(sql_str)
    print "Trying to delete %s with name '%s', version '%s', release '%s' ..." % (logging_tools.get_plural("package", dc.rowcount),
                                                                                  name,
                                                                                  version,
                                                                                  release)
    for pack in dc.fetchall():
        del_entry = check_for_association(dc, pack["package_idx"], pack["name"], pack["version"], pack["release"], {})
        if del_entry:
            print "Delete package '%s-%s.%s' from database ..." % (pack["name"], pack["version"], pack["release"])
            dc.execute("DELETE FROM inst_package WHERE package=%d" % (pack["package_idx"]))
            dc.execute("DELETE FROM package WHERE package_idx=%d" % (pack["package_idx"]))
        else:
            print "Cannot delete"

def list_groups(dc):
    sql_str = "SELECT p.pgroup,COUNT(DISTINCT p.package_idx) AS c FROM inst_package ip,package p WHERE ip.package=p.package_idx GROUP BY p.pgroup"
    dc.execute(sql_str)
    all_g = dc.fetchall()
    print "Found %s:" % (logging_tools.get_plural("distinct group", len(all_g)))
    print "\n".join(["%3d : %s" % (db_rec["c"], db_rec["pgroup"]) for db_rec in all_g])

def check_auto_incr_release(dc, name, version):
    sql_str = "SELECT p.release FROM inst_package ip, package p WHERE ip.package=p.package_idx AND p.name='%s' AND p.version='%s'" % (name, version)
    dc.execute(sql_str)
    if dc.rowcount:
        try:
            release = max([int(x["release"]) for x in dc.fetchall()]) + 1
        except:
            release = 1
            print "Something bad happened while trying to fetch highest release, using %d" % (release)
    else:
        release = 1
    return release

def main():
    # try:
    #    opts, args = getopt.getopt(sys.argv[1:], "n:v:r:g:hl:a:D:C:P:u:g:G:Lms:d:", ["help", "del", "doc=", "exclude-dir-names="] + ["%s-script=" % (script_t) for script_t in rpm_build_tools.SCRIPT_TYPES])
    # except:
    #    print "Error parsing commandline %s" % (" ".join(sys.argv[:]))
    #    sys.exit(-1)
    # version, release = ("0.0", "AUTO_INCR")
    # name = None
    sql_server = True
    package_group = "System/Monitoring"
    list_arg = None
    # if mysql_tools:
    #    db_con = mysql_tools.dbcon_container(with_logging=False)
    #    try:
    #        dc = db_con.get_connection("cluster_full_access")
    #    except:
    #        dc = None
    # else:
    dc = None
    config_dict = {
        "dist_dir"      : "",
        "copy_to"       : "",
        "exc_dir_names" : [],
    }
    if dc:
        dc.execute("SELECT cs.name, cs.value FROM config_str cs, new_config c WHERE c.name='package_server' AND cs.new_config=c.new_config_idx")
        for db_rec in dc.fetchall():
            if db_rec["name"] == "ROOT_EXPORT_DIR":
                config_dict["copy_to"] = db_rec["value"]
            elif db_rec["name"] == "ROOT_IMPORT_DIR":
                config_dict["dist_dir"] = db_rec["value"]
    if not (config_dict["dist_dir"] or config_dict["copy_to"]):
        if os.path.isfile("/etc/debian_version"):
            config_dict["dist_dir"] = "/packages/debian"
            config_dict["copy_to"] = "/opt/cluster/system/packages/debian"
        else:
            config_dict["dist_dir"] = "/packages/RPMs"
            config_dict["copy_to"] = "/opt/cluster/system/packages/RPMs"
    long_package_name = None
    delete, list_grps = (False, False)
    script_dict = {}
    # build_package entity

    my_arg = rpm_build_tools.package_parser()
    opts = my_arg.parse_args()
    build_p = rpm_build_tools.build_package(opts)
    if False:
        print opts
        if not opts:
            opts = [("-h", None)]
        for opt, arg in opts:
            if opt in ["-h", "--help"]:
                print "Usage: %s [ OPTIONS ] FILES/DIRS" % (os.path.basename(sys.argv[0]))
                print "where OPTIONS is one of:"
                print "  -v VERS                  sets package version the VERS, defaults to '%s'" % (version)
                print "  -r REL                   sets package release to REL, defaults to '%s'" % (release)
                print "  -n NAME                  sets package name to NAME"
                print "  -G GRP                   sets package group to GRP, defaults to '%s'" % (package_group)
                print "  -a ARCH                  sets package architecture to ARCH, default is '%s'" % (build_p["arch"])
                print "  -D dist_dir              sets distribution directory, default to %s" % (config_dict["dist_dir"])
                print "  -C copy_to_dir           copy package to directory, defaults to %s" % (config_dict["copy_to"])
                print "  -l [NAME|ALL]            lists one or all installable packages"
                print "  -P package_name          parses package and inserts it into the database"
                print "  -s summary               sets the package summary; defaults to '%s'" % (build_p["summary"])
                print "  -d description           sets the package description; defaults to '%s'" % (build_p["description"])
                print "  -u user                  user for package-files, default is %s" % (build_p["user"])
                print "  -g group                 group for package-files, default is %s" % (build_p["group"])
                print "  -L                       list all known groups"
                print "  -m                       no SQL server (default: yes)"
                print "  --doc DOC_PF             comma-separated list of path-parts to define doc-files, default is %s" % (",".join(build_p["doc_dirs"]))
                print "  --exclude-dir-names EXC_DIRS comma-separated list of directory names to exclude (example .svn)"
                print "  --del                    deletes all matching packages found in database"
                for script_t in rpm_build_tools.SCRIPT_TYPES:
                    print "  %-24s %s" % ("--%s-script FILE" % (script_t),
                                          "reads %s-script content from file (or use FILE as value if FILE startswith a ':' [then a double-semicolon is the line-delimeter])" % (script_t))
                print " FILES/DIRS is a space delimeted list of (SRC[:DST]|!SRC) pairs"
                print "example:"
                print "%s -v 2.4 -r 3 -n atlas -G System/Libraries /opt/libs/atlas-2.4.3:/opt/libs/atlas-default /tmp/bla !/tmp/bla/false_config.cnf" % (os.path.basename(sys.argv[0]))
                print "%s -n bla -v 1.0 --del" % (os.path.basename(sys.argv[0]))
                if dc:
                    dc.release()
                sys.exit(1)
            if opt == "--exclude-dir-names":
                config_dict["exc_dir_names"] = [part.strip() for part in arg.split(",") if part.strip()]
            if opt == "--doc":
                build_p["doc_dirs"] = [x.strip() for x in arg.split(",")]
            if opt == "-m":
                sql_server = False
            if opt == "-L":
                list_grps = True
            if opt == "--del":
                delete = True
            # if opt == "-G":
            #    package_group = arg
            if opt == "-l":
                list_arg = arg.split(",")
            if opt == "-P":
                long_package_name = arg
            if opt == "-C":
                config_dict["copy_to"] = arg
            if opt == "-D":
                config_dict["dist_dir"] = arg
    # if not sql_server and dc:
    #    dc.release()
    #    dc = None
    # if release == "AUTO_INCR":
    #    print "AUTO_INCR as release specified (SQL-connection required)"
    # if not dc and (list_arg or list_grps or delete or release == "AUTO_INCR"):
    #    print "No (needed) SQL Server connection"
    #    sys.exit(5)
    # # pwd_field = pwd.getpwnam(os.getlogin())
    if not long_package_name:
        if False:
            build_it = False
            if list_grps:
                list_groups(dc)
            elif list_arg:
                list_packages(list_arg, dc)
            else:
                if not name:
                    print "Need package name !"
                    print "try %s -h for help" % (os.path.basename(sys.argv[0]))
                else:
                    if delete:
                        delete_package(dc, name, version, release)
                    else:
                        build_it = True
        build_it = True
        if build_it:
            act_cl = rpm_build_tools.file_content_list(opts.args) # , exclude_dir_names=config_dict["exc_dir_names"])
            if not act_cl:
                print "Need a file and/or directory-list !"
                if dc:
                    dc.release()
                sys.exit(-1)
            act_cl.show_content()
            # if release == "AUTO_INCR":
            #    release = check_auto_incr_release(dc, name, version)
            if dc:
                sql_str = "SELECT p.pgroup, COUNT(DISTINCT p.package_idx) AS c FROM inst_package ip, package p WHERE ip.package=p.package_idx GROUP BY p.pgroup"
                dc.execute(sql_str)
                all_g = [x["pgroup"] for x in dc.fetchall()]
                if not package_group in all_g:
                    print "Package Group '%s' is new (already existing: %s); continue ?" % (package_group, ", ".join(all_g) or "<none>")
                    ret = None
                    while ret not in ["yes", "no"]:
                        ret = getinput(" - [yes/no]")
                        if ret == "no":
                            build_it = False
                        elif ret == "yes":
                            break
        if build_it:
            # build_p["version"] = version
            # build_p["release"] = release
            # build_p["name"] = name
            # build_p["package_group"] = package_group
            # set scripts
            for key, value in script_dict.iteritems():
                build_p[key] = value
            build_p.create_tgz_file(act_cl)
            build_p.write_specfile(act_cl)
            build_p.build_package()
            if build_p.build_ok:
                if dc:
                    print "Success, insert info into database..."
                else:
                    print "Success, local mode"
                long_package_name = build_p.long_package_name
                print "Package locations:"
                print build_p.long_package_name
                print build_p.src_package_name
            else:
                print "Build went wrong, exiting"
                build_it = False
        if not build_it:
            if dc:
                dc.release()
            sys.exit(0)
    short_package_name = os.path.basename(long_package_name)
    if dc:
        p_idx = None
        stat, out = commands.getstatusoutput("/usr/local/sbin/insert_package_info.py -p %s" % (long_package_name))
        if stat:
            print "Some error occured (%d) : " % (stat)
            for line in [x.strip() for x in out.split("\n")]:
                print "    %s" % (line)
            if dc:
                dc.release()
            sys.exit(3)
        else:
            for line in [x.strip() for x in out.split("\n")]:
                if line.startswith("pidx"):
                    p_idx = int(line.split()[1])
                elif line.startswith("pname"):
                    name = line.split(None, 1)[1]
        # p_idx now holds the index of the package
        if p_idx is None:
            print "Can't get db-index of package info %s" % (long_package_name)
            if dc:
                dc.release()
            sys.exit(2)
        if dc:
            # read name, version and release from db
            dc.execute("SELECT p.name, p.version, p.release, p.buildhost, p.packager FROM package p WHERE p.package_idx=%d" % (p_idx))
            db_stuff = dc.fetchone()
            name, version, release = (db_stuff["name"], db_stuff["version"], db_stuff["release"])
            set_dict = {"package"    : p_idx,
                        "location"   : os.path.normpath("%s/%s" % (config_dict["dist_dir"], short_package_name)),
                        "last_build" : time.time()}
            write_entry = check_for_association(dc, p_idx, name, version, release, set_dict)
            if write_entry:
                sql_str, sql_tuple = ("INSERT INTO inst_package SET %s" % (", ".join(["%s=%%s" % (key) for key in set_dict.keys()])),
                                      tuple([set_dict[key] for key in set_dict.keys()]))
                ok = dc.execute(sql_str, sql_tuple)
                if not ok:
                    print "Error: something went wrong while inserting info into inst_package: %s" % (sql_str)
        if config_dict["copy_to"]:
            if os.path.isdir(config_dict["copy_to"]):
                if os.path.normpath("%s/%s" % (os.getcwd(), long_package_name)) == os.path.normpath("%s/%s" % (config_dict["copy_to"], short_package_name)):
                    # same file, no copy
                    pass
                else:
                    print "Copying %s to %s/%s ..." % (short_package_name, config_dict["copy_to"], short_package_name)
                    try:
                        shutil.copy2(long_package_name, "%s/%s" % (config_dict["copy_to"], short_package_name))
                    except:
                        print "An error occured: %s" % (process_tools.get_except_info())
            else:
                print "Error: target directory '%s' does not exist " % (config_dict["copy_to"])
    if dc:
        dc.release()
    print "done"

if __name__ == "__main__":
    # print "not ready right now, please wait for rewrite"
    # sys.exit(1)
    main()

