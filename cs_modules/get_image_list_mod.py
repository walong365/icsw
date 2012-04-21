#!/usr/bin/python -Ot
#
# Copyright (C) 2007,2008,2012 Andreas Lang-Nevyjel
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
    class Meta:
        needed_configs = ["image_server"]
        needed_config_keys = ["IMAGE_SOURCE_DIR"]
    def _call(self):
        #sys.path.append("/usr/local/sbin/modules")
        source_dir = self.global_config["IMAGE_SOURCE_DIR"]
        if os.path.isdir(source_dir):
            t_dirs = ["%s/%s" % (source_dir, sub_dir) for sub_dir in os.listdir(source_dir) if os.path.isdir("%s/%s" % (source_dir, sub_dir))]
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
                    self.log("  ... skipping %s (%s [%s] missing)" % (t_dir,
                                                                      logging_tools.get_plural("subdirectory", len(dirs_missing)),
                                                                      ", ".join(dirs_missing)))
            self.srv_com["result"].attrib.update({
                "reply" : "found %s" % (logging_tools.get_plural("image", len(valid_sys.keys()))),
                "state" : "%d" % (server_command.SRV_REPLY_STATE_OK)})
            if valid_sys:
                image_list = self.srv_com.builder("image_list", image_dir=source_dir)
                self.srv_com["result"] = image_list
                for image_name, sys_dict in valid_sys.iteritems():
                    sys_dict["bitcount"] = "%d" % (sys_dict["bitcount"])
                    image_list.append(self.srv_com.builder("image", image_name, **sys_dict))
        else:
            self.srv_com["result"].attrib.update({
                "reply" : "error image-source-dir '%s' not found" % (source_dir),
                "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR)})
        #print unicode(self.srv_com)
    
if __name__ == "__main__":
    print "Loadable module, exiting ..."
    sys.exit(0)
    
