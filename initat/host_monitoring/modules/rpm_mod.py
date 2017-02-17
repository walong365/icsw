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

import os
import re
import subprocess
import time

from initat.constants import PLATFORM_SYSTEM_TYPE, PlatformSystemTypeEnum
from .. import hm_classes, limits
from initat.tools import logging_tools, server_command
from ..constants import HMAccessClassEnum

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


class ModuleDefinition(hm_classes.MonitoringModule):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        required_access = HMAccessClassEnum.level0
        uuid = "825f08c8-c83c-43f8-bc76-cf9e2a56334d"


class installedupdates_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.WINDOWS
        required_access = HMAccessClassEnum.level0
        uuid = "e2e456ea-d358-4e52-8d5f-0d5ac9ac0ba4"
        description = "Installed updates on {} machines".format(PlatformSystemTypeEnum.WINDOWS.name)
        create_mon_check_command = False

    class Update:
        def __init__(self):
            self.title = None
            self.status = None
            self.date = None

        def __lt__(self, other):
            return self.date < other.date

        def __eg__(self, other):
            return self.date == other.date

    def __call__(self, srv_com, cur_ns):
        installed_updates = []
        if PLATFORM_SYSTEM_TYPE == PlatformSystemTypeEnum.WINDOWS:
            import win32com.client
            import pywintypes

            update = win32com.client.Dispatch('Microsoft.Update.Session')
            update_searcher = update.CreateUpdateSearcher()
            count = update_searcher.GetTotalHistoryCount()

            update_history = update_searcher.QueryHistory(0, count)

            for i in range(update_history.Count):
                update = installedupdates_command.Update()
                update.title = update_history.Item(i).Title
                update.date = update_history.Item(i).Date
                try:
                    update.status = update_history.Item(i).ResultCode
                except pywintypes.com_error:
                    update.status = "Unknown"

                if update.status == 0:
                    update.status = "NotStarted"
                elif update.status == 1:
                    update.status = "InProgress"
                elif update.status == 2:
                    update.status = "Succeeded"
                elif update.status == 3:
                    update.status = "SucceededWithErrors"
                elif update.status == 4:
                    update.status = "Failed"
                elif update.status == 5:
                    update.status = "Aborted"

                installed_updates.append(update)

        installed_updates = [(update.title, update.date.isoformat(), update.status) for update in installed_updates]
        srv_com["installed_updates"] = server_command.compress(installed_updates, pickle=True)


class rpmlist_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        required_access = HMAccessClassEnum.level0
        uuid = "46d060f7-3c7f-4620-9436-0a1b14999c26"
        description = "Returns a list of installed packages and software (plus various meta information)"
        create_mon_check_command = False

    class Package:
        def __init__(self):
            self.displayName = "Unknown"
            self.displayVersion = "Unknown"
            self.estimatedSize = "Unknown"
            self.installDate = "Unknown"

        def __lt__(self, other):
            return self.displayName < other.displayName

        def __eq__(self, other):
            return self.displayName == other.displayName

        def __hash__(self):
            return hash((self.displayName, self.displayVersion, self.estimatedSize, self.installDate))

    def __call__(self, srv_com, cur_ns):
        if PLATFORM_SYSTEM_TYPE == PlatformSystemTypeEnum.WINDOWS:
            uninstall_path1 = "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall"
            uninstall_path2 = "SOFTWARE\\Wow6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall"

            import winreg

            def get_installed_packages_for_keypath(keypath):
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, keypath, 0, winreg.KEY_READ)

                packages = []

                i = 0

                while True:
                    try:
                        subkey_str = winreg.EnumKey(key, i)
                        i += 1
                        subkey = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, keypath + "\\" + subkey_str,
                                                0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY)
                        # print subkey_str

                        j = 0

                        package = rpmlist_command.Package()
                        while True:
                            try:
                                subvalue = winreg.EnumValue(subkey, j)
                                j += 1

                                _val, _data, _type = subvalue

                                _data = str(_data).split("\\u0000")[0]

                                if _val == "DisplayName":
                                    package.displayName = _data
                                elif _val == "DisplayVersion":
                                    package.displayVersion = _data
                                elif _val == "EstimatedSize":
                                    package.estimatedSize = _data
                                elif _val == "InstallDate":
                                    package.installDate = _data

                            except WindowsError as e:
                                break

                        if package.displayName != "Unknown":
                            packages.append(package)

                    except WindowsError as e:
                        break

                return packages

            package_list1 = get_installed_packages_for_keypath(uninstall_path1)
            package_list2 = get_installed_packages_for_keypath(uninstall_path2)
            package_list1.extend(package_list2)

            package_list = list(set(package_list1))

            package_list.sort()

            srv_com["format"] = "windows"
            srv_com["pkg_list"] = server_command.compress(package_list, pickle=True)
        else:
            if os.path.isfile("/etc/debian_version"):
                is_debian = True
            else:
                is_debian = False
            rpm_root_dir, re_strs = ("/", [])
            arguments = getattr(cur_ns, "arguments", None)
            if arguments:
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
        out_f = logging_tools.NewFormList()
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
                        if isinstance(value, tuple):
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
            return limits.mon_STATE_OK, "{}\n{}".format(header_line, str(out_f))
        else:
            return limits.mon_STATE_CRITICAL, "{}, nothing found".format(header_line)


class updatelist_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        required_access = HMAccessClassEnum.level0
        uuid = "9a23e2f7-1953-4476-b4cc-3f3c2c813157"
        description = "Returns a list of software packages that are available for update on the host system."
        create_mon_check_command = False

    def __call__(self, srv_com, cur_ns):
        if PLATFORM_SYSTEM_TYPE == PlatformSystemTypeEnum.WINDOWS:
            import win32com
            import win32com.client

            update = win32com.client.Dispatch('Microsoft.Update.Session')
            update_searcher = update.CreateUpdateSearcher()

            search_result = update_searcher.Search("( IsInstalled = 0 and IsHidden = 0 )")

            update_list = []
            # Update items interface: IUpdate
            for i in range(search_result.Updates.Count):
                title = search_result.Updates.Item(i).Title
                optional = not search_result.Updates.Item(i).IsMandatory
                update_list.append((title, optional))

            srv_com["format"] = "windows"
            srv_com["update_list"] = server_command.compress(update_list, pickle=True)
        else:
            s_time = time.time()
            update_list, log_list = get_update_list()
            for log_entry in log_list:
                self.log(log_entry)
            e_time = time.time()
            srv_com.set_result(
                "ok got list in {}".format(logging_tools.get_diff_time_str(e_time - s_time)),
            )
            srv_com["format"] = "linux"
            srv_com["update_list"] = server_command.compress(update_list, pickle=True)

    @staticmethod
    def interpret(srv_com, cur_ns):
        _ = cur_ns
        update_list = server_command.decompress(srv_com["update_list"].text, pickle=True)
        if update_list:
            return limits.mon_STATE_OK, "{}: {}".format(
                logging_tools.get_plural("update", len(update_list)),
                "\n".join(["{:} {:}".format(_name, _vers) for _name, _vers in update_list])
            )
        else:
            return limits.mon_STATE_OK, "No updates found"


def rpmlist_int(rpm_root_dir, re_strs, is_debian):
    returncode = 0
    if is_debian:
        namere = None
        log_list = [
            "doing dpkg -l command in dir {}".format(rpm_root_dir)
        ]

        rpm_com = ["dpkg", '-l']
        if rpm_root_dir:
            rpm_com.insert(1, '--root={}'.format(rpm_root_dir))

        log_list.append(
            "  dpkg-command is {}".format(" ".join(rpm_com))
        )
    else:
        namere = re.compile("^(?P<name>\S+)\s+(?P<version>\S+)\s+(?P<release>\S+)\s+(?P<size>\S+)"
                            "\s+(?P<arch>\S+)\s+(?P<installtimestamp>\S+)\s+(?P<summary>.*)$")
        log_list = [
            "doing rpm-call in dir {}, mode is {}".format(rpm_root_dir, "via rpm-command")
        ]
        rpm_com = ['rpm',
                   '-qa',
                   '--queryformat=%{NAME} %{VERSION} %{RELEASE} %{SIZE} %{ARCH} %{INSTALLTIME} %{SUMMARY}\n']

        if rpm_root_dir:
            rpm_com.insert(1, '--root={}'.format(rpm_root_dir))

        log_list.append("  rpm-command is {}".format(" ".join(rpm_com)))

    try:
        output = subprocess.check_output(rpm_com, stderr=subprocess.STDOUT).decode()
    except subprocess.CalledProcessError as e:
        ret_dict = e.output.decode()
        returncode = e.returncode
    else:
        ret_dict = {}
        if is_debian:
            lines = output.split("\n")
            while True:
                line = lines.pop(0)
                if line.count("=") > 20:
                    break
            for line in lines:
                try:
                    flags, name, verrel, info = line.split(None, 3)
                except Exception as e:
                    _ = e
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
        else:
            num_tot, num_match = (0, 0)
            log_list.append(" - first line is {}".format(output.split("\n")[0].strip()))
            for rfp in [x for x in [namere.match(actl.strip()) for actl in output.split("\n")] if x]:
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
                    except Exception as e:
                        _ = e
                        size = 0
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

    return log_list, ret_dict, returncode


def get_update_list():
    update_commands = []
    update_list = []
    log_list = []
    errors_happened = False
    update_command = None

    if os.path.isdir("/etc/zypp"):
        def update_command_handler():
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

        update_command = "zypper"
        update_commands.append(([update_command, "refresh"], None))
        update_commands.append(([update_command, "list-updates"], update_command_handler))
    elif os.path.isdir("/etc/yum"):
        def update_command_handler():
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

        update_command = "yum"
        update_commands.append(([update_command, "check-update", "-q"], update_command_handler))
    elif os.path.isdir("/etc/apt"):
        def update_command_handler():
            lines = output.split("\n")
            for line in lines:
                if line.startswith("Inst"):
                    comps = line.split(" ")
                    update_list.append((comps[1], comps[3][1:]))

        update_command = "apt-get"
        update_commands.append(([update_command, "update"], None))
        update_commands.append(([update_command, "--just-print", "upgrade"], update_command_handler))

    for update_command_args, update_command_handler in update_commands:
        try:
            output = subprocess.check_output(update_command_args, stderr=subprocess.STDOUT).decode()
        except subprocess.CalledProcessError as e:
            log_list.append('"{}" failed with return code {}'.format(" ".join(update_command_args), e.returncode))
            errors_happened = True
            break
        else:
            if update_command_handler:
                update_command_handler()

    if errors_happened:
        try:
            subprocess.check_output(["killall", "-s9", update_command], stderr=subprocess.STDOUT)
        except Exception as e:
            _ = e

    return update_list, log_list
