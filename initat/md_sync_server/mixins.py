# Copyright (C) 2016 Andreas Lang-Nevyjel, init.at
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
""" mixins for md-sync-server """

import commands
import os
import re
import time

from initat.md_sync_server.config import global_config
from initat.tools import configfile, logging_tools, process_tools


class VersionCheckMixin(object):
    def VCM_check_md_version(self):
        start_time = time.time()
        _info_file = "/opt/cluster/etc/mon_info"
        self.log(
            "checking type and version of installed monitoring daemon via file {}".format(
                _info_file
            )
        )
        if os.path.isfile(_info_file):
            try:
                _content = {
                    _key.strip(): _value.strip().replace("\"", "") for _key, _value in [
                        _line.split("=") for _line in file(
                            _info_file,
                            "r"
                        ).read().split("\n") if _line.count("=")
                    ]
                }
            except:
                self.log(
                    "error reading from {}: {}".format(
                        _info_file,
                        process_tools.get_except_info()
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
            else:
                md_type = _content["MON_TYPE"].lower()
                md_versrel = _content["MON_VERSION"].lower()
                md_version, md_release = md_versrel.split("-", 1)
                global_config.add_config_entries(
                    [
                        ("MD_TYPE", configfile.str_c_var(md_type)),
                        ("MD_VERSION", configfile.int_c_var(int(md_version.split(".")[0]))),
                        ("MD_RELEASE", configfile.int_c_var(int(md_version.split(".")[1]))),
                        ("MD_VERSION_STRING", configfile.str_c_var(md_version)),
                        ("MD_BASEDIR", configfile.str_c_var(os.path.join("/opt", "cluster", md_type))),
                        ("MAIN_CONFIG_NAME", configfile.str_c_var(md_type)),
                        ("MD_LOCK_FILE", configfile.str_c_var("{}.lock".format(md_type))),
                    ]
                )
                self.log(
                    "Discovered installed monitor-daemon {}, version {}".format(
                        md_type,
                        md_version
                    )
                )
        end_time = time.time()
        self.log("monitor-daemon version discovery took {}".format(logging_tools.get_diff_time_str(end_time - start_time)))

    def VCM_check_relay_version(self):
        from initat.client_version import VERSION_STRING as relay_version
        global_config.add_config_entries(
            [
                ("HAS_SNMP_RELAYER", configfile.bool_c_var(True))
            ]
        )
        self.log("host-relay version {}".format(relay_version))
