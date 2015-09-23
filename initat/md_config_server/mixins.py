# Copyright (C) 2014-2015 Andreas Lang-Nevyjel, init.at
#
# this file is part of md-config-server
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
""" mixins for md-config-server """

import commands
import os
import re
import time

from initat.md_config_server.config import global_config
from initat.tools import configfile, logging_tools, cluster_location


class version_check_mixin(object):
    def _check_md_version(self):
        start_time = time.time()
        self.log("checking type and version of installed monitoring daemon")
        md_version, md_type = ("unknown", "unknown")
        for t_daemon in ["icinga", "icinga-init"]:
            if os.path.isfile("/etc/debian_version"):
                cstat, cout = commands.getstatusoutput("dpkg -s {}".format(t_daemon))
                if not cstat:
                    deb_version = [
                        y for y in [x.strip() for x in cout.split("\n")] if y.startswith("Version")
                    ]
                    if deb_version:
                        md_version = deb_version[0].split(":")[1].strip()
                    else:
                        self.log("No Version-info found in dpkg-list", logging_tools.LOG_LEVEL_WARN)
                else:
                    self.log("Package {} not found in dpkg-list".format(t_daemon), logging_tools.LOG_LEVEL_ERROR)
            else:
                cstat, cout = commands.getstatusoutput("rpm -q {}".format(t_daemon))
                if not cstat:
                    # hm, dirty but working ... check all strings from output
                    for _line in cout.strip().split():
                        rpm_m = re.match("^{}-(?P<version>.*)$".format(t_daemon), _line)
                        if rpm_m:
                            md_version = rpm_m.group("version")
                        else:
                            self.log("Cannot parse {}".format(cout.split()[0].strip()), logging_tools.LOG_LEVEL_WARN)
                else:
                    self.log("Package {} not found in RPM database (result was {})".format(t_daemon, cout), logging_tools.LOG_LEVEL_ERROR)
            if md_version != "unknown":
                md_type = t_daemon.split("-")[0]
                break
        # save to local config
        if md_version[0].isdigit():
            global_config.add_config_entries(
                [
                    ("MD_TYPE", configfile.str_c_var(md_type)),
                    ("MD_VERSION", configfile.int_c_var(int(md_version.split(".")[0]))),
                    ("MD_RELEASE", configfile.int_c_var(int(md_version.split(".")[1]))),
                    ("MD_VERSION_STRING", configfile.str_c_var(md_version)),
                    ("MD_BASEDIR", configfile.str_c_var(os.path.join("/opt", md_type))),
                    ("MAIN_CONFIG_NAME", configfile.str_c_var(md_type)),
                    ("MD_LOCK_FILE", configfile.str_c_var("{}.lock".format(md_type))),
                ]
            )
        # device_variable local to the server
        _dv = cluster_location.db_device_variable(
            global_config["SERVER_IDX"],
            "md_version",
            description="Version of the Monitor-daemon package",
            value=md_version
        )
# #        if dv.is_set():
# #            dv.set_value(md_version)
# #            dv.update(dc)
        cluster_location.db_device_variable(
            global_config["SERVER_IDX"],
            "md_version",
            description="Version of the Monitor-daemon RPM",
            value=md_version,
            force_update=True
        )
        cluster_location.db_device_variable(
            global_config["SERVER_IDX"],
            "md_type",
            description="Type of the Monitor-daemon RPM",
            value=md_type,
            force_update=True
        )
        if md_version == "unknown":
            self.log(
                "No installed monitor-daemon found (version set to {})".format(
                    md_version
                ),
                logging_tools.LOG_LEVEL_CRITICAL
            )
        else:
            self.log(
                "Discovered installed monitor-daemon {}, version {}".format(
                    md_type,
                    md_version
                )
            )
        end_time = time.time()
        self.log("monitor-daemon version discovery took {}".format(logging_tools.get_diff_time_str(end_time - start_time)))

    def _check_relay_version(self):
        from initat.client_version import VERSION_STRING as relay_version
        relay_split = [int(value) for value in relay_version.split("-")[0].split(".")]
        global_config.add_config_entries(
            [
                ("HAS_SNMP_RELAYER", configfile.bool_c_var(True))
            ]
        )
        self.log("host-relay version {}".format(relay_version))
