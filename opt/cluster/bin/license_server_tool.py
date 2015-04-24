#!/usr/bin/python-init -Otu
#
# Copyright (C) 2007,2012-2014 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
# encoding: -*- utf8 -*-
#
# This file is part of init-license-tools
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

import commands
import getopt
from initat.tools import logging_tools
import os
from initat.tools import process_tools
import psutil
import sys
import time

DEFAULT_CFG_DIR = "/etc/sysconfig/init-license-server.d"
LICENSE_DIR = "/opt/cluster/license_tools"

LICENSE_LOG_DIR = os.path.join(LICENSE_DIR, "log")
LICENSE_SCRIPT_DIR = os.path.join(LICENSE_DIR, "scripts")
LICENSE_PID_DIR = os.path.join(LICENSE_DIR, "pids")


class license_object(object):
    def __init__(self, full_name):
        self.__full_name = full_name
        self.__val_dict = {
            "USE_ROOT": "no",
            "ENABLED": "yes"
        }
        self._read_license()
        self._check_for_settings()

    def set_target_user_and_group(self, t_user, t_group):
        self.__target_user, self.__target_group = (t_user, t_group)

    def _read_license(self):
        self.__lic_lines = [x.strip() for x in file(self.__full_name, "r").read().split("\n")]
        line_num = 0
        for lic_line in self.__lic_lines:
            line_num += 1
            if lic_line.startswith("#") or not lic_line:
                # comment line
                pass
            elif lic_line.count("="):
                key, value = lic_line.split("=", 1)
                self.__val_dict[key.strip().upper()] = value.strip()
            else:
                raise ValueError(
                    "unparsable line {:d} in license-file: {}".format(
                        line_num,
                        lic_line
                    )
                )

    def _check_for_settings(self):
        # checks for missing keys and files (if enabled)
        if self["ENABLED"] == "yes":
            needed_keys = set(
                [
                    "NAME",
                    "LMGRD_BINARY",
                    "LICENSE_FILE"
                ]
            )
            self["SAVE_NAME"] = self["NAME"].replace(" ", "_").replace("__", "_").replace("__", "_")
            found_keys = needed_keys & set(self.__val_dict.keys())
            if len(found_keys) != len(needed_keys):
                raise KeyError("some keys missing: {}".format(", ".join(sorted(list(needed_keys - found_keys)))))
            if not os.path.isfile(self["LMGRD_BINARY"]):
                raise IOError("cannot find LMGRD_BINARY {}".format(self["LMGRD_BINARY"]))
            if not os.path.isfile(self["LICENSE_FILE"]) and not os.path.isdir(self["LICENSE_FILE"]):
                raise IOError("cannot find LICENSE_FILE {} (file or directory)".format(self["LICENSE_FILE"]))
            self["DEBUG_LOG"] = os.path.join(
                LICENSE_LOG_DIR,
                "{}.dbg".format(self["SAVE_NAME"])
            )
            self["STDOUT_LOG"] = os.path.join(
                LICENSE_LOG_DIR,
                "{}.log".format(self["SAVE_NAME"])
            )
            self["START_SCRIPT"] = os.path.join(
                LICENSE_LOG_DIR,
                "{}.start.sh".format(self["SAVE_NAME"])
            )
            self["STOP_SCRIPT"] = os.path.join(
                LICENSE_LOG_DIR,
                "{}.stop.sh".format(self["SAVE_NAME"])
            )
            self._write_scripts()

    def get_license_files(self):
        return self.__license_files

    def __getitem__(self, key):
        return self.__val_dict[key]

    def __setitem__(self, key, value):
        self.__val_dict[key] = value

    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        logging_tools.my_syslog(what, lev)

    def _write_scripts(self):
        start_lines = [
            "#!/bin/bash",
            "{} -c {} -x lmdown -l +{} >>{} 2>&1".format(
                self["LMGRD_BINARY"],
                self["LICENSE_FILE"],
                self["DEBUG_LOG"],
                self["STDOUT_LOG"]),
            ""
        ]
        file(self["START_SCRIPT"], "w").write("\n".join(start_lines))
        os.chmod(self["START_SCRIPT"], 0550)

    def get_pid(self):
        # try to extract the pid of the (running ?) license server
        exe_lut = {}
        for value in psutil.process_iter():
            if value.exe():
                exe_lut.setdefault(value.exe(), []).append(value.pid)
        pid = exe_lut.get(self["LMGRD_BINARY"], [0])[0]
        return pid

    def start_server(self):
        if self.get_pid():
            return 7, "already running"
        else:
            if self["USE_ROOT"] == "no":
                start_com = "su - -s /bin/bash {} {}".format(
                    self.__target_user,
                    self["START_SCRIPT"]
                )
            else:
                start_com = self["START_SCRIPT"]
            stat, out = commands.getstatusoutput(start_com)
            if stat:
                self.log(
                    "error calling start_script via {} ({:d}): {}".format(
                        start_com,
                        stat,
                        out
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
                return 1, "start error"
            else:
                self.log("successfully called %s" % (start_com))
                return 0, "started"

    def stop_server(self):
        server_pid = self.get_pid()
        if server_pid:
            try:
                os.kill(server_pid, 15)
                time.sleep(1)
                os.kill(server_pid, 9)
            except:
                pass
            return 0, "stopped"
        else:
            return 1, "not running"

    def server_status(self):
        server_pid = self.get_pid()
        if server_pid:
            return 0, "running"
        else:
            return 5, "not running"


class license_tree(object):
    def __init__(self, cfg_dir):
        self.__num_lics, self.__num_lics_enabled, self.__error_lics = (0, 0, [])
        self.__cfg_dir = cfg_dir
        self.__license_dict = {}
        self._read_licenses()

    def _read_licenses(self):
        for lic_file in os.listdir(self.__cfg_dir):
            full_name = os.path.join(self.__cfg_dir, lic_file)
            try:
                new_lic = license_object(full_name)
            except:
                self.__error_lics.append(lic_file)
                self.__error_lics.sort()
                self.log(
                    "Error reading license from file {}: {}".format(
                        full_name,
                        process_tools.get_except_info()
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
            else:
                self.log(
                    "read license '{}' from file {}".format(
                        new_lic["NAME"],
                        full_name
                    )
                )
                self.__num_lics += 1
                self.__license_dict[new_lic["NAME"]] = new_lic
                if new_lic["ENABLED"] == "yes":
                    self.__num_lics_enabled += 1

    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        logging_tools.my_syslog(what, lev)

    def __len__(self):
        return self.__num_lics_enabled

    def get_error_licenses(self):
        return self.__error_lics

    def get_licenses(self, only_enabled=True):
        if only_enabled:
            return [x for x in self.__license_dict.values() if x["ENABLED"] == "yes"]
        else:
            return self.__license_dict.values()


def main():
    print " ",
    try:
        opts, args = getopt.getopt(sys.argv[1:], "u:g:l:")
    except getopt.GetoptError:
        print "Commandline error : {}".format(process_tools.get_except_info())
        sys.exit(1)
    target_user, target_group, target_license = ("root", "root", None)
    for opt, arg in opts:
        if opt == "-u":
            target_user = arg
        if opt == "-g":
            target_group = arg
        if opt == "-l":
            if arg == "all":
                pass
            else:
                target_license = arg
    process_tools.fix_directories(target_user, target_group, [LICENSE_LOG_DIR,
                                                              LICENSE_SCRIPT_DIR,
                                                              LICENSE_PID_DIR])
    ok_commands = ["start", "stop", "status"]
    if len(args) != 1:
        print "Need argument (one of %s)" % (", ".join(ok_commands))
        sys.exit(1)
    command = args[0]
    if command not in ok_commands:
        print "Wrong argument (one of %s)" % (", ".join(ok_commands))
        sys.exit(1)
    lic_tree = license_tree(DEFAULT_CFG_DIR)
    error_lics = lic_tree.get_error_licenses()
    if error_lics:
        print "error reading %s: %s" % (logging_tools.get_plural("license file", len(error_lics)),
                                        ", ".join(error_lics)),
        sys.exit(1)
    if lic_tree:
        ret_stat = 0
        ok_lics, error_lics = ([], [])
        out_lines = []
        if target_license is None:
            target_licenses = [x["NAME"] for x in lic_tree.get_licenses()]
        else:
            target_licenses = [target_license]
        for lic in lic_tree.get_licenses():
            if lic["NAME"] in target_licenses:
                lic.set_target_user_and_group(target_user, target_group)
                if command == "start":
                    loc_stat, ret_str = lic.start_server()
                elif command == "stop":
                    loc_stat, ret_str = lic.stop_server()
                else:
                    loc_stat, ret_str = lic.server_status()
                if loc_stat:
                    ret_stat = 1
                if loc_stat:
                    error_lics.append(lic["NAME"])
                else:
                    ok_lics.append(lic["NAME"])
                out_lines.append("%s: %s" % (lic["NAME"], ret_str))
            else:
                out_lines.append("%s: <skipped>" % (lic["NAME"]))
        f_line_f = []
        if error_lics:
            f_line_f.append("%d error: %s" % (len(error_lics),
                                              ", ".join(error_lics)))
        if ok_lics:
            f_line_f.append("%d ok: %s" % (len(ok_lics),
                                           ", ".join(ok_lics)))
        out_lines.insert(0, ", ".join(f_line_f))
        sys.stdout.write("\n".join(out_lines))
        sys.exit(ret_stat)
    else:
        sys.exit(5)

if __name__ == "__main__":
    main()
