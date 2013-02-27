#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008,2012 Andreas Lang-Nevyjel, init.at
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

import sys
import re
import os
import commands
from initat.host_monitoring import limits
from initat.host_monitoring import hm_classes
import logging_tools
import warnings
#warnings.filterwarnings("ignore")
import rpm_module

class my_modclass(hm_classes.hm_fileinfo):
    def __init__(self, **args):
        hm_classes.hm_fileinfo.__init__(self,
                                        "rpm",
                                        "provides a simple interface to the rpm-database",
                                        **args)
    def process_client_args(self, opts, hmb):
        ok, why = (1, "")
        my_lim = limits.limits()
        for opt, arg in opts:
            #print opt, arg
            if hmb.name == "rpmlist":
                if opt in ("-r", "--raw"):
                    my_lim.set_add_flags("R")
                elif opt == "-R":
                    rpm_root_dir = arg
        return ok, why, [my_lim]

class rpmlist_command(hm_classes.hmb_command):
    def __init__(self, **args):
        hm_classes.hmb_command.__init__(self, "rpmlist", **args)
        self.help_str = "returns the rpm-database of the given root-directory"
        self.short_client_info = "-r, --raw"
        self.long_client_info = "sets raw-output (for scripts) or list-mode"
        self.short_client_opts = "r"
        self.long_client_opts = ["raw"]
    def server_call(self, cm):
        if os.path.isfile("/etc/debian_version"):
            is_debian = True
        else:
            is_debian = False
        rpm_root_dir, re_strs = ("/", [])
        if len(cm):
            for arg in cm:
                if arg.startswith("/"):
                    rpm_root_dir = arg
                else:
                    re_strs.append(arg)
        if is_debian:
            self.log("Starting dpkg -l command for root_dir '%s' (%d regexp_strs: %s)" % (rpm_root_dir, len(re_strs), ", ".join(re_strs)))
        else:
            self.log("Starting rpm-list command for root_dir '%s' (%d regexp_strs: %s)" % (rpm_root_dir, len(re_strs), ", ".join(re_strs)))
        log_list, ret_dict, stat = rpmlist_int(rpm_root_dir, re_strs, is_debian)
        for log in log_list:
            self.log(log)
        if not stat:
            return "ok %s" % (hm_classes.sys_to_net(is_debian and {"format"    : "debian",
                                                                   "dpkg_dict" : ret_dict} or {"format"   : "rpm",
                                                                                               "rpm_dict" : ret_dict}))
        else:
            return "error (%d) : %s" % (stat, ret_dict)
    def client_call(self, result, parsed_coms):
        lim = parsed_coms[0]
        raw_output = lim.get_add_flag("R")
        if raw_output:
            return limits.nag_STATE_OK, result
        else:
            if result.startswith("ok "):
                r_dict = hm_classes.net_to_sys(result[3:])
                if len(r_dict.keys()) == 2 and r_dict.has_key("format"):
                    in_format = r_dict["format"]
                    if in_format == "rpm":
                        r_dict = r_dict["rpm_dict"]
                    else:
                        r_dict = r_dict["dpkg_dict"]
                else:
                    in_format = "rpm"
                out_f = logging_tools.form_list()
                keys = sorted(r_dict.keys())
                header_line = "%s found, system is %s" % (logging_tools.get_plural("package", len(keys)),
                                                          in_format)
                if keys:
                    if in_format == "rpm":
                        out_f.set_format_string(1, "s", "", "", " .")
                        out_f.set_format_string(3, "s", "", "(", ")")
                        out_f.set_format_string(4, "s", "")
                        for key in keys:
                            for value in r_dict[key]:
                                if type(value) == type(()):
                                    if len(value) == 4:
                                        ver, rel, arch, summary = value
                                        size = 0
                                    else:
                                        ver, rel, arch, size, summary = value
                                else:
                                    ver, rel, arch, size, summary = (value["version"],
                                                                     value["release"],
                                                                     value["arch"],
                                                                     value["size"],
                                                                     value["summary"])
                                out_f.add_line((key, ver, rel, arch, size, summary))
                        return limits.nag_STATE_OK, "%s\n%s" % (header_line, str(out_f))
                    elif in_format == "debian":
                        out_f.set_format_string(1, "s", "", "< ", " |")
                        out_f.set_format_string(2, "s", "", "", " |")
                        out_f.set_format_string(4, "s", "", " >", " .")
                        out_f.set_format_string(5, "s", "-")
                        for key in keys:
                            for value in r_dict[key]:
                                d_flag, s_flag, e_flag = value["flags"]
                                ver, rel = (value["version"], value["release"])
                                summary = value["summary"]
                                out_f.add_line((key, d_flag, s_flag, e_flag, ver, rel, summary))
                        return limits.nag_STATE_OK, "%s\n%s" % (header_line, str(out_f))
                else:
                    return limits.nag_STATE_WARNING, header_line
            else:
                return limits.nag_STATE_CRITICAL, "error parsing rpm list (len %d)" % (len(result))

def rpmlist_int(rpm_root_dir, re_strs, is_debian):
    if is_debian:
        log_list = ["doing dpkg -l command in dir %s" % (rpm_root_dir)]
        if rpm_root_dir:
            rpm_coms = ['chroot %s dpkg -l' % (rpm_root_dir),
                        'dpkg --root=%s -l' % (rpm_root_dir)]
        else:
            rpm_coms = ['dpkg -l']
        for rpm_com in rpm_coms:
            log_list.append("  dpkg-command is %s" % (rpm_com.strip()))
            stat, ipl = commands.getstatusoutput(rpm_com)
            if not stat:
                ret_dict = {}
                lines = ipl.split("\n")
                while True:
                    line = lines.pop(0)
                    if line.count("=") > 20:
                        break
                for line in lines:
                    try:
                        flags, name, verrel, info = line.split(None, 3)
                    except:
                        pass
                    else:
                        if verrel.count("-"):
                            ver, rel = verrel.split("-", 1)
                        else:
                            ver, rel = (verrel, "0")
                        if len(flags) == 2:
                            desired_flag, status_flag = flags
                            error_flag = ""
                        else:
                            desired_flag, status_flag, error_flag = flags
                        ret_dict.setdefault(name, []).append({"flags"   : (desired_flag, status_flag, error_flag),
                                                              "version" : ver,
                                                              "release" : rel,
                                                              "summary" : info})
                break
            else:
                ret_dict = ipl
    else:
        namere = re.compile("^(?P<name>\S+)\s+(?P<version>\S+)\s+(?P<release>\S+)\s+(?P<size>\S+)\s+(?P<arch>\S+)\s+(?P<summary>.*)$")
        log_list = ["doing rpm-call in dir %s, mode is %s" % (rpm_root_dir, rpm_module.rpm_module_ok() and "direct access" or "via rpm-command")]
        if rpm_module.rpm_module_ok():
            num_tot, num_match = (0, 0)
            rpm = rpm_module.get_rpm_module()
            ts = rpm_module.get_TransactionSet(rpm_root_dir)
            rpm.setVerbosity(rpm.RPMLOG_ERR)
            db_match = ts.dbMatch()
            ret_dict = {}
            for hdr in db_match:
                num_tot += 1
                new_rpm = rpm_module.rpm_package(hdr)
                add_it = 0
                if re_strs:
                    for re_str in re_strs:
                        if re.search(re_str, new_rpm.bi["name"]):
                            add_it = 1
                            break
                else:
                    add_it = 1
                if add_it:
                    num_match += 1
                    ret_dict.setdefault(new_rpm.bi["name"], []).append({"version" : new_rpm.bi["version"],
                                                                        "release" : new_rpm.bi["release"],
                                                                        "arch"    : new_rpm.bi["arch"],
                                                                        "size"    : new_rpm.bi["size"],
                                                                        "summary" : new_rpm.bi["summary"]})
            stat = 0
            log_list.append("Found %d packages (%d matches)" % (num_tot, num_match))
        else:
            if rpm_root_dir:
                rpm_coms = ['chroot %s rpm -qa --queryformat="%%{NAME} %%{VERSION} %%{RELEASE} %%{SIZE} %%{ARCH} %%{SUMMARY}\n" ' % (rpm_root_dir),
                            'rpm --root=%s -qa --queryformat="%%{NAME} %%{VERSION} %%{RELEASE} %%{SIZE} %%{ARCH} %%{SUMMARY}\n" ' % (rpm_root_dir)]
            else:
                rpm_coms = ['rpm -qa --queryformat="%{NAME} %{VERSION} %{RELEASE} %{SIZE} %{ARCH} %{SUMMARY}\n" ']
            for rpm_com in rpm_coms:
                log_list.append("  rpm-command is %s" % (rpm_com.strip()))
                stat, ipl = commands.getstatusoutput(rpm_com)
                num_tot, num_match = (0, 0)
                if not stat:
                    ret_dict = {}
                    log_list.append(" - first line is %s" % (ipl.split("\n")[0].strip()))
                    for rfp in [x for x in [namere.match(actl.strip()) for actl in ipl.split("\n")] if x]:
                        num_tot += 1
                        name = rfp.group("name")
                        add_it = 0
                        # check for re_match
                        if re_strs:
                            for re_str in re_strs:
                                if re.search(re_str, name):
                                    add_it = 1
                                    break
                        else:
                            add_it = 1
                        if add_it:
                            valid = 1
                            num_match += 1
                            ver = rfp.group("version")
                            rel = rfp.group("release")
                            try:
                                size = int(rfp.group("size"))
                            except:
                                valid = 0
                            arch = rfp.group("arch")
                            summary = rfp.group("summary")
                            if valid:
                                ret_dict.setdefault(name, []).append({"version" : ver,
                                                                      "release" : rel,
                                                                      "arch"    : arch,
                                                                      "size"    : size,
                                                                      "summary" : summary})
                    log_list.append("Found %d packages (%d matches)" % (num_tot, num_match))
                    break
                else:
                    ret_dict = ipl
    return log_list, ret_dict, stat
    
if __name__ == "__main__":
    print "This is a loadable module."
    sys.exit(0)
