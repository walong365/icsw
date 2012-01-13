#!/usr/bin/python -Ot
#
# Copyright (C) 2007,2008 Andreas Lang-Nevyjel
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
import cs_base_class
import server_command
import os
import logging_tools
import process_tools

NEEDED_IMAGE_DIRS = ["usr", "etc", "bin", "sbin", "var"]

class get_image_list(cs_base_class.server_com):
    def __init__(self):
        cs_base_class.server_com.__init__(self)
        self.set_config(["image_server"])
        self.set_public_via_net(False)
        self.set_used_config_keys(["IMAGE_SOURCE_DIR"])
    def call_it(self, opt_dict, call_params):
        sys.path.append("/usr/local/sbin/modules")
        if os.path.isdir(call_params.get_g_config()["IMAGE_SOURCE_DIR"]):
            t_dirs = ["%s/%s" % (call_params.get_g_config()["IMAGE_SOURCE_DIR"], x) for x in os.listdir(call_params.get_g_config()["IMAGE_SOURCE_DIR"]) if os.path.isdir("%s/%s" % (call_params.get_g_config()["IMAGE_SOURCE_DIR"], x))]
            valid_sys = {}
            for t_dir in t_dirs:
                dirs_found = os.listdir(t_dir)
                if len([x for x in dirs_found if x in NEEDED_IMAGE_DIRS]) == len(NEEDED_IMAGE_DIRS):
                    try:
                        log_lines, sys_dict = process_tools.fetch_sysinfo(t_dir)
                    except:
                        sys_dict = {}
                    else:
                        sys_dict["bitcount"] = {"i386"   : 32,
                                                "i486"   : 32,
                                                "i586"   : 32,
                                                "i686"   : 32,
                                                "x86_64" : 64,
                                                "alpha"  : 64,
                                                "ia64"   : 64}.get(sys_dict.get("arch", "???"), 0)
                    valid_sys[os.path.basename(t_dir)] = sys_dict
                else:
                    dirs_missing = [x for x in NEEDED_IMAGE_DIRS if x not in dirs_found]
                    call_params.log("  ... skipping %s (%s [%s] missing)" % (t_dir,
                                                                             logging_tools.get_plural("subdirectory", len(dirs_missing)),
                                                                             ", ".join(dirs_missing)))
            ret_str = server_command.server_reply()
            ret_str.set_ok_result("found %s" % (logging_tools.get_plural("image", len(valid_sys.keys()))))
            if valid_sys:
                ret_str.set_option_dict({"image_dir" : call_params.get_g_config()["IMAGE_SOURCE_DIR"],
                                         "images"    : valid_sys})
            #ret_str = "ok found "
        else:
            ret_str = "error image-source-dir '%s' not found" % (call_params.get_g_config()["IMAGE_SOURCE_DIR"])
        return ret_str
    
if __name__ == "__main__":
    print "Loadable module, exiting ..."
    sys.exit(0)
    
