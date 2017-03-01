# Copyright (C) 2016-2017 Andreas Lang-Nevyjel, init.at
#
# this file is part of icsw-server
#
# Send feedback to: <lang-nevyjel@init.at>
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
""" mixins for md-sync-server and md-config-server """

import os
import time

from initat.constants import MON_DAEMON_INFO_FILE
from initat.tools import configfile, logging_tools, process_tools


class VersionCheckMixin(object):
    def VCM_check_md_version(self, global_config):
        start_time = time.time()
        _info_file = MON_DAEMON_INFO_FILE
        self.log(
            "checking type and version of installed monitoring daemon via file {}".format(
                _info_file
            )
        )
        if os.path.isfile(_info_file):
            try:
                _content = {
                    _key.strip(): _value.strip().replace("\"", "") for _key, _value in [
                        _line.split("=") for _line in open(
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
                        ("MD_TYPE", configfile.StringConfigVar(md_type)),
                        ("MD_VERSION_STRING", configfile.StringConfigVar(md_versrel)),
                        ("MD_VERSION", configfile.StringConfigVar(md_version)),
                        ("MD_RELEASE", configfile.StringConfigVar(md_release)),
                        ("MD_BASEDIR", configfile.StringConfigVar(os.path.join("/opt", "cluster", md_type))),
                        ("MAIN_CONFIG_NAME", configfile.StringConfigVar(md_type)),
                        ("MD_LOCK_FILE", configfile.StringConfigVar("{}.lock".format(md_type))),
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
