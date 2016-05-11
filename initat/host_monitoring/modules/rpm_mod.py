# Copyright (C) 2001-2008,2012-2015 Andreas Lang-Nevyjel, init.at
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

import base64
import commands
import marshal
import os
import re
import time
import bz2
import pickle

from initat.host_monitoring import hm_classes
from initat.host_monitoring import limits
from initat.tools import logging_tools, server_command


class _general(hm_classes.hm_module):
    pass


class rpmlist_command(hm_classes.hm_command):
    info_str = "rpm list"

    def __init__(self, name):
        hm_classes.hm_command.__init__(self, name, positional_arguments=True)

    def __call__(self, srv_com, cur_ns):
        if os.path.isfile("/etc/debian_version"):
            is_debian = True
        else:
            is_debian = False
        rpm_root_dir, re_strs = ("/", [])
        if len(cur_ns.arguments):
            for arg in cur_ns.arguments:
                if arg.startswith("/"):
                    rpm_root_dir = arg
                else:
                    re_strs.append(arg)
        if is_debian:
            self.log("Starting dpkg -l command for root_dir '%s' (%d regexp_strs: %s)" % (rpm_root_dir, len(re_strs), ", ".join(re_strs)))
        else:
            self.log("Starting rpm-list command for root_dir '%s' (%d regexp_strs: %s)" % (rpm_root_dir, len(re_strs), ", ".join(re_strs)))
        s_time = time.time()
        log_list, ret_dict, cur_stat = rpmlist_int(rpm_root_dir, re_strs, is_debian)
        e_time = time.time()
        for log in log_list:
            self.log(log)
        if not cur_stat:
            srv_com.set_result(
                "ok got list in {}".format(logging_tools.get_diff_time_str(e_time - s_time)),
            )
            srv_com["root_dir"] = rpm_root_dir
            srv_com["format"] = "deb" if is_debian else "rpm"
            srv_com["pkg_list"] = base64.b64encode(bz2.compress(pickle.dumps(ret_dict)))
        else:
            srv_com["result"].set_result(
                "error getting list: {:d}".format(cur_stat),
                server_command.SRV_REPLY_STATE_ERROR
            )

    def interpret(self, srv_com, cur_ns):
        r_dict = pickle.loads(bz2.decompress(base64.b64decode(srv_com["pkg_list"].text)))
        root_dir = srv_com["root_dir"].text
        in_format = srv_com["format"].text
        out_f = logging_tools.new_form_list()
        keys = sorted(r_dict.keys())
        header_line = "{} found, system is {} (root is {})".format(
            logging_tools.get_plural("package", len(keys)),
            in_format,
            root_dir,
        )
        if keys:
            if in_format == "rpm":
                for key in keys:
                    for value in r_dict[key]:
                        if type(value) is tuple:
                            if len(value) == 4:
                                ver, rel, arch, summary = value
                                size = 0
                            else:
                                ver, rel, arch, size, summary = value
                        else:
                            ver, rel, arch, size, summary = (
                                value["version"],
                                value["release"],
                                value["arch"],
                                value["size"],
                                value["summary"]
                            )
                        out_f.append(
                            [
                                logging_tools.form_entry(key, header="name"),
                                logging_tools.form_entry_right(ver, header="version"),
                                logging_tools.form_entry(rel, header="release"),
                                logging_tools.form_entry(arch, header="arch"),
                                logging_tools.form_entry_right(size, header="size"),
                                logging_tools.form_entry(summary, header="summary"),
                            ]
                        )
            elif in_format == "debian":
                for key in keys:
                    for value in r_dict[key]:
                        d_flag, s_flag, e_flag = value["flags"]
                        ver, rel = (value["version"], value["release"])
                        summary = value["summary"]
                        out_f.append(
                            [
                                logging_tools.form_entry(key, header="name"),
                                logging_tools.form_entry_right(d_flag, header="d_flag"),
                                logging_tools.form_entry_right(s_flag, header="s_flag"),
                                logging_tools.form_entry_right(e_flag, header="e_flag"),
                                logging_tools.form_entry_right(ver, header="version"),
                                logging_tools.form_entry(rel, header="release"),
                                logging_tools.form_entry(summary, header="summary"),
                            ]
                        )
                        out_f.add_line((key, d_flag, s_flag, e_flag, ver, rel, summary))
            return limits.nag_STATE_OK, "{}\n{}".format(header_line, str(out_f))
        else:
            return limits.nag_STATE_CRITICAL, "{}, nothing found".format(header_line)


def rpmlist_int(rpm_root_dir, re_strs, is_debian):
    if is_debian:
        log_list = ["doing dpkg -l command in dir %s" % (rpm_root_dir)]
        if rpm_root_dir:
            rpm_coms = [
                'chroot %s dpkg -l' % (rpm_root_dir),
                'dpkg --root=%s -l' % (rpm_root_dir)
            ]
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
                        ret_dict.setdefault(name, []).append({
                            "flags": (desired_flag, status_flag, error_flag),
                            "version": ver,
                            "release": rel,
                            "summary": info})
                break
            else:
                ret_dict = ipl
    else:
        namere = re.compile("^(?P<name>\S+)\s+(?P<version>\S+)\s+(?P<release>\S+)\s+(?P<size>\S+)\s+(?P<arch>\S+)\s+(?P<summary>.*)$")
        log_list = ["doing rpm-call in dir %s, mode is %s" % (rpm_root_dir, "via rpm-command")]
        if rpm_root_dir:
            rpm_coms = [
                'chroot %s rpm -qa --queryformat="%%{NAME} %%{VERSION} %%{RELEASE} %%{SIZE} %%{ARCH} %%{SUMMARY}\n" ' % (rpm_root_dir),
                'rpm --root=%s -qa --queryformat="%%{NAME} %%{VERSION} %%{RELEASE} %%{SIZE} %%{ARCH} %%{SUMMARY}\n" ' % (rpm_root_dir)
            ]
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
                            ret_dict.setdefault(name, []).append(
                                {
                                    "version": ver,
                                    "release": rel,
                                    "arch": arch,
                                    "size": size,
                                    "summary": summary
                                }
                            )
                log_list.append("Found %d packages (%d matches)" % (num_tot, num_match))
                break
            else:
                ret_dict = ipl
    return log_list, ret_dict, stat
