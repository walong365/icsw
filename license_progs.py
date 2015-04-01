#!/usr/bin/python-init -Ot
# -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2005,2007 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
# 
# This file is part of rms-tools
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
import getopt
import os
import os.path
import re
import time
import sge_license_tools
import logging_tools

LIC_VERSION = 0.3

def parse_sge_file(lines):
    new_lines = []
    new_line = ""
    for line in [x.strip() for x in lines.split("\n") if x.strip()]:
        if line.endswith("\\"):
            new_line += (line[:-1]).strip()
        else:
            new_line += line
            new_lines.append(new_line)
            new_line = ""
    return dict([(x[0], x[1]) for x in [y.split(None, 1) for y in new_lines]])

def create_sge_file(fname, in_dict):
    open(fname, "w").write("\n".join(["%s %s" % (k, v) for k, v in in_dict.iteritems()] + [""]))
    
def append_to_site_license_file(base_dir, act_site, new_licenses):
    lic_file = "%s/lic_%s.conf" % (base_dir, act_site)
    try:
        ap_file = open(lic_file, "a")
    except IOError, what:
        print "Cannot append to site-license file %s: %s" % (lic_file, what)
    else:
        if new_licenses:
            new_lic_names = sorted(new_licenses.keys())
            print "Appending %d new licenses to site-license file %s" % (len(new_lic_names), lic_file)
            ap_file.write("\n".join(["#",
                                     "# %d licenses added %s" % (len(new_lic_names), time.ctime()),
                                     "#"]))
            form_str = "%-40s %-40s %-40s %s\n"
            ap_file.write("#\n%s#\n" % (form_str % ("#license", "lic_server_setting", "attribute", "total")))
            for new_lic_name in new_lic_names:
                nl_stuff = new_licenses[new_lic_name]
                ap_file.write(form_str % ("#lic_%s_%s" % (act_site, new_lic_name),
                                          nl_stuff.get_lic_server_spec(),
                                          nl_stuff.get_attribute(),
                                          str(nl_stuff.get_total_num())))
        ap_file.close()
        
def main():
    prog_name = os.path.basename(sys.argv[0]).split(".")[0]
    glob_short_options = "hb:s:"
    glob_long_options = ["version", "help"]
    try:
        opts, args = getopt.getopt(sys.argv[1:], glob_short_options, glob_long_options)
    except getopt.GetoptError, why:
        print "Error parsing commandline %s: %s" % (" ".join(sys.argv[1:]), why)
        sys.exit(-1)
    base_dir, act_site = ("/etc/sysconfig/licenses", "")
    act_conf = sge_license_tools.DEFAULT_CONFIG
    for opt, arg in opts:
        if opt in ["-h", "--help"]:
            print "Usage: %s [OPTIONS]" % (prog_name)
            print "  where options is one or more of"
            print "    -h, --help        this help"
            print "    --version         show program version"
            print "    -b BASEDIR        sets basedir, default is actual dir (%s)" % (base_dir)
            print "    -s SITE           select site"
            print "config file syntax is:"
            print "  [KEY] [VALUE]       where key is one of (with default):"
            for k, v in act_conf.iteritems():
                print "%s%-20s : %s" % (" " * 22, k, v and v or "<no default value>")
            sys.exit(0)
        if opt == "--version":
            print "%s, version is %s" % (prog_name, LIC_VERSION)
            sys.exit(0)
        if opt == "-b":
            if not os.path.isdir(arg):
                print "Error: basedir '%s' is not a directory" % (arg)
                sys.exit(-1)
            else:
                base_dir = os.path.normpath(arg)
        if opt == "-s":
            if arg.strip():
                act_site = arg.strip()
            else:
                print "Error parsing site-string '%s'" % (arg)
                sys.exit(1)
    if not os.path.isdir(base_dir):
        try:
            os.makedirs(base_dir)
        except IOError:
            print "Error creating base_dir '%s', exiting ..." % (base_dir)
            sys.exit(1)
        else:
            print "Successfully created base_dir '%s'" % (base_dir)
    valid_sites = sge_license_tools.read_site_config_file(base_dir, sge_license_tools.SITE_CONF_NAME)
    if not act_site:
        if valid_sites:
            default_site = sge_license_tools.read_default_site_file(base_dir, sge_license_tools.ACT_SITE_NAME)
            if default_site:
                if default_site in valid_sites:
                    act_site = default_site
                else:
                    print "Default site '%s' not found in lic_SITES.conf, exiting" % (default_site)
                    sys.exit(1)
            else:
                act_site = valid_sites[0]
                print "No site given and no default site defined, taking first (%s) from list (%s)" % (act_site, ", ".join(valid_sites))
        else:
            print "No site given and no sites found in lic_SITES.conf, exiting"
            sys.exit(1)
    if act_site in valid_sites:
        pass
    else:
        print "Error, given site %s not in list of valid sites: %s" % (act_site, ", ".join(valid_sites))
        sys.exit(2)
    print "%s, running in basedir %s" % (prog_name, base_dir)
    sge_license_tools.parse_site_config_file(base_dir, act_site, act_conf)
    needed_keys_dict = {"lic_fetch" : ["LM_UTIL_COMMAND", "LM_UTIL_PATH"]}
    if prog_name in needed_keys_dict.keys():
        failed_keys, empty_keys = ([], [])
        for nk in needed_keys_dict[prog_name]:
            if nk not in act_conf.keys():
                failed_keys.append(nk)
            elif not act_conf[nk]:
                empty_keys.append(nk)
        if failed_keys:
            print "the following keys are missing: %s" % (", ".join(failed_keys))
            sys.exit(2)
        if empty_keys:
            print "the following keys are empty: %s" % (", ".join(empty_keys))
            sys.exit(2)
    if prog_name == "lic_fetch":
        lmstat_command = "lmstat -a"
        if act_conf["LICENSE_FILE"]:
            lmstat_command += " -c %s" % (act_conf["LICENSE_FILE"])
        if not os.path.isdir(act_conf["LM_UTIL_PATH"]):
            print "Error: LM_UTIL_PATH '%s' is not directory" % (act_conf["LM_UTIL_PATH"])
            sys.exit(-1)
        stat, out = sge_license_tools.call_command("%s/%s %s" % (act_conf["LM_UTIL_PATH"], act_conf["LM_UTIL_COMMAND"], lmstat_command), 1)
        stat_re = re.compile("^License server status: (?P<lic_server_spec>\S+).*$")
        users_re = re.compile("^Users of (?P<attribute>\S+): .* of (?P<total>\d+) .* of (?P<used>\d+).*$")
        out_lines = [y for y in [x.strip() for x in out.split("\n")] if y]
        act_lic_server_settings = ""
        act_licenses = {}
        for line in out_lines:
            stat_mo, users_mo = (stat_re.match(line),
                                 users_re.match(line))
            if stat_mo:
                act_lic_server_settings = stat_mo.group("lic_server_spec")
            if users_mo:
                attribute, total, used = (users_mo.group("attribute"),
                                          int(users_mo.group("total")),
                                          int(users_mo.group("used")))
                if not act_lic_server_settings:
                    print "Warning, found valid attribute_line but no adjacent host_line"
                else:
                    new_lic = sge_license_tools.sge_license(attribute,
                                                            license_server=act_lic_server_settings,
                                                            license_type="simple")
                    new_lic.set_total_num(total)
                    new_lic.set_used_num(used)
                    act_licenses[new_lic.get_name()] = new_lic
        old_license_file = sge_license_tools.read_site_license_file(base_dir, act_site)
        old_licenses = sge_license_tools.parse_license_lines(old_license_file, act_site)
        print "Discovered %d licenses, %d of them are in use" % (len(old_licenses.keys()), len([1 for x in old_licenses.values() if x.get_is_used()]))
        new_licenses = {}
        # check for new attributes
        for al_name in sorted(act_licenses.keys()):
            if not old_licenses.has_key(al_name):
                al_stuff = act_licenses[al_name]
                print "discovered new license %s (%s, %d)" % (al_stuff.get_name(), al_stuff.get_attribute(), al_stuff.get_total_num())
                new_licenses[al_name] = al_stuff
        if new_licenses:
            append_to_site_license_file(base_dir, act_site, new_licenses)
    elif prog_name == "lic_config":
        if not os.environ.has_key("SGE_ROOT"):
            print "Error, no SGE_ROOT environment variable set"
            sys.exit(1)
        if not os.environ.has_key("SGE_CELL"):
            print "Error, no SGE_CELL environment variable set"
            sys.exit(1)
        sge_root, sge_cell = (os.environ["SGE_ROOT"],
                              os.environ["SGE_CELL"])
        arch_util = "%s/util/arch" % (sge_root)
        if not os.path.isfile(arch_util):
            print "No arch-utility found in %s/util" % (sge_root)
            sys.exit(1)
        sge_stat, sge_arch = sge_license_tools.call_command(arch_util)
        sge_arch = sge_arch.strip()
        print "SGE_ROOT is %s, SGE_CELL is %s, SGE_ARCH is %s" % (sge_root, sge_cell, sge_arch)
        qconf_bin = "%s/bin/%s/qconf" % (sge_root, sge_arch)
        if not os.path.isfile(qconf_bin):
            print "No qconf command found under %s" % (sge_root)
        # modify complexes
        complex_stat, complex_out = sge_license_tools.call_command("%s -sc" % (qconf_bin), 1)
        defined_complexes = [y for y in [x.strip() for x in complex_out.split("\n")] if y and not y.startswith("#")]
        defined_complex_names = [x.split()[0] for x in defined_complexes]
        actual_license_file = sge_license_tools.read_site_license_file(base_dir, act_site)
        actual_licenses = sge_license_tools.parse_license_lines(actual_license_file, act_site)
        licenses_to_use = [x.get_name() for x in actual_licenses.values() if x.get_is_used()]
        temp_file_name = "/tmp/.sge_new_complexes."
        temp_file = open(temp_file_name, "w")
        temp_file.write("\n".join(defined_complexes + [""]))
        form_str = "%s %s INT <= YES YES 0 0\n"
        for new_lic_name in licenses_to_use:
            if new_lic_name not in defined_complex_names:
                new_lic = actual_licenses[new_lic_name]
                temp_file.write(form_str % (new_lic_name, new_lic_name))
        temp_file.close()
        complex_stat, complex_out = sge_license_tools.call_command("%s -Mc %s" % (qconf_bin, temp_file_name), 1, 1)
        os.unlink(temp_file_name)
        # modify global execution host
        geh_stat, geh_out = sge_license_tools.call_command("%s -se global" % (qconf_bin), 1)
        geh_dict = parse_sge_file(geh_out)
        if geh_dict["complex_values"] == "NONE":
            geh_complexes = {}
        else:
            geh_complexes = dict([(k, v) for k, v in [x.split("=") for x in geh_dict["complex_values"].split(",")]])
        for new_lic_name in licenses_to_use:
            if new_lic_name not in geh_complexes.keys():
                geh_complexes[new_lic_name] = str(actual_licenses[new_lic_name].get_total_num())
        if geh_complexes:
            geh_dict["complex_values"] = ",".join(["%s=%s" % (k, v) for k, v in geh_complexes.iteritems()])
        # kill unused entries
        for kk in ["load_values", "processors"]:
            if geh_dict.has_key(kk):
                del geh_dict[kk]
        temp_file_name = "/tmp/.sge_geh_definition."
        create_sge_file(temp_file_name, geh_dict)
        geh_stat, geh_out = sge_license_tools.call_command("%s -Me %s" % (qconf_bin, temp_file_name), 1)
        os.unlink(temp_file_name)
    else:
        print "Unknown program-mode %s" % (prog_name)
        sys.exit(-1)
        
if __name__ == "__main__":
    main()
