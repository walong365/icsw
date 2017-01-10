# Copyright (C) 2001-2008,2012-2017 Andreas Lang-Nevyjel, Gregor Kaufmann, init.at
#
# Send feedback to: <lang-nevyjel@init.at>, <kaufmann@init.at>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
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

from __future__ import unicode_literals, print_function

import commands
import os
import re
import time

from initat.host_monitoring import hm_classes, limits
from initat.tools import logging_tools, server_command

TEST_OUTPUT_ZYPPER = """Loading repository data...
Reading installed packages...
S | Repository | Name              | Current Version | Available Version | Arch
--+------------+-------------------+-----------------+-------------------+-------
v | icsw_devel | icsw-dependencies | 3.0-330         | 3.0-331           | x86_64
v | icsw_devel | nginx-init        | 1.9.15-2        | 1.10.0-2          | x86_64
"""

TEST_OUTPUT_YUM = """
icsw-dependencies.x86_64                                                                                                                   3.0-331                                                                                                                     mainrepo
nginx-init.x86_64                                                                                                                          1.10.0-2                                                                                                                    mainrepo"""

TEST_OUTPUT_APT = """Reading package lists... Done
Building dependency tree
Reading state information... Done
The following packages will be upgraded:
  handbook-init ldb-tools libldb1 libsmbclient libunivention-config0 libwbclient0 plymouth plymouth-drm plymouth-themes-all plymouth-themes-fade-in plymouth-themes-glow plymouth-themes-script plymouth-themes-solar plymouth-themes-spinfinity plymouth-themes-spinner
  python-ldb python-modules-rrd python-samba python-univention-appcenter python-univention-config-registry python-univention-directory-manager python-univention-directory-manager-cli samba samba-common samba-common-bin samba-dsdb-modules samba-libs samba-vfs-modules
  smbclient univention-appcenter univention-appcenter-docker univention-config univention-config-registry univention-directory-manager-tools univention-errata-level univention-heimdal-common univention-heimdal-kdc univention-management-console-frontend
  univention-management-console-module-appcenter univention-management-console-module-apps univention-management-console-module-diagnostic univention-management-console-module-updater univention-management-console-web-server univention-pam univention-samba4
  univention-samba4-sysvol-sync univention-updater winbind
48 upgraded, 0 newly installed, 0 to remove and 0 not upgraded.
Inst univention-config [11.0.0-1.491.201509272107] (11.0.0-3.493.201603231553 Univention:updates.software-univention.de [all]) []
Inst python-univention-config-registry [11.0.0-1.491.201509272107] (11.0.0-3.493.201603231553 Univention:updates.software-univention.de [all])
Inst univention-config-registry [11.0.0-1.491.201509272107] (11.0.0-3.493.201603231553 Univention:updates.software-univention.de [all])
Inst univention-heimdal-kdc [9.0.1-2.159.201601062025] (9.0.1-3.160.201603222053 Univention:updates.software-univention.de [all]) []
Inst univention-heimdal-common [9.0.1-2.159.201601062025] (9.0.1-3.160.201603222053 Univention:updates.software-univention.de [all])
Inst univention-directory-manager-tools [11.0.2-23.1378.201603081544] (11.0.2-26.1381.201604191507 Univention:updates.software-univention.de [all]) []
Inst python-univention-directory-manager [11.0.2-23.1378.201603081544] (11.0.2-26.1381.201604191507 Univention:updates.software-univention.de [all]) []
Inst python-univention-directory-manager-cli [11.0.2-23.1378.201603081544] (11.0.2-26.1381.201604191507 Univention:updates.software-univention.de [all])
Inst winbind [2:4.3.3-1.833.201603071722] (2:4.3.7-1.830.201604110947 Univention:updates.software-univention.de [i386]) []
Inst libwbclient0 [2:4.3.3-1.833.201603071722] (2:4.3.7-1.830.201604110947 Univention:updates.software-univention.de [i386]) []
Inst python-ldb [2:1.1.24-1.67.201512111426] (2:1.1.25-1.72.201604061731 Univention:updates.software-univention.de [i386]) []
Inst python-samba [2:4.3.3-1.833.201603071722] (2:4.3.7-1.830.201604110947 Univention:updates.software-univention.de [i386]) []
Inst libsmbclient [2:4.3.3-1.833.201603071722] (2:4.3.7-1.830.201604110947 Univention:updates.software-univention.de [i386]) []
Inst smbclient [2:4.3.3-1.833.201603071722] (2:4.3.7-1.830.201604110947 Univention:updates.software-univention.de [i386]) []
Inst samba [2:4.3.3-1.833.201603071722] (2:4.3.7-1.830.201604110947 Univention:updates.software-univention.de [i386]) []
Inst samba-common-bin [2:4.3.3-1.833.201603071722] (2:4.3.7-1.830.201604110947 Univention:updates.software-univention.de [i386]) []
Inst samba-common [2:4.3.3-1.833.201603071722] (2:4.3.7-1.830.201604110947 Univention:updates.software-univention.de [all]) []
Inst samba-dsdb-modules [2:4.3.3-1.833.201603071722] (2:4.3.7-1.830.201604110947 Univention:updates.software-univention.de [i386]) []
Inst samba-vfs-modules [2:4.3.3-1.833.201603071722] (2:4.3.7-1.830.201604110947 Univention:updates.software-univention.de [i386]) []
Inst samba-libs [2:4.3.3-1.833.201603071722] (2:4.3.7-1.830.201604110947 Univention:updates.software-univention.de [i386]) []
Inst libldb1 [2:1.1.24-1.67.201512111426] (2:1.1.25-1.72.201604061731 Univention:updates.software-univention.de [i386])
Inst plymouth-drm [0.8.5.1-5.17.201512031309] (0.8.5.1-5.18.201602181308 Univention:updates.software-univention.de [i386]) []
Inst plymouth [0.8.5.1-5.17.201512031309] (0.8.5.1-5.18.201602181308 Univention:updates.software-univention.de [i386])
Inst ldb-tools [2:1.1.24-1.67.201512111426] (2:1.1.25-1.72.201604061731 Univention:updates.software-univention.de [i386])
Inst libunivention-config0 [11.0.0-1.491.201509272107] (11.0.0-3.493.201603231553 Univention:updates.software-univention.de [i386])
Inst plymouth-themes-fade-in [0.8.5.1-5.17.201512031309] (0.8.5.1-5.18.201602181308 Univention:updates.software-univention.de [all])
Inst plymouth-themes-glow [0.8.5.1-5.17.201512031309] (0.8.5.1-5.18.201602181308 Univention:updates.software-univention.de [all])
Inst plymouth-themes-script [0.8.5.1-5.17.201512031309] (0.8.5.1-5.18.201602181308 Univention:updates.software-univention.de [all])
Inst plymouth-themes-solar [0.8.5.1-5.17.201512031309] (0.8.5.1-5.18.201602181308 Univention:updates.software-univention.de [all])
Inst plymouth-themes-spinfinity [0.8.5.1-5.17.201512031309] (0.8.5.1-5.18.201602181308 Univention:updates.software-univention.de [all])
Inst plymouth-themes-spinner [0.8.5.1-5.17.201512031309] (0.8.5.1-5.18.201602181308 Univention:updates.software-univention.de [all])
Inst plymouth-themes-all [0.8.5.1-5.17.201512031309] (0.8.5.1-5.18.201602181308 Univention:updates.software-univention.de [all])
Inst python-univention-appcenter [5.0.20-28.139.201603160904] (5.0.20-48.161.201604261100 Univention:updates.software-univention.de [all])
Inst univention-appcenter [5.0.20-28.139.201603160904] (5.0.20-48.161.201604261100 Univention:updates.software-univention.de [all])
Inst univention-appcenter-docker [5.0.20-28.139.201603160904] (5.0.20-48.161.201604261100 Univention:updates.software-univention.de [all])
Inst univention-errata-level [4.0.0-1.1261.201604061241] (4.0.0-1.1307.201604271726 Univention:updates.software-univention.de [all])
Inst univention-management-console-frontend [5.0.63-29.1219.201603071055] (5.0.63-32.1222.201603311834 Univention:updates.software-univention.de [all])
Inst univention-management-console-module-updater [11.0.9-2.1445.201602151056] (11.0.9-5.1464.201603230907 Univention:updates.software-univention.de [all]) []
Inst univention-updater [11.0.9-2.1445.201602151056] (11.0.9-5.1464.201603230907 Univention:updates.software-univention.de [all])
Inst univention-management-console-module-appcenter [5.0.20-28.139.201603160904] (5.0.20-48.161.201604261100 Univention:updates.software-univention.de [all])
Inst univention-management-console-module-apps [5.0.20-28.139.201603160904] (5.0.20-48.161.201604261100 Univention:updates.software-univention.de [all])
Inst univention-management-console-module-diagnostic [2.0.0-4.27.201601141258] (2.0.0-5.28.201604120834 Univention:updates.software-univention.de [all])
Inst univention-management-console-web-server [5.0.63-29.1219.201603071055] (5.0.63-32.1222.201603311834 Univention:updates.software-univention.de [all])
Inst univention-samba4 [5.0.1-25.645.201601281632] (5.0.1-33.665.201604141703 Univention:updates.software-univention.de [i386]) []
Inst univention-samba4-sysvol-sync [5.0.1-25.645.201601281632] (5.0.1-33.665.201604141703 Univention:updates.software-univention.de [all])
Inst handbook-init [0.2-106] (0.2-107 init.at icsw-2.5 packages:3.1/stable [i386])
Inst python-modules-rrd [1.5.5-4] (1.6.0-3 init.at icsw-2.5 packages:3.1/stable [i386])
Inst univention-pam [9.0.0-5.267.201601111715] (9.0.0-6.268.201604140831 Univention:updates.software-univention.de [all])
Conf python-univention-config-registry (11.0.0-3.493.201603231553 Univention:updates.software-univention.de [all])
Conf univention-config (11.0.0-3.493.201603231553 Univention:updates.software-univention.de [all])
Conf univention-config-registry (11.0.0-3.493.201603231553 Univention:updates.software-univention.de [all])
Conf python-univention-directory-manager-cli (11.0.2-26.1381.201604191507 Univention:updates.software-univention.de [all])
Conf python-univention-directory-manager (11.0.2-26.1381.201604191507 Univention:updates.software-univention.de [all])
Conf univention-directory-manager-tools (11.0.2-26.1381.201604191507 Univention:updates.software-univention.de [all])
Conf univention-heimdal-common (9.0.1-3.160.201603222053 Univention:updates.software-univention.de [all])
Conf univention-heimdal-kdc (9.0.1-3.160.201603222053 Univention:updates.software-univention.de [all])
Conf libldb1 (2:1.1.25-1.72.201604061731 Univention:updates.software-univention.de [i386])
Conf python-ldb (2:1.1.25-1.72.201604061731 Univention:updates.software-univention.de [i386])
Conf libwbclient0 (2:4.3.7-1.830.201604110947 Univention:updates.software-univention.de [i386])
Conf samba-libs (2:4.3.7-1.830.201604110947 Univention:updates.software-univention.de [i386])
Conf python-samba (2:4.3.7-1.830.201604110947 Univention:updates.software-univention.de [i386])
Conf samba-common (2:4.3.7-1.830.201604110947 Univention:updates.software-univention.de [all])
Conf samba-common-bin (2:4.3.7-1.830.201604110947 Univention:updates.software-univention.de [i386])
Conf samba-dsdb-modules (2:4.3.7-1.830.201604110947 Univention:updates.software-univention.de [i386])
Conf samba (2:4.3.7-1.830.201604110947 Univention:updates.software-univention.de [i386])
Conf winbind (2:4.3.7-1.830.201604110947 Univention:updates.software-univention.de [i386])
Conf libsmbclient (2:4.3.7-1.830.201604110947 Univention:updates.software-univention.de [i386])
Conf smbclient (2:4.3.7-1.830.201604110947 Univention:updates.software-univention.de [i386])
Conf samba-vfs-modules (2:4.3.7-1.830.201604110947 Univention:updates.software-univention.de [i386])
Conf plymouth (0.8.5.1-5.18.201602181308 Univention:updates.software-univention.de [i386])
Conf plymouth-drm (0.8.5.1-5.18.201602181308 Univention:updates.software-univention.de [i386])
Conf ldb-tools (2:1.1.25-1.72.201604061731 Univention:updates.software-univention.de [i386])
Conf libunivention-config0 (11.0.0-3.493.201603231553 Univention:updates.software-univention.de [i386])
Conf plymouth-themes-fade-in (0.8.5.1-5.18.201602181308 Univention:updates.software-univention.de [all])
Conf plymouth-themes-glow (0.8.5.1-5.18.201602181308 Univention:updates.software-univention.de [all])
Conf plymouth-themes-script (0.8.5.1-5.18.201602181308 Univention:updates.software-univention.de [all])
Conf plymouth-themes-solar (0.8.5.1-5.18.201602181308 Univention:updates.software-univention.de [all])
Conf plymouth-themes-spinfinity (0.8.5.1-5.18.201602181308 Univention:updates.software-univention.de [all])
Conf plymouth-themes-spinner (0.8.5.1-5.18.201602181308 Univention:updates.software-univention.de [all])
Conf plymouth-themes-all (0.8.5.1-5.18.201602181308 Univention:updates.software-univention.de [all])
Conf python-univention-appcenter (5.0.20-48.161.201604261100 Univention:updates.software-univention.de [all])
Conf univention-appcenter (5.0.20-48.161.201604261100 Univention:updates.software-univention.de [all])
Conf univention-appcenter-docker (5.0.20-48.161.201604261100 Univention:updates.software-univention.de [all])
Conf univention-errata-level (4.0.0-1.1307.201604271726 Univention:updates.software-univention.de [all])
Conf univention-management-console-frontend (5.0.63-32.1222.201603311834 Univention:updates.software-univention.de [all])
Conf univention-updater (11.0.9-5.1464.201603230907 Univention:updates.software-univention.de [all])
Conf univention-management-console-module-updater (11.0.9-5.1464.201603230907 Univention:updates.software-univention.de [all])
Conf univention-management-console-module-appcenter (5.0.20-48.161.201604261100 Univention:updates.software-univention.de [all])
Conf univention-management-console-module-apps (5.0.20-48.161.201604261100 Univention:updates.software-univention.de [all])
Conf univention-management-console-module-diagnostic (2.0.0-5.28.201604120834 Univention:updates.software-univention.de [all])
Conf univention-management-console-web-server (5.0.63-32.1222.201603311834 Univention:updates.software-univention.de [all])
Conf univention-samba4-sysvol-sync (5.0.1-33.665.201604141703 Univention:updates.software-univention.de [all])
Conf univention-samba4 (5.0.1-33.665.201604141703 Univention:updates.software-univention.de [i386])
Conf handbook-init (0.2-107 init.at icsw-2.5 packages:3.1/stable [i386])
Conf python-modules-rrd (1.6.0-3 init.at icsw-2.5 packages:3.1/stable [i386])
Conf univention-pam (9.0.0-6.268.201604140831 Univention:updates.software-univention.de [all])
"""


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
            self.log(
                "Starting dpkg -l command for root_dir '{}' ({:d} regexp_strs{})".format(
                    rpm_root_dir,
                    len(re_strs),
                    ": {}".format(", ".join(re_strs)) if re_strs else "",
                )
            )
        else:
            self.log(
                "Starting rpm-list command for root_dir '{}' ({:d} regexp_strs{})".format(
                    rpm_root_dir,
                    len(re_strs),
                    ": {}".format(", ".join(re_strs)) if re_strs else "",
                )
            )
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
            srv_com["pkg_list"] = server_command.compress(ret_dict, pickle=True)
        else:
            srv_com["result"].set_result(
                "error getting list: {:d}".format(cur_stat),
                server_command.SRV_REPLY_STATE_ERROR
            )

    def interpret(self, srv_com, cur_ns):
        r_dict = server_command.decompress(srv_com["pkg_list"].text, pickle=True)
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
            return limits.mon_STATE_OK, "{}\n{}".format(header_line, unicode(out_f))
        else:
            return limits.mon_STATE_CRITICAL, "{}, nothing found".format(header_line)


class updatelist_command(hm_classes.hm_command):
    def __init__(self, name):
        hm_classes.hm_command.__init__(self, name, positional_arguments=True)

    def __call__(self, srv_com, cur_ns):
        s_time = time.time()
        update_list = get_update_list()
        e_time = time.time()
        srv_com.set_result(
            "ok got list in {}".format(logging_tools.get_diff_time_str(e_time - s_time)),
        )
        srv_com["update_list"] = server_command.compress(update_list, pickle=True)

    def interpret(self, srv_com, cur_ns):
        update_list = server_command.decompress(srv_com["update_list"].text, pickle=True)
        if update_list:
            return limits.mon_STATE_OK, "{}: {}".format(
                logging_tools.get_plural("update", len(update_list)),
                "\n".join(["{:} {:}".format(_name, _vers) for _name, _vers in update_list])
            )
        else:
            return limits.mon_STATE_OK, "No updates found"


def rpmlist_int(rpm_root_dir, re_strs, is_debian):
    if is_debian:
        log_list = [
            "doing dpkg -l command in dir {}".format(rpm_root_dir)
        ]
        if rpm_root_dir:
            rpm_coms = [
                'chroot {} dpkg -l'.format(rpm_root_dir),
                'dpkg --root={} -l'.format(rpm_root_dir)
            ]
        else:
            rpm_coms = ['dpkg -l']
        for rpm_com in rpm_coms:
            log_list.append(
                "  dpkg-command is {}".format(rpm_com.strip())
            )
            stat, ipl = commands.getstatusoutput(rpm_com)
            ipl = ipl.decode("utf-8")
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
        namere = re.compile("^(?P<name>\S+)\s+(?P<version>\S+)\s+(?P<release>\S+)\s+(?P<size>\S+)\s+(?P<arch>\S+)\s+(?P<installtimestamp>\S+)\s+(?P<summary>.*)$")
        log_list = [
            "doing rpm-call in dir {}, mode is {}".format(rpm_root_dir, "via rpm-command")
        ]
        if rpm_root_dir:
            rpm_coms = [
                'chroot {} rpm -qa --queryformat="%{{NAME}} %{{VERSION}} %{{RELEASE}} %{{SIZE}} %{{ARCH}} %{{INSTALLTIME}} %{{SUMMARY}}\n" '.format(rpm_root_dir),
                'rpm --root={} -qa --queryformat="%{{NAME}} %{{VERSION}} %{{RELEASE}} %{{SIZE}} %{{ARCH}} %{{INSTALLTIME}} %{{SUMMARY}}\n" '.format(rpm_root_dir),
            ]
        else:
            rpm_coms = [
                'rpm -qa --queryformat="%{NAME} %{VERSION} %{RELEASE} %{SIZE} %{ARCH} %{INSTALLTIME} %{SUMMARY}\n" '
            ]
        for rpm_com in rpm_coms:
            log_list.append("  rpm-command is {}".format(rpm_com.strip()))
            stat, ipl = commands.getstatusoutput(rpm_com)
            ipl = ipl.decode("utf-8")
            num_tot, num_match = (0, 0)
            if not stat:
                ret_dict = {}
                log_list.append(" - first line is {}".format(ipl.split("\n")[0].strip()))
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
                        installtimestamp = rfp.group("installtimestamp")
                        if valid:
                            ret_dict.setdefault(name, []).append(
                                {
                                    "version": ver,
                                    "release": rel,
                                    "arch": arch,
                                    "size": size,
                                    "installtimestamp": installtimestamp,
                                    "summary": summary
                                }
                            )
                log_list.append("Found {:d} packages ({:d} matches)".format(num_tot, num_match))
                break
            else:
                ret_dict = ipl
    return log_list, ret_dict, stat


def get_update_list():
    use_zypper = False
    use_yum = False
    use_apt = False
    if os.path.isdir("/etc/zypp"):
        use_zypper = True
    if os.path.isdir("/etc/yum"):
        use_yum = True
    if os.path.isdir("/etc/apt"):
        use_apt = True

    update_list = []

    if use_zypper:
        status, output = commands.getstatusoutput("zypper refresh")
        # todo error handling
        status, output = commands.getstatusoutput("zypper list-updates")
        # todo error handling
        lines = output.split("\n")

        start_parse = False
        for line in lines:
            if start_parse:
                line = line.strip()
                if line:
                    components = line.split("|")
                    update_list.append((components[2].strip(), components[4].strip()))

            elif line.startswith("--"):
                start_parse = True
            else:
                pass
    elif use_yum:
        status, output = commands.getstatusoutput("yum check-update -q")
        # todo error handling
        lines = output.split("\n")

        prevline = None
        for line in lines:
            line = line.strip()
            if line:
                if line.startswith("Obsoleting Packages"):
                    break
                comps = [s for s in line.split(" ") if s]
                if prevline:
                    update_list.append((prevline.strip(), comps[0].strip()))
                    prevline = None
                else:
                    if len(comps) > 1:
                        update_list.append((comps[0].strip(), comps[1].strip()))
                    else:
                        prevline = comps[0].strip()

    elif use_apt:
        status, output = commands.getstatusoutput("apt-get update")
        # todo error handling
        status, output = commands.getstatusoutput("apt-get --just-print upgrade")
        # todo error handling

        lines = output.split("\n")
        for line in lines:
            if line.startswith("Inst"):
                comps = line.split(" ")
                update_list.append((comps[1], comps[3][1:]))

    return update_list
