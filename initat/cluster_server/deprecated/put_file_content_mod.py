#!/usr/bin/python -Ot
#
# Copyright (C) 2007 Andreas Lang-Nevyjel
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
import logging_tools
import server_command
import os

class put_file_content(cs_base_class.server_com):
    def __init__(self):
        cs_base_class.server_com.__init__(self)
    def call_it(self, opt_dict, call_params):
        ret_str = server_command.server_reply()
        file_dict = opt_dict.get("file_dict", {})
        if file_dict:
            for file_name, file_stuff in file_dict.iteritems():
                try:
                    file(file_name, "w").write(file_stuff["content"])
                    os.chown(file_name, file_stuff["uid"], file_stuff["gid"])
                    os.chmod(file_name, file_stuff["mode"])
                except:
                    pass
            ret_str.set_ok_result("ok changed %s" % (logging_tools.get_plural("file", len(file_dict.keys()))))
        else:
            ret_str.set_warn_result("warn no filenames given")
        return ret_str

if __name__ == "__main__":
    print "Loadable module, exiting ..."
    sys.exit(0)
    
