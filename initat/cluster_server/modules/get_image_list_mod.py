# Copyright (C) 2007-2008,2012-2015 Andreas Lang-Nevyjel
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

""" checks image directories for valid images """

from initat.cluster_server.config import global_config
import cs_base_class
from initat.tools import logging_tools
import os
from initat.tools import process_tools
from initat.tools import server_command

NEEDED_IMAGE_DIRS = ["usr", "etc", "bin", "sbin", "var"]


class get_image_list(cs_base_class.server_com):
    class Meta:
        needed_configs = ["image_server"]
        needed_config_keys = ["IMAGE_SOURCE_DIR"]

    def _call(self, cur_inst):
        source_dir = global_config["IMAGE_SOURCE_DIR"]
        if os.path.isdir(source_dir):
            t_dirs = [os.path.join(source_dir, sub_dir) for sub_dir in os.listdir(source_dir) if os.path.isdir(os.path.join(source_dir, sub_dir))]
            valid_sys = {}
            for t_dir in t_dirs:
                dirs_found = os.listdir(t_dir)
                if len([x for x in dirs_found if x in NEEDED_IMAGE_DIRS]) == len(NEEDED_IMAGE_DIRS):
                    try:
                        _log_lines, sys_dict = process_tools.fetch_sysinfo(root_dir=t_dir)
                    except:
                        sys_dict = {}
                    else:
                        sys_dict["bitcount"] = {
                            "i386": 32,
                            "i486": 32,
                            "i586": 32,
                            "i686": 32,
                            "x86_64": 64,
                            "alpha": 64,
                            "ia64": 64
                        }.get(sys_dict.get("arch", "???"), 0)
                    valid_sys[os.path.basename(t_dir)] = sys_dict
                else:
                    dirs_missing = [x for x in NEEDED_IMAGE_DIRS if x not in dirs_found]
                    self.log(
                        "  ... skipping {} ({} [{}] missing)".format(
                            t_dir,
                            logging_tools.get_plural("subdirectory", len(dirs_missing)),
                            ", ".join(dirs_missing)
                        )
                    )
            cur_inst.srv_com.set_result(
                "found {}".format(logging_tools.get_plural("image", len(valid_sys.keys())))
            )
            if valid_sys:
                image_list = cur_inst.srv_com.builder("image_list", image_dir=source_dir)
                cur_inst.srv_com["result"] = image_list
                for image_name, sys_dict in valid_sys.iteritems():
                    sys_dict["bitcount"] = "{:d}".format(sys_dict["bitcount"])
                    image_list.append(cur_inst.srv_com.builder("image", image_name, **sys_dict))
        else:
            cur_inst.srv_com.set_result(
                "error image-source-dir '{}' not found".format(source_dir),
                server_command.SRV_REPLY_STATE_ERROR
            )
