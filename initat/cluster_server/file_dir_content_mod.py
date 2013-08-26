#!/usr/bin/python -Ot
#
# Copyright (C) 2007, 2013 Lang-Nevyjel
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
""" fetches informations from files or directories """

import cs_base_class
import logging_tools
import os
import process_tools
import server_command
import sys

class get_file_content(cs_base_class.server_com):
    def _call(self, cur_inst):
        for file_entry in cur_inst.srv_com.xpath(None, ".//ns:file"):
            try:
                content = file(file_entry.attrib["name"], "r").read()
            except:
                file_entry.attrib["error"] = "1"
                file_entry.attrib["error_str"] = process_tools.get_except_info()
            else:
                file_entry.attrib["error"] = "0"
                file_entry.attrib["size"] = "%d" % (len(content))
                file_entry.attrib["lines"] = "%d" % (content.count("\n") + 1)
                file_entry.text = content
        cur_inst.srv_com["result"].attrib.update({
            "reply" : "read file contents",
            "state" : "%d" % (server_command.SRV_REPLY_STATE_OK)
        })

if False:
    class get_file_conten2t(cs_base_class.server_com):
        def __init__(self):
            cs_base_class.server_com.__init__(self)
            self.set_write_log(0)
        def call_it(self, opt_dict, call_params):
            ret_str = server_command.server_reply()
            f_names = opt_dict.get("file_names", [])
            if f_names:
                file_dict = {}
                for file_name in f_names:
                    res_dict = {"found" : False,
                                "name"  : file_name}
                    if os.path.isfile(file_name):
                        res_dict["found"] = True
                        try:
                            stat_res = os.stat(file_name)
                        except:
                            res_dict["error"] = process_tools.get_except_info()
                        else:
                            res_dict["stat"] = stat_res
                            try:
                                content = file(file_name, "r").read()
                            except:
                                res_dict["error"] = process_tools.get_except_info()
                            else:
                                res_dict["content"] = content
                    file_dict[file_name] = res_dict
                ret_str.set_option_dict(file_dict)
                ret_str.set_ok_result("ok fetched %s" % (logging_tools.get_plural("file", len(f_names))))
            else:
                ret_str.set_warn_result("warn no filenames given")
            return ret_str

# class get_dir_content(cs_base_class.server_com):
#     def __init__(self):
#         cs_base_class.server_com.__init__(self)
#         self.set_write_log(0)
#     def call_it(self, opt_dict, call_params):
#         ret_str = server_command.server_reply()
#         dir_names = opt_dict.get("dir_names", [])
#         if dir_names:
#             dir_dict = {}
#             for dir_name in dir_names:
#                 res_dict = {"found"   : False,
#                             "name"    : dir_name,
#                             "entries" : {"dirs"  : {},
#                                          "files" : {}}}
#                 if os.path.isdir(dir_name):
#                     res_dict["found"] = True
#                     for d_name, sub_dirs, sub_files in os.walk(dir_name, topdown=True):
#                         for sub_dir in sub_dirs:
#                             res_dict["entries"]["dirs"][sub_dir] = os.stat("%s/%s" % (d_name, sub_dir))
#                         for sub_file in sub_files:
#                             full_name = "%s/%s" % (d_name, sub_file)
#                             if os.path.islink(full_name):
#                                 res_dict["entries"]["files"][sub_file] = ("L", os.readlink(full_name))
#                             elif os.path.isfile(full_name):
#                                 res_dict["entries"]["files"][sub_file] = ("F", os.stat(full_name))
#                         break
#                 dir_dict[dir_name] = res_dict
#             ret_str.set_option_dict(dir_dict)
#             ret_str.set_ok_result("ok checked %s" % (logging_tools.get_plural("dir", len(dir_names))))
#         else:
#             ret_str.set_warn_result("warn no dirnames given")
#         return ret_str
#
# class get_file_info(cs_base_class.server_com):
#     def __init__(self):
#         cs_base_class.server_com.__init__(self)
#         self.set_write_log(0)
#     def call_it(self, opt_dict, call_params):
#         ret_str = server_command.server_reply()
#         f_names = opt_dict.get("file_names", [])
#         if f_names:
#             file_dict = {}
#             for file_name in f_names:
#                 res_dict = {"found" : False,
#                             "name"  : file_name}
#                 if os.path.isfile(file_name):
#                     res_dict["found"] = True
#                     try:
#                         stat_res = os.stat(file_name)
#                     except:
#                         res_dict["error"] = process_tools.get_except_info()
#                     else:
#                         res_dict["stat"] = stat_res
#                 file_dict[file_name] = res_dict
#             ret_str.set_option_dict(file_dict)
#             ret_str.set_ok_result("ok checked %s" % (logging_tools.get_plural("file", len(f_names))))
#         else:
#             ret_str.set_warn_result("warn no filenames given")
#         return ret_str

if __name__ == "__main__":
    print "Loadable module, exiting ..."
    sys.exit(0)

