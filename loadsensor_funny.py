#!/usr/bin/python-init -Ot
# -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2005,2007 Andreas Lang, init.at
#
# Send feedback to: <lang@init.at>
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
import time
import os
import commands
import re
import license_tools

CHECK_QUEUE = "license.q"
LOG_FILE    = "/tmp/loadsensor.log"
DEBUG = 1

class dummy_ios(object):
    def __init__(self, file_name):
        self.file_name = file_name
        self.__line_cache = ""
    def write(self, what):
        act_h = file(self.file_name, "a+")
        for x in what:
            if x == "\n":
                act_h.write("%s: %s\n" % (time.ctime(), self.line_cache))
                self.__line_cache = ""
            else:
                self.__line_cache += x
        act_h.close()
    def fileno(self):
        return 0
    def close(self):
        pass
    def __del__(self):
        pass

class error(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return self.value

class term_error(error):
    def __init__(self):
        pass
    
class alarm_error(error):
    def __init__(self):
        pass
    
class stop_error(error):
    def __init__(self):
        pass
    
class int_error(error):
    def __init__(self):
        pass

def raw_read(fd):
    ret_str = ""
    while 1:
        in_byte = os.read(fd, 1)
        if ord(in_byte) == 10:
            break
        ret_str += in_byte
    return ret_str

def write_to_sge(lines, stdout):
    act_stdout = sys.stdout
    sys.stdout = stdout
    print "\n".join(lines + [""])
    sys.stdout.flush()
    sys.stdout = act_stdout
    #print lines
    
def parse_actual_license_usage(actual_licenses, act_conf):
    configured_lics = []
    if not os.path.isdir(act_conf["LM_UTIL_PATH"]):
        print "Error: LM_UTIL_PATH '%s' is not directory" % (act_conf["LM_UTIL_PATH"])
    else:
        users_re = re.compile("^Users of (?P<attribute>\S+): .* of (?P<total>\d+) .* of (?P<used>\d+).*$")
        # build different license-server calls
        all_server_addrs = dict([("%d@%s" % (x.get_port(), x.get_host()), True) for x in actual_licenses.values()]).keys()
        all_out_lines = []
        print "asa:", all_server_addrs
        for server_addr in all_server_addrs:
            lmstat_options = "lmstat -a -c %s" % (server_addr)
            lmstat_com = "%s/%s %s" % (act_conf["LM_UTIL_PATH"],
                                       act_conf["LM_UTIL_COMMAND"],
                                       lmstat_options)
            stat, out = license_tools.call_command(lmstat_com)
            print stat, out
            if not stat:
                all_out_lines.extend([y for y in [x.strip() for x in out.split("\n")] if y])
        for line in all_out_lines:
            users_mo = users_re.match(line)
            if users_mo:
                attribute, total, used = (users_mo.group("attribute"),
                                          int(users_mo.group("total")),
                                          int(users_mo.group("used")))
                name = attribute.lower()
                act_lic = actual_licenses.get(name, None)
                if act_lic and act_lic.get_is_used():
                    configured_lics.append(name)
                    if act_lic.get_used_num() != used:
                        print "attribute %s: use_count changed from %d to %d" % (act_lic.get_attribute(),
                                                                                 act_lic.get_used_num(),
                                                                                 used)
                        act_lic.set_used_num(int(used))
    return configured_lics
                
def get_sge_reported(qs_bin, cq, configured_lics):
    sge_rep_lics = {}
    stat, out = license_tools.call_command("%s -F -q %s" % (qs_bin, cq))
    if not stat:
        lic_re = re.compile("^(?P<type>..):(?P<name>\w+)=(?P<value>\d+)$")
        for line in [x.strip() for x in out.split("\n")]:
            lic_m = lic_re.match(line)
            if lic_m:
                if lic_m.group("name") in configured_lics:
                    sge_rep_lics[lic_m.group("name")] = int(lic_m.group("value"))
    return sge_rep_lics
    
def build_sge_report_lines(configured_lics, actual_lics, sge_reported):
    lines = ["start"]
    lics_in_use = []
    for configured_lic in configured_lics:
        act_lic = actual_lics[configured_lic]
        server_free = act_lic.get_total_num() - act_lic.get_used_num()
        #print configured_lic,act_lic.get_total_num(),act_lic.get_used_num(),sge_reported.get(configured_lic, "-")
        if sge_reported.has_key(configured_lic):
            free_lics = min(server_free, sge_reported[configured_lic])
        else:
            free_lics = server_free
        if server_free != free_lics:
            lics_in_use.append(configured_lic)
        print "reporting %d free of %d for %s (server_free is %d, sge_reported is %d)" % (free_lics,
                                                                                          act_lic.get_total_num(),
                                                                                          configured_lic,
                                                                                          server_free,
                                                                                          sge_reported.get(configured_lic, -1))
        lines.append("global:%s:%d" % (configured_lic, free_lics))
    lines.append("end")
    return lines, lics_in_use

def get_used(qstat_bin):
    act_dict = {}
    job_id_re = re.compile("\d+\.*\d*")
    act_com = "%s -ne -r" % (qstat_bin)
    stat, out = commands.getstatusoutput(act_com)
    if stat:
        print "Error calling %s (%d):" % (act_com, stat)
        for line in out.split("\n"):
            print " - %s" % (line.rstrip())
    else:
        act_job_mode = "?"
        for line_parts in [x.strip().split() for x in out.split("\n") if x.strip()]:
            job_id = line_parts[0]
            if job_id_re.match(job_id) and len(line_parts) >= 9:
                act_job_mode = line_parts[4]
            elif len(line_parts) >= 3:
                if ("%s %s" % (line_parts[0], line_parts[1])).lower() == "hard resources:":
                    res_name, res_value = line_parts[2].split("=")
                    if "r" in act_job_mode or "R" in act_job_mode or "t" in act_job_mode:
                        dict_name = "used"
                    else:
                        dict_name = "requested"
                    act_dict.setdefault(dict_name, {}).setdefault(res_name, 0)
                    try:
                        res_value = int(res_value)
                    except ValueError:
                        pass
                    else:
                        act_dict[dict_name][res_name] += res_value
    return act_dict
                
def main():
    # change IO-descriptors
    sge_stdout, sge_stderr = (sys.stdout, sys.stderr)
    sys.stdout = dummy_ios(LOG_FILE)
    sys.stderr = dummy_ios(LOG_FILE)
    base_dir = "/etc/sysconfig/licenses"
    my_pid = os.getpid()
    print "starting for pid %d, base_dir is %s" % (my_pid, base_dir)
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
    sge_arch = commands.getoutput(arch_util)
    print "SGE_ROOT is %s, SGE_CELL is %s, SGE_ARCH is %s" % (sge_root, sge_cell, sge_arch)
    act_site = license_tools.read_default_site_file(base_dir, license_tools.ACT_SITE_NAME)
    if not act_site:
        print "Actual site not defined, exiting..."
        sys.exit(1)
    act_conf = license_tools.DEFAULT_CONFIG
    license_tools.parse_site_config_file(base_dir, act_site, act_conf)
    print "read config for actual site '%s'" % (act_site)
    for k, v in act_conf.iteritems():
        print " - %-20s : %s" % (k, v)
    qstat_bin = "%s/bin/%s/qstat" % (sge_root, sge_arch)
    #print get_used(qstat_bin)
    call_num = 0
    io_in_fd  = sys.stdin.fileno()
    io_out_fd = sys.stdout.fileno()
    print "starting up, input handle is %d, output handle is %d" % (io_in_fd, io_out_fd)
    try:
        while 1:
            in_lines = raw_read(io_in_fd)
            call_num += 1
            if in_lines == "quit":
                print "call #%d, received '%s'" % (call_num, in_lines)
                break
            else:
                print "starting reporting load values (call #%d)" % (call_num)
                start_time = time.time()
                actual_licenses = license_tools.parse_license_lines(license_tools.read_site_license_file(base_dir, act_site), act_site)
                configured_licenses = parse_actual_license_usage(actual_licenses, act_conf)
                sge_reported = get_sge_reported(qstat_bin, CHECK_QUEUE, configured_licenses)
                #print sge_reported
                sge_lines, lics_in_use = build_sge_report_lines(configured_licenses, actual_licenses, sge_reported)
                write_to_sge(sge_lines, sge_stdout)
                end_time = time.time()
                print "%d licenses defined, %d configured, %d in use%s, took %.2f seconds" % (len(actual_licenses.keys()),
                                                                                              len(configured_licenses),
                                                                                              len(lics_in_use),
                                                                                              lics_in_use and " (%s)" % (", ".join(lics_in_use)) or "",
                                                                                              end_time-start_time)
    except KeyboardInterrupt:
        print "proc %d: got KeyboardInterrupt, exiting ..." % (my_pid)
    except term_error:
        print "proc %d: got term-signal, exiting ..." % (my_pid)
    except stop_error:
        print "proc %d: got stop-signal, exiting ..." % (my_pid)
    except int_error:
        print "proc %d: got int-signal, exiting ..." % (my_pid)
    print "exiting"
    print "-"*50
    # back to original IO-descriptors
    sys.stdout, sys.stderr = (sge_stdout, sge_stderr)
    
if __name__ == "__main__":
    main()
    
